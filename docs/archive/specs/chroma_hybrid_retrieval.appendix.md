# `chroma_hybrid_retrieval` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

Inspected before implementation:

- `backend/app/retrieval.py` is the only retrieval boundary. `Retriever.from_documents` owns catalog/passage/campaign eligibility; `search` builds `RetrievedPassage` citation records; `Retriever.indexed_documents()` (from `local_bge_m3_embeddings`) exposes the admitted `(passage_id, text)` pairs.
- `/ask` (`app/ask_api.py`) prepares a `Retriever` per request via `_prepare_runtime_corpus`, then `answer_with_clarification` / `abstention` / `generation` call `corpus.search` and check `isinstance(corpus, Retriever)`. So a hybrid ranker must keep the `Retriever` type, not replace it. No consumer reads `RetrievedPassage.score`; generation verifies markers against dense ranks.
- `app/embedding_index.py` already produces a validated, pinned, digest-bound `passage-embedding-index-v1`. The Chroma store is built from that file instead of re-embedding, so building the store needs `chromadb` but not `torch`.
- `test_embeddings.py` asserts that `import app.main` imports neither embedding module. Hybrid selection is therefore isolated in a light `app/retrieval_backend.py`, with every heavy import lazy.
- `app/answer_eval.py` plus `backend/scripts/evaluate_pac_answers.py` run the 14 reviewed cases in `knowledge/pac_answer_eval.json` through `/ask` via `TestClient` dependency overrides. The comparison reuses `evaluate()` unchanged, once per mode.
- Host: the worktree's original `backend/.venv` was Python 3.9.6. The accepted backend code uses `X | None` annotations evaluated at import, so 6 test modules failed to collect on it before any change here. The only Python 3.10+ interpreter available was `~/.local/bin/python3.12` (3.12.16). No JDK is installed.

## Implementation plan

1. Inspect the current owning modules, schemas, and focused command before changing code.
2. Implement the capability behind a narrow interface with explicit configuration and fail-closed behavior.
3. Add representative and adversarial fixtures, including malformed, stale, duplicate, unavailable, and ambiguous cases as applicable.
4. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Implementation notes

- `backend/app/retrieval.py`: new `CandidateRanker` protocol, `Retriever.with_ranker(ranker)`, and `Retriever.uses_ranker`. `search` computes the positive-score BM25 ranking first. If that is empty it returns `()` (lexical gate) and the ranker never runs. Otherwise it hands the ranking to the ranker and builds `RetrievedPassage` values only for admitted ids, dropping unknown ids, duplicates, and non-finite or bool scores. Ranks stay dense. Without a ranker the behavior is byte-for-byte the accepted BM25 path (the full pre-existing suite passes unchanged).
- `backend/app/vector_store.py`: the `chroma-passage-store-v1` store. It holds a closed manifest (model pin, corpus inputs, `documents_sha256` over the exact admitted `(passage_id, text)` pairs, sorted ids, source index SHA-256, and `vectors_sha256` over the `float32` vectors read back from Chroma) plus one Chroma collection (`manijero-reviewed-passages`, cosine, ids and vectors only; no documents and no metadata text).
  - `write_store` builds into a sibling staging directory, reads back and verifies, writes the manifest last, then swaps it into place. It refuses `knowledge/` and refuses to replace a directory that is not already a store.
  - `ChromaPassageStore.open` re-verifies the pin, ids, and vector digest. `query` re-sorts by `(-similarity, id)`.
  - Telemetry is always off (`anonymized_telemetry=False`), no embedding function is set, and `chromadb` is imported lazily.
  - `store_status` / `manifest_status` need no runtime.
- `backend/app/hybrid_retrieval.py`:
  - The closed `hybrid-retrieval-v1` config and `reciprocal_rank_fusion`.
  - `HybridRanker`: embeds the question, queries the store, fuses, and on any exception returns the lexical ranking with `hybrid_retrieval_fallback`.
  - `HybridBackend`: lazy one-time load, per-request freshness against the current retriever, and a `retrieval_mode` log on state change.
  - `failure_code`: logs fixed project codes or exception type names only, never third-party messages.
