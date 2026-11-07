"""Turn quarantined official PDFs into review Markdown with honest provenance.

This module consumes the ``official-ingestion-state-v1`` quarantine written by
``app/document_ingestion.py`` and writes, per PDF candidate, one clean Markdown
file plus one provenance manifest. A later structural chunker
(``legal_structure_chunker``) reads those artifacts; nothing written here is
answerable knowledge.

Boundaries:

- the parser never writes canonical knowledge, never changes the ingestion
  state or a candidate ``review_status``, and is not read by ``/ask``,
  retrieval, readiness, the release builder, or the review merge;
- it reads the quarantine only: no network access, no fetch, no model download,
  no paid OCR service;
- the base runtime is standard-library only. The optional ``docparse`` profile
  adds layout (``pymupdf4llm``), table (``docling``) and OCR (``tesseract``,
  language ``spa``) adapters; each is imported lazily inside its adapter, and a
  missing or failing adapter degrades that one capability with a fixed code;
- structure, table cells, and article numbers are never invented: headings,
  lists, and tables appear only when an adapter derives them;
- artifacts are hash-named, canonical JSON, written atomically, and carry no
  timestamp, no absolute path, and no document text in the run report.

Failure, warning, and capability codes are fixed, value-free strings.
"""

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from app.change_impact import ImpactAnalysisError, load_ingestion_state

PARSER = "manijero-markdown-parser-v1"
DOCUMENT_VERSION = "legal-markdown-document-v1"
UPSTREAM_DOCUMENT_VERSION = "official-ingestion-document-v1"

MAX_DOCUMENTS = 1000
MAX_BLOCKS = 5000
MAX_CHARACTERS = 2000000
MAX_MARKDOWN_BYTES = 8 * 1024 * 1024
MAX_TABLE_PAGES = 50
MAX_OCR_PAGES = 100
OCR_PAGE_TIMEOUT_SECONDS = 60
MAX_HEADING_LEVEL = 6
OCR_DPI = 200

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

CANDIDATE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
ORIGINAL_NAME_PATTERN = re.compile(r"^original-[a-f0-9]{64}\.pdf$")
EXTRACTED_NAME_PATTERN = re.compile(r"^extracted-[a-f0-9]{64}\.json$")
PAGE_NUMBER_PATTERN = re.compile(
    r"^(?:p[áa]g(?:ina)?\.?\s*)?[-–—]?\s*\d{1,3}\s*[-–—]?$", re.IGNORECASE
)
DIGITS_PATTERN = re.compile(r"\d+")

LAYOUT = "layout"
TABLES = "tables"
OCR = "ocr"
CAPABILITIES = (LAYOUT, TABLES, OCR)

# Runtime detection outcomes.
RUNTIME_READY = "ready"
RUNTIME_UNAVAILABLE = "unavailable"
CAPABILITY_REASONS = frozenset({"runtime_missing", "binary_missing", "language_missing"})

# Manifest capability states.
USED = "used"
NOT_NEEDED = "not_needed"
UNAVAILABLE = "unavailable"
FAILED = "failed"
# Fixed per-document failures. They never carry upstream text.
FAILURES = frozenset(
    {
        "missing_source",
        "source_hash_mismatch",
        "invalid_extracted_document",
        "no_extractable_text",
        "size_limit_exceeded",
        "internal_error",
    }
)

# Fixed skips: a candidate this parser deliberately does not handle.
SKIPS = frozenset({"not_a_pdf", "not_extracted"})

# Fixed run-level failures: nothing is written.
GLOBAL_FAILURES = frozenset(
    {
        "invalid_ingestion_state",
        "candidate_count_exceeded",
        "unsafe_output_root",
        "internal_error",
    }
)

# Fixed, value-free warning codes.
WARNINGS = frozenset(
    {
        "layout_runtime_unavailable",
        "layout_adapter_failed",
        "tables_runtime_unavailable",
        "tables_adapter_failed",
        "tables_page_budget_exceeded",
        "ocr_runtime_unavailable",
        "ocr_adapter_failed",
        "ocr_page_budget_exceeded",
        "ocr_timeout",
        "no_text_layer",
    }
)

BLOCK_KINDS = frozenset({"heading", "text", "list_item", "table"})


