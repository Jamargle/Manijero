"""Derive a review-only validity report from reviewed metadata and change impact.

This module combines the reviewed source catalog, the reviewed passage set, and
one accepted ``legal-change-impact-report-v1`` report into a derived
``validity-review-v1`` artifact. It states each catalog source's explicit
expiry, publication and consolidation facts, and turns the accepted signals into
retirement, review and addition proposals for an identified human reviewer.

Boundaries:

- it is read-only. It never writes ``knowledge/``, a release, an index, an
  evaluation case, or an answer, and it never makes a source eligible or
  ineligible for the answer path;
- retirement is proposed only for structured expiry or a machine-evident repeal
  whose instrument intersects a source linked with reason ``repeal_target``;
  every ambiguous or negated signal, an unmatched repeal, a validity signal and
  a linked publication stay review-required;
- an addition is a review lead only. It never enters the catalog or the corpus;
- expiry and publication are judged only against the injected UTC calendar date.
  No date, consolidation state, or applicability value is inferred from a
  campaign, title, passage text, local timezone, or wall clock;
- the artifact carries input digests and no timestamp, so the same inputs and
  the same ``as_of`` date produce byte-identical output. No model, network call,
  or scheduler is used.

Standard-library only.
"""

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.retrieval import load_passage_set, validate_passage_set
from app.source_catalog import load_catalog, validate_catalog

REPORT_VERSION = "validity-review-v1"
CHECKER = "manijero-source-validity-checker-v1"
IMPACT_REPORT_VERSION = "legal-change-impact-report-v1"
CATALOG_VERSION = "source-catalog-v1"
PASSAGE_SET_VERSION = "passage-set-v1"

MAX_CANDIDATES = 1000
MAX_PROPOSALS = 5000

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

SIGNAL_KINDS = frozenset({"repeal", "amendment", "validity", "publication"})
CLASSIFICATIONS = frozenset({"machine_evident", "ambiguous"})
VERSION_STATUSES = frozenset(
    {
        "no_extracted_document",
        "approved_copy",
        "unchanged_since_ingestion",
        "new_version",
        "baseline_unknown",
        "analysis_failed",
    }
)

# Fixed, value-free failure categories. They are stable for operators and tests.
FAILURES = frozenset(
    {
        "invalid_as_of",
        "invalid_catalog",
        "invalid_passage_set",
        "invalid_impact_report",
        "impact_inputs_mismatch",
        "candidate_count_exceeded",
        "proposal_count_exceeded",
        "unsafe_report_path",
        "internal_error",
    }
)

REVIEW_GATE = {
    "canonical_changes_applied": False,
    "automatic_retirement": False,
    "requires_human_approval": True,
}

# Durable limits copied into every artifact so it states its own scope.
LIMITS = (
    "This report is a review aid, not a legal conclusion: it does not decide "
    "whether a source is in force, applicable, or safe to cite.",
    "Expiry and publication states come only from reviewed catalog dates judged "
    "against the injected as-of date; no date is inferred from a campaign, "
    "title, passage text, or the current date.",
    "The reviewed catalog has no BOE consolidation-state field, so 'unknown' "
    "consolidation is not evidence that a text is not consolidated.",
    "An addition is a review lead for a human, not an admission; the catalog, "
    "passages, releases, indexes, and answers stay unchanged.",
    "The accepted impact report remains the review surface for amendment, "
    "version, and conflict review; its lexical signals are only as good as that "
    "report and their detection precision and recall are unmeasured.",
    "Only synthetic fixtures back this feature today; no live run against a "
    "published repeal or expiry exists.",
)


class SourceValidityError(ValueError):
    """An invalid input or unsafe output path that must fail closed."""

    def __init__(self, failure: str) -> None:
        if failure not in FAILURES:
            failure = "internal_error"
        self.failure = failure
        super().__init__(failure)


