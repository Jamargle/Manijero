"""The health dashboard owner commands through ``./scripts/init.sh``: dispatch, early stops, misuse.

Each run uses a temporary ``MANIJERO_LOCAL_HOME`` and ``MANIJERO_QA_HOME``, an empty
``MANIJERO_VENV_ROOT``, and either a missing or a fake ``MANIJERO_DOCKER_CLI``. The fake Docker is
a small shell script that records every call, answers ``info`` as open or closed, and answers every
``inspect`` as "no such object"; it never pulls or runs anything. The full start and stop logic runs
against an in-memory fake in ``test_local_monitoring.py``.
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
COMMANDS = ["--monitoring-start", "--monitoring-status", "--monitoring-stop"]

pytestmark = pytest.mark.skipif(
    not os.access(BACKEND_ROOT / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_DOCKER = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
case "$1" in
  info) if [ -f "{open_flag}" ]; then echo 27.3.1; exit 0; fi; echo 'Cannot connect to the Docker daemon' >&2; exit 1 ;;
  image|container|network|volume) echo 'Error: No such object' >&2; exit 1 ;;
  *) exit 0 ;;
esac
"""


def free_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


def fake_docker(tmp_path: Path, open_: bool) -> Path:
    script = tmp_path / "bin" / "docker"
    script.parent.mkdir(exist_ok=True)
    script.write_text(
        FAKE_DOCKER.format(calls=tmp_path / "docker-calls.txt", open_flag=tmp_path / "docker-open"), encoding="utf-8"
    )
    script.chmod(0o755)
    if open_:
        (tmp_path / "docker-open").write_text("", encoding="utf-8")
    return script


def docker_calls(tmp_path: Path) -> List[str]:
    path = tmp_path / "docker-calls.txt"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def run_init(tmp_path: Path, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_LOCAL_HOME": str(tmp_path / "home"),
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
            "MANIJERO_DOCKER_CLI": str(tmp_path / "no-docker-here"),
            "MANIJERO_MONITORING_PORT": free_port(),
            "MANIJERO_LOCAL_RAG_PORT": free_port(),
            "MANIJERO_PILOT_TOKEN_FILE": str(tmp_path / "no-token-file"),
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


@pytest.mark.parametrize("mode, code", zip(COMMANDS, [1, 1, 0]))
def test_without_docker_each_command_names_the_install_step_or_has_nothing_to_stop(tmp_path: Path, mode: str, code: int) -> None:
    completed = run_init(tmp_path, mode)

    assert completed.returncode == code, completed.stdout + completed.stderr
    assert len(results(completed)) == 1
    if mode == "--monitoring-stop":
        assert completed.stdout.splitlines() == ["Result: the health dashboard was not running, so there was nothing to stop."]
    elif mode == "--monitoring-status":
        assert "Install Docker Desktop from https://www.docker.com/products/docker-desktop/" in completed.stdout
        assert completed.stdout.splitlines()[-1] == "Result: the health dashboard is not running. Start it with ./scripts/init.sh --monitoring-start."
    else:
        assert completed.stdout.splitlines()[-1].endswith(
            "Install Docker Desktop from https://www.docker.com/products/docker-desktop/, open it once, then run this command again."
        )
        assert completed.stdout.splitlines()[-1].startswith("Result: the health dashboard did not start.")
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("mode", COMMANDS)
def test_with_docker_desktop_closed_each_command_says_so(tmp_path: Path, mode: str) -> None:
    docker = fake_docker(tmp_path, open_=False)

    completed = run_init(tmp_path, mode, extra={"MANIJERO_DOCKER_CLI": str(docker)})

    assert completed.returncode == (0 if mode == "--monitoring-stop" else 1), completed.stdout + completed.stderr
    if mode == "--monitoring-start":
        assert "Docker Desktop is not open" in completed.stdout
        assert completed.stdout.splitlines()[-1].endswith(
            "Open the Docker Desktop app, wait until it says it is running, then run this command again."
        )
    elif mode == "--monitoring-status":
        assert "Docker Desktop is not open" in completed.stdout
    assert all(call.split()[0] == "info" for call in docker_calls(tmp_path))
    assert not (tmp_path / "home").exists()


def test_with_docker_open_and_nothing_running_status_and_stop_report_it(tmp_path: Path) -> None:
    extra = {"MANIJERO_DOCKER_CLI": str(fake_docker(tmp_path, open_=True))}

    status = run_init(tmp_path, "--monitoring-status", extra=extra)
    stop = run_init(tmp_path, "--monitoring-stop", extra=extra)
    stop_again = run_init(tmp_path, "--monitoring-stop", extra=extra)

    assert status.returncode == 1 and status.stdout.splitlines()[-1].startswith("Result: the health dashboard is not running.")
    assert stop.returncode == 0 and stop.stdout.splitlines() == [
        "Result: the health dashboard was not running, so there was nothing to stop."
    ]
    assert stop_again.stdout == stop.stdout
    assert not [call for call in docker_calls(tmp_path) if call.split()[0] in ("run", "rm", "stop", "pull", "create")]


def test_a_busy_port_stops_the_start_with_one_fix_and_creates_nothing(tmp_path: Path) -> None:
    extra = {"MANIJERO_DOCKER_CLI": str(fake_docker(tmp_path, open_=True))}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        extra["MANIJERO_MONITORING_PORT"] = str(holder.getsockname()[1])

        completed = run_init(tmp_path, "--monitoring-start", extra=extra)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "is in use by another program." in completed.stdout
    assert completed.stdout.splitlines()[-1].startswith("Result: the health dashboard did not start. Close the other program")
    assert not [call for call in docker_calls(tmp_path) if call.split()[0] in ("run", "pull", "network", "volume") and call.split()[1:2] != ["inspect"]]


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_refused_with_exit_2(tmp_path: Path, mode: str) -> None:
    completed = run_init(tmp_path, mode, "extra")

    assert completed.returncode == 2
    assert "on its own, with nothing after it" in completed.stderr
    assert completed.stdout == ""


def test_a_bad_port_setting_is_refused_with_exit_2(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--monitoring-start", extra={"MANIJERO_MONITORING_PORT": "99999"})

    assert completed.returncode == 2
    assert "port numbers between 1 and 65535" in completed.stderr


def test_help_lists_the_three_commands(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--help")

    assert completed.returncode == 0
    for mode in COMMANDS:
        assert mode in completed.stdout
