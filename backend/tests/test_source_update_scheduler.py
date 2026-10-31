"""Offline tests for the best-effort source-update scheduler.

Every upstream call goes through recorded fakes; sockets are blocked so no test
can reach an official site.
"""
import fcntl
import hashlib
import importlib.util
import json
import os
import socket
import stat
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path

import pytest

from app import source_discovery, source_monitor
from app import source_update_scheduler as scheduler

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "backend" / "scripts" / "run_source_updates.py"
NOW = datetime(2026, 10, 28, 9, 30, tzinfo=timezone.utc)  # 10:30 Madrid, Wednesday
SOURCES = [
    {"id": "boe-api", "url": "https://www.boe.es/datosabiertos/api/api.php", "format": "json"},
    {"id": "boja-rss", "url": "https://www.juntadeandalucia.es/boja/distribucion/s51.xml", "format": "rss"},
]
FEED = b'<rss version="2.0"><channel><title>Official feed</title></channel></rss>'
SENTINEL = "SECRET-SENTINEL"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _forbid(*args, **kwargs):
        raise AssertionError("network access is forbidden in scheduler tests")
    monkeypatch.setattr(socket, "socket", _forbid)
    monkeypatch.setattr(socket, "create_connection", _forbid)


class Upstream:
    """Recording fakes for ``source_monitor._request`` and ``source_discovery._fetch``."""

    def __init__(self, monkeypatch):
        self.monitor_calls = []
        self.fetch_calls = []
        self.monitor_always_fail = set()
        self.boe_failures_left = 0
        self.boe_always_fail = False
        self.boja_always_fail = False
        monkeypatch.setattr(source_monitor, "_request", self.request)
        monkeypatch.setattr(source_discovery, "_fetch", self.fetch)

    @property
    def calls(self):
        return len(self.monitor_calls) + len(self.fetch_calls)

    def request(self, source, previous):
        self.monitor_calls.append(source["id"])
        if source["id"] in self.monitor_always_fail:
            raise OSError(SENTINEL)
        payload = FEED if source["format"] == "rss" else b'{"status": "ok"}'
        return 200, Message(), payload

    def fetch(self, url, accept):
        self.fetch_calls.append(url)
        if "/sumario/" in url:
            if self.boe_always_fail:
                raise OSError(SENTINEL)
            if self.boe_failures_left:
                self.boe_failures_left -= 1
                raise OSError(SENTINEL)
            day = url.rsplit("/", 1)[1]
            return ("<response><status><code>200</code></status><data><item>"
                    "<identificador>BOE-A-{0}-1</identificador><titulo>Title {0}</titulo>"
                    "<url_pdf>https://www.boe.es/boe/dias/{0}/pdfs/x.pdf</url_pdf>"
                    "</item></data></response>").format(day).encode()
        if self.boja_always_fail:
            raise OSError(SENTINEL)
        year = url.split("year=")[1].split("&")[0]
        if "/calendar" in url:
            return json.dumps({"columns": [{"name": "number"}, {"name": "date"}],
                               "rows": [[1, "02/01/" + year]]}).encode()
        return json.dumps({"hits": 1, "total_hits": 1, "results": [{
            "id": "boja.{}.1.1".format(year), "summaryNoHtml": "Bulletin " + year,
            "pdf": [{"publicUrl": "https://juntadeandalucia.es/eboja/{}/1/doc.pdf".format(year)}]}]}).encode()


@pytest.fixture
def upstream(monkeypatch):
    return Upstream(monkeypatch)


@pytest.fixture
def setup(tmp_path):
    state = tmp_path / "state"
    config = tmp_path / "source-monitor.json"
    config.write_text(json.dumps({"sources": SOURCES}))
    return state, config


class Sleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


def run(state, config, now=NOW, sleep=None, **kwargs):
    return scheduler.run_updates(state, monitor_config=config, now=now, sleep=sleep or Sleep(), **kwargs)


def ledger(state):
    return [json.loads(line) for line in (state / scheduler.LEDGER_NAME).read_text().splitlines()]


def job(report, name):
    return next(item for item in report["jobs"] if item["job"] == name)


def write_ledger(state, records):
    state.mkdir(parents=True, exist_ok=True)
    (state / scheduler.LEDGER_NAME).write_text("".join(json.dumps(r) + "\n" for r in records))


