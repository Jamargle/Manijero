"""Offline, code-owned land clarification decisions.

This module makes the accepted ``needs_land_clarification`` response actually
happen. It composes the accepted modules unchanged (``retrieval``,
``abstention``, ``generation``): it never reads a catalog or a passages file
itself, never calls a model or the network, and never filters by applicability
anywhere else.

When the answer materially differs between the supplied lands, the person is
asked to choose which land (or lands) their question is about instead of the
service guessing one arbitrarily. Only the opaque local ids are returned on the
wire: the client owns the names and collects the selection, and no name, note,
area, or timestamp ever leaves the device.

Durable rules:

* A clarification is offered only for ``mode: all_active`` with two or more
  supplied lands. ``general``, a single land, and a ``selected`` request (the
  person has already chosen) always delegate to the accepted
  :func:`app.abstention.answer_or_abstain`, so a selected request is never asked
  to clarify again.
* The only discriminating dimensions are ``water_regime`` and ``production_method``
  (the two a request can carry). ``crop`` is not a request field, so a ``crop``
  restriction is compatible with every land and never discriminates.
* Compatibility is conservative and lexical. A candidate *declares* a dimension
  when its ``applicability`` carries that key with a value other than ``unknown``.
  A candidate is compatible with a land when it declares no dimension the land
  disagrees with; an omitted, blank, or ``unknown`` land attribute never excludes
  a candidate and never invents a value.
* A clarification payload is exactly the accepted ``AskResponse`` keys with
  ``status == "needs_land_clarification"``, ``answer == ""``, ``sources == []``,
  ``land_scope == "selected"``, and a non-empty, unique list of the request's own
  land ids. No passage, excerpt, figure, or date can appear.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from app.abstention import Abstention, answer_or_abstain
from app.generation import (
    LAND_SCOPES,
    Answered,
    GroundingGenerator,
)
from app.retrieval import DEFAULT_K, RetrievedPassage, Retriever

# The attribute dimensions that can discriminate between two supplied lands, in
# the documented order. `crop` is deliberately absent: the request has no crop
# field, so a crop restriction applies to every land equally.
DISCRIMINATING_DIMENSIONS: Tuple[str, ...] = ("water_regime", "production_method")

CLARIFICATION_STATUS = "needs_land_clarification"
CLARIFICATION_SCOPE = "selected"

# Clarification needs at least two lands to differentiate.
MIN_LANDS = 2

# The citation window inspected for applicability, matching `abstention`.
DEFAULT_MAX_CLAIMS = 2

# Accepted `AskResponse.land_ids_to_choose` items are 1..128 characters.
MAX_LAND_ID_CHARS = 128


@dataclass(frozen=True)
class NeedsLandClarification:
    """One deterministically-detected land clarification decision.

    ``land_ids_to_choose`` holds the opaque local ids of the supplied lands that
    are involved in a material difference, in request order and deduplicated. The
    wire payload is assembled by :func:`to_clarification_response`; an empty list,
    a blank id, an over-long id, or a duplicate is a programming error and raises
    ``ValueError`` rather than emitting anything.
    """

    land_ids_to_choose: Tuple[str, ...]

    def __post_init__(self) -> None:
        ids = tuple(self.land_ids_to_choose)
        if not ids:
            raise ValueError("land_ids_to_choose must not be empty")
        for land_id in ids:
            if not isinstance(land_id, str) or not land_id.strip():
                raise ValueError("every chosen land id must be a non-blank string")
            if len(land_id) > MAX_LAND_ID_CHARS:
                raise ValueError(
                    "a chosen land id exceeds the {} character contract bound".format(
                        MAX_LAND_ID_CHARS
                    )
                )
        if len(set(ids)) != len(ids):
            raise ValueError("chosen land ids must be unique")


def land_context_mode(land_context: Any) -> str:
    """Return the request's ``land_context.mode``, defaulting to ``general``."""

    if isinstance(land_context, Mapping):
        mode = land_context.get("mode")
        if isinstance(mode, str):
            return mode
    return "general"


def land_ids_of(land_context: Any) -> Tuple[str, ...]:
    """Return the non-blank land ids the request carries, in request order."""

    ids: List[str] = []
    for land in _lands_of(land_context):
        land_id = land.get("id")
        if isinstance(land_id, str) and land_id.strip():
            ids.append(land_id)
    return tuple(ids)


def declared_applicability(
    candidate: RetrievedPassage, dimension: str
) -> Optional[str]:
    """Return the value ``candidate`` declares for ``dimension``, or ``None``.

    A dimension is declared only when ``applicability`` carries it with a
    non-blank value other than ``unknown``. Anything unrecognized is treated as
    not declared, so it never excludes a land.
    """

    applicability = candidate.applicability
    if not isinstance(applicability, Mapping):
        return None
    value = applicability.get(dimension)
    if not isinstance(value, str) or not value.strip() or value == "unknown":
        return None
    return value


def candidate_is_applicable(candidate: RetrievedPassage, land: Any) -> bool:
    """Return whether ``candidate`` is compatible with one supplied ``land``.

    A land's omitted, blank, or ``unknown`` attribute is compatible with every
    candidate, and a candidate that declares no discriminating dimension is
    compatible with every land. Only a known land value that disagrees with a
    declared applicability excludes the candidate.
    """

    for dimension in DISCRIMINATING_DIMENSIONS:
        declared = declared_applicability(candidate, dimension)
        if declared is None:
            continue
        value = _land_attribute(land, dimension)
        if value is None:
            continue
        if value != declared:
            return False
    return True


