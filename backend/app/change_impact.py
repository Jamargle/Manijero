"""Analyze quarantined official-document changes against approved knowledge.

This module consumes the quarantine written by ``app/document_ingestion.py`` and
turns it into one deterministic, reviewable impact report. It compares the
versions recorded for each candidate, detects explicit publication, amendment,
repeal and validity wording, separates machine-evident wording from wording that
needs legal interpretation, and links the potential impact to approved catalog
sources, reviewed passages and reviewed answer-evaluation cases.

Boundaries:

- it is read-only. It never writes ``knowledge/``, never changes a catalog, a
  passage, an evaluation case, an index, or an answer, and never makes a
  candidate answerable;
- it never retires, replaces or re-approves a source. Every candidate that could
  touch reviewed knowledge stays review-required until an identified human acts
  on the reviewed-update workflow; an ambiguous signal never authorizes
  retirement, and any ambiguous publication, amendment, repeal or validity signal
  (including negated wording) makes its candidate review-required even when it
  links no approved source, or only a reviewed passage or case;
- a per-candidate failure is recorded with a fixed category and never aborts the
  rest of the run; an invalid catalog, passage set, case set, ingestion state, or
  unsafe report path fails closed before any report is written;
- the report contains only bounded excerpts of official public document text and
  no personal or land data, and it carries no wall-clock timestamp, so identical
  pinned inputs and the same ``as_of`` date produce byte-identical output.

Standard-library only.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.retrieval import load_passage_set, validate_passage_set
from app.source_catalog import load_catalog, validate_catalog

REPORT_VERSION = "legal-change-impact-report-v1"
ANALYZER = "manijero-change-impact-analyzer-v1"
INGESTION_STATE_VERSION = "official-ingestion-state-v1"
EXTRACTED_DOCUMENT_VERSION = "official-ingestion-document-v1"
CATALOG_VERSION = "source-catalog-v1"
PASSAGE_SET_VERSION = "passage-set-v1"
EVALUATION_CASES_VERSION = "pac-answer-eval-v2"

MAX_CANDIDATES = 1000
MAX_BLOCKS = 5000
MAX_TEXT_CHARS = 2000000
MAX_SIGNALS_PER_CANDIDATE = 50
MAX_EXCERPTS = 5
MAX_EXCERPT_CHARS = 280

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

CANDIDATE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

# Signal kinds in report order. Publication is informational; the other three can
# name an instrument whose approved records may need review.
SIGNAL_KINDS = ("repeal", "amendment", "validity", "publication")
IMPACT_SIGNAL_KINDS = ("repeal", "amendment", "validity")

# Fixed, value-free failure categories. They are stable for operators and tests.
FAILURES = frozenset(
    {
        "no_extracted_document",
        "missing_extracted_document",
        "extracted_text_mismatch",
        "malformed_extracted_document",
        "size_limit_exceeded",
        "internal_error",
    }
)

GLOBAL_FAILURES = frozenset(
    {
        "invalid_as_of",
        "invalid_catalog",
        "invalid_passage_set",
        "invalid_evaluation_cases",
        "invalid_ingestion_state",
        "candidate_count_exceeded",
        "unsafe_workspace",
    }
)

# Durable limits copied into every report so the artifact states its own scope.
REPORT_LIMITS = (
    "Detection is lexical over extracted text. It finds explicit Spanish wording, "
    "not the legal effect of a change; a static deadline phrase without change "
    "wording (for example 'el plazo ... hasta') is not reported as a validity "
    "signal.",
    "Triggers are broad word stems ('modific...', 'derog...', 'prorrog...', "
    "'entrada en vigor'). Static document wording such as a 'Disposicion "
    "derogatoria' heading or 'Modificaciones presupuestarias' therefore produces "
    "an ambiguous signal, so review-required may be near-universal on real text.",
    "Negation is recognised only for the listed Spanish phrasings (for example "
    "'no se modifica', 'sin que se modifique', 'no deja sin efecto', 'no pierde "
    "vigencia', 'en ningun caso', 'tampoco', 'nunca'). Other negative wording is "
    "read as positive or missed.",
    "Ambiguous wording is reported for author review and never authorizes "
    "retirement, replacement, or an answer change. Every ambiguous publication, "
    "amendment, repeal, or validity signal makes its candidate review-required, "
    "even when it links no approved source or is negated.",
    "Only catalog sources, reviewed passages, and reviewed evaluation cases are "
    "linked; no corpus scope, eligibility, or answer-quality claim follows.",
    "Only a version recorded by candidate ingestion can be compared. Text "
    "replaced at a stable URL without a new ingestion version is not detected.",
    "Excerpts are bounded official-document text for review only; they are never "
    "interpolated into an answer.",
    "A failed or rejected ingestion is reported as 'no_extracted_document' and "
    "does not by itself raise the review gate, so a run whose only unresolved "
    "candidates failed ingestion exits 0; exit status alone does not report it.",
)

_NEGATION = re.compile(
    r"\bno\s+(?:se\s+)?(?:modific|modifiq|derog|suprim|anul|revoc|altera|afect|public)"
    r"|\bsin\s+que\s+se\s+(?:modific|modifiq|derog|suprim|alter)"
    r"|\bno\s+(?:supone|implica|conlleva)\s+(?:una\s+)?(?:modific|derog)"
    r"|\bno\s+(?:queda|quedan)\s+(?:derogad|modificad|sin\s+efecto)"
    r"|\bno\s+(?:se\s+)?deja(?:n)?\s+sin\s+efecto"
    r"|\bno\s+(?:se\s+)?pierde(?:n)?\s+(?:su\s+)?vigencia"
    r"|\ben\s+ningun\s+caso\b|\btampoco\b|\bnunca\b"
)

_SIGNAL_PATTERNS = {
    "repeal": re.compile(
        r"\bderog\w*|\brevoc\w*|\bdeja(?:n)?\s+sin\s+efecto"
        r"|\bqueda(?:n)?\s+sin\s+efecto|\bpierde(?:n)?\s+(?:su\s+)?vigencia"
    ),
    "amendment": re.compile(
        r"\bmodifi(?:c|q)\w*|\bnueva\s+redaccion"
        r"|\bse\s+(?:suprim\w*|a[nñ]ad\w*|adicion\w*)"
        r"|\bqueda(?:n)?\s+(?:modificad|redactad|suprimid)\w*"
    ),
    "validity": re.compile(
        r"\bentra(?:ra|ran)?\s+en\s+vigor|\bentrada\s+en\s+vigor"
        r"|\bprorrog\w*"
        r"|\bse\s+(?:extiende|amplia|prorroga|reduce|acorta)\b[^.;:]{0,80}\bhasta\b"
        r"|\bmantiene\s+su\s+vigencia"
    ),
    "publication": re.compile(
        r"\bboletin\s+oficial\s+del\s+estado|\bboletin\s+oficial\s+de\s+la\s+junta"
        r"|\bse\s+publica\b|\bpublicad[oa]s?\s+en\s+el\b"
    ),
}

_BULLETIN = re.compile(
    r"\bboletin\s+oficial\s+del\s+estado|\bboletin\s+oficial\s+de\s+la\s+junta"
)

_BULLETIN_REFERENCE = re.compile(r"\bnum\.?\b|\bnumero\b")

_MONTHS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre"
    "|octubre|noviembre|diciembre"
)

_EXPLICIT_DATE = re.compile(
    r"\b\d{1,2}\s+de\s+(?:" + _MONTHS + r")\s+de\s+\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b"
)

_INSTRUMENT = re.compile(
    r"\b(real\s+decreto\s+legislativo|real\s+decreto(?:[- ]ley)?"
    r"|decreto\s+legislativo|decreto[- ]ley|decreto"
    r"|ley\s+organica|ley|orden|resolucion|reglamento(?:\s+\(ue\))?)"
    r"\s+(?:[a-z]+/)?(\d{1,4})\s*/\s*(\d{4})\b"
)

_INSTRUMENT_TYPES = {
    "real decreto legislativo": "real decreto legislativo",
    "real decreto-ley": "decreto-ley",
    "real decreto ley": "decreto-ley",
    "real decreto": "real decreto",
    "decreto legislativo": "decreto legislativo",
    "decreto-ley": "decreto-ley",
    "decreto ley": "decreto-ley",
    "decreto": "decreto",
    "ley organica": "ley organica",
    "ley": "ley",
    "orden": "orden",
    "resolucion": "resolucion",
    "reglamento": "reglamento",
    "reglamento (ue)": "reglamento (ue)",
}

_SENTENCE_BREAK = re.compile(r"(?<=[.;:])\s+")


class ImpactAnalysisError(ValueError):
    """An invalid input or unsafe workspace that must fail closed."""

    def __init__(self, failure: str) -> None:
        if failure not in GLOBAL_FAILURES:
            failure = "internal_error"
        self.failure = failure
        super().__init__(failure)


class _CandidateError(Exception):
    """A per-candidate analysis failure that never aborts the run."""

    def __init__(self, failure: str) -> None:
        if failure not in FAILURES:
            failure = "internal_error"
        self.failure = failure
        super().__init__(failure)


@dataclass(frozen=True)
class CatalogIndex:
    """Approved catalog sources indexed for deterministic impact linking."""

    sources: Tuple[Dict[str, Any], ...]
    ids: Tuple[str, ...]
    by_url: Dict[str, Tuple[str, ...]]
    by_content: Dict[str, Tuple[str, ...]]
    by_instrument: Dict[str, Tuple[str, ...]]


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


def fold(text: str) -> str:
    """Lowercase, strip diacritics, and collapse whitespace for matching."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    without_diacritics = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(without_diacritics.split())


