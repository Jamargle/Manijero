#!/usr/bin/env python3
"""Manually dispatch one official-feed monitoring scan."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.source_monitor import MonitorError, scan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="JSON file containing an explicit sources array")
    parser.add_argument("--state", type=Path, required=True, help="Local monitoring state JSON path")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or set(config) != {"sources"}:
            raise MonitorError("configuration must contain exactly a sources array")
        report = scan(config["sources"], args.state)
    except (OSError, json.JSONDecodeError, MonitorError) as error:
        print("source scan configuration/state error: {}".format(error), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
