"""Offline tests for the nightly evaluation.

The metrics command is a scripted fake, the clock and the sleep are fakes, ``launchctl`` is in
memory, Telegram is an in-memory fake, and sockets are blocked. No real launchctl, Telegram,
LaunchAgents folder, ``~/manijero`` folder, or token is ever touched; the token is a fake.
"""

from __future__ import annotations

import importlib.util
import json
import plistlib
import socket
import stat
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app import nightly_eval as nightly

REPO_ROOT = Path(__file__).resolve().parents[2]
START = datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc)  # 00:00 on 2026-11-11 in Madrid
FAKE_TOKEN = "123456789:AbCdEfGhIjKlMnOpQrStUvWxYz0123"
CHAT_ID = 4242424242
MARKER = "QUESTION-MARKER-ayuda-secreta"
EXCEPTION_MARKER = "EXCEPTION-MARKER-ruta-privada"
HIGH = {"hit_at_1": 0.7, "hit_at_3": 0.8, "hit_at_5": 0.9, "mrr": 0.75, "abstention": 0.95,
        "numeric": 0.8, "faithfulness": None, "cache_reuse": 0.85}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in nightly-eval tests")

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
        self._present, self.loaded, self.calls = present, False, []  # type: bool, bool, List[str]

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


class FakeTelegram:
    """Records every message; ``fail`` makes the next sends fail; ``is_set_up`` is the stored-details switch."""

    def __init__(self) -> None:
        self.sent: List[str] = []
        self.fail = 0
        self.attempts = 0
        self.is_set_up = False

    def configured(self) -> bool:
        return self.is_set_up

    def send(self, text: str) -> bool:
        self.attempts += 1
        if self.fail > 0:
            self.fail -= 1
            return False
        self.sent.append(text)
        return True


