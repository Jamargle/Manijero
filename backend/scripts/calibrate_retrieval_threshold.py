#!/usr/bin/env python3
"""Sweep a minimum BM25 score over the approved golden and trap items, report only."""
import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.answer_eval import AnswerEvalError, load_case_document
from app.golden_set import GoldenSetError
from app.retrieval import PassageSetError, load_passage_set
from app.source_catalog import CatalogReadError, load_catalog
from app.threshold_calibration import SweepInputs, run_sweep
from app.trap_set import TrapSetError


def _write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load_scored(args: argparse.Namespace) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Load and validate the reviewed inputs; only approved golden and trap items are scored."""

    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    cases, coverage = load_case_document(args.cases, catalog, passages)

    from app import golden_set, trap_set

    golden = golden_set.load_golden(args.golden, catalog, passages, cases, coverage)
    golden_cases = golden_set.approved_cases(golden)
    if {case["id"] for case in golden_cases} & {case["id"] for case in cases}:
        raise AnswerEvalError("--golden: an approved item id collides with a reviewed case")
    covered = dict(coverage, areas=coverage["areas"] + golden["additional_areas"])
    traps = trap_set.load_traps(args.traps, catalog, passages, cases, covered, golden)
    trap_cases = trap_set.approved_cases(traps)
    if {case["id"] for case in trap_cases} & (
        {case["id"] for case in cases} | {case["id"] for case in golden_cases}
    ):
        raise AnswerEvalError("--traps: an approved item id collides with another case")

    for case in golden_cases:
        case["case_set"] = "golden"
    for case in trap_cases:
        case["case_set"] = "trap"
    return catalog, passages, golden_cases + trap_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--traps", type=Path, required=True)
    parser.add_argument("--active-campaign", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("build/threshold-calibration"))
    args = parser.parse_args()

    try:
        if args.k < 1 or args.k > 100:
            raise AnswerEvalError("--k must be between 1 and 100")
        catalog, passages, scored = _load_scored(args)
    except (
        AnswerEvalError,
        GoldenSetError,
        TrapSetError,
        CatalogReadError,
        PassageSetError,
        OSError,
        ValueError,
    ) as error:
        print(
            "error: {}".format(
                error
                if isinstance(
                    error,
                    (
                        AnswerEvalError,
                        GoldenSetError,
                        TrapSetError,
                        CatalogReadError,
                        PassageSetError,
                    ),
                )
                else "the reviewed inputs could not be read"
            ),
            file=sys.stderr,
        )
        return 2

    inputs = SweepInputs(
        catalog=args.catalog,
        passages=args.passages,
        cases=args.cases,
        golden=args.golden,
        traps=args.traps,
        active_campaign=args.active_campaign,
        as_of=args.as_of,
        k=args.k,
    )
    loader = lambda _inputs: (catalog, passages, scored)
    outcome = run_sweep(inputs, loader, args.out)
    if outcome.exit_code == 2:
        print(outcome.line, file=sys.stderr)
        return 2
    if outcome.exit_code != 0 or outcome.report is None or outcome.table is None:
        print(outcome.line)
        return outcome.exit_code

    _write_atomically(
        args.out / "report.json",
        json.dumps(outcome.report, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )
    _write_atomically(args.out / "table.md", outcome.table)
    print(outcome.line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
