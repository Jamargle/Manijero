# reranker_evaluation — appendix

Contract: [`reranker_evaluation.md`](reranker_evaluation.md). This file holds research, the plan, and evidence.

## Repository research

Inspected 2026-11-10 (planner, read-only):

- `backend/config/bge_m3_embedding.json` — the pin shape to mirror (`embedding-model-v1`: revision, license, per-file path/size/sha256).
- `backend/app/embeddings.py` — closed pin validator, `verify_artifact`, `safe_relative_path`, `path_stays_inside`, `OFFLINE_ENVIRONMENT`, lazy runtime import; the reranker module copies these patterns.
- `backend/app/pinned_download.py` — pin-only URLs, https-only redirects, `.part` resume, size+SHA-256 check before rename; typed to `EmbeddingModelSpec` and SHA-256 only, so it needs a small generalization.
- `backend/app/retrieval.py` — `CandidateRanker`, `Retriever.with_ranker` (replaces the ranker, so the reranker must wrap the current one), lexical gate in `_search`; the ranker receives the expanded query and ids only (needs a text lookup).
- `backend/app/hybrid_retrieval.py` — `HybridRanker` / `HybridBackend` lazy-load and fail-closed model to copy; `answer_cache.note_degraded_retrieval` on fallback.
- `backend/app/retrieval_backend.py` — environment-driven backend choice; import-light rule.
- `backend/app/answer_eval.py` — per-row `source_match`, `expected_state_match`; `evaluate(cases, client, ...)` posts to in-process `/ask`.
- `backend/scripts/evaluate_pac_answers.py` — how golden (`golden_set.load_golden`/`approved_cases`) and traps (`trap_set.load_traps`/`approved_cases`/`row_extra`) merge into one run with dependency overrides.
- `backend/app/trap_set.py` — `row_extra` gives `abstention_reason_match` and `must_not_say_found` used for "trap worse".
- `backend/app/local_rag_bootstrap.py` — `LocalPaths`, `settings.env` template and strict reader (allowlisted keys), disk-space port, hybrid venv path `backend/.venv-hybrid`.
- `backend/app/local_rag_service.py` — `launch_environment` (always hybrid + local drafting) and status checks.
- `scripts/init.sh` (`--grounding-judge-*` block, ~line 399) — owner-command dispatch shape; `docs/owner-guide/grounding-judge.md` — owner guide shape.
- `docs/constraints/answers-and-knowledge.md` "Local embeddings" / "Hybrid retrieval" and `docs/constraints/operations.md` — rules the reranker must extend.
- `knowledge/passages.json` (7 passages) and `knowledge/golden_set.json` / `knowledge/trap_set.json` — measurement inputs; no score threshold exists yet in `/ask` (grep `threshold` in `backend/app`).
- Not inspected: Hugging Face metadata for `BAAI/bge-reranker-v2-m3` (no network in this session); the exact revision, file list, sizes, and digests are unknown to the planner.

## Model choice

- **Chosen:** `BAAI/bge-reranker-v2-m3` — Apache-2.0, ~568 M parameters, XLM-RoBERTa-large base initialised from `bge-m3` (same tokenizer family the repo already pins), multilingual with Spanish, single-logit cross-encoder loadable with the already-pinned `transformers`/`torch`, safetensors weights about 2.3 GB.
- **Rejected:** `jinaai/jina-reranker-v2-base-multilingual` (CC-BY-NC-4.0, non-commercial; needs remote code); `BAAI/bge-reranker-v2-gemma` (~10 GB, over the 5 GB limit); `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache-2.0, ~0.5 GB and faster, but trained on machine-translated MS MARCO and weaker). It is the natural follow-up if the only failed rule is `slower than 2 extra seconds`.
- **Latency expectation (unmeasured):** with 7 passages every candidate is reranked; `max_tokens = 512`, `batch_size = 8`, `candidate_depth = 20` in `backend/config/reranker.json`. Whether CPU float32 stays under 2 s is exactly what the owner's run decides.
- **Baseline (orchestrator decision 2):** the owner's hybrid retrieval, as `local_rag_service.launch_environment` runs it (`MANIJERO_RETRIEVAL_MODE=hybrid`, current release store, `bge-m3`). Candidate = the reranker wrapping that same loaded `HybridBackend`, so both runs share one embedder and store. The command requires a fresh store for the repository's `knowledge/` files (else `--local-rag-setup`) and rejects the run if any question fell back to BM25 in either pass. Memory: `bge-m3` plus the reranker, about 4.6 GB of weights in RAM during the run.

## Pinning (implementer, before any code that depends on values)

- Accepted by the orchestrator 2026-11-10: metadata only, no small-file fetch.
- Read only `GET https://huggingface.co/api/models/BAAI/bge-reranker-v2-m3?blobs=true` (one metadata JSON; no model file bytes). Record the commit `sha`; for each needed sibling, `size` plus `lfs.sha256` → `sha256`, or non-LFS `blobId` → `git_blob_sha1`. Needed files: `config.json`, `model.safetensors`, `sentencepiece.bpe.model`, `special_tokens_map.json`, `tokenizer.json`, `tokenizer_config.json` (adjust only to what the revision lists; never `pytorch_model.bin` as well).
- Record the request date and values in `Feature evidence`. If the metadata cannot be read, leave `model_revision: "unpinned"` (check-pin fails) and stop with a `## Handoff` question; never invent values.
- `config.json` content cannot be cross-checked by agents; the architecture/one-label check runs at the owner's download.

