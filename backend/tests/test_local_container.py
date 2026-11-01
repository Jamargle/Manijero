"""Answer service container: build, start, status, and stop with a fake Docker, probe, and Ollama.

Offline: no Docker, no container, no Ollama, no model, no ``torch``/``chromadb``. Each local
home is a temporary directory made ready by the fake-backed setup from
``test_local_rag_bootstrap`` (the same ``Env`` and fakes), so ``inspect`` runs for real.
Docker is an in-memory fake that interprets the argument lists this module sends; the
loopback probe answers from the fake container's state; the clock is fake.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

import test_local_rag_bootstrap as boot
import test_local_rag_service as svc_tests
from app import knowledge_release as kr
from app import local_container as lc
from app import local_rag_bootstrap as lrb
from app import local_rag_service as svc

REPO_ROOT = boot.REPO_ROOT
RECORD = boot.RECORD
REVISION = boot.REVISION
DIGEST = "sha256:" + "ab" * 32
BASE = "python:3.12-slim-bookworm@" + DIGEST
URL = "http://127.0.0.1:8000"


# --- Fakes ---------------------------------------------------------------------------------


class FakeBuild:
    def __init__(self, docker: "FakeDocker", args: List[str]) -> None:
        self.docker = docker
        self.args = args
        self.polls = docker.build_polls
        self.stopped = False

    def poll(self) -> Optional[int]:
        if self.polls > 0:
            self.polls -= 1
            return None
        if self.docker.build_code == 0:
            labels = dict(item.split("=", 1) for item in _values(self.args, "--label"))
            for tag in _values(self.args, "--tag"):
                self.docker.images[tag] = {"labels": labels, "size": 3_200_000_000}
        return self.docker.build_code

    def stop(self) -> None:
        self.stopped = True


def _values(args: Sequence[str], option: str) -> List[str]:
    return [args[position + 1] for position, item in enumerate(args) if item == option]


class FakeDocker:
    """Docker Desktop in memory: images, at most one container, and every call made."""

    def __init__(self) -> None:
        self.installed = True
        self.open = True
        self.images: Dict[str, Dict[str, Any]] = {}
        self.container: Optional[Dict[str, Any]] = None
        self.calls: List[List[str]] = []
        self.builds: List[FakeBuild] = []
        self.build_polls = 0
        self.build_code = 0
        self.run_code = 0
        self.exit_at_once = False
        self.serves = True
        self.ready_answer = svc.READY
        self.relay_code = 0
        self.stop_code = 0

    def present(self) -> bool:
        return self.installed

    def kinds(self) -> List[str]:
        return [call[0] if call[0] not in ("image", "container") else call[0] + " " + call[1] for call in self.calls]

    def _inspect(self, document: Any) -> lrb.CommandResult:
        if document is None:
            return lrb.CommandResult(1, "", "Error: No such object")
        return lrb.CommandResult(0, json.dumps([document]), "")

    def run(self, args: Sequence[str], timeout: float) -> lrb.CommandResult:
        args = [str(item) for item in args]
        self.calls.append(args)
        if args[0] == "info":
            return lrb.CommandResult(0, "27.3.1\n", "") if self.open else lrb.CommandResult(1, "", "Cannot connect")
        if args[:2] == ["image", "inspect"]:
            image = self.images.get(args[2])
            return self._inspect(None if image is None else {"Config": {"Labels": image["labels"]}, "Size": image["size"]})
        if args[:2] == ["container", "inspect"]:
            box = self.container
            if box is None:
                return self._inspect(None)
            ports = {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(box["port"])}]} if box["running"] else {}
            return self._inspect(
                {
                    "Config": {"Labels": box["labels"], "Image": box["image"]},
                    "State": {"Running": box["running"], "StartedAt": "2026-11-01T09:30:12.123456789Z"},
                    "NetworkSettings": {"Ports": ports},
                }
            )
        if args[0] == "tag":
            self.images[args[2]] = dict(self.images[args[1]])
            return lrb.CommandResult(0, "", "")
        if args[0] == "run":
            if self.run_code:
                return lrb.CommandResult(self.run_code, "", "docker: error")
            labels = dict(item.split("=", 1) for item in _values(args, "--label"))
            port = int(_values(args, "--publish")[0].split(":")[1])
            self.container = {"labels": labels, "running": not self.exit_at_once, "image": args[-1], "port": port}
            return lrb.CommandResult(0, "c0ffee\n", "")
        if args[0] == "logs":
            return lrb.CommandResult(0, "service started\n", "")
        if args[0] == "stop":
            if self.stop_code:
                return lrb.CommandResult(self.stop_code, "", "error")
            self.container["running"] = False
            return lrb.CommandResult(0, "", "")
        if args[0] == "rm":
            self.container = None
            return lrb.CommandResult(0, "", "")
        if args[0] == "exec":
            return lrb.CommandResult(self.relay_code, "", "")
        raise AssertionError("unexpected docker call: {}".format(args))

    def start(self, args: Sequence[str], log_path: Path) -> FakeBuild:
        args = [str(item) for item in args]
        self.calls.append(args)
        build = FakeBuild(self, args)
        self.builds.append(build)
        return build

    def add_foreign_container(self) -> None:
        self.container = {"labels": {}, "running": True, "image": "nginx", "port": 8000}


class FakeSource:
    def __init__(self) -> None:
        self.is_dirty = False
        self.asked: List[Sequence[str]] = []

    def head_revision(self) -> str:
        return REVISION

    def dirty(self, paths: Sequence[str]) -> bool:
        self.asked.append(tuple(paths))
        return self.is_dirty


class FakeProbe:
    """``/health`` answers as the service while the fake container runs and serves."""

    def __init__(self, docker: FakeDocker) -> None:
        self.docker = docker
        self.owner = svc.PORT_FREE
        self.calls: List[tuple] = []

    def _ours(self) -> bool:
        box = self.docker.container
        return bool(box and box["running"] and box["labels"].get(lc.MANAGED_LABEL) == "1")

    def health(self, port: int) -> str:
        self.calls.append(("health", port))
        if self._ours():
            return svc.SERVICE_NAME if self.docker.serves else svc.PORT_OTHER
        return self.owner

    def ready(self, port: int) -> str:
        self.calls.append(("ready", port))
        return self.docker.ready_answer if self._ours() and self.docker.serves else svc.SILENT


class Harness:
    def __init__(self, env: boot.Env) -> None:
        self.env = env
        self.docker = FakeDocker()
        self.source = FakeSource()
        self.processes = svc_tests.FakeProcesses()
        self.probe = FakeProbe(self.docker)
        self.clock = svc_tests.FakeServiceClock()
        self.pin = env.tmp / "base-image.json"
        write_pin(self.pin)
        self.ports = lc.ContainerPorts(
            tools=env.ports,
            processes=self.processes,
            probe=self.probe,
            clock=self.clock,
            docker=self.docker,
            source=self.source,
        )

    @property
    def lines(self) -> List[str]:
        return self.env.lines

    @property
    def output(self) -> str:
        return self.env.output

    @property
    def release_id(self) -> str:
        return str(kr.current_release_id(self.env.paths.releases))

    @property
    def tag(self) -> str:
        return "manijero-backend:{}-{}".format(self.release_id, REVISION[:12])

    def build(self) -> int:
        self.env._reset()
        return lc.run_build(self.env.ctx, self.ports, base_pin=self.pin)

    def start(self, port: int = 8000) -> int:
        self.env._reset()
        return lc.run_start(self.env.ctx, self.ports, port)

    def status(self, port: int = 8000) -> int:
        self.env._reset()
        return lc.run_status(self.env.ctx, self.ports, port)

    def stop(self) -> int:
        self.env._reset()
        return lc.run_stop(self.env.ctx, self.ports)

    def forget(self) -> None:
        self.docker.calls.clear()
        self.probe.calls.clear()


def write_pin(path: Path, **changes: Any) -> None:
    document = {
        "image": "python:3.12-slim-bookworm",
        "digest": DIGEST,
        "reviewed_on": "2026-11-01",
        "reason": "test pin",
    }
    document.update(changes)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.fixture
def ready(tmp_path: Path) -> boot.Env:
    env = boot.Env(tmp_path)
    assert env.setup("yes") == 0, env.output
    env.forget_calls()
    return env


@pytest.fixture
def harness(ready: boot.Env) -> Harness:
    return Harness(ready)


@pytest.fixture
def built(harness: Harness) -> Harness:
    assert harness.build() == 0, harness.output
    harness.forget()
    return harness


@pytest.fixture
def running(built: Harness) -> Harness:
    assert built.start() == 0, built.output
    built.forget()
    return built


def check_lines(output: str) -> List[str]:
    return [line for line in output.splitlines() if line.split(None, 1)[:1] in (["OK"], ["PROBLEM"], ["MISSING"])]


def hold(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def change_knowledge(env: boot.Env) -> None:
    svc_tests._change_knowledge(env)


# --- 1. Build when everything is ready -----------------------------------------------------


def test_build_when_ready_runs_the_fixed_build_and_reports_the_tag(harness: Harness) -> None:
    env = harness.env
    harness.docker.build_polls = 130  # about two minutes with one-second polls

    code = harness.build()

    assert code == 0, harness.output
    assert harness.lines[0] == "Checking what the image needs..."
    [build] = harness.docker.builds
    release_dir = env.paths.releases / "releases" / harness.release_id
    assert build.args == [
        "build",
        "--file", str(REPO_ROOT / "backend" / "container" / "Dockerfile"),
        "--build-context", "knowledge-release={}".format(release_dir),
        "--build-context", "embedding-model={}".format(env.paths.bge_m3),
        "--build-arg", "BASE_IMAGE=" + BASE,
        "--build-arg", "RELEASE_ID=" + harness.release_id,
        "--build-arg", "LOCAL_MODEL=" + RECORD["model"],
        "--label", "org.manijero.managed=1",
        "--label", "org.opencontainers.image.revision=" + REVISION,
        "--label", "org.manijero.knowledge-release=" + harness.release_id,
        "--label", "org.manijero.campaign=2026",
        "--label", "org.manijero.embedding-revision=" + lrb.load_pins(env.ctx, boot.NOW.date())[0].model_revision,
        "--label", "org.manijero.local-model=" + RECORD["model"],
        "--label", "org.manijero.base-image=" + BASE,
        "--tag", harness.tag,
        "--tag", "manijero-backend:local",
        "--progress", "plain",
        str(REPO_ROOT),
    ]
    assert "first build can take 10 to 30 minutes" in harness.output and "but no model" in harness.output
    assert [line for line in harness.lines if line.startswith("Still building")] == [
        "Still building (1 minute so far)...",
        "Still building (2 minutes so far)...",
    ]
    assert "Knowledge release: {}".format(harness.release_id) in harness.lines
    assert "Size: about 3.2 GB" in harness.lines
    assert harness.lines[-1] == "Result: the image {} was built with knowledge release {}.".format(harness.tag, harness.release_id)
    assert harness.docker.images["manijero-backend:local"]["labels"]["org.manijero.knowledge-release"] == harness.release_id
    assert harness.source.asked == [lc.COPIED_PATHS]
    assert not harness.env.runner.calls and not harness.env.opener.requests and not harness.env.ollama.pulls


def test_build_output_goes_only_to_the_log_file(harness: Harness) -> None:
    assert harness.build() == 0
    [log_line] = [line for line in harness.lines if line.startswith("Build details go to the log file: ")]
    log = Path(log_line.split(": ", 1)[1])
    assert log.parent == harness.env.paths.logs and log.name.startswith("container-build-")
    assert "$ docker build" in log.read_text(encoding="utf-8")


# --- 2. Build when the image is already up to date -----------------------------------------


def test_build_again_builds_nothing_and_points_local_at_the_image(built: Harness) -> None:
    built.docker.images["manijero-backend:local"] = {"labels": {}, "size": 1}

    code = built.build()

    assert code == 0, built.output
    assert len(built.docker.builds) == 1  # only the first build
    assert ["tag", built.tag, "manijero-backend:local"] in built.docker.calls
    assert built.docker.images["manijero-backend:local"]["labels"]["org.opencontainers.image.revision"] == REVISION
    assert built.lines[-1] == "Result: nothing new was built; {} is already up to date.".format(built.tag)


# --- 3. Build while a prerequisite is missing ----------------------------------------------


def _corrupt_model(harness: Harness) -> None:
    target = next(path for path in harness.env.paths.bge_m3.rglob("*") if path.is_file())
    target.write_bytes(b"damaged")


@pytest.mark.parametrize(
    "arrange, expected, fix",
    [
        (lambda h: setattr(h.docker, "installed", False), "Docker Desktop is not installed", "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"),
        (lambda h: setattr(h.docker, "open", False), "Docker Desktop is not open", "Open the Docker Desktop app"),
        (lambda h: h.env.paths.settings.unlink(), "not set up yet", "Run ./scripts/init.sh --local-rag-setup."),
        (_corrupt_model, "PROBLEM  Search model (bge-m3): a file is damaged", "Run ./scripts/init.sh --local-rag-setup; it fetches only the bad files again."),
        (lambda h: change_knowledge(h.env), "PROBLEM  Knowledge release: the knowledge files changed", "Run ./scripts/init.sh --local-rag-setup to rebuild it."),
        (lambda h: setattr(h.source, "is_dirty", True), "not saved in Git", "A developer must save or undo the changes"),
        (lambda h: write_pin(h.pin, digest=""), "base-image pin backend/container/base-image.json is not valid", "A developer must review backend/container/base-image.json."),
        (lambda h: write_pin(h.pin, image="python@latest"), "is not valid", "A developer must review"),
        (lambda h: hold(lc.lock_path(h.env.paths)), "Another container command is running", "Wait for the other command to finish"),
        (lambda h: hold(h.env.paths.lock), "A setup of the local answer tools is running", "Wait for the other command to finish"),
    ],
    ids=["docker-missing", "docker-closed", "never-set-up", "model-damaged", "release-changed", "dirty", "no-digest", "bad-image", "lock", "setup-running"],
)
def test_a_missing_build_prerequisite_builds_nothing_and_changes_nothing(harness: Harness, arrange, expected: str, fix: str) -> None:
    held = arrange(harness)
    before = boot.snapshot(harness.env.paths.home)

    code = harness.build()

    assert code == 1
    assert expected in harness.output
    assert harness.lines[-1].startswith(lc.NOT_BUILT + " ") and fix in harness.lines[-1]
    assert not harness.docker.builds
    assert not [call for call in harness.docker.calls if call[0] in ("tag", "run", "rm", "stop")]
    assert boot.snapshot(harness.env.paths.home) == before
    assert not harness.env.ollama.pulls and not harness.env.opener.requests
    if isinstance(held, int):
        os.close(held)


def test_every_failed_build_prerequisite_is_listed_and_the_first_fix_is_the_result(harness: Harness) -> None:
    harness.docker.open = False
    harness.source.is_dirty = True

    assert harness.build() == 1
    assert harness.lines[1:3] == [lc.MSG_DOCKER_CLOSED, lc.MSG_DIRTY]
    assert harness.lines[-1] == "{} {}".format(lc.NOT_BUILT, lc.FIX_OPEN_DOCKER)


# --- 4. Build fails or is interrupted ------------------------------------------------------


def test_a_failed_build_moves_no_tag_and_names_the_log(built: Harness) -> None:
    assert built.start() == 0
    built.forget()
    change_knowledge(built.env)
    built.env.setup()  # a new release is published; the image is now older
    built.forget()
    old_local = dict(built.docker.images["manijero-backend:local"])
    built.docker.build_code = 1

    code = built.build()

    assert code == 1
    assert "free disk space" in built.output
    log_line = next(line for line in built.lines if line.startswith("Details are in the log file: "))
    assert Path(log_line.split(": ", 1)[1]).exists()
    assert built.lines[-1].startswith(lc.NOT_BUILT)
    assert built.docker.images["manijero-backend:local"] == old_local
    assert not [call for call in built.docker.calls if call[0] in ("tag", "stop", "rm", "run")]
    assert built.docker.container is not None and built.docker.container["running"]


def test_ctrl_c_during_the_build_stops_it_and_moves_no_tag(harness: Harness) -> None:
    harness.docker.build_polls = 1000

    def interrupt() -> None:
        if harness.clock.t >= 5:
            raise KeyboardInterrupt

    harness.clock.on_sleep = interrupt

    code = harness.build()

    assert code == 1
    [build] = harness.docker.builds
    assert build.stopped
    assert "stopped with Ctrl+C, so no image was changed" in harness.output
    assert harness.lines[-1] == "{} Run {} again when you are ready.".format(lc.NOT_BUILT, lc.BUILD_COMMAND)
    assert "manijero-backend:local" not in harness.docker.images
    assert not [call for call in harness.docker.calls if call[0] == "tag"]


# --- 5. Start when everything is ready -----------------------------------------------------


def test_start_when_ready_runs_the_fixed_container_and_waits_for_it(built: Harness, monkeypatch) -> None:
    monkeypatch.setenv("MANIJERO_DEPLOYMENT_PROFILE", "pilot")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")

    code = built.start()

    assert code == 0, built.output
    [run] = [call for call in built.docker.calls if call[0] == "run"]
    assert run == [
        "run", "--detach", "--init",
        "--name", "manijero-backend",
        "--label", "org.manijero.managed=1",
        "--publish", "127.0.0.1:8000:8000",
        "--env", "MANIJERO_ACTIVE_CAMPAIGN=2026",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--restart", "no",
        "manijero-backend:local",
    ]
    assert _values(run, "--env") == ["MANIJERO_ACTIVE_CAMPAIGN=2026"]
    assert ("health", 8000) in built.probe.calls and ("ready", 8000) in built.probe.calls
    assert "  Desktop app address:          http://127.0.0.1:8000" in built.lines
    assert "  Android emulator app address: http://10.0.2.2:8000" in built.lines
    assert "  These are the apps' default addresses, so nothing needs changing in the apps." in built.lines
    assert any(built.tag in line and built.release_id in line for line in built.lines)
    assert built.lines[-1] == "Result: the answer service in the container started at {}.".format(URL)


def test_start_on_a_custom_port_publishes_only_that_loopback_port(built: Harness) -> None:
    assert built.start(port=8765) == 0, built.output
    [run] = [call for call in built.docker.calls if call[0] == "run"]
    assert _values(run, "--publish") == ["127.0.0.1:8765:8000"]
    assert "These are the apps' default addresses" not in built.output


# --- 6. Start blocked by the image, Ollama, or the port ------------------------------------


def _older_release(h: Harness) -> None:
    h.docker.images["manijero-backend:local"]["labels"]["org.manijero.knowledge-release"] = "0" * 16


def _other_campaign(h: Harness) -> None:
    h.docker.images["manijero-backend:local"]["labels"]["org.manijero.campaign"] = "2025"


def _local_rag_service(h: Harness) -> None:
    h.probe.owner = svc.SERVICE_NAME
    h.processes.add(41_000, "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log")
    svc.write_record(svc.record_path(h.env.paths), svc.ServiceRecord(41_000, 8000, "2026-11-01T09:00:00Z", "r", "/tmp/x"))


@pytest.mark.parametrize(
    "arrange, said, step",
    [
        (lambda h: h.docker.images.clear(), "no answer service image", "Run ./scripts/init.sh --container-build first."),
        (_older_release, "older knowledge release or another campaign", "Run ./scripts/init.sh --container-build to package the current knowledge."),
        (_other_campaign, "older knowledge release or another campaign", "Run ./scripts/init.sh --container-build to package the current knowledge."),
        (lambda h: setattr(h.env.ollama, "running", False), "PROBLEM  Drafting model: Ollama is not running", "Open the Ollama app"),
        (lambda h: h.env.ollama._install("sha256:" + "0" * 64), "PROBLEM  Drafting model: Ollama has a different version", "Run ./scripts/init.sh --local-rag-setup"),
        (lambda h: setattr(h.probe, "owner", svc.MOCK_SERVICE_NAME), "in use by the mock answer service", "./scripts/init.sh --mock-stop"),
        (_local_rag_service, "in use by the local answer service", "Run ./scripts/init.sh --local-rag-stop"),
        (lambda h: setattr(h.probe, "owner", svc.SERVICE_NAME), "a Manijero answer service that this command did not start", "Press Ctrl+C in the window where ./scripts/init.sh --backend runs"),
        (lambda h: setattr(h.probe, "owner", svc.PORT_OTHER), "in use by another program", "Close the other program that uses port 8000"),
        (lambda h: h.docker.add_foreign_container(), "Manijero did not create it", "Rename or delete that container in Docker Desktop"),
        (lambda h: setattr(h.docker, "open", False), "Docker Desktop is not open", "Open the Docker Desktop app"),
        (lambda h: h.env.paths.settings.unlink(), "not set up yet", "Run ./scripts/init.sh --local-rag-setup."),
    ],
    ids=["no-image", "older-release", "other-campaign", "ollama-closed", "digest-mismatch", "port-mock", "port-local-rag",
         "port-backend", "port-other", "foreign-container", "docker-closed", "never-set-up"],
)
def test_a_blocked_start_names_the_step_and_creates_nothing(built: Harness, arrange, said: str, step: str) -> None:
    arrange(built)
    foreign = dict(built.docker.container) if built.docker.container else None
    before = boot.snapshot(built.env.paths.home)

    code = built.start()

    assert code == 1
    assert said in built.output
    assert built.lines[-1].startswith(lc.START_FAILED + " ") and step in built.lines[-1]
    assert not [call for call in built.docker.calls if call[0] in ("run", "rm", "stop", "tag")]
    assert built.docker.container == foreign
    assert boot.snapshot(built.env.paths.home) == before


# --- 7. Start while already running, or after an unclean end -------------------------------


def test_start_while_running_starts_nothing(running: Harness) -> None:
    code = running.start()

    assert code == 0, running.output
    assert not [call for call in running.docker.calls if call[0] == "run"]
    assert [line.split()[0] for line in check_lines(running.output)] == ["OK"] * 4
    assert running.lines[-1] == (
        "Result: nothing new was started; the answer service in the container is already running at {}.".format(URL)
    )


def test_start_while_running_with_a_problem_says_which_check_needs_attention(running: Harness) -> None:
    running.docker.ready_answer = svc.UNAVAILABLE

    assert running.start() == 1
    assert running.lines[-1] == (
        "Result: nothing new was started; the answer service in the container is already running at {}, but a "
        "check needs attention: do the first step shown above.".format(URL)
    )


def test_a_stopped_leftover_container_is_cleared_and_the_start_continues(running: Harness) -> None:
    running.docker.container["running"] = False

    code = running.start()

    assert code == 0, running.output
    assert lc.MSG_LEFTOVER in running.lines
    kinds = running.docker.kinds()
    assert kinds.index("logs") < kinds.index("rm") < kinds.index("run")
    assert running.docker.container is not None and running.docker.container["running"]


# --- 8. Start fails after the container was created ----------------------------------------


def _timeout(h: Harness) -> None:
    h.docker.serves = False


def _ctrl_c(h: Harness) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    h.docker.serves = False
    h.clock.on_sleep = interrupt


@pytest.mark.parametrize(
    "arrange, said",
    [
        (lambda h: setattr(h.docker, "exit_at_once", True), "stopped while it was starting"),
        (_timeout, "did not answer within 120 seconds"),
        (lambda h: setattr(h.docker, "ready_answer", svc.UNAVAILABLE), "cannot answer questions yet"),
        (_ctrl_c, "stopped with Ctrl+C, so the answer service container was removed"),
        (lambda h: setattr(h.docker, "run_code", 125), "Docker Desktop could not start the answer service container"),
    ],
    ids=["exited", "health-timeout", "ready-503", "ctrl-c", "run-failed"],
)
def test_a_failed_start_saves_the_output_and_removes_the_container(built: Harness, arrange, said: str) -> None:
    arrange(built)

    code = built.start()

    assert code == 1
    assert said in built.output
    assert built.lines[-1].startswith(lc.START_FAILED)
    log_line = next(line for line in built.lines if line.startswith("Details are in the log file: "))
    log = Path(log_line.split(": ", 1)[1])
    assert log.parent == built.env.paths.logs
    assert built.docker.container is None
    if built.docker.run_code == 0:
        assert "service started" in log.read_text(encoding="utf-8")
        assert ["rm", "--force", "manijero-backend"] in built.docker.calls


# --- 9. Status -----------------------------------------------------------------------------


def test_status_when_running_and_ready_is_four_ok_lines(running: Harness) -> None:
    code = running.status()

    assert code == 0, running.output
    lines = check_lines(running.output)
    assert [line.split(None, 2)[1] for line in lines] == ["Container:", "Answers:", "Search:", "Drafting:"]
    assert all(line.startswith("OK ") for line in lines)
    assert running.tag in lines[0] and REVISION[:12] in lines[0] and "2026-11-01 09:30 UTC" in lines[0]
    assert ["exec", "manijero-backend", "python", "/opt/manijero/backend/container/ollama_relay.py", "--check"] in running.docker.calls
    assert "  Android emulator app address: http://10.0.2.2:8000" in running.lines
    assert running.lines[-1] == "Result: the answer service in the container is running at {}.".format(URL)


@pytest.mark.parametrize(
    "arrange, label, said",
    [
        (lambda h: setattr(h.docker, "ready_answer", svc.UNAVAILABLE), "Answers", "cannot answer questions right now"),
        (_older_release, "Search", "a newer knowledge release was published after the image was built"),
        (lambda h: setattr(h.env.ollama, "running", False), "Drafting", "Answers continue without the drafting model until Ollama is opened"),
        (lambda h: setattr(h.docker, "relay_code", 1), "Drafting", "the answer service in the container cannot reach it"),
    ],
    ids=["answers", "search", "host-ollama", "relay"],
)
def test_status_names_each_problem_and_still_prints_the_addresses(running: Harness, arrange, label: str, said: str) -> None:
    arrange(running)

    code = running.status()

    assert code == 1
    problems = [line for line in check_lines(running.output) if line.startswith("PROBLEM")]
    assert len(problems) == 1 and problems[0].split(None, 2)[1] == label + ":" and said in problems[0]
    assert "  Desktop app address:          http://127.0.0.1:8000" in running.lines
    assert running.lines[-1] == (
        "Result: the answer service in the container is running at {}, but a check needs attention: do the "
        "first step shown above.".format(URL)
    )


def test_status_without_a_container_or_with_docker_closed_makes_no_probe(built: Harness) -> None:
    assert built.status() == 1
    assert built.lines[-1] == lc.NOT_RUNNING == (
        "Result: the answer service in the container is not running. Start it with ./scripts/init.sh --container-start."
    )
    built.docker.open = False
    assert built.status() == 1
    assert "Docker Desktop is not open" in built.output and built.lines[-1] == lc.NOT_RUNNING
    built.docker.add_foreign_container()
    built.docker.open = True
    assert built.status() == 1 and built.lines[-1] == lc.NOT_RUNNING
    assert not built.probe.calls
    assert not [call for call in built.docker.calls if call[0] == "exec"]


# --- 10. Stop ------------------------------------------------------------------------------


def test_stop_stops_saves_the_output_and_removes_the_container(running: Harness) -> None:
    code = running.stop()

    assert code == 0, running.output
    stops = [call for call in running.docker.calls if call[0] in ("stop", "logs", "rm")]
    assert stops == [["stop", "--time", "10", "manijero-backend"], ["logs", "manijero-backend"], ["rm", "--force", "manijero-backend"]]
    log_line = next(line for line in running.lines if line.startswith("Its output was saved to the log file: "))
    assert "service started" in Path(log_line.split(": ", 1)[1]).read_text(encoding="utf-8")
    assert running.lines[-1] == "Result: the answer service in the container has stopped."
    assert running.docker.container is None and "manijero-backend:local" in running.docker.images

    assert running.stop() == 0
    assert running.lines == ["Result: the answer service in the container was not running, so there was nothing to stop."]


def test_stop_with_docker_closed_or_missing_has_nothing_to_stop(running: Harness) -> None:
    for attribute in ("open", "installed"):
        setattr(running.docker, attribute, False)
        assert running.stop() == 0
        assert running.lines == [lc.NOTHING_TO_STOP]
    assert not [call for call in running.docker.calls if call[0] in ("stop", "rm")]


def test_a_container_without_the_manijero_label_is_never_stopped_or_removed(harness: Harness) -> None:
    harness.docker.add_foreign_container()

    assert harness.stop() == 0
    assert harness.lines[-1] == lc.NOTHING_TO_STOP
    assert harness.docker.container is not None and harness.docker.container["running"]
    assert not [call for call in harness.docker.calls if call[0] in ("stop", "rm", "logs")]


def test_a_stop_that_fails_says_so(running: Harness) -> None:
    running.docker.stop_code = 1

    assert running.stop() == 1
    assert running.lines[-1] == "Result: the answer service in the container could not be stopped."


def test_stop_while_another_container_command_runs_changes_nothing(running: Harness) -> None:
    handle = hold(lc.lock_path(running.env.paths))
    try:
        assert running.stop() == 1
        assert running.lines[-1].startswith("Result: nothing was stopped.")
        assert running.docker.container["running"]
    finally:
        os.close(handle)


# --- 11. Misuse ----------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["container-build", "container-start", "container-status", "container-stop"])
@pytest.mark.parametrize("value", ["0", "65536", "abc"])
def test_a_bad_port_is_misuse_and_touches_nothing(harness: Harness, monkeypatch, capsys, command: str, value: str) -> None:
    monkeypatch.setenv(svc.PORT_ENV, value)
    harness.env._reset()

    code = boot.local_cli.main([command], ctx=harness.env.ctx, container_ports=harness.ports)

    assert code == 2
    assert "between 1 and 65535" in capsys.readouterr().err
    assert not harness.docker.calls and not harness.lines


def test_an_unexpected_error_prints_one_sentence_and_logs_the_traceback(harness: Harness, monkeypatch) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(lc, "run_status", broken)
    harness.env._reset()

    code = boot.local_cli.main(["container-status"], ctx=harness.env.ctx, container_ports=harness.ports)

    assert code == 1
    assert "Something unexpected went wrong" in harness.output
    assert harness.lines[-1] == "Result: the answer service in the container could not be checked."
    assert "Traceback" not in harness.output


# --- 12. Safety and privacy ----------------------------------------------------------------


def test_no_output_label_or_log_line_contains_corpus_text(running: Harness) -> None:
    running.status()
    running.env.ollama.running = False
    running.status()
    running.stop()
    running.build()
    texts = list(running.env.all_output + running.env.lines)
    texts += [json.dumps(image["labels"]) for image in running.docker.images.values()]
    texts += [" ".join(call) for call in running.docker.calls]
    texts += [path.read_text(encoding="utf-8") for path in running.env.paths.logs.glob("container*.log")]
    combined = "\n".join(texts)
    passages = json.loads((boot.KNOWLEDGE / kr.PASSAGES_FILE).read_text(encoding="utf-8"))["passages"]
    for passage in passages:
        assert passage["text"][:40] not in combined
