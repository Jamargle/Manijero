"""Development-only inspection of one answer: passages, scores, and verification codes.

``inspection`` rides on the ``/ask`` 200 response only when the deployment profile is
explicitly stated as ``development`` (the same rule as the trace text:
:func:`app.answer_trace.text_allowed`). It is never sent for an unset, unknown, pilot, QA,
or production profile. It holds ids, scores, fixed codes, timings, and public corpus
text only; question, answer, and draft text, land values, client ids, tokens, and
``GroundingIssue.detail`` are never included. Standard library only.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.answer_trace import TraceCollector, text_allowed

SCHEMA_VERSION = "answer-inspection-v1"
MAX_EXCERPT_CHARS = 2000

# Key paths of an inspection ("[]" marks a list of objects). Anything else is a leak.
INSPECTION_KEYS = frozenset(
    {
        "schema", "total_ms",
        "retrieval", "retrieval.mode", "retrieval.k", "retrieval.search_calls",
        "retrieval.duration_ms", "retrieval.vector", "retrieval.vector.used",
        "retrieval.vector.fallback_code", "retrieval.passages",
        "retrieval.passages[].rank", "retrieval.passages[].passage_id",
        "retrieval.passages[].source_id", "retrieval.passages[].title",
        "retrieval.passages[].location", "retrieval.passages[].score",
        "retrieval.passages[].lexical_rank", "retrieval.passages[].lexical_score",
        "retrieval.passages[].vector_similarity", "retrieval.passages[].cited",
        "retrieval.passages[].excerpt",
        "drafting", "drafting.provider", "drafting.outcome", "drafting.status",
        "drafting.cited_markers", "drafting.duration_ms",
        "verification", "verification.ok", "verification.issues", "verification.claims",
        "verification.claims[].index", "verification.claims[].markers",
        "verification.claims[].ok", "verification.claims[].issues",
        "verification.duration_ms",
        "outcome", "outcome.abstention_reason", "outcome.generation_reason",
        "outcome.cited_passage_ids",
    }
)


def inspection_allowed(profile: str, environ: Any) -> bool:
    """One rule for trace text and inspection: an explicitly stated local profile."""

    return text_allowed(profile, environ)


class InspectionError(Exception):
    """Building the inspection failed; ``code`` is a fixed value safe to log."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _ms(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


def build_inspection(collector: Optional[TraceCollector]) -> Dict[str, Any]:
    """The ``answer-inspection-v1`` object; raises :class:`InspectionError` on any problem."""

    if collector is None:
        raise InspectionError("no_collector")
    try:
        outcome = collector.outcome
        cited = [str(i) for i in outcome.get("cited_passage_ids", [])]
        return {
            "schema": SCHEMA_VERSION,
            "retrieval": _retrieval(collector, set(cited)),
            "drafting": _drafting(collector),
            "verification": _verification(collector),
            "outcome": {
                "abstention_reason": outcome.get("abstention_reason"),
                "generation_reason": outcome.get("generation_reason"),
                "cited_passage_ids": cited,
            },
            "total_ms": _ms(time.monotonic() - collector.started),
        }
    except InspectionError:
        raise
    except Exception:  # noqa: BLE001 - never fails a request
        raise InspectionError("build_failed")


def _retrieval(collector: TraceCollector, cited: set) -> Optional[Dict[str, Any]]:
    if collector.mode is None:
        return None
    k = collector.k if collector.k is not None else 0
    lexical = {
        passage_id: (rank, score)
        for rank, (passage_id, score) in enumerate(collector.lexical, start=1)
    }
    vector = collector.vector
    similarity = (
        {m["passage_id"]: m["similarity"] for m in vector["matches"]} if vector else {}
    )
    passages: List[Dict[str, Any]] = []
    for candidate in sorted(collector.candidates, key=lambda c: c["rank"])[: max(k, 0)]:
        passage_id = candidate["passage_id"]
        title, location, excerpt = collector.details.get(passage_id, ("", "", ""))
        lexical_rank, lexical_score = lexical.get(passage_id, (None, None))
        passages.append(
            {
                "rank": candidate["rank"],
                "passage_id": passage_id,
                "source_id": candidate["source_id"],
                "title": title,
                "location": location,
                "score": candidate["score"],
                "lexical_rank": lexical_rank,
                "lexical_score": None if lexical_score is None else round(lexical_score, 6),
                "vector_similarity": similarity.get(passage_id),
                "cited": passage_id in cited,
                "excerpt": excerpt[:MAX_EXCERPT_CHARS],
            }
        )
    return {
        "mode": collector.mode,
        "k": k,
        "search_calls": collector.search_calls,
        "duration_ms": _ms(collector.retrieval_seconds),
        "vector": (
            None
            if vector is None
            else {"used": vector["used"], "fallback_code": vector["fallback_code"]}
        ),
        "passages": passages,
    }


def _drafting(collector: TraceCollector) -> Optional[Dict[str, Any]]:
    if collector.drafting is None:
        return None
    drafting = collector.drafting
    return {
        "provider": drafting.get("provider"),
        "outcome": drafting.get("outcome"),
        "status": drafting.get("status"),
        "cited_markers": drafting.get("cited_markers", []),
        "duration_ms": drafting.get("duration_ms"),
    }


def _verification(collector: TraceCollector) -> Optional[Dict[str, Any]]:
    verification = collector.verification
    if verification is None:
        return None
    return {
        "ok": verification["ok"],
        "issues": list(verification["issues"]),
        "claims": [dict(claim) for claim in verification["claims"]],
        "duration_ms": verification["duration_ms"],
    }
