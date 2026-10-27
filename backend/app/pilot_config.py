"""Explicit runtime configuration for the service profiles.

Two profiles exist:

- ``development`` is the local workflow (`./scripts/init.sh --backend`). It keeps the
  current unauthenticated single-user behavior.
- `pilot` is the only profile the hosted launcher serves. It refuses to run without an
  explicit four-digit campaign and a client-credentials file, and it enables
  authentication, per-client rate limiting, and operational request logging.

Client credentials are stored as SHA-256 digests so the file never contains a usable
token. Error codes are fixed strings: no configuration value, path fragment, or token is
ever included in an exception message.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from typing import Mapping, Tuple

DEVELOPMENT_PROFILE = "development"
PILOT_PROFILE = "pilot"
PROFILES = (DEVELOPMENT_PROFILE, PILOT_PROFILE)

CLIENTS_SCHEMA_VERSION = "pilot-clients-v1"
MIN_REQUEST_BYTES = 1024
DEFAULT_MAX_REQUEST_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MIN_REQUESTS_PER_MINUTE = 1
MAX_REQUESTS_PER_MINUTE = 600
MAX_CLIENTS = 200

_CAMPAIGN = re.compile(r"\d{4}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_CLIENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class PilotConfigError(Exception):
    """A fail-closed configuration problem named by a fixed code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ClientPolicy:
    """One authenticated pilot client and its per-minute request allowance."""

    client_id: str
    token_sha256: str
    requests_per_minute: int


@dataclass(frozen=True)
class PilotConfig:
    """Validated configuration for one service process."""

    profile: str
    active_campaign: str | None
    max_request_bytes: int
    clients: Tuple[ClientPolicy, ...] = ()

    @property
    def pilot(self) -> bool:
        return self.profile == PILOT_PROFILE

    @property
    def authentication_required(self) -> bool:
        """Only the pilot profile authenticates callers."""

        return self.pilot

    @property
    def operational_logging(self) -> bool:
        """Only the pilot profile emits the reviewed operational request line."""

        return self.pilot

    def client_for_token(self, token: str | None) -> ClientPolicy | None:
        """Return the client whose digest matches ``token``, comparing in constant time."""

        if not token:
            return None
        digest = token_sha256(token)
        for client in self.clients:
            if _constant_time_equal(digest, client.token_sha256):
                return client
        return None


def token_sha256(token: str) -> str:
    """Return the hex SHA-256 digest stored for a bearer token."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_campaign(value: str | None) -> str | None:
    """Return a four-digit campaign or ``None``; never infer one from the date."""

    if value is None:
        return None
    candidate = value.strip()
    return candidate if _CAMPAIGN.fullmatch(candidate) else None


def load_config(env: Mapping[str, str] | None = None) -> PilotConfig:
    """Build the validated configuration for the current process.

    Raises :class:`PilotConfigError` with a fixed code. The development profile never
    reads credentials, so a missing campaign there stays a per-request ``503``.
    """

    source = os.environ if env is None else env
    profile = _read_profile(source)
    max_request_bytes = _read_max_request_bytes(source)
    if profile == DEVELOPMENT_PROFILE:
        return PilotConfig(
            profile=profile,
            active_campaign=parse_campaign(source.get("MANIJERO_ACTIVE_CAMPAIGN")),
            max_request_bytes=max_request_bytes,
        )

    campaign = parse_campaign(source.get("MANIJERO_ACTIVE_CAMPAIGN"))
    if campaign is None:
        raise PilotConfigError("campaign_invalid")
    clients_path = (source.get("MANIJERO_PILOT_CLIENTS_FILE") or "").strip()
    if not clients_path:
        raise PilotConfigError("clients_missing")
    clients = load_clients_file(Path(clients_path))
    return PilotConfig(
        profile=profile,
        active_campaign=campaign,
        max_request_bytes=max_request_bytes,
        clients=clients,
    )


def load_clients_file(path: Path) -> Tuple[ClientPolicy, ...]:
    """Read and validate the operator-managed client-credentials file."""

    if os.name == "posix":
        try:
            mode = path.stat().st_mode
        except OSError as error:
            raise PilotConfigError("clients_unreadable") from error
        if mode & 0o077:
            raise PilotConfigError("clients_permissions")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PilotConfigError("clients_unreadable") from error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PilotConfigError("clients_invalid") from error
    return validate_clients_document(document)


def validate_clients_document(document: object) -> Tuple[ClientPolicy, ...]:
    """Validate the parsed client-credentials document without echoing its values."""

    if not isinstance(document, dict):
        raise PilotConfigError("clients_invalid")
    if set(document) != {"schema_version", "clients"}:
        raise PilotConfigError("clients_invalid")
    if document["schema_version"] != CLIENTS_SCHEMA_VERSION:
        raise PilotConfigError("clients_invalid")
    records = document["clients"]
    if not isinstance(records, list) or len(records) > MAX_CLIENTS:
        raise PilotConfigError("clients_invalid")

    clients = []
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "client_id",
            "token_sha256",
            "requests_per_minute",
            "enabled",
        }:
            raise PilotConfigError("clients_invalid")
        client_id = record["client_id"]
        digest = record["token_sha256"]
        limit = record["requests_per_minute"]
        enabled = record["enabled"]
        if not isinstance(client_id, str) or not _CLIENT_ID.fullmatch(client_id):
            raise PilotConfigError("clients_invalid")
        if client_id in seen:
            raise PilotConfigError("clients_invalid")
        seen.add(client_id)
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise PilotConfigError("clients_invalid")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not MIN_REQUESTS_PER_MINUTE <= limit <= MAX_REQUESTS_PER_MINUTE
        ):
            raise PilotConfigError("clients_invalid")
        if not isinstance(enabled, bool):
            raise PilotConfigError("clients_invalid")
        if enabled:
            clients.append(ClientPolicy(client_id, digest, limit))

    if not clients:
        raise PilotConfigError("clients_empty")
    return tuple(clients)


def serialized_clients_document(clients: Tuple[ClientPolicy, ...]) -> dict:
    """Serialize enabled clients back to the on-disk shape, digests only."""

    return {
        "schema_version": CLIENTS_SCHEMA_VERSION,
        "clients": [
            {
                "client_id": client.client_id,
                "token_sha256": client.token_sha256,
                "requests_per_minute": client.requests_per_minute,
                "enabled": True,
            }
            for client in clients
        ],
    }


def _read_profile(env: Mapping[str, str]) -> str:
    value = (env.get("MANIJERO_DEPLOYMENT_PROFILE") or "").strip()
    if not value:
        return DEVELOPMENT_PROFILE
    if value not in PROFILES:
        raise PilotConfigError("profile_invalid")
    return value


def _read_max_request_bytes(env: Mapping[str, str]) -> int:
    raw = (env.get("MANIJERO_MAX_REQUEST_BYTES") or "").strip()
    if not raw:
        return DEFAULT_MAX_REQUEST_BYTES
    try:
        value = int(raw)
    except ValueError as error:
        raise PilotConfigError("request_limit_invalid") from error
    if not MIN_REQUEST_BYTES <= value <= MAX_REQUEST_BYTES:
        raise PilotConfigError("request_limit_invalid")
    return value


def _constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
