"""Focused tests for the offline safe-abstention decisions.

The fixtures under ``fixtures/abstention/`` are synthetic and clearly labelled:
they are not real legal documents, and their figures are explicitly fictitious
examples ("cifra inventada"), including an impossible ``999/2099`` reference
that belongs to no real instrument. They exist only to exercise the abstention
taxonomy, the pre-checks, the pinned copy, and the evaluation CLI.

The tests never call a model or the network: the only enabled generator is the
accepted code-composed extractive one, and every recorded "fake generator" draft
is discarded wholesale rather than trusted.
"""

import dataclasses
import importlib.util
import json
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.abstention import (  # noqa: E402  (path setup must run first)
    ABSTENTION_MESSAGES,
    ABSTENTION_REASONS,
    CRITICAL_UNITS,
    GENERATION_REASON_MAP,
    INSTRUMENT_KEYWORDS,
    Abstention,
    UnitConflict,
    abstention_from_generation,
    answer_or_abstain,
    find_unit_conflict,
    has_unsupported_presupposition,
    prepare_corpus,
    presupposed_identifiers,
    to_abstention_response,
    unit_values,
)
from app.generation import (  # noqa: E402
    ELIGIBILITY_PHRASES,
    LAND_SCOPES,
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    Answered,
    ClaimVerdict,
    DraftAnswer,
    GroundingIssue,
    NotAnswered,
    extract_figures,
    generate_grounded_answer,
    to_answer_response,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    CatalogRejectedError,
    PassageSetError,
    RetrievedPassage,
    Retriever,
    load_passage_set,
)
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "evaluate_abstention.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "abstention"
RETRIEVAL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval"
GENERATION_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "generation"
CANONICAL_CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
EMPTY_CATALOG = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.json"
CONTRACT_EXAMPLE = REPO_ROOT / "contracts" / "examples" / "response-abstained.json"
CONTRACT_OPENAPI = REPO_ROOT / "contracts" / "openapi.yaml"

AS_OF = "2026-10-13"

SOLICITUD_QUESTION = "¿Qué explica la solicitud anual?"
NORMA_QUESTION = "¿Qué dice la norma ficticia?"
PLAZO_QUESTION = "¿Cuánto dura el plazo ficticio de prueba?"
IMPORTE_QUESTION = "¿Cuál es el importe ficticio de ejemplo?"
RIEGO_QUESTION = "¿Qué se explica sobre el riego?"
AYUDA_QUESTION = "¿A qué ayuda ficticia da derecho el fragmento de prueba?"
FALSE_PREMISE_QUESTION = (
    "¿Qué dice el Real Decreto sintético de prueba sobre la solicitud anual?"
)
NUMBERED_FALSE_PREMISE_QUESTION = "¿Qué regula el reglamento 999/2099 sobre el riego?"
UNCOVERED_QUESTION = "zzzz qqqq"

# A distinctly non-fixture sentence used to prove that no diagnostics echo it.
SECRET_EXCERPT = "Texto reservado sintético que no debe aparecer en diagnósticos."


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
        catalog_document(),
        passage_document(),
        as_of_date(as_of),
        active_campaign="2026",
    )


def current_corpus(as_of: str = AS_OF) -> Retriever:
    corpus = prepare_corpus(
        catalog_document(), passage_document(), as_of_date(as_of), "2026"
    )
    assert isinstance(corpus, Retriever)
    return corpus


def generation_retriever() -> Retriever:
    return Retriever.from_documents(
        load_catalog(GENERATION_FIXTURES / "catalog.json"),
        load_passage_set(GENERATION_FIXTURES / "passages.json"),
        as_of_date(),
        active_campaign="2026",
    )


def make_passage(
    excerpt: str,
    *,
    passage_id: str = "fixture-abs-a-1",
    critical: bool = False,
    rank: int = 1,
) -> RetrievedPassage:
    """Build one candidate directly, so unit tests do not depend on ranking."""

    return RetrievedPassage(
        passage_id=passage_id,
        source_id="fixture_abs_boe",
        title="Documento sintético de prueba (fixture; no es una norma real)",
        issuing_body="BOE",
        url="https://www.boe.es/buscar/doc.php?id=DOC-FIXTURE-ABS-0002",
        location="Art. 9 (fixture, sintético)",
        published_or_updated_on="2026-02-10",
        verified_on="2026-10-05",
        excerpt=excerpt,
        applicability=None,
        critical=critical,
        score=1.0,
        rank=rank,
    )


class RecordingRetriever(Retriever):
    """A retriever that records every search it receives, in order."""

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner
        self.queries: list = []
        self.results: list = []

    def search(self, question: str, k: int = DEFAULT_K):
        self.queries.append((question, k))
        result = self._inner.search(question, k=k)
        self.results.append(result)
        return result


class RecordingGenerator:
    """A stand-in for a future model adapter: records its calls and returns a draft."""

    def __init__(self, draft: DraftAnswer) -> None:
        self.draft = draft
        self.calls = 0

    def generate(self, question, numbered_candidates, *, as_of=None) -> DraftAnswer:
        self.calls += 1
        return self.draft


class ExplodingGenerator:
    def generate(self, question, numbered_candidates, *, as_of=None) -> DraftAnswer:
        raise RuntimeError("synthetic generator failure")


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
        "--active-campaign",
        "2026",
        "--k",
        "5",
        *extra,
    )


def stale_cli(*extra: str) -> subprocess.CompletedProcess:
    return run_cli(
        "--catalog",
        str(RETRIEVAL_FIXTURES / "catalog_expired.json"),
        "--eval",
        str(fixture("eval_questions_stale.jsonl")),
        "--as-of",
        AS_OF,
        "--k",
        "5",
        *extra,
    )


