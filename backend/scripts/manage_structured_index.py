#!/usr/bin/env python3
"""Build or check the derived structured-chunk index from reviewed chunk sets.

Developer command, offline: it reads local chunk sets (from ``chunk_legal_documents.py``)
and the reviewed catalog, and writes one derived index directory outside ``knowledge/``.
Nothing it writes is canonical knowledge. The answer service reads the index only when
``MANIJERO_STRUCTURED_INDEX=on`` in local development or QA.

Usage::

    backend/.venv/bin/python backend/scripts/manage_structured_index.py build \
      --chunks /path/to/chunks --catalog knowledge/source_catalog.json \
      --reviewed-baseline-revision <40-hex git revision> \
      --as-of 2026-11-07 --active-campaign 2026 --output /path/to/structured-index \
      [--embedding-artifact /path/to/bge-m3 [--embedding-config CONFIG]]

    backend/.venv/bin/python backend/scripts/manage_structured_index.py check \
      --index /path/to/structured-index --catalog knowledge/source_catalog.json

Approval evidence is exactly one of ``--reviewed-baseline-revision`` or
``--merge-record`` (which also needs ``--passages``, the canonical passages the merge
approved; they are hashed, never indexed).

Exit codes: ``0`` built, unchanged, or up to date; ``1`` the build was refused (malformed
or unreviewed input) or the index is stale or invalid; ``2`` usage error, unsafe root, a
missing input, a bound exceeded, or a vector-step failure. The last stdout line is always
one plain ``Result:`` line. Output carries fixed codes and counts only: never chunk text
and never a reviewer name.
"""
import argparse
import sys
from datetime import date
from pathlib import Path
from typing import NoReturn, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge_release import DEFAULT_EMBEDDING_CONFIG, sha256_bytes  # noqa: E402
from app.structured_chunk_index import (  # noqa: E402
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_USAGE,
    STATE_INVALID,
    STATE_STALE,
    STATE_UP_TO_DATE,
    StructuredIndexError,
    VectorOptions,
    build_index,
    index_status,
    verify_index,
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:  # keep the last stdout line a Result line
        print("Result: nothing was written; the command line is not valid (usage_error).")
        raise SystemExit(EXIT_USAGE)


def _as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--as-of must be YYYY-MM-DD") from error


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Build or check the structured-chunk index. Offline.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    build = commands.add_parser("build", help="rebuild the index from reviewed chunk sets")
    build.add_argument("--chunks", type=Path, required=True)
    build.add_argument("--catalog", type=Path, required=True)
    build.add_argument("--as-of", dest="as_of", type=_as_of, required=True)
    build.add_argument("--active-campaign", required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--merge-record", type=Path, default=None)
    build.add_argument("--passages", type=Path, default=None)
    build.add_argument("--reviewed-baseline-revision", default=None)
    build.add_argument("--embedding-artifact", type=Path, default=None)
    build.add_argument("--embedding-config", type=Path, default=None)

    check = commands.add_parser("check", help="report whether the index matches the catalog")
    check.add_argument("--index", type=Path, required=True)
    check.add_argument("--catalog", type=Path, required=True)
    return parser


def _refused(error: StructuredIndexError) -> int:
    if error.exit_code == EXIT_USAGE:
        print("Result: nothing was written; the build cannot start ({}).".format(error.code))
    else:
        print("Result: nothing was written; the build was refused ({}).".format(error.code))
    return error.exit_code


def command_build(args: argparse.Namespace) -> int:
    if args.embedding_config is not None and args.embedding_artifact is None:
        print("Result: nothing was written; --embedding-config needs --embedding-artifact (usage_error).")
        return EXIT_USAGE
    vectors = None
    if args.embedding_artifact is not None:
        vectors = VectorOptions(
            artifact=args.embedding_artifact,
            config=args.embedding_config or DEFAULT_EMBEDDING_CONFIG,
        )
    try:
        report = build_index(
            chunks_root=args.chunks,
            catalog_path=args.catalog,
            output_root=args.output,
            as_of=args.as_of,
            active_campaign=args.active_campaign,
            merge_record=args.merge_record,
            passages_path=args.passages,
            reviewed_baseline_revision=args.reviewed_baseline_revision,
            vectors=vectors,
        )
    except StructuredIndexError as error:
        return _refused(error)
    except Exception:
        # Never echo exception text or a traceback: both may contain chunk text or local paths.
        print("Result: nothing was written; the build failed unexpectedly (internal_error).")
        return EXIT_USAGE
    if report.status == "unchanged":
        print(
            "Result: the structured index is already up to date; nothing was rewritten "
            "({} chunks from {} documents).".format(report.chunks, report.documents)
        )
    else:
        print(
            "Result: built the structured index from {} chunks in {} documents.".format(
                report.chunks, report.documents
            )
        )
    return EXIT_OK


def command_check(args: argparse.Namespace) -> int:
    try:
        catalog_sha256 = sha256_bytes(Path(args.catalog).read_bytes())
    except OSError:
        print("Result: the catalog could not be read (missing_catalog).")
        return EXIT_USAGE
    state = index_status(args.index, catalog_sha256)
    if state == STATE_UP_TO_DATE:
        counts = verify_index(args.index).manifest["counts"]
        print(
            "Result: the structured index is up to date with the catalog "
            "({} chunks from {} documents).".format(counts["chunks"], counts["documents"])
        )
        return EXIT_OK
    if state == STATE_STALE:
        print("Result: the structured index is stale; the catalog changed, so rebuild it (stale).")
    else:
        print("Result: the structured index is missing or damaged; rebuild it ({}).".format(STATE_INVALID))
    return EXIT_REFUSED


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        return command_build(args)
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
