#!/usr/bin/env python3
"""The nightly evaluation. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --nightly-eval-on      # turn the nightly run on (launchd, 00:00)
    ./scripts/init.sh --nightly-eval-run     # run the complete evaluation now
    ./scripts/init.sh --nightly-eval-status  # is it on, and how did the last run go
    ./scripts/init.sh --nightly-eval-off     # turn the nightly run off (history is kept)

``run --scheduled`` is what launchd runs. Owner commands print plain sentences and end with one
``Result:`` line. Exit codes: ``0`` done and healthy, ``1`` failed or needs attention, ``2`` a
prerequisite is missing, ``3`` another run is in progress. A score drop never changes an exit code.
``MANIJERO_NIGHTLY_EVAL_HOME``, ``MANIJERO_NIGHTLY_EVAL_CHILD_CLI``, ``MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT``,
``MANIJERO_NIGHTLY_EVAL_NO_WAIT``, ``MANIJERO_ALERTS_HOME``, ``MANIJERO_TELEGRAM_API`` (loopback only),
``MANIJERO_LAUNCHCTL_CLI``, and ``MANIJERO_LAUNCH_AGENTS_DIR`` exist for tests only.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import nightly_eval as nightly  # noqa: E402  (path setup must run first)
from app import qa_alerts as alerts  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = ("on", "off", "run", "status")


class TelegramSender:
    """The QA-alerts Telegram bot (``qa_alerts`` unchanged). The details are read here and nowhere else."""

    def __init__(self, home: Path, transport: alerts.TelegramTransport) -> None:
        self._home, self._transport = home, transport

    def configured(self) -> bool:
        return alerts.load_credentials(self._home)[0] is not None

    def send(self, text: str) -> bool:
        credentials, _ = alerts.load_credentials(self._home)
        return credentials is not None and alerts.send_text(self._transport, credentials, text) is None


def _say(text: str) -> None:
    print(text, flush=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_ports() -> nightly.Ports:
    environment = os.environ
    home = nightly.nightly_eval_home(environment)
    python = Path(sys.executable)
    configured = (environment.get(nightly.CHILD_CLI_ENV) or "").strip()
    prefix = [configured] if configured else [str(python), str(REPO_ROOT / "backend" / "scripts" / "evaluate_metrics.py")]
    agents = (environment.get(alerts.AGENTS_DIR_ENV) or "").strip()
    reports = (environment.get(nightly.REPORTS_ROOT_ENV) or "").strip()
    return nightly.Ports(
        home=home,
        repo_root=REPO_ROOT,
        agents_dir=Path(agents).expanduser() if agents else Path.home() / "Library" / "LaunchAgents",
        python=python,
        reports_root=Path(reports).expanduser() if reports else REPO_ROOT / "build" / "eval-reports",
        clock=_now,
        sleep=(lambda seconds: None) if environment.get(nightly.NO_WAIT_ENV) else time.sleep,
        runner=nightly.SubprocessChild(prefix, home),
        launchctl=alerts.SystemLaunchctl(os.getuid(), label=nightly.LABEL),
        telegram=TelegramSender(alerts.alerts_home(environment), alerts.HttpTelegram(alerts.api_from_environment(environment))),
        launchd_path=alerts.LAUNCHD_PATH,
        out=_say,
    )


def _fix(fix: str) -> str:
    return "Run {}, then try again.".format(fix) if fix.startswith("./") else fix[:1].upper() + fix[1:] + "."


def _problem(ports: nightly.Ports, problem: nightly.Problem, did_not: str) -> int:
    ports.out("{} {}".format(problem.sentence, _fix(problem.fix)))
    ports.out("Result: {}.".format(did_not))
    return 2


def _run(ports: nightly.Ports, scheduled: bool) -> int:
    try:
        result = nightly.run_once(ports, "schedule" if scheduled else "manual")
    except nightly.Problem as problem:
        return _problem(ports, problem, "the nightly evaluation did not start")
    except nightly.AlreadyRunning:
        ports.out("A nightly evaluation is already in progress. Wait for it to finish, then look at {}.".format(
            nightly.STATUS_COMMAND))
        ports.out("Result: nothing was started because a run is already in progress.")
        return 3
    ports.out(result.summary.rstrip("\n"))
    ports.out(nightly.result_line(result))
    return result.exit_code


def _status(ports: nightly.Ports) -> int:
    try:
        state = nightly.status(ports)
    except nightly.OpsError:
        ports.out("The history of past runs could not be read. Tell a developer; details are in {}.".format(
            nightly.log_path(ports.home)))
        ports.out("Result: the status could not be read.")
        return 1
    lines, result = nightly.status_lines(state)
    for line in lines:
        ports.out(line)
    ports.out(result)
    return 0 if state.healthy else 1


def _toggle(ports: nightly.Ports, operation: str) -> int:
    try:
        code, result = nightly.turn_on(ports) if operation == "on" else nightly.turn_off(ports)
    except nightly.Problem as problem:
        return _problem(ports, problem, "the nightly evaluation was not turned on")
    ports.out(result)
    return code


def main(argv: Optional[Sequence[str]] = None, ports: Optional[nightly.Ports] = None) -> int:
    parser = argparse.ArgumentParser(description="Turn on, run, check, or turn off the nightly evaluation.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    try:
        active = ports or build_ports()
    except alerts.AlertsUsageError as error:
        print(str(error))
        print("Result: the nightly evaluation command did not run.")
        return 2
    try:
        if args.operation == "run":
            return _run(active, args.scheduled)
        if args.operation == "status":
            return _status(active)
        return _toggle(active, args.operation)
    except KeyboardInterrupt:
        active.out("")
        active.out("Stopped. Run the same command again when you are ready.")
        active.out("Result: the command was stopped.")
        return 1
    except Exception as error:  # noqa: BLE001 - one sentence and the log; never the exception text
        nightly.append_log(active.home, "unexpected error: {}".format(type(error).__name__))
        active.out("Something unexpected went wrong. Run the same command again; if it happens again, "
                   "tell a developer. Details: {}".format(nightly.log_path(active.home)))
        active.out("Result: the command did not finish.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
