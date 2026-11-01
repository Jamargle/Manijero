"""Offline, code-controlled grounded answer generation.

Generation is the *write* side of the accepted source gate. It reads only the
ranked candidates that :class:`app.retrieval.Retriever` returns from reviewed
passages of approved catalog sources, and it is the authority on whether a draft
answer may be shown: code (not a model) selects the evidence, assigns the
citation markers, and re-checks every material claim before assembly.

The module is deliberately dependency-free and offline. It never reads the
catalog or the passage set itself, never re-implements eligibility, never calls
a model or the network, and never falls back to unreviewed content or model
knowledge. A rejected draft is discarded whole ("fail closed"); the pipeline
then returns a machine-readable :class:`NotAnswered` reason code, and
``safe_abstention`` owns the user-visible limitation and next step.

Durable rules:

* Draft citation markers mean candidate number ``n``, i.e.
  ``RetrievedPassage.rank``. After verification, emitted markers are dense
  response-local positions in the cited-source array.
* Every sentence of an ``answered`` draft must carry at least one marker.
* Every figure or date in a sentence must also appear in the text of the
  passage(s) that sentence cites.
* Every number word, month, day–month or full written date, and day, week,
  month, or year duration (with any ``hábiles``/``naturales`` qualifier) in a
  sentence must appear, in an equivalent written form, in the passage(s) that
  sentence cites (``numeric_fact_unsupported``). ``extract_figures`` stays
  digit-only, because the abstention and land-safety checks depend on it.
* For a passage flagged ``critical`` the sentence must be a literal substring of
  one of its cited ``critical`` excerpts after whitespace/case/diacritic
  normalization, so a critical figure is copied, never paraphrased.
* A sentence asserting the person's legal status is rejected.
* The orientative notice is added by code, never produced by a generator, and
  neither pinned string contains a digit or a date.

The checks are lexical by design: figure presence is not entailment, the
eligibility check is a phrase list, and semantic grounding and conflict
detection are explicitly deferred to ``safe_abstention`` and a later judge.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, FrozenSet, List, Optional, Protocol, Sequence, Tuple, Union

from app.retrieval import (
    DEFAULT_K,
    RetrievedPassage,
    Retriever,
)

# The accepted ``AskResponse`` bound (``contracts/openapi.yaml``).
MAX_ANSWER_CHARS = 1200
# The accepted ``AskRequest`` bound (``contracts/openapi.yaml``).
MAX_QUESTION_CHARS = 2000

LEAD_IN = "Según los documentos oficiales revisados:"
NOTICE = (
    "Información orientativa basada en documentos oficiales. "
    "No sustituye el asesoramiento profesional."
)

LAND_SCOPES = ("general", "all_active", "selected")

# Exactly the seven keys of the accepted ``AnswerSource`` schema. The
# retrieval-local fields (passage_id, source_id, applicability, critical, score,
# rank) never cross into the response payload.
ANSWER_SOURCE_KEYS: Tuple[str, ...] = (
    "title",
    "issuing_body",
    "url",
    "location",
    "published_or_updated_on",
    "verified_on",
    "excerpt",
)

# Starter Spanish phrase list for the "no personalized legal advice" rule. It is
# intentionally short, tested, and fail-closed: a sentence matching any phrase
# is rejected outright rather than weakened.
ELIGIBILITY_PHRASES: Tuple[str, ...] = (
    "tienes derecho a",
    "tiene derecho a",
    "puedes cobrar",
    "puede cobrar",
    "cumples los requisitos",
    "cumple los requisitos",
    "vas a recibir",
    "te corresponde cobrar",
)

# Issue codes that describe a policy violation rather than a grounding failure.
POLICY_ISSUE_CODES: FrozenSet[str] = frozenset({"eligibility_claim"})

# Issue codes that mean a draft produced unsupported output. ``answer_too_long``
# is a size failure and ``generator_abstained`` is the abstention handoff, so
# neither is listed here.
GROUNDING_FAILURE_CODES: FrozenSet[str] = frozenset(
    {
        "incoherent_draft",
        "empty_answer",
        "no_markers",
        "unknown_marker",
        "marker_mismatch",
        "uncited_sentence",
        "figure_unsupported",
        "numeric_fact_unsupported",
        "critical_not_literal",
    }
)

NUMERIC_FACT_DETAIL = (
    "a number, date, or deadline in the claim is absent from the cited passage(s)"
)

_MARKER = re.compile(r"\[(\d+)\]")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_FIGURE = re.compile(r"\d+(?:[.,]\d+)*\s?%?")


@dataclass(frozen=True)
class DraftAnswer:
    """The generator-facing draft, mirroring ``MasterPlanV3`` section 8.1.

    ``status``, ``answer`` and ``source_markers`` line up with the projected
    ``{"status", "answer", "sources"}`` JSON, so a future model adapter can
    produce this shape without a redesign. ``source_markers`` are candidate
    numbers, not text: a generator declares which candidates it used.
    """

    status: str
    answer: str
    source_markers: Tuple[int, ...] = ()


@dataclass(frozen=True)
class GroundingIssue:
    """One rejected-rule violation.

    ``detail`` names codes, candidate numbers, and rule names only: it never
    contains question text, an excerpt, or any other content (privacy, and
    consistent with the catalog and retrieval modules).
    """

    code: str
    detail: str

    def __str__(self) -> str:
        return "{}: {}".format(self.code, self.detail)


@dataclass(frozen=True)
class ClaimVerdict:
    """One material claim (a sentence) plus its cited candidate numbers."""

    text: str
    markers: Tuple[int, ...]
    ok: bool
    issues: Tuple[GroundingIssue, ...] = ()


@dataclass(frozen=True)
class GroundingReport:
    """The verifier verdict for one draft, with per-claim detail."""

    ok: bool
    issues: Tuple[GroundingIssue, ...]
    claims: Tuple[ClaimVerdict, ...]

    def codes(self) -> Tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


@dataclass(frozen=True)
class Answered:
    """A verified, assembled answer plus the candidates it cites."""

    answer: str
    claims: Tuple[ClaimVerdict, ...]
    sources: Tuple[RetrievedPassage, ...]
    land_scope: str = "general"
    cited_markers: Tuple[int, ...] = ()


@dataclass(frozen=True)
class NotAnswered:
    """A machine-readable reason why no answer was assembled.

    ``safe_abstention`` consumes the reason code and owns the copy and the next
    step; this feature never emits user-facing abstention text. ``claims``
    carries the per-sentence verdicts when a draft was verified and rejected, so
    a caller can report exactly which claim failed. No claim text from a
    rejected draft is ever emitted as an answer.
    """

    reason: str
    issues: Tuple[GroundingIssue, ...] = ()
    claims: Tuple[ClaimVerdict, ...] = ()

    def codes(self) -> Tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


class GroundingGenerator(Protocol):
    """The seam between evidence and drafting.

    The code-composed :class:`ExtractiveGroundingGenerator` is the only enabled
    implementation today. The gated model adapter
    (:class:`app.gemini_generation.GatedGeminiGenerator`) implements this protocol,
    verifies its own draft and falls back to the extractive draft otherwise; it has
    no transport in this repository. Whatever draft is returned is passed through the
    same :func:`verify_draft` again, so a model can never introduce a fact.
    """

    def generate(
        self,
        question: str,
        numbered_candidates: Sequence[Tuple[int, RetrievedPassage]],
        *,
        as_of: Optional[date],
    ) -> DraftAnswer:
        ...


@dataclass(frozen=True)
class ExtractiveGroundingGenerator:
    """The default, deterministic, offline generator: no clock, no model.

    For the top ``max_claims`` candidates in rank order it emits one claim per
    candidate whose text is the candidate's reviewed ``excerpt`` followed by its
    marker. The text is copied verbatim, so the figure/date and critical
    extractive checks hold by construction.
    """

    max_claims: int = 2

    def generate(
        self,
        question: str,
        numbered_candidates: Sequence[Tuple[int, RetrievedPassage]],
        *,
        as_of: Optional[date] = None,
    ) -> DraftAnswer:
        limit = self.max_claims if self.max_claims > 0 else 0
        claims: List[str] = []
        markers: List[int] = []
        for rank, passage in numbered_candidates[:limit]:
            claims.append("{} [{}]".format(passage.excerpt.strip(), rank))
            markers.append(rank)
        if not claims:
            return DraftAnswer(status="abstained", answer="", source_markers=())
        # One claim per line: a reviewed excerpt need not end with a terminal
        # mark, and joining with a space would let the claim splitter merge two
        # candidates into one sentence (and attach another passage's rules to
        # the first claim). The assembled user-facing answer still joins the
        # verified claims with a space.
        return DraftAnswer(
            status="answered",
            answer="\n".join(claims),
            source_markers=tuple(markers),
        )


def normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, and collapse whitespace for comparison."""

    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_marks).strip()


