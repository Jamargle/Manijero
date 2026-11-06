"""Turn parsed legal Markdown into article-scale chunks with honest provenance.

This module consumes the ``legal-markdown-document-v1`` artifacts written by
``app/legal_document_parser.py`` and writes, per document, one deterministic
chunk set plus one run manifest under an operator-owned output root. A later
reviewed indexing step (``structured_chunk_index``) reads those artifacts;
nothing written here is answerable knowledge.

Boundaries:

- the chunker never writes canonical knowledge, never changes a candidate
  ``review_status``, and is not read by ``/ask``, retrieval, readiness, the
  release builder, or the review merge;
- it reads local Markdown and JSON only: no PDF or HTML re-reading, no network,
  no model, no OCR, no download;
- splitting uses only explicit article/chapter/annex heading lines. ``Título``,
  ``Sección``, ``Disposición``, ``Preámbulo``, numbered sub-items, and table rows
  never open a chunk, so a document written in another shape stays whole or is
  reported ``unstructured`` instead of being split on a guess;
- validity metadata is copied only from a reviewed source-catalog entry whose
  ``content_sha256`` equals the document's ``source_sha256``. Otherwise validity
  stays ``unknown``; no date, campaign, or applicability is read from the text;
- artifacts are hash-named, canonical JSON, written atomically, and carry no
  timestamp, no absolute path, and no document text in the run report.

Catalog validation is deterministic: ``validate_catalog`` needs an explicit
``as_of``, and this module always passes ``CATALOG_AS_OF`` (the earliest
possible date, ``0001-01-01``). Reading the wall clock would make two runs of
the same input differ, and expiry is a retrieval concern (``--as-of``), not a
chunking one. A catalog entry whose ``valid_until`` is in the past therefore
still joins, and its reviewed ``valid_until`` is copied verbatim.

Failure, warning, and status codes are fixed, value-free strings.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from app.source_catalog import CatalogReadError, load_catalog, validate_catalog

CHUNKER = "manijero-legal-chunker-v1"
CHUNK_SET_VERSION = "legal-chunk-set-v1"
CHUNK_MANIFEST_VERSION = "legal-chunk-manifest-v1"
MANIFEST_VERSION = "legal-markdown-document-v1"

MAX_DOCUMENTS = 1000
MAX_MARKDOWN_BYTES = 8 * 1024 * 1024
MAX_CHUNKS = 2000
MAX_HEADING_CHARS = 200
CHUNK_SOFT_LIMIT = 8000

# Deterministic catalog-validation date. See the module docstring: expiry is a
# retrieval concern, so no reviewed entry is rejected here for being expired.
CATALOG_AS_OF = date.min

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"
SCHEMA_PATH = KNOWLEDGE_ROOT / "legal-chunk-set.schema.json"

CANDIDATE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MANIFEST_NAME_PATTERN = re.compile(r"^parse-([a-f0-9]{64})\.json$")
PAGE_MARKER_PATTERN = re.compile(r"^<!-- page: ([0-9]+) -->$")
ATX_PATTERN = re.compile(r"^#{1,6}[ \t]+")

# One heading shape, shared by every parser runtime that produces this Markdown.
# It is deliberately narrow: a label, a numeral, then end-of-line or a
# separator. Prose such as ``Artículo 14 de la presente Ley`` never matches.
HEADING_LABEL = r"(?P<label>art[ií]culo|cap[ií]tulo|anexo)"
HEADING_NUMERAL = r"(?P<numeral>[0-9]+|[IVXLCDM]+|[uú]nico|[uú]nica|primero|primera)"
HEADING_SUFFIX = r"(?:\s+(?P<suffix>bis|ter|quater))?"
HEADING_SEPARATOR = r"[ \t]*(?=$|[.:\u2013-])"
HEADING_PATTERN = re.compile(
    r"^" + HEADING_LABEL + r"\s+" + HEADING_NUMERAL + HEADING_SUFFIX + HEADING_SEPARATOR,
    re.IGNORECASE,
)

HEADING_KINDS = {"art": "article", "cap": "chapter", "ane": "annex"}
HEADING_LEVELS = {"article": 2, "chapter": 1, "annex": 1}

STATUSES = ("chunked", "unstructured", "failed")

# Fixed per-document failures. They never carry document text.
FAILURES = frozenset(
    {
        "invalid_manifest",
        "candidate_mismatch",
        "missing_markdown",
        "markdown_hash_mismatch",
        "page_map_mismatch",
        "size_limit_exceeded",
        "chunk_limit_exceeded",
        "missing_title",
        "internal_error",
    }
)

# Fixed, value-free warning codes.
WARNINGS = frozenset(
    {
        "no_structure_headings",
        "catalog_source_unknown",
        "chunk_over_soft_limit",
    }
)

# Fixed run-level refusals: nothing is written.
GLOBAL_FAILURES = frozenset(
    {
        "unsafe_output_root",
        "missing_documents_root",
        "missing_catalog",
        "invalid_catalog",
        "manifest_count_exceeded",
        "internal_error",
    }
)

MANIFEST_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "parser",
        "candidate_id",
        "title",
        "source_sha256",
        "source_path",
        "upstream_extractor",
        "markdown_path",
        "markdown_sha256",
        "markdown_bytes",
        "page_count",
        "block_count",
        "character_count",
        "table_count",
        "ocr_page_count",
        "pages",
        "capabilities",
        "warnings",
        "runtime",
    }
)
MANIFEST_OPTIONAL_KEYS = frozenset({"previous_markdown_sha256"})
PAGE_KEYS = frozenset(
    {"page", "line_start", "line_end", "blocks", "tables", "ocr", "empty", "warnings"}
)
CAPABILITY_NAMES = ("layout", "tables", "ocr")
CAPABILITY_KEYS = frozenset({"status", "reason", "version"})
CAPABILITY_STATUSES = ("used", "not_needed", "unavailable", "failed")
RUNTIME_KEYS = frozenset({"profile", "signature"})
RUNTIME_PROFILES = ("base", "docparse")

CHUNK_SET_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "chunker",
        "input",
        "validity_status",
        "chunk_count",
        "chunks",
        "warnings",
    }
)
CHUNK_SET_OPTIONAL_KEYS = frozenset({"catalog"})
CHUNK_INPUT_KEYS = frozenset({"candidate_id", "source_sha256", "markdown_sha256", "title"})
CHUNK_KEYS = frozenset(
    {
        "id",
        "candidate_id",
        "source_sha256",
        "markdown_sha256",
        "heading_path",
        "location",
        "page_start",
        "page_end",
        "character_count",
        "text",
    }
)
# Reviewed catalog values copied into a chunk set, in artifact order.
CATALOG_BLOCK_KEYS = (
    "source_id",
    "catalog_sha256",
    "published_on",
    "lifecycle_status",
    "valid_until",
    "campaign",
    "critical",
    "applicability",
)
CATALOG_OPTIONAL_VALUES = (
    "published_on",
    "lifecycle_status",
    "valid_until",
    "campaign",
    "critical",
    "applicability",
)
APPLICABILITY_KEYS = frozenset({"crop", "water_regime", "production_method"})

RUN_MANIFEST_REQUIRED_KEYS = frozenset({"schema_version", "chunker", "documents", "summary"})
DOCUMENT_KEYS = frozenset(
    {
        "candidate_id",
        "status",
        "failure",
        "chunk_count",
        "source_sha256",
        "artifact",
        "chunk_set_sha256",
        "warnings",
    }
)
SUMMARY_KEYS = frozenset({"documents", "chunked", "unstructured", "failed", "chunks"})

ARTIFACT_NAME = "chunks-{}.json"
RUN_MANIFEST_NAME = "chunks-manifest.json"
PREAMBLE_LOCATION = "Documento"
LOCATION_SEPARATOR = " \u203a "


class ChunkerError(ValueError):
    """An invalid configuration or input that must abort before writing."""

    def __init__(self, failure: str) -> None:
        self.failure = failure if failure in GLOBAL_FAILURES else "internal_error"
        super().__init__(self.failure)


class DocumentFailure(Exception):
    """One document that cannot become a chunk set; the run continues."""

    def __init__(
        self,
        failure: str,
        candidate_id: str,
        source_sha256: Optional[str] = None,
        warnings: Iterable[str] = (),
    ) -> None:
        self.failure = failure if failure in FAILURES else "internal_error"
        self.candidate_id = candidate_id
        self.source_sha256 = source_sha256
        self.warnings = sorted({item for item in warnings if item in WARNINGS})
        super().__init__(self.failure)


@dataclass(frozen=True)
class Heading:
    """One explicit boundary heading line."""

    kind: str
    level: int
    text: str


@dataclass(frozen=True)
class Segment:
    """Text under one heading (or before the first heading)."""

    kind: str
    path: Tuple[str, ...]
    body: Tuple[Tuple[str, int], ...]


@dataclass(frozen=True)
class Manifest:
    """The validated parts of one parser manifest this module needs."""

    candidate_id: str
    source_sha256: str
    markdown_path: Path
    markdown_sha256: str
    markdown_bytes: int
    title: Optional[str]
    pages: Tuple[Mapping[str, Any], ...]


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


def _write_if_changed(path: Path, text: str) -> bool:
    """Write ``text`` only when the file's bytes differ; return whether it wrote."""
    payload = text.encode("utf-8")
    try:
        if path.read_bytes() == payload:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, text)
    return True


