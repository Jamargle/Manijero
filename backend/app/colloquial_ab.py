"""Compare no rewriting, the pinned glossary, and glossary plus local-model rewriting.

Approved variants of the golden questions (``backend/config/variants.json``) are scored
three ways through the same in-process ``/ask`` path. Only ``approved`` variants are ever
scored; the expectation, land context, type, area, and segment come from the approved parent
at load, so they cannot drift. The model arm asks the already-pinned
``backend/config/local_generation_model.json`` (loopback Ollama, temperature 0, seed 0) for up
to four *official* terms per variant and appends them after the glossary's terms, never
replacing the grower's words.

Report only: the command reports the owner's rule (strictly better hit@5 than no rewriting and
no approved trap worse) and changes no default, threshold, gate, route, or corpus byte. Reports,
the review list, and the model-term cache stay under ``build/colloquial-ab/``; ``knowledge/`` is
never written.

Standard library plus :mod:`app.eval_metrics`, :mod:`app.question_glossary`,
:mod:`app.golden_set`, and :mod:`app.trap_set`. Model modules are imported only inside
:func:`prepare_rewrites`; nothing here imports the model at module import.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app import eval_metrics, golden_set, trap_set
from app.input_guardrails import screen_question
from app.question_glossary import (
    DEFAULT_PATH as GLOSSARY_PATH,
    MAX_APPENDED,
    SETTING_ENV as GLOSSARY_ENV,
    QuestionGlossary,
    load_question_glossary,
)
from app.question_scope import out_of_scope_topic
from app.retrieval import tokenize

SCHEMA_VERSION = "colloquial-ab-report-v1"
VARIANTS_VERSION = "colloquial-variants-v1"
REWRITES_VERSION = "colloquial-rewrites-v1"
K = 5
MODES = ("no_rewriting", "glossary", "glossary_plus_model")

STATES = ("draft", "approved", "rejected")
STATE_LABELS = {"draft": "waiting", "approved": "approved", "rejected": "rejected"}

VARIANTS = 53
MAX_QUESTION_CHARS = 200
MAX_VARIANT_TERMS = 4
MAX_MODEL_TERMS = 4
MAX_TOTAL_APPENDED = 8
TERM_MAX_TOKENS = 8
TERM_MAX_CHARS = 80

MODEL_REWRITTEN = "rewritten"
MODEL_EMPTY = "empty"
MODEL_REJECTED = "rejected"
MODEL_SKIPPED_SCREENED = "skipped_screened"
MODEL_STATUSES = (MODEL_REWRITTEN, MODEL_EMPTY, MODEL_REJECTED, MODEL_SKIPPED_SCREENED)
MODEL_NOT_USED = "not_used"
MODEL_NOT_PREPARED = "not_prepared"

DRAFTED_BY = "agent:colloquial_ab_evaluation"
CASE_SET_COLLOQUIAL = "colloquial"
CASE_SET_GOLDEN = "golden"
CASE_SET_TRAP = "trap"

TERMS_INSTRUCTION = (
    "Eres un asistente que ayuda a buscar en documentos oficiales de la PAC en Andalucía. "
    "Recibes una pregunta escrita por un agricultor. Devuelve SOLO un objeto JSON con la clave "
    '"terms": una lista de como máximo 4 términos oficiales en español que aparecen en los '
    "documentos oficiales y que sirven para buscar la respuesta. No expliques nada, no cites "
    "enlaces, no inventes números ni fechas, y no repitas las palabras del agricultor."
)
TERMS_INSTRUCTION_VERSION = "colloquial-terms-v1"
TERMS_JSON_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"terms": {"type": "array", "items": {"type": "string"}}},
    "required": ["terms"],
}

MODEL_STATUS_LABELS = {
    MODEL_REWRITTEN: "rewritten",
    MODEL_EMPTY: "empty",
    MODEL_REJECTED: "rejected",
    MODEL_SKIPPED_SCREENED: "skipped",
}

FAILURES: Mapping[str, str] = {
    "invalid_inputs": "the reviewed files or the variant list could not be read; a developer must check them.",
    "no_approved_variants": "no colloquial variant is approved yet; the owner must approve at least one with ./scripts/init.sh --colloquial-decide.",
    "rewrites_missing": "the model rewrites are missing; run prepare first.",
    "rewrites_stale": "the model rewrites are out of date; run prepare again.",
    "model_unavailable": "the pinned local model is not available; start Ollama with the pinned model, or run ./scripts/init.sh --local-rag-setup.",
    "ask_failed": "the in-process /ask route did not return a valid answer; a developer must check the backend.",
    "unsafe_output_path": "the output folder is not allowed; it must be outside knowledge/ and must not overwrite an input.",
    "internal_error": "something unexpected stopped the run; a developer can read build/colloquial-ab/last-error.log.",
}

LIMITS = (
    "The colloquial variants are agent-drafted; only the owner-approved ones are scored.",
    "The three arms share corpus, campaign, as-of date, k=5, extractive drafting, cache off, and case order; only the query expansion differs.",
    "Small reviewed sets, BM25 extractive retrieval, and one pinned local model on one Mac; no quality or legal claim.",
    "Report only: the adoption rule is reported and no default, threshold, or gate changes.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"
DEFAULT_VARIANTS = REPO_ROOT / "backend" / "config" / "colloquial_variants.json"
DEFAULT_ROOT = REPO_ROOT / "build" / "colloquial-ab"

_ID = re.compile(r"^coll-[0-9]{3}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_URL = re.compile(r"(?i)(?:https?://|www\.|\b[\w-]+\.(?:com|es|org|net|eu|gob|info|cat)\b)")
_VARIANT_KEYS = {
    "id",
    "parent_id",
    "question",
    "colloquial_terms",
    "drafted",
    "review_state",
    "decision",
}
_KEY_ORDER = (
    "id",
    "parent_id",
    "question",
    "colloquial_terms",
    "drafted",
    "review_state",
    "decision",
)


class ColloquialAbort(Exception):
    """A fixed failure that ends the command before any report is written."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VariantsError(ValueError):
    """The variant file cannot be used; carries no question text."""