def split_sentences(text: str) -> Tuple[str, ...]:
    """Split text into claims, keeping a trailing marker with its claim.

    A terminal mark (``.!?``) ends a claim: a citation marker follows the claim
    it cites (``... fin. [1]``), so a marker immediately after terminal
    punctuation is attached to the preceding claim instead of starting a new
    one. A line break is always a claim boundary, because the code-composed
    extractive generator emits one claim per line: a reviewed excerpt need not
    end with a terminal mark, and joining two excerpts on one line would merge
    them into a single claim that borrows the other passage's critical and
    figure rules.
    """

    if not isinstance(text, str):
        return ()
    sentences: List[str] = []
    for line in text.splitlines():
        sentences.extend(_split_line(line))
    return tuple(sentence for sentence in sentences if sentence)


def _split_line(text: str) -> Tuple[str, ...]:
    """Split one line into claims at terminal punctuation."""

    source = text.strip()
    if not source:
        return ()

    sentences: List[str] = []
    start = 0
    index = 0
    length = len(source)
    while index < length:
        if source[index] in ".!?":
            cursor = index + 1
            while True:
                probe = cursor
                while probe < length and source[probe] in " \t\n":
                    probe += 1
                marker = _MARKER.match(source, probe)
                if marker is None:
                    break
                cursor = marker.end()
            if cursor >= length:
                sentences.append(source[start:cursor].strip(" \t\n"))
                start = cursor
                index = cursor
                continue
            if source[cursor] in " \t\n":
                sentences.append(source[start:cursor].strip(" \t\n"))
                probe = cursor
                while probe < length and source[probe] in " \t\n":
                    probe += 1
                start = probe
                index = probe
                continue
        index += 1

    if start < length:
        tail = source[start:].strip(" \t\n")
        if tail:
            sentences.append(tail)
    return tuple(sentence for sentence in sentences if sentence)


