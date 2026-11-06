# Split parsed legal documents by article, chapter, and annex with contextual prefixes and reviewed validity metadata

## Source metadata

- `id`: legal_structure_chunker · `area`: knowledge · `depends_on`: legal_document_parser (accepted), source_catalog_validation (accepted) · `status` at planning: not_started
- User-visible behavior: none in the apps. A developer runs one offline backend command over the accepted parser's Markdown plus provenance manifests and the reviewed source catalog, and gets one deterministic chunk artifact per document plus one deterministic run manifest, outside `knowledge/`; nothing it writes becomes answerable.
- Verification: offline pytest over synthetic parser artifacts and a two-root CLI diff; the commands are in Focused verification.
- Notes (owner decisions, 2026-11-06, fixed):
  1. Standalone offline backend command over the `legal_document_parser` Markdown + manifest, writing chunk artifacts and a deterministic manifest outside `knowledge/`; never answerable, never read by `/ask`, retrieval, readiness, release builder, or review merge, and no canonical change.
  2. Split deterministically only on explicit article/chapter/annex headings present in the Markdown (Spanish forms); preserve page mapping and source hash; add a contextual prefix with the source title and heading path.
  3. Validity metadata comes only from reviewed source/catalog metadata; otherwise keep it unknown, and never infer or parse dates from free text.
  4. No model, no network, no OCR in the chunker; bounded input and fail-closed on malformed manifests.
  5. Developer-only: no `docs/owner-guide.md` step and no new `init.sh` mode.
  6. Acceptance: validator accept is final; no owner walkthrough.

## Goal

Turn each reviewed, page-mapped parsed document into structure-faithful chunks — one per article/annex segment instead of one page blob — so a later reviewed indexing step can cite `Artículo 14` with an honest page range, an unchanged source hash, and only catalog-approved validity metadata.

## Non-goals

- No PDF/HTML re-reading, OCR, download, model call, embedding, or index build (`structured_chunk_index`); no retrieval, `/ask`, `/ready`, release, or review-merge change.
- No canonical write: no `review_status`, catalog, passage, evaluation, or release change; only a schema file is added under `knowledge/`.
- No inferred structure: no splitting on numbered sub-items (`1.`, `a)`), tables, or layout/font cues; no token-window subdivision or overlap.
- No boundary beyond the owner decision: `Título`, `Sección`, `Disposición`, and `Preámbulo` lines never split a document, so such text stays in its enclosing chunk and the limit is recorded.
- No validity inference: no date, campaign, applicability, or in-force reading from document text; no expiry evaluation (retrieval already filters with `--as-of`).
- No owner-facing operation, no `docs/owner-guide.md` step.

## Job story

When an official PDF has been parsed into page-mapped Markdown with a provenance manifest, I want one offline command that cuts it into article-scale chunks carrying the reviewed source title, heading path, and page range, so a reviewer and the later index can point at one provision without re-parsing the PDF or trusting guessed metadata.

## Acceptance Scenarios

### 1. Article, chapter, and annex become chunks with a prefix and page range

Given a synthetic parser output root holding one manifest and its Markdown with `<!-- page: N -->` markers · When the command runs · Then `chunks-<source_sha256>.json` holds one chunk per non-empty article/chapter/annex segment in document order, each with `heading_path`, `location`, `page_start`/`page_end` from the markers, `source_sha256`, `markdown_sha256`, `candidate_id`, a unique stable `id`, and text beginning with one prefix line `[<source title> · <path>]` followed by the verbatim body; the run manifest lists it as `chunked`, and the catalog, passages, and parser artifacts are byte-identical afterwards.

### 2. Header-only segments do not become chunks; the preamble does

Given Markdown where `CAPÍTULO II` is followed immediately by `Artículo 14` · When the command runs · Then no empty chunk is emitted for the chapter, the article chunk's `heading_path` still names that chapter, and text before the first heading is emitted once as the `preamble` chunk with `location: "Documento"` and an empty path.

### 3. Only explicit, heading-shaped lines split; nothing is invented

Given a paragraph that begins `Artículo 14 de la presente Ley ...` mid-document, a Markdown with no heading-shaped line, and a Markdown whose only heading-shaped line is a pipe-table row · When the command runs · Then the first stays inside its current chunk, and the other two are `unstructured` with warning `no_structure_headings`, no chunk artifact written, exit `0`; a boundary heading needs an article/chapter/annex label, a numeral, and end-of-line or one of `. : – -` after it.

### 4. Validity metadata comes only from the reviewed catalog

