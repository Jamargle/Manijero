"""Offline review tooling for the question glossary (``question_rewriting``).

Seeds proposals from a ``notice-review-v1`` file, lists the waiting pairs readably, records the
owner's decisions, and checks that the approved pairs break no reviewed case. Developer and owner
commands only: nothing on the ``/ask`` path imports this module. The runtime rules (file shape,
entry rules, matching) live in :mod:`app.question_glossary`; this module adds the screening that
needs the guardrails and the notice pipeline's personal-data rules.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app import golden_set
from app.input_guardrails import screen_question
from app.notice_pipeline import SCHEMA_VERSION as NOTICE_SCHEMA, personal_data_codes
from app.question_glossary import (
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    SCHEMA_VERSION,
    QuestionGlossary,
    document_failures,
    entry_failures,
    pair_failures,
)
from app.retrieval import tokenize

DRAFTED_BY = "agent:question_rewriting"
_KEY_ORDER = ("id", "colloquial", "official", "origin", "drafted", "review_state", "decision")


class GlossaryReviewError(ValueError):
    """The glossary or notice-review file cannot be used; carries no pair text."""


class DecisionError(ValueError):
    """A decision that cannot be recorded; ``kind`` is ``usage``, ``unknown``, or ``entry``."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(kind)
        self.kind = kind
        self.detail = detail


# --- File ------------------------------------------------------------------------------


def empty_document() -> Dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "entries": []}


def read_document(path: Path) -> Dict[str, Any]:
    """Read and fully check the glossary file; raises :class:`GlossaryReviewError`."""

    try:
        raw = Path(path).read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            raise GlossaryReviewError("glossary file is too large")
        document = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise GlossaryReviewError("cannot read a valid glossary file") from exc
    if document_failures(document):
        raise GlossaryReviewError("glossary file breaks the file rules")
    return document


def dump_document(document: Dict[str, Any]) -> str:
    """Stable formatting: fixed key order, two-space indent, no ASCII escaping."""

    ordered = {
        "schema_version": document["schema_version"],
        "entries": [
            {key: entry[key] for key in _KEY_ORDER if key in entry}
            for entry in document["entries"]
        ],
    }
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def state_counts(document: Dict[str, Any]) -> Dict[str, int]:
    counts = Counter(entry["review_state"] for entry in document["entries"])
    return {state: counts.get(state, 0) for state in ("proposed", "approved", "rejected")}


# --- Screening -------------------------------------------------------------------------


def screen_pair(colloquial: Any, official: Any) -> List[str]:
    """Runtime entry rules plus the question screen and personal-data codes; fixed codes only."""

    failures = pair_failures(colloquial, official)
    if failures:
        return failures
    for side, text in (("colloquial", colloquial), ("official", official)):
        if screen_question(text) is not None:
            failures.append(f"{side}_screened")
        if personal_data_codes(text):
            failures.append(f"{side}_personal_data")
    return failures


def entry_rule_failures(entry: Dict[str, Any]) -> List[str]:
    return entry_failures(entry) or screen_pair(entry["colloquial"], entry["official"])


def _pair_key(colloquial: str, official: str) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    return tokenize(colloquial), tokenize(official)


# --- Seed ------------------------------------------------------------------------------


def read_notice_review(path: Path) -> Tuple[List[Tuple[str, str]], str]:
    """The merged ``(colloquial, standard)`` pairs and the first 12 hex of the file's SHA-256."""

    try:
        raw = Path(path).read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise GlossaryReviewError("cannot read a valid notice review file") from exc
    if not isinstance(document, dict) or document.get("schema_version") != NOTICE_SCHEMA:
        raise GlossaryReviewError("not a notice review file")
    vocabulary = document.get("vocabulary")
    if not isinstance(vocabulary, list):
        raise GlossaryReviewError("not a notice review file")
    pairs: List[Tuple[str, str]] = []
    for item in vocabulary:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) for key in ("colloquial", "standard")
        ):
            raise GlossaryReviewError("not a notice review file")
        pairs.append((item["colloquial"], item["standard"]))
    return pairs, hashlib.sha256(raw).hexdigest()[:12]


