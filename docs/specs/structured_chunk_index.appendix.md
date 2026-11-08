# structured_chunk_index — appendix

## Research

### Files read

- `docs/specs/legal_structure_chunker.md`: chunk-set and manifest shape, chunk id `<source_id>-NNNN`, catalog join by `content_sha256`, `validity_status`, and fixed codes.
- `backend/app/legal_structure_chunker.py`: version and key constants (`CHUNK_SET_VERSION`, `CHUNK_KEYS`, `CATALOG_BLOCK_KEYS`, `DOCUMENT_KEYS`, `RUN_MANIFEST_NAME`). It exports no strict chunk-set reader, so the new module needs one.
- `backend/tests/fixtures/legal_structure_chunker/`: one candidate matches the reviewed catalog entry `decreto-123-2026` (campaign `2099`, `valid_until` `2099-12-31`), and one does not match. This gives the positive and the unreviewed case.
- `docs/specs/chroma_hybrid_retrieval.md` and `docs/archive/specs/chroma_hybrid_retrieval.appendix.md`: `Retriever.with_ranker`, store freshness keyed to admitted documents, lazy heavy imports, and the fake-embedder test pattern.
- `backend/app/retrieval.py`: `passage-set-v1` keys and slug pattern (chunk ids comply). `_build_record` falls back to catalog `applicability`/`critical`. `indexed_documents` and `admitted_fingerprint` are relevant here.
- `backend/app/retrieval_backend.py`: env-selected BM25/hybrid backend. Freshness is checked per request against the current retriever, so a store built from the structured passages is fresh with no code change.
- `backend/app/embedding_index.py` and `backend/app/vector_store.py`: the writers already take catalog and passages inputs and refuse `knowledge/`. `manage_vector_store.py` and `manage_embeddings.py` accept `--catalog`/`--passages`.
- `backend/app/knowledge_release.py`: `approval_from_options` (merge record or reviewed Git baseline, minimized approval block), canonical JSON, and hash helpers.
- `backend/app/release_gates.py`: `bm25_fingerprint`. Gates override `ask_api.get_corpus_documents`, so they never see the flag.
- `backend/app/corpus_security.py`: `scan_canonical(catalog, passages)` is the canonical one-shape rule.
- `backend/app/ask_api.py`: `load_corpus_documents` (default branch, release-root branch, `CorpusDocuments(load_error=True)`). It is the single seam used by `/ask` and `/ready` through `get_corpus_documents`. `pilot_ops` passes explicit paths.
- `backend/app/answer_cache.py`: `knowledge_identity` includes the admitted fingerprint, so a structured corpus gets distinct keys.
- `backend/app/answer_trace.py` and `backend/app/pilot_config.py`: precedent for exact-value profile gating. `MANIJERO_DEPLOYMENT_PROFILE` unset defaults to development in pilot config. This spec requires the explicit value.
- `backend/app/environment_profiles.py`, `backend/app/privacy_review.py`, and `backend/app/qa_deployment.py`: QA is identified by `MANIJERO_ENVIRONMENT=qa` (run with profile `pilot`), and local by `MANIJERO_ENVIRONMENT=local` with `development`. QA settings also set `MANIJERO_KNOWLEDGE_RELEASE_ROOT`.
- `backend/app/review_package.py` and `knowledge/knowledge-update-review-decisions.schema.json`: the named-human approval lives in the review package and covers only catalog and passages, which drives Open question 1.
- `docs/constraints/answers-and-knowledge.md` (Local embeddings, Hybrid retrieval, Knowledge updates): rules this feature must respect or extend.
- `knowledge/README.md` (intro, Files, Adding a document): "only reviewed passages ... are ever searchable" needs a qualifier.
- `PROGRESS.md` Current state and `ARCHITECTURE.md` line 25.

### Gaps and findings that shaped the contract

- No chunk-level review artifact exists. The only named-human approvals are the catalog entry's `reviewed_by` and the controlled merge, which is bound to catalog and passage hashes. The review gate therefore composes the chunker's catalog join with `approval_from_options` rather than inventing a review flow.
- `approval_from_options` needs a passages hash only for a merge record, which is why `--passages` is required with `--merge-record` and is never indexed.
- Chunk text keeps the `[título · ruta]` prefix so BM25 and vectors see the context. Extractive drafting may quote it, and that is recorded as a limit.
- No real reviewed chunk set is committed, so the reviewed-case comparison required by the "retrieval changes MUST be compared" rule cannot run. The flag stays limited to local development and QA, with no claim.
- The selector was not run in this planning session: the feature id came from the parent. Its spec, validation, and dependency fields in `feature_list.json` already exist and are unchanged.

