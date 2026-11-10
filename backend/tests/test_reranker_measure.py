"""Offline tests for the reranker measurement and the owner's on/off rule.

A fake scorer, a fake clock, and a fake hybrid loader (keyword embedder plus in-memory vector
searcher over a synthetic labelled corpus) stand in for the real models: no ``torch``, no
``chromadb``, no download. Nothing here claims retrieval quality or a latency figure.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

import test_hybrid_retrieval as hyb  # noqa: E402  (shares the synthetic corpus and fakes)
from app import reranker_measure as measure  # noqa: E402
from app.hybrid_retrieval import HybridBackend  # noqa: E402
from app.reranker import RerankerSettings  # noqa: E402
from app.reranker_measure import (  # noqa: E402
    Comparison,
    MeasureInputs,
    compare,
    result_line,
    verdict,
)

JUNTA = "fixture_clar_junta"
BOE = "fixture_clar_boe"
SECRET_WORDS = ("solicitud", "riego", "pesca")


# --- The rule ----------------------------------------------------------------------------------


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


def golden_runs(before: Sequence[bool], after: Sequence[bool]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    first = [row("g{}".format(i), source=value) for i, value in enumerate(before)]
    second = [row("g{}".format(i), source=value) for i, value in enumerate(after)]
    return first, second


def comparison(**overrides: Any) -> Comparison:
    values: Dict[str, Any] = dict(
        golden=49, traps=26, found_baseline=40, found_reranked=42, broken=0, trap_worse=0,
        slowest_extra_seconds=1.0,
    )
    values.update(overrides)
    return Comparison(**values)


def test_on_at_exactly_the_boundaries() -> None:
    assert verdict(comparison(found_reranked=42, slowest_extra_seconds=2.0)) == (True, ())


@pytest.mark.parametrize(
    "overrides,reasons",
    [
        ({"found_reranked": 41}, [measure.REASON_FEW_GAIN]),
        ({"found_reranked": 40}, [measure.REASON_FEW_GAIN]),
        ({"found_reranked": 39}, [measure.REASON_FEW_GAIN]),
        ({"found_reranked": 43, "broken": 1}, [measure.REASON_BROKEN]),
        ({"trap_worse": 1}, [measure.REASON_TRAP_WORSE]),
        ({"slowest_extra_seconds": 2.01}, [measure.REASON_SLOW]),
        (
            {"found_reranked": 40, "broken": 2, "trap_worse": 3, "slowest_extra_seconds": 9.0},
            [measure.REASON_FEW_GAIN, measure.REASON_BROKEN, measure.REASON_TRAP_WORSE, measure.REASON_SLOW],
        ),
    ],
)
def test_off_with_every_failed_rule_in_the_fixed_order(overrides, reasons) -> None:
    switch_on, found = verdict(comparison(**overrides))

    assert switch_on is False and list(found) == reasons


def test_the_on_line_is_exactly_the_contract_text() -> None:
    assert result_line(comparison(found_reranked=43, slowest_extra_seconds=1.24)) == (
        "Result: reranker measured on 49 golden and 26 trap questions against today's hybrid search. "
        "Right source found: 40 today, 43 with the reranker (+3). Golden questions broken: 0. "
        "Trap questions worse: 0. Slowest extra time: 1.2 seconds. "
        "Verdict: ON - it met all the rules. Send this line to the developer."
    )


def test_the_off_line_joins_the_reasons_and_keeps_the_experiment() -> None:
    line = result_line(comparison(found_reranked=39, broken=1, slowest_extra_seconds=2.5))

    assert line == (
        "Result: reranker measured on 49 golden and 26 trap questions against today's hybrid search. "
        "Right source found: 40 today, 39 with the reranker (-1). Golden questions broken: 1. "
        "Trap questions worse: 0. Slowest extra time: 2.5 seconds. "
        "Verdict: OFF - fewer than 2 more golden questions found their right source; "
        "a golden question that worked today broke; slower than 2 extra seconds. "
        "It stays off and this result is kept as a recorded experiment. Send this line to the developer."
    )
    assert line.count("\n") == 0 and line.startswith("Result: ")


def test_the_rule_constants_are_the_owners() -> None:
    assert (measure.MIN_GOLDEN_GAIN, measure.MAX_EXTRA_SECONDS, measure.MAX_MODEL_BYTES) == (2, 2.0, 5_000_000_000)


def test_right_source_found_needs_an_answer_that_cites_every_expected_source() -> None:
    before = [
        row("g0", source=False),
        row("g1", expected="abstained", actual="abstained"),  # abstained items never count as found
        row("g2", expected="answered", actual="abstained", source=False),
        row("g3"),
    ]
    after = [row("g0"), row("g1", expected="abstained", actual="abstained"), row("g2"), row("g3")]

    result = compare(before, after, {})

    assert (result.golden, result.found_baseline, result.found_reranked) == (4, 1, 3)


def test_a_golden_item_that_passed_and_no_longer_does_is_broken_even_with_a_big_gain() -> None:
    before = [row("g0"), row("g1", source=False), row("g2", source=False), row("g3", source=False)]
    after = [row("g0", source=False), row("g1"), row("g2"), row("g3")]

    result = compare(before, after, {})

    assert (result.found_baseline, result.found_reranked, result.broken) == (1, 3, 1)
    assert verdict(result)[0] is False


def test_an_abstention_that_flips_to_an_answer_is_broken() -> None:
    before = [row("g0", expected="abstained", actual="abstained")]
    after = [row("g0", expected="abstained", actual="answered")]

    assert compare(before, after, {}).broken == 1


def trap(identifier: str, **kwargs: Any) -> Dict[str, Any]:
    defaults: Dict[str, Any] = dict(case_set="trap", expected="abstained", actual="abstained", reason=True)
    defaults.update(kwargs)
    return row(identifier, **defaults)


@pytest.mark.parametrize(
    "after,worse",
    [
        (trap("t"), 0),
        (trap("t", actual="answered"), 1),  # expected state true -> false
        (trap("t", reason=False), 1),  # abstention reason true -> false
        (trap("t", reason=None), 1),
        (trap("t", said=["bad phrase"]), 1),  # must_not_say grows
        (trap("t", actual="answered", reason=False, said=["x", "y"]), 1),  # one trap counts once
    ],
)
def test_trap_worse_kinds(after: Dict[str, Any], worse: int) -> None:
    result = compare([trap("t")], [after], {})

    assert result.trap_worse == worse and result.traps == 1


def test_a_trap_that_was_already_wrong_or_improves_is_not_worse() -> None:
    before = trap("t", actual="answered", reason=False, said=["x"])

    assert compare([before], [trap("t")], {}).trap_worse == 0
    assert compare([before], [before], {}).trap_worse == 0
    assert compare([trap("t", said=["x"])], [trap("t", said=["x"])], {}).trap_worse == 0


def test_the_slowest_extra_time_is_the_maximum_over_all_questions() -> None:
    first, second = golden_runs([True, True], [True, True])

    assert compare(first, second, {"g0": 0.4, "g1": 1.7}).slowest_extra_seconds == 1.7
    assert compare(first, second, {}).slowest_extra_seconds == 0.0


def test_runs_over_different_questions_are_refused() -> None:
    with pytest.raises(ValueError):
        compare([row("a")], [row("b")], {})
    with pytest.raises(ValueError):
        compare([row("a")], [row("a"), row("a")], {})


# --- Running over a fake hybrid backend --------------------------------------------------------

AS_OF = hyb.AS_OF
SETTINGS = RerankerSettings("off", 20, 512, 8, "c" * 64)


class StepClock:
    """Every call advances by ``step`` seconds, so one scorer call lasts exactly ``step``."""

    def __init__(self, step: float) -> None:
        self.step = step
        self._now = 0.0

    def __call__(self) -> float:
        current = self._now
        self._now += self.step
        return current


class PreferJunta:
    """Puts the application-request passage first; everything else keeps its order."""

    def __init__(self) -> None:
        self.calls = 0

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        self.calls += 1
        return tuple(10.0 if "solicitud anual" in text else float(-position) for position, text in enumerate(texts))


class KeepOrder:
    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        return tuple(float(-position) for position in range(len(texts)))


class PreferBoe:
    """Moves the application-request passage last: breaks questions that found it first."""

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        return tuple(-10.0 if "solicitud anual" in text else float(-position) for position, text in enumerate(texts))


def make_case(identifier: str, question: str, case_set: str, status: str, sources: Sequence[str] = ()) -> Dict[str, Any]:
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
    if case_set == "trap":
        case.update(category="false_premise", acceptable_abstention_reasons=["no_evidence"], must_not_say=[])
    return case


CASES = [
    # Today's hybrid search puts a riego passage first for these, so with k=1 it cites the wrong source.
    make_case("g-1", "riego regadio secano parcela anual", "golden", "answered", [JUNTA]),
    make_case("g-2", "regadio riego secano anual ejemplo", "golden", "answered", [JUNTA]),
    # Today's hybrid search already puts the application passage first.
    make_case("g-3", "¿Cuándo se presenta la solicitud anual de ejemplo?", "golden", "answered", [JUNTA]),
    make_case("t-1", "¿Qué ayuda de pesca me corresponde?", "trap", "abstained"),
]


class Run:
    """One measurement over the synthetic corpus with injectable fakes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, **options: Any) -> None:
        self.retriever = hyb.clarification_retriever()
        self.embedder = options.get("embedder") or hyb.KeywordEmbedder()
        self.loads: List[int] = []
        self.lines: List[str] = []
        self.scorer = options.get("scorer") or PreferJunta()
        self.ready = options.get("ready", True)
        self.scorer_error = options.get("scorer_error")
        self.clock = StepClock(options.get("step", 0.25))
        self.retriever_for_store = options.get("store_retriever") or self.retriever
        cases = options.get("cases", CASES)
        documents = hyb.clarification_documents()
        self.cases_loader = lambda inputs: (documents.catalog, documents.passages, [dict(c) for c in cases])
        self.k = options.get("k", 1)

    def components(self) -> Any:
        self.loads.append(1)
        return hyb.components_for(self.retriever_for_store, embedder=self.embedder)

    def inputs(self) -> MeasureInputs:
        path = Path("unused.json")
        return MeasureInputs(path, path, path, path, path, hyb.CAMPAIGN, AS_OF, self.k)

    def scorer_loader(self) -> Any:
        if self.scorer_error:
            raise self.scorer_error
        return self.scorer

    def run(self) -> measure.MeasureOutcome:
        return measure.run_measurement(
            self.inputs(),
            HybridBackend(self.components),
            cases_loader=self.cases_loader,
            reranker_ready=lambda: self.ready,
            scorer_loader=self.scorer_loader,
            settings=SETTINGS,
            clock=self.clock,
            out=self.lines.append,
        )


