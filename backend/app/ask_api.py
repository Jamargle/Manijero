"""HTTP boundary for the local, source-grounded ``POST /ask`` route."""

from datetime import date, datetime, timezone
import json
import os
import re
import threading
from pathlib import Path
from typing import Annotated, Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from app import answer_inspection, answer_trace, health_metrics
from app.abstention import (
    Abstention,
    prepare_corpus,
    to_abstention_response,
)
from app.clarification import (
    DEFAULT_MAX_CLAIMS,
    NeedsLandClarification,
    answer_with_clarification,
    to_clarification_response,
)
from app.gemini_generation import ProviderResolution
from app.input_guardrails import screen_question
from app.generation import Answered, to_answer_response
from app.knowledge_release import ReleaseError, load_published_corpus
from app.answer_trace import AnswerTrace
from app.pilot_logging import operational_log
from app.retention import RetentionStore, retain_if_opted_in
from app.retrieval_backend import RetrievalBackend, get_retrieval_backend
from app.retrieval import CatalogRejectedError, PassageSetError, Retriever, validate_passage_set
from app.source_catalog import CatalogReadError, load_catalog, validate_catalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "source_catalog.json"
PASSAGES_PATH = REPOSITORY_ROOT / "knowledge" / "passages.json"
# Opt-in: when set, requests read the verified published knowledge release under this root.
KNOWLEDGE_RELEASE_ROOT_ENV = "MANIJERO_KNOWLEDGE_RELEASE_ROOT"


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MinimalLandContext(ClosedModel):
    id: StrictStr = Field(min_length=1, max_length=128)
    municipality: StrictStr = Field(
        default_factory=lambda: None, min_length=1, max_length=160
    )
    water_regime: Literal["dryland", "irrigated", "mixed", "unknown"] = Field(
        default_factory=lambda: None
    )
    production_method: Literal[
        "conventional", "organic", "mixed", "unknown"
    ] = Field(default_factory=lambda: None)


class LandContext(ClosedModel):
    mode: Literal["general", "all_active", "selected"]
    lands: list[MinimalLandContext]

    @model_validator(mode="after")
    def validate_mode_and_lands(self) -> "LandContext":
        ids = [land.id for land in self.lands]
        if len(ids) != len(set(ids)):
            raise ValueError("land ids must be unique")
        if self.mode == "general" and self.lands:
            raise ValueError("general mode must not include lands")
        if self.mode in {"all_active", "selected"} and not self.lands:
            raise ValueError("land-aware mode must include at least one land")
        return self


class AskRequest(ClosedModel):
    question: StrictStr = Field(min_length=1, max_length=2000)
    land_context: LandContext
    # Explicit, per-question permission to keep the redacted question and final answer for
    # product improvement. Absent means false; it never changes the answer.
    retain_for_improvement: StrictBool = False


class AnswerSource(ClosedModel):
    title: StrictStr = Field(min_length=1, max_length=300)
    issuing_body: StrictStr = Field(min_length=1, max_length=200)
    url: AnyHttpUrl
    location: StrictStr = Field(min_length=1, max_length=200)
    published_or_updated_on: date = Field(strict=False)
    verified_on: date = Field(strict=False)
    excerpt: StrictStr = Field(min_length=1, max_length=2000)


class InspectionVector(ClosedModel):
    used: StrictBool
    fallback_code: StrictStr | None


class InspectionPassage(ClosedModel):
    rank: StrictInt
    passage_id: StrictStr
    source_id: StrictStr
    title: StrictStr
    location: StrictStr
    score: StrictFloat | StrictInt
    lexical_rank: StrictInt | None
    lexical_score: StrictFloat | StrictInt | None
    vector_similarity: StrictFloat | StrictInt | None
    cited: StrictBool
    excerpt: StrictStr = Field(max_length=2000)


class InspectionRetrieval(ClosedModel):
    mode: Literal["bm25", "hybrid"]
    k: StrictInt
    search_calls: StrictInt
    duration_ms: StrictInt
    vector: InspectionVector | None
    passages: list[InspectionPassage]


class InspectionDrafting(ClosedModel):
    provider: StrictStr | None
    outcome: StrictStr | None
    status: StrictStr | None
    cited_markers: list[StrictInt]
    duration_ms: StrictInt | None


class InspectionClaim(ClosedModel):
    index: StrictInt
    markers: list[StrictInt]
    ok: StrictBool
    issues: list[StrictStr]


class InspectionVerification(ClosedModel):
    ok: StrictBool
    issues: list[StrictStr]
    claims: list[InspectionClaim]
    duration_ms: StrictInt | None


class InspectionOutcome(ClosedModel):
    abstention_reason: StrictStr | None
    generation_reason: StrictStr | None
    cited_passage_ids: list[StrictStr]


