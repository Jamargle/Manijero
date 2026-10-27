import hashlib
import importlib.util
import json
import subprocess
import sys
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path

import pytest

from app.document_ingestion import (
    EXTRACTOR,
    MAX_DOCUMENT_BYTES,
    FetchedDocument,
    IngestionError,
    _AllowlistedRedirect,
    _classify,
    _decode_pdf_bytes,
    _extract,
    _fetch,
    _files_present,
    _url_allowed,
    ingest,
    load_discovery_candidates,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "document_ingestion"
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
PDF_BYTES = (FIXTURES / "valid_document.pdf").read_bytes()
HTML_BYTES = (FIXTURES / "valid_document.html").read_bytes()


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def candidate(index=1, **overrides):
    identity = "BOE-A-2026-{}".format(index)
    data = {
        "candidate_id": _hash("candidate-{}".format(index).encode()),
        "issuer": "BOE",
        "registry_id": "boe",
        "registry_url": "https://www.boe.es/datosabiertos/api/boe/sumario/20261027",
        "publication_url": "https://www.boe.es/boe/dias/2026/10/27/pdfs/{}.pdf".format(identity),
        "title": "Documento sintético {}".format(index),
        "stable_identity": identity,
        "version_hash": _hash("version-1".encode()),
        "review_status": "pending",
    }
    data.update(overrides)
    return data


def write_discovery(tmp_path, candidates):
    path = tmp_path / "discovery.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "official-discovery-state-v1",
                "registries": {},
                "candidates": {item["candidate_id"]: item for item in candidates},
            }
        ),
        encoding="utf-8",
    )
    return path


def stub_fetch(monkeypatch, responses):
    """Map publication URL (or ``*``) to FetchedDocument or an exception/bytes."""
    calls = []

    def fake(url, allowed_hosts=None):
        calls.append(url)
        response = responses.get(url, responses.get("*"))
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(url)
        if isinstance(response, bytes):
            raise AssertionError("test must state the response content type")
        return response

    monkeypatch.setattr("app.document_ingestion._fetch", fake)
    return calls


def defaults(tmp_path):
    return (
        write_discovery(tmp_path, [candidate()]),
        tmp_path / "state.json",
        tmp_path / "quarantine",
    )


def canonical_digests():
    return {
        name: hashlib.sha256((ROOT / "knowledge" / name).read_bytes()).hexdigest()
        for name in ("source_catalog.json", "passages.json")
    }


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def build_pdf(page_count: int, filler_count: int = 0) -> bytes:
    kids = " ".join(f"{3 + index} 0 R" for index in range(page_count))
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {page_count} >>\nendobj\n",
    ]
    for index in range(page_count):
        page, content = 3 + index, 3 + page_count + index
        objects.append(f"{page} 0 obj\n<< /Type /Page /Parent 2 0 R /Contents {content} 0 R >>\nendobj\n")
    for index in range(page_count):
        content = f"BT /F1 12 Tf 72 720 Td (Pagina {index + 1}) Tj ET"
        objects.append(f"{3 + page_count + index} 0 obj\n<< >>\nstream\n{content}\nendstream\nendobj\n")
    for index in range(filler_count):
        number = 3 + 2 * page_count + index
        objects.append(f"{number} 0 obj\n<< /Filler {number} >>\nendobj\n")
    return ("%PDF-1.4\n" + "".join(objects)).encode("ascii")


