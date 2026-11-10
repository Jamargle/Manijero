# Feature Spec: `reranker_evaluation`

## Source metadata

- **Feature:** `reranker_evaluation` — Measure a local reranker and enable it only if retrieval improves (`backend`).
- **Depends on:** `golden_dataset_expansion`, `chroma_hybrid_retrieval`, `adversarial_trap_set` (all accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no app screen, route, copy, or `/ask` contract change. The local answer service gains an optional second ranking step (a reranker) that is **off by default**. The owner gets one named command to download and verify the reranker model, one to measure it against today's search, and one each to switch it on or off; each ends with one plain-language `Result:` line. A plain-language owner guide explains what a reranker is, how it is measured, how to read the result, and how to switch it.
- **Verification:** offline pytest with a fake scorer, a fake hybrid loader, and a fake download opener (no model, no network, no `torch`, no `chromadb`), an offline pin check, then the owner's own download and measurement run (numbered steps below). No separate owner walkthrough: the owner's run of the documented commands is the walkthrough [operations](../constraints/operations.md) asks for.
- **Notes — owner decisions, 2026-11-10 (binding):**
  1. The planner picks a small local reranker model, backend side, pinned and verified like the `bge-m3` embedding model (same pin / checksum / download-and-verify pattern).
  2. Measurement stays simple: the existing 49-question golden set (metric: right source found near the top) plus the 26-question trap set (`knowledge/trap_set.json`).
  3. Enable only if at least 2 more golden questions find their right source than today's retrieval, no trap question gets worse, and no golden question that passes today breaks.
  4. If it does not improve retrieval, it stays off and the result is kept as a recorded experiment.
  5. Limits: at most 2 extra seconds per answer; model download up to 5 GB on the backend.
  6. The owner does not know what a reranker is: plain-language owner documentation explaining what it does, how it is measured, how to read the result, and how to switch it on/off, with one named command and plain-language results. No owner walkthrough unless strictly necessary.
  - (A) `adversarial_trap_set` is merged into this branch and is in `depends_on`.
  - (B) The **owner** downloads the reranker and runs the measurement. Agents never download the model, never run against the real model, and never write outside the project folder. Code and docs ship with the reranker **off**. Tests use fakes (no model, no network). The feature ends at `passing` with the owner step list below; after the owner reports the result line, the orchestrator records it and decides on/off by rule 3.
- **Orchestrator decisions, 2026-11-10 (binding):** (1) Pin values come only from the Hugging Face metadata API: SHA-256 for large-file-storage files, git-blob SHA-1 for the small non-LFS files; no small-file fetch. (2) "Today's retrieval" in rule 3 is what the owner's local service runs: **hybrid** (`local_rag_service.launch_environment`). The baseline is that hybrid ranking; the candidate is the reranker wrapping that same hybrid ranker. The measure command uses the hybrid environment and Chroma store `--local-rag-setup` prepares; if they are missing or stale it stops with a `Result:` line naming `--local-rag-setup` and never falls back to BM25. (3) The owner's own run of `--reranker-download` and `--reranker-measure` as the owner guide writes them **is** the owner walkthrough required by [operations](../constraints/operations.md); no separate walkthrough.
- **Planner decisions:** model = `BAAI/bge-reranker-v2-m3` (cross-encoder, XLM-RoBERTa base shared with `bge-m3`, multilingual incl. Spanish, Apache-2.0, about 568 M parameters, about 2.3 GB download — well under 5 GB). Both runs use the reviewed glossary expansion and extractive drafting over the repository's reviewed `knowledge/` files; reasons and rejected alternatives in the appendix. "Right source found" = an approved golden item expected `answered` comes back `answered` with every expected source cited (`answer_eval` `source_match`, top `k = 5`).

## Goal

Find out, with the owner's own reviewed questions and on the owner's Mac, whether re-ordering the found passages with a small local reranker makes the assistant cite the right official source more often without breaking anything, and switch it on only when the owner's rule says it earned it.

## Non-goals

- Changing the default retrieval, the `/ask` wire contract, abstention, citations, generation, verification, land clarification, or the answer cache key.
- The reranker in the container image, QA, the pilot profile, or any hosted environment.
- Measuring the plain BM25 path + reranker, a BM25 fallback baseline, a per-category quality claim, a numeric score threshold (that is `retrieval_threshold_calibration`), or MRR/hit@k reporting (that is `evaluation_metrics_report`).
- Editing `knowledge/`, the golden or trap sets, `contracts/`, `shared/`, or any app copy; any GPU/MPS path.
- Any agent download of model files, any run against the real model, any write outside the checkout by an agent.

## Job story

When my assistant finds several official passages for a question, I want a second, more careful reader to put the right one first, but only if my own reviewed questions prove it helps and nothing gets worse, so that I never trade safety for a guess.

## Acceptance scenarios

### 1. The pin is reviewed, closed, and fits the 5 GB limit
Given `backend/config/bge_reranker_v2_m3.json` (`reranker-model-v1`) · When `backend/scripts/reranker.py check-pin` runs · Then it exits `0` only if: closed key set; `model_id` `BAAI/bge-reranker-v2-m3`; a 40-hex `model_revision`; `https://huggingface.co/...` `source_url`; non-blank `license`; every file has a safe relative path, a byte size, and exactly one digest (`sha256` for large-file-storage files, `git_blob_sha1` for small text files); `config.json` and the weights file are pinned; total bytes ≤ 5,000,000,000. A placeholder revision `unpinned` exits `1` with `reranker_pin_unpinned`, so the feature cannot pass on a placeholder.

### 2. Artifact verification and download follow the bge-m3 pattern
Given a pinned spec and a fake opener · When the download runs · Then URLs come only from `<source_url>/resolve/<revision>/<path>`, redirects only to `https`, each file streams to `.part`, is checked against its pinned size and digest before rename, interrupted files resume, a mismatching file is deleted with `checksum_mismatch` / `size_mismatch`, already-matching files are not fetched, and the pin is never edited. Verification also rejects missing files, symlinks, path escapes, and a `config.json` that is not a single-score sequence classifier (`architectures` contains `XLMRobertaForSequenceClassification`, one label). Embedding downloads behave exactly as before.

### 3. The reranker only re-orders admitted candidates and fails closed
Given a retriever, a ranking from BM25 or hybrid, and a fake scorer · When the reranking ranker runs · Then it scores `(query, passage text)` for the first `candidate_depth` ids, orders them by score (ties keep the earlier rank), keeps any remaining ids after them in their original order, never adds or drops an id, and the lexical gate still returns no candidate for a zero-match question. Any scorer exception, wrong count, or non-finite score returns the input ranking unchanged, logs only a fixed reason code, and marks retrieval degraded for the answer cache. No question or passage text reaches a log or error.

### 4. Off by default; on only by explicit, verified configuration
Given no `MANIJERO_RERANKER`, or `off` · When the service starts and answers · Then the ranking is byte-for-byte today's, and importing `app.main` imports neither the reranker module nor `torch`/`transformers`. Given `MANIJERO_RERANKER=on` with `MANIJERO_RERANKER_ARTIFACT` · Then the reranker wraps the configured backend (BM25 or hybrid) and loads lazily on the first request; a missing variable, invalid value, invalid pin, missing runtime, or artifact mismatch keeps the unreranked ranking with one fixed reason code.

### 5. Owner downloads the model with one command
Given the local answer tools are set up · When the owner runs `./scripts/init.sh --reranker-download` (no arguments) · Then it checks free disk space and the pin first, downloads into `~/manijero/local/models/bge-reranker-v2-m3` with progress, verifies every file, and ends with `Result: the reranker model is downloaded and matches the reviewed copy (S.S GB). It stays off until it is switched on.` (size from the pin, one decimal). A second run ends `Result: the reranker model is already downloaded and matches the reviewed copy; nothing was downloaded.` Missing tools, low disk space, a failed download (re-run resumes), a non-matching file, or an unpinned record each end with one pinned `Result:` line naming the next step and exit non-zero.

### 6. Owner measures it with one command and gets the verdict by rule 3
Given the model is downloaded · When the owner runs `./scripts/init.sh --reranker-measure` (no arguments) · Then it first checks, in this order, the hybrid environment (`backend/.venv-hybrid`), the verified `bge-m3` artifact, the current release's Chroma store being fresh (`HybridBackend.status(...).up_to_date`) for the repository's reviewed `knowledge/` files and campaign `2026`, and the verified reranker model. It then runs the approved golden items and approved trap items through the in-process `/ask` path twice — **today's hybrid search**, then **the reranker wrapping that same hybrid ranker** — with today's local date, answer cache off, extractive drafting, both models loaded and warmed before timing, printing `Checked question <n> of <N>`. It prints only counts and timings and ends with exactly one line of the shape:

```
Result: reranker measured on G golden and T trap questions against today's hybrid search. Right source found: B today, R with the reranker (+D). Golden questions broken: X. Trap questions worse: Y. Slowest extra time: S.S seconds. Verdict: ON - it met all the rules. Send this line to the developer.
```

or, when any rule fails, the same line ending `Verdict: OFF - <reasons joined by "; ">. It stays off and this result is kept as a recorded experiment. Send this line to the developer.` Reasons, in this order: `fewer than 2 more golden questions found their right source`, `a golden question that worked today broke`, `a trap question got worse`, `slower than 2 extra seconds`. Definitions: *right source found* = expected `answered`, actual `answered`, `source_match`; *passes* = `expected_state_match` and `source_match`; *broken* = passes today, not with the reranker; *trap worse* = with the reranker `expected_state_match` goes true→false, `abstention_reason_match` goes true→false, or `must_not_say_found` grows; *extra time* = seconds spent in the reranker for one question; *ON* iff `R − B ≥ 2`, `X = 0`, `Y = 0`, slowest ≤ 2.0. A missing hybrid environment, `bge-m3` artifact, or store, or a stale store, ends `Result: the reranker was not measured because today's hybrid search is not ready. Run ./scripts/init.sh --local-rag-setup, then measure again.`; a missing reranker model names `--reranker-download`. If any question in either run used the BM25 fallback (`HybridRanker.last_trace.used_vector` false), there is no verdict: `Result: the reranker was not measured because today's hybrid search did not run for every question. Run ./scripts/init.sh --local-rag-setup, then measure again.` Never a silent BM25 baseline. All failures exit non-zero; a traceback goes only to a log path that is printed.

### 7. Owner switches it on or off with one command
Given the local settings file · When the owner runs `./scripts/init.sh --reranker-on` · Then it refuses (exit `1`) unless the model verifies, otherwise writes `MANIJERO_RERANKER=on` (replacing any earlier line, every other byte kept) and ends `Result: the reranker is switched on. It is used from the next ./scripts/init.sh --local-rag-start.` (adding "Stop and start the service to use it now." when the service runs). `--reranker-off` always writes `off` and ends with the matching line. `--local-rag-start` passes `MANIJERO_RERANKER`/`MANIJERO_RERANKER_ARTIFACT` only when the effective state is on and the model verifies; `--local-rag-service-status` shows one `Reranker:` line (`off`, `on`, or `switched on but the model is missing; answering without it`).

### 8. Effective state: owner line first, else the repository default
Given `backend/config/reranker.json` (`reranker-settings-v1`: `default_state`, `candidate_depth`, `max_tokens`, `batch_size`) with `default_state: "off"` · Then with no settings line the reranker is off; with `default_state: "on"` and a verified model it is on; an owner `off` line always wins. A settings template comment documents the key; an unknown value stops with a line naming the fix.

### 9. Recording the owner's result is evidence only
Given the owner reports the `Result:` line · When the orchestrator records it · Then it is pasted into the appendix `Feature evidence` and the acceptance record with the date; if `Verdict: ON`, the only change is `default_state` `"off"` → `"on"` in `backend/config/reranker.json` plus one status line in `PROGRESS.md`; if `OFF`, nothing changes and the result is the recorded experiment. No code changes in either case.

## Technical approach

- **`backend/app/reranker.py`** (stdlib at import): `reranker-model-v1` pin validator/loader (mirrors `embeddings.py`, reuses `safe_relative_path`/`path_stays_inside`), `verify_reranker_artifact`, `reranker-settings-v1` loader, `RerankScorer` protocol (`score(query, texts) -> tuple[float,...]`), `RerankingRanker(inner, scorer, settings, text_for)` implementing `CandidateRanker`, `RerankerBackend(inner_backend, loader)` (lazy, remembers a load failure, like `HybridBackend`), and `LocalBgeReranker.load` (lazy `torch`/`transformers` import with `OFFLINE_ENVIRONMENT`, `AutoModelForSequenceClassification`, `local_files_only`, `trust_remote_code=False`, `use_safetensors=True`, CPU float32, truncation to `max_tokens`).
- **`backend/app/pinned_download.py`**: accept any pin with `source_url`, `model_revision`, `files` and a per-file digest kind; compute SHA-256 or git-blob SHA-1 (`"blob <size>\0"` prefix) while streaming. Embedding behavior and its tests unchanged.
- **`backend/app/retrieval.py`**: two read-only accessors only — the current ranker and a passage text lookup by admitted id — so the reranker can wrap hybrid without replacing it.
- **`backend/app/retrieval_backend.py`**: after choosing BM25/hybrid, wrap with `RerankerBackend` only when `MANIJERO_RERANKER=on`; the import stays inside that branch.
- **`backend/app/reranker_measure.py`**: pure `compare(baseline_rows, reranked_rows, timings) -> Comparison`, `verdict`, `result_line`; plus `run_measurement(..., hybrid_loader, scorer)` building the app as `evaluate_pac_answers.py` does (golden + traps via `golden_set`/`trap_set` loaders, `answer_eval.evaluate`), overriding `get_retrieval_backend` per run: baseline = one `HybridBackend` built with `load_hybrid_components(bge-m3 pin, local bge-m3 artifact, current release store, hybrid config)` from `local_rag_bootstrap.local_paths()`; candidate = `RerankerBackend` wrapping that same loaded hybrid backend. It checks freshness before running, records `used_vector` per question, and times the scorer through a wrapper. Tests inject a fake hybrid loader (fake embedder + fake vector searcher) and a fake scorer; no `torch`, `chromadb`, or model. Owner rule constants: `MIN_GOLDEN_GAIN = 2`, `MAX_EXTRA_SECONDS = 2.0`, `MAX_MODEL_BYTES = 5_000_000_000`.
- **`backend/scripts/reranker.py`**: subcommands `check-pin`, `download`, `measure`, `switch on|off`; `main(argv, *, opener=None, scorer=None, ports=None)` for fakes. Reuses `local_rag_bootstrap` paths, settings reader, disk-space port, and log folder.
- **`local_rag_bootstrap.py` / `local_rag_service.py`**: `LocalPaths.reranker`, settings key `MANIJERO_RERANKER`, template comment, launch environment and status line.
- **`scripts/init.sh`**: four no-argument blocks mirroring `--grounding-judge-*` (`--reranker-download`, `--reranker-measure`, `--reranker-on`, `--reranker-off`) running with the hybrid environment's Python, plus help lines.

## Expected file changes

- Create: `backend/app/reranker.py`, `backend/app/reranker_measure.py`, `backend/scripts/reranker.py`, `backend/config/bge_reranker_v2_m3.json`, `backend/config/reranker.json`, `backend/tests/test_reranker.py`, `backend/tests/test_reranker_measure.py`, `backend/tests/test_reranker_commands.py`, `backend/tests/fixtures/reranker/` (synthetic, labelled), `docs/owner-guide/reranker.md`.
- Update: `backend/app/{pinned_download,retrieval,retrieval_backend,local_rag_bootstrap,local_rag_service}.py`, `scripts/init.sh`, `docs/owner-guide/README.md`, `backend/README.md` (≤30 lines), plus the durable docs below.
- Do not change: `backend/app/{main,ask_api,generation,answer_eval,golden_set,trap_set,embeddings,hybrid_retrieval}.py` behavior, `knowledge/`, `contracts/`, `shared/`, `backend/container/`, `requirements*.txt` (the pinned `transformers`/`torch` already provide cross-encoders), existing tests except to add cases.
- Implementer/validator only after evidence: `feature_list.json`, `PROGRESS.md`, `docs/progress/*`, `docs/validations/reranker_evaluation.md`.

## Visual design impact

None. Terminal output only, English like the other owner commands.

## Durable documentation impact

- `ARCHITECTURE.md`: update — one bullet: optional, off-by-default local cross-encoder reranker composed after BM25/hybrid through `with_ranker`, local service only.
- `docs/constraints/answers-and-knowledge.md`: update — new "Reranking" section: only re-orders admitted candidates, lexical gate kept, fails closed to the unreranked order, never imported when off, pin rule like embeddings (revision + per-file digest); `default_state` flips to `on` only with a recorded owner measurement meeting decision 3.
- `docs/constraints/operations.md`: update — one MUST: `--reranker-measure` prints only counts and timings and its verdict is the owner's on/off rule, not a quality claim or service promise.
- `docs/risks-and-open-questions.md`: update — the reranker decision rests on one owner run on one Mac over the author-reviewed golden and trap sets; the plain BM25 path (`MANIJERO_RETRIEVAL_MODE` unset) plus reranker is not measured.
- `docs/owner-guide/reranker.md`: create (≤60 lines). `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`: not needed.

## Owner steps (after `passing`)

These steps are the owner walkthrough (orchestrator decision 3). Before step 1, `./scripts/init.sh --local-rag-setup` must have finished (it prepares today's hybrid search).

1. Run `./scripts/init.sh --reranker-download`. Expect `Result: the reranker model is downloaded and matches the reviewed copy (about 2.3 GB). ...` It takes a while; running it again resumes.
2. Run `./scripts/init.sh --reranker-measure`. Expect the one `Result: reranker measured on ... against today's hybrid search ...` line of scenario 6. If it names `--local-rag-setup`, run that, then repeat this step.
3. Send that line to the developer. Do not switch anything on; the developer records it and applies rule 3.

## Focused verification

No step needs the model, `torch`, or the network. `check-pin` fails until the real pin is recorded.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_reranker.py tests/test_reranker_measure.py tests/test_reranker_commands.py tests/test_hybrid_retrieval.py tests/test_embeddings.py tests/test_local_rag_bootstrap.py tests/test_local_rag_service.py -q
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/reranker.py check-pin
```
<!-- verify:end -->

## Appendix

See [`reranker_evaluation.appendix.md`](reranker_evaluation.appendix.md) for repository research, the model choice, pinning, the ordered plan, evidence to capture, and the validator checklist.
