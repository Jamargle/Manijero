# Validation: structured_chunk_index

Verdict: accept (validator-final; no owner walkthrough by owner decision). Date: 2026-11-07.
Spec: [structured_chunk_index.md](../specs/structured_chunk_index.md). Evidence: [appendix](../specs/structured_chunk_index.appendix.md) "Feature evidence".

## Checks rerun by the validator

- `./scripts/init.sh --feature structured_chunk_index`: passed (targeted pytest, two-root `diff -r` empty, `check` up_to_date, mixed root refused with `unreviewed_chunk_set` and no output dir).
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed (backend-tests 2592 passed, 8 skipped).
- `--verify` not rerun: diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging.
- Diff review: `ask_api.load_corpus_documents` only consults the loader on the default no-path branch; loader gate is exact (`qa`, or `local`+`development`), invalid or refused values log a fixed code and return `None`; broken or stale index returns `load_error=True`; heavy modules are imported lazily; `knowledge/` gains only the schema; no reviewer name or chunk text in reports.
- Chunker import-guard test exemption is justified (reader reuses constants only).

## Real-Chroma test skipped

`tests/test_structured_chunk_index_chroma.py` skips without `chromadb` (no `backend/.venv-hybrid` in this worktree). Accepted: it follows the `test_vector_store_chroma.py` `importorskip` convention, the spec requires the run only "when the hybrid venv exists", and the offline suite covers the vector path with the fake embedder and in-memory store writer. Not independently run: the real Chroma build and hybrid pairing.

## Limits that remain

- Honoured only in local development and QA; document-level review only (chunk text not separately reviewed); no quality comparison; extractive answers may quote the `[título · ruta]` prefix (recorded in known-limitations).
- Real-Chroma build of the structured index unverified until someone runs the test in the hybrid venv.