class ParserError(ValueError):
    """An invalid configuration, state, or document that must fail closed."""

    def __init__(self, failure: str, warnings: Iterable[str] = ()) -> None:
        if failure not in FAILURES and failure not in GLOBAL_FAILURES:
            failure = "internal_error"
        self.failure = failure
        self.warnings = sorted({item for item in warnings if item in WARNINGS})
        super().__init__(failure)


@dataclass(frozen=True)
class Block:
    """One rendered content block of a page."""

    kind: str
    text: str = ""
    level: int = 2
    rows: Tuple[Tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Capability:
    """Detected state of one optional parsing capability."""

    status: str
    reason: Optional[str] = None
    version: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {"status": self.status, "reason": self.reason, "version": self.version}


@dataclass(frozen=True)
class ParserRuntime:
    """Detected capabilities plus the adapters that implement them.

    Tests inject adapters through ``detect_runtime``; the base runtime detects
    everything as unavailable and passes no adapter at all.
    """

    profile: str
    capabilities: Mapping[str, Capability]
    adapters: Mapping[str, Any]

    def signature(self) -> str:
        """Stable identity of this runtime, used to decide an unchanged skip."""
        payload = {
            "profile": self.profile,
            "capabilities": {
                name: {"status": capability.status, "version": capability.version}
                for name, capability in self.capabilities.items()
            },
        }
        return _sha256(_canonical_json(payload).encode("utf-8"))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _collapse(text: Any) -> str:
    return " ".join(str(text).split())


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(str(temporary), str(path))


# ---------------------------------------------------------------------------------------------
# Runtime detection
# ---------------------------------------------------------------------------------------------


def _module_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except Exception:
        return None


def _detect_layout() -> Tuple[Capability, Optional[Any]]:
    if importlib.util.find_spec("pymupdf4llm") is None:
        return Capability(RUNTIME_UNAVAILABLE, "runtime_missing"), None
    adapter = _Pymupdf4llmLayout(_module_version("pymupdf4llm") or "unknown")
    return Capability(RUNTIME_READY, None, adapter.version), adapter


def _detect_tables() -> Tuple[Capability, Optional[Any]]:
    if importlib.util.find_spec("docling") is None:
        return Capability(RUNTIME_UNAVAILABLE, "runtime_missing"), None
    adapter = _DoclingTables(_module_version("docling") or "unknown")
    return Capability(RUNTIME_READY, None, adapter.version), adapter


def _detect_ocr() -> Tuple[Capability, Optional[Any]]:
    if importlib.util.find_spec("pytesseract") is None or importlib.util.find_spec("pymupdf") is None:
        return Capability(RUNTIME_UNAVAILABLE, "runtime_missing"), None
    try:
        import pytesseract
    except Exception:
        return Capability(RUNTIME_UNAVAILABLE, "runtime_missing"), None
    try:
        binary_version = str(pytesseract.get_tesseract_version())
    except Exception:
        return Capability(RUNTIME_UNAVAILABLE, "binary_missing"), None
    try:
        languages = list(pytesseract.get_languages(config=""))
    except Exception:
        languages = []
    if "spa" not in languages:
        return Capability(RUNTIME_UNAVAILABLE, "language_missing"), None
    adapter = _TesseractOcr("tesseract " + binary_version)
    return Capability(RUNTIME_READY, None, adapter.version), adapter


def detect_runtime(
    *,
    layout: Optional[Any] = None,
    tables: Optional[Any] = None,
    ocr: Optional[Any] = None,
) -> ParserRuntime:
    """Detect the parsing capabilities, or accept injected adapters.

    An injected adapter is reported ``ready`` with the adapter's own version.
    Nothing heavy is imported here beyond what detection needs: a missing
    module is reported from ``find_spec`` alone.
    """
    capabilities: Dict[str, Capability] = {}
    adapters: Dict[str, Any] = {}
    for name, detector, injected in (
        (LAYOUT, _detect_layout, layout),
        (TABLES, _detect_tables, tables),
        (OCR, _detect_ocr, ocr),
    ):
        if injected is not None:
            capabilities[name] = Capability(
                RUNTIME_READY, None, str(getattr(injected, "version", "unknown"))
            )
            adapters[name] = injected
            continue
        capability, adapter = detector()
        capabilities[name] = capability
        if adapter is not None:
            adapters[name] = adapter
    profile = "docparse" if any(
        capability.status == RUNTIME_READY for capability in capabilities.values()
    ) else "base"
    return ParserRuntime(profile, capabilities, adapters)


def runtime_lines(runtime: ParserRuntime) -> List[str]:
    """One plain-language line per capability, for ``--check-runtime``."""
    labels = {
        LAYOUT: "Layout (pymupdf4llm)",
        TABLES: "Tables (docling)",
        OCR: "OCR (Tesseract, Spanish)",
    }
    reasons = {
        "runtime_missing": "the optional docparse environment is not installed",
        "binary_missing": "the Tesseract program is not installed",
        "language_missing": "the Spanish (spa) Tesseract language data is not installed",
    }
    lines: List[str] = []
    for name in CAPABILITIES:
        capability = runtime.capabilities[name]
        if capability.status == RUNTIME_READY:
            lines.append("{}: ready (version {}).".format(labels[name], capability.version))
        else:
            lines.append(
                "{}: not available ({}).".format(
                    labels[name], reasons.get(capability.reason or "", "unavailable")
                )
            )
    return lines


# ---------------------------------------------------------------------------------------------
# Optional adapters (imported lazily; each one implements one capability)
# ---------------------------------------------------------------------------------------------


class _Pymupdf4llmLayout:
    """Layout adapter: per-page headings, list items, and paragraphs."""

    def __init__(self, version: str) -> None:
        self.version = version

    def pages(self, path: Path, page_count: int) -> Dict[int, List[Block]]:
        import pymupdf4llm

        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
        pages: Dict[int, List[Block]] = {}
        for index, chunk in enumerate(chunks, start=1):
            text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
            pages[index] = _blocks_from_markdown(text)
        return pages


class _DoclingTables:
    """Table adapter: per-page pipe-table rows from Docling's document model."""

    def __init__(self, version: str) -> None:
        self.version = version

    def tables(self, path: Path, page_count: int) -> Dict[int, List[Block]]:
        from docling.document_converter import DocumentConverter

        converted = DocumentConverter().convert(str(path))
        document = converted.document
        pages: Dict[int, List[Block]] = {}
        for table in list(getattr(document, "tables", []) or []):
            page = _docling_page(table)
            rows = _docling_rows(table)
            if page is None or not rows:
                continue
            pages.setdefault(page, []).append(Block("table", rows=rows))
        return pages


class _TesseractOcr:
    """OCR adapter: rasterize one page and read it as Spanish text."""

    def __init__(self, version: str) -> None:
        self.version = version

    def page_text(self, path: Path, page_number: int, timeout: int) -> str:
        import pymupdf
        import pytesseract

        with pymupdf.open(str(path)) as document:
            page = document.load_page(page_number - 1)
            image = page.get_pixmap(dpi=OCR_DPI).pil_image()
        try:
            return pytesseract.image_to_string(image, lang="spa", timeout=timeout)
        except RuntimeError as error:
            # pytesseract reports its own ``timeout`` option as a RuntimeError.
            # Translate only that case so the caller records ``ocr_timeout`` and
            # degrades one page instead of the whole capability.
            if "timeout" in str(error).lower():
                raise TimeoutError("ocr page timeout") from error
            raise


def _docling_page(table: Any) -> Optional[int]:
    for provenance in list(getattr(table, "prov", []) or []):
        page = getattr(provenance, "page_no", None)
        if isinstance(page, int) and page >= 1:
            return page
    return None


def _docling_rows(table: Any) -> Tuple[Tuple[str, ...], ...]:
    grid = getattr(getattr(table, "data", None), "grid", None)
    if not grid:
        return ()
    rows: List[Tuple[str, ...]] = []
    for row in grid:
        cells = tuple(_collapse(getattr(cell, "text", "")).replace("|", "\\|") for cell in row)
        if any(cells):
            rows.append(cells)
    return tuple(rows)


def _blocks_from_markdown(text: str) -> List[Block]:
    """Turn adapter Markdown into blocks, never into a table.

    A pipe table produced by the layout adapter is kept as plain paragraph
    lines: only the table adapter may create table cells.
    """
    blocks: List[Block] = []
    paragraph: List[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block("text", _collapse(" ".join(paragraph))))
            paragraph.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading is not None:
            flush()
            blocks.append(
                Block("heading", _collapse(heading.group(2)), min(len(heading.group(1)), MAX_HEADING_LEVEL))
            )
            continue
        item = re.match(r"^[-*+]\s+(.*)$", line)
        if item is not None:
            flush()
            blocks.append(Block("list_item", _collapse(item.group(1))))
            continue
        paragraph.append(line)
    flush()
    return [block for block in blocks if block.text]


# ---------------------------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------------------------


def _record_paths(record: Mapping[str, Any], quarantine: Path) -> Tuple[Path, Path]:
    """Resolve the candidate's quarantine files, refusing any escape."""
    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
        raise ParserError("invalid_ingestion_state")
    resolved = []
    for key, pattern in (("original_path", ORIGINAL_NAME_PATTERN), ("extracted_path", EXTRACTED_NAME_PATTERN)):
        value = record.get(key)
        if not isinstance(value, str):
            raise ParserError("missing_source")
        relative = Path(value)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:1] != (candidate_id,)
            or len(relative.parts) != 2
            or not pattern.fullmatch(relative.parts[1])
        ):
            raise ParserError("missing_source")
        resolved.append(Path(quarantine) / relative)
    return resolved[0], resolved[1]


