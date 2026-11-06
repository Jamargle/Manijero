"""Contract tests for the privacy-minimal ``POST /feedback`` route.

Everything is in-process over synthetic corpora, fake pilot clients, and fake tokens. No
network is used and no real pilot token is read.
"""

from __future__ import annotations

from datetime import date
import io
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.answer_trace import load_answer_trace
from app.ask_api import CorpusDocuments, get_active_campaign, get_as_of_date, get_corpus_documents
from app.main import create_app
from app.pilot_config import ClientPolicy, PilotConfig, token_sha256
from app.pilot_logging import LOGGER_NAME
from app.readiness import get_configured_campaign
from app.retention import RetentionStore
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clarification"
FIXED_DAY = date(2026, 10, 13)
TOKEN = "synthetic-feedback-token-0123456789abcdef"
CLIENT_ID = "feedback-pilot-device-SENTINEL"
RATINGS = ("useful", "not_useful")
FEEDBACK_SAMPLE = re.compile(r'^manijero_feedback_total\{rating="([^"]+)"\} (\d+)$')


def dev_config(campaign: str | None = "2026", max_request_bytes: int = 65536) -> PilotConfig:
    return PilotConfig(profile="development", active_campaign=campaign, max_request_bytes=max_request_bytes)


def pilot_config(limit: int = 100, max_request_bytes: int = 4096) -> PilotConfig:
    return PilotConfig(
        profile="pilot",
        active_campaign="2026",
        max_request_bytes=max_request_bytes,
        clients=(ClientPolicy(CLIENT_ID, token_sha256(TOKEN), limit),),
    )


def build_app(config: PilotConfig | None = None, **options: Any) -> FastAPI:
    application = create_app(config or dev_config(), retention_store=None, **options)
    application.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=load_catalog(FIXTURES / "catalog.json"),
        passages=load_passage_set(FIXTURES / "passages.json"),
    )
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    application.dependency_overrides[get_configured_campaign] = lambda: "2026"
    return application


def auth() -> dict[str, str]:
    return {"authorization": "Bearer " + TOKEN}


def ask_body() -> dict[str, Any]:
    return {
        "question": "¿Cuándo se presenta la solicitud anual de ejemplo?",
        "land_context": {"mode": "general", "lands": []},
    }


def feedback_metric_values(text: str) -> dict[str, int]:
    found = {}
    for line in text.splitlines():
        match = FEEDBACK_SAMPLE.match(line)
        if match:
            found[match.group(1)] = int(match.group(2))
    return found


# --- scenario 1: accepted ratings ------------------------------------------------------------


def test_feedback_accepts_useful_and_not_useful_with_204_no_body() -> None:
    with TestClient(build_app()) as client:
        for rating in RATINGS:
            response = client.post("/feedback", json={"rating": rating})
            assert response.status_code == 204, rating
            assert response.content == b"", rating


def test_feedback_works_without_campaign_or_corpus() -> None:
    # No corpus override, no campaign: the route reads neither and must still answer.
    application = create_app(dev_config(campaign=None), retention_store=None)
    with TestClient(application) as client:
        assert client.get("/ready").status_code == 503
        assert client.post("/feedback", json={"rating": "useful"}).status_code == 204


# --- scenario 2: only the fixed rating crosses the boundary ----------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"rating": "maybe-SECRET-RATING"},
        {"rating": 5},
        {"rating": "useful", "comment": "SECRET-COMMENT"},
        {"rating": "useful", "question": "SECRET-QUESTION"},
        {"rating": "useful", "answer": "SECRET-ANSWER"},
        {"rating": "useful", "land": {"id": "SECRET-LAND"}},
        {"rating": "useful", "id": "SECRET-ANSWER-ID"},
        {"rating": "useful", "device": "SECRET-DEVICE"},
        {"rating": "useful", "client": "SECRET-CLIENT"},
        {"rating": "useful", "text": "SECRET-FREE-TEXT"},
    ],
)
def test_feedback_rejects_extra_fields_and_free_text_without_echo(payload: dict) -> None:
    with TestClient(build_app()) as client:
        rejected = client.post("/feedback", json=payload)
        page = client.get("/metrics").text

    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "Request validation failed."}
    assert "SECRET" not in rejected.text
    assert feedback_metric_values(page) == {rating: 0 for rating in RATINGS}


