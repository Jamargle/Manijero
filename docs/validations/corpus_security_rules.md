# Validation: corpus_security_rules

Verdict: accept (independent validator, after one `revise` cycle). No owner walkthrough: the spec's
verification is offline pytest plus the canonical gate, and no UI or operator step exists.

Spec: [../specs/corpus_security_rules.md](../specs/corpus_security_rules.md) · Evidence:
[appendix](../specs/corpus_security_rules.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature corpus_security_rules`: 317 passed, 1 warning (published block is accurate and unchanged).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 1901 passed, 4 skipped; harness 20 passed).
- `--verify` not rerun: the diff touches only `backend/`, `knowledge/`, docs, and the feature index, no `shared/`, apps, Gradle, contract, or packaging input.
- Independent probes beyond the tests: real HTML extraction of a listing with no list noun in title or heading yields one identifier per cell block (indexes 4 and 6) and `scan_blocks` rejects the whole document with findings at those blocks; one identifier in a title plus one in a body block also rejects; `scan_canonical` flags one DNI in passage text, one NIE in passage text, one DNI in `location`, and one DNI in a catalog title, and returns empty on the reviewed corpus.

## Repairs confirmed (prior `revise`)

- HIGH (per-block counting) fixed: `scan_blocks` sums identifier shapes over every title and block before deciding `nominal_listing`; findings stay per contributing block as `{flag, page, block_index}`, capped at 20.
- HIGH (canonical single identifier) fixed: `scan_canonical`/`flags_for_text` use `CANONICAL_IDENTIFIER_THRESHOLD = 1` over catalog string values, passage text, and `location`; `run_gates` adds `corpus_security` before readiness and leaves `bm25_document is None`.
- Spec scenarios 1 and 5, `backend/README.md`, the constraints rule, risks, and the known limitation now state the two-shape document-wide ingestion rule and the stricter one-shape canonical rule.

## Review

- Scenarios 1-7 map to the 30 tests in `backend/tests/test_corpus_security.py`: content-free nominal rejection with schema validation, purge of an earlier extraction, legacy rescan without refetch (purge when flagged, clean rescan otherwise), durable re-rejection for an unchanged version hash, injection rejection with the sentinel absent from state and report, benign control, lookalike host rejected before the scan, fail-closed invalid stored state, `gemini-draft-v2` data-only clause, `verify_draft` discarding an obeyed embedded instruction, and an offline-only detector (socket patched).
- Scope held: no new allowlist domain or host, no `/ask`, retrieval, contract, or Compose change; `knowledge/source_catalog.json` and `knowledge/passages.json` bytes are untouched.
- Test placement deviates from the spec's expected changes (ingestion and gate scenarios live in `test_corpus_security.py`, not `test_document_ingestion.py`/`test_generation.py`); documented in the appendix and the focused block runs both files.
- Security checklist: no secrets, fixtures synthetic, no new dependency, stdlib-only offline detector, resolved-path guards on purge and rescan, content-free state/report/logs, attempt history preserved.

## Accepted scope

A candidate whose official document is a nominal listing or carries model-directed text is `rejected`
with a fixed category, its record rebuilt from provenance plus the bounded `security` scan, and its
whole quarantine directory deleted; a legacy stored extraction is rescanned without refetch; the
unchanged fast path needs a current clean scan. The canonical gate refuses to publish on a single
identifier shape or an instruction in catalog metadata, passage text, or `location`. The shared
drafting instruction is `gemini-draft-v2` (fragments are data); `verify_draft` remains the answer
authority.

## Remaining limits

- Conservative Spanish-first heuristic (English only for injection): it can miss a reworded listing or a novel instruction; precision/recall is unmeasured and no real listing or malicious document was available.
- A false positive removes that document from automation; there is no override, only the normal human-reviewed corpus update.
- Identifier shapes cover DNI/NIE/affiliation-number only; other personal data (names, addresses) is not detected on its own.
- An excluded candidate is not refetched while its `version_hash` (title and URL) is unchanged, and an extractor upgrade re-fetches rather than reprocessing text.
- Purge uses `shutil.rmtree(..., ignore_errors=True)`: a failed delete would leave unreachable bytes on disk, not re-read by review or answers but not verified deleted.

## Follow-ups (recorded, not accepted behavior)

- `gemini-draft-v1` is still named in the accepted `gemini_generation_provider`, `local_generation_provider`, and `numeric_grounding_check` specs and in `docs/validations/local_generation_provider.md`; current code and this feature's docs say `gemini-draft-v2`. Accepted specs were left as historical records.
- `validate_security` accepts `page` 0/negative where `official-ingestion-state.schema.json` requires ≥ 1; unreachable through the extractor, whose page numbering starts at 1.