# --- Small deterministic helpers -------------------------------------------


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _read_bytes(path: Path, failure: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise SourceValidityError(failure) from error


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _parsed_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or ISO_DATE_PATTERN.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def structural_as_of(catalog: Any, as_of: date) -> date:
    """Return the date the catalog may be validated at without hiding expiry.

    The accepted catalog validator refuses a ``valid_until`` earlier than its
    validation date. This derived check must still inspect an already-expired
    entry, so it validates the same bytes at the earliest parseable
    ``valid_until`` (or ``as_of`` when that is earlier). Every structural,
    policy, date-order, host, and malformed-date rule still fails closed; only
    the expiry comparison moves.
    """
    dates = [as_of]
    sources = catalog.get("sources") if isinstance(catalog, dict) else None
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            parsed = _parsed_date(source.get("valid_until"))
            if parsed is not None:
                dates.append(parsed)
    return min(dates)


# --- Input loading and validation ------------------------------------------


def load_reviewed_catalog(catalog_path: Path, as_of: date) -> Tuple[Dict[str, Any], bytes]:
    """Load and validate ``source-catalog-v1`` over the reviewed bytes."""
    catalog_bytes = _read_bytes(catalog_path, "invalid_catalog")
    try:
        catalog = load_catalog(catalog_path)
    except Exception as error:
        raise SourceValidityError("invalid_catalog") from error
    if not isinstance(catalog, dict) or catalog.get("schema_version") != CATALOG_VERSION:
        raise SourceValidityError("invalid_catalog")
    if validate_catalog(catalog, structural_as_of(catalog, as_of)).issues:
        raise SourceValidityError("invalid_catalog")
    return catalog, catalog_bytes


def load_reviewed_passages(
    passages_path: Path, catalog: Dict[str, Any]
) -> Tuple[Dict[str, Any], bytes]:
    """Load and validate ``passage-set-v1`` against the supplied catalog."""
    passages_bytes = _read_bytes(passages_path, "invalid_passage_set")
    try:
        passages = load_passage_set(passages_path)
    except Exception as error:
        raise SourceValidityError("invalid_passage_set") from error
    report = validate_passage_set(passages)
    if (
        not report.ok
        or not isinstance(passages, dict)
        or passages.get("schema_version") != PASSAGE_SET_VERSION
    ):
        raise SourceValidityError("invalid_passage_set")
    catalog_ids = {source["id"] for source in catalog["sources"]}
    if any(passage.get("source_id") not in catalog_ids for passage in passages["passages"]):
        raise SourceValidityError("invalid_passage_set")
    return passages, passages_bytes


def load_impact_report(
    report_path: Path, catalog_bytes: bytes, passages_bytes: bytes, catalog_ids: Set[str]
) -> Tuple[Dict[str, Any], bytes]:
    """Load the accepted impact report and bind it to the supplied inputs."""
    payload = _read_bytes(report_path, "invalid_impact_report")
    try:
        report = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceValidityError("invalid_impact_report") from error
    _validate_impact_report(report, catalog_ids)
    inputs = report["inputs"]
    if (
        inputs["catalog_sha256"] != _sha256(catalog_bytes)
        or inputs["passages_sha256"] != _sha256(passages_bytes)
    ):
        raise SourceValidityError("impact_inputs_mismatch")
    return report, payload


def _validate_impact_report(report: Any, catalog_ids: Set[str]) -> None:
    """Fail closed unless the report has the signal and source shape we consume."""
    _require(isinstance(report, dict))
    _require(report.get("schema_version") == IMPACT_REPORT_VERSION)
    inputs = report.get("inputs")
    _require(isinstance(inputs, dict))
    for key in ("catalog_sha256", "passages_sha256"):
        value = inputs.get(key)
        _require(isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None)

    candidates = report.get("candidates")
    _require(isinstance(candidates, list))
    if len(candidates) > MAX_CANDIDATES:
        raise SourceValidityError("candidate_count_exceeded")

    seen: Set[str] = set()
    for candidate in candidates:
        _require(isinstance(candidate, dict))
        candidate_id = candidate.get("candidate_id")
        _require(
            isinstance(candidate_id, str) and SHA256_PATTERN.fullmatch(candidate_id) is not None
        )
        _require(candidate_id not in seen)
        seen.add(candidate_id)
        _require(candidate.get("version_status") in VERSION_STATUSES)
        for key in ("title", "issuer", "publication_url"):
            _require(_is_text(candidate.get(key)))

        signals = candidate.get("signals")
        _require(isinstance(signals, list))
        for signal in signals:
            _require(isinstance(signal, dict))
            _require(signal.get("kind") in SIGNAL_KINDS)
            _require(signal.get("classification") in CLASSIFICATIONS)
            _require(_is_text(signal.get("reason")))
            _require(_is_text_list(signal.get("instrument_keys")))

        affected = candidate.get("potentially_affected")
        _require(isinstance(affected, dict))
        sources = affected.get("sources")
        _require(isinstance(sources, list))
        for source in sources:
            _require(isinstance(source, dict))
            source_id = source.get("id")
            _require(_is_text(source_id) and source_id in catalog_ids)
            _require(_is_text_list(source.get("reasons")))
            _require(_is_text_list(source.get("instrument_keys")))


def _require(condition: Any) -> None:
    if not condition:
        raise SourceValidityError("invalid_impact_report")


def _is_text_list(value: Any) -> bool:
    return isinstance(value, list) and all(_is_text(item) for item in value)


# --- Per-source reviewed facts ---------------------------------------------


def _expiry_facts(valid_until: Any, as_of: date) -> Dict[str, Any]:
    parsed = _parsed_date(valid_until)
    if parsed is None:
        return {"state": "unknown", "valid_until": None}
    return {
        "state": "expired" if parsed < as_of else "in_force",
        "valid_until": valid_until,
    }


def _publication_facts(published_on: Any, as_of: date) -> Dict[str, Any]:
    parsed = _parsed_date(published_on)
    if parsed is None:
        return {"state": "unknown", "published_on": None}
    return {
        "state": "published" if parsed <= as_of else "future",
        "published_on": published_on,
    }


def _source_facts(source: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return {
        "id": source["id"],
        "lifecycle_status": source["lifecycle_status"],
        "expiry": _expiry_facts(source.get("valid_until"), as_of),
        "publication": _publication_facts(source.get("published_on"), as_of),
        "consolidation": {
            "state": (
                "official_consolidated_text_linked"
                if source.get("consolidated_url")
                else "unknown"
            )
        },
    }


def _passages_by_source(passages: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for passage in passages:
        grouped.setdefault(passage["source_id"], []).append(passage["id"])
    return grouped


# --- Proposal mapping -------------------------------------------------------


def _review() -> Dict[str, bool]:
    return {"required": True, "applied": False}


def _retirement(reasons: Set[str], keys: Set[str]) -> Dict[str, Any]:
    return {"reasons": reasons, "instrument_keys": keys}


def _review_entry() -> Dict[str, Any]:
    return {"reasons": set(), "instrument_keys": set(), "source_ids": set()}


def _add_review(
    reviews: Dict[Tuple[str, str], Dict[str, Any]],
    target_type: str,
    target_id: str,
    reason: str,
    instrument_keys: Iterable[str],
    source_ids: Iterable[str],
) -> None:
    entry = reviews.setdefault((target_type, target_id), _review_entry())
    entry["reasons"].add(reason)
    entry["instrument_keys"].update(instrument_keys)
    entry["source_ids"].update(source_ids)


def _repeal_target_links(links: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [link for link in links if "repeal_target" in link["reasons"]]


def _retire_machine_evident_repeals(
    signals: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    retirements: Dict[str, Dict[str, Any]],
) -> None:
    repeal_links = _repeal_target_links(links)
    for signal in signals:
        if signal["kind"] != "repeal" or signal["classification"] != "machine_evident":
            continue
        keys = set(signal["instrument_keys"])
        for link in repeal_links:
            overlap = keys & set(link["instrument_keys"])
            if not overlap:
                continue
            entry = retirements.setdefault(link["id"], _retirement(set(), set()))
            entry["reasons"].add("machine_evident_repeal")
            entry["instrument_keys"].update(overlap)


def _has_unmatched_repeal(
    signals: Sequence[Dict[str, Any]], links: Sequence[Dict[str, Any]]
) -> bool:
    repeal_links = _repeal_target_links(links)
    for signal in signals:
        if signal["kind"] != "repeal" or signal["classification"] != "machine_evident":
            continue
        keys = set(signal["instrument_keys"])
        if not any(keys & set(link["instrument_keys"]) for link in repeal_links):
            return True
    return False


def _candidate_proposals(
    candidate: Dict[str, Any],
    retirements: Dict[str, Dict[str, Any]],
    reviews: Dict[Tuple[str, str], Dict[str, Any]],
    additions: Dict[str, Dict[str, Any]],
) -> None:
    candidate_id = candidate["candidate_id"]
    links = candidate["potentially_affected"]["sources"]
    source_ids = {link["id"] for link in links}
    signals = candidate["signals"]
    all_keys = {key for signal in signals for key in signal["instrument_keys"]}

    _retire_machine_evident_repeals(signals, links, retirements)
    if _has_unmatched_repeal(signals, links):
        _add_review(
            reviews, "candidate", candidate_id, "unmatched_repeal_target", all_keys, source_ids
        )

    ambiguous = [signal for signal in signals if signal["classification"] == "ambiguous"]
    if ambiguous:
        _add_review(
            reviews,
            "candidate",
            candidate_id,
            "ambiguous_signal",
            {key for signal in ambiguous for key in signal["instrument_keys"]},
            source_ids,
        )
        if any(signal["reason"] == "negated_signal" for signal in ambiguous):
            _add_review(reviews, "candidate", candidate_id, "negated_signal", (), source_ids)

    validity = [
        signal
        for signal in signals
        if signal["kind"] == "validity" and signal["classification"] == "machine_evident"
    ]
    if validity:
        _add_review(
            reviews,
            "candidate",
            candidate_id,
            "validity_signal",
            {key for signal in validity for key in signal["instrument_keys"]},
            source_ids,
        )

    publications = [
        signal
        for signal in signals
        if signal["kind"] == "publication" and signal["classification"] == "machine_evident"
    ]
    if not publications:
        return
    keys = {key for signal in publications for key in signal["instrument_keys"]}
    if links:
        _add_review(
            reviews, "candidate", candidate_id, "linked_publication", keys, source_ids
        )
    elif candidate["version_status"] != "approved_copy":
        entry = additions.setdefault(
            candidate_id,
            {
                "instrument_keys": set(),
                "title": " ".join(candidate["title"].split()),
                "issuer": candidate["issuer"],
                "publication_url": candidate["publication_url"],
            },
        )
        entry["instrument_keys"].update(keys)


def _proposal_sort_key(proposal: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        proposal["kind"],
        proposal["target"]["type"],
        proposal["target"]["id"],
    )


def _build_proposals(
    sources: Sequence[Dict[str, Any]],
    passages_by_source: Dict[str, List[str]],
    impact: Dict[str, Any],
) -> List[Dict[str, Any]]:
    retirements: Dict[str, Dict[str, Any]] = {}
    reviews: Dict[Tuple[str, str], Dict[str, Any]] = {}
    additions: Dict[str, Dict[str, Any]] = {}

    for source in sources:
        if source["expiry"]["state"] == "expired":
            entry = retirements.setdefault(source["id"], _retirement(set(), set()))
            entry["reasons"].add("expired_valid_until")
        if source["publication"]["state"] == "future":
            _add_review(
                reviews,
                "source",
                source["id"],
                "future_publication_date",
                (),
                (source["id"],),
            )

    for candidate in impact["candidates"]:
        _candidate_proposals(candidate, retirements, reviews, additions)

    proposals: List[Dict[str, Any]] = []
    for source_id in sorted(retirements):
        entry = retirements[source_id]
        proposals.append(
            {
                "kind": "retirement",
                "target": {"type": "source", "id": source_id},
                "reasons": sorted(entry["reasons"]),
                "instrument_keys": sorted(entry["instrument_keys"]),
                "passage_ids": sorted(passages_by_source.get(source_id, [])),
                "review": _review(),
            }
        )
    for target_type, target_id in sorted(reviews):
        entry = reviews[(target_type, target_id)]
        proposals.append(
            {
                "kind": "review",
                "target": {"type": target_type, "id": target_id},
                "reasons": sorted(entry["reasons"]),
                "instrument_keys": sorted(entry["instrument_keys"]),
                "source_ids": sorted(entry["source_ids"]),
                "review": _review(),
            }
        )
    for candidate_id in sorted(additions):
        entry = additions[candidate_id]
        proposals.append(
            {
                "kind": "addition",
                "target": {"type": "candidate", "id": candidate_id},
                "reasons": ["machine_evident_publication"],
                "instrument_keys": sorted(entry["instrument_keys"]),
                "title": entry["title"],
                "issuer": entry["issuer"],
                "publication_url": entry["publication_url"],
                "review": _review(),
            }
        )
    proposals.sort(key=_proposal_sort_key)
    return proposals


# --- Report -----------------------------------------------------------------


def check_validity(
    catalog_path: Path,
    passages_path: Path,
    impact_report_path: Path,
    as_of: date,
) -> Dict[str, Any]:
    """Return the derived validity review for the supplied inputs and date."""
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise SourceValidityError("invalid_as_of")

    catalog, catalog_bytes = load_reviewed_catalog(catalog_path, as_of)
    passages, passages_bytes = load_reviewed_passages(passages_path, catalog)
    catalog_ids = {source["id"] for source in catalog["sources"]}
    impact, impact_bytes = load_impact_report(
        impact_report_path, catalog_bytes, passages_bytes, catalog_ids
    )

    sources = sorted(
        (_source_facts(source, as_of) for source in catalog["sources"]),
        key=lambda source: source["id"],
    )
    passages_by_source = _passages_by_source(passages["passages"])
    proposals = _build_proposals(sources, passages_by_source, impact)
    if len(proposals) > MAX_PROPOSALS:
        raise SourceValidityError("proposal_count_exceeded")

    return {
        "schema_version": REPORT_VERSION,
        "checker": CHECKER,
        "as_of": as_of.isoformat(),
        "inputs": {
            "catalog_sha256": _sha256(catalog_bytes),
            "passages_sha256": _sha256(passages_bytes),
            "impact_report_sha256": _sha256(impact_bytes),
        },
        "sources": sources,
        "proposals": proposals,
        "summary": _summary(sources, proposals),
        "review_gate": dict(REVIEW_GATE),
        "limits": list(LIMITS),
    }


def _summary(
    sources: Sequence[Dict[str, Any]], proposals: Sequence[Dict[str, Any]]
) -> Dict[str, int]:
    return {
        "sources": len(sources),
        "expired": sum(1 for source in sources if source["expiry"]["state"] == "expired"),
        "in_force": sum(1 for source in sources if source["expiry"]["state"] == "in_force"),
        "expiry_unknown": sum(
            1 for source in sources if source["expiry"]["state"] == "unknown"
        ),
        "future_publications": sum(
            1 for source in sources if source["publication"]["state"] == "future"
        ),
        "retirements": sum(1 for proposal in proposals if proposal["kind"] == "retirement"),
        "additions": sum(1 for proposal in proposals if proposal["kind"] == "addition"),
        "reviews": sum(1 for proposal in proposals if proposal["kind"] == "review"),
        "proposals": len(proposals),
    }


def write_report(
    report: Dict[str, Any], path: Path, input_paths: Sequence[Path] = ()
) -> None:
    """Write the canonical artifact atomically outside ``knowledge/``."""
    target = Path(path)
    if _inside_directory(target, KNOWLEDGE_ROOT):
        raise SourceValidityError("unsafe_report_path")
    resolved = target.resolve()
    if any(resolved == Path(input_path).resolve() for input_path in input_paths):
        raise SourceValidityError("unsafe_report_path")
    text = _canonical_json(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(target, text)


def exit_code(report: Dict[str, Any]) -> int:
    """Return ``1`` when proposals need review, ``0`` when none do."""
    return 1 if report["proposals"] else 0


def proposal_lines(report: Dict[str, Any]) -> List[str]:
    """Return one deterministic, plain-language line per proposal."""
    lines: List[str] = []
    for proposal in report["proposals"]:
        target = proposal["target"]
        identifier = "{} {}".format(target["type"], target["id"])
        reasons = ", ".join(proposal["reasons"])
        if proposal["kind"] == "retirement":
            lines.append(
                "Proposal: retire {} ({}); {} passage(s) affected; human review "
                "required.".format(identifier, reasons, len(proposal["passage_ids"]))
            )
        elif proposal["kind"] == "addition":
            title = " ".join(proposal["title"].split())
            lines.append(
                'Proposal: add {} ("{}"); human review required.'.format(identifier, title)
            )
        else:
            lines.append(
                "Proposal: review {} ({}); human review required.".format(identifier, reasons)
            )
    return lines


def result_line(report: Dict[str, Any], path: Path) -> str:
    """Return the single fixed ``Result:`` line for a written report."""
    count = len(report["proposals"])
    if count == 0:
        return "Result: no proposals need review; report written to {}.".format(path)
    if count == 1:
        return "Result: 1 proposal needs review; report written to {}.".format(path)
    return "Result: {} proposals need review; report written to {}.".format(count, path)