def test_feedback_rejects_malformed_json_with_400() -> None:
    with TestClient(build_app()) as client:
        for raw in (b'{"rating": "useful"', b'{"rating": "useful", "comment": "SECRET-COMMENT"'):
            rejected = client.post(
                "/feedback", content=raw, headers={"content-type": "application/json"}
            )
            assert rejected.status_code == 400
            assert rejected.json() == {"detail": "Malformed JSON request."}
            assert "SECRET" not in rejected.text


def test_feedback_returns_413_over_the_body_bound() -> None:
    with TestClient(build_app(dev_config(max_request_bytes=1024))) as client:
        oversized = b'{"rating": "useful", "comment": "' + b"S" * 2000 + b'"}'
        rejected = client.post(
            "/feedback", content=oversized, headers={"content-type": "application/json"}
        )

    assert rejected.status_code == 413
    assert rejected.json() == {"detail": "Request body is too large."}
    assert "SSSS" not in rejected.text


# --- scenario 3: local is open, pilot is gated ------------------------------------------------


def test_feedback_pilot_requires_a_client_token() -> None:
    with TestClient(build_app(pilot_config())) as client:
        for headers in ({}, {"authorization": "Bearer"}, {"authorization": "Basic abc"},
                        {"authorization": "Bearer wrong-token"}):
            rejected = client.post("/feedback", json={"rating": "useful"}, headers=headers)
            assert rejected.status_code == 401
            assert rejected.headers["www-authenticate"] == "Bearer"
            assert rejected.json() == {"detail": "Client credentials are required."}
        assert client.post("/feedback", json={"rating": "not_useful"}, headers=auth()).status_code == 204
        # Liveness and readiness stay open.
        assert client.get("/health").status_code == 200


def test_feedback_does_not_consume_the_ask_allowance() -> None:
    with TestClient(build_app(pilot_config(limit=3))) as client:
        feedback = [client.post("/feedback", json={"rating": "useful"}, headers=auth()).status_code
                    for _ in range(4)]
        exceeded = client.post("/feedback", json={"rating": "useful"}, headers=auth())
        asks = [client.post("/ask", json=ask_body(), headers=auth()).status_code for _ in range(4)]
        page = client.get("/metrics", headers=auth()).text

    assert feedback == [204, 204, 204, 429]
    assert exceeded.status_code == 429
    assert exceeded.headers["retry-after"] == "60"
    # Feedback used its own window; the client's /ask allowance was still whole.
    assert asks == [200, 200, 200, 429]
    assert 'code="429"' in page


# --- scenario 4: counts only, no content or identifiers ---------------------------------------


def test_feedback_counts_both_ratings_in_metrics() -> None:
    with TestClient(build_app()) as client:
        empty = feedback_metric_values(client.get("/metrics").text)
        assert client.post("/feedback", json={"rating": "useful"}).status_code == 204
        assert client.post("/feedback", json={"rating": "useful"}).status_code == 204
        assert client.post("/feedback", json={"rating": "not_useful"}).status_code == 204
        page = client.get("/metrics").text

    assert empty == {"useful": 0, "not_useful": 0}
    assert feedback_metric_values(page) == {"useful": 2, "not_useful": 1}
    assert 'manijero_http_requests_total{code="204",route="/feedback"} 3' in page


