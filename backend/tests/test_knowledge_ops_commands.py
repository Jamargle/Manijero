"""The knowledge update owner commands through ``./scripts/init.sh``: the automated owner walkthrough.

The owner guide (``docs/owner-guide/knowledge-updates.md``) replaces a manual walkthrough with this
test: every documented command is run through ``scripts/init.sh`` exactly as the guide writes it, with
one missing-prerequisite case and one recovery. Each run uses temporary folders, a fake ``launchctl``
(a shell script that records its arguments), and a fake step program, so the real launchctl, the
internet, Ollama, and every secret are never touched.
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

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
GUIDE = REPO_ROOT / "docs" / "owner-guide" / "knowledge-updates.md"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
COMMANDS = ["--knowledge-updates-on", "--knowledge-updates-run", "--knowledge-updates-status", "--knowledge-updates-off"]
LABEL = "org.manijero.knowledge-ops"

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

# The child step program: succeeds, except classify while the "ollama-down" flag file exists.
FAKE_STEP = """#!{python}
import os, sys
sys.path.insert(0, {backend!r})
from pathlib import Path
from app import knowledge_ops as ops

step, run_dir = sys.argv[2], Path(sys.argv[4])
if step == "classify" and (Path({flags!r}) / "ollama-down").exists():
    ops.write_child_result(run_dir, step, failure=ops.StepFailure("model_not_running"))
    raise SystemExit(1)
counts = {{
    "discover": {{"new_candidates": 3, "pages_changed": 0}},
    "classify": {{"relevant": 2, "unsure": 1, "not_relevant": 0}},
    "ingest": {{"documents_ingested": 3, "documents_failed": 0}},
    "impact": {{"impact_findings": 1}},
    "validity": {{"validity_proposals": 0}},
    "review": {{"impact_findings": 1, "validity_proposals": 0}},
}}[step]
if step == "review":
    (run_dir / "review").mkdir(exist_ok=True)
    (run_dir / "review" / "REVIEW.md").write_text("fake review\\n", encoding="utf-8")
