#!/usr/bin/env python3
"""Operator commands for the private hosted pilot service.

Run from the repository root with the backend virtualenv, for example:

    backend/.venv/bin/python backend/scripts/pilot_ops.py preflight

Commands cover the runbook's repeatable steps: preflight, corpus/config backup, verified
restore, a deployment smoke check, client-credential rotation, the privacy review gate,
and the owner's product-improvement retention operations (status, daily purge, export,
delete-all). Output contains fixed codes, counts, and hashes only, never a question,
answer, land value, or bearer token; only ``retention-export`` writes redacted retained
text, and only to an owner-only file outside the repository.

Exit codes: 0 success, 1 a check failed, 2 refused input or configuration.
"""
import argparse
import getpass
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pilot_config import parse_campaign, token_sha256  # noqa: E402
from app.privacy_review import (  # noqa: E402
    decide_generation_provider,
    evaluate_pilot_review,
    load_review_record,
)
from app.retention import (  # noqa: E402
    RetentionError,
    export_records,
    load_retention_store,
    today_utc,
)
from app.pilot_ops import (  # noqa: E402
    PilotOperationError,
    create_backup,
    remove_client,
    restore_backup,
    run_preflight,
    run_smoke,
    service_active_status,
    upsert_client,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight", help="validate configuration and corpus")
    preflight.add_argument("--as-of", type=date.fromisoformat, default=None)

    backup = commands.add_parser("backup", help="back up the reviewed corpus and config")
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--config", type=Path, action="append", default=[])
    backup.add_argument("--campaign", default=None)

    restore = commands.add_parser(
        "restore", help="restore a verified corpus backup with the service stopped"
    )
    restore.add_argument("--backup-dir", type=Path, required=True)
    restore.add_argument("--confirm", action="store_true")
    restore.add_argument("--as-of", type=date.fromisoformat, default=None)

    smoke = commands.add_parser("smoke", help="check a deployment's health and answer path")
    smoke.add_argument("--base-url", required=True)
    smoke.add_argument("--token-env", default=None)
    smoke.add_argument("--timeout", type=float, default=10.0)

    upsert = commands.add_parser("upsert-client", help="add or rotate one client credential")
    upsert.add_argument("--clients-file", type=Path, required=True)
    upsert.add_argument("--client-id", required=True)
    upsert.add_argument("--requests-per-minute", type=int, required=True)
    upsert.add_argument("--token-stdin", action="store_true")

    revoke = commands.add_parser("remove-client", help="revoke one client credential")
    revoke.add_argument("--clients-file", type=Path, required=True)
    revoke.add_argument("--client-id", required=True)

    commands.add_parser("hash-token", help="print the digest stored for a token from stdin")

    gate = commands.add_parser("privacy-gate", help="report the pilot and Gemini review gates")
    gate.add_argument("--as-of", type=date.fromisoformat, default=None)

    for name, help_text in (
        ("retention-status", "count retained records and report overdue ones"),
        ("retention-purge", "delete retained records at or past their expiry date"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--as-of", type=date.fromisoformat, default=None)

    export = commands.add_parser("retention-export", help="export unexpired redacted records")
    export.add_argument("--destination", type=Path, required=True)

    delete_all = commands.add_parser("retention-delete-all", help="delete every retained record")
    delete_all.add_argument("--confirm", action="store_true")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except PilotOperationError as error:
        print(f"error: {error.code}", file=sys.stderr)
        return error.exit_code
    except RetentionError as error:
        # A failed purge or export is an alert for the operator: exit 1, fixed code only.
        print(f"error: {error.code}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "preflight":
        return _preflight(args)
    if args.command == "backup":
        return _backup(args)
    if args.command == "restore":
        return _restore(args)
    if args.command == "smoke":
        return _smoke(args)
    if args.command == "upsert-client":
        token = _read_token(args)
        count = upsert_client(
            args.clients_file,
            client_id=args.client_id,
            token=token,
            requests_per_minute=args.requests_per_minute,
        )
        print(f"clients: {count}")
        return 0
    if args.command == "remove-client":
        count = remove_client(args.clients_file, client_id=args.client_id)
        print(f"clients: {count}")
        return 0
    if args.command == "hash-token":
        print(token_sha256(_read_token(argparse.Namespace(token_stdin=True))))
        return 0
    if args.command == "privacy-gate":
        return _privacy_gate(args)
    if args.command.startswith("retention-"):
        return _retention(args)
    raise PilotOperationError("unknown_command")


def _privacy_gate(args: argparse.Namespace) -> int:
    as_of = args.as_of or today_utc()
    record = load_review_record()
    review = evaluate_pilot_review(record, as_of=as_of)
    decision = decide_generation_provider(record=record, as_of=as_of)
    print(f"pilot_privacy_review: {'passed' if review.passed else 'blocked'}")
    print(f"generation_provider: {decision.provider}")
    print(f"gemini_configured: {'yes' if decision.gemini_configured else 'no'}")
    print("gemini_requests: disabled")
    for blocker in review.blockers:
        print(f"blocker: {blocker}", file=sys.stderr)
    if decision.gemini_configured:
        for blocker in decision.gemini_gate.blockers:
            print(f"gemini_blocker: {blocker}", file=sys.stderr)
    return 0 if review.passed else 1


def _retention(args: argparse.Namespace) -> int:
    store = load_retention_store()
    if store is None:
        print("retention: not_configured")
        return 0
    today = getattr(args, "as_of", None) or today_utc()
    if args.command == "retention-status":
        status = store.status(today=today)
        print(f"records: {status.records}")
        print(f"overdue: {status.overdue}")
        print(f"oldest_created_on: {status.oldest_created_on or 'none'}")
        if status.overdue:
            print("alert: retention_overdue", file=sys.stderr)
            return 1
        return 0
    if args.command == "retention-purge":
        print(f"purged: {store.purge_expired(today=today)}")
        return 0
    if args.command == "retention-export":
        print(f"exported: {export_records(store, args.destination, today=today)}")
        return 0
    if args.command == "retention-delete-all":
        if not args.confirm:
            raise PilotOperationError("confirmation_required")
        print(f"deleted: {store.delete_all()}")
        return 0
    raise PilotOperationError("unknown_command")


def _preflight(args: argparse.Namespace) -> int:
    report = run_preflight(as_of=args.as_of)
    print(f"profile: {report.profile}")
    print(f"campaign: {report.campaign or 'unknown'}")
    print(f"configured_clients: {report.configured_clients}")
    print(f"max_request_bytes: {report.max_request_bytes}")
    print(f"corpus_ready: {'yes' if report.readiness and report.readiness.ready else 'no'}")
    print(f"privacy_review: {'passed' if report.privacy_review_passed else 'blocked'}")
    print(f"retention: {'configured' if report.retention_configured else 'off'}")
    print(f"generation_provider: {report.generation_provider}")
    for problem in report.problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 0 if report.ok else 1


def _backup(args: argparse.Namespace) -> int:
    campaign = args.campaign or parse_campaign(os.environ.get("MANIJERO_ACTIVE_CAMPAIGN"))
    report = create_backup(args.destination, campaign=campaign, config_files=args.config)
    print(f"backup_dir: {report.directory}")
    print(f"campaign: {report.campaign or 'unknown'}")
    for role in report.roles:
        print(f"role: {role}")
    for name in report.config_files:
        print(f"config_file: {name}")
    return 0


def _restore(args: argparse.Namespace) -> int:
    if args.confirm:
        state = service_active_status()
        if state is True:
            raise PilotOperationError("service_running")
        if state is None:
            print(
                "warning: systemd was not queried; confirm manijero-pilot is stopped"
                " before restoring",
                file=sys.stderr,
            )
    report = restore_backup(args.backup_dir, confirm=args.confirm, as_of=args.as_of)
    print(f"restored: {','.join(report.roles)}")
    print(f"campaign: {report.campaign or 'unknown'}")
    print(f"corpus_ready: {'yes' if report.readiness.ready else 'no'}")
    for problem in report.readiness.problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 0 if report.readiness.ready else 1


def _smoke(args: argparse.Namespace) -> int:
    token = _token_from_env(args.token_env) if args.token_env else None
    report = run_smoke(args.base_url, token=token, timeout=args.timeout)
    print(f"health_status: {_status(report.health_status)}")
    print(f"ready_status: {_status(report.readiness_status)}")
    print(f"ask_status: {_status(report.ask_status_code)}")
    print(f"ask_state: {report.ask_state or 'unknown'}")
    for failure in report.failures:
        print(f"failure: {failure}", file=sys.stderr)
    return 0 if report.ok else 1


def _read_token(args: argparse.Namespace) -> str:
    if getattr(args, "token_stdin", False):
        token = sys.stdin.readline().strip()
    else:
        token = getpass.getpass("client token (not echoed): ").strip()
    if not token:
        raise PilotOperationError("token_missing")
    return token


def _token_from_env(name: str) -> str:
    token = os.environ.get(name, "").strip()
    if not token:
        raise PilotOperationError("token_missing")
    return token


def _status(value: int | None) -> str:
    return "none" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