def test_feedback_metrics_have_no_user_values() -> None:
    with TestClient(build_app()) as client:
        assert client.post("/feedback", json={"rating": "useful"}).status_code == 204
        assert client.post(
            "/feedback", json={"rating": "useful", "comment": "SECRET-COMMENT"}
        ).status_code == 422
        assert client.post(
            "/feedback", json={"rating": "SECRET-RATING"}, headers={"x": "SECRET-TOKEN"}
        ).status_code == 422
        page = client.get("/metrics").text

    values = feedback_metric_values(page)
    assert set(values) == set(RATINGS)
    assert values == {"useful": 1, "not_useful": 0}
    for secret in ("SECRET-COMMENT", "SECRET-RATING", "SECRET-TOKEN"):
        assert secret not in page
    assert all(value in RATINGS for value in values)


def test_feedback_logs_only_request_metadata() -> None:
    stream = io.StringIO()
    logger = logging.getLogger(LOGGER_NAME)
    previous_handlers = list(logger.handlers)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        with TestClient(build_app(pilot_config())) as client:
            assert client.post("/feedback", json={"rating": "useful"}, headers=auth()).status_code == 204
            assert client.post(
                "/feedback", json={"rating": "useful", "comment": "SECRET-COMMENT"}, headers=auth()
            ).status_code == 422
    finally:
        logger.handlers.clear()
        logger.handlers.extend(previous_handlers)

    logged = stream.getvalue()
    requests = [json.loads(line) for line in logged.splitlines()
                if line.strip() and json.loads(line)["event"] == "request"]
    assert [(item["method"], item["path"], item["status"]) for item in requests] == [
        ("POST", "/feedback", 204),
        ("POST", "/feedback", 422),
    ]
    assert all(set(item) == {"event", "time", "method", "path", "status", "duration_ms", "gate"}
               for item in requests)
    for secret in ("useful", "SECRET-COMMENT", TOKEN, CLIENT_ID):
        assert secret not in logged


# --- scenario 5: no persistence or answer linkage ---------------------------------------------


def test_feedback_creates_no_retention_or_trace_record(tmp_path: Path) -> None:
    owner = tmp_path / "retention"
    owner.mkdir(mode=0o700)
    os.chmod(owner, 0o700)
    store = RetentionStore.open(owner / "qa.sqlite3")
    trace_folder = tmp_path / "traces"
    trace = load_answer_trace({"MANIJERO_ANSWER_TRACE": "on"}, "development", folder=trace_folder)
    application = create_app(dev_config(), retention_store=store, answer_trace=trace)
    with TestClient(application) as client:
        assert client.post("/feedback", json={"rating": "useful"}).status_code == 204

    connection = sqlite3.connect(store.path)
    try:
        rows = connection.execute("SELECT * FROM retained_qa").fetchall()
    finally:
        connection.close()

    assert rows == []
    assert (list(trace_folder.glob("*.json")) if trace_folder.exists() else []) == []


def test_feedback_does_not_change_an_ask_response() -> None:
    with TestClient(build_app()) as client:
        before = client.post("/ask", json=ask_body())
        assert client.post("/feedback", json={"rating": "not_useful"}).status_code == 204
        after = client.post("/ask", json=ask_body())
        page = client.get("/metrics").text

    assert before.status_code == after.status_code == 200
    assert before.json() == after.json()
    assert 'manijero_answers_total{status="answered"} 2' in page


# --- scenario 6: contract and examples are published ------------------------------------------


def test_feedback_is_documented_in_openapi_and_examples() -> None:
    with TestClient(build_app()) as client:
        spec = client.get("/openapi.json").json()

    operation = spec["paths"]["/feedback"]["post"]
    assert operation["operationId"] == "submitAnswerFeedback"
    assert {"204", "400", "401", "413", "422", "429"} <= set(operation["responses"])
    assert "requestBody" in operation
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FeedbackRequest"
    }

    schema = spec["components"]["schemas"]["FeedbackRequest"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["rating"]
    assert set(schema["properties"]) == {"rating"}
    assert schema["properties"]["rating"]["enum"] == list(RATINGS)

    for name, rating in (("feedback-useful.json", "useful"),
                         ("feedback-not-useful.json", "not_useful")):
        example = json.loads((ROOT / "contracts" / "examples" / name).read_text(encoding="utf-8"))
        assert set(example) == {"rating"}
        assert example["rating"] == rating
