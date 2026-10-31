#!/usr/bin/env python3
"""Prepare, publish, roll back, and check immutable knowledge releases. Offline.

Operator entry point for the reindex-and-release step after an approved knowledge
merge. Every command reads and writes local files only; nothing is downloaded, no
model is loaded, and no corpus text, question, or land value is printed.

Usage::

    # 1. Build and gate a candidate (writes <root>/releases/<id>/, manifest last).
    backend/.venv/bin/python backend/scripts/knowledge_release.py prepare \
      --root /srv/manijero/knowledge-releases \
      --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
      --cases knowledge/pac_answer_eval.json \
      --active-campaign 2026 --as-of 2026-10-31 \
      --code-revision "$(git rev-parse HEAD)" \
      --merge-record /path/to/package/merge.json   # or --reviewed-baseline-revision <sha>

    # 2. Atomically switch the service to it, or back.
    ... knowledge_release.py publish --root ROOT --release-id <id> --active-campaign 2026
    ... knowledge_release.py rollback --root ROOT --active-campaign 2026 [--to <id>]

    # 3. Inspect.
    ... knowledge_release.py status --root ROOT
    ... knowledge_release.py verify --root ROOT [--release-id <id>]
    ... knowledge_release.py compare --a ROOT_A/releases/<id> --b ROOT_B/releases/<id>

Exit codes: ``0`` success; ``1`` gate failed, not ready, no current/previous release,
integrity or BM25 mismatch on ``verify``/``status``, or ``compare`` found differences;
``2`` refused or invalid input (approval evidence, gate_failed target, tampered target,
lock held, unsafe root, stale embedding index, missing optional runtime).
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import knowledge_release as kr  # noqa: E402  (path setup must run first)


def parse_as_of(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--as-of must be YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("--as-of must be YYYY-MM-DD")
    return parsed


def parse_campaign(value: str) -> str:
    if len(value) != 4 or not value.isdigit():
        raise argparse.ArgumentTypeError("--active-campaign must be a four-digit year")
    return value


def _today() -> date:
    return datetime.now(timezone.utc).date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage immutable knowledge releases. Offline.")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="build and gate a release candidate")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--catalog", type=Path, required=True)
    prepare.add_argument("--passages", type=Path, required=True)
    prepare.add_argument("--cases", type=Path, required=True)
    prepare.add_argument("--as-of", dest="as_of", type=parse_as_of, required=True)
    prepare.add_argument("--active-campaign", type=parse_campaign, required=True)
    prepare.add_argument("--code-revision", required=True)
    prepare.add_argument("--merge-record", type=Path)
    prepare.add_argument("--reviewed-baseline-revision")
    prepare.add_argument("--embedding-index", type=Path)
    prepare.add_argument("--with-vector-store", action="store_true")
    prepare.add_argument("--embedding-config", type=Path, default=kr.DEFAULT_EMBEDDING_CONFIG)

    for name, help_text in (("publish", "make a passed release current"), ("rollback", "return to the previous release")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--as-of", dest="as_of", type=parse_as_of, default=None)
        command.add_argument("--active-campaign", type=parse_campaign, required=True)
        if name == "publish":
            command.add_argument("--release-id", required=True)
        else:
            command.add_argument("--to", default=None)

    status = commands.add_parser("status", help="report the current release")
    status.add_argument("--root", type=Path, required=True)

    verify = commands.add_parser("verify", help="re-check hashes and the BM25 fingerprint")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--release-id", default=None)

    compare = commands.add_parser("compare", help="report differing manifest fields")
    compare.add_argument("--a", type=Path, required=True)
    compare.add_argument("--b", type=Path, required=True)

    for command in commands.choices.values():
        command.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None, clock=None) -> int:
    args = build_parser().parse_args(argv)
    # Keep stderr free of third-party deprecation noise; errors are fixed codes.
    warnings.simplefilter("ignore")
    try:
        if args.command == "prepare":
            return command_prepare(args)
        if args.command in ("publish", "rollback"):
            return command_switch(args, clock)
        if args.command == "status":
            return command_status(args)
        if args.command == "verify":
            return command_verify(args)
        return command_compare(args)
    except kr.ReleaseError as error:
        lines: List[Tuple[str, Any]] = [("command", args.command), ("error", error.code)]
        if error.release_id:
            lines.append(("release_id", error.release_id))
        _emit(lines, getattr(args, "json", False), stream=sys.stderr)
        return error.exit_code
    except OSError:
        _emit([("command", args.command), ("error", "file_unreadable")], getattr(args, "json", False), stream=sys.stderr)
        return kr.EXIT_REFUSED


def command_prepare(args: argparse.Namespace) -> int:
    result = kr.prepare_release(
        root=args.root,
        catalog=args.catalog,
        passages=args.passages,
        cases=args.cases,
        as_of=args.as_of,
        active_campaign=args.active_campaign,
        code_revision=args.code_revision,
        merge_record=args.merge_record,
        reviewed_baseline_revision=args.reviewed_baseline_revision,
        embedding_index=args.embedding_index,
        with_vector_store=args.with_vector_store,
        embedding_config=args.embedding_config,
    )
    manifest = result.manifest
    lines: List[Tuple[str, Any]] = [
        ("release_id", result.release_id),
        ("gate", "passed" if result.passed else "failed"),
        ("failures", ",".join(result.failures) or "none"),
        ("baseline_release_id", result.baseline_release_id or "none"),
        ("already_prepared", "yes" if result.already_prepared else "no"),
        ("bm25_index_sha256", manifest["bm25"]["index_sha256"] if manifest["bm25"] else "none"),
        ("vector", "packaged" if manifest["vector"] else "none"),
    ]
    for name in sorted(manifest["files"]):
        entry = manifest["files"][name]
        lines.append(("file", "{} {} {}".format(name, entry["sha256"], entry["bytes"])))
    _emit(lines, args.json)
    return kr.EXIT_OK if result.passed else kr.EXIT_FAILED


def command_switch(args: argparse.Namespace, clock) -> int:
    as_of = args.as_of or _today()
    extra: Dict[str, Any] = {} if clock is None else {"clock": clock}
    if args.command == "publish":
        result = kr.publish(args.root, args.release_id, as_of, args.active_campaign, **extra)
    else:
        result = kr.rollback(args.root, as_of, args.active_campaign, to=args.to, **extra)
    _emit(
        [
            ("command", args.command),
            ("release_id", result.release_id),
            ("previous_release_id", result.previous_release_id or "none"),
            ("result", "already_current" if result.already_current else "switched"),
        ],
        args.json,
    )
    return kr.EXIT_OK


def command_status(args: argparse.Namespace) -> int:
    report = kr.status(args.root)
    gate = "none" if report.gate_passed is None else ("passed" if report.gate_passed else "failed")
    _emit(
        [
            ("current_release_id", report.current_release_id or "none"),
            ("gate", gate),
            ("integrity", report.integrity),
            ("log", "in_sync" if report.log_in_sync else "log_out_of_sync"),
        ],
        args.json,
    )
    healthy = report.current_release_id is not None and report.integrity == "ok" and report.gate_passed
    return kr.EXIT_OK if healthy and report.log_in_sync else kr.EXIT_FAILED


def command_verify(args: argparse.Namespace) -> int:
    try:
        manifest = kr.verify(args.root, args.release_id)
    except kr.ReleaseError as error:
        if error.code in ("integrity_mismatch", "manifest_invalid"):
            raise kr.ReleaseError(error.code, kr.EXIT_FAILED, release_id=error.release_id) from error
        raise
    _emit(
        [
            ("release_id", manifest["release_id"]),
            ("integrity", "ok"),
            ("bm25", "match" if manifest["bm25"] else "none"),
            ("gate", "passed" if manifest["gate"]["passed"] else "failed"),
        ],
        args.json,
    )
    return kr.EXIT_OK if manifest["gate"]["passed"] else kr.EXIT_FAILED


def command_compare(args: argparse.Namespace) -> int:
    differences = kr.compare_releases(args.a, args.b)
    lines: List[Tuple[str, Any]] = [("identical", "no" if differences else "yes")]
    lines.extend(differences)
    _emit(lines, args.json)
    return kr.EXIT_FAILED if differences else kr.EXIT_OK


def _emit(lines: List[Tuple[str, Any]], as_json: bool, stream=None) -> None:
    out = stream or sys.stdout
    if as_json:
        document: Dict[str, Any] = {}
        for key, value in lines:
            if key in document:
                existing = document[key]
                document[key] = (existing if isinstance(existing, list) else [existing]) + [value]
            else:
                document[key] = value
        print(json.dumps(document, ensure_ascii=False, sort_keys=True), file=out)
        return
    for key, value in lines:
        print("{}: {}".format(key, value), file=out)


if __name__ == "__main__":
    raise SystemExit(main())
