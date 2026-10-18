#!/usr/bin/env python3
"""Run the offline abstention decisions over reviewed passages.

This is a report-only review tool for ``backend/app/abstention.py``. It reads
local JSON/JSONL only, never performs network access, and never configures a
model provider: the only enabled generator is the accepted code-composed
extractive one, so no abstention copy is ever model-produced.

Usage::

    python3 backend/scripts/evaluate_abstention.py \
      --catalog backend/tests/fixtures/abstention/catalog.json \
      --passages backend/tests/fixtures/abstention/passages.json \
      --eval backend/tests/fixtures/abstention/eval_questions.jsonl \
      --as-of 2026-10-13 --k 5

``--passages`` and ``--eval`` may be omitted. A catalog whose sources are all
ineligible as of ``--as-of`` reports ``corpus: not_current`` and abstains with
``stale_evidence`` for every question.

Abstention invariants are **enforced**: an abstention payload that carries
sources or land choices, a blank or over-long message, a message containing a
digit or a date, or a reason outside the taxonomy makes the command exit ``1``,
because any of them means an abstention leaked something. Outcome coverage is
**not** enforced unless ``--fail-on-miss`` is passed, because the fixture corpus
is small and synthetic.

Exit codes:

* ``0`` — a report was produced and every abstention invariant held.
* ``1`` — an abstention invariant failed, or (only with ``--fail-on-miss``) an
  outcome differed from its ``expect`` value.
* ``2`` — an input file was unreadable or invalid, or arguments were invalid.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.abstention import (  # noqa: E402  (path setup must run first)
    ABSTENTION_MESSAGES,
    ABSTENTION_REASONS,
    Abstention,
    answer_or_abstain,
    prepare_corpus,
    to_abstention_response,
)
from app.generation import (  # noqa: E402
    MAX_ANSWER_CHARS,
    Answered,
    extract_figures,
    to_answer_response,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402

EXIT_REPORTED = 0
EXIT_FAILED = 1
EXIT_UNREADABLE = 2

EXPECTED_OUTCOMES: Tuple[str, ...] = ("answered",) + ABSTENTION_REASONS

RESPONSE_KEYS = frozenset(
    {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
)


@dataclass(frozen=True)
class EvalLine:
    """One evaluation line: a question and its expected outcome."""

    line: int
    question: str
    expect: str


@dataclass(frozen=True)
class Decision:
    """The decision recorded for one evaluation line."""

    line: int
    question: str
    expect: str
    outcome: str
    reason: Optional[str]
    generation_reason: Optional[str]
    issue_codes: Tuple[str, ...]
    message: Optional[str]
    payload: Dict[str, Any]
    sources_count: int
    violated_invariants: Tuple[str, ...]

    @property
    def abstained(self) -> bool:
        return self.outcome != "answered"

    @property
    def matched_expectation(self) -> bool:
        return self.outcome == self.expect


def parse_as_of(value: str) -> date:
    """Parse an ``--as-of`` argument as YYYY-MM-DD."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--as-of must be a real calendar date formatted as YYYY-MM-DD"
        ) from error


def current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def empty_passage_set() -> Dict[str, Any]:
    """Return a valid passage set with no passages."""

    return {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []}


def load_eval_lines(path: Path) -> Tuple[EvalLine, ...]:
    """Read the JSONL evaluation file, raising ``ValueError`` on invalid input.

    Each line must be a JSON object with exactly ``question`` and ``expect``.
    ``question`` must be a string (a blank one is a legitimate
    ``invalid_question`` case); ``expect`` must be ``answered`` or one of the
    documented abstention reasons.
    """

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError("cannot read evaluation file: {}".format(error)) from error

    lines: List[EvalLine] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError("line {} is not valid JSON: {}".format(number, error)) from error
        if not isinstance(payload, dict):
            raise ValueError("line {} must be a JSON object".format(number))
        if set(payload) != {"question", "expect"}:
            raise ValueError(
                "line {} must have exactly 'question' and 'expect'".format(number)
            )
        question = payload["question"]
        expect = payload["expect"]
        if not isinstance(question, str):
            raise ValueError("line {}: 'question' must be a string".format(number))
        if expect not in EXPECTED_OUTCOMES:
            raise ValueError(
                "line {}: 'expect' must be one of: {}".format(
                    number, ", ".join(EXPECTED_OUTCOMES)
                )
            )
        lines.append(EvalLine(line=number, question=question, expect=expect))

    if not lines:
        raise ValueError("evaluation file contains no questions")
    return tuple(lines)


