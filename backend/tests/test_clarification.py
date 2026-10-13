"""Focused tests for the offline land-clarification decisions.

The fixtures under ``fixtures/clarification/`` are synthetic and clearly
labelled: they are not real legal documents and they carry no real deadline,
amount, or article. They exist only to exercise the clarification trigger, the
conservative compatibility rules, the assembled payload, and the evaluation CLI.

The tests never call a model or the network: the only enabled generator is the
accepted code-composed extractive one, and the corpus is built from the local
fixtures.
"""

import importlib.util
import json
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.abstention import (  # noqa: E402  (path setup must run first)
    Abstention,
    answer_or_abstain,
    prepare_corpus,
)
from app.clarification import (  # noqa: E402
    CLARIFICATION_SCOPE,
    CLARIFICATION_STATUS,
    DEFAULT_MAX_CLAIMS,
    DISCRIMINATING_DIMENSIONS,
    LAND_SCOPES,
    MAX_LAND_ID_CHARS,
    MIN_LANDS,
    NeedsLandClarification,
    answer_with_clarification,
    candidate_is_applicable,
    clarify_land_scope,
    compatible_passage_ids,
    declared_applicability,
    land_context_mode,
    land_ids_of,
    to_clarification_response,
)
from app.generation import (  # noqa: E402
    Answered,
    to_answer_response,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    CatalogRejectedError,
    PassageSetError,
    RetrievedPassage,
    Retriever,
    load_passage_set,
)
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "evaluate_clarification.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clarification"
RETRIEVAL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval"

AS_OF = "2026-10-13"
WATER_QUESTION = "¿Puedo regar mi olivar de ejemplo?"
SOLICITUD_QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"


# --- helpers ----------------------------------------------------------------


def fixture(name: str) -> Path:
    return FIXTURES / name


def as_of_date(as_of: str = AS_OF) -> date:
    return date.fromisoformat(as_of)


def catalog_document(name: str = "catalog.json"):
    return load_catalog(fixture(name))


def passage_document(name: str = "passages.json"):
    return load_passage_set(fixture(name))


def build_retriever(as_of: str = AS_OF) -> Retriever:
    return Retriever.from_documents(
        catalog_document(), passage_document(), as_of_date(as_of)
    )


def current_corpus(as_of: str = AS_OF):
    corpus = prepare_corpus(catalog_document(), passage_document(), as_of_date(as_of))
    assert isinstance(corpus, Retriever)
    return corpus


def all_active(*lands: Dict[str, Any]) -> Dict[str, Any]:
    return {"mode": "all_active", "lands": list(lands)}


def make_passage(
    excerpt: str,
    *,
    passage_id: str = "fixture-clar-synthetic-1",
    applicability: Optional[Dict[str, str]] = None,
    critical: bool = False,
    rank: int = 1,
) -> RetrievedPassage:
    """Build one candidate directly, so unit tests do not depend on ranking."""

    return RetrievedPassage(
        passage_id=passage_id,
        source_id="fixture_clar_boe",
        title="Documento sintético de prueba (fixture; no es una norma real)",
        issuing_body="BOE",
        url="https://www.boe.es/buscar/doc.php?id=DOC-FIXTURE-CLAR-0001",
        location="Art. 9 (fixture, sintético)",
        published_or_updated_on="2026-02-20",
        verified_on="2026-10-04",
        excerpt=excerpt,
        applicability=applicability,
        critical=critical,
        score=1.0,
        rank=rank,
    )


class FixedRetriever(Retriever):
    """A retriever that returns a fixed candidate list, for window tests."""

    def __init__(self, candidates: Sequence[RetrievedPassage]) -> None:
        self._candidates = tuple(candidates)

    def search(self, question: str, k: int = DEFAULT_K):
        return self._candidates[:k]


class RecordingRetriever(Retriever):
    """A retriever that records every search it receives."""

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner
        self.queries: list = []

    def search(self, question: str, k: int = DEFAULT_K):
        self.queries.append((question, k))
        return self._inner.search(question, k=k)


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def baseline_cli(*extra: str) -> subprocess.CompletedProcess:
    return run_cli(
        "--catalog",
        str(fixture("catalog.json")),
        "--passages",
        str(fixture("passages.json")),
        "--eval",
        str(fixture("eval_questions.jsonl")),
        "--as-of",
        AS_OF,
        "--k",
        "5",
        *extra,
    )