class DecisionError(ValueError):
    """A decision that cannot be recorded; ``kind`` is ``usage``, ``unknown``, ``entry``, ``file``."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(kind)
        self.kind = kind
        self.detail = detail


# --- Variant file -----------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_date(value: Any) -> bool:
    return isinstance(value, str) and _DATE.match(value) is not None


def _text(value: Any, limit: int = 80) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= limit and "\n" not in value


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    size = len(needle)
    return size > 0 and any(
        tuple(haystack[i : i + size]) == tuple(needle)
        for i in range(len(haystack) - size + 1)
    )


def _single_line(value: str) -> bool:
    return "\n" not in value and "\r" not in value and not any(ord(c) < 32 for c in value)


def entry_failures(entry: Any) -> List[str]:
    """Fixed codes for one entry's shape, state, and decision metadata."""

    if (
        not isinstance(entry, dict)
        or not _VARIANT_KEYS <= set(entry)
        or set(entry) - _VARIANT_KEYS
    ):
        return ["variant_shape"]
    failures: List[str] = []
    if not isinstance(entry.get("id"), str) or not _ID.match(entry["id"]):
        failures.append("id")
    if not isinstance(entry.get("parent_id"), str) or not entry["parent_id"].startswith(
        "golden-"
    ):
        failures.append("parent_id")
    if not isinstance(entry.get("question"), str):
        failures.append("question_shape")
    terms = entry.get("colloquial_terms")
    if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
        failures.append("terms_shape")
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
    elif state == "draft":
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
    """Fixed codes for the whole file: schema, digest shape, per-entry shape, unique ids."""

    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "golden_sha256",
        "variants",
    }:
        return ["wrong_schema"]
    if (
        document["schema_version"] != VARIANTS_VERSION
        or not isinstance(document["golden_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", document["golden_sha256"])
        or not isinstance(document["variants"], list)
    ):
        return ["wrong_schema"]
    failures: List[str] = []
    ids: set = set()
    for entry in document["variants"]:
        failures.extend(entry_failures(entry))
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            if entry["id"] in ids:
                failures.append("duplicate_id")
            ids.add(entry["id"])
    return sorted(set(failures))


def _shape_failures(term: Any) -> List[str]:
    """The common shape rules of a variant term or a model term."""

    if not isinstance(term, str):
        return ["term_not_text"]
    codes: List[str] = []
    if not term.strip() or len(term) > TERM_MAX_CHARS:
        codes.append("term_length")
    if not _single_line(term):
        codes.append("term_multiline")
    if not 1 <= len(tokenize(term)) <= TERM_MAX_TOKENS:
        codes.append("term_tokens")
    if any(c.isdigit() for c in term):
        codes.append("term_digit")
    if _URL.search(term):
        codes.append("term_url")
    if screen_question(term) is not None:
        codes.append("term_screened")
    return codes


def variant_term_failures(
    term: Any,
    *,
    variant: str,
    parent: str,
    seen: Sequence[Tuple[str, ...]] = (),
) -> List[str]:
    """A variant term must be new grower wording that occurs in the variant."""

    codes = _shape_failures(term)
    tokens = tokenize(term)
    if not _contains(tokenize(variant), tokens):
        codes.append("term_missing")
    if _contains(tokenize(parent), tokens):
        codes.append("term_in_parent")
    if tuple(tokens) in {tuple(item) for item in seen}:
        codes.append("term_duplicate")
    return codes


def model_term_failures(
    term: Any,
    *,
    question: str,
    expanded: str,
    seen: Sequence[Tuple[str, ...]] = (),
) -> List[str]:
    """A model term must be official wording not already present in the query or expansion."""

    codes = _shape_failures(term)
    tokens = tokenize(term)
    if _contains(tokenize(question), tokens):
        codes.append("term_in_question")
    if _contains(tokenize(expanded), tokens):
        codes.append("term_in_expansion")
    if tuple(tokens) in {tuple(item) for item in seen}:
        codes.append("term_duplicate")
    return codes


def _basis_omission(parent: Mapping[str, Any], omissions: Sequence[str]) -> Optional[str]:
    basis = (parent.get("deliberate_abstention") or {}).get("basis")
    return basis if basis in omissions else None


def variant_failures(
    variant: Mapping[str, Any],
    parent: Mapping[str, Any],
    *,
    duplicate_ids: Sequence[str] = (),
    omissions: Sequence[str] = (),
) -> List[str]:
    """The scenario-2 rules of one variant against its approved parent."""

    question = variant.get("question")
    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > MAX_QUESTION_CHARS
    ):
        return ["question_length"]
    codes: List[str] = []
    if not _single_line(question):
        codes.append("question_multiline")
    if screen_question(question) is not None:
        codes.append("question_screened")
    if _URL.search(question):
        codes.append("question_url")
    parent_tokens = tokenize(parent["question"])
    tokens = tokenize(question)
    if tokens == parent_tokens:
        codes.append("question_same_as_parent")
    if duplicate_ids:
        codes.append("question_duplicate")
    for token in tokens:
        if any(c.isdigit() for c in token) and token not in parent_tokens:
            codes.append("question_digit")
            break
    if parent["expected_status"] == "answered":
        if out_of_scope_topic(question) is not None:
            codes.append("question_out_of_scope")
    else:
        omission = _basis_omission(parent, omissions)
        if omission is not None:
            topic = out_of_scope_topic(question)
            if topic is None or topic.omission != omission:
                codes.append("question_omission")
    terms = variant.get("colloquial_terms")
    if not isinstance(terms, list):
        return sorted(set(codes + ["terms_shape"]))
    if parent["expected_status"] == "answered":
        if not 1 <= len(terms) <= MAX_VARIANT_TERMS:
            codes.append("terms_count")
    elif len(terms) > MAX_VARIANT_TERMS:
        codes.append("terms_count")
    seen: List[Tuple[str, ...]] = []
    for term in terms:
        if isinstance(term, str):
            codes.extend(
                variant_term_failures(
                    term, variant=question, parent=parent["question"], seen=seen
                )
            )
            seen.append(tokenize(term))
        else:
            codes.append("term_not_text")
    return sorted(set(codes))


