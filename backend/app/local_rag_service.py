"""Start, stop, and check the full local answer service over the local RAG artifacts.

Operator-only and stdlib-only at import time; the answer service never imports this
module. It runs the unchanged service (``app.main:app``) from the hybrid environment
(``backend/.venv-hybrid``) in the background, bound to ``127.0.0.1`` only, without reload,
in the default (non-pilot) profile, over the artifacts that ``local_rag_bootstrap`` set up
in the local home (default ``~/manijero/local``):

* :func:`run_start` checks every prerequisite (all six ``--local-rag-status`` parts ``OK``,
  no setup running, the port free) before it writes anything or starts any process, then
  launches the service with an allowlisted environment, writes the run record
  ``<local home>/run/service.json``, and waits until ``/health`` and ``/ready`` answer;
* :func:`run_service_status` reports three checks (answers, search, drafting) from live
  loopback probes and the run record; it never inspects the six artifacts;
* :func:`run_stop` ends the recorded process, but only while its command line still
  verifies it as this service.

Network calls are loopback only (the service port and Ollama). Messages are fixed English
sentences with no question, passage text, land value, or token; server output goes only to
the log file under ``<local home>/logs/``. External effects go through injected ports
(:class:`ServicePorts`) so tests use fakes.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple

from app import knowledge_release as kr
from app import local_rag_bootstrap as bootstrap
from app.local_generation import LocalModelRecord, loopback_opener

START_COMMAND = "./scripts/init.sh --local-rag-start"
STOP_COMMAND = "./scripts/init.sh --local-rag-stop"
SERVICE_STATUS_COMMAND = "./scripts/init.sh --local-rag-service-status"

PORT_ENV = "MANIJERO_LOCAL_RAG_PORT"  # tests and developers only
DEFAULT_PORT = 8000
HOST = "127.0.0.1"
EMULATOR_HOST = "10.0.2.2"

START_TIMEOUT_SECONDS = 60.0
STOP_TIMEOUT_SECONDS = 10.0
KILL_WAIT_SECONDS = 2.0
PROBE_TIMEOUT_SECONDS = 2.0
POLL_SECONDS = 0.5
MAX_PROBE_BYTES = 65_536

SERVICE_NAME = "manijero-backend"
MOCK_SERVICE_NAME = "manijero-mock"
PORT_FREE = "free"
PORT_OTHER = "other"
READY = "ready"
UNAVAILABLE = "unavailable"
SILENT = "silent"

# Inherited variables the service may see; every MANIJERO_* key is set explicitly instead.
INHERITED_KEYS = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")

RUN_DIR = "run"
RECORD_NAME = "service.json"
SERVICE_LOCK_NAME = ".service.lock"
LOG_COMMAND = "service"

_PORT_PATTERN = re.compile(r"[0-9]{1,5}")

MSG_BAD_PORT = "{} must be a port number between 1 and 65535.".format(PORT_ENV)
MSG_NOT_SET_UP = (
    "The local answer tools are not set up yet. Run {} to set them up.".format(bootstrap.SETUP_COMMAND)
)
MSG_SETUP_RUNNING = (
    "A setup of the local answer tools is running in another Terminal window. Wait until it shows "
    "its Result: line, then run this command again."
)
MSG_SERVICE_BUSY = (
    "Another start or stop of the local answer service is running in another Terminal window. Wait "
    "until it shows its Result: line, then run this command again."
)
MSG_STALE = "An earlier local answer service ended without being stopped; its leftover record was cleared."
FIX_RUN_SETUP = "Run {}.".format(bootstrap.SETUP_COMMAND)
FIX_WAIT = "Wait for the other command to finish, then run this command again."
FIX_SETTINGS = "Fix the settings file as described above, then run this command again."
FIX_PIN = "A developer must review the reviewed settings named above."
FIX_RESTART = "Run {}, then {}".format(STOP_COMMAND, START_COMMAND)  # no final period: it starts a sentence

START_FAILED = "Result: the local answer service did not start."
STOPPED = "Result: the local answer service has stopped."
NOTHING_TO_STOP = "Result: the local answer service was not running, so there was nothing to stop."
NOT_RUNNING = "Result: the local answer service is not running. Start it with {}.".format(START_COMMAND)


class UsageError(Exception):
    """A misuse (exit ``2``): one plain sentence, nothing changed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def port_from_environment(environ: Mapping[str, str]) -> int:
    """The service port: ``MANIJERO_LOCAL_RAG_PORT`` (tests and developers only) or ``8000``."""

    text = environ.get(PORT_ENV) or ""
    if not text:
        return DEFAULT_PORT
    if not _PORT_PATTERN.fullmatch(text) or not 1 <= int(text) <= 65535:
        raise UsageError(MSG_BAD_PORT)
    return int(text)


