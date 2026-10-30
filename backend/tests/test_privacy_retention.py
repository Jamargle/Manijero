"""Tests for opt-in Q/A retention, redaction, deletion, and the privacy/Gemini review gates.

All text is synthetic. The approved review used here is a clearly labelled test fixture,
never a real review; the committed record stays pending and the gates closed.
"""

from __future__ import annotations

from datetime import date, timedelta
import io
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import app.retention as retention_module
from app.ask_api import CorpusDocuments, get_active_campaign, get_as_of_date, get_corpus_documents
from app.main import create_app
from app.pilot_config import load_config
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.privacy_review import (
    DEFAULT_REVIEW_PATH,
    GEMINI_ALLOWED_DATA,
    decide_generation_provider,
    evaluate_gemini_review,
    evaluate_pilot_review,
    load_review_record,
    minimal_provider_payload,
)
from app.redaction import redact_text
from app.retention import (
    RETENTION_DAYS,
    RetainedRecord,
    RetentionError,
    RetentionStore,
    expiry_for,
    export_records,
    load_retention_store,
    retain_if_opted_in,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CATALOG = FIXTURES / "clarification" / "catalog.json"
PASSAGES = FIXTURES / "clarification" / "passages.json"
SYNTHETIC_APPROVED_REVIEW = FIXTURES / "privacy" / "synthetic_approved_review.json"
FIXED_DAY = date(2026, 10, 13)
PERSONAL_QUESTION = (
    "Me llamo Juan Pérez y mi finca Los Olivos está en Martos, polígono 12 parcela 345. "
    "Mi teléfono es 600 123 456 y mi correo juan.perez@example.com. "
    "¿Cuándo se presenta la solicitud anual de ejemplo?"
)
SINGLE_LAND = {"mode": "all_active", "lands": [{"id": "opaque-land-7f3a", "municipality": "Martos"}]}
FORBIDDEN_IN_RECORD = (
    "Juan",
    "Pérez",
    "Los Olivos",
    "Martos",
    "600 123 456",
    "juan.perez@example.com",
    "345",
    "opaque-land-7f3a",
)


def _owner_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "retention"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    return directory


def _store(tmp_path: Path) -> RetentionStore:
    return RetentionStore.open(_owner_dir(tmp_path) / "qa.sqlite3")


def _rows(store: RetentionStore) -> list[tuple]:
    connection = sqlite3.connect(store.path)
    try:
        return connection.execute("SELECT * FROM retained_qa").fetchall()
    finally:
        connection.close()


def _app(store: RetentionStore | None):
    application = create_app(load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}), retention_store=store)
    application.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=json.loads(CATALOG.read_text(encoding="utf-8")),
        passages=json.loads(PASSAGES.read_text(encoding="utf-8")),
    )
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    return application


