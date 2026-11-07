#!/usr/bin/env python3
"""Measure local answer latency and throughput under the expected pilot load.

The owner never runs this file directly::

    ./scripts/init.sh --local-rag-load-test

With the service started by ``./scripts/init.sh --local-rag-start``, it sends the reviewed answer
cases from a closed loop of 10 clients over a 10 s ramp and a 180 s steady phase (stdlib only, no
load-testing tool), reports the median, p95 and slowest successful steady answer, the achieved
requests per second, and the answer kinds, and saves one aggregate-only report under
``<local home>/reports/``. ``status`` is read from each response and everything else -- question,
passage, answer, and land text -- is discarded at once.

The command takes no arguments, reads no port from the environment, and never changes the
service, the knowledge files, or the repository. It refuses to run unless the verified
``--local-rag-start`` record and its three checks are ``OK``: a run without drafting would measure
a different stack.

Exit codes: ``0`` the run finished, nothing failed, and the same service was running at the end;
``1`` refused, failed, incomplete, or interrupted; ``2`` misuse or an unreadable case set.
External effects go through injected ports (:class:`LoadPorts`) so tests use fakes.
"""

from __future__ import annotations

import fcntl
import http.client
import json
import math
import os
import socket
import sys
import threading
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import knowledge_release as kr  # noqa: E402
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as svc  # noqa: E402
from app.answer_eval import load_case_document  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

COMMAND = "./scripts/init.sh --local-rag-load-test"
LOCK_NAME = ".load-test.lock"
REPORT_DIR = "reports"
REPORT_PREFIX = "local-load-"
REPORT_SUFFIX = ".json"
REPORT_SCHEMA = "local-load-measurement-v1"
LOG_COMMAND = "load-test"

# The plan the owner decision fixed; tests pass their own tiny Plan.
CLIENTS = 10
RAMP_SECONDS = 10.0
STEADY_SECONDS = 180.0
WARMUP_QUESTIONS = 2
REQUEST_TIMEOUT_SECONDS = 60.0

MAX_RESPONSE_BYTES = 262_144
CANDIDATE_P95_SECONDS = 8.0
DRAFT_TIMEOUT_SECONDS = 10
DRAFT_REQUESTS_PER_MINUTE = 30

RAMP = "ramp"
STEADY = "steady"
WARMUP = "warmup"
ANSWER_STATUSES = ("answered", "abstained", "needs_land_clarification")
# Every measured request carries this context: the contract's no-land case (see the spec's
# "no land context in the measured requests"). A reviewed case's own context is never replayed.
GENERAL_LAND_CONTEXT = {"mode": "general", "lands": []}

CHECKING_LINE = "Checking the local answer service..."
SERVICE_LINE = "The local answer service is running at {} (process {}, knowledge release {})."
BUSY_LINE = "Another load test is running in another Terminal window."
NOT_RUNNING_LINE = "The local answer service is not running."
NOT_RUN_RESULT = "Result: the load test did not run."
FIX_START = "Start the local answer service with {}, then run this command again.".format(svc.START_COMMAND)
FIX_SHOWN = "Do the first step shown above."
WARMUP_RESULT = (
    "Result: the load test did not run. The service did not answer the warm-up questions. "
    "Run {} and do its first step.".format(svc.SERVICE_STATUS_COMMAND)
)
CASES_RESULT = "The reviewed questions could not be read, so the load test did not run."
STOPPED_LINE = "The load test was stopped."
STOPPED_RESULT = "Result: the load test was stopped before it finished. Nothing was changed."
FINISHED_RESULT = "Result: the load test finished; the report is in {}."
FAILED_RESULT = (
    "Result: the load test finished, but {} questions failed. The numbers above are incomplete; "
    "run it again once and send the report to a developer if it repeats."
)
CHANGED_RESULT = (
    "Result: the load test finished, but the local answer service changed during the run, so the "
    "numbers are not a complete measurement. Run {} before the next load test.".format(svc.START_COMMAND)
)
REPORT_LINE = "The report is saved as: {}"