def service_url(port: int) -> str:
    return "http://{}:{}".format(HOST, port)


def record_path(paths: bootstrap.LocalPaths) -> Path:
    return paths.home / RUN_DIR / RECORD_NAME


def service_lock_path(paths: bootstrap.LocalPaths) -> Path:
    return paths.home / SERVICE_LOCK_NAME


# --- Ports --------------------------------------------------------------------------------


class Processes(Protocol):
    def spawn(self, argv: Sequence[str], cwd: Path, env: Mapping[str, str], log_path: Path) -> int: ...

    def alive(self, pid: int) -> bool: ...

    def command_line(self, pid: int) -> str: ...

    def terminate(self, pid: int) -> None: ...

    def kill(self, pid: int) -> None: ...


class ServiceProbe(Protocol):
    def health(self, port: int) -> str:
        """``PORT_FREE`` when nothing listens, the ``service`` name it reports, else ``PORT_OTHER``."""

    def ready(self, port: int) -> str:
        """``READY``, ``UNAVAILABLE`` (it answered not ready), or ``SILENT`` (no answer)."""


class ServiceClock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


@dataclass
class ServicePorts:
    """Every external effect; ``tools`` are the bootstrap ports used for inspection."""

    tools: bootstrap.Ports
    processes: Processes
    probe: ServiceProbe
    clock: ServiceClock

    @property
    def out(self) -> Callable[[str], None]:
        return self.tools.out


# --- Run record ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceRecord:
    pid: int
    port: int
    started_at: str
    release_id: str
    log: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "pid": self.pid,
                "port": self.port,
                "started_at": self.started_at,
                "release_id": self.release_id,
                "log": self.log,
            },
            sort_keys=True,
        )


def read_record(path: Path) -> Optional[ServiceRecord]:
    """The run record, or ``None`` when it is missing or not a valid record."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    pid, port = document.get("pid"), document.get("port")
    texts = [document.get(key) for key in ("started_at", "release_id", "log")]
    if (
        not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1
        or not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535
        or not all(isinstance(text, str) for text in texts)
    ):
        return None
    return ServiceRecord(pid, port, *texts)  # type: ignore[arg-type]


def write_record(path: Path, record: ServiceRecord) -> None:
    """Write the record atomically with mode ``0600``."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(record.to_json() + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)


