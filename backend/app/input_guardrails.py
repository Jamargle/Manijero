"""Deterministic screen for a question, run by ``/ask`` before any retrieval.

:func:`screen_question` returns one reason code from :data:`SCREEN_REASONS`, or ``None``
when the question should go on to the grounded path. It uses word lists and patterns only:
no model, no network, no logging. It never returns, stores or logs the matched text.

Precedence is fixed: ``personal_data``, then ``prompt_injection``, then ``out_of_domain``.

Precision comes before recall. A missed case still reaches the grounded path, which abstains
on unsupported questions, while a false positive blocks a real farming question. So:

* Personal data patterns (DNI, NIE, company NIF, email, IBAN) run on the raw text after
  SIGPAC and cadastral references are masked, because those are land data and must never be
  screened. IDs are not check-letter validated: a typo of a real ID is still personal data.
  Phones are checked on the raw text with look-arounds that skip SIGPAC groups (``:`` or
  ``-`` between digits).
* Injection rules need a verb plus a target (never a bare word) and run on
  :func:`app.generation.normalize_text`.
* Out-of-domain needs an off-topic marker **and** no farming, PAC or land term.

Coverage is lexical, Spanish and English only; names and addresses are not screened.
"""

import re
from typing import Optional, Tuple

from app.generation import normalize_text

SCREEN_REASONS: Tuple[str, ...] = ("personal_data", "prompt_injection", "out_of_domain")

# -- personal data ---------------------------------------------------------------------

_SIGPAC = re.compile(r"(?<!\d)\d{1,5}(?:[:\-]\d{1,5}){2,}(?!\d)")
_CADASTRAL = re.compile(
    r"(?<![A-Za-z0-9])\d{7}[A-Za-z]{2}\d{4}[A-Za-z]\d{4}[A-Za-z]{2}(?![A-Za-z0-9])"
)
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_DNI = re.compile(
    r"(?<![\w.])(?:\d{8}|\d{2}\.\d{3}\.\d{3})"
    r"(?:[- ]?[" + _DNI_LETTERS + r"]|-?[" + _DNI_LETTERS.lower() + r"])(?![A-Za-z0-9])"
)
_NIE = re.compile(r"(?<!\w)[XYZxyz][- ]?\d{7}[- ]?[A-Za-z](?![A-Za-z0-9])")
_NIF = re.compile(
    r"(?<!\w)[ABCDEFGHJNPQRSUVWabcdefghjnpqrsuvw]\d{7}[0-9A-Ja-j](?![A-Za-z0-9])"
)
_PHONE = re.compile(
    r"(?<![\d:])(?<!\d[-.])(?:(?:\+|00)34 ?)?"
    r"(?:[6-9]\d{8}|[6-9]\d{2}([ .-])\d{3}\1\d{3}|[6-9]\d{2}([ .-])\d{2}\2\d{2}\2\d{2})"
    r"(?!\d|:|-\d|\.\d)"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_IBAN = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{4}){2,7}(?: ?[A-Za-z0-9]{1,4})?"
    r"(?![A-Za-z0-9])"
)
_MIN_IBAN_DIGITS = 10


def _has_personal_data(question: str) -> bool:
    if _PHONE.search(question):
        return True
    masked = _CADASTRAL.sub(" ", _SIGPAC.sub(" ", question))
    if _EMAIL.search(masked):
        return True
    if _DNI.search(masked) or _NIE.search(masked) or _NIF.search(masked):
        return True
    for match in _IBAN.finditer(masked):
        if sum(character.isdigit() for character in match.group()[4:]) >= _MIN_IBAN_DIGITS:
            return True
    return False


# -- prompt injection (normalized text) ---------------------------------------------------

_NOUNS = r"(?:instrucciones|reglas|indicaciones|ordenes|directrices|prompt|instructions|rules)"
_QUALIFIERS = r"(?:tus|las|todas|anteriores|previas|previous|prior|your|all|above|the|mis|el)"
_IGNORE = re.compile(
    r"\b(?:ignora|ignorar|ignores|olvida|olvidar|olvides|olvidate|omite|salta|saltate|"
    r"desobedece|ignore|forget|disregard)\b(?:\W+\w+){0,3}?\W+" + _QUALIFIERS
    + r"\b(?:\W+\w+){0,2}?\W+" + _NOUNS + r"\b"
)
_REVEAL = re.compile(
    r"\b(?:muestra|muestrame|ensename|dime|revela|revelame|repite|repiteme|escribe|imprime|"
    r"show|reveal|print|repeat|cuales son|cual es|what is|what are)\b(?:\W+\w+){0,3}?\W+"
    r"(?:tu prompt|tus instrucciones|instrucciones (?:del sistema|iniciales|internas|ocultas)|"
    r"mensaje del sistema|system prompt|your (?:system )?(?:prompt|instructions))\b"
)
_ROLE = re.compile(
    r"\ba partir de ahora (?:eres|seras|actua)\b|\bfinge (?:ser|que eres)\b|"
    r"\bhaz como si fueras\b|\bmodo (?:desarrollador|dios|sin restricciones)\b|"
    r"\bjailbreak\b|\byou are now\b|\bact as (?:an?|my) (?:unrestricted|different)\b|"
    r"\bpretend (?:to be|you are)\b"
)


def _is_injection(text: str) -> bool:
    return bool(_IGNORE.search(text) or _REVEAL.search(text) or _ROLE.search(text))


# -- out of domain (normalized text) ------------------------------------------------------

_DOMAIN = re.compile(
    r"\b(?:pac|ayudas?|subvencion\w*|solicitud\w*|tramit\w*|plazos?|campana|convocatoria\w*|"
    r"junta|consejeria|ministerio|oficina comarcal|cooperativa\w*|sigpac|catastro|catastral|"
    r"poligono\w*|parcela\w*|recinto\w*|finca\w*|terreno\w*|tierra\w*|hectarea\w*|olivo\w*|"
    r"olivar\w*|aceituna\w*|aceite|almazara\w*|cosecha\w*|poda\w*|riego|regadio|secano|"
    r"ecologic\w*|cultivo\w*|abono\w*|fertiliz\w*|fitosanitari\w*|tratamiento\w*|plaga\w*|"
    r"cuaderno de campo|condicionalidad|ecorregimen\w*|agricult\w*|agrari\w*|tractor\w*|"
    r"maquinaria|ganado|ganader\w*|olive|farm\w*|subsid\w*|grove)\b"
)
_OFF_TOPIC = re.compile(
    r"\b(?:futbol|liga|partido de|baloncesto|receta\w*|cocinar|chiste\w*|poema\w*|cancion|"
    r"canciones|cuento\w*|pelicula\w*|serie de television|netflix|musica|programar|"
    r"programacion|python|javascript|deberes|loteria|apuesta\w*|quiniela\w*|bitcoin|cripto\w*|"
    r"horoscopo|viaje\w*|hotel\w*|vuelo\w*|cual es la capital de|quien gano|football|recipe\w*|"
    r"joke\w*|poem\w*|movie\w*|homework|lottery|horoscope)\b"
)


def _is_out_of_domain(text: str) -> bool:
    return bool(_OFF_TOPIC.search(text)) and not _DOMAIN.search(text)


def screen_question(question: str) -> Optional[str]:
    """Return the screening reason for ``question``, or ``None`` to answer it as usual."""

    if not isinstance(question, str) or not question.strip():
        return None
    if _has_personal_data(question):
        return "personal_data"
    text = normalize_text(question)
    if _is_injection(text):
        return "prompt_injection"
    if _is_out_of_domain(text):
        return "out_of_domain"
    return None
