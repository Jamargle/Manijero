#!/usr/bin/env python3
"""Verify, measure, and rebuild the pinned local embedding artifact.

This is the operator entry point for the optional multilingual embedding
capability. It reads local files only, never downloads a model, and never
touches canonical knowledge: ``build`` writes one derived index file that the
operator named, and ``check`` only reads it.

Usage::

    # 1. Confirm the local artifact matches the pinned revision and checksums.
    backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py verify \
      --config backend/config/bge_m3_embedding.json \
      --artifact /path/to/bge-m3

    # 2. Optionally measure this host (load time, latency, peak RSS, determinism).
    backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py verify \
      --config backend/config/bge_m3_embedding.json \
      --artifact /path/to/bge-m3 --measure --json

    # 3. Embed the eligible reviewed passages into a derived index.
    backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py build \
      --config backend/config/bge_m3_embedding.json \
      --artifact /path/to/bge-m3 \
      --catalog knowledge/source_catalog.json \
      --passages knowledge/passages.json \
      --as-of 2026-10-27 --active-campaign 2026 \
      --index /path/to/embedding-index.json

    # 4. Report whether that index still matches the pin and the corpus.
    backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py check \
      --config backend/config/bge_m3_embedding.json \
      --catalog knowledge/source_catalog.json \
      --passages knowledge/passages.json \
      --as-of 2026-10-27 --active-campaign 2026 \
      --index /path/to/embedding-index.json

Exit codes:

* ``0`` — the requested operation succeeded (artifact verified, index built, or
  index up to date);
* ``1`` — the artifact does not match the pin, or the index is stale/invalid;
* ``2`` — a file was unreadable or invalid, the optional runtime is missing, the
  model failed to load, or the index path was refused.

The measurement output is a host observation, not a retrieval-quality claim.
No embedded text, question, or personal value is printed or stored.
"""

import argparse
import json
import resource
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.embedding_index import (  # noqa: E402  (path setup must run first)
    INDEX_UP_TO_DATE,
    IndexInputs,
    build_index_document,
    build_passage_index,
    file_sha256,
    index_status,
    write_index_atomic,
)
from app.embeddings import (  # noqa: E402
    EmbeddingArtifactError,
    EmbeddingConfigError,
    EmbeddingError,
    LocalBgeM3Embedder,
    load_model_spec,
    verify_artifact,
)
from app.retrieval import (  # noqa: E402
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_REFUSED = 2

MEASUREMENT_TEXTS: Tuple[str, ...] = (
    "La solicitud se presenta una vez al año.",
    "El plazo indicado aparece en el documento oficial.",
)
MEASUREMENT_REPETITIONS = 3


def parse_as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--as-of must be a real calendar date formatted as YYYY-MM-DD"
        ) from error