def remove_record(path: Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def is_this_service(command_line: str, port: int) -> bool:
    """Whether a process command line is the service this module launches on ``port``."""

    tokens = command_line.split()
    pairs = set(zip(tokens, tokens[1:]))
    return ("uvicorn", "app.main:app") in pairs and ("--host", HOST) in pairs and ("--port", str(port)) in pairs


def verified(processes: Processes, record: ServiceRecord) -> bool:
    return processes.alive(record.pid) and is_this_service(processes.command_line(record.pid), record.port)


def find_running(
    paths: bootstrap.LocalPaths, processes: Processes, clear: bool = True
) -> Tuple[Optional[ServiceRecord], bool]:
    """``(record, stale)``: the record when its process is this service; a stale one is removed when ``clear``."""

    path = record_path(paths)
    if not path.exists() and not path.is_symlink():
        return None, False
    record = read_record(path)
    if record is not None and verified(processes, record):
        return record, False
    if clear:
        remove_record(path)
    return None, True


@contextmanager
def service_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``<local home>/.service.lock`` during a start or stop."""

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise bootstrap.BootstrapError(MSG_SERVICE_BUSY) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


# --- Launch -------------------------------------------------------------------------------


def launch_argv(ctx: bootstrap.Context, port: int) -> List[str]:
    return [
        ctx.hybrid_python, "-m", "uvicorn", "app.main:app",
        "--app-dir", str(ctx.repo_root / "backend"),
        "--host", HOST,
        "--port", str(port),
        "--no-access-log",
    ]


def launch_environment(
    ctx: bootstrap.Context,
    settings: bootstrap.Settings,
    record: LocalModelRecord,
    release_id: str,
    inherited: Mapping[str, str],
) -> dict:
    """Exactly the allowlist: a few inherited basics plus the local-RAG keys, nothing else."""

    environment = {key: inherited[key] for key in INHERITED_KEYS if inherited.get(key)}
    releases = ctx.paths.releases
    environment.update(
        {
            "MANIJERO_ACTIVE_CAMPAIGN": settings.active_campaign,
            "MANIJERO_KNOWLEDGE_RELEASE_ROOT": str(releases),
            "MANIJERO_RETRIEVAL_MODE": "hybrid",
            "MANIJERO_VECTOR_STORE": str(releases / kr.RELEASES_DIR / release_id / kr.VECTOR_STORE_DIR),
            "MANIJERO_EMBEDDING_ARTIFACT": str(ctx.paths.bge_m3),
            "MANIJERO_GENERATION_PROVIDER": "local",
            "MANIJERO_LOCAL_MODEL": record.model,
        }
    )
    return environment


# --- Output helpers -----------------------------------------------------------------------


def address_lines(port: int) -> List[str]:
    lines = [
        "  Desktop app address:          http://{}:{}".format(HOST, port),
        "  Android emulator app address: http://{}:{}".format(EMULATOR_HOST, port),
    ]
    if port == DEFAULT_PORT:
        lines.append("  These are the apps' default addresses, so nothing needs changing in the apps.")
    return lines


def _line(state: str, label: str, text: str) -> str:
    return "{:<8} {}: {}".format(state, label, text)


@dataclass(frozen=True)
class Check:
    ok: bool
    line: str


def answers_check(probe: ServiceProbe, port: int) -> Check:
    if probe.health(port) != SERVICE_NAME:
        return Check(
            False,
            _line(
                bootstrap.PROBLEM,
                "Answers",
                "the service does not answer. {}; if it happens again, send the log file to a "
                "developer.".format(FIX_RESTART),
            ),
        )
    if probe.ready(port) != READY:
        return Check(
            False,
            _line(
                bootstrap.PROBLEM,
                "Answers",
                "the service runs but cannot answer questions right now. Run {} and do its first "
                "step.".format(bootstrap.STATUS_COMMAND),
            ),
        )
    return Check(True, _line(bootstrap.OK, "Answers", "the service answers and is ready."))


def search_check(paths: bootstrap.LocalPaths, record: ServiceRecord) -> Check:
    try:
        current = kr.current_release_id(paths.releases)
    except kr.ReleaseError:
        current = None
    if current is None:
        return Check(
            False,
            _line(
                bootstrap.PROBLEM,
                "Search",
                "the published knowledge release cannot be read. Run {} and do its first step.".format(
                    bootstrap.STATUS_COMMAND
                ),
            ),
        )
    if current != record.release_id:
        return Check(
            False,
            _line(
                bootstrap.PROBLEM,
                "Search",
                "a newer knowledge release was published after the service started. {} to use "
                "it.".format(FIX_RESTART),
            ),
        )
    return Check(
        True,
        _line(
            bootstrap.OK,
            "Search",
            "started with hybrid search and knowledge release {}, which is still the published "
            "release.".format(record.release_id),
        ),
    )


def drafting_check(tools: bootstrap.Ports, model: LocalModelRecord) -> Check:
    try:
        models = tools.ollama.tags()
    except bootstrap.OllamaUnavailable as error:
        if error.code == "not_running":
            reason = "ollama_not_running" if tools.ollama.cli_present() else "ollama_not_installed"
        else:
            reason = "ollama_bad_answer"
    else:
        entry = bootstrap.find_model(models, model.model)
        if entry is not None and entry.get("digest") == model.digest:
            return Check(True, _line(bootstrap.OK, "Drafting", "Ollama answers and has the reviewed drafting model."))
        reason = "drafting_missing" if entry is None else "drafting_mismatch"
    meaning, action = bootstrap.REASONS[reason]
    if reason == "drafting_missing":
        meaning = "the reviewed drafting model is not in Ollama."
    until = "Ollama is opened" if reason == "ollama_not_running" else "this is fixed"
    return Check(
        False,
        _line(
            bootstrap.PROBLEM,
            "Drafting",
            "{} Answers continue without the drafting model until {}. {}".format(meaning, until, action),
        ),
    )


def _started_text(started_at: str) -> str:
    try:
        moment = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return "at an unknown time"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def report_running(ctx: bootstrap.Context, ports: ServicePorts, record: ServiceRecord) -> bool:
    """Print the running service's lines; ``True`` when all three checks are ``OK``."""

    out = ports.out
    out(
        "The local answer service is running at {} (process {}, started {}).".format(
            service_url(record.port), record.pid, _started_text(record.started_at)
        )
    )
    _, model = bootstrap.load_pins(ctx, ports.tools.today())
    checks = [
        answers_check(ports.probe, record.port),
        search_check(ctx.paths, record),
        drafting_check(ports.tools, model),
    ]
    for check in checks:
        out(check.line)
    for line in address_lines(record.port):
        out(line)
    out("Log file: {}".format(record.log))
    return all(check.ok for check in checks)


def _attention(port: int, verb: str) -> str:
    return "Result: {} at {}, but a check needs attention: do the first step shown above.".format(verb, service_url(port))


# --- Commands -----------------------------------------------------------------------------


class _StartStop(Exception):
    """A start prerequisite failed; nothing was written or started."""

    def __init__(self, lines: Sequence[str], fix: str) -> None:
        super().__init__(fix)
        self.lines = list(lines)
        self.fix = fix


def run_service_status(ctx: bootstrap.Context, ports: ServicePorts) -> int:
    """Say whether the service runs and whether its three checks are ``OK``."""

    out = ports.out
    try:
        record, stale = find_running(ctx.paths, ports.processes)
        if record is None:
            if stale:
                out(MSG_STALE)
            out(NOT_RUNNING)
            return 1
        if report_running(ctx, ports, record):
            out("Result: the local answer service is running at {}.".format(service_url(record.port)))
            return 0
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: the local answer service could not be checked. Do the step shown above.")
        return 1
    out(_attention(record.port, "the local answer service is running"))
    return 1


def run_stop(ctx: bootstrap.Context, ports: ServicePorts) -> int:
    """Stop the recorded service; a process that is not this service is never signalled."""

    out = ports.out
    record, stale = find_running(ctx.paths, ports.processes)
    if record is None:
        if stale:
            out(MSG_STALE)
        out(NOTHING_TO_STOP)
        return 0
    try:
        with service_lock(service_lock_path(ctx.paths)):
            record, stale = find_running(ctx.paths, ports.processes)
            if record is None:
                if stale:
                    out(MSG_STALE)
                out(NOTHING_TO_STOP)
                return 0
            out("Stopping the local answer service at {}...".format(service_url(record.port)))
            if not _end_process(ports, record):
                out(
                    "The local answer service did not stop. Restart the computer to stop it; if it "
                    "happens again, send the log file to a developer: {}".format(record.log)
                )
                out("Result: the local answer service could not be stopped.")
                return 1
            remove_record(record_path(ctx.paths))
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: nothing was stopped. {}".format(FIX_WAIT))
        return 1
    out(STOPPED)
    return 0


def _end_process(ports: ServicePorts, record: ServiceRecord) -> bool:
    """Polite stop, then a forced one only while the process still verifies as this service."""

    processes, clock = ports.processes, ports.clock
    if not verified(processes, record):
        return True
    processes.terminate(record.pid)
    if _wait_until_gone(processes, clock, record.pid, STOP_TIMEOUT_SECONDS):
        return True
    if verified(processes, record):
        processes.kill(record.pid)
        return _wait_until_gone(processes, clock, record.pid, KILL_WAIT_SECONDS)
    return True


def _wait_until_gone(processes: Processes, clock: ServiceClock, pid: int, seconds: float) -> bool:
    deadline = clock.monotonic() + seconds
    while processes.alive(pid):
        if clock.monotonic() >= deadline:
            return False
        clock.sleep(POLL_SECONDS)
    return True


def run_start(ctx: bootstrap.Context, ports: ServicePorts, port: int) -> int:
    """Check every prerequisite, then start the service in the background and wait for it."""

    out = ports.out
    record, _ = find_running(ctx.paths, ports.processes, clear=False)
    if record is not None:
        if report_running(ctx, ports, record):
            out(
                "Result: nothing new was started; the local answer service is already running at "
                "{}.".format(service_url(record.port))
            )
            return 0
        out(_attention(record.port, "nothing new was started; the local answer service is already running"))
        return 1

    out("Checking the local answer tools...")
    try:
        settings, model, release_id = _check_prerequisites(ctx, ports, port)
    except _StartStop as stop:
        for line in stop.lines:
            out(line)
        out("{} {}".format(START_FAILED, stop.fix))
        return 1

    try:
        with service_lock(service_lock_path(ctx.paths)):
            record, stale = find_running(ctx.paths, ports.processes)
            if stale:
                out(MSG_STALE)
            if record is not None:
                out(
                    "Result: nothing new was started; the local answer service is already running at "
                    "{}.".format(service_url(record.port))
                )
                return 0
            return _launch(ctx, ports, port, settings, model, release_id)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(START_FAILED, FIX_WAIT))
        return 1


