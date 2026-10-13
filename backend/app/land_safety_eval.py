"""Offline, report-only land-safety evaluation over the accepted decision.

This module turns the measurements the accepted slices deferred
(``safe_abstention``'s trap set and ``land_clarification``'s clarification
measurement) into one reproducible baseline. It runs the accepted end-to-end
decision — :func:`app.clarification.answer_with_clarification`, which already
composes retrieval, grounding, abstention, and land clarification — over a set of
reviewed, source-anchored cases and reports, per category, whether the service
returned the correct sources, abstained safely, or clarified the correct land.

It deliberately does **not** change the decision. It imports the accepted
modules unchanged, never re-implements eligibility, grounding, or clarification,
never reads a catalog or a passage file itself except through the accepted
``prepare_corpus``/decision path, never calls a model, and never touches the
network. Grading is deterministic rule checking, not a semantic judge.

Durable rules:

* A case is a Git-tracked, human-reviewed artifact. A case whose expectation
  turns on a critical fact must carry a completed ``review`` block (reviewer,
  review date, level, and a ``<source_id>#<location>`` anchor); without it the
  set fails closed at load time. The harness records that provenance, but a human
  must verify the fact itself.
* Coverage and expected-source/clarification mismatches are **report-only**.
  Only the enforced safety invariants (a leaked or invented payload) can make the
  CLI exit ``1`` without an explicit ``--fail-on-miss``.
* The fixtures are synthetic and labelled. No number here is a legal-coverage or
  answer-quality claim, and no metric is a release gate.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, AbstractSet, Dict, List, Mapping, Optional, Sequence, Tuple

from app.abstention import (
    ABSTENTION_MESSAGES,
    ABSTENTION_REASONS,
    Abstention,
    to_abstention_response,
)
from app.clarification import (
    CLARIFICATION_SCOPE,
    CLARIFICATION_STATUS,
    DEFAULT_MAX_CLAIMS,
    NeedsLandClarification,
    answer_with_clarification,
    land_context_mode,
    land_ids_of,
    to_clarification_response,
)
from app.generation import (
    Answered,
    extract_figures,
    inline_markers,
    to_answer_response,
)
from app.retrieval import (
    DEFAULT_K,
    Retriever,
)

LAND_SAFETY_EVAL_SCHEMA_VERSION = "land-safety-eval-v1"

# Which trap-taxonomy concern each case exercises.
CATEGORIES: Tuple[str, ...] = (
    "covered",
    "uncovered",
    "mixed_land",
    "unknown_attribute",
    "false_premise",
)

# The accepted ``AskResponse`` outcomes a case may expect.
EXPECTED_OUTCOMES: Tuple[str, ...] = (
    "answered",
    "abstained",
    "needs_land_clarification",
)

# The accepted request scopes (``AskRequest.land_context.mode``).
LAND_SCOPES: Tuple[str, ...] = ("general", "all_active", "selected")

# The only keys a case set, a case, a land context, a land, and a review may
# carry. Anything else is a located load error.
CASE_SET_KEYS = frozenset({"schema_version", "cases"})
CASE_REQUIRED_KEYS = frozenset({"id", "category", "question", "land_context", "expect"})
CASE_OPTIONAL_KEYS = frozenset(
    {
        "expect_reason",
        "expected_source_ids",
        "expected_passage_ids",
        "expected_land_ids_to_choose",
        "critical",
        "review",
    }
)
LAND_CONTEXT_KEYS = frozenset({"mode", "lands"})
LAND_KEYS = frozenset({"id", "municipality", "water_regime", "production_method"})
REVIEW_KEYS = frozenset({"reviewed_by", "reviewed_on", "level", "anchor"})

# Exactly the seven keys of the accepted ``AnswerSource`` schema; the payload's
# own shape is the accepted ``AskResponse``.
RESPONSE_KEYS = frozenset(
    {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
)
ANSWER_SOURCE_KEYS = frozenset(
    {
        "title",
        "issuing_body",
        "url",
        "location",
        "published_or_updated_on",
        "verified_on",
        "excerpt",
    }
)

# The accepted ``AskResponse.land_ids_to_choose`` items are 1..128 characters.
MAX_LAND_ID_CHARS = 128

STATUS_BY_OUTCOME: Dict[str, str] = {
    "answered": "answered",
    "abstained": "abstained",
    "needs_land_clarification": CLARIFICATION_STATUS,
}


class LandSafetyEvalError(Exception):
    """A case set could not be read, parsed, or validated.

    Schema violations, unknown keys, duplicate ids, and missing conditional
    fields are reported with the JSON path that failed, such as
    ``$.cases[0].expected_source_ids``. Case text (a question, an id value) is
    never included in the message, so a diagnostic can be printed as-is.
    """


@dataclass(frozen=True)
class EvalCase:
    """One reviewed safety case."""

    id: str
    category: str
    question: str
    land_context: Mapping[str, Any]
    expect: str
    expect_reason: Optional[str] = None
    expected_source_ids: Tuple[str, ...] = ()
    expected_passage_ids: Tuple[str, ...] = ()
    expected_land_ids_to_choose: Tuple[str, ...] = ()
    critical: bool = False
    review: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class CaseResult:
    """The outcome, payload, per-check verdicts, and invariant status of one case."""

    id: str
    category: str
    expect: str
    expect_reason: Optional[str]
    outcome: str
    status: Optional[str]
    reason: Optional[str]
    generation_reason: Optional[str]
    source_ids: Tuple[str, ...]
    passage_ids: Tuple[str, ...]
    land_ids_to_choose: Tuple[str, ...]
    payload: Mapping[str, Any]
    checks: Mapping[str, bool]
    expectation_met: bool
    safety_violations: Tuple[str, ...]


# --- loading and validation -------------------------------------------------


def _fail(path: str, message: str) -> "LandSafetyEvalError":
    return LandSafetyEvalError("{}: {}".format(path, message))


def _require_non_blank_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(path, "must be a non-blank string")
    return value


def _require_str_list(value: Any, path: str, *, non_empty: bool) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise _fail(path, "must be a JSON array")
    if non_empty and not value:
        raise _fail(path, "must not be empty")
    items: List[str] = []
    for position, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise _fail("{}[{}]".format(path, position), "must be a non-blank string")
        items.append(item)
    return tuple(items)


def _require_iso_date(value: Any, path: str) -> str:
    text = _require_non_blank_str(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise _fail(path, "must be a real calendar date formatted as YYYY-MM-DD") from error
    return text


def load_cases(path: Path) -> Tuple[EvalCase, ...]:
    """Read and validate a land-safety case set, raising ``LandSafetyEvalError``."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise LandSafetyEvalError("cannot read case file: {}".format(error)) from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise LandSafetyEvalError("case file is not valid JSON: {}".format(error)) from error
    return validate_cases(document)