def test_a_reranker_that_finds_two_more_sources_and_breaks_nothing_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch)

    outcome = run.run()

    assert outcome.exit_code == 0
    assert outcome.comparison == Comparison(
        golden=3, traps=1, found_baseline=1, found_reranked=3, broken=0, trap_worse=0,
        slowest_extra_seconds=0.5,  # two searches per question, 0.25 s each
    )
    assert outcome.line == (
        "Result: reranker measured on 3 golden and 1 trap questions against today's hybrid search. "
        "Right source found: 1 today, 3 with the reranker (+2). Golden questions broken: 0. "
        "Trap questions worse: 0. Slowest extra time: 0.5 seconds. "
        "Verdict: ON - it met all the rules. Send this line to the developer."
    )


def test_both_passes_share_one_loaded_hybrid_backend_and_the_vector_side_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch)

    run.run()

    assert run.loads == [1]  # the candidate wraps the very same hybrid backend: one embedder, one store
    # Three questions have a lexical match: the vector side ran for them in both passes, equally often.
    assert len(run.embedder.calls) > 0 and len(run.embedder.calls) % 2 == 0
    half = len(run.embedder.calls) // 2
    assert run.embedder.calls[:half] == run.embedder.calls[half:]


def test_the_answer_cache_is_off_between_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    scorer = PreferJunta()
    run = Run(monkeypatch, scorer=scorer)

    run.run()

    # Every search of the second pass was scored (after the one warm-up call): a cache hit would skip it.
    assert scorer.calls - 1 == len(run.embedder.calls) // 2 > 0


