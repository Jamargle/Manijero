"""Privacy-safe per-question trace of the answer pipeline, for local debugging only.

Tracing is off unless ``MANIJERO_ANSWER_TRACE=on``. One JSON file per ``/ask`` that reaches
the route is written to the fixed, git-ignored ``build/answer-traces`` folder (mode 0700,
files 0600, atomic rename) and deleted after seven days. Question, answer, and draft text
are recorded only when ``MANIJERO_DEPLOYMENT_PROFILE`` is set to exactly ``development``; every other
profile gets ids, scores, timings, and verification codes. A trace never changes an answer
and never fails a request: every hook here swallows its own errors.

Land values, client ids, tokens, IP addresses, the retention flag, ``GroundingIssue.detail``
strings, and passage excerpts are never recorded. Standard library only.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app.pilot_logging import operational_log

SETTING_ENV = "MANIJERO_ANSWER_TRACE"
PROFILE_ENV = "MANIJERO_DEPLOYMENT_PROFILE"
SCHEMA_VERSION = "answer-trace-v1"
LOCAL_PROFILES = frozenset({"development"})
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FOLDER = REPOSITORY_ROOT / "build" / "answer-traces"
RETENTION = timedelta(days=7)
MAX_LEXICAL = 20
MAX_DRAFT_CHARS = 4000
_NAME = re.compile(r"^(\d{8}T\d{6}Z)-([0-9a-f]{32})\.json$")
_NAME_TIME = "%Y%m%dT%H%M%SZ"

# Key paths of a metadata-only trace ("[]" marks a list of objects; a list of scalars and
# every other leaf is the path itself). Anything outside this set is a text or unknown key.
METADATA_KEYS = frozenset(
    {
        "schema", "trace_id", "created_at", "profile", "text_included", "total_ms",
        "retrieval", "retrieval.mode", "retrieval.k", "retrieval.search_calls", "retrieval.duration_ms",
        "retrieval.lexical", "retrieval.lexical[].passage_id", "retrieval.lexical[].score",
        "retrieval.lexical[].rank",
        "retrieval.vector", "retrieval.vector.used", "retrieval.vector.fallback_code",
        "retrieval.vector.matches", "retrieval.vector.matches[].passage_id",
        "retrieval.vector.matches[].similarity",
        "retrieval.candidates", "retrieval.candidates[].passage_id", "retrieval.candidates[].source_id",
        "retrieval.candidates[].score", "retrieval.candidates[].rank",
        "drafting", "drafting.provider", "drafting.outcome", "drafting.status",
        "drafting.cited_markers", "drafting.duration_ms",
        "verification", "verification.ok", "verification.issues", "verification.duration_ms",
        "verification.claims", "verification.claims[].index", "verification.claims[].markers",
        "verification.claims[].ok", "verification.claims[].issues",
        "outcome", "outcome.status", "outcome.abstention_reason", "outcome.generation_reason",
        "outcome.cited_passage_ids", "outcome.land_scope", "outcome.land_choice_count",
    }
)
TEXT_KEYS = frozenset(
    {"question", "answer", "drafting.draft_text", "drafting.draft_truncated"}
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_setting(value: Optional[str]) -> Tuple[bool, Optional[str]]:
    """``(on, reason)``: only the exact word ``on`` enables; a stray value is flagged."""

    if value is None or value in ("", "off"):
        return False, None
    if value == "on":
        return True, None
    return False, "value_invalid"


def text_allowed(profile: str, environ: Any) -> bool:
    """Text may be traced only for a profile the allowlist names exactly (fail closed).

    The profile must also be set explicitly: an unset profile resolves to ``development``
    elsewhere, but a service started without one is never trusted to be local.
    """

    stated = (environ.get(PROFILE_ENV) or "").strip()
    return isinstance(profile, str) and profile in LOCAL_PROFILES and stated == profile


class TraceError(Exception):
    """A trace step failed; ``code`` is a fixed value safe to log."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _file_name(moment: datetime, trace_id: str) -> str:
    return "{}-{}.json".format(moment.astimezone(timezone.utc).strftime(_NAME_TIME), trace_id)