def _ask(store: RetentionStore | None, body: dict) -> dict:
    with TestClient(_app(store)) as client:
        response = client.post("/ask", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _body(question: str = PERSONAL_QUESTION, land_context: dict | None = None, **extra) -> dict:
    return {"question": question, "land_context": land_context or SINGLE_LAND, **extra}


@pytest.fixture
def captured_log() -> io.StringIO:
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


# --- Default no retention and explicit opt-in -------------------------------------------


def test_without_opt_in_nothing_is_retained_or_logged(tmp_path: Path, captured_log: io.StringIO) -> None:
    store = _store(tmp_path)

    absent = _ask(store, _body())
    explicit_false = _ask(store, _body(retain_for_improvement=False))

    assert absent["status"] == "answered"
    assert absent == explicit_false
    assert _rows(store) == []
    assert "Juan" not in captured_log.getvalue()
    assert "solicitud anual" not in captured_log.getvalue()


def test_opt_in_retains_only_redacted_question_and_answer(tmp_path: Path, captured_log: io.StringIO) -> None:
    store = _store(tmp_path)

    baseline = _ask(None, _body())
    opted_in = _ask(store, _body(retain_for_improvement=True))

    # Retention never changes the answer.
    assert opted_in == baseline
    rows = _rows(store)
    assert len(rows) == 1
    created_on, expires_on, status, question, answer = rows[0]
    assert created_on == FIXED_DAY.isoformat()
    assert date.fromisoformat(expires_on) - FIXED_DAY < timedelta(days=RETENTION_DAYS)
    assert status == "answered"
    assert "¿Cuándo se presenta la solicitud anual de ejemplo?" in question
    assert answer.strip()
    assert answer == redact_text(
        baseline["answer"], [("opaque-land-7f3a", "[terreno]"), ("Martos", "[municipio]")]
    )
    stored = json.dumps(rows, ensure_ascii=False)
    for forbidden in FORBIDDEN_IN_RECORD:
        assert forbidden not in stored, forbidden
    assert "[nombre]" in question and "[teléfono]" in question and "[correo]" in question
    assert "[municipio]" in question and "[nombre del terreno]" in question
    assert "Juan" not in captured_log.getvalue()


def test_retained_record_has_exactly_the_minimal_columns(tmp_path: Path) -> None:
    store = _store(tmp_path)
    connection = sqlite3.connect(store.path)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(retained_qa)")]
    finally:
        connection.close()

    assert columns == ["created_on", "expires_on", "answer_status", "question_redacted", "answer_redacted"]


def test_opt_in_must_be_a_real_boolean(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with TestClient(_app(store)) as client:
        for value in ("true", 1, None):
            response = client.post("/ask", json=_body(retain_for_improvement=value))
            assert response.status_code == 422
            assert "Juan" not in response.text
    assert _rows(store) == []


def test_opt_in_without_a_configured_store_retains_nothing(tmp_path: Path) -> None:
    assert _ask(None, _body(retain_for_improvement=True)) == _ask(None, _body())
    assert load_retention_store({}) is None


def test_clarification_is_not_retained(tmp_path: Path) -> None:
    store = _store(tmp_path)
    clarification = _ask(
        store,
        _body(
            "¿Puedo regar mi olivar de ejemplo?",
            {
                "mode": "all_active",
                "lands": [
                    {"id": "opaque-one", "water_regime": "irrigated"},
                    {"id": "opaque-two", "water_regime": "dryland"},
                ],
            },
            retain_for_improvement=True,
        ),
    )

    assert clarification["status"] == "needs_land_clarification"
    assert _rows(store) == []


def test_abstention_is_retained_without_land_context(tmp_path: Path) -> None:
    store = _store(tmp_path)
    abstained = _ask(store, _body("¿Qué ayuda me corresponde en 2031 en Martos?", retain_for_improvement=True))

    assert abstained["status"] == "abstained"
    rows = _rows(store)
    assert len(rows) == 1 and rows[0][2] == "abstained"
    assert "Martos" not in json.dumps(rows, ensure_ascii=False)


# --- Failure isolation --------------------------------------------------------------------


def test_storage_failure_never_changes_the_answer(tmp_path: Path, captured_log: io.StringIO) -> None:
    store = _store(tmp_path)
    baseline = _ask(None, _body())
    store.path.unlink()

    assert _ask(store, _body(retain_for_improvement=True)) == baseline
    log = captured_log.getvalue()
    assert '"event":"retention_skipped"' in log
    assert '"outcome":"store_failed"' in log
    assert "Juan" not in log and "solicitud" not in log


def test_redaction_failure_retains_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)

    def broken(*_args, **_kwargs):
        raise RuntimeError("synthetic redaction failure")

    monkeypatch.setattr(retention_module, "redact_text", broken)
    outcome = retain_if_opted_in(
        store,
        opted_in=True,
        question=PERSONAL_QUESTION,
        land_context=SINGLE_LAND,
        response={"status": "answered", "answer": "Respuesta sintética."},
        today=FIXED_DAY,
    )

    assert outcome == "redaction_failed"
    assert _rows(store) == []


def test_retention_outcome_codes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    answered = {"status": "answered", "answer": "Respuesta sintética."}
    common = {"question": "Pregunta sintética.", "land_context": {"mode": "general", "lands": []}}

    assert retain_if_opted_in(store, opted_in=False, response=answered, **common) == "not_opted_in"
    assert retain_if_opted_in(None, opted_in=True, response=answered, **common) == "not_configured"
    assert (
        retain_if_opted_in(
            store,
            opted_in=True,
            response={"status": "needs_land_clarification", "answer": ""},
            **common,
        )
        == "not_final"
    )
    assert retain_if_opted_in(store, opted_in=True, response=answered, today=FIXED_DAY, **common) == "retained"


# --- Expiry, purge, and owner operations ----------------------------------------------------


def _record(created_on: date) -> RetainedRecord:
    return RetainedRecord(
        created_on=created_on,
        expires_on=expiry_for(created_on),
        answer_status="answered",
        question_redacted="Pregunta sintética.",
        answer_redacted="Respuesta sintética.",
    )


def test_records_are_deleted_no_later_than_thirty_days(tmp_path: Path) -> None:
    store = _store(tmp_path)
    created = date(2026, 10, 1)
    store.retain(_record(created), today=created)

    assert (expiry_for(created) - created).days == RETENTION_DAYS - 1
    assert store.purge_expired(today=created + timedelta(days=RETENTION_DAYS - 2)) == 0
    assert store.status(today=created).records == 1
    assert store.purge_expired(today=created + timedelta(days=RETENTION_DAYS - 1)) == 1
    assert store.status(today=created).records == 0


def test_every_write_purges_expired_records_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old = date(2026, 9, 1)
    store.retain(_record(old), today=old)
    later = old + timedelta(days=RETENTION_DAYS)
    store.retain(_record(later), today=later)

    assert [row[0] for row in _rows(store)] == [later.isoformat()]


def test_status_reports_overdue_records_and_export_skips_them(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old = date(2026, 9, 1)
    store.retain(_record(old), today=old)
    store.retain(_record(FIXED_DAY), today=old)  # written before the old one was due

    status = store.status(today=FIXED_DAY)
    assert (status.records, status.overdue, status.oldest_created_on) == (2, 1, old)

    destination = tmp_path / "export.json"
    assert export_records(store, destination, today=FIXED_DAY) == 1
    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert [record["created_on"] for record in exported["records"]] == [FIXED_DAY.isoformat()]
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o600
    with pytest.raises(RetentionError) as exists:
        export_records(store, destination, today=FIXED_DAY)
    assert exists.value.code == "export_exists"
    with pytest.raises(RetentionError) as inside:
        export_records(store, BACKEND_ROOT / "retained-export.json", today=FIXED_DAY)
    assert inside.value.code == "export_inside_repository"

    assert store.delete_all() == 2
    assert store.status(today=FIXED_DAY).records == 0


def test_purge_failure_is_reported(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.path.write_bytes(b"not a sqlite database at all" * 100)

    with pytest.raises(RetentionError) as error:
        store.purge_expired(today=FIXED_DAY)
    assert error.value.code == "retention_purge_failed"


def test_store_location_must_be_owner_only_and_outside_the_repository(tmp_path: Path) -> None:
    with pytest.raises(RetentionError) as inside:
        RetentionStore.open(BACKEND_ROOT / "config" / "qa.sqlite3")
    assert inside.value.code == "retention_store_inside_repository"

    with pytest.raises(RetentionError) as missing:
        RetentionStore.open(tmp_path / "missing" / "qa.sqlite3")
    assert missing.value.code == "retention_store_directory_missing"

    if os.name == "posix":
        shared = tmp_path / "shared"
        shared.mkdir()
        os.chmod(shared, 0o755)
        with pytest.raises(RetentionError) as permissions:
            RetentionStore.open(shared / "qa.sqlite3")
        assert permissions.value.code == "retention_store_permissions"

        store = _store(tmp_path)
        assert store.path.stat().st_mode & 0o777 == 0o600


def test_unsafe_configured_store_leaves_retention_off(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    os.chmod(shared, 0o755)
    os.environ["MANIJERO_RETENTION_DB"] = str(shared / "qa.sqlite3")
    try:
        application = create_app(load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}))
    finally:
        del os.environ["MANIJERO_RETENTION_DB"]
    if os.name == "posix":
        assert application.state.retention_store is None
    assert not (shared / "qa.sqlite3").exists()


def _ops(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("MANIJERO_")}
    environment.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "pilot_ops.py"), *args],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )


def test_operator_retention_commands(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old = date(2026, 9, 1)
    store.retain(_record(old), today=old)
    env = {"MANIJERO_RETENTION_DB": str(store.path)}

    overdue = _ops("retention-status", "--as-of", FIXED_DAY.isoformat(), env_extra=env)
    assert overdue.returncode == 1
    assert "records: 1" in overdue.stdout and "overdue: 1" in overdue.stdout
    assert "alert: retention_overdue" in overdue.stderr
    assert "Pregunta" not in overdue.stdout + overdue.stderr

    purge = _ops("retention-purge", "--as-of", FIXED_DAY.isoformat(), env_extra=env)
    assert purge.returncode == 0 and "purged: 1" in purge.stdout
    assert _ops("retention-status", "--as-of", FIXED_DAY.isoformat(), env_extra=env).returncode == 0

    refused = _ops("retention-delete-all", env_extra=env)
    assert refused.returncode == 2 and "confirmation_required" in refused.stderr

    store.path.write_bytes(b"corrupt" * 200)
    failed = _ops("retention-purge", env_extra=env)
    assert failed.returncode == 1
    # The damaged store is refused when it is opened, before the purge: still an alert.
    assert "error: retention_store_unreadable" in failed.stderr

    assert "retention: not_configured" in _ops("retention-status").stdout


# --- Redaction ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mi DNI es 12345678Z y mi NIE X1234567L.", "Mi DNI es [documento] y mi NIE [documento]."),
        ("IBAN ES91 2100 0418 4502 0005 1332.", "IBAN [cuenta]."),
        ("Llama al +34 612 345 678.", "Llama al [teléfono]."),
        ("Referencia 23:050:0:0:12:345:1.", "Referencia [referencia]."),
        ("Catastro 9872023VH5797S0001WX.", "Catastro [referencia]."),
        ("Expediente 20261234567.", "Expediente [número]."),
        ("Mira https://example.org/x?y=1 ahora.", "Mira [enlace] ahora."),
        ("Soy agricultor en secano.", "Soy agricultor en secano."),
        ("Soy María López.", "Soy [nombre]."),
        ("El cortijo de La Vega tiene olivos.", "El cortijo de [nombre del terreno] tiene olivos."),
        ("La solicitud única de la PAC 2026 vence el 30 de abril.", "La solicitud única de la PAC 2026 vence el 30 de abril."),
    ],
)
def test_redaction_examples(text: str, expected: str) -> None:
    assert redact_text(text) == expected


