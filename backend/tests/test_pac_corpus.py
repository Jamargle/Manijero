"""Offline invariants for the approved PAC corpus boundary."""

import json
from datetime import date
from pathlib import Path

from app.retrieval import Retriever, validate_passage_set
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
    assert len(catalog["sources"]) == 4
    assert len(passages["passages"]) == 4
    assert "Diego" in coverage
    assert "2026-10-17" in coverage
    assert "Aprobada" in coverage
    retriever = Retriever.from_documents(
        catalog, passages, date(2026, 10, 17), active_campaign="2026"
    )
    assert retriever.indexed_passage_count == 4
    results = retriever.search("¿Cuál es el plazo de presentación?")
    assert len(results) > 0


def test_approved_topics_and_exclusions():
    coverage = (ROOT / "knowledge/pac_coverage.md").read_text(encoding="utf-8")
    assert "Canal ordinario de presentación" in coverage
    assert "Fecha final de presentación" in coverage
    assert "Fecha separada de modificación" in coverage
    assert "Elegibilidad individual, importes" in coverage
