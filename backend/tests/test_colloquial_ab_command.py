"""Command tests for the colloquial variant review and the three-arm report.

The owner walkthrough runs the real command module with a temporary copy of the committed
variants. The report test uses a temporary copy with every variant approved, a fake rewriter
for the pinned model seam, and the real ``knowledge/`` files read-only. Sockets are blocked,
so no Ollama or live service is ever contacted.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
KNOWLEDGE = ROOT / "knowledge"
INIT = ROOT / "scripts" / "init.sh"
SCRIPT = BACKEND / "scripts" / "colloquial_ab.py"
VARIANTS = BACKEND / "config" / "colloquial_variants.json"
GLOSSARY = BACKEND / "config" / "question_glossary.json"
TODAY = date(2026, 11, 10)
REAL_MODEL_TERM = '{"terms": ["boletin oficial"]}'


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("tests must not open a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("colloquial_ab_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _script()


def _paths(variants: Path) -> List[str]:
    return [
        "--catalog", str(KNOWLEDGE / "source_catalog.json"),
        "--passages", str(KNOWLEDGE / "passages.json"),
        "--cases", str(KNOWLEDGE / "pac_answer_eval.json"),
        "--golden", str(KNOWLEDGE / "golden_set.json"),
        "--traps", str(KNOWLEDGE / "trap_set.json"),
        "--variants", str(variants),
    ]


def _result_lines(output: str) -> List[str]:
    return [line for line in output.splitlines() if line.startswith("Result:")]


def _copy(tmp_path: Path, *, approve_all: bool = False) -> Path:
    # The committed file records the owner's 2026-11-11 approvals; these tests exercise the
    # commands from a known all-draft copy, so they do not depend on the owner's live decisions.
    document = json.loads(VARIANTS.read_text(encoding="utf-8"))
    for entry in document["variants"]:
        entry["review_state"] = "draft"
        entry["decision"] = None
    if approve_all:
        for entry in document["variants"]:
            entry["review_state"] = "approved"
            entry["decision"] = {
                "decision": "approved",
                "reviewed_by": "Reviewer",
                "reviewed_on": "2026-11-10",
            }
    target = tmp_path / "colloquial_variants.json"
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


# --- check ----------------------------------------------------------------------------------


def test_check_passes_on_repository_variants_and_names_failures_by_id(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code = SCRIPT_MODULE.main(["check", *_paths(VARIANTS)])
    output = capsys.readouterr().out
    assert code == 0
    assert "colloquial check: 49 variants OK" in output
    assert "49 approved golden parents, 49 covered, 0 orphans" in output

    document = json.loads(VARIANTS.read_text(encoding="utf-8"))
    document["variants"][0]["colloquial_terms"] = ["palabra que no está"]
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    code = SCRIPT_MODULE.main(["check", *_paths(broken)])
    output = capsys.readouterr().out
    assert code == 1
    assert "coll-001: term_missing" in output
    assert output.rstrip().endswith("failures")


# --- owner walkthrough ---------------------------------------------------------------------


def test_list_waiting_pinned_line_and_full_list_file(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    variants = _copy(tmp_path)
    build = tmp_path / "build"

    code = SCRIPT_MODULE.main(
        ["list", *_paths(variants), "--build-dir", str(build)]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert output.splitlines()[-1] == (
        "Result: 49 colloquial variants wait for your decision (0 approved, 0 rejected). "
        "The same list is in build/colloquial-ab/variants.txt."
    )
    text = (build / "variants.txt").read_text(encoding="utf-8")
    assert text.count("[") == 49
    assert "The grower says:" in text
    assert "The approved question:" in text
    assert "Expected:" in text
    assert "Plain words it introduces:" in text

    document = json.loads(variants.read_text(encoding="utf-8"))
    for entry in document["variants"]:
        entry["review_state"] = "rejected"
        entry["decision"] = {
            "decision": "rejected",
            "reviewed_by": "Reviewer",
            "reviewed_on": "2026-11-10",
        }
    variants.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    code = SCRIPT_MODULE.main(
        ["list", *_paths(variants), "--build-dir", str(build)]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.splitlines()[-1] == (
        "Result: no colloquial variants wait for your decision (0 approved, 49 rejected)."
    )


def test_decide_records_replaces_and_records_nothing_on_bad_input(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    variants = _copy(tmp_path)
    build = tmp_path / "build"

    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "approve", "Diego", "1"]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.splitlines()[-1] == (
        "Result: recorded approve for 1 colloquial variants by Diego. 48 still wait for your decision."
    )
    document = json.loads(variants.read_text(encoding="utf-8"))
    assert document["variants"][0]["review_state"] == "approved"
    assert document["variants"][0]["decision"]["reviewed_by"] == "Diego"

    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "reject", "Diego", "coll-001"]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "recorded reject for 1 colloquial variants" in output
    assert json.loads(variants.read_text(encoding="utf-8"))["variants"][0][
        "review_state"
    ] == "rejected"

    before = variants.read_bytes()
    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "approve", "Diego", "999"]
    )
    output = capsys.readouterr().out
    assert code == 1
    assert output.splitlines()[-1].startswith(
        "Result: nothing was recorded. These variant numbers are not in the list: 999."
    )
    assert variants.read_bytes() == before

    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "approve", ""]
    )
    output = capsys.readouterr().out
    assert code == 1
    assert output.splitlines()[-1].startswith("Result: nothing was recorded. Write approve or reject")
    assert variants.read_bytes() == before


def test_decide_refuses_a_bad_variant_and_a_stale_golden_binding(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    variants = _copy(tmp_path)
    build = tmp_path / "build"
    document = json.loads(variants.read_text(encoding="utf-8"))
    document["variants"][2]["colloquial_terms"] = ["palabra que no está"]
    variants.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    before = variants.read_bytes()

    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "approve", "Diego", "3"]
    )
    output = capsys.readouterr().out
    assert code == 1
    assert output.splitlines()[-1].startswith(
        "Result: nothing was recorded. Colloquial variant 3 cannot be approved as written."
    )
    assert variants.read_bytes() == before

    stale = json.loads(json.dumps(document))
    stale["golden_sha256"] = "b" * 64
    variants.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
    before = variants.read_bytes()
    code = SCRIPT_MODULE.main(
        ["decide", *_paths(variants), "--build-dir", str(build),
         "reject", "Diego", "1"]
    )
    output = capsys.readouterr().out
    assert code == 1
    assert output.splitlines()[-1].startswith(
        "Result: nothing was recorded. The colloquial variant list does not match"
    )
    assert variants.read_bytes() == before


def test_missing_backend_environment_line_and_init_wiring(tmp_path: Path) -> None:
    fake = tmp_path / "repo"
    # init.sh sources scripts/lib and scripts/commands, so the checkout needs the whole folder.
    shutil.copytree(ROOT / "scripts", fake / "scripts")

    completed = subprocess.run(
        ["bash", str(fake / "scripts" / "init.sh"), "--colloquial-review"],
        cwd=fake,
        env={**os.environ, "MANIJERO_LOCAL_HOME": str(tmp_path / "home")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert (
        "Result: the colloquial variant review did not run. "
        "Run ./scripts/init.sh --local-rag-setup."
    ) in completed.stdout
    assert "did not run" in completed.stdout

    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "scripts").rglob("*.sh"))
    )
    assert "--colloquial-review" in source and "--colloquial-decide" in source
    assert "colloquial_ab.py\" list" in source
    assert "colloquial_ab.py\" decide" in source
    assert "commands/knowledge.sh" in (ROOT / "scripts" / "init.sh").read_text(encoding="utf-8")


# --- prepare and run ------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.access(BACKEND / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)
def test_run_writes_one_report_one_result_line_and_is_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    variants = _copy(tmp_path, approve_all=True)
    report_root = tmp_path / "reports"
    knowledge_before = _tree_hashes(KNOWLEDGE)
    glossary_before = hashlib.sha256(GLOSSARY.read_bytes()).hexdigest()

    code = SCRIPT_MODULE.main(
        ["prepare", *_paths(variants), "--as-of", "2026-11-10"],
        reports_root=report_root,
        rewriter=lambda question: REAL_MODEL_TERM,
    )
    output = capsys.readouterr().out
    assert code == 0
    assert output.splitlines()[-1].startswith(
        "Result: prepared model rewrites for 49 approved colloquial variants with "
    )
    assert "49 rewritten, 0 empty, 0 rejected, 0 skipped" in output
    cache_files = list((report_root / "rewrites").glob("*.json"))
    assert len(cache_files) == 1
    cache = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert "question" not in cache_files[0].read_text(encoding="utf-8")
    assert len(cache["cases"]) == 49

    code = SCRIPT_MODULE.main(
        ["run", *_paths(variants), "--as-of", "2026-11-10"],
        reports_root=report_root,
    )
    output = capsys.readouterr().out
    assert code == 0
    lines = _result_lines(output)
    assert len(lines) == 1
    assert lines[0].startswith(
        "Result: compared 3 ways on 49 approved colloquial variants"
    )
    assert "model rewrites: 49 rewritten, 0 empty, 0 rejected, 0 skipped" in lines[0]
    assert lines[0].endswith("Report only, no gate. Report: report.json.")

    reports = list((report_root / "reports").glob("*/report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["schema_version"] == "colloquial-ab-report-v1"
    assert report["report_only"] is True
    assert report["defaults_changed"] is False
    assert report["variant_counts"] == {"approved": 49, "draft": 0, "rejected": 0}
    assert report["case_counts"] == {"colloquial": 49, "golden": 49, "trap": 26, "total": 124}
    assert len(report["cases"]) == 3 * 124
    assert report["arms"]["glossary"]["hit_at_5"]["of"] == report["arms"]["no_rewriting"]["hit_at_5"]["of"]
    assert report["adoption"]["arms"]["glossary"]["reason"] in {
        "no_gain", "trap_worse", None
    }
    assert "¿" not in reports[0].read_text(encoding="utf-8")
    assert '"question"' not in reports[0].read_text(encoding="utf-8")

    first = reports[0].read_bytes()
    code = SCRIPT_MODULE.main(
        ["run", *_paths(variants), "--as-of", "2026-11-10"],
        reports_root=report_root,
    )
    capsys.readouterr()
    assert code == 0
    assert reports[0].read_bytes() == first

    assert _tree_hashes(KNOWLEDGE) == knowledge_before
    assert hashlib.sha256(GLOSSARY.read_bytes()).hexdigest() == glossary_before


@pytest.mark.skipif(
    not os.access(BACKEND / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)
def test_prepare_and_run_stop_on_unapproved_and_missing_or_stale_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    variants = _copy(tmp_path)
    report_root = tmp_path / "reports"

    for command in ("prepare", "run"):
        code = SCRIPT_MODULE.main(
            [command, *_paths(variants), "--as-of", "2026-11-10"],
            reports_root=report_root,
            rewriter=lambda question: REAL_MODEL_TERM,
        )
        output = capsys.readouterr().out
        assert code == 2
        assert output.splitlines()[-1].startswith(
            "Result: the colloquial comparison did not run (no_approved_variants):"
        )
        assert not report_root.exists()

    approved = _copy(tmp_path, approve_all=True)
    code = SCRIPT_MODULE.main(
        ["run", *_paths(approved), "--as-of", "2026-11-10"],
        reports_root=report_root,
    )
    output = capsys.readouterr().out
    assert code == 2
    assert "rewrites_missing" in output.splitlines()[-1]

    prepare = SCRIPT_MODULE.main(
        ["prepare", *_paths(approved), "--as-of", "2026-11-10"],
        reports_root=report_root,
        rewriter=lambda question: REAL_MODEL_TERM,
    )
    capsys.readouterr()
    assert prepare == 0
    cache = next((report_root / "rewrites").glob("*.json"))
    document = json.loads(cache.read_text(encoding="utf-8"))
    document["cache_key"] = "0" * 16
    cache.write_text(json.dumps(document), encoding="utf-8")

    code = SCRIPT_MODULE.main(
        ["run", *_paths(approved), "--as-of", "2026-11-10"],
        reports_root=report_root,
    )
    output = capsys.readouterr().out
    assert code == 2
    assert "rewrites_stale" in output.splitlines()[-1]
    assert not list((report_root / "reports").glob("*/report.json"))


@pytest.mark.skipif(
    not os.access(BACKEND / ".venv" / "bin" / "python", os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)
def test_run_refuses_an_output_root_inside_knowledge(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    approved = _copy(tmp_path, approve_all=True)
    code = SCRIPT_MODULE.main(
        ["run", *_paths(approved), "--as-of", "2026-11-10"],
        reports_root=KNOWLEDGE / "colloquial-ab",
    )
    output = capsys.readouterr().out
    assert code == 2
    assert output.splitlines()[-1].startswith(
        "Result: the colloquial comparison did not run (unsafe_output_path):"
    )
    assert not (KNOWLEDGE / "colloquial-ab").exists()