def next_id(document: Dict[str, Any]) -> str:
    numbers = [int(entry["id"][3:]) for entry in document["entries"]]
    return "gl-{:03d}".format(max(numbers, default=0) + 1)


def add_proposal(
    document: Dict[str, Any], colloquial: str, official: str, origin: Dict[str, str], today: date
) -> bool:
    """Append a ``proposed`` entry unless the pair exists or fails screening; True when added."""

    key = _pair_key(colloquial, official)
    if any(_pair_key(e["colloquial"], e["official"]) == key for e in document["entries"]):
        return False
    if len(document["entries"]) >= MAX_ENTRIES or screen_pair(colloquial, official):
        return False
    document["entries"].append(
        {
            "id": next_id(document),
            "colloquial": colloquial,
            "official": official,
            "origin": origin,
            "drafted": {"by": DRAFTED_BY, "on": today.isoformat()},
            "review_state": "proposed",
        }
    )
    return True


def seed_from_notice(path: Path, notice_review: Path, today: date) -> Tuple[int, int, int]:
    """Add the notice vocabulary as proposals. Returns ``(added, already_present, refused)``."""

    pairs, digest = read_notice_review(notice_review)
    document = read_document(path) if Path(path).exists() else empty_document()
    added = present = refused = 0
    origin = {"kind": "notice", "ref": digest}
    for colloquial, official in pairs:
        known = {_pair_key(e["colloquial"], e["official"]) for e in document["entries"]}
        if _pair_key(colloquial, official) in known:
            present += 1
        elif add_proposal(document, colloquial.strip(), official.strip(), dict(origin), today):
            added += 1
        else:
            refused += 1
    if added:
        golden_set.write_atomically(Path(path), dump_document(document))
    return added, present, refused


# --- Readable list ---------------------------------------------------------------------


def _passage_count(official: str, passages: Any) -> int:
    needle = tokenize(official)
    size = len(needle)
    count = 0
    for passage in passages["passages"]:
        text = tokenize(passage["text"])
        if any(text[i : i + size] == needle for i in range(len(text) - size + 1)):
            count += 1
    return count


def _origin_words(entry: Dict[str, Any]) -> str:
    kind = entry["origin"]["kind"]
    if kind == "notice":
        return "un aviso de cooperativa revisado (archivo {})".format(entry["origin"]["ref"])
    return "la pregunta de prueba {}".format(entry["origin"]["ref"])


def render_entry(
    number: int, entry: Dict[str, Any], passages: Any, golden: Optional[Dict[str, Any]]
) -> str:
    lines = [
        "{}. {}  [{}]".format(number, entry["id"], entry["review_state"]),
        "   The grower says:  {}".format(entry["colloquial"]),
        "   Official term:    {}".format(entry["official"]),
        "   Comes from:       {}".format(_origin_words(entry)),
        "   Reviewed passages containing the official term: {}".format(
            _passage_count(entry["official"], passages)
        ),
    ]
    if entry["origin"]["kind"] == "golden" and golden is not None:
        item = next((i for i in golden["items"] if i["id"] == entry["origin"]["ref"]), None)
        if item is not None:
            lines.append("   Golden question:  {}".format(item["question"]))
            lines.append(
                "   Words added to the search: {}".format(
                    QuestionGlossary([(entry["colloquial"], entry["official"])]).expand(
                        item["question"]
                    )[len(item["question"]) :].strip()
                    or "(none)"
                )
            )
    return "\n".join(lines)


def render_list(
    document: Dict[str, Any], passages: Any, golden: Optional[Dict[str, Any]], only_waiting: bool
) -> str:
    blocks = [
        render_entry(number, entry, passages, golden)
        for number, entry in enumerate(document["entries"], start=1)
        if not only_waiting or entry["review_state"] == "proposed"
    ]
    return "\n\n".join(blocks)


# --- Decide ----------------------------------------------------------------------------


