# `official_document_candidate_ingestion` acceptance

## Verdict

**Accepted** on 2026-10-27 after one validator `revise` cycle and independent re-validation.

- Spec: [`official_document_candidate_ingestion.md`](../specs/official_document_candidate_ingestion.md)
- Evidence: [`official_document_candidate_ingestion.appendix.md`](../specs/official_document_candidate_ingestion.appendix.md)
- Reviewed scope: `backend/app/document_ingestion.py`, `backend/scripts/ingest_official_documents.py`, `backend/tests/test_document_ingestion.py`, `backend/tests/fixtures/document_ingestion/`, `knowledge/official-ingestion-state.schema.json`, `knowledge/official-ingestion-document.schema.json`, plus the operator/documentation updates in `backend/README.md`, `knowledge/README.md`, `ARCHITECTURE.md`, `PROGRESS.md`, this feature's spec/appendix, and the `feature_list.json` status line.

## Independent verification

- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_document_candidate_ingestion` — passed, 672 tests (one unrelated Starlette/httpx deprecation warning).
- `./scripts/init.sh --fast` — passed, all nine offline checks.
- `backend/.venv/bin/python -m pytest tests/test_document_ingestion.py -q` — 36 focused tests passed.
- `./scripts/init.sh --verify` was not run: the change is backend-only and does not touch the shared/Android/Desktop surface, packaging, the HTTP contract, or the answer path; the focused and fast tiers cover the changed code.
- Validator reproduced the limit behavior independently: 501 pages and 20,001 objects fail as `size_limit_exceeded` with no quarantine files written, while 500 pages / 20,000 objects extract successfully.
- Validator reproduced extractor-version refresh: an older stored `extractor` re-fetches and re-extracts, `last_success_at` advances, attempts increment, and a previously recorded `previous_original_sha256` is preserved.
- Validator reproduced workspace and state confinement: state/quarantine paths inside the repository `knowledge/` directory (including a symlink) fail as `unsafe_workspace` before any fetch or write; absolute, `..`, and out-of-candidate file paths in state are rejected as not present, forcing a refetch.
- Validator reproduced CLI exit behavior: `0` on success, `1` on a rejected/failed candidate with a fixed category and empty stderr, and `2` for invalid state, more than 1,000 candidates, knowledge-path configuration, and unexpected exceptions (`{"error": "<ExceptionType>"}`, no traceback or path).
- Validator re-ran the live smoke and matched the appendix numbers exactly: BOE `216,494` bytes, SHA-256 prefix `d9171daf4c871928`, 2 pages, 93 blocks, 4,179 characters, 0 `U+FFFD`; BOJA `307` → approved `www` host → `200`, 756,455 bytes, `9ef939b3dcfce748`, 35 pages, 1,767 blocks, 80,388 characters, 5,041 `U+FFFD` (6.27%). The documented `SSL_CERT_FILE`/`certifi` trust-store workaround was required; TLS verification was never disabled.
- Confirmed the canonical source catalog and passage artifacts are unchanged by ingestion, no secrets or land/personal details appear in reports or logs, and no other feature's spec or status was modified.

## Accepted scope and limitations

Pending `official-discovery-state-v1` candidates are admitted only for a known approved issuer and an exact approved HTTPS host; redirects are followed only within the same issuer's approved hosts, capped at three hops. Originals and provenance hashes are preserved in quarantine, PDF/HTML text is extracted with page or heading-path locations, and every record stays `review_status: pending`. Nothing quarantined becomes answerable knowledge automatically.

Accepted limits: no OCR (scanned or image-only PDFs fail `no_extractable_text`); no LZW/ASCII85/encrypted PDF support; incomplete subset-font `ToUnicode` maps can leave `U+FFFD` placeholders or drop glyphs (6.27% observed on one BOJA sample); extraction is line-level, not paragraph reconstruction, and is not an accuracy guarantee; HTML extraction is not a browser rendering; `page_count` counts pages that yielded text, not declared pages; monitoring feeds contribute zero document candidates because they retain snapshots only; discovery's `version_hash` covers title and URL only, so bytes changed behind a stable URL need a refetch; an extractor revision refetches and re-extracts rather than reprocessing stored bytes; quarantine grows across versions and is never garbage-collected; one writer per state/quarantine pair; state provenance values remain trusted operator input. Live smoke covers two documents on one date. No legal-coverage or answer-quality claim follows.

## Follow-ups (recorded, not accepted behavior)

- Same-name re-extraction of unchanged original bytes overwrites the previous `extracted-<sha256>.json`; only the original bytes are retained across an extractor revision. A later feature may version extracted text by extractor.
- The documented 15-second timeout is a per-operation socket/read timeout, not a total wall-clock cap for a slow-drip response.
- The knowledge-directory confinement test targets real repository paths; a regression would be caught by the assertion and digest checks rather than by a temporary knowledge root.
- The spec's planning wording still says "OCR is a separately measured fallback"; OCR is not implemented or measured.