- `backend/app/retrieval_backend.py`: `Bm25Backend` (default), `backend_from_environment`, and the `get_retrieval_backend` FastAPI dependency.
- `backend/app/ask_api.py`: one new dependency, `retrieval_backend`. After the corpus is prepared and is a `Retriever`, it calls `retrieval_backend.attach(...)`. Wire models, status codes, and the OpenAPI document are unchanged (`contract-examples` passes).
- `backend/config/hybrid_retrieval.json`: RRF with `rrf_k: 60`, `candidate_depth: 20`, `vector_min_similarity: 0.0`. These are the published default and the accepted cosine rule, chosen before measurement and not tuned on the cases.
- `backend/requirements-hybrid.txt`: `-r requirements.txt`, `-r requirements-embeddings.txt`, `chromadb==1.5.9`.
- `backend/scripts/manage_vector_store.py`: `build` (refuses a non-`up_to_date` embedding index), `check` (`--deep` opens the collection), and `compare` (report only; exits `1` if hybrid fell back on any case).
- Tests:
  - `backend/tests/test_hybrid_retrieval.py`: 68 tests, default environment, using a deterministic keyword embedder and an in-memory searcher.
  - `backend/tests/test_vector_store_chroma.py`: 11 real-Chroma tests, skipped without `chromadb`.