def _declared_page_count(payload: bytes) -> Optional[int]:
    """Count the PDF's declared pages with the accepted extractor's page walk.

    The upstream ``page_count`` counts pages that produced text, so a scanned
    page inside an otherwise textual publication is invisible in it. The page
    walk is the same standard-library one the extractor uses, imported lazily so
    this module stays light; any failure leaves the count unknown.
    """
    from app.document_ingestion import _pdf_expand_object_streams, _pdf_objects, _pdf_pages

    try:
        pages = _pdf_pages(_pdf_expand_object_streams(_pdf_objects(payload)))
    except Exception:
        return None
    return len(pages) if 0 < len(pages) <= 500 else None


def _load_extracted_document(path: Path, candidate_id: str) -> Tuple[List[Dict[str, Any]], int]:
    """Read the upstream extracted document; unusable blocks are dropped.

    A structurally valid document whose blocks are all unusable is not an error
    here: it becomes a page range with no text, so the parser can report
    ``no_extractable_text`` (or fill it with OCR) instead of inventing text.
    """
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ParserError("invalid_extracted_document") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != UPSTREAM_DOCUMENT_VERSION
        or document.get("candidate_id") != candidate_id
        or not isinstance(document.get("blocks"), list)
    ):
        raise ParserError("invalid_extracted_document")
    blocks: List[Dict[str, Any]] = []
    pages: Set[int] = set()
    for block in document["blocks"]:
        if not isinstance(block, dict):
            raise ParserError("invalid_extracted_document")
        kind = block.get("kind")
        page = block.get("page")
        text = block.get("text")
        if kind not in ("heading", "text") or not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(page, int) or page < 1:
            continue
        blocks.append({"kind": kind, "page": page, "text": _collapse(text)})
        pages.add(page)
    return blocks, max(pages) if pages else 0


