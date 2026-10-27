"""Fetch and parse pending official-publication candidates into quarantine.

This module consumes the pending candidates written by
``app/source_discovery.py`` (or an explicit monitoring state) and turns the
safely retrievable ones into *quarantined* documents with provenance.

Boundaries:

- only candidates whose declared issuer and exact HTTPS host are on the
  approved allowlist of ``app/source_catalog.py`` are fetched;
- a redirect is followed only when it stays on HTTPS and on an exact host
  approved for the same issuer, at most ``MAX_REDIRECTS`` times; any other
  redirect, non-200 response, oversize payload, unsupported content type,
  body/type mismatch, or undecodable document fails that candidate closed;
- the original bytes and their SHA-256 are preserved, together with the
  discovery provenance (registry/observation version hash) and the parser
  version;
- extracted text keeps page (PDF) or section (HTML) locations, and PDF text
  uses an embedded font's ``ToUnicode`` map when the document provides one;
- the canonical ``knowledge/source_catalog.json`` and
  ``knowledge/passages.json`` are never read or written, and no run makes a
  candidate answerable. OCR is not attempted; a document without an embedded
  text layer is reported as ``no_extractable_text``.

Standard-library only. Failure records use fixed category strings and never
copy upstream exception text, document text, or personal data.
"""

import copy
import hashlib
import html.parser
import json
import os
import re
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit

from app.source_catalog import ISSUER_ALLOWED_HOSTS

STATE_VERSION = "official-ingestion-state-v1"
DISCOVERY_STATE_VERSION = "official-discovery-state-v1"
MONITOR_STATE_VERSION = "source-monitor-state-v1"
EXTRACTED_DOCUMENT_VERSION = "official-ingestion-document-v1"
EXTRACTOR = "manijero-document-extractor-v1"

MAX_CANDIDATES = 1000
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_PDF_OBJECTS = 20000
MAX_PDF_PAGES = 500
MAX_TEXT_BLOCKS = 5000
MAX_TEXT_CHARS = 2000000
MAX_ATTEMPTS_PER_CANDIDATE = 50
MAX_FONTS_PER_PAGE = 200
MAX_CMAP_ENTRIES = 65536
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 15
USER_AGENT = "Manijero-Official-Document-Ingestion/1.0"

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml+xml": "html",
}
HTML_CHARSETS = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "us-ascii": "ascii",
    "ascii": "ascii",
    "iso-8859-1": "iso-8859-1",
    "latin-1": "iso-8859-1",
    "windows-1252": "cp1252",
    "cp1252": "cp1252",
}

CANDIDATE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REGISTRY_URL_PATTERN = re.compile(r"^https://[^\s]+$")

# Fixed, value-free failure categories. They are stable for operators and tests.
FAILURES = frozenset(
    {
        "unsupported_candidate",
        "unsafe_destination",
        "duplicate_candidate",
        "duplicate_content",
        "redirect_rejected",
        "http_error",
        "unavailable_upstream",
        "size_limit_exceeded",
        "unsupported_content_type",
        "content_type_mismatch",
        "unsupported_pdf_encoding",
        "malformed_document",
        "no_extractable_text",
        "internal_error",
    }
)

CANDIDATE_RECORD_KEYS = frozenset(
    {
        "candidate_id",
        "issuer",
        "registry_id",
        "registry_url",
        "publication_url",
        "title",
        "stable_identity",
        "version_hash",
        "review_status",
        "status",
        "failure",
        "last_attempt_at",
        "last_success_at",
        "original_sha256",
        "byte_size",
        "declared_content_type",
        "media_type",
        "extractor",
        "extracted_text_sha256",
        "page_count",
        "block_count",
        "original_path",
        "extracted_path",
        "previous_original_sha256",
        "attempts",
    }
)

REQUIRED_RECORD_KEYS = frozenset(
    {
        "candidate_id",
        "issuer",
        "registry_id",
        "registry_url",
        "publication_url",
        "title",
        "stable_identity",
        "version_hash",
        "review_status",
        "status",
        "failure",
        "last_attempt_at",
        "last_success_at",
        "attempts",
    }
)


class IngestionError(ValueError):
    """An invalid configuration, state, or document that must fail closed."""

    def __init__(self, failure: str) -> None:
        if failure not in FAILURES and failure not in (
            "invalid_discovery_state",
            "invalid_monitoring_state",
            "invalid_ingestion_state",
            "candidate_count_exceeded",
            "unsafe_workspace",
        ):
            failure = "internal_error"
        self.failure = failure
        super().__init__(failure)


@dataclass(frozen=True)
class FetchedDocument:
    """Bytes and transport metadata of one accepted HTTP response."""

    payload: bytes
    declared_content_type: str
    charset: Optional[str]


@dataclass(frozen=True)
class ExtractedDocument:
    """Parsed text blocks and optional document title."""

    media_type: str
    title: Optional[str]
    blocks: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class _PDFFont:
    """One PDF font resource: optional ToUnicode map and code width."""

    cmap: Optional[Dict[int, str]]
    code_bytes: int = 1


class _AllowlistedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow bounded HTTPS redirects only inside one issuer's approved hosts."""

    def __init__(self, allowed_hosts: Iterable[str]) -> None:
        super().__init__()
        self._allowed_hosts = frozenset(allowed_hosts)
        self._followed = 0

    def redirect_request(self, request, response, code, message, headers, new_url):
        if self._followed >= MAX_REDIRECTS or not _url_allowed(new_url, self._allowed_hosts):
            raise IngestionError("redirect_rejected")
        self._followed += 1
        return super().redirect_request(request, response, code, message, headers, new_url)


