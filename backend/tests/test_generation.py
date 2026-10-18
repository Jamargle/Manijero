"""Focused tests for the offline grounded answer-generation pipeline.

The fixtures under ``fixtures/generation/`` are synthetic and clearly labelled:
they are not real legal documents, and their figures, dates, and amounts are
explicitly fictitious examples ("cifra inventada"). They exist only to exercise
the grounding verifier, the extractive generator, the pipeline reason codes, and
the evaluation CLI.

The tests never call a model or the network: the only enabled generator is the
code-composed extractive one, and the recorded "fake generator" drafts in
``drafts_ungrounded.json`` are rejected wholesale rather than trusted.
"""

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

from app.generation import (  # noqa: E402  (path setup must run first)
    ANSWER_SOURCE_KEYS,
    ELIGIBILITY_PHRASES,
    GROUNDING_FAILURE_CODES,
    LEAD_IN,
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    NOTICE,
    POLICY_ISSUE_CODES,
    Answered,
    DraftAnswer,
    ExtractiveGroundingGenerator,
    NotAnswered,
    contains_eligibility_claim,
    extract_figures,
    generate_grounded_answer,
    is_literal_substring,
    split_sentences,
    strip_markers,
    to_answer_response,
    verify_draft,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    RetrievedPassage,
    Retriever,
    load_passage_set,
)
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "evaluate_generation.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "generation"
CANONICAL_CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
EMPTY_CATALOG = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.json"
CONTRACT_EXAMPLE = REPO_ROOT / "contracts" / "examples" / "response-answered.json"
CONTRACT_OPENAPI = REPO_ROOT / "contracts" / "openapi.yaml"

AS_OF = "2026-10-13"

SOLICITUD_QUESTION = "¿Cómo se presenta la solicitud única?"
PLAZO_QUESTION = "¿Cuánto dura el plazo ficticio de prueba?"
IMPORTE_QUESTION = "¿Cuál es el importe ficticio de ejemplo?"
DOCUMENTOS_QUESTION = "¿Cuántos documentos ficticios menciona el ejemplo?"
UNCOVERED_QUESTION = "zzzz qqqq"

SOLICITUD_EXCERPT = (
    "Fragmento sintético de prueba sobre la solicitud única: describe el trámite "
    "anual de forma genérica y no fija ningún plazo ni cuantía real."
)
PLAZO_EXCERPT = (
    "Fragmento sintético de prueba (fixture, cifra inventada): el plazo ficticio de "
    "ejemplo es de 42 días y no corresponde a ningún trámite real."
)


# --- helpers ----------------------------------------------------------------


def fixture(name: str) -> Path:
    return FIXTURES / name


def catalog_document(name: str = "catalog.json"):
    return load_catalog(fixture(name))


def passage_document(name: str = "passages.json"):
    return load_passage_set(fixture(name))


def build_retriever(as_of: str = AS_OF) -> Retriever:
    return Retriever.from_documents(
        catalog_document(),
        passage_document(),
        date.fromisoformat(as_of),
        active_campaign="2026",
    )


def empty_catalog_retriever(as_of: str = AS_OF) -> Retriever:
    return Retriever.from_documents(
        load_catalog(EMPTY_CATALOG),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        date.fromisoformat(as_of),
    )


def numbered_candidates(
    retriever: Retriever, question: str, k: int = DEFAULT_K
) -> Tuple[Tuple[int, RetrievedPassage], ...]:
    return tuple((candidate.rank, candidate) for candidate in retriever.search(question, k=k))


def as_of_date(as_of: str = AS_OF) -> date:
    return date.fromisoformat(as_of)


def make_passage(
    excerpt: str = SOLICITUD_EXCERPT,
    *,
    passage_id: str = "fixture-gen-solicitud-1",
    rank: int = 1,
    critical: bool = False,
) -> RetrievedPassage:
    """Build one candidate directly, so verifier tests do not depend on ranking."""

    return RetrievedPassage(
        passage_id=passage_id,
        source_id="fixture_gen_junta",
        title="Documento sintético de prueba (fixture; no es una norma real)",
        issuing_body="BOE",
        url="https://www.boe.es/buscar/doc.php?id=DOC-FIXTURE-GEN-0002",
        location="Art. 1 (fixture, sintético)",
        published_or_updated_on="2026-02-10",
        verified_on="2026-10-05",
        excerpt=excerpt,
        applicability=None,
        critical=critical,
        score=1.0,
        rank=rank,
    )


