"""Tell the owner on Telegram when the QA answer service stops working, on the owner's Mac.

Operator-only and stdlib-only; the answer service never imports this module. A launchd user agent
(``org.manijero.qa-alerts``) runs ``backend/scripts/qa_alerts.py check`` every 5 minutes while the
Mac is awake. Each run looks at QA the same way the owner would (Docker, loopback ``/health``,
``/ready``, ``/metrics``, then the public Tailscale address), keeps a small state file, and sends
one fixed-text Telegram message when a problem is confirmed on two checks in a row, a reminder at
most every 4 hours, and one "back to normal" message. Messages never hold a token, chat id, the
``ts.net`` address, question or answer text, land data, names, or client ids.

The Telegram bot token and chat id live only in ``~/manijero/alerts/credentials/telegram.json``
(``0600``). The token is used only in-process (never argv, a child environment, a log, or an
exception text): every Telegram failure becomes a fixed code. ``launchctl`` is only ever called
for the label ``org.manijero.qa-alerts``. A sleeping or switched-off Mac cannot be detected. See
``docs/specs/qa_service_alerts.md``. ``MANIJERO_ALERTS_HOME``, ``MANIJERO_LAUNCHCTL_CLI``,
``MANIJERO_LAUNCH_AGENTS_DIR`` and ``MANIJERO_TELEGRAM_API`` (loopback only) are for tests.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from app import environment_profiles as profiles
from app import local_container as lc
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service
from app import qa_deployment as qa
from app.local_generation import loopback_opener

SETUP_COMMAND = "./scripts/init.sh --qa-alerts-setup"
START_COMMAND = "./scripts/init.sh --qa-alerts-start"
STOP_COMMAND = "./scripts/init.sh --qa-alerts-stop"
STATUS_COMMAND = "./scripts/init.sh --qa-alerts-status"
TEST_COMMAND = "./scripts/init.sh --qa-alerts-test"
OPERATIONS = ("setup", "start", "stop", "status", "test", "check")

HOME_ENV = "MANIJERO_ALERTS_HOME"  # tests only
LAUNCHCTL_ENV = "MANIJERO_LAUNCHCTL_CLI"  # tests only
AGENTS_DIR_ENV = "MANIJERO_LAUNCH_AGENTS_DIR"  # tests only
TELEGRAM_API_ENV = "MANIJERO_TELEGRAM_API"  # tests only, loopback only
LABEL = "org.manijero.qa-alerts"
INTERVAL_SECONDS = 300
LAUNCHD_PATH = (
    "/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin"
)

CREDENTIALS_NAME = "telegram.json"
STATE_NAME = "state.json"
LOG_NAME = "qa-alerts.log"
LAUNCHD_LOG_NAME = "launchd.log"
LOG_LIMIT_BYTES = 1_000_000
THRESHOLDS_FILE = Path(__file__).resolve().parents[1] / "monitoring" / "thresholds.json"

CONFIRM_CHECKS = 2  # consecutive checks before an alert or a recovery
REMINDER = timedelta(hours=4)
SAME_KIND_CAP = timedelta(minutes=60)
STALE_CHECK = timedelta(minutes=15)
WINDOW_SLACK_SECONDS = 90.0  # a check may run a little early
KEEP_EXTRA_SECONDS = 600.0
SETUP_TRIES = 3
TELEGRAM_TIMEOUT_SECONDS = 10.0
MAX_REPLY_BYTES = 1_048_576
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

TOKEN_PATTERN = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,80}")
API_PATTERN = re.compile(r"http://127\.0\.0\.1:[0-9]{1,5}")
WINDOW_PATTERN = re.compile(r"([0-9]{1,4})([smh])")

# --- Wording ------------------------------------------------------------------------------

TEST_MESSAGE = "Manijero QA: this is a test alert. If you can read it, alerts reach you."
RECOVERY_MESSAGE = "Manijero QA is back to normal (problem from {start} to {end})."
REMINDER_MESSAGE = "Manijero QA: still a problem since {since}: {text} {step}"
PROBLEM_MESSAGE = "Manijero QA: {text} {step}"

FIX_SETUP = "Run {}, then run this command again.".format(SETUP_COMMAND)
FIX_UNREACHABLE = "Check this Mac's internet connection, then run this command again."
FIX_NO_TTY = "Run this command in a Terminal window you can type in."
FIX_STATUS_STEP = "Run ./scripts/init.sh --qa-status on your Mac."

# kind -> (problem sentence, first step, short name for status)
KINDS: Dict[str, Tuple[str, str, str]] = {
    "down_docker": (
        "QA is down: Docker Desktop is not open.",
        "Open Docker Desktop, then run ./scripts/init.sh --qa-deploy.",
        "QA is down because Docker Desktop is not open",
    ),
    "down": (
        "QA is down: the QA service is not running or does not answer.",
        FIX_STATUS_STEP,
        "QA is down",
    ),
    "not_ready": (
        "QA is running but not ready to answer questions.",
        FIX_STATUS_STEP,
        "QA is not ready",
    ),
    "erroring": (
        "QA failed on {percent}% of questions in the last {minutes} minutes.",
        "Open the health dashboard, then run ./scripts/init.sh --qa-status.",
        "QA is failing on many questions",
    ),
    "unreachable": (
        "QA works on your Mac but phones cannot reach it.",
        "Open the Tailscale app, check you are logged in, then run ./scripts/init.sh --qa-status.",
        "QA works on this Mac but phones cannot reach it",
    ),
}

# Telegram failure code -> sentence and fix for the owner commands.
TELEGRAM_WORDS: Dict[str, Tuple[str, str]] = {
    "token_rejected": (
        "Telegram did not accept the bot token.",
        "Run {} to store a new one.".format(SETUP_COMMAND),
    ),
    "chat_unavailable": (
        "Telegram would not deliver to your chat.",
        "Open your bot in Telegram, press Start or send it a message, then run {}.".format(SETUP_COMMAND),
    ),
    "unreachable": ("Telegram could not be reached.", FIX_UNREACHABLE),
}
CREDENTIAL_WORDS: Dict[str, Tuple[str, str]] = {
    "missing": ("Telegram alerts are not set up yet.", "Run {}.".format(SETUP_COMMAND)),
    "unsafe": (
        "The stored Telegram details cannot be used.",
        "Run {} to store them again.".format(SETUP_COMMAND),
    ),
}


class AlertsUsageError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --- Paths and private files ----------------------------------------------------------------


def alerts_home(environ: Mapping[str, str]) -> Path:
    raw = (environ.get(HOME_ENV) or "").strip()
    return Path(raw).expanduser() if raw else Path.home() / "manijero" / "alerts"


def credentials_path(home: Path) -> Path:
    return Path(home) / "credentials" / CREDENTIALS_NAME


def state_path(home: Path) -> Path:
    return Path(home) / STATE_NAME


def log_path(home: Path) -> Path:
    return Path(home) / "logs" / LOG_NAME


def _private_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, profiles.PRIVATE_DIR)


def _write_private(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` with mode ``0600`` through a temporary file in the same folder."""

    _private_dir(path.parent)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".new-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.chmod(temporary, profiles.PRIVATE_FILE)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def append_log(home: Path, line: str) -> None:
    """One line per check; rolled at 1 MB, keeping one older file. Fixed codes and times only."""

    path = log_path(home)
    try:
        _private_dir(path.parent)
        if path.exists() and path.stat().st_size > LOG_LIMIT_BYTES:
            os.replace(path, path.with_name(LOG_NAME + ".1"))
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, profiles.PRIVATE_FILE)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(line.rstrip("\n") + "\n")
    except OSError:
        pass


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(STAMP_FORMAT)


