"""Knowledge releases that package a Chroma vector store.

Skipped when the optional ``chromadb`` runtime is absent (the default backend
environment). Run with the pinned hybrid runtime::

    MANIJERO_PYTHON=backend/.venv-hybrid/bin/python ./scripts/init.sh --backend-tests tests/test_knowledge_release_chroma.py

Vectors are synthetic 1024-dimension unit vectors bound to the repository model pin;
no model is loaded and nothing is downloaded.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import pytest

pytest.importorskip("chromadb")

from app import knowledge_release as kr  # noqa: E402
from app.embedding_index import IndexInputs, PassageEmbeddingIndex, build_index_document, write_index_atomic  # noqa: E402
from app.embeddings import load_model_spec  # noqa: E402
from app.hybrid_retrieval import HybridBackend, HybridComponents, HybridSettings  # noqa: E402
from app.retrieval import Retriever  # noqa: E402
from app.vector_store import MANIFEST_NAME, ChromaPassageStore  # noqa: E402

KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"
SPEC = load_model_spec(kr.DEFAULT_EMBEDDING_CONFIG)
AS_OF = date(2026, 10, 13)
CAMPAIGN = "2026"
REVISION = "0123456789abcdef0123456789abcdef01234567"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path: Path) -> Dict[str, Path]:
    paths = {}
    for key, name in (("catalog", "source_catalog.json"), ("passages", "passages.json"), ("cases", "pac_answer_eval.json")):
        target = tmp_path / name
        target.write_bytes((KNOWLEDGE / name).read_bytes())
        paths[key] = target
    return paths


def fake_index(path: Path, inputs: Dict[str, Path]) -> Path:
    catalog = json.loads(inputs["catalog"].read_text(encoding="utf-8"))
    passages = json.loads(inputs["passages"].read_text(encoding="utf-8"))
    admitted = Retriever.from_documents(catalog, passages, AS_OF, CAMPAIGN).indexed_documents()
    vectors = {}
    for position, (passage_id, _) in enumerate(admitted):
        vector = [0.0] * SPEC.embedding_dimension
        vector[position] = 1.0
        vectors[passage_id] = tuple(vector)
    index_inputs = IndexInputs(sha(inputs["catalog"]), sha(inputs["passages"]), AS_OF.isoformat(), CAMPAIGN)
    write_index_atomic(path, build_index_document(PassageEmbeddingIndex(SPEC.embedding_dimension, vectors), SPEC, index_inputs), SPEC)
    return path


def prepare(root: Path, inputs: Dict[str, Path], index: Path, **overrides: Any) -> kr.PrepareResult:
    arguments: Dict[str, Any] = dict(
        root=root,
        catalog=inputs["catalog"],
        passages=inputs["passages"],
        cases=inputs["cases"],
        as_of=AS_OF,
        active_campaign=CAMPAIGN,
        code_revision=REVISION,
        reviewed_baseline_revision=REVISION,
        embedding_index=index,
        with_vector_store=True,
    )
    arguments.update(overrides)
    return kr.prepare_release(**arguments)


def test_release_packages_the_store_and_records_its_digests(tmp_path, inputs) -> None:
    index = fake_index(tmp_path / "index.json", inputs)
    result = prepare(tmp_path / "root", inputs, index)

    assert result.passed, result.failures
    release = tmp_path / "root" / "releases" / result.release_id
    store_manifest = json.loads((release / "vector-store" / MANIFEST_NAME).read_text(encoding="utf-8"))
    vector = result.manifest["vector"]
    assert vector["documents_sha256"] == store_manifest["inputs"]["documents_sha256"]
    assert vector["vectors_sha256"] == store_manifest["vectors_sha256"]
    assert vector["embedding_index_sha256"] == sha(index) == sha(release / "embedding-index.json")
    assert vector["model"] == SPEC.index_metadata()
    kr.publish(tmp_path / "root", result.release_id, AS_OF, CAMPAIGN)
    assert kr.verify(tmp_path / "root")["release_id"] == result.release_id
    ChromaPassageStore.open(tmp_path / "root" / "current" / "vector-store", SPEC)


def test_two_builds_from_the_same_index_have_equal_content_digests(tmp_path, inputs) -> None:
    index = fake_index(tmp_path / "index.json", inputs)
    first = prepare(tmp_path / "a", inputs, index)
    second = prepare(tmp_path / "b", inputs, index)

    assert first.release_id == second.release_id
    assert first.manifest["vector"] == second.manifest["vector"]
    assert kr.compare_releases(tmp_path / "a/releases" / first.release_id, tmp_path / "b/releases" / second.release_id) == []


class _Embedder:
    model_id = SPEC.model_id
    model_revision = SPEC.model_revision
    normalized = True
    dimension = SPEC.embedding_dimension

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        vector = [0.0] * SPEC.embedding_dimension
        vector[0] = 1.0
        return tuple(tuple(vector) for _ in texts)


def test_a_store_from_another_release_is_stale_until_a_new_backend_is_built(tmp_path, inputs) -> None:
    root = tmp_path / "root"
    first = prepare(root, inputs, fake_index(tmp_path / "index-a.json", inputs))
    kr.publish(root, first.release_id, AS_OF, CAMPAIGN)
    settings = HybridSettings(rrf_k=60, candidate_depth=20, vector_min_similarity=0.0, config_sha256="c" * 64)

    def backend() -> HybridBackend:
        store = ChromaPassageStore.open(root / "current" / "vector-store", SPEC)
        return HybridBackend(lambda: HybridComponents(spec=SPEC, embedder=_Embedder(), store=store, settings=settings))

    def retriever() -> Retriever:
        catalog, passages, _ = kr.load_published_corpus(root)
        return Retriever.from_documents(catalog, passages, AS_OF, CAMPAIGN)

    old = backend()
    assert old.status(retriever(), CAMPAIGN).up_to_date

    passages = json.loads(inputs["passages"].read_text(encoding="utf-8"))
    for passage in passages["passages"]:
        if passage["id"] == "pasaje-plazo-modificacion-2026-andalucia":
            # Changes the admitted (id, text) documents without regressing a reviewed case.
            passage["text"] = passage["text"] + " "
    changed = dict(inputs, passages=tmp_path / "passages-b.json")
    changed["passages"].write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")
    second = prepare(root, changed, fake_index(tmp_path / "index-b.json", changed))
    assert second.passed, second.failures
    kr.publish(root, second.release_id, AS_OF, CAMPAIGN)

    # The old backend keeps its loaded store: freshness is by admitted documents, so a
    # store whose documents differ from the new release is stale (BM25) until restart.
    status = old.status(retriever(), CAMPAIGN)
    assert not status.up_to_date and "documents_changed" in status.reasons
    assert backend().status(retriever(), CAMPAIGN).up_to_date