class _HTMLExtractor(html.parser.HTMLParser):
    """Collect headings and text blocks while preserving section hierarchy."""

    SKIPPED_ELEMENTS = frozenset({"script", "style", "template", "noscript"})
    BLOCK_ELEMENTS = frozenset(
        {"p", "li", "blockquote", "td", "th", "dd", "dt", "figcaption", "pre", "div", "section", "article"}
    )
    HEADING_ELEMENTS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: List[Dict[str, Any]] = []
        self.title = ""
        self._buffer: List[str] = []
        self._kind = ""
        self._heading_level = 0
        self._headings: List[Tuple[int, str]] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        name = tag.lower()
        if name in self.SKIPPED_ELEMENTS:
            self._skip_depth += 1
            return
        if name == "title":
            self._in_title = True
            return
        if self._skip_depth:
            return
        if name in self.HEADING_ELEMENTS:
            self._flush()
            self._kind = "heading"
            self._heading_level = int(name[1])
            return
        if name in self.BLOCK_ELEMENTS:
            self._flush()
            self._kind = "text"
        elif name == "br":
            self._buffer.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        name = tag.lower()
        if name in self.SKIPPED_ELEMENTS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if name == "title":
            self._in_title = False
            return
        if self._skip_depth:
            return
        if name in self.HEADING_ELEMENTS:
            self._flush()
            self._heading_level = 0
            return
        if name in self.BLOCK_ELEMENTS:
            self._flush()
            self._kind = ""

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._skip_depth:
            return
        self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if not text or not self._kind:
            return
        if self._kind == "heading":
            self._headings = [item for item in self._headings if item[0] < self._heading_level]
            self._headings.append((self._heading_level, text))
            section = " > ".join(item[1] for item in self._headings)
            self.blocks.append({"kind": "heading", "page": None, "section": section, "text": text})
            self._kind = ""
            return
        section = " > ".join(item[1] for item in self._headings) if self._headings else "Documento"
        self.blocks.append({"kind": "text", "page": None, "section": section, "text": text})


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _now(now: Optional[datetime]) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _inside_directory(path: Path, directory: Path) -> bool:
    """Return True when ``path`` resolves inside ``directory``."""
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _load_json(path: Path, failure: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IngestionError(failure) from error


def load_discovery_candidates(path: Path) -> List[Dict[str, Any]]:
    """Load and structurally validate the pending discovery candidates."""
    state = _load_json(path, "invalid_discovery_state")
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != DISCOVERY_STATE_VERSION
        or not isinstance(state.get("candidates"), dict)
        or not isinstance(state.get("registries"), dict)
    ):
        raise IngestionError("invalid_discovery_state")
    required = ("candidate_id", "issuer", "registry_id", "registry_url", "publication_url", "title",
                "stable_identity", "version_hash", "review_status")
    candidates = []
    for candidate_id, candidate in state["candidates"].items():
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            raise IngestionError("invalid_discovery_state")
        if not isinstance(candidate, dict) or candidate.get("candidate_id") != candidate_id:
            raise IngestionError("invalid_discovery_state")
        if not all(isinstance(candidate.get(key), str) for key in required):
            raise IngestionError("invalid_discovery_state")
        candidates.append({key: candidate[key] for key in required})
    if len(candidates) > MAX_CANDIDATES:
        raise IngestionError("candidate_count_exceeded")
    return sorted(candidates, key=lambda item: item["candidate_id"])


def load_monitoring_sources(path: Path) -> List[Dict[str, str]]:
    """Load monitoring state and report its document-level coverage gap.

    Monitoring snapshots feed responses only; it retains no publication
    document URL. It therefore contributes zero fetchable candidates, and the
    gap is surfaced instead of guessing documents from a feed.
    """
    state = _load_json(path, "invalid_monitoring_state")
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != MONITOR_STATE_VERSION
        or not isinstance(state.get("sources"), dict)
    ):
        raise IngestionError("invalid_monitoring_state")
    if any(not isinstance(source_id, str) for source_id in state["sources"]):
        raise IngestionError("invalid_monitoring_state")
    return [
        {"id": source_id, "status": "unchecked", "failure": "no_document_candidates"}
        for source_id in sorted(state["sources"])
    ]


def _load_state(path: Path) -> Dict[str, Any]:
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": STATE_VERSION, "candidates": {}}
    except (OSError, json.JSONDecodeError) as error:
        raise IngestionError("invalid_ingestion_state") from error
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != STATE_VERSION
        or not isinstance(state.get("candidates"), dict)
    ):
        raise IngestionError("invalid_ingestion_state")
    for candidate_id, record in state["candidates"].items():
        if not isinstance(candidate_id, str) or not CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            raise IngestionError("invalid_ingestion_state")
        if not isinstance(record, dict) or not set(record).issubset(CANDIDATE_RECORD_KEYS):
            raise IngestionError("invalid_ingestion_state")
        if not REQUIRED_RECORD_KEYS.issubset(record):
            raise IngestionError("invalid_ingestion_state")
        if (
            record.get("candidate_id") != candidate_id
            or record.get("review_status") != "pending"
            or record.get("status") not in ("extracted", "failed", "rejected")
            or not isinstance(record.get("attempts"), list)
            or not isinstance(record.get("version_hash"), str)
            or not isinstance(record.get("publication_url"), str)
            or not isinstance(record.get("issuer"), str)
        ):
            raise IngestionError("invalid_ingestion_state")
    return state


