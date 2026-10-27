"""Prepare and gate a human-reviewed knowledge update.

This module turns quarantined official-document candidates (written by
``app/document_ingestion.py`` and analyzed by ``app/change_impact.py``) into one
reviewable update package: a deterministic manifest, a bounded reviewer summary
(the draft pull-request body), the proposed catalog/passage edits, the
provenance and integrity evidence, the automated check results, and the
unresolved questions a human must answer.

Boundaries:

- preparation and decisions are read-only over ``knowledge/``. The controlled
  ``merge`` is the only function here that writes canonical artifacts, and it
  writes them only after a recorded approval by a named human who is not the
  package author and only while every required check still passes;
- a bot identity, a CI status, a label, or a matching hash is never approval:
  only an explicit human decision counts;
- the canonical catalog and passage set are never changed before merge, and
  merge never reindexes, releases, or deploys anything. Reindex/release is a
  separate post-merge operation owned by ``knowledge_reindex_release``;
- a rejected or changes-requested package keeps its decision and leaves
  canonical knowledge byte-identical. A revised proposal is a new package with
  new checks and no inherited approval;
- source document text is untrusted data. It is stored and rendered only as
  bounded, quoted evidence and is never interpreted as instructions;
- the package contains no question, land, personal, or attempt-history data,
  and it carries no wall-clock timestamp: identical pinned inputs and the same
  ``as_of`` date produce byte-identical output.

Standard-library only. No network access, no model provider, no Git or hosting
API call: the "pull request" is a local, inspectable draft directory that an
operator can attach to a real PR.
"""

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from app.change_impact import ImpactAnalysisError, analyze as analyze_change_impact
from app.change_impact import load_evaluation_cases, load_ingestion_state
from app.document_ingestion import candidate_admission_issue
from app.retrieval import load_passage_set, validate_passage_set
from app.source_catalog import load_catalog, validate_catalog

PACKAGE_VERSION = "knowledge-update-review-package-v1"
DECISIONS_VERSION = "knowledge-update-review-decisions-v1"
MERGE_VERSION = "knowledge-update-merge-v1"
PROPOSAL_VERSION = "knowledge-update-proposal-v1"
PREPARER = "manijero-knowledge-review-preparer-v1"

MAX_CANDIDATES_PER_PACKAGE = 20
MAX_EXTRACTED_BLOCKS = 5000
MAX_REVIEWED_TEXT_CHARS = 2000000
MAX_DIFFS = 40
MAX_DIFF_VALUE_CHARS = 400
MAX_UNRESOLVED_QUESTIONS = 50
MAX_LISTED_LOCATIONS = 20

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

CANDIDATE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DECISIONS = ("approve", "request_changes", "reject")
EFFECTIVE_DECISIONS = {
    "approve": "approved",
    "request_changes": "changes_requested",
    "reject": "rejected",
}
RESOLVABLE_FINDINGS = ("ambiguous_signal", "conflicting_signals")
ACKNOWLEDGEABLE_FINDINGS = RESOLVABLE_FINDINGS + ("text_changed_without_signal",)
UNKNOWN_FIELDS = ("validity", "applicability")
UNKNOWN_VALUE_TOKENS = frozenset({"unknown", "desconocido", "desconegut"})

REQUIRED_PROVENANCE_KEYS = (
    "title",
    "issuer",
    "stable_identity",
    "publication_url",
    "registry_id",
    "registry_url",
    "version_hash",
    "last_attempt_at",
    "last_success_at",
    "media_type",
    "declared_content_type",
    "extractor",
    "original_sha256",
    "extracted_text_sha256",
    "original_path",
    "extracted_path",
)

REQUIRED_PACKAGE_KEYS = (
    "schema_version",
    "preparer",
    "prepared_on",
    "author",
    "review",
    "package_kind",
    "summary",
    "candidates",
    "proposal",
    "affected",
    "checks",
    "check_summary",
    "merge_readiness",
    "blocking_reasons",
    "unresolved_questions",
    "limits",
    "package_id",
)

REQUIRED_PROPOSAL_KEYS = (
    "input",
    "before",
    "after",
    "differences",
    "differences_truncated",
    "evaluation",
)

REQUIRED_EVALUATION_KEYS = (
    "cases_available",
    "cases_sha256",
    "case_count",
    "validated_against",
    "orphaned_case_ids",
    "rewritten_case_ids",
)

REQUIRED_HASH_KEYS = ("catalog_sha256", "passages_sha256")

GLOBAL_FAILURES = frozenset(
    {
        "invalid_as_of",
        "invalid_catalog",
        "invalid_passage_set",
        "invalid_ingestion_state",
        "invalid_proposal",
        "invalid_evaluation_cases",
        "invalid_review_package",
        "invalid_review_decisions",
        "invalid_decision",
        "invalid_decision_date",
        "unsafe_workspace",
        "candidate_count_exceeded",
        "reviewer_required",
        "reviewer_not_human",
        "reviewer_not_requested",
        "reviewer_is_author",
        "self_approval",
        "approval_required",
        "approval_blocked",
        "stale_approval",
        "cases_required",
        "evaluation_cases_drift",
        "canonical_drift",
        "already_merged",
    }
)

AUTOMATION_IDENTITIES = frozenset(
    {
        "automation",
        "automated",
        "bot",
        "ci",
        "cd",
        "ci/cd",
        "actions",
        "github-actions",
        "workflow",
        "pipeline",
        "service-account",
        "preparer",
        PREPARER,
    }
)

PACKAGE_LIMITS = (
    "The package is a local draft, not a hosting-platform pull request: the "
    "operator attaches the generated review body to the real repository PR. "
    "Repository merge protection is therefore not enforced by GitHub here; the "
    "controlled merge command verifies the recorded human approval instead.",
    "Preparation verifies the extracted-text digest and, when the original bytes "
    "are still present in the quarantine, the original-bytes digest. A missing "
    "original copy is reported as a reviewer question; only a person can compare "
    "the extracted text with the official original.",
    "Evidence retention follows the operator's ingestion state and quarantine. "
    "Neither is garbage-collected, and deleting either makes an old package's "
    "evidence unrecoverable.",
    "Review display is bounded: text diffs, signals, and proposed field changes "
    "show at most a fixed number of excerpts and characters. A large document "
    "must be opened in the quarantine for a full reading.",
    "Extraction supports standard-library PDF/HTML text without OCR. Scanned, "
    "encrypted, or unsupported documents were already failed or uncertain at "
    "ingestion; this package inherits that limitation.",
    "A proposal that changes the reviewed corpus requires the reviewed "
    "answer-evaluation case set. Preparation validates the after-state catalog "
    "and passages against those cases, and a case that would lose an expected "
    "source or passage blocks readiness with the affected case ids. Without a "
    "case set, any catalog or passage change is blocked; a no-op proposal is "
    "still allowed.",
    "Merge revalidates the same case set by digest before writing canonical "
    "files, so editing the cases after preparation cannot bypass preparation's "
    "after-state check. Evaluation cases are not rewritten or retired by this "
    "feature; a reviewer must update them in a separate reviewed change.",
    "Affected and rewritten answer-evaluation cases are reported, not re-run, "
    "and every metric stays report-only. A human approval of this bounded "
    "update is not legal completeness, corpus currency, or answer-quality "
    "certification.",
    "Canonical catalog/passage after hashes and merge writes preserve each "
    "file's existing field order; only a real proposal change alters the diff. "
    "A no-op package leaves both canonical files byte-identical.",
    "Review turnaround and reviewer availability are operational, not automated: "
    "an unapproved package simply stays unmerged, and nothing expires it.",
)


class ReviewPackageError(ValueError):
    """An invalid input, unsafe workspace, or refused gate that must fail closed."""

    def __init__(self, failure: str) -> None:
        if failure not in GLOBAL_FAILURES:
            failure = "invalid_review_package"
        self.failure = failure
        super().__init__(failure)


