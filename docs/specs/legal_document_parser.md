# Parse official PDFs into clean Markdown with tables and local Spanish OCR

## Source metadata

- `id`: legal_document_parser · `area`: knowledge · `depends_on`: official_document_candidate_ingestion (accepted) · `status` at planning: not_started
- User-visible behavior: none in the apps. A developer/agent runs one backend command over the accepted ingestion quarantine and gets, per PDF candidate, a clean Markdown file plus a provenance manifest (source hash, parser version, page mapping, capability statuses) outside `knowledge/`; nothing parsed becomes answerable.
- Verification: offline pytest over synthetic quarantines, in-process fake table/OCR adapters, and byte-identical double runs; the commands are in Focused verification.
- Notes (owner decisions, fixed):
  1. Scope is the full parser, but heavyweight dependencies MUST NOT enter the default runtime: follow the `backend/requirements-embeddings.txt` / `requirements-hybrid.txt` pattern of optional, exactly pinned requirement files with separate venvs, explicit graceful degradation, and recorded limits. The base backend (fastapi/uvicorn/httpx) and the default test suite stay free of torch/Docling/Tesseract.
  2. Verification must be deterministic in-process. A real Docling/Tesseract measurement on the owner's Mac is optional; if the runtime is absent, cover tables/OCR with small deterministic fixtures and declare the honest limit instead of claiming measured accuracy.
  3. Integration is a standalone backend command plus written per-document Markdown artifacts with provenance (source hash, parser version, page mapping). Do not change the accepted candidate-ingestion record contract, the `/ask` wire contract, or make parsed output answerable knowledge automatically; `legal_structure_chunker` consumes these artifacts later.
- Planning decisions: not owner-facing, so no `docs/owner-guide.md` step and no new `init.sh` mode; the optional runtime is installed with the existing named command `./scripts/init.sh --setup-python docparse` (profile `docparse` → `backend/.venv-docparse`). Only PDFs are parsed; HTML candidates are reported `skipped / not_a_pdf`.

## Goal

Turn the accepted, quarantined PDF originals into deterministic, review-friendly Markdown that a later structural chunker can split by article, chapter, and annex — with structure, tables, and Spanish OCR available when the optional runtime is installed, and with every capability that was unavailable or failed recorded instead of guessed.

## Non-goals

- No article/chapter/annex splitting, contextual prefixes, validity metadata, indexing, or retrieval (`legal_structure_chunker`, `structured_chunk_index`).
- No change to `backend/app/document_ingestion.py`, its state/document schemas, its quarantine layout, or any candidate `review_status`.
- No change to `/ask`, `/ready`, `/health`, `contracts/openapi.yaml`, retrieval, knowledge releases, the review merge, or the container image contents.
- No network access, no fetching, no model download, no paid OCR service; the command reads the quarantine only.
- No invented headings, table cells, or article numbers: structure comes only from an adapter that can derive it.
- No table/OCR accuracy claim beyond the deterministic fixtures, unless a real run is measured and recorded in the appendix.

## Job story

When a reviewed official PDF has been fetched into quarantine, I want one command that writes clean Markdown with page mapping and honest provenance, so that the next knowledge step can split and review it without re-parsing PDFs or trusting an undocumented conversion.

## Acceptance Scenarios

### 1. A text-layer PDF becomes clean Markdown with provenance

Given an extracted PDF candidate in an accepted `official-ingestion-state-v1` quarantine · When the command runs in the base runtime · Then `<output>/<candidate_id>/markdown-<source_sha256>.md` exists with one `<!-- page: N -->` marker per page in ascending order, whitespace-collapsed paragraphs, and no repeated page-edge line or page-number-only line, and the sibling `parse-<source_sha256>.json` reports the same `source_sha256`, `source_path`, `parser`, `upstream_extractor`, `markdown_sha256`, and per-page line ranges; canonical knowledge bytes are unchanged.

### 2. Ten documents parse reproducibly

Given ten synthetic official-style PDFs ingested into one quarantine · When the command runs twice into two different output roots · Then every document is `parsed` and the Markdown and manifest bytes are identical across runs: no timestamp, no absolute path, canonical JSON, LF endings, one trailing newline.