def inline_markers(text: str) -> Tuple[int, ...]:
    """Return the ``[n]`` candidate numbers found in ``text``, in order."""

    if not isinstance(text, str):
        return ()
    return tuple(int(match.group(1)) for match in _MARKER.finditer(text))


def strip_markers(text: str) -> str:
    """Remove citation markers without gluing words together."""

    if not isinstance(text, str):
        return ""
    without_markers = _MARKER.sub(" ", text)
    without_markers = re.sub(r"\s+([.,;:!?])", r"\1", without_markers)
    return re.sub(r"\s+", " ", without_markers).strip()


def _canonical_figure(token: str) -> str:
    """Canonicalize one numeric token (thousands separators, decimal comma)."""

    token = token.strip()
    percent = token.endswith("%")
    digits = token[:-1].strip() if percent else token
    if "." in digits and "," in digits:
        decimal_separator = "." if digits.rfind(".") > digits.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        integer_part, _, fraction = digits.rpartition(decimal_separator)
        canonical = "{}.{}".format(integer_part.replace(thousands_separator, ""), fraction)
    elif "." in digits or "," in digits:
        separator = "." if "." in digits else ","
        groups = digits.split(separator)
        if (
            len(groups) > 1
            and len(groups[0]) <= 3
            and all(len(group) == 3 for group in groups[1:])
        ):
            canonical = "".join(groups)
        else:
            canonical = "{}.{}".format(groups[0], ".".join(groups[1:]))
    else:
        canonical = digits
    return canonical + ("%" if percent else "")


def extract_figures(text: str) -> FrozenSet[str]:
    """Return the normalized figures and dates that appear in ``text``.

    Dates are recognized in ISO (``2031-01-01``) and day/month/year
    (``01/01/2031``) form and normalized to ISO. Numbers accept a decimal comma
    or point, thousands separators, and a trailing percent sign.
    """

    if not isinstance(text, str) or not text:
        return frozenset()

    figures: Dict[str, None] = {}
    for match in _ISO_DATE.finditer(text):
        year, month, day = match.groups()
        figures[_canonical_date(year, month, day)] = None
    for match in _SLASH_DATE.finditer(text):
        day, month, year = match.groups()
        figures[_canonical_date(year, month, day)] = None
    for match in _FIGURE.finditer(text):
        figures[_canonical_figure(match.group(0))] = None
    return frozenset(figures)


def _canonical_date(year: str, month: str, day: str) -> str:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return "{}-{}-{}".format(year, month, day)


# --- numeric facts in words, months, and durations ---------------------------
#
# Closed Spanish vocabulary in ``normalize_text`` spelling (lowercase, no
# diacritics), so "dieciséis" and "dieciseis" match and "año" reads "ano".