def report_document(report_id: str, scores: Dict[str, Optional[float]], *, digest: str = "a",
                    asked: int = 100) -> Dict[str, Any]:
    faithfulness: Dict[str, Any] = {"status": "not_judged", "reason": "skipped"}
    if scores.get("faithfulness") is not None:
        faithfulness = {"status": "judged", "supported_share": scores["faithfulness"]}
    reuse = scores.get("cache_reuse")
    return {
        "schema_version": "eval-metrics-report-v1",
        "version": {"as_of": "2026-11-11", "catalog_sha256": digest, "k": 5, "answer_cache_check": True},
        "version_id": report_id,
        "metrics": {
            "retrieval": {"overall": {k: scores[k] for k in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr")}},
            "abstention": {"overall": {"share": scores["abstention"]}},
            "numeric": {"overall": {"share": scores["numeric"]}},
        },
        "faithfulness": faithfulness,
        "answer_cache_check": {"asked": asked, "served_from_cache": asked,
                               "reused_unchanged": round((reuse or 0) * asked), "differed": 0},
    }


class FakeChild:
    """Scripted metrics command: each call pops one action (the last repeats)."""

    def __init__(self, clock: FakeClock, reports_root: Path) -> None:
        self.clock, self.root = clock, reports_root
        self.actions: List[Any] = []
        self.calls: List[Tuple[str, float]] = []

    def run(self, as_of: str, timeout_seconds: float) -> nightly.ChildResult:
        self.calls.append((as_of, timeout_seconds))
        action = self.actions[min(len(self.calls), len(self.actions)) - 1]
        self.clock.advance(120)
        if action == "hang":
            self.clock.advance(timeout_seconds)
            return nightly.ChildResult(True, None)
        if isinstance(action, str):  # a fixed failure code
            return nightly.ChildResult(False, 2, "Result: the metrics report did not run ({}): x Nothing was written.".format(action))
        if isinstance(action, Exception):
            raise action
        report_id, scores, extra = action
        path = self.root / report_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "metrics.json").write_text(json.dumps(report_document(report_id, scores, **extra)), encoding="utf-8")
        return nightly.ChildResult(False, 0, "Result: evaluated 92 questions. Report: build/eval-reports/{}/metrics.json; cached answers: x.".format(report_id))


class Lab:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "nightly-eval"
        self.clock = FakeClock()
        self.launchctl = FakeLaunchctl()
        self.telegram = FakeTelegram()
        self.child = FakeChild(self.clock, tmp_path / "reports")
        self.ports = nightly.Ports(
            home=self.home, repo_root=REPO_ROOT, agents_dir=tmp_path / "LaunchAgents", python=Path(sys.executable),
            reports_root=tmp_path / "reports", clock=self.clock, sleep=self.clock.sleep,
            runner=self.child, launchctl=self.launchctl, telegram=self.telegram, out=lambda text: None,
        )
        self.home.mkdir()

    def store_credentials(self) -> None:
        self.telegram.is_set_up = True

    def run(self, action: Any, trigger: str = "manual") -> nightly.RunResult:
        self.child.actions = [action]
        self.child.calls.clear()
        self.clock.advance(3600)  # the previous run is an hour older
        return nightly.run_once(self.ports, trigger)

    def records(self) -> List[Dict[str, Any]]:
        return nightly.read_ledger(self.home)


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return Lab(tmp_path)


def good(report_id: str = "0123456789abcdef", **changes: Optional[float]) -> Tuple[str, Dict[str, Optional[float]], Dict[str, Any]]:
    return report_id, {**HIGH, **changes}, {}


def test_a_first_run_records_scores_compares_nothing_and_sends_nothing(lab: Lab) -> None:
    lab.store_credentials()
    result = lab.run(good(), "schedule")
    assert (result.outcome, result.exit_code, result.alert, result.drops) == ("evaluated", 0, "not_needed", [])
    assert lab.child.calls == [("2026-11-11", 3 * 3600.0)]  # Europe/Madrid date at the start; the full budget
    assert lab.telegram.sent == []
    started, finished = lab.records()
    assert (started["event"], started["trigger"], started["as_of"]) == ("run_started", "schedule", "2026-11-11")
    assert finished["event"] == "run_finished" and finished["outcome"] == "evaluated"
    assert finished["first_run"] is True and finished["drops"] == [] and finished["inputs_changed"] is False
    assert finished["report_id"] == "0123456789abcdef" and finished["scores"]["mrr"] == 0.75
    assert finished["scores"]["faithfulness"] is None and finished["faithfulness"] == "not_judged"
    assert finished["scores"]["cache_reuse"] == 0.85
    assert stat.S_IMODE((lab.home / nightly.LEDGER_NAME).stat().st_mode) == 0o600
    summary = (lab.home / nightly.LATEST_SUMMARY_NAME).read_text(encoding="utf-8")
    assert summary == result.summary and len(summary.splitlines()) <= 10
    assert "first run" in summary and "sentences the judge found supported not measured" in summary
    assert nightly.result_line(result) == "Result: the nightly evaluation finished. No score dropped."


@pytest.mark.parametrize("key", nightly.SCORE_KEYS)
def test_a_drop_in_any_score_sends_exactly_one_message(lab: Lab, key: str) -> None:
    lab.store_credentials()
    base = {**HIGH, "faithfulness": 0.9}
    lab.run(("aaaaaaaaaaaaaaaa", base, {}))
    result = lab.run(("bbbbbbbbbbbbbbbb", {**base, key: base[key] - 0.05}, {}))  # type: ignore[operator]
    assert result.outcome == "evaluated" and result.exit_code == 0  # a drop never changes the exit code
    assert [d["metric"] for d in result.drops] == [key] and result.alert == "sent"
    old, new = nightly._value(key, base[key]), nightly._value(key, round(base[key] - 0.05, 4))  # type: ignore[operator,arg-type]
    assert lab.telegram.sent == [
        "Manijero nightly evaluation: 1 score(s) dropped since the last run: {} {} -> {}."
        " First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.".format(
            nightly.LABELS[key], old, new)]
    assert nightly.result_line(result).startswith("Result: the nightly evaluation finished and 1 score(s) dropped.")
    assert lab.records()[-1]["alert"] == "sent"


def test_the_message_formats_shares_as_percentages_and_mrr_with_four_decimals(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", {**HIGH, "mrr": 0.7768, "hit_at_1": 0.7321}, {}))
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.7, "hit_at_1": 0.6}, {}))
    assert "right source first 73.2% -> 60.0%; average source rank score (MRR) 0.7768 -> 0.7000." in lab.telegram.sent[0]


