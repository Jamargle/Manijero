#!/usr/bin/env python3
"""Validate the reviewed source catalog without network access.

Usage::

    python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12

Exit codes:

* ``0`` — the catalog is valid and conforms to the admission policy.
* ``1`` — the catalog violates the policy; diagnostics are written to stderr.
* ``2`` — the catalog file could not be read or parsed as JSON.

``--as-of`` makes expiry checks deterministic and should always be supplied by
automation. When it is omitted the current UTC date is used. This tool reads
local metadata only: it does not fetch documents, follow redirects, or claim
that a source is authentic, current, or legally applicable.
"""

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.source_catalog import CatalogReadError, load_catalog, validate_catalog

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_UNREADABLE = 2


def parse_as_of(value: str) -> date:
    """Parse an ``--as-of`` argument as YYYY-MM-DD."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--as-of must be a real calendar date formatted as YYYY-MM-DD"
        ) from error


def current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a local source catalog against the approved-provenance, "
            "metadata, review, and lifecycle policy. No network access."
        )
    )
    parser.add_argument("catalog", type=Path, help="path to source_catalog.json")
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=parse_as_of,
        default=None,
        metavar="YYYY-MM-DD",
        help="validation date used for expiry checks (defaults to the current UTC date)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    as_of = args.as_of or current_utc_date()

    try:
        document = load_catalog(args.catalog)
    except CatalogReadError as error:
        print("error: {}: {}".format(args.catalog, error), file=sys.stderr)
        return EXIT_UNREADABLE

    report = validate_catalog(document, as_of=as_of)
    if not report.ok:
        print("invalid source catalog: {}".format(args.catalog), file=sys.stderr)
        for issue in report.issues:
            print("  {}".format(issue), file=sys.stderr)
        print(
            "{} problem(s) found; the catalog was not accepted".format(len(report.issues)),
            file=sys.stderr,
        )
        return EXIT_INVALID

    print(
        "valid source catalog: {} (schema {}, {} source(s) checked as of {})".format(
            args.catalog,
            report.schema_version,
            report.checked_sources,
            as_of.isoformat(),
        )
    )
    return EXIT_VALID


if __name__ == "__main__":
    sys.exit(main())
