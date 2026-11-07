"""Tests for the in-memory answer cache (scenarios 1-8 of ``docs/specs/answer_cache.md``).

Everything is in process: a fake corpus, a fake clock, and a counting fake model transport.
No test reaches a network or reads a secret.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import io
import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
from fastapi.testclient import TestClient

import app.ask_api as ask_api
import app.gemini_generation as gemini_module
import app.generation as generation_module
from app import answer_cache as cache_module
from app.answer_cache import AnswerCache, CacheHit, CacheMiss
from app.ask_api import (
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.gemini_generation import GeminiDraftRequest
from app.main import create_app
from app.pilot_config import load_config
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.readiness import get_configured_campaign
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLARIFICATION = FIXTURES / "clarification"
SYNTHETIC_REVIEW = FIXTURES / "privacy" / "synthetic_approved_review.json"
SYNTHETIC_LIMITS = FIXTURES / "privacy" / "synthetic_gemini_limits.json"
FIXED_DAY = date(2026, 10, 13)
MODEL = "synthetic-model-for-tests"
GEMINI_ENV = {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": MODEL}
QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"
SOLICITUD_FRAGMENT = "se presenta una vez al año"
GENERAL = {"mode": "general", "lands": []}
SELECTED = {"mode": "selected", "lands": [{"id": "opaque-land-7f3a", "municipality": "Martos"}]}
DISTINCTIVE_QUESTION = "Mi finca Zumbacoronel está en Martos. ¿Cuándo se presenta la solicitud anual de ejemplo?"


class FakeClock:
    def monotonic(self) -> float:
        return 1000.0

    def utc_day(self) -> date:
        return FIXED_DAY


class CountingTransport:
    """Answers the solicitud question with a verified draft and counts every call."""

    def __init__(self, reply: Callable[[GeminiDraftRequest], str] | None = None) -> None:
        self.requests: list[GeminiDraftRequest] = []
        self.reply = reply or _solicitud_reply

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        return self.reply(request)


def _solicitud_reply(request: GeminiDraftRequest) -> str:
    payload = json.loads(request.payload_json)
    handle = next(item["passage_id"] for item in payload["passages"] if SOLICITUD_FRAGMENT in item["text"])
    return json.dumps(
        {"status": "answered", "answer": f"Se presenta una vez al año [{handle}]", "sources": [int(handle)]},
        ensure_ascii=False,
    )


class Tick:
    """A fake clock for the cache TTL."""

    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


class Setup:
    """One app plus the mutable pieces a test changes between requests."""

    def __init__(self, application: Any, documents: dict) -> None:
        self.app = application
        self.documents = documents
        self.client = TestClient(application)

    def ask(self, question: str = QUESTION, land_context: dict | None = None, **extra: Any) -> dict:
        response = self.client.post(
            "/ask", json={"question": question, "land_context": land_context or GENERAL, **extra}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def metrics(self) -> str:
        return self.client.get("/metrics").text

    def lookups(self, outcome: str) -> int:
        return _metric(self.metrics(), "answer_cache_lookups_total", outcome=outcome)


def _metric(text: str, name: str, **labels: str) -> int:
    wanted = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
    prefix = f"manijero_{name}{{{wanted}}} "
    for line in text.splitlines():
        if line.startswith(prefix):
            return int(float(line[len(prefix):]))
    raise AssertionError(prefix)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documents(folder: Path = CLARIFICATION, release_id: str | None = None) -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(folder / "catalog.json"),
        passages=load_passage_set(folder / "passages.json"),
        release_id=release_id,
    )


def make(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cache: Any = "default",
    transport: CountingTransport | None = None,
    model: bool = False,
    **options: Any,
) -> Setup:
    """An app over the clarification fixtures; ``model`` turns the synthetic Gemini provider on."""

    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", "2026")
    if model:
        for key, value in GEMINI_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(gemini_module, "load_review_record", lambda: _json(SYNTHETIC_REVIEW))
        monkeypatch.setattr(gemini_module, "load_gemini_limits", lambda: _json(SYNTHETIC_LIMITS))
    state: dict[str, Any] = {"documents": _documents(), "campaign": "2026"}
    application = create_app(
        load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}),
        retention_store=None,
        generation_transport=transport if model else None,
        generation_clock=FakeClock(),
        answer_cache=AnswerCache() if cache == "default" else cache,
        **options,
    )
    application.dependency_overrides[get_corpus_documents] = lambda: state["documents"]
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: state["campaign"]
    application.dependency_overrides[get_configured_campaign] = lambda: state["campaign"]
    return Setup(application, state)


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


class CountingExtractive:
    """Counts extractive drafts; used to prove a hit skips the generator."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls = 0
        original = generation_module.ExtractiveGroundingGenerator.generate
        counter = self

        def counted(self: Any, *args: Any, **kwargs: Any) -> Any:
            counter.calls += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(generation_module.ExtractiveGroundingGenerator, "generate", counted)