def test_equal_improved_and_unmeasured_scores_send_nothing(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", {**HIGH, "faithfulness": 0.9}, {}))
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "faithfulness": 0.9, "mrr": 0.9}, {}))  # equal and improved
    lab.run(("cccccccccccccccc", {**HIGH, "faithfulness": None, "mrr": 0.9}, {}))  # not judged today: not compared
    lab.run(("dddddddddddddddd", {**HIGH, "faithfulness": 0.1, "mrr": 0.9}, {}))  # not judged before: not compared
    assert lab.telegram.sent == [] and all(r["drops"] == [] for r in lab.records() if r["event"] == "run_finished")


def test_a_drop_smaller_than_four_decimals_is_not_a_drop(lab: Lab) -> None:
    lab.run(("aaaaaaaaaaaaaaaa", {**HIGH, "mrr": 0.77681}, {}))
    result = lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.77684}, {}))
    assert result.drops == []


def test_changed_inputs_add_one_sentence_to_the_message(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {"digest": "a"}))
    result = lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "numeric": 0.5}, {"digest": "b"}))
    assert lab.records()[-1]["inputs_changed"] is True
    assert lab.telegram.sent[0].endswith(
        "{} First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.".format(
            nightly.INPUTS_CHANGED.strip()))
    assert "The questions or the knowledge changed since the last run" in result.summary


def test_a_failed_run_is_never_the_comparison_base(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}))
    failed = lab.run("ask_failed")
    assert (failed.outcome, failed.code, failed.exit_code) == ("failed", "ask_failed", 1)
    finished = lab.records()[-1]
    assert "scores" not in finished and finished["alert"] == "sent"  # a failed run is reported, never compared
    lab.run("hang")
    result = lab.run(("cccccccccccccccc", {**HIGH, "hit_at_3": 0.5}, {}))
    assert [d["metric"] for d in result.drops] == ["hit_at_3"] and result.drops[0]["old"] == 0.8


@pytest.mark.parametrize("code", ["invalid_inputs", "ask_failed", "unsafe_report_path", "internal_error"])
def test_a_child_that_exits_2_is_a_failed_run_with_its_code(lab: Lab, code: str) -> None:
    result = lab.run(code)
    assert (result.outcome, result.code, result.exit_code) == ("failed", code, 1)
    assert "Code: {}. No scores were recorded.".format(code) in result.summary
    assert nightly.result_line(result).startswith("Result: the nightly evaluation failed.")


def test_unreadable_child_output_is_a_failed_run(lab: Lab) -> None:
    class Odd:
        def run(self, as_of: str, timeout_seconds: float) -> nightly.ChildResult:
            return nightly.ChildResult(False, 0, "Result: evaluated, but no path here.")

    lab.ports.runner = Odd()
    assert lab.run("x").code == "child_output_unreadable"

    class Missing:
        def run(self, as_of: str, timeout_seconds: float) -> nightly.ChildResult:
            return nightly.ChildResult(False, 0, "Result: x. Report: build/eval-reports/ffffffffffffffff/metrics.json.")

    lab.ports.runner = Missing()
    assert nightly.run_once(lab.ports, "manual").code == "child_output_unreadable"

    class NotStarted:
        def run(self, as_of: str, timeout_seconds: float) -> nightly.ChildResult:
            return nightly.ChildResult(False, None)

    lab.ports.runner = NotStarted()
    assert nightly.run_once(lab.ports, "manual").code == "child_output_unreadable"


def test_a_run_still_going_at_three_hours_is_stopped(lab: Lab) -> None:
    result = lab.run("hang")
    assert (result.outcome, result.code, result.exit_code) == ("stopped_at_time_limit", "time_limit", 1)
    assert lab.child.calls[0][1] == 3 * 3600.0
    assert "How it went: stopped at the 3-hour limit." in result.summary
    assert lab.records()[-1]["outcome"] == "stopped_at_time_limit"


def test_a_failing_send_is_tried_three_times_ten_seconds_apart(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}))
    lab.telegram.fail = 99
    lab.clock.sleeps.clear()
    result = lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    assert result.alert == "not_sent" and result.exit_code == 0 and lab.clock.sleeps == [10, 10]
    assert lab.telegram.attempts == 3
    assert "run ./scripts/init.sh --qa-alerts-test" in result.summary
    lab.telegram.fail = 1  # one failure, then success on the second try
    assert lab.run(("cccccccccccccccc", {**HIGH, "mrr": 0.05}, {})).alert == "sent"
    assert len(lab.telegram.sent) == 1


