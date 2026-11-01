"""Build, start, check, and stop the answer service as a container in Docker Desktop.

Operator-only and stdlib-only at import time; the answer service never imports this
module. It packages the unchanged service (``app.main:app``), its pinned Python runtime,
the published knowledge release, and the pin-verified ``bge-m3`` search model from the
local home (default ``~/manijero/local``) into one image, and runs that image on this Mac
with the same hybrid search and local drafting as ``--local-rag-start``:

* :func:`run_build` checks every prerequisite (Docker Desktop, the image parts of
  ``--local-rag-status``, uncommitted copied files, the base-image pin, other commands)
  before it builds anything, then runs ``docker build`` with fixed arguments
  (:func:`build_argv`); an image with the same code and release is reused instead;
* :func:`run_start` checks the image, Ollama, and the port, then runs the image with fixed
  arguments (:func:`run_argv`) and waits until ``/health`` and ``/ready`` answer;
* :func:`run_status` reports four checks (container, answers, search, drafting);
* :func:`run_stop` stops and removes the container, but only one carrying the Manijero label.

Drafting stays on the host Mac: inside the container a fixed relay
(``backend/container/ollama_relay.py``) forwards the service's constant loopback Ollama
address to ``host.docker.internal:11434``. Messages are fixed English sentences with no
question, passage text, land value, or token; Docker output goes only to log files under
``<local home>/logs/``. External effects go through injected ports
(:class:`ContainerPorts`) so tests use fakes; ``MANIJERO_DOCKER_CLI`` is for tests only.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple

from app import knowledge_release as kr
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service
from app.local_generation import LocalModelRecord

BUILD_COMMAND = "./scripts/init.sh --container-build"
START_COMMAND = "./scripts/init.sh --container-start"
STATUS_COMMAND = "./scripts/init.sh --container-status"
STOP_COMMAND = "./scripts/init.sh --container-stop"

DOCKER_CLI_ENV = "MANIJERO_DOCKER_CLI"  # tests only
DOCKER_DOWNLOAD_URL = "https://www.docker.com/products/docker-desktop/"

IMAGE_REPOSITORY = "manijero-backend"
LOCAL_TAG = IMAGE_REPOSITORY + ":local"
CONTAINER_NAME = "manijero-backend"
CONTAINER_PORT = 8000

MANAGED_LABEL = "org.manijero.managed"
LABEL_REVISION = "org.opencontainers.image.revision"
LABEL_RELEASE = "org.manijero.knowledge-release"
LABEL_CAMPAIGN = "org.manijero.campaign"
LABEL_EMBEDDING = "org.manijero.embedding-revision"
LABEL_MODEL = "org.manijero.local-model"
LABEL_BASE = "org.manijero.base-image"

# Tracked paths the image copies (Dockerfile.dockerignore is the allowlist that matches these).
COPIED_PATHS = (
    "backend/app",
    "backend/config",
    "backend/requirements.txt",
    "backend/requirements-embeddings.txt",
    "backend/requirements-hybrid.txt",
    "backend/deploy/requirements-production.txt",
    "backend/container",
)
CONTAINER_DIR = Path("backend") / "container"
DOCKERFILE = CONTAINER_DIR / "Dockerfile"
BASE_IMAGE_FILE = CONTAINER_DIR / "base-image.json"
RELAY_CHECK = ("python", "/opt/manijero/backend/container/ollama_relay.py", "--check")

# The local-RAG parts the image packages (the drafting model stays in Ollama on the host).
IMAGE_PARTS = ("model", "store", "release")

LOCK_NAME = ".container.lock"
BUILD_LOG = "container-build"
CONTAINER_LOG = "container"

DOCKER_TIMEOUT_SECONDS = 30.0
INFO_TIMEOUT_SECONDS = 20.0
LOGS_TIMEOUT_SECONDS = 60.0
STOP_TIMEOUT_SECONDS = 10
START_TIMEOUT_SECONDS = 120.0
POLL_SECONDS = 1.0
TICK_SECONDS = 60.0

_IMAGE_PATTERN = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*:[A-Za-z0-9_][A-Za-z0-9._-]{0,127}")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_STARTED_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")

DOCKER_MISSING = "missing"
DOCKER_CLOSED = "closed"
DOCKER_READY = "ready"

FIX_INSTALL_DOCKER = "Install Docker Desktop from {}, open it once, then run this command again.".format(
    DOCKER_DOWNLOAD_URL
)
FIX_OPEN_DOCKER = "Open the Docker Desktop app, wait until it says it is running, then run this command again."
MSG_DOCKER_MISSING = "Docker Desktop is not installed on this computer. " + FIX_INSTALL_DOCKER
MSG_DOCKER_CLOSED = "Docker Desktop is not open, or it is still starting. " + FIX_OPEN_DOCKER
MSG_DIRTY = "Files that go into the image have changes that are not saved in Git, so the image could not say which code it holds."
FIX_DIRTY = "A developer must save or undo the changes, then run this command again."
MSG_BAD_BASE = "The reviewed base-image pin {} is not valid.".format(BASE_IMAGE_FILE)
FIX_BAD_BASE = "A developer must review {}.".format(BASE_IMAGE_FILE)
MSG_BUSY = (
    "Another container command is running in another Terminal window. Wait until it shows its Result: "
    "line, then run this command again."
)
MSG_NO_IMAGE = "There is no answer service image on this computer yet."
FIX_BUILD_FIRST = "Run {} first.".format(BUILD_COMMAND)
MSG_OLD_IMAGE = (
    "The answer service image holds an older knowledge release or another campaign than the settings file."
)
FIX_REBUILD = "Run {} to package the current knowledge.".format(BUILD_COMMAND)
MSG_FOREIGN = "A container named {} exists in Docker Desktop, but Manijero did not create it.".format(CONTAINER_NAME)
FIX_FOREIGN = "Rename or delete that container in Docker Desktop, then run this command again."
MSG_LEFTOVER = "An earlier answer service container ended without being stopped; it was cleared."
FIX_STATUS = "Run {} and do its first step.".format(bootstrap.STATUS_COMMAND)
FIX_CONTAINER_RESTART = "Run {}, then {}".format(STOP_COMMAND, START_COMMAND)  # starts a sentence

NOT_BUILT = "Result: the image was not built."
START_FAILED = "Result: the answer service in the container did not start."
STOPPED = "Result: the answer service in the container has stopped."
NOTHING_TO_STOP = "Result: the answer service in the container was not running, so there was nothing to stop."
NOT_RUNNING = "Result: the answer service in the container is not running. Start it with {}.".format(START_COMMAND)


def lock_path(paths: bootstrap.LocalPaths) -> Path:
    return paths.home / LOCK_NAME


def versioned_tag(release_id: str, revision: str) -> str:
    return "{}:{}-{}".format(IMAGE_REPOSITORY, release_id, revision[:12])


# --- Ports --------------------------------------------------------------------------------


class RunningCommand(Protocol):
    def poll(self) -> Optional[int]: ...

    def stop(self) -> None:
        """End the command (politely, then for sure) and wait for it."""


class DockerCli(Protocol):
    def present(self) -> bool: ...

    def run(self, args: Sequence[str], timeout: float) -> bootstrap.CommandResult: ...

    def start(self, args: Sequence[str], log_path: Path) -> RunningCommand:
        """Run a long command (the build) with its output appended to ``log_path`` only."""


class SourceTree(Protocol):
    def head_revision(self) -> str: ...

    def dirty(self, paths: Sequence[str]) -> bool: ...


@dataclass
class ContainerPorts:
    """Every external effect; ``tools``/``processes``/``probe``/``clock`` as for the service."""

    tools: bootstrap.Ports
    processes: service.Processes
    probe: service.ServiceProbe
    clock: service.ServiceClock
    docker: DockerCli
    source: SourceTree

    @property
    def out(self) -> Callable[[str], None]:
        return self.tools.out


# --- Docker facts -------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageInfo:
    labels: Mapping[str, str]
    size_bytes: int


@dataclass(frozen=True)
class ContainerInfo:
    labels: Mapping[str, str]
    running: bool
    started_at: str
    host_port: Optional[int]

    @property
    def managed(self) -> bool:
        return self.labels.get(MANAGED_LABEL) == "1"


def docker_state(docker: DockerCli) -> str:
    if not docker.present():
        return DOCKER_MISSING
    result = docker.run(["info", "--format", "{{.ServerVersion}}"], INFO_TIMEOUT_SECONDS)
    return DOCKER_READY if result.returncode == 0 and result.stdout.strip() else DOCKER_CLOSED


def _inspect(docker: DockerCli, kind: str, name: str) -> Optional[Mapping[str, Any]]:
    result = docker.run([kind, "inspect", name], DOCKER_TIMEOUT_SECONDS)
    if result.returncode != 0:
        return None
    try:
        document = json.loads(result.stdout)
    except ValueError:
        return None
    if isinstance(document, list) and document and isinstance(document[0], dict):
        return document[0]
    return None


def _labels(config: Any) -> Dict[str, str]:
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        return {}
    return {str(key): str(value) for key, value in labels.items()}


def image_info(docker: DockerCli, reference: str) -> Optional[ImageInfo]:
    document = _inspect(docker, "image", reference)
    if document is None:
        return None
    size = document.get("Size")
    return ImageInfo(_labels(document.get("Config")), size if isinstance(size, int) and size > 0 else 0)


def container_info(docker: DockerCli) -> Optional[ContainerInfo]:
    document = _inspect(docker, "container", CONTAINER_NAME)
    if document is None:
        return None
    state = document.get("State") if isinstance(document.get("State"), dict) else {}
    host_port: Optional[int] = None
    network = document.get("NetworkSettings")
    bindings = network.get("Ports") if isinstance(network, dict) else None
    entries = bindings.get("{}/tcp".format(CONTAINER_PORT)) if isinstance(bindings, dict) else None
    if isinstance(entries, list):
        for entry in entries:
            text = entry.get("HostPort") if isinstance(entry, dict) else None
            if isinstance(text, str) and text.isdigit():
                host_port = int(text)
                break
    return ContainerInfo(
        labels=_labels(document.get("Config")),
        running=state.get("Running") is True,
        started_at=str(state.get("StartedAt") or ""),
        host_port=host_port,
    )


# --- Image inputs and fixed arguments ------------------------------------------------------


def load_base_image(path: Path) -> str:
    """``<tag>@<digest>`` from ``base-image.json``; an invalid pin is a developer problem."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise bootstrap.BootstrapError(MSG_BAD_BASE) from None
    if not isinstance(document, dict) or set(document) != {"image", "digest", "reviewed_on", "reason"}:
        raise bootstrap.BootstrapError(MSG_BAD_BASE)
    image, digest, reviewed, reason = (document.get(key) for key in ("image", "digest", "reviewed_on", "reason"))
    if not (
        isinstance(image, str) and _IMAGE_PATTERN.fullmatch(image)
        and isinstance(digest, str) and _DIGEST_PATTERN.fullmatch(digest)
        and isinstance(reviewed, str) and _DATE_PATTERN.fullmatch(reviewed)
        and isinstance(reason, str) and reason.strip()
    ):
        raise bootstrap.BootstrapError(MSG_BAD_BASE)
    return "{}@{}".format(image, digest)