def finished(at, jobs, run_id="run-20261001T000000Z-00000000", outcome="success"):
    stamp = at.isoformat()
    return [
        {"schema_version": scheduler.LEDGER_SCHEMA, "event": "run_started", "run_id": run_id,
         "trigger": "manual", "started_at": stamp, "jobs": list(scheduler.JOBS), "forced": False},
        {"schema_version": scheduler.LEDGER_SCHEMA, "event": "run_finished", "run_id": run_id,
         "trigger": "manual", "started_at": stamp, "finished_at": stamp, "outcome": outcome,
         "jobs": jobs, "unchecked_registries": ["fega", "mapa"]},
    ]


def job_entry(name, status="success", succeeded=(), failed=(), **extra):
    return {"job": name, "status": status, "attempts": 1, "backoff_seconds": [], "targets": [],
            "succeeded": list(succeeded), "failed": [{"target": t, "failure": "OSError"} for t in failed],
            **extra}


def healthy_jobs(boe_dates=("20261027",)):
    return [job_entry("monitor", succeeded=["boe-api", "boja-rss"]),
            job_entry("boe", succeeded=boe_dates), job_entry("boja", succeeded=["2026"])]


def knowledge_hashes():
    return {name: hashlib.sha256((ROOT / "knowledge" / name).read_bytes()).hexdigest()
            for name in ("source_catalog.json", "passages.json")}


# ------------------------------------------------------------------ due runs

def test_due_run_succeeds_records_ledger_pair_and_keeps_knowledge(setup, upstream):
    state, config = setup
    before = knowledge_hashes()
    report = run(state, config, run_id="run-20261028T093000Z-1a2b3c4d")
    assert report["outcome"] == "success"
    assert scheduler.exit_code_for_run(report) == 0
    assert sorted(upstream.monitor_calls) == ["boe-api", "boja-rss"]
    assert job(report, "boe")["succeeded"] == ["20261028"]
    assert job(report, "boja")["succeeded"] == ["2026"]
    assert any(url.endswith("/sumario/20261028") for url in upstream.fetch_calls)
    assert any("calendar?year=2026" in url for url in upstream.fetch_calls)
    records = ledger(state)
    assert [r["event"] for r in records] == ["run_started", "run_finished"]
    assert {r["run_id"] for r in records} == {"run-20261028T093000Z-1a2b3c4d"}
    assert records[1]["outcome"] == "success"
    assert records[1]["unchecked_registries"] == ["fega", "mapa"]
    assert (state / scheduler.MONITOR_STATE_NAME).is_file()
    assert (state / scheduler.DISCOVERY_STATE_NAME).is_file()
    assert not list(state.glob(".discovery-config-*"))
    assert knowledge_hashes() == before
    assert report["status"]["healthy"] is True


def test_repeat_dispatch_is_idempotent_and_force_does_not_duplicate(setup, upstream):
    state, config = setup
    run(state, config)
    discovery = json.loads((state / scheduler.DISCOVERY_STATE_NAME).read_text())
    calls = upstream.calls
    later = NOW + timedelta(hours=2)
    report = run(state, config, now=later)
    assert upstream.calls == calls
    assert report["outcome"] == "nothing_due"
    assert {j["status"] for j in report["jobs"]} == {"not_due"}
    assert scheduler.exit_code_for_run(report) == 0
    forced = run(state, config, now=later, force=True)
    assert forced["outcome"] == "success"
    assert job(forced, "monitor")["status"] == job(forced, "boja")["status"] == "success"
    assert job(forced, "boe")["succeeded"] == ["20261028"]
    after = json.loads((state / scheduler.DISCOVERY_STATE_NAME).read_text())
    assert len(after["candidates"]) == len(discovery["candidates"])
    assert ({k: v["observations"] for k, v in after["candidates"].items()}
            == {k: v["observations"] for k, v in discovery["candidates"].items()})


# ------------------------------------------------------------------- retries

def test_transient_boe_failure_retries_with_backoff(setup, upstream):
    state, config = setup
    upstream.boe_failures_left = 1
    sleep = Sleep()
    report = run(state, config, sleep=sleep, jobs=["boe"])
    boe = job(report, "boe")
    assert boe["status"] == "success"
    assert boe["attempts"] == 2
    assert boe["backoff_seconds"] == [60]
    assert sleep.calls == [60]


