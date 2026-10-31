# `knowledge_reindex_release` planning appendix

Re-planned 2026-10-31 against the accepted dependencies. The previous generic placeholder is superseded.

## Repository research

Inspected (read, not assumed):

- `AGENTS.md`, `PROGRESS.md` "Current state", `ARCHITECTURE.md`, `CONSTRAINTS.md` (lines ~500–560), `docs/risks-and-open-questions.md`, `knowledge/README.md` (review workflow steps 1–5), `backend/README.md` (pilot deployment/rollback, embeddings, hybrid, PAC evaluation, review packages).
- `scripts/init.sh`: `--feature <id>` extracts lines between `<!-- verify:start -->`/`<!-- verify:end -->`, drops fence and blank lines, writes them to one temp script, and runs it with `bash -euo pipefail` from the repository root with `AS_OF` (default `2026-10-13`) and `REPO_ROOT` exported. Variables therefore persist across lines; any failing line fails the tier. `--backend-tests [targets]` runs pytest from `backend/` and makes a relative `MANIJERO_PYTHON` absolute. The script checks for Java and `gradlew` before any mode except `--setup-python`/`--backend`. `scripts/python-env.sh`: `hybrid` = runtime + embeddings + hybrid + dev requirements, linked as `backend/.venv-hybrid` (so pytest exists there).
- Accepted backend verify blocks: `backend_answer_evaluation` (targeted tests + an evaluator CLI run), `local_generation_provider` (targeted tests then the full suite with `${MANIJERO_PYTHON:-backend/.venv/bin/python}`), `knowledge_update_scheduler` (targeted tests). This spec follows the same shape.
- `backend/app/ask_api.py`: `CATALOG_PATH`/`PASSAGES_PATH` are fixed to the checkout's `knowledge/`; `load_corpus_documents(catalog_path=None, passages_path=None)` is the single read seam (also used by `pilot_ops._load_documents` for preflight) and maps read errors to `load_error=True` → generic `503`. Files are re-read on every request, so today a non-atomic two-file replace can serve a mixed pair (documented limit in README "restore").
- `backend/app/main.py`: `create_app(config, retention_store, ...)` builds the app; `app = create_app()` at import reads env. `/ready` and `/ask` share `get_corpus_documents`.
- `backend/app/readiness.py`: `evaluate_readiness(documents, as_of, campaign)` reuses `_prepare_runtime_corpus`; codes `campaign_unavailable`, `corpus_unavailable`, `corpus_not_current`, `no_eligible_sources`.
- `backend/app/retrieval.py`: `Bm25Index` is in-memory only (no persisted BM25 artifact exists); `BM25_K1 = 1.5`, `BM25_B = 0.75`; `tokenize` uses `unicodedata.normalize("NFKD")` (so the Unicode-data version is a real input); `Retriever.from_documents` validates catalog and passages and orders by passage id; `Retriever.indexed_documents()` is the public admitted `(id, text)` list.
- `backend/app/retrieval_backend.py`: `Bm25Backend`, `get_retrieval_backend` (process-wide, env-built once), hybrid only with `MANIJERO_RETRIEVAL_MODE=hybrid` + `MANIJERO_VECTOR_STORE` + `MANIJERO_EMBEDDING_ARTIFACT`.
- `backend/app/hybrid_retrieval.py`: `HybridBackend` loads components once per process (lazy); per request `manifest_status` compares the loaded store manifest against the current retriever's documents → a store from an older release becomes `stale` and the request uses BM25 until restart.
- `backend/app/vector_store.py`: `write_store` (staging + swap, refuses `knowledge/`, needs `chromadb`), `store_status` (no runtime), manifest with `documents_sha256`/`vectors_sha256`; Chroma file bytes are not content-addressed.
- `backend/app/embedding_index.py`: `IndexInputs`, `index_status`, `read_index_document`, `build_index_document`, `file_sha256`, `write_index_atomic` (refuses `knowledge/`). `backend/scripts/manage_vector_store.py` and `manage_embeddings.py` are the existing operator entry points (exit `0/1/2` convention).
- `backend/app/answer_eval.py`: `load_case_document(path, catalog, passages)` and `evaluate(cases, client, catalog, passages, k, coverage=...)` (client needs only `.post`); rows carry `expected_state_match`, `source_match`, `passage_match`, `critical_facts_match`, `clarification_ids_match`; evaluate silently drops a source it cannot map. `backend/scripts/evaluate_pac_answers.py` overrides dependencies on the module-level `app`.
- `backend/app/review_package.py` `merge(...)`: writes catalog then passages atomically one by one and `merge.json` (`knowledge-update-merge-v1`: `package_id`, `reviewer`, `approved_on`, `catalog_sha256`, `passages_sha256`, `canonical_changes_applied`, `reindex_required: true`, `reindexed: false`, `released: false`, `statement`). It explicitly leaves reindex/release to this feature.
- `backend/app/pilot_ops.py`: preflight (`run_preflight`) reads the corpus via `load_corpus_documents`; backup/restore operate on the checkout's `knowledge/` pair; `run_smoke` uses `httpx`. `backend/app/pilot_config.py`: `load_config(env)`.
- Tests: `backend/tests/test_vector_store_chroma.py` uses `pytest.importorskip("chromadb")`; `test_hybrid_retrieval.py` has a subprocess import-hygiene check (~line 691); `test_pilot_operations.py` builds apps with `create_app(config)`.
- Not inspected in depth: every existing test body, `backend/deploy/systemd/*` units, `contracts/openapi.yaml` (unchanged by design).

