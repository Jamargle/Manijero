#!/usr/bin/env python3
"""Derive a review-only source-validity report from reviewed knowledge.

Reads the approved catalog, the reviewed passages, and one accepted change-impact
report, then writes a ``validity-review-v1`` artifact outside ``knowledge/``. It
never edits canonical knowledge, never retires a source itself, and never records
an approval: every retirement, review and addition stays for a human reviewer.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.source_validity import (  # noqa: E402
    ISO_DATE_PATTERN,
    SourceValidityError,
    check_validity,
    proposal_lines,
    result_line,
    write_report,
)

ABORT_LINE = "Result: the validity check did not run: {}. Nothing was written.\n"


def _failure(name: str) -> int:
    # Never echo exception text, local paths, or document values: they may carry
    # operator data. Only the fixed failure name leaves the process.
    sys.stderr.write(ABORT_LINE.format(name))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--impact-report", dest="impact_report", type=Path, required=True)
    parser.add_argument("--as-of", dest="as_of", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if not ISO_DATE_PATTERN.fullmatch(args.as_of):
        return _failure("invalid_as_of")
    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError:
        return _failure("invalid_as_of")

    try:
        report = check_validity(args.catalog, args.passages, args.impact_report, as_of)
        write_report(
            report,
            args.report,
            input_paths=(args.catalog, args.passages, args.impact_report),
        )
    except SourceValidityError as error:
        return _failure(error.failure)
    except Exception:  # pragma: no cover - defensive, mirrors the other CLIs
        return _failure("internal_error")

    for line in proposal_lines(report):
        print(line)
    print(result_line(report, args.report))
    return 1 if report["proposals"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
