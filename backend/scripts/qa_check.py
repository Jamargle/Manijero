#!/usr/bin/env python3
"""Check the QA Desktop app against the live QA service. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --qa-check   # is QA reachable, does the QA Desktop app get a sourced answer, is feedback accepted

The run prints plain sentences, one ``PASS`` or ``FAIL`` line per step, and ends with one
``Result:`` line. The test question is made up; no key or answer text is printed. Exit codes: ``0``
every step passed, ``1`` a step failed or the check did not run, ``2`` misuse. An unexpected error
prints one sentence and the path of a log under ``build/qa-check/``.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import qa_check as check  # noqa: E402  (path setup must run first)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _say(text: str) -> None:
    print(text, flush=True)


def main(
    argv: Optional[Sequence[str]] = None,
    repo_root: Optional[Path] = None,
    ports: Optional[check.QaCheckPorts] = None,
) -> int:
    argparse.ArgumentParser(description="Check the QA Desktop app against the live QA service.").parse_args(argv)
    warnings.simplefilter("ignore")
    root = repo_root or REPO_ROOT
    active = ports or check.default_ports(root, dict(os.environ), _say)
    try:
        return check.run_qa_check(root, active)
    except KeyboardInterrupt:
        _say("")
        _say(check.STOPPED_LINE)
        _say(check.STOPPED_RESULT)
        return 1
    except Exception:  # noqa: BLE001 - every unexpected failure becomes one sentence plus a log
        log = root / check.CHECK_DIR / "error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        _say(
            "Something unexpected went wrong. Run the same command again; if it happens again, send "
            "this log file to a developer: {}".format(log)
        )
        _say("Result: the QA check could not finish.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
