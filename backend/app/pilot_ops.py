"""Operator commands for the private hosted pilot service.

These are the repeatable operations behind the runbook in ``backend/README.md``:
preflight before serving traffic, a hashed backup of the reviewed corpus plus
non-secret operator configuration, a verified restore, a deployment smoke check, and
client-credential rotation. Every function is standard-library except the smoke check,
which uses the declared ``httpx`` runtime dependency.

Nothing here reads or prints a question, an answer, a land value, or a bearer token.
Manifests store hashes and the campaign only; a token is shown once by the operator and
the file keeps its SHA-256 digest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Mapping, Sequence, Tuple
from urllib.parse import urlparse

from app.pilot_config import (
    DEFAULT_MAX_REQUEST_BYTES,
    DEVELOPMENT_PROFILE,
    ClientPolicy,
    PilotConfigError,
    load_config,
    parse_campaign,
    serialized_clients_document,
    token_sha256,
    validate_clients_document,
)
from app.readiness import ReadinessResult, evaluate_readiness

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "source_catalog.json"
DEFAULT_PASSAGES_PATH = REPOSITORY_ROOT / "knowledge" / "passages.json"

BACKUP_SCHEMA_VERSION = "pilot-backup-v1"
CATALOG_ROLE = "catalog"
PASSAGES_ROLE = "passages"
# Canonical artifacts are read by the service account (systemd User=manijero), which may
# not own them: a restore writes them world-readable. Backup files remain 0600.
CANONICAL_CORPUS_MODE = 0o644
# Only these non-secret operator files may enter a backup. The clients file, tunnel
# credentials, and anything else fail closed instead of being copied.
BACKUP_CONFIG_ALLOWLIST = frozenset({"pilot.env", "pilot.env.example"})
# A token must be long enough that the fast SHA-256 digest is not a practical offline
# target if the clients file is exposed. 32 characters is the floor; the runbook generates
# 48 random bytes (64 base64 characters).
MIN_CLIENT_TOKEN_LENGTH = 32
_SECRET_MARKERS = (
    b"token_sha256",
    b"begin private key",
    b"begin rsa private key",
    b"begin openssh private key",
    b"begin ec private key",
    b"tunnelsecret",
    b"accounttag",
    b"client_secret",
    b"aws_secret_access_key",
)
_SMOKE_QUESTION = "Pregunta sintética de comprobación del servicio."
_HASH = re.compile(r"[0-9a-f]{64}")


class PilotOperationError(Exception):
    """A failed operator command named by a fixed code and no sensitive value."""

    def __init__(self, code: str, exit_code: int = 2) -> None:
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class _PriorTarget:
    """A canonical target's bytes and permission metadata before a restore."""

    content: bytes | None = None
    mode: int = CANONICAL_CORPUS_MODE
    uid: int | None = None
    gid: int | None = None


@dataclass(frozen=True)
class PreflightReport:
    """Outcome of the pre-deployment configuration and corpus check."""

    profile: str
    campaign: str | None
    configured_clients: int
    max_request_bytes: int
    readiness: ReadinessResult | None
    problems: Tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass(frozen=True)
class BackupReport:
    """What a corpus backup wrote, without any configuration secret."""

    directory: Path
    campaign: str | None
    roles: Tuple[str, ...]
    config_files: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RestoreReport:
    """What a restore replaced and whether the service would be ready afterwards."""

    roles: Tuple[str, ...]
    readiness: ReadinessResult
    campaign: str | None


@dataclass(frozen=True)
class SmokeReport:
    """Deployment smoke result: statuses only, never an answer or a question."""

    health_status: int | None
    readiness_status: int | None
    ask_status_code: int | None
    ask_state: str | None
    failures: Tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not self.failures