# ---------------------------------------------------------------------------------------------
# Cleaning and rendering
# ---------------------------------------------------------------------------------------------


def _page_number_only(text: str) -> bool:
    return bool(PAGE_NUMBER_PATTERN.match(text.strip()))


def _normalized_edge(text: str) -> str:
    return DIGITS_PATTERN.sub("#", _collapse(text).casefold())


def _edge_indexes(blocks: Sequence[Block]) -> Tuple[Optional[int], Optional[int]]:
    indexes = [index for index, block in enumerate(blocks) if block.kind != "table" and block.text]
    if not indexes:
        return None, None
    return indexes[0], indexes[-1]


def _clean_pages(pages: Mapping[int, List[Block]]) -> Dict[int, List[Block]]:
    """Drop a repeated page-edge line or a page-number-only line, never a whole page.

    A line is removed only when it is a page's first or last non-empty line and
    it is page-number-only, or its digit-normalized text repeats on at least
    three pages and half of all pages. A page that would become empty keeps its
    blocks.
    """
    total = len(pages)
    occurrences: Dict[str, Set[int]] = {}
    for page, blocks in pages.items():
        first, last = _edge_indexes(blocks)
        for index in {first, last}:
            if index is None:
                continue
            occurrences.setdefault(_normalized_edge(blocks[index].text), set()).add(page)

    removable: Dict[int, Set[int]] = {page: set() for page in pages}
    for page, blocks in pages.items():
        first, last = _edge_indexes(blocks)
        for index in {first, last}:
            if index is None:
                continue
            text = blocks[index].text
            repeated = len(occurrences.get(_normalized_edge(text), set()))
            if _page_number_only(text) or (repeated >= 3 and repeated * 2 >= total):
                removable[page].add(index)

    cleaned: Dict[int, List[Block]] = {}
    for page in sorted(pages):
        blocks = pages[page]
        kept = [block for index, block in enumerate(blocks) if index not in removable[page]]
        if not kept:
            kept = list(blocks)
        cleaned[page] = kept
    return cleaned


