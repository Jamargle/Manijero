"""Best-effort scheduled dispatch of official-source monitoring and discovery.

This module wraps the accepted ``source_monitor.scan`` and
``source_discovery.discover`` commands unchanged. It adds due rules, catch-up,
target-level retries with fixed backoff, an exclusive run lock, an append-only
run ledger, and a status evaluation that makes missed, interrupted, failed, and
stale runs visible. Every result stays a quarantined review signal: a
successful run means only that the listed targets responded. It never claims
freshness or coverage, never reads secrets, and never sends notifications.
"""

import errno
import fcntl
import json
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from app import source_discovery, source_monitor

LEDGER_SCHEMA = "source-update-ledger-v1"
STATUS_SCHEMA = "source-update-status-v1"
LEDGER_NAME = "source-update-ledger.jsonl"
LOCK_NAME = "source-update.lock"
MONITOR_STATE_NAME = "source-monitor-state.json"
DISCOVERY_STATE_NAME = "official-discovery-state.json"
MAX_LEDGER_BYTES = 10 * 1024 * 1024

JOBS = ("monitor", "boe", "boja")
TRIGGERS = ("manual", "systemd")
MAX_ATTEMPTS = {"monitor": 3, "boe": 3, "boja": 2}
# Backoff before attempt 2 and attempt 3.
BACKOFF_SECONDS = (60, 300)

MADRID = ZoneInfo("Europe/Madrid")
MONITOR_DUE_AFTER = timedelta(hours=12)
BOJA_DUE_AFTER = timedelta(hours=156)
BOE_WINDOW_DAYS = 14
BOE_READY_HOUR = 9
BOE_MANUAL_MAX_AGE_DAYS = 60
BOJA_MAX_YEARS = 2

MISSED_RUN_AFTER = timedelta(hours=30)
INTERRUPTED_AFTER = timedelta(hours=2)
STALE_AFTER = {"monitor": timedelta(hours=36), "boe": timedelta(hours=36), "boja": timedelta(hours=192)}
ABANDONED_LOOKBACK_DAYS = 60
UNCHECKED_REGISTRIES = ("fega", "mapa")

