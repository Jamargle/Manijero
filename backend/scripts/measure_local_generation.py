#!/usr/bin/env python3
"""Opt-in live measurement of local (Ollama) drafting against the extractive baseline.

Runs the reviewed /ask cases once with the extractive provider and ``--repeats`` times with
the ``local`` provider, in-process, and prints one text-free JSON report: latencies, the cold
load, peak memory against the 50 GB budget, outcome counts, the verified-draft rate, and the
side-by-side ``answer_eval`` aggregates. It never prints question, passage, or answer text and
makes no recommendation. It is not part of the automated tests and needs Ollama serving the
pinned model at the loopback constant; it never pulls a model.

Exit codes: 0 completed within budget; 1 completed but a memory peak exceeded the budget;
2 Ollama unreachable, model missing, digest mismatch, invalid input, or a run failure.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.answer_eval import evaluate, load_case_document  # noqa: E402
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.local_generation import (  # noqa: E402
    DEFAULT_RECORD_PATH,
    LOCAL_MODEL_ENV,
    MEMORY_BUDGET_BYTES,
    OLLAMA_BASE_URL,
    OUTCOME_LOCAL_USED,
    PROVIDER_LOCAL,
    LocalModelRecord,
    OllamaTransport,
    evaluate_local_model_record,
    load_local_model_record,
    loopback_opener,
)
from app.main import create_app  # noqa: E402
from app.pilot_config import load_config  # noqa: E402
from app.privacy_review import GEMINI_MODEL_ENV, GENERATION_PROVIDER_ENV  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

REPORT_SCHEMA = "local-generation-measurement-v1"
PROBE_TIMEOUT_SECONDS = 2.0
UNLOAD_TIMEOUT_SECONDS = 120.0
COLD_LOAD_TIMEOUT_SECONDS = 300.0
SAMPLE_INTERVAL_SECONDS = 0.5
MAX_PROBE_BYTES = 1_048_576
COMPARED_FLAGS = (
    "actual_status",
    "expected_state_match",
    "source_match",
    "passage_match",
    "critical_facts_match",
    "response_sha256",
)
NOT_DRAFTED = "not_drafted"


class MeasurementError(Exception):
    """A fixed-code failure that ends the run with exit 2."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- Pure helpers (imported by the tests) ---------------------------------------------


def summarize_latencies(values: Iterable[float]) -> dict:
    """Count, median, nearest-rank p95, and max; ``None`` statistics when empty."""

    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "median": None, "p95": None, "max": None}
    count = len(ordered)
    middle = count // 2
    median = ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    p95 = ordered[max(0, math.ceil(0.95 * count) - 1)]
    return {"count": count, "median": _round(median), "p95": _round(p95), "max": _round(ordered[-1])}


def verified_draft_rate(outcomes: Mapping[str, int]) -> Optional[float]:
    """``local_used`` over all drafting invocations; ``None`` when nothing was drafted."""

    invocations = sum(outcomes.values())
    if invocations == 0:
        return None
    return _round(outcomes.get(OUTCOME_LOCAL_USED, 0) / invocations)


def changed_case_ids(baseline_rows: Sequence[Mapping], other_rows: Sequence[Mapping]) -> dict:
    """The case ids whose compared flags differ, each with the sorted changed flag names."""

    baseline = {row["id"]: row for row in baseline_rows}
    changed = {}
    for row in other_rows:
        reference = baseline.get(row["id"], {})
        flags = sorted(
            flag
            for flag in COMPARED_FLAGS
            if (flag in row or flag in reference) and row.get(flag) != reference.get(flag)
        )
        if flags:
            changed[row["id"]] = flags
    return changed


def budget_check(peaks: Mapping[str, Optional[int]], budget: int = MEMORY_BUDGET_BYTES) -> bool:
    """True when every sampled peak is within the budget (inclusive)."""

    return all(value <= budget for value in peaks.values() if value is not None)


def _round(value: float) -> float:
    return round(float(value), 4)


# --- Loopback probe and memory sampling -----------------------------------------------


class OllamaProbe:
    """Plain JSON calls to the loopback Ollama API for measurement control only."""

    def __init__(self, opener: Any) -> None:
        self._opener = opener

    def call(self, path: str, body: Optional[Mapping[str, Any]] = None, *, timeout: float) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            OLLAMA_BASE_URL + path,
            data=data,
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json"},
        )
        with self._opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_PROBE_BYTES + 1)
        if len(raw) > MAX_PROBE_BYTES:
            raise ValueError("probe_response_too_large")
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("probe_response_invalid")
        return document

    def loaded(self, model: str) -> Optional[dict]:
        document = self.call("/api/ps", timeout=PROBE_TIMEOUT_SECONDS)
        for entry in document.get("models") or []:
            if isinstance(entry, dict) and model in (entry.get("name"), entry.get("model")):
                return entry
        return None