def validate_cases(document: Any) -> Tuple[EvalCase, ...]:
    """Validate a parsed case-set document against the readable contract."""

    if not isinstance(document, Mapping):
        raise _fail("$", "must be a JSON object")
    unknown = sorted(set(document) - CASE_SET_KEYS)
    if unknown:
        raise _fail("$", "has an unknown key: {}".format(unknown[0]))
    if document.get("schema_version") != LAND_SAFETY_EVAL_SCHEMA_VERSION:
        raise _fail(
            "$.schema_version",
            "must be '{}'".format(LAND_SAFETY_EVAL_SCHEMA_VERSION),
        )
    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list):
        raise _fail("$.cases", "must be a JSON array")

    cases: List[EvalCase] = []
    seen_ids: Dict[str, None] = {}
    for position, raw_case in enumerate(raw_cases):
        case = _validate_case(raw_case, "$.cases[{}]".format(position))
        if case.id in seen_ids:
            raise _fail("$.cases[{}].id".format(position), "duplicate case id")
        seen_ids[case.id] = None
        cases.append(case)
    return tuple(cases)


def _validate_case(raw: Any, path: str) -> EvalCase:
    if not isinstance(raw, Mapping):
        raise _fail(path, "must be a JSON object")
    unknown = sorted(set(raw) - CASE_REQUIRED_KEYS - CASE_OPTIONAL_KEYS)
    if unknown:
        raise _fail(path, "has an unknown key: {}".format(unknown[0]))
    missing = sorted(CASE_REQUIRED_KEYS - set(raw))
    if missing:
        raise _fail(path, "is missing required key: {}".format(missing[0]))

    case_id = _require_non_blank_str(raw.get("id"), _join(path, "id"))
    category = raw.get("category")
    if category not in CATEGORIES:
        raise _fail(_join(path, "category"), "must be one of: {}".format(", ".join(CATEGORIES)))
    question = raw.get("question")
    if not isinstance(question, str) or not question.strip():
        raise _fail(_join(path, "question"), "must be a non-blank string")
    land_context = _validate_land_context(raw.get("land_context"), _join(path, "land_context"))
    expect = raw.get("expect")
    if expect not in EXPECTED_OUTCOMES:
        raise _fail(
            _join(path, "expect"), "must be one of: {}".format(", ".join(EXPECTED_OUTCOMES))
        )

    expect_reason = raw.get("expect_reason")
    if expect_reason is not None:
        if expect_reason not in ABSTENTION_REASONS:
            raise _fail(
                _join(path, "expect_reason"),
                "must be one of: {}".format(", ".join(ABSTENTION_REASONS)),
            )
    if expect == "abstained" and expect_reason is None:
        raise _fail(_join(path, "expect_reason"), "is required when expect is 'abstained'")

    expected_source_ids = _require_str_list(
        raw.get("expected_source_ids", []),
        _join(path, "expected_source_ids"),
        non_empty=False,
    )
    if expect == "answered" and not expected_source_ids:
        raise _fail(
            _join(path, "expected_source_ids"),
            "must not be empty when expect is 'answered'",
        )
    expected_passage_ids = _require_str_list(
        raw.get("expected_passage_ids", []),
        _join(path, "expected_passage_ids"),
        non_empty=False,
    )
    expected_land_ids_to_choose = _require_str_list(
        raw.get("expected_land_ids_to_choose", []),
        _join(path, "expected_land_ids_to_choose"),
        non_empty=False,
    )
    if expect == "needs_land_clarification" and not expected_land_ids_to_choose:
        raise _fail(
            _join(path, "expected_land_ids_to_choose"),
            "must not be empty when expect is 'needs_land_clarification'",
        )

    critical = raw.get("critical", False)
    if not isinstance(critical, bool):
        raise _fail(_join(path, "critical"), "must be a boolean")

    review = raw.get("review")
    if review is not None:
        review = _validate_review(review, _join(path, "review"))
    if critical and review is None:
        raise _fail(_join(path, "review"), "is required when critical is true")

    return EvalCase(
        id=case_id,
        category=category,
        question=question,
        land_context=land_context,
        expect=expect,
        expect_reason=expect_reason,
        expected_source_ids=expected_source_ids,
        expected_passage_ids=expected_passage_ids,
        expected_land_ids_to_choose=expected_land_ids_to_choose,
        critical=critical,
        review=review,
    )