def compatible_passage_ids(
    candidates: Any, land: Any
) -> Tuple[str, ...]:
    """Return the ids of the candidates applicable to one supplied ``land``."""

    return tuple(
        candidate.passage_id
        for candidate in candidates
        if candidate_is_applicable(candidate, land)
    )


def clarify_land_scope(
    question: str,
    land_context: Any,
    corpus: Union[Retriever, Abstention],
    *,
    k: int = DEFAULT_K,
    max_claims: int = DEFAULT_MAX_CLAIMS,
) -> Optional[NeedsLandClarification]:
    """Decide whether the question must be clarified across the supplied lands.

    Returns ``None`` unless the request is ``all_active`` with at least two
    lands, the corpus is a current :class:`Retriever`, and the citation window
    (the first ``max_claims`` candidates) makes the lands' applicable-passage
    sets differ. A corpus-level :class:`Abstention` (a stale corpus), a
    ``general``/``selected`` request, a single land, and an empty candidate set
    all return ``None`` so the accepted abstention/answer path owns them.
    """

    if land_context_mode(land_context) != "all_active":
        return None
    lands = _lands_of(land_context)
    if len(lands) < MIN_LANDS:
        return None
    if isinstance(corpus, Abstention):
        return None
    if not isinstance(corpus, Retriever):
        raise ValueError("corpus must be a Retriever or a corpus-level Abstention")

    candidates = corpus.search(question, k=k)
    window = tuple(candidates[: max(0, max_claims)])
    if not window:
        return None

    compatible_by_land = [compatible_passage_ids(window, land) for land in lands]

    chosen: List[str] = []
    seen: Dict[str, None] = {}
    for index, land in enumerate(lands):
        differs = any(
            compatible_by_land[index] != compatible_by_land[other]
            for other in range(len(lands))
            if other != index
        )
        if not differs:
            continue
        land_id = land.get("id")
        if not isinstance(land_id, str) or not land_id.strip():
            # An unusable id cannot be offered; never invent one.
            continue
        if land_id in seen:
            continue
        seen[land_id] = None
        chosen.append(land_id)

    if not chosen:
        return None
    return NeedsLandClarification(tuple(chosen))


def answer_with_clarification(
    question: str,
    land_context: Any,
    corpus: Union[Retriever, Abstention],
    *,
    k: int = DEFAULT_K,
    max_claims: int = DEFAULT_MAX_CLAIMS,
    as_of: Optional[date],
    generator: Optional[GroundingGenerator] = None,
) -> Union[Answered, Abstention, NeedsLandClarification]:
    """Return a clarification decision, or the accepted answer/abstention.

    :func:`clarify_land_scope` runs first; on a decision it is returned
    unchanged. Otherwise the accepted :func:`answer_or_abstain` runs with
    ``land_scope = land_context.mode``, so ``general``, a single land, and a
    ``selected`` request behave exactly as accepted.
    """

    decision = clarify_land_scope(
        question,
        land_context,
        corpus,
        k=k,
        max_claims=max_claims,
    )
    if decision is not None:
        return decision
    return answer_or_abstain(
        question,
        corpus,
        k=k,
        max_claims=max_claims,
        land_scope=land_context_mode(land_context),
        as_of=as_of,
        generator=generator,
    )


def to_clarification_response(needs: NeedsLandClarification) -> Dict[str, Any]:
    """Assemble the accepted ``AskResponse`` payload for a clarification.

    The payload has exactly ``{status, answer, sources, land_scope,
    land_ids_to_choose}`` with an empty answer, no sources, ``land_scope:
    selected``, and the request's own land ids. A non-clarification decision
    raises ``ValueError`` rather than emitting anything.
    """

    if not isinstance(needs, NeedsLandClarification):
        raise ValueError(
            "to_clarification_response requires a NeedsLandClarification result"
        )
    return {
        "status": CLARIFICATION_STATUS,
        "answer": "",
        "sources": [],
        "land_scope": CLARIFICATION_SCOPE,
        "land_ids_to_choose": list(needs.land_ids_to_choose),
    }


def _lands_of(land_context: Any) -> Tuple[Mapping[str, Any], ...]:
    """Return the mapping-like lands the request carries, in request order."""

    if not isinstance(land_context, Mapping):
        return ()
    lands = land_context.get("lands")
    if not isinstance(lands, (list, tuple)):
        return ()
    return tuple(land for land in lands if isinstance(land, Mapping))


def _land_attribute(land: Any, dimension: str) -> Optional[str]:
    """Return a land's known value for ``dimension``, or ``None``.

    ``None`` covers an omitted key and an ``unknown``/blank stored value: neither
    ever excludes a candidate.
    """

    value = land.get(dimension) if isinstance(land, Mapping) else None
    if not isinstance(value, str) or not value.strip() or value == "unknown":
        return None
    return value


# `LAND_SCOPES` is re-exported so callers and tests can validate a mode without
# importing the generation module directly.
__all__ = [
    "CLARIFICATION_SCOPE",
    "CLARIFICATION_STATUS",
    "DEFAULT_MAX_CLAIMS",
    "DISCRIMINATING_DIMENSIONS",
    "LAND_SCOPES",
    "MAX_LAND_ID_CHARS",
    "MIN_LANDS",
    "NeedsLandClarification",
    "answer_with_clarification",
    "candidate_is_applicable",
    "clarify_land_scope",
    "compatible_passage_ids",
    "declared_applicability",
    "land_context_mode",
    "land_ids_of",
    "to_clarification_response",
]
