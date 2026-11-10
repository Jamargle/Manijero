"""Offline tests for the retrieval-threshold sweep.

The synthetic clarification corpus stands in for the reviewed knowledge: no model, no
network, no vector store, and no optional runtime. Nothing here claims retrieval quality;
the sweep is report-only and the /ask default is unchanged.
"""

import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
SCRIPT = BACKEND_ROOT / "scripts" / "calibrate_retrieval_threshold.py"

import test_hybrid_retrieval as hyb  # noqa: E402  (shares the synthetic corpus)
from app import threshold_calibration as cal  # noqa: E402
from app.abstention import Abstention, answer_or_abstain  # noqa: E402
from app.retrieval_backend import Bm25Backend  # noqa: E402

JUNTA = "fixture_clar_junta"
BOE = "fixture_clar_boe"
SECRET_WORDS = ("solicitud anual", "cooperativa paga", "riego de apoyo")

spec_cli = importlib.util.spec_from_file_location("calibrate_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec_cli)
sys.modules["calibrate_cli"] = cli  # dataclasses look the module up by name
spec_cli.loader.exec_module(cli)  # type: ignore[union-attr]


def make_case(
    identifier: str,
    question: str,
    case_set: str,
    status: str,
    sources: Sequence[str] = (),
    passages: Sequence[str] = (),
    category: str = "cooperative_practice",
) -> Dict[str, Any]:
    case: Dict[str, Any] = {
        "id": identifier,
        "area": "fixture",
        "question": question,
        "land_context": {"mode": "general", "lands": []},
        "expected_status": status,
        "case_set": case_set,
    }
    if sources:
        case["expected_source_ids"] = list(sources)
    if passages:
        case["expected_passage_ids"] = list(passages)
    if case_set == "trap":
        case.update(
            category=category,
            acceptable_abstention_reasons=["no_evidence"],
            must_not_say=[],
        )
    return case


CASES = [
    make_case(
        "g-1",
        "¿Cuándo se presenta la solicitud anual de ejemplo?",
        "golden",
        "answered",
        [JUNTA],
        ["fixture-clar-solicitud-1"],
    ),
    make_case(
        "g-2",
        "riego de apoyo en parcela de regadio",
        "golden",
        "answered",
        [BOE],
        ["fixture-clar-riego-regadio-1"],
    ),
    make_case("g-3", "pesca", "golden", "abstained"),
    # Routed before retrieval: the input screen and the year check. They must never change.
    make_case("g-4", "Mi DNI es 12345678Z, ¿qué ayuda me toca?", "golden", "abstained"),
    make_case("g-5", "¿Cuándo se presenta la solicitud de 2031?", "golden", "abstained"),
    make_case("trap-013", "¿La cooperativa paga el riego de apoyo?", "trap", "abstained"),
    make_case("trap-014", "¿La cooperativa reparte la solicitud anual?", "trap", "abstained"),
    make_case("trap-016", "¿La cooperativa decide el riego en secano?", "trap", "abstained"),
]


def inputs() -> cal.SweepInputs:
    path = Path("unused.json")
    return cal.SweepInputs(path, path, path, path, path, hyb.CAMPAIGN, hyb.AS_OF, 5)


def run(
    cases: Sequence[Dict[str, Any]] = CASES,
    out: Optional[Path] = None,
    loader: Any = None,
) -> cal.SweepOutcome:
    documents = hyb.clarification_documents()
    if loader is None:
        def loader(_inputs: cal.SweepInputs) -> Any:
            return documents.catalog, documents.passages, [dict(case) for case in cases]
    return cal.run_sweep(
        inputs(),
        loader,
        out or Path("build/unused-threshold-out"),
        out_line=lambda _line: None,
    )


def report_row(
    threshold: float,
    found: int = 10,
    broken: int = 0,
    worse: int = 0,
    traps: int = 2,
) -> Dict[str, Any]:
    return {
        "threshold": threshold,
        "golden": {
            "answered": found,
            "right_source_found": found,
            "correct_abstentions": 0,
            "broken": broken,
        },
        "traps": {
            "correct_abstentions": traps,
            "unexpected_answers": 0,
            "right_source_found": 0,
            "must_not_say_hits": 0,
            "worse": worse,
        },
        "changed_ids": [],
        "not_eligible_reason": None,
    }


def row(
    identifier: str,
    case_set: str = "golden",
    expected: str = "answered",
    actual: str = "answered",
    source: bool = True,
    state: Optional[bool] = None,
    reason: Optional[bool] = None,
    said: Sequence[str] = (),
) -> Dict[str, Any]:
    return {
        "id": identifier,
        "case_set": case_set,
        "expected_status": expected,
        "actual_status": actual,
        "source_match": source,
        "expected_state_match": (expected == actual) if state is None else state,
        "abstention_reason_match": reason,
        "must_not_say_found": list(said),
    }


# --- The ranker --------------------------------------------------------------------------------


def test_the_zero_threshold_returns_the_lexical_ranking_unchanged() -> None:
    lexical = (("a", 2.0), ("b", 1.0), ("c", 0.25))
    ranker = cal.MinScoreRanker(0.0)

    assert ranker.rank("q", lexical) == lexical
    assert ranker.take() == 2.0


def test_a_threshold_keeps_only_high_scores_in_their_original_order() -> None:
    lexical = (("a", 2.0), ("b", 1.0), ("c", 0.5))

    assert cal.MinScoreRanker(1.0).rank("q", lexical) == (("a", 2.0), ("b", 1.0))
    # The boundary is inclusive, and nothing is added or rescaled.
    assert cal.MinScoreRanker(2.0).rank("q", lexical) == (("a", 2.0),)


def test_the_recorded_top_score_resets_after_each_take() -> None:
    ranker = cal.MinScoreRanker(0.0)
    ranker.rank("q", (("a", 2.0),))
    ranker.rank("q", (("b", 3.0),))

    assert ranker.take() == 3.0
    assert ranker.take() is None


def test_all_candidates_below_the_threshold_abstain_with_no_evidence() -> None:
    retriever = hyb.clarification_retriever().with_ranker(cal.MinScoreRanker(10.0))

    result = answer_or_abstain("solicitud anual", retriever, as_of=hyb.AS_OF, k=5)

    assert isinstance(result, Abstention) and result.reason == "no_evidence"
    assert retriever.search("solicitud anual", k=5) == ()


def test_the_threshold_backend_composes_the_evaluation_ranker() -> None:
    backend = cal.ThresholdBackend(1.0)
    retriever = hyb.clarification_retriever()

    attached = backend.attach(retriever, hyb.CAMPAIGN)

    assert attached.uses_ranker and attached.current_ranker is backend.ranker
    assert retriever.uses_ranker is False


# --- Grid and counts ---------------------------------------------------------------------------


def test_the_grid_starts_at_zero_and_ends_on_the_first_step_above_the_largest_score() -> None:
    assert cal.grid([]) == (0.0,)
    assert cal.grid([None, None]) == (0.0,)
    assert cal.grid([0.4]) == (0.0, 0.5)
    assert cal.grid([2.3]) == (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)
    # A score exactly on a step still includes the next step, because the rule is "strictly above".
    assert cal.grid([2.5]) == (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)


def test_a_score_range_wider_than_the_row_budget_is_visible_before_the_sweep() -> None:
    assert len(cal.grid([100.0])) > cal.MAX_GRID_ROWS


def test_row_metrics_count_golden_and_trap_outcomes_against_today() -> None:
    baseline = [
        row("g-found"),
        row("g-wrong-source", source=False),
        row("g-abstained", expected="abstained", actual="abstained"),
        row("t-safe", case_set="trap", expected="abstained", actual="abstained", reason=True),
        row("t-answered", case_set="trap", expected="abstained"),
    ]
    changed = [
        row("g-found", actual="abstained", source=False),
        row("g-wrong-source", actual="abstained", source=False),
        row("g-abstained", expected="abstained", actual="abstained"),
        row("t-safe", case_set="trap", expected="abstained", actual="abstained", reason=True),
        row("t-answered", case_set="trap", expected="abstained", actual="abstained", reason=True),
    ]

    metrics = cal.row_metrics(baseline, changed)

    assert metrics["golden"] == {
        "answered": 0,
        "right_source_found": 0,
        "correct_abstentions": 1,
        "broken": 1,
    }
    assert metrics["traps"] == {
        "correct_abstentions": 2,
        "unexpected_answers": 0,
        "right_source_found": 0,
        "must_not_say_hits": 0,
        "worse": 0,
    }
    assert metrics["changed_ids"] == ["g-found", "g-wrong-source", "t-answered"]


def test_a_trap_reason_change_counts_as_changed_even_when_both_abstain() -> None:
    baseline = [row("t", case_set="trap", expected="abstained", actual="abstained", reason=False)]
    changed = [row("t", case_set="trap", expected="abstained", actual="abstained", reason=True)]

    assert cal.changed_ids(baseline, changed) == ["t"]
    assert cal.row_metrics(baseline, changed)["traps"]["correct_abstentions"] == 1


def test_the_ineligible_reason_names_every_failed_eligibility_rule() -> None:
    baseline = report_row(0.0, found=10)

    assert cal.ineligible_reason(report_row(1.0, found=8, broken=2, worse=1), baseline) == (
        "loses 2 golden right sources; breaks 2 golden questions; makes 1 trap question worse"
    )
    assert cal.ineligible_reason(report_row(1.0), baseline) is None


# --- Recommendation ----------------------------------------------------------------------------


def test_the_recommendation_prefers_more_correct_trap_abstentions() -> None:
    rows = [report_row(0.0, traps=2), report_row(0.5, traps=3), report_row(1.0, traps=3)]

    recommendation = cal.recommend(rows)

    assert recommendation.threshold == 0.5
    assert recommendation.row is rows[1]
    assert recommendation.rule == cal.RULE_TEXT


def test_a_lost_golden_source_a_break_or_a_worse_trap_makes_a_row_ineligible() -> None:
    rows = [
        report_row(0.0, traps=2),
        report_row(0.5, found=9, traps=5),
        report_row(1.0, broken=1, traps=5),
        report_row(1.5, worse=1, traps=5),
    ]

    assert cal.recommend(rows).threshold == 0.0


def test_the_smallest_threshold_wins_a_tie_and_zero_is_kept_without_a_gain() -> None:
    tied = [report_row(0.0, traps=2), report_row(0.5, traps=4), report_row(1.0, traps=4)]
    assert cal.recommend(tied).threshold == 0.5

    no_gain = [report_row(0.0, traps=3), report_row(0.5, traps=3)]
    assert cal.recommend(no_gain).threshold == 0.0

    all_ineligible = [report_row(0.0, traps=1), report_row(0.5, broken=1, traps=9)]
    assert cal.recommend(all_ineligible).threshold == 0.0


# --- Cooperative follow-up ---------------------------------------------------------------------


def test_the_cooperative_outcome_reports_today_the_recommendation_and_the_first_safe_stop() -> None:
    rows = {
        0.0: [
            row("g", source=True),
            row("trap-013", case_set="trap", expected="abstained", reason=False),
            row("trap-014", case_set="trap", expected="abstained", actual="abstained", reason=True),
            row("trap-016", case_set="trap", expected="abstained", reason=False),
        ],
        0.5: [
            row("g", source=True),
            row("trap-013", case_set="trap", expected="abstained", actual="abstained", reason=True),
            row("trap-014", case_set="trap", expected="abstained", actual="abstained", reason=True),
            row("trap-016", case_set="trap", expected="abstained", reason=False),
        ],
    }

    outcomes = cal.cooperative_outcome(
        rows, {"trap-013": 0.4, "trap-014": 0.2, "trap-016": 0.9}, 0.5
    )

    by_id = {item["id"]: item for item in outcomes}
    assert by_id["trap-013"]["first_acceptable_abstention"] == {
        "threshold": 0.5,
        "golden_right_source_found": 1,
    }
    assert by_id["trap-013"]["today"] == {"state": "answered", "reason": None}
    assert by_id["trap-014"]["today"] == {"state": "abstained", "reason": None}
    assert by_id["trap-016"]["first_acceptable_abstention"] is None
    assert by_id["trap-016"]["recommended"] == {"state": "answered", "reason": None}


def test_a_cooperative_trap_outside_the_scored_rows_is_refused() -> None:
    with pytest.raises(ValueError):
        cal.cooperative_outcome({0.0: [row("g")]}, {}, 0.0)


# --- The sweep and its report ------------------------------------------------------------------


def test_the_sweep_is_deterministic_and_keeps_text_and_timing_out() -> None:
    first = run()
    second = run()

    assert first.exit_code == second.exit_code == 0
    assert first.report is not None and second.report is not None
    assert json.dumps(first.report, sort_keys=True) == json.dumps(second.report, sort_keys=True)
    assert first.table == second.table
    joined = (json.dumps(first.report) + (first.table or "")).lower()
    for word in SECRET_WORDS:
        assert word not in joined
    assert "seconds" not in joined and "timing" not in joined


def test_the_sweep_reports_approved_counts_every_row_and_the_result_line() -> None:
    outcome = run()

    assert outcome.exit_code == 0
    assert outcome.report is not None and outcome.table is not None
    report = outcome.report
    assert report["schema_version"] == "retrieval-threshold-calibration-v1"
    assert report["report_only"] is True and report["default_changed"] is False
    assert report["counts"] == {"golden": 5, "traps": 3}
    assert report["thresholds"][0]["threshold"] == 0.0
    assert report["thresholds"][0]["changed_ids"] == []
    assert report["thresholds"][-1]["threshold"] > max(
        report["cooperative_follow_up"][0]["top_score"] or 0.0,
        report["cooperative_follow_up"][1]["top_score"] or 0.0,
        report["cooperative_follow_up"][2]["top_score"] or 0.0,
    )
    for threshold_row in report["thresholds"]:
        assert set(threshold_row) >= {"threshold", "golden", "traps", "changed_ids"}
        assert set(threshold_row["golden"]) == {
            "answered",
            "right_source_found",
            "correct_abstentions",
            "broken",
        }
        assert set(threshold_row["traps"]) == {
            "correct_abstentions",
            "unexpected_answers",
            "right_source_found",
            "must_not_say_hits",
            "worse",
        }
    assert report["recommendation"]["rule"] == cal.RULE_TEXT
    assert report["recommendation"]["threshold"] in [r["threshold"] for r in report["thresholds"]]
    assert outcome.line == (
        "Result: threshold sweep over 5 golden and 3 trap questions at {} thresholds. "
        "Recommended minimum search score: {:.1f} (today 0.0). The /ask default is unchanged."
    ).format(len(report["thresholds"]), report["recommendation"]["threshold"])


def test_pre_retrieval_routes_never_change_state() -> None:
    report = run().report

    assert report is not None
    for threshold_row in report["thresholds"]:
        assert "g-4" not in threshold_row["changed_ids"]  # input screen
        assert "g-5" not in threshold_row["changed_ids"]  # year check


def test_the_zero_row_equals_todays_answers_and_a_mismatch_stops_with_nothing_written() -> None:
    assert run().report["thresholds"][0]["changed_ids"] == []

    class DropsEverything(cal.ThresholdBackend):
        def __init__(self, threshold: float) -> None:
            super().__init__(threshold)
            self.ranker = cal.MinScoreRanker(10.0)

    original = cal.ThresholdBackend
    try:
        cal.ThresholdBackend = DropsEverything  # type: ignore[assignment]
        outcome = run()
    finally:
        cal.ThresholdBackend = original  # type: ignore[assignment]

    assert (outcome.exit_code, outcome.line) == (1, cal.LINE_ZERO_MISMATCH)
    assert outcome.report is None and outcome.table is None


def test_a_grid_over_the_row_budget_stops_before_any_threshold_pass() -> None:
    original = cal.grid
    try:
        cal.grid = lambda scores: tuple(index * 0.5 for index in range(cal.MAX_GRID_ROWS + 1))  # type: ignore[assignment]
        outcome = run()
    finally:
        cal.grid = original  # type: ignore[assignment]

    assert (outcome.exit_code, outcome.line) == (1, cal.LINE_GRID_TOO_WIDE)
    assert outcome.report is None


def test_a_missing_or_unapproved_cooperative_trap_stops_the_sweep() -> None:
    outcome = run([case for case in CASES if case["id"] != "trap-013"])

    assert (outcome.exit_code, outcome.line) == (1, cal.LINE_COOPERATIVE_MISSING)
    assert outcome.report is None and outcome.table is None


def test_the_table_holds_the_zero_row_changed_counts_the_last_row_and_the_recommendation() -> None:
    outcome = run()
    report = outcome.report

    assert outcome.table is not None and outcome.report is not None
    thresholds = [row["threshold"] for row in report["thresholds"]]
    lines = [
        line
        for line in outcome.table.split("## Cooperative")[0].splitlines()
        if line.startswith("| ")
    ]
    tradeoff_rows = [line for line in lines[1:] if line.split("|")[1].strip()[:1].isdigit()]
    shown = {float(line.split("|")[1].strip()) for line in tradeoff_rows}
    assert 0.0 in shown
    assert thresholds[-1] in shown
    assert report["recommendation"]["threshold"] in shown
    for index in range(1, len(report["thresholds"])):
        previous = report["thresholds"][index - 1]
        current = report["thresholds"][index]
        if (current["golden"], current["traps"]) != (previous["golden"], previous["traps"]):
            assert current["threshold"] in shown
    assert all(item["id"] in outcome.table for item in report["cooperative_follow_up"])


def test_the_out_directory_inside_knowledge_stops_before_scoring(tmp_path: Path) -> None:
    called: List[int] = []
    original = cal.KNOWLEDGE_ROOT
    try:
        cal.KNOWLEDGE_ROOT = tmp_path / "knowledge"
        outcome = cal.run_sweep(
            inputs(),
            lambda _inputs: called.append(1),  # type: ignore[arg-type,return-value]
            tmp_path / "knowledge" / "out",
        )
    finally:
        cal.KNOWLEDGE_ROOT = original

    assert (outcome.exit_code, outcome.line) == (2, cal.LINE_OUT_INSIDE_KNOWLEDGE)
    assert outcome.line.startswith("error: ")
    assert called == []


def test_the_measurement_environment_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANIJERO_ANSWER_CACHE", "on")
    monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", "local")
    monkeypatch.delenv("MANIJERO_ANSWER_TRACE", raising=False)

    assert run().exit_code == 0

    assert os.environ["MANIJERO_ANSWER_CACHE"] == "on"
    assert os.environ["MANIJERO_GENERATION_PROVIDER"] == "local"
    assert "MANIJERO_ANSWER_TRACE" not in os.environ


def test_the_sweep_never_opens_a_socket_or_writes_the_reviewed_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid(self: Any, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("the threshold sweep must stay offline")

    monkeypatch.setattr(socket.socket, "connect", _forbid)
    before = {
        path.relative_to(ROOT / "knowledge"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "knowledge").rglob("*"))
        if path.is_file()
    }

    assert run().exit_code == 0

    after = {
        path.relative_to(ROOT / "knowledge"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "knowledge").rglob("*"))
        if path.is_file()
    }
    assert before == after


