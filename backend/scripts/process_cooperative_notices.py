#!/usr/bin/env python3
"""Turn anonymized cooperative notices into review candidates with the local model.

Reads ``notice-NNN.txt`` files from ``--notices``, refuses any that look personal or
model-directed before a model call, asks the pinned local Ollama model for colloquial terms
and grower questions, and writes one unreviewed ``notice-review.json`` under ``--output``
(outside ``knowledge/``). ``--screen-only`` applies the input checks without a model and
writes nothing. Development profile only. Prints one JSON report of fixed codes.

Exit codes:

* ``0`` - every notice was extracted (or, with ``--screen-only``, is clean).
* ``1`` - at least one notice was refused or failed; the others were still processed.
* ``2`` - aborted before writing: unsafe or missing setup, or the local model is unavailable.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.notice_pipeline import ABORT_UNEXPECTED, NoticePipelineError, process_notices  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notices", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--screen-only", action="store_true")
    args = parser.parse_args(argv)
    if args.screen_only and args.output is not None:
        parser.error("--screen-only writes nothing and takes no --output")
    if not args.screen_only and args.output is None:
        parser.error("--output is required unless --screen-only is given")

    try:
        report = process_notices(args.notices, args.output, screen_only=args.screen_only)
    except NoticePipelineError as error:
        _fail(error.code)
        return 2
    except Exception:  # noqa: BLE001 - never echo text, paths, or a traceback
        _fail(ABORT_UNEXPECTED)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    summary = report["summary"]
    return 1 if summary["refused"] or summary["failed"] else 0


def _fail(code: str) -> None:
    print(json.dumps({"error": "NoticePipelineError", "code": code}), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
