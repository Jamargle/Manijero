#!/usr/bin/env python3
"""List, decide, and check the golden question queue (``knowledge/golden_set.json``).

Owner commands, run through ``./scripts/init.sh`` (steps in ``docs/owner-guide.md``)::

    ./scripts/init.sh --golden-review
    ./scripts/init.sh --golden-decide approve|reject "<name>" <number-or-id>...

``list`` prints the waiting questions in readable form, writes every item with its state to
``build/golden-review/drafts.txt``, and ends with one ``Result:`` line. ``decide`` records a
named reviewer's decision and rewrites the file atomically; bad input records nothing.
``check`` is for developers and validators (explicit paths, exit 0/1, one line per failure).
Unexpected errors go to ``build/golden-review/last-error.log``, never to the terminal.

Reads only the reviewed catalog, passages, and cases; writes only the golden file (decide) and
files under ``build/``. Standard library plus ``app.golden_set``.
"""

import argparse
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.dont_write_bytecode = True

from app import golden_set as gs  # noqa: E402
from app.answer_eval import AnswerEvalError, load_case_document  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

KNOWLEDGE = REPO_ROOT / "knowledge"
DEFAULT_BUILD = REPO_ROOT / "build" / "golden-review"

USAGE_LINE = (
    "Result: nothing was recorded. Write approve or reject, your name in quotes, and at least "
    'one question number, for example: ./scripts/init.sh --golden-decide approve "Diego" 1 2 3'
)
DAMAGED_LINE = (
    "Result: the golden question list could not be read, and nothing was recorded. "
    "Send this line to the developer."
)
DAMAGED_LIST_LINE = "Result: the golden question list could not be read. Send this line to the developer."


def _unknown_line(refs: str) -> str:
    return (
        f"Result: nothing was recorded. These question numbers are not in the list: {refs}. "
        "Run ./scripts/init.sh --golden-review and use the numbers shown there."
    )


def _anchor_line(number: str) -> str:
    return (
        f"Result: nothing was recorded. Question {number} no longer matches the approved "
        "sources. Send this line to the developer."
    )


def _log_error(build_dir: Path) -> None:
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "last-error.log").write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass


def _load_reviewed(args: argparse.Namespace):
    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    cases, coverage = load_case_document(args.cases, catalog, passages)
    return catalog, passages, cases, coverage


def cmd_list(args: argparse.Namespace) -> int:
    try:
        catalog, passages, _cases, _coverage = _load_reviewed(args)
        doc = gs.read_document(args.golden)
        counts = gs.state_counts(doc)
        waiting = counts["draft"]
        args.build_dir.mkdir(parents=True, exist_ok=True)
        gs.write_atomically(args.build_dir / "drafts.txt", gs.render_list(doc, catalog, passages, only_waiting=False))
        text = gs.render_list(doc, catalog, passages, only_waiting=True)
    except Exception:
        _log_error(args.build_dir)
        print(DAMAGED_LIST_LINE)
        return 1
    if text:
        print(text)
    tail = f"({counts['approved']} approved, {counts['rejected']} rejected)"
    if waiting:
        print(
            f"Result: {waiting} golden questions wait for your decision {tail}. "
            "The same list is in build/golden-review/drafts.txt."
        )
    else:
        print(f"Result: no golden questions wait for your decision {tail}.")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    words: List[str] = list(args.words)
    decision = words[0] if words else ""
    name = words[1] if len(words) > 1 else ""
    refs = words[2:]
    if decision not in ("approve", "reject") or not gs.valid_name(name) or not refs:
        print(USAGE_LINE)
        return 1
    try:
        catalog, passages, _cases, coverage = _load_reviewed(args)
        recorded, waiting = gs.record_decision(
            args.golden, decision, name, refs, date.today() if args.today is None else args.today,
            catalog, passages, coverage["omissions"],
        )
    except gs.DecisionError as exc:
        print(
            {"usage": USAGE_LINE}.get(exc.kind)
            or (_unknown_line(exc.detail) if exc.kind == "unknown" else _anchor_line(exc.detail))
        )
        return 1
    except Exception:
        _log_error(args.build_dir)
        print(DAMAGED_LINE)
        return 1
    print(
        f"Result: recorded {decision} for {recorded} golden questions by {name}. "
        f"{waiting} still wait for your decision."
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        catalog, passages, cases, coverage = _load_reviewed(args)
        doc = gs.read_document(args.golden)
    except (gs.GoldenSetError, AnswerEvalError, Exception) as exc:  # noqa: BLE001
        print(f"golden check: cannot read inputs: {exc}")
        return 1
    failures = gs.validate(doc, catalog, passages, cases, coverage)
    for line in failures:
        print(line)
    if failures:
        print(f"golden check: {len(failures)} failures")
        return 1
    summary = gs.distribution_summary(doc["items"])
    print(f"golden check: {len(doc['items'])} items OK")
    for key in ("type", "segment", "passage", "area", "state"):
        print(f"  {key}: " + ", ".join(f"{k}={v}" for k, v in summary[key].items()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "decide", "check"):
        p = sub.add_parser(name)
        p.add_argument("--catalog", type=Path, default=KNOWLEDGE / "source_catalog.json")
        p.add_argument("--passages", type=Path, default=KNOWLEDGE / "passages.json")
        p.add_argument("--cases", type=Path, default=KNOWLEDGE / "pac_answer_eval.json")
        p.add_argument("--golden", type=Path, default=KNOWLEDGE / "golden_set.json")
        p.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
        if name == "decide":
            p.add_argument("--today", type=date.fromisoformat, default=None)
            p.add_argument("words", nargs="*")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return {"list": cmd_list, "decide": cmd_decide, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