## Design decisions

1. **Release = immutable directory + atomic pointer.** The service today re-reads two files per request; replacing them in place cannot be atomic. A content-addressed directory per release plus one `os.replace` of a relative `current` symlink is atomic on POSIX, keeps every prior release intact for rollback, and needs no new dependency. Windows is out of scope (the target host and dev Mac are POSIX).
2. **Opt-in service seam, default unchanged.** `MANIJERO_KNOWLEDGE_RELEASE_ROOT` unset keeps the checkout `knowledge/` path; set, the request resolves `current` once (`os.path.realpath`), requires the result inside `<root>/releases/`, verifies `gate.passed` and the catalog/passages SHA-256 from the manifest, and reads both files from that one directory. Cost is two small hashes per request (four passages today); recorded as an evidence item.
3. **BM25 "rebuild" is a fingerprint, not a served artifact.** BM25 stays in-memory and per request. `bm25-index.json` (canonical JSON: `k1`, `b`, ordered ids, per-doc text SHA-256, lengths, term frequencies, document frequencies, `repr` of the average length) is the reproducibility record; `prepare` builds it twice and `verify` rebuilds it from the release's own files and compares. The README must say plainly that the service does not load it.
4. **Gates never trust environment knobs.** The evaluation app is a fresh `create_app` with a development config and overrides for corpus, date, campaign, `k`, retrieval backend (`Bm25Backend()`), generation (`None` → extractive), and retention (`None`). This keeps the gate deterministic and offline even if the operator shell exports hybrid/local settings.
5. **Regression baseline = currently published release.** There is no numeric quality threshold in the repo (report-only metrics, 13/14 known). A no-regression rule per unchanged case is the strictest rule that does not invent a threshold. The first release records `baseline_release_id: null`. Changed/new/removed cases are reported only, because the case set itself goes through review (`knowledge_update_review_pr`).
6. **Approval binding without inventing authentication.** A matching `merge.json` is the normal path. The current corpus predates the merge tool, so `--reviewed-baseline-revision` lets the owner bind a release to a reviewed Git revision; the tool records it as an unverified assertion. Exactly one is required. The reviewer name is not copied into the manifest (data minimization; it stays in the package).
7. **Vectors are packaged, not computed.** Embedding requires torch and the 2.1 GiB pinned artifact; `prepare` only accepts an `up_to_date` index built by `manage_embeddings.py build` and, with `--with-vector-store` in `backend/.venv-hybrid`, loads it with the existing `write_store` into `<release>/vector-store`. Content digests (`documents_sha256`, `vectors_sha256`, index SHA-256) go into the manifest; Chroma's SQLite bytes are not claimed reproducible.
8. **No timestamp in the manifest.** Release identity is a pure function of inputs; publish/rollback times live only in `release-log.jsonl`.

