"""Tests for the development-only ``inspection`` object on the ``/ask`` 200 response.

Synthetic clarification fixtures and fake tokens only; nothing writes into the repository.
"""

from __future__ import annotations

import dataclasses
import io
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.answer_inspection as answer_inspection  # noqa: E402
from app.answer_inspection import INSPECTION_KEYS, build_inspection, inspection_allowed  # noqa: E402
from app.answer_trace import METADATA_KEYS, TraceCollector, key_paths, load_answer_trace  # noqa: E402
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_backend,
)
from app.main import create_app  # noqa: E402
from app.pilot_config import load_config  # noqa: E402
from app.pilot_logging import LOGGER_NAME  # noqa: E402
from app.retention import RetentionStore  # noqa: E402
from test_answer_trace import (  # noqa: E402
    CLARIFY_LANDS,
    CLARIFY_QUESTION,
    GENERAL,
    LANDS,
    MARKER,
    QUESTION,
    TOKEN,
    _BadDraftGenerator,
    _Resolution,
    _unavailable,
    ask,
    documents,
    load,
    make_app as make_trace_app,
    pilot_config,
    trace_for,
)
from test_hybrid_retrieval import (  # noqa: E402
    FailingEmbedder,
    HybridBackend,
    clarification_retriever,
    components_for,
)

YEAR_QUESTION = "¿Cuándo se presenta la solicitud anual de 2031?"
ABSTAIN_QUESTION = "¿Qué ayuda de pesca me corresponde?"
ENVIRONMENT_KEY = "MANIJERO_DEPLOYMENT_PROFILE"


def make_app(*, inspection: Any = True, trace: Any = None, docs: Any = documents):
    config = load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"})
    application = create_app(
        config,
        retention_store=None,
        answer_trace=trace or load_answer_trace({}, "development"),
        answer_inspection=inspection,
    )
    application.dependency_overrides[get_corpus_documents] = docs
    application.dependency_overrides[get_as_of_date] = lambda: __import__("datetime").date(2026, 10, 13)
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    return application


@pytest.fixture
def operational_records():
    logger = logging.getLogger(LOGGER_NAME)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield lambda: [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def contains_key(value: Any, name: str) -> bool:
    if isinstance(value, dict):
        return name in value or any(contains_key(v, name) for v in value.values())
    if isinstance(value, list):
        return any(contains_key(v, name) for v in value)
    return False


# --- the profile gate --------------------------------------------------------------------


@pytest.mark.parametrize(
    "question,lands",
    [
        (QUESTION, GENERAL),
        (ABSTAIN_QUESTION, GENERAL),
        (YEAR_QUESTION, GENERAL),
        (CLARIFY_QUESTION, CLARIFY_LANDS),
    ],
)
def test_explicit_development_sends_inspection_and_other_keys_are_byte_identical(
    question: str, lands: Any
) -> None:
    on = ask(make_app(inspection=True), question, lands)
    off = ask(make_app(inspection=False), question, lands)

    assert on.status_code == off.status_code == 200
    body = on.json()
    assert body["inspection"]["schema"] == "answer-inspection-v1"
    assert not contains_key(off.json(), "inspection")
    assert json.dumps({k: v for k, v in body.items() if k != "inspection"}, sort_keys=True) == json.dumps(
        off.json(), sort_keys=True
    )
    assert list(off.json()) == ["status", "answer", "sources", "land_scope", "land_ids_to_choose"]


@pytest.mark.parametrize(
    "stated,expected",
    [
        ("development", True),
        (None, False),
        ("", False),
        (" development", False),
        ("Development", False),
        ("qa", False),
        ("prod", False),
    ],
)
def test_create_app_resolves_inspection_only_from_an_explicit_development_profile(
    monkeypatch: pytest.MonkeyPatch, stated: Any, expected: bool
) -> None:
    if stated is None:
        monkeypatch.delenv(ENVIRONMENT_KEY, raising=False)
    else:
        monkeypatch.setenv(ENVIRONMENT_KEY, stated)
    base = load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"})
    # The resolved profile is "development" for unset; other values are forced to the stated one.
    config = dataclasses.replace(base, profile=stated if stated is not None else "development")
    application = create_app(config, retention_store=None, answer_trace=load_answer_trace({}, config.profile))
    application.dependency_overrides[get_corpus_documents] = documents
    application.dependency_overrides[get_as_of_date] = lambda: __import__("datetime").date(2026, 10, 13)
    application.dependency_overrides[get_active_campaign] = lambda: "2026"

    response = ask(application)

    assert response.status_code == 200
    assert application.state.answer_inspection is expected
    assert contains_key(response.json(), "inspection") is expected
    assert inspection_allowed(config.profile, {ENVIRONMENT_KEY: stated or ""}) is expected


def test_pilot_profile_never_sends_inspection_even_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENVIRONMENT_KEY, "pilot")
    application = create_app(pilot_config(), retention_store=None, answer_trace=load_answer_trace({}, "pilot"))
    application.dependency_overrides[get_corpus_documents] = documents
    application.dependency_overrides[get_as_of_date] = lambda: __import__("datetime").date(2026, 10, 13)
    application.dependency_overrides[get_active_campaign] = lambda: "2026"

    response = ask(application, pilot=True)

    assert response.status_code == 200 and not contains_key(response.json(), "inspection")


