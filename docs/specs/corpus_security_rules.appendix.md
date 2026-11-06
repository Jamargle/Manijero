# corpus_security_rules — appendix

## Repository research

### Files inspected

- `backend/app/document_ingestion.py` — the only publication-body fetch path; owns allowlist admission, fixed `FAILURES`, quarantine writes, and the `unchanged` fast path this feature extends.
- `backend/app/source_catalog.py` — single `ISSUER_ALLOWED_HOSTS`/`APPROVED_HOSTS` policy and catalog validation; reused, not replaced.
- `backend/app/release_gates.py` — `run_gates` structural gate and `GateOutcome.failures`; the indexing boundary for the canonical-content check.
- `backend/app/gemini_generation.py` — `GEMINI_INSTRUCTION`, `GEMINI_INSTRUCTION_VERSION`, and where the shared drafting instruction is built.
- `backend/app/local_generation.py` — sends the same instruction as the system message, so one instruction change covers both providers.
- `backend/scripts/ingest_official_documents.py` — operator CLI; report summary keys and exit 1 on failed/rejected candidates.
- `knowledge/official-ingestion-state.schema.json` — `additionalProperties: false` record contract that must accept the new `security` object.
- `knowledge/official-ingestion-document.schema.json`, `knowledge/passages.json` — extracted-block shape and the canonical `text`/`location` fields the canonical scan reads.
- `backend/tests/test_document_ingestion.py` — synthetic discovery/state helpers, `stub_fetch`, `build_pdf`, canonical-digest guard; the pattern for new ingestion tests.
- `backend/tests/test_generation.py` — `make_passage` and `verify_draft` assertion style for the injected-draft test.
- `backend/tests/test_gemini_generation.py` — asserts the exact instruction version string, so the bump must update it.
- `backend/tests/test_knowledge_update_review.py` — confirms a non-`extracted` candidate already fails package readiness, so no review-package change is needed.
- `scripts/init.sh` — `--feature <id>` executes the spec's verify block from the repo root; `--backend-tests` runs `pytest` from `backend/`.
- `docs/constraints/answers-and-knowledge.md`, `ARCHITECTURE.md`, `backend/README.md`, `knowledge/README.md` — durable rules and the operator/schema text this feature must keep true.
- `docs/archive/MasterPlanV3.md` §7.6 and A16/A17 — domain allowlist, provenance, text-as-data, no nominal listings, "malicious document tests pass".

### Existing patterns to follow

- Fixed, value-free failure categories; exception text and document text are never copied into state, report, or logs.
- Standard-library-only backend modules with offline tests; optional runtimes never imported at service import.
- Marks/rejections fail closed; a candidate never becomes answerable without a human-reviewed merge.
- Ingestion state rejects unknown keys, so new fields need `CANDIDATE_RECORD_KEYS` and the JSON Schema in the same change.
- Focused verification is a subset of `--fast`, published between `verify:start`/`verify:end`; feature-scoped `pytest` targets, no service, no network.

### Current gaps

- No detector: an allowlisted listing with names/DNI or a document addressing the model is parsed and quarantined like a norm.
- No purge: an earlier extraction of a now-excluded candidate keeps its original/extracted files.
- No canonical check: nothing prevents prohibited or personal text from being indexed if it reaches `knowledge/` by another path.
- The drafting instruction never states that fragments are data rather than instructions.
- No fixtures exercise A16/A17 ("malicious document tests pass").

## Implementation plan

