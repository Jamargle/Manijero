"""Focused tests for the offline legal structure chunker.

Covered here: article/chapter/annex chunks with a prefix line and page range,
header-only segments versus the preamble, the conservative heading shape,
catalog-only validity, malformed parser artifacts that fail per document while
the others continue, unsafe or oversized input that aborts before writing,
byte-identical double runs, the contract check, and the guarantee that chunks
never become answerable knowledge.
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.legal_structure_chunker import (
    CHUNKER,
    CHUNK_MANIFEST_VERSION,
    CHUNK_SET_VERSION,
    MAX_CHUNKS,
    MAX_MARKDOWN_BYTES,
    ChunkerError,
    check_contract,
    chunk_documents,
    heading_of,
    segments_of,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "knowledge" / "legal-chunk-set.schema.json"
DOCUMENT_SCHEMA = ROOT / "knowledge" / "legal-markdown-document.schema.json"
KNOWLEDGE = ROOT / "knowledge"
FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "legal_structure_chunker"
CLI = ROOT / "backend" / "scripts" / "chunk_legal_documents.py"
HEADING = " \u203a "
SEPARATOR = " \u00b7 "

DOCUMENT_A = (
    "<!-- page: 1 -->\n"
    "\n"
    "Decreto 123/2026, de 1 de enero (documento sintético)\n"
    "\n"
    "<!-- page: 2 -->\n"
    "\n"
    "CAPÍTULO II\n"
    "\n"
    "<!-- page: 3 -->\n"
    "\n"
    "Artículo 14. Objeto\n"
    "\n"
    "La solicitud se presenta en la oficina competente.\n"
    "\n"
    "Artículo 15. Plazo\n"
    "\n"
    "El plazo es de tres meses desde la publicación.\n"
    "\n"
    "<!-- page: 4 -->\n"
    "\n"
    "ANEXO I. Documentación\n"
    "\n"
    "Documento de identidad y resguardo de la solicitud.\n"
)


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def page_metadata(markdown):
    """Derive the parser's per-page line ranges from the page markers."""
    lines = markdown.splitlines()
    indexes = [index for index, line in enumerate(lines) if line.startswith("<!-- page: ")]
    pages = []
    for position, index in enumerate(indexes):
        limit = indexes[position + 1] if position + 1 < len(indexes) else len(lines)
        blocks = 0
        last = index + 1
        for line_index in range(index + 1, limit):
            if lines[line_index].strip():
                blocks += 1
                last = line_index + 1
        pages.append(
            {
                "page": int(lines[index].split(":", 1)[1].strip(" ->")),
                "line_start": index + 1,
                "line_end": last,
                "blocks": blocks,
                "tables": 0,
                "ocr": False,
                "empty": blocks == 0,
                "warnings": [],
            }
        )
    return pages


def parser_manifest(candidate_id, source_sha256, markdown, title):
    pages = page_metadata(markdown)
    return {
        "schema_version": "legal-markdown-document-v1",
        "parser": "manijero-markdown-parser-v1",
        "candidate_id": candidate_id,
        "title": title,
        "source_sha256": source_sha256,
        "source_path": "{}/original-{}.pdf".format(candidate_id, source_sha256),
        "upstream_extractor": "manijero-document-extractor-v1",
        "markdown_path": "{}/markdown-{}.md".format(candidate_id, source_sha256),
        "markdown_sha256": _hash(markdown.encode("utf-8")),
        "markdown_bytes": len(markdown.encode("utf-8")),
        "page_count": len(pages),
        "block_count": sum(page["blocks"] for page in pages),
        "character_count": sum(len(line) for line in markdown.splitlines() if line.strip()),
        "table_count": 0,
        "ocr_page_count": 0,
        "pages": pages,
        "capabilities": {
            name: {"status": "unavailable", "reason": "runtime_missing", "version": None}
            for name in ("layout", "tables", "ocr")
        },
        "warnings": [],
        "runtime": {"profile": "base", "signature": _hash(b"runtime")},
    }


