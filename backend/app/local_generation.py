"""Local open-weight drafting through a loopback Ollama server.

This module adds the ``local`` provider to the replaceable generation slot built by
:mod:`app.gemini_generation`. It reuses :class:`~app.gemini_generation.GatedGeminiGenerator`
unchanged (the same instruction, strict parser, citation window, ``verify_draft``, rate
limiter, and extractive fallback), so a local draft can never be worse than today's
extractive answer. Only the transport and the startup gate are new here.

The local path runs only when every gate input passes at startup:

* ``MANIJERO_GENERATION_PROVIDER=local`` and ``MANIJERO_LOCAL_MODEL`` equal to the pinned
  ``model`` in the committed record ``backend/config/local_generation_model.json``
  (``local-generation-model-v1``);
* that record is readable, has exactly the expected keys, every value is in range, the model
  size is within the 50 GB memory budget, and it is not dated in the future;
* in the pilot profile, the pilot privacy review has passed (real users' questions would
  reach the model process).

Otherwise the resolver delegates to :func:`app.gemini_generation.resolve_startup_provider`
(when local is not selected) or resolves to ``extractive`` with fixed blocker codes that
echo no value.

:class:`OllamaTransport` talks only to :data:`OLLAMA_BASE_URL`, a loopback constant nothing
can override. Its default opener ignores proxy settings and refuses redirects. On first use
it checks that the pinned tag is installed with the recorded digest; only a success is
cached. It never logs and never carries response text in an exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import socket
import threading
from typing import Any, Callable, Mapping, Optional, Tuple
import urllib.error
import urllib.request

from app.gemini_generation import (
    BLOCKER_UNRESOLVED,
    PROVIDER_EXTRACTIVE,
    GatedGeminiProvider,
    GeminiDraftClient,
    GeminiDraftRequest,
    GeminiLimits,
    GeminiTransport,
    GenerationClock,
    ProviderResolution,
    RateLimiter,
    SystemClock,
    resolve_startup_provider,
)
from app.privacy_review import (
    GENERATION_PROVIDER_ENV,
    GateResult,
    evaluate_pilot_review,
    load_review_record,
)

# --- Constants ------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MEMORY_BUDGET_BYTES = 50_000_000_000
MAX_RESPONSE_BYTES = 65_536
TAGS_TIMEOUT_SECONDS = 2.0

RECORD_SCHEMA_VERSION = "local-generation-model-v1"
DEFAULT_RECORD_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "local_generation_model.json"
)
RECORD_KEYS = frozenset(
    {
        "schema_version",
        "model",
        "digest",
        "license",
        "license_reference",
        "parameter_size",
        "quantization",
        "size_bytes",
        "num_ctx",
        "timeout_seconds",
        "max_output_tokens",
        "max_requests_per_minute",
        "max_requests_per_day",
        "keep_alive_seconds",
        "recorded_on",
    }
)
MODEL_MAX_CHARS = 128
SIZE_BYTES_MIN = 1
NUM_CTX_RANGE = (2048, 32768)
TIMEOUT_RANGE = (1, 14)
MAX_OUTPUT_TOKENS_RANGE = (1, 1024)
REQUESTS_PER_MINUTE_RANGE = (1, 600)
REQUESTS_PER_DAY_RANGE = (1, 100000)
KEEP_ALIVE_RANGE = (0, 86400)

LOCAL_MODEL_ENV = "MANIJERO_LOCAL_MODEL"
PROVIDER_LOCAL = "local"
OUTCOME_LOCAL_USED = "local_used"
COST_REFERENCE = "local-no-spend"

BLOCKER_MODEL_MISMATCH = "local_model_mismatch"
BLOCKER_RECORD_UNREADABLE = "local_model_record_unreadable"
BLOCKER_RECORD_INVALID = "local_model_record_invalid"
BLOCKER_RECORD_OUT_OF_RANGE = "local_model_record_out_of_range"
BLOCKER_OVER_BUDGET = "local_model_over_budget"
BLOCKER_RECORD_FUTURE_DATE = "local_model_record_future_date"
BLOCKER_PILOT_REVIEW = "pilot_privacy_review_not_passed"

ERROR_CONNECTION_REFUSED = "connection_refused"
ERROR_HTTP = "http_error"
ERROR_MODEL_NOT_FOUND = "model_not_found"
ERROR_DIGEST_MISMATCH = "model_digest_mismatch"
ERROR_RESPONSE_INVALID = "response_invalid"
ERROR_MODEL_MISMATCH = "model_mismatch"
TRANSPORT_ERRORS = (
    ERROR_CONNECTION_REFUSED,
    ERROR_HTTP,
    ERROR_MODEL_NOT_FOUND,
    ERROR_DIGEST_MISMATCH,
    ERROR_RESPONSE_INVALID,
    ERROR_MODEL_MISMATCH,
)

# The same draft shape :func:`app.gemini_generation.parse_draft` accepts; the parser stays
# the authority, this only constrains Ollama's decoding.
DRAFT_JSON_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "abstained"]},
        "answer": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["status", "answer", "sources"],
}
OLLAMA_OPTIONS: Mapping[str, int] = {"temperature": 0, "seed": 0}
METRIC_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_SPDX_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")


# --- Model record ---------------------------------------------------------------------


@dataclass(frozen=True)
class LocalModelRecord:
    """The pinned local model and its operational limits."""

    model: str
    digest: str
    license: str
    license_reference: str
    parameter_size: str
    quantization: str
    size_bytes: int
    num_ctx: int
    timeout_seconds: float
    max_output_tokens: int
    max_requests_per_minute: int
    max_requests_per_day: int
    keep_alive_seconds: int
    recorded_on: date

    def limits(self) -> GeminiLimits:
        """The shared generator's limits for this record; local drafting costs nothing."""

        return GeminiLimits(
            timeout_seconds=self.timeout_seconds,
            max_output_tokens=self.max_output_tokens,
            max_requests_per_minute=self.max_requests_per_minute,
            max_requests_per_day=self.max_requests_per_day,
            cost_reference=COST_REFERENCE,
            recorded_on=self.recorded_on,
        )