HONESTY_LINES = (
    "These numbers describe this Mac at that moment. They are not a capacity measurement, and the "
    "pilot computer has not been measured.",
    "The plan's candidate reference is a p95 of {} seconds. It is context only: no verdict, ratio, "
    "or pass or fail line is computed from it.".format("{:.1f}".format(CANDIDATE_P95_SECONDS)),
    "The service may quietly answer without the drafting model when its {}-second draft timeout or "
    "its {} requests per minute limit is reached, so a low p95 can hide drafting. The mix of "
    "drafted and fallback answers cannot be observed by this test.".format(
        DRAFT_TIMEOUT_SECONDS, DRAFT_REQUESTS_PER_MINUTE
    ),
)

LIMITATIONS = (
    "These numbers describe one Mac at that moment; the pilot computer has not been measured.",
    "They are not a capacity measurement, a service promise, or a pass or fail result.",
    "The service may answer without the drafting model when its 10-second draft timeout or its "
    "30 requests per minute limit is reached, so a low p95 can hide drafting.",
    "The mix of drafted and fallback answers cannot be observed by this test.",
    "Requests are sent back to back with no think time, so the throughput is not a model of "
    "human pacing.",
    "Land context is not measured: every request uses the empty general context, so real land "
    "payloads are not covered.",
)


# --- Plan and pure helpers -----------------------------------------------------------------


def _round(value: float) -> float:
    return round(float(value), 4)


@dataclass(frozen=True)
class Plan:
    """The load plan: client count, ramp, steady phase, warm-up, and per-request timeout."""

    clients: int = CLIENTS
    ramp_seconds: float = RAMP_SECONDS
    steady_seconds: float = STEADY_SECONDS
    warmup_questions: int = WARMUP_QUESTIONS
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS

    def start_offset(self, index: int) -> float:
        """When client ``index`` starts: ``t0 + index * ramp / clients``."""

        if self.clients <= 1 or self.ramp_seconds <= 0:
            return 0.0
        return index * self.ramp_seconds / self.clients

    def phase_of(self, offset: float) -> Optional[str]:
        """The phase of a request started ``offset`` seconds after ``t0``; ``None`` past the end."""

        if offset >= self.ramp_seconds + self.steady_seconds:
            return None
        return RAMP if offset < self.ramp_seconds else STEADY


PLAN = Plan()


def summarize_latencies(values: Sequence[float]) -> dict:
    """Count, median, nearest-rank p95, max, and mean; ``None`` statistics when empty."""

    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "median": None, "p95": None, "max": None, "mean": None}
    count = len(ordered)
    middle = count // 2
    median = ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    p95 = ordered[max(0, math.ceil(0.95 * count) - 1)]
    return {
        "count": count,
        "median": _round(median),
        "p95": _round(p95),
        "max": _round(ordered[-1]),
        "mean": _round(sum(ordered) / count),
    }


def plan_line(cases: int, plan: Plan) -> str:
    """The one plain sentence describing the plan the run follows."""

    step = plan.ramp_seconds / plan.clients if plan.clients else plan.ramp_seconds
    if step == 1:
        ramp = "one more every second for {:g} seconds".format(plan.ramp_seconds)
    else:
        ramp = "one more every {:g} seconds for {:g} seconds".format(step, plan.ramp_seconds)
    minutes = plan.steady_seconds / 60
    steady = "{:g} minutes at once".format(minutes)
    return (
        "The plan: {} reviewed questions, {} warm-up questions, {} clients, {}, {}, about five minutes."
    ).format(cases, plan.warmup_questions, plan.clients, ramp, steady)


# --- One measured request ------------------------------------------------------------------


