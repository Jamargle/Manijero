"""Tests for the hosted-pilot runtime gates and operator commands.

Everything here is local: no host, tunnel, domain, or provider account is involved. The
fixtures are synthetic, and the tests assert the operational boundaries — bounded bodies,
per-client authentication and rate limiting, readiness separate from liveness, hashed
backups and verified restores, and logs that never carry question text.
"""

from __future__ import annotations

from datetime import date
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import stat
import subprocess
import sys

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ask_api import (
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.main import create_app
from app import pilot_ops
from app.pilot_config import (
    ClientPolicy,
    PilotConfig,
    PilotConfigError,
    load_clients_file,
    load_config,
    token_sha256,
)
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.pilot_ops import (
    PilotOperationError,
    create_backup,
    remove_client,
    restore_backup,
    run_preflight,
    run_smoke,
    upsert_client,
)
from app.readiness import get_configured_campaign

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clarification"
CATALOG = FIXTURES / "catalog.json"
PASSAGES = FIXTURES / "passages.json"
FIXED_DAY = date(2026, 10, 13)
TOKEN = "synthetic-pilot-token-0123456789abcdef"
# A clearly labelled synthetic record: it lets the readiness path be exercised without any
# real review existing. The committed record stays pending (see test_privacy_retention.py).
SYNTHETIC_APPROVED_REVIEW = (
    Path(__file__).resolve().parent / "fixtures" / "privacy" / "synthetic_approved_review.json"
)
TOKEN_TWO = "second-synthetic-token-0123456789abcdef"
TOKEN_THREE = "third-synthetic-token-0123456789abcdef"
SHORT_TOKEN = "too-short"
MARKER = "MARCADOR-QUE-NO-DEBE-REGISTRARSE"


def pilot_config(**overrides) -> PilotConfig:
    values = {
        "profile": "pilot",
        "active_campaign": "2026",
        "max_request_bytes": 4096,
        "clients": (ClientPolicy("pilot-device", token_sha256(TOKEN), 3),),
    }
    values.update(overrides)
    return PilotConfig(**values)


def pilot_app(config: PilotConfig | None = None) -> FastAPI:
    application = create_app(config or pilot_config())
    application.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=json.loads(CATALOG.read_text(encoding="utf-8")),
        passages=json.loads(PASSAGES.read_text(encoding="utf-8")),
    )
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    application.dependency_overrides[get_configured_campaign] = lambda: "2026"
    return application


def ask_payload(question: str = "¿Cuándo se presenta la solicitud anual de ejemplo?") -> dict:
    return {"question": question, "land_context": {"mode": "general", "lands": []}}


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


def test_development_profile_keeps_the_local_behavior() -> None:
    config = load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"})

    assert config.profile == "development"
    assert config.authentication_required is False
    assert config.operational_logging is False


def test_pilot_profile_requires_campaign_and_clients(tmp_path: Path) -> None:
    with pytest.raises(PilotConfigError) as missing_campaign:
        load_config({"MANIJERO_DEPLOYMENT_PROFILE": "pilot"})
    assert missing_campaign.value.code == "campaign_invalid"

    with pytest.raises(PilotConfigError) as missing_clients:
        load_config(
            {
                "MANIJERO_DEPLOYMENT_PROFILE": "pilot",
                "MANIJERO_ACTIVE_CAMPAIGN": "2026",
            }
        )
    assert missing_clients.value.code == "clients_missing"


def test_pilot_profile_rejects_unknown_profile_and_request_bound() -> None:
    with pytest.raises(PilotConfigError) as profile:
        load_config({"MANIJERO_DEPLOYMENT_PROFILE": "staging"})
    assert profile.value.code == "profile_invalid"

    with pytest.raises(PilotConfigError) as bound:
        load_config({"MANIJERO_MAX_REQUEST_BYTES": "10"})
    assert bound.value.code == "request_limit_invalid"


