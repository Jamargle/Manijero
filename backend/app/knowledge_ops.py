"""One scheduled, budgeted, retryable run of the whole knowledge update cycle.

The cycle is discover, classify, ingest, analyze impact, check validity, prepare review. Each step
calls an accepted entry point unchanged, inside its own child process, so one hour is a hard stop
even for a step that hangs. A step may be tried 3 times (2 retries, waiting 60 s then 300 s, never
longer than the time left); a step that still fails is reported with a fixed code, one plain
sentence, and the first thing to do. The run always ends at "ready for review": it writes a short
plain-language summary and a ledger line the health dashboard reads, and it never touches the
approved knowledge or any release. Owner commands live in ``backend/scripts/knowledge_ops.py``.

Only counts, fixed codes, candidate ids, and times reach the summary, the ledger, and the metrics:
never a title, a URL, document text, or exception text. Tracebacks go only to the private log.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import plistlib
import re
import secrets
import signal
import subprocess
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
from zoneinfo import ZoneInfo

from app.source_update_scheduler import BACKOFF_SECONDS

ON_COMMAND = "./scripts/init.sh --knowledge-updates-on"
OFF_COMMAND = "./scripts/init.sh --knowledge-updates-off"
RUN_COMMAND = "./scripts/init.sh --knowledge-updates-run"
STATUS_COMMAND = "./scripts/init.sh --knowledge-updates-status"
SETUP_COMMAND = "./scripts/init.sh --local-rag-setup"

HOME_ENV = "MANIJERO_KNOWLEDGE_OPS_HOME"  # tests only
STATE_DIR_ENV = "MANIJERO_KNOWLEDGE_OPS_STATE_DIR"  # read by the health metrics
STEP_CLI_ENV = "MANIJERO_KNOWLEDGE_OPS_STEP_CLI"  # tests only: replaces the child step program
LABEL = "org.manijero.knowledge-ops"
SCHEDULE_HOUR, SCHEDULE_MINUTE = 10, 20

BUDGET = timedelta(hours=1)
MAX_ATTEMPTS = 3
BACKOFF = BACKOFF_SECONDS
KILL_GRACE_SECONDS = 10
MISSED_AFTER = timedelta(hours=30)
INTERRUPTED_AFTER = timedelta(hours=2)
MADRID = ZoneInfo("Europe/Madrid")

LEDGER_SCHEMA = "knowledge-ops-ledger-v1"
STEP_SCHEMA = "knowledge-ops-step-v1"
REVIEW_SCHEMA = "knowledge-ops-review-ready-v1"
LEDGER_NAME = "knowledge-ops-ledger.jsonl"
LOCK_NAME = "knowledge-ops.lock"
SUMMARY_NAME = "summary.txt"
LATEST_SUMMARY_NAME = "latest-summary.txt"
LOG_NAME = "knowledge-ops.log"
LAUNCHD_LOG_NAME = "launchd.log"
MAX_LEDGER_BYTES = 10 * 1024 * 1024
RUN_ID_PATTERN = re.compile(r"^run-\d{8}T\d{6}Z-[a-f0-9]{8}$")

STEPS = ("discover", "classify", "ingest", "impact", "validity", "review")
LABELS = {
    "discover": "Look for new official documents",
    "classify": "Sort them by relevance",
    "ingest": "Download and read the documents",
    "impact": "Compare them with approved sources",
    "validity": "Check which sources are still valid",
    "review": "Prepare your review",
}
# A step runs only when every step it needs produced its output.
NEEDS = {
    "discover": (),
    "classify": ("discover",),
    "ingest": ("discover",),
    "impact": ("ingest",),
    "validity": ("impact",),
    "review": ("impact", "validity"),
}
OUTCOMES = ("review_ready", "failed", "stopped_at_time_limit")
TRIGGERS = ("manual", "schedule")
COUNT_KEYS = (
    "new_candidates", "pages_changed", "relevant", "unsure", "not_relevant",
    "documents_ingested", "documents_failed", "impact_findings", "validity_proposals",
)

# Fixed failure codes: (what happened, first thing to do, retried?). Nothing else ever reaches the owner.
CODES: Dict[str, Tuple[str, str, bool]] = {
    "sources_unreachable": (
        "An official source did not answer.",
        "check the internet connection, then run {} again.".format(RUN_COMMAND), True),
    "pages_unreachable": (
        "An official page could not be checked.",
        "check the internet connection and run {} again; if it keeps happening, tell a developer "
        "because the page address may have changed.".format(RUN_COMMAND), True),
    "model_not_running": (
        "The local drafting program (Ollama) is not running.",
        "open Ollama, then run {} again.".format(RUN_COMMAND), True),
    "step_crashed": (
        "The step stopped unexpectedly.",
        "run {} again; if it happens again, tell a developer.".format(RUN_COMMAND), True),
    "config_invalid": (
        "A setting or a saved file is not valid.",
        "tell a developer; the details are in the log.", False),
    "knowledge_files_invalid": (
        "The approved sources or the downloaded documents could not be read.",
        "tell a developer; the details are in the log.", False),
}
NOT_RUN_REASONS = {
    "earlier_step_failed": "an earlier step failed",
    "time_limit": "the one-hour limit was reached",
}
OUTCOME_WORDS = {
    "review_ready": "ready for your review",
    "failed": "something failed",
    "stopped_at_time_limit": "stopped at the one-hour limit",
    "interrupted": "interrupted before it finished",
}
FIXED_LINE = "Nothing was published. You approve every change before it goes live."
NOT_SET_UP = "Knowledge updates are not set up yet."


class OpsError(Exception):
    """A fixed, value-safe code; never carries a path, title, or document text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class StepFailure(Exception):
    """Raised by a step adapter: a fixed code, whether the step is worth retrying, and its counts."""

    def __init__(self, code: str, *, usable: bool = False, counts: Optional[Mapping[str, int]] = None) -> None:
        super().__init__(code)
        self.code = code if code in CODES else "step_crashed"
        self.usable = usable
        self.counts = dict(counts or {})

    @property
    def retryable(self) -> bool:
        return CODES[self.code][2]