### Manifest `knowledge-release-v1` (closed; unknown keys rejected)

```json
{
  "schema_version": "knowledge-release-v1",
  "release_id": "<16 lowercase hex>",
  "inputs": {"catalog_sha256": "…", "passages_sha256": "…", "cases_sha256": "…",
             "as_of": "YYYY-MM-DD", "active_campaign": "2026"},
  "approval": {"kind": "merge_record", "package_id": "…", "approved_on": "YYYY-MM-DD",
               "merge_record_sha256": "…"},
  "build": {"code_revision": "<40 hex>", "python_version": "3.12.x",
            "unicode_data_version": "15.x.x", "bm25": {"k1": 1.5, "b": 0.75}, "retrieval_k": 5},
  "files": {"source_catalog.json": {"sha256": "…", "bytes": 0}, "passages.json": {…},
            "pac_answer_eval.json": {…}, "bm25-index.json": {…}, "evaluation-report.json": {…}},
  "bm25": {"index_sha256": "…", "document_count": 4},
  "vector": null,
  "gate": {"passed": true, "failures": [], "baseline_release_id": null,
           "summary": {"cases": 14, "expected_state_agreement": 13, "unexpected_answers": 1}},
  "statement": "Built from canonical reviewed artifacts. Not a legal-coverage or answer-quality claim."
}
```

`approval` alternative: `{"kind": "reviewed_git_baseline", "revision": "<40 hex>"}`. `vector`, when present: `{"model": <spec.index_metadata()>, "embedding_index_sha256", "store_manifest_sha256", "documents_sha256", "vectors_sha256", "chromadb_version"}` and `files` gains `embedding-index.json`. `release_id` = first 16 hex of SHA-256 of the canonical JSON (`sort_keys`, `ensure_ascii=False`, `(",", ":")`) of the manifest without `release_id`. Summary numbers above are illustrative, not expected values.

Release log line (`release-log.jsonl`, append + fsync, `0644`): `{"event": "publish"|"rollback", "release_id", "previous_release_id", "at": "<UTC ISO seconds>"}`.

### Fixed codes (non-exhaustive; implementer may add, never with values)

`unsafe_release_root`, `approval_evidence_required`, `approval_evidence_ambiguous`, `approval_mismatch`, `merge_record_invalid`, `catalog_invalid`, `passages_invalid`, `passage_source_unresolved`, `corpus_not_ready:<readiness code>`, `cases_invalid`, `bm25_nondeterministic`, `grounding_invalid_response`, `grounding_empty_sources`, `grounding_unmapped_source`, `evaluation_failed`, `evaluation_regression:<case_id>`, `baseline_unreadable`, `embedding_index_stale:<reasons>`, `embedding_index_invalid`, `vector_runtime_unavailable`, `store_*` (from `vector_store`), `release_conflict`, `already_prepared`, `release_not_found`, `gate_failed`, `integrity_mismatch`, `manifest_invalid`, `release_locked`, `no_current_release`, `no_previous_release`, `already_current`, `current_outside_releases`, `log_out_of_sync`, `publish_failed`.

## Implementation plan