@dataclass(frozen=True)
class Attempt:
    """One ``/ask``: its timing, its HTTP status, and the contract ``status`` it returned."""

    ok: bool
    seconds: float
    error: str = ""  # "", "timeout", "connection", "status", "response", or "error"
    http_status: int = 0
    answer_status: str = ""


@dataclass(frozen=True)
class Step:
    """One request placed in the plan: the phase it started in and its offsets from ``t0``."""

    phase: str
    start_offset: float
    end_offset: float
    attempt: Attempt


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def now(self) -> datetime: ...

    def wait(self, event: threading.Event, seconds: float) -> bool: ...


class Connection(Protocol):
    def ask(self, question: str, land_context: Mapping[str, Any]) -> Attempt: ...

    def close(self) -> None: ...


class Connector(Protocol):
    def __call__(self, port: int) -> Connection: ...


def _answer_status(raw: bytes) -> str:
    """The contract ``status`` of a response body, or ``""``; nothing else is kept."""

    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    if not isinstance(document, dict):
        return ""
    status = document.get("status")
    return status if status in ANSWER_STATUSES else ""


class AskConnection:
    """One loopback ``/ask`` connection per simulated client; text is dropped at once.

    The connection is reused between requests and reset after a timeout or a transport error so
    the next request starts on a fresh socket.
    """

    def __init__(
        self,
        port: int,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._timeout = timeout
        self._timer = timer
        self._connection = http.client.HTTPConnection(svc.HOST, port, timeout=timeout)

    def ask(self, question: str, land_context: Mapping[str, Any]) -> Attempt:
        body = json.dumps({"question": question, "land_context": dict(land_context)})
        started = self._timer()
        try:
            self._connection.request(
                "POST", "/ask", body=body, headers={"Content-Type": "application/json"}
            )
            response = self._connection.getresponse()
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (socket.timeout, TimeoutError):
            self._reset()
            return Attempt(False, self._elapsed(started), "timeout")
        except (OSError, http.client.HTTPException):
            self._reset()
            return Attempt(False, self._elapsed(started), "connection")
        elapsed = self._elapsed(started)
        if len(raw) > MAX_RESPONSE_BYTES:
            return Attempt(False, elapsed, "response", status)
        ok = 200 <= status < 300
        return Attempt(ok, elapsed, "" if ok else "status", status, _answer_status(raw))

    def close(self) -> None:
        try:
            self._connection.close()
        except Exception:  # noqa: BLE001 - closing never fails a run
            pass

    def _reset(self) -> None:
        self.close()

    def _elapsed(self, started: float) -> float:
        return max(0.0, self._timer() - started)


class HostConnector:
    """Builds one :class:`AskConnection` for the recorded service port."""

    def __init__(
        self, timeout: float = REQUEST_TIMEOUT_SECONDS, timer: Callable[[], float] = time.perf_counter
    ) -> None:
        self._timeout = timeout
        self._timer = timer

    def __call__(self, port: int) -> Connection:
        return AskConnection(port, self._timeout, self._timer)


def client_steps(
    index: int,
    connection: Connection,
    cases: Sequence[Mapping[str, Any]],
    plan: Plan,
    t0: float,
    clock: Clock,
    stop_event: threading.Event,
) -> List[Step]:
    """One client's closed loop: start at its ramp offset, then ask round-robin until time is up."""

    if clock.wait(stop_event, plan.start_offset(index)):
        return []
    steps: List[Step] = []
    position = index
    while not stop_event.is_set():
        offset = clock.monotonic() - t0
        phase = plan.phase_of(offset)
        if phase is None:
            break
        case = cases[position % len(cases)]
        position += 1
        attempt = connection.ask(str(case["question"]), dict(GENERAL_LAND_CONTEXT))
        steps.append(Step(phase, offset, offset + attempt.seconds, attempt))
    return steps


def warm_up(
    port: int, connect: Connector, cases: Sequence[Mapping[str, Any]], plan: Plan
) -> Tuple[Attempt, ...]:
    """The warm-up questions, sent one at a time before the timed phase on their own connection."""

    questions = list(cases[: max(0, plan.warmup_questions)])
    if not questions:
        return ()
    try:
        connection = connect(port)
    except OSError:
        return tuple(Attempt(False, 0.0, "connection") for _ in questions)
    try:
        return tuple(
            connection.ask(str(case["question"]), dict(GENERAL_LAND_CONTEXT)) for case in questions
        )
    finally:
        connection.close()


def _worker(
    index: int,
    connection: Connection,
    cases: Sequence[Mapping[str, Any]],
    plan: Plan,
    t0: float,
    clock: Clock,
    stop_event: threading.Event,
    results: List[Step],
    guard: threading.Lock,
) -> None:
    try:
        steps = client_steps(index, connection, cases, plan, t0, clock, stop_event)
    except Exception:  # noqa: BLE001 - one client's failure is counted, never raised
        offset = max(0.0, clock.monotonic() - t0)
        steps = [Step(STEADY, offset, offset, Attempt(False, 0.0, "error"))]
    with guard:
        results.extend(steps)


def run_clients(
    port: int,
    connect: Connector,
    cases: Sequence[Mapping[str, Any]],
    plan: Plan,
    clock: Clock,
    stop_event: threading.Event,
) -> List[Step]:
    """Start every client at its ramp offset and collect the steps; Ctrl+C stops and re-raises."""

    t0 = clock.monotonic()
    results: List[Step] = []
    guard = threading.Lock()
    connections: List[Connection] = []
    threads: List[threading.Thread] = []
    try:
        for _ in range(max(1, plan.clients)):
            connections.append(connect(port))
        for index, connection in enumerate(connections):
            thread = threading.Thread(
                target=_worker,
                args=(index, connection, cases, plan, t0, clock, stop_event, results, guard),
                name="load-client-{}".format(index),
                daemon=True,
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            while thread.is_alive():
                thread.join(0.2)
    except KeyboardInterrupt:
        stop_event.set()
        for thread in threads:
            thread.join(5)
        raise
    finally:
        for connection in connections:
            connection.close()
    return sorted(results, key=lambda step: (step.start_offset, step.end_offset))


# --- Aggregation ---------------------------------------------------------------------------


def _counts(values: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def phase_summary(attempts: Sequence[Attempt]) -> dict:
    """Counts and the successful-request latency summary of one phase."""

    succeeded = [attempt for attempt in attempts if attempt.ok]
    failed = [attempt for attempt in attempts if not attempt.ok]
    return {
        "requests": len(attempts),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "timeouts": sum(1 for attempt in failed if attempt.error == "timeout"),
        "latency_seconds": summarize_latencies([attempt.seconds for attempt in succeeded]),
    }


def aggregate(steps: Sequence[Step]) -> Dict[str, dict]:
    """The ramp and steady phase summaries; the warm-up is reported separately."""

    return {
        phase: phase_summary([step.attempt for step in steps if step.phase == phase])
        for phase in (RAMP, STEADY)
    }


def steady_throughput(steps: Sequence[Step], plan: Plan) -> dict:
    """Successful steady requests over the measured steady window (the observed, planned-length-capped span)."""

    steady = [step for step in steps if step.phase == STEADY]
    succeeded = [step for step in steady if step.attempt.ok]
    latest = max((step.end_offset for step in steady), default=plan.ramp_seconds)
    window = min(plan.steady_seconds, max(0.0, latest - plan.ramp_seconds))
    rate = len(succeeded) / window if window > 0 else 0.0
    return {
        "successful_requests": len(succeeded),
        "measured_seconds": _round(window),
        "requests_per_second": _round(rate),
    }


@dataclass(frozen=True)
class ServiceChanges:
    """Whether the recorded service stopped or its release changed during the run."""

    stopped: bool = False
    changed: bool = False

    @property
    def any(self) -> bool:
        return self.stopped or self.changed


def end_changes(
    paths: bootstrap.LocalPaths,
    processes: svc.Processes,
    record: svc.ServiceRecord,
    release_id: Optional[str],
) -> ServiceChanges:
    """Re-read the record without clearing it and compare the same process and release."""

    running, _ = svc.find_running(paths, processes, clear=False)
    if running is None or running.pid != record.pid or running.release_id != record.release_id:
        return ServiceChanges(stopped=True)
    if release_id is not None and release_id != record.release_id:
        return ServiceChanges(changed=True)
    return ServiceChanges()


def build_report(
    plan: Plan,
    cases: int,
    record: svc.ServiceRecord,
    warmup: Sequence[Attempt],
    steps: Sequence[Step],
    phases: Mapping[str, dict],
    rate: Mapping[str, Any],
    changes: ServiceChanges,
    started_at: str,
    finished_at: str,
) -> dict:
    """The aggregate-only report: no per-case id, timing, question, answer, or land text."""

    steady_successes = [step.attempt for step in steps if step.phase == STEADY and step.attempt.ok]
    all_attempts = list(warmup) + [step.attempt for step in steps]
    return {
        "schema": REPORT_SCHEMA,
        "started_at": started_at,
        "finished_at": finished_at,
        "plan": {
            "clients": plan.clients,
            "ramp_seconds": plan.ramp_seconds,
            "steady_seconds": plan.steady_seconds,
            "warmup_questions": plan.warmup_questions,
            "request_timeout_seconds": plan.request_timeout_seconds,
            "closed_loop": True,
        },
        "service": {
            "pid": record.pid,
            "port": record.port,
            "release_id": record.release_id,
            "started_at": record.started_at,
        },
        "service_stopped_during_run": changes.stopped,
        "service_changed_mid_run": changes.changed,
        "reviewed_cases": cases,
        "phases": {
            WARMUP: phase_summary(list(warmup)),
            RAMP: phases[RAMP],
            STEADY: phases[STEADY],
        },
        "steady_throughput": dict(rate),
        "http_status_counts": _counts([str(a.http_status) for a in all_attempts if a.http_status]),
        "answer_status_counts": _counts([a.answer_status for a in steady_successes]),
        "candidate_reference": {
            "p95_seconds": CANDIDATE_P95_SECONDS,
            "used_as_gate": False,
        },
        "limitations": list(LIMITATIONS),
    }


def summary_lines(phases: Mapping[str, dict], rate: Mapping[str, Any], answers: Mapping[str, int]) -> List[str]:
    """The steady summary: finished, failed, median/p95/slowest, throughput, and answer kinds."""

    ramp, steady = phases[RAMP], phases[STEADY]
    lines = [
        "Ramp: {} questions finished, {} did not answer.".format(ramp["succeeded"], ramp["failed"]),
        "Steady phase: {} questions finished, {} did not answer.".format(
            steady["succeeded"], steady["failed"]
        ),
    ]
    latency = steady["latency_seconds"]
    if latency["count"]:
        lines.append(
            "  Median {:.2f} s, p95 {:.2f} s, slowest {:.2f} s.".format(
                latency["median"], latency["p95"], latency["max"]
            )
        )
    else:
        lines.append("  No steady question answered, so there is no time to report.")
    lines.append(
        "  Requests per second: {:.2f} ({} successful questions over {:.2f} s).".format(
            rate["requests_per_second"], rate["successful_requests"], rate["measured_seconds"]
        )
    )
    lines.append(
        "  Answers: {} answered, {} abstained, {} needed a land choice.".format(
            answers.get("answered", 0),
            answers.get("abstained", 0),
            answers.get("needs_land_clarification", 0),
        )
    )
    return lines


def warmup_line(attempts: Sequence[Attempt]) -> str:
    """One line: how many warm-up questions answered, with their times when all did."""

    answered = [attempt for attempt in attempts if attempt.ok]
    if not attempts:
        return "Warm-up: no warm-up question was sent."
    if len(answered) == len(attempts):
        times = ", ".join("{:.2f} s".format(attempt.seconds) for attempt in attempts)
        return "Warm-up: {} of {} questions answered ({}).".format(len(answered), len(attempts), times)
    return "Warm-up: {} of {} questions answered.".format(len(answered), len(attempts))


# --- Prerequisite gate, lock, and report file ----------------------------------------------


class _NotRun(Exception):
    """A prerequisite gap: no question was sent and nothing was written."""

    def __init__(self, lines: Sequence[str], fix: str) -> None:
        super().__init__(fix)
        self.lines = list(lines)
        self.fix = fix


def check_service(ctx: bootstrap.Context, ports: svc.ServicePorts) -> svc.ServiceRecord:
    """Settings, the verified run record, then the three checks; stop at the first gap."""

    paths = ctx.paths
    try:
        settings = bootstrap.read_settings(paths.settings)
    except bootstrap.SettingsError as error:
        raise _NotRun([error.message], svc.FIX_SETTINGS) from None
    if settings is None:
        raise _NotRun([svc.MSG_NOT_SET_UP], FIX_SHOWN)
    record, stale = svc.find_running(paths, ports.processes)
    if record is None:
        raise _NotRun(([svc.MSG_STALE] if stale else []) + [NOT_RUNNING_LINE], FIX_START)
    try:
        checks = svc.service_checks(ctx, ports, record)
    except bootstrap.BootstrapError as error:
        raise _NotRun([error.message], FIX_SHOWN) from None
    failing = [check for check in checks if not check.ok]
    if failing:
        raise _NotRun([failing[0].line], FIX_SHOWN)
    return record


@contextmanager
def load_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``<local home>/.load-test.lock`` for one measurement."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise _NotRun([BUSY_LINE], "Wait for the other load test to finish, then run this command again.") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


def load_cases(ctx: bootstrap.Context) -> List[dict]:
    """The reviewed cases, validated by the same loader the offline evaluators use."""

    catalog = load_catalog(ctx.knowledge_file(kr.CATALOG_FILE))
    passages = load_passage_set(ctx.knowledge_file(kr.PASSAGES_FILE))
    cases, _ = load_case_document(ctx.knowledge_file(kr.CASES_FILE), catalog, passages)
    return list(cases)


def current_release(paths: bootstrap.LocalPaths) -> Optional[str]:
    try:
        return kr.current_release_id(paths.releases)
    except kr.ReleaseError:
        return None


def shown_path(path: Path) -> str:
    """The path with the home folder written as ``~``, so the line stays short."""

    try:
        return str(Path("~") / Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def write_report(home: Path, report: Mapping[str, Any], now: Callable[[], datetime]) -> Path:
    """Write the report atomically with mode ``0600`` under ``<local home>/reports``."""

    directory = Path(home) / REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stamp = now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / "{}{}{}".format(REPORT_PREFIX, stamp, REPORT_SUFFIX)
    temporary = target.with_name(target.name + ".tmp")
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    return target


# --- Ports ---------------------------------------------------------------------------------


@dataclass
class LoadPorts:
    """Every external effect: the service ports, the connector, the clock, and the stop event."""

    service: svc.ServicePorts
    connect: Connector
    clock: Clock
    stop_event: threading.Event = field(default_factory=threading.Event)

    @property
    def out(self) -> Callable[[str], None]:
        return self.service.out


class SystemLoadClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def wait(self, event: threading.Event, seconds: float) -> bool:
        return event.wait(seconds)


def _utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Command -------------------------------------------------------------------------------


def run_load(ctx: bootstrap.Context, ports: LoadPorts, plan: Plan = PLAN) -> int:
    """Validate the cases, gate on the service, measure, then report; ``0`` only on a clean run."""

    out = ports.out
    try:
        cases = load_cases(ctx)
    except Exception:  # noqa: BLE001 - any unreadable or invalid case set is misuse
        out(CASES_RESULT)
        return 2
    out(CHECKING_LINE)
    try:
        with load_lock(ctx.paths.home / LOCK_NAME):
            record = check_service(ctx, ports.service)
            out(SERVICE_LINE.format(svc.service_url(record.port), record.pid, record.release_id))
            out(plan_line(len(cases), plan))
            warmup = warm_up(record.port, ports.connect, cases, plan)
            out(warmup_line(warmup))
            if any(not attempt.ok for attempt in warmup):
                out(WARMUP_RESULT)
                return 1
            started_at = _utc(ports.clock.now())
            steps = run_clients(record.port, ports.connect, cases, plan, ports.clock, ports.stop_event)
            finished_at = _utc(ports.clock.now())
            changes = end_changes(ctx.paths, ports.service.processes, record, current_release(ctx.paths))
            phases = aggregate(steps)
            rate = steady_throughput(steps, plan)
            answers = _counts(
                [step.attempt.answer_status for step in steps if step.phase == STEADY and step.attempt.ok]
            )
            report = build_report(
                plan, len(cases), record, warmup, steps, phases, rate, changes, started_at, finished_at
            )
            path = write_report(ctx.paths.home, report, ports.clock.now)
            for line in summary_lines(phases, rate, answers):
                out(line)
            out(REPORT_LINE.format(shown_path(path)))
            for line in HONESTY_LINES:
                out(line)
            if changes.any:
                out(CHANGED_RESULT)
                return 1
            failed = phases[RAMP]["failed"] + phases[STEADY]["failed"]
            if failed:
                out(FAILED_RESULT.format(failed))
                return 1
            out(FINISHED_RESULT.format(shown_path(path)))
            return 0
    except _NotRun as stop:
        for line in stop.lines:
            out(line)
        out("{} {}".format(NOT_RUN_RESULT, stop.fix))
        return 1
    except KeyboardInterrupt:
        out("")
        out(STOPPED_LINE)
        out(STOPPED_RESULT)
        return 1


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports(ctx: bootstrap.Context) -> LoadPorts:
    tools = bootstrap.Ports(
        ollama=bootstrap.OllamaClient(),
        checkout=bootstrap.GitCheckout(ctx.repo_root, ctx.knowledge_dir),
        runner=bootstrap.LoggedRunner(ctx.repo_root),
        prompter=bootstrap.TerminalPrompter(),
        disk=bootstrap.LocalDisk(),
        clock=bootstrap.SystemClock(),
        opener=None,  # the load test never downloads anything
        out=_say,
    )
    return LoadPorts(
        service=svc.ServicePorts(
            tools=tools,
            processes=svc.SystemProcesses(),
            probe=svc.LoopbackProbe(),
            clock=svc.SystemServiceClock(),
        ),
        connect=HostConnector(),
        clock=SystemLoadClock(),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print("Run {} on its own, with nothing after it.".format(COMMAND), file=sys.stderr, flush=True)
        return 2
    warnings.simplefilter("ignore")
    ctx = bootstrap.default_context(sys.executable)
    clock = SystemLoadClock()
    log = bootstrap.RunLog(ctx.paths.logs, LOG_COMMAND, clock.now)
    try:
        return run_load(ctx, build_ports(ctx))
    except KeyboardInterrupt:
        print("", flush=True)
        print(STOPPED_LINE, flush=True)
        print(STOPPED_RESULT, flush=True)
        return 1
    except Exception:  # noqa: BLE001 - one sentence plus a log, never a traceback on screen
        path = log.write_traceback()
        print(
            "Something unexpected went wrong. Run the same command again; if it happens again, send "
            "this log file to a developer: {}".format(path),
            flush=True,
        )
        print("Result: the load test could not finish.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