def load_cli_module():
    path = ROOT / "backend/scripts/ingest_official_documents.py"
    spec = importlib.util.spec_from_file_location("ingest_official_documents_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pdf_candidate_is_quarantined_with_pages_and_provenance(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    before = canonical_digests()
    calls = stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})

    report = ingest(discovery, state_path, quarantine, now=NOW)

    assert calls == [candidate()["publication_url"]]
    assert report["summary"] == {"extracted": 1, "unchanged": 0, "failed": 0, "rejected": 0}
    entry = report["documents"][0]
    assert entry["status"] == "extracted" and entry["failure"] is None
    assert entry["original_sha256"] == _hash(PDF_BYTES)
    assert entry["page_count"] == 2 and entry["block_count"] == 3

    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    assert record["review_status"] == "pending"
    assert record["status"] == "extracted"
    assert record["extractor"] == "manijero-document-extractor-v1"
    assert record["byte_size"] == len(PDF_BYTES)
    assert record["original_path"].endswith(".pdf")
    assert (quarantine / record["original_path"]).read_bytes() == PDF_BYTES
    assert hashlib.sha256((quarantine / record["original_path"]).read_bytes()).hexdigest() == entry["original_sha256"]

    document = json.loads((quarantine / record["extracted_path"]).read_text(encoding="utf-8"))
    assert document["schema_version"] == "official-ingestion-document-v1"
    assert [block["page"] for block in document["blocks"]] == [1, 2, 2]
    assert [block["section"] for block in document["blocks"]] == ["Página 1", "Página 2", "Página 2"]
    assert [block["text"] for block in document["blocks"]] == ["Primera pagina", "Segunda pagina", "Requisitos"]
    assert _hash(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n") == record["extracted_text_sha256"]

    assert canonical_digests() == before
    assert not str(quarantine.resolve()).startswith(str((ROOT / "knowledge").resolve()))


def test_html_candidate_preserves_section_structure_and_skips_script(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": FetchedDocument(HTML_BYTES, "text/html", "utf-8")})

    report = ingest(discovery, state_path, quarantine, now=NOW)

    assert report["summary"]["extracted"] == 1
    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    document = json.loads((quarantine / record["extracted_path"]).read_text(encoding="utf-8"))
    assert document["title"] == "Resolución sintética de prueba"
    assert document["media_type"] == "html"
    assert record["page_count"] is None
    assert all(block["page"] is None for block in document["blocks"])
    assert [block["text"] for block in document["blocks"] if block["kind"] == "heading"] == [
        "Requisitos",
        "Documentación",
    ]
    sections = [block["section"] for block in document["blocks"]]
    assert "Requisitos" in sections
    assert "Requisitos > Documentación" in sections
    assert sections.count("Requisitos > Documentación") == 3
    joined = " ".join(block["text"] for block in document["blocks"])
    assert "Documento sintético de prueba con un plazo ficticio." in joined
    assert "Primer documento ficticio." in joined
    assert "no debe aparecer" not in joined
    assert "color: red" not in joined


def test_flate_compressed_pdf_stream_is_extracted(tmp_path, monkeypatch):
    content = b"BT /F1 12 Tf 72 720 Td (Contenido comprimido) Tj ET"
    compressed = zlib.compress(content)
    payload = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n"
        + compressed + b"\nendstream\nendobj\n"
    )
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": FetchedDocument(payload, "application/pdf", None)})

    ingest(discovery, state_path, quarantine, now=NOW)

    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    document = json.loads((quarantine / record["extracted_path"]).read_text(encoding="utf-8"))
    assert [block["text"] for block in document["blocks"]] == ["Contenido comprimido"]


@pytest.mark.parametrize(
    ("overrides", "failure"),
    [
        ({"publication_url": "http://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf"}, "unsafe_destination"),
        ({"publication_url": "https://boe.es.example.com/x.pdf"}, "unsafe_destination"),
        ({"publication_url": "https://juntadeandalucia.es/x.pdf"}, "unsafe_destination"),
        ({"publication_url": "https://user:secret@www.boe.es/x.pdf"}, "unsafe_destination"),
        ({"publication_url": "https://www.boe.es/"}, "unsafe_destination"),
        ({"publication_url": "https://www.boe.es/x.pdf#fragment"}, "unsafe_destination"),
        ({"publication_url": "https://www.boe.es:8443/x.pdf"}, "unsafe_destination"),
        ({"issuer": "Ayuntamiento"}, "unsupported_candidate"),
        ({"review_status": "approved"}, "unsupported_candidate"),
        ({"version_hash": "not-a-hash"}, "unsupported_candidate"),
        ({"registry_url": "http://www.boe.es/registry"}, "unsupported_candidate"),
    ],
)
def test_unsafe_or_incomplete_candidates_are_rejected_without_fetch(tmp_path, monkeypatch, overrides, failure):
    discovery = write_discovery(tmp_path, [candidate(**overrides)])
    stub_fetch(monkeypatch, {"*": AssertionError("a rejected candidate must never be fetched")})

    report = ingest(discovery, tmp_path / "state.json", tmp_path / "quarantine", now=NOW)

    entry = report["documents"][0]
    assert entry["status"] == "rejected"
    assert entry["failure"] == failure
    assert report["summary"]["rejected"] == 1


def test_redirect_policy_allows_only_bounded_same_issuer_https_targets():
    allowed = ("www.boe.es", "boe.es")
    handler = _AllowlistedRedirect(allowed)
    request = urllib.request.Request("https://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf")

    redirected = handler.redirect_request(
        request, None, 307, None, Message(), "https://boe.es/boe/dias/2026/10/27/pdfs/x.pdf"
    )
    assert redirected.full_url == "https://boe.es/boe/dias/2026/10/27/pdfs/x.pdf"

    for target in (
        "http://boe.es/boe/dias/2026/10/27/pdfs/x.pdf",
        "https://evil.example/boe.pdf",
        "https://www.juntadeandalucia.es/eboja/2026/1/x.pdf",
        "https://user:pass@boe.es/boe.pdf",
        "https://www.boe.es/",
        "https://www.boe.es/boe.pdf#fragment",
        "https://www.boe.es:8443/boe.pdf",
    ):
        with pytest.raises(IngestionError) as raised:
            handler.redirect_request(request, None, 307, None, Message(), target)
        assert raised.value.failure == "redirect_rejected"

    for _ in range(2):
        handler.redirect_request(request, None, 307, None, Message(), "https://boe.es/boe.pdf")
    with pytest.raises(IngestionError) as raised:
        handler.redirect_request(request, None, 307, None, Message(), "https://boe.es/boe.pdf")
    assert raised.value.failure == "redirect_rejected"


def test_url_allowlist_is_exact_https_only_and_rejects_unsafe_parts():
    allowed = ("boe.es", "www.boe.es")
    assert _url_allowed("https://boe.es/boe.pdf", allowed)
    assert _url_allowed("https://www.boe.es/boe.pdf", allowed)
    assert not _url_allowed("http://boe.es/boe.pdf", allowed)
    assert not _url_allowed("https://boe.es.example.com/boe.pdf", allowed)
    assert not _url_allowed("https://www.juntadeandalucia.es/eboja/x.pdf", allowed)
    assert not _url_allowed("https://user:pass@boe.es/boe.pdf", allowed)
    assert not _url_allowed("https://boe.es/", allowed)
    assert not _url_allowed("https://boe.es/boe.pdf#fragment", allowed)
    assert not _url_allowed("https://boe.es:8443/boe.pdf", allowed)
    assert not _url_allowed(None, allowed)


def test_fetch_refuses_unsafe_redirects_and_reports_upstream_failures(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": IngestionError("redirect_rejected")})
    report = ingest(discovery, state_path, quarantine, now=NOW)
    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "redirect_rejected"


class _FakeResponse:
    def __init__(self, payload, content_type, url, status=200):
        self._payload = payload
        self.status = status
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self, size):
        return self._payload[:size]

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_opener(response, monkeypatch):
    class Opener:
        def open(self, request, timeout):
            return response

    monkeypatch.setattr("app.document_ingestion.urllib.request.build_opener", lambda handler: Opener())


def test_actual_fetch_enforces_size_type_and_final_url_safety(monkeypatch):
    hosts = ("www.boe.es", "boe.es")
    url = candidate()["publication_url"]

    fake_opener(_FakeResponse(b"x" * (MAX_DOCUMENT_BYTES + 1), "application/pdf", url), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _fetch(url, hosts)
    assert raised.value.failure == "size_limit_exceeded"

    fake_opener(_FakeResponse(PDF_BYTES, "text/html", url), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _classify(_fetch(url, hosts))
    assert raised.value.failure == "content_type_mismatch"

    fake_opener(_FakeResponse(PDF_BYTES, "application/octet-stream", url), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _classify(_fetch(url, hosts))
    assert raised.value.failure == "unsupported_content_type"

    # A redirect to a different approved host for the same issuer is allowed.
    fake_opener(
        _FakeResponse(PDF_BYTES, "application/pdf", "https://boe.es/boe/dias/2026/10/27/pdfs/x.pdf"),
        monkeypatch,
    )
    assert _fetch(url, hosts).payload == PDF_BYTES

    # A response whose final URL is not on the issuer's allowlist fails closed.
    fake_opener(_FakeResponse(PDF_BYTES, "application/pdf", "https://evil.example/x.pdf"), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _fetch(url, hosts)
    assert raised.value.failure == "redirect_rejected"

    # A non-allowlisted initial URL never reaches the opener.
    fake_opener(_FakeResponse(PDF_BYTES, "application/pdf", url), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _fetch(url, ("example.com",))
    assert raised.value.failure == "unsafe_destination"

    fake_opener(_FakeResponse(PDF_BYTES, "application/pdf", url, status=206), monkeypatch)
    with pytest.raises(IngestionError) as raised:
        _fetch(url, hosts)
    assert raised.value.failure == "http_error"


def test_malformed_and_textless_documents_fail_closed(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    malformed = (FIXTURES / "malformed.pdf").read_bytes()
    stub_fetch(monkeypatch, {"*": FetchedDocument(malformed, "application/pdf", None)})
    report = ingest(discovery, state_path, quarantine, now=NOW)
    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "malformed_document"
    assert not quarantine.joinpath(candidate()["candidate_id"], "extracted-" + _hash(malformed) + ".json").exists()

    textless = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 5 >>\nstream\nBT ET\nendstream\nendobj\n"
    )
    stub_fetch(monkeypatch, {"*": FetchedDocument(textless, "application/pdf", None)})
    report = ingest(discovery, state_path, quarantine, now=NOW)
    assert report["documents"][0]["failure"] == "no_extractable_text"


def test_pdf_page_limit_fails_closed(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    payload = build_pdf(501)
    stub_fetch(monkeypatch, {"*": FetchedDocument(payload, "application/pdf", None)})

    report = ingest(discovery, state_path, quarantine, now=NOW)

    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "size_limit_exceeded"


def test_pdf_object_limit_fails_closed(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    payload = build_pdf(500, filler_count=18999)
    stub_fetch(monkeypatch, {"*": FetchedDocument(payload, "application/pdf", None)})

    report = ingest(discovery, state_path, quarantine, now=NOW)

    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "size_limit_exceeded"


def test_pdf_page_and_object_boundaries_succeed(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    payload = build_pdf(500, filler_count=18998)
    stub_fetch(monkeypatch, {"*": FetchedDocument(payload, "application/pdf", None)})

    report = ingest(discovery, state_path, quarantine, now=NOW)

    entry = report["documents"][0]
    assert entry["status"] == "extracted"
    assert entry["failure"] is None
    assert entry["page_count"] == 500
    assert entry["block_count"] == 500
    assert entry["original_sha256"] == _hash(payload)


def test_extractor_revision_reextracts_and_preserves_prior_files(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    calls = stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    ingest(discovery, state_path, quarantine, now=NOW)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    record = state["candidates"][candidate()["candidate_id"]]
    original_path = quarantine / record["original_path"]
    extracted_path = quarantine / record["extracted_path"]
    extracted_before = extracted_path.read_bytes()
    prior_digest = _hash(b"prior-version")
    prior_file = quarantine / candidate()["candidate_id"] / "original-{}.pdf".format(prior_digest)
    prior_file.write_bytes(b"prior-version")
    record["extractor"] = "manijero-document-extractor-v0"
    record["last_success_at"] = "2026-10-26T12:00:00+00:00"
    record["previous_original_sha256"] = prior_digest
    state_path.write_text(_canonical_json(state), encoding="utf-8")

    later = NOW + timedelta(days=1)
    report = ingest(discovery, state_path, quarantine, now=later)

    assert len(calls) == 2
    assert report["documents"][0]["status"] == "extracted"
    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    assert record["extractor"] == EXTRACTOR
    assert record["last_success_at"] == later.isoformat()
    assert record["original_sha256"] == _hash(PDF_BYTES)
    assert record["previous_original_sha256"] == prior_digest
    assert (quarantine / record["original_path"]).read_bytes() == PDF_BYTES
    assert (quarantine / record["extracted_path"]).read_bytes() == extracted_before
    assert original_path.is_file() and extracted_path.is_file() and prior_file.is_file()
    assert len(record["attempts"]) == 2


def test_state_file_paths_must_stay_inside_the_candidate_directory(tmp_path):
    candidate_id = candidate()["candidate_id"]
    record = {"candidate_id": candidate_id, "original_path": "../outside.pdf",
              "extracted_path": "{}/extracted.json".format(candidate_id)}
    assert not _files_present(record, tmp_path)

    record = {"candidate_id": candidate_id, "original_path": "/tmp/outside.pdf",
              "extracted_path": "{}/extracted.json".format(candidate_id)}
    assert not _files_present(record, tmp_path)

    record = {"candidate_id": candidate_id, "original_path": "other/original.pdf",
              "extracted_path": "{}/extracted.json".format(candidate_id)}
    assert not _files_present(record, tmp_path)


def test_repo_knowledge_paths_are_rejected_without_writing(tmp_path, monkeypatch):
    discovery = write_discovery(tmp_path, [candidate()])
    stub_fetch(monkeypatch, {"*": AssertionError("knowledge paths must reject before fetch")})
    before = canonical_digests()
    state_target = ROOT / "knowledge" / "test-ingestion-state-do-not-write.json"
    quarantine_target = ROOT / "knowledge" / "test-ingestion-quarantine-do-not-write"

    with pytest.raises(IngestionError) as raised:
        ingest(discovery, state_target, tmp_path / "quarantine", now=NOW)
    assert raised.value.failure == "unsafe_workspace"

    with pytest.raises(IngestionError) as raised:
        ingest(discovery, tmp_path / "state.json", quarantine_target, now=NOW)
    assert raised.value.failure == "unsafe_workspace"

    assert not state_target.exists()
    assert not quarantine_target.exists()
    assert canonical_digests() == before


def test_cli_exits_zero_on_success_and_one_on_candidate_failure(tmp_path, monkeypatch, capsys):
    module = load_cli_module()
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    monkeypatch.setattr(sys, "argv", [
        "ingest_official_documents.py", "--discovery-state", str(discovery),
        "--state", str(state_path), "--quarantine", str(quarantine),
    ])

    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["summary"]["extracted"] == 1

    failure_dir = tmp_path / "failure"
    failure_dir.mkdir()
    discovery, state_path, quarantine = defaults(failure_dir)
    stub_fetch(monkeypatch, {"*": IngestionError("malformed_document")})
    monkeypatch.setattr(sys, "argv", [
        "ingest_official_documents.py", "--discovery-state", str(discovery),
        "--state", str(state_path), "--quarantine", str(quarantine),
    ])

    assert module.main() == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["documents"][0]["failure"] == "malformed_document"


def test_cli_returns_two_without_a_traceback_for_unexpected_errors(tmp_path, monkeypatch, capsys):
    module = load_cli_module()

    def boom(*args, **kwargs):
        raise RuntimeError("/secret/path")

    monkeypatch.setattr(module, "ingest", boom)
    monkeypatch.setattr(sys, "argv", [
        "ingest_official_documents.py", "--discovery-state", str(tmp_path / "discovery.json"),
        "--state", str(tmp_path / "state.json"), "--quarantine", str(tmp_path / "quarantine"),
    ])

    assert module.main() == 2
    captured = capsys.readouterr()
    assert captured.err.strip() == '{"error": "RuntimeError"}'
    assert "secret" not in captured.err
    assert "Traceback" not in captured.err


def test_unchanged_candidate_is_not_refetched_and_state_is_reproducible(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    calls = stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    first = ingest(discovery, state_path, quarantine, now=NOW)
    state_after_first = state_path.read_bytes()

    second = ingest(discovery, state_path, quarantine, now=NOW)

    assert len(calls) == 1
    assert second["summary"] == {"extracted": 0, "unchanged": 1, "failed": 0, "rejected": 0}
    assert second["documents"][0]["status"] == "unchanged"
    assert second["documents"][0]["original_sha256"] == first["documents"][0]["original_sha256"]
    assert state_path.read_bytes() == state_after_first
    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    assert len(record["attempts"]) == 1


def test_failure_preserves_last_good_document_and_changed_version_records_previous_hash(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    ingest(discovery, state_path, quarantine, now=NOW)
    first = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]

    changed = candidate(version_hash=_hash(b"version-2"))
    write_discovery(tmp_path, [changed])
    stub_fetch(monkeypatch, {"*": IngestionError("unavailable_upstream")})
    report = ingest(discovery, state_path, quarantine, now=NOW)

    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "unavailable_upstream"
    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    assert record["status"] == "failed"
    assert record["original_sha256"] == first["original_sha256"]
    assert record["last_success_at"] == first["last_success_at"]
    assert record["extracted_path"] == first["extracted_path"]
    assert len(record["attempts"]) == 2
    assert (quarantine / record["extracted_path"]).is_file()

    changed_html = FetchedDocument(HTML_BYTES, "text/html", "utf-8")
    write_discovery(tmp_path, [candidate(version_hash=_hash(b"version-3"), publication_url=candidate()["publication_url"])])
    stub_fetch(monkeypatch, {"*": changed_html})
    ingest(discovery, state_path, quarantine, now=NOW)
    record = json.loads(state_path.read_text(encoding="utf-8"))["candidates"][candidate()["candidate_id"]]
    assert record["status"] == "extracted"
    assert record["previous_original_sha256"] == first["original_sha256"]
    assert record["original_sha256"] != first["original_sha256"]
    assert (quarantine / first["original_path"]).is_file()


def test_duplicate_candidates_and_duplicate_content_are_reported(tmp_path, monkeypatch):
    first = candidate(1)
    duplicate_url = candidate(2, publication_url=first["publication_url"])
    discovery = write_discovery(tmp_path, [first, duplicate_url])
    calls = stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    report = ingest(discovery, tmp_path / "state.json", tmp_path / "quarantine", now=NOW)

    assert len(calls) == 1
    assert report["summary"] == {"extracted": 1, "unchanged": 0, "failed": 0, "rejected": 1}
    failures = sorted(
        "none" if entry["failure"] is None else entry["failure"] for entry in report["documents"]
    )
    assert failures == ["duplicate_candidate", "none"]

    second = candidate(3)
    same_bytes = candidate(4, publication_url="https://www.boe.es/boe/dias/2026/10/27/pdfs/other.pdf")
    write_discovery(tmp_path, [second, same_bytes])
    report = ingest(discovery, tmp_path / "other-state.json", tmp_path / "other-quarantine", now=NOW)
    failures = sorted(
        "none" if entry["failure"] is None else entry["failure"] for entry in report["documents"]
    )
    assert failures == ["duplicate_content", "none"]


def test_monitoring_state_is_reported_as_a_document_coverage_gap(tmp_path, monkeypatch):
    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": AssertionError("monitoring has no document URL to fetch")})

    report = ingest(
        discovery,
        state_path,
        quarantine,
        monitoring_state=FIXTURES / "monitoring_state.json",
        now=NOW,
    )

    assert report["monitoring"] == [
        {"id": "boja-rss", "status": "unchecked", "failure": "no_document_candidates"}
    ]
    assert report["summary"]["extracted"] == 0


def test_invalid_input_states_fail_before_network_or_overwrite(tmp_path, monkeypatch):
    stub_fetch(monkeypatch, {"*": AssertionError("invalid state must fail before any fetch")})
    broken = tmp_path / "broken.json"
    broken.write_text('{"schema_version":"official-discovery-state-v1","registries":{}}', encoding="utf-8")
    with pytest.raises(IngestionError) as raised:
        load_discovery_candidates(broken)
    assert raised.value.failure == "invalid_discovery_state"

    original_state = '{"schema_version":"official-ingestion-state-v1","candidates":{"bad":"record"}}\n'
    state_path = tmp_path / "state.json"
    state_path.write_text(original_state, encoding="utf-8")
    with pytest.raises(IngestionError) as raised:
        ingest(write_discovery(tmp_path, [candidate()]), state_path, tmp_path / "quarantine", now=NOW)
    assert raised.value.failure == "invalid_ingestion_state"
    assert state_path.read_text(encoding="utf-8") == original_state

    monitoring = tmp_path / "monitor.json"
    monitoring.write_text('{"schema_version":"source-monitor-state-v1","sources":[]}', encoding="utf-8")
    with pytest.raises(IngestionError) as raised:
        ingest(write_discovery(tmp_path, [candidate()]), tmp_path / "fresh.json", tmp_path / "quarantine",
               monitoring_state=monitoring, now=NOW)
    assert raised.value.failure == "invalid_monitoring_state"


def test_cli_reports_only_the_error_type_for_invalid_input(tmp_path):
    script = ROOT / "backend" / "scripts" / "ingest_official_documents.py"
    result = subprocess.run(
        [sys.executable, str(script), "--discovery-state", str(tmp_path / "missing.json"),
         "--state", str(tmp_path / "state.json"), "--quarantine", str(tmp_path / "quarantine")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "missing.json" not in result.stderr
    assert json.loads(result.stderr) == {"error": "IngestionError"}


def test_pdf_tounicode_cmap_is_applied_to_embedded_font_text():
    cmap = b"""/CIDInit /ProcSet findresource begin
begincmap
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
9 beginbfchar
<0020> <0020>
<0050> <0050>
<0072> <0072>
<0065> <0065>
<0073> <0073>
<0075> <0075>
<0070> <0070>
<0074> <0074>
<006F> <006F>
endbfchar
1 beginbfrange
<0041> <0043> <0041>
endbfrange
endcmap
end
"""
    content = b"BT /F1 12 Tf 72 720 Td <0050007200650073007500700075006500730074006F00730020004100420043> Tj ET"
    payload = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Resources 5 0 R /Contents 6 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /ToUnicode 7 0 R >>\nendobj\n"
        b"5 0 obj\n<< /Font << /F1 4 0 R >> >>\nendobj\n"
        b"6 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream\nendobj\n"
        b"7 0 obj\n<< /Length " + str(len(cmap)).encode() + b" >>\nstream\n" + cmap + b"\nendstream\nendobj\n"
    )

    document = _extract(FetchedDocument(payload, "application/pdf", None))

    assert [block["text"] for block in document.blocks] == ["Presupuestos ABC"]
    assert document.blocks[0]["page"] == 1


def test_pdf_text_with_no_decodable_glyphs_is_not_reported_as_extractable():
    cmap = b"""/CIDInit /ProcSet findresource begin
begincmap
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
1 beginbfchar
<0020> <0020>
endbfchar
endcmap
end
"""
    content = b"BT /F1 12 Tf 72 720 Td <0041> Tj ET"
    pdf = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Resources 5 0 R /Contents 6 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /ToUnicode 7 0 R >>\nendobj\n"
        b"5 0 obj\n<< /Font << /F1 4 0 R >> >>\nendobj\n"
        b"6 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream\nendobj\n"
        b"7 0 obj\n<< /Length " + str(len(cmap)).encode() + b" >>\nstream\n" + cmap + b"\nendstream\nendobj\n"
    )

    with pytest.raises(IngestionError) as raised:
        _extract(FetchedDocument(pdf, "application/pdf", None))

    assert raised.value.failure == "no_extractable_text"


def test_pdf_unicode_strings_and_published_schemas(tmp_path, monkeypatch):
    from jsonschema import Draft202012Validator

    assert _decode_pdf_bytes(b"\xfe\xff\x00R\x00e\x00q") == "Req"
    assert _decode_pdf_bytes(b"Requisitos") == "Requisitos"

    discovery, state_path, quarantine = defaults(tmp_path)
    stub_fetch(monkeypatch, {"*": FetchedDocument(PDF_BYTES, "application/pdf", None)})
    ingest(discovery, state_path, quarantine, now=NOW)

    state_schema = json.loads((ROOT / "knowledge" / "official-ingestion-state.schema.json").read_text(encoding="utf-8"))
    document_schema = json.loads((ROOT / "knowledge" / "official-ingestion-document.schema.json").read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    Draft202012Validator(state_schema).validate(state)
    record = state["candidates"][candidate()["candidate_id"]]
    document = json.loads((quarantine / record["extracted_path"]).read_text(encoding="utf-8"))
    Draft202012Validator(document_schema).validate(document)