def test_persistent_monitor_failure_retries_only_failed_source(setup, upstream):
    state, config = setup
    run(state, config)
    good_hash = json.loads((state / scheduler.MONITOR_STATE_NAME).read_text())["sources"]["boja-rss"]["content_sha256"]
    upstream.monitor_calls.clear()
    upstream.monitor_always_fail = {"boja-rss"}
    sleep = Sleep()
    report = run(state, config, now=NOW + timedelta(hours=13), sleep=sleep, jobs=["monitor"])
    monitor = job(report, "monitor")
    assert upstream.monitor_calls == ["boe-api", "boja-rss", "boja-rss", "boja-rss"]
    assert sleep.calls == [60, 300]
    assert monitor["status"] == "failure"
    assert monitor["attempts"] == 3
    assert monitor["succeeded"] == ["boe-api"]
    assert monitor["failed"] == [{"target": "boja-rss", "failure": "upstream request failed"}]
    saved = json.loads((state / scheduler.MONITOR_STATE_NAME).read_text())["sources"]
    assert saved["boja-rss"]["content_sha256"] == good_hash
    assert saved["boe-api"]["status"] == "success"
    assert report["outcome"] == "failure"
    assert "last_run_failed:monitor" in report["status"]["alerts"]
    assert scheduler.exit_code_for_run(report) == 1


def test_boja_failure_stops_after_two_attempts(setup, upstream):
    state, config = setup
    upstream.boja_always_fail = True
    sleep = Sleep()
    report = run(state, config, sleep=sleep, jobs=["boja"])
    boja = job(report, "boja")
    assert boja["status"] == "failure"
    assert boja["attempts"] == 2
    assert sleep.calls == [60]
    assert boja["failed"] == [{"target": "2026", "failure": "OSError"}]


# ------------------------------------------------------------- BOE calendar

def test_catch_up_skips_sunday_in_order(setup, upstream):
    state, config = setup
    write_ledger(state, finished(datetime(2026, 10, 23, 10, tzinfo=timezone.utc),
                                 healthy_jobs(("20261023",))))
    report = run(state, config, jobs=["boe"])
    assert job(report, "boe")["targets"] == ["20261024", "20261026", "20261027", "20261028"]
    sumario = [url.rsplit("/", 1)[1] for url in upstream.fetch_calls if "/sumario/" in url]
    assert sumario == ["20261024", "20261026", "20261027", "20261028"]


def test_catch_up_is_capped_to_fourteen_days(setup, upstream):
    state, config = setup
    write_ledger(state, finished(datetime(2026, 9, 1, tzinfo=timezone.utc), healthy_jobs(("20260901",))))
    targets = job(run(state, config, jobs=["boe"]), "boe")["targets"]
    assert targets[0] == "20261015" and targets[-1] == "20261028"
    assert "20261018" not in targets and "20261025" not in targets
    assert len(targets) == 12


def test_today_not_due_before_nine_madrid(setup, upstream):
    state, config = setup
    early = datetime(2026, 10, 28, 7, 30, tzinfo=timezone.utc)  # 08:30 Madrid
    write_ledger(state, finished(datetime(2026, 10, 26, 10, tzinfo=timezone.utc), healthy_jobs(("20261026",))))
    assert job(run(state, config, now=early, jobs=["boe"]), "boe")["targets"] == ["20261027"]


def test_failed_date_is_retried_then_abandoned_once(setup, upstream):
    state, config = setup
    records = finished(datetime(2026, 10, 10, 10, tzinfo=timezone.utc),
                       [job_entry("boe", status="failure", succeeded=["20261009"], failed=["20261010"])])
    records += finished(datetime(2026, 10, 12, 10, tzinfo=timezone.utc),
                        [job_entry("boe", succeeded=["20261012"])], run_id="run-20261012T100000Z-00000001")
    write_ledger(state, records)
    inside = datetime(2026, 10, 13, 9, 30, tzinfo=timezone.utc)
    upstream.boe_always_fail = True
    report = run(state, config, now=inside, jobs=["boe"])
    assert job(report, "boe")["targets"] == ["20261010", "20261013"]
    upstream.boe_always_fail = False
    # By 2026-10-28 both failed dates have left the 14-day window (starts 20261015).
    second = run(state, config, jobs=["boe"])
    assert job(second, "boe")["abandoned_dates"] == ["20261010", "20261013"]
    assert job(second, "boe")["targets"][0] == "20261015"
    third = run(state, config, now=NOW + timedelta(hours=1), jobs=["boe"])
    assert job(third, "boe")["status"] == "not_due"
    assert job(third, "boe")["abandoned_dates"] == []
    status = scheduler.evaluate_status(state / scheduler.LEDGER_NAME, NOW)
    assert status["abandoned_boe_dates"] == ["20261010", "20261013"]
    assert "abandoned_boe_dates" in status["warnings"]
    rescued = run(state, config, now=NOW + timedelta(hours=2), jobs=["boe"], boe_dates=["20261010"])
    assert job(rescued, "boe")["succeeded"] == ["20261010"]
    assert scheduler.evaluate_status(state / scheduler.LEDGER_NAME, NOW)["abandoned_boe_dates"] == ["20261013"]