def run_preflight(
    env: Mapping[str, str] | None = None,
    *,
    as_of: date | None = None,
    catalog_path: Path | None = None,
    passages_path: Path | None = None,
) -> PreflightReport:
    """Validate the pilot profile, explicit campaign, credentials, and corpus."""

    checked_on = as_of or date.today()
    try:
        config = load_config(env)
    except PilotConfigError as error:
        return PreflightReport(
            profile=str((env or os.environ).get("MANIJERO_DEPLOYMENT_PROFILE", DEVELOPMENT_PROFILE)),
            campaign=None,
            configured_clients=0,
            max_request_bytes=DEFAULT_MAX_REQUEST_BYTES,
            readiness=None,
            problems=(error.code,),
        )
    problems: list[str] = []
    if not config.pilot:
        problems.append("pilot_profile_required")
    documents = _load_documents(catalog_path, passages_path)
    readiness = evaluate_readiness(documents, checked_on, config.active_campaign)
    problems.extend(readiness.problems)
    return PreflightReport(
        profile=config.profile,
        campaign=config.active_campaign,
        configured_clients=len(config.clients),
        max_request_bytes=config.max_request_bytes,
        readiness=readiness,
        problems=tuple(problems),
    )


def create_backup(
    destination: Path,
    *,
    campaign: str | None,
    catalog_path: Path | None = None,
    passages_path: Path | None = None,
    config_files: Sequence[Path] = (),
    now: datetime | None = None,
) -> BackupReport:
    """Copy the reviewed corpus and named non-secret configuration to a hashed backup."""

    if campaign is not None and parse_campaign(campaign) != campaign:
        raise PilotOperationError("campaign_invalid")
    root = Path(destination).expanduser().resolve()
    if root == REPOSITORY_ROOT / "knowledge" or (REPOSITORY_ROOT / "knowledge") in root.parents:
        raise PilotOperationError("destination_inside_knowledge")

    prepared_config: list[tuple[Path, bytes]] = []
    seen_names: set[str] = set()
    for config_file in config_files:
        source = Path(config_file).expanduser()
        if not source.is_file():
            raise PilotOperationError("config_file_missing")
        if source.name not in BACKUP_CONFIG_ALLOWLIST:
            raise PilotOperationError("config_file_not_allowed")
        if source.name in seen_names:
            raise PilotOperationError("config_file_duplicate")
        seen_names.add(source.name)
        try:
            payload = source.read_bytes()
        except OSError as error:
            raise PilotOperationError("config_file_unreadable") from error
        if _contains_secret_marker(payload):
            raise PilotOperationError("config_file_secret")
        prepared_config.append((source, payload))

    if root.exists() and not root.is_dir():
        raise PilotOperationError("destination_invalid")
    if not root.exists():
        root.mkdir(parents=True)
        _chmod_private_dir(root)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = root / f"manijero-pilot-backup-{stamp}"
    suffix = 1
    while backup_dir.exists():
        backup_dir = root / f"manijero-pilot-backup-{stamp}-{suffix}"
        suffix += 1
    backup_dir.mkdir(mode=0o700)
    _chmod_private_dir(backup_dir)

    files = [
        _copy_role(CATALOG_ROLE, Path(catalog_path or DEFAULT_CATALOG_PATH), backup_dir),
        _copy_role(PASSAGES_ROLE, Path(passages_path or DEFAULT_PASSAGES_PATH), backup_dir),
    ]
    copied_config: list[dict] = []
    for source, payload in prepared_config:
        config_dir = backup_dir / "config"
        if not config_dir.exists():
            config_dir.mkdir(mode=0o700)
            _chmod_private_dir(config_dir)
        target = config_dir / source.name
        _write_private_bytes(target, payload)
        copied_config.append(
            {"name": f"config/{source.name}", "sha256": _sha256(payload), "size_bytes": len(payload)}
        )

    manifest = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "campaign": campaign,
        "files": files,
        "config_files": sorted(copied_config, key=lambda entry: entry["name"]),
    }
    _write_private_bytes(
        backup_dir / "backup-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
    )
    return BackupReport(
        directory=backup_dir,
        campaign=campaign,
        roles=tuple(entry["role"] for entry in files),
        config_files=tuple(entry["name"] for entry in copied_config),
    )


