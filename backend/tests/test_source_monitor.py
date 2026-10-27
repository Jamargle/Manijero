import hashlib
import json
from email.message import Message

import pytest

from app.source_monitor import MonitorError, scan, validate_sources


SOURCE = {"id": "boja", "url": "https://www.juntadeandalucia.es/boja/distribucion/s51.xml", "format": "rss"}
FEED = b'<rss version="2.0"><channel><title>Official feed</title></channel></rss>'


def test_rejects_arbitrary_and_lookalike_hosts():
    for url in ("https://evil.example/feed", "https://juntadeandalucia.es.evil/feed",
                "http://www.juntadeandalucia.es/feed", "https://www.juntadeandalucia.es/"):
        with pytest.raises(MonitorError):
            validate_sources([{**SOURCE, "url": url}])


def test_scan_records_stable_hash_validators_and_success(monkeypatch, tmp_path):
    headers = Message()
    headers["ETag"] = '"v1"'
    headers["Last-Modified"] = "Tue, 01 Jan 2026 00:00:00 GMT"
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (200, headers, FEED))
    path = tmp_path / "state.json"
    result = scan([SOURCE], path)
    entry = result["sources"][0]
    assert result["success"] is True
    assert entry["changed"] is True
    assert entry["etag"] == '"v1"'
    assert entry["content_sha256"] == hashlib.sha256(FEED).hexdigest()
    assert json.loads(path.read_text())["sources"]["boja"]["last_success_at"]


def test_identical_content_is_not_a_change(monkeypatch, tmp_path):
    headers = Message()
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (200, headers, FEED))
    path = tmp_path / "state.json"
    scan([SOURCE], path)
    assert scan([SOURCE], path)["sources"][0]["changed"] is False


def test_failure_keeps_last_good_snapshot_and_is_observable(monkeypatch, tmp_path):
    headers = Message()
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (200, headers, FEED))
    path = tmp_path / "state.json"
    scan([SOURCE], path)
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (_ for _ in ()).throw(MonitorError("malformed upstream rss feed")))
    report = scan([SOURCE], path)
    entry = report["sources"][0]
    assert report["success"] is False
    assert entry["failure"] == "malformed upstream rss feed"
    assert entry["content_sha256"] == hashlib.sha256(FEED).hexdigest()
    assert entry["last_success_at"]


def test_malformed_payload_fails_without_overwriting_snapshot(monkeypatch, tmp_path):
    headers = Message()
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (200, headers, b"<rss"))
    report = scan([SOURCE], tmp_path / "state.json")
    assert report["sources"][0]["status"] == "failure"
    assert report["sources"][0]["content_sha256"] is None


def test_304_requires_prior_success(monkeypatch, tmp_path):
    monkeypatch.setattr("app.source_monitor._request", lambda source, previous: (304, {}, b""))
    result = scan([SOURCE], tmp_path / "state.json")
    assert result["success"] is False
    assert "prior successful snapshot" in result["sources"][0]["failure"]


def test_json_api_payload_is_validated(monkeypatch, tmp_path):
    source = {"id": "boe", "url": "https://www.boe.es/datosabiertos/api/api.php", "format": "json"}
    monkeypatch.setattr("app.source_monitor._request", lambda *args: (200, {}, b'{"results":[]}'))
    assert scan([source], tmp_path / "state.json")["success"] is True