def load_cli_module():
    """Load the CLI script as a module so its pure helpers can be unit-tested."""

    spec = importlib.util.spec_from_file_location("evaluate_clarification_cli", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def eval_lines(name: str) -> Tuple[Dict[str, Any], ...]:
    return tuple(
        json.loads(line)
        for line in fixture(name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


# --- compatibility rules ----------------------------------------------------


def test_discriminating_dimensions_are_the_two_request_fields() -> None:
    assert DISCRIMINATING_DIMENSIONS == ("water_regime", "production_method")
    assert "crop" not in DISCRIMINATING_DIMENSIONS
    assert MIN_LANDS == 2
    assert DEFAULT_MAX_CLAIMS == 2
    assert set(LAND_SCOPES) == {"general", "all_active", "selected"}


def test_declared_applicability_ignores_absent_unknown_and_blank_values() -> None:
    assert declared_applicability(make_passage("t", applicability=None), "water_regime") is None
    assert (
        declared_applicability(
            make_passage("t", applicability={"water_regime": "unknown"}), "water_regime"
        )
        is None
    )
    assert (
        declared_applicability(
            make_passage("t", applicability={"water_regime": "   "}), "water_regime"
        )
        is None
    )
    assert declared_applicability(make_passage("t", applicability={"crop": "olivar"}), "water_regime") is None
    assert (
        declared_applicability(
            make_passage("t", applicability={"water_regime": "irrigated"}), "water_regime"
        )
        == "irrigated"
    )


def test_a_candidate_is_applicable_unless_a_known_value_disagrees() -> None:
    candidate = make_passage("t", applicability={"water_regime": "irrigated"})

    assert candidate_is_applicable(candidate, {"water_regime": "irrigated"}) is True
    assert candidate_is_applicable(candidate, {"water_regime": "unknown"}) is True
    assert candidate_is_applicable(candidate, {}) is True
    assert candidate_is_applicable(candidate, {"water_regime": "dryland"}) is False


def test_a_declared_production_method_can_discriminate() -> None:
    candidate = make_passage("t", applicability={"production_method": "organic"})

    assert candidate_is_applicable(candidate, {"production_method": "organic"}) is True
    assert candidate_is_applicable(candidate, {"production_method": "conventional"}) is False
    assert candidate_is_applicable(candidate, {"production_method": "unknown"}) is True
    assert candidate_is_applicable(candidate, {}) is True


def test_compatible_passage_ids_lists_only_the_applicable_candidates() -> None:
    irrigated = make_passage(
        "t", passage_id="p-irrigated", applicability={"water_regime": "irrigated"}
    )
    dryland = make_passage("t", passage_id="p-dryland", applicability={"water_regime": "dryland"})
    unrestricted = make_passage("t", passage_id="p-generic", applicability=None)

    candidates = (irrigated, dryland, unrestricted)

    assert compatible_passage_ids(candidates, {"water_regime": "irrigated"}) == (
        "p-irrigated",
        "p-generic",
    )
    assert compatible_passage_ids(candidates, {"water_regime": "dryland"}) == (
        "p-dryland",
        "p-generic",
    )
    assert compatible_passage_ids(candidates, {"water_regime": "unknown"}) == (
        "p-irrigated",
        "p-dryland",
        "p-generic",
    )


# --- trigger ----------------------------------------------------------------


def test_two_different_lands_return_both_ids_for_a_water_question() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        corpus,
        k=5,
    )

    assert isinstance(decision, NeedsLandClarification)
    assert decision.land_ids_to_choose == ("land-A", "land-B")


def test_lands_equal_on_the_needed_dimension_do_not_clarify() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active(
            {"id": "land-A", "water_regime": "irrigated"},
            {"id": "land-B", "water_regime": "irrigated"},
        ),
        corpus,
        k=5,
    )

    assert decision is None


def test_unknown_or_omitted_attributes_never_filter_or_clarify() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "unknown"}, {"id": "land-B"}),
        corpus,
        k=5,
    )

    assert decision is None


def test_crop_only_applicability_never_discriminates() -> None:
    crop_candidate = make_passage(
        "t", passage_id="p-crop", applicability={"crop": "olivar"}
    )
    corpus = FixedRetriever([crop_candidate])

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active(
            {"id": "land-A", "water_regime": "irrigated"},
            {"id": "land-B", "water_regime": "dryland"},
        ),
        corpus,
        k=5,
    )

    assert decision is None