def _check_prerequisites(
    ctx: bootstrap.Context, ports: ServicePorts, port: int
) -> Tuple[bootstrap.Settings, LocalModelRecord, str]:
    """Read-only: settings, pins, the six parts, other commands, then the port owner."""

    paths = ctx.paths
    if bootstrap.lock_is_held(paths.lock):
        raise _StartStop([MSG_SETUP_RUNNING], FIX_WAIT)
    try:
        settings = bootstrap.read_settings(paths.settings)
        if settings is None:
            raise _StartStop([MSG_NOT_SET_UP], FIX_RUN_SETUP)
        spec, model = bootstrap.load_pins(ctx, ports.tools.today())
    except bootstrap.SettingsError as error:
        raise _StartStop([error.message], FIX_SETTINGS) from None
    except bootstrap.BootstrapError as error:
        raise _StartStop([error.message], FIX_PIN) from None

    inspection = bootstrap.inspect(ctx, ports.tools, spec, model, settings.active_campaign)
    if not inspection.all_ok:
        lines = [line for state, line in zip(inspection.parts, bootstrap.status_lines(inspection)) if not state.ok]
        first = next(state for state in inspection.parts if not state.ok)
        raise _StartStop(lines, bootstrap.REASONS[first.reason][1])

    if bootstrap.lock_is_held(service_lock_path(paths)):
        raise _StartStop([MSG_SERVICE_BUSY], FIX_WAIT)
    _check_port(ports.probe, port)
    try:
        release_id = kr.current_release_id(paths.releases)
    except kr.ReleaseError:
        release_id = None
    if release_id is None:  # inspect reported the release OK, so this is a race with a publish
        raise _StartStop([], "Run {} and do its first step.".format(bootstrap.STATUS_COMMAND))
    return settings, model, release_id