## Resolved questions (orchestrator readings, 2026-11-07; recorded in the contract Notes)

1. Review gate: document-level approval through the named-human catalog rule. There is no per-chunk review.
2. Flag scope: the flag is honoured only for `MANIJERO_ENVIRONMENT=local` + `MANIJERO_DEPLOYMENT_PROFILE=development`, or for `MANIJERO_ENVIRONMENT=qa`. Unset, `prod`, and any other value are ignored, failing closed. QA settings files and deployment scripts are not changed.
3. The whole build fails closed on any non-reviewed, non-`chunked`, or malformed document.
- Planner consequence of 2: QA settings set `MANIJERO_KNOWLEDGE_RELEASE_ROOT`. When the flag is effective, the structured index therefore takes precedence over the release root for `/ask` and `/ready`, and staleness is checked against the release's verified catalog. The earlier `structured_index_release_conflict` refusal is dropped. Release build, publish, and rollback are untouched.

## Implementation plan

1. Read the chunker module, `knowledge_release.approval_from_options`, `release_gates.bm25_fingerprint`, `vector_store.write_store`, and `ask_api.load_corpus_documents`. Confirm `validate_catalog` accepts the fixture catalog at `2099-06-01`; if not, pick the nearest valid fixed date and update the verify block.
2. Write `knowledge/structured-chunk-index.schema.json` and the version constants, plus a `--check-contract`-style unit test for schema/constant agreement.
3. Implement the strict chunk-manifest and chunk-set reader, with byte hashes checked against the manifest's `chunk_set_sha256`.
4. Implement the review gate: catalog validation at `--as-of`, the join, the catalog-block equality check, approval evidence, and the fixed refusal codes.
5. Implement the passage mapping (id, source_id, verbatim text, location plus page suffix, no optional keys), then `validate_passage_set`, `Retriever.from_documents`, and `scan_canonical`.
6. Implement the atomic staging writer (refuse `knowledge/`, overlap with the chunks root, or a non-index directory), canonical files, the BM25 fingerprint, the manifest written last, and the unchanged-rebuild detection.
7. Add the optional vector step: lazy `embedding_index` build into staging, then `vector_store.write_store`, with digests in the manifest. Inject the embedder and store writer for tests.
8. Implement `verify_index` and `index_status` (file hashes, manifest shape, canonical-catalog comparison) and the CLI `check`.
9. Implement the loader and the `ask_api.load_corpus_documents` hook, placed before the release-root branch: setting parse, the exact environment gate (`local`+`development` or `qa`), the stale check against the catalog that would otherwise be served, log once per state change, and `load_error` on a broken index.
10. Write the CLI (`build`/`check`, exit codes, final `Result:` line) and generate the `fixtures/structured_chunk_index/chunks/` fixture from the matched candidate with the chunker.
11. Write the tests (below), run the focused block and then the full backend suite, and update the durable docs listed in the contract.

## Tests to write (`backend/tests/test_structured_chunk_index.py`)

- builds the reviewed fixture into all four files, with the passage mapping, page suffix, and manifest fields asserted;
- two roots are byte-identical, and a same-root rebuild rewrites nothing (mtimes unchanged);
- the derived passages carry no `critical`/`applicability`/`official_deadline`, and the catalog validity reaches `RetrievedPassage` through the `Retriever`;
- refusals, one test each, with the existing index left byte-identical: unknown validity, non-`chunked` entry, tampered chunk set, manifest hash mismatch, duplicate id, catalog-block mismatch, stale `catalog_sha256`, invalid catalog, no approval, both approvals, merge-record mismatch, a security finding (an injected identifier shape), and zero chunks;
- unsafe output under `knowledge/`, inside the chunks root, or a foreign non-empty directory, plus the bounds: exit `2` and nothing written;
- the vector step with a fake embedder and an in-memory store writer records digests, and an embedding failure exits `2` with nothing written;
- loader with the flag unset or `off`, in every environment: returns `None`;
- loader local-on (`local` + `development`): returns the verified documents;
- loader qa-on (`qa`, profile `pilot`, release root set): returns the verified documents, does not read the release root, and checks staleness against the release catalog;
- loader ignored cases, each returning `None` plus `structured_index_environment_refused`: environment `prod`, unset, `pilot`, `QA` (wrong case), ` qa` (padded), or `local` with profile `pilot` or unset;
- loader setting errors: an invalid value, and no dir;
- loader with a tampered file or catalog drift: returns `load_error`;
- `/ask` and `/ready` through `TestClient`: flag off gives today's answer; local-on and qa-on each cite a structured passage id; prod, pilot, and unset environments with the flag on give today's answer;
- release gates and `pilot_ops` ignore the flag;
- the last stdout line is one `Result:` line in every exit path, with no chunk text or reviewer name in output or logs.

