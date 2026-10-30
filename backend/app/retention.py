"""Opt-in, short-lived product-improvement retention of redacted question/answer text.

Retention is off unless the operator sets ``MANIJERO_RETENTION_DB`` to a SQLite file in an
owner-only directory outside the repository, **and** the request explicitly carries
``retain_for_improvement: true`` for that one question. Without both, nothing is written.

A retained record holds exactly: the redacted question, the redacted final answer, the
answer state, the UTC creation date, and its expiry date. It never holds the land context,
a land id, a municipality, a client id, a token, an IP address, a device identifier, or a
precise timestamp (dates only, so a record cannot be joined with request-metadata lines).

Every record is deleted no later than 30 days after creation: ``expires_on`` is the
creation date plus ``RETENTION_DAYS - 1`` days, and records whose ``expires_on`` is today or
earlier are purged before every write, by the operator's daily purge command, and are never
returned by an export. Any failure on this path is swallowed by the caller: the answer the
person sees never depends on retention, and an unretained question is the safe outcome.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping, Tuple

from app.redaction import RedactionError, land_context_values, redact_text

RETENTION_DAYS = 30
RETENTION_ENV = "MANIJERO_RETENTION_DB"
RETAINED_STATUSES = frozenset({"answered", "abstained"})
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = """
CREATE TABLE IF NOT EXISTS retained_qa (
    created_on TEXT NOT NULL,
    expires_on TEXT NOT NULL,
    answer_status TEXT NOT NULL,
    question_redacted TEXT NOT NULL,
    answer_redacted TEXT NOT NULL
)
"""


class RetentionError(Exception):
    """A retention configuration or storage problem named by a fixed code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RetainedRecord:
    """One retained, redacted question/answer pair. No identifier of any person or land."""

    created_on: date
    expires_on: date
    answer_status: str
    question_redacted: str
    answer_redacted: str


@dataclass(frozen=True)
class RetentionStatus:
    """Counts only: never record text."""

    records: int
    overdue: int
    oldest_created_on: date | None


def expiry_for(created_on: date) -> date:
    """Return the date on which a record created on ``created_on`` is purged."""

    return created_on + timedelta(days=RETENTION_DAYS - 1)


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