def test_clients_file_requires_restricted_permissions(tmp_path: Path) -> None:
    path = tmp_path / "pilot-clients.json"
    upsert_client(path, client_id="pilot-device", token=TOKEN, requests_per_minute=5)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert TOKEN not in path.read_text(encoding="utf-8")

    path.chmod(0o644)
    with pytest.raises(PilotConfigError) as error:
        load_clients_file(path)
    assert error.value.code == "clients_permissions"


def test_clients_file_rejects_duplicate_and_unknown_fields(tmp_path: Path) -> None:
    document = {
        "schema_version": "pilot-clients-v1",
        "clients": [
            {
                "client_id": "pilot-device",
                "token_sha256": token_sha256(TOKEN),
                "requests_per_minute": 5,
                "enabled": True,
                "note": "untracked",
            }
        ],
    }
    path = tmp_path / "pilot-clients.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(PilotConfigError) as error:
        load_clients_file(path)
    assert error.value.code == "clients_invalid"


def test_upsert_and_remove_client_keep_digests_only(tmp_path: Path) -> None:
    path = tmp_path / "pilot-clients.json"
    assert upsert_client(path, client_id="pilot-a", token=TOKEN, requests_per_minute=5) == 1
    assert upsert_client(path, client_id="pilot-b", token=TOKEN_TWO, requests_per_minute=5) == 2
    assert upsert_client(path, client_id="pilot-a", token=TOKEN_THREE, requests_per_minute=9) == 2

    document = json.loads(path.read_text(encoding="utf-8"))
    digests = {record["client_id"]: record["token_sha256"] for record in document["clients"]}
    assert digests == {"pilot-a": token_sha256(TOKEN_THREE), "pilot-b": token_sha256(TOKEN_TWO)}
    assert TOKEN_THREE not in path.read_text(encoding="utf-8")

    assert remove_client(path, client_id="pilot-b") == 1
    with pytest.raises(PilotOperationError) as missing:
        remove_client(path, client_id="pilot-b")
    assert missing.value.code == "client_not_found"
    with pytest.raises(PilotOperationError) as last:
        remove_client(path, client_id="pilot-a")
    assert last.value.code == "last_client_refused"
    assert json.loads(path.read_text(encoding="utf-8"))["clients"][0]["client_id"] == "pilot-a"


def test_upsert_client_requires_a_long_token(tmp_path: Path) -> None:
    path = tmp_path / "pilot-clients.json"

    with pytest.raises(PilotOperationError) as weak:
        upsert_client(path, client_id="pilot-a", token=SHORT_TOKEN, requests_per_minute=5)

    assert weak.value.code == "token_too_weak"
    assert not path.exists()


def test_pilot_answer_route_requires_a_client_token() -> None:
    with TestClient(pilot_app()) as client:
        assert client.post("/ask", json=ask_payload()).status_code == 401
        rejected = client.post(
            "/ask", json=ask_payload(), headers={"authorization": "Bearer wrong"}
        )
        assert rejected.status_code == 401
        assert "synthetic" not in rejected.text.lower()
        accepted = client.post(
            "/ask", json=ask_payload(), headers={"authorization": f"Bearer {TOKEN}"}
        )
        assert accepted.status_code == 200


def test_pilot_rate_limit_is_per_client() -> None:
    with TestClient(pilot_app()) as client:
        headers = {"authorization": f"Bearer {TOKEN}"}
        statuses = [
            client.post("/ask", json=ask_payload(), headers=headers).status_code
            for _ in range(4)
        ]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