class _ExtractionError(Exception):
    """A fixed reason why a candidate's extracted document is unusable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> str:
    """Stable sorted JSON for package, decision, and merge ids."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _ordered_json(value: Any) -> str:
    """Canonical knowledge JSON that preserves the existing field order.

    Catalog and passage files are reviewed, Git-tracked artifacts. Sorting their
    keys would rewrite every entry on the first no-op merge, so their after
    hashes and merge writes must use insertion order instead.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=False, indent=2) + "\n"


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    without_diacritics = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(without_diacritics.split())


def _is_automated(identity: str) -> bool:
    """Refuse identities that are unambiguously automation or CI.

    This is a name-based denial list, not authentication: a person can still
    choose a name that is not on it, because local records cannot prove who is
    typing. It blocks the common GitHub Actions, CI job, workflow, pipeline,
    automation, service-account, and preparer identities.
    """
    folded = _fold(identity)
    return (
        folded in AUTOMATION_IDENTITIES
        or folded.startswith("automation-")
        or folded.startswith("automation/")
        or folded == "service-account"
        or folded.startswith("service-account-")
        or folded.startswith("service-account/")
        or folded.startswith("manijero-knowledge-review-preparer")
        or "[bot]" in folded
        or re.search(r"\bbot\b", folded) is not None
    )


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _atomic_write_text(path: Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)


def _read_bytes(path: Path, failure: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise ReviewPackageError(failure) from error


def _bounded(text: Any, limit: int = MAX_DIFF_VALUE_CHARS) -> Tuple[str, bool]:
    """Return a display string for any JSON value, plus whether it was cut."""
    if isinstance(text, str):
        compact = " ".join(text.split())
    else:
        compact = _canonical_json(text).strip()
    if len(compact) <= limit:
        return compact, False
    return compact[: limit - 1].rstrip() + "…", True


def _fenced(text: str) -> str:
    """Quote untrusted document text so it can never render as instructions."""
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return "{0}\n{1}\n{0}".format(fence, text)


def _require_keys(
    value: Any, required: Iterable[str], optional: Iterable[str] = ()
) -> None:
    if not isinstance(value, dict):
        raise ReviewPackageError("invalid_proposal")
    required_set = set(required)
    allowed = required_set | set(optional)
    if not required_set <= set(value) or set(value) - allowed:
        raise ReviewPackageError("invalid_proposal")


def _require_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewPackageError("invalid_proposal")
    return value


# --- Proposal ---------------------------------------------------------------


def load_proposal(path: Path) -> Dict[str, Any]:
    """Load and strictly validate ``knowledge-update-proposal-v1``."""
    try:
        proposal = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewPackageError("invalid_proposal") from error
    _require_keys(
        proposal,
        ("schema_version", "summary", "candidates", "catalog", "passages"),
        ("author", "links", "unresolved_questions"),
    )
    if proposal["schema_version"] != PROPOSAL_VERSION:
        raise ReviewPackageError("invalid_proposal")
    summary = _require_text(proposal["summary"])

    author = proposal.get("author", {"identity": PREPARER, "kind": "automation"})
    _require_keys(author, ("identity", "kind"))
    identity = _require_text(author["identity"])
    if author["kind"] not in ("human", "automation"):
        raise ReviewPackageError("invalid_proposal")

    raw_candidates = proposal["candidates"]
    if not isinstance(raw_candidates, list) or not 1 <= len(raw_candidates) <= MAX_CANDIDATES_PER_PACKAGE:
        raise ReviewPackageError("invalid_proposal")
    candidates: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for item in raw_candidates:
        _require_keys(item, ("candidate_id",), ("resolution", "unknown_fields"))
        candidate_id = item["candidate_id"]
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            raise ReviewPackageError("invalid_proposal")
        if candidate_id in seen:
            raise ReviewPackageError("invalid_proposal")
        seen.add(candidate_id)
        resolution = item.get("resolution")
        if resolution is not None:
            _require_keys(resolution, ("findings", "note"))
            findings = resolution["findings"]
            if (
                not isinstance(findings, list)
                or not findings
                or any(finding not in ACKNOWLEDGEABLE_FINDINGS for finding in findings)
                or len(findings) != len(set(findings))
            ):
                raise ReviewPackageError("invalid_proposal")
            _require_text(resolution["note"])
        unknown_fields = item.get("unknown_fields", [])
        if (
            not isinstance(unknown_fields, list)
            or any(field not in UNKNOWN_FIELDS for field in unknown_fields)
            or len(unknown_fields) != len(set(unknown_fields))
        ):
            raise ReviewPackageError("invalid_proposal")
        candidates.append(
            {
                "candidate_id": candidate_id,
                "resolution": resolution,
                "unknown_fields": tuple(unknown_fields),
            }
        )

    catalog = _normalize_section(proposal["catalog"], with_entries=True)
    passages = _normalize_section(proposal["passages"], with_entries=True)

    links = proposal.get("links", [])
    if not isinstance(links, list):
        raise ReviewPackageError("invalid_proposal")
    normalized_links: List[Dict[str, str]] = []
    for link in links:
        _require_keys(link, ("source_id", "candidate_id"))
        source_id = _require_text(link["source_id"])
        candidate_id = link["candidate_id"]
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            raise ReviewPackageError("invalid_proposal")
        if candidate_id not in seen:
            raise ReviewPackageError("invalid_proposal")
        normalized_links.append({"source_id": source_id, "candidate_id": candidate_id})

    questions = proposal.get("unresolved_questions", [])
    if not isinstance(questions, list) or any(
        not isinstance(question, str) or not question.strip() for question in questions
    ):
        raise ReviewPackageError("invalid_proposal")

    return {
        "schema_version": PROPOSAL_VERSION,
        "summary": summary,
        "author": {"identity": identity, "kind": author["kind"]},
        "candidates": candidates,
        "catalog": catalog,
        "passages": passages,
        "links": normalized_links,
        "unresolved_questions": questions,
    }


def _normalize_section(section: Any, *, with_entries: bool) -> Dict[str, Any]:
    _require_keys(section, ("add", "update", "remove"))
    normalized: Dict[str, Any] = {}
    for key in ("add", "update"):
        entries = section[key]
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ReviewPackageError("invalid_proposal")
        if key == "update" and any(
            not isinstance(entry.get("id"), str) or not entry["id"].strip() for entry in entries
        ):
            raise ReviewPackageError("invalid_proposal")
        normalized[key] = [dict(entry) for entry in entries]
    removals = section["remove"]
    if not isinstance(removals, list) or any(
        not isinstance(item, str) or not item.strip() for item in removals
    ):
        raise ReviewPackageError("invalid_proposal")
    if len(removals) != len(set(removals)):
        raise ReviewPackageError("invalid_proposal")
    normalized["remove"] = list(removals)
    if not with_entries:
        raise ReviewPackageError("invalid_proposal")
    return normalized


def _apply_section(
    document: Dict[str, Any], key: str, section: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return a copy of ``document`` with one proposal section applied."""
    after = json.loads(json.dumps(document))
    items = after.get(key)
    if not isinstance(items, list):
        raise ReviewPackageError("invalid_proposal")
    removed = set(section["remove"])
    known = {item.get("id") for item in items if isinstance(item, dict)}
    if not removed <= known:
        raise ReviewPackageError("invalid_proposal")
    items = [item for item in items if item.get("id") not in removed]
    for entry in section["update"]:
        source_id = entry["id"]
        if source_id in removed or source_id not in known:
            raise ReviewPackageError("invalid_proposal")
        position = next(
            index for index, item in enumerate(items) if item.get("id") == source_id
        )
        items[position] = json.loads(json.dumps(entry))
    for entry in section["add"]:
        items.append(json.loads(json.dumps(entry)))
    after[key] = items
    return after


# --- Candidate evidence -----------------------------------------------------


def _relative_quarantine_path(value: Any, candidate_id: str) -> Optional[Path]:
    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != (candidate_id,):
        return None
    return relative


def _read_extracted_document(
    quarantine_root: Path, record: Mapping[str, Any]
) -> Dict[str, Any]:
    candidate_id = str(record.get("candidate_id", ""))
    relative = _relative_quarantine_path(record.get("extracted_path"), candidate_id)
    if relative is None:
        raise _ExtractionError("extracted_document_missing")
    path = Path(quarantine_root) / relative
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise _ExtractionError("extracted_document_missing") from error
    expected = record.get("extracted_text_sha256")
    if not isinstance(expected, str) or _sha256(payload) != expected:
        raise _ExtractionError("extracted_text_mismatch")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _ExtractionError("extracted_document_malformed") from error
    if (
        not isinstance(document, dict)
        or document.get("candidate_id") != candidate_id
        or not isinstance(document.get("blocks"), list)
        or not document["blocks"]
    ):
        raise _ExtractionError("extracted_document_malformed")
    characters = 0
    replacement_characters = 0
    sections: List[str] = []
    for block in document["blocks"]:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            raise _ExtractionError("extracted_document_malformed")
        text = " ".join(block["text"].split())
        if not text:
            raise _ExtractionError("extracted_document_malformed")
        section = block.get("section")
        if not isinstance(section, str) or not section.strip():
            raise _ExtractionError("extracted_document_malformed")
        characters += len(text)
        replacement_characters += text.count("\ufffd")
        if len(sections) < MAX_LISTED_LOCATIONS and section not in sections:
            sections.append(section)
        if len(document["blocks"]) > MAX_EXTRACTED_BLOCKS or characters > MAX_REVIEWED_TEXT_CHARS:
            raise _ExtractionError("extracted_document_too_large")
    return {
        "blocks": len(document["blocks"]),
        "characters": characters,
        "replacement_characters": replacement_characters,
        "sections": sections,
    }


def _original_bytes_status(
    quarantine_root: Path, record: Mapping[str, Any]
) -> Tuple[str, str]:
    """Return ``(status, detail)`` for the preserved original bytes."""
    candidate_id = str(record.get("candidate_id", ""))
    relative = _relative_quarantine_path(record.get("original_path"), candidate_id)
    if relative is None:
        return "report_only", "original_bytes_not_recorded"
    path = Path(quarantine_root) / relative
    try:
        payload = path.read_bytes()
    except OSError:
        return "report_only", "original_bytes_unavailable"
    expected = record.get("original_sha256")
    if not isinstance(expected, str) or _sha256(payload) != expected:
        return "fail", "original_bytes_mismatch"
    return "pass", "original_bytes_verified"


