"""The complete evaluation, run every night at 00:00 with a cache check, and a report.

One run starts the accepted metrics command (``backend/scripts/evaluate_metrics.py run
--answer-cache-check``) in a child process, so three hours is a hard stop even if the local judge
hangs. The run reads the report that command wrote, keeps eight overall scores, compares them with
the previous *evaluated* run, appends a ledger line the health dashboard reads, and sends one fixed
Telegram message when a score is lower than before. It is report-only: no score changes an exit
code, a gate, a release, or the answers. Owner commands live in ``backend/scripts/nightly_eval.py``.

Only ids, fixed codes, counts, scores, and times reach the ledger, the summary, the metrics, and
the message: never a question, an answer, a passage, a land, a token, or exception text. Tracebacks
go only to the private log. The Telegram details are used only inside this process.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from app.knowledge_ops import (
    MADRID,
    AlreadyRunning,
    OpsError,
    Problem,
    SubprocessRunner,
    _Lock as _BaseLock,
    _parse_time,
    _private_dir,
    _utc,
    _write_private,
    new_run_id,
)

ON_COMMAND = "./scripts/init.sh --nightly-eval-on"
OFF_COMMAND = "./scripts/init.sh --nightly-eval-off"
RUN_COMMAND = "./scripts/init.sh --nightly-eval-run"
STATUS_COMMAND = "./scripts/init.sh --nightly-eval-status"
SETUP_COMMAND = "./scripts/init.sh --local-rag-setup"

HOME_ENV = "MANIJERO_NIGHTLY_EVAL_HOME"  # tests only
STATE_DIR_ENV = "MANIJERO_NIGHTLY_EVAL_STATE_DIR"  # read by the health metrics
CHILD_CLI_ENV = "MANIJERO_NIGHTLY_EVAL_CHILD_CLI"  # tests only: replaces the metrics command
REPORTS_ROOT_ENV = "MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT"  # tests only: where the child writes reports
NO_WAIT_ENV = "MANIJERO_NIGHTLY_EVAL_NO_WAIT"  # tests only: the alert retries do not wait
LABEL = "org.manijero.nightly-eval"
SCHEDULE_HOUR, SCHEDULE_MINUTE = 0, 0

BUDGET = timedelta(hours=3)
MISSED_AFTER = timedelta(hours=30)
INTERRUPTED_AFTER = timedelta(hours=4)
SEND_TRIES = 3
SEND_WAIT_SECONDS = 10
KILL_GRACE_SECONDS = 10

LEDGER_SCHEMA = "nightly-eval-ledger-v1"
REPORT_SCHEMA = "eval-metrics-report-v1"
LEDGER_NAME = "nightly-eval-ledger.jsonl"
LOCK_NAME = "nightly-eval.lock"
LATEST_SUMMARY_NAME = "latest-summary.txt"
LOG_NAME = "nightly-eval.log"
LAUNCHD_LOG_NAME = "launchd.log"
CHILD_OUTPUT_NAME = ".child-output"
MAX_LEDGER_BYTES = 10 * 1024 * 1024
RUN_ID_PATTERN = re.compile(r"^run-\d{8}T\d{6}Z-[a-f0-9]{8}$")
REPORT_PATH = re.compile(r"Report: (?:\S*/)?([0-9a-f]{16})/metrics\.json")
CHILD_ABORT = re.compile(r"did not run \(([a-z_]+)\)")

TRIGGERS = ("manual", "schedule")
OUTCOMES = ("evaluated", "failed", "stopped_at_time_limit")
ALERT_STATES = ("not_needed", "sent", "not_sent", "not_set_up")
FAILURE_CODES = ("invalid_inputs", "ask_failed", "unsafe_report_path", "internal_error", "child_output_unreadable")

# The eight overall scores, in the order they are shown, with their plain labels.
SCORE_KEYS = ("hit_at_1", "hit_at_3", "hit_at_5", "mrr", "abstention", "numeric", "faithfulness", "cache_reuse")
LABELS: Mapping[str, str] = {
    "hit_at_1": "right source first",
    "hit_at_3": "right source in the top 3",
    "hit_at_5": "right source in the top 5",
    "mrr": "average source rank score (MRR)",
    "abstention": "correct refusals",
    "numeric": "numbers and dates correct",
    "faithfulness": "sentences the judge found supported",
    "cache_reuse": "cached answers reused unchanged",
}

OUTCOME_WORDS = {
    "evaluated": "evaluated",
    "failed": "something failed",
    "stopped_at_time_limit": "stopped at the 3-hour limit",
    "interrupted": "interrupted before it finished",
}
NOT_SET_UP = "The nightly evaluation is not set up yet."
FIRST_STEP = " First step: open the health dashboard, then run {}.".format(STATUS_COMMAND)
INPUTS_CHANGED = " The questions or the knowledge changed since the last run, so a drop may be expected."
ALERT_FIX = {
    "not_sent": "run ./scripts/init.sh --qa-alerts-test and fix what it says",
    "not_set_up": "run ./scripts/init.sh --qa-alerts-setup",
}


# --- Ports ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChildResult:
    """What the metrics command left behind: whether it timed out, its exit code, its ``Result:`` line."""

    timed_out: bool
    exit_code: Optional[int]
    result_line: str = ""


class ChildRunner(Protocol):
    def run(self, as_of: str, timeout_seconds: float) -> ChildResult: ...


class Launchctl(Protocol):
    """``launchctl`` for the one nightly label and nothing else."""

    def present(self) -> bool: ...

    def is_loaded(self) -> bool: ...

    def bootstrap(self, plist: Path) -> bool: ...

    def bootout(self) -> bool: ...


class Telegram(Protocol):
    """The owner's Telegram bot. The token and chat id live only inside the implementation."""

    def configured(self) -> bool: ...

    def send(self, text: str) -> bool:
        """One try; ``True`` when Telegram accepted the message."""


