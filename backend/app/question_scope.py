"""Code-owned list of question topics the reviewed corpus deliberately omits.

One :class:`ScopeTopic` per omission declared in ``knowledge/pac_coverage.md``
"Exclusiones" (mirrored in ``coverage.omissions`` of
``knowledge/pac_answer_eval.json``). :func:`out_of_scope_topic` is a pure,
lexical, accent-, case- and punctuation-insensitive check, so a question about
an omitted topic can abstain *before* retrieval can surface a nearby but
unrelated passage.

Patterns are written against normalized text (lowercase, no accents, every
non-alphanumeric character replaced by one space) and are deliberately personal
or topic phrasings, never bare words such as ``importe``, ``plazo``, or
``notificacion``, which also appear in in-scope questions. The check is
conservative in the other direction too: an unlisted paraphrase still reaches
retrieval. Standard library and ``app.generation.normalize_text`` only; no
legal fact, no copy, and no question text leaves this module.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from app.generation import normalize_text


@dataclass(frozen=True)
class ScopeTopic:
    """One declared omission, its abstention reason, and its question patterns."""

    omission: str
    reason: str
    patterns: Tuple[str, ...]


OUT_OF_SCOPE_TOPICS: Tuple[ScopeTopic, ...] = (
    ScopeTopic(
        "importes de ayudas",
        "unsafe_request",
        (
            r"importes? de (la |las |mi |mis )?ayudas?",
            r"importe por hectarea",
            r"cuantia de (la |las )?ayudas?",
            r"cuanto (dinero )?(voy a |me van a |se )?(cobr|pag|recib)\w*",
            r"euros por hectarea",
        ),
    ),
    ScopeTopic(
        "elegibilidad individual",
        "unsafe_request",
        (
            r"tengo derecho",
            r"(cumplo|reuno) (con )?(los )?requisitos",
            r"me corresponde\w* (la |una |alguna )?ayuda",
            r"ayuda\w* .* me corresponde",
            r"puedo cobrar",
            r"soy (agricultor activo|beneficiari)\w*",
        ),
    ),
    ScopeTopic(
        "notificaciones individuales",
        "unsafe_request",
        (
            r"mi expediente",
            r"(estado|situacion) de mi",
            r"me (han|ha) (enviado|notificado|pagado|ingresado|concedido|denegado|resuelto|llegado)",
            r"ya me (han|ha)",
        ),
    ),
    ScopeTopic(
        "reclamaciones y recursos",
        "no_evidence",
        (
            r"reclamacion\w*",
            r"reclamar",
            r"recurso (de|contra|contencioso)",
            r"recurr\w*",
            r"impugn\w*",
            r"interponer",
        ),
    ),
    ScopeTopic(
        "penalizaciones por mora",
        "no_evidence",
        (
            r"penaliz\w*",
            r"sancion\w*",
            r"recargo",
            r"fuera de plazo",
            r"presentacion tardia",
            r"(presento|entrego) .* tarde",
        ),
    ),
    ScopeTopic(
        "fuerza mayor",
        "no_evidence",
        (r"fuerza mayor", r"circunstancias excepcionales"),
    ),
    ScopeTopic(
        "adaptaciones por controles de monitorización",
        "no_evidence",
        (r"monitoriz\w*", r"control(es)? por satelite", r"satelite"),
    ),
    ScopeTopic(
        "otras campañas",
        "no_evidence",
        (
            r"campana (pasada|anterior|proxima|siguiente|que viene)",
            r"(pasada|anterior|proxima|siguiente) campana",
            r"ano (pasado|que viene)",
            r"proximo ano",
        ),
    ),
)

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_COMPILED = tuple(
    (topic, tuple(re.compile(r"\b" + pattern + r"\b") for pattern in topic.patterns))
    for topic in OUT_OF_SCOPE_TOPICS
)


def _scope_text(question: str) -> str:
    return " ".join(_NON_ALNUM.split(normalize_text(question))).strip()


def out_of_scope_topic(question: str) -> Optional[ScopeTopic]:
    """Return the first declared omission the question matches, else ``None``."""

    if not isinstance(question, str) or not question.strip():
        return None
    text = _scope_text(question)
    for topic, patterns in _COMPILED:
        if any(pattern.search(text) for pattern in patterns):
            return topic
    return None
