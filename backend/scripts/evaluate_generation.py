#!/usr/bin/env python3
"""Run the offline grounded-generation pipeline over reviewed passages.

This is a report-only review tool for ``backend/app/generation.py``. It reads
local JSON/JSONL only, never performs network access, and never configures a
model provider: the default (and only enabled) generator is the code-composed
extractive one, so every emitted claim is copied from a reviewed excerpt.

Usage::

    python3 backend/scripts/evaluate_generation.py \
      --catalog backend/tests/fixtures/generation/catalog.json \
      --passages backend/tests/fixtures/generation/passages.json \
      --eval backend/tests/fixtures/generation/eval_questions.jsonl \
      --as-of 2026-10-13 --k 5

``--passages`` may be omitted; generation then has no reviewed passages to
answer from (and, with the empty canonical catalog, returns ``no_candidates``).
``--eval`` may be omitted for an index-only report.

Grounding invariants (a claim with no citation, an unsupported figure, a
non-literal critical claim, an unknown or undeclared marker, or an eligibility
assertion) are **enforced**: any of them makes the command exit ``1``, because
it means a generator produced ungrounded output. Answer *coverage* is **not**
enforced unless ``--fail-on-miss`` is passed, because the fixture corpus is
small and synthetic.

Exit codes:

* ``0`` — a report was produced and every grounding invariant held.
* ``1`` — a grounding invariant failed, or (only with ``--fail-on-miss``) a
  question's outcome differed from its ``expect`` value.
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

from app.generation import (  # noqa: E402  (path setup must run first)
    GROUNDING_FAILURE_CODES,
    POLICY_ISSUE_CODES,
    Answered,
    generate_grounded_answer,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    eligible_source_ids,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402

EXIT_REPORTED = 0
EXIT_FAILED = 1
EXIT_UNREADABLE = 2

EXPECTED_OUTCOMES = ("answered", "no_candidates")

# A run fails hard when a generator produced ungrounded output: an ungrounded
# claim, an unknown or undeclared marker, a non-literal critical claim, or a
# policy violation (an eligibility assertion). ``answer_too_long`` and
# ``generator_abstained`` are handled as coverage outcomes instead.
ENFORCED_INVARIANT_CODES = GROUNDING_FAILURE_CODES | POLICY_ISSUE_CODES


@dataclass(frozen=True)
class EvalQuestion:
    """One evaluation line: a question, its reviewed passage(s), and its expectation."""

    line: int
    question: str
    expected_passage_ids: Tuple[str, ...]
    expect: str


@dataclass(frozen=True)
class ClaimOutcome:
    """One material claim and its grounding verdict."""

    text: str
    markers: Tuple[int, ...]
    ok: bool
    issue_codes: Tuple[str, ...]


@dataclass(frozen=True)
class QuestionOutcome:
    """The pipeline outcome for one evaluation question."""

    question: str
    expected_passage_ids: Tuple[str, ...]
    expect: str
    outcome: str
    answer: Optional[str]
    cited_candidate_numbers: Tuple[int, ...]
    claims: Tuple[ClaimOutcome, ...]
    issue_codes: Tuple[str, ...]

    @property
    def produced_answer(self) -> bool:
        return self.outcome == "answered"

    @property
    def matched_expectation(self) -> bool:
        return self.outcome == self.expect

    @property
    def has_grounding_failure(self) -> bool:
        return bool(ENFORCED_INVARIANT_CODES.intersection(self.issue_codes))


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


def load_eval_questions(path: Path) -> Tuple[EvalQuestion, ...]:
    """Read the JSONL evaluation file, raising ``ValueError`` on invalid input."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError("cannot read evaluation file: {}".format(error)) from error

    questions: List[EvalQuestion] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError("line {} is not valid JSON: {}".format(number, error)) from error
        if not isinstance(payload, dict):
            raise ValueError("line {} must be a JSON object".format(number))
        if set(payload) != {"question", "expected_passage_ids", "expect"}:
            raise ValueError(
                "line {} must have exactly 'question', 'expected_passage_ids' and "
                "'expect'".format(number)
            )
        question = payload["question"]
        expected = payload["expected_passage_ids"]
        expect = payload["expect"]
        if not isinstance(question, str) or not question.strip():
            raise ValueError("line {}: 'question' must be a non-blank string".format(number))
        if (
            not isinstance(expected, list)
            or not expected
            or not all(isinstance(item, str) and item.strip() for item in expected)
        ):
            raise ValueError(
                "line {}: 'expected_passage_ids' must be a non-empty array of ids".format(
                    number
                )
            )
        if expect not in EXPECTED_OUTCOMES:
            raise ValueError(
                "line {}: 'expect' must be one of: {}".format(
                    number, ", ".join(EXPECTED_OUTCOMES)
                )
            )
        questions.append(
            EvalQuestion(
                line=number,
                question=question,
                expected_passage_ids=tuple(expected),
                expect=expect,
            )
        )

    if not questions:
        raise ValueError("evaluation file contains no questions")
    return tuple(questions)