@dataclass(frozen=True)
class ImageInputs:
    """Everything an image is built from; each is recorded as a label."""

    revision: str
    release_id: str
    campaign: str
    embedding_revision: str
    local_model: str
    base_image: str

    @property
    def tag(self) -> str:
        return versioned_tag(self.release_id, self.revision)

    def labels(self) -> List[Tuple[str, str]]:
        return [
            (MANAGED_LABEL, "1"),
            (LABEL_REVISION, self.revision),
            (LABEL_RELEASE, self.release_id),
            (LABEL_CAMPAIGN, self.campaign),
            (LABEL_EMBEDDING, self.embedding_revision),
            (LABEL_MODEL, self.local_model),
            (LABEL_BASE, self.base_image),
        ]

    def matches(self, labels: Mapping[str, str]) -> bool:
        return all(labels.get(key) == value for key, value in self.labels())


def build_argv(ctx: bootstrap.Context, inputs: ImageInputs) -> List[str]:
    """The fixed ``docker build`` arguments (after the ``docker`` command itself)."""

    release_dir = ctx.paths.releases / kr.RELEASES_DIR / inputs.release_id
    argv = [
        "build",
        "--file", str(ctx.repo_root / DOCKERFILE),
        "--build-context", "knowledge-release={}".format(release_dir),
        "--build-context", "embedding-model={}".format(ctx.paths.bge_m3),
        "--build-arg", "BASE_IMAGE={}".format(inputs.base_image),
        "--build-arg", "RELEASE_ID={}".format(inputs.release_id),
        "--build-arg", "LOCAL_MODEL={}".format(inputs.local_model),
    ]
    for key, value in inputs.labels():
        argv += ["--label", "{}={}".format(key, value)]
    argv += ["--tag", inputs.tag, "--tag", LOCAL_TAG, "--progress", "plain", str(ctx.repo_root)]
    return argv


