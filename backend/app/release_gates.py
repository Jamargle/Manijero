"""Deterministic release gates for one knowledge-release candidate.

Imported lazily by :func:`app.knowledge_release.prepare_release` (and by ``verify`` for
the BM25 fingerprint) only; the answer service never imports this module.

Gates run in order and collect every failure code instead of stopping at the first:

1. **structural** — catalog and passage contracts at ``as_of``, resolvable passage
   sources, campaign/date readiness, and a valid, non-orphaned reviewed case set;
2. **BM25** — two independent fingerprints of the admitted documents must match;
3. **grounding + evaluation** — the reviewed cases run through the unchanged ``/ask``
   route with BM25 retrieval and extractive generation forced, whatever the shell
   environment says; every answered response must satisfy the API contract, cite at
   least one source, and map each source to exactly one candidate passage;
4. **regression** — against the currently published release: a tracked per-case
   boolean that goes true -> false for an unchanged case fails the gate. New, changed,
   and removed cases are reported, not gated. There is no numeric quality threshold.

Nothing here makes a network call, loads a model, or prints corpus text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.knowledge_release import ReleaseError, canonical_json, sha256_bytes

BM25_SCHEMA_VERSION = "knowledge-release-bm25-v1"
EVALUATION_SCHEMA_VERSION = "knowledge-release-evaluation-v1"
TRACKED_CASE_FIELDS = (
    "expected_state_match",
    "source_match",
    "passage_match",
    "critical_facts_match",
    "clarification_ids_match",
)
EVALUATION_STATEMENT = (
    "Report-only evaluation on the reviewed sample with BM25 retrieval and extractive "
    "generation. Not a legal-coverage or answer-quality claim."
)


@dataclass(frozen=True)
class GateOutcome:
    failures: Tuple[str, ...]
    bm25_document: Optional[Dict[str, Any]]
    bm25_document_count: int
    evaluation_document: Dict[str, Any]
    summary: Optional[Dict[str, int]]


# --- BM25 fingerprint ------------------------------------------------------------------


def bm25_fingerprint(catalog: Any, passages: Any, as_of: date, active_campaign: str) -> Dict[str, Any]:
    """Canonical record of the BM25 statistics the service would build in memory.

    The service does not load this record; it is the reproducibility evidence.
    """

    from app.retrieval import BM25_B, BM25_K1, Retriever, tokenize

    retriever = Retriever.from_documents(catalog, passages, as_of, active_campaign=active_campaign)
    documents: List[Dict[str, Any]] = []
    document_frequencies: Dict[str, int] = {}
    lengths: List[int] = []
    for passage_id, text in retriever.indexed_documents():
        tokens = tokenize(text)
        frequencies: Dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        for token in frequencies:
            document_frequencies[token] = document_frequencies.get(token, 0) + 1
        lengths.append(len(tokens))
        documents.append(
            {
                "id": passage_id,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
                "length": len(tokens),
                "term_frequencies": frequencies,
            }
        )
    average = (sum(lengths) / len(lengths)) if lengths else 0.0
    return {
        "schema_version": BM25_SCHEMA_VERSION,
        "k1": BM25_K1,
        "b": BM25_B,
        "document_count": len(documents),
        "documents": documents,
        "document_frequencies": document_frequencies,
        "average_length": repr(average),
    }


# --- Grounding ---------------------------------------------------------------------------


def check_grounding(
    case_ids: Sequence[str], bodies: Sequence[Any], catalog: Any, passages: Any
) -> List[Tuple[str, str]]:
    """Return ``(case_id, code)`` for every response that is not grounded in the candidate."""

    from app.ask_api import AskResponse

    problems: List[Tuple[str, str]] = []
    for case_id, body in zip(case_ids, bodies):
        try:
            response = AskResponse.model_validate(body).model_dump(mode="json")
        except Exception:
            problems.append((case_id, "grounding_invalid_response"))
            continue
        if response["status"] != "answered":
            continue
        if not response["sources"]:
            problems.append((case_id, "grounding_empty_sources"))
            continue
        for source in response["sources"]:
            if _mapped_passages(source, catalog, passages) != 1:
                problems.append((case_id, "grounding_unmapped_source"))
                break
    return problems


def _mapped_passages(source: Mapping[str, Any], catalog: Any, passages: Any) -> int:
    sources = [entry for entry in catalog["sources"] if entry.get("original_url") == str(source["url"])]
    if len(sources) != 1:
        return 0
    source_id = sources[0].get("id")
    return sum(
        1
        for passage in passages["passages"]
        if passage.get("source_id") == source_id
        and passage.get("location") == source["location"]
        and passage.get("text") == source["excerpt"]
    )


# --- Regression ----------------------------------------------------------------------------


def compare_to_baseline(
    case_digests: Mapping[str, str],
    case_rows: Sequence[Mapping[str, Any]],
    baseline: Optional[Mapping[str, Any]],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Per-case no-regression rule against the published release's evaluation report.

    Returns ``(failures, notes)``; ``notes`` lists regressed, changed, new, and removed
    case ids. Only regressions of unchanged cases fail.
    """

    notes: Dict[str, List[str]] = {"regressed_cases": [], "changed_cases": [], "new_cases": [], "removed_cases": []}
    if baseline is None:
        return [], notes
    try:
        old_digests = baseline["case_digests"]
        old_rows = {row["id"]: row for row in baseline["report"]["case_rows"]}
        if not isinstance(old_digests, dict):
            raise TypeError
    except (KeyError, TypeError):
        return ["baseline_unreadable"], notes
    rows = {row["id"]: row for row in case_rows}
    failures: List[str] = []
    for case_id in sorted(case_digests):
        if case_id not in old_digests:
            notes["new_cases"].append(case_id)
            continue
        if old_digests[case_id] != case_digests[case_id]:
            notes["changed_cases"].append(case_id)
            continue
        old_row = old_rows.get(case_id)
        new_row = rows.get(case_id)
        if not isinstance(old_row, dict) or new_row is None:
            continue
        if any(old_row.get(name) is True and new_row.get(name) is not True for name in TRACKED_CASE_FIELDS):
            notes["regressed_cases"].append(case_id)
            failures.append("evaluation_regression:{}".format(case_id))
    notes["removed_cases"] = sorted(set(old_digests) - set(case_digests))
    return failures, notes


