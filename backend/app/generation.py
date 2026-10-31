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
        "critical_not_literal",
    }
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