def _instrument_matches(text: str) -> List[Tuple[int, str]]:
    matches: List[Tuple[int, str]] = []
    for match in _INSTRUMENT.finditer(fold(text)):
        raw_type = " ".join(match.group(1).split())
        kind = _INSTRUMENT_TYPES.get(raw_type)
        if kind is None:
            continue
        matches.append((match.start(), "{} {}/{}".format(kind, int(match.group(2)), match.group(3))))
    return matches


def instrument_keys(text: str) -> Tuple[str, ...]:
    """Return canonical ``<type> <number>/<year>`` keys found in ``text``."""
    return tuple(sorted({key for _, key in _instrument_matches(text)}))


def own_instrument_key(text: str) -> Optional[str]:
    """Return the instrument ``text`` starts with, or ``None``.

    A publication title identifies the instrument the publication *is* only when
    it opens with that numbered instrument, for example "Real Decreto
    2200/2099, ...". A title that starts with an unnumbered act ("Resolución de
    9 de septiembre de 2099, ... por la que se modifica la Ley 5/2098") names
    targets only, so it has no own identity and every named instrument stays a
    possible target.
    """
    match = _INSTRUMENT.match(fold(text))
    if match is None:
        return None
    kind = _INSTRUMENT_TYPES.get(" ".join(match.group(1).split()))
    if kind is None:
        return None
    return "{} {}/{}".format(kind, int(match.group(2)), match.group(3))


