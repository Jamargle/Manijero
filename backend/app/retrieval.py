"""Offline retrieval over human-reviewed source passages.

Retrieval is the *read* side of the accepted source-catalog gate. It searches
only passages whose ``source_id`` resolves to a catalog source that is
``review_status: approved``, ``lifecycle_status: current``, and not expired as
of a caller-supplied ``as_of`` date. It re-validates the catalog itself with
:func:`app.source_catalog.validate_catalog` and refuses to build an index when
the catalog is invalid, instead of indexing partially approved data.

The module is deliberately dependency-free and offline: it reads local JSON,
never opens a socket, never downloads or parses a document, and never claims
that a passage is authentic, currently in force, or legally applicable. Its
durable contracts live in ``knowledge/passages.schema.json`` (passage set) and
``knowledge/source_catalog.schema.json`` (approved catalog).

The ``Retriever.search`` boundary is narrow on purpose. It returns ranked
:class:`RetrievedPassage` values whose field names line up with the accepted
``AnswerSource`` contract (``title``, ``issuing_body``, ``url``, ``location``,
``published_or_updated_on``, ``verified_on``, ``excerpt``) plus retrieval-local
fields (``passage_id``, ``source_id``, ``applicability``, ``critical``,
``score``, ``rank``).

Hybrid retrieval plugs in through :meth:`Retriever.with_ranker`, never by
replacing this class: a :class:`CandidateRanker` may only reorder or add
passages this retriever already admitted, a question with no lexical match still
returns no candidate, and without a ranker ``search`` is the accepted BM25
behavior unchanged.
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Protocol, Sequence, Tuple

from app.source_catalog import (
    ValidationIssue,
    is_non_blank_string,
    join_path,
    validate_catalog,
)

PASSAGE_SET_SCHEMA_VERSION = "passage-set-v1"

TOP_LEVEL_KEYS = frozenset({"schema_version", "passages"})

PASSAGE_REQUIRED_KEYS = frozenset({"id", "source_id", "location", "text"})
PASSAGE_OPTIONAL_KEYS = frozenset({"critical", "applicability"})

APPLICABILITY_KEYS = frozenset({"crop", "water_regime", "production_method"})

WATER_REGIMES = ("dryland", "irrigated", "mixed")
PRODUCTION_METHODS = ("conventional", "organic", "mixed")

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_K = 5

# Okapi BM25 parameters. These are the conventional defaults from the
# literature, not tuned values: the fixture baseline in PROGRESS.md is the
# starting measurement to calibrate them against.
BM25_K1 = 1.5
BM25_B = 0.75

# Small built-in Spanish stopword list. Kept intentionally short and free of
# content-bearing words so that negations and quantities are never dropped
# before scoring.
STOPWORDS: FrozenSet[str] = frozenset(
    {
        "a",
        "al",
        "algo",
        "ante",
        "como",
        "con",
        "contra",
        "cual",
        "cuando",
        "de",
        "del",
        "desde",
        "donde",
        "el",
        "ella",
        "ellas",
        "ellos",
        "en",
        "entre",
        "es",
        "esa",
        "esas",
        "ese",
        "eso",
        "esos",
        "esta",
        "este",
        "esto",
        "estos",
        "ha",
        "hasta",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "los",
        "me",
        "mi",
        "mis",
        "mucho",
        "muy",
        "o",
        "os",
        "otra",
        "otro",
        "para",
        "pero",
        "por",
        "porque",
        "que",
        "se",
        "sin",
        "sobre",
        "son",
        "su",
        "sus",
        "te",
        "tu",
        "tus",
        "un",
        "una",
        "unas",
        "uno",
        "unos",
        "y",
        "yo",
    }
)


class RetrievalError(Exception):
    """Base class for offline retrieval failures."""


class PassageSetError(RetrievalError):
    """A passage set could not be read, parsed, or validated.

    Schema violations and unknown ``source_id`` references are reported with the
    JSON path that failed, such as ``$.passages[0].source_id``. Field values and
    excerpt text are never included in the message.
    """


class CatalogRejectedError(RetrievalError):
    """The catalog did not pass the accepted source-catalog admission gate."""


@dataclass(frozen=True)
class PassageSetReport:
    """Result of validating one passage-set document against the contract."""

    schema_version: Optional[str]
    checked_passages: int
    issues: Tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_issues(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


@dataclass(frozen=True)
class RetrievedPassage:
    """One ranked candidate passage plus the metadata needed to cite it.

    ``title``, ``issuing_body``, ``url``, ``location``,
    ``published_or_updated_on``, ``verified_on`` and ``excerpt`` intentionally
    mirror the accepted ``AnswerSource`` contract. ``passage_id``, ``source_id``,
    ``applicability``, ``critical``, ``score`` and ``rank`` are retrieval-local.

    ``applicability`` and ``critical`` are the passage-level values when the
    passage declares them, otherwise the source-level values. They are surfaced,
    never used to filter here: applicability-based selection belongs to
    ``minimal_land_context`` / ``land_clarification``.
    """

    passage_id: str
    source_id: str
    title: str
    issuing_body: str
    url: str
    location: str
    published_or_updated_on: str
    verified_on: str
    excerpt: str
    applicability: Optional[Dict[str, str]]
    critical: bool
    score: float
    rank: int


def tokenize(text: str) -> Tuple[str, ...]:
    """Return the search tokens of ``text``.

    Lowercases, decomposes compatibility characters with NFKD, drops combining
    diacritics, splits on non-alphanumerics, and removes a small Spanish
    stopword list. ``"solicitud única"`` and ``"SOLICITUD unica"`` therefore
    tokenize to the same tokens.
    """

    if not isinstance(text, str):
        return ()
    normalized = unicodedata.normalize("NFKD", text.lower())
    without_diacritics = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return tuple(
        token for token in re.findall(r"[a-z0-9]+", without_diacritics) if token not in STOPWORDS
    )


def validate_passage_set(document: Any) -> PassageSetReport:
    """Validate a parsed passage-set document against the readable contract."""

    return _PassageSetValidator().validate(document)


def load_passage_set(path: Path) -> Any:
    """Read and parse a passage-set file, raising ``PassageSetError`` on failure."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise PassageSetError("cannot read passage set file: {}".format(error)) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise PassageSetError("passage set file is not valid JSON: {}".format(error)) from error


