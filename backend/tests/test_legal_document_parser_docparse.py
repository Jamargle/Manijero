"""Optional real-runtime smoke for the legal document parser.

Skipped unless the ``docparse`` environment (pymupdf4llm, docling, and the
Tesseract Spanish binary data) is installed. Build it with
``./scripts/init.sh --setup-python docparse`` and run this file with
``MANIJERO_PYTHON=backend/.venv-docparse/bin/python``; the default suite never
needs it. A skipped run is not evidence of parser accuracy.
"""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

pytest.importorskip("pymupdf4llm")
pytest.importorskip("docling")
pytest.importorskip("pytesseract")

from app.legal_document_parser import (  # noqa: E402
    RUNTIME_READY,
    detect_runtime,
    parse_documents,
)

pytestmark = pytest.mark.skipif(
    not all(
        capability.status == RUNTIME_READY
        for capability in detect_runtime().capabilities.values()
    ),
    reason="the full docparse runtime (pymupdf4llm, docling, Tesseract Spanish) is not installed",
)


def _tiny_pdf(path: Path) -> bytes:
    """One page with a heading and a two-cell table drawn as text."""
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    content = (
        b"BT /F1 14 Tf 72 720 Td (Articulo 1) Tj ET\n"
        b"BT /F1 10 Tf 72 700 Td (Concepto Importe) Tj ET\n"
        b"BT /F1 10 Tf 72 688 Td (Cuota 120,00) Tj ET\n"
    )
    objects.append(
        b"4 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream\nendobj\n"
    )
    payload = b"%PDF-1.4\n" + b"".join(objects)
    path.write_bytes(payload)
    return payload


def test_the_real_runtime_parses_a_small_pdf_into_markdown(tmp_path):
    quarantine = tmp_path / "quarantine"
    output = tmp_path / "output"
    candidate_id = "a" * 64
    directory = quarantine / candidate_id
    directory.mkdir(parents=True)
    payload = _tiny_pdf(directory / "source.pdf")
    digest = hashlib.sha256(payload).hexdigest()
    (directory / "source.pdf").rename(directory / "original-{}.pdf".format(digest))
    document = {
        "schema_version": "official-ingestion-document-v1",
        "candidate_id": candidate_id,
        "media_type": "pdf",
        "extractor": "manijero-document-extractor-v1",
        "title": None,
        "blocks": [
            {"kind": "text", "page": 1, "section": "Página 1", "text": "Articulo 1"},
            {"kind": "text", "page": 1, "section": "Página 1", "text": "Concepto Importe"},
            {"kind": "text", "page": 1, "section": "Página 1", "text": "Cuota 120,00"},
        ],
    }
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (directory / "extracted-{}.json".format(digest)).write_text(text, encoding="utf-8")
    record = {
        "candidate_id": candidate_id,
        "issuer": "BOE",
        "registry_id": "boe",
        "registry_url": "https://www.boe.es/datosabiertos/api/boe/sumario/20261027",
        "publication_url": "https://www.boe.es/boe/dias/2026/10/27/pdfs/tiny.pdf",
        "title": "Documento sintético mínimo",
        "stable_identity": "BOE-A-2026-tiny",
        "version_hash": hashlib.sha256(b"version").hexdigest(),
        "review_status": "pending",
        "status": "extracted",
        "failure": None,
        "last_attempt_at": None,
        "last_success_at": None,
        "attempts": [],
        "original_sha256": digest,
        "byte_size": len(payload),
        "declared_content_type": "application/pdf",
        "media_type": "pdf",
        "extractor": "manijero-document-extractor-v1",
        "extracted_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "page_count": 1,
        "block_count": 3,
        "original_path": "{}/original-{}.pdf".format(candidate_id, digest),
        "extracted_path": "{}/extracted-{}.json".format(candidate_id, digest),
    }
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"schema_version": "official-ingestion-state-v1", "candidates": {candidate_id: record}}),
        encoding="utf-8",
    )

    report = parse_documents(state, quarantine, output)

    assert report["runtime"]["profile"] == "docparse"
    assert all(
        capability["status"] == RUNTIME_READY
        for capability in report["runtime"]["capabilities"].values()
    )
    assert report["documents"][0]["status"] == "parsed"
    manifest = json.loads(
        (output / candidate_id / "parse-{}.json".format(digest)).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "knowledge" / "legal-markdown-document.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(manifest)
    markdown = (output / candidate_id / "markdown-{}.md".format(digest)).read_text(encoding="utf-8")
    assert markdown.startswith("<!-- page: 1 -->\n")
    # This is a wiring smoke, not an accuracy measurement: a text-drawn table need
    # not be recognized as a table, and OCR of a text-layer page is not exercised.
    assert manifest["page_count"] >= 1
