"""The real ``:shared:runDesktopQaCheck`` task sees the QA environment and access key resources.

This runs the Gradle task itself against a fake QA setup: a fake access key and a fake address file in
a temporary folder (``MANIJERO_PILOT_TOKEN_FILE``, ``MANIJERO_QA_ADDRESS_FILE``) and a closed loopback
https port. Nothing leaves this computer and no real key is read. The expected result is a connection
failure; ``not_qa_build`` or ``no_access_key`` would mean the generated resources did not reach the
forked test JVM (the 2026-11-07 owner-walkthrough defect). It starts Gradle, so it only runs when
``MANIJERO_GRADLE_WIRING_TEST=1`` (the feature's focused tier sets it; ``--fast`` skips it).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app import qa_check as check

REPO_ROOT = Path(__file__).resolve().parents[2]
CLOSED_ADDRESS = "https://127.0.0.1:1"
FAKE_KEY = "fake-qa-access-key-that-must-never-be-printed-0123456789"

pytestmark = pytest.mark.skipif(
    os.environ.get("MANIJERO_GRADLE_WIRING_TEST") != "1",
    reason="starts Gradle; set MANIJERO_GRADLE_WIRING_TEST=1 (the focused tier does)",
)


def test_the_task_sees_the_qa_environment_and_key_resources(tmp_path: Path) -> None:
    key = tmp_path / "qa-test-device.token"
    key.write_text(FAKE_KEY)
    address = tmp_path / "qa-address.local"
    address.write_text(CLOSED_ADDRESS + "\n")
    result_file = tmp_path / "desktop-result.txt"
    environment = dict(os.environ)
    environment.update({"MANIJERO_PILOT_TOKEN_FILE": str(key), "MANIJERO_QA_ADDRESS_FILE": str(address)})

    run = subprocess.run(
        [
            str(REPO_ROOT / "gradlew"),
            "--console=plain",
            "--quiet",
            "-PmanijeroEnvironment=qa",
            check.GRADLE_TASK,
            "-PmanijeroSmokeExpected=" + CLOSED_ADDRESS,
            "-PmanijeroSmokeResult=" + str(result_file),
        ],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=check.BUILD_TIMEOUT_SECONDS,
    )

    assert run.returncode == 0, "Gradle failed; see its log"
    parsed = check.parse_result(result_file.read_text())
    assert parsed is not None
    assert parsed.outcome not in ("not_qa_build", "no_access_key")
    assert parsed.outcome == "unreachable"
    assert parsed.url == CLOSED_ADDRESS
    assert FAKE_KEY not in run.stdout + run.stderr + result_file.read_text()
