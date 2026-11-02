"""Code-owned deadline notices appended to a verified, grounded answer.

Two fixed Spanish sentences, never written by a model:

* ``EXPIRED``: the official deadline of a cited passage has already passed.
* ``COOPERATIVE``: the cooperative or entidad colaboradora may set an earlier date.

The only input is a cited passage's reviewed ``official_deadline`` (the inclusive
last day, ``YYYY-MM-DD``) and the injected UTC ``as_of`` date. Nothing here parses
dates from text or reads a clock. The module is stdlib-only so that both
``generation`` and ``gemini_generation`` can import it without a cycle.
"""

import re
import unicodedata
from datetime import date
from typing import Iterable, Optional, Tuple

COOPERATIVE = (
    "Tu cooperativa o entidad colaboradora puede tener una fecha anterior "
    "al plazo oficial: pregúntale primero."
)
EXPIRED_PREFIX = "El plazo oficial terminó el"
EXPIRED_TEMPLATE = EXPIRED_PREFIX + " {day} de {month} de {year}."

MONTHS: Tuple[str, ...] = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_marks).strip()


# Normalized (lowercase, no diacritics) text a generator must never contain.
CODE_OWNED_MARKERS: Tuple[str, ...] = (_normalize(COOPERATIVE), _normalize(EXPIRED_PREFIX))


def format_spanish_date(value: date) -> str:
    """Return ``15 de mayo de 2031``: no leading zero, lowercase month."""

    return "{} de {} de {}".format(value.day, MONTHS[value.month - 1], value.year)


def expired_sentence(deadline: date) -> str:
    return EXPIRED_TEMPLATE.format(
        day=deadline.day, month=MONTHS[deadline.month - 1], year=deadline.year
    )


def deadline_paragraph(passages: Iterable[object], as_of: Optional[date]) -> str:
    """Return the notice paragraph for the cited ``passages``, or ``""``.

    ``EXPIRED`` sentences (distinct dates, ascending) come first, then one
    ``COOPERATIVE``, joined by single spaces. A deadline has passed only when it
    is strictly before ``as_of``; with ``as_of`` ``None`` nothing has passed.
    """

    deadlines = set()
    for passage in passages:
        raw = getattr(passage, "official_deadline", None)
        if isinstance(raw, str):
            try:
                deadlines.add(date.fromisoformat(raw))
            except ValueError:
                continue
    if not deadlines:
        return ""
    sentences = [
        expired_sentence(deadline)
        for deadline in sorted(deadlines)
        if as_of is not None and deadline < as_of
    ]
    sentences.append(COOPERATIVE)
    return " ".join(sentences)
