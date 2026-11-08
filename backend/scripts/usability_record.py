#!/usr/bin/env python3
"""Record one usability-session participant under an anonymous code.

Owner entry point behind ``./scripts/init.sh --usability-record`` (steps in
``docs/owner-guide.md``, kit in ``docs/usability-session/``). It asks for the code from the paper
sheet, one outcome and whole minutes per task, optional short notes, and whether the app asked
to choose a land in task 3; shows a recap of counts only; and saves after ``yes``. It then prints
counts and median minutes for every saved participant and exactly one ``Result:`` line.

Exit codes: ``0`` saved, ``1`` stopped, declined, refused three times, or unreadable file,
``2`` misuse. The results file lives outside the checkout (``~/manijero/usability``), folder
``0700``, file ``0600``. Refused text is never printed or stored. Standard library only, plus
``app.usability_results``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
sys.dont_write_bytecode = True

from app import usability_results as ur  # noqa: E402

COMMAND = "./scripts/init.sh --usability-record"
MAX_TRIES = 3
RESULT_NOTHING = "Result: nothing was saved. Run {} again.".format(COMMAND)
TASK_LABELS = (
    "Task 1, first use",
    "Task 2, add two lands",
    "Task 3, land question",
    "Task 4, sources",
)

Ask = Callable[[str], Optional[str]]
Out = Callable[[str], None]


class Stop(Exception):
    """The run ends with nothing saved (end of input, refusals, or a declined step)."""


def _read(prompt: str) -> Optional[str]:
    try:
        return input(prompt)
    except EOFError:
        return None


def _ask_valid(ask: Ask, out: Out, prompt: str, check: Callable[[str], Optional[str]], refusal: str) -> str:
    """Ask until ``check`` returns a value; three refusals in a row stop the run."""

    for _ in range(MAX_TRIES):
        answer = ask(prompt)
        if answer is None:
            raise Stop()
        value = check(answer)
        if value is not None:
            return value
        out(refusal)
    raise Stop()


def _note_checker(limit: int) -> Callable[[str], Optional[str]]:
    def check(text: str) -> Optional[str]:
        text = text.strip()
        if len(text) > limit or ur.screen_note(text) is not None:
            return None
        return text

    return check


def _ask_note(ask: Ask, out: Out, label: str, limit: int) -> str:
    refusal = ur.MSG_NOTE_REFUSED + " (At most {} characters.)".format(limit)
    return _ask_valid(ask, out, "{} (optional, Enter to skip): ".format(label), _note_checker(limit), refusal)


def _check_outcome(text: str) -> Optional[str]:
    return ur.OUTCOME_BY_INPUT.get(text.strip())


def _check_minutes(text: str) -> Optional[str]:
    text = text.strip()
    if text.isascii() and text.isdigit() and 0 <= int(text) <= ur.MAX_MINUTES:
        return str(int(text))
    return None


def _check_yes_no(text: str) -> Optional[str]:
    answer = text.strip().lower()
    if answer in ("y", "yes", "s", "si", "sí"):
        return "yes"
    if answer in ("n", "no"):
        return "no"
    return None


def _ask_task(ask: Ask, out: Out, index: int) -> ur.TaskResult:
    task_id = ur.TASK_IDS[index]
    label = TASK_LABELS[index]
    outcome = _ask_valid(
        ask, out,
        "{}: 1 Completada, 2 Necesitó ayuda, 3 Abandonó: ".format(label),
        _check_outcome, "Type 1, 2, or 3.",
    )
    minutes = _ask_valid(
        ask, out, "{}: whole minutes (0-{}): ".format(label, ur.MAX_MINUTES), _check_minutes,
        "Type a whole number from 0 to {}.".format(ur.MAX_MINUTES),
    )
    shown: Optional[bool] = None
    if task_id == ur.LAND_TASK:
        answer = _ask_valid(
            ask, out, "Did the app ask to choose a land? (yes/no): ", _check_yes_no, "Type yes or no."
        )
        shown = answer == "yes"
    note = _ask_note(ask, out, "{} note".format(label), ur.MAX_NOTE)
    return ur.TaskResult(task_id, outcome, int(minutes), note, shown)


def _recap(participant: ur.Participant) -> List[str]:
    done = ur.ResultsFile([participant])
    lines = ["Recap for {}:".format(participant.code)]
    lines.extend(ur.summary_lines(done)[1:])
    return lines


def run(
    argv: Sequence[str],
    env: Mapping[str, str],
    ask: Ask = _read,
    out: Out = print,
    checkout: Path = REPO_ROOT,
) -> int:
    if argv:
        out("Run {} on its own, with nothing after it.".format(COMMAND))
        return 2
    home = ur.results_home(env)
    if ur.is_inside(home, checkout):
        out("The results folder must be outside the Manijero folder.")
        out(RESULT_NOTHING)
        return 1
    path = home / ur.RESULTS_NAME
    try:
        existing = ur.load(path)
    except ur.ResultsFileError:
        out("Result: the results file could not be read, so nothing was saved. Send {} to the developer.".format(path))
        return 1
    try:
        participant = _collect(ask, out, existing)
        results = existing.with_participant(participant)
        ur.save(path, results)
    except (Stop, KeyboardInterrupt):
        out("")
        out("Nothing was saved.")
        out(RESULT_NOTHING)
        return 1
    except OSError:
        out("The results file could not be written.")
        out(RESULT_NOTHING)
        return 1
    for line in ur.summary_lines(results):
        out(line)
    count = len(results.participants)
    out(
        "Result: {} was saved; the results file holds {} participant{}: {}.".format(
            participant.code, count, "" if count == 1 else "s", path
        )
    )
    return 0


def _collect(ask: Ask, out: Out, existing: ur.ResultsFile) -> ur.Participant:
    code = _ask_valid(
        ask, out, "Participant code from the sheet (P1, P2, ...): ", ur.validate_code, ur.MSG_CODE_REFUSED
    )
    if existing.has(code):
        answer = ask("{} is already saved. Type yes to replace it: ".format(code))
        if answer is None or answer.strip().lower() != "yes":
            raise Stop()
    tasks = [_ask_task(ask, out, index) for index in range(len(ur.TASK_IDS))]
    debrief = _ask_note(ask, out, "Debrief note", ur.MAX_DEBRIEF)
    participant = ur.Participant(code, tasks, debrief)
    for line in _recap(participant):
        out(line)
    answer = ask("Type yes to save {}: ".format(code))
    if answer is None or answer.strip().lower() != "yes":
        raise Stop()
    return participant


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return run(list(sys.argv[1:] if argv is None else argv), os.environ)
    except Exception:  # plain line, no traceback
        print("Something unexpected stopped the run.")
        print(RESULT_NOTHING)
        return 1


if __name__ == "__main__":
    sys.exit(main())
