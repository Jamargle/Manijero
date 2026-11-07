"""The QA check orchestrator with a fake runner, fake probe, fake QA home, and fake address file.

Offline: no Gradle, QA, Tailscale, network, or real key. The key file holds a fake value that must
never be read or printed.
"""

from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

import pytest

from app import local_smoke as smoke
from app import qa_check as check

ADDRESS = "https://qa.example.org"
FAKE_KEY = "fake-qa-access-key-that-must-never-be-read-or-printed-0123456789"
OK = "MANIJERO_QA_CHECK_RESULT outcome=answered sources=2 feedback=sent address=default url=" + ADDRESS


def result(outcome: str = "answered", sources: int = 2, feedback: str = "sent", address: str = "default", url: str = ADDRESS) -> str:
    return "MANIJERO_QA_CHECK_RESULT outcome={} sources={} feedback={} address={} url={}".format(
        outcome, sources, feedback, address, url
    )


class FakeRunner:
    def __init__(self) -> None:
        self.calls: List[Dict[str, object]] = []
        self.result: Optional[str] = OK + "\n"
        self.fail = False
        self.time_out = False
        self.interrupt = False

    def run(self, argv: Sequence[str], cwd: Path, log_path: Path, timeout: float, env: Optional[Mapping[str, str]] = None) -> smoke.RunResult:
        argv = [str(part) for part in argv]
        self.calls.append({"argv": argv, "timeout": timeout, "log": Path(log_path), "cwd": Path(cwd), "env": env})
        if self.interrupt:
            raise KeyboardInterrupt
        if self.time_out:
            return smoke.RunResult(None, True)
        target = next(part.split("=", 1)[1] for part in argv if part.startswith("-PmanijeroSmokeResult="))
        if self.result is not None:
            Path(target).write_text(self.result, encoding="utf-8")
        return smoke.RunResult(1 if self.fail else 0)


class FakeTools:
    def __init__(self) -> None:
        self.java = True

    def java_available(self) -> bool:
        return self.java

    def adb_path(self) -> Optional[str]:
        raise AssertionError("the QA check never uses adb")


class Check:
    def __init__(self, tmp_path: Path) -> None:
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        gradlew = self.repo / "gradlew"
        gradlew.write_text("#!/bin/sh\n", encoding="utf-8")
        gradlew.chmod(0o755)
        self.home = tmp_path / "qa"
        (self.home / "credentials").mkdir(parents=True)
        self.key = self.home / "credentials" / "qa-test-device.token"
        self.key.write_text(FAKE_KEY, encoding="utf-8")
        self.address_file = tmp_path / "qa-address.local"
        self.address_file.write_text(ADDRESS + "\n", encoding="utf-8")
        self.runner = FakeRunner()
        self.tools = FakeTools()
        self.probes: List[str] = []
        self.reachable = True
        self.lines: List[str] = []

    def probe(self, address: str) -> bool:
        self.probes.append(address)
        return self.reachable

    def run(self) -> int:
        ports = check.QaCheckPorts(
            runner=self.runner, tools=self.tools, probe=self.probe, out=self.lines.append,
            address_file=self.address_file, qa_home=self.home,
        )
        return check.run_qa_check(self.repo, ports)

    @property
    def dir(self) -> Path:
        return self.repo / "build" / "qa-check"


@pytest.fixture
def c(tmp_path: Path) -> Check:
    return Check(tmp_path)


# --- 1. Everything passes ----------------------------------------------------------------------


def test_everything_passes(c: Check) -> None:
    assert c.run() == 0, c.lines
    assert c.lines == [
        "Checking the QA service at {}...".format(ADDRESS),
        "PASS  Service: QA answers at {}.".format(ADDRESS),
        "Checking the QA Desktop app (the first run can take a few minutes)...",
        "PASS  Answer: the QA app asked the test question and showed an answer with 2 source cards.",
        "PASS  Feedback: QA accepted the app's Útil rating.",
        "Result: the QA check passed: QA is reachable, answers with sources, and accepts feedback from the Desktop app.",
    ]
    (call,) = c.runner.calls
    assert call["argv"] == [
        str(c.repo / "gradlew"), "--console=plain", "--quiet", "-PmanijeroEnvironment=qa", ":shared:runDesktopQaCheck",
        "-PmanijeroSmokeExpected=" + ADDRESS,
        "-PmanijeroSmokeResult={}".format(c.dir / "desktop-result.txt"),
    ]
    assert call["timeout"] == 15 * 60 and call["log"] == c.dir / "desktop.log" and call["cwd"] == c.repo
    assert c.probes == [ADDRESS]
    assert sorted(p.name for p in c.dir.iterdir()) == [".lock", "desktop-result.txt"]


