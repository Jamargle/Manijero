"""Tests for the gated, replaceable Gemini drafting path.

No test reaches a network or reads a secret: every Gemini call goes to an in-process fake
transport, time comes from a fake clock, and the approved review and limits are clearly
labelled synthetic fixtures. The committed records stay pending/null and the gate closed.
"""

from __future__ import annotations

import ast
from datetime import date, timedelta
import io
import json
import logging
from pathlib import Path
import socket
import threading
from typing import Any, Callable, Iterator

import pytest
from fastapi.testclient import TestClient

import app.gemini_generation as gemini_module
from app.abstention import Abstention, prepare_corpus
from app.ask_api import (
    AskResponse,
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.clarification import NeedsLandClarification, answer_with_clarification
from app.gemini_generation import (
    DEFAULT_LIMITS_PATH,
    GEMINI_INSTRUCTION,
    GEMINI_INSTRUCTION_VERSION,
    MAX_RAW_OUTPUT_CHARS,
    OUTCOMES,
    GatedGeminiGenerator,
    GeminiDraftClient,
    GeminiDraftRequest,
    GeminiLimits,
    MalformedDraftError,
    ProviderResolution,
    RateLimiter,
    evaluate_gemini_limits,
    load_gemini_limits,
    parse_draft,
    resolve_generation_provider,
    resolve_startup_provider,
)
from app.generation import (
    LEAD_IN,
    NOTICE,
    DraftAnswer,
    ExtractiveGroundingGenerator,
    verify_draft,
)
from app.main import create_app
from app.pilot_config import load_config
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.privacy_review import load_review_record, minimal_provider_payload
from app.redaction import land_context_values, redact_text
from app.retrieval import PASSAGE_SET_SCHEMA_VERSION, RetrievedPassage, Retriever, load_passage_set
from app.source_catalog import load_catalog

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLARIFICATION = FIXTURES / "clarification"
ABSTENTION = FIXTURES / "abstention"
SYNTHETIC_REVIEW = FIXTURES / "privacy" / "synthetic_approved_review.json"
SYNTHETIC_LIMITS = FIXTURES / "privacy" / "synthetic_gemini_limits.json"
MODULE_PATH = BACKEND_ROOT / "app" / "gemini_generation.py"
FIXED_DAY = date(2026, 10, 13)
MODEL = "synthetic-model-for-tests"
GEMINI_ENV = {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": MODEL}

ANSWER_QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"
# A land name after a land word, the request municipality, and a parcel number.
PERSONAL_QUESTION = (
    "Mi finca Los Olivos está en Martos, polígono 12 parcela 345. "
    "¿Cuándo se presenta la solicitud anual de ejemplo?"
)
LAND_CONTEXT = {"mode": "selected", "lands": [{"id": "opaque-land-7f3a", "municipality": "Martos"}]}
SOLICITUD_FRAGMENT = "se presenta una vez al año"


# --- fakes and helpers -------------------------------------------------------------------


class FakeClock:
    def __init__(self, day: date = FIXED_DAY) -> None:
        self.now = 1000.0
        self.day = day

    def monotonic(self) -> float:
        return self.now

    def utc_day(self) -> date:
        return self.day


class FakeTransport:
    """Records every request; answers with a fixed text or a callable of the request."""

    def __init__(self, reply: str | Callable[[GeminiDraftRequest], str] | BaseException = "") -> None:
        self.reply = reply
        self.requests: list[GeminiDraftRequest] = []

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        if isinstance(self.reply, BaseException):
            raise self.reply
        if callable(self.reply):
            return self.reply(request)
        return self.reply


class RecordingEnv(dict):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.read: list[str] = []

    def get(self, key: str, default: Any = None) -> Any:
        self.read.append(key)
        return super().get(key, default)

    def __getitem__(self, key: str) -> Any:
        self.read.append(key)
        return super().__getitem__(key)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _limits() -> GeminiLimits:
    gate, limits = evaluate_gemini_limits(_json(SYNTHETIC_LIMITS), as_of=FIXED_DAY)
    assert gate.passed and limits is not None
    return limits


def _passage(excerpt: str, rank: int, *, critical: bool = False) -> RetrievedPassage:
    return RetrievedPassage(
        passage_id=f"fixture-catalog-passage-{rank}",
        source_id="fixture_catalog_source",
        title="Título sintético de catálogo",
        issuing_body="Organismo sintético",
        url="https://www.example.org/documento-sintetico",
        location="Art. 1 (fixture)",
        published_or_updated_on="2026-02-20",
        verified_on="2026-10-04",
        excerpt=excerpt,
        applicability=None,
        critical=critical,
        score=1.0,
        rank=rank,
    )


CANDIDATES = (
    (1, _passage("La solicitud anual se presenta una vez al año ante la oficina comarcal.", 1)),
    (2, _passage("El plazo sintético es de 30 días naturales.", 2, critical=True)),
    (3, _passage("Un tercer fragmento fuera de la ventana de citas.", 3)),
)
GOOD_DRAFT = json.dumps(
    {"status": "answered", "answer": "La solicitud anual se presenta una vez al año [1].", "sources": [1]},
    ensure_ascii=False,
)


def _draft(answer: str, sources: list, status: str = "answered") -> str:
    return json.dumps({"status": status, "answer": answer, "sources": sources}, ensure_ascii=False)


def _generator(
    transport: FakeTransport,
    *,
    clock: FakeClock | None = None,
    land_context: Any = LAND_CONTEXT,
    limits: GeminiLimits | None = None,
    log: list | None = None,
) -> GatedGeminiGenerator:
    active_limits = limits or _limits()
    active_clock = clock or FakeClock()
    records = log if log is not None else []
    return GatedGeminiGenerator(
        client=GeminiDraftClient(transport=transport, model=MODEL, limits=active_limits),
        limiter=RateLimiter(
            active_limits.max_requests_per_minute, active_limits.max_requests_per_day, active_clock
        ),
        clock=active_clock,
        land_context=land_context,
        log=lambda event, **fields: records.append({"event": event, **fields}),
    )


def _extractive(question: str = ANSWER_QUESTION) -> DraftAnswer:
    return ExtractiveGroundingGenerator(max_claims=2).generate(question, CANDIDATES, as_of=FIXED_DAY)


def _resolve(
    env: dict | None = None,
    *,
    record: Any = "synthetic",
    limits: Any = "synthetic",
    transport: Any = "fake",
) -> ProviderResolution:
    return resolve_generation_provider(
        GEMINI_ENV if env is None else env,
        record=_json(SYNTHETIC_REVIEW) if record == "synthetic" else record,
        limits_document=_json(SYNTHETIC_LIMITS) if limits == "synthetic" else limits,
        transport=FakeTransport(GOOD_DRAFT) if transport == "fake" else transport,
        as_of=FIXED_DAY,
        clock=FakeClock(),
    )


def _documents(folder: Path = CLARIFICATION) -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(folder / "catalog.json"),
        passages=load_passage_set(folder / "passages.json"),
    )


def _app(
    monkeypatch: pytest.MonkeyPatch,
    transport: FakeTransport | None,
    *,
    approved: bool,
    env: dict | None = None,
):
    for key, value in (GEMINI_ENV if env is None else env).items():
        monkeypatch.setenv(key, value)
    if approved:
        monkeypatch.setattr(gemini_module, "load_review_record", lambda: _json(SYNTHETIC_REVIEW))
        monkeypatch.setattr(gemini_module, "load_gemini_limits", lambda: _json(SYNTHETIC_LIMITS))
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}),
        retention_store=None,
        generation_transport=transport,
        generation_clock=FakeClock(),
    )
    application.dependency_overrides[get_corpus_documents] = _documents
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    return application


