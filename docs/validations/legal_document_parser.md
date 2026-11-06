# Validation: `legal_document_parser`

Verdict: **accept** (independent validator, 2026-11-06; re-validation after one `revise` repair).
Spec: [legal_document_parser.md](../specs/legal_document_parser.md). Evidence: appendix "Feature evidence".

## Checks rerun
- `./scripts/init.sh --feature legal_document_parser`: `134 passed in 4.28s`; `--check-runtime` printed three `not available (the optional docparse environment is not installed)` lines, exit `0`.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend `1896 passed, 6 skipped`).
- `--verify` not rerun: the diff touches only `backend/`, `scripts/`, `knowledge/` and docs, with no `shared/`, `android*`, Gradle or packaging inputs.

## Findings
- End-to-end probe with a real ingestion state and quarantine: exit `0`, one document parsed, `not_a_pdf` and `not_extracted` skipped, two output roots byte-identical, manifests valid against `knowledge/legal-markdown-document.schema.json`, no absolute path or document text in the report.
- Fail-closed: an output root under `knowledge/` exits `2` with `{"error": "ParserError"}` and writes nothing; an output root nested in the quarantine reports `unsafe_output_root`.
- Bounds: 51 table pages keep 50 and warn `tables_page_budget_exceeded`; 102 empty OCR pages keep 100 and warn `ocr_page_budget_exceeded`; over-bound characters and blocks fail `size_limit_exceeded` per document.
- Default runtime stays light: importing `app.main` and the parser loads no torch, docling, pymupdf, pytesseract or chromadb; `requirements-docparse.txt` is pinned, isolated and excluded from the container image.
- Ingestion record, `/ask` contract, knowledge bytes and `review_status` are unchanged; the parser fetches nothing and logs no payload.
- Repair items confirmed: the optional smoke imports `Draft202012Validator` and collects as a skip, not an error; the README section shows the `backend/.venv-docparse/bin/python` run within its 30-line budget; `ocr_timeout` is reachable through the `RuntimeError` to `TimeoutError` translation; the unreachable `tables_page_unknown` and `not_installed` codes are gone; the four new focused tests cover the character bound, Markdown byte bound, table page budget and OCR page budget (main file: 25 tests).

## Unverified claims
- No Docling, pymupdf4llm or Tesseract runtime on this Mac: tables and Spanish OCR are covered by in-process fakes and small deterministic fixtures; no accuracy or real-document claim.
- No owner walkthrough: backend-only operator command with no UI surface.

## Remaining limits
- The optional `docparse` environment was never built here, so the real Docling/pymupdf4llm/Tesseract adapter paths are unexercised.
- A fully scanned PDF never reaches the parser: the accepted ingestion already fails it (`skipped / not_extracted`), so OCR applies only to text-less pages inside extracted PDFs.
- The artifact schema leaves `warnings` and `reason` unrestricted strings; fixed codes are enforced by the module and tests, not the schema.
- Parsed Markdown stays derived review input outside `knowledge/`; nothing becomes answerable knowledge automatically.
