# Feature Spec: `knowledge_reindex_release`

## Source metadata

- **Feature:** `knowledge_reindex_release` — Rebuild and release approved knowledge (`operations`).
- **Status at planning:** `not_started`; depends on `knowledge_update_review_pr`, `chroma_hybrid_retrieval`, `backend_answer_evaluation`, `hosted_pilot_operations` (all accepted). Re-planned 2026-10-31; the earlier generic placeholder is superseded.
- **Source behavior:** After an approved human merge, validate catalog and passage schemas, deterministically rebuild BM25 and vector indexes from canonical reviewed artifacts, run grounding and evaluation gates, publish an artifact/version manifest, and deploy through the owner-operated release procedure with rollback. A failed gate cannot publish the candidate index.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.
- **Owner constraints (2026-10-31):** no spending and no paid/external service call; no server or provider account exists, so release and rollback are implemented and rehearsed **locally** (local release directory + local FastAPI service) and every host step is an honest limit. The backend environment is the shared `backend/.venv`; vector tooling comes only from `./scripts/init.sh --setup-python hybrid`. No wire-contract change; BM25 default and opt-in hybrid behavior stay intact.

## Goal and boundaries

Give the owner one repeatable, offline command path that turns the merged canonical catalog/passages into an immutable, hash-addressed **knowledge release**, gates it, and publishes it atomically with a one-command rollback, so the service never serves an unvalidated or half-written corpus.

**In scope**

- A stdlib-only release builder (`prepare`) that validates the canonical pair, binds it to human-approval evidence, rebuilds and fingerprints the BM25 index, runs structural, grounding, and evaluation gates, optionally packages a pre-built embedding index and Chroma store, and writes a closed `knowledge-release-v1` manifest last.
- Atomic `publish` (symlink swap under a lock), `rollback` (to the previous or a named release), `status`/`verify`, and `compare` (reproducibility report between two releases), with an append-only release log.
- An **opt-in** service read path: when `MANIJERO_KNOWLEDGE_RELEASE_ROOT` is set, `/ask` and `/ready` read the published release (hash-verified per request); when unset, behavior is byte-for-byte today's (`knowledge/` in the checkout).
- A local rehearsal (tests plus a manual loopback uvicorn run) of publish → serve → bad release → rollback.

**Non-goals:** changing `contracts/openapi.yaml` or any response field; changing BM25 scoring, hybrid fusion, generation, or verification; making hybrid the default; building embeddings inside `prepare` (that stays `manage_embeddings.py build` in the hybrid environment); downloading any model; deploying to or claiming a host, systemd, tunnel, or provider; garbage-collecting old releases; editing canonical `knowledge/` files or `merge.json`; a numeric quality threshold or any legal-coverage/answer-quality claim; Windows support for the release root.

## Job story

When an approved knowledge update has been merged, I (the owner-operator) want to rebuild, check, and switch the answer service to it in one reversible step, so that a bad corpus or index can never reach users and I can return to the last good release in seconds.

## Acceptance scenarios

### Prepare a candidate from an approved merge

Given the canonical catalog/passages, the reviewed case set, a `merge.json` whose `catalog_sha256`/`passages_sha256` equal the candidate bytes (or an explicit `--reviewed-baseline-revision <40-hex>`), `--as-of`, `--active-campaign`, and `--code-revision <40-hex>`, when `prepare` runs, then it writes `<root>/releases/<release_id>/` containing byte copies of the three inputs, `bm25-index.json`, `evaluation-report.json`, and `release-manifest.json` (written last, gate `passed: true`), prints the release id, and exits `0`. Canonical `knowledge/` and the merge package are byte-identical afterwards.

### Missing or mismatched approval evidence

Given neither approval option, both options, or a merge record whose hashes differ from the candidate, when `prepare` runs, then it exits `2` with `approval_evidence_required`, `approval_evidence_ambiguous`, or `approval_mismatch` and writes no release directory.

### Failed gate never publishes