def _post(application, body: dict) -> Any:
    with TestClient(application) as client:
        return client.post("/ask", json=body)


def _body(question: str = ANSWER_QUESTION, land_context: dict | None = None) -> dict:
    return {"question": question, "land_context": land_context or {"mode": "general", "lands": []}}


def _baseline(monkeypatch: pytest.MonkeyPatch, body: dict) -> dict:
    with monkeypatch.context() as patch:
        for key in GEMINI_ENV:
            patch.delenv(key, raising=False)
        response = _post(_app(patch, None, approved=False, env={}), body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def captured_log() -> Iterator[io.StringIO]:
    logger = logging.getLogger(LOGGER_NAME)
    previous = list(logger.handlers)
    logger.handlers.clear()
    stream = io.StringIO()
    configure_operational_logging(stream)
    try:
        yield stream
    finally:
        logger.handlers.clear()
        logger.handlers.extend(previous)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list:
    attempts: list = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        attempts.append(args)
        raise AssertionError("no outbound connection may be attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    return attempts


def _log_lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


# --- Limits record -----------------------------------------------------------------------


def test_committed_limits_file_is_not_recorded() -> None:
    document = load_gemini_limits()

    assert DEFAULT_LIMITS_PATH == BACKEND_ROOT / "config" / "gemini_provider_limits.json"
    assert document is not None
    assert all(value is None for key, value in document.items() if key != "schema_version")
    gate, limits = evaluate_gemini_limits(document, as_of=FIXED_DAY)
    assert gate.blockers == ("gemini_limits_not_recorded",)
    assert limits is None


def test_synthetic_limits_fixture_passes_and_is_labelled() -> None:
    document = _json(SYNTHETIC_LIMITS)

    assert document["cost_reference"].startswith("SYNTHETIC TEST FIXTURE")
    assert _limits() == GeminiLimits(10.0, 512, 3, 5, document["cost_reference"], date(2026, 10, 1))


def test_missing_or_unreadable_limits_are_unreadable(tmp_path: Path) -> None:
    broken = tmp_path / "limits.json"
    broken.write_text("{not json", encoding="utf-8")

    assert load_gemini_limits(tmp_path / "absent.json") is None
    assert load_gemini_limits(broken) is None
    assert evaluate_gemini_limits(None, as_of=FIXED_DAY)[0].blockers == ("gemini_limits_unreadable",)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(extra=1),
        lambda d: d.pop("recorded_on"),
        lambda d: d.update(schema_version="gemini-provider-limits-v2"),
        lambda d: d.update(max_output_tokens=True),
        lambda d: d.update(timeout_seconds=False),
        lambda d: d.update(max_requests_per_day=10.0),
        lambda d: d.update(timeout_seconds="10"),
        lambda d: d.update(cost_reference="  "),
        lambda d: d.update(recorded_on="2026-13-40"),
    ],
)
def test_malformed_limits_are_invalid(change: Callable[[dict], Any]) -> None:
    document = _json(SYNTHETIC_LIMITS)
    change(document)

    gate, limits = evaluate_gemini_limits(document, as_of=FIXED_DAY)
    assert gate.blockers == ("gemini_limits_invalid",)
    assert limits is None


