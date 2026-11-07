"""Start, check, and stop the owner's health dashboard (Prometheus and Grafana) in Docker Desktop.

Operator-only and stdlib-only at import time; the answer service never imports this module.
It mirrors :mod:`app.local_container` (same Docker port, sentences, ``Result:`` line, exit
codes, and ``org.manijero.managed=1`` label rule):

* :func:`run_start` checks every prerequisite (Docker Desktop, the reviewed image pins, other
  containers with the same names, the port) before it creates anything, writes the Prometheus
  settings under ``<local home>/monitoring/``, pulls the pinned images, and runs a Prometheus
  and a Grafana container with fixed arguments; only Grafana is published, only on
  ``127.0.0.1``;
* :func:`run_status` says whether both containers run and Grafana answers;
* :func:`run_stop` stops and removes only the labelled containers and keeps the history volume.

Prometheus scrapes ``/metrics`` of the local service (``host.docker.internal``) and, when the
QA settings hold a real address and complete access keys, of QA with the QA token read from a
read-only mounted file. The token never appears in an argument, a generated file, a message, or
a log. Prometheus keeps only ``manijero_*`` series and allowlisted labels. Messages are fixed
English sentences. ``MANIJERO_DOCKER_CLI`` and ``MANIJERO_MONITORING_PORT`` are for tests (and,
for the port, developers) only.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import secrets
import socket
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from app import environment_profiles as profiles
from app import local_container as container
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service
from app.health_metrics import LABEL_NAMES

START_COMMAND = "./scripts/init.sh --monitoring-start"
STATUS_COMMAND = "./scripts/init.sh --monitoring-status"
STOP_COMMAND = "./scripts/init.sh --monitoring-stop"

PORT_ENV = "MANIJERO_MONITORING_PORT"  # tests and developers only
DEFAULT_PORT = 3000
GRAFANA_PORT = 3000
PROMETHEUS_PORT = 9090

NETWORK = "manijero-monitoring"
PROMETHEUS = "manijero-prometheus"
GRAFANA = "manijero-grafana"
VOLUME = "manijero-monitoring-data"
CONTAINERS = (GRAFANA, PROMETHEUS)  # stop order
COMPONENT_LABEL = "org.manijero.component"
COMPONENT = "monitoring"
RETENTION = "15d"

MONITORING_DIR = Path("backend") / "monitoring"
IMAGES_FILE = MONITORING_DIR / "images.json"
RULES_DIR = MONITORING_DIR / "prometheus"
PROVISIONING_DIR = MONITORING_DIR / "grafana" / "provisioning"
DASHBOARDS_DIR = MONITORING_DIR / "grafana" / "dashboards"
HOME_DASHBOARD = "/etc/grafana/dashboards/manijero-health.json"
CONFIG_NAME = "prometheus.yml"  # JSON, which is valid YAML
RUNTIME_DIR = "monitoring"

CONFIG_MOUNT = "/etc/manijero-prometheus"
RULES_MOUNT = "/etc/manijero-rules"
RULES_FILE = RULES_MOUNT + "/rules.json"
QA_TOKEN_MOUNT = "/run/manijero/qa.token"
LOCAL_SCRAPE_SECONDS = 15
QA_SCRAPE_SECONDS = 30

LOCK_NAME = ".monitoring.lock"
LOG_NAME = "monitoring"

DOCKER_TIMEOUT_SECONDS = 30.0
STOP_TIMEOUT_SECONDS = 10
LOGS_TIMEOUT_SECONDS = 60.0
START_TIMEOUT_SECONDS = 120.0
POLL_SECONDS = 1.0
TICK_SECONDS = 60.0
PROBE_TIMEOUT_SECONDS = 2.0

# Grafana settings (environment variables of the container): anonymous Viewer only, no login
# form, Explore, editing accounts, plugin downloads, analytics, update checks, or alerting.
GRAFANA_SETTINGS: Tuple[Tuple[str, str], ...] = (
    ("GF_AUTH_ANONYMOUS_ENABLED", "true"),
    ("GF_AUTH_ANONYMOUS_ORG_ROLE", "Viewer"),
    ("GF_AUTH_DISABLE_LOGIN_FORM", "true"),
    ("GF_AUTH_BASIC_ENABLED", "false"),
    ("GF_USERS_ALLOW_SIGN_UP", "false"),
    ("GF_EXPLORE_ENABLED", "false"),
    ("GF_ANALYTICS_REPORTING_ENABLED", "false"),
    ("GF_ANALYTICS_CHECK_FOR_UPDATES", "false"),
    ("GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES", "false"),
    ("GF_ANALYTICS_FEEDBACK_LINKS_ENABLED", "false"),
    ("GF_PLUGINS_PREINSTALL_DISABLED", "true"),
    ("GF_PLUGINS_PLUGIN_ADMIN_ENABLED", "false"),
    ("GF_NEWS_NEWS_FEED_ENABLED", "false"),
    ("GF_SNAPSHOTS_EXTERNAL_ENABLED", "false"),
    ("GF_UNIFIED_ALERTING_ENABLED", "false"),
    ("GF_ALERTING_ENABLED", "false"),
    ("GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH", HOME_DASHBOARD),
)
ADMIN_PASSWORD_KEY = "GF_SECURITY_ADMIN_PASSWORD"  # random per start, passed by name only

# Labels Prometheus keeps: the backend_health_metrics allowlist plus the scrape's own labels
# (``exported_job`` is the backend's ``job`` label, renamed because the scrape sets ``job``).
KEPT_LABELS = tuple(sorted(set(LABEL_NAMES) | {"__name__", "env", "job", "instance", "exported_job"}))

_PIN_KEYS = {"image", "digest", "reviewed_on", "reason"}
_IMAGE_PATTERN = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*:[A-Za-z0-9_][A-Za-z0-9._-]{0,127}")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_PORT_PATTERN = re.compile(r"[0-9]{1,5}")

MSG_BAD_PORT = "{} must be a port number between 1 and 65535.".format(PORT_ENV)
MSG_BAD_PINS = "The reviewed monitoring image pins {} are not valid.".format(IMAGES_FILE)
FIX_BAD_PINS = "A developer must review {}.".format(IMAGES_FILE)
MSG_BUSY = (
    "Another monitoring command is running in another Terminal window. Wait until it shows its Result: "
    "line, then run this command again."
)
FIX_WAIT = "Wait for the other command to finish, then run this command again."
MSG_LEFTOVER = "An earlier health dashboard ended without being stopped; it was cleared."
FIX_RESTART = "Run {}, then {}".format(STOP_COMMAND, START_COMMAND)  # starts a sentence

START_FAILED = "Result: the health dashboard did not start."
STOPPED = "Result: the health dashboard has stopped."
NOTHING_TO_STOP = "Result: the health dashboard was not running, so there was nothing to stop."
NOT_RUNNING = "Result: the health dashboard is not running. Start it with {}.".format(START_COMMAND)


def address(port: int) -> str:
    return service.service_url(port)


def open_line(port: int) -> str:
    return "Open {} in your web browser.".format(address(port))


def port_from_environment(environ: Mapping[str, str]) -> int:
    text = environ.get(PORT_ENV) or ""
    if not text:
        return DEFAULT_PORT
    if not _PORT_PATTERN.fullmatch(text) or not 1 <= int(text) <= 65535:
        raise service.UsageError(MSG_BAD_PORT)
    return int(text)


# --- Reviewed image pins --------------------------------------------------------------------


@dataclass(frozen=True)
class ImagePin:
    """A reviewed image: an explicit version tag and, once read from the registry, its digest."""

    image: str
    digest: Optional[str]

    @property
    def reference(self) -> str:
        return "{}@{}".format(self.image, self.digest) if self.digest else self.image


@dataclass(frozen=True)
class Pins:
    grafana: ImagePin
    prometheus: ImagePin


def _pin(document: Any) -> ImagePin:
    if not isinstance(document, dict) or set(document) != _PIN_KEYS:
        raise bootstrap.BootstrapError(MSG_BAD_PINS)
    image, digest, reviewed, reason = (document[key] for key in ("image", "digest", "reviewed_on", "reason"))
    if not (
        isinstance(image, str) and _IMAGE_PATTERN.fullmatch(image) and not image.endswith(":latest")
        and (digest is None or (isinstance(digest, str) and _DIGEST_PATTERN.fullmatch(digest)))
        and isinstance(reviewed, str) and _DATE_PATTERN.fullmatch(reviewed)
        and isinstance(reason, str) and reason.strip()
    ):
        raise bootstrap.BootstrapError(MSG_BAD_PINS)
    return ImagePin(image, digest)


def load_pins(path: Path) -> Pins:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise bootstrap.BootstrapError(MSG_BAD_PINS) from None
    if not isinstance(document, dict) or set(document) != {"grafana", "prometheus"}:
        raise bootstrap.BootstrapError(MSG_BAD_PINS)
    return Pins(_pin(document["grafana"]), _pin(document["prometheus"]))


# --- Prometheus settings --------------------------------------------------------------------


@dataclass(frozen=True)
class QaTarget:
    target: str  # host:port
    metrics_path: str
    token_file: Path


def qa_target(qa_home: Path) -> Optional[QaTarget]:
    """The QA scrape target, or ``None`` unless the address is real and the access keys complete."""

    try:
        settings = profiles.read_profile_settings(profiles.QA, qa_home)
    except profiles.ProfileSettingsError:
        return None
    if not settings.public_url or settings.placeholder_url:
        return None
    keys = profiles.credential_paths(qa_home, profiles.QA_CLIENT_ID)
    if profiles.check_credentials(keys, profiles.QA_CLIENT_ID) is not None:
        return None
    parts = urlsplit(settings.public_url)
    host = parts.hostname or ""
    if not host:
        return None
    return QaTarget(
        "{}:{}".format(host, parts.port or 443), parts.path.rstrip("/") + "/metrics", keys.token
    )


def prometheus_config(local_port: int, qa: Optional[QaTarget]) -> Dict[str, Any]:
    """The Prometheus settings document: what is scraped, what is kept, which rules run."""

    keep = [
        {"source_labels": ["__name__"], "regex": "manijero_.*", "action": "keep"},
        {"regex": "|".join(KEPT_LABELS), "action": "labelkeep"},
    ]
    jobs: List[Dict[str, Any]] = [
        {
            "job_name": "manijero-local",
            "scrape_interval": "{}s".format(LOCAL_SCRAPE_SECONDS),
            "metrics_path": "/metrics",
            "static_configs": [
                {"targets": ["host.docker.internal:{}".format(local_port)], "labels": {"env": "local"}}
            ],
            "metric_relabel_configs": keep,
        }
    ]
    if qa is not None:
        jobs.append(
            {
                "job_name": "manijero-qa",
                "scrape_interval": "{}s".format(QA_SCRAPE_SECONDS),
                "scheme": "https",
                "metrics_path": qa.metrics_path,
                "authorization": {"type": "Bearer", "credentials_file": QA_TOKEN_MOUNT},
                "static_configs": [{"targets": [qa.target], "labels": {"env": "qa"}}],
                "metric_relabel_configs": keep,
            }
        )
    return {
        "global": {
            "scrape_interval": "{}s".format(LOCAL_SCRAPE_SECONDS),
            "evaluation_interval": "{}s".format(LOCAL_SCRAPE_SECONDS),
        },
        "rule_files": [RULES_FILE],
        "scrape_configs": jobs,
    }


def write_config(directory: Path, config: Mapping[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    path = directory / CONFIG_NAME
    temporary = directory / (CONFIG_NAME + ".new")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)
    return path


# --- Fixed container arguments --------------------------------------------------------------


def _common(name: str) -> List[str]:
    return [
        "run", "--detach", "--init",
        "--name", name,
        "--network", NETWORK,
        "--label", "{}=1".format(container.MANAGED_LABEL),
        "--label", "{}={}".format(COMPONENT_LABEL, COMPONENT),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--restart", "no",
    ]


def prometheus_argv(pin: ImagePin, config_dir: Path, rules_dir: Path, qa: Optional[QaTarget]) -> List[str]:
    """``docker run`` for Prometheus: nothing published, settings and rules read-only."""

    argv = _common(PROMETHEUS)
    argv += ["--volume", "{}:{}:ro".format(config_dir, CONFIG_MOUNT)]
    argv += ["--volume", "{}:{}:ro".format(rules_dir, RULES_MOUNT)]
    argv += ["--volume", "{}:/prometheus".format(VOLUME)]
    if qa is not None:
        argv += ["--volume", "{}:{}:ro".format(qa.token_file, QA_TOKEN_MOUNT)]
    argv += [
        pin.reference,
        "--config.file={}/{}".format(CONFIG_MOUNT, CONFIG_NAME),
        "--storage.tsdb.path=/prometheus",
        "--storage.tsdb.retention.time={}".format(RETENTION),
    ]
    return argv


def grafana_argv(pin: ImagePin, port: int, provisioning: Path, dashboards: Path) -> List[str]:
    """``docker run`` for Grafana: published only on loopback; the admin password by name only."""

    argv = _common(GRAFANA)
    argv += ["--publish", "{}:{}:{}".format(service.HOST, port, GRAFANA_PORT)]
    argv += ["--volume", "{}:/etc/grafana/provisioning:ro".format(provisioning)]
    argv += ["--volume", "{}:/etc/grafana/dashboards:ro".format(dashboards)]
    for key, value in GRAFANA_SETTINGS:
        argv += ["--env", "{}={}".format(key, value)]
    argv += ["--env", ADMIN_PASSWORD_KEY, pin.reference]
    return argv


# --- Ports ----------------------------------------------------------------------------------


class GrafanaProbe:
    """Loopback checks of the dashboard port (the real implementation of the probe port)."""

    def port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(PROBE_TIMEOUT_SECONDS)
            return sock.connect_ex((service.HOST, port)) != 0

    def healthy(self, port: int) -> bool:
        url = "http://{}:{}/api/health".format(service.HOST, port)
        try:
            with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT_SECONDS) as reply:  # noqa: S310 - loopback
                document = json.loads(reply.read(service.MAX_PROBE_BYTES).decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError):
            return False
        return isinstance(document, dict) and document.get("database") == "ok"


@dataclass
class MonitoringPorts:
    """Every external effect; tests pass fakes."""

    docker: container.DockerCli
    probe: Any
    clock: service.ServiceClock
    out: Callable[[str], None]
    new_password: Callable[[], str] = lambda: secrets.token_urlsafe(24)


@dataclass(frozen=True)
class MonitoringContext:
    repo_root: Path
    home: Path
    qa_home: Path
    local_port: int = service.DEFAULT_PORT

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def runtime(self) -> Path:
        return self.home / RUNTIME_DIR

    @property
    def lock(self) -> Path:
        return self.home / LOCK_NAME


def default_context(local_port: int = service.DEFAULT_PORT) -> MonitoringContext:
    return MonitoringContext(bootstrap.REPOSITORY_ROOT, bootstrap.default_home(), profiles.qa_home(), local_port)


# --- Docker facts ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Found:
    labels: Mapping[str, str]
    running: bool
    host_port: Optional[int]

    @property
    def managed(self) -> bool:
        return self.labels.get(container.MANAGED_LABEL) == "1"


def find(docker: container.DockerCli, name: str) -> Optional[Found]:
    result = docker.run(["container", "inspect", name], DOCKER_TIMEOUT_SECONDS)
    if result.returncode != 0:
        return None
    try:
        document = json.loads(result.stdout)
    except ValueError:
        return None
    if not (isinstance(document, list) and document and isinstance(document[0], dict)):
        return None
    entry = document[0]
    config = entry.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    state = entry.get("State") if isinstance(entry.get("State"), dict) else {}
    host_port: Optional[int] = None
    network = entry.get("NetworkSettings")
    bindings = network.get("Ports") if isinstance(network, dict) else None
    entries = bindings.get("{}/tcp".format(GRAFANA_PORT)) if isinstance(bindings, dict) else None
    if isinstance(entries, list):
        for binding in entries:
            text = binding.get("HostPort") if isinstance(binding, dict) else None
            if isinstance(text, str) and text.isdigit():
                host_port = int(text)
                break
    return Found(
        {str(k): str(v) for k, v in labels.items()} if isinstance(labels, dict) else {},
        state.get("Running") is True,
        host_port,
    )


def _ours(docker: container.DockerCli, resource: str, name: str) -> Optional[bool]:
    """Whether a network or volume exists and carries the label; ``None`` when absent."""

    result = docker.run([resource, "inspect", name], DOCKER_TIMEOUT_SECONDS)
    if result.returncode != 0:
        return None
    try:
        document = json.loads(result.stdout)
        labels = document[0].get("Labels") or {}
    except (ValueError, IndexError, AttributeError, TypeError):
        return False
    return isinstance(labels, dict) and labels.get(container.MANAGED_LABEL) == "1"


@contextmanager
def monitoring_lock(path: Path) -> Iterator[None]:
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


def _lock_is_held(path: Path) -> bool:
    if not Path(path).exists():
        return False
    handle = os.open(path, os.O_RDWR)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False
    finally:
        os.close(handle)


class _Problems:
    def __init__(self) -> None:
        self.items: List[Tuple[str, str]] = []

    def add(self, line: str, fix: str) -> None:
        self.items.append((line, fix))

    def report(self, out: Callable[[str], None]) -> int:
        for line, _ in self.items:
            out(line)
        out("{} {}".format(START_FAILED, self.items[0][1]))
        return 1

    def __bool__(self) -> bool:
        return bool(self.items)


def _foreign(name: str) -> str:
    return "A container named {} exists in Docker Desktop, but Manijero did not create it.".format(name)


FIX_FOREIGN = "Rename or delete that container in Docker Desktop, then run this command again."


# --- Start ----------------------------------------------------------------------------------


def run_start(ctx: MonitoringContext, ports: MonitoringPorts, port: int) -> int:
    out = ports.out
    problems = _Problems()
    state = container.docker_state(ports.docker)
    if state == container.DOCKER_MISSING:
        problems.add(container.MSG_DOCKER_MISSING, container.FIX_INSTALL_DOCKER)
    elif state == container.DOCKER_CLOSED:
        problems.add(container.MSG_DOCKER_CLOSED, container.FIX_OPEN_DOCKER)

    running_here = False
    if state == container.DOCKER_READY:
        found = {name: find(ports.docker, name) for name in CONTAINERS}
        for name, entry in found.items():
            if entry is not None and not entry.managed:
                problems.add(_foreign(name), FIX_FOREIGN)
        if not problems and all(entry is not None and entry.running for entry in found.values()):
            return _already_running(ports, found[GRAFANA], port)  # type: ignore[arg-type]
        running_here = any(entry is not None and entry.managed for entry in found.values())

    pins: Optional[Pins] = None
    try:
        pins = load_pins(ctx.repo_root / IMAGES_FILE)
    except bootstrap.BootstrapError as error:
        problems.add(error.message, FIX_BAD_PINS)
    if _lock_is_held(ctx.lock):
        problems.add(MSG_BUSY, FIX_WAIT)
    if not running_here and not ports.probe.port_free(port):
        problems.add(
            "Port {} is in use by another program.".format(port),
            "Close the other program that uses port {}, then run this command again.".format(port),
        )
    if problems:
        return problems.report(out)

    assert pins is not None
    try:
        with monitoring_lock(ctx.lock):
            return _launch(ctx, ports, pins, port)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(START_FAILED, FIX_WAIT))
        return 1


def _already_running(ports: MonitoringPorts, grafana: Found, port: int) -> int:
    actual = grafana.host_port or port
    if ports.probe.healthy(actual):
        ports.out(open_line(actual))
        ports.out("Result: nothing new was started; the health dashboard is already running at {}.".format(address(actual)))
        return 0
    ports.out("The health dashboard containers run, but the page does not answer yet.")
    ports.out(
        "Result: the health dashboard is running at {}, but it does not answer yet. Wait a minute and run "
        "{}.".format(address(actual), STATUS_COMMAND)
    )
    return 1


def _run_logged(ports: MonitoringPorts, log: bootstrap.RunLog, args: Sequence[str]) -> bool:
    log.write("$ docker " + " ".join(args))
    result = ports.docker.run(args, DOCKER_TIMEOUT_SECONDS)
    log.write(result.stdout)
    log.write(result.stderr)
    return result.returncode == 0


def _pull(ports: MonitoringPorts, log: bootstrap.RunLog, pin: ImagePin) -> bool:
    """Make the pinned image available; returns ``False`` when Docker could not get it."""

    docker, out, clock = ports.docker, ports.out, ports.clock
    present = docker.run(["image", "inspect", pin.reference], DOCKER_TIMEOUT_SECONDS)
    if present.returncode == 0:
        return True
    out("Downloading {} (first time only, this can take a few minutes)...".format(pin.reference))
    path = log.ensure()
    log.write("$ docker pull {}".format(pin.reference))
    running = docker.start(["pull", pin.reference], path)
    started = clock.monotonic()
    shown = 0
    try:
        while running.poll() is None:
            clock.sleep(POLL_SECONDS)
            minutes = int((clock.monotonic() - started) // TICK_SECONDS)
            if minutes > shown:
                shown = minutes
                out("Still downloading ({} {} so far)...".format(minutes, "minute" if minutes == 1 else "minutes"))
    except BaseException:
        running.stop()
        raise
    code = running.poll()
    if code != 0:
        log.write("docker pull exit {}".format(code))
        return False
    info = container.image_info(docker, pin.reference)
    if info is not None and info.size_bytes:
        out("Downloaded {} (size {}).".format(pin.image, bootstrap.format_size(info.size_bytes, approximate=True)))
    return True


def _remove(ports: MonitoringPorts, name: str) -> bool:
    entry = find(ports.docker, name)
    if entry is None:
        return True
    if not entry.managed:
        return False
    return ports.docker.run(["rm", "--force", name], DOCKER_TIMEOUT_SECONDS).returncode == 0


def _save_logs(ports: MonitoringPorts, log: bootstrap.RunLog, name: str) -> None:
    result = ports.docker.run(["logs", name], LOGS_TIMEOUT_SECONDS)
    log.write("== {} output ==".format(name))
    log.write(result.stdout)
    log.write(result.stderr)


def _abandon(ports: MonitoringPorts, log: bootstrap.RunLog) -> None:
    for name in CONTAINERS:
        if find(ports.docker, name) is not None:
            _save_logs(ports, log, name)
            _remove(ports, name)


@contextmanager
def _password_in_environment(value: str) -> Iterator[None]:
    """Hand the password to the docker command by name (``--env NAME``), never in an argument."""

    before = os.environ.get(ADMIN_PASSWORD_KEY)
    os.environ[ADMIN_PASSWORD_KEY] = value
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(ADMIN_PASSWORD_KEY, None)
        else:
            os.environ[ADMIN_PASSWORD_KEY] = before


def _launch(ctx: MonitoringContext, ports: MonitoringPorts, pins: Pins, port: int) -> int:
    out, docker = ports.out, ports.docker
    log = bootstrap.RunLog(ctx.logs, LOG_NAME, ports.clock.now)
    failed = _clear_leftovers(ports, log)
    if failed:
        out(failed)
        out("{} {}".format(START_FAILED, container.FIX_OPEN_DOCKER))
        return 1

    qa = qa_target(ctx.qa_home)
    created = False
    try:
        for pin in (pins.prometheus, pins.grafana):
            if not _pull(ports, log, pin):
                out("Docker Desktop could not download {}. Check the internet connection and the free disk space in Docker Desktop.".format(pin.image))
                out("Details are in the log file: {}".format(log.ensure()))
                out("{} Run {} again.".format(START_FAILED, START_COMMAND))
                return 1
        out("Starting the health dashboard (this can take up to two minutes)...")
        if _ours(docker, "network", NETWORK) is None and not _run_logged(
            ports, log, ["network", "create", "--label", "{}=1".format(container.MANAGED_LABEL), NETWORK]
        ):
            return _failed(ports, log, False, "Docker Desktop could not prepare the monitoring network.")
        if _ours(docker, "volume", VOLUME) is None and not _run_logged(
            ports, log, ["volume", "create", "--label", "{}=1".format(container.MANAGED_LABEL), VOLUME]
        ):
            return _failed(ports, log, False, "Docker Desktop could not prepare the history storage.")
        write_config(ctx.runtime, prometheus_config(ctx.local_port, qa))
        rules = ctx.repo_root / RULES_DIR
        if not _run_logged(ports, log, prometheus_argv(pins.prometheus, ctx.runtime, rules, qa)):
            created = find(docker, PROMETHEUS) is not None
            return _failed(ports, log, created, "Docker Desktop could not start the monitoring collector.")
        grafana = grafana_argv(
            pins.grafana, port, ctx.repo_root / PROVISIONING_DIR, ctx.repo_root / DASHBOARDS_DIR
        )
        with _password_in_environment(ports.new_password()):
            started = _run_logged(ports, log, grafana)
        if not started:
            return _failed(ports, log, True, "Docker Desktop could not start the dashboard page.")
        created = True
        problem = _wait_until_healthy(ports, port)
        if problem is not None:
            return _failed(ports, log, True, problem)
    except KeyboardInterrupt:
        _abandon(ports, log)
        out("")
        out("The start was stopped with Ctrl+C, so the health dashboard was removed.")
        out("{} Run {} again when you are ready.".format(START_FAILED, START_COMMAND))
        return 1
    except BaseException:
        _abandon(ports, log)
        raise

    out("")
    out(open_line(port))
    if qa is None:
        out("QA shows \"Not set up yet\" until the QA service is deployed.")
    out("Next steps:")
    out("  {}   check it at any time".format(STATUS_COMMAND))
    out("  {}     stop it when you are done".format(STOP_COMMAND))
    out("It keeps running after you close Terminal.")
    out("Result: the health dashboard started at {}.".format(address(port)))
    return 0


def _failed(ports: MonitoringPorts, log: bootstrap.RunLog, created: bool, sentence: str) -> int:
    if created:
        _abandon(ports, log)
    ports.out(sentence)
    ports.out("Details are in the log file: {}".format(log.ensure()))
    ports.out(
        "{} Run {} again; if it fails again, send the log file to a developer.".format(START_FAILED, START_COMMAND)
    )
    return 1


def _clear_leftovers(ports: MonitoringPorts, log: bootstrap.RunLog) -> Optional[str]:
    """Remove stopped or half-started Manijero monitoring containers; a sentence on failure."""

    cleared = False
    for name in CONTAINERS:
        entry = find(ports.docker, name)
        if entry is None:
            continue
        if not entry.managed:
            return _foreign(name)
        _save_logs(ports, log, name)
        if not _remove(ports, name):
            return "An earlier health dashboard container could not be cleared."
        cleared = True
    if cleared:
        ports.out(MSG_LEFTOVER)
    return None


def _wait_until_healthy(ports: MonitoringPorts, port: int) -> Optional[str]:
    clock = ports.clock
    deadline = clock.monotonic() + START_TIMEOUT_SECONDS
    while True:
        for name in CONTAINERS:
            entry = find(ports.docker, name)
            if entry is None or not entry.running:
                return "The health dashboard stopped while it was starting, so it was removed."
        if ports.probe.healthy(port):
            return None
        if clock.monotonic() >= deadline:
            return "The dashboard page did not answer within {} seconds, so it was removed.".format(
                int(START_TIMEOUT_SECONDS)
            )
        clock.sleep(POLL_SECONDS)


# --- Status ---------------------------------------------------------------------------------


def _line(state: str, label: str, text: str) -> str:
    return "{:<8} {}: {}".format(state, label, text)


def run_status(ctx: MonitoringContext, ports: MonitoringPorts, port: int) -> int:
    out = ports.out
    state = container.docker_state(ports.docker)
    if state == container.DOCKER_MISSING:
        out(container.MSG_DOCKER_MISSING)
        out(NOT_RUNNING)
        return 1
    if state == container.DOCKER_CLOSED:
        out("Docker Desktop is not open, so the health dashboard cannot be running.")
        out(NOT_RUNNING)
        return 1
    grafana, prometheus = find(ports.docker, GRAFANA), find(ports.docker, PROMETHEUS)
    entries = [entry for entry in (grafana, prometheus) if entry is not None and entry.managed]
    if not entries:
        out(NOT_RUNNING)
        return 1
    if grafana is None or prometheus is None or not (grafana.managed and prometheus.managed) or not (
        grafana.running and prometheus.running
    ):
        out(_line(bootstrap.PROBLEM, "Dashboard", "only part of the health dashboard runs."))
        out("Result: the health dashboard is not running completely. {}, or just {}.".format(FIX_RESTART, START_COMMAND))
        return 1
    actual = grafana.host_port or port
    healthy = ports.probe.healthy(actual)
    out(_line(bootstrap.OK, "Collector", "Prometheus runs and reads the answer service every {} seconds.".format(LOCAL_SCRAPE_SECONDS)))
    if healthy:
        out(_line(bootstrap.OK, "Page", "Grafana answers at {}.".format(address(actual))))
    else:
        out(_line(bootstrap.PROBLEM, "Page", "Grafana runs but does not answer yet. Wait a minute and run {} again.".format(STATUS_COMMAND)))
    qa = qa_target(ctx.qa_home)
    out(
        _line(
            bootstrap.OK,
            "QA",
            "the dashboard also reads the QA service." if qa is not None
            else "not set up yet; the QA row says so until the QA service is deployed.",
        )
    )
    if healthy:
        out(open_line(actual))
        out("Result: the health dashboard is running at {}.".format(address(actual)))
        return 0
    out("Result: the health dashboard is running at {}, but the page does not answer yet. Do the step shown above.".format(address(actual)))
    return 1


# --- Stop -----------------------------------------------------------------------------------


def run_stop(ctx: MonitoringContext, ports: MonitoringPorts) -> int:
    out = ports.out
    if container.docker_state(ports.docker) != container.DOCKER_READY:
        out(NOTHING_TO_STOP)
        return 0
    entries = {name: find(ports.docker, name) for name in CONTAINERS}
    for name, entry in entries.items():
        if entry is not None and not entry.managed:
            out("{} It was left as it is.".format(_foreign(name)))
    ours = [name for name in CONTAINERS if entries[name] is not None and entries[name].managed]  # type: ignore[union-attr]
    if not ours:
        out(NOTHING_TO_STOP)
        return 0
    try:
        with monitoring_lock(ctx.lock):
            log = bootstrap.RunLog(ctx.logs, LOG_NAME, ports.clock.now)
            out("Stopping the health dashboard...")
            for name in ours:
                entry = find(ports.docker, name)
                if entry is None or not entry.managed:
                    continue
                if entry.running:
                    stopped = ports.docker.run(
                        ["stop", "--time", str(STOP_TIMEOUT_SECONDS), name], STOP_TIMEOUT_SECONDS + DOCKER_TIMEOUT_SECONDS
                    )
                    if stopped.returncode != 0:
                        log.write(stopped.stderr)
                        return _stop_failed(out, log)
                _save_logs(ports, log, name)
                if not _remove(ports, name):
                    return _stop_failed(out, log)
            if _ours(ports.docker, "network", NETWORK):
                ports.docker.run(["network", "rm", NETWORK], DOCKER_TIMEOUT_SECONDS)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: nothing was stopped. {}".format(FIX_WAIT))
        return 1
    out("The history is kept for the next start.")
    out(STOPPED)
    return 0


def _stop_failed(out: Callable[[str], None], log: bootstrap.RunLog) -> int:
    out(
        "The health dashboard did not stop. Quit and reopen Docker Desktop, then run {} again; if it happens "
        "again, send the log file to a developer: {}".format(STOP_COMMAND, log.ensure())
    )
    out("Result: the health dashboard could not be stopped.")
    return 1
