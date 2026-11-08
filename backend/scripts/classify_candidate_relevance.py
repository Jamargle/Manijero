#!/usr/bin/env python3
"""Suggest a relevance label and topic for discovered official publications.

Reads an ``official-discovery-state-v1`` file and the procedure map, asks the pinned
local model (loopback only) about each pending candidate, and writes a
``relevance-review-v1`` list outside ``knowledge/``. Suggestions only: it never drops,
admits, or changes a candidate, and a person decides what happens next.
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.gemini_generation import SystemClock  # noqa: E402
from app.local_generation import DEFAULT_RECORD_PATH, OllamaTransport  # noqa: E402
from app.relevance_classifier import (  # noqa: E402
    ClassificationAbort,
    build_response_format,
    classify,
    load_model_record,
    load_topics,
    result_line,
)

ABORT_LINE = "Result: the relevance classification did not run: {}. Nothing was written.\n"


def _failure(name: str) -> int:
    # Only the fixed failure name leaves the process: never paths, titles, or model text.
    sys.stderr.write(ABORT_LINE.format(name))
    return 2


def _default_transport(procedure_map: Path, clock: Any, record_path: Path) -> Any:
    record = load_model_record(record_path, clock)
    try:
        topics = load_topics(Path(procedure_map).read_bytes())
    except OSError as error:
        raise ClassificationAbort("invalid_procedure_map") from error
    return OllamaTransport(record, response_format=build_response_format(topics))


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    transport: Any = None,
    clock: Any = None,
    record_path: Optional[Path] = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-state", dest="discovery_state", type=Path, required=True)
    parser.add_argument("--procedure-map", dest="procedure_map", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    clock = clock or SystemClock()
    record_path = record_path or DEFAULT_RECORD_PATH
    try:
        if transport is None:
            transport = _default_transport(args.procedure_map, clock, record_path)
        document = classify(
            discovery_state=args.discovery_state,
            procedure_map=args.procedure_map,
            report=args.report,
            transport=transport,
            clock=clock,
            record_path=record_path,
        )
    except ClassificationAbort as error:
        return _failure(error.failure)
    except Exception:  # pragma: no cover - defensive, mirrors the other CLIs
        return _failure("internal_error")
    print(result_line(document, args.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
