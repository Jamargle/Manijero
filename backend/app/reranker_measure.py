"""Measure whether the local reranker helps, and apply the owner's on/off rule.

The measurement runs the approved golden items and the approved trap items through the
in-process ``/ask`` path twice over the same prepared corpus: **today's hybrid search**
(what the owner's local service runs), then **the reranker wrapping that same hybrid
backend**. Both runs use the reviewed glossary and extractive drafting, the answer cache
off, and today's date. Nothing is printed except counts and timings.

Owner rule (decision 3, 2026-11-10): the reranker is switched on only if at least
``MIN_GOLDEN_GAIN`` more golden questions find their right source than with today's search,
no trap question gets worse, no golden question that passes today breaks, and the reranker
adds no more than ``MAX_EXTRA_SECONDS`` seconds to one answer. The verdict is the owner's
on/off rule for this Mac and these reviewed sets, not a quality claim.

Definitions (rows are :func:`app.answer_eval.evaluate` rows):

* *right source found*: expected ``answered``, actual ``answered``, and ``source_match``;
* *passes*: ``expected_state_match`` and ``source_match``;
* *broken*: a golden question that passes today and does not with the reranker;
* *trap worse*: with the reranker ``expected_state_match`` goes true to false,
  ``abstention_reason_match`` goes true to false, or ``must_not_say_found`` grows;
* *extra time*: seconds spent inside the reranker for one question.

This module imports neither the operator modules nor the golden-set review tooling; the command
(``backend/scripts/reranker.py``) supplies the paths, the loaders, and the printing.
"""

from __future__ import annotations

import contextlib
import math
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from fastapi.testclient import TestClient