def _excerpt(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= MAX_EXCERPT_CHARS:
        return compact
    return compact[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"


def _sentences(text: str) -> List[str]:
    return [sentence for sentence in _SENTENCE_BREAK.split(text) if sentence.strip()]


def _url_key(url: Any) -> Optional[str]:
    if not isinstance(url, str):
        return None
    try:
        from urllib.parse import urlsplit

        parsed = urlsplit(url.strip())
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower()).geturl().rstrip("/")


def _identity_matches_url(identity: str, url: Any) -> bool:
    """Return True when ``identity`` appears as the URL's id or a path segment."""
    if not isinstance(url, str) or not identity:
        return False
    try:
        from urllib.parse import parse_qs, urlsplit

        parsed = urlsplit(url)
        values = parse_qs(parsed.query).get("id", [])
    except ValueError:
        return False
    if identity in values:
        return True
    return identity in [segment for segment in parsed.path.split("/") if segment]


def _index_catalog(document: Any) -> CatalogIndex:
    sources = tuple(document["sources"])
    by_url: Dict[str, List[str]] = {}
    by_content: Dict[str, List[str]] = {}
    by_instrument: Dict[str, List[str]] = {}
    for source in sources:
        source_id = source["id"]
        for key in (_url_key(source.get("original_url")), _url_key(source.get("consolidated_url"))):
            if key is not None:
                by_url.setdefault(key, []).append(source_id)
        content = source.get("content_sha256")
        if isinstance(content, str):
            by_content.setdefault(content, []).append(source_id)
        for instrument in instrument_keys(str(source.get("title", ""))):
            by_instrument.setdefault(instrument, []).append(source_id)
    return CatalogIndex(
        sources=sources,
        ids=tuple(sorted(source["id"] for source in sources)),
        by_url={key: tuple(sorted(value)) for key, value in by_url.items()},
        by_content={key: tuple(sorted(value)) for key, value in by_content.items()},
        by_instrument={key: tuple(sorted(value)) for key, value in by_instrument.items()},
    )


def load_ingestion_state(path: Path) -> Dict[str, Any]:
    """Load and structurally validate ``official-ingestion-state-v1``."""
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImpactAnalysisError("invalid_ingestion_state") from error
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != INGESTION_STATE_VERSION
        or not isinstance(state.get("candidates"), dict)
    ):
        raise ImpactAnalysisError("invalid_ingestion_state")
    required = (
        "candidate_id",
        "issuer",
        "stable_identity",
        "publication_url",
        "title",
        "review_status",
        "status",
    )
    for candidate_id, record in state["candidates"].items():
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            raise ImpactAnalysisError("invalid_ingestion_state")
        if not isinstance(record, dict) or record.get("candidate_id") != candidate_id:
            raise ImpactAnalysisError("invalid_ingestion_state")
        if not all(isinstance(record.get(key), str) for key in required):
            raise ImpactAnalysisError("invalid_ingestion_state")
        if record.get("review_status") != "pending":
            raise ImpactAnalysisError("invalid_ingestion_state")
        if record.get("status") not in ("extracted", "failed", "rejected"):
            raise ImpactAnalysisError("invalid_ingestion_state")
        if record.get("status") == "extracted":
            for key in ("original_sha256", "extracted_text_sha256"):
                if not isinstance(record.get(key), str) or not SHA256_PATTERN.fullmatch(record[key]):
                    raise ImpactAnalysisError("invalid_ingestion_state")
            for key in ("extracted_path", "media_type", "extractor"):
                if not isinstance(record.get(key), str) or not record[key].strip():
                    raise ImpactAnalysisError("invalid_ingestion_state")
            previous = record.get("previous_original_sha256")
            if previous is not None and (
                not isinstance(previous, str) or not SHA256_PATTERN.fullmatch(previous)
            ):
                raise ImpactAnalysisError("invalid_ingestion_state")
    if len(state["candidates"]) > MAX_CANDIDATES:
        raise ImpactAnalysisError("candidate_count_exceeded")
    return state


