"""Offline tests for the knowledge update orchestrator.

Steps are faked (a scripted runner stands in for the child processes), the clock and the sleep are
fakes, sockets are blocked, and launchctl is an in-memory fake. No real official site, model,
launchctl, or token is ever touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import socket
import stat
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app import knowledge_ops as ops

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = REPO_ROOT / "knowledge"
START = datetime(2026, 11, 8, 9, 20, tzinfo=timezone.utc)  # 10:20 in Madrid
MARKER = "TITLE-MARKER-Ayuda-secreta"
EXCEPTION_MARKER = "EXCEPTION-MARKER-ruta-privada"
CANDIDATE_IDS = [hashlib.sha256(name.encode()).hexdigest() for name in ("a", "b")]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in knowledge-ops tests")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)


class FakeClock:
    def __init__(self, now: datetime = START) -> None:
        self.current = now
        self.sleeps: List[float] = []

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)


class FakeLaunchctl:
    def __init__(self, present: bool = True) -> None:
        self._present = present
        self.loaded = False
        self.calls: List[str] = []

    def present(self) -> bool:
        return self._present

    def is_loaded(self) -> bool:
        self.calls.append("print")
        return self.loaded

    def bootstrap(self, plist: Path) -> bool:
        self.calls.append("bootstrap")
        self.loaded = True
        return True

    def bootout(self) -> bool:
        self.calls.append("bootout")
        self.loaded = False
        return True


def candidate(identifier: str) -> Dict[str, str]:
    return {
        "candidate_id": identifier, "issuer": "BOE", "registry_id": "boe",
        "registry_url": "https://www.boe.es/datosabiertos/api/boe/sumario/20261107",
        "publication_url": "https://www.boe.es/boe/dias/2026/11/07/pdfs/BOE-A-2026-1.pdf",
        "title": MARKER, "stable_identity": "BOE-A-2026-1", "version_hash": "v1", "review_status": "pending",
    }


class FakeRunner:
    """Stands in for the child processes. ``script[step]`` lists one action per attempt (the last repeats)."""

    def __init__(self, clock: FakeClock, home: Path, script: Optional[Dict[str, List[Any]]] = None) -> None:
        self.clock, self.home, self.script = clock, home, script or {}
        self.calls: List[Tuple[str, float]] = []

    def attempts(self, step: str) -> int:
        return sum(1 for name, _ in self.calls if name == step)

    def run(self, step: str, run_dir: Path, timeout_seconds: float) -> ops.RunnerResult:
        self.calls.append((step, timeout_seconds))
        actions = self.script.get(step) or ["ok"]
        action = actions[min(self.attempts(step), len(actions)) - 1]
        if step == "discover":
            self._write_discovery()
        if action == "hang":
            self.clock.advance(timeout_seconds)
            return ops.RunnerResult(timed_out=True)
        if isinstance(action, tuple):
            kind, *rest = action
            if kind == "late_fail":
                self.clock.advance(rest[0])
            code = rest[-1]
            ops.write_child_result(run_dir, step, failure=ops.StepFailure(code, usable=kind == "fail_usable",
                                                                          counts={"new_candidates": 2} if step == "discover" else {}))
            return ops.RunnerResult(timed_out=False)
        self._succeed(step, run_dir)
        return ops.RunnerResult(timed_out=False)

    def _write_discovery(self) -> None:
        path = self.home / "source-updates" / "official-discovery-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": "official-discovery-state-v1", "registries": {},
            "candidates": {identifier: candidate(identifier) for identifier in CANDIDATE_IDS},
        }), encoding="utf-8")

    def _succeed(self, step: str, run_dir: Path) -> None:
        if step == "review":
            assert ops.execute_step("review", run_dir, REPO_ROOT) == 0
            return
        reports = run_dir / "reports"
        counts: Dict[str, int] = {
            "discover": {"new_candidates": 2, "pages_changed": 1},
            "classify": {"relevant": 1, "unsure": 1, "not_relevant": 0},
            "ingest": {"documents_ingested": 2, "documents_failed": 0},
            "impact": {"impact_findings": 1},
            "validity": {"validity_proposals": 1},
        }[step]
        if step == "impact":
            (reports / "impact.json").write_text(json.dumps({"candidates": [
                {"candidate_id": CANDIDATE_IDS[0], "review": {"required": True}},
                {"candidate_id": CANDIDATE_IDS[1], "review": {"required": False}},
            ]}), encoding="utf-8")
        if step == "validity":
            (reports / "validity.json").write_text(json.dumps({"proposals": [{"kind": "review"}]}), encoding="utf-8")
        ops.write_child_result(run_dir, step, counts=counts)


class Harness:
    def __init__(self, tmp_path: Path, script: Optional[Dict[str, List[Any]]] = None) -> None:
        self.home = tmp_path / "knowledge-ops"
        self.home.mkdir(mode=0o700)
        for name in ops.EXAMPLES:
            (self.home / name).write_text('{"sources":[]}', encoding="utf-8")
        self.clock = FakeClock()
        self.runner = FakeRunner(self.clock, self.home, script)
        self.launchctl = FakeLaunchctl()
        self.lines: List[str] = []
        self.ports = ops.Ports(
            home=self.home, repo_root=REPO_ROOT, agents_dir=tmp_path / "LaunchAgents", python=Path(sys.executable),
            clock=self.clock, sleep=self.clock.sleep, runner=self.runner, launchctl=self.launchctl,
            out=self.lines.append,
        )

    def run(self, trigger: str = "manual") -> ops.RunResult:
        return ops.run_cycle(self.ports, trigger)

    def step(self, result: ops.RunResult, name: str) -> Dict[str, Any]:
        return json.loads((result.run_dir / "steps" / (name + ".json")).read_text(encoding="utf-8"))

    def ledger(self) -> List[Dict[str, Any]]:
        return ops.read_ledger(self.home)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def tree_digest(root: Path) -> Dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


# --- 2. A full run stops at review ready ------------------------------------------------------


def test_a_full_run_goes_through_every_step_once_in_order_and_stops_at_review_ready(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    before = tree_digest(KNOWLEDGE)

    result = harness.run()

    assert [name for name, _ in harness.runner.calls] == ["discover", "classify", "ingest", "impact", "validity", "review"]
    assert result.outcome == "review_ready" and result.exit_code == 0
    review = result.run_dir / "review"
    assert (review / "REVIEW.md").is_file()
    ready = json.loads((review / "review-ready.json").read_text(encoding="utf-8"))
    assert ready["published"] is False and ready["requires_owner_approval"] is True
    assert ready["candidate_ids"] == [CANDIDATE_IDS[0]]
    assert set(ready["reports"]) == {"impact.json", "validity.json"}
    for name in ops.STEPS:
        assert harness.step(result, name)["status"] == "done"
    events = harness.ledger()
    assert [event["event"] for event in events] == ["run_started", "run_finished"]
    assert events[1]["outcome"] == "review_ready" and events[0]["trigger"] == "manual"
    assert tree_digest(KNOWLEDGE) == before  # the approved knowledge is untouched
    assert not (harness.home / "releases").exists()
    assert (harness.home / ops.LATEST_SUMMARY_NAME).read_text(encoding="utf-8") == result.summary


def test_the_scheduled_trigger_is_recorded(harness: Harness) -> None:
    harness.run("schedule")
    assert harness.ledger()[0]["trigger"] == "schedule"


def test_the_review_folder_names_ids_and_admission_codes_but_never_titles(harness: Harness) -> None:
    result = harness.run()
    text = (result.run_dir / "review" / "REVIEW.md").read_text(encoding="utf-8")

    assert CANDIDATE_IDS[0] in text and CANDIDATE_IDS[1] not in text
    assert "admission check:" in text and "knowledge_review.py prepare" in text
    assert ops.FIXED_LINE in text
    assert MARKER not in text and "https://" not in text


def test_as_of_is_the_madrid_date_at_run_start(tmp_path: Path) -> None:
    late = Harness(tmp_path)
    late.clock.current = datetime(2026, 11, 8, 23, 30, tzinfo=timezone.utc)  # already Monday 9 in Madrid
    result = late.run()
    assert json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))["as_of"] == "2026-11-09"


def test_files_and_folders_are_private(harness: Harness) -> None:
    result = harness.run()
    for path in (result.run_dir, result.run_dir / "steps", result.run_dir / "review"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700, path
    for path in (harness.home / ops.LEDGER_NAME, harness.home / ops.LATEST_SUMMARY_NAME,
                 result.run_dir / "summary.txt", result.run_dir / "review" / "REVIEW.md"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


# --- 3. Retries, then a reported failure -----------------------------------------------------


def test_a_step_that_fails_once_then_succeeds_reports_two_attempts(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"classify": [("fail", "model_not_running"), "ok"]})
    result = harness.run()

    assert result.outcome == "review_ready"
    assert harness.step(result, "classify")["attempts"] == 2
    assert harness.clock.sleeps == [60]


def test_a_step_that_always_fails_is_tried_three_times_and_reported(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"classify": [("fail", "model_not_running")]})
    result = harness.run()

    assert harness.runner.attempts("classify") == 3 and harness.clock.sleeps == [60, 300]
    report = harness.step(result, "classify")
    assert report["status"] == "failed" and report["attempts"] == 3 and report["code"] == "model_not_running"
    assert "Ollama" in report["what_happened"] and report["first_thing_to_do"].startswith("open Ollama")
    assert report["log"].endswith("knowledge-ops.log")
    assert result.outcome == "failed" and result.exit_code == 1
    assert "failed after 3 tries" in result.summary and "First thing to do: open Ollama" in result.summary
    # classify does not feed ingest: independent steps still run, and the rest is never omitted
    assert harness.step(result, "ingest")["status"] == "done"
    assert harness.step(result, "review")["status"] == "done"


def test_steps_that_need_a_failed_step_are_reported_not_run(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"ingest": [("fail", "step_crashed")]})
    result = harness.run()

    assert harness.runner.attempts("ingest") == 3
    for name in ("impact", "validity", "review"):
        report = harness.step(result, name)
        assert report["status"] == "not_run" and report["reason"] == "earlier_step_failed", name
        assert harness.runner.attempts(name) == 0
    assert harness.step(result, "classify")["status"] == "done"
    assert "Compare them with approved sources: not run (an earlier step failed)." in result.summary


def test_a_step_with_a_bad_configuration_is_tried_once(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"discover": [("fail", "config_invalid")]})
    result = harness.run()

    assert harness.runner.attempts("discover") == 1 and harness.clock.sleeps == []
    assert harness.step(result, "discover")["attempts"] == 1
    assert "failed after 1 try." in result.summary
    for name in ("classify", "ingest", "impact", "validity", "review"):
        assert harness.step(result, name)["status"] == "not_run"


def test_a_page_failure_keeps_the_discovered_candidates_usable(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"discover": [("fail_usable", "pages_unreachable")]})
    result = harness.run()

    assert harness.step(result, "discover")["status"] == "failed" and harness.runner.attempts("discover") == 3
    assert all(harness.step(result, name)["status"] == "done" for name in ops.STEPS[1:])
    assert result.outcome == "failed"


def test_a_missing_or_garbled_step_file_counts_as_a_crash(tmp_path: Path) -> None:
    class Silent(FakeRunner):
        def run(self, step: str, run_dir: Path, timeout_seconds: float) -> ops.RunnerResult:
            self.calls.append((step, timeout_seconds))
            if step == "discover":
                (run_dir / "steps" / "discover.json").write_text("{not json", encoding="utf-8")
            return ops.RunnerResult(timed_out=False)

    harness = Harness(tmp_path)
    harness.runner = Silent(harness.clock, harness.home)
    harness.ports.runner = harness.runner
    result = harness.run()

    assert harness.step(result, "discover")["code"] == "step_crashed" and harness.runner.attempts("discover") == 3


# --- 4. One-hour hard budget -----------------------------------------------------------------


def test_a_running_step_is_stopped_at_the_hour_and_the_run_still_reports(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"ingest": ["hang"]})
    harness.clock.advance(0)
    result = harness.run()

    name, timeout = harness.runner.calls[-1]
    assert name == "ingest" and timeout == pytest.approx(3600)  # the whole budget was left
    assert harness.step(result, "ingest")["status"] == "stopped_at_time_limit"
    for later in ("impact", "validity", "review"):
        assert harness.step(result, later)["status"] == "not_run" and harness.step(result, later)["reason"] == "time_limit"
    assert result.outcome == "stopped_at_time_limit" and result.exit_code == 1
    assert harness.ledger()[-1]["event"] == "run_finished" and harness.ledger()[-1]["outcome"] == "stopped_at_time_limit"
    assert (result.run_dir / "summary.txt").is_file()
    assert "stopped at the one-hour limit" in result.summary


def test_the_child_timeout_is_the_time_left(tmp_path: Path) -> None:
    class Slow(FakeRunner):
        def run(self, step: str, run_dir: Path, timeout_seconds: float) -> ops.RunnerResult:
            if step != "discover":
                self.clock.advance(20 * 60)
            return super().run(step, run_dir, timeout_seconds)

    harness = Harness(tmp_path)
    harness.runner = Slow(harness.clock, harness.home)
    harness.ports.runner = harness.runner
    harness.run()

    timeouts = {name: seconds for name, seconds in harness.runner.calls}
    assert timeouts["discover"] == pytest.approx(3600) and timeouts["classify"] == pytest.approx(3600)
    assert timeouts["ingest"] == pytest.approx(3600 - 20 * 60)
    assert timeouts["impact"] == pytest.approx(1200)
    assert harness.runner.attempts("validity") == 0  # the hour is spent: nothing new starts


def test_a_retry_wait_is_never_longer_than_the_time_left(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"discover": [("late_fail", 59 * 60 + 30, "sources_unreachable")]})
    result = harness.run()

    assert harness.clock.sleeps == [30]  # 60 s was due, only 30 s were left
    assert harness.runner.attempts("discover") == 1  # and no further attempt starts after the wait
    assert harness.step(result, "discover")["status"] == "stopped_at_time_limit"
    assert result.outcome == "stopped_at_time_limit"


def test_no_step_starts_once_the_budget_is_spent(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"discover": [("late_fail", 3600, "config_invalid")]})
    result = harness.run()

    assert [name for name, _ in harness.runner.calls] == ["discover"]
    assert harness.step(result, "classify")["reason"] == "time_limit"
    assert result.outcome == "stopped_at_time_limit"


# --- 5. Plain-language summary ---------------------------------------------------------------


def test_the_summary_is_short_plain_and_counts_only(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"classify": [("fail", "model_not_running")]})
    result = harness.run()

    lines = result.summary.splitlines()
    assert len(lines) <= 15
    assert lines[0] == "Knowledge update run on 2026-11-08 10:20 (took 6 min)."
    assert lines[-1] == ops.FIXED_LINE
    assert "2 new candidates" in result.summary and "2 documents read, 0 failed" in result.summary
    assert "1 impact findings and 1 validity proposals" in result.summary
    assert MARKER not in result.summary and "https://" not in result.summary
    assert (harness.home / "runs" / result.run_id / "summary.txt").read_text(encoding="utf-8") == result.summary


def test_the_worst_summary_still_fits_fifteen_lines(tmp_path: Path) -> None:
    every = {name: [("fail", "step_crashed")] for name in ops.STEPS}
    harness = Harness(tmp_path, every)
    result = harness.run()
    assert len(result.summary.splitlines()) <= 15
    assert "Details for a developer:" in result.summary


def test_no_title_url_or_exception_text_reaches_the_summary_ledger_or_step_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(context: ops.StepContext) -> Dict[str, int]:
        raise RuntimeError(EXCEPTION_MARKER + " " + MARKER)

    monkeypatch.setitem(ops.ADAPTERS, "classify", boom)

    class Real(FakeRunner):
        def run(self, step: str, run_dir: Path, timeout_seconds: float) -> ops.RunnerResult:
            if step == "classify":
                self.calls.append((step, timeout_seconds))
                ops.execute_step("classify", run_dir, REPO_ROOT)
                return ops.RunnerResult(timed_out=False)
            return super().run(step, run_dir, timeout_seconds)

    harness = Harness(tmp_path)
    harness.runner = Real(harness.clock, harness.home)
    harness.ports.runner = harness.runner
    result = harness.run()

    published = [result.summary, (harness.home / ops.LEDGER_NAME).read_text(encoding="utf-8")]
    published += [path.read_text(encoding="utf-8") for path in (result.run_dir / "steps").glob("*.json")]
    for text in published:
        assert EXCEPTION_MARKER not in text and MARKER not in text and "https://" not in text
    assert EXCEPTION_MARKER in ops.log_path(harness.home).read_text(encoding="utf-8")  # the log keeps the traceback
    assert stat.S_IMODE(ops.log_path(harness.home).stat().st_mode) == 0o600
    assert harness.step(result, "classify")["code"] == "step_crashed"


# --- 7. Fail closed and stay single ----------------------------------------------------------


def test_a_missing_folder_changes_nothing(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    for name in ops.EXAMPLES:
        (harness.home / name).unlink()

    with pytest.raises(ops.Problem) as problem:
        harness.run()

    assert problem.value.fix == ops.ON_COMMAND and not (harness.home / ops.LEDGER_NAME).exists()
    assert harness.runner.calls == []


def test_a_missing_backend_environment_changes_nothing(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.ports.python = tmp_path / "no-python"
    with pytest.raises(ops.Problem) as problem:
        harness.run()
    assert problem.value.fix == ops.SETUP_COMMAND and not (harness.home / ops.LEDGER_NAME).exists()


def test_a_second_run_starts_nothing_and_writes_no_ledger_line(harness: Harness) -> None:
    with ops._Lock(harness.home):
        with pytest.raises(ops.AlreadyRunning):
            harness.run()
    assert harness.runner.calls == [] and not (harness.home / ops.LEDGER_NAME).exists()
    harness.run()  # the lock was released
    assert len(harness.ledger()) == 2


# --- Status ----------------------------------------------------------------------------------


def test_status_after_a_good_run_is_healthy(harness: Harness) -> None:
    harness.launchctl.loaded = True
    harness.ports.plist.parent.mkdir(parents=True)
    harness.ports.plist.write_bytes(b"x")
    harness.run()
    harness.clock.advance(3600)

    state = ops.status(harness.ports)
    lines, result = ops.status_lines(state)

    assert state.healthy and state.last_outcome == "review_ready" and state.warnings == []
    assert lines[0] == "Knowledge updates are on (every day at 10:20)."
    assert any("ready for your review" in line for line in lines) and any(line.startswith("Summary: ") for line in lines)
    assert result.startswith("Result: knowledge updates are on and the last run is ready")


def test_status_warns_missed_after_thirty_hours_while_on(harness: Harness) -> None:
    harness.launchctl.loaded = True
    harness.ports.plist.parent.mkdir(parents=True)
    harness.ports.plist.write_bytes(b"x")
    harness.run()
    harness.clock.advance(31 * 3600)

    state = ops.status(harness.ports)
    assert "missed" in state.warnings and not state.healthy
    assert any(line.startswith("Warning (missed)") for line in ops.status_lines(state)[0])


def test_status_does_not_warn_missed_while_off(harness: Harness) -> None:
    harness.run()
    harness.clock.advance(40 * 3600)
    state = ops.status(harness.ports)
    assert not state.on and state.warnings == [] and not state.healthy
    assert "off" in ops.status_lines(state)[1]


def test_status_warns_interrupted_when_a_run_started_and_never_finished(harness: Harness) -> None:
    harness.launchctl.loaded = True
    harness.ports.plist.parent.mkdir(parents=True)
    harness.ports.plist.write_bytes(b"x")
    ops._append_ledger(harness.home, {
        "schema_version": ops.LEDGER_SCHEMA, "event": "run_started", "run_id": "run-20261108T092000Z-00000000",
        "trigger": "schedule", "started_at": START.isoformat()})
    harness.clock.advance(3 * 3600)

    state = ops.status(harness.ports)
    assert state.warnings == ["interrupted"] and state.last_outcome == "interrupted"
    assert ops.metrics_snapshot(harness.home, harness.clock())["outcome"] == "interrupted"


def test_status_reports_a_failed_run_as_not_healthy(tmp_path: Path) -> None:
    harness = Harness(tmp_path, {"discover": [("fail", "config_invalid")]})
    harness.launchctl.loaded = True
    harness.ports.plist.parent.mkdir(parents=True)
    harness.ports.plist.write_bytes(b"x")
    harness.run()
    state = ops.status(harness.ports)
    assert not state.healthy and state.last_outcome == "failed"
    assert ops.metrics_snapshot(harness.home, harness.clock())["outcome"] == "failed"


def test_status_with_no_folder_is_a_problem(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.ports.home = tmp_path / "missing"
    with pytest.raises(ops.Problem):
        ops.status(harness.ports)


def test_a_damaged_ledger_is_refused_without_echoing_it(harness: Harness) -> None:
    (harness.home / ops.LEDGER_NAME).write_text("SECRET not json\n", encoding="utf-8")
    with pytest.raises(ops.OpsError) as error:
        ops.status(harness.ports)
    assert "SECRET" not in str(error.value)
    assert ops.metrics_snapshot(harness.home) == {"readable": False}


# --- 1. Turn on and off ----------------------------------------------------------------------


def test_turn_on_creates_the_folder_the_configs_and_the_agent(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    fresh = tmp_path / "fresh-home"
    harness.ports.home = fresh

    code, result = ops.turn_on(harness.ports)

    assert code == 0 and result.startswith("Result: knowledge updates are on.") and "10:20" in result
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o700
    for name in ops.EXAMPLES:
        assert (fresh / name).read_text(encoding="utf-8") == (REPO_ROOT / "backend" / "deploy" / (name + ".example")).read_text(encoding="utf-8")
    document = plistlib.loads(harness.ports.plist.read_bytes())
    assert document["Label"] == "org.manijero.knowledge-ops"
    assert document["StartCalendarInterval"] == {"Hour": 10, "Minute": 20}
    assert document["ProgramArguments"][-2:] == ["run", "--scheduled"]
    assert not any(key.startswith("MANIJERO_") for key in document["EnvironmentVariables"])
    assert "MANIJERO_" not in harness.ports.plist.read_text(encoding="latin-1")
    assert harness.launchctl.loaded and harness.launchctl.calls.count("bootstrap") == 1


def test_turn_on_twice_changes_nothing_the_second_time(harness: Harness) -> None:
    ops.turn_on(harness.ports)
    first = harness.ports.plist.read_bytes()
    (harness.home / "page-monitor.json").write_text('{"sources":[{"edited":true}]}', encoding="utf-8")
    harness.launchctl.calls.clear()

    code, result = ops.turn_on(harness.ports)

    assert code == 0 and "already on" in result and "nothing was changed" in result
    assert harness.ports.plist.read_bytes() == first
    assert "bootstrap" not in harness.launchctl.calls and "bootout" not in harness.launchctl.calls
    assert "edited" in (harness.home / "page-monitor.json").read_text(encoding="utf-8")  # owner edits survive


def test_turn_on_without_launchctl_or_backend_changes_nothing(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.ports.home = tmp_path / "fresh"
    harness.launchctl = FakeLaunchctl(present=False)
    harness.ports.launchctl = harness.launchctl
    with pytest.raises(ops.Problem):
        ops.turn_on(harness.ports)
    assert not (tmp_path / "fresh").exists() and not harness.ports.plist.exists()

    harness.launchctl = FakeLaunchctl()
    harness.ports.launchctl = harness.launchctl
    harness.ports.python = tmp_path / "none"
    with pytest.raises(ops.Problem) as problem:
        ops.turn_on(harness.ports)
    assert problem.value.fix == ops.SETUP_COMMAND and not (tmp_path / "fresh").exists()


def test_turn_off_removes_only_the_agent_and_keeps_the_history(harness: Harness) -> None:
    ops.turn_on(harness.ports)
    harness.run()

    code, result = ops.turn_off(harness.ports)

    assert code == 0 and "off" in result and "history is kept" in result
    assert not harness.ports.plist.exists() and not harness.launchctl.loaded
    assert (harness.home / ops.LEDGER_NAME).exists() and (harness.home / ops.LATEST_SUMMARY_NAME).exists()
    again = ops.turn_off(harness.ports)
    assert again[0] == 0 and "already off" in again[1]


def test_launchctl_is_only_ever_asked_about_the_one_label() -> None:
    from app import qa_alerts

    calls: List[List[str]] = []
    launchctl = qa_alerts.SystemLaunchctl(501, cli="/bin/echo", label=ops.LABEL)
    launchctl._run = lambda args: calls.append(list(args)) or True  # type: ignore[method-assign]
    launchctl.is_loaded()
    launchctl.bootout()
    assert calls == [["print", "gui/501/org.manijero.knowledge-ops"], ["bootout", "gui/501/org.manijero.knowledge-ops"]]


# --- Step adapters call the accepted entry points --------------------------------------------


def context(tmp_path: Path) -> ops.StepContext:
    home = tmp_path / "ko"
    run_dir = home / "runs" / "run-20261108T092000Z-00000000"
    (run_dir / "reports").mkdir(parents=True)
    return ops.StepContext(home, run_dir, REPO_ROOT, date(2026, 11, 8))


def test_discover_calls_the_scheduler_then_the_page_monitor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import page_monitor
    from app import source_update_scheduler as scheduler

    ctx = context(tmp_path)
    ctx.home.mkdir(parents=True, exist_ok=True)
    (ctx.home / "page-monitor.json").write_text('{"sources":[]}', encoding="utf-8")
    seen: Dict[str, Any] = {}

    def fake_updates(state_dir: Path, **kwargs: Any) -> Dict[str, Any]:
        seen["updates"] = (state_dir, kwargs)
        return {"outcome": "success", "jobs": [{"job": "boe", "new_or_changed_observations": 3},
                                               {"job": "monitor", "status": "success"}]}

    def fake_pages(config: Any, state: Path, report: Path, now: Any = None) -> Dict[str, Any]:
        seen["pages"] = (config, state, report)
        return {"pages": [{"status": "changed"}, {"status": "unchanged"}]}

    monkeypatch.setattr(scheduler, "run_updates", fake_updates)
    monkeypatch.setattr(page_monitor, "run", fake_pages)

    counts = ops.step_discover(ctx)

    assert seen["updates"] == (ctx.home / "source-updates", {"monitor_config": ctx.home / "source-monitor.json", "trigger": "knowledge_ops"})
    assert seen["pages"] == ({"sources": []}, ctx.home / "page-monitor-state.json", ctx.reports / "page-monitor.json")
    assert counts == {"new_candidates": 3, "pages_changed": 1}
    state = json.loads(ctx.discovery_state.read_text(encoding="utf-8"))
    assert state["candidates"] == {} and state["schema_version"] == "official-discovery-state-v1"


@pytest.mark.parametrize(
    ("scheduler_outcome", "page_status", "code", "usable"),
    [("failure", "changed", "sources_unreachable", False), ("config_error", "changed", "config_invalid", False),
     ("success", "failed", "pages_unreachable", True)],
)
def test_discover_failures_have_fixed_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scheduler_outcome: str, page_status: str, code: str, usable: bool
) -> None:
    from app import page_monitor
    from app import source_update_scheduler as scheduler

    ctx = context(tmp_path)
    ctx.home.mkdir(parents=True, exist_ok=True)
    (ctx.home / "page-monitor.json").write_text('{"sources":[]}', encoding="utf-8")
    monkeypatch.setattr(scheduler, "run_updates", lambda *a, **k: {"outcome": scheduler_outcome, "jobs": []})
    monkeypatch.setattr(page_monitor, "run", lambda *a, **k: {"pages": [{"status": page_status}]})

    with pytest.raises(ops.StepFailure) as failure:
        ops.step_discover(ctx)
    assert failure.value.code == code and failure.value.usable is usable


def test_classify_ingest_impact_and_validity_call_the_accepted_entry_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import change_impact, document_ingestion, local_generation, relevance_classifier, source_validity

    ctx = context(tmp_path)
    seen: Dict[str, Any] = {}
    monkeypatch.setattr(relevance_classifier, "load_model_record", lambda path, clock: "record")
    monkeypatch.setattr(local_generation, "OllamaTransport", lambda record, response_format=None: "transport")

    def fake_classify(**kwargs: Any) -> Dict[str, Any]:
        seen["classify"] = kwargs
        return {"summary": {"relevant": 2, "unsure": 1, "not_relevant": 0, "total": 3}}

    monkeypatch.setattr(relevance_classifier, "classify", fake_classify)
    assert ops.step_classify(ctx) == {"relevant": 2, "unsure": 1, "not_relevant": 0}
    assert seen["classify"]["discovery_state"] == ctx.discovery_state
    assert seen["classify"]["procedure_map"] == KNOWLEDGE / "procedure_map.json"
    assert seen["classify"]["report"] == ctx.reports / "relevance.json"
    assert seen["classify"]["transport"] == "transport"

    def fake_ingest(discovery: Path, state: Path, quarantine: Path, monitoring_state: Any = None) -> Dict[str, Any]:
        seen["ingest"] = (discovery, state, quarantine, monitoring_state)
        return {"summary": {"extracted": 2, "unchanged": 1, "failed": 1, "rejected": 1}}

    monkeypatch.setattr(document_ingestion, "ingest", fake_ingest)
    assert ops.step_ingest(ctx) == {"documents_ingested": 3, "documents_failed": 2}
    assert seen["ingest"] == (ctx.discovery_state, ctx.ingestion_state, ctx.quarantine, None)

    def fake_analyze(state: Path, quarantine: Path, catalog: Path, passages: Path, cases_path: Any = None, as_of: Any = None) -> Dict[str, Any]:
        seen["analyze"] = (state, quarantine, catalog, passages, cases_path, as_of)
        return {"summary": {"review_required": 4}}

    written: List[Path] = []
    monkeypatch.setattr(change_impact, "analyze", fake_analyze)
    monkeypatch.setattr(change_impact, "write_report", lambda report, path: written.append(path))
    assert ops.step_impact(ctx) == {"impact_findings": 4}
    assert seen["analyze"] == (ctx.ingestion_state, ctx.quarantine, KNOWLEDGE / "source_catalog.json",
                               KNOWLEDGE / "passages.json", KNOWLEDGE / "pac_answer_eval.json", date(2026, 11, 8))
    assert written == [ctx.reports / "impact.json"]

    def fake_validity(catalog: Path, passages: Path, impact: Path, as_of: date) -> Dict[str, Any]:
        seen["validity"] = (catalog, passages, impact, as_of)
        return {"proposals": [1, 2]}

    monkeypatch.setattr(source_validity, "check_validity", fake_validity)
    monkeypatch.setattr(source_validity, "write_report", lambda report, path, input_paths=(): written.append(path))
    assert ops.step_validity(ctx) == {"validity_proposals": 2}
    assert seen["validity"] == (KNOWLEDGE / "source_catalog.json", KNOWLEDGE / "passages.json",
                                ctx.reports / "impact.json", date(2026, 11, 8))
    assert written[-1] == ctx.reports / "validity.json"


def test_classify_reports_a_stopped_model_as_retryable_and_bad_input_as_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import local_generation, relevance_classifier

    ctx = context(tmp_path)
    monkeypatch.setattr(relevance_classifier, "load_model_record", lambda path, clock: "record")
    monkeypatch.setattr(local_generation, "OllamaTransport", lambda record, response_format=None: "transport")
    for failure, code in (("model_unavailable", "model_not_running"), ("invalid_discovery_state", "config_invalid")):
        def abort(**kwargs: Any) -> None:
            raise relevance_classifier.ClassificationAbort(failure)

        monkeypatch.setattr(relevance_classifier, "classify", abort)
        with pytest.raises(ops.StepFailure) as raised:
            ops.step_classify(ctx)
        assert raised.value.code == code
        assert raised.value.retryable is (code == "model_not_running")


def test_the_orchestrator_never_publishes_merges_decides_or_releases() -> None:
    source = (REPO_ROOT / "backend" / "app" / "knowledge_ops.py").read_text(encoding="utf-8")
    script = (REPO_ROOT / "backend" / "scripts" / "knowledge_ops.py").read_text(encoding="utf-8")
    for text in (source, script):
        for forbidden in ("merge", "record_decision", "knowledge_release", "review_package", "canonical"):
            assert forbidden not in text, forbidden
    assert "KNOWLEDGE_ROOT" not in source


def test_every_failure_code_has_a_sentence_and_a_first_step() -> None:
    for code, (sentence, fix, retryable) in ops.CODES.items():
        assert sentence.endswith(".") and fix and isinstance(retryable, bool), code
    assert ops.BUDGET == timedelta(hours=1) and ops.MAX_ATTEMPTS == 3 and ops.BACKOFF == (60, 300)


# --- The real process runner -----------------------------------------------------------------


def test_the_process_runner_stops_a_hung_child_and_reports_it(tmp_path: Path) -> None:
    runner = ops.SubprocessRunner([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path / "logs" / "log.txt")
    started = time.monotonic()

    result = runner.run("discover", tmp_path, 0.5)

    assert result.timed_out and time.monotonic() - started < 15
    assert stat.S_IMODE((tmp_path / "logs" / "log.txt").stat().st_mode) == 0o600


def test_the_process_runner_passes_the_step_and_run_folder_to_the_child(tmp_path: Path) -> None:
    code = "import sys, pathlib; pathlib.Path(sys.argv[-1]).joinpath('seen.txt').write_text(' '.join(sys.argv[1:3]))"
    runner = ops.SubprocessRunner([sys.executable, "-c", code], tmp_path / "log.txt")

    result = runner.run("ingest", tmp_path, 30)

    assert not result.timed_out and (tmp_path / "seen.txt").read_text(encoding="utf-8") == "step ingest"
