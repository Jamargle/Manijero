"""Minimal operational logging for the hosted pilot profile.

The only record this service writes is one JSON line per HTTP request with the method,
the route path (never the query string or headers), the status code, the duration, and
the request gate that produced the response. Question text, land context, notes, client
identifiers, tokens, and response bodies are never fields of an operational record.

The log line is written to stdout so the process manager owns collection. Application
code must not add question or land values to these records.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from typing import IO

from app.pilot_config import PilotConfig

LOGGER_NAME = "manijero.operational"
_PRIMITIVES = (str, int, float, bool)


def configure_operational_logging(stream: IO[str] | None = None) -> None:
    """Send the operational logger to stdout once, without duplicating handlers."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def operational_log(event: str, **fields: object) -> None:
    """Write one structured operational record with primitive fields only."""

    record: dict[str, object] = {
        "event": event,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    for name, value in fields.items():
        if isinstance(value, _PRIMITIVES):
            record[name] = value
    logging.getLogger(LOGGER_NAME).info(
        json.dumps(record, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    )


def log_request(
    config: PilotConfig,
    *,
    method: str,
    path: str,
    status: int,
    duration_ms: int,
    gate: str,
) -> None:
    """Record one reviewed request-metadata line for the pilot profile only."""

    if not config.operational_logging:
        return
    operational_log(
        "request",
        method=method[:16],
        path=path.split("?", 1)[0][:128],
        status=status,
        duration_ms=duration_ms,
        gate=gate,
    )