1. **Manifest and layout** (`backend/app/knowledge_release.py`): constants, `ReleaseError(code, exit_code)`, canonical JSON helper, `validate_manifest`, `content_id`, `read_manifest`, `verify_release(dir)` (every `files` hash/size; `vector` store manifest hash when present), path safety (`unsafe_release_root` for anything inside `knowledge/`; resolved `current` must be inside `releases/`). Add `knowledge/knowledge-release-manifest.schema.json` (Draft 2020-12) mirroring the validator.
2. **Writer:** staging dir `<root>/releases/.staging-<uuid>` → copy inputs byte-for-byte, write derived files, write manifest last, `os.rename` to `<id>`; identical existing → `already_prepared`; different → `release_conflict`; failure removes staging. Modes `0644`/`0755`.
3. **Gates** (`backend/app/release_gates.py`): structural → BM25 fingerprint (×2) → evaluation app + capturing client + grounding check → regression comparator (pure function over two reports, unit-testable) → optional vector packaging. Collect all failure codes (sorted, de-duplicated) rather than stopping at the first, except where a later gate cannot run (structural failure skips evaluation and records `evaluation_failed`).
4. **Approval binding:** parse `merge.json` strictly (schema version, `canonical_changes_applied: true`, 64-hex hashes, date) and compare hashes with the candidate bytes; or accept a 40-hex `--reviewed-baseline-revision`. `--code-revision` must be 40 hex.
5. **Publish/rollback/status/verify/compare:** lock with `O_CREAT|O_EXCL` on `<root>/.release.lock` (removed in `finally`); verify target, `gate.passed`, readiness via `evaluate_readiness` on the release's own files for `--as-of`/`--active-campaign` (not ready → exit `1`, unchanged); create `<root>/.current-<uuid>` symlink to `releases/<id>` and `os.replace` onto `current`; fsync the root; append the log line; if the append fails, `os.replace` back to the previous link and raise `publish_failed`. Rollback target = `--to` or the `previous_release_id` of the latest log event for the current id. `status` reports current id, gate, integrity, and `log_out_of_sync` when the log's last event disagrees with `current`. Publishing the current id returns `already_current` (exit `0`) and appends an event only if the log is out of sync. `compare` prints each differing dotted manifest path; vector fields are tagged `vector_digest_differs`.
6. **Service seam** (`backend/app/ask_api.py`): in `load_corpus_documents`, when both paths are `None` and `MANIJERO_KNOWLEDGE_RELEASE_ROOT` is non-empty, call `knowledge_release.load_published_corpus(Path(root))`; map `ReleaseError`/`OSError`/`ValueError` to `load_error=True`; emit a change-only `knowledge_release` operational record (`release_id`, `state` = `served`|`refused`, `reason`). Keep `knowledge_release` import stdlib-light (no FastAPI, no gates).
7. **CLI** (`backend/scripts/knowledge_release.py`): argparse sub-commands per the contract; same `sys.path` setup as other scripts; `prepare` prints `release_id:`, `gate:`, `failures:`, `baseline_release_id:`, `bm25_index_sha256:`, and file hashes; never corpus text.
8. **Tests** (see verification plan), then `deploy/pilot.env.example` commented line, then documentation (README section, knowledge/README step 5, ARCHITECTURE, CONSTRAINTS, risks), then the local rehearsal and evidence.

## Verification plan

### `backend/tests/test_knowledge_release.py` (default `backend/.venv`; offline; sockets blocked where the gate runs)

Use `tmp_path` copies of the canonical `knowledge/source_catalog.json`, `passages.json`, `pac_answer_eval.json`, `as_of = 2026-10-13`, campaign `2026`, and an injected clock. Confirm first that the canonical corpus is ready for that date and campaign (the fast tier validates the catalog at `2026-10-13`).