class AnswerInspection(ClosedModel):
    """Development-profile-only debug view of one answer; never sent in pilot, QA, or prod."""

    schema_version: Literal["answer-inspection-v1"] = Field(alias="schema")
    retrieval: InspectionRetrieval | None
    drafting: InspectionDrafting | None
    verification: InspectionVerification | None
    outcome: InspectionOutcome
    total_ms: StrictInt

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class AskResponse(ClosedModel):
    status: Literal["answered", "abstained", "needs_land_clarification"]
    answer: StrictStr = Field(max_length=1200)
    sources: list[AnswerSource]
    land_scope: Literal["general", "all_active", "selected"]
    land_ids_to_choose: list[Annotated[StrictStr, Field(min_length=1, max_length=128)]]
    inspection: AnswerInspection | None = None


class CorpusDocuments(ClosedModel):
    catalog: Any
    passages: Any
    load_error: bool = False


def get_as_of_date() -> date:
    """Return today's UTC date for catalog expiry checks."""

    return datetime.now(timezone.utc).date()


def get_active_campaign() -> str:
    value = os.environ.get("MANIJERO_ACTIVE_CAMPAIGN", "")
    if not re.fullmatch(r"\d{4}", value):
        raise _unavailable_corpus_error()
    return value


def get_retrieval_k() -> int:
    return 5


def load_corpus_documents(
    catalog_path: Path | None = None,
    passages_path: Path | None = None,
) -> CorpusDocuments:
    """Read canonical repository artifacts; failures are translated by the route.

    The optional paths are an operator-tool seam (preflight and restore verification);
    the request path always uses the canonical artifact locations. When
    ``MANIJERO_KNOWLEDGE_RELEASE_ROOT`` is set and no path is given, the request reads
    the verified published release instead (:mod:`app.knowledge_release`).
    """

    if catalog_path is None and passages_path is None:
        release_root = os.environ.get(KNOWLEDGE_RELEASE_ROOT_ENV, "").strip()
        if release_root:
            return _load_published_release(Path(release_root))
    try:
        catalog = load_catalog(catalog_path or CATALOG_PATH)
        passages = json.loads((passages_path or PASSAGES_PATH).read_text(encoding="utf-8"))
    except (CatalogReadError, OSError, json.JSONDecodeError):
        return CorpusDocuments(catalog=None, passages=None, load_error=True)
    return CorpusDocuments(catalog=catalog, passages=passages)


def _load_published_release(root: Path) -> CorpusDocuments:
    """Read the verified ``current`` release; any failure is the generic unavailable path."""

    try:
        catalog, passages, release_id = load_published_corpus(root)
    except ReleaseError as error:
        _note_release_outcome(error.release_id, "refused", error.code)
        return CorpusDocuments(catalog=None, passages=None, load_error=True)
    except (OSError, ValueError):
        _note_release_outcome(None, "refused", "release_unreadable")
        return CorpusDocuments(catalog=None, passages=None, load_error=True)
    _note_release_outcome(release_id, "served", "ok")
    return CorpusDocuments(catalog=catalog, passages=passages)


_RELEASE_OUTCOME_LOCK = threading.Lock()
_LAST_RELEASE_OUTCOME: tuple[str | None, str, str] | None = None


def _note_release_outcome(release_id: str | None, state: str, reason: str) -> None:
    """Write one ``knowledge_release`` record only when the outcome changes."""

    global _LAST_RELEASE_OUTCOME
    outcome = (release_id, state, reason)
    with _RELEASE_OUTCOME_LOCK:
        if outcome == _LAST_RELEASE_OUTCOME:
            return
        _LAST_RELEASE_OUTCOME = outcome
    operational_log("knowledge_release", release_id=release_id or "none", state=state, reason=reason)


def last_release_outcome() -> tuple[str | None, str] | None:
    """The last ``(release_id, state)`` a request saw, for ``/metrics``; ``None`` if none yet."""

    with _RELEASE_OUTCOME_LOCK:
        outcome = _LAST_RELEASE_OUTCOME
    return None if outcome is None else (outcome[0], outcome[1])


def get_corpus_documents() -> CorpusDocuments:
    """FastAPI dependency seam for local files and fixture-backed route tests."""

    return load_corpus_documents()


def get_retention_store(request: Request) -> RetentionStore | None:
    """The product-improvement store built by ``create_app``; ``None`` keeps retention off."""

    return getattr(request.app.state, "retention_store", None)


def get_generation_provider(request: Request) -> ProviderResolution | None:
    """The answer provider resolved by ``create_app``; ``None`` keeps the extractive path."""

    return getattr(request.app.state, "generation_provider", None)


def get_answer_trace(request: Request) -> AnswerTrace | None:
    """The local debug trace built by ``create_app``; ``None`` keeps tracing off."""

    return getattr(request.app.state, "answer_trace", None)