def test_redaction_removes_every_request_land_value() -> None:
    redacted = redact_text(
        "En Villanueva del Arzobispo, y en villanueva, mi id land-42.",
        [("land-42", "[terreno]"), ("Villanueva del Arzobispo", "[municipio]"), ("Villanueva", "[municipio]")],
    )
    assert redacted == "En [municipio], y en [municipio], mi id [terreno]."


# --- Privacy review gate ------------------------------------------------------------------


def test_committed_review_record_is_pending_and_blocks_the_pilot() -> None:
    record = load_review_record()
    assert record is not None
    assert record["pilot_review"]["status"] == "pending"
    assert record["gemini_review"]["status"] == "pending"
    # The record keeps a qualification, never a reviewer's name or contact.
    assert "reviewer" not in record["pilot_review"] and "reviewer_name" not in record["pilot_review"]

    result = evaluate_pilot_review(record, as_of=FIXED_DAY)
    assert result.passed is False
    assert "privacy_review_pending" in result.blockers
    assert "privacy_review_undated" in result.blockers


def test_privacy_gate_command_reports_the_blocker() -> None:
    result = _ops("privacy-gate", "--as-of", FIXED_DAY.isoformat())
    assert result.returncode == 1
    assert "pilot_privacy_review: blocked" in result.stdout
    assert "gemini_requests: disabled" in result.stdout
    assert "blocker: privacy_review_pending" in result.stderr


def _synthetic() -> dict:
    return json.loads(SYNTHETIC_APPROVED_REVIEW.read_text(encoding="utf-8"))


def test_a_dated_complete_qualified_review_passes() -> None:
    assert evaluate_pilot_review(_synthetic(), as_of=FIXED_DAY).passed is True


@pytest.mark.parametrize(
    ("change", "blocker"),
    [
        ({"reviewed_on": None}, "privacy_review_undated"),
        ({"reviewed_on": "next week"}, "privacy_review_undated"),
        ({"reviewed_on": "2026-12-01"}, "privacy_review_future_date"),
        ({"reviewer_qualification": " "}, "privacy_review_qualification_missing"),
        ({"scope": ["notice"]}, "privacy_review_scope_incomplete"),
        ({"conditions": []}, "privacy_review_conditions_missing"),
        ({"evidence_reference": None}, "privacy_review_evidence_missing"),
        ({"status": "rejected"}, "privacy_review_rejected"),
        ({"status": "maybe"}, "privacy_review_invalid"),
        ({"reviewer_name": "x"}, "privacy_review_invalid"),
    ],
)
def test_incomplete_reviews_block(change: dict, blocker: str) -> None:
    record = _synthetic()
    record["pilot_review"].update(change)

    result = evaluate_pilot_review(record, as_of=FIXED_DAY)
    assert result.passed is False
    assert blocker in result.blockers


