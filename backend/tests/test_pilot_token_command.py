"""The owner command ``./scripts/init.sh --pilot-token-save`` (client_pilot_credentials).

Every run uses a fake clipboard script through ``MANIJERO_CLIPBOARD_CLI``, a temporary
``MANIJERO_PILOT_TOKEN_FILE``, and an empty ``MANIJERO_VENV_ROOT``, so the owner's real
``pilot-token.local`` is never read or written and only fake tokens are used.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"

FAKE_TOKEN = "fakeTokenForTestsOnly-0123456789abcdefABCDEF+/="
OTHER_FAKE_TOKEN = "otherFakeTokenForTestsOnly-0123456789abcdef~._"

SAVED = "Result: the pilot token is saved. The next test build will send it."
REPLACED = "Result: the pilot token is saved; it replaced the previous one. The next test build will send it."
EMPTY = "Result: the clipboard is empty. Copy the pilot token first, then run this command again."
NOT_A_TOKEN = (
    "Result: the clipboard does not hold a pilot token. Copy the whole token again, "
    "then run this command again."
)
NO_CLIPBOARD = "Result: this command could not read the clipboard; it needs a Mac. Ask the developer for help."


def fake_clipboard(tmp_path: Path, content: Optional[bytes]) -> Path:
    """A clipboard tool that prints ``content`` exactly, or a missing path when ``None``."""

    tool = tmp_path / "fake-pbpaste"
    if content is None:
        return tool
    payload = tmp_path / "clipboard.bin"
    payload.write_bytes(content)
    tool.write_text(f"#!/bin/sh\ncat '{payload}'\n")
    tool.chmod(0o755)
    return tool


def save(tmp_path: Path, clipboard: Optional[bytes]) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_CLIPBOARD_CLI": str(fake_clipboard(tmp_path, clipboard)),
            "MANIJERO_PILOT_TOKEN_FILE": str(token_file(tmp_path)),
            "MANIJERO_VENV_ROOT": str(tmp_path / "no-venvs"),
            "PATH": "/usr/bin:/bin",
        }
    )
    return subprocess.run(
        [str(INIT), "--pilot-token-save"],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def token_file(tmp_path: Path) -> Path:
    return tmp_path / "tokens" / "pilot-token.local"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "tokens").mkdir()
    return tmp_path


def assert_no_token_in(result: subprocess.CompletedProcess, *tokens: str) -> None:
    output = result.stdout + result.stderr
    for token in tokens:
        assert token not in output
        assert str(len(token)) not in output


def test_saves_exactly_the_trimmed_token_privately(workspace: Path) -> None:
    result = save(workspace, f"  \t{FAKE_TOKEN}\n".encode())

    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == [SAVED]
    saved = token_file(workspace)
    assert saved.read_text() == FAKE_TOKEN
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert sorted(p.name for p in saved.parent.iterdir()) == ["pilot-token.local"]
    assert_no_token_in(result, FAKE_TOKEN)


def test_a_rerun_reports_the_replacement(workspace: Path) -> None:
    assert save(workspace, FAKE_TOKEN.encode()).returncode == 0

    result = save(workspace, f"{OTHER_FAKE_TOKEN}\r\n".encode())

    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == [REPLACED]
    assert token_file(workspace).read_text() == OTHER_FAKE_TOKEN
    assert stat.S_IMODE(token_file(workspace).stat().st_mode) == 0o600
    assert_no_token_in(result, FAKE_TOKEN, OTHER_FAKE_TOKEN)


@pytest.mark.parametrize(
    ("clipboard", "expected"),
    [
        (b"", EMPTY),
        (b" \n\t\n", EMPTY),
        (b"a" * 31, NOT_A_TOKEN),
        (b"a" * 513, NOT_A_TOKEN),
        (f"{FAKE_TOKEN}\nsecond-line".encode(), NOT_A_TOKEN),
        (f"{FAKE_TOKEN} extra".encode(), NOT_A_TOKEN),
        (f"{FAKE_TOKEN}ñ".encode(), NOT_A_TOKEN),
        (f"{FAKE_TOKEN}\U0001F600".encode(), NOT_A_TOKEN),
        (f"{FAKE_TOKEN};x".encode(), NOT_A_TOKEN),
        (f"{FAKE_TOKEN}=x".encode(), NOT_A_TOKEN),
    ],
)
def test_a_refused_clipboard_writes_nothing_and_keeps_the_previous_file(
    workspace: Path, clipboard: bytes, expected: str
) -> None:
    previous = token_file(workspace)
    previous.write_bytes(b"previous fake content\n")
    previous.chmod(0o600)

    result = save(workspace, clipboard)

    assert result.returncode != 0
    assert result.stdout.strip().splitlines() == [expected]
    assert previous.read_bytes() == b"previous fake content\n"
    assert sorted(p.name for p in previous.parent.iterdir()) == ["pilot-token.local"]
    assert result.stderr == ""


def test_a_refused_first_save_creates_no_file(workspace: Path) -> None:
    result = save(workspace, b"short")

    assert result.returncode != 0
    assert result.stdout.strip().splitlines() == [NOT_A_TOKEN]
    assert list(token_file(workspace).parent.iterdir()) == []


def test_a_missing_clipboard_tool_gives_the_plain_message(workspace: Path) -> None:
    result = save(workspace, None)

    assert result.returncode != 0
    assert result.stdout.strip().splitlines() == [NO_CLIPBOARD]
    assert not token_file(workspace).exists()


def test_the_command_is_listed_in_the_help_and_dispatched_before_any_toolchain_step() -> None:
    # Read the script text instead of running --help, which would go through the Android setup.
    script = INIT.read_text()
    usage = script[script.index("usage() {"):]

    assert "--pilot-token-save" in usage[: usage.index("EOF\n}")]
    dispatch = script.index('if [[ "${1:-}" == "--pilot-token-save" ]]; then')
    for later_step in ("python-env.sh", "local.properties", "./gradlew", "MANIJERO_VENV_ROOT"):
        if later_step in script:
            assert dispatch < script.index(later_step)