class Problem(Exception):
    """A missing prerequisite: one sentence and the one command that fixes it."""

    def __init__(self, sentence: str, fix: str) -> None:
        super().__init__(sentence)
        self.sentence = sentence
        self.fix = fix


class AlreadyRunning(Exception):
    """Another run holds the lock."""


# --- Ports ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunnerResult:
    timed_out: bool


class StepRunner(Protocol):
    def run(self, step: str, run_dir: Path, timeout_seconds: float) -> RunnerResult: ...


class Launchctl(Protocol):
    def present(self) -> bool: ...

    def is_loaded(self) -> bool: ...

    def bootstrap(self, plist: Path) -> bool: ...

    def bootout(self) -> bool: ...


@dataclass
class Ports:
    """Every external effect; tests pass fakes."""

    home: Path
    repo_root: Path
    agents_dir: Path
    python: Path
    clock: Callable[[], datetime]
    sleep: Callable[[float], None]
    runner: StepRunner
    launchctl: Launchctl
    launchd_path: str = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    out: Callable[[str], None] = print

    @property
    def plist(self) -> Path:
        return self.agents_dir / "{}.plist".format(LABEL)

    @property
    def script(self) -> Path:
        return self.repo_root / "backend" / "scripts" / "knowledge_ops.py"


def knowledge_ops_home(environ: Mapping[str, str]) -> Path:
    raw = (environ.get(HOME_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    home = (environ.get("HOME") or "").strip()
    return (Path(home) if home else Path.home()) / "manijero" / "knowledge-ops"


class SubprocessRunner:
    """Runs one step as a child process; terminates it, then kills it, when the time is up."""

    def __init__(self, argv_prefix: Sequence[str], log_path: Path) -> None:
        self._prefix = list(argv_prefix)
        self._log = log_path

    def run(self, step: str, run_dir: Path, timeout_seconds: float) -> RunnerResult:
        _private_dir(self._log.parent)
        descriptor = os.open(str(self._log), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed program, fixed arguments
                [*self._prefix, "step", step, "--run-dir", str(run_dir)],
                stdin=subprocess.DEVNULL, stdout=descriptor, stderr=descriptor, start_new_session=True,
            )
        except OSError:
            return RunnerResult(timed_out=False)
        finally:
            os.close(descriptor)
        try:
            process.wait(timeout=max(timeout_seconds, 0.01))
            return RunnerResult(timed_out=False)
        except subprocess.TimeoutExpired:
            self._signal(process, signal.SIGTERM)
            try:
                process.wait(timeout=KILL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                self._signal(process, signal.SIGKILL)
                process.wait()
            return RunnerResult(timed_out=True)

    @staticmethod
    def _signal(process: "subprocess.Popen[bytes]", number: int) -> None:
        try:
            os.killpg(process.pid, number)
        except (OSError, ProcessLookupError):
            try:
                process.send_signal(number)
            except OSError:
                pass


# --- Files ----------------------------------------------------------------------------------


def _private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(str(path), 0o700)


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".{}-".format(path.name))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def log_path(home: Path) -> Path:
    return Path(home) / "logs" / LOG_NAME


def append_log(home: Path, message: str) -> None:
    """The only place a traceback may go: the private log, never the output."""

    try:
        _private_dir(Path(home) / "logs")
        descriptor = os.open(str(log_path(home)), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, (message.rstrip() + "\n").encode("utf-8", "replace"))
        finally:
            os.close(descriptor)
    except OSError:
        pass


class _Lock:
    def __init__(self, home: Path) -> None:
        self._path = home / LOCK_NAME
        self._fd: Optional[int] = None

    def __enter__(self) -> "_Lock":
        descriptor = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(descriptor)
            if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                raise AlreadyRunning() from None
            raise
        self._fd = descriptor
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


# --- Ledger ---------------------------------------------------------------------------------


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise OpsError("ledger_invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise OpsError("ledger_invalid") from None
    if parsed.tzinfo is None:
        raise OpsError("ledger_invalid")
    return parsed


def _validate_record(record: Any) -> Dict[str, Any]:
    if (not isinstance(record, dict) or record.get("schema_version") != LEDGER_SCHEMA
            or record.get("event") not in ("run_started", "run_finished")
            or not isinstance(record.get("run_id"), str) or not RUN_ID_PATTERN.fullmatch(record["run_id"])
            or record.get("trigger") not in TRIGGERS):
        raise OpsError("ledger_invalid")
    _parse_time(record.get("started_at"))
    if record["event"] == "run_finished":
        _parse_time(record.get("finished_at"))
        steps = record.get("steps")
        if record.get("outcome") not in OUTCOMES or not isinstance(steps, list) or not all(
                isinstance(item, dict) and item.get("step") in STEPS for item in steps):
            raise OpsError("ledger_invalid")
    return record


def read_ledger(home: Path) -> List[Dict[str, Any]]:
    path = Path(home) / LEDGER_NAME
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return []
    except OSError:
        raise OpsError("ledger_unreadable") from None
    if size > MAX_LEDGER_BYTES:
        raise OpsError("ledger_too_large")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        raise OpsError("ledger_unreadable") from None
    records = []
    for line in lines:
        try:
            records.append(_validate_record(json.loads(line)))
        except json.JSONDecodeError:
            raise OpsError("ledger_invalid") from None
    return records


def _append_ledger(home: Path, record: Mapping[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    descriptor = os.open(str(Path(home) / LEDGER_NAME), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, line.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# --- Step results ---------------------------------------------------------------------------


@dataclass
class StepReport:
    step: str
    status: str  # done | failed | not_run | stopped_at_time_limit
    attempts: int = 0
    code: Optional[str] = None
    reason: Optional[str] = None  # not_run only
    usable: bool = False
    counts: Dict[str, int] = field(default_factory=dict)
    waits: List[int] = field(default_factory=list)

    @property
    def produced(self) -> bool:
        """Whether later steps may use this step's output."""

        return self.status == "done" or (self.status == "failed" and self.usable)

    def as_json(self, run_dir: Path) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "schema_version": STEP_SCHEMA, "step": self.step, "status": self.status,
            "attempts": self.attempts, "counts": self.counts, "waits_seconds": self.waits,
        }
        if self.code:
            sentence, fix, _ = CODES[self.code]
            record.update({"code": self.code, "what_happened": sentence, "first_thing_to_do": fix,
                           "log": str(log_path(run_dir.parent.parent))})
        if self.reason:
            record["reason"] = self.reason
        return record


def step_file(run_dir: Path, step: str) -> Path:
    return Path(run_dir) / "steps" / "{}.json".format(step)


def write_child_result(run_dir: Path, step: str, *, failure: Optional[StepFailure] = None,
                       counts: Optional[Mapping[str, int]] = None) -> None:
    record: Dict[str, Any] = {"schema_version": STEP_SCHEMA, "step": step}
    if failure is None:
        record.update({"status": "ok", "counts": dict(counts or {})})
    else:
        record.update({"status": "failed", "code": failure.code, "retryable": failure.retryable,
                       "usable": failure.usable, "counts": failure.counts})
    _write_private(step_file(run_dir, step), _json_text(record))


def _clean_counts(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {key: int(item) for key, item in value.items()
            if key in COUNT_KEYS and isinstance(item, int) and not isinstance(item, bool) and item >= 0}


def read_child_result(run_dir: Path, step: str) -> Dict[str, Any]:
    """What the child wrote, or a crash when it wrote nothing usable."""

    crashed = {"status": "failed", "code": "step_crashed", "retryable": True, "usable": False, "counts": {}}
    try:
        record = json.loads(step_file(run_dir, step).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return crashed
    if not isinstance(record, dict) or record.get("step") != step or record.get("status") not in ("ok", "failed"):
        return crashed
    counts = _clean_counts(record.get("counts"))
    if record["status"] == "ok":
        return {"status": "ok", "counts": counts}
    code = record.get("code") if record.get("code") in CODES else "step_crashed"
    return {"status": "failed", "code": code, "retryable": CODES[code][2],
            "usable": record.get("usable") is True, "counts": counts}


# --- The run --------------------------------------------------------------------------------


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    outcome: str
    summary: str
    steps: Dict[str, StepReport]

    @property
    def exit_code(self) -> int:
        return 0 if self.outcome == "review_ready" else 1


def _utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc)


def new_run_id(started: datetime) -> str:
    return "run-{}-{}".format(_utc(started).strftime("%Y%m%dT%H%M%SZ"), secrets.token_hex(4))


def run_prerequisites(ports: Ports) -> None:
    home = ports.home
    if not (home.is_dir() and (home / "source-monitor.json").is_file() and (home / "page-monitor.json").is_file()):
        raise Problem(NOT_SET_UP, ON_COMMAND)
    if not os.access(str(ports.python), os.X_OK):
        raise Problem("The backend tools are not set up yet.", SETUP_COMMAND)


def run_cycle(ports: Ports, trigger: str) -> RunResult:
    """Run every step once in order (with retries) inside one hour; raises ``Problem``/``AlreadyRunning``."""

    if trigger not in TRIGGERS:
        raise OpsError("trigger_invalid")
    run_prerequisites(ports)
    with _Lock(ports.home):
        started = _utc(ports.clock())
        deadline = started + BUDGET
        run_id = new_run_id(started)
        run_dir = ports.home / "runs" / run_id
        for sub in ("", "steps", "reports"):
            _private_dir(run_dir / sub if sub else run_dir)
        _write_private(run_dir / "run.json", _json_text(
            {"run_id": run_id, "as_of": started.astimezone(MADRID).date().isoformat(),
             "started_at": started.isoformat()}))
        base = {"schema_version": LEDGER_SCHEMA, "run_id": run_id, "trigger": trigger,
                "started_at": started.isoformat()}
        _append_ledger(ports.home, {**base, "event": "run_started"})

        reports: Dict[str, StepReport] = {}
        stopped = False
        for name in STEPS:
            if stopped or ports.clock() >= deadline:
                stopped = True
                report = StepReport(name, "not_run", reason="time_limit")
            elif any(not reports[need].produced for need in NEEDS[name]):
                report = StepReport(name, "not_run", reason="earlier_step_failed")
            else:
                report = _run_step(ports, name, run_dir, deadline)
                stopped = report.status == "stopped_at_time_limit"
            reports[name] = report
            _write_private(step_file(run_dir, name), _json_text(report.as_json(run_dir)))

        finished = _utc(ports.clock())
        outcome = _outcome(reports)
        summary = render_summary(started, finished, outcome, reports, run_dir)
        _write_private(run_dir / SUMMARY_NAME, summary)
        _write_private(ports.home / LATEST_SUMMARY_NAME, summary)
        _append_ledger(ports.home, {
            **base, "event": "run_finished", "finished_at": finished.isoformat(), "outcome": outcome,
            "steps": [{"step": name, "status": reports[name].status, "attempts": reports[name].attempts,
                       "code": reports[name].code or reports[name].reason} for name in STEPS],
        })
    return RunResult(run_id, run_dir, outcome, summary, reports)


def _outcome(reports: Mapping[str, StepReport]) -> str:
    statuses = [report.status for report in reports.values()]
    if "stopped_at_time_limit" in statuses or (
            "not_run" in statuses and any(r.reason == "time_limit" for r in reports.values())):
        return "stopped_at_time_limit"
    return "review_ready" if all(status == "done" for status in statuses) else "failed"


def _seconds_left(ports: Ports, deadline: datetime) -> float:
    return (deadline - _utc(ports.clock())).total_seconds()


def _run_step(ports: Ports, name: str, run_dir: Path, deadline: datetime) -> StepReport:
    report = StepReport(name, "failed")
    while True:
        left = _seconds_left(ports, deadline)
        if left <= 0:
            report.status = "stopped_at_time_limit"
            return report
        report.attempts += 1
        try:
            step_file(run_dir, name).unlink()
        except FileNotFoundError:
            pass
        result = ports.runner.run(name, run_dir, left)
        if result.timed_out or _seconds_left(ports, deadline) <= 0 and not step_file(run_dir, name).exists():
            report.status = "stopped_at_time_limit"
            return report
        answer = read_child_result(run_dir, name)
        report.counts = answer["counts"]
        if answer["status"] == "ok":
            report.status, report.code, report.usable = "done", None, False
            return report
        report.code, report.usable = answer["code"], answer["usable"]
        if not answer["retryable"] or report.attempts >= MAX_ATTEMPTS:
            report.status = "failed"
            return report
        wait = min(BACKOFF[report.attempts - 1], max(_seconds_left(ports, deadline), 0))
        if wait <= 0:
            report.status = "stopped_at_time_limit"
            return report
        report.waits.append(int(wait))
        ports.sleep(wait)


# --- Summary --------------------------------------------------------------------------------


def _local(moment: datetime) -> str:
    return moment.astimezone(MADRID).strftime("%Y-%m-%d %H:%M")


def _took(started: datetime, finished: datetime) -> str:
    minutes = round((finished - started).total_seconds() / 60)
    return "less than a minute" if minutes < 1 else "{} min".format(minutes)


def _count_line(reports: Mapping[str, StepReport]) -> str:
    totals: Dict[str, int] = {}
    for name in STEPS:
        totals.update(reports[name].counts)
    parts = []
    if "new_candidates" in totals:
        parts.append("{} new candidates".format(totals["new_candidates"]))
    if "relevant" in totals:
        parts.append("{} relevant, {} unsure, {} not relevant".format(
            totals["relevant"], totals.get("unsure", 0), totals.get("not_relevant", 0)))
    if "documents_ingested" in totals:
        parts.append("{} documents read, {} failed".format(totals["documents_ingested"], totals.get("documents_failed", 0)))
    if "impact_findings" in totals:
        parts.append("{} impact findings".format(totals["impact_findings"]))
    if "validity_proposals" in totals:
        parts.append("{} validity proposals".format(totals["validity_proposals"]))
    return "Counts: " + ("; ".join(parts) if parts else "none yet") + "."


def render_summary(started: datetime, finished: datetime, outcome: str,
                   reports: Mapping[str, StepReport], run_dir: Path) -> str:
    lines = [
        "Knowledge update run on {} (took {}).".format(_local(started), _took(started, finished)),
        "How it went: {}.".format(OUTCOME_WORDS[outcome]),
    ]
    failed_log = False
    for name in STEPS:
        report, label = reports[name], LABELS[name]
        if report.status == "done":
            lines.append("{}: done.".format(label))
        elif report.status == "not_run":
            lines.append("{}: not run ({}).".format(label, NOT_RUN_REASONS[report.reason or "earlier_step_failed"]))
        elif report.status == "stopped_at_time_limit":
            lines.append("{}: stopped at the one-hour limit.".format(label))
        else:
            sentence, fix, _ = CODES[report.code or "step_crashed"]
            tries = "{} {}".format(report.attempts, "try" if report.attempts == 1 else "tries")
            lines.append("{}: failed after {}. {} First thing to do: {}".format(label, tries, sentence, fix))
            failed_log = True
    lines.append(_count_line(reports))
    review = reports["review"]
    if review.status == "done":
        lines.append("Waiting for your review: {} impact findings and {} validity proposals. Open {}.".format(
            review.counts.get("impact_findings", 0), review.counts.get("validity_proposals", 0),
            run_dir / "review" / "REVIEW.md"))
    else:
        lines.append("Nothing is ready for your review yet.")
    if failed_log:
        lines.append("Details for a developer: {}".format(log_path(run_dir.parent.parent)))
    lines.append(FIXED_LINE)
    return "\n".join(lines) + "\n"


def result_line(result: RunResult) -> str:
    if result.outcome == "review_ready":
        return "Result: the knowledge update run is ready for your review. Open the summary above."
    if result.outcome == "stopped_at_time_limit":
        return "Result: the knowledge update run stopped at the one-hour limit. Read the summary above."
    return "Result: the knowledge update run failed. Read the summary above and do the first thing it says."


# --- Status ---------------------------------------------------------------------------------


@dataclass
class Status:
    on: bool
    last_outcome: Optional[str]
    last_finished: Optional[datetime]
    summary_path: Optional[Path]
    warnings: List[str]

    @property
    def healthy(self) -> bool:
        return self.on and not self.warnings and self.last_outcome in (None, "review_ready")


def _plist_since(ports: Ports) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(ports.plist.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def status(ports: Ports) -> Status:
    """On/off, the last run, and the ``missed`` / ``interrupted`` warnings. Raises ``OpsError`` on a bad ledger."""

    if not ports.home.is_dir():
        raise Problem(NOT_SET_UP, ON_COMMAND)
    on = ports.plist.exists() and ports.launchctl.is_loaded()
    records = read_ledger(ports.home)
    now = _utc(ports.clock())
    finished = {r["run_id"]: r for r in records if r["event"] == "run_finished"}
    started = [r for r in records if r["event"] == "run_started"]
    last_finished = next(iter(sorted(finished.values(), key=lambda r: r["finished_at"], reverse=True)), None)
    warnings: List[str] = []
    since = _parse_time(started[-1]["started_at"]) if started else None
    if on:
        origin = since or _plist_since(ports)
        if origin is not None and now - origin > MISSED_AFTER:
            warnings.append("missed")
    outcome = last_finished["outcome"] if last_finished else None
    if started and started[-1]["run_id"] not in finished and now - _parse_time(started[-1]["started_at"]) > INTERRUPTED_AFTER:
        warnings.append("interrupted")
        outcome = "interrupted"
    summary = None
    if last_finished is not None:
        candidate = ports.home / "runs" / last_finished["run_id"] / SUMMARY_NAME
        summary = candidate if candidate.exists() else None
    return Status(on, outcome, _parse_time(last_finished["finished_at"]) if last_finished else None, summary, warnings)


def status_lines(state: Status) -> Tuple[List[str], str]:
    """Plain lines and the closing ``Result:`` line."""

    lines = ["Knowledge updates are {}{}.".format(
        "on" if state.on else "off", " (every day at {:02d}:{:02d})".format(SCHEDULE_HOUR, SCHEDULE_MINUTE) if state.on else "")]
    if state.last_outcome is None:
        lines.append("No run has finished yet.")
    else:
        text = "Last run: {}".format(OUTCOME_WORDS[state.last_outcome])
        if state.last_finished is not None:
            text += ", finished {}".format(_local(state.last_finished))
        lines.append(text + ".")
    if state.summary_path is not None:
        lines.append("Summary: {}".format(state.summary_path))
    if "missed" in state.warnings:
        lines.append("Warning (missed): no run started in the last 30 hours. First thing to do: run {} now; "
                     "if it keeps happening, make sure this Mac is awake at {:02d}:{:02d}.".format(
                         RUN_COMMAND, SCHEDULE_HOUR, SCHEDULE_MINUTE))
    if "interrupted" in state.warnings:
        lines.append("Warning (interrupted): a run started and never finished. First thing to do: run {} again.".format(RUN_COMMAND))
    if not state.on:
        result = "Result: knowledge updates are off. Turn them on with {}.".format(ON_COMMAND)
    elif state.warnings:
        result = "Result: knowledge updates are on but need attention. Do the first thing above."
    elif state.last_outcome in (None, "review_ready"):
        result = ("Result: knowledge updates are on and the last run is ready for your review." if state.last_outcome
                  else "Result: knowledge updates are on. No run has finished yet.")
    else:
        result = "Result: knowledge updates are on but the last run did not finish well. Read its summary."
    return lines, result


def metrics_snapshot(folder: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    """The last finished outcome and time for the health metrics; ``readable`` is false on any problem."""

    try:
        if not Path(folder).is_dir():
            return {"readable": False}
        moment = _utc(now or datetime.now(timezone.utc))
        records = read_ledger(Path(folder))
        finished = {r["run_id"]: r for r in records if r["event"] == "run_finished"}
        started = [r for r in records if r["event"] == "run_started"]
        last = max(finished.values(), key=lambda r: r["finished_at"]) if finished else None
        outcome = last["outcome"] if last else None
        if started and started[-1]["run_id"] not in finished and \
                moment - _parse_time(started[-1]["started_at"]) > INTERRUPTED_AFTER:
            outcome = "interrupted"
        return {"readable": True, "outcome": outcome,
                "finished": _parse_time(last["finished_at"]).timestamp() if last else None}
    except Exception:  # noqa: BLE001 - an unreadable folder is a metric, never an error
        return {"readable": False}


# --- Turn on and off ------------------------------------------------------------------------

EXAMPLES = ("source-monitor.json", "page-monitor.json")


def plist_bytes(ports: Ports) -> bytes:
    """The launchd job: daily 10:20, no secret and no ``MANIJERO_*`` value."""

    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [str(ports.python), str(ports.script), "run", "--scheduled"],
        "StartCalendarInterval": {"Hour": SCHEDULE_HOUR, "Minute": SCHEDULE_MINUTE},
        "WorkingDirectory": str(ports.repo_root / "backend"),
        "EnvironmentVariables": {"PATH": ports.launchd_path},
        "StandardOutPath": str(ports.home / "logs" / LAUNCHD_LOG_NAME),
        "StandardErrorPath": str(ports.home / "logs" / LAUNCHD_LOG_NAME),
    })


def on_prerequisites(ports: Ports) -> None:
    if not os.access(str(ports.python), os.X_OK) or not ports.script.is_file():
        raise Problem("The backend tools are not set up yet.", SETUP_COMMAND)
    if not ports.launchctl.present():
        raise Problem("The macOS launchctl tool was not found; scheduled updates need macOS.",
                      "run this command on the Mac")
    for name in EXAMPLES:
        if not (ports.repo_root / "backend" / "deploy" / (name + ".example")).is_file():
            raise Problem("An example settings file is missing from the checkout.", "update the checkout with git pull")


def turn_on(ports: Ports) -> Tuple[int, str]:
    """Create the folder and the launchd agent; returns ``(exit code, Result line)``."""

    on_prerequisites(ports)
    _private_dir(ports.home)
    _private_dir(ports.home / "logs")
    for name in EXAMPLES:
        target = ports.home / name
        if not target.exists():
            _write_private(target, (ports.repo_root / "backend" / "deploy" / (name + ".example")).read_text(encoding="utf-8"))
    content = plist_bytes(ports)
    loaded = ports.launchctl.is_loaded()
    try:
        same = ports.plist.read_bytes() == content
    except OSError:
        same = False
    if same and loaded:
        return 0, "Result: knowledge updates are already on; nothing was changed."
    if loaded and not ports.launchctl.bootout():
        return 1, "Result: knowledge updates were not turned on. Run {} and try again.".format(OFF_COMMAND)
    ports.plist.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(ports.plist.parent), prefix=".{}-".format(LABEL))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, ports.plist)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    if not ports.launchctl.bootstrap(ports.plist):
        return 1, "Result: knowledge updates were not turned on. macOS refused the schedule; run {} again.".format(ON_COMMAND)
    return 0, "Result: knowledge updates are on. A run starts every day at {:02d}:{:02d} while this Mac is awake.".format(
        SCHEDULE_HOUR, SCHEDULE_MINUTE)


def turn_off(ports: Ports) -> Tuple[int, str]:
    """Remove only the launchd agent; the folder and its history stay."""

    if not ports.launchctl.present():
        if ports.plist.exists():
            return 1, "Result: knowledge updates could not be turned off because launchctl was not found. Run this command on the Mac."
        return 0, "Result: knowledge updates were already off; nothing was changed."
    loaded = ports.launchctl.is_loaded()
    existed = ports.plist.exists()
    if loaded and not ports.launchctl.bootout():
        return 1, "Result: knowledge updates could not be turned off. Run {} again.".format(OFF_COMMAND)
    try:
        ports.plist.unlink()
    except FileNotFoundError:
        pass
    if not loaded and not existed:
        return 0, "Result: knowledge updates were already off; nothing was changed."
    return 0, "Result: knowledge updates are off. Your history is kept."


# --- Steps (run in the child process) -------------------------------------------------------


@dataclass
class StepContext:
    home: Path
    run_dir: Path
    repo_root: Path
    as_of: date

    @property
    def reports(self) -> Path:
        return self.run_dir / "reports"

    @property
    def discovery_state(self) -> Path:
        return self.home / "source-updates" / "official-discovery-state.json"

    @property
    def ingestion_state(self) -> Path:
        return self.home / "ingestion" / "state.json"

    @property
    def quarantine(self) -> Path:
        return self.home / "ingestion" / "quarantine"

    @property
    def knowledge(self) -> Path:
        return self.repo_root / "knowledge"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, code: str = "config_invalid") -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StepFailure(code) from None


def step_discover(ctx: StepContext) -> Dict[str, int]:
    from app import page_monitor
    from app import source_update_scheduler as scheduler

    try:
        report = scheduler.run_updates(ctx.home / "source-updates", monitor_config=ctx.home / "source-monitor.json",
                                       trigger="knowledge_ops")
    except scheduler.LockedError:
        raise StepFailure("sources_unreachable") from None
    except (scheduler.SchedulerConfigError, OSError):
        raise StepFailure("config_invalid") from None
    if report["outcome"] == "config_error":
        raise StepFailure("config_invalid")
    config = _read_json(ctx.home / "page-monitor.json")
    try:
        pages = page_monitor.run(config, ctx.home / "page-monitor-state.json", ctx.reports / "page-monitor.json")
    except (page_monitor.PageMonitorError, OSError):
        raise StepFailure("config_invalid") from None
    if not ctx.discovery_state.exists():
        # Nothing was found yet: an empty, valid state lets the later steps run on zero candidates.
        from app import source_discovery
        _write_private(ctx.discovery_state, _json_text(
            {"schema_version": source_discovery.STATE_VERSION, "registries": {}, "candidates": {}}))
    counts = {
        "new_candidates": sum(int(job.get("new_or_changed_observations", 0)) for job in report["jobs"]),
        "pages_changed": sum(1 for page in pages["pages"] if page["status"] == "changed"),
    }
    if report["outcome"] == "failure":
        raise StepFailure("sources_unreachable", counts=counts)
    if any(page["status"] == "failed" for page in pages["pages"]):
        # The discovery state is good; only a page could not be read, so later steps may still run.
        raise StepFailure("pages_unreachable", usable=True, counts=counts)
    return counts


def step_classify(ctx: StepContext) -> Dict[str, int]:
    from app.gemini_generation import SystemClock
    from app.local_generation import DEFAULT_RECORD_PATH, OllamaTransport
    from app.relevance_classifier import (
        ClassificationAbort, build_response_format, classify, load_model_record, load_topics)

    clock = SystemClock()
    procedure_map = ctx.knowledge / "procedure_map.json"
    try:
        record = load_model_record(DEFAULT_RECORD_PATH, clock)
        topics = load_topics(procedure_map.read_bytes())
        transport = OllamaTransport(record, response_format=build_response_format(topics))
        document = classify(discovery_state=ctx.discovery_state, procedure_map=procedure_map,
                            report=ctx.reports / "relevance.json", transport=transport, clock=clock,
                            record_path=DEFAULT_RECORD_PATH)
    except ClassificationAbort as abort:
        raise StepFailure("model_not_running" if abort.failure == "model_unavailable" else "config_invalid") from None
    except OSError:
        raise StepFailure("config_invalid") from None
    summary = document["summary"]
    return {"relevant": summary["relevant"], "unsure": summary["unsure"], "not_relevant": summary["not_relevant"]}


def step_ingest(ctx: StepContext) -> Dict[str, int]:
    from app.document_ingestion import IngestionError, ingest

    monitor_state = ctx.home / "source-updates" / "source-monitor-state.json"
    try:
        report = ingest(ctx.discovery_state, ctx.ingestion_state, ctx.quarantine,
                        monitoring_state=monitor_state if monitor_state.exists() else None)
    except (IngestionError, OSError):
        raise StepFailure("knowledge_files_invalid") from None
    summary = report["summary"]
    return {"documents_ingested": summary["extracted"] + summary["unchanged"],
            "documents_failed": summary["failed"] + summary["rejected"]}


def step_impact(ctx: StepContext) -> Dict[str, int]:
    from app.change_impact import ImpactAnalysisError, analyze, write_report

    try:
        report = analyze(ctx.ingestion_state, ctx.quarantine, ctx.knowledge / "source_catalog.json",
                         ctx.knowledge / "passages.json", cases_path=ctx.knowledge / "pac_answer_eval.json",
                         as_of=ctx.as_of)
        write_report(report, ctx.reports / "impact.json")
    except (ImpactAnalysisError, OSError):
        raise StepFailure("knowledge_files_invalid") from None
    return {"impact_findings": report["summary"]["review_required"]}


def step_validity(ctx: StepContext) -> Dict[str, int]:
    from app.source_validity import SourceValidityError, check_validity, write_report

    catalog, passages, impact = ctx.knowledge / "source_catalog.json", ctx.knowledge / "passages.json", ctx.reports / "impact.json"
    try:
        report = check_validity(catalog, passages, impact, ctx.as_of)
        write_report(report, ctx.reports / "validity.json", input_paths=(catalog, passages, impact))
    except (SourceValidityError, OSError):
        raise StepFailure("knowledge_files_invalid") from None
    return {"validity_proposals": len(report["proposals"])}


REVIEW_REPORTS = ("page-monitor.json", "relevance.json", "impact.json", "validity.json")


def step_review(ctx: StepContext) -> Dict[str, int]:
    """Write the review folder: a plain-language REVIEW.md and review-ready.json. It publishes nothing."""

    from app.document_ingestion import IngestionError, candidate_admission_issue, load_discovery_candidates

    impact = _read_json(ctx.reports / "impact.json", "knowledge_files_invalid")
    validity = _read_json(ctx.reports / "validity.json", "knowledge_files_invalid")
    try:
        issues = {c["candidate_id"]: candidate_admission_issue(c) for c in load_discovery_candidates(ctx.discovery_state)}
    except IngestionError:
        raise StepFailure("knowledge_files_invalid") from None
    flagged = [c["candidate_id"] for c in impact["candidates"] if c["review"]["required"]]
    findings, proposals = len(flagged), len(validity["proposals"])
    earlier: Dict[str, int] = {}
    for name in ("discover", "classify", "ingest"):
        earlier.update(_clean_counts(_read_json(step_file(ctx.run_dir, name), "knowledge_files_invalid").get("counts")))
    digests = {name: _sha256_file(ctx.reports / name) for name in REVIEW_REPORTS if (ctx.reports / name).exists()}
    lines = [
        "# Knowledge update review: {}".format(ctx.run_dir.name), "",
        FIXED_LINE, "",
        "## What was found", "",
        "- New candidates: {}".format(earlier.get("new_candidates", 0)),
        "- Sorted by relevance: {} relevant, {} unsure, {} not relevant".format(
            earlier.get("relevant", 0), earlier.get("unsure", 0), earlier.get("not_relevant", 0)),
        "- Documents read: {}, failed: {}".format(earlier.get("documents_ingested", 0), earlier.get("documents_failed", 0)),
        "- Impact findings that need a person: {}".format(findings),
        "- Validity proposals: {}".format(proposals), "",
        "## Candidates to look at", "",
    ]
    lines += ["- {} (admission check: {})".format(cid, issues.get(cid) or "passed") for cid in flagged] or ["- None."]
    lines += ["", "## Reports", ""]
    lines += ["- ../reports/{} (sha256 {})".format(name, digest) for name, digest in digests.items()]
    lines += ["", "## Next step", "",
              "These reports only list what changed; they do not decide it. To turn a change into a review "
              "package, a developer writes the proposal file and runs `backend/scripts/knowledge_review.py prepare` "
              "(see the Knowledge update runs section of backend/README.md). Nothing goes live until you approve it."]
    review_dir = ctx.run_dir / "review"
    _private_dir(review_dir)
    _write_private(review_dir / "REVIEW.md", "\n".join(lines) + "\n")
    _write_private(review_dir / "review-ready.json", _json_text({
        "schema_version": REVIEW_SCHEMA, "run_id": ctx.run_dir.name, "as_of": ctx.as_of.isoformat(),
        "published": False, "requires_owner_approval": True,
        "counts": {"impact_findings": findings, "validity_proposals": proposals},
        "candidate_ids": flagged,
        "reports": {name: {"path": "../reports/" + name, "sha256": digest} for name, digest in digests.items()},
    }))
    return {"impact_findings": findings, "validity_proposals": proposals}


ADAPTERS: Dict[str, Callable[[StepContext], Dict[str, int]]] = {
    "discover": step_discover, "classify": step_classify, "ingest": step_ingest,
    "impact": step_impact, "validity": step_validity, "review": step_review,
}


def execute_step(name: str, run_dir: Path, repo_root: Path) -> int:
    """Child-process entry: run one step and write its result file. Tracebacks go only to the log."""

    run_dir = Path(run_dir)
    home = run_dir.parent.parent
    try:
        info = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        context = StepContext(home, run_dir, Path(repo_root), date.fromisoformat(info["as_of"]))
        counts = ADAPTERS[name](context)
    except StepFailure as failure:
        write_child_result(run_dir, name, failure=failure)
        return 1
    except Exception as error:  # noqa: BLE001 - the child must always leave a fixed result
        append_log(home, "step {} stopped unexpectedly ({}):\n{}".format(name, type(error).__name__, traceback.format_exc()))
        write_child_result(run_dir, name, failure=StepFailure("step_crashed"))
        return 1
    write_child_result(run_dir, name, counts=counts)
    return 0