@pytest.mark.parametrize("mode", ["general", "selected"])
def test_general_and_selected_never_clarify(mode: str) -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        {"mode": mode, "lands": [
            {"id": "land-A", "water_regime": "irrigated"},
            {"id": "land-B", "water_regime": "dryland"},
        ]},
        corpus,
        k=5,
    )

    assert decision is None


def test_one_land_never_clarifies() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "irrigated"}),
        corpus,
        k=5,
    )

    assert decision is None


def test_no_candidates_never_clarifies() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        "zzzz qqqq",
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        corpus,
        k=5,
    )

    assert decision is None


def test_only_the_citation_window_is_inspected() -> None:
    # The restricting candidate sits outside the window; with max_claims = 1 the
    # second candidate is ignored, so the lands' sets stay equal.
    generic = make_passage("t", passage_id="p-generic", applicability=None, rank=1)
    restricting = make_passage(
        "t", passage_id="p-restricting", applicability={"water_regime": "irrigated"}, rank=2
    )
    corpus = FixedRetriever([generic, restricting])
    lands = all_active(
        {"id": "land-A", "water_regime": "irrigated"},
        {"id": "land-B", "water_regime": "dryland"},
    )

    assert clarify_land_scope(WATER_QUESTION, lands, corpus, k=5, max_claims=1) is None
    assert clarify_land_scope(WATER_QUESTION, lands, corpus, k=5, max_claims=2) is not None


def test_land_ids_keep_request_order_and_are_deduplicated() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active(
            {"id": "z-land", "water_regime": "dryland"},
            {"id": "a-land", "water_regime": "irrigated"},
            {"id": "z-land", "water_regime": "dryland"},
        ),
        corpus,
        k=5,
    )

    assert isinstance(decision, NeedsLandClarification)
    assert decision.land_ids_to_choose == ("z-land", "a-land")


def test_a_land_without_a_usable_id_cannot_be_offered() -> None:
    corpus = current_corpus()

    decision = clarify_land_scope(
        WATER_QUESTION,
        all_active(
            {"water_regime": "irrigated"},
            {"id": "   ", "water_regime": "dryland"},
        ),
        corpus,
        k=5,
    )

    assert decision is None


def test_land_context_mode_defaults_to_general() -> None:
    assert land_context_mode(None) == "general"
    assert land_context_mode({}) == "general"
    assert land_context_mode({"mode": "all_active"}) == "all_active"
    assert land_ids_of({"mode": "all_active", "lands": [{"id": "x"}, {}]}) == ("x",)


def test_the_decision_searches_once() -> None:
    recording = RecordingRetriever(build_retriever())
    corpus = recording

    clarify_land_scope(WATER_QUESTION, all_active({"id": "a", "water_regime": "irrigated"}, {"id": "b", "water_regime": "dryland"}), corpus, k=5)

    assert len(recording.queries) == 1
    assert recording.queries[0][0] == WATER_QUESTION


# --- delegation -------------------------------------------------------------


def test_answer_with_clarification_returns_the_decision_on_a_difference() -> None:
    corpus = current_corpus()

    result = answer_with_clarification(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        corpus,
        k=5,
        as_of=as_of_date(),
    )

    assert isinstance(result, NeedsLandClarification)
    assert result.land_ids_to_choose == ("land-A", "land-B")


def test_answer_with_clarification_delegates_when_lands_are_equal() -> None:
    corpus = current_corpus()
    lands = all_active(
        {"id": "land-A", "water_regime": "irrigated"},
        {"id": "land-B", "water_regime": "irrigated"},
    )

    result = answer_with_clarification(
        WATER_QUESTION, lands, corpus, k=5, as_of=as_of_date()
    )
    expected = answer_or_abstain(
        WATER_QUESTION, corpus, k=5, land_scope="all_active", as_of=as_of_date()
    )

    assert isinstance(result, Answered)
    assert result == expected