# ---------------------------------------------------------------------------------------------
# Heading scanning and segmentation
# ---------------------------------------------------------------------------------------------


def heading_of(line: str) -> Optional[Heading]:
    """Return the boundary heading on ``line``, or ``None``.

    A leading ATX marker is stripped and never required. The line must then be a
    standalone, at most 200-character ``Artículo``/``Capítulo``/``Anexo`` label
    plus a numeral and end-of-line or one of ``. : – -``. Table rows, list items,
    page markers, and every other label are not headings.
    """
    text = ATX_PATTERN.sub("", line, count=1).rstrip()
    if not text or len(text) > MAX_HEADING_CHARS:
        return None
    match = HEADING_PATTERN.match(text)
    if match is None:
        return None
    label = match.group("label").lower()
    if match.group("suffix") and not label.startswith("art"):
        return None
    kind = HEADING_KINDS.get(label[:3])
    if kind is None:
        return None
    return Heading(kind, HEADING_LEVELS[kind], text)


def _trim(
    lines: Sequence[Tuple[str, int]]
) -> Tuple[Tuple[str, int], ...]:
    start = 0
    end = len(lines)
    while start < end and not lines[start][0].strip():
        start += 1
    while end > start and not lines[end - 1][0].strip():
        end -= 1
    return tuple(lines[start:end])