_UNIT_WORDS: Dict[str, int] = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
}
# ``un/una/uno`` alone is usually an article ("una vez", "un plazo"): it counts
# only as a duration's number or as a day.
_ARTICLE_WORDS: FrozenSet[str] = frozenset({"un", "una", "uno"})
_SMALL_WORDS: Dict[str, int] = {
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiun": 21,
    "veintiuna": 21,
    "veintiuno": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
}
_TENS_WORDS: Dict[str, int] = {
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
}
_HUNDRED_WORDS: Dict[str, int] = {
    "cien": 100,
    "ciento": 100,
    "doscientos": 200,
    "doscientas": 200,
    "trescientos": 300,
    "trescientas": 300,
    "cuatrocientos": 400,
    "cuatrocientas": 400,
    "quinientos": 500,
    "quinientas": 500,
    "seiscientos": 600,
    "seiscientas": 600,
    "setecientos": 700,
    "setecientas": 700,
    "ochocientos": 800,
    "ochocientas": 800,
    "novecientos": 900,
    "novecientas": 900,
}
_NUMBER_WORDS: FrozenSet[str] = frozenset(
    {"cero", "mil", *_UNIT_WORDS, *_SMALL_WORDS, *_TENS_WORDS, *_HUNDRED_WORDS}
)
_MONTHS: Dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_DURATION_UNITS: Dict[str, str] = {
    "dia": "dia",
    "dias": "dia",
    "semana": "semana",
    "semanas": "semana",
    "mes": "mes",
    "meses": "mes",
    "ano": "ano",
    "anos": "ano",
}
# Only a day count takes a qualifier.
_DAY_QUALIFIERS: Dict[str, str] = {
    "habil": "habiles",
    "habiles": "habiles",
    "natural": "naturales",
    "naturales": "naturales",
}

# One token of normalized text: a parenthetical digit restatement "(15)", a digit
# number with an optional ordinal mark ("1.º" normalizes to "1.o"), a word, or a
# single punctuation character, which ends any number-word run.
_NUMERIC_TOKEN = re.compile(
    r"(?P<paren>\(\s*\d+(?:[.,]\d+)*\s*\))"
    r"|(?P<digits>\d+(?:[.,]\d+)*)(?P<ordinal>\.?o(?![a-z0-9]))?"
    r"|(?P<word>[a-z]+)"
    r"|(?P<other>\S)"
)
_YEAR = re.compile(r"\d{4}")


@dataclass(frozen=True)
class _Token:
    kind: str  # "paren", "digits", "word", or "other"
    text: str
    ordinal: bool = False


def _numeric_tokens(normalized: str) -> Tuple[_Token, ...]:
    tokens: List[_Token] = []
    for match in _NUMERIC_TOKEN.finditer(normalized):
        if match.group("digits") is not None:
            ordinal = match.group("ordinal") is not None
            tokens.append(_Token("digits", match.group("digits"), ordinal))
        else:
            tokens.append(_Token(match.lastgroup or "other", match.group(0)))
    return tuple(tokens)


def _word_at(tokens: Sequence[_Token], index: int) -> str:
    if 0 <= index < len(tokens) and tokens[index].kind == "word":
        return tokens[index].text
    return ""


def _canonical_value(token: str) -> str:
    """Canonicalize a digit number like :func:`_canonical_figure`, without leading zeros."""

    canonical = _canonical_figure(token)
    percent = canonical.endswith("%")
    core = canonical[:-1] if percent else canonical
    if core.isdigit():
        core = str(int(core))
    return core + ("%" if percent else "")


def _number_run_end(tokens: Sequence[_Token], start: int) -> int:
    """Return the end of the maximal number-word run starting at ``start``.

    ``y`` joins the run only between a tens word and a unit ("treinta y uno").
    """

    index = start
    while index < len(tokens):
        word = _word_at(tokens, index)
        if word in _NUMBER_WORDS:
            index += 1
        elif (
            word == "y"
            and _word_at(tokens, index - 1) in _TENS_WORDS
            and _word_at(tokens, index + 1) in _UNIT_WORDS
        ):
            index += 1
        else:
            break
    return index


def _parse_below_thousand(words: Sequence[str]) -> Optional[int]:
    """Parse 1–999 written in words, or return ``None`` for an invalid run."""

    index = 0
    total = 0
    if index < len(words) and words[index] in _HUNDRED_WORDS:
        hundred = words[index]
        total = _HUNDRED_WORDS[hundred]
        index += 1
        if hundred == "cien" and index < len(words):
            return None
        if hundred == "ciento" and index == len(words):
            return None
    if index < len(words):
        word = words[index]
        if word in _TENS_WORDS:
            total += _TENS_WORDS[word]
            index += 1
            if index < len(words) and words[index] == "y":
                if index + 1 < len(words) and words[index + 1] in _UNIT_WORDS:
                    total += _UNIT_WORDS[words[index + 1]]
                    index += 2
                else:
                    return None
        elif word in _SMALL_WORDS:
            total += _SMALL_WORDS[word]
            index += 1
        elif word in _UNIT_WORDS:
            total += _UNIT_WORDS[word]
            index += 1
    if index != len(words) or total == 0:
        return None
    return total