ops.write_child_result(run_dir, step, counts=counts)
"""


class Mac:
    """One temporary Mac: folders, a fake launchctl, a fake step program."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "knowledge-ops"
        self.agents = tmp_path / "LaunchAgents"
        self.flags = tmp_path / "flags"
        self.flags.mkdir()
        (tmp_path / "bin").mkdir()
        self.launchctl = self._script("launchctl", FAKE_LAUNCHCTL.format(calls=tmp_path / "launchctl-calls.txt"))
        self.step = self._script("step", FAKE_STEP.format(python=sys.executable, backend=str(BACKEND_ROOT), flags=str(self.flags)))

    def _script(self, name: str, body: str) -> Path:
        script = self.tmp / "bin" / name
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
        return script

    @property
    def plist(self) -> Path:
        return self.agents / (LABEL + ".plist")

    def calls(self) -> List[str]:
        path = self.tmp / "launchctl-calls.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(os.environ)
        env.update({
            "MANIJERO_KNOWLEDGE_OPS_HOME": str(self.home),
            "MANIJERO_KNOWLEDGE_OPS_STEP_CLI": str(self.step),
            "MANIJERO_KNOWLEDGE_OPS_NO_WAIT": "1",
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
    assert "Traceback" not in completed.stdout + completed.stderr
    return results(completed)[0]


def test_the_guide_documents_exactly_the_four_commands_the_walkthrough_runs() -> None:
    documented = set(re.findall(r"\./scripts/init\.sh (--knowledge-updates-[a-z]+)", GUIDE.read_text(encoding="utf-8")))
    assert documented == set(COMMANDS)
    assert len(GUIDE.read_text(encoding="utf-8").splitlines()) <= 60


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
    # Missing prerequisite: run and status before turning the schedule on change nothing.
    for mode in ("--knowledge-updates-run", "--knowledge-updates-status"):
        before = mac.init(mode)
        assert before.returncode == 2, before.stdout
        assert before.stdout.splitlines()[0] == (
            "Knowledge updates are not set up yet. Run ./scripts/init.sh --knowledge-updates-on, then try again.")
        one_clean_result(before)
    assert not mac.home.exists() and mac.calls() == []

    # Step 1: turn on, then again.
    first = mac.init("--knowledge-updates-on")
    assert first.returncode == 0, first.stdout
    assert one_clean_result(first) == (
        "Result: knowledge updates are on. A run starts every day at 10:20 while this Mac is awake.")
    assert stat.S_IMODE(mac.home.stat().st_mode) == 0o700
    assert (mac.home / "source-monitor.json").is_file() and (mac.home / "page-monitor.json").is_file()
    assert mac.plist.is_file() and "MANIJERO_" not in mac.plist.read_text(encoding="latin-1")
    again = mac.init("--knowledge-updates-on")
    assert again.returncode == 0 and "already on" in one_clean_result(again)
    assert [call.split()[0] for call in mac.calls()].count("bootstrap") == 1
    assert all(LABEL in call for call in mac.calls() if call.split()[0] in ("print", "bootout"))
    assert all(call.endswith(LABEL + ".plist") for call in mac.calls() if call.split()[0] == "bootstrap")

    # Nothing has run yet.
    waiting = mac.init("--knowledge-updates-status")
    assert waiting.returncode == 0 and "No run has finished yet." in waiting.stdout
    assert one_clean_result(waiting) == "Result: knowledge updates are on. No run has finished yet."

    # Step 2 with a stopped drafting program: the run fails and names the first thing to do.
    (mac.flags / "ollama-down").write_text("", encoding="utf-8")
    failed = mac.init("--knowledge-updates-run")
    assert failed.returncode == 1, failed.stdout
    assert "Sort them by relevance: failed after 3 tries. The local drafting program (Ollama) is not running." in failed.stdout
    assert "First thing to do: open Ollama, then run ./scripts/init.sh --knowledge-updates-run again." in failed.stdout
    assert len([line for line in failed.stdout.splitlines() if not line.startswith("Result:")]) <= 15
    assert one_clean_result(failed).startswith("Result: the knowledge update run failed.")
    status = mac.init("--knowledge-updates-status")
    assert status.returncode == 1 and "Last run: something failed" in status.stdout
    one_clean_result(status)

    # Recovery: Ollama is back; the same command now ends at review ready.
    (mac.flags / "ollama-down").unlink()
    recovered = mac.init("--knowledge-updates-run")
    assert recovered.returncode == 0, recovered.stdout
    assert "How it went: ready for your review." in recovered.stdout
    assert ops_summary_line(recovered) == "Nothing was published. You approve every change before it goes live."
    assert one_clean_result(recovered) == "Result: the knowledge update run is ready for your review. Open the summary above."
    assert (mac.home / "latest-summary.txt").read_text(encoding="utf-8").strip() == "\n".join(
        line for line in recovered.stdout.splitlines() if not line.startswith("Result:"))
    events = [json.loads(line)["event"] for line in (mac.home / "knowledge-ops-ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events == ["run_started", "run_finished", "run_started", "run_finished"]

    # Step 3: status is healthy.
    healthy = mac.init("--knowledge-updates-status")
    assert healthy.returncode == 0 and "Summary: " in healthy.stdout
    assert one_clean_result(healthy) == "Result: knowledge updates are on and the last run is ready for your review."

    # Step 4: turn off; the history stays, and a second off changes nothing.
    off = mac.init("--knowledge-updates-off")
    assert off.returncode == 0 and one_clean_result(off) == "Result: knowledge updates are off. Your history is kept."
    assert not mac.plist.exists() and (mac.home / "knowledge-ops-ledger.jsonl").exists()
    off_again = mac.init("--knowledge-updates-off")
    assert off_again.returncode == 0 and "already off" in one_clean_result(off_again)
    after = mac.init("--knowledge-updates-status")
    assert after.returncode == 1 and "Knowledge updates are off." in after.stdout
    assert all(call.split()[0] in ("print", "bootstrap", "bootout") for call in mac.calls())  # nothing else was asked of launchctl


def ops_summary_line(completed: subprocess.CompletedProcess) -> str:
    return [line for line in completed.stdout.splitlines() if not line.startswith("Result:")][-1]


def test_turning_on_without_launchctl_changes_nothing(mac: Mac) -> None:
    completed = mac.init("--knowledge-updates-on", extra={"MANIJERO_LAUNCHCTL_CLI": str(mac.tmp / "no-launchctl-here")})
    assert completed.returncode == 2
    assert completed.stdout.splitlines()[0] == (
        "The macOS launchctl tool was not found; scheduled updates need macOS. Run this command on the Mac.")
    one_clean_result(completed)
    assert not mac.home.exists() and not mac.agents.exists()


def test_a_second_run_while_one_is_working_starts_nothing(mac: Mac) -> None:
    assert mac.init("--knowledge-updates-on").returncode == 0
    handle = os.open(mac.home / "knowledge-ops.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = mac.init("--knowledge-updates-run")
    finally:
        os.close(handle)
    assert completed.returncode == 3
    assert completed.stdout.splitlines()[0].startswith("A knowledge update run is already in progress.")
    assert one_clean_result(completed) == "Result: nothing was started because a run is already in progress."
    assert not (mac.home / "knowledge-ops-ledger.jsonl").exists()


def test_turning_off_when_it_was_never_on_changes_nothing(mac: Mac) -> None:
    completed = mac.init("--knowledge-updates-off")
    assert completed.returncode == 0 and "already off" in one_clean_result(completed)
    assert not mac.home.exists()