def abstention_invariant_violations(
    payload: Dict[str, Any], abstention: Abstention
) -> Tuple[str, ...]:
    """Return the violated abstention invariants for one assembled payload.

    These are the checks that mean an abstention leaked evidence, copy, or a
    figure. An empty tuple means the payload is a safe abstention.
    """

    violations: List[str] = []
    if set(payload) != RESPONSE_KEYS:
        violations.append("payload_keys")
    if payload.get("status") != "abstained":
        violations.append("status_not_abstained")
    if payload.get("sources") != []:
        violations.append("sources_not_empty")
    if payload.get("land_ids_to_choose") != []:
        violations.append("land_ids_not_empty")

    message = payload.get("answer")
    if not isinstance(message, str) or not message.strip():
        violations.append("blank_message")
        message = message if isinstance(message, str) else ""
    elif len(message) > MAX_ANSWER_CHARS:
        violations.append("message_too_long")

    if abstention.reason not in ABSTENTION_MESSAGES:
        violations.append("unknown_reason")
    elif message != ABSTENTION_MESSAGES[abstention.reason]:
        violations.append("message_not_pinned")

    if any(character.isdigit() for character in message):
        violations.append("message_has_digit")
    if extract_figures(message):
        violations.append("message_has_figure_or_date")
    return tuple(violations)


def evaluate_line(
    item: EvalLine,
    corpus: Any,
    as_of: date,
    k: int,
) -> Decision:
    """Run one evaluation line and record its decision."""

    result = answer_or_abstain(item.question, corpus, k=k, as_of=as_of)
    if isinstance(result, Answered):
        payload = to_answer_response(result)
        return Decision(
            line=item.line,
            question=item.question,
            expect=item.expect,
            outcome="answered",
            reason=None,
            generation_reason=None,
            issue_codes=(),
            message=None,
            payload=payload,
            sources_count=len(payload["sources"]),
            violated_invariants=(),
        )

    payload = to_abstention_response(result)
    return Decision(
        line=item.line,
        question=item.question,
        expect=item.expect,
        outcome=result.reason,
        reason=result.reason,
        generation_reason=result.generation_reason,
        issue_codes=result.codes(),
        message=result.message,
        payload=payload,
        sources_count=len(payload["sources"]),
        violated_invariants=abstention_invariant_violations(payload, result),
    )


def build_totals(decisions: Sequence[Decision]) -> Dict[str, int]:
    return {
        "questions": len(decisions),
        "answered": sum(1 for decision in decisions if not decision.abstained),
        "abstained": sum(1 for decision in decisions if decision.abstained),
        "abstentions_with_sources": sum(
            1 for decision in decisions if decision.abstained and decision.sources_count
        ),
        "abstentions_with_figures": sum(
            1
            for decision in decisions
            if decision.abstained
            and decision.message is not None
            and (
                any(character.isdigit() for character in decision.message)
                or bool(extract_figures(decision.message))
            )
        ),
        "abstention_invariant_failures": sum(
            len(decision.violated_invariants) for decision in decisions
        ),
        "outcomes_differing_from_expect": sum(
            1 for decision in decisions if not decision.matched_expectation
        ),
    }


def index_summary(corpus: Any) -> Dict[str, int]:
    """Return the index counts for a current corpus, or zeros for a stale one."""

    if isinstance(corpus, Retriever):
        return {
            "eligible_sources": corpus.eligible_source_count,
            "indexed_passages": corpus.indexed_passage_count,
            "excluded_passages_ineligible_source": corpus.excluded_passage_count,
        }
    return {
        "eligible_sources": 0,
        "indexed_passages": 0,
        "excluded_passages_ineligible_source": 0,
    }


