"""Chroma adapter tests for the derived passage vector store.

Skipped when the optional ``chromadb`` runtime is absent (the default backend
environment). Run them with the pinned hybrid runtime::

    backend/.venv-hybrid/bin/python -m pytest backend/tests/test_vector_store_chroma.py

They write real Chroma persistent stores under ``tmp_path`` with synthetic
four-dimension vectors; no model is loaded and nothing is downloaded.
"""

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("chromadb")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.embedding_index import IndexInputs, PassageEmbeddingIndex  # noqa: E402
from app.embeddings import load_model_spec  # noqa: E402
from app.hybrid_retrieval import HybridRanker, HybridSettings  # noqa: E402
from app.retrieval import Retriever, load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402
from app.vector_store import (  # noqa: E402
    MANIFEST_NAME,
    ChromaPassageStore,
    VectorStoreError,
    store_status,
    write_store,
)

TESTS = Path(__file__).resolve().parent
CLARIFICATION = TESTS / "fixtures" / "clarification"
SPEC = load_model_spec(TESTS / "fixtures" / "embeddings" / "spec.json")
AS_OF = date(2026, 10, 13)
DIGEST = "c" * 64
VECTORS = {
    "fixture-clar-riego-regadio-1": (1.0, 0.0, 0.0, 0.0),
    "fixture-clar-riego-secano-1": (0.0, 1.0, 0.0, 0.0),
    "fixture-clar-solicitud-1": (0.0, 0.0, 1.0, 0.0),
}


def retriever() -> Retriever:
    return Retriever.from_documents(
        load_catalog(CLARIFICATION / "catalog.json"),
        load_passage_set(CLARIFICATION / "passages.json"),
        AS_OF,
        "2026",
    )


def inputs() -> IndexInputs:
    return IndexInputs(catalog_sha256=DIGEST, passages_sha256=DIGEST, as_of=AS_OF.isoformat(), active_campaign="2026")


def build(store: Path, vectors=VECTORS) -> dict:
    return write_store(
        store,
        PassageEmbeddingIndex(dimension=4, vectors=vectors),
        SPEC,
        inputs(),
        retriever().indexed_documents(),
        DIGEST,
    )


def test_store_round_trips_ids_and_queries_by_cosine(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    manifest = build(store_dir)

    store = ChromaPassageStore.open(store_dir, SPEC)
    matches = store.query([0.1, 0.9, 0.0, 0.0], depth=3)

    assert manifest["inputs"]["passage_count"] == 3
    assert [match.passage_id for match in matches][0] == "fixture-clar-riego-secano-1"
    assert matches[0].similarity == pytest.approx(0.9 / (0.82 ** 0.5), abs=1e-5)
    assert [match.rank for match in matches] == [1, 2, 3]
    assert store_status(store_dir, SPEC, "2026", retriever().indexed_documents()).up_to_date


def test_equal_similarities_break_ties_by_passage_id(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)

    matches = ChromaPassageStore.open(store_dir, SPEC).query([1.0, 1.0, 1.0, 0.0], depth=3)

    assert [match.passage_id for match in matches] == sorted(VECTORS)


def test_store_never_contains_passage_text(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)
    texts = [text for _, text in retriever().indexed_documents()]

    for path in store_dir.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            for text in texts:
                assert text.encode("utf-8") not in content
                assert text[:40].encode("utf-8") not in content
    with sqlite3.connect(str(store_dir / "chroma.sqlite3")) as connection:
        tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table'")]
        for table in tables:
            for row in connection.execute('select * from "{}"'.format(table)):
                for value in row:
                    if isinstance(value, str):
                        assert not any(text[:40] in value for text in texts)


def test_rebuild_replaces_an_existing_store_atomically(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    first = build(store_dir)
    changed = dict(VECTORS, **{"fixture-clar-solicitud-1": (0.0, 0.0, 0.0, 1.0)})

    second = build(store_dir, changed)

    assert first["vectors_sha256"] != second["vectors_sha256"]
    assert read_manifest_digest(store_dir) == second["vectors_sha256"]
    assert ChromaPassageStore.open(store_dir, SPEC).query([0, 0, 0, 1], 1)[0].passage_id == "fixture-clar-solicitud-1"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["store"]


def read_manifest_digest(store_dir: Path) -> str:
    return json.loads((store_dir / MANIFEST_NAME).read_text(encoding="utf-8"))["vectors_sha256"]


def test_open_refuses_a_tampered_manifest(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    manifest = build(store_dir)
    manifest["vectors_sha256"] = "d" * 64
    (store_dir / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(VectorStoreError, match="store_vectors_mismatch"):
        ChromaPassageStore.open(store_dir, SPEC)


def test_open_refuses_a_store_whose_ids_differ_from_the_manifest(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    manifest = build(store_dir)
    manifest["passage_ids"] = manifest["passage_ids"][:2]
    manifest["inputs"]["passage_count"] = 2
    (store_dir / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(VectorStoreError, match="store_ids_mismatch"):
        ChromaPassageStore.open(store_dir, SPEC)


def test_open_refuses_a_different_model_pin(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)
    other = load_model_spec(TESTS / "fixtures" / "embeddings" / "spec_pooling_mismatch.json")

    with pytest.raises(VectorStoreError, match="store_model_mismatch"):
        ChromaPassageStore.open(store_dir, other)


def test_open_refuses_a_missing_collection(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)
    manifest = (store_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / MANIFEST_NAME).write_text(manifest, encoding="utf-8")

    with pytest.raises(VectorStoreError, match="store_open_failed"):
        ChromaPassageStore.open(empty, SPEC)


def test_query_rejects_wrong_dimension_and_non_finite_vectors(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)
    store = ChromaPassageStore.open(store_dir, SPEC)

    with pytest.raises(VectorStoreError, match="query_dimension_mismatch"):
        store.query([1.0, 0.0], depth=3)
    with pytest.raises(VectorStoreError, match="query_not_finite"):
        store.query([float("nan"), 0.0, 0.0, 0.0], depth=3)
    assert store.query([1.0, 0.0, 0.0, 0.0], depth=0) == ()


def test_a_failed_build_leaves_the_previous_store_in_place(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    first = build(store_dir)

    with pytest.raises(VectorStoreError, match="store_documents_mismatch"):
        build(store_dir, {"fixture-clar-solicitud-1": (0.0, 0.0, 1.0, 0.0)})

    assert read_manifest_digest(store_dir) == first["vectors_sha256"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["store"]


def test_chroma_store_drives_hybrid_ranking_end_to_end(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    build(store_dir)
    store = ChromaPassageStore.open(store_dir, SPEC)

    class SecanoEmbedder:
        dimension = 4

        def embed(self, texts):
            return tuple((0.0, 1.0, 0.0, 0.0) for _ in texts)

    settings = HybridSettings(rrf_k=60, candidate_depth=20, vector_min_similarity=0.0, config_sha256=DIGEST)
    ranker = HybridRanker(SecanoEmbedder(), store, settings)

    candidates = retriever().with_ranker(ranker).search("riego", k=5)

    assert ranker.last_trace.used_vector is True
    assert candidates[0].passage_id == "fixture-clar-riego-secano-1"
