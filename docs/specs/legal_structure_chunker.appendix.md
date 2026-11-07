# legal_structure_chunker — appendix

## Research

### Files read

- `PROGRESS.md` "Current state" — accepted command tiers and the "nothing converted is answerable" rule.
- `docs/specs/legal_structure_chunker.md` (parent) — status `not_started`, dependencies, no prior spec.
- `legal_document_parser` contract and `backend/README.md` "Markdown parsing of quarantined official PDFs" — artifact layout, manifest fields, exit codes to mirror.
- `backend/app/legal_document_parser.py` — `_render` (page markers and per-page ranges), `_canonical_json`/`_atomic_write_text`, `_parse_candidate` (manifest keys, `source_sha256`), runtime/`--check-*` CLI pattern.
- `knowledge/legal-markdown-document.schema.json` — `legal-markdown-document-v1` manifest shape consumed unchanged.
- `knowledge/source_catalog.schema.json`, `knowledge/source_catalog.json`, `backend/app/source_catalog.py` — reviewed fields (`title`, `published_on`, `lifecycle_status`, `valid_until`, `campaign`, `critical`, `applicability`), `load_catalog`/`validate_catalog`, `content_sha256` join key.
- `backend/app/change_impact.py` — accepted `by_content` join (`content_sha256`) and `instrument_keys`, reused as the join convention.
- `backend/app/document_ingestion.py` (block collector, read via grep) — headings come only from HTML extraction; base PDF extraction writes plain text blocks, so the Markdown often has no ATX headings.
- `knowledge/passages.schema.json` — `location` convention and the "unknown stays absent, never 'unknown'" rule for applicability.
- `docs/constraints/answers-and-knowledge.md` "Knowledge updates and retrieval" — parser rule this feature extends; the security and no-canonical-change rules that constrain chunk text.
- `docs/validations/legal_document_parser.md` — how its artifacts were exercised and its recorded limits.
- `backend/tests/test_legal_document_parser.py` — fixture/helper style (`add_candidate`, digest helpers, `load_cli_module`, subprocess CLI tests, `jsonschema` validation).
- `backend/tests/fixtures/` — fixture-directory convention; `scripts/init.sh` `run_feature` (`bash -euo pipefail`, five-line tail).

### Patterns followed

- One stdlib module + one thin CLI + one readable schema under `knowledge/` + one focused test file.
- Deterministic artifacts: canonical JSON, LF, one trailing newline, no timestamp or absolute path, hash-named files, atomic write, "unchanged" skip.
- Output roots refused under `knowledge/` and nested in the input root; report is JSON on stdout with fixed codes and no document text.
- `MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}"` in the published block, because `run_feature` runs with `set -u` and does not export it for this feature.
- Fallback `location: "Documento"` for text without a section, as ingestion already does.

### Gaps and findings that shaped the contract

- Base-runtime PDF Markdown has no ATX headings, so splitting cannot rely on `#`; the heading rule must be line-shape based. ATX markers are therefore stripped and never required.
- Heading shape must reject body sentences such as `Artículo 14 de la presente Ley ...`; requiring end-of-line or `. : – -` after the numeral separates real headings from prose. A heading written without one of those separators is deliberately not detected — a visible miss, never invented structure. The owner decision limits boundaries to article/chapter/annex, so `Título`, `Sección`, `Disposición`, and `Preámbulo` lines are path-neutral text and stay inside their chunk; this limit is recorded rather than extended unilaterally.
- No parser artifact is committed (the output root is operator-owned), so all evidence is synthetic and the verification block builds fixtures under `build/chunk-check/`.
- The catalog can be empty, and a parser output root can legitimately contain documents with no catalog entry; the join is optional and validity is then `unknown`, never guessed.

## Implementation plan