def test_any_null_limit_is_not_recorded() -> None:
    for key in ("timeout_seconds", "max_output_tokens", "cost_reference", "recorded_on"):
        document = _json(SYNTHETIC_LIMITS)
        document[key] = None
        assert evaluate_gemini_limits(document, as_of=FIXED_DAY)[0].blockers == ("gemini_limits_not_recorded",)


@pytest.mark.parametrize(
    "key, low, high",
    [
        ("timeout_seconds", 1, 30),
        ("max_output_tokens", 1, 2048),
        ("max_requests_per_minute", 1, 600),
        ("max_requests_per_day", 1, 100000),
    ],
)
def test_each_limit_bound_is_inclusive(key: str, low: int, high: int) -> None:
    for value, passes in ((low - 1, False), (low, True), (high, True), (high + 1, False)):
        document = _json(SYNTHETIC_LIMITS)
        document[key] = value
        gate, _ = evaluate_gemini_limits(document, as_of=FIXED_DAY)
        assert gate.passed is passes, (key, value)
        if not passes:
            assert gate.blockers == ("gemini_limits_out_of_range",)


def test_nan_timeout_is_out_of_range() -> None:
    document = _json(SYNTHETIC_LIMITS)
    document["timeout_seconds"] = float("nan")

    assert evaluate_gemini_limits(document, as_of=FIXED_DAY)[0].blockers == ("gemini_limits_out_of_range",)


def test_future_recorded_on_blocks() -> None:
    document = _json(SYNTHETIC_LIMITS)
    document["recorded_on"] = (FIXED_DAY + timedelta(days=1)).isoformat()

    assert evaluate_gemini_limits(document, as_of=FIXED_DAY)[0].blockers == ("gemini_limits_future_date",)
    document["recorded_on"] = FIXED_DAY.isoformat()
    assert evaluate_gemini_limits(document, as_of=FIXED_DAY)[0].passed


# --- Resolver ----------------------------------------------------------------------------