def segments_of(lines: Sequence[str]) -> Tuple[List[Segment], bool]:
    """Split page-mapped Markdown into a preamble and one segment per heading.

    Page-marker lines are removed. Each heading opens a segment that ends at the
    next heading at any level, so the body never repeats the heading line. The
    second return value says whether any boundary heading exists at all.
    """
    segments: List[Segment] = []
    preamble: List[Tuple[str, int]] = []
    stack: List[Tuple[int, str]] = []
    current: Optional[Tuple[str, Tuple[str, ...], List[Tuple[str, int]]]] = None
    page: Optional[int] = None
    has_heading = False

    def close() -> None:
        if current is None:
            return
        kind, path, body = current
        trimmed = _trim(body)
        if trimmed:
            segments.append(Segment(kind, path, trimmed))

    for line in lines:
        marker = PAGE_MARKER_PATTERN.match(line)
        if marker is not None:
            page = int(marker.group(1))
            continue
        if page is None:
            # The page map is validated before scanning, so this cannot happen.
            continue
        heading = heading_of(line)
        if heading is not None:
            has_heading = True
            close()
            while stack and stack[-1][0] >= heading.level:
                stack.pop()
            stack.append((heading.level, heading.text))
            current = (heading.kind, tuple(text for _, text in stack), [])
            continue
        if current is None:
            preamble.append((line, page))
        else:
            current[2].append((line, page))
    close()
    preamble_body = _trim(preamble)
    if has_heading and preamble_body:
        segments.insert(0, Segment("preamble", (), preamble_body))
    return segments, has_heading