def write_document(
    root,
    name="doc",
    markdown=DOCUMENT_A,
    *,
    title="Decreto 123/2026, de 1 de enero (documento sintético)",
    candidate_id=None,
    source_sha256=None,
    overrides=None,
    drop=(),
    write_markdown=True,
):
    """Write one parser artifact pair under ``root`` and return its identity."""
    root = Path(root)
    candidate_id = candidate_id or _hash("candidate-{}".format(name).encode())
    source_sha256 = source_sha256 or _hash("source-{}".format(name).encode())
    directory = root / candidate_id
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = directory / "markdown-{}.md".format(source_sha256)
    if write_markdown:
        markdown_path.write_text(markdown, encoding="utf-8")
    manifest = parser_manifest(candidate_id, source_sha256, markdown, title)
    manifest.update(overrides or {})
    for key in drop:
        manifest.pop(key, None)
    manifest_path = directory / "parse-{}.json".format(source_sha256)
    manifest_path.write_text(_canonical(manifest), encoding="utf-8")
    return {
        "candidate_id": candidate_id,
        "source_sha256": source_sha256,
        "directory": directory,
        "markdown_path": markdown_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def catalog_entry(source_sha256, **overrides):
    entry = {
        "id": "decreto-123-2026",
        "title": "Decreto 123/2026, de 1 de enero (revisado)",
        "issuing_body": "BOE",
        "original_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-00123",
        "published_on": "2099-01-02",
        "downloaded_on": "2099-03-01",
        "verified_on": "2099-03-02",
        "content_sha256": source_sha256,
        "review_status": "approved",
        "reviewed_by": "fixture-reviewer",
        "reviewed_on": "2099-03-01",
        "lifecycle_status": "current",
        "valid_until": "2099-12-31",
        "campaign": "2099",
        "critical": True,
        "applicability": {"crop": "olivo", "water_regime": "irrigated"},
    }
    entry.update(overrides)
    return entry


def write_catalog(path, entries=()):
    path = Path(path)
    path.write_text(
        _canonical({"schema_version": "source-catalog-v1", "sources": list(entries)}),
        encoding="utf-8",
    )
    return path


def load_cli_module():
    spec = importlib.util.spec_from_file_location("chunk_legal_documents_cli", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(documents, catalog, output):
    return load_cli_module().main(
        ["--documents", str(documents), "--catalog", str(catalog), "--output", str(output)]
    )


def artifact_of(output, identity):
    return (
        Path(output)
        / identity["candidate_id"]
        / "chunks-{}.json".format(identity["source_sha256"])
    )


def load_artifact(output, identity):
    path = artifact_of(output, identity)
    payload = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(payload)
    return payload


def run_manifest(output):
    path = Path(output) / "chunks-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(payload)
    return payload


def tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    }


def canonical_digests():
    names = ("source_catalog.json", "passages.json", "procedure_map.json")
    return {name: _hash((KNOWLEDGE / name).read_bytes()) for name in names}


# --- Scenario 1: article, chapter, and annex chunks ----------------------------------------


def test_article_chapter_and_annex_become_chunks_with_prefix_and_page_range(tmp_path):
    documents, output = tmp_path / "documents", tmp_path / "output"
    identity = write_document(documents, source_sha256=_hash(b"source-a"))
    write_catalog(
        tmp_path / "catalog.json", [catalog_entry(identity["source_sha256"])]
    )
    before_knowledge = canonical_digests()
    before_parser = {
        path.name: _hash(path.read_bytes())
        for path in identity["directory"].iterdir()
        if path.is_file()
    }

    report = chunk_documents(
        documents, tmp_path / "catalog.json", output
    )

    assert report["summary"]["documents"] == 1
    assert report["summary"]["chunked"] == 1
    assert report["summary"]["failed"] == 0
    assert report["documents"][0]["status"] == "chunked"
    assert report["documents"][0]["failure"] is None
    assert report["documents"][0]["chunk_count"] == 4

    artifact = load_artifact(output, identity)
    assert artifact["schema_version"] == CHUNK_SET_VERSION
    assert artifact["chunker"] == CHUNKER
    assert artifact["input"] == {
        "candidate_id": identity["candidate_id"],
        "source_sha256": identity["source_sha256"],
        "markdown_sha256": identity["manifest"]["markdown_sha256"],
        "title": "Decreto 123/2026, de 1 de enero (revisado)",
    }
    assert artifact["validity_status"] == "known"
    assert artifact["catalog"] == {
        "source_id": "decreto-123-2026",
        "catalog_sha256": _hash((tmp_path / "catalog.json").read_bytes()),
        "published_on": "2099-01-02",
        "lifecycle_status": "current",
        "valid_until": "2099-12-31",
        "campaign": "2099",
        "critical": True,
        "applicability": {"crop": "olivo", "water_regime": "irrigated"},
    }

    chunks = artifact["chunks"]
    assert [chunk["id"] for chunk in chunks] == [
        "decreto-123-2026-0001",
        "decreto-123-2026-0002",
        "decreto-123-2026-0003",
        "decreto-123-2026-0004",
    ]
    assert len({chunk["id"] for chunk in chunks}) == len(chunks)
    assert [chunk["heading_path"] for chunk in chunks] == [
        [],
        ["CAPÍTULO II", "Artículo 14. Objeto"],
        ["CAPÍTULO II", "Artículo 15. Plazo"],
        ["ANEXO I. Documentación"],
    ]
    assert [chunk["location"] for chunk in chunks] == [
        "Documento",
        "CAPÍTULO II" + HEADING + "Artículo 14. Objeto",
        "CAPÍTULO II" + HEADING + "Artículo 15. Plazo",
        "ANEXO I. Documentación",
    ]
    assert [(chunk["page_start"], chunk["page_end"]) for chunk in chunks] == [
        (1, 1),
        (3, 3),
        (3, 3),
        (4, 4),
    ]
    for chunk in chunks:
        assert chunk["candidate_id"] == identity["candidate_id"]
        assert chunk["source_sha256"] == identity["source_sha256"]
        assert chunk["markdown_sha256"] == identity["manifest"]["markdown_sha256"]
        assert chunk["character_count"] == len(chunk["text"])

    assert chunks[1]["text"] == (
        "[Decreto 123/2026, de 1 de enero (revisado)"
        + SEPARATOR
        + "CAPÍTULO II"
        + HEADING
        + "Artículo 14. Objeto]\n"
        "\n"
        "La solicitud se presenta en la oficina competente."
    )
    assert chunks[3]["text"].endswith("\n\nDocumento de identidad y resguardo de la solicitud.")
    assert "\u00b7" in chunks[1]["text"].splitlines()[0]
    assert HEADING in chunks[1]["text"].splitlines()[0]
    assert "<!-- page:" not in "".join(chunk["text"] for chunk in chunks)

    manifest = run_manifest(output)
    assert manifest["schema_version"] == CHUNK_MANIFEST_VERSION
    assert manifest["chunker"] == CHUNKER
    entry = manifest["documents"][0]
    assert entry["status"] == "chunked"
    assert entry["chunk_count"] == 4
    assert entry["artifact"] == "{}/chunks-{}.json".format(
        identity["candidate_id"], identity["source_sha256"]
    )
    assert entry["chunk_set_sha256"] == _hash(artifact_of(output, identity).read_bytes())

    text = artifact_of(output, identity).read_text(encoding="utf-8")
    assert str(ROOT) not in text and str(tmp_path) not in text
    assert not re.search(r"\d{4}-\d{2}-\d{2}T", text)
    assert text.endswith("}\n") and "\r" not in text

    assert canonical_digests() == before_knowledge
    assert {
        path.name: _hash(path.read_bytes())
        for path in identity["directory"].iterdir()
        if path.is_file()
    } == before_parser


# --- Scenario 2: header-only segments versus the preamble ----------------------------------


def test_header_only_chapter_emits_no_chunk_and_the_preamble_does(tmp_path):
    markdown = (
        "<!-- page: 1 -->\n"
        "\n"
        "Texto anterior a cualquier título.\n"
        "\n"
        "CAPÍTULO II\n"
        "\n"
        "Artículo 14. Objeto\n"
        "\n"
        "Cuerpo del artículo.\n"
    )
    documents = tmp_path / "documents"
    identity = write_document(documents, markdown=markdown, title="Documento sintético")
    write_catalog(tmp_path / "catalog.json")

    report = chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    assert report["documents"][0]["status"] == "chunked"
    artifact = load_artifact(tmp_path / "output", identity)
    chunks = artifact["chunks"]
    assert [chunk["location"] for chunk in chunks] == [
        "Documento",
        "CAPÍTULO II" + HEADING + "Artículo 14. Objeto",
    ]
    assert chunks[0]["heading_path"] == []
    assert chunks[0]["text"] == "[Documento sintético]\n\nTexto anterior a cualquier título."
    assert chunks[1]["heading_path"] == ["CAPÍTULO II", "Artículo 14. Objeto"]
    assert sum(1 for chunk in chunks if chunk["location"] == "Documento") == 1


# --- Scenario 3: only explicit heading-shaped lines split ----------------------------------


def test_prose_heading_mention_stays_inside_its_current_chunk(tmp_path):
    markdown = (
        "<!-- page: 1 -->\n"
        "\n"
        "CAPÍTULO I\n"
        "\n"
        "Artículo 1. Ámbito\n"
        "\n"
        "Artículo 14 de la presente Ley se cita aquí solo como ejemplo.\n"
        "\n"
        "Artículo 2. Efectos\n"
        "\n"
        "Texto final.\n"
    )
    documents = tmp_path / "documents"
    identity = write_document(documents, markdown=markdown, title="Documento sintético")
    write_catalog(tmp_path / "catalog.json")

    chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    chunks = load_artifact(tmp_path / "output", identity)["chunks"]
    assert [chunk["heading_path"] for chunk in chunks] == [
        ["CAPÍTULO I", "Artículo 1. Ámbito"],
        ["CAPÍTULO I", "Artículo 2. Efectos"],
    ]
    assert "Artículo 14 de la presente Ley" in chunks[0]["text"]
    assert "Artículo 14" not in chunks[1]["text"]


@pytest.mark.parametrize(
    "markdown",
    [
        "<!-- page: 1 -->\n\nSolo un párrafo sin títulos.\n",
        "<!-- page: 1 -->\n\n| Artículo | 14 |\n| --- | --- |\n| Objeto | Texto |\n",
    ],
    ids=["no_headings", "pipe_table_only"],
)
def test_unstructured_markdown_writes_no_chunk_artifact(tmp_path, markdown):
    documents = tmp_path / "documents"
    identity = write_document(documents, markdown=markdown, title="Documento sintético")
    write_catalog(tmp_path / "catalog.json")

    exit_code = run_cli(documents, tmp_path / "catalog.json", tmp_path / "output")

    assert exit_code == 0
    manifest = run_manifest(tmp_path / "output")
    entry = manifest["documents"][0]
    assert entry["status"] == "unstructured"
    assert entry["failure"] is None
    assert entry["chunk_count"] == 0
    assert entry["artifact"] is None
    assert entry["warnings"] == ["catalog_source_unknown", "no_structure_headings"]
    assert not artifact_of(tmp_path / "output", identity).exists()
    assert not identity["directory"].joinpath("chunks").exists()


def test_heading_shape_is_the_narrow_spanish_rule():
    assert heading_of("Artículo 14. Objeto") is not None
    assert heading_of("CAPÍTULO II") is not None
    assert heading_of("## ANEXO I. Documentación") is not None
    assert heading_of("Artículo 4 bis. Algo") is not None
    assert heading_of("Artículo único") is not None
    assert heading_of("Artículo 14 - Algo") is not None
    assert heading_of("Artículo 14 de la presente Ley") is None
    assert heading_of("El artículo 14 de la presente Ley") is None
    assert heading_of("Artículo 14. Objeto y ámbito") is not None
    assert heading_of("Capítulo II bis") is None
    assert heading_of("Título I") is None
    assert heading_of("Sección 2") is None
    assert heading_of("Disposición adicional primera") is None
    assert heading_of("Preámbulo") is None
    assert heading_of("1. Artículo 14") is None
    assert heading_of("a) Artículo 14") is None
    assert heading_of("| Artículo | 14 |") is None
    assert heading_of("<!-- page: 2 -->") is None
    assert heading_of("Artículo " + "9" * 300) is None


def test_annex_starts_a_fresh_path_and_paths_contain_only_explicit_headings():
    segments, has_heading = segments_of(
        [
            "<!-- page: 1 -->",
            "",
            "Título I",
            "",
            "preamble text",
            "",
            "Capítulo Primero",
            "",
            "Artículo 1. Uno",
            "",
            "Cuerpo uno.",
            "",
            "Disposición adicional primera",
            "",
            "Artículo 2. Dos",
            "",
            "Cuerpo dos.",
            "",
            "ANEXO I. Anexo",
            "",
            "Cuerpo del anexo.",
        ]
    )
    assert has_heading is True
    assert [segment.path for segment in segments] == [
        (),
        ("Capítulo Primero", "Artículo 1. Uno"),
        ("Capítulo Primero", "Artículo 2. Dos"),
        ("ANEXO I. Anexo",),
    ]


# --- Scenario 4: validity comes only from the reviewed catalog -----------------------------


def test_unmatched_catalog_keeps_validity_unknown_and_derives_no_value(tmp_path):
    markdown = (
        "<!-- page: 1 -->\n"
        "\n"
        "CAPÍTULO I\n"
        "\n"
        "Artículo 1. Vigencia\n"
        "\n"
        "Publicado el 2 de enero de 2099, campaña 2099, válido hasta el 31 de "
        "diciembre de 2099.\n"
    )
    documents = tmp_path / "documents"
    identity = write_document(
        documents,
        "unmatched",
        markdown,
        title="Resolución sin entrada en el catálogo",
        source_sha256=_hash(b"unmatched-source"),
    )
    write_catalog(tmp_path / "catalog.json", [catalog_entry(_hash(b"another-source"))])

    chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    artifact = load_artifact(tmp_path / "output", identity)
    assert artifact["validity_status"] == "unknown"
    assert "catalog" not in artifact
    assert artifact["warnings"] == ["catalog_source_unknown"]
    assert artifact["input"]["title"] == "Resolución sin entrada en el catálogo"
    assert artifact["chunks"][0]["id"] == "cand-{}-0001".format(
        identity["source_sha256"][:12]
    )
    for key in (
        "published_on",
        "lifecycle_status",
        "valid_until",
        "campaign",
        "critical",
        "applicability",
    ):
        assert key not in artifact
        assert key not in artifact["chunks"][0]
    assert "campaña 2099" in artifact["chunks"][0]["text"]


def test_catalog_block_copies_only_present_values(tmp_path):
    documents = tmp_path / "documents"
    identity = write_document(documents, "minimal")
    entry = catalog_entry(identity["source_sha256"])
    for key in ("valid_until", "campaign", "critical", "applicability"):
        entry.pop(key)
    write_catalog(tmp_path / "catalog.json", [entry])

    chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    artifact = load_artifact(tmp_path / "output", identity)
    assert artifact["validity_status"] == "known"
    assert set(artifact["catalog"]) == {
        "source_id",
        "catalog_sha256",
        "published_on",
        "lifecycle_status",
    }


# --- Scenario 5: malformed parser artifacts fail closed, per document ----------------------


def _break(case, identity):
    manifest = identity["manifest"]
    if case == "schema_version":
        identity["manifest_path"].write_text(
            _canonical({**manifest, "schema_version": "legal-markdown-document-v2"}),
            encoding="utf-8",
        )
    elif case == "unknown_key":
        identity["manifest_path"].write_text(
            _canonical({**manifest, "extra": True}), encoding="utf-8"
        )
    elif case == "candidate_mismatch":
        (identity["directory"] / "parse-{}.json".format(identity["source_sha256"])).write_text(
            _canonical({**manifest, "candidate_id": _hash(b"another-candidate")}),
            encoding="utf-8",
        )
    elif case == "missing_markdown":
        identity["markdown_path"].unlink()
    elif case == "markdown_hash_mismatch":
        identity["manifest_path"].write_text(
            _canonical({**manifest, "markdown_sha256": _hash(b"wrong")}), encoding="utf-8"
        )
    elif case == "markdown_byte_mismatch":
        identity["manifest_path"].write_text(
            _canonical({**manifest, "markdown_bytes": manifest["markdown_bytes"] + 1}),
            encoding="utf-8",
        )
    elif case == "page_map_mismatch":
        pages = [dict(page) for page in manifest["pages"]]
        pages[1]["line_start"] = pages[1]["line_start"] + 1
        identity["manifest_path"].write_text(
            _canonical({**manifest, "pages": pages}), encoding="utf-8"
        )
    else:  # pragma: no cover
        raise AssertionError(case)


@pytest.mark.parametrize(
    "case, code",
    [
        ("schema_version", "invalid_manifest"),
        ("unknown_key", "invalid_manifest"),
        ("candidate_mismatch", "candidate_mismatch"),
        ("missing_markdown", "missing_markdown"),
        ("markdown_hash_mismatch", "markdown_hash_mismatch"),
        ("markdown_byte_mismatch", "markdown_hash_mismatch"),
        ("page_map_mismatch", "page_map_mismatch"),
    ],
)
def test_a_malformed_document_fails_alone_and_keeps_its_previous_artifact(
    tmp_path, case, code
):
    documents, output = tmp_path / "documents", tmp_path / "output"
    good = write_document(documents, "good", source_sha256=_hash(b"good-source"))
    broken = write_document(documents, "broken", source_sha256=_hash(b"broken-source"))
    write_catalog(tmp_path / "catalog.json")
    _break(case, broken)

    previous = artifact_of(output, broken)
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_bytes(b'{"previous": true}\n')

    exit_code = run_cli(documents, tmp_path / "catalog.json", output)

    assert exit_code == 1
    manifest = run_manifest(output)
    entries = {entry["candidate_id"]: entry for entry in manifest["documents"]}
    failed = entries[broken["directory"].name]
    assert failed["status"] == "failed"
    assert failed["failure"] == code
    assert failed["chunk_count"] == 0
    assert failed["artifact"] is None
    assert failed["chunk_set_sha256"] is None
    assert entries[good["candidate_id"]]["status"] == "chunked"
    assert previous.read_bytes() == b'{"previous": true}\n'
    assert manifest["summary"] == {
        "documents": 2,
        "chunked": 1,
        "unstructured": 0,
        "failed": 1,
        "chunks": 4,
    }


def test_missing_title_fails_the_document(tmp_path):
    documents = tmp_path / "documents"
    identity = write_document(documents, "untitled", title=None)
    write_catalog(tmp_path / "catalog.json")

    report = chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    assert report["documents"][0]["status"] == "failed"
    assert report["documents"][0]["failure"] == "missing_title"
    assert not artifact_of(tmp_path / "output", identity).exists()


# --- Scenario 6: unsafe or oversized input ------------------------------------------------


def test_unsafe_output_roots_abort_before_writing(tmp_path, monkeypatch):
    documents = tmp_path / "documents"
    write_document(documents, source_sha256=_hash(b"source-a"))
    catalog = write_catalog(tmp_path / "catalog.json")

    knowledge_output = KNOWLEDGE / "chunk-output-should-not-exist"
    for output in (
        knowledge_output,
        documents,
        documents / "nested-output",
    ):
        with pytest.raises(ChunkerError):
            chunk_documents(documents, catalog, output)
        assert not Path(output).exists() or Path(output) == documents

    with pytest.raises(ChunkerError):
        chunk_documents(tmp_path / "missing-documents", catalog, tmp_path / "output")
    with pytest.raises(ChunkerError):
        chunk_documents(documents, tmp_path / "missing-catalog.json", tmp_path / "output")

    broken = tmp_path / "broken-catalog.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ChunkerError):
        chunk_documents(documents, broken, tmp_path / "output")

    invalid = write_catalog(
        tmp_path / "invalid-catalog.json",
        [catalog_entry("not-a-hash")],
    )
    with pytest.raises(ChunkerError):
        chunk_documents(documents, invalid, tmp_path / "output")
    assert not (tmp_path / "output").exists()
    assert not knowledge_output.exists()


def test_more_than_one_thousand_manifests_aborts_before_writing(tmp_path):
    documents = tmp_path / "documents"
    for index in range(1001):
        directory = documents / _hash("candidate-{}".format(index).encode())
        directory.mkdir(parents=True)
        (directory / "parse-{}.json".format(_hash(b"unused"))).write_text("{}", encoding="utf-8")
    catalog = write_catalog(tmp_path / "catalog.json")

    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--documents",
            str(documents),
            "--catalog",
            str(catalog),
            "--output",
            str(tmp_path / "output"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stderr.strip() == '{"error": "ChunkerError"}'
    assert not (tmp_path / "output").exists()


def test_oversized_markdown_fails_only_that_document(tmp_path):
    documents, output = tmp_path / "documents", tmp_path / "output"
    good = write_document(documents, "good", source_sha256=_hash(b"good-source"))
    huge_body = "x" * (MAX_MARKDOWN_BYTES + 10)
    huge = write_document(
        documents,
        "huge",
        "<!-- page: 1 -->\n\n" + huge_body + "\n",
        source_sha256=_hash(b"huge-source"),
    )
    write_catalog(tmp_path / "catalog.json")

    exit_code = run_cli(documents, tmp_path / "catalog.json", output)

    assert exit_code == 1
    entries = {entry["candidate_id"]: entry for entry in run_manifest(output)["documents"]}
    assert entries[huge["candidate_id"]]["failure"] == "size_limit_exceeded"
    assert entries[good["candidate_id"]]["status"] == "chunked"


def test_more_than_the_chunk_limit_fails_only_that_document(tmp_path):
    lines = ["<!-- page: 1 -->", ""]
    for index in range(MAX_CHUNKS + 1):
        lines.extend(
            ["Artículo {}. Cuerpo".format(index + 1), "", "Texto {}.".format(index + 1), ""]
        )
    documents = tmp_path / "documents"
    identity = write_document(documents, "many", "\n".join(lines), source_sha256=_hash(b"many"))
    write_catalog(tmp_path / "catalog.json")

    report = chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    assert report["documents"][0]["failure"] == "chunk_limit_exceeded"
    assert not artifact_of(tmp_path / "output", identity).exists()


def test_a_chunk_over_the_soft_limit_is_kept_whole_with_a_warning(tmp_path):
    body = "y" * 8100
    markdown = "<!-- page: 1 -->\n\nArtículo 1. Largo\n\n" + body + "\n"
    documents = tmp_path / "documents"
    identity = write_document(documents, "long", markdown, source_sha256=_hash(b"long"))
    write_catalog(tmp_path / "catalog.json")

    chunk_documents(documents, tmp_path / "catalog.json", tmp_path / "output")

    artifact = load_artifact(tmp_path / "output", identity)
    assert artifact["warnings"] == ["catalog_source_unknown", "chunk_over_soft_limit"]
    assert artifact["chunk_count"] == 1
    assert len(artifact["chunks"][0]["text"]) > 8000
    assert artifact["chunks"][0]["text"].endswith(body)


# --- Scenario 7: reproducible, non-answerable output --------------------------------------


def test_committed_fixtures_are_valid_parser_artifacts():
    validator = Draft202012Validator(json.loads(DOCUMENT_SCHEMA.read_text(encoding="utf-8")))
    manifests = sorted(FIXTURES.glob("documents/*/parse-*.json"))
    assert len(manifests) == 2
    for path in manifests:
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_two_runs_are_byte_identical_and_a_rerun_rewrites_nothing(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    catalog = FIXTURES / "source_catalog.json"

    assert run_cli(FIXTURES / "documents", catalog, first) == 0
    assert run_cli(FIXTURES / "documents", catalog, second) == 0
    assert tree(first) == tree(second)

    paths = sorted(path for path in first.rglob("*") if path.is_file())
    assert paths and not any(path.name.endswith(".tmp") for path in paths)
    stamps = {path: path.stat().st_mtime_ns for path in paths}
    again = load_cli_module().main(
        [
            "--documents",
            str(FIXTURES / "documents"),
            "--catalog",
            str(catalog),
            "--output",
            str(first),
        ]
    )
    assert again == 0
    assert {path: path.stat().st_mtime_ns for path in paths} == stamps

    for path in first.rglob("chunks-*.json"):
        Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(
            json.loads(path.read_text(encoding="utf-8"))
        )


def test_chunk_output_is_not_read_by_the_answer_path_and_changes_no_canonical_byte(tmp_path):
    before_knowledge = {
        path.name: _hash(path.read_bytes())
        for path in KNOWLEDGE.iterdir()
        if path.is_file()
    }
    write_catalog(tmp_path / "catalog.json")
    chunk_documents(FIXTURES / "documents", tmp_path / "catalog.json", tmp_path / "output")

    assert {
        path.name: _hash(path.read_bytes())
        for path in KNOWLEDGE.iterdir()
        if path.is_file()
    } == before_knowledge
    for path in (tmp_path / "output").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "review_status" not in text
        assert str(ROOT) not in text

    answer_path = (
        "main.py",
        "ask_api.py",
        "retrieval.py",
        "retrieval_backend.py",
        "generation.py",
        "readiness.py",
        "knowledge_release.py",
        "review_package.py",
    )
    for name in answer_path:
        assert "legal_structure_chunker" not in (ROOT / "backend" / "app" / name).read_text(
            encoding="utf-8"
        )
    for path in (ROOT / "backend" / "app").glob("*.py"):
        if path.name == "legal_structure_chunker.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "from app.legal_structure_chunker" not in text, path
        assert "import app.legal_structure_chunker" not in text, path


# --- Contract check -----------------------------------------------------------------------


def test_contract_check_agrees_with_the_committed_schema(capsys):
    assert check_contract() == []
    assert load_cli_module().main(["--check-contract"]) == 0
    output = capsys.readouterr().out.strip().splitlines()
    assert len(output) == 1
    assert CHUNK_SET_VERSION in output[0] and CHUNK_MANIFEST_VERSION in output[0]


def test_contract_check_reports_a_drifted_schema(tmp_path):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    schema["$defs"]["manifest"]["properties"]["chunker"]["const"] = "drifted"
    drifted = tmp_path / "drifted.json"
    drifted.write_text(_canonical(schema), encoding="utf-8")

    problems = check_contract(drifted)

    assert problems
    assert not check_contract(SCHEMA)


def test_check_contract_refuses_other_arguments(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CLI), "--check-contract", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--check-contract takes no other argument" in result.stderr