def test_missing_telegram_details_are_recorded_and_never_resent(lab: Lab) -> None:
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}))
    result = lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    assert result.alert == "not_set_up" and "./scripts/init.sh --qa-alerts-setup" in result.summary
    lab.store_credentials()
    equal = lab.run(("cccccccccccccccc", {**HIGH, "mrr": 0.1}, {}))  # no new drop: nothing to send
    assert equal.alert == "not_needed" and lab.telegram.sent == []


def test_another_run_holding_the_lock_starts_nothing(lab: Lab) -> None:
    with nightly._Lock(lab.home):
        with pytest.raises(nightly.AlreadyRunning):
            nightly.run_once(lab.ports, "manual")
    assert lab.records() == [] and lab.child.calls == []


def test_missing_prerequisites_change_nothing(lab: Lab, tmp_path: Path) -> None:
    lab.ports.home = tmp_path / "never-created"
    with pytest.raises(nightly.Problem) as raised:
        nightly.run_once(lab.ports, "manual")
    assert raised.value.fix == nightly.ON_COMMAND and not lab.ports.home.exists()
    lab.ports.home = lab.home
    lab.launchctl._present = False
    with pytest.raises(nightly.Problem):
        nightly.run_once(lab.ports, "manual")
    lab.launchctl._present = True
    lab.ports.python = tmp_path / "no-python"
    with pytest.raises(nightly.Problem) as raised:
        nightly.run_once(lab.ports, "manual")
    assert raised.value.fix == nightly.SETUP_COMMAND and lab.child.calls == [] and lab.records() == []


def test_turn_on_and_off_manage_only_the_nightly_agent(lab: Lab) -> None:
    code, line = nightly.turn_on(lab.ports)
    assert (code, line) == (0, "Result: the nightly evaluation is on. It runs every night at 00:00 while this Mac is on.")
    assert stat.S_IMODE(lab.home.stat().st_mode) == 0o700
    document = plistlib.loads(lab.ports.plist.read_bytes())
    assert document["Label"] == "org.manijero.nightly-eval"
    assert document["StartCalendarInterval"] == {"Hour": 0, "Minute": 0}
    assert document["ProgramArguments"][-2:] == ["run", "--scheduled"] and document["ProgramArguments"][1].endswith("backend/scripts/nightly_eval.py")
    assert set(document["EnvironmentVariables"]) == {"PATH"} and "MANIJERO_" not in lab.ports.plist.read_text(encoding="latin-1")
    assert nightly.turn_on(lab.ports) == (0, "Result: the nightly evaluation is already on; nothing was changed.")
    assert lab.launchctl.calls.count("bootstrap") == 1
    lab.run(good())
    assert nightly.turn_off(lab.ports) == (0, "Result: the nightly evaluation is off. Your history is kept.")
    assert not lab.ports.plist.exists() and (lab.home / nightly.LEDGER_NAME).exists()
    assert nightly.turn_off(lab.ports)[1].startswith("Result: the nightly evaluation was already off")
    lab.launchctl._present = False
    with pytest.raises(nightly.Problem):
        nightly.turn_on(lab.ports)


def test_status_reports_on_off_warnings_and_health(lab: Lab) -> None:
    nightly.turn_on(lab.ports)
    state = nightly.status(lab.ports)
    assert not state.healthy and nightly.status_lines(state)[1] == "Result: the nightly evaluation is on. No run has finished yet."
    lab.store_credentials()
    lab.run(good())
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    state = nightly.status(lab.ports)
    lines, result = nightly.status_lines(state)
    assert state.healthy  # a score drop alone never makes the status unhealthy
    assert result == "Result: the nightly evaluation is on and the last run was evaluated."
    assert "Alert: one message was sent to your phone." in lines and any("MRR) 0.7500 -> 0.1000" in line for line in lines)
    lab.clock.advance(31 * 3600)
    state = nightly.status(lab.ports)
    assert state.warnings == ["missed"] and not state.healthy
    assert "no run started in the last 30 hours" in "\n".join(nightly.status_lines(state)[0])
    nightly.turn_off(lab.ports)
    assert nightly.status_lines(nightly.status(lab.ports))[1].startswith("Result: the nightly evaluation is off.")