def source_is_eligible(source: Any, as_of: date) -> bool:
    """Return whether a catalog entry may back a retrievable passage.

    This is an independent re-check of the accepted catalog rules: ``approved``
    review, ``current`` lifecycle, and no ``valid_until`` earlier than ``as_of``.
    Anything unrecognized fails closed.
    """

    if not isinstance(source, dict):
        return False
    if source.get("review_status") != "approved":
        return False
    if source.get("lifecycle_status") != "current":
        return False
    return not _is_expired(source.get("valid_until"), as_of)


def eligible_source_ids(catalog_document: Any, as_of: date) -> FrozenSet[str]:
    """Return the ids of the catalog sources eligible for retrieval as of ``as_of``."""

    if not isinstance(catalog_document, dict):
        return frozenset()
    sources = catalog_document.get("sources")
    if not isinstance(sources, list):
        return frozenset()
    return frozenset(
        source["id"]
        for source in sources
        if isinstance(source, dict)
        and is_non_blank_string(source.get("id"))
        and source_is_eligible(source, as_of)
    )


class Bm25Index:
    """Okapi BM25 over a fixed, in-memory set of ``(document_id, text)`` pairs.

    Scoring is deterministic: the ranking orders by descending score and breaks
    ties by ascending document id, so equal scores never reorder between runs.
    """

    def __init__(self, documents: Sequence[Tuple[str, str]]) -> None:
        ids: List[str] = []
        term_frequencies: List[Dict[str, int]] = []
        lengths: List[int] = []
        for document_id, text in documents:
            tokens = tokenize(text)
            ids.append(document_id)
            term_frequencies.append(_term_frequencies(tokens))
            lengths.append(len(tokens))

        self._ids: Tuple[str, ...] = tuple(ids)
        self._term_frequencies: Tuple[Dict[str, int], ...] = tuple(term_frequencies)
        self._lengths: Tuple[int, ...] = tuple(lengths)
        self._document_count = len(ids)
        self._average_length = (sum(lengths) / len(lengths)) if lengths else 0.0

        document_frequencies: Dict[str, int] = {}
        for frequencies in term_frequencies:
            for term in frequencies:
                document_frequencies[term] = document_frequencies.get(term, 0) + 1
        self._document_frequencies = document_frequencies

    @property
    def document_count(self) -> int:
        return self._document_count

    def ranked_scores(self, query_tokens: Sequence[str]) -> Tuple[Tuple[str, float], ...]:
        """Return every ``(document_id, score)`` pair, best first.

        Pairs with a zero score are included so callers can decide whether an
        absent lexical match is a candidate at all.
        """

        terms = _unique_terms(query_tokens)
        scored = [
            (document_id, self._score_document(position, terms))
            for position, document_id in enumerate(self._ids)
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return tuple(scored)

    def _score_document(self, position: int, terms: Sequence[str]) -> float:
        if not terms or self._document_count == 0 or self._average_length <= 0.0:
            return 0.0

        frequencies = self._term_frequencies[position]
        length = self._lengths[position]
        score = 0.0
        for term in terms:
            frequency = frequencies.get(term, 0)
            if frequency == 0:
                continue
            document_frequency = self._document_frequencies.get(term, 0)
            inverse_document_frequency = math.log(
                1.0
                + (self._document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            denominator = frequency + BM25_K1 * (
                1.0 - BM25_B + BM25_B * length / self._average_length
            )
            score += (
                inverse_document_frequency * (frequency * (BM25_K1 + 1.0)) / denominator
            )
        return score


class CandidateRanker(Protocol):
    """Optional re-ranking step composed into :meth:`Retriever.search`.

    ``rank`` receives the question and the non-empty BM25 ranking (``(passage_id,
    score)`` pairs with a positive score, best first) and returns ``(passage_id,
    score)`` pairs best first. The retriever drops any id it did not admit and
    any duplicate, so a ranker cannot introduce an ineligible passage. A ranker
    that cannot run must return the lexical ranking it was given.
    """

    def rank(
        self, question: str, lexical: Tuple[Tuple[str, float], ...]
    ) -> Sequence[Tuple[str, float]]:
        """Return the final ranking, best first."""


@dataclass(frozen=True)
class _PassageRecord:
    """Citation metadata for one indexed passage, without score or rank."""

    passage_id: str
    source_id: str
    title: str
    issuing_body: str
    url: str
    location: str
    published_or_updated_on: str
    verified_on: str
    excerpt: str
    applicability: Optional[Dict[str, str]]
    critical: bool


class Retriever:
    """Offline lexical retriever over reviewed passages of approved sources.

    Build one with :meth:`from_documents`, then call :meth:`search`. The index is
    immutable after construction, so repeated searches over the same question are
    deterministic.
    """

    def __init__(
        self,
        records: Sequence[_PassageRecord],
        index: Bm25Index,
        as_of: date,
        eligible_source_count: int,
        excluded_passage_count: int,
        ranker: Optional[CandidateRanker] = None,
    ) -> None:
        self._ranker = ranker
        self._records: Tuple[_PassageRecord, ...] = tuple(records)
        self._records_by_id: Dict[str, _PassageRecord] = {
            record.passage_id: record for record in self._records
        }
        self._index = index
        self._as_of = as_of
        self._eligible_source_count = eligible_source_count
        self._excluded_passage_count = excluded_passage_count

    @classmethod
    def from_documents(
        cls,
        catalog_document: Any,
        passage_document: Any,
        as_of: date,
        active_campaign: Optional[str] = None,
    ) -> "Retriever":
        """Build a retriever from a catalog document, a passage set, and ``as_of``.

        Fails closed: an invalid catalog raises :class:`CatalogRejectedError`, an
        invalid passage set raises :class:`PassageSetError`, and a passage whose
        ``source_id`` is not in the catalog raises :class:`PassageSetError`
        located at that passage's ``source_id`` JSON path.
        """

        catalog_report = validate_catalog(catalog_document, as_of)
        if not catalog_report.ok:
            raise CatalogRejectedError(catalog_report.format_issues())

        passage_report = validate_passage_set(passage_document)
        if not passage_report.ok:
            raise PassageSetError(passage_report.format_issues())

        sources: Dict[str, Dict[str, Any]] = {
            source["id"]: source for source in catalog_document["sources"]
        }
        eligible_ids = eligible_source_ids(catalog_document, as_of)

        records: List[_PassageRecord] = []
        excluded = 0
        for position, passage in enumerate(passage_document["passages"]):
            source_id = passage["source_id"]
            source = sources.get(source_id)
            if source is None:
                raise PassageSetError(
                    "{}: does not resolve to a source in the catalog".format(
                        join_path("$.passages[{}]".format(position), "source_id")
                    )
                )
            if source_id not in eligible_ids or (
                source.get("campaign") is not None and source.get("campaign") != active_campaign
            ):
                # Defense in depth: the accepted gate already rejects catalogs
                # containing ineligible sources, so this normally excludes none.
                excluded += 1
                continue
            records.append(_build_record(source, passage))

        ordered = tuple(sorted(records, key=lambda record: record.passage_id))
        index = Bm25Index(
            tuple((record.passage_id, record.excerpt) for record in ordered)
        )
        return cls(
            records=ordered,
            index=index,
            as_of=as_of,
            eligible_source_count=len(eligible_ids),
            excluded_passage_count=excluded,
        )

    @property
    def as_of(self) -> date:
        return self._as_of

    @property
    def indexed_passage_count(self) -> int:
        return len(self._records)

    @property
    def eligible_source_count(self) -> int:
        return self._eligible_source_count

    @property
    def excluded_passage_count(self) -> int:
        """Passages skipped because their source was not eligible.

        Zero for any catalog that passed the accepted gate, because that gate
        already rejects non-approved, non-current, and expired sources.
        """

        return self._excluded_passage_count

    def indexed_documents(self) -> Tuple[Tuple[str, str], ...]:
        """Return ``(passage_id, text)`` for every document this instance indexes.

        The pairs are ordered by ``passage_id`` and contain only passages that
        already passed the catalog and passage admission gates, so a consumer
        that embeds them does not re-implement eligibility.
        """

        return tuple((record.passage_id, record.excerpt) for record in self._records)

    @property
    def uses_ranker(self) -> bool:
        """Whether ``search`` composes a :class:`CandidateRanker` after BM25."""

        return self._ranker is not None

    def with_ranker(self, ranker: CandidateRanker) -> "Retriever":
        """Return a retriever over the same admitted passages that uses ``ranker``.

        The admitted records, the BM25 index, and the corpus counts are shared;
        only the final ordering step changes. ``self`` is left unchanged.
        """

        return Retriever(
            records=self._records,
            index=self._index,
            as_of=self._as_of,
            eligible_source_count=self._eligible_source_count,
            excluded_passage_count=self._excluded_passage_count,
            ranker=ranker,
        )

    def search(self, question: str, k: int = DEFAULT_K) -> Tuple[RetrievedPassage, ...]:
        """Return up to ``k`` candidate passages ranked best-first.

        A blank question, a question made only of stopwords, an empty index, and
        an out-of-vocabulary question all return an empty tuple: passages without
        any lexical match are never returned with a fabricated score. That lexical
        gate also applies when a ranker is composed, so a ranker cannot turn a
        zero-evidence question into an answerable one.
        """

        if k < 1:
            return ()
        query_tokens = tokenize(question)
        if not query_tokens:
            return ()

        lexical = tuple(
            (passage_id, score)
            for passage_id, score in self._index.ranked_scores(query_tokens)
            if score > 0.0
        )
        if not lexical:
            return ()
        ranked: Sequence[Tuple[str, float]] = lexical
        if self._ranker is not None:
            ranked = self._ranker.rank(question, lexical)

        candidates: List[RetrievedPassage] = []
        seen: Dict[str, None] = {}
        for passage_id, score in ranked:
            record = self._records_by_id.get(passage_id)
            if record is None or passage_id in seen or not _is_finite_number(score):
                continue
            seen[passage_id] = None
            candidates.append(
                RetrievedPassage(
                    passage_id=record.passage_id,
                    source_id=record.source_id,
                    title=record.title,
                    issuing_body=record.issuing_body,
                    url=record.url,
                    location=record.location,
                    published_or_updated_on=record.published_or_updated_on,
                    verified_on=record.verified_on,
                    excerpt=record.excerpt,
                    applicability=record.applicability,
                    critical=record.critical,
                    score=float(score),
                    rank=len(candidates) + 1,
                )
            )
            if len(candidates) >= k:
                break
        return tuple(candidates)


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _term_frequencies(tokens: Sequence[str]) -> Dict[str, int]:
    frequencies: Dict[str, int] = {}
    for token in tokens:
        frequencies[token] = frequencies.get(token, 0) + 1
    return frequencies


def _unique_terms(tokens: Sequence[str]) -> Tuple[str, ...]:
    seen: Dict[str, None] = {}
    for token in tokens:
        seen.setdefault(token, None)
    return tuple(seen)


def _is_expired(valid_until: Any, as_of: date) -> bool:
    if valid_until is None:
        return False
    if not isinstance(valid_until, str) or not ISO_DATE_PATTERN.match(valid_until):
        return True
    try:
        expiry = date.fromisoformat(valid_until)
    except ValueError:
        return True
    return expiry < as_of


def _build_record(source: Dict[str, Any], passage: Dict[str, Any]) -> _PassageRecord:
    applicability = passage.get("applicability")
    if applicability is None:
        applicability = source.get("applicability")

    critical = passage.get("critical")
    if critical is None:
        critical = source.get("critical", False)

    return _PassageRecord(
        passage_id=passage["id"],
        source_id=passage["source_id"],
        title=source["title"],
        issuing_body=source["issuing_body"],
        url=source["original_url"],
        location=passage["location"],
        published_or_updated_on=source["published_on"],
        verified_on=source["verified_on"],
        excerpt=passage["text"],
        applicability=dict(applicability) if isinstance(applicability, dict) else None,
        critical=bool(critical),
    )


class _PassageSetValidator:
    """Accumulates every passage-set violation instead of failing on the first."""

    def __init__(self) -> None:
        self._issues: List[ValidationIssue] = []

    def validate(self, document: Any) -> PassageSetReport:
        if not isinstance(document, dict):
            self._fail("$", "passage set document must be a JSON object")
            return self._report(None, 0)

        self._check_keys(document, TOP_LEVEL_KEYS, TOP_LEVEL_KEYS, "$")

        schema_version = document.get("schema_version")
        if "schema_version" in document and schema_version != PASSAGE_SET_SCHEMA_VERSION:
            self._fail(
                "$.schema_version",
                "must equal '{}'".format(PASSAGE_SET_SCHEMA_VERSION),
            )

        passages = document.get("passages")
        if not isinstance(passages, list):
            if "passages" in document:
                self._fail("$.passages", "must be a JSON array of passage objects")
            return self._report(_as_text(schema_version), 0)

        seen_ids: Dict[str, str] = {}
        for index, passage in enumerate(passages):
            location = "$.passages[{}]".format(index)
            if not isinstance(passage, dict):
                self._fail(location, "each passage must be a JSON object")
                continue
            self._check_passage(passage, location, seen_ids)

        return self._report(_as_text(schema_version), len(passages))

    def _check_passage(
        self,
        passage: Dict[str, Any],
        location: str,
        seen_ids: Dict[str, str],
    ) -> None:
        self._check_keys(
            passage,
            PASSAGE_REQUIRED_KEYS,
            PASSAGE_REQUIRED_KEYS | PASSAGE_OPTIONAL_KEYS,
            location,
        )

        self._check_slug(passage, "id", location, seen_ids)
        self._check_slug(passage, "source_id", location, None)
        if "location" in passage and not is_non_blank_string(passage["location"]):
            self._fail(join_path(location, "location"), "must be a non-blank string")
        if "text" in passage and not is_non_blank_string(passage["text"]):
            self._fail(join_path(location, "text"), "must be a non-blank string")
        if "critical" in passage and not isinstance(passage["critical"], bool):
            self._fail(join_path(location, "critical"), "must be true or false")
        self._check_applicability(passage, location)

    def _check_slug(
        self,
        passage: Dict[str, Any],
        key: str,
        location: str,
        seen_ids: Optional[Dict[str, str]],
    ) -> None:
        if key not in passage:
            return
        value = passage[key]
        if not is_non_blank_string(value):
            self._fail(join_path(location, key), "must be a non-blank string")
            return
        if not ID_PATTERN.match(value):
            self._fail(
                join_path(location, key),
                "must be a stable lowercase slug such as 'fixture-rd1048-art1-p1'",
            )
            return
        if seen_ids is None:
            return
        if value in seen_ids:
            self._fail(
                join_path(location, key),
                "duplicate id; already used by {}".format(seen_ids[value]),
            )
            return
        seen_ids[value] = location

    def _check_applicability(self, passage: Dict[str, Any], location: str) -> None:
        if "applicability" not in passage:
            return
        value = passage["applicability"]
        applicability_location = join_path(location, "applicability")
        if not isinstance(value, dict):
            self._fail(applicability_location, "must be an object")
            return
        self._check_keys(value, frozenset(), APPLICABILITY_KEYS, applicability_location)
        if not value:
            self._fail(
                applicability_location,
                "must not be empty; leave applicability absent when nothing is known",
            )
            return
        if "crop" in value and not is_non_blank_string(value["crop"]):
            self._fail(join_path(applicability_location, "crop"), "must be a non-blank string")
        if "water_regime" in value and value["water_regime"] not in WATER_REGIMES:
            self._fail(
                join_path(applicability_location, "water_regime"),
                "must be one of: {}; leave unknown absent".format(", ".join(WATER_REGIMES)),
            )
        if "production_method" in value and value["production_method"] not in PRODUCTION_METHODS:
            self._fail(
                join_path(applicability_location, "production_method"),
                "must be one of: {}; leave unknown absent".format(
                    ", ".join(PRODUCTION_METHODS)
                ),
            )

    def _check_keys(
        self,
        payload: Dict[str, Any],
        required: FrozenSet[str],
        allowed: FrozenSet[str],
        location: str,
    ) -> None:
        for key in sorted(payload):
            if key not in allowed:
                self._fail(join_path(location, key), "unknown key is not allowed")
        for key in sorted(required):
            if key not in payload:
                self._fail(join_path(location, key), "required key is missing")

    def _fail(self, location: str, rule: str) -> None:
        self._issues.append(ValidationIssue(location, rule))

    def _report(self, schema_version: Optional[str], checked_passages: int) -> PassageSetReport:
        return PassageSetReport(
            schema_version=schema_version,
            checked_passages=checked_passages,
            issues=tuple(self._issues),
        )


def _as_text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() != "" else None