def load_cli_module():
    """Load the CLI script as a module so its pure helpers can be unit-tested."""

    spec = importlib.util.spec_from_file_location("evaluate_abstention_cli", CLI)
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


# --- taxonomy and pinned copy -----------------------------------------------


def test_taxonomy_lists_the_documented_reasons_in_order() -> None:
    assert ABSTENTION_REASONS == (
        "invalid_question",
        "no_evidence",
        "insufficient_evidence",
        "stale_evidence",
        "conflicting_evidence",
        "false_premise",
        "unsafe_request",
        "generator_abstained",
        "generation_error",
    )
    assert tuple(ABSTENTION_MESSAGES) == ABSTENTION_REASONS


def test_every_reason_has_exactly_one_pinned_message() -> None:
    assert set(ABSTENTION_MESSAGES) == set(ABSTENTION_REASONS)
    assert len(set(ABSTENTION_MESSAGES.values())) == len(ABSTENTION_REASONS)


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_every_pinned_message_is_short_plain_and_digitless(reason: str) -> None:
    message = ABSTENTION_MESSAGES[reason]

    assert message.strip()
    assert len(message) <= MAX_ANSWER_CHARS
    assert not any(character.isdigit() for character in message)
    assert extract_figures(message) == frozenset()


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_no_pinned_message_contains_an_eligibility_phrase(reason: str) -> None:
    for phrase in ELIGIBILITY_PHRASES:
        assert phrase not in ABSTENTION_MESSAGES[reason].lower()


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_every_pinned_message_offers_a_next_step(reason: str) -> None:
    message = ABSTENTION_MESSAGES[reason].lower()

    assert (
        "oficina comarcal agraria" in message
        or "cooperativa" in message
        or "inténtalo otra vez" in message
    )


def test_abstention_has_no_copy_field() -> None:
    names = {field.name for field in dataclasses.fields(Abstention)}

    assert names == {"reason", "generation_reason", "issues", "claims"}
    assert not {"answer", "text", "message", "sources"}.intersection(names)


def test_abstention_message_resolves_from_the_taxonomy() -> None:
    for reason in ABSTENTION_REASONS:
        assert Abstention(reason=reason).message == ABSTENTION_MESSAGES[reason]


def test_abstention_rejects_an_unknown_reason() -> None:
    with pytest.raises(ValueError):
        Abstention(reason="not_a_reason")


def test_abstention_carries_generation_traceability() -> None:
    issue = GroundingIssue("uncited_sentence", "a sentence carries no citation marker")
    claim = ClaimVerdict(text="texto", markers=(1,), ok=False, issues=(issue,))
    abstention = Abstention(
        reason="insufficient_evidence",
        generation_reason="grounding_failed",
        issues=(issue,),
        claims=(claim,),
    )

    assert abstention.generation_reason == "grounding_failed"
    assert abstention.codes() == ("uncited_sentence",)
    assert abstention.claims == (claim,)


def test_abstention_is_immutable() -> None:
    abstention = Abstention(reason="no_evidence")

    with pytest.raises(dataclasses.FrozenInstanceError):
        abstention.reason = "unsafe_request"  # type: ignore[misc]


# --- generation reason mapping ----------------------------------------------


@pytest.mark.parametrize("generation_reason,mapped", sorted(GENERATION_REASON_MAP.items()))
def test_generation_reasons_map_into_the_taxonomy(generation_reason: str, mapped: str) -> None:
    assert mapped in ABSTENTION_REASONS

    abstention = abstention_from_generation(NotAnswered(generation_reason))

    assert abstention.reason == mapped
    assert abstention.generation_reason == generation_reason


def test_every_accepted_generation_reason_is_mapped() -> None:
    assert set(GENERATION_REASON_MAP) == {
        "invalid_question",
        "no_candidates",
        "grounding_failed",
        "policy_failed",
        "generator_abstained",
        "generation_error",
    }


def test_unmapped_generation_reason_fails_closed_to_generation_error() -> None:
    abstention = abstention_from_generation(NotAnswered("something_new"))

    assert abstention.reason == "generation_error"
    assert abstention.generation_reason == "something_new"


def test_abstention_from_generation_preserves_issues_and_claims() -> None:
    issue = GroundingIssue("figure_unsupported", "a figure is absent from the cited passage")
    claim = ClaimVerdict(text="texto", markers=(1,), ok=False, issues=(issue,))
    result = NotAnswered("grounding_failed", (issue,), (claim,))

    abstention = abstention_from_generation(result)

    assert abstention.reason == "insufficient_evidence"
    assert abstention.issues == (issue,)
    assert abstention.claims == (claim,)
    assert abstention.codes() == ("figure_unsupported",)


def test_abstention_from_generation_rejects_an_answered_result() -> None:
    answered = Answered(answer="texto", claims=(), sources=())

    with pytest.raises(ValueError):
        abstention_from_generation(answered)  # type: ignore[arg-type]


# --- contract-shaped payload ------------------------------------------------


def test_abstention_payload_has_exactly_the_contract_keys() -> None:
    payload = to_abstention_response(Abstention(reason="no_evidence"))

    assert set(payload) == {
        "status",
        "answer",
        "sources",
        "land_scope",
        "land_ids_to_choose",
    }
    assert payload["status"] == "abstained"
    assert payload["sources"] == []
    assert payload["land_ids_to_choose"] == []
    assert payload["land_scope"] == "general"
    assert payload["answer"] == ABSTENTION_MESSAGES["no_evidence"]


