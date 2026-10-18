"""Offline invariants for the candidate PAC corpus boundary."""

import json
from datetime import date
from pathlib import Path

from app.retrieval import Retriever, validate_passage_set
from app.source_catalog import validate_catalog

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_canonical_empty_artifacts_are_valid_and_have_no_coverage():
    catalog = _json("knowledge/source_catalog.json")
    passages = _json("knowledge/passages.json")
    coverage = (ROOT / "knowledge/pac_coverage.md").read_text(encoding="utf-8")

    assert validate_catalog(catalog, date(2026, 10, 17)).ok
    assert validate_passage_set(passages).ok
    assert catalog["sources"] == []
    assert passages["passages"] == []
    assert "Diego" in coverage
    assert "2026-10-17" in coverage
    assert "pendiente" in coverage
    retriever = Retriever.from_documents(catalog, passages, date(2026, 10, 17))
    assert retriever.indexed_passage_count == 0
    assert retriever.search("¿Cuál es el plazo de presentación?") == ()


def test_candidate_topics_are_not_misrepresented_as_approved_coverage():
    coverage = (ROOT / "knowledge/pac_coverage.md").read_text(encoding="utf-8")
    assert "canal ordinario de presentación" in coverage
    assert "fecha final de presentación" in coverage
    assert "fecha separada de modificación" in coverage
    assert "no acredita" in coverage
    assert "Elegibilidad individual, importes, penalizaciones" in coverage
