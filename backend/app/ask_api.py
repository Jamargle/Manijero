"""HTTP boundary for the local, source-grounded ``POST /ask`` route."""

from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Annotated, Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StrictStr, model_validator

from app.abstention import (
    Abstention,
    prepare_corpus,
    to_abstention_response,
)
from app.clarification import (
    NeedsLandClarification,
    answer_with_clarification,
    to_clarification_response,
)
from app.generation import Answered, to_answer_response
from app.retrieval import CatalogRejectedError, PassageSetError, Retriever
from app.source_catalog import CatalogReadError, load_catalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "source_catalog.json"
PASSAGES_PATH = REPOSITORY_ROOT / "knowledge" / "passages.json"


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


class AnswerSource(ClosedModel):
    title: StrictStr = Field(min_length=1, max_length=300)
    issuing_body: StrictStr = Field(min_length=1, max_length=200)
    url: AnyHttpUrl
    location: StrictStr = Field(min_length=1, max_length=200)
    published_or_updated_on: date = Field(strict=False)
    verified_on: date = Field(strict=False)
    excerpt: StrictStr = Field(min_length=1, max_length=2000)


class AskResponse(ClosedModel):
    status: Literal["answered", "abstained", "needs_land_clarification"]
    answer: StrictStr = Field(max_length=1200)
    sources: list[AnswerSource]
    land_scope: Literal["general", "all_active", "selected"]
    land_ids_to_choose: list[Annotated[StrictStr, Field(min_length=1, max_length=128)]]


class CorpusDocuments(ClosedModel):
    catalog: Any
    passages: Any
    load_error: bool = False


def get_as_of_date() -> date:
    """Return today's UTC date for catalog expiry checks."""

    return datetime.now(timezone.utc).date()


def load_corpus_documents() -> CorpusDocuments:
    """Read canonical repository artifacts; failures are translated by the route."""

    try:
        catalog = load_catalog(CATALOG_PATH)
        passages = json.loads(PASSAGES_PATH.read_text(encoding="utf-8"))
    except (CatalogReadError, OSError, json.JSONDecodeError):
        return CorpusDocuments(catalog=None, passages=None, load_error=True)
    return CorpusDocuments(catalog=catalog, passages=passages)


def get_corpus_documents() -> CorpusDocuments:
    """FastAPI dependency seam for local files and fixture-backed route tests."""

    return load_corpus_documents()


router = APIRouter()


@router.post(
    "/ask",
    operation_id="askQuestion",
    summary="Ask for a source-grounded answer",
    response_model=AskResponse,
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
) -> Dict[str, Any]:
    """Run accepted corpus and answer decisions without exposing internal errors."""

    try:
        corpus = _prepare_runtime_corpus(corpus_documents, as_of)
    except (CatalogReadError, CatalogRejectedError, PassageSetError, RuntimeError, ValueError):
        raise _unavailable_corpus_error()

    result = answer_with_clarification(
        request.question,
        request.land_context.model_dump(exclude_none=True),
        corpus,
        as_of=as_of,
    )
    if isinstance(result, NeedsLandClarification):
        return to_clarification_response(result)
    if isinstance(result, Abstention):
        return to_abstention_response(result, land_scope=request.land_context.mode)
    if isinstance(result, Answered):
        return to_answer_response(result)
    raise _unavailable_corpus_error()


def _prepare_runtime_corpus(documents: CorpusDocuments, as_of: date) -> Retriever | Abstention:
    if documents.load_error:
        raise ValueError("corpus unavailable")
    catalog = documents.catalog
    if not isinstance(catalog, dict) or not isinstance(catalog.get("sources"), list):
        raise ValueError("invalid corpus")
    if any(isinstance(source, dict) and "campaign" in source for source in catalog["sources"]):
        raise ValueError("campaign filtering is not available")
    return prepare_corpus(catalog, documents.passages, as_of)


def _unavailable_corpus_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Answer service is temporarily unavailable.")


async def sanitize_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return contract statuses without reflecting rejected request values."""

    malformed_json = any(error.get("type") == "json_invalid" for error in exc.errors())
    status_code = 400 if malformed_json else 422
    detail = "Malformed JSON request." if malformed_json else "Request validation failed."
    return JSONResponse(status_code=status_code, content={"detail": detail})
