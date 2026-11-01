"""The container owner commands through ``./scripts/init.sh``: dispatch, early stops, and misuse.

Each run uses a temporary ``MANIJERO_LOCAL_HOME``, an empty ``MANIJERO_VENV_ROOT``, a free
``MANIJERO_LOCAL_RAG_PORT``, a missing ``MANIJERO_OLLAMA_CLI``, and either a missing or a fake
``MANIJERO_DOCKER_CLI``. The fake Docker is a small shell script that records every call and
answers ``info`` as open or closed and every ``inspect`` as "no such object"; it never builds
or runs anything, and no real container is ever created.
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
COMMANDS = ["--container-build", "--container-start", "--container-status", "--container-stop"]

pytestmark = pytest.mark.skipif(
    not os.access(BACKEND_ROOT / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_DOCKER = """#!/bin/sh
printf '%s\\n' "$*" >> "{calls}"
case "$1" in
  info) if [ -f "{open_flag}" ]; then echo 27.3.1; exit 0; fi; echo 'Cannot connect to the Docker daemon' >&2; exit 1 ;;
  image|container) echo 'Error: No such object' >&2; exit 1 ;;
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
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
            "MANIJERO_OLLAMA_CLI": str(tmp_path / "no-ollama-here"),
            "MANIJERO_DOCKER_CLI": str(tmp_path / "no-docker-here"),
            "MANIJERO_LOCAL_RAG_PORT": free_port(),
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


@pytest.mark.parametrize("mode, code", zip(COMMANDS, [1, 1, 1, 0]))
def test_without_docker_each_command_names_the_install_step_or_has_nothing_to_stop(tmp_path: Path, mode: str, code: int) -> None:
    completed = run_init(tmp_path, mode)

    assert completed.returncode == code, completed.stdout + completed.stderr
    last = completed.stdout.splitlines()[-1]
    if mode == "--container-stop":
        assert completed.stdout.splitlines() == [
            "Result: the answer service in the container was not running, so there was nothing to stop."
        ]
    elif mode == "--container-status":
        assert "Install Docker Desktop from https://www.docker.com/products/docker-desktop/" in completed.stdout
        assert last == "Result: the answer service in the container is not running. Start it with ./scripts/init.sh --container-start."
    else:
        assert last.endswith(
            "Install Docker Desktop from https://www.docker.com/products/docker-desktop/, open it once, then run this command again."
        )
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("mode", COMMANDS)
def test_with_docker_desktop_closed_each_command_says_so(tmp_path: Path, mode: str) -> None:
    docker = fake_docker(tmp_path, open_=False)

    completed = run_init(tmp_path, mode, extra={"MANIJERO_DOCKER_CLI": str(docker)})

    assert completed.returncode == (0 if mode == "--container-stop" else 1), completed.stdout + completed.stderr
    if mode in ("--container-build", "--container-start"):
        assert "Docker Desktop is not open" in completed.stdout
        assert completed.stdout.splitlines()[-1].endswith(
            "Open the Docker Desktop app, wait until it says it is running, then run this command again."
        )
    elif mode == "--container-status":
        assert "Docker Desktop is not open" in completed.stdout
    assert all(call.split()[0] == "info" for call in docker_calls(tmp_path))
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("mode", ["--container-build", "--container-start"])
def test_with_an_empty_home_build_and_start_name_the_setup_command_and_write_nothing(tmp_path: Path, mode: str) -> None:
    docker = fake_docker(tmp_path, open_=True)

    completed = run_init(tmp_path, mode, extra={"MANIJERO_DOCKER_CLI": str(docker)})

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup" in completed.stdout
    result = completed.stdout.splitlines()[-1]
    assert result.startswith(("Result: the image was not built.", "Result: the answer service in the container did not start."))
    assert "Run ./scripts/init.sh --local-rag-setup." in result
    assert not [call for call in docker_calls(tmp_path) if call.split()[0] in ("build", "run", "rm", "stop", "tag")]
    assert not (tmp_path / "home").exists()


def test_with_docker_open_and_no_container_status_and_stop_report_nothing_running(tmp_path: Path) -> None:
    docker = fake_docker(tmp_path, open_=True)
    extra = {"MANIJERO_DOCKER_CLI": str(docker)}

    status = run_init(tmp_path, "--container-status", extra=extra)
    stop = run_init(tmp_path, "--container-stop", extra=extra)

    assert status.returncode == 1 and status.stdout.splitlines()[-1].startswith("Result: the answer service in the container is not running.")
    assert stop.returncode == 0 and stop.stdout.splitlines() == [
        "Result: the answer service in the container was not running, so there was nothing to stop."
    ]
    assert [call.split()[0] for call in docker_calls(tmp_path)] == ["info", "container", "info", "container"]
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_or_a_bad_port_is_misuse(tmp_path: Path, mode: str) -> None:
    extra = run_init(tmp_path, mode, "now")
    assert extra.returncode == 2 and "on its own" in extra.stderr and not extra.stdout

    for value in ("0", "65536", "abc"):
        bad_port = run_init(tmp_path, mode, extra={"MANIJERO_LOCAL_RAG_PORT": value})
        assert bad_port.returncode == 2 and "between 1 and 65535" in bad_port.stderr
        assert not bad_port.stdout
    assert not (tmp_path / "home").exists()
    assert not docker_calls(tmp_path)