def test_general_and_selected_delegate_to_the_accepted_path_unchanged() -> None:
    corpus = current_corpus()

    general = answer_with_clarification(
        WATER_QUESTION, {"mode": "general", "lands": []}, corpus, k=5, as_of=as_of_date()
    )
    selected = answer_with_clarification(
        WATER_QUESTION,
        {"mode": "selected", "lands": [{"id": "land-A", "water_regime": "irrigated"}]},
        corpus,
        k=5,
        as_of=as_of_date(),
    )

    assert isinstance(general, Answered)
    assert general.land_scope == "general"
    assert isinstance(selected, Answered)
    assert selected.land_scope == "selected"


def test_a_stale_corpus_abstains_stale_evidence_without_clarifying() -> None:
    stale = prepare_corpus(
        load_catalog(RETRIEVAL_FIXTURES / "catalog_expired.json"),
        load_passage_set(fixture("passages.json")),
        as_of_date(),
    )
    assert isinstance(stale, Abstention)

    result = answer_with_clarification(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        stale,
        k=5,
        as_of=as_of_date(),
    )

    assert isinstance(result, Abstention)
    assert result.reason == "stale_evidence"


def test_a_blank_question_delegates_to_invalid_question() -> None:
    corpus = current_corpus()

    result = answer_with_clarification(
        "   ",
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        corpus,
        k=5,
        as_of=as_of_date(),
    )

    assert isinstance(result, Abstention)
    assert result.reason == "invalid_question"


# --- payload shape ----------------------------------------------------------


def test_the_clarification_payload_has_exactly_the_contract_keys() -> None:
    payload = to_clarification_response(NeedsLandClarification(("land-A", "land-B")))

    assert payload == {
        "status": "needs_land_clarification",
        "answer": "",
        "sources": [],
        "land_scope": "selected",
        "land_ids_to_choose": ["land-A", "land-B"],
    }
    assert set(payload) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}


def test_the_clarification_payload_matches_the_accepted_example_shape() -> None:
    example = json.loads(
        (REPO_ROOT / "contracts" / "examples" / "response-needs-land-clarification.json")
        .read_text(encoding="utf-8")
    )

    payload = to_clarification_response(NeedsLandClarification(("land-A",)))

    assert set(payload) == set(example)
    assert payload["status"] == example["status"]
    assert payload["answer"] == ""
    assert payload["sources"] == []
    assert payload["land_scope"] in LAND_SCOPES


def test_to_clarification_response_rejects_a_non_clarification() -> None:
    with pytest.raises(ValueError):
        to_clarification_response(Answered(answer="x", claims=(), sources=()))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "ids",
    [
        (),
        ("",),
        ("   ",),
        ("a" * (MAX_LAND_ID_CHARS + 1),),
        ("dup", "dup"),
    ],
)
def test_needs_land_clarification_rejects_malformed_ids(ids: Tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        NeedsLandClarification(ids)


def test_needs_land_clarification_is_immutable() -> None:
    decision = NeedsLandClarification(("land-A",))
    with pytest.raises(Exception):
        decision.land_ids_to_choose = ("land-B",)  # type: ignore[misc]


# --- determinism and offline ------------------------------------------------


def test_the_decision_is_deterministic() -> None:
    corpus = current_corpus()
    lands = all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"})

    first = clarify_land_scope(WATER_QUESTION, lands, corpus, k=5)
    second = clarify_land_scope(WATER_QUESTION, lands, corpus, k=5)

    assert first == second


def test_the_decision_never_opens_a_network_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = current_corpus()

    def _forbid(*args, **kwargs):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket, "socket", _forbid)

    result = answer_with_clarification(
        WATER_QUESTION,
        all_active({"id": "land-A", "water_regime": "irrigated"}, {"id": "land-B", "water_regime": "dryland"}),
        corpus,
        k=5,
        as_of=as_of_date(),
    )

    assert isinstance(result, NeedsLandClarification)


def test_clarification_module_imports_no_network_client() -> None:
    source = (BACKEND_ROOT / "app" / "clarification.py").read_text(encoding="utf-8")
    for forbidden in ("import socket", "import urllib", "import httpx", "import requests"):
        assert forbidden not in source


# --- CLI --------------------------------------------------------------------


def test_cli_reports_a_clarification_and_all_outcomes() -> None:
    result = baseline_cli()

    assert result.returncode == 0
    assert "corpus: current" in result.stdout
    assert "eligible sources: 2" in result.stdout
    assert "land ids to choose: land-A, land-B" in result.stdout
    assert "clarifications: 1" in result.stdout
    assert "clarification invariants hold: yes" in result.stdout
    assert "outcomes differing from expect: 0" in result.stdout


