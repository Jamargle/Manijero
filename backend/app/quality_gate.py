"""Read-only comparison of the agreed evaluation metrics against one reviewed baseline.

The baseline is a committed file a person reviewed. :func:`compare` returns every metric
that fell, so the developer gate can fail with one plain line; :func:`record_baseline`
is the only writer and is never called by ``check``. Nothing here imports the app, reads
knowledge, or defines a metric: hit@k and MRR come from :mod:`app.eval_metrics`.

Metric values are integer counts over fixed denominators plus a 4-decimal MRR. A group
with no cases renders ``n/a`` and enforces nothing. Only the ``review`` block authorizes
gating; a missing, empty, or incomplete block fails closed instead of comparing.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

SCHEMA_VERSION = "eval-quality-gate-baseline-v1"

# The fixed measurement settings the baseline must record. A mismatch is stale input.
SETTINGS: Dict[str, Any] = {
    "as_of": "2026-10-13",
    "active_campaign": "2026",
    "k": 5,
    "retrieval": "bm25",
    "drafting": "extractive",
    "glossary": "off",
}

BASELINE_KEYS = frozenset({"schema_version", "review", "settings", "inputs", "metrics"})
REVIEW_KEYS = frozenset({"reviewed_by", "reviewed_on", "reason"})
INPUT_KEYS = frozenset(
    {"retrieval_fixture", "abstention_fixture", "reviewed_sample"}
)
FIXTURE_INPUT_KEYS = frozenset({"catalog", "passages", "questions"})
RETRIEVAL_METRIC_KEYS = frozenset(
    {"questions", "hits_at_1", "hits_at_3", "hits_at_5", "mrr"}
)
ABSTENTION_METRIC_KEYS = frozenset({"questions", "correct"})
REVIEWED_ABSTENTION_METRIC_KEYS = frozenset({"expected", "correct"})
METRIC_GROUPS = {
    "fixtures_retrieval": RETRIEVAL_METRIC_KEYS,
    "fixtures_abstention": ABSTENTION_METRIC_KEYS,
    "reviewed_retrieval": RETRIEVAL_METRIC_KEYS,
    "reviewed_abstention": REVIEWED_ABSTENTION_METRIC_KEYS,
}

# (display label, retrieval block, abstention block, abstention denominator key)
GROUPS = (
    ("fixtures", "fixtures_retrieval", "fixtures_abstention", "questions"),
    (
        "reviewed sample",
        "reviewed_retrieval",
        "reviewed_abstention",
        "expected",
    ),
)

NEXT_STEPS = {
    "baseline_unreviewed": "ask the owner to review and record the baseline again",
    "baseline_invalid": "repair backend/config/quality_gate_baseline.json and try again",
    "baseline_stale": "record a new baseline for the current inputs and settings",
    "ask_failed": "check the backend and record a new baseline",
    "internal_error": "check the backend and try again",
}

REFUSALS = {
    "reviewer": "the reviewer must be named",
    "reason": "the reason must be given",
    "reviewed_on": "the review date must be a real YYYY-MM-DD date",
    "regression": (
        "a metric would fall; the owner must review the change, then record it with "
        "--accept-regression"
    ),
}


class GateAbort(Exception):
    """A fixed reason the gate does not compare or enforce."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RecordRefusal(Exception):
    """A fixed reason the baseline was not written."""


# --- baseline loading --------------------------------------------------------------------