def test_only_all_valid_inputs_resolve_to_gemini() -> None:
    resolution = _resolve()

    assert resolution.provider == "gemini"
    assert resolution.blockers == ()
    assert resolution.gemini is not None
    assert resolution.gemini.client.model == MODEL
    assert isinstance(resolution.generator_for(LAND_CONTEXT), GatedGeminiGenerator)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"env": {}}, "gemini_not_configured"),
        ({"env": {"MANIJERO_GENERATION_PROVIDER": "extractive", "MANIJERO_GEMINI_MODEL": MODEL}}, "gemini_not_configured"),
        ({"env": {"MANIJERO_GENERATION_PROVIDER": "Gemini-x", "MANIJERO_GEMINI_MODEL": MODEL}}, "gemini_not_configured"),
        ({"env": {"MANIJERO_GENERATION_PROVIDER": "gemini"}}, "gemini_model_mismatch"),
        ({"env": {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": "other-model"}}, "gemini_model_mismatch"),
        ({"record": None}, "gemini_review_record_unreadable"),
        ({"limits": None}, "gemini_limits_unreadable"),
        ({"transport": None}, "gemini_transport_unavailable"),
    ],
)
def test_each_gate_input_independently_blocks(kwargs: dict, expected: str) -> None:
    resolution = _resolve(**kwargs)

    assert resolution.provider == "extractive"
    assert resolution.gemini is None
    assert expected in resolution.blockers
    assert resolution.generator_for(LAND_CONTEXT) is None


def test_unpassed_pilot_or_gemini_review_blocks() -> None:
    pilot_pending = _json(SYNTHETIC_REVIEW)
    pilot_pending["pilot_review"]["status"] = "pending"
    gemini_rejected = _json(SYNTHETIC_REVIEW)
    gemini_rejected["gemini_review"]["status"] = "rejected"

    assert "pilot_privacy_review_not_passed" in _resolve(record=pilot_pending).blockers
    assert "gemini_review_rejected" in _resolve(record=gemini_rejected).blockers
    assert _resolve(record=pilot_pending).gemini is None
    assert _resolve(record=gemini_rejected).gemini is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(max_output_tokens=None),
        lambda d: d.update(max_requests_per_day=0),
        lambda d: d.update(recorded_on="2099-01-01"),
        lambda d: d.update(schema_version="other"),
    ],
)
def test_each_limits_problem_blocks(mutate: Callable[[dict], Any]) -> None:
    document = _json(SYNTHETIC_LIMITS)
    mutate(document)

    resolution = _resolve(limits=document)
    assert resolution.provider == "extractive"
    assert any(code.startswith("gemini_limits_") for code in resolution.blockers)


