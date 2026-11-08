#!/usr/bin/env python3
"""Telegram alerts for the QA answer service. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --qa-alerts-setup    # store the Telegram bot token and find the chat (one time)
    ./scripts/init.sh --qa-alerts-start    # turn the 5-minute check on (launchd)
    ./scripts/init.sh --qa-alerts-stop     # turn it off
    ./scripts/init.sh --qa-alerts-status   # is it on, and what did the last check find
    ./scripts/init.sh --qa-alerts-test     # send one test message

``check`` is what launchd runs every 5 minutes; it is not an owner command. Owner commands print plain
sentences and end with one ``Result:`` line. Exit codes: ``0`` done, ``1`` stopped or failed, ``2``
misuse. ``MANIJERO_ALERTS_HOME``, ``MANIJERO_QA_HOME``, ``MANIJERO_LAUNCHCTL_CLI``,
``MANIJERO_LAUNCH_AGENTS_DIR``, ``MANIJERO_DOCKER_CLI``, ``MANIJERO_TAILSCALE_CLI``,
``MANIJERO_QA_PORT``, and ``MANIJERO_TELEGRAM_API`` exist for tests only.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import environment_profiles as profiles  # noqa: E402  (path setup must run first)
from app import local_container as container  # noqa: E402
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as service  # noqa: E402
from app import qa_alerts as alerts  # noqa: E402
from app import qa_deployment as qa  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# operation -> (the Ctrl+C sentence, its result line, the failure result line)
WORDING = {
    "setup": ("Setup was stopped. Nothing was stored.", alerts.NOT_SET_UP, alerts.NOT_SET_UP),
    "start": ("The start was stopped.", alerts.NOT_ON, alerts.NOT_ON),
    "stop": (
        "The stop was interrupted. Run {} again to finish it.".format(alerts.STOP_COMMAND),
        "Result: QA alerts could not be turned off.",
        "Result: QA alerts could not be turned off.",
    ),
    "status": ("The check was stopped. Nothing was changed.", "Result: the check was stopped.", "Result: QA alerts could not be checked."),
    "test": ("The test was stopped.", alerts.NOT_SENT, alerts.NOT_SENT),
    "check": ("", "", ""),
}


class _Prompter:
    def ask(self, question: str) -> Optional[str]:
        try:
            return input(question)
        except EOFError:
            return None

    def ask_secret(self, question: str) -> Optional[str]:
        try:
            return getpass.getpass(question)
        except EOFError:
            return None


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports() -> alerts.AlertPorts:
    environment = os.environ
    uid = os.getuid()
    configured = environment.get(alerts.AGENTS_DIR_ENV, "").strip()
    return alerts.AlertPorts(
        home=alerts.alerts_home(environment),
        qa_home=profiles.qa_home(),
        repo_root=REPO_ROOT,
        agents_dir=Path(configured).expanduser() if configured else Path.home() / "Library" / "LaunchAgents",
        port=qa.port_from_environment(environment),
        docker=container.SystemDockerCli(REPO_ROOT),
        tailscale=qa.SystemTailscaleCli(REPO_ROOT),
        probe=service.LoopbackProbe(),
        metrics=alerts.system_metrics,
        public=qa.system_public_probe,
        telegram=alerts.HttpTelegram(alerts.api_from_environment(environment)),
        launchctl=alerts.SystemLaunchctl(uid),
        clock=service.SystemServiceClock(),
        prompter=_Prompter(),
        tty=sys.stdin.isatty(),
        out=_say,
    )


def main(argv: Optional[Sequence[str]] = None, ports: Optional[alerts.AlertPorts] = None) -> int:
    parser = argparse.ArgumentParser(description="Set up, start, stop, check, or test the QA Telegram alerts.")
    parser.add_argument("operation", choices=alerts.OPERATIONS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    try:
        active = ports or build_ports()
    except (alerts.AlertsUsageError, service.UsageError) as misuse:
        print(misuse.message, file=sys.stderr, flush=True)
        return 2
    out = active.out
    interrupted, interrupted_result, failed_result = WORDING[args.operation]
    try:
        return alerts.run_operation(args.operation, active)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out(failed_result)
        return 1
    except KeyboardInterrupt:
        if args.operation == "check":
            return 1
        out("")
        out(interrupted)
        out(interrupted_result)
        return 1
    except Exception as error:  # noqa: BLE001 - one sentence and the log; never the exception text (it could hold a URL)
        alerts.append_log(active.home, "unexpected error: {}".format(type(error).__name__))
        if args.operation == "check":
            return 1
        out(
            "Something unexpected went wrong. Run the same command again; if it happens again, tell a "
            "developer. Details: {}".format(alerts.log_path(active.home))
        )
        out(failed_result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
