"""Derived, rebuildable passage-embedding index.

The index is a *derived artifact*: it is never canonical knowledge, never lives
under ``knowledge/``, and never becomes an answer source. It stores one vector
per eligible reviewed passage plus the identities that produced it — the model
pin, the catalog/passages digests, ``as_of``, and the active campaign — so a
stale index is reported instead of silently reused.

Rebuild behavior is explicit:

* ``build_passage_index`` embeds the passages a validated
  :class:`app.retrieval.Retriever` already found eligible. Eligibility is never
  re-implemented here;
* ``write_index_atomic`` validates the document, refuses a path inside
  ``knowledge/``, and replaces the target atomically;
* :func:`index_status` reports ``missing``, ``up_to_date``, ``stale``, or
  ``invalid`` against the current inputs, so the rebuild command can gate on it.

The file never contains passage text, a question, or a score. It holds opaque
passage ids and floats, so it can live in an operator workspace with the same
access control as the derived reports.
"""

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.embeddings import (
    EmbeddingError,
    EmbeddingExecutionError,
    EmbeddingInputError,
    EmbeddingModel,
    EmbeddingModelSpec,
)
from app.source_catalog import is_non_blank_string

INDEX_SCHEMA_VERSION = "passage-embedding-index-v1"

INDEX_TOP_LEVEL_KEYS = frozenset({"schema_version", "model", "inputs", "passages"})
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
        "indexed_passage_count",
    }
)
PASSAGE_KEYS = frozenset({"passage_id", "vector"})

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

DEFAULT_K = 5

INDEX_UP_TO_DATE = "up_to_date"
INDEX_MISSING = "missing"
INDEX_STALE = "stale"
INDEX_INVALID = "invalid"


class EmbeddingIndexError(EmbeddingError):
    """A derived index is unreadable, malformed, or inconsistent with the pin."""


@dataclass(frozen=True)
class IndexInputs:
    """The corpus inputs that determine which passages are indexed."""

    catalog_sha256: str
    passages_sha256: str
    as_of: str
    active_campaign: Optional[str]

    def to_document(self, indexed_passage_count: int) -> Dict[str, Any]:
        return {
            "catalog_sha256": self.catalog_sha256,
            "passages_sha256": self.passages_sha256,
            "as_of": self.as_of,
            "active_campaign": self.active_campaign,
            "indexed_passage_count": indexed_passage_count,
        }


@dataclass(frozen=True)
class PassageMatch:
    """One nearest passage, ranked by cosine similarity."""

    passage_id: str
    score: float
    rank: int


@dataclass(frozen=True)
class IndexStatus:
    """Freshness of a derived index against the current inputs and pin."""

    state: str
    reasons: Tuple[str, ...]

    @property
    def up_to_date(self) -> bool:
        return self.state == INDEX_UP_TO_DATE

    def format_reasons(self) -> str:
        return ", ".join(self.reasons) if self.reasons else "none"


