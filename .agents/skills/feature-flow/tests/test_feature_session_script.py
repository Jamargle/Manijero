"""The harness launcher ``./scripts/feature-session.sh``.

Every run puts fake ``claude``, ``codex``, and ``opencode`` programs first on ``PATH`` that only
record their arguments and stdin, points ``MANIJERO_AGENT_LOG_DIR`` and ``GRADLE_USER_HOME`` at
temporary folders, and never starts a real agent.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[4]  # .agents/skills/feature-flow/tests/<this file>
SCRIPT = REPO_ROOT / "scripts" / "feature-session.sh"
FEATURE = "local_end_to_end_smoke"  # any id present in feature_list.json

CLAUDE_RESULT = {
    "type": "result",
    "result": "Feature accepted.",
    "num_turns": 12,
    "duration_ms": 90000,
    "total_cost_usd": 1.25,
    "modelUsage": {
        "claude-opus-5-5": {"inputTokens": 100, "outputTokens": 20, "cacheReadInputTokens": 1000,
                            "cacheCreationInputTokens": 50},
        "claude-sonnet-5-5": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 0,
                              "cacheCreationInputTokens": 0},
    },
}


def fake_agents(tmp_path: Path, claude_output: Optional[str] = None) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    record = tmp_path / "calls"
    for name in ("claude", "codex", "opencode"):
        output = claude_output if name == "claude" and claude_output is not None else "ok"
        tool = bin_dir / name
        tool.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > '{record}-{name}-args'\n"
            f"if [ ! -t 0 ]; then cat > '{record}-{name}-stdin'; fi\n"
            f"cat <<'OUT'\n{output}\nOUT\n"
        )
        tool.chmod(0o755)
    return bin_dir


def run(tmp_path: Path, *args: str, claude_output: Optional[str] = None) -> subprocess.CompletedProcess:
    bin_dir = fake_agents(tmp_path, claude_output)
    environment = dict(os.environ)
    environment.pop("JAVA_HOME", None)
    environment.pop("MANIJERO_AGENT", None)
    environment.update(
        {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "MANIJERO_AGENT_LOG_DIR": str(tmp_path / "sessions"),
            "GRADLE_USER_HOME": str(tmp_path / "gradle"),
            "MANIJERO_JAVA_HOME_TOOL": str(tmp_path / "no-java-home"),
        }
    )
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def lines(path: Path) -> list:
    return path.read_text().splitlines()


def test_interactive_claude_gets_the_prompt_as_an_argument(tmp_path: Path) -> None:
    result = run(tmp_path, FEATURE)
    assert result.returncode == 0, result.stderr
    assert lines(tmp_path / "calls-claude-args") == [f"Use feature-flow for {FEATURE} only, until accepted."]


def test_note_is_appended_to_the_prompt(tmp_path: Path) -> None:
    result = run(tmp_path, "--note", "Owner chose Docker Desktop.", FEATURE)
    assert result.returncode == 0, result.stderr
    assert lines(tmp_path / "calls-claude-args")[-1].endswith("Handoff from the orchestrator: Owner chose Docker Desktop.")


def test_headless_claude_scopes_tools_reads_stdin_and_logs_usage(tmp_path: Path) -> None:
    result = run(tmp_path, "--headless", FEATURE, claude_output=json.dumps(CLAUDE_RESULT))
    assert result.returncode == 0, result.stderr

    args = lines(tmp_path / "calls-claude-args")
    assert args[:4] == ["-p", "--output-format", "json", "--permission-mode"]
    allowed = args[args.index("--allowedTools") + 1]
    denied = args[args.index("--disallowedTools") + 1]
    assert "Bash(./scripts/*)" in allowed and "Bash(git commit:*)" in allowed
    assert "Bash(git push" not in allowed and "Bash(gh" not in allowed
    assert "Bash(git push:*)" in denied and "Bash(gh:*)" in denied
    assert not any("feature-flow" in arg for arg in args), "the prompt must not be a CLI argument"
    assert "Use feature-flow for" in (tmp_path / "calls-claude-stdin").read_text()

    assert "Feature accepted." in result.stdout
    assert "Usage: 12 turns, 1.5 min, input 110, output 25, cache read 1000, cache write 50" in result.stdout
    table = lines(tmp_path / "sessions" / "usage.tsv")
    assert table[0].startswith("stamp\tfeature\tturns")
    assert table[1].split("\t")[1:] == [FEATURE, "12", "1.5", "110", "25", "1000", "50", "1.2500"]


def test_headless_claude_without_json_still_finishes(tmp_path: Path) -> None:
    result = run(tmp_path, "--headless", FEATURE, claude_output="You've hit your limit")
    assert result.returncode == 0, result.stderr
    assert "Usage: not reported" in result.stdout
    assert not (tmp_path / "sessions" / "usage.tsv").exists()


def test_headless_codex_runs_in_a_writable_sandbox(tmp_path: Path) -> None:
    result = run(tmp_path, "--agent", "codex", "--headless", FEATURE)
    assert result.returncode == 0, result.stderr
    args = lines(tmp_path / "calls-codex-args")
    assert args[:3] == ["exec", "--full-auto", "--json"]
    assert args[-1].startswith(f"Use feature-flow for {FEATURE}")


def test_headless_opencode_uses_run(tmp_path: Path) -> None:
    result = run(tmp_path, "--agent", "opencode", "--headless", FEATURE)
    assert result.returncode == 0, result.stderr
    args = lines(tmp_path / "calls-opencode-args")
    assert args[0] == "run" and args[-1].startswith(f"Use feature-flow for {FEATURE}")


def test_unknown_feature_and_agent_are_refused(tmp_path: Path) -> None:
    assert run(tmp_path, "no_such_feature").returncode == 2
    assert run(tmp_path, "--agent", "gpt", FEATURE).returncode == 2
