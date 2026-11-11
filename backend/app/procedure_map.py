"""Offline validation of the reviewed olive-grove procedure map.

The procedure map is a Git-tracked taxonomy index of the olive-grove
procedures the assistant is meant to cover. Each topic records plain-Spanish
wording for later source scouting and question work, plus an honest statement of
whether the approved corpus contains reviewed evidence for it.

The map is **not** legal knowledge and **not** an answer source: it carries no
dates, amounts, thresholds, article numbers, eligibility conclusions, or
applicability claims, and it never approves, retires, or re-dates evidence. It
validates structure, review honesty, and cross-references only. Missing coverage
is reported, never treated as a validation failure. The durable format is
``knowledge/procedure_map.schema.json`` and ``knowledge/README.md``.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "procedure-map-v1"

# The ordered seed set from ``docs/archive/MasterPlanV3.md`` section 7.3. The
# validator pins it so that widening the taxonomy is a reviewed code-and-data
# change, not an unreviewed addition.
SEED_TOPIC_IDS: Tuple[str, ...] = (
    "solicitud-unica-pac",
    "sigpac",
    "ayuda-directa-olivar",
    "agricultor-activo",
    "superficies-minimas",
    "riego",
    "condicionalidad",
    "cuaderno-digital",
    "ayudas-junta-andalucia",
    "notificaciones-y-rectificaciones",
    "delegacion-entidades-colaboradoras",
    "pagos",
    "quema-restos-poda",
    "productos-fitosanitarios",
    "seguros-agrarios",
    "produccion-ecologica",
    # Added on 2026-11-11 with the owner-approved scope expansion that records the
    # olive-oil marketing rule (BOE-A-2026-23330) as a reviewed-corpus topic.
    "comercializacion-aceite-oliva",
)

SEED_TOPIC_ID_SET = frozenset(SEED_TOPIC_IDS)

TOP_LEVEL_KEYS = frozenset({"schema_version", "topics"})

TOPIC_REQUIRED_KEYS = frozenset(
    {
        "id",
        "title",
        "summary",
        "search_terms",
        "review_status",
        "coverage",
    }
)
TOPIC_OPTIONAL_KEYS = frozenset({"reviewed_by"})

COVERAGE_REQUIRED_KEYS = frozenset({"state", "source_ids", "passage_ids"})
COVERAGE_OPTIONAL_KEYS = frozenset({"gap_note"})

REVIEW_STATUSES = ("proposed", "reviewed")
COVERAGE_STATES = ("covered", "partial", "uncovered")

MAX_TITLE_LENGTH = 120
MAX_SUMMARY_LENGTH = 320
MAX_SEARCH_TERM_LENGTH = 60
MAX_SEARCH_TERMS = 6
MAX_GAP_NOTE_LENGTH = 240
MAX_REVIEWER_LENGTH = 120

TOPIC_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")

DIGIT_RULE = "must not contain digits; the procedure map is not legal knowledge"


class ProcedureMapReadError(Exception):
    """Raised when the map or one of its reference files cannot be read."""


@dataclass(frozen=True)
class ValidationIssue:
    """One map-policy violation, located by its JSON path.

    Diagnostics deliberately contain no map field values: only the path and the
    violated rule. That keeps validator output free of document text.
    """

    location: str
    rule: str

    def __str__(self) -> str:
        return "{}: {}".format(self.location, self.rule)


@dataclass(frozen=True)
class TopicCoverage:
    """One deterministic coverage row for a structurally readable topic."""

    id: str
    review_status: str
    state: str
    source_count: int
    passage_count: int


@dataclass(frozen=True)
class CoverageReport:
    """Report-only coverage summary; gaps never make validation fail."""

    topics: Tuple[TopicCoverage, ...]
    covered: int
    partial: int
    uncovered: int
    proposed: int
    reviewed: int
    mapped_source_ids: Tuple[str, ...]
    mapped_passage_ids: Tuple[str, ...]
    unreferenced_source_ids: Tuple[str, ...]
    unreferenced_passage_ids: Tuple[str, ...]
    references_checked: bool

    def summary_line(self) -> str:
        line = (
            "coverage: {} covered, {} partial, {} uncovered; "
            "{} mapped source(s), {} mapped passage(s)"
        ).format(
            self.covered,
            self.partial,
            self.uncovered,
            len(self.mapped_source_ids),
            len(self.mapped_passage_ids),
        )
        if self.references_checked:
            line += "; unreferenced source ids: {}; unreferenced passage ids: {}".format(
                ", ".join(self.unreferenced_source_ids) or "none",
                ", ".join(self.unreferenced_passage_ids) or "none",
            )
        else:
            line += "; reference ids not checked (supply --catalog and --passages)"
        return line

    def format_lines(self) -> Tuple[str, ...]:
        return tuple(
            "topic {}: {}, {}, {} source(s), {} passage(s)".format(
                row.id,
                row.review_status,
                row.state,
                row.source_count,
                row.passage_count,
            )
            for row in self.topics
        )


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating one procedure-map document."""

    schema_version: Optional[str]
    checked_topics: int
    issues: Tuple[ValidationIssue, ...]
    coverage: CoverageReport

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_issues(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


def validate_procedure_map(
    document: Any,
    catalog_ids: Optional[FrozenSet[str]] = None,
    passage_sources: Optional[Mapping[str, str]] = None,
) -> ValidationReport:
    """Validate a parsed map, optionally cross-checking corpus references.

    Cross-file reference checks run only when both ``catalog_ids`` and
    ``passage_sources`` are supplied. Coverage gaps are always reported and
    never make the document invalid.
    """

    return _ProcedureMapValidator(catalog_ids, passage_sources).validate(document)


def load_procedure_map(path: Path) -> Any:
    """Read and parse a map file, raising ``ProcedureMapReadError`` on failure."""

    return _load_json(path, "procedure map")


def load_catalog_ids(path: Path) -> FrozenSet[str]:
    """Read the approved source ids from a canonical source catalog."""

    document = _load_json(path, "catalog")
    if not isinstance(document, dict) or not isinstance(document.get("sources"), list):
        raise ProcedureMapReadError("catalog file does not contain a sources array")
    ids = set()
    for entry in document["sources"]:
        if isinstance(entry, dict) and is_non_blank_string(entry.get("id")):
            ids.add(entry["id"])
    return frozenset(ids)


def load_passage_sources(path: Path) -> Dict[str, str]:
    """Read reviewed passages and map each passage id to its source id."""

    document = _load_json(path, "passage set")
    if not isinstance(document, dict) or not isinstance(document.get("passages"), list):
        raise ProcedureMapReadError("passage file does not contain a passages array")
    sources: Dict[str, str] = {}
    for entry in document["passages"]:
        if (
            isinstance(entry, dict)
            and is_non_blank_string(entry.get("id"))
            and is_non_blank_string(entry.get("source_id"))
        ):
            sources[entry["id"]] = entry["source_id"]
    return sources


def _load_json(path: Path, label: str) -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ProcedureMapReadError("cannot read {} file: {}".format(label, error)) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ProcedureMapReadError(
            "{} file is not valid JSON: {}".format(label, error)
        ) from error


class _ProcedureMapValidator:
    """Accumulates every policy violation instead of failing on the first one."""

    def __init__(
        self,
        catalog_ids: Optional[FrozenSet[str]],
        passage_sources: Optional[Mapping[str, str]],
    ) -> None:
        self._catalog_ids = catalog_ids
        self._passage_sources = passage_sources
        self._references_checked = catalog_ids is not None and passage_sources is not None
        self._issues: List[ValidationIssue] = []
        self._topic_documents: List[Any] = []
        self._seen_ids: Dict[str, str] = {}
        self._search_terms_seen: Dict[str, str] = {}
        self._search_terms: Dict[str, str] = {}

    def validate(self, document: Any) -> ValidationReport:
        if not isinstance(document, dict):
            self._fail("$", "procedure map document must be a JSON object")
            return self._report(None, 0)

        self.check_keys(document, TOP_LEVEL_KEYS, TOP_LEVEL_KEYS, "$")

        schema_version = document.get("schema_version")
        if "schema_version" in document and schema_version != SCHEMA_VERSION:
            self._fail("$.schema_version", "must equal '{}'".format(SCHEMA_VERSION))

        topics = document.get("topics")
        if not isinstance(topics, list):
            if "topics" in document:
                self._fail("$.topics", "must be a JSON array of topic objects")
            return self._report(_as_text(schema_version), 0)

        self._topic_documents = topics
        for index, topic in enumerate(topics):
            location = "$.topics[{}]".format(index)
            if not isinstance(topic, dict):
                self._fail(location, "each topic must be a JSON object")
                continue
            _TopicValidator(self, location, topic).validate()

        self._check_seed_set(topics)
        return self._report(_as_text(schema_version), len(topics))

    def fail(self, location: str, rule: str) -> None:
        self._fail(location, rule)

    def check_keys(
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

    def check_topic_id(self, topic: Dict[str, Any], location: str) -> None:
        if "id" not in topic:
            return
        value = topic["id"]
        if not is_non_blank_string(value):
            self._fail(join_path(location, "id"), "must be a non-blank string")
            return
        if not TOPIC_ID_PATTERN.match(value):
            self._fail(
                join_path(location, "id"),
                "must be a stable lowercase slug such as 'solicitud-unica-pac'",
            )
            return
        if value in self._seen_ids:
            self._fail(
                join_path(location, "id"),
                "duplicate id; already used by {}".format(self._seen_ids[value]),
            )
            return
        self._seen_ids[value] = location
        if value not in SEED_TOPIC_ID_SET:
            self._fail(join_path(location, "id"), "topic id is not in the seed set")

    def claim_search_term(self, term: str, location: str) -> bool:
        """Register a search term across topics; false when already used."""

        if term in self._search_terms:
            self._fail(
                location,
                "duplicate search wording across topics; already used by {}".format(
                    self._search_terms[term]
                ),
            )
            return False
        self._search_terms[term] = location
        return True

    def check_references(
        self,
        location: str,
        source_ids: Sequence[Any],
        passage_ids: Sequence[Any],
    ) -> None:
        if not self._references_checked:
            return
        assert self._catalog_ids is not None
        assert self._passage_sources is not None
        known_sources = set(source_ids)
        for index, source_id in enumerate(source_ids):
            if source_id not in self._catalog_ids:
                self._fail(
                    join_path(location, "source_ids[{}]".format(index)),
                    "unknown catalog source id",
                )
        for index, passage_id in enumerate(passage_ids):
            if passage_id not in self._passage_sources:
                self._fail(
                    join_path(location, "passage_ids[{}]".format(index)),
                    "unknown reviewed passage id",
                )
                continue
            if self._passage_sources[passage_id] not in known_sources:
                self._fail(
                    join_path(location, "passage_ids[{}]".format(index)),
                    "passage source is not listed by the topic",
                )

    def _check_seed_set(self, topics: Sequence[Any]) -> None:
        present = set(self._seen_ids)
        for seed_id in SEED_TOPIC_IDS:
            if seed_id not in present:
                self._fail("$.topics", "seed topic is missing: {}".format(seed_id))
        # Preserve the authored order of seed ids for the ordering check.
        ordered = []
        for topic in topics:
            if isinstance(topic, dict):
                topic_id = topic.get("id")
                if is_non_blank_string(topic_id) and topic_id in SEED_TOPIC_ID_SET:
                    ordered.append(topic_id)
        if not present.difference(SEED_TOPIC_ID_SET) and ordered != list(SEED_TOPIC_IDS):
            if len(ordered) == len(SEED_TOPIC_IDS):
                self._fail("$.topics", "topics must follow the seed order")

    def _fail(self, location: str, rule: str) -> None:
        self._issues.append(ValidationIssue(location, rule))

    def _report(self, schema_version: Optional[str], checked_topics: int) -> ValidationReport:
        return ValidationReport(
            schema_version=schema_version,
            checked_topics=checked_topics,
            issues=tuple(self._issues),
            coverage=_build_coverage(
                self._topic_documents,
                self._catalog_ids,
                self._passage_sources,
                self._references_checked,
            ),
        )


class _TopicValidator:
    """Validates one topic entry using only values already present."""

    def __init__(self, parent: _ProcedureMapValidator, location: str, topic: Dict[str, Any]) -> None:
        self._parent = parent
        self._location = location
        self._topic = topic

    def validate(self) -> None:
        self._parent.check_keys(
            self._topic,
            TOPIC_REQUIRED_KEYS,
            TOPIC_REQUIRED_KEYS | TOPIC_OPTIONAL_KEYS,
            self._location,
        )
        self._parent.check_topic_id(self._topic, self._location)
        self._check_text("title", MAX_TITLE_LENGTH)
        self._check_text("summary", MAX_SUMMARY_LENGTH)
        self._check_search_terms()
        self._check_review()
        self._check_coverage()

    def _fail(self, key: str, rule: str) -> None:
        self._parent.fail(join_path(self._location, key), rule)

    def _check_text(self, key: str, max_length: int) -> None:
        if key not in self._topic:
            return
        check_human_text(self._parent, self._topic[key], join_path(self._location, key), max_length)

    def _check_search_terms(self) -> None:
        if "search_terms" not in self._topic:
            return
        value = self._topic["search_terms"]
        location = join_path(self._location, "search_terms")
        if not isinstance(value, list):
            self._parent.fail(location, "must be a JSON array of plain-Spanish phrases")
            return
        if not 1 <= len(value) <= MAX_SEARCH_TERMS:
            self._parent.fail(location, "must contain between 1 and 6 phrases")
        seen: Dict[str, str] = {}
        for index, term in enumerate(value):
            term_location = join_path(location, "[{}]".format(index))
            if not check_human_text(self._parent, term, term_location, MAX_SEARCH_TERM_LENGTH):
                continue
            normalized = " ".join(term.strip().casefold().split())
            if normalized in seen:
                self._parent.fail(
                    term_location,
                    "duplicate search wording within the topic; already used by {}".format(
                        seen[normalized]
                    ),
                )
                continue
            if normalized in self._parent._search_terms_seen:
                self._parent.fail(
                    term_location,
                    "duplicate search wording; already used by {}".format(
                        self._parent._search_terms_seen[normalized]
                    ),
                )
                continue
            seen[normalized] = term_location
            self._parent._search_terms_seen[normalized] = term_location
            self._parent.claim_search_term(normalized, term_location)

    def _check_review(self) -> None:
        status = self._topic.get("review_status")
        if "review_status" in self._topic and status not in REVIEW_STATUSES:
            self._fail(
                "review_status",
                "must be 'proposed' or 'reviewed'; proposed is the only unreviewed default",
            )
        reviewer = self._topic.get("reviewed_by")
        if status == "reviewed":
            if not is_non_blank_string(reviewer):
                self._fail(
                    "reviewed_by",
                    "reviewed topics require a named human reviewer; unreviewed topics stay proposed",
                )
            elif len(reviewer) > MAX_REVIEWER_LENGTH:
                self._fail(
                    "reviewed_by",
                    "must be at most {} characters".format(MAX_REVIEWER_LENGTH),
                )
        elif status == "proposed" and "reviewed_by" in self._topic:
            self._fail("reviewed_by", "proposed topics must omit reviewed_by")

    def _check_coverage(self) -> None:
        if "coverage" not in self._topic:
            return
        value = self._topic["coverage"]
        location = join_path(self._location, "coverage")
        if not isinstance(value, dict):
            self._parent.fail(location, "must be a JSON object")
            return
        self._parent.check_keys(
            value,
            COVERAGE_REQUIRED_KEYS,
            COVERAGE_REQUIRED_KEYS | COVERAGE_OPTIONAL_KEYS,
            location,
        )
        state = value.get("state")
        if "state" in value and state not in COVERAGE_STATES:
            self._parent.fail(
                join_path(location, "state"),
                "must be 'covered', 'partial', or 'uncovered'",
            )
        source_ids = self._check_reference_list(value, "source_ids", location)
        passage_ids = self._check_reference_list(value, "passage_ids", location)
        if state == "uncovered":
            if source_ids or passage_ids:
                self._parent.fail(
                    location,
                    "uncovered topic must not list evidence references; leave both lists empty",
                )
        elif state in ("covered", "partial"):
            if not source_ids:
                self._parent.fail(
                    join_path(location, "source_ids"),
                    "covered and partial topics must list at least one approved source",
                )
            if not passage_ids:
                self._parent.fail(
                    join_path(location, "passage_ids"),
                    "covered and partial topics must list at least one reviewed passage",
                )
        if state == "partial" and not is_non_blank_string(value.get("gap_note")):
            self._parent.fail(
                join_path(location, "gap_note"),
                "partial coverage requires a gap note naming what reviewed evidence is missing",
            )
        if "gap_note" in value:
            check_human_text(
                self._parent,
                value["gap_note"],
                join_path(location, "gap_note"),
                MAX_GAP_NOTE_LENGTH,
            )
        if self._parent._references_checked and state in ("covered", "partial"):
            self._parent.check_references(location, source_ids, passage_ids)

    def _check_reference_list(
        self, value: Dict[str, Any], key: str, location: str
    ) -> List[str]:
        if key not in value:
            return []
        items = value[key]
        list_location = join_path(location, key)
        if not isinstance(items, list):
            self._parent.fail(list_location, "must be a JSON array of ids")
            return []
        valid: List[str] = []
        seen = set()
        for index, item in enumerate(items):
            item_location = join_path(list_location, "[{}]".format(index))
            if not is_non_blank_string(item):
                self._parent.fail(item_location, "must be a non-blank id string")
                continue
            if not REFERENCE_ID_PATTERN.match(item):
                self._parent.fail(item_location, "must be a stable lowercase id slug")
                continue
            if item in seen:
                self._parent.fail(item_location, "duplicate reference id within the topic")
                continue
            seen.add(item)
            valid.append(item)
        return valid


def check_human_text(
    parent: _ProcedureMapValidator, value: Any, location: str, max_length: int
) -> bool:
    """Check one human-readable field for blankness, length, and digits."""

    if not is_non_blank_string(value):
        parent.fail(location, "must be a non-blank string")
        return False
    if len(value) > max_length:
        parent.fail(location, "must be at most {} characters".format(max_length))
    if any(character.isdigit() for character in value):
        parent.fail(location, DIGIT_RULE)
        return False
    return True


def _build_coverage(
    topic_documents: Sequence[Any],
    catalog_ids: Optional[FrozenSet[str]],
    passage_sources: Optional[Mapping[str, str]],
    references_checked: bool,
) -> CoverageReport:
    rows: List[TopicCoverage] = []
    mapped_sources = set()
    mapped_passages = set()
    covered = partial = uncovered = proposed = reviewed = 0

    for topic in topic_documents:
        if not isinstance(topic, dict):
            continue
        topic_id = topic.get("id")
        coverage = topic.get("coverage")
        if not is_non_blank_string(topic_id) or not isinstance(coverage, dict):
            continue
        review_status = topic.get("review_status")
        review_status = review_status if review_status in REVIEW_STATUSES else "unknown"
        state = coverage.get("state")
        state = state if state in COVERAGE_STATES else "unknown"
        source_ids = _string_ids(coverage.get("source_ids"))
        passage_ids = _string_ids(coverage.get("passage_ids"))
        mapped_sources.update(source_ids)
        mapped_passages.update(passage_ids)
        if review_status == "proposed":
            proposed += 1
        elif review_status == "reviewed":
            reviewed += 1
        if state == "covered":
            covered += 1
        elif state == "partial":
            partial += 1
        elif state == "uncovered":
            uncovered += 1
        rows.append(
            TopicCoverage(
                id=topic_id,
                review_status=review_status,
                state=state,
                source_count=len(source_ids),
                passage_count=len(passage_ids),
            )
        )

    unreferenced_sources: Tuple[str, ...] = ()
    if catalog_ids is not None:
        unreferenced_sources = tuple(sorted(catalog_ids.difference(mapped_sources)))
    unreferenced_passages: Tuple[str, ...] = ()
    if passage_sources is not None:
        unreferenced_passages = tuple(sorted(set(passage_sources).difference(mapped_passages)))

    return CoverageReport(
        topics=tuple(rows),
        covered=covered,
        partial=partial,
        uncovered=uncovered,
        proposed=proposed,
        reviewed=reviewed,
        mapped_source_ids=tuple(sorted(mapped_sources)),
        mapped_passage_ids=tuple(sorted(mapped_passages)),
        unreferenced_source_ids=unreferenced_sources,
        unreferenced_passage_ids=unreferenced_passages,
        references_checked=references_checked,
    )


def _string_ids(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if is_non_blank_string(item)]


def join_path(location: str, key: str) -> str:
    """Return a JSON path such as ``$.topics[0].coverage.source_ids``."""

    if key.startswith("["):
        return "{}{}".format(location, key)
    return "{}.{}".format(location, key)


def is_non_blank_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _as_text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() != "" else None