def _check_port(probe: ServiceProbe, port: int) -> None:
    owner = probe.health(port)
    if owner == PORT_FREE:
        return
    if owner == MOCK_SERVICE_NAME:
        raise _StartStop(
            ["Port {} is in use by the mock answer service.".format(port)],
            "Run ./scripts/init.sh --mock-stop, then run this command again.",
        )
    if owner == SERVICE_NAME:
        raise _StartStop(
            [
                "Port {} is in use by a Manijero answer service that this command did not start "
                "(for example ./scripts/init.sh --backend in another window).".format(port)
            ],
            "Press Ctrl+C in the window where ./scripts/init.sh --backend runs, then run this command again.",
        )
    raise _StartStop(
        ["Port {} is in use by another program.".format(port)],
        "Close the other program that uses port {}, then run this command again.".format(port),
    )


def _launch(
    ctx: bootstrap.Context,
    ports: ServicePorts,
    port: int,
    settings: bootstrap.Settings,
    model: LocalModelRecord,
    release_id: str,
) -> int:
    out, processes = ports.out, ports.processes
    log = bootstrap.RunLog(ctx.paths.logs, LOG_COMMAND, ports.clock.now)
    log_path = log.ensure()
    path = record_path(ctx.paths)
    environment = launch_environment(ctx, settings, model, release_id, os.environ)
    out("Starting the local answer service (this can take up to a minute)...")
    pid: Optional[int] = None
    try:
        pid = processes.spawn(launch_argv(ctx, port), ctx.repo_root / "backend", environment, log_path)
        started_at = ports.clock.now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_record(path, ServiceRecord(pid, port, started_at, release_id, str(log_path)))
        failure = _wait_until_serving(ports, pid, port)
    except KeyboardInterrupt:
        _abandon(ports, pid, port, path)
        out("")
        out("The start was stopped with Ctrl+C, so the local answer service was ended.")
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again when you are ready.".format(START_FAILED, START_COMMAND))
        return 1
    except BaseException:
        _abandon(ports, pid, port, path)
        raise
    if failure is not None:
        _abandon(ports, pid, port, path)
        out(failure[0])
        out("Details are in the log file: {}".format(log_path))
        out("{} {}".format(START_FAILED, failure[1]))
        return 1

    out("")
    out(
        "The local answer service started with hybrid search, knowledge release {}, and the local "
        "drafting model {}.".format(release_id, model.model)
    )
    for line in address_lines(port):
        out(line)
    out("Next steps:")
    out("  ./scripts/init.sh --desktop          open the Desktop app")
    out("  ./scripts/init.sh --android-run      open the app on the Android emulator")
    out("  {}   stop the local answer service when you are done".format(STOP_COMMAND))
    out("Log file: {}".format(log_path))
    out("Result: the local answer service started at {}.".format(service_url(port)))
    return 0