def test_cli_json_report_is_machine_readable() -> None:
    result = baseline_cli("--json")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["corpus_status"] == "current"
    assert report["clarification_invariants_hold"] is True
    assert report["totals"]["clarifications"] == 1
    assert report["totals"]["outcomes_differing_from_expect"] == 0
    assert report["fixtures_are_synthetic"] is True
    assert report["thresholds_are_release_gates"] is False
    first = report["questions"][0]
    assert first["outcome"] == "needs_land_clarification"
    assert first["land_ids_to_choose"] == ["land-A", "land-B"]


def test_cli_run_is_deterministic() -> None:
    first = baseline_cli("--json")
    second = baseline_cli("--json")

    assert first.stdout == second.stdout


def test_cli_fail_on_miss_is_off_by_default_and_opt_in_is_exit_one(
    tmp_path: Path,
) -> None:
    evaluation = tmp_path / "eval.jsonl"
    evaluation.write_text(
        json.dumps(
            {
                "question": WATER_QUESTION,
                "land_context": all_active(
                    {"id": "land-A", "water_regime": "irrigated"},
                    {"id": "land-B", "water_regime": "dryland"},
                ),
                "expect": "answered",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    without = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--eval", str(evaluation),
        "--as-of", AS_OF, "--k", "5",
    )
    with_flag = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--eval", str(evaluation),
        "--as-of", AS_OF, "--k", "5", "--fail-on-miss",
    )

    assert without.returncode == 0
    assert with_flag.returncode == 1
    assert with_flag.stdout == without.stdout


@pytest.mark.parametrize(
    "line",
    [
        "",
        "not json",
        '{"question": "q"}',
        '{"question": "q", "land_context": {"mode": "all_active", "lands": []}, "expect": "nope"}',
        '{"question": 3, "land_context": {"mode": "all_active", "lands": []}, "expect": "answered"}',
        '{"question": "q", "land_context": {"mode": "bogus", "lands": []}, "expect": "answered"}',
        '{"question": "q", "land_context": {"mode": "all_active", "lands": [], "extra": 1}, "expect": "answered"}',
        '{"question": "q", "land_context": {"mode": "all_active", "lands": [{"id": "x", "extra": 1}]}, "expect": "answered"}',
        '{"question": "q", "land_context": {"mode": "all_active", "lands": [{"id": "   "}]}, "expect": "answered"}',
    ],
)
def test_cli_rejects_a_malformed_eval_line(tmp_path: Path, line: str) -> None:
    evaluation = tmp_path / "eval.jsonl"
    evaluation.write_text(line + "\n", encoding="utf-8")

    result = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--eval", str(evaluation),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 2
    assert result.stdout == ""


def test_cli_rejects_an_eval_file_with_no_questions(tmp_path: Path) -> None:
    evaluation = tmp_path / "eval.jsonl"
    evaluation.write_text("\n\n", encoding="utf-8")

    result = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--eval", str(evaluation),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ("--k", "0"),
        ("--as-of", "not-a-date"),
        ("--catalog", "does_not_exist.json"),
    ],
)
def test_cli_rejects_invalid_arguments(arguments: Tuple[str, ...]) -> None:
    base = ["--catalog", str(fixture("catalog.json")), "--as-of", AS_OF]
    result = run_cli(*base, *arguments)

    assert result.returncode == 2