def _url_allowed(url: Any, allowed_hosts: Iterable[str]) -> bool:
    """Return True only for an HTTPS URL on one exact approved host.

    Credentials, non-443 ports, the site root, and fragments are never fetched.
    """
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and host in allowed_hosts
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and (parsed.path or "") not in ("", "/")
        and not parsed.fragment
    )


def _destination_failure(candidate: Dict[str, Any]) -> Optional[str]:
    """Return a fixed failure category when the candidate may not be fetched."""
    if candidate.get("review_status") != "pending":
        return "unsupported_candidate"
    issuer = candidate.get("issuer")
    if issuer not in ISSUER_ALLOWED_HOSTS:
        return "unsupported_candidate"
    if not isinstance(candidate.get("title"), str) or not candidate["title"].strip():
        return "unsupported_candidate"
    if not isinstance(candidate.get("stable_identity"), str) or not candidate["stable_identity"].strip():
        return "unsupported_candidate"
    if not isinstance(candidate.get("version_hash"), str) or not SHA256_PATTERN.fullmatch(candidate["version_hash"]):
        return "unsupported_candidate"
    registry_url = candidate.get("registry_url")
    if not isinstance(registry_url, str) or not REGISTRY_URL_PATTERN.fullmatch(registry_url):
        return "unsupported_candidate"
    if not _url_allowed(candidate.get("publication_url"), ISSUER_ALLOWED_HOSTS[issuer]):
        return "unsafe_destination"
    return None


def candidate_admission_issue(candidate: Dict[str, Any]) -> Optional[str]:
    """Return the fixed admission failure for a candidate record, if any.

    Public, network-free seam: review preparation reuses the one approved-host
    admission policy instead of duplicating the allowlist. This function never
    fetches anything.
    """
    return _destination_failure(candidate)


def _fetch(publication_url: str, allowed_hosts: Iterable[str]) -> FetchedDocument:
    """Fetch one allowed URL, following only bounded same-issuer HTTPS redirects."""
    allowed = frozenset(allowed_hosts)
    if not _url_allowed(publication_url, allowed):
        raise IngestionError("unsafe_destination")
    request = urllib.request.Request(
        publication_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf, text/html;q=0.9"},
    )
    opener = urllib.request.build_opener(_AllowlistedRedirect(allowed))
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except IngestionError:
        raise
    except urllib.error.HTTPError as error:
        raise IngestionError("http_error") from error
    except (urllib.error.URLError, OSError) as error:
        raise IngestionError("unavailable_upstream") from error
    with response:
        if not _url_allowed(response.geturl(), allowed):
            raise IngestionError("redirect_rejected")
        if response.status != 200:
            raise IngestionError("http_error")
        headers = response.headers
        payload = response.read(MAX_DOCUMENT_BYTES + 1)
        declared_content_type = headers.get_content_type()
        charset = headers.get_content_charset()
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise IngestionError("size_limit_exceeded")
    if not payload:
        raise IngestionError("malformed_document")
    return FetchedDocument(payload, declared_content_type, charset)


def _sniff_media_type(payload: bytes) -> Optional[str]:
    head = payload[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"%PDF-"):
        return "pdf"
    lowered = head.lower()
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html") or lowered.startswith(b"<head"):
        return "html"
    return None


def _sniff_media_type_lenient(payload: bytes) -> Optional[str]:
    sniffed = _sniff_media_type(payload)
    if sniffed is not None:
        return sniffed
    lowered = payload[:4096].lower()
    return "html" if b"<html" in lowered or b"<body" in lowered or b"<p" in lowered else None


def _classify(fetched: FetchedDocument) -> str:
    expected = ALLOWED_CONTENT_TYPES.get(fetched.declared_content_type)
    if expected is None:
        raise IngestionError("unsupported_content_type")
    sniffed = _sniff_media_type_lenient(fetched.payload)
    if sniffed != expected:
        raise IngestionError("content_type_mismatch")
    return expected


def _decode_html(fetched: FetchedDocument) -> str:
    codec = HTML_CHARSETS.get((fetched.charset or "").lower())
    if codec:
        try:
            return fetched.payload.decode(codec)
        except UnicodeDecodeError as error:
            raise IngestionError("malformed_document") from error
    try:
        return fetched.payload.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return fetched.payload.decode("cp1252")
    except UnicodeDecodeError as error:
        raise IngestionError("malformed_document") from error


def _extract_html(fetched: FetchedDocument) -> ExtractedDocument:
    parser = _HTMLExtractor()
    try:
        parser.feed(_decode_html(fetched))
        parser.close()
    except IngestionError:
        raise
    except Exception as error:
        raise IngestionError("malformed_document") from error
    blocks = _finalize_blocks(parser.blocks)
    title = " ".join(parser.title.split()) or None
    return ExtractedDocument("html", title, blocks)


