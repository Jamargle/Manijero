"""Content-free security scan for official documents and the reviewed corpus.

Document text is **untrusted data**. This module keeps two kinds of text out of
the reviewed corpus and out of a draft:

- ``nominal_listing`` — an aid award/admittee/excluded-person list: a listing
  phrase in a candidate/document title or a heading, or at least two
  personal-identifier tokens (DNI/NIE/affiliation-number shapes) counted
  across the whole extracted document (all blocks and titles); the canonical
  gate is stricter and treats any single identifier shape as prohibited;
- ``prompt_injection`` — wording directed at a model or assistant (ignore or
  forget instructions, reveal/override a prompt, role reassignment, fake
  system/role tags).

Boundaries:

- standard library only, no network, no model, no legal judgment;
- detection is a conservative, Spanish-first heuristic (English only for
  injection). It can miss a reworded listing or a novel instruction, and a
  false positive excludes a document from automation; the retained provenance
  is what lets a person open the official procedure;
- results carry fixed flag tokens and bounded findings made of
  ``{flag, page, block_index}`` only. No document text, heading, or name is
  ever copied into a finding, a state file, a report, or a log.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

SCAN_VERSION = "corpus-security-scan-v1"
_SCAN_VERSION_PATTERN = re.compile(r"^corpus-security-scan-v[0-9]+$")

NOMINAL_LISTING = "nominal_listing"
PROMPT_INJECTION = "prompt_injection"
FLAGS = (NOMINAL_LISTING, PROMPT_INJECTION)
# Privacy first: when both are present the record's fixed failure is the listing.
FAILURE_PRECEDENCE = (NOMINAL_LISTING, PROMPT_INJECTION)

MAX_FINDINGS = 20
# Ingestion counts identifier shapes across the whole extracted document, so a
# table row or PDF line carrying one DNI still contributes to the total. The
# canonical gate is stricter: one identifier shape anywhere is already a breach.
IDENTIFIER_THRESHOLD = 2
CANONICAL_IDENTIFIER_THRESHOLD = 1
LISTING_WINDOW_CHARS = 80
DIRECTIVE_WINDOW_CHARS = 40
ROLE_WINDOW_CHARS = 30

# Listing phrase: a list noun followed, within one short window, by a people role.
_LIST_NOUN = r"(?:listado|listados|relacion|relaciones|relacionado|relacionados)"
_PEOPLE_ROLE = (
    r"(?:beneficiari[oa]s?|admitid[oa]s?|excluid[oa]s?|solicitantes?|personas?|"
    r"titular(?:es)?|interesad[oa]s?|agricultor(?:a|es|as)?|olivicultor(?:a|es|as)?|"
    r"perceptor(?:a|es|as)?|concesionari[oa]s?)"
)
_LISTING_PHRASE = re.compile(
    _LIST_NOUN + r"\b[^\n]{0," + str(LISTING_WINDOW_CHARS) + r"}?\b" + _PEOPLE_ROLE + r"\b"
)

# Personal-identifier shapes. Two tokens are needed, so a single stray code is not enough.
_DNI = re.compile(r"\b\d{8}[ -]?[a-z]\b")
_NIE = re.compile(r"\b[xyz][ -]?\d{7}[ -]?[a-z]\b")
_AFFILIATION = re.compile(
    r"\bafiliacion\b[^\n]{0,20}?\b\d{10,12}\b|\b\d{10,12}\b[^\n]{0,20}?\bafiliacion\b"
)

# Directive family addressed to a model or assistant.
_MODEL_OBJECT = (
    r"(?:asistente|modelo(?: de lenguaje)?|inteligencia artificial|chatgpt|gpt|chatbot|"
    r"sistema|ia)\b"
)
_IGNORE_VERB = r"\b(?:ignora|ignorad|ignoren|ignore|olvida|olvidad|olviden|forget)\b"
_INSTRUCTION_OBJECT = (
    r"\b(?:instrucciones|indicaciones|instructions|prompt|anteriores|previas|previous|"
    r"prior|todo lo anterior|lo anterior)\b"
)
_REVEAL_VERB = r"\b(?:revela|revelad|revelen|muestra|muestrame|ensena|ensename|repite|override|reveal|show|print)\b"
_PROMPT_OBJECT = (
    r"\b(?:prompt|mensaje del sistema|system prompt|instrucciones del sistema|"
    r"instrucciones iniciales|reglas del sistema)\b"
)
_INJECTION_PATTERNS = (
    re.compile(_IGNORE_VERB + r"[^\n]{0," + str(DIRECTIVE_WINDOW_CHARS) + r"}?" + _INSTRUCTION_OBJECT),
    re.compile(_REVEAL_VERB + r"[^\n]{0," + str(DIRECTIVE_WINDOW_CHARS) + r"}?" + _PROMPT_OBJECT),
    re.compile(r"\bactua como\b[^\n]{0," + str(ROLE_WINDOW_CHARS) + r"}?" + _MODEL_OBJECT),
    re.compile(
        r"\b(?:act as|you are now)\b[^\n]{0," + str(ROLE_WINDOW_CHARS) + r"}?"
        r"\b(?:assistant|system|model|ai|chatbot)\b"
    ),
    re.compile(
        r"</?\s*(?:system|assistant|developer)\s*>|<\|\s*im_start\s*\|>|\[\s*/?\s*inst\s*\]"
    ),
    re.compile(r"(?m:^)\s*(?:system|assistant|developer)\s*:"),
)

_WHITESPACE = re.compile(r"\s+")


def normalize(text: Any) -> str:
    """Fold case and diacritics and collapse whitespace, keeping punctuation."""
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WHITESPACE.sub(" ", folded).strip().lower()


def _identifier_count(folded: str) -> int:
    return (
        len(_DNI.findall(folded))
        + len(_NIE.findall(folded))
        + len(_AFFILIATION.findall(folded))
    )


def _matches_listing(folded: str, *, title_like: bool, identifier_threshold: int) -> bool:
    if title_like and _LISTING_PHRASE.search(folded):
        return True
    return identifier_threshold <= _identifier_count(folded)


def _matches_injection(folded: str) -> bool:
    return any(pattern.search(folded) for pattern in _INJECTION_PATTERNS)


def flags_for_text(
    text: Any,
    *,
    title_like: bool = False,
    identifier_threshold: int = IDENTIFIER_THRESHOLD,
) -> Tuple[str, ...]:
    """Return the sorted flags for one string.

    ``title_like`` marks a candidate title, document title, or heading, where a
    bare listing phrase is enough. In ordinary body prose only the identifier
    shapes count, so a resolution that merely mentions a list stays clean.
    ``identifier_threshold`` is the number of identifier shapes one string must
    carry; :func:`scan_blocks` re-checks the document-wide total itself and
    :func:`scan_canonical` passes ``CANONICAL_IDENTIFIER_THRESHOLD``.
    """
    folded = normalize(text)
    if not folded:
        return ()
    found: List[str] = []
    if _matches_listing(folded, title_like=title_like, identifier_threshold=identifier_threshold):
        found.append(NOMINAL_LISTING)
    if _matches_injection(folded):
        found.append(PROMPT_INJECTION)
    return tuple(sorted(found))


def scan_text(text: Any, *, title_like: bool = False) -> Tuple[str, ...]:
    """Return the sorted security flags for one string (no positions)."""
    return flags_for_text(text, title_like=title_like)


@dataclass(frozen=True)
class ScanResult:
    """Fixed flags and bounded, content-free findings for one document."""

    flags: Tuple[str, ...] = ()
    findings: Tuple[Dict[str, Any], ...] = ()

    @property
    def flagged(self) -> bool:
        return bool(self.flags)

    @property
    def failure(self) -> Optional[str]:
        """The fixed rejection category, privacy first, or ``None``."""
        for flag in FAILURE_PRECEDENCE:
            if flag in self.flags:
                return flag
        return None

    def as_record(self) -> Dict[str, Any]:
        """The serializable ``security`` object stored on an ingestion record."""
        return {
            "scan_version": SCAN_VERSION,
            "flags": list(self.flags),
            "findings": [dict(finding) for finding in self.findings],
        }


def scan_blocks(
    blocks: Iterable[Mapping[str, Any]],
    *,
    titles: Iterable[Any] = (),
) -> ScanResult:
    """Scan extracted blocks and optional titles for the fixed flags.

    Identifier shapes are counted across the whole document (every title and
    block) before ``nominal_listing`` is decided, because HTML table cells and
    PDF lines are separate blocks that may each carry only one shape. A finding
    still points at the block that contributed: ``{"flag", "page",
    "block_index"}`` only, with ``block_index`` ``None`` for a title. Every
    finding is capped at ``MAX_FINDINGS``.
    """
    found: set = set()
    findings: List[Dict[str, Any]] = []

    def record(flags: Iterable[str], page: Optional[int], block_index: Optional[int]) -> None:
        for flag in flags:
            found.add(flag)
            if len(findings) < MAX_FINDINGS:
                findings.append({"flag": flag, "page": page, "block_index": block_index})

    entries: List[Tuple[Optional[int], Optional[int], str, bool]] = []
    for title in titles:
        folded = normalize(title)
        if folded:
            entries.append((None, None, folded, True))
    for index, block in enumerate(blocks):
        if not isinstance(block, Mapping):
            continue
        page = block.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            page = None
        folded = normalize(block.get("text"))
        if not folded:
            continue
        entries.append((page, index, folded, block.get("kind") == "heading"))

    document_identifiers = sum(_identifier_count(folded) for _, _, folded, _ in entries)
    identifier_listing = document_identifiers >= IDENTIFIER_THRESHOLD

    for page, block_index, folded, title_like in entries:
        current: List[str] = []
        if (title_like and _LISTING_PHRASE.search(folded)) or (
            identifier_listing and _identifier_count(folded) > 0
        ):
            current.append(NOMINAL_LISTING)
        if _matches_injection(folded):
            current.append(PROMPT_INJECTION)
        record(flags=sorted(set(current)), page=page, block_index=block_index)

    return ScanResult(tuple(sorted(found)), tuple(findings))


def scan_canonical(catalog: Any, passages: Any) -> Tuple[str, ...]:
    """Return sorted flags for canonical catalog metadata and passage text.

    Called only by the release gate: it never writes, and it never makes an
    answer. Every catalog string value is scanned title-like because a source
    title can itself be a listing; passage ``location`` is title-like and
    passage ``text`` is ordinary body prose. The canonical corpus is stricter
    than ingestion: one identifier shape is already a breach, so a tampered
    passage naming a single DNI/NIE cannot be published.
    """
    found: set = set()

    if isinstance(catalog, Mapping):
        sources = catalog.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if not isinstance(source, Mapping):
                    continue
                for value in source.values():
                    if isinstance(value, str):
                        found.update(
                            flags_for_text(
                                value,
                                title_like=True,
                                identifier_threshold=CANONICAL_IDENTIFIER_THRESHOLD,
                            )
                        )

    if isinstance(passages, Mapping):
        items = passages.get("passages")
        if isinstance(items, list):
            for passage in items:
                if not isinstance(passage, Mapping):
                    continue
                found.update(
                    flags_for_text(
                        passage.get("location"),
                        title_like=True,
                        identifier_threshold=CANONICAL_IDENTIFIER_THRESHOLD,
                    )
                )
                found.update(
                    flags_for_text(
                        passage.get("text"),
                        identifier_threshold=CANONICAL_IDENTIFIER_THRESHOLD,
                    )
                )

    return tuple(sorted(found))


def validate_security(value: Any) -> bool:
    """Return True when a stored ``security`` object has a well-formed shape.

    The scan version is validated as the expected token shape, not equality:
    a record scanned by an older version stays readable so the next ingestion
    run can rescan it from disk. :func:`is_current_security` decides currency.
    """
    if not isinstance(value, Mapping):
        return False
    if not set(value).issubset({"scan_version", "flags", "findings"}):
        return False
    version = value.get("scan_version")
    if not isinstance(version, str) or not _SCAN_VERSION_PATTERN.fullmatch(version):
        return False
    flags = value.get("flags")
    if not isinstance(flags, list) or any(flag not in FLAGS for flag in flags):
        return False
    if len(set(flags)) != len(flags):
        return False
    findings = value.get("findings")
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        return False
    for finding in findings:
        if not isinstance(finding, Mapping) or set(finding) != {"flag", "page", "block_index"}:
            return False
        if finding["flag"] not in FLAGS:
            return False
        if finding["page"] is not None and not isinstance(finding["page"], int):
            return False
        if finding["block_index"] is not None and not isinstance(finding["block_index"], int):
            return False
    return True


def is_current_security(value: Any) -> bool:
    """Return True when a stored scan is current and carries no flag."""
    return (
        validate_security(value)
        and value.get("scan_version") == SCAN_VERSION
        and value.get("flags") == []
    )