# ---------------------------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------------------------


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_int(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _invalid(candidate_id: str, source_sha256: Optional[str] = None) -> DocumentFailure:
    return DocumentFailure("invalid_manifest", candidate_id, source_sha256)


def _check_pages(pages: Any, page_count: int, candidate_id: str) -> None:
    if not isinstance(pages, list) or len(pages) != page_count or not pages:
        raise _invalid(candidate_id)
    previous = 0
    for item in pages:
        if not isinstance(item, dict) or set(item) != PAGE_KEYS:
            raise _invalid(candidate_id)
        page = item["page"]
        if not _is_int(item["line_start"], 1) or not _is_int(page, 1):
            raise _invalid(candidate_id)
        if not _is_int(item["line_end"], 1) or item["line_end"] < item["line_start"]:
            raise _invalid(candidate_id)
        if page <= previous:
            raise _invalid(candidate_id)
        previous = page
        if not _is_int(item["blocks"]) or not _is_int(item["tables"]):
            raise _invalid(candidate_id)
        if not isinstance(item["ocr"], bool) or not isinstance(item["empty"], bool):
            raise _invalid(candidate_id)
        if item["empty"] != (item["blocks"] == 0):
            raise _invalid(candidate_id)
        if not isinstance(item["warnings"], list) or not all(
            isinstance(value, str) and value for value in item["warnings"]
        ):
            raise _invalid(candidate_id)


def _check_manifest_payload(document: Any, candidate_id: str) -> None:
    if not isinstance(document, dict):
        raise _invalid(candidate_id)
    keys = set(document)
    if document.get("schema_version") != MANIFEST_VERSION:
        raise _invalid(candidate_id)
    if not MANIFEST_REQUIRED_KEYS <= keys <= MANIFEST_REQUIRED_KEYS | MANIFEST_OPTIONAL_KEYS:
        raise _invalid(candidate_id)
    if not isinstance(document["parser"], str) or not document["parser"]:
        raise _invalid(candidate_id)
    if not CANDIDATE_ID_PATTERN.fullmatch(str(document["candidate_id"])):
        raise _invalid(candidate_id)
    if document["title"] is not None and not isinstance(document["title"], str):
        raise _invalid(candidate_id)
    if not _is_hash(document["source_sha256"]) or not _is_hash(document["markdown_sha256"]):
        raise _invalid(candidate_id)
    if not isinstance(document["source_path"], str) or not document["source_path"]:
        raise _invalid(candidate_id)
    if not isinstance(document["markdown_path"], str) or not document["markdown_path"]:
        raise _invalid(candidate_id)
    if not isinstance(document["upstream_extractor"], str) or not document["upstream_extractor"]:
        raise _invalid(candidate_id)
    for key in ("markdown_bytes", "page_count"):
        if not _is_int(document[key], 1):
            raise _invalid(candidate_id)
    for key in ("block_count", "character_count", "table_count", "ocr_page_count"):
        if not _is_int(document[key], 0):
            raise _invalid(candidate_id)
    _check_pages(document["pages"], document["page_count"], candidate_id)

    capabilities = document["capabilities"]
    if not isinstance(capabilities, dict) or set(capabilities) != set(CAPABILITY_NAMES):
        raise _invalid(candidate_id)
    for name in CAPABILITY_NAMES:
        capability = capabilities[name]
        if not isinstance(capability, dict) or set(capability) != CAPABILITY_KEYS:
            raise _invalid(candidate_id)
        if capability["status"] not in CAPABILITY_STATUSES:
            raise _invalid(candidate_id)
        for key in ("reason", "version"):
            if capability[key] is not None and not isinstance(capability[key], str):
                raise _invalid(candidate_id)

    if not isinstance(document["warnings"], list) or not all(
        isinstance(value, str) and value for value in document["warnings"]
    ):
        raise _invalid(candidate_id)

    runtime = document["runtime"]
    if not isinstance(runtime, dict) or set(runtime) != RUNTIME_KEYS:
        raise _invalid(candidate_id)
    if runtime["profile"] not in RUNTIME_PROFILES or not _is_hash(runtime["signature"]):
        raise _invalid(candidate_id)
    if "previous_markdown_sha256" in document and not _is_hash(
        document["previous_markdown_sha256"]
    ):
        raise _invalid(candidate_id)


def load_manifest(path: Path, documents_root: Path) -> Manifest:
    """Read and strictly validate one parser manifest; fail closed."""
    directory_id = path.parent.name
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _invalid(directory_id) from error
    _check_manifest_payload(document, directory_id)

    candidate_id = document["candidate_id"]
    source_sha256 = document["source_sha256"]
    name_match = MANIFEST_NAME_PATTERN.fullmatch(path.name)
    if candidate_id != directory_id or name_match is None or name_match.group(1) != source_sha256:
        raise DocumentFailure("candidate_mismatch", directory_id, source_sha256)

    relative = Path(document["markdown_path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise _invalid(candidate_id, source_sha256)
    markdown_path = Path(documents_root) / relative
    if not _inside_directory(markdown_path, documents_root):
        raise _invalid(candidate_id, source_sha256)

    return Manifest(
        candidate_id=candidate_id,
        source_sha256=source_sha256,
        markdown_path=markdown_path,
        markdown_sha256=document["markdown_sha256"],
        markdown_bytes=document["markdown_bytes"],
        title=document["title"],
        pages=tuple(document["pages"]),
    )


def read_markdown(manifest: Manifest) -> Tuple[str, str]:
    """Load the Markdown, enforcing the byte bound and the declared hashes."""
    path = manifest.markdown_path
    try:
        if not path.is_file():
            raise DocumentFailure("missing_markdown", manifest.candidate_id, manifest.source_sha256)
        size = path.stat().st_size
    except OSError as error:
        raise DocumentFailure(
            "missing_markdown", manifest.candidate_id, manifest.source_sha256
        ) from error
    if size > MAX_MARKDOWN_BYTES:
        raise DocumentFailure(
            "size_limit_exceeded", manifest.candidate_id, manifest.source_sha256
        )
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise DocumentFailure(
            "missing_markdown", manifest.candidate_id, manifest.source_sha256
        ) from error
    if len(payload) > MAX_MARKDOWN_BYTES:
        raise DocumentFailure(
            "size_limit_exceeded", manifest.candidate_id, manifest.source_sha256
        )
    if len(payload) != manifest.markdown_bytes or _sha256(payload) != manifest.markdown_sha256:
        raise DocumentFailure(
            "markdown_hash_mismatch", manifest.candidate_id, manifest.source_sha256
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DocumentFailure(
            "markdown_hash_mismatch", manifest.candidate_id, manifest.source_sha256
        ) from error
    return text, _sha256(payload)


def check_page_map(lines: Sequence[str], pages: Sequence[Mapping[str, Any]], candidate_id: str,
                   source_sha256: str) -> None:
    """Require the page markers to agree with the manifest's line ranges."""
    markers: List[Tuple[int, int]] = []
    for index, line in enumerate(lines, start=1):
        match = PAGE_MARKER_PATTERN.match(line)
        if match is not None:
            markers.append((index, int(match.group(1))))
    if len(markers) != len(pages) or not markers or markers[0][0] != 1:
        raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)

    for position, ((line_number, page_number), meta) in enumerate(zip(markers, pages)):
        limit = markers[position + 1][0] - 1 if position + 1 < len(markers) else len(lines)
        if meta["page"] != page_number or meta["line_start"] != line_number:
            raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)
        if meta["line_end"] > limit:
            raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)
        if meta["blocks"] == 0:
            if meta["line_end"] != line_number:
                raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)
        elif not lines[meta["line_end"] - 1].strip():
            raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)
        for index in range(meta["line_end"], limit):
            if lines[index].strip():
                raise DocumentFailure("page_map_mismatch", candidate_id, source_sha256)


