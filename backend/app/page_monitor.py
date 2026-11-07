"""Bounded, review-only monitoring of explicitly configured official PAC pages.

The monitor compares exact response bytes and normalized visible text against a
last-successful snapshot. It reports only added, removed, or changed text. It
never interprets legal meaning, follows linked resources, executes scripts, or
writes canonical knowledge.

State and report are operator data outside ``knowledge/``. State keeps only the
bounded normalized text needed for the next diff. Run the command through
``backend/scripts/monitor_official_pages.py``.
"""

import argparse
import difflib
import hashlib
import html.parser
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from app.source_catalog import APPROVED_HOSTS, ISSUER_ALLOWED_HOSTS

STATE_VERSION = "official-page-monitor-state-v1"
REPORT_VERSION = "official-page-change-report-v1"

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15
MAX_TEXT_SEGMENTS = 5000
MAX_TEXT_CHARS = 2000000
MAX_EXCERPTS = 50
MAX_EXCERPT_CHARS = 240

USER_AGENT = "Manijero-Official-Page-Monitor/1.0"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

ISSUERS = ("FEGA", "MAPA", "Junta de Andalucía")

# Only each issuer's first-party pair. BOE hosts are approved for FEGA/MAPA in
# the catalog, but they are not PAC page hosts for this monitor.
PAGE_HOSTS: Dict[str, Tuple[str, ...]] = {
    "FEGA": ("fega.gob.es", "www.fega.gob.es"),
    "MAPA": ("mapa.gob.es", "www.mapa.gob.es"),
    "Junta de Andalucía": ("juntadeandalucia.es", "www.juntadeandalucia.es"),
}

if not set(host for hosts in PAGE_HOSTS.values() for host in hosts).issubset(APPROVED_HOSTS):
    raise RuntimeError("page monitor hosts must stay on the approved-host allowlist")
for _issuer, _hosts in PAGE_HOSTS.items():
    if not set(_hosts).issubset(ISSUER_ALLOWED_HOSTS[_issuer]):
        raise RuntimeError("page monitor hosts must stay first-party for their issuer")

ALLOWED_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})

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

STATE_RECORD_KEYS = frozenset({
    "url", "issuer", "last_attempt_at", "http_status", "last_success_at",
    "content_sha256", "text_sha256", "segments", "etag", "last_modified",
})

FAILURES = frozenset({
    "upstream request failed",
    "unsupported content type",
    "response exceeded size limit",
    "page text exceeded limit",
    "page had no readable text",
    "redirect rejected: host or scheme changed",
    "received 304 without a prior successful snapshot",
})

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"


class PageMonitorError(ValueError):
    """Invalid configuration, state, page response, or output path."""


class PageMonitorWriteError(PageMonitorError):
    """The report or state file could not be written."""


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        original = urlsplit(request.full_url)
        target = urlsplit(new_url)
        try:
            port = target.port
        except ValueError as error:
            raise PageMonitorError("redirect rejected: host or scheme changed") from error
        if (target.scheme != "https"
                or target.hostname != original.hostname
                or port not in (None, 443)
                or target.username is not None
                or target.password is not None
                or target.fragment):
            raise PageMonitorError("redirect rejected: host or scheme changed")
        return super().redirect_request(request, response, code, message, headers, new_url)