def test_startup_logs_only_the_state(operational_records) -> None:
    make_app(inspection=True)
    make_app(inspection=False)

    logged = [r for r in operational_records() if r["event"] == "answer_inspection"]
    assert [(set(r) - {"time"}) for r in logged] == [{"event", "state"}] * 2
    assert [r["state"] for r in logged] == ["on", "off"]


def test_unavailable_corpus_503_is_unchanged() -> None:
    on = ask(make_app(inspection=True, docs=_unavailable))
    off = ask(make_app(inspection=False, docs=_unavailable))

    assert (on.status_code, on.content) == (off.status_code, off.content) == (503, off.content)


# --- content -----------------------------------------------------------------------------


def test_inspection_key_set_equals_the_allowlist_and_stages_are_filled() -> None:
    response = ask(make_app(), QUESTION)
    inspection = response.json()["inspection"]

    hybrid_app = make_app()
    backend = HybridBackend(lambda: components_for(clarification_retriever()))
    hybrid_app.dependency_overrides[get_retrieval_backend] = lambda: backend
    hybrid = ask(hybrid_app).json()["inspection"]
    # BM25 has no vector stage; the hybrid response completes the published key set.
    assert key_paths(inspection) | key_paths(hybrid) == INSPECTION_KEYS
    assert key_paths(inspection) <= INSPECTION_KEYS
    retrieval = inspection["retrieval"]
    assert retrieval["mode"] == "bm25" and retrieval["k"] == 5 and retrieval["vector"] is None
    passages = retrieval["passages"]
    assert 1 <= len(passages) <= retrieval["k"]
    assert [p["rank"] for p in passages] == sorted(p["rank"] for p in passages)
    cited_ids = inspection["outcome"]["cited_passage_ids"]
    assert cited_ids and {p["passage_id"] for p in passages if p["cited"]} == set(cited_ids) & {
        p["passage_id"] for p in passages
    }
    assert all(p["title"] and p["location"] and p["excerpt"] for p in passages)
    assert passages[0]["lexical_rank"] == 1 and passages[0]["lexical_score"] > 0
    assert all(p["vector_similarity"] is None for p in passages)
    assert inspection["drafting"]["provider"] == "extractive"
    assert inspection["verification"]["ok"] is True
    assert inspection["verification"]["claims"][0]["index"] == 1
    assert inspection["total_ms"] >= 0


def test_stages_that_did_not_run_are_null() -> None:
    year = ask(make_app(), YEAR_QUESTION).json()["inspection"]
    clarification = ask(make_app(), CLARIFY_QUESTION, CLARIFY_LANDS).json()["inspection"]

    assert year["retrieval"] is None and year["drafting"] is None and year["verification"] is None
    assert year["outcome"]["abstention_reason"] == "no_evidence"
    assert clarification["retrieval"] is not None
    assert key_paths(clarification) <= INSPECTION_KEYS


def test_private_text_land_values_and_token_never_appear() -> None:
    question = QUESTION + " " + MARKER
    response = ask(make_app(), question, LANDS)
    text = json.dumps(response.json()["inspection"], ensure_ascii=False)

    for forbidden in (MARKER, "opaque-land-7f3a", "Martos", TOKEN, question):
        assert forbidden not in text
    assert "detail" not in text and "land_scope" not in text


