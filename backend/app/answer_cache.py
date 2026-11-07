"""In-memory reuse of verified answers and abstentions for a repeated question.

A hit skips a slow model draft. The cache lives in one process, is empty at every start,
and never writes to disk, logs, or metrics: it holds only a SHA-256 digest of the key and
the response (plus the cited reviewed passages needed to verify it again). The key is the
question normalized for case, accents, and whitespace, the land context, the knowledge
identity, and the model identity; there is no fuzzy matching.

An entry lives until the knowledge or model identity changes (the whole cache is then
emptied) and for at most 24 hours. Every hit re-runs :func:`app.generation.verify_draft`
on the stored draft and cited passages (or re-checks the code-owned abstention shape);
an entry that no longer verifies is discarded whole. Generation errors and every
transient model outcome are never stored. Standard library plus ``app`` only; every
hook swallows its own errors like :mod:`app.answer_trace`.
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import copy
import hashlib
import json
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from app import health_metrics
from app.abstention import ABSTENTION_MESSAGES, Abstention, to_abstention_response
from app.generation import (
    Answered,
    DraftAnswer,
    _render_claim,
    answer_source,
    normalize_text,
    verify_draft,
)
from app.retrieval import RetrievedPassage

SETTING_ENV = "MANIJERO_ANSWER_CACHE"
TTL_SECONDS = 86_400
MAX_ENTRIES = 1_000

HIT = "hit"
MISS = "miss"
EXPIRED = "expired"
DISCARDED = "discarded"

GENERATION_ERROR = "generation_error"
DEGRADED_RETRIEVAL = "retrieval_fallback"

Clock = Callable[[], float]


def parse_setting(value: Optional[str]) -> Tuple[bool, Optional[str]]:
    """``(on, reason)``: unset, empty, and ``on`` enable; ``off`` disables; the rest is flagged."""

    if value is None or value in ("", "on"):
        return True, None
    if value == "off":
        return False, None
    return False, "value_invalid"


def load_answer_cache(environ: Mapping[str, str]) -> Optional["AnswerCache"]:
    """A fresh empty cache when the setting allows it, else ``None``."""

    on, _ = parse_setting(environ.get(SETTING_ENV))
    return AnswerCache() if on else None


def knowledge_identity(release_id: Optional[str], fingerprint: str, campaign: str) -> str:
    """The served release id (or ``repository``) plus the admitted passages and the campaign."""

    return "{}|{}|{}".format(release_id or "repository", fingerprint, campaign)


def model_identity(model_version: str, retrieval_mode: str, k: int, max_claims: int) -> str:
    """The pinned model plus the effective retrieval mode, ``k``, and ``max_claims``."""

    return "{}|{}|{}|{}".format(model_version, retrieval_mode, k, max_claims)


def cache_key(
    question: str, land_context: Mapping[str, Any], knowledge: str, model: str
) -> str:
    """SHA-256 of canonical JSON over the normalized question, lands, and both identities."""

    canonical = json.dumps(
        [normalize_text(question), land_context, knowledge, model],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- Request-scoped model outcomes ---------------------------------------------------------

_OUTCOMES: ContextVar[Optional[List[str]]] = ContextVar("answer_cache_outcomes", default=None)


def note_generation_outcome(outcome: str) -> None:
    """Record one model-draft outcome for the request being captured; never raises."""

    try:
        captured = _OUTCOMES.get()
        if captured is not None:
            captured.append(str(outcome))
    except Exception:  # noqa: BLE001 - a hook must never affect the answer
        return


def note_degraded_retrieval() -> None:
    """Record that the vector side fell back to BM25, so this result is not stored."""

    note_generation_outcome(DEGRADED_RETRIEVAL)


@contextmanager
def capture_generation_outcomes() -> Iterator[List[str]]:
    """Collect the model outcomes noted while drafting one request."""

    captured: List[str] = []
    token = _OUTCOMES.set(captured)
    try:
        yield captured
    finally:
        _OUTCOMES.reset(token)


def outcomes_cacheable(outcomes: Sequence[str], used_outcome: Optional[str]) -> bool:
    """Cacheable only when nothing but the ``*_used`` outcome was noted (no failure, no fallback)."""

    return all(used_outcome is not None and outcome == used_outcome for outcome in outcomes)


# --- Entries ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Entry:
    stored_at: float
    response: Dict[str, Any]
    status: str  # "answered" or "abstained"
    reason: Optional[str] = None  # abstention reason
    generation_reason: Optional[str] = None
    draft: Optional[DraftAnswer] = None
    candidates: Tuple[Tuple[int, RetrievedPassage], ...] = ()


@dataclass(frozen=True)
class CacheHit:
    """A verified stored result; ``response`` is a private deep copy."""

    response: Dict[str, Any]
    status: str
    reason: Optional[str]
    generation_reason: Optional[str]
    cited_passage_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CacheMiss:
    """No usable entry; ``outcome`` is ``miss``, ``expired``, or ``discarded``."""

    outcome: str


class AnswerCache:
    """A bounded, TTL-limited, per-process cache of digests to verified results."""

    def __init__(
        self,
        clock: Clock = time.monotonic,
        ttl_seconds: float = TTL_SECONDS,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: "OrderedDict[str, _Entry]" = OrderedDict()
        self._identity: Optional[Tuple[str, str]] = None

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def sync_identity(self, knowledge: str, model: str) -> None:
        """Empty the cache when the knowledge or model identity differs from the last seen."""

        identity = (knowledge, model)
        with self._lock:
            if self._identity != identity:
                self._entries.clear()
                self._identity = identity

    def lookup(self, key: str) -> "CacheHit | CacheMiss":
        """Return a re-verified copy of the stored result, or why there is none."""

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return self._counted(CacheMiss(MISS))
            if self._clock() - entry.stored_at >= self._ttl:
                del self._entries[key]
                return self._counted(CacheMiss(EXPIRED))
        hit = _recheck(entry)
        if hit is None:
            with self._lock:
                self._entries.pop(key, None)
            return self._counted(CacheMiss(DISCARDED))
        return self._counted(hit)

    @staticmethod
    def _counted(result: "CacheHit | CacheMiss") -> "CacheHit | CacheMiss":
        health_metrics.note_cache_lookup(HIT if isinstance(result, CacheHit) else result.outcome)
        return result

    def store_answered(self, key: str, response: Mapping[str, Any], answered: Answered) -> None:
        """Keep a verified answer with a re-checkable draft and its cited passages."""

        try:
            candidates = tuple(zip(answered.cited_markers, answered.sources))
            draft = DraftAnswer(
                status="answered",
                answer="\n".join(_render_claim(claim) for claim in answered.claims),
                source_markers=tuple(answered.cited_markers),
            )
            self._put(
                key,
                _Entry(
                    stored_at=self._clock(),
                    response=copy.deepcopy(dict(response)),
                    status="answered",
                    draft=draft,
                    candidates=candidates,
                ),
            )
        except Exception:  # noqa: BLE001 - storing is best effort
            return

    def store_abstention(
        self, key: str, response: Mapping[str, Any], abstention: Abstention
    ) -> None:
        """Keep a code-owned abstention unless it is a generation error."""

        if abstention.reason == GENERATION_ERROR:
            return
        try:
            self._put(
                key,
                _Entry(
                    stored_at=self._clock(),
                    response=copy.deepcopy(dict(response)),
                    status="abstained",
                    reason=abstention.reason,
                    generation_reason=abstention.generation_reason,
                ),
            )
        except Exception:  # noqa: BLE001
            return

    def _put(self, key: str, entry: _Entry) -> None:
        with self._lock:
            self._entries.pop(key, None)
            while self._entries and len(self._entries) >= self._max:
                self._entries.popitem(last=False)
            self._entries[key] = entry


def _recheck(entry: _Entry) -> Optional[CacheHit]:
    """Re-verify a stored entry; ``None`` means it must be discarded whole."""

    try:
        if entry.status == "abstained":
            return _recheck_abstention(entry)
        return _recheck_answer(entry)
    except Exception:  # noqa: BLE001 - anything unexpected discards the entry
        return None


def _recheck_answer(entry: _Entry) -> Optional[CacheHit]:
    if entry.draft is None or not entry.candidates:
        return None
    report = verify_draft(entry.draft, entry.candidates)
    if not report.ok:
        return None
    passages = [passage for _, passage in entry.candidates]
    response = entry.response
    if (
        response.get("status") != "answered"
        or response.get("sources") != [answer_source(passage) for passage in passages]
    ):
        return None
    return CacheHit(
        response=copy.deepcopy(response),
        status="answered",
        reason=None,
        generation_reason=None,
        cited_passage_ids=tuple(passage.passage_id for passage in passages),
    )


def _recheck_abstention(entry: _Entry) -> Optional[CacheHit]:
    reason = entry.reason
    if reason not in ABSTENTION_MESSAGES or reason == GENERATION_ERROR:
        return None
    land_scope = entry.response.get("land_scope")
    expected = to_abstention_response(Abstention(reason=reason), land_scope=land_scope)
    if entry.response != expected:
        return None
    return CacheHit(
        response=copy.deepcopy(entry.response),
        status="abstained",
        reason=reason,
        generation_reason=entry.generation_reason,
        cited_passage_ids=(),
    )
