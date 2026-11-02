"""The environment commands through ``./scripts/init.sh``: dispatch, misuse, and secrecy.

Each run uses temporary ``MANIJERO_LOCAL_HOME`` and ``MANIJERO_QA_HOME`` folders and an empty
``MANIJERO_VENV_ROOT``. Nothing is deployed, downloaded, or contacted.
"""

from __future__ import annotations

import os
import stat
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


def run_init(
    tmp_path: Path, *args: str, extra: Optional[Dict[str, str]] = None, stdin: Optional[str] = None
) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_LOCAL_HOME": str(tmp_path / "local"),
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
        }
    )
    environment.update(extra or {})
    return subprocess.run(
        [str(INIT), *args],
        cwd=REPO_ROOT,
        env=environment,
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.mark.parametrize("flag", ["--environments-status", "--qa-settings-setup"])
def test_an_extra_argument_is_refused_and_changes_nothing(tmp_path: Path, flag: str) -> None:
    completed = run_init(tmp_path, flag, "extra")

    assert completed.returncode == 2
    assert "Run {} on its own, with nothing after it.".format(flag) in completed.stderr
    assert not (tmp_path / "qa").exists() and not (tmp_path / "local").exists()


def test_status_on_fresh_homes_prints_three_lines_and_the_result(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--environments-status")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    lines = completed.stdout.splitlines()
    assert [line.split(":")[0] for line in lines[:3]] == ["NOT SET UP  local", "NOT SET UP  QA", "NOT SET UP  prod"]
    assert lines[3] == "Result: the local environment is not set up yet. Run ./scripts/init.sh --local-rag-setup."
    assert not (tmp_path / "qa").exists() and not (tmp_path / "local").exists()


def test_qa_setup_creates_the_keys_and_never_prints_the_token(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-settings-setup")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.splitlines()[-1] == "Result: QA is prepared on this computer. Nothing was deployed."
    token_file = tmp_path / "qa" / "credentials" / "qa-test-device.token"
    token = token_file.read_text(encoding="utf-8")
    assert len(token) >= 32 and token not in completed.stdout + completed.stderr
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600

    again = run_init(tmp_path, "--qa-settings-setup")
    assert again.returncode == 0 and again.stdout.splitlines()[-1] == "Result: QA was already prepared; nothing was changed."


def test_recovery_without_a_terminal_changes_nothing(tmp_path: Path) -> None:
    assert run_init(tmp_path, "--qa-settings-setup").returncode == 0
    token_file = tmp_path / "qa" / "credentials" / "qa-test-device.token"
    token_file.unlink()

    completed = run_init(tmp_path, "--qa-settings-setup")

    assert completed.returncode == 1
    assert "Terminal window" in completed.stdout and not token_file.exists()
    status = run_init(tmp_path, "--environments-status")
    assert "PROBLEM  QA" in status.stdout and status.returncode == 1