RUN_OUTCOMES = ("success", "failure", "config_error", "nothing_due")
JOB_STATUSES = ("success", "failure", "config_error", "not_due", "not_selected")
ATTEMPTED_STATUSES = ("success", "failure", "config_error")
RUN_ID_PATTERN = re.compile(r"^run-\d{8}T\d{6}Z-[a-f0-9]{8}$")
BOE_DATE_PATTERN = re.compile(r"^\d{8}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class SchedulerConfigError(ValueError):
    """Run-level configuration or state error; ``code`` is a fixed, value-safe string."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class LockedError(RuntimeError):
    """Another scheduler run holds the state-directory lock."""


class _JobConfigError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- paths/files

def _resolve_state_dir(state_dir: Path) -> Path:
    resolved = Path(state_dir).expanduser().resolve()
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise SchedulerConfigError("state_dir_inside_repository")
    return resolved


def _restrict(path: Path) -> None:
    try:
        os.chmod(str(path), 0o600)
    except FileNotFoundError:
        pass


class _RunLock:
    def __init__(self, state_dir: Path):
        self._path = state_dir / LOCK_NAME
        self._fd: Optional[int] = None

    def __enter__(self) -> "_RunLock":
        fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(fd)
            if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                raise LockedError("locked") from None
            raise
        self._fd = fd
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


# --------------------------------------------------------------------- ledger

def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise SchedulerConfigError("ledger_invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise SchedulerConfigError("ledger_invalid") from None
    if parsed.tzinfo is None:
        raise SchedulerConfigError("ledger_invalid")
    return parsed


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_record(record: Any) -> Dict[str, Any]:
    if (not isinstance(record, dict) or record.get("schema_version") != LEDGER_SCHEMA
            or record.get("event") not in ("run_started", "run_finished")
            or not isinstance(record.get("run_id"), str) or not RUN_ID_PATTERN.fullmatch(record["run_id"])
            or record.get("trigger") not in TRIGGERS):
        raise SchedulerConfigError("ledger_invalid")
    _parse_time(record.get("started_at"))
    if record["event"] == "run_started":
        if not _is_str_list(record.get("jobs")) or not isinstance(record.get("forced"), bool):
            raise SchedulerConfigError("ledger_invalid")
        return record
    _parse_time(record.get("finished_at"))
    if record.get("outcome") not in RUN_OUTCOMES or not isinstance(record.get("jobs"), list):
        raise SchedulerConfigError("ledger_invalid")
    for job in record["jobs"]:
        if (not isinstance(job, dict) or job.get("job") not in JOBS or job.get("status") not in JOB_STATUSES
                or not _is_str_list(job.get("succeeded")) or not isinstance(job.get("failed"), list)
                or not all(isinstance(item, dict) and isinstance(item.get("target"), str) for item in job["failed"])
                or not _is_str_list(job.get("abandoned_dates", []))):
            raise SchedulerConfigError("ledger_invalid")
    return record


def read_ledger(ledger_path: Path) -> List[Dict[str, Any]]:
    """Read and validate every ledger line; refuse a malformed or oversized ledger."""
    try:
        size = os.stat(str(ledger_path)).st_size
    except FileNotFoundError:
        return []
    except OSError:
        raise SchedulerConfigError("ledger_unreadable") from None
    if size > MAX_LEDGER_BYTES:
        raise SchedulerConfigError("ledger_too_large")
    try:
        text = Path(ledger_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise SchedulerConfigError("ledger_unreadable") from None
    records = []
    for line in text.splitlines():
        if not line.strip():
            raise SchedulerConfigError("ledger_invalid")
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            raise SchedulerConfigError("ledger_invalid") from None
        records.append(_validate_record(value))
    return records


def _append_ledger(ledger_path: Path, record: Mapping[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    fd = os.open(str(ledger_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


# ------------------------------------------------------------ ledger history

class _History:
    def __init__(self, records: Sequence[Mapping[str, Any]]):
        self.records = list(records)
        self.finished = [r for r in self.records if r["event"] == "run_finished"]
        self.boe_succeeded = set()
        self.boe_failed = set()
        self.boe_abandoned_recorded = set()
        for record in self.finished:
            for job in record["jobs"]:
                if job["job"] == "boe":
                    self.boe_succeeded.update(job["succeeded"])
                    self.boe_failed.update(item["target"] for item in job["failed"])
                    self.boe_abandoned_recorded.update(job.get("abandoned_dates", []))

    def last_success(self, job_name: str) -> Optional[datetime]:
        for record in reversed(self.finished):
            if any(job["job"] == job_name and job["status"] == "success" for job in record["jobs"]):
                return _parse_time(record["finished_at"])
        return None

    def last_attempt_status(self, job_name: str) -> Optional[str]:
        for record in reversed(self.finished):
            for job in record["jobs"]:
                if job["job"] == job_name and job["status"] in ATTEMPTED_STATUSES:
                    return job["status"]
        return None


# --------------------------------------------------------------------- dates

def _madrid(moment: datetime) -> datetime:
    return moment.astimezone(MADRID)


def _fmt(day: date) -> str:
    return day.strftime("%Y%m%d")


def _parse_boe_date(value: str) -> date:
    if not isinstance(value, str) or not BOE_DATE_PATTERN.fullmatch(value):
        raise _JobConfigError("boe_date_invalid")
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        raise _JobConfigError("boe_date_invalid") from None


def _latest_due_boe_date(now: datetime) -> date:
    local = _madrid(now)
    return local.date() if local.hour >= BOE_READY_HOUR else local.date() - timedelta(days=1)


def _abandoned_dates(history: _History, today: date) -> List[str]:
    window_start = _fmt(today - timedelta(days=BOE_WINDOW_DAYS - 1))
    lookback = _fmt(today - timedelta(days=ABANDONED_LOOKBACK_DAYS))
    return sorted(d for d in history.boe_failed - history.boe_succeeded if lookback <= d < window_start)


def _pending_boe_dates(history: _History, now: datetime, force: bool,
                       explicit: Sequence[str]) -> List[str]:
    today = _madrid(now).date()
    end = _latest_due_boe_date(now)
    window_start = today - timedelta(days=BOE_WINDOW_DAYS - 1)
    if history.boe_succeeded:
        last = _parse_boe_date(max(history.boe_succeeded))
        start = max(last + timedelta(days=1), window_start)
    else:
        start = end
    pending = set()
    day = start
    while day <= end:
        if day.weekday() != 6:  # BOE publishes no Sunday sumario.
            pending.add(_fmt(day))
        day += timedelta(days=1)
    for failed in history.boe_failed - history.boe_succeeded:
        if _fmt(window_start) <= failed <= _fmt(end):
            pending.add(failed)
    if force and end == today and today.weekday() != 6:
        pending.add(_fmt(today))
    oldest = today - timedelta(days=BOE_MANUAL_MAX_AGE_DAYS)
    for value in explicit:
        parsed = _parse_boe_date(value)
        if parsed > today or parsed < oldest:
            raise _JobConfigError("boe_date_invalid")
        pending.add(_fmt(parsed))
    return sorted(pending)


def _boja_years(history: _History, now: datetime) -> List[int]:
    year = _madrid(now).year
    last = history.last_success("boja")
    if last is not None and _madrid(last).year < year:
        return list(range(year - BOJA_MAX_YEARS + 1, year + 1))
    return [year]


# ----------------------------------------------------------------------- jobs

def _job_record(name: str, status: str, **extra: Any) -> Dict[str, Any]:
    record = {"job": name, "status": status, "attempts": 0, "backoff_seconds": [],
              "targets": [], "succeeded": [], "failed": []}
    record.update(extra)
    return record


def _retry(name: str, targets: Sequence[Any], attempt_once: Callable[[List[Any]], Dict[Any, Optional[str]]],
           sleep: Callable[[float], None]) -> Dict[str, Any]:
    """Run ``attempt_once`` on targets, retrying only failed targets with fixed backoff.

    ``attempt_once`` returns ``{target: None}`` on success or ``{target: failure}``.
    """
    remaining = list(targets)
    results: Dict[Any, Optional[str]] = {}
    attempts = 0
    backoffs: List[int] = []
    while remaining and attempts < MAX_ATTEMPTS[name]:
        if attempts:
            delay = BACKOFF_SECONDS[attempts - 1]
            backoffs.append(delay)
            sleep(delay)
        attempts += 1
        outcome = attempt_once(remaining)
        results.update(outcome)
        remaining = [target for target in remaining if outcome.get(target) is not None]
    succeeded = [str(t) for t in targets if results.get(t) is None and t in results]
    failed = [{"target": str(t), "failure": results[t]} for t in targets if results.get(t) is not None]
    return {"status": "failure" if failed else "success", "attempts": attempts, "backoff_seconds": backoffs,
            "targets": [str(t) for t in targets], "succeeded": succeeded, "failed": failed}


def _load_monitor_sources(monitor_config: Optional[Path]) -> List[Dict[str, str]]:
    if monitor_config is None:
        raise _JobConfigError("monitor_config_missing")
    try:
        config = json.loads(Path(monitor_config).read_text(encoding="utf-8"))
        if not isinstance(config, dict) or set(config) != {"sources"}:
            raise source_monitor.MonitorError("configuration must contain exactly a sources array")
        return source_monitor.validate_sources(config["sources"])
    except (OSError, UnicodeDecodeError, ValueError):
        raise _JobConfigError("monitor_config_invalid") from None


def _run_monitor(state_dir: Path, monitor_config: Optional[Path], now: datetime,
                 sleep: Callable[[float], None]) -> Dict[str, Any]:
    sources = _load_monitor_sources(monitor_config)
    state_path = state_dir / MONITOR_STATE_NAME
    try:
        source_monitor._read_state(state_path)
    except (OSError, ValueError):
        raise _JobConfigError("monitor_state_invalid") from None
    by_id = {source["id"]: source for source in sources}
    changed = set()

    def attempt(ids: List[str]) -> Dict[str, Optional[str]]:
        try:
            report = source_monitor.scan([by_id[i] for i in ids], state_path, now)
        except (OSError, ValueError):
            raise _JobConfigError("monitor_state_invalid") from None
        finally:
            _restrict(state_path)
        outcome = {}
        for entry in report["sources"]:
            if entry["status"] == "success":
                outcome[entry["id"]] = None
                if entry["changed"]:
                    changed.add(entry["id"])
            else:
                outcome[entry["id"]] = entry["failure"]
        return outcome

    result = _retry("monitor", list(by_id), attempt, sleep)
    return _job_record("monitor", **result, changed=len(changed))


def _discovery_config(state_dir: Path, run_id: str, registry: str, value: str) -> Path:
    meta = source_discovery.REGISTRIES[registry]
    url = meta["url"].format(date=value, year=value)
    config = {"schema_version": source_discovery.CONFIG_VERSION,
              "registries": [{"id": registry, "issuer": meta["issuer"], "format": meta["format"], "url": url}]}
    path = state_dir / ".discovery-config-{}.json".format(run_id)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False)
    return path


def _run_discovery(name: str, targets: Sequence[str], state_dir: Path, run_id: str, now: datetime,
                   sleep: Callable[[float], None]) -> Dict[str, Any]:
    state_path = state_dir / DISCOVERY_STATE_NAME
    try:
        source_discovery._load_state(state_path)
    except (OSError, ValueError):
        raise _JobConfigError("discovery_state_invalid") from None
    observations = [0]

    def attempt(values: List[str]) -> Dict[str, Optional[str]]:
        outcome: Dict[str, Optional[str]] = {}
        for value in values:
            config_path = _discovery_config(state_dir, run_id, name, value)
            try:
                report = source_discovery.discover(config_path, state_path, now)
            except (OSError, ValueError):
                raise _JobConfigError("discovery_state_invalid") from None
            finally:
                config_path.unlink()
                _restrict(state_path)
            entry = next(item for item in report["registries"] if item["registry_id"] == name)
            if entry["status"] == "checked":
                outcome[value] = None
                observations[0] += entry["new_or_changed_observations"]
            else:
                outcome[value] = entry["failure"]
        return outcome

    result = _retry(name, list(targets), attempt, sleep)
    return {**result, "new_or_changed_observations": observations[0]}


# ------------------------------------------------------------------------ run

def _new_run_id(now: datetime) -> str:
    return "run-{}-{}".format(now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), secrets.token_hex(4))


def _run_outcome(jobs: Iterable[Mapping[str, Any]]) -> str:
    statuses = [job["status"] for job in jobs]
    if "config_error" in statuses:
        return "config_error"
    if "failure" in statuses:
        return "failure"
    if "success" in statuses:
        return "success"
    return "nothing_due"


def run_updates(state_dir: Path, monitor_config: Optional[Path] = None, jobs: Optional[Sequence[str]] = None,
                force: bool = False, boe_dates: Sequence[str] = (), trigger: str = "manual",
                now: Optional[datetime] = None, sleep: Callable[[float], None] = time.sleep,
                run_id: Optional[str] = None) -> Dict[str, Any]:
    """Run due jobs under the state-directory lock and return the run report.

    Raises ``SchedulerConfigError`` for run-level errors (nothing is fetched or
    written to the ledger) and ``LockedError`` when another run is active.
    """
    selected = list(JOBS) if not jobs else [job for job in JOBS if job in set(jobs)]
    if jobs and (set(jobs) - set(JOBS)):
        raise SchedulerConfigError("job_invalid")
    if trigger not in TRIGGERS:
        raise SchedulerConfigError("trigger_invalid")
    clock = (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
    resolved = _resolve_state_dir(state_dir)
    try:
        resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        raise SchedulerConfigError("state_dir_unusable") from None
    ledger_path = resolved / LEDGER_NAME
    with _RunLock(resolved):
        history = _History(read_ledger(ledger_path))
        started = clock().astimezone(timezone.utc)
        run_id = run_id or _new_run_id(started)
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise SchedulerConfigError("run_id_invalid")
        base = {"schema_version": LEDGER_SCHEMA, "run_id": run_id, "trigger": trigger,
                "started_at": started.isoformat()}
        _append_ledger(ledger_path, {**base, "event": "run_started", "jobs": selected, "forced": bool(force)})
        job_reports = []
        for name in JOBS:
            job_reports.append(_dispatch(name, selected, history, resolved, monitor_config, force,
                                         boe_dates, run_id, started, sleep))
        finished = {**base, "event": "run_finished", "finished_at": clock().astimezone(timezone.utc).isoformat(),
                    "outcome": _run_outcome(job_reports), "jobs": job_reports,
                    "unchecked_registries": list(UNCHECKED_REGISTRIES)}
        _append_ledger(ledger_path, finished)
        status = evaluate_status(ledger_path, clock())
    return {**finished, "status": status}


def _dispatch(name: str, selected: Sequence[str], history: _History, state_dir: Path,
              monitor_config: Optional[Path], force: bool, boe_dates: Sequence[str], run_id: str,
              now: datetime, sleep: Callable[[float], None]) -> Dict[str, Any]:
    if name not in selected:
        return _job_record(name, "not_selected")
    extra: Dict[str, Any] = {}
    try:
        if name == "monitor":
            last = history.last_success("monitor")
            if not force and last is not None and now - last < MONITOR_DUE_AFTER:
                return _job_record(name, "not_due", changed=0)
            return _run_monitor(state_dir, monitor_config, now, sleep)
        if name == "boe":
            today = _madrid(now).date()
            abandoned = [d for d in _abandoned_dates(history, today) if d not in history.boe_abandoned_recorded]
            extra = {"new_or_changed_observations": 0, "abandoned_dates": abandoned}
            targets = _pending_boe_dates(history, now, force, boe_dates)
            if not targets:
                return _job_record(name, "not_due", **extra)
            result = _run_discovery("boe", targets, state_dir, run_id, now, sleep)
            return _job_record(name, **result, abandoned_dates=abandoned)
        extra = {"new_or_changed_observations": 0}
        last = history.last_success("boja")
        if not force and last is not None and now - last < BOJA_DUE_AFTER:
            return _job_record(name, "not_due", **extra)
        years = [str(year) for year in _boja_years(history, now)]
        return _job_record(name, **_run_discovery("boja", years, state_dir, run_id, now, sleep))
    except _JobConfigError as error:
        return _job_record(name, "config_error", error=error.code, **extra)


# --------------------------------------------------------------------- status

def evaluate_status(ledger_path: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Evaluate alerts and warnings from the ledger. Raises ``SchedulerConfigError`` on a bad ledger."""
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    history = _History(read_ledger(Path(ledger_path)))
    alerts: List[str] = []
    jobs: Dict[str, Any] = {}
    last_run = None
    if not history.records:
        alerts.append("never_run")
    else:
        started = [r for r in history.records if r["event"] == "run_started"]
        finished_ids = {r["run_id"] for r in history.finished}
        latest = started[-1] if started else history.records[-1]
        latest_started_at = _parse_time(latest["started_at"])
        if moment - latest_started_at > MISSED_RUN_AFTER:
            alerts.append("missed_run")
        if latest["run_id"] not in finished_ids and moment - latest_started_at > INTERRUPTED_AFTER:
            alerts.append("interrupted_run")
        finished_record = next((r for r in reversed(history.finished) if r["run_id"] == latest["run_id"]), None)
        last_run = {"run_id": latest["run_id"], "trigger": latest["trigger"], "started_at": latest["started_at"],
                    "finished_at": finished_record["finished_at"] if finished_record else None,
                    "outcome": finished_record["outcome"] if finished_record else None}
        for name in JOBS:
            if history.last_attempt_status(name) in ("failure", "config_error"):
                alerts.append("last_run_failed:{}".format(name))
        for name in JOBS:
            last = history.last_success(name)
            if last is None or moment - last > STALE_AFTER[name]:
                alerts.append("stale:{}".format(name))
    for name in JOBS:
        last = history.last_success(name)
        jobs[name] = {"last_success_at": last.isoformat() if last else None,
                      "last_attempt_status": history.last_attempt_status(name)}
    abandoned = _abandoned_dates(history, _madrid(moment).date())
    warnings = (["abandoned_boe_dates"] if abandoned else []) + ["unchecked:" + r for r in UNCHECKED_REGISTRIES]
    return {"schema_version": STATUS_SCHEMA, "evaluated_at": moment.isoformat(), "healthy": not alerts,
            "alerts": alerts, "warnings": warnings, "abandoned_boe_dates": abandoned, "last_run": last_run,
            "jobs": jobs,
            "unchecked_registries": [{"registry_id": r, "status": "unchecked",
                                      "failure": "no_verified_machine_readable_registry"}
                                     for r in UNCHECKED_REGISTRIES],
            "freshness_claim": "none"}


def status_for_state_dir(state_dir: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    resolved = _resolve_state_dir(state_dir)
    return evaluate_status(resolved / LEDGER_NAME, now)


def exit_code_for_run(report: Mapping[str, Any]) -> int:
    if report["outcome"] == "config_error":
        return 2
    if report["outcome"] == "failure" or report["status"]["alerts"]:
        return 1
    return 0