def test_committed_records_block_with_fixed_codes_echoing_no_value() -> None:
    env = {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": "value-that-must-not-echo"}
    resolution = _resolve(env, record=load_review_record(), limits=load_gemini_limits())

    assert resolution.provider == "extractive"
    assert "pilot_privacy_review_not_passed" in resolution.blockers
    assert "gemini_review_pending" in resolution.blockers
    assert "gemini_limits_not_recorded" in resolution.blockers
    for code in resolution.blockers:
        assert "value-that-must-not-echo" not in code
        assert code.replace("_", "").isalpha()


def test_resolver_reads_only_the_two_provider_settings() -> None:
    env = RecordingEnv(
        GEMINI_ENV,
        GOOGLE_APPLICATION_CREDENTIALS="never-read",
        MANIJERO_RETENTION_DB="never-read",
    )

    resolution = _resolve(env)

    assert resolution.provider == "gemini"
    assert set(env.read) <= {"MANIJERO_GENERATION_PROVIDER", "MANIJERO_GEMINI_MODEL"}


def test_startup_resolution_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(gemini_module, "load_review_record", explode)

    resolution = resolve_startup_provider(FakeTransport(GOOD_DRAFT), FakeClock())
    assert resolution == ProviderResolution("extractive", ("generation_provider_unresolved",))


# --- Minimal payload ---------------------------------------------------------------------


def test_transport_receives_only_the_minimal_payload() -> None:
    transport = FakeTransport(GOOD_DRAFT)
    candidates = (
        (1, _passage("La solicitud anual se presenta una vez al año.", 1)),
        (2, _passage("Otro fragmento revisado de ejemplo.", 2)),
        (3, _passage("Un fragmento fuera de la ventana.", 3)),
    )

    _generator(transport).generate(PERSONAL_QUESTION, candidates, as_of=FIXED_DAY)

    assert len(transport.requests) == 1
    request = transport.requests[0]
    limits = _limits()
    redacted = redact_text(PERSONAL_QUESTION, land_context_values(LAND_CONTEXT))
    assert request.model == MODEL
    assert request.instruction == GEMINI_INSTRUCTION
    assert request.instruction_version == GEMINI_INSTRUCTION_VERSION == "gemini-draft-v1"
    assert request.max_output_tokens == limits.max_output_tokens
    assert request.timeout_seconds == limits.timeout_seconds
    assert json.loads(request.payload_json) == minimal_provider_payload(
        redacted,
        [
            {"passage_id": "1", "text": "La solicitud anual se presenta una vez al año."},
            {"passage_id": "2", "text": "Otro fragmento revisado de ejemplo."},
        ],
    )
    serialized = repr(request)
    for forbidden in (
        "opaque-land-7f3a",
        "Martos",
        "Los Olivos",
        "345",
        "fixture-catalog-passage",
        "fixture_catalog_source",
        "example.org",
        "Título sintético",
        "Organismo sintético",
        "2026-02-20",
        "2026-10-04",
        "2026-10-13",
        "2026",
        "selected",
        "Un fragmento fuera de la ventana",
    ):
        assert forbidden not in serialized, forbidden


def test_instruction_pins_the_drafting_rules_and_contains_no_digit_or_link() -> None:
    lowered = GEMINI_INSTRUCTION.lower()

    for rule in ("solo con la información", "[1]", "literalmente", "nunca digas", "no añadas", "json"):
        assert rule in lowered
    assert "http" not in lowered
    assert NOTICE not in GEMINI_INSTRUCTION and LEAD_IN not in GEMINI_INSTRUCTION


# --- Parsing -----------------------------------------------------------------------------


def test_parse_accepts_a_well_formed_draft() -> None:
    assert parse_draft(GOOD_DRAFT, (1, 2)) == DraftAnswer(
        "answered", "La solicitud anual se presenta una vez al año [1].", (1,)
    )
    assert parse_draft(_draft("", [], status="abstained"), (1, 2)).status == "abstained"


@pytest.mark.parametrize(
    "text",
    [
        "La solicitud se presenta una vez al año [1].",
        "```json\n" + GOOD_DRAFT + "\n```",
        "[" + GOOD_DRAFT + "]",
        json.dumps({"status": "answered", "answer": "x [1]", "sources": [1], "extra": 1}),
        json.dumps({"status": "answered", "answer": "x [1]"}),
        '{"status": "answered", "status": "answered", "answer": "x [1]", "sources": [1]}',
        _draft("x [1]", [1], status="maybe"),
        json.dumps({"status": "answered", "answer": 5, "sources": [1]}),
        json.dumps({"status": "answered", "answer": "x [1]", "sources": "1"}),
        json.dumps({"status": "answered", "answer": "x [1]", "sources": [True]}),
        json.dumps({"status": "answered", "answer": "x [1]", "sources": [1.0]}),
        _draft("x [1][1]", [1, 1]),
        _draft("x [7]", [7]),
        _draft("   ", [1]),
        _draft("a" * 1201 + " [1]", [1]),
        _draft("x [1]", [1]) + " " * MAX_RAW_OUTPUT_CHARS,
        _draft("Según los documentos oficiales revisados: x [1]", [1]),
        _draft("x [1]. " + NOTICE, [1]),
        _draft("Consulta https://example.org [1]", [1]),
        _draft("Consulta WWW.example.org [1]", [1]),
        None,
    ],
)
def test_parse_rejects_every_malformed_class(text: Any) -> None:
    with pytest.raises(MalformedDraftError):
        parse_draft(text, (1, 2))


def test_malformed_error_carries_no_output_text() -> None:
    with pytest.raises(MalformedDraftError) as error:
        parse_draft(_draft("Texto secreto del modelo [9]", [9]), (1, 2))

    assert "secreto" not in str(error.value)


# --- Generator outcomes ------------------------------------------------------------------


def test_a_verified_gemini_draft_is_used() -> None:
    log: list = []
    draft = _generator(FakeTransport(GOOD_DRAFT), log=log).generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY)

    assert draft == parse_draft(GOOD_DRAFT, (1, 2))
    assert verify_draft(draft, CANDIDATES).ok
    assert log == [{"event": "generation", "provider": "gemini", "outcome": "gemini_used"}]