def resolve_refs(document: Dict[str, Any], refs: Sequence[str]) -> List[int]:
    ids = [entry["id"] for entry in document["entries"]]
    indexes: List[int] = []
    unknown: List[str] = []
    for ref in refs:
        index: Optional[int] = None
        if ref.isascii() and ref.isdigit() and 1 <= int(ref) <= len(ids):
            index = int(ref) - 1
        elif ref in ids:
            index = ids.index(ref)
        if index is None:
            unknown.append(ref)
        elif index not in indexes:
            indexes.append(index)
    if unknown:
        raise DecisionError("unknown", " ".join(unknown))
    return indexes


def record_decision(
    path: Path, decision: str, name: str, refs: Sequence[str], today: date
) -> Tuple[int, int]:
    """Validate everything, then rewrite the file once. Returns ``(recorded, still waiting)``."""

    if decision not in ("approve", "reject") or not golden_set.valid_name(name) or not refs:
        raise DecisionError("usage")
    document = read_document(path)
    indexes = resolve_refs(document, refs)
    state = "approved" if decision == "approve" else "rejected"
    if state == "approved":
        for index in indexes:
            if entry_rule_failures(document["entries"][index]):
                raise DecisionError("entry", str(index + 1))
    for index in indexes:
        entry = document["entries"][index]
        entry["review_state"] = state
        entry["decision"] = {"decision": state, "reviewed_by": name, "reviewed_on": today.isoformat()}
    golden_set.write_atomically(Path(path), dump_document(document))
    return len(indexes), state_counts(document)["proposed"]


# --- Check -----------------------------------------------------------------------------


_MATCH_KEYS = ("expected_state_match", "source_match", "passage_match", "critical_facts_match")


def _run(
    cases: List[Dict[str, Any]],
    coverage: Any,
    catalog: Any,
    passages: Any,
    as_of: date,
    active_campaign: str,
    k: int,
    glossary: Optional[QuestionGlossary],
) -> Dict[str, bool]:
    """Case id -> whether state, source, passage, and critical facts all matched."""

    from fastapi.testclient import TestClient

    from app.answer_eval import evaluate
    from app.ask_api import CorpusDocuments
    from app.release_gates import evaluation_app

    application = evaluation_app(
        CorpusDocuments(catalog=catalog, passages=passages), as_of, active_campaign, k
    )
    application.state.question_glossary = glossary
    report = evaluate(cases, TestClient(application), catalog, passages, k, coverage=coverage)
    return {row["id"]: all(row[key] for key in _MATCH_KEYS) for row in report["case_rows"]}


def check(
    document: Dict[str, Any],
    cases: List[Dict[str, Any]],
    coverage: Any,
    catalog: Any,
    passages: Any,
    as_of: date,
    active_campaign: str,
    k: int,
) -> Tuple[List[str], str]:
    """``(failure lines, summary line)``; lines name ids only."""

    failures = [
        "{}: entry rules: {}".format(entry["id"], ",".join(codes))
        for entry in document["entries"]
        for codes in [entry_rule_failures(entry)]
        if codes
    ]
    approved = [e for e in document["entries"] if e["review_state"] == "approved"]
    pairs = [(e["colloquial"], e["official"]) for e in approved]
    without = _run(cases, coverage, catalog, passages, as_of, active_campaign, k, None)
    improved = 0
    if approved and not failures:
        with_glossary = _run(
            cases, coverage, catalog, passages, as_of, active_campaign, k, QuestionGlossary(pairs)
        )
        questions = {case["id"]: case["question"] for case in cases}
        for case_id, passed in without.items():
            if passed and not with_glossary[case_id]:
                fired = [
                    e["id"]
                    for e in approved
                    if QuestionGlossary([(e["colloquial"], e["official"])]).expand(questions[case_id])
                    != questions[case_id]
                ]
                failures.append(
                    "{}: breaks with the glossary; pairs fired: {}".format(case_id, ",".join(fired))
                )
            elif with_glossary[case_id] and not passed:
                improved += 1
    counts = state_counts(document)
    summary = (
        "glossary check: {} entries OK (proposed={}, approved={}, rejected={}); "
        "{} cases checked, {} improved"
    ).format(len(document["entries"]), counts["proposed"], counts["approved"], counts["rejected"], len(cases), improved)
    return failures, summary
