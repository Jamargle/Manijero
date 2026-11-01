"""The owner commands through ``./scripts/init.sh``: dispatch, early stops, and read-only status.

Each run uses a temporary ``MANIJERO_LOCAL_HOME`` and an empty ``MANIJERO_VENV_ROOT`` (so no
shared hybrid environment is found or linked), and either a missing or a fake
``MANIJERO_OLLAMA_CLI``. Nothing is downloaded or built; the only network use is the
loopback Ollama probe the commands make themselves.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
from typing import Dict, Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"

pytestmark = pytest.mark.skipif(
    not os.access(BACKEND_ROOT / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)


def run_init(tmp_path: Path, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_LOCAL_HOME": str(tmp_path / "home"),
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
            "MANIJERO_OLLAMA_CLI": str(tmp_path / "no-ollama-here"),
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


def ollama_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


def fake_ollama_cli(tmp_path: Path) -> Path:
    script = tmp_path / "bin" / "ollama"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def test_setup_without_ollama_names_the_install_step_and_changes_nothing(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--local-rag-setup")

    assert completed.returncode == 1
    assert "https://ollama.com/download" in completed.stdout
    assert completed.stdout.splitlines()[-1] == "Result: setup stopped before changing anything."
    assert not (tmp_path / "home").exists()
    assert not (tmp_path / "venvs").exists()


def test_status_before_setup_names_the_setup_command_and_writes_nothing(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--local-rag-status")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    lines = completed.stdout.splitlines()
    assert sum(1 for line in lines if line.split(None, 1)[:1] in (["OK"], ["MISSING"], ["PROBLEM"])) == 6
    assert lines[-1] == "Result: setup has not run yet. Run ./scripts/init.sh --local-rag-setup to set everything up."
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "home").exists()
    assert not (tmp_path / "venvs").exists()


@pytest.mark.skipif(ollama_port_open(), reason="a real Ollama is serving on 127.0.0.1:11434 on this machine")
def test_setup_with_ollama_closed_says_to_open_it(tmp_path: Path) -> None:
    cli = fake_ollama_cli(tmp_path)

    completed = run_init(tmp_path, "--local-rag-setup", extra={"MANIJERO_OLLAMA_CLI": str(cli)})

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "Open the Ollama app" in completed.stdout
    assert completed.stdout.splitlines()[-1] == "Result: setup stopped before changing anything."
    assert not (tmp_path / "home").exists()


@pytest.mark.skipif(ollama_port_open(), reason="a real Ollama is serving on 127.0.0.1:11434 on this machine")
def test_status_with_ollama_closed_is_a_problem_line(tmp_path: Path) -> None:
    cli = fake_ollama_cli(tmp_path)

    completed = run_init(tmp_path, "--local-rag-status", extra={"MANIJERO_OLLAMA_CLI": str(cli)})

    assert completed.returncode == 1
    assert "PROBLEM  Drafting model: Ollama is not running. Open the Ollama app" in completed.stdout


@pytest.mark.parametrize("mode", ["--local-rag-setup", "--local-rag-status"])
def test_an_extra_argument_is_misuse(tmp_path: Path, mode: str) -> None:
    completed = run_init(tmp_path, mode, "now")

    assert completed.returncode == 2
    assert not (tmp_path / "home").exists()
