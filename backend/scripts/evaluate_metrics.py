#!/usr/bin/env python3
"""Write one deterministic metrics report per version, from the in-process /ask path.

``run`` posts the reviewed ``/ask`` cases, the approved golden items, and the approved trap
items once each through the application, with answer inspection on, and writes
``<reports-root>/<version_id>/metrics.json``. Faithfulness is judged only when the pinned
local judge is available; ``--no-judge`` skips it. Report only: no metric changes the exit
code, and nothing is written outside the reports root.

Defaults are the repository ``knowledge/`` files and ``build/eval-reports``. The command
never drives a live service, never writes under ``knowledge/``, and needs no network.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import answer_eval, eval_metrics, golden_set, trap_set  # noqa: E402
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
from app.question_glossary import (  # noqa: E402
    DEFAULT_PATH as GLOSSARY_PATH,
    SETTING_ENV as GLOSSARY_ENV,
    load_question_glossary,
)
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
DEFAULT_CATALOG = KNOWLEDGE / "source_catalog.json"
DEFAULT_PASSAGES = KNOWLEDGE / "passages.json"
DEFAULT_CASES = KNOWLEDGE / "pac_answer_eval.json"
DEFAULT_GOLDEN = KNOWLEDGE / "golden_set.json"
DEFAULT_TRAPS = KNOWLEDGE / "trap_set.json"
DEFAULT_REPORTS_ROOT = ROOT / "build" / "eval-reports"
JUDGE_SCRIPT = Path(__file__).with_name("judge_grounding.py")

# Environment that would change how the app answers; cleared for the duration of the run.
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


# --- inputs ------------------------------------------------------------------------------


def _tag_case(
    case: Mapping[str, Any], case_set: str, question_type: Optional[str] = None
) -> Dict[str, Any]:
    tagged = dict(case, case_set=case_set)
    if question_type is not None:
        tagged["question_type"] = question_type
    return tagged


def _load_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    """Load and validate every file, tagging each case with its set and golden type."""

    if not eval_metrics.LABEL_PATTERN.match(args.label):
        raise eval_metrics.MetricsAbort("invalid_inputs")
    try:
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        golden = golden_set.load_golden(args.golden, catalog, passages, cases, coverage)
        approved_golden = golden_set.approved_cases(golden)
        if {case["id"] for case in approved_golden} & {case["id"] for case in cases}:
            raise AnswerEvalError("a golden item id collides with a reviewed case")
        coverage = dict(coverage, areas=coverage["areas"] + golden["additional_areas"])
        traps = trap_set.load_traps(
            args.traps, catalog, passages, cases + approved_golden, coverage, golden
        )
        approved_traps = trap_set.approved_cases(traps)
        if {case["id"] for case in approved_traps} & {
            case["id"] for case in cases + approved_golden
        }:
            raise AnswerEvalError("a trap item id collides with another case")
    except Exception:  # noqa: BLE001 - one fixed failure, never a path or parser message
        raise eval_metrics.MetricsAbort("invalid_inputs") from None
    types = {item["id"]: item["question_type"] for item in golden["items"]}
    tagged = (
        [_tag_case(case, "reviewed") for case in cases]
        + [
            _tag_case(case, "golden", types.get(case["id"]))
            for case in approved_golden
        ]
        + [_tag_case(case, "trap") for case in approved_traps]
    )
    glossary: Optional[Any] = None
    glossary_digest = "off"
    if args.glossary == "on":
        glossary, _reason = load_question_glossary({GLOSSARY_ENV: "on"}, GLOSSARY_PATH)
        if glossary is None:
            raise eval_metrics.MetricsAbort("invalid_inputs")
        glossary_digest = eval_metrics._sha256(GLOSSARY_PATH)
    return {
        "catalog": catalog,
        "passages": passages,
        "cases": tagged,
        "glossary": glossary,
        "glossary_digest": glossary_digest,
    }


# --- running -----------------------------------------------------------------------------


def _row_extra(case: Mapping[str, Any], actual: Mapping[str, Any]) -> Dict[str, Any]:
    return eval_metrics.case_row(
        case, actual, case["case_set"], case.get("question_type")
    )


def _run_cases(inputs: Mapping[str, Any], campaign: str, as_of: date) -> List[Dict[str, Any]]:
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": campaign}),
        retention_store=None,
        answer_cache=None,
        answer_inspection=True,
        question_glossary=inputs["glossary"],
    )
    documents = CorpusDocuments(catalog=inputs["catalog"], passages=inputs["passages"])
    application.dependency_overrides[get_corpus_documents] = lambda: documents
    application.dependency_overrides[get_as_of_date] = lambda: as_of
    application.dependency_overrides[get_active_campaign] = lambda: campaign
    application.dependency_overrides[get_retrieval_k] = lambda: eval_metrics.K
    try:
        with TestClient(application) as client:
            report = evaluate(
                inputs["cases"],
                client,
                inputs["catalog"],
                inputs["passages"],
                eval_metrics.K,
                row_extra=_row_extra,
            )
    except AnswerEvalError:
        raise eval_metrics.MetricsAbort("ask_failed") from None
    return list(report["case_rows"])


def _judge_module() -> Any:
    spec = importlib.util.spec_from_file_location("eval_metrics_judge_grounding", JUDGE_SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise eval_metrics.MetricsAbort("internal_error")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _judge_faithfulness(
    args: argparse.Namespace,
    report_path: Path,
    judge_options: Mapping[str, Any],
) -> Dict[str, Any]:
    if args.no_judge:
        return eval_metrics.faithfulness_from_judge(None, "", None)
    judge_report = report_path.parent / "grounding-judge.json"
    argv = [
        "run",
        "--catalog",
        str(args.catalog),
        "--passages",
        str(args.passages),
        "--cases",
        str(args.cases),
        "--golden",
        str(args.golden),
        "--active-campaign",
        args.active_campaign,
        "--as-of",
        args.as_of.isoformat(),
        "--k",
        str(eval_metrics.K),
        "--report",
        str(judge_report),
    ]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = _judge_module().main(argv, **dict(judge_options))
    return eval_metrics.faithfulness_from_judge(code, captured.getvalue(), judge_report)


# --- command -----------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="evaluate the approved sets and write one report")
    run.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    run.add_argument("--passages", type=Path, default=DEFAULT_PASSAGES)
    run.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    run.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    run.add_argument("--traps", type=Path, default=DEFAULT_TRAPS)
    run.add_argument("--active-campaign", default="2026")
    run.add_argument("--as-of", type=date.fromisoformat, required=True)
    run.add_argument("--glossary", choices=("off", "on"), default="off")
    run.add_argument("--label", default="repository")
    run.add_argument(
        "--no-judge",
        action="store_true",
        help="skip the grounding judge; the report says the faithfulness was not judged",
    )
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    reports_root: Optional[Path] = None,
    judge_options: Optional[Mapping[str, Any]] = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    inputs = (args.catalog, args.passages, args.cases, args.golden, args.traps)
    root = DEFAULT_REPORTS_ROOT if reports_root is None else Path(reports_root)
    allowed = False
    try:
        root = eval_metrics.check_reports_root(root, inputs)
        allowed = True
        loaded = _load_inputs(args)
        version = eval_metrics.version_block(
            catalog=args.catalog,
            passages=args.passages,
            cases=args.cases,
            golden=args.golden,
            traps=args.traps,
            glossary=loaded["glossary_digest"],
            as_of=args.as_of.isoformat(),
            active_campaign=args.active_campaign,
            label=args.label,
            schema_versions={
                "answer_eval": answer_eval.VERSION,
                "golden_set": golden_set.VERSION,
                "trap_set": trap_set.VERSION,
                "report": eval_metrics.SCHEMA_VERSION,
            },
        )
        report_id = eval_metrics.version_id(version)
        report_path = root / report_id / "metrics.json"
        with _isolated_environment():
            rows = _run_cases(loaded, args.active_campaign, args.as_of)
            faithfulness = _judge_faithfulness(
                args, report_path, judge_options if judge_options is not None else {}
            )
        document = eval_metrics.build_report(
            version=version,
            report_id=report_id,
            rows=rows,
            faithfulness=faithfulness,
        )
        eval_metrics.write_report_atomically(document, report_path)
        print(eval_metrics.result_line(document, report_path))
        return 0
    except eval_metrics.MetricsAbort as error:
        print(eval_metrics.abort_line(error.code))
        return 2
    except Exception:  # noqa: BLE001 - the trace goes to a log file, never to the terminal
        if allowed:
            eval_metrics.write_error_log(root, traceback.format_exc())
        print(eval_metrics.abort_line("internal_error"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