def test_the_new_modules_import_no_model_and_are_not_on_the_runtime_path() -> None:
    runtime = (BACKEND_ROOT / "app" / "threshold_calibration.py").read_text(encoding="utf-8")
    command = SCRIPT.read_text(encoding="utf-8")

    for forbidden in ("torch", "chromadb", "sentence_transformers", "transformers", "app.hybrid_retrieval", "app.embeddings"):
        assert forbidden not in runtime
    for forbidden in ("import socket", "import urllib", "import httpx", "import requests"):
        assert forbidden not in runtime and forbidden not in command
    assert "threshold_calibration" not in (BACKEND_ROOT / "app" / "main.py").read_text(
        encoding="utf-8"
    )


# --- The command -------------------------------------------------------------------------------


def test_the_command_loads_only_approved_golden_and_trap_items() -> None:
    from app import golden_set, trap_set

    args = Namespace(
        catalog=ROOT / "knowledge" / "source_catalog.json",
        passages=ROOT / "knowledge" / "passages.json",
        cases=ROOT / "knowledge" / "pac_answer_eval.json",
        golden=ROOT / "knowledge" / "golden_set.json",
        traps=ROOT / "knowledge" / "trap_set.json",
        active_campaign="2026",
        as_of=hyb.AS_OF,
        k=5,
        out=Path("build/unused"),
    )
    _catalog, _passages, scored = cli._load_scored(args)
    golden = golden_set.read_document(args.golden)
    traps = trap_set.read_document(args.traps)
    unapproved_golden = {
        item["id"] for item in golden["items"] if item["review_state"] != "approved"
    }
    unapproved_traps = {
        item["id"] for item in traps["items"] if item["review_state"] != "approved"
    }
    ids = {case["id"] for case in scored}
    assert sum(case["case_set"] == "golden" for case in scored) == len(golden_set.approved_cases(golden))
    assert sum(case["case_set"] == "trap" for case in scored) == len(trap_set.approved_cases(traps))
    assert not (unapproved_golden | unapproved_traps) & ids
    assert set(cal.COOPERATIVE_FOLLOW_UP) <= ids


