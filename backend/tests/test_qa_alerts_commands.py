"""The QA alert owner commands through ``./scripts/init.sh``, and the launchd ``check`` entry point.

Each run uses temporary alerts, QA, and LaunchAgents folders, a fake ``launchctl`` / Docker /
Tailscale (small shell scripts that record their arguments), and a fake Telegram server on a
loopback test socket (``MANIJERO_TELEGRAM_API``). Only fake tokens are used; the real ``launchctl``,
Docker, Tailscale, Telegram, and internet are never touched.
"""

from __future__ import annotations

import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from app import environment_profiles as profiles
from app import qa_alerts as alerts
from test_qa_alerts import CHAT_ID, FAKE_TOKEN, FakeServer, START

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
ENTRY = BACKEND_ROOT / "scripts" / "qa_alerts.py"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
COMMANDS = ["--qa-alerts-setup", "--qa-alerts-start", "--qa-alerts-stop", "--qa-alerts-status", "--qa-alerts-test"]
LABEL = "org.manijero.qa-alerts"

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

FAKE_DOCKER_CLOSED = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
exit 1
"""

FAKE_TAILSCALE = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
echo '{{"BackendState": "NeedsLogin", "Self": {{}}}}'
exit 0
"""


def free_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


def fake(tmp_path: Path, name: str, body: str) -> Path:
    script = tmp_path / "bin" / name
    script.parent.mkdir(exist_ok=True)
    script.write_text(body.format(calls=tmp_path / (name + "-calls.txt")), encoding="utf-8")
    script.chmod(0o755)
    return script


def calls(tmp_path: Path, name: str) -> List[str]:
    path = tmp_path / (name + "-calls.txt")
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def environment(tmp_path: Path, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "MANIJERO_ALERTS_HOME": str(tmp_path / "alerts"),
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_LOCAL_HOME": str(tmp_path / "local"),
            "MANIJERO_LAUNCH_AGENTS_DIR": str(tmp_path / "LaunchAgents"),
            "MANIJERO_LAUNCHCTL_CLI": str(fake(tmp_path, "launchctl", FAKE_LAUNCHCTL)),
            "MANIJERO_DOCKER_CLI": str(tmp_path / "no-docker-here"),
            "MANIJERO_TAILSCALE_CLI": str(tmp_path / "no-tailscale-here"),
            "MANIJERO_QA_PORT": free_port(),
            "MANIJERO_TELEGRAM_API": "http://127.0.0.1:9",  # nothing listens unless a test starts a fake
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
        }
    )
    env.update(extra or {})
    return env


def run(argv: List[str], env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, cwd=REPO_ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180, check=False
    )