def test_request_body_bound_is_enforced_with_a_generic_response() -> None:
    config = pilot_config(max_request_bytes=1024)
    with TestClient(pilot_app(config)) as client:
        response = client.post(
            "/ask",
            json=ask_payload("¿" + MARKER * 500 + "?"),
            headers={"authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}
    assert MARKER not in response.text


def test_pilot_liveness_and_readiness_are_open_and_readiness_carries_no_corpus() -> None:
    with TestClient(pilot_app()) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "manijero-backend",
        }
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready", "service": "manijero-backend"}


def test_readiness_fails_closed_without_a_campaign_or_a_usable_corpus() -> None:
    application = pilot_app()
    application.dependency_overrides[get_configured_campaign] = lambda: None
    with TestClient(application) as client:
        unavailable = client.get("/ready")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"status": "unavailable", "service": "manijero-backend"}

    application = pilot_app()
    application.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog={"schema_version": "source-catalog-v1", "sources": []},
        passages={"schema_version": "passage-set-v1", "passages": []},
    )
    with TestClient(application) as client:
        assert client.get("/ready").status_code == 503

    expired = pilot_app()
    expired.dependency_overrides[get_corpus_documents] = lambda: CorpusDocuments(
        catalog=_campaign_catalog(), passages=json.loads(PASSAGES.read_text(encoding="utf-8"))
    )
    expired.dependency_overrides[get_as_of_date] = lambda: date(2027, 6, 1)
    with TestClient(expired) as client:
        assert client.get("/ready").status_code == 503


def test_pilot_profile_hides_interactive_docs() -> None:
    with TestClient(pilot_app()) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_operational_log_records_metadata_only(captured_log: io.StringIO) -> None:
    with TestClient(pilot_app()) as client:
        response = client.post(
            "/ask",
            json=ask_payload(MARKER),
            headers={"authorization": f"Bearer {TOKEN}"},
            params={"q": MARKER},
        )

    assert response.status_code in {200, 422}
    output = captured_log.getvalue()
    assert MARKER not in output
    assert TOKEN not in output
    assert '"event":"request"' in output
    assert '"path":"/ask"' in output
    assert '"gate":"authenticated"' in output


def test_generic_server_error_does_not_echo_the_exception(captured_log: io.StringIO) -> None:
    application = pilot_app()

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError(MARKER)

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert MARKER not in response.text
    assert MARKER not in captured_log.getvalue()


def test_preflight_requires_the_pilot_profile_and_a_ready_corpus(tmp_path: Path) -> None:
    development = run_preflight({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}, as_of=FIXED_DAY)
    assert "pilot_profile_required" in development.problems

    pilot_without_clients = run_preflight(
        {"MANIJERO_DEPLOYMENT_PROFILE": "pilot", "MANIJERO_ACTIVE_CAMPAIGN": "2026"},
        as_of=FIXED_DAY,
    )
    assert pilot_without_clients.problems == ("clients_missing",)

    blocked = run_preflight(
        _pilot_env(tmp_path), as_of=FIXED_DAY, catalog_path=CATALOG, passages_path=PASSAGES
    )
    assert blocked.ok is False
    assert "privacy_review_pending" in blocked.problems
    assert blocked.privacy_review_passed is False

    ready = run_preflight(
        _pilot_env(tmp_path),
        as_of=FIXED_DAY,
        catalog_path=CATALOG,
        passages_path=PASSAGES,
        privacy_review_path=SYNTHETIC_APPROVED_REVIEW,
    )
    assert ready.problems == ()
    assert ready.ok is True
    assert ready.privacy_review_passed is True
    assert ready.campaign == "2026"
    assert ready.configured_clients == 1


def test_preflight_reports_an_expired_corpus_as_not_ready(tmp_path: Path) -> None:
    catalog_path = tmp_path / "source_catalog.json"
    catalog_path.write_text(json.dumps(_campaign_catalog()), encoding="utf-8")

    report = run_preflight(
        _pilot_env(tmp_path),
        as_of=date(2027, 6, 1),
        catalog_path=catalog_path,
        passages_path=PASSAGES,
    )

    assert report.ok is False
    assert "corpus_not_current" in report.problems