def test_a_bad_input_exits_two_with_an_error_and_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--catalog",
            str(tmp_path / "missing-catalog.json"),
            "--passages",
            str(tmp_path / "missing-passages.json"),
            "--cases",
            str(tmp_path / "missing-cases.json"),
            "--golden",
            str(tmp_path / "missing-golden.json"),
            "--traps",
            str(tmp_path / "missing-traps.json"),
            "--active-campaign",
            "2026",
            "--as-of",
            "2026-11-07",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stderr.strip().splitlines()[-1].startswith("error: ")
    assert not out.exists()


def test_the_command_writes_both_files_in_the_out_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = cal.SweepOutcome(0, "Result: done.", {"schema_version": "x"}, "# table\n")
    monkeypatch.setattr(cli, "_load_scored", lambda args: (None, None, [{"id": "x"}]))
    monkeypatch.setattr(cli, "run_sweep", lambda inputs, loader, out: outcome)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--catalog",
            "catalog.json",
            "--passages",
            "passages.json",
            "--cases",
            "cases.json",
            "--golden",
            "golden.json",
            "--traps",
            "traps.json",
            "--active-campaign",
            "2026",
            "--as-of",
            "2026-11-07",
            "--out",
            str(tmp_path / "out"),
        ],
    )

    assert cli.main() == 0

    assert sorted(path.name for path in (tmp_path / "out").iterdir()) == [
        "report.json",
        "table.md",
    ]
    assert json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8")) == {
        "schema_version": "x"
    }
    assert (tmp_path / "out" / "table.md").read_text(encoding="utf-8") == "# table\n"