def unknown_expected_passage_ids(
    questions: Sequence[EvalQuestion], indexed_passage_ids: Sequence[str]
) -> Tuple[Tuple[int, str], ...]:
    """Return ``(line, passage id)`` pairs naming ids absent from the built index.

    This closes the accepted retrieval finding F4: an evaluation line that names
    a passage the index does not contain is a harness error, not a silent miss.
    """

    indexed = frozenset(indexed_passage_ids)
    unknown: List[Tuple[int, str]] = []
    for item in questions:
        for passage_id in item.expected_passage_ids:
            if passage_id not in indexed:
                unknown.append((item.line, passage_id))
    return tuple(unknown)


def indexed_passage_ids(
    catalog_document: Any, passage_document: Any, as_of: date
) -> Tuple[str, ...]:
    """Return the passage ids the retriever indexed for this catalog and ``as_of``.

    The retriever exposes counts rather than ids, so the harness reuses the
    retriever's own eligibility predicate (:func:`eligible_source_ids`) instead
    of re-implementing it. With a catalog that passed the accepted gate this is
    every declared passage id, because that gate rejects ineligible sources
    before per-passage exclusion runs.
    """

    if not isinstance(passage_document, dict):
        return ()
    passages = passage_document.get("passages")
    if not isinstance(passages, list):
        return ()
    eligible = eligible_source_ids(catalog_document, as_of)
    return tuple(
        passage["id"]
        for passage in passages
        if isinstance(passage, dict)
        and isinstance(passage.get("id"), str)
        and passage.get("source_id") in eligible
    )


def evaluate_question(
    item: EvalQuestion, retriever: Retriever, as_of: date, k: int
) -> QuestionOutcome:
    """Run the pipeline for one question and capture its per-claim verdicts."""

    result = generate_grounded_answer(item.question, retriever, k=k, as_of=as_of)
    claims = tuple(
        ClaimOutcome(
            text=claim.text,
            markers=claim.markers,
            ok=claim.ok,
            issue_codes=tuple(issue.code for issue in claim.issues),
        )
        for claim in result.claims
    )
    if isinstance(result, Answered):
        return QuestionOutcome(
            question=item.question,
            expected_passage_ids=item.expected_passage_ids,
            expect=item.expect,
            outcome="answered",
            answer=result.answer,
            cited_candidate_numbers=result.cited_markers,
            claims=claims,
            issue_codes=(),
        )
    return QuestionOutcome(
        question=item.question,
        expected_passage_ids=item.expected_passage_ids,
        expect=item.expect,
        outcome=result.reason,
        answer=None,
        cited_candidate_numbers=(),
        claims=claims,
        issue_codes=result.codes(),
    )


def build_totals(outcomes: Sequence[QuestionOutcome]) -> Dict[str, int]:
    return {
        "questions": len(outcomes),
        "answers_produced": sum(1 for outcome in outcomes if outcome.produced_answer),
        "claims_checked": sum(len(outcome.claims) for outcome in outcomes),
        "ungrounded_claims": sum(
            1 for outcome in outcomes for claim in outcome.claims if not claim.ok
        ),
        "invented_sources": sum(
            1 for outcome in outcomes if "unknown_marker" in outcome.issue_codes
        ),
        "no_evidence_outcomes": sum(
            1 for outcome in outcomes if outcome.outcome == "no_candidates"
        ),
        "grounding_invariant_failures": sum(
            1 for outcome in outcomes if outcome.has_grounding_failure
        ),
        "outcomes_differing_from_expect": sum(
            1 for outcome in outcomes if not outcome.matched_expectation
        ),
    }


