"""Tests for the loopback local (Ollama) drafting provider.

No test needs Ollama or any network: every HTTP call goes to an in-process fake opener, the
real-opener tests patch ``socket.create_connection`` (or use an in-process loopback server
on an ephemeral port for the redirect check), and time comes from a fake clock. The model
record used by the route tests is a clearly labelled synthetic fixture.
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import http.server
import importlib.util
import io
import json
import logging
import math
from pathlib import Path
import socket
import subprocess
import threading
from typing import Any, Callable, Iterator
import urllib.error
import urllib.parse
import urllib.request

import pytest
from fastapi.testclient import TestClient

import app.gemini_generation as gemini_module
import app.local_generation as local_module
from app.abstention import Abstention, prepare_corpus
from app.ask_api import (
    AskResponse,
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.clarification import answer_with_clarification
from app.gemini_generation import (
    GEMINI_INSTRUCTION,
    GeminiDraftRequest,
    ProviderResolution,
    resolve_startup_provider,
)
from app.generation import LEAD_IN, NOTICE
from app.local_generation import (
    DEFAULT_RECORD_PATH,
    DRAFT_JSON_SCHEMA,
    MAX_RESPONSE_BYTES,
    MEMORY_BUDGET_BYTES,
    OLLAMA_BASE_URL,
    LocalTransportError,
    OllamaTransport,
    evaluate_local_model_record,
    load_local_model_record,
    loopback_opener,
    resolve_local_provider,
    resolve_startup_generation,
)
from app.main import create_app
from app.pilot_config import load_config
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.privacy_review import generation_provider_problem, load_review_record, minimal_provider_payload
from app.redaction import land_context_values, redact_text
from app.retrieval import PASSAGE_SET_SCHEMA_VERSION, RetrievedPassage, load_passage_set
from app.source_catalog import load_catalog

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLARIFICATION = FIXTURES / "clarification"
ABSTENTION = FIXTURES / "abstention"
SYNTHETIC_RECORD = FIXTURES / "local_generation" / "synthetic_model_record.json"
SYNTHETIC_REVIEW = FIXTURES / "privacy" / "synthetic_approved_review.json"
MODULE_PATH = BACKEND_ROOT / "app" / "local_generation.py"
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "measure_local_generation.py"
FIXED_DAY = date(2026, 10, 13)
MODEL = "synthetic-local-model:test"
DIGEST = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
LOCAL_ENV = {"MANIJERO_GENERATION_PROVIDER": "local", "MANIJERO_LOCAL_MODEL": MODEL}
ENV_KEYS = ("MANIJERO_GENERATION_PROVIDER", "MANIJERO_LOCAL_MODEL", "MANIJERO_GEMINI_MODEL")

ANSWER_QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"
PERSONAL_QUESTION = (
    "Mi finca Los Olivos está en Martos, polígono 12 parcela 345. "
    "¿Cuándo se presenta la solicitud anual de ejemplo?"
)
PERSONAL_LAND = {"mode": "selected", "lands": [{"id": "opaque-land-7f3a", "municipality": "Martos"}]}
SOLICITUD_FRAGMENT = "se presenta una vez al año"
TAGS_OK = {"models": [{"name": MODEL, "model": MODEL, "digest": DIGEST, "size": 1000000}]}


# --- fakes and helpers -------------------------------------------------------------------


class FakeClock:
    def __init__(self, day: date = FIXED_DAY) -> None:
        self.now = 1000.0
        self.day = day

    def monotonic(self) -> float:
        return self.now

    def utc_day(self) -> date:
        return self.day


class FakeResponse:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self, size: int = -1) -> bytes:
        return self._raw if size < 0 else self._raw[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


Reply = Any  # dict (JSON), bytes (raw body), BaseException, or callable(body) -> one of those


class FakeOpener:
    """Records every request; replies per path with JSON, raw bytes, or an exception."""

    def __init__(self, chat: Reply = None, tags: Reply = None) -> None:
        self.replies = {"/api/tags": TAGS_OK if tags is None else tags, "/api/chat": chat}
        self.calls: list[dict] = []

    def open(self, request: urllib.request.Request, timeout: float | None = None) -> FakeResponse:
        parsed = urllib.parse.urlsplit(request.full_url)
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.calls.append(
            {"url": request.full_url, "host": parsed.hostname, "port": parsed.port, "path": parsed.path,
             "method": request.get_method(), "body": body, "timeout": timeout}
        )
        reply = self.replies[parsed.path]
        if callable(reply) and not isinstance(reply, BaseException):
            reply = reply(body)
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, bytes):
            return FakeResponse(reply)
        return FakeResponse(json.dumps(reply, ensure_ascii=False).encode("utf-8"))

    def paths(self) -> list[str]:
        return [call["path"] for call in self.calls]


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


def _record():
    gate, record = evaluate_local_model_record(_json(SYNTHETIC_RECORD), as_of=FIXED_DAY)
    assert gate.passed and record is not None
    return record


def _draft(answer: str, sources: list, status: str = "answered") -> str:
    return json.dumps({"status": status, "answer": answer, "sources": sources}, ensure_ascii=False)


def _chat(content: str, **metrics: Any) -> dict:
    return {"model": MODEL, "message": {"role": "assistant", "content": content}, "done": True, **metrics}


def _solicitud_handle(body: dict) -> int:
    payload = json.loads(body["messages"][1]["content"])
    return int(next(item["passage_id"] for item in payload["passages"] if SOLICITUD_FRAGMENT in item["text"]))


def _solicitud_reply(body: dict) -> dict:
    handle = _solicitud_handle(body)
    return _chat(_draft(f"Se presenta una vez al año [{handle}]", [handle]))


def _request(**overrides: Any) -> GeminiDraftRequest:
    values = dict(
        model=MODEL,
        instruction=GEMINI_INSTRUCTION,
        instruction_version="gemini-draft-v1",
        payload_json=json.dumps({"question": "q", "passages": []}),
        max_output_tokens=400,
        timeout_seconds=10.0,
    )
    values.update(overrides)
    return GeminiDraftRequest(**values)


def _documents(folder: Path = CLARIFICATION) -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(folder / "catalog.json"),
        passages=load_passage_set(folder / "passages.json"),
    )


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _app(
    monkeypatch: pytest.MonkeyPatch,
    opener: FakeOpener | None,
    *,
    env: dict | None = None,
    clock: FakeClock | None = None,
):
    _clear_env(monkeypatch)
    for key, value in (LOCAL_ENV if env is None else env).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(local_module, "load_local_model_record", lambda: _json(SYNTHETIC_RECORD))
    if opener is not None:
        monkeypatch.setattr(local_module, "loopback_opener", lambda: opener)
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}),
        retention_store=None,
        generation_clock=clock or FakeClock(),
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
        response = _post(_app(patch, None, env={}), body)
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


def _generation_lines(stream: io.StringIO) -> list[dict]:
    return [line for line in _log_lines(stream) if line["event"] == "generation"]


# --- Model record ------------------------------------------------------------------------


def test_committed_record_passes_and_pins_the_contract_model() -> None:
    document = load_local_model_record()

    assert DEFAULT_RECORD_PATH == BACKEND_ROOT / "config" / "local_generation_model.json"
    assert document is not None
    gate, record = evaluate_local_model_record(document, as_of=datetime.now(timezone.utc).date())
    assert gate.passed, gate.blockers
    assert record is not None
    assert record.model == "mistral-small3.2:24b-instruct-2506-q4_K_M"
    assert record.license == "Apache-2.0"
    assert 0 < record.size_bytes <= MEMORY_BUDGET_BYTES
    assert (record.timeout_seconds, record.max_output_tokens, record.num_ctx) == (10.0, 400, 4096)
    assert (record.max_requests_per_minute, record.max_requests_per_day, record.keep_alive_seconds) == (
        30, 2000, 1800,
    )
    assert record.limits().cost_reference == "local-no-spend"


def test_synthetic_record_passes_and_is_labelled() -> None:
    record = _record()

    assert record.license_reference.startswith("SYNTHETIC TEST FIXTURE")
    assert (record.model, record.digest, record.recorded_on) == (MODEL, DIGEST, date(2026, 10, 1))


def test_missing_or_unreadable_record_is_unreadable(tmp_path: Path) -> None:
    broken = tmp_path / "record.json"
    broken.write_text("{not json", encoding="utf-8")
    listed = tmp_path / "list.json"
    listed.write_text("[]", encoding="utf-8")

    assert load_local_model_record(tmp_path / "absent.json") is None
    assert load_local_model_record(broken) is None
    assert load_local_model_record(listed) is None
    assert evaluate_local_model_record(None, as_of=FIXED_DAY)[0].blockers == ("local_model_record_unreadable",)


def _changed(**changes: Any) -> dict:
    document = _json(SYNTHETIC_RECORD)
    for key, value in changes.items():
        if value is _DELETE:
            del document[key]
        else:
            document[key] = value
    return document


_DELETE = object()


@pytest.mark.parametrize(
    "changes",
    [
        {"extra": 1},
        {"license": _DELETE},
        {"schema_version": "local-generation-model-v2"},
        {"num_ctx": True},
        {"size_bytes": 1.5},
        {"timeout_seconds": "10"},
        {"timeout_seconds": False},
        {"digest": DIGEST.upper()},
        {"digest": DIGEST[:-1]},
        {"digest": "sha256:" + DIGEST},
        {"license": ""},
        {"license": "Apache 2.0"},
        {"license_reference": "   "},
        {"parameter_size": None},
        {"quantization": 4},
        {"model": "two words"},
        {"model": ""},
        {"model": "x" * 129},
        {"model": None},
        {"recorded_on": "13/10/2026"},
        {"recorded_on": None},
    ],
)
def test_wrong_shape_is_invalid(changes: dict) -> None:
    gate, record = evaluate_local_model_record(_changed(**changes), as_of=FIXED_DAY)

    assert gate.blockers == ("local_model_record_invalid",)
    assert record is None


@pytest.mark.parametrize(
    "key, low, high",
    [
        ("num_ctx", 2048, 32768),
        ("timeout_seconds", 1, 14),
        ("max_output_tokens", 1, 1024),
        ("max_requests_per_minute", 1, 600),
        ("max_requests_per_day", 1, 100000),
        ("keep_alive_seconds", 0, 86400),
    ],
)
def test_each_bound_is_inclusive_and_one_past_is_out_of_range(key: str, low: int, high: int) -> None:
    assert evaluate_local_model_record(_changed(**{key: low}), as_of=FIXED_DAY)[0].passed
    assert evaluate_local_model_record(_changed(**{key: high}), as_of=FIXED_DAY)[0].passed
    for value in (low - 1, high + 1):
        gate, record = evaluate_local_model_record(_changed(**{key: value}), as_of=FIXED_DAY)
        assert gate.blockers == ("local_model_record_out_of_range",), (key, value)
        assert record is None


def test_nan_timeout_and_zero_size_are_out_of_range() -> None:
    assert evaluate_local_model_record(_changed(timeout_seconds=math.nan), as_of=FIXED_DAY)[0].blockers == (
        "local_model_record_out_of_range",
    )
    assert evaluate_local_model_record(_changed(size_bytes=0), as_of=FIXED_DAY)[0].blockers == (
        "local_model_record_out_of_range",
    )
    assert evaluate_local_model_record(_changed(size_bytes=1), as_of=FIXED_DAY)[0].passed


def test_size_over_the_memory_budget_is_over_budget() -> None:
    at_budget = evaluate_local_model_record(_changed(size_bytes=50_000_000_000), as_of=FIXED_DAY)
    over = evaluate_local_model_record(_changed(size_bytes=50_000_000_001), as_of=FIXED_DAY)

    assert MEMORY_BUDGET_BYTES == 50_000_000_000
    assert at_budget[0].passed
    assert over[0].blockers == ("local_model_over_budget",) and over[1] is None


def test_future_recorded_on_is_a_future_date() -> None:
    gate, record = evaluate_local_model_record(_changed(recorded_on="2026-10-14"), as_of=FIXED_DAY)

    assert gate.blockers == ("local_model_record_future_date",)
    assert record is None
    assert evaluate_local_model_record(_changed(recorded_on="2026-10-13"), as_of=FIXED_DAY)[0].passed


# --- Resolver ----------------------------------------------------------------------------


def _resolve_local(
    env: dict,
    *,
    record: Any = "synthetic",
    pilot: bool = False,
    review: Any = None,
    transport: Any = None,
) -> ProviderResolution:
    return resolve_local_provider(
        env,
        record_document=_json(SYNTHETIC_RECORD) if record == "synthetic" else record,
        transport=transport,
        as_of=FIXED_DAY,
        clock=FakeClock(),
        pilot=pilot,
        review_record=review,
    )


@pytest.mark.parametrize("provider_env", [None, "extractive", "gemini", "local", "Local"])
@pytest.mark.parametrize("model_env", [None, "mistral-small3.2:24b", MODEL])
@pytest.mark.parametrize("pilot", [False, True])
@pytest.mark.parametrize("review", ["committed", "synthetic_approved"])
def test_only_all_valid_inputs_resolve_to_local(
    monkeypatch: pytest.MonkeyPatch, provider_env: str | None, model_env: str | None, pilot: bool, review: str
) -> None:
    _clear_env(monkeypatch)
    if provider_env is not None:
        monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", provider_env)
    if model_env is not None:
        monkeypatch.setenv("MANIJERO_LOCAL_MODEL", model_env)
    monkeypatch.setattr(local_module, "load_local_model_record", lambda: _json(SYNTHETIC_RECORD))
    review_record = load_review_record() if review == "committed" else _json(SYNTHETIC_REVIEW)
    monkeypatch.setattr(local_module, "load_review_record", lambda: review_record)
    built: list = []
    monkeypatch.setattr(local_module, "OllamaTransport", lambda *args, **kwargs: built.append(args) or object())

    resolution = resolve_startup_generation(clock=FakeClock(), pilot=pilot)

    expected_local = (
        provider_env == "local" and model_env == MODEL and (not pilot or review == "synthetic_approved")
    )
    assert (resolution.provider == "local") is expected_local
    assert len(built) == (1 if expected_local else 0)
    if expected_local:
        assert resolution.blockers == () and resolution.gemini is not None
        assert resolution.gemini.provider_name == "local"
        assert resolution.gemini.used_outcome == "local_used"
    else:
        assert resolution.provider == "extractive" and resolution.blockers
    if provider_env == "local" and not expected_local:
        expected_blockers = set()
        if model_env != MODEL:
            expected_blockers.add("local_model_mismatch")
        if pilot and review == "committed":
            expected_blockers.add("pilot_privacy_review_not_passed")
        assert set(resolution.blockers) == expected_blockers
    for blocker in resolution.blockers:
        assert MODEL not in blocker and "mistral" not in blocker


@pytest.mark.parametrize("provider_env", [None, "gemini", "extractive", "Local", "LOCAL"])
def test_non_local_values_delegate_to_the_unchanged_gemini_resolution(
    monkeypatch: pytest.MonkeyPatch, provider_env: str | None
) -> None:
    _clear_env(monkeypatch)
    if provider_env is not None:
        monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", provider_env)
    monkeypatch.setenv("MANIJERO_LOCAL_MODEL", MODEL)
    clock = FakeClock()

    assert resolve_startup_generation(clock=clock) == resolve_startup_provider(None, clock)


@pytest.mark.parametrize(
    "record, expected",
    [
        (None, ("local_model_record_unreadable",)),
        ({"schema_version": "local-generation-model-v1"}, ("local_model_record_invalid",)),
        ("out_of_range", ("local_model_record_out_of_range",)),
        ("over_budget", ("local_model_over_budget",)),
        ("future", ("local_model_record_future_date",)),
    ],
)
def test_each_record_problem_is_one_fixed_blocker(record: Any, expected: tuple) -> None:
    documents = {
        "out_of_range": _changed(num_ctx=1),
        "over_budget": _changed(size_bytes=MEMORY_BUDGET_BYTES + 1),
        "future": _changed(recorded_on="2027-01-01"),
    }

    resolution = _resolve_local(LOCAL_ENV, record=documents.get(record, record) if isinstance(record, str) else record)

    assert resolution == ProviderResolution("extractive", expected)


def test_model_env_unset_or_different_is_a_model_mismatch() -> None:
    assert _resolve_local({"MANIJERO_GENERATION_PROVIDER": "local"}).blockers == ("local_model_mismatch",)
    assert _resolve_local({**LOCAL_ENV, "MANIJERO_LOCAL_MODEL": "other:tag"}).blockers == ("local_model_mismatch",)
    assert _resolve_local(LOCAL_ENV, pilot=True, review=load_review_record()).blockers == (
        "pilot_privacy_review_not_passed",
    )
    assert _resolve_local(LOCAL_ENV, pilot=True, review=_json(SYNTHETIC_REVIEW)).provider == "local"


def test_resolver_reads_only_the_two_local_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    env = RecordingEnv(
        LOCAL_ENV,
        MANIJERO_GEMINI_MODEL="never-read",
        MANIJERO_RETENTION_DB="never-read",
        HTTP_PROXY="never-read",
    )
    monkeypatch.setattr(local_module.os, "environ", env)
    monkeypatch.setattr(local_module, "load_local_model_record", lambda: _json(SYNTHETIC_RECORD))

    resolution = resolve_startup_generation(clock=FakeClock())

    assert resolution.provider == "local"
    assert set(env.read) == {"MANIJERO_GENERATION_PROVIDER", "MANIJERO_LOCAL_MODEL"}


def test_startup_resolution_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> None:
        raise RuntimeError("boom")

    _clear_env(monkeypatch)
    for key, value in LOCAL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(local_module, "load_local_model_record", explode)

    assert resolve_startup_generation(clock=FakeClock()) == ProviderResolution(
        "extractive", ("generation_provider_unresolved",)
    )


def test_local_is_an_accepted_provider_value_for_preflight() -> None:
    assert generation_provider_problem({"MANIJERO_GENERATION_PROVIDER": "local"}) is None
    assert generation_provider_problem({"MANIJERO_GENERATION_PROVIDER": "Local"}) == "generation_provider_invalid"


# --- Transport (fake opener) -------------------------------------------------------------


def test_transport_checks_tags_once_then_posts_the_exact_chat_body() -> None:
    opener = FakeOpener(chat=_chat("{}"))
    transport = OllamaTransport(_record(), opener=opener, clock=FakeClock())
    request = _request(payload_json=json.dumps({"question": "¿Cuándo?", "passages": []}, ensure_ascii=False))

    assert transport.send(request) == "{}"
    assert transport.send(request) == "{}"

    assert opener.paths() == ["/api/tags", "/api/chat", "/api/chat"]
    assert {(call["host"], call["port"]) for call in opener.calls} == {("127.0.0.1", 11434)}
    assert all(call["url"].startswith(OLLAMA_BASE_URL + "/api/") for call in opener.calls)
    assert opener.calls[0]["method"] == "GET" and opener.calls[0]["timeout"] == 2.0
    chat = opener.calls[1]
    assert chat["method"] == "POST" and chat["timeout"] == 10.0
    assert chat["body"] == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": GEMINI_INSTRUCTION},
            {"role": "user", "content": request.payload_json},
        ],
        "stream": False,
        "format": DRAFT_JSON_SCHEMA,
        "options": {"temperature": 0, "seed": 0, "num_ctx": 4096, "num_predict": 400},
        "keep_alive": "1800s",
    }
    assert DRAFT_JSON_SCHEMA["required"] == ["status", "answer", "sources"]
    assert DRAFT_JSON_SCHEMA["properties"]["status"]["enum"] == ["answered", "abstained"]
    assert DRAFT_JSON_SCHEMA["properties"]["sources"]["items"] == {"type": "integer"}


def test_a_request_for_another_model_raises_without_any_call() -> None:
    opener = FakeOpener(chat=_chat("{}"))

    with pytest.raises(LocalTransportError) as error:
        OllamaTransport(_record(), opener=opener).send(_request(model="other:tag"))

    assert error.value.code == "model_mismatch"
    assert opener.calls == []


def test_default_opener_ignores_proxies_and_refuses_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
        monkeypatch.setenv(key, "http://proxy.invalid:3128")

    opener = loopback_opener()

    assert not any(isinstance(handler, urllib.request.ProxyHandler) and handler.proxies for handler in opener.handlers)
    assert not any(hasattr(handler, "proxy_open") for handler in opener.handlers)
    assert not any(isinstance(handler, urllib.request.HTTPSHandler) for handler in opener.handlers)
    redirects = [handler for handler in opener.handlers if isinstance(handler, urllib.request.HTTPRedirectHandler)]
    assert len(redirects) == 1 and type(redirects[0]) is not urllib.request.HTTPRedirectHandler
    with pytest.raises(urllib.error.URLError):
        opener.open("https://127.0.0.1:11434/api/tags", timeout=1)  # no HTTPS handler exists


def test_a_redirect_is_refused_on_a_loopback_test_server(monkeypatch: pytest.MonkeyPatch) -> None:
    class Redirecting(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/elsewhere")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirecting)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            loopback_opener().open(f"http://127.0.0.1:{server.server_port}/api/tags", timeout=5)
        assert error.value.code == 302
        error.value.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "tags, chat, expected",
    [
        (urllib.error.URLError(ConnectionRefusedError()), None, "connection_refused"),
        (ConnectionRefusedError(), None, "connection_refused"),
        (TAGS_OK, urllib.error.URLError(ConnectionRefusedError()), "connection_refused"),
        (TAGS_OK, urllib.error.HTTPError(OLLAMA_BASE_URL, 404, "nf", {}, None), "model_not_found"),
        (TAGS_OK, urllib.error.HTTPError(OLLAMA_BASE_URL, 500, "Texto secreto", {}, None), "http_error"),
        (urllib.error.HTTPError(OLLAMA_BASE_URL, 503, "x", {}, None), None, "http_error"),
        (TAGS_OK, urllib.error.URLError(OSError("Texto secreto")), "http_error"),
        (TAGS_OK, b"no es JSON secreto", "response_invalid"),
        (TAGS_OK, b"[1, 2]", "response_invalid"),
        (TAGS_OK, b'{"message": "' + b"a" * MAX_RESPONSE_BYTES + b'"}', "response_invalid"),
        (TAGS_OK, {"model": MODEL, "done": True}, "response_invalid"),
        (TAGS_OK, {"message": {"role": "assistant"}}, "response_invalid"),
        (TAGS_OK, {"message": {"content": 5}}, "response_invalid"),
        ({"models": "nope"}, None, "response_invalid"),
        ({"models": []}, None, "model_not_found"),
        ({"models": [{"name": "other:tag", "digest": DIGEST}]}, None, "model_not_found"),
        ({"models": [{"name": MODEL, "digest": "f" * 64}]}, None, "model_digest_mismatch"),
        ({"models": [{"name": MODEL, "digest": "sha256:" + DIGEST}]}, None, "model_digest_mismatch"),
    ],
)
def test_every_failure_maps_to_a_fixed_code_without_response_text(tags: Any, chat: Any, expected: str) -> None:
    opener = FakeOpener(chat=chat, tags=tags)

    with pytest.raises(LocalTransportError) as error:
        OllamaTransport(_record(), opener=opener, clock=FakeClock()).send(_request())

    assert error.value.code == expected
    assert str(error.value) == expected
    assert "secreto" not in str(error.value) and "secreto" not in repr(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "reply",
    [socket.timeout("timed out"), TimeoutError(), urllib.error.URLError(socket.timeout("timed out"))],
)
def test_a_socket_timeout_is_re_raised_as_timeout_error(reply: BaseException) -> None:
    opener = FakeOpener(chat=reply)

    with pytest.raises(TimeoutError) as error:
        OllamaTransport(_record(), opener=opener, clock=FakeClock()).send(_request())

    assert not isinstance(error.value, LocalTransportError)


def test_the_tags_check_counts_against_the_request_timeout() -> None:
    clock = FakeClock()

    def slow_tags(body: Any) -> dict:
        clock.now += 3.0
        return TAGS_OK

    opener = FakeOpener(chat=_chat("{}"), tags=slow_tags)
    OllamaTransport(_record(), opener=opener, clock=clock).send(_request(timeout_seconds=10.0))
    assert opener.calls[1]["timeout"] == pytest.approx(7.0)

    def exhausting_tags(body: Any) -> dict:
        clock.now += 11.0
        return TAGS_OK

    exhausted = FakeOpener(chat=_chat("{}"), tags=exhausting_tags)
    with pytest.raises(TimeoutError):
        OllamaTransport(_record(), opener=exhausted, clock=clock).send(_request(timeout_seconds=10.0))
    assert exhausted.paths() == ["/api/tags"]


def test_a_digest_failure_is_not_cached_and_a_success_is() -> None:
    opener = FakeOpener(chat=_chat("{}"), tags={"models": [{"name": MODEL, "digest": "f" * 64}]})
    transport = OllamaTransport(_record(), opener=opener, clock=FakeClock())

    with pytest.raises(LocalTransportError):
        transport.send(_request())
    opener.replies["/api/tags"] = TAGS_OK
    transport.send(_request())
    transport.send(_request())

    assert opener.paths() == ["/api/tags", "/api/tags", "/api/chat", "/api/chat"]


def test_metrics_receive_only_the_six_non_negative_integer_fields() -> None:
    received: list = []
    reply = _chat(
        "{}",
        total_duration=5, load_duration=1, prompt_eval_count=7, prompt_eval_duration=2,
        eval_count=9, eval_duration=3, created_at="2026-10-31T00:00:00Z", done_reason="stop",
    )
    transport = OllamaTransport(_record(), opener=FakeOpener(chat=reply), clock=FakeClock(), on_metrics=received.append)
    transport.send(_request())

    assert received == [
        {"total_duration": 5, "load_duration": 1, "prompt_eval_count": 7, "prompt_eval_duration": 2,
         "eval_count": 9, "eval_duration": 3}
    ]

    received.clear()
    odd = _chat("{}", total_duration=-1, load_duration=True, eval_count=1.5, eval_duration="3")
    OllamaTransport(_record(), opener=FakeOpener(chat=odd), clock=FakeClock(), on_metrics=received.append).send(_request())
    assert received == [{}]


def test_a_failing_metrics_observer_never_breaks_a_draft() -> None:
    def explode(metrics: Any) -> None:
        raise RuntimeError("observer")

    transport = OllamaTransport(_record(), opener=FakeOpener(chat=_chat("ok")), clock=FakeClock(), on_metrics=explode)
    assert transport.send(_request()) == "ok"


def test_constructing_the_transport_makes_no_call(no_network: list) -> None:
    opener = FakeOpener(chat=_chat("{}"))

    OllamaTransport(_record(), opener=opener)
    OllamaTransport(_record())

    assert opener.calls == [] and no_network == []


# --- Off by default and the default real transport ---------------------------------------


def test_off_by_default_builds_no_transport_and_matches_the_baseline(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    built: list = []
    monkeypatch.setattr(local_module, "OllamaTransport", lambda *args, **kwargs: built.append(args))
    baseline = _baseline(monkeypatch, _body())
    captured_log.truncate(0)
    captured_log.seek(0)

    application = _app(monkeypatch, None, env={})
    response = _post(application, _body())

    assert response.json() == baseline
    assert built == [] and no_network == []
    assert application.state.generation_provider == resolve_startup_provider(None, FakeClock())
    startup = [line for line in _log_lines(captured_log) if line["event"] == "generation_provider"]
    assert len(startup) == 1
    assert startup[0]["provider"] == "extractive"
    assert startup[0]["blockers"] == "gemini_not_configured"
    assert _generation_lines(captured_log) == []


def test_the_default_real_transport_only_dials_loopback(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO
) -> None:
    baseline = _baseline(monkeypatch, _body())
    addresses: list = []

    def refuse(address: Any, *args: Any, **kwargs: Any) -> None:
        addresses.append(address)
        raise ConnectionRefusedError()

    monkeypatch.setattr(socket, "create_connection", refuse)
    for key in ("HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        monkeypatch.setenv(key, "http://proxy.invalid:3128")
    captured_log.truncate(0)
    captured_log.seek(0)

    application = _app(monkeypatch, None)
    assert application.state.generation_provider.provider == "local"
    response = _post(application, _body())

    assert response.json() == baseline
    assert addresses == [("127.0.0.1", 11434)]
    startup = [line for line in _log_lines(captured_log) if line["event"] == "generation_provider"]
    assert [(line["provider"], line["blockers"]) for line in startup] == [("local", "")]
    lines = _generation_lines(captured_log)
    assert [(line["provider"], line["outcome"]) for line in lines] == [("local", "transport_error")]
    assert set(lines[0]) == {"event", "time", "provider", "outcome"}


# --- Generator through /ask --------------------------------------------------------------


def test_a_verified_local_draft_is_used_inside_the_code_owned_shell(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    opener = FakeOpener(chat=_solicitud_reply)

    response = _post(_app(monkeypatch, opener), _body())

    assert response.status_code == 200
    body = response.json()
    AskResponse.model_validate(body)
    assert set(body) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
    assert body["status"] == "answered"
    assert body["answer"] == f"{LEAD_IN} Se presenta una vez al año [1] {NOTICE}"
    assert body["answer"].count(NOTICE) == 1 and body["answer"].count(LEAD_IN) == 1
    assert len(body["sources"]) == 1 and SOLICITUD_FRAGMENT in body["sources"][0]["excerpt"]
    assert opener.paths() == ["/api/tags", "/api/chat"]
    assert no_network == []
    lines = _generation_lines(captured_log)
    assert [(line["provider"], line["outcome"]) for line in lines] == [("local", "local_used")]


def test_the_chat_payload_is_the_minimal_redacted_payload_only(
    monkeypatch: pytest.MonkeyPatch, no_network: list
) -> None:
    opener = FakeOpener(chat=_solicitud_reply)

    _post(_app(monkeypatch, opener), _body(PERSONAL_QUESTION, PERSONAL_LAND))

    chat = [call for call in opener.calls if call["path"] == "/api/chat"]
    assert len(chat) == 1
    body = chat[0]["body"]
    assert set(body) == {"model", "messages", "stream", "format", "options", "keep_alive"}
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    user = body["messages"][1]["content"]
    payload = json.loads(user)
    redacted = redact_text(PERSONAL_QUESTION, land_context_values(PERSONAL_LAND))
    excerpts = {passage["text"] for passage in _documents().passages["passages"]}
    assert 1 <= len(payload["passages"]) <= 2
    assert [item["passage_id"] for item in payload["passages"]] == [
        str(rank) for rank in range(1, len(payload["passages"]) + 1)
    ]
    assert all(item["text"] in excerpts for item in payload["passages"])
    assert user == json.dumps(
        minimal_provider_payload(redacted, payload["passages"]), ensure_ascii=False, sort_keys=True
    )
    serialized = json.dumps(body, ensure_ascii=False)
    catalog = _documents().catalog["sources"]
    forbidden = [
        "opaque-land-7f3a", "Martos", "Los Olivos", "345", "selected",
        *(source["id"] for source in catalog),
        *(source["original_url"] for source in catalog),
        *(source["title"] for source in catalog),
        *(source["issuing_body"] for source in catalog),
        *(source["published_on"] for source in catalog),
        *(source["verified_on"] for source in catalog),
        *(passage["id"] for passage in _documents().passages["passages"]),
        "https://",
        "client",
    ]
    assert len(forbidden) >= 15
    for value in forbidden:
        assert value not in serialized, value


def _outcome_cases() -> list:
    return [
        ("transport_error", lambda clock: FakeOpener(chat=urllib.error.URLError(ConnectionRefusedError()))),
        ("timeout", lambda clock: FakeOpener(chat=urllib.error.URLError(socket.timeout("timed out")))),
        ("timeout", lambda clock: FakeOpener(chat=_advance_then(clock, 10.5, _solicitud_reply))),
        ("transport_error", lambda clock: FakeOpener(chat=urllib.error.HTTPError(OLLAMA_BASE_URL, 404, "x", {}, None))),
        ("transport_error", lambda clock: FakeOpener(chat=urllib.error.HTTPError(OLLAMA_BASE_URL, 500, "x", {}, None))),
        ("transport_error", lambda clock: FakeOpener(chat=b"<html>no es JSON</html>")),
        ("transport_error", lambda clock: FakeOpener(chat=b"{" + b" " * MAX_RESPONSE_BYTES + b"}")),
        ("transport_error", lambda clock: FakeOpener(chat={"done": True})),
        ("transport_error", lambda clock: FakeOpener(chat=_solicitud_reply, tags={"models": []})),
        ("transport_error", lambda clock: FakeOpener(chat=_solicitud_reply, tags={"models": [{"name": MODEL, "digest": "e" * 64}]})),
        ("malformed_output", lambda clock: FakeOpener(chat=_chat("no es JSON"))),
        ("malformed_output", lambda clock: FakeOpener(chat=_chat(_draft("x [5]", [5])))),
        ("provider_abstained", lambda clock: FakeOpener(chat=_chat(_draft("", [], status="abstained")))),
        ("verifier_rejected", lambda clock: FakeOpener(chat=lambda body: _chat(
            _draft(f"Tienes derecho a cobrar 500 euros [{_solicitud_handle(body)}].", [_solicitud_handle(body)])
        ))),
    ]


def _advance_then(clock: FakeClock, seconds: float, reply: Callable) -> Callable:
    def advance(body: Any) -> Any:
        clock.now += seconds
        return reply(body)

    return advance


@pytest.mark.parametrize("expected, make_opener", _outcome_cases())
def test_every_failure_on_ask_equals_the_extractive_baseline(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list, expected: str, make_opener: Callable
) -> None:
    baseline = _baseline(monkeypatch, _body(PERSONAL_QUESTION, PERSONAL_LAND))
    clock = FakeClock()
    opener = make_opener(clock)
    captured_log.truncate(0)
    captured_log.seek(0)

    response = _post(_app(monkeypatch, opener, clock=clock), _body(PERSONAL_QUESTION, PERSONAL_LAND))

    assert response.status_code == 200
    assert response.json() == baseline
    lines = _generation_lines(captured_log)
    assert [(line["provider"], line["outcome"]) for line in lines] == [("local", expected)]
    assert set(lines[0]) == {"event", "time", "provider", "outcome"}
    text = captured_log.getvalue()
    for forbidden in ("Olivos", "Martos", "solicitud", "opaque", "secreto", "euros", MODEL):
        assert forbidden not in text


def test_the_rate_limit_falls_back_without_calling_the_opener(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, no_network: list
) -> None:
    baseline = _baseline(monkeypatch, _body())
    opener = FakeOpener(chat=_chat(_draft("", [], status="abstained")))
    application = _app(monkeypatch, opener)  # synthetic record: 3 requests per minute
    captured_log.truncate(0)
    captured_log.seek(0)

    with TestClient(application) as client:
        responses = [client.post("/ask", json=_body()).json() for _ in range(4)]

    assert all(response == baseline for response in responses)
    assert [line["outcome"] for line in _generation_lines(captured_log)] == ["provider_abstained"] * 3 + ["rate_limited"]
    assert opener.paths().count("/api/chat") == 3


def test_a_redaction_failure_never_calls_the_opener(monkeypatch: pytest.MonkeyPatch, no_network: list) -> None:
    opener = FakeOpener(chat=_solicitud_reply)
    records: list = []
    resolution = _app(monkeypatch, opener).state.generation_provider
    generator = resolution.generator_for({"mode": "selected", "lands": "not-a-list"}, max_claims=2)
    generator.log = lambda event, **fields: records.append(fields)
    passage = RetrievedPassage(
        passage_id="p", source_id="s", title="t", issuing_body="b", url="https://example.org/x",
        location="l", published_or_updated_on="2026-02-20", verified_on="2026-10-04",
        excerpt="La solicitud anual se presenta una vez al año.", applicability=None, critical=False,
        score=1.0, rank=1,
    )
    candidates = ((1, passage),)

    generator.generate(ANSWER_QUESTION, candidates, as_of=FIXED_DAY)

    assert records == [{"provider": "local", "outcome": "redaction_failed"}]
    assert opener.calls == []


# --- Pipeline order ----------------------------------------------------------------------


def _abstention_corpus():
    return prepare_corpus(
        load_catalog(ABSTENTION / "catalog.json"),
        load_passage_set(ABSTENTION / "passages.json"),
        FIXED_DAY,
        "2026",
    )


def _local_generator(monkeypatch: pytest.MonkeyPatch, opener: FakeOpener, land_context: dict):
    resolution = _app(monkeypatch, opener).state.generation_provider
    assert resolution.provider == "local"
    return resolution.generator_for(land_context, max_claims=2)


@pytest.mark.parametrize(
    "question, reason",
    [
        ("¿Cuánto dura el plazo ficticio de prueba?", "conflicting_evidence"),
        ("¿Qué dice el Real Decreto sintético de prueba sobre la solicitud anual?", "false_premise"),
        ("zzzz qqqq", "no_evidence"),
        ("   ", "invalid_question"),
    ],
)
def test_pre_check_abstentions_never_call_the_opener(
    monkeypatch: pytest.MonkeyPatch, no_network: list, question: str, reason: str
) -> None:
    opener = FakeOpener(chat=_solicitud_reply)
    general = {"mode": "general", "lands": []}

    result = answer_with_clarification(
        question, general, _abstention_corpus(), k=5, as_of=FIXED_DAY,
        generator=_local_generator(monkeypatch, opener, general),
    )

    assert isinstance(result, Abstention) and result.reason == reason
    assert opener.calls == []


def test_a_stale_corpus_never_calls_the_opener(monkeypatch: pytest.MonkeyPatch, no_network: list) -> None:
    opener = FakeOpener(chat=_solicitud_reply)
    corpus = prepare_corpus(
        load_catalog(FIXTURES / "retrieval" / "catalog_expired.json"),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        FIXED_DAY,
    )

    result = answer_with_clarification(
        ANSWER_QUESTION, {"mode": "general", "lands": []}, corpus, k=5, as_of=FIXED_DAY,
        generator=_local_generator(monkeypatch, opener, {"mode": "general", "lands": []}),
    )

    assert isinstance(result, Abstention) and result.reason == "stale_evidence"
    assert opener.calls == []


def test_route_clarification_and_invalid_requests_never_call_the_opener(
    monkeypatch: pytest.MonkeyPatch, no_network: list
) -> None:
    opener = FakeOpener(chat=_solicitud_reply)
    application = _app(monkeypatch, opener)
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
    assert opener.calls == []


# --- Guards ------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_module_imports_only_stdlib_urllib_and_the_app() -> None:
    imported = _imports(MODULE_PATH)
    roots = {name.split(".")[0] for name in imported}

    assert not roots & {"httpx", "requests", "aiohttp", "subprocess", "grpc", "http"}
    assert not any(name.startswith("google") for name in roots)
    assert roots <= {
        "__future__", "dataclasses", "datetime", "json", "os", "pathlib", "re", "socket", "threading",
        "typing", "urllib", "app",
    }
    assert "app.local_generation" not in _imports(BACKEND_ROOT / "app" / "gemini_generation.py")


def test_module_has_one_loopback_url_and_no_url_setting() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert urllib.parse.urlsplit(OLLAMA_BASE_URL).hostname == "127.0.0.1"
    assert urllib.parse.urlsplit(OLLAMA_BASE_URL).port == 11434
    assert source.count("http://") == 1 and "https://" not in source
    for forbidden in ("0.0.0.0", "localhost", "OLLAMA_HOST", "getenv", "environ["):
        assert forbidden not in source
    assert source.count("environ.get(") == 1  # only the provider key; the model key goes through ``source``


def test_no_requirements_file_changed() -> None:
    files = sorted(BACKEND_ROOT.glob("requirements*.txt")) + [BACKEND_ROOT / "deploy" / "requirements-production.txt"]
    assert len(files) >= 3
    for path in files:
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            committed = subprocess.run(
                ["git", "show", f"HEAD:{relative}"], cwd=REPO_ROOT, capture_output=True, check=True, text=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            pytest.skip("git history unavailable")
        assert path.read_text(encoding="utf-8") == committed, relative
        assert "ollama" not in committed.lower()


# --- Measurement script helpers ----------------------------------------------------------


def _script():
    spec = importlib.util.spec_from_file_location("measure_local_generation", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_latencies_uses_nearest_rank_p95() -> None:
    script = _script()

    assert script.summarize_latencies([]) == {"count": 0, "median": None, "p95": None, "max": None}
    assert script.summarize_latencies([2.0]) == {"count": 1, "median": 2.0, "p95": 2.0, "max": 2.0}
    values = [float(value) for value in range(1, 21)]  # 1..20: rank ceil(0.95*20)=19
    assert script.summarize_latencies(values) == {"count": 20, "median": 10.5, "p95": 19.0, "max": 20.0}
    assert script.summarize_latencies([3.0, 1.0, 2.0])["p95"] == 3.0


def test_verified_draft_rate_handles_a_zero_denominator() -> None:
    script = _script()

    assert script.verified_draft_rate({}) is None
    assert script.verified_draft_rate({"local_used": 0}) is None
    assert script.verified_draft_rate({"local_used": 0, "timeout": 2}) == 0.0
    assert script.verified_draft_rate({"local_used": 3, "timeout": 1}) == 0.75


def test_changed_case_ids_report_only_changed_flags() -> None:
    script = _script()
    base = [
        {"id": "a", "actual_status": "answered", "source_match": True, "response_sha256": "1"},
        {"id": "b", "actual_status": "answered", "source_match": True, "response_sha256": "2"},
    ]
    other = [
        {"id": "a", "actual_status": "answered", "source_match": True, "response_sha256": "1"},
        {"id": "b", "actual_status": "abstained", "source_match": False, "response_sha256": "3"},
    ]

    assert script.changed_case_ids(base, other) == {"b": ["actual_status", "response_sha256", "source_match"]}
    assert script.changed_case_ids(base, base) == {}


def test_budget_check_is_inclusive_and_ignores_missing_samples() -> None:
    script = _script()

    assert script.budget_check({"ps": MEMORY_BUDGET_BYTES, "rss": None}) is True
    assert script.budget_check({"ps": MEMORY_BUDGET_BYTES + 1, "rss": 1}) is False
    assert script.budget_check({}) is True


def test_ollama_rss_counts_the_app_server_and_model_runner() -> None:
    script = _script()
    output = (
        "  83040 /Applications/Ollama.app/Contents/MacOS/Ollama\n"
        "  44512 /Applications/Ollama.app/Contents/Resources/ollama\n"
        "16364336 /Applications/Ollama.app/Contents/Resources/llama-server\n"
        "    100 /usr/local/bin/ollama\n"
        "   9999 /usr/bin/python3\n"
        "  12345 /opt/other/llama-server\n"
    )

    class Completed:
        stdout = output

    assert script.ollama_rss_bytes(lambda *args, **kwargs: Completed()) == (83040 + 44512 + 16364336 + 100) * 1024

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("ps unavailable")

    assert script.ollama_rss_bytes(fail) is None


def test_script_exits_2_without_a_trace_when_ollama_is_unreachable(capsys: pytest.CaptureFixture) -> None:
    script = _script()
    opener = FakeOpener(tags=urllib.error.URLError(ConnectionRefusedError()))
    opener.replies["/api/version"] = urllib.error.URLError(ConnectionRefusedError())

    code = script.main(
        [
            "--catalog", str(REPO_ROOT / "knowledge" / "source_catalog.json"),
            "--passages", str(REPO_ROOT / "knowledge" / "passages.json"),
            "--cases", str(REPO_ROOT / "knowledge" / "pac_answer_eval.json"),
            "--active-campaign", "2026", "--as-of", "2026-10-31",
            "--record", str(SYNTHETIC_RECORD),
        ],
        opener=opener,
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert captured.err.strip() == "error: ollama_unreachable"
    assert {call["host"] for call in opener.calls} == {"127.0.0.1"}


def test_script_exits_2_on_a_digest_mismatch(capsys: pytest.CaptureFixture) -> None:
    script = _script()
    opener = FakeOpener(tags={"models": [{"name": MODEL, "digest": "f" * 64}]})
    opener.replies["/api/version"] = {"version": "0.0.0-test"}

    code = script.main(
        [
            "--catalog", "unused", "--passages", "unused", "--cases", "unused",
            "--active-campaign", "2026", "--as-of", "2026-10-31", "--record", str(SYNTHETIC_RECORD),
        ],
        opener=opener,
    )

    assert code == 2
    assert capsys.readouterr().err.strip() == "error: model_digest_mismatch"