def _parse_cardinal(words: Sequence[str]) -> Optional[int]:
    """Parse a Spanish cardinal from 0 to 999 999, or return ``None``."""

    if list(words) == ["cero"]:
        return 0
    if "mil" not in words:
        return _parse_below_thousand(words)
    if list(words).count("mil") > 1:
        return None
    at = list(words).index("mil")
    head, tail = words[:at], words[at + 1 :]
    thousands = _parse_below_thousand(head) if head else 1
    if thousands is None or (head and thousands == 1):
        return None
    rest = _parse_below_thousand(tail) if tail else 0
    if rest is None:
        return None
    return thousands * 1000 + rest


def _read_number(
    tokens: Sequence[_Token],
    end: int,
    value: Optional[str],
    facts: Dict[str, None],
    *,
    as_duration: bool,
    as_free: bool,
    free_fact: Optional[str],
) -> int:
    """Record the fact a number ending at ``end`` states; return the next index.

    A day–month (and full date) wins, then a duration, then a percent, then a
    free-standing number fact.
    """

    month = _MONTHS.get(_word_at(tokens, end + 1))
    if (
        value is not None
        and value.isdigit()
        and 1 <= int(value) <= 31
        and _word_at(tokens, end) == "de"
        and month is not None
    ):
        day = int(value)
        facts["m:{}".format(month)] = None
        facts["dm:{}-{}".format(day, month)] = None
        after = end + 2
        if (
            _word_at(tokens, after) in ("de", "del")
            and after + 1 < len(tokens)
            and tokens[after + 1].kind == "digits"
            and _YEAR.fullmatch(tokens[after + 1].text)
        ):
            facts[
                "d:" + _canonical_date(
                    tokens[after + 1].text, "{:02d}".format(month), "{:02d}".format(day)
                )
            ] = None
            return after + 2
        return after

    if value is not None and as_duration:
        index = end
        if index < len(tokens) and tokens[index].kind == "paren":
            index += 1
        unit = _DURATION_UNITS.get(_word_at(tokens, index))
        if unit is not None:
            fact = "dur:{}:{}".format(value, unit)
            index += 1
            qualifier = _DAY_QUALIFIERS.get(_word_at(tokens, index))
            if unit == "dia" and qualifier is not None:
                fact += ":" + qualifier
                index += 1
            facts[fact] = None
            return index

    if not as_free:
        return end
    percent = _word_at(tokens, end) == "por" and _word_at(tokens, end + 1) == "ciento"
    if value is not None and percent:
        facts["n:{}%".format(value)] = None
        return end + 2
    if free_fact is not None:
        facts[free_fact] = None
    return end


def _read_numeric_fact(tokens: Sequence[_Token], index: int, facts: Dict[str, None]) -> int:
    """Record the fact starting at ``index``, if any; return the next index."""

    token = tokens[index]
    if token.kind == "digits":
        # A bare digit figure is the digit rule's job; here digits only anchor a
        # day, a duration, or a percent.
        return _read_number(
            tokens,
            index + 1,
            _canonical_value(token.text),
            facts,
            as_duration=not token.ordinal,
            as_free=not token.ordinal,
            free_fact=None,
        )
    if token.kind != "word":
        return index + 1
    word = token.text
    if word == "por" and _word_at(tokens, index + 1) == "ciento":
        return index + 2
    if word in _MONTHS:
        facts["m:{}".format(_MONTHS[word])] = None
        return index + 1
    if word == "primero":
        return _read_number(
            tokens, index + 1, "1", facts, as_duration=False, as_free=False, free_fact=None
        )
    if word not in _NUMBER_WORDS:
        return index + 1
    end = _number_run_end(tokens, index)
    words = [run_token.text for run_token in tokens[index:end]]
    parsed = _parse_cardinal(words)
    value = None if parsed is None else str(parsed)
    article = len(words) == 1 and words[0] in _ARTICLE_WORDS
    return _read_number(
        tokens,
        end,
        value,
        facts,
        as_duration=True,
        as_free=not article,
        free_fact="w:" + " ".join(words) if value is None else "n:" + value,
    )