def _validate_land_context(raw: Any, path: str) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _fail(path, "must be a JSON object")
    unknown = sorted(set(raw) - LAND_CONTEXT_KEYS)
    if unknown:
        raise _fail(path, "has an unknown key: {}".format(unknown[0]))
    missing = sorted(LAND_CONTEXT_KEYS - set(raw))
    if missing:
        raise _fail(path, "is missing required key: {}".format(missing[0]))
    if raw.get("mode") not in LAND_SCOPES:
        raise _fail(
            _join(path, "mode"), "must be one of: {}".format(", ".join(LAND_SCOPES))
        )
    lands = raw.get("lands")
    if not isinstance(lands, list):
        raise _fail(_join(path, "lands"), "must be a JSON array")
    for position, land in enumerate(lands):
        _validate_land(land, "{}.lands[{}]".format(path, position))
    return {"mode": raw["mode"], "lands": list(lands)}


def _validate_land(raw: Any, path: str) -> None:
    if not isinstance(raw, Mapping):
        raise _fail(path, "must be a JSON object")
    unknown = sorted(set(raw) - LAND_KEYS)
    if unknown:
        raise _fail(path, "has an unknown key: {}".format(unknown[0]))
    land_id = raw.get("id")
    _require_non_blank_str(land_id, _join(path, "id"))
    if len(land_id) > MAX_LAND_ID_CHARS:
        raise _fail(
            _join(path, "id"),
            "must be at most {} characters".format(MAX_LAND_ID_CHARS),
        )
    for key in ("municipality", "water_regime", "production_method"):
        if key in raw and not isinstance(raw[key], str):
            raise _fail(_join(path, key), "must be a string")