def test_backup_and_restore_round_trip_and_refuse_corruption(tmp_path: Path) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
        config_files=(),
    )
    target_catalog = tmp_path / "knowledge" / "source_catalog.json"
    target_passages = tmp_path / "knowledge" / "passages.json"
    target_catalog.parent.mkdir()
    target_catalog.write_bytes(b'{"schema_version":"source-catalog-v1","sources":[]}')
    target_passages.write_bytes(b'{"schema_version":"passage-set-v1","passages":[]}')

    report = restore_backup(
        backup.directory,
        confirm=True,
        env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
        catalog_path=target_catalog,
        passages_path=target_passages,
        as_of=FIXED_DAY,
    )

    assert report.roles == ("catalog", "passages")
    assert report.readiness.ready is True
    assert target_catalog.read_bytes() == CATALOG.read_bytes()
    assert target_passages.read_bytes() == PASSAGES.read_bytes()
    # Canonical artifacts are read by the service account, which may not own them.
    assert stat.S_IMODE(target_catalog.stat().st_mode) == 0o644
    assert stat.S_IMODE(target_passages.stat().st_mode) == 0o644

    with pytest.raises(PilotOperationError) as unconfirmed:
        restore_backup(backup.directory, confirm=False)
    assert unconfirmed.value.code == "confirmation_required"

    (backup.directory / "passages.json").write_bytes(b"corrupted")
    with pytest.raises(PilotOperationError) as corrupt:
        restore_backup(
            backup.directory,
            confirm=True,
            catalog_path=target_catalog,
            passages_path=target_passages,
        )
    assert corrupt.value.code == "backup_corrupt"
    assert target_passages.read_bytes() == PASSAGES.read_bytes()


def test_backup_refuses_the_canonical_knowledge_directory(tmp_path: Path) -> None:
    with pytest.raises(PilotOperationError) as error:
        create_backup(
            BACKEND_ROOT.parent / "knowledge",
            campaign="2026",
            catalog_path=CATALOG,
            passages_path=PASSAGES,
        )
    assert error.value.code == "destination_inside_knowledge"


def test_backup_refuses_client_credentials_and_secret_config(tmp_path: Path) -> None:
    clients = tmp_path / "pilot-clients.json"
    upsert_client(clients, client_id="pilot-a", token=TOKEN, requests_per_minute=5)
    destination = tmp_path / "backups"

    with pytest.raises(PilotOperationError) as credentials:
        create_backup(
            destination,
            campaign="2026",
            catalog_path=CATALOG,
            passages_path=PASSAGES,
            config_files=(clients,),
        )

    assert credentials.value.code == "config_file_not_allowed"
    assert not destination.exists()

    secret = tmp_path / "pilot.env"
    secret.write_text(f"token_sha256={token_sha256(TOKEN)}\n", encoding="utf-8")
    with pytest.raises(PilotOperationError) as marker:
        create_backup(
            destination,
            campaign="2026",
            catalog_path=CATALOG,
            passages_path=PASSAGES,
            config_files=(secret,),
        )

    assert marker.value.code == "config_file_secret"
    assert not destination.exists()


def test_backup_tree_is_owner_only_and_carries_no_credential(tmp_path: Path) -> None:
    config = tmp_path / "pilot.env"
    config.write_text("MANIJERO_ACTIVE_CAMPAIGN=2026\n", encoding="utf-8")

    report = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
        config_files=(config,),
    )

    assert stat.S_IMODE(report.directory.stat().st_mode) == 0o700
    for path in report.directory.rglob("*"):
        expected = 0o700 if path.is_dir() else 0o600
        assert stat.S_IMODE(path.stat().st_mode) == expected, path
    contents = b"".join(
        path.read_bytes() for path in report.directory.rglob("*") if path.is_file()
    )
    assert token_sha256(TOKEN).encode("utf-8") not in contents
    assert TOKEN.encode("utf-8") not in contents


def test_backup_refuses_an_invalid_campaign(tmp_path: Path) -> None:
    destination = tmp_path / "backups"

    with pytest.raises(PilotOperationError) as error:
        create_backup(
            destination,
            campaign="202",
            catalog_path=CATALOG,
            passages_path=PASSAGES,
        )

    assert error.value.code == "campaign_invalid"
    assert not destination.exists()


