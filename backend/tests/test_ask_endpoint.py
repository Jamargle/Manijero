"""HTTP contract tests for the local answer endpoint.

The only positive answer and land-clarification inputs below are clearly synthetic
fixtures. They exercise decision wiring and do not establish legal coverage.
"""

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.ask_api as ask_api
from app.ask_api import CorpusDocuments, get_as_of_date, get_corpus_documents
from app.main import app
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clarification"


def fixture_documents() -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(FIXTURES / "catalog.json"),
        passages=load_passage_set(FIXTURES / "passages.json"),
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_corpus_documents] = fixture_documents
    app.dependency_overrides[get_as_of_date] = lambda: date(2026, 10, 13)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload(question: str = "¿Cuándo se presenta la solicitud anual de ejemplo?") -> dict[str, Any]:
    return {"question": question, "land_context": {"mode": "general", "lands": []}}


def test_ask_returns_verified_source_backed_answer_from_synthetic_fixture(client) -> None:
    response = client.post("/ask", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["land_scope"] == "general"
    assert body["sources"]
    assert "sintético" in body["sources"][0]["title"]
    assert "sintético" in body["answer"]
    assert set(body) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}


def test_ask_abstains_on_empty_canonical_corpus(client) -> None:
    app.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog={"schema_version": "source-catalog-v1", "sources": []},
        passages={"schema_version": "passage-set-v1", "passages": []},
    )

    response = client.post("/ask", json=payload("¿Qué ayuda me corresponde?"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "abstained",
        "answer": "No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa.",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
    }


def test_ask_clarifies_only_with_request_land_ids(client) -> None:
    request = payload("¿Puedo regar mi olivar de ejemplo?")
    request["land_context"] = {
        "mode": "all_active",
        "lands": [
            {"id": "opaque-one", "water_regime": "irrigated"},
            {"id": "opaque-two", "water_regime": "dryland"},
        ],
    }

    response = client.post("/ask", json=request)

    assert response.status_code == 200
    assert response.json() == {
        "status": "needs_land_clarification",
        "answer": "",
        "sources": [],
        "land_scope": "selected",
        "land_ids_to_choose": ["opaque-one", "opaque-two"],
    }


def test_selected_request_does_not_repeat_land_clarification(client) -> None:
    request = payload("¿Puedo regar mi olivar de ejemplo?")
    request["land_context"] = {
        "mode": "selected",
        "lands": [{"id": "opaque-one", "water_regime": "irrigated"}],
    }

    response = client.post("/ask", json=request)

    assert response.status_code == 200
    assert response.json()["status"] != "needs_land_clarification"


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"question": "x"},
        {**payload(), "extra": "do not echo"},
        {**payload(), "land_context": {"mode": "nope", "lands": []}},
        {**payload(), "land_context": {"mode": "all_active", "lands": []}},
        {
            **payload(),
            "land_context": {
                "mode": "all_active",
                "lands": [{"id": "same"}, {"id": "same"}],
            },
        },
        {
            **payload(),
            "land_context": {
                "mode": "selected",
                "lands": [{"id": "one", "municipality": None}],
            },
        },
        {
            **payload(),
            "land_context": {
                "mode": "selected",
                "lands": [{"id": "one", "water_regime": None}],
            },
        },
        {
            **payload(),
            "land_context": {
                "mode": "selected",
                "lands": [{"id": "one", "production_method": None}],
            },
        },
        {**payload(), "land_context": {"mode": "general", "lands": [{"id": "one"}]}},
        {**payload("q" * 2001)},
        {
            **payload(),
            "land_context": {
                "mode": "selected",
                "lands": [{"id": "one", "secret": "do not echo"}],
            },
        },
    ],
)
def test_invalid_contract_payload_returns_non_reflective_422(client, invalid_payload) -> None:
    response = client.post("/ask", json=invalid_payload)

    assert response.status_code == 422
    assert "do not echo" not in response.text
    assert "secret" not in response.text