def test_hybrid_vector_values_and_fallback_code() -> None:
    retriever = clarification_retriever()
    good = make_app()
    hybrid = HybridBackend(lambda: components_for(retriever))
    good.dependency_overrides[get_retrieval_backend] = lambda: hybrid
    retrieval = ask(good).json()["inspection"]["retrieval"]
    assert retrieval["mode"] == "hybrid" and retrieval["vector"] == {"used": True, "fallback_code": None}
    assert any(p["vector_similarity"] is not None for p in retrieval["passages"])

    broken_app = make_app()
    broken = HybridBackend(lambda: components_for(retriever, embedder=FailingEmbedder()))
    broken_app.dependency_overrides[get_retrieval_backend] = lambda: broken
    vector = ask(broken_app).json()["inspection"]["retrieval"]["vector"]
    assert vector["used"] is False and vector["fallback_code"]


def test_rejected_draft_records_codes_only() -> None:
    application = make_app()
    application.state.generation_provider = _Resolution(_BadDraftGenerator())
    response = ask(application)
    inspection = response.json()["inspection"]

    assert response.json()["status"] == "abstained"
    assert inspection["verification"]["ok"] is False
    assert {"eligibility_claim", "uncited_sentence"} <= set(inspection["verification"]["issues"])
    assert "Tienes derecho" not in json.dumps(inspection)


def test_passages_are_capped_at_k_and_excerpt_at_2000() -> None:
    collector = TraceCollector()
    collector.mode, collector.k = "bm25", 2
    collector.candidates = [
        {"passage_id": "p%d" % n, "source_id": "s", "score": 1.0 / n, "rank": n} for n in (3, 1, 2)
    ]
    collector.details = {"p%d" % n: ("t", "l", "x" * 3000) for n in (1, 2, 3)}
    collector.outcome = {"cited_passage_ids": ["p2"]}

    passages = build_inspection(collector)["retrieval"]["passages"]

    assert [p["passage_id"] for p in passages] == ["p1", "p2"]
    assert [p["cited"] for p in passages] == [False, True]
    assert all(len(p["excerpt"]) == 2000 for p in passages)


# --- isolation ---------------------------------------------------------------------------


def test_builder_failure_omits_the_key_keeps_the_answer_and_logs_a_fixed_code(
    monkeypatch: pytest.MonkeyPatch, operational_records
) -> None:
    baseline = ask(make_app(inspection=False))

    def boom(collector: Any) -> Any:
        raise answer_inspection.InspectionError("build_failed")

    monkeypatch.setattr(answer_inspection, "build_inspection", boom)
    response = ask(make_app(inspection=True))

    assert (response.status_code, response.content) == (baseline.status_code, baseline.content)
    skipped = [r for r in operational_records() if r["event"] == "answer_inspection_skipped"]
    assert [{k: v for k, v in r.items() if k != "time"} for r in skipped] == [
        {"event": "answer_inspection_skipped", "reason": "build_failed"}
    ]


def test_trace_on_or_off_does_not_change_inspection_and_trace_keys_stay_metadata(tmp_path: Path) -> None:
    def shape(inspection: dict) -> Any:
        return key_paths(inspection)

    off = ask(make_app(trace=trace_for(tmp_path / "off", enabled=False))).json()["inspection"]
    trace = trace_for(tmp_path / "on", profile="pilot")
    on = ask(make_app(trace=trace)).json()["inspection"]
    document = load(trace)

    assert shape(off) == shape(on) and shape(on) <= INSPECTION_KEYS
    assert key_paths(document) <= METADATA_KEYS
    assert "inspection" not in json.dumps(document)


def test_retained_records_never_contain_inspection(tmp_path: Path) -> None:
    directory = tmp_path / "retention"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    store = RetentionStore.open(directory / "qa.sqlite3")
    config = load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"})
    application = create_app(
        config,
        retention_store=store,
        answer_trace=load_answer_trace({}, "development"),
        answer_inspection=True,
    )
    application.dependency_overrides[get_corpus_documents] = documents
    application.dependency_overrides[get_as_of_date] = lambda: __import__("datetime").date(2026, 10, 13)
    application.dependency_overrides[get_active_campaign] = lambda: "2026"

    response = ask(application, retain_for_improvement=True)

    assert contains_key(response.json(), "inspection")
    stored = (directory / "qa.sqlite3").read_bytes()
    assert b"answer-inspection-v1" not in stored and b"lexical_rank" not in stored