_PDF_OBJECT_PATTERN = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b")
_PDF_STREAM_PATTERN = re.compile(rb"stream\r?\n")
_PDF_FILTER_PATTERN = re.compile(rb"/([A-Za-z0-9]+Decode)")
_PDF_PAGE_TYPE = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_PDF_PAGES_TYPE = re.compile(rb"/Type\s*/Pages(?![A-Za-z])")
_PDF_CATALOG_TYPE = re.compile(rb"/Type\s*/Catalog(?![A-Za-z])")


def _pdf_objects(payload: bytes) -> Dict[int, bytes]:
    objects: Dict[int, bytes] = {}
    position = 0
    while len(objects) < MAX_PDF_OBJECTS:
        match = _PDF_OBJECT_PATTERN.search(payload, position)
        if match is None:
            break
        end = payload.find(b"endobj", match.end())
        if end < 0:
            raise IngestionError("malformed_document")
        objects[int(match.group(1))] = payload[match.end():end]
        position = end + len(b"endobj")
    if len(objects) >= MAX_PDF_OBJECTS and _PDF_OBJECT_PATTERN.search(payload, position) is not None:
        raise IngestionError("size_limit_exceeded")
    if not objects:
        raise IngestionError("malformed_document")
    return objects


def _pdf_refs(body: bytes, key: bytes) -> List[int]:
    array = re.search(rb"/" + key + rb"\s*\[([^\]]*)\]", body)
    if array is not None:
        return [int(number) for number, _ in re.findall(rb"(\d+)\s+(\d+)\s+R", array.group(1))]
    single = re.search(rb"/" + key + rb"\s+(\d+)\s+(\d+)\s+R", body)
    return [int(single.group(1))] if single is not None else []


_PDF_OBJSTM_TYPE = re.compile(rb"/Type\s*/ObjStm(?![A-Za-z])")


def _pdf_expand_object_streams(objects: Dict[int, bytes]) -> Dict[int, bytes]:
    """Unpack PDF 1.5 object streams so referenced fonts/streams are resolvable."""
    additions: Dict[int, bytes] = {}
    for body in list(objects.values()):
        match = _PDF_OBJSTM_TYPE.search(body)
        if match is None:
            continue
        stream = _pdf_stream(body)
        if stream is None:
            raise IngestionError("malformed_document")
        dictionary, payload = stream
        count = re.search(rb"/N\s+(\d+)", dictionary)
        first = re.search(rb"/First\s+(\d+)", dictionary)
        if count is None or first is None:
            raise IngestionError("malformed_document")
        number_of_objects, first_offset = int(count.group(1)), int(first.group(1))
        if number_of_objects < 0 or number_of_objects > MAX_PDF_OBJECTS:
            raise IngestionError("malformed_document")
        data = _pdf_decode_stream(dictionary, payload)
        if first_offset > len(data):
            raise IngestionError("malformed_document")
        header = data[:first_offset].split()
        if len(header) < 2 * number_of_objects:
            raise IngestionError("malformed_document")
        pairs = [
            (int(header[index]), int(header[index + 1]))
            for index in range(0, 2 * number_of_objects, 2)
        ]
        for index, (number, offset) in enumerate(pairs):
            start = first_offset + offset
            end = first_offset + pairs[index + 1][1] if index + 1 < len(pairs) else len(data)
            if start > end or end > len(data):
                raise IngestionError("malformed_document")
            additions.setdefault(number, data[start:end])
    if len(objects) + len(additions) > MAX_PDF_OBJECTS:
        raise IngestionError("size_limit_exceeded")
    for number, body in additions.items():
        objects.setdefault(number, body)
    return objects


def _pdf_pages(objects: Dict[int, bytes]) -> List[int]:
    pages: List[int] = []
    catalog = next((body for body in objects.values() if _PDF_CATALOG_TYPE.search(body)), None)
    visited = set()

    def add_page(number: int) -> None:
        if len(pages) >= MAX_PDF_PAGES:
            raise IngestionError("size_limit_exceeded")
        pages.append(number)

    def walk(number: int, depth: int) -> None:
        if depth > 32 or number in visited or number not in objects:
            return
        visited.add(number)
        body = objects[number]
        if _PDF_PAGE_TYPE.search(body):
            add_page(number)
            return
        if _PDF_PAGES_TYPE.search(body):
            for child in _pdf_refs(body, b"Kids"):
                walk(child, depth + 1)

    if catalog is not None:
        for root in _pdf_refs(catalog, b"Pages")[:1]:
            walk(root, 0)
    if not pages:
        for number in sorted(number for number, body in objects.items() if _PDF_PAGE_TYPE.search(body)):
            add_page(number)
    return pages


def _pdf_stream(body: bytes) -> Optional[Tuple[bytes, bytes]]:
    match = _PDF_STREAM_PATTERN.search(body)
    if match is None:
        return None
    dictionary = body[:match.start()]
    rest = body[match.end():]
    end = rest.find(b"endstream")
    if end < 0:
        raise IngestionError("malformed_document")
    payload = rest[:end]
    if payload.endswith(b"\n"):
        payload = payload[:-1]
    if payload.endswith(b"\r"):
        payload = payload[:-1]
    return dictionary, payload


