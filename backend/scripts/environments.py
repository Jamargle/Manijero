#!/usr/bin/env python3
"""Show the three environments and prepare QA on this computer. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --environments-status   # read-only: local, QA, and prod lines and one result line
    ./scripts/init.sh --qa-settings-setup     # prepare QA settings and access keys on this computer

Every run prints plain sentences and ends with one ``Result:`` line. Nothing is deployed and no
server is contacted. Exit codes: ``0`` done or ready, ``1`` stopped or not ready, ``2`` misuse.
``MANIJERO_LOCAL_HOME`` and ``MANIJERO_QA_HOME`` exist for tests only.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import environment_profiles as profiles  # noqa: E402  (path setup must run first)
from app import local_rag_bootstrap as bootstrap  # noqa: E402


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports() -> profiles.Ports:
    return profiles.Ports(out=_say, prompter=bootstrap.TerminalPrompter(), tty=sys.stdin.isatty())


def main(argv: Optional[Sequence[str]] = None, ports: Optional[profiles.Ports] = None) -> int:
    parser = argparse.ArgumentParser(description="Show the environments or prepare QA on this computer.")
    parser.add_argument("command", choices=("status", "qa-setup"))
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    active = ports or build_ports()
    out = active.out
    try:
        if args.command == "status":
            return profiles.run_status(active)
        return profiles.run_qa_setup(active)
    except KeyboardInterrupt:
        out("")
        out("The command was stopped. Run it again to finish.")
        out("Result: stopped; nothing was deployed.")
        return 1
    except Exception:  # noqa: BLE001 - every unexpected failure becomes one sentence
        out("Something unexpected went wrong. Run the same command again; if it happens again, ask a developer.")
        out("Result: the command could not finish; nothing was deployed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