Given a document whose `source_sha256` equals one approved catalog `content_sha256` · When the command runs · Then the artifact's `catalog` block copies only `source_id`, `catalog_sha256`, and the catalog's present `published_on`, `lifecycle_status`, `valid_until`, `campaign`, `critical`, and `applicability` values, with `validity_status: "known"`. Given no matching entry, or dates/campaign words inside the body text · Then the artifact has no `catalog` block, reports `validity_status: "unknown"` with warning `catalog_source_unknown`, and derives no value from the text.

### 5. Malformed parser artifacts fail closed and per document

Given a manifest with a wrong `schema_version`, an unknown key, a `candidate_id` that mismatches its directory, a missing Markdown file, a Markdown hash or byte-count mismatch, or page markers inconsistent with the manifest page ranges · When the command runs · Then that document is `failed` with one fixed code (`invalid_manifest`, `candidate_mismatch`, `missing_markdown`, `markdown_hash_mismatch`, `page_map_mismatch`), its previous artifact stays byte-identical, every other document is still processed, and exit is `1`.

### 6. Unsafe or oversized input aborts before writing

Given an output root under `knowledge/`, an output root equal to or inside the documents root, a missing root, an unreadable or invalid catalog, or more than 1,000 manifests · When the command runs · Then it exits `2` with `{"error": "ChunkerError"}` on stderr and writes nothing. Given a document over 8 MiB of Markdown or over 2,000 chunks · Then only that document is `failed` (`size_limit_exceeded`, `chunk_limit_exceeded`); a chunk whose text, prefix included, exceeds 8,000 characters is kept whole with warning `chunk_over_soft_limit`.

### 7. Runs are reproducible and chunk output is not answerable

Given the same documents root run twice into two output roots · When both complete · Then artifacts and manifests are byte-identical (canonical JSON, sorted keys, LF, one trailing newline, no timestamp or absolute path); rerunning into the same root rewrites nothing that already matches. Then `/ask`, retrieval, `/ready`, the release builder, and the review merge still read none of that output, and no `review_status` or canonical byte changes.

## Technical approach

- New stdlib-only `backend/app/legal_structure_chunker.py` owns the strict artifact reader, the heading scanner, the segmenter, the prefix and chunk builders, the catalog join, the run loop with atomic writes, and the deterministic report. It reuses the pattern (not the adapters) of `app/legal_document_parser.py` and reads `app/source_catalog.load_catalog`/`validate_catalog` unchanged.
- CLI `backend/scripts/chunk_legal_documents.py`: `--documents`, `--catalog`, `--output`, plus standalone `--check-contract` (no other argument) that validates the committed schema and the module's version constants, prints one plain line, and exits `0`. Exit `0`/`1`/`2` as in scenarios 3/5/6.
- Heading rule (code-owned, identical in every parser runtime): strip a leading ATX marker; a boundary heading is a standalone line of at most 200 characters that starts at line start with `Artículo|ARTÍCULO|Articulo|ARTICULO`, `Capítulo|CAPÍTULO`, or `Anexo|ANEXO` (case-insensitive), followed by a numeral (`[IVXLCDM]+`, digits, `único/única`, `primero/primera`, optional `bis|ter|quater` for articles) and then end-of-line or one of `. : – -`. Table rows (`|`), list items, `<!-- page: N -->` lines, and every other label (`Título`, `Sección`, `Disposición`, `Preámbulo`) never open a chunk. `kind` and level come from the label: chapter 1, article 2, annex 1 (an annex starts a fresh path); a heading truncates the path at its own level and appends itself, so the path nests only detected headings.
- Segments: every heading opens a segment ending at the next heading at any level; empty bodies emit no chunk. Chunk `id` is `<catalog source_id>` or `cand-<first 12 hex of source_sha256>` plus a 4-digit ordinal (`0001`); `location` is the path joined by ` › ` (`Documento` for the preamble) and `character_count` counts the chunk text, prefix included. Chunk text is `[<source title> · <path>]` (path omitted when empty, joined by ` › `) plus a blank line and the body verbatim: markers removed, surrounding blank lines trimmed, never rewrapped. Source title is the catalog `title` when resolved, else the manifest `title`; when neither exists the document is `failed` (`missing_title`).
- Catalog join is by `content_sha256 == source_sha256` only (the accepted join used by `app/change_impact.py`). The artifact stores the validity block once at document level and each chunk inherits it; `catalog_sha256` is the hash of the catalog file read. `validate_catalog` needs an explicit `as_of`, so the chunker passes a fixed `CATALOG_AS_OF` (`0001-01-01`) and never reads the wall clock: repeated runs stay byte-identical, and expiry remains a retrieval concern (`--as-of`), so a reviewed `valid_until` that is already past still joins and is copied verbatim.
- Artifacts: manifests are the `<output>/<candidate_id>/parse-<source_sha256>.json` files found under `--documents` (other files ignored, a directory without a manifest ignored). Each artifact is `<output>/<candidate_id>/chunks-<source_sha256>.json` (`legal-chunk-set-v1`: `schema_version`, `chunker`, `input` with `candidate_id`/`source_sha256`/`markdown_sha256`/`title`, `validity_status`, optional `catalog`, `chunk_count`, `chunks`, `warnings`), and `<output>/chunks-manifest.json` (`legal-chunk-manifest-v1`, written last, relative artifact paths, per-document status/chunk count/hash, fixed codes only). Both shapes live in `knowledge/legal-chunk-set.schema.json`; canonical JSON is sorted-key `indent=2` plus one trailing newline, with no timestamp or absolute path. A non-`chunked` outcome never deletes an earlier artifact.
- Bounds: 1,000 manifests, 8 MiB Markdown and 2,000 chunks per document, 200-character heading lines; the stdout report (`run`, `catalog`, `documents_root`, `output`, `documents` sorted by `candidate_id`, `summary`) carries fixed codes and never document text.