def _wait_until_serving(ports: ServicePorts, pid: int, port: int) -> Optional[Tuple[str, str]]:
    """``None`` once ``/health`` and ``/ready`` answer; else ``(sentence, fix)``."""

    processes, probe, clock = ports.processes, ports.probe, ports.clock
    again = "Run {} again; if it fails again, send the log file to a developer.".format(START_COMMAND)
    deadline = clock.monotonic() + START_TIMEOUT_SECONDS
    while True:
        if not processes.alive(pid):
            return ("The local answer service stopped while it was starting.", again)
        if probe.health(port) == SERVICE_NAME:
            break
        if clock.monotonic() >= deadline:
            return (
                "The local answer service did not answer within {} seconds, so it was ended.".format(
                    int(START_TIMEOUT_SECONDS)
                ),
                again,
            )
        clock.sleep(POLL_SECONDS)
    if probe.ready(port) != READY:
        return (
            "The local answer service started but cannot answer questions yet, so it was ended.",
            "Run {} and do its first step.".format(bootstrap.STATUS_COMMAND),
        )
    return None


def _abandon(ports: ServicePorts, pid: Optional[int], port: int, path: Path) -> None:
    """End a process this start launched and remove its record."""

    if pid is not None:
        record = ServiceRecord(pid, port, "", "", "")
        if ports.processes.alive(pid):
            ports.processes.terminate(pid)
            if not _wait_until_gone(ports.processes, ports.clock, pid, STOP_TIMEOUT_SECONDS) and verified(
                ports.processes, record
            ):
                ports.processes.kill(pid)
                _wait_until_gone(ports.processes, ports.clock, pid, KILL_WAIT_SECONDS)
    remove_record(path)