def parse_stamp(text: Any) -> Optional[datetime]:
    if not isinstance(text, str):
        return None
    try:
        return datetime.strptime(text, STAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def local_time(text: Any) -> str:
    """``HH:MM`` in the Mac's local time for a stored stamp."""

    moment = parse_stamp(text)
    return moment.astimezone().strftime("%H:%M") if moment is not None else "an unknown time"


# --- Telegram -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Credentials:
    token: str = field(repr=False)
    chat_id: int = field(repr=False)


def load_credentials(home: Path) -> Tuple[Optional[Credentials], Optional[str]]:
    """The stored details, or a fixed code: ``missing`` or ``unsafe`` (wrong mode or content)."""

    path = credentials_path(home)
    if not path.exists():
        return None, "missing"
    try:
        if path.stat().st_mode & 0o777 != profiles.PRIVATE_FILE:
            return None, "unsafe"
        if path.parent.stat().st_mode & profiles.GROUP_OTHER:
            return None, "unsafe"
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "unsafe"
    token = document.get("bot_token") if isinstance(document, dict) else None
    chat = document.get("chat_id") if isinstance(document, dict) else None
    if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token) or isinstance(chat, bool) or not isinstance(chat, int):
        return None, "unsafe"
    return Credentials(token, chat), None


def write_credentials(home: Path, credentials: Credentials) -> None:
    _write_private(
        credentials_path(home),
        json.dumps({"bot_token": credentials.token, "chat_id": credentials.chat_id}) + "\n",
    )


@dataclass(frozen=True)
class TelegramReply:
    status: int  # 0 when nothing usable came back
    document: Any = None


class TelegramTransport(Protocol):
    def call(self, token: str, method: str, payload: Optional[Mapping[str, Any]]) -> TelegramReply: ...


def api_from_environment(environ: Mapping[str, str]) -> Optional[str]:
    raw = (environ.get(TELEGRAM_API_ENV) or "").strip()
    if not raw:
        return None
    if not API_PATTERN.fullmatch(raw):
        raise AlertsUsageError("{} must look like http://127.0.0.1:<port>.".format(TELEGRAM_API_ENV))
    return raw