class PassageEmbeddingIndex:
    """Immutable in-memory map of passage id to unit-length embedding."""

    def __init__(self, dimension: int, vectors: Mapping[str, Tuple[float, ...]]) -> None:
        vectors_by_id = {passage_id: tuple(float(value) for value in vector) for passage_id, vector in vectors.items()}
        for passage_id, vector in vectors_by_id.items():
            if not passage_id:
                raise EmbeddingIndexError("index_invalid_id")
            if len(vector) != dimension:
                raise EmbeddingIndexError("index_dimension_mismatch")
        self._dimension = dimension
        self._vectors = vectors_by_id

    @classmethod
    def build(
        cls, documents: Sequence[Tuple[str, str]], model: EmbeddingModel
    ) -> "PassageEmbeddingIndex":
        """Embed ``(passage_id, text)`` pairs with ``model``.

        The document order is normalized by passage id so two runs over the same
        documents produce the same index. Embedding is batched by the model, not
        duplicated here.
        """

        ordered = sorted(documents, key=lambda pair: pair[0])
        seen: Dict[str, None] = {}
        texts: List[str] = []
        for passage_id, text in ordered:
            if not is_non_blank_string(passage_id) or not is_non_blank_string(text):
                raise EmbeddingIndexError("index_invalid_document")
            if passage_id in seen:
                raise EmbeddingIndexError("index_duplicate_id")
            seen[passage_id] = None
            texts.append(text)
        if not ordered:
            return cls(dimension=model.dimension, vectors={})
        try:
            embedded = model.embed(texts)
        except EmbeddingError:
            raise
        if len(embedded) != len(ordered):
            raise EmbeddingIndexError("index_embedding_count_mismatch")
        vectors: Dict[str, Tuple[float, ...]] = {}
        for (passage_id, _), vector in zip(ordered, embedded):
            if len(vector) != model.dimension:
                raise EmbeddingIndexError("index_dimension_mismatch")
            vectors[passage_id] = tuple(vector)
        return cls(dimension=model.dimension, vectors=vectors)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def passage_count(self) -> int:
        return len(self._vectors)

    @property
    def passage_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._vectors))

    def vector(self, passage_id: str) -> Optional[Tuple[float, ...]]:
        return self._vectors.get(passage_id)

    def search_vector(self, query_vector: Sequence[float], k: int = DEFAULT_K) -> Tuple[PassageMatch, ...]:
        """Rank every passage by cosine similarity to ``query_vector``.

        Only positive similarities are returned, mirroring the lexical retriever's
        rule that an unrelated passage is not a candidate. Ties break by ascending
        passage id so repeated runs never reorder.
        """

        if k < 1 or not self._vectors:
            return ()
        if len(query_vector) != self._dimension:
            raise EmbeddingIndexError("query_dimension_mismatch")
        query_norm = _norm(query_vector)
        if query_norm == 0.0:
            raise EmbeddingIndexError("query_zero_vector")
        scored: List[Tuple[str, float]] = []
        for passage_id, vector in self._vectors.items():
            denominator = query_norm * _norm(vector)
            if denominator == 0.0:
                continue
            similarity = sum(
                float(left) * float(right) for left, right in zip(query_vector, vector)
            ) / denominator
            if similarity > 0.0:
                scored.append((passage_id, similarity))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return tuple(
            PassageMatch(passage_id=passage_id, score=score, rank=position + 1)
            for position, (passage_id, score) in enumerate(scored[:k])
        )

    def search_text(
        self, model: EmbeddingModel, question: str, k: int = DEFAULT_K
    ) -> Tuple[PassageMatch, ...]:
        """Embed one question with ``model`` and rank the indexed passages."""

        if not is_non_blank_string(question):
            raise EmbeddingInputError("invalid_text_input")
        if k < 1 or not self._vectors:
            return ()
        try:
            embedded = model.embed([question])
        except EmbeddingError:
            raise
        if not embedded:
            raise EmbeddingExecutionError("encode_failed")
        return self.search_vector(embedded[0], k)

    def to_document(self, spec: EmbeddingModelSpec, inputs: IndexInputs) -> Dict[str, Any]:
        """Serialize the index with its model pin and corpus inputs."""

        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "model": spec.index_metadata(),
            "inputs": inputs.to_document(self.passage_count),
            "passages": [
                {"passage_id": passage_id, "vector": list(self._vectors[passage_id])}
                for passage_id in self.passage_ids
            ],
        }


def build_passage_index(
    retriever: Any, model: EmbeddingModel
) -> PassageEmbeddingIndex:
    """Build an index over the passages ``retriever`` already found eligible."""

    documents = retriever.indexed_documents()
    return PassageEmbeddingIndex.build(documents, model)


def build_index_document(
    index: PassageEmbeddingIndex,
    spec: EmbeddingModelSpec,
    inputs: IndexInputs,
) -> Dict[str, Any]:
    """Return the validated, serializable index document."""

    document = index.to_document(spec, inputs)
    _validate_index_document(document, spec)
    return document


def write_index_atomic(
    path: Path, document: Mapping[str, Any], spec: EmbeddingModelSpec
) -> None:
    """Validate and atomically replace a derived index file.

    Refuses a target inside the repository ``knowledge/`` directory, because the
    index is derived and must never look like reviewed canonical knowledge.
    """

    target = Path(path)
    if _inside_directory(target, KNOWLEDGE_ROOT):
        raise EmbeddingIndexError("unsafe_index_path")
    _validate_index_document(document, spec)
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, target)
    except OSError as error:
        raise EmbeddingIndexError("index_write_failed") from error


def read_index_document(path: Path) -> Dict[str, Any]:
    """Read a derived index file, raising a fixed-code error on failure."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise EmbeddingIndexError("index_unreadable") from error
    try:
        document = json.loads(text)
    except ValueError as error:
        raise EmbeddingIndexError("index_malformed") from error
    if not isinstance(document, dict):
        raise EmbeddingIndexError("index_malformed")
    return document


def load_index(document: Mapping[str, Any], spec: EmbeddingModelSpec) -> PassageEmbeddingIndex:
    """Validate ``document`` against ``spec`` and return the in-memory index."""

    _validate_index_document(document, spec)
    vectors: Dict[str, Tuple[float, ...]] = {}
    for entry in document["passages"]:
        vectors[entry["passage_id"]] = tuple(entry["vector"])
    return PassageEmbeddingIndex(
        dimension=document["model"]["embedding_dimension"], vectors=vectors
    )


def index_status(
    path: Path, spec: EmbeddingModelSpec, inputs: IndexInputs
) -> IndexStatus:
    """Report whether the index at ``path`` matches the pin and current inputs.

    A missing file is ``missing``; an unreadable or contract-violating file is
    ``invalid``; a different model pin or different corpus inputs is ``stale``
    with one reason per mismatch.
    """

    target = Path(path)
    if not target.exists():
        return IndexStatus(INDEX_MISSING, ("index_missing",))
    try:
        document = read_index_document(target)
        _validate_index_document(document, spec, check_pin=False)
    except EmbeddingIndexError as error:
        return IndexStatus(INDEX_INVALID, (_error_code(error),))

    reasons: List[str] = []
    model = document["model"]
    if model["model_id"] != spec.model_id:
        reasons.append("model_id_changed")
    if model["model_revision"] != spec.model_revision:
        reasons.append("model_revision_changed")
    if model["config_sha256"] != spec.config_sha256:
        reasons.append("model_config_changed")
    if model["embedding_dimension"] != spec.embedding_dimension:
        reasons.append("dimension_changed")
    if model["pooling"] != spec.pooling:
        reasons.append("pooling_changed")
    if model["normalize"] != spec.normalize:
        reasons.append("normalization_changed")
    if model["dtype"] != spec.dtype:
        reasons.append("dtype_changed")

    recorded_inputs = document["inputs"]
    if recorded_inputs["catalog_sha256"] != inputs.catalog_sha256:
        reasons.append("catalog_changed")
    if recorded_inputs["passages_sha256"] != inputs.passages_sha256:
        reasons.append("passages_changed")
    if recorded_inputs["as_of"] != inputs.as_of:
        reasons.append("as_of_changed")
    if recorded_inputs["active_campaign"] != inputs.active_campaign:
        reasons.append("active_campaign_changed")

    if reasons:
        return IndexStatus(INDEX_STALE, tuple(reasons))
    return IndexStatus(INDEX_UP_TO_DATE, ())


def file_sha256(path: Path) -> str:
    """Return the SHA-256 of one file's exact bytes."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _norm(vector: Sequence[float]) -> float:
    total = 0.0
    for value in vector:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise EmbeddingIndexError("vector_not_finite")
        total += number * number
    return total ** 0.5


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _error_code(error: EmbeddingError) -> str:
    text = str(error)
    return text.split(":", 1)[0] if text else "index_invalid"