def _validate_review(raw: Any, path: str) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _fail(path, "must be a JSON object")
    unknown = sorted(set(raw) - REVIEW_KEYS)
    if unknown:
        raise _fail(path, "has an unknown key: {}".format(unknown[0]))
    missing = sorted(REVIEW_KEYS - set(raw))
    if missing:
        raise _fail(path, "is missing required key: {}".format(missing[0]))
    reviewed_by = _require_non_blank_str(raw.get("reviewed_by"), _join(path, "reviewed_by"))
    reviewed_on = _require_iso_date(raw.get("reviewed_on"), _join(path, "reviewed_on"))
    level = raw.get("level")
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        raise _fail(_join(path, "level"), "must be an integer of at least 1")
    anchor = _require_non_blank_str(raw.get("anchor"), _join(path, "anchor"))
    if "#" not in anchor or anchor.startswith("#") or anchor.endswith("#"):
        raise _fail(_join(path, "anchor"), "must be formatted as '<source_id>#<location>'")
    return {
        "reviewed_by": reviewed_by,
        "reviewed_on": reviewed_on,
        "level": level,
        "anchor": anchor,
    }


def _join(path: str, key: str) -> str:
    return "{}.{}".format(path, key)


def _unique(values: Sequence[str]) -> Tuple[str, ...]:
    """Return ``values`` deduplicated, preserving first-seen order."""

    seen: Dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return tuple(seen)


def applicable_checks(category: str, expect: str) -> Tuple[str, ...]:
    """Return the per-case checks that are meaningful for one expectation.

    ``correct_sources`` only grades an answered case, ``safe_abstention`` only an
    abstained one, and ``correct_clarification`` only a clarification; the others
    are always reported. A non-applicable check is never a failure.
    """

    names = ["correct_outcome"]
    if expect == "answered":
        names.append("correct_sources")
    if expect == "abstained":
        names.append("safe_abstention")
    if expect == "needs_land_clarification":
        names.append("correct_clarification")
    if category in ("covered", "unknown_attribute"):
        names.append("no_over_clarification")
    return tuple(names)


# --- running one case -------------------------------------------------------


def run_case(
    case: EvalCase,
    corpus: Any,
    as_of: date,
    k: int = DEFAULT_K,
    *,
    max_claims: int = DEFAULT_MAX_CLAIMS,
    corpus_source_ids: Optional[AbstractSet[str]] = None,
) -> CaseResult:
    """Run one case through the accepted decision and grade it.

    ``corpus`` is what :func:`app.abstention.prepare_corpus` returned. The
    accepted :func:`app.clarification.answer_with_clarification` is called exactly
    once; this function never re-decides anything. ``corpus_source_ids``, when
    supplied, is the set of source ids the corpus may cite, so a returned source
    outside it is caught rather than trusted.
    """

    request_land_ids = land_ids_of(case.land_context)
    result = answer_with_clarification(
        case.question,
        case.land_context,
        corpus,
        k=k,
        max_claims=max_claims,
        as_of=as_of,
    )

    if isinstance(result, NeedsLandClarification):
        outcome = CLARIFICATION_STATUS
        status = CLARIFICATION_STATUS
        reason = None
        generation_reason = None
        land_ids_to_choose = result.land_ids_to_choose
        source_ids: Tuple[str, ...] = ()
        passage_ids: Tuple[str, ...] = ()
        payload: Mapping[str, Any] = to_clarification_response(result)
    elif isinstance(result, Answered):
        outcome = "answered"
        status = "answered"
        reason = None
        generation_reason = None
        land_ids_to_choose = ()
        source_ids = _unique(
            source.source_id for source in result.sources
        )
        passage_ids = _unique(source.passage_id for source in result.sources)
        payload = to_answer_response(result)
    else:  # Abstention
        outcome = "abstained"
        status = "abstained"
        reason = result.reason
        generation_reason = result.generation_reason
        land_ids_to_choose = ()
        source_ids = ()
        passage_ids = ()
        payload = to_abstention_response(result, land_scope=land_context_mode(case.land_context))

    checks = _checks_for(case, outcome, reason, source_ids, passage_ids,
                         land_ids_to_choose, payload, request_land_ids, corpus_source_ids)
    return CaseResult(
        id=case.id,
        category=case.category,
        expect=case.expect,
        expect_reason=case.expect_reason,
        outcome=outcome,
        status=status,
        reason=reason,
        generation_reason=generation_reason,
        source_ids=source_ids,
        passage_ids=passage_ids,
        land_ids_to_choose=land_ids_to_choose,
        payload=payload,
        checks=checks,
        expectation_met=_expectation_met(case, outcome, reason, checks),
        safety_violations=safety_violations(payload, outcome, reason, request_land_ids),
    )


