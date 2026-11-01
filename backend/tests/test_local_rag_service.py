"""Local answer service: start, service status, and stop with fake processes, probes, and Ollama.

Offline: no service process, no Ollama, no model, no ``torch``/``chromadb``. Each local home
is a temporary directory made ready by the fake-backed setup from ``test_local_rag_bootstrap``
(the same ``Env`` and fakes), so ``inspect`` runs for real. Processes, the loopback probe,
and the clock are fakes defined here; nothing is spawned or signalled for real.
"""

from __future__ import annotations

import contextlib
import fcntl
import http.server
import json
import os
import re
import socket
import stat
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

import test_local_rag_bootstrap as boot
from app import knowledge_release as kr
from app import local_rag_bootstrap as lrb
from app import local_rag_service as svc
from app.local_generation import PROVIDER_LOCAL, resolve_local_provider
from app.retrieval_backend import Bm25Backend, backend_from_environment

REPO_ROOT = boot.REPO_ROOT
RECORD = boot.RECORD
URL = "http://127.0.0.1:8000"
ALLOWED_KEYS = {
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL",
    "MANIJERO_ACTIVE_CAMPAIGN", "MANIJERO_KNOWLEDGE_RELEASE_ROOT", "MANIJERO_RETRIEVAL_MODE",
    "MANIJERO_VECTOR_STORE", "MANIJERO_EMBEDDING_ARTIFACT", "MANIJERO_GENERATION_PROVIDER",
    "MANIJERO_LOCAL_MODEL",
}


# --- Fakes ---------------------------------------------------------------------------------


class FakeProcesses:
    """A process table; spawned children are 'alive' until signalled (or exit at once)."""

    def __init__(self) -> None:
        self.table: Dict[int, Dict[str, Any]] = {}
        self.spawned: List[Dict[str, Any]] = []
        self.signals: List[tuple] = []
        self.next_pid = 40_000
        self.exit_at_once = False
        self.stubborn = False
        self.on_terminate = None

    def add(self, pid: int, command: str, alive: bool = True) -> None:
        self.table[pid] = {"alive": alive, "cmd": command, "stubborn": False}

    def spawn(self, argv, cwd, env, log_path) -> int:
        pid = self.next_pid
        self.next_pid += 1
        self.spawned.append({"argv": list(argv), "cwd": Path(cwd), "env": dict(env), "log": Path(log_path)})
        self.table[pid] = {"alive": not self.exit_at_once, "cmd": " ".join(argv), "stubborn": self.stubborn}
        return pid

    def alive(self, pid: int) -> bool:
        return bool(self.table.get(pid, {}).get("alive"))

    def command_line(self, pid: int) -> str:
        entry = self.table.get(pid)
        return entry["cmd"] if entry and entry["alive"] else ""

    def terminate(self, pid: int) -> None:
        self.signals.append(("TERM", pid))
        if self.on_terminate is not None:
            self.on_terminate(pid)
        if not self.table[pid]["stubborn"]:
            self.table[pid]["alive"] = False

    def kill(self, pid: int) -> None:
        self.signals.append(("KILL", pid))
        self.table[pid]["alive"] = False


class FakeProbe:
    """``/health`` answers as this service while a verified service process is alive."""

    def __init__(self, processes: FakeProcesses) -> None:
        self.processes = processes
        self.owner = svc.PORT_FREE  # what answers on the port when no service process does
        self.serves = True
        self.ready_answer = svc.READY
        self.calls: List[tuple] = []

    def _ours(self, port: int) -> bool:
        return any(entry["alive"] and svc.is_this_service(entry["cmd"], port) for entry in self.processes.table.values())

    def health(self, port: int) -> str:
        self.calls.append(("health", port))
        if self._ours(port):
            return svc.SERVICE_NAME if self.serves else svc.PORT_OTHER
        return self.owner

    def ready(self, port: int) -> str:
        self.calls.append(("ready", port))
        return self.ready_answer if self._ours(port) and self.serves else svc.SILENT


class FakeServiceClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.on_sleep = None

    def now(self) -> datetime:
        return boot.NOW

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        if self.on_sleep is not None:
            self.on_sleep()


class Harness:
    def __init__(self, env: boot.Env) -> None:
        self.env = env
        self.processes = FakeProcesses()
        self.probe = FakeProbe(self.processes)
        self.clock = FakeServiceClock()
        self.tag_calls = 0
        real_tags = env.ollama.tags

        def counted_tags() -> List[Dict[str, Any]]:
            self.tag_calls += 1
            return real_tags()

        env.ollama.tags = counted_tags  # type: ignore[assignment]
        self.ports = svc.ServicePorts(tools=env.ports, processes=self.processes, probe=self.probe, clock=self.clock)

    @property
    def lines(self) -> List[str]:
        return self.env.lines

    @property
    def output(self) -> str:
        return self.env.output

    @property
    def record_file(self) -> Path:
        return svc.record_path(self.env.paths)

    def record(self) -> Optional[svc.ServiceRecord]:
        return svc.read_record(self.record_file)

    def start(self, port: int = 8000) -> int:
        self.env._reset()
        return svc.run_start(self.env.ctx, self.ports, port)

    def status(self) -> int:
        self.env._reset()
        return svc.run_service_status(self.env.ctx, self.ports)

    def stop(self) -> int:
        self.env._reset()
        return svc.run_stop(self.env.ctx, self.ports)

    def forget(self) -> None:
        self.probe.calls.clear()
        self.processes.signals.clear()
        self.tag_calls = 0

    def write_record(self, pid: int, port: int = 8000) -> None:
        svc.write_record(self.record_file, svc.ServiceRecord(pid, port, "2026-11-01T09:30:00Z", "r", "/tmp/x.log"))


@pytest.fixture
def env(tmp_path: Path) -> boot.Env:
    return boot.Env(tmp_path)


@pytest.fixture
def ready(env: boot.Env) -> boot.Env:
    assert env.setup("yes") == 0, env.output
    env.forget_calls()
    return env


@pytest.fixture
def harness(ready: boot.Env) -> Harness:
    return Harness(ready)


@pytest.fixture
def running(harness: Harness) -> Harness:
    assert harness.start() == 0, harness.output
    harness.forget()
    return harness


def check_lines(output: str) -> List[str]:
    return [line for line in output.splitlines() if line.split(None, 1)[:1] in (["OK"], ["PROBLEM"], ["MISSING"])]


def lock_held(env: boot.Env) -> bool:
    return lrb.lock_is_held(svc.service_lock_path(env.paths))


# --- 1. Start when everything is ready -----------------------------------------------------