from app import trap_set
from app.answer_eval import evaluate
from app.ask_api import (
    CorpusDocuments,
    _prepare_runtime_corpus,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.main import create_app
from app.pilot_config import load_config
from app.reranker import MAX_MODEL_BYTES, RerankerBackend, RerankerSettings, RerankScorer
from app.retrieval_backend import get_retrieval_backend

MIN_GOLDEN_GAIN = 2
MAX_EXTRA_SECONDS = 2.0
__all__ = ["MAX_MODEL_BYTES", "MIN_GOLDEN_GAIN", "MAX_EXTRA_SECONDS"]

CASE_SET_GOLDEN = "golden"
CASE_SET_TRAP = "trap"

REASON_FEW_GAIN = "fewer than 2 more golden questions found their right source"
REASON_BROKEN = "a golden question that worked today broke"
REASON_TRAP_WORSE = "a trap question got worse"
REASON_SLOW = "slower than 2 extra seconds"

LINE_NOT_READY = (
    "Result: the reranker was not measured because today's hybrid search is not ready. "
    "Run ./scripts/init.sh --local-rag-setup, then measure again."
)
LINE_NO_VECTOR = (
    "Result: the reranker was not measured because today's hybrid search did not run for every "
    "question. Run ./scripts/init.sh --local-rag-setup, then measure again."
)
LINE_NO_MODEL = (
    "Result: the reranker was not measured because its model is missing or does not match the "
    "reviewed copy. Run ./scripts/init.sh --reranker-download, then measure again."
)
LINE_RERANK_FAILED = (
    "Result: the reranker was not measured because it could not score every question. Run "
    "./scripts/init.sh --reranker-download to check the model, then measure again; if it happens "
    "again, send the log file to the developer."
)
LINE_INPUTS = (
    "Result: the reranker was not measured because the reviewed question files could not be "
    "read. Send this line to the developer."
)
LINE_INTERNAL = "Result: the reranker measurement stopped on an unexpected problem. {detail}"


class MeasureStop(Exception):
    """The measurement cannot give a verdict; ``line`` is the one ``Result:`` line to print."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.line = line


# --- The rule --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    """Counts and the slowest extra time; the verdict follows from these only."""

    golden: int
    traps: int
    found_baseline: int
    found_reranked: int
    broken: int
    trap_worse: int
    slowest_extra_seconds: float

    @property
    def gain(self) -> int:
        return self.found_reranked - self.found_baseline


def _found(row: Mapping[str, Any]) -> bool:
    return (
        row["expected_status"] == "answered"
        and row["actual_status"] == "answered"
        and bool(row["source_match"])
    )


def _passes(row: Mapping[str, Any]) -> bool:
    return bool(row["expected_state_match"]) and bool(row["source_match"])


def _trap_got_worse(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    if before["expected_state_match"] and not after["expected_state_match"]:
        return True
    if before.get("abstention_reason_match") is True and after.get("abstention_reason_match") is not True:
        return True
    return len(after.get("must_not_say_found", [])) > len(before.get("must_not_say_found", []))


def compare(
    baseline_rows: Sequence[Mapping[str, Any]],
    reranked_rows: Sequence[Mapping[str, Any]],
    timings: Mapping[str, float],
) -> Comparison:
    """Pair the two runs by question id and count what the owner's rule needs.

    Every row carries ``id`` and ``case_set`` (``golden`` or ``trap``). ``timings`` maps a
    question id to the seconds the reranker spent on it.
    """

    after = {row["id"]: row for row in reranked_rows}
    if len(after) != len(reranked_rows) or {row["id"] for row in baseline_rows} != set(after):
        raise ValueError("the two runs must cover the same questions")
    golden = traps = found_before = found_after = broken = worse = 0
    for before in baseline_rows:
        row = after[before["id"]]
        if before["case_set"] == CASE_SET_GOLDEN:
            golden += 1
            found_before += _found(before)
            found_after += _found(row)
            broken += _passes(before) and not _passes(row)
        else:
            traps += 1
            worse += _trap_got_worse(before, row)
    slowest = max((float(value) for value in timings.values()), default=0.0)
    return Comparison(
        golden=golden,
        traps=traps,
        found_baseline=found_before,
        found_reranked=found_after,
        broken=broken,
        trap_worse=worse,
        slowest_extra_seconds=slowest,
    )


def verdict(comparison: Comparison) -> Tuple[bool, Tuple[str, ...]]:
    """``(switch_on, reasons)``; reasons are in the fixed order and empty when it is ON."""

    reasons: List[str] = []
    if comparison.gain < MIN_GOLDEN_GAIN:
        reasons.append(REASON_FEW_GAIN)
    if comparison.broken > 0:
        reasons.append(REASON_BROKEN)
    if comparison.trap_worse > 0:
        reasons.append(REASON_TRAP_WORSE)
    if comparison.slowest_extra_seconds > MAX_EXTRA_SECONDS:
        reasons.append(REASON_SLOW)
    return (not reasons, tuple(reasons))


def result_line(comparison: Comparison) -> str:
    """The one line the owner sends to the developer."""

    switch_on, reasons = verdict(comparison)
    head = (
        "Result: reranker measured on {g} golden and {t} trap questions against today's hybrid "
        "search. Right source found: {b} today, {r} with the reranker ({d:+d}). Golden questions "
        "broken: {x}. Trap questions worse: {y}. Slowest extra time: {s:.1f} seconds. "
    ).format(
        g=comparison.golden,
        t=comparison.traps,
        b=comparison.found_baseline,
        r=comparison.found_reranked,
        d=comparison.gain,
        x=comparison.broken,
        y=comparison.trap_worse,
        s=comparison.slowest_extra_seconds,
    )
    if switch_on:
        return head + "Verdict: ON - it met all the rules. Send this line to the developer."
    return (
        head
        + "Verdict: OFF - {}. It stays off and this result is kept as a recorded experiment. "
        "Send this line to the developer.".format("; ".join(reasons))
    )


# --- Run ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MeasureInputs:
    """The reviewed files and the run settings (the command fills these in)."""

    catalog: Path
    passages: Path
    cases: Path
    golden: Path
    traps: Path
    active_campaign: str
    as_of: date
    k: int = 5


@dataclass(frozen=True)
class MeasureOutcome:
    exit_code: int
    line: str
    comparison: Optional[Comparison] = None


class TimedScorer:
    """Wraps the real scorer: adds up the seconds per question and flags a bad answer."""

    def __init__(self, inner: RerankScorer, clock: Callable[[], float]) -> None:
        self._inner = inner
        self._clock = clock
        self._seconds = 0.0
        self.bad_calls = 0

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        started = self._clock()
        try:
            scores = tuple(self._inner.score(query, texts))
        except Exception:
            self.bad_calls += 1
            raise
        finally:
            self._seconds += max(0.0, self._clock() - started)
        if len(scores) != len(texts) or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            for value in scores
        ):
            self.bad_calls += 1
        return scores

    def take(self) -> float:
        seconds, self._seconds = self._seconds, 0.0
        return seconds


class _RecordingBackend:
    """Passes a backend through and remembers whether the hybrid ranking ran or fell back."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._attached = 0
        self._ranker: Any = None

    @property
    def mode(self) -> str:
        return self._inner.mode

    def begin(self) -> None:
        self._attached = 0
        self._ranker = None

    def fell_back(self) -> bool:
        """The request reached retrieval but the hybrid ranker was absent or fell back to BM25."""

        if not self._attached:
            return False
        trace = getattr(self._ranker, "last_trace", None)
        return trace is None or trace.fallback_reason is not None

    def attach(self, retriever: Any, active_campaign: Optional[str]) -> Any:
        attached = self._inner.attach(retriever, active_campaign)
        self._attached += 1
        self._ranker = attached.current_ranker
        return attached


@contextlib.contextmanager
def _measurement_environment(campaign: str) -> Iterator[None]:
    """Extractive drafting, answer cache and trace off, for the duration of the runs only."""

    removed = (
        "MANIJERO_GENERATION_PROVIDER",
        "MANIJERO_LOCAL_MODEL",
        "MANIJERO_GEMINI_MODEL",
        "MANIJERO_ANSWER_TRACE",
        "MANIJERO_RERANKER",
    )
    keys = removed + ("MANIJERO_ANSWER_CACHE", "MANIJERO_ACTIVE_CAMPAIGN")
    saved = {key: os.environ.get(key) for key in keys}
    try:
        for key in removed:
            os.environ.pop(key, None)
        os.environ["MANIJERO_ANSWER_CACHE"] = "off"
        os.environ["MANIJERO_ACTIVE_CAMPAIGN"] = campaign
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_pass(
    label: str,
    backend: Any,
    cases: Sequence[Dict[str, Any]],
    catalog: Any,
    passages: Any,
    inputs: MeasureInputs,
    recorder: _RecordingBackend,
    timed: Optional[TimedScorer],
    out: Callable[[str], None],
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": inputs.active_campaign}),
        retention_store=None,
        answer_cache=None,
    )
    documents = CorpusDocuments(catalog=catalog, passages=passages)
    application.dependency_overrides[get_corpus_documents] = lambda: documents
    application.dependency_overrides[get_as_of_date] = lambda: inputs.as_of
    application.dependency_overrides[get_active_campaign] = lambda: inputs.active_campaign
    application.dependency_overrides[get_retrieval_k] = lambda: inputs.k
    application.dependency_overrides[get_retrieval_backend] = lambda: backend
    out(label)
    rows: List[Dict[str, Any]] = []
    timings: Dict[str, float] = {}
    total = len(cases)
    with TestClient(application) as client:
        for number, case in enumerate(cases, start=1):
            recorder.begin()
            if timed is not None:
                timed.take()
            report = evaluate(
                [case], client, catalog, passages, inputs.k, row_extra=trap_set.row_extra
            )
            if recorder.fell_back():
                raise MeasureStop(LINE_NO_VECTOR)
            row = dict(report["case_rows"][0], case_set=case["case_set"])
            rows.append(row)
            if timed is not None:
                timings[case["id"]] = timed.take()
            out("Checked question {} of {}".format(number, total))
    return rows, timings


def run_measurement(
    inputs: MeasureInputs,
    hybrid_backend: Any,
    *,
    cases_loader: Callable[[MeasureInputs], Tuple[Any, Any, List[Dict[str, Any]]]],
    reranker_ready: Callable[[], bool],
    scorer_loader: Callable[[], RerankScorer],
    settings: RerankerSettings,
    clock: Callable[[], float] = time.perf_counter,
    out: Callable[[str], None] = print,
) -> MeasureOutcome:
    """Run both passes and return the verdict line; stops with a line instead of guessing.

    ``cases_loader`` returns ``(catalog, passages, cases)``: the approved golden items then the
    approved trap items, each tagged with ``case_set`` (the command supplies it, because reading
    the golden set is review tooling that runtime modules must not import). It raises
    :class:`MeasureStop` with :data:`LINE_INPUTS` when the files cannot be read.

    Order: reviewed files, today's hybrid search is fresh for them, the reranker model
    verifies, then both models are loaded and warmed before any timing. ``hybrid_backend`` is a
    :class:`app.hybrid_retrieval.HybridBackend` (a fake in tests); the reranked pass wraps that
    same instance, so both passes share one embedder and one store.
    """

    try:
        catalog, passages, cases = cases_loader(inputs)
        documents = CorpusDocuments(catalog=catalog, passages=passages)
        try:
            retriever = _prepare_runtime_corpus(documents, inputs.as_of, inputs.active_campaign)
            status = hybrid_backend.status(retriever, inputs.active_campaign)
        except Exception:  # noqa: BLE001
            raise MeasureStop(LINE_NOT_READY) from None
        if not status.up_to_date:
            raise MeasureStop(LINE_NOT_READY)
        if not reranker_ready():
            raise MeasureStop(LINE_NO_MODEL)
        try:
            timed = TimedScorer(scorer_loader(), clock)
            timed.score("warm-up", ["warm-up one", "warm-up two"])  # loaded and warmed before timing
        except Exception:  # noqa: BLE001
            raise MeasureStop(LINE_NO_MODEL) from None
        timed.take()
        timed.bad_calls = 0

        total = len(cases)
        out("Measuring {} questions twice: with today's hybrid search, then with the reranker.".format(total))
        with _measurement_environment(inputs.active_campaign):
            recorder = _RecordingBackend(hybrid_backend)
            baseline_rows, _ = _run_pass(
                "Pass 1 of 2: today's hybrid search", recorder, cases, catalog, passages, inputs,
                recorder, None, out,
            )
            candidate = RerankerBackend(recorder, lambda: timed, settings)
            reranked_rows, timings = _run_pass(
                "Pass 2 of 2: with the reranker", candidate, cases, catalog, passages, inputs,
                recorder, timed, out,
            )
        if timed.bad_calls:
            raise MeasureStop(LINE_RERANK_FAILED)
        comparison = compare(baseline_rows, reranked_rows, timings)
    except MeasureStop as stop:
        return MeasureOutcome(1, stop.line)
    return MeasureOutcome(0, result_line(comparison), comparison)

