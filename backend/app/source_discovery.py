"""Manual, bounded discovery of official publication records into review-only state."""
import hashlib
import json
import os
import re
import copy
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlsplit

from app.source_catalog import ISSUER_ALLOWED_HOSTS
from app.source_monitor import MAX_RESPONSE_BYTES, TIMEOUT_SECONDS, _SameHostRedirect

CONFIG_VERSION = "official-discovery-config-v1"
STATE_VERSION = "official-discovery-state-v1"
REGISTRIES = {
    "boe": {"issuer": "BOE", "url": "https://www.boe.es/datosabiertos/api/boe/sumario/{date}", "format": "boe-xml"},
    "boja": {"issuer": "Junta de Andalucía", "url": "https://datos.juntadeandalucia.es/api/v0/boja/get/calendar?year={year}", "format": "boja-json"},
}
UNCHECKED_ISSUERS = ("FEGA", "MAPA")
MAX_RECORDS = 10000
MAX_BOJA_BULLETINS = 400
MAX_BOJA_TOTAL_BYTES = 160 * 1024 * 1024


def _safe_url(url: Any, issuer: str) -> bool:
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in ISSUER_ALLOWED_HOSTS[issuer]
                and p.username is None and p.password is None and p.path not in ("", "/")
                and not p.fragment)
    except ValueError:
        return False


def _fetch(url: str, accept: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "Manijero-Discovery/1.0"})
    opener = urllib.request.build_opener(_SameHostRedirect())
    with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
        final = response.geturl()
        if urlsplit(final).scheme != "https" or urlsplit(final).hostname != urlsplit(url).hostname:
            raise ValueError("unsafe redirect")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds configured size limit")
    return data


def _boe(payload: bytes) -> List[Dict[str, str]]:
    root = ET.fromstring(payload)
    if root.findtext("./status/code") != "200":
        raise ValueError("registry response reports failure")
    items = root.findall(".//item")
    result = []
    for item in items:
        title = (item.findtext("titulo") or "").strip()
        url = (item.findtext("url_pdf") or item.findtext("url_html") or "").strip()
        identity = (item.findtext("identificador") or "").strip()
        if not (identity and title and url):
            raise ValueError("registry contains an incomplete publication record")
        result.append({"id": identity, "title": title, "url": url})
    if not result:
        raise ValueError("registry contains no recognized publication records")
    return result


def _flatten_records(value: Any) -> List[Dict[str, str]]:
    """Extract records using the registry's documented object dataset; accept known field aliases."""
    rows = value if isinstance(value, list) else value.get("results") if isinstance(value, dict) and isinstance(value.get("results"), list) else next((v for v in value.values() if isinstance(v, list)), None) if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ValueError("registry JSON has no record array")
    records = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("registry contains an unrecognized publication record")
        lowered = {str(k).lower(): v for k, v in row.items()}
        def pick(*keys):
            return next((lowered[k] for k in keys if isinstance(lowered.get(k), str) and lowered[k].strip()), "")
        identity = pick("id", "bid", "identificador", "num_boletin")
        title = pick("summarynohtml", "titulo", "título", "sumario", "denominacion", "title")
        url = pick("url", "url_documento", "url_html", "enlace", "link")
        if not url and isinstance(row.get("pdf"), list):
            url = next((pdf.get("publicUrl", "") for pdf in row["pdf"] if isinstance(pdf, dict) and isinstance(pdf.get("publicUrl"), str)), "")
        if not (identity and title and url):
            raise ValueError("registry contains an incomplete publication record")
        records.append({"id": identity.strip(), "title": title.strip(), "url": url.strip()})
    if not records:
        raise ValueError("registry has no recognized publication records")
    return records


def _boja_calendar(value: Any) -> List[int]:
    if not isinstance(value, dict) or not isinstance(value.get("columns"), list) or not isinstance(value.get("rows"), list):
        raise ValueError("BOJA calendar has invalid structure")
    names = [column.get("name") for column in value["columns"] if isinstance(column, dict)]
    if "number" not in names or "date" not in names:
        raise ValueError("BOJA calendar is missing documented fields")
    number_index, date_index = names.index("number"), names.index("date")
    numbers = set()
    for row in value["rows"]:
        if not isinstance(row, list) or max(number_index, date_index) >= len(row):
            raise ValueError("BOJA calendar row has invalid structure")
        number, date_value = row[number_index], row[date_index]
        if not isinstance(number, int) or number < 1 or not isinstance(date_value, str):
            raise ValueError("BOJA calendar row has invalid values")
        numbers.add(number)
    ordered = sorted(numbers)
    if not ordered:
        raise ValueError("BOJA calendar contains no bulletin records")
    if len(ordered) > MAX_BOJA_BULLETINS:
        raise ValueError("BOJA calendar exceeds configured bulletin limit")
    return ordered


def _boja_bulletin(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, dict) or not isinstance(value.get("results"), list):
        raise ValueError("BOJA bulletin has invalid structure")
    hits = value.get("hits")
    if not isinstance(hits, int) or hits != len(value["results"]):
        raise ValueError("BOJA bulletin result set is incomplete")
    records = _flatten_records(value)
    if len(records) != hits:
        raise ValueError("BOJA bulletin contains incomplete publication records")
    return records


def _load_state(path: Path) -> Dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": STATE_VERSION, "registries": {}, "candidates": {}}
    if not isinstance(state, dict) or state.get("schema_version") != STATE_VERSION or not isinstance(state.get("registries"), dict) or not isinstance(state.get("candidates"), dict):
        raise ValueError("candidate state has invalid schema")
    return state