1. Happy path: exit `0`; expected files; manifest validates against the JSON Schema (jsonschema Draft 2020-12) and the Python validator; modes `0644`/`0755`; canonical inputs and a supplied `merge.json` byte-identical afterwards.
2. Determinism: two roots → byte-identical `release-manifest.json`, `bm25-index.json`, `evaluation-report.json`, equal ids; changing `as_of` changes the id and `compare` lists only `inputs.as_of` (plus anything it legitimately feeds).
3. Approval: none / both / mismatched hashes / wrong schema → exit `2`, no release directory; a valid fake merge record → manifest has `package_id`, `approved_on`, `merge_record_sha256`, and no reviewer name anywhere in the release.
4. Structural failures (expired source for `as_of`, passage with unknown `source_id`, campaign mismatch, case pointing at a missing passage): exit `1`, `gate.passed: false`, expected codes, `publish` refuses `gate_failed`.
5. Grounding checker unit tests: unmapped source, zero sources on `answered`, non-contract response.
6. Regression comparator unit tests: flip of each tracked boolean fails; changed case digest, new case, and removed case are reported but not gated; no baseline → `baseline_release_id: null`.
7. Publish: success switches `current` and appends one log line; tampered file → `integrity_mismatch`; not ready at a later `--as-of` → exit `1`; held lock → `release_locked`; `os.replace` monkeypatched to raise → `current` unchanged; log append failure → link reverted, `publish_failed`; `already_current`.
8. Rollback: default previous; `--to` unknown → `release_not_found`; nothing to roll back → `no_previous_release`; refuses a failed or tampered target.
9. Safety: root inside `knowledge/` → `unsafe_release_root`; `current` pointing outside `releases/` → refused by both CLI and service; existing different directory → `release_conflict`.
10. Service (TestClient, `monkeypatch.setenv`): release A → `/ready` 200, `/ask` 200 with the same body as the unset-variable path; publish B (a passed release built by a test helper from a fixture corpus with a distinguishable answer) → the next request is served from B without restart; tamper B → `/ready` and `/ask` 503 with generic bodies and one `knowledge_release` record containing no corpus value; rollback → 200. A monkeypatched swap between the two file reads still yields one consistent release. Unset variable → unchanged behavior (existing `test_ask_endpoint.py`).
11. Gate isolation: with `MANIJERO_RETRIEVAL_MODE=hybrid` and `MANIJERO_GENERATION_PROVIDER=local` exported and `socket.socket.connect` patched to raise, `prepare` succeeds with identical output to a clean environment.
12. Import hygiene (subprocess, like `test_hybrid_retrieval.py`): importing `app.main` does not import `app.release_gates`, `app.answer_eval`, `chromadb`, or `torch`.
13. Vector options in the default venv: stale `--embedding-index` → `embedding_index_stale:…` exit `2`; `--with-vector-store` without `chromadb` → `vector_runtime_unavailable` exit `2`; no release directory either way.
14. Privacy: captured stdout/stderr and log lines contain no passage text, question, or land value.

### `backend/tests/test_knowledge_release_chroma.py` (`pytest.importorskip("chromadb")`; fake 1024-d vectors; no model)

- `prepare --with-vector-store` from a fake `up_to_date` index → release has `vector-store/`; manifest digests equal the store manifest; `verify` passes.
- Two builds from the same fake index → equal `documents_sha256`, `vectors_sha256`, `embedding_index_sha256`, and release id (Chroma file bytes not compared).
- A `HybridBackend` with a fake embedder opened on `<root>/current/vector-store` is `up_to_date` for that release and `stale` (BM25) after publishing a release with different admitted documents, until a new backend is built.

### Commands

- Focused block (contract): targeted tests, CLI double prepare + `compare` + `publish` + `verify` in temp roots, then the full backend suite.
- Hybrid (needs `./scripts/init.sh --setup-python hybrid`): `MANIJERO_PYTHON=backend/.venv-hybrid/bin/python ./scripts/init.sh --backend-tests tests/test_knowledge_release_chroma.py tests/test_vector_store_chroma.py tests/test_hybrid_retrieval.py`.
- Optional real-vector reproducibility (only if the pinned bge-m3 artifact already exists locally; never download): build the embedding index twice with `manage_embeddings.py build` into two paths, `prepare --embedding-index … --with-vector-store` into two roots, `compare` → record whether vector digests match on this host. Not a cross-host claim.
- Regression guard: `./scripts/init.sh --fast` once before handoff.

### Local rehearsal (manual, recorded in Feature evidence; no host, no network)

```sh
ROOT="$(mktemp -d)"; REV="$(git rev-parse HEAD)"
# prepare A (as_of 2026-10-13) and B (as_of 2026-10-31), publish A
MANIJERO_ACTIVE_CAMPAIGN=2026 MANIJERO_KNOWLEDGE_RELEASE_ROOT="$ROOT" \
  backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765 &
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/ready      # 200
# POST /ask with a reviewed-topic question → 200 answered
# publish B → status shows B; /ready 200 without restart
# tamper one byte of $ROOT/current/passages.json → /ready 503, /ask 503
# rollback → current = A; /ready 200; /ask 200; inspect release-log.jsonl and the server log
kill %1; rm -rf "$ROOT"
```

