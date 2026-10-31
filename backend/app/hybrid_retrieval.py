"""Opt-in hybrid (BM25 + vector) candidate ranking with Reciprocal Rank Fusion.

Hybrid retrieval is composed into the accepted :class:`app.retrieval.Retriever`
through :meth:`Retriever.with_ranker`; it is never a second retriever. The
retriever keeps every guarantee it already had:

* only passages it admitted (approved, current, unexpired, active campaign) can
  be returned, because the retriever drops any other id a ranker yields;
* a question with no lexical BM25 match still returns no candidate (the
  *lexical gate*), so vector similarity can never turn a zero-evidence question
  into an answer;
* citations, generation, verification, abstention, and land clarification are
  downstream and unchanged.

Fusion method — Reciprocal Rank Fusion (Cormack, Clarke and Büttcher, 2009)::

    rrf(d) = sum over lists L containing d of 1 / (rrf_k + rank_L(d))

with two lists: the BM25 ranking (positive scores only) and the vector ranking
(cosine similarity strictly above ``vector_min_similarity``), each truncated to
``candidate_depth``; ranks are 1-based; both lists have equal weight; ties break
by ascending passage id. Scores and ranks are therefore deterministic for the
same inputs, model, and store.

Fail-closed rule: when hybrid retrieval is not configured, the store is
missing/invalid/stale, the optional runtime or model is unavailable, or a query
fails, the request uses the unchanged BM25 ranking. Only fixed reason codes are
logged — never a question, passage text, or land value.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple

from app.embeddings import EmbeddingError, EmbeddingModel, EmbeddingModelSpec
from app.pilot_logging import operational_log
from app.retrieval import Retriever
from app.retrieval_backend import MODE_BM25, MODE_HYBRID
from app.vector_store import (
    StoreStatus,
    VectorMatch,
    error_code,
    manifest_status,
)

HYBRID_CONFIG_SCHEMA_VERSION = "hybrid-retrieval-v1"
FUSION_METHOD = "reciprocal_rank_fusion"
HYBRID_CONFIG_KEYS = frozenset(
    {"schema_version", "fusion", "rrf_k", "candidate_depth", "vector_min_similarity"}
)



class HybridConfigError(ValueError):
    """The hybrid retrieval configuration violates its closed contract."""


@dataclass(frozen=True)
class HybridSettings:
    """Validated fusion parameters plus the digest of the configuration file."""

    rrf_k: int
    candidate_depth: int
    vector_min_similarity: float
    config_sha256: str


def validate_hybrid_config(document: Any) -> HybridSettings:
    """Validate a parsed ``hybrid-retrieval-v1`` document."""

    if not isinstance(document, dict) or set(document) != HYBRID_CONFIG_KEYS:
        raise HybridConfigError("hybrid_config_unknown_keys")
    if document["schema_version"] != HYBRID_CONFIG_SCHEMA_VERSION:
        raise HybridConfigError("hybrid_config_schema_version")
    if document["fusion"] != FUSION_METHOD:
        raise HybridConfigError("hybrid_config_fusion")
    rrf_k = document["rrf_k"]
    if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or not 1 <= rrf_k <= 1000:
        raise HybridConfigError("hybrid_config_rrf_k")
    depth = document["candidate_depth"]
    if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= 100:
        raise HybridConfigError("hybrid_config_candidate_depth")
    floor = document["vector_min_similarity"]
    if (
        isinstance(floor, bool)
        or not isinstance(floor, (int, float))
        or not 0.0 <= float(floor) < 1.0
    ):
        raise HybridConfigError("hybrid_config_vector_min_similarity")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return HybridSettings(
        rrf_k=rrf_k,
        candidate_depth=depth,
        vector_min_similarity=float(floor),
        config_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def load_hybrid_settings(path: Path) -> HybridSettings:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HybridConfigError("hybrid_config_unreadable") from error
    return validate_hybrid_config(document)


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], rrf_k: int, depth: int
) -> Tuple[Tuple[str, float], ...]:
    """Fuse best-first id lists with RRF; ties break by ascending id.

    Each list is truncated to ``depth`` and de-duplicated (first occurrence
    wins) before scoring, so a repeated id cannot gain extra weight.
    """

    if rrf_k < 1 or depth < 1:
        raise ValueError("rrf_k and depth must be positive")
    scores: Dict[str, float] = {}
    for ranking in rankings:
        seen: Dict[str, None] = {}
        for passage_id in ranking:
            if passage_id in seen:
                continue
            seen[passage_id] = None
            if len(seen) > depth:
                break
            scores[passage_id] = scores.get(passage_id, 0.0) + 1.0 / (rrf_k + len(seen))
    return tuple(sorted(scores.items(), key=lambda pair: (-pair[1], pair[0])))


class VectorSearcher(Protocol):
    """The vector side of hybrid ranking (a Chroma store in production)."""

    def query(self, vector: Sequence[float], depth: int) -> Tuple[VectorMatch, ...]:
        """Return up to ``depth`` matches best first."""


@dataclass(frozen=True)
class RankTrace:
    """What the last ranking call did, for operators and evaluation only."""

    used_vector: bool
    fallback_reason: Optional[str]


class HybridRanker:
    """A :class:`app.retrieval.CandidateRanker` fusing BM25 with vector matches."""

    def __init__(
        self,
        embedder: EmbeddingModel,
        store: VectorSearcher,
        settings: HybridSettings,
        lock: Optional[threading.Lock] = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._settings = settings
        self._lock = lock or threading.Lock()
        self.last_trace = RankTrace(used_vector=False, fallback_reason=None)

    def rank(
        self, question: str, lexical: Tuple[Tuple[str, float], ...]
    ) -> Sequence[Tuple[str, float]]:
        depth = self._settings.candidate_depth
        try:
            with self._lock:
                embedded = self._embedder.embed([question])
                if len(embedded) != 1:
                    raise ValueError("encode_failed")
                matches = self._store.query(embedded[0], depth)
        except Exception as error:  # any failure keeps the accepted BM25 ranking
            reason = failure_code(error)
            self.last_trace = RankTrace(used_vector=False, fallback_reason=reason)
            operational_log("hybrid_retrieval_fallback", reason=reason)
            return lexical
        vector_ids = [
            match.passage_id
            for match in matches
            if match.similarity > self._settings.vector_min_similarity
        ]
        self.last_trace = RankTrace(used_vector=True, fallback_reason=None)
        return reciprocal_rank_fusion(
            [[passage_id for passage_id, _ in lexical], vector_ids],
            rrf_k=self._settings.rrf_k,
            depth=depth,
        )


@dataclass(frozen=True)
class HybridComponents:
    """Loaded runtime pieces for hybrid ranking."""

    spec: EmbeddingModelSpec
    embedder: EmbeddingModel
    store: Any  # ChromaPassageStore (or a test double with ``manifest`` and ``query``)
    settings: HybridSettings


class HybridBackend:
    """Hybrid ranking when the store is fresh for the current corpus; else BM25.

    ``loader`` runs once, lazily, on the first request, so importing the service
    never loads a model or opens a store. A load failure is remembered and the
    service keeps answering with BM25 until it restarts.
    """

    def __init__(self, loader: Callable[[], HybridComponents]) -> None:
        self._loader = loader
        self._lock = threading.Lock()
        self._query_lock = threading.Lock()
        self._components: Optional[HybridComponents] = None
        self._load_failure: Optional[str] = None
        self._loaded = False
        self._last_state: Optional[Tuple[str, Tuple[str, ...]]] = None

    @property
    def mode(self) -> str:
        return MODE_HYBRID

    def status(self, retriever: Retriever, active_campaign: Optional[str]) -> StoreStatus:
        """Freshness for this corpus; ``invalid`` with the load reason on failure."""

        components = self._ensure_loaded()
        if components is None:
            return StoreStatus("invalid", (self._load_failure or "hybrid_unavailable",))
        return manifest_status(
            components.store.manifest,
            components.spec,
            active_campaign,
            retriever.indexed_documents(),
        )

    def attach(self, retriever: Retriever, active_campaign: Optional[str]) -> Retriever:
        try:
            status = self.status(retriever, active_campaign)
            self._report(status)
            if not status.up_to_date or self._components is None:
                return retriever
            components = self._components
            return retriever.with_ranker(
                HybridRanker(
                    components.embedder,
                    components.store,
                    components.settings,
                    lock=self._query_lock,
                )
            )
        except Exception as error:  # never let ranking setup fail a request
            operational_log("hybrid_retrieval_fallback", reason=type(error).__name__)
            return retriever

    def _ensure_loaded(self) -> Optional[HybridComponents]:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                try:
                    self._components = self._loader()
                except Exception as error:
                    self._load_failure = failure_code(error)
                    self._components = None
            return self._components

    def _report(self, status: StoreStatus) -> None:
        state = (status.state, status.reasons)
        if state == self._last_state:
            return
        self._last_state = state
        operational_log(
            "retrieval_mode",
            configured=MODE_HYBRID,
            active=MODE_HYBRID if status.up_to_date else MODE_BM25,
            store_state=status.state,
            reasons=",".join(status.reasons),
        )


def load_hybrid_components(
    embedding_config: Path,
    artifact_dir: Path,
    store_dir: Path,
    hybrid_config: Path,
    threads: Optional[int] = None,
) -> HybridComponents:
    """Load the pinned embedder and open the Chroma store (both fail closed)."""

    from app.embeddings import LocalBgeM3Embedder, load_model_spec
    from app.vector_store import ChromaPassageStore

    settings = load_hybrid_settings(hybrid_config)
    spec = load_model_spec(embedding_config)
    store = ChromaPassageStore.open(store_dir, spec)
    embedder = LocalBgeM3Embedder.load(spec, artifact_dir, threads=threads)
    return HybridComponents(spec=spec, embedder=embedder, store=store, settings=settings)


def failure_code(error: Exception) -> str:
    """A loggable reason: the fixed code of a project error, else the type name.

    Third-party exception messages may echo inputs, so they are never logged.
    """

    if isinstance(error, (EmbeddingError, HybridConfigError)) and str(error):
        return error_code(error)
    return type(error).__name__


def describe_settings(settings: HybridSettings) -> Mapping[str, Any]:
    return {
        "fusion": FUSION_METHOD,
        "rrf_k": settings.rrf_k,
        "candidate_depth": settings.candidate_depth,
        "vector_min_similarity": settings.vector_min_similarity,
        "config_sha256": settings.config_sha256,
    }