def parse_campaign(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if len(value) != 4 or not value.isdigit():
        raise argparse.ArgumentTypeError("--active-campaign must be a four-digit year")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a pinned local bge-m3 artifact, build its derived passage index, "
            "or check that index against the current corpus. Offline; never downloads."
        )
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    verify_parser = subcommands.add_parser("verify", help="verify the local artifact")
    verify_parser.add_argument("--config", type=Path, required=True)
    verify_parser.add_argument("--artifact", type=Path, required=True)
    verify_parser.add_argument(
        "--measure",
        action="store_true",
        help="load the model and measure load time, latency, peak RSS, determinism",
    )
    verify_parser.add_argument("--threads", type=int, default=None)
    verify_parser.add_argument("--json", action="store_true")

    build = subcommands.add_parser("build", help="build a derived passage embedding index")
    build.add_argument("--config", type=Path, required=True)
    build.add_argument("--artifact", type=Path, required=True)
    build.add_argument("--catalog", type=Path, required=True)
    build.add_argument("--passages", type=Path, required=True)
    build.add_argument("--as-of", dest="as_of", type=parse_as_of, required=True)
    build.add_argument("--active-campaign", type=parse_campaign, default=None)
    build.add_argument("--index", type=Path, required=True)
    build.add_argument("--threads", type=int, default=None)
    build.add_argument("--json", action="store_true")

    check = subcommands.add_parser("check", help="check index freshness without the model")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--catalog", type=Path, required=True)
    check.add_argument("--passages", type=Path, required=True)
    check.add_argument("--as-of", dest="as_of", type=parse_as_of, required=True)
    check.add_argument("--active-campaign", type=parse_campaign, default=None)
    check.add_argument("--index", type=Path, required=True)
    check.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            return command_verify(args)
        if args.command == "build":
            return command_build(args)
        return command_check(args)
    except (CatalogReadError, CatalogRejectedError, PassageSetError):
        print("error: invalid_corpus", file=sys.stderr)
        return EXIT_REFUSED
    except EmbeddingConfigError as error:
        print("error: {}".format(_code(error)), file=sys.stderr)
        return EXIT_REFUSED
    except EmbeddingArtifactError as error:
        print("error: {}".format(_error_lines(error)), file=sys.stderr)
        return EXIT_MISMATCH
    except EmbeddingError as error:
        print("error: {}".format(_error_lines(error)), file=sys.stderr)
        return EXIT_REFUSED
    except OSError:
        print("error: file_unreadable", file=sys.stderr)
        return EXIT_REFUSED


def command_verify(args: argparse.Namespace) -> int:
    spec = load_model_spec(args.config)
    report = verify_artifact(args.artifact, spec)
    payload: Dict[str, Any] = {
        "command": "verify",
        "model_id": spec.model_id,
        "model_revision": spec.model_revision,
        "license": spec.license,
        "config_sha256": spec.config_sha256,
        "artifact": {
            "checked_files": report.checked_files,
            "verified_bytes": report.verified_bytes,
            "ignored_files": report.ignored_files,
            "ignored_bytes": report.ignored_bytes,
            "issues": [str(issue) for issue in report.issues],
        },
    }
    if not report.ok:
        _emit(payload, args.json)
        return EXIT_MISMATCH
    if args.measure:
        payload["measurement"] = measure(spec, args.artifact, args.threads, report.verified_bytes)
    _emit(payload, args.json)
    return EXIT_OK


def measure(
    spec: Any, artifact: Path, threads: Optional[int], verified_bytes: int
) -> Dict[str, Any]:
    """Load the pinned model once and report host observations for this run."""

    started = time.perf_counter()
    embedder = LocalBgeM3Embedder.load(spec, artifact, threads=threads)
    load_seconds = time.perf_counter() - started

    embedder.embed(list(MEASUREMENT_TEXTS))  # warm-up, excluded from latency
    durations: List[float] = []
    first: Optional[Tuple[Tuple[float, ...], ...]] = None
    last: Optional[Tuple[Tuple[float, ...], ...]] = None
    for _ in range(MEASUREMENT_REPETITIONS):
        run_started = time.perf_counter()
        vectors = embedder.embed(list(MEASUREMENT_TEXTS))
        durations.append(time.perf_counter() - run_started)
        if first is None:
            first = vectors
        last = vectors

    max_abs_diff = 0.0
    if first is not None and last is not None and len(first) == len(last):
        for left, right in zip(first, last):
            for left_value, right_value in zip(left, right):
                max_abs_diff = max(max_abs_diff, abs(left_value - right_value))

    return {
        "device": "cpu",
        "threads": embedder.thread_count,
        "dtype": spec.dtype,
        "dimension": embedder.dimension,
        "pooling": spec.pooling,
        "normalized": embedder.normalized,
        "max_tokens": spec.max_tokens,
        "texts_per_run": len(MEASUREMENT_TEXTS),
        "repetitions": MEASUREMENT_REPETITIONS,
        "load_seconds": round(load_seconds, 3),
        "embed_seconds": [round(duration, 4) for duration in durations],
        "median_ms": round(_quantile(durations, 0.5) * 1000, 2),
        "p95_ms": round(_quantile(durations, 0.95) * 1000, 2),
        "min_ms": round(min(durations) * 1000, 2),
        "max_ms": round(max(durations) * 1000, 2),
        "peak_rss_mb": round(_peak_rss_bytes() / (1024 * 1024), 1),
        "determinism_max_abs_diff": max_abs_diff,
        "verified_bytes": verified_bytes,
    }