def _checks_for(
    case: EvalCase,
    outcome: str,
    reason: Optional[str],
    source_ids: Sequence[str],
    passage_ids: Sequence[str],
    land_ids_to_choose: Sequence[str],
    payload: Mapping[str, Any],
    request_land_ids: Sequence[str],
    corpus_source_ids: Optional[AbstractSet[str]],
) -> Dict[str, bool]:
    expected_sources = set(case.expected_source_ids)
    returned_sources = set(source_ids)
    sources_in_corpus = (
        True if corpus_source_ids is None else returned_sources <= set(corpus_source_ids)
    )
    correct_sources = (
        outcome == "answered"
        and bool(expected_sources)
        and expected_sources <= returned_sources
        and sources_in_corpus
        and set(case.expected_passage_ids) <= set(passage_ids)
    )

    correct_clarification = (
        outcome == CLARIFICATION_STATUS
        and bool(case.expected_land_ids_to_choose)
        and set(land_ids_to_choose) == set(case.expected_land_ids_to_choose)
        and set(land_ids_to_choose) <= set(request_land_ids)
    )

    return {
        "correct_outcome": outcome == case.expect,
        "correct_sources": correct_sources,
        "safe_abstention": _safe_abstention(outcome, reason, payload),
        "correct_clarification": correct_clarification,
        "no_over_clarification": outcome != CLARIFICATION_STATUS,
    }


def _safe_abstention(
    outcome: str, reason: Optional[str], payload: Mapping[str, Any]
) -> bool:
    """Return whether an abstention payload is a safe, pinned abstention.

    Vacuously true for a non-abstention: the check exists to catch a leaked or
    invented abstention, not to grade a non-abstention case.
    """

    if outcome != "abstained":
        return True
    message = payload.get("answer")
    if payload.get("sources") != [] or payload.get("land_ids_to_choose") != []:
        return False
    if reason not in ABSTENTION_MESSAGES:
        return False
    if not isinstance(message, str) or message != ABSTENTION_MESSAGES[reason]:
        return False
    if any(character.isdigit() for character in message):
        return False
    return not extract_figures(message)


def _expectation_met(
    case: EvalCase, outcome: str, reason: Optional[str], checks: Mapping[str, bool]
) -> bool:
    """Return whether the case met its own expectation (the ``--fail-on-miss`` key)."""

    if case.expect == "answered":
        return outcome == "answered" and checks["correct_sources"]
    if case.expect == "abstained":
        return outcome == "abstained" and reason == case.expect_reason and checks["safe_abstention"]
    if case.expect == "needs_land_clarification":
        return checks["correct_clarification"]
    return False


