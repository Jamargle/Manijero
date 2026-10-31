#!/usr/bin/env python3
"""Run or inspect best-effort scheduled official-source monitoring and discovery.

Exit codes: 0 success/healthy, 1 a job failed or status has an alert,
2 configuration/state error, 3 another run holds the lock.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.source_update_scheduler import (  # noqa: E402
    JOBS,
    TRIGGERS,
    LockedError,
    SchedulerConfigError,
    exit_code_for_run,
    run_updates,
    status_for_state_dir,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run every due job once (manual dispatch or systemd timer)")
    run.add_argument("--state-dir", type=Path, required=True, help="Operator-owned directory outside the repository")
    run.add_argument("--monitor-config", type=Path, help="JSON file containing exactly a sources array")
    run.add_argument("--job", action="append", choices=JOBS, help="Limit the run to these jobs (repeatable)")
    run.add_argument("--force", action="store_true", help="Run selected jobs even when not due")
    run.add_argument("--boe-date", action="append", default=[], metavar="YYYYMMDD",
                     help="Also scan this BOE sumario date (at most 60 days old, not in the future)")
    run.add_argument("--trigger", choices=TRIGGERS, default="manual")
    status = commands.add_parser("status", help="Report missed, interrupted, failed, and stale runs")
    status.add_argument("--state-dir", type=Path, required=True)
    return parser


def main(argv: Optional[List[str]] = None, **overrides) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.boe_date and args.job and "boe" not in args.job:
        parser.error("--boe-date requires the boe job")
    try:
        if args.command == "run":
            report = run_updates(args.state_dir, monitor_config=args.monitor_config, jobs=args.job,
                                 force=args.force, boe_dates=args.boe_date, trigger=args.trigger, **overrides)
            code = exit_code_for_run(report)
        else:
            report = status_for_state_dir(args.state_dir, **overrides)
            code = 0 if report["healthy"] else 1
    except LockedError:
        print(json.dumps({"error": "locked"}), file=sys.stderr)
        return 3
    except SchedulerConfigError as error:
        print(json.dumps({"error": error.code}), file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        # Never echo exception text: it may contain local paths or upstream data.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
