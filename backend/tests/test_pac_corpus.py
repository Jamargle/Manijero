"""Offline invariants for the approved PAC corpus boundary."""

import json
from datetime import date
from pathlib import Path

from app.deadline_notices import deadline_paragraph
from app.generation import LEAD_IN, MAX_ANSWER_CHARS, NOTICE, extract_numeric_facts
from app.retrieval import RetrievedPassage, Retriever, validate_passage_set
from app.source_catalog import validate_catalog

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_canonical_artifacts_are_valid_and_have_approved_coverage():
    catalog = _json("knowledge/source_catalog.json")
    passages = _json("knowledge/passages.json")
    coverage = (ROOT / "knowledge/pac_coverage.md").read_text(encoding="utf-8")

    assert validate_catalog(catalog, date(2026, 10, 17)).ok
    assert validate_passage_set(passages).ok
    assert len(catalog["sources"]) == 7
    assert len(passages["passages"]) == 9
    assert "Diego" in coverage
    assert "2026-10-17" in coverage
    assert "Aprobada" in coverage
    retriever = Retriever.from_documents(
        catalog, passages, date(2026, 10, 17), active_campaign="2026"
    )
    assert retriever.indexed_passage_count == 9
    results = retriever.search("¿Cuál es el plazo de presentación?")
    assert len(results) > 0


def test_approved_topics_and_exclusions():
    coverage = (ROOT / "knowledge/pac_coverage.md").read_text(encoding="utf-8")
    assert "Canal ordinario de presentación" in coverage
    assert "Fecha final de presentación" in coverage
    assert "Fecha separada de modificación" in coverage
    assert "Elegibilidad individual, importes" in coverage


DEADLINES = {
    "pasaje-plazo-presentacion-2026-andalucia": "2026-05-15",
    "pasaje-plazo-modificacion-2026-andalucia": "2026-06-15",
}


def test_only_the_two_reviewed_deadline_passages_carry_official_deadline():
    catalog = _json("knowledge/source_catalog.json")
    passages = _json("knowledge/passages.json")["passages"]
    campaigns = {source["id"]: source.get("campaign") for source in catalog["sources"]}

    declared = {p["id"]: p["official_deadline"] for p in passages if "official_deadline" in p}
    assert declared == DEADLINES
    for passage in passages:
        value = declared.get(passage["id"])
        if value is None:
            continue
        year, month, day = (int(part) for part in value.split("-"))
        assert str(year) == campaigns[passage["source_id"]]
        assert "dm:{}-{}".format(day, month) in extract_numeric_facts(passage["text"])


def test_every_real_deadline_passage_fits_alone_with_its_worst_case_paragraph():
    passages = _json("knowledge/passages.json")["passages"]
    worst_date = date(2099, 12, 31)
    checked = 0
    for passage in passages:
        if "official_deadline" not in passage:
            continue
        cited = RetrievedPassage(
            passage_id=passage["id"], source_id=passage["source_id"], title="t",
            issuing_body="b", url="u", location=passage["location"],
            published_or_updated_on="2026-01-01", verified_on="2026-01-01",
            excerpt=passage["text"], applicability=None, critical=True, score=1.0, rank=1,
            official_deadline=passage["official_deadline"],
        )
        answer = "{} {} [1] {}".format(LEAD_IN, passage["text"], NOTICE)
        full = answer + "\n\n" + deadline_paragraph([cited], worst_date)
        assert len(full) <= MAX_ANSWER_CHARS
        checked += 1
    assert checked == 2
