#!/usr/bin/env python3
"""Parse quarantined official PDFs into review Markdown with provenance.

Reads the accepted ``official-ingestion-state-v1`` quarantine, writes one
Markdown file plus one provenance manifest per PDF candidate under an
operator-owned output root outside ``knowledge/``, and never makes a candidate
answerable. ``--check-runtime`` prints one plain-language line per optional
capability and exits 0.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.legal_document_parser import (  # noqa: E402
    detect_runtime,
    parse_documents,
    runtime_lines,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--quarantine", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check-runtime",
        action="store_true",
        help="Print one line per optional capability and exit without parsing anything.",
    )
    args = parser.parse_args(argv)

    if args.check_runtime:
        if args.state is not None or args.quarantine is not None or args.output is not None:
            parser.error("--check-runtime takes no other argument")
        for line in runtime_lines(detect_runtime()):
            print(line)
        return 0

    missing = [
        flag
        for flag, value in (
            ("--state", args.state),
            ("--quarantine", args.quarantine),
            ("--output", args.output),
        )
        if value is None
    ]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))

    try:
        report = parse_documents(args.state, args.quarantine, args.output)
    except Exception as error:
        # Never echo exception text or a traceback: both may contain document
        # text, local paths, or other operator data.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
