"""Fail-closed polling of explicitly configured official source feeds.

Monitoring records feed snapshots only. It never follows a feed item URL,
parses legal meaning, or writes the canonical source catalog/passages.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from app.source_catalog import APPROVED_HOSTS

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15
USER_AGENT = "Manijero-Official-Source-Monitor/1.0"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class MonitorError(ValueError):
    """Invalid monitor configuration or persisted state."""


def validate_sources(sources: Any) -> List[Dict[str, str]]:
    if not isinstance(sources, list) or not sources:
        raise MonitorError("sources must be a non-empty list")
    result: List[Dict[str, str]] = []
    ids = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"id", "url", "format"}:
            raise MonitorError("source {} must contain exactly id, url, format".format(index))
        source_id, url, feed_format = source["id"], source["url"], source["format"]
        if not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id) or source_id in ids:
            raise MonitorError("source {} has an invalid or duplicate id".format(index))
        if feed_format not in ("rss", "json"):
            raise MonitorError("source {} format must be rss or json".format(index))
        if not isinstance(url, str):
            raise MonitorError("source {} URL must be a string".format(index))
        try:
            parsed = urlsplit(url)
        except ValueError as error:
            raise MonitorError("source {} URL is malformed".format(index)) from error
        if (parsed.scheme != "https" or parsed.hostname not in APPROVED_HOSTS or
                parsed.username is not None or parsed.password is not None or
                not parsed.path or parsed.path == "/" or parsed.fragment):
            raise MonitorError("source {} URL is not an approved official endpoint".format(index))
        ids.add(source_id)
        result.append({"id": source_id, "url": url, "format": feed_format})
    return result


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        original = urlsplit(request.full_url)
        target = urlsplit(new_url)
        if target.scheme != "https" or target.hostname != original.hostname:
            raise MonitorError("redirect rejected: host or scheme changed")
        return super().redirect_request(request, response, code, message, headers, new_url)


def _validate_payload(payload: bytes, feed_format: str) -> None:
    if not payload:
        raise MonitorError("empty upstream response")
    try:
        if feed_format == "rss":
            root = ET.fromstring(payload)
            if root.tag.rsplit("}", 1)[-1].lower() not in ("rss", "feed", "rdf"):
                raise MonitorError("response is not an RSS/Atom feed")
        else:
            json.loads(payload.decode("utf-8"))
    except (ET.ParseError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MonitorError("malformed upstream {} feed".format(feed_format)) from error


def _read_state(path: Path) -> Dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": "source-monitor-state-v1", "sources": {}}
    except (OSError, json.JSONDecodeError) as error:
        raise MonitorError("cannot read monitoring state") from error
    if (not isinstance(state, dict) or state.get("schema_version") != "source-monitor-state-v1"
            or not isinstance(state.get("sources"), dict)):
        raise MonitorError("invalid monitoring state")
    return state


def _request(source: Mapping[str, str], previous: Mapping[str, Any]) -> Tuple[int, Mapping[str, str], bytes]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/json, */*"}
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("last_modified"):
        headers["If-Modified-Since"] = previous["last_modified"]
    request = urllib.request.Request(source["url"], headers=headers)
    opener = urllib.request.build_opener(_SameHostRedirect())
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return 304, error.headers, b""
        raise MonitorError("upstream returned HTTP {}".format(error.code)) from error
    with response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise MonitorError("upstream response exceeded size limit")
        return response.status, response.headers, payload


def scan(sources: Any, state_path: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Poll configured feeds and atomically persist success/failure evidence."""
    configured = validate_sources(sources)
    state = _read_state(Path(state_path))
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    outcomes = []
    for source in configured:
        previous = state["sources"].get(source["id"], {})
        record = {"url": source["url"], "last_attempt_at": timestamp}
        try:
            status, headers, payload = _request(source, previous)
            if status == 304:
                digest = previous.get("content_sha256")
                if not isinstance(digest, str):
                    raise MonitorError("received 304 without a prior successful snapshot")
                changed = False
            else:
                _validate_payload(payload, source["format"])
                digest = hashlib.sha256(payload).hexdigest()
                changed = digest != previous.get("content_sha256")
            etag = headers.get("ETag") or previous.get("etag")
            modified = headers.get("Last-Modified") or previous.get("last_modified")
            record.update({"status": "success", "http_status": status, "last_success_at": timestamp,
                           "etag": etag, "last_modified": modified, "content_sha256": digest,
                           "changed": changed})
        except Exception as error:
            # Do not persist exception text: urllib errors may contain private proxy details.
            record.update({"status": "failure", "failure": str(error) if isinstance(error, MonitorError) else "upstream request failed",
                           "last_success_at": previous.get("last_success_at"),
                           "etag": previous.get("etag"), "last_modified": previous.get("last_modified"),
                           "content_sha256": previous.get("content_sha256"), "changed": False})
        state["sources"][source["id"]] = record
        outcomes.append({"id": source["id"], **record})
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(state_path) + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(state_path))
    return {"scanned_at": timestamp, "sources": outcomes,
            "success": all(item["status"] == "success" for item in outcomes)}
