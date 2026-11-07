"""The QA owner commands through ``./scripts/init.sh``: dispatch, early stops, and misuse.

Each run uses temporary QA and local homes, a temporary address file, a free ``MANIJERO_QA_PORT``,
and a missing or fake ``MANIJERO_DOCKER_CLI`` / ``MANIJERO_TAILSCALE_CLI``. The fakes are small shell
scripts that record every call and answer from files; nothing real is built, run, or shared, and
no token is read or printed.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
COMMANDS = ["--qa-deploy", "--qa-update", "--qa-rollback", "--qa-status", "--qa-stop"]

pytestmark = pytest.mark.skipif(
    not os.access(BACKEND_ROOT / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_DOCKER = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
case "$1" in
  info) echo 27.3.1; exit 0 ;;
  image|container) echo 'Error: No such object' >&2; exit 1 ;;
  *) exit 0 ;;
esac
"""

FAKE_TAILSCALE = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
case "$1" in
  status) echo '{{"BackendState": "NeedsLogin", "Self": {{}}}}'; exit 0 ;;
  *) exit 1 ;;
esac
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


def run_init(tmp_path: Path, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_LOCAL_HOME": str(tmp_path / "local"),
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_QA_ADDRESS_FILE": str(tmp_path / "qa-address.local"),
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
            "MANIJERO_OLLAMA_CLI": str(tmp_path / "no-ollama-here"),
            "MANIJERO_DOCKER_CLI": str(tmp_path / "no-docker-here"),
            "MANIJERO_TAILSCALE_CLI": str(tmp_path / "no-tailscale-here"),
            "MANIJERO_QA_PORT": free_port(),
        }
    )
    environment.update(extra or {})
    return subprocess.run(
        [str(INIT), *args],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def results(completed: subprocess.CompletedProcess) -> List[str]:
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_misuse(tmp_path: Path, mode: str) -> None:
    completed = run_init(tmp_path, mode, "extra")
    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run {} on its own, with nothing after it.".format(mode)
    assert completed.stdout == ""


def test_a_bad_port_setting_is_misuse(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-status", extra={"MANIJERO_QA_PORT": "http"})
    assert completed.returncode == 2
    assert "MANIJERO_QA_PORT must be a port number between 1 and 65535." in completed.stderr


@pytest.mark.parametrize("mode, op", [("--qa-deploy", "deployed"), ("--qa-update", "updated"), ("--qa-rollback", "rolled back")])
def test_without_tailscale_docker_or_qa_setup_nothing_is_changed(tmp_path: Path, mode: str, op: str) -> None:
    completed = run_init(tmp_path, mode)
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "Tailscale is not installed on this computer." in completed.stdout
    assert "Docker Desktop is not installed" in completed.stdout
    assert "QA is not prepared on this computer" in completed.stdout
    (result,) = results(completed)
    assert result.startswith("Result: QA was not {}. ".format(op)) and 'step "Set up Tailscale"' in result
    assert completed.stdout.splitlines()[-1] == result
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "qa-address.local").exists() and not (tmp_path / "qa").exists()


def test_with_tailscale_logged_out_and_docker_open_deploy_changes_nothing(tmp_path: Path) -> None:
    docker = fake(tmp_path, "docker", FAKE_DOCKER)
    tailscale = fake(tmp_path, "tailscale", FAKE_TAILSCALE)
    completed = run_init(
        tmp_path, "--qa-deploy", extra={"MANIJERO_DOCKER_CLI": str(docker), "MANIJERO_TAILSCALE_CLI": str(tailscale)}
    )
    assert completed.returncode == 1, completed.stdout
    assert "Tailscale is installed but not logged in or not turned on." in completed.stdout
    assert "There is no answer service image on this computer yet." in completed.stdout
    assert all(call.split()[0] in ("info", "image", "container") for call in calls(tmp_path, "docker"))
    assert all(call.split()[0] in ("status", "funnel") and "off" not in call for call in calls(tmp_path, "tailscale"))
    assert not (tmp_path / "qa-address.local").exists()


def test_status_with_nothing_running_and_stop_with_nothing_to_stop(tmp_path: Path) -> None:
    docker = fake(tmp_path, "docker", FAKE_DOCKER)
    extra = {"MANIJERO_DOCKER_CLI": str(docker)}
    status = run_init(tmp_path, "--qa-status", extra=extra)
    assert status.returncode == 1
    assert results(status) == ["Result: QA is not running. Start it with ./scripts/init.sh --qa-deploy."]
    stop = run_init(tmp_path, "--qa-stop", extra=extra)
    assert stop.returncode == 0
    assert results(stop) == ["Result: QA was not running, so there was nothing to stop."]
    assert not [call for call in calls(tmp_path, "docker") if call.split()[0] in ("stop", "rm", "run", "tag")]


def test_status_and_stop_without_docker_are_plain(tmp_path: Path) -> None:
    status = run_init(tmp_path, "--qa-status")
    assert status.returncode == 1 and results(status) == [
        "Result: QA is not running. Start it with ./scripts/init.sh --qa-deploy."
    ]
    stop = run_init(tmp_path, "--qa-stop")
    assert stop.returncode == 0 and results(stop) == ["Result: QA was not running, so there was nothing to stop."]