def load_evaluation_cases(path: Path, catalog: Any, passages: Any) -> List[Dict[str, Any]]:
    """Read the identity and reference fields this analysis consumes.

    ``app/answer_eval.py`` stays the authoritative validator for the full
    reviewed case contract. This narrow read fails closed on the structure and
    references used for linking, so an unknown source or passage can never
    silently skip an affected case.
    """
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImpactAnalysisError("invalid_evaluation_cases") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != EVALUATION_CASES_VERSION
        or not isinstance(document.get("cases"), list)
    ):
        raise ImpactAnalysisError("invalid_evaluation_cases")
    source_ids = {source["id"] for source in catalog["sources"]}
    passage_ids = {passage["id"] for passage in passages["passages"]}
    cases: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for case in document["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"].strip():
            raise ImpactAnalysisError("invalid_evaluation_cases")
        if case["id"] in seen:
            raise ImpactAnalysisError("invalid_evaluation_cases")
        seen.add(case["id"])
        for key, known in (("expected_source_ids", source_ids), ("expected_passage_ids", passage_ids)):
            values = case.get(key, [])
            if (
                not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                or not set(values) <= known
            ):
                raise ImpactAnalysisError("invalid_evaluation_cases")
        cases.append(
            {
                "id": case["id"],
                "expected_source_ids": tuple(case.get("expected_source_ids", [])),
                "expected_passage_ids": tuple(case.get("expected_passage_ids", [])),
            }
        )
    return sorted(cases, key=lambda item: item["id"])


def _relative_quarantine_path(value: Any, candidate_id: str) -> Optional[Path]:
    if not isinstance(value, str):
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != (candidate_id,):
        return None
    return relative


def _load_blocks(path: Path, candidate_id: str, expected_digest: Optional[str]) -> List[Dict[str, Any]]:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise _CandidateError("missing_extracted_document") from error
    if expected_digest is not None and _sha256(payload) != expected_digest:
        raise _CandidateError("extracted_text_mismatch")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _CandidateError("malformed_extracted_document") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != EXTRACTED_DOCUMENT_VERSION
        or document.get("candidate_id") != candidate_id
        or not isinstance(document.get("blocks"), list)
    ):
        raise _CandidateError("malformed_extracted_document")
    blocks: List[Dict[str, Any]] = []
    characters = 0
    for block in document["blocks"]:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            raise _CandidateError("malformed_extracted_document")
        text = " ".join(block["text"].split())
        if not text:
            raise _CandidateError("malformed_extracted_document")
        page = block.get("page")
        if page is not None and not isinstance(page, int):
            raise _CandidateError("malformed_extracted_document")
        section = block.get("section")
        if not isinstance(section, str) or not section.strip():
            raise _CandidateError("malformed_extracted_document")
        characters += len(text)
        if len(blocks) >= MAX_BLOCKS or characters > MAX_TEXT_CHARS:
            raise _CandidateError("size_limit_exceeded")
        blocks.append({"page": page, "section": section, "text": text})
    if not blocks:
        raise _CandidateError("malformed_extracted_document")
    return blocks


def block_text(block: Dict[str, Any]) -> str:
    """Return the normalized text of one extracted block."""
    return " ".join(str(block.get("text", "")).split())


def _previous_extracted_path(record: Dict[str, Any]) -> Optional[Path]:
    """Return the quarantine path of the previous version's extracted text.

    The ingestion state keeps only the current ``extracted_path`` and the
    previous original digest. The previous extracted document is the sibling
    ``extracted-<previous sha256>.json`` file, when the previous run wrote one
    with a different original digest.
    """
    previous = record.get("previous_original_sha256")
    if not isinstance(previous, str):
        return None
    if previous == record.get("original_sha256"):
        return None
    relative = _relative_quarantine_path(record.get("extracted_path"), record["candidate_id"])
    if relative is None:
        return None
    return relative.parent / "extracted-{}.json".format(previous)