def load_local_model_record(path: Path | None = None) -> Mapping[str, Any] | None:
    """Read the model record; ``None`` when it is missing, unreadable, or not an object."""

    try:
        document = json.loads((path or DEFAULT_RECORD_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def evaluate_local_model_record(
    document: Mapping[str, Any] | None, *, as_of: date
) -> Tuple[GateResult, Optional[LocalModelRecord]]:
    """Check the model record; return the gate result and the record when it passes."""

    if document is None:
        return GateResult(False, (BLOCKER_RECORD_UNREADABLE,)), None
    if (
        not isinstance(document, Mapping)
        or set(document) != RECORD_KEYS
        or document.get("schema_version") != RECORD_SCHEMA_VERSION
    ):
        return GateResult(False, (BLOCKER_RECORD_INVALID,)), None

    integers = (
        document["size_bytes"],
        document["num_ctx"],
        document["max_output_tokens"],
        document["max_requests_per_minute"],
        document["max_requests_per_day"],
        document["keep_alive_seconds"],
    )
    recorded_on = _parse_date(document["recorded_on"])
    if (
        not _is_model_tag(document["model"])
        or not isinstance(document["digest"], str)
        or not _DIGEST_PATTERN.fullmatch(document["digest"])
        or not isinstance(document["license"], str)
        or not _SPDX_PATTERN.fullmatch(document["license"])
        or not _is_text(document["license_reference"])
        or not _is_text(document["parameter_size"])
        or not _is_text(document["quantization"])
        or not all(_is_int(value) for value in integers)
        or not _is_number(document["timeout_seconds"])
        or recorded_on is None
    ):
        return GateResult(False, (BLOCKER_RECORD_INVALID,)), None

    if not (
        document["size_bytes"] >= SIZE_BYTES_MIN
        and _within(document["num_ctx"], NUM_CTX_RANGE)
        and _within(document["timeout_seconds"], TIMEOUT_RANGE)
        and _within(document["max_output_tokens"], MAX_OUTPUT_TOKENS_RANGE)
        and _within(document["max_requests_per_minute"], REQUESTS_PER_MINUTE_RANGE)
        and _within(document["max_requests_per_day"], REQUESTS_PER_DAY_RANGE)
        and _within(document["keep_alive_seconds"], KEEP_ALIVE_RANGE)
    ):
        return GateResult(False, (BLOCKER_RECORD_OUT_OF_RANGE,)), None
    if document["size_bytes"] > MEMORY_BUDGET_BYTES:
        return GateResult(False, (BLOCKER_OVER_BUDGET,)), None
    if recorded_on > as_of:
        return GateResult(False, (BLOCKER_RECORD_FUTURE_DATE,)), None

    return GateResult(True), LocalModelRecord(
        model=document["model"],
        digest=document["digest"],
        license=document["license"],
        license_reference=document["license_reference"].strip(),
        parameter_size=document["parameter_size"].strip(),
        quantization=document["quantization"].strip(),
        size_bytes=document["size_bytes"],
        num_ctx=document["num_ctx"],
        timeout_seconds=float(document["timeout_seconds"]),
        max_output_tokens=document["max_output_tokens"],
        max_requests_per_minute=document["max_requests_per_minute"],
        max_requests_per_day=document["max_requests_per_day"],
        keep_alive_seconds=document["keep_alive_seconds"],
        recorded_on=recorded_on,
    )


def _is_model_tag(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= MODEL_MAX_CHARS
        and not any(character.isspace() for character in value)
    )


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


# --- Loopback transport ---------------------------------------------------------------


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: the 3xx response surfaces as an ``HTTPError``."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def loopback_opener() -> urllib.request.OpenerDirector:
    """A plain-HTTP opener that ignores every proxy setting and refuses redirects.

    It is assembled explicitly rather than with ``build_opener`` so no proxy handler is
    read from the environment and no HTTPS, FTP, file, or data handler exists at all.
    ``ProxyHandler({})`` is passed for clarity; with no proxies it registers nothing.
    """

    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler({}),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        _RefuseRedirects(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


class LocalTransportError(RuntimeError):
    """A local transport failure; carries only a fixed code, never response text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OllamaTransport:
    """A :class:`~app.gemini_generation.GeminiTransport` for the pinned loopback model.

    The whole ``send`` (digest check plus chat) is bounded by ``request.timeout_seconds``;
    a socket timeout or an exhausted budget is re-raised as ``TimeoutError``. Every other
    failure is a :class:`LocalTransportError` with a fixed code.
    """

    def __init__(
        self,
        record: LocalModelRecord,
        *,
        opener: Any = None,
        clock: Optional[GenerationClock] = None,
        on_metrics: Optional[Callable[[Mapping[str, int]], None]] = None,
    ) -> None:
        self._record = record
        self._opener = opener if opener is not None else loopback_opener()
        self._clock = clock or SystemClock()
        self._on_metrics = on_metrics
        self._lock = threading.Lock()
        self._digest_verified = False

    def send(self, request: GeminiDraftRequest) -> str:
        if request.model != self._record.model:
            raise LocalTransportError(ERROR_MODEL_MISMATCH)
        deadline = self._clock.monotonic() + request.timeout_seconds
        self._ensure_digest(deadline)
        body = {
            "model": self._record.model,
            "messages": [
                {"role": "system", "content": request.instruction},
                {"role": "user", "content": request.payload_json},
            ],
            "stream": False,
            "format": DRAFT_JSON_SCHEMA,
            "options": {
                **OLLAMA_OPTIONS,
                "num_ctx": self._record.num_ctx,
                "num_predict": request.max_output_tokens,
            },
            "keep_alive": f"{self._record.keep_alive_seconds}s",
        }
        document = self._call("/api/chat", body, self._remaining(deadline))
        message = document.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LocalTransportError(ERROR_RESPONSE_INVALID)
        self._report_metrics(document)
        return content

    def _ensure_digest(self, deadline: float) -> None:
        with self._lock:
            if self._digest_verified:
                return
            timeout = min(TAGS_TIMEOUT_SECONDS, self._remaining(deadline))
            document = self._call("/api/tags", None, timeout)
            models = document.get("models")
            if not isinstance(models, list):
                raise LocalTransportError(ERROR_RESPONSE_INVALID)
            entry = next(
                (
                    item
                    for item in models
                    if isinstance(item, dict)
                    and self._record.model in (item.get("name"), item.get("model"))
                ),
                None,
            )
            if entry is None:
                raise LocalTransportError(ERROR_MODEL_NOT_FOUND)
            if entry.get("digest") != self._record.digest:
                raise LocalTransportError(ERROR_DIGEST_MISMATCH)
            self._digest_verified = True

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._clock.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        return remaining

    def _call(self, path: str, body: Optional[Mapping[str, Any]], timeout: float) -> dict:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            OLLAMA_BASE_URL + path,
            data=data,
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener.open(http_request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            error.close()
            code = ERROR_MODEL_NOT_FOUND if error.code == 404 else ERROR_HTTP
            raise LocalTransportError(code) from None
        except urllib.error.URLError as error:
            raise _mapped(error.reason) from None
        except Exception as error:  # noqa: BLE001 - every failure becomes a fixed code
            raise _mapped(error) from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LocalTransportError(ERROR_RESPONSE_INVALID)
        try:
            document = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise LocalTransportError(ERROR_RESPONSE_INVALID) from None
        if not isinstance(document, dict):
            raise LocalTransportError(ERROR_RESPONSE_INVALID)
        return document

    def _report_metrics(self, document: Mapping[str, Any]) -> None:
        if self._on_metrics is None:
            return
        metrics = {
            name: document[name]
            for name in METRIC_FIELDS
            if _is_int(document.get(name)) and document[name] >= 0
        }
        try:
            self._on_metrics(metrics)
        except Exception:  # noqa: BLE001 - a metrics observer must never break a draft
            pass


def _mapped(reason: object) -> BaseException:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return TimeoutError()
    if isinstance(reason, ConnectionRefusedError):
        return LocalTransportError(ERROR_CONNECTION_REFUSED)
    if isinstance(reason, LocalTransportError):
        return LocalTransportError(reason.code)
    return LocalTransportError(ERROR_HTTP)


# --- Startup resolution ---------------------------------------------------------------


def resolve_local_provider(
    env: Mapping[str, str] | None = None,
    *,
    record_document: Mapping[str, Any] | None,
    transport: Optional[GeminiTransport],
    as_of: date,
    clock: Optional[GenerationClock] = None,
    pilot: bool,
    review_record: Mapping[str, Any] | None,
) -> ProviderResolution:
    """Return the local provider only when every gate input passes; else ``extractive``.

    The caller has already selected ``local``; this reads only ``MANIJERO_LOCAL_MODEL``.
    A transport is built only when the gate passes, and building one makes no network call.
    """

    source = os.environ if env is None else env
    configured_model = (source.get(LOCAL_MODEL_ENV) or "").strip()
    record_gate, record = evaluate_local_model_record(record_document, as_of=as_of)
    blockers = list(record_gate.blockers)
    if record is not None and configured_model != record.model:
        blockers.append(BLOCKER_MODEL_MISMATCH)
    elif record is None and not configured_model:
        blockers.insert(0, BLOCKER_MODEL_MISMATCH)
    if pilot and not evaluate_pilot_review(review_record, as_of=as_of).passed:
        blockers.append(BLOCKER_PILOT_REVIEW)
    if blockers or record is None:
        return ProviderResolution(PROVIDER_EXTRACTIVE, tuple(dict.fromkeys(blockers)))

    active_clock = clock or SystemClock()
    limits = record.limits()
    active_transport = transport or OllamaTransport(record, clock=active_clock)
    return ProviderResolution(
        PROVIDER_LOCAL,
        (),
        GatedGeminiProvider(
            client=GeminiDraftClient(transport=active_transport, model=record.model, limits=limits),
            limiter=RateLimiter(
                limits.max_requests_per_minute, limits.max_requests_per_day, active_clock
            ),
            clock=active_clock,
            provider_name=PROVIDER_LOCAL,
            used_outcome=OUTCOME_LOCAL_USED,
        ),
    )


def resolve_startup_generation(
    *,
    gemini_transport: Optional[GeminiTransport] = None,
    local_transport: Optional[GeminiTransport] = None,
    clock: Optional[GenerationClock] = None,
    pilot: bool = False,
) -> ProviderResolution:
    """Resolve the answer provider once at startup; never raises and makes no network call.

    Unless ``MANIJERO_GENERATION_PROVIDER`` is exactly ``local``, this is
    :func:`app.gemini_generation.resolve_startup_provider`, unchanged.
    """

    try:
        selected = (os.environ.get(GENERATION_PROVIDER_ENV) or "").strip()
        if selected != PROVIDER_LOCAL:
            return resolve_startup_provider(gemini_transport, clock)
        active_clock = clock or SystemClock()
        return resolve_local_provider(
            None,
            record_document=load_local_model_record(),
            transport=local_transport,
            as_of=active_clock.utc_day(),
            clock=active_clock,
            pilot=pilot,
            review_record=load_review_record() if pilot else None,
        )
    except Exception:  # noqa: BLE001 - startup must fail closed, never crash
        return ProviderResolution(PROVIDER_EXTRACTIVE, (BLOCKER_UNRESOLVED,))
