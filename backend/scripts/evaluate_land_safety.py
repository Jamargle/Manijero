#!/usr/bin/env python3
"""Run the offline land-safety evaluation over the accepted decision.

This is a report-only review tool for ``backend/app/land_safety_eval.py``. It
runs the accepted end-to-end decision (``answer_with_clarification``) over a
reviewed, source-anchored case set and reports, per category, whether the
service returned the correct sources, abstained safely, or clarified the correct
land. It reads local JSON only, never performs network access, and never
configures a model provider: grading is deterministic rule checking.

Usage::

    python3 backend/scripts/evaluate_land_safety.py \
      --catalog backend/tests/fixtures/land_safety/catalog.json \
      --passages backend/tests/fixtures/land_safety/passages.json \
      --cases backend/tests/fixtures/land_safety/cases.json \
      --as-of 2026-10-13 --k 5

``--passages`` and ``--cases`` may be omitted; with neither, the command reports
a corpus summary and no metrics, inventing nothing.

The enforced safety invariants (a payload that leaks or invents something: an
abstention carrying a source, a figure, or a date; a clarification carrying an
answer or a foreign land id; an answered payload with no source or an
out-of-range marker) make the command exit ``1``. Coverage and
expected-source/clarification mismatches are **not** enforced unless
``--fail-on-miss`` is passed, because the fixture corpus is small and synthetic
and no metric is a release gate.

Exit codes:

* ``0`` — a report was produced and every safety invariant held.
* ``1`` — a safety invariant failed, or (only with ``--fail-on-miss``) a case did
  not meet its expectation.
* ``2`` — an input file was unreadable or invalid, or arguments were invalid.
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.abstention import prepare_corpus  # noqa: E402  (path setup must run first)
from app.clarification import DEFAULT_MAX_CLAIMS  # noqa: E402
from app.land_safety_eval import (  # noqa: E402
    CATEGORIES,
    LAND_SAFETY_EVAL_SCHEMA_VERSION,
    LandSafetyEvalError,
    evaluate,
    load_cases,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    CatalogRejectedError,
    PassageSetError,
    eligible_source_ids,
    load_passage_set,
)
from app.source_catalog import CatalogReadError, load_catalog  # noqa: E402

EXIT_REPORTED = 0
EXIT_FAILED = 1
EXIT_UNREADABLE = 2


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


def build_report(
    catalog_path: Path,
    passages_path: Optional[Path],
    cases_path: Optional[Path],
    as_of: date,
    k: int,
    max_claims: int,
    core: Dict[str, Any],
) -> Dict[str, Any]:
    """Compose the CLI report around the pure evaluation core."""

    return {
        "catalog": str(catalog_path),
        "passages": str(passages_path) if passages_path is not None else None,
        "cases": str(cases_path) if cases_path is not None else None,
        "as_of": as_of.isoformat(),
        "k": k,
        "max_claims": max_claims,
        "schema_version": LAND_SAFETY_EVAL_SCHEMA_VERSION,
        "fixtures_are_synthetic": True,
        "thresholds_are_release_gates": False,
        **core,
    }


def format_report(report: Dict[str, Any]) -> str:
    """Render the human-readable land-safety report (case ids only, no case text)."""

    index = report["index"]
    lines: List[str] = [
        "land-safety evaluation (synthetic fixtures; safety invariants are enforced)",
        "catalog: {}".format(report["catalog"]),
        "passages: {}".format(report["passages"] if report["passages"] else "(none supplied)"),
        "cases: {}".format(report["cases"] if report["cases"] else "(none supplied)"),
        "as of: {}".format(report["as_of"]),
        "k: {}".format(report["k"]),
        "max claims: {}".format(report["max_claims"]),
        "corpus: {}".format(report["corpus_status"]),
        "eligible sources: {}".format(index["eligible_sources"]),
        "indexed passages: {}".format(index["indexed_passages"]),
        "excluded passages (ineligible source): {}".format(
            index["excluded_passages_ineligible_source"]
        ),
        "",
    ]

    if not report["case_rows"]:
        lines.append("no evaluation cases supplied (pass --cases to run the evaluation)")
        lines.append("")
        lines.append("metrics: (none; no cases supplied)")
        lines.append(
            "safety invariants hold: {}".format(
                "yes" if report["safety_invariants_hold"] else "no"
            )
        )
        return "\n".join(lines)

    for position, row in enumerate(report["case_rows"], start=1):
        lines.append(
            "{}. {} [{}]".format(position, row["id"], row["category"])
        )
        lines.append(
            "   expect: {} -> outcome: {}".format(row["expect"], row["outcome"])
        )
        if row["outcome"] == "answered":
            lines.append(
                "   sources: {}".format(", ".join(row["source_ids"]) or "(none)")
            )
            lines.append(
                "   passages: {}".format(", ".join(row["passage_ids"]) or "(none)")
            )
        elif row["outcome"] == "abstained":
            lines.append("   reason: {}".format(row["reason"] or "(none)"))
            lines.append(
                "   generation reason: {}".format(row["generation_reason"] or "(none)")
            )
        else:
            lines.append(
                "   land ids to choose: {}".format(
                    ", ".join(row["land_ids_to_choose"]) or "(none)"
                )
            )
        failed_checks = [
            name
            for name in row["applicable_checks"]
            if not row["checks"].get(name, True)
        ]
        lines.append(
            "   checks failed: {}".format(", ".join(failed_checks) or "(none)")
        )
        lines.append(
            "   expectation met: {}".format("yes" if row["expectation_met"] else "no")
        )
        if row["safety_violations"]:
            lines.append(
                "   safety violations: {}".format(", ".join(row["safety_violations"]))
            )

    lines.append("")
    lines.append("per category (expectations met / cases):")
    for category in CATEGORIES:
        entry = report["category_totals"][category]
        lines.append(
            "  {}: {}/{}".format(category, entry["expectations_met"], entry["cases"])
        )

    lines.append("")
    lines.append("metrics (report-only; enforced only with --fail-on-miss):")
    counts = report["metric_counts"]
    for name, rate in report["metrics"].items():
        count = counts[name]
        rendered = "(no cases)" if rate is None else "{:.3f}".format(rate)
        lines.append(
            "  {}: {} ({}/{})".format(
                name, rendered, count["matched"], count["total"]
            )
        )

    lines.append("")
    lines.append("critical cases (review provenance for manual audit):")
    if report["critical_reviews"]:
        for review in report["critical_reviews"]:
            lines.append(
                "  {}: reviewed_by={} reviewed_on={} level={} anchor={} outcome={}".format(
                    review["id"],
                    review["reviewed_by"],
                    review["reviewed_on"],
                    review["level"],
                    review["anchor"],
                    review["outcome"],
                )
            )
    else:
        lines.append("  (none)")

    totals = report["totals"]
    lines.append("")
    lines.append("answered outcomes: {}".format(totals["answered"]))
    lines.append("abstained outcomes: {}".format(totals["abstained"]))
    lines.append("clarifications: {}".format(totals["clarifications"]))
    lines.append(
        "safety invariants hold: {}".format(
            "yes" if report["safety_invariants_hold"] else "no"
        )
    )
    lines.append(
        "cases not meeting their expectation: {} (enforced only with --fail-on-miss)".format(
            totals["expectation_mismatches"]
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the offline land-safety evaluation over the accepted decision and "
            "report, per case and per category, whether the service returned the "
            "correct sources, abstained safely, or clarified the correct land. "
            "Report-only for coverage; safety invariants are enforced. No network "
            "access and no model provider."
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
        "--cases",
        type=Path,
        default=None,
        help="path to the JSON case set (omit for a corpus summary only)",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=parse_as_of,
        default=None,
        metavar="YYYY-MM-DD",
        help="evaluation date used for catalog currency (defaults to the current UTC date)",
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
        "--max-claims",
        dest="max_claims",
        type=int,
        default=DEFAULT_MAX_CLAIMS,
        metavar="N",
        help="citation window and answer claim limit (default: {})".format(
            DEFAULT_MAX_CLAIMS
        ),
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="print the report as JSON"
    )
    parser.add_argument(
        "--fail-on-miss",
        dest="fail_on_miss",
        action="store_true",
        help="exit 1 when a case does not meet its expectation (off by default)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_of = args.as_of or current_utc_date()

    if args.k < 1:
        parser.error("--k must be a positive integer")
    if args.max_claims < 1:
        parser.error("--max-claims must be a positive integer")

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
        print("error: land-safety input was rejected", file=sys.stderr)
        for line in str(error).splitlines():
            print("  {}".format(line), file=sys.stderr)
        return EXIT_UNREADABLE

    cases = ()
    if args.cases is not None:
        try:
            cases = load_cases(args.cases)
        except LandSafetyEvalError as error:
            print("error: {}: {}".format(args.cases, error), file=sys.stderr)
            return EXIT_UNREADABLE

    core = evaluate(
        cases,
        corpus,
        as_of,
        args.k,
        max_claims=args.max_claims,
        corpus_source_ids=eligible_source_ids(catalog_document, as_of),
    )
    report = build_report(
        catalog_path=args.catalog,
        passages_path=args.passages,
        cases_path=args.cases,
        as_of=as_of,
        k=args.k,
        max_claims=args.max_claims,
        core=core,
    )

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))

    if not report["safety_invariants_hold"]:
        return EXIT_FAILED
    if args.fail_on_miss and report["totals"]["expectation_mismatches"]:
        return EXIT_FAILED
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