def build_report(
    catalog_path: Path,
    passages_path: Optional[Path],
    eval_path: Optional[Path],
    as_of: date,
    k: int,
    corpus: Any,
    decisions: Sequence[Decision],
) -> Dict[str, Any]:
    totals = build_totals(decisions)
    corpus_status = "current" if isinstance(corpus, Retriever) else "not_current"
    return {
        "catalog": str(catalog_path),
        "passages": str(passages_path) if passages_path is not None else None,
        "eval": str(eval_path) if eval_path is not None else None,
        "as_of": as_of.isoformat(),
        "k": k,
        "fixtures_are_synthetic": True,
        "thresholds_are_release_gates": False,
        "corpus_status": corpus_status,
        "index": index_summary(corpus),
        "questions": [
            {
                "line": decision.line,
                "question": decision.question,
                "expect": decision.expect,
                "outcome": decision.outcome,
                "reason": decision.reason,
                "generation_reason": decision.generation_reason,
                "issue_codes": list(decision.issue_codes),
                "message": decision.message,
                "sources": len(decision.payload.get("sources", [])),
                "land_ids_to_choose": list(decision.payload.get("land_ids_to_choose", [])),
                "violated_invariants": list(decision.violated_invariants),
            }
            for decision in decisions
        ],
        "totals": totals,
        "abstention_invariants_hold": totals["abstention_invariant_failures"] == 0,
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render the human-readable abstention report."""

    index = report["index"]
    lines = [
        "abstention decisions (synthetic fixtures; abstention invariants are enforced)",
        "catalog: {}".format(report["catalog"]),
        "passages: {}".format(report["passages"] if report["passages"] else "(none supplied)"),
        "eval: {}".format(report["eval"] if report["eval"] else "(none supplied)"),
        "as of: {}".format(report["as_of"]),
        "k: {}".format(report["k"]),
        "corpus: {}".format(report["corpus_status"]),
        "eligible sources: {}".format(index["eligible_sources"]),
        "indexed passages: {}".format(index["indexed_passages"]),
        "excluded passages (ineligible source): {}".format(
            index["excluded_passages_ineligible_source"]
        ),
        "",
    ]

    if not report["questions"]:
        lines.append("no evaluation questions supplied (pass --eval to run the decisions)")
        return "\n".join(lines)

    for position, decision in enumerate(report["questions"], start=1):
        lines.append("{}. {}".format(position, decision["question"]))
        lines.append(
            "   expect: {} -> outcome: {}".format(decision["expect"], decision["outcome"])
        )
        if decision["outcome"] == "answered":
            lines.append("   sources: {}".format(decision["sources"]))
            continue
        lines.append(
            "   generation reason: {}".format(decision["generation_reason"] or "(none)")
        )
        lines.append(
            "   issues: {}".format(", ".join(decision["issue_codes"]) or "(none)")
        )
        lines.append("   message: {}".format(decision["message"]))
        if decision["violated_invariants"]:
            lines.append(
                "   invariant violations: {}".format(
                    ", ".join(decision["violated_invariants"])
                )
            )

    totals = report["totals"]
    lines.append("")
    lines.append("answered outcomes: {}".format(totals["answered"]))
    lines.append("abstained outcomes: {}".format(totals["abstained"]))
    lines.append("abstentions with sources: {}".format(totals["abstentions_with_sources"]))
    lines.append("abstentions with figures: {}".format(totals["abstentions_with_figures"]))
    lines.append(
        "abstention invariants hold: {}".format(
            "yes" if report["abstention_invariants_hold"] else "no"
        )
    )
    lines.append(
        "outcomes differing from expect: {} (enforced only with --fail-on-miss)".format(
            totals["outcomes_differing_from_expect"]
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the offline abstention decisions over reviewed passages and report "
            "the outcome, reason, generation reason, issue codes, and pinned message "
            "for every question. Report-only for coverage; abstention invariants are "
            "enforced. No network access and no model provider."
        )
    )
    parser.add_argument("--catalog", type=Path, required=True, help="path to the source catalog")
    parser.add_argument(
        "--passages",
        type=Path,
        default=None,
        help="path to the reviewed passage set (omit when no passages are reviewed yet)",
    )
    parser.add_argument(
        "--eval",
        type=Path,
        default=None,
        help="path to the JSONL evaluation questions (omit for a corpus summary only)",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=parse_as_of,
        default=None,
        metavar="YYYY-MM-DD",
        help="decision date used for catalog currency (defaults to the current UTC date)",
    )
    parser.add_argument(
        "--active-campaign",
        default=None,
        help="campaign used to scope campaign-specific sources (default: no campaign)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        metavar="K",
        help="candidate window size (default: {})".format(DEFAULT_K),
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="print the report as JSON"
    )
    parser.add_argument(
        "--fail-on-miss",
        dest="fail_on_miss",
        action="store_true",
        help="exit 1 when an outcome differs from its expect value (off by default)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_of = args.as_of or current_utc_date()

    if args.k < 1:
        parser.error("--k must be a positive integer")

    try:
        catalog_document = load_catalog(args.catalog)
    except CatalogReadError as error:
        print("error: {}: {}".format(args.catalog, error), file=sys.stderr)
        return EXIT_UNREADABLE

    try:
        passage_document = (
            empty_passage_set() if args.passages is None else load_passage_set(args.passages)
        )
    except PassageSetError as error:
        print("error: {}: {}".format(args.passages, error), file=sys.stderr)
        return EXIT_UNREADABLE

    try:
        corpus = prepare_corpus(
            catalog_document, passage_document, as_of, args.active_campaign
        )
    except (PassageSetError, CatalogRejectedError) as error:
        print("error: abstention input was rejected", file=sys.stderr)
        for line in str(error).splitlines():
            print("  {}".format(line), file=sys.stderr)
        return EXIT_UNREADABLE

    lines: Tuple[EvalLine, ...] = ()
    if args.eval is not None:
        try:
            lines = load_eval_lines(args.eval)
        except ValueError as error:
            print("error: {}: {}".format(args.eval, error), file=sys.stderr)
            return EXIT_UNREADABLE

    decisions = tuple(evaluate_line(item, corpus, as_of, args.k) for item in lines)
    report = build_report(
        catalog_path=args.catalog,
        passages_path=args.passages,
        eval_path=args.eval,
        as_of=as_of,
        k=args.k,
        corpus=corpus,
        decisions=decisions,
    )

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))

    if not report["abstention_invariants_hold"]:
        return EXIT_FAILED
    if args.fail_on_miss and report["totals"]["outcomes_differing_from_expect"]:
        return EXIT_FAILED
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