# ---------------------------------------------------------------------------------------------
# Catalog join
# ---------------------------------------------------------------------------------------------


def load_reviewed_catalog(path: Path) -> Tuple[Any, str]:
    """Read, hash, and validate the reviewed catalog as of ``CATALOG_AS_OF``."""
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ChunkerError("missing_catalog") from error
    try:
        document = load_catalog(Path(path))
    except CatalogReadError as error:
        raise ChunkerError("invalid_catalog") from error
    report = validate_catalog(document, as_of=CATALOG_AS_OF)
    if not report.ok:
        raise ChunkerError("invalid_catalog")
    return document, _sha256(payload)


def catalog_index(document: Any) -> Dict[str, Mapping[str, Any]]:
    """Join key ``content_sha256`` -> reviewed source, as ``change_impact`` does.

    A duplicate content hash resolves to the smallest ``source_id`` so the join
    never depends on catalog file order.
    """
    index: Dict[str, Mapping[str, Any]] = {}
    for source in document.get("sources", []):
        content = source.get("content_sha256")
        if not isinstance(content, str):
            continue
        current = index.get(content)
        if current is None or str(source.get("id")) < str(current.get("id")):
            index[content] = source
    return index


def catalog_block(source: Mapping[str, Any], catalog_sha256: str) -> Dict[str, Any]:
    """Copy only present, reviewed validity values; never derive one."""
    block: Dict[str, Any] = {
        "source_id": source["id"],
        "catalog_sha256": catalog_sha256,
    }
    for key in CATALOG_OPTIONAL_VALUES:
        if key in source:
            block[key] = source[key]
    return block