class _Timeout:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock

    def __call__(self, request: GeminiDraftRequest) -> str:
        self.clock.now += request.timeout_seconds + 0.5
        return GOOD_DRAFT


def _outcome_cases() -> list:
    return [
        ("transport_error", lambda clock: RuntimeError("Texto secreto")),
        ("timeout", lambda clock: TimeoutError()),
        ("timeout", lambda clock: _Timeout(clock)),
        ("malformed_output", lambda clock: "no es JSON"),
        ("malformed_output", lambda clock: "```" + GOOD_DRAFT + "```"),
        ("malformed_output", lambda clock: _draft("x [5]", [5])),
        ("malformed_output", lambda clock: _draft("x [3]", [3])),  # outside the citation window
        ("malformed_output", lambda clock: _draft(LEAD_IN + " x [1]", [1])),
        ("provider_abstained", lambda clock: _draft("", [], status="abstained")),
        ("verifier_rejected", lambda clock: _draft("Tienes derecho a la solicitud anual [1].", [1])),
        ("verifier_rejected", lambda clock: _draft("La solicitud anual se presenta 3 veces [1].", [1])),
        ("verifier_rejected", lambda clock: _draft("El plazo sintético es de un mes [2].", [2])),
        ("verifier_rejected", lambda clock: _draft("La solicitud anual se presenta. Sin cita.", [])),
        ("verifier_rejected", lambda clock: _draft("La solicitud anual se presenta una vez al año [1].", [1, 2])),
    ]


@pytest.mark.parametrize("expected, make_reply", _outcome_cases())
def test_every_failure_falls_back_to_the_extractive_draft(expected: str, make_reply: Callable) -> None:
    clock = FakeClock()
    log: list = []
    transport = FakeTransport(make_reply(clock))

    draft = _generator(transport, clock=clock, log=log).generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY)

    assert draft == _extractive()
    assert log == [{"event": "generation", "provider": "gemini", "outcome": expected}]
    assert expected in OUTCOMES


def test_redaction_failure_falls_back_without_calling_the_transport() -> None:
    log: list = []
    transport = FakeTransport(GOOD_DRAFT)

    draft = _generator(transport, land_context={"mode": "selected", "lands": "not-a-list"}, log=log).generate(
        ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY
    )

    assert draft == _extractive()
    assert transport.requests == []
    assert log[0]["outcome"] == "redaction_failed"


def test_invalid_payload_falls_back_without_calling_the_transport() -> None:
    log: list = []
    transport = FakeTransport(GOOD_DRAFT)
    candidates = ((1, _passage(None, 1)),)  # type: ignore[arg-type]

    generator = _generator(transport, log=log)
    outcome, draft = generator._gemini_draft(ANSWER_QUESTION, candidates)

    assert (outcome, draft) == ("payload_invalid", None)
    assert transport.requests == []


def test_rate_limit_per_minute_and_per_day() -> None:
    clock = FakeClock()
    log: list = []
    transport = FakeTransport(GOOD_DRAFT)
    generator = _generator(transport, clock=clock, log=log)  # synthetic: 3/minute, 5/day

    outcomes = []
    for _ in range(4):
        generator.generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY)
        outcomes.append(log[-1]["outcome"])
    assert outcomes == ["gemini_used"] * 3 + ["rate_limited"]
    assert len(transport.requests) == 3
    assert generator.generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY) == _extractive()

    clock.now += 60
    for _ in range(3):
        generator.generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY)
        outcomes.append(log[-1]["outcome"])
    assert outcomes[-3:] == ["gemini_used", "gemini_used", "rate_limited"]  # the daily cap of 5

    clock.now += 60
    clock.day = FIXED_DAY + timedelta(days=1)
    generator.generate(ANSWER_QUESTION, CANDIDATES, as_of=FIXED_DAY)
    assert log[-1]["outcome"] == "gemini_used"
    assert len(transport.requests) == 6


def test_rate_limiter_never_exceeds_its_cap_under_threads() -> None:
    limiter = RateLimiter(per_minute=7, per_day=100, clock=FakeClock())
    granted: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(10):
            result = limiter.try_acquire()
            with lock:
                granted.append(result)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert granted.count(True) == 7