def run_argv(port: int, campaign: str) -> List[str]:
    """The fixed ``docker run`` arguments: loopback publish, only the campaign from the host."""

    return [
        "run", "--detach", "--init",
        "--name", CONTAINER_NAME,
        "--label", "{}=1".format(MANAGED_LABEL),
        "--publish", "{}:{}:{}".format(service.HOST, port, CONTAINER_PORT),
        "--env", "{}={}".format(bootstrap.CAMPAIGN_KEY, campaign),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--restart", "no",
        LOCAL_TAG,
    ]


# --- Lock ---------------------------------------------------------------------------------


@contextmanager
def container_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``<local home>/.container.lock`` during a command."""

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise bootstrap.BootstrapError(MSG_BUSY) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


# --- Prerequisites ------------------------------------------------------------------------


class _Problems:
    """Every failed prerequisite, in order: its plain line and its fix."""

    def __init__(self) -> None:
        self.items: List[Tuple[str, str]] = []

    def add(self, line: str, fix: str) -> None:
        self.items.append((line, fix))

    def report(self, out: Callable[[str], None], result: str) -> int:
        for line, _ in self.items:
            out(line)
        out("{} {}".format(result, self.items[0][1]))
        return 1

    def __bool__(self) -> bool:
        return bool(self.items)


def _check_docker(ports: ContainerPorts, problems: _Problems) -> str:
    state = docker_state(ports.docker)
    if state == DOCKER_MISSING:
        problems.add(MSG_DOCKER_MISSING, FIX_INSTALL_DOCKER)
    elif state == DOCKER_CLOSED:
        problems.add(MSG_DOCKER_CLOSED, FIX_OPEN_DOCKER)
    return state


def _settings_and_pins(
    ctx: bootstrap.Context, ports: ContainerPorts, problems: _Problems
) -> Optional[Tuple[bootstrap.Settings, Any, LocalModelRecord]]:
    """Settings and the two reviewed pins, or ``None`` after adding the reason."""

    if bootstrap.lock_is_held(ctx.paths.lock):
        problems.add(service.MSG_SETUP_RUNNING, service.FIX_WAIT)
        return None
    try:
        settings = bootstrap.read_settings(ctx.paths.settings)
        if settings is None:
            problems.add(service.MSG_NOT_SET_UP, service.FIX_RUN_SETUP)
            return None
        spec, model = bootstrap.load_pins(ctx, ports.tools.today())
    except bootstrap.SettingsError as error:
        problems.add(error.message, service.FIX_SETTINGS)
        return None
    except bootstrap.BootstrapError as error:
        problems.add(error.message, service.FIX_PIN)
        return None
    return settings, spec, model


def _published_release(ctx: bootstrap.Context) -> Optional[str]:
    try:
        return kr.current_release_id(ctx.paths.releases)
    except kr.ReleaseError:
        return None


# --- Build --------------------------------------------------------------------------------


def run_build(ctx: bootstrap.Context, ports: ContainerPorts, base_pin: Optional[Path] = None) -> int:
    """Check every prerequisite, then build (or reuse) the image and tag it ``local``."""

    out = ports.out
    out("Checking what the image needs...")
    problems = _Problems()
    _check_docker(ports, problems)
    release_id: Optional[str] = None
    loaded = _settings_and_pins(ctx, ports, problems)
    if loaded is not None:
        settings, spec, model = loaded
        inspection = bootstrap.inspect(ctx, ports.tools, spec, model, settings.active_campaign)
        lines = bootstrap.status_lines(inspection)
        for state, line in zip(inspection.parts, lines):
            if state.part in IMAGE_PARTS and not state.ok:
                problems.add(line, bootstrap.REASONS[state.reason][1])
        release_id = _published_release(ctx)
        if release_id is None and not problems:
            problems.add("The published knowledge release cannot be read.", FIX_STATUS)
    try:
        if ports.source.dirty(COPIED_PATHS):
            problems.add(MSG_DIRTY, FIX_DIRTY)
        revision = ports.source.head_revision()
    except bootstrap.BootstrapError as error:
        problems.add(error.message, "Do the step shown above, then run this command again.")
        revision = ""
    try:
        base_image = load_base_image(base_pin or ctx.repo_root / BASE_IMAGE_FILE)
    except bootstrap.BootstrapError as error:
        problems.add(error.message, FIX_BAD_BASE)
        base_image = ""
    if bootstrap.lock_is_held(lock_path(ctx.paths)):
        problems.add(MSG_BUSY, service.FIX_WAIT)
    if problems:
        return problems.report(out, NOT_BUILT)

    assert loaded is not None and release_id is not None
    settings, spec, model = loaded
    inputs = ImageInputs(
        revision=revision,
        release_id=release_id,
        campaign=settings.active_campaign,
        embedding_revision=spec.model_revision,
        local_model=model.model,
        base_image=base_image,
    )
    try:
        with container_lock(lock_path(ctx.paths)):
            return _build(ctx, ports, inputs)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(NOT_BUILT, service.FIX_WAIT))
        return 1


def _build(ctx: bootstrap.Context, ports: ContainerPorts, inputs: ImageInputs) -> int:
    out, docker, clock = ports.out, ports.docker, ports.clock
    existing = image_info(docker, inputs.tag)
    if existing is not None and inputs.matches(existing.labels):
        if docker.run(["tag", inputs.tag, LOCAL_TAG], DOCKER_TIMEOUT_SECONDS).returncode != 0:
            out("Docker Desktop could not mark the image as the one to start.")
            out("{} {}".format(NOT_BUILT, FIX_OPEN_DOCKER))
            return 1
        out("The image {} already holds this code and knowledge release {}.".format(inputs.tag, inputs.release_id))
        out("Result: nothing new was built; {} is already up to date.".format(inputs.tag))
        return 0

    log = bootstrap.RunLog(ctx.paths.logs, BUILD_LOG, clock.now)
    log_path = log.ensure()
    out(
        "Building the image. The first build can take 10 to 30 minutes: it downloads the pinned base "
        "image and Python packages, but no model."
    )
    out("Build details go to the log file: {}".format(log_path))
    log.write("$ docker " + " ".join(build_argv(ctx, inputs)))
    started = clock.monotonic()
    shown = 0
    running = docker.start(build_argv(ctx, inputs), log_path)
    try:
        while True:
            code = running.poll()
            if code is not None:
                break
            clock.sleep(POLL_SECONDS)
            minutes = int((clock.monotonic() - started) // TICK_SECONDS)
            if minutes > shown:
                shown = minutes
                out("Still building ({} {} so far)...".format(minutes, "minute" if minutes == 1 else "minutes"))
    except KeyboardInterrupt:
        running.stop()
        out("")
        out("The build was stopped with Ctrl+C, so no image was changed.")
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again when you are ready.".format(NOT_BUILT, BUILD_COMMAND))
        return 1
    except BaseException:
        running.stop()
        raise

    built = image_info(docker, inputs.tag) if code == 0 else None
    if built is None or not inputs.matches(built.labels):
        log.write("docker build exit {}".format(code))
        out(
            "The image could not be built. Check that Docker Desktop has free disk space in its settings; "
            "if it happens again, send the log file to a developer."
        )
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again.".format(NOT_BUILT, BUILD_COMMAND))
        return 1

    out("")
    out("Image: {} (also tagged {})".format(inputs.tag, LOCAL_TAG))
    out("Knowledge release: {}".format(inputs.release_id))
    if built.size_bytes:
        out("Size: {}".format(bootstrap.format_size(built.size_bytes, approximate=True)))
    out("Result: the image {} was built with knowledge release {}.".format(inputs.tag, inputs.release_id))
    return 0


# --- Start --------------------------------------------------------------------------------


def run_start(ctx: bootstrap.Context, ports: ContainerPorts, port: int) -> int:
    """Check the image, Ollama, and the port, then run the container and wait for it."""

    out = ports.out
    problems = _Problems()
    state = _check_docker(ports, problems)
    leftover = False
    if state == DOCKER_READY:
        found = container_info(ports.docker)
        if found is not None and not found.managed:
            problems.add(MSG_FOREIGN, FIX_FOREIGN)
        elif found is not None and found.running:
            return _report_already_running(ctx, ports, found, port)
        elif found is not None:
            leftover = True

    out("Checking the answer service image...")
    loaded = _settings_and_pins(ctx, ports, problems)
    if loaded is not None:
        settings, spec, model = loaded
        if state == DOCKER_READY:
            image = image_info(ports.docker, LOCAL_TAG)
            published = _published_release(ctx)
            if image is None:
                problems.add(MSG_NO_IMAGE, FIX_BUILD_FIRST)
            elif published is None:
                problems.add("The published knowledge release cannot be read.", FIX_STATUS)
            elif (
                image.labels.get(LABEL_RELEASE) != published
                or image.labels.get(LABEL_CAMPAIGN) != settings.active_campaign
                or image.labels.get(LABEL_MODEL) != model.model
            ):
                problems.add(MSG_OLD_IMAGE, FIX_REBUILD)
        inspection = bootstrap.inspect(ctx, ports.tools, spec, model, settings.active_campaign)
        drafting = inspection.part("drafting")
        if not drafting.ok:
            line = bootstrap.status_lines(bootstrap.Inspection((drafting,), ()))[0]
            problems.add(line, bootstrap.REASONS[drafting.reason][1])
    if bootstrap.lock_is_held(lock_path(ctx.paths)):
        problems.add(MSG_BUSY, service.FIX_WAIT)
    _check_port(ctx, ports, port, problems)
    if problems:
        return problems.report(out, START_FAILED)

    assert loaded is not None
    settings, _, model = loaded
    try:
        with container_lock(lock_path(ctx.paths)):
            found = container_info(ports.docker)
            if found is not None and found.managed and found.running:
                out(
                    "Result: nothing new was started; the answer service in the container is already running "
                    "at {}.".format(service.service_url(found.host_port or port))
                )
                return 0
            if found is not None and not found.managed:
                out(MSG_FOREIGN)
                out("{} {}".format(START_FAILED, FIX_FOREIGN))
                return 1
            if found is not None:
                log = bootstrap.RunLog(ctx.paths.logs, CONTAINER_LOG, ports.clock.now)
                _save_logs(ports, log)
                if not _remove(ports):
                    out("The earlier answer service container could not be cleared.")
                    out("{} {}".format(START_FAILED, FIX_OPEN_DOCKER))
                    return 1
                out(MSG_LEFTOVER)
            return _launch(ctx, ports, port, settings.active_campaign, model)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(START_FAILED, service.FIX_WAIT))
        return 1


def _check_port(ctx: bootstrap.Context, ports: ContainerPorts, port: int, problems: _Problems) -> None:
    owner = ports.probe.health(port)
    if owner == service.PORT_FREE:
        return
    if owner == service.MOCK_SERVICE_NAME:
        problems.add(
            "Port {} is in use by the mock answer service.".format(port),
            "Run ./scripts/init.sh --mock-stop, then run this command again.",
        )
    elif owner == service.SERVICE_NAME:
        record, _ = service.find_running(ctx.paths, ports.processes, clear=False)
        if record is not None and record.port == port:
            problems.add(
                "Port {} is in use by the local answer service ({}).".format(port, service.START_COMMAND),
                "Run {}, then run this command again.".format(service.STOP_COMMAND),
            )
        else:
            problems.add(
                "Port {} is in use by a Manijero answer service that this command did not start (for example "
                "./scripts/init.sh --backend in another window).".format(port),
                "Press Ctrl+C in the window where ./scripts/init.sh --backend runs, then run this command again.",
            )
    else:
        problems.add(
            "Port {} is in use by another program.".format(port),
            "Close the other program that uses port {}, then run this command again.".format(port),
        )


def _launch(ctx: bootstrap.Context, ports: ContainerPorts, port: int, campaign: str, model: LocalModelRecord) -> int:
    out = ports.out
    log = bootstrap.RunLog(ctx.paths.logs, CONTAINER_LOG, ports.clock.now)
    log_path = log.ensure()
    out("Starting the answer service in the container (this can take up to two minutes)...")
    created = False
    try:
        argv = run_argv(port, campaign)
        log.write("$ docker " + " ".join(argv))
        result = ports.docker.run(argv, DOCKER_TIMEOUT_SECONDS)
        log.write(result.stdout)
        log.write(result.stderr)
        created = container_info(ports.docker) is not None
        if result.returncode != 0:
            failure: Optional[Tuple[str, str]] = (
                "Docker Desktop could not start the answer service container.",
                "Run {} again; if it fails again, send the log file to a developer.".format(START_COMMAND),
            )
        else:
            created = True
            failure = _wait_until_serving(ports, port)
    except KeyboardInterrupt:
        _abandon(ports, log, created or container_info(ports.docker) is not None)
        out("")
        out("The start was stopped with Ctrl+C, so the answer service container was removed.")
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again when you are ready.".format(START_FAILED, START_COMMAND))
        return 1
    except BaseException:
        _abandon(ports, log, True)
        raise
    if failure is not None:
        _abandon(ports, log, created)
        out(failure[0])
        out("Details are in the log file: {}".format(log_path))
        out("{} {}".format(START_FAILED, failure[1]))
        return 1

    image = image_info(ports.docker, LOCAL_TAG)
    labels = image.labels if image is not None else {}
    release_id = labels.get(LABEL_RELEASE, "unknown")
    out("")
    out(
        "The answer service started in the container from image {}, with hybrid search, knowledge release {}, "
        "and the local drafting model {} from Ollama on this Mac.".format(
            versioned_tag(release_id, labels.get(LABEL_REVISION, "unknown")), release_id, model.model
        )
    )
    for line in service.address_lines(port):
        out(line)
    out("Next steps:")
    out("  ./scripts/init.sh --desktop          open the Desktop app")
    out("  ./scripts/init.sh --android-run      open the app on the Android emulator")
    out("  {}   check it at any time".format(STATUS_COMMAND))
    out("  {}     stop it when you are done".format(STOP_COMMAND))
    out("It keeps running after you close Terminal.")
    out("Result: the answer service in the container started at {}.".format(service.service_url(port)))
    return 0


def _wait_until_serving(ports: ContainerPorts, port: int) -> Optional[Tuple[str, str]]:
    """``None`` once ``/health`` and ``/ready`` answer; else ``(sentence, fix)``."""

    probe, clock = ports.probe, ports.clock
    again = "Run {} again; if it fails again, send the log file to a developer.".format(START_COMMAND)
    deadline = clock.monotonic() + START_TIMEOUT_SECONDS
    while True:
        found = container_info(ports.docker)
        if found is None or not found.running:
            return ("The answer service container stopped while it was starting, so it was removed.", again)
        if probe.health(port) == service.SERVICE_NAME:
            break
        if clock.monotonic() >= deadline:
            return (
                "The answer service in the container did not answer within {} seconds, so it was removed.".format(
                    int(START_TIMEOUT_SECONDS)
                ),
                again,
            )
        clock.sleep(POLL_SECONDS)
    if probe.ready(port) != service.READY:
        return ("The answer service in the container started but cannot answer questions yet, so it was removed.", FIX_STATUS)
    return None


def _save_logs(ports: ContainerPorts, log: bootstrap.RunLog) -> None:
    result = ports.docker.run(["logs", CONTAINER_NAME], LOGS_TIMEOUT_SECONDS)
    log.write("== container output ==")
    log.write(result.stdout)
    log.write(result.stderr)


def _remove(ports: ContainerPorts) -> bool:
    """Remove the container, only after inspect shows the Manijero label."""

    found = container_info(ports.docker)
    if found is None:
        return True
    if not found.managed:
        return False
    return ports.docker.run(["rm", "--force", CONTAINER_NAME], DOCKER_TIMEOUT_SECONDS).returncode == 0


def _abandon(ports: ContainerPorts, log: bootstrap.RunLog, created: bool) -> None:
    if created:
        _save_logs(ports, log)
        _remove(ports)


# --- Status -------------------------------------------------------------------------------


def _line(state: str, label: str, text: str) -> str:
    return "{:<8} {}: {}".format(state, label, text)


def _started_text(started_at: str) -> str:
    match = _STARTED_PATTERN.match(started_at)
    return "{} {} UTC".format(match.group(1), match.group(2)) if match else "at an unknown time"


def _relay_reaches_ollama(ports: ContainerPorts) -> bool:
    result = ports.docker.run(["exec", CONTAINER_NAME, *RELAY_CHECK], DOCKER_TIMEOUT_SECONDS)
    return result.returncode == 0


def report_running(ctx: bootstrap.Context, ports: ContainerPorts, found: ContainerInfo, port: int) -> bool:
    """Print the running container's four checks and the addresses; ``True`` when all are ``OK``."""

    out = ports.out
    image = image_info(ports.docker, LOCAL_TAG)
    image_labels = image.labels if image is not None else {}
    release_id = image_labels.get(LABEL_RELEASE, "")
    revision = image_labels.get(LABEL_REVISION, "")
    checks: List[service.Check] = [
        service.Check(
            True,
            _line(
                bootstrap.OK,
                "Container",
                "{} runs image {} (knowledge release {}, code {}), started {}.".format(
                    CONTAINER_NAME,
                    versioned_tag(release_id or "unknown", revision or "unknown"),
                    release_id or "unknown",
                    revision[:12] or "unknown",
                    _started_text(found.started_at),
                ),
            ),
        ),
        service.answers_check(ports.probe, port),
    ]
    published = _published_release(ctx)
    if published is None:
        checks.append(
            service.Check(False, _line(bootstrap.PROBLEM, "Search", "the published knowledge release cannot be read. {}".format(FIX_STATUS)))
        )
    elif published != release_id:
        checks.append(
            service.Check(
                False,
                _line(
                    bootstrap.PROBLEM,
                    "Search",
                    "a newer knowledge release was published after the image was built. Run {}, then {}, then {} "
                    "to use it.".format(BUILD_COMMAND, STOP_COMMAND, START_COMMAND),
                ),
            )
        )
    else:
        checks.append(
            service.Check(
                True,
                _line(
                    bootstrap.OK,
                    "Search",
                    "the image holds knowledge release {}, which is still the published release.".format(release_id),
                ),
            )
        )
    _, model = bootstrap.load_pins(ctx, ports.tools.today())
    drafting = service.drafting_check(ports.tools, model)
    if drafting.ok and not _relay_reaches_ollama(ports):
        drafting = service.Check(
            False,
            _line(
                bootstrap.PROBLEM,
                "Drafting",
                "Ollama answers on this Mac, but the answer service in the container cannot reach it. Answers "
                "continue without the drafting model until this is fixed. {}; if it happens again, send the "
                "latest container log file to a developer.".format(FIX_CONTAINER_RESTART),
            ),
        )
    elif drafting.ok:
        drafting = service.Check(
            True,
            _line(
                bootstrap.OK,
                "Drafting",
                "Ollama answers and has the reviewed drafting model, and the container reaches it.",
            ),
        )
    checks.append(drafting)
    for check in checks:
        out(check.line)
    for line in service.address_lines(port):
        out(line)
    return all(check.ok for check in checks)


