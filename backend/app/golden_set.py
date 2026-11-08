"""Golden question queue: drafts stay out of every score and gate until a person decides.

``knowledge/golden_set.json`` (``golden-set-v1``) holds agent-drafted questions beside the
reviewed ``pac_answer_eval.json``. Each answered item quotes one reviewed passage word for
word; each abstention names the omission it relies on. Nothing here is read by a release
gate, review merge, demo, or load test. Only :func:`approved_cases` turns items into
evaluator cases, and only ``approved`` ones, through ``evaluate_pac_answers.py --golden``.

Standard library, plus the two existing question checks (``screen_question`` and
``out_of_scope_topic``) used to keep drafts from being traps. The clock is injected.
"""

import json
import os
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.generation import normalize_text
from app.input_guardrails import screen_question
from app.question_scope import out_of_scope_topic

VERSION = "golden-set-v1"
QUESTION_TYPES = (
    "procedure",
    "deadline",
    "eligibility_caveat",
    "land_dependent",
    "out_of_scope",
    "colloquial",
)
SEGMENTS = ("secano-convencional", "regadio-convencional", "ecologico", "transversal")
REVIEW_STATES = ("draft", "approved", "rejected")
MIN_ITEMS, MAX_ITEMS = 40, 60
MIN_PER_TYPE = {
    "procedure": 6,
    "deadline": 8,
    "eligibility_caveat": 4,
    "land_dependent": 5,
    "out_of_scope": 6,
    "colloquial": 6,
}
MIN_PER_SEGMENT = 3
MIN_PER_PASSAGE = 2
AUTHOR_REVIEW_ROLE = "author_only"

_ID = re.compile(r"^golden-[0-9]{3}$")
_NAME_EXTRA = " .-'"
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_ITEM_KEYS = {
    "id", "question_type", "segment", "area", "question", "land_context",
    "expected_status", "expected_source_ids", "expected_passage_ids", "critical_facts",
    "anchor", "deliberate_abstention", "drafted", "review_state", "decision",
}
_REQUIRED = {
    "id", "question_type", "segment", "area", "question", "land_context",
    "expected_status", "drafted", "review_state",
}
_KEY_ORDER = (
    "id", "question_type", "segment", "area", "question", "land_context",
    "expected_status", "expected_source_ids", "expected_passage_ids", "critical_facts",
    "anchor", "deliberate_abstention", "drafted", "review_state", "decision",
)


class GoldenSetError(ValueError):
    """The golden file cannot be read or has the wrong structure."""