def test_a_trailing_slash_in_the_address_file_is_dropped_and_one_card_reads_as_one(c: Check) -> None:
    c.address_file.write_text(ADDRESS + "/\n", encoding="utf-8")
    c.runner.result = result(sources=1) + "\n"
    assert c.run() == 0
    assert c.lines[0] == "Checking the QA service at {}...".format(ADDRESS)
    assert "an answer with 1 source card." in c.lines[3]


# --- 2. A prerequisite is missing ---------------------------------------------------------------


def _write_address(text: str) -> Callable[[Check], None]:
    return lambda c: c.address_file.write_text(text, encoding="utf-8")


DEPLOY = "Deploy QA with ./scripts/init.sh --qa-deploy, then run this command again."
SETUP = "Run ./scripts/init.sh --qa-settings-setup, then run this command again."


@pytest.mark.parametrize(
    "arrange, line, fix",
    [
        (lambda c: c.address_file.unlink(), check.MSG_NO_ADDRESS, DEPLOY),
        (_write_address("  \n"), check.MSG_NO_ADDRESS, DEPLOY),
        (_write_address("https://qa.manijero.invalid\n"), check.MSG_PLACEHOLDER, DEPLOY),
        (_write_address("http://qa.example.org\n"), check.MSG_NOT_HTTPS, DEPLOY),
        (_write_address("qa.example.org\n"), check.MSG_NOT_HTTPS, DEPLOY),
        (lambda c: c.key.unlink(), check.MSG_NO_KEY, SETUP),
        (lambda c: setattr(c.tools, "java", False), smoke.MSG_NO_JAVA, smoke.FIX_JAVA),
        (lambda c: (c.repo / "gradlew").chmod(0o644), smoke.MSG_NO_WRAPPER, smoke.FIX_WRAPPER),
    ],
)
def test_a_missing_prerequisite_stops_before_anything_runs(c: Check, arrange, line: str, fix: str) -> None:
    arrange(c)

    assert c.run() == 1
    assert c.lines == [line, "Result: the QA check did not run. " + fix]
    assert c.runner.calls == [] and c.probes == []