def _pdf_decode_stream(dictionary: bytes, payload: bytes) -> bytes:
    filters = [name for name in _PDF_FILTER_PATTERN.findall(dictionary)]
    if not filters:
        return payload
    if filters != [b"FlateDecode"]:
        raise IngestionError("unsupported_pdf_encoding")
    try:
        decompressor = zlib.decompressobj()
        data = decompressor.decompress(payload, MAX_DECOMPRESSED_BYTES + 1)
        if len(data) > MAX_DECOMPRESSED_BYTES or decompressor.unconsumed_tail:
            raise IngestionError("size_limit_exceeded")
        data += decompressor.flush()
    except zlib.error as error:
        raise IngestionError("malformed_document") from error
    if len(data) > MAX_DECOMPRESSED_BYTES:
        raise IngestionError("size_limit_exceeded")
    return data


def _pdf_inline_dict(body: bytes, key: bytes) -> Optional[bytes]:
    """Return the balanced ``<<...>>`` value following ``/key``."""
    match = re.search(rb"/" + key + rb"\s*<<", body)
    if match is None:
        return None
    start = match.end() - 2
    depth = 0
    position = start
    while position < len(body) - 1:
        pair = body[position:position + 2]
        if pair == b"<<":
            depth += 1
            position += 2
        elif pair == b">>":
            depth -= 1
            position += 2
            if depth == 0:
                return body[start:position]
        else:
            position += 1
    raise IngestionError("malformed_document")


def _pdf_resources(page_body: bytes, objects: Dict[int, bytes]) -> Optional[bytes]:
    """Resolve a page's resources, following the parent chain when inherited."""
    body = page_body
    for _ in range(8):
        references = _pdf_refs(body, b"Resources")
        if references:
            return objects.get(references[0])
        inline = _pdf_inline_dict(body, b"Resources")
        if inline is not None:
            return inline
        parents = _pdf_refs(body, b"Parent")
        if not parents:
            return None
        body = objects.get(parents[0], b"")
    return None


def _pdf_destination(hex_value: str) -> str:
    if len(hex_value) % 2:
        hex_value += "0"
    raw = bytes.fromhex(hex_value)
    if not raw:
        return ""
    if len(raw) % 2:
        return chr(int.from_bytes(raw, "big"))
    return raw.decode("utf-16-be", errors="replace")


def _pdf_increment(text: str, offset: int) -> str:
    if not text or offset == 0:
        return text
    return text[:-1] + chr(ord(text[-1]) + offset)