Given a candidate that fails any gate (invalid catalog/passages, unresolved passage source, corpus not ready for the campaign/date, invalid or orphaned cases, an answered evaluation response whose citation does not map to exactly one candidate passage, or a per-case regression against the currently published release), when `prepare` runs, then the release directory is written with `gate.passed: false` and fixed failure codes, the command exits `1`, and `publish`/`rollback` to that id refuse with `gate_failed` (exit `2`) leaving `current` unchanged. The service read path also refuses a release whose manifest says `gate.passed: false`.

### Atomic publish and rollback

Given a passed release, when `publish --release-id <id>` runs, then the tool re-verifies every recorded hash, checks readiness as of `--as-of`, takes an exclusive lock, swaps `<root>/current` to `releases/<id>` with one `os.replace`, appends a `publish` event (with `previous_release_id`) to `<root>/release-log.jsonl`, and exits `0`. When `rollback` runs, `current` returns to the previous published release (or `--to <id>`) under the same checks and a `rollback` event is appended. A tampered, missing, not-ready, or failed target leaves `current` untouched (exit `1` not ready, `2` refused). A held lock refuses with `release_locked`.

### Service reads only a verified published release (opt-in)

Given `MANIJERO_KNOWLEDGE_RELEASE_ROOT` is set, when `/ask` or `/ready` runs, then the request resolves `current` once, requires the target to be inside `<root>/releases/`, reads the manifest, verifies the catalog and passages SHA-256 and `gate.passed`, and uses that single directory for both files; any failure is the existing generic `503` / not-ready. A publish between two requests switches the corpus without restart; one request never mixes two releases. Given the variable is unset, `/ask`, `/ready`, preflight, and all existing tests behave exactly as before.

### Determinism and reproducibility report

Given the same inputs, `as_of`, campaign, code revision, Python and Unicode-data versions, and model pin, when `prepare` runs twice into different roots, then `bm25-index.json`, `evaluation-report.json`, and `release-manifest.json` are byte-identical and the release ids are equal. `compare` reports every differing manifest field; vector digests that differ across hosts/runtimes are reported as `vector_digest_differs`, never hidden. No timestamp enters the manifest; timestamps live only in the release log.

### Optional hybrid artifacts

Given `--embedding-index <path>` that is `up_to_date` for the candidate inputs and pin, when `prepare --with-vector-store` runs in the hybrid environment, then the release also holds `embedding-index.json` and `vector-store/` (built with the existing `write_store`), and the manifest records the model pin, index SHA-256, and the store manifest's `documents_sha256`/`vectors_sha256`. A stale index (`embedding_index_stale:<reasons>`) or missing `chromadb` (`vector_runtime_unavailable`) fails closed with nothing published. Hybrid still activates only through `MANIJERO_RETRIEVAL_MODE=hybrid` with `MANIJERO_VECTOR_STORE` pointing at the store; a store from another release is stale and falls back to BM25 until restart.

## Technical approach

