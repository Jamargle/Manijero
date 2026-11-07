"""Privacy-safe health metrics for the answer service, in Prometheus text format 0.0.4.

``GET /metrics`` reports whether the service can answer and how it has behaved since this
process started, as counts and timings only. Every label name is on a fixed allowlist and
every label value is a fixed code (or a 16-hex knowledge release id); a value outside its
allowlist is clamped to ``other``. No question, answer, land detail, client id, token, path,
or exception text is ever recorded, so nothing here can leak what a person typed.

The exporter is hand-written with the standard library: the metric set is small and fixed,
and a global third-party registry would leak between ``create_app`` instances in tests.
Counters live in memory per process and reset on restart, like the pilot rate limiter; they
are never cluster-wide. Recording hooks mirror :mod:`app.answer_trace`: module-level,
swallow their own errors, and write to the registry the request middleware bound.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
SOURCE_UPDATE_STATE_DIR_ENV = "MANIJERO_SOURCE_UPDATE_STATE_DIR"
PREFIX = "manijero_"

# Label allowlist: the only label names a sample may carry.
LABEL_NAMES = frozenset(
    {"profile", "version", "provider", "route", "code", "rating", "reason", "status", "outcome",
     "problem", "release_id", "state", "job", "le"}
)
OTHER = "other"

ROUTES = ("/ask", "/ready", "/health", "/metrics", "/feedback")
CODES = frozenset({200, 204, 400, 401, 403, 404, 405, 413, 422, 429, 500, 503})
PROFILES = ("development", "pilot")
PROVIDERS = ("gemini", "local")
INFO_PROVIDERS = ("extractive", "gemini", "local")
REJECTION_REASONS = ("too_large", "unauthenticated", "rate_limited")
ANSWER_STATUSES = ("answered", "abstained", "needs_land_clarification")
FEEDBACK_RATINGS = ("useful", "not_useful")
ABSTENTION_REASONS = (
    "invalid_question", "no_evidence", "insufficient_evidence", "stale_evidence",
    "conflicting_evidence", "false_premise", "unsafe_request", "generator_abstained",
    "generation_error", "personal_data", "prompt_injection", "out_of_domain",
)
GENERATION_OUTCOMES = (
    "used", "rate_limited", "redaction_failed", "payload_invalid", "transport_error",
    "timeout", "malformed_output", "provider_abstained", "verifier_rejected",
)
READINESS_PROBLEMS = (
    "campaign_unavailable", "corpus_unavailable", "corpus_not_current", "no_eligible_sources",
)
RELEASE_STATES = ("served", "refused", "repository")
JOBS = ("monitor", "boe", "boja")
RELEASE_ID = re.compile(r"^[0-9a-f]{16}$")
BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

Labels = Tuple[Tuple[str, str], ...]

# (name, type, help) for every family, in rendering order (sorted by name below).
FAMILIES: Dict[str, Tuple[str, str]] = {
    "service_info": ("gauge", "Service profile and version; the value is always 1."),
    "generation_provider_info": ("gauge", "Effective answer provider; the value is always 1."),
    "process_start_time_seconds": ("gauge", "Start time of this process in Unix seconds."),
    "ready": ("gauge", "1 when the configured campaign and corpus can serve answers."),
    "readiness_problem": ("gauge", "1 for each fixed readiness problem currently present."),
    "http_requests_total": ("counter", "Responses by route and status code since process start."),
    "request_duration_seconds": ("histogram", "Request duration in seconds by route."),
    "request_rejections_total": ("counter", "Requests refused at the gate by route and reason."),
    "answers_total": ("counter", "Answer responses by status since process start."),
    "feedback_total": ("counter", "Accepted answer feedback by fixed rating, never by content."),
    "abstentions_total": ("counter", "Abstained answers by fixed reason since process start."),
    "generation_outcomes_total": ("counter", "Model drafts by provider and fixed outcome."),
    "knowledge_release_info": ("gauge", "Active knowledge release id and state; the value is 1."),
    "source_updates_configured": ("gauge", "1 when a source-update state folder is configured."),
    "source_updates_readable": ("gauge", "1 when the source-update ledger could be read."),
    "source_updates_healthy": ("gauge", "1 when the scheduler status reports no alerts."),
    "source_update_stale": ("gauge", "1 when the job has no recent successful run."),
    "source_update_last_success_timestamp_seconds": (
        "gauge", "Unix time of the job's last successful run."),
}


def clamp(value: Any, allowed: Iterable[Any]) -> str:
    """The value as a label when it is on the allowlist, else ``other``."""

    return str(value) if value in tuple(allowed) else OTHER


def route_for(path: str) -> str:
    return path if path in ROUTES else OTHER


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**labels: str) -> Labels:
    return tuple(sorted(labels.items()))


def _fmt(value: float) -> str:
    if isinstance(value, int) or float(value).is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(float(value))


def _sample(name: str, labels: Labels, value: float) -> str:
    if not labels:
        return "{}{} {}".format(PREFIX, name, _fmt(value))
    body = ",".join('{}="{}"'.format(key, _escape(val)) for key, val in labels)
    return "{}{}{{{}}} {}".format(PREFIX, name, body, _fmt(value))


class HealthMetrics:
    """One process's counters and one latency histogram, behind one lock."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, Dict[Labels, int]] = {
            name: {} for name, (kind, _) in FAMILIES.items() if kind == "counter"
        }
        self._histograms: Dict[str, List[Any]] = {}
        self._service: Labels = ()
        self._providers: Tuple[str, ...] = ()
        self._started = clock()
        for status in ANSWER_STATUSES:
            self._counters["answers_total"][_labels(status=status)] = 0
        for reason in ABSTENTION_REASONS:
            self._counters["abstentions_total"][_labels(reason=reason)] = 0
        for rating in FEEDBACK_RATINGS:
            self._counters["feedback_total"][_labels(rating=rating)] = 0

    # -- recording ----------------------------------------------------------------------

    def set_service(self, profile: str, version: str) -> None:
        with self._lock:
            self._service = _labels(profile=clamp(profile, PROFILES), version=_clamp_version(version))

    def set_provider(self, provider: str) -> None:
        with self._lock:
            self._providers = (clamp(provider, INFO_PROVIDERS),)

    def _increment(self, family: str, labels: Labels) -> None:
        with self._lock:
            counter = self._counters[family]
            counter[labels] = counter.get(labels, 0) + 1

    def count_response(self, path: str, status: int, seconds: float) -> None:
        route = route_for(path)
        code = str(status) if status in CODES else OTHER
        self._increment("http_requests_total", _labels(route=route, code=code))
        elapsed = max(0.0, float(seconds))
        with self._lock:
            entry = self._histograms.setdefault(route, [[0] * len(BUCKETS), 0.0, 0])
            for index, bound in enumerate(BUCKETS):
                if elapsed <= bound:
                    entry[0][index] += 1
            entry[1] += elapsed
            entry[2] += 1

    def count_rejection(self, path: str, reason: str) -> None:
        self._increment(
            "request_rejections_total",
            _labels(route=route_for(path), reason=clamp(reason, REJECTION_REASONS)),
        )

    def count_answer(self, status: str, reason: Optional[str]) -> None:
        self._increment("answers_total", _labels(status=clamp(status, ANSWER_STATUSES)))
        if reason is not None:
            self._increment("abstentions_total", _labels(reason=clamp(reason, ABSTENTION_REASONS)))

    def count_generation(self, provider: str, outcome: str) -> None:
        self._increment(
            "generation_outcomes_total",
            _labels(provider=clamp(provider, PROVIDERS), outcome=clamp(outcome, GENERATION_OUTCOMES)),
        )

    def count_feedback(self, rating: str) -> None:
        self._increment("feedback_total", _labels(rating=clamp(rating, FEEDBACK_RATINGS)))

    # -- rendering ----------------------------------------------------------------------

    def render(
        self,
        *,
        ready: bool,
        problems: Sequence[str] = (),
        release: Tuple[str, str] = ("none", "repository"),
        source_updates: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Prometheus text format 0.0.4: sorted families, each with HELP and TYPE."""

        with self._lock:
            counters = {name: dict(samples) for name, samples in self._counters.items()}
            histograms = {route: [list(e[0]), e[1], e[2]] for route, e in self._histograms.items()}
            service, providers, started = self._service, self._providers, self._started

        samples: Dict[str, List[str]] = {name: [] for name in FAMILIES}
        if service:
            samples["service_info"].append(_sample("service_info", service, 1))
        for provider in providers:
            samples["generation_provider_info"].append(
                _sample("generation_provider_info", _labels(provider=provider), 1))
        samples["process_start_time_seconds"].append(
            _sample("process_start_time_seconds", (), started))
        samples["ready"].append(_sample("ready", (), 1 if ready else 0))
        for problem in READINESS_PROBLEMS:
            samples["readiness_problem"].append(
                _sample("readiness_problem", _labels(problem=problem), 1 if problem in problems else 0))
        for name, series in counters.items():
            for labels in sorted(series):
                samples[name].append(_sample(name, labels, series[labels]))
        for route in sorted(histograms):
            counts, total, count = histograms[route]
            for bound, cumulative in zip(BUCKETS, counts):
                samples["request_duration_seconds"].append(
                    _sample("request_duration_seconds_bucket",
                            _labels(route=route, le=_fmt(bound)), cumulative))
            samples["request_duration_seconds"].append(
                _sample("request_duration_seconds_bucket", _labels(route=route, le="+Inf"), count))
            samples["request_duration_seconds"].append(
                _sample("request_duration_seconds_sum", _labels(route=route), total))
            samples["request_duration_seconds"].append(
                _sample("request_duration_seconds_count", _labels(route=route), count))
        release_id, state = release
        samples["knowledge_release_info"].append(_sample(
            "knowledge_release_info",
            _labels(release_id=release_id if RELEASE_ID.match(release_id) else "none",
                    state=clamp(state, RELEASE_STATES)),
            1))
        _render_source_updates(samples, source_updates)

        lines: List[str] = []
        for name in sorted(FAMILIES):
            kind, text = FAMILIES[name]
            lines.append("# HELP {}{} {}".format(PREFIX, name, text))
            lines.append("# TYPE {}{} {}".format(PREFIX, name, kind))
            lines.extend(samples[name])
        return "\n".join(lines) + "\n"


def _clamp_version(version: str) -> str:
    return version if re.fullmatch(r"[0-9][0-9A-Za-z.\-]{0,31}", str(version)) else OTHER


def _render_source_updates(
    samples: Dict[str, List[str]], snapshot: Optional[Mapping[str, Any]]
) -> None:
    configured = snapshot is not None
    samples["source_updates_configured"].append(
        _sample("source_updates_configured", (), 1 if configured else 0))
    if snapshot is None:
        return
    readable = bool(snapshot.get("readable"))
    samples["source_updates_readable"].append(
        _sample("source_updates_readable", (), 1 if readable else 0))
    if not readable:
        return
    samples["source_updates_healthy"].append(
        _sample("source_updates_healthy", (), 1 if snapshot["healthy"] else 0))
    for job in JOBS:
        entry = snapshot["jobs"][job]
        samples["source_update_stale"].append(
            _sample("source_update_stale", _labels(job=job), 1 if entry["stale"] else 0))
        if entry["last_success"] is not None:
            samples["source_update_last_success_timestamp_seconds"].append(
                _sample("source_update_last_success_timestamp_seconds",
                        _labels(job=job), entry["last_success"]))


def read_source_updates(environ: Mapping[str, str] | None = None) -> Optional[Dict[str, Any]]:
    """Scheduler run recency, or ``None`` when no state folder is configured.

    Any failure to read or evaluate the ledger reports ``readable`` as false; the folder
    path and the error text are never exposed. Recency only: this is no legal-freshness claim.
    """

    source = os.environ if environ is None else environ
    folder = (source.get(SOURCE_UPDATE_STATE_DIR_ENV) or "").strip()
    if not folder:
        return None
    try:
        from app.source_update_scheduler import status_for_state_dir  # lazy: optional tooling

        status = status_for_state_dir(Path(folder))
        alerts = set(status["alerts"])
        jobs = {}
        for job in JOBS:
            last = status["jobs"][job]["last_success_at"]
            jobs[job] = {
                "stale": "stale:{}".format(job) in alerts,
                "last_success": datetime.fromisoformat(last).timestamp() if last else None,
            }
        return {"readable": True, "healthy": bool(status["healthy"]), "jobs": jobs}
    except Exception:  # noqa: BLE001 - an unreadable ledger is a metric, never an error
        return {"readable": False}


# -- request-bound registry and hooks ---------------------------------------------------------

_ACTIVE: ContextVar[Optional[HealthMetrics]] = ContextVar("health_metrics_registry", default=None)


def bind(registry: Optional[HealthMetrics]) -> Token:
    return _ACTIVE.set(registry)


def unbind(token: Token) -> None:
    try:
        _ACTIVE.reset(token)
    except Exception:  # noqa: BLE001
        pass


def _safe(function: Callable[..., None]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except Exception:  # noqa: BLE001 - a hook must never affect a response
            return None

    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


@_safe
def note_response(path: str, status: int, seconds: float) -> None:
    registry = _ACTIVE.get()
    if registry is not None:
        registry.count_response(path, int(status), float(seconds))


@_safe
def note_rejection(path: str, reason: str) -> None:
    registry = _ACTIVE.get()
    if registry is not None:
        registry.count_rejection(path, reason)


@_safe
def note_answer(status: str, reason: Optional[str] = None) -> None:
    registry = _ACTIVE.get()
    if registry is not None:
        registry.count_answer(status, reason)


@_safe
def note_generation(provider: str, outcome: str, used_outcome: str) -> None:
    registry = _ACTIVE.get()
    if registry is not None:
        registry.count_generation(provider, "used" if outcome == used_outcome else outcome)


@_safe
def note_feedback(rating: str) -> None:
    registry = _ACTIVE.get()
    if registry is not None:
        registry.count_feedback(rating)