def restore_backup(
    backup_dir: Path,
    *,
    confirm: bool,
    env: Mapping[str, str] | None = None,
    catalog_path: Path | None = None,
    passages_path: Path | None = None,
    as_of: date | None = None,
) -> RestoreReport:
    """Replace the canonical corpus with a verified backup, or refuse and change nothing."""

    if not confirm:
        raise PilotOperationError("confirmation_required")
    root = Path(backup_dir).expanduser()
    manifest = _read_manifest(manifest_path=root / "backup-manifest.json")
    entries = {entry["role"]: entry for entry in manifest["files"]}
    for role in (CATALOG_ROLE, PASSAGES_ROLE):
        if role not in entries:
            raise PilotOperationError("backup_incomplete")
    payloads = {
        entry["role"]: _verified_bytes(root / entry["name"], entry) for entry in manifest["files"]
    }
    for config_entry in manifest.get("config_files", []):
        _verified_bytes(root / config_entry["name"], config_entry)
    if not _corpus_shape_valid(payloads):
        raise PilotOperationError("backup_corpus_invalid")

    targets = {
        CATALOG_ROLE: Path(catalog_path or DEFAULT_CATALOG_PATH),
        PASSAGES_ROLE: Path(passages_path or DEFAULT_PASSAGES_PATH),
    }
    previous = {role: _read_prior(path) for role, path in targets.items()}
    written: list[str] = []
    try:
        for role in (CATALOG_ROLE, PASSAGES_ROLE):
            _write_canonical(targets[role], payloads[role], previous[role])
            written.append(role)
        if not all(_service_readable(targets[role]) for role in written):
            raise PilotOperationError("corpus_not_readable")
    except PilotOperationError as error:
        for role in written:
            _restore_prior(targets[role], previous[role])
        raise error
    except OSError as error:
        for role in written:
            _restore_prior(targets[role], previous[role])
        raise PilotOperationError("restore_write_failed") from error

    campaign = manifest.get("campaign")
    try:
        campaign = load_config(env).active_campaign or campaign
    except PilotConfigError:
        pass
    documents = _load_documents(targets[CATALOG_ROLE], targets[PASSAGES_ROLE])
    readiness = evaluate_readiness(documents, as_of or date.today(), campaign)
    return RestoreReport(
        roles=tuple(written),
        readiness=readiness,
        campaign=campaign,
    )


def service_active_status(unit: str = "manijero-pilot") -> bool | None:
    """Report whether a systemd unit is active, or ``None`` when systemd is unavailable.

    The restore command uses this to refuse swapping the corpus under a running service.
    It never raises and prints no unit detail.
    """

    executable = shutil.which("systemctl")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "is-active", "--quiet", unit],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.returncode == 0


def run_smoke(
    base_url: str,
    *,
    token: str | None = None,
    timeout: float = 10.0,
    transport: object | None = None,
) -> SmokeReport:
    """Check health, readiness, and one synthetic answer request on a deployment."""

    import httpx

    url = base_url.rstrip("/")
    _require_acceptable_base_url(url)
    headers = {"authorization": f"Bearer {token}"} if token else {}
    failures: list[str] = []
    health_status: int | None = None
    readiness_status: int | None = None
    ask_status_code: int | None = None
    ask_state: str | None = None
    payload = {
        "question": _SMOKE_QUESTION,
        "land_context": {"mode": "general", "lands": []},
    }

    with httpx.Client(timeout=timeout, transport=transport, follow_redirects=False) as client:
        try:
            response = client.get(f"{url}/health")
            health_status = response.status_code
            if health_status != 200:
                failures.append("health_status")
        except httpx.HTTPError:
            failures.append("health_unreachable")

        try:
            response = client.get(f"{url}/ready")
            readiness_status = response.status_code
            if readiness_status != 200:
                failures.append("ready_status")
        except httpx.HTTPError:
            failures.append("ready_unreachable")

        try:
            response = client.post(f"{url}/ask", json=payload, headers=headers)
            ask_status_code = response.status_code
            if ask_status_code == 200:
                body = response.json()
                ask_state = body.get("status") if isinstance(body, dict) else None
                if ask_state not in {"answered", "abstained", "needs_land_clarification"}:
                    failures.append("ask_payload")
            elif ask_status_code in {401, 403}:
                failures.append("ask_unauthorized")
            else:
                failures.append("ask_status")
        except httpx.HTTPError:
            failures.append("ask_unreachable")
        except ValueError:
            failures.append("ask_payload")

    return SmokeReport(
        health_status=health_status,
        readiness_status=readiness_status,
        ask_status_code=ask_status_code,
        ask_state=ask_state,
        failures=tuple(failures),
    )