def test_cli_treats_an_ineligible_catalog_as_stale_not_clarification() -> None:
    result = run_cli(
        "--catalog", str(RETRIEVAL_FIXTURES / "catalog_expired.json"),
        "--passages", str(fixture("passages.json")),
        "--eval", str(fixture("eval_questions.jsonl")),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 0
    assert "corpus: not_current" in result.stdout
    assert "clarifications: 0" in result.stdout
    assert "abstained outcomes: 6" in result.stdout


def test_cli_exits_two_for_a_broken_passage_set(tmp_path: Path) -> None:
    broken = tmp_path / "passages.json"
    broken.write_text('{"schema_version": "passage-set-v1", "passages": [{}]}', encoding="utf-8")

    result = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(broken),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 2
    assert "rejected" in result.stderr
    assert result.stdout == ""


def test_cli_exits_one_when_a_clarification_invariant_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli_module()

    def _leaking_response(needs: Any) -> Dict[str, Any]:
        return {
            "status": "needs_land_clarification",
            "answer": "",
            "sources": [],
            "land_scope": "selected",
            "land_ids_to_choose": ["ghost-land"],
        }

    monkeypatch.setattr(cli, "to_clarification_response", _leaking_response)
    exit_code = cli.main(
        [
            "--catalog", str(fixture("catalog.json")),
            "--passages", str(fixture("passages.json")),
            "--eval", str(fixture("eval_questions.jsonl")),
            "--as-of", AS_OF, "--k", "5",
        ]
    )

    assert exit_code == 1


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"answer": "una respuesta"}, "answer_not_empty"),
        ({"sources": [{"title": "x"}]}, "sources_not_empty"),
        ({"land_ids_to_choose": []}, "land_ids_empty"),
        ({"land_ids_to_choose": ["a", "a"]}, "land_ids_not_unique"),
        ({"land_ids_to_choose": ["ghost"]}, "land_id_not_requested"),
        ({"land_ids_to_choose": ["  "]}, "land_id_blank"),
        ({"status": "answered"}, "status_not_clarification"),
        ({"land_scope": "general"}, "scope_not_selected"),
    ],
)
def test_clarification_invariant_violations_detect_each_leak(
    mutate: Dict[str, Any], expected: str
) -> None:
    cli = load_cli_module()
    payload = to_clarification_response(NeedsLandClarification(("land-A",)))
    payload.update(mutate)

    assert expected in cli.clarification_invariant_violations(payload, ("land-A",))


def test_clarification_invariant_violations_accept_a_clean_payload() -> None:
    cli = load_cli_module()
    payload = to_clarification_response(NeedsLandClarification(("land-A", "land-B")))

    assert cli.clarification_invariant_violations(payload, ("land-A", "land-B")) == ()


# --- fixture hygiene --------------------------------------------------------


def test_fixtures_are_labelled_synthetic() -> None:
    catalog = catalog_document()
    passages = passage_document()

    assert len(catalog["sources"]) == 2
    for source in catalog["sources"]:
        assert "fixture" in source["title"]
        assert "no es una norma real" in source["title"]
    for passage in passages["passages"]:
        assert "Sintético" in passage["text"] or "sintético" in passage["text"]


def test_fixtures_cover_both_applicability_values_and_one_unrestricted_passage() -> None:
    passages = passage_document()["passages"]
    declared = {
        passage["applicability"]["water_regime"]
        for passage in passages
        if passage.get("applicability", {}).get("water_regime")
    }

    assert declared == {"irrigated", "dryland"}
    assert any(not passage.get("applicability") for passage in passages)


def test_eval_file_declares_only_the_three_keys_and_a_documented_expect() -> None:
    for line in eval_lines("eval_questions.jsonl"):
        assert set(line) == {"question", "land_context", "expect"}
        assert line["expect"] in ("answered", "abstained", "needs_land_clarification")
        assert line["land_context"]["mode"] in LAND_SCOPES


def test_eval_file_covers_a_differentiating_pair_and_a_non_differing_pair() -> None:
    lines = eval_lines("eval_questions.jsonl")
    clarifications = [line for line in lines if line["expect"] == "needs_land_clarification"]
    non_clarifications = [line for line in lines if line["expect"] != "needs_land_clarification"]

    assert clarifications
    assert non_clarifications
    differing = clarifications[0]["land_context"]["lands"]
    assert differing[0]["water_regime"] != differing[1]["water_regime"]


def test_accepted_abstention_and_generation_modules_stay_unchanged() -> None:
    # The clarification module composes them; it must not have required a change.
    import app.abstention as abstention_module
    import app.generation as generation_module

    assert hasattr(abstention_module, "answer_or_abstain")
    assert hasattr(generation_module, "to_answer_response")


def test_clarification_does_not_change_the_delegated_payload_bytes() -> None:
    corpus = current_corpus()
    lands = all_active(
        {"id": "land-A", "water_regime": "irrigated"},
        {"id": "land-B", "water_regime": "irrigated"},
    )

    delegated = answer_with_clarification(
        WATER_QUESTION, lands, corpus, k=5, as_of=as_of_date()
    )
    direct = answer_or_abstain(
        WATER_QUESTION, corpus, k=5, land_scope="all_active", as_of=as_of_date()
    )

    assert to_answer_response(delegated) == to_answer_response(direct)
