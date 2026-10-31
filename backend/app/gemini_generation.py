"""Gated, replaceable Gemini drafting behind the ``GroundingGenerator`` seam.

This module holds everything a model-drafted answer needs *except* a way to reach a model.
It ships no transport: :class:`GeminiTransport` is a protocol only, ``create_app`` defaults
the transport to ``None``, and ``None`` is itself a gate blocker
(``gemini_transport_unavailable``). Until a separate reviewed change supplies a real
transport, the effective provider is ``extractive`` in every deployment and nothing can
leave the service. Only tests inject a fake transport.

The Gemini path runs only when every gate input passes at startup:

* ``MANIJERO_GENERATION_PROVIDER=gemini`` and ``MANIJERO_GEMINI_MODEL`` equal to the
  reviewed ``gemini_review.model`` (the accepted gate in :mod:`app.privacy_review`, which
  also requires the pilot review);
* the recorded limits file ``backend/config/gemini_provider_limits.json``
  (``gemini-provider-limits-v1``) holds a dated, in-range value for every limit;
* a transport was injected.

When it runs, :class:`GatedGeminiGenerator` sends only the minimal payload (the redacted
question plus the reviewed excerpts of the offered candidates, labelled by candidate
number), strictly parses a structured ``{"status","answer","sources"}`` draft, and returns
it only when the accepted :func:`app.generation.verify_draft` passes. Every other outcome
returns the extractive draft, so a model problem can never become a worse answer than
today's. The lead-in, citation renumbering, sources, and notice stay code-owned in
:func:`app.generation.generate_grounded_answer`, which verifies the returned draft again.

Only the candidates inside the citation window (the first ``max_claims``) are offered, the
same window the land-clarification and unit-conflict pre-checks inspect, so a model draft
cannot cite a candidate those checks never saw.

Logs carry fixed codes only: never question, passage, or draft text. Blocker and outcome
codes never echo an environment or record value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from app.generation import (
    LEAD_IN,
    MAX_ANSWER_CHARS,
    NOTICE,
    DraftAnswer,
    ExtractiveGroundingGenerator,
    normalize_text,
    verify_draft,
)
from app.pilot_logging import operational_log
from app.privacy_review import (
    GEMINI_MODEL_ENV,
    GateResult,
    decide_generation_provider,
    load_review_record,
    minimal_provider_payload,
)
from app.redaction import land_context_values, redact_text
from app.retrieval import RetrievedPassage

LIMITS_SCHEMA_VERSION = "gemini-provider-limits-v1"
DEFAULT_LIMITS_PATH = Path(__file__).resolve().parents[1] / "config" / "gemini_provider_limits.json"
LIMIT_KEYS = frozenset(
    {
        "schema_version",
        "timeout_seconds",
        "max_output_tokens",
        "max_requests_per_minute",
        "max_requests_per_day",
        "cost_reference",
        "recorded_on",
    }
)
TIMEOUT_RANGE = (1, 30)
MAX_OUTPUT_TOKENS_RANGE = (1, 2048)
REQUESTS_PER_MINUTE_RANGE = (1, 600)
REQUESTS_PER_DAY_RANGE = (1, 100000)

PROVIDER_EXTRACTIVE = "extractive"
PROVIDER_GEMINI = "gemini"
DEFAULT_MAX_CLAIMS = 2
MAX_RAW_OUTPUT_CHARS = 8192
DRAFT_KEYS = frozenset({"status", "answer", "sources"})

BLOCKER_TRANSPORT_UNAVAILABLE = "gemini_transport_unavailable"
BLOCKER_UNRESOLVED = "generation_provider_unresolved"

OUTCOME_USED = "gemini_used"
OUTCOME_RATE_LIMITED = "rate_limited"
OUTCOME_REDACTION_FAILED = "redaction_failed"
OUTCOME_PAYLOAD_INVALID = "payload_invalid"
OUTCOME_TRANSPORT_ERROR = "transport_error"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_MALFORMED = "malformed_output"
OUTCOME_ABSTAINED = "provider_abstained"
OUTCOME_REJECTED = "verifier_rejected"
OUTCOMES = (
    OUTCOME_USED,
    OUTCOME_RATE_LIMITED,
    OUTCOME_REDACTION_FAILED,
    OUTCOME_PAYLOAD_INVALID,
    OUTCOME_TRANSPORT_ERROR,
    OUTCOME_TIMEOUT,
    OUTCOME_MALFORMED,
    OUTCOME_ABSTAINED,
    OUTCOME_REJECTED,
)

GEMINI_INSTRUCTION_VERSION = "gemini-draft-v1"
GEMINI_INSTRUCTION = (
    "Eres un asistente que redacta respuestas en español sencillo para personas que "
    "cultivan olivar. Responde solo con la información de los fragmentos numerados que "
    "recibes; no uses ningún otro conocimiento. Termina cada frase con el número del "
    "fragmento que la respalda entre corchetes, por ejemplo [1]. Copia literalmente las "
    "cifras, fechas, plazos y requisitos. Nunca digas si la persona tiene derecho, cumple "
    "requisitos o va a cobrar algo. No añadas avisos, introducciones ni enlaces. Si los "
    "fragmentos no responden a la pregunta, abstente. Devuelve solo un objeto JSON con las "
    'claves "status" ("answered" o "abstained"), "answer" (texto) y "sources" (lista de los '
    "números de fragmento citados)."
)

_URL_MARKERS = ("http://", "https://", "www.")
_NORMALIZED_NOTICE = normalize_text(NOTICE)
_NORMALIZED_LEAD_IN = normalize_text(LEAD_IN)


# --- Limits record --------------------------------------------------------------------


@dataclass(frozen=True)
class GeminiLimits:
    """The recorded operational limits a Gemini request must respect."""

    timeout_seconds: float
    max_output_tokens: int
    max_requests_per_minute: int
    max_requests_per_day: int
    cost_reference: str
    recorded_on: date


def load_gemini_limits(path: Path | None = None) -> Mapping[str, Any] | None:
    """Read the limits record; ``None`` when it is missing, unreadable, or not an object."""

    try:
        document = json.loads((path or DEFAULT_LIMITS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def evaluate_gemini_limits(
    document: Mapping[str, Any] | None, *, as_of: date
) -> Tuple[GateResult, Optional[GeminiLimits]]:
    """Check the limits record; return the gate result and the limits when it passes."""

    if document is None:
        return GateResult(False, ("gemini_limits_unreadable",)), None
    if (
        not isinstance(document, Mapping)
        or set(document) != LIMIT_KEYS
        or document.get("schema_version") != LIMITS_SCHEMA_VERSION
    ):
        return GateResult(False, ("gemini_limits_invalid",)), None
    if any(document[key] is None for key in LIMIT_KEYS):
        return GateResult(False, ("gemini_limits_not_recorded",)), None

    timeout = document["timeout_seconds"]
    integers = (
        document["max_output_tokens"],
        document["max_requests_per_minute"],
        document["max_requests_per_day"],
    )
    cost_reference = document["cost_reference"]
    recorded_on = _parse_date(document["recorded_on"])
    if (
        not _is_number(timeout)
        or not all(_is_int(value) for value in integers)
        or not isinstance(cost_reference, str)
        or not cost_reference.strip()
        or recorded_on is None
    ):
        return GateResult(False, ("gemini_limits_invalid",)), None

    if not (
        _within(timeout, TIMEOUT_RANGE)
        and _within(document["max_output_tokens"], MAX_OUTPUT_TOKENS_RANGE)
        and _within(document["max_requests_per_minute"], REQUESTS_PER_MINUTE_RANGE)
        and _within(document["max_requests_per_day"], REQUESTS_PER_DAY_RANGE)
    ):
        return GateResult(False, ("gemini_limits_out_of_range",)), None
    if recorded_on > as_of:
        return GateResult(False, ("gemini_limits_future_date",)), None

    return GateResult(True), GeminiLimits(
        timeout_seconds=float(timeout),
        max_output_tokens=document["max_output_tokens"],
        max_requests_per_minute=document["max_requests_per_minute"],
        max_requests_per_day=document["max_requests_per_day"],
        cost_reference=cost_reference.strip(),
        recorded_on=recorded_on,
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _within(value: float, bounds: Tuple[int, int]) -> bool:
    # NaN fails both comparisons, so it is out of range rather than accepted.
    return bounds[0] <= value <= bounds[1]


def _parse_date(value: object) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --- Transport seam and request ---------------------------------------------------------


@dataclass(frozen=True)
class GeminiDraftRequest:
    """Everything a transport may send for one draft; built only by code.

    ``payload_json`` is the JSON of :func:`app.privacy_review.minimal_provider_payload`
    (the redacted question and candidate-numbered reviewed excerpts). No land context,
    identifier, catalog metadata, or retained text is a field of this request.
    """

    model: str
    instruction: str
    instruction_version: str
    payload_json: str
    max_output_tokens: int
    timeout_seconds: float


class GeminiTransport(Protocol):
    """The only seam that could ever reach a model.

    ``send`` returns the model's text output for one request, or raises. Mapping the
    request to a vendor wire format, the endpoint, credentials, and honoring
    ``timeout_seconds`` are the job of a future reviewed transport; none exists here.
    """

    def send(self, request: GeminiDraftRequest) -> str:
        ...


class GenerationClock(Protocol):
    """Monotonic seconds for timeouts and per-minute limits; the UTC day for daily limits."""

    def monotonic(self) -> float:
        ...

    def utc_day(self) -> date:
        ...


class SystemClock:
    """The real clock; tests inject a fake one."""

    def monotonic(self) -> float:
        return time.monotonic()

    def utc_day(self) -> date:
        return datetime.now(timezone.utc).date()


class MalformedDraftError(ValueError):
    """The model output is not a well-formed structured draft; carries no output text."""


def parse_draft(text: object, offered: Iterable[int]) -> DraftAnswer:
    """Strictly parse a model output into a :class:`DraftAnswer`, or raise.

    Accepts only a bare JSON object with exactly ``status`` (``answered``/``abstained``),
    ``answer`` (text; non-blank and at most the response bound when answered), and
    ``sources`` (unique integers among the offered candidate numbers). Code fences, the
    pinned notice or lead-in, a link, duplicate keys, and oversize output are malformed.
    """

    if not isinstance(text, str) or len(text) > MAX_RAW_OUTPUT_CHARS:
        raise MalformedDraftError("output_invalid")
    if "```" in text:
        raise MalformedDraftError("output_fenced")
    lowered = text.lower()
    if any(marker in lowered for marker in _URL_MARKERS):
        raise MalformedDraftError("output_link")
    try:
        document = json.loads(text, object_pairs_hook=_unique_pairs)
    except ValueError:
        raise MalformedDraftError("output_not_json") from None
    if not isinstance(document, dict) or set(document) != DRAFT_KEYS:
        raise MalformedDraftError("output_shape")

    status = document["status"]
    answer = document["answer"]
    sources = document["sources"]
    if status not in ("answered", "abstained") or not isinstance(answer, str):
        raise MalformedDraftError("output_shape")
    if status == "answered" and (not answer.strip() or len(answer) > MAX_ANSWER_CHARS):
        raise MalformedDraftError("output_answer_size")
    normalized_answer = normalize_text(answer)
    if _NORMALIZED_NOTICE in normalized_answer or _NORMALIZED_LEAD_IN in normalized_answer:
        raise MalformedDraftError("output_code_owned_text")
    allowed = frozenset(offered)
    if (
        not isinstance(sources, list)
        or not all(_is_int(item) for item in sources)
        or len(set(sources)) != len(sources)
        or not set(sources) <= allowed
    ):
        raise MalformedDraftError("output_sources")
    return DraftAnswer(status=status, answer=answer, source_markers=tuple(sources))


def _unique_pairs(pairs: List[Tuple[str, Any]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


@dataclass(frozen=True)
class GeminiDraftClient:
    """Builds the code-owned request and hands it to the injected transport."""

    transport: GeminiTransport
    model: str
    limits: GeminiLimits

    def request_for(self, payload: Mapping[str, Any]) -> GeminiDraftRequest:
        return GeminiDraftRequest(
            model=self.model,
            instruction=GEMINI_INSTRUCTION,
            instruction_version=GEMINI_INSTRUCTION_VERSION,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            max_output_tokens=self.limits.max_output_tokens,
            timeout_seconds=self.limits.timeout_seconds,
        )

    def send(self, payload: Mapping[str, Any]) -> str:
        return self.transport.send(self.request_for(payload))


# --- Rate limiting --------------------------------------------------------------------


class RateLimiter:
    """Thread-safe per-minute sliding window plus a per-UTC-day count, per process."""

    def __init__(self, per_minute: int, per_day: int, clock: GenerationClock) -> None:
        self._per_minute = per_minute
        self._per_day = per_day
        self._clock = clock
        self._lock = threading.Lock()
        self._recent: List[float] = []
        self._day: Optional[date] = None
        self._day_count = 0

    def try_acquire(self) -> bool:
        with self._lock:
            now = self._clock.monotonic()
            today = self._clock.utc_day()
            if today != self._day:
                self._day = today
                self._day_count = 0
            self._recent = [stamp for stamp in self._recent if now - stamp < 60.0]
            if len(self._recent) >= self._per_minute or self._day_count >= self._per_day:
                return False
            self._recent.append(now)
            self._day_count += 1
            return True


# --- Generator and provider -----------------------------------------------------------


@dataclass
class GatedGeminiGenerator:
    """A ``GroundingGenerator`` that drafts with Gemini and falls back to extractive.

    It never raises because of the model path: every failure returns the extractive draft
    and records one fixed outcome code.
    """

    client: GeminiDraftClient
    limiter: RateLimiter
    clock: GenerationClock
    land_context: Any
    max_claims: int = DEFAULT_MAX_CLAIMS
    log: Callable[..., None] = field(default=operational_log)

    def generate(
        self,
        question: str,
        numbered_candidates: Sequence[Tuple[int, RetrievedPassage]],
        *,
        as_of: Optional[date] = None,
    ) -> DraftAnswer:
        outcome, draft = self._gemini_draft(question, numbered_candidates)
        self.log("generation", provider=PROVIDER_GEMINI, outcome=outcome)
        if draft is not None:
            return draft
        return ExtractiveGroundingGenerator(max_claims=self.max_claims).generate(
            question, numbered_candidates, as_of=as_of
        )

    def _gemini_draft(
        self,
        question: str,
        numbered_candidates: Sequence[Tuple[int, RetrievedPassage]],
    ) -> Tuple[str, Optional[DraftAnswer]]:
        if not self.limiter.try_acquire():
            return OUTCOME_RATE_LIMITED, None
        try:
            redacted = redact_text(question, land_context_values(self.land_context))
        except Exception:  # noqa: BLE001 - any redaction problem must keep the text local
            return OUTCOME_REDACTION_FAILED, None

        offered = tuple(numbered_candidates[: max(0, self.max_claims)])
        try:
            payload = minimal_provider_payload(
                redacted,
                [{"passage_id": str(rank), "text": passage.excerpt} for rank, passage in offered],
            )
            if not offered:
                raise ValueError("no_candidates")
        except Exception:  # noqa: BLE001
            return OUTCOME_PAYLOAD_INVALID, None

        started = self.clock.monotonic()
        try:
            raw = self.client.send(payload)
        except TimeoutError:
            return OUTCOME_TIMEOUT, None
        except Exception:  # noqa: BLE001 - a transport must never break the answer
            return OUTCOME_TRANSPORT_ERROR, None
        if self.clock.monotonic() - started > self.client.limits.timeout_seconds:
            return OUTCOME_TIMEOUT, None

        try:
            draft = parse_draft(raw, (rank for rank, _ in offered))
        except MalformedDraftError:
            return OUTCOME_MALFORMED, None
        if draft.status == "abstained":
            return OUTCOME_ABSTAINED, None
        if not verify_draft(draft, offered).ok:
            return OUTCOME_REJECTED, None
        return OUTCOME_USED, draft


@dataclass(frozen=True)
class GatedGeminiProvider:
    """The startup-resolved Gemini provider; one shared rate limiter per process."""

    client: GeminiDraftClient
    limiter: RateLimiter
    clock: GenerationClock

    def generator_for(
        self, land_context: Any, *, max_claims: int = DEFAULT_MAX_CLAIMS
    ) -> GatedGeminiGenerator:
        return GatedGeminiGenerator(
            client=self.client,
            limiter=self.limiter,
            clock=self.clock,
            land_context=land_context,
            max_claims=max_claims,
        )


@dataclass(frozen=True)
class ProviderResolution:
    """The effective provider, the fixed blocker codes, and the Gemini provider if any."""

    provider: str
    blockers: Tuple[str, ...] = ()
    gemini: Optional[GatedGeminiProvider] = None

    def generator_for(
        self, land_context: Any, *, max_claims: int = DEFAULT_MAX_CLAIMS
    ) -> Optional[GatedGeminiGenerator]:
        if self.gemini is None:
            return None
        return self.gemini.generator_for(land_context, max_claims=max_claims)


def resolve_generation_provider(
    env: Mapping[str, str] | None = None,
    *,
    record: Mapping[str, Any] | None,
    limits_document: Mapping[str, Any] | None,
    transport: Optional[GeminiTransport],
    as_of: date,
    clock: Optional[GenerationClock] = None,
) -> ProviderResolution:
    """Return the Gemini provider only when every gate input passes; else ``extractive``.

    Reads only ``MANIJERO_GENERATION_PROVIDER`` and ``MANIJERO_GEMINI_MODEL``.
    """

    source = os.environ if env is None else env
    decision = decide_generation_provider(source, record=record, as_of=as_of)
    if not decision.gemini_configured:
        return ProviderResolution(PROVIDER_EXTRACTIVE, decision.gemini_gate.blockers)

    blockers = list(decision.gemini_gate.blockers)
    limits_gate, limits = evaluate_gemini_limits(limits_document, as_of=as_of)
    blockers.extend(limits_gate.blockers)
    if transport is None:
        blockers.append(BLOCKER_TRANSPORT_UNAVAILABLE)
    if blockers or limits is None or transport is None:
        return ProviderResolution(PROVIDER_EXTRACTIVE, tuple(dict.fromkeys(blockers)))

    active_clock = clock or SystemClock()
    model = (source.get(GEMINI_MODEL_ENV) or "").strip()
    return ProviderResolution(
        PROVIDER_GEMINI,
        (),
        GatedGeminiProvider(
            client=GeminiDraftClient(transport=transport, model=model, limits=limits),
            limiter=RateLimiter(
                limits.max_requests_per_minute, limits.max_requests_per_day, active_clock
            ),
            clock=active_clock,
        ),
    )


def resolve_startup_provider(
    transport: Optional[GeminiTransport] = None,
    clock: Optional[GenerationClock] = None,
) -> ProviderResolution:
    """Resolve once at startup from the environment and the committed records.

    Never raises: an unexpected problem resolves to ``extractive`` with a fixed code.
    """

    active_clock = clock or SystemClock()
    try:
        return resolve_generation_provider(
            None,
            record=load_review_record(),
            limits_document=load_gemini_limits(),
            transport=transport,
            as_of=active_clock.utc_day(),
            clock=active_clock,
        )
    except Exception:  # noqa: BLE001 - startup must fail closed, never crash
        return ProviderResolution(PROVIDER_EXTRACTIVE, (BLOCKER_UNRESOLVED,))