class HttpTelegram:
    """The Telegram Bot API over HTTPS. The token is in the URL, so nothing here logs or raises it."""

    def __init__(self, api: Optional[str] = None) -> None:
        self._api = api
        self._opener = loopback_opener() if api else urllib.request.build_opener()

    def call(self, token: str, method: str, payload: Optional[Mapping[str, Any]]) -> TelegramReply:
        base = self._api or "https://api.telegram.org"
        body = json.dumps(payload if payload is not None else {}).encode("utf-8")
        request = urllib.request.Request(
            "{}/bot{}/{}".format(base, token, method),
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            try:
                with self._opener.open(request, timeout=TELEGRAM_TIMEOUT_SECONDS) as response:
                    status, raw = response.getcode(), response.read(MAX_REPLY_BYTES)
            except urllib.error.HTTPError as error:
                status, raw = error.code, error.read(MAX_REPLY_BYTES)
                error.close()
            try:
                document = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                document = None
            return TelegramReply(int(status), document)
        except Exception:  # noqa: BLE001 - never let a URL with the token reach an error text
            return TelegramReply(0, None)


def _accepted(reply: TelegramReply) -> bool:
    return reply.status == 200 and isinstance(reply.document, dict) and reply.document.get("ok") is True


def _failure_code(reply: TelegramReply, bad_request: str) -> str:
    if reply.status in (401, 404):
        return "token_rejected"
    if reply.status in (400, 403):
        return bad_request
    return "unreachable"


def check_token(transport: TelegramTransport, token: str) -> Optional[str]:
    reply = transport.call(token, "getMe", None)
    return None if _accepted(reply) else _failure_code(reply, "token_rejected")


def latest_private_chat(transport: TelegramTransport, token: str) -> Tuple[Optional[int], Optional[str]]:
    """The chat id of the newest private message to the bot; nothing else from the reply is read."""

    reply = transport.call(token, "getUpdates", {"timeout": 0, "allowed_updates": ["message"]})
    if not _accepted(reply):
        return None, _failure_code(reply, "token_rejected")
    updates = reply.document.get("result")
    best: Optional[Tuple[int, int]] = None
    for update in updates if isinstance(updates, list) else []:
        message = update.get("message") if isinstance(update, dict) else None
        chat = message.get("chat") if isinstance(message, dict) else None
        number = update.get("update_id") if isinstance(update, dict) else None
        identifier = chat.get("id") if isinstance(chat, dict) else None
        if (
            isinstance(chat, dict)
            and chat.get("type") == "private"
            and isinstance(identifier, int) and not isinstance(identifier, bool)
            and isinstance(number, int) and not isinstance(number, bool)
            and (best is None or number > best[0])
        ):
            best = (number, identifier)
    return (best[1], None) if best is not None else (None, "no_message")


def send_text(transport: TelegramTransport, credentials: Credentials, text: str) -> Optional[str]:
    """``None`` when sent, else a fixed failure code."""

    reply = transport.call(
        credentials.token,
        "sendMessage",
        {"chat_id": credentials.chat_id, "text": text, "disable_web_page_preview": True},
    )
    return None if _accepted(reply) else _failure_code(reply, "chat_unavailable")


# --- launchd --------------------------------------------------------------------------------


class Launchctl(Protocol):
    def present(self) -> bool: ...

    def is_loaded(self) -> bool: ...

    def bootstrap(self, plist: Path) -> bool: ...

    def bootout(self) -> bool: ...


class SystemLaunchctl:
    """``launchctl`` for the one label ``org.manijero.qa-alerts`` and nothing else."""

    def __init__(self, uid: int, cli: Optional[str] = None) -> None:
        self._domain = "gui/{}".format(uid)
        self._cli = cli or os.environ.get(LAUNCHCTL_ENV, "").strip() or "launchctl"

    def _executable(self) -> Optional[str]:
        return shutil.which(self._cli)

    def present(self) -> bool:
        return self._executable() is not None

    def _run(self, args: Sequence[str]) -> bool:
        executable = self._executable()
        if executable is None:
            return False
        try:
            completed = subprocess.run(  # noqa: S603 - fixed arguments for one label
                [executable, *args],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0

    def is_loaded(self) -> bool:
        return self._run(["print", "{}/{}".format(self._domain, LABEL)])

    def bootstrap(self, plist: Path) -> bool:
        return self._run(["bootstrap", self._domain, str(plist)])

    def bootout(self) -> bool:
        return self._run(["bootout", "{}/{}".format(self._domain, LABEL)])


# --- Ports ----------------------------------------------------------------------------------


class Clock(Protocol):
    def now(self) -> datetime: ...


class Prompter(Protocol):
    def ask(self, question: str) -> Optional[str]: ...

    def ask_secret(self, question: str) -> Optional[str]: ...


MetricsReader = Callable[[int, str], Optional[Tuple[int, int]]]


@dataclass
class AlertPorts:
    """Every external effect; tests pass fakes."""

    home: Path
    qa_home: Path
    repo_root: Path
    agents_dir: Path
    port: int
    docker: lc.DockerCli
    tailscale: qa.TailscaleCli
    probe: service.ServiceProbe
    metrics: MetricsReader
    public: Callable[[str], bool]
    telegram: TelegramTransport
    launchctl: Launchctl
    clock: Clock
    prompter: Prompter
    tty: bool
    out: Callable[[str], None]

    @property
    def plist(self) -> Path:
        return self.agents_dir / "{}.plist".format(LABEL)

    @property
    def script(self) -> Path:
        return self.repo_root / "backend" / "scripts" / "qa_alerts.py"

    @property
    def python(self) -> Path:
        return self.repo_root / "backend" / ".venv" / "bin" / "python"


def system_metrics(port: int, token: str) -> Optional[Tuple[int, int]]:
    """(``/ask`` responses, ``/ask`` 5xx responses) from loopback ``/metrics``; ``None`` when unreadable."""

    request = urllib.request.Request(
        "http://{}:{}/metrics".format(service.HOST, port),
        headers={"Authorization": "Bearer " + token},
        method="GET",
    )
    try:
        with loopback_opener().open(request, timeout=service.PROBE_TIMEOUT_SECONDS) as response:
            if response.getcode() != 200:
                return None
            text = response.read(MAX_REPLY_BYTES).decode("utf-8")
    except Exception:  # noqa: BLE001 - the token travels in a header only; say nothing about why
        return None
    return parse_ask_counters(text)


_SAMPLE = re.compile(r'^manijero_http_requests_total\{([^}]*)\}\s+([0-9]+(?:\.[0-9]+)?)\s*$')


def parse_ask_counters(text: str) -> Optional[Tuple[int, int]]:
    total = errors = 0
    seen = False
    for raw in text.splitlines():
        match = _SAMPLE.match(raw.strip())
        if match is None:
            continue
        labels = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1)))
        if labels.get("route") != "/ask":
            continue
        seen = True
        value = int(float(match.group(2)))
        total += value
        if labels.get("code", "").startswith("5"):
            errors += value
    return (total, errors) if seen else (0, 0) if "manijero_ready" in text else None