def test_another_check_running_stops_the_run(c: Check) -> None:
    c.dir.mkdir(parents=True)
    handle = os.open(c.dir / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert c.run() == 1
    finally:
        os.close(handle)
    assert c.lines == [
        "Another QA check is running in another Terminal window.",
        "Result: the QA check did not run. Wait for it to finish, then run this command again.",
    ]
    assert c.runner.calls == []


def test_the_key_file_is_only_tested_for_existence_never_opened(c: Check, monkeypatch: pytest.MonkeyPatch) -> None:
    c.key.chmod(0)  # unreadable: an existence test still passes, an open would fail
    opened: List[str] = []
    real_open = Path.open

    def spy(self, *args, **kwargs):
        opened.append(str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    try:
        assert c.run() == 0, c.lines
    finally:
        c.key.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert str(c.key) not in opened


# --- 3. QA is not reachable ----------------------------------------------------------------------


def test_an_unreachable_service_fails_before_any_build(c: Check) -> None:
    c.reachable = False

    assert c.run() == 1
    assert c.lines == [
        "Checking the QA service at {}...".format(ADDRESS),
        "FAIL  Service: QA does not answer at {}.".format(ADDRESS),
        "Result: the QA check failed at the service step. Run ./scripts/init.sh --qa-status and do its first step, "
        "then run this command again.",
    ]
    assert c.runner.calls == []


# --- 4. / 5. The app steps ------------------------------------------------------------------------

STATUS = "Run ./scripts/init.sh --qa-status and do its first step, then run this command again."
SEND = "Send build/qa-check/desktop.log to a developer."
ANSWER_FAILED = "Result: the QA check failed at the answer step. Do the first step shown above."
FEEDBACK_FAILED = "Result: the QA check failed at the feedback step. Do the first step shown above."


@pytest.mark.parametrize(
    "outcome, feedback, text",
    [
        ("abstained", "sent", "the QA app showed an honest abstention (Sin respuesta segura) instead of an answer with sources. " + SEND),
        ("answered_without_sources", "sent", "the QA app showed an answer without any source card. " + SEND),
        ("land_clarification", "not_tried", "the QA app asked to choose a land instead of answering the general test question. " + SEND),
        ("unreachable", "not_tried", "the QA app could not reach the QA service at {}. {}".format(ADDRESS, STATUS)),
        ("service_error", "not_tried", "the QA service answered the app with an error. " + STATUS),
        ("not_ready", "not_tried", "the QA app reached {}, but it cannot answer questions right now. {}".format(ADDRESS, STATUS)),
        ("ready_unknown", "not_tried", "the QA app reached {}, but could not tell whether it can answer. {}".format(ADDRESS, STATUS)),
        ("not_manijero", "not_tried", "the program at {} is not the Manijero answer service. {}".format(ADDRESS, STATUS)),
        ("no_answer", "not_tried", "the QA app showed no reply within 90 seconds. " + STATUS),
    ],
)
def test_each_answer_failure_names_one_step(c: Check, outcome: str, feedback: str, text: str) -> None:
    c.runner.result = result(outcome=outcome, sources=0, feedback=feedback) + "\n"

    assert c.run() == 1
    assert c.lines[3] == "FAIL  Answer: " + text
    assert c.lines[-1] == ANSWER_FAILED


def test_a_zero_source_answered_line_fails_the_answer_step(c: Check) -> None:
    c.runner.result = result(outcome="answered", sources=0) + "\n"
    assert c.run() == 1
    assert c.lines[3] == "FAIL  Answer: the QA app showed an answer without any source card. " + SEND


def test_a_saved_other_address_names_the_connection_screen_step(c: Check) -> None:
    c.runner.result = result(outcome="other_address", sources=0, feedback="not_tried", address="saved", url="https://old.example.org") + "\n"

    assert c.run() == 1
    assert c.lines[3] == (
        "FAIL  Answer: the QA app uses the saved address https://old.example.org, not {}. In ./scripts/init.sh "
        "--desktop-qa open Ayuda > Herramientas de prueba > Conexión, press Usar la dirección predeterminada, then run "
        "this command again.".format(ADDRESS)
    )
    assert len(c.lines) == 5 and c.lines[-1] == ANSWER_FAILED  # no feedback line without a finished reply


@pytest.mark.parametrize(
    "feedback, text",
    [
        ("failed", "QA did not accept the app's Útil rating. " + STATUS),
        ("no_reply", "QA did not confirm the app's Útil rating within 30 seconds. " + STATUS),
        ("not_shown", "the QA app showed no rating buttons. " + SEND),
    ],
)
def test_each_feedback_failure_names_one_step(c: Check, feedback: str, text: str) -> None:
    c.runner.result = result(feedback=feedback) + "\n"

    assert c.run() == 1
    assert c.lines[3].startswith("PASS  Answer:")
    assert c.lines[4] == "FAIL  Feedback: " + text
    assert c.lines[-1] == FEEDBACK_FAILED


def test_a_qa_without_feedback_tells_the_owner_to_update_qa(c: Check) -> None:
    c.runner.result = result(feedback="not_on_qa") + "\n"

    assert c.run() == 1
    assert c.lines[3].startswith("PASS  Answer:")
    assert c.lines[4] == (
        "FAIL  Feedback: QA runs an older version that does not accept ratings yet. From the up-to-date main "
        "checkout run ./scripts/init.sh --container-build, then ./scripts/init.sh --qa-update (answer yes), "
        "then run ./scripts/init.sh --qa-check again."
    )
    assert "--qa-status" not in c.lines[4]
    assert c.lines[-1] == FEEDBACK_FAILED


def test_the_result_names_the_answer_step_when_both_fail(c: Check) -> None:
    c.runner.result = result(outcome="abstained", sources=0, feedback="failed") + "\n"

    assert c.run() == 1
    assert c.lines[3].startswith("FAIL  Answer:") and c.lines[4].startswith("FAIL  Feedback:")
    assert c.lines[-1] == ANSWER_FAILED


# --- 6. The check cannot run -----------------------------------------------------------------------

COULD_NOT_RUN = "FAIL  Answer: the check could not run. Details are in build/qa-check/desktop.log; send that file to a developer."


@pytest.mark.parametrize(
    "arrange",
    [
        lambda c: setattr(c.runner, "fail", True),
        lambda c: setattr(c.runner, "time_out", True),
        lambda c: setattr(c.runner, "result", None),
        lambda c: setattr(c.runner, "result", "garbage\n"),
        lambda c: setattr(c.runner, "result", OK + "\n" + OK + "\n"),
        lambda c: setattr(c.runner, "result", OK + " extra=1\n"),
        lambda c: setattr(c.runner, "result", result(outcome="error", sources=0, feedback="not_tried") + "\n"),
    ],
)
def test_a_check_that_cannot_run_says_so_and_points_to_the_log(c: Check, arrange) -> None:
    arrange(c)

    assert c.run() == 1
    assert c.lines[3] == COULD_NOT_RUN
    assert c.lines[-1] == ANSWER_FAILED
    assert len(c.lines) == 5


@pytest.mark.parametrize(
    "outcome, line",
    [
        (
            "not_qa_build",
            "FAIL  Answer: the check app was not built as the QA app, so no question was asked. "
            "Send build/qa-check/desktop.log to a developer.",
        ),
        (
            "no_access_key",
            "FAIL  Answer: the QA access key did not reach the check app, so no question was asked. "
            "Run ./scripts/init.sh --qa-settings-setup, then run this command again.",
        ),
    ],
)
def test_a_well_formed_not_run_outcome_gets_its_own_plain_line(c: Check, outcome: str, line: str) -> None:
    c.runner.result = result(outcome=outcome, sources=0, feedback="not_tried", url="invalid") + "\n"

    assert c.run() == 1
    assert c.lines[3] == line
    assert "could not run" not in line
    assert c.lines[-1] == ANSWER_FAILED
    assert len(c.lines) == 5


# --- 7. Interruption --------------------------------------------------------------------------------


def test_ctrl_c_ends_the_check_with_the_stopped_lines(c: Check) -> None:
    c.runner.interrupt = True

    assert c.run() == 1
    assert c.lines[-2:] == ["The QA check was stopped.", "Result: the QA check was stopped before it finished."]


# --- 8. Safety and privacy ---------------------------------------------------------------------------


def test_no_output_or_file_carries_the_key_and_the_key_stays_out_of_the_command(c: Check) -> None:
    assert c.run() == 0
    everything = "\n".join(c.lines) + "\n".join(str(call["argv"]) + str(call["env"]) for call in c.runner.calls)
    for path in c.dir.iterdir():
        if path.is_file():
            everything += path.read_text(encoding="utf-8")
    assert FAKE_KEY not in everything
    assert all(call["env"] is None for call in c.runner.calls)
    assert not any("token" in part.lower() or "key" in part.lower() for call in c.runner.calls for part in call["argv"])  # type: ignore[union-attr]


def test_the_log_and_result_file_never_carry_the_key_on_any_path(c: Check) -> None:
    real_run = c.runner.run

    def run_and_log(argv, cwd, log_path, timeout, env=None):  # type: ignore[no-untyped-def]
        Path(log_path).write_text("gradle log line\n", encoding="utf-8")
        return real_run(argv, cwd, log_path, timeout, env)

    c.runner.run = run_and_log  # type: ignore[method-assign]
    for result in (OK + "\n", None, "garbage\n"):
        c.runner.result = result
        c.run()
        written = sorted(path for path in c.dir.iterdir() if path.is_file())
        assert any(path.name == check.LOG_NAME for path in written)
        assert all(FAKE_KEY not in path.read_text(encoding="utf-8") for path in written)
        assert FAKE_KEY not in "\n".join(c.lines)
    assert FAKE_KEY not in str(c.dir)


def test_parse_result_accepts_only_the_one_exact_line() -> None:
    parsed = check.parse_result(OK + "\n")
    assert parsed == check.QaCheckResult("answered", 2, "sent", "default", ADDRESS)
    assert check.parse_result("") is None
    assert check.parse_result(OK.replace("feedback=sent", "feedback=maybe")) is None
    assert check.parse_result(OK.replace("outcome=answered", "outcome=weird")) is None
