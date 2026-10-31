#!/usr/bin/env python3
"""Build, check, and evaluate the derived Chroma vector store for hybrid retrieval.

Operator entry point for the optional hybrid (BM25 + vector) ranking. It reads
local files only, never downloads a model, and never touches canonical
knowledge: ``build`` writes one derived store directory the operator named,
``check`` only reads it, and ``compare`` runs the reviewed ``/ask`` evaluation
cases once with BM25 and once with hybrid ranking in-process.

Usage::

    # 1. Build the passage-embedding index with the pinned model (see manage_embeddings.py).
    # 2. Load that index into a persistent Chroma store (needs chromadb, not torch).
    backend/.venv-hybrid/bin/python backend/scripts/manage_vector_store.py build \
      --config backend/config/bge_m3_embedding.json \
      --embedding-index /path/to/embedding-index.json \
      --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
      --as-of 2026-10-31 --active-campaign 2026 \
      --store /path/to/vector-store

    # 3. Report freshness (manifest only; add --deep to open and verify the collection).
    backend/.venv/bin/python backend/scripts/manage_vector_store.py check \
      --config backend/config/bge_m3_embedding.json \
      --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
      --as-of 2026-10-31 --active-campaign 2026 --store /path/to/vector-store

    # 4. Compare BM25 and hybrid on the reviewed evaluation cases (report only).
    backend/.venv-hybrid/bin/python backend/scripts/manage_vector_store.py compare \
      --config backend/config/bge_m3_embedding.json \
      --hybrid-config backend/config/hybrid_retrieval.json \
      --artifact /path/to/bge-m3 --store /path/to/vector-store \
      --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
      --cases knowledge/pac_answer_eval.json \
      --as-of 2026-10-31 --active-campaign 2026 --json

Exit codes: ``0`` success (store built, store up to date, comparison ran);
``1`` the store or source index is stale/missing/invalid, or hybrid fell back
during a comparison; ``2`` unreadable or invalid input, missing optional
runtime, refused path, or model/store load failure.

The comparison is a measurement on the reviewed sample only; it is not a
legal-coverage, answer-quality, or general-accuracy claim. No question text,
passage text, or land value is printed except the reviewed case ids.
"""

