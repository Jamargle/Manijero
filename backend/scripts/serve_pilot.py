#!/usr/bin/env python3
"""Serve the hosted pilot API: no reload, loopback origin, validated configuration.

This is the production-shaped entry point. The development launcher
(``./scripts/init.sh --backend``) binds ``0.0.0.0`` and enables reload; neither is
appropriate for the pilot, so the pilot process never imports that path.

Before serving traffic the launcher:

1. loads the explicit configuration (profile, campaign, client credentials, body bound),
2. refuses anything but the ``pilot`` profile,
3. runs the same preflight the operator runs (campaign + reviewed corpus readiness),
4. refuses a non-loopback bind unless explicitly acknowledged, because the reviewed
   design is a Cloudflare Tunnel connector reaching ``127.0.0.1``,
5. starts Uvicorn with the access log off (the application writes the reviewed request
   line) and without reload.

Config, not secrets, is printed at startup. ``--preflight-only`` exits after the checks so
a service manager can run it as a precondition.

Exit codes: 0 success, 2 refused configuration/preflight.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.pilot_config import PilotConfigError, load_config  # noqa: E402
from app.pilot_logging import configure_operational_logging  # noqa: E402
from app.pilot_ops import run_preflight  # noqa: E402

PROFILE_REQUIRED = "pilot_profile_required"
PUBLIC_BIND_REFUSED = "public_bind_refused"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_WORKERS = 2
MAX_WORKERS = 8
DEFAULT_MAX_CONCURRENCY = 64
MAX_CONCURRENCY = 512


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--host", default=os.environ.get("MANIJERO_PILOT_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=_int_env("MANIJERO_PILOT_PORT", DEFAULT_PORT))
    parser.add_argument(
        "--workers", type=int, default=_int_env("MANIJERO_PILOT_WORKERS", DEFAULT_WORKERS)
    )
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except PilotConfigError as error:
        _fail(error.code)
        return 2
    if not config.pilot:
        _fail(PROFILE_REQUIRED)
        return 2

    report = run_preflight()
    if not report.ok:
        for problem in report.problems:
            _fail(problem)
        return 2
    if not _loopback(args.host) and os.environ.get("MANIJERO_PILOT_ALLOW_PUBLIC_BIND") != "1":
        _fail(PUBLIC_BIND_REFUSED)
        return 2
    if not 1 <= args.workers <= MAX_WORKERS:
        _fail("workers_invalid")
        return 2
    if not 1 <= args.port <= 65535:
        _fail("port_invalid")
        return 2
    concurrency = _int_env("MANIJERO_PILOT_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY)
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        _fail("concurrency_invalid")
        return 2

    _summary(config, args.host, args.port, args.workers, concurrency, report)
    if args.preflight_only:
        return 0

    configure_operational_logging()
    import uvicorn

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=False,
        access_log=False,
        server_header=False,
        limit_concurrency=concurrency,
        timeout_keep_alive=30,
        log_level="info",
    )
    return 0


def _summary(config, host: str, port: int, workers: int, concurrency: int, report) -> None:
    print("profile: pilot", flush=True)
    print(f"campaign: {config.active_campaign}", flush=True)
    print(f"configured_clients: {len(config.clients)}", flush=True)
    print(f"max_request_bytes: {config.max_request_bytes}", flush=True)
    print(f"bind: {host}:{port}", flush=True)
    print(f"workers: {workers}", flush=True)
    print(f"limit_concurrency: {concurrency}", flush=True)
    print("reload: disabled", flush=True)
    print("access_log: application-owned", flush=True)
    print(f"corpus_ready: {'yes' if report.readiness and report.readiness.ready else 'no'}", flush=True)


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return -1


def _fail(code: str) -> None:
    print(f"refused: {code}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
