"""Persistent, rebuildable Chroma vector store over reviewed passages.

The store is a *derived artifact*, like the ``passage-embedding-index-v1`` file it
is built from. It never lives under ``knowledge/``, never stores passage text, a
question, or a score, and never becomes an answer source: it maps opaque passage
ids to the pinned model's vectors so hybrid retrieval can rank passages that
:class:`app.retrieval.Retriever` already admitted.

Layout of one store directory::

    <store>/manijero-vector-store.json   # manifest, written last (closed contract)
    <store>/chroma.sqlite3 ...           # Chroma persistent client files

The manifest is the authority. It records the model pin, the corpus inputs the
source index was built from, a digest of the exact admitted ``(passage_id,
text)`` documents, the sorted passage ids, and a digest of the vectors Chroma
returned after the write. Opening a store re-checks the collection against the
manifest (count, ids, vector digest) and refuses anything that differs.

Freshness at answer time does not depend on file digests or ``as_of``: the store
is current only while the model pin, the active campaign, and the digest of the
documents the *current* retriever admits all match. A source that expires, a
passage edit, or a campaign change therefore makes the store stale and hybrid
retrieval falls back to BM25.

``chromadb`` is optional and imported lazily; manifest validation and freshness
need no runtime. Chroma anonymized telemetry is always disabled, no Chroma
embedding function is ever configured (vectors are always supplied), and every
error carries a fixed code only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.embedding_index import IndexInputs, PassageEmbeddingIndex
from app.embeddings import EmbeddingError, EmbeddingModelSpec
from app.source_catalog import is_non_blank_string

STORE_SCHEMA_VERSION = "chroma-passage-store-v1"
MANIFEST_NAME = "manijero-vector-store.json"
COLLECTION_NAME = "manijero-reviewed-passages"
DISTANCE = "cosine"
CHROMADB_VERSION = "1.5.9"

MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "collection",
        "distance",
        "chromadb_version",
        "model",
        "inputs",
        "source_index_sha256",
        "vectors_sha256",
        "passage_ids",
    }
)
MODEL_KEYS = frozenset(
    {
        "model_id",
        "model_revision",
        "embedding_dimension",
        "pooling",
        "normalize",
        "dtype",
        "config_sha256",
    }
)
INPUT_KEYS = frozenset(
    {
        "catalog_sha256",
        "passages_sha256",
        "as_of",
        "active_campaign",
        "documents_sha256",
        "passage_count",
    }
)

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

STORE_UP_TO_DATE = "up_to_date"
STORE_MISSING = "missing"
STORE_STALE = "stale"
STORE_INVALID = "invalid"


class VectorStoreError(EmbeddingError):
    """A vector store is unreadable, inconsistent, refused, or failed to query."""


class VectorStoreUnavailable(VectorStoreError):
    """The optional ``chromadb`` runtime is not installed or failed to import."""


@dataclass(frozen=True)
class VectorMatch:
    """One nearest passage from the vector store, by cosine similarity."""

    passage_id: str
    similarity: float
    rank: int


@dataclass(frozen=True)
class StoreStatus:
    """Freshness of a store against the current pin, campaign, and documents."""

    state: str
    reasons: Tuple[str, ...]

    @property
    def up_to_date(self) -> bool:
        return self.state == STORE_UP_TO_DATE


def documents_sha256(documents: Sequence[Tuple[str, str]]) -> str:
    """Digest the exact admitted ``(passage_id, text)`` documents, id-ordered."""

    ordered = sorted((str(passage_id), str(text)) for passage_id, text in documents)
    payload = json.dumps(
        [list(pair) for pair in ordered], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def vectors_sha256(vectors: Mapping[str, Sequence[float]]) -> str:
    """Digest id-ordered vectors as little-endian ``float32`` (Chroma's storage)."""

    digest = hashlib.sha256()
    for passage_id in sorted(vectors):
        values = [float(value) for value in vectors[passage_id]]
        digest.update(passage_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(struct.pack("<{}f".format(len(values)), *values))
    return digest.hexdigest()


def build_manifest(
    index: PassageEmbeddingIndex,
    spec: EmbeddingModelSpec,
    inputs: IndexInputs,
    documents: Sequence[Tuple[str, str]],
    source_index_sha256: str,
    stored_vectors_sha256: str,
) -> Dict[str, Any]:
    """Return the validated manifest for a store built from ``index``."""

    passage_ids = list(index.passage_ids)
    if passage_ids != sorted(passage_id for passage_id, _ in documents):
        raise VectorStoreError("store_documents_mismatch")
    manifest = {
        "schema_version": STORE_SCHEMA_VERSION,
        "collection": COLLECTION_NAME,
        "distance": DISTANCE,
        "chromadb_version": CHROMADB_VERSION,
        "model": spec.index_metadata(),
        "inputs": {
            "catalog_sha256": inputs.catalog_sha256,
            "passages_sha256": inputs.passages_sha256,
            "as_of": inputs.as_of,
            "active_campaign": inputs.active_campaign,
            "documents_sha256": documents_sha256(documents),
            "passage_count": len(passage_ids),
        },
        "source_index_sha256": source_index_sha256,
        "vectors_sha256": stored_vectors_sha256,
        "passage_ids": passage_ids,
    }
    validate_manifest(manifest)
    return manifest


def validate_manifest(document: Any) -> None:
    """Validate the closed manifest contract; raise a fixed-code error."""

    if not isinstance(document, dict) or set(document) != MANIFEST_KEYS:
        raise VectorStoreError("manifest_unknown_keys")
    if document["schema_version"] != STORE_SCHEMA_VERSION:
        raise VectorStoreError("manifest_schema_version")
    if document["collection"] != COLLECTION_NAME or document["distance"] != DISTANCE:
        raise VectorStoreError("manifest_invalid")
    if not is_non_blank_string(document["chromadb_version"]):
        raise VectorStoreError("manifest_invalid")
    model = document["model"]
    if not isinstance(model, dict) or set(model) != MODEL_KEYS:
        raise VectorStoreError("manifest_invalid")
    dimension = model["embedding_dimension"]
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise VectorStoreError("manifest_invalid")
    inputs = document["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != INPUT_KEYS:
        raise VectorStoreError("manifest_invalid")
    for key in ("catalog_sha256", "passages_sha256", "documents_sha256"):
        _check_digest(inputs[key])
    _check_digest(document["source_index_sha256"])
    _check_digest(document["vectors_sha256"])
    if not is_non_blank_string(inputs["as_of"]):
        raise VectorStoreError("manifest_invalid")
    campaign = inputs["active_campaign"]
    if campaign is not None and not is_non_blank_string(campaign):
        raise VectorStoreError("manifest_invalid")
    count = inputs["passage_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise VectorStoreError("manifest_invalid")
    passage_ids = document["passage_ids"]
    if not isinstance(passage_ids, list) or len(passage_ids) != count:
        raise VectorStoreError("manifest_count_mismatch")
    previous: Optional[str] = None
    for passage_id in passage_ids:
        if not is_non_blank_string(passage_id):
            raise VectorStoreError("manifest_invalid")
        if previous is not None and passage_id <= previous:
            raise VectorStoreError("manifest_unsorted_or_duplicate")
        previous = passage_id


def read_manifest(store_dir: Path) -> Dict[str, Any]:
    """Read and validate the manifest of ``store_dir``."""

    try:
        text = (Path(store_dir) / MANIFEST_NAME).read_text(encoding="utf-8")
    except OSError as error:
        raise VectorStoreError("manifest_unreadable") from error
    try:
        document = json.loads(text)
    except ValueError as error:
        raise VectorStoreError("manifest_malformed") from error
    validate_manifest(document)
    return document


def manifest_status(
    manifest: Mapping[str, Any],
    spec: EmbeddingModelSpec,
    active_campaign: Optional[str],
    documents: Sequence[Tuple[str, str]],
) -> StoreStatus:
    """Compare a validated manifest with the current pin, campaign, and documents."""

    reasons: List[str] = []
    model = manifest["model"]
    expected = spec.index_metadata()
    for key, reason in (
        ("model_id", "model_id_changed"),
        ("model_revision", "model_revision_changed"),
        ("config_sha256", "model_config_changed"),
        ("embedding_dimension", "dimension_changed"),
        ("pooling", "pooling_changed"),
        ("normalize", "normalization_changed"),
        ("dtype", "dtype_changed"),
    ):
        if model[key] != expected[key]:
            reasons.append(reason)
    inputs = manifest["inputs"]
    if inputs["active_campaign"] != active_campaign:
        reasons.append("active_campaign_changed")
    if inputs["documents_sha256"] != documents_sha256(documents):
        reasons.append("documents_changed")
    if reasons:
        return StoreStatus(STORE_STALE, tuple(reasons))
    return StoreStatus(STORE_UP_TO_DATE, ())


def store_status(
    store_dir: Path,
    spec: EmbeddingModelSpec,
    active_campaign: Optional[str],
    documents: Sequence[Tuple[str, str]],
) -> StoreStatus:
    """Report ``missing``/``invalid``/``stale``/``up_to_date`` from the manifest.

    This needs no ``chromadb`` runtime; :meth:`ChromaPassageStore.open` performs
    the additional collection-level integrity checks.
    """

    target = Path(store_dir)
    if not (target / MANIFEST_NAME).exists():
        return StoreStatus(STORE_MISSING, ("store_missing",))
    try:
        manifest = read_manifest(target)
    except VectorStoreError as error:
        return StoreStatus(STORE_INVALID, (error_code(error),))
    return manifest_status(manifest, spec, active_campaign, documents)


class ChromaPassageStore:
    """An opened, integrity-checked Chroma collection plus its manifest."""

    def __init__(self, collection: Any, manifest: Mapping[str, Any]) -> None:
        self._collection = collection
        self._manifest = dict(manifest)
        self._dimension = int(manifest["model"]["embedding_dimension"])
        self._count = int(manifest["inputs"]["passage_count"])

    @property
    def manifest(self) -> Dict[str, Any]:
        return dict(self._manifest)

    @property
    def passage_count(self) -> int:
        return self._count

    @classmethod
    def open(cls, store_dir: Path, spec: EmbeddingModelSpec) -> "ChromaPassageStore":
        """Open ``store_dir`` and verify its collection against the manifest.

        Refuses a store whose model pin differs from ``spec`` (it could never
        compare against this model's query vectors), whose collection is missing,
        or whose ids or vectors differ from what the manifest recorded.
        """

        target = Path(store_dir)
        if _inside_directory(target, KNOWLEDGE_ROOT):
            raise VectorStoreError("unsafe_store_path")
        if not (target / MANIFEST_NAME).exists():
            raise VectorStoreError("store_missing")
        manifest = read_manifest(target)
        if manifest["model"] != spec.index_metadata():
            raise VectorStoreError("store_model_mismatch")
        chromadb = _import_chromadb()
        try:
            client = _client(chromadb, target)
            collection = client.get_collection(name=COLLECTION_NAME)
            stored = collection.get(include=["embeddings"])
        except VectorStoreError:
            raise
        except Exception as error:  # chromadb raises many unrelated types
            raise VectorStoreError("store_open_failed") from error
        vectors = _vectors_by_id(stored)
        if sorted(vectors) != manifest["passage_ids"]:
            raise VectorStoreError("store_ids_mismatch")
        if vectors_sha256(vectors) != manifest["vectors_sha256"]:
            raise VectorStoreError("store_vectors_mismatch")
        return cls(collection, manifest)

    def query(self, vector: Sequence[float], depth: int) -> Tuple[VectorMatch, ...]:
        """Return up to ``depth`` passages by descending cosine similarity.

        Results are re-sorted by ``(-similarity, passage_id)`` so equal
        similarities never reorder between runs.
        """

        if depth < 1 or self._count == 0:
            return ()
        values = [float(value) for value in vector]
        if len(values) != self._dimension:
            raise VectorStoreError("query_dimension_mismatch")
        if not all(math.isfinite(value) for value in values):
            raise VectorStoreError("query_not_finite")
        try:
            result = self._collection.query(
                query_embeddings=[values],
                n_results=min(depth, self._count),
                include=["distances"],
            )
            ids = list(result["ids"][0])
            distances = [float(value) for value in result["distances"][0]]
        except Exception as error:  # chromadb raises many unrelated types
            raise VectorStoreError("store_query_failed") from error
        if len(ids) != len(distances):
            raise VectorStoreError("store_query_failed")
        pairs = sorted(
            ((passage_id, 1.0 - distance) for passage_id, distance in zip(ids, distances)),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return tuple(
            VectorMatch(passage_id=passage_id, similarity=similarity, rank=position + 1)
            for position, (passage_id, similarity) in enumerate(pairs)
            if math.isfinite(similarity)
        )


def write_store(
    store_dir: Path,
    index: PassageEmbeddingIndex,
    spec: EmbeddingModelSpec,
    inputs: IndexInputs,
    documents: Sequence[Tuple[str, str]],
    source_index_sha256: str,
) -> Dict[str, Any]:
    """Build a fresh store from ``index`` and atomically replace ``store_dir``.

    The new collection is written into a sibling staging directory, read back,
    and checked before its manifest is written; only then is it swapped into
    place. An existing ``store_dir`` is replaced only when it is itself a store
    (it carries a manifest), so an arbitrary operator directory is never removed.
    Returns the written manifest.
    """

    target = Path(store_dir)
    if _inside_directory(target, KNOWLEDGE_ROOT):
        raise VectorStoreError("unsafe_store_path")
    if target.exists() and not (target.is_dir() and (target / MANIFEST_NAME).is_file()):
        raise VectorStoreError("store_path_not_a_store")
    if index.dimension != spec.embedding_dimension:
        raise VectorStoreError("store_model_mismatch")
    chromadb = _import_chromadb()

    staging = target.parent / ".{}.staging-{}".format(target.name, uuid.uuid4().hex)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        manifest = _populate(chromadb, staging, index, spec, inputs, documents, source_index_sha256)
        _release_clients(chromadb)
        _swap_into_place(staging, target)
    except VectorStoreError:
        _release_clients(chromadb)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except OSError as error:
        _release_clients(chromadb)
        shutil.rmtree(staging, ignore_errors=True)
        raise VectorStoreError("store_write_failed") from error
    return manifest


def error_code(error: Exception) -> str:
    text = str(error)
    return text.split(":", 1)[0] if text else "vector_store_error"


def _populate(
    chromadb: Any,
    staging: Path,
    index: PassageEmbeddingIndex,
    spec: EmbeddingModelSpec,
    inputs: IndexInputs,
    documents: Sequence[Tuple[str, str]],
    source_index_sha256: str,
) -> Dict[str, Any]:
    passage_ids = list(index.passage_ids)
    if passage_ids != sorted(passage_id for passage_id, _ in documents):
        raise VectorStoreError("store_documents_mismatch")
    try:
        client = _client(chromadb, staging)
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
            metadata={"hnsw:space": DISTANCE, "manijero_schema": STORE_SCHEMA_VERSION},
        )
        if passage_ids:
            collection.add(
                ids=passage_ids,
                embeddings=[list(index.vector(passage_id) or ()) for passage_id in passage_ids],
            )
        stored = collection.get(include=["embeddings"])
    except Exception as error:  # chromadb raises many unrelated types
        raise VectorStoreError("store_write_failed") from error
    vectors = _vectors_by_id(stored)
    if sorted(vectors) != passage_ids:
        raise VectorStoreError("store_ids_mismatch")
    manifest = build_manifest(
        index, spec, inputs, documents, source_index_sha256, vectors_sha256(vectors)
    )
    text = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (staging / MANIFEST_NAME).write_text(text, encoding="utf-8")
    return manifest


def _swap_into_place(staging: Path, target: Path) -> None:
    if not target.exists():
        os.rename(staging, target)
        return
    previous = target.parent / ".{}.previous-{}".format(target.name, uuid.uuid4().hex)
    os.rename(target, previous)
    try:
        os.rename(staging, target)
    except OSError:
        os.rename(previous, target)
        raise
    shutil.rmtree(previous, ignore_errors=True)


def _vectors_by_id(stored: Any) -> Dict[str, Tuple[float, ...]]:
    try:
        ids = list(stored["ids"])
        embeddings = stored["embeddings"]
        embeddings = [] if embeddings is None else list(embeddings)
    except (KeyError, TypeError) as error:
        raise VectorStoreError("store_read_failed") from error
    if len(ids) != len(embeddings):
        raise VectorStoreError("store_read_failed")
    vectors: Dict[str, Tuple[float, ...]] = {}
    for passage_id, embedding in zip(ids, embeddings):
        if passage_id in vectors:
            raise VectorStoreError("store_ids_mismatch")
        vectors[str(passage_id)] = tuple(float(value) for value in embedding)
    return vectors


def _import_chromadb() -> Any:
    try:
        import chromadb  # type: ignore[import-not-found]
    except Exception as error:  # ImportError or a broken native extension
        raise VectorStoreUnavailable("vector_runtime_unavailable") from error
    return chromadb


def _client(chromadb: Any, path: Path) -> Any:
    from chromadb.config import Settings  # type: ignore[import-not-found]

    return chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )


def _release_clients(chromadb: Any) -> None:
    """Drop Chroma's per-path client cache so a directory can be renamed."""

    try:
        from chromadb.api.client import SharedSystemClient  # type: ignore[import-not-found]

        SharedSystemClient.clear_system_cache()
    except Exception:
        return


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _check_digest(value: Any) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise VectorStoreError("manifest_invalid")