def test_abstention_payload_matches_the_accepted_example_shape() -> None:
    example = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))

    payload = to_abstention_response(Abstention(reason="stale_evidence"))

    assert set(payload) == set(example)


@pytest.mark.parametrize("land_scope", LAND_SCOPES)
def test_abstention_payload_echoes_a_valid_land_scope(land_scope: str) -> None:
    payload = to_abstention_response(Abstention(reason="no_evidence"), land_scope=land_scope)

    assert payload["land_scope"] == land_scope


@pytest.mark.parametrize("land_scope", ["planet", "", "GENERAL"])
def test_abstention_payload_rejects_an_unknown_land_scope(land_scope: str) -> None:
    with pytest.raises(ValueError):
        to_abstention_response(Abstention(reason="no_evidence"), land_scope=land_scope)


def test_to_abstention_response_rejects_a_non_abstention() -> None:
    with pytest.raises(ValueError):
        to_abstention_response("no es una abstención")  # type: ignore[arg-type]


def test_to_abstention_response_rejects_an_unknown_reason() -> None:
    abstention = Abstention(reason="no_evidence")
    object.__setattr__(abstention, "reason", "not_a_reason")

    with pytest.raises(ValueError):
        to_abstention_response(abstention)


@pytest.mark.parametrize("reason", ABSTENTION_REASONS)
def test_no_abstention_payload_carries_sources_ids_or_figures(reason: str) -> None:
    payload = to_abstention_response(Abstention(reason=reason))

    assert payload["sources"] == []
    assert payload["land_ids_to_choose"] == []
    assert payload["status"] == "abstained"
    assert not any(character.isdigit() for character in payload["answer"])
    assert extract_figures(payload["answer"]) == frozenset()
    assert len(payload["answer"]) <= MAX_ANSWER_CHARS


# --- corpus preparation -----------------------------------------------------


def test_prepare_corpus_returns_a_retriever_for_the_current_fixture() -> None:
    corpus = prepare_corpus(catalog_document(), passage_document(), as_of_date(), "2026")

    assert isinstance(corpus, Retriever)
    assert corpus.eligible_source_count == 2
    assert corpus.indexed_passage_count == 7


@pytest.mark.parametrize(
    "catalog_name",
    ["catalog_expired.json", "catalog_not_approved.json", "catalog_not_current.json"],
)
def test_prepare_corpus_abstains_stale_for_an_ineligible_catalog(catalog_name: str) -> None:
    catalog = load_catalog(RETRIEVAL_FIXTURES / catalog_name)

    corpus = prepare_corpus(catalog, {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []}, as_of_date())

    assert isinstance(corpus, Abstention)
    assert corpus.reason == "stale_evidence"
    assert corpus.codes() == ("stale_corpus",)
    payload = to_abstention_response(corpus)
    assert payload["status"] == "abstained"
    assert payload["sources"] == []


def test_prepare_corpus_allows_an_empty_catalog() -> None:
    corpus = prepare_corpus(
        load_catalog(EMPTY_CATALOG),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        as_of_date(),
    )

    assert isinstance(corpus, Retriever)
    assert corpus.eligible_source_count == 0
    assert corpus.indexed_passage_count == 0


def test_prepare_corpus_raises_for_an_unknown_source_id() -> None:
    passage_document = load_passage_set(RETRIEVAL_FIXTURES / "passages_unknown_source.json")

    with pytest.raises(PassageSetError):
        prepare_corpus(catalog_document(), passage_document, as_of_date())


def test_prepare_corpus_raises_for_a_malformed_passage_set() -> None:
    malformed = load_passage_set(RETRIEVAL_FIXTURES / "passages_unknown_key.json")

    with pytest.raises(PassageSetError):
        prepare_corpus(catalog_document(), malformed, as_of_date())


def test_prepare_corpus_propagates_an_unreadable_passage_file() -> None:
    with pytest.raises(PassageSetError):
        load_passage_set(RETRIEVAL_FIXTURES / "passages_malformed.json")


def test_prepare_corpus_rejects_a_structurally_broken_catalog() -> None:
    broken = {"schema_version": "source-catalog-v1", "sources": ["no es un objeto"]}

    with pytest.raises(CatalogRejectedError):
        prepare_corpus(broken, {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []}, as_of_date())