## Verification plan

- The focused block in the contract (targeted pytest, CLI two-root diff, `check`, CLI fail-closed on the mixed root).
- The full `./scripts/init.sh --backend-tests` once, recorded as one line.
- `test_structured_chunk_index_chroma.py` in `backend/.venv-hybrid` if present; otherwise record "skipped: no chromadb" honestly.
- `git status --short knowledge` shows only the new schema file.

## Evidence to capture

- Commands and one-line results only: the focused block, the full suite, the optional Chroma test, and the `git status` of `knowledge/`.
- The manifest `inputs` and `files` hashes from the two-root build (hashes, not content).
- A one-line confirmation that the implementation follows the three orchestrator readings.

## Feature evidence

- `./scripts/init.sh --feature structured_chunk_index`: passed (targeted pytest incl. `test_embeddings.py`, two-root `diff -r` empty, `check` exit 0, mixed root refused with `unreviewed_chunk_set` and no output dir).
- `./scripts/init.sh --backend-tests -q`: 2591 passed, 8 skipped before one fix; `CI=true ./scripts/init.sh --fast`: all 10 checks passed (backend-tests 2592 passed, 8 skipped).
- `tests/test_structured_chunk_index.py`: 76 passed. `tests/test_structured_chunk_index_chroma.py`: skipped, no `chromadb` (no `backend/.venv-hybrid` in this worktree); not run.
- `--verify` not run: no Android/Desktop, Gradle, or packaging change.
- Two-root build hashes: `catalog_sha256` 4148ea21...f18d2d, `chunk_manifest_sha256` f12ab46c...4299cd, `chunk_set_sha256` d7447c9b...e33a0, `structured-passages.json` 594493ed...51c0f79.
- `git status --short knowledge`: `knowledge/README.md` (doc qualifier + Files row) and the new schema file only; no data file changed.
- Test edit: `tests/test_legal_structure_chunker.py` import-guard now exempts `structured_chunk_index.py` (it reuses the chunker constants as the spec requires).
- Orchestrator readings followed: document-level approval gate, exact `local`+`development` or `qa` gate, whole-build fail-closed. Flag-on precedence: structured index ahead of the release root.

## Validator checklist

- The default path is unchanged: with the flag unset, the existing `/ask`, `/ready`, release, and hybrid tests pass unmodified, and the wire contract and `contract-examples` are unchanged.
- The flag takes effect only for `MANIJERO_ENVIRONMENT=local` + `development`, or for exactly `MANIJERO_ENVIRONMENT=qa`. Prod, pilot, unset, any other environment, and an invalid value all keep today's corpus and log a fixed code only. No QA settings, deployment, or `init.sh` file changed.
- Only reviewed chunk sets are indexed. Any unknown-validity, non-`chunked`, malformed, mismatched, or unapproved input refuses the whole build and leaves earlier output byte-identical.
- Validity comes only from the catalog: no passage-level optional keys, and no values from chunk text.
- Determinism: the two-root diff is empty, there is no timestamp or absolute path, and an unchanged rebuild rewrites nothing.
- Vectors use only the existing pin and Chroma store writer. The service import pulls no heavy module, and no network is used in tests.
- Output lives outside `knowledge/`. `knowledge/` gains only the schema file. No reviewer name, chunk text, or question text appears in reports or logs.
- The durable docs listed in the contract are updated within budget, and no owner-guide step is added.
- The evidence confirms the orchestrator readings, and no quality claim is made.