# ---------------------------------------------------------------------------------------------
# Chunk building
# ---------------------------------------------------------------------------------------------


def _chunk_text(title: str, path: Sequence[str], body: str) -> str:
    if path:
        prefix = "{} \u00b7 {}".format(_collapse(title), LOCATION_SEPARATOR.join(path))
    else:
        prefix = _collapse(title)
    return "[{}]\n\n{}".format(prefix, body)


def build_chunk_set(
    manifest: Manifest,
    markdown_sha256: str,
    segments: Sequence[Segment],
    *,
    title: str,
    source: Optional[Mapping[str, Any]],
    catalog_sha256: str,
    warnings: Set[str],
) -> Dict[str, Any]:
    """Build the ``legal-chunk-set-v1`` document for one parsed document."""
    source_id = str(source["id"]) if source is not None else None
    id_prefix = source_id if source_id is not None else "cand-{}".format(
        manifest.source_sha256[:12]
    )
    chunks: List[Dict[str, Any]] = []
    for ordinal, segment in enumerate(segments, start=1):
        body = "\n".join(line for line, _ in segment.body)
        text = _chunk_text(title, segment.path, body)
        if len(text) > CHUNK_SOFT_LIMIT:
            warnings.add("chunk_over_soft_limit")
        chunks.append(
            {
                "id": "{}-{:04d}".format(id_prefix, ordinal),
                "candidate_id": manifest.candidate_id,
                "source_sha256": manifest.source_sha256,
                "markdown_sha256": markdown_sha256,
                "heading_path": list(segment.path),
                "location": (
                    LOCATION_SEPARATOR.join(segment.path)
                    if segment.path
                    else PREAMBLE_LOCATION
                ),
                "page_start": min(page for _, page in segment.body),
                "page_end": max(page for _, page in segment.body),
                "character_count": len(text),
                "text": text,
            }
        )
    chunk_set: Dict[str, Any] = {
        "schema_version": CHUNK_SET_VERSION,
        "chunker": CHUNKER,
        "input": {
            "candidate_id": manifest.candidate_id,
            "source_sha256": manifest.source_sha256,
            "markdown_sha256": markdown_sha256,
            "title": _collapse(title),
        },
        "validity_status": "known" if source is not None else "unknown",
        "chunk_count": len(chunks),
        "chunks": chunks,
        "warnings": sorted(warnings),
    }
    if source is not None:
        chunk_set["catalog"] = catalog_block(source, catalog_sha256)
    return chunk_set


# ---------------------------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------------------------


def _outcome(
    candidate_id: str,
    status: str,
    failure: Optional[str],
    chunk_count: int,
    source_sha256: Optional[str],
    artifact: Optional[str],
    chunk_set_sha256: Optional[str],
    warnings: Iterable[str] = (),
) -> Dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "status": status,
        "failure": failure,
        "chunk_count": chunk_count,
        "source_sha256": source_sha256,
        "artifact": artifact,
        "chunk_set_sha256": chunk_set_sha256,
        "warnings": sorted({item for item in warnings if item in WARNINGS}),
    }