def build_report(
    catalog_path: Path,
    passages_path: Optional[Path],
    eval_path: Optional[Path],
    as_of: date,
    k: int,
    retriever: Retriever,
    outcomes: Sequence[QuestionOutcome],
) -> Dict[str, Any]:
    totals = build_totals(outcomes)
    return {
        "catalog": str(catalog_path),
        "passages": str(passages_path) if passages_path is not None else None,
        "eval": str(eval_path) if eval_path is not None else None,
        "as_of": as_of.isoformat(),
        "k": k,
        "fixtures_are_synthetic": True,
        "thresholds_are_release_gates": False,
        "index": {
            "eligible_sources": retriever.eligible_source_count,
            "indexed_passages": retriever.indexed_passage_count,
            "excluded_passages_ineligible_source": retriever.excluded_passage_count,
        },
        "questions": [
            {
                "question": outcome.question,
                "expected_passage_ids": list(outcome.expected_passage_ids),
                "expect": outcome.expect,
                "outcome": outcome.outcome,
                "answer": outcome.answer,
                "cited_candidate_numbers": list(outcome.cited_candidate_numbers),
                "claims": [
                    {
                        "text": claim.text,
                        "markers": list(claim.markers),
                        "ok": claim.ok,
                        "issue_codes": list(claim.issue_codes),
                    }
                    for claim in outcome.claims
                ],
                "issue_codes": list(outcome.issue_codes),
            }
            for outcome in outcomes
        ],
        "totals": totals,
        "grounding_invariants_hold": totals["grounding_invariant_failures"] == 0,
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render the human-readable generation report."""

    index = report["index"]
    lines = [
        "grounded generation (synthetic fixtures; grounding invariants are enforced)",
        "catalog: {}".format(report["catalog"]),
        "passages: {}".format(report["passages"] if report["passages"] else "(none supplied)"),
        "as of: {}".format(report["as_of"]),
        "k: {}".format(report["k"]),
        "eligible sources: {}".format(index["eligible_sources"]),
        "indexed passages: {}".format(index["indexed_passages"]),
        "excluded passages (ineligible source): {}".format(
            index["excluded_passages_ineligible_source"]
        ),
        "",
    ]

    if not report["questions"]:
        lines.append("no evaluation questions supplied (pass --eval to run the pipeline)")
        return "\n".join(lines)

    for position, outcome in enumerate(report["questions"], start=1):
        lines.append("{}. {}".format(position, outcome["question"]))
        lines.append(
            "   expect: {} -> outcome: {}".format(outcome["expect"], outcome["outcome"])
        )
        if outcome["answer"] is not None:
            lines.append("   answer: {}".format(outcome["answer"]))
        if outcome["answer"] is None and outcome["issue_codes"]:
            lines.append("   issues: {}".format(", ".join(outcome["issue_codes"])))
        for claim_number, claim in enumerate(outcome["claims"], start=1):
            verdict = "ok" if claim["ok"] else "failed"
            cited = ", ".join(str(marker) for marker in claim["markers"]) or "none"
            detail = (
                " ({})".format(", ".join(claim["issue_codes"]))
                if claim["issue_codes"]
                else ""
            )
            lines.append(
                "   claim {}: {}; cites [{}]{}".format(claim_number, verdict, cited, detail)
            )
            lines.append("      {}".format(claim["text"]))

    totals = report["totals"]
    lines.append("")
    lines.append("answers produced: {}".format(totals["answers_produced"]))
    lines.append("claims checked: {}".format(totals["claims_checked"]))
    lines.append("ungrounded claims: {}".format(totals["ungrounded_claims"]))
    lines.append("invented sources: {}".format(totals["invented_sources"]))
    lines.append("no-evidence outcomes: {}".format(totals["no_evidence_outcomes"]))
    lines.append(
        "grounding invariants hold: {}".format(
            "yes" if report["grounding_invariants_hold"] else "no"
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
            "Run the offline grounded-generation pipeline over reviewed passages and "
            "report every material claim with its grounding verdict. Report-only for "
            "coverage; grounding invariants are enforced. No network access and no "
            "model provider."
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
        help="path to the JSONL evaluation questions (omit for an index summary only)",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=parse_as_of,
        default=None,
        metavar="YYYY-MM-DD",
        help="generation date used for catalog expiry (defaults to the current UTC date)",
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
        help="exit 1 when a question's outcome differs from its expect value (off by default)",
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
        retriever = Retriever.from_documents(
            catalog_document, passage_document, as_of, args.active_campaign
        )
    except (PassageSetError, CatalogRejectedError) as error:
        print("error: generation input was rejected", file=sys.stderr)
        for line in str(error).splitlines():
            print("  {}".format(line), file=sys.stderr)
        return EXIT_UNREADABLE

    questions: Tuple[EvalQuestion, ...] = ()
    if args.eval is not None:
        try:
            questions = load_eval_questions(args.eval)
        except ValueError as error:
            print("error: {}: {}".format(args.eval, error), file=sys.stderr)
            return EXIT_UNREADABLE
        unknown = unknown_expected_passage_ids(
            questions, indexed_passage_ids(catalog_document, passage_document, as_of)
        )
        if unknown:
            print(
                "error: {}: evaluation line(s) name passage ids that are not in the "
                "built index".format(args.eval),
                file=sys.stderr,
            )
            for line, passage_id in unknown:
                print("  line {}: {}".format(line, passage_id), file=sys.stderr)
            return EXIT_UNREADABLE

    outcomes = tuple(
        evaluate_question(item, retriever, as_of, args.k) for item in questions
    )
    report = build_report(
        catalog_path=args.catalog,
        passages_path=args.passages,
        eval_path=args.eval,
        as_of=as_of,
        k=args.k,
        retriever=retriever,
        outcomes=outcomes,
    )

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))

    if not report["grounding_invariants_hold"]:
        return EXIT_FAILED
    if args.fail_on_miss and report["totals"]["outcomes_differing_from_expect"]:
        return EXIT_FAILED
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