def _attention(port: int, verb: str) -> str:
    return "Result: {} at {}, but a check needs attention: do the first step shown above.".format(
        verb, service.service_url(port)
    )


def _report_already_running(ctx: bootstrap.Context, ports: ContainerPorts, found: ContainerInfo, port: int) -> int:
    out = ports.out
    actual = found.host_port or port
    if report_running(ctx, ports, found, actual):
        out(
            "Result: nothing new was started; the answer service in the container is already running at "
            "{}.".format(service.service_url(actual))
        )
        return 0
    out(_attention(actual, "nothing new was started; the answer service in the container is already running"))
    return 1


def run_status(ctx: bootstrap.Context, ports: ContainerPorts, port: int) -> int:
    """Say whether the container runs and whether its four checks are ``OK``."""

    out = ports.out
    state = docker_state(ports.docker)
    if state == DOCKER_MISSING:
        out(MSG_DOCKER_MISSING)
        out(NOT_RUNNING)
        return 1
    if state == DOCKER_CLOSED:
        out("Docker Desktop is not open, so the answer service in the container cannot be running.")
        out(NOT_RUNNING)
        return 1
    found = container_info(ports.docker)
    if found is None or not found.managed or not found.running:
        if found is not None and found.managed:
            out("An earlier answer service container ended without being stopped; the next start clears it.")
        out(NOT_RUNNING)
        return 1
    actual = found.host_port or port
    try:
        healthy = report_running(ctx, ports, found, actual)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: the answer service in the container could not be checked. Do the step shown above.")
        return 1
    if healthy:
        out("Result: the answer service in the container is running at {}.".format(service.service_url(actual)))
        return 0
    out(_attention(actual, "the answer service in the container is running"))
    return 1


