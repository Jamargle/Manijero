#!/usr/bin/env python3
"""Manually scan configured first-party registries into quarantined candidate state."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.source_discovery import discover


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = discover(args.config, args.state)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        # Never echo exception text: parsing/network errors may contain upstream or local data.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    failed_attempt = any(
        item.get("failure") not in (None, "not_configured", "no_verified_machine_readable_registry")
        for item in report["registries"]
    )
    return 1 if failed_attempt else 0


if __name__ == "__main__":
    raise SystemExit(main())