def test_status_flags_an_unfinished_run_and_an_unsent_alert(lab: Lab) -> None:
    nightly.turn_on(lab.ports)
    lab.run(good())
    nightly._append_ledger(lab.home, {"schema_version": nightly.LEDGER_SCHEMA, "run_id": "run-20261111T000000Z-deadbeef",
                                      "trigger": "schedule", "started_at": lab.clock().isoformat(), "event": "run_started"})
    assert nightly.status(lab.ports).warnings == []
    lab.clock.advance(4 * 3600 + 60)
    state = nightly.status(lab.ports)
    assert state.warnings == ["interrupted"] and state.outcome == "interrupted" and not state.healthy
    assert nightly.metrics_snapshot(lab.home, lab.clock())["outcome"] == "interrupted"
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))  # a drop without Telegram details
    state = nightly.status(lab.ports)
    assert state.last is not None and state.last["alert"] == "not_set_up" and not state.healthy


def test_the_metrics_snapshot_has_scores_and_drops_of_an_evaluated_run(lab: Lab) -> None:
    lab.run(good())
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    snapshot = nightly.metrics_snapshot(lab.home, lab.clock())
    assert snapshot["readable"] and snapshot["outcome"] == "evaluated"
    assert snapshot["scores"]["mrr"] == 0.1 and "faithfulness" not in snapshot["scores"]
    assert snapshot["dropped"]["mrr"] == 1 and snapshot["dropped"]["hit_at_1"] == 0
    lab.run("ask_failed")
    failed = nightly.metrics_snapshot(lab.home, lab.clock())
    assert failed["outcome"] == "failed" and failed["scores"] == {} and failed["dropped"] == {}
    assert nightly.metrics_snapshot(lab.tmp / "missing") == {"readable": False}
    (lab.home / nightly.LEDGER_NAME).write_text("not json\n", encoding="utf-8")
    assert nightly.metrics_snapshot(lab.home) == {"readable": False}


def test_nothing_private_reaches_the_ledger_summary_log_plist_or_output(lab: Lab) -> None:
    lab.store_credentials()
    shown: List[str] = []
    lab.ports.out = shown.append
    nightly.turn_on(lab.ports)
    lab.run(good())
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    # A crash inside the run: the CLI turns it into one sentence and a class name.
    cli = load_cli()
    shown.clear()
    lab.child.actions = [RuntimeError("{} {} {}".format(MARKER, EXCEPTION_MARKER, FAKE_TOKEN))]
    assert cli.main(["run"], lab.ports) == 1
    everything = "\n".join(
        [path.read_text(encoding="utf-8", errors="replace") for path in lab.home.rglob("*") if path.is_file()]
        + [lab.ports.plist.read_text(encoding="latin-1"), "\n".join(shown)])
    for secret in (FAKE_TOKEN, str(CHAT_ID), MARKER, EXCEPTION_MARKER):
        assert secret not in everything
    assert "RuntimeError" in (lab.home / "logs" / nightly.LOG_NAME).read_text(encoding="utf-8")
    assert shown[-1] == "Result: the command did not finish."