def get_answer_inspection(request: Request) -> bool:
    """Whether ``create_app`` resolved the development-only inspection as on."""

    return bool(getattr(request.app.state, "answer_inspection", False))


router = APIRouter()


@router.post(
    "/ask",
    operation_id="askQuestion",
    summary="Ask for a source-grounded answer",
    response_model=AskResponse,
    response_model_exclude_unset=True,
    responses={
        400: {"description": "Malformed JSON request."},
        422: {"description": "Request shape, bounds, enum, or land-context validation failed."},
        503: {"description": "The local answer corpus is unavailable or unsafe."},
    },
)
def ask_question(
    request: AskRequest,
    corpus_documents: CorpusDocuments = Depends(get_corpus_documents),
    as_of: date = Depends(get_as_of_date),
    active_campaign: str = Depends(get_active_campaign),
    retrieval_k: int = Depends(get_retrieval_k),
    retention_store: RetentionStore | None = Depends(get_retention_store),
    retrieval_backend: RetrievalBackend = Depends(get_retrieval_backend),
    generation: ProviderResolution | None = Depends(get_generation_provider),
    trace: AnswerTrace | None = Depends(get_answer_trace),
    inspect: bool = Depends(get_answer_inspection),
) -> Dict[str, Any]:
    """Run accepted corpus and answer decisions, then the separate opt-in retention step."""

    session = (
        trace.open(collect=inspect)
        if trace is not None
        else answer_trace.TraceSession(None, collect=inspect)
    )
    land_scope = request.land_context.mode
    screened = screen_question(request.question)
    if screened is not None:
        return _screened_reply(request, session, inspect, retention_store, as_of, screened)
    try:
        response = _answer(
            request,
            corpus_documents,
            as_of,
            active_campaign,
            retrieval_k,
            retrieval_backend,
            generation,
        )
    except HTTPException:
        session.finish(question=request.question, land_scope=land_scope, response=None)
        raise
    finally:
        session.release()
    # The trace is written once the answer exists; it cannot change or fail it.
    session.finish(question=request.question, land_scope=land_scope, response=response)
    # Retention runs after the answer exists and cannot change or fail it. Only a fixed
    # outcome code is logged, and only when something was attempted.
    outcome = retain_if_opted_in(
        retention_store,
        opted_in=request.retain_for_improvement,
        question=request.question,
        land_context=request.land_context.model_dump(exclude_none=True),
        response=response,
        today=as_of,
    )
    if outcome in {"redaction_failed", "store_failed"}:
        operational_log("retention_skipped", outcome=outcome)
    if inspect:
        # Attached last, so it is never traced or retained, and a failure only omits it.
        try:
            return dict(response, inspection=answer_inspection.build_inspection(session.collector))
        except answer_inspection.InspectionError as error:
            operational_log("answer_inspection_skipped", reason=error.code)
    return response


def _screened_reply(
    request: AskRequest,
    session: "answer_trace.TraceSession",
    inspect: bool,
    retention_store: RetentionStore | None,
    as_of: date,
    reason: str,
) -> Dict[str, Any]:
    """Answer a screened question with its pinned message, before any retrieval.

    A ``personal_data`` hit is never retained and its trace holds no text; the other
    reasons keep today's trace and opt-in retention.
    """

    land_scope = request.land_context.mode
    try:
        answer_trace.note_outcome(abstention_reason=reason)
        health_metrics.note_answer("abstained", reason)
        response = to_abstention_response(Abstention(reason=reason), land_scope=land_scope)
    finally:
        session.release()
    private = reason == "personal_data"
    session.finish(
        question=request.question, land_scope=land_scope, response=response, withhold_text=private
    )
    if not private:
        outcome = retain_if_opted_in(
            retention_store,
            opted_in=request.retain_for_improvement,
            question=request.question,
            land_context=request.land_context.model_dump(exclude_none=True),
            response=response,
            today=as_of,
        )
        if outcome in {"redaction_failed", "store_failed"}:
            operational_log("retention_skipped", outcome=outcome)
    if inspect:
        try:
            return dict(response, inspection=answer_inspection.build_inspection(session.collector))
        except answer_inspection.InspectionError as error:
            operational_log("answer_inspection_skipped", reason=error.code)
    return response