import argparse
import json
import resource
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.embedding_index import (  # noqa: E402  (path setup must run first)
    IndexInputs,
    file_sha256,
    index_status,
    load_index,
    read_index_document,
)
from app.embeddings import EmbeddingError, load_model_spec  # noqa: E402
from app.hybrid_retrieval import (  # noqa: E402
    HybridBackend,
    HybridConfigError,
    HybridRanker,
    describe_settings,
    load_hybrid_components,
)
from app.retrieval import (  # noqa: E402
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402
from app.vector_store import (  # noqa: E402
    STORE_UP_TO_DATE,
    ChromaPassageStore,
    VectorStoreError,
    error_code,
    store_status,
    write_store,
)

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_REFUSED = 2


def parse_as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--as-of must be YYYY-MM-DD") from error


def parse_campaign(value: str) -> str:
    if len(value) != 4 or not value.isdigit():
        raise argparse.ArgumentTypeError("--active-campaign must be a four-digit year")
    return value


def _corpus_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--as-of", dest="as_of", type=parse_as_of, required=True)
    parser.add_argument("--active-campaign", type=parse_campaign, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, check, or evaluate the derived Chroma store. Offline."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="load an up-to-date embedding index into Chroma")
    _corpus_arguments(build)
    build.add_argument("--embedding-index", type=Path, required=True)

    check = commands.add_parser("check", help="report store freshness")
    _corpus_arguments(check)
    check.add_argument("--deep", action="store_true", help="also open and verify the collection")

    compare = commands.add_parser("compare", help="BM25 vs hybrid on reviewed cases")
    _corpus_arguments(compare)
    compare.add_argument("--hybrid-config", type=Path, required=True)
    compare.add_argument("--artifact", type=Path, required=True)
    compare.add_argument("--cases", type=Path, required=True)
    compare.add_argument("--k", type=int, default=5)
    compare.add_argument("--threads", type=int, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            return command_build(args)
        if args.command == "check":
            return command_check(args)
        return command_compare(args)
    except (CatalogReadError, CatalogRejectedError, PassageSetError):
        print("error: invalid_corpus", file=sys.stderr)
        return EXIT_REFUSED
    except (EmbeddingError, HybridConfigError) as error:
        print("error: {}".format(error_code(error)), file=sys.stderr)
        return EXIT_REFUSED
    except OSError:
        print("error: file_unreadable", file=sys.stderr)
        return EXIT_REFUSED


def _retriever(args: argparse.Namespace) -> Retriever:
    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    return Retriever.from_documents(
        catalog, passages, args.as_of, active_campaign=args.active_campaign
    )


def _inputs(args: argparse.Namespace) -> IndexInputs:
    return IndexInputs(
        catalog_sha256=file_sha256(args.catalog),
        passages_sha256=file_sha256(args.passages),
        as_of=args.as_of.isoformat(),
        active_campaign=args.active_campaign,
    )


def command_build(args: argparse.Namespace) -> int:
    spec = load_model_spec(args.config)
    retriever = _retriever(args)
    inputs = _inputs(args)
    source_status = index_status(args.embedding_index, spec, inputs)
    if not source_status.up_to_date:
        _emit(
            {
                "command": "build",
                "embedding_index_state": source_status.state,
                "reasons": list(source_status.reasons),
            },
            args.json,
        )
        return EXIT_MISMATCH
    index = load_index(read_index_document(args.embedding_index), spec)
    started = time.perf_counter()
    manifest = write_store(
        args.store,
        index,
        spec,
        inputs,
        retriever.indexed_documents(),
        file_sha256(args.embedding_index),
    )
    seconds = time.perf_counter() - started
    _emit(
        {
            "command": "build",
            "store_path": str(args.store),
            "schema_version": manifest["schema_version"],
            "chromadb_version": manifest["chromadb_version"],
            "model_id": manifest["model"]["model_id"],
            "model_revision": manifest["model"]["model_revision"],
            "passage_count": manifest["inputs"]["passage_count"],
            "documents_sha256": manifest["inputs"]["documents_sha256"],
            "vectors_sha256": manifest["vectors_sha256"],
            "source_index_sha256": manifest["source_index_sha256"],
            "write_seconds": round(seconds, 3),
            "store_bytes": _directory_bytes(args.store),
            "peak_rss_mb": round(_peak_rss_bytes() / (1024 * 1024), 1),
        },
        args.json,
    )
    return EXIT_OK


def command_check(args: argparse.Namespace) -> int:
    spec = load_model_spec(args.config)
    retriever = _retriever(args)
    status = store_status(args.store, spec, args.active_campaign, retriever.indexed_documents())
    payload: Dict[str, Any] = {
        "command": "check",
        "store_path": str(args.store),
        "indexed_passages": retriever.indexed_passage_count,
        "state": status.state,
        "reasons": list(status.reasons),
    }
    if status.up_to_date and args.deep:
        try:
            ChromaPassageStore.open(args.store, spec)
            payload["collection"] = "verified"
        except VectorStoreError as error:
            payload["state"] = "invalid"
            payload["reasons"] = [error_code(error)]
    _emit(payload, args.json)
    return EXIT_OK if payload["state"] == STORE_UP_TO_DATE else EXIT_MISMATCH


def command_compare(args: argparse.Namespace) -> int:
    if args.k < 1 or args.k > 100:
        print("error: --k must be between 1 and 100", file=sys.stderr)
        return EXIT_REFUSED
    from fastapi.testclient import TestClient

    from app.answer_eval import AnswerEvalError, evaluate, load_case_document
    from app.ask_api import (
        CorpusDocuments,
        _prepare_runtime_corpus,
        get_active_campaign,
        get_as_of_date,
        get_corpus_documents,
        get_retrieval_k,
    )
    from app.main import app
    from app.retrieval_backend import Bm25Backend, get_retrieval_backend

    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    try:
        cases, coverage = load_case_document(args.cases, catalog, passages)
    except AnswerEvalError as error:
        print("error: {}".format(error), file=sys.stderr)
        return EXIT_REFUSED

    started = time.perf_counter()
    components = load_hybrid_components(
        args.config, args.artifact, args.store, args.hybrid_config, threads=args.threads
    )
    load_seconds = time.perf_counter() - started
    documents = CorpusDocuments(catalog=catalog, passages=passages)
    retriever = _prepare_runtime_corpus(documents, args.as_of, args.active_campaign)
    if not isinstance(retriever, Retriever):
        print("error: corpus_not_current", file=sys.stderr)
        return EXIT_REFUSED

    hybrid_backend = HybridBackend(lambda: components)
    status = hybrid_backend.status(retriever, args.active_campaign)
    if not status.up_to_date:
        _emit({"command": "compare", "store_state": status.state, "reasons": list(status.reasons)}, args.json)
        return EXIT_MISMATCH

    ranker = HybridRanker(components.embedder, components.store, components.settings)
    hybrid_retriever = retriever.with_ranker(ranker)
    retrieval_rows, fallbacks, latencies = _retrieval_rows(
        cases, retriever, hybrid_retriever, ranker, args.k
    )

    reports: Dict[str, Any] = {}
    try:
        app.dependency_overrides[get_corpus_documents] = lambda: documents
        app.dependency_overrides[get_as_of_date] = lambda: args.as_of
        app.dependency_overrides[get_active_campaign] = lambda: args.active_campaign
        app.dependency_overrides[get_retrieval_k] = lambda: args.k
        client = TestClient(app)
        for mode, backend in (("bm25", Bm25Backend()), ("hybrid", hybrid_backend)):
            app.dependency_overrides[get_retrieval_backend] = _provider(backend)
            reports[mode] = evaluate(cases, client, catalog, passages, args.k, coverage=coverage)
    finally:
        app.dependency_overrides.clear()

    payload = {
        "command": "compare",
        "quality_metrics_are_report_only": True,
        "independent_legal_review": False,
        "as_of": args.as_of.isoformat(),
        "active_campaign": args.active_campaign,
        "k": args.k,
        "cases": len(cases),
        "model_id": components.spec.model_id,
        "model_revision": components.spec.model_revision,
        "store": {
            "state": status.state,
            "passage_count": components.store.passage_count,
            "documents_sha256": components.store.manifest["inputs"]["documents_sha256"],
        },
        "fusion": dict(describe_settings(components.settings)),
        "hybrid_fallbacks": fallbacks,
        "load_seconds": round(load_seconds, 3),
        "search_latency_ms": latencies,
        "peak_rss_mb": round(_peak_rss_bytes() / (1024 * 1024), 1),
        "answer_metrics": {mode: _summary(report) for mode, report in reports.items()},
        "retrieval_metrics": _retrieval_summary(retrieval_rows),
        "changed_cases": _changed_cases(reports["bm25"], reports["hybrid"]),
        "retrieval_rows": retrieval_rows,
    }
    _emit(payload, args.json)
    return EXIT_OK if fallbacks == 0 else EXIT_MISMATCH


def _provider(value: Any) -> Any:
    # A parameterless closure: FastAPI would read a defaulted lambda argument as a
    # query parameter.
    return lambda: value


def _retrieval_rows(
    cases: List[Dict[str, Any]],
    bm25: Retriever,
    hybrid: Retriever,
    ranker: HybridRanker,
    k: int,
) -> Any:
    rows: List[Dict[str, Any]] = []
    fallbacks = 0
    timings: Dict[str, List[float]] = {"bm25": [], "hybrid": []}
    for case in cases:
        started = time.perf_counter()
        lexical = bm25.search(case["question"], k=k)
        timings["bm25"].append(time.perf_counter() - started)
        started = time.perf_counter()
        fused = hybrid.search(case["question"], k=k)
        timings["hybrid"].append(time.perf_counter() - started)
        if fused and not ranker.last_trace.used_vector:
            fallbacks += 1
        expected = list(case.get("expected_passage_ids", []))
        rows.append(
            {
                "id": case["id"],
                "expected_status": case["expected_status"],
                "expected_passage_ids": expected,
                "bm25_ids": [item.passage_id for item in lexical],
                "hybrid_ids": [item.passage_id for item in fused],
                "bm25_expected_rank": _first_rank(lexical, expected),
                "hybrid_expected_rank": _first_rank(fused, expected),
            }
        )
    latencies = {
        mode: {
            "median": round(_quantile(values, 0.5) * 1000, 2),
            "p95": round(_quantile(values, 0.95) * 1000, 2),
            "max": round(max(values) * 1000, 2),
        }
        for mode, values in timings.items()
        if values
    }
    return rows, fallbacks, latencies


def _first_rank(candidates: Sequence[Any], expected: Sequence[str]) -> Optional[int]:
    for candidate in candidates:
        if candidate.passage_id in expected:
            return candidate.rank
    return None


def _retrieval_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    answered = [row for row in rows if row["expected_passage_ids"]]
    summary: Dict[str, Any] = {"cases_with_expected_passage": len(answered)}
    for mode in ("bm25", "hybrid"):
        ranks = [row["{}_expected_rank".format(mode)] for row in answered]
        summary[mode] = {
            "expected_passage_at_1": sum(1 for rank in ranks if rank == 1),
            "expected_passage_in_top_k": sum(1 for rank in ranks if rank is not None),
            "mean_reciprocal_rank": round(
                sum(1.0 / rank for rank in ranks if rank) / len(ranks), 4
            )
            if ranks
            else None,
        }
    summary["non_answer_cases_with_candidates"] = {
        mode: sum(
            1
            for row in rows
            if not row["expected_passage_ids"] and row["{}_ids".format(mode)]
        )
        for mode in ("bm25", "hybrid")
    }
    return summary


def _summary(report: Dict[str, Any]) -> Dict[str, Any]:
    rows = report["case_rows"]
    return {
        "expected_state_agreement": report["expected_state_agreement"],
        "expected_answer_coverage": report["expected_answer_coverage"],
        "answered_cases": report["answered_cases"],
        "source_citation_agreement": report["source_citation_agreement"],
        "passage_citation_agreement": sum(
            row["passage_match"] for row in rows if row["expected_status"] == "answered"
        ),
        "critical_fact_matches": report["critical_fact_matches"],
        "abstention_cases": report["abstention_cases"],
        "expected_abstentions": sum(
            1
            for row in rows
            if row["expected_status"] == "abstained" and row["actual_status"] == "abstained"
        ),
        "unexpected_answers": report["unexpected_answers"],
        "clarification_outcomes": report["clarification_outcomes"],
    }


def _changed_cases(bm25: Dict[str, Any], hybrid: Dict[str, Any]) -> List[Dict[str, Any]]:
    changed: List[Dict[str, Any]] = []
    for left, right in zip(bm25["case_rows"], hybrid["case_rows"]):
        keys = ("actual_status", "actual_passage_ids", "passage_match", "critical_facts_match")
        if any(left[key] != right[key] for key in keys):
            changed.append(
                {
                    "id": left["id"],
                    "bm25": {key: left[key] for key in keys},
                    "hybrid": {key: right[key] for key in keys},
                }
            )
    return changed


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())


def _quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _peak_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage if sys.platform == "darwin" else usage * 1024


def _emit(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print("{}: {}".format(key, value))


if __name__ == "__main__":
    raise SystemExit(main())
