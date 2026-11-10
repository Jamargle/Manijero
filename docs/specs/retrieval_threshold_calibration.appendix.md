# retrieval_threshold_calibration — appendix

## Repository research

### Files inspected

- `backend/app/retrieval.py` — `Retriever._search` lexical gate (`score > 0.0`, none → empty), `CandidateRanker` protocol, `with_ranker` keeps records/index/fingerprint; this gate is the only `/ask` default retrieval threshold.
- `backend/app/abstention.py` — `answer_or_abstain`: scope guard before retrieval, empty candidates → `no_evidence` (`no_candidates`), then false-premise and conflict checks.
- `backend/app/ask_api.py` — year check before retrieval (`no_evidence`), `retrieval_backend.attach(...)` then `with_query_expansion(glossary.expand)`, so a ranker sees BM25 scores of the expanded query.
- `backend/app/retrieval_backend.py` — `Bm25Backend` default; `get_retrieval_backend` reads the environment, so the sweep overrides it explicitly.
- `backend/app/hybrid_retrieval.py` — `vector_min_similarity` is a hybrid-only floor (out of scope).
- `backend/app/reranker_measure.py` — reuse: `compare` (found / broken / trap worse), `_measurement_environment`, app building and overrides in `_run_pass`; `_run_pass` itself is not reusable (its fallback check expects a hybrid `last_trace`).
- `backend/app/answer_eval.py` — `evaluate(cases, client, catalog, passages, k, row_extra=...)` and its row keys.
- `backend/app/trap_set.py` — `load_traps`, `approved_cases`, `row_extra` (`actual_abstention_reason`, `abstention_reason_match`, `must_not_say_found`; `{}` for non-traps).
- `backend/scripts/evaluate_pac_answers.py` — argument set, golden/trap loading order, id-collision checks, exit 2 with `error: ...`.
- `backend/tests/test_reranker_measure.py` — synthetic-corpus pattern (`test_hybrid_retrieval` as `hyb`, `make_case`, injected `cases_loader`).
- `backend/tests/test_question_glossary.py` — runtime modules under `backend/app/` must not import `golden_set`; the new app module must not either.
- `backend/tests/test_golden_set.py` — gate/release/demo/load scripts must not read the queue; the new script is evaluation-only and is not on that list.
- `knowledge/golden_set.json` — 49 approved items (37 expected answered, 12 abstained by line count; implementer confirms from the loader).
- `knowledge/trap_set.json` — 26 approved; `trap-013`, `trap-014`, `trap-016` accept `no_evidence`, `insufficient_evidence`, `generator_abstained`.
- `docs/specs/adversarial_trap_set.appendix.md` — baseline: cooperative_practice 5 cases / 2 state agreement / 3 unexpected answers.
- `docs/specs/reranker_evaluation.md` — definitions reused (right source found, passes, broken, trap worse).
- `docs/constraints/answers-and-knowledge.md` — Reranking, Abstention, Safety evaluation sections.
- Not inspected: `safe_abstention` spec (accepted dependency; its behaviour is visible in `abstention.py`).

### Existing patterns to follow

- In-process `/ask` through `TestClient(create_app(load_config(...), retention_store=None, answer_cache=None))` with `dependency_overrides` for corpus, as-of, campaign, `k`, retrieval backend.
- Approved-only loading through `golden_set` / `trap_set` loaders in a script, never in `backend/app/`.
- Deterministic JSON: `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`; atomic writes (temp file + `os.replace`).
- Synthetic corpus and cases from `test_hybrid_retrieval` for offline tests.

### Current gaps

- No threshold exists beyond the lexical gate; no sweep tooling. No decision on adoption (by design: owner approves at acceptance, a later feature changes the default).

## Implementation plan

1. `threshold_calibration.py`: `MinScoreRanker` (filter `score ≥ t`, identity at `0.0`, records top lexical score) and `ThresholdBackend`.
2. Pure helpers: `grid`, `row_metrics` (via `reranker_measure.compare(baseline, rows, {})` plus local counts and changed ids), `recommend`, `cooperative_outcome`, `table_markdown`.
3. `run_sweep`: environment context, baseline pass (`Bm25Backend`), `t = 0.0` pass with per-id top scores, identity check, grid passes, report dict; stops raise a `SweepStop(line, exit_code)`.
4. Script: argument parsing like `evaluate_pac_answers.py`, `--out` guard (not inside `knowledge/`), approved golden + traps tagged `case_set`, cooperative-id check, atomic writes, final `Result:` line.
5. Tests (below), then the real sweep twice and compare digests.
6. Durable docs: constraint MUST, risks entry, `backend/README.md` section.
7. Paste the compact `table.md`, the recommendation, and the cooperative outcome into `Feature evidence`.

## Verification plan

Tests in `backend/tests/test_threshold_calibration.py` (synthetic corpus, no network, no model):

- ranker: identity at `0.0`; drops below `t` keeping order; never adds/reorders; all dropped → `/ask` abstains `no_evidence`.
- pre-retrieval routes (screen, scope guard, year check) identical at every `t`.
- zero row equals baseline; a forced mismatch (fake ranker) stops with exit 1, nothing written.
- grid: step 0.5, stops at the first step above the max top score; `[0.0]` with no retrieval; over 200 rows stops.
- `row_metrics` counts on hand-built rows, including `broken`/`worse` via `compare`.
- `recommend`: picks most trap correct abstentions among eligible, smallest on ties, `0.0` when nothing beats baseline, excludes rows with broken/worse/lost right sources.
- cooperative outcome: first abstaining threshold or `never in the grid`; missing/unapproved id stops.
- script: approved-only (drafts/rejected ignored), byte-identical double run, no question text in outputs, `--out` inside `knowledge/` exits 2, bad input exits 2 with nothing written, `knowledge/` digests unchanged, `socket.socket.connect` guarded, environment restored.
- isolation: `app.main` does not import `app.threshold_calibration`; existing glossary isolation test passes.
- Focused block: tests, the real sweep, and the unchanged-files diff.
- E2E: none; no app, HTTP contract, or UI change. `/ask` is exercised in-process.

## Evidence to capture

- Focused block result; real sweep run twice with SHA-256 of both `report.json` (identical).
- Baseline counts at `0.0`: golden answered / right source found / correct abstentions; trap correct abstentions / unexpected answers.
- Compact `table.md` (≤25 lines), the recommended value and the rule outcome.
- Cooperative outcome for `trap-013`, `trap-014`, `trap-016`.
- Unchanged-files diff and `knowledge/` digest check.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

## Validator checklist

- [ ] No change to `/ask` code, `backend/config/`, or `knowledge/` (merge-base diff empty); the evaluation ranker is not composed anywhere in the runtime.
- [ ] Only approved golden (49) and trap (26) items are scored, through `answer_eval.evaluate` + `trap_set.row_extra`.
- [ ] The zero row equals today's baseline; the identity stop is tested.
- [ ] Grid, recommendation rule, and cooperative outcome match scenarios 4–6; spot-check two table rows against `report.json`.
- [ ] Rerun the sweep: byte-identical report; no text, timing, or wall-clock date in outputs.
- [ ] Offline and model-free (socket guard test, no optional runtime imported).
- [ ] Focused block runs unchanged through `./scripts/init.sh --feature retrieval_threshold_calibration`.
- [ ] Constraint MUST, risks entry, and `backend/README.md` section added without restating the spec.
- [ ] Acceptance record carries the recommended value, compact table, and cooperative outcome for owner approval; the default change is left to a later feature. `feature_list.json` status and `PROGRESS.md` left to the integrator.