- Docs: `backend/README.md` (hybrid section, plus the embeddings section's "off the answer path" wording), `ARCHITECTURE.md`, `CONSTRAINTS.md` (the embeddings rule now names the opt-in; new "Hybrid retrieval" rules), `docs/risks-and-open-questions.md`, and `PROGRESS.md` (product shape and the embeddings limit).

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

### Environment

Host: macOS, Apple M1 Max, CPU only. Worktree `chroma_hybrid_retrieval`, measured 2026-10-31.

- `backend/.venv` (ignored) was Python 3.9.6, and the accepted suite could not collect on it (`TypeError: unsupported operand type(s) for |` in 6 modules, before any change here). It was moved aside to `backend/.venv-py39-broken` and recreated with `~/.local/bin/python3.12 -m venv backend/.venv` plus `pip install -r backend/requirements-dev.txt` (fastapi 0.162.0, pytest 8.4.2). Size: `du -sh backend/.venv/lib` = 57M.
- `backend/.venv-hybrid` (ignored by `.venv-*/`), Python 3.12.16: `pip install -r backend/requirements-hybrid.txt -r backend/requirements-dev.txt` resolved `chromadb==1.5.9`, `torch==2.14.1`, `transformers==5.21.0`, `tokenizers==0.23.3`, `huggingface_hub==2.3.0`, `safetensors==0.8.0`, and `numpy==2.5.4`. Those are exactly the embedding pins, with no conflict, across 100 packages. `du -sh backend/.venv-hybrid/lib` = 1.2G.
- The pinned bge-m3 revision was downloaded with `curl -fsSL` from `https://huggingface.co/BAAI/bge-m3/resolve/5617a9f61b028005a4858fdac845db406aefb181/<file>` into `backend/.venv-hybrid/artifacts/bge-m3` (ignored, 2.1G). `manage_embeddings.py verify` reported 9 files, 2,293,315,747 verified bytes, `issues: []`, and `config_sha256 b1bc262b…`.
- Derived artifacts for this evidence (`embedding-index.json`, `vector-store/`, and the comparison JSON) live under `backend/.venv-hybrid/artifacts/`. They are not committed, and none is under `knowledge/`.

### Real build, check, and freshness

- `manage_embeddings.py build … --as-of 2026-10-31 --active-campaign 2026`: 4 passages from 4 eligible sources, dimension 1024, `embed_seconds 0.46`, `peak_rss_mb 1984.4`, `index_sha256 18b776b0e2be7ff800af04e270e5693fb622aeb4f33e0649b85ad3e53f2ca892`. A second build to another path gave the same `index_sha256`.
- `manage_vector_store.py build …`: `chroma-passage-store-v1`, `chromadb_version 1.5.9`, 4 passages, `documents_sha256 f3ea22b5…a3a5`, `vectors_sha256 2a8ef39f…2b6c`, `store_bytes 630124`, `write_seconds 1.268` (first) and `0.217` (in-place rebuild), `peak_rss_mb 97.4`.
  - A second store built from the second index gave the identical `vectors_sha256`.
  - The in-place rebuild left no staging or previous directory.
- `check` (default venv, no chromadb): `up_to_date`, exit 0. `check --deep` (hybrid venv): `collection: verified`, exit 0.
- `check` with a copy of `knowledge/passages.json` whose first passage had one trailing space added, written to `/tmp`: `stale`, `reasons: ["documents_changed"]`, exit 1. `check --as-of 2026-11-02` with unchanged passages: `up_to_date`, because freshness depends on the admitted documents, not on the date.
- `git status --short knowledge` is empty: canonical knowledge is unchanged.

### BM25 vs hybrid comparison (reviewed cases)

Command (exit 0, `hybrid_fallbacks: 0`):

```sh
backend/.venv-hybrid/bin/python backend/scripts/manage_vector_store.py compare \
  --config backend/config/bge_m3_embedding.json --hybrid-config backend/config/hybrid_retrieval.json \
  --artifact backend/.venv-hybrid/artifacts/bge-m3 --store backend/.venv-hybrid/artifacts/vector-store \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json --as-of 2026-10-31 --active-campaign 2026 --json
```

Answer metrics through `/ask`, 14 author-only cases, `k=5`, fusion `config_sha256 95be2f64…7847`:

| Metric | BM25 | Hybrid |
|---|---|---|
| expected_state_agreement | 13/14 | 13/14 |
| expected_answer_coverage | 11/11 | 11/11 |
| source_citation_agreement | 8/11 | 8/11 |
| passage_citation_agreement | 8/11 | 8/11 |
| critical_fact_matches | 9/11 | 9/11 |
| expected_abstentions | 2/3 | 2/3 |
| unexpected_answers | 1 | 1 |

The BM25 column reproduces the accepted baseline in `PROGRESS.md` exactly.

Changed answers (`changed_cases`):

- `canal-sga-2026`: BM25 cites `pasaje-plazo-presentacion-2026-andalucia`; hybrid cites `pasaje-canal-presentacion-excepcion-nacional`. Both miss the expected `pasaje-canal-presentacion-andalucia`, and the critical literal matches in both.
- `canal-sga-entidades-2026`: hybrid cites one extra passage (`pasaje-canal-presentacion-excepcion-nacional`) besides the expected one. `passage_match` stays true.

Retrieval-level metrics (candidate lists at `k=5`, 11 cases with an expected passage):

| Metric | BM25 | Hybrid |
|---|---|---|
| expected passage at rank 1 | 8 | 8 |
| expected passage in top 5 | 10 | 11 |
| mean reciprocal rank | 0.8182 | 0.8409 |
| non-answer cases with candidates | 2 | 2 |

The only recall change is `canal-sga-2026`: the expected passage is now at rank 4, where BM25 had no candidate for it. Hybrid candidate lists contain all four passages whenever BM25 has any match, because every passage has a positive cosine.

Timing and memory, same run:

- `load_seconds 2.711`, which includes artifact verification, model load, and store open.
- Per-question search: BM25 median 0.02 ms, p95 0.03 ms. Hybrid median 33.89 ms, p95 52.97 ms, max 87.94 ms.
- `peak_rss_mb 1967.5`. `/usr/bin/time -l`: maximum resident set size 2,072,969,216 bytes, 4.50 s wall clock.

A second identical `compare` run produced output identical to the first apart from the timing and RSS fields (`identical_except_timing True`; load 2.697 s, hybrid median 33.82 ms).

**Conclusion recorded honestly:** no answer-level improvement was measured, and one top-5 retrieval gain does not support changing the default. BM25 stays the default.

### Runtime smoke through the environment (real model and store)

Through the real `app.main` app with `TestClient`, `MANIJERO_ACTIVE_CAMPAIGN=2026`, and `as_of` overridden to 2026-10-31:

- `MANIJERO_RETRIEVAL_MODE=hybrid` with the fresh store: 200 `answered`. The first request took 2.817 s (lazy load) and the second 0.071 s. Log: `{"active":"hybrid","configured":"hybrid","event":"retrieval_mode","reasons":"","store_state":"up_to_date",…}`.
- Mode unset: 200 `answered`, no `retrieval_mode` record.
- Hybrid with a missing store path: 200 `answered` on BM25. Log: `active: bm25`, `store_state: invalid`, `reasons: manifest_unreadable`. Since then, `open` reports `store_missing` for an absent manifest, as covered by tests.
- Hybrid configured in the default venv without chromadb: 200 `answered` on BM25. Log reasons: `vector_runtime_unavailable`.
- In every run, `question_in_log False`: no question token appears in the operational log.
- Out-of-scope probes gave the same results in both modes: "¿Cuántos olivos puedo plantar por hectárea?" → `abstained`, 0 sources; "¿Qué tiempo hará mañana en Jaén?" → `answered`, 1 source.

### Verification gates actually run

- `backend/.venv/bin/python -m pytest -q backend/tests`: `1036 passed, 1 skipped` (the skip is the Chroma module without chromadb).
- `backend/.venv-hybrid/bin/python -m pytest -q -p no:cacheprovider backend/tests`: `1047 passed`, including the 11 real-Chroma tests.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature chroma_hybrid_retrieval`: `1036 passed, 1 skipped, 1 warning in 5.89s` (the warning is the pre-existing Starlette `httpx` deprecation notice).
- `CI=true ./scripts/init.sh --fast`: **exit 1**. 8 of 9 checks passed: `contract-examples` (3 request and 3 response examples), `backend-tests`, `source-catalog`, `retrieval`, `generation`, `abstention`, `clarification`, `land-safety`. `gradle-jvm-test` (`./gradlew :shared:jvmTest`) failed with "The operation couldn’t be completed. Unable to locate a Java Runtime." This host has no JDK: `/usr/libexec/java_home -V` finds none, and there is no Android Studio JBR. This change touches no Kotlin, Gradle, or shared code, but the Gradle check has **not** passed in this environment.
- `./scripts/init.sh --verify` was not run, for the same missing-JDK reason. The change has no Android, Desktop, shared, or packaging surface.
- Orchestrator rerun: no system JDK exists, but Gradle had already provisioned Azul Zulu 21.0.11 under `~/.gradle/jdks/`. With `JAVA_HOME` and `PATH` pointing at that JDK for this one command, `CI=true MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` gave **All 9 offline checks passed. Fast tier passed.**, including `gradle-jvm-test`. No system configuration was changed. `feature_list.json` moved to `passing` on that result.
- `./scripts/init.sh --verify` was not run. The change has no Android, Desktop, shared, or packaging surface.

### Failure behavior covered by focused tests

`test_hybrid_retrieval.py` (default environment) covers:

- RRF formula, tie-break, depth truncation and repeats, and determinism.
- The identity ranker equals BM25; `with_ranker` is non-mutating; reorder and add with dense ranks.
- Unknown, duplicate, NaN, or bool ids and scores are dropped; an empty ranking yields no candidates.
- Lexical gate: the ranker is never called for an out-of-vocabulary, blank, or `k=0` question, and excluded-campaign passages cannot be reintroduced.
- `HybridRanker` fusion equals RRF over both lists; the similarity floor applies; embedder and store failures fall back to the identical BM25 result with a logged fixed code; a third-party error message containing a name and DNI is not logged.
- Closed hybrid config (11 cases); manifest content without passage text; the documents and vectors digests.
- Closed manifest contract (10 cases); `missing` / `invalid` / `up_to_date` / `stale` with campaign, documents, expiry, and pin reasons.
- Write refusal under `knowledge/` and over a non-store directory, which is left intact.
- Environment selection (default, invalid, incomplete); lazy load; one load with the failure remembered; `attach` never raises.
- `import app.main` imports no `chromadb`, `torch`, vector, hybrid, or embedding module.
- `/ask` contract with hybrid: a failing hybrid answers identically to BM25 for answered, out-of-scope, off-campaign-year, and land-clarification requests; zero-evidence abstention holds without the embedder being called.
- CLI `check` exit codes 0, 1, and 2.

`test_vector_store_chroma.py` (real chromadb 1.5.9) covers:

- Round trip and cosine query; ties by id.
- No passage text in any store file or SQLite string column.
- Atomic rebuild; a failed build leaves the previous store; refusals for a tampered manifest digest, mismatched ids, another pin, and a missing collection.
- Query dimension and NaN refusal; end-to-end hybrid ranking over a real Chroma store.

### Privacy

The store and manifest hold passage ids, digests, and floats only. Logs carry fixed reason codes or exception type names only. The question is embedded only by the local model and sent nowhere. Chroma telemetry is disabled in code. No secret was read or used; the model download is an unauthenticated public artifact.

### Honest limits

- One host, four approved passages, and 14 author-only cases. Not an owned-server capacity measurement, not independent legal review, and not evidence of general retrieval or answer quality.
- With four passages, hybrid candidate lists include every passage whenever BM25 matches anything, so the comparison cannot show how fusion behaves on a realistic corpus. The fusion parameters were not tuned.
- The lexical gate keeps BM25's false positives: "¿Qué tiempo hará mañana en Jaén?" answers in both modes because BM25 matches the tokens. Hybrid neither fixes nor worsens this pre-existing behavior.
- Chroma's HNSW search is approximate. At four items it returned every item, and results are re-sorted deterministically, but exact recall on large corpora is not claimed. The store format is tied to `chromadb==1.5.9`.
- The first hybrid request after start pays about 2.7–2.8 s for verification and load. A load failure is remembered until restart. `/ready` does not report the hybrid state.
- Chroma's `PersistentClient` needs a writable store directory, so the store is not read-only at runtime.
- Determinism was observed on one host only. No cross-platform bit-identity is claimed.
- `--verify` has not run for this change. `gradle-jvm-test` passed only with the Gradle-provisioned JDK (`~/.gradle/jdks`), not a system JDK.

### Validation

- 2026-10-31: independent validator verdict **accept**; it reran `--feature`, `--fast` (with the Gradle-provisioned JDK), the hybrid-venv suite (1047 passed), and the real `compare` run, and reproduced the figures above. See [acceptance record](../../validations/chroma_hybrid_retrieval.md).