1. Create `backend/app/corpus_security.py`: `SCAN_VERSION`, flag tokens, normalization, listing/injection detectors, bounded findings, `scan_canonical`.
2. Add the three synthetic fixtures under `backend/tests/fixtures/corpus_security/` (injection HTML, listing HTML, benign control).
3. In `document_ingestion.py`, scan extracted blocks before quarantine; reject `nominal_listing`/`prompt_injection`, rebuild the record from provenance with `security`, and delete the candidate directory behind a resolved-path check.
4. Extend `CANDIDATE_RECORD_KEYS`, `_load_state` acceptance, and the `unchanged` path with a current-scan requirement; rescan a stored extraction without refetch and purge when flagged.
5. Update `knowledge/official-ingestion-state.schema.json` with the optional `security` object (`scan_version`, fixed `flags`, bounded `findings`).
6. In `release_gates.run_gates`, add `corpus_security` when `scan_canonical(catalog, passages)` reports any flag.
7. Add the data-only clause to `GEMINI_INSTRUCTION` and bump `GEMINI_INSTRUCTION_VERSION` to `gemini-draft-v2`; update the exact-version test.
8. Write `backend/tests/test_corpus_security.py` and the small additions to `test_document_ingestion.py`, `test_generation.py`, `test_gemini_generation.py`.
9. Update `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `backend/README.md`, `knowledge/README.md`, `docs/risks-and-open-questions.md`.
10. Run the focused block, then `./scripts/init.sh --fast`; record one-line results in `## Feature evidence`.

## Verification plan

- `./scripts/init.sh --feature corpus_security_rules` — focused tier passes; offline pytest only, no network, no model.
- `./scripts/init.sh --fast` — full backend suite, catalog validator, and offline evaluators pass (new canonical scan does not reject the reviewed corpus).
- `./scripts/init.sh --verify` — full gate only if a shared/platform input changed (expected: not needed; no UI/contract change).
- New tests to name and assert:
  - `test_nominal_listing_is_rejected_without_keeping_content` — status/failure, no directory, no content paths.
  - `test_previous_extraction_is_purged_when_a_candidate_becomes_a_listing` and `test_legacy_extraction_is_rescanned_without_fetch` — purge and no refetch.
  - `test_prompt_injection_document_is_rejected_without_echoing_its_text` — sentinel sentence absent from state/report bytes.
  - `test_benign_official_wording_is_not_flagged` — extracted, empty flags.
  - `test_lookalike_host_is_rejected_before_the_security_scan` — allowlist precedence and provenance unchanged.
  - `test_release_gate_reports_corpus_security_for_instruction_or_identifier_text` — tampered copy of canonical inputs, `corpus_security` in failures.
  - `test_verify_draft_discards_a_draft_that_obeys_an_embedded_instruction` — unsupported figure/date rejected whole.
  - `test_generation_instruction_declares_fragments_as_data` — `gemini-draft-v2` and the clause.
- E2E: not added. The feature changes no API, authentication, routing, or client flow; the backend has no persistent E2E command for ingestion, which needs approved official hosts. The CLI report is exercised by the ingestion integration tests, and the operator check is the existing manual command with a synthetic discovery state (no live fetch required by the spec).

## Evidence to capture

- Focused tier command and one-line result.
- Fast tier command and one-line result.
- Names of new/changed tests with pass counts.
- Confirmation that no listing/injection text appears in serialized state or report fixtures, and that canonical knowledge digests are unchanged by tests.
- Any detector false positive/negative observed while writing fixtures, plus the final pattern boundaries.
- Honest limits to record in the acceptance record and risks: the detectors are conservative Spanish-first heuristics (English only for injection), they can miss a reworded listing or a novel instruction, and a false positive excludes a document from automation; the retained provenance is the official title, URLs, identity, and hashes only, never the listed rows.

## Feature evidence

### 2026-11-06 — implementer self-verification

- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature corpus_security_rules` — focused tier passed, `311 passed, 1 warning`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` — all 10 offline checks passed; backend `1895 passed, 4 skipped`, catalog valid, retrieval/generation/abstention/clarification/land-safety unchanged.
- New `backend/tests/test_corpus_security.py` — 24 tests at first verification (30 after the repair below): detector normalization/listing/injection/bounds/strict stored-shape, nominal rejection with schema validation and no content paths, purge of a prior extraction, legacy rescan without fetch (flagged purge and clean rescan from a missing or older scan), injection rejection with sentinel absent from state and report, benign control, allowlist-before-scan, invalid `security` fails closed, tampered-canonical gate (`corpus_security`), `gemini-draft-v2` clause, `verify_draft` discarding an obeyed embedded instruction, offline-only scan.
- Changed existing tests: `test_gemini_generation.py` asserts `gemini-draft-v2` plus the data-only clause; `test_local_generation.py` request helper uses the same version.
- No pasted logs. Canonical catalog/passages digests unchanged by the feature: `git diff --stat knowledge/` touches only `README.md` and `official-ingestion-state.schema.json`; `test_reviewed_corpus_trips_no_security_flag` asserts `scan_canonical` is empty on the reviewed corpus.
- Detector boundaries observed while writing fixtures: a body-prose mention ("el listado de documentos figura en el anexo") is clean; one DNI/NIE alone is clean; `actúa como` needs a model/assistant object; listing phrases count only in candidate/document titles and headings. No false positive on the reviewed corpus; no real listing/instruction document was available, so precision/recall stays unmeasured (recorded in `docs/progress/known-limitations.md`).
- Fixtures are synthetic and clearly labelled; the two identity shapes (`00000000T`, `X0000000L`) and names are invented and appear only inside the fixture.
- `./scripts/init.sh --verify` not run: no shared, Android/Desktop, contract, or packaging input changed.

### 2026-11-06 — implementer repair after validator `revise`

- HIGH fixed: `scan_blocks` sums identifier shapes over every title and block *before* deciding `nominal_listing`, while findings stay per contributing block as `{flag, page, block_index}`. A listing titled "Anexo I. Personas admitidas" with one DNI/NIE per HTML cell or PDF line now rejects the whole document.
- HIGH fixed: `scan_canonical` uses `CANONICAL_IDENTIFIER_THRESHOLD = 1`, so one DNI or NIE in catalog metadata, passage text, or `location` reports `corpus_security` and leaves `bm25_document is None`.
- New tests: `test_identifiers_are_counted_across_the_document_not_per_block`, `test_listing_split_across_table_cells_is_rejected_document_wide` (no listing noun in title or heading, no bytes/text retained), plus canonical cases for one DNI in passage text, one NIE in passage text, one DNI in a catalog title, and one DNI in `location`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature corpus_security_rules` — focused tier passed, `317 passed, 1 warning`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` — all 10 offline checks passed; backend `1901 passed, 4 skipped`.
- Coverage consolidation: the new ingestion and gate scenarios live in `backend/tests/test_corpus_security.py`, not the spec's expected `backend/tests/test_document_ingestion.py` / `backend/tests/test_generation.py`; the shared fixtures/helpers keep one module cheaper and the focused block still runs both files.
- Wording aligned in `backend/README.md`, `docs/constraints/answers-and-knowledge.md`, `docs/risks-and-open-questions.md`, and `docs/progress/known-limitations.md`: ingestion counts two shapes document-wide, the canonical gate rejects any single identifier shape; spec scenarios 1 and 5 updated minimally.


## Validator checklist

- [ ] Scope matches the contract; no new allowlist domain, UI, `/ask`, retrieval, or canonical rewrite.
- [ ] Scenarios 1–7 pass with evidence; nominal/injection rejections retain no bytes or text and keep provenance.
- [ ] Identifier shapes are counted across the whole extracted document before `nominal_listing`; a listing split across table cells or PDF lines with no listing noun in its title or heading is still rejected, and findings stay per block.
- [ ] Legacy/extracted quarantine is rescanned and purged without refetch; unchanged fast path requires the current scan.
- [ ] Canonical release gate reports `corpus_security` for a *single* identifier shape in catalog metadata, passage text, or `location`, and cannot publish; reviewed corpus still passes.
- [ ] `gemini-draft-v2` states fragments are data; `verify_draft` remains the sole answer authority.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature corpus_security_rules`; `--fast` passes.
- [ ] Durable docs updated once each: `ARCHITECTURE.md`, constraints, `backend/README.md`, `knowledge/README.md`, risks; nothing restated.
- [ ] `feature_list.json`, `PROGRESS.md`, and (`if accepted`) `docs/validations/corpus_security_rules.md` updated; limits stated honestly.