def test_prepare_corpus_never_opens_a_network_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("corpus preparation must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    corpus = prepare_corpus(catalog_document(), passage_document(), as_of_date(), "2026")

    assert isinstance(corpus, Retriever)


# --- false premise ----------------------------------------------------------


@pytest.mark.parametrize("keyword", INSTRUMENT_KEYWORDS)
def test_presupposed_identifiers_find_each_documented_instrument(keyword: str) -> None:
    identifiers = presupposed_identifiers("¿Qué dice el {} de prueba?".format(keyword))

    assert keyword in identifiers


@pytest.mark.parametrize(
    "question,identifier",
    [
        ("¿Qué dice el real decreto 123/2099?", "real decreto 123/2099"),
        ("¿Qué dice la ley 7/2022?", "ley 7/2022"),
        ("¿Qué dice la norma n.º 5?", "norma 5"),
        ("¿Qué dice el artículo 55?", "articulo 55"),
    ],
)
def test_presupposed_identifiers_find_numbered_references(
    question: str, identifier: str
) -> None:
    assert identifier in presupposed_identifiers(question)


def test_presupposed_identifiers_ignore_an_ordinary_question() -> None:
    assert presupposed_identifiers(SOLICITUD_QUESTION) == ()
    assert presupposed_identifiers(PLAZO_QUESTION) == ()
    assert presupposed_identifiers(UNCOVERED_QUESTION) == ()


def test_presupposed_identifiers_normalize_case_and_diacritics() -> None:
    assert presupposed_identifiers("¿QUÉ DICE LA NORMA?") == ("norma",)
    assert presupposed_identifiers("¿Qué dice el ARTÍCULO 9?") == ("articulo 9",)


def test_an_identifier_present_in_a_candidate_is_not_flagged() -> None:
    candidates = (make_passage("Sintético de prueba: esta norma ficticia no es real."),)

    assert not has_unsupported_presupposition(NORMA_QUESTION, candidates)
    assert not has_unsupported_presupposition(UNCOVERED_QUESTION, candidates)


def test_an_identifier_absent_from_candidates_is_flagged() -> None:
    candidates = (make_passage("Sintético de prueba sobre la solicitud anual."),)

    assert has_unsupported_presupposition(FALSE_PREMISE_QUESTION, candidates)
    assert has_unsupported_presupposition(NUMBERED_FALSE_PREMISE_QUESTION, candidates)


def test_an_identifier_may_be_found_in_the_candidate_location() -> None:
    candidate = make_passage(
        "Sintético de prueba sin nombres propios.", passage_id="fixture-abs-loc-1"
    )
    located = dataclasses.replace(candidate, location="Norma ficticia de prueba (sintético)")

    assert not has_unsupported_presupposition(NORMA_QUESTION, (located,))
    assert has_unsupported_presupposition(NORMA_QUESTION, (candidate,))


def test_false_premise_question_retrieves_candidates_and_abstains_false_premise() -> None:
    corpus = current_corpus()

    candidates = corpus.search(FALSE_PREMISE_QUESTION, k=5)
    assert candidates

    result = answer_or_abstain(FALSE_PREMISE_QUESTION, corpus, k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "false_premise"
    assert result.generation_reason is None
    assert result.codes() == ("unconfirmed_presupposition",)
    assert "real decreto" not in to_abstention_response(result)["answer"].lower()


def test_numbered_false_premise_question_abstains() -> None:
    result = answer_or_abstain(
        NUMBERED_FALSE_PREMISE_QUESTION, current_corpus(), k=5, as_of=as_of_date()
    )

    assert isinstance(result, Abstention)
    assert result.reason == "false_premise"


def test_a_confirmed_identifier_fixture_question_still_answers() -> None:
    result = answer_or_abstain(NORMA_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert "norma" in result.answer


# --- unit-anchored conflicts ------------------------------------------------


@pytest.mark.parametrize(
    "text,unit,value",
    [
        ("el plazo es de 30 días", "días", "30"),
        ("el plazo es de 3 meses", "meses", "3"),
        ("la antigüedad es de 5 años", "años", "5"),
        ("el importe es de 1.200 euros", "euros", "1200"),
        ("la finca tiene 2 hectáreas", "hectáreas", "2"),
        ("el plazo es de 4 semanas", "semanas", "4"),
        ("un 50% del total", "%", "50"),
    ],
)
def test_unit_values_extract_each_documented_unit(text: str, unit: str, value: str) -> None:
    assert (unit, value) in unit_values(text)


def test_unit_values_ignore_units_outside_the_documented_list() -> None:
    assert unit_values("la finca tiene 3 olivos y 2 siglos de historia") == ()
    assert unit_values("sin ninguna cifra") == ()
    assert unit_values("") == ()


def test_unit_values_normalize_thousands_separators_and_decimal_commas() -> None:
    assert unit_values("1.200 euros") == (("euros", "1200"),)
    assert unit_values("3,5 meses") == (("meses", "3.5"),)
    assert unit_values("1.000.000 euros") == (("euros", "1000000"),)
    assert unit_values("1.200,50 euros") == (("euros", "1200.50"),)


def test_find_unit_conflict_detects_two_critical_candidates_on_the_same_unit() -> None:
    candidates = (
        make_passage("el plazo ficticio es de 30 días", critical=True, rank=1),
        make_passage(
            "el plazo ficticio es de 45 días",
            passage_id="fixture-abs-b-1",
            critical=True,
            rank=2,
        ),
    )

    conflict = find_unit_conflict(candidates)

    assert conflict == UnitConflict(unit="días", values=("30", "45"))


def test_find_unit_conflict_ignores_non_critical_candidates() -> None:
    candidates = (
        make_passage("el plazo ficticio es de 30 días", critical=False, rank=1),
        make_passage(
            "el plazo ficticio es de 45 días",
            passage_id="fixture-abs-b-1",
            critical=False,
            rank=2,
        ),
    )

    assert find_unit_conflict(candidates) is None


def test_find_unit_conflict_ignores_different_units() -> None:
    candidates = (
        make_passage("el plazo ficticio es de 30 días", critical=True, rank=1),
        make_passage(
            "el importe ficticio es de 1.200 euros",
            passage_id="fixture-abs-b-1",
            critical=True,
            rank=2,
        ),
    )

    assert find_unit_conflict(candidates) is None


def test_find_unit_conflict_only_inspects_the_citation_window() -> None:
    candidates = (
        make_passage("el plazo ficticio es de 30 días", critical=True, rank=1),
        make_passage(
            "el plazo ficticio no declara ninguna cifra",
            passage_id="fixture-abs-b-1",
            critical=False,
            rank=2,
        ),
        make_passage(
            "el plazo ficticio es de 45 días",
            passage_id="fixture-abs-c-1",
            critical=True,
            rank=3,
        ),
    )

    assert find_unit_conflict(candidates, max_claims=2) is None
    assert find_unit_conflict(candidates, max_claims=3) is not None


def test_find_unit_conflict_ignores_two_values_inside_one_candidate() -> None:
    candidates = (
        make_passage("el plazo ficticio está entre 30 días y 45 días", critical=True, rank=1),
    )

    assert find_unit_conflict(candidates) is None


def test_find_unit_conflict_returns_none_for_no_candidates() -> None:
    assert find_unit_conflict(()) is None


def test_conflicting_fixture_question_abstains_conflicting_evidence() -> None:
    result = answer_or_abstain(PLAZO_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "conflicting_evidence"
    assert result.generation_reason is None
    assert result.codes() == ("unit_conflict",)
    payload = to_abstention_response(result)
    assert payload["sources"] == []
    assert extract_figures(payload["answer"]) == frozenset()


def test_critical_candidates_on_different_units_still_answer() -> None:
    result = answer_or_abstain(IMPORTE_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert any(source.critical for source in result.sources)


# --- the decision pipeline --------------------------------------------------


def test_out_of_corpus_question_abstains_no_evidence() -> None:
    result = answer_or_abstain(UNCOVERED_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "no_evidence"
    assert result.generation_reason == "no_candidates"
    payload = to_abstention_response(result)
    assert payload["status"] == "abstained"
    assert payload["sources"] == []
    assert payload["land_ids_to_choose"] == []


@pytest.mark.parametrize("question", ["", "   ", "a" * (MAX_QUESTION_CHARS + 1)])
def test_invalid_question_abstains_invalid_question(question: str) -> None:
    result = answer_or_abstain(question, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "invalid_question"


def test_a_question_of_exactly_the_contract_limit_is_retrieved() -> None:
    # A one-character question of the accepted bound is a valid question, not an
    # invalid one; it simply has no lexical match in the fixture corpus.
    result = answer_or_abstain("a" * MAX_QUESTION_CHARS, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "no_evidence"


def test_invalid_question_never_searches() -> None:
    retriever = RecordingRetriever(build_retriever())

    answer_or_abstain("   ", retriever, k=5, as_of=as_of_date())

    assert retriever.queries == []


def test_no_evidence_never_calls_the_generator() -> None:
    generator = RecordingGenerator(
        DraftAnswer(status="answered", answer="texto [1]", source_markers=(1,))
    )

    result = answer_or_abstain(
        UNCOVERED_QUESTION, current_corpus(), k=5, as_of=as_of_date(), generator=generator
    )

    assert isinstance(result, Abstention)
    assert result.reason == "no_evidence"
    assert generator.calls == 0


def test_insufficient_evidence_keeps_the_generation_reason_and_issues() -> None:
    result = answer_or_abstain(RIEGO_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "insufficient_evidence"
    assert result.generation_reason == "grounding_failed"
    assert "uncited_sentence" in result.codes()
    assert to_abstention_response(result)["answer"] == ABSTENTION_MESSAGES["insufficient_evidence"]


def test_unsafe_request_maps_policy_failed() -> None:
    result = answer_or_abstain(AYUDA_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "unsafe_request"
    assert result.generation_reason == "policy_failed"
    assert "eligibility_claim" in result.codes()


def test_generator_abstention_discards_its_copy() -> None:
    generator = RecordingGenerator(
        DraftAnswer(status="abstained", answer="No lo sé, pero podría decir otra cosa.", source_markers=())
    )

    result = answer_or_abstain(
        SOLICITUD_QUESTION, current_corpus(), k=5, as_of=as_of_date(), generator=generator
    )

    assert isinstance(result, Abstention)
    assert result.reason == "generator_abstained"
    assert result.generation_reason == "generator_abstained"
    payload = to_abstention_response(result)
    assert "podría decir otra cosa" not in payload["answer"]
    assert payload["answer"] == ABSTENTION_MESSAGES["generator_abstained"]


def test_generator_error_maps_to_generation_error() -> None:
    result = answer_or_abstain(
        SOLICITUD_QUESTION,
        current_corpus(),
        k=5,
        as_of=as_of_date(),
        generator=ExplodingGenerator(),
    )

    assert isinstance(result, Abstention)
    assert result.reason == "generation_error"
    assert result.generation_reason == "generation_error"


def test_generator_returning_a_non_draft_maps_to_generation_error() -> None:
    class NotADraftGenerator:
        def generate(self, question, numbered_candidates, *, as_of=None):
            return "no es un borrador"

    result = answer_or_abstain(
        SOLICITUD_QUESTION,
        current_corpus(),
        k=5,
        as_of=as_of_date(),
        generator=NotADraftGenerator(),  # type: ignore[arg-type]
    )

    assert isinstance(result, Abstention)
    assert result.reason == "generation_error"


def test_answered_result_is_returned_unchanged() -> None:
    result = answer_or_abstain(SOLICITUD_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert result.land_scope == "general"
    payload = to_answer_response(result)
    assert payload["status"] == "answered"
    assert payload["sources"]


def test_pipeline_searches_the_same_candidates_the_generator_receives() -> None:
    retriever = RecordingRetriever(build_retriever())

    result = answer_or_abstain(NORMA_QUESTION, retriever, k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert retriever.queries == [(NORMA_QUESTION, 5), (NORMA_QUESTION, 5)]
    assert retriever.results[0] == retriever.results[1]
    assert [tuple(item.rank for item in batch) for batch in retriever.results][0] == [
        tuple(item.rank for item in batch) for batch in retriever.results
    ][1]


def test_a_stale_corpus_abstains_for_every_question() -> None:
    corpus = prepare_corpus(
        load_catalog(RETRIEVAL_FIXTURES / "catalog_expired.json"),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        as_of_date(),
    )
    assert isinstance(corpus, Abstention)

    for question in (SOLICITUD_QUESTION, PLAZO_QUESTION, UNCOVERED_QUESTION):
        result = answer_or_abstain(question, corpus, k=5, as_of=as_of_date())
        assert isinstance(result, Abstention)
        assert result.reason == "stale_evidence"
        payload = to_abstention_response(result)
        assert payload["sources"] == []
        assert payload["answer"] == ABSTENTION_MESSAGES["stale_evidence"]


def test_a_stale_corpus_wins_over_an_invalid_question() -> None:
    corpus = prepare_corpus(
        load_catalog(RETRIEVAL_FIXTURES / "catalog_not_current.json"),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        as_of_date(),
    )

    result = answer_or_abstain("   ", corpus, k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "stale_evidence"
    assert result.generation_reason is None


@pytest.mark.parametrize("land_scope", ["planet", "", "GENERAL"])
def test_answer_or_abstain_rejects_an_unknown_land_scope(land_scope: str) -> None:
    with pytest.raises(ValueError):
        answer_or_abstain(
            SOLICITUD_QUESTION,
            current_corpus(),
            k=5,
            land_scope=land_scope,
            as_of=as_of_date(),
        )


def test_answer_or_abstain_rejects_a_non_retriever_corpus() -> None:
    with pytest.raises(ValueError):
        answer_or_abstain(SOLICITUD_QUESTION, "no es un corpus", k=5, as_of=as_of_date())  # type: ignore[arg-type]


def test_pipeline_is_deterministic() -> None:
    runs = []
    for _ in range(2):
        corpus = current_corpus()
        for question in (PLAZO_QUESTION, UNCOVERED_QUESTION, FALSE_PREMISE_QUESTION):
            result = answer_or_abstain(question, corpus, k=5, as_of=as_of_date())
            assert isinstance(result, Abstention)
            runs.append(
                (question, result.reason, result.generation_reason, result.codes(), to_abstention_response(result))
            )

    assert runs[len(runs) // 2 :] == runs[: len(runs) // 2]


def test_pipeline_abstains_without_a_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("abstention must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    result = answer_or_abstain(UNCOVERED_QUESTION, current_corpus(), k=5, as_of=as_of_date())

    assert isinstance(result, Abstention)
    assert result.reason == "no_evidence"


def test_abstention_module_imports_no_network_client() -> None:
    source = (BACKEND_ROOT / "app" / "abstention.py").read_text(encoding="utf-8")

    for forbidden in ("import socket", "import urllib", "import httpx", "import requests"):
        assert forbidden not in source


def test_decision_diagnostics_never_echo_question_or_excerpt_text() -> None:
    generator = RecordingGenerator(
        DraftAnswer(
            status="answered",
            answer="{} y una cifra inventada 987. [1]".format(SECRET_EXCERPT),
            source_markers=(1,),
        )
    )

    result = answer_or_abstain(
        SOLICITUD_QUESTION,
        current_corpus(),
        k=5,
        as_of=as_of_date(),
        generator=generator,
    )

    assert isinstance(result, Abstention)
    diagnostics = "\n".join(str(issue) for issue in result.issues)
    assert SECRET_EXCERPT not in diagnostics
    assert "987" not in diagnostics
    assert SOLICITUD_QUESTION not in diagnostics
    assert to_abstention_response(result)["answer"] == ABSTENTION_MESSAGES[result.reason]


# --- evaluation CLI ---------------------------------------------------------


def test_cli_prints_a_per_question_decision_report() -> None:
    result = baseline_cli()

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "abstention invariants are enforced" in result.stdout
    assert "corpus: current" in result.stdout
    assert "answered outcomes: 3" in result.stdout
    assert "abstained outcomes: 7" in result.stdout
    assert "abstentions with sources: 0" in result.stdout
    assert "abstentions with figures: 0" in result.stdout
    assert "abstention invariants hold: yes" in result.stdout
    assert "outcomes differing from expect: 0" in result.stdout
    assert ABSTENTION_MESSAGES["conflicting_evidence"] in result.stdout
    assert ABSTENTION_MESSAGES["no_evidence"] in result.stdout


def test_cli_reports_the_generation_reason_and_issue_codes() -> None:
    result = baseline_cli()

    assert "generation reason: policy_failed" in result.stdout
    assert "issues: eligibility_claim" in result.stdout
    assert "generation reason: grounding_failed" in result.stdout
    assert "issues: uncited_sentence" in result.stdout
    assert "generation reason: (none)" in result.stdout


def test_cli_output_never_prints_a_passage_excerpt() -> None:
    result = baseline_cli()

    assert "cifra inventada" not in result.stdout
    assert "no corresponde a ningún trámite real" not in result.stdout
    assert "el plazo ficticio de ejemplo" not in result.stdout


def test_cli_json_report_is_machine_readable() -> None:
    result = baseline_cli("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["as_of"] == AS_OF
    assert report["k"] == 5
    assert report["fixtures_are_synthetic"] is True
    assert report["thresholds_are_release_gates"] is False
    assert report["corpus_status"] == "current"
    assert report["index"] == {
        "eligible_sources": 2,
        "indexed_passages": 7,
        "excluded_passages_ineligible_source": 0,
    }
    assert report["abstention_invariants_hold"] is True
    assert report["totals"] == {
        "questions": 10,
        "answered": 3,
        "abstained": 7,
        "abstentions_with_sources": 0,
        "abstentions_with_figures": 0,
        "abstention_invariant_failures": 0,
        "outcomes_differing_from_expect": 0,
    }
    abstained = [item for item in report["questions"] if item["outcome"] != "answered"]
    assert len(abstained) == 7
    for item in abstained:
        assert item["message"] == ABSTENTION_MESSAGES[item["reason"]]
        assert item["sources"] == 0
        assert item["land_ids_to_choose"] == []
        assert item["violated_invariants"] == []
    answered = [item for item in report["questions"] if item["outcome"] == "answered"]
    assert len(answered) == 3
    for item in answered:
        assert item["message"] is None
        assert item["sources"] >= 1


def test_cli_run_is_deterministic() -> None:
    first = baseline_cli("--json")
    second = baseline_cli("--json")

    assert first.stdout == second.stdout
    assert first.returncode == second.returncode == 0


def test_cli_stale_catalog_abstains_for_every_question() -> None:
    result = stale_cli("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["corpus_status"] == "not_current"
    assert report["index"] == {
        "eligible_sources": 0,
        "indexed_passages": 0,
        "excluded_passages_ineligible_source": 0,
    }
    assert report["totals"]["questions"] == 3
    assert report["totals"]["answered"] == 0
    assert report["totals"]["abstained"] == 3
    assert report["totals"]["outcomes_differing_from_expect"] == 0
    assert {item["outcome"] for item in report["questions"]} == {"stale_evidence"}
    for item in report["questions"]:
        assert item["generation_reason"] is None
        assert item["issue_codes"] == ["stale_corpus"]


def test_cli_fail_on_miss_is_off_by_default_and_opt_in_is_exit_one(
    tmp_path: Path,
) -> None:
    missed = tmp_path / "missed.jsonl"
    missed.write_text(
        json.dumps({"question": UNCOVERED_QUESTION, "expect": "answered"}) + "\n",
        encoding="utf-8",
    )

    default = baseline_cli("--eval", str(missed))
    strict = baseline_cli("--eval", str(missed), "--fail-on-miss")

    assert default.returncode == 0
    assert strict.returncode == 1
    assert strict.stdout == default.stdout
    assert "outcomes differing from expect: 1" in strict.stdout


@pytest.mark.parametrize(
    "line",
    [
        '{"question": "q", "expect": "answered", "extra": 1}',
        '{"question": "q"}',
        '{"question": 7, "expect": "answered"}',
        '{"question": "q", "expect": "maybe"}',
        '{"question": "q", "expect": "no_candidates"}',
        'not json at all',
    ],
)
def test_cli_rejects_a_malformed_eval_line(tmp_path: Path, line: str) -> None:
    broken = tmp_path / "eval.jsonl"
    broken.write_text(line + "\n", encoding="utf-8")

    result = baseline_cli("--eval", str(broken))

    assert result.returncode == 2
    assert "error:" in result.stderr
    assert result.stdout == ""


def test_cli_rejects_an_eval_file_with_no_questions(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n   \n", encoding="utf-8")

    result = baseline_cli("--eval", str(empty))

    assert result.returncode == 2
    assert "no questions" in result.stderr
    assert result.stdout == ""


def test_cli_rejects_a_non_positive_window() -> None:
    result = baseline_cli("--k", "0")

    assert result.returncode == 2
    assert "--k must be a positive integer" in result.stderr


def test_cli_rejects_an_invalid_as_of() -> None:
    result = run_cli("--catalog", str(fixture("catalog.json")), "--as-of", "not-a-date")

    assert result.returncode == 2
    assert "--as-of must be a real calendar date" in result.stderr


def test_cli_rejects_a_missing_catalog() -> None:
    result = run_cli("--catalog", str(fixture("does_not_exist.json")), "--as-of", AS_OF)

    assert result.returncode == 2
    assert "cannot read catalog file" in result.stderr


def test_cli_rejects_a_missing_passage_file() -> None:
    result = run_cli(
        "--catalog", str(fixture("catalog.json")), "--passages", str(fixture("nope.json"))
    )

    assert result.returncode == 2
    assert "cannot read passage set file" in result.stderr


def test_cli_rejects_a_malformed_passage_set(tmp_path: Path) -> None:
    broken = tmp_path / "passages.json"
    broken.write_text(
        json.dumps({"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": [{"id": "x"}]}),
        encoding="utf-8",
    )

    result = run_cli(
        "--catalog", str(fixture("catalog.json")), "--passages", str(broken), "--as-of", AS_OF
    )

    assert result.returncode == 2
    assert "rejected" in result.stderr
    assert result.stdout == ""


def test_cli_exits_one_when_an_abstention_invariant_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.abstention as abstention_module

    monkeypatch.setitem(
        abstention_module.ABSTENTION_MESSAGES,
        "no_evidence",
        "No he encontrado nada; el plazo ficticio es de 42 días.",
    )
    evaluation = tmp_path / "eval.jsonl"
    evaluation.write_text(
        json.dumps({"question": UNCOVERED_QUESTION, "expect": "no_evidence"}) + "\n",
        encoding="utf-8",
    )

    cli = load_cli_module()
    exit_code = cli.main(
        [
            "--catalog",
            str(fixture("catalog.json")),
            "--passages",
            str(fixture("passages.json")),
            "--eval",
            str(evaluation),
            "--as-of",
            AS_OF,
            "--k",
            "5",
        ]
    )

    assert exit_code == 1


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"sources": [{"title": "x"}]}, "sources_not_empty"),
        ({"land_ids_to_choose": ["land-1"]}, "land_ids_not_empty"),
        ({"answer": "   "}, "blank_message"),
        ({"answer": "a" * (MAX_ANSWER_CHARS + 1)}, "message_too_long"),
        ({"answer": "Consulta en 3 días."}, "message_has_digit"),
        ({"answer": "Consulta el 2031-01-01."}, "message_has_figure_or_date"),
        ({"status": "answered"}, "status_not_abstained"),
    ],
)
def test_abstention_invariant_violations_detect_each_leak(
    mutate: Dict[str, Any], expected: str
) -> None:
    cli = load_cli_module()
    abstention = Abstention(reason="no_evidence")
    payload = to_abstention_response(abstention)
    payload.update(mutate)

    assert expected in cli.abstention_invariant_violations(payload, abstention)


def test_abstention_invariant_violations_accept_a_clean_payload() -> None:
    cli = load_cli_module()

    for reason in ABSTENTION_REASONS:
        abstention = Abstention(reason=reason)
        assert cli.abstention_invariant_violations(to_abstention_response(abstention), abstention) == ()


# --- fixture hygiene --------------------------------------------------------


def test_abstention_fixtures_are_labelled_synthetic() -> None:
    catalog = catalog_document()
    passages = passage_document()

    assert len(catalog["sources"]) == 2
    for source in catalog["sources"]:
        assert "fixture" in source["title"]
        assert "no es una norma real" in source["title"]
    for passage in passages["passages"]:
        assert "Sintético" in passage["text"] or "sintetico" in passage["text"]
        assert "prueba" in passage["text"]


def test_abstention_fixture_figures_are_labelled_fictitious() -> None:
    for passage in passage_document()["passages"]:
        if any(character.isdigit() for character in passage["text"]):
            assert "cifra inventada" in passage["text"]


def test_abstention_fixtures_conflict_on_one_critical_unit() -> None:
    critical = [p for p in passage_document()["passages"] if p.get("critical")]
    values: Dict[str, set] = {}
    for passage in critical:
        for unit, value in unit_values(passage["text"]):
            values.setdefault(unit, set()).add(value)

    assert len(critical) == 3
    assert {"30", "45"} <= values["días"]
    assert {"1200"} <= values["euros"]


def test_abstention_eval_files_declare_only_question_and_expect() -> None:
    for name in ("eval_questions.jsonl", "eval_questions_stale.jsonl"):
        lines = eval_lines(name)
        assert lines
        for line in lines:
            assert set(line) == {"question", "expect"}


def test_abstention_eval_file_expectations_are_in_the_taxonomy() -> None:
    known = {"answered"} | set(ABSTENTION_REASONS)

    for name in ("eval_questions.jsonl", "eval_questions_stale.jsonl"):
        for line in eval_lines(name):
            assert line["expect"] in known


def test_current_eval_file_covers_the_pre_checks_and_the_pipeline() -> None:
    expects = {line["expect"] for line in eval_lines("eval_questions.jsonl")}

    assert expects == {
        "answered",
        "no_evidence",
        "insufficient_evidence",
        "conflicting_evidence",
        "false_premise",
        "unsafe_request",
        "invalid_question",
    }


def test_stale_eval_file_expects_stale_evidence_only() -> None:
    lines = eval_lines("eval_questions_stale.jsonl")

    assert len(lines) == 3
    assert {line["expect"] for line in lines} == {"stale_evidence"}


def test_the_numbered_false_premise_fixture_uses_an_impossible_identifier() -> None:
    numbered = [
        line["question"] for line in eval_lines("eval_questions.jsonl") if "999/2099" in line["question"]
    ]

    assert len(numbered) == 1
    assert "2099" in numbered[0]


# --- regression against the accepted generation fixtures --------------------


def generation_eval_lines() -> Tuple[Dict[str, Any], ...]:
    return tuple(
        json.loads(raw)
        for raw in (GENERATION_FIXTURES / "eval_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if raw.strip()
    )


@pytest.mark.parametrize(
    "question,expect",
    [(line["question"], line["expect"]) for line in generation_eval_lines()],
)
def test_accepted_generation_questions_still_resolve_through_the_pipeline(
    question: str, expect: str
) -> None:
    result = answer_or_abstain(question, generation_retriever(), k=5, as_of=as_of_date())

    if expect == "answered":
        assert isinstance(result, Answered)
    else:
        assert isinstance(result, Abstention)
        assert result.reason == "no_evidence"


def test_covered_critical_question_with_two_units_answers() -> None:
    # The accepted generation fixture passes a fictional deadline in días and a
    # fictional amount in euros through the extractive pipeline. They are not a
    # conflict, so this feature must not over-abstain on it.
    result = answer_or_abstain(
        PLAZO_QUESTION, generation_retriever(), k=5, as_of=as_of_date()
    )

    assert isinstance(result, Answered)


def test_generate_grounded_answer_is_still_importable_and_guarded() -> None:
    # The accepted pipeline is imported, never re-implemented: a direct call
    # still returns a guarded result carrying an accepted reason code.
    direct = generate_grounded_answer(
        PLAZO_QUESTION, generation_retriever(), k=5, as_of=as_of_date()
    )

    assert isinstance(direct, (Answered, NotAnswered))
    if isinstance(direct, NotAnswered):
        assert direct.reason in {
            "invalid_question",
            "no_candidates",
            "generator_abstained",
            "grounding_failed",
            "policy_failed",
            "generation_error",
        }