## Expected file changes

- `backend/app/legal_structure_chunker.py` — create; reader, scanner, segmenter, catalog join, artifacts, report.
- `backend/scripts/chunk_legal_documents.py` — create; CLI, exit codes, `--check-contract`.
- `knowledge/legal-chunk-set.schema.json` — create; readable chunk-set and run-manifest contract (no data).
- `backend/tests/test_legal_structure_chunker.py` — create; scenarios 1–7.
- `backend/tests/fixtures/legal_structure_chunker/` — create; `documents/` with one matched and one unmatched hash-addressed candidate (manifest + Markdown) plus a reviewed `source_catalog.json`; unstructured and malformed cases are built in tests.
- `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `backend/README.md`, `knowledge/README.md`, `docs/progress/known-limitations.md`, `PROGRESS.md` — see below.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line beside `legal_document_parser.py`: the chunker turns that Markdown into structure chunks with reviewed validity, outside `knowledge/`, never read by the answer path.
- `docs/constraints/answers-and-knowledge.md`: update, under "Knowledge updates and retrieval" — one MUST: chunk artifacts are derived review input outside `knowledge/`, split only on explicit headings, validity only from reviewed metadata, never read by the answer path or a merge.
- `AGENTS.md`: not needed — no workflow, startup, or repo-wide rule change.
- `backend/README.md`: update — one section of at most 30 lines: command, artifact layout, heading rule, catalog join, bounds, exit codes.
- `knowledge/README.md`: update — one Files row for the schema and one sentence in "Adding a document".
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update — one line: heading detection is a conservative Spanish shape rule limited to article/chapter/annex (títulos, secciones, and disposiciones stay inside their chunk), validity is only as reviewed as the catalog, chunks are never answerable, and no accuracy is claimed.
- `docs/owner-guide.md`, `contracts/openapi.yaml`, `DESIGN.md`, `CONTEXT.md`, `scripts/init.sh`, `scripts/python-env.sh`: not needed — developer-only, stdlib, no wire, UI, domain, or command change.

## Focused verification (required)

<!-- verify:start -->
```sh
PY="${MANIJERO_PYTHON:-backend/.venv/bin/python}"
MANIJERO_PYTHON="$PY" ./scripts/init.sh --backend-tests tests/test_legal_structure_chunker.py -q
"$PY" backend/scripts/chunk_legal_documents.py --check-contract
rm -rf build/chunk-check
"$PY" backend/scripts/chunk_legal_documents.py --documents backend/tests/fixtures/legal_structure_chunker/documents --catalog backend/tests/fixtures/legal_structure_chunker/source_catalog.json --output build/chunk-check/first
"$PY" backend/scripts/chunk_legal_documents.py --documents backend/tests/fixtures/legal_structure_chunker/documents --catalog backend/tests/fixtures/legal_structure_chunker/source_catalog.json --output build/chunk-check/second
diff -r build/chunk-check/first build/chunk-check/second
```
<!-- verify:end -->

No owner walkthrough (owner decision). The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence; no optional runtime and no network are involved.

## Appendix

See [`legal_structure_chunker.appendix.md`](legal_structure_chunker.appendix.md) for research, plan, evidence, and the validator checklist.