class _VisibleTextParser(html.parser.HTMLParser):
    """Collect normalized visible text blocks, skipping script-like content."""

    SKIPPED_ELEMENTS = frozenset({"script", "style", "noscript", "template"})
    BLOCK_ELEMENTS = frozenset({
        "address", "article", "aside", "blockquote", "body", "caption", "dd",
        "details", "dialog", "div", "dl", "dt", "fieldset", "figcaption",
        "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
        "head", "header", "hgroup", "hr", "html", "li", "main", "nav", "ol",
        "p", "pre", "section", "summary", "table", "tbody", "td", "tfoot",
        "th", "thead", "title", "tr", "ul",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: List[str] = []
        self._buffer: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        name = tag.lower()
        if name in self.SKIPPED_ELEMENTS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if name in self.BLOCK_ELEMENTS:
            self._flush()
        elif name == "br":
            self._buffer.append(" ")

    def handle_startendtag(self, tag, attrs):
        name = tag.lower()
        if name in self.SKIPPED_ELEMENTS:
            return
        if self._skip_depth:
            return
        if name in self.BLOCK_ELEMENTS:
            self._flush()
        elif name == "br":
            self._buffer.append(" ")

    def handle_endtag(self, tag):
        name = tag.lower()
        if name in self.SKIPPED_ELEMENTS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if name in self.BLOCK_ELEMENTS:
            self._flush()

    def handle_data(self, data):
        if self._skip_depth:
            return
        self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = _normalize("".join(self._buffer))
        self._buffer = []
        if text:
            self.blocks.append(text)


def validate_config(config: Any, strict_urls: bool = True) -> List[Dict[str, str]]:
    """Validate the explicit page config before any request or write.

    ``strict_urls`` is the public validation default. ``run`` keeps the
    structural checks global but checks each destination inside that page's
    outcome, so one unsafe URL cannot hide the other pages' results.
    """

    if not isinstance(config, dict) or set(config) != {"sources"}:
        raise PageMonitorError("configuration must contain exactly a sources array")
    sources = config["sources"]
    if not isinstance(sources, list) or not sources:
        raise PageMonitorError("sources must be a non-empty list")

    result: List[Dict[str, str]] = []
    ids = set()
    urls = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"id", "issuer", "url"}:
            raise PageMonitorError("source {} must contain exactly id, issuer, url".format(index))
        source_id = source["id"]
        issuer = source["issuer"]
        url = source["url"]
        if (not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id)
                or source_id in ids):
            raise PageMonitorError("source {} has an invalid or duplicate id".format(index))
        if not isinstance(issuer, str) or issuer not in PAGE_HOSTS:
            raise PageMonitorError("source {} issuer is not approved".format(index))
        if strict_urls:
            try:
                _validate_source_url(url, issuer)
            except PageMonitorError as error:
                raise PageMonitorError(
                    "source {} URL is not an approved official page".format(index)
                ) from error
        if not isinstance(url, str):
            raise PageMonitorError("source {} URL must be a string".format(index))
        if url in urls:
            raise PageMonitorError("source {} has a duplicate URL".format(index))
        ids.add(source_id)
        urls.add(url)
        result.append({"id": source_id, "issuer": issuer, "url": url})
    return result


def _validate_source_url(url: Any, issuer: str) -> None:
    if not isinstance(url, str):
        raise PageMonitorError("URL must be a string")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PageMonitorError("URL is malformed") from error
    if (parsed.scheme != "https"
            or parsed.hostname not in PAGE_HOSTS[issuer]
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or not parsed.path
            or parsed.path == "/"):
        raise PageMonitorError("URL is not an approved official page")


def _is_safe_final_url(url: str, original_url: str) -> bool:
    try:
        final = urlsplit(url)
        original = urlsplit(original_url)
        port = final.port
    except ValueError:
        return False
    return (final.scheme == "https"
            and final.hostname == original.hostname
            and port in (None, 443)
            and final.username is None
            and final.password is None
            and not final.fragment)


def _request(source: Mapping[str, str], previous: Mapping[str, Any]) -> Tuple[int, Any, bytes]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html, application/xhtml+xml, text/plain",
    }
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("last_modified"):
        headers["If-Modified-Since"] = previous["last_modified"]
    request = urllib.request.Request(source["url"], headers=headers)
    opener = urllib.request.build_opener(_SameHostRedirect())
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except PageMonitorError:
        raise
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return 304, error.headers, b""
        raise PageMonitorError("upstream returned HTTP {}".format(error.code)) from error
    except (urllib.error.URLError, OSError) as error:
        raise PageMonitorError("upstream request failed") from error
    try:
        with response:
            if not _is_safe_final_url(response.geturl(), source["url"]):
                raise PageMonitorError("redirect rejected: host or scheme changed")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, response.headers, payload
    except PageMonitorError:
        raise
    except (OSError, ValueError) as error:
        raise PageMonitorError("upstream request failed") from error


