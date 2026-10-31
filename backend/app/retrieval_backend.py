"""Which candidate ranking ``POST /ask`` uses: BM25 by default, hybrid when opted in.

This module is deliberately light: importing it (and therefore the service)
never imports the embedding, vector-store, or hybrid modules, their optional
runtimes, or a model. Hybrid retrieval is selected only by explicit environment
configuration and is loaded lazily on the first request:

* ``MANIJERO_RETRIEVAL_MODE`` — unset or ``bm25`` keeps the accepted BM25
  ranking; ``hybrid`` opts in; any other value is refused and BM25 is used;
* ``MANIJERO_VECTOR_STORE`` — the derived Chroma store directory (required);
* ``MANIJERO_EMBEDDING_ARTIFACT`` — the verified local model directory (required);
* ``MANIJERO_EMBEDDING_CONFIG`` — the model pin (default: the repository pin);
* ``MANIJERO_HYBRID_CONFIG`` — fusion parameters (default: the repository file).

Even when hybrid is configured, a request uses hybrid ranking only while the
store is fresh for the current pin, campaign, and admitted documents; otherwise
it uses BM25. Nothing here changes the ``/ask`` wire contract.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Mapping, Optional, Protocol

from app.pilot_logging import operational_log
from app.retrieval import Retriever

MODE_BM25 = "bm25"
MODE_HYBRID = "hybrid"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMBEDDING_CONFIG = BACKEND_ROOT / "config" / "bge_m3_embedding.json"
DEFAULT_HYBRID_CONFIG = BACKEND_ROOT / "config" / "hybrid_retrieval.json"


class RetrievalBackend(Protocol):
    """Decides, per request, which ranking a prepared retriever uses."""

    @property
    def mode(self) -> str:
        """The configured mode (``bm25`` or ``hybrid``), not the per-request outcome."""

    def attach(self, retriever: Retriever, active_campaign: Optional[str]) -> Retriever:
        """Return ``retriever`` itself or a hybrid-ranked view of it; never raises."""


class Bm25Backend:
    """The default: the accepted BM25 ranking, unchanged."""

    def __init__(self, reason: Optional[str] = None) -> None:
        self._reason = reason

    @property
    def mode(self) -> str:
        return MODE_BM25

    @property
    def reason(self) -> Optional[str]:
        """Why a requested hybrid mode was refused, when it was."""

        return self._reason

    def attach(self, retriever: Retriever, active_campaign: Optional[str]) -> Retriever:
        return retriever


def backend_from_environment(environ: Mapping[str, str]) -> RetrievalBackend:
    """Build the configured backend without loading any model or store."""

    mode = (environ.get("MANIJERO_RETRIEVAL_MODE") or MODE_BM25).strip()
    if mode == MODE_BM25:
        return Bm25Backend()
    if mode != MODE_HYBRID:
        return _refused("retrieval_mode_invalid", configured="invalid")
    store = environ.get("MANIJERO_VECTOR_STORE", "").strip()
    artifact = environ.get("MANIJERO_EMBEDDING_ARTIFACT", "").strip()
    if not store or not artifact:
        return _refused("hybrid_not_configured")
    embedding_config = Path(
        environ.get("MANIJERO_EMBEDDING_CONFIG", "").strip() or DEFAULT_EMBEDDING_CONFIG
    )
    hybrid_config = Path(
        environ.get("MANIJERO_HYBRID_CONFIG", "").strip() or DEFAULT_HYBRID_CONFIG
    )

    from app.hybrid_retrieval import HybridBackend, load_hybrid_components

    return HybridBackend(
        lambda: load_hybrid_components(
            embedding_config, Path(artifact), Path(store), hybrid_config
        )
    )


_DEFAULT_LOCK = threading.Lock()
_DEFAULT_BACKEND: Optional[RetrievalBackend] = None


def get_retrieval_backend() -> RetrievalBackend:
    """FastAPI dependency: the process-wide backend, built once from the environment."""

    global _DEFAULT_BACKEND
    with _DEFAULT_LOCK:
        if _DEFAULT_BACKEND is None:
            _DEFAULT_BACKEND = backend_from_environment(os.environ)
        return _DEFAULT_BACKEND


def _refused(reason: str, configured: str = MODE_HYBRID) -> Bm25Backend:
    operational_log("retrieval_mode", configured=configured, active=MODE_BM25, reasons=reason)
    return Bm25Backend(reason=reason)