@pytest.mark.parametrize("value", ["20261029", "20260801", "2026-10-01", "20261340"])
def test_invalid_explicit_boe_date_is_config_error_without_fetch(setup, upstream, value):
    state, config = setup
    report = run(state, config, jobs=["boe"], boe_dates=[value])
    assert job(report, "boe")["status"] == "config_error"
    assert job(report, "boe")["error"] == "boe_date_invalid"
    assert upstream.calls == 0
    assert scheduler.exit_code_for_run(report) == 2


def test_explicit_sunday_boe_date_is_allowed(setup, upstream):
    state, config = setup
    report = run(state, config, jobs=["boe"], boe_dates=["20261025"])
    assert job(report, "boe")["targets"] == ["20261025", "20261028"]


def test_boja_year_rollover_scans_both_years(setup, upstream):
    state, config = setup
    write_ledger(state, finished(datetime(2026, 12, 28, 10, tzinfo=timezone.utc), healthy_jobs(("20261228",))))
    report = run(state, config, now=datetime(2027, 1, 5, 9, 30, tzinfo=timezone.utc), jobs=["boja"])
    assert job(report, "boja")["targets"] == ["2026", "2027"]
    assert job(report, "boja")["status"] == "success"


# -------------------------------------------------------------------- status

def test_status_alerts(tmp_path):
    state = tmp_path / "state"
    path = state / scheduler.LEDGER_NAME
    status = scheduler.evaluate_status(path, NOW)
    assert status["alerts"] == ["never_run"] and status["healthy"] is False

    write_ledger(state, finished(NOW - timedelta(hours=31), healthy_jobs()))
    assert "missed_run" in scheduler.evaluate_status(path, NOW)["alerts"]

    records = finished(NOW - timedelta(hours=20), healthy_jobs())
    records.append({**records[0], "run_id": "run-20261028T063000Z-00000002",
                    "started_at": (NOW - timedelta(hours=3)).isoformat()})
    write_ledger(state, records)
    assert "interrupted_run" in scheduler.evaluate_status(path, NOW)["alerts"]

    write_ledger(state, finished(NOW - timedelta(days=9), [job_entry("boja", succeeded=["2026"])])
                 + finished(NOW - timedelta(hours=1), [job_entry("monitor"), job_entry("boe", succeeded=["20261028"])],
                            run_id="run-20261028T083000Z-00000003"))
    alerts = scheduler.evaluate_status(path, NOW)["alerts"]
    assert alerts == ["stale:boja"]

    write_ledger(state, finished(NOW - timedelta(hours=1), [job_entry("monitor", status="failure", failed=["boe-api"]),
                                                            job_entry("boe", succeeded=["20261028"]),
                                                            job_entry("boja", succeeded=["2026"])], outcome="failure"))
    assert scheduler.evaluate_status(path, NOW)["alerts"] == ["last_run_failed:monitor", "stale:monitor"]

    write_ledger(state, finished(NOW - timedelta(hours=1), healthy_jobs()))
    healthy = scheduler.evaluate_status(path, NOW)
    assert healthy["healthy"] is True and healthy["alerts"] == []
    for report in (status, healthy):
        assert report["freshness_claim"] == "none"
        assert [r["registry_id"] for r in report["unchecked_registries"]] == ["fega", "mapa"]
        assert {"unchecked:fega", "unchecked:mapa"} <= set(report["warnings"])


# --------------------------------------------------------------- fail closed