# --- 1. a repeat is served from the cache -------------------------------------------------------


def test_normalized_repeat_hits_without_calling_the_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = CountingTransport()
    setup = make(monkeypatch, transport=transport, model=True)

    first = setup.ask()
    variants = [
        QUESTION.upper(),
        "  ¿Cuándo   se presenta\tla solicitud anual de ejemplo?  ",
        "¿Cuando se presenta la solicitud anual de ejemplo?",
    ]
    repeats = [setup.ask(variant) for variant in variants]

    assert first["status"] == "answered"
    assert all(json.dumps(repeat, sort_keys=True) == json.dumps(first, sort_keys=True) for repeat in repeats)
    assert len(transport.requests) == 1
    page = setup.metrics()
    assert _metric(page, "answer_cache_lookups_total", outcome="hit") == 3
    assert _metric(page, "answer_cache_lookups_total", outcome="miss") == 1
    assert _metric(page, "answers_total", status="answered") == 4


def test_a_cached_abstention_is_a_hit_too(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = make(monkeypatch)

    first = setup.ask("zzzz qqqq")
    second = setup.ask("ZZZZ   QQQQ")

    assert first["status"] == "abstained" and second == first
    page = setup.metrics()
    assert _metric(page, "answer_cache_lookups_total", outcome="hit") == 1
    assert _metric(page, "answers_total", status="abstained") == 2
    assert _metric(page, "abstentions_total", reason="no_evidence") == 2


def test_extractive_repeat_does_not_draft_again(monkeypatch: pytest.MonkeyPatch) -> None:
    extractive = CountingExtractive(monkeypatch)
    setup = make(monkeypatch)

    first = setup.ask()
    second = setup.ask()

    assert second == first and extractive.calls == 1


# --- 2. anything else in the key misses --------------------------------------------------------


def test_punctuation_wording_and_land_context_changes_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = make(monkeypatch)
    setup.ask(QUESTION, SELECTED)
    baseline_misses = setup.lookups("miss")

    other_land_id = {"mode": "selected", "lands": [{"id": "opaque-other", "municipality": "Martos"}]}
    other_attribute = {"mode": "selected", "lands": [{"id": "opaque-land-7f3a", "municipality": "Jaén"}]}
    other_mode = {"mode": "all_active", "lands": SELECTED["lands"]}
    changes = [
        (QUESTION.replace("?", ""), SELECTED),
        ("¿Cuándo se presenta la solicitud anual?", SELECTED),
        (QUESTION, other_land_id),
        (QUESTION, other_attribute),
        (QUESTION, other_mode),
        (QUESTION, GENERAL),
    ]
    for question, lands in changes:
        setup.ask(question, lands)

    assert setup.lookups("hit") == 0
    assert setup.lookups("miss") == baseline_misses + len(changes)


def test_release_corpus_campaign_model_or_retrieval_mode_change_misses_and_flushes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    setup.ask()
    setup.ask("zzzz qqqq")
    assert len(cache) == 2

    setup.documents["documents"] = _documents(release_id="0123456789abcdef")
    setup.ask()
    assert (setup.lookups("hit"), len(cache)) == (0, 1)  # a release change emptied the cache

    setup.ask()
    assert setup.lookups("hit") == 1
    setup.documents["documents"] = _documents(release_id="fedcba9876543210")
    setup.ask()
    assert setup.lookups("hit") == 1 and len(cache) == 1

    folder = tmp_path / "edited"
    folder.mkdir()
    (folder / "catalog.json").write_text((CLARIFICATION / "catalog.json").read_text(encoding="utf-8"), encoding="utf-8")
    passages = _json(CLARIFICATION / "passages.json")
    passages["passages"][0]["text"] = passages["passages"][0]["text"] + " Añadido."
    (folder / "passages.json").write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")
    setup.documents["documents"] = _documents(folder, release_id="fedcba9876543210")
    setup.ask()
    assert setup.lookups("hit") == 1 and len(cache) == 1  # same release id, different admitted passages

    setup.ask()
    assert setup.lookups("hit") == 2
    setup.documents["campaign"] = "2026"  # unchanged campaign keeps the entry
    setup.ask()
    assert setup.lookups("hit") == 3


def test_model_and_retrieval_mode_identity_flush_the_whole_cache() -> None:
    cache = AnswerCache()
    knowledge = cache_module.knowledge_identity(None, "f" * 64, "2026")
    extractive = cache_module.model_identity("extractive", "bm25", 5, 2)

    cache.sync_identity(knowledge, extractive)
    cache._put("a" * 64, cache_module._Entry(stored_at=0.0, response={}, status="abstained", reason="no_evidence"))
    cache.sync_identity(knowledge, extractive)
    assert len(cache) == 1
    for changed in (
        cache_module.model_identity("local:tag@digest", "bm25", 5, 2),
        cache_module.model_identity("local:tag@digest", "hybrid", 5, 2),
    ):
        cache._put("a" * 64, cache_module._Entry(stored_at=0.0, response={}, status="abstained", reason="no_evidence"))
        cache.sync_identity(knowledge, changed)
        assert len(cache) == 0
    cache._put("a" * 64, cache_module._Entry(stored_at=0.0, response={}, status="abstained", reason="no_evidence"))
    cache.sync_identity(cache_module.knowledge_identity(None, "f" * 64, "2027"), changed)
    assert len(cache) == 0


def test_key_changes_with_every_part() -> None:
    lands = {"mode": "general", "lands": []}
    base = cache_module.cache_key("¿Hola?", lands, "k", "m")

    assert cache_module.cache_key("¡HOLA?", lands, "k", "m") != base  # punctuation counts
    assert cache_module.cache_key("¿hola?", lands, "k", "m") == base
    assert cache_module.cache_key("¿Hola?", {"mode": "selected", "lands": []}, "k", "m") != base
    assert cache_module.cache_key("¿Hola?", lands, "k2", "m") != base
    assert cache_module.cache_key("¿Hola?", lands, "k", "m2") != base


def test_model_version_is_pinned_per_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini = make(monkeypatch, transport=CountingTransport(), model=True).app.state.generation_provider
    assert gemini.model_version == f"gemini:{MODEL}"
    assert gemini_module.ProviderResolution("extractive").model_version == "extractive"


def test_a_different_model_does_not_share_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    extractive_app = make(monkeypatch, cache=cache)
    extractive_app.ask()
    transport = CountingTransport()
    model_app = make(monkeypatch, cache=cache, transport=transport, model=True)

    model_app.ask()
    model_app.ask()

    assert len(transport.requests) == 1  # the extractive entry was not served to the model app


# --- 3. entries expire after 24 hours --------------------------------------------------------


def test_entry_hits_just_before_and_expires_at_24_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    tick = Tick()
    extractive = CountingExtractive(monkeypatch)
    setup = make(monkeypatch, cache=AnswerCache(clock=tick))

    first = setup.ask()
    tick.now += 86_399
    assert setup.ask() == first
    assert (setup.lookups("hit"), extractive.calls) == (1, 1)

    tick.now += 1  # exactly 24 hours after storing
    assert setup.ask() == first
    assert setup.lookups("expired") == 1 and extractive.calls == 2

    tick.now += 86_399  # the replacement is fresh, measured from its own store time
    setup.ask()
    assert setup.lookups("hit") == 2


# --- 4. transient failures are never cached --------------------------------------------------


@pytest.mark.parametrize("outcome", [value for value in gemini_module.OUTCOMES if value != gemini_module.OUTCOME_USED])
def test_transient_outcomes_are_not_stored(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    calls: list[str] = []

    def failing(self: Any, question: str, candidates: Any) -> Any:
        calls.append(outcome)
        return outcome, None

    monkeypatch.setattr(gemini_module.GatedGeminiGenerator, "_gemini_draft", failing)
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache, transport=CountingTransport(), model=True)

    first = setup.ask()
    second = setup.ask()

    assert first["status"] == "answered" and second == first  # the extractive fallback answered
    assert len(cache) == 0 and len(calls) == 2
    assert setup.lookups("hit") == 0


def test_generation_error_and_503_are_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    def raising(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(generation_module.ExtractiveGroundingGenerator, "generate", raising)
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)

    first = setup.ask()
    assert first["status"] == "abstained" and len(cache) == 0
    setup.ask()
    assert setup.lookups("hit") == 0

    setup.documents["documents"] = CorpusDocuments(catalog=None, passages=None, load_error=True)
    response = setup.client.post("/ask", json={"question": QUESTION, "land_context": GENERAL})
    assert response.status_code == 503 and len(cache) == 0


def test_model_used_and_extractive_results_are_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache, transport=CountingTransport(), model=True)

    setup.ask()
    assert len(cache) == 1

    plain = AnswerCache()
    make(monkeypatch, cache=plain).ask()
    assert len(plain) == 1


