"""Index reviewed structured chunks for BM25 and vector search, derived from the catalog.

This module turns reviewed ``legal-chunk-set-v1`` artifacts (written by
``app/legal_structure_chunker.py``) into one derived, hash-verified directory outside
``knowledge/``::

    <index>/source_catalog.json            exact bytes of the reviewed catalog
    <index>/structured-passages.json       passage-set-v1, one passage per chunk
    <index>/bm25-index.json                release_gates.bm25_fingerprint
    <index>/embedding-index.json           optional (passage-embedding-index-v1)
    <index>/vector-store/                  optional (chroma-passage-store-v1)
    <index>/structured-index-manifest.json written last (structured-chunk-index-v1)

Boundaries:

- Review gate (document level, no per-chunk review): a chunk set's ``source_sha256`` must
  equal the ``content_sha256`` of an ``approved`` catalog entry with a named
  ``reviewed_by``, and the catalog must be bound to human-approval evidence through the
  release builder's ``approval_from_options``. Any malformed, unreviewed, unstructured,
  or failed document refuses the whole build and leaves an existing index untouched.
- Validity is copied, never inferred: passages carry no ``critical``, ``applicability``,
  or ``official_deadline``; the unchanged ``Retriever`` reads them from the catalog.
- The answer service reads this index only through :func:`structured_corpus_from_environment`,
  and only when ``MANIJERO_STRUCTURED_INDEX=on`` in ``MANIJERO_ENVIRONMENT=local`` with
  ``MANIJERO_DEPLOYMENT_PROFILE=development``, or in ``MANIJERO_ENVIRONMENT=qa``. Every other
  or unset environment ignores the flag. Release gates and the review merge never read it.
- Import is stdlib plus ``app.*`` only. ``release_gates``, ``embedding_index``,
  ``embeddings``, and ``vector_store`` are imported lazily inside the build; the optional
  ``chromadb`` and ``torch`` runtimes are never imported by the request path.

Errors and log reasons are fixed codes; no chunk text, question, or reviewer name appears.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from app.knowledge_release import (
    BASELINE_APPROVAL_KEYS,
    DEFAULT_EMBEDDING_CONFIG,
    MERGE_APPROVAL_KEYS,
    VECTOR_KEYS,
    VECTOR_MODEL_KEYS,
    ReleaseError,
    approval_from_options,
    document_bytes,
    sha256_bytes,
)
from app.legal_structure_chunker import (
    CHUNK_INPUT_KEYS,
    CHUNK_KEYS,
    CHUNK_MANIFEST_VERSION,
    CHUNK_SET_OPTIONAL_KEYS,
    CHUNK_SET_REQUIRED_KEYS,
    CHUNK_SET_VERSION,
    CHUNKER,
    DOCUMENT_KEYS,
    RUN_MANIFEST_NAME,
    RUN_MANIFEST_REQUIRED_KEYS,
    STATUSES,
    SUMMARY_KEYS,
    catalog_block,
    catalog_index,
)
from app.retrieval import PASSAGE_SET_SCHEMA_VERSION
from app.source_catalog import validate_catalog

INDEX_VERSION = "structured-chunk-index-v1"
BUILDER = "manijero-structured-chunk-index-v1"

CATALOG_FILE = "source_catalog.json"
PASSAGES_FILE = "structured-passages.json"
BM25_FILE = "bm25-index.json"
EMBEDDING_FILE = "embedding-index.json"
VECTOR_DIR = "vector-store"
VECTOR_MANIFEST_FILE = "manijero-vector-store.json"
MANIFEST_NAME = "structured-index-manifest.json"

MAX_CHUNK_SETS = 1000
MAX_CHUNKS = 20000

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2

STATE_UP_TO_DATE = "up_to_date"
STATE_STALE = "stale"
STATE_INVALID = "invalid"

FLAG_ENV = "MANIJERO_STRUCTURED_INDEX"
DIR_ENV = "MANIJERO_STRUCTURED_INDEX_DIR"
ENVIRONMENT_ENV = "MANIJERO_ENVIRONMENT"
PROFILE_ENV = "MANIJERO_DEPLOYMENT_PROFILE"
KNOWLEDGE_RELEASE_ROOT_ENV = "MANIJERO_KNOWLEDGE_RELEASE_ROOT"

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"
SCHEMA_PATH = KNOWLEDGE_ROOT / "structured-chunk-index.schema.json"

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REVISION_PATTERN = re.compile(r"^[a-f0-9]{40}$")
CAMPAIGN_PATTERN = re.compile(r"^\d{4}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARTIFACT_PATTERN = re.compile(r"^([a-f0-9]{64})/chunks-([a-f0-9]{64})\.json$")

MANIFEST_KEYS = frozenset(
    {"schema_version", "builder", "inputs", "approval", "files", "counts", "vectors"}
)
INPUT_KEYS = frozenset(
    {"catalog_sha256", "chunk_manifest_sha256", "chunk_sets", "as_of", "active_campaign"}
)
CHUNK_SET_ENTRY_KEYS = frozenset(
    {"candidate_id", "source_id", "source_sha256", "chunk_set_sha256", "chunk_count"}
)
COUNT_KEYS = frozenset({"documents", "chunks", "indexed_passages"})
FILE_ENTRY_KEYS = frozenset({"sha256", "bytes"})
BASE_FILES = (CATALOG_FILE, PASSAGES_FILE, BM25_FILE)


class StructuredIndexError(Exception):
    """A build or verification failure with a fixed code and a CLI exit code."""

    def __init__(self, code: str, exit_code: int = EXIT_REFUSED) -> None:
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class ChunkSetEntry:
    """One validated, reviewed chunk set and the manifest facts that bind it."""

    candidate_id: str
    source_id: str
    source_sha256: str
    chunk_set_sha256: str
    chunk_count: int
    document: Mapping[str, Any]


@dataclass(frozen=True)
class VectorOptions:
    """Optional vector step. The loaders are injected only by tests."""

    artifact: Path
    config: Path = DEFAULT_EMBEDDING_CONFIG
    load_embedder: Optional[Callable[[Any, Path], Any]] = None
    write_store: Optional[Callable[..., Dict[str, Any]]] = None


@dataclass(frozen=True)
class BuildReport:
    status: str  # "built" or "unchanged"
    documents: int
    chunks: int
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class VerifiedIndex:
    manifest: Mapping[str, Any]
    catalog: Any
    passages: Any


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_int(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _invalid_chunk_set() -> StructuredIndexError:
    return StructuredIndexError("invalid_chunk_set")


def _inside(path: Path, directory: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(directory)))
    except ValueError:
        return False
    return True


def _read_json(path: Path, error: StructuredIndexError) -> Tuple[bytes, Any]:
    try:
        payload = path.read_bytes()
        return payload, json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as cause:
        raise error from cause


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _entry(payload: bytes) -> Dict[str, Any]:
    return {"sha256": sha256_bytes(payload), "bytes": len(payload)}


# ---------------------------------------------------------------------------------------------
# Strict chunk-manifest and chunk-set reader
# ---------------------------------------------------------------------------------------------


def _check_chunk(chunk: Any, input_block: Mapping[str, Any]) -> None:
    if not isinstance(chunk, dict) or set(chunk) != CHUNK_KEYS:
        raise _invalid_chunk_set()
    text = chunk["text"]
    path = chunk["heading_path"]
    if (
        not _non_blank(chunk["id"])
        or chunk["candidate_id"] != input_block["candidate_id"]
        or chunk["source_sha256"] != input_block["source_sha256"]
        or chunk["markdown_sha256"] != input_block["markdown_sha256"]
        or not isinstance(path, list)
        or not all(_non_blank(item) for item in path)
        or not _non_blank(chunk["location"])
        or not _is_int(chunk["page_start"], 1)
        or not _is_int(chunk["page_end"], 1)
        or chunk["page_start"] > chunk["page_end"]
        or not _non_blank(text)
        or chunk["character_count"] != len(text)
    ):
        raise _invalid_chunk_set()


def _check_chunk_set(document: Any, candidate_id: str, source_sha256: str, chunk_count: int) -> None:
    """Strict ``legal-chunk-set-v1`` reader; a failure is always ``invalid_chunk_set``."""

    if not isinstance(document, dict):
        raise _invalid_chunk_set()
    keys = set(document)
    if not CHUNK_SET_REQUIRED_KEYS <= keys <= CHUNK_SET_REQUIRED_KEYS | CHUNK_SET_OPTIONAL_KEYS:
        raise _invalid_chunk_set()
    input_block = document["input"]
    chunks = document["chunks"]
    warnings = document["warnings"]
    if (
        document["schema_version"] != CHUNK_SET_VERSION
        or document["chunker"] != CHUNKER
        or not isinstance(input_block, dict)
        or set(input_block) != CHUNK_INPUT_KEYS
        or input_block["candidate_id"] != candidate_id
        or input_block["source_sha256"] != source_sha256
        or not _is_hash(input_block["markdown_sha256"])
        or not isinstance(input_block["title"], str)
        or document["validity_status"] not in ("known", "unknown")
        or not isinstance(chunks, list)
        or not _is_int(document["chunk_count"])
        or document["chunk_count"] != len(chunks)
        or len(chunks) != chunk_count
        or not isinstance(warnings, list)
        or not all(isinstance(item, str) for item in warnings)
    ):
        raise _invalid_chunk_set()
    for chunk in chunks:
        _check_chunk(chunk, input_block)


def _check_run_manifest(document: Any) -> List[Mapping[str, Any]]:
    if (
        not isinstance(document, dict)
        or set(document) != RUN_MANIFEST_REQUIRED_KEYS
        or document["schema_version"] != CHUNK_MANIFEST_VERSION
        or document["chunker"] != CHUNKER
        or not isinstance(document["documents"], list)
        or not isinstance(document["summary"], dict)
        or set(document["summary"]) != SUMMARY_KEYS
    ):
        raise _invalid_chunk_set()
    entries = document["documents"]
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != DOCUMENT_KEYS
            or entry["status"] not in STATUSES
            or not _is_hash(entry["candidate_id"])
        ):
            raise _invalid_chunk_set()
    return entries


def _read_chunk_sets(chunks_root: Path) -> Tuple[str, List[ChunkSetEntry]]:
    """Read the run manifest and every chunk set; return ``(manifest_sha256, entries)``.

    Every listed document must be ``chunked`` with known validity. Anything else raises a
    fixed refusal and the caller writes nothing.
    """

    payload, document = _read_json(chunks_root / RUN_MANIFEST_NAME, _invalid_chunk_set())
    entries = _check_run_manifest(document)
    if len(entries) > MAX_CHUNK_SETS:
        raise StructuredIndexError("chunk_set_limit_exceeded", EXIT_USAGE)
    chunk_total = sum(
        entry["chunk_count"] for entry in entries if _is_int(entry["chunk_count"])
    )
    if chunk_total > MAX_CHUNKS:
        raise StructuredIndexError("chunk_limit_exceeded", EXIT_USAGE)
    for entry in entries:
        if entry["status"] != "chunked":
            raise StructuredIndexError("unreviewed_chunk_set")

    sets: List[ChunkSetEntry] = []
    for entry in entries:
        artifact = entry["artifact"]
        match = ARTIFACT_PATTERN.fullmatch(artifact) if isinstance(artifact, str) else None
        if (
            match is None
            or match.group(1) != entry["candidate_id"]
            or match.group(2) != entry["source_sha256"]
            or not _is_hash(entry["chunk_set_sha256"])
            or not _is_int(entry["chunk_count"], 1)
        ):
            raise _invalid_chunk_set()
        raw, chunk_set = _read_json(chunks_root / artifact, _invalid_chunk_set())
        if sha256_bytes(raw) != entry["chunk_set_sha256"]:
            raise _invalid_chunk_set()
        _check_chunk_set(chunk_set, entry["candidate_id"], entry["source_sha256"], entry["chunk_count"])
        if chunk_set["validity_status"] != "known":
            raise StructuredIndexError("unreviewed_chunk_set")
        block = chunk_set.get("catalog")
        if not isinstance(block, dict) or not _non_blank(block.get("source_id")):
            raise _invalid_chunk_set()
        sets.append(
            ChunkSetEntry(
                candidate_id=entry["candidate_id"],
                source_id=block["source_id"],
                source_sha256=entry["source_sha256"],
                chunk_set_sha256=entry["chunk_set_sha256"],
                chunk_count=entry["chunk_count"],
                document=chunk_set,
            )
        )
    return sha256_bytes(payload), sets


# ---------------------------------------------------------------------------------------------
# Review gate and passage mapping
# ---------------------------------------------------------------------------------------------


def _load_reviewed_catalog(catalog_path: Path, as_of: date) -> Tuple[bytes, Any]:
    try:
        payload = Path(catalog_path).read_bytes()
    except OSError as error:
        raise StructuredIndexError("missing_catalog", EXIT_USAGE) from error
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise StructuredIndexError("invalid_catalog") from error
    if not validate_catalog(document, as_of).ok:
        raise StructuredIndexError("invalid_catalog")
    return payload, document


def _gate(entry: ChunkSetEntry, index: Mapping[str, Mapping[str, Any]], catalog_sha256: str) -> None:
    """Join one chunk set to a currently approved, named-reviewer catalog entry."""

    source = index.get(entry.source_sha256)
    if source is None:
        raise StructuredIndexError("chunk_validity_mismatch")
    if source.get("review_status") != "approved" or not _non_blank(source.get("reviewed_by")):
        raise StructuredIndexError("unreviewed_chunk_set")
    block = entry.document["catalog"]
    if block != catalog_block(source, catalog_sha256):
        raise StructuredIndexError("chunk_validity_mismatch")
    id_pattern = re.compile(r"^{}-[0-9]{{4}}$".format(re.escape(source["id"])))
    if any(not id_pattern.fullmatch(chunk["id"]) for chunk in entry.document["chunks"]):
        raise _invalid_chunk_set()


def _page_suffix(chunk: Mapping[str, Any]) -> str:
    start, end = chunk["page_start"], chunk["page_end"]
    if start == end:
        return ", pág. {}".format(start)
    return ", págs. {}-{}".format(start, end)


def _passages_of(entries: Sequence[ChunkSetEntry]) -> Dict[str, Any]:
    """One passage per chunk: id, source_id, verbatim text, and an honest location."""

    seen: Dict[str, None] = {}
    passages: List[Dict[str, Any]] = []
    for entry in entries:
        for chunk in entry.document["chunks"]:
            if chunk["id"] in seen:
                raise StructuredIndexError("duplicate_chunk_id")
            seen[chunk["id"]] = None
            passages.append(
                {
                    "id": chunk["id"],
                    "source_id": entry.source_id,
                    "location": chunk["location"] + _page_suffix(chunk),
                    "text": chunk["text"],
                }
            )
    if not passages:
        raise StructuredIndexError("no_reviewed_chunks")
    passages.sort(key=lambda passage: passage["id"])
    return {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": passages}


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------


def _check_output(output: Path, chunks_root: Path) -> None:
    if _inside(output, KNOWLEDGE_ROOT) or _inside(KNOWLEDGE_ROOT, output):
        raise StructuredIndexError("unsafe_output_root", EXIT_USAGE)
    if _inside(output, chunks_root) or _inside(chunks_root, output):
        raise StructuredIndexError("unsafe_output_root", EXIT_USAGE)
    if os.path.lexists(output):
        if output.is_symlink() or not output.is_dir():
            raise StructuredIndexError("output_not_an_index", EXIT_USAGE)
        if any(output.iterdir()) and not (output / MANIFEST_NAME).is_file():
            raise StructuredIndexError("output_not_an_index", EXIT_USAGE)


def _vector_precheck(options: VectorOptions) -> Any:
    from app.embeddings import EmbeddingError, load_model_spec

    try:
        spec = load_model_spec(options.config)
    except (EmbeddingError, OSError) as error:
        raise StructuredIndexError("embedding_config_invalid", EXIT_USAGE) from error
    if options.write_store is None:
        try:
            import chromadb  # noqa: F401  (optional runtime; presence check only)
        except Exception as error:  # ImportError or a broken native extension
            raise StructuredIndexError("vector_runtime_unavailable", EXIT_USAGE) from error
    return spec


def _build_vectors(
    options: VectorOptions,
    spec: Any,
    retriever: Any,
    inputs: Any,
    staging: Path,
) -> Tuple[Dict[str, Any], bytes]:
    """Embed the admitted chunks and load them into Chroma with the existing writers."""

    from app import vector_store
    from app.embedding_index import PassageEmbeddingIndex, build_index_document
    from app.embeddings import EmbeddingError, LocalBgeM3Embedder

    documents = retriever.indexed_documents()
    load_embedder = options.load_embedder or (
        lambda model_spec, artifact: LocalBgeM3Embedder.load(model_spec, artifact)
    )
    write_store = options.write_store or vector_store.write_store
    try:
        embedder = load_embedder(spec, Path(options.artifact))
        index = PassageEmbeddingIndex.build(documents, embedder)
        document = build_index_document(index, spec, inputs)
        index_bytes = (
            json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        store_manifest = write_store(
            staging / VECTOR_DIR, index, spec, inputs, documents, sha256_bytes(index_bytes)
        )
        store_manifest_bytes = (staging / VECTOR_DIR / VECTOR_MANIFEST_FILE).read_bytes()
    except (EmbeddingError, vector_store.VectorStoreError) as error:
        text = str(error)
        raise StructuredIndexError(
            (text.split(":", 1)[0] if text else "embedding_failed"), EXIT_USAGE
        ) from error
    except OSError as error:
        raise StructuredIndexError("store_write_failed", EXIT_USAGE) from error
    vectors = {
        "model": spec.index_metadata(),
        "embedding_index_sha256": sha256_bytes(index_bytes),
        "store_manifest_sha256": sha256_bytes(store_manifest_bytes),
        "documents_sha256": store_manifest["inputs"]["documents_sha256"],
        "vectors_sha256": store_manifest["vectors_sha256"],
        "chromadb_version": store_manifest["chromadb_version"],
    }
    return vectors, index_bytes


def _swap_into_place(staging: Path, target: Path) -> None:
    if not os.path.lexists(target):
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


def build_index(
    *,
    chunks_root: Path,
    catalog_path: Path,
    output_root: Path,
    as_of: date,
    active_campaign: str,
    merge_record: Optional[Path] = None,
    passages_path: Optional[Path] = None,
    reviewed_baseline_revision: Optional[str] = None,
    vectors: Optional[VectorOptions] = None,
) -> BuildReport:
    """Rebuild the structured index; raise :class:`StructuredIndexError` writing nothing."""

    chunks_root = Path(chunks_root)
    output_root = Path(output_root)
    if not CAMPAIGN_PATTERN.fullmatch(active_campaign or ""):
        raise StructuredIndexError("active_campaign_invalid", EXIT_USAGE)
    if not chunks_root.is_dir():
        raise StructuredIndexError("missing_chunks_root", EXIT_USAGE)
    _check_output(output_root, chunks_root)
    if merge_record is not None and passages_path is None:
        raise StructuredIndexError("passages_required", EXIT_USAGE)
    passages_sha256 = ""
    if passages_path is not None:
        try:
            passages_sha256 = sha256_bytes(Path(passages_path).read_bytes())
        except OSError as error:
            raise StructuredIndexError("passages_unreadable", EXIT_USAGE) from error
    spec = _vector_precheck(vectors) if vectors is not None else None

    catalog_bytes, catalog = _load_reviewed_catalog(catalog_path, as_of)
    catalog_sha256 = sha256_bytes(catalog_bytes)
    chunk_manifest_sha256, entries = _read_chunk_sets(chunks_root)

    index = catalog_index(catalog)
    for entry in entries:
        _gate(entry, index, catalog_sha256)
    try:
        approval = approval_from_options(
            merge_record, reviewed_baseline_revision, catalog_sha256, passages_sha256
        )
    except ReleaseError as error:
        raise StructuredIndexError(error.code) from error

    passage_set = _passages_of(entries)
    passages_bytes = document_bytes(passage_set)
    retriever = _admitted_retriever(catalog, passage_set, as_of, active_campaign)

    from app import corpus_security, release_gates

    if corpus_security.scan_canonical(catalog, passage_set):
        raise StructuredIndexError("corpus_security")
    bm25_bytes = document_bytes(
        release_gates.bm25_fingerprint(catalog, passage_set, as_of, active_campaign)
    )

    staging = output_root.parent / ".{}.staging-{}".format(output_root.name, uuid.uuid4().hex)
    try:
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        files = {CATALOG_FILE: catalog_bytes, PASSAGES_FILE: passages_bytes, BM25_FILE: bm25_bytes}
        vector_entry: Optional[Dict[str, Any]] = None
        if vectors is not None:
            from app.embedding_index import IndexInputs

            inputs = IndexInputs(
                catalog_sha256=catalog_sha256,
                passages_sha256=sha256_bytes(passages_bytes),
                as_of=as_of.isoformat(),
                active_campaign=active_campaign,
            )
            vector_entry, index_bytes = _build_vectors(vectors, spec, retriever, inputs, staging)
            files[EMBEDDING_FILE] = index_bytes
        for name, payload in files.items():
            _write_new(staging / name, payload)
        chunk_total = len(passage_set["passages"])
        manifest = {
            "schema_version": INDEX_VERSION,
            "builder": BUILDER,
            "inputs": {
                "catalog_sha256": catalog_sha256,
                "chunk_manifest_sha256": chunk_manifest_sha256,
                "chunk_sets": sorted(
                    (
                        {
                            "candidate_id": entry.candidate_id,
                            "source_id": entry.source_id,
                            "source_sha256": entry.source_sha256,
                            "chunk_set_sha256": entry.chunk_set_sha256,
                            "chunk_count": entry.chunk_count,
                        }
                        for entry in entries
                    ),
                    key=lambda item: (item["candidate_id"], item["source_sha256"]),
                ),
                "as_of": as_of.isoformat(),
                "active_campaign": active_campaign,
            },
            "approval": approval,
            "files": {name: _entry(payload) for name, payload in sorted(files.items())},
            "counts": {
                "documents": len(entries),
                "chunks": chunk_total,
                "indexed_passages": len(retriever.indexed_documents()),
            },
            "vectors": vector_entry,
        }
        manifest_bytes = document_bytes(manifest)
        report_status = "built"
        if _is_unchanged(output_root, manifest_bytes):
            shutil.rmtree(staging, ignore_errors=True)
            report_status = "unchanged"
        else:
            _write_new(staging / MANIFEST_NAME, manifest_bytes)
            _swap_into_place(staging, output_root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return BuildReport(report_status, len(entries), chunk_total, manifest)


def _admitted_retriever(catalog: Any, passage_set: Any, as_of: date, campaign: str) -> Any:
    from app.retrieval import (
        CatalogRejectedError,
        PassageSetError,
        Retriever,
    )

    try:
        retriever = Retriever.from_documents(catalog, passage_set, as_of, active_campaign=campaign)
    except (CatalogRejectedError, PassageSetError) as error:
        raise _invalid_chunk_set() from error
    if not retriever.indexed_documents():
        raise StructuredIndexError("no_reviewed_chunks")
    return retriever


def _is_unchanged(output_root: Path, manifest_bytes: bytes) -> bool:
    try:
        if (output_root / MANIFEST_NAME).read_bytes() != manifest_bytes:
            return False
        verify_index(output_root)
    except (OSError, StructuredIndexError):
        return False
    return True


# ---------------------------------------------------------------------------------------------
# Verify and status
# ---------------------------------------------------------------------------------------------


def _invalid() -> StructuredIndexError:
    return StructuredIndexError("structured_index_invalid")


def _check_approval(approval: Any) -> bool:
    if not isinstance(approval, dict):
        return False
    if approval.get("kind") == "merge_record":
        return (
            set(approval) == MERGE_APPROVAL_KEYS
            and _non_blank(approval["package_id"])
            and isinstance(approval["approved_on"], str)
            and DATE_PATTERN.fullmatch(approval["approved_on"]) is not None
            and _is_hash(approval["merge_record_sha256"])
        )
    if approval.get("kind") == "reviewed_git_baseline":
        return (
            set(approval) == BASELINE_APPROVAL_KEYS
            and isinstance(approval["revision"], str)
            and REVISION_PATTERN.fullmatch(approval["revision"]) is not None
        )
    return False


def _check_vectors(vectors: Any) -> bool:
    if vectors is None:
        return True
    return (
        isinstance(vectors, dict)
        and set(vectors) == VECTOR_KEYS
        and isinstance(vectors["model"], dict)
        and set(vectors["model"]) == VECTOR_MODEL_KEYS
        and all(
            _is_hash(vectors[key])
            for key in (
                "embedding_index_sha256",
                "store_manifest_sha256",
                "documents_sha256",
                "vectors_sha256",
            )
        )
        and _non_blank(vectors["chromadb_version"])
    )


def validate_manifest(document: Any) -> Mapping[str, Any]:
    """Closed manifest contract; raises ``structured_index_invalid``."""

    if not isinstance(document, dict) or set(document) != MANIFEST_KEYS:
        raise _invalid()
    inputs, counts, files = document["inputs"], document["counts"], document["files"]
    if (
        document["schema_version"] != INDEX_VERSION
        or document["builder"] != BUILDER
        or not isinstance(inputs, dict)
        or set(inputs) != INPUT_KEYS
        or not _is_hash(inputs["catalog_sha256"])
        or not _is_hash(inputs["chunk_manifest_sha256"])
        or not isinstance(inputs["as_of"], str)
        or DATE_PATTERN.fullmatch(inputs["as_of"]) is None
        or not isinstance(inputs["active_campaign"], str)
        or CAMPAIGN_PATTERN.fullmatch(inputs["active_campaign"]) is None
        or not isinstance(inputs["chunk_sets"], list)
        or not _check_approval(document["approval"])
        or not isinstance(counts, dict)
        or set(counts) != COUNT_KEYS
        or not all(_is_int(value) for value in counts.values())
        or not isinstance(files, dict)
        or not _check_vectors(document["vectors"])
    ):
        raise _invalid()
    for item in inputs["chunk_sets"]:
        if (
            not isinstance(item, dict)
            or set(item) != CHUNK_SET_ENTRY_KEYS
            or not _is_hash(item["candidate_id"])
            or not _non_blank(item["source_id"])
            or not _is_hash(item["source_sha256"])
            or not _is_hash(item["chunk_set_sha256"])
            or not _is_int(item["chunk_count"])
        ):
            raise _invalid()
    expected = set(BASE_FILES) | ({EMBEDDING_FILE} if document["vectors"] is not None else set())
    if set(files) != expected:
        raise _invalid()
    for entry in files.values():
        if (
            not isinstance(entry, dict)
            or set(entry) != FILE_ENTRY_KEYS
            or not _is_hash(entry["sha256"])
            or not _is_int(entry["bytes"])
        ):
            raise _invalid()
    if files[CATALOG_FILE]["sha256"] != inputs["catalog_sha256"]:
        raise _invalid()
    return document


def _verified_bytes(directory: Path, name: str, entry: Mapping[str, Any]) -> bytes:
    try:
        payload = (directory / name).read_bytes()
    except OSError as error:
        raise _invalid() from error
    if len(payload) != entry["bytes"] or sha256_bytes(payload) != entry["sha256"]:
        raise _invalid()
    return payload


def verify_index(index_dir: Path) -> VerifiedIndex:
    """Re-check the manifest shape and every recorded file hash; parse catalog and passages."""

    directory = Path(index_dir)
    try:
        document = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise _invalid() from error
    manifest = validate_manifest(document)
    payloads = {
        name: _verified_bytes(directory, name, entry) for name, entry in manifest["files"].items()
    }
    vectors = manifest["vectors"]
    if vectors is not None:
        try:
            store_manifest = (directory / VECTOR_DIR / VECTOR_MANIFEST_FILE).read_bytes()
        except OSError as error:
            raise _invalid() from error
        if (
            sha256_bytes(store_manifest) != vectors["store_manifest_sha256"]
            or sha256_bytes(payloads[EMBEDDING_FILE]) != vectors["embedding_index_sha256"]
        ):
            raise _invalid()
    try:
        catalog = json.loads(payloads[CATALOG_FILE].decode("utf-8"))
        passages = json.loads(payloads[PASSAGES_FILE].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise _invalid() from error
    return VerifiedIndex(manifest, catalog, passages)


def index_status(index_dir: Path, catalog_sha256: str) -> str:
    """``up_to_date``, ``stale`` (catalog changed), or ``invalid`` (missing or tampered)."""

    try:
        verified = verify_index(index_dir)
    except StructuredIndexError:
        return STATE_INVALID
    if verified.manifest["inputs"]["catalog_sha256"] != catalog_sha256:
        return STATE_STALE
    return STATE_UP_TO_DATE


# ---------------------------------------------------------------------------------------------
# Request loader (flag-gated, local development and QA only)
# ---------------------------------------------------------------------------------------------

_OUTCOME_LOCK = threading.Lock()
_LAST_OUTCOME: Optional[Tuple[str, str]] = None


def reset_outcome_log() -> None:
    """Forget the last logged outcome (tests)."""

    global _LAST_OUTCOME
    with _OUTCOME_LOCK:
        _LAST_OUTCOME = None


def _note(state: str, reason: str) -> None:
    """Write one ``structured_index`` record only when the outcome changes."""

    global _LAST_OUTCOME
    outcome = (state, reason)
    with _OUTCOME_LOCK:
        if outcome == _LAST_OUTCOME:
            return
        _LAST_OUTCOME = outcome
    from app.pilot_logging import operational_log

    operational_log("structured_index", state=state, reason=reason)


def environment_allows_flag(environ: Mapping[str, str]) -> bool:
    """Exact-match gate: local development, or QA. Anything else fails closed."""

    environment = environ.get(ENVIRONMENT_ENV)
    if environment == "qa":
        return True
    return environment == "local" and environ.get(PROFILE_ENV) == "development"


def _baseline_catalog_sha256(
    environ: Mapping[str, str], checkout_catalog_path: Optional[Path]
) -> str:
    """Hash of the catalog the service would otherwise serve."""

    release_root = environ.get(KNOWLEDGE_RELEASE_ROOT_ENV, "").strip()
    if release_root:
        from app.knowledge_release import load_published_corpus, read_manifest, release_dir

        try:
            _, _, release_id = load_published_corpus(Path(release_root))
            manifest = read_manifest(release_dir(Path(release_root), release_id))
        except (ReleaseError, OSError, ValueError) as error:
            raise StructuredIndexError("structured_index_stale") from error
        return str(manifest["files"]["source_catalog.json"]["sha256"])
    path = checkout_catalog_path or (KNOWLEDGE_ROOT / "source_catalog.json")
    try:
        return sha256_bytes(Path(path).read_bytes())
    except OSError as error:
        raise StructuredIndexError("structured_index_stale") from error


def structured_corpus_from_environment(
    environ: Mapping[str, str],
    *,
    checkout_catalog_path: Optional[Path] = None,
) -> Any:
    """Return the verified structured corpus, ``None`` to keep today's corpus, or a load error.

    ``None`` means the flag is off or ignored (with one logged reason when it was set).
    An effective flag over a missing, tampered, or stale index returns
    ``CorpusDocuments(load_error=True)``, which the route turns into the generic
    corpus-unavailable answer.
    """

    setting = environ.get(FLAG_ENV, "")
    if setting in ("", "off"):
        return None
    if setting != "on":
        _note("ignored", "structured_index_setting_invalid")
        return None
    if not environment_allows_flag(environ):
        _note("ignored", "structured_index_environment_refused")
        return None
    directory = environ.get(DIR_ENV, "").strip()
    if not directory or not Path(directory).is_dir():
        _note("ignored", "structured_index_not_configured")
        return None

    from app.ask_api import CorpusDocuments  # lazy: ask_api imports this module

    try:
        verified = verify_index(Path(directory))
        if verified.manifest["inputs"]["catalog_sha256"] != _baseline_catalog_sha256(
            environ, checkout_catalog_path
        ):
            raise StructuredIndexError("structured_index_stale")
    except StructuredIndexError as error:
        _note("refused", error.code)
        return CorpusDocuments(catalog=None, passages=None, load_error=True)
    _note("served", "ok")
    return CorpusDocuments(catalog=verified.catalog, passages=verified.passages)


# ---------------------------------------------------------------------------------------------
# Contract check (no jsonschema dependency)
# ---------------------------------------------------------------------------------------------


def check_contract(schema_path: Path = SCHEMA_PATH) -> List[str]:
    """Compare the committed schema with this module's constants; empty means they agree."""

    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return ["structured index schema is not readable JSON: {}".format(schema_path)]
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    if not isinstance(defs, dict):
        return ["structured index schema has no $defs object"]

    problems: List[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    def definition(name: str) -> Mapping[str, Any]:
        value = defs.get(name)
        return value if isinstance(value, dict) else {}

    manifest = definition("manifest")
    properties = manifest.get("properties", {})
    expect(set(manifest.get("required", ())) == MANIFEST_KEYS, "manifest requires different keys")
    expect(set(properties) == MANIFEST_KEYS, "manifest properties disagree with the module")
    expect((properties.get("schema_version") or {}).get("const") == INDEX_VERSION,
           "manifest schema_version constant differs")
    expect((properties.get("builder") or {}).get("const") == BUILDER, "manifest builder differs")
    expect(set(definition("inputs").get("required", ())) == INPUT_KEYS, "inputs require different keys")
    expect(set(definition("chunk_set_entry").get("required", ())) == CHUNK_SET_ENTRY_KEYS,
           "chunk_set_entry requires different keys")
    expect(set(definition("counts").get("required", ())) == COUNT_KEYS, "counts require different keys")
    expect(set(definition("file_entry").get("required", ())) == FILE_ENTRY_KEYS,
           "file_entry requires different keys")
    expect(set(definition("files").get("required", ())) == set(BASE_FILES),
           "files require different names")
    expect(set(definition("files").get("properties", {})) == set(BASE_FILES) | {EMBEDDING_FILE},
           "files properties disagree with the module")
    expect(set(definition("vectors").get("required", ())) == VECTOR_KEYS,
           "vectors require different keys")
    return problems


def contract_line() -> str:
    return "structured chunk index contract OK: {}, builder {}.".format(INDEX_VERSION, BUILDER)
