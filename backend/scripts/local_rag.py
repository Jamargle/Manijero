#!/usr/bin/env python3
"""Set up, check, start, and stop the local answer tools. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --local-rag-setup           # guided setup: checks, shows sizes, asks, downloads, builds
    ./scripts/init.sh --local-rag-status          # read-only: six plain lines and one result line
    ./scripts/init.sh --local-rag-start           # start the local answer service in the background
    ./scripts/init.sh --local-rag-service-status  # is it running, can it answer, which addresses
    ./scripts/init.sh --local-rag-stop            # stop it

Every run prints plain sentences and ends with one ``Result:`` line. An unexpected error
prints one sentence and the path of a log file under ``<local home>/logs/``; the traceback
is only in that file. Exit codes: ``0`` done, all parts OK, or running and OK; ``1``
stopped, cancelled, failed, or not all OK; ``2`` misuse.

``MANIJERO_LOCAL_HOME``, ``MANIJERO_OLLAMA_CLI``, and ``MANIJERO_LOCAL_RAG_PORT`` exist for
tests (and, for the port, developers) only.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import local_rag_bootstrap as bootstrap  # noqa: E402  (path setup must run first)
from app import local_rag_service as service  # noqa: E402
from app.pinned_download import https_opener  # noqa: E402

SERVICE_COMMANDS = ("start", "stop", "service-status")

# command -> (the Ctrl+C sentence, its result line, the failure result line)
SERVICE_WORDING = {
    "start": (
        "The start was stopped before the local answer service was started.",
        service.START_FAILED,
        service.START_FAILED,
    ),
    "stop": (
        "The stop was interrupted. Run {} again to finish it.".format(service.STOP_COMMAND),
        "Result: the stop was interrupted.",
        "Result: the local answer service could not be stopped.",
    ),
    "service-status": (
        "The check was stopped. Nothing was changed.",
        "Result: the check was stopped.",
        "Result: the local answer service could not be checked.",
    ),
}


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


def build_service_ports(ctx: bootstrap.Context) -> service.ServicePorts:
    tools = bootstrap.Ports(
        ollama=bootstrap.OllamaClient(),
        checkout=bootstrap.GitCheckout(ctx.repo_root, ctx.knowledge_dir),
        runner=bootstrap.LoggedRunner(ctx.repo_root),
        prompter=bootstrap.TerminalPrompter(),
        disk=bootstrap.LocalDisk(),
        clock=bootstrap.SystemClock(),
        opener=None,  # the service commands never download anything
        out=_say,
    )
    return service.ServicePorts(
        tools=tools,
        processes=service.SystemProcesses(),
        probe=service.LoopbackProbe(),
        clock=service.SystemServiceClock(),
    )


def main(
    argv: Optional[Sequence[str]] = None,
    ctx: Optional[bootstrap.Context] = None,
    ports: Optional[bootstrap.Ports] = None,
    service_ports: Optional[service.ServicePorts] = None,
) -> int:
    parser = argparse.ArgumentParser(description="Set up, check, start, or stop the local answer tools.")
    parser.add_argument("command", choices=("setup", "status") + SERVICE_COMMANDS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")

    context = ctx or bootstrap.default_context(sys.executable)
    if args.command in SERVICE_COMMANDS:
        return _run_service_command(args.command, context, service_ports)

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


def _run_service_command(
    command: str, context: bootstrap.Context, service_ports: Optional[service.ServicePorts]
) -> int:
    try:
        port = service.port_from_environment(os.environ)
    except service.UsageError as misuse:
        print(misuse.message, file=sys.stderr, flush=True)
        return 2
    active = service_ports or build_service_ports(context)
    out = active.out
    interrupted, interrupted_result, failed_result = SERVICE_WORDING[command]
    log = bootstrap.RunLog(context.paths.logs, command, active.clock.now)
    try:
        if command == "start":
            return service.run_start(context, active, port)
        if command == "stop":
            return service.run_stop(context, active)
        return service.run_service_status(context, active)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} Do the step shown above.".format(failed_result))
        return 1
    except KeyboardInterrupt:
        out("")
        out(interrupted)
        out(interrupted_result)
        return 1
    except Exception:  # noqa: BLE001 - every unexpected failure becomes one sentence plus a log
        path = log.write_traceback()
        out(
            "Something unexpected went wrong. Run the same command again; if it happens again, send "
            "this log file to a developer: {}".format(path)
        )
        out(failed_result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
