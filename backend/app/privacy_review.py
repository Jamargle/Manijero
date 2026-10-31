"""Pilot privacy/legal review gate and the separate Gemini provider review gate.

Both gates read one reviewed record, ``backend/config/pilot_privacy_review.json``
(``pilot-privacy-review-v1``). The committed record is ``pending``: no qualified review has
been recorded, so both gates are closed. This module never decides that a review happened;
it only checks that a dated, qualified, complete decision has been written down by a person.

The pilot gate passes only when the ``pilot_review`` section is ``approved`` or
``approved_with_conditions`` (with conditions listed), carries a ``reviewed_on`` date that is
not in the future, names the reviewer's qualification (not their name: the record keeps no
unnecessary personal data), covers every required scope item, and references the evidence.

The Gemini gate additionally requires the ``gemini_review`` section to pass the same checks
for its own scope, to name the exact reviewed model, and to limit the data sent to the
question and the approved retrieved passages. It also requires the pilot gate to pass, and
``MANIJERO_GENERATION_PROVIDER=gemini`` with a matching ``MANIJERO_GEMINI_MODEL``. This gate
is necessary, not sufficient: :mod:`app.gemini_generation` also requires the recorded limits
file and an injected transport, and this repository ships no Gemini transport, so the
Gemini path stays extractive.

``MANIJERO_GENERATION_PROVIDER=local`` is also an accepted value: it selects the loopback
Ollama provider in :mod:`app.local_generation`, which has its own model-record gate and, in
the pilot profile, requires the pilot review gate here to pass. The Gemini decision below
reports ``gemini_not_configured`` for it, unchanged.

Blockers are fixed codes; no record value is echoed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence, Tuple

REVIEW_SCHEMA_VERSION = "pilot-privacy-review-v1"
DEFAULT_REVIEW_PATH = Path(__file__).resolve().parents[1] / "config" / "pilot_privacy_review.json"
APPROVED_STATUSES = frozenset({"approved", "approved_with_conditions"})
REVIEW_STATUSES = frozenset({"pending", "rejected"}) | APPROVED_STATUSES
PILOT_REVIEW_SCOPE = (
    "data_flow",
    "notice",
    "opt_in",
    "redaction_limits",
    "retention_deletion",
    "access_controls",
    "incident_and_contact",
    "host_terms",
    "tunnel_terms",
)
GEMINI_REVIEW_SCOPE = ("model_terms", "data_flow", "data_sent", "retention_by_provider")
GEMINI_ALLOWED_DATA = frozenset({"question", "approved_passages"})
GENERATION_PROVIDER_ENV = "MANIJERO_GENERATION_PROVIDER"
GEMINI_MODEL_ENV = "MANIJERO_GEMINI_MODEL"
GENERATION_PROVIDERS = frozenset({"extractive", "gemini", "local"})
_SECTION_KEYS = frozenset(
    {"status", "reviewed_on", "reviewer_qualification", "scope", "conditions", "evidence_reference"}
)
_GEMINI_EXTRA_KEYS = frozenset({"model", "data_sent"})


@dataclass(frozen=True)
class GateResult:
    """Whether a gate passed and, if not, the fixed blocker codes."""

    passed: bool
    blockers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationDecision:
    """The provider the answer path uses, and why the gated provider is not used."""

    provider: str
    gemini_configured: bool
    gemini_gate: GateResult


def load_review_record(path: Path | None = None) -> Mapping[str, Any] | None:
    """Read the review record; ``None`` when it is missing or unreadable."""

    try:
        document = json.loads((path or DEFAULT_REVIEW_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def evaluate_pilot_review(record: Mapping[str, Any] | None, *, as_of: date) -> GateResult:
    """Evaluate the pilot privacy/legal review gate."""

    section = _section(record, "pilot_review")
    if isinstance(section, GateResult):
        return GateResult(False, tuple(code.replace("review_", "privacy_review_", 1) for code in section.blockers))
    blockers = _section_blockers(section, PILOT_REVIEW_SCOPE, as_of, "privacy_review")
    if set(section) != _SECTION_KEYS:
        blockers.insert(0, "privacy_review_invalid")
    return GateResult(not blockers, tuple(blockers))


def evaluate_gemini_review(
    record: Mapping[str, Any] | None,
    *,
    as_of: date,
    configured_model: str | None,
) -> GateResult:
    """Evaluate the separate Gemini provider gate (pilot gate included)."""

    blockers: list[str] = []
    pilot = evaluate_pilot_review(record, as_of=as_of)
    if not pilot.passed:
        blockers.append("pilot_privacy_review_not_passed")
    section = _section(record, "gemini_review")
    if isinstance(section, GateResult):
        blockers.extend(code.replace("review_", "gemini_review_", 1) for code in section.blockers)
        return GateResult(False, tuple(blockers))
    if set(section) != _SECTION_KEYS | _GEMINI_EXTRA_KEYS:
        blockers.append("gemini_review_invalid")
    blockers.extend(_section_blockers(section, GEMINI_REVIEW_SCOPE, as_of, "gemini_review"))
    model = section.get("model")
    if not isinstance(model, str) or not model.strip():
        blockers.append("gemini_model_not_recorded")
    elif configured_model is None or configured_model.strip() != model.strip():
        blockers.append("gemini_model_mismatch")
    data_sent = section.get("data_sent")
    if (
        not isinstance(data_sent, list)
        or not data_sent
        or not all(isinstance(item, str) for item in data_sent)
        or not set(data_sent) <= GEMINI_ALLOWED_DATA
    ):
        blockers.append("gemini_data_sent_not_minimal")
    return GateResult(not blockers, tuple(dict.fromkeys(blockers)))


def decide_generation_provider(
    env: Mapping[str, str] | None = None,
    *,
    record: Mapping[str, Any] | None = None,
    as_of: date,
) -> GenerationDecision:
    """Return the review-gate decision; ``provider`` here is always ``extractive``.

    A configured Gemini provider is reported with its gate result so the operator can see
    why it is not used. The effective provider is decided by
    :func:`app.gemini_generation.resolve_generation_provider`, which calls this gate first
    and adds the limits and transport gates; no transport exists in this repository.
    """

    source = os.environ if env is None else env
    configured = (source.get(GENERATION_PROVIDER_ENV) or "").strip() == "gemini"
    model = (source.get(GEMINI_MODEL_ENV) or "").strip() or None
    gate = (
        evaluate_gemini_review(record, as_of=as_of, configured_model=model)
        if configured
        else GateResult(False, ("gemini_not_configured",))
    )
    return GenerationDecision(provider="extractive", gemini_configured=configured, gemini_gate=gate)


def generation_provider_problem(env: Mapping[str, str] | None = None) -> str | None:
    """Return a fixed problem code for an unknown provider setting, else ``None``."""

    source = os.environ if env is None else env
    value = (source.get(GENERATION_PROVIDER_ENV) or "").strip()
    if value and value not in GENERATION_PROVIDERS:
        return "generation_provider_invalid"
    return None


def minimal_provider_payload(question: str, passages: Sequence[Mapping[str, Any]]) -> dict:
    """The only data a gated generation provider may receive for one question.

    It carries the question and the text of the approved retrieved passages, each with
    its passage id so a draft can cite it. It never carries land context, land ids,
    names, notes, client or device identifiers, or retained question/answer text. The shared
    gated generator builds its payload only through this function (with the redacted
    question and candidate numbers as ids), for Gemini (no transport exists, so nothing
    sends it) and for the loopback local provider (sent only to ``127.0.0.1``).
    """

    if not isinstance(question, str) or not question.strip():
        raise ValueError("question_invalid")
    allowed = []
    for passage in passages:
        passage_id = passage.get("passage_id") if isinstance(passage, Mapping) else None
        text = passage.get("text") if isinstance(passage, Mapping) else None
        if not isinstance(passage_id, str) or not isinstance(text, str):
            raise ValueError("passage_invalid")
        allowed.append({"passage_id": passage_id, "text": text})
    return {"question": question, "passages": allowed}


def _section(record: Mapping[str, Any] | None, name: str) -> Mapping[str, Any] | GateResult:
    if record is None:
        return GateResult(False, ("review_record_unreadable",))
    if record.get("schema_version") != REVIEW_SCHEMA_VERSION or set(record) != {
        "schema_version",
        "pilot_review",
        "gemini_review",
    }:
        return GateResult(False, ("review_record_invalid",))
    section = record.get(name)
    if not isinstance(section, dict):
        return GateResult(False, ("review_record_invalid",))
    return section


def _section_blockers(
    section: Mapping[str, Any], required_scope: Sequence[str], as_of: date, prefix: str
) -> list[str]:
    blockers: list[str] = []
    status = section.get("status")
    if status not in REVIEW_STATUSES:
        return [f"{prefix}_invalid"]
    if status == "pending":
        blockers.append(f"{prefix}_pending")
    elif status == "rejected":
        blockers.append(f"{prefix}_rejected")
    reviewed_on = section.get("reviewed_on")
    if reviewed_on is None:
        blockers.append(f"{prefix}_undated")
    else:
        try:
            parsed = date.fromisoformat(reviewed_on) if isinstance(reviewed_on, str) else None
        except ValueError:
            parsed = None
        if parsed is None:
            blockers.append(f"{prefix}_undated")
        elif parsed > as_of:
            blockers.append(f"{prefix}_future_date")
    qualification = section.get("reviewer_qualification")
    if not isinstance(qualification, str) or not qualification.strip():
        blockers.append(f"{prefix}_qualification_missing")
    scope = section.get("scope")
    if not isinstance(scope, list) or not set(required_scope) <= {item for item in scope if isinstance(item, str)}:
        blockers.append(f"{prefix}_scope_incomplete")
    conditions = section.get("conditions")
    if not isinstance(conditions, list) or not all(isinstance(item, str) for item in conditions):
        blockers.append(f"{prefix}_invalid")
    elif status == "approved_with_conditions" and not conditions:
        blockers.append(f"{prefix}_conditions_missing")
    evidence = section.get("evidence_reference")
    if not isinstance(evidence, str) or not evidence.strip():
        blockers.append(f"{prefix}_evidence_missing")
    return blockers
