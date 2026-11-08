#!/usr/bin/env python3
"""Judge, offline, whether local draft sentences are supported by the passages they cite.

``run`` drafts answers for the reviewed cases and the approved golden items with the pinned
local generator, asks a second pinned local model (a different family) about each draft
sentence, and writes a ``grounding-judge-report-v1`` file outside ``knowledge/``. ``setup``
downloads the pinned judge model and checks its digest, ``check-record`` checks the pin
offline, and ``show-pin`` prints what Ollama has installed for a tag (it never writes).

Evaluation only: nothing here touches ``/ask``, the corpus, or the golden set. Judge scores
are unchecked against human review. Stdout never carries question, answer, sentence, or
passage text, and the only endpoint is the loopback constant in ``app.local_generation``.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, List, Mapping, Optional, Sequence
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

import app.local_generation as local_generation  # noqa: E402
from app import golden_set  # noqa: E402
from app.answer_eval import AnswerEvalError, load_case_document  # noqa: E402
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.gemini_generation import GEMINI_INSTRUCTION_VERSION, SystemClock  # noqa: E402
from app.grounding_judge import (  # noqa: E402
    FAILURES,
    NOT_DRAFTED,
    VERDICT_SCHEMA,
    VERIFIER_BY_OUTCOME,
    JudgeAbort,
    RecordingTransport,
    abort_line,
    build_report,
    check_records,
    check_report_path,
    draft_from_call,
    judge_draft,
    result_line,
    write_report,
)
from app.local_generation import (  # noqa: E402
    LOCAL_MODEL_ENV,
    OLLAMA_BASE_URL,
    PROVIDER_LOCAL,
    OllamaTransport,
    evaluate_local_model_record,
    load_local_model_record,
    loopback_opener,
)
from app.local_rag_bootstrap import OllamaClient, OllamaUnavailable, find_model  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pilot_config import load_config  # noqa: E402
from app.privacy_review import GEMINI_MODEL_ENV, GENERATION_PROVIDER_ENV  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

JUDGE_RECORD_PATH = ROOT / "backend" / "config" / "grounding_judge_model.json"
ERROR_LOG = ROOT / "build" / "grounding-judge" / "last-error.log"
ANSWER_CACHE_ENV = "MANIJERO_ANSWER_CACHE"
WARM_TIMEOUT_SECONDS = 300
SHOW_TIMEOUT_SECONDS = 10
MAX_SHOW_BYTES = 1_048_576

SETUP_LINES = {
    "unpinned": "Result: the grounding judge model is not pinned yet. A developer must record it first; nothing was downloaded.",
    "invalid": "Result: the grounding judge model record is not valid. A developer must fix it; nothing was downloaded.",
    "no_cli": "Result: Ollama is not installed. Install the Ollama app from ollama.com, open it, then run ./scripts/init.sh --grounding-judge-setup again.",
    "not_running": "Result: Ollama is not running. Open the Ollama app, then run ./scripts/init.sh --grounding-judge-setup again.",
    "pull_failed": "Result: the grounding judge model could not be downloaded. Check the internet connection, then run ./scripts/init.sh --grounding-judge-setup again.",
    "mismatch": "Result: the downloaded grounding judge model is not the reviewed one, so it was not accepted. A developer must check it; the record was not changed.",
    "ready": "Result: the grounding judge model is ready.",
    "already_ready": "Result: the grounding judge model is already ready; nothing was downloaded.",
}


# --- helpers ------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _record_document(path: Path) -> Optional[Mapping[str, Any]]:
    return load_local_model_record(path)


def _installed(models: Sequence[Mapping[str, Any]], record: Any) -> str:
    entry = find_model(models, record.model)
    if entry is None:
        return "missing"
    return "ready" if entry.get("digest") == record.digest else "mismatch"


# --- run ----------------------------------------------------------------------------------


def _load_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    try:
        if not 1 <= args.k <= 100:
            raise ValueError("k")
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        golden = golden_set.load_golden(args.golden, catalog, passages, cases, coverage)
        approved = golden_set.approved_cases(golden)
        if {case["id"] for case in approved} & {case["id"] for case in cases}:
            raise AnswerEvalError("an approved item id collides with a reviewed case")
        digests = {
            "catalog_sha256": _sha256(args.catalog),
            "passages_sha256": _sha256(args.passages),
            "cases_sha256": _sha256(args.cases),
            "golden_sha256": _sha256(args.golden),
        }
    except Exception:  # noqa: BLE001 - one fixed failure, never a path or message
        raise JudgeAbort("invalid_inputs") from None
    cases_with_set = [(case, "reviewed") for case in cases] + [(case, "golden") for case in approved]
    return {
        "cases": cases_with_set,
        "documents": CorpusDocuments(catalog=catalog, passages=passages),
        "digests": digests,
    }


def _preflight(ollama: Any, opener: Any, generator: Any, judge: Any) -> None:
    try:
        models = ollama.tags()
    except OllamaUnavailable:
        raise JudgeAbort("ollama_unavailable") from None
    if _installed(models, generator) != "ready":
        raise JudgeAbort("generator_unavailable")
    if _installed(models, judge) != "ready":
        raise JudgeAbort("judge_unavailable")
    # Load each model once, so the generator's short per-request timeout is not spent on a cold load.
    for record in (generator, judge):
        body = json.dumps({"model": record.model, "keep_alive": f"{record.keep_alive_seconds}s"}).encode("utf-8")
        request = urllib.request.Request(
            OLLAMA_BASE_URL + "/api/generate",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with opener.open(request, timeout=WARM_TIMEOUT_SECONDS) as response:
                response.read(local_generation.MAX_RESPONSE_BYTES + 1)
        except Exception:  # noqa: BLE001
            raise JudgeAbort("ollama_unavailable") from None


def _run_cases(
    args: argparse.Namespace,
    inputs: Mapping[str, Any],
    generator: Any,
    judge: Any,
    opener: Any,
    generator_transport: Any,
    judge_transport: Any,
    clock: Any,
) -> List[Dict[str, Any]]:
    recording = RecordingTransport(
        generator_transport
        if generator_transport is not None
        else OllamaTransport(generator, opener=opener)
    )
    judge_sender = (
        judge_transport
        if judge_transport is not None
        else OllamaTransport(judge, opener=opener, response_format=VERDICT_SCHEMA)
    )
    keys = (GENERATION_PROVIDER_ENV, LOCAL_MODEL_ENV, GEMINI_MODEL_ENV, ANSWER_CACHE_ENV)
    saved = {key: os.environ.get(key) for key in keys}
    try:
        os.environ.pop(GEMINI_MODEL_ENV, None)
        os.environ[GENERATION_PROVIDER_ENV] = PROVIDER_LOCAL
        os.environ[LOCAL_MODEL_ENV] = generator.model
        os.environ[ANSWER_CACHE_ENV] = "off"
        application = create_app(
            load_config({"MANIJERO_ACTIVE_CAMPAIGN": args.active_campaign}),
            retention_store=None,
            local_transport=recording,
            generation_clock=clock,
            answer_cache=None,
        )
        resolution = application.state.generation_provider
        if resolution.provider != PROVIDER_LOCAL or resolution.gemini is None:
            raise JudgeAbort("generator_model_record_invalid")
        outcomes: List[str] = []
        recorder = lambda event, **fields: outcomes.append(str(fields.get("outcome")))  # noqa: E731
        application.state.generation_provider = replace(
            resolution, gemini=replace(resolution.gemini, log=recorder)
        )
        documents = inputs["documents"]
        application.dependency_overrides[get_corpus_documents] = lambda: documents
        application.dependency_overrides[get_as_of_date] = lambda: args.as_of
        application.dependency_overrides[get_active_campaign] = lambda: args.active_campaign
        application.dependency_overrides[get_retrieval_k] = lambda: args.k

        rows: List[Dict[str, Any]] = []
        total = len(inputs["cases"])
        with TestClient(application) as client:
            for number, (case, case_set) in enumerate(inputs["cases"], start=1):
                before_outcomes, before_calls = len(outcomes), len(recording.calls)
                client.post(
                    "/ask", json={"question": case["question"], "land_context": case["land_context"]}
                )
                outcome = outcomes[before_outcomes] if len(outcomes) > before_outcomes else NOT_DRAFTED
                sentences: List[Dict[str, Any]] = []
                if outcome in VERIFIER_BY_OUTCOME and len(recording.calls) > before_calls:
                    draft = draft_from_call(*recording.calls[-1])
                    if draft is not None:
                        answer, excerpts = draft
                        sentences = judge_draft(answer, excerpts, transport=judge_sender, record=judge)
                rows.append(
                    {"id": case["id"], "case_set": case_set, "outcome": outcome, "sentences": sentences}
                )
                print(f"Checked case {number} of {total}", flush=True)
        return rows
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run(args: argparse.Namespace, opts: Mapping[str, Any]) -> int:
    clock = opts["clock"]
    opener = opts["opener"] if opts["opener"] is not None else loopback_opener()
    judge, generator = check_records(
        _record_document(args.judge_record),
        _record_document(local_generation.DEFAULT_RECORD_PATH),
        clock.utc_day(),
    )
    target = check_report_path(args.report, (args.catalog, args.passages, args.cases, args.golden))
    inputs = _load_inputs(args)
    ollama = opts["ollama"] if opts["ollama"] is not None else OllamaClient(opener=opener)
    _preflight(ollama, opener, generator, judge)
    rows = _run_cases(
        args, inputs, generator, judge, opener, opts["generator_transport"], opts["judge_transport"],
        opts["clock_override"],
    )
    document = build_report(
        case_rows=rows,
        generator=generator,
        judge=judge,
        generator_instruction_version=GEMINI_INSTRUCTION_VERSION,
        input_digests=inputs["digests"],
        settings={
            "active_campaign": args.active_campaign,
            "as_of": args.as_of.isoformat(),
            "k": args.k,
        },
    )
    write_report(document, target)
    print(result_line(document["summary"], str(args.report)))
    return 0


# --- setup, check-record, show-pin --------------------------------------------------------------


def _setup(args: argparse.Namespace, opts: Mapping[str, Any]) -> int:
    document = _record_document(args.judge_record)
    if isinstance(document, Mapping) and document.get("digest") == "unpinned":
        print(SETUP_LINES["unpinned"])
        return 1
    _, record = evaluate_local_model_record(document, as_of=opts["clock"].utc_day())
    if record is None:
        print(SETUP_LINES["invalid"])
        return 1
    opener = opts["opener"] if opts["opener"] is not None else loopback_opener()
    ollama = opts["ollama"] if opts["ollama"] is not None else OllamaClient(opener=opener)
    if not ollama.cli_present():
        print(SETUP_LINES["no_cli"])
        return 1
    try:
        state = _installed(ollama.tags(), record)
    except OllamaUnavailable:
        print(SETUP_LINES["not_running"])
        return 1
    if state == "ready":
        print(SETUP_LINES["already_ready"])
        return 0
    print(
        f"Downloading the grounding judge model ({record.model}, about "
        f"{record.size_bytes / 1e9:.1f} GB). Ollama shows its own progress.",
        flush=True,
    )
    if ollama.pull(record.model) != 0:
        print(SETUP_LINES["pull_failed"])
        return 1
    try:
        state = _installed(ollama.tags(), record)
    except OllamaUnavailable:
        print(SETUP_LINES["pull_failed"])
        return 1
    if state == "missing":
        print(SETUP_LINES["pull_failed"])
        return 1
    if state == "mismatch":
        print(SETUP_LINES["mismatch"])
        return 1
    print(SETUP_LINES["ready"])
    return 0


def _check_record(args: argparse.Namespace, opts: Mapping[str, Any]) -> int:
    try:
        judge, generator = check_records(
            _record_document(args.judge_record),
            _record_document(local_generation.DEFAULT_RECORD_PATH),
            opts["clock"].utc_day(),
        )
    except JudgeAbort as error:
        print(f"Result: the grounding judge record check failed ({error.failure}): {FAILURES[error.failure]}")
        return 2
    print(
        f"Result: the grounding judge record is valid and pinned (judge {judge.model}, "
        f"drafting {generator.model}; different tag, digest, and family)."
    )
    return 0


def _show_pin(args: argparse.Namespace, opts: Mapping[str, Any]) -> int:
    opener = opts["opener"] if opts["opener"] is not None else loopback_opener()
    ollama = opts["ollama"] if opts["ollama"] is not None else OllamaClient(opener=opener)
    tag = args.tag
    if tag is None:
        document = _record_document(args.judge_record)
        tag = document.get("model") if isinstance(document, Mapping) else None
    try:
        entry = find_model(ollama.tags(), str(tag))
        if entry is None:
            raise ValueError("missing")
        request = urllib.request.Request(
            OLLAMA_BASE_URL + "/api/show",
            data=json.dumps({"model": tag}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=SHOW_TIMEOUT_SECONDS) as response:
            shown = json.loads(response.read(MAX_SHOW_BYTES + 1).decode("utf-8"))
        license_text = shown.get("license") if isinstance(shown, dict) else None
    except Exception:  # noqa: BLE001
        print("Result: could not read that model from Ollama; nothing was written.")
        return 2
    print(f"model: {tag}")
    print(f"digest: {entry.get('digest')}")
    print(f"size_bytes: {entry.get('size')}")
    print("details: " + json.dumps(shown.get("details"), sort_keys=True))
    if isinstance(license_text, str):
        print(
            f"license_sha256: {hashlib.sha256(license_text.encode('utf-8')).hexdigest()} "
            f"({len(license_text)} chars)"
        )
    print("Result: printed the installed model details; nothing was written.")
    return 0


# --- entry point ----------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="draft, judge, and write the report")
    run.add_argument("--catalog", type=Path, required=True)
    run.add_argument("--passages", type=Path, required=True)
    run.add_argument("--cases", type=Path, required=True)
    run.add_argument("--golden", type=Path, required=True)
    run.add_argument("--active-campaign", required=True)
    run.add_argument("--as-of", type=date.fromisoformat, required=True)
    run.add_argument("--k", type=int, default=5)
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--judge-record", type=Path, default=JUDGE_RECORD_PATH)

    for name, text in (("setup", "download and verify the pinned judge model"), ("check-record", "offline pin check")):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--judge-record", type=Path, default=JUDGE_RECORD_PATH)

    show = commands.add_parser("show-pin", help="print what Ollama has installed for a tag")
    show.add_argument("--tag", default=None)
    show.add_argument("--judge-record", type=Path, default=JUDGE_RECORD_PATH)
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    opener: Any = None,
    generator_transport: Any = None,
    judge_transport: Any = None,
    ollama: Any = None,
    clock: Any = None,
    error_log: Optional[Path] = None,
) -> int:
    args = _parser().parse_args(argv)
    opts = {
        "opener": opener,
        "generator_transport": generator_transport,
        "judge_transport": judge_transport,
        "ollama": ollama,
        "clock": clock if clock is not None else SystemClock(),
        "clock_override": clock,
    }
    handlers = {"run": _run, "setup": _setup, "check-record": _check_record, "show-pin": _show_pin}
    try:
        return handlers[args.command](args, opts)
    except JudgeAbort as error:
        print(abort_line(error.failure))
        return 2
    except Exception:  # noqa: BLE001 - the trace goes to a log file, never to the terminal
        target = error_log if error_log is not None else ERROR_LOG
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        print(abort_line("internal_error"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