def test_invalid_monitor_config_is_config_error_without_retry(setup, upstream):
    state, config = setup
    config.write_text(json.dumps({"sources": [{"id": "x", "url": "https://evil.example/feed", "format": "rss"}]}))
    sleep = Sleep()
    report = run(state, config, sleep=sleep)
    assert job(report, "monitor")["status"] == "config_error"
    assert job(report, "monitor")["error"] == "monitor_config_invalid"
    assert upstream.monitor_calls == [] and sleep.calls == []
    assert job(report, "boe")["status"] == "success"
    assert report["outcome"] == "config_error"
    assert scheduler.exit_code_for_run(report) == 2


def test_missing_monitor_config_is_config_error(setup, upstream):
    state, _ = setup
    report = run(state, None, jobs=["monitor"])
    assert job(report, "monitor")["error"] == "monitor_config_missing"


def test_invalid_states_are_config_errors_without_fetch(setup, upstream):
    state, config = setup
    state.mkdir()
    (state / scheduler.MONITOR_STATE_NAME).write_text('{"schema_version": "wrong"}')
    (state / scheduler.DISCOVERY_STATE_NAME).write_text("not json")
    sleep = Sleep()
    report = run(state, config, sleep=sleep)
    assert [job(report, n)["error"] for n in ("monitor", "boe", "boja")] == [
        "monitor_state_invalid", "discovery_state_invalid", "discovery_state_invalid"]
    assert upstream.calls == 0 and sleep.calls == []
    assert scheduler.exit_code_for_run(report) == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode-000 files")
def test_unreadable_state_file_is_config_error(setup, upstream):
    state, config = setup
    state.mkdir()
    path = state / scheduler.DISCOVERY_STATE_NAME
    path.write_text("{}")
    path.chmod(0)
    try:
        report = run(state, config, jobs=["boe"])
    finally:
        path.chmod(0o600)
    assert job(report, "boe")["status"] == "config_error"
    assert upstream.calls == 0


def test_state_dir_inside_repository_is_refused(upstream):
    with pytest.raises(scheduler.SchedulerConfigError) as error:
        scheduler.run_updates(ROOT / "backend" / "var" / "source-updates", now=NOW, sleep=Sleep())
    assert error.value.code == "state_dir_inside_repository"
    assert not (ROOT / "backend" / "var" / "source-updates").exists()
    with pytest.raises(scheduler.SchedulerConfigError):
        scheduler.status_for_state_dir(ROOT / "knowledge", NOW)
    assert upstream.calls == 0


def test_corrupt_ledger_refuses_run_and_status(setup, upstream):
    state, config = setup
    write_ledger(state, finished(NOW - timedelta(hours=1), healthy_jobs()))
    with (state / scheduler.LEDGER_NAME).open("a") as handle:
        handle.write("{not json\n")
    before = (state / scheduler.LEDGER_NAME).read_bytes()
    with pytest.raises(scheduler.SchedulerConfigError) as error:
        run(state, config)
    assert error.value.code == "ledger_invalid"
    with pytest.raises(scheduler.SchedulerConfigError):
        scheduler.evaluate_status(state / scheduler.LEDGER_NAME, NOW)
    assert (state / scheduler.LEDGER_NAME).read_bytes() == before
    assert upstream.calls == 0


def test_unknown_ledger_event_and_oversized_ledger_are_refused(setup, monkeypatch):
    state, _ = setup
    records = finished(NOW, healthy_jobs())
    records[0]["event"] = "something_else"
    write_ledger(state, records)
    with pytest.raises(scheduler.SchedulerConfigError):
        scheduler.evaluate_status(state / scheduler.LEDGER_NAME, NOW)
    write_ledger(state, finished(NOW, healthy_jobs()))
    monkeypatch.setattr(scheduler, "MAX_LEDGER_BYTES", 10)
    with pytest.raises(scheduler.SchedulerConfigError) as error:
        scheduler.evaluate_status(state / scheduler.LEDGER_NAME, NOW)
    assert error.value.code == "ledger_too_large"