def test_a_stopped_command_prints_its_line_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = cal.SweepOutcome(1, cal.LINE_ZERO_MISMATCH)
    monkeypatch.setattr(cli, "_load_scored", lambda args: (None, None, [{"id": "x"}]))
    monkeypatch.setattr(cli, "run_sweep", lambda inputs, loader, out: outcome)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--catalog",
            "catalog.json",
            "--passages",
            "passages.json",
            "--cases",
            "cases.json",
            "--golden",
            "golden.json",
            "--traps",
            "traps.json",
            "--active-campaign",
            "2026",
            "--as-of",
            "2026-11-07",
            "--out",
            str(tmp_path / "out"),
        ],
    )

    assert cli.main() == 1
    assert not (tmp_path / "out").exists()


def test_a_zero_score_grid_keeps_a_single_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A question that never reaches retrieval records no top score; with every case routed
    # before retrieval the grid is exactly [0.0].
    cases = [
        make_case("g-screen", "Mi DNI es 12345678Z, ¿qué ayuda me toca?", "golden", "abstained"),
        make_case("g-year", "¿Cuándo se presenta la solicitud de 2031?", "golden", "abstained"),
        make_case("trap-013", "Mi DNI es 12345678Z, ¿qué ayuda me toca?", "trap", "abstained"),
        make_case("trap-014", "Mi teléfono es 600000000, ¿qué ayuda me toca?", "trap", "abstained"),
        make_case("trap-016", "Mi correo es a@b.es, ¿qué ayuda me toca?", "trap", "abstained"),
    ]

    outcome = run(cases)

    assert outcome.exit_code == 0 and outcome.report is not None
    assert [row["threshold"] for row in outcome.report["thresholds"]] == [0.0]
    assert all(
        item["top_score"] is None for item in outcome.report["cooperative_follow_up"]
    )