def safety_violations(
    payload: Mapping[str, Any],
    outcome: str,
    reason: Optional[str],
    request_land_ids: Sequence[str],
) -> Tuple[str, ...]:
    """Return the enforced safety invariants one assembled payload violates.

    An empty tuple means the payload is safe: it means the service did not leak,
    guess, or invent anything. These are the only failures that make the CLI exit
    ``1`` without ``--fail-on-miss``.
    """

    violations: List[str] = []
    if set(payload) != RESPONSE_KEYS:
        violations.append("payload_keys")
        return tuple(violations)
    if payload.get("status") != STATUS_BY_OUTCOME.get(outcome):
        violations.append("payload_status_mismatch")

    if outcome == "abstained":
        if payload.get("sources") != []:
            violations.append("abstention_has_sources")
        if payload.get("land_ids_to_choose") != []:
            violations.append("abstention_has_land_ids")
        if reason not in ABSTENTION_MESSAGES:
            violations.append("abstention_reason_off_taxonomy")
            return tuple(violations)
        message = payload.get("answer")
        if not isinstance(message, str) or not message.strip():
            violations.append("abstention_blank_message")
        elif message != ABSTENTION_MESSAGES[reason]:
            violations.append("abstention_message_not_pinned")
        else:
            if any(character.isdigit() for character in message):
                violations.append("abstention_message_has_digit")
            if extract_figures(message):
                violations.append("abstention_message_has_figure_or_date")
    elif outcome == CLARIFICATION_STATUS:
        if payload.get("answer") != "":
            violations.append("clarification_answer_not_empty")
        if payload.get("sources") != []:
            violations.append("clarification_has_sources")
        if payload.get("land_scope") != CLARIFICATION_SCOPE:
            violations.append("clarification_scope_not_selected")
        ids = payload.get("land_ids_to_choose")
        if not isinstance(ids, list) or not ids:
            violations.append("clarification_ids_empty")
        else:
            if any(not isinstance(land_id, str) or not land_id.strip() for land_id in ids):
                violations.append("clarification_id_blank")
            if len(set(ids)) != len(ids):
                violations.append("clarification_ids_not_unique")
            requested = set(request_land_ids)
            if any(land_id not in requested for land_id in ids):
                violations.append("clarification_id_not_requested")
    elif outcome == "answered":
        sources = payload.get("sources")
        if not isinstance(sources, list) or not sources:
            violations.append("answered_no_sources")
        else:
            for position, source in enumerate(sources):
                if not isinstance(source, Mapping) or set(source) != ANSWER_SOURCE_KEYS:
                    violations.append("answered_source_keys")
                    break
            answer = payload.get("answer")
            markers = inline_markers(answer if isinstance(answer, str) else "")
            if any(marker < 1 or marker > len(sources) for marker in markers):
                violations.append("answered_marker_out_of_range")
    else:
        violations.append("unknown_outcome")

    return tuple(violations)


# --- evaluating the whole set -----------------------------------------------


def evaluate(
    cases: Sequence[EvalCase],
    corpus: Any,
    as_of: date,
    k: int = DEFAULT_K,
    *,
    max_claims: int = DEFAULT_MAX_CLAIMS,
    corpus_source_ids: Optional[AbstractSet[str]] = None,
) -> Dict[str, Any]:
    """Run every case and return the report rows, totals, and metrics.

    The report is deterministic: the cases are evaluated in file order and every
    value is derived from the accepted decision, with no clock, model, or network
    input beyond ``as_of``.
    """

    results = tuple(
        run_case(
            case,
            corpus,
            as_of,
            k,
            max_claims=max_claims,
            corpus_source_ids=corpus_source_ids,
        )
        for case in cases
    )
    return {
        "corpus_status": "current" if isinstance(corpus, Retriever) else "not_current",
        "index": index_summary(corpus),
        "case_rows": [case_row(result) for result in results],
        "category_totals": category_totals(results),
        "totals": totals(results),
        "metrics": metrics(results),
        "metric_counts": metric_counts(results),
        "critical_reviews": critical_reviews(cases, results),
        "safety_invariants_hold": all(not result.safety_violations for result in results),
    }


def index_summary(corpus: Any) -> Dict[str, int]:
    """Return the index counts for a current corpus, or zeros for a stale one."""

    if isinstance(corpus, Retriever):
        return {
            "eligible_sources": corpus.eligible_source_count,
            "indexed_passages": corpus.indexed_passage_count,
            "excluded_passages_ineligible_source": corpus.excluded_passage_count,
        }
    return {
        "eligible_sources": 0,
        "indexed_passages": 0,
        "excluded_passages_ineligible_source": 0,
    }