def extract_numeric_facts(text: str) -> FrozenSet[str]:
    """Return the numeric facts ``text`` states in words, month names, or durations.

    The text is read through :func:`normalize_text`. Each fact is a canonical
    token with a stable prefix:

    * ``n:<value>`` — a Spanish cardinal written in words (0–999 999), or
      ``n:<value>%`` for ``<number> por ciento`` (in digits or words). A bare
      digit figure is not a fact here: :func:`extract_figures` checks it.
    * ``w:<run>`` — a number-word run that is not a valid cardinal.
    * ``m:<month>`` — a month name (``enero`` … ``diciembre``, ``setiembre``).
    * ``dm:<day>-<month>`` — ``<day> de <month>``, the day in digits (an ordinal
      mark allowed), in words, or ``primero``.
    * ``d:<yyyy-mm-dd>`` — ``<day> de <month> de <yyyy>``.
    * ``dur:<value>:<unit>[:<qualifier>]`` — a number (digits, words, or
      ``un/una``, optionally restated as ``(15)``) followed by ``dia``,
      ``semana``, ``mes``, or ``ano``; a day count keeps ``habiles`` or
      ``naturales``.

    ``un/una/uno`` alone counts only as a duration's number or as a day, so
    articles ("una vez", "un plazo") state no fact.
    """

    if not isinstance(text, str) or not text:
        return frozenset()
    tokens = _numeric_tokens(normalize_text(text))
    facts: Dict[str, None] = {}
    index = 0
    while index < len(tokens):
        index = _read_numeric_fact(tokens, index, facts)
    return frozenset(facts)


def _numeric_support(passages: Sequence[RetrievedPassage]) -> FrozenSet[str]:
    """Return the numeric facts the cited ``passages`` support, in any written form.

    That is every :func:`extract_numeric_facts` token, an ``n:`` token for each
    non-date digit figure, and the month, day–month, and full-date tokens of each
    ISO or ``d/m/yyyy`` date.
    """

    support: Dict[str, None] = {}
    for passage in passages:
        excerpt = passage.excerpt if isinstance(passage.excerpt, str) else ""
        support.update(dict.fromkeys(extract_numeric_facts(excerpt)))
        for figure in extract_figures(excerpt):
            if "-" not in figure:
                support["n:" + _canonical_value(figure)] = None
        dates = [match.groups() for match in _ISO_DATE.finditer(excerpt)] + [
            tuple(reversed(match.groups())) for match in _SLASH_DATE.finditer(excerpt)
        ]
        for year, month, day in dates:
            support["m:{}".format(int(month))] = None
            support["dm:{}-{}".format(int(day), int(month))] = None
            support["d:" + _canonical_date(year, month.zfill(2), day.zfill(2))] = None
    return frozenset(support)


_NORMALIZED_ELIGIBILITY_PHRASES: Tuple[str, ...] = tuple(
    normalize_text(phrase) for phrase in ELIGIBILITY_PHRASES
)


def contains_eligibility_claim(text: str) -> bool:
    """Return whether ``text`` asserts the person's legal status.

    Matching is on whitespace/punctuation boundaries after normalization, so
    ``tienes derecho a`` matches while ``derecho al`` does not. A negation still
    matches and is still rejected: the phrase list fails closed.
    """

    normalized = normalize_text(text)
    if not normalized:
        return False
    padded = " {} ".format(normalized)
    return any(
        " {} ".format(phrase) in padded for phrase in _NORMALIZED_ELIGIBILITY_PHRASES
    )


def is_literal_substring(claim: str, excerpt: str) -> bool:
    """Return whether ``claim`` is a literal substring of ``excerpt`` after normalization."""

    normalized_claim = normalize_text(claim)
    if not normalized_claim:
        return False
    return normalized_claim in normalize_text(excerpt)