def test_progress_lines_and_stdout_carry_counts_only(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch)

    run.run()

    assert "Checked question 1 of 4" in run.lines and "Checked question 4 of 4" in run.lines
    assert sum(line.startswith("Checked question") for line in run.lines) == 8
    joined = "\n".join(run.lines).lower()
    for word in SECRET_WORDS:
        assert word not in joined


def test_the_measurement_environment_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANIJERO_ANSWER_CACHE", "on")
    monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", "local")
    monkeypatch.delenv("MANIJERO_ANSWER_TRACE", raising=False)
    run = Run(monkeypatch)

    run.run()

    assert os.environ["MANIJERO_ANSWER_CACHE"] == "on"
    assert os.environ["MANIJERO_GENERATION_PROVIDER"] == "local"
    assert "MANIJERO_ANSWER_TRACE" not in os.environ


def test_a_reranker_that_changes_nothing_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = Run(monkeypatch, scorer=KeepOrder()).run()

    assert outcome.exit_code == 0
    assert (outcome.comparison.found_baseline, outcome.comparison.found_reranked) == (1, 1)
    assert "Verdict: OFF - fewer than 2 more golden questions found their right source." in outcome.line


def test_a_reranker_that_breaks_a_working_question_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = Run(monkeypatch, scorer=PreferBoe()).run()

    assert outcome.comparison.broken == 1
    assert "a golden question that worked today broke" in outcome.line
    assert "Verdict: OFF" in outcome.line


