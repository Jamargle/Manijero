"""``./scripts/init.sh --qa-check``: dispatch, misuse, and the early stops that never build or reach QA.

Each run uses a temporary QA home and a temporary address file that is missing or a placeholder, so
no Gradle build starts and no network is used. No real key is read or printed.
"""

from __future__ import annotations

import os
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
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_QA_ADDRESS_FILE": str(tmp_path / "qa-address.local"),
            "MANIJERO_VENV_ROOT": str(tmp_path / "venvs"),
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


def test_an_extra_argument_is_misuse(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-check", "extra")

    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run --qa-check on its own, with nothing after it."
    assert completed.stdout == ""


def test_usage_lists_the_command() -> None:
    completed = subprocess.run([str(INIT), "--help"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False)

    assert "--qa-check" in completed.stdout + completed.stderr


def test_without_a_qa_address_it_says_to_deploy_and_builds_nothing(tmp_path: Path) -> None:
    completed = run_init(tmp_path, "--qa-check")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines() == [
        "No QA address is saved on this computer.",
        "Result: the QA check did not run. Deploy QA with ./scripts/init.sh --qa-deploy, then run this command again.",
    ]
    assert "Traceback" not in completed.stdout + completed.stderr


def test_with_a_placeholder_address_it_says_to_deploy(tmp_path: Path) -> None:
    (tmp_path / "qa-address.local").write_text("https://qa.manijero.invalid\n", encoding="utf-8")

    completed = run_init(tmp_path, "--qa-check")

    assert completed.returncode == 1
    assert completed.stdout.splitlines()[-1].startswith("Result: the QA check did not run. Deploy QA with ")


def test_without_an_access_key_it_says_to_run_the_settings_setup(tmp_path: Path) -> None:
    (tmp_path / "qa-address.local").write_text("https://qa.example.org\n", encoding="utf-8")

    completed = run_init(tmp_path, "--qa-check")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stdout.splitlines() == [
        "The QA access key was not found on this computer.",
        "Result: the QA check did not run. Run ./scripts/init.sh --qa-settings-setup, then run this command again.",
    ]