def verify_draft(
    draft: DraftAnswer,
    numbered_candidates: Sequence[Tuple[int, RetrievedPassage]],
) -> GroundingReport:
    """Apply every grounding rule to one draft and return the verdict.

    The rules are applied to every draft whatever produced it. An empty
    candidate sequence cannot reach here: the pipeline returns ``no_candidates``
    before drafting, so ``unknown_marker`` is the only way a marker can fail.
    """

    passages_by_rank = {rank: passage for rank, passage in numbered_candidates}
    ranks = frozenset(passages_by_rank)

    if not isinstance(draft, DraftAnswer):
        return GroundingReport(
            ok=False,
            issues=(GroundingIssue("incoherent_draft", "draft must be a DraftAnswer"),),
            claims=(),
        )

    if draft.status == "abstained":
        return GroundingReport(
            ok=False,
            issues=(
                GroundingIssue(
                    "generator_abstained",
                    "the generator abstained; its copy is discarded",
                ),
            ),
            claims=(),
        )
    if draft.status != "answered":
        return GroundingReport(
            ok=False,
            issues=(GroundingIssue("incoherent_draft", "status must be 'answered'"),),
            claims=(),
        )

    answer = draft.answer if isinstance(draft.answer, str) else ""
    if not answer.strip():
        return GroundingReport(
            ok=False,
            issues=(GroundingIssue("empty_answer", "answer must be non-blank"),),
            claims=(),
        )

    issues: List[GroundingIssue] = []

    markers = inline_markers(answer)
    if not markers:
        issues.append(
            GroundingIssue("no_markers", "the answer has no [n] citation marker")
        )
    unknown = tuple(sorted({marker for marker in markers if marker not in ranks}))
    if unknown:
        issues.append(
            GroundingIssue(
                "unknown_marker",
                "cites candidate number(s) outside the retrieved set: {}".format(
                    ", ".join(str(marker) for marker in unknown)
                ),
            )
        )
    declared = tuple(sorted(set(draft.source_markers)))
    if declared != tuple(sorted(set(markers))):
        issues.append(
            GroundingIssue(
                "marker_mismatch",
                "declared source_markers do not match the inline markers",
            )
        )

    claims: List[ClaimVerdict] = []
    for sentence in split_sentences(answer):
        sentence_markers = inline_markers(sentence)
        text = strip_markers(sentence)
        claim_issues: List[GroundingIssue] = []

        if not text:
            claim_issues.append(
                GroundingIssue("empty_answer", "a sentence has no text besides its markers")
            )
        if not sentence_markers:
            claim_issues.append(
                GroundingIssue("uncited_sentence", "a sentence carries no citation marker")
            )
        else:
            cited = [
                passages_by_rank[marker]
                for marker in sentence_markers
                if marker in passages_by_rank
            ]
            if cited:
                supported: FrozenSet[str] = frozenset().union(
                    *(extract_figures(passage.excerpt) for passage in cited)
                )
                unsupported = tuple(sorted(extract_figures(text) - supported))
                if unsupported:
                    claim_issues.append(
                        GroundingIssue(
                            "figure_unsupported",
                            "a figure or date in the claim is absent from the cited passage(s)",
                        )
                    )
                elif extract_numeric_facts(text) - _numeric_support(cited):
                    # At most one numeric code per claim: the digit rule wins.
                    claim_issues.append(
                        GroundingIssue("numeric_fact_unsupported", NUMERIC_FACT_DETAIL)
                    )
                critical = [passage for passage in cited if passage.critical]
                if critical and not any(
                    is_literal_substring(text, passage.excerpt) for passage in critical
                ):
                    claim_issues.append(
                        GroundingIssue(
                            "critical_not_literal",
                            "a critical claim must be a literal excerpt of its source",
                        )
                    )

        if contains_eligibility_claim(text):
            claim_issues.append(
                GroundingIssue(
                    "eligibility_claim",
                    "an answer claim must not assert the person's legal status",
                )
            )

        claims.append(
            ClaimVerdict(
                text=text,
                markers=sentence_markers,
                ok=not claim_issues,
                issues=tuple(claim_issues),
            )
        )
        issues.extend(claim_issues)

    if not claims:
        issues.append(GroundingIssue("empty_answer", "answer has no verifiable claim"))
    elif len(_assemble_claims((claims[0],))) > MAX_ANSWER_CHARS:
        issues.append(
            GroundingIssue(
                "answer_too_long",
                "the notice plus one claim exceeds {} characters".format(MAX_ANSWER_CHARS),
            )
        )

    return GroundingReport(ok=not issues, issues=tuple(issues), claims=tuple(claims))