# --- Stop ---------------------------------------------------------------------------------


def run_stop(ctx: bootstrap.Context, ports: ContainerPorts) -> int:
    """Stop and remove the Manijero container; a container without the label is never touched."""

    out = ports.out
    if docker_state(ports.docker) != DOCKER_READY:
        out(NOTHING_TO_STOP)
        return 0
    found = container_info(ports.docker)
    if found is None:
        out(NOTHING_TO_STOP)
        return 0
    if not found.managed:
        out("{} It was left as it is.".format(MSG_FOREIGN))
        out(NOTHING_TO_STOP)
        return 0
    try:
        with container_lock(lock_path(ctx.paths)):
            found = container_info(ports.docker)
            if found is None or not found.managed:
                out(NOTHING_TO_STOP)
                return 0
            log = bootstrap.RunLog(ctx.paths.logs, CONTAINER_LOG, ports.clock.now)
            if not found.running:
                _save_logs(ports, log)
                if _remove(ports):
                    out(MSG_LEFTOVER)
                    out(NOTHING_TO_STOP)
                    return 0
                return _stop_failed(out, log)
            out("Stopping the answer service in the container...")
            stopped = ports.docker.run(
                ["stop", "--time", str(STOP_TIMEOUT_SECONDS), CONTAINER_NAME], STOP_TIMEOUT_SECONDS + DOCKER_TIMEOUT_SECONDS
            )
            if stopped.returncode != 0:
                log.write(stopped.stderr)
                return _stop_failed(out, log)
            _save_logs(ports, log)
            if not _remove(ports):
                return _stop_failed(out, log)
            out("Its output was saved to the log file: {}".format(log.ensure()))
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: nothing was stopped. {}".format(service.FIX_WAIT))
        return 1
    out(STOPPED)
    return 0