def case_row(result: CaseResult) -> Dict[str, Any]:
    """Return one JSON-ready case row (case ids and source ids only, no text)."""

    return {
        "id": result.id,
        "category": result.category,
        "expect": result.expect,
        "outcome": result.outcome,
        "status": result.status,
        "reason": result.reason,
        "generation_reason": result.generation_reason,
        "source_ids": list(result.source_ids),
        "passage_ids": list(result.passage_ids),
        "land_ids_to_choose": list(result.land_ids_to_choose),
        "checks": dict(result.checks),
        "applicable_checks": list(applicable_checks(result.category, result.expect)),
        "expectation_met": result.expectation_met,
        "safety_violations": list(result.safety_violations),
    }


def category_totals(results: Sequence[CaseResult]) -> Dict[str, Dict[str, int]]:
    """Return per-category case counts and how many met their expectation."""

    totals: Dict[str, Dict[str, int]] = {}
    for category in CATEGORIES:
        in_category = [result for result in results if result.category == category]
        totals[category] = {
            "cases": len(in_category),
            "expectations_met": sum(1 for result in in_category if result.expectation_met),
        }
    return totals


def totals(results: Sequence[CaseResult]) -> Dict[str, int]:
    return {
        "cases": len(results),
        "answered": sum(1 for result in results if result.outcome == "answered"),
        "abstained": sum(1 for result in results if result.outcome == "abstained"),
        "clarifications": sum(
            1 for result in results if result.outcome == CLARIFICATION_STATUS
        ),
        "expectations_met": sum(1 for result in results if result.expectation_met),
        "expectation_mismatches": sum(
            1 for result in results if not result.expectation_met
        ),
        "safety_invariant_failures": sum(
            len(result.safety_violations) for result in results
        ),
    }


def metric_counts(results: Sequence[CaseResult]) -> Dict[str, Dict[str, int]]:
    """Return the numerator/denominator behind each reported metric."""

    covered = [result for result in results if result.category == "covered"]
    abstention_cases = [
        result
        for result in results
        if result.category in ("uncovered", "false_premise")
    ]
    mixed = [result for result in results if result.category == "mixed_land"]
    no_over_clarification_cases = [
        result
        for result in results
        if result.category in ("covered", "unknown_attribute")
    ]

    return {
        "covered_source_hit_rate": {
            "matched": sum(1 for result in covered if result.checks["correct_sources"]),
            "total": len(covered),
        },
        "correct_abstention_rate": {
            "matched": sum(
                1
                for result in abstention_cases
                if result.outcome == "abstained"
                and result.reason == result.expect_reason
                and result.checks["safe_abstention"]
            ),
            "total": len(abstention_cases),
        },
        "correct_clarification_rate": {
            "matched": sum(
                1 for result in mixed if result.checks["correct_clarification"]
            ),
            "total": len(mixed),
        },
        "no_over_clarification_rate": {
            "matched": sum(
                1
                for result in no_over_clarification_cases
                if result.checks["no_over_clarification"]
            ),
            "total": len(no_over_clarification_cases),
        },
        "expected_outcome_match_rate": {
            "matched": sum(1 for result in results if result.checks["correct_outcome"]),
            "total": len(results),
        },
    }


def metrics(results: Sequence[CaseResult]) -> Dict[str, Optional[float]]:
    """Return the per-category rates, or ``None`` when a denominator is empty."""

    counts = metric_counts(results)
    return {
        name: _rate(count["matched"], count["total"]) for name, count in counts.items()
    }


def _rate(matched: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return round(matched / total, 3)


def critical_reviews(
    cases: Sequence[EvalCase], results: Sequence[CaseResult]
) -> List[Dict[str, Any]]:
    """Return the review provenance of every critical case, for manual audit."""

    by_id = {result.id: result for result in results}
    reviews: List[Dict[str, Any]] = []
    for case in cases:
        if not case.critical:
            continue
        review = case.review or {}
        result = by_id.get(case.id)
        reviews.append(
            {
                "id": case.id,
                "reviewed_by": review.get("reviewed_by"),
                "reviewed_on": review.get("reviewed_on"),
                "level": review.get("level"),
                "anchor": review.get("anchor"),
                "outcome": result.outcome if result is not None else None,
            }
        )
    return reviews