def _is_ollama_process(command: str) -> bool:
    # Ollama 0.40.13 on macOS runs the model in a separate ``llama-server`` process inside
    # ``Ollama.app``; matching only names that start with ``ollama`` would miss it.
    return "/ollama.app/" in command.lower() or command.rsplit("/", 1)[-1].lower().startswith("ollama")


def ollama_rss_bytes(run: Callable[..., Any] = subprocess.run) -> Optional[int]:
    """Summed resident set size of the Ollama processes (server, app, and model runner)."""

    try:
        output = run(
            ["ps", "-axo", "rss=,comm="], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except Exception:  # noqa: BLE001 - sampling is best effort
        return None
    total = 0
    for line in output.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and _is_ollama_process(parts[1]):
            total += int(parts[0]) * 1024
    return total


class MemorySampler(threading.Thread):
    """Samples ``/api/ps`` and the ``ollama`` RSS every half second and keeps the peaks."""

    def __init__(self, probe: OllamaProbe, model: str) -> None:
        super().__init__(daemon=True)
        self._probe = probe
        self._model = model
        self._stop_event = threading.Event()
        self.samples = 0
        self.peaks: dict = {"ps_size_bytes": None, "ps_size_vram_bytes": None, "ollama_rss_bytes": None}

    def run(self) -> None:
        self.sample()
        while not self._stop_event.wait(SAMPLE_INTERVAL_SECONDS):
            self.sample()

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=10)
        self.sample()

    def sample(self) -> None:
        self.samples += 1
        try:
            entry = self._probe.loaded(self._model)
        except Exception:  # noqa: BLE001 - sampling is best effort
            entry = None
        if entry is not None:
            self._peak("ps_size_bytes", entry.get("size"))
            self._peak("ps_size_vram_bytes", entry.get("size_vram"))
        self._peak("ollama_rss_bytes", ollama_rss_bytes())

    def _peak(self, key: str, value: object) -> None:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            current = self.peaks[key]
            self.peaks[key] = value if current is None else max(current, value)