def generate_grounded_answer(
    question: str,
    retriever: Retriever,
    *,
    k: int = DEFAULT_K,
    max_claims: int = 2,
    land_scope: str = "general",
    as_of: Optional[date],
    generator: Optional[GroundingGenerator] = None,
) -> Union[Answered, NotAnswered]:
    """Retrieve, draft, verify, and assemble one grounded answer.

    Returns an :class:`Answered` only when every material claim of the draft is
    traceable to a returned candidate; otherwise a :class:`NotAnswered` carrying
    a reason code and the issue codes. The question is never rewritten, and no
    text from a rejected draft is emitted.

    ``as_of`` is passed to the generator; the retriever already applied it to
    catalog eligibility. An invalid ``land_scope`` is a programming error and
    raises ``ValueError`` rather than being silently coerced.
    """

    if land_scope not in LAND_SCOPES:
        raise ValueError("land_scope must be one of: {}".format(", ".join(LAND_SCOPES)))

    if not isinstance(question, str) or not question.strip():
        return NotAnswered(
            "invalid_question",
            (GroundingIssue("blank_question", "question must be a non-blank string"),),
        )
    if len(question) > MAX_QUESTION_CHARS:
        return NotAnswered(
            "invalid_question",
            (
                GroundingIssue(
                    "question_too_long",
                    "question exceeds {} characters".format(MAX_QUESTION_CHARS),
                ),
            ),
        )

    candidates = retriever.search(question, k=k)
    if not candidates:
        return NotAnswered("no_candidates")

    numbered_candidates = tuple((candidate.rank, candidate) for candidate in candidates)
    active_generator = (
        generator
        if generator is not None
        else ExtractiveGroundingGenerator(max_claims=max_claims)
    )

    try:
        draft = active_generator.generate(question, numbered_candidates, as_of=as_of)
    except Exception as error:  # noqa: BLE001 - a generator must never break the pipeline
        return NotAnswered(
            "generation_error",
            (
                GroundingIssue(
                    "generator_error",
                    "the generator raised {}".format(type(error).__name__),
                ),
            ),
        )

    if not isinstance(draft, DraftAnswer):
        return NotAnswered(
            "generation_error",
            (
                GroundingIssue(
                    "generator_error",
                    "the generator returned {}".format(type(draft).__name__),
                ),
            ),
        )

    report = verify_draft(draft, numbered_candidates)
    if not report.ok:
        return NotAnswered(_reason_for(report.issues), report.issues, report.claims)

    answer, kept_claims = _fit_claims(report.claims)
    if not kept_claims:
        return NotAnswered(
            "grounding_failed",
            (
                GroundingIssue(
                    "answer_too_long",
                    "no verified claim fits {} characters".format(MAX_ANSWER_CHARS),
                ),
            ),
        )

    cited_markers = tuple(
        sorted({marker for claim in kept_claims for marker in claim.markers})
    )
    passages_by_rank = {rank: passage for rank, passage in numbered_candidates}
    sources = tuple(passages_by_rank[marker] for marker in cited_markers)
    response_marker_by_rank = {
        rank: ordinal for ordinal, rank in enumerate(cited_markers, start=1)
    }
    answer = _MARKER.sub(
        lambda match: "[{}]".format(response_marker_by_rank[int(match.group(1))]),
        answer,
    )
    return Answered(
        answer=answer,
        claims=kept_claims,
        sources=sources,
        land_scope=land_scope,
        cited_markers=cited_markers,
    )


def answer_source(passage: RetrievedPassage) -> Dict[str, str]:
    """Return exactly the seven accepted ``AnswerSource`` keys for one passage."""

    return {
        "title": passage.title,
        "issuing_body": passage.issuing_body,
        "url": passage.url,
        "location": passage.location,
        "published_or_updated_on": passage.published_or_updated_on,
        "verified_on": passage.verified_on,
        "excerpt": passage.excerpt,
    }


def to_answer_response(answered: Answered) -> Dict[str, Any]:
    """Assemble the accepted ``AskResponse`` payload for an answered result.

    ``land_ids_to_choose`` is always empty for an answer. An unsupported
    ``land_scope``, a missing source, a blank answer, or an over-long answer is
    rejected rather than emitted.
    """

    if not isinstance(answered, Answered):
        raise ValueError("to_answer_response requires an Answered result")
    if answered.land_scope not in LAND_SCOPES:
        raise ValueError("land_scope must be one of: {}".format(", ".join(LAND_SCOPES)))
    if not answered.sources:
        raise ValueError("an answered response requires at least one source")
    if not answered.answer.strip() or len(answered.answer) > MAX_ANSWER_CHARS:
        raise ValueError(
            "answer must be non-blank and at most {} characters".format(MAX_ANSWER_CHARS)
        )
    return {
        "status": "answered",
        "answer": answered.answer,
        "sources": [answer_source(passage) for passage in answered.sources],
        "land_scope": answered.land_scope,
        "land_ids_to_choose": [],
    }


def _reason_for(issues: Sequence[GroundingIssue]) -> str:
    codes = {issue.code for issue in issues}
    if "generator_abstained" in codes:
        return "generator_abstained"
    if codes & POLICY_ISSUE_CODES:
        return "policy_failed"
    return "grounding_failed"


def _render_claim(claim: ClaimVerdict) -> str:
    markers = "".join("[{}]".format(marker) for marker in claim.markers)
    if not markers:
        return claim.text
    return "{} {}".format(claim.text, markers)


def _assemble_claims(claims: Sequence[ClaimVerdict]) -> str:
    body = " ".join(_render_claim(claim) for claim in claims)
    if not body:
        return "{} {}".format(LEAD_IN, NOTICE)
    return "{} {} {}".format(LEAD_IN, body, NOTICE)


def _fit_claims(
    claims: Sequence[ClaimVerdict],
) -> Tuple[str, Tuple[ClaimVerdict, ...]]:
    """Assemble the surviving claims, dropping trailing ones until the payload fits.

    Claims are dropped whole, never mid-sentence, and the first claim is always
    kept because :func:`verify_draft` already checked that it fits.
    """

    kept = list(claims)
    while kept:
        answer = _assemble_claims(kept)
        if len(answer) <= MAX_ANSWER_CHARS:
            return answer, tuple(kept)
        kept.pop()
    return "", ()
