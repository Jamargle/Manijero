"""Reviewed question glossary: approved colloquial -> official terms, appended to the search query.

Runtime side of ``question_rewriting``. A grower's words and an official source's words often
differ ("papeleo" vs "solicitud"). The owner approves colloquial -> official pairs in
``backend/config/question_glossary.json``; this module appends the approved official term to
the *retrieval query only*. It never replaces a word and never touches the question used for
screening, the year check, scope and presupposition checks, drafting, the cache key text,
trace, retention, or the response.

Deterministic and offline: whole-token matching over :func:`app.retrieval.tokenize`, longest
match first, no overlaps, at most :data:`MAX_APPENDED` terms. Any problem with the file or the
``MANIJERO_QUESTION_GLOSSARY`` setting leaves expansion off (the unchanged search). Reasons are
fixed codes; no term is ever returned for logging.

Imports only the standard library and :mod:`app.retrieval`. The review tooling lives in
``app.question_glossary_review`` and is never imported on the ``/ask`` path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.retrieval import tokenize

SCHEMA_VERSION = "question-glossary-v1"
SETTING_ENV = "MANIJERO_QUESTION_GLOSSARY"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "question_glossary.json"
MAX_FILE_BYTES = 256 * 1024
MAX_ENTRIES = 500
MAX_APPENDED = 4

STATES = ("proposed", "approved", "rejected")
ORIGIN_KINDS = ("notice", "golden")

COLLOQUIAL_MAX_TOKENS = 4
COLLOQUIAL_MAX_CHARS = 60
OFFICIAL_MAX_TOKENS = 8
OFFICIAL_MAX_CHARS = 80

# Fixed reason codes (never a term).
REASON_MISSING = "missing"
REASON_UNREADABLE = "unreadable"
REASON_TOO_LARGE = "too_large"
REASON_WRONG_SCHEMA = "wrong_schema"
REASON_INVALID_ENTRY = "invalid_entry"
REASON_DISABLED = "disabled"
REASON_INVALID_SETTING = "invalid_setting"

_ID = re.compile(r"^gl-[0-9]{3}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_URL = re.compile(r"(?i)(?:https?://|www\.|\b[\w-]+\.(?:com|es|org|net|eu|gob|info|cat)\b)")
_ENTRY_KEYS = {"id", "colloquial", "official", "origin", "drafted", "review_state", "decision"}


def pair_failures(colloquial: Any, official: Any) -> List[str]:
    """Fixed codes for the entry rules on one pair; empty when the pair is acceptable."""

    failures: List[str] = []
    for side, value, max_tokens, max_chars in (
        ("colloquial", colloquial, COLLOQUIAL_MAX_TOKENS, COLLOQUIAL_MAX_CHARS),
        ("official", official, OFFICIAL_MAX_TOKENS, OFFICIAL_MAX_CHARS),
    ):
        if not isinstance(value, str):
            failures.append(f"{side}_not_text")
            continue
        if not value.strip() or len(value) > max_chars:
            failures.append(f"{side}_length")
        elif not 1 <= len(tokenize(value)) <= max_tokens:
            failures.append(f"{side}_tokens")
        if "\n" in value or "\r" in value or any(ord(c) < 32 for c in value):
            failures.append(f"{side}_multiline")
        if any(c.isdigit() for c in value):
            failures.append(f"{side}_digit")
        if _URL.search(value):
            failures.append(f"{side}_url")
    if not failures and tokenize(colloquial) == tokenize(official):
        failures.append("same_tokens")
    return failures


def _is_date(value: Any) -> bool:
    return isinstance(value, str) and _DATE.match(value) is not None


def _text(value: Any, limit: int = 80) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= limit and "\n" not in value


def entry_failures(entry: Any) -> List[str]:
    """Fixed codes for one glossary entry: shape, states, decision, and the pair rules."""

    if not isinstance(entry, dict) or set(entry) - _ENTRY_KEYS:
        return ["entry_shape"]
    failures: List[str] = []
    if not isinstance(entry.get("id"), str) or not _ID.match(entry["id"]):
        failures.append("id")
    failures.extend(pair_failures(entry.get("colloquial"), entry.get("official")))
    origin = entry.get("origin")
    if not (
        isinstance(origin, dict)
        and set(origin) == {"kind", "ref"}
        and origin["kind"] in ORIGIN_KINDS
        and _text(origin["ref"])
    ):
        failures.append("origin")
    drafted = entry.get("drafted")
    if not (
        isinstance(drafted, dict)
        and set(drafted) == {"by", "on"}
        and _text(drafted["by"])
        and _is_date(drafted["on"])
    ):
        failures.append("drafted")
    state = entry.get("review_state")
    decision = entry.get("decision")
    if state not in STATES:
        failures.append("review_state")
    elif state == "proposed":
        if decision is not None:
            failures.append("decision")
    elif not (
        isinstance(decision, dict)
        and set(decision) == {"decision", "reviewed_by", "reviewed_on"}
        and decision["decision"] == state
        and _text(decision["reviewed_by"])
        and _is_date(decision["reviewed_on"])
    ):
        failures.append("decision")
    return failures


def document_failures(document: Any) -> List[str]:
    """Fixed codes for the whole file: schema, size of the list, per-entry rules, uniqueness."""

    if not isinstance(document, dict) or set(document) != {"schema_version", "entries"}:
        return [REASON_WRONG_SCHEMA]
    if document["schema_version"] != SCHEMA_VERSION or not isinstance(document["entries"], list):
        return [REASON_WRONG_SCHEMA]
    entries = document["entries"]
    if len(entries) > MAX_ENTRIES:
        return [REASON_INVALID_ENTRY]
    failures: List[str] = []
    ids: set = set()
    approved_pairs: set = set()
    for entry in entries:
        found = entry_failures(entry)
        if found:
            failures.append(REASON_INVALID_ENTRY)
            continue
        if entry["id"] in ids:
            failures.append(REASON_INVALID_ENTRY)
        ids.add(entry["id"])
        if entry["review_state"] == "approved":
            pair = (tokenize(entry["colloquial"]), tokenize(entry["official"]))
            if pair in approved_pairs:
                failures.append(REASON_INVALID_ENTRY)
            approved_pairs.add(pair)
    return sorted(set(failures))


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    size = len(needle)
    return any(tuple(haystack[i : i + size]) == tuple(needle) for i in range(len(haystack) - size + 1))


@dataclass(frozen=True)
class _Rule:
    colloquial: Tuple[str, ...]
    official: str
    official_tokens: Tuple[str, ...]


class QuestionGlossary:
    """The approved pairs of one loaded glossary; immutable after construction."""

    def __init__(self, pairs: Sequence[Tuple[str, str]]) -> None:
        self._pairs: Tuple[Tuple[str, str], ...] = tuple(pairs)
        by_first: Dict[str, List[_Rule]] = {}
        for colloquial, official in self._pairs:
            tokens = tokenize(colloquial)
            by_first.setdefault(tokens[0], []).append(
                _Rule(tokens, official, tokenize(official))
            )
        self._by_first = by_first

    @property
    def approved_count(self) -> int:
        return len(self._pairs)

    def expand(self, question: str) -> str:
        """``question`` plus up to four approved official terms; the original words stay first."""

        if not self._pairs or not isinstance(question, str):
            return question
        tokens = tokenize(question)
        matched: List[_Rule] = []
        index = 0
        while index < len(tokens):
            candidates = [
                rule
                for rule in self._by_first.get(tokens[index], ())
                if tuple(tokens[index : index + len(rule.colloquial)]) == rule.colloquial
            ]
            if not candidates:
                index += 1
                continue
            longest = max(len(rule.colloquial) for rule in candidates)
            matched.extend(rule for rule in candidates if len(rule.colloquial) == longest)
            index += longest
        # Only the first MAX_APPENDED matches are considered, so re-expanding an expanded
        # query (which already holds them) can never add a later one.
        appended: List[str] = []
        seen: List[Tuple[str, ...]] = []
        for rule in matched[:MAX_APPENDED]:
            if _contains(tokens, rule.official_tokens) or rule.official_tokens in seen:
                continue
            seen.append(rule.official_tokens)
            appended.append(rule.official)
        if not appended:
            return question
        return " ".join([question] + appended)

    def identity(self) -> str:
        """First 12 hex of the SHA-256 over the canonical approved pairs."""

        canonical = json.dumps(
            sorted([" ".join(tokenize(c)), o] for c, o in self._pairs),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def cache_suffix(self) -> str:
        """The model-identity suffix for the answer cache; empty with no approved pair."""

        return "+glossary:" + self.identity() if self._pairs else ""


def approved_pairs(document: Mapping[str, Any]) -> List[Tuple[str, str]]:
    """The ``(colloquial, official)`` text of every approved entry of a valid document."""

    return [
        (entry["colloquial"], entry["official"])
        for entry in document["entries"]
        if entry["review_state"] == "approved"
    ]


def parse_setting(value: Optional[str]) -> Tuple[bool, Optional[str]]:
    """``(on, reason)``: unset, empty, and ``on`` enable; ``off`` disables; the rest is flagged."""

    if value is None or value in ("", "on"):
        return True, None
    if value == "off":
        return False, REASON_DISABLED
    return False, REASON_INVALID_SETTING


def load_question_glossary(
    environ: Mapping[str, str], path: Optional[Path] = None
) -> Tuple[Optional[QuestionGlossary], Optional[str]]:
    """``(glossary, None)`` when expansion is on, else ``(None, reason)``. Never raises."""

    on, reason = parse_setting(environ.get(SETTING_ENV))
    if not on:
        return None, reason
    target = Path(path) if path is not None else DEFAULT_PATH
    try:
        if not target.is_file():
            return None, REASON_MISSING
        if target.stat().st_size > MAX_FILE_BYTES:
            return None, REASON_TOO_LARGE
        raw = target.read_bytes()
    except OSError:
        return None, REASON_UNREADABLE
    if len(raw) > MAX_FILE_BYTES:
        return None, REASON_TOO_LARGE
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, REASON_UNREADABLE
    failures = document_failures(document)
    if failures:
        return None, failures[0]
    return QuestionGlossary(approved_pairs(document)), None