Also run one failed-gate candidate (e.g., cases file referencing a removed passage) and show `publish` refusing it while `/ready` stays 200 on the current release.

## Evidence to capture

- Focused block output and full backend suite counts; hybrid test output (or the reason it was not run).
- Two release ids and `compare` output for the double build; byte sizes of each release file; `prepare` wall time.
- Per-request overhead of the release read path (median of N local `/ready` calls with and without the variable), stated as one-host, four-passage observation.
- Rehearsal transcript: status codes per step, `release-log.jsonl` lines, the `knowledge_release` log records (showing no corpus text).
- If run: real-vector double-build digests and whether they matched on this host; Python, torch, chromadb versions.
- Honest limits: no host/systemd/tunnel step executed; Git revision and reviewed-baseline assertions unverified by the tool; release root on a single disk without off-host copy; no garbage collection; hybrid needs restart after publish to use the new store; evaluation is the 14-case author-only sample.

## Open human decisions (not blocking implementation)

- Where the release root lives on a future host and how it is backed up off-host (procedure only until a host exists).
- Whether to retire `pilot_ops.py backup/restore` for the corpus once a release root is configured; this feature only documents that rollback replaces restore in that mode.

## Feature evidence

<!-- Implementer appends dated evidence here. Validator appends the acceptance note. -->

### 2026-10-31 — implementer self-verification (development Mac, offline, `backend/.venv`)

Environment: Python 3.12.16, `unicodedata.unidata_version` 15.0.0, shared `backend/.venv` (dev profile). `chromadb`, `torch`, `backend/.venv-hybrid`, and a bge-m3 artifact are **not** present. No virtualenv was created. No network, model, or paid call was made.

**Commands and results**

- `./scripts/init.sh --feature knowledge_reindex_release` → exit `0`. The targeted tests (`test_knowledge_release.py`, `test_ask_endpoint.py`, `test_pilot_operations.py`, `test_hybrid_retrieval.py`, `test_pac_answer_eval.py`, `test_knowledge_update_review.py`) → **232 passed**. The two CLI prepares gave the same id, `aa97b66716f31e37` (at `HEAD` ab3ef86). `compare` → `identical: yes`. `publish` → `result: switched`. `verify` → `integrity: ok`, `bm25: match`, `gate: passed`. Full backend suite → **1346 passed, 2 skipped** (`test_vector_store_chroma.py` and `test_knowledge_release_chroma.py`, both `importorskip("chromadb")`).
- `backend/.venv/bin/python -m pytest -q tests/test_knowledge_release.py` → 39 passed. It covers plan items 1–14: happy path plus JSON Schema plus modes, determinism plus `compare`, approval (none/both/mismatch/wrong schema/not applied), four structural failures plus `gate_failed` publish refusal, end-to-end `evaluation_regression:fecha-presentacion-2026`, grounding unit, regression comparator unit, publish (lock, swap failure, log failure, tamper, not-ready, `already_current`), rollback, safety (`unsafe_release_root`, `current_outside_releases`, `release_conflict`, manifest consistency), service (unset-equivalence, publish without restart, tamper `503` plus one `knowledge_release` record, rollback, failed-gate target, empty root, mid-request swap), gate isolation (hybrid/local env plus sockets refused), import hygiene, vector options in the default env, and privacy.
- `CI=true ./scripts/init.sh --fast`, first run → exit `1`, only because `gradle-jvm-test` reported `Unable to locate a Java Runtime` (this agent host has no system JDK). Re-run with `JAVA_HOME` set to the Gradle-provisioned Zulu 21.0.11 JDK already in `~/.gradle/jdks` (nothing downloaded) → **exit `0`, "All 9 offline checks passed"** (`:shared:jvmTest` BUILD SUCCESSFUL, backend 1346 passed / 2 skipped).
- Hybrid tier **not run**. `./scripts/python-env.sh hybrid --if-present` → exit `1` (no hybrid environment has been built). Building it with `./scripts/init.sh --setup-python hybrid` would install several GB (torch, chromadb) from PyPI, an external network call the owner's no-external-call rule forbids. So `test_knowledge_release_chroma.py` (3 tests) was written but only collected and skipped, and the optional real-vector double build was not attempted (and no pinned artifact exists here).