class DecisionError(ValueError):
    """A decision was refused; ``kind`` picks the pinned owner message."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail


# --- Reading, structure, writing -------------------------------------------------------


def read_document(path: Path) -> Dict[str, Any]:
    """Read the file and check its structure only (no corpus rules)."""

    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GoldenSetError("cannot read a valid golden set file") from exc
    failures = structure_failures(doc)
    if failures:
        raise GoldenSetError(failures[0])
    return doc


def dump_document(doc: Dict[str, Any]) -> str:
    """Stable formatting: fixed key order, two-space indent, no ASCII escaping."""

    ordered = {
        "schema_version": doc["schema_version"],
        "additional_areas": doc["additional_areas"],
        "items": [
            {key: item[key] for key in _KEY_ORDER if key in item} for item in doc["items"]
        ],
    }
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def write_atomically(path: Path, text: str) -> None:
    path = Path(path)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def _is_date(value: Any) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def structure_failures(doc: Any) -> List[str]:
    """Return structural failures (``$.path: rule``); empty when the shape is valid."""

    if (
        not isinstance(doc, dict)
        or set(doc) != {"schema_version", "additional_areas", "items"}
        or doc["schema_version"] != VERSION
        or not isinstance(doc["additional_areas"], list)
        or not isinstance(doc["items"], list)
        or not doc["items"]
    ):
        return ["$: invalid golden set structure"]
    failures: List[str] = []
    for i, area in enumerate(doc["additional_areas"]):
        if (
            not isinstance(area, dict)
            or set(area) != {"id", "kind", "label"}
            or not all(isinstance(area[k], str) and area[k].strip() for k in area)
            or area["kind"] != "topic"
        ):
            failures.append(f"$.additional_areas[{i}]: invalid area")
    for i, item in enumerate(doc["items"]):
        failures.extend(_item_structure(i, item))
        if failures:
            return failures
    return failures


def _item_structure(i: int, item: Any) -> List[str]:
    where = f"$.items[{i}]"
    if not isinstance(item, dict) or not _REQUIRED <= set(item) or set(item) - _ITEM_KEYS:
        return [f"{where}: invalid keys"]
    ident = item["id"]
    if not isinstance(ident, str) or not _ID.match(ident):
        return [f"{where}.id: invalid"]
    where = ident
    if item["question_type"] not in QUESTION_TYPES:
        return [f"{where}: question_type invalid"]
    if item["segment"] not in SEGMENTS:
        return [f"{where}: segment invalid"]
    for key in ("area", "question"):
        if not isinstance(item[key], str) or not item[key].strip():
            return [f"{where}: {key} invalid"]
    if len(item["question"]) > 2000:
        return [f"{where}: question too long"]
    if item["expected_status"] not in ("answered", "abstained"):
        return [f"{where}: expected_status invalid"]
    if not _land_context_ok(item["land_context"]):
        return [f"{where}: land_context invalid"]
    for key in ("expected_source_ids", "expected_passage_ids", "critical_facts"):
        if key in item and not _str_list(item[key]):
            return [f"{where}: {key} invalid"]
    if "anchor" in item:
        anchor = item["anchor"]
        if (
            not isinstance(anchor, dict)
            or set(anchor) != {"source_id", "passage_id", "text"}
            or not all(isinstance(v, str) and v for v in anchor.values())
        ):
            return [f"{where}: anchor invalid"]
    if "deliberate_abstention" in item:
        da = item["deliberate_abstention"]
        if (
            not isinstance(da, dict)
            or set(da) != {"basis"}
            or not isinstance(da["basis"], str)
            or not da["basis"].strip()
        ):
            return [f"{where}: deliberate_abstention invalid"]
    drafted = item["drafted"]
    if (
        not isinstance(drafted, dict)
        or set(drafted) != {"by", "on"}
        or not isinstance(drafted["by"], str)
        or not drafted["by"].strip()
        or not _is_date(drafted["on"])
    ):
        return [f"{where}: drafted invalid"]
    if item["review_state"] not in REVIEW_STATES:
        return [f"{where}: review_state invalid"]
    if item["review_state"] == "draft":
        if "decision" in item:
            return [f"{where}: a draft must not carry a decision"]
    else:
        decision = item.get("decision")
        expected = item["review_state"]
        if (
            not isinstance(decision, dict)
            or set(decision) != {"decision", "reviewed_by", "reviewed_on"}
            or decision["decision"] != expected
            or not valid_name(decision["reviewed_by"])
            or not _is_date(decision["reviewed_on"])
        ):
            return [f"{where}: decision invalid or missing"]
    return []


def _land_context_ok(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"mode", "lands"}:
        return False
    if value["mode"] not in ("general", "all_active", "selected") or not isinstance(value["lands"], list):
        return False
    if (value["mode"] == "general") != (not value["lands"]):
        return False
    ids = []
    for land in value["lands"]:
        if not isinstance(land, dict) or "id" not in land or not isinstance(land["id"], str) or not land["id"]:
            return False
        if set(land) - {"id", "municipality", "water_regime", "production_method"}:
            return False
        if land.get("water_regime", "unknown") not in ("dryland", "irrigated", "mixed", "unknown"):
            return False
        if land.get("production_method", "unknown") not in ("conventional", "organic", "mixed", "unknown"):
            return False
        ids.append(land["id"])
    return len(ids) == len(set(ids))


def valid_name(name: Any) -> bool:
    """1-80 characters: letters, spaces, ``.``, ``-``, ``'``; at least one letter."""

    return (
        isinstance(name, str)
        and 1 <= len(name) <= 80
        and name.strip() == name
        and any(c.isalpha() for c in name)
        and all(c.isalpha() or c in _NAME_EXTRA for c in name)
    )


