"""Structured chunk index: reviewed chunk sets to a derived BM25/vector index and a flagged read path.

Runs in the default backend environment: offline, no model, no ``chromadb``, no network.
Index roots are temporary directories; ``knowledge/`` is only read. Vectors use a fake
embedder and an in-memory store writer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List

import jsonschema
import pytest
from fastapi.testclient import TestClient

import app.ask_api as ask_api
from app import knowledge_release as kr
from app import pilot_logging
from app import structured_chunk_index as sci
from app.ask_api import CorpusDocuments, get_as_of_date
from app.embeddings import EmbeddingExecutionError
from app.main import app
from app.retrieval import Retriever
from app.retrieval_backend import Bm25Backend, get_retrieval_backend
from app.vector_store import documents_sha256

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FIXTURES = BACKEND_ROOT / "tests" / "fixtures"
CHUNKS = FIXTURES / "structured_chunk_index" / "chunks"
CATALOG = FIXTURES / "legal_structure_chunker" / "source_catalog.json"
EMBEDDING_SPEC = FIXTURES / "embeddings" / "spec.json"
SCHEMA = REPO_ROOT / "knowledge" / "structured-chunk-index.schema.json"
SCRIPT = BACKEND_ROOT / "scripts" / "manage_structured_index.py"
AS_OF = date(2099, 6, 1)
CAMPAIGN = "2099"
REVISION = "0123456789abcdef0123456789abcdef01234567"
SOURCE_ID = "decreto-123-2026"

_spec = importlib.util.spec_from_file_location("manage_structured_index_cli", SCRIPT)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)  # type: ignore[union-attr]

LOCAL = {
    "MANIJERO_STRUCTURED_INDEX": "on",
    "MANIJERO_ENVIRONMENT": "local",
    "MANIJERO_DEPLOYMENT_PROFILE": "development",
}
QA = {"MANIJERO_STRUCTURED_INDEX": "on", "MANIJERO_ENVIRONMENT": "qa", "MANIJERO_DEPLOYMENT_PROFILE": "pilot"}


# --- Helpers -------------------------------------------------------------------------------


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chunk_root(tmp_path: Path) -> Path:
    root = tmp_path / "chunks"
    shutil.copytree(CHUNKS, root)
    return root


def set_file(root: Path) -> Path:
    return next(root.glob("*/chunks-*.json"))


def _dump(document: Any) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def edit_manifest(root: Path, mutate: Callable[[Dict[str, Any]], None]) -> None:
    path = root / "chunks-manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(_dump(document), encoding="utf-8")


def edit_set(root: Path, mutate: Callable[[Dict[str, Any]], None]) -> None:
    """Edit the chunk set and re-sign it in the run manifest, so only the edit is wrong."""
    path = set_file(root)
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    payload = _dump(document)
    path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def resign(manifest: Dict[str, Any]) -> None:
        manifest["documents"][0]["chunk_set_sha256"] = digest

    edit_manifest(root, resign)


def edited_catalog(tmp_path: Path, mutate: Callable[[Dict[str, Any]], None]) -> Path:
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    mutate(document)
    path = tmp_path / "catalog.json"
    path.write_text(_dump(document), encoding="utf-8")
    return path


def build(tmp_path: Path, output: str = "index", **overrides: Any) -> sci.BuildReport:
    arguments: Dict[str, Any] = dict(
        chunks_root=CHUNKS,
        catalog_path=CATALOG,
        output_root=tmp_path / output,
        as_of=AS_OF,
        active_campaign=CAMPAIGN,
        reviewed_baseline_revision=REVISION,
    )
    arguments.update(overrides)
    return sci.build_index(**arguments)


def snapshot(directory: Path) -> Dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def log(monkeypatch) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        pilot_logging, "operational_log", lambda event, **fields: records.append({"event": event, **fields})
    )
    sci.reset_outcome_log()
    yield records
    sci.reset_outcome_log()


# --- Fake vector pieces --------------------------------------------------------------------


class FakeEmbedder:
    model_id = "fixture/embedding-model"
    model_revision = "0123456789abcdef0123456789abcdef01234567"
    dimension = 4
    normalized = True

    def embed(self, texts):
        vectors = []
        for position, _ in enumerate(texts):
            vector = [0.0] * 4
            vector[position % 4] = 1.0
            vectors.append(tuple(vector))
        return tuple(vectors)


def memory_store_writer(store_dir, index, spec, inputs, documents, source_index_sha256):
    Path(store_dir).mkdir(parents=True)
    manifest = {
        "inputs": {"documents_sha256": documents_sha256(documents)},
        "vectors_sha256": hashlib.sha256(",".join(index.passage_ids).encode("utf-8")).hexdigest(),
        "chromadb_version": "1.5.9",
    }
    (Path(store_dir) / sci.VECTOR_MANIFEST_FILE).write_text(_dump(manifest), encoding="utf-8")
    return manifest


def fake_vectors(**overrides: Any) -> sci.VectorOptions:
    arguments: Dict[str, Any] = dict(
        artifact=Path("unused"),
        config=EMBEDDING_SPEC,
        load_embedder=lambda spec, artifact: FakeEmbedder(),
        write_store=memory_store_writer,
    )
    arguments.update(overrides)
    return sci.VectorOptions(**arguments)


# --- 1. Reviewed chunk sets become a deterministic index -----------------------------------


def test_build_writes_the_four_files_with_the_passage_mapping(tmp_path) -> None:
    report = build(tmp_path)
    index = tmp_path / "index"
    assert report.status == "built" and (report.documents, report.chunks) == (1, 4)
    assert sorted(path.name for path in index.iterdir()) == [
        "bm25-index.json",
        "source_catalog.json",
        "structured-index-manifest.json",
        "structured-passages.json",
    ]
    assert (index / "source_catalog.json").read_bytes() == CATALOG.read_bytes()

    passages = json.loads((index / "structured-passages.json").read_text(encoding="utf-8"))
    chunk_set = json.loads(set_file(CHUNKS).read_text(encoding="utf-8"))
    assert passages["schema_version"] == "passage-set-v1"
    assert [passage["id"] for passage in passages["passages"]] == [c["id"] for c in chunk_set["chunks"]]
    for passage, chunk in zip(passages["passages"], chunk_set["chunks"]):
        assert set(passage) == {"id", "source_id", "location", "text"}
        assert passage["source_id"] == SOURCE_ID
        assert passage["text"] == chunk["text"]
        assert passage["location"] == "{}, pág. {}".format(chunk["location"], chunk["page_start"])

    manifest = json.loads((index / "structured-index-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "structured-chunk-index-v1" and manifest["vectors"] is None
    assert manifest["counts"] == {"documents": 1, "chunks": 4, "indexed_passages": 4}
    assert manifest["inputs"]["catalog_sha256"] == sha(CATALOG)
    assert manifest["inputs"]["chunk_manifest_sha256"] == sha(CHUNKS / "chunks-manifest.json")
    assert manifest["approval"] == {"kind": "reviewed_git_baseline", "revision": REVISION}
    for name, entry in manifest["files"].items():
        assert entry == {"sha256": sha(index / name), "bytes": (index / name).stat().st_size}
    from app import release_gates

    expected_bm25 = kr.document_bytes(
        release_gates.bm25_fingerprint(json.loads(CATALOG.read_text(encoding="utf-8")), passages, AS_OF, CAMPAIGN)
    )
    assert (index / "bm25-index.json").read_bytes() == expected_bm25


def test_a_page_range_gets_the_plural_suffix(tmp_path) -> None:
    root = chunk_root(tmp_path)
    edit_set(root, lambda document: document["chunks"][1].update(page_end=4))
    build(tmp_path, chunks_root=root)
    passages = json.loads((tmp_path / "index" / "structured-passages.json").read_text(encoding="utf-8"))
    assert passages["passages"][1]["location"] == "CAPÍTULO II › Artículo 14. Objeto, págs. 3-4"


def test_two_roots_are_byte_identical_and_an_unchanged_rebuild_writes_nothing(tmp_path) -> None:
    build(tmp_path, "first")
    build(tmp_path, "second")
    assert snapshot(tmp_path / "first") == snapshot(tmp_path / "second")

    before = {path: path.stat().st_mtime_ns for path in (tmp_path / "first").iterdir()}
    again = build(tmp_path, "first")
    assert again.status == "unchanged"
    assert {path: path.stat().st_mtime_ns for path in (tmp_path / "first").iterdir()} == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["first", "second"]


def test_a_changed_input_replaces_the_index_atomically(tmp_path) -> None:
    build(tmp_path)
    root = chunk_root(tmp_path)
    edit_set(root, lambda document: document["chunks"][3].update(page_start=4, page_end=5))
    assert build(tmp_path, chunks_root=root).status == "built"
    assert "págs. 4-5" in (tmp_path / "index" / "structured-passages.json").read_text(encoding="utf-8")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["chunks", "index"]


# --- 2. Validity is copied, never inferred -------------------------------------------------


def test_validity_comes_from_the_catalog_through_the_unchanged_retriever(tmp_path) -> None:
    build(tmp_path)
    verified = sci.verify_index(tmp_path / "index")
    assert all(not ({"critical", "applicability", "official_deadline"} & set(p)) for p in verified.passages["passages"])
    retriever = Retriever.from_documents(verified.catalog, verified.passages, AS_OF, active_campaign=CAMPAIGN)
    found = retriever.search("plazo de la solicitud tres meses publicación", 3)
    assert found and found[0].passage_id == "decreto-123-2026-0003"
    assert found[0].critical is True
    assert found[0].applicability == {"crop": "olivo", "water_regime": "irrigated"}
    assert found[0].title.startswith("Decreto 123/2026")
    assert (found[0].published_or_updated_on, found[0].verified_on) == ("2099-01-02", "2099-03-02")


# --- 3. Malformed or unreviewed input fails closed -----------------------------------------


def _unknown_validity(document: Dict[str, Any]) -> None:
    document["validity_status"] = "unknown"
    document.pop("catalog")


def _tamper_bytes(root: Path) -> None:
    set_file(root).write_bytes(set_file(root).read_bytes() + b" ")


REFUSALS = [
    ("unknown_validity", lambda root: edit_set(root, _unknown_validity), "unreviewed_chunk_set"),
    (
        "not_chunked",
        lambda root: edit_manifest(root, lambda m: m["documents"][0].update(status="unstructured")),
        "unreviewed_chunk_set",
    ),
    ("tampered_bytes", _tamper_bytes, "invalid_chunk_set"),
    ("extra_key", lambda root: edit_set(root, lambda d: d.update(extra=1)), "invalid_chunk_set"),
    ("bad_version", lambda root: edit_set(root, lambda d: d.update(schema_version="legal-chunk-set-v2")), "invalid_chunk_set"),
    ("chunk_count_lie", lambda root: edit_set(root, lambda d: d.update(chunk_count=9)), "invalid_chunk_set"),
    ("bad_page_order", lambda root: edit_set(root, lambda d: d["chunks"][0].update(page_start=5)), "invalid_chunk_set"),
    ("blank_text", lambda root: edit_set(root, lambda d: d["chunks"][0].update(text=" ", character_count=1)), "invalid_chunk_set"),
    ("id_prefix", lambda root: edit_set(root, lambda d: d["chunks"][0].update(id="otro-0001")), "invalid_chunk_set"),
    (
        "manifest_hash",
        lambda root: edit_manifest(root, lambda m: m["documents"][0].update(chunk_set_sha256="0" * 64)),
        "invalid_chunk_set",
    ),
    ("manifest_unknown_key", lambda root: edit_manifest(root, lambda m: m.update(extra=1)), "invalid_chunk_set"),
    ("missing_manifest", lambda root: (root / "chunks-manifest.json").unlink(), "invalid_chunk_set"),
    (
        "duplicate_id",
        lambda root: edit_set(
            root, lambda d: d["chunks"][1].update(id=d["chunks"][0]["id"])
        ),
        "duplicate_chunk_id",
    ),
    ("catalog_block_field", lambda root: edit_set(root, lambda d: d["catalog"].update(valid_until="2099-12-30")), "chunk_validity_mismatch"),
    ("catalog_block_hash", lambda root: edit_set(root, lambda d: d["catalog"].update(catalog_sha256="0" * 64)), "chunk_validity_mismatch"),
    ("catalog_block_extra", lambda root: edit_set(root, lambda d: d["catalog"].update(reviewed_by="x")), "chunk_validity_mismatch"),
    (
        "security_finding",
        lambda root: edit_set(
            root,
            lambda d: d["chunks"][0].update(
                text=d["chunks"][0]["text"] + " 12345678Z",
                character_count=len(d["chunks"][0]["text"] + " 12345678Z"),
            ),
        ),
        "corpus_security",
    ),
    (
        "zero_chunks",
        lambda root: edit_manifest(root, lambda m: m.update(documents=[])),
        "no_reviewed_chunks",
    ),
]


@pytest.mark.parametrize("name,damage,code", REFUSALS, ids=[item[0] for item in REFUSALS])
def test_malformed_or_unreviewed_input_refuses_and_keeps_the_index(tmp_path, name, damage, code) -> None:
    build(tmp_path)
    before = snapshot(tmp_path / "index")
    root = chunk_root(tmp_path)
    damage(root)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, chunks_root=root)
    assert (refused.value.code, refused.value.exit_code) == (code, 1)
    assert snapshot(tmp_path / "index") == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["chunks", "index"]


def test_a_catalog_that_changed_since_chunking_is_refused_as_stale(tmp_path) -> None:
    catalog = edited_catalog(tmp_path, lambda d: d["sources"][0].update(title="Otro título revisado"))
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, catalog_path=catalog)
    assert refused.value.code == "chunk_validity_mismatch"


def test_an_unreviewed_or_unknown_catalog_entry_is_refused(tmp_path) -> None:
    pending = edited_catalog(tmp_path, lambda d: d["sources"][0].update(review_status="pending"))
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, catalog_path=pending)
    assert refused.value.code in {"unreviewed_chunk_set", "invalid_catalog"}
    other_hash = edited_catalog(tmp_path, lambda d: d["sources"][0].update(content_sha256="1" * 64))
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, catalog_path=other_hash)
    assert refused.value.code == "chunk_validity_mismatch"


def test_an_invalid_catalog_is_refused(tmp_path) -> None:
    broken = tmp_path / "catalog.json"
    broken.write_text('{"schema_version": "source-catalog-v1", "sources": [{"id": "x"}]}', encoding="utf-8")
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, catalog_path=broken)
    assert (refused.value.code, refused.value.exit_code) == ("invalid_catalog", 1)
    broken.write_text("not json", encoding="utf-8")
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, catalog_path=broken)
    assert refused.value.code == "invalid_catalog"
    expired = AS_OF.replace(year=2100)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, as_of=expired)
    assert refused.value.code in {"invalid_catalog", "no_reviewed_chunks"}
    assert not (tmp_path / "index").exists()


def merge_record(path: Path, passages: Path, **overrides: Any) -> Path:
    record = {
        "schema_version": kr.MERGE_RECORD_VERSION,
        "package_id": "paquete-prueba",
        "reviewer": "fixture-reviewer",
        "approved_on": "2099-03-01",
        "catalog_sha256": sha(CATALOG),
        "passages_sha256": sha(passages),
        "canonical_changes_applied": True,
        "reindex_required": True,
        "reindexed": False,
        "released": False,
        "statement": "fixture",
    }
    record.update(overrides)
    path.write_text(_dump(record), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"reviewed_baseline_revision": None}, "approval_evidence_required"),
        ({"merge_record": Path("record.json")}, "approval_evidence_ambiguous"),
        ({"reviewed_baseline_revision": "abc"}, "approval_evidence_invalid"),
    ],
)
def test_missing_ambiguous_or_invalid_approval_refuses(tmp_path, extra, code) -> None:
    passages = tmp_path / "passages.json"
    passages.write_text('{"schema_version": "passage-set-v1", "passages": []}', encoding="utf-8")
    if "merge_record" in extra:
        extra = dict(extra, merge_record=merge_record(tmp_path / "record.json", passages), passages_path=passages)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, **extra)
    assert (refused.value.code, refused.value.exit_code) == (code, 1)
    assert not (tmp_path / "index").exists()


def test_a_merge_record_binds_the_catalog_and_passage_hashes(tmp_path) -> None:
    passages = tmp_path / "canonical-passages.json"
    passages.write_text('{"schema_version": "passage-set-v1", "passages": []}', encoding="utf-8")
    good = merge_record(tmp_path / "good.json", passages)
    report = build(tmp_path, reviewed_baseline_revision=None, merge_record=good, passages_path=passages)
    assert report.manifest["approval"]["kind"] == "merge_record"
    assert "fixture-reviewer" not in (tmp_path / "index" / "structured-index-manifest.json").read_text(encoding="utf-8")

    for name, overrides, code in (
        ("wrong_catalog", {"catalog_sha256": "0" * 64}, "approval_mismatch"),
        ("wrong_passages", {"passages_sha256": "0" * 64}, "approval_mismatch"),
        ("not_applied", {"canonical_changes_applied": False}, "merge_record_invalid"),
    ):
        bad = merge_record(tmp_path / (name + ".json"), passages, **overrides)
        with pytest.raises(sci.StructuredIndexError) as refused:
            build(tmp_path, "other", reviewed_baseline_revision=None, merge_record=bad, passages_path=passages)
        assert refused.value.code == code
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, "other", reviewed_baseline_revision=None, merge_record=good)
    assert (refused.value.code, refused.value.exit_code) == ("passages_required", 2)


# --- 4. Unsafe roots and usage errors abort before writing ---------------------------------


def test_unsafe_roots_and_missing_inputs_exit_2_and_write_nothing(tmp_path) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep", encoding="utf-8")
    a_file = tmp_path / "a-file"
    a_file.write_text("x", encoding="utf-8")
    knowledge_target = REPO_ROOT / "knowledge" / "structured-index-test-output"
    cases = [
        ({"output_root": knowledge_target}, "unsafe_output_root"),
        ({"output_root": CHUNKS}, "unsafe_output_root"),
        ({"output_root": CHUNKS / "inside"}, "unsafe_output_root"),
        ({"output_root": foreign}, "output_not_an_index"),
        ({"output_root": a_file}, "output_not_an_index"),
        ({"chunks_root": tmp_path / "missing"}, "missing_chunks_root"),
        ({"catalog_path": tmp_path / "missing.json"}, "missing_catalog"),
        ({"active_campaign": "26"}, "active_campaign_invalid"),
    ]
    for overrides, code in cases:
        with pytest.raises(sci.StructuredIndexError) as refused:
            build(tmp_path, **overrides)
        assert (refused.value.code, refused.value.exit_code) == (code, 2), code
    assert not knowledge_target.exists() and not (CHUNKS / "inside").exists()
    assert (foreign / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert a_file.read_text(encoding="utf-8") == "x"
    assert not (tmp_path / "index").exists()


def test_the_set_and_chunk_bounds_exit_2(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sci, "MAX_CHUNKS", 3)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path)
    assert (refused.value.code, refused.value.exit_code) == ("chunk_limit_exceeded", 2)
    monkeypatch.setattr(sci, "MAX_CHUNKS", 20000)
    monkeypatch.setattr(sci, "MAX_CHUNK_SETS", 0)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path)
    assert (refused.value.code, refused.value.exit_code) == ("chunk_set_limit_exceeded", 2)
    assert not (tmp_path / "index").exists()


# --- 5. Vectors use the existing local stack only ------------------------------------------


def test_vectors_are_built_by_the_existing_writers_and_recorded(tmp_path) -> None:
    report = build(tmp_path, vectors=fake_vectors())
    index = tmp_path / "index"
    vectors = report.manifest["vectors"]
    assert (index / "embedding-index.json").is_file() and (index / "vector-store").is_dir()
    assert vectors["embedding_index_sha256"] == sha(index / "embedding-index.json")
    assert vectors["store_manifest_sha256"] == sha(index / "vector-store" / sci.VECTOR_MANIFEST_FILE)
    passages = json.loads((index / "structured-passages.json").read_text(encoding="utf-8"))
    retriever = Retriever.from_documents(json.loads(CATALOG.read_text(encoding="utf-8")), passages, AS_OF, CAMPAIGN)
    assert vectors["documents_sha256"] == documents_sha256(retriever.indexed_documents())
    assert vectors["model"]["model_id"] == "fixture/embedding-model"
    embedding = json.loads((index / "embedding-index.json").read_text(encoding="utf-8"))
    assert embedding["schema_version"] == "passage-embedding-index-v1"
    assert [entry["passage_id"] for entry in embedding["passages"]] == [p["id"] for p in passages["passages"]]
    assert sci.verify_index(index).manifest["vectors"] == vectors
    assert report.manifest["files"].keys() == {
        "source_catalog.json",
        "structured-passages.json",
        "bm25-index.json",
        "embedding-index.json",
    }


def test_a_vector_failure_exits_2_with_nothing_written_and_the_index_kept(tmp_path) -> None:
    build(tmp_path)
    before = snapshot(tmp_path / "index")

    def failing(spec, artifact):
        raise EmbeddingExecutionError("encode_failed")

    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, vectors=fake_vectors(load_embedder=failing))
    assert (refused.value.code, refused.value.exit_code) == ("encode_failed", 2)
    assert snapshot(tmp_path / "index") == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["index"]


def test_an_artifact_that_fails_the_pin_exits_2(tmp_path) -> None:
    empty = tmp_path / "artifact"
    empty.mkdir()
    options = sci.VectorOptions(artifact=empty, config=EMBEDDING_SPEC, write_store=memory_store_writer)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, vectors=options)
    assert (refused.value.code, refused.value.exit_code) == ("artifact_invalid", 2)
    assert not (tmp_path / "index").exists()


@pytest.mark.skipif(importlib.util.find_spec("chromadb") is not None, reason="default environment only")
def test_without_the_hybrid_runtime_the_vector_step_exits_2(tmp_path) -> None:
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, vectors=sci.VectorOptions(artifact=tmp_path, config=kr.DEFAULT_EMBEDDING_CONFIG))
    assert (refused.value.code, refused.value.exit_code) == ("vector_runtime_unavailable", 2)
    with pytest.raises(sci.StructuredIndexError) as refused:
        build(tmp_path, vectors=sci.VectorOptions(artifact=tmp_path, config=tmp_path / "missing.json"))
    assert (refused.value.code, refused.value.exit_code) == ("embedding_config_invalid", 2)
    assert not (tmp_path / "index").exists()


# --- 7. A broken or stale index (verify and check) -----------------------------------------


def test_verify_and_status_detect_missing_tampered_and_stale_indexes(tmp_path) -> None:
    build(tmp_path)
    index = tmp_path / "index"
    assert sci.index_status(index, sha(CATALOG)) == "up_to_date"
    assert sci.index_status(index, "0" * 64) == "stale"
    assert sci.index_status(tmp_path / "missing", sha(CATALOG)) == "invalid"

    for name in ("structured-passages.json", "bm25-index.json", "source_catalog.json"):
        target = index / name
        original = target.read_bytes()
        target.write_bytes(original + b" ")
        assert sci.index_status(index, sha(CATALOG)) == "invalid", name
        target.write_bytes(original)
        target.unlink()
        assert sci.index_status(index, sha(CATALOG)) == "invalid", name
        target.write_bytes(original)
    manifest = index / "structured-index-manifest.json"
    original = manifest.read_text(encoding="utf-8")
    for damage in ("{", json.dumps({"schema_version": "structured-chunk-index-v1"})):
        manifest.write_text(damage, encoding="utf-8")
        assert sci.index_status(index, sha(CATALOG)) == "invalid"
    document = json.loads(original)
    document["inputs"]["extra"] = 1
    manifest.write_text(_dump(document), encoding="utf-8")
    assert sci.index_status(index, sha(CATALOG)) == "invalid"
    manifest.write_text(original, encoding="utf-8")
    assert sci.index_status(index, sha(CATALOG)) == "up_to_date"


def test_the_manifest_matches_the_published_schema_and_module(tmp_path) -> None:
    assert sci.check_contract() == []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(build(tmp_path).manifest)
    validator.validate(build(tmp_path, "vec", vectors=fake_vectors()).manifest)
    assert list(validator.iter_errors(dict(build(tmp_path, "again").manifest, extra=1)))


# --- 6. The service is unchanged unless the flag is effective ------------------------------


@pytest.fixture(scope="module")
def built_index(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("structured")
    build(root)
    return root / "index"


def loader(env: Dict[str, str], index: Path) -> Any:
    return sci.structured_corpus_from_environment(
        dict(env, MANIJERO_STRUCTURED_INDEX_DIR=str(index)) if index else env,
        checkout_catalog_path=CATALOG,
    )


@pytest.mark.parametrize("environment", [{}, LOCAL, QA, {"MANIJERO_ENVIRONMENT": "prod"}])
@pytest.mark.parametrize("setting", [None, "", "off"])
def test_flag_unset_or_off_never_changes_the_corpus_in_any_environment(built_index, log, environment, setting) -> None:
    env = {key: value for key, value in environment.items() if key != "MANIJERO_STRUCTURED_INDEX"}
    if setting is not None:
        env["MANIJERO_STRUCTURED_INDEX"] = setting
    assert loader(env, built_index) is None
    assert log == []


@pytest.mark.parametrize(
    "environment",
    [
        {"MANIJERO_ENVIRONMENT": "local", "MANIJERO_DEPLOYMENT_PROFILE": "development"},
        {"MANIJERO_ENVIRONMENT": "qa", "MANIJERO_DEPLOYMENT_PROFILE": "pilot"},
    ],
    ids=["local-on", "qa-on"],
)
def test_the_flag_serves_the_verified_index_in_local_development_and_qa(built_index, log, environment) -> None:
    result = loader(dict(environment, MANIJERO_STRUCTURED_INDEX="on"), built_index)
    assert isinstance(result, CorpusDocuments) and not result.load_error and result.release_id is None
    verified = sci.verify_index(built_index)
    assert (result.catalog, result.passages) == (verified.catalog, verified.passages)
    assert loader(dict(environment, MANIJERO_STRUCTURED_INDEX="on"), built_index) is not None
    assert log == [{"event": "structured_index", "state": "served", "reason": "ok"}]


@pytest.mark.parametrize(
    "environment",
    [
        {"MANIJERO_ENVIRONMENT": "prod", "MANIJERO_DEPLOYMENT_PROFILE": "pilot"},
        {"MANIJERO_ENVIRONMENT": "prod", "MANIJERO_DEPLOYMENT_PROFILE": "development"},
        {"MANIJERO_ENVIRONMENT": "pilot"},
        {"MANIJERO_ENVIRONMENT": "QA"},
        {"MANIJERO_ENVIRONMENT": " qa"},
        {"MANIJERO_ENVIRONMENT": "qa "},
        {"MANIJERO_ENVIRONMENT": "local", "MANIJERO_DEPLOYMENT_PROFILE": "pilot"},
        {"MANIJERO_ENVIRONMENT": "local", "MANIJERO_DEPLOYMENT_PROFILE": "Development"},
        {"MANIJERO_ENVIRONMENT": "local"},
        {"MANIJERO_DEPLOYMENT_PROFILE": "development"},
        {},
    ],
)
def test_the_flag_is_ignored_outside_local_development_and_qa(built_index, log, environment) -> None:
    assert loader(dict(environment, MANIJERO_STRUCTURED_INDEX="on"), built_index) is None
    assert log == [{"event": "structured_index", "state": "ignored", "reason": "structured_index_environment_refused"}]


def test_setting_and_directory_errors_keep_todays_corpus_with_a_fixed_reason(built_index, log, tmp_path) -> None:
    assert loader(dict(LOCAL, MANIJERO_STRUCTURED_INDEX="yes"), built_index) is None
    assert loader(dict(LOCAL, MANIJERO_STRUCTURED_INDEX=" on"), built_index) is None
    assert loader(dict(LOCAL), None) is None
    assert loader(dict(LOCAL), tmp_path / "no-such-dir") is None
    reasons = [record["reason"] for record in log]
    assert reasons == [
        "structured_index_setting_invalid",
        "structured_index_not_configured",
    ]
    assert all(record["state"] == "ignored" for record in log)


def test_a_broken_or_stale_index_never_answers(tmp_path, log) -> None:
    build(tmp_path)
    index = tmp_path / "index"
    ok = loader(LOCAL, index)
    assert isinstance(ok, CorpusDocuments) and not ok.load_error

    # Catalog drift: the checkout catalog differs from the one the index was built from.
    drifted = edited_catalog(tmp_path, lambda d: d["sources"][0].update(title="Otro título"))
    stale = sci.structured_corpus_from_environment(
        dict(LOCAL, MANIJERO_STRUCTURED_INDEX_DIR=str(index)), checkout_catalog_path=drifted
    )
    assert stale.load_error is True and stale.catalog is None
    missing_catalog = sci.structured_corpus_from_environment(
        dict(LOCAL, MANIJERO_STRUCTURED_INDEX_DIR=str(index)), checkout_catalog_path=tmp_path / "gone.json"
    )
    assert missing_catalog.load_error is True

    passages = index / "structured-passages.json"
    original = passages.read_bytes()
    passages.write_bytes(original + b" ")
    tampered = loader(LOCAL, index)
    assert tampered.load_error is True
    passages.write_bytes(original)
    (index / "structured-index-manifest.json").write_text("{", encoding="utf-8")
    assert loader(LOCAL, index).load_error is True
    reasons = [record["reason"] for record in log if record["state"] == "refused"]
    assert reasons == ["structured_index_stale", "structured_index_invalid"]


def _fake_release(monkeypatch, catalog_sha256: str) -> None:
    monkeypatch.setattr(kr, "load_published_corpus", lambda root: ({}, {}, "0123456789abcdef"))
    monkeypatch.setattr(kr, "release_dir", lambda root, release_id: Path(root) / "releases" / release_id)
    monkeypatch.setattr(
        kr, "read_manifest", lambda directory: {"files": {"source_catalog.json": {"sha256": catalog_sha256}}}
    )


def test_qa_checks_staleness_against_the_release_catalog_not_the_checkout(built_index, log, monkeypatch, tmp_path) -> None:
    env = dict(QA, MANIJERO_KNOWLEDGE_RELEASE_ROOT=str(tmp_path / "release-root"))
    served: List[Any] = []
    real = ask_api._load_published_release
    monkeypatch.setattr(ask_api, "_load_published_release", lambda root: served.append(root) or real(root))

    _fake_release(monkeypatch, sha(CATALOG))
    fresh = sci.structured_corpus_from_environment(
        dict(env, MANIJERO_STRUCTURED_INDEX_DIR=str(built_index)), checkout_catalog_path=tmp_path / "ignored.json"
    )
    assert isinstance(fresh, CorpusDocuments) and not fresh.load_error and fresh.release_id is None

    _fake_release(monkeypatch, "0" * 64)
    stale = sci.structured_corpus_from_environment(
        dict(env, MANIJERO_STRUCTURED_INDEX_DIR=str(built_index)), checkout_catalog_path=CATALOG
    )
    assert stale.load_error is True
    assert served == []

    monkeypatch.setattr(kr, "load_published_corpus", lambda root: (_ for _ in ()).throw(kr.ReleaseError("no_current_release")))
    unavailable = sci.structured_corpus_from_environment(
        dict(env, MANIJERO_STRUCTURED_INDEX_DIR=str(built_index)), checkout_catalog_path=CATALOG
    )
    assert unavailable.load_error is True
    assert [record["reason"] for record in log] == ["ok", "structured_index_stale"]


# --- 6/7. /ask and /ready through the route -------------------------------------------------


STRUCTURED_QUESTION = {
    "question": "¿Cuál es el plazo de la solicitud según el decreto?",
    "land_context": {"mode": "general", "lands": []},
}
CANONICAL_QUESTION = {
    "question": "¿Hasta cuándo puedo presentar la solicitud única de 2026?",
    "land_context": {"mode": "general", "lands": []},
}


@pytest.fixture
def service(monkeypatch, log):
    clock = {"as_of": date(2026, 10, 13)}
    for name in (
        "MANIJERO_STRUCTURED_INDEX",
        "MANIJERO_STRUCTURED_INDEX_DIR",
        "MANIJERO_ENVIRONMENT",
        "MANIJERO_DEPLOYMENT_PROFILE",
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ask_api, "_LAST_RELEASE_OUTCOME", None)
    app.dependency_overrides[get_as_of_date] = lambda: clock["as_of"]
    app.dependency_overrides[get_retrieval_backend] = Bm25Backend
    with TestClient(app) as client:
        yield client, clock
    app.dependency_overrides.clear()


def use_structured(monkeypatch, clock, index: Path, **environment: str) -> None:
    clock["as_of"] = AS_OF
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", CAMPAIGN)
    monkeypatch.setenv("MANIJERO_STRUCTURED_INDEX_DIR", str(index))
    monkeypatch.setattr(ask_api, "CATALOG_PATH", CATALOG)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)


def locations(response) -> List[str]:
    return [source["location"] for source in response.json()["sources"]]


@pytest.mark.parametrize("environment", [LOCAL, QA], ids=["local-on", "qa-on"])
def test_ask_and_ready_read_the_structured_index_only_when_effective(service, monkeypatch, built_index, environment) -> None:
    client, clock = service
    canonical_catalog = ask_api.CATALOG_PATH
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", "2026")
    baseline = client.post("/ask", json=CANONICAL_QUESTION)
    assert baseline.status_code == 200 and baseline.json()["status"] == "answered"

    use_structured(monkeypatch, clock, built_index, **environment)
    response = client.post("/ask", json=STRUCTURED_QUESTION)
    assert response.status_code == 200 and response.json()["status"] == "answered"
    assert locations(response)[0] == "CAPÍTULO II › Artículo 15. Plazo, pág. 3"
    assert client.get("/ready").status_code == 200

    monkeypatch.setenv("MANIJERO_STRUCTURED_INDEX", "off")
    monkeypatch.setattr(ask_api, "CATALOG_PATH", canonical_catalog)
    clock["as_of"] = date(2026, 10, 13)
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", "2026")
    assert client.post("/ask", json=CANONICAL_QUESTION).json() == baseline.json()


@pytest.mark.parametrize(
    "environment",
    [
        {"MANIJERO_ENVIRONMENT": "prod", "MANIJERO_DEPLOYMENT_PROFILE": "pilot"},
        {"MANIJERO_ENVIRONMENT": "pilot"},
        {},
    ],
    ids=["prod", "pilot", "unset"],
)
def test_ask_with_the_flag_on_outside_local_development_and_qa_gives_todays_answer(
    service, monkeypatch, built_index, environment
) -> None:
    client, clock = service
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", "2026")
    baseline = client.post("/ask", json=CANONICAL_QUESTION).json()
    monkeypatch.setenv("MANIJERO_STRUCTURED_INDEX", "on")
    monkeypatch.setenv("MANIJERO_STRUCTURED_INDEX_DIR", str(built_index))
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    assert client.post("/ask", json=CANONICAL_QUESTION).json() == baseline
    assert all("pág." not in location for location in [s["location"] for s in baseline["sources"]])


def test_a_tampered_index_gives_the_generic_unavailable_answer(service, monkeypatch, tmp_path, log) -> None:
    client, clock = service
    build(tmp_path)
    index = tmp_path / "index"
    use_structured(monkeypatch, clock, index, MANIJERO_STRUCTURED_INDEX="on", **{k: v for k, v in LOCAL.items() if k != "MANIJERO_STRUCTURED_INDEX"})
    assert client.get("/ready").status_code == 200
    target = index / "structured-passages.json"
    target.write_bytes(target.read_bytes() + b" ")
    ready = client.get("/ready")
    ask = client.post("/ask", json=STRUCTURED_QUESTION)
    assert (ready.status_code, ready.json()) == (503, {"status": "unavailable", "service": "manijero-backend"})
    assert (ask.status_code, ask.json()) == (503, {"detail": "Answer service is temporarily unavailable."})
    assert log[-1] == {"event": "structured_index", "state": "refused", "reason": "structured_index_invalid"}
    assert STRUCTURED_QUESTION["question"] not in json.dumps(log)


def test_explicit_paths_gates_and_the_release_builder_ignore_the_flag(monkeypatch, built_index) -> None:
    for name, value in dict(LOCAL, MANIJERO_STRUCTURED_INDEX_DIR=str(built_index)).items():
        monkeypatch.setenv(name, value)
    canonical = ask_api.load_corpus_documents(REPO_ROOT / "knowledge" / "source_catalog.json", REPO_ROOT / "knowledge" / "passages.json")
    assert canonical.load_error is False
    assert all(not passage["id"].startswith("decreto-123") for passage in canonical.passages["passages"])
    for module in ("release_gates.py", "knowledge_release.py", "knowledge_review.py", "review_package.py", "pilot_ops.py"):
        path = BACKEND_ROOT / "app" / module
        if path.exists():
            assert "structured_chunk_index" not in path.read_text(encoding="utf-8"), module


def test_service_import_does_not_load_heavy_or_embedding_modules() -> None:
    code = (
        "import sys\n"
        "import app.main\n"
        "import app.structured_chunk_index\n"
        "names = ['app.release_gates', 'app.embedding_index', 'app.vector_store', 'chromadb', 'torch']\n"
        "print([name for name in names if name in sys.modules])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(BACKEND_ROOT))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


# --- CLI and output hygiene ----------------------------------------------------------------


def run_cli(capsys, *argv: str):
    try:
        code = cli.main(list(argv))
    except SystemExit as exit_:
        code = exit_.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def build_args(output: Path, *extra: str, chunks: Path = CHUNKS) -> List[str]:
    return [
        "build", "--chunks", str(chunks), "--catalog", str(CATALOG), "--as-of", "2099-06-01",
        "--active-campaign", CAMPAIGN, "--output", str(output), *extra,
    ]


def assert_one_result_line(out: str) -> str:
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines and lines[-1].startswith("Result: ")
    assert sum(1 for line in lines if line.startswith("Result:")) == 1
    return lines[-1]


def test_cli_exit_codes_and_the_last_line_is_always_one_result_line(tmp_path, capsys) -> None:
    index = tmp_path / "index"
    code, out, _ = run_cli(capsys, *build_args(index, "--reviewed-baseline-revision", REVISION))
    assert code == 0 and "built the structured index from 4 chunks in 1 documents" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, *build_args(index, "--reviewed-baseline-revision", REVISION))
    assert code == 0 and "already up to date" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, "check", "--index", str(index), "--catalog", str(CATALOG))
    assert code == 0 and "up to date" in assert_one_result_line(out)

    other = edited_catalog(tmp_path, lambda d: d["sources"][0].update(title="Otro título"))
    code, out, _ = run_cli(capsys, "check", "--index", str(index), "--catalog", str(other))
    assert code == 1 and "stale" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, "check", "--index", str(tmp_path / "none"), "--catalog", str(CATALOG))
    assert code == 1 and "invalid" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, "check", "--index", str(index), "--catalog", str(tmp_path / "none.json"))
    assert code == 2 and "missing_catalog" in assert_one_result_line(out)

    before = snapshot(index)
    root = chunk_root(tmp_path)
    edit_set(root, _unknown_validity)
    code, out, _ = run_cli(capsys, *build_args(index, "--reviewed-baseline-revision", REVISION, chunks=root))
    line = assert_one_result_line(out)
    assert code == 1 and "nothing was written" in line and "unreviewed_chunk_set" in line
    assert snapshot(index) == before
    code, out, _ = run_cli(capsys, *build_args(tmp_path / "x"))
    assert code == 1 and "approval_evidence_required" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, *build_args(REPO_ROOT / "knowledge" / "nope", "--reviewed-baseline-revision", REVISION))
    assert code == 2 and "unsafe_output_root" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, "build", "--chunks", str(CHUNKS))
    assert code == 2 and "usage_error" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, *build_args(tmp_path / "y", "--embedding-config", str(EMBEDDING_SPEC)))
    assert code == 2 and "usage_error" in assert_one_result_line(out)
    code, out, _ = run_cli(capsys, "build", "--as-of", "soon")
    assert code == 2 and assert_one_result_line(out)
    assert not (tmp_path / "x").exists() and not (tmp_path / "y").exists()


def test_no_chunk_text_reviewer_or_question_appears_in_output_or_logs(tmp_path, capsys, log) -> None:
    root = chunk_root(tmp_path)
    outputs: List[str] = []
    for argv in (
        build_args(tmp_path / "index", "--reviewed-baseline-revision", REVISION),
        ["check", "--index", str(tmp_path / "index"), "--catalog", str(CATALOG)],
        build_args(tmp_path / "other", chunks=root),
    ):
        _, out, err = run_cli(capsys, *argv)
        outputs.append(out + err)
    edit_set(root, _unknown_validity)
    _, out, err = run_cli(capsys, *build_args(tmp_path / "third", "--reviewed-baseline-revision", REVISION, chunks=root))
    outputs.append(out + err)
    loader(LOCAL, tmp_path / "index")
    loader(dict(LOCAL, MANIJERO_STRUCTURED_INDEX="maybe"), tmp_path / "index")
    outputs.append(json.dumps(log))
    text = "\n".join(outputs)
    for secret in ("El plazo es de tres meses", "fixture-reviewer", "Decreto 123", "procedimiento de solicitud"):
        assert secret not in text
