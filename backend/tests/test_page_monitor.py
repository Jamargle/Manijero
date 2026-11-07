"""Offline tests for the developer-only official-page change monitor."""

import hashlib
import json
import socket
import urllib.request
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

import pytest

from app import page_monitor
from app.page_monitor import (
    MAX_EXCERPT_CHARS,
    MAX_EXCERPTS,
    MAX_RESPONSE_BYTES,
    MAX_TEXT_CHARS,
    PAGE_HOSTS,
    PageMonitorError,
    PageMonitorWriteError,
    _diff,
    _extract_segments,
    _SameHostRedirect,
    main,
    run,
    validate_config,
)
from app.source_catalog import APPROVED_HOSTS, ISSUER_ALLOWED_HOSTS

FIXTURES = Path(__file__).parent / "fixtures" / "page_monitor"
NOW = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)

HOSTS = {
    "FEGA": "www.fega.gob.es",
    "MAPA": "www.mapa.gob.es",
    "Junta de Andalucía": "www.juntadeandalucia.es",
}


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Prove the focused suite never opens a socket."""

    def blocked(*args, **kwargs):
        raise AssertionError("page-monitor tests must stay offline")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def page_headers(content_type: str = "text/html; charset=utf-8",
                 etag: str = None, last_modified: str = None) -> Message:
    headers = Message()
    headers["Content-Type"] = content_type
    if etag:
        headers["ETag"] = etag
    if last_modified:
        headers["Last-Modified"] = last_modified
    return headers


def page_source(source_id: str, issuer: str, path: str = "/pac") -> dict:
    return {"id": source_id, "issuer": issuer, "url": "https://{}{}".format(HOSTS[issuer], path)}


def config(*sources: dict) -> dict:
    return {"sources": list(sources)}


def install(monkeypatch, responses: dict) -> list:
    calls = []

    def fake_request(source, previous):
        calls.append((source["id"], dict(previous)))
        response = responses[source["id"]]
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(page_monitor, "_request", fake_request)
    return calls


def response(payload: bytes, content_type: str = "text/html; charset=utf-8",
             status: int = 200, etag: str = None, last_modified: str = None):
    return status, page_headers(content_type, etag, last_modified), payload


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_config(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "page-monitor.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_config_accepts_the_three_first_party_pairs():
    configured = validate_config(config(
        page_source("fega-pac", "FEGA"),
        page_source("mapa-pac", "MAPA"),
        page_source("junta-pac", "Junta de Andalucía"),
    ))
    assert [source["id"] for source in configured] == ["fega-pac", "mapa-pac", "junta-pac"]


def test_page_hosts_are_contained_in_the_approved_allowlist():
    page_hosts = set(host for hosts in PAGE_HOSTS.values() for host in hosts)
    assert page_hosts <= APPROVED_HOSTS
    for issuer, hosts in PAGE_HOSTS.items():
        assert set(hosts) <= set(ISSUER_ALLOWED_HOSTS[issuer])


def test_explicit_default_port_is_accepted():
    source = page_source("fega-pac", "FEGA")
    source["url"] = source["url"].replace("www.fega.gob.es", "www.fega.gob.es:443")
    assert validate_config(config(source))[0]["url"].endswith(":443/pac")


@pytest.mark.parametrize("bad_url", [
    "http://www.fega.gob.es/pac",
    "https://www.fega.gob.es:8443/pac",
    "https://user:pass@www.fega.gob.es/pac",
    "https://www.fega.gob.es/pac#top",
    "https://www.fega.gob.es/",
    "https://www.fega.gob.es",
    "https://www.fega.gob.es.evil.example/pac",
    "https://www.mapa.gob.es/pac",
    "https://boe.es/pac",
    "ftp://www.fega.gob.es/pac",
])
def test_config_rejects_unsafe_urls(bad_url):
    source = page_source("fega-pac", "FEGA")
    source["url"] = bad_url
    with pytest.raises(PageMonitorError):
        validate_config(config(source))


@pytest.mark.parametrize("bad_url", [
    "http://www.mapa.gob.es/pac",
    "https://www.mapa.gob.es:8443/pac",
    "https://user:pass@www.mapa.gob.es/pac",
    "https://www.mapa.gob.es/pac#top",
    "https://www.mapa.gob.es/",
    "https://www.mapa.gob.es.evil.example/pac",
])
def test_unsafe_page_url_fails_that_page_without_hiding_others(monkeypatch, tmp_path, bad_url):
    good = page_source("fega-pac", "FEGA")
    bad = {"id": "mapa-pac", "issuer": "MAPA", "url": bad_url}
    monkeypatch.setattr(
        page_monitor, "_request",
        lambda source, previous: response(fixture("baseline.html")),
    )
    state_path = tmp_path / "state.json"
    report = run(config(bad, good), state_path, tmp_path / "report.json", now=NOW)
    by_id = {page["id"]: page for page in report["pages"]}

    assert by_id["mapa-pac"]["status"] == "failed"
    assert by_id["mapa-pac"]["failure"] == "upstream request failed"
    assert by_id["fega-pac"]["status"] == "first_seen"
    assert list(read_json(state_path)["pages"]) == ["fega-pac"]


def test_config_rejects_bad_shape_ids_issuers_and_duplicates():
    source = page_source("fega-pac", "FEGA")
    for value in (
        {"sources": []},
        {"sources": [source], "extra": True},
        {"sources": [dict(source, issuer="BOE")]},
        {"sources": [dict(source, id="Bad Id")]},
        {"sources": [source, dict(source, id="fega-other")]},
        {"sources": [source, dict(source, id="mapa-pac", issuer="MAPA", url=source["url"])]},
        {"sources": [{"id": "fega-pac", "issuer": "FEGA"}]},
    ):
        with pytest.raises(PageMonitorError):
            validate_config(value)


def test_first_run_records_a_baseline(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(
        fixture("baseline.html"), etag='"v1"', last_modified="Tue, 06 Nov 2026 10:00:00 GMT",
    )})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    report = run(config(source), state_path, report_path, now=NOW)
    page = report["pages"][0]
    record = read_json(state_path)["pages"]["fega-pac"]
    segments = record["segments"]
    joined = "\n".join(segments)

    assert page["status"] == "first_seen"
    assert page["first_seen"] is True
    assert page["content_changed"] is False
    assert page["text_changed"] is False
    assert page["content_sha256"] == hashlib.sha256(fixture("baseline.html")).hexdigest()
    assert page["text_sha256"] == hashlib.sha256(joined.encode("utf-8")).hexdigest()
    assert record["url"] == source["url"]
    assert record["issuer"] == "FEGA"
    assert record["last_attempt_at"] == NOW.isoformat()
    assert record["http_status"] == 200
    assert record["etag"] == '"v1"'
    assert record["last_modified"] == "Tue, 06 Nov 2026 10:00:00 GMT"
    assert "window.baseline" not in joined
    assert "internal comment" not in joined
    assert "15 de mayo de 2026" in joined


def test_identical_repeat_is_unchanged(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"), etag='"v1"')})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)
    before = read_json(state_path)["pages"]["fega-pac"]

    report = run(config(source), state_path, report_path, now=LATER)
    page = report["pages"][0]
    after = read_json(state_path)["pages"]["fega-pac"]

    assert page["status"] == "unchanged"
    assert page["first_seen"] is False
    assert page["added"]["count"] == 0
    assert page["changed"]["count"] == 0
    assert page["removed"]["count"] == 0
    assert after["content_sha256"] == before["content_sha256"]
    assert after["text_sha256"] == before["text_sha256"]
    assert after["segments"] == before["segments"]
    assert after["etag"] == before["etag"]
    assert after["last_success_at"] == LATER.isoformat()


def test_changed_page_reports_only_text_deltas(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)

    install(monkeypatch, {"fega-pac": response(fixture("changed.html"))})
    page = run(config(source), state_path, report_path, now=LATER)["pages"][0]

    assert page["status"] == "changed"
    assert page["content_changed"] is True
    assert page["text_changed"] is True
    assert page["added"]["count"] == 1
    assert page["removed"]["count"] == 1
    assert page["changed"]["count"] == 1
    assert page["added"]["excerpts"][0]["text"] == "Nueva nota: croquis de la parcela."
    assert page["removed"]["excerpts"][0]["text"] == "Documento que ya no aparece."
    changed = page["changed"]["excerpts"][0]
    assert changed["before"] == "Plazo de solicitud: 15 de mayo de 2026."
    assert changed["after"] == "Plazo de solicitud: 20 de mayo de 2026."


def test_markup_only_change_reports_content_not_text(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)

    install(monkeypatch, {"fega-pac": response(fixture("markup_only.html"))})
    page = run(config(source), state_path, report_path, now=LATER)["pages"][0]

    assert page["status"] == "changed"
    assert page["content_changed"] is True
    assert page["text_changed"] is False
    assert page["added"]["count"] == 0
    assert page["removed"]["count"] == 0
    assert page["changed"]["count"] == 0
    assert page["added"]["excerpts"] == []
    assert page["removed"]["excerpts"] == []
    assert page["changed"]["excerpts"] == []


def test_unsupported_content_type_fails_without_a_snapshot(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(b"%PDF-1.7", "application/pdf")})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    page = run(config(source), state_path, report_path, now=NOW)["pages"][0]

    assert page["status"] == "failed"
    assert page["failure"] == "unsupported content type"
    assert page["content_sha256"] is None
    assert read_json(state_path)["pages"] == {}


@pytest.mark.parametrize("declared", [None, ""])
def test_missing_or_empty_content_type_is_unsupported(monkeypatch, tmp_path, declared):
    source = page_source("fega-pac", "FEGA")
    headers = Message()
    if declared is not None:
        headers["Content-Type"] = declared
    install(monkeypatch, {"fega-pac": (200, headers, fixture("baseline.html"))})
    page = run(
        config(source), tmp_path / "state.json", tmp_path / "report.json", now=NOW,
    )["pages"][0]

    assert page["status"] == "failed"
    assert page["failure"] == "unsupported content type"
    assert read_json(tmp_path / "state.json")["pages"] == {}


def test_size_limit_and_text_bounds_fail_closed(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(b"x" * (MAX_RESPONSE_BYTES + 1))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    assert run(config(source), state_path, report_path, now=NOW)["pages"][0]["failure"] == (
        "response exceeded size limit"
    )

    install(monkeypatch, {"fega-pac": response(fixture("oversized.html"))})
    assert run(config(source), state_path, report_path, now=NOW)["pages"][0]["failure"] == (
        "page text exceeded limit"
    )

    install(monkeypatch, {"fega-pac": response(b"<p>" + b"a" * (MAX_TEXT_CHARS + 1) + b"</p>")})
    assert run(config(source), state_path, report_path, now=NOW)["pages"][0]["failure"] == (
        "page text exceeded limit"
    )


def test_empty_text_fails_closed(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("empty_text.html"))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    page = run(config(source), state_path, report_path, now=NOW)["pages"][0]

    assert page["status"] == "failed"
    assert page["failure"] == "page had no readable text"
    assert read_json(state_path)["pages"] == {}


def test_unsupported_status_fails(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"), status=206)})
    page = run(
        config(source), tmp_path / "state.json", tmp_path / "report.json", now=NOW,
    )["pages"][0]
    assert page["failure"] == "upstream returned HTTP 206"


def test_304_requires_a_prior_snapshot(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": (304, page_headers(), b"")})
    page = run(
        config(source), tmp_path / "state.json", tmp_path / "report.json", now=NOW,
    )["pages"][0]
    assert page["status"] == "failed"
    assert page["failure"] == "received 304 without a prior successful snapshot"


def test_304_with_prior_snapshot_is_unchanged(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"), etag='"v1"')})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)
    before = read_json(state_path)["pages"]["fega-pac"]

    install(monkeypatch, {"fega-pac": (304, page_headers(), b"")})
    page = run(config(source), state_path, report_path, now=LATER)["pages"][0]
    after = read_json(state_path)["pages"]["fega-pac"]

    assert page["status"] == "unchanged"
    assert page["content_sha256"] == before["content_sha256"]
    assert page["text_sha256"] == before["text_sha256"]
    assert after["content_sha256"] == before["content_sha256"]
    assert after["segments"] == before["segments"]
    assert after["etag"] == before["etag"]
    assert after["last_success_at"] == before["last_success_at"]
    assert after["last_attempt_at"] == LATER.isoformat()
    assert after["http_status"] == 304


def test_failure_preserves_last_good_state_and_next_run_diffs_against_it(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"), etag='"v1"')})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)
    original_state = state_path.read_bytes()
    original = read_json(state_path)["pages"]["fega-pac"]

    install(monkeypatch, {"fega-pac": PageMonitorError("upstream request failed")})
    page = run(config(source), state_path, report_path, now=LATER)["pages"][0]

    assert page["status"] == "failed"
    assert page["failure"] == "upstream request failed"
    assert page["content_sha256"] == original["content_sha256"]
    assert page["text_sha256"] == original["text_sha256"]
    assert state_path.read_bytes() == original_state

    install(monkeypatch, {"fega-pac": response(fixture("changed.html"))})
    changed = run(config(source), state_path, report_path, now=LATER)["pages"][0]
    assert changed["status"] == "changed"
    assert changed["changed"]["count"] == 1


def test_other_pages_still_produce_outcomes(monkeypatch, tmp_path):
    sources = config(page_source("mapa-pac", "MAPA"), page_source("fega-pac", "FEGA"))
    install(monkeypatch, {
        "mapa-pac": PageMonitorError("upstream request failed"),
        "fega-pac": response(fixture("baseline.html")),
    })
    report = run(sources, tmp_path / "state.json", tmp_path / "report.json", now=NOW)
    by_id = {page["id"]: page for page in report["pages"]}
    assert set(by_id) == {"fega-pac", "mapa-pac"}
    assert by_id["fega-pac"]["status"] == "first_seen"
    assert by_id["mapa-pac"]["status"] == "failed"


def test_redirects_reject_cross_host_scheme_port_and_credentials():
    handler = _SameHostRedirect()
    request = urllib.request.Request("https://www.fega.gob.es/pac")
    for target in (
        "https://evil.example/pac",
        "http://www.fega.gob.es/pac",
        "https://www.fega.gob.es:8443/pac",
        "https://user@www.fega.gob.es/pac",
        "https://www.fega.gob.es/pac#fragment",
    ):
        with pytest.raises(PageMonitorError, match="redirect rejected: host or scheme changed"):
            handler.redirect_request(request, None, 302, "Found", Message(), target)


def test_output_paths_are_refused_under_knowledge_before_any_request(monkeypatch, tmp_path):
    monkeypatch.setattr(
        page_monitor, "_request",
        lambda *args: pytest.fail("path validation must precede any request"),
    )
    source = page_source("fega-pac", "FEGA")
    knowledge_state = page_monitor.KNOWLEDGE_ROOT / "official-page-monitor-state.json"
    knowledge_report = page_monitor.KNOWLEDGE_ROOT / "official-page-change-report.json"

    with pytest.raises(PageMonitorError):
        run(config(source), knowledge_state, tmp_path / "report.json", now=NOW)
    with pytest.raises(PageMonitorError):
        run(config(source), tmp_path / "state.json", knowledge_report, now=NOW)
    assert not knowledge_state.exists()
    assert not knowledge_report.exists()


def test_equal_state_and_report_paths_are_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(
        page_monitor, "_request",
        lambda *args: pytest.fail("path validation must precede any request"),
    )
    path = tmp_path / "same.json"
    with pytest.raises(PageMonitorError):
        run(config(page_source("fega-pac", "FEGA")), path, path, now=NOW)


def test_invalid_state_fails_before_request_and_preserves_bytes(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    original = json.dumps({"schema_version": page_monitor.STATE_VERSION, "pages": {"fega-pac": "bad"}})
    state_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        page_monitor, "_request",
        lambda *args: pytest.fail("invalid state must fail before requesting"),
    )

    with pytest.raises(PageMonitorError, match="invalid monitoring state"):
        run(config(page_source("fega-pac", "FEGA")), state_path, tmp_path / "report.json", now=NOW)
    assert state_path.read_text(encoding="utf-8") == original


def test_state_write_failure_writes_report_first_and_keeps_old_state(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    run(config(source), state_path, report_path, now=NOW)
    original_state = state_path.read_bytes()

    install(monkeypatch, {"fega-pac": response(fixture("changed.html"))})
    original_write = page_monitor._atomic_write

    def fail_state(path, payload):
        if path == state_path.resolve():
            raise PageMonitorWriteError("cannot write state")
        return original_write(path, payload)

    monkeypatch.setattr(page_monitor, "_atomic_write", fail_state)
    with pytest.raises(PageMonitorWriteError):
        run(config(source), state_path, report_path, now=LATER)

    assert read_json(report_path)["pages"][0]["status"] == "changed"
    assert state_path.read_bytes() == original_state

    monkeypatch.setattr(page_monitor, "_atomic_write", original_write)
    assert run(config(source), state_path, report_path, now=LATER)["pages"][0]["status"] == "changed"


def test_report_is_deterministic_and_ordered_by_id(monkeypatch, tmp_path):
    sources = config(page_source("mapa-pac", "MAPA"), page_source("fega-pac", "FEGA"))
    responses = {
        "mapa-pac": response(fixture("baseline.html")),
        "fega-pac": response(fixture("markup_only.html")),
    }

    reports = []
    for directory in (tmp_path / "a", tmp_path / "b"):
        install(monkeypatch, responses)
        report = run(sources, directory / "state.json", directory / "report.json", now=NOW)
        reports.append((directory / "report.json").read_bytes())
        assert [page["id"] for page in report["pages"]] == ["fega-pac", "mapa-pac"]
    assert reports[0] == reports[1]


def test_report_has_no_legal_or_currency_fields_and_stores_no_raw_markup(monkeypatch, tmp_path):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("changed.html"))})
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    report = run(config(source), state_path, report_path, now=NOW)
    report_text = report_path.read_text(encoding="utf-8").lower()
    state_text = state_path.read_text(encoding="utf-8").lower()
    forbidden_fields = ("currency", "validity", "legal_effect", "recommendation")

    for page in report["pages"]:
        for field in forbidden_fields:
            assert field not in page
    assert "window." not in report_text
    assert "window." not in state_text
    assert "<script" not in report_text
    assert "<script" not in state_text


def test_extraction_skips_scripts_styles_comments_and_normalizes():
    segments = _extract_segments(fixture("baseline.html"), "text/html", "utf-8")
    joined = "\n".join(segments)
    assert "window.baseline" not in joined
    assert "color: red" not in joined
    assert "internal comment" not in joined
    assert "15 de mayo de 2026" in joined

    normalized = _extract_segments("<p>Ａ　Ｂ</p>".encode("utf-8"), "text/html", "utf-8")
    assert normalized == ["A B"]


def test_plain_text_and_charset_fallback():
    assert _extract_segments(fixture("plain.txt"), "text/plain", "utf-8") == [
        "Primera línea con espacios.",
        "Segunda línea con acentos: explotación.",
    ]
    payload = "<p>Explotación</p>".encode("cp1252")
    assert _extract_segments(payload, "text/html", None) == ["Explotación"]


def test_diff_counts_and_excerpt_caps():
    old = ["line {}".format(index) for index in range(100)]
    new = ["changed {}".format(index) for index in range(100)]
    diff = _diff(old, new)
    total_excerpts = sum(
        len(diff[group]["excerpts"]) for group in ("added", "removed", "changed")
    )
    assert diff["changed"]["count"] == 100
    assert diff["added"]["count"] == 0
    assert diff["removed"]["count"] == 0
    assert total_excerpts == MAX_EXCERPTS
    for group in ("added", "removed", "changed"):
        for excerpt in diff[group]["excerpts"]:
            for value in excerpt.values():
                assert len(value) <= MAX_EXCERPT_CHARS

    long_diff = _diff(["a" * 1000], ["b" * 1000])
    assert long_diff["changed"]["excerpts"][0]["before"] == "a" * 240
    assert long_diff["changed"]["excerpts"][0]["after"] == "b" * 240


def test_diff_pairs_replace_and_keeps_remainders():
    added = _diff(["a", "b"], ["a", "x", "y"])
    assert added["changed"]["count"] == 1
    assert added["added"]["count"] == 1
    assert added["removed"]["count"] == 0

    removed = _diff(["a", "x", "y"], ["a", "b"])
    assert removed["changed"]["count"] == 1
    assert removed["added"]["count"] == 0
    assert removed["removed"]["count"] == 1


def test_main_prints_result_lines_and_exits_1_on_failure(monkeypatch, tmp_path, capsys):
    sources = config(page_source("fega-pac", "FEGA"), page_source("mapa-pac", "MAPA"))
    install(monkeypatch, {
        "fega-pac": response(fixture("baseline.html")),
        "mapa-pac": PageMonitorError("upstream request failed"),
    })
    config_path = write_config(tmp_path, sources)
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    code = main([
        "--config", str(config_path),
        "--state", str(state_path),
        "--report", str(report_path),
    ], now=NOW)
    output = capsys.readouterr().out

    assert code == 1
    assert "Result: fega-pac: first seen." in output
    assert "Result: mapa-pac: could not be checked (upstream request failed)." in output
    assert "Result: 2 pages checked: 1 first seen, 0 changed, 0 unchanged, 1 failed." in output
    assert "Report: {}".format(report_path) in output
    assert "15 de mayo" not in output


def test_main_exits_0_when_every_page_is_checked(monkeypatch, tmp_path, capsys):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    config_path = write_config(tmp_path, config(source))
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"

    code = main([
        "--config", str(config_path),
        "--state", str(state_path),
        "--report", str(report_path),
        "--now", NOW.isoformat(),
    ])
    output = capsys.readouterr().out

    assert code == 0
    assert "Result: fega-pac: first seen." in output
    assert "Result: 1 page checked: 1 first seen, 0 changed, 0 unchanged, 0 failed." in output


def test_main_changed_line_uses_counts(monkeypatch, tmp_path, capsys):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    config_path = write_config(tmp_path, config(source))
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    main(["--config", str(config_path), "--state", str(state_path),
          "--report", str(report_path)], now=NOW)
    capsys.readouterr()

    install(monkeypatch, {"fega-pac": response(fixture("changed.html"))})
    code = main(["--config", str(config_path), "--state", str(state_path),
                 "--report", str(report_path)], now=LATER)
    output = capsys.readouterr().out

    assert code == 0
    assert "Result: fega-pac: 1 added, 1 changed, 1 removed." in output
    assert "15 de mayo" not in output
    assert "20 de mayo" not in output
    assert "Nueva nota" not in output


def test_main_exits_2_for_config_and_now_errors(tmp_path, capsys):
    bad_config = tmp_path / "bad.json"
    bad_config.write_text("{not json", encoding="utf-8")
    code = main([
        "--config", str(bad_config),
        "--state", str(tmp_path / "state.json"),
        "--report", str(tmp_path / "report.json"),
    ], now=NOW)
    assert code == 2
    assert "Result: could not start" in capsys.readouterr().out

    config_path = write_config(tmp_path, config(page_source("fega-pac", "FEGA")))
    code = main([
        "--config", str(config_path),
        "--state", str(tmp_path / "state.json"),
        "--report", str(tmp_path / "report.json"),
        "--now", "not-a-timestamp",
    ])
    assert code == 2
    assert "Result: could not start" in capsys.readouterr().out


def test_main_exits_2_when_state_write_fails(monkeypatch, tmp_path, capsys):
    source = page_source("fega-pac", "FEGA")
    install(monkeypatch, {"fega-pac": response(fixture("baseline.html"))})
    config_path = write_config(tmp_path, config(source))
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    original_write = page_monitor._atomic_write

    def fail_state(path, payload):
        if path == state_path.resolve():
            raise PageMonitorWriteError("cannot write state")
        return original_write(path, payload)

    monkeypatch.setattr(page_monitor, "_atomic_write", fail_state)
    code = main(["--config", str(config_path), "--state", str(state_path),
                 "--report", str(report_path)], now=NOW)

    assert code == 2
    assert "Result: could not write the report or state." in capsys.readouterr().out
    assert report_path.exists()
    assert not state_path.exists()