## Implementation plan

1. Pin + settings files: `backend/config/bge_reranker_v2_m3.json` (values per Pinning), `backend/config/reranker.json` (`default_state: "off"`, depth 20, tokens 512, batch 8).
2. `app/reranker.py` pin validator, loader, `verify_reranker_artifact` (sha256 / git-blob SHA-1, config cross-check), settings loader; tests first.
3. Generalize `pinned_download.py` digest handling; keep every embedding test green.
4. `retrieval.py` accessors (current ranker, admitted passage text); `RerankingRanker` + `RerankerBackend`; `retrieval_backend.py` wrap branch.
5. `LocalBgeReranker` (lazy runtime; untested beyond a fake-runtime unit test of batching, truncation, and sigmoid-free raw logits ordering).
6. `app/reranker_measure.py`: `compare`, `verdict`, `result_line`, `run_measurement` with injectable hybrid loader, scorer, and clock; prerequisite order: hybrid venv, `bge-m3`, fresh store, reranker model.
7. `scripts/reranker.py` subcommands and pinned `Result:` lines; tracebacks to `~/manijero/local/logs/reranker-last-error.log`.
8. `local_rag_bootstrap.py` (paths, key, template comment), `local_rag_service.py` (environment, status line).
9. `scripts/init.sh` four blocks + help lines.
10. Owner guide `docs/owner-guide/reranker.md` + index line; `backend/README.md`; durable docs per contract.
11. Run the focused block; append evidence; set status `passing`; update `## Handoff` with the owner steps.

## Tests to write (named by behavior)

- `test_reranker.py`: pin closed keys / revision / one-digest-per-file / size cap / placeholder; verify sha256 and git-blob files, symlink, escape, missing, wrong architecture; ranker reorders top depth, keeps tail, never adds/drops, ties stable, lexical gate kept over BM25 and over a fake hybrid inner ranker; fallback on exception, count mismatch, NaN/inf with fixed log code and degraded mark; no text in logs (sentinel); off/unset/invalid env; lazy load once; `import app.main` in a subprocess leaves `app.reranker`, `torch`, `transformers` out of `sys.modules`.
- `test_reranker_measure.py`: verdict ON at exactly +2 / 0 / 0 / 2.0 s; OFF for +1, for one broken golden despite +3, for each trap-worse kind, for 2.01 s; multiple reasons in fixed order; exact result line text; golden abstained items never count as found; run with a fake hybrid loader (fake embedder + fake vector searcher) and fake scorer over fixture golden/trap files gives expected counts, the candidate wraps the same hybrid backend instance, and the baseline is hybrid (`used_vector` true); missing hybrid venv / `bge-m3` / store and a stale store each stop with the `--local-rag-setup` line and no verdict; a BM25 fallback on any question in either pass stops with the "did not run for every question" line; missing reranker model names `--reranker-download`; cache disabled between runs; stdout has no question/passage sentinel text.
- `test_reranker_commands.py`: download via fake opener (fresh, resume, mismatch deletes, https-only, already-complete, low disk, unpinned), each pinned `Result:` line and exit code; switch on refused without verified model, on/off replace one line and keep other bytes; effective-state precedence; launch environment and status line; `init.sh` blocks reject extra arguments and name `--local-rag-setup` when tools are missing.

## Evidence to capture

- Pin source request date and values; focused block command + one-line result; `check-pin` result; the subprocess import-guard result; `git diff --stat` showing no change under `knowledge/`, `contracts/`, `shared/`, `backend/container/`.
- After the owner run (orchestrator): the two owner `Result:` lines verbatim with date, the rule-3 decision, and whether `default_state` changed.

## Feature evidence