def recorded_drafts() -> Dict[str, Any]:
    return json.loads(fixture("drafts_ungrounded.json").read_text(encoding="utf-8"))


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


def source_entry(**overrides: Any) -> dict:
    entry = {
        "id": "fixture_gen_junta",
        "title": "Documento sintético de prueba (fixture; no es una norma real)",
        "issuing_body": "Junta de Andalucía",
        "original_url": "https://www.juntadeandalucia.es/boja/2026/00/FIXTURE-GEN-0001.pdf",
        "published_on": "2026-03-30",
        "downloaded_on": "2026-09-28",
        "verified_on": "2026-10-02",
        "content_sha256": "1" * 64,
        "review_status": "approved",
        "reviewed_by": "fixture reviewer (synthetic, not a real approval)",
        "reviewed_on": "2026-10-03",
        "lifecycle_status": "current",
    }
    entry.update(overrides)
    return entry


@dataclass(frozen=True)
class RecordedGenerator:
    """A stand-in for a future model adapter: it returns a fixed draft."""

    draft: DraftAnswer

    def generate(self, question, numbered_candidates, *, as_of=None) -> DraftAnswer:
        return self.draft


class ExplodingGenerator:
    def generate(self, question, numbered_candidates, *, as_of=None) -> DraftAnswer:
        raise RuntimeError("synthetic generator failure")


class ForbiddenRetriever:
    """Fails the test if the pipeline retrieves at all."""

    def search(self, question: str, k: int = DEFAULT_K):
        raise AssertionError("retrieval must not run")


# --- text helpers -----------------------------------------------------------


def test_split_sentences_keeps_a_trailing_marker_with_its_sentence() -> None:
    sentences = split_sentences("Primera frase. [1] Segunda frase. [2]")

    assert sentences == ("Primera frase. [1]", "Segunda frase. [2]")


def test_split_sentences_handles_text_without_terminal_punctuation() -> None:
    assert split_sentences("una sola frase [3]") == ("una sola frase [3]",)
    assert split_sentences("   ") == ()


def test_strip_markers_removes_markers_without_gluing_words() -> None:
    assert strip_markers("texto final. [1]") == "texto final."
    assert strip_markers("uno [1] dos") == "uno dos"
    assert strip_markers("[2] empieza") == "empieza"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("el plazo es de 42 días", {"42"}),
        ("el importe es de 1.200 euros", {"1200"}),
        ("un 3,5 por ciento", {"3.5"}),
        ("el 50% del total", {"50%"}),
        ("la fecha es 2031-01-01", {"2031-01-01", "2031", "01", "01"}),
        ("la fecha es 01/01/2031", {"2031-01-01", "01", "01", "2031"}),
        ("sin cifras", set()),
    ],
)
def test_extract_figures_normalizes_dates_separators_and_percent(text: str, expected: set) -> None:
    assert set(extract_figures(text)) == expected


def test_extract_figures_never_invents_a_figure() -> None:
    assert extract_figures("") == frozenset()
    assert extract_figures("texto sin números") == frozenset()


@pytest.mark.parametrize("phrase", ELIGIBILITY_PHRASES)
def test_every_starter_eligibility_phrase_is_detected(phrase: str) -> None:
    assert contains_eligibility_claim("Aviso: {} la ayuda.".format(phrase))
    assert contains_eligibility_claim("AVISO: {} LA AYUDA.".format(phrase.upper()))


def test_eligibility_check_is_a_phrase_list_not_a_judge() -> None:
    # Documented limitation: this is a lexical phrase list, not entailment.
    assert not contains_eligibility_claim("La solicitud se presenta cada año.")
    assert not contains_eligibility_claim("derecho al uso del agua")


def test_is_literal_substring_ignores_case_diacritics_and_whitespace() -> None:
    assert is_literal_substring("  EL   PLAZO  ", "el plazo es de prueba")
    assert is_literal_substring("solicitud unica", "la SOLICITUD única anual")
    assert not is_literal_substring("otro texto", "el plazo es de prueba")


# --- the grounding verifier -------------------------------------------------


def test_extractive_draft_on_an_ordinary_passage_passes() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered",
        answer="{} [1]".format(passage.excerpt),
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert report.ok, report.codes()
    assert len(report.claims) == 1
    assert report.claims[0].ok
    assert report.claims[0].markers == (1,)
    assert report.claims[0].text == passage.excerpt