def _pdf_parse_cmap(text: str) -> Tuple[Optional[Dict[int, str]], int]:
    """Parse a ToUnicode CMap into ``code -> text`` and its code width."""
    code_bytes = 1
    codespace = re.search(r"begincodespacerange(.*?)endcodespacerange", text, re.S)
    if codespace is not None:
        values = re.findall(r"<([0-9A-Fa-f]+)>", codespace.group(1))
        widths = {max(1, len(value) // 2) for value in values}
        code_bytes = max(widths) if widths else 1
    if code_bytes > 4:
        raise IngestionError("unsupported_pdf_encoding")

    mapping: Dict[int, str] = {}

    def add(code: int, value: str) -> None:
        if len(mapping) >= MAX_CMAP_ENTRIES:
            raise IngestionError("size_limit_exceeded")
        mapping[code] = value

    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for source, destination in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            add(int(source, 16), _pdf_destination(destination))

    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        cleaned = block
        for match in re.finditer(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.S
        ):
            low, high = int(match.group(1), 16), int(match.group(2), 16)
            destinations = re.findall(r"<([0-9A-Fa-f]+)>", match.group(3))
            for offset, code in enumerate(range(low, high + 1)):
                if offset >= len(destinations):
                    break
                add(code, _pdf_destination(destinations[offset]))
            cleaned = cleaned.replace(match.group(0), " ")
        for match in re.finditer(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", cleaned
        ):
            low, high = int(match.group(1), 16), int(match.group(2), 16)
            base = _pdf_destination(match.group(3))
            for offset, code in enumerate(range(low, high + 1)):
                add(code, _pdf_increment(base, offset))
    return (mapping or None), code_bytes


def _pdf_fonts(resources: Optional[bytes], objects: Dict[int, bytes]) -> Dict[str, _PDFFont]:
    """Resolve ``/Font`` resource names to their optional ToUnicode maps."""
    if resources is None:
        return {}
    references = _pdf_refs(resources, b"Font")
    font_dict = objects.get(references[0]) if references else _pdf_inline_dict(resources, b"Font")
    if font_dict is None:
        return {}
    fonts: Dict[str, _PDFFont] = {}
    for name, number in re.findall(rb"/([^\s/<>\[\]()]+)\s+(\d+)\s+\d+\s+R", font_dict):
        if len(fonts) >= MAX_FONTS_PER_PAGE:
            raise IngestionError("size_limit_exceeded")
        body = objects.get(int(number), b"")
        cmap: Optional[Dict[int, str]] = None
        code_bytes = 1
        unicode_refs = _pdf_refs(body, b"ToUnicode")
        if unicode_refs:
            stream = _pdf_stream(objects.get(unicode_refs[0], b""))
            if stream is None:
                raise IngestionError("malformed_document")
            dictionary, payload = stream
            decoded = _pdf_decode_stream(dictionary, payload).decode("latin-1")
            cmap, code_bytes = _pdf_parse_cmap(decoded)
        fonts[name.decode("latin-1")] = _PDFFont(cmap, code_bytes)
    return fonts



_PDF_ESCAPES = {0x6E: b"\n", 0x72: b"\r", 0x74: b"\t", 0x62: b"\b", 0x66: b"\f",
                0x28: b"(", 0x29: b")", 0x5C: b"\\"}


def _pdf_literal(stream: bytes, position: int) -> Tuple[bytes, int]:
    output = bytearray()
    depth = 1
    while position < len(stream):
        byte = stream[position]
        if byte == 0x5C:
            position += 1
            if position >= len(stream):
                break
            escaped = stream[position]
            if escaped in _PDF_ESCAPES:
                output += _PDF_ESCAPES[escaped]
                position += 1
            elif escaped in (0x0D, 0x0A):
                if escaped == 0x0D and position + 1 < len(stream) and stream[position + 1] == 0x0A:
                    position += 2
                else:
                    position += 1
            elif 0x30 <= escaped <= 0x37:
                digits = bytearray()
                while position < len(stream) and len(digits) < 3 and 0x30 <= stream[position] <= 0x37:
                    digits.append(stream[position])
                    position += 1
                output.append(int(digits.decode("ascii"), 8) & 0xFF)
            else:
                output.append(escaped)
                position += 1
        elif byte == 0x28:
            depth += 1
            output.append(byte)
            position += 1
        elif byte == 0x29:
            depth -= 1
            position += 1
            if depth == 0:
                return bytes(output), position
            output.append(byte)
        else:
            output.append(byte)
            position += 1
    raise IngestionError("malformed_document")


def _pdf_hex(stream: bytes, position: int) -> Tuple[bytes, int]:
    digits = bytearray()
    while position < len(stream):
        byte = stream[position]
        if byte == 0x3E:
            if len(digits) % 2:
                digits.append(0x30)
            try:
                return bytes.fromhex(digits.decode("ascii")), position + 1
            except ValueError as error:
                raise IngestionError("malformed_document") from error
        if byte in b" \t\r\n\f\0":
            position += 1
            continue
        if not (0x30 <= byte <= 0x39 or 0x41 <= byte <= 0x46 or 0x61 <= byte <= 0x66):
            raise IngestionError("malformed_document")
        digits.append(byte)
        position += 1
    raise IngestionError("malformed_document")


def _decode_pdf_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace")
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


_PDF_TEXT_BREAK_OPERATORS = (b"Td", b"TD", b"T*", b"Tm", b"ET")


def _pdf_decode_with_font(raw: bytes, font: Optional[_PDFFont]) -> str:
    if font is None or font.cmap is None:
        return _decode_pdf_bytes(raw)
    width = font.code_bytes
    parts: List[str] = []
    position = 0
    while position + width <= len(raw):
        code = int.from_bytes(raw[position:position + width], "big")
        parts.append(font.cmap.get(code, "\ufffd"))
        position += width
    if position < len(raw):
        parts.append(_decode_pdf_bytes(raw[position:]))
    return "".join(parts)


def _pdf_content_lines(stream: bytes, fonts: Optional[Dict[str, _PDFFont]] = None) -> List[str]:
    """Collect text-showing operands from one content stream, line by line."""
    fonts = fonts or {}
    lines: List[str] = []
    current: List[str] = []
    in_text = False
    current_font: Optional[_PDFFont] = None
    last_name: Optional[str] = None
    position = 0

    def flush() -> None:
        if not current:
            return
        text = " ".join("".join(current).replace("\x00", " ").split())
        current.clear()
        if text:
            lines.append(text)

    while position < len(stream):
        byte = stream[position]
        if byte == 0x28:  # (
            raw, position = _pdf_literal(stream, position + 1)
            if in_text:
                current.append(_pdf_decode_with_font(raw, current_font))
        elif byte == 0x3C:  # <
            if stream[position:position + 2] == b"<<":
                end = stream.find(b">>", position + 2)
                if end < 0:
                    raise IngestionError("malformed_document")
                position = end + 2
            else:
                raw, position = _pdf_hex(stream, position + 1)
                if in_text:
                    current.append(_pdf_decode_with_font(raw, current_font))
        elif byte == 0x25:  # %
            newline = stream.find(b"\n", position)
            position = len(stream) if newline < 0 else newline + 1
        elif byte in b"[]{}":
            position += 1
        elif byte in b" \t\r\n\f\x00":
            position += 1
        elif byte == 0x2F:  # /Name
            position += 1
            start = position
            while position < len(stream) and stream[position] not in b" \t\r\n\f\x00()<>[]{}/%":
                position += 1
            last_name = stream[start:position].decode("latin-1")
        elif 0x41 <= byte <= 0x5A or 0x61 <= byte <= 0x7A:
            start = position
            while position < len(stream) and stream[position] not in b" \t\r\n\f\x00()<>[]{}/%":
                position += 1
            token = stream[start:position]
            if token == b"BT":
                in_text = True
            elif token == b"Tf":
                current_font = fonts.get(last_name or "")
            elif token == b"BI":
                image_end = stream.find(b"EI", position)
                if image_end < 0:
                    raise IngestionError("malformed_document")
                position = image_end + 2
            elif token in _PDF_TEXT_BREAK_OPERATORS:
                if token == b"ET":
                    in_text = False
                flush()
        elif byte in (0x27, 0x22):  # ' and " show text on the next line
            flush()
            position += 1
        else:
            position += 1
    flush()
    return lines


def _extract_pdf(fetched: FetchedDocument) -> ExtractedDocument:
    objects = _pdf_expand_object_streams(_pdf_objects(fetched.payload))
    blocks: List[Dict[str, Any]] = []
    page_numbers = _pdf_pages(objects)
    for page_number, object_number in enumerate(page_numbers, start=1):
        page_body = objects[object_number]
        fonts = _pdf_fonts(_pdf_resources(page_body, objects), objects)
        chunks: List[bytes] = []
        total = 0
        for content_number in _pdf_refs(page_body, b"Contents"):
            body = objects.get(content_number)
            if body is None:
                continue
            stream = _pdf_stream(body)
            if stream is None:
                raise IngestionError("malformed_document")
            dictionary, payload = stream
            chunk = _pdf_decode_stream(dictionary, payload)
            total += len(chunk)
            if total > MAX_DECOMPRESSED_BYTES:
                raise IngestionError("size_limit_exceeded")
            chunks.append(chunk)
        lines = _pdf_content_lines(b"\n".join(chunks), fonts) if chunks else []
        section = "Página {}".format(page_number)
        for line in lines:
            blocks.append({"kind": "text", "page": page_number, "section": section, "text": line})
    blocks = _finalize_blocks(blocks)
    return ExtractedDocument("pdf", None, blocks)


def _finalize_blocks(blocks: Iterable[Dict[str, Any]]) -> Tuple[Dict[str, Any], ...]:
    finalized: List[Dict[str, Any]] = []
    characters = 0
    for block in blocks:
        text = " ".join(str(block.get("text", "")).split())
        if not text or not text.replace("\ufffd", "").strip():
            continue
        if len(finalized) >= MAX_TEXT_BLOCKS:
            raise IngestionError("size_limit_exceeded")
        characters += len(text)
        if characters > MAX_TEXT_CHARS:
            raise IngestionError("size_limit_exceeded")
        finalized.append(
            {
                "kind": block.get("kind", "text"),
                "page": block.get("page"),
                "section": block.get("section"),
                "text": text,
            }
        )
    if not finalized:
        raise IngestionError("no_extractable_text")
    return tuple(finalized)


def _extract(fetched: FetchedDocument) -> ExtractedDocument:
    media_type = _classify(fetched)
    return _extract_pdf(fetched) if media_type == "pdf" else _extract_html(fetched)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(str(temporary), str(path))


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _quarantine_document(
    quarantine_root: Path,
    candidate: Dict[str, Any],
    fetched: FetchedDocument,
    extracted: ExtractedDocument,
) -> Dict[str, Any]:
    candidate_id = candidate["candidate_id"]
    document = {
        "schema_version": EXTRACTED_DOCUMENT_VERSION,
        "candidate_id": candidate_id,
        "media_type": extracted.media_type,
        "extractor": EXTRACTOR,
        "title": extracted.title,
        "blocks": list(extracted.blocks),
    }
    document_text = _canonical_json(document)
    original_digest = _sha256(fetched.payload)
    text_digest = _sha256(document_text.encode("utf-8"))
    directory = Path(quarantine_root) / candidate_id
    directory.mkdir(parents=True, exist_ok=True)
    original_path = directory / "original-{}.{}".format(original_digest, extracted.media_type)
    if not original_path.exists() or _sha256(original_path.read_bytes()) != original_digest:
        _atomic_write_bytes(original_path, fetched.payload)
    extracted_path = directory / "extracted-{}.json".format(original_digest)
    _atomic_write_text(extracted_path, document_text)
    pages = {block["page"] for block in extracted.blocks if block["page"] is not None}
    return {
        "original_sha256": original_digest,
        "byte_size": len(fetched.payload),
        "declared_content_type": fetched.declared_content_type,
        "media_type": extracted.media_type,
        "extractor": EXTRACTOR,
        "extracted_text_sha256": text_digest,
        "page_count": len(pages) if pages else None,
        "block_count": len(extracted.blocks),
        "original_path": str(Path(candidate_id) / original_path.name),
        "extracted_path": str(Path(candidate_id) / extracted_path.name),
    }


def _base_record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "issuer": candidate["issuer"],
        "registry_id": candidate["registry_id"],
        "registry_url": candidate["registry_url"],
        "publication_url": candidate["publication_url"],
        "title": candidate["title"],
        "stable_identity": candidate["stable_identity"],
        "version_hash": candidate["version_hash"],
        "review_status": "pending",
        "status": "failed",
        "failure": None,
        "last_attempt_at": None,
        "last_success_at": None,
        "attempts": [],
    }


def _files_present(record: Dict[str, Any], quarantine_root: Path) -> bool:
    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str):
        return False
    for key in ("original_path", "extracted_path"):
        value = record.get(key)
        if not isinstance(value, str):
            return False
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != (candidate_id,):
            return False
        if not (Path(quarantine_root) / relative).is_file():
            return False
    return True


