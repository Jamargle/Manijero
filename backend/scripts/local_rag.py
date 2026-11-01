#!/usr/bin/env python3
"""Set up, or check, every local RAG artifact. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --local-rag-setup    # guided setup: checks, shows sizes, asks, downloads, builds
    ./scripts/init.sh --local-rag-status   # read-only: six plain lines and one result line

Every run prints plain sentences and ends with one ``Result:`` line. An unexpected error
prints one sentence and the path of a log file under ``<local home>/logs/``; the traceback
is only in that file. Exit codes: ``0`` done or all parts OK; ``1`` stopped, cancelled,
failed, or not all OK; ``2`` misuse.

``MANIJERO_LOCAL_HOME`` and ``MANIJERO_OLLAMA_CLI`` exist for tests only.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import local_rag_bootstrap as bootstrap  # noqa: E402  (path setup must run first)
from app.pinned_download import https_opener  # noqa: E402


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports(ctx: bootstrap.Context) -> bootstrap.Ports:
    return bootstrap.Ports(
        ollama=bootstrap.OllamaClient(),
        checkout=bootstrap.GitCheckout(ctx.repo_root, ctx.knowledge_dir),
        runner=bootstrap.LoggedRunner(ctx.repo_root),
        prompter=bootstrap.TerminalPrompter(),
        disk=bootstrap.LocalDisk(),
        clock=bootstrap.SystemClock(),
        opener=https_opener(),
        out=_say,
    )


def main(
    argv: Optional[Sequence[str]] = None,
    ctx: Optional[bootstrap.Context] = None,
    ports: Optional[bootstrap.Ports] = None,
) -> int:
    parser = argparse.ArgumentParser(description="Set up or check the local answer tools.")
    parser.add_argument("command", choices=("setup", "status"))
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")

    context = ctx or bootstrap.default_context(sys.executable)
    active_ports = ports or build_ports(context)
    out = active_ports.out
    log = bootstrap.RunLog(context.paths.logs, args.command, active_ports.clock.now)
    command = "setup" if args.command == "setup" else "status check"
    try:
        if args.command == "setup":
            return bootstrap.run_setup(context, active_ports, log)
        return bootstrap.run_status(context, active_ports)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: {} stopped before changing anything.".format(command))
        return 1
    except KeyboardInterrupt:
        out("")
        if args.command == "setup":
            out("Setup was stopped. Finished parts are kept; run {} again to continue.".format(bootstrap.SETUP_COMMAND))
            out("Result: setup stopped; finished parts are kept.")
        else:
            out("The status check was stopped. Nothing was changed.")
            out("Result: status check stopped.")
        return 1
    except Exception:  # noqa: BLE001 - every unexpected failure becomes one sentence plus a log
        path = log.write_traceback()
        out(
            "Something unexpected went wrong. Run the same command again; if it happens again, send "
            "this log file to a developer: {}".format(path)
        )
        out("Result: {} failed; finished parts are kept.".format(command))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
