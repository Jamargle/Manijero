"""Knowledge reindex and release: prepare, gates, publish, rollback, and the service seam.

Runs in the default backend environment: offline, no model, no ``chromadb``, no server.
Release roots are temporary directories; canonical ``knowledge/`` is only read.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
import pytest
from fastapi.testclient import TestClient

import app.ask_api as ask_api
from app import knowledge_release as kr
from app import release_gates
from app.ask_api import get_as_of_date
from app.embedding_index import IndexInputs, PassageEmbeddingIndex, build_index_document, write_index_atomic
from app.embeddings import load_model_spec
from app.main import app
from app.retrieval_backend import Bm25Backend, get_retrieval_backend

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
KNOWLEDGE = REPO_ROOT / "knowledge"
SCHEMA = KNOWLEDGE / "knowledge-release-manifest.schema.json"
SCRIPT = BACKEND_ROOT / "scripts" / "knowledge_release.py"
AS_OF = date(2026, 10, 13)
LATER = date(2026, 10, 20)
CAMPAIGN = "2026"
REVISION = "0123456789abcdef0123456789abcdef01234567"
FIXED_NOW = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)

_spec = importlib.util.spec_from_file_location("knowledge_release_cli", SCRIPT)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)  # type: ignore[union-attr]


# --- Helpers -------------------------------------------------------------------------------


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path: Path) -> Dict[str, Path]:
    folder = tmp_path / "inputs"
    folder.mkdir()
    paths = {}
    for name in ("source_catalog.json", "passages.json", "pac_answer_eval.json"):
        target = folder / name
        target.write_bytes((KNOWLEDGE / name).read_bytes())
        paths[name] = target
    return {"catalog": paths["source_catalog.json"], "passages": paths["passages.json"], "cases": paths["pac_answer_eval.json"]}


def prepare(root: Path, inputs: Dict[str, Path], **overrides: Any) -> kr.PrepareResult:
    arguments: Dict[str, Any] = dict(
        root=root,
        catalog=inputs["catalog"],
        passages=inputs["passages"],
        cases=inputs["cases"],
        as_of=AS_OF,
        active_campaign=CAMPAIGN,
        code_revision=REVISION,
        reviewed_baseline_revision=REVISION,
    )
    arguments.update(overrides)
    return kr.prepare_release(**arguments)


def edited(path: Path, target: Path, change) -> Path:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    change(document)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv), clock=lambda: FIXED_NOW)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def prepare_args(root: Path, inputs: Dict[str, Path], *extra: str, as_of: str = "2026-10-13") -> List[str]:
    return [
        "prepare", "--root", str(root),
        "--catalog", str(inputs["catalog"]), "--passages", str(inputs["passages"]), "--cases", str(inputs["cases"]),
        "--active-campaign", CAMPAIGN, "--as-of", as_of, "--code-revision", REVISION, *extra,
    ]


def release_entries(root: Path) -> List[str]:
    releases = root / kr.RELEASES_DIR
    return sorted(os.listdir(releases)) if releases.exists() else []


def merge_record(path: Path, inputs: Dict[str, Path], **overrides: Any) -> Path:
    record = {
        "schema_version": "knowledge-update-merge-v1",
        "package_id": "a" * 64,
        "reviewer": "Revisora Ejemplo Sintética",
        "approved_on": "2026-10-12",
        "catalog_sha256": sha(inputs["catalog"]),
        "passages_sha256": sha(inputs["passages"]),
        "canonical_changes_applied": True,
        "reindex_required": True,
        "reindexed": False,
        "released": False,
        "statement": "Synthetic merge record for tests.",
    }
    record.update(overrides)
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    return path


def two_published_releases(root: Path, inputs: Dict[str, Path]) -> tuple[str, str]:
    first = prepare(root, inputs)
    kr.publish(root, first.release_id, AS_OF, CAMPAIGN, clock=lambda: FIXED_NOW)
    second = prepare(root, inputs, as_of=LATER)
    assert second.passed and second.baseline_release_id == first.release_id
    kr.publish(root, second.release_id, LATER, CAMPAIGN, clock=lambda: FIXED_NOW)
    return first.release_id, second.release_id


# --- 1. Happy path -------------------------------------------------------------------------


def test_prepare_writes_a_passed_schema_valid_release_and_leaves_inputs_untouched(tmp_path, inputs, capsys) -> None:
    canonical_before = {name: sha(KNOWLEDGE / name) for name in ("source_catalog.json", "passages.json", "pac_answer_eval.json")}
    record = merge_record(tmp_path / "merge.json", inputs)
    record_before = sha(record)
    root = tmp_path / "root"

    code, out, err = run_cli(capsys, *prepare_args(root, inputs, "--merge-record", str(record)))

    assert code == 0, err
    release_id = out.splitlines()[0].removeprefix("release_id: ")
    release = root / "releases" / release_id
    assert sorted(os.listdir(release)) == sorted(
        ["source_catalog.json", "passages.json", "pac_answer_eval.json", "bm25-index.json", "evaluation-report.json", "release-manifest.json"]
    )
    manifest = json.loads((release / "release-manifest.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(manifest)
    kr.validate_manifest(manifest)
    assert manifest["gate"]["passed"] is True and manifest["gate"]["baseline_release_id"] is None
    assert manifest["approval"] == {
        "kind": "merge_record",
        "package_id": "a" * 64,
        "approved_on": "2026-10-12",
        "merge_record_sha256": record_before,
    }
    for name in ("source_catalog.json", "passages.json", "pac_answer_eval.json"):
        assert (release / name).read_bytes() == (KNOWLEDGE / name).read_bytes()
    assert stat.S_IMODE(release.stat().st_mode) == 0o755
    assert all(stat.S_IMODE((release / name).stat().st_mode) == 0o644 for name in os.listdir(release))
    assert {name: sha(KNOWLEDGE / name) for name in canonical_before} == canonical_before
    assert sha(record) == record_before
    for name in os.listdir(release):
        assert "Revisora" not in (release / name).read_text(encoding="utf-8")


# --- 2. Determinism ------------------------------------------------------------------------


def test_same_inputs_give_byte_identical_releases_and_compare_reports_as_of(tmp_path, inputs, capsys) -> None:
    first = prepare(tmp_path / "a", inputs)
    second = prepare(tmp_path / "b", inputs)
    later = prepare(tmp_path / "c", inputs, as_of=LATER)

    assert first.release_id == second.release_id
    for name in ("release-manifest.json", "bm25-index.json", "evaluation-report.json"):
        assert (tmp_path / "a/releases" / first.release_id / name).read_bytes() == (
            tmp_path / "b/releases" / second.release_id / name
        ).read_bytes()
    assert later.release_id != first.release_id

    code, out, _ = run_cli(capsys, "compare", "--a", str(tmp_path / "a/releases" / first.release_id), "--b", str(tmp_path / "b/releases" / second.release_id))
    assert (code, out) == (0, "identical: yes\n")
    code, out, _ = run_cli(capsys, "compare", "--a", str(tmp_path / "a/releases" / first.release_id), "--b", str(tmp_path / "c/releases" / later.release_id))
    paths = {line.split(": ", 1)[1] for line in out.splitlines()[1:]}
    assert code == 1
    assert "inputs.as_of" in paths
    assert paths <= {"inputs.as_of", "release_id", "files.evaluation-report.json.sha256", "files.evaluation-report.json.bytes"}
    assert "release-manifest" not in out and "\"at\"" not in (tmp_path / "a/releases" / first.release_id / "release-manifest.json").read_text()


# --- 3. Approval evidence ------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra, code_name",
    [
        ((), "approval_evidence_required"),
        (("--reviewed-baseline-revision", REVISION, "--merge-record", "MERGE"), "approval_evidence_ambiguous"),
        (("--merge-record", "MISMATCH"), "approval_mismatch"),
        (("--merge-record", "WRONG_SCHEMA"), "merge_record_invalid"),
        (("--merge-record", "NOT_APPLIED"), "merge_record_invalid"),
    ],
)
def test_missing_or_mismatched_approval_refuses_without_writing(tmp_path, inputs, capsys, extra, code_name) -> None:
    files = {
        "MERGE": merge_record(tmp_path / "merge.json", inputs),
        "MISMATCH": merge_record(tmp_path / "mismatch.json", inputs, passages_sha256="f" * 64),
        "WRONG_SCHEMA": merge_record(tmp_path / "wrong.json", inputs, schema_version="knowledge-update-merge-v0"),
        "NOT_APPLIED": merge_record(tmp_path / "not-applied.json", inputs, canonical_changes_applied=False),
    }
    argv = [str(files.get(value, value)) for value in extra]
    root = tmp_path / "root"

    code, out, err = run_cli(capsys, *prepare_args(root, inputs, *argv))

    assert code == 2
    assert "error: {}".format(code_name) in err
    assert release_entries(root) == []


# --- 4. Structural gate failures -----------------------------------------------------------


def _expire_one_source(document: Dict[str, Any]) -> None:
    document["sources"][0]["valid_until"] = "2026-10-01"


def _unknown_source(document: Dict[str, Any]) -> None:
    document["passages"][0]["source_id"] = "fuente_inexistente"


def _case_to_missing_passage(document: Dict[str, Any]) -> None:
    case = next(case for case in document["cases"] if case.get("expected_passage_ids"))
    case["expected_passage_ids"] = ["pasaje-inexistente"]


@pytest.mark.parametrize(
    "target, change, campaign, expected",
    [
        ("catalog", _expire_one_source, CAMPAIGN, {"catalog_invalid", "corpus_not_ready:corpus_unavailable", "evaluation_failed"}),
        ("passages", _unknown_source, CAMPAIGN, {"passage_source_unresolved", "evaluation_failed"}),
        ("cases", _case_to_missing_passage, CAMPAIGN, {"cases_invalid", "evaluation_failed"}),
        (None, None, "2027", {"cases_orphaned", "evaluation_failed"}),
    ],
)
def test_failed_gate_is_written_but_never_publishable(tmp_path, inputs, capsys, target, change, campaign, expected) -> None:
    if target is not None:
        inputs = dict(inputs)
        inputs[target] = edited(inputs[target], tmp_path / "edited.json", change)
    root = tmp_path / "root"
    argv = prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION)
    argv[argv.index("--active-campaign") + 1] = campaign

    code, out, _ = run_cli(capsys, *argv)

    assert code == 1
    release_id = out.splitlines()[0].removeprefix("release_id: ")
    manifest = kr.read_manifest(root / "releases" / release_id)
    assert manifest["gate"]["passed"] is False
    assert expected <= set(manifest["gate"]["failures"])
    code, _, err = run_cli(capsys, "publish", "--root", str(root), "--release-id", release_id, "--as-of", "2026-10-13", "--active-campaign", campaign)
    assert code == 2 and "error: gate_failed" in err
    assert not os.path.lexists(root / "current")


def test_a_regressed_case_fails_the_gate_against_the_published_release(tmp_path, inputs) -> None:
    root = tmp_path / "root"
    first = prepare(root, inputs)
    kr.publish(root, first.release_id, AS_OF, CAMPAIGN)

    def drop_the_date(document: Dict[str, Any]) -> None:
        for passage in document["passages"]:
            if passage["id"] == "pasaje-plazo-presentacion-2026-andalucia":
                passage["text"] = "Texto alterado de prueba sin el plazo de presentación."

    broken = dict(inputs, passages=edited(inputs["passages"], tmp_path / "p.json", drop_the_date))
    result = prepare(root, broken)

    assert not result.passed
    assert "evaluation_regression:fecha-presentacion-2026" in result.failures
    assert result.baseline_release_id == first.release_id
    assert kr.current_release_id(root) == first.release_id


# --- 5. Grounding checker ------------------------------------------------------------------


def _canonical_corpus() -> tuple[Any, Any]:
    return (
        json.loads((KNOWLEDGE / "source_catalog.json").read_text(encoding="utf-8")),
        json.loads((KNOWLEDGE / "passages.json").read_text(encoding="utf-8")),
    )


def _answered_body(catalog: Any, passage: Dict[str, Any], **source_overrides: Any) -> Dict[str, Any]:
    source = next(s for s in catalog["sources"] if s["id"] == passage["source_id"])
    item = {
        "title": "Título",
        "issuing_body": "Organismo",
        "url": source["original_url"],
        "location": passage["location"],
        "published_or_updated_on": "2026-01-01",
        "verified_on": "2026-10-17",
        "excerpt": passage["text"],
    }
    item.update(source_overrides)
    return {"status": "answered", "answer": "Respuesta.", "sources": [item], "land_scope": "general", "land_ids_to_choose": []}


def test_grounding_accepts_mapped_sources_and_flags_each_defect() -> None:
    catalog, passages = _canonical_corpus()
    passage = passages["passages"][0]
    good = _answered_body(catalog, passage)
    unmapped = _answered_body(catalog, passage, excerpt="Texto que no es literal del pasaje.")
    empty = dict(good, sources=[])
    invalid = dict(good, unexpected="x")
    abstained = {"status": "abstained", "answer": "No.", "sources": [], "land_scope": "general", "land_ids_to_choose": []}

    problems = release_gates.check_grounding(
        ["ok", "unmapped", "empty", "invalid", "abstained", "none"],
        [good, unmapped, empty, invalid, abstained, None],
        catalog,
        passages,
    )

    assert problems == [
        ("unmapped", "grounding_unmapped_source"),
        ("empty", "grounding_empty_sources"),
        ("invalid", "grounding_invalid_response"),
        ("none", "grounding_invalid_response"),
    ]


# --- 6. Regression comparator --------------------------------------------------------------


def _row(case_id: str, **flags: bool) -> Dict[str, Any]:
    row = {"id": case_id, **{name: True for name in release_gates.TRACKED_CASE_FIELDS}}
    row.update(flags)
    return row


@pytest.mark.parametrize("field", release_gates.TRACKED_CASE_FIELDS)
def test_each_tracked_flag_going_false_fails(field) -> None:
    baseline = {"case_digests": {"c": "d1"}, "report": {"case_rows": [_row("c")]}}

    failures, notes = release_gates.compare_to_baseline({"c": "d1"}, [_row("c", **{field: False})], baseline)

    assert failures == ["evaluation_regression:c"]
    assert notes["regressed_cases"] == ["c"]


def test_changed_new_and_removed_cases_are_reported_not_gated() -> None:
    baseline = {"case_digests": {"same": "d", "changed": "old", "gone": "g"}, "report": {"case_rows": [_row("same"), _row("changed"), _row("gone")]}}
    rows = [_row("same"), _row("changed", source_match=False), _row("new", passage_match=False)]

    failures, notes = release_gates.compare_to_baseline({"same": "d", "changed": "new", "new": "n"}, rows, baseline)

    assert failures == []
    assert notes == {"regressed_cases": [], "changed_cases": ["changed"], "new_cases": ["new"], "removed_cases": ["gone"]}
    assert release_gates.compare_to_baseline({"same": "d"}, [_row("same")], None) == ([], {"regressed_cases": [], "changed_cases": [], "new_cases": [], "removed_cases": []})
    assert release_gates.compare_to_baseline({"same": "d"}, [_row("same")], {"report": {}})[0] == ["baseline_unreadable"]


# --- 7. Publish ----------------------------------------------------------------------------


def test_publish_switches_current_and_logs_once(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    release_id = prepare(root, inputs).release_id

    code, out, _ = run_cli(capsys, "publish", "--root", str(root), "--release-id", release_id, "--as-of", "2026-10-13", "--active-campaign", CAMPAIGN)
    again, again_out, _ = run_cli(capsys, "publish", "--root", str(root), "--release-id", release_id, "--as-of", "2026-10-13", "--active-campaign", CAMPAIGN)

    assert code == 0 and "result: switched" in out
    assert again == 0 and "result: already_current" in again_out
    assert os.readlink(root / "current") == os.path.join("releases", release_id)
    assert kr.read_log(root) == [
        {"event": "publish", "release_id": release_id, "previous_release_id": None, "at": "2026-10-31T12:00:00+00:00"}
    ]
    code, out, _ = run_cli(capsys, "status", "--root", str(root))
    assert code == 0 and "integrity: ok" in out and "log: in_sync" in out
    assert run_cli(capsys, "verify", "--root", str(root))[0] == 0


def test_publish_refuses_a_tampered_or_not_ready_release_and_keeps_current(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    first, second = two_published_releases(root, inputs)
    kr.rollback(root, AS_OF, CAMPAIGN)
    assert kr.current_release_id(root) == first

    target = root / "releases" / second / "passages.json"
    os.chmod(target, 0o644)
    target.write_bytes(target.read_bytes().replace(b"2026", b"2027", 1))
    code, _, err = run_cli(capsys, "publish", "--root", str(root), "--release-id", second, "--as-of", "2026-10-20", "--active-campaign", CAMPAIGN)
    assert code == 2 and "error: integrity_mismatch" in err

    code, _, err = run_cli(capsys, "publish", "--root", str(root), "--release-id", first, "--as-of", "2027-01-15", "--active-campaign", CAMPAIGN)
    assert code == 1 and "error: corpus_not_ready:" in err
    assert kr.current_release_id(root) == first
    assert run_cli(capsys, "verify", "--root", str(root), "--release-id", second)[0] == 1


def test_publish_refuses_while_locked(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    release_id = prepare(root, inputs).release_id
    (root / ".release.lock").write_text("", encoding="utf-8")

    code, _, err = run_cli(capsys, "publish", "--root", str(root), "--release-id", release_id, "--as-of", "2026-10-13", "--active-campaign", CAMPAIGN)

    assert code == 2 and "error: release_locked" in err
    assert not os.path.lexists(root / "current")


def test_a_failed_swap_or_log_append_leaves_the_previous_release_current(tmp_path, inputs, monkeypatch) -> None:
    root = tmp_path / "root"
    first = prepare(root, inputs).release_id
    kr.publish(root, first, AS_OF, CAMPAIGN)
    second = prepare(root, inputs, as_of=LATER).release_id

    def broken_replace(*_: Any) -> None:
        raise OSError("disk")

    with monkeypatch.context() as patch:
        patch.setattr(kr.os, "replace", broken_replace)
        with pytest.raises(kr.ReleaseError) as error:
            kr.publish(root, second, LATER, CAMPAIGN)
    assert error.value.code == "publish_failed"
    assert kr.current_release_id(root) == first
    assert not [name for name in os.listdir(root) if name.startswith(".current-")]

    def broken_append(*_: Any) -> None:
        raise OSError("disk")

    with monkeypatch.context() as patch:
        patch.setattr(kr, "append_log", broken_append)
        with pytest.raises(kr.ReleaseError) as error:
            kr.publish(root, second, LATER, CAMPAIGN)
    assert error.value.code == "publish_failed"
    assert kr.current_release_id(root) == first
    assert len(kr.read_log(root)) == 1
    assert not (root / ".release.lock").exists()


# --- 8. Rollback ---------------------------------------------------------------------------


def test_rollback_returns_to_the_previous_release_and_logs_it(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    first, second = two_published_releases(root, inputs)

    code, out, _ = run_cli(capsys, "rollback", "--root", str(root), "--as-of", "2026-10-20", "--active-campaign", CAMPAIGN)

    assert code == 0
    assert "release_id: {}".format(first) in out and "previous_release_id: {}".format(second) in out
    assert kr.current_release_id(root) == first
    assert kr.read_log(root)[-1]["event"] == "rollback"
    code, _, err = run_cli(capsys, "rollback", "--root", str(root), "--as-of", "2026-10-20", "--active-campaign", CAMPAIGN)
    assert code == 1 and "error: no_previous_release" in err
    code, _, err = run_cli(capsys, "rollback", "--root", str(root), "--to", "ffffffffffffffff", "--as-of", "2026-10-20", "--active-campaign", CAMPAIGN)
    assert code == 2 and "error: release_not_found" in err


def test_rollback_refuses_failed_or_tampered_targets(tmp_path, inputs) -> None:
    root = tmp_path / "root"
    first, second = two_published_releases(root, inputs)
    failed = prepare(root, inputs, active_campaign="2027").release_id

    with pytest.raises(kr.ReleaseError) as error:
        kr.rollback(root, AS_OF, CAMPAIGN, to=failed)
    assert error.value.code == "gate_failed"

    (root / "releases" / first / "source_catalog.json").write_bytes(b"{}")
    with pytest.raises(kr.ReleaseError) as error:
        kr.rollback(root, AS_OF, CAMPAIGN)
    assert error.value.code == "integrity_mismatch"
    assert kr.current_release_id(root) == second


def test_rollback_without_a_current_release(tmp_path, inputs) -> None:
    root = tmp_path / "root"
    prepare(root, inputs)
    with pytest.raises(kr.ReleaseError) as error:
        kr.rollback(root, AS_OF, CAMPAIGN)
    assert (error.value.code, error.value.exit_code) == ("no_current_release", 1)


# --- 9. Safety -----------------------------------------------------------------------------


def test_release_root_inside_knowledge_is_refused(inputs, capsys) -> None:
    root = KNOWLEDGE / "releases-must-not-exist"

    code, _, err = run_cli(capsys, *prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION))

    assert code == 2 and "error: unsafe_release_root" in err
    assert not root.exists()


def test_current_outside_releases_is_refused_by_cli_and_service(tmp_path, inputs, capsys, monkeypatch) -> None:
    root = tmp_path / "root"
    release_id = prepare(root, inputs).release_id
    kr.publish(root, release_id, AS_OF, CAMPAIGN)
    elsewhere = tmp_path / "elsewhere" / release_id
    elsewhere.mkdir(parents=True)
    for name in os.listdir(root / "releases" / release_id):
        (elsewhere / name).write_bytes((root / "releases" / release_id / name).read_bytes())
    os.unlink(root / "current")
    os.symlink(elsewhere, root / "current")

    code, _, err = run_cli(capsys, "verify", "--root", str(root))
    assert code == 2 and "error: current_outside_releases" in err
    with pytest.raises(kr.ReleaseError) as error:
        kr.load_published_corpus(root)
    assert error.value.code == "current_outside_releases"


def test_a_different_existing_release_directory_conflicts(tmp_path, inputs) -> None:
    release_id = prepare(tmp_path / "a", inputs).release_id
    root = tmp_path / "b"
    (root / "releases" / release_id).mkdir(parents=True)
    (root / "releases" / release_id / "release-manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(kr.ReleaseError) as error:
        prepare(root, inputs)

    assert error.value.code == "release_conflict"
    assert release_entries(root) == [release_id]
    again = prepare(tmp_path / "a", inputs)
    assert again.already_prepared and again.release_id == release_id


def test_unknown_or_inconsistent_manifest_is_invalid(tmp_path, inputs) -> None:
    root = tmp_path / "root"
    manifest = prepare(root, inputs).manifest
    for mutate in (
        lambda m: m.update(extra=1),
        lambda m: m["gate"].update(passed=False),
        lambda m: m["inputs"].update(as_of="2026-10-14"),
        lambda m: m["files"]["passages.json"].update(sha256="0" * 64),
    ):
        broken = json.loads(json.dumps(manifest))
        mutate(broken)
        with pytest.raises(kr.ReleaseError):
            kr.validate_manifest(broken)


# --- 10. Service read path -----------------------------------------------------------------


@pytest.fixture
def service(monkeypatch):
    records: List[Dict[str, Any]] = []
    monkeypatch.setattr(ask_api, "operational_log", lambda event, **fields: records.append({"event": event, **fields}))
    monkeypatch.setattr(ask_api, "_LAST_RELEASE_OUTCOME", None)
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", CAMPAIGN)
    app.dependency_overrides[get_as_of_date] = lambda: AS_OF
    app.dependency_overrides[get_retrieval_backend] = Bm25Backend
    with TestClient(app) as client:
        yield client, records
    app.dependency_overrides.clear()


QUESTION = {"question": "¿Hasta cuándo puedo presentar la solicitud única de 2026?", "land_context": {"mode": "general", "lands": []}}


def _relocate(document: Dict[str, Any]) -> None:
    for passage in document["passages"]:
        if passage["id"] == "pasaje-plazo-presentacion-2026-andalucia":
            passage["location"] = "Artículo 14 (copia de prueba B)"


def test_service_reads_only_the_verified_published_release(tmp_path, inputs, service, monkeypatch) -> None:
    client, records = service
    monkeypatch.delenv("MANIJERO_KNOWLEDGE_RELEASE_ROOT", raising=False)
    unset_body = client.post("/ask", json=QUESTION).json()

    root = tmp_path / "root"
    first = prepare(root, inputs).release_id
    kr.publish(root, first, AS_OF, CAMPAIGN)
    monkeypatch.setenv("MANIJERO_KNOWLEDGE_RELEASE_ROOT", str(root))
    assert client.get("/ready").status_code == 200
    response = client.post("/ask", json=QUESTION)
    assert response.status_code == 200 and response.json() == unset_body
    assert unset_body["status"] == "answered"

    relocated = dict(inputs, passages=edited(inputs["passages"], tmp_path / "b.json", _relocate))
    second = prepare(root, relocated)
    assert second.passed, second.failures
    kr.publish(root, second.release_id, AS_OF, CAMPAIGN)
    body = client.post("/ask", json=QUESTION).json()
    assert any(source["location"] == "Artículo 14 (copia de prueba B)" for source in body["sources"])

    target = root / "releases" / second.release_id / "passages.json"
    target.write_bytes(target.read_bytes() + b" ")
    ready = client.get("/ready")
    ask = client.post("/ask", json=QUESTION)
    assert (ready.status_code, ready.json()) == (503, {"status": "unavailable", "service": "manijero-backend"})
    assert (ask.status_code, ask.json()) == (503, {"detail": "Answer service is temporarily unavailable."})
    refused = [record for record in records if record["event"] == "knowledge_release" and record["state"] == "refused"]
    assert refused == [{"event": "knowledge_release", "release_id": second.release_id, "state": "refused", "reason": "integrity_mismatch"}]

    kr.rollback(root, AS_OF, CAMPAIGN)
    assert client.get("/ready").status_code == 200
    assert client.post("/ask", json=QUESTION).json() == unset_body
    served = [r["release_id"] for r in records if r["event"] == "knowledge_release" and r["state"] == "served"]
    assert served == [first, second.release_id, first]
    assert all(set(record) == {"event", "release_id", "state", "reason"} for record in records if record["event"] == "knowledge_release")


def test_service_refuses_a_failed_gate_release_even_if_pointed_at(tmp_path, inputs, service, monkeypatch) -> None:
    client, _ = service
    root = tmp_path / "root"
    failed = prepare(root, inputs, active_campaign="2027").release_id
    os.symlink(os.path.join("releases", failed), root / "current")
    monkeypatch.setenv("MANIJERO_KNOWLEDGE_RELEASE_ROOT", str(root))

    assert client.get("/ready").status_code == 503
    assert client.post("/ask", json=QUESTION).status_code == 503


def test_service_with_an_empty_release_root_is_unavailable(tmp_path, inputs, service, monkeypatch) -> None:
    client, records = service
    root = tmp_path / "root"
    prepare(root, inputs)
    monkeypatch.setenv("MANIJERO_KNOWLEDGE_RELEASE_ROOT", str(root))

    assert client.get("/ready").status_code == 503
    assert records[-1]["reason"] == "no_current_release"


def test_one_request_never_mixes_two_releases(tmp_path, inputs, monkeypatch) -> None:
    root = tmp_path / "root"
    first, second = two_published_releases(root, inputs)
    kr.rollback(root, AS_OF, CAMPAIGN)
    original = kr._check_file
    calls: List[Path] = []

    def swap_between_reads(path: Path, *args: Any) -> bytes:
        payload = original(path, *args)
        if not calls:
            kr._point_current(root, second)
        calls.append(path)
        return payload

    monkeypatch.setattr(kr, "_check_file", swap_between_reads)
    catalog, passages, release_id = kr.load_published_corpus(root)

    assert release_id == first
    assert {path.parent.name for path in calls} == {first}
    assert kr.current_release_id(root) == second


def test_preflight_default_read_inherits_the_release(tmp_path, inputs, monkeypatch) -> None:
    root = tmp_path / "root"
    monkeypatch.setenv("MANIJERO_KNOWLEDGE_RELEASE_ROOT", str(root))
    prepare(root, inputs)
    assert ask_api.load_corpus_documents().load_error is True
    explicit = ask_api.load_corpus_documents(KNOWLEDGE / "source_catalog.json", KNOWLEDGE / "passages.json")
    assert explicit.load_error is False


# --- 11. Gate isolation --------------------------------------------------------------------


def test_gate_ignores_environment_knobs_and_never_opens_a_socket(tmp_path, inputs, monkeypatch) -> None:
    clean = prepare(tmp_path / "clean", inputs)
    monkeypatch.setenv("MANIJERO_RETRIEVAL_MODE", "hybrid")
    monkeypatch.setenv("MANIJERO_GENERATION_PROVIDER", "local")
    monkeypatch.setenv("MANIJERO_VECTOR_STORE", str(tmp_path / "no-store"))
    monkeypatch.setenv("MANIJERO_EMBEDDING_ARTIFACT", str(tmp_path / "no-model"))

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    noisy = prepare(tmp_path / "noisy", inputs)

    assert noisy.passed and noisy.release_id == clean.release_id
    assert (tmp_path / "noisy/releases" / noisy.release_id / "evaluation-report.json").read_bytes() == (
        tmp_path / "clean/releases" / clean.release_id / "evaluation-report.json"
    ).read_bytes()


# --- 12. Import hygiene --------------------------------------------------------------------


def test_service_import_does_not_load_gates_evaluation_or_vector_runtimes() -> None:
    code = (
        "import sys\n"
        "import app.main\n"
        "names = ['app.release_gates', 'app.answer_eval', 'app.vector_store', 'chromadb', 'torch', 'fastapi.testclient']\n"
        "print([name for name in names if name in sys.modules])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(BACKEND_ROOT))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


# --- 13. Vector options in the default environment -----------------------------------------


def _fake_index(path: Path, inputs: Dict[str, Path], as_of: str) -> Path:
    spec = load_model_spec(kr.DEFAULT_EMBEDDING_CONFIG)
    passage_ids = sorted(p["id"] for p in json.loads(inputs["passages"].read_text(encoding="utf-8"))["passages"])
    vectors = {}
    for position, passage_id in enumerate(passage_ids):
        vector = [0.0] * spec.embedding_dimension
        vector[position] = 1.0
        vectors[passage_id] = tuple(vector)
    index_inputs = IndexInputs(sha(inputs["catalog"]), sha(inputs["passages"]), as_of, CAMPAIGN)
    document = build_index_document(PassageEmbeddingIndex(spec.embedding_dimension, vectors), spec, index_inputs)
    write_index_atomic(path, document, spec)
    return path


@pytest.mark.skipif(importlib.util.find_spec("chromadb") is not None, reason="default environment only")
def test_vector_options_fail_closed_without_writing(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    stale = _fake_index(tmp_path / "stale.json", inputs, "2026-10-01")
    fresh = _fake_index(tmp_path / "fresh.json", inputs, "2026-10-13")

    code, _, err = run_cli(capsys, *prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION, "--embedding-index", str(stale), "--with-vector-store"))
    assert code == 2 and "error: embedding_index_stale:as_of_changed" in err
    code, _, err = run_cli(capsys, *prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION, "--embedding-index", str(fresh), "--with-vector-store"))
    assert code == 2 and "error: vector_runtime_unavailable" in err
    code, _, err = run_cli(capsys, *prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION, "--with-vector-store"))
    assert code == 2 and "error: vector_options_incomplete" in err
    assert release_entries(root) == []


# --- 14. Privacy ---------------------------------------------------------------------------


def test_no_corpus_text_question_or_land_value_is_printed_or_logged(tmp_path, inputs, capsys) -> None:
    root = tmp_path / "root"
    outputs = []
    code, out, err = run_cli(capsys, *prepare_args(root, inputs, "--reviewed-baseline-revision", REVISION))
    outputs.append(out + err)
    release_id = out.splitlines()[0].removeprefix("release_id: ")
    for argv in (
        ["publish", "--root", str(root), "--release-id", release_id, "--as-of", "2026-10-13", "--active-campaign", CAMPAIGN],
        ["status", "--root", str(root)],
        ["verify", "--root", str(root), "--json"],
        ["rollback", "--root", str(root), "--as-of", "2026-10-13", "--active-campaign", CAMPAIGN],
    ):
        _, out, err = run_cli(capsys, *argv)
        outputs.append(out + err)
    outputs.append((root / "release-log.jsonl").read_text(encoding="utf-8"))
    text = "\n".join(outputs)

    passages = json.loads(inputs["passages"].read_text(encoding="utf-8"))["passages"]
    cases = json.loads(inputs["cases"].read_text(encoding="utf-8"))["cases"]
    assert all(passage["text"][:30] not in text for passage in passages)
    assert all(case["question"][:30] not in text for case in cases)
    land_values = {
        land.get("municipality") for case in cases for land in case["land_context"].get("lands", []) if land.get("municipality")
    }
    assert all(value not in text for value in land_values)
