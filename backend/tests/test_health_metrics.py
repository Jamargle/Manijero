"""Tests for the privacy-safe ``GET /metrics`` page.

Everything is in-process over synthetic corpora, fake generation transports, fake ledgers,
and fake tokens. No network is used and no real pilot token is read.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.ask_api as ask_api
import app.gemini_generation as gemini_module
from app import health_metrics
from app import source_update_scheduler as scheduler
from app.ask_api import (
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.gemini_generation import (
    GeminiDraftClient,
    GeminiDraftRequest,
    GatedGeminiGenerator,
    OUTCOMES as GEMINI_OUTCOMES,
    RateLimiter as GenerationRateLimiter,
)
from app.knowledge_release import ReleaseError
from app.main import create_app
from app.abstention import ABSTENTION_REASONS
from app.pilot_config import ClientPolicy, PilotConfig, token_sha256
from app.readiness import get_configured_campaign
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLARIFICATION = FIXTURES / "clarification"
ABSTENTION = FIXTURES / "abstention"
SYNTHETIC_REVIEW = FIXTURES / "privacy" / "synthetic_approved_review.json"
SYNTHETIC_LIMITS = FIXTURES / "privacy" / "synthetic_gemini_limits.json"
FIXED_DAY = date(2026, 10, 13)
TOKEN = "synthetic-metrics-token-0123456789abcdef"
CLIENT_ID = "metrics-pilot-device-SENTINEL"
QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"
RELEASE_A = "0123456789abcdef"
RELEASE_B = "fedcba9876543210"
SOLICITUD_FRAGMENT = "se presenta una vez al año"

# Independent copy of the contract: label names and their fixed values.
ALLOWED_LABEL_NAMES = {
    "profile", "version", "provider", "route", "code", "rating", "reason", "status", "outcome",
    "problem", "release_id", "state", "job", "le",
}
ALLOWED_LABEL_VALUES: dict[str, set[str]] = {
    "profile": {"development", "pilot"},
    "version": {"0.1.0"},
    "provider": {"extractive", "gemini", "local"},
    "route": {"/ask", "/ready", "/health", "/metrics", "/feedback", "other"},
    "code": {"200", "204", "400", "401", "404", "405", "413", "422", "429", "500", "503", "other"},
    "rating": {"useful", "not_useful"},
    "reason": {
        "too_large", "unauthenticated", "rate_limited", "invalid_question", "no_evidence",
        "insufficient_evidence", "stale_evidence", "conflicting_evidence", "false_premise",
        "unsafe_request", "generator_abstained", "generation_error", "personal_data",
        "prompt_injection", "out_of_domain",
    },
    "status": {"answered", "abstained", "needs_land_clarification"},
    "outcome": {
        "used", "rate_limited", "redaction_failed", "payload_invalid", "transport_error",
        "timeout", "malformed_output", "provider_abstained", "verifier_rejected",
    },
    "problem": {
        "campaign_unavailable", "corpus_unavailable", "corpus_not_current", "no_eligible_sources",
    },
    "state": {"served", "refused", "repository"},
    "job": {"monitor", "boe", "boja"},
    "le": {"0.05", "0.1", "0.25", "0.5", "1", "2.5", "5", "10", "30", "60", "+Inf"},
}
EXPECTED_FAMILIES = {
    "service_info", "generation_provider_info", "process_start_time_seconds", "ready",
    "readiness_problem", "http_requests_total", "request_duration_seconds",
    "request_rejections_total", "answers_total", "feedback_total", "abstentions_total",
    "generation_outcomes_total", "answer_cache_lookups_total", "knowledge_release_info", "source_updates_configured",
    "source_updates_readable", "source_updates_healthy", "source_update_stale",
    "source_update_last_success_timestamp_seconds",
}


# --- helpers -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(health_metrics.SOURCE_UPDATE_STATE_DIR_ENV, raising=False)
    monkeypatch.delenv(ask_api.KNOWLEDGE_RELEASE_ROOT_ENV, raising=False)
    monkeypatch.setattr(ask_api, "_LAST_RELEASE_OUTCOME", None)


def documents(folder: Path = CLARIFICATION) -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(folder / "catalog.json"),
        passages=load_passage_set(folder / "passages.json"),
    )


def dev_config() -> PilotConfig:
    return PilotConfig(profile="development", active_campaign="2026", max_request_bytes=65536)


def pilot_config(limit: int = 100, max_request_bytes: int = 4096) -> PilotConfig:
    return PilotConfig(
        profile="pilot",
        active_campaign="2026",
        max_request_bytes=max_request_bytes,
        clients=(ClientPolicy(CLIENT_ID, token_sha256(TOKEN), limit),),
    )


def build_app(config: PilotConfig | None = None, folder: Path = CLARIFICATION, **options: Any) -> FastAPI:
    application = create_app(config or dev_config(), retention_store=None, **options)
    application.dependency_overrides[get_corpus_documents] = lambda: documents(folder)
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    application.dependency_overrides[get_configured_campaign] = lambda: "2026"
    return application


def auth() -> dict[str, str]:
    return {"authorization": "Bearer " + TOKEN}


def body(question: str = QUESTION, land_context: dict | None = None) -> dict:
    return {"question": question, "land_context": land_context or {"mode": "general", "lands": []}}


_SAMPLE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})? (-?[0-9][0-9.e+\-]*|\+Inf|NaN)$")
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\\n]|\\.)*)"(?:,|$)')


class Page:
    """A strictly parsed Prometheus text page (format 0.0.4)."""

    def __init__(self, text: str) -> None:
        assert text.endswith("\n")
        self.text = text
        self.help: dict[str, int] = {}
        self.types: dict[str, str] = {}
        self.samples: list[tuple[str, dict[str, str], float]] = []
        for line in text.splitlines():
            if line.startswith("# HELP "):
                name = line.split(" ", 3)[2]
                self.help[name] = self.help.get(name, 0) + 1
            elif line.startswith("# TYPE "):
                _, _, name, kind = line.split(" ")
                assert name not in self.types
                self.types[name] = kind
            else:
                match = _SAMPLE.match(line)
                assert match, line
                labels: dict[str, str] = {}
                raw = match.group(2) or ""
                position = 0
                while position < len(raw):
                    label = _LABEL.match(raw, position)
                    assert label, line
                    labels[label.group(1)] = label.group(2)
                    position = label.end()
                self.samples.append((match.group(1), labels, float(match.group(3))))

    def families(self) -> set[str]:
        assert set(self.help) == set(self.types)
        assert all(count == 1 for count in self.help.values())
        return {name.removeprefix("manijero_") for name in self.types}

    def values(self, name: str, **labels: str) -> list[float]:
        full = "manijero_" + name
        return [
            value
            for sample, found, value in self.samples
            if sample == full and all(found.get(key) == val for key, val in labels.items())
        ]

    def value(self, name: str, **labels: str) -> float | None:
        found = self.values(name, **labels)
        assert len(found) <= 1, (name, labels, found)
        return found[0] if found else None

    def sample_names(self) -> set[str]:
        return {name for name, _, _ in self.samples}


def scrape(client: TestClient, headers: dict[str, str] | None = None) -> Page:
    response = client.get("/metrics", headers=headers or {})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == health_metrics.CONTENT_TYPE
    return Page(response.text)


def assert_privacy_invariants(page: Page) -> None:
    for name, labels, _ in page.samples:
        assert name.startswith("manijero_")
        for label, value in labels.items():
            assert label in ALLOWED_LABEL_NAMES, (name, label)
            if label == "release_id":
                assert value == "none" or re.fullmatch(r"[0-9a-f]{16}", value), value
            else:
                allowed = ALLOWED_LABEL_VALUES[label]
                if name == "manijero_answer_cache_lookups_total":
                    allowed = {"hit", "miss", "expired", "discarded"}
                assert value in allowed, (name, label, value)


# --- scenario 1: format and open development profile ----------------------------------------


def test_metrics_open_in_development_profile() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    assert Page(response.text).families() == EXPECTED_FAMILIES


def test_metrics_text_format_grammar() -> None:
    with TestClient(build_app()) as client:
        client.post("/ask", json=body())
        client.get("/health")
        page = scrape(client)

    for name in page.types:
        assert page.help[name] == 1
    assert page.types["manijero_request_duration_seconds"] == "histogram"
    assert page.types["manijero_http_requests_total"] == "counter"
    assert page.types["manijero_ready"] == "gauge"
    names = list(page.types)
    assert names == sorted(names)
    buckets = [
        (labels["le"], value)
        for name, labels, value in page.samples
        if name == "manijero_request_duration_seconds_bucket" and labels["route"] == "/ask"
    ]
    assert buckets[-1][0] == "+Inf"
    assert page.value("request_duration_seconds_count", route="/ask") == buckets[-1][1] == 1
    assert page.value("request_duration_seconds_sum", route="/ask") is not None
    assert_privacy_invariants(page)


def test_feedback_allowlists_match_the_registry() -> None:
    assert set(health_metrics.FEEDBACK_RATINGS) == ALLOWED_LABEL_VALUES["rating"]
    assert set(health_metrics.ROUTES) == ALLOWED_LABEL_VALUES["route"] - {"other"}
    assert "204" in ALLOWED_LABEL_VALUES["code"] and 204 in health_metrics.CODES
    assert health_metrics.FAMILIES["feedback_total"][0] == "counter"
    assert "feedback_total" in EXPECTED_FAMILIES


def test_label_values_are_escaped_and_clamped() -> None:
    registry = health_metrics.HealthMetrics()
    registry.count_rejection('/ask"\n\\', "weird")
    registry.count_generation("openai", "free text")
    registry.count_response("/anything/else", 418, 0.0)
    page = Page(registry.render(ready=False))

    assert page.value("request_rejections_total", route="other", reason="other") == 1
    assert page.value("generation_outcomes_total", provider="other", outcome="other") == 1
    assert page.value("http_requests_total", route="other", code="other") == 1
    assert health_metrics._escape('a"b\\c\nd') == 'a\\"b\\\\c\\nd'


# --- scenario 2: pilot gate -------------------------------------------------------------------


def test_metrics_pilot_requires_client_token() -> None:
    with TestClient(build_app(pilot_config())) as client:
        for headers in ({}, {"authorization": "Bearer"}, {"authorization": "Basic abc"},
                        {"authorization": "Bearer wrong-token"}):
            rejected = client.get("/metrics", headers=headers)
            assert rejected.status_code == 401
            assert rejected.headers["www-authenticate"] == "Bearer"
            assert rejected.json() == {"detail": "Client credentials are required."}
        assert client.get("/metrics", headers=auth()).status_code == 200
        # Liveness and readiness stay open.
        assert client.get("/health").status_code == 200


def test_metrics_scrape_does_not_consume_ask_allowance() -> None:
    with TestClient(build_app(pilot_config(limit=3))) as client:
        assert [client.get("/metrics", headers=auth()).status_code for _ in range(3)] == [200] * 3
        exceeded = client.get("/metrics", headers=auth())
        assert exceeded.status_code == 429
        assert exceeded.headers["retry-after"] == "60"
        # The client's /ask allowance is untouched by the scrapes.
        statuses = [client.post("/ask", json=body(), headers=auth()).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


# --- scenario 3: answer outcomes and latency ------------------------------------------------


def test_answer_status_and_abstention_reason_counted() -> None:
    questions = [
        json.loads(line)
        for line in (ABSTENTION / "eval_questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # A blank question and a question naming another year are decided before the evaluation
    # pipeline runs; every other question maps to its recorded reason code.
    questions = [
        item
        for item in questions
        if item["expect"] != "invalid_question" and not re.search(r"\d{4}", item["question"])
    ]
    expected_abstentions: dict[str, int] = {}
    answered = 0
    with TestClient(build_app(folder=ABSTENTION)) as client:
        for item in questions:
            response = client.post("/ask", json=body(item["question"]))
            assert response.status_code == 200
            if response.json()["status"] == "answered":
                answered += 1
            else:
                reason = item["expect"]
                expected_abstentions[reason] = expected_abstentions.get(reason, 0) + 1
        clarification = body(
            "¿Puedo regar mi olivar de ejemplo?",
            {"mode": "all_active", "lands": [{"id": "a", "water_regime": "irrigated"},
                                              {"id": "b", "water_regime": "dryland"}]},
        )
        # The clarification fixture corpus is needed for this question.
        clarify_app = build_app()
        with TestClient(clarify_app) as other:
            assert other.post("/ask", json=clarification).json()["status"] == "needs_land_clarification"
            clarify_page = scrape(other)
        page = scrape(client)

    assert page.value("answers_total", status="answered") == answered
    assert page.value("answers_total", status="abstained") == sum(expected_abstentions.values())
    assert page.value("answers_total", status="needs_land_clarification") == 0
    assert clarify_page.value("answers_total", status="needs_land_clarification") == 1
    for reason in ABSTENTION_REASONS:
        assert page.value("abstentions_total", reason=reason) == expected_abstentions.get(reason, 0)
    assert len(expected_abstentions) >= 3


def test_year_mismatch_counts_as_no_evidence_abstention() -> None:
    with TestClient(build_app()) as client:
        client.post("/ask", json=body("¿Qué plazo hay en 2019?"))
        page = scrape(client)

    assert page.value("answers_total", status="abstained") == 1
    assert page.value("abstentions_total", reason="no_evidence") == 1


def test_ask_latency_histogram_cumulative() -> None:
    with TestClient(build_app()) as client:
        for _ in range(3):
            client.post("/ask", json=body())
        client.post("/ask", json={"question": "x"})
        page = scrape(client)

    counts = [
        value
        for name, labels, value in page.samples
        if name == "manijero_request_duration_seconds_bucket" and labels["route"] == "/ask"
    ]
    assert len(counts) == len(ALLOWED_LABEL_VALUES["le"])
    assert counts == sorted(counts)
    assert counts[-1] == page.value("request_duration_seconds_count", route="/ask") == 4


# --- scenario 4: errors and gate rejections ---------------------------------------------------


def test_http_errors_and_gate_rejections_counted() -> None:
    with TestClient(build_app(pilot_config(limit=3, max_request_bytes=1024))) as client:
        assert client.post("/ask", json=body()).status_code == 401
        assert client.post(
            "/ask", content=b"{not json", headers={**auth(), "content-type": "application/json"}
        ).status_code == 400
        assert client.post("/ask", json={"question": "x"}, headers=auth()).status_code == 422
        assert client.post("/ask", content=b"x" * 2000, headers=auth()).status_code == 413
        assert client.post("/ask", json=body(), headers=auth()).status_code == 200
        assert client.post("/ask", json=body(), headers=auth()).status_code == 429
        page = scrape(client, auth())

    for code in ("401", "400", "422", "413", "200", "429"):
        assert page.value("http_requests_total", route="/ask", code=code) == 1, code
    assert page.value("request_rejections_total", route="/ask", reason="too_large") == 1
    assert page.value("request_rejections_total", route="/ask", reason="unauthenticated") == 1
    assert page.value("request_rejections_total", route="/ask", reason="rate_limited") == 1
    assert page.value("request_duration_seconds_count", route="/ask") == 6
    assert_privacy_invariants(page)


def test_unavailable_corpus_counted_as_503() -> None:
    application = build_app()
    application.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=None, passages=None, load_error=True
    )
    with TestClient(application) as client:
        assert client.post("/ask", json=body()).status_code == 503
        page = scrape(client)

    assert page.value("http_requests_total", route="/ask", code="503") == 1
    assert page.value("answers_total", status="answered") == 0


def test_unhandled_exception_counted_as_500() -> None:
    application = build_app()

    def explode() -> int:
        raise RuntimeError("SECRET-FAILURE-TEXT")

    application.dependency_overrides[get_retrieval_k] = explode
    with TestClient(application, raise_server_exceptions=False) as client:
        failed = client.post("/ask", json=body())
        page = scrape(client)

    assert failed.status_code == 500
    assert page.value("http_requests_total", route="/ask", code="500") == 1
    assert page.value("request_duration_seconds_count", route="/ask") == 1
    assert "SECRET-FAILURE-TEXT" not in page.text


# --- scenario 5: generation fallbacks ---------------------------------------------------------


class ScriptedTransport:
    def __init__(self, reply: Callable[[GeminiDraftRequest], str] | BaseException | str) -> None:
        self.reply = reply

    def send(self, request: GeminiDraftRequest) -> str:
        if isinstance(self.reply, BaseException):
            raise self.reply
        if callable(self.reply):
            return self.reply(request)
        return self.reply


class FixedClock:
    def monotonic(self) -> float:
        return 1000.0

    def utc_day(self) -> date:
        return FIXED_DAY


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _draft(answer: str, sources: list, status: str = "answered") -> str:
    return json.dumps({"status": status, "answer": answer, "sources": sources}, ensure_ascii=False)


def _handle(request: GeminiDraftRequest) -> str:
    payload = json.loads(request.payload_json)
    return next(item["passage_id"] for item in payload["passages"] if SOLICITUD_FRAGMENT in item["text"])


def _good(request: GeminiDraftRequest) -> str:
    handle = _handle(request)
    return _draft(f"Se presenta una vez al año [{handle}]", [int(handle)])


def _rejected(request: GeminiDraftRequest) -> str:
    handle = _handle(request)
    return _draft(f"El plazo es de 99 días [{handle}]", [int(handle)])


def _generation_app(monkeypatch: pytest.MonkeyPatch, transport: ScriptedTransport, roomy: bool) -> FastAPI:
    monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", "gemini")
    monkeypatch.setenv("MANIJERO_GEMINI_MODEL", "synthetic-model-for-tests")
    limits = _json(SYNTHETIC_LIMITS)
    if roomy:
        limits = dict(limits, max_requests_per_minute=100, max_requests_per_day=1000)
    monkeypatch.setattr(gemini_module, "load_review_record", lambda: _json(SYNTHETIC_REVIEW))
    monkeypatch.setattr(gemini_module, "load_gemini_limits", lambda: limits)
    # The cache is off so every request makes the model draft being counted.
    return build_app(generation_transport=transport, generation_clock=FixedClock(), answer_cache=None)


def test_generation_used_and_fallbacks_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    replies: list[tuple[str, Any]] = [
        ("used", _good),
        ("timeout", TimeoutError()),
        ("transport_error", RuntimeError("SECRET-TRANSPORT-TEXT")),
        ("malformed_output", "this is not json"),
        ("provider_abstained", _draft("", [], status="abstained")),
        ("verifier_rejected", _rejected),
    ]
    for expected, reply in replies:
        application = _generation_app(monkeypatch, ScriptedTransport(reply), roomy=True)
        assert application.state.generation_provider.provider == "gemini"
        with TestClient(application) as client:
            assert client.post("/ask", json=body()).status_code == 200
            page = scrape(client)
        assert page.value("generation_outcomes_total", provider="gemini", outcome=expected) == 1, expected
        assert len(page.values("generation_outcomes_total")) == 1
        assert page.value("generation_provider_info", provider="gemini") == 1
        assert "SECRET-TRANSPORT-TEXT" not in page.text


def test_generation_provider_limiter_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    application = _generation_app(monkeypatch, ScriptedTransport(_good), roomy=False)
    with TestClient(application) as client:
        for _ in range(4):
            assert client.post("/ask", json=body()).status_code == 200
        page = scrape(client)

    assert page.value("generation_outcomes_total", provider="gemini", outcome="used") == 3
    assert page.value("generation_outcomes_total", provider="gemini", outcome="rate_limited") == 1


def test_local_provider_used_outcome_is_normalised() -> None:
    registry = health_metrics.HealthMetrics()
    token = health_metrics.bind(registry)
    try:
        limits = _json(SYNTHETIC_LIMITS)
        generator = GatedGeminiGenerator(
            client=GeminiDraftClient(
                transport=ScriptedTransport(_good),
                model="m",
                limits=gemini_module.evaluate_gemini_limits(limits, as_of=FIXED_DAY)[1],
            ),
            limiter=GenerationRateLimiter(100, 1000, FixedClock()),
            clock=FixedClock(),
            land_context={"mode": "general", "lands": []},
            log=lambda *args, **fields: None,
            provider_name="local",
            used_outcome="local_used",
        )
        generator.generate(QUESTION, [], as_of=FIXED_DAY)
    finally:
        health_metrics.unbind(token)
    page = Page(registry.render(ready=True))

    # No candidates: the draft cannot be built, and the outcome is still a fixed code.
    assert page.value("generation_outcomes_total", provider="local", outcome="payload_invalid") == 1


def test_generation_outcome_allowlist_matches_the_generator() -> None:
    codes = {"used" if code == gemini_module.OUTCOME_USED else code for code in GEMINI_OUTCOMES}
    assert codes == ALLOWED_LABEL_VALUES["outcome"] == set(health_metrics.GENERATION_OUTCOMES)
    assert set(health_metrics.ABSTENTION_REASONS) == set(ABSTENTION_REASONS)


def test_extractive_provider_info_only() -> None:
    with TestClient(build_app()) as client:
        client.post("/ask", json=body())
        page = scrape(client)

    assert page.value("generation_provider_info", provider="extractive") == 1
    assert page.values("generation_outcomes_total") == []


# --- scenario 6: readiness and release -------------------------------------------------------


def _expiring_catalog() -> dict:
    catalog = json.loads((CLARIFICATION / "catalog.json").read_text(encoding="utf-8"))
    for source in catalog["sources"]:
        source["campaign"] = "2026"
        source["valid_until"] = "2026-12-31"
    return catalog


def test_readiness_gauges_follow_corpus() -> None:
    with TestClient(build_app()) as client:
        page = scrape(client)
    assert page.value("ready") == 1
    for problem in ALLOWED_LABEL_VALUES["problem"]:
        assert page.value("readiness_problem", problem=problem) == 0

    cases = {
        "campaign_unavailable": lambda app: app.dependency_overrides.update(
            {get_configured_campaign: lambda: None}),
        "corpus_unavailable": lambda app: app.dependency_overrides.update(
            {get_corpus_documents: lambda: CorpusDocuments(catalog=None, passages=None, load_error=True)}),
        "corpus_not_current": lambda app: app.dependency_overrides.update(
            {get_as_of_date: lambda: date(2027, 6, 1),
             get_corpus_documents: lambda: CorpusDocuments(
                 catalog=_expiring_catalog(), passages=documents().passages)}),
    }
    for problem, change in cases.items():
        application = build_app()
        change(application)
        with TestClient(application) as client:
            page = scrape(client)
        assert page.value("ready") == 0, problem
        for candidate in ALLOWED_LABEL_VALUES["problem"]:
            assert page.value("readiness_problem", problem=candidate) == (1 if candidate == problem else 0), problem


def test_release_info_served_refused_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with TestClient(build_app()) as client:
        page = scrape(client)
    assert page.value("knowledge_release_info", release_id="none", state="repository") == 1

    monkeypatch.setenv(ask_api.KNOWLEDGE_RELEASE_ROOT_ENV, str(tmp_path / "SECRET-ROOT"))
    served = documents()
    monkeypatch.setattr(
        ask_api, "load_published_corpus", lambda root: (served.catalog, served.passages, RELEASE_A)
    )
    application = create_app(dev_config(), retention_store=None)
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_configured_campaign] = lambda: "2026"
    with TestClient(application) as client:
        page = scrape(client)
    assert page.value("ready") == 1
    assert page.value("knowledge_release_info", release_id=RELEASE_A, state="served") == 1
    assert len(page.values("knowledge_release_info")) == 1

    def refuse(root: Path) -> None:
        raise ReleaseError("gate_failed", release_id=RELEASE_B)

    monkeypatch.setattr(ask_api, "load_published_corpus", refuse)
    with TestClient(application) as client:
        page = scrape(client)
    assert page.value("ready") == 0
    assert page.value("knowledge_release_info", release_id=RELEASE_B, state="refused") == 1
    assert "SECRET-ROOT" not in page.text
    assert_privacy_invariants(page)


# --- scenario 7: source-update recency --------------------------------------------------------


def _ledger(state: Path, success: tuple[str, ...]) -> Path:
    now = datetime.now(timezone.utc).isoformat()
    jobs = [
        {"job": name, "status": "success" if name in success else "not_due", "attempts": 1,
         "backoff_seconds": [], "targets": [], "succeeded": [], "failed": []}
        for name in scheduler.JOBS
    ]
    run_id = "run-20261001T000000Z-00000000"
    common = {"schema_version": scheduler.LEDGER_SCHEMA, "run_id": run_id, "trigger": "manual",
              "started_at": now}
    records = [
        {**common, "event": "run_started", "jobs": list(scheduler.JOBS), "forced": False},
        {**common, "event": "run_finished", "finished_at": now, "outcome": "success", "jobs": jobs,
         "unchecked_registries": ["fega", "mapa"]},
    ]
    state.mkdir(parents=True, exist_ok=True)
    ledger = state / scheduler.LEDGER_NAME
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return ledger


def test_source_updates_unconfigured_configured_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with TestClient(build_app()) as client:
        page = scrape(client)
    assert page.value("source_updates_configured") == 0
    assert not {name for name in page.sample_names() if "source_update" in name} - {
        "manijero_source_updates_configured"
    }

    for success in (scheduler.JOBS, ("monitor", "boe")):
        state = tmp_path / "-".join(success)
        ledger = _ledger(state, success)
        status = scheduler.evaluate_status(ledger)
        monkeypatch.setenv(health_metrics.SOURCE_UPDATE_STATE_DIR_ENV, str(state))
        with TestClient(build_app()) as client:
            page = scrape(client)
        assert page.value("source_updates_configured") == 1
        assert page.value("source_updates_readable") == 1
        assert page.value("source_updates_healthy") == (1 if status["healthy"] else 0)
        for job in scheduler.JOBS:
            assert page.value("source_update_stale", job=job) == (
                1 if "stale:" + job in status["alerts"] else 0)
            last = status["jobs"][job]["last_success_at"]
            if last is None:
                assert page.value("source_update_last_success_timestamp_seconds", job=job) is None
            else:
                assert page.value(
                    "source_update_last_success_timestamp_seconds", job=job
                ) == pytest.approx(datetime.fromisoformat(last).timestamp())
        assert str(state) not in page.text
    assert page.value("source_update_stale", job="boja") == 1

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / scheduler.LEDGER_NAME).write_text("not json\n", encoding="utf-8")
    monkeypatch.setenv(health_metrics.SOURCE_UPDATE_STATE_DIR_ENV, str(broken))
    with TestClient(build_app()) as client:
        page = scrape(client)
    assert page.value("source_updates_configured") == 1
    assert page.value("source_updates_readable") == 0
    assert page.values("source_updates_healthy") == []
    assert page.values("source_update_stale") == []
    assert "broken" not in page.text


# --- scenario 8: privacy and resilience -------------------------------------------------------


def test_metrics_carry_no_user_text_land_or_client_values(tmp_path: Path) -> None:
    secrets = ["PREGUNTA-SECRETA", "FINCA-SECRETA", "NOTA-SECRETA", "ID-SECRETO", "MUNI-SECRETO"]
    request = body(
        "¿Cuándo se presenta la solicitud anual de ejemplo? " + secrets[0],
        {"mode": "selected",
         "lands": [{"id": secrets[3], "municipality": secrets[4], "water_regime": "irrigated"}]},
    )
    request["retain_for_improvement"] = False
    with TestClient(build_app(pilot_config())) as client:
        client.post("/ask", json=request, headers=auth())
        client.post("/ask", json={**request, "note": secrets[2], "land": secrets[1]}, headers=auth())
        client.get("/SECRET-PATH-ONE?q=" + secrets[0], headers=auth())
        client.get("/ask/SECRET-PATH-TWO")
        page = scrape(client, auth())

    for secret in [*secrets, TOKEN, CLIENT_ID, token_sha256(TOKEN), "SECRET-PATH", "pilot-device"]:
        assert secret not in page.text
    assert_privacy_invariants(page)
    assert page.value("http_requests_total", route="other", code="404") == 2
    assert "other" in {labels.get("route") for _, labels, _ in page.samples}


def test_unknown_route_clamped_to_other() -> None:
    with TestClient(build_app()) as client:
        client.get("/nope")
        client.get("/ready")
        page = scrape(client)

    assert page.value("http_requests_total", route="other", code="404") == 1
    assert page.value("http_requests_total", route="/ready", code="200") == 1


def test_failing_hook_never_changes_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(build_app()) as client:
        baseline = client.post("/ask", json=body())

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("recording failed")

    for method in ("count_answer", "count_response", "count_rejection", "count_generation"):
        monkeypatch.setattr(health_metrics.HealthMetrics, method, fail)
    with TestClient(build_app(pilot_config(limit=1))) as client:
        accepted = client.post("/ask", json=body(), headers=auth())
        limited = client.post("/ask", json=body(), headers=auth())
        unauthorised = client.post("/ask", json=body())

    assert (accepted.status_code, accepted.json()) == (baseline.status_code, baseline.json())
    assert limited.status_code == 429
    assert unauthorised.status_code == 401


def test_registry_isolated_between_apps() -> None:
    first, second = build_app(), build_app()
    with TestClient(first) as one, TestClient(second) as two:
        one.post("/ask", json=body())
        page_one, page_two = scrape(one), scrape(two)

    assert first.state.health_metrics is not second.state.health_metrics
    assert page_one.value("answers_total", status="answered") == 1
    assert page_two.value("answers_total", status="answered") == 0


def test_requirements_stay_free_of_a_metrics_library() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    assert "prometheus" not in requirements.lower()


# --- answer cache lookups ---------------------------------------------------------------------


def test_answer_cache_lookup_family_is_zero_seeded_with_fixed_outcomes() -> None:
    with TestClient(build_app()) as client:
        page = scrape(client)

    assert_privacy_invariants(page)
    for outcome in ("hit", "miss", "expired", "discarded"):
        assert page.value("answer_cache_lookups_total", outcome=outcome) == 0
    assert len(page.values("answer_cache_lookups_total")) == 4


def test_answer_cache_lookup_outcomes_clamp_to_the_fixed_values() -> None:
    registry = health_metrics.HealthMetrics()
    registry.count_cache_lookup("hit")
    registry.count_cache_lookup("mi pregunta secreta")

    page = Page(registry.render(ready=True))

    assert page.value("answer_cache_lookups_total", outcome="hit") == 1
    assert page.value("answer_cache_lookups_total", outcome="other") == 1
    assert "secreta" not in page.text
