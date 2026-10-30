"""Conservative redaction for opt-in product-improvement question/answer retention.

Redaction runs only on the retention path, after the answer has been produced, and never
changes what the person is shown. It is deliberately conservative: it prefers removing a
harmless value over keeping a personal one, and it is pattern-based, so it cannot
recognise every personal detail. Its known limits are documented in ``backend/README.md``
("Product-improvement retention") and must be part of the qualified privacy review.

What is replaced, with a fixed bracketed placeholder:

- e-mail addresses, web addresses, and phone numbers;
- Spanish DNI/NIE numbers, IBAN account numbers, and cadastral references;
- SIGPAC-style colon/dash-separated references and polígono/parcela/recinto numbers;
- any run of six or more digits;
- a person's name introduced as "me llamo …", "mi nombre es …" or "soy …" (capitalised);
- a capitalised name after a land word ("finca", "cortijo", "olivar", …), because a land
  name can be typed into a question even though the app never sends one;
- every land-context value that arrived with the request (opaque ids and municipalities),
  so retained text cannot carry the request's land context back in.

Every function is pure and standard-library only.
"""

from __future__ import annotations

import re
from typing import Iterable

PLACEHOLDER_EMAIL = "[correo]"
PLACEHOLDER_URL = "[enlace]"
PLACEHOLDER_PHONE = "[teléfono]"
PLACEHOLDER_DOCUMENT = "[documento]"
PLACEHOLDER_ACCOUNT = "[cuenta]"
PLACEHOLDER_REFERENCE = "[referencia]"
PLACEHOLDER_NUMBER = "[número]"
PLACEHOLDER_NAME = "[nombre]"
PLACEHOLDER_LAND_NAME = "[nombre del terreno]"
PLACEHOLDER_LAND = "[terreno]"
PLACEHOLDER_MUNICIPALITY = "[municipio]"

_UPPER = "A-ZÁÉÍÓÚÜÑ"
_WORD = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
_CAPITALISED = rf"[{_UPPER}][{_WORD}'’-]*"
_CAPITALISED_RUN = rf"{_CAPITALISED}(?:\s+(?:de\s+(?:la\s+|los\s+|las\s+)?|del\s+|la\s+|el\s+)?{_CAPITALISED})*"

# Order matters: the most specific identifiers are replaced before the generic digit rule.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE), PLACEHOLDER_EMAIL),
    (re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE), PLACEHOLDER_URL),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){4,7}(?:[ ]?[A-Z0-9]{1,4})?\b"), PLACEHOLDER_ACCOUNT),
    (re.compile(r"\b\d{7}[A-Z]{2}\d{4}[A-Z]\d{4}[A-Z]{2}\b", re.IGNORECASE), PLACEHOLDER_REFERENCE),
    (re.compile(r"\b[XYZ][ -]?\d{7}[ -]?[A-Z]\b", re.IGNORECASE), PLACEHOLDER_DOCUMENT),
    (re.compile(r"\b\d{8}[ -]?[A-Z]\b", re.IGNORECASE), PLACEHOLDER_DOCUMENT),
    (re.compile(r"\b\d{1,5}(?:\s*[:/-]\s*\d{1,6}){2,}\b"), PLACEHOLDER_REFERENCE),
    (
        re.compile(r"(?:(?:\+|00)\s?34[\s.-]?)?\b[6789]\d{2}(?:[\s.-]?\d{2,3}){2,3}\b"),
        PLACEHOLDER_PHONE,
    ),
    (re.compile(r"\d{6,}"), PLACEHOLDER_NUMBER),
)
_PARCEL_NUMBER = re.compile(
    r"\b(polígono|poligono|parcela|recinto|finca\s+registral)(\s+(?:n\.?º|nº|número|numero|num\.?)?\s*)(\d+)\b",
    re.IGNORECASE,
)
# The trigger words are case-insensitive; the name itself must be capitalised, so
# "soy agricultor" keeps its lowercase word.
_PERSON_NAME = re.compile(
    rf"\b((?i:me\s+llamo|mi\s+nombre\s+es|soy)\s+)({_CAPITALISED_RUN})",
)
_LAND_NAME = re.compile(
    rf"\b((?i:finca|fincas|cortijo|olivar|huerta|terreno|terrenos|parcela|haza|paraje|hacienda|tierra)"
    rf"\s+(?i:de\s+|del\s+|llamad[ao]\s+|que\s+se\s+llama\s+)?)"
    rf"({_CAPITALISED_RUN})",
)


class RedactionError(Exception):
    """Redaction could not be applied; the caller must not retain the text."""


def redact_text(text: str, land_values: Iterable[tuple[str, str]] = ()) -> str:
    """Return ``text`` with personal details and land-context values replaced.

    ``land_values`` pairs each request land-context value with its placeholder, for
    example ``("land-001", "[terreno]")``. Raises :class:`RedactionError` for a value
    that is not text, so a caller fails closed instead of retaining unredacted input.
    """

    if not isinstance(text, str):
        raise RedactionError("text_invalid")
    redacted = text
    # Land-context values first and longest first, so "Villanueva del Arzobispo" is not
    # partially replaced by a shorter value.
    for value, placeholder in sorted(land_values, key=lambda item: len(item[0]), reverse=True):
        if not isinstance(value, str) or not isinstance(placeholder, str):
            raise RedactionError("land_value_invalid")
        candidate = value.strip()
        if not candidate:
            continue
        redacted = re.sub(re.escape(candidate), placeholder, redacted, flags=re.IGNORECASE)
    for pattern, placeholder in _PATTERNS:
        redacted = pattern.sub(placeholder, redacted)
    redacted = _PARCEL_NUMBER.sub(lambda match: f"{match.group(1)}{match.group(2)}{PLACEHOLDER_NUMBER}", redacted)
    redacted = _PERSON_NAME.sub(lambda match: _keep_lowercase(match, PLACEHOLDER_NAME), redacted)
    redacted = _LAND_NAME.sub(lambda match: _keep_lowercase(match, PLACEHOLDER_LAND_NAME), redacted)
    return redacted


def land_context_values(land_context: dict) -> tuple[tuple[str, str], ...]:
    """Collect the request's land-context text values with their placeholders."""

    if not isinstance(land_context, dict):
        raise RedactionError("land_context_invalid")
    lands = land_context.get("lands", [])
    if not isinstance(lands, list):
        raise RedactionError("land_context_invalid")
    values: list[tuple[str, str]] = []
    for land in lands:
        if not isinstance(land, dict):
            raise RedactionError("land_context_invalid")
        land_id = land.get("id")
        if isinstance(land_id, str):
            values.append((land_id, PLACEHOLDER_LAND))
        municipality = land.get("municipality")
        if isinstance(municipality, str):
            values.append((municipality, PLACEHOLDER_MUNICIPALITY))
    return tuple(values)


def _keep_lowercase(match: re.Match[str], placeholder: str) -> str:
    """Replace the captured capitalised name, keeping the trigger words."""

    return f"{match.group(1)}{placeholder}"