# --- 5. a cached answer that no longer verifies is discarded whole ------------------------------


def test_failed_reverification_discards_the_entry_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    first = setup.ask()
    assert len(cache) == 1

    real = cache_module.verify_draft
    monkeypatch.setattr(
        cache_module,
        "verify_draft",
        lambda draft, candidates: replace(real(draft, candidates), ok=False),
    )
    second = setup.ask()

    assert second == first  # the fresh pipeline result, not a partial cached one
    assert setup.lookups("discarded") == 1 and setup.lookups("hit") == 0
    assert len(cache) == 1  # replaced by the fresh result


def test_a_tampered_cached_answer_is_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    first = setup.ask()
    key, entry = next(iter(cache._entries.items()))
    cache._entries[key] = replace(entry, response=dict(entry.response, sources=[]))

    assert setup.ask() == first
    assert setup.lookups("discarded") == 1


def test_malformed_cached_abstention_is_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    first = setup.ask("zzzz qqqq")
    key, entry = next(iter(cache._entries.items()))
    cache._entries[key] = replace(entry, response=dict(entry.response, answer="Texto inventado."))

    assert setup.ask("zzzz qqqq") == first
    assert setup.lookups("discarded") == 1 and setup.lookups("hit") == 0


def test_a_generation_error_entry_is_never_served() -> None:
    entry = cache_module._Entry(
        stored_at=0.0, response={}, status="abstained", reason="generation_error"
    )
    assert cache_module._recheck(entry) is None


