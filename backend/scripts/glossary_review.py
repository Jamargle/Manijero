#!/usr/bin/env python3
"""Seed, list, decide, and check the question glossary (``backend/config/question_glossary.json``).

Owner commands, run through ``./scripts/init.sh`` (steps in ``docs/owner-guide/question-glossary-review.md``)::

    ./scripts/init.sh --glossary-review
    ./scripts/init.sh --glossary-decide approve|reject "<name>" <number-or-id>...

``list`` prints the word pairs that wait for a decision, writes every pair with its state to
``build/glossary-review/pairs.txt``, and ends with one ``Result:`` line. ``decide`` records a named
reviewer's decision and rewrites the file atomically; bad input records nothing. ``seed`` and
``check`` are for developers and validators (explicit paths, exit 0/1/2, ids only).
Unexpected errors go to ``build/glossary-review/last-error.log``, never to the terminal.

Reads the reviewed passages and golden questions; writes only the glossary file (seed, decide)
and files under ``build/``. No network and no model.
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
from app import question_glossary_review as review  # noqa: E402
from app.answer_eval import load_case_document  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

KNOWLEDGE = REPO_ROOT / "knowledge"
DEFAULT_GLOSSARY = REPO_ROOT / "backend" / "config" / "question_glossary.json"
DEFAULT_BUILD = REPO_ROOT / "build" / "glossary-review"

USAGE_LINE = (
    "Result: nothing was recorded. Write approve or reject, your name in quotes, and at least "
    'one word pair number, for example: ./scripts/init.sh --glossary-decide approve "Diego" 1 2 3'
)
DAMAGED_LINE = (
    "Result: the word pair list could not be read, and nothing was recorded. "
    "Send this line to the developer."
)
DAMAGED_LIST_LINE = "Result: the word pair list could not be read. Send this line to the developer."


def _unknown_line(refs: str) -> str:
    return (
        f"Result: nothing was recorded. These word pair numbers are not in the list: {refs}. "
        "Run ./scripts/init.sh --glossary-review and use the numbers shown there."
    )


def _entry_line(number: str) -> str:
    return (
        f"Result: nothing was recorded. Word pair {number} cannot be approved as written. "
        "Reject it, or send this line to the developer."
    )


def _log_error(build_dir: Path) -> None:
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "last-error.log").write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass


def cmd_seed(args: argparse.Namespace) -> int:
    try:
        added, present, refused = review.seed_from_notice(args.glossary, args.notice_review, args.today)
    except review.GlossaryReviewError as exc:
        print(f"glossary seed: {exc}; nothing was written")
        return 2
    except Exception:  # noqa: BLE001
        _log_error(args.build_dir)
        print("glossary seed: unexpected error; nothing was written")
        return 2
    print(f"glossary seed: added {added} proposed, {present} already present, {refused} skipped")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        passages = load_passage_set(args.passages)
        document = review.read_document(args.glossary)
        try:
            golden = gs.read_document(args.golden)
        except gs.GoldenSetError:
            golden = None
        counts = review.state_counts(document)
        args.build_dir.mkdir(parents=True, exist_ok=True)
        gs.write_atomically(
            args.build_dir / "pairs.txt", review.render_list(document, passages, golden, only_waiting=False) + "\n"
        )
        text = review.render_list(document, passages, golden, only_waiting=True)
    except Exception:  # noqa: BLE001
        _log_error(args.build_dir)
        print(DAMAGED_LIST_LINE)
        return 1
    if text:
        print(text)
    tail = f"({counts['approved']} approved, {counts['rejected']} rejected)"
    waiting = counts["proposed"]
    if waiting:
        print(
            f"Result: {waiting} word pairs wait for your decision {tail}. "
            "The same list is in build/glossary-review/pairs.txt."
        )
    else:
        print(f"Result: no word pairs wait for your decision {tail}.")
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
        recorded, waiting = review.record_decision(
            args.glossary, decision, name, refs, date.today() if args.today is None else args.today
        )
    except review.DecisionError as exc:
        print(
            USAGE_LINE
            if exc.kind == "usage"
            else _unknown_line(exc.detail) if exc.kind == "unknown" else _entry_line(exc.detail)
        )
        return 1
    except Exception:  # noqa: BLE001
        _log_error(args.build_dir)
        print(DAMAGED_LINE)
        return 1
    print(
        f"Result: recorded {decision} for {recorded} word pairs by {name}. "
        f"{waiting} still wait for your decision."
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        document = review.read_document(args.glossary)
        golden = gs.load_golden(args.golden, catalog, passages, cases, coverage)
        failures, summary = review.check(
            document,
            cases + gs.approved_cases(golden),
            coverage,
            catalog,
            passages,
            args.as_of,
            args.active_campaign,
            args.k,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"glossary check: cannot run: {type(exc).__name__}")
        return 1
    for line in failures:
        print(line)
    if failures:
        print(f"glossary check: {len(failures)} failures")
        return 1
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("seed", "list", "decide", "check"):
        p = sub.add_parser(name)
        p.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
        p.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
        if name in ("list", "check"):
            p.add_argument("--passages", type=Path, default=KNOWLEDGE / "passages.json")
            p.add_argument("--golden", type=Path, default=KNOWLEDGE / "golden_set.json")
        if name == "check":
            p.add_argument("--catalog", type=Path, required=True)
            p.add_argument("--cases", type=Path, required=True)
            p.add_argument("--active-campaign", required=True)
            p.add_argument("--as-of", type=date.fromisoformat, required=True)
            p.add_argument("--k", type=int, required=True)
        if name in ("seed", "decide"):
            p.add_argument("--today", type=date.fromisoformat, default=None)
        if name == "seed":
            p.add_argument("--notice-review", type=Path, required=True)
            p.set_defaults(today=date.today())
        if name == "decide":
            p.add_argument("words", nargs="*")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return {"seed": cmd_seed, "list": cmd_list, "decide": cmd_decide, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
