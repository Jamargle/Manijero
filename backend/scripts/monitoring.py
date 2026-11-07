#!/usr/bin/env python3
"""Start, check, and stop the owner's health dashboard. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --monitoring-start    # run Prometheus and Grafana in Docker Desktop, print the address
    ./scripts/init.sh --monitoring-status   # is it running, can the page answer
    ./scripts/init.sh --monitoring-stop     # stop and remove them (the history is kept)

Every run prints plain sentences and ends with one ``Result:`` line. An unexpected error prints
one sentence and the path of a log file under ``<local home>/logs/``. Exit codes: ``0`` done or
running, ``1`` stopped, failed, or not running, ``2`` misuse. ``MANIJERO_LOCAL_HOME``,
``MANIJERO_QA_HOME``, ``MANIJERO_DOCKER_CLI``, ``MANIJERO_LOCAL_RAG_PORT``, and
``MANIJERO_MONITORING_PORT`` exist for tests (and, for the ports, developers) only.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import local_container as container  # noqa: E402  (path setup must run first)
from app import local_monitoring as monitoring  # noqa: E402
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as service  # noqa: E402

COMMANDS = ("start", "status", "stop")

# command -> (the Ctrl+C sentence, its result line, the failure result line)
WORDING = {
    "start": (
        "The start was stopped before the health dashboard was started.",
        monitoring.START_FAILED,
        monitoring.START_FAILED,
    ),
    "status": (
        "The check was stopped. Nothing was changed.",
        "Result: the check was stopped.",
        "Result: the health dashboard could not be checked.",
    ),
    "stop": (
        "The stop was interrupted. Run {} again to finish it.".format(monitoring.STOP_COMMAND),
        "Result: the stop was interrupted.",
        "Result: the health dashboard could not be stopped.",
    ),
}


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports() -> monitoring.MonitoringPorts:
    ctx = monitoring.default_context()
    return monitoring.MonitoringPorts(
        docker=container.SystemDockerCli(ctx.repo_root),
        probe=monitoring.GrafanaProbe(),
        clock=service.SystemServiceClock(),
        out=_say,
    )


def main(
    argv: Optional[Sequence[str]] = None,
    ctx: Optional[monitoring.MonitoringContext] = None,
    ports: Optional[monitoring.MonitoringPorts] = None,
) -> int:
    parser = argparse.ArgumentParser(description="Start, check, or stop the health dashboard.")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")

    try:
        port = monitoring.port_from_environment(os.environ)
        local_port = service.port_from_environment(os.environ)
    except service.UsageError as misuse:
        print(misuse.message, file=sys.stderr, flush=True)
        return 2
    context = ctx or monitoring.default_context(local_port)
    active = ports or build_ports()
    out = active.out
    interrupted, interrupted_result, failed_result = WORDING[args.command]
    log = bootstrap.RunLog(context.logs, args.command, active.clock.now)
    try:
        if args.command == "start":
            return monitoring.run_start(context, active, port)
        if args.command == "status":
            return monitoring.run_status(context, active, port)
        return monitoring.run_stop(context, active)
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