@dataclass
class Ports:
    """Every external effect; tests pass fakes."""

    home: Path
    repo_root: Path
    agents_dir: Path
    python: Path
    reports_root: Path
    clock: Callable[[], datetime]
    sleep: Callable[[float], None]
    runner: ChildRunner
    launchctl: Launchctl
    telegram: Telegram
    launchd_path: str = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    out: Callable[[str], None] = print

    @property
    def plist(self) -> Path:
        return self.agents_dir / "{}.plist".format(LABEL)

    @property
    def script(self) -> Path:
        return self.repo_root / "backend" / "scripts" / "nightly_eval.py"


def nightly_eval_home(environ: Mapping[str, str]) -> Path:
    raw = (environ.get(HOME_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    home = (environ.get("HOME") or "").strip()
    return (Path(home) if home else Path.home()) / "manijero" / "nightly-eval"


class SubprocessChild:
    """Runs the metrics command as a child process; terminates it, then kills it, when time is up."""

    def __init__(self, argv_prefix: Sequence[str], home: Path) -> None:
        self._prefix = list(argv_prefix)
        self._home = home

    def run(self, as_of: str, timeout_seconds: float) -> ChildResult:
        _private_dir(self._home / "logs")
        output = self._home / CHILD_OUTPUT_NAME
        log = log_path(self._home)
        out_fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        err_fd = os.open(str(log), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed program, fixed arguments
                [*self._prefix, "run", "--as-of", as_of, "--answer-cache-check"],
                stdin=subprocess.DEVNULL, stdout=out_fd, stderr=err_fd, start_new_session=True,
            )
        except OSError:
            return ChildResult(False, None)
        finally:
            os.close(out_fd)
            os.close(err_fd)
        timed_out = False
        try:
            process.wait(timeout=max(timeout_seconds, 0.01))
        except subprocess.TimeoutExpired:
            timed_out = True
            SubprocessRunner._signal(process, signal.SIGTERM)
            try:
                process.wait(timeout=KILL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                SubprocessRunner._signal(process, signal.SIGKILL)
                process.wait()
        line = _last_result_line(output)
        try:
            output.unlink()
        except OSError:
            pass
        return ChildResult(timed_out, None if timed_out else process.returncode, line)


def _last_result_line(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    found = [line for line in lines if line.startswith("Result:")]
    return found[-1] if found else ""


# --- Files ----------------------------------------------------------------------------------


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


class _Lock(_BaseLock):
    def __init__(self, home: Path) -> None:
        super().__init__(home)
        self._path = Path(home) / LOCK_NAME


# --- Ledger ---------------------------------------------------------------------------------


def _number_or_none(value: Any) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def _validate_record(record: Any) -> Dict[str, Any]:
    if (not isinstance(record, dict) or record.get("schema_version") != LEDGER_SCHEMA
            or record.get("event") not in ("run_started", "run_finished")
            or not isinstance(record.get("run_id"), str) or not RUN_ID_PATTERN.fullmatch(record["run_id"])
            or record.get("trigger") not in TRIGGERS):
        raise OpsError("ledger_invalid")
    _parse_time(record.get("started_at"))
    if record["event"] == "run_finished":
        _parse_time(record.get("finished_at"))
        scores = record.get("scores", {})
        if (record.get("outcome") not in OUTCOMES or record.get("alert") not in ALERT_STATES
                or not isinstance(scores, dict) or any(k not in SCORE_KEYS or not _number_or_none(v) for k, v in scores.items())
                or not isinstance(record.get("drops", []), list)
                or any(not isinstance(d, dict) or d.get("metric") not in SCORE_KEYS for d in record.get("drops", []))):
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


def _finished(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(r) for r in records if r["event"] == "run_finished"]


# --- Scores ---------------------------------------------------------------------------------


def _rounded(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpsError("report_invalid")
    return round(float(value), 4)


def extract(document: Any) -> Tuple[Dict[str, Optional[float]], str, Dict[str, Any], str]:
    """``(scores, faithfulness status, inputs, report id)`` from a metrics report; ``OpsError`` if unusable."""

    try:
        if document["schema_version"] != REPORT_SCHEMA:
            raise OpsError("report_invalid")
        metrics = document["metrics"]
        retrieval = metrics["retrieval"]["overall"]
        faithfulness = document["faithfulness"]
        judged = faithfulness["status"] == "judged"
        check = document.get("answer_cache_check")
        reuse = None
        if isinstance(check, Mapping) and int(check["asked"]) > 0:
            reuse = int(check["reused_unchanged"]) / int(check["asked"])
        scores = {
            "hit_at_1": _rounded(retrieval["hit_at_1"]),
            "hit_at_3": _rounded(retrieval["hit_at_3"]),
            "hit_at_5": _rounded(retrieval["hit_at_5"]),
            "mrr": _rounded(retrieval["mrr"]),
            "abstention": _rounded(metrics["abstention"]["overall"]["share"]),
            "numeric": _rounded(metrics["numeric"]["overall"]["share"]),
            "faithfulness": _rounded(faithfulness["supported_share"]) if judged else None,
            "cache_reuse": _rounded(reuse),
        }
        version = document["version"]
        inputs = {key: value for key, value in version.items() if key != "as_of"}
        report_id = document["version_id"]
        if not isinstance(report_id, str) or not re.fullmatch(r"[0-9a-f]{16}", report_id):
            raise OpsError("report_invalid")
        return scores, "judged" if judged else "not_judged", json.loads(json.dumps(inputs)), report_id
    except OpsError:
        raise
    except (KeyError, TypeError, ValueError):
        raise OpsError("report_invalid") from None


def compare(previous: Optional[Mapping[str, Any]], current: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Scores strictly lower (at 4 decimals) than in the previous run; a missing value is never compared."""

    if previous is None:
        return []
    drops = []
    for key in SCORE_KEYS:
        old, new = previous.get(key), current.get(key)
        if old is None or new is None:
            continue
        if round(float(new), 4) < round(float(old), 4):
            drops.append({"metric": key, "old": round(float(old), 4), "new": round(float(new), 4)})
    return drops


def _value(key: str, value: Optional[float]) -> str:
    if value is None:
        return "not measured"
    return "{:.4f}".format(value) if key == "mrr" else "{:.1f}%".format(value * 100)


def alert_text(drops: Sequence[Mapping[str, Any]], inputs_changed: bool) -> str:
    parts = "; ".join("{} {} -> {}".format(LABELS[d["metric"]], _value(d["metric"], d["old"]), _value(d["metric"], d["new"]))
                      for d in drops)
    return "Manijero nightly evaluation: {} score(s) dropped since the last run: {}.{}{}".format(
        len(drops), parts, INPUTS_CHANGED if inputs_changed else "", FIRST_STEP)


def failure_alert_text(outcome: str, code: Optional[str]) -> str:
    return "Manijero nightly evaluation: the run did not finish ({}, code {}). No scores were recorded.{}".format(
        OUTCOME_WORDS[outcome], code, FIRST_STEP)


def missed_sentence(since: datetime, started: datetime) -> str:
    return "It had not run since {} ({} hours), so at least one night was missed.".format(
        _local(since), int((started - since).total_seconds() // 3600))


def run_alert_text(outcome: str, code: Optional[str], record: Mapping[str, Any], missed: Optional[str]) -> Optional[str]:
    """The one message for a run: a score drop, a run that did not finish, or a missed night; else ``None``."""

    if outcome != "evaluated":
        text = failure_alert_text(outcome, code)
    elif record.get("drops"):
        text = alert_text(record["drops"], record["inputs_changed"])
    elif missed:
        text = "Manijero nightly evaluation: it ran and no score dropped.{}".format(FIRST_STEP)
    else:
        return None
    if missed:
        prefix = "Manijero nightly evaluation: "
        text = prefix + missed + " " + text[len(prefix):]
    return text


def send_alert(ports: Ports, text: str) -> str:
    """One message, at most 3 tries 10 s apart; returns the alert state to record."""

    if not ports.telegram.configured():
        return "not_set_up"
    for attempt in range(SEND_TRIES):
        if ports.telegram.send(text):
            return "sent"
        if attempt + 1 < SEND_TRIES:
            ports.sleep(SEND_WAIT_SECONDS)
    return "not_sent"


# --- The run --------------------------------------------------------------------------------


@dataclass
class RunResult:
    run_id: str
    outcome: str
    summary: str
    code: Optional[str] = None
    drops: List[Dict[str, Any]] = field(default_factory=list)
    alert: str = "not_needed"

    @property
    def exit_code(self) -> int:
        return 0 if self.outcome == "evaluated" else 1


def run_prerequisites(ports: Ports) -> None:
    if not ports.home.is_dir():
        raise Problem(NOT_SET_UP, ON_COMMAND)
    if not os.access(str(ports.python), os.X_OK):
        raise Problem("The backend tools are not set up yet.", SETUP_COMMAND)
    if not ports.launchctl.present():
        raise Problem("The macOS launchctl tool was not found; the nightly evaluation needs macOS.",
                      "run this command on the Mac")


def _read_report(ports: Ports, result: ChildResult) -> Tuple[Dict[str, Optional[float]], str, Dict[str, Any], str]:
    found = REPORT_PATH.search(result.result_line)
    if found is None:
        raise OpsError("child_output_unreadable")
    path = ports.reports_root / found.group(1) / "metrics.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise OpsError("child_output_unreadable") from None
    try:
        return extract(document)
    except OpsError:
        raise OpsError("child_output_unreadable") from None


def _failure_code(result: ChildResult) -> str:
    found = CHILD_ABORT.search(result.result_line)
    return found.group(1) if found and found.group(1) in FAILURE_CODES else "child_output_unreadable"


def run_once(ports: Ports, trigger: str) -> RunResult:
    """Run the whole evaluation once inside 3 hours; raises ``Problem``/``AlreadyRunning``."""

    if trigger not in TRIGGERS:
        raise OpsError("trigger_invalid")
    run_prerequisites(ports)
    with _Lock(ports.home):
        history = read_ledger(ports.home)
        started = _utc(ports.clock())
        earlier = [_parse_time(r["started_at"]) for r in history if r["event"] == "run_started"]
        missed = missed_sentence(max(earlier), started) if earlier and started - max(earlier) > MISSED_AFTER else None
        deadline = started + BUDGET
        run_id = new_run_id(started)
        as_of = started.astimezone(MADRID).date().isoformat()
        base = {"schema_version": LEDGER_SCHEMA, "run_id": run_id, "trigger": trigger, "started_at": started.isoformat()}
        _append_ledger(ports.home, {**base, "event": "run_started", "as_of": as_of})

        child = ports.runner.run(as_of, max((deadline - _utc(ports.clock())).total_seconds(), 0.0))
        record: Dict[str, Any] = {}
        outcome, code = "failed", None
        if child.timed_out:
            outcome, code = "stopped_at_time_limit", "time_limit"
        elif child.exit_code == 0:
            try:
                scores, faith, inputs, report_id = _read_report(ports, child)
                outcome = "evaluated"
                previous = next((r for r in reversed(_finished(history)) if r["outcome"] == "evaluated"), None)
                drops = compare(previous["scores"] if previous else None, scores)
                changed = bool(previous) and previous.get("inputs") != inputs
                record = {"report_id": report_id, "scores": scores, "faithfulness": faith, "inputs": inputs,
                          "inputs_changed": changed, "first_run": previous is None, "drops": drops}
            except OpsError as error:
                code = error.code if error.code in FAILURE_CODES else "child_output_unreadable"
        else:
            code = _failure_code(child)

        alert = "not_needed"
        text = run_alert_text(outcome, code, record, missed)
        if text is not None:
            alert = send_alert(ports, text)
        finished = _utc(ports.clock())
        summary = render_summary(started, finished, outcome, code, record, alert, log_path(ports.home), missed)
        _write_private(ports.home / LATEST_SUMMARY_NAME, summary)
        _append_ledger(ports.home, {**base, "event": "run_finished", "finished_at": finished.isoformat(),
                                    "outcome": outcome, "code": code, "alert": alert, **record})
    return RunResult(run_id, outcome, summary, code, record.get("drops", []), alert)


# --- Summary --------------------------------------------------------------------------------


def _local(moment: datetime) -> str:
    return moment.astimezone(MADRID).strftime("%Y-%m-%d %H:%M")


def _took(started: datetime, finished: datetime) -> str:
    minutes = round((finished - started).total_seconds() / 60)
    return "less than a minute" if minutes < 1 else "{} min".format(minutes)


def _score_line(title: str, keys: Sequence[str], scores: Mapping[str, Any]) -> str:
    return "{}: {}.".format(title, "; ".join("{} {}".format(LABELS[k], _value(k, scores.get(k))) for k in keys))


def _drop_sentence(record: Mapping[str, Any]) -> str:
    if record.get("first_run"):
        return "Compared with the last run: this is the first run, so nothing was compared."
    drops = record.get("drops") or []
    if not drops:
        return "Compared with the last run: no score dropped."
    return "Compared with the last run: {} score(s) dropped: {}.".format(
        len(drops), "; ".join("{} {} -> {}".format(LABELS[d["metric"]], _value(d["metric"], d["old"]),
                                                    _value(d["metric"], d["new"])) for d in drops))


def _alert_sentence(alert: str) -> Optional[str]:
    if alert == "sent":
        return "Alert: one message was sent to your phone."
    if alert in ALERT_FIX:
        return "Alert: the message was not sent. First thing to do: {}.".format(ALERT_FIX[alert])
    return None


def render_summary(started: datetime, finished: datetime, outcome: str, code: Optional[str],
                   record: Mapping[str, Any], alert: str, log: Path, missed: Optional[str] = None) -> str:
    lines = ["Nightly evaluation on {} (took {}).".format(_local(started), _took(started, finished))]
    if missed:
        lines.append(missed)
    if outcome == "evaluated":
        scores = record["scores"]
        lines += ["How it went: evaluated.",
                  _score_line("Sources", SCORE_KEYS[:4], scores),
                  _score_line("Answers", SCORE_KEYS[4:], scores),
                  _drop_sentence(record)]
        if record.get("inputs_changed"):
            lines.append(INPUTS_CHANGED.strip())
        sentence = _alert_sentence(alert)
        if sentence:
            lines.append(sentence)
        lines.append("Report: {}.".format(record["report_id"]))
    else:
        lines.append("How it went: {}.".format(OUTCOME_WORDS[outcome]))
        lines.append("Code: {}. No scores were recorded. First thing to do: run {} again; if it keeps "
                     "happening, tell a developer.".format(code, RUN_COMMAND))
        sentence = _alert_sentence(alert)
        if sentence:
            lines.append(sentence)
        lines.append("Details for a developer: {}".format(log))
    return "\n".join(lines) + "\n"


def result_line(result: RunResult) -> str:
    if result.outcome == "evaluated":
        if result.drops:
            return "Result: the nightly evaluation finished and {} score(s) dropped. Read the summary above.".format(
                len(result.drops))
        return "Result: the nightly evaluation finished. No score dropped."
    if result.outcome == "stopped_at_time_limit":
        return "Result: the nightly evaluation stopped at the 3-hour limit. Read the summary above."
    return "Result: the nightly evaluation failed. Read the summary above and do the first thing it says."


# --- Status ---------------------------------------------------------------------------------


@dataclass
class Status:
    on: bool
    outcome: Optional[str]
    finished: Optional[datetime]
    last: Optional[Dict[str, Any]]
    warnings: List[str]
    healthy: bool


def _plist_since(ports: Ports) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(ports.plist.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def status(ports: Ports) -> Status:
    """On/off, the last run, and the ``missed`` / ``interrupted`` warnings. Raises ``OpsError`` on a bad ledger."""

    on = ports.plist.exists() and ports.launchctl.is_loaded()
    records = read_ledger(ports.home) if ports.home.is_dir() else []
    now = _utc(ports.clock())
    finished = _finished(records)
    started = [r for r in records if r["event"] == "run_started"]
    last = max(finished, key=lambda r: r["finished_at"]) if finished else None
    warnings: List[str] = []
    if on:
        origin = _parse_time(started[-1]["started_at"]) if started else _plist_since(ports)
        if origin is not None and now - origin > MISSED_AFTER:
            warnings.append("missed")
    outcome = last["outcome"] if last else None
    finished_at = _parse_time(last["finished_at"]) if last else None
    finished_ids = {r["run_id"] for r in finished}
    if started and started[-1]["run_id"] not in finished_ids and \
            now - _parse_time(started[-1]["started_at"]) > INTERRUPTED_AFTER:
        warnings.append("interrupted")
        outcome = "interrupted"
    healthy = (on and not warnings and last is not None and last["outcome"] == "evaluated"
               and finished_at is not None and now - finished_at <= MISSED_AFTER
               and last["alert"] not in ("not_sent", "not_set_up"))
    return Status(on, outcome, finished_at, last, warnings, healthy)


def status_lines(state: Status) -> Tuple[List[str], str]:
    """Plain lines and the closing ``Result:`` line."""

    lines = ["The nightly evaluation is {}{}.".format(
        "on" if state.on else "off",
        " (every night at {:02d}:{:02d})".format(SCHEDULE_HOUR, SCHEDULE_MINUTE) if state.on else "")]
    last = state.last
    if state.outcome is None:
        lines.append("No run has finished yet.")
    else:
        text = "Last run: {}".format(OUTCOME_WORDS[state.outcome])
        if state.finished is not None:
            text += ", finished {}".format(_local(state.finished))
        lines.append(text + ".")
    if last is not None and last["outcome"] == "evaluated":
        lines.append(_score_line("Scores", SCORE_KEYS, last["scores"]))
        lines.append(_drop_sentence(last))
        sentence = _alert_sentence(last["alert"])
        if sentence:
            lines.append(sentence)
    if "missed" in state.warnings:
        lines.append("Warning (missed): no run started in the last 30 hours. First thing to do: run {} now; "
                     "if it keeps happening, make sure this Mac is on at {:02d}:{:02d}.".format(
                         RUN_COMMAND, SCHEDULE_HOUR, SCHEDULE_MINUTE))
    if "interrupted" in state.warnings:
        lines.append("Warning (interrupted): a run started and never finished. First thing to do: run {} again.".format(
            RUN_COMMAND))
    if not state.on:
        result = "Result: the nightly evaluation is off. Turn it on with {}.".format(ON_COMMAND)
    elif state.healthy:
        result = "Result: the nightly evaluation is on and the last run was evaluated."
    elif state.outcome is None and not state.warnings:
        result = "Result: the nightly evaluation is on. No run has finished yet."
    else:
        result = "Result: the nightly evaluation is on but needs attention. Do the first thing above."
    return lines, result


def metrics_snapshot(folder: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Outcome, time, scores, and drops of the last finished run for the health metrics.

    ``readable`` is false on any problem. Scores and drops are present only for an evaluated run.
    """

    try:
        if not Path(folder).is_dir():
            return {"readable": False}
        moment = _utc(now or datetime.now(timezone.utc))
        records = read_ledger(Path(folder))
        finished = _finished(records)
        started = [r for r in records if r["event"] == "run_started"]
        last = max(finished, key=lambda r: r["finished_at"]) if finished else None
        outcome = last["outcome"] if last else None
        if started and started[-1]["run_id"] not in {r["run_id"] for r in finished} and \
                moment - _parse_time(started[-1]["started_at"]) > INTERRUPTED_AFTER:
            outcome = "interrupted"
        scores: Dict[str, float] = {}
        dropped: Dict[str, int] = {}
        if last is not None and last["outcome"] == "evaluated":
            names = {d["metric"] for d in last.get("drops", [])}
            for key in SCORE_KEYS:
                value = last["scores"].get(key)
                if value is not None:
                    scores[key] = float(value)
                    dropped[key] = 1 if key in names else 0
        return {"readable": True, "outcome": outcome,
                "finished": _parse_time(last["finished_at"]).timestamp() if last else None,
                "scores": scores, "dropped": dropped}
    except Exception:  # noqa: BLE001 - an unreadable folder is a metric, never an error
        return {"readable": False}


# --- Turn on and off ------------------------------------------------------------------------


def plist_bytes(ports: Ports) -> bytes:
    """The launchd job: every night at 00:00, no secret and no ``MANIJERO_*`` value."""

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
        raise Problem("The macOS launchctl tool was not found; the nightly evaluation needs macOS.",
                      "run this command on the Mac")


def turn_on(ports: Ports) -> Tuple[int, str]:
    """Create the folder and the launchd agent; returns ``(exit code, Result line)``."""

    on_prerequisites(ports)
    _private_dir(ports.home)
    _private_dir(ports.home / "logs")
    content = plist_bytes(ports)
    loaded = ports.launchctl.is_loaded()
    try:
        same = ports.plist.read_bytes() == content
    except OSError:
        same = False
    if same and loaded:
        return 0, "Result: the nightly evaluation is already on; nothing was changed."
    if loaded and not ports.launchctl.bootout():
        return 1, "Result: the nightly evaluation was not turned on. Run {} and try again.".format(OFF_COMMAND)
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
        return 1, "Result: the nightly evaluation was not turned on. macOS refused the schedule; run {} again.".format(
            ON_COMMAND)
    return 0, "Result: the nightly evaluation is on. It runs every night at {:02d}:{:02d} while this Mac is on.".format(
        SCHEDULE_HOUR, SCHEDULE_MINUTE)


def turn_off(ports: Ports) -> Tuple[int, str]:
    """Remove only the launchd agent; the folder and its history stay."""

    if not ports.launchctl.present():
        if ports.plist.exists():
            return 1, ("Result: the nightly evaluation could not be turned off because launchctl was not found. "
                       "Run this command on the Mac.")
        return 0, "Result: the nightly evaluation was already off; nothing was changed."
    loaded = ports.launchctl.is_loaded()
    existed = ports.plist.exists()
    if loaded and not ports.launchctl.bootout():
        return 1, "Result: the nightly evaluation could not be turned off. Run {} again.".format(OFF_COMMAND)
    try:
        ports.plist.unlink()
    except FileNotFoundError:
        pass
    if not loaded and not existed:
        return 0, "Result: the nightly evaluation was already off; nothing was changed."
    return 0, "Result: the nightly evaluation is off. Your history is kept."