def _stop_failed(out: Callable[[str], None], log: bootstrap.RunLog) -> int:
    out(
        "The answer service in the container did not stop. Quit and reopen Docker Desktop, then run {} "
        "again; if it happens again, send the log file to a developer: {}".format(STOP_COMMAND, log.ensure())
    )
    out("Result: the answer service in the container could not be stopped.")
    return 1


# --- Real ports ---------------------------------------------------------------------------


class _Popened:
    def __init__(self, child: "subprocess.Popen[bytes]") -> None:
        self._child = child

    def poll(self) -> Optional[int]:
        return self._child.poll()

    def stop(self) -> None:
        if self._child.poll() is not None:
            return
        self._child.terminate()
        try:
            self._child.wait(timeout=STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._child.kill()
            self._child.wait()


class SystemDockerCli:
    """The ``docker`` command (``MANIJERO_DOCKER_CLI`` replaces it in tests only)."""

    def __init__(self, repo_root: Path, cli: Optional[str] = None) -> None:
        self._root = Path(repo_root)
        self._cli = cli or os.environ.get(DOCKER_CLI_ENV, "").strip() or "docker"

    def _executable(self) -> Optional[str]:
        return shutil.which(self._cli)

    def present(self) -> bool:
        return self._executable() is not None

    def run(self, args: Sequence[str], timeout: float) -> bootstrap.CommandResult:
        executable = self._executable()
        if executable is None:
            return bootstrap.CommandResult(127, "", "docker not found")
        try:
            completed = subprocess.run(  # noqa: S603 - fixed arguments built in this module
                [executable, *[str(part) for part in args]],
                cwd=str(self._root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return bootstrap.CommandResult(124, "", "timed out")
        except OSError:
            return bootstrap.CommandResult(126, "", "could not run")
        return bootstrap.CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def start(self, args: Sequence[str], log_path: Path) -> RunningCommand:
        executable = self._executable() or self._cli
        with open(log_path, "ab") as log, open(os.devnull, "rb") as devnull:
            child = subprocess.Popen(  # noqa: S603 - fixed arguments built by build_argv
                [executable, *[str(part) for part in args]],
                cwd=str(self._root),
                stdin=devnull,
                stdout=log,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        return _Popened(child)


class GitSource:
    """The checkout's commit and whether the copied paths have unsaved changes."""

    def __init__(self, repo_root: Path) -> None:
        self._root = Path(repo_root)

    def _git(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self._root), *args], capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            raise bootstrap.BootstrapError(
                "Git is not available on this computer. Install the Xcode command line tools (run "
                "xcode-select --install), then run the same command again."
            ) from None
        if completed.returncode != 0:
            raise bootstrap.BootstrapError(
                "This folder is not a complete Manijero checkout. Run the command from the Manijero folder a "
                "developer prepared for you."
            )
        return completed.stdout

    def head_revision(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def dirty(self, paths: Sequence[str]) -> bool:
        return bool(self._git("status", "--porcelain", "--untracked-files=all", "--", *paths).strip())
