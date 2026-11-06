"""Focused tests for the quarantined-PDF to Markdown parser.

Covered here: text-layer Markdown with page mapping and provenance, header/footer
and page-number cleaning, ten-document byte-identical double runs, base-runtime
degradation and the no-heavy-import guard, a faked table adapter versus the base
runtime, faked Spanish OCR and an honest no-text failure, unsafe or inconsistent
input that fails closed, per-document failure isolation, and the guarantee that
parsed output is not answerable knowledge.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.legal_document_parser import (
    LAYOUT,
    OCR,
    PARSER,
    RUNTIME_READY,
    RUNTIME_UNAVAILABLE,
    TABLES,
    Block,
    Capability,
    ParserError,
    ParserRuntime,
    detect_runtime,
    parse_documents,
    runtime_lines,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "knowledge" / "legal-markdown-document.schema.json"
EXTRACTOR = "manijero-document-extractor-v1"


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def build_pdf(page_count):
    """A minimal PDF whose declared page count is the standard-library walk's."""
    kids = " ".join("{} 0 R".format(3 + index) for index in range(page_count))
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [{}] /Count {} >>\nendobj\n".format(kids, page_count),
    ]
    for index in range(page_count):
        objects.append(
            "{} 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n".format(3 + index)
        )
    return ("%PDF-1.4\n" + "".join(objects)).encode("ascii")


def base_runtime():
    return ParserRuntime(
        "base",
        {
            name: Capability(RUNTIME_UNAVAILABLE, "runtime_missing")
            for name in (LAYOUT, TABLES, OCR)
        },
        {},
    )


def runtime_with(**adapters):
    return detect_runtime(**adapters)


def text_block(page, text, kind="text"):
    return {"kind": kind, "page": page, "section": "Página {}".format(page), "text": text}


def default_blocks(page_count):
    return [text_block(page, "Contenido de la página {}".format(page)) for page in range(1, page_count + 1)]


def add_candidate(quarantine, index=1, blocks=None, media_type="pdf", page_count=1, payload=None,
                  status="extracted", **record_overrides):
    """Write one quarantined candidate and return its ingestion state record."""
    candidate_id = _hash("candidate-{}".format(index).encode())
    if payload is None:
        payload = build_pdf(page_count) if media_type == "pdf" else b"<html><body><p>texto</p></body></html>"
    digest = _hash(payload)
    suffix = "pdf" if media_type == "pdf" else "html"
    directory = Path(quarantine) / candidate_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "original-{}.{}".format(digest, suffix)).write_bytes(payload)
    if blocks is None:
        blocks = default_blocks(page_count) if media_type == "pdf" else [text_block(None, "texto")]
    document = {
        "schema_version": "official-ingestion-document-v1",
        "candidate_id": candidate_id,
        "media_type": media_type,
        "extractor": EXTRACTOR,
        "title": None,
        "blocks": blocks,
    }
    extracted_text = _canonical(document)
    (directory / "extracted-{}.json".format(digest)).write_text(extracted_text, encoding="utf-8")
    pages = {block["page"] for block in blocks if block["page"] is not None}
    record = {
        "candidate_id": candidate_id,
        "issuer": "BOE",
        "registry_id": "boe",
        "registry_url": "https://www.boe.es/datosabiertos/api/boe/sumario/20261027",
        "publication_url": "https://www.boe.es/boe/dias/2026/10/27/pdfs/BOE-A-2026-{}.pdf".format(index),
        "title": "Documento sintético {}".format(index),
        "stable_identity": "BOE-A-2026-{}".format(index),
        "version_hash": _hash("version-{}".format(index).encode()),
        "review_status": "pending",
        "status": status,
        "failure": None,
        "last_attempt_at": "2026-10-27T12:00:00+00:00",
        "last_success_at": "2026-10-27T12:00:00+00:00",
        "attempts": [],
        "original_sha256": digest,
        "byte_size": len(payload),
        "declared_content_type": "application/pdf" if media_type == "pdf" else "text/html",
        "media_type": media_type,
        "extractor": EXTRACTOR,
        "extracted_text_sha256": _hash(extracted_text.encode("utf-8")),
        "page_count": max(pages) if pages else None,
        "block_count": len(blocks),
        "original_path": "{}/original-{}.{}".format(candidate_id, digest, suffix),
        "extracted_path": "{}/extracted-{}.json".format(candidate_id, digest),
    }
    if status != "extracted":
        for key in ("original_sha256", "extracted_text_sha256", "media_type", "extractor",
                    "original_path", "extracted_path", "page_count", "block_count",
                    "byte_size", "declared_content_type"):
            record.pop(key)
    record.update(record_overrides)
    return record