def _accept_response(status: int, headers: Any, payload: bytes) -> None:
    if status == 304:
        return
    if status != 200:
        raise PageMonitorError("upstream returned HTTP {}".format(status))
    if len(payload) > MAX_RESPONSE_BYTES:
        raise PageMonitorError("response exceeded size limit")
    if _content_type(headers) not in ALLOWED_CONTENT_TYPES:
        raise PageMonitorError("unsupported content type")


def _content_type(headers: Any) -> str:
    if headers is None or not hasattr(headers, "get_content_type"):
        return ""
    declared = headers.get("Content-Type")
    if declared is None or not str(declared).strip():
        return ""
    return headers.get_content_type().lower()


def _header(headers: Any, name: str) -> Optional[str]:
    if headers is None:
        return None
    value = headers.get(name)
    return str(value) if value else None


def _decode(payload: bytes, charset: Optional[str]) -> str:
    declared = (charset or "").strip()
    codec = HTML_CHARSETS.get(declared.lower(), declared or None)
    candidates = [codec] if codec else []
    candidates.extend(["utf-8", "cp1252"])
    for candidate in candidates:
        try:
            return payload.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("cp1252", errors="replace")


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _extract_segments(payload: bytes, content_type: str, charset: Optional[str]) -> List[str]:
    text = _decode(payload, charset)
    if content_type == "text/plain":
        segments = [_normalize(line) for line in text.splitlines()]
    else:
        parser = _VisibleTextParser()
        try:
            parser.feed(text)
            parser.close()
        except Exception as error:
            raise PageMonitorError("page had no readable text") from error
        segments = parser.blocks
    return _bounded_segments([segment for segment in segments if segment])


def _bounded_segments(segments: List[str]) -> List[str]:
    if not segments:
        raise PageMonitorError("page had no readable text")
    if len(segments) > MAX_TEXT_SEGMENTS:
        raise PageMonitorError("page text exceeded limit")
    if len("\n".join(segments)) > MAX_TEXT_CHARS:
        raise PageMonitorError("page text exceeded limit")
    return segments


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _text_sha256(segments: List[str]) -> str:
    return _sha256("\n".join(segments).encode("utf-8"))


def _empty_diff() -> Dict[str, Dict[str, Any]]:
    return {
        "added": {"count": 0, "excerpts": []},
        "removed": {"count": 0, "excerpts": []},
        "changed": {"count": 0, "excerpts": []},
    }


def _take_excerpt(excerpts: List[Dict[str, str]], item: Dict[str, str], budget: int) -> int:
    if budget <= 0:
        return budget
    excerpts.append(item)
    return budget - 1


def _text_excerpt(text: str) -> Dict[str, str]:
    return {"text": text[:MAX_EXCERPT_CHARS]}


def _changed_excerpt(before: str, after: str) -> Dict[str, str]:
    return {"before": before[:MAX_EXCERPT_CHARS], "after": after[:MAX_EXCERPT_CHARS]}