# --- Thresholds and error share -------------------------------------------------------------


@dataclass(frozen=True)
class ErrorThreshold:
    window_seconds: float
    problem_percent: float

    @property
    def minutes(self) -> int:
        return max(1, int(self.window_seconds // 60))


def load_threshold(path: Path = THRESHOLDS_FILE) -> Optional[ErrorThreshold]:
    """The dashboard's Problem level for errors, read from ``thresholds.json``; ``None`` if unusable."""

    try:
        errors = json.loads(Path(path).read_text(encoding="utf-8"))["errors"]
        match = WINDOW_PATTERN.fullmatch(str(errors["window"]))
        percent = float(errors["problem_percent"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if match is None or percent <= 0:
        return None
    seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600}[match.group(2)]
    return ErrorThreshold(float(seconds), percent) if seconds > 0 else None


Sample = List[float]  # [epoch seconds, /ask total, /ask 5xx]


def update_samples(samples: List[Sample], counters: Tuple[int, int], now: float, window: float) -> List[Sample]:
    """Add this check's counters; a counter that went down means QA restarted, so start over."""

    total, errors = counters
    if samples and (total < samples[-1][1] or errors < samples[-1][2]):
        samples = []
    kept = [s for s in samples if now - s[0] <= window + KEEP_EXTRA_SECONDS]
    return kept + [[now, float(total), float(errors)]]


def error_percent(samples: List[Sample], window: float) -> Optional[float]:
    """The 5xx share of ``/ask`` over the window, or ``None`` until a full window exists or with no ``/ask``."""

    if len(samples) < 2:
        return None
    latest = samples[-1]
    older = [s for s in samples[:-1] if latest[0] - s[0] >= window - WINDOW_SLACK_SECONDS]
    if not older:
        return None
    base = older[-1]
    asks = latest[1] - base[1]
    if asks <= 0:
        return None
    return (latest[2] - base[2]) * 100.0 / asks


# --- Looking at QA --------------------------------------------------------------------------


@dataclass
class Facts:
    docker_ready: bool = True
    container: str = "none"  # none | stopped | running
    health_ok: bool = False
    ready_ok: bool = False
    funnel_ours: bool = False
    counters: Optional[Tuple[int, int]] = None
    public_ok: Optional[bool] = None


def gather(ports: AlertPorts, public_url: Optional[str], token: Optional[str]) -> Facts:
    if lc.docker_state(ports.docker) != lc.DOCKER_READY:
        return Facts(docker_ready=False)
    found = lc.container_info(ports.docker, qa.CONTAINER_NAME)
    ours = found if qa.is_qa_container(found) else None
    facts = Facts(container="none" if ours is None else "running" if ours.running else "stopped")
    if facts.container == "stopped":
        return facts
    facts.health_ok = ports.probe.health(ports.port) == service.SERVICE_NAME
    if facts.health_ok:
        facts.ready_ok = ports.probe.ready(ports.port) == service.READY
        if token:
            facts.counters = ports.metrics(ports.port, token)
        if facts.ready_ok and public_url:
            facts.public_ok = ports.public(public_url)
    elif ours is None:
        shared = qa.read_tailscale(ports.tailscale, ports.port)
        facts.funnel_ours = shared.state == "running" and shared.funnel == "ours"
    return facts


def classify(facts: Facts, percent: Optional[float], threshold: Optional[ErrorThreshold]) -> Tuple[Optional[str], bool]:
    """(problem kind or ``None``, whether QA is stopped on purpose). Down beats not ready beats erroring."""

    if not facts.docker_ready:
        return "down_docker", False
    if facts.container == "stopped":
        return "down", False
    if not facts.health_ok:
        if facts.container == "none" and not facts.funnel_ours:
            return None, True
        return "down", False
    if not facts.ready_ok:
        return "not_ready", False
    if percent is not None and threshold is not None and percent >= threshold.problem_percent:
        return "erroring", False
    if facts.public_ok is False:
        return "unreachable", False
    return None, False


def problem_text(kind: str, percent: int, minutes: int) -> Tuple[str, str]:
    sentence, step, _ = KINDS[kind]
    return sentence.format(percent=percent, minutes=minutes), step


# --- State and alerting ---------------------------------------------------------------------


@dataclass
class State:
    samples: List[Sample] = field(default_factory=list)
    cand_kind: Optional[str] = None
    cand_count: int = 0
    cand_since: Optional[str] = None
    ok_streak: int = 0
    ok_since: Optional[str] = None
    incident: Optional[Dict[str, Any]] = None  # kind, since, alerted_kind, sent_any
    last_sent: Dict[str, str] = field(default_factory=dict)
    last_check: Optional[Dict[str, Any]] = None  # at, outcome, send_failed


def _valid_state(document: Any) -> State:
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("state")
    samples = [[float(a), float(b), float(c)] for a, b, c in document["samples"]]
    kind = document["cand_kind"]
    if kind is not None and kind not in KINDS:
        raise ValueError("kind")
    incident = document["incident"]
    if incident is not None:
        if incident["kind"] not in KINDS or parse_stamp(incident["since"]) is None:
            raise ValueError("incident")
        if incident["alerted_kind"] is not None and incident["alerted_kind"] not in KINDS:
            raise ValueError("incident")
        incident = {
            "kind": incident["kind"], "since": incident["since"],
            "alerted_kind": incident["alerted_kind"], "sent_any": bool(incident["sent_any"]),
        }
    last_sent = {k: v for k, v in document["last_sent"].items() if k in KINDS and parse_stamp(v) is not None}
    last_check = document["last_check"]
    if last_check is not None:
        if parse_stamp(last_check["at"]) is None or not isinstance(last_check["outcome"], str):
            raise ValueError("last_check")
        last_check = {
            "at": last_check["at"], "outcome": last_check["outcome"][:40],
            "send_failed": bool(last_check.get("send_failed")),
        }
    return State(
        samples=samples, cand_kind=kind, cand_count=int(document["cand_count"]),
        cand_since=document["cand_since"], ok_streak=int(document["ok_streak"]),
        ok_since=document["ok_since"], incident=incident, last_sent=last_sent, last_check=last_check,
    )


def load_state(home: Path) -> State:
    """The saved state; a missing or damaged file starts fresh."""

    try:
        return _valid_state(json.loads(state_path(home).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return State()


def save_state(home: Path, state: State) -> None:
    document = dict(state.__dict__)
    document["version"] = 1
    _write_private(state_path(home), json.dumps(document, sort_keys=True) + "\n")


def advance(
    state: State,
    kind: Optional[str],
    percent: int,
    minutes: int,
    now: datetime,
    send: Callable[[str], bool],
) -> None:
    """One check's effect on the alert state; ``send`` returns whether Telegram accepted the text."""

    moment = stamp(now)
    if kind is None:
        state.cand_kind, state.cand_count, state.cand_since = None, 0, None
        state.ok_streak += 1
        if state.ok_streak == 1:
            state.ok_since = moment
        incident = state.incident
        if incident is not None and state.ok_streak >= CONFIRM_CHECKS:
            if incident["sent_any"]:
                text = RECOVERY_MESSAGE.format(
                    start=local_time(incident["since"]), end=local_time(state.ok_since)
                )
                if not send(text):
                    return
            state.incident = None
        return
    state.ok_streak, state.ok_since = 0, None
    if state.cand_kind == kind:
        state.cand_count += 1
    else:
        state.cand_kind, state.cand_count, state.cand_since = kind, 1, moment
    if state.cand_count < CONFIRM_CHECKS:
        return
    incident = state.incident
    if incident is None:
        incident = state.incident = {
            "kind": kind, "since": state.cand_since or moment, "alerted_kind": None, "sent_any": False,
        }
    elif incident["kind"] != kind:
        incident["kind"], incident["alerted_kind"] = kind, None
    text, step = problem_text(kind, percent, minutes)
    last = parse_stamp(state.last_sent.get(kind))
    if incident["alerted_kind"] != kind:
        if last is not None and now - last < SAME_KIND_CAP:
            incident["alerted_kind"] = kind  # the same kind was sent within the hour: stay quiet
            return
        message = PROBLEM_MESSAGE.format(text=text, step=step)
    elif last is not None and now - last >= REMINDER:
        message = REMINDER_MESSAGE.format(since=local_time(incident["since"]), text=text, step=step)
    else:
        return
    if send(message):
        incident["alerted_kind"], incident["sent_any"] = kind, True
        state.last_sent[kind] = moment


# --- check (run by launchd) -----------------------------------------------------------------


def _qa_inputs(ports: AlertPorts) -> Tuple[Optional[str], Optional[str]]:
    """(real public address, QA token) when each is usable; the token is never printed."""

    url: Optional[str] = None
    try:
        settings = profiles.read_profile_settings(profiles.QA, ports.qa_home)
        if settings.public_url and not settings.placeholder_url:
            url = settings.public_url
    except profiles.ProfileSettingsError:
        pass
    paths = profiles.credential_paths(ports.qa_home, profiles.QA_CLIENT_ID)
    token = profiles.read_token(paths.token) if profiles.check_credentials(paths, profiles.QA_CLIENT_ID) is None else None
    return url, token


def run_check(ports: AlertPorts, threshold_file: Optional[Path] = None) -> int:
    now = ports.clock.now()
    if bootstrap.lock_is_held(ports.qa_home / qa.LOCK_NAME):
        append_log(ports.home, "{} outcome=skipped reason=qa_command_running".format(stamp(now)))
        return 0
    credentials, _ = load_credentials(ports.home)
    url, token = _qa_inputs(ports)
    facts = gather(ports, url, token)
    state = load_state(ports.home)
    threshold = load_threshold(threshold_file or THRESHOLDS_FILE)
    percent: Optional[float] = None
    if threshold is not None and facts.counters is not None:
        state.samples = update_samples(state.samples, facts.counters, now.timestamp(), threshold.window_seconds)
        percent = error_percent(state.samples, threshold.window_seconds)
    kind, stopped = classify(facts, percent, threshold)
    failed: List[str] = []

    def send(text: str) -> bool:
        if credentials is None:
            failed.append("not_set_up")
            return False
        code = send_text(ports.telegram, credentials, text)
        if code is not None:
            failed.append(code)
        return code is None

    shown = min(100, int((percent or 0.0) + 0.5))
    advance(state, kind, shown, threshold.minutes if threshold else 15, now, send)
    outcome = kind or ("stopped" if stopped else "ok")
    state.last_check = {"at": stamp(now), "outcome": outcome, "send_failed": bool(failed)}
    save_state(ports.home, state)
    append_log(
        ports.home,
        "{} outcome={} send={}".format(stamp(now), outcome, "failed:" + failed[0] if failed else "ok_or_none"),
    )
    return 0


# --- Owner commands -------------------------------------------------------------------------


def _line(ok: bool, label: str, text: str) -> str:
    return "{:<8} {}: {}".format(bootstrap.OK if ok else bootstrap.PROBLEM, label, text)


def _stop_with(ports: AlertPorts, result: str, sentence: str, fix: str) -> int:
    ports.out(sentence)
    ports.out("{} {}".format(result, fix))
    return 1


NOT_SET_UP = "Result: Telegram alerts were not set up."
NOT_SENT = "Result: the test alert was not sent."
NOT_ON = "Result: QA alerts were not turned on."


def run_setup(ports: AlertPorts) -> int:
    out = ports.out
    if not ports.tty:
        return _stop_with(ports, NOT_SET_UP, "There is no Terminal window to type in.", FIX_NO_TTY)
    if credentials_path(ports.home).exists():
        answer = ports.prompter.ask("Telegram details are already stored. Type yes to replace them: ")
        if answer is None or answer.strip().lower() != "yes":
            out("Result: the stored Telegram details were kept.")
            return 0
    out("Paste the bot token from BotFather. Nothing is shown while you paste. Then press Enter.")
    token = (ports.prompter.ask_secret("Bot token: ") or "").strip()
    if not TOKEN_PATTERN.fullmatch(token):
        return _stop_with(
            ports, NOT_SET_UP,
            "That does not look like a bot token.",
            "Copy it again from BotFather (it looks like 123456:ABC-DEF...), then run {} again.".format(SETUP_COMMAND),
        )
    code = check_token(ports.telegram, token)
    if code is not None:
        sentence, fix = TELEGRAM_WORDS[code]
        return _stop_with(ports, NOT_SET_UP, sentence, fix)
    chat_id: Optional[int] = None
    for attempt in range(SETUP_TRIES):
        if ports.prompter.ask("Now open your bot in Telegram, send it any message, then press Enter here: ") is None:
            break
        chat_id, code = latest_private_chat(ports.telegram, token)
        if chat_id is not None:
            break
        if code in TELEGRAM_WORDS:
            sentence, fix = TELEGRAM_WORDS[code]
            return _stop_with(ports, NOT_SET_UP, sentence, fix)
        out("No message to your bot was found yet.")
    if chat_id is None:
        return _stop_with(
            ports, NOT_SET_UP,
            "No private message to your bot was found.",
            "Open your bot in Telegram, send it any message, then run {} again.".format(SETUP_COMMAND),
        )
    write_credentials(ports.home, Credentials(token, chat_id))
    out("Result: Telegram alerts are set up. Send a test with {}.".format(TEST_COMMAND))
    return 0


def run_test(ports: AlertPorts) -> int:
    credentials, problem = load_credentials(ports.home)
    if credentials is None:
        sentence, fix = CREDENTIAL_WORDS[problem or "unsafe"]
        return _stop_with(ports, NOT_SENT, sentence, fix)
    code = send_text(ports.telegram, credentials, TEST_MESSAGE)
    if code is not None:
        sentence, fix = TELEGRAM_WORDS[code]
        return _stop_with(ports, NOT_SENT, sentence, fix)
    ports.out("Result: a test alert was sent. Check Telegram on your phone.")
    return 0


def _prerequisites(ports: AlertPorts) -> List[Tuple[str, str]]:
    problems: List[Tuple[str, str]] = []
    credentials, problem = load_credentials(ports.home)
    if credentials is None:
        sentence, fix = CREDENTIAL_WORDS[problem or "unsafe"]
        problems.append((sentence, fix))
    try:
        settings = profiles.read_profile_settings(profiles.QA, ports.qa_home)
    except profiles.ProfileSettingsError as error:
        if error.code == "settings_missing":
            problems.append(("QA is not prepared on this computer: the QA settings file does not exist.", qa.FIX_QA_SETUP))
        else:
            problems.append((error.sentence, "Fix the QA settings file as described above, then run this command again."))
    else:
        if not settings.public_url or settings.placeholder_url:
            problems.append((
                "QA has no real internet address yet.",
                "Run {}, then run this command again.".format(qa.DEPLOY_COMMAND),
            ))
    paths = profiles.credential_paths(ports.qa_home, profiles.QA_CLIENT_ID)
    if profiles.check_credentials(paths, profiles.QA_CLIENT_ID) is not None:
        problems.append(("The QA access keys are missing or incomplete.", qa.FIX_QA_SETUP))
    if not os.access(ports.python, os.X_OK):
        problems.append((
            "The backend tools are not set up yet.",
            "Run ./scripts/init.sh --local-rag-setup, then run this command again.",
        ))
    if not ports.launchctl.present():
        problems.append(("The macOS launchctl tool was not found; QA alerts need macOS.", "Run this command on the Mac."))
    return problems


def plist_bytes(ports: AlertPorts) -> bytes:
    """The launchd job: no secret and no ``MANIJERO_*`` value."""

    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [str(ports.python), str(ports.script), "check"],
            "StartInterval": INTERVAL_SECONDS,
            "RunAtLoad": True,
            "WorkingDirectory": str(ports.repo_root / "backend"),
            "EnvironmentVariables": {"PATH": LAUNCHD_PATH},
            "StandardOutPath": str(ports.home / "logs" / LAUNCHD_LOG_NAME),
            "StandardErrorPath": str(ports.home / "logs" / LAUNCHD_LOG_NAME),
        }
    )


def _write_plist(ports: AlertPorts, content: bytes) -> None:
    directory = ports.plist.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(directory), prefix=".{}-".format(LABEL))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, ports.plist)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def run_start(ports: AlertPorts) -> int:
    problems = _prerequisites(ports)
    if problems:
        for sentence, _ in problems:
            ports.out(sentence)
        ports.out("{} {}".format(NOT_ON, problems[0][1]))
        return 1
    content = plist_bytes(ports)
    loaded = ports.launchctl.is_loaded()
    try:
        same = ports.plist.read_bytes() == content
    except OSError:
        same = False
    if same and loaded:
        ports.out("Result: QA alerts are already on; nothing was changed.")
        return 0
    _private_dir(ports.home / "logs")
    _write_plist(ports, content)
    if loaded and not ports.launchctl.bootout():
        return _stop_with(
            ports, "Result: QA alerts could not be turned on.",
            "macOS did not let the earlier alert job be replaced.",
            "Run {}, then {}.".format(STOP_COMMAND, START_COMMAND),
        )
    if not ports.launchctl.bootstrap(ports.plist):
        return _stop_with(
            ports, "Result: QA alerts could not be turned on.",
            "macOS did not start the alert job.",
            "Run {}, then {} again.".format(STOP_COMMAND, START_COMMAND),
        )
    ports.out("Result: QA alerts are on. The check runs every 5 minutes while this Mac is awake.")
    return 0


def run_stop(ports: AlertPorts) -> int:
    loaded = ports.launchctl.is_loaded()
    exists = ports.plist.exists()
    if not loaded and not exists:
        ports.out("Result: QA alerts were not on, so there was nothing to stop.")
        return 0
    if loaded and not ports.launchctl.bootout():
        return _stop_with(
            ports, "Result: QA alerts could not be turned off.",
            "macOS did not stop the alert job.",
            "Quit and reopen Terminal, then run {} again.".format(STOP_COMMAND),
        )
    try:
        ports.plist.unlink()
    except FileNotFoundError:
        pass
    ports.out("Result: QA alerts are off.")
    return 0


def run_status(ports: AlertPorts) -> int:
    out = ports.out
    loaded = ports.launchctl.is_loaded()
    exists = ports.plist.exists()
    if not loaded and not exists:
        out(_line(False, "Alert job", "off."))
        out("Result: QA alerts are off. Turn them on with {}.".format(START_COMMAND))
        return 1
    checks: List[Tuple[bool, str, str]] = []  # ok, line, fix
    again = "Run {}, then {}.".format(STOP_COMMAND, START_COMMAND)
    try:
        current = ports.plist.read_bytes() == plist_bytes(ports)
    except OSError:
        current = False
    if loaded and exists and current:
        checks.append((True, _line(True, "Alert job", "on, every 5 minutes while this Mac is awake."), ""))
    elif loaded and exists:
        checks.append((False, _line(False, "Alert job", "on, but for a different folder or older settings."), "Run {} again.".format(START_COMMAND)))
    elif exists:
        checks.append((False, _line(False, "Alert job", "its file exists but macOS is not running it."), "Run {} again.".format(START_COMMAND)))
    else:
        checks.append((False, _line(False, "Alert job", "running but its file is missing."), again))
    credentials, _ = load_credentials(ports.home)
    checks.append((
        credentials is not None,
        _line(credentials is not None, "Telegram", "set up." if credentials is not None else "not set up."),
        "Run {}.".format(SETUP_COMMAND),
    ))
    state = load_state(ports.home)
    last = state.last_check
    moment = parse_stamp(last["at"]) if last else None
    if last is None or moment is None:
        checks.append((
            False,
            _line(False, "Last check", "none yet. If it stays so for a few minutes, macOS may be blocking background items."),
            "Wait a few minutes, then run {} again.".format(STATUS_COMMAND),
        ))
    elif ports.clock.now() - moment > STALE_CHECK:
        checks.append((
            False,
            _line(False, "Last check", "at {} (this Mac's time), more than 15 minutes ago; the Mac may have been asleep.".format(local_time(last["at"]))),
            "Wait for the next check while this Mac is awake, then run {} again.".format(STATUS_COMMAND),
        ))
    else:
        outcome = last["outcome"]
        if outcome in KINDS:
            checks.append((False, _line(False, "Last check", "at {}, found: {}.".format(local_time(last["at"]), KINDS[outcome][2])), KINDS[outcome][1]))
        elif outcome == "not_set_up":
            checks.append((False, _line(False, "Last check", "at {}, Telegram was not set up.".format(local_time(last["at"]))), "Run {}.".format(SETUP_COMMAND)))
        else:
            what = "QA is stopped on purpose, which is not a problem" if outcome == "stopped" else "no problem found"
            sent = "; an alert could not be sent and will be tried again" if last.get("send_failed") else ""
            checks.append((not sent, _line(not sent, "Last check", "at {}, {}{}.".format(local_time(last["at"]), what, sent)), "Run {} to see if Telegram works.".format(TEST_COMMAND)))
    incident = state.incident
    if incident is None:
        checks.append((True, _line(True, "Open problems", "none."), ""))
    else:
        kind = incident["kind"]
        sent = "alert sent" if incident["alerted_kind"] == kind else "alert not sent"
        checks.append((
            False,
            _line(False, "Open problems", "{} since {}; {}.".format(KINDS[kind][2], local_time(incident["since"]), sent)),
            KINDS[kind][1],
        ))
    for _, line, _ in checks:
        out(line)
    for ok, _, fix in checks:
        if not ok:
            out("Result: QA alerts need attention: {}".format(fix))
            return 1
    out("Result: QA alerts are on and the last check found no problem.")
    return 0


def run_operation(operation: str, ports: AlertPorts) -> int:
    runners = {
        "setup": run_setup, "start": run_start, "stop": run_stop,
        "status": run_status, "test": run_test, "check": run_check,
    }
    return runners[operation](ports)
