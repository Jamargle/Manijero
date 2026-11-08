"""Deploy, update, roll back, check, and stop the QA answer service on the owner's Mac.

Operator-only and stdlib-only at import time; the answer service never imports this module.
QA is the existing answer service image (``manijero-backend``) run as container ``manijero-qa``
in the pilot profile, published on ``127.0.0.1:8100`` only, and reached by real devices through
Tailscale Funnel at ``https://<mac>.<tailnet>.ts.net``. QA uses made-up test data only: the
pilot launcher accepts the still-pending privacy review only for ``MANIJERO_ENVIRONMENT=qa`` plus
``MANIJERO_QA_TEST_DATA_ONLY=yes`` (owner decision 2026-11-02, :mod:`app.privacy_review`), and the
flag is set only by :func:`run_argv` below. See ``docs/specs/qa_server_deployment.md``.

Every command checks all prerequisites before it changes anything, asks the owner to type ``yes``
before it deploys, updates, or rolls back, and ends with one ``Result:`` line. Messages are fixed
English sentences with no token, question, answer, or land value. External effects go through
injected ports (:class:`QaPorts`); ``MANIJERO_TAILSCALE_CLI``, ``MANIJERO_DOCKER_CLI`` and
``MANIJERO_QA_PORT`` are for tests only. Only Funnel's own HTTPS 443 entry that points at the QA
port is ever turned off; containers without the QA labels are never touched.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from app import environment_profiles as profiles
from app import local_container as lc
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service

DEPLOY_COMMAND = "./scripts/init.sh --qa-deploy"
UPDATE_COMMAND = "./scripts/init.sh --qa-update"
ROLLBACK_COMMAND = "./scripts/init.sh --qa-rollback"
STATUS_COMMAND = "./scripts/init.sh --qa-status"
STOP_COMMAND = "./scripts/init.sh --qa-stop"
OPERATIONS = ("deploy", "update", "rollback", "status", "stop")

TAILSCALE_CLI_ENV = "MANIJERO_TAILSCALE_CLI"  # tests only
PORT_ENV = "MANIJERO_QA_PORT"  # tests only
ADDRESS_FILE_ENV = "MANIJERO_QA_ADDRESS_FILE"
DEFAULT_PORT = 8100
TAILSCALE_APP_CLI = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"

CONTAINER_NAME = "manijero-qa"
LABEL_ENVIRONMENT = "org.manijero.environment"
LABEL_LAUNCHERS = "org.manijero.launchers"
TAG_CURRENT = lc.IMAGE_REPOSITORY + ":qa-current"
TAG_PREVIOUS = lc.IMAGE_REPOSITORY + ":qa-previous"
TAG_SWAP = lc.IMAGE_REPOSITORY + ":qa-swap"
TEST_DATA_FLAG = "MANIJERO_QA_TEST_DATA_ONLY"
CLIENTS_MOUNT = "/run/manijero/pilot-clients.json"
LOCK_NAME = ".qa.lock"

PUBLIC_WAIT_SECONDS = 60.0
PUBLIC_POLL_SECONDS = 3.0
PUBLIC_TIMEOUT_SECONDS = 8.0
TAILSCALE_TIMEOUT_SECONDS = 20.0

# --- Tailscale CLI forms (documented current forms; the owner walkthrough confirms them) --------
# Everything that depends on the Tailscale command line or its JSON lives in this block.

TAILSCALE_STATUS_ARGV = ("status", "--json")
TAILSCALE_FUNNEL_STATUS_ARGV = ("funnel", "status", "--json")
HTTPS_PORT = 443


def funnel_target(port: int) -> str:
    return "http://127.0.0.1:{}".format(port)


def funnel_on_argv(port: int) -> List[str]:
    return ["funnel", "--bg", "--https={}".format(HTTPS_PORT), funnel_target(port)]


def funnel_off_argv() -> List[str]:
    return ["funnel", "--https={}".format(HTTPS_PORT), "off"]


def _capability_names(self_node: Mapping[str, Any]) -> List[str]:
    names: List[str] = []
    cap_map = self_node.get("CapMap")
    if isinstance(cap_map, dict):
        names += [str(key) for key in cap_map]
    capabilities = self_node.get("Capabilities")
    if isinstance(capabilities, list):
        names += [str(item) for item in capabilities]
    return names


def _allows_https(self_node: Mapping[str, Any], document: Mapping[str, Any]) -> bool:
    if any(name == "https" or name.split("?")[0].endswith("/cap/https") for name in _capability_names(self_node)):
        return True
    domains = document.get("CertDomains")
    return isinstance(domains, list) and bool(domains)


def _allows_funnel(self_node: Mapping[str, Any]) -> bool:
    return any("funnel" in name.lower() for name in _capability_names(self_node))


def _funnel_state(document: Any, dns_name: str, port: int) -> str:
    """``off``, ``ours`` (443 serves only ``/`` to the QA port with Funnel on), or ``foreign``."""

    if not isinstance(document, dict):
        return "off"
    web = document.get("Web") if isinstance(document.get("Web"), dict) else {}
    allow = document.get("AllowFunnel") if isinstance(document.get("AllowFunnel"), dict) else {}
    tcp = document.get("TCP") if isinstance(document.get("TCP"), dict) else {}
    https_entries = [key for key in web if str(key).endswith(":{}".format(HTTPS_PORT))]
    if not https_entries and str(HTTPS_PORT) not in tcp:
        return "off"
    ours_key = "{}:{}".format(dns_name, HTTPS_PORT)
    if https_entries != [ours_key]:
        return "foreign"
    handlers = web[ours_key].get("Handlers") if isinstance(web[ours_key], dict) else None
    if not isinstance(handlers, dict) or set(handlers) != {"/"}:
        return "foreign"
    proxy = handlers["/"].get("Proxy") if isinstance(handlers["/"], dict) else None
    if not isinstance(proxy, str) or proxy.rstrip("/") != funnel_target(port):
        return "foreign"
    return "ours" if allow.get(ours_key) is True else "off"


# --- Ports --------------------------------------------------------------------------------


class TailscaleCli(Protocol):
    def present(self) -> bool: ...

    def run(self, args: Sequence[str], timeout: float) -> bootstrap.CommandResult: ...


@dataclass
class QaPorts:
    """Every external effect; tests pass fakes."""

    tools: bootstrap.Ports
    probe: service.ServiceProbe
    clock: service.ServiceClock
    docker: lc.DockerCli
    tailscale: TailscaleCli
    smoke: Callable[[str, str], Sequence[str]]  # (loopback base url, token) -> failure codes
    public: Callable[[str], bool]  # does <https address>/health answer?
    tty: bool
    home: Path
    port: int
    address_file: Path

    @property
    def out(self) -> Callable[[str], None]:
        return self.tools.out


def port_from_environment(environ: Mapping[str, str]) -> int:
    raw = (environ.get(PORT_ENV) or "").strip()
    if not raw:
        return DEFAULT_PORT
    if not re.fullmatch(r"[0-9]{1,5}", raw) or not 1 <= int(raw) <= 65535:
        raise service.UsageError("{} must be a port number between 1 and 65535.".format(PORT_ENV))
    return int(raw)


# --- Wording ------------------------------------------------------------------------------

NOT_DONE = {
    "deploy": "Result: QA was not deployed.",
    "update": "Result: QA was not updated.",
    "rollback": "Result: QA was not rolled back.",
}
FIX_TAILSCALE = 'Do the owner-guide step "Set up Tailscale", then run this command again.'
FIX_FUNNEL_FOREIGN = (
    "Turn off the other Funnel sharing on this Mac (run: tailscale funnel reset, if you do not need it), "
    "then run this command again."
)
FIX_QA_SETUP = "Run ./scripts/init.sh --qa-settings-setup, then run this command again."
FIX_BUILD = "Run ./scripts/init.sh --container-build, then run this command again."
FIX_OLLAMA = "Do the Drafting step shown above, then run this command again."
MSG_TS_MISSING = "Tailscale is not installed on this computer."
MSG_TS_STOPPED = "Tailscale is installed but not logged in or not turned on."
MSG_TS_NO_FUNNEL = "Tailscale does not allow HTTPS and Funnel for this account yet."
MSG_FUNNEL_FOREIGN = "Tailscale Funnel on this Mac is already sharing something else on the HTTPS port."
MSG_TS_UNREADABLE = "Tailscale did not say what it is sharing."
MSG_FOREIGN = "A container named {} exists in Docker Desktop, but Manijero did not create it.".format(CONTAINER_NAME)
FIX_FOREIGN = "Rename or delete that container in Docker Desktop, then run this command again."
MSG_BUSY = (
    "Another QA command is running in another Terminal window. Wait until it shows its Result: line, "
    "then run this command again."
)
MSG_NO_TTY = "There is no Terminal window to ask you to confirm in."
FIX_NO_TTY = "Run this command in a Terminal window you can type in."
MSG_NO_IMAGE = "There is no answer service image on this computer yet."
MSG_OLD_LAUNCHER = "The answer service image is older than QA support (it has no pilot launcher)."
MSG_OTHER_CAMPAIGN = "The answer service image was built for another campaign than the QA settings file."
MSG_NOT_DEPLOYED = "QA has not been deployed yet, so there is nothing to update."
FIX_DEPLOY_FIRST = "Run {} first.".format(DEPLOY_COMMAND)
NO_PREVIOUS = "Result: there is no earlier QA version to go back to; nothing was changed."
TEST_DATA_LINE = "Test data only: the privacy review is still pending. Use made-up questions only; no real users."
NOT_RUNNING = "Result: QA is not running. Start it with {}.".format(DEPLOY_COMMAND)
STOPPED = "Result: QA has stopped and is no longer reachable from the internet."
NOTHING_TO_STOP = "Result: QA was not running, so there was nothing to stop."

# launcher refusal code -> (plain sentence, fix)
REFUSALS: Dict[str, Tuple[str, str]] = {
    "privacy_review_rejected": (
        "The recorded privacy review was rejected, so the service will not start.",
        "A developer must review the privacy review record.",
    ),
    "clients_permissions": (
        "The QA access key file is readable by other users on this Mac.",
        "Run ./scripts/init.sh --qa-settings-setup, then run this command again.",
    ),
    "clients_unreadable": (
        "The service inside Docker could not read the QA access key file.",
        "Open Docker Desktop settings, allow file sharing for your home folder, then run this command again.",
    ),
    "clients_missing": ("The QA access key file is missing.", FIX_QA_SETUP),
    "clients_invalid": ("The QA access key file is not valid.", FIX_QA_SETUP),
    "clients_empty": ("The QA access key file has no keys.", FIX_QA_SETUP),
    "campaign_invalid": ("The campaign in the QA settings file is not valid.", FIX_QA_SETUP),
    "pilot_profile_required": (
        "The image did not start in the pilot profile.",
        "A developer must review the image.",
    ),
}
_REFUSED = re.compile(r"^refused: ([a-z0-9_]{1,80})\s*$", re.MULTILINE)


# --- Facts --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Tailscale:
    state: str  # missing | stopped | unreadable | running
    dns_name: str = ""
    allowed: bool = False
    funnel: str = "off"  # off | ours | foreign | unreadable

    @property
    def address(self) -> str:
        return "https://{}".format(self.dns_name)


def _read_tailscale(ports: QaPorts) -> _Tailscale:
    return read_tailscale(ports.tailscale, ports.port)


def read_tailscale(cli: TailscaleCli, port: int) -> _Tailscale:
    """What Tailscale and Funnel say; also used by :mod:`app.qa_alerts`."""

    if not cli.present():
        return _Tailscale("missing")
    result = cli.run(TAILSCALE_STATUS_ARGV, TAILSCALE_TIMEOUT_SECONDS)
    try:
        document = json.loads(result.stdout) if result.returncode == 0 else None
    except ValueError:
        document = None
    if not isinstance(document, dict):
        return _Tailscale("stopped")
    node = document.get("Self") if isinstance(document.get("Self"), dict) else {}
    dns_name = str(node.get("DNSName") or "").rstrip(".")
    if document.get("BackendState") != "Running" or not dns_name.endswith(".ts.net"):
        return _Tailscale("stopped")
    allowed = _allows_https(node, document) and _allows_funnel(node)
    shared = cli.run(TAILSCALE_FUNNEL_STATUS_ARGV, TAILSCALE_TIMEOUT_SECONDS)
    if shared.returncode != 0:
        return _Tailscale("running", dns_name, allowed, "unreadable")
    text = shared.stdout.strip()
    try:
        funnel_document = json.loads(text) if text else {}
    except ValueError:
        return _Tailscale("running", dns_name, allowed, "unreadable")
    return _Tailscale("running", dns_name, allowed, _funnel_state(funnel_document, dns_name, port))


def _funnel_on(ports: QaPorts) -> bool:
    return ports.tailscale.run(funnel_on_argv(ports.port), TAILSCALE_TIMEOUT_SECONDS).returncode == 0


def _funnel_off(ports: QaPorts) -> bool:
    return ports.tailscale.run(funnel_off_argv(), TAILSCALE_TIMEOUT_SECONDS).returncode == 0


def _lock_path(ports: QaPorts) -> Path:
    return ports.home / LOCK_NAME


def _is_ours(found: Optional[lc.ContainerInfo]) -> bool:
    return (
        found is not None
        and found.labels.get(lc.MANAGED_LABEL) == "1"
        and found.labels.get(LABEL_ENVIRONMENT) == profiles.QA
    )


is_qa_container = _is_ours  # public name for :mod:`app.qa_alerts`


def _qa_container(ports: QaPorts) -> Optional[lc.ContainerInfo]:
    return lc.container_info(ports.docker, CONTAINER_NAME)


def version_tag(labels: Mapping[str, str]) -> str:
    return lc.versioned_tag(labels.get(lc.LABEL_RELEASE, "unknown"), labels.get(lc.LABEL_REVISION, "unknown"))


def run_argv(port: int, campaign: str, clients_file: Path) -> List[str]:
    """The fixed ``docker run`` arguments: loopback publish, fixed environment, read-only keys."""

    return [
        "run", "--detach", "--init",
        "--name", CONTAINER_NAME,
        "--label", "{}=1".format(lc.MANAGED_LABEL),
        "--label", "{}={}".format(LABEL_ENVIRONMENT, profiles.QA),
        "--publish", "{}:{}:{}".format(service.HOST, port, lc.CONTAINER_PORT),
        "--env", "{}={}".format(profiles.CAMPAIGN_KEY, campaign),
        "--env", "{}={}".format(profiles.PROFILE_KEY, profiles.QA_PROFILE),
        "--env", "{}={}".format(profiles.ENVIRONMENT_KEY, profiles.QA),
        "--env", "{}=yes".format(TEST_DATA_FLAG),
        "--env", "{}={}".format(profiles.CLIENTS_FILE_KEY, CLIENTS_MOUNT),
        "--mount", "type=bind,source={},target={},readonly".format(clients_file, CLIENTS_MOUNT),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--restart", "no",
        TAG_CURRENT,
    ]


@dataclass
class _Facts:
    tailscale: _Tailscale
    docker: str
    settings: Optional[profiles.ProfileSettings] = None
    settings_problem: Optional[Tuple[str, str]] = None
    credentials_problem: Optional[str] = None
    token: Optional[str] = None
    drafting: Optional[service.Check] = None
    pin_problem: Optional[str] = None
    container: Optional[lc.ContainerInfo] = None
    local: Optional[lc.ImageInfo] = None
    current: Optional[lc.ImageInfo] = None
    previous: Optional[lc.ImageInfo] = None
    lock_held: bool = False
    port_owner: str = service.PORT_FREE

    @property
    def docker_ready(self) -> bool:
        return self.docker == lc.DOCKER_READY

    @property
    def running(self) -> bool:
        return _is_ours(self.container) and bool(self.container and self.container.running)


def _gather(ctx: bootstrap.Context, ports: QaPorts) -> _Facts:
    facts = _Facts(tailscale=_read_tailscale(ports), docker=lc.docker_state(ports.docker))
    try:
        facts.settings = profiles.read_profile_settings(profiles.QA, ports.home)
    except profiles.ProfileSettingsError as error:
        if error.code == "settings_missing":
            facts.settings_problem = (
                "QA is not prepared on this computer: the QA settings file does not exist.",
                FIX_QA_SETUP,
            )
        else:
            facts.settings_problem = (error.sentence, "Fix the QA settings file as described above, then run this command again.")
    paths = profiles.credential_paths(ports.home, profiles.QA_CLIENT_ID)
    facts.credentials_problem = profiles.check_credentials(paths, profiles.QA_CLIENT_ID)
    if facts.credentials_problem is None:
        facts.token = profiles.read_token(paths.token)
    try:
        _, model = bootstrap.load_pins(ctx, ports.tools.today())
        facts.drafting = service.drafting_check(ports.tools, model)
    except bootstrap.BootstrapError as error:
        facts.pin_problem = error.message
    facts.lock_held = bootstrap.lock_is_held(_lock_path(ports))
    if facts.docker_ready:
        facts.container = _qa_container(ports)
        facts.local = lc.image_info(ports.docker, lc.LOCAL_TAG)
        facts.current = lc.image_info(ports.docker, TAG_CURRENT)
        facts.previous = lc.image_info(ports.docker, TAG_PREVIOUS)
    if not facts.running:
        facts.port_owner = ports.probe.health(ports.port)
    return facts


class _Problems:
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


def _image_problems(image: Optional[lc.ImageInfo], campaign: Optional[str], problems: _Problems) -> None:
    if image is None:
        problems.add(MSG_NO_IMAGE, FIX_BUILD)
    elif "pilot" not in image.labels.get(LABEL_LAUNCHERS, "").split(","):
        problems.add(MSG_OLD_LAUNCHER, FIX_BUILD)
    elif campaign is not None and image.labels.get(lc.LABEL_CAMPAIGN) != campaign:
        problems.add(MSG_OTHER_CAMPAIGN, FIX_BUILD)


def _problems(op: str, facts: _Facts, ports: QaPorts) -> _Problems:
    problems = _Problems()
    ts = facts.tailscale
    if ts.state == "missing":
        problems.add(MSG_TS_MISSING, FIX_TAILSCALE)
    elif ts.state != "running":
        problems.add(MSG_TS_STOPPED, FIX_TAILSCALE)
    else:
        if not ts.allowed:
            problems.add(MSG_TS_NO_FUNNEL, FIX_TAILSCALE)
        if ts.funnel == "foreign":
            problems.add(MSG_FUNNEL_FOREIGN, FIX_FUNNEL_FOREIGN)
        elif ts.funnel == "unreadable":
            problems.add(MSG_TS_UNREADABLE, FIX_TAILSCALE)
    if facts.docker == lc.DOCKER_MISSING:
        problems.add(lc.MSG_DOCKER_MISSING, lc.FIX_INSTALL_DOCKER)
    elif facts.docker == lc.DOCKER_CLOSED:
        problems.add(lc.MSG_DOCKER_CLOSED, lc.FIX_OPEN_DOCKER)
    if facts.settings_problem is not None:
        problems.add(*facts.settings_problem)
    elif facts.credentials_problem is not None:
        problems.add("The QA access keys are missing or incomplete.", FIX_QA_SETUP)
    if facts.pin_problem is not None:
        problems.add(facts.pin_problem, service.FIX_PIN)
    elif facts.drafting is not None and not facts.drafting.ok:
        problems.add(facts.drafting.line, FIX_OLLAMA)
    if facts.lock_held:
        problems.add(MSG_BUSY, service.FIX_WAIT)
    if facts.docker_ready:
        if facts.container is not None and not _is_ours(facts.container):
            problems.add(MSG_FOREIGN, FIX_FOREIGN)
        elif not facts.running and facts.port_owner != service.PORT_FREE:
            problems.add(
                "Port {} is in use by another program.".format(ports.port),
                "Close the other program that uses port {}, then run this command again.".format(ports.port),
            )
        campaign = facts.settings.campaign if facts.settings is not None else None
        if op == "deploy":
            _image_problems(facts.current or facts.local, campaign, problems)
        elif op == "update":
            if facts.current is None:
                problems.add(MSG_NOT_DEPLOYED, FIX_DEPLOY_FIRST)
            _image_problems(facts.local, campaign, problems)
        elif op == "rollback" and facts.previous is not None:
            _image_problems(facts.previous, campaign, problems)
    return problems


def _confirm(ports: QaPorts, lines: Sequence[str]) -> bool:
    for line in lines:
        ports.out(line)
    answer = ports.tools.prompter.ask("Type yes and press Enter to continue: ")
    return answer is not None and answer.strip().lower() == "yes"


# --- Container work -----------------------------------------------------------------------


def _save_logs(ports: QaPorts, log: bootstrap.RunLog) -> str:
    result = ports.docker.run(["logs", CONTAINER_NAME], lc.LOGS_TIMEOUT_SECONDS)
    log.write("== container output ==")
    log.write(result.stdout)
    log.write(result.stderr)
    return result.stdout + "\n" + result.stderr


def _remove_ours(ports: QaPorts, log: bootstrap.RunLog) -> bool:
    found = _qa_container(ports)
    if found is None:
        return True
    if not _is_ours(found):
        return False
    _save_logs(ports, log)
    return ports.docker.run(["rm", "--force", CONTAINER_NAME], lc.DOCKER_TIMEOUT_SECONDS).returncode == 0


def _plain_failure(output: str, again: str) -> Tuple[str, str]:
    """Translate a launcher ``refused: <code>`` line; no other container output is shown."""

    match = _REFUSED.search(output)
    if match and match.group(1) in REFUSALS:
        return REFUSALS[match.group(1)]
    if match:
        return ("The answer service refused to start ({}).".format(match.group(1)), again)
    return ("The answer service container stopped while it was starting.", again)


def _wait_ready(ports: QaPorts, log: bootstrap.RunLog, again: str) -> Optional[Tuple[str, str]]:
    deadline = ports.clock.monotonic() + lc.START_TIMEOUT_SECONDS
    while True:
        found = _qa_container(ports)
        if found is None or not found.running:
            output = _save_logs(ports, log) if found is not None else ""
            return _plain_failure(output, again)
        if ports.probe.health(ports.port) == service.SERVICE_NAME and ports.probe.ready(ports.port) == service.READY:
            return None
        if ports.clock.monotonic() >= deadline:
            return (
                "The answer service did not answer within {} seconds.".format(int(lc.START_TIMEOUT_SECONDS)),
                again,
            )
        ports.clock.sleep(lc.POLL_SECONDS)


def _start(ports: QaPorts, facts: _Facts, log: bootstrap.RunLog, again: str) -> Optional[Tuple[str, str]]:
    """Replace the QA container by one running ``qa-current``; ``None`` when it is ready and smoked."""

    assert facts.settings is not None and facts.token is not None
    if not _remove_ours(ports, log):
        return ("The earlier QA container could not be cleared.", lc.FIX_OPEN_DOCKER)
    clients = profiles.credential_paths(ports.home, profiles.QA_CLIENT_ID).clients
    argv = run_argv(ports.port, facts.settings.campaign, clients)
    log.write("$ docker " + " ".join(argv))
    result = ports.docker.run(argv, lc.DOCKER_TIMEOUT_SECONDS)
    log.write(result.stdout)
    log.write(result.stderr)
    if result.returncode != 0:
        return ("Docker Desktop could not start the QA container.", again)
    failure = _wait_ready(ports, log, again)
    if failure is not None:
        return failure
    failures = ports.smoke(service.service_url(ports.port), facts.token)
    if failures:
        log.write("smoke: " + ",".join(failures))
        return ("The answer service started but its self-check failed ({}).".format(", ".join(failures)), again)
    return None


def _tag(ports: QaPorts, source: str, target: str) -> bool:
    return ports.docker.run(["tag", source, target], lc.DOCKER_TIMEOUT_SECONDS).returncode == 0


def _untag(ports: QaPorts, tag: str) -> None:
    ports.docker.run(["image", "rm", tag], lc.DOCKER_TIMEOUT_SECONDS)


def _write_addresses(ports: QaPorts, address: str) -> None:
    profiles.write_public_url(ports.home, address)
    directory = ports.address_file.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / ".{}.new".format(ports.address_file.name)
    temporary.write_text(address + "\n", encoding="utf-8")
    os.replace(temporary, ports.address_file)


def _wait_public(ports: QaPorts, address: str) -> bool:
    deadline = ports.clock.monotonic() + PUBLIC_WAIT_SECONDS
    while True:
        if ports.public(address):
            return True
        if ports.clock.monotonic() >= deadline:
            return False
        ports.clock.sleep(PUBLIC_POLL_SECONDS)


def _log(ports: QaPorts, op: str) -> bootstrap.RunLog:
    return bootstrap.RunLog(ports.home / "logs", "qa-{}".format(op), ports.clock.now)


# --- Deploy -------------------------------------------------------------------------------


def run_deploy(ctx: bootstrap.Context, ports: QaPorts) -> int:
    out = ports.out
    out("Checking what QA needs...")
    facts = _gather(ctx, ports)
    if facts.running and facts.tailscale.state == "running" and facts.tailscale.funnel == "ours":
        return _already_running(ports, facts)
    problems = _problems("deploy", facts, ports)
    if not ports.tty:
        problems.add(MSG_NO_TTY, FIX_NO_TTY)
    if problems:
        return problems.report(out, NOT_DONE["deploy"])
    address = facts.tailscale.address
    if not _confirm(
        ports,
        [
            "QA will become reachable from the internet at {} for made-up test questions only.".format(address),
            "Do not use real questions or real land details. {} takes it off the internet again.".format(STOP_COMMAND),
        ],
    ):
        out("Nothing was changed.")
        out("{} You did not type yes.".format(NOT_DONE["deploy"]))
        return 1
    try:
        with lc.container_lock(_lock_path(ports), MSG_BUSY):
            return _deploy_locked(ctx, ports, facts)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(NOT_DONE["deploy"], service.FIX_WAIT))
        return 1


def _already_running(ports: QaPorts, facts: _Facts) -> int:
    ports.out(
        "Result: QA is already running at {}; nothing was changed. To ship a newer image use {}.".format(
            facts.tailscale.address, UPDATE_COMMAND
        )
    )
    return 0


def _deploy_locked(ctx: bootstrap.Context, ports: QaPorts, facts: _Facts) -> int:
    out = ports.out
    fresh = _gather(ctx, ports)
    if fresh.running and fresh.tailscale.funnel == "ours":
        return _already_running(ports, fresh)
    if fresh.container is not None and not _is_ours(fresh.container):
        out(MSG_FOREIGN)
        out("{} {}".format(NOT_DONE["deploy"], FIX_FOREIGN))
        return 1
    log = _log(ports, "deploy")
    log_path = log.ensure()
    again = "Run {} again; if it fails again, send the log file to a developer.".format(DEPLOY_COMMAND)
    address = fresh.tailscale.address
    funnel_started = False
    created_current = False
    out("Starting QA (this can take up to two minutes)...")
    try:
        if fresh.current is None:
            if not _tag(ports, lc.LOCAL_TAG, TAG_CURRENT):
                return _deploy_failed(ports, log, log_path, False, False, ("Docker Desktop could not tag the image.", lc.FIX_OPEN_DOCKER))
            created_current = True
        failure = _start(ports, fresh, log, again)
        if failure is None:
            if fresh.tailscale.funnel != "ours":
                if not _funnel_on(ports):
                    failure = ("Tailscale could not turn on Funnel.", FIX_TAILSCALE)
                else:
                    funnel_started = True
        if failure is None and not _wait_public(ports, address):
            failure = (
                "The internet address {} does not answer yet. Tailscale may still be preparing its certificate.".format(address),
                "Wait a minute, then run {} again.".format(DEPLOY_COMMAND),
            )
        if failure is None:
            try:
                _write_addresses(ports, address)
            except (OSError, profiles.ProfileSettingsError):
                failure = ("The address could not be saved in the QA settings file or qa-address.local.", again)
    except KeyboardInterrupt:
        _cleanup(ports, log, funnel_started, created_current)
        out("")
        out("The deploy was stopped with Ctrl+C, so QA was taken off the internet and its container removed.")
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again when you are ready.".format(NOT_DONE["deploy"], DEPLOY_COMMAND))
        return 1
    except BaseException:
        _cleanup(ports, log, funnel_started, created_current)
        raise
    if failure is not None:
        return _deploy_failed(ports, log, log_path, funnel_started, created_current, failure)
    image = lc.image_info(ports.docker, TAG_CURRENT)
    labels = image.labels if image is not None else {}
    out("")
    out("QA runs {} in container {}, with drafting through Ollama on this Mac.".format(version_tag(labels), CONTAINER_NAME))
    out("Address: {}".format(address))
    out("WARNING: QA is for made-up test questions only. The privacy review is still pending; no real users.")
    out("Next steps:")
    out("  Rebuild the QA apps so they use this address (docs/owner-guide/qa.md, \"Build the QA test apps\").")
    out("  On a phone, open {}/health in the browser; it should show a short status.".format(address))
    out("  {}   check it at any time".format(STATUS_COMMAND))
    out("  {}     take it off the internet when you are done".format(STOP_COMMAND))
    out("Result: QA is running at {} for test data only.".format(address))
    return 0


def _cleanup(ports: QaPorts, log: bootstrap.RunLog, funnel_started: bool, created_current: bool) -> None:
    if funnel_started:
        _funnel_off(ports)
    _remove_ours(ports, log)
    if created_current:
        _untag(ports, TAG_CURRENT)


def _deploy_failed(
    ports: QaPorts,
    log: bootstrap.RunLog,
    log_path: Path,
    funnel_started: bool,
    created_current: bool,
    failure: Tuple[str, str],
) -> int:
    _cleanup(ports, log, funnel_started, created_current)
    ports.out(failure[0])
    ports.out("Details are in the log file: {}".format(log_path))
    ports.out("{} {}".format(NOT_DONE["deploy"], failure[1]))
    return 1


# --- Update and rollback ------------------------------------------------------------------


def run_update(ctx: bootstrap.Context, ports: QaPorts) -> int:
    return _replace_version(ctx, ports, "update")


def run_rollback(ctx: bootstrap.Context, ports: QaPorts) -> int:
    return _replace_version(ctx, ports, "rollback")


def _replace_version(ctx: bootstrap.Context, ports: QaPorts, op: str) -> int:
    out = ports.out
    out("Checking what QA needs...")
    facts = _gather(ctx, ports)
    if op == "rollback" and facts.docker_ready and facts.previous is None:
        out(NO_PREVIOUS)
        return 1
    problems = _problems(op, facts, ports)
    if not problems and op == "update" and facts.current and facts.local and facts.current.image_id == facts.local.image_id:
        out("Result: nothing new to ship; QA already runs {}.".format(version_tag(facts.current.labels)))
        return 0
    if not ports.tty:
        problems.add(MSG_NO_TTY, FIX_NO_TTY)
    if problems:
        return problems.report(out, NOT_DONE[op])
    assert facts.local is not None or op == "rollback"
    incoming = facts.local if op == "update" else facts.previous
    assert incoming is not None
    if not _confirm(
        ports,
        [
            "QA will switch to {} and restart. QA stays at {}.".format(version_tag(incoming.labels), facts.tailscale.address),
            "Made-up test questions only.",
        ],
    ):
        out("Nothing was changed.")
        out("{} You did not type yes.".format(NOT_DONE[op]))
        return 1
    try:
        with lc.container_lock(_lock_path(ports), MSG_BUSY):
            return _replace_locked(ctx, ports, op)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(NOT_DONE[op], service.FIX_WAIT))
        return 1


def _swap_tags(ports: QaPorts, op: str, had_previous: bool) -> bool:
    """Make the incoming image ``qa-current`` and the running one ``qa-previous``."""

    if op == "update":
        return _tag(ports, TAG_CURRENT, TAG_PREVIOUS) and _tag(ports, lc.LOCAL_TAG, TAG_CURRENT)
    ok = _tag(ports, TAG_CURRENT, TAG_SWAP) and _tag(ports, TAG_PREVIOUS, TAG_CURRENT) and _tag(ports, TAG_SWAP, TAG_PREVIOUS)
    _untag(ports, TAG_SWAP)
    return ok


def _restore_tags(ports: QaPorts, op: str, had_previous: bool) -> None:
    if op == "update":
        _tag(ports, TAG_PREVIOUS, TAG_CURRENT)
        if not had_previous:
            _untag(ports, TAG_PREVIOUS)
    else:
        _swap_tags(ports, "rollback", True)


def _replace_locked(ctx: bootstrap.Context, ports: QaPorts, op: str) -> int:
    out = ports.out
    facts = _gather(ctx, ports)
    if facts.container is not None and not _is_ours(facts.container):
        out(MSG_FOREIGN)
        out("{} {}".format(NOT_DONE[op], FIX_FOREIGN))
        return 1
    if facts.current is None:
        out(MSG_NOT_DEPLOYED)
        out("{} {}".format(NOT_DONE[op], FIX_DEPLOY_FIRST))
        return 1
    log = _log(ports, op)
    log_path = log.ensure()
    command = UPDATE_COMMAND if op == "update" else ROLLBACK_COMMAND
    again = "Run {} again; if it fails again, send the log file to a developer.".format(command)
    had_previous = facts.previous is not None
    out("Replacing the QA container (this can take up to two minutes)...")
    failure: Optional[Tuple[str, str]]
    try:
        if not _swap_tags(ports, op, had_previous):
            _restore_tags(ports, op, had_previous)
            failure = ("Docker Desktop could not change the image tags.", lc.FIX_OPEN_DOCKER)
            tags_changed = False
        else:
            tags_changed = True
            failure = _start(ports, facts, log, again)
            if failure is None and facts.tailscale.funnel != "ours":
                failure = None if _funnel_on(ports) else ("Tailscale could not turn on Funnel.", FIX_TAILSCALE)
    except KeyboardInterrupt:
        _recover(ports, facts, op, had_previous, log, True)
        out("")
        out("The {} was stopped with Ctrl+C; the earlier QA version was started again.".format(op))
        out("Details are in the log file: {}".format(log_path))
        out("{} Run {} again when you are ready.".format(NOT_DONE[op], command))
        return 1
    if failure is not None:
        restored = _recover(ports, facts, op, had_previous, log, tags_changed)
        out(failure[0])
        out("Details are in the log file: {}".format(log_path))
        if restored:
            out("{} The earlier version is running again. {}".format(NOT_DONE[op], failure[1]))
        else:
            out("{} The earlier version could not be started again either: run {} to start QA fresh.".format(
                NOT_DONE[op], DEPLOY_COMMAND))
        return 1
    image = lc.image_info(ports.docker, TAG_CURRENT)
    tag = version_tag(image.labels if image is not None else {})
    if op == "update":
        out(
            "Result: QA was updated to {}. If something is wrong, run {}.".format(tag, ROLLBACK_COMMAND)
        )
    else:
        out("Result: QA was rolled back to {}.".format(tag))
    return 0


def _recover(
    ports: QaPorts, facts: _Facts, op: str, had_previous: bool, log: bootstrap.RunLog, tags_changed: bool
) -> bool:
    """Put the earlier tags back and start the earlier version again; ``True`` when it runs."""

    if tags_changed:
        _restore_tags(ports, op, had_previous)
    return _start(ports, facts, log, "") is None


# --- Status -------------------------------------------------------------------------------


_STARTED = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")


def _started_text(started_at: str) -> str:
    match = _STARTED.match(started_at)
    return "{} {} UTC".format(match.group(1), match.group(2)) if match else "at an unknown time"


def _line(ok: bool, label: str, text: str) -> str:
    return "{:<8} {}: {}".format(bootstrap.OK if ok else bootstrap.PROBLEM, label, text)


def _read_address_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def run_status(ctx: bootstrap.Context, ports: QaPorts) -> int:
    out = ports.out
    state = lc.docker_state(ports.docker)
    if state != lc.DOCKER_READY:
        out(lc.MSG_DOCKER_MISSING if state == lc.DOCKER_MISSING else lc.MSG_DOCKER_CLOSED)
        out(NOT_RUNNING)
        return 1
    found = _qa_container(ports)
    if not _is_ours(found) or not (found and found.running):
        if found is not None and not _is_ours(found):
            out("{} It was left as it is.".format(MSG_FOREIGN))
        out(NOT_RUNNING)
        return 1
    assert found is not None
    checks: List[Tuple[bool, str, str]] = []  # ok, line, fix
    image = lc.image_info(ports.docker, TAG_CURRENT)
    labels = image.labels if image is not None else {}
    checks.append(
        (
            True,
            _line(
                True, "Container",
                "{} runs {} (knowledge release {}), started {}.".format(
                    CONTAINER_NAME, version_tag(labels), labels.get(lc.LABEL_RELEASE, "unknown"),
                    _started_text(found.started_at),
                ),
            ),
            "",
        )
    )
    answers = ports.probe.health(ports.port) == service.SERVICE_NAME and ports.probe.ready(ports.port) == service.READY
    checks.append(
        (
            answers,
            _line(answers, "Answers", "the service answers and is ready." if answers else "the service does not answer."),
            "Run {}, then {}.".format(STOP_COMMAND, DEPLOY_COMMAND),
        )
    )
    relay = ports.docker.run(["exec", CONTAINER_NAME, *lc.RELAY_CHECK], lc.DOCKER_TIMEOUT_SECONDS).returncode == 0
    checks.append(
        (
            relay,
            _line(
                relay, "Drafting",
                "the container reaches Ollama on this Mac." if relay else
                "the container cannot reach Ollama. Answers continue without drafting.",
            ),
            "Open Ollama on this Mac, then run {}, then {}.".format(STOP_COMMAND, DEPLOY_COMMAND),
        )
    )
    tailscale = _read_tailscale(ports)
    reachable = tailscale.state == "running" and tailscale.funnel == "ours"
    if reachable:
        text = "Funnel is on: {} reaches this Mac's QA service.".format(tailscale.address)
    elif tailscale.state != "running":
        text = "Tailscale is not running, so QA is not reachable from the internet."
    else:
        text = "Funnel is not pointing at the QA service."
    checks.append((reachable, _line(reachable, "Internet address", text),
                   FIX_TAILSCALE if tailscale.state != "running" else "Run {}, then {}.".format(STOP_COMMAND, DEPLOY_COMMAND)))
    settings_url: Optional[str] = None
    try:
        settings_url = profiles.read_profile_settings(profiles.QA, ports.home).public_url
    except profiles.ProfileSettingsError:
        pass
    file_url = _read_address_file(ports.address_file)
    agree = bool(settings_url) and settings_url == file_url and (not reachable or settings_url == tailscale.address)
    checks.append(
        (
            agree,
            _line(
                agree, "Address files",
                "the QA settings file and qa-address.local agree." if agree else
                "the QA settings file and qa-address.local do not both hold the QA address.",
            ),
            "Run {}, then {}.".format(STOP_COMMAND, DEPLOY_COMMAND),
        )
    )
    for _, line, _ in checks:
        out(line)
    out(TEST_DATA_LINE)
    for ok, _, fix in checks:
        if not ok:
            out("Result: QA needs attention: {}".format(fix))
            return 1
    out("Result: QA is running at {} for test data only.".format(tailscale.address))
    return 0


# --- Stop ---------------------------------------------------------------------------------


def run_stop(ctx: bootstrap.Context, ports: QaPorts) -> int:
    out = ports.out
    try:
        with lc.container_lock(_lock_path(ports), MSG_BUSY):
            return _stop_locked(ports)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("Result: nothing was stopped. {}".format(service.FIX_WAIT))
        return 1


def _stop_locked(ports: QaPorts) -> int:
    out = ports.out
    stopped_something = False
    tailscale = _read_tailscale(ports)
    if tailscale.state == "running" and tailscale.funnel == "ours":
        out("Taking QA off the internet...")
        if not _funnel_off(ports):
            out("Tailscale could not turn Funnel off, so the QA container was left running.")
            out("Result: QA could not be stopped. Open the Tailscale app and turn off sharing, then run {} again.".format(STOP_COMMAND))
            return 1
        stopped_something = True
    if lc.docker_state(ports.docker) == lc.DOCKER_READY:
        found = _qa_container(ports)
        if found is not None and not _is_ours(found):
            out("{} It was left as it is.".format(MSG_FOREIGN))
        elif found is not None:
            log = _log(ports, "stop")
            out("Stopping the QA container...")
            if found.running:
                result = ports.docker.run(
                    ["stop", "--time", str(lc.STOP_TIMEOUT_SECONDS), CONTAINER_NAME],
                    lc.STOP_TIMEOUT_SECONDS + lc.DOCKER_TIMEOUT_SECONDS,
                )
                if result.returncode != 0:
                    log.write(result.stderr)
                    out("The QA container did not stop. Quit and reopen Docker Desktop, then run {} again.".format(STOP_COMMAND))
                    out("Result: QA could not be stopped.")
                    return 1
            if not _remove_ours(ports, log):
                out("The QA container could not be removed. Quit and reopen Docker Desktop, then run {} again.".format(STOP_COMMAND))
                out("Result: QA could not be stopped.")
                return 1
            stopped_something = True
    if not stopped_something:
        out(NOTHING_TO_STOP)
        return 0
    out(STOPPED)
    return 0


# --- Real ports ---------------------------------------------------------------------------


class SystemTailscaleCli:
    """The ``tailscale`` command (``MANIJERO_TAILSCALE_CLI`` replaces it in tests only)."""

    def __init__(self, repo_root: Path, cli: Optional[str] = None) -> None:
        self._root = Path(repo_root)
        self._cli = cli or os.environ.get(TAILSCALE_CLI_ENV, "").strip() or None

    def _executable(self) -> Optional[str]:
        if self._cli:
            return shutil.which(self._cli)
        return shutil.which("tailscale") or (TAILSCALE_APP_CLI if os.access(TAILSCALE_APP_CLI, os.X_OK) else None)

    def present(self) -> bool:
        return self._executable() is not None

    def run(self, args: Sequence[str], timeout: float) -> bootstrap.CommandResult:
        executable = self._executable()
        if executable is None:
            return bootstrap.CommandResult(127, "", "tailscale not found")
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


def system_smoke(base_url: str, token: str) -> Sequence[str]:
    """``/health``, ``/ready`` and one synthetic ``/ask`` on loopback; fixed failure codes only."""

    from app.pilot_ops import run_smoke

    return run_smoke(base_url, token=token).failures


def system_public_probe(address: str) -> bool:
    """Whether ``<address>/health`` answers with the Manijero service name over HTTPS."""

    request = urllib.request.Request(address.rstrip("/") + "/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_TIMEOUT_SECONDS) as response:  # noqa: S310 - https only
            document = json.loads(response.read(service.MAX_PROBE_BYTES).decode("utf-8"))
            return response.getcode() == 200 and isinstance(document, dict) and document.get("service") == service.SERVICE_NAME
    except (OSError, ValueError, urllib.error.URLError):
        return False
