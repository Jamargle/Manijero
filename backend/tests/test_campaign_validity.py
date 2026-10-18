"""Campaign configuration, metadata, and request-scope regression checks."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.ask_api import get_active_campaign, get_as_of_date, get_corpus_documents
from app.main import app
from app.source_catalog import validate_catalog
from app.ask_api import CorpusDocuments
from pathlib import Path
from app.source_catalog import load_catalog
from app.retrieval import load_passage_set
from copy import deepcopy


def catalog(**overrides):
    source = {
        "id": "campaign-source", "title": "Fixture", "issuing_body": "FEGA",
        "original_url": "https://fega.gob.es/documento", "published_on": "2026-01-01",
        "downloaded_on": "2026-01-01", "verified_on": "2026-01-01",
        "content_sha256": "a" * 64, "review_status": "approved", "reviewed_by": "test",
        "reviewed_on": "2026-01-01", "lifecycle_status": "current",
        "campaign": "2026", "valid_until": "2026-12-31",
    }
    source.update(overrides)
    return {"schema_version": "source-catalog-v1", "sources": [source]}


@pytest.mark.parametrize("value,valid", [("2026", True), ("26", False), ("20260", False), ("synthetic", False), ("", False)])
def test_campaign_metadata_is_strict(value, valid):
    assert validate_catalog(catalog(campaign=value), date(2026, 6, 1)).ok is valid


def test_campaign_requires_finite_validity_date():
    source = catalog()["sources"][0]
    del source["valid_until"]
    assert not validate_catalog({"schema_version": "source-catalog-v1", "sources": [source]}, date(2026, 6, 1)).ok


def test_campaign_validity_includes_boundary_but_rejects_after():
    doc = catalog()
    assert validate_catalog(doc, date(2026, 12, 31)).ok
    assert not validate_catalog(doc, date(2027, 1, 1)).ok


@pytest.mark.parametrize("setting", [None, "", "26", "2026x"])
def test_missing_or_malformed_campaign_configuration_is_generic_503(monkeypatch, setting):
    app.dependency_overrides.clear()
    if setting is None:
        monkeypatch.delenv("MANIJERO_ACTIVE_CAMPAIGN", raising=False)
    else:
        monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", setting)
    with TestClient(app) as client:
        response = client.post("/ask", json={"question":"PAC", "land_context":{"mode":"general","lands":[]}})
    assert response.status_code == 503
    assert not setting or setting not in response.text
    assert get_active_campaign.__name__ == "get_active_campaign"


@pytest.mark.parametrize("question,expected", [("¿Cuándo se presenta la solicitud anual de ejemplo? 2026", "answered"), ("¿PAC 2025?", "abstained"), ("¿PAC 2025 o 2026?", "abstained")])
def test_explicit_year_scope_precedes_answer_pipeline(question, expected):
    fixture_dir = Path(__file__).parent / "fixtures" / "clarification"
    documents = CorpusDocuments(catalog=load_catalog(fixture_dir / "catalog.json"), passages=load_passage_set(fixture_dir / "passages.json"))
    app.dependency_overrides[get_active_campaign] = lambda: "2026"
    app.dependency_overrides[get_as_of_date] = lambda: date(2026, 10, 13)
    app.dependency_overrides[get_corpus_documents] = lambda: documents
    try:
        with TestClient(app) as client:
            response = client.post("/ask", json={"question": question, "land_context":{"mode":"general","lands":[]}})
        assert response.status_code == 200
        assert response.json()["status"] == expected
        if expected == "abstained":
            assert response.json()["sources"] == []
    finally:
        app.dependency_overrides.clear()


def test_malformed_off_campaign_metadata_is_not_hidden_by_filtering():
    fixture_dir = Path(__file__).parent / "fixtures" / "clarification"
    source_catalog = load_catalog(fixture_dir / "catalog.json")
    source_catalog["sources"][0]["campaign"] = "not-a-year"
    documents = CorpusDocuments(catalog=source_catalog, passages=load_passage_set(fixture_dir / "passages.json"))
    app.dependency_overrides[get_active_campaign] = lambda: "2026"
    app.dependency_overrides[get_as_of_date] = lambda: date(2026, 10, 13)
    app.dependency_overrides[get_corpus_documents] = lambda: documents
    try:
        with TestClient(app) as client:
            response = client.post("/ask", json={"question":"PAC", "land_context":{"mode":"general","lands":[]}})
        assert response.status_code == 503
        assert response.json() == {"detail": "Answer service is temporarily unavailable."}
        assert "not-a-year" not in response.text
    finally:
        app.dependency_overrides.clear()