def upsert_client(
    clients_path: Path,
    *,
    client_id: str,
    token: str,
    requests_per_minute: int,
) -> int:
    """Add or replace one enabled client, writing digests only, and return the count."""

    if len(token) < MIN_CLIENT_TOKEN_LENGTH:
        raise PilotOperationError("token_too_weak")
    path = Path(clients_path).expanduser()
    if not path.parent.is_dir():
        raise PilotOperationError("clients_dir_missing")
    existing = _existing_clients(path)
    replacement = ClientPolicy(client_id, token_sha256(token), requests_per_minute)
    merged = [client for client in existing if client.client_id != client_id] + [replacement]
    document = serialized_clients_document(tuple(merged))
    validate_clients_document(document)
    _write_private_json(path, document)
    return len(merged)


def remove_client(clients_path: Path, *, client_id: str) -> int:
    """Revoke one client credential and return the number of enabled clients left."""

    path = Path(clients_path).expanduser()
    existing = _existing_clients(path)
    remaining = [client for client in existing if client.client_id != client_id]
    if len(remaining) == len(existing):
        raise PilotOperationError("client_not_found", exit_code=1)
    if not remaining:
        raise PilotOperationError("last_client_refused")
    document = serialized_clients_document(tuple(remaining))
    _write_private_json(path, document)
    return len(remaining)


def _load_documents(catalog_path: Path | None, passages_path: Path | None):
    from app.ask_api import load_corpus_documents

    return load_corpus_documents(
        catalog_path=Path(catalog_path) if catalog_path else None,
        passages_path=Path(passages_path) if passages_path else None,
    )


def _copy_role(role: str, source: Path, backup_dir: Path) -> dict:
    try:
        data = source.read_bytes()
    except OSError as error:
        raise PilotOperationError("corpus_file_missing") from error
    name = "source_catalog.json" if role == CATALOG_ROLE else "passages.json"
    _write_private_bytes(backup_dir / name, data)
    return {"role": role, "name": name, "sha256": _sha256(data), "size_bytes": len(data)}


def _read_manifest(*, manifest_path: Path) -> dict:
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PilotOperationError("backup_unreadable") from error
    if not isinstance(document, dict) or document.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise PilotOperationError("backup_unreadable")
    campaign = document.get("campaign")
    if campaign is not None and not (
        isinstance(campaign, str) and parse_campaign(campaign) == campaign
    ):
        raise PilotOperationError("backup_unreadable")
    files = document.get("files")
    if not isinstance(files, list):
        raise PilotOperationError("backup_unreadable")
    for entry in files:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"role", "name", "sha256", "size_bytes"}
            or entry["role"] not in {CATALOG_ROLE, PASSAGES_ROLE}
            or not isinstance(entry["name"], str)
            or "/" in entry["name"]
            or not _HASH.fullmatch(str(entry["sha256"]))
            or isinstance(entry["size_bytes"], bool)
            or not isinstance(entry["size_bytes"], int)
        ):
            raise PilotOperationError("backup_unreadable")
    config_files = document.get("config_files", [])
    if not isinstance(config_files, list):
        raise PilotOperationError("backup_unreadable")
    for entry in config_files:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"name", "sha256", "size_bytes"}
            or not isinstance(entry["name"], str)
            or not entry["name"].startswith("config/")
            or "/" in entry["name"][len("config/") :]
            or not _HASH.fullmatch(str(entry["sha256"]))
        ):
            raise PilotOperationError("backup_unreadable")
    return document


