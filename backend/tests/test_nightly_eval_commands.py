"""The nightly evaluation owner commands through ``./scripts/init.sh``: the automated owner walkthrough.

The owner guide (``docs/owner-guide/nightly-evaluation.md``) replaces a manual walkthrough with this
test (owner decision): every documented command is run through ``scripts/init.sh`` exactly as the
guide writes it, with one missing-prerequisite case, one failure, and one recovery. Each run uses
temporary folders, a fake ``launchctl`` (a shell script that records its arguments), a fake metrics
program, and a fake Telegram server on a loopback test socket. The real ``launchctl``, Telegram,
``~/Library/LaunchAgents``, ``~/manijero``, and every secret are never touched; the token is a fake.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from app import qa_alerts as alerts
from test_qa_alerts import CHAT_ID, FAKE_TOKEN, FakeServer

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
GUIDE = REPO_ROOT / "docs" / "owner-guide" / "nightly-evaluation.md"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
COMMANDS = ["--nightly-eval-on", "--nightly-eval-run", "--nightly-eval-status", "--nightly-eval-off"]
LABEL = "org.manijero.nightly-eval"

pytestmark = pytest.mark.skipif(
    not os.access(VENV_PYTHON, os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_LAUNCHCTL = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
case "$1" in
  print) [ -f "{calls}.loaded" ] && exit 0 || exit 113 ;;
  bootstrap) touch "{calls}.loaded"; exit 0 ;;
  bootout) rm -f "{calls}.loaded"; exit 0 ;;
  *) exit 64 ;;
esac
"""

# The metrics program: fails while "fail" exists, otherwise writes a report with the scores in "scores.json".
FAKE_METRICS = """#!{python}
import json, os, sys
sys.path.insert(0, {backend!r})
sys.path.insert(0, {tests!r})
from pathlib import Path
from test_nightly_eval import report_document

flags = Path({flags!r})
assert sys.argv[1:2] == ["run"] and "--answer-cache-check" in sys.argv and "--as-of" in sys.argv
if (flags / "fail").exists():
    print("Result: the metrics report did not run (ask_failed): x Nothing was written.")
    raise SystemExit(2)
scores = json.loads((flags / "scores.json").read_text(encoding="utf-8"))
count = len(list((flags / "made").glob("*"))) if (flags / "made").exists() else 0
(flags / "made").mkdir(exist_ok=True)
(flags / "made" / str(count)).write_text("", encoding="utf-8")
report_id = "{{:016x}}".format(count + 1)
root = Path(os.environ["MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT"]) / report_id
root.mkdir(parents=True)
(root / "metrics.json").write_text(json.dumps(report_document(report_id, scores)), encoding="utf-8")
print("Result: evaluated 92 questions. Report: build/eval-reports/" + report_id + "/metrics.json; cached answers: fake.")
"""

SCORES = {"hit_at_1": 0.7, "hit_at_3": 0.8, "hit_at_5": 0.9, "mrr": 0.75, "abstention": 0.95,
          "numeric": 0.8, "faithfulness": None, "cache_reuse": 0.85}