def test_extractive_draft_on_a_critical_passage_passes() -> None:
    passage = make_passage(PLAZO_EXCERPT, critical=True)
    draft = DraftAnswer(status="answered", answer=PLAZO_EXCERPT + " [1]", source_markers=(1,))

    report = verify_draft(draft, ((1, passage),))

    assert report.ok, report.codes()


def test_a_figure_present_in_the_cited_passage_passes() -> None:
    passage = make_passage("Fragmento sintético de prueba: menciona 3 documentos.")
    draft = DraftAnswer(
        status="answered",
        answer="La prueba sintética menciona 3 documentos. [1]",
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert report.ok, report.codes()


@pytest.mark.parametrize(
    "claim",
    [
        "La prueba sintética menciona 99 documentos. [1]",
        "La prueba sintética se presenta el 2031-12-31. [1]",
        "El artículo sintético 77 de prueba se aplica. [1]",
    ],
)
def test_an_invented_figure_date_or_article_number_is_rejected(claim: str) -> None:
    passage = make_passage("Fragmento sintético de prueba: menciona 3 documentos.")
    draft = DraftAnswer(status="answered", answer=claim, source_markers=(1,))

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "figure_unsupported" in report.codes()
    assert not report.claims[0].ok


def test_a_critical_claim_must_be_a_literal_excerpt() -> None:
    passage = make_passage(PLAZO_EXCERPT, critical=True)
    draft = DraftAnswer(
        status="answered",
        answer="El plazo sintético de prueba es de cuarenta y dos días. [1]",
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "critical_not_literal" in report.codes()


def test_a_critical_claim_may_be_a_normalized_literal_excerpt() -> None:
    passage = make_passage("El plazo sintético de prueba es de 42 días.", critical=True)
    draft = DraftAnswer(
        status="answered",
        answer="el   PLAZO sintetico de prueba es de 42 dias. [1]",
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert report.ok, report.codes()


def test_a_policy_claim_is_rejected() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered",
        answer="Tienes derecho a la ayuda sintética de prueba. [1]",
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "eligibility_claim" in report.codes()
    assert not report.claims[0].ok


def test_a_sentence_without_a_marker_is_an_uncited_sentence() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered",
        answer="{} [1] Y una segunda frase sin cita.".format(passage.excerpt),
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "uncited_sentence" in report.codes()


def test_declared_and_inline_markers_must_agree() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered", answer="{} [1]".format(passage.excerpt), source_markers=(2,)
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "marker_mismatch" in report.codes()


def test_a_marker_outside_the_candidate_set_is_rejected() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered", answer="{} [9]".format(passage.excerpt), source_markers=(9,)
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    assert "unknown_marker" in report.codes()


def test_verify_draft_rejects_a_non_draft_object() -> None:
    report = verify_draft("not a draft", ((1, make_passage()),))  # type: ignore[arg-type]

    assert not report.ok
    assert report.codes() == ("incoherent_draft",)


@pytest.mark.parametrize(
    "case_name",
    sorted(json.loads(FIXTURES.joinpath("drafts_ungrounded.json").read_text(encoding="utf-8"))),
)
def test_each_recorded_ungrounded_draft_is_rejected_with_its_expected_code(
    case_name: str,
) -> None:
    case = recorded_drafts()[case_name]
    retriever = build_retriever()
    payload = case["draft"]
    draft = DraftAnswer(
        status=payload["status"],
        answer=payload["answer"],
        source_markers=tuple(payload["source_markers"]),
    )

    report = verify_draft(draft, numbered_candidates(retriever, case["question"]))

    assert not report.ok, case_name
    assert case["expected_issue"] in report.codes(), case_name


def test_every_recorded_draft_case_declares_a_known_issue_code() -> None:
    known = GROUNDING_FAILURE_CODES | POLICY_ISSUE_CODES | {
        "generator_abstained",
        "answer_too_long",
    }

    for name, case in recorded_drafts().items():
        assert case["expected_issue"] in known, name
        # Every recorded case is either an issue code or a documented variant of one.
        assert name == case["expected_issue"] or name.startswith(case["expected_issue"])


def test_rejection_messages_contain_no_question_or_excerpt_text() -> None:
    secret_excerpt = "Texto reservado sintético que no debe aparecer en diagnósticos."
    passage = make_passage(secret_excerpt)
    draft = DraftAnswer(
        status="answered",
        answer=secret_excerpt + " y una cifra inventada 987. [1]",
        source_markers=(1,),
    )

    report = verify_draft(draft, ((1, passage),))

    assert not report.ok
    diagnostics = "\n".join(str(issue) for issue in report.issues)
    assert secret_excerpt not in diagnostics
    assert "987" not in diagnostics
    assert "Textos reservado" not in diagnostics


def test_issue_details_name_only_codes_numbers_and_rules() -> None:
    passage = make_passage()
    draft = DraftAnswer(
        status="answered", answer="{} [9]".format(passage.excerpt), source_markers=(1,)
    )

    report = verify_draft(draft, ((1, passage),))

    details = {issue.code: issue.detail for issue in report.issues}
    assert "9" in details["unknown_marker"]
    assert passage.excerpt not in details["unknown_marker"]
    assert passage.excerpt not in details["marker_mismatch"]


# --- the pipeline -----------------------------------------------------------


def test_covered_question_returns_a_cited_grounded_answer() -> None:
    retriever = build_retriever()
    candidates = numbered_candidates(retriever, SOLICITUD_QUESTION)

    result = generate_grounded_answer(
        SOLICITUD_QUESTION, retriever, k=5, as_of=as_of_date()
    )

    assert isinstance(result, Answered)
    assert result.answer.startswith(LEAD_IN)
    assert result.answer.endswith(NOTICE)
    assert 0 < len(result.answer) <= MAX_ANSWER_CHARS
    assert result.land_scope == "general"
    assert result.sources
    assert result.claims
    returned_ranks = {rank for rank, _ in candidates}
    for claim in result.claims:
        assert claim.ok
        assert claim.markers
        assert set(claim.markers) <= returned_ranks
        cited = [passage for rank, passage in candidates if rank in claim.markers]
        assert any(is_literal_substring(claim.text, passage.excerpt) for passage in cited)
    assert result.cited_markers == tuple(sorted(set(result.cited_markers)))


def test_cited_sources_follow_ascending_candidate_order() -> None:
    retriever = build_retriever()

    result = generate_grounded_answer(PLAZO_QUESTION, retriever, k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert result.cited_markers == (1, 2)
    assert len(result.claims) == 2
    assert [claim.markers for claim in result.claims] == [(1,), (2,)]
    candidates_by_rank = {
        rank: passage
        for rank, passage in numbered_candidates(retriever, PLAZO_QUESTION)
    }
    assert [passage.passage_id for passage in result.sources] == [
        candidates_by_rank[1].passage_id,
        candidates_by_rank[2].passage_id,
    ]


def test_answer_payload_matches_the_accepted_contract_keys() -> None:
    retriever = build_retriever()
    result = generate_grounded_answer(SOLICITUD_QUESTION, retriever, k=5, as_of=as_of_date())
    assert isinstance(result, Answered)

    payload = to_answer_response(result)
    example = json.loads(CONTRACT_EXAMPLE.read_text(encoding="utf-8"))

    assert set(payload) == set(example) == {
        "status",
        "answer",
        "sources",
        "land_scope",
        "land_ids_to_choose",
    }
    assert payload["status"] == "answered"
    assert payload["land_scope"] == "general"
    assert payload["land_ids_to_choose"] == []
    assert payload["sources"]
    for source in payload["sources"]:
        assert set(source) == set(example["sources"][0]) == set(ANSWER_SOURCE_KEYS)
    assert isinstance(payload["answer"], str) and len(payload["answer"]) <= 1200


def test_contract_declares_the_same_answer_bound() -> None:
    openapi = CONTRACT_OPENAPI.read_text(encoding="utf-8")

    assert "maxLength: 1200" in openapi
    assert "maxLength: 2000" in openapi
    assert MAX_ANSWER_CHARS == 1200
    assert MAX_QUESTION_CHARS == 2000


def test_answer_uses_the_pinned_lead_in_and_notice_without_any_digit() -> None:
    retriever = build_retriever()

    result = generate_grounded_answer(SOLICITUD_QUESTION, retriever, k=5, as_of=as_of_date())

    assert isinstance(result, Answered)
    assert LEAD_IN in result.answer
    assert NOTICE in result.answer
    assert not any(character.isdigit() for character in LEAD_IN)
    assert not any(character.isdigit() for character in NOTICE)


def test_no_candidates_for_an_out_of_vocabulary_question() -> None:
    result = generate_grounded_answer(
        UNCOVERED_QUESTION, build_retriever(), k=5, as_of=as_of_date()
    )

    assert result == NotAnswered("no_candidates")
    assert not hasattr(result, "answer")


def test_no_candidates_for_an_empty_catalog() -> None:
    result = generate_grounded_answer(
        SOLICITUD_QUESTION, empty_catalog_retriever(), k=5, as_of=as_of_date()
    )

    assert result == NotAnswered("no_candidates")
    assert not hasattr(result, "answer")


@pytest.mark.parametrize(
    "question",
    ["", "   ", "\n\t ", None, "x" * (MAX_QUESTION_CHARS + 1)],
)
def test_invalid_question_never_retrieves_or_generates(question: Optional[str]) -> None:
    result = generate_grounded_answer(
        question,  # type: ignore[arg-type]
        ForbiddenRetriever(),  # type: ignore[arg-type]
        k=5,
        as_of=as_of_date(),
        generator=ExplodingGenerator(),
    )

    assert isinstance(result, NotAnswered)
    assert result.reason == "invalid_question"
    assert result.codes() == (
        "question_too_long" if question is not None and len(question) > MAX_QUESTION_CHARS else
        "blank_question",
    )


def test_a_question_of_exactly_the_contract_limit_is_retrieved() -> None:
    retriever = build_retriever()
    question = SOLICITUD_QUESTION + " " * (MAX_QUESTION_CHARS - len(SOLICITUD_QUESTION))
    assert len(question) == MAX_QUESTION_CHARS

    result = generate_grounded_answer(question, retriever, k=5, as_of=as_of_date())

    assert isinstance(result, Answered)


def test_max_claims_limits_the_number_of_claims() -> None:
    retriever = build_retriever()

    result = generate_grounded_answer(
        PLAZO_QUESTION, retriever, k=5, max_claims=1, as_of=as_of_date()
    )

    assert isinstance(result, Answered)
    assert len(result.claims) == 1
    assert result.cited_markers == (1,)


def test_assembly_drops_trailing_claims_until_the_payload_fits() -> None:
    retriever = build_retriever()
    candidates = numbered_candidates(retriever, PLAZO_QUESTION)
    first = candidates[0][1]
    overlong_second_claim = "palabra " * 140
    draft = DraftAnswer(
        status="answered",
        answer="{} [1] {} [2]".format(first.excerpt, overlong_second_claim),
        source_markers=(1, 2),
    )
    assert len(draft.answer) > MAX_ANSWER_CHARS

    result = generate_grounded_answer(
        PLAZO_QUESTION,
        retriever,
        k=5,
        as_of=as_of_date(),
        generator=RecordedGenerator(draft),
    )

    assert isinstance(result, Answered)
    assert len(result.answer) <= MAX_ANSWER_CHARS
    assert len(result.claims) == 1
    assert result.cited_markers == (1,)
    assert overlong_second_claim not in result.answer


def test_a_single_claim_that_cannot_fit_returns_not_answered() -> None:
    retriever = build_retriever()
    draft = DraftAnswer(
        status="answered", answer="palabra " * 140 + "[1]", source_markers=(1,)
    )

    result = generate_grounded_answer(
        SOLICITUD_QUESTION,
        retriever,
        k=5,
        as_of=as_of_date(),
        generator=RecordedGenerator(draft),
    )

    assert isinstance(result, NotAnswered)
    assert result.reason == "grounding_failed"
    assert "answer_too_long" in result.codes()


def test_the_notice_plus_one_claim_is_the_1200_boundary() -> None:
    passage = make_passage()
    budget = MAX_ANSWER_CHARS - len(LEAD_IN) - len(NOTICE) - len(" [1]") - 2
    fits = DraftAnswer(status="answered", answer="a" * budget + " [1]", source_markers=(1,))
    too_long = DraftAnswer(
        status="answered", answer="a" * (budget + 1) + " [1]", source_markers=(1,)
    )

    assert verify_draft(fits, ((1, passage),)).ok
    report = verify_draft(too_long, ((1, passage),))
    assert not report.ok
    assert "answer_too_long" in report.codes()


def test_generator_abstention_is_a_reason_code() -> None:
    draft = DraftAnswer(status="abstained", answer="", source_markers=())

    result = generate_grounded_answer(
        SOLICITUD_QUESTION,
        build_retriever(),
        k=5,
        as_of=as_of_date(),
        generator=RecordedGenerator(draft),
    )

    assert isinstance(result, NotAnswered)
    assert result.reason == "generator_abstained"
    assert "generator_abstained" in result.codes()


def test_generator_error_is_a_reason_code_without_a_fallback() -> None:
    result = generate_grounded_answer(
        SOLICITUD_QUESTION,
        build_retriever(),
        k=5,
        as_of=as_of_date(),
        generator=ExplodingGenerator(),
    )

    assert isinstance(result, NotAnswered)
    assert result.reason == "generation_error"
    assert result.codes() == ("generator_error",)
    assert "RuntimeError" in result.issues[0].detail


def test_a_policy_violation_is_reported_as_policy_failed() -> None:
    draft = DraftAnswer(
        status="answered",
        answer="Tienes derecho a la ayuda sintética de prueba. [1]",
        source_markers=(1,),
    )

    result = generate_grounded_answer(
        SOLICITUD_QUESTION,
        build_retriever(),
        k=5,
        as_of=as_of_date(),
        generator=RecordedGenerator(draft),
    )

    assert isinstance(result, NotAnswered)
    assert result.reason == "policy_failed"
    assert "eligibility_claim" in result.codes()


def test_a_rejected_draft_emits_no_text_at_all() -> None:
    secret = "Marcador reservado sintético que no debe emitirse."
    draft = DraftAnswer(
        status="answered",
        answer="{} Tienes derecho a la ayuda 4242. [1]".format(secret),
        source_markers=(1,),
    )

    result = generate_grounded_answer(
        SOLICITUD_QUESTION,
        build_retriever(),
        k=5,
        as_of=as_of_date(),
        generator=RecordedGenerator(draft),
    )

    assert isinstance(result, NotAnswered)
    assert not hasattr(result, "answer")
    assert "4242" not in json.dumps(
        [issue.detail for issue in result.issues], ensure_ascii=False
    )


def test_pipeline_is_deterministic() -> None:
    runs = []
    for _ in range(2):
        retriever = build_retriever()
        result = generate_grounded_answer(
            PLAZO_QUESTION, retriever, k=5, as_of=as_of_date()
        )
        assert isinstance(result, Answered)
        runs.append(
            (
                result.answer,
                tuple((claim.text, claim.markers) for claim in result.claims),
                tuple(passage.passage_id for passage in result.sources),
                result.cited_markers,
                to_answer_response(result),
            )
        )

    assert runs[0] == runs[1]


def test_pipeline_never_opens_a_network_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("generation must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    result = generate_grounded_answer(
        SOLICITUD_QUESTION, build_retriever(), k=5, as_of=as_of_date()
    )
    payload = to_answer_response(result)  # type: ignore[arg-type]

    assert payload["status"] == "answered"


def test_generation_module_imports_no_network_client() -> None:
    source = (BACKEND_ROOT / "app" / "generation.py").read_text(encoding="utf-8")

    for forbidden in ("import socket", "import urllib", "import httpx", "import requests"):
        assert forbidden not in source


@pytest.mark.parametrize("land_scope", ["planet", "", "GENERAL"])
def test_invalid_land_scope_is_rejected(land_scope: str) -> None:
    with pytest.raises(ValueError):
        generate_grounded_answer(
            SOLICITUD_QUESTION,
            build_retriever(),
            k=5,
            land_scope=land_scope,
            as_of=as_of_date(),
        )

    passage = make_passage()
    answered = Answered(answer="texto", claims=(), sources=(passage,), land_scope=land_scope)
    with pytest.raises(ValueError):
        to_answer_response(answered)


def test_to_answer_response_rejects_an_over_long_or_sourceless_answer() -> None:
    passage = make_passage()
    with pytest.raises(ValueError):
        to_answer_response(
            Answered(answer="a" * (MAX_ANSWER_CHARS + 1), claims=(), sources=(passage,))
        )
    with pytest.raises(ValueError):
        to_answer_response(Answered(answer="a" * MAX_ANSWER_CHARS, claims=(), sources=()))
    with pytest.raises(ValueError):
        to_answer_response(Answered(answer="   ", claims=(), sources=(passage,)))


def test_answered_answer_may_be_exactly_the_contract_bound() -> None:
    passage = make_passage()

    payload = to_answer_response(
        Answered(answer="a" * MAX_ANSWER_CHARS, claims=(), sources=(passage,))
    )

    assert len(payload["answer"]) == MAX_ANSWER_CHARS


# --- evaluation CLI ---------------------------------------------------------


def test_cli_prints_a_per_claim_grounding_report() -> None:
    result = baseline_cli()

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "grounding invariants are enforced" in result.stdout
    assert "claim 1: ok; cites [1]" in result.stdout
    assert "ungrounded claims: 0" in result.stdout
    assert "invented sources: 0" in result.stdout
    assert "no-evidence outcomes: 1" in result.stdout
    assert "grounding invariants hold: yes" in result.stdout
    assert LEAD_IN in result.stdout
    assert NOTICE in result.stdout


def test_cli_json_mode_is_machine_readable() -> None:
    result = baseline_cli("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["as_of"] == AS_OF
    assert report["k"] == 5
    assert report["fixtures_are_synthetic"] is True
    assert report["thresholds_are_release_gates"] is False
    assert report["index"] == {
        "eligible_sources": 2,
        "indexed_passages": 4,
        "excluded_passages_ineligible_source": 0,
    }
    assert report["grounding_invariants_hold"] is True
    assert report["totals"] == {
        "questions": 6,
        "answers_produced": 5,
        "claims_checked": 8,
        "ungrounded_claims": 0,
        "invented_sources": 0,
        "no_evidence_outcomes": 1,
        "grounding_invariant_failures": 0,
        "outcomes_differing_from_expect": 0,
    }
    answered = [item for item in report["questions"] if item["outcome"] == "answered"]
    assert len(answered) == 5
    for item in answered:
        assert item["answer"]
        assert item["claims"]
        assert all(claim["ok"] for claim in item["claims"])
        assert item["issue_codes"] == []
    no_evidence = [item for item in report["questions"] if item["outcome"] == "no_candidates"]
    assert len(no_evidence) == 1
    assert no_evidence[0]["answer"] is None


def test_cli_run_is_deterministic() -> None:
    first = baseline_cli("--json")
    second = baseline_cli("--json")

    assert first.stdout == second.stdout
    assert first.returncode == second.returncode == 0


def test_cli_empty_corpus_reports_no_answers() -> None:
    result = run_cli(
        "--catalog", str(EMPTY_CATALOG), "--as-of", AS_OF, "--k", "5"
    )

    assert result.returncode == 0, result.stderr
    assert "eligible sources: 0" in result.stdout
    assert "indexed passages: 0" in result.stdout
    assert "no evaluation questions supplied" in result.stdout


def test_cli_fail_on_miss_is_off_by_default_and_opt_in_is_exit_one(
    tmp_path: Path,
) -> None:
    missed = tmp_path / "missed.jsonl"
    missed.write_text(
        json.dumps(
            {
                "question": UNCOVERED_QUESTION,
                "expected_passage_ids": ["fixture-gen-solicitud-1"],
                "expect": "answered",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    default = baseline_cli("--eval", str(missed))
    strict = baseline_cli("--eval", str(missed), "--fail-on-miss")

    assert default.returncode == 0
    assert strict.returncode == 1
    assert strict.stdout == default.stdout
    assert "outcomes differing from expect: 1" in strict.stdout


def test_cli_exits_one_when_a_grounding_invariant_fails(tmp_path: Path) -> None:
    passages = tmp_path / "passages.json"
    passages.write_text(
        json.dumps(
            {
                "schema_version": PASSAGE_SET_SCHEMA_VERSION,
                "passages": [
                    {
                        "id": "fixture-gen-policy-1",
                        "source_id": "fixture_gen_junta",
                        "location": "Art. 9 (fixture, sintético)",
                        "text": (
                            "Fragmento sintético de prueba (fixture): tienes derecho a la "
                            "ayuda ficticia y no afirma nada real."
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evaluation = tmp_path / "eval.jsonl"
    evaluation.write_text(
        json.dumps(
            {
                "question": "¿A qué ayuda ficticia da derecho el fragmento?",
                "expected_passage_ids": ["fixture-gen-policy-1"],
                "expect": "answered",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_cli(
        "--catalog",
        str(fixture("catalog.json")),
        "--passages",
        str(passages),
        "--eval",
        str(evaluation),
        "--as-of",
        AS_OF,
        "--active-campaign",
        "2026",
        "--k",
        "5",
    )

    assert result.returncode == 1
    assert "grounding invariants hold: no" in result.stdout
    assert "eligibility_claim" in result.stdout
    assert "ungrounded claims: 1" in result.stdout


def test_cli_rejects_an_unknown_expected_passage_id(tmp_path: Path) -> None:
    broken = tmp_path / "unknown_id.jsonl"
    broken.write_text(
        json.dumps(
            {
                "question": SOLICITUD_QUESTION,
                "expected_passage_ids": ["fixture-gen-does-not-exist"],
                "expect": "answered",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = baseline_cli("--eval", str(broken))

    assert result.returncode == 2
    assert "not in the built index" in result.stderr
    assert "fixture-gen-does-not-exist" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize(
    "line",
    [
        '{"question": "q", "expected_passage_ids": ["fixture-gen-solicitud-1"], "expect": "answered", "extra": 1}',
        '{"question": "q", "expected_passage_ids": ["fixture-gen-solicitud-1"]}',
        '{"question": "  ", "expected_passage_ids": ["fixture-gen-solicitud-1"], "expect": "answered"}',
        '{"question": "q", "expected_passage_ids": [], "expect": "answered"}',
        '{"question": "q", "expected_passage_ids": ["fixture-gen-solicitud-1"], "expect": "maybe"}',
    ],
)
def test_cli_rejects_a_malformed_eval_line(tmp_path: Path, line: str) -> None:
    broken = tmp_path / "eval.jsonl"
    broken.write_text(line + "\n", encoding="utf-8")

    result = baseline_cli("--eval", str(broken))

    assert result.returncode == 2
    assert "error:" in result.stderr
    assert result.stdout == ""


def test_cli_rejects_a_non_positive_window() -> None:
    result = baseline_cli("--k", "0")

    assert result.returncode == 2
    assert "--k must be a positive integer" in result.stderr


def test_cli_rejects_an_invalid_as_of() -> None:
    result = run_cli("--catalog", str(fixture("catalog.json")), "--as-of", "not-a-date")

    assert result.returncode == 2
    assert "--as-of must be a real calendar date" in result.stderr


def test_cli_rejects_an_ineligible_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog_expired.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": "source-catalog-v1",
                "sources": [source_entry(valid_until="2026-01-01")],
            }
        ),
        encoding="utf-8",
    )

    result = run_cli("--catalog", str(catalog), "--as-of", AS_OF, "--k", "5")

    assert result.returncode == 2
    assert "valid_until" in result.stderr
    assert result.stdout == ""


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


# --- fixture hygiene --------------------------------------------------------


def test_generation_fixtures_are_labelled_synthetic() -> None:
    catalog = catalog_document()
    passages = passage_document()

    assert len(catalog["sources"]) == 2
    for source in catalog["sources"]:
        assert "fixture" in source["title"]
        assert "no es una norma real" in source["title"]
    for passage in passages["passages"]:
        assert "sintético" in passage["text"] or "sintetico" in passage["text"]
        assert "prueba" in passage["text"]


def test_generation_fixtures_label_every_fictitious_figure() -> None:
    for passage in passage_document()["passages"]:
        if any(character.isdigit() for character in passage["text"]):
            assert "cifra inventada" in passage["text"] or "fixture" in passage["text"]


def test_generation_fixtures_exercise_a_critical_figure_passage() -> None:
    passages = passage_document()["passages"]
    critical = [p for p in passages if p.get("critical")]
    ordinary = [p for p in passages if not p.get("critical")]

    assert critical
    assert ordinary
    assert any(any(character.isdigit() for character in p["text"]) for p in critical)


def test_evaluation_questions_cover_answered_and_no_evidence_outcomes() -> None:
    lines = [
        json.loads(line)
        for line in fixture("eval_questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(lines) == 6
    assert {line["expect"] for line in lines} == {"answered", "no_candidates"}
    indexed_ids = {
        passage["id"] for passage in passage_document()["passages"]
    }
    for line in lines:
        assert set(line) == {"question", "expected_passage_ids", "expect"}
        assert set(line["expected_passage_ids"]) <= indexed_ids