1. **`backend/app/knowledge_release.py` (stdlib only; imported by `ask_api`)** owns the layout (`<root>/releases/<id>/`, `<root>/current` relative symlink, `<root>/release-log.jsonl`, `<root>/.release.lock` via `O_CREAT|O_EXCL`), the closed `knowledge-release-v1` manifest (validator plus `knowledge/knowledge-release-manifest.schema.json`), the content id (first 16 hex of SHA-256 over canonical JSON of the manifest minus `release_id`), integrity verification, publish/rollback/status/compare, and `load_published_corpus(root) -> (catalog, passages, release_id)`. Errors are `ReleaseError(code, exit_code)` with fixed codes; no file content, question, or land value is printed or logged. The release root must be outside `knowledge/` (`unsafe_release_root`); files are written `0644`, directories `0755`; a release directory is written to a sibling staging directory and renamed into place; an existing id is reused only if its manifest is byte-identical (`already_prepared`), otherwise `release_conflict`.
2. **`backend/app/release_gates.py`** (lazily imported by `prepare` only) runs, in order: **structural** (`load_catalog`/`validate_catalog` at `as_of`, `validate_passage_set`, `Retriever.from_documents`, `evaluate_readiness`, `answer_eval.load_case_document`); **BM25** (two independent rebuilds from `Retriever.indexed_documents()` + `tokenize` + `BM25_K1`/`BM25_B`, canonical JSON of ids, text SHA-256, lengths, term frequencies, document frequencies, average length; digests must match, else `bm25_nondeterministic`); **grounding + evaluation** (a fresh `create_app(load_config({"MANIJERO_ACTIVE_CAMPAIGN": campaign}), retention_store=None)` with dependency overrides for corpus, `as_of`, campaign, `k=5`, `get_retrieval_backend → Bm25Backend()`, `get_generation_provider → None`, driven by a capturing client passed to the unchanged `answer_eval.evaluate`; every answered response must validate as `AskResponse`, have ≥1 source, and map each source to exactly one candidate passage by URL, location, and literal excerpt); **regression** against the currently published release's `evaluation-report.json`: for each case id whose case-definition SHA-256 is unchanged, any of `expected_state_match`, `source_match`, `passage_match`, `critical_facts_match`, `clarification_ids_match` going true → false fails with `evaluation_regression:<case_id>`; new, changed, and removed cases are reported, not gated; with no published release the baseline is recorded as `none`. The gate is deterministic and never uses the environment's retrieval mode or generation provider.
3. **Approval binding:** `--merge-record` must be `knowledge-update-merge-v1` with `canonical_changes_applied: true` and matching hashes; the manifest records `package_id`, `approved_on`, and the record's SHA-256 (not the reviewer name). `--reviewed-baseline-revision` records `kind: reviewed_git_baseline` as an operator assertion the tool cannot verify (honest limit). `--code-revision` is recorded, not checked against Git.
4. **Service seam:** `ask_api.load_corpus_documents()` with no path arguments checks `MANIJERO_KNOWLEDGE_RELEASE_ROOT`; if set it calls `load_published_corpus` and maps any `ReleaseError` to `load_error=True`. It logs one `knowledge_release` operational record (`release_id`, `state`, `reason` fixed code) only when the outcome changes. The explicit path seam used by preflight overrides and restore verification is unchanged; preflight inherits the release automatically through the default call.
5. **CLI `backend/scripts/knowledge_release.py`:** `prepare`, `publish`, `rollback`, `status`, `verify`, `compare`; exit `0` success, `1` gate failed / not ready / differs / no current, `2` refused or invalid input. Output is fixed-key `key: value` lines (or `--json`), never corpus text; `prepare` always prints a `release_id: <id>` line (also on exit `1`). `--root` may be an existing empty directory or is created `0755`. `publish`/`rollback` take `--root`, `--as-of` (default today UTC), `--active-campaign`; `publish` takes `--release-id`; `rollback` takes optional `--to`. `verify`/`status` take `--root`; `compare` takes two release directories `--a`/`--b`. The publish clock is injectable for tests.

## Expected file changes

- `backend/app/knowledge_release.py`, `backend/app/release_gates.py` — new.
- `backend/scripts/knowledge_release.py` — new operator CLI.
- `backend/app/ask_api.py` — opt-in published-release read path and change-only `knowledge_release` log record; nothing else.
- `knowledge/knowledge-release-manifest.schema.json` — new readable contract for the manifest.
- `backend/tests/test_knowledge_release.py` — new; default environment, offline, no model, no `chromadb`.
- `backend/tests/test_knowledge_release_chroma.py` — new; `pytest.importorskip("chromadb")`, fake 1024-d vectors, no model.
- `backend/deploy/pilot.env.example` — one commented `MANIJERO_KNOWLEDGE_RELEASE_ROOT` line.
- `backend/README.md`, `knowledge/README.md`, `ARCHITECTURE.md`, `CONSTRAINTS.md`, `docs/risks-and-open-questions.md` — see below. `PROGRESS.md` and `docs/progress/session-log.md` per the normal acceptance flow.
- **Not changed:** `contracts/`, canonical `knowledge/*.json`, `backend/app/retrieval.py`, `hybrid_retrieval.py`, `vector_store.py`, `embedding_index.py`, `answer_eval.py`, `review_package.py`, `pilot_ops.py`, requirements files, `scripts/init.sh`, `feature_list.json`.