class Mac:
    """One temporary Mac: folders, a fake launchctl, a fake metrics program, and a fake Telegram."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "nightly-eval"
        self.agents = tmp_path / "LaunchAgents"
        self.flags = tmp_path / "flags"
        self.flags.mkdir()
        (tmp_path / "bin").mkdir()
        self.launchctl = self._script("launchctl", FAKE_LAUNCHCTL.format(calls=tmp_path / "launchctl-calls.txt"))
        self.child = self._script("metrics", FAKE_METRICS.format(
            python=sys.executable, backend=str(BACKEND_ROOT), tests=str(BACKEND_ROOT / "tests"), flags=str(self.flags)))
        self.set_scores(SCORES)
        self.api = "http://127.0.0.1:9"  # nothing listens unless a test starts the fake server

    def _script(self, name: str, body: str) -> Path:
        script = self.tmp / "bin" / name
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
        return script

    def set_scores(self, scores: Dict[str, Optional[float]]) -> None:
        (self.flags / "scores.json").write_text(json.dumps(scores), encoding="utf-8")

    def store_telegram(self) -> None:
        alerts.write_credentials(self.tmp / "alerts", alerts.Credentials(FAKE_TOKEN, CHAT_ID))

    @property
    def plist(self) -> Path:
        return self.agents / (LABEL + ".plist")

    def calls(self) -> List[str]:
        path = self.tmp / "launchctl-calls.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(os.environ)
        env.update({
            "MANIJERO_NIGHTLY_EVAL_HOME": str(self.home),
            "MANIJERO_NIGHTLY_EVAL_CHILD_CLI": str(self.child),
            "MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT": str(self.tmp / "reports"),
            "MANIJERO_NIGHTLY_EVAL_NO_WAIT": "1",
            "MANIJERO_ALERTS_HOME": str(self.tmp / "alerts"),
            "MANIJERO_TELEGRAM_API": self.api,
            "MANIJERO_LAUNCH_AGENTS_DIR": str(self.agents),
            "MANIJERO_LAUNCHCTL_CLI": str(self.launchctl),
            "MANIJERO_VENV_ROOT": str(self.tmp / "venvs"),
        })
        env.update(extra or {})
        return env

    def init(self, mode: str, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        return subprocess.run([str(INIT), mode, *args], cwd=REPO_ROOT, env=self.env(extra), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=180, check=False)


@pytest.fixture
def mac(tmp_path: Path) -> Mac:
    return Mac(tmp_path)


def results(completed: subprocess.CompletedProcess) -> List[str]:
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


def one_clean_result(completed: subprocess.CompletedProcess) -> str:
    assert len(results(completed)) == 1 and completed.stdout.splitlines()[-1] == results(completed)[0], completed.stdout
    both = completed.stdout + completed.stderr
    assert "Traceback" not in both and FAKE_TOKEN not in both and str(CHAT_ID) not in both
    return results(completed)[0]


def test_the_guide_documents_exactly_the_four_commands_the_walkthrough_runs() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert set(re.findall(r"\./scripts/init\.sh (--nightly-eval-[a-z]+)", text)) == set(COMMANDS)
    assert len(text.splitlines()) <= 60


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_misuse(mac: Mac, mode: str) -> None:
    completed = mac.init(mode, "extra")
    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run {} on its own, with nothing after it.".format(mode)
    assert completed.stdout == "" and mac.calls() == [] and not mac.home.exists()


def test_help_lists_the_four_commands(mac: Mac) -> None:
    completed = subprocess.run([str(INIT), "--help"], cwd=REPO_ROOT, env=mac.env(), capture_output=True, text=True, check=False)
    assert completed.returncode == 0 and all(command in completed.stdout for command in COMMANDS)


def test_the_owner_walkthrough(mac: Mac) -> None:
    # Missing prerequisite: run before turning the schedule on changes nothing; status says it is off.
    before = mac.init("--nightly-eval-run")
    assert before.returncode == 2, before.stdout
    assert before.stdout.splitlines()[0] == (
        "The nightly evaluation is not set up yet. Run ./scripts/init.sh --nightly-eval-on, then try again.")
    one_clean_result(before)
    off = mac.init("--nightly-eval-status")
    assert off.returncode == 1 and one_clean_result(off).startswith("Result: the nightly evaluation is off.")
    assert not mac.home.exists() and not mac.agents.exists()

    # Step 1: turn on, then again.
    first = mac.init("--nightly-eval-on")
    assert first.returncode == 0, first.stdout
    assert one_clean_result(first) == "Result: the nightly evaluation is on. It runs every night at 00:00 while this Mac is on."
    assert stat.S_IMODE(mac.home.stat().st_mode) == 0o700
    plist = mac.plist.read_text(encoding="latin-1")
    assert "MANIJERO_" not in plist and FAKE_TOKEN not in plist and "nightly_eval.py" in plist
    again = mac.init("--nightly-eval-on")
    assert again.returncode == 0 and "already on" in one_clean_result(again)
    assert [call.split()[0] for call in mac.calls()].count("bootstrap") == 1
    waiting = mac.init("--nightly-eval-status")
    assert waiting.returncode == 1 and "No run has finished yet." in waiting.stdout
    assert one_clean_result(waiting) == "Result: the nightly evaluation is on. No run has finished yet."

    # Step 2 with a failing metrics program: the run fails and says what to do.
    (mac.flags / "fail").write_text("", encoding="utf-8")
    failed = mac.init("--nightly-eval-run")
    assert failed.returncode == 1, failed.stdout
    assert "Code: ask_failed. No scores were recorded." in failed.stdout
    assert one_clean_result(failed).startswith("Result: the nightly evaluation failed.")
    status = mac.init("--nightly-eval-status")
    assert status.returncode == 1 and "Last run: something failed" in status.stdout
    one_clean_result(status)

    # Recovery: the first good run has nothing to compare with.
    (mac.flags / "fail").unlink()
    recovered = mac.init("--nightly-eval-run")
    assert recovered.returncode == 0, recovered.stdout
    assert "this is the first run, so nothing was compared" in recovered.stdout
    assert one_clean_result(recovered) == "Result: the nightly evaluation finished. No score dropped."
    assert (mac.home / "latest-summary.txt").read_text(encoding="utf-8").strip() == "\n".join(
        line for line in recovered.stdout.splitlines() if not line.startswith("Result:"))
    healthy = mac.init("--nightly-eval-status")
    assert healthy.returncode == 0 and "Last run: evaluated, finished " in healthy.stdout
    assert one_clean_result(healthy) == "Result: the nightly evaluation is on and the last run was evaluated."

    # A dropping run sends one fixed message to the fake Telegram and still exits 0.
    mac.store_telegram()
    mac.set_scores({**SCORES, "mrr": 0.6, "numeric": 0.5})
    with FakeServer() as server:
        mac.api = server.api
        dropped = mac.init("--nightly-eval-run")
        assert dropped.returncode == 0, dropped.stdout
        assert one_clean_result(dropped).startswith("Result: the nightly evaluation finished and 2 score(s) dropped.")
        assert [(path, body["chat_id"]) for path, body in server.requests] == [
            ("/bot{}/sendMessage".format(FAKE_TOKEN), CHAT_ID)]
        text = server.requests[0][1]["text"]
        assert text == (
            "Manijero nightly evaluation: 2 score(s) dropped since the last run: average source rank score (MRR) "
            "0.7500 -> 0.6000; numbers and dates correct 80.0% -> 50.0%. First step: open the health dashboard, "
            "then run ./scripts/init.sh --nightly-eval-status.")
        after = mac.init("--nightly-eval-status")
        assert after.returncode == 0 and "Alert: one message was sent to your phone." in after.stdout
        assert len(server.requests) == 1  # status never sends

    # A drop with Telegram unreachable is recorded; status then needs attention (exit 1).
    mac.set_scores({**SCORES, "mrr": 0.3})
    unsent = mac.init("--nightly-eval-run")
    assert unsent.returncode == 0 and "Alert: the message was not sent." in unsent.stdout
    needs = mac.init("--nightly-eval-status")
    assert needs.returncode == 1 and "./scripts/init.sh --qa-alerts-test" in needs.stdout
    one_clean_result(needs)

    # The ledger holds ids, codes, counts, scores, and times only.
    ledger = (mac.home / "nightly-eval-ledger.jsonl").read_text(encoding="utf-8")
    assert [json.loads(line)["event"] for line in ledger.splitlines()] == ["run_started", "run_finished"] * 4
    assert FAKE_TOKEN not in ledger and str(CHAT_ID) not in ledger
    assert stat.S_IMODE((mac.home / "nightly-eval-ledger.jsonl").stat().st_mode) == 0o600

    # Step 4: turn off; the history stays, and a second off changes nothing.
    stopped = mac.init("--nightly-eval-off")
    assert stopped.returncode == 0 and one_clean_result(stopped) == "Result: the nightly evaluation is off. Your history is kept."
    assert not mac.plist.exists() and (mac.home / "nightly-eval-ledger.jsonl").exists()
    again_off = mac.init("--nightly-eval-off")
    assert again_off.returncode == 0 and "already off" in one_clean_result(again_off)
    assert mac.init("--nightly-eval-status").returncode == 1
    assert all(call.split()[0] in ("print", "bootstrap", "bootout") for call in mac.calls())  # nothing else was asked
    assert all(LABEL in call for call in mac.calls() if call.split()[0] in ("print", "bootout"))
    assert all(call.endswith(LABEL + ".plist") for call in mac.calls() if call.split()[0] == "bootstrap")


def test_turning_on_without_launchctl_changes_nothing(mac: Mac) -> None:
    completed = mac.init("--nightly-eval-on", extra={"MANIJERO_LAUNCHCTL_CLI": str(mac.tmp / "no-launchctl-here")})
    assert completed.returncode == 2
    assert completed.stdout.splitlines()[0] == (
        "The macOS launchctl tool was not found; the nightly evaluation needs macOS. Run this command on the Mac.")
    one_clean_result(completed)
    assert not mac.home.exists() and not mac.agents.exists()


def test_a_second_run_while_one_is_working_starts_nothing(mac: Mac) -> None:
    assert mac.init("--nightly-eval-on").returncode == 0
    handle = os.open(mac.home / "nightly-eval.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = mac.init("--nightly-eval-run")
    finally:
        os.close(handle)
    assert completed.returncode == 3
    assert one_clean_result(completed) == "Result: nothing was started because a run is already in progress."
    assert not (mac.home / "nightly-eval-ledger.jsonl").exists()


def test_the_telegram_override_must_be_loopback(mac: Mac) -> None:
    completed = mac.init("--nightly-eval-status", extra={"MANIJERO_TELEGRAM_API": "https://api.telegram.org"})
    assert completed.returncode == 2 and "MANIJERO_TELEGRAM_API" in completed.stdout
    one_clean_result(completed)