class RetentionStore:
    """An owner-only SQLite file of redacted, expiring question/answer pairs."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @classmethod
    def open(cls, path: Path) -> "RetentionStore":
        """Validate the location and permissions, then create the schema if needed."""

        resolved = Path(path).expanduser().resolve()
        if resolved == _REPOSITORY_ROOT or _REPOSITORY_ROOT in resolved.parents:
            raise RetentionError("retention_store_inside_repository")
        parent = resolved.parent
        if not parent.is_dir():
            raise RetentionError("retention_store_directory_missing")
        if os.name == "posix":
            if parent.stat().st_mode & 0o077:
                raise RetentionError("retention_store_permissions")
            if resolved.exists() and resolved.stat().st_mode & 0o077:
                raise RetentionError("retention_store_permissions")
        if not resolved.exists():
            try:
                descriptor = os.open(resolved, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            except OSError as error:
                raise RetentionError("retention_store_unwritable") from error
            else:
                os.close(descriptor)
        store = cls(resolved)
        try:
            with store._connect() as connection:
                connection.execute(_SCHEMA)
        except sqlite3.Error as error:
            raise RetentionError("retention_store_unreadable") from error
        return store

    def retain(self, record: RetainedRecord, *, today: date) -> None:
        """Purge expired records, then write ``record`` in the same transaction."""

        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
                connection.execute("DELETE FROM retained_qa WHERE expires_on <= ?", (today.isoformat(),))
                connection.execute(
                    "INSERT INTO retained_qa (created_on, expires_on, answer_status,"
                    " question_redacted, answer_redacted) VALUES (?, ?, ?, ?, ?)",
                    (
                        record.created_on.isoformat(),
                        record.expires_on.isoformat(),
                        record.answer_status,
                        record.question_redacted,
                        record.answer_redacted,
                    ),
                )
        except sqlite3.Error as error:
            raise RetentionError("retention_write_failed") from error

    def purge_expired(self, *, today: date) -> int:
        """Delete every record whose expiry date is today or earlier; return the count."""

        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
                cursor = connection.execute(
                    "DELETE FROM retained_qa WHERE expires_on <= ?", (today.isoformat(),)
                )
                return cursor.rowcount
        except sqlite3.Error as error:
            raise RetentionError("retention_purge_failed") from error

    def delete_all(self) -> int:
        """Delete every retained record (the owner's whole-store deletion path)."""

        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
                return connection.execute("DELETE FROM retained_qa").rowcount
        except sqlite3.Error as error:
            raise RetentionError("retention_delete_failed") from error

    def status(self, *, today: date) -> RetentionStatus:
        """Report counts and overdue records without reading any text."""

        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
                total, oldest = connection.execute(
                    "SELECT COUNT(*), MIN(created_on) FROM retained_qa"
                ).fetchone()
                overdue = connection.execute(
                    "SELECT COUNT(*) FROM retained_qa WHERE expires_on <= ?", (today.isoformat(),)
                ).fetchone()[0]
        except sqlite3.Error as error:
            raise RetentionError("retention_store_unreadable") from error
        return RetentionStatus(
            records=int(total),
            overdue=int(overdue),
            oldest_created_on=date.fromisoformat(oldest) if oldest else None,
        )

    def unexpired_records(self, *, today: date) -> Tuple[RetainedRecord, ...]:
        """Return the records still inside their retention window (owner access only)."""

        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
                rows = connection.execute(
                    "SELECT created_on, expires_on, answer_status, question_redacted,"
                    " answer_redacted FROM retained_qa WHERE expires_on > ? ORDER BY created_on",
                    (today.isoformat(),),
                ).fetchall()
        except sqlite3.Error as error:
            raise RetentionError("retention_store_unreadable") from error
        return tuple(
            RetainedRecord(
                created_on=date.fromisoformat(row[0]),
                expires_on=date.fromisoformat(row[1]),
                answer_status=row[2],
                question_redacted=row[3],
                answer_redacted=row[4],
            )
            for row in rows
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """One committed (or rolled-back) transaction on a connection that is always closed."""

        if not self.path.is_file():
            raise sqlite3.OperationalError("retention store missing")
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def load_retention_store(env: Mapping[str, str] | None = None) -> RetentionStore | None:
    """Return the configured store, ``None`` when retention is not configured.

    Raises :class:`RetentionError` for a configured but unsafe or unusable location.
    """

    source = os.environ if env is None else env
    raw = (source.get(RETENTION_ENV) or "").strip()
    if not raw:
        return None
    return RetentionStore.open(Path(raw))


def build_record(
    *,
    question: str,
    land_context: Mapping[str, Any],
    response: Mapping[str, Any],
    today: date,
) -> RetainedRecord | None:
    """Build the redacted record for one opted-in question, or ``None`` to retain nothing.

    Only a final answer (answered or abstained) is retained; a clarification has no answer
    yet. The land context is used only to redact its own values out of the text and is
    never stored. Raises :class:`RedactionError` if redaction cannot be applied.
    """

    status = response.get("status")
    answer = response.get("answer")
    if status not in RETAINED_STATUSES or not isinstance(answer, str) or not answer.strip():
        return None
    values = land_context_values(dict(land_context))
    return RetainedRecord(
        created_on=today,
        expires_on=expiry_for(today),
        answer_status=str(status),
        question_redacted=redact_text(question, values),
        answer_redacted=redact_text(answer, values),
    )


def retain_if_opted_in(
    store: RetentionStore | None,
    *,
    opted_in: bool,
    question: str,
    land_context: Mapping[str, Any],
    response: Mapping[str, Any],
    today: date | None = None,
) -> str:
    """Retain one redacted pair only when opted in and configured; return an outcome code.

    Outcome codes are fixed strings (``not_opted_in``, ``not_configured``, ``not_final``,
    ``retained``, ``redaction_failed``, ``store_failed``). This function never raises and
    never returns or logs text, so the answer path cannot be affected by retention.
    """

    if opted_in is not True:
        return "not_opted_in"
    if store is None:
        return "not_configured"
    day = today or today_utc()
    try:
        record = build_record(question=question, land_context=land_context, response=response, today=day)
    except (RedactionError, TypeError, ValueError):
        return "redaction_failed"
    except Exception:  # noqa: BLE001 - retention must never break the answer path.
        return "redaction_failed"
    if record is None:
        return "not_final"
    try:
        store.retain(record, today=day)
    except Exception:  # noqa: BLE001 - includes RetentionError and unexpected I/O errors.
        return "store_failed"
    return "retained"


EXPORT_SCHEMA_VERSION = "retained-qa-export-v1"


def export_records(store: RetentionStore, destination: Path, *, today: date) -> int:
    """Write the unexpired redacted records to an owner-only file outside the repository.

    The export is for the owner's product-improvement review only. It refuses an existing
    file and any location inside the repository, is created ``0600``, and carries no
    identifier. An exported copy is outside the automatic purge: the owner must delete it
    within the same 30-day window (the runbook states this).
    """

    target = Path(destination).expanduser().resolve()
    if target == _REPOSITORY_ROOT or _REPOSITORY_ROOT in target.parents:
        raise RetentionError("export_inside_repository")
    records = store.unexpired_records(today=today)
    document = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_on": today.isoformat(),
        "records": [
            {
                "created_on": record.created_on.isoformat(),
                "expires_on": record.expires_on.isoformat(),
                "answer_status": record.answer_status,
                "question_redacted": record.question_redacted,
                "answer_redacted": record.answer_redacted,
            }
            for record in records
        ],
    }
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RetentionError("export_exists") from error
    except OSError as error:
        raise RetentionError("export_unwritable") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return len(records)