def test_start_when_ready_launches_the_service_in_the_background(harness: Harness, monkeypatch) -> None:
    for key, value in {
        "MANIJERO_DEPLOYMENT_PROFILE": "pilot",
        "MANIJERO_RETENTION_DB": "/tmp/retention.db",
        "MANIJERO_GEMINI_MODEL": "gemini-x",
        "MANIJERO_RETRIEVAL_MODE": "bm25",
        "HTTPS_PROXY": "http://proxy.example:3128",
        "PYTHONPATH": "/elsewhere",
        "LANG": "es_ES.UTF-8",
    }.items():
        monkeypatch.setenv(key, value)
    env = harness.env
    release_id = kr.current_release_id(env.paths.releases)

    code = harness.start()

    assert code == 0, harness.output
    assert harness.lines[0] == "Checking the local answer tools..."
    [launch] = harness.processes.spawned
    assert launch["argv"] == [
        boot.HYBRID_PYTHON, "-m", "uvicorn", "app.main:app", "--app-dir", str(REPO_ROOT / "backend"),
        "--host", "127.0.0.1", "--port", "8000", "--no-access-log",
    ]
    assert "--reload" not in launch["argv"] and "0.0.0.0" not in launch["argv"]
    assert launch["cwd"] == REPO_ROOT / "backend"
    launched = launch["env"]
    assert set(launched) <= ALLOWED_KEYS and set(launched) >= ALLOWED_KEYS - {"TMPDIR", "LC_ALL", "LANG", "HOME", "PATH"}
    assert launched["LANG"] == "es_ES.UTF-8" and launched["PATH"] == os.environ["PATH"]
    assert launched == {
        **{key: os.environ[key] for key in svc.INHERITED_KEYS if os.environ.get(key)},
        "MANIJERO_ACTIVE_CAMPAIGN": "2026",
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT": str(env.paths.releases),
        "MANIJERO_RETRIEVAL_MODE": "hybrid",
        "MANIJERO_VECTOR_STORE": str(env.paths.releases / "releases" / release_id / "vector-store"),
        "MANIJERO_EMBEDDING_ARTIFACT": str(env.paths.bge_m3),
        "MANIJERO_GENERATION_PROVIDER": "local",
        "MANIJERO_LOCAL_MODEL": RECORD["model"],
    }

    record = harness.record()
    assert record is not None and record.pid == 40_000 and record.port == 8000
    assert record.started_at == "2026-11-01T09:30:00Z" and record.release_id == release_id
    assert Path(record.log) == launch["log"] and launch["log"].parent == env.paths.logs and launch["log"].exists()
    assert stat.S_IMODE(harness.record_file.stat().st_mode) == 0o600

    out = harness.output
    assert "started with hybrid search, knowledge release {}, and the local drafting model {}".format(release_id, RECORD["model"]) in out
    assert "  Desktop app address:          http://127.0.0.1:8000" in out
    assert "  Android emulator app address: http://10.0.2.2:8000" in out
    assert "These are the apps' default addresses" in out
    for step in ("--desktop", "--android-run", "--local-rag-stop"):
        assert "./scripts/init.sh " + step in out
    assert "Log file: {}".format(launch["log"]) in out
    assert harness.lines[-1] == "Result: the local answer service started at http://127.0.0.1:8000."
    assert env.no_side_calls()  # no download, pull, build, or question
    assert not lock_held(env)


def test_the_launch_environment_passes_the_real_hybrid_and_local_gates(ready: boot.Env) -> None:
    _, model = lrb.load_pins(ready.ctx, boot.NOW.date())
    release_id = kr.current_release_id(ready.paths.releases)
    environment = svc.launch_environment(ready.ctx, lrb.Settings("2026"), model, release_id, {"PATH": "/bin"})

    assert not isinstance(backend_from_environment(environment), Bm25Backend)  # built lazily, nothing loaded
    resolution = resolve_local_provider(
        environment, record_document=RECORD, transport=object(), as_of=boot.NOW.date(), pilot=False, review_record=None
    )
    assert resolution.provider == PROVIDER_LOCAL and not resolution.blockers
    assert Path(environment["MANIJERO_VECTOR_STORE"]).is_dir()


def test_a_custom_port_has_no_default_address_note(harness: Harness) -> None:
    assert harness.start(port=8765) == 0, harness.output
    assert "These are the apps' default addresses" not in harness.output
    assert harness.lines[-1] == "Result: the local answer service started at http://127.0.0.1:8765."


# --- 2. A prerequisite is missing ----------------------------------------------------------


