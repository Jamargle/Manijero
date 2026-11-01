"""The owner commands through ``./scripts/init.sh``: dispatch, early stops, read-only status, and
the local answer service commands (which never start a service here).

Each run uses a temporary ``MANIJERO_LOCAL_HOME`` and an empty ``MANIJERO_VENV_ROOT`` (so no
shared hybrid environment is found or linked), and either a missing or a fake
``MANIJERO_OLLAMA_CLI``. Nothing is downloaded or built; the only network use is the
loopback Ollama probe the commands make themselves.
"""

from __future__ import annotations

import json
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


# --- The local answer service commands (never start a service) ----------------------------


def free_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


def run_service(tmp_path: Path, *args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return run_init(tmp_path, *args, extra={"MANIJERO_LOCAL_RAG_PORT": free_port(), **(extra or {})})


def test_start_before_setup_names_the_setup_command_and_writes_nothing(tmp_path: Path) -> None:
    completed = run_service(tmp_path, "--local-rag-start")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines()[-1] == (
        "Result: the local answer service did not start. Run ./scripts/init.sh --local-rag-setup."
    )
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "home").exists()


def test_service_status_before_any_start_says_how_to_start(tmp_path: Path) -> None:
    completed = run_service(tmp_path, "--local-rag-service-status")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines()[-1] == (
        "Result: the local answer service is not running. Start it with ./scripts/init.sh --local-rag-start."
    )
    assert not (tmp_path / "home").exists()


def test_stop_when_nothing_runs_has_nothing_to_stop(tmp_path: Path) -> None:
    completed = run_service(tmp_path, "--local-rag-stop")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.splitlines() == ["Result: the local answer service was not running, so there was nothing to stop."]
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize("mode", ["--local-rag-service-status", "--local-rag-stop"])
def test_a_record_for_another_program_is_cleared_and_that_program_keeps_running(tmp_path: Path, mode: str) -> None:
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        record = tmp_path / "home" / "run" / "service.json"
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps({"pid": sleeper.pid, "port": 8000, "started_at": "2026-11-01T09:30:00Z", "release_id": "r", "log": "x"}),
            encoding="utf-8",
        )

        completed = run_service(tmp_path, mode)

        lines = completed.stdout.splitlines()
        assert lines[0] == "An earlier local answer service ended without being stopped; its leftover record was cleared."
        assert completed.returncode == (1 if mode.endswith("status") else 0), completed.stdout + completed.stderr
        assert not record.exists()
        assert sleeper.poll() is None  # never signalled
    finally:
        sleeper.kill()
        sleeper.wait()


@pytest.mark.parametrize("mode", ["--local-rag-start", "--local-rag-service-status", "--local-rag-stop"])
def test_an_extra_argument_or_a_bad_port_is_misuse_for_the_service_commands(tmp_path: Path, mode: str) -> None:
    extra = run_service(tmp_path, mode, "now")
    assert extra.returncode == 2 and "on its own" in extra.stderr

    for value in ("0", "65536", "abc"):
        bad_port = run_init(tmp_path, mode, extra={"MANIJERO_LOCAL_RAG_PORT": value})
        assert bad_port.returncode == 2 and "between 1 and 65535" in bad_port.stderr
        assert not bad_port.stdout
    assert not (tmp_path / "home").exists()


# --- The local smoke test command (never reaches Gradle or adb here) -----------------------

SMOKE_DIR = REPO_ROOT / "build" / "local-smoke"


def smoke_marks(tmp_path: Path) -> Dict[str, object]:
    """Everything a build, install, or app start would leave behind, to compare after a run."""

    marker = tmp_path / "adb-was-called"
    adb = tmp_path / "sdk" / "platform-tools" / "adb"
    if not adb.exists():
        adb.parent.mkdir(parents=True)
        adb.write_text("#!/bin/sh\ntouch " + str(marker) + "\n", encoding="utf-8")
        adb.chmod(0o755)
    logs = {
        name: (SMOKE_DIR / name).stat().st_mtime_ns if (SMOKE_DIR / name).exists() else None
        for name in ("desktop.log", "android.log", "desktop-result.txt")
    }
    return {"logs": logs, "local.properties": (REPO_ROOT / "local.properties").exists(), "adb": marker.exists()}


def run_smoke(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return run_service(tmp_path, "--local-smoke", *args, extra={"ANDROID_HOME": str(tmp_path / "sdk"), "ANDROID_SDK_ROOT": ""})


def test_local_smoke_with_an_extra_argument_is_misuse(tmp_path: Path) -> None:
    completed = run_smoke(tmp_path, "now")

    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run --local-smoke on its own, with nothing after it."
    assert not completed.stdout
    assert not (tmp_path / "home").exists()


def test_local_smoke_before_setup_says_to_set_up_and_builds_nothing(tmp_path: Path) -> None:
    before = smoke_marks(tmp_path)

    completed = run_smoke(tmp_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines() == [
        "Checking the local answer service...",
        "The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.",
        "Result: the smoke test did not run. Run ./scripts/init.sh --local-rag-setup.",
    ]
    assert "Traceback" not in completed.stdout + completed.stderr
    assert not (tmp_path / "home").exists()
    assert smoke_marks(tmp_path) == before
    assert before["adb"] is False


def _settings(tmp_path: Path) -> Path:
    settings = tmp_path / "home" / "settings.env"
    settings.parent.mkdir(parents=True)
    settings.write_text("MANIJERO_ACTIVE_CAMPAIGN=2026\n", encoding="utf-8")
    return settings


def test_local_smoke_with_no_service_running_says_how_to_start_it(tmp_path: Path) -> None:
    _settings(tmp_path)
    before = smoke_marks(tmp_path)

    completed = run_smoke(tmp_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines() == [
        "Checking the local answer service...",
        "The local answer service is not running.",
        "Result: the smoke test did not run. Start it with ./scripts/init.sh --local-rag-start, then run this command again.",
    ]
    assert smoke_marks(tmp_path) == before
    assert not (tmp_path / "home" / "run").exists()


def test_local_smoke_clears_a_record_for_another_program_and_never_signals_it(tmp_path: Path) -> None:
    _settings(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        record = tmp_path / "home" / "run" / "service.json"
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps({"pid": sleeper.pid, "port": 8000, "started_at": "2026-11-01T09:30:00Z", "release_id": "r", "log": "x"}),
            encoding="utf-8",
        )
        before = smoke_marks(tmp_path)

        completed = run_smoke(tmp_path)

        assert completed.returncode == 1, completed.stdout + completed.stderr
        assert completed.stdout.splitlines()[1:] == [
            "An earlier local answer service ended without being stopped; its leftover record was cleared.",
            "The local answer service is not running.",
            "Result: the smoke test did not run. Start it with ./scripts/init.sh --local-rag-start, then run this command again.",
        ]
        assert not record.exists()
        assert sleeper.poll() is None
        assert smoke_marks(tmp_path) == before
    finally:
        sleeper.kill()
        sleeper.wait()