## Visual design impact

None. No app or Spanish copy changes.

## Durable documentation impact

- `ARCHITECTURE.md` — **update**: add a bullet for `knowledge_release.py`/`release_gates.py` (immutable hash-verified releases, atomic `current` swap, opt-in service read path) and amend the hosted-pilot sentence that a corpus change is a reviewed deploy to name the release publish/rollback path.
- `CONSTRAINTS.md` — **update** the existing release MUST (line ~531) into concrete invariants: a release is built only from canonical artifacts bound to approval evidence; a failed gate MUST NOT be published or served; publication MUST be a single atomic pointer swap with recorded previous release; the manifest MUST carry no timestamp or personal value; releases MUST NOT live under `knowledge/`.
- `backend/README.md` — **update**: new "Knowledge reindex and release" section (layout, commands, exit codes, gates, hybrid packaging, determinism, rollback, limits); point "Deploying an update and rolling back" and "Corpus/config rollback" to it for a configured release root.
- `knowledge/README.md` — **update** step 5 to name the implemented local release step and its limits.
- `docs/risks-and-open-questions.md` — **update**: release/rollback rehearsed only locally; no host, unit, or tunnel rehearsal.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/openapi.yaml` — **not needed**: no rule, term, UI, or wire change.

## Focused verification

Runs offline in the shared `backend/.venv` (no model, no `chromadb`, no network, no server). The CLI lines rehearse prepare → publish → verify → compare in a throwaway root.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_knowledge_release.py tests/test_ask_endpoint.py tests/test_pilot_operations.py tests/test_hybrid_retrieval.py tests/test_pac_answer_eval.py tests/test_knowledge_update_review.py
REL_A="$(mktemp -d "${TMPDIR:-/tmp}/manijero-release-a-XXXXXX")"; REL_B="$(mktemp -d "${TMPDIR:-/tmp}/manijero-release-b-XXXXXX")"; REV="$(git rev-parse HEAD)"
ID_A="$(backend/.venv/bin/python backend/scripts/knowledge_release.py prepare --root "$REL_A" --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of "${AS_OF:-2026-10-13}" --code-revision "$REV" --reviewed-baseline-revision "$REV" | sed -n 's/^release_id: //p')"
ID_B="$(backend/.venv/bin/python backend/scripts/knowledge_release.py prepare --root "$REL_B" --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of "${AS_OF:-2026-10-13}" --code-revision "$REV" --reviewed-baseline-revision "$REV" | sed -n 's/^release_id: //p')"
test -n "$ID_A" && test "$ID_A" = "$ID_B"
backend/.venv/bin/python backend/scripts/knowledge_release.py compare --a "$REL_A/releases/$ID_A" --b "$REL_B/releases/$ID_B"
backend/.venv/bin/python backend/scripts/knowledge_release.py publish --root "$REL_A" --release-id "$ID_A" --as-of "${AS_OF:-2026-10-13}" --active-campaign 2026
backend/.venv/bin/python backend/scripts/knowledge_release.py verify --root "$REL_A"
rm -rf "$REL_A" "$REL_B"
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

Heavier checks (not in the block; need `./scripts/init.sh --setup-python hybrid`, and for the last item an already-present pinned bge-m3 artifact — never download one for this feature) are listed in the appendix verification plan: `test_knowledge_release_chroma.py` with `backend/.venv-hybrid`, and an optional real-vector double build to report same-host vector reproducibility.

## Appendix

See [`knowledge_reindex_release.appendix.md`](../archive/specs/knowledge_reindex_release.appendix.md) for repository research, design decisions, the implementation plan, the verification plan and local rehearsal, evidence to capture, feature evidence, and the validator checklist.
