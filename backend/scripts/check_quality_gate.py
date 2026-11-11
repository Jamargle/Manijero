#!/usr/bin/env python3
"""Compare the agreed evaluation metrics with one committed, owner-reviewed baseline.

``check`` measures the two synthetic fixture groups and the 17-case reviewed sample in
process, verifies the baseline's review block, settings, and input digests, and prints
exactly one ``Result:`` line. It writes nothing, reads no golden/trap/judge file, opens
no socket, and never calls ``record``.

``record`` is the only writer: it recomputes the metrics, lists each changed metric, and
rewrites ``backend/config/quality_gate_baseline.json`` canonically. A named reviewer and
a reason are required, and a drop needs ``--accept-regression`` after the owner approves.

Exit codes: ``0`` pass, ``1`` regression, ``2`` no comparison (unreviewed, invalid, or
stale baseline, an ``/ask`` failure, or an unexpected error).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import os
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# Keep the one-line gate output clean; the warning is about the test transport version.
warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient  # noqa: E402

from app import eval_metrics, quality_gate  # noqa: E402
from app.answer_eval import (  # noqa: E402
    AnswerEvalError,
    evaluate,
    load_case_document,
)
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.main import create_app  # noqa: E402
from app.pilot_config import load_config  # noqa: E402
from app.question_glossary import SETTING_ENV as GLOSSARY_ENV  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
CATALOG = KNOWLEDGE / "source_catalog.json"
PASSAGES = KNOWLEDGE / "passages.json"
REVIEWED_CASES = KNOWLEDGE / "pac_answer_eval.json"
DEFAULT_BASELINE = ROOT / "backend" / "config" / "quality_gate_baseline.json"
SCRIPTS = ROOT / "backend" / "scripts"
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

AS_OF = quality_gate.SETTINGS["as_of"]
AS_OF_DATE = date.fromisoformat(AS_OF)
CAMPAIGN = quality_gate.SETTINGS["active_campaign"]
K = quality_gate.SETTINGS["k"]

FIXTURE_FILES = {
    "retrieval_fixture": {
        "catalog": FIXTURES / "retrieval" / "catalog.json",
        "passages": FIXTURES / "retrieval" / "passages.json",
        "questions": FIXTURES / "retrieval" / "eval_questions.jsonl",
    },
    "abstention_fixture": {
        "catalog": FIXTURES / "abstention" / "catalog.json",
        "passages": FIXTURES / "abstention" / "passages.json",
        "questions": FIXTURES / "abstention" / "eval_questions.jsonl",
    },
    "reviewed_sample": {"cases": REVIEWED_CASES},
}

# Environment that would change how the app answers; cleared and restored like the metrics report.
REMOVED_ENV = (
    "MANIJERO_GENERATION_PROVIDER",
    "MANIJERO_LOCAL_MODEL",
    "MANIJERO_GEMINI_MODEL",
    "MANIJERO_ANSWER_TRACE",
    "MANIJERO_RERANKER",
    "MANIJERO_RETRIEVAL_MODE",
    "MANIJERO_STRUCTURED_INDEX",
    "MANIJERO_STRUCTURED_INDEX_DIR",
    "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    GLOSSARY_ENV,
)
ANSWER_CACHE_ENV = "MANIJERO_ANSWER_CACHE"


@contextlib.contextmanager
def _isolated_environment() -> Iterator[None]:
    """Extractive BM25 drafting with the cache off, then every key restored."""

    keys = REMOVED_ENV + (ANSWER_CACHE_ENV,)
    saved = {key: os.environ.get(key) for key in keys}
    try:
        for key in REMOVED_ENV:
            os.environ.pop(key, None)
        os.environ[ANSWER_CACHE_ENV] = "off"
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise quality_gate.GateAbort("internal_error")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- inputs ------------------------------------------------------------------------------


def input_digests() -> Dict[str, Any]:
    """The six pinned fixture files plus the reviewed sample."""

    return {
        name: {
            key: eval_metrics._sha256(path) for key, path in files.items()
        }
        for name, files in FIXTURE_FILES.items()
    }


# --- fixture groups ----------------------------------------------------------------------


def _retrieval_counts(block: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "questions": block["questions"],
        "hits_at_1": block["hits_at_1"],
        "hits_at_3": block["hits_at_3"],
        "hits_at_5": block["hits_at_5"],
        "mrr": 0.0 if block["mrr"] is None else block["mrr"],
    }


def _fixture_retrieval() -> Dict[str, Any]:
    retrieval = _module("quality_gate_evaluate_retrieval", "evaluate_retrieval.py")
    files = FIXTURE_FILES["retrieval_fixture"]
    catalog = load_catalog(files["catalog"])
    passages = load_passage_set(files["passages"])
    retriever = retrieval.Retriever.from_documents(catalog, passages, AS_OF_DATE, CAMPAIGN)
    questions = retrieval.load_eval_questions(files["questions"])
    rows = []
    for result in retrieval.evaluate(retriever, questions, K):
        ranks = [rank for rank in result.ranks if rank is not None]
        rows.append(
            {
                "expected_passages": len(result.expected_passage_ids),
                "first_expected_rank": min(ranks) if ranks else None,
            }
        )
    return _retrieval_counts(eval_metrics.metric_block(rows))


def _fixture_abstention() -> Dict[str, Any]:
    abstention = _module("quality_gate_evaluate_abstention", "evaluate_abstention.py")
    files = FIXTURE_FILES["abstention_fixture"]
    catalog = load_catalog(files["catalog"])
    passages = load_passage_set(files["passages"])
    corpus = abstention.prepare_corpus(catalog, passages, AS_OF_DATE, CAMPAIGN)
    decisions = [
        abstention.evaluate_line(item, corpus, AS_OF_DATE, K)
        for item in abstention.load_eval_lines(files["questions"])
    ]
    return {
        "questions": len(decisions),
        "correct": sum(1 for decision in decisions if decision.matched_expectation),
    }


# --- reviewed sample ---------------------------------------------------------------------


def _row_extra(case: Mapping[str, Any], actual: Mapping[str, Any]) -> Dict[str, Any]:
    return eval_metrics.case_row(case, actual, "reviewed", case.get("question_type"))


def _reviewed_rows() -> List[Dict[str, Any]]:
    catalog = load_catalog(CATALOG)
    passages = load_passage_set(PASSAGES)
    cases, _coverage = load_case_document(REVIEWED_CASES, catalog, passages)
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": CAMPAIGN}),
        retention_store=None,
        answer_cache=None,
        answer_inspection=True,
        question_glossary=None,
    )
    documents = CorpusDocuments(catalog=catalog, passages=passages)
    application.dependency_overrides[get_corpus_documents] = lambda: documents
    application.dependency_overrides[get_as_of_date] = lambda: AS_OF_DATE
    application.dependency_overrides[get_active_campaign] = lambda: CAMPAIGN
    application.dependency_overrides[get_retrieval_k] = lambda: K
    try:
        with TestClient(application) as client:
            report = evaluate(
                cases,
                client,
                catalog,
                passages,
                K,
                row_extra=_row_extra,
            )
    except AnswerEvalError:
        raise quality_gate.GateAbort("ask_failed") from None
    return list(report["case_rows"])


def measure() -> Dict[str, Any]:
    """Both fixture groups and the reviewed sample, once each, offline and in process."""

    rows = _reviewed_rows()
    abstention = eval_metrics.summarize(rows)["abstention"]["overall"]
    return {
        "fixtures_retrieval": _fixture_retrieval(),
        "fixtures_abstention": _fixture_abstention(),
        "reviewed_retrieval": _retrieval_counts(eval_metrics.metric_block(rows)),
        "reviewed_abstention": {
            "expected": abstention["expected"],
            "correct": abstention["correct"],
        },
    }


# --- commands ----------------------------------------------------------------------------


def _baseline_path(value: Optional[Path], override: Optional[Path]) -> Path:
    if override is not None:
        return Path(override)
    return Path(value) if value is not None else DEFAULT_BASELINE


def _check(path: Path) -> int:
    try:
        baseline = quality_gate.load_baseline(path)
        problem = quality_gate.review_problem(baseline)
        if problem is not None:
            raise quality_gate.GateAbort(problem)
        if not quality_gate.settings_match(baseline["settings"]):
            raise quality_gate.GateAbort("baseline_stale")
        if not quality_gate.inputs_match(baseline["inputs"], input_digests()):
            raise quality_gate.GateAbort("baseline_stale")
        with _isolated_environment():
            measured = measure()
        drops = quality_gate.compare(baseline["metrics"], measured)
        if drops:
            print(quality_gate.failed_line(drops))
            return 1
        print(quality_gate.passed_line(measured, baseline["review"]))
        return 0
    except quality_gate.GateAbort as error:
        print(quality_gate.not_enforced_line(error.code))
        return 2
    except Exception:  # noqa: BLE001 - one fixed line, never a traceback on stdout
        print(quality_gate.not_enforced_line("internal_error"))
        return 2


def _record(
    path: Path,
    *,
    reviewer: str,
    reason: str,
    reviewed_on: Optional[str],
    accept_regression: bool,
) -> int:
    try:
        review = quality_gate.review_block(
            reviewer, reason, reviewed_on or date.today().isoformat()
        )
        with _isolated_environment():
            measured = measure()
        changes = quality_gate.record_baseline(
            path=path,
            metrics=measured,
            review=review,
            inputs=input_digests(),
            accept_regression=accept_regression,
        )
        for line in changes:
            print(line)
        print(quality_gate.recorded_line(len(changes), review))
        return 0
    except quality_gate.RecordRefusal as error:
        print(quality_gate.not_recorded_line(str(error)))
        return 2
    except quality_gate.GateAbort as error:
        print(
            quality_gate.not_recorded_line(
                quality_gate.NEXT_STEPS.get(error.code, "the measurement failed")
            )
        )
        return 2
    except Exception:  # noqa: BLE001 - one fixed line, never a traceback on stdout
        print(quality_gate.not_recorded_line("the measurement failed"))
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="compare the metrics with the reviewed baseline")
    check.add_argument("--baseline", type=Path, default=None, help="tests only")
    record = commands.add_parser("record", help="write a new reviewed baseline")
    record.add_argument("--reviewer", default="")
    record.add_argument("--reason", default="")
    record.add_argument("--reviewed-on", default=None)
    record.add_argument("--accept-regression", action="store_true")
    record.add_argument("--baseline", type=Path, default=None, help="tests only")
    return parser


def main(
    argv: Optional[Sequence[str]] = None, *, baseline_path: Optional[Path] = None
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    path = _baseline_path(getattr(args, "baseline", None), baseline_path)
    if args.command == "record":
        return _record(
            path,
            reviewer=args.reviewer,
            reason=args.reason,
            reviewed_on=args.reviewed_on,
            accept_regression=args.accept_regression,
        )
    return _check(path)


if __name__ == "__main__":
    raise SystemExit(main())