def test_lock_held_exits_three_without_request_or_ledger_write(setup, upstream, capsys):
    state, config = setup
    state.mkdir()
    holder = os.open(str(state / scheduler.LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        code = load_cli().main(["run", "--state-dir", str(state), "--monitor-config", str(config)],
                               now=NOW, sleep=Sleep())
    finally:
        os.close(holder)
    assert code == 3
    assert json.loads(capsys.readouterr().err) == {"error": "locked"}
    assert not (state / scheduler.LEDGER_NAME).exists()
    assert upstream.calls == 0


# ------------------------------------------------------------------- privacy

def test_ledger_and_report_contain_no_url_message_or_path_and_are_private(setup, upstream):
    state, config = setup
    upstream.monitor_always_fail = {"boe-api"}
    upstream.boe_always_fail = True
    upstream.boja_always_fail = True
    report = run(state, config)
    text = (state / scheduler.LEDGER_NAME).read_text() + json.dumps(report)
    for forbidden in (SENTINEL, "https://", "http://", str(state), str(config)):
        assert forbidden not in text
    assert stat.S_IMODE(os.stat(state / scheduler.LEDGER_NAME).st_mode) == 0o600
    for name in (scheduler.MONITOR_STATE_NAME, scheduler.DISCOVERY_STATE_NAME, scheduler.LOCK_NAME):
        assert stat.S_IMODE(os.stat(state / name).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(state).st_mode) == 0o700


# ----------------------------------------------------------------------- CLI

def load_cli():
    spec = importlib.util.spec_from_file_location("run_source_updates_cli", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_run_and_status(setup, upstream, capsys):
    state, config = setup
    cli = load_cli()
    assert cli.main(["status", "--state-dir", str(state)], now=NOW) == 1
    assert json.loads(capsys.readouterr().out)["alerts"] == ["never_run"]
    code = cli.main(["run", "--state-dir", str(state), "--monitor-config", str(config), "--trigger", "systemd"],
                    now=NOW, sleep=Sleep())
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["trigger"] == "systemd" and out["outcome"] == "success" and out["status"]["healthy"]
    assert cli.main(["status", "--state-dir", str(state)], now=NOW + timedelta(hours=1)) == 0
    capsys.readouterr()
    assert cli.main(["run", "--state-dir", str(ROOT / "knowledge" / "x")], now=NOW, sleep=Sleep()) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "state_dir_inside_repository"}
    with pytest.raises(SystemExit) as error:
        cli.main(["run", "--state-dir", str(state), "--job", "monitor", "--boe-date", "20261027"])
    assert error.value.code == 2


def test_cli_failure_exit_one(setup, upstream, capsys):
    state, config = setup
    upstream.boja_always_fail = True
    code = load_cli().main(["run", "--state-dir", str(state), "--monitor-config", str(config)],
                           now=NOW, sleep=Sleep())
    assert code == 1
    assert json.loads(capsys.readouterr().out)["outcome"] == "failure"


# -------------------------------------------------------- repository safety

def test_no_repository_workflow_schedules_or_invokes_the_scheduler():
    workflows = sorted((ROOT / ".github" / "workflows").glob("*"))
    assert workflows
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        assert "schedule:" not in text, path.name
        assert "run_source_updates" not in text, path.name


def _directives(path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def test_systemd_templates_match_the_documented_decisions():
    systemd = ROOT / "backend" / "deploy" / "systemd"
    timer_text = (systemd / "manijero-source-updates.timer").read_text(encoding="utf-8")
    service_text = (systemd / "manijero-source-updates.service").read_text(encoding="utf-8")
    assert "TEMPLATE, NOT REHEARSED, NOT INSTALLED OR ENABLED" in timer_text
    assert "TEMPLATE, NOT REHEARSED, NOT INSTALLED OR ENABLED" in service_text
    timer = _directives(systemd / "manijero-source-updates.timer")
    assert "OnCalendar=*-*-* 10:20:00 Europe/Madrid" in timer
    assert "Persistent=true" in timer and "RandomizedDelaySec=30m" in timer
    service = _directives(systemd / "manijero-source-updates.service")
    assert not [d for d in service if d.startswith(("EnvironmentFile=", "Environment=", "OnFailure="))]
    assert [d for d in service if d.startswith("ReadWritePaths=")] == ["ReadWritePaths=/var/lib/manijero/source-updates"]
    assert "TimeoutStartSec=90min" in service and "Type=oneshot" in service
    assert "SyslogIdentifier=manijero-source-updates" in service
    exec_start = next(d for d in service if d.startswith("ExecStart="))
    assert "run_source_updates.py run --trigger systemd --state-dir /var/lib/manijero/source-updates" in exec_start
    assert "pilot.env" not in service_text


def test_example_monitor_config_is_valid():
    config = json.loads((ROOT / "backend" / "deploy" / "source-monitor.json.example").read_text(encoding="utf-8"))
    assert set(config) == {"sources"}
    assert [s["id"] for s in source_monitor.validate_sources(config["sources"])] == ["boe-api", "boja-rss"]