# --- Corpus rules ------------------------------------------------------------------------


def _question_key(item_or_case: Dict[str, Any]) -> Tuple[str, str]:
    text = " ".join(_NON_ALNUM.split(normalize_text(item_or_case["question"]))).strip()
    lands = json.dumps(item_or_case["land_context"], sort_keys=True, ensure_ascii=False)
    return text, lands


def anchor_failures(item: Dict[str, Any], catalog: Any, passages: Any, omissions: Sequence[str]) -> List[str]:
    """The proof rules of one item against the reviewed corpus (scenario 2)."""

    ident = item["id"]
    sources = {s["id"]: s for s in catalog["sources"]}
    by_id = {p["id"]: p for p in passages["passages"]}
    out: List[str] = []
    if item["expected_status"] == "abstained":
        for key in ("anchor", "expected_source_ids", "expected_passage_ids", "critical_facts"):
            if item.get(key):
                out.append(f"{ident}: abstention must not carry {key}")
        basis = item.get("deliberate_abstention", {}).get("basis")
        if basis is None:
            out.append(f"{ident}: abstention must declare deliberate_abstention.basis")
        elif basis not in omissions:
            out.append(f"{ident}: deliberate_abstention.basis is not a declared omission")
        return out
    if "deliberate_abstention" in item:
        out.append(f"{ident}: answered item must not declare deliberate_abstention")
    anchor = item.get("anchor")
    if anchor is None:
        return out + [f"{ident}: answered item needs an anchor"]
    source = sources.get(anchor["source_id"])
    if source is None:
        out.append(f"{ident}: anchor source_id is not in the catalog")
    elif source.get("review_status") != "approved" or source.get("lifecycle_status") != "current":
        out.append(f"{ident}: anchor source is not approved and current")
    passage = by_id.get(anchor["passage_id"])
    if passage is None:
        out.append(f"{ident}: anchor passage_id is not in the passages")
    elif passage["source_id"] != anchor["source_id"]:
        out.append(f"{ident}: anchor passage belongs to another source")
    elif anchor["text"] not in passage["text"]:
        out.append(f"{ident}: anchor text is not an exact quote of the passage")
    expected_passages = item.get("expected_passage_ids", [])
    expected_sources = item.get("expected_source_ids", [])
    if anchor["passage_id"] not in expected_passages:
        out.append(f"{ident}: expected_passage_ids must contain the anchor passage")
    unknown = [p for p in expected_passages if p not in by_id]
    if unknown:
        out.append(f"{ident}: expected_passage_ids has unknown passage {unknown[0]}")
    needed = {by_id[p]["source_id"] for p in expected_passages if p in by_id}
    if not needed <= set(expected_sources):
        out.append(f"{ident}: expected_source_ids must cover every expected passage source")
    if any(s not in sources for s in expected_sources):
        out.append(f"{ident}: expected_source_ids has an unknown source")
    texts = [by_id[p]["text"] for p in expected_passages if p in by_id]
    for fact in item.get("critical_facts", []):
        if not any(fact in t for t in texts):
            out.append(f"{ident}: critical fact is not an exact quote of an expected passage: {fact!r}")
    return out


def validate(
    doc: Dict[str, Any],
    catalog: Any,
    passages: Any,
    base_cases: Sequence[Dict[str, Any]],
    base_coverage: Dict[str, Any],
) -> List[str]:
    """Every failure of the structure, anchor, safety, duplicate, area, and distribution rules."""

    failures = structure_failures(doc)
    if failures:
        return failures
    omissions = base_coverage["omissions"]
    base_areas = {a["id"] for a in base_coverage["areas"]}
    extra_ids = [a["id"] for a in doc["additional_areas"]]
    if len(extra_ids) != len(set(extra_ids)) or set(extra_ids) & base_areas:
        failures.append("$.additional_areas: ids must be new and unique")
    declared = base_areas | set(extra_ids)
    seen = {_question_key(c) for c in base_cases}
    ids = set()
    for item in doc["items"]:
        ident = item["id"]
        if ident in ids or ident in {c["id"] for c in base_cases}:
            failures.append(f"{ident}: duplicate or colliding id")
        ids.add(ident)
        if item["area"] not in declared:
            failures.append(f"{ident}: area is not declared")
        failures.extend(anchor_failures(item, catalog, passages, omissions))
        reason = screen_question(item["question"])
        if reason is not None:
            failures.append(f"{ident}: question is flagged by the input guardrails ({reason})")
        if item["expected_status"] == "answered" and out_of_scope_topic(item["question"]) is not None:
            failures.append(f"{ident}: an answered question matches an out-of-scope topic")
        key = _question_key(item)
        if key in seen:
            failures.append(f"{ident}: question and lands duplicate another item or reviewed case")
        seen.add(key)
    failures.extend(distribution_failures(doc["items"], passages, base_areas))
    return failures