def test_a_slow_reranker_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = Run(monkeypatch, step=2.5).run()

    assert outcome.comparison.slowest_extra_seconds > measure.MAX_EXTRA_SECONDS
    assert outcome.line.endswith(
        "slower than 2 extra seconds. It stays off and this result is kept as a recorded experiment. "
        "Send this line to the developer."
    )


def test_a_stale_store_stops_with_the_setup_line_and_no_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch, store_retriever=hyb.retrieval_retriever())

    outcome = run.run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NOT_READY)
    assert "./scripts/init.sh --local-rag-setup" in outcome.line
    assert run.lines == []  # nothing was checked


def test_a_hybrid_that_cannot_load_stops_with_the_setup_line(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch)

    def broken() -> Any:
        raise RuntimeError("cannot open the store")

    outcome = measure.run_measurement(
        run.inputs(), HybridBackend(broken), cases_loader=run.cases_loader, reranker_ready=lambda: True,
        scorer_loader=run.scorer_loader, settings=SETTINGS, out=run.lines.append,
    )

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NOT_READY)


def test_the_hybrid_check_comes_before_the_reranker_model_check(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch, store_retriever=hyb.retrieval_retriever(), ready=False)

    assert run.run().line == measure.LINE_NOT_READY


def test_a_missing_reranker_model_names_the_download_command(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch, ready=False)

    outcome = run.run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NO_MODEL)
    assert "./scripts/init.sh --reranker-download" in outcome.line
    assert run.lines == []


def test_a_reranker_that_cannot_load_is_reported_as_a_model_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = Run(monkeypatch, scorer_error=RuntimeError("boom")).run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NO_MODEL)


def test_a_bm25_fallback_in_the_first_pass_gives_no_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch, embedder=hyb.FailingEmbedder())

    outcome = run.run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NO_VECTOR)
    assert "Verdict" not in outcome.line and outcome.comparison is None


class FailsInSecondPass(hyb.KeywordEmbedder):
    def __init__(self, good_calls: int) -> None:
        super().__init__()
        self._good = good_calls

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        if len(self.calls) >= self._good:
            self.calls.append(tuple(texts))
            raise RuntimeError("vector side went away")
        return super().embed(texts)


def test_a_bm25_fallback_in_the_second_pass_gives_no_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Run(monkeypatch, embedder=FailsInSecondPass(good_calls=3))

    outcome = run.run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_NO_VECTOR)


class BrokenScorer:
    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        if len(texts) == 2 and texts[0] == "warm-up one":
            return (0.0, 1.0)
        raise RuntimeError("scoring failed")


def test_a_reranker_that_fails_while_measuring_gives_no_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = Run(monkeypatch, scorer=BrokenScorer()).run()

    assert (outcome.exit_code, outcome.line) == (1, measure.LINE_RERANK_FAILED)


def test_a_question_that_never_reaches_retrieval_is_not_a_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = CASES + [
        make_case("t-2", "Mi DNI es 12345678Z, ¿qué ayuda me toca?", "trap", "abstained"),
        make_case("t-3", "¿Cuándo se presenta la solicitud de 2031?", "trap", "abstained"),
    ]

    outcome = Run(monkeypatch, cases=cases).run()

    assert outcome.exit_code == 0 and outcome.comparison.traps == 3