def test_generator_never_raises_and_logs_only_fixed_fields(captured_log: io.StringIO) -> None:
    clock = FakeClock()
    limits = _limits()
    generator = GatedGeminiGenerator(
        client=GeminiDraftClient(transport=FakeTransport(RuntimeError("Texto secreto")), model=MODEL, limits=limits),
        limiter=RateLimiter(3, 5, clock),
        clock=clock,
        land_context=LAND_CONTEXT,
    )

    assert generator.generate(PERSONAL_QUESTION, CANDIDATES, as_of=FIXED_DAY) == _extractive(PERSONAL_QUESTION)
    lines = _log_lines(captured_log)
    assert len(lines) == 1
    assert set(lines[0]) == {"event", "time", "provider", "outcome"}
    assert (lines[0]["event"], lines[0]["provider"], lines[0]["outcome"]) == ("generation", "gemini", "transport_error")
    for forbidden in ("secreto", "Olivos", "Martos", "solicitud", "opaque"):
        assert forbidden not in captured_log.getvalue()


# --- Pipeline order ----------------------------------------------------------------------


def _abstention_corpus() -> Retriever:
    corpus = prepare_corpus(
        load_catalog(ABSTENTION / "catalog.json"),
        load_passage_set(ABSTENTION / "passages.json"),
        FIXED_DAY,
        "2026",
    )
    assert isinstance(corpus, Retriever)
    return corpus


@pytest.mark.parametrize(
    "question, reason",
    [
        ("¿Cuánto dura el plazo ficticio de prueba?", "conflicting_evidence"),
        ("¿Qué dice el Real Decreto sintético de prueba sobre la solicitud anual?", "false_premise"),
        ("zzzz qqqq", "no_evidence"),
        ("   ", "invalid_question"),
    ],
)
def test_pre_check_abstentions_never_call_the_transport(question: str, reason: str) -> None:
    transport = FakeTransport(GOOD_DRAFT)
    general = {"mode": "general", "lands": []}

    result = answer_with_clarification(
        question, general, _abstention_corpus(), k=5, as_of=FIXED_DAY,
        generator=_generator(transport, land_context=general),
    )

    assert isinstance(result, Abstention)
    assert result.reason == reason
    assert transport.requests == []


def test_a_stale_corpus_never_calls_the_transport() -> None:
    transport = FakeTransport(GOOD_DRAFT)
    corpus = prepare_corpus(
        load_catalog(FIXTURES / "retrieval" / "catalog_expired.json"),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        FIXED_DAY,
    )

    result = answer_with_clarification(
        ANSWER_QUESTION, {"mode": "general", "lands": []}, corpus, k=5, as_of=FIXED_DAY,
        generator=_generator(transport),
    )

    assert isinstance(result, Abstention) and result.reason == "stale_evidence"
    assert transport.requests == []


def test_a_land_clarification_never_calls_the_transport() -> None:
    transport = FakeTransport(GOOD_DRAFT)
    lands = {
        "mode": "all_active",
        "lands": [{"id": "opaque-one", "water_regime": "irrigated"}, {"id": "opaque-two", "water_regime": "dryland"}],
    }
    corpus = prepare_corpus(
        load_catalog(CLARIFICATION / "catalog.json"), load_passage_set(CLARIFICATION / "passages.json"), FIXED_DAY, "2026"
    )

    result = answer_with_clarification(
        "¿Puedo regar mi olivar de ejemplo?", lands, corpus, k=5, as_of=FIXED_DAY,
        generator=_generator(transport, land_context=lands),
    )

    assert isinstance(result, NeedsLandClarification)
    assert transport.requests == []


# --- Route -------------------------------------------------------------------------------


def _solicitud_reply(request: GeminiDraftRequest) -> str:
    payload = json.loads(request.payload_json)
    handle = next(item["passage_id"] for item in payload["passages"] if SOLICITUD_FRAGMENT in item["text"])
    return _draft(f"Se presenta una vez al año [{handle}]", [int(handle)])