def _missing_provenance(record: Mapping[str, Any]) -> List[str]:
    missing: List[str] = []
    for key in REQUIRED_PROVENANCE_KEYS:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
    for key in ("byte_size", "block_count"):
        value = record.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            missing.append(key)
    return missing


def _check(
    check_id: str,
    status: str,
    detail: str,
    candidate_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "candidate_id": candidate_id,
        "status": status,
        "detail": detail,
    }


def _candidate_checks_and_evidence(
    record: Mapping[str, Any],
    impact: Mapping[str, Any],
    quarantine_root: Path,
    resolution: Optional[Mapping[str, Any]],
    unknown_fields: Sequence[str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    candidate_id = str(record["candidate_id"])
    checks: List[Dict[str, Any]] = []
    questions: List[str] = []

    extracted_status = "extracted"
    if record.get("status") != "extracted":
        checks.append(
            _check("candidate_ingested", "fail", str(record.get("failure") or record.get("status")), candidate_id)
        )
        extracted_status = str(record.get("status"))
    else:
        checks.append(_check("candidate_ingested", "pass", "extracted", candidate_id))

    if record.get("review_status") != "pending":
        checks.append(_check("candidate_pending", "fail", "not_pending", candidate_id))
    else:
        checks.append(_check("candidate_pending", "pass", "pending", candidate_id))

    missing = _missing_provenance(record)
    if missing:
        checks.append(
            _check("candidate_provenance", "fail", "missing:" + ",".join(missing), candidate_id)
        )
    else:
        checks.append(_check("candidate_provenance", "pass", "complete", candidate_id))

    admission = candidate_admission_issue(dict(record))
    if admission == "unsafe_destination":
        checks.append(_check("candidate_source_url", "fail", "unsafe_destination", candidate_id))
    elif admission is not None:
        checks.append(_check("candidate_source_url", "fail", "unsupported_candidate", candidate_id))
    else:
        checks.append(_check("candidate_source_url", "pass", "approved_host", candidate_id))

    extraction: Optional[Dict[str, Any]] = None
    if record.get("status") == "extracted":
        try:
            extraction = _read_extracted_document(quarantine_root, record)
        except _ExtractionError as error:
            checks.append(_check("candidate_extraction", "fail", error.reason, candidate_id))
        else:
            if extraction["replacement_characters"]:
                checks.append(
                    _check(
                        "candidate_extraction",
                        "fail",
                        "extraction_uncertain:{}".format(extraction["replacement_characters"]),
                        candidate_id,
                    )
                )
                questions.append(
                    "Candidate {} has {} replacement characters in its extracted text; "
                    "compare the official original before approving any passage.".format(
                        candidate_id, extraction["replacement_characters"]
                    )
                )
            else:
                checks.append(
                    _check("candidate_extraction", "pass", "digest_and_text_verified", candidate_id)
                )
        original_status, original_detail = _original_bytes_status(quarantine_root, record)
        checks.append(
            _check("candidate_original_bytes", original_status, original_detail, candidate_id)
        )
        if original_detail == "original_bytes_unavailable":
            questions.append(
                "Candidate {} has no original copy in the quarantine; the reviewer must "
                "compare the extracted text with the official original.".format(candidate_id)
            )
    else:
        checks.append(
            _check("candidate_extraction", "fail", "not_extracted", candidate_id)
        )
        checks.append(
            _check("candidate_original_bytes", "fail", "not_extracted", candidate_id)
        )

    reasons = set(impact.get("review", {}).get("reasons", []))
    acknowledged = set(resolution.get("findings", [])) if resolution else set()
    mismatched = sorted(acknowledged - reasons)
    unresolved = sorted((reasons & set(RESOLVABLE_FINDINGS)) - acknowledged)
    analysis_failure = impact.get("analysis_failure")
    if analysis_failure not in (None, "no_extracted_document") or "analysis_failed" in reasons:
        checks.append(
            _check("candidate_impact", "fail", "impact_analysis_failed", candidate_id)
        )
    elif mismatched:
        checks.append(
            _check(
                "candidate_impact",
                "fail",
                "resolution_mismatch:" + ",".join(mismatched),
                candidate_id,
            )
        )
    elif unresolved:
        checks.append(
            _check(
                "candidate_impact",
                "fail",
                "unresolved:" + ",".join(unresolved),
                candidate_id,
            )
        )
    else:
        checks.append(_check("candidate_impact", "pass", "analyzed", candidate_id))

    for finding in sorted(reasons & set(RESOLVABLE_FINDINGS)):
        if resolution and finding in acknowledged:
            note, _ = _bounded(resolution["note"])
            questions.append(
                "Candidate {} was classified '{}'; the proposal acknowledges this, and "
                "the reviewer must confirm the resolution note still applies: {}".format(
                    candidate_id, finding, note
                )
            )
    if "text_changed_without_signal" in reasons and "text_changed_without_signal" not in acknowledged:
        questions.append(
            "Candidate {} changed text without a recognisable change signal; the reviewer "
            "must read the diff and decide whether the corpus needs an edit.".format(candidate_id)
        )

    if unknown_fields:
        checks.append(
            _check(
                "candidate_unknowns",
                "fail",
                "unknown_fields:" + ",".join(unknown_fields),
                candidate_id,
            )
        )
        questions.append(
            "Candidate {} leaves {} unknown; the catalog fields stay absent and must not "
            "be inferred.".format(candidate_id, ", ".join(unknown_fields))
        )
    else:
        checks.append(_check("candidate_unknowns", "pass", "no_declared_unknowns", candidate_id))

    evidence = {
        "candidate_id": candidate_id,
        "issuer": record.get("issuer"),
        "title": record.get("title"),
        "stable_identity": record.get("stable_identity"),
        "publication_url": record.get("publication_url"),
        "registry": {
            "id": record.get("registry_id"),
            "url": record.get("registry_url"),
        },
        "observation": {
            "attempted_at": record.get("last_attempt_at"),
            "succeeded_at": record.get("last_success_at"),
            "version_hash": record.get("version_hash"),
        },
        "integrity": {
            "original_sha256": record.get("original_sha256"),
            "previous_original_sha256": record.get("previous_original_sha256"),
            "extracted_text_sha256": record.get("extracted_text_sha256"),
            "extractor": record.get("extractor"),
            "media_type": record.get("media_type"),
            "declared_content_type": record.get("declared_content_type"),
            "byte_size": record.get("byte_size"),
            "page_count": record.get("page_count"),
            "block_count": record.get("block_count"),
        },
        "documents": {
            "original_path": record.get("original_path"),
            "extracted_path": record.get("extracted_path"),
            "sections": extraction["sections"] if extraction else [],
            "replacement_characters": (
                extraction["replacement_characters"] if extraction else None
            ),
        },
        "ingestion_status": extracted_status,
        "version_status": impact.get("version_status"),
        "text_diff": impact.get("version", {}).get("text_diff"),
        "signals": [
            {
                "kind": signal.get("kind"),
                "classification": signal.get("classification"),
                "reason": signal.get("reason"),
                "page": signal.get("page"),
                "section": signal.get("section"),
                "excerpt": signal.get("excerpt"),
                "instrument_keys": list(signal.get("instrument_keys", [])),
            }
            for signal in impact.get("signals", [])
        ],
        "potentially_affected": {
            "sources": list(impact.get("potentially_affected", {}).get("sources", [])),
            "passages": list(impact.get("potentially_affected", {}).get("passages", [])),
            "evaluation_cases": list(
                impact.get("potentially_affected", {}).get("evaluation_cases", [])
            ),
        },
        "resolution": (
            {"findings": list(resolution["findings"]), "note": resolution["note"]}
            if resolution
            else None
        ),
        "declared_unknowns": list(unknown_fields),
    }
    return evidence, checks, questions


# --- Proposed changes -------------------------------------------------------


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _proposed_unknown_value(entries: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        _fold(text) in UNKNOWN_VALUE_TOKENS
        for entry in entries
        for text in _iter_strings(entry)
    )


def _render_value(value: Any) -> Tuple[Optional[str], bool]:
    if value is None:
        return None, False
    return _bounded(value)


def _diff_items(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    *,
    target: str,
) -> Tuple[List[Dict[str, Any]], bool]:
    before_by_id = {item.get("id"): item for item in before}
    after_by_id = {item.get("id"): item for item in after}
    differences: List[Dict[str, Any]] = []
    truncated = False

    def field(name: str, before_value: Any, after_value: Any) -> Dict[str, Any]:
        nonlocal truncated
        before_text, before_cut = _render_value(before_value)
        after_text, after_cut = _render_value(after_value)
        cut = before_cut or after_cut
        truncated = truncated or cut
        return {
            "name": name,
            "before": before_text,
            "after": after_text,
            "truncated": cut,
        }

    def add_difference(action: str, entry_id: Any, fields: List[Dict[str, Any]]) -> None:
        nonlocal truncated
        if len(fields) == 0:
            return
        if len(diff_pairs) >= MAX_DIFFS:
            truncated = True
            return
        diff_pairs.append((action, entry_id, fields))

    diff_pairs: List[Tuple[str, Any, List[Dict[str, Any]]]] = []

    for entry_id in [item.get("id") for item in after if item.get("id") not in before_by_id]:
        entry = after_by_id[entry_id]
        add_difference(
            "added",
            entry_id,
            [field(name, None, entry[name]) for name in sorted(entry)],
        )

    for entry_id in [item.get("id") for item in before if item.get("id") not in after_by_id]:
        entry = before_by_id[entry_id]
        add_difference(
            "removed",
            entry_id,
            [field(name, entry[name], None) for name in sorted(entry)],
        )

    for entry_id in sorted(set(before_by_id) & set(after_by_id), key=str):
        entry_before, entry_after = before_by_id[entry_id], after_by_id[entry_id]
        changed = [
            field(name, entry_before.get(name), entry_after.get(name))
            for name in sorted(set(entry_before) | set(entry_after))
            if entry_before.get(name) != entry_after.get(name)
        ]
        add_difference("updated", entry_id, changed)

    for action, entry_id, fields in diff_pairs:
        differences.append(
            {"target": target, "change": action, "id": entry_id, "fields": fields}
        )
    return differences, truncated


def _proposal_differences(
    before_catalog: Mapping[str, Any],
    after_catalog: Mapping[str, Any],
    before_passages: Mapping[str, Any],
    after_passages: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], bool]:
    catalog_diff, catalog_truncated = _diff_items(
        before_catalog.get("sources", []), after_catalog.get("sources", []), target="catalog"
    )
    passages_diff, passages_truncated = _diff_items(
        before_passages.get("passages", []),
        after_passages.get("passages", []),
        target="passages",
    )
    return catalog_diff + passages_diff, catalog_truncated or passages_truncated


def _proposal_has_changes(proposal: Mapping[str, Any]) -> bool:
    return any(
        proposal[section][key]
        for section in ("catalog", "passages")
        for key in ("add", "update", "remove")
    )


def _passage_source_index(
    before_passages: Mapping[str, Any], after_passages: Mapping[str, Any]
) -> Dict[str, Any]:
    """Map every known passage id to its source, before or after the proposal."""
    sources = {
        passage.get("id"): passage.get("source_id")
        for passage in before_passages.get("passages", [])
    }
    sources.update(
        {
            passage.get("id"): passage.get("source_id")
            for passage in after_passages.get("passages", [])
        }
    )
    return sources


def _provenance_link_checks(
    proposal: Mapping[str, Any],
    selected: Mapping[str, Mapping[str, Any]],
    state_records: Mapping[str, Mapping[str, Any]],
    passage_sources: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Check a selected-candidate link for every catalog and passage change.

    Added or updated sources must match the linked candidate's original hash
    and publication URL. Removals and passage edits cannot match removed bytes,
    so they require the same explicit source-to-candidate link instead. A link
    can only point at a candidate selected by the proposal (``load_proposal``
    also enforces that), and the linked candidate must exist in the ingestion
    state. The single check keeps its detail truthful about which class of
    change it inspected.
    """
    links_by_source: Dict[str, List[Mapping[str, Any]]] = {}
    for link in proposal["links"]:
        links_by_source.setdefault(link["source_id"], []).append(link)

    problems: List[str] = []
    passes: List[str] = []

    def linked_record(source_id: Any, label: str) -> Tuple[Optional[Mapping[str, Any]], Optional[str]]:
        if not isinstance(source_id, str) or not source_id.strip():
            return None, "source_id_missing"
        links = links_by_source.get(source_id, [])
        if len(links) != 1:
            return None, "{}:{}".format(label, source_id)
        candidate_id = links[0]["candidate_id"]
        if candidate_id not in selected:
            return None, "unselected_candidate:{}".format(source_id)
        return state_records.get(candidate_id), None

    catalog_add_update = list(proposal["catalog"]["add"]) + list(
        proposal["catalog"]["update"]
    )
    passage_add_update = list(proposal["passages"]["add"]) + list(
        proposal["passages"]["update"]
    )
    catalog_removals = list(proposal["catalog"]["remove"])
    passage_removals = list(proposal["passages"]["remove"])

    for entry in catalog_add_update:
        source_id = entry.get("id")
        record, problem = linked_record(source_id, "unlinked_source")
        if problem is not None:
            problems.append(problem)
            continue
        if record is None or (
            entry.get("content_sha256") != record.get("original_sha256")
            or entry.get("original_url") != record.get("publication_url")
        ):
            problems.append("provenance_mismatch:{}".format(source_id))
            continue
        passes.append("source_matches_candidate:{}".format(source_id))

    for source_id in catalog_removals:
        record, problem = linked_record(source_id, "unlinked_removal")
        if problem is not None:
            problems.append(problem)
            continue
        if record is None:
            problems.append("unknown_candidate:{}".format(source_id))
            continue
        passes.append("removal_linked:{}".format(source_id))

    for entry in passage_add_update:
        passage_id = entry.get("id")
        source_id = entry.get("source_id") or passage_sources.get(passage_id)
        record, problem = linked_record(source_id, "unlinked_passage")
        if problem is not None:
            problems.append(problem)
            continue
        if source_id is None:
            problems.append("passage_source_missing:{}".format(passage_id))
            continue
        passes.append("passage_linked:{}".format(passage_id))

    for passage_id in passage_removals:
        source_id = passage_sources.get(passage_id)
        record, problem = linked_record(source_id, "unlinked_removal")
        if problem is not None:
            problems.append(problem)
            continue
        if source_id is None:
            problems.append("passage_source_missing:{}".format(passage_id))
            continue
        passes.append("passage_removal_linked:{}".format(passage_id))

    has_changes = bool(
        catalog_add_update
        or passage_add_update
        or catalog_removals
        or passage_removals
    )
    if not has_changes:
        return [_check("proposal_provenance", "pass", "no_catalog_add_or_update")]

    prefix = ""
    if not catalog_add_update and not passage_add_update and (
        catalog_removals or passage_removals
    ):
        prefix = "removals_only"
    elif not catalog_add_update and not catalog_removals:
        prefix = "passages_only"

    parts = problems or passes
    detail = ";".join(parts) if parts else "no_change_details"
    if prefix:
        detail = "{}:{}".format(prefix, detail)
    status = "fail" if problems else "pass"
    return [_check("proposal_provenance", status, detail)]


def _evaluation_case_status(
    cases: Sequence[Mapping[str, Any]],
    after_catalog: Mapping[str, Any],
    after_passages: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> Tuple[List[str], List[str]]:
    """Return (orphaned, rewritten) case ids against the proposed state.

    A case is orphaned when one of its expected sources or passages no longer
    exists after the proposal. It is rewritten when a still-referenced entry is
    an explicit update, because the reviewed expectation may no longer match the
    new text even though the ids still resolve.
    """
    catalog_ids = {entry.get("id") for entry in after_catalog.get("sources", [])}
    passage_ids = {entry.get("id") for entry in after_passages.get("passages", [])}
    updated_sources = {entry.get("id") for entry in proposal["catalog"]["update"]}
    updated_passages = {entry.get("id") for entry in proposal["passages"]["update"]}
    orphaned: List[str] = []
    rewritten: List[str] = []
    for case in cases:
        expected_sources = set(case.get("expected_source_ids", ()))
        expected_passages = set(case.get("expected_passage_ids", ()))
        if not expected_sources <= catalog_ids or not expected_passages <= passage_ids:
            orphaned.append(case["id"])
            continue
        if expected_sources & updated_sources or expected_passages & updated_passages:
            rewritten.append(case["id"])
    return orphaned, rewritten



# --- Preparing a package ----------------------------------------------------


def prepare(
    ingestion_state: Path,
    quarantine_dir: Path,
    catalog_path: Path,
    passages_path: Path,
    proposal_path: Path,
    reviewers: Sequence[str],
    as_of: Optional[date],
    workspace: Path,
    cases_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Prepare one draft review package and write it under ``workspace``.

    Returns ``{"package": ..., "package_dir": ..., "exit_code": 0|1}``. Every
    input is read-only; canonical knowledge is byte-identical afterwards. The
    package is ``ready_for_review`` only when no automated check failed.
    """
    if not isinstance(as_of, date):
        raise ReviewPackageError("invalid_as_of")
    if _inside_directory(workspace, KNOWLEDGE_ROOT):
        raise ReviewPackageError("unsafe_workspace")

    catalog_bytes = _read_bytes(catalog_path, "invalid_catalog")
    try:
        catalog = load_catalog(catalog_path)
    except Exception as error:  # noqa: BLE001 - fixed failure, never echoed
        raise ReviewPackageError("invalid_catalog") from error
    if not isinstance(catalog, dict):
        raise ReviewPackageError("invalid_catalog")
    if validate_catalog(catalog, as_of).issues:
        raise ReviewPackageError("invalid_catalog")

    passages_bytes = _read_bytes(passages_path, "invalid_passage_set")
    try:
        passages = load_passage_set(passages_path)
    except Exception as error:  # noqa: BLE001
        raise ReviewPackageError("invalid_passage_set") from error
    if not isinstance(passages, dict) or not validate_passage_set(passages).ok:
        raise ReviewPackageError("invalid_passage_set")
    catalog_ids = {source["id"] for source in catalog["sources"]}
    if any(passage.get("source_id") not in catalog_ids for passage in passages["passages"]):
        raise ReviewPackageError("invalid_passage_set")

    try:
        state = load_ingestion_state(ingestion_state)
    except ImpactAnalysisError as error:
        raise ReviewPackageError("invalid_ingestion_state") from error
    state_records = state["candidates"]

    # The package body is stored as sorted canonical JSON, so normalize the
    # proposal through that same representation before computing after hashes.
    # Otherwise a proposed entry's input order would change between preparation
    # and merge and a legitimate merge would report canonical_drift.
    proposal = json.loads(_canonical_json(load_proposal(proposal_path)))
    selected = {
        item["candidate_id"]: item for item in proposal["candidates"]
    }
    for candidate_id in selected:
        if candidate_id not in state_records:
            raise ReviewPackageError("invalid_proposal")
    if len(selected) > MAX_CANDIDATES_PER_PACKAGE:
        raise ReviewPackageError("candidate_count_exceeded")

    try:
        impact = analyze_change_impact(
            ingestion_state,
            quarantine_dir,
            catalog_path,
            passages_path,
            cases_path=cases_path,
            as_of=as_of,
        )
    except ImpactAnalysisError as error:
        raise ReviewPackageError(error.failure) from error
    impact_by_id = {item["candidate_id"]: item for item in impact["candidates"]}
    if any(candidate_id not in impact_by_id for candidate_id in selected):
        raise ReviewPackageError("invalid_proposal")

    requested_reviewers = sorted(
        {reviewer.strip() for reviewer in reviewers if isinstance(reviewer, str) and reviewer.strip()}
    )
    if not requested_reviewers:
        raise ReviewPackageError("reviewer_required")
    author = proposal["author"]
    for reviewer in requested_reviewers:
        if _is_automated(reviewer):
            raise ReviewPackageError("reviewer_not_human")
        if _fold(reviewer) == _fold(author["identity"]):
            raise ReviewPackageError("reviewer_is_author")

    checks: List[Dict[str, Any]] = []
    questions: List[str] = []
    evidence: List[Dict[str, Any]] = []
    for candidate_id in sorted(selected):
        item = selected[candidate_id]
        candidate_evidence, candidate_checks, candidate_questions = (
            _candidate_checks_and_evidence(
                state_records[candidate_id],
                impact_by_id[candidate_id],
                Path(quarantine_dir),
                item["resolution"],
                item["unknown_fields"],
            )
        )
        evidence.append(candidate_evidence)
        checks.extend(candidate_checks)
        questions.extend(candidate_questions)

    before_catalog = json.loads(json.dumps(catalog))
    before_passages = json.loads(json.dumps(passages))
    after_catalog = _apply_section(before_catalog, "sources", proposal["catalog"])
    after_passages = _apply_section(before_passages, "passages", proposal["passages"])

    catalog_report = validate_catalog(after_catalog, as_of)
    if catalog_report.issues:
        checks.append(_check("proposal_catalog", "fail", "invalid_catalog"))
    else:
        checks.append(_check("proposal_catalog", "pass", "validated"))

    after_catalog_ids = {source["id"] for source in after_catalog["sources"]}
    passage_report = validate_passage_set(after_passages)
    dangling = [
        passage.get("id")
        for passage in after_passages["passages"]
        if passage.get("source_id") not in after_catalog_ids
    ]
    if not passage_report.ok or dangling:
        checks.append(_check("proposal_passages", "fail", "invalid_passage_set"))
    else:
        checks.append(_check("proposal_passages", "pass", "validated"))

    proposed_entries: List[Mapping[str, Any]] = []
    for section in ("catalog", "passages"):
        proposed_entries.extend(proposal[section]["add"])
        proposed_entries.extend(proposal[section]["update"])
    if _proposed_unknown_value(proposed_entries):
        checks.append(_check("proposal_unknown_values", "fail", "inferred_unknown_value"))
    else:
        checks.append(_check("proposal_unknown_values", "pass", "no_inferred_unknowns"))

    reviewed_cases: List[Mapping[str, Any]] = []
    cases_sha: Optional[str] = None
    orphaned_cases: List[str] = []
    rewritten_cases: List[str] = []
    if cases_path is not None:
        cases_bytes = _read_bytes(cases_path, "invalid_evaluation_cases")
        cases_sha = _sha256(cases_bytes)
        try:
            reviewed_cases = load_evaluation_cases(cases_path, catalog, passages)
        except ImpactAnalysisError as error:
            raise ReviewPackageError(error.failure) from error
        orphaned_cases, rewritten_cases = _evaluation_case_status(
            reviewed_cases, after_catalog, after_passages, proposal
        )
        after_case_error = None
        try:
            load_evaluation_cases(cases_path, after_catalog, after_passages)
        except ImpactAnalysisError as error:
            after_case_error = error
        if orphaned_cases:
            detail = "orphaned_cases:" + ",".join(orphaned_cases)
            checks.append(_check("proposal_evaluation_impact", "fail", detail))
            questions.append(
                "Proposal removes or replaces knowledge referenced by reviewed "
                "answer-evaluation case(s) {}; update or retire those cases in a "
                "separate reviewed change before approving this package, or withdraw "
                "the removal.".format(", ".join(orphaned_cases))
            )
        elif after_case_error is not None:
            checks.append(
                _check("proposal_evaluation_impact", "fail", "invalid_evaluation_cases")
            )
            questions.append(
                "The proposal produces catalog/passages that the reviewed "
                "answer-evaluation case set cannot validate; a reviewer must fix "
                "the after-state before this package can be approved."
            )
        else:
            checks.append(
                _check("proposal_evaluation_impact", "pass", "validated_against_after")
            )
        if rewritten_cases:
            questions.append(
                "Reviewed evaluation case(s) {} reference catalog or passage entries "
                "this proposal updates; re-run and review the evaluation after merge. "
                "This is a report-only reminder, not a re-run.".format(
                    ", ".join(rewritten_cases)
                )
            )
    elif _proposal_has_changes(proposal):
        checks.append(
            _check("proposal_evaluation_impact", "fail", "cases_unavailable")
        )
        questions.append(
            "This proposal changes the reviewed corpus, but no reviewed "
            "answer-evaluation case set was supplied. Provide --cases so the "
            "after-state can be validated, or withdraw the catalog/passage changes."
        )
    else:
        checks.append(_check("proposal_evaluation_impact", "pass", "no_changes"))

    checks.extend(
        _provenance_link_checks(
            proposal,
            selected,
            state_records,
            _passage_source_index(before_passages, after_passages),
        )
    )

    affected_cases: Dict[str, Set[str]] = {}
    affected_sources: Dict[str, Set[str]] = {}
    affected_passages: Dict[str, Set[str]] = {}
    for item in evidence:
        for case in item["potentially_affected"]["evaluation_cases"]:
            affected_cases.setdefault(case["id"], set()).update(case.get("reasons", []))
        for source in item["potentially_affected"]["sources"]:
            affected_sources.setdefault(source["id"], set()).update(source.get("reasons", []))
        for passage in item["potentially_affected"]["passages"]:
            affected_passages.setdefault(passage["id"], set()).update(
                passage.get("reasons", [])
            )
    checks.append(
        _check(
            "evaluation_impact",
            "report_only",
            "affected_cases:{}".format(len(affected_cases)),
        )
    )

    before_catalog_sha = _sha256(catalog_bytes)
    before_passages_sha = _sha256(passages_bytes)
    after_catalog_text = _ordered_json(after_catalog)
    after_passages_text = _ordered_json(after_passages)
    after_catalog_sha = _sha256(after_catalog_text.encode("utf-8"))
    after_passages_sha = _sha256(after_passages_text.encode("utf-8"))
    differences, differences_truncated = _proposal_differences(
        before_catalog, after_catalog, before_passages, after_passages
    )

    failed = [check for check in checks if check["status"] == "fail"]
    readiness = "needs_human_attention" if failed else "ready_for_review"
    blocking_reasons = [
        "{}:{}".format(check["id"], check["detail"]) for check in failed
    ]

    for question in proposal["unresolved_questions"]:
        questions.append(question)
    if affected_cases:
        questions.append(
            "{} reviewed answer-evaluation case(s) may be affected; re-run the PAC "
            "evaluation after merge. This report is not a pass/fail gate.".format(
                len(affected_cases)
            )
        )
    questions = _bounded_questions(questions)

    package_body: Dict[str, Any] = {
        "schema_version": PACKAGE_VERSION,
        "preparer": PREPARER,
        "prepared_on": as_of.isoformat(),
        "author": author,
        "review": {
            "requires_human_review": True,
            "draft": True,
            "requested_reviewers": requested_reviewers,
            "independent_reviewer_required": True,
            "bot_or_ci_is_not_approval": True,
            "merge_protection": {
                "hosting_platform_enforced": False,
                "controlled_merge_verifies_approval": True,
            },
        },
        "package_kind": "coherent_batch" if len(selected) > 1 else "single_update",
        "summary": proposal["summary"],
        "candidates": evidence,
        "proposal": {
            "input": proposal,
            "before": {
                "catalog_sha256": before_catalog_sha,
                "passages_sha256": before_passages_sha,
            },
            "after": {
                "catalog_sha256": after_catalog_sha,
                "passages_sha256": after_passages_sha,
            },
            "differences": differences,
            "differences_truncated": differences_truncated,
            "evaluation": {
                "cases_available": cases_path is not None,
                "cases_sha256": cases_sha,
                "case_count": len(reviewed_cases),
                "validated_against": "after",
                "orphaned_case_ids": orphaned_cases,
                "rewritten_case_ids": rewritten_cases,
            },
        },
        "affected": {
            "sources": [
                {"id": source_id, "reasons": sorted(reasons)}
                for source_id, reasons in sorted(affected_sources.items())
            ],
            "passages": [
                {"id": passage_id, "reasons": sorted(reasons)}
                for passage_id, reasons in sorted(affected_passages.items())
            ],
            "evaluation_cases": [
                {"id": case_id, "reasons": sorted(reasons)}
                for case_id, reasons in sorted(affected_cases.items())
            ],
            "evaluation_report_only": True,
            "evaluation_statement": (
                "Affected reviewed answer-evaluation cases are reported for manual "
                "re-evaluation after merge. They are not re-run here and are not a "
                "pass/fail gate or a quality claim."
            ),
        },
        "checks": checks,
        "check_summary": {
            "passed": sum(1 for check in checks if check["status"] == "pass"),
            "failed": len(failed),
            "report_only": sum(1 for check in checks if check["status"] == "report_only"),
            "failed_checks": [check["id"] for check in failed],
        },
        "merge_readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "unresolved_questions": questions,
        "limits": list(PACKAGE_LIMITS),
    }
    package_id = _sha256(_canonical_json(package_body).encode("utf-8"))
    package = {"package_id": package_id, **package_body}

    package_dir = Path(workspace) / package_id
    _atomic_write_text(package_dir / "package.json", _canonical_json(package))
    _atomic_write_text(package_dir / "REVIEW.md", render_review_markdown(package))
    return {
        "package": package,
        "package_dir": package_dir,
        "exit_code": 0 if readiness == "ready_for_review" else 1,
    }


def _bounded_questions(questions: Sequence[str]) -> List[str]:
    unique: List[str] = []
    for question in questions:
        if question not in unique:
            unique.append(question)
    if len(unique) > MAX_UNRESOLVED_QUESTIONS:
        unique = unique[:MAX_UNRESOLVED_QUESTIONS] + [
            "More unresolved questions were truncated; read the package evidence."
        ]
    return unique


# --- Decisions --------------------------------------------------------------


def load_package(package_dir: Path) -> Dict[str, Any]:
    """Load one package and verify its content digest and required shape."""
    path = Path(package_dir)
    file = path / "package.json" if path.is_dir() else path
    try:
        package = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewPackageError("invalid_review_package") from error
    if not isinstance(package, dict) or package.get("schema_version") != PACKAGE_VERSION:
        raise ReviewPackageError("invalid_review_package")
    if not set(REQUIRED_PACKAGE_KEYS) <= set(package):
        raise ReviewPackageError("invalid_review_package")
    package_id = package.get("package_id")
    if not isinstance(package_id, str) or not SHA256_PATTERN.fullmatch(package_id):
        raise ReviewPackageError("invalid_review_package")
    body = {key: value for key, value in package.items() if key != "package_id"}
    if _sha256(_canonical_json(body).encode("utf-8")) != package_id:
        raise ReviewPackageError("invalid_review_package")
    if not _valid_package_shape(package):
        raise ReviewPackageError("invalid_review_package")
    return package


def _valid_package_shape(package: Mapping[str, Any]) -> bool:
    """Check the fields this module reads without duplicating the full schema."""
    author = package.get("author")
    if (
        not isinstance(author, dict)
        or not isinstance(author.get("identity"), str)
        or not author["identity"].strip()
        or author.get("kind") not in ("human", "automation")
    ):
        return False
    prepared_on = package.get("prepared_on")
    if not isinstance(prepared_on, str) or not DATE_PATTERN.fullmatch(prepared_on):
        return False
    try:
        date.fromisoformat(prepared_on)
    except ValueError:
        return False
    if (
        not isinstance(package.get("summary"), str)
        or not package["summary"].strip()
        or package.get("merge_readiness") not in ("ready_for_review", "needs_human_attention")
        or not isinstance(package.get("candidates"), list)
        or not isinstance(package.get("checks"), list)
        or not isinstance(package.get("blocking_reasons"), list)
        or not isinstance(package.get("unresolved_questions"), list)
        or not isinstance(package.get("limits"), list)
    ):
        return False
    summary = package.get("check_summary")
    if (
        not isinstance(summary, dict)
        or not isinstance(summary.get("failed"), int)
        or isinstance(summary.get("failed"), bool)
    ):
        return False
    review = package.get("review")
    if (
        not isinstance(review, dict)
        or not isinstance(review.get("requested_reviewers"), list)
        or not review["requested_reviewers"]
        or any(
            not isinstance(reviewer, str) or not reviewer.strip()
            for reviewer in review["requested_reviewers"]
        )
    ):
        return False
    proposal = package.get("proposal")
    if (
        not isinstance(proposal, dict)
        or not set(REQUIRED_PROPOSAL_KEYS) <= set(proposal)
        or not isinstance(proposal.get("input"), dict)
        or not isinstance(proposal.get("differences"), list)
        or not isinstance(proposal.get("differences_truncated"), bool)
    ):
        return False
    evaluation = proposal.get("evaluation")
    if (
        not isinstance(evaluation, dict)
        or not set(REQUIRED_EVALUATION_KEYS) <= set(evaluation)
        or not isinstance(evaluation.get("cases_available"), bool)
        or (
            evaluation.get("cases_sha256") is not None
            and (
                not isinstance(evaluation.get("cases_sha256"), str)
                or not SHA256_PATTERN.fullmatch(evaluation["cases_sha256"])
            )
        )
        or not isinstance(evaluation.get("case_count"), int)
        or isinstance(evaluation.get("case_count"), bool)
        or evaluation.get("validated_against") != "after"
        or not isinstance(evaluation.get("orphaned_case_ids"), list)
        or not isinstance(evaluation.get("rewritten_case_ids"), list)
    ):
        return False
    input_proposal = proposal["input"]
    if (
        not set(("schema_version", "summary", "candidates", "catalog", "passages"))
        <= set(input_proposal)
        or not isinstance(input_proposal.get("candidates"), list)
    ):
        return False
    for key in ("catalog", "passages"):
        section = input_proposal.get(key)
        if (
            not isinstance(section, dict)
            or not set(("add", "update", "remove")) <= set(section)
            or not all(
                isinstance(section.get(name), list) for name in ("add", "update", "remove")
            )
        ):
            return False
    for key in ("before", "after"):
        hashes = proposal.get(key)
        if not isinstance(hashes, dict) or not set(REQUIRED_HASH_KEYS) <= set(hashes):
            return False
        if any(
            not isinstance(hashes[name], str) or not SHA256_PATTERN.fullmatch(hashes[name])
            for name in REQUIRED_HASH_KEYS
        ):
            return False
    return True


def _requested_reviewer_names(package: Mapping[str, Any]) -> Set[str]:
    return {
        _fold(reviewer)
        for reviewer in package.get("review", {}).get("requested_reviewers", [])
        if isinstance(reviewer, str) and reviewer.strip()
    }


def _checks_digest(package: Mapping[str, Any]) -> str:
    return _sha256(
        _canonical_json(
            {
                "checks": package.get("checks", []),
                "merge_readiness": package.get("merge_readiness"),
            }
        ).encode("utf-8")
    )


def _decisions_path(package_dir: Path) -> Path:
    path = Path(package_dir)
    return path / "decisions.json" if path.is_dir() else path


def load_decisions(package_dir: Path) -> Optional[Dict[str, Any]]:
    path = _decisions_path(package_dir)
    if not path.exists():
        return None
    try:
        decisions = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewPackageError("invalid_review_decisions") from error
    if (
        not isinstance(decisions, dict)
        or decisions.get("schema_version") != DECISIONS_VERSION
        or not isinstance(decisions.get("history"), list)
        or not decisions["history"]
    ):
        raise ReviewPackageError("invalid_review_decisions")
    for entry in decisions["history"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("sequence"), int)
            or isinstance(entry.get("sequence"), bool)
            or not isinstance(entry.get("reviewer"), str)
            or not entry["reviewer"].strip()
            or entry.get("decision") not in DECISIONS
            or not isinstance(entry.get("decided_on"), str)
            or not DATE_PATTERN.fullmatch(entry["decided_on"])
            or not isinstance(entry.get("note"), str)
            or entry.get("package_id") != decisions.get("package_id")
            or not isinstance(entry.get("checks_digest"), str)
        ):
            raise ReviewPackageError("invalid_review_decisions")
    return decisions


def record_decision(
    package_dir: Path,
    reviewer: str,
    decision: str,
    decided_on: Optional[date],
    note: str = "",
) -> Dict[str, Any]:
    """Record one reviewer decision; an approval is accepted only when eligible."""
    package = load_package(package_dir)
    if (Path(package_dir) / "merge.json").exists():
        raise ReviewPackageError("already_merged")
    if decision not in DECISIONS:
        raise ReviewPackageError("invalid_decision")
    if not isinstance(decided_on, date):
        raise ReviewPackageError("invalid_decision_date")
    prepared_on = date.fromisoformat(package["prepared_on"])
    if decided_on < prepared_on:
        raise ReviewPackageError("invalid_decision_date")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewPackageError("reviewer_required")
    reviewer = reviewer.strip()
    if _is_automated(reviewer):
        raise ReviewPackageError("reviewer_not_human")
    author_identity = package["author"]["identity"]
    if _fold(reviewer) == _fold(author_identity):
        raise ReviewPackageError("self_approval")
    if decision == "approve":
        if _fold(reviewer) not in _requested_reviewer_names(package):
            raise ReviewPackageError("reviewer_not_requested")
        if package.get("merge_readiness") != "ready_for_review":
            raise ReviewPackageError("approval_blocked")
        if package.get("check_summary", {}).get("failed"):
            raise ReviewPackageError("approval_blocked")
    if not isinstance(note, str):
        raise ReviewPackageError("invalid_decision")

    decisions = load_decisions(package_dir)
    if decisions is None:
        decisions = {
            "schema_version": DECISIONS_VERSION,
            "package_id": package["package_id"],
            "author": package["author"],
            "checks_digest": _checks_digest(package),
            "history": [],
            "effective_decision": None,
            "approved_by": None,
        }
    if decisions.get("package_id") != package["package_id"]:
        raise ReviewPackageError("invalid_review_decisions")
    if decisions.get("checks_digest") != _checks_digest(package):
        raise ReviewPackageError("stale_approval")

    history = list(decisions["history"])
    history.append(
        {
            "sequence": len(history) + 1,
            "reviewer": reviewer,
            "decision": decision,
            "decided_on": decided_on.isoformat(),
            "note": note.strip(),
            "package_id": package["package_id"],
            "checks_digest": _checks_digest(package),
        }
    )
    decisions["history"] = history
    decisions["effective_decision"] = EFFECTIVE_DECISIONS[decision]
    decisions["approved_by"] = reviewer if decision == "approve" else None
    _atomic_write_text(_decisions_path(package_dir), _canonical_json(decisions))
    _atomic_write_text(Path(package_dir) / "DECISION.md", render_decisions_markdown(decisions))
    return decisions


def render_decisions_markdown(decisions: Mapping[str, Any]) -> str:
    lines = [
        "# Review history",
        "",
        "Package: `{}`".format(decisions["package_id"]),
        "",
        "Every decision below is recorded in order. Approval is a named human "
        "decision; a bot, label, CI status, or hash is not approval.",
        "",
        "| # | Reviewer | Decision | Date | Note |",
        "|---|---|---|---|---|",
    ]
    for entry in decisions.get("history", []):
        note = (entry.get("note") or "").replace("|", "\\|")
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                entry.get("sequence"),
                entry.get("reviewer"),
                entry.get("decision"),
                entry.get("decided_on"),
                note,
            )
        )
    lines.extend(
        [
            "",
            "Effective decision: `{}`".format(decisions.get("effective_decision")),
            "Approved by: `{}`".format(decisions.get("approved_by")),
            "",
        ]
    )
    return "\n".join(lines)