# --- Gate runner ---------------------------------------------------------------------------


def run_gates(
    catalog_path: Path,
    passages_path: Path,
    cases_path: Path,
    *,
    as_of: date,
    active_campaign: str,
    retrieval_k: int,
    baseline_release_id: Optional[str],
    baseline_report: Optional[Mapping[str, Any]],
) -> GateOutcome:
    from app.answer_eval import AnswerEvalError, load_case_document
    from app.ask_api import CorpusDocuments
    from app.readiness import evaluate_readiness
    from app.retrieval import (
        CatalogRejectedError,
        PassageSetError,
        Retriever,
        load_passage_set,
        validate_passage_set,
    )
    from app.source_catalog import CatalogReadError, load_catalog, validate_catalog

    failures: set = set()
    catalog: Any = None
    passages: Any = None
    try:
        catalog = load_catalog(catalog_path)
        if not validate_catalog(catalog, as_of).ok:
            failures.add("catalog_invalid")
    except CatalogReadError:
        failures.add("catalog_invalid")
    try:
        passages = load_passage_set(passages_path)
        if not validate_passage_set(passages).ok:
            failures.add("passages_invalid")
    except PassageSetError:
        failures.add("passages_invalid")
    if _is_sectioned(catalog, "sources") and _is_sectioned(passages, "passages"):
        known = {source.get("id") for source in catalog["sources"] if isinstance(source, dict)}
        if any(isinstance(p, dict) and p.get("source_id") not in known for p in passages["passages"]):
            failures.add("passage_source_unresolved")
    if catalog is not None and passages is not None:
        verdict = evaluate_readiness(CorpusDocuments(catalog=catalog, passages=passages), as_of, active_campaign)
        if not verdict.ready:
            failures.add("corpus_not_ready:{}".format(verdict.problems[0]))

    retriever = None
    if not failures:
        try:
            retriever = Retriever.from_documents(catalog, passages, as_of, active_campaign=active_campaign)
        except (CatalogRejectedError, PassageSetError):
            failures.add("catalog_invalid")

    cases: Optional[List[Dict[str, Any]]] = None
    coverage: Optional[Dict[str, Any]] = None
    if retriever is not None:
        try:
            cases, coverage = load_case_document(cases_path, catalog, passages)
        except (AnswerEvalError, KeyError, TypeError, ValueError):
            failures.add("cases_invalid")
    if cases is not None and retriever is not None:
        admitted = {passage_id for passage_id, _ in retriever.indexed_documents()}
        admitted_sources = {
            passage["source_id"] for passage in passages["passages"] if passage["id"] in admitted
        }
        for case in cases:
            if not set(case.get("expected_passage_ids", [])) <= admitted or not set(
                case.get("expected_source_ids", [])
            ) <= admitted_sources:
                failures.add("cases_orphaned")

    bm25_document = None
    bm25_count = 0
    if retriever is not None:
        first = bm25_fingerprint(catalog, passages, as_of, active_campaign)
        second = bm25_fingerprint(catalog, passages, as_of, active_campaign)
        if canonical_json(first) != canonical_json(second):
            failures.add("bm25_nondeterministic")
        bm25_document = first
        bm25_count = first["document_count"]

    case_digests = {case["id"]: sha256_bytes(canonical_json(case)) for case in cases or []}
    report = None
    grounding: List[Tuple[str, str]] = []
    notes: Dict[str, List[str]] = {"regressed_cases": [], "changed_cases": [], "new_cases": [], "removed_cases": []}
    if failures or cases is None:
        failures.add("evaluation_failed")
    else:
        report, grounding, evaluation_failed = _evaluate(
            cases, coverage, catalog, passages, as_of, active_campaign, retrieval_k
        )
        failures.update(code for _, code in grounding)
        if evaluation_failed:
            failures.add("evaluation_failed")
        if report is not None:
            regression_failures, notes = compare_to_baseline(case_digests, report["case_rows"], baseline_report)
            failures.update(regression_failures)

    summary = None
    if report is not None:
        summary = {
            "cases": report["cases"],
            "expected_state_agreement": report["expected_state_agreement"],
            "unexpected_answers": report["unexpected_answers"],
        }
    evaluation_document = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "active_campaign": active_campaign,
        "retrieval": "bm25",
        "generation": "extractive",
        "retrieval_k": retrieval_k,
        "baseline_release_id": baseline_release_id,
        "case_digests": case_digests,
        "grounding_failures": [{"case_id": case_id, "code": code} for case_id, code in grounding],
        "regression": notes,
        "report": report,
        "statement": EVALUATION_STATEMENT,
    }
    return GateOutcome(
        failures=tuple(sorted(failures)),
        bm25_document=bm25_document,
        bm25_document_count=bm25_count,
        evaluation_document=evaluation_document,
        summary=summary,
    )