def _answer(
    request: AskRequest,
    corpus_documents: CorpusDocuments,
    as_of: date,
    active_campaign: str,
    retrieval_k: int,
    retrieval_backend: RetrievalBackend,
    generation: ProviderResolution | None = None,
) -> Dict[str, Any]:
    try:
        years = set(re.findall(r"(?<!\d)\d{4}(?!\d)", request.question))
        if len(years) > 1 or (years and years != {active_campaign}):
            answer_trace.note_outcome(abstention_reason="no_evidence")
            health_metrics.note_answer("abstained", "no_evidence")
            return to_abstention_response(Abstention(reason="no_evidence", issues=()), land_scope=request.land_context.mode)
        corpus = _prepare_runtime_corpus(corpus_documents, as_of, active_campaign)
    except (CatalogReadError, CatalogRejectedError, PassageSetError, RuntimeError, ValueError):
        raise _unavailable_corpus_error()

    if isinstance(corpus, Retriever):
        # BM25 unless hybrid retrieval is explicitly configured and its store is fresh
        # for this exact admitted corpus; the backend never raises.
        corpus = retrieval_backend.attach(corpus, active_campaign)
        answer_trace.note_mode(
            answer_trace_mode(corpus),
            retrieval_k,
        )

    land_context = request.land_context.model_dump(exclude_none=True)
    # ``None`` (the committed state) keeps the accepted extractive generator. A gated
    # Gemini generator verifies its own draft and falls back to extractive on any problem.
    generator = (
        generation.generator_for(land_context, max_claims=DEFAULT_MAX_CLAIMS)
        if generation is not None
        else None
    )
    result = answer_with_clarification(
        request.question,
        land_context,
        corpus,
        as_of=as_of,
        k=retrieval_k,
        max_claims=DEFAULT_MAX_CLAIMS,
        generator=generator,
    )
    if isinstance(result, NeedsLandClarification):
        health_metrics.note_answer("needs_land_clarification")
        return to_clarification_response(result)
    if isinstance(result, Abstention):
        answer_trace.note_outcome(
            abstention_reason=result.reason, generation_reason=result.generation_reason
        )
        health_metrics.note_answer("abstained", result.reason)
        return to_abstention_response(result, land_scope=request.land_context.mode)
    if isinstance(result, Answered):
        answer_trace.note_outcome(
            cited_passage_ids=[passage.passage_id for passage in result.sources]
        )
        health_metrics.note_answer("answered")
        return to_answer_response(result)
    raise _unavailable_corpus_error()


def answer_trace_mode(corpus: Retriever) -> str:
    """The effective ranking of this request: hybrid only when a ranker was attached."""

    return "hybrid" if corpus.uses_ranker else "bm25"


def _prepare_runtime_corpus(documents: CorpusDocuments, as_of: date, active_campaign: str) -> Retriever | Abstention:
    if documents.load_error:
        raise ValueError("corpus unavailable")
    catalog = documents.catalog
    if not isinstance(catalog, dict) or not isinstance(catalog.get("sources"), list):
        raise ValueError("invalid corpus")
    passages = documents.passages
    if not isinstance(passages, dict) or not isinstance(passages.get("passages"), list):
        raise ValueError("invalid corpus")
    # Validate the complete artifacts before campaign selection. In particular,
    # off-campaign metadata and dangling references must not be hidden by scope.
    catalog_report = validate_catalog(catalog, as_of)
    if not catalog_report.ok:
        expired_only = all(issue.location.endswith(".valid_until") and "expired and ineligible" in issue.rule for issue in catalog_report.issues)
        declared = catalog.get("sources", [])
        every_source_expired = bool(declared) and all(
            isinstance(source, dict) and isinstance(source.get("valid_until"), str)
            and source["valid_until"] < as_of.isoformat()
            for source in declared
        )
        if expired_only and every_source_expired:
            return prepare_corpus(catalog, passages, as_of, active_campaign)
        raise CatalogRejectedError(catalog_report.format_issues())
    passage_report = validate_passage_set(passages)
    if not passage_report.ok:
        raise PassageSetError(passage_report.format_issues())
    all_ids = {source.get("id") for source in catalog["sources"] if isinstance(source, dict)}
    if any(passage["source_id"] not in all_ids for passage in passages["passages"]):
        raise PassageSetError("passage source reference is invalid")
    source_ids = {source.get("id") for source in catalog["sources"] if isinstance(source, dict) and source.get("campaign") in (None, active_campaign)}
    if any(not isinstance(source, dict) for source in catalog["sources"]):
        raise ValueError("invalid corpus")
    filtered_catalog = dict(catalog, sources=[source for source in catalog["sources"] if source.get("id") in source_ids])
    filtered_passages = dict(passages, passages=[p for p in passages["passages"] if isinstance(p, dict) and p.get("source_id") in source_ids])
    return prepare_corpus(filtered_catalog, filtered_passages, as_of, active_campaign)


def _unavailable_corpus_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Answer service is temporarily unavailable.")


async def sanitize_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return contract statuses without reflecting rejected request values."""

    malformed_json = any(error.get("type") == "json_invalid" for error in exc.errors())
    status_code = 400 if malformed_json else 422
    detail = "Malformed JSON request." if malformed_json else "Request validation failed."
    return JSONResponse(status_code=status_code, content={"detail": detail})