def unload(probe: OllamaProbe, model: str) -> None:
    probe.call("/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
    deadline = time.monotonic() + UNLOAD_TIMEOUT_SECONDS
    while probe.loaded(model) is not None:
        if time.monotonic() > deadline:
            raise MeasurementError("unload_timeout")
        time.sleep(0.5)


def cold_load_seconds(probe: OllamaProbe, record: LocalModelRecord) -> float:
    unload(probe, record.model)
    started = time.perf_counter()
    probe.call(
        "/api/generate",
        {"model": record.model, "keep_alive": f"{record.keep_alive_seconds}s"},
        timeout=COLD_LOAD_TIMEOUT_SECONDS,
    )
    return time.perf_counter() - started


# --- One mode over the cases ----------------------------------------------------------


class TimedClient:
    """Times each ``/ask`` and pairs it with the drafting outcome it produced, if any."""

    def __init__(self, client: TestClient, outcomes: list) -> None:
        self._client = client
        self._outcomes = outcomes
        self.records: list[dict] = []

    def post(self, url: str, json: Any) -> Any:  # noqa: A002 - mirrors TestClient.post
        before = len(self._outcomes)
        started = time.perf_counter()
        response = self._client.post(url, json=json)
        elapsed = time.perf_counter() - started
        self.records.append(
            {
                "seconds": elapsed,
                "outcome": self._outcomes[before] if len(self._outcomes) > before else None,
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
        return response


class TimedTransport:
    """Times each ``send`` of the wrapped transport, including failures."""

    def __init__(self, inner: OllamaTransport) -> None:
        self._inner = inner
        self.seconds: list[float] = []

    def send(self, request: Any) -> str:
        started = time.perf_counter()
        try:
            return self._inner.send(request)
        finally:
            self.seconds.append(time.perf_counter() - started)


def _set_mode_env(mode: str, record: LocalModelRecord) -> None:
    for key in (GENERATION_PROVIDER_ENV, LOCAL_MODEL_ENV, GEMINI_MODEL_ENV):
        os.environ.pop(key, None)
    if mode == PROVIDER_LOCAL:
        os.environ[GENERATION_PROVIDER_ENV] = PROVIDER_LOCAL
        os.environ[LOCAL_MODEL_ENV] = record.model


def run_mode(
    mode: str,
    record: LocalModelRecord,
    args: argparse.Namespace,
    inputs: Mapping[str, Any],
    transport: Optional[TimedTransport] = None,
) -> dict:
    _set_mode_env(mode, record)
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": args.active_campaign}),
        retention_store=None,
        local_transport=transport,
    )
    resolution = application.state.generation_provider
    outcomes: list[str] = []
    if mode == PROVIDER_LOCAL:
        if resolution.provider != PROVIDER_LOCAL or resolution.gemini is None:
            raise MeasurementError("local_provider_blocked")
        recorder = lambda event, **fields: outcomes.append(str(fields.get("outcome")))  # noqa: E731
        application.state.generation_provider = replace(
            resolution, gemini=replace(resolution.gemini, log=recorder)
        )
    elif resolution.provider != "extractive":
        raise MeasurementError("extractive_provider_not_resolved")

    documents = inputs["documents"]
    application.dependency_overrides[get_corpus_documents] = lambda: documents
    application.dependency_overrides[get_as_of_date] = lambda: args.as_of
    application.dependency_overrides[get_active_campaign] = lambda: args.active_campaign
    application.dependency_overrides[get_retrieval_k] = lambda: args.k
    with TestClient(application) as client:
        timed = TimedClient(client, outcomes)
        report = evaluate(
            inputs["cases"], timed, inputs["catalog"], inputs["passages"], args.k,
            coverage=inputs["coverage"],
        )
    rows = report["case_rows"]
    for row, measured in zip(rows, timed.records):
        row["response_sha256"] = measured["response_sha256"]
    return {
        "rows": rows,
        "aggregates": aggregates(report),
        "records": [
            {"id": row["id"], "seconds": measured["seconds"], "outcome": measured["outcome"]}
            for row, measured in zip(rows, timed.records)
        ],
    }


def aggregates(report: Mapping[str, Any]) -> dict:
    rows = report["case_rows"]
    answered = [row for row in rows if row["expected_status"] == "answered"]
    return {
        "cases": report["cases"],
        "expected_state_agreement": report["expected_state_agreement"],
        "answered_cases": report["answered_cases"],
        "expected_answer_coverage": report["expected_answer_coverage"],
        "source_citation_agreement": report["source_citation_agreement"],
        "passage_agreement": sum(row["passage_match"] for row in answered),
        "critical_fact_matches": report["critical_fact_matches"],
        "abstention_cases": report["abstention_cases"],
        "abstentions_kept": sum(
            row["expected_status"] == "abstained" and row["actual_status"] == "abstained" for row in rows
        ),
        "unexpected_answers": report["unexpected_answers"],
        "clarification_cases": report["clarification_cases"],
        "clarification_outcomes": report["clarification_outcomes"],
    }


def _metric_summaries(metrics: Sequence[Mapping[str, int]]) -> dict:
    eval_counts = [item["eval_count"] for item in metrics if "eval_count" in item]
    rates = [
        item["eval_count"] / (item["eval_duration"] / 1e9)
        for item in metrics
        if item.get("eval_duration") and "eval_count" in item
    ]
    loads = [item["load_duration"] / 1e9 for item in metrics if "load_duration" in item]
    prompts = [item["prompt_eval_count"] for item in metrics if "prompt_eval_count" in item]
    return {
        "eval_count": summarize_latencies(eval_counts),
        "prompt_eval_count": summarize_latencies(prompts),
        "tokens_per_second": summarize_latencies(rates),
        "ollama_load_seconds": summarize_latencies(loads),
    }


# --- Entry point ----------------------------------------------------------------------


def _parse(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--active-campaign", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD_PATH)
    return parser.parse_args(argv)


def _preflight(probe: OllamaProbe, record: LocalModelRecord) -> dict:
    try:
        version = probe.call("/api/version", timeout=PROBE_TIMEOUT_SECONDS)
        tags = probe.call("/api/tags", timeout=PROBE_TIMEOUT_SECONDS)
    except Exception:  # noqa: BLE001
        raise MeasurementError("ollama_unreachable") from None
    entry = next(
        (
            item
            for item in tags.get("models") or []
            if isinstance(item, dict) and record.model in (item.get("name"), item.get("model"))
        ),
        None,
    )
    if entry is None:
        raise MeasurementError("model_not_found")
    if entry.get("digest") != record.digest:
        raise MeasurementError("model_digest_mismatch")
    return {"ollama_version": version.get("version"), "size_bytes": entry.get("size")}


def _load_inputs(args: argparse.Namespace) -> dict:
    try:
        if not 1 <= args.k <= 100 or not 1 <= args.repeats <= 10:
            raise ValueError("arguments")
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
    except Exception:  # noqa: BLE001
        raise MeasurementError("input_invalid") from None
    return {
        "catalog": catalog,
        "passages": passages,
        "cases": cases,
        "coverage": coverage,
        "documents": CorpusDocuments(catalog=catalog, passages=passages),
    }


def measure(args: argparse.Namespace, opener: Any) -> tuple[int, dict]:
    today = datetime.now(timezone.utc).date()
    _, record = evaluate_local_model_record(load_local_model_record(args.record), as_of=today)
    if record is None:
        raise MeasurementError("model_record_invalid")
    probe = OllamaProbe(opener)
    server = _preflight(probe, record)
    inputs = _load_inputs(args)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    started = time.perf_counter()

    extractive = run_mode("extractive", record, args, inputs)

    sampler = MemorySampler(probe, record.model)
    sampler.start()
    try:
        cold_load = cold_load_seconds(probe, record)
        unload(probe, record.model)  # repeat 1 starts cold
        repeats = []
        for index in range(1, args.repeats + 1):
            metrics: list = []
            transport = TimedTransport(
                OllamaTransport(record, opener=opener, on_metrics=metrics.append)
            )
            result = run_mode(PROVIDER_LOCAL, record, args, inputs, transport)
            repeats.append((index, result, transport, metrics))
    finally:
        sampler.stop()

    repeat_reports = []
    for index, result, transport, metrics in repeats:
        counts = Counter(item["outcome"] for item in result["records"] if item["outcome"] is not None)
        repeat_reports.append(
            {
                "repeat": index,
                "ask_seconds": summarize_latencies(item["seconds"] for item in result["records"]),
                "send_seconds": summarize_latencies(transport.seconds),
                "drafting_invocations": sum(counts.values()),
                "outcomes": dict(sorted(counts.items())),
                "verified_draft_rate": verified_draft_rate(counts),
                "aggregates": result["aggregates"],
                "changed_case_ids": changed_case_ids(extractive["rows"], result["rows"]),
                "case_outcomes": {
                    item["id"]: item["outcome"] or NOT_DRAFTED for item in result["records"]
                },
                **_metric_summaries(metrics),
            }
        )

    first = repeats[0][1]["records"] if repeats else []
    cold_case = next((item for item in first if item["outcome"] is not None), None)
    total_counts: Counter = Counter()
    for report in repeat_reports:
        total_counts.update(report["outcomes"])
    all_local = [item["seconds"] for _, result, _, _ in repeats for item in result["records"]]
    warm_local = [
        item["seconds"]
        for index, result, _, _ in repeats
        for item in result["records"]
        if not (index == 1 and cold_case is not None and item is cold_case)
    ]
    within = budget_check(sampler.peaks)
    report = {
        "schema": REPORT_SCHEMA,
        "started_at": started_at,
        "total_seconds": _round(time.perf_counter() - started),
        "model": record.model,
        "digest": record.digest,
        "record_size_bytes": record.size_bytes,
        "tags_size_bytes": server["size_bytes"],
        "ollama_version": server["ollama_version"],
        "limits": {
            "timeout_seconds": record.timeout_seconds,
            "max_output_tokens": record.max_output_tokens,
            "num_ctx": record.num_ctx,
            "keep_alive_seconds": record.keep_alive_seconds,
        },
        "as_of": args.as_of.isoformat(),
        "active_campaign": args.active_campaign,
        "k": args.k,
        "repeats": args.repeats,
        "cases": len(inputs["cases"]),
        "cold_start": {
            "cold_load_seconds": _round(cold_load),
            "first_drafting_case_id": cold_case["id"] if cold_case else None,
            "first_drafting_case_ask_seconds": _round(cold_case["seconds"]) if cold_case else None,
            "first_drafting_case_outcome": cold_case["outcome"] if cold_case else None,
        },
        "extractive": {
            "ask_seconds": summarize_latencies(item["seconds"] for item in extractive["records"]),
            "aggregates": extractive["aggregates"],
        },
        "local": {
            "ask_seconds_all": summarize_latencies(all_local),
            "ask_seconds_excluding_cold_case": summarize_latencies(warm_local),
            "outcomes_total": dict(sorted(total_counts.items())),
            "verified_draft_rate_total": verified_draft_rate(total_counts),
            "outcomes_identical_across_repeats": len(
                {json.dumps(item["case_outcomes"], sort_keys=True) for item in repeat_reports}
            ) <= 1,
            "changed_case_ids_identical_across_repeats": len(
                {json.dumps(item["changed_case_ids"], sort_keys=True) for item in repeat_reports}
            ) <= 1,
            "runs": repeat_reports,
        },
        "memory": {
            "budget_bytes": MEMORY_BUDGET_BYTES,
            **sampler.peaks,
            "samples": sampler.samples,
            "within_budget": within,
        },
        "quality_metrics_are_report_only": True,
    }
    return (0 if within else 1), report


def main(argv: Optional[Sequence[str]] = None, *, opener: Any = None) -> int:
    args = _parse(argv)
    saved = {key: os.environ.get(key) for key in (GENERATION_PROVIDER_ENV, LOCAL_MODEL_ENV, GEMINI_MODEL_ENV)}
    try:
        code, report = measure(args, opener if opener is not None else loopback_opener())
    except MeasurementError as error:
        print(f"error: {error.code}", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - never print a trace or any text
        print(f"error: measurement_failed ({type(error).__name__})", file=sys.stderr)
        return 2
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
