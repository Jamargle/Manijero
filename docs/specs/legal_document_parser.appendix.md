# legal_document_parser — appendix

## Repository research

### Files inspected

- `backend/app/document_ingestion.py` — accepted extractor: `manijero-document-extractor-v1`, state `official-ingestion-state-v1`, documents `official-ingestion-document-v1`; PDF blocks are `kind: text`, `page: N`, `section: "Página N"`, no title; quarantine holds `original-<sha256>.pdf` and `extracted-<sha256>.json`.
- `backend/scripts/ingest_official_documents.py` — CLI shape to mirror: explicit `--state/--quarantine`, JSON report on stdout, exit `1` on per-candidate failure, exit `2` with `{"error": "<TypeName>"}` and no traceback.
- `backend/app/change_impact.py` — `load_ingestion_state` is the public, narrow, fail-closed reader of that state (pending-only, sha/candidate patterns, 1,000-candidate cap); reuse it instead of duplicating validation.
- `backend/README.md` §"Manual official-document candidate ingestion" — the owner of the quarantine contract, its bounds, and its extraction limits; the new section follows it.
- `knowledge/official-ingestion-document.schema.json`, `knowledge/official-ingestion-state.schema.json` — field contracts the parser reads and must not extend.
- `knowledge/README.md` — Files table convention for readable schemas; "Adding a document" reviewer procedure; no automatic ingestion or chunking pipeline exists yet.
- `docs/constraints/answers-and-knowledge.md` §"Knowledge updates and retrieval" — quarantined-candidate and no-answerability rules the parser must extend.
- `docs/specs/official_document_candidate_ingestion.md` (+ archived appendix) — accepted scope, exit-code and evidence conventions.
- `backend/requirements-embeddings.txt`, `backend/requirements-hybrid.txt`, `scripts/python-env.sh`, `scripts/init.sh` — optional-profile pattern: exact pins, `--setup-python <profile>`, shared env under `.git/manijero-venvs`, symlink in `backend/`.
- `backend/tests/test_document_ingestion.py` — in-test `build_pdf()` generator, `stub_fetch`, `jsonschema` `Draft202012Validator` checks against the published schema; the parser tests follow it.
- `backend/tests/test_container_image_files.py` — exact `.dockerignore` allowlist and requirements assertions; the new requirement file must stay out of the image.
- `docs/specs/backend_health_metrics.md` — current compact contract shape and focused-verification block style.
- `PROGRESS.md` "Current state", `docs/progress/known-limitations.md` — wording and limits digest the new limitation joins.

### Existing patterns to follow

- Derived artifacts never live under `knowledge/`; they are hash-named, canonical JSON, written atomically (`_atomic_write_text` pattern), and never carry timestamps, reviewer names, or absolute paths.
- Failure codes are fixed, value-free strings; CLIs never print exception text, document text, or paths from upstream.
- Optional runtimes are lazy-imported per capability; the base profile and default tests never import them (see `docs/constraints/answers-and-knowledge.md` hybrid-retrieval rule).
- Python-env profiles are keyed by their requirement files, so adding a profile never rebuilds an existing one.
- `./scripts/init.sh --backend-tests <targets> -q` is the cheapest published check; `--feature <id>` runs the block unchanged.

### Current gaps

- No Markdown artifact, no page-mapped output, no header/footer cleaning, no table handling, no OCR anywhere in the repository.
- No `docparse` Python profile and no pinned optional parser requirements.
- No published schema for a parsed document.
- Real Docling/Tesseract accuracy is unmeasured; the repository has no sample table or scanned fixture and must not download one for this feature.

## Implementation plan