### 3. The base runtime degrades explicitly and stays light

Given a base `backend/.venv` without Docling, pymupdf4llm, or pytesseract · When the command runs and `--check-runtime` is asked · Then text-layer PDFs still parse with exit `0`, the report's `runtime` block marks `tables` and `ocr` `unavailable` with a fixed reason, no manifest claims either capability, one plain-language line per capability is printed, and importing `app.main` or the parser module loads none of `torch`, `docling`, `pymupdf`, `pytesseract`, or `chromadb`.

### 4. Tables come only from a capable adapter and are never invented

Given a page whose text layer holds an amount table and a capable table adapter (Docling in `docparse`, or the same interface faked in-process) · When the document is parsed · Then the Markdown holds exactly one pipe table with header row and separator whose cells equal the adapter rows, and the manifest counts it on that page. Given the base runtime · Then the same page stays paragraphs, the manifest warns `tables_runtime_unavailable`, and no cell or delimiter is added.

### 5. Scanned pages: Spanish OCR, or an honest failure

Given a PDF with no text layer · When the base runtime parses it · Then every page is recorded `empty` with warning `no_text_layer` and the document fails `no_extractable_text` without writing a Markdown file, leaving any previous artifact byte-identical. Given Tesseract with the `spa` language (or the same OCR adapter faked in-process) · Then OCR text appears under each page marker and the manifest marks those pages `ocr: true`. Given Tesseract without `spa` · Then OCR is `unavailable` with reason `language_missing` and the document fails as above.

### 6. Unsafe or inconsistent input fails closed

Given an output root inside `knowledge/`, an output root equal to the quarantine, an invalid ingestion state, or more than 1,000 candidates · When the command runs · Then it exits `2` with `{"error": "<TypeName>"}` on stderr and writes nothing. Given a missing original, a source hash mismatch, or an HTML candidate · Then that document is `failed` (`missing_source`, `source_hash_mismatch`) or `skipped` (`not_a_pdf`), every other document is still written, exit is `1` when any document failed, and the candidate's prior Markdown/manifest pair is untouched.

### 7. Parsed output is not answerable knowledge

Given a written output root · When `/ask`, retrieval, `/ready`, the release builder, and the review merge run · Then none of them reads that root, no `review_status` or canonical artifact changes, and the candidate stays `pending` until a human reviews it.

## Technical approach

- New stdlib-only `backend/app/legal_document_parser.py` owns the strict state read (reuse `app.change_impact.load_ingestion_state`), the block model, header/footer cleaning, the Markdown renderer, the manifest builder, capability detection, and the run loop with atomic writes. It never writes canonical knowledge and never changes ingestion state.
- One adapter interface, four implementations: `quarantine-text` (base; the accepted `official-ingestion-document-v1` blocks), `pymupdf4llm` (layout, headings, lists in `docparse`), `docling` (tables), `tesseract` (OCR of pages without a text layer, language `spa`). Optional imports happen inside functions; a missing or failing adapter degrades that capability only, with a fixed warning code. The report's `runtime` block reports each capability as `ready` or `unavailable` (plus reason and version); a manifest records `used`, `not_needed`, `unavailable`, or `failed` per capability.
- Renderer rules (code-owned, identical in both profiles): one `<!-- page: N -->` line per page; paragraphs, headings, list items, and pipe tables; cleaning removes only a page's first or last non-empty line, when it repeats (digits normalized) on at least 3 pages and half of all pages, or when it is page-number-only (`Página 12`, `- 12 -`, `12`); cleaning never empties a page; output is UTF-8 with LF, no trailing spaces, one trailing newline.
- Artifacts: `<output>/<candidate_id>/markdown-<source_sha256>.md` and `parse-<source_sha256>.json`, hash-named like the quarantine; canonical JSON with no timestamps and no absolute paths; `previous_markdown_sha256` records a superseded manifest's hash; the parser id is `manijero-markdown-parser-v1` and the contract is `knowledge/legal-markdown-document.schema.json` (`legal-markdown-document-v1`). The registry title stays in the manifest and is never injected into the body. The Markdown *is* document text, so the output root is operator-owned, outside `knowledge/`, and documented as access-controlled and unlogged.
- `unchanged` skip: same source hash, parser version, runtime signature (profile, capability statuses, adapter versions), and files present → no rewrite. Installing Docling or Tesseract changes the signature and reparses.
- Bounds: 1,000 documents, 5,000 blocks / 2,000,000 characters per document (mirroring ingestion), 8 MiB Markdown, 50 table pages, 100 OCR pages at 60 s each; exceeding a table/OCR budget degrades with a warning, exceeding a document budget fails that document closed.
- CLI `backend/scripts/parse_official_documents.py`: `--state`, `--quarantine`, `--output`, and a standalone `--check-runtime` (no other argument; prints one plain line per capability and exits `0`); exit `0`/`1`/`2` as in scenarios 3 and 6; a deterministic JSON report (`run`, `runtime`, `documents` sorted by `candidate_id`, `summary`, `state`, `quarantine`, `output`) with fixed failure and warning codes only — never document text, upstream exception text, or personal data.
- Optional runtime: `backend/requirements-docparse.txt` with exact pins resolved and recorded at implementation time, profile `docparse` in `scripts/python-env.sh`, linked as `backend/.venv-docparse`; excluded from the container image and never installed by the base profile. Tesseract stays a system binary; its detected version, `spa` availability, and the adapter versions are recorded in the manifest and in the appendix evidence.