def _validate_index_document(
    document: Any, spec: EmbeddingModelSpec, *, check_pin: bool = True
) -> None:
    """Validate the closed index contract and, optionally, its model binding.

    Freshness checking validates the document's own shape without pinning it to
    the current model, so a different (but valid) pin is reported as stale
    instead of invalid.
    """

    if not isinstance(document, dict):
        raise EmbeddingIndexError("index_malformed")
    if set(document) != INDEX_TOP_LEVEL_KEYS:
        raise EmbeddingIndexError("index_unknown_keys")
    if document.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise EmbeddingIndexError("index_schema_version")
    model = document.get("model")
    if not isinstance(model, dict) or set(model) != MODEL_KEYS:
        raise EmbeddingIndexError("index_invalid")
    if check_pin:
        if model["model_id"] != spec.model_id:
            raise EmbeddingIndexError("model_id_mismatch")
        if model["model_revision"] != spec.model_revision:
            raise EmbeddingIndexError("model_revision_mismatch")
        if model["embedding_dimension"] != spec.embedding_dimension:
            raise EmbeddingIndexError("dimension_mismatch")
        if model["config_sha256"] != spec.config_sha256:
            raise EmbeddingIndexError("model_config_mismatch")
        if model["pooling"] != spec.pooling:
            raise EmbeddingIndexError("pooling_mismatch")
        if model["normalize"] != spec.normalize:
            raise EmbeddingIndexError("normalize_mismatch")
    inputs = document.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != INPUT_KEYS:
        raise EmbeddingIndexError("index_invalid")
    _check_digest(inputs.get("catalog_sha256"))
    _check_digest(inputs.get("passages_sha256"))
    if not is_non_blank_string(inputs.get("as_of")):
        raise EmbeddingIndexError("index_invalid")
    campaign = inputs.get("active_campaign")
    if campaign is not None and not is_non_blank_string(campaign):
        raise EmbeddingIndexError("index_invalid")
    count = inputs.get("indexed_passage_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise EmbeddingIndexError("index_invalid")
    passages = document.get("passages")
    if not isinstance(passages, list):
        raise EmbeddingIndexError("index_invalid")
    if len(passages) != inputs["indexed_passage_count"]:
        raise EmbeddingIndexError("index_count_mismatch")
    seen: Dict[str, None] = {}
    previous_id: Optional[str] = None
    expected_dimension = spec.embedding_dimension if check_pin else model["embedding_dimension"]
    for entry in passages:
        if not isinstance(entry, dict) or set(entry) != PASSAGE_KEYS:
            raise EmbeddingIndexError("index_invalid")
        passage_id = entry["passage_id"]
        if not is_non_blank_string(passage_id):
            raise EmbeddingIndexError("index_invalid")
        if passage_id in seen:
            raise EmbeddingIndexError("index_duplicate_id")
        if previous_id is not None and passage_id <= previous_id:
            raise EmbeddingIndexError("index_unsorted")
        seen[passage_id] = None
        previous_id = passage_id
        vector = entry["vector"]
        if not isinstance(vector, list) or len(vector) != expected_dimension:
            raise EmbeddingIndexError("vector_length_mismatch")
        if len(vector) != model["embedding_dimension"]:
            raise EmbeddingIndexError("dimension_mismatch")
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingIndexError("vector_not_numeric")
            if not math.isfinite(float(value)):
                raise EmbeddingIndexError("vector_not_finite")


def _check_digest(value: Any) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise EmbeddingIndexError("index_invalid")
