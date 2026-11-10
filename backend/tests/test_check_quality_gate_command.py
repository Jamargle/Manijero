"""Command tests for the read-only quality gate.

Every test uses the real fixtures, ``knowledge/`` sample, and committed baseline unless
it copies the baseline to a temporary folder. Sockets are refused, nothing is written by
``check``, and no golden, trap, or judge file is read.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import socket
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
KNOWLEDGE = ROOT / "knowledge"
FIXTURES = BACKEND / "tests" / "fixtures"
BASELINE = BACKEND / "config" / "quality_gate_baseline.json"
SCRIPT = BACKEND / "scripts" / "check_quality_gate.py"

ENV_KEYS = (
    "MANIJERO_GENERATION_PROVIDER",
    "MANIJERO_LOCAL_MODEL",
    "MANIJERO_GEMINI_MODEL",
    "MANIJERO_ANSWER_TRACE",
    "MANIJERO_RERANKER",
    "MANIJERO_RETRIEVAL_MODE",
    "MANIJERO_STRUCTURED_INDEX",
    "MANIJERO_STRUCTURED_INDEX_DIR",
    "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    "MANIJERO_QUESTION_GLOSSARY",
    "MANIJERO_ANSWER_CACHE",
)


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("tests must not open a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_quality_gate_script", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _script()


def _run(
    argv: list[str],
    capsys: pytest.CaptureFixture,
    *,
    baseline: Path | None = None,
) -> tuple[int, str]:
    capsys.readouterr()
    code = SCRIPT_MODULE.main(argv, baseline_path=baseline)
    return code, capsys.readouterr().out


def _result_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("Result:")]


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _baseline_document() -> dict[str, Any]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _write_variant(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "quality_gate_baseline.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# --- scenario 1: unchanged inputs pass ------------------------------------------------------


def test_real_check_passes_with_one_line_and_writes_nothing(
    capsys: pytest.CaptureFixture,
) -> None:
    before_baseline = BASELINE.read_bytes()
    code, output = _run(["check"], capsys)

    assert code == 0
    assert output.count("\n") == 1
    lines = _result_lines(output)
    assert len(lines) == 1
    assert lines[0].startswith("Result: quality gate passed: fixtures ")
    review = _baseline_document()["review"]
    assert (
        f"Baseline reviewed by {review['reviewed_by']} on {review['reviewed_on']}."
        in lines[0]
    )
    assert BASELINE.read_bytes() == before_baseline


def test_knowledge_fixtures_and_baseline_are_byte_identical(
    capsys: pytest.CaptureFixture,
) -> None:
    knowledge = _tree_hashes(KNOWLEDGE)
    fixtures = _tree_hashes(FIXTURES)
    baseline = BASELINE.read_bytes()

    code, _ = _run(["check"], capsys)

    assert code == 0
    assert _tree_hashes(KNOWLEDGE) == knowledge
    assert _tree_hashes(FIXTURES) == fixtures
    assert BASELINE.read_bytes() == baseline


# --- scenario 4: only a reviewed, current baseline can gate --------------------------------


def test_stale_baseline_exit_2_without_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    document = _baseline_document()
    document["settings"]["as_of"] = "2026-10-14"
    path = _write_variant(tmp_path, document)

    code, output = _run(["check"], capsys, baseline=path)

    assert code == 2
    assert output.splitlines() == [
        SCRIPT_MODULE.quality_gate.not_enforced_line("baseline_stale")
    ]
    assert "fell from" not in output


def test_unreviewed_baseline_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    document = _baseline_document()
    document.pop("review")
    path = _write_variant(tmp_path, document)

    code, output = _run(["check"], capsys, baseline=path)

    assert code == 2
    assert output.splitlines() == [
        SCRIPT_MODULE.quality_gate.not_enforced_line("baseline_unreviewed")
    ]


# --- scenario 2: a regression blocks -------------------------------------------------------


def test_regression_exit_1_names_old_and_new(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    document = _baseline_document()
    retrieval = document["metrics"]["reviewed_retrieval"]
    retrieval["hits_at_1"] = min(
        retrieval["questions"], retrieval["hits_at_1"] + 1
    )
    assert retrieval["hits_at_1"] > _baseline_document()["metrics"][
        "reviewed_retrieval"
    ]["hits_at_1"]
    path = _write_variant(tmp_path, document)

    code, output = _run(["check"], capsys, baseline=path)

    assert code == 1
    lines = _result_lines(output)
    assert len(lines) == 1
    assert lines[0].startswith("Result: quality gate failed: reviewed sample hit@1 fell")
    assert lines[0].endswith(
        "A developer must review the change; if the new numbers are right, the owner "
        "reviews and records a new baseline."
    )


# --- scenario 6: read-only, offline, deterministic -----------------------------------------


def test_environment_keys_removed_then_restored(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    for index, key in enumerate(ENV_KEYS):
        monkeypatch.setenv(key, f"sentinel-{index}")

    with SCRIPT_MODULE._isolated_environment():
        for key in ENV_KEYS:
            if key == "MANIJERO_ANSWER_CACHE":
                assert SCRIPT_MODULE.os.environ[key] == "off"
            else:
                assert key not in SCRIPT_MODULE.os.environ
    for index, key in enumerate(ENV_KEYS):
        assert SCRIPT_MODULE.os.environ[key] == f"sentinel-{index}"

    code, _ = _run(["check"], capsys)

    assert code == 0
    for index, key in enumerate(ENV_KEYS):
        assert SCRIPT_MODULE.os.environ[key] == f"sentinel-{index}"


def test_golden_trap_and_judge_files_are_not_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    forbidden = {"golden_set.json", "trap_set.json", "grounding-judge.json"}
    original = Path.read_text

    def guarded(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name in forbidden:
            raise AssertionError(f"the gate must not read {self.name}")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)

    code, output = _run(["check"], capsys)

    assert code == 0
    assert len(_result_lines(output)) == 1


def test_two_runs_print_the_same_line(capsys: pytest.CaptureFixture) -> None:
    first_code, first = _run(["check"], capsys)
    second_code, second = _run(["check"], capsys)

    assert (first_code, second_code) == (0, 0)
    assert first == second


# --- scenario 5: record is the only writer -------------------------------------------------


def test_record_creates_first_baseline_and_reports_deltas(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = tmp_path / "quality_gate_baseline.json"

    code, output = _run(
        [
            "record",
            "--reviewer",
            "Jose",
            "--reason",
            "initial measured fixture baseline approved",
            "--reviewed-on",
            "2026-11-10",
        ],
        capsys,
        baseline=path,
    )

    assert code == 0
    assert path.is_file()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["review"] == {
        "reviewed_by": "Jose",
        "reviewed_on": "2026-11-10",
        "reason": "initial measured fixture baseline approved",
    }
    assert document["settings"] == SCRIPT_MODULE.quality_gate.SETTINGS
    assert path.read_text(encoding="utf-8") == SCRIPT_MODULE.quality_gate.canonical_json(
        document
    )
    lines = output.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("Result: baseline recorded: 0 metrics changed; reviewed by Jose")


def test_record_refuses_without_reviewer(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = tmp_path / "quality_gate_baseline.json"

    code, output = _run(
        ["record", "--reason", "no reviewer"], capsys, baseline=path
    )

    assert code == 2
    assert not path.exists()
    assert output.splitlines() == [
        "Result: baseline not recorded: the reviewer must be named."
    ]


# --- scenario 4: unexpected failures stay one fixed line ------------------------------------


def test_internal_error_prints_one_fixed_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def explode() -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(SCRIPT_MODULE, "measure", explode)

    code, output = _run(["check"], capsys)

    assert code == 2
    assert output.splitlines() == [
        SCRIPT_MODULE.quality_gate.not_enforced_line("internal_error")
    ]
    assert "boom" not in output
    assert "Traceback" not in output