def run_init(tmp_path: Path, mode: str, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return run([str(INIT), mode, *args], environment(tmp_path, extra))


def results(completed: subprocess.CompletedProcess) -> List[str]:
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


def prepare_qa(tmp_path: Path) -> None:
    qa_home = tmp_path / "qa"
    qa_home.mkdir(exist_ok=True)
    (qa_home / "settings.env").write_text(profiles.render_template(qa_home), encoding="utf-8")
    profiles.make_new_credentials(qa_home, profiles.QA_CLIENT_ID)
    profiles.write_public_url(qa_home, "https://secretname-mac.tail1234.ts.net")


def store_telegram(tmp_path: Path) -> None:
    alerts.write_credentials(tmp_path / "alerts", alerts.Credentials(FAKE_TOKEN, CHAT_ID))


def assert_one_clean_result(completed: subprocess.CompletedProcess) -> None:
    assert len(results(completed)) == 1 and completed.stdout.splitlines()[-1] == results(completed)[0], completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr
    assert FAKE_TOKEN not in completed.stdout + completed.stderr and str(CHAT_ID) not in completed.stdout + completed.stderr


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_misuse(tmp_path: Path, mode: str) -> None:
    completed = run_init(tmp_path, mode, "extra")
    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run {} on its own, with nothing after it.".format(mode)
    assert completed.stdout == "" and calls(tmp_path, "launchctl") == []


def test_help_lists_the_five_commands(tmp_path: Path) -> None:
    completed = run([str(INIT), "--help"], environment(tmp_path))
    assert completed.returncode == 0
    for mode in COMMANDS:
        assert mode in completed.stdout


def test_the_telegram_override_must_be_loopback(tmp_path: Path) -> None:
    store_telegram(tmp_path)
    completed = run_init(tmp_path, "--qa-alerts-test", extra={"MANIJERO_TELEGRAM_API": "https://api.telegram.org"})
    assert completed.returncode == 2 and "MANIJERO_TELEGRAM_API must look like http://127.0.0.1:<port>." in completed.stderr
    assert completed.stdout == ""


def test_setup_without_a_terminal_stops_and_writes_nothing(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-alerts-setup")
    assert completed.returncode == 1
    assert results(completed) == ["Result: Telegram alerts were not set up. Run this command in a Terminal window you can type in."]
    assert not (tmp_path / "alerts").exists()
    assert_one_clean_result(completed)


def test_the_test_alert_reaches_the_fake_telegram_and_never_prints_the_details(tmp_path: Path) -> None:
    store_telegram(tmp_path)
    with FakeServer() as server:
        completed = run_init(tmp_path, "--qa-alerts-test", extra={"MANIJERO_TELEGRAM_API": server.api})
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert results(completed) == ["Result: a test alert was sent. Check Telegram on your phone."]
    assert [(path, body["text"]) for path, body in server.requests] == [
        ("/bot{}/sendMessage".format(FAKE_TOKEN), "Manijero QA: this is a test alert. If you can read it, alerts reach you.")
    ]
    assert server.requests[0][1]["chat_id"] == CHAT_ID
    assert_one_clean_result(completed)


@pytest.mark.parametrize(
    "status, words",
    [(401, "did not accept the bot token"), (403, "would not deliver to your chat"), (502, "could not be reached")],
)
def test_the_test_alert_explains_a_refusal(tmp_path: Path, status: int, words: str) -> None:
    store_telegram(tmp_path)
    with FakeServer(reply_status=status, reply={"ok": False}) as server:
        completed = run_init(tmp_path, "--qa-alerts-test", extra={"MANIJERO_TELEGRAM_API": server.api})
    assert completed.returncode == 1
    assert words in completed.stdout and results(completed)[0].startswith("Result: the test alert was not sent. ")
    assert_one_clean_result(completed)


def test_the_test_alert_without_details_or_with_open_permissions_sends_nothing(tmp_path: Path) -> None:
    with FakeServer() as server:
        extra = {"MANIJERO_TELEGRAM_API": server.api}
        missing = run_init(tmp_path, "--qa-alerts-test", extra=extra)
        assert missing.returncode == 1 and "not set up yet" in missing.stdout and "--qa-alerts-setup" in missing.stdout
        store_telegram(tmp_path)
        os.chmod(alerts.credentials_path(tmp_path / "alerts"), 0o644)
        open_file = run_init(tmp_path, "--qa-alerts-test", extra=extra)
        assert open_file.returncode == 1 and "cannot be used" in open_file.stdout
    assert server.requests == []
    assert_one_clean_result(missing)
    assert_one_clean_result(open_file)


def test_start_status_stop_with_a_fake_launchctl(tmp_path: Path) -> None:
    prepare_qa(tmp_path)
    store_telegram(tmp_path)
    uid = os.getuid()
    plist = tmp_path / "LaunchAgents" / (LABEL + ".plist")

    off = run_init(tmp_path, "--qa-alerts-status")
    assert off.returncode == 1 and results(off) == [
        "Result: QA alerts are off. Turn them on with ./scripts/init.sh --qa-alerts-start."
    ]

    start = run_init(tmp_path, "--qa-alerts-start")
    assert start.returncode == 0, start.stdout + start.stderr
    assert results(start) == ["Result: QA alerts are on. The check runs every 5 minutes while this Mac is awake."]
    assert plist.exists()
    assert calls(tmp_path, "launchctl")[-1] == "bootstrap gui/{} {}".format(uid, plist)

    again = run_init(tmp_path, "--qa-alerts-start")
    assert again.returncode == 0 and results(again) == ["Result: QA alerts are already on; nothing was changed."]
    assert [c for c in calls(tmp_path, "launchctl") if c.startswith("bootstrap")] == ["bootstrap gui/{} {}".format(uid, plist)]

    waiting = run_init(tmp_path, "--qa-alerts-status")
    assert waiting.returncode == 1 and "Last check: none yet" in waiting.stdout

    alerts.save_state(
        tmp_path / "alerts",
        alerts.State(last_check={"at": alerts.stamp(START), "outcome": "ok", "send_failed": False}),
    )
    stale = run_init(tmp_path, "--qa-alerts-status")
    assert stale.returncode == 1 and "the Mac may have been asleep" in stale.stdout

    fresh = alerts.stamp(datetime.now(timezone.utc))
    alerts.save_state(tmp_path / "alerts", alerts.State(last_check={"at": fresh, "outcome": "ok", "send_failed": False}))
    healthy = run_init(tmp_path, "--qa-alerts-status")
    assert healthy.returncode == 0 and results(healthy) == ["Result: QA alerts are on and the last check found no problem."]
    assert [line.split()[0] for line in healthy.stdout.splitlines()[:-1]] == ["OK"] * 4

    stop = run_init(tmp_path, "--qa-alerts-stop")
    assert stop.returncode == 0 and results(stop) == ["Result: QA alerts are off."]
    assert not plist.exists() and alerts.credentials_path(tmp_path / "alerts").exists() and alerts.state_path(tmp_path / "alerts").exists()
    nothing = run_init(tmp_path, "--qa-alerts-stop")
    assert nothing.returncode == 0 and results(nothing) == ["Result: QA alerts were not on, so there was nothing to stop."]

    for completed in (off, start, again, waiting, stale, healthy, stop, nothing):
        assert_one_clean_result(completed)
    for call in calls(tmp_path, "launchctl"):
        assert call.split()[0] in ("print", "bootstrap", "bootout") and LABEL in call, call


def test_start_refuses_before_writing_anything_when_a_prerequisite_is_missing(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-alerts-start")
    assert completed.returncode == 1
    assert "Telegram alerts are not set up yet." in completed.stdout
    assert "QA settings file does not exist" in completed.stdout
    assert results(completed)[0].startswith("Result: QA alerts were not turned on. ") and "--qa-alerts-setup" in results(completed)[0]
    assert not (tmp_path / "LaunchAgents").exists() and calls(tmp_path, "launchctl") == []
    assert_one_clean_result(completed)


def test_the_launchd_check_alerts_through_the_fake_telegram_after_two_checks(tmp_path: Path) -> None:
    prepare_qa(tmp_path)
    store_telegram(tmp_path)
    docker = fake(tmp_path, "docker", FAKE_DOCKER_CLOSED)
    tailscale = fake(tmp_path, "tailscale", FAKE_TAILSCALE)
    with FakeServer() as server:
        env = environment(
            tmp_path,
            {"MANIJERO_TELEGRAM_API": server.api, "MANIJERO_DOCKER_CLI": str(docker), "MANIJERO_TAILSCALE_CLI": str(tailscale)},
        )
        first = run([str(VENV_PYTHON), str(ENTRY), "check"], env)
        assert first.returncode == 0 and server.requests == []
        second = run([str(VENV_PYTHON), str(ENTRY), "check"], env)
    assert second.returncode == 0
    assert [body["text"] for _, body in server.requests] == [
        "Manijero QA: QA is down: Docker Desktop is not open. Open Docker Desktop, then run ./scripts/init.sh --qa-deploy."
    ]
    for completed in (first, second):
        assert completed.stdout == "" and completed.stderr == ""
    log = alerts.log_path(tmp_path / "alerts").read_text(encoding="utf-8")
    assert log.count("outcome=down_docker") == 2
    everything = log + alerts.state_path(tmp_path / "alerts").read_text(encoding="utf-8") + "".join(calls(tmp_path, "docker"))
    for secret in (FAKE_TOKEN, str(CHAT_ID), "ts.net", "secretname"):
        assert secret not in everything
    assert calls(tmp_path, "launchctl") == []


def test_the_entry_point_rejects_an_unknown_operation() -> None:
    completed = subprocess.run(
        [str(VENV_PYTHON), str(ENTRY), "restart-everything"], capture_output=True, text=True, timeout=60, check=False
    )
    assert completed.returncode == 2