def discover(config_path: Path, state_path: Path, now: datetime = None) -> Dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (not isinstance(config, dict) or config.get("schema_version") != CONFIG_VERSION
            or not isinstance(config.get("registries"), list) or not config["registries"]):
        raise ValueError("invalid discovery configuration")
    state = _load_state(state_path)
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    results = []
    configured = set()
    for entry in config["registries"]:
        if not isinstance(entry, dict) or set(entry) != {"id", "url", "format", "issuer"}:
            raise ValueError("registry config entry has unexpected fields")
        rid, url, fmt, issuer = entry["id"], entry["url"], entry["format"], entry["issuer"]
        registry_host = "datos.juntadeandalucia.es" if rid == "boja" else "www.boe.es"
        parsed_registry = urlsplit(url) if isinstance(url, str) else None
        path_ok = bool(parsed_registry) and (parsed_registry.path == "/api/v0/boja/get/calendar" if rid == "boja" else re.fullmatch(r"/datosabiertos/api/boe/sumario/\d{8}", parsed_registry.path) is not None)
        query = parse_qs(parsed_registry.query) if parsed_registry else {}
        query_ok = bool(parsed_registry) and (set(query) == {"year"} and len(query["year"]) == 1 and re.fullmatch(r"\d{4}", query["year"][0]) is not None if rid == "boja" else not parsed_registry.query)
        if (rid not in REGISTRIES or rid in configured or fmt != REGISTRIES[rid]["format"] or issuer != REGISTRIES[rid]["issuer"]
                or not isinstance(url, str) or urlsplit(url).scheme != "https" or urlsplit(url).hostname != registry_host
                or not path_ok or not query_ok
                or urlsplit(url).username is not None or urlsplit(url).password is not None or urlsplit(url).fragment):
            raise ValueError("registry is not explicitly supported or has unsafe policy")
        configured.add(rid)
        old = state["registries"].get(rid, {})
        try:
            candidate_working = copy.deepcopy(state["candidates"])
            if fmt == "boe-xml":
                payload = _fetch(url, "application/xml")
                records = _boe(payload)
                bulletins = 1
            else:
                calendar_payload = _fetch(url, "application/json")
                calendar = json.loads(calendar_payload.decode("utf-8"))
                bulletin_numbers = _boja_calendar(calendar)
                response_bytes = len(calendar_payload)
                records = []
                for number in bulletin_numbers:
                    bulletin_url = "https://datos.juntadeandalucia.es/api/v0/boja/get/bulletin?" + urlencode({"year": query["year"][0], "number": number})
                    bulletin_payload = _fetch(bulletin_url, "application/json")
                    response_bytes += len(bulletin_payload)
                    if response_bytes > MAX_BOJA_TOTAL_BYTES:
                        raise ValueError("BOJA scan exceeds configured total response limit")
                    for record in _boja_bulletin(json.loads(bulletin_payload.decode("utf-8"))):
                        record["registry_url"] = bulletin_url
                        records.append(record)
                    if len(records) > MAX_RECORDS:
                        raise ValueError("record count exceeds configured limit")
                bulletins = len(bulletin_numbers)
            if len(records) > MAX_RECORDS:
                raise ValueError("record count exceeds configured limit")
            observed = 0
            rejected = 0
            for row in records:
                if not _safe_url(row["url"], issuer):
                    rejected += 1
                    continue
                identity = hashlib.sha256((issuer + "\0" + row["id"].strip().lower()).encode()).hexdigest()
                version = hashlib.sha256(json.dumps({"title": row["title"].strip(), "url": row["url"]}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
                previous = candidate_working.get(identity)
                if previous is None:
                    candidate = {"candidate_id": identity, "issuer": issuer, "registry_id": rid, "registry_url": row.get("registry_url", url), "publication_url": row["url"], "title": row["title"], "stable_identity": row["id"], "version_hash": version, "review_status": "pending", "observations": []}
                    candidate_working[identity] = candidate
                    previous = candidate
                if not previous["observations"] or previous["observations"][-1]["version_hash"] != version:
                    previous["observations"].append({"observed_at": stamp, "registry_url": row.get("registry_url", url), "version_hash": version})
                    previous.update({"title": row["title"], "publication_url": row["url"], "version_hash": version})
                    observed += 1
            state["candidates"] = candidate_working
            state["registries"][rid] = {"status": "checked", "last_attempt_at": stamp, "last_success_at": stamp, "failure": None}
            results.append({"registry_id": rid, "status": "checked", "bulletins_checked": bulletins, "new_or_changed_observations": observed, "rejected_unsafe_records": rejected})
        except Exception as error:
            state["registries"][rid] = {**old, "status": "unchecked", "last_attempt_at": stamp, "failure": type(error).__name__}
            results.append({"registry_id": rid, "status": "unchecked", "failure": type(error).__name__})
    for rid in REGISTRIES:
        if rid not in configured:
            results.append({"registry_id": rid, "status": "unchecked", "failure": "not_configured"})
    for issuer in UNCHECKED_ISSUERS:
        results.append({"registry_id": issuer.lower(), "issuer": issuer, "status": "unchecked", "failure": "no_verified_machine_readable_registry"})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp = state_path.with_name(state_path.name + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, state_path)
    return {"registries": results, "candidate_count": len(state["candidates"]), "state": str(state_path)}
