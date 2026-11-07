"""Code-owned deadline notices: sentences, paragraph rules, fitting, validation."""

import dataclasses
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.deadline_notices import (  # noqa: E402
    CODE_OWNED_MARKERS,
    COOPERATIVE,
    MONTHS,
    deadline_paragraph,
    format_spanish_date,
)
from app.generation import (  # noqa: E402
    LEAD_IN,
    MAX_ANSWER_CHARS,
    NOTICE,
    Answered,
    DraftAnswer,
    NotAnswered,
    answer_source,
    generate_grounded_answer,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    PASSAGE_SET_SCHEMA_VERSION,
    RetrievedPassage,
    validate_passage_set,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSED = " ".join(["El plazo oficial terminó el 15 de mayo de 2031."])


def passage(
    excerpt: str = "Texto sintético sin cifras.",
    *,
    rank: int = 1,
    deadline: Optional[str] = None,
) -> RetrievedPassage:
    return RetrievedPassage(
        passage_id="fixture-deadline-{}".format(rank),
        source_id="fixture_deadline",
        title="Documento sintético",
        issuing_body="BOE",
        url="https://www.boe.es/buscar/doc.php?id=DOC-FIXTURE",
        location="Art. {}".format(rank),
        published_or_updated_on="2031-01-10",
        verified_on="2031-01-11",
        excerpt=excerpt,
        applicability=None,
        critical=False,
        score=1.0,
        rank=rank,
        official_deadline=deadline,
    )


class StaticRetriever:
    def __init__(self, *candidates: RetrievedPassage) -> None:
        self._candidates = candidates

    def search(self, question: str, k: int = DEFAULT_K) -> Tuple[RetrievedPassage, ...]:
        return self._candidates[:k]


def answer(retriever: StaticRetriever, as_of: Optional[date], **kwargs):
    return generate_grounded_answer("pregunta", retriever, as_of=as_of, **kwargs)


# --- sentences and formatting ------------------------------------------------


def test_the_pinned_sentence_is_exact() -> None:
    assert COOPERATIVE == (
        "Tu cooperativa o entidad colaboradora puede tener una fecha anterior "
        "al plazo oficial: pregúntale primero."
    )


def test_every_month_formats_lowercase_and_the_first_day_has_no_zero() -> None:
    assert len(MONTHS) == 12
    for month, name in enumerate(MONTHS, start=1):
        assert format_spanish_date(date(2031, month, 1)) == "1 de {} de 2031".format(name)
        assert name == name.lower()
    assert format_spanish_date(date(2031, 5, 15)) == "15 de mayo de 2031"


def test_code_owned_markers_are_normalized() -> None:
    assert all(marker == marker.lower() and "ó" not in marker for marker in CODE_OWNED_MARKERS)
    assert len(CODE_OWNED_MARKERS) == 2


# --- paragraph rules (scenarios 1-4) -----------------------------------------


@pytest.mark.parametrize("as_of", [date(2031, 5, 15), date(2031, 1, 1), None])
def test_an_open_or_unknown_date_adds_only_the_cooperative_sentence(as_of) -> None:
    assert deadline_paragraph([passage(deadline="2031-05-15")], as_of) == COOPERATIVE


def test_the_day_after_the_deadline_adds_the_exact_end_date() -> None:
    paragraph = deadline_paragraph([passage(deadline="2031-05-15")], date(2031, 5, 16))

    assert paragraph == PASSED + " " + COOPERATIVE


def test_several_deadlines_are_deduplicated_ordered_and_closed_once() -> None:
    passages = [
        passage(rank=1, deadline="2031-06-15"),
        passage(rank=2, deadline="2031-05-15"),
        passage(rank=3, deadline="2031-05-15"),
    ]

    paragraph = deadline_paragraph(passages, date(2031, 7, 1))

    assert paragraph == (
        "El plazo oficial terminó el 15 de mayo de 2031. "
        "El plazo oficial terminó el 15 de junio de 2031. " + COOPERATIVE
    )


def test_only_the_passed_deadline_gets_an_expired_sentence() -> None:
    passages = [passage(rank=1, deadline="2031-05-15"), passage(rank=2, deadline="2031-06-15")]

    paragraph = deadline_paragraph(passages, date(2031, 5, 20))

    assert paragraph == PASSED + " " + COOPERATIVE


def test_no_reviewed_date_means_no_paragraph() -> None:
    text = "Se presentará hasta el 15 de mayo de 2031."

    assert deadline_paragraph([passage(text)], date(2032, 1, 1)) == ""
    assert deadline_paragraph([], date(2032, 1, 1)) == ""


# --- assembly (scenarios 2, 4, 6, 7) -----------------------------------------


def test_a_cited_passed_deadline_ends_the_answer_with_its_own_paragraph() -> None:
    cited = passage("Se presenta hasta el 15 de mayo de 2031.", deadline="2031-05-15")

    result = answer(StaticRetriever(cited), date(2031, 5, 16))

    assert isinstance(result, Answered)
    base = "{} Se presenta hasta el 15 de mayo de 2031. [1] {}".format(LEAD_IN, NOTICE)
    assert result.answer == base + "\n\n" + PASSED + " " + COOPERATIVE
    assert result.answer.count("[") == 1


def test_a_cited_text_date_without_metadata_is_byte_identical_to_today() -> None:
    plain = passage("Se presenta hasta el 15 de mayo de 2031.")

    result = answer(StaticRetriever(plain), date(2032, 1, 1))

    assert isinstance(result, Answered)
    assert result.answer == "{} Se presenta hasta el 15 de mayo de 2031. [1] {}".format(
        LEAD_IN, NOTICE
    )


def test_a_retrieved_but_uncited_deadline_adds_nothing() -> None:
    first = passage("Primera frase sin cifras.", rank=1)
    second = passage("Segunda frase sin cifras.", rank=2, deadline="2031-05-15")

    result = answer(StaticRetriever(first, second), date(2032, 1, 1), max_claims=1)

    assert isinstance(result, Answered)
    assert "\n" not in result.answer and COOPERATIVE not in result.answer


def test_the_notice_skips_the_numeric_check_but_the_draft_is_verified_first() -> None:
    cited = passage("El plazo finalizará el 15 de junio, inclusive.", deadline="2031-06-15")

    result = answer(StaticRetriever(cited), date(2031, 6, 16))

    assert isinstance(result, Answered)
    assert "El plazo oficial terminó el 15 de junio de 2031." in result.answer

    class AddsYear:
        def generate(self, question, numbered_candidates, *, as_of=None):
            return DraftAnswer("answered", "El plazo finalizará el 15 de junio de 2031. [1]", (1,))

    rejected = answer(StaticRetriever(cited), date(2031, 6, 16), generator=AddsYear())
    assert isinstance(rejected, NotAnswered)


def _filler(length: int) -> str:
    return "x" * (length - 1) + "."


def _overhead(*texts: str) -> int:
    claims = " ".join("{} [{}]".format(text, rank) for rank, text in enumerate(texts, 1))
    return len("{} {} {}".format(LEAD_IN, claims, NOTICE))


def test_a_trailing_claim_is_dropped_and_the_paragraph_recomputed_to_fit() -> None:
    first_text = _filler(200)
    second_length = MAX_ANSWER_CHARS - 5 - _overhead(first_text, "")
    second_text = _filler(second_length)
    assert _overhead(first_text, second_text) == MAX_ANSWER_CHARS - 5
    first = passage(first_text, rank=1)
    second = passage(second_text, rank=2, deadline="2031-05-15")

    open_result = answer(StaticRetriever(first, second), date(2031, 1, 1))
    assert isinstance(open_result, Answered)
    assert len(open_result.answer) <= MAX_ANSWER_CHARS
    assert [source.rank for source in open_result.sources] == [1]
    assert "\n" not in open_result.answer and COOPERATIVE not in open_result.answer


def test_the_first_claim_plus_its_paragraph_that_cannot_fit_abstains() -> None:
    text = _filler(MAX_ANSWER_CHARS - 5 - _overhead(""))
    cited = passage(text, deadline="2031-05-15")

    open_result = answer(StaticRetriever(cited), date(2031, 1, 1))

    assert isinstance(open_result, NotAnswered)
    assert open_result.reason == "grounding_failed"
    assert "answer_too_long" in open_result.codes()
    without = answer(StaticRetriever(passage(text)), date(2031, 1, 1))
    assert isinstance(without, Answered) and len(without.answer) <= MAX_ANSWER_CHARS


# --- validation (scenario 8) -------------------------------------------------


def _document(value) -> dict:
    return {
        "schema_version": PASSAGE_SET_SCHEMA_VERSION,
        "passages": [
            {
                "id": "pasaje-uno",
                "source_id": "fuente-uno",
                "location": "Art. 1",
                "text": "Texto.",
                "official_deadline": value,
            }
        ],
    }


@pytest.mark.parametrize("value", ["2026-05-15", "2028-02-29"])
def test_a_real_iso_date_validates(value: str) -> None:
    assert validate_passage_set(_document(value)).ok


@pytest.mark.parametrize(
    "value",
    ["2026-02-30", "15/05/2026", None, "20260515", "2026-5-15", "2026-05-15\n", 20260515, ""],
)
def test_anything_else_is_reported_at_the_key(value) -> None:
    report = validate_passage_set(_document(value))

    assert [issue.location for issue in report.issues] == ["$.passages[0].official_deadline"]


def test_the_field_stays_retrieval_local() -> None:
    fields = [field.name for field in dataclasses.fields(RetrievedPassage)]
    assert fields[-1] == "official_deadline"
    assert "official_deadline" not in answer_source(passage())
    schema = json.loads((REPO_ROOT / "knowledge" / "passages.schema.json").read_text("utf-8"))
    assert "official_deadline" in schema["$defs"]["passage"]["properties"]