def _table_lines(rows: Sequence[Sequence[str]]) -> List[str]:
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return []

    def line(values: Sequence[str]) -> str:
        cells = [_collapse(value).replace("|", "\\|") for value in values]
        cells = (cells + [""] * width)[:width]
        return "| " + " | ".join(cells) + " |"

    lines = [line(rows[0]), "| " + " | ".join(["---"] * width) + " |"]
    lines.extend(line(row) for row in rows[1:])
    return lines


def _render(
    pages: Mapping[int, List[Block]],
    ocr_pages: Set[int],
    page_warnings: Mapping[int, Set[str]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Render page-mapped Markdown and the manifest's per-page line ranges."""
    lines: List[str] = []
    metadata: List[Dict[str, Any]] = []
    for page in sorted(pages):
        blocks = pages[page]
        start = len(lines) + 1
        lines.append("<!-- page: {} -->".format(page))
        lines.append("")
        tables = 0
        content = 0
        for block in blocks:
            if block.kind == "table":
                rendered = _table_lines(block.rows)
                if not rendered:
                    continue
                tables += 1
                content += 1
                lines.extend(rendered)
                lines.append("")
            elif block.kind == "heading":
                content += 1
                lines.append("#" * max(1, min(block.level, MAX_HEADING_LEVEL)) + " " + block.text)
                lines.append("")
            elif block.kind == "list_item":
                content += 1
                lines.append("- " + block.text)
                lines.append("")
            else:
                content += 1
                lines.append(block.text)
                lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        metadata.append(
            {
                "page": page,
                "line_start": start,
                "line_end": len(lines),
                "blocks": content,
                "tables": tables,
                "ocr": page in ocr_pages,
                "empty": content == 0,
                "warnings": sorted(page_warnings.get(page, set())),
            }
        )
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n", metadata


# ---------------------------------------------------------------------------------------------
# Per-document parsing
# ---------------------------------------------------------------------------------------------


def _sanitize_adapter_blocks(value: Any, page_count: int) -> Dict[int, List[Block]]:
    pages: Dict[int, List[Block]] = {}
    if not isinstance(value, dict):
        raise ValueError("layout adapter returned no mapping")
    for page, blocks in value.items():
        if not isinstance(page, int) or page < 1 or page > page_count:
            continue
        if not isinstance(blocks, (list, tuple)):
            continue
        for block in blocks:
            if not isinstance(block, Block) or block.kind not in BLOCK_KINDS or block.kind == "table":
                continue
            if block.text:
                pages.setdefault(page, []).append(block)
    return pages


def _sanitize_adapter_tables(value: Any, page_count: int) -> Dict[int, List[Block]]:
    pages: Dict[int, List[Block]] = {}
    if not isinstance(value, dict):
        raise ValueError("table adapter returned no mapping")
    for page, tables in value.items():
        if not isinstance(page, int) or page < 1 or page > page_count:
            continue
        if not isinstance(tables, (list, tuple)):
            continue
        for table in tables:
            if not isinstance(table, Block) or table.kind != "table":
                continue
            rows = tuple(
                tuple(_collapse(cell) for cell in row)
                for row in table.rows
                if isinstance(row, (list, tuple))
            )
            rows = tuple(row for row in rows if any(row))
            if rows:
                pages.setdefault(page, []).append(Block("table", rows=rows))
    return pages


def _previous_manifest(path: Path) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _unchanged(
    manifest_path: Path,
    markdown_path: Path,
    source_sha256: str,
    runtime: ParserRuntime,
) -> Optional[Dict[str, Any]]:
    manifest = _previous_manifest(manifest_path)
    if manifest is None or not markdown_path.is_file():
        return None
    runtime_block = manifest.get("runtime")
    if (
        manifest.get("schema_version") != DOCUMENT_VERSION
        or manifest.get("parser") != PARSER
        or manifest.get("source_sha256") != source_sha256
        or not isinstance(runtime_block, dict)
        or runtime_block.get("signature") != runtime.signature()
    ):
        return None
    try:
        digest = _sha256(markdown_path.read_bytes())
    except OSError:
        return None
    return manifest if manifest.get("markdown_sha256") == digest else None


def _skipped_outcome(record: Mapping[str, Any], code: str) -> Dict[str, Any]:
    if code not in SKIPS:
        raise ParserError("internal_error")
    recorded_pages = record.get("page_count")
    return {
        "candidate_id": record.get("candidate_id"),
        "status": "skipped",
        "failure": code,
        "warnings": [],
        "page_count": recorded_pages if isinstance(recorded_pages, int) else None,
        "empty_pages": 0,
        "table_count": 0,
        "ocr_page_count": 0,
        "markdown_sha256": None,
    }


def _failed_outcome(record: Mapping[str, Any], failure: str, warnings: Iterable[str] = (),
                    empty_pages: int = 0, page_count: Optional[int] = None) -> Dict[str, Any]:
    recorded_pages = record.get("page_count")
    return {
        "candidate_id": record.get("candidate_id"),
        "status": "failed",
        "failure": failure,
        "warnings": sorted({item for item in warnings if item in WARNINGS}),
        "page_count": page_count if page_count is not None else (
            recorded_pages if isinstance(recorded_pages, int) else None
        ),
        "empty_pages": empty_pages,
        "table_count": 0,
        "ocr_page_count": 0,
        "markdown_sha256": None,
    }


class _NoText(ParserError):
    """A document whose every page stayed empty after the adapters ran."""

    def __init__(self, warnings: Iterable[str], page_count: int) -> None:
        super().__init__("no_extractable_text", warnings)
        self.page_count = page_count
        self.empty_pages = page_count


def _parse_candidate(
    record: Mapping[str, Any],
    quarantine: Path,
    output: Path,
    runtime: ParserRuntime,
) -> Dict[str, Any]:
    candidate_id = record["candidate_id"]
    if record.get("status") != "extracted":
        return _skipped_outcome(record, "not_extracted")
    if record.get("media_type") != "pdf":
        return _skipped_outcome(record, "not_a_pdf")

    original_path, extracted_path = _record_paths(record, quarantine)
    if not original_path.is_file():
        raise ParserError("missing_source")
    try:
        source_bytes = original_path.read_bytes()
    except OSError as error:
        raise ParserError("missing_source") from error
    source_sha256 = _sha256(source_bytes)
    if record.get("original_sha256") != source_sha256:
        raise ParserError("source_hash_mismatch")

    blocks, extracted_pages = _load_extracted_document(extracted_path, candidate_id)
    declared_pages = _declared_page_count(source_bytes) or 0
    recorded_pages = record.get("page_count")
    page_count = max(
        declared_pages,
        extracted_pages,
        recorded_pages if isinstance(recorded_pages, int) and recorded_pages >= 1 else 0,
    )
    if page_count < 1:
        raise ParserError("invalid_extracted_document")
    pages: Dict[int, List[Block]] = {page: [] for page in range(1, page_count + 1)}
    for block in blocks:
        kind = "heading" if block["kind"] == "heading" else "text"
        pages[block["page"]].append(Block(kind, block["text"]))

    warnings: Set[str] = set()
    capabilities: Dict[str, str] = {}
    layout_blocks: Dict[int, List[Block]] = {}
    table_blocks: Dict[int, List[Block]] = {}

    if LAYOUT in runtime.adapters:
        try:
            layout_blocks = _sanitize_adapter_blocks(
                runtime.adapters[LAYOUT].pages(original_path, page_count), page_count
            )
            capabilities[LAYOUT] = USED if layout_blocks else NOT_NEEDED
        except Exception:
            warnings.add("layout_adapter_failed")
            capabilities[LAYOUT] = FAILED
    else:
        warnings.add("layout_runtime_unavailable")
        capabilities[LAYOUT] = UNAVAILABLE

    if TABLES in runtime.adapters:
        try:
            found = _sanitize_adapter_tables(
                runtime.adapters[TABLES].tables(original_path, page_count), page_count
            )
            for page in sorted(found)[:MAX_TABLE_PAGES]:
                table_blocks[page] = found[page]
            if len(found) > MAX_TABLE_PAGES:
                warnings.add("tables_page_budget_exceeded")
            capabilities[TABLES] = USED if table_blocks else NOT_NEEDED
        except Exception:
            warnings.add("tables_adapter_failed")
            capabilities[TABLES] = FAILED
    else:
        warnings.add("tables_runtime_unavailable")
        capabilities[TABLES] = UNAVAILABLE

    for page, found in layout_blocks.items():
        if found:
            pages[page] = list(found)
    for page, found in table_blocks.items():
        pages[page] = pages[page] + list(found)

    ocr_pages: Set[int] = set()
    page_warnings: Dict[int, Set[str]] = {page: set() for page in pages}
    empty = [page for page in sorted(pages) if not pages[page]]
    if empty:
        if OCR in runtime.adapters:
            used = 0
            failed = False
            for page in empty:
                if used >= MAX_OCR_PAGES:
                    warnings.add("ocr_page_budget_exceeded")
                    break
                used += 1
                try:
                    text = _collapse(
                        runtime.adapters[OCR].page_text(original_path, page, OCR_PAGE_TIMEOUT_SECONDS)
                    )
                except TimeoutError:
                    warnings.add("ocr_timeout")
                    page_warnings[page].add("ocr_timeout")
                    failed = True
                    continue
                except Exception:
                    warnings.add("ocr_adapter_failed")
                    page_warnings[page].add("ocr_adapter_failed")
                    failed = True
                    continue
                if text:
                    pages[page] = [Block("text", text)]
                    ocr_pages.add(page)
                else:
                    page_warnings[page].add("no_text_layer")
            if failed:
                capabilities[OCR] = FAILED
            elif ocr_pages:
                capabilities[OCR] = USED
            elif used:
                capabilities[OCR] = NOT_NEEDED
            else:
                capabilities[OCR] = NOT_NEEDED
            if len(ocr_pages) < len(empty):
                warnings.add("no_text_layer")
        else:
            warnings.add("ocr_runtime_unavailable")
            capabilities[OCR] = UNAVAILABLE
            for page in empty:
                page_warnings[page].add("no_text_layer")
            warnings.add("no_text_layer")

    for page in pages:
        if not pages[page]:
            page_warnings[page].add("no_text_layer")
    empty_pages = sum(1 for page in pages if not pages[page])
    if empty_pages == len(pages):
        raise _NoText(warnings, empty_pages)

    pages = _clean_pages(pages)
    markdown, page_metadata = _render(pages, ocr_pages, page_warnings)
    if len(markdown.encode("utf-8")) > MAX_MARKDOWN_BYTES:
        raise ParserError("size_limit_exceeded", warnings)
    block_count = sum(item["blocks"] for item in page_metadata)
    character_count = sum(
        len(block.text) if block.kind != "table" else sum(len(cell) for row in block.rows for cell in row)
        for page in pages.values()
        for block in page
    )
    if block_count > MAX_BLOCKS or character_count > MAX_CHARACTERS:
        raise ParserError("size_limit_exceeded", warnings)

    table_count = sum(item["tables"] for item in page_metadata)
    markdown_sha256 = _sha256(markdown.encode("utf-8"))
    markdown_path = Path(output) / candidate_id / "markdown-{}.md".format(source_sha256)
    manifest_path = Path(output) / candidate_id / "parse-{}.json".format(source_sha256)

    previous = _unchanged(manifest_path, markdown_path, source_sha256, runtime)
    if previous is not None:
        return {
            "candidate_id": candidate_id,
            "status": "unchanged",
            "failure": None,
            "warnings": sorted(warnings),
            "page_count": page_count,
            "empty_pages": empty_pages,
            "table_count": previous.get("table_count", table_count),
            "ocr_page_count": previous.get("ocr_page_count", len(ocr_pages)),
            "markdown_sha256": markdown_sha256,
        }

    manifest: Dict[str, Any] = {
        "schema_version": DOCUMENT_VERSION,
        "parser": PARSER,
        "candidate_id": candidate_id,
        "title": record.get("title"),
        "source_sha256": source_sha256,
        "source_path": str(Path(record["original_path"])),
        "upstream_extractor": record.get("extractor"),
        "markdown_path": str(Path(candidate_id) / markdown_path.name),
        "markdown_sha256": markdown_sha256,
        "markdown_bytes": len(markdown.encode("utf-8")),
        "page_count": page_count,
        "block_count": block_count,
        "character_count": character_count,
        "table_count": table_count,
        "ocr_page_count": len(ocr_pages),
        "pages": page_metadata,
        "capabilities": {
            name: {
                "status": capabilities.get(name, NOT_NEEDED),
                "reason": (
                    runtime.capabilities[name].reason
                    if runtime.capabilities[name].reason in CAPABILITY_REASONS
                    else None
                ),
                "version": runtime.capabilities[name].version,
            }
            for name in CAPABILITIES
        },
        "warnings": sorted(warnings),
        "runtime": {"profile": runtime.profile, "signature": runtime.signature()},
    }
    previous_manifest = _previous_manifest(manifest_path)
    if previous_manifest is not None:
        previous_digest = previous_manifest.get("markdown_sha256")
        if isinstance(previous_digest, str) and SHA256_PATTERN.fullmatch(previous_digest):
            manifest["previous_markdown_sha256"] = previous_digest

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(markdown_path, markdown)
    _atomic_write_text(manifest_path, _canonical_json(manifest))
    return {
        "candidate_id": candidate_id,
        "status": "parsed",
        "failure": None,
        "warnings": sorted(warnings),
        "page_count": page_count,
        "empty_pages": empty_pages,
        "table_count": table_count,
        "ocr_page_count": len(ocr_pages),
        "markdown_sha256": markdown_sha256,
    }


# ---------------------------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------------------------


def parse_documents(
    state_path: Path,
    quarantine_dir: Path,
    output_dir: Path,
    runtime: Optional[ParserRuntime] = None,
) -> Dict[str, Any]:
    """Parse every extracted PDF candidate into Markdown plus a manifest.

    Global configuration or state errors raise ``ParserError`` before anything
    is written. A per-document failure is recorded and never aborts the run,
    and it never touches that candidate's previous artifact pair.
    """
    state_path = Path(state_path)
    quarantine_root = Path(quarantine_dir)
    output_root = Path(output_dir)

    if _inside_directory(output_root, KNOWLEDGE_ROOT):
        raise ParserError("unsafe_output_root")
    try:
        same_as_quarantine = output_root.resolve() == quarantine_root.resolve()
    except OSError as error:
        raise ParserError("unsafe_output_root") from error
    if same_as_quarantine or _inside_directory(output_root, quarantine_root):
        raise ParserError("unsafe_output_root")

    try:
        state = load_ingestion_state(state_path)
    except ImpactAnalysisError as error:
        raise ParserError(error.failure) from error
    except Exception as error:
        raise ParserError("invalid_ingestion_state") from error
    if len(state["candidates"]) > MAX_DOCUMENTS:
        raise ParserError("candidate_count_exceeded")

    runtime = runtime or detect_runtime()
    output_root.mkdir(parents=True, exist_ok=True)

    outcomes: List[Dict[str, Any]] = []
    for candidate_id in sorted(state["candidates"]):
        record = state["candidates"][candidate_id]
        try:
            outcomes.append(_parse_candidate(record, quarantine_root, output_root, runtime))
        except _NoText as error:
            outcomes.append(
                _failed_outcome(
                    record, error.failure, error.warnings, error.empty_pages, error.page_count
                )
            )
        except ParserError as error:
            outcomes.append(_failed_outcome(record, error.failure, error.warnings))
        except Exception:
            outcomes.append(_failed_outcome(record, "internal_error"))

    summary = {
        "documents": len(outcomes),
        "parsed": sum(1 for item in outcomes if item["status"] == "parsed"),
        "unchanged": sum(1 for item in outcomes if item["status"] == "unchanged"),
        "failed": sum(1 for item in outcomes if item["status"] == "failed"),
        "skipped": sum(1 for item in outcomes if item["status"] == "skipped"),
    }
    return {
        "run": {"parser": PARSER, "document_version": DOCUMENT_VERSION},
        "runtime": {
            "profile": runtime.profile,
            "signature": runtime.signature(),
            "capabilities": {
                name: runtime.capabilities[name].as_dict() for name in CAPABILITIES
            },
        },
        "documents": outcomes,
        "summary": summary,
        "state": str(state_path),
        "quarantine": str(quarantine_root),
        "output": str(output_root),
    }
