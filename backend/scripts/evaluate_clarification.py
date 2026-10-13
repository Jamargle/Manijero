#!/usr/bin/env python3
"""Run the offline land-clarification decisions over reviewed passages.

This is a report-only review tool for ``backend/app/clarification.py``. It reads
local JSON/JSONL only, never performs network access, and never configures a
model provider: the only enabled generator is the accepted code-composed
extractive one.

Usage::

    python3 backend/scripts/evaluate_clarification.py \
      --catalog backend/tests/fixtures/clarification/catalog.json \
      --passages backend/tests/fixtures/clarification/passages.json \
      --eval backend/tests/fixtures/clarification/eval_questions.jsonl \
      --as-of 2026-10-13 --k 5

``--passages`` and ``--eval`` may be omitted. Every evaluation line is a JSON
object with exactly ``question``, ``land_context``, and ``expect``; ``expect`` is
``answered``, ``abstained``, or ``needs_land_clarification``.

Clarification invariants are **enforced**: a clarification payload that carries
an answer or a source, a stale or empty answer, an empty/unusable
``land_ids_to_choose``, or an id that was not in the request's own land ids makes
the command exit ``1``, because any of them means the service guessed or
invented something. Outcome coverage is **not** enforced unless ``--fail-on-miss``
is passed, because the fixture corpus is small and synthetic.

Exit codes:

* ``0`` — a report was produced and every clarification invariant held.
* ``1`` — a clarification invariant failed, or (only with ``--fail-on-miss``) an
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
    prepare_corpus,
    to_abstention_response,
)
from app.clarification import (  # noqa: E402
    CLARIFICATION_SCOPE,
    CLARIFICATION_STATUS,
    LAND_SCOPES,
    NeedsLandClarification,
    answer_with_clarification,
    land_ids_of,
    to_clarification_response,
)
from app.generation import (  # noqa: E402
    Answered,
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

EXPECTED_OUTCOMES: Tuple[str, ...] = (
    "answered",
    "abstained",
    "needs_land_clarification",
)

RESPONSE_KEYS = frozenset(
    {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
)

# The only `land_context` keys a request may carry, and the only keys a land may
# carry. Anything else is a malformed evaluation line (exit 2).
LAND_CONTEXT_KEYS = frozenset({"mode", "lands"})
LAND_KEYS = frozenset({"id", "municipality", "water_regime", "production_method"})


@dataclass(frozen=True)
class EvalLine:
    """One evaluation line: a question, its land context, and its expectation."""

    line: int
    question: str
    land_context: Dict[str, Any]
    expect: str


@dataclass(frozen=True)
class Decision:
    """The decision recorded for one evaluation line."""

    line: int
    question: str
    expect: str
    outcome: str
    reason: Optional[str]
    land_ids_to_choose: Tuple[str, ...]
    payload: Dict[str, Any]
    sources_count: int
    violated_invariants: Tuple[str, ...]

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


def validate_land_context(payload: Any, line: int) -> Dict[str, Any]:
    """Validate and return one ``land_context`` object, raising ``ValueError``.

    The context must be an object with only ``mode`` and ``lands``; ``mode`` must
    be one of the documented scopes; ``lands`` must be an array of objects with
    only the contract's land keys, each carrying a non-blank ``id``.
    """

    if not isinstance(payload, dict):
        raise ValueError("line {}: 'land_context' must be a JSON object".format(line))
    unknown = sorted(set(payload) - LAND_CONTEXT_KEYS)
    if unknown:
        raise ValueError(
            "line {}: 'land_context' has an unknown key: {}".format(line, unknown[0])
        )
    if payload.get("mode") not in LAND_SCOPES:
        raise ValueError(
            "line {}: 'land_context.mode' must be one of: {}".format(
                line, ", ".join(LAND_SCOPES)
            )
        )
    lands = payload.get("lands")
    if not isinstance(lands, list):
        raise ValueError("line {}: 'land_context.lands' must be a JSON array".format(line))
    for position, land in enumerate(lands):
        if not isinstance(land, dict):
            raise ValueError(
                "line {}: 'land_context.lands[{}]' must be a JSON object".format(
                    line, position
                )
            )
        land_unknown = sorted(set(land) - LAND_KEYS)
        if land_unknown:
            raise ValueError(
                "line {}: 'land_context.lands[{}]' has an unknown key: {}".format(
                    line, position, land_unknown[0]
                )
            )
        land_id = land.get("id")
        if not isinstance(land_id, str) or not land_id.strip():
            raise ValueError(
                "line {}: 'land_context.lands[{}].id' must be a non-blank string".format(
                    line, position
                )
            )
    return payload


def load_eval_lines(path: Path) -> Tuple[EvalLine, ...]:
    """Read the JSONL evaluation file, raising ``ValueError`` on invalid input."""

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
        if set(payload) != {"question", "land_context", "expect"}:
            raise ValueError(
                "line {} must have exactly 'question', 'land_context', and 'expect'".format(
                    number
                )
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
        land_context = validate_land_context(payload["land_context"], number)
        lines.append(
            EvalLine(line=number, question=question, land_context=land_context, expect=expect)
        )

    if not lines:
        raise ValueError("evaluation file contains no questions")
    return tuple(lines)


def clarification_invariant_violations(
    payload: Dict[str, Any], request_land_ids: Sequence[str]
) -> Tuple[str, ...]:
    """Return the violated clarification invariants for one assembled payload.

    An empty tuple means the payload is a safe clarification. These are the
    checks that mean the service guessed, invented, or leaked something.
    """

    violations: List[str] = []
    if set(payload) != RESPONSE_KEYS:
        violations.append("payload_keys")
    if payload.get("status") != CLARIFICATION_STATUS:
        violations.append("status_not_clarification")
    if payload.get("land_scope") != CLARIFICATION_SCOPE:
        violations.append("scope_not_selected")
    if payload.get("answer") != "":
        violations.append("answer_not_empty")
    if payload.get("sources") != []:
        violations.append("sources_not_empty")

    ids = payload.get("land_ids_to_choose")
    if not isinstance(ids, list) or not ids:
        violations.append("land_ids_empty")
        return tuple(violations)
    if any(not isinstance(land_id, str) or not land_id.strip() for land_id in ids):
        violations.append("land_id_blank")
    if len(set(ids)) != len(ids):
        violations.append("land_ids_not_unique")
    requested = set(request_land_ids)
    if any(land_id not in requested for land_id in ids):
        violations.append("land_id_not_requested")
    return tuple(violations)


def evaluate_line(
    item: EvalLine,
    corpus: Any,
    as_of: date,
    k: int,
) -> Decision:
    """Run one evaluation line and record its decision."""

    result = answer_with_clarification(
        item.question,
        item.land_context,
        corpus,
        k=k,
        as_of=as_of,
    )
    request_land_ids = land_ids_of(item.land_context)

    if isinstance(result, NeedsLandClarification):
        payload = to_clarification_response(result)
        return Decision(
            line=item.line,
            question=item.question,
            expect=item.expect,
            outcome=CLARIFICATION_STATUS,
            reason=None,
            land_ids_to_choose=result.land_ids_to_choose,
            payload=payload,
            sources_count=0,
            violated_invariants=clarification_invariant_violations(
                payload, request_land_ids
            ),
        )

    if isinstance(result, Answered):
        payload = to_answer_response(result)
        return Decision(
            line=item.line,
            question=item.question,
            expect=item.expect,
            outcome="answered",
            reason=None,
            land_ids_to_choose=(),
            payload=payload,
            sources_count=len(payload["sources"]),
            violated_invariants=(),
        )

    payload = to_abstention_response(result)
    return Decision(
        line=item.line,
        question=item.question,
        expect=item.expect,
        outcome="abstained",
        reason=result.reason,
        land_ids_to_choose=(),
        payload=payload,
        sources_count=len(payload["sources"]),
        violated_invariants=(),
    )


def build_totals(decisions: Sequence[Decision]) -> Dict[str, int]:
    return {
        "questions": len(decisions),
        "answered": sum(1 for decision in decisions if decision.outcome == "answered"),
        "abstained": sum(1 for decision in decisions if decision.outcome == "abstained"),
        "clarifications": sum(
            1 for decision in decisions if decision.outcome == CLARIFICATION_STATUS
        ),
        "clarifications_with_land_ids": sum(
            1
            for decision in decisions
            if decision.outcome == CLARIFICATION_STATUS and decision.land_ids_to_choose
        ),
        "clarification_invariant_failures": sum(
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
                "land_ids_to_choose": list(decision.land_ids_to_choose),
                "sources": decision.sources_count,
                "violated_invariants": list(decision.violated_invariants),
            }
            for decision in decisions
        ],
        "totals": totals,
        "clarification_invariants_hold": totals["clarification_invariant_failures"] == 0,
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render the human-readable clarification report."""

    index = report["index"]
    lines = [
        "clarification decisions (synthetic fixtures; clarification invariants are enforced)",
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
        elif decision["outcome"] == "abstained":
            lines.append("   reason: {}".format(decision["reason"] or "(none)"))
        else:
            lines.append(
                "   land ids to choose: {}".format(
                    ", ".join(decision["land_ids_to_choose"]) or "(none)"
                )
            )
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
    lines.append("clarifications: {}".format(totals["clarifications"]))
    lines.append(
        "clarifications with land ids: {}".format(totals["clarifications_with_land_ids"])
    )
    lines.append(
        "clarification invariants hold: {}".format(
            "yes" if report["clarification_invariants_hold"] else "no"
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
            "Run the offline land-clarification decisions over reviewed passages and "
            "report the outcome, land ids to choose, and invariant status for every "
            "question. Report-only for coverage; clarification invariants are enforced. "
            "No network access and no model provider."
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
        corpus = prepare_corpus(catalog_document, passage_document, as_of)
    except (PassageSetError, CatalogRejectedError) as error:
        print("error: clarification input was rejected", file=sys.stderr)
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

    if not report["clarification_invariants_hold"]:
        return EXIT_FAILED
    if args.fail_on_miss and report["totals"]["outcomes_differing_from_expect"]:
        return EXIT_FAILED
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
