"""The local load measurement with fake connections, a fake clock, and the fake service harness.

Offline: no service process, no Ollama, no model, no ``torch``/``chromadb``, and no network beyond
the loopback fakes. The service side reuses ``test_local_rag_service`` (a temporary local home made
ready by the fake-backed setup and a fake running service), so the real ``find_running``,
``service_checks``, and ``check_service`` gate run. Every request is a fake connection that records
the exact question text it was given, which is how the privacy assertions know the text never
reaches the screen or the report.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import stat
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest

import test_local_rag_bootstrap as boot
from test_local_rag_service import Harness, env, harness, ready, running  # noqa: F401 - fixtures
from app import knowledge_release as kr
from app import local_rag_service as svc

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "measure_local_load.py"
SENTINEL = "SENTINEL-QUESTION-TEXT-9f3a"
TINY = {"clients": 1, "ramp_seconds": 0.0, "steady_seconds": 2.0, "warmup_questions": 2}


@pytest.fixture(scope="module")
def load():
    spec = importlib.util.spec_from_file_location("measure_local_load", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_local_load"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


# --- Fakes ----------------------------------------------------------------------------------


class FakeClock:
    """A scripted monotonic clock; ``times`` are consumed in order, then ``step`` is added."""

    def __init__(self, step: float = 0.0, times: Sequence[float] = (), now: Any = boot.NOW) -> None:
        self.step = step
        self.times = list(times)
        self.t = 0.0
        self.now_value = now
        self.now_calls = 0
        self.on_now = None

    def monotonic(self) -> float:
        if self.times:
            self.t = self.times.pop(0)
        elif self.step:
            self.t += self.step
        else:
            raise AssertionError("the scripted clock ran out")
        return self.t

    def now(self):
        self.now_calls += 1
        if self.on_now is not None:
            self.on_now(self.now_calls)
        return self.now_value

    def wait(self, event: threading.Event, seconds: float) -> bool:
        if seconds:
            self.t += seconds
        return event.is_set()


class PerClientClock(FakeClock):
    """A stepping clock whose time is per thread, so each simulated client gets its own window.

    ``run_clients`` starts all clients together, but the GIL can let one finish its whole scripted
    window before the others are scheduled; a per-thread budget keeps the fake multi-client run
    deterministic without depending on thread scheduling.
    """

    def __init__(self, step: float = 0.05) -> None:
        super().__init__(step=step)
        self._local = threading.local()

    def monotonic(self) -> float:
        current = getattr(self._local, "t", 0.0) + self.step
        self._local.t = current
        return current


class FakeConnection:
    """Answers from a script, then a default; records every question it was given."""

    def __init__(self, load, attempts: Sequence[Any] = (), default: Any = None) -> None:
        self.load = load
        self.attempts = list(attempts)
        self.default = default
        self.questions: List[str] = []
        self.contexts: List[Mapping[str, Any]] = []
        self.closed = False

    def ask(self, question: str, land_context: Mapping[str, Any]):
        self.questions.append(question)
        self.contexts.append(dict(land_context))
        if self.attempts:
            return self.attempts.pop(0)
        return self.default if self.default is not None else ok(self.load)

    def close(self) -> None:
        self.closed = True


class FakeConnector:
    """One connection per call; ``build(index, port)`` scripts each client (index 0 is warm-up)."""

    def __init__(self, build) -> None:
        self.build = build
        self.connections: List[FakeConnection] = []
        self.ports: List[int] = []

    def __call__(self, port: int) -> FakeConnection:
        self.ports.append(port)
        connection = self.build(len(self.connections), port)
        self.connections.append(connection)
        return connection


def ok(load, seconds: float = 0.5, status: str = "answered", http_status: int = 200):
    return load.Attempt(True, seconds, "", http_status, status)


def failure(load, code: str = "timeout", seconds: float = 1.5, http_status: int = 0):
    return load.Attempt(False, seconds, code, http_status, "")


def tiny_plan(load, **overrides):
    return load.Plan(**{**TINY, **overrides})


def ports(load, service, connector, clock, stop=None):
    return load.LoadPorts(
        service=service,
        connect=connector,
        clock=clock,
        stop_event=stop if stop is not None else threading.Event(),
    )


def run(harness: Harness, load, connector, clock, plan, stop=None) -> int:
    harness.env._reset()
    return load.run_load(harness.env.ctx, ports(load, harness.ports, connector, clock, stop), plan)


def report_files(home: Path) -> List[Path]:
    directory = Path(home) / "reports"
    return sorted(directory.glob("*.json")) if directory.exists() else []


# --- Case parsing (scenario 8) --------------------------------------------------------------


def test_the_reviewed_cases_load(load, env: boot.Env) -> None:
    cases = load.load_cases(env.ctx)

    assert len(cases) == 17
    assert all(case["question"] for case in cases)
    # One reviewed case carries an ``all_active`` context in the corpus; measurement still sends
    # the empty general context for every case (scenario 9), which the test below checks.
    assert [case["land_context"]["mode"] for case in cases].count("general") == 16


def _case_document(env: boot.Env) -> Path:
    return env.knowledge / kr.CASES_FILE


def _rewrite(env: boot.Env, change) -> None:
    path = _case_document(env)
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda d: d.update(schema_version="pac-answer-eval-v1"), id="wrong-schema"),
        pytest.param(lambda d: d["cases"][0].pop("question"), id="missing-key"),
        pytest.param(lambda d: d["cases"].append(dict(d["cases"][0])), id="duplicate-id"),
        pytest.param(lambda d: d["cases"][0].update(question="   "), id="blank-question"),
        pytest.param(lambda d: d["cases"][0].update(question="x" * 2001), id="oversized-question"),
        pytest.param(lambda d: d["cases"][0].update(land_context={"mode": "all_active", "lands": []}), id="wrong-land-mode"),
    ],
)
def test_an_invalid_case_set_is_misuse_and_sends_nothing(load, env: boot.Env, tmp_path: Path, change) -> None:
    _rewrite(env, change)
    connector = FakeConnector(lambda index, port: FakeConnection(load))
    lines: List[str] = []

    code = load.run_load(
        env.ctx,
        ports(load, type("Service", (), {"out": lines.append})(), connector, FakeClock()),
    )

    assert code == 2
    assert lines == [load.CASES_RESULT]
    assert connector.ports == []
    assert not (env.paths.home / "reports").exists()


def test_an_unreadable_case_file_is_misuse_and_writes_nothing(load, env: boot.Env) -> None:
    _case_document(env).unlink()
    connector = FakeConnector(lambda index, port: FakeConnection(load))
    lines: List[str] = []

    code = load.run_load(
        env.ctx,
        ports(load, type("Service", (), {"out": lines.append})(), connector, FakeClock()),
    )

    assert code == 2 and lines == [load.CASES_RESULT]
    assert connector.ports == []
    assert not (env.paths.home / "reports").exists()


# --- Pure helpers ---------------------------------------------------------------------------


def test_ramp_offsets_spread_the_clients(load) -> None:
    plan = load.Plan()

    assert [plan.start_offset(index) for index in range(10)] == [float(index) for index in range(10)]
    assert load.Plan(clients=1, ramp_seconds=10.0).start_offset(0) == 0.0
    assert load.Plan(clients=4, ramp_seconds=0.0).start_offset(3) == 0.0


def test_phase_of_switches_at_the_ramp_and_the_end(load) -> None:
    plan = load.Plan(clients=10, ramp_seconds=10.0, steady_seconds=180.0)

    assert plan.phase_of(0.0) == load.RAMP
    assert plan.phase_of(9.999) == load.RAMP
    assert plan.phase_of(10.0) == load.STEADY
    assert plan.phase_of(189.999) == load.STEADY
    assert plan.phase_of(190.0) is None
    assert load.Plan(ramp_seconds=0.0, steady_seconds=5.0).phase_of(0.0) == load.STEADY


def test_percentiles_use_nearest_rank(load) -> None:
    assert load.summarize_latencies([]) == {"count": 0, "median": None, "p95": None, "max": None, "mean": None}
    assert load.summarize_latencies([2.0]) == {"count": 1, "median": 2.0, "p95": 2.0, "max": 2.0, "mean": 2.0}
    values = [float(value) for value in range(1, 21)]  # 1..20: rank ceil(0.95*20)=19
    assert load.summarize_latencies(values) == {
        "count": 20,
        "median": 10.5,
        "p95": 19.0,
        "max": 20.0,
        "mean": 10.5,
    }
    assert load.summarize_latencies([3.0, 1.0, 2.0])["p95"] == 3.0
    assert load.summarize_latencies([1.0, 2.0])["median"] == 1.5


def test_the_plan_line_names_every_constant(load) -> None:
    assert load.plan_line(14, load.Plan()) == (
        "The plan: 14 reviewed questions, 2 warm-up questions, 10 clients, one more every second "
        "for 10 seconds, 3 minutes at once, about five minutes."
    )


# --- One client's loop ----------------------------------------------------------------------


def test_client_steps_count_each_phase_and_use_the_request_start(load) -> None:
    plan = load.Plan(clients=1, ramp_seconds=1.0, steady_seconds=2.0)
    connection = FakeConnection(load, [ok(load, 0.4), ok(load, 0.6), ok(load, 0.2, "abstained")])
    clock = FakeClock(times=[0.0, 1.0, 2.0, 3.0])  # 0 = ramp, 1 and 2 = steady, 3 = past the end

    steps = load.client_steps(0, connection, [{"question": "q", "land_context": {"mode": "general", "lands": []}}], plan, 0.0, clock, threading.Event())

    assert [step.phase for step in steps] == [load.RAMP, load.STEADY, load.STEADY]
    assert [step.start_offset for step in steps] == [0.0, 1.0, 2.0]
    assert [step.end_offset for step in steps] == [0.4, 1.6, 2.2]
    assert len(connection.questions) == 3


def test_client_steps_always_send_the_empty_general_context(load) -> None:
    plan = load.Plan(clients=1, ramp_seconds=0.0, steady_seconds=1.0)
    connection = FakeConnection(load)
    case = {"question": "q", "land_context": {"mode": "all_active", "lands": [{"id": "a-land"}]}}

    load.client_steps(0, connection, [case], plan, 0.0, FakeClock(times=[0.0, 1.0]), threading.Event())

    assert connection.contexts == [{"mode": "general", "lands": []}]


def test_client_steps_stop_when_the_stop_event_is_set(load) -> None:
    plan = load.Plan(clients=1, ramp_seconds=0.0, steady_seconds=100.0)
    stop = threading.Event()
    stop.set()
    connection = FakeConnection(load)
    clock = FakeClock(times=[0.0, 1.0])

    assert load.client_steps(0, connection, [{"question": "q", "land_context": {"mode": "general", "lands": []}}], plan, 0.0, clock, stop) == []
    assert connection.questions == []


def test_client_steps_failures_keep_their_fixed_code_and_add_no_latency(load) -> None:
    plan = load.Plan(clients=1, ramp_seconds=0.0, steady_seconds=3.0)
    connection = FakeConnection(
        load,
        [
            failure(load, "timeout"),
            failure(load, "status", http_status=503),
            failure(load, "response"),
        ],
    )
    clock = FakeClock(times=[0.0, 1.0, 2.0, 3.0])

    steps = load.client_steps(0, connection, [{"question": "q", "land_context": {"mode": "general", "lands": []}}], plan, 0.0, clock, threading.Event())
    phases = load.aggregate(steps)

    assert phases[load.STEADY]["failed"] == 3
    assert phases[load.STEADY]["timeouts"] == 1
    assert phases[load.STEADY]["latency_seconds"]["count"] == 0


def test_one_failing_client_does_not_stop_the_others(load) -> None:
    plan = load.Plan(clients=3, ramp_seconds=0.0, steady_seconds=10.0)
    connector = FakeConnector(
        lambda index, port: FakeConnection(load, default=None if index else failure(load, "connection"))
    )
    clock = PerClientClock(step=0.05)

    steps = load.run_clients(8000, connector, [{"question": "q", "land_context": {"mode": "general", "lands": []}}], plan, clock, threading.Event())

    phases = load.aggregate(steps)
    assert phases[load.STEADY]["failed"] > 0
    assert phases[load.STEADY]["succeeded"] > 0
    assert all(connection.closed for connection in connector.connections)
    assert len(connector.connections) == 3
    assert all(connection.questions for connection in connector.connections)


def test_throughput_uses_only_successful_steady_requests(load) -> None:
    plan = load.Plan(ramp_seconds=10.0, steady_seconds=180.0)
    steps = [
        load.Step(load.RAMP, 1.0, 2.0, ok(load, 1.0)),
        load.Step(load.STEADY, 10.0, 12.0, ok(load, 2.0)),
        load.Step(load.STEADY, 12.0, 14.0, ok(load, 2.0)),
        load.Step(load.STEADY, 14.0, 20.0, failure(load, "timeout", 6.0)),
    ]

    rate = load.steady_throughput(steps, plan)

    assert rate == {"successful_requests": 2, "measured_seconds": 10.0, "requests_per_second": 0.2}


def test_throughput_window_never_exceeds_the_planned_steady_seconds(load) -> None:
    plan = load.Plan(ramp_seconds=10.0, steady_seconds=180.0)
    steps = [
        load.Step(load.STEADY, 170.0, 190.0, ok(load, 20.0)),
        load.Step(load.STEADY, 180.0, 240.0, ok(load, 60.0)),
    ]

    rate = load.steady_throughput(steps, plan)

    assert rate == {"successful_requests": 2, "measured_seconds": 180.0, "requests_per_second": 0.0111}


# --- The prerequisite gate (scenarios 3 and 4) ----------------------------------------------


def test_before_setup_says_to_set_up_and_sends_nothing(load, env: boot.Env) -> None:
    connector = FakeConnector(lambda index, port: FakeConnection(load))
    harness_ = Harness(env)

    code = run(harness_, load, connector, FakeClock(), tiny_plan(load))

    assert code == 1
    assert harness_.lines == [
        load.CHECKING_LINE,
        svc.MSG_NOT_SET_UP,
        "{} {}".format(load.NOT_RUN_RESULT, load.FIX_SHOWN),
    ]
    assert connector.ports == []
    assert not (env.paths.home / "reports").exists()


def test_with_no_run_record_says_how_to_start(load, harness: Harness) -> None:
    connector = FakeConnector(lambda index, port: FakeConnection(load))

    code = run(harness, load, connector, FakeClock(), tiny_plan(load))

    assert code == 1
    assert harness.lines == [
        load.CHECKING_LINE,
        load.NOT_RUNNING_LINE,
        "{} {}".format(load.NOT_RUN_RESULT, load.FIX_START),
    ]
    assert load.FIX_START == (
        "Start the local answer service with ./scripts/init.sh --local-rag-start, then run this command again."
    )
    assert connector.ports == []
    assert not (harness.env.paths.home / "reports").exists()


def test_a_stale_record_is_cleared_and_nothing_is_sent(load, harness: Harness) -> None:
    harness.write_record(999_999)
    connector = FakeConnector(lambda index, port: FakeConnection(load))

    code = run(harness, load, connector, FakeClock(), tiny_plan(load))

    assert code == 1
    assert harness.lines == [
        load.CHECKING_LINE,
        svc.MSG_STALE,
        load.NOT_RUNNING_LINE,
        "{} {}".format(load.NOT_RUN_RESULT, load.FIX_START),
    ]
    assert not harness.record_file.exists()
    assert connector.ports == []
    assert not (harness.env.paths.home / "reports").exists()


def _newer_release(harness: Harness) -> None:
    passages = harness.env.knowledge / kr.PASSAGES_FILE
    passages.write_text(
        json.dumps(json.loads(passages.read_text(encoding="utf-8")), ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    assert harness.env.setup() == 0, harness.env.output


@pytest.mark.parametrize(
    "arrange, line",
    [
        (lambda h: setattr(h.probe, "serves", False), "PROBLEM  Answers: the service does not answer."),
        (
            lambda h: setattr(h.probe, "ready_answer", svc.UNAVAILABLE),
            "PROBLEM  Answers: the service runs but cannot answer questions right now.",
        ),
        (lambda h: setattr(h.env.ollama, "running", False), "PROBLEM  Drafting: Ollama is not running."),
        (
            lambda h: h.env.ollama._install("f" * 64),
            "PROBLEM  Drafting: Ollama has a different version than the reviewed one.",
        ),
        (_newer_release, "PROBLEM  Search: a newer knowledge release was published after the service started."),
    ],
    ids=["health-down", "ready-unavailable", "ollama-closed", "digest-mismatch", "newer-release"],
)
def test_a_failing_service_check_stops_before_any_question(load, running: Harness, arrange, line: str) -> None:
    arrange(running)
    connector = FakeConnector(lambda index, port: FakeConnection(load))

    code = run(running, load, connector, FakeClock(), tiny_plan(load))

    assert code == 1
    assert [item for item in running.lines if line in item], running.output
    assert len(check_lines(running)) == 1, running.output
    assert running.lines[-1] == "{} {}".format(load.NOT_RUN_RESULT, load.FIX_SHOWN)
    assert connector.ports == []
    assert not (running.env.paths.home / "reports").exists()


def check_lines(harness: Harness) -> List[str]:
    return [line for line in harness.lines if line.split(None, 1)[:1] in (["OK"], ["PROBLEM"], ["MISSING"])]


# --- Interruption and the lock (scenario 7) -------------------------------------------------


def test_another_load_test_holds_the_lock(load, running: Harness) -> None:
    connector = FakeConnector(lambda index, port: FakeConnection(load))
    lock_path = running.env.paths.home / load.LOCK_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        code = run(running, load, connector, FakeClock(), tiny_plan(load))
    finally:
        os.close(handle)

    assert code == 1
    assert running.lines == [
        load.CHECKING_LINE,
        load.BUSY_LINE,
        "{} Wait for the other load test to finish, then run this command again.".format(load.NOT_RUN_RESULT),
    ]
    assert connector.ports == []
    assert not (running.env.paths.home / "reports").exists()


def test_ctrl_c_stops_before_the_report_and_writes_nothing(load, running: Harness) -> None:
    def interrupt(calls: int) -> None:
        if calls == 1:
            raise KeyboardInterrupt

    clock = FakeClock()
    clock.on_now = interrupt
    connector = FakeConnector(lambda index, port: FakeConnection(load))

    code = run(running, load, connector, clock, tiny_plan(load))

    assert code == 1
    assert running.lines[-2:] == [load.STOPPED_LINE, load.STOPPED_RESULT]
    assert not (running.env.paths.home / "reports").exists()
    # The lock was released, so a fresh run is not refused as busy.
    assert run(running, load, FakeConnector(lambda index, port: FakeConnection(load)), FakeClock(step=0.5), tiny_plan(load)) == 0


def test_a_pre_set_stop_event_ends_the_clients_without_asking(load, running: Harness) -> None:
    stop = threading.Event()
    stop.set()
    connector = FakeConnector(lambda index, port: FakeConnection(load))

    steps = load.run_clients(8000, connector, [{"question": "q", "land_context": {"mode": "general", "lands": []}}], load.Plan(clients=3, ramp_seconds=0.0, steady_seconds=100.0), FakeClock(step=1.0), stop)

    assert steps == []
    assert all(connection.questions == [] for connection in connector.connections)


# --- A complete run (scenarios 1, 2, 5, 6, 9) -----------------------------------------------


def clean_connector(load, steady=None) -> FakeConnector:
    def build(index: int, port: int) -> FakeConnection:
        if index == 0:
            return FakeConnection(load, [ok(load, 1.0), ok(load, 2.0)])
        return FakeConnection(load, default=steady or ok(load, 0.5, "abstained"))

    return FakeConnector(build)


def test_a_clean_run_reports_and_saves_an_aggregate_report(load, running: Harness) -> None:
    connector = clean_connector(load)
    clock = FakeClock(step=0.5)

    code = run(running, load, connector, clock, tiny_plan(load))

    report_path = report_files(running.env.paths.home)[0]
    assert code == 0, running.output
    assert running.lines[0] == load.CHECKING_LINE
    assert running.lines[1].startswith("The local answer service is running at http://127.0.0.1:8000 (process 40000, knowledge release ")
    assert running.lines[2] == load.plan_line(17, tiny_plan(load))
    assert running.lines[3] == "Warm-up: 2 of 2 questions answered (1.00 s, 2.00 s)."
    assert "Steady phase: 3 questions finished, 0 did not answer." in running.lines
    assert "  Median 0.50 s, p95 0.50 s, slowest 0.50 s." in running.lines
    assert "  Answers: 0 answered, 3 abstained, 0 needed a land choice." in running.lines
    assert load.REPORT_LINE.format(load.shown_path(report_path)) in running.lines
    assert load.HONESTY_LINES[0] in running.lines
    assert load.HONESTY_LINES[1] in running.lines
    assert "cannot be observed" in load.HONESTY_LINES[2]
    assert running.lines[-1] == load.FINISHED_RESULT.format(load.shown_path(report_path))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert report["schema"] == "local-load-measurement-v1"
    assert report["reviewed_cases"] == 17
    assert report["plan"] == {
        "clients": 1,
        "ramp_seconds": 0.0,
        "steady_seconds": 2.0,
        "warmup_questions": 2,
        "request_timeout_seconds": 60.0,
        "closed_loop": True,
    }
    assert report["service"] == {
        "pid": 40000,
        "port": 8000,
        "release_id": kr.current_release_id(running.env.paths.releases),
        "started_at": "2026-11-01T09:30:00Z",
    }
    assert report["service_stopped_during_run"] is False
    assert report["service_changed_mid_run"] is False
    assert report["phases"]["warmup"]["succeeded"] == 2
    assert report["phases"]["steady"]["succeeded"] == 3 and report["phases"]["steady"]["failed"] == 0
    assert report["steady_throughput"] == {"successful_requests": 3, "measured_seconds": 2.0, "requests_per_second": 1.5}
    assert report["http_status_counts"] == {"200": 5}
    assert report["answer_status_counts"] == {"abstained": 3}
    assert report["candidate_reference"] == {"p95_seconds": 8.0, "used_as_gate": False}
    assert report["limitations"] and any("pilot computer" in item for item in report["limitations"])
    assert report_path.parent == running.env.paths.home / "reports"
    assert [path.name for path in report_files(running.env.paths.home)] == [report_path.name]


def test_question_text_never_reaches_the_screen_or_the_report(load, tmp_path: Path) -> None:
    env = boot.Env(tmp_path)
    cases = env.knowledge / kr.CASES_FILE
    document = json.loads(cases.read_text(encoding="utf-8"))
    document["cases"][0]["question"] = SENTINEL
    cases.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    assert env.setup("yes") == 0, env.output
    env.forget_calls()
    harness_ = Harness(env)
    assert harness_.start() == 0, harness_.output
    harness_.forget()
    connector = clean_connector(load)

    code = run(harness_, load, connector, FakeClock(step=0.5), tiny_plan(load))

    output = harness_.output
    text = report_files(env.paths.home)[0].read_text(encoding="utf-8")
    assert code == 0
    assert connector.connections[0].questions and connector.connections[0].questions[0] == SENTINEL
    assert SENTINEL not in output and SENTINEL not in text
    for case in json.loads(cases.read_text(encoding="utf-8"))["cases"][:3]:
        assert case["id"] not in output and case["id"] not in text
        assert case["question"] not in output and case["question"] not in text
    assert "¿" not in output and "¿" not in text


def test_failed_requests_are_counted_without_inventing_a_latency(load, running: Harness) -> None:
    connector = clean_connector(load, steady=failure(load, "status", seconds=1.0, http_status=503))

    code = run(running, load, connector, FakeClock(step=0.5), tiny_plan(load))

    report_path = report_files(running.env.paths.home)[0]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 1
    assert "Steady phase: 0 questions finished, 3 did not answer." in running.lines
    assert "  No steady question answered, so there is no time to report." in running.lines
    assert report["phases"]["steady"]["failed"] == 3
    assert report["phases"]["steady"]["latency_seconds"]["count"] == 0
    assert report["http_status_counts"] == {"200": 2, "503": 3}
    assert running.lines[-1] == load.FAILED_RESULT.format(3)
    assert "incomplete" in running.lines[-1]


def test_a_failed_ramp_request_also_makes_the_run_incomplete(load, running: Harness) -> None:
    connector = FakeConnector(
        lambda index, port: FakeConnection(load, [failure(load, "status", 0.0, 503), ok(load)])
    )
    plan = load.Plan(clients=1, ramp_seconds=1.0, steady_seconds=1.0, warmup_questions=0)

    code = run(running, load, connector, FakeClock(step=0.5), plan)

    report = json.loads(report_files(running.env.paths.home)[0].read_text(encoding="utf-8"))
    assert code == 1
    assert "Ramp: 0 questions finished, 1 did not answer." in running.lines
    assert "Steady phase: 2 questions finished, 0 did not answer." in running.lines
    assert report["phases"]["ramp"]["failed"] == 1 and report["phases"]["steady"]["failed"] == 0
    assert running.lines[-1] == load.FAILED_RESULT.format(1)


def test_a_failed_warm_up_stops_before_the_timed_phase(load, running: Harness) -> None:
    connector = FakeConnector(
        lambda index, port: FakeConnection(
            load, [ok(load, 1.0), failure(load, "timeout")]
        )
    )

    code = run(running, load, connector, FakeClock(step=0.5), tiny_plan(load))

    assert code == 1
    assert running.lines[3] == "Warm-up: 1 of 2 questions answered."
    assert running.lines[-1] == load.WARMUP_RESULT
    assert len(connector.connections) == 1  # no client connection was ever opened
    assert not (running.env.paths.home / "reports").exists()


def test_a_service_that_stops_mid_run_makes_the_numbers_incomplete(load, running: Harness) -> None:
    def stop_service(calls: int) -> None:
        if calls == 2:  # started_at, then finished_at
            for entry in running.processes.table.values():
                entry["alive"] = False

    clock = FakeClock(step=0.5)
    clock.on_now = stop_service

    code = run(running, load, clean_connector(load), clock, tiny_plan(load))

    report = json.loads(report_files(running.env.paths.home)[0].read_text(encoding="utf-8"))
    assert code == 1
    assert report["service_stopped_during_run"] is True
    assert report["service_changed_mid_run"] is False
    assert running.lines[-1] == load.CHANGED_RESULT
    assert "--local-rag-start" in running.lines[-1] and "not a complete measurement" in running.lines[-1]


def test_a_newer_release_mid_run_makes_the_numbers_incomplete(load, running: Harness, monkeypatch) -> None:
    # Patch only the measurement's own reader: the service check must still see the real release.
    monkeypatch.setattr(load, "current_release", lambda paths: "newer-release")

    code = run(running, load, clean_connector(load), FakeClock(step=0.5), tiny_plan(load))

    report = json.loads(report_files(running.env.paths.home)[0].read_text(encoding="utf-8"))
    assert code == 1
    assert report["service_changed_mid_run"] is True and report["service_stopped_during_run"] is False
    assert running.lines[-1] == load.CHANGED_RESULT


# --- Command and service boundary -----------------------------------------------------------


def test_the_measurement_takes_no_arguments(load, capsys) -> None:
    code = load.main(["now"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.strip() == "Run {} on its own, with nothing after it.".format(load.COMMAND)


def test_the_service_never_imports_the_measurement_script() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; import app.main; print('measure_local_load' in sys.modules)"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"
