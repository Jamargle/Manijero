#!/usr/bin/env python3
"""Scheduled knowledge update runs. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --knowledge-updates-on      # turn the daily run on (launchd, 10:20)
    ./scripts/init.sh --knowledge-updates-run     # run the whole cycle now
    ./scripts/init.sh --knowledge-updates-status  # is it on, and how did the last run go
    ./scripts/init.sh --knowledge-updates-off     # turn the daily run off (history is kept)

``run --scheduled`` is what launchd runs; ``step`` is the child process of one step. Neither is an
owner command. Owner commands print plain sentences and end with one ``Result:`` line. Exit codes:
``0`` done and healthy, ``1`` failed or needs attention, ``2`` a prerequisite is missing, ``3`` another
run is in progress. ``MANIJERO_KNOWLEDGE_OPS_HOME``, ``MANIJERO_KNOWLEDGE_OPS_STEP_CLI``, ``MANIJERO_KNOWLEDGE_OPS_NO_WAIT``,
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

from app import knowledge_ops as ops  # noqa: E402  (path setup must run first)
from app import qa_alerts as alerts  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = ("on", "off", "run", "status", "step")
NO_WAIT_ENV = "MANIJERO_KNOWLEDGE_OPS_NO_WAIT"  # tests only: retries do not wait


def _say(text: str) -> None:
    print(text, flush=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_ports() -> ops.Ports:
    environment = os.environ
    home = ops.knowledge_ops_home(environment)
    python = Path(sys.executable)
    script = REPO_ROOT / "backend" / "scripts" / "knowledge_ops.py"
    configured = (environment.get(ops.STEP_CLI_ENV) or "").strip()
    prefix = [configured] if configured else [str(python), str(script)]
    agents = (environment.get(alerts.AGENTS_DIR_ENV) or "").strip()
    return ops.Ports(
        home=home,
        repo_root=REPO_ROOT,
        agents_dir=Path(agents).expanduser() if agents else Path.home() / "Library" / "LaunchAgents",
        python=python,
        clock=_now,
        sleep=(lambda seconds: None) if environment.get(NO_WAIT_ENV) else time.sleep,
        runner=ops.SubprocessRunner(prefix, ops.log_path(home)),
        launchctl=alerts.SystemLaunchctl(os.getuid(), label=ops.LABEL),
        launchd_path=alerts.LAUNCHD_PATH,
        out=_say,
    )


def _problem(ports: ops.Ports, problem: ops.Problem, did_not: str) -> int:
    ports.out("{} {}".format(problem.sentence, _fix(problem.fix)))
    ports.out("Result: {}.".format(did_not))
    return 2


def _fix(fix: str) -> str:
    return "Run {}, then try again.".format(fix) if fix.startswith("./") else fix[:1].upper() + fix[1:] + "."


def _run(ports: ops.Ports, scheduled: bool) -> int:
    try:
        result = ops.run_cycle(ports, "schedule" if scheduled else "manual")
    except ops.Problem as problem:
        return _problem(ports, problem, "the knowledge update run did not start")
    except ops.AlreadyRunning:
        ports.out("A knowledge update run is already in progress. Wait for it to finish, then look at {}.".format(
            ops.STATUS_COMMAND))
        ports.out("Result: nothing was started because a run is already in progress.")
        return 3
    ports.out(result.summary.rstrip("\n"))
    ports.out(ops.result_line(result))
    return result.exit_code


def _status(ports: ops.Ports) -> int:
    try:
        state = ops.status(ports)
    except ops.Problem as problem:
        return _problem(ports, problem, "knowledge updates are not set up")
    except ops.OpsError:
        ports.out("The history of past runs could not be read. Tell a developer; details are in {}.".format(
            ops.log_path(ports.home)))
        ports.out("Result: the status could not be read.")
        return 1
    lines, result = ops.status_lines(state)
    for line in lines:
        ports.out(line)
    ports.out(result)
    return 0 if state.healthy else 1


def _toggle(ports: ops.Ports, operation: str) -> int:
    try:
        code, result = ops.turn_on(ports) if operation == "on" else ops.turn_off(ports)
    except ops.Problem as problem:
        return _problem(ports, problem, "knowledge updates were not turned on")
    ports.out(result)
    return code


def main(argv: Optional[Sequence[str]] = None, ports: Optional[ops.Ports] = None) -> int:
    parser = argparse.ArgumentParser(description="Turn on, run, check, or turn off the scheduled knowledge updates.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("step", nargs="?", choices=ops.STEPS)
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    if args.operation == "step":
        if args.step is None or args.run_dir is None:
            parser.error("step needs a step name and --run-dir")
        return ops.execute_step(args.step, args.run_dir, REPO_ROOT)
    active = ports or build_ports()
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
        ops.append_log(active.home, "unexpected error: {}".format(type(error).__name__))
        active.out("Something unexpected went wrong. Run the same command again; if it happens again, "
                   "tell a developer. Details: {}".format(ops.log_path(active.home)))
        active.out("Result: the command did not finish.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