# --- Real ports ---------------------------------------------------------------------------


class SystemProcesses:
    """Detached child processes plus ``ps`` for command-line verification."""

    def __init__(self) -> None:
        self._children: dict = {}

    def spawn(self, argv: Sequence[str], cwd: Path, env: Mapping[str, str], log_path: Path) -> int:
        with open(log_path, "ab") as log, open(os.devnull, "rb") as devnull:
            child = subprocess.Popen(  # noqa: S603 - fixed argv built by launch_argv
                [str(part) for part in argv],
                cwd=str(cwd),
                env=dict(env),
                stdin=devnull,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # survives closing the Terminal window and Ctrl+C
                close_fds=True,
            )
        self._children[child.pid] = child
        return child.pid

    def alive(self, pid: int) -> bool:
        child = self._children.get(pid)
        if child is not None:
            return child.poll() is None
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def command_line(self, pid: int) -> str:
        completed = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    def terminate(self, pid: int) -> None:
        self._signal(pid, signal.SIGTERM)

    def kill(self, pid: int) -> None:
        self._signal(pid, signal.SIGKILL)

    @staticmethod
    def _signal(pid: int, number: int) -> None:
        try:
            os.kill(pid, number)
        except ProcessLookupError:
            pass


class LoopbackProbe:
    """``GET /health`` and ``GET /ready`` on ``127.0.0.1`` (no proxy, no redirect, 2 s)."""

    def __init__(self, opener: Any = None) -> None:
        self._opener = opener if opener is not None else loopback_opener()

    def _get(self, port: int, route: str) -> Tuple[Optional[int], Any]:
        request = urllib.request.Request("http://{}:{}{}".format(HOST, port, route), method="GET")
        try:
            with self._opener.open(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
                status, raw = response.getcode(), response.read(MAX_PROBE_BYTES + 1)
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read(MAX_PROBE_BYTES + 1)
            error.close()
        try:
            document = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_PROBE_BYTES else None
        except (UnicodeDecodeError, ValueError):
            document = None
        return status, document

    def health(self, port: int) -> str:
        try:
            status, document = self._get(port, "/health")
        except urllib.error.URLError as error:
            return PORT_FREE if isinstance(error.reason, ConnectionRefusedError) else PORT_OTHER
        except ConnectionRefusedError:
            return PORT_FREE
        except Exception:  # noqa: BLE001 - reset, timeout, bad answer: something else listens
            return PORT_OTHER
        service = document.get("service") if isinstance(document, dict) else None
        if status == 200 and service in (SERVICE_NAME, MOCK_SERVICE_NAME):
            return str(service)
        return PORT_OTHER

    def ready(self, port: int) -> str:
        try:
            status, document = self._get(port, "/ready")
        except Exception:  # noqa: BLE001 - no answer at all
            return SILENT
        state = document.get("status") if isinstance(document, dict) else None
        return READY if status == 200 and state == READY else UNAVAILABLE


class SystemServiceClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
