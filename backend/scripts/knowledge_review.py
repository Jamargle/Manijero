#!/usr/bin/env python3
"""Prepare, decide, and merge one human-reviewed knowledge update.

Subcommands:

``prepare``  Build a deterministic draft review package (manifest plus draft
             pull-request body) from quarantined candidates and a reviewed
             proposal. It never writes canonical knowledge.
``decide``   Record one reviewer decision (approve / request_changes / reject).
             A named human other than the package author is required; a bot,
             label, CI status, or hash is never approval.
``merge``    Controlled merge: write the approved proposal into the canonical
             catalog and passage set, and only while the recorded approval and
             every required check still hold. When the package recorded a
             reviewed case-set digest, the same case file must be supplied and
             still validate the after-state. It never reindexes or releases.

Run it from the repository root. See `backend/README.md` for the full procedure
and the artifact lifecycle.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.review_package import (  # noqa: E402
    ReviewPackageError,
    exit_code,
    merge,
    prepare,
    record_decision,
)


def _failure(name: str) -> int:
    # Never echo exception text, local paths, or document values: they may carry
    # operator data. Only the fixed error name leaves the process.
    print(json.dumps({"error": name}), file=sys.stderr)
    return 2


def _parse_date(value: str, failure: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ReviewPackageError(failure) from error


def _prepare(args: argparse.Namespace) -> int:
    try:
        as_of = _parse_date(args.as_of, "invalid_as_of")
        result = prepare(
            args.ingestion_state,
            args.quarantine,
            args.catalog,
            args.passages,
            args.proposal,
            args.reviewer,
            as_of,
            args.workspace,
            cases_path=args.cases,
        )
    except ReviewPackageError as error:
        return _failure(error.failure)
    except Exception as error:  # pragma: no cover - defensive, mirrors ingestion
        return _failure(type(error).__name__)

    package = result["package"]
    print(
        json.dumps(
            {
                "package_id": package["package_id"],
                "package_dir": str(result["package_dir"]),
                "prepared_on": package["prepared_on"],
                "merge_readiness": package["merge_readiness"],
                "check_summary": package["check_summary"],
                "blocking_reasons": package["blocking_reasons"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return exit_code(package)


def _decide(args: argparse.Namespace) -> int:
    try:
        decided_on = _parse_date(args.decided_on, "invalid_decision_date")
        decisions = record_decision(
            args.package_dir,
            args.reviewer,
            args.decision,
            decided_on,
            note=args.note,
        )
    except ReviewPackageError as error:
        return _failure(error.failure)
    except Exception as error:  # pragma: no cover - defensive
        return _failure(type(error).__name__)
    print(
        json.dumps(
            {
                "package_id": decisions["package_id"],
                "effective_decision": decisions["effective_decision"],
                "approved_by": decisions["approved_by"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def _merge(args: argparse.Namespace) -> int:
    try:
        record = merge(
            args.package_dir,
            args.catalog,
            args.passages,
            cases_path=args.cases,
        )
    except ReviewPackageError as error:
        return _failure(error.failure)
    except Exception as error:  # pragma: no cover - defensive
        return _failure(type(error).__name__)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subcommands.add_parser("prepare", help="prepare a draft review package")
    prepare_parser.add_argument("--ingestion-state", type=Path, required=True)
    prepare_parser.add_argument("--quarantine", type=Path, required=True)
    prepare_parser.add_argument("--catalog", type=Path, required=True)
    prepare_parser.add_argument("--passages", type=Path, required=True)
    prepare_parser.add_argument("--proposal", type=Path, required=True)
    prepare_parser.add_argument("--cases", type=Path, default=None)
    prepare_parser.add_argument("--as-of", dest="as_of", required=True)
    prepare_parser.add_argument(
        "--reviewer", action="append", default=[], help="named human reviewer to request"
    )
    prepare_parser.add_argument("--workspace", type=Path, required=True)
    prepare_parser.set_defaults(handler=_prepare)

    decide_parser = subcommands.add_parser("decide", help="record a reviewer decision")
    decide_parser.add_argument("--package-dir", type=Path, required=True)
    decide_parser.add_argument("--reviewer", required=True)
    decide_parser.add_argument(
        "--decision", required=True, choices=("approve", "request_changes", "reject")
    )
    decide_parser.add_argument("--decided-on", dest="decided_on", required=True)
    decide_parser.add_argument("--note", default="")
    decide_parser.set_defaults(handler=_decide)

    merge_parser = subcommands.add_parser("merge", help="controlled merge of an approved package")
    merge_parser.add_argument("--package-dir", type=Path, required=True)
    merge_parser.add_argument("--catalog", type=Path, required=True)
    merge_parser.add_argument("--passages", type=Path, required=True)
    merge_parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="reviewed evaluation cases bound into the package; required when it recorded a digest",
    )
    merge_parser.set_defaults(handler=_merge)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