## Expected file changes

- `backend/app/legal_document_parser.py` — create; state read, adapters, cleaning, renderer, manifest, run loop.
- `backend/scripts/parse_official_documents.py` — create; CLI, exit codes, JSON report, `--check-runtime`.
- `backend/requirements-docparse.txt` — create; optional exact pins (pymupdf4llm, docling, pytesseract).
- `scripts/python-env.sh`, `scripts/init.sh` — modify; `docparse` profile and usage line only.
- `knowledge/legal-markdown-document.schema.json` — create; readable manifest contract.
- `backend/tests/test_legal_document_parser.py` — create; scenarios 1–3 and 5–7 with fakes.
- `backend/tests/test_legal_document_parser_docparse.py` — create; `pytest.importorskip` real-runtime smoke.
- `backend/tests/test_container_image_files.py` — modify; the optional requirement file never enters the image.
- `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `backend/README.md`, `knowledge/README.md`, `docs/progress/known-limitations.md`, `PROGRESS.md` — see below.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line beside `document_ingestion.py`: the parser turns quarantined PDFs into derived Markdown artifacts outside `knowledge/`, with optional adapters and no answerability.
- `docs/constraints/answers-and-knowledge.md`: update — one MUST: parsed Markdown is derived review input, written outside `knowledge/`, never read by the answer path, never changing `review_status`; a missing optional runtime MUST degrade with a recorded limit, never silently or over the network.
- `AGENTS.md`: not needed — no workflow, startup, or repo-wide rule change.
- `backend/README.md`: update — new section of at most 30 lines: command, artifact layout, manifest fields, `--setup-python docparse`, degradation, bounds, exit codes.
- `knowledge/README.md`: update — one Files row for the new schema and one sentence in "Adding a document" pointing at the parser.
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update — one line: Markdown is derived, tables/OCR verified with fakes and fixtures unless a real run is measured, no accuracy claim.
- `docs/owner-guide.md`, `contracts/openapi.yaml`, `DESIGN.md`, `CONTEXT.md`: not needed — no owner operation, wire contract, UI, or domain term.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_legal_document_parser.py tests/test_document_ingestion.py tests/test_change_impact.py tests/test_container_image_files.py -q
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/parse_official_documents.py --check-runtime
```
<!-- verify:end -->

No owner walkthrough (owner decision). The optional heavy tier is not in the block: the implementer runs `./scripts/init.sh --setup-python docparse` and `test_legal_document_parser_docparse.py` only when the runtime is actually available, and otherwise records the limit. The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence.

## Appendix

See [`legal_document_parser.appendix.md`](legal_document_parser.appendix.md) for repository research, plan, evidence, and the validator checklist.