def write_state(tmp_path, records, name="state.json"):
    path = Path(tmp_path) / name
    path.write_text(
        json.dumps(
            {
                "schema_version": "official-ingestion-state-v1",
                "candidates": {record["candidate_id"]: record for record in records},
            }
        ),
        encoding="utf-8",
    )
    return path


def canonical_digests():
    return {
        name: _hash((ROOT / "knowledge" / name).read_bytes())
        for name in ("source_catalog.json", "passages.json")
    }


def load_cli_module():
    path = ROOT / "backend" / "scripts" / "parse_official_documents.py"
    spec = importlib.util.spec_from_file_location("parse_official_documents_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_for(output, record):
    directory = Path(output) / record["candidate_id"]
    manifests = sorted(directory.glob("parse-*.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(manifest)
    return manifests[0], manifest


# --- Scenario 1: text-layer PDF -> clean Markdown with provenance --------------------------


def test_text_layer_pdf_becomes_page_mapped_markdown_with_provenance(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    blocks = [
        text_block(1, "Boletín Oficial del Estado"),
        text_block(1, "Párrafo   uno con    espacios"),
        text_block(1, "Página 1"),
        text_block(2, "Boletín Oficial del Estado"),
        text_block(2, "Párrafo dos"),
        text_block(2, "- 2 -"),
        text_block(3, "Boletín Oficial del Estado"),
        text_block(3, "Párrafo tres"),
        text_block(3, "3"),
    ]
    record = add_candidate(quarantine, blocks=blocks, page_count=3)
    state = write_state(tmp_path, [record])
    before_knowledge = canonical_digests()
    before_state = state.read_bytes()

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["summary"] == {"documents": 1, "parsed": 1, "unchanged": 0, "failed": 0, "skipped": 0}
    assert report["documents"][0]["status"] == "parsed"
    digest = record["original_sha256"]
    markdown_path = output / record["candidate_id"] / "markdown-{}.md".format(digest)
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown == (
        "<!-- page: 1 -->\n"
        "\n"
        "Párrafo uno con espacios\n"
        "\n"
        "<!-- page: 2 -->\n"
        "\n"
        "Párrafo dos\n"
        "\n"
        "<!-- page: 3 -->\n"
        "\n"
        "Párrafo tres\n"
    )
    assert "\r" not in markdown and not any(line.endswith(" ") for line in markdown.splitlines())
    assert "Boletín Oficial" not in markdown and "Página 1" not in markdown

    _, manifest = manifest_for(output, record)
    assert manifest["schema_version"] == "legal-markdown-document-v1"
    assert manifest["parser"] == PARSER
    assert manifest["source_sha256"] == digest
    assert manifest["source_path"] == record["original_path"]
    assert manifest["upstream_extractor"] == EXTRACTOR
    assert manifest["markdown_sha256"] == _hash(markdown.encode("utf-8"))
    assert manifest["markdown_path"] == "{}/markdown-{}.md".format(record["candidate_id"], digest)
    assert manifest["page_count"] == 3
    assert [(page["page"], page["line_start"], page["line_end"]) for page in manifest["pages"]] == [
        (1, 1, 3),
        (2, 5, 7),
        (3, 9, 11),
    ]
    assert manifest["runtime"]["profile"] == "base"

    assert canonical_digests() == before_knowledge
    assert state.read_bytes() == before_state
    assert str(output.resolve()).startswith(str(quarantine.resolve())) is False


def test_cleaning_keeps_a_page_whose_only_line_is_a_page_number(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    blocks = [text_block(1, "12"), text_block(2, "Texto real de la página dos")]
    record = add_candidate(quarantine, blocks=blocks, page_count=2)
    state = write_state(tmp_path, [record])

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["documents"][0]["status"] == "parsed"
    markdown = (output / record["candidate_id"] / "markdown-{}.md".format(record["original_sha256"])).read_text(
        encoding="utf-8"
    )
    assert "12" in markdown


def test_repeated_header_needs_three_pages_and_half_the_document(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    blocks = [
        text_block(1, "Cabecera repetida"),
        text_block(1, "Uno"),
        text_block(2, "Cabecera repetida"),
        text_block(2, "Dos"),
    ]
    record = add_candidate(quarantine, blocks=blocks, page_count=2)
    state = write_state(tmp_path, [record])

    parse_documents(state, quarantine, output, runtime=base_runtime())

    markdown = (output / record["candidate_id"] / "markdown-{}.md".format(record["original_sha256"])).read_text(
        encoding="utf-8"
    )
    assert markdown.count("Cabecera repetida") == 2


# --- Scenario 2: ten documents parse reproducibly ------------------------------------------


def test_ten_documents_are_byte_identical_across_two_output_roots(tmp_path):
    quarantine = tmp_path / "quarantine"
    records = [
        add_candidate(
            quarantine,
            index=index,
            blocks=[text_block(1, "Documento {} página 1".format(index)), text_block(2, "Documento {} página 2".format(index))],
            page_count=2,
        )
        for index in range(1, 11)
    ]
    state = write_state(tmp_path, records)

    first = parse_documents(state, quarantine, tmp_path / "out-one", runtime=base_runtime())
    second = parse_documents(state, quarantine, tmp_path / "out-two", runtime=base_runtime())

    assert first["summary"]["parsed"] == 10
    assert second["summary"]["parsed"] == 10
    one = {path.relative_to(tmp_path / "out-one"): path.read_bytes() for path in (tmp_path / "out-one").rglob("*") if path.is_file()}
    two = {path.relative_to(tmp_path / "out-two"): path.read_bytes() for path in (tmp_path / "out-two").rglob("*") if path.is_file()}
    assert one == two
    assert len([name for name in one if name.suffix == ".md"]) == 10
    for payload in one.values():
        assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
    for outcome in first["documents"]:
        assert outcome["status"] == "parsed" and outcome["failure"] is None


def test_an_unchanged_rerun_rewrites_nothing_and_a_new_runtime_reparses(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Texto estable")], page_count=1)
    state = write_state(tmp_path, [record])

    parse_documents(state, quarantine, output, runtime=base_runtime())
    manifest_path, manifest = manifest_for(output, record)
    before = manifest_path.read_bytes()

    again = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert again["documents"][0]["status"] == "unchanged"
    assert manifest_path.read_bytes() == before

    class FakeTables:
        version = "fake-docling-1"

        def tables(self, path, page_count):
            return {}

    reparsed = parse_documents(state, quarantine, output, runtime=runtime_with(tables=FakeTables()))

    assert reparsed["documents"][0]["status"] == "parsed"
    _, updated = manifest_for(output, record)
    assert updated["runtime"]["profile"] == "docparse"
    assert updated["previous_markdown_sha256"] == manifest["markdown_sha256"]


# --- Scenario 3: the base runtime degrades explicitly and stays light ----------------------


def test_base_runtime_reports_both_optional_capabilities_unavailable(tmp_path, capsys):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Solo texto")], page_count=1)
    state = write_state(tmp_path, [record])

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["runtime"]["profile"] == "base"
    assert report["runtime"]["capabilities"][TABLES]["status"] == RUNTIME_UNAVAILABLE
    assert report["runtime"]["capabilities"][TABLES]["reason"] == "runtime_missing"
    assert report["runtime"]["capabilities"][OCR]["status"] == RUNTIME_UNAVAILABLE
    assert report["runtime"]["capabilities"][OCR]["reason"] == "runtime_missing"
    _, manifest = manifest_for(output, record)
    assert manifest["capabilities"][TABLES]["status"] == "unavailable"
    # A text-only document needs no OCR, so the manifest records that instead of
    # claiming the capability; the reason still names the missing runtime.
    assert manifest["capabilities"][OCR]["status"] == "not_needed"
    assert manifest["capabilities"][OCR]["reason"] == "runtime_missing"
    assert [page["ocr"] for page in manifest["pages"]] == [False]
    assert "tables_runtime_unavailable" in manifest["warnings"]

    for line in runtime_lines(base_runtime()):
        print(line)
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert all("not available" in line for line in lines)


def test_check_runtime_prints_one_line_per_capability_and_exits_zero(capsys):
    cli = load_cli_module()

    assert cli.main(["--check-runtime"]) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert any(line.startswith("Layout") for line in lines)
    assert any(line.startswith("Tables") for line in lines)
    assert any(line.startswith("OCR") for line in lines)


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is not None for name in ("pymupdf4llm", "docling", "pytesseract")),
    reason="the optional docparse runtime is installed in this environment",
)
def test_detected_base_runtime_marks_every_capability_unavailable():
    runtime = detect_runtime()

    assert runtime.profile == "base"
    assert runtime.adapters == {}
    assert all(capability.status == RUNTIME_UNAVAILABLE for capability in runtime.capabilities.values())


def test_importing_the_service_and_parser_loads_no_heavy_runtime():
    script = (
        "import sys\n"
        "import app.main\n"
        "import app.legal_document_parser\n"
        "heavy = ['torch', 'docling', 'pymupdf', 'fitz', 'pymupdf4llm', 'pytesseract', 'chromadb']\n"
        "loaded = sorted(name for name in heavy if name in sys.modules)\n"
        "print(','.join(loaded))\n"
        "raise SystemExit(1 if loaded else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT / "backend"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


# --- Scenario 4: tables come only from a capable adapter -----------------------------------


class FakeTables:
    version = "fake-docling-1"

    def __init__(self, tables):
        self._tables = tables

    def tables(self, path, page_count):
        return self._tables


def test_a_table_adapter_renders_one_pipe_table_and_the_base_runtime_adds_none(tmp_path):
    quarantine = tmp_path / "quarantine"
    blocks = [text_block(1, "Importes de la cuota"), text_block(2, "Concepto Importe Cuota 120,00")]
    record = add_candidate(quarantine, blocks=blocks, page_count=2)
    state = write_state(tmp_path, [record])
    table = Block("table", rows=(("Concepto", "Importe"), ("Cuota", "120,00 €")))
    markdown_name = "markdown-{}.md".format(record["original_sha256"])

    base_output = tmp_path / "out-base"
    parse_documents(state, quarantine, base_output, runtime=base_runtime())
    base_markdown = (base_output / record["candidate_id"] / markdown_name).read_text(encoding="utf-8")
    assert "|" not in base_markdown
    _, base_manifest = manifest_for(base_output, record)
    assert base_manifest["table_count"] == 0
    assert "tables_runtime_unavailable" in base_manifest["warnings"]

    table_output = tmp_path / "out-tables"
    report = parse_documents(
        state, quarantine, table_output, runtime=runtime_with(tables=FakeTables({2: [table]}))
    )
    markdown = (table_output / record["candidate_id"] / markdown_name).read_text(encoding="utf-8")

    table_lines = [line for line in markdown.splitlines() if line.startswith("|")]
    assert table_lines == ["| Concepto | Importe |", "| --- | --- |", "| Cuota | 120,00 € |"]
    assert report["documents"][0]["table_count"] == 1
    _, manifest = manifest_for(table_output, record)
    assert manifest["table_count"] == 1
    assert manifest["capabilities"][TABLES]["status"] == "used"
    assert [page["tables"] for page in manifest["pages"]] == [0, 1]
    assert "tables_runtime_unavailable" not in manifest["warnings"]


def test_a_failing_table_adapter_degrades_only_that_capability(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Texto intacto")], page_count=1)
    state = write_state(tmp_path, [record])

    class BrokenTables:
        version = "fake-broken"

        def tables(self, path, page_count):
            raise RuntimeError("upstream detail that must never surface")

    report = parse_documents(state, quarantine, output, runtime=runtime_with(tables=BrokenTables()))

    assert report["documents"][0]["status"] == "parsed"
    _, manifest = manifest_for(output, record)
    assert manifest["capabilities"][TABLES]["status"] == "failed"
    assert "tables_adapter_failed" in manifest["warnings"]
    assert "upstream detail" not in json.dumps(report)
    assert "|" not in (output / record["candidate_id"] / "markdown-{}.md".format(record["original_sha256"])).read_text(
        encoding="utf-8"
    )


# --- Scenario 5: scanned pages, Spanish OCR, or an honest failure --------------------------


class FakeOcr:
    version = "fake-tesseract-spa"

    def __init__(self, texts):
        self._texts = texts
        self.calls = []

    def page_text(self, path, page_number, timeout):
        self.calls.append((page_number, timeout))
        return self._texts.get(page_number, "")


def test_a_page_without_a_text_layer_fails_closed_and_keeps_prior_artifacts(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[], page_count=2)
    state = write_state(tmp_path, [record])
    prior_directory = output / record["candidate_id"]
    prior_directory.mkdir(parents=True)
    prior_markdown = prior_directory / "markdown-{}.md".format(record["original_sha256"])
    prior_markdown.write_bytes(b"<!-- page: 1 -->\n\nArtefacto anterior\n")
    prior_manifest = prior_directory / "parse-{}.json".format(record["original_sha256"])
    prior_manifest.write_bytes(b'{"previous": true}\n')

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    outcome = report["documents"][0]
    assert outcome["status"] == "failed" and outcome["failure"] == "no_extractable_text"
    assert outcome["empty_pages"] == 2 and outcome["page_count"] == 2
    assert "no_text_layer" in outcome["warnings"]
    assert prior_markdown.read_bytes() == b"<!-- page: 1 -->\n\nArtefacto anterior\n"
    assert prior_manifest.read_bytes() == b'{"previous": true}\n'


def test_a_faked_spanish_ocr_fills_textless_pages_and_marks_them(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[], page_count=2)
    state = write_state(tmp_path, [record])
    ocr = FakeOcr({1: "Primera página escaneada", 2: "Segunda página escaneada"})

    report = parse_documents(state, quarantine, output, runtime=runtime_with(ocr=ocr))

    assert report["documents"][0]["status"] == "parsed"
    assert report["documents"][0]["ocr_page_count"] == 2
    markdown = (output / record["candidate_id"] / "markdown-{}.md".format(record["original_sha256"])).read_text(
        encoding="utf-8"
    )
    assert markdown == (
        "<!-- page: 1 -->\n\nPrimera página escaneada\n\n"
        "<!-- page: 2 -->\n\nSegunda página escaneada\n"
    )
    _, manifest = manifest_for(output, record)
    assert [page["ocr"] for page in manifest["pages"]] == [True, True]
    assert manifest["capabilities"][OCR]["status"] == "used"
    assert "no_text_layer" not in manifest["warnings"]
    assert ocr.calls == [(1, 60), (2, 60)]


def test_tesseract_without_spanish_degrades_with_a_fixed_reason(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[], page_count=1)
    state = write_state(tmp_path, [record])
    runtime = ParserRuntime(
        "docparse",
        {
            LAYOUT: Capability(RUNTIME_UNAVAILABLE, "runtime_missing"),
            TABLES: Capability(RUNTIME_UNAVAILABLE, "runtime_missing"),
            OCR: Capability(RUNTIME_UNAVAILABLE, "language_missing"),
        },
        {},
    )

    report = parse_documents(state, quarantine, output, runtime=runtime)

    assert report["runtime"]["capabilities"][OCR] == {
        "status": RUNTIME_UNAVAILABLE,
        "reason": "language_missing",
        "version": None,
    }
    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "no_extractable_text"
    assert "ocr_runtime_unavailable" in report["documents"][0]["warnings"]


def test_an_ocr_adapter_failure_keeps_the_rest_of_the_document(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    blocks = [text_block(1, "Texto de la primera página")]
    record = add_candidate(quarantine, blocks=blocks, page_count=2)
    state = write_state(tmp_path, [record])

    class BrokenOcr:
        version = "fake-broken-ocr"

        def page_text(self, path, page_number, timeout):
            raise TimeoutError("slow page")

    report = parse_documents(state, quarantine, output, runtime=runtime_with(ocr=BrokenOcr()))

    assert report["documents"][0]["status"] == "parsed"
    _, manifest = manifest_for(output, record)
    assert manifest["capabilities"][OCR]["status"] == "failed"
    assert "ocr_timeout" in manifest["warnings"]
    assert manifest["pages"][1]["empty"] is True
    assert manifest["pages"][1]["warnings"] == ["no_text_layer", "ocr_timeout"]


# --- Scenario 6: unsafe or inconsistent input fails closed --------------------------------


def test_unsafe_output_root_aborts_before_writing_anything(tmp_path):
    quarantine = tmp_path / "quarantine"
    record = add_candidate(quarantine)
    state = write_state(tmp_path, [record])

    with pytest.raises(ParserError) as error:
        parse_documents(state, quarantine, ROOT / "knowledge" / "derived")

    assert error.value.failure == "unsafe_output_root"
    assert not (ROOT / "knowledge" / "derived").exists()

    with pytest.raises(ParserError) as error:
        parse_documents(state, quarantine, quarantine)

    assert error.value.failure == "unsafe_output_root"


def test_an_invalid_state_or_too_many_candidates_aborts_with_exit_two(tmp_path, capsys):
    cli = load_cli_module()
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    output = tmp_path / "output"
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version": "not-the-contract", "candidates": {}}', encoding="utf-8")

    assert cli.main(["--state", str(invalid), "--quarantine", str(quarantine), "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "ParserError"}
    assert not output.exists()

    too_many = {
        "schema_version": "official-ingestion-state-v1",
        "candidates": {
            _hash("bulk-{}".format(index).encode()): {
                "candidate_id": _hash("bulk-{}".format(index).encode()),
                "issuer": "BOE",
                "stable_identity": "BOE-A-2026-{}".format(index),
                "publication_url": "https://www.boe.es/boe/dias/2026/10/27/pdfs/{}.pdf".format(index),
                "title": "Documento {}".format(index),
                "review_status": "pending",
                "status": "failed",
            }
            for index in range(1001)
        },
    }
    bulk = tmp_path / "bulk.json"
    bulk.write_text(json.dumps(too_many), encoding="utf-8")

    assert cli.main(["--state", str(bulk), "--quarantine", str(quarantine), "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "ParserError"}
    assert not output.exists()


def test_per_document_failures_are_isolated_and_exit_one(tmp_path, capsys):
    cli = load_cli_module()
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    good = add_candidate(quarantine, index=1, blocks=[text_block(1, "Documento correcto")], page_count=1)
    missing = add_candidate(quarantine, index=2, blocks=[text_block(1, "Documento ausente")], page_count=1)
    (quarantine / missing["original_path"]).unlink()
    mismatch = add_candidate(quarantine, index=3, blocks=[text_block(1, "Documento alterado")], page_count=1)
    (quarantine / mismatch["original_path"]).write_bytes(b"%PDF-1.4 alterado")
    html = add_candidate(quarantine, index=4, media_type="html")
    state = write_state(tmp_path, [good, missing, mismatch, html])

    assert cli.main(["--state", str(state), "--quarantine", str(quarantine), "--output", str(output)]) == 1

    report = json.loads(capsys.readouterr().out)
    outcomes = {outcome["candidate_id"]: outcome for outcome in report["documents"]}
    assert [outcome["candidate_id"] for outcome in report["documents"]] == sorted(outcomes)
    assert outcomes[good["candidate_id"]]["status"] == "parsed"
    assert outcomes[missing["candidate_id"]]["failure"] == "missing_source"
    assert outcomes[mismatch["candidate_id"]]["failure"] == "source_hash_mismatch"
    assert outcomes[html["candidate_id"]]["status"] == "skipped"
    assert outcomes[html["candidate_id"]]["failure"] == "not_a_pdf"
    assert report["summary"] == {"documents": 4, "parsed": 1, "unchanged": 0, "failed": 2, "skipped": 1}
    assert (output / good["candidate_id"]).is_dir()
    assert not (output / missing["candidate_id"]).exists()
    assert not (output / mismatch["candidate_id"]).exists()
    assert "Documento" not in json.dumps(report)


def test_a_failed_reparse_leaves_the_previous_pair_byte_identical(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Versión buena")], page_count=1)
    state = write_state(tmp_path, [record])
    parse_documents(state, quarantine, output, runtime=base_runtime())
    markdown_path = output / record["candidate_id"] / "markdown-{}.md".format(record["original_sha256"])
    manifest_path, _ = manifest_for(output, record)
    before = (markdown_path.read_bytes(), manifest_path.read_bytes())

    (quarantine / record["extracted_path"]).write_text(
        json.dumps({"schema_version": "other", "candidate_id": record["candidate_id"], "blocks": []}),
        encoding="utf-8",
    )
    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["documents"][0]["failure"] == "invalid_extracted_document"
    assert (markdown_path.read_bytes(), manifest_path.read_bytes()) == before


def test_a_document_over_the_character_bound_fails_closed(tmp_path, monkeypatch):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Texto de sobra para el límite")], page_count=1)
    state = write_state(tmp_path, [record])
    monkeypatch.setattr("app.legal_document_parser.MAX_CHARACTERS", 10)

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "size_limit_exceeded"
    assert not (output / record["candidate_id"]).exists()


def test_a_markdown_over_the_byte_bound_fails_closed(tmp_path, monkeypatch):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Texto")], page_count=1)
    state = write_state(tmp_path, [record])
    monkeypatch.setattr("app.legal_document_parser.MAX_MARKDOWN_BYTES", 10)

    report = parse_documents(state, quarantine, output, runtime=base_runtime())

    assert report["documents"][0]["failure"] == "size_limit_exceeded"
    assert not (output / record["candidate_id"]).exists()


def test_the_table_page_budget_degrades_with_a_warning(tmp_path, monkeypatch):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=default_blocks(3), page_count=3)
    state = write_state(tmp_path, [record])
    monkeypatch.setattr("app.legal_document_parser.MAX_TABLE_PAGES", 2)
    tables = {
        page: [Block("table", rows=(("Concepto", "Importe"), ("Cuota", str(page))))]
        for page in (1, 2, 3)
    }

    report = parse_documents(state, quarantine, output, runtime=runtime_with(tables=FakeTables(tables)))

    assert report["documents"][0]["status"] == "parsed"
    _, manifest = manifest_for(output, record)
    assert "tables_page_budget_exceeded" in manifest["warnings"]
    assert [page["tables"] for page in manifest["pages"]] == [1, 1, 0]
    assert manifest["capabilities"][TABLES]["status"] == "used"


def test_the_ocr_page_budget_degrades_with_a_warning(tmp_path, monkeypatch):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[], page_count=3)
    state = write_state(tmp_path, [record])
    monkeypatch.setattr("app.legal_document_parser.MAX_OCR_PAGES", 1)
    ocr = FakeOcr({page: "Página escaneada {}".format(page) for page in (1, 2, 3)})

    report = parse_documents(state, quarantine, output, runtime=runtime_with(ocr=ocr))

    assert report["documents"][0]["status"] == "parsed"
    assert report["documents"][0]["ocr_page_count"] == 1
    assert len(ocr.calls) == 1
    _, manifest = manifest_for(output, record)
    assert "ocr_page_budget_exceeded" in manifest["warnings"]
    assert [page["ocr"] for page in manifest["pages"]] == [True, False, False]
    assert [page["empty"] for page in manifest["pages"]] == [False, True, True]


def test_check_runtime_rejects_other_arguments():
    cli = load_cli_module()

    with pytest.raises(SystemExit) as error:
        cli.main(["--check-runtime", "--state", "x.json"])

    assert error.value.code == 2


# --- Scenario 7: parsed output is not answerable knowledge --------------------------------


def test_parsed_output_is_never_read_by_the_answer_path(tmp_path):
    quarantine, output = tmp_path / "quarantine", tmp_path / "output"
    record = add_candidate(quarantine, blocks=[text_block(1, "Texto derivado")], page_count=1)
    state = write_state(tmp_path, [record])
    before_knowledge = canonical_digests()
    before_state = state.read_bytes()

    parse_documents(state, quarantine, output, runtime=base_runtime())

    assert canonical_digests() == before_knowledge
    assert state.read_bytes() == before_state
    assert json.loads(state.read_text(encoding="utf-8"))["candidates"][record["candidate_id"]]["review_status"] == "pending"
    for name in (
        "main.py",
        "ask_api.py",
        "retrieval.py",
        "retrieval_backend.py",
        "knowledge_release.py",
        "review_package.py",
        "readiness.py",
    ):
        assert "legal_document_parser" not in (ROOT / "backend" / "app" / name).read_text(encoding="utf-8")

    script = "import sys, app.main\nraise SystemExit(1 if 'app.legal_document_parser' in sys.modules else 0)\n"
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=str(ROOT / "backend"), capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