def test_unreadable_or_invalid_record_blocks(tmp_path: Path) -> None:
    broken = tmp_path / "review.json"
    broken.write_text("{", encoding="utf-8")
    assert evaluate_pilot_review(load_review_record(broken), as_of=FIXED_DAY).blockers == (
        "privacy_review_record_unreadable",
    )
    assert evaluate_pilot_review({"schema_version": "other"}, as_of=FIXED_DAY).blockers == (
        "privacy_review_record_invalid",
    )


# --- Gemini review gate -------------------------------------------------------------------


def test_gemini_stays_closed_with_the_committed_record() -> None:
    env = {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": "synthetic-model-for-tests"}
    decision = decide_generation_provider(env, record=load_review_record(), as_of=FIXED_DAY)

    assert decision.provider == "extractive"
    assert decision.gemini_configured is True
    assert decision.gemini_gate.passed is False
    assert "pilot_privacy_review_not_passed" in decision.gemini_gate.blockers
    assert "gemini_review_pending" in decision.gemini_gate.blockers


def test_gemini_gate_requires_the_exact_reviewed_model_and_minimal_data() -> None:
    record = _synthetic()
    assert evaluate_gemini_review(record, as_of=FIXED_DAY, configured_model="synthetic-model-for-tests").passed
    assert "gemini_model_mismatch" in evaluate_gemini_review(
        record, as_of=FIXED_DAY, configured_model="another-model"
    ).blockers

    record["gemini_review"]["data_sent"] = ["question", "approved_passages", "land_context"]
    assert "gemini_data_sent_not_minimal" in evaluate_gemini_review(
        record, as_of=FIXED_DAY, configured_model="synthetic-model-for-tests"
    ).blockers

    record = _synthetic()
    record["pilot_review"]["status"] = "pending"
    assert "pilot_privacy_review_not_passed" in evaluate_gemini_review(
        record, as_of=FIXED_DAY, configured_model="synthetic-model-for-tests"
    ).blockers


def test_even_a_passed_gemini_gate_keeps_the_extractive_path() -> None:
    env = {"MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": "synthetic-model-for-tests"}
    decision = decide_generation_provider(env, record=_synthetic(), as_of=FIXED_DAY)

    assert decision.gemini_gate.passed is True
    assert decision.provider == "extractive"


def test_configured_gemini_makes_no_network_request_on_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _ask(None, _body())
    monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", "gemini")
    monkeypatch.setenv("MANIJERO_GEMINI_MODEL", "synthetic-model-for-tests")
    attempts: list[object] = []

    def refuse(self, address, *args, **kwargs):  # noqa: ANN001
        attempts.append(address)
        raise AssertionError("no outbound connection may be attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: refuse(None, a))

    assert _ask(None, _body()) == baseline
    assert attempts == []


def test_minimal_provider_payload_carries_only_question_and_passages() -> None:
    payload = minimal_provider_payload(
        "¿Cuándo se presenta la solicitud?",
        [{"passage_id": "p-1", "text": "Texto aprobado.", "source_id": "s-1", "land_ids": ["x"]}],
    )

    assert payload == {
        "question": "¿Cuándo se presenta la solicitud?",
        "passages": [{"passage_id": "p-1", "text": "Texto aprobado."}],
    }
    assert GEMINI_ALLOWED_DATA == {"question", "approved_passages"}
    with pytest.raises(ValueError):
        minimal_provider_payload(" ", [])


def test_default_review_path_is_the_committed_record() -> None:
    assert DEFAULT_REVIEW_PATH == BACKEND_ROOT / "config" / "pilot_privacy_review.json"


def test_generated_openapi_declares_the_optional_opt_in() -> None:
    with TestClient(_app(None)) as client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]["AskRequest"]

    assert schema["properties"]["retain_for_improvement"] == {
        "type": "boolean",
        "title": "Retain For Improvement",
        "default": False,
    }
    assert "retain_for_improvement" not in schema.get("required", [])
    contract = (BACKEND_ROOT.parent / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert "retain_for_improvement:\n          type: boolean\n          default: false" in contract
