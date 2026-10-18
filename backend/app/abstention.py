"""Offline, code-owned abstention decisions.

This module is the *decision* side of the answer gate. It composes the accepted
:func:`app.generation.generate_grounded_answer` pipeline and adds the pre-checks
that ``grounded_answer_generation`` explicitly deferred: a question whose
presupposition no retrieved candidate supports, a corpus that cannot be confirmed
current as of ``as_of``, and two ``critical`` candidates that disagree about the
same unit.

Every "no safe answer" outcome becomes one :class:`Abstention` with a stable
machine-readable :data:`ABSTENTION_REASONS` code, and every code maps to one
pinned plain-Spanish message in :data:`ABSTENTION_MESSAGES`. The module never
reads a catalog or a passage file itself, never re-implements eligibility or
grounding, never calls a model or the network, and never emits a draft sentence,
candidate excerpt, source, figure, or date. Copy is owned by code: an
:class:`Abstention` has no text field, and :func:`to_abstention_response`
resolves the pinned message by reason.

Durable rules:

* An abstention payload is exactly the accepted ``AskResponse`` keys with
  ``status == "abstained"``, ``sources == []``, ``land_ids_to_choose == []``,
  and a non-blank ``answer`` of at most ``MAX_ANSWER_CHARS``.
* Every pinned message contains no digit and no date, so an abstention can never
  invent a deadline or an amount, and ends with a concrete next step.
* Detection is lexical and conservative (a retrieval miss, an unconfirmed
  instrument reference, or an unrelated pair of critical passages sharing a unit
  can all abstain). That is the safe direction; semantic judgement and the
  measured trap set belong to ``land_safety_evaluation``.
* A corpus that declares sources but has no source eligible as of ``as_of``
  (expired, non-``approved``, or non-``current``) abstains as ``stale_evidence``
  before any question is answered. Any other catalog defect stays a hard
  ``CatalogRejectedError`` from the accepted gate, and a malformed passage set,
  an unknown ``source_id``, or an unreadable file stays a hard
  ``PassageSetError``/``CatalogReadError``, because a broken deployment must be
  loud, not silent.
* ``AskResponse`` forbids extra properties, so the abstention sub-reason is not
  on the wire: it stays a Python-level value on :class:`Abstention`.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple, Union

from app.generation import (
    LAND_SCOPES,
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    Answered,
    ClaimVerdict,
    GroundingGenerator,
    GroundingIssue,
    NotAnswered,
    generate_grounded_answer,
    normalize_text,
)
from app.retrieval import (
    DEFAULT_K,
    RetrievedPassage,
    Retriever,
    eligible_source_ids,
)

# The stable, machine-readable abstention taxonomy, in the documented order.
ABSTENTION_REASONS: Tuple[str, ...] = (
    "invalid_question",
    "no_evidence",
    "insufficient_evidence",
    "stale_evidence",
    "conflicting_evidence",
    "false_premise",
    "unsafe_request",
    "generator_abstained",
    "generation_error",
)

# The pinned plain-Spanish copy, one message per reason. Code owns this copy: no
# generator, prompt, model, or clock contributes to it, and no message contains a
# digit or a date. Every message ends with a concrete next step.
ABSTENTION_MESSAGES: Dict[str, str] = {
    "invalid_question": (
        "Necesito una pregunta para poder ayudarte. Escribe tu duda en pocas "
        "palabras e inténtalo otra vez."
    ),
    "no_evidence": (
        "No he encontrado esta información en los documentos oficiales que tengo. "
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."
    ),
    "insufficient_evidence": (
        "Los documentos oficiales que tengo no me permiten responderte con seguridad. "
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."
    ),
    "stale_evidence": (
        "No puedo comprobar que la información oficial que tengo siga vigente, así que "
        "no te doy una respuesta. Comprueba la convocatoria vigente o pregunta en tu "
        "oficina comarcal agraria."
    ),
    "conflicting_evidence": (
        "He encontrado documentos oficiales que no coinciden entre sí y no puedo darte "
        "un dato seguro. Confírmalo en tu oficina comarcal agraria o con tu cooperativa."
    ),
    "false_premise": (
        "No puedo confirmar ese dato con los documentos oficiales revisados. Comprueba "
        "el nombre o el número exacto con tu oficina comarcal agraria o con tu "
        "cooperativa."
    ),
    "unsafe_request": (
        "No puedo confirmar tu situación concreta ni calcular lo que te corresponde. "
        "Consulta tu caso en tu oficina comarcal agraria o con tu cooperativa."
    ),
    "generator_abstained": (
        "Con los documentos oficiales que tengo no puedo preparar una respuesta segura "
        "para esta pregunta. Consulta con tu oficina comarcal agraria o con tu "
        "cooperativa."
    ),
    "generation_error": (
        "Ahora mismo no he podido preparar la respuesta. Vuelve a intentarlo dentro de "
        "un momento; si sigue igual, pregunta en tu oficina comarcal agraria o con tu "
        "cooperativa."
    ),
}

# The one-way map from an accepted generation reason to this taxonomy. An
# unrecognized generation reason fails closed to ``generation_error``.
GENERATION_REASON_MAP: Dict[str, str] = {
    "invalid_question": "invalid_question",
    "no_candidates": "no_evidence",
    "grounding_failed": "insufficient_evidence",
    "policy_failed": "unsafe_request",
    "generator_abstained": "generator_abstained",
    "generation_error": "generation_error",
}

# The fixed, documented units used by the critical-evidence conflict check. The
# unit names are the display forms; matching is done on their normalized forms.
CRITICAL_UNITS: Tuple[str, ...] = (
    "días",
    "meses",
    "años",
    "euros",
    "hectáreas",
    "semanas",
    "%",
)

# Normalized singular/plural aliases for the documented units. They are used
# only to anchor a number to a unit; unknown units are ignored.
_UNIT_ALIASES: Dict[str, str] = {
    "dia": "días",
    "dias": "días",
    "mes": "meses",
    "meses": "meses",
    "ano": "años",
    "anos": "años",
    "euro": "euros",
    "euros": "euros",
    "hectarea": "hectáreas",
    "hectareas": "hectáreas",
    "semana": "semanas",
    "semanas": "semanas",
    "%": "%",
}

# Instrument/article keywords whose presupposition must be confirmable from the
# retrieved candidates. Longest alternatives come first so ``real decreto`` and
# ``decreto ley`` win over ``decreto``.
INSTRUMENT_KEYWORDS: Tuple[str, ...] = (
    "real decreto",
    "decreto ley",
    "decreto",
    "ley",
    "orden",
    "reglamento",
    "norma",
    "rd",
)

_INSTRUMENT = re.compile(
    r"\b(real decreto|decreto[-\s]?ley|decreto|ley|orden|reglamento|norma|rd)\b"
    r"(?:\s+(?:n[.,]?[o0]?\s*|numero\s+|num[.,]?\s+)?(\d+(?:\s*/\s*\d+)?))?"
)
_ARTICLE = re.compile(r"\barticulos?\s+(\d+(?:\s*/\s*\d+)?)")
_UNIT_VALUE = re.compile(
    r"(\d[\d.,]*)\s*(%|dias?\b|mes(?:es)?\b|anos?\b|euros?\b|hectareas?\b|semanas?\b)"
)


@dataclass(frozen=True)
class Abstention:
    """One deterministic, code-owned abstention decision.

    ``reason`` is always a member of :data:`ABSTENTION_REASONS`; an unknown reason
    is a programming error and raises ``ValueError``. ``generation_reason``
    preserves the accepted generation reason code when the abstention came from
    the pipeline, and ``issues``/``claims`` preserve its traceability. There is
    deliberately no text field: :attr:`message` resolves the pinned copy by
    reason, so no caller can inject copy.
    """

    reason: str
    generation_reason: Optional[str] = None
    issues: Tuple[GroundingIssue, ...] = ()
    claims: Tuple[ClaimVerdict, ...] = ()

    def __post_init__(self) -> None:
        if self.reason not in ABSTENTION_MESSAGES:
            raise ValueError(
                "reason must be one of: {}".format(", ".join(ABSTENTION_REASONS))
            )

    @property
    def message(self) -> str:
        """Return the pinned plain-Spanish message for this reason."""

        return ABSTENTION_MESSAGES[self.reason]

    def codes(self) -> Tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


@dataclass(frozen=True)
class UnitConflict:
    """Two ``critical`` candidates in the citation window disagree on one unit."""

    unit: str
    values: Tuple[str, ...]


def prepare_corpus(
    catalog_document: Any,
    passage_document: Any,
    as_of: date,
    active_campaign: Optional[str] = None,
) -> Union[Retriever, Abstention]:
    """Return a retriever, or a corpus-level ``stale_evidence`` abstention.

    The catalog's currency is a corpus property: when the catalog declares
    sources but :func:`app.retrieval.eligible_source_ids` is empty as of
    ``as_of`` (every declared source is expired, non-``approved``, or
    non-``current``), no question can be answered and the whole run abstains with
    ``stale_evidence``. Any other catalog defect is left to the accepted gate,
    which raises ``CatalogRejectedError``; a malformed passage set or an unknown
    ``source_id`` raises ``PassageSetError``.
    """

    if _declares_sources(catalog_document) and not eligible_source_ids(
        catalog_document, as_of
    ):
        return Abstention(
            reason="stale_evidence",
            issues=(
                GroundingIssue(
                    "stale_corpus",
                    "no catalog source is eligible as of the given date "
                    "(expired, non-approved, or non-current)",
                ),
            ),
        )
    return Retriever.from_documents(catalog_document, passage_document, as_of, active_campaign)


def answer_or_abstain(
    question: str,
    corpus: Union[Retriever, Abstention],
    *,
    k: int = DEFAULT_K,
    max_claims: int = 2,
    land_scope: str = "general",
    as_of: Optional[date],
    generator: Optional[GroundingGenerator] = None,
) -> Union[Answered, Abstention]:
    """Decide between the accepted grounded answer and one abstention.

    ``corpus`` is what :func:`prepare_corpus` returned. A corpus-level
    :class:`Abstention` (a stale corpus) is returned unchanged for every
    question. Otherwise the pre-checks run on the ranked candidates the accepted
    retriever returns, and the accepted :func:`generate_grounded_answer` performs
    the drafting and verification. An invalid ``land_scope`` is a programming
    error and raises ``ValueError``.
    """

    if land_scope not in LAND_SCOPES:
        raise ValueError("land_scope must be one of: {}".format(", ".join(LAND_SCOPES)))
    if isinstance(corpus, Abstention):
        return corpus
    if not isinstance(corpus, Retriever):
        raise ValueError("corpus must be a Retriever or a corpus-level Abstention")

    if not isinstance(question, str) or not question.strip():
        return Abstention(
            reason="invalid_question",
            generation_reason="invalid_question",
            issues=(
                GroundingIssue("blank_question", "question must be a non-blank string"),
            ),
        )
    if len(question) > MAX_QUESTION_CHARS:
        return Abstention(
            reason="invalid_question",
            generation_reason="invalid_question",
            issues=(
                GroundingIssue(
                    "question_too_long",
                    "question exceeds {} characters".format(MAX_QUESTION_CHARS),
                ),
            ),
        )

    candidates = corpus.search(question, k=k)
    if not candidates:
        return Abstention(reason="no_evidence", generation_reason="no_candidates")

    if has_unsupported_presupposition(question, candidates):
        return Abstention(
            reason="false_premise",
            issues=(
                GroundingIssue(
                    "unconfirmed_presupposition",
                    "the question presupposes an instrument or article that no "
                    "retrieved candidate contains",
                ),
            ),
        )

    conflict = find_unit_conflict(candidates, max_claims=max_claims)
    if conflict is not None:
        return Abstention(
            reason="conflicting_evidence",
            issues=(
                GroundingIssue(
                    "unit_conflict",
                    "two critical candidates state different values for the unit "
                    "'{}'".format(conflict.unit),
                ),
            ),
        )

    result = generate_grounded_answer(
        question,
        corpus,
        k=k,
        max_claims=max_claims,
        land_scope=land_scope,
        as_of=as_of,
        generator=generator,
    )
    if isinstance(result, Answered):
        return result
    return abstention_from_generation(result)


def abstention_from_generation(result: NotAnswered) -> Abstention:
    """Map an accepted :class:`NotAnswered` result into this taxonomy.

    The original generation reason and its issue codes are preserved for
    traceability. An unrecognized reason fails closed to ``generation_error``.
    """

    if not isinstance(result, NotAnswered):
        raise ValueError("abstention_from_generation requires a NotAnswered result")
    return Abstention(
        reason=GENERATION_REASON_MAP.get(result.reason, "generation_error"),
        generation_reason=result.reason,
        issues=result.issues,
        claims=result.claims,
    )


def to_abstention_response(
    abstention: Abstention,
    *,
    land_scope: str = "general",
) -> Dict[str, Any]:
    """Assemble the accepted ``AskResponse`` payload for an abstention.

    The payload has exactly ``{status, answer, sources, land_scope,
    land_ids_to_choose}`` with ``status == "abstained"``, no sources, no land
    choices, and the pinned message. An unknown reason or scope raises
    ``ValueError`` rather than emitting anything.
    """

    if not isinstance(abstention, Abstention):
        raise ValueError("to_abstention_response requires an Abstention result")
    if abstention.reason not in ABSTENTION_MESSAGES:
        raise ValueError(
            "reason must be one of: {}".format(", ".join(ABSTENTION_REASONS))
        )
    if land_scope not in LAND_SCOPES:
        raise ValueError("land_scope must be one of: {}".format(", ".join(LAND_SCOPES)))

    message = abstention.message
    if not message.strip() or len(message) > MAX_ANSWER_CHARS:
        raise ValueError(
            "the pinned message must be non-blank and at most {} characters".format(
                MAX_ANSWER_CHARS
            )
        )
    return {
        "status": "abstained",
        "answer": message,
        "sources": [],
        "land_scope": land_scope,
        "land_ids_to_choose": [],
    }


def presupposed_identifiers(question: str) -> Tuple[str, ...]:
    """Return the normalized instrument/article references a question presupposes.

    Recognizes the documented instrument keywords (``real decreto``, ``rd``,
    ``decreto``, ``decreto ley``, ``ley``, ``orden``, ``reglamento``, ``norma``)
    with an optional ``N``, ``N/YYYY``, ``n.º N``, or ``número N`` identifier,
    plus ``artículo N``. Order is preserved and duplicates are removed.
    """

    text = normalize_text(question)
    if not text:
        return ()

    identifiers = []
    for match in _INSTRUMENT.finditer(text):
        keyword = match.group(1)
        number = match.group(2)
        if number is None:
            identifiers.append(keyword)
        else:
            identifiers.append("{} {}".format(keyword, _collapse_identifier(number)))
    for match in _ARTICLE.finditer(text):
        identifiers.append("articulo {}".format(_collapse_identifier(match.group(1))))
    return tuple(dict.fromkeys(identifiers))


def has_unsupported_presupposition(
    question: str,
    candidates: Sequence[RetrievedPassage],
) -> bool:
    """Return whether a presupposed identifier is absent from every candidate.

    The check is lexical and conservative: the identifier only has to appear
    (normalized) in a candidate's reviewed ``excerpt`` or its ``location``. It
    never asserts that an instrument is false; it only refuses to answer around a
    presupposition the retrieved evidence does not confirm.
    """

    identifiers = presupposed_identifiers(question)
    if not identifiers:
        return False
    haystack = " ".join(
        normalize_text("{} {}".format(candidate.excerpt, candidate.location))
        for candidate in candidates
    )
    return any(identifier not in haystack for identifier in identifiers)


def unit_values(text: str) -> Tuple[Tuple[str, str], ...]:
    """Return the ``(unit, canonical value)`` pairs documented in ``text``.

    Only the fixed :data:`CRITICAL_UNITS` list is recognized; any other unit is
    ignored. Values are canonicalized (thousands separators removed, decimal
    comma normalized) and the result is sorted, so repeated calls are
    deterministic.
    """

    normalized = normalize_text(text)
    if not normalized:
        return ()
    found: Dict[Tuple[str, str], None] = {}
    for match in _UNIT_VALUE.finditer(normalized):
        unit = _UNIT_ALIASES.get(match.group(2))
        value = _canonical_number(match.group(1))
        if unit is None or not value:
            continue
        found[(unit, value)] = None
    return tuple(sorted(found))


def find_unit_conflict(
    candidates: Sequence[RetrievedPassage],
    *,
    max_claims: int = 2,
) -> Optional[UnitConflict]:
    """Return the first unit conflict among the critical candidates, if any.

    Only the citation window (the first ``max_claims`` candidates) is inspected,
    and only ``critical`` candidates contribute. A conflict requires the same
    documented unit to carry two different canonical values from two different
    candidates, so two critical passages about different units (a deadline in
    ``días`` and an amount in ``euros``) are not a conflict.
    """

    window = tuple(candidates)[: max(0, max_claims)]
    occurrences_by_unit: Dict[str, Dict[str, FrozenSet[str]]] = {}
    for candidate in window:
        if not candidate.critical:
            continue
        for unit, value in unit_values(candidate.excerpt):
            values = occurrences_by_unit.setdefault(unit, {})
            values[value] = values.get(value, frozenset()) | {candidate.passage_id}

    for unit in CRITICAL_UNITS:
        values = occurrences_by_unit.get(unit)
        if not values or len(values) < 2:
            continue
        occurrences = [
            (value, passage_id)
            for value, passage_ids in values.items()
            for passage_id in passage_ids
        ]
        for index, (value, passage_id) in enumerate(occurrences):
            for other_value, other_passage_id in occurrences[index + 1 :]:
                if value != other_value and passage_id != other_passage_id:
                    return UnitConflict(unit=unit, values=tuple(sorted(values)))
    return None


def _declares_sources(catalog_document: Any) -> bool:
    """Return whether a structurally recognizable catalog declares any source."""

    if not isinstance(catalog_document, dict):
        return False
    sources = catalog_document.get("sources")
    return (
        isinstance(sources, list)
        and len(sources) > 0
        and all(isinstance(source, dict) for source in sources)
    )


def _collapse_identifier(number: str) -> str:
    """Collapse the whitespace a ``N / YYYY`` identifier may contain."""

    return re.sub(r"\s+", "", number)


def _canonical_number(raw: str) -> str:
    """Canonicalize one numeric token (thousands separators, decimal comma)."""

    digits = raw.strip().strip(".,")
    if not digits:
        return ""
    if "." in digits and "," in digits:
        decimal_separator = "." if digits.rfind(".") > digits.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        integer_part, _, fraction = digits.rpartition(decimal_separator)
        return "{}.{}".format(integer_part.replace(thousands_separator, ""), fraction)
    if "." in digits or "," in digits:
        separator = "." if "." in digits else ","
        groups = digits.split(separator)
        if (
            len(groups) > 1
            and len(groups[0]) <= 3
            and all(len(group) == 3 for group in groups[1:])
        ):
            return "".join(groups)
        return "{}.{}".format(groups[0], ".".join(groups[1:]))
    return digits