def _detect_signals(blocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, Optional[int], str, str]] = set()
    for block in blocks:
        for sentence in _sentences(block_text(block)):
            folded = fold(sentence)
            keys = instrument_keys(sentence)
            for kind in SIGNAL_KINDS:
                if _SIGNAL_PATTERNS[kind].search(folded) is None:
                    continue
                classification, reason = _classify(kind, folded, sentence, keys)
                excerpt = _excerpt(sentence)
                identity = (kind, classification, block["page"], block["section"], excerpt)
                if identity in seen:
                    continue
                seen.add(identity)
                signals.append(
                    {
                        "kind": kind,
                        "classification": classification,
                        "reason": reason,
                        "page": block["page"],
                        "section": block["section"],
                        "excerpt": excerpt,
                        "instrument_keys": list(keys),
                    }
                )
    return signals


def _classify(
    kind: str, folded: str, sentence: str, keys: Sequence[str]
) -> Tuple[str, str]:
    """Return ``(classification, reason)`` for one lexical signal."""
    uncertain = "\ufffd" in sentence
    # Sentence-scoped negation applies to every signal kind, publication included,
    # because "no se publica" states the opposite of a publication.
    if _NEGATION.search(folded):
        return "ambiguous", "negated_signal"
    if kind in ("amendment", "repeal"):
        if uncertain:
            return "ambiguous", "extraction_uncertainty"
        if not keys:
            return "ambiguous", "no_named_instrument"
        return "machine_evident", "explicit_action_on_named_instrument"
    if kind == "validity":
        if uncertain:
            return "ambiguous", "extraction_uncertainty"
        if _EXPLICIT_DATE.search(folded) is None:
            return "ambiguous", "no_explicit_date"
        return "machine_evident", "explicit_date"
    if uncertain:
        return "ambiguous", "extraction_uncertainty"
    if _BULLETIN.search(folded) and (
        _BULLETIN_REFERENCE.search(folded) or _EXPLICIT_DATE.search(folded)
    ):
        return "machine_evident", "explicit_publication_reference"
    return "ambiguous", "incomplete_publication_reference"