def load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("nightly_eval_cli", REPO_ROOT / "backend" / "scripts" / "nightly_eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cli_maps_outcomes_to_exit_codes(lab: Lab) -> None:
    cli = load_cli()
    shown: List[str] = []
    lab.ports.out = shown.append
    assert cli.main(["status"], lab.ports) == 1 and shown[-1].startswith("Result: the nightly evaluation is off.")
    lab.child.actions = [good()]
    assert cli.main(["run", "--scheduled"], lab.ports) == 0
    assert [r["trigger"] for r in lab.records()] == ["schedule", "schedule"]
    lab.child.actions = ["ask_failed"]
    assert cli.main(["run"], lab.ports) == 1
    with nightly._Lock(lab.home):
        assert cli.main(["run"], lab.ports) == 3
    assert shown[-1] == "Result: nothing was started because a run is already in progress."
    lab.ports.home = lab.tmp / "never-created"
    assert cli.main(["run"], lab.ports) == 2
    assert shown[-2].startswith("The nightly evaluation is not set up yet. Run ./scripts/init.sh --nightly-eval-on")


def test_the_real_child_runner_stops_a_program_that_ignores_the_stop_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program = tmp_path / "hang.py"
    program.write_text(textwrap.dedent("""
        import signal, sys, time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        print("Result: still going " + " ".join(sys.argv[1:]), flush=True)
        time.sleep(60)
    """), encoding="utf-8")
    monkeypatch.setattr(nightly, "KILL_GRACE_SECONDS", 0.5)
    home = tmp_path / "home"
    began = time.monotonic()
    result = nightly.SubprocessChild([sys.executable, str(program)], home).run("2026-11-11", 1.0)
    assert result.timed_out and result.exit_code is None and time.monotonic() - began < 15
    assert "run --as-of 2026-11-11 --answer-cache-check" in result.result_line
    assert not (home / nightly.CHILD_OUTPUT_NAME).exists()
    quick = tmp_path / "quick.py"
    quick.write_text("import sys\nprint('Result: done')\nsys.exit(2)\n", encoding="utf-8")
    done = nightly.SubprocessChild([sys.executable, str(quick)], home).run("2026-11-11", 30.0)
    assert (done.timed_out, done.exit_code, done.result_line) == (False, 2, "Result: done")


def test_the_ledger_rejects_a_corrupt_line(lab: Lab) -> None:
    (lab.home / nightly.LEDGER_NAME).write_text('{"schema_version": "other"}\n', encoding="utf-8")
    with pytest.raises(nightly.OpsError):
        nightly.read_ledger(lab.home)
    with pytest.raises(nightly.OpsError):
        nightly.run_once(lab.ports, "manual")


def test_the_knowledge_folder_is_untouched(lab: Lab) -> None:
    def fingerprint() -> List[Tuple[str, int, int]]:
        return sorted((str(p.relative_to(REPO_ROOT)), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in (REPO_ROOT / "knowledge").rglob("*") if p.is_file())

    before = fingerprint()
    lab.run(good())
    lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    assert fingerprint() == before


def test_a_run_that_does_not_finish_sends_one_message(lab: Lab) -> None:
    lab.store_credentials()
    failed = lab.run("ask_failed", "schedule")
    stopped = lab.run("hang", "schedule")
    assert (failed.alert, stopped.alert) == ("sent", "sent") and failed.exit_code == 1
    assert lab.telegram.sent == [
        "Manijero nightly evaluation: the run did not finish (something failed, code ask_failed). No scores were "
        "recorded. First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.",
        "Manijero nightly evaluation: the run did not finish (stopped at the 3-hour limit, code time_limit). No scores "
        "were recorded. First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.",
    ]
    assert "Alert: one message was sent to your phone." in failed.summary


def test_a_failed_run_without_telegram_says_how_to_set_it_up(lab: Lab) -> None:
    result = lab.run("internal_error")
    assert result.alert == "not_set_up" and "./scripts/init.sh --qa-alerts-setup" in result.summary
    assert lab.telegram.sent == []


def test_a_missed_night_is_reported_by_the_next_run(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}), "schedule")
    lab.clock.advance(2 * 24 * 3600)  # the Mac was off for two nights
    result = lab.run(("bbbbbbbbbbbbbbbb", HIGH, {}), "schedule")
    assert result.outcome == "evaluated" and result.drops == [] and result.alert == "sent"
    message = lab.telegram.sent[-1]
    assert message.startswith("Manijero nightly evaluation: It had not run since ") and "at least one night was missed" in message
    assert "it ran and no score dropped." in message
    assert "at least one night was missed" in result.summary


def test_a_missed_night_and_a_drop_share_one_message(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}))
    lab.clock.advance(2 * 24 * 3600)
    result = lab.run(("bbbbbbbbbbbbbbbb", {**HIGH, "mrr": 0.1}, {}))
    assert len(lab.telegram.sent) == 1 and "night was missed" in lab.telegram.sent[0]
    assert "1 score(s) dropped since the last run" in lab.telegram.sent[0] and result.alert == "sent"


def test_runs_less_than_thirty_hours_apart_are_not_missed(lab: Lab) -> None:
    lab.store_credentials()
    lab.run(("aaaaaaaaaaaaaaaa", HIGH, {}))
    lab.clock.advance(28 * 3600)
    result = lab.run(("bbbbbbbbbbbbbbbb", HIGH, {}))
    assert result.alert == "not_needed" and lab.telegram.sent == []