def _verified_bytes(path: Path, entry: dict) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PilotOperationError("backup_corrupt") from error
    if len(data) != entry.get("size_bytes") or _sha256(data) != entry.get("sha256"):
        raise PilotOperationError("backup_corrupt")
    return data


def _corpus_shape_valid(payloads: Mapping[str, bytes]) -> bool:
    try:
        catalog = json.loads(payloads[CATALOG_ROLE].decode("utf-8"))
        passages = json.loads(payloads[PASSAGES_ROLE].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(catalog, dict) or not isinstance(catalog.get("sources"), list):
        return False
    if not isinstance(passages, dict) or not isinstance(passages.get("passages"), list):
        return False
    source_ids = {
        source.get("id") for source in catalog["sources"] if isinstance(source, dict)
    }
    return all(
        isinstance(passage, dict) and passage.get("source_id") in source_ids
        for passage in passages["passages"]
    )


def _read_prior(path: Path) -> _PriorTarget:
    """Read a canonical target and its mode/owner before replacing it."""

    try:
        metadata = path.stat()
    except FileNotFoundError:
        return _PriorTarget()
    except OSError as error:
        raise PilotOperationError("target_unreadable") from error
    try:
        content = path.read_bytes()
    except OSError as error:
        raise PilotOperationError("target_unreadable") from error
    return _PriorTarget(
        content=content,
        mode=stat.S_IMODE(metadata.st_mode),
        uid=metadata.st_uid,
        gid=metadata.st_gid,
    )


def _restore_prior(path: Path, prior: _PriorTarget) -> None:
    """Best-effort rollback of one canonical target, including its prior mode."""

    try:
        if prior.content is None:
            path.unlink()
        else:
            _write_atomically(path, prior.content, mode=prior.mode, uid=prior.uid, gid=prior.gid)
    except OSError:
        return


def _write_canonical(path: Path, data: bytes, prior: _PriorTarget) -> None:
    """Write a canonical artifact readable by the service account.

    The corpus is public official text: new and restored targets are mode 0644 so the
    ``User=manijero`` process can read them even when the restore ran as root. The prior
    owner is preserved where the platform and process permit it.
    """

    _write_atomically(
        path,
        data,
        mode=CANONICAL_CORPUS_MODE,
        uid=prior.uid,
        gid=prior.gid,
    )


def _service_readable(path: Path) -> bool:
    """Whether every account can read the file, as the service account must."""

    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    required = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    return mode & required == required


def _write_atomically(
    path: Path,
    data: bytes,
    *,
    mode: int = CANONICAL_CORPUS_MODE,
    uid: int | None = None,
    gid: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if uid is not None and gid is not None and hasattr(os, "chown"):
            try:
                os.chown(temporary, uid, gid)
            except OSError:
                pass
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _chmod_private_dir(path: Path) -> None:
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _write_private_bytes(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _contains_secret_marker(payload: bytes) -> bool:
    lowered = payload.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _write_private_json(path: Path, document: dict) -> None:
    data = json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _existing_clients(path: Path) -> Tuple[ClientPolicy, ...]:
    if not path.exists():
        return ()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PilotOperationError("clients_invalid") from error
    try:
        return validate_clients_document(document)
    except PilotConfigError as error:
        raise PilotOperationError(error.code) from error


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_acceptable_base_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme == "https" and host:
        return
    if parsed.scheme == "http" and host in {"127.0.0.1", "::1", "localhost"}:
        return
    raise PilotOperationError("base_url_requires_https")