def _is_sectioned(document: Any, key: str) -> bool:
    return isinstance(document, dict) and isinstance(document.get(key), list)


class _CapturingClient:
    """Pass-through client that keeps every ``/ask`` response body for grounding."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.bodies: List[Any] = []

    def post(self, url: str, json: Any) -> Any:  # noqa: A002 - mirrors the TestClient API
        response = self._client.post(url, json=json)
        try:
            self.bodies.append(response.json() if response.status_code == 200 else None)
        except ValueError:
            self.bodies.append(None)
        return response


def evaluation_app(corpus: Any, as_of: date, active_campaign: str, retrieval_k: int) -> Any:
    """A minimal app around the unchanged ``/ask`` router with every knob pinned.

    Deliberately not :func:`app.main.create_app`: importing ``app.main`` builds the
    module-level app from the operator's environment (profile, retention, generation),
    and the gate must not depend on any of it. Retrieval is BM25, generation is
    extractive, retention is off.
    """

    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError

    from app import ask_api
    from app.retrieval_backend import Bm25Backend, get_retrieval_backend

    application = FastAPI()
    application.include_router(ask_api.router)
    application.add_exception_handler(RequestValidationError, ask_api.sanitize_request_validation)
    application.state.retention_store = None
    application.state.generation_provider = None
    application.dependency_overrides.update(
        {
            ask_api.get_corpus_documents: lambda: corpus,
            ask_api.get_as_of_date: lambda: as_of,
            ask_api.get_active_campaign: lambda: active_campaign,
            ask_api.get_retrieval_k: lambda: retrieval_k,
            ask_api.get_retention_store: lambda: None,
            ask_api.get_generation_provider: lambda: None,
            get_retrieval_backend: Bm25Backend,
        }
    )
    return application


def _evaluate(
    cases: List[Dict[str, Any]],
    coverage: Optional[Dict[str, Any]],
    catalog: Any,
    passages: Any,
    as_of: date,
    active_campaign: str,
    retrieval_k: int,
) -> Tuple[Optional[Dict[str, Any]], List[Tuple[str, str]], bool]:
    from fastapi.testclient import TestClient

    from app.answer_eval import AnswerEvalError, evaluate
    from app.ask_api import CorpusDocuments

    corpus = CorpusDocuments(catalog=catalog, passages=passages)
    client = _CapturingClient(TestClient(evaluation_app(corpus, as_of, active_campaign, retrieval_k)))
    report = None
    failed = False
    try:
        report = evaluate(cases, client, catalog, passages, retrieval_k, coverage=coverage)
    except AnswerEvalError:
        failed = True
    case_ids = [case["id"] for case in cases[: len(client.bodies)]]
    grounding = check_grounding(case_ids, client.bodies, catalog, passages)
    return report, grounding, failed


# --- Optional vector packaging ---------------------------------------------------------------


@dataclass(frozen=True)
class VectorPlan:
    spec: Any
    index_document: Dict[str, Any]
    index_bytes: bytes
    inputs: Any
    catalog: Any
    passages: Any
    as_of: date
    active_campaign: str


def plan_vector_packaging(
    index_path: Path,
    config_path: Path,
    catalog_bytes: bytes,
    passages_bytes: bytes,
    as_of: date,
    active_campaign: str,
) -> VectorPlan:
    """Check, before anything is written, that a pre-built index fits this candidate.

    The index must be ``up_to_date`` for the candidate bytes, ``as_of``, campaign, and
    model pin, and the optional ``chromadb`` runtime must be importable. No model is
    loaded and nothing is embedded here.
    """

    from app.embedding_index import IndexInputs, index_status, load_index
    from app.embeddings import EmbeddingError, load_model_spec

    try:
        spec = load_model_spec(config_path)
    except (EmbeddingError, OSError) as error:
        raise ReleaseError("embedding_config_invalid") from error
    inputs = IndexInputs(
        catalog_sha256=sha256_bytes(catalog_bytes),
        passages_sha256=sha256_bytes(passages_bytes),
        as_of=as_of.isoformat(),
        active_campaign=active_campaign,
    )
    state = index_status(index_path, spec, inputs)
    if state.state == "stale":
        raise ReleaseError("embedding_index_stale:{}".format(",".join(state.reasons)))
    if not state.up_to_date:
        raise ReleaseError("embedding_index_invalid")
    try:
        index_bytes = Path(index_path).read_bytes()
        document = json.loads(index_bytes.decode("utf-8"))
        load_index(document, spec)
    except (OSError, UnicodeDecodeError, ValueError, EmbeddingError) as error:
        raise ReleaseError("embedding_index_invalid") from error
    recorded = document["inputs"]
    if (
        recorded["catalog_sha256"] != inputs.catalog_sha256
        or recorded["passages_sha256"] != inputs.passages_sha256
        or recorded["as_of"] != inputs.as_of
        or recorded["active_campaign"] != inputs.active_campaign
    ):
        raise ReleaseError("embedding_index_invalid")
    try:
        import chromadb  # noqa: F401  (optional runtime; presence check only)
    except Exception as error:  # ImportError or a broken native extension
        raise ReleaseError("vector_runtime_unavailable") from error
    try:
        catalog = json.loads(catalog_bytes.decode("utf-8"))
        passages = json.loads(passages_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ReleaseError("embedding_index_invalid") from error
    return VectorPlan(spec, document, index_bytes, inputs, catalog, passages, as_of, active_campaign)


def package_vectors(plan: VectorPlan, store_dir: Path) -> Tuple[Dict[str, Any], bytes]:
    """Load the planned index into ``store_dir`` with the existing ``write_store``."""

    from app.embedding_index import load_index
    from app.embeddings import EmbeddingError
    from app.retrieval import Retriever
    from app.vector_store import MANIFEST_NAME, VectorStoreError, error_code, write_store

    retriever = Retriever.from_documents(plan.catalog, plan.passages, plan.as_of, active_campaign=plan.active_campaign)
    try:
        index = load_index(plan.index_document, plan.spec)
        manifest = write_store(
            store_dir,
            index,
            plan.spec,
            plan.inputs,
            retriever.indexed_documents(),
            sha256_bytes(plan.index_bytes),
        )
        store_manifest_bytes = (Path(store_dir) / MANIFEST_NAME).read_bytes()
    except VectorStoreError as error:
        raise ReleaseError(error_code(error)) from error
    except (EmbeddingError, OSError) as error:
        raise ReleaseError("store_write_failed") from error
    vector = {
        "model": plan.spec.index_metadata(),
        "embedding_index_sha256": sha256_bytes(plan.index_bytes),
        "store_manifest_sha256": sha256_bytes(store_manifest_bytes),
        "documents_sha256": manifest["inputs"]["documents_sha256"],
        "vectors_sha256": manifest["vectors_sha256"],
        "chromadb_version": manifest["chromadb_version"],
    }
    return vector, plan.index_bytes
