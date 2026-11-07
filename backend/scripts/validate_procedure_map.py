#!/usr/bin/env python3
"""Validate the reviewed olive-grove procedure map without network access.

Usage::

    python3 backend/scripts/validate_procedure_map.py knowledge/procedure_map.json \
        --catalog knowledge/source_catalog.json \
        --passages knowledge/passages.json --report

Exit codes:

* ``0`` — the map is valid. Coverage gaps are reported but never fail the run.
* ``1`` — the map violates the policy; diagnostics are written to stderr.
* ``2`` — the map or one of the supplied reference files could not be read.

``--catalog`` and ``--passages`` are optional but must be supplied together:
together they enable the cross-file reference checks. This tool reads local JSON
only. It does not fetch documents and never claims that the map is legal
knowledge, an answer source, or a coverage gate.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.procedure_map import (
    ProcedureMapReadError,
    load_catalog_ids,
    load_passage_sources,
    load_procedure_map,
    validate_procedure_map,
)

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_UNREADABLE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a local olive-grove procedure map: seed set, review "
            "honesty, human-readable wording, and coverage declarations. "
            "No network access."
        )
    )
    parser.add_argument("map", type=Path, help="path to procedure_map.json")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="path to source_catalog.json for cross-file reference checks",
    )
    parser.add_argument(
        "--passages",
        type=Path,
        default=None,
        help="path to passages.json for cross-file reference checks",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print one coverage line per topic",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.catalog is None) != (args.passages is None):
        parser.error("--catalog and --passages must be supplied together")

    try:
        document = load_procedure_map(args.map)
        catalog_ids = load_catalog_ids(args.catalog) if args.catalog is not None else None
        passage_sources = (
            load_passage_sources(args.passages) if args.passages is not None else None
        )
    except ProcedureMapReadError as error:
        print("error: {}".format(error), file=sys.stderr)
        return EXIT_UNREADABLE

    report = validate_procedure_map(document, catalog_ids, passage_sources)
    if not report.ok:
        print("invalid procedure map: {}".format(args.map), file=sys.stderr)
        for issue in report.issues:
            print("  {}".format(issue), file=sys.stderr)
        print(
            "{} problem(s) found; the map was not accepted".format(len(report.issues)),
            file=sys.stderr,
        )
        return EXIT_INVALID

    print(
        "valid procedure map: {} (schema {}, {} topics: {} proposed, {} reviewed)".format(
            args.map,
            report.schema_version,
            report.checked_topics,
            report.coverage.proposed,
            report.coverage.reviewed,
        )
    )
    print(report.coverage.summary_line())
    if args.report:
        for line in report.coverage.format_lines():
            print(line)
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