# --- Controlled merge -------------------------------------------------------


def merge(
    package_dir: Path,
    catalog_path: Path,
    passages_path: Path,
    cases_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write the approved proposal; refuse every unapproved or stale package.

    When the package recorded a case-set digest, the same case file must be
    supplied and must still match. This closes the gap where the reviewed cases
    could change after preparation and silently stop covering the new corpus.
    """
    package = load_package(package_dir)
    if (Path(package_dir) / "merge.json").exists():
        raise ReviewPackageError("already_merged")
    decisions = load_decisions(package_dir)
    if decisions is None or decisions.get("effective_decision") != "approved":
        raise ReviewPackageError("approval_required")
    if decisions.get("package_id") != package["package_id"]:
        raise ReviewPackageError("invalid_review_decisions")
    if decisions.get("checks_digest") != _checks_digest(package):
        raise ReviewPackageError("stale_approval")
    reviewer = decisions.get("approved_by")
    if not isinstance(reviewer, str) or not reviewer.strip() or _is_automated(reviewer):
        raise ReviewPackageError("approval_required")
    if _fold(reviewer) == _fold(package["author"]["identity"]):
        raise ReviewPackageError("self_approval")
    if _fold(reviewer) not in _requested_reviewer_names(package):
        raise ReviewPackageError("reviewer_not_requested")
    if package.get("merge_readiness") != "ready_for_review":
        raise ReviewPackageError("approval_blocked")
    if package.get("check_summary", {}).get("failed"):
        raise ReviewPackageError("approval_blocked")

    catalog_bytes = _read_bytes(catalog_path, "invalid_catalog")
    passages_bytes = _read_bytes(passages_path, "invalid_passage_set")
    if _sha256(catalog_bytes) != package["proposal"]["before"]["catalog_sha256"]:
        raise ReviewPackageError("canonical_drift")
    if _sha256(passages_bytes) != package["proposal"]["before"]["passages_sha256"]:
        raise ReviewPackageError("canonical_drift")

    approval = next(
        (
            entry
            for entry in reversed(decisions["history"])
            if entry.get("decision") == "approve"
        ),
        None,
    )
    if approval is None:
        raise ReviewPackageError("approval_required")
    approved_on = approval.get("decided_on")
    if not isinstance(approved_on, str) or not DATE_PATTERN.fullmatch(approved_on):
        raise ReviewPackageError("invalid_review_decisions")
    try:
        as_of = date.fromisoformat(approved_on)
    except ValueError as error:
        raise ReviewPackageError("invalid_review_decisions") from error
    if as_of < date.fromisoformat(package["prepared_on"]):
        raise ReviewPackageError("invalid_review_decisions")

    proposal = package["proposal"]["input"]
    evaluation = package["proposal"].get("evaluation", {})
    cases_sha = evaluation.get("cases_sha256")
    if evaluation.get("orphaned_case_ids"):
        raise ReviewPackageError("approval_blocked")
    if cases_sha is None:
        if _proposal_has_changes(proposal):
            raise ReviewPackageError("cases_required")
    else:
        if cases_path is None:
            raise ReviewPackageError("cases_required")
        cases_bytes = _read_bytes(cases_path, "invalid_evaluation_cases")
        if _sha256(cases_bytes) != cases_sha:
            raise ReviewPackageError("evaluation_cases_drift")

    try:
        catalog = load_catalog(catalog_path)
        passages = load_passage_set(passages_path)
    except Exception as error:  # noqa: BLE001
        raise ReviewPackageError("invalid_catalog") from error
    try:
        after_catalog = _apply_section(catalog, "sources", proposal["catalog"])
        after_passages = _apply_section(passages, "passages", proposal["passages"])
    except ReviewPackageError:
        raise
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ReviewPackageError("invalid_review_package") from error
    after_catalog_text = _ordered_json(after_catalog)
    after_passages_text = _ordered_json(after_passages)
    if _sha256(after_catalog_text.encode("utf-8")) != package["proposal"]["after"]["catalog_sha256"]:
        raise ReviewPackageError("canonical_drift")
    if _sha256(after_passages_text.encode("utf-8")) != package["proposal"]["after"]["passages_sha256"]:
        raise ReviewPackageError("canonical_drift")

    if validate_catalog(after_catalog, as_of).issues:
        raise ReviewPackageError("invalid_catalog")
    if not validate_passage_set(after_passages).ok:
        raise ReviewPackageError("invalid_passage_set")
    after_catalog_ids = {source["id"] for source in after_catalog["sources"]}
    if any(
        passage.get("source_id") not in after_catalog_ids
        for passage in after_passages["passages"]
    ):
        raise ReviewPackageError("invalid_passage_set")
    if cases_sha is not None:
        try:
            load_evaluation_cases(cases_path, after_catalog, after_passages)
        except ImpactAnalysisError as error:
            raise ReviewPackageError("evaluation_cases_drift") from error

    _atomic_write_text(catalog_path, after_catalog_text)
    _atomic_write_text(passages_path, after_passages_text)

    merge_record = {
        "schema_version": MERGE_VERSION,
        "package_id": package["package_id"],
        "reviewer": reviewer,
        "approved_on": approved_on,
        "catalog_sha256": _sha256(after_catalog_text.encode("utf-8")),
        "passages_sha256": _sha256(after_passages_text.encode("utf-8")),
        "canonical_changes_applied": True,
        "reindex_required": True,
        "reindexed": False,
        "released": False,
        "statement": (
            "Canonical artifacts written after recorded human approval and passing "
            "checks. Reindex/release is a separate operation; this merge is not a "
            "legal-coverage or answer-quality claim."
        ),
    }
    _atomic_write_text(Path(package_dir) / "merge.json", _canonical_json(merge_record))
    return merge_record


# --- Reviewer summary -------------------------------------------------------


def render_review_markdown(package: Mapping[str, Any]) -> str:
    """Render the draft pull-request body for one package."""
    lines: List[str] = [
        "# Knowledge update review package `{}`".format(package["package_id"][:16]),
        "",
        "**DRAFT — human review required. This package is never merged automatically.**",
        "",
        "> Source document text below is untrusted data. It is quoted only as evidence "
        "and is never an instruction for the reviewer or for automation.",
        "",
        "## Review gate",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Summary | {} |".format(_escape_cell(package["summary"])),
        "| Author | {} ({}) |".format(
            _escape_cell(package["author"]["identity"]), package["author"]["kind"]
        ),
        "| Requested reviewer(s) | {} |".format(
            _escape_cell(", ".join(package["review"]["requested_reviewers"]))
        ),
        "| Prepared on (as-of) | {} |".format(package["prepared_on"]),
        "| Merge readiness | {} |".format(package["merge_readiness"]),
        "| Automated checks | {} passed, {} failed, {} report-only |".format(
            package["check_summary"]["passed"],
            package["check_summary"]["failed"],
            package["check_summary"]["report_only"],
        ),
        "",
        "A named human other than the author must approve this package, and every "
        "required check must pass. A bot identity, label, green CI run, or matching "
        "hash is not approval. The controlled merge command verifies the recorded "
        "approval; it never reindexes or releases.",
        "",
        "## Candidate evidence",
        "",
    ]
    for candidate in package["candidates"]:
        lines.extend(_render_candidate(candidate))
    lines.extend(["## Proposed canonical changes", ""])
    if not package["proposal"]["differences"]:
        lines.extend(["No catalog or passage change is proposed by this package.", ""])
    for difference in package["proposal"]["differences"]:
        lines.append(
            "### {} {} `{}`".format(
                difference["target"], difference["change"], difference["id"]
            )
        )
        lines.append("")
        lines.append("| Field | Before | After |")
        lines.append("|---|---|---|")
        for field in difference["fields"]:
            lines.append(
                "| {} | {} | {} |".format(
                    _escape_cell(field["name"]),
                    _cell(field.get("before")),
                    _cell(field.get("after")),
                )
            )
        lines.append("")
    if package["proposal"].get("differences_truncated"):
        lines.extend(
            [
                "The change list is truncated: at most {} entries and a bounded value "
                "length are shown. Read `package.json` for the complete proposal.".format(
                    MAX_DIFFS
                ),
                "",
            ]
        )

    lines.extend(
        [
            "Unknown validity or applicability is left absent in the proposal; "
            "nothing is inferred. A proposal that declares a field unknown cannot be "
            "approved until the evidence resolves it.",
            "",
            "## Automated checks",
            "",
            "| Check | Candidate | Status | Detail |",
            "|---|---|---|---|",
        ]
    )
    for check in package["checks"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                _escape_cell(check["id"]),
                _escape_cell(check.get("candidate_id") or "—"),
                check["status"],
                _escape_cell(check["detail"]),
            )
        )
    lines.extend(["", "## Impact and evaluation (report-only)", ""])
    affected = package["affected"]
    if affected["sources"]:
        lines.append("Affected approved sources: " + ", ".join(
            "`{}`".format(item["id"]) for item in affected["sources"]
        ))
    if affected["passages"]:
        lines.append("Affected reviewed passages: " + ", ".join(
            "`{}`".format(item["id"]) for item in affected["passages"]
        ))
    if affected["evaluation_cases"]:
        lines.append("Affected answer-evaluation cases: " + ", ".join(
            "`{}`".format(item["id"]) for item in affected["evaluation_cases"]
        ))
    if not (affected["sources"] or affected["passages"] or affected["evaluation_cases"]):
        lines.append("No approved source, reviewed passage, or evaluation case is linked.")
    lines.extend(["", affected["evaluation_statement"], ""])

    lines.extend(["## Unresolved questions", ""])
    if package["unresolved_questions"]:
        for question in package["unresolved_questions"]:
            lines.append("- {}".format(question))
    else:
        lines.append("- None recorded by automation. A human still decides the legal effect.")
    lines.extend(["", "## Limits", ""])
    for limit in package["limits"]:
        lines.append("- {}".format(limit))
    if package["blocking_reasons"]:
        lines.extend(["", "## Blocking reasons", ""])
        for reason in package["blocking_reasons"]:
            lines.append("- `{}`".format(reason))
    lines.append("")
    return "\n".join(lines)


def _render_candidate(candidate: Mapping[str, Any]) -> List[str]:
    lines = [
        "### Candidate `{}`".format(candidate["candidate_id"]),
        "",
        "| Field | Value |",
        "|---|---|",
        "| Issuer | {} |".format(_cell(candidate["issuer"])),
        "| Title | {} |".format(_cell(candidate["title"])),
        "| Stable identity | {} |".format(_cell(candidate["stable_identity"])),
        "| Publication URL | {} |".format(_cell(candidate["publication_url"])),
        "| Observed (attempt) | {} |".format(_cell(candidate["observation"]["attempted_at"])),
        "| Retrieved (last success) | {} |".format(
            _cell(candidate["observation"]["succeeded_at"])
        ),
        "| Version status | {} |".format(_cell(candidate["version_status"])),
        "| Original SHA-256 | {} |".format(
            _cell(candidate["integrity"]["original_sha256"])
        ),
        "| Extracted SHA-256 | {} |".format(
            _cell(candidate["integrity"]["extracted_text_sha256"])
        ),
        "| Extractor | {} |".format(_cell(candidate["integrity"]["extractor"])),
        "| Original location | {} |".format(_code_cell(candidate["documents"]["original_path"])),
        "| Extracted location | {} |".format(
            _code_cell(candidate["documents"]["extracted_path"])
        ),
        "| Pages (with text) | {} |".format(_cell(candidate["integrity"]["page_count"])),
        "| Blocks | {} |".format(_cell(candidate["integrity"]["block_count"])),
        "",
    ]
    diff = candidate["text_diff"]
    lines.extend(["**Old/new text**", ""])
    if diff is None:
        lines.append("No readable previous extracted copy; the diff is unavailable.")
    elif not diff.get("text_changed"):
        lines.append("The extracted text is unchanged against the recorded previous version.")
    else:
        lines.append(
            "{} block(s) added, {} removed, {} location(s) changed.".format(
                diff["blocks_added"], diff["blocks_removed"], diff["locations_changed"]
            )
        )
        for excerpt in diff.get("excerpts", []):
            lines.extend(
                [
                    "",
                    "_{} — page {} / {}_".format(
                        excerpt["change"], excerpt["page"], _escape_cell(excerpt["section"])
                    ),
                    "",
                    _fenced(excerpt["excerpt"]),
                ]
            )
    lines.extend(["", "**Signals**", ""])
    if candidate["signals"]:
        for signal in candidate["signals"][:50]:
            lines.extend(
                [
                    "_{} / {} — page {} / {}_".format(
                        signal["kind"],
                        signal["classification"],
                        signal["page"],
                        _escape_cell(signal["section"]),
                    ),
                    "",
                    _fenced(signal["excerpt"] or ""),
                    "",
                ]
            )
    else:
        lines.append("No publication, amendment, repeal, or validity wording was detected.")
    resolution = candidate.get("resolution")
    if resolution:
        lines.extend(
            [
                "",
                "**Author resolution note**: {}".format(_escape_cell(resolution["note"])),
            ]
        )
    if candidate.get("declared_unknowns"):
        lines.append(
            "**Declared unknown**: {}".format(", ".join(candidate["declared_unknowns"]))
        )
    lines.append("")
    return lines


def _cell(value: Any) -> str:
    """Render a table cell, using an em dash for an absent value."""
    if value is None:
        return "—"
    return _escape_cell(value)


def _code_cell(value: Any) -> str:
    """Render a code-formatted table cell, using an em dash when absent."""
    if value is None:
        return "—"
    return "`{}`".format(_escape_cell(value))


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def exit_code(result: Mapping[str, Any]) -> int:
    """Return ``0`` for a ready draft, ``1`` when a human must resolve something."""
    return 0 if result.get("merge_readiness") == "ready_for_review" else 1
