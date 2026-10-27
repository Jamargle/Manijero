"""Readiness for the answer service, separate from process liveness.

``/health`` keeps answering "this process is serving HTTP". Readiness answers the
different question the operator needs before routing traffic: is the explicitly
configured campaign valid, and can the reviewed corpus produce answers as of today?

Readiness reuses the accepted request-time corpus preparation, so it can never pass on a
corpus that would fail ``/ask``. Problems are fixed codes for the operator; the HTTP
response carries no corpus detail. Nothing here reads, stores, or logs a question.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from typing import Any, Tuple

from app.pilot_config import parse_campaign

CAMPAIGN_UNAVAILABLE = "campaign_unavailable"
CORPUS_UNAVAILABLE = "corpus_unavailable"
CORPUS_NOT_CURRENT = "corpus_not_current"
NO_ELIGIBLE_SOURCES = "no_eligible_sources"


@dataclass(frozen=True)
class ReadinessResult:
    """A readiness verdict with operator-facing fixed problem codes."""

    ready: bool
    problems: Tuple[str, ...] = ()
    eligible_source_count: int = 0


def get_configured_campaign() -> str | None:
    """Return the explicit campaign for the readiness route; never raises."""

    return parse_campaign(os.environ.get("MANIJERO_ACTIVE_CAMPAIGN"))


def evaluate_readiness(documents: Any, as_of: date, campaign: str | None) -> ReadinessResult:
    """Validate the active campaign and the corpus the answer path would use."""

    if campaign is None:
        return _not_ready(CAMPAIGN_UNAVAILABLE)

    # Imported lazily: app.ask_api owns the single corpus-validation path and imports
    # this module for its /ready route.
    from app.abstention import Abstention
    from app.ask_api import _prepare_runtime_corpus
    from app.retrieval import CatalogRejectedError, PassageSetError
    from app.source_catalog import CatalogReadError

    try:
        corpus: Any = _prepare_runtime_corpus(documents, as_of, campaign)
    except (CatalogReadError, CatalogRejectedError, PassageSetError, RuntimeError, ValueError):
        # Every accepted corpus defect already fails closed on /ask; readiness only needs
        # the verdict, never the rejected values.
        return _not_ready(CORPUS_UNAVAILABLE)
    if isinstance(corpus, Abstention):
        return _not_ready(CORPUS_NOT_CURRENT)
    eligible = int(getattr(corpus, "eligible_source_count", 0))
    if eligible == 0:
        return _not_ready(NO_ELIGIBLE_SOURCES)
    return ReadinessResult(ready=True, eligible_source_count=eligible)


def _not_ready(code: str) -> ReadinessResult:
    return ReadinessResult(ready=False, problems=(code,))