def test_committed_state_never_calls_an_injected_transport(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    baseline = _baseline(monkeypatch, _body())
    transport = FakeTransport(_solicitud_reply)
    captured_log.truncate(0)
    captured_log.seek(0)

    response = _post(_app(monkeypatch, transport, approved=False), _body())

    assert response.json() == baseline
    assert transport.requests == []
    assert no_network == []
    startup = [line for line in _log_lines(captured_log) if line["event"] == "generation_provider"]
    assert len(startup) == 1
    assert startup[0]["provider"] == "extractive"
    blockers = startup[0]["blockers"].split(",")
    assert {"gemini_review_pending", "gemini_limits_not_recorded"} <= set(blockers)
    assert "gemini_transport_unavailable" not in blockers
    assert MODEL not in captured_log.getvalue()


def test_default_app_has_no_transport_even_when_everything_else_passes(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    application = _app(monkeypatch, None, approved=True)

    resolution = application.state.generation_provider
    assert resolution.provider == "extractive"
    assert resolution.blockers == ("gemini_transport_unavailable",)
    assert _post(application, _body()).json() == _baseline(monkeypatch, _body())


def test_verified_gemini_draft_reaches_ask_inside_the_code_owned_shell(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    transport = FakeTransport(_solicitud_reply)

    response = _post(_app(monkeypatch, transport, approved=True), _body())

    assert response.status_code == 200
    body = response.json()
    AskResponse.model_validate(body)
    assert set(body) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
    assert body["status"] == "answered"
    assert body["answer"] == f"{LEAD_IN} Se presenta una vez al año [1] {NOTICE}"
    assert body["answer"].count(NOTICE) == 1 and body["answer"].count(LEAD_IN) == 1
    assert len(body["sources"]) == 1 and SOLICITUD_FRAGMENT in body["sources"][0]["excerpt"]
    assert body["land_ids_to_choose"] == []
    assert len(transport.requests) == 1
    assert no_network == []
    outcomes = [line["outcome"] for line in _log_lines(captured_log) if line["event"] == "generation"]
    assert outcomes == ["gemini_used"]


@pytest.mark.parametrize(
    "reply",
    [
        RuntimeError("down"),
        "no es JSON",
        _draft("Tienes derecho a cobrar 500 euros [1].", [1]),
        _draft("", [], status="abstained"),
    ],
)
def test_a_failed_gemini_draft_on_ask_equals_the_extractive_baseline(
    monkeypatch: pytest.MonkeyPatch, reply: Any, no_network: list
) -> None:
    land = {"mode": "selected", "lands": [{"id": "opaque-land-7f3a", "municipality": "Martos"}]}
    baseline = _baseline(monkeypatch, _body(PERSONAL_QUESTION, land))
    transport = FakeTransport(reply)

    response = _post(_app(monkeypatch, transport, approved=True), _body(PERSONAL_QUESTION, land))

    assert response.json() == baseline
    assert len(transport.requests) == 1
    sent = repr(transport.requests[0])
    for forbidden in ("opaque-land-7f3a", "Martos", "Los Olivos", "345"):
        assert forbidden not in sent


def test_route_clarification_and_invalid_requests_never_call_the_transport(
    monkeypatch: pytest.MonkeyPatch, no_network: list
) -> None:
    transport = FakeTransport(_solicitud_reply)
    application = _app(monkeypatch, transport, approved=True)
    lands = {
        "mode": "all_active",
        "lands": [{"id": "opaque-one", "water_regime": "irrigated"}, {"id": "opaque-two", "water_regime": "dryland"}],
    }

    with TestClient(application) as client:
        clarification = client.post("/ask", json=_body("¿Puedo regar mi olivar de ejemplo?", lands))
        invalid = client.post("/ask", json={"question": "", "land_context": {"mode": "general", "lands": []}})
        uncovered = client.post("/ask", json=_body("zzzz qqqq"))

    assert clarification.json()["status"] == "needs_land_clarification"
    assert invalid.status_code == 422
    assert uncovered.json()["status"] == "abstained"
    assert transport.requests == []


# --- Guards: nothing reaches Google, no secret, no dependency ----------------------------


def test_module_imports_no_network_library() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {"socket", "ssl", "http", "urllib", "httpx", "requests", "aiohttp", "google", "grpc"}
    assert not imported & forbidden
    assert not any(name.startswith("google") for name in imported)
    assert imported <= {
        "__future__", "dataclasses", "datetime", "json", "os", "pathlib", "threading", "time", "typing", "app",
    }


def test_module_names_no_key_or_credential_setting() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("API_KEY", "api_key", "GOOGLE_", "getenv", "environ[", "environ.get", "generativelanguage"):
        assert forbidden not in source


def test_no_requirements_file_names_a_google_package() -> None:
    files = list(BACKEND_ROOT.glob("requirements*.txt")) + [BACKEND_ROOT / "deploy" / "requirements-production.txt"]

    assert len(files) >= 3
    for path in files:
        assert "google" not in path.read_text(encoding="utf-8").lower(), path.name