def load_baseline(path: Path) -> Dict[str, Any]:
    """Read and structurally validate the baseline, else raise ``baseline_invalid``."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GateAbort("baseline_invalid") from None
    _validate_baseline(document)
    return document


def _validate_baseline(document: Any) -> None:
    if not isinstance(document, dict):
        raise GateAbort("baseline_invalid")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise GateAbort("baseline_invalid")
    if not set(document) <= BASELINE_KEYS:
        raise GateAbort("baseline_invalid")
    try:
        _validate_settings(document["settings"])
        _validate_inputs(document["inputs"])
        _validate_metrics(document["metrics"])
        review = document.get("review")
        if review is not None and not isinstance(review, dict):
            raise GateAbort("baseline_invalid")
        if isinstance(review, dict) and set(review) - REVIEW_KEYS:
            raise GateAbort("baseline_invalid")
    except (KeyError, TypeError, ValueError):
        raise GateAbort("baseline_invalid") from None


def _validate_settings(settings: Any) -> None:
    if not isinstance(settings, dict) or set(settings) != set(SETTINGS):
        raise GateAbort("baseline_invalid")
    if not isinstance(settings["as_of"], str):
        raise GateAbort("baseline_invalid")
    if not isinstance(settings["active_campaign"], str):
        raise GateAbort("baseline_invalid")
    if not isinstance(settings["k"], int) or isinstance(settings["k"], bool):
        raise GateAbort("baseline_invalid")
    for key in ("retrieval", "drafting", "glossary"):
        if not isinstance(settings[key], str):
            raise GateAbort("baseline_invalid")


def _validate_inputs(inputs: Any) -> None:
    if not isinstance(inputs, dict) or set(inputs) != INPUT_KEYS:
        raise GateAbort("baseline_invalid")
    fixtures = ("retrieval_fixture", "abstention_fixture")
    for name in fixtures:
        block = inputs[name]
        if not isinstance(block, dict) or set(block) != FIXTURE_INPUT_KEYS:
            raise GateAbort("baseline_invalid")
        for value in block.values():
            _digest_value(value)
    reviewed = inputs["reviewed_sample"]
    if not isinstance(reviewed, dict) or set(reviewed) != {"cases"}:
        raise GateAbort("baseline_invalid")
    _digest_value(reviewed["cases"])


def _digest_value(value: Any) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GateAbort("baseline_invalid")


def _validate_metrics(metrics: Any) -> None:
    if not isinstance(metrics, dict) or set(metrics) != set(METRIC_GROUPS):
        raise GateAbort("baseline_invalid")
    for name, keys in METRIC_GROUPS.items():
        block = metrics[name]
        if not isinstance(block, dict) or set(block) != keys:
            raise GateAbort("baseline_invalid")
        for key, value in block.items():
            if key == "mrr":
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise GateAbort("baseline_invalid")
            elif not isinstance(value, int) or isinstance(value, bool):
                raise GateAbort("baseline_invalid")


def review_problem(document: Mapping[str, Any]) -> Optional[str]:
    """``baseline_unreviewed`` unless the review block names a person, day, and reason."""

    review = document.get("review")
    if not isinstance(review, Mapping):
        return "baseline_unreviewed"
    if set(review) != REVIEW_KEYS:
        return "baseline_unreviewed"
    values = [review.get(key) for key in REVIEW_KEYS]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        return "baseline_unreviewed"
    try:
        reviewed_on = date.fromisoformat(review["reviewed_on"])
    except ValueError:
        return "baseline_unreviewed"
    if reviewed_on.isoformat() != review["reviewed_on"]:
        return "baseline_unreviewed"
    return None


def settings_match(settings: Mapping[str, Any]) -> bool:
    return dict(settings) == SETTINGS


def inputs_match(baseline_inputs: Mapping[str, Any], current_inputs: Mapping[str, Any]) -> bool:
    return dict(baseline_inputs) == dict(current_inputs)


# --- comparison --------------------------------------------------------------------------


def _count(value: Any, denominator: Any) -> str:
    return f"{int(value)}/{int(denominator)}"


def _mrr(value: Any) -> str:
    return "{:.4f}".format(float(value))


def _retrieval_drops(
    label: str,
    baseline: Mapping[str, Any],
    measured: Mapping[str, Any],
) -> List[Dict[str, str]]:
    if baseline.get("questions", 0) == 0:
        return []
    drops: List[Dict[str, str]] = []
    old_total = baseline["questions"]
    new_total = measured["questions"]
    for key, metric in (
        ("hits_at_1", "hit@1"),
        ("hits_at_3", "hit@3"),
        ("hits_at_5", "hit@5"),
    ):
        if measured[key] < baseline[key]:
            drops.append(
                {
                    "group": label,
                    "metric": metric,
                    "old": _count(baseline[key], old_total),
                    "new": _count(measured[key], new_total),
                }
            )
    return drops


def _abstention_drops(
    label: str,
    baseline: Mapping[str, Any],
    measured: Mapping[str, Any],
    denominator_key: str,
) -> List[Dict[str, str]]:
    if baseline.get(denominator_key, 0) == 0:
        return []
    if measured["correct"] >= baseline["correct"]:
        return []
    return [
        {
            "group": label,
            "metric": "abstention",
            "old": _count(baseline["correct"], baseline[denominator_key]),
            "new": _count(measured["correct"], measured[denominator_key]),
        }
    ]


def compare(
    baseline: Mapping[str, Any], measured: Mapping[str, Any]
) -> List[Dict[str, str]]:
    """Every blocked drop, fixtures first, then hit@1/3/5, abstention, and MRR."""

    drops: List[Dict[str, str]] = []
    for label, retrieval_key, abstention_key, denominator_key in GROUPS:
        old_retrieval = baseline[retrieval_key]
        new_retrieval = measured[retrieval_key]
        old_abstention = baseline[abstention_key]
        new_abstention = measured[abstention_key]
        drops.extend(_retrieval_drops(label, old_retrieval, new_retrieval))
        drops.extend(
            _abstention_drops(
                label, old_abstention, new_abstention, denominator_key
            )
        )
        if (
            old_retrieval.get("questions", 0) > 0
            and round(float(new_retrieval["mrr"]), 4)
            < round(float(old_retrieval["mrr"]), 4)
        ):
            drops.append(
                {
                    "group": label,
                    "metric": "MRR",
                    "old": _mrr(old_retrieval["mrr"]),
                    "new": _mrr(new_retrieval["mrr"]),
                }
            )
    return drops


def deltas(
    earlier: Mapping[str, Any], later: Mapping[str, Any]
) -> List[str]:
    """Every metric that changed between two baselines, in the same fixed order."""

    lines: List[str] = []
    for label, retrieval_key, abstention_key, denominator_key in GROUPS:
        old_retrieval = earlier[retrieval_key]
        new_retrieval = later[retrieval_key]
        old_total = old_retrieval["questions"]
        new_total = new_retrieval["questions"]
        for key, metric in (
            ("hits_at_1", "hit@1"),
            ("hits_at_3", "hit@3"),
            ("hits_at_5", "hit@5"),
        ):
            if old_retrieval[key] != new_retrieval[key]:
                lines.append(
                    "{} {}: {} -> {}".format(
                        label,
                        metric,
                        _count(old_retrieval[key], old_total),
                        _count(new_retrieval[key], new_total),
                    )
                )
        old_abstention = earlier[abstention_key]
        new_abstention = later[abstention_key]
        if old_abstention["correct"] != new_abstention["correct"]:
            lines.append(
                "{} abstention: {} -> {}".format(
                    label,
                    _count(old_abstention["correct"], old_abstention[denominator_key]),
                    _count(new_abstention["correct"], new_abstention[denominator_key]),
                )
            )
        if round(float(old_retrieval["mrr"]), 4) != round(
            float(new_retrieval["mrr"]), 4
        ):
            lines.append(
                "{} MRR: {} -> {}".format(
                    label,
                    _mrr(old_retrieval["mrr"]),
                    _mrr(new_retrieval["mrr"]),
                )
            )
    return lines


# --- result lines ------------------------------------------------------------------------


def _retrieval_text(label: str, block: Mapping[str, Any]) -> str:
    if block.get("questions", 0) == 0:
        return "{} n/a hit@1, n/a hit@3, n/a hit@5, MRR n/a".format(label)
    total = block["questions"]
    return "{} {}/{} hit@1, {}/{} hit@3, {}/{} hit@5, MRR {}".format(
        label,
        block["hits_at_1"],
        total,
        block["hits_at_3"],
        total,
        block["hits_at_5"],
        total,
        _mrr(block["mrr"]),
    )


def _abstention_text(
    label: str, block: Mapping[str, Any], denominator_key: str
) -> str:
    total = block.get(denominator_key, 0)
    if total == 0:
        return "{} abstention n/a".format(label)
    return "{} abstention {}/{}".format(label, block["correct"], total)


def passed_line(measured: Mapping[str, Any], review: Mapping[str, Any]) -> str:
    parts = []
    for label, retrieval_key, abstention_key, denominator_key in GROUPS:
        parts.append(_retrieval_text(label, measured[retrieval_key]))
        parts.append(
            _abstention_text(label, measured[abstention_key], denominator_key)
        )
    return (
        "Result: quality gate passed: {}. Baseline reviewed by {} on {}.".format(
            "; ".join(parts), review["reviewed_by"], review["reviewed_on"]
        )
    )


def failed_line(drops: Sequence[Mapping[str, str]]) -> str:
    named = "; ".join(
        "{} {} fell from {} to {}".format(
            drop["group"], drop["metric"], drop["old"], drop["new"]
        )
        for drop in drops
    )
    return (
        "Result: quality gate failed: {}. A developer must review the change; if the "
        "new numbers are right, the owner reviews and records a new baseline.".format(
            named
        )
    )


def not_enforced_line(code: str) -> str:
    code = code if code in NEXT_STEPS else "internal_error"
    return "Result: quality gate not enforced: {}; a developer must {}.".format(
        code, NEXT_STEPS[code]
    )


def not_recorded_line(reason: str) -> str:
    return f"Result: baseline not recorded: {reason}."


def recorded_line(changes: int, review: Mapping[str, Any]) -> str:
    noun = "metric" if changes == 1 else "metrics"
    return "Result: baseline recorded: {} {} changed; reviewed by {} on {}.".format(
        changes, noun, review["reviewed_by"], review["reviewed_on"]
    )


# --- writing -----------------------------------------------------------------------------


def review_block(reviewer: str, reason: str, reviewed_on: str) -> Dict[str, str]:
    """Validate one record command's review fields, else raise a fixed refusal."""

    reviewer = (reviewer or "").strip()
    reason = (reason or "").strip()
    if not reviewer:
        raise RecordRefusal(REFUSALS["reviewer"])
    if not reason:
        raise RecordRefusal(REFUSALS["reason"])
    try:
        day = date.fromisoformat(reviewed_on)
    except (TypeError, ValueError):
        raise RecordRefusal(REFUSALS["reviewed_on"]) from None
    if day.isoformat() != reviewed_on:
        raise RecordRefusal(REFUSALS["reviewed_on"])
    return {"reviewed_by": reviewer, "reviewed_on": day.isoformat(), "reason": reason}


def build_baseline(
    *,
    review: Mapping[str, Any],
    inputs: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "review": dict(review),
        "settings": dict(SETTINGS),
        "inputs": dict(inputs),
        "metrics": dict(metrics),
    }


def canonical_json(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_baseline_atomically(document: Mapping[str, Any], target: Path) -> None:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(canonical_json(document), encoding="utf-8")
    os.replace(temporary, target)


def _existing_metrics(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return dict(load_baseline(path)["metrics"])
    except GateAbort:
        return None


def record_baseline(
    *,
    path: Path,
    metrics: Mapping[str, Any],
    review: Mapping[str, Any],
    inputs: Mapping[str, Any],
    accept_regression: bool = False,
) -> List[str]:
    """Write the canonical baseline, refusing a silent drop. Returns changed-metric lines."""

    earlier = _existing_metrics(path)
    lines: List[str] = []
    if earlier is not None:
        drops = compare(earlier, metrics)
        if drops and not accept_regression:
            raise RecordRefusal(REFUSALS["regression"])
        lines = deltas(earlier, metrics)
    document = build_baseline(review=review, inputs=inputs, metrics=metrics)
    write_baseline_atomically(document, path)
    return lines