def _previous_attempts(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    attempts = record.get("attempts")
    return copy.deepcopy(attempts) if isinstance(attempts, list) else []


def _append_attempt(record: Dict[str, Any], attempt: Dict[str, Any]) -> None:
    attempts = _previous_attempts(record)
    attempts.append(attempt)
    record["attempts"] = attempts[-MAX_ATTEMPTS_PER_CANDIDATE:]


def _record_failure(
    state: Dict[str, Any],
    candidate: Dict[str, Any],
    failure: str,
    status: str,
    stamp: str,
) -> Dict[str, Any]:
    existing = state["candidates"].get(candidate["candidate_id"])
    record = copy.deepcopy(existing) if isinstance(existing, dict) else _base_record(candidate)
    record.update({"status": status, "failure": failure, "last_attempt_at": stamp})
    _append_attempt(record, {"attempted_at": stamp, "status": status, "failure": failure})
    state["candidates"][candidate["candidate_id"]] = record
    return {"candidate_id": candidate["candidate_id"], "status": status, "failure": failure,
            "original_sha256": record.get("original_sha256"), "media_type": record.get("media_type"),
            "page_count": record.get("page_count"), "block_count": record.get("block_count")}


def _ingest_candidate(
    candidate: Dict[str, Any],
    state: Dict[str, Any],
    quarantine_root: Path,
    stamp: str,
    seen_urls: Dict[str, str],
    seen_digests: Dict[str, str],
) -> Dict[str, Any]:
    candidate_id = candidate["candidate_id"]
    existing = state["candidates"].get(candidate_id)
    if isinstance(existing, dict):
        unchanged = (
            existing.get("status") == "extracted"
            and existing.get("version_hash") == candidate["version_hash"]
            and existing.get("extractor") == EXTRACTOR
            and existing.get("media_type") in ("pdf", "html")
            and _files_present(existing, quarantine_root)
        )
        if unchanged:
            return {"candidate_id": candidate_id, "status": "unchanged", "failure": None,
                    "original_sha256": existing.get("original_sha256"),
                    "media_type": existing.get("media_type"),
                    "page_count": existing.get("page_count"),
                    "block_count": existing.get("block_count")}
    try:
        allowed_hosts = ISSUER_ALLOWED_HOSTS.get(candidate.get("issuer"), ())
        fetched = _fetch(candidate["publication_url"], allowed_hosts)
        extracted = _extract(fetched)
        digest = _sha256(fetched.payload)
        if digest in seen_digests and seen_digests[digest] != candidate_id:
            return _record_failure(state, candidate, "duplicate_content", "rejected", stamp)
        seen_digests[digest] = candidate_id
        quarantine = _quarantine_document(quarantine_root, candidate, fetched, extracted)
    except IngestionError as error:
        return _record_failure(state, candidate, error.failure, "failed", stamp)
    except Exception:
        return _record_failure(state, candidate, "internal_error", "failed", stamp)

    record = copy.deepcopy(existing) if isinstance(existing, dict) else _base_record(candidate)
    previous_digest = record.get("original_sha256")
    previous_value = record.get("previous_original_sha256")
    if isinstance(previous_digest, str) and previous_digest != quarantine["original_sha256"]:
        previous_value = previous_digest
    record.update(
        {
            "status": "extracted",
            "failure": None,
            "last_attempt_at": stamp,
            "last_success_at": stamp,
            "version_hash": candidate["version_hash"],
            **quarantine,
        }
    )
    if isinstance(previous_value, str):
        record["previous_original_sha256"] = previous_value
    _append_attempt(
        record,
        {"attempted_at": stamp, "status": "extracted", "failure": None,
         "original_sha256": quarantine["original_sha256"]},
    )
    state["candidates"][candidate_id] = record
    return {"candidate_id": candidate_id, "status": "extracted", "failure": None,
            "original_sha256": quarantine["original_sha256"],
            "media_type": quarantine["media_type"],
            "page_count": quarantine["page_count"],
            "block_count": quarantine["block_count"]}


def ingest(
    discovery_state: Path,
    state_path: Path,
    quarantine_dir: Path,
    monitoring_state: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Ingest every pending discovery candidate into quarantine.

    Returns a deterministic per-candidate report. Global configuration or state
    errors raise ``IngestionError`` before any network access; per-candidate
    failures are recorded and never abort the run. The canonical knowledge
    artifacts are not read or written.
    """
    started = _now(now)
    stamp = started.isoformat()
    state_path = Path(state_path)
    quarantine_root = Path(quarantine_dir)
    if _inside_directory(state_path, KNOWLEDGE_ROOT) or _inside_directory(quarantine_root, KNOWLEDGE_ROOT):
        raise IngestionError("unsafe_workspace")
    candidates = load_discovery_candidates(Path(discovery_state))
    monitoring = load_monitoring_sources(Path(monitoring_state)) if monitoring_state else []
    state = _load_state(state_path)
    quarantine_root.mkdir(parents=True, exist_ok=True)

    seen_urls: Dict[str, str] = {}
    seen_digests: Dict[str, str] = {}
    outcomes: List[Dict[str, Any]] = []
    for candidate in candidates:
        failure = _destination_failure(candidate)
        if failure is not None:
            outcomes.append(_record_failure(state, candidate, failure, "rejected", stamp))
            continue
        url = candidate["publication_url"]
        if url in seen_urls:
            outcomes.append(_record_failure(state, candidate, "duplicate_candidate", "rejected", stamp))
            continue
        seen_urls[url] = candidate["candidate_id"]
        outcomes.append(
            _ingest_candidate(candidate, state, quarantine_root, stamp, seen_urls, seen_digests)
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(state_path, _canonical_json(state))
    finished = _now(now)
    summary = {
        status: sum(1 for item in outcomes if item["status"] == status)
        for status in ("extracted", "unchanged", "failed", "rejected")
    }
    return {
        "run": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "documents": sorted(outcomes, key=lambda item: item["candidate_id"]),
        "monitoring": monitoring,
        "summary": summary,
        "state": str(state_path),
        "quarantine": str(quarantine_root),
    }