def test_restore_validates_the_backup_before_touching_the_targets(tmp_path: Path) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    _replace_backup_file(
        backup.directory,
        "passages.json",
        b'{"schema_version":"passage-set-v1","passages":[{"id":"p","source_id":"missing"}]}',
    )
    target_catalog = tmp_path / "target" / "source_catalog.json"
    target_passages = tmp_path / "target" / "passages.json"
    target_catalog.parent.mkdir()
    catalog_before = b'{"schema_version":"source-catalog-v1","sources":[]}'
    passages_before = b'{"schema_version":"passage-set-v1","passages":[]}'
    target_catalog.write_bytes(catalog_before)
    target_passages.write_bytes(passages_before)

    with pytest.raises(PilotOperationError) as invalid:
        restore_backup(
            backup.directory,
            confirm=True,
            env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
            catalog_path=target_catalog,
            passages_path=target_passages,
            as_of=FIXED_DAY,
        )

    assert invalid.value.code == "backup_corpus_invalid"
    assert invalid.value.exit_code == 2
    assert target_catalog.read_bytes() == catalog_before
    assert target_passages.read_bytes() == passages_before


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_refuses_an_unreadable_target_without_unlinking_it(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can read a mode-0000 file")
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_catalog = tmp_path / "target" / "source_catalog.json"
    target_passages = tmp_path / "target" / "passages.json"
    target_catalog.parent.mkdir()
    target_catalog.write_bytes(b'{"original":"catalog"}')
    target_passages.write_bytes(b'{"original":"passages"}')
    target_catalog.chmod(0o000)

    try:
        with pytest.raises(PilotOperationError) as unreadable:
            restore_backup(
                backup.directory,
                confirm=True,
                env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
                catalog_path=target_catalog,
                passages_path=target_passages,
                as_of=FIXED_DAY,
            )

        assert unreadable.value.code == "target_unreadable"
        assert target_catalog.exists()
        assert stat.S_IMODE(target_catalog.stat().st_mode) == 0
        assert target_passages.read_bytes() == b'{"original":"passages"}'
    finally:
        target_catalog.chmod(0o600)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_reports_a_read_only_target_directory_without_claiming_success(
    tmp_path: Path,
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can write a mode-0555 directory")
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target_catalog = target_dir / "source_catalog.json"
    target_passages = target_dir / "passages.json"
    target_catalog.write_bytes(b'{"original":"catalog"}')
    target_passages.write_bytes(b'{"original":"passages"}')
    target_dir.chmod(0o555)

    try:
        with pytest.raises(PilotOperationError) as read_only:
            restore_backup(
                backup.directory,
                confirm=True,
                env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
                catalog_path=target_catalog,
                passages_path=target_passages,
                as_of=FIXED_DAY,
            )

        assert read_only.value.code == "restore_write_failed"
        assert target_catalog.read_bytes() == b'{"original":"catalog"}'
        assert target_passages.read_bytes() == b'{"original":"passages"}'
    finally:
        target_catalog.parent.chmod(0o700)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_writes_service_readable_files_over_private_targets(tmp_path: Path) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_catalog = tmp_path / "target" / "source_catalog.json"
    target_passages = tmp_path / "target" / "passages.json"
    target_catalog.parent.mkdir()
    target_catalog.write_bytes(b'{"original":"catalog"}')
    target_passages.write_bytes(b'{"original":"passages"}')
    target_catalog.chmod(0o600)
    target_passages.chmod(0o600)

    report = restore_backup(
        backup.directory,
        confirm=True,
        env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
        catalog_path=target_catalog,
        passages_path=target_passages,
        as_of=FIXED_DAY,
    )

    assert report.readiness.ready is True
    assert stat.S_IMODE(target_catalog.stat().st_mode) == 0o644
    assert stat.S_IMODE(target_passages.stat().st_mode) == 0o644
    assert pilot_ops._service_readable(target_catalog) is True
    assert pilot_ops._service_readable(target_passages) is True


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_under_a_restrictive_umask_still_writes_readable_files(
    tmp_path: Path,
) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_catalog = tmp_path / "fresh" / "source_catalog.json"
    target_passages = tmp_path / "fresh" / "passages.json"

    previous_umask = os.umask(0o077)
    try:
        report = restore_backup(
            backup.directory,
            confirm=True,
            env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
            catalog_path=target_catalog,
            passages_path=target_passages,
            as_of=FIXED_DAY,
        )
    finally:
        os.umask(previous_umask)

    assert report.readiness.ready is True
    assert stat.S_IMODE(target_catalog.stat().st_mode) == 0o644
    assert stat.S_IMODE(target_passages.stat().st_mode) == 0o644


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_failed_second_write_reverts_the_prior_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_catalog = tmp_path / "target" / "source_catalog.json"
    target_passages = tmp_path / "target" / "passages.json"
    target_catalog.parent.mkdir()
    catalog_before = b'{"original":"catalog"}'
    passages_before = b'{"original":"passages"}'
    target_catalog.write_bytes(catalog_before)
    target_passages.write_bytes(passages_before)
    target_catalog.chmod(0o640)
    target_passages.chmod(0o600)

    real_write = pilot_ops._write_canonical

    def fail_on_passages(path: Path, data: bytes, prior: object) -> None:
        if path == target_passages:
            raise OSError("simulated second-write failure")
        real_write(path, data, prior)  # type: ignore[arg-type]

    monkeypatch.setattr(pilot_ops, "_write_canonical", fail_on_passages)

    with pytest.raises(PilotOperationError) as error:
        restore_backup(
            backup.directory,
            confirm=True,
            env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
            catalog_path=target_catalog,
            passages_path=target_passages,
            as_of=FIXED_DAY,
        )

    assert error.value.code == "restore_write_failed"
    assert error.value.exit_code == 2
    assert target_catalog.read_bytes() == catalog_before
    assert stat.S_IMODE(target_catalog.stat().st_mode) == 0o640
    assert target_passages.read_bytes() == passages_before
    assert stat.S_IMODE(target_passages.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_restore_refuses_a_result_the_service_cannot_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = create_backup(
        tmp_path / "backups",
        campaign="2026",
        catalog_path=CATALOG,
        passages_path=PASSAGES,
    )
    target_catalog = tmp_path / "target" / "source_catalog.json"
    target_passages = tmp_path / "target" / "passages.json"
    target_catalog.parent.mkdir()
    catalog_before = b'{"original":"catalog"}'
    passages_before = b'{"original":"passages"}'
    target_catalog.write_bytes(catalog_before)
    target_passages.write_bytes(passages_before)
    target_catalog.chmod(0o640)
    target_passages.chmod(0o640)

    def write_privately(path: Path, data: bytes, prior: object) -> None:
        pilot_ops._write_atomically(path, data, mode=0o600)

    monkeypatch.setattr(pilot_ops, "_write_canonical", write_privately)

    with pytest.raises(PilotOperationError) as error:
        restore_backup(
            backup.directory,
            confirm=True,
            env={"MANIJERO_ACTIVE_CAMPAIGN": "2026"},
            catalog_path=target_catalog,
            passages_path=target_passages,
            as_of=FIXED_DAY,
        )

    assert error.value.code == "corpus_not_readable"
    assert error.value.exit_code == 2
    assert target_catalog.read_bytes() == catalog_before
    assert target_passages.read_bytes() == passages_before
    assert stat.S_IMODE(target_catalog.stat().st_mode) == 0o640
    assert stat.S_IMODE(target_passages.stat().st_mode) == 0o640


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
def test_service_readable_helper_requires_every_read_bit(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_bytes(b"{}")

    path.chmod(0o600)
    assert pilot_ops._service_readable(path) is False
    path.chmod(0o640)
    assert pilot_ops._service_readable(path) is False
    path.chmod(0o644)
    assert pilot_ops._service_readable(path) is True


def test_restore_command_refuses_while_the_service_is_active(tmp_path: Path) -> None:
    systemctl = tmp_path / "bin" / "systemctl"
    systemctl.parent.mkdir()
    systemctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    systemctl.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{systemctl.parent}:{os.environ.get('PATH', '')}",
    }

    active = _restore_command(tmp_path / "missing", environment)
    assert active.returncode == 2
    assert "service_running" in active.stderr

    systemctl.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    stopped = _restore_command(tmp_path / "missing", environment)
    assert stopped.returncode == 2
    assert "backup_unreadable" in stopped.stderr
    assert "service_running" not in stopped.stderr

    empty_path = tmp_path / "empty"
    empty_path.mkdir()
    unchecked = _restore_command(
        tmp_path / "missing", {**os.environ, "PATH": str(empty_path)}
    )
    assert unchecked.returncode == 2
    assert "warning:" in unchecked.stderr
    assert "backup_unreadable" in unchecked.stderr


def test_smoke_reports_statuses_without_answer_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "service": "manijero-backend"})
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready", "service": "manijero-backend"})
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert json.loads(request.content)["land_context"] == {"mode": "general", "lands": []}
        return httpx.Response(
            200,
            json={
                "status": "abstained",
                "answer": "SIN-RESPUESTA-SINTETICA",
                "sources": [],
                "land_scope": "general",
                "land_ids_to_choose": [],
            },
        )

    report = run_smoke(
        "https://pilot.example.test",
        token=TOKEN,
        transport=httpx.MockTransport(handler),
    )

    assert report.ok is True
    assert report.ask_state == "abstained"
    assert "SIN-RESPUESTA-SINTETICA" not in repr(report)


def test_smoke_flags_missing_credentials_and_plain_http_off_loopback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ask":
            return httpx.Response(401, json={"detail": "Client credentials are required."})
        return httpx.Response(200, json={"status": "ok", "service": "manijero-backend"})

    report = run_smoke(
        "https://pilot.example.test",
        transport=httpx.MockTransport(handler),
    )
    assert report.failures == ("ask_unauthorized",)

    with pytest.raises(PilotOperationError) as error:
        run_smoke("http://pilot.example.test")
    assert error.value.code == "base_url_requires_https"


def test_serve_pilot_refuses_without_a_pilot_configuration() -> None:
    import subprocess

    environment = {
        key: value
        for key, value in __import__("os").environ.items()
        if not key.startswith("MANIJERO_")
    }
    environment.update({"MANIJERO_DEPLOYMENT_PROFILE": "development"})
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "serve_pilot.py"), "--preflight-only"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )

    assert result.returncode == 2
    assert "refused: pilot_profile_required" in result.stderr




def _replace_backup_file(directory: Path, name: str, payload: bytes) -> None:
    """Keep a tampered backup internally consistent so the shape check is what fires."""

    (directory / name).write_bytes(payload)
    manifest_path = directory / "backup-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["name"] == name:
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            entry["size_bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _restore_command(backup_dir: Path, environment: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "pilot_ops.py"),
            "restore",
            "--backup-dir",
            str(backup_dir),
            "--confirm",
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )


def _campaign_catalog() -> dict:
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    for source in document["sources"]:
        source["campaign"] = "2026"
        source["valid_until"] = "2026-12-31"
    return document


def _pilot_env(tmp_path: Path) -> dict[str, str]:
    clients = tmp_path / "pilot-clients.json"
    upsert_client(clients, client_id="pilot-device", token=TOKEN, requests_per_minute=5)
    return {
        "MANIJERO_DEPLOYMENT_PROFILE": "pilot",
        "MANIJERO_ACTIVE_CAMPAIGN": "2026",
        "MANIJERO_PILOT_CLIENTS_FILE": str(clients),
    }