def _text_diff(
    current: Sequence[Dict[str, Any]], previous: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    def group(blocks: Iterable[Dict[str, Any]]) -> Dict[Tuple[Optional[int], str], List[str]]:
        grouped: Dict[Tuple[Optional[int], str], List[str]] = {}
        for block in blocks:
            grouped.setdefault((block["page"], block["section"]), []).append(block_text(block))
        return {key: sorted(value) for key, value in grouped.items()}

    current_groups = group(current)
    previous_groups = group(previous)
    additions: List[Dict[str, Any]] = []
    removals: List[Dict[str, Any]] = []
    changed_locations = 0
    for key in sorted(set(current_groups) | set(previous_groups), key=lambda item: (item[0] or 0, item[1])):
        now, before = current_groups.get(key, []), previous_groups.get(key, [])
        if now == before:
            continue
        changed_locations += 1
        for text in now:
            if text not in before:
                additions.append({"change": "added", "page": key[0], "section": key[1], "excerpt": _excerpt(text)})
        for text in before:
            if text not in now:
                removals.append({"change": "removed", "page": key[0], "section": key[1], "excerpt": _excerpt(text)})
    excerpts = (additions + removals)[:MAX_EXCERPTS]
    return {
        "blocks_added": len(additions),
        "blocks_removed": len(removals),
        "locations_changed": changed_locations,
        "text_changed": bool(additions or removals),
        "excerpts": excerpts,
    }


def _analysis_failed(record: Dict[str, Any], failure: str) -> Dict[str, Any]:
    return {
        "candidate_id": record["candidate_id"],
        "issuer": record["issuer"],
        "stable_identity": record["stable_identity"],
        "title": record["title"],
        "publication_url": record["publication_url"],
        "review_status": "pending",
        "ingestion_status": record["status"],
        "version_status": "analysis_failed",
        "version": {
            "current_original_sha256": record.get("original_sha256"),
            "previous_original_sha256": record.get("previous_original_sha256"),
            "baseline_text_available": False,
            "text_diff": None,
        },
        "signals": [],
        "potentially_affected": {"sources": [], "passages": [], "evaluation_cases": []},
        "review": {
            "required": True,
            "reasons": ["analysis_failed"],
            "automatic_retirement_allowed": False,
        },
        "analysis_failure": failure,
    }


def _not_extracted(record: Dict[str, Any]) -> Dict[str, Any]:
    """Report a candidate that ingestion never turned into text.

    ``analysis_failure`` names why no text analysis exists, so a consumer never
    has to infer it from a null field. Retrying or fixing the ingestion is owned
    by the ingestion state (``status``/``failure``/``attempts``), not by this
    report, so this candidate does not raise the legal review gate on its own.
    """
    return {
        "candidate_id": record["candidate_id"],
        "issuer": record["issuer"],
        "stable_identity": record["stable_identity"],
        "title": record["title"],
        "publication_url": record["publication_url"],
        "review_status": "pending",
        "ingestion_status": record["status"],
        "version_status": "no_extracted_document",
        "version": {
            "current_original_sha256": record.get("original_sha256"),
            "previous_original_sha256": record.get("previous_original_sha256"),
            "baseline_text_available": False,
            "text_diff": None,
        },
        "signals": [],
        "potentially_affected": {"sources": [], "passages": [], "evaluation_cases": []},
        "review": {
            "required": False,
            "reasons": [],
            "automatic_retirement_allowed": False,
        },
        "analysis_failure": "no_extracted_document",
    }


def analyze_candidate(
    record: Dict[str, Any],
    quarantine_root: Path,
    catalog_index: CatalogIndex,
    passages: Sequence[Dict[str, Any]],
    cases: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze one quarantined candidate and return its report entry."""
    if record["status"] != "extracted":
        return _not_extracted(record)

    candidate_id = record["candidate_id"]
    relative = _relative_quarantine_path(record.get("extracted_path"), candidate_id)
    if relative is None:
        raise _CandidateError("missing_extracted_document")
    current_blocks = _load_blocks(
        Path(quarantine_root) / relative, candidate_id, record.get("extracted_text_sha256")
    )

    previous_relative = _previous_extracted_path(record)
    previous_blocks: Optional[List[Dict[str, Any]]] = None
    if previous_relative is not None:
        previous_path = Path(quarantine_root) / previous_relative
        if _inside_directory(previous_path, Path(quarantine_root) / candidate_id) and previous_path.is_file():
            try:
                previous_blocks = _load_blocks(previous_path, candidate_id, None)
            except _CandidateError:
                previous_blocks = None

    current_key = record.get("original_sha256")
    previous_key = record.get("previous_original_sha256")
    url_key = _url_key(record["publication_url"])
    by_url = set(catalog_index.by_url.get(url_key, ())) if url_key else set()
    by_identity = {
        source["id"]
        for source in catalog_index.sources
        if _identity_matches_url(record["stable_identity"], source.get("original_url"))
        or _identity_matches_url(record["stable_identity"], source.get("consolidated_url"))
    }
    identity_sources = by_url | by_identity
    content_sources = set(catalog_index.by_content.get(current_key, ())) if isinstance(current_key, str) else set()
    approved_copy = bool(content_sources)

    if approved_copy:
        version_status = "approved_copy"
    elif previous_key is not None and previous_key == current_key:
        version_status = "unchanged_since_ingestion"
    elif previous_key is not None:
        version_status = "new_version"
    else:
        version_status = "baseline_unknown"

    baseline_available = previous_blocks is not None
    text_diff = (
        _text_diff(current_blocks, previous_blocks)
        if version_status == "new_version" and previous_blocks is not None
        else None
    )

    signals = _detect_signals(current_blocks)
    if len(signals) > MAX_SIGNALS_PER_CANDIDATE:
        raise _CandidateError("size_limit_exceeded")
    previous_signal_locations: Set[Tuple[str, str]] = set()
    if previous_blocks is not None:
        previous_signal_locations = {
            (signal["kind"], signal["section"]) for signal in _detect_signals(previous_blocks)
        }
    for signal in signals:
        if previous_blocks is None:
            signal["introduced"] = None
        else:
            signal["introduced"] = (signal["kind"], signal["section"]) not in previous_signal_locations
    order = {kind: index for index, kind in enumerate(SIGNAL_KINDS)}
    signals.sort(
        key=lambda item: (
            order[item["kind"]],
            item["page"] or 0,
            item["section"],
            item["classification"],
            item["excerpt"],
        )
    )

    own_instrument = own_instrument_key(record["title"])
    impact_signals = [signal for signal in signals if signal["kind"] in IMPACT_SIGNAL_KINDS]
    # A negated sentence states that something is *not* changed, so it is reported
    # for transparency but never treated as an action on an instrument.
    actionable_signals = [
        signal for signal in impact_signals if signal["reason"] != "negated_signal"
    ]
    target_instruments: Dict[str, Set[str]] = {}
    for signal in actionable_signals:
        for key in signal["instrument_keys"]:
            if own_instrument is not None and key == own_instrument:
                continue
            target_instruments.setdefault(key, set()).add(signal["kind"])

    source_reasons: Dict[str, Set[str]] = {}
    source_instruments: Dict[str, Set[str]] = {}
    if identity_sources and not approved_copy:
        for source_id in identity_sources:
            source_reasons.setdefault(source_id, set()).add("candidate_version_differs_from_approved")
    for key in sorted(target_instruments):
        for source_id in catalog_index.by_instrument.get(key, ()):
            for kind in target_instruments[key]:
                source_reasons.setdefault(source_id, set()).add("{}_target".format(kind))
            source_instruments.setdefault(source_id, set()).add(key)
    affected_sources = sorted(source_reasons)

    passage_reasons: Dict[str, Set[str]] = {}
    for passage in passages:
        reasons: Set[str] = set()
        if passage["source_id"] in source_reasons:
            reasons.add("source_affected")
        if set(target_instruments) & set(instrument_keys(str(passage["text"]))):
            reasons.add("cites_target_instrument")
        if reasons:
            passage_reasons[passage["id"]] = reasons

    case_reasons: Dict[str, Set[str]] = {}
    for case in cases:
        reasons = set()
        if set(case["expected_source_ids"]) & set(affected_sources):
            reasons.add("expected_source")
        if set(case["expected_passage_ids"]) & set(passage_reasons):
            reasons.add("expected_passage")
        if reasons:
            case_reasons[case["id"]] = reasons

    reasons: List[str] = []
    if version_status == "new_version":
        reasons.append("new_version")
    if version_status == "baseline_unknown" and (identity_sources or affected_sources):
        reasons.append("baseline_unknown")
    if identity_sources and not approved_copy:
        reasons.append("approved_copy_differs")
    if affected_sources:
        reasons.append("affected_source")
    # A reviewed passage or evaluation case can link to a target instrument whose
    # own approved source is absent from the catalog. Without this reason such a
    # candidate would be reported as potentially affected yet not review-required.
    if (passage_reasons or case_reasons) and "affected_source" not in reasons:
        reasons.append("affected_passage")
    if version_status == "new_version" and not baseline_available:
        reasons.append("previous_text_unavailable")
    if text_diff is not None and text_diff["text_changed"] and not actionable_signals:
        reasons.append("text_changed_without_signal")
    # Fail closed: any ambiguous publication, amendment, repeal or validity
    # wording needs an author, including negated wording, even when it links no
    # approved source. Otherwise negated "no se deroga" phrasing or an unlinked
    # blanket repeal could pass as "nothing to review".
    ambiguous = [signal for signal in signals if signal["classification"] == "ambiguous"]
    if ambiguous:
        reasons.append("ambiguous_signal")
    kinds_by_instrument: Dict[str, Set[str]] = {}
    for signal in actionable_signals:
        for key in signal["instrument_keys"]:
            kinds_by_instrument.setdefault(key, set()).add(signal["kind"])
    if any({"amendment", "repeal"} <= kinds for kinds in kinds_by_instrument.values()):
        reasons.append("conflicting_signals")

    return {
        "candidate_id": candidate_id,
        "issuer": record["issuer"],
        "stable_identity": record["stable_identity"],
        "title": record["title"],
        "publication_url": record["publication_url"],
        "review_status": "pending",
        "ingestion_status": record["status"],
        "version_status": version_status,
        "version": {
            "current_original_sha256": current_key,
            "previous_original_sha256": previous_key,
            "baseline_text_available": baseline_available,
            "text_diff": text_diff,
        },
        "signals": [
            {
                "kind": signal["kind"],
                "classification": signal["classification"],
                "reason": signal["reason"],
                "page": signal["page"],
                "section": signal["section"],
                "excerpt": signal["excerpt"],
                "instrument_keys": signal["instrument_keys"],
                "introduced": signal["introduced"],
            }
            for signal in signals
        ],
        "potentially_affected": {
            "sources": [
                {
                    "id": source_id,
                    "reasons": sorted(source_reasons[source_id]),
                    "instrument_keys": sorted(source_instruments.get(source_id, ())),
                }
                for source_id in affected_sources
            ],
            "passages": [
                {"id": passage_id, "reasons": sorted(reasons_set)}
                for passage_id, reasons_set in sorted(passage_reasons.items())
            ],
            "evaluation_cases": [
                {"id": case_id, "reasons": sorted(reasons_set)}
                for case_id, reasons_set in sorted(case_reasons.items())
            ],
        },
        "review": {
            "required": bool(reasons),
            "reasons": reasons,
            "automatic_retirement_allowed": False,
        },
        "analysis_failure": None,
    }


def analyze(
    ingestion_state: Path,
    quarantine_dir: Path,
    catalog_path: Path,
    passages_path: Path,
    cases_path: Optional[Path] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Analyze every ingested candidate and return the impact report.

    The report is deterministic for fixed inputs and ``as_of``: it carries input
    digests and no wall-clock time. Global input errors raise
    ``ImpactAnalysisError`` before any candidate is analyzed; per-candidate
    failures are recorded without aborting the run.
    """
    if not isinstance(as_of, date):
        raise ImpactAnalysisError("invalid_as_of")

    catalog_bytes = _read_bytes(catalog_path, "invalid_catalog")
    try:
        catalog = load_catalog(catalog_path)
    except Exception as error:
        raise ImpactAnalysisError("invalid_catalog") from error
    if not isinstance(catalog, dict) or catalog.get("schema_version") != CATALOG_VERSION:
        raise ImpactAnalysisError("invalid_catalog")
    if validate_catalog(catalog, as_of).issues:
        raise ImpactAnalysisError("invalid_catalog")

    passages_bytes = _read_bytes(passages_path, "invalid_passage_set")
    try:
        passages = load_passage_set(passages_path)
    except Exception as error:
        raise ImpactAnalysisError("invalid_passage_set") from error
    report = validate_passage_set(passages)
    if not report.ok or not isinstance(passages, dict) or passages.get("schema_version") != PASSAGE_SET_VERSION:
        raise ImpactAnalysisError("invalid_passage_set")
    catalog_ids = {source["id"] for source in catalog["sources"]}
    if any(passage.get("source_id") not in catalog_ids for passage in passages["passages"]):
        raise ImpactAnalysisError("invalid_passage_set")

    cases: List[Dict[str, Any]] = []
    cases_bytes: Optional[bytes] = None
    if cases_path is not None:
        cases_bytes = _read_bytes(cases_path, "invalid_evaluation_cases")
        cases = load_evaluation_cases(cases_path, catalog, passages)

    state_bytes = _read_bytes(ingestion_state, "invalid_ingestion_state")
    state = load_ingestion_state(ingestion_state)
    catalog_index = _index_catalog(catalog)

    candidates: List[Dict[str, Any]] = []
    for candidate_id in sorted(state["candidates"]):
        record = state["candidates"][candidate_id]
        try:
            candidates.append(
                analyze_candidate(record, Path(quarantine_dir), catalog_index, passages["passages"], cases)
            )
        except _CandidateError as error:
            candidates.append(_analysis_failed(record, error.failure))
        except Exception:
            candidates.append(_analysis_failed(record, "internal_error"))

    summary = {
        "candidates": len(candidates),
        "no_extracted_document": sum(
            1 for item in candidates if item["version_status"] == "no_extracted_document"
        ),
        "approved_copy": sum(1 for item in candidates if item["version_status"] == "approved_copy"),
        "unchanged_since_ingestion": sum(
            1 for item in candidates if item["version_status"] == "unchanged_since_ingestion"
        ),
        "new_version": sum(1 for item in candidates if item["version_status"] == "new_version"),
        "baseline_unknown": sum(1 for item in candidates if item["version_status"] == "baseline_unknown"),
        "analysis_failed": sum(1 for item in candidates if item["version_status"] == "analysis_failed"),
        "review_required": sum(1 for item in candidates if item["review"]["required"]),
        "machine_evident_signals": sum(
            1
            for item in candidates
            for signal in item["signals"]
            if signal["classification"] == "machine_evident"
        ),
        "ambiguous_signals": sum(
            1 for item in candidates for signal in item["signals"] if signal["classification"] == "ambiguous"
        ),
        "affected_sources": len(
            {source["id"] for item in candidates for source in item["potentially_affected"]["sources"]}
        ),
        "affected_passages": len(
            {passage["id"] for item in candidates for passage in item["potentially_affected"]["passages"]}
        ),
        "affected_evaluation_cases": len(
            {case["id"] for item in candidates for case in item["potentially_affected"]["evaluation_cases"]}
        ),
    }

    return {
        "schema_version": REPORT_VERSION,
        "analyzer": ANALYZER,
        "as_of": as_of.isoformat(),
        "inputs": {
            "ingestion_state_sha256": _sha256(state_bytes),
            "catalog_sha256": _sha256(catalog_bytes),
            "passages_sha256": _sha256(passages_bytes),
            "evaluation_cases_sha256": _sha256(cases_bytes) if cases_bytes is not None else None,
        },
        "candidates": candidates,
        "summary": summary,
        "review_gate": {
            "canonical_changes_applied": False,
            "automatic_retirement": False,
            "requires_human_approval": True,
        },
        "limits": list(REPORT_LIMITS),
    }


def _read_bytes(path: Path, failure: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise ImpactAnalysisError(failure) from error


def write_report(report: Dict[str, Any], path: Path) -> None:
    """Write the canonical report outside ``knowledge/``, atomically."""
    target = Path(path)
    if _inside_directory(target, KNOWLEDGE_ROOT):
        raise ImpactAnalysisError("unsafe_workspace")
    text = _canonical_json(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(target, text)


def exit_code(report: Dict[str, Any]) -> int:
    """Return ``1`` when a report needs attention, ``0`` when nothing does."""
    summary = report["summary"]
    return 1 if summary["review_required"] or summary["analysis_failed"] else 0