def _diff(previous: List[str], current: List[str]) -> Dict[str, Dict[str, Any]]:
    added_count = removed_count = changed_count = 0
    added_excerpts: List[Dict[str, str]] = []
    removed_excerpts: List[Dict[str, str]] = []
    changed_excerpts: List[Dict[str, str]] = []
    budget = MAX_EXCERPTS

    matcher = difflib.SequenceMatcher(autojunk=False, a=previous, b=current)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added_count += j2 - j1
            for text in current[j1:j2]:
                budget = _take_excerpt(added_excerpts, _text_excerpt(text), budget)
        elif tag == "delete":
            removed_count += i2 - i1
            for text in previous[i1:i2]:
                budget = _take_excerpt(removed_excerpts, _text_excerpt(text), budget)
        elif tag == "replace":
            old = previous[i1:i2]
            new = current[j1:j2]
            paired = min(len(old), len(new))
            changed_count += paired
            for index in range(paired):
                budget = _take_excerpt(
                    changed_excerpts, _changed_excerpt(old[index], new[index]), budget
                )
            if len(new) > paired:
                added_count += len(new) - paired
                for text in new[paired:]:
                    budget = _take_excerpt(added_excerpts, _text_excerpt(text), budget)
            elif len(old) > paired:
                removed_count += len(old) - paired
                for text in old[paired:]:
                    budget = _take_excerpt(removed_excerpts, _text_excerpt(text), budget)

    return {
        "added": {"count": added_count, "excerpts": added_excerpts},
        "removed": {"count": removed_count, "excerpts": removed_excerpts},
        "changed": {"count": changed_count, "excerpts": changed_excerpts},
    }


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def _resolve_output_path(path: Any, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if _inside_directory(resolved, KNOWLEDGE_ROOT):
        raise PageMonitorError("{} must not be inside knowledge/".format(label))
    if resolved.exists() and resolved.is_dir():
        raise PageMonitorError("{} must be a file path".format(label))
    if resolved.parent.exists() and not resolved.parent.is_dir():
        raise PageMonitorError("{} parent must be a directory".format(label))
    return resolved


def _is_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_optional_timestamp(value: Any) -> bool:
    return value is None or _is_timestamp(value)


def _is_optional_hash(value: Any) -> bool:
    return value is None or (isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None)


def _is_optional_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _invalid_state() -> PageMonitorError:
    return PageMonitorError("invalid monitoring state")


def _validate_state_record(page_id: Any, record: Any) -> None:
    if not isinstance(page_id, str) or not ID_PATTERN.fullmatch(page_id):
        raise PageMonitorError("invalid monitoring state")
    if not isinstance(record, dict) or set(record) != STATE_RECORD_KEYS:
        raise PageMonitorError("invalid monitoring state")
    if not isinstance(record["url"], str) or not isinstance(record["issuer"], str):
        raise PageMonitorError("invalid monitoring state")
    if record["issuer"] not in PAGE_HOSTS:
        raise PageMonitorError("invalid monitoring state")
    try:
        _validate_source_url(record["url"], record["issuer"])
    except PageMonitorError as error:
        raise _invalid_state() from error
    if (not _is_timestamp(record["last_attempt_at"])
            or not _is_optional_timestamp(record["last_success_at"])
            or record["http_status"] not in (None, 200, 304)
            or not _is_optional_hash(record["content_sha256"])
            or not _is_optional_hash(record["text_sha256"])
            or not _is_optional_string(record["etag"])
            or not _is_optional_string(record["last_modified"])):
        raise PageMonitorError("invalid monitoring state")
    segments = record["segments"]
    if segments is not None:
        if not isinstance(segments, list) or not segments:
            raise PageMonitorError("invalid monitoring state")
        for segment in segments:
            if (not isinstance(segment, str) or not segment
                    or _normalize(segment) != segment):
                raise PageMonitorError("invalid monitoring state")
        try:
            _bounded_segments(segments)
        except PageMonitorError as error:
            raise _invalid_state() from error
    if record["last_success_at"] is None:
        if (record["http_status"] is not None
                or record["content_sha256"] is not None
                or record["text_sha256"] is not None
                or segments is not None):
            raise PageMonitorError("invalid monitoring state")
    elif (record["http_status"] not in (200, 304)
            or record["content_sha256"] is None
            or record["text_sha256"] is None
            or segments is None):
        raise PageMonitorError("invalid monitoring state")


def _read_state(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"schema_version": STATE_VERSION, "pages": {}}
    except (OSError, UnicodeDecodeError) as error:
        raise PageMonitorError("cannot read monitoring state") from error
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PageMonitorError("cannot read monitoring state") from error
    if (not isinstance(state, dict) or set(state) != {"schema_version", "pages"}
            or state.get("schema_version") != STATE_VERSION
            or not isinstance(state.get("pages"), dict)):
        raise PageMonitorError("invalid monitoring state")
    for page_id, record in state["pages"].items():
        _validate_state_record(page_id, record)
    return state


def _normalize_now(now: Any) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise PageMonitorError("invalid --now value")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _parse_now_arg(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PageMonitorError("invalid --now value") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _failure_category(error: BaseException) -> str:
    message = str(error)
    if message in FAILURES or message.startswith("upstream returned HTTP "):
        return message
    return "upstream request failed"


def _outcome(source: Mapping[str, str], status: str, first_seen: bool,
             content_sha256: Optional[str], text_sha256: Optional[str],
             content_changed: bool, text_changed: bool,
             diff: Mapping[str, Mapping[str, Any]], failure: Optional[str]) -> Dict[str, Any]:
    return {
        "id": source["id"],
        "issuer": source["issuer"],
        "url": source["url"],
        "status": status,
        "first_seen": first_seen,
        "content_sha256": content_sha256,
        "text_sha256": text_sha256,
        "content_changed": content_changed,
        "text_changed": text_changed,
        "added": diff["added"],
        "removed": diff["removed"],
        "changed": diff["changed"],
        "failure": failure,
    }


def _failed_outcome(source: Mapping[str, str], previous: Optional[Mapping[str, Any]],
                    category: str) -> Dict[str, Any]:
    return _outcome(
        source, "failed", False,
        previous.get("content_sha256") if previous else None,
        previous.get("text_sha256") if previous else None,
        False, False, _empty_diff(), category,
    )


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = Path(str(path) + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(str(temporary), str(path))
    except OSError as error:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise PageMonitorWriteError("cannot write {}".format(path.name)) from error


def run(config: Any, state_path: Any, report_path: Any,
        now: Optional[datetime] = None) -> Dict[str, Any]:
    """Validate, fetch each configured page, and write the report then state."""

    sources = validate_config(config, strict_urls=False)
    resolved_state = _resolve_output_path(state_path, "state")
    resolved_report = _resolve_output_path(report_path, "report")
    if resolved_state == resolved_report:
        raise PageMonitorError("state and report paths must differ")
    state = _read_state(resolved_state)
    timestamp = _normalize_now(now).isoformat()
    pages = state["pages"]
    outcomes: List[Dict[str, Any]] = []

    for source in sources:
        previous = pages.get(source["id"])
        try:
            _validate_source_url(source["url"], source["issuer"])
            status, headers, payload = _request(source, previous or {})
            _accept_response(status, headers, payload)
            if status == 304:
                if not previous or previous.get("last_success_at") is None:
                    raise PageMonitorError("received 304 without a prior successful snapshot")
                record = dict(previous)
                record["last_attempt_at"] = timestamp
                record["http_status"] = 304
                pages[source["id"]] = record
                outcome = _outcome(
                    source, "unchanged", False,
                    previous["content_sha256"], previous["text_sha256"],
                    False, False, _empty_diff(), None,
                )
            else:
                content_type = _content_type(headers)
                charset = headers.get_content_charset() if headers is not None else None
                segments = _extract_segments(payload, content_type, charset)
                content_sha256 = _sha256(payload)
                text_sha256 = _text_sha256(segments)
                etag = _header(headers, "ETag") or (
                    previous.get("etag") if previous else None
                )
                modified = _header(headers, "Last-Modified") or (
                    previous.get("last_modified") if previous else None
                )
                if previous and previous.get("last_success_at") is not None:
                    content_changed = content_sha256 != previous["content_sha256"]
                    text_changed = text_sha256 != previous["text_sha256"]
                    diff = _diff(previous["segments"], segments) if text_changed else _empty_diff()
                    result = "changed" if (content_changed or text_changed) else "unchanged"
                    first_seen = False
                else:
                    content_changed = False
                    text_changed = False
                    diff = _empty_diff()
                    result = "first_seen"
                    first_seen = True
                pages[source["id"]] = {
                    "url": source["url"],
                    "issuer": source["issuer"],
                    "last_attempt_at": timestamp,
                    "http_status": 200,
                    "last_success_at": timestamp,
                    "content_sha256": content_sha256,
                    "text_sha256": text_sha256,
                    "segments": segments,
                    "etag": etag,
                    "last_modified": modified,
                }
                outcome = _outcome(
                    source, result, first_seen, content_sha256, text_sha256,
                    content_changed, text_changed, diff, None,
                )
        except PageMonitorError as error:
            outcome = _failed_outcome(source, previous, _failure_category(error))
        except Exception:
            outcome = _failed_outcome(source, previous, "upstream request failed")
        outcomes.append(outcome)

    report = {
        "schema_version": REPORT_VERSION,
        "checked_at": timestamp,
        "pages": sorted(outcomes, key=lambda page: page["id"]),
    }
    _atomic_write(resolved_report, report)
    _atomic_write(resolved_state, {"schema_version": STATE_VERSION, "pages": pages})
    return report


def _print_results(report: Mapping[str, Any], report_path: Any) -> None:
    counts = {"first_seen": 0, "changed": 0, "unchanged": 0, "failed": 0}
    for page in report["pages"]:
        status = page["status"]
        counts[status] = counts.get(status, 0) + 1
        if status == "first_seen":
            print("Result: {}: first seen.".format(page["id"]))
        elif status == "unchanged":
            print("Result: {}: no change.".format(page["id"]))
        elif status == "changed":
            if page["text_changed"]:
                print("Result: {}: {} added, {} changed, {} removed.".format(
                    page["id"], page["added"]["count"], page["changed"]["count"],
                    page["removed"]["count"],
                ))
            else:
                print("Result: {}: content changed, no visible text change.".format(page["id"]))
        else:
            print("Result: {}: could not be checked ({}).".format(page["id"], page["failure"]))

    total = len(report["pages"])
    summary = "Result: {} {} checked: ".format(total, "page" if total == 1 else "pages")
    if counts["first_seen"]:
        summary += "{} first seen, ".format(counts["first_seen"])
    summary += "{} changed, {} unchanged, {} failed. Report: {}.".format(
        counts["changed"], counts["unchanged"], counts["failed"], report_path,
    )
    print(summary)


def main(argv: Optional[List[str]] = None, now: Optional[datetime] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="JSON file containing an explicit sources array")
    parser.add_argument("--state", type=Path, required=True,
                        help="Local last-good monitoring state JSON path outside knowledge/")
    parser.add_argument("--report", type=Path, required=True,
                        help="Change report JSON path outside knowledge/")
    parser.add_argument("--now", help="Optional ISO-8601 timestamp for deterministic replay")
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code or 0)

    try:
        timestamp = _parse_now_arg(args.now) if args.now else now
        try:
            config = json.loads(args.config.read_text(encoding="utf-8"))
        except OSError as error:
            raise PageMonitorError("cannot read configuration") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PageMonitorError("configuration is not valid JSON") from error
        report = run(config, args.state, args.report, now=timestamp)
    except PageMonitorWriteError:
        print("Result: could not write the report or state.")
        return 2
    except (PageMonitorError, OSError):
        print("Result: could not start (invalid configuration, state, path, or time).")
        return 2

    _print_results(report, args.report)
    return 1 if any(page["status"] == "failed" for page in report["pages"]) else 0