def _hold(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def _change_knowledge(env: boot.Env) -> None:
    passages = env.knowledge / kr.PASSAGES_FILE
    passages.write_text(json.dumps(json.loads(passages.read_text(encoding="utf-8")), ensure_ascii=False, indent=4), encoding="utf-8")


@pytest.mark.parametrize(
    "arrange, expected, fix",
    [
        (lambda env: setattr(env.ollama, "running", False), "PROBLEM  Drafting model: Ollama is not running. Open the Ollama app", "Open the Ollama app, then run this command again."),
        (lambda env: (setattr(env.ollama, "running", False), setattr(env.ollama, "cli", False)), "PROBLEM  Drafting model: Ollama is not installed.", "Install it from https://ollama.com/download"),
        (lambda env: setattr(env.ollama, "models", []), "MISSING  Drafting model: not downloaded yet.", "Run ./scripts/init.sh --local-rag-setup."),
        (lambda env: env.ollama._install("f" * 64), "PROBLEM  Drafting model: Ollama has a different version", "Run ./scripts/init.sh --local-rag-setup; if it still differs"),
        (_change_knowledge, "PROBLEM  Knowledge release: the knowledge files changed since it was built.", "Run ./scripts/init.sh --local-rag-setup to rebuild it."),
        (lambda env: [env.paths.settings.write_text("MANIJERO_ACTIVE_CAMPAIGN=26\n", encoding="utf-8")], "has a problem on line 1", svc.FIX_SETTINGS),
        (lambda env: _hold(env.paths.lock), svc.MSG_SETUP_RUNNING, svc.FIX_WAIT),
        (lambda env: _hold(svc.service_lock_path(env.paths)), svc.MSG_SERVICE_BUSY, svc.FIX_WAIT),
    ],
    ids=["ollama-closed", "ollama-missing", "drafting-missing", "digest-mismatch", "knowledge-changed", "bad-settings", "setup-running", "start-running"],
)
def test_a_missing_prerequisite_stops_before_any_change(harness: Harness, arrange, expected: str, fix: str) -> None:
    env = harness.env
    held = arrange(env)
    before = boot.snapshot(env.tmp)

    code = harness.start()

    assert code == 1
    assert expected in harness.output, harness.output
    assert harness.lines[-1].startswith(svc.START_FAILED + " ") and fix in harness.lines[-1]
    assert not any(line.startswith("OK ") for line in harness.lines)  # only the parts that are not OK
    assert not harness.processes.spawned and not harness.probe.calls
    assert env.no_side_calls()
    assert boot.snapshot(env.tmp) == before
    if isinstance(held, int):
        os.close(held)


def test_start_before_setup_names_the_setup_command_and_writes_nothing(env: boot.Env) -> None:
    harness = Harness(env)
    before = boot.snapshot(env.tmp)

    assert harness.start() == 1
    assert svc.MSG_NOT_SET_UP in harness.lines
    assert harness.lines[-1] == "Result: the local answer service did not start. Run ./scripts/init.sh --local-rag-setup."
    assert not env.paths.home.exists() and boot.snapshot(env.tmp) == before
    assert not harness.processes.spawned and not harness.probe.calls and harness.tag_calls == 0


# --- 3. The port is in use -----------------------------------------------------------------


@pytest.mark.parametrize(
    "owner, said, step",
    [
        (svc.MOCK_SERVICE_NAME, "in use by the mock answer service", "./scripts/init.sh --mock-stop"),
        (svc.SERVICE_NAME, "a Manijero answer service that this command did not start", "Press Ctrl+C in the window where ./scripts/init.sh --backend runs"),
        (svc.PORT_OTHER, "in use by another program", "Close the other program that uses port 8000"),
    ],
)
def test_a_port_in_use_names_the_one_step_and_starts_nothing(harness: Harness, owner: str, said: str, step: str) -> None:
    harness.probe.owner = owner
    before = boot.snapshot(harness.env.tmp)

    assert harness.start() == 1
    assert said in harness.output
    assert harness.lines[-1].startswith(svc.START_FAILED) and step in harness.lines[-1]
    assert not harness.processes.spawned
    assert boot.snapshot(harness.env.tmp) == before


# --- 4. Start while already running --------------------------------------------------------


def test_start_while_running_reports_the_status_and_starts_nothing(running: Harness) -> None:
    assert running.start() == 0
    assert len(running.processes.spawned) == 1
    assert running.lines[0].startswith("The local answer service is running at http://127.0.0.1:8000 (process 40000")
    assert [line.split()[0] for line in check_lines(running.output)] == ["OK"] * 3
    assert running.lines[-1] == "Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000."


def test_start_while_running_with_a_problem_exits_1(running: Harness) -> None:
    running.env.ollama.running = False

    assert running.start() == 1
    assert len(running.processes.spawned) == 1
    assert running.lines[-1] == (
        "Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000, "
        "but a check needs attention: do the first step shown above."
    )


# --- 5. Start fails after the process was launched -----------------------------------------


def _interrupt() -> None:
    raise KeyboardInterrupt


@pytest.mark.parametrize(
    "arrange, said, fix",
    [
        (lambda h: setattr(h.processes, "exit_at_once", True), "stopped while it was starting", "Run ./scripts/init.sh --local-rag-start again"),
        (lambda h: setattr(h.probe, "serves", False), "did not answer within 60 seconds", "Run ./scripts/init.sh --local-rag-start again"),
        (lambda h: (setattr(h.probe, "serves", False), setattr(h.processes, "stubborn", True)), "did not answer within 60 seconds", "send the log file"),
        (lambda h: setattr(h.probe, "ready_answer", svc.UNAVAILABLE), "cannot answer questions yet", "Run ./scripts/init.sh --local-rag-status and do its first step."),
        (lambda h: (setattr(h.probe, "serves", False), setattr(h.clock, "on_sleep", _interrupt)), "stopped with Ctrl+C", "Run ./scripts/init.sh --local-rag-start again when you are ready."),
    ],
    ids=["early-exit", "health-timeout", "stubborn-timeout", "ready-unavailable", "ctrl-c"],
)
def test_a_failed_start_ends_the_process_and_removes_the_record(harness: Harness, arrange, said: str, fix: str) -> None:
    arrange(harness)

    code = harness.start()

    assert code == 1
    [launch] = harness.processes.spawned
    pid = 40_000
    assert not harness.processes.alive(pid)
    if not harness.processes.exit_at_once:
        assert harness.processes.signals[0] == ("TERM", pid)
    if harness.processes.stubborn:
        assert harness.processes.signals == [("TERM", pid), ("KILL", pid)]
        assert harness.clock.t >= svc.START_TIMEOUT_SECONDS + svc.STOP_TIMEOUT_SECONDS
    assert not harness.record_file.exists()
    assert said in harness.output
    assert "Details are in the log file: {}".format(launch["log"]) in harness.lines
    assert harness.lines[-1].startswith(svc.START_FAILED) and fix in harness.lines[-1]
    assert "Traceback" not in harness.output
    assert not lock_held(harness.env)


def test_the_health_wait_is_bounded_by_60_seconds(harness: Harness) -> None:
    harness.probe.serves = False

    harness.start()

    assert svc.START_TIMEOUT_SECONDS <= harness.clock.t < svc.START_TIMEOUT_SECONDS + svc.STOP_TIMEOUT_SECONDS


def test_an_unexpected_error_after_launch_ends_the_process(harness: Harness) -> None:
    def explode(port: int) -> str:
        raise RuntimeError("internal detail that must stay in the log")

    harness.probe.ready = explode  # type: ignore[assignment]
    harness.env._reset()

    code = boot.local_cli.main(["start"], ctx=harness.env.ctx, service_ports=harness.ports)

    assert code == 1
    assert ("TERM", 40_000) in harness.processes.signals and not harness.record_file.exists()
    assert "Something unexpected went wrong." in harness.output and "internal detail" not in harness.output
    assert harness.lines[-1] == svc.START_FAILED
    log_path = Path(harness.output.split("send this log file to a developer: ", 1)[1].splitlines()[0])
    assert log_path.parent == harness.env.paths.logs and "Traceback" in log_path.read_text(encoding="utf-8")


# --- 6-7. Service status -------------------------------------------------------------------


def test_status_when_running_and_healthy(running: Harness) -> None:
    release_id = kr.current_release_id(running.env.paths.releases)
    before = boot.snapshot(running.env.tmp)

    code = running.status()

    assert code == 0
    assert running.lines[0] == "The local answer service is running at http://127.0.0.1:8000 (process 40000, started 2026-11-01 09:30 UTC)."
    assert check_lines(running.output) == [
        "OK       Answers: the service answers and is ready.",
        "OK       Search: started with hybrid search and knowledge release {}, which is still the published release.".format(release_id),
        "OK       Drafting: Ollama answers and has the reviewed drafting model.",
    ]
    assert "  Android emulator app address: http://10.0.2.2:8000" in running.lines
    assert any(line.startswith("Log file: ") for line in running.lines)
    assert running.lines[-1] == "Result: the local answer service is running at http://127.0.0.1:8000."
    assert boot.snapshot(running.env.tmp) == before
    assert running.env.no_side_calls()


def _newer_release(harness: Harness) -> None:
    _change_knowledge(harness.env)
    assert harness.env.setup() == 0, harness.env.output


@pytest.mark.parametrize(
    "arrange, line",
    [
        (lambda h: setattr(h.env.ollama, "running", False), "PROBLEM  Drafting: Ollama is not running. Answers continue without the drafting model until Ollama is opened. Open the Ollama app"),
        (lambda h: h.env.ollama._install("f" * 64), "PROBLEM  Drafting: Ollama has a different version than the reviewed one. Answers continue without the drafting model until this is fixed."),
        (lambda h: setattr(h.env.ollama, "models", []), "PROBLEM  Drafting: the reviewed drafting model is not in Ollama."),
        (_newer_release, "PROBLEM  Search: a newer knowledge release was published after the service started. Run ./scripts/init.sh --local-rag-stop, then ./scripts/init.sh --local-rag-start to use it."),
        (lambda h: setattr(h.probe, "ready_answer", svc.UNAVAILABLE), "PROBLEM  Answers: the service runs but cannot answer questions right now. Run ./scripts/init.sh --local-rag-status"),
        (lambda h: setattr(h.probe, "serves", False), "PROBLEM  Answers: the service does not answer. Run ./scripts/init.sh --local-rag-stop, then ./scripts/init.sh --local-rag-start; if it happens again, send the log file"),
    ],
    ids=["ollama-closed", "digest-mismatch", "model-removed", "newer-release", "ready-unavailable", "health-silent"],
)
def test_status_reports_each_problem_in_plain_words(running: Harness, arrange, line: str) -> None:
    arrange(running)

    code = running.status()

    assert code == 1
    assert any(item.startswith(line) for item in running.lines), running.output
    assert len(check_lines(running.output)) == 3
    assert "  Desktop app address:          http://127.0.0.1:8000" in running.lines
    assert running.lines[-1] == (
        "Result: the local answer service is running at http://127.0.0.1:8000, but a check needs attention: do the first step shown above."
    )


def test_status_recovers_once_ollama_is_opened_again(running: Harness) -> None:
    running.env.ollama.running = False
    assert running.status() == 1
    running.env.ollama.running = True
    assert running.status() == 0
    assert len(running.processes.spawned) == 1


# --- 8. Not running and stale records ------------------------------------------------------


def test_status_when_not_running_makes_no_network_call_and_writes_nothing(env: boot.Env) -> None:
    harness = Harness(env)

    assert harness.status() == 1
    assert harness.lines == [svc.NOT_RUNNING]
    assert not harness.probe.calls and harness.tag_calls == 0
    assert not env.paths.home.exists()


@pytest.mark.parametrize(
    "arrange",
    [
        lambda h: h.write_record(41_000),  # the process is gone
        lambda h: (h.processes.add(41_000, "/bin/sleep 600"), h.write_record(41_000)),  # pid reused
        lambda h: (h.processes.add(41_000, "python -m uvicorn app.main:app --host 127.0.0.1 --port 8001"), h.write_record(41_000)),
        lambda h: (h.record_file.parent.mkdir(parents=True), h.record_file.write_text("{not json", encoding="utf-8")),
    ],
    ids=["dead-pid", "other-program", "other-port", "unreadable"],
)
@pytest.mark.parametrize("command", ["status", "stop"])
def test_a_stale_record_is_cleared_and_never_signalled(harness: Harness, arrange, command: str) -> None:
    arrange(harness)

    code = getattr(harness, command)()

    assert harness.lines[0] == svc.MSG_STALE
    assert not harness.record_file.exists()
    assert not harness.processes.signals and not harness.probe.calls and harness.tag_calls == 0
    if command == "status":
        assert code == 1 and harness.lines[-1] == svc.NOT_RUNNING
    else:
        assert code == 0 and harness.lines[-1] == svc.NOTHING_TO_STOP
    if 41_000 in harness.processes.table:
        assert harness.processes.table[41_000]["alive"]


# --- 9. Stop -------------------------------------------------------------------------------


def test_stop_ends_the_service_and_removes_the_record(running: Harness) -> None:
    assert running.stop() == 0
    assert running.processes.signals == [("TERM", 40_000)]
    assert not running.record_file.exists()
    assert running.lines[-1] == svc.STOPPED
    assert not running.env.ollama.pulls and running.env.ollama.running  # Ollama keeps running

    assert running.stop() == 0
    assert running.lines == [svc.NOTHING_TO_STOP]
    assert running.status() == 1 and running.lines[-1] == svc.NOT_RUNNING


def test_a_stubborn_service_is_ended_for_sure_after_10_seconds(running: Harness) -> None:
    running.processes.table[40_000]["stubborn"] = True

    assert running.stop() == 0
    assert running.processes.signals == [("TERM", 40_000), ("KILL", 40_000)]
    assert svc.STOP_TIMEOUT_SECONDS <= running.clock.t
    assert not running.record_file.exists()


def test_a_process_that_stops_being_the_service_is_never_killed(running: Harness) -> None:
    entry = running.processes.table[40_000]
    entry["stubborn"] = True

    def reuse(pid: int) -> None:  # the service exits and its pid is reused by another program
        entry["cmd"] = "/bin/sleep 600"

    running.processes.on_terminate = reuse

    assert running.stop() == 0
    assert running.processes.signals == [("TERM", 40_000)]
    assert running.lines[-1] == svc.STOPPED


def test_stop_while_a_start_is_running_waits(running: Harness) -> None:
    handle = _hold(svc.service_lock_path(running.env.paths))
    try:
        assert running.stop() == 1
    finally:
        os.close(handle)
    assert svc.MSG_SERVICE_BUSY in running.lines and not running.processes.signals
    assert running.record_file.exists()


def test_stop_when_never_set_up_writes_nothing(env: boot.Env) -> None:
    harness = Harness(env)

    assert harness.stop() == 0
    assert harness.lines == [svc.NOTHING_TO_STOP]
    assert not env.paths.home.exists()


# --- 10. Misuse ----------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "65536", "abc", "-1", " 8000", "8000x", "８０００", "123456"])
def test_a_bad_port_is_misuse(value: str) -> None:
    with pytest.raises(svc.UsageError, match="between 1 and 65535"):
        svc.port_from_environment({svc.PORT_ENV: value})


def test_port_defaults_and_overrides() -> None:
    assert svc.port_from_environment({}) == 8000
    assert svc.port_from_environment({svc.PORT_ENV: ""}) == 8000
    assert svc.port_from_environment({svc.PORT_ENV: "8765"}) == 8765


@pytest.mark.parametrize("command", ["start", "stop", "service-status"])
def test_the_entry_point_refuses_a_bad_port_and_changes_nothing(harness: Harness, monkeypatch, capsys, command: str) -> None:
    monkeypatch.setenv(svc.PORT_ENV, "65536")
    before = boot.snapshot(harness.env.tmp)

    assert boot.local_cli.main([command], ctx=harness.env.ctx, service_ports=harness.ports) == 2
    assert "between 1 and 65535" in capsys.readouterr().err
    assert not harness.processes.spawned and boot.snapshot(harness.env.tmp) == before


def test_the_command_line_check_matches_only_this_service_on_its_port() -> None:
    base = "/x/.venv-hybrid/bin/python -m uvicorn app.main:app --app-dir /x/backend --host 127.0.0.1 --port {} --no-access-log"
    assert svc.is_this_service(base.format(8000), 8000)
    assert not svc.is_this_service(base.format(80000), 8000)
    assert not svc.is_this_service(base.format(8000).replace("127.0.0.1", "0.0.0.0"), 8000)
    assert not svc.is_this_service("java MockAnswerServerKt --host 127.0.0.1 --port 8000", 8000)
    assert not svc.is_this_service("", 8000)


# --- 11. Safety and privacy ----------------------------------------------------------------


def test_no_output_record_or_log_contains_corpus_text(running: Harness) -> None:
    running.status()
    running.env.ollama.running = False
    running.status()
    running.start()
    running.stop()
    running.probe.ready_answer = svc.UNAVAILABLE
    running.env.ollama.running = True
    running.start()
    texts = [line for line in running.env.all_output + running.lines]
    for path in running.env.paths.home.rglob("*"):
        if path.is_file() and (path.parent.name in ("logs", "run")):
            texts.append(path.read_text(encoding="utf-8"))
    joined = "\n".join(texts)
    passages = json.loads((boot.KNOWLEDGE / kr.PASSAGES_FILE).read_text(encoding="utf-8"))["passages"]
    for passage in passages:
        assert passage["text"][:40] not in joined


def test_the_service_never_imports_the_operator_modules() -> None:
    operator = ("local_rag_service", "local_rag_bootstrap", "pinned_download")
    pattern = re.compile(r"^\s*(from app(\.| import )|import app\.)({})".format("|".join(operator)), re.MULTILINE)
    for path in (REPO_ROOT / "backend" / "app").glob("*.py"):
        if path.stem in operator:
            continue
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
    assert pattern.search((REPO_ROOT / "backend" / "app" / "local_rag_service.py").read_text(encoding="utf-8"))


def test_the_real_probe_has_no_proxy_and_refuses_redirects() -> None:
    probe = svc.LoopbackProbe()
    handlers = [type(handler).__name__ for handler in probe._opener.handlers]
    assert "HTTPSHandler" not in handlers and "_RefuseRedirects" in handlers
    assert not any(getattr(handler, "proxies", None) for handler in probe._opener.handlers)


# --- Real ports (loopback only, test-owned) ------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextlib.contextmanager
def fake_http(routes: Dict[str, tuple]):
    """A test-owned loopback HTTP server thread answering fixed JSON per route."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            status, body = routes.get(self.path, (404, {}))
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: object) -> None:
            return None

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_the_real_probe_reads_health_and_ready() -> None:
    probe = svc.LoopbackProbe()
    port = _free_port()
    assert probe.health(port) == svc.PORT_FREE and probe.ready(port) == svc.SILENT

    healthy = {"/health": (200, {"status": "ok", "service": "manijero-backend"}), "/ready": (200, {"status": "ready", "service": "manijero-backend"})}
    with fake_http(healthy) as port:
        assert probe.health(port) == svc.SERVICE_NAME and probe.ready(port) == svc.READY
    unready = {"/health": (200, {"status": "ok", "service": "manijero-mock"}), "/ready": (503, {"status": "unavailable", "service": "manijero-backend"})}
    with fake_http(unready) as port:
        assert probe.health(port) == svc.MOCK_SERVICE_NAME and probe.ready(port) == svc.UNAVAILABLE
    with fake_http({"/health": (302, {"service": "manijero-backend"})}) as port:
        assert probe.health(port) == svc.PORT_OTHER


def test_the_real_process_port_verifies_by_command_line() -> None:
    processes = svc.SystemProcesses()
    assert processes.alive(os.getpid())
    assert "pytest" in processes.command_line(os.getpid()) or "python" in processes.command_line(os.getpid())
    assert not svc.is_this_service(processes.command_line(os.getpid()), 8000)
