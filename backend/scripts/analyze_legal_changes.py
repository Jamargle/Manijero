#!/usr/bin/env python3
"""Analyze quarantined official-document changes against approved knowledge.

Reads the document-ingestion state and quarantine plus the approved catalog,
passages, and (optionally) answer-evaluation cases, and writes one deterministic
impact report. It never changes canonical knowledge, never retires a source, and
never records an approval: every affected candidate stays for human review.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.change_impact import (  # noqa: E402
    ImpactAnalysisError,
    analyze,
    exit_code,
    write_report,
)


def _failure(name: str) -> int:
    # Never echo exception text, local paths, or document values: they may carry
    # operator data. Only the fixed error name leaves the process.
    print(json.dumps({"error": name}), file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingestion-state", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--as-of", dest="as_of", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError:
        return _failure("invalid_as_of")

    try:
        report = analyze(
            args.ingestion_state,
            args.quarantine,
            args.catalog,
            args.passages,
            cases_path=args.cases,
            as_of=as_of,
        )
        write_report(report, args.report)
    except ImpactAnalysisError as error:
        return _failure(error.failure)
    except Exception as error:  # pragma: no cover - defensive, mirrors ingestion
        return _failure(type(error).__name__)

    print(
        json.dumps(
            {
                "analyzer": report["analyzer"],
                "as_of": report["as_of"],
                "report": str(args.report),
                "summary": report["summary"],
                "review_required": [
                    candidate["candidate_id"]
                    for candidate in report["candidates"]
                    if candidate["review"]["required"]
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