1. Create the schema `knowledge/legal-chunk-set.schema.json` with `legal-chunk-set-v1` (`$defs.chunk_set`) and `legal-chunk-manifest-v1` (`$defs.manifest`), top-level `oneOf`, closed objects, required keys exactly as in the contract.
2. Create `backend/app/legal_structure_chunker.py`: constants (`CHUNKER = "manijero-legal-chunker-v1"`, versions, bounds, fixed codes), `ChunkerError`.
3. Reader: enumerate `*/parse-<hash>.json`, validate strictly against the accepted manifest shape (version, keys, hashes, candidate id vs directory), load and hash the Markdown, verify `markdown_sha256`/`markdown_bytes`, collect page markers and compare with `pages[].line_start/line_end`.
4. Scanner: line model over the Markdown (page markers, ATX strip, boundary matcher for article/chapter/annex only, path stack and level truncation).
5. Segmenter: one segment per boundary heading, preamble segment, empty-body suppression, page start/end from markers.
6. Catalog join: `content_sha256 == source_sha256`, validity block from present reviewed fields only, `catalog_sha256`.
7. Chunk builder: id, ordinal, prefix line, verbatim body, character count, soft-limit warning; per-document `failed`/`unstructured` outcomes.
8. Artifact + manifest writer: canonical JSON, atomic writes, manifest last, unchanged detection.
9. CLI `backend/scripts/chunk_legal_documents.py`: arguments, path safety, exit codes, JSON report, `--check-contract`.
10. Fixtures: matched document (chapter → article → annex), unmatched document, prose-mention document, catalog with one valid entry; both fixtures hash-consistent.
11. Tests `backend/tests/test_legal_structure_chunker.py` covering scenarios 1–7, schema validation of every artifact, the `--check-contract` guard, and the answer-path/canonical-bytes guard.
12. Docs: `ARCHITECTURE.md` line, constraint MUST, `backend/README.md` ≤30-line section, `knowledge/README.md` row + sentence, limitation line + `PROGRESS.md` digest.

## Verification plan

- `./scripts/init.sh --feature legal_structure_chunker` — targeted pytest, contract check, and a byte-identical two-root CLI diff.
- Manually inspect `build/chunk-check/first/chunks-manifest.json` — statuses, chunk counts, no absolute path or document text.
- E2E: not applicable; developer-only offline command with no app, API, or owner surface, so unit/integration coverage plus the real-CLI diff is the evidence.

## Evidence to capture

- Targeted pytest result and the two-root `diff -r` result.
- `--check-contract` line.
- One artifact excerpt showing `heading_path`, `page_start/page_end`, `catalog.validity_status`, and the prefix line.
- Confirmation that `knowledge/` bytes, `review_status`, and the parser artifacts are unchanged after a run.
- Full `./scripts/init.sh --backend-tests` result once.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

- 2026-11-07 — `./scripts/init.sh --feature legal_structure_chunker` — focused tier passed: targeted
  pytest, the `--check-contract` line, and the two-root `diff -r` (identical); log in
  `build/verify-logs/feature-legal_structure_chunker.log`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_legal_structure_chunker.py -q`
  — `28 passed in 0.31s`.
- `backend/.venv/bin/python backend/scripts/chunk_legal_documents.py --check-contract` — `legal chunk
  contract OK: legal-chunk-set-v1 + legal-chunk-manifest-v1, chunker manijero-legal-chunker-v1, 9
  failure codes, 3 warning codes.`
- Two-root CLI run then `diff -r build/chunk-check/first build/chunk-check/second` — no output
  (byte-identical); the tests also assert a rerun into the same root leaves every file's
  `st_mtime_ns` unchanged.
- Manual check of `build/chunk-check/first/chunks-manifest.json` — 2 documents, both `chunked` (4 and
  3 chunks), one `catalog_source_unknown`; relative artifact paths only, no timestamp or absolute path.
- Manual artifact check — `decreto-123-2026-0002` has `heading_path ["CAPÍTULO II", "Artículo 14.
  Objeto"]`, pages 3–3, `validity_status: known`, text beginning `[Decreto 123/2026, de 1 de enero
  (documento sintético revisado) · CAPÍTULO II › Artículo 14. Objeto]` then the body; the `catalog`
  block carries only `source_id`, `catalog_sha256`, `published_on`, `lifecycle_status`, `valid_until`,
  `campaign`, `critical`, and `applicability`, copied from the reviewed entry.
- `./scripts/init.sh --fast` — all 10 offline checks passed (backend tests `2069 passed, 5 skipped`).
- `./scripts/init.sh --backend-tests` — `2069 passed, 5 skipped, 1 warning in 35.19s`.
- Unchanged/not answerable — tests compare every `knowledge/` file digest and the fixture parser
  artifacts before/after a run, assert no `review_status` in any output, and assert no answer-path
  module imports the chunker.
- Catalog `as_of` — fixed `CATALOG_AS_OF = 0001-01-01`, never the wall clock; documented in the module
  docstring, the spec's catalog-join bullet, and `backend/README.md`. Expiry stays retrieval's
  `--as-of`, so a reviewed `valid_until` that is past still joins and is copied verbatim.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no indexing, retrieval, canonical change, PDF re-read, or validity inference).
- [ ] Scenarios 1–7 pass with evidence, including the unmatched-catalog and prose-mention cases.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature legal_structure_chunker`.
- [ ] Schema and module agree (`--check-contract`), and every written artifact validates.
- [ ] Durable documentation impact followed; no fact restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly, with no accuracy or coverage claim.
