#!/usr/bin/env python3
"""Open ready knowledge review packages as GitHub pull requests, and protect main.

The owner never runs this file directly::

    ./scripts/init.sh --knowledge-review-open      # open one PR per ready package
    ./scripts/init.sh --knowledge-review-protect   # enable the protected-main ruleset

Both commands print plain sentences and end with one ``Result:`` line. Exit codes:
``0`` done, ``1`` needs attention or was not confirmed, ``2`` a prerequisite is missing
(or the ruleset does not exist). The tool never merges, never enables auto-merge, never
force-pushes, and never deletes a branch. Tests use ``MANIJERO_KNOWLEDGE_REVIEW_HOME``,
``MANIJERO_GH_CLI``, and ``MANIJERO_HOSTED_REVIEW_REPO``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import hosted_review as hosted  # noqa: E402  (path setup must run first)

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = ("open", "protect")
MADRID = hosted.review_package_date_zone()


class EvaluationError(Exception):
    """The offline evaluator did not produce a usable report."""


class Program:
    """Run one external program with a fixed program name and captured text output."""

    def __init__(self, program: str, *, git: bool = False) -> None:
        self._program = program
        self._git = git

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        input_text: Optional[str] = None,
    ) -> hosted.CommandResult:
        environment = dict(os.environ)
        if self._git:
            environment.update(
                {
                    # Keep the author as the automation identity, but let the operator's
                    # Git identity be the committer: protected main requires verified
                    # signatures, and GitHub verifies them under the committer's account.
                    "GIT_AUTHOR_NAME": hosted.GIT_NAME,
                    "GIT_AUTHOR_EMAIL": hosted.GIT_EMAIL,
                    "GIT_TERMINAL_PROMPT": "0",
                }
            )
        try:
            completed = subprocess.run(  # noqa: S603 - fixed program, fixed argv from this module
                [self._program, *argv],
                cwd=str(cwd) if cwd is not None else None,
                input=input_text,
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
        except OSError:
            return hosted.CommandResult(127)
        return hosted.CommandResult(completed.returncode, completed.stdout, completed.stderr)


class ChildEvaluator:
    """Run the offline PAC answer evaluator as a child process over given files."""

    def __init__(self, python: Path, script: Path) -> None:
        self._python = python
        self._script = script

    def evaluate(self, *, catalog: Path, passages: Path, cases: Path, as_of):
        completed = subprocess.run(  # noqa: S603 - fixed program, fixed argv
            [
                str(self._python),
                str(self._script),
                "--catalog",
                str(catalog),
                "--passages",
                str(passages),
                "--cases",
                str(cases),
                "--active-campaign",
                hosted.CAMPAIGN,
                "--as-of",
                as_of.isoformat(),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=dict(os.environ),
            check=False,
        )
        if completed.returncode != 0:
            raise EvaluationError("evaluator exit {}".format(completed.returncode))
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise EvaluationError("evaluator output is not JSON") from error
        if not isinstance(report, dict):
            raise EvaluationError("evaluator output is not a report")
        return report


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports() -> hosted.Ports:
    environment = os.environ
    home = hosted.knowledge_review_home(environment)
    configured_repo = (environment.get(hosted.REPO_ENV) or "").strip()
    repo = Path(configured_repo).expanduser() if configured_repo else REPO_ROOT
    gh = (environment.get(hosted.GH_ENV) or "").strip() or "gh"
    return hosted.Ports(
        home=home,
        repo=repo,
        git=Program("git", git=True),
        gh=Program(gh),
        evaluator=ChildEvaluator(
            Path(sys.executable), REPO_ROOT / "backend" / "scripts" / "evaluate_pac_answers.py"
        ),
        clock=lambda: datetime.now(MADRID),
        input=input,
        out=_say,
    )


def main(argv: Optional[Sequence[str]] = None, ports: Optional[hosted.Ports] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open knowledge review pull requests, or protect main on GitHub."
    )
    parser.add_argument("operation", choices=OPERATIONS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    active = ports or build_ports()
    try:
        if args.operation == "open":
            return hosted.open_reviews(active)
        return hosted.protect(active)
    except KeyboardInterrupt:
        active.out("")
        active.out("Stopped. Run the same command again when you are ready.")
        active.out("Result: the command was stopped.")
        return 1
    except Exception as error:  # noqa: BLE001 - one sentence and the log; never the exception text
        hosted.append_review_log(active.home, "unexpected error: {}".format(type(error).__name__))
        active.out(
            "Something unexpected went wrong. Run the same command again; if it happens "
            "again, tell a developer. Details: {}".format(
                hosted.hosted_review_log(active.home)
            )
        )
        active.out("Result: the command did not finish.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