def command_build(args: argparse.Namespace) -> int:
    spec = load_model_spec(args.config)
    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    retriever = Retriever.from_documents(
        catalog, passages, args.as_of, active_campaign=args.active_campaign
    )
    inputs = index_inputs(args.catalog, args.passages, args.as_of, args.active_campaign)
    embedder = LocalBgeM3Embedder.load(spec, args.artifact, threads=args.threads)
    started = time.perf_counter()
    index = build_passage_index(retriever, embedder)
    embed_seconds = time.perf_counter() - started
    document = build_index_document(index, spec, inputs)
    write_index_atomic(args.index, document, spec)
    payload = {
        "command": "build",
        "model_id": spec.model_id,
        "model_revision": spec.model_revision,
        "config_sha256": spec.config_sha256,
        "indexed_passages": index.passage_count,
        "eligible_source_count": retriever.eligible_source_count,
        "excluded_passage_count": retriever.excluded_passage_count,
        "dimension": index.dimension,
        "embed_seconds": round(embed_seconds, 3),
        "peak_rss_mb": round(_peak_rss_bytes() / (1024 * 1024), 1),
        "index_path": str(args.index),
        "index_sha256": file_sha256(args.index),
        "inputs": inputs.to_document(index.passage_count),
    }
    _emit(payload, args.json)
    return EXIT_OK


def command_check(args: argparse.Namespace) -> int:
    spec = load_model_spec(args.config)
    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    # Reuse the accepted gates so a check never reports "up to date" for a corpus
    # that could not be indexed in the first place.
    retriever = Retriever.from_documents(
        catalog, passages, args.as_of, active_campaign=args.active_campaign
    )
    inputs = index_inputs(args.catalog, args.passages, args.as_of, args.active_campaign)
    status = index_status(args.index, spec, inputs)
    payload = {
        "command": "check",
        "model_id": spec.model_id,
        "model_revision": spec.model_revision,
        "config_sha256": spec.config_sha256,
        "indexed_passages": retriever.indexed_passage_count,
        "index_path": str(args.index),
        "state": status.state,
        "reasons": list(status.reasons),
    }
    _emit(payload, args.json)
    if status.state == INDEX_UP_TO_DATE:
        return EXIT_OK
    return EXIT_MISMATCH


def index_inputs(
    catalog: Path, passages: Path, as_of: date, active_campaign: Optional[str]
) -> IndexInputs:
    return IndexInputs(
        catalog_sha256=file_sha256(catalog),
        passages_sha256=file_sha256(passages),
        as_of=as_of.isoformat(),
        active_campaign=active_campaign,
    )


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
    # macOS reports bytes; Linux reports kibibytes.
    return usage if sys.platform == "darwin" else usage * 1024


def _error_lines(error: EmbeddingError) -> str:
    return str(error)


def _code(error: EmbeddingError) -> str:
    text = str(error)
    return text.split(":", 1)[0] if text else "embedding_error"


def _emit(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        if isinstance(value, dict):
            print("{}:".format(key))
            for nested_key, nested_value in value.items():
                print("  {}: {}".format(nested_key, nested_value))
        elif isinstance(value, list):
            print("{}: {}".format(key, ", ".join(str(item) for item in value)))
        else:
            print("{}: {}".format(key, value))
    if payload.get("state") == INDEX_UP_TO_DATE:
        print("Index matches the pinned model and the current corpus.")
    elif payload.get("state"):
        print("Index is not current; rebuild it with 'build' before use.")


if __name__ == "__main__":
    raise SystemExit(main())