# --- 6. clarification and pre-checks run on every request -----------------------------------


def test_clarification_and_year_precheck_run_before_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    question = "¿Puedo regar mi olivar de ejemplo?"
    one_land = {"mode": "all_active", "lands": [{"id": "opaque-one", "water_regime": "irrigated"}]}
    two_lands = {
        "mode": "all_active",
        "lands": [{"id": "opaque-one", "water_regime": "irrigated"}, {"id": "opaque-two", "water_regime": "dryland"}],
    }

    answered = setup.ask(question, one_land)
    assert answered["status"] == "answered"
    clarified = setup.ask(question, two_lands)
    assert clarified["status"] == "needs_land_clarification"
    assert setup.lookups("hit") == 0 and len(cache) == 1  # a clarification is never stored

    wrong_year = setup.ask("¿Qué plazo hay en 1999?")
    assert wrong_year["status"] == "abstained"
    assert setup.lookups("miss") == 1  # the pre-check never looked anything up

    setup.documents["documents"] = CorpusDocuments(catalog=None, passages=None, load_error=True)
    assert setup.client.post("/ask", json={"question": question, "land_context": one_land}).status_code == 503


# --- 7. the setting turns it off ---------------------------------------------------------------


@pytest.mark.parametrize("profile", ["development", "pilot"])
@pytest.mark.parametrize(
    "value, on, reason",
    [(None, True, None), ("", True, None), ("on", True, None), ("off", False, None),
     ("ON", False, "value_invalid"), ("yes", False, "value_invalid")],
)
def test_setting_on_off_and_invalid_values(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, profile: str, value: str | None, on: bool, reason: str | None
) -> None:
    monkeypatch.delenv("MANIJERO_ANSWER_CACHE", raising=False)
    if value is not None:
        monkeypatch.setenv("MANIJERO_ANSWER_CACHE", value)
    monkeypatch.setenv("MANIJERO_DEPLOYMENT_PROFILE", profile)
    config = load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}) if profile == "development" else None
    if config is None:
        from app.pilot_config import PilotConfig

        config = PilotConfig(profile="pilot", active_campaign="2026", max_request_bytes=65536)

    application = create_app(config, retention_store=None)

    assert (application.state.answer_cache is not None) is on
    records = [json.loads(line) for line in captured_log.getvalue().splitlines() if '"answer_cache"' in line]
    assert len(records) == 1 and records[0]["state"] == ("on" if on else "off")
    assert records[0].get("reason") == reason


def test_off_path_uses_answer_with_clarification_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = ask_api.answer_with_clarification

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append("answer_with_clarification")
        return real(*args, **kwargs)

    monkeypatch.setattr(ask_api, "answer_with_clarification", spy)
    setup = make(monkeypatch, cache=None)

    first = setup.ask()
    second = setup.ask()

    assert first == second and len(calls) == 2
    page = setup.metrics()
    assert all(_metric(page, "answer_cache_lookups_total", outcome=o) == 0 for o in ("hit", "miss", "expired", "discarded"))
    assert _metric(page, "answers_total", status="answered") == 2


# --- 8. nothing personal leaves memory ---------------------------------------------------------


