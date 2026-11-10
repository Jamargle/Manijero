"""Measure what a minimum BM25 score would change, without changing ``/ask``.

The sweep scores the approved golden and trap items through the in-process ``/ask``
pipeline twice: first **today's plain BM25 search**, then an evaluation-only ranker that
keeps only lexical candidates with ``score >= threshold``. It reports, for each threshold
in a fixed 0.5 grid, how many golden questions still find their right source and how many
traps are correctly refused. Nothing here is composed into the service, and the ``/ask``
default is unchanged.

Definitions (rows are :func:`app.answer_eval.evaluate` rows):

* *right source found*: expected ``answered``, actual ``answered``, and ``source_match``;
* *golden broken*: a golden question that passes today and does not at this threshold
  (the :func:`app.reranker_measure.compare` definition);
* *trap worse*: with the threshold, ``expected_state_match`` goes true to false, the
  abstention reason stops matching, or ``must_not_say`` grows (the same definition);
* *correct trap abstention*: expected ``abstained``, actually ``abstained``, and
  ``abstention_reason_match`` true.

The recommendation rule is fixed and recorded in the report. The command
(``backend/scripts/calibrate_retrieval_threshold.py``) supplies the reviewed paths, the
approved-only loaders, and the two output files.

This module imports no review tooling that reads the golden queue directly and is never
imported by ``app.main``. It imports no model, embedding, vector-store, or network client.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi.testclient import TestClient

from app import trap_set
from app.answer_eval import evaluate
from app.ask_api import (
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.main import create_app
from app.pilot_config import load_config
from app.reranker_measure import _measurement_environment, compare
from app.retrieval_backend import Bm25Backend, get_retrieval_backend

GRID_STEP = 0.5
MAX_GRID_ROWS = 200
COOPERATIVE_FOLLOW_UP: Tuple[str, ...] = ("trap-013", "trap-014", "trap-016")

CASE_SET_GOLDEN = "golden"
CASE_SET_TRAP = "trap"

RULE_TEXT = (
    "eligible when no golden question breaks, no trap question gets worse, and golden "
    "right sources do not drop below today's count; among eligible thresholds the most "
    "correct trap abstentions wins, ties go to the smallest threshold, and otherwise "
    "today's 0.0 is kept"
)

LINE_ZERO_MISMATCH = (
    "Result: the threshold sweep stopped because the zero threshold did not reproduce "
    "today's answers."
)
LINE_GRID_TOO_WIDE = (
    "Result: the threshold sweep stopped because the score range is too wide for the "
    "fixed 0.5 step."
)
LINE_COOPERATIVE_MISSING = (
    "Result: the threshold sweep stopped because a cooperative follow-up trap is missing "
    "or not approved."
)
LINE_OUT_INSIDE_KNOWLEDGE = (
    "error: --out must be outside knowledge/ so the reviewed corpus is never written."
)

# Repository ``knowledge/``; only the ``--out`` guard reads it, and tests may replace it.
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"


class SweepStop(Exception):
    """The sweep cannot finish; ``line`` is the one line to print and ``exit_code`` its code."""

    def __init__(self, line: str, exit_code: int = 1) -> None:
        super().__init__(line)
        self.line = line
        self.exit_code = exit_code


@dataclass(frozen=True)
class SweepInputs:
    """The reviewed files and run settings (the command fills these in)."""

    catalog: Path
    passages: Path
    cases: Path
    golden: Path
    traps: Path
    active_campaign: str
    as_of: date
    k: int = 5


@dataclass(frozen=True)
class SweepOutcome:
    """The process result, plus the two documents when the sweep completed."""

    exit_code: int
    line: str
    report: Optional[Dict[str, Any]] = None
    table: Optional[str] = None


@dataclass(frozen=True)
class Recommendation:
    """The chosen threshold and its full report row."""

    threshold: float
    row: Mapping[str, Any]

    @property
    def rule(self) -> str:
        return RULE_TEXT


class MinScoreRanker:
    """Keep only lexical candidates at or above a minimum score, order unchanged.

    It never adds, reorders, or rescores a candidate. ``take()`` returns the largest
    lexical score seen since the previous call and resets the recording, so one question
    can search more than once without inflating its top score.
    """

    def __init__(self, threshold: float) -> None:
        self.threshold = float(threshold)
        self._tops: List[float] = []

    def rank(
        self, question: str, lexical: Tuple[Tuple[str, float], ...]
    ) -> Tuple[Tuple[str, float], ...]:
        if lexical:
            self._tops.append(float(lexical[0][1]))
        return tuple(
            (passage_id, score)
            for passage_id, score in lexical
            if float(score) >= self.threshold
        )

    def take(self) -> Optional[float]:
        """The largest lexical score since the previous ``take()``, or ``None``."""

        top = max(self._tops) if self._tops else None
        self._tops.clear()
        return top


class ThresholdBackend:
    """A BM25 backend whose attached retriever composes the evaluation-only ranker."""

    def __init__(self, threshold: float) -> None:
        self.threshold = float(threshold)
        self.ranker = MinScoreRanker(self.threshold)

    @property
    def mode(self) -> str:
        return "bm25"

    def attach(self, retriever: Any, active_campaign: Optional[str]) -> Any:
        return retriever.with_ranker(self.ranker)


def grid(top_scores: Sequence[Optional[float]]) -> Tuple[float, ...]:
    """The fixed grid: 0.0, 0.5, ... through the first step strictly above the largest score."""

    present = [float(score) for score in top_scores if score is not None]
    if not present:
        return (0.0,)
    steps = math.floor(max(present) / GRID_STEP) + 1
    return tuple(round(index * GRID_STEP, 10) for index in range(steps + 1))


def _found(row: Mapping[str, Any]) -> bool:
    return (
        row["expected_status"] == "answered"
        and row["actual_status"] == "answered"
        and bool(row["source_match"])
    )


def _abstained(row: Mapping[str, Any]) -> bool:
    return row["actual_status"] == "abstained"


def _changed(row: Mapping[str, Any]) -> Tuple[Any, ...]:
    """Everything a threshold can change about one scored question."""

    return (
        row["actual_status"],
        bool(row["source_match"]),
        bool(row["expected_state_match"]),
        row.get("abstention_reason_match"),
        tuple(row.get("must_not_say_found", [])),
    )


def changed_ids(
    baseline_rows: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> List[str]:
    """The ids whose scored state differs from today, sorted by id."""

    after = {row["id"]: row for row in rows}
    if len(after) != len(rows):
        raise ValueError("rows must cover each question once")
    return sorted(
        row["id"]
        for row in baseline_rows
        if row["id"] not in after or _changed(row) != _changed(after[row["id"]])
    )


def row_metrics(
    baseline_rows: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """The per-threshold counts, using :func:`app.reranker_measure.compare` for broken/worse."""

    comparison = compare(baseline_rows, rows, {})
    golden = [row for row in rows if row["case_set"] == CASE_SET_GOLDEN]
    traps = [row for row in rows if row["case_set"] == CASE_SET_TRAP]
    return {
        "golden": {
            "answered": sum(row["actual_status"] == "answered" for row in golden),
            "right_source_found": sum(_found(row) for row in golden),
            "correct_abstentions": sum(
                row["expected_status"] == "abstained" and _abstained(row) for row in golden
            ),
            "broken": comparison.broken,
        },
        "traps": {
            "correct_abstentions": sum(
                row["expected_status"] == "abstained"
                and _abstained(row)
                and row.get("abstention_reason_match") is True
                for row in traps
            ),
            "unexpected_answers": sum(
                row["expected_status"] != "answered" and row["actual_status"] == "answered"
                for row in traps
            ),
            "right_source_found": sum(_found(row) for row in traps),
            "must_not_say_hits": sum(
                len(row.get("must_not_say_found", [])) for row in traps
            ),
            "worse": comparison.trap_worse,
        },
        "changed_ids": changed_ids(baseline_rows, rows),
    }


def ineligible_reason(
    row: Mapping[str, Any], baseline: Mapping[str, Any]
) -> Optional[str]:
    """One plain line for why a row is not eligible; ``None`` when it is eligible."""

    reasons: List[str] = []
    lost = baseline["golden"]["right_source_found"] - row["golden"]["right_source_found"]
    if lost > 0:
        reasons.append(
            "loses {} golden right source{}".format(lost, "" if lost == 1 else "s")
        )
    broken = row["golden"]["broken"]
    if broken:
        reasons.append(
            "breaks {} golden question{}".format(broken, "" if broken == 1 else "s")
        )
    worse = row["traps"]["worse"]
    if worse:
        reasons.append(
            "makes {} trap question{} worse".format(worse, "" if worse == 1 else "s")
        )
    return "; ".join(reasons) or None


def recommend(rows: Sequence[Mapping[str, Any]]) -> Recommendation:
    """The eligible threshold with the most trap correct abstentions; ties to the smallest."""

    if not rows:
        raise ValueError("the grid must hold at least the 0.0 row")
    baseline = rows[0]
    best: Optional[Mapping[str, Any]] = None
    for row in rows:
        if ineligible_reason(row, baseline) is not None:
            continue
        if baseline["traps"]["correct_abstentions"] <= row["traps"]["correct_abstentions"]:
            if (
                best is None
                or row["traps"]["correct_abstentions"]
                > best["traps"]["correct_abstentions"]
            ):
                best = row
    chosen = baseline if best is None else best
    if chosen["traps"]["correct_abstentions"] <= baseline["traps"]["correct_abstentions"]:
        chosen = baseline
    return Recommendation(float(chosen["threshold"]), chosen)


def _state(row: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "state": row["actual_status"],
        "reason": row.get("actual_abstention_reason"),
    }


def cooperative_outcome(
    rows_by_threshold: Mapping[float, Sequence[Mapping[str, Any]]],
    top_scores: Mapping[str, Optional[float]],
    recommended_threshold: float,
    ids: Sequence[str] = COOPERATIVE_FOLLOW_UP,
) -> List[Dict[str, Any]]:
    """State and reason today and at the recommended value, plus the first safe abstention."""

    ordered = sorted(rows_by_threshold)
    zero_by_id = {row["id"]: row for row in rows_by_threshold[ordered[0]]}
    recommended_by_id = {
        row["id"]: row for row in rows_by_threshold[recommended_threshold]
    }
    outcomes: List[Dict[str, Any]] = []
    for ident in ids:
        baseline_row = zero_by_id.get(ident)
        if baseline_row is None:
            raise ValueError("cooperative trap {} is not in the scored rows".format(ident))
        first: Optional[Dict[str, Any]] = None
        for threshold in ordered:
            by_id = {candidate["id"]: candidate for candidate in rows_by_threshold[threshold]}
            row = by_id.get(ident)
            if row is None:
                continue
            if _abstained(row) and row.get("abstention_reason_match") is True:
                golden = [
                    candidate
                    for candidate in rows_by_threshold[threshold]
                    if candidate["case_set"] == CASE_SET_GOLDEN
                ]
                first = {
                    "threshold": threshold,
                    "golden_right_source_found": sum(_found(candidate) for candidate in golden),
                }
                break
        outcomes.append(
            {
                "id": ident,
                "top_score": top_scores.get(ident),
                "today": _state(baseline_row),
                "recommended": _state(recommended_by_id[ident]),
                "first_acceptable_abstention": first,
            }
        )
    return outcomes


def _cell(value: Any) -> str:
    return "-" if value is None else str(value)


def _state_cell(state: Mapping[str, Any]) -> str:
    value = str(state["state"])
    if state.get("reason"):
        return "{} ({})".format(value, state["reason"])
    return value


def _threshold_row_line(row: Mapping[str, Any], note: str) -> str:
    golden = row["golden"]
    traps = row["traps"]
    return "| {t:.1f} | {ga} | {gs} | {gc} | {gb} | {tc} | {tu} | {ts} | {tm} | {tw} | {note} |".format(
        t=float(row["threshold"]),
        ga=golden["answered"],
        gs=golden["right_source_found"],
        gc=golden["correct_abstentions"],
        gb=golden["broken"],
        tc=traps["correct_abstentions"],
        tu=traps["unexpected_answers"],
        ts=traps["right_source_found"],
        tm=traps["must_not_say_hits"],
        tw=traps["worse"],
        note=note,
    )


def table_markdown(report: Mapping[str, Any]) -> str:
    """The short Markdown table: the ends, every changed count, and the recommendation."""

    rows = report["thresholds"]
    recommendation = report["recommendation"]
    chosen = recommendation["threshold"]
    selected = {0, len(rows) - 1}
    previous: Optional[Mapping[str, Any]] = None
    for index, row in enumerate(rows):
        signature = (row["golden"], row["traps"])
        if previous is not None and signature != previous:
            selected.add(index)
        previous = signature
    for index, row in enumerate(rows):
        if float(row["threshold"]) == float(chosen):
            selected.add(index)

    lines = [
        "# Retrieval threshold trade-off (report only; /ask default unchanged)",
        "| t | G ans | G src | G abst | G broken | T abst | T unexp | T src | T must-not | T worse | note |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for index in sorted(selected):
        row = rows[index]
        if float(row["threshold"]) == float(chosen):
            note = "recommended"
        elif row.get("not_eligible_reason"):
            note = row["not_eligible_reason"]
        else:
            note = "eligible"
        lines.append(_threshold_row_line(row, note))

    lines.extend(
        [
            "",
            "## Cooperative-practice traps",
            "",
            "| id | top score | today | at {:.1f} | first acceptable abstention | golden src then |".format(
                float(chosen)
            ),
            "|---|---|---|---|---|---|",
        ]
    )
    for item in report["cooperative_follow_up"]:
        today = _state_cell(item["today"])
        at_recommended = _state_cell(item["recommended"])
        first = item["first_acceptable_abstention"]
        first_text = "never in the grid" if first is None else "{:.1f}".format(first["threshold"])
        first_golden = "-" if first is None else _cell(first["golden_right_source_found"])
        top = item["top_score"]
        top_text = "-" if top is None else "{:.3f}".format(float(top))
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                item["id"],
                top_text,
                today,
                at_recommended,
                first_text,
                first_golden,
            )
        )
    return "\n".join(lines) + "\n"


# --- Run ---------------------------------------------------------------------------------------


def _out_inside_knowledge(out: Path) -> bool:
    resolved = Path(out).resolve()
    root = Path(KNOWLEDGE_ROOT).resolve()
    return resolved == root or root in resolved.parents


def _run_pass(
    label: str,
    backend: Any,
    cases: Sequence[Dict[str, Any]],
    catalog: Any,
    passages: Any,
    inputs: SweepInputs,
    out: Callable[[str], None],
) -> Tuple[List[Dict[str, Any]], Dict[str, Optional[float]]]:
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
    top_scores: Dict[str, Optional[float]] = {}
    ranker = getattr(backend, "ranker", None)
    total = len(cases)
    with TestClient(application) as client:
        for number, case in enumerate(cases, start=1):
            if ranker is not None:
                ranker.take()
            report = evaluate(
                [case], client, catalog, passages, inputs.k, row_extra=trap_set.row_extra
            )
            rows.append(dict(report["case_rows"][0], case_set=case["case_set"]))
            top_scores[case["id"]] = ranker.take() if ranker is not None else None
            out("Scored question {} of {}".format(number, total))
    return rows, top_scores


def run_sweep(
    inputs: SweepInputs,
    cases_loader: Callable[[SweepInputs], Tuple[Any, Any, List[Dict[str, Any]]]],
    out: Path,
    out_line: Callable[[str], None] = print,
) -> SweepOutcome:
    """Run the baseline, zero-row identity check, and grid; return the report and table.

    ``cases_loader`` returns ``(catalog, passages, cases)``: the approved golden items
    then the approved trap items, each tagged with ``case_set``. The command supplies it
    because reading the golden set is review tooling that this module must not import.
    Input errors propagate to the command, which maps them to exit 2.
    """

    if _out_inside_knowledge(out):
        return SweepOutcome(2, LINE_OUT_INSIDE_KNOWLEDGE)
    try:
        catalog, passages, cases = cases_loader(inputs)
        if not cases:
            raise ValueError("the sweep needs at least one approved item")
        golden_count = sum(case["case_set"] == CASE_SET_GOLDEN for case in cases)
        trap_count = sum(case["case_set"] == CASE_SET_TRAP for case in cases)
        trap_ids = {case["id"] for case in cases if case["case_set"] == CASE_SET_TRAP}
        missing = [ident for ident in COOPERATIVE_FOLLOW_UP if ident not in trap_ids]
        if missing:
            raise SweepStop(LINE_COOPERATIVE_MISSING)

        with _measurement_environment(inputs.active_campaign):
            out_line("Pass 1: today's plain BM25 search")
            baseline_rows, _ = _run_pass(
                "Baseline", Bm25Backend(), cases, catalog, passages, inputs, out_line
            )
            zero_backend = ThresholdBackend(0.0)
            zero_rows, top_scores = _run_pass(
                "Threshold 0.0", zero_backend, cases, catalog, passages, inputs, out_line
            )

        baseline_by_id = {row["id"]: row for row in baseline_rows}
        zero_by_id = {row["id"]: row for row in zero_rows}
        if set(baseline_by_id) != set(zero_by_id):
            raise SweepStop(LINE_ZERO_MISMATCH)
        if any(baseline_by_id[ident] != zero_by_id[ident] for ident in baseline_by_id):
            raise SweepStop(LINE_ZERO_MISMATCH)

        thresholds = grid(list(top_scores.values()))
        if len(thresholds) > MAX_GRID_ROWS:
            raise SweepStop(LINE_GRID_TOO_WIDE)

        rows_by_threshold: Dict[float, List[Dict[str, Any]]] = {0.0: zero_rows}
        for threshold in thresholds[1:]:
            backend = ThresholdBackend(threshold)
            with _measurement_environment(inputs.active_campaign):
                rows, _ = _run_pass(
                    "Threshold {:.1f}".format(threshold),
                    backend,
                    cases,
                    catalog,
                    passages,
                    inputs,
                    out_line,
                )
            rows_by_threshold[threshold] = rows

        report_rows: List[Dict[str, Any]] = []
        for threshold in thresholds:
            metrics = row_metrics(baseline_rows, rows_by_threshold[threshold])
            report_rows.append(dict(metrics, threshold=threshold))
        baseline_row = report_rows[0]
        for row in report_rows:
            row["not_eligible_reason"] = ineligible_reason(row, baseline_row)

        recommendation = recommend(report_rows)
        cooperative = cooperative_outcome(
            rows_by_threshold,
            top_scores,
            recommendation.threshold,
        )
        report: Dict[str, Any] = {
            "schema_version": "retrieval-threshold-calibration-v1",
            "report_only": True,
            "default_changed": False,
            "active_campaign": inputs.active_campaign,
            "k": inputs.k,
            "grid_step": GRID_STEP,
            "counts": {"golden": golden_count, "traps": trap_count},
            "thresholds": report_rows,
            "recommendation": {
                "rule": RULE_TEXT,
                "threshold": recommendation.threshold,
                "keeps_today": recommendation.threshold == 0.0,
                "row": recommendation.row,
            },
            "cooperative_follow_up": cooperative,
        }
        table = table_markdown(report)
    except SweepStop as stop:
        return SweepOutcome(stop.exit_code, stop.line)

    line = (
        "Result: threshold sweep over {g} golden and {t} trap questions at {n} thresholds. "
        "Recommended minimum search score: {x:.1f} (today 0.0). The /ask default is unchanged."
    ).format(
        g=golden_count,
        t=trap_count,
        n=len(thresholds),
        x=recommendation.threshold,
    )
    return SweepOutcome(0, line, report, table)