def test_malformed_json_returns_400_without_echoing_body(client) -> None:
    response = client.post("/ask", content='{"question":"private words",', headers={"content-type": "application/json"})

    assert response.status_code == 400
    assert "private words" not in response.text


@pytest.mark.parametrize(
    "documents",
    [
        CorpusDocuments(catalog={"schema_version": "wrong", "sources": []}, passages={"schema_version": "passage-set-v1", "passages": []}),
        CorpusDocuments(catalog={"schema_version": "source-catalog-v1", "sources": []}, passages={"bad": "corpus secret"}),
    ],
)
def test_invalid_runtime_corpus_returns_generic_503(client, documents) -> None:
    app.dependency_overrides[get_corpus_documents] = lambda: documents

    response = client.post("/ask", json=payload())

    assert response.status_code == 503
    assert "corpus secret" not in response.text
    assert "knowledge/" not in response.text


def test_campaign_tagged_runtime_source_fails_closed(client) -> None:
    documents = fixture_documents()
    catalog = deepcopy(documents.catalog)
    catalog["sources"][0]["campaign"] = "synthetic"
    app.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=catalog, passages=documents.passages
    )

    response = client.post("/ask", json=payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer service is temporarily unavailable."}


def test_expired_runtime_corpus_abstains_without_sources(client) -> None:
    documents = fixture_documents()
    catalog = deepcopy(documents.catalog)
    for source in catalog["sources"]:
        source["valid_until"] = "2026-10-12"
    app.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=catalog, passages=documents.passages
    )

    response = client.post("/ask", json=payload())

    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
    assert response.json()["sources"] == []


def test_health_remains_live_when_corpus_is_invalid(client) -> None:
    app.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog={"invalid": "corpus"}, passages={}
    )

    assert client.get("/health").json() == {
        "status": "ok",
        "service": "manijero-backend",
    }


def test_openapi_documents_ask_operation_and_error_statuses(client) -> None:
    document = client.get("/openapi.json").json()
    operation = document["paths"]["/ask"]["post"]

    assert operation["operationId"] == "askQuestion"
    assert {"200", "400", "422", "503"}.issubset(operation["responses"])
    request_schema = document["components"]["schemas"]["AskRequest"]
    assert request_schema["additionalProperties"] is False
    land_schema = document["components"]["schemas"]["MinimalLandContext"]
    assert land_schema["properties"]["municipality"]["type"] == "string"
    assert land_schema["properties"]["water_regime"]["enum"] == [
        "dryland", "irrigated", "mixed", "unknown"
    ]
    assert land_schema["properties"]["production_method"]["enum"] == [
        "conventional", "organic", "mixed", "unknown"
    ]
    response_schema = document["components"]["schemas"]["AskResponse"]
    assert set(response_schema["properties"]) == {
        "status", "answer", "sources", "land_scope", "land_ids_to_choose"
    }
    assert document["paths"]["/health"]["get"]["operationId"] == "health_health_get"


def test_local_empty_canonical_files_use_safe_abstention(client) -> None:
    app.dependency_overrides.clear()

    response = client.post("/ask", json=payload("¿Qué ayuda me corresponde?"))

    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
    assert response.json()["sources"] == []


def test_unreadable_canonical_artifact_returns_generic_503(client, monkeypatch) -> None:
    monkeypatch.setattr(ask_api, "CATALOG_PATH", BACKEND_ROOT / "missing-catalog.json")
    app.dependency_overrides[get_corpus_documents] = ask_api.load_corpus_documents

    response = client.post("/ask", json=payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer service is temporarily unavailable."}


def test_invalid_corpus_source_metadata_fails_closed(client) -> None:
    documents = fixture_documents()
    catalog = deepcopy(documents.catalog)
    catalog["sources"][0]["review_status"] = "pending"
    app.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=catalog, passages=documents.passages
    )

    response = client.post("/ask", json=payload("¿Puedo regar mi olivar de ejemplo?"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer service is temporarily unavailable."}