- Pin source (2026-11-10, owner-saved metadata, no network request by the implementer): `build/reranker-metadata.json` = `GET https://huggingface.co/api/models/BAAI/bge-reranker-v2-m3?blobs=true`. Revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, license apache-2.0, `XLMRobertaForSequenceClassification`. Pinned 6 files, 2,293,242,108 bytes (about 2.3 GB, under 5 GB): `model.safetensors`, `sentencepiece.bpe.model`, `tokenizer.json` by LFS SHA-256; `config.json`, `special_tokens_map.json`, `tokenizer_config.json` by git-blob SHA-1. A script cross-checked every pin value against the saved metadata (sizes, digests, revision): ok. `config.json` content (one label) is only checked at the owner's download.
- `./scripts/init.sh --feature reranker_evaluation`: 463 passed (focused block as published) and `check-pin`: `Result: the reranker pin is valid (6 files, 2.3 GB; revision 953dc6f6f85a).`
- `./scripts/init.sh --fast`: all 10 offline checks passed (`backend-tests` 3312 passed, 9 skipped). `--verify` not run (no Android, Desktop, packaging, or shared-surface change).
- Import guard (subprocess, in `test_reranker.py`): importing `app.main` leaves `app.reranker`, `app.reranker_measure`, `torch`, `transformers`, `chromadb` out of `sys.modules`; `MANIJERO_RERANKER` unset or `off` does not import `app.reranker`.
- `git diff --stat`: no change under `knowledge/`, `contracts/`, `shared/`, `backend/container/`; `main`, `ask_api`, `generation`, `answer_eval`, `golden_set`, `trap_set`, `embeddings`, `hybrid_retrieval` untouched.
- No agent download, real-model run, or write outside the checkout. The measure command was exercised only over fakes (fake hybrid loader and scorer, plus the real reviewed golden and trap files in `test_reranker_commands.py`).
- Implementation notes (refinements, not contract changes): (1) a BM25 fallback is detected as "the hybrid ranker was absent or recorded a fallback reason" (`HybridRanker.last_trace.fallback_reason`), because a question with no lexical match or screened before retrieval never calls the ranker and is not a fallback. (2) The reranker keeps each id's inner score and changes only the order. (3) One `/ask` can search twice (land clarification), so "extra time" sums the scorer seconds per question. (4) The service-status `Reranker:` line is printed as `NOTE`, outside the three OK/PROBLEM checks. (5) Owner commands run with `backend/.venv-hybrid`. (6) The golden/trap case loader lives in `backend/scripts/reranker.py` (`load_cases`) and is passed to `run_measurement`, because `test_question_glossary` forbids runtime modules under `app/` from importing `golden_set`.
- After the owner run (orchestrator, not yet done): paste the owner's two `Result:` lines here with the date and the rule-3 decision.

## Validator checklist

- Notes carry owner decisions 1–6, A, B; reranker off by default everywhere; no agent download or real-model run in evidence.
- Pin values trace to the recorded metadata request; `check-pin` passes; total ≤ 5 GB.
- Ranker cannot add, drop, or admit passages; lexical gate and fallback proven over BM25 and hybrid; no text in logs.
- Baseline is the owner's hybrid search and the candidate wraps that same hybrid ranker; no path yields a verdict over BM25.
- Rule 3 + 2-second limit implemented exactly as scenario 6 defines; result-line text matches the contract and owner guide.
- Owner commands: no arguments, prerequisites checked first, one `Result:` line, non-zero on failure; owner guide ≤ 60 lines, plain language, explains what a reranker is, how it is measured, how to read the line, how to switch.
- Durable docs updated as listed; forbidden files unchanged; focused block passes as published.

## Handoff

- Status: `passing`, held pending the owner run. Validator 2026-11-10: accept with condition `pending owner walkthrough` (`docs/validations/reranker_evaluation.md`). Next action: owner steps below; no further validator. The reranker ships **off** (`default_state: "off"`).
- Done: pin from the saved metadata, `app/reranker.py`, `app/reranker_measure.py`, `scripts/reranker.py`, shared downloader generalized (SHA-256 and git-blob SHA-1), retriever accessors, `MANIJERO_RERANKER` wrap in `retrieval_backend.py`, settings/launch/status wiring, four `init.sh` commands, owner guide, durable docs, tests (463 in the focused block).
- Checks run: `./scripts/init.sh --feature reranker_evaluation` (pass, 463 tests) and `./scripts/init.sh --fast` (pass, 3312 tests). `--verify` not run: no Android, Desktop, packaging, or shared-surface change.
- Not done by design: no model download and no real measurement (agents never do these). Real `torch`/`transformers` loading and the real latency are exercised only in the owner's run.
- Owner steps (after validation), after `./scripts/init.sh --local-rag-setup` has finished: (1) `./scripts/init.sh --reranker-download`; (2) `./scripts/init.sh --reranker-measure`; (3) send the `Result:` line to the developer. The orchestrator records the line here and in `docs/validations/reranker_evaluation.md` and applies rule 3: on `Verdict: ON` change only `default_state` to `"on"` in `backend/config/reranker.json` plus one `PROGRESS.md` status line; on `OFF` change nothing.
- Risks for the validator to probe: the `config.json` one-label check (`id2label` or `num_labels`) first runs on the real file at the owner's download; memory use of `bge-m3` plus the reranker (about 4.6 GB of weights) is unmeasured.