1. Add `knowledge/legal-markdown-document.schema.json` (`legal-markdown-document-v1`, `additionalProperties: false`) for the manifest described in the contract.
2. Implement the block model and the `quarantine-text` adapter over `load_ingestion_state` + `official-ingestion-document-v1` blocks; enforce the ingestion-mirroring bounds.
3. Implement cleaning (page-edge repetition, digit normalization, page-number pattern, never-empty-page) and the renderer (page markers, paragraphs, headings, list items, pipe tables, LF/one trailing newline).
4. Implement the manifest builder (hashes, page line ranges, capability block, warnings, `previous_markdown_sha256`), canonical JSON, and atomic writes under a validated output root.
5. Implement capability detection: profile, `find_spec` checks, Tesseract binary + `spa` via `pytesseract.get_languages()`, adapter version strings, fixed reasons (`runtime_missing`, `binary_missing`, `language_missing`, `adapter_failed`).
6. Implement the optional adapters (`pymupdf4llm` layout, `docling` tables, `tesseract` OCR) behind injectable factories so tests pass fakes.
7. Implement the run loop: per-document outcomes, unchanged skip by runtime signature, failure isolation, sorted report, summary, exit codes.
8. Add `backend/scripts/parse_official_documents.py` with the four arguments, `--check-runtime` plain-language lines, and the no-traceback error path.
9. Add `backend/requirements-docparse.txt` with exact pins resolved on this Mac (record the resolved versions), and the `docparse` profile in `scripts/python-env.sh` plus the `init.sh` usage line.
10. Add `backend/tests/test_legal_document_parser.py` (fakes) and `backend/tests/test_legal_document_parser_docparse.py` (`importorskip`), and the container-image exclusion assertion.
11. Update `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `backend/README.md`, `knowledge/README.md`, `docs/progress/known-limitations.md`, `PROGRESS.md`.

## Verification plan

- `./scripts/init.sh --feature legal_document_parser` — focused block passes: parser, ingestion, change-impact, and container-image tests, then `--check-runtime` prints one line per capability.
- Named tests (behavior, not implementation): text-layer Markdown with page mapping and provenance; header/footer and page-number cleaning with a never-empty-page case; ten-document byte-identical double run; base-runtime degradation and no-heavy-import guard; fake table adapter renders one pipe table and base adds none; fake OCR adapter fills text-less pages and Tesseract-without-`spa` degrades; unsafe output/state and per-document failure isolation; manifest validated against the published schema; parsed output unreachable from `/ask`, retrieval, and release code paths.
- Optional heavy tier (not in the block): `./scripts/init.sh --setup-python docparse`, then `MANIJERO_PYTHON=backend/.venv-docparse/bin/python ./scripts/init.sh --backend-tests tests/test_legal_document_parser_docparse.py -q`; if unavailable on this Mac, record the limit instead of claiming accuracy.
- Optional real-document measurement: parse one already-quarantined BOE and one BOJA PDF with `docparse` and record page count, table count, OCR pages, and one reviewer sentence per document in Feature evidence — never paste document text.
- E2E: none; no app, API, auth, or routing behavior changes, so in-process coverage is enough. No owner walkthrough by owner decision.

## Evidence to capture

- Focused block result, with the one-line `--check-runtime` output per capability.
- Ten-document double-run byte-identity result (command and pass/fail only).
- Resolved exact pins and Tesseract version/language detected, or the recorded reason they were unavailable.
- Full `./scripts/init.sh --backend-tests` result once.
- Confirmation that `knowledge/` digests and `review_status` are unchanged after a run.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-06 — implementer (status: `passing`, ready for independent validation).

- `./scripts/init.sh --feature legal_document_parser` → focused tier passed (`130 passed in 4.31s`), then `--check-runtime` printed three lines: layout, tables, and OCR each `not available (the optional docparse environment is not installed)`; exit `0`.
- `./scripts/init.sh --backend-tests` → `1892 passed, 6 skipped, 1 warning in 32.79s` (the 6 skips are the pre-existing optional-runtime files plus the new `test_legal_document_parser_docparse.py`).
- `./scripts/init.sh --fast` → all 10 offline checks passed (backend suite included).
- Ten-document double run is covered by `test_ten_documents_are_byte_identical_across_two_output_roots`: ten synthetic quarantines, two output roots, every Markdown and manifest byte-identical and every document `parsed`.
- Canonical knowledge and state are unchanged after a run (`test_text_layer_pdf_becomes_page_mapped_markdown_with_provenance`, `test_parsed_output_is_never_read_by_the_answer_path`): `source_catalog.json`/`passages.json` digests equal, state bytes equal, `review_status` still `pending`.
- No-heavy-import guard passes: importing `app.main` and `app.legal_document_parser` loads none of torch, docling, pymupdf/fitz, pymupdf4llm, pytesseract, chromadb.
- Resolved exact pins (via `uv pip compile --python-version 3.12`, 2026-11-06): `pymupdf4llm==2.1`, `pymupdf==2.1`, `docling==2.148.0`, `pytesseract==0.3.13`; the full docling closure is 354 resolved lines and pulls `torch==2.15.0`, which conflicts with the embeddings pin, so it stays a separate profile and is never combined with `hybrid`.
- Optional heavy tier NOT run: no Docling/pymupdf4llm/Tesseract runtime is installed on this Mac (`tesseract` is not on PATH either), so `./scripts/init.sh --setup-python docparse`, `test_legal_document_parser_docparse.py`, and the real-document BOE/BOJA measurement are unexecuted. Tables and OCR are verified only with in-process fakes and small deterministic fixtures; no accuracy is claimed.
- Decisions taken while implementing (recorded in `docs/progress/known-limitations.md` and `backend/README.md`): the parser derives the page range from the accepted stdlib PDF page walk, so text-less pages inside an otherwise extracted PDF reach OCR; a fully scanned PDF is already failed by accepted ingestion and arrives as `skipped / not_extracted`; the optional-runtime reason `language_missing` is exercised through an injected capability, not a real Tesseract.

2026-11-06 — repair after validator `revise` (status stays `passing`).

- Fixed the optional smoke's unbound name: `backend/tests/test_legal_document_parser_docparse.py` now imports `Draft202012Validator` and drops the unused capability-name imports. A scope-aware AST check over that file, `test_legal_document_parser.py`, the module, and the CLI reports no other undefined name.
- `backend/README.md` "Markdown parsing" section now shows the optional-runtime run from `backend/.venv-docparse/bin/python backend/scripts/parse_official_documents.py` and is exactly 30 lines.
- Removed unreachable codes: `tables_page_unknown` and the `not_installed` reason are deleted. pytesseract reports its own `timeout` option as a `RuntimeError`, so the adapter translates only that (message contains "timeout") into `TimeoutError`, which the run loop records as `ocr_timeout` and degrades one page; any other `RuntimeError` still degrades the capability.
- New focused tests (4): a document over the character bound and one over the Markdown byte bound both fail `size_limit_exceeded` with no artifact; the table page budget keeps only the budgeted pages and warns `tables_page_budget_exceeded`; the OCR page budget warns `ocr_page_budget_exceeded`, OCRs only the budgeted page, and leaves the rest `empty`.
- `./scripts/init.sh --feature legal_document_parser` → passed, `134 passed in 4.28s`; `--check-runtime` unchanged (three unavailable lines, exit `0`).
- `./scripts/init.sh --fast` → all 10 offline checks passed.

2026-11-06 — independent validator (verdict: `accept`; record in
[legal_document_parser.md](../validations/legal_document_parser.md)).

- `./scripts/init.sh --feature legal_document_parser` → `134 passed in 4.28s`; `--check-runtime` exit `0`.
- `./scripts/init.sh --fast` → all 10 offline checks passed (backend `1896 passed, 6 skipped`).


## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no chunking, no ingestion or wire-contract change, no answerability).
- [ ] Acceptance scenarios 1–7 pass, with evidence.
- [ ] Base runtime and default tests import no torch/Docling/pymupdf/pytesseract/chromadb; the optional requirement file is outside the container image.
- [ ] Artifacts are hash-named, deterministic, outside `knowledge/`, and schema-valid; no timestamp, absolute path, or document text in the report.
- [ ] Degradation and failure codes are fixed strings; limits are recorded honestly in the appendix and known limitations.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature legal_document_parser`.
- [ ] Durable documentation impact followed; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly by the implementer.
