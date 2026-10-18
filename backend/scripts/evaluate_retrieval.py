#!/usr/bin/env python3
"""Run the offline retrieval baseline over reviewed passages.

This is a report-only measurement tool for the retrieval boundary implemented in
``backend/app/retrieval.py``. It reads local JSON/JSONL only and never performs
network access.

Usage::

    python3 backend/scripts/evaluate_retrieval.py \
      --catalog backend/tests/fixtures/retrieval/catalog.json \
      --passages backend/tests/fixtures/retrieval/passages.json \
      --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
      --as-of 2026-10-13 --k 5

``--passages`` may be omitted; retrieval then has no reviewed passages to index
(and, with the empty canonical catalog, returns no candidates).

``hit@k``, ``recall@k`` and MRR are **reported, not enforced**. The fixture
corpus is small and synthetic, so these numbers are a starting measurement to
calibrate against, not a release gate.

Exit codes:

* ``0`` — a report was produced.
* ``1`` — only with ``--fail-on-miss``: at least one question missed.
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

from app.retrieval import (  # noqa: E402  (path setup must run first)
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402

EXIT_REPORTED = 0
EXIT_MISS = 1
EXIT_UNREADABLE = 2


@dataclass(frozen=True)
class EvalQuestion:
    """One evaluation line: a question and the passages that answer it."""

    question: str
    expected_passage_ids: Tuple[str, ...]


@dataclass(frozen=True)
class EvalResult:
    """Per-question outcome, including the rank of every expected passage."""

    question: str
    expected_passage_ids: Tuple[str, ...]
    ranks: Tuple[Optional[int], ...]
    retrieved_passage_ids: Tuple[str, ...]
    hit: bool
    recall: float
    reciprocal_rank: float


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
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                "line {} is not valid JSON: {}".format(number, error)
            ) from error
        if not isinstance(payload, dict):
            raise ValueError("line {} must be a JSON object".format(number))
        if set(payload) != {"question", "expected_passage_ids"}:
            raise ValueError(
                "line {} must have exactly 'question' and 'expected_passage_ids'".format(
                    number
                )
            )
        question = payload["question"]
        expected = payload["expected_passage_ids"]
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
        questions.append(
            EvalQuestion(question=question, expected_passage_ids=tuple(expected))
        )

    if not questions:
        raise ValueError("evaluation file contains no questions")
    return tuple(questions)


def evaluate(
    retriever: Retriever, questions: Sequence[EvalQuestion], k: int
) -> Tuple[EvalResult, ...]:
    """Search each question and record the rank of every expected passage."""

    results: List[EvalResult] = []
    for item in questions:
        candidates = retriever.search(item.question, k=k)
        ranks_by_id = {candidate.passage_id: candidate.rank for candidate in candidates}
        ranks = tuple(ranks_by_id.get(passage_id) for passage_id in item.expected_passage_ids)
        found = [rank for rank in ranks if rank is not None]
        results.append(
            EvalResult(
                question=item.question,
                expected_passage_ids=item.expected_passage_ids,
                ranks=ranks,
                retrieved_passage_ids=tuple(
                    candidate.passage_id for candidate in candidates
                ),
                hit=bool(found),
                recall=len(found) / len(item.expected_passage_ids),
                reciprocal_rank=(1.0 / min(found)) if found else 0.0,
            )
        )
    return tuple(results)


def build_report(
    catalog_path: Path,
    passages_path: Optional[Path],
    eval_path: Optional[Path],
    as_of: date,
    k: int,
    retriever: Retriever,
    results: Sequence[EvalResult],
) -> Dict[str, Any]:
    count = len(results)
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
                "question": result.question,
                "expected_passage_ids": list(result.expected_passage_ids),
                "expected_ranks": list(result.ranks),
                "retrieved_passage_ids": list(result.retrieved_passage_ids),
                "hit": result.hit,
                "recall": result.recall,
                "reciprocal_rank": result.reciprocal_rank,
            }
            for result in results
        ],
        "metrics": {
            "questions": count,
            "hit_at_k": (sum(1 for r in results if r.hit) / count) if count else None,
            "recall_at_k": (sum(r.recall for r in results) / count) if count else None,
            "mrr": (sum(r.reciprocal_rank for r in results) / count) if count else None,
        },
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render the human-readable baseline report."""

    index = report["index"]
    lines = [
        "retrieval baseline (synthetic fixtures; thresholds are not release gates)",
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
        lines.append("no evaluation questions supplied (pass --eval to run the baseline)")
        return "\n".join(lines)

    for position, result in enumerate(report["questions"], start=1):
        lines.append("{}. {}".format(position, result["question"]))
        for passage_id, rank in zip(
            result["expected_passage_ids"], result["expected_ranks"]
        ):
            if rank is None:
                lines.append(
                    "   expected {} -> not retrieved within k={}".format(passage_id, report["k"])
                )
            else:
                lines.append("   expected {} -> rank {}".format(passage_id, rank))
        if result["retrieved_passage_ids"]:
            lines.append(
                "   candidates: {}".format(", ".join(result["retrieved_passage_ids"]))
            )
        else:
            lines.append("   candidates: none")

    metrics = report["metrics"]
    lines.append("")
    lines.append(
        "hit@{k}: {value:.3f} ({hits}/{questions})".format(
            k=report["k"],
            value=metrics["hit_at_k"],
            hits=sum(1 for r in report["questions"] if r["hit"]),
            questions=metrics["questions"],
        )
    )
    lines.append("recall@{k}: {value:.3f}".format(k=report["k"], value=metrics["recall_at_k"]))
    lines.append("MRR: {:.3f}".format(metrics["mrr"]))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the offline retrieval baseline over reviewed passages of approved "
            "catalog sources. Report-only by default; no network access."
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
        help="retrieval date used for catalog expiry (defaults to the current UTC date)",
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
        help="exit 1 when a question misses (off by default; thresholds are not gates yet)",
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
        print("error: retrieval input was rejected", file=sys.stderr)
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

    results = evaluate(retriever, questions, args.k) if questions else ()
    report = build_report(
        catalog_path=args.catalog,
        passages_path=args.passages,
        eval_path=args.eval,
        as_of=as_of,
        k=args.k,
        retriever=retriever,
        results=results,
    )

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))

    if args.fail_on_miss and any(not result.hit for result in results):
        return EXIT_MISS
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