def read_variant_document(path: Path) -> Any:
    """Read the JSON only; ``check_variants`` reports shape failures with their id."""

    try:
        raw = Path(path).read_bytes()
        return json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise VariantsError("cannot read a valid variant file") from exc


def read_variants(path: Path) -> Dict[str, Any]:
    """Read and shape-check the variant file; raise :class:`VariantsError`."""

    document = read_variant_document(path)
    failures = document_failures(document)
    if failures:
        raise VariantsError("variant file breaks the file rules: " + ",".join(failures))
    return document


def dump_variants(document: Mapping[str, Any]) -> str:
    """Stable formatting: fixed key order, two-space indent, no ASCII escaping."""

    ordered = {
        "schema_version": document["schema_version"],
        "golden_sha256": document["golden_sha256"],
        "variants": [
            {key: entry[key] for key in _KEY_ORDER if key in entry}
            for entry in document["variants"]
        ],
    }
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def state_counts(document: Mapping[str, Any]) -> Dict[str, int]:
    counts = Counter(entry["review_state"] for entry in document["variants"])
    return {state: counts.get(state, 0) for state in STATES}


def _golden_by_id(golden: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {item["id"]: item for item in golden["items"]}


def check_variants(
    document: Any,
    golden: Mapping[str, Any],
    base_cases: Sequence[Mapping[str, Any]],
    golden_digest: str,
    omissions: Sequence[str] = (),
) -> List[str]:
    """Every scenario-1/2 failure; each line names an id (or ``$``) and a rule.

    Structural and coverage rules apply to every entry; the scenario-2 content rules apply only
    to approved and draft variants, because a rejected variant is never scored.
    """

    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "golden_sha256",
        "variants",
    }:
        return ["$: wrong_schema"]
    if (
        document["schema_version"] != VARIANTS_VERSION
        or not isinstance(document["golden_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", document["golden_sha256"])
        or not isinstance(document["variants"], list)
    ):
        return ["$: wrong_schema"]
    if document["golden_sha256"] != golden_digest:
        return ["$: golden_sha256 does not match the golden file"]
    items = _golden_by_id(golden)
    approved_parents = {
        item["id"] for item in golden["items"] if item["review_state"] == "approved"
    }
    variants: Sequence[Any] = document["variants"]
    failures: List[str] = []
    # Per-entry shape first, named by id, so a malformed entry never crashes the rest.
    trusted: List[Mapping[str, Any]] = []
    seen_ids: set = set()
    for position, entry in enumerate(variants, start=1):
        label = (
            entry["id"]
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
            else f"#{position}"
        )
        codes = entry_failures(entry)
        for code in codes:
            failures.append(f"{label}: {code}")
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            if entry["id"] in seen_ids:
                failures.append(f"{label}: duplicate_id")
            seen_ids.add(entry["id"])
        if not codes:
            trusted.append(entry)
    if len(variants) != VARIANTS:
        failures.append(f"$: expected {VARIANTS} variants, found {len(variants)}")
    expected_ids = [f"coll-{number:03d}" for number in range(1, VARIANTS + 1)]
    present = [
        entry["id"]
        for entry in variants
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    for wanted in expected_ids:
        if wanted not in present:
            failures.append(f"{wanted}: missing")
    parents: List[str] = []
    for entry in trusted:
        if entry["id"] not in expected_ids:
            failures.append(f"{entry['id']}: id")
        if entry["parent_id"] not in items:
            failures.append(f"{entry['id']}: parent_id is not a golden item")
            continue
        if entry["parent_id"] in parents:
            failures.append(f"{entry['id']}: parent_id used twice")
        parents.append(entry["parent_id"])
        if entry["parent_id"] not in approved_parents:
            failures.append(f"{entry['id']}: parent is not approved")
    orphans = sorted(approved_parents - set(parents))
    if orphans:
        failures.append(f"$: orphan approved parents: {','.join(orphans)}")
    # Duplicates are decided over the tokens of every variant, reviewed case, and golden item.
    protected = {
        "reviewed:" + case["id"]: tokenize(case["question"]) for case in base_cases
    }
    protected.update(
        {"golden:" + item["id"]: tokenize(item["question"]) for item in golden["items"]}
    )
    # A rejected variant keeps the structural checks above but is never scored, so the
    # scenario-2 content rules (and duplicate wording) apply only to approved and draft entries.
    active = [entry for entry in trusted if entry["review_state"] != "rejected"]
    variant_tokens = {
        entry["id"]: tokenize(entry["question"]) for entry in active
    }
    for entry in active:
        parent = items.get(entry["parent_id"])
        if parent is None:
            continue
        mine = variant_tokens.get(entry["id"])
        clashes = [
            key.split(":", 1)[1]
            for key, tokens in protected.items()
            if key != "golden:" + entry["parent_id"] and tokens == mine
        ]
        clashes += [
            other
            for other, other_tokens in variant_tokens.items()
            if other != entry["id"] and other_tokens == mine
        ]
        found = variant_failures(
            entry, parent, duplicate_ids=clashes, omissions=omissions
        )
        for code in found:
            detail = (
                f" ({','.join(sorted(set(clashes)))})"
                if code == "question_duplicate"
                else ""
            )
            failures.append(f"{entry['id']}: {code}{detail}")
    return failures


def approved_cases(
    document: Mapping[str, Any],
    golden: Mapping[str, Any],
    base_cases: Sequence[Mapping[str, Any]],
    golden_digest: str,
    omissions: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    """Only ``approved`` variants as scored cases; drafts and rejected never appear."""

    if document["golden_sha256"] != golden_digest:
        raise VariantsError("the variant file is bound to another golden file")
    items = _golden_by_id(golden)
    approved = [
        entry for entry in document["variants"] if entry["review_state"] == "approved"
    ]
    failures: List[str] = []
    protected = {
        "reviewed:" + case["id"]: tokenize(case["question"]) for case in base_cases
    }
    protected.update(
        {"golden:" + item["id"]: tokenize(item["question"]) for item in golden["items"]}
    )
    variant_tokens = {entry["id"]: tokenize(entry["question"]) for entry in approved}
    for entry in approved:
        parent = items.get(entry["parent_id"])
        if parent is None or parent["review_state"] != "approved":
            failures.append(f"{entry['id']}: parent_id is not an approved golden item")
            continue
        mine = tokenize(entry["question"])
        clashes = [
            key.split(":", 1)[1]
            for key, tokens in protected.items()
            if key != "golden:" + entry["parent_id"] and tokens == mine
        ]
        clashes += [
            other
            for other, other_tokens in variant_tokens.items()
            if other != entry["id"] and other_tokens == mine
        ]
        for code in variant_failures(
            entry, parent, duplicate_ids=clashes, omissions=omissions
        ):
            failures.append(f"{entry['id']}: {code}")
    if failures:
        raise VariantsError("; ".join(failures[:5]))
    cases: List[Dict[str, Any]] = []
    for entry in approved:
        parent = items[entry["parent_id"]]
        decision = parent["decision"]
        case: Dict[str, Any] = {
            "id": entry["id"],
            "parent_id": parent["id"],
            "case_set": CASE_SET_COLLOQUIAL,
            "area": parent["area"],
            "question_type": parent["question_type"],
            "segment": parent["segment"],
            "question": entry["question"],
            "land_context": json.loads(json.dumps(parent["land_context"])),
            "expected_status": parent["expected_status"],
            "review": {
                "reviewed_by": decision["reviewed_by"],
                "reviewed_on": decision["reviewed_on"],
                "role": golden_set.AUTHOR_REVIEW_ROLE,
            },
        }
        for key in ("expected_source_ids", "expected_passage_ids", "critical_facts"):
            if parent.get(key):
                case[key] = list(parent[key])
        cases.append(case)
    return cases


# --- Readable list ----------------------------------------------------------------------


def _passage_and_source(
    parent: Mapping[str, Any], catalog: Any, passages: Any
) -> Tuple[Optional[str], Optional[str]]:
    anchor = parent.get("anchor") or {}
    passage = next(
        (item for item in passages["passages"] if item["id"] == anchor.get("passage_id")),
        None,
    )
    source = next(
        (item for item in catalog["sources"] if item["id"] == anchor.get("source_id")),
        None,
    )
    return (
        passage["location"] if passage is not None else None,
        source["title"] if source is not None else None,
    )


def _expected_words(parent: Mapping[str, Any], omissions: Sequence[str]) -> str:
    if parent["expected_status"] == "abstained":
        basis = (parent.get("deliberate_abstention") or {}).get("basis", "")
        if basis in omissions:
            return f'a deliberate "no lo sé" (the reviewed sources do not cover it: {basis})'
        return f'a deliberate "no lo sé" (it follows the reviewed case {basis})'
    return "an answer that quotes the source below"


def render_variant(
    number: int,
    entry: Mapping[str, Any],
    parent: Mapping[str, Any],
    catalog: Any,
    passages: Any,
    omissions: Sequence[str],
) -> str:
    location, title = _passage_and_source(parent, catalog, passages)
    lines = [
        "[{} of {}] {}  parent: {}  state: {}".format(
            number,
            VARIANTS,
            entry["id"],
            entry["parent_id"],
            STATE_LABELS[entry["review_state"]],
        ),
        "  The grower says: {}".format(entry["question"]),
        "  The approved question: {}".format(parent["question"]),
        "  Expected: {}".format(_expected_words(parent, omissions)),
    ]
    if title is not None:
        lines.append("  Source: {}".format(title))
    if location is not None:
        lines.append("  Location: {}".format(location))
    terms = entry["colloquial_terms"]
    lines.append(
        "  Plain words it introduces: {}".format("; ".join(terms) if terms else "(none)")
    )
    if entry["review_state"] != "draft":
        decision = entry["decision"]
        lines.append(
            "  Decision: {} by {} on {}".format(
                decision["decision"], decision["reviewed_by"], decision["reviewed_on"]
            )
        )
    return "\n".join(lines)


def render_list(
    document: Mapping[str, Any],
    golden: Mapping[str, Any],
    catalog: Any,
    passages: Any,
    omissions: Sequence[str],
    only_waiting: bool,
) -> str:
    items = _golden_by_id(golden)
    blocks = [
        render_variant(number, entry, items[entry["parent_id"]], catalog, passages, omissions)
        for number, entry in enumerate(document["variants"], start=1)
        if not only_waiting or entry["review_state"] == "draft"
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


# --- Decisions --------------------------------------------------------------------------


def resolve_refs(document: Mapping[str, Any], refs: Sequence[str]) -> List[int]:
    """Map numbers (``7``) and ids (``coll-007``) to 0-based indexes; unknown refs raise."""

    ids = [entry["id"] for entry in document["variants"]]
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


def decide(
    path: Path,
    decision: str,
    name: str,
    refs: Sequence[str],
    today: date,
    golden: Mapping[str, Any],
    base_cases: Sequence[Mapping[str, Any]],
    golden_digest: str,
    omissions: Sequence[str] = (),
) -> Tuple[int, int]:
    """Validate everything, then rewrite the file once. Returns ``(recorded, still waiting)``."""

    if decision not in ("approve", "reject") or not golden_set.valid_name(name) or not refs:
        raise DecisionError("usage")
    document = read_variants(path)
    if document["golden_sha256"] != golden_digest:
        raise DecisionError("file")
    indexes = resolve_refs(document, refs)
    state = "approved" if decision == "approve" else "rejected"
    if state == "approved":
        items = _golden_by_id(golden)
        variant_tokens = {
            entry["id"]: tokenize(entry["question"]) for entry in document["variants"]
        }
        for index in indexes:
            entry = document["variants"][index]
            parent = items.get(entry["parent_id"])
            if parent is None or parent["review_state"] != "approved":
                raise DecisionError("entry", str(index + 1))
            mine = variant_tokens[entry["id"]]
            clashes = [
                other
                for other, tokens in variant_tokens.items()
                if other != entry["id"] and tokens == mine
            ]
            clashes += [
                "reviewed"
                for case in base_cases
                if tokenize(case["question"]) == mine
            ]
            clashes += [
                item["id"]
                for item in golden["items"]
                if item["id"] != entry["parent_id"] and tokenize(item["question"]) == mine
            ]
            if variant_failures(
                entry, parent, duplicate_ids=clashes, omissions=omissions
            ):
                raise DecisionError("entry", str(index + 1))
    for index in indexes:
        entry = document["variants"][index]
        entry["review_state"] = state
        entry["decision"] = {
            "decision": state,
            "reviewed_by": name,
            "reviewed_on": today.isoformat(),
        }
    golden_set.write_atomically(Path(path), dump_variants(document))
    return len(indexes), state_counts(document)["draft"]


# --- Model terms ------------------------------------------------------------------------


class GlossaryPlusModel(QuestionGlossary):
    """The glossary's expansion plus prepared model terms for the matching question.

    Subclasses :class:`QuestionGlossary` so the existing ``create_app`` type check keeps the
    object as the arm's expansion; only ``expand`` and ``approved_count`` are used.
    """

    def __init__(
        self,
        glossary: QuestionGlossary,
        terms_by_question: Mapping[str, Sequence[str]],
    ) -> None:
        self._glossary = glossary
        self._terms = {
            question: tuple(terms)[:MAX_MODEL_TERMS]
            for question, terms in terms_by_question.items()
            if isinstance(question, str) and terms
        }

    @property
    def expandable_count(self) -> int:
        return len(self._terms)

    @property
    def approved_count(self) -> int:
        return self._glossary.approved_count

    def identity(self) -> str:
        return self._glossary.identity()

    def cache_suffix(self) -> str:
        return self._glossary.cache_suffix()

    def expand(self, question: str) -> str:
        """``question`` plus the glossary terms plus the prepared official terms."""

        expanded = self._glossary.expand(question)
        terms = self._terms.get(question, ())
        if not terms:
            return expanded
        tokens = tokenize(expanded)
        appended: List[str] = []
        seen: List[Tuple[str, ...]] = []
        for term in terms:
            term_tokens = tokenize(term)
            if not term_tokens or term_tokens in seen:
                continue
            if _contains(tokens, term_tokens):
                continue
            seen.append(term_tokens)
            appended.append(term)
        # The glossary adds at most MAX_APPENDED terms; keep the combined appends bounded.
        appended = appended[:MAX_MODEL_TERMS]
        if not appended:
            return expanded
        return " ".join([expanded] + appended)


def parse_model_terms(
    raw: Any, *, question: str, expanded: str
) -> Tuple[List[str], str]:
    """``(accepted terms, status)`` from one model answer; never a partial invented term."""

    if not isinstance(raw, str) or not raw.strip():
        return [], MODEL_EMPTY
    try:
        document = json.loads(raw)
    except ValueError:
        return [], MODEL_REJECTED
    if not isinstance(document, dict) or set(document) != {"terms"}:
        return [], MODEL_REJECTED
    terms = document["terms"]
    if not isinstance(terms, list):
        return [], MODEL_REJECTED
    accepted: List[str] = []
    seen: List[Tuple[str, ...]] = []
    for term in terms:
        if model_term_failures(term, question=question, expanded=expanded, seen=seen):
            continue
        accepted.append(term.strip())
        seen.append(tokenize(term))
        if len(accepted) == MAX_MODEL_TERMS:
            break
    if accepted:
        return accepted, MODEL_REWRITTEN
    return [], MODEL_EMPTY if not terms else MODEL_REJECTED


def prepare_rewrites(
    cases: Sequence[Mapping[str, Any]],
    glossary: QuestionGlossary,
    *,
    record: Any,
    rewriter: Any,
) -> Dict[str, Any]:
    """Ask the pinned model for official terms per approved case; return the cache document."""

    from app.local_generation import LocalTransportError

    entries: List[Dict[str, Any]] = []
    counts = {status: 0 for status in MODEL_STATUSES}
    for case in cases:
        question = case["question"]
        if screen_question(question) is not None:
            entries.append({"id": case["id"], "terms": [], "status": MODEL_SKIPPED_SCREENED})
            counts[MODEL_SKIPPED_SCREENED] += 1
            continue
        try:
            raw = rewriter(question)
        except (TimeoutError, LocalTransportError, OSError, ValueError) as exc:
            raise ColloquialAbort("model_unavailable") from exc
        terms, status = parse_model_terms(
            raw, question=question, expanded=glossary.expand(question)
        )
        entries.append({"id": case["id"], "terms": terms, "status": status})
        counts[status] += 1
    return {
        "schema_version": REWRITES_VERSION,
        "model": record.model,
        "digest": record.digest,
        "cases": entries,
        "counts": counts,
    }


def rewrite_cache_key(
    cases: Sequence[Mapping[str, Any]],
    *,
    glossary_digest: str,
    model: str,
    digest: str,
) -> str:
    """First 16 hex of the SHA-256 over every scored ``(id, question)`` and the pins."""

    canonical = json.dumps(
        {
            "cases": [[case["id"], case["question"]] for case in cases],
            "glossary": glossary_digest,
            "model": model,
            "digest": digest,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# --- Arms -------------------------------------------------------------------------------


def _row_builder(
    mode: str,
    *,
    pairs: Sequence[Tuple[str, str, str]],
    model_terms_by_id: Mapping[str, Sequence[str]],
    model_status_by_id: Mapping[str, str],
    questions_by_id: Mapping[str, str],
):
    def row_extra(case: Mapping[str, Any], actual: Mapping[str, Any]) -> Dict[str, Any]:
        row = eval_metrics.canonical_row(
            eval_metrics.case_row(
                case, actual, case["case_set"], case.get("question_type")
            )
        )
        row["mode"] = mode
        if case["case_set"] == CASE_SET_COLLOQUIAL:
            question = questions_by_id[case["id"]]
            fired: List[str] = []
            if mode != "no_rewriting":
                for pair_id, colloquial, official in pairs:
                    if (
                        QuestionGlossary([(colloquial, official)]).expand(question)
                        != question
                    ):
                        fired.append(pair_id)
            row["parent_id"] = case["parent_id"]
            row["glossary_pairs"] = fired
            row["model_terms"] = list(model_terms_by_id.get(case["id"], ()))
            row["model_status"] = (
                model_status_by_id.get(case["id"], MODEL_NOT_PREPARED)
                if mode == "glossary_plus_model"
                else MODEL_NOT_USED
            )
        return row

    return row_extra


def run_arms(
    cases: Sequence[Dict[str, Any]],
    catalog: Any,
    passages: Any,
    *,
    as_of: date,
    campaign: str,
    glossary: QuestionGlossary,
    model_terms_by_question: Mapping[str, Sequence[str]],
    model_terms_by_id: Mapping[str, Sequence[str]],
    model_status_by_id: Mapping[str, str],
    pairs: Sequence[Tuple[str, str, str]],
    application_factory: Optional[Any] = None,
    evaluator: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Score every case through one app per arm; only the expansion object differs.

    ``application_factory(settings)`` must return a context manager that yields an ``/ask``
    client; tests use it to record that every setting is identical across arms. The real
    builder creates one FastAPI app per arm with the same overrides as ``evaluate_metrics``.
    """

    from app.answer_eval import AnswerEvalError, evaluate as default_evaluate

    questions_by_id = {case["id"]: case["question"] for case in cases}
    expansions: Dict[str, Optional[Any]] = {
        "no_rewriting": None,
        "glossary": glossary,
        "glossary_plus_model": GlossaryPlusModel(glossary, model_terms_by_question),
    }
    run = evaluator or default_evaluate
    results: Dict[str, List[Dict[str, Any]]] = {}
    for mode in MODES:
        settings = {
            "mode": mode,
            "catalog": catalog,
            "passages": passages,
            "cases": list(cases),
            "k": K,
            "as_of": as_of,
            "campaign": campaign,
            "retention_store": None,
            "answer_cache": None,
            "answer_inspection": True,
            "expansion": expansions[mode],
        }
        extra = _row_builder(
            mode,
            pairs=pairs,
            model_terms_by_id=model_terms_by_id,
            model_status_by_id=model_status_by_id,
            questions_by_id=questions_by_id,
        )
        try:
            if application_factory is not None:
                with application_factory(settings) as client:
                    report = run(
                        settings["cases"], client, catalog, passages, K, row_extra=extra
                    )
            else:
                from fastapi.testclient import TestClient

                from app.ask_api import (
                    CorpusDocuments,
                    get_active_campaign,
                    get_as_of_date,
                    get_corpus_documents,
                    get_retrieval_k,
                )
                from app.main import create_app
                from app.pilot_config import load_config

                application = create_app(
                    load_config({"MANIJERO_ACTIVE_CAMPAIGN": campaign}),
                    retention_store=settings["retention_store"],
                    answer_cache=settings["answer_cache"],
                    answer_inspection=settings["answer_inspection"],
                    question_glossary=settings["expansion"],
                )
                documents = CorpusDocuments(catalog=catalog, passages=passages)
                application.dependency_overrides[get_corpus_documents] = lambda: documents
                application.dependency_overrides[get_as_of_date] = lambda: as_of
                application.dependency_overrides[get_active_campaign] = lambda: campaign
                application.dependency_overrides[get_retrieval_k] = lambda: K
                with TestClient(application) as client:
                    report = run(
                        settings["cases"], client, catalog, passages, K, row_extra=extra
                    )
        except AnswerEvalError:
            raise ColloquialAbort("ask_failed") from None
        extras = ("mode", "parent_id", "glossary_pairs", "model_terms", "model_status")
        rows = [
            {
                **eval_metrics.canonical_row(row),
                **{key: row[key] for key in extras if key in row},
            }
            for row in report["case_rows"]
        ]
        for row in rows:
            row["mode"] = mode
        results[mode] = rows
    return results


def trap_worse(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    """True when one approved trap got worse than arm A."""

    if before.get("expected_state_match") and not after.get("expected_state_match"):
        return True
    if before.get("abstention_reason_match") is True and after.get(
        "abstention_reason_match"
    ) is not True:
        return True
    return int(after.get("must_not_say_hits", 0)) > int(before.get("must_not_say_hits", 0))


def hit_at_5(rows: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    """``(hits, answered variants)``: the fixed denominator of the adoption rule."""

    answered = [
        row
        for row in rows
        if row.get("case_set") == CASE_SET_COLLOQUIAL
        and row.get("expected_status") == "answered"
    ]
    hits = sum(
        1
        for row in answered
        if isinstance(row.get("first_expected_rank"), int)
        and row["first_expected_rank"] <= K
    )
    return hits, len(answered)


def trap_regressions(
    baseline: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]
) -> List[str]:
    after = {row["id"]: row for row in candidate}
    return [
        row["id"]
        for row in baseline
        if row.get("case_set") == CASE_SET_TRAP
        and row["id"] in after
        and trap_worse(row, after[row["id"]])
    ]


def adoption(
    *,
    variant_counts: Mapping[str, int],
    baseline_hits: int,
    candidate_hits: int,
    changed_queries: int,
    regressions: int,
) -> Dict[str, Any]:
    """The owner's report-only rule for one candidate arm.

    ``adoptable`` is ``True`` only when hit@5 is strictly greater than arm A and no approved
    trap got worse. Incomplete review and no effect are reported as their own fixed phrases.
    """

    if variant_counts["draft"] > 0:
        return {
            "adoptable": None,
            "reason": "review_incomplete",
            "label": "not assessable (review incomplete)",
        }
    if changed_queries == 0:
        return {
            "adoptable": False,
            "reason": "no_effect",
            "label": "not adoptable (no effect)",
        }
    if candidate_hits <= baseline_hits:
        return {
            "adoptable": False,
            "reason": "no_gain",
            "label": "not adoptable (no gain)",
        }
    if regressions > 0:
        return {
            "adoptable": False,
            "reason": "trap_worse",
            "label": "not adoptable (a trap got worse)",
        }
    return {"adoptable": True, "reason": None, "label": "adoptable"}


# --- Version and report -----------------------------------------------------------------


def version_block(
    *,
    catalog: Path,
    passages: Path,
    cases: Path,
    golden: Path,
    traps: Path,
    variants: Path,
    glossary: str,
    model: str,
    model_digest: str,
    as_of: str,
    active_campaign: str,
    label: str,
    schema_versions: Mapping[str, str],
) -> Dict[str, Any]:
    """The exact inputs and settings a report is keyed by."""

    version = eval_metrics.version_block(
        catalog=catalog,
        passages=passages,
        cases=cases,
        golden=golden,
        traps=traps,
        glossary=glossary,
        as_of=as_of,
        active_campaign=active_campaign,
        label=label,
        schema_versions=schema_versions,
    )
    version.update(
        {
            "variants_sha256": _sha256(variants),
            "model": model,
            "model_digest": model_digest,
        }
    )
    return version


def version_id(version: Mapping[str, Any]) -> str:
    return eval_metrics.version_id(version)


def build_report(
    *,
    version: Mapping[str, Any],
    report_id: str,
    variants: Mapping[str, int],
    arms: Mapping[str, Mapping[str, Any]],
    adoption_block: Mapping[str, Any],
    rewrites: Mapping[str, int],
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    counts = {CASE_SET_COLLOQUIAL: 0, CASE_SET_GOLDEN: 0, CASE_SET_TRAP: 0}
    for row in rows:
        if row["mode"] == "no_rewriting":
            counts[row["case_set"]] += 1
    counts["total"] = sum(counts.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "version": dict(version),
        "version_id": report_id,
        "variant_counts": dict(variants),
        "case_counts": counts,
        "arms": {mode: dict(block) for mode, block in arms.items()},
        "adoption": dict(adoption_block),
        "rewrites": dict(rewrites),
        "cases": [dict(row) for row in rows],
        "limits": list(LIMITS),
        "report_only": True,
        "defaults_changed": False,
    }


def result_line(report: Mapping[str, Any], report_path: Path) -> str:
    arms = report["arms"]
    counts = report["variant_counts"]
    rewrites = report["rewrites"]
    verdicts = report["adoption"]["arms"]
    return (
        "Result: compared 3 ways on {n} approved colloquial variants ({m} answered, {c} with a "
        "changed query) and {t} approved traps: hit@5 no rewriting {a}/{m}, glossary {b}/{m}, "
        "glossary+model {d}/{m}; model rewrites: {r} rewritten, {e} empty, {x} rejected, {s} "
        "skipped; traps worse: glossary {y}, glossary+model {z}; verdict: glossary {g}, "
        "glossary+model {h}. No setting was changed. Report only, no gate. Report: {path}.".format(
            n=counts["approved"],
            m=arms["no_rewriting"]["hit_at_5"]["of"],
            c=arms["glossary"]["changed_queries"],
            t=arms["no_rewriting"]["traps"],
            a=arms["no_rewriting"]["hit_at_5"]["hits"],
            b=arms["glossary"]["hit_at_5"]["hits"],
            d=arms["glossary_plus_model"]["hit_at_5"]["hits"],
            r=rewrites["rewritten"],
            e=rewrites["empty"],
            x=rewrites["rejected"],
            s=rewrites["skipped_screened"],
            y=arms["glossary"]["trap_regressions"],
            z=arms["glossary_plus_model"]["trap_regressions"],
            g=verdicts["glossary"]["label"],
            h=verdicts["glossary_plus_model"]["label"],
            path=eval_metrics.display_path(Path(report_path)),
        )
    )


def abort_line(code: str) -> str:
    text = FAILURES.get(code, FAILURES["internal_error"])
    return f"Result: the colloquial comparison did not run ({code}): {text} Nothing was written."


# --- Output -----------------------------------------------------------------------------


def check_output_root(root: Path, inputs: Sequence[Path]) -> Path:
    """Refuse an output root inside ``knowledge/`` or on an input file."""

    target = Path(root).resolve()
    knowledge = KNOWLEDGE_ROOT.resolve()
    try:
        target.relative_to(knowledge)
    except ValueError:
        pass
    else:
        raise ColloquialAbort("unsafe_output_path")
    for path in inputs:
        if target == Path(path).resolve():
            raise ColloquialAbort("unsafe_output_path")
    return target


def write_document_atomically(document: Mapping[str, Any], target: Path) -> None:
    eval_metrics.write_report_atomically(document, target)


def write_error_log(root: Path, text: str) -> None:
    eval_metrics.write_error_log(root, text)