**Determinism and sizes (canonical corpus, `as_of` 2026-10-13, campaign 2026, `HEAD` revision as both code and reviewed-baseline revision).** Two roots give release `aa97b66716f31e37` both times, with byte-identical manifest, BM25 record, and evaluation report. `prepare` wall time is 0.19 s (`/usr/bin/time`, real). File sizes in bytes: `source_catalog.json` 3126, `passages.json` 2988, `pac_answer_eval.json` 8875, `bm25-index.json` 7826, `evaluation-report.json` 13533, `release-manifest.json` 1938. Gate summary: 14 cases, 13 expected-state agreements, 1 unexpected answer (the known result; report-only, not a target). There were no grounding failures. `as_of` 2026-10-31 gives a different id (`07e2689c6999b406`); `compare` against the 2026-10-13 build lists only `inputs.as_of`, `release_id`, and the evaluation-report hash/size.

**Local rehearsal (temporary root, `uvicorn app.main:app --host 127.0.0.1 --port 8765`).** It ran in the pilot profile so operational records are visible, with a throwaway client token generated into the temp directory, and `MANIJERO_KNOWLEDGE_RELEASE_ROOT=<tmp root>`.

| Step | Result |
|---|---|
| prepare A (`2026-10-13`) / B (`2026-10-31`) | `aa97b66716f31e37` passed / `07e2689c6999b406` passed |
| publish A | `switched`; `/ready` 200, `/ask` 200 `answered` |
| publish B (no restart) | `switched`, previous A; `status` in sync; `/ready` 200, `/ask` 200 `answered` |
| failed-gate candidate (case pointing at a removed passage) | `c6b5719e0c3413e7`, `failures: cases_invalid,evaluation_failed`, exit 1; `publish` → `error: gate_failed` exit 2; service still on B, `/ready` 200, `/ask` 200 |
| tamper one byte of `current/passages.json` | `/ready` 503, `/ask` 503 `{"detail":"Answer service is temporarily unavailable."}`; `status` → `integrity: integrity_mismatch`, exit 1 |
| rollback | `switched` to A, previous B; `/ready` 200, `/ask` 200 `answered` |

`release-log.jsonl`: three lines, `publish A (prev null)`, `publish B (prev A)`, `rollback A (prev B)`, each with `at` UTC seconds. Server `knowledge_release` records (change-only): `served A ok`, `served B ok`, `refused B integrity_mismatch`, `served A ok`. A grep of the server log for passage or question text found 0 matches. The server was stopped, the root deleted, and port 8765 confirmed free.

**Per-request overhead (one host, four passages, 200 sequential authenticated `/ready` calls, same pilot profile).** With the release root: median 0.84 ms, p90 0.93 ms. Checkout `knowledge/` (variable unset): median 0.72 ms, p90 0.80 ms. That is about 0.1 ms per request on this Mac only, not a host measurement.

**Deviations and additions (within the contract).**
- The evaluation gate drives the unchanged `/ask` router through a minimal in-process FastAPI app (`release_gates.evaluation_app`) instead of `create_app(load_config(...))`. Importing `app.main` builds its module-level app from the operator's environment (a pilot profile without a clients file raises), and the gate must not depend on the environment. Overrides are as specified: corpus, `as_of`, campaign, `k=5`, `Bm25Backend`, generation `None`, retention `None`.
- Added fixed codes: `cases_orphaned` (expected passages/sources not admitted for the campaign/date; this is what a campaign mismatch produces, because readiness alone still passes on the campaign-less source), `code_revision_invalid`, `active_campaign_invalid`, `approval_evidence_invalid`, `input_unreadable`, `vector_options_incomplete` (`--embedding-index` and `--with-vector-store` go together), `embedding_config_invalid`, `log_unreadable`, `bm25_mismatch` (`verify`), `release_unreadable` (service).
- `rollback` without `--to` returns to the `previous_release_id` of the latest **publish** of the current release. A second rollback therefore reports `no_previous_release` instead of bouncing back to the release just rolled away from.
- A `manifest.bm25` of `null` is allowed only when the gate failed before BM25 could be built; `summary` is `null` only when evaluation did not run.
- The gate is sensitive by design: in a probe, prefixing a passage with "Nota. " regressed several unchanged cases (answer composition changed), while a trailing space did not. The Chroma test uses the trailing-space edit to change the admitted documents.

