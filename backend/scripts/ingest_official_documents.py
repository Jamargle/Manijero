#!/usr/bin/env python3
"""Ingest pending official-publication candidates into local quarantine.

Fetches only allowlisted official documents, preserves the original bytes and
provenance hashes, and extracts text with page/section locations. It never
writes canonical knowledge and never makes a candidate answerable.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.document_ingestion import ingest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-state", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--monitor-state", type=Path, default=None)
    args = parser.parse_args()
    try:
        report = ingest(
            args.discovery_state,
            args.state,
            args.quarantine,
            monitoring_state=args.monitor_state,
        )
    except Exception as error:
        # Never echo exception text or a traceback: both may contain upstream
        # values, local paths, or other operator data.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    failed = report["summary"]["failed"] + report["summary"]["rejected"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