def distribution_summary(items: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    answered = [i for i in items if i["expected_status"] == "answered" and "anchor" in i]
    return {
        "type": dict(sorted(Counter(i["question_type"] for i in items).items())),
        "segment": dict(sorted(Counter(i["segment"] for i in items).items())),
        "passage": dict(sorted(Counter(i["anchor"]["passage_id"] for i in answered).items())),
        "area": dict(sorted(Counter(i["area"] for i in items).items())),
        "state": dict(sorted(Counter(i["review_state"] for i in items).items())),
    }


def distribution_failures(
    items: Sequence[Dict[str, Any]], passages: Any, base_areas: Sequence[str]
) -> List[str]:
    out: List[str] = []
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        out.append(f"distribution: {len(items)} items, need {MIN_ITEMS} to {MAX_ITEMS}")
    if [i["id"] for i in items] != [f"golden-{n:03d}" for n in range(1, len(items) + 1)]:
        out.append("distribution: ids must run golden-001 upward without gaps")
    summary = distribution_summary(items)
    for kind, minimum in MIN_PER_TYPE.items():
        if summary["type"].get(kind, 0) < minimum:
            out.append(f"distribution: question_type {kind} has {summary['type'].get(kind, 0)}, need {minimum}")
    for segment in SEGMENTS:
        if summary["segment"].get(segment, 0) < MIN_PER_SEGMENT:
            out.append(f"distribution: segment {segment} has {summary['segment'].get(segment, 0)}, need {MIN_PER_SEGMENT}")
    for passage in passages["passages"]:
        if summary["passage"].get(passage["id"], 0) < MIN_PER_PASSAGE:
            out.append(f"distribution: passage {passage['id']} anchors fewer than {MIN_PER_PASSAGE} answered items")
    for area in base_areas:
        if summary["area"].get(area, 0) < 1:
            out.append(f"distribution: coverage area {area} is not used")
    return out


def load_golden(
    path: Path,
    catalog: Any,
    passages: Any,
    base_cases: Sequence[Dict[str, Any]],
    base_coverage: Dict[str, Any],
) -> Dict[str, Any]:
    """Read and fully validate the file; raise :class:`GoldenSetError` on any failure."""

    doc = read_document(path)
    failures = validate(doc, catalog, passages, base_cases, base_coverage)
    if failures:
        raise GoldenSetError("; ".join(failures[:5]))
    return doc


# --- Scoring ----------------------------------------------------------------------------


def state_counts(doc: Dict[str, Any]) -> Dict[str, int]:
    counts = Counter(i["review_state"] for i in doc["items"])
    return {state: counts.get(state, 0) for state in ("approved", "draft", "rejected")}


def approved_cases(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Only ``approved`` items, as ``pac-answer-eval-v2`` cases. Drafts and rejected never appear."""

    cases = []
    for item in doc["items"]:
        if item["review_state"] != "approved":
            continue
        case: Dict[str, Any] = {
            "id": item["id"],
            "area": item["area"],
            "question": item["question"],
            "land_context": item["land_context"],
            "expected_status": item["expected_status"],
            "review": {
                "reviewed_by": item["decision"]["reviewed_by"],
                "reviewed_on": item["decision"]["reviewed_on"],
                "role": AUTHOR_REVIEW_ROLE,
            },
        }
        for key in ("expected_source_ids", "expected_passage_ids", "critical_facts"):
            if item.get(key):
                case[key] = list(item[key])
        cases.append(case)
    return cases


# --- Readable list ---------------------------------------------------------------------


_STATE_WORDS = {"draft": "waiting", "approved": "approved", "rejected": "rejected"}
_WATER = {"dryland": "secano", "irrigated": "regadío", "mixed": "mixto", "unknown": "desconocido"}
_METHOD = {"conventional": "convencional", "organic": "ecológico", "mixed": "mixto", "unknown": "desconocido"}


def item_number(doc: Dict[str, Any], item: Dict[str, Any]) -> int:
    return doc["items"].index(item) + 1


def render_item(doc: Dict[str, Any], item: Dict[str, Any], catalog: Any, passages: Any) -> str:
    sources = {s["id"]: s for s in catalog["sources"]}
    by_id = {p["id"]: p for p in passages["passages"]}
    total = len(doc["items"])
    lines = [
        f"[{item_number(doc, item)} of {total}] {item['id']}  type: {item['question_type']}  "
        f"segment: {item['segment']}  area: {item['area']}  state: {_STATE_WORDS[item['review_state']]}",
        f"  Question: {item['question']}",
    ]
    lands = item["land_context"]["lands"]
    if lands:
        parts = [
            f"{land['id']} ({_WATER.get(land.get('water_regime', 'unknown'))}, "
            f"{_METHOD.get(land.get('production_method', 'unknown'))})"
            for land in lands
        ]
        lines.append(f"  Lands: {'; '.join(parts)}")
    if item["expected_status"] == "abstained":
        basis = item["deliberate_abstention"]["basis"]
        lines.append(f"  Expected: a deliberate \"no lo sé\" (basis: {basis}); the reviewed sources do not cover it")
    else:
        anchor = item["anchor"]
        passage = by_id[anchor["passage_id"]]
        source = sources[anchor["source_id"]]
        lines.append("  Expected: an answer that quotes the source below")
        lines.append(f"  Source: {source['title']}")
        lines.append(f"  Location: {passage['location']}")
        lines.append(f"  Link: {source['original_url']}")
        lines.append(f"  Quoted text: \"{anchor['text']}\"")
        if item.get("critical_facts"):
            lines.append(f"  Must say: {' | '.join(item['critical_facts'])}")
    if item["review_state"] != "draft":
        d = item["decision"]
        lines.append(f"  Decision: {d['decision']} by {d['reviewed_by']} on {d['reviewed_on']}")
    return "\n".join(lines)


def render_list(doc: Dict[str, Any], catalog: Any, passages: Any, only_waiting: bool) -> str:
    items = [i for i in doc["items"] if i["review_state"] == "draft" or not only_waiting]
    return "\n\n".join(render_item(doc, i, catalog, passages) for i in items) + ("\n" if items else "")


# --- Decisions --------------------------------------------------------------------------


def resolve_refs(doc: Dict[str, Any], refs: Sequence[str]) -> List[int]:
    """Map numbers (``7``) and ids (``golden-007``) to 0-based indexes; unknown refs raise."""

    ids = [i["id"] for i in doc["items"]]
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
    path: Path,
    decision: str,
    name: str,
    refs: Sequence[str],
    today: date,
    catalog: Any,
    passages: Any,
    omissions: Sequence[str],
) -> Tuple[int, int]:
    """Validate everything, then rewrite the file once. Returns (recorded, still waiting)."""

    if decision not in ("approve", "reject") or not valid_name(name) or not refs:
        raise DecisionError("usage")
    doc = read_document(path)
    indexes = resolve_refs(doc, refs)
    state = "approved" if decision == "approve" else "rejected"
    if state == "approved":
        for index in indexes:
            if anchor_failures(doc["items"][index], catalog, passages, omissions):
                raise DecisionError("anchor", str(index + 1))
    for index in indexes:
        item = doc["items"][index]
        item["review_state"] = state
        item["decision"] = {"decision": state, "reviewed_by": name, "reviewed_on": today.isoformat()}
    write_atomically(path, dump_document(doc))
    return len(indexes), state_counts(doc)["draft"]