def _chunk_document(
    manifest_path: Path,
    documents_root: Path,
    output_root: Path,
    index: Mapping[str, Mapping[str, Any]],
    catalog_sha256: str,
) -> Tuple[Dict[str, Any], bool]:
    """Chunk one document; raise ``DocumentFailure`` for that document only."""
    manifest = load_manifest(manifest_path, documents_root)
    markdown, markdown_sha256 = read_markdown(manifest)
    lines = markdown.splitlines()
    check_page_map(lines, manifest.pages, manifest.candidate_id, manifest.source_sha256)

    source = index.get(manifest.source_sha256)
    title = _collapse(source["title"] if source is not None else (manifest.title or ""))
    if not title:
        raise DocumentFailure("missing_title", manifest.candidate_id, manifest.source_sha256)

    segments, has_heading = segments_of(lines)
    warnings: Set[str] = set()
    if source is None:
        warnings.add("catalog_source_unknown")
    if not has_heading:
        warnings.add("no_structure_headings")
        return _outcome(
            manifest.candidate_id,
            "unstructured",
            None,
            0,
            manifest.source_sha256,
            None,
            None,
            warnings,
        )
    if len(segments) > MAX_CHUNKS:
        raise DocumentFailure(
            "chunk_limit_exceeded", manifest.candidate_id, manifest.source_sha256, warnings
        )

    chunk_set = build_chunk_set(
        manifest,
        markdown_sha256,
        segments,
        title=title,
        source=source,
        catalog_sha256=catalog_sha256,
        warnings=warnings,
    )
    payload = _canonical_json(chunk_set)
    relative = "{}/{}".format(
        manifest.candidate_id, ARTIFACT_NAME.format(manifest.source_sha256)
    )
    _write_if_changed(Path(output_root) / relative, payload)
    return _outcome(
        manifest.candidate_id,
        "chunked",
        None,
        chunk_set["chunk_count"],
        manifest.source_sha256,
        relative,
        _sha256(payload.encode("utf-8")),
        chunk_set["warnings"],
    )


def _find_manifests(documents_root: Path) -> List[Path]:
    try:
        directories = sorted(path for path in Path(documents_root).iterdir() if path.is_dir())
    except OSError as error:
        raise ChunkerError("missing_documents_root") from error
    found: List[Path] = []
    for directory in directories:
        found.extend(sorted(directory.glob("parse-*.json")))
    return found