class TraceWriter:
    """Atomic 0600 writer into one folder, plus the seven-day purge."""

    def __init__(self, folder: Path = DEFAULT_FOLDER, clock: Clock = utc_now) -> None:
        self.folder = Path(folder)
        self._clock = clock

    def purge(self) -> None:
        """Delete trace files seven days old or older; foreign names stay; never raises."""

        try:
            if self.folder.is_symlink() or not self.folder.is_dir():
                return
            cutoff = self._clock() - RETENTION
            for entry in os.listdir(self.folder):
                match = _NAME.match(entry)
                if match is None:
                    continue
                try:
                    stamp = datetime.strptime(match.group(1), _NAME_TIME).replace(tzinfo=timezone.utc)
                    if stamp <= cutoff:
                        os.unlink(self.folder / entry)
                except (ValueError, OSError):
                    continue
        except Exception:  # noqa: BLE001 - a failed purge never stops anything
            return

    def write(self, document: Dict[str, Any]) -> None:
        """Purge, then write ``document``; raises :class:`TraceError` with a fixed code."""

        try:
            payload = json.dumps(
                document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            raise TraceError("serialize_failed")
        if self.folder.is_symlink():
            raise TraceError("folder_symlink")
        temporary: Optional[str] = None
        try:
            self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.folder.is_symlink():
                raise TraceError("folder_symlink")
            os.chmod(self.folder, 0o700)
            self.purge()
            descriptor, temporary = tempfile.mkstemp(dir=self.folder, prefix=".tmp-", suffix=".tmp")
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(payload)
            os.replace(temporary, self.folder / _file_name(self._clock(), document["trace_id"]))
            temporary = None
        except TraceError:
            raise
        except Exception:  # noqa: BLE001
            raise TraceError("write_failed")
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


@dataclass
class TraceCollector:
    """Everything one request notes; only codes, ids, numbers, and (local) text."""

    started: float = field(default_factory=time.monotonic)
    mode: Optional[str] = None
    k: Optional[int] = None
    search_calls: int = 0
    retrieval_seconds: float = 0.0
    lexical: List[Tuple[str, float]] = field(default_factory=list)
    vector: Optional[Dict[str, Any]] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    drafting: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    outcome: Dict[str, Any] = field(default_factory=dict)


_ACTIVE: ContextVar[Optional[TraceCollector]] = ContextVar("answer_trace_collector", default=None)


def _safe(function: Callable[..., None]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except Exception:  # noqa: BLE001 - a hook must never affect the answer
            return None

    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


@_safe
def note_mode(mode: str, k: int) -> None:
    collector = _ACTIVE.get()
    if collector is not None:
        collector.mode = str(mode)
        collector.k = int(k)


@_safe
def note_search_begin() -> Optional[float]:
    collector = _ACTIVE.get()
    if collector is None:
        return None
    collector.search_calls += 1
    collector.lexical = []
    collector.vector = None
    collector.candidates = []
    return time.monotonic()


@_safe
def note_lexical(ranked: Iterable[Tuple[str, float]]) -> None:
    collector = _ACTIVE.get()
    if collector is not None:
        collector.lexical = [(str(i), float(s)) for i, s in ranked]


@_safe
def note_vector(used: bool, fallback_code: Optional[str], matches: Iterable[Tuple[str, float]]) -> None:
    collector = _ACTIVE.get()
    if collector is not None:
        collector.vector = {
            "used": bool(used),
            "fallback_code": fallback_code,
            "matches": [
                {"passage_id": str(i), "similarity": round(float(s), 6)} for i, s in matches
            ],
        }


@_safe
def note_search_end(started: Optional[float], candidates: Sequence[Any]) -> None:
    collector = _ACTIVE.get()
    if collector is None:
        return
    collector.candidates = [
        {
            "passage_id": c.passage_id,
            "source_id": c.source_id,
            "score": round(float(c.score), 6),
            "rank": int(c.rank),
        }
        for c in candidates
    ]
    if started is not None:
        collector.retrieval_seconds += time.monotonic() - started


@_safe
def note_provider(provider: str, outcome: str) -> None:
    collector = _ACTIVE.get()
    if collector is not None:
        collector.drafting = dict(collector.drafting or {}, provider=str(provider), outcome=str(outcome))


@_safe
def note_draft(draft: Any, started: Optional[float]) -> None:
    collector = _ACTIVE.get()
    if collector is None:
        return
    drafting = dict(collector.drafting or {})
    if draft is not None:
        drafting["status"] = str(draft.status)
        drafting["cited_markers"] = [int(m) for m in draft.source_markers]
        drafting["_text"] = str(draft.answer)
    if started is not None:
        drafting["duration_ms"] = _ms(time.monotonic() - started)
    collector.drafting = drafting


@_safe
def note_verification(report: Any, started: Optional[float]) -> None:
    collector = _ACTIVE.get()
    if collector is None:
        return
    collector.verification = {
        "ok": bool(report.ok),
        "issues": [str(issue.code) for issue in report.issues],
        "claims": [
            {
                "index": index,
                "markers": [int(m) for m in claim.markers],
                "ok": bool(claim.ok),
                "issues": [str(issue.code) for issue in claim.issues],
            }
            for index, claim in enumerate(report.claims, start=1)
        ],
        "duration_ms": _ms(time.monotonic() - started) if started is not None else None,
    }


@_safe
def note_outcome(
    *,
    abstention_reason: Optional[str] = None,
    generation_reason: Optional[str] = None,
    cited_passage_ids: Sequence[str] = (),
) -> None:
    collector = _ACTIVE.get()
    if collector is not None:
        collector.outcome.update(
            abstention_reason=abstention_reason,
            generation_reason=generation_reason,
            cited_passage_ids=[str(i) for i in cited_passage_ids],
        )


def _ms(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


def build_document(
    collector: TraceCollector,
    *,
    profile: str,
    text_included: bool,
    question: str,
    answer: Optional[str],
    status: str,
    land_scope: str,
    land_choice_count: int,
    moment: datetime,
    trace_id: str,
) -> Dict[str, Any]:
    """The ``answer-trace-v1`` document; text keys are added only when ``text_included``."""

    document: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "trace_id": trace_id,
        "created_at": moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": profile,
        "text_included": text_included,
    }
    if text_included:
        document["question"] = question
        document["answer"] = answer
    document["retrieval"] = _retrieval(collector)
    document["drafting"] = _drafting(collector, text_included)
    document["verification"] = collector.verification
    outcome = collector.outcome
    document["outcome"] = {
        "status": status,
        "abstention_reason": outcome.get("abstention_reason"),
        "generation_reason": outcome.get("generation_reason"),
        "cited_passage_ids": outcome.get("cited_passage_ids", []),
        "land_scope": land_scope,
        "land_choice_count": land_choice_count,
    }
    document["total_ms"] = _ms(time.monotonic() - collector.started)
    return document


def _retrieval(collector: TraceCollector) -> Optional[Dict[str, Any]]:
    if collector.mode is None:
        return None
    return {
        "mode": collector.mode,
        "k": collector.k,
        "search_calls": collector.search_calls,
        "duration_ms": _ms(collector.retrieval_seconds),
        "lexical": [
            {"passage_id": passage_id, "score": round(score, 6), "rank": rank}
            for rank, (passage_id, score) in enumerate(collector.lexical[:MAX_LEXICAL], start=1)
        ],
        "vector": collector.vector,
        "candidates": collector.candidates,
    }


def _drafting(collector: TraceCollector, text_included: bool) -> Optional[Dict[str, Any]]:
    if collector.drafting is None:
        return None
    drafting = dict(collector.drafting)
    text = drafting.pop("_text", None)
    result: Dict[str, Any] = {
        "provider": drafting.get("provider"),
        "outcome": drafting.get("outcome"),
        "status": drafting.get("status"),
        "cited_markers": drafting.get("cited_markers", []),
        "duration_ms": drafting.get("duration_ms"),
    }
    if text_included:
        result["draft_text"] = None if text is None else text[:MAX_DRAFT_CHARS]
        result["draft_truncated"] = text is not None and len(text) > MAX_DRAFT_CHARS
    return result


def key_paths(document: Any, prefix: str = "") -> frozenset:
    """Every key path of ``document`` in the notation of :data:`METADATA_KEYS`."""

    paths = set()
    if isinstance(document, dict):
        for key, value in document.items():
            path = "{}.{}".format(prefix, key) if prefix else key
            paths.add(path)
            paths |= key_paths(value, path)
    elif isinstance(document, list):
        for item in document:
            if isinstance(item, (dict, list)):
                paths |= key_paths(item, prefix + "[]")
    return frozenset(paths)


@dataclass
class AnswerTrace:
    """The startup-resolved trace configuration held on ``app.state``."""

    enabled: bool
    profile: str
    text_included: bool
    writer: TraceWriter
    reason: Optional[str] = None
    clock: Clock = utc_now

    def startup(self) -> None:
        """Purge old files (even when off) and log one fixed-field record."""

        self.writer.purge()
        fields: Dict[str, object] = {
            "state": "on" if self.enabled else "off",
            "text": "included" if self.text_included else "excluded",
        }
        if self.reason:
            fields["reason"] = self.reason
        operational_log("answer_trace", **fields)

    def open(self) -> "TraceSession":
        return TraceSession(self if self.enabled else None)


def load_answer_trace(
    environ: Any,
    profile: str,
    folder: Path = DEFAULT_FOLDER,
    clock: Clock = utc_now,
) -> AnswerTrace:
    enabled, reason = parse_setting(environ.get(SETTING_ENV))
    return AnswerTrace(
        enabled=enabled,
        profile=profile,
        text_included=enabled and text_allowed(profile, environ),
        writer=TraceWriter(folder, clock),
        reason=reason,
        clock=clock,
    )


class TraceSession:
    """One request's collector; ``finish`` writes the file and never raises."""

    def __init__(self, trace: Optional[AnswerTrace]) -> None:
        self._trace = trace
        self._collector: Optional[TraceCollector] = None
        self._token: Optional[Token] = None
        if trace is not None:
            try:
                self._collector = TraceCollector()
                self._token = _ACTIVE.set(self._collector)
            except Exception:  # noqa: BLE001
                self._collector = None

    def release(self) -> None:
        if self._token is not None:
            try:
                _ACTIVE.reset(self._token)
            except Exception:  # noqa: BLE001
                pass
            self._token = None

    def finish(
        self,
        *,
        question: str,
        land_scope: str,
        response: Optional[Dict[str, Any]],
    ) -> None:
        if self._trace is None or self._collector is None:
            return
        try:
            trace = self._trace
            if response is None:
                status, answer, choices = "unavailable", None, 0
            else:
                status = str(response.get("status"))
                answer = response.get("answer")
                choices = len(response.get("land_ids_to_choose") or [])
            moment = trace.clock()
            document = build_document(
                self._collector,
                profile=trace.profile,
                text_included=trace.text_included,
                question=question,
                answer=answer,
                status=status,
                land_scope=land_scope,
                land_choice_count=choices,
                moment=moment,
                trace_id=uuid.uuid4().hex,
            )
            trace.writer.write(document)
        except TraceError as error:
            operational_log("answer_trace_skipped", reason=error.code)
        except Exception:  # noqa: BLE001
            operational_log("answer_trace_skipped", reason="serialize_failed")
