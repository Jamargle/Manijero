"""Tests for the privacy-safe, off-by-default answer pipeline trace.

Everything runs on the synthetic clarification fixtures with fake tokens in temporary
folders. No test writes into the repository ``build`` folder.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import stat
import sys
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.answer_trace as answer_trace  # noqa: E402
from app.answer_trace import (  # noqa: E402
    DEFAULT_FOLDER,
    METADATA_KEYS,
    AnswerTrace,
    TraceCollector,
    TraceWriter,
    build_document,
    key_paths,
    load_answer_trace,
    parse_setting,
    text_allowed,
)
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_backend,
)
from app.generation import DraftAnswer  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pilot_config import ClientPolicy, PilotConfig, load_config  # noqa: E402
from app.pilot_logging import LOGGER_NAME  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402
from test_gemini_generation import FakeTransport, _draft, _generator  # noqa: E402
from test_hybrid_retrieval import (  # noqa: E402
    FailingEmbedder,
    HybridBackend,
    clarification_retriever,
    components_for,
)

CLARIFICATION = Path(__file__).resolve().parent / "fixtures" / "clarification"
AS_OF = date(2026, 10, 13)
NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
QUESTION = "¿Cuándo se presenta la solicitud anual de ejemplo?"
MARKER = "zzmarcadorzz"
TOKEN = "fake-pilot-token-for-tests"
LANDS = {
    "mode": "selected",
    "lands": [
        {
            "id": "opaque-land-7f3a",
            "municipality": "Martos",
            "water_regime": "irrigated",
            "production_method": "organic",
        }
    ],
}
GENERAL = {"mode": "general", "lands": []}
CLARIFY_LANDS = {
    "mode": "all_active",
    "lands": [
        {"id": "opaque-one", "water_regime": "irrigated"},
        {"id": "opaque-two", "water_regime": "dryland"},
    ],
}
CLARIFY_QUESTION = "¿Puedo regar mi olivar de ejemplo?"


class FixedClock:
    def __init__(self, moment: datetime = NOW) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


def documents() -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(CLARIFICATION / "catalog.json"),
        passages=load_passage_set(CLARIFICATION / "passages.json"),
    )


def pilot_config() -> PilotConfig:
    digest = hashlib.sha256(TOKEN.encode()).hexdigest()
    return PilotConfig(
        profile="pilot",
        active_campaign="2026",
        max_request_bytes=65536,
        clients=(ClientPolicy(client_id="client-secret-id", token_sha256=digest, requests_per_minute=600),),
    )


def trace_for(
    tmp_path: Path, *, profile: str = "development", enabled: bool = True, clock: Optional[FixedClock] = None
) -> AnswerTrace:
    folder = tmp_path / "traces"
    return load_answer_trace(
        {"MANIJERO_ANSWER_TRACE": "on" if enabled else "off", "MANIJERO_DEPLOYMENT_PROFILE": profile},
        profile,
        folder=folder,
        clock=clock or FixedClock(),
    )


def make_app(trace: AnswerTrace, *, profile: str = "development", docs: Any = documents):
    config = pilot_config() if profile == "pilot" else load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"})
    application = create_app(config, retention_store=None, answer_trace=trace)
    application.dependency_overrides[get_corpus_documents] = docs
    application.dependency_overrides[get_as_of_date] = lambda: AS_OF
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    return application


def ask(application, question: str = QUESTION, land_context: Any = GENERAL, pilot: bool = False, **extra: Any):
    headers = {"Authorization": "Bearer " + TOKEN} if pilot else {}
    body = {"question": question, "land_context": land_context, **extra}
    with TestClient(application) as client:
        return client.post("/ask", json=body, headers=headers)


def trace_files(trace: AnswerTrace) -> list[Path]:
    folder = trace.writer.folder
    return sorted(folder.glob("*")) if folder.exists() else []


def load(trace: AnswerTrace) -> dict:
    files = [p for p in trace_files(trace) if p.suffix == ".json"]
    assert len(files) == 1, files
    return json.loads(files[0].read_text(encoding="utf-8"))


@pytest.fixture
def operational_records():
    logger = logging.getLogger(LOGGER_NAME)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def records() -> list[dict]:
        return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


# --- setting and profile -----------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "off"])
def test_setting_unset_empty_off_disables_and_creates_no_folder(tmp_path: Path, value: Optional[str]) -> None:
    environ = {} if value is None else {"MANIJERO_ANSWER_TRACE": value}
    trace = load_answer_trace(environ, "development", folder=tmp_path / "traces")
    response = ask(make_app(trace))

    assert trace.enabled is False and trace.reason is None
    assert response.status_code == 200
    assert not (tmp_path / "traces").exists()


@pytest.mark.parametrize("stated", [None, "", "  "])
def test_an_unset_profile_never_records_text_even_though_it_resolves_to_development(
    tmp_path: Path, stated: Optional[str]
) -> None:
    environ = {"MANIJERO_ANSWER_TRACE": "on"}
    if stated is not None:
        environ["MANIJERO_DEPLOYMENT_PROFILE"] = stated
    trace = load_answer_trace(environ, "development", folder=tmp_path / "traces")

    assert trace.enabled is True and trace.text_included is False


def test_a_stated_development_profile_records_text(tmp_path: Path) -> None:
    environ = {"MANIJERO_ANSWER_TRACE": "on", "MANIJERO_DEPLOYMENT_PROFILE": "development"}
    trace = load_answer_trace(environ, "development", folder=tmp_path / "traces")

    assert trace.text_included is True


@pytest.mark.parametrize("value", ["On", "1", "yes", " on", "ON", "true"])
def test_invalid_setting_values_stay_off_and_log_value_invalid(
    tmp_path: Path, value: str, operational_records
) -> None:
    trace = load_answer_trace({"MANIJERO_ANSWER_TRACE": value}, "development", folder=tmp_path / "traces")
    ask(make_app(trace))

    assert trace.enabled is False
    assert not (tmp_path / "traces").exists()
    logged = [r for r in operational_records() if r["event"] == "answer_trace"]
    assert logged[-1]["state"] == "off" and logged[-1]["reason"] == "value_invalid"
    assert parse_setting(value) == (False, "value_invalid")


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("development", True),
        ("pilot", False),
        ("qa", False),
        ("prod", False),
        ("local", False),
        ("Development", False),
        (" development", False),
        ("", False),
    ],
)
def test_text_allowed_only_for_exact_development(profile: str, expected: bool) -> None:
    assert text_allowed(profile, {"MANIJERO_DEPLOYMENT_PROFILE": profile}) is expected


# --- document content --------------------------------------------------------------------


def test_local_profile_trace_has_text_and_all_stages(tmp_path: Path) -> None:
    trace = trace_for(tmp_path)
    response = ask(make_app(trace))
    document = load(trace)

    assert response.json()["status"] == "answered"
    assert document["schema"] == "answer-trace-v1"
    assert document["profile"] == "development" and document["text_included"] is True
    assert document["created_at"] == "2026-11-02T12:00:00Z"
    assert len(document["trace_id"]) == 32
    assert document["question"] == QUESTION
    assert document["answer"] == response.json()["answer"]
    retrieval = document["retrieval"]
    assert retrieval["mode"] == "bm25" and retrieval["k"] == 5 and retrieval["search_calls"] >= 1
    assert retrieval["lexical"][0]["rank"] == 1 and retrieval["lexical"][0]["score"] > 0
    assert retrieval["vector"] is None
    assert retrieval["candidates"] and set(retrieval["candidates"][0]) == {"passage_id", "source_id", "score", "rank"}
    drafting = document["drafting"]
    assert drafting["provider"] == "extractive" and drafting["outcome"] == "used"
    assert drafting["status"] == "answered" and drafting["draft_text"] and drafting["draft_truncated"] is False
    assert drafting["cited_markers"]
    assert document["verification"]["ok"] is True and document["verification"]["claims"][0]["index"] == 1
    outcome = document["outcome"]
    assert outcome["status"] == "answered" and outcome["cited_passage_ids"]
    assert outcome["land_scope"] == "general" and outcome["land_choice_count"] == 0
    assert document["total_ms"] >= 0
    assert key_paths(document) - answer_trace.TEXT_KEYS <= METADATA_KEYS


def test_trace_written_for_abstained_clarification_year_mismatch_and_503(tmp_path: Path) -> None:
    cases = [
        ("abstained", "¿Qué ayuda de pesca me corresponde?", GENERAL, documents),
        ("needs_land_clarification", CLARIFY_QUESTION, CLARIFY_LANDS, documents),
        ("abstained", "¿Cuándo se presenta la solicitud anual de 2031?", GENERAL, documents),
    ]
    for index, (status, question, lands, docs) in enumerate(cases):
        trace = trace_for(tmp_path / str(index))
        response = ask(make_app(trace, docs=docs), question, lands)
        document = load(trace)
        assert response.json()["status"] == status == document["outcome"]["status"]
        if index == 1:
            assert document["outcome"]["land_choice_count"] == 2
        if index == 2:
            assert document["retrieval"] is None and document["drafting"] is None
            assert document["verification"] is None
            assert document["outcome"]["abstention_reason"] == "no_evidence"
        if index == 0:
            assert document["drafting"] is None and document["outcome"]["abstention_reason"]

    unavailable = trace_for(tmp_path / "503")
    response = ask(
        make_app(unavailable, docs=lambda: CorpusDocuments(catalog=None, passages=None, load_error=True))
    )
    document = load(unavailable)
    assert response.status_code == 503
    assert document["outcome"]["status"] == "unavailable"
    assert document["retrieval"] is None and document["drafting"] is None
    assert document["answer"] is None


def test_pilot_profile_trace_matches_metadata_allowlist_and_omits_marker_bytes(tmp_path: Path) -> None:
    trace = trace_for(tmp_path, profile="pilot")
    response = ask(make_app(trace, profile="pilot"), QUESTION + " " + MARKER, pilot=True)
    path = next(p for p in trace_files(trace) if p.suffix == ".json")
    raw = path.read_bytes()
    document = json.loads(raw)

    assert response.status_code == 200
    assert document["text_included"] is False and document["profile"] == "pilot"
    assert MARKER.encode() not in raw
    assert response.json()["answer"].encode() not in raw
    assert not key_paths(document) & answer_trace.TEXT_KEYS
    assert key_paths(document) <= METADATA_KEYS
    for banned in ("question", "answer", "draft_text"):
        assert banned not in raw.decode().replace('"', " ").split()


def test_complete_metadata_document_keys_equal_the_published_allowlist() -> None:
    collector = TraceCollector()
    collector.mode, collector.k, collector.search_calls = "hybrid", 5, 1
    collector.lexical = [("p1", 1.0)]
    collector.vector = {"used": True, "fallback_code": None, "matches": [{"passage_id": "p1", "similarity": 0.5}]}
    collector.candidates = [{"passage_id": "p1", "source_id": "s", "score": 1.0, "rank": 1}]
    collector.drafting = {"provider": "gemini", "outcome": "gemini_used", "status": "answered",
                          "cited_markers": [1], "duration_ms": 1, "_text": "texto"}
    collector.verification = {"ok": False, "issues": ["x"], "duration_ms": 1,
                              "claims": [{"index": 1, "markers": [1], "ok": False, "issues": ["x"]}]}
    collector.outcome = {"abstention_reason": None, "generation_reason": None, "cited_passage_ids": ["p1"]}
    kwargs = dict(profile="pilot", question="q", answer="a", status="answered", land_scope="general",
                  land_choice_count=0, moment=NOW, trace_id="a" * 32)

    metadata = build_document(collector, text_included=False, **kwargs)
    local = build_document(collector, text_included=True, **kwargs)

    assert key_paths(metadata) == METADATA_KEYS
    assert key_paths(local) == METADATA_KEYS | answer_trace.TEXT_KEYS


def test_no_land_values_client_id_token_or_retain_flag_in_any_profile(tmp_path: Path) -> None:
    forbidden = ("opaque-land-7f3a", "Martos", "irrigated", "organic", "client-secret-id", TOKEN,
                 "retain_for_improvement", "testclient", "127.0.0.1")
    for profile in ("development", "pilot"):
        trace = trace_for(tmp_path / profile, profile=profile)
        response = ask(
            make_app(trace, profile=profile), QUESTION, LANDS, pilot=profile == "pilot",
            retain_for_improvement=True,
        )
        assert response.status_code == 200
        text = next(p for p in trace_files(trace) if p.suffix == ".json").read_text(encoding="utf-8")
        for value in forbidden:
            assert value not in text, (profile, value)
        assert '"detail"' not in text and "excerpt" not in text


def test_hybrid_trace_records_vector_matches_and_fallback_code(tmp_path: Path) -> None:
    retriever = clarification_retriever()
    good = trace_for(tmp_path / "good")
    application = make_app(good)
    hybrid = HybridBackend(lambda: components_for(retriever))
    application.dependency_overrides[get_retrieval_backend] = lambda: hybrid
    ask(application)
    document = load(good)["retrieval"]
    assert document["mode"] == "hybrid"
    assert document["vector"]["used"] is True and document["vector"]["fallback_code"] is None
    assert document["vector"]["matches"] and set(document["vector"]["matches"][0]) == {"passage_id", "similarity"}

    failing = trace_for(tmp_path / "failing")
    application = make_app(failing)
    broken = HybridBackend(lambda: components_for(retriever, embedder=FailingEmbedder()))
    application.dependency_overrides[get_retrieval_backend] = lambda: broken
    ask(application)
    vector = load(failing)["retrieval"]["vector"]
    assert vector["used"] is False and vector["fallback_code"] and vector["matches"] == []


class _Resolution:
    model_version = "test-double"
    used_outcome = None

    def __init__(self, generator: Any) -> None:
        self._generator = generator

    def generator_for(self, land_context: Any, *, max_claims: int) -> Any:
        return self._generator


class _BadDraftGenerator:
    def generate(self, question: str, numbered_candidates: Any, *, as_of: Any = None) -> DraftAnswer:
        return DraftAnswer(status="answered", answer="Tienes derecho a la ayuda [1]. Sin cita.", source_markers=(1,))


def test_model_draft_outcome_and_rejected_verification_codes_recorded(tmp_path: Path) -> None:
    gated = trace_for(tmp_path / "gated")
    application = make_app(gated)
    reply = _draft("Tienes derecho a la solicitud anual [1].", [1])
    application.state.generation_provider = _Resolution(_generator(FakeTransport(reply)))
    ask(application)
    drafting = load(gated)["drafting"]
    assert drafting["provider"] == "gemini" and drafting["outcome"] == "verifier_rejected"

    rejected = trace_for(tmp_path / "rejected")
    application = make_app(rejected)
    application.state.generation_provider = _Resolution(_BadDraftGenerator())
    response = ask(application)
    document = load(rejected)
    assert response.json()["status"] == "abstained"
    assert document["verification"]["ok"] is False
    assert {"eligibility_claim", "uncited_sentence"} <= set(document["verification"]["issues"])
    assert document["verification"]["claims"][0]["issues"]
    assert document["drafting"]["draft_text"].startswith("Tienes derecho")
    assert document["outcome"]["generation_reason"] or document["outcome"]["abstention_reason"]


# --- never changes or breaks an answer ---------------------------------------------------


def _unavailable() -> CorpusDocuments:
    return CorpusDocuments(catalog=None, passages=None, load_error=True)


CASES = [
    (QUESTION, GENERAL, documents),
    ("¿Qué ayuda de pesca me corresponde?", GENERAL, documents),
    ("¿Cuándo se presenta la solicitud anual de 2031?", GENERAL, documents),
    (CLARIFY_QUESTION, CLARIFY_LANDS, documents),
    (QUESTION, GENERAL, _unavailable),
]


@pytest.mark.parametrize("question,lands,docs", CASES)
def test_responses_identical_with_trace_on_and_off(tmp_path: Path, question: str, lands: Any, docs: Any) -> None:
    off = ask(make_app(trace_for(tmp_path / "off", enabled=False), docs=docs), question, lands)
    on = ask(make_app(trace_for(tmp_path / "on"), docs=docs), question, lands)

    assert (off.status_code, off.content) == (on.status_code, on.content)


def test_write_failure_symlink_and_serialize_error_never_change_response_and_leave_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operational_records
) -> None:
    baseline = ask(make_app(trace_for(tmp_path / "base", enabled=False)))

    blocked = trace_for(tmp_path / "blocked")
    blocked.writer.folder.parent.mkdir(parents=True)
    blocked.writer.folder.write_text("not a folder")
    unwritable = ask(make_app(blocked))

    target = tmp_path / "elsewhere"
    target.mkdir()
    linked = trace_for(tmp_path / "linked")
    linked.writer.folder.parent.mkdir(parents=True)
    linked.writer.folder.symlink_to(target, target_is_directory=True)
    symlinked = ask(make_app(linked))

    broken = trace_for(tmp_path / "broken")
    monkeypatch.setattr(
        answer_trace, "build_document", lambda *a, **k: {"trace_id": "a" * 32, "bad": float("nan")}
    )
    unserializable = ask(make_app(broken))
    monkeypatch.undo()

    for response in (unwritable, symlinked, unserializable):
        assert (response.status_code, response.content) == (baseline.status_code, baseline.content)
    assert list(target.iterdir()) == []
    assert not [p for p in broken.writer.folder.glob("*")] if broken.writer.folder.exists() else True
    reasons = [r["reason"] for r in operational_records() if r["event"] == "answer_trace_skipped"]
    assert reasons == ["write_failed", "folder_symlink", "serialize_failed"]
    assert all(set(r) <= {"event", "time", "reason"} for r in operational_records() if r["event"] == "answer_trace_skipped")


def test_folder_0700_file_0600_name_pattern_and_atomic_replace(tmp_path: Path) -> None:
    trace = trace_for(tmp_path)
    ask(make_app(trace))
    ask(make_app(trace))
    entries = trace_files(trace)

    assert stat.S_IMODE(os.stat(trace.writer.folder).st_mode) == 0o700
    assert len(entries) == 2 and all(p.suffix == ".json" for p in entries)  # no temp files left
    for path in entries:
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert answer_trace._NAME.match(path.name) and path.name.startswith("20261102T120000Z-")


def test_default_folder_is_repo_build_answer_traces() -> None:
    repository = Path(__file__).resolve().parents[2]
    assert DEFAULT_FOLDER == repository / "build" / "answer-traces"
    assert load_answer_trace({}, "development").writer.folder == DEFAULT_FOLDER


# --- seven-day deletion ------------------------------------------------------------------


def _name(moment: datetime, suffix: str = "0") -> str:
    return "{}-{}.json".format(moment.strftime("%Y%m%dT%H%M%SZ"), suffix * 32)


def _seed(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True)
    files = {
        "old": folder / _name(NOW - timedelta(days=7), "a"),
        "older": folder / _name(NOW - timedelta(days=30), "b"),
        "edge": folder / _name(NOW - timedelta(days=7) + timedelta(seconds=1), "c"),
        "young": folder / _name(NOW - timedelta(days=1), "d"),
        "foreign": folder / "notes.json",
        "near": folder / "20200101T000000Z-short.json",
    }
    for path in files.values():
        path.write_text("{}")
    return files


def test_purge_removes_seven_day_old_keeps_younger_ignores_foreign_names(tmp_path: Path) -> None:
    files = _seed(tmp_path / "traces")

    TraceWriter(tmp_path / "traces", FixedClock()).purge()

    assert not files["old"].exists() and not files["older"].exists()
    assert files["edge"].exists() and files["young"].exists()
    assert files["foreign"].exists() and files["near"].exists()


def test_purge_runs_before_each_write(tmp_path: Path) -> None:
    files = _seed(tmp_path / "traces")
    trace = trace_for(tmp_path)

    ask(make_app(trace))

    assert not files["old"].exists() and files["young"].exists()


def test_startup_purges_even_when_tracing_off(tmp_path: Path) -> None:
    files = _seed(tmp_path / "traces")
    trace = trace_for(tmp_path, enabled=False)

    make_app(trace)

    assert not files["old"].exists() and files["young"].exists()


def test_startup_purge_failure_and_missing_folder_never_stop_startup(tmp_path: Path) -> None:
    make_app(trace_for(tmp_path / "missing", enabled=False))
    assert not (tmp_path / "missing" / "traces").exists()

    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "traces").write_text("a file, not a folder")
    make_app(trace_for(plain))  # purge on a non-directory is silently skipped


# --- bounds ------------------------------------------------------------------------------


def test_draft_text_truncated_at_4000_with_flag() -> None:
    collector = TraceCollector()
    collector.mode = "bm25"
    collector.drafting = {"provider": "extractive", "outcome": "used", "_text": "x" * 4001}
    document = build_document(collector, profile="development", text_included=True, question="q", answer="a",
                              status="answered", land_scope="general", land_choice_count=0,
                              moment=NOW, trace_id="a" * 32)

    assert len(document["drafting"]["draft_text"]) == 4000 and document["drafting"]["draft_truncated"] is True


def test_lexical_list_capped_at_20() -> None:
    collector = TraceCollector()
    collector.mode = "bm25"
    collector.lexical = [("p{}".format(n), 1.0) for n in range(50)]
    document = build_document(collector, profile="pilot", text_included=False, question="q", answer=None,
                              status="answered", land_scope="general", land_choice_count=0,
                              moment=NOW, trace_id="a" * 32)

    assert len(document["retrieval"]["lexical"]) == 20


def test_hooks_are_no_ops_without_an_active_collector() -> None:
    assert answer_trace.note_search_begin() is None
    answer_trace.note_lexical([("p", 1.0)])
    answer_trace.note_draft(object(), None)  # a malformed argument is swallowed
    answer_trace.note_outcome(cited_passage_ids=["p"])