def chunk_documents(
    documents_dir: Path,
    catalog_path: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """Chunk every parser artifact under ``documents_dir`` into ``output_dir``.

    Configuration and catalog errors raise ``ChunkerError`` before anything is
    written. A per-document failure is recorded and never aborts the run, and it
    never touches that candidate's previous artifact.
    """
    documents_root = Path(documents_dir)
    catalog_file = Path(catalog_path)
    output_root = Path(output_dir)

    if _inside_directory(output_root, KNOWLEDGE_ROOT):
        raise ChunkerError("unsafe_output_root")
    try:
        same_as_documents = output_root.resolve() == documents_root.resolve()
    except OSError as error:
        raise ChunkerError("unsafe_output_root") from error
    if same_as_documents or _inside_directory(output_root, documents_root):
        raise ChunkerError("unsafe_output_root")

    if not documents_root.is_dir():
        raise ChunkerError("missing_documents_root")

    catalog, catalog_sha256 = load_reviewed_catalog(catalog_file)
    index = catalog_index(catalog)

    manifest_paths = _find_manifests(documents_root)
    if len(manifest_paths) > MAX_DOCUMENTS:
        raise ChunkerError("manifest_count_exceeded")

    output_root.mkdir(parents=True, exist_ok=True)

    outcomes: list = []
    for manifest_path in manifest_paths:
        directory_id = manifest_path.parent.name
        try:
            outcome = _chunk_document(
                manifest_path, documents_root, output_root, index, catalog_sha256
            )
        except DocumentFailure as error:
            outcome = _outcome(
                error.candidate_id,
                "failed",
                error.failure,
                0,
                error.source_sha256,
                None,
                None,
                error.warnings,
            )
        except Exception:
            outcome = _outcome(directory_id, "failed", "internal_error", 0, None, None, None)
        outcomes.append(outcome)

    outcomes.sort(
        key=lambda item: (item["candidate_id"], item["source_sha256"] or "", item["failure"] or "")
    )
    summary = {
        "documents": len(outcomes),
        "chunked": sum(1 for item in outcomes if item["status"] == "chunked"),
        "unstructured": sum(1 for item in outcomes if item["status"] == "unstructured"),
        "failed": sum(1 for item in outcomes if item["status"] == "failed"),
        "chunks": sum(item["chunk_count"] for item in outcomes),
    }
    manifest = {
        "schema_version": CHUNK_MANIFEST_VERSION,
        "chunker": CHUNKER,
        "documents": outcomes,
        "summary": summary,
    }
    _write_if_changed(output_root / RUN_MANIFEST_NAME, _canonical_json(manifest))

    return {
        "run": {
            "chunker": CHUNKER,
            "chunk_set_version": CHUNK_SET_VERSION,
            "manifest_version": CHUNK_MANIFEST_VERSION,
        },
        "catalog": str(catalog_file),
        "documents_root": str(documents_root),
        "output": str(output_root),
        "documents": outcomes,
        "summary": summary,
    }


# ---------------------------------------------------------------------------------------------
# Contract check (no jsonschema dependency: this module stays standard-library only)
# ---------------------------------------------------------------------------------------------


def check_contract(schema_path: Path = SCHEMA_PATH) -> List[str]:
    """Check the committed schema against this module's constants.

    Returns a list of human-readable problems; an empty list means the readable
    contract and the code agree.
    """
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["chunk schema is not readable JSON: {}".format(schema_path)]

    problems: List[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    defs = schema.get("$defs") if isinstance(schema, dict) else None
    if not isinstance(defs, dict):
        return ["chunk schema has no $defs object"]

    def definition(name: str) -> Mapping[str, Any]:
        value = defs.get(name)
        return value if isinstance(value, dict) else {}

    chunk_set = definition("chunk_set")
    expect(set(chunk_set.get("required", ())) == CHUNK_SET_REQUIRED_KEYS,
           "chunk_set requires {} keys".format(len(CHUNK_SET_REQUIRED_KEYS)))
    expect(
        set(chunk_set.get("properties", {})) == CHUNK_SET_REQUIRED_KEYS | CHUNK_SET_OPTIONAL_KEYS,
        "chunk_set properties disagree with the module",
    )
    expect(
        (chunk_set.get("properties", {}).get("schema_version") or {}).get("const")
        == CHUNK_SET_VERSION,
        "chunk_set schema_version constant differs",
    )
    expect(
        (chunk_set.get("properties", {}).get("chunker") or {}).get("const") == CHUNKER,
        "chunk_set chunker constant differs",
    )
    expect(
        set((chunk_set.get("properties", {}).get("validity_status") or {}).get("enum", ()))
        == {"known", "unknown"},
        "chunk_set validity_status enum differs",
    )

    expect(set(definition("input").get("required", ())) == CHUNK_INPUT_KEYS,
           "input requires different keys")
    expect(set(definition("chunk").get("required", ())) == CHUNK_KEYS,
           "chunk requires different keys")
    expect(set(definition("catalog").get("required", ())) == {"source_id", "catalog_sha256"},
           "catalog block requires different keys")
    expect(set(definition("catalog").get("properties", {})) == set(CATALOG_BLOCK_KEYS),
           "catalog block properties disagree with the module")
    expect(set(definition("catalog").get("properties", {}).get("applicability", {}).get(
        "properties", {})) == APPLICABILITY_KEYS, "catalog applicability keys disagree")

    manifest = definition("manifest")
    expect(set(manifest.get("required", ())) == RUN_MANIFEST_REQUIRED_KEYS,
           "manifest requires different keys")
    expect(
        (manifest.get("properties", {}).get("schema_version") or {}).get("const")
        == CHUNK_MANIFEST_VERSION,
        "manifest schema_version constant differs",
    )
    expect(
        (manifest.get("properties", {}).get("chunker") or {}).get("const") == CHUNKER,
        "manifest chunker constant differs",
    )
    expect(set(definition("document").get("required", ())) == DOCUMENT_KEYS,
           "document requires different keys")
    expect(set(definition("summary").get("required", ())) == SUMMARY_KEYS,
           "summary requires different keys")
    expect(tuple(definition("status").get("enum", ())) == STATUSES,
           "status enum differs from the module")
    expect(set(definition("failure").get("enum", ())) == FAILURES,
           "failure code enum differs from the module")
    expect(set(definition("warning").get("enum", ())) == WARNINGS,
           "warning code enum differs from the module")

    return problems


def contract_line() -> str:
    return (
        "legal chunk contract OK: {} + {}, chunker {}, {} failure codes, "
        "{} warning codes.".format(
            CHUNK_SET_VERSION,
            CHUNK_MANIFEST_VERSION,
            CHUNKER,
            len(FAILURES),
            len(WARNINGS),
        )
    )