**Honest limits.** None of the following was executed: host, systemd unit, tunnel, TLS/DNS, provider account, release root on a server, or off-host backup of a release root. The release root is single-disk with no garbage collection. `--reviewed-baseline-revision` and `--code-revision` are recorded operator assertions; the tool does not verify them against Git. Chroma packaging and the vector-reproducibility comparison are untested here (no hybrid runtime, no pinned artifact). A hybrid backend needs a restart after a publish with changed documents and answers with BM25 until then. The evaluation is the 14-case author-only sample, and a passed gate is not a legal-coverage, answer-quality, or freshness claim. The planning note said the implementer leaves `feature_list.json` unchanged, but per the orchestrator's instruction the status was moved `in_progress` → `passing` after these checks; no evidence array was added.

## Validator checklist

- [ ] `./scripts/init.sh --feature knowledge_reindex_release` passes unchanged, offline, in `backend/.venv`; no virtualenv was created by hand.
- [ ] `contracts/openapi.yaml`, canonical `knowledge/*.json`, `retrieval.py`, `hybrid_retrieval.py`, `vector_store.py`, `embedding_index.py`, `answer_eval.py`, `review_package.py`, `pilot_ops.py`, requirements files, and `feature_list.json` status are unchanged by the implementer.
- [ ] With `MANIJERO_KNOWLEDGE_RELEASE_ROOT` unset, `/ask`, `/ready`, and preflight behave exactly as before (existing tests green, no new import at service start beyond the stdlib-light module).
- [ ] A failed gate writes `gate.passed: false`, exits `1`, and can be neither published, rolled back to, nor served.
- [ ] Publish is one `os.replace` of `current`; a failure at any step leaves the previous release serving; rollback restores the previous release and logs it.
- [ ] Each request resolves `current` once and verifies hashes and `gate.passed`; a tampered release yields the generic `503`.
- [ ] The gate forces BM25 retrieval and extractive generation and makes no network call regardless of environment.
- [ ] Same inputs give byte-identical manifest, BM25 record, and evaluation report; vector differences are reported, not hidden.
- [ ] Approval evidence is mandatory and hash-bound for merge records; the reviewed-baseline path is documented as an unverified assertion; no reviewer name in the release.
- [ ] No passage text, question, land value, or secret in stdout, logs, manifest, or release log.
- [ ] README, knowledge/README, ARCHITECTURE, CONSTRAINTS, and risks updated as the contract states; every host step is labeled not executed.
- [ ] Evidence supports only the local, one-host scope claimed; no answer-quality or legal-coverage claim.

### 2026-10-31 — validator acceptance note

Independent validator verdict: **accept**. `./scripts/init.sh --feature knowledge_reindex_release` was rerun offline in `backend/.venv` and passed (exit 0; full suite 1346 passed, 2 skipped). Throwaway-root CLI and service-seam probes reproduced the implementer's release ids and confirmed:

- approval and unsafe-root refusals;
- `gate_failed` refusal for both publish and `rollback --to`;
- `no_previous_release` on a second rollback;
- `release_locked`;
- a not-ready target is refused with exit 1;
- `integrity_mismatch`;
- the service refuses a failed-gate target and a `current` outside `releases/`.

Protected files are unchanged. The Chroma packaging path is an accepted, recorded limit (never executed; no hybrid environment, and downloads are forbidden). Record: [`docs/validations/knowledge_reindex_release.md`](../validations/knowledge_reindex_release.md).