def test_question_and_land_values_never_reach_logs_metrics_or_disk(
    monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    cache = AnswerCache()
    land = {"mode": "selected", "lands": [{"id": "opaque-land-Zumba9", "municipality": "Zumbacoronel"}]}
    setup = make(monkeypatch, cache=cache, transport=CountingTransport(), model=True)

    for _ in range(3):  # a miss and two hits
        setup.ask(DISTINCTIVE_QUESTION, land)
    setup.ask("zzzz Zumbacoronel qqqq", land)  # a stored abstention

    held = repr(cache._entries) + repr(vars(cache))
    sensitive = ("Zumbacoronel", "Zumba9", "Martos")
    for value in sensitive:
        assert value not in captured_log.getvalue()
        assert value not in setup.metrics()
        assert value not in held
    assert all(len(key) == 64 and set(key) <= set("0123456789abcdef") for key in cache._entries)
    written = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert written == []  # nothing was written under the temporary home or working folder


def test_new_app_starts_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    first = make(monkeypatch)
    first.ask()
    assert len(first.app.state.answer_cache) == 1

    second = make(monkeypatch)

    assert second.app.state.answer_cache is not first.app.state.answer_cache
    assert len(second.app.state.answer_cache) == 0


def test_hit_omits_inspection_and_keeps_retention_and_trace_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    retained: list[dict] = []
    outcomes: list[dict] = []
    real_note = ask_api.answer_trace.note_outcome

    def retain(store: Any, **kwargs: Any) -> str:
        retained.append(kwargs["response"])
        return "skipped"

    def note(**kwargs: Any) -> None:
        outcomes.append(kwargs)
        real_note(**kwargs)

    monkeypatch.setattr(ask_api, "retain_if_opted_in", retain)
    monkeypatch.setattr(ask_api.answer_trace, "note_outcome", note)
    setup = make(monkeypatch, answer_inspection=True)

    first = setup.ask(retain_for_improvement=True)
    second = setup.ask(retain_for_improvement=True)

    assert "inspection" in first and "inspection" not in second
    assert {key: value for key, value in first.items() if key != "inspection"} == second
    assert retained == [second, second]
    assert outcomes[0] == outcomes[1] and outcomes[0]["cited_passage_ids"]


def test_hits_are_deep_copies(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)
    setup.ask()
    key = next(iter(cache._entries))

    hit = cache.lookup(key)
    assert isinstance(hit, CacheHit)
    hit.response["sources"].clear()
    hit.response["answer"] = "mutated"

    again = cache.lookup(key)
    assert isinstance(again, CacheHit) and again.response["sources"] and again.response["answer"] != "mutated"


# --- bounds ------------------------------------------------------------------------------------


def test_eviction_keeps_at_most_max_entries() -> None:
    cache = AnswerCache(max_entries=3)
    for index in range(5):
        cache._put(f"k{index}", cache_module._Entry(stored_at=0.0, response={}, status="abstained", reason="no_evidence"))

    assert len(cache) == 3
    assert list(cache._entries) == ["k2", "k3", "k4"]  # the oldest went first
    assert isinstance(cache.lookup("k0"), CacheMiss)


def test_default_bounds_are_the_owner_decisions() -> None:
    cache = AnswerCache()

    assert cache._ttl == 86_400 and cache._max == 1_000


def test_outcome_hook_is_request_scoped_and_never_raises() -> None:
    cache_module.note_generation_outcome("timeout")  # no capture open: ignored
    with cache_module.capture_generation_outcomes() as outcomes:
        cache_module.note_generation_outcome("gemini_used")
        cache_module.note_generation_outcome(None)  # type: ignore[arg-type]
    assert outcomes == ["gemini_used", "None"]
    assert cache_module.outcomes_cacheable([], None)
    assert cache_module.outcomes_cacheable(["gemini_used"], "gemini_used")
    assert not cache_module.outcomes_cacheable(["gemini_used", "timeout"], "gemini_used")
    assert not cache_module.outcomes_cacheable(["gemini_used"], None)
    with cache_module.capture_generation_outcomes() as degraded:
        cache_module.note_degraded_retrieval()  # a vector fallback result is not stored
    assert not cache_module.outcomes_cacheable(degraded, None)


def test_a_degraded_retrieval_result_is_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    original = generation_module.ExtractiveGroundingGenerator.generate

    def degraded(self: Any, *args: Any, **kwargs: Any) -> Any:
        cache_module.note_degraded_retrieval()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(generation_module.ExtractiveGroundingGenerator, "generate", degraded)
    cache = AnswerCache()
    setup = make(monkeypatch, cache=cache)

    setup.ask()

    assert len(cache) == 0
