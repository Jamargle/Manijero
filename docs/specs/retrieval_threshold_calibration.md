# Calibrate the retrieval abstention threshold on the golden and trap sets

## Source metadata

- `id`: retrieval_threshold_calibration · `area`: backend · `depends_on`: golden_dataset_expansion, adversarial_trap_set, safe_abstention (all accepted) · `status` at planning: not_started
- User-visible behavior: none in the app or `/ask`. A developer command sweeps a minimum search-score threshold over the 49 approved golden items and the 26 approved traps. It writes a report-only trade-off table and one recommended value. The owner approves that value at acceptance by reading the acceptance record.
- Verification: offline pytest with the synthetic corpus, then one real deterministic sweep over the reviewed `knowledge/` files (focused block). Validator accept is final; there is no owner walkthrough.
- Owner decisions (2026-11-10, final):
  1. Sweep over the approved golden and trap items, scored only through the existing evaluator path (`answer_eval.evaluate` plus `trap_set.row_extra`).
  2. The `/ask` default MUST NOT change. Publish the per-threshold table and a recommended value for the owner to approve at acceptance. Changing the default is a later, separate feature.
  3. Deterministic, report-only, read-only over `knowledge/`. No new model, no network, no paid API.
  4. Record the outcome for the 3 cooperative-practice traps that `adversarial_trap_set` left here: `trap-013`, `trap-014`, `trap-016`. All three expect `no_evidence` / `insufficient_evidence` / `generator_abstained` and are answered by `/ask` today.
- Planner decisions:
  - **The threshold.** The `/ask` default ranking is BM25, and its only retrieval abstention threshold is the lexical gate in `Retriever._search`: candidates with score `> 0.0` are kept, and none left means `no_evidence`. The swept threshold `t` is a minimum BM25 score on those lexical candidates. `t = 0.0` is today. For `t > 0`, a candidate is kept only if its score is `≥ t`. A question whose best candidate scores below `t` abstains `no_evidence`.
  - **How it is simulated.** An evaluation-only ranker composed through `Retriever.with_ranker`; no runtime code changes.
  - **Hybrid is out of scope.** The hybrid `vector_min_similarity` is not swept (it needs the `bge-m3` model).
  - **Parallel worktree.** `feature_list.json` status and `PROGRESS.md` belong to the integrator.

## Goal

Measure, on the owner's reviewed questions, what each minimum search score would change: golden questions still answered with the right source, and trap questions correctly refused. Then recommend one value by a fixed rule. Nothing the app does changes.

## Non-goals

- Changing `/ask`, `Retriever`, `retrieval_backend`, `abstention`, guardrails, scope guard, glossary, hybrid or reranker config, the answer cache, or any default. That includes adopting the recommended value.
- Sweeping hybrid `vector_min_similarity`, the reranker, `k`, or any model. Hybrid or Chroma runs, downloads, network or paid calls.
- Editing anything under `knowledge/`: golden, trap, and case files, passages, catalog, glossary.
- Fixing the cooperative traps another way: new scope-guard topics, copy, or corpus changes.
- A quality claim, a release or CI gate, MRR/hit@k (`evaluation_metrics_report`), an owner command, or an owner guide.

## Job story

When I decide whether the assistant should refuse weak search matches, I want a table of what each cut-off gains on trick questions and loses on real questions, plus one safe recommendation, so I can approve a value before anyone changes the app.

## Acceptance Scenarios

### 1. The sweep writes a deterministic trade-off report

Given the reviewed `knowledge/` files, `--active-campaign 2026`, `--as-of 2026-11-07`, and `--k 5`, when `backend/scripts/calibrate_retrieval_threshold.py` runs, then it exits 0 and writes `report.json` and `table.md` under `--out` (default `build/threshold-calibration/`).

- The report scores exactly the approved golden items (49) and approved traps (26). Drafts, rejected items, and `pac_answer_eval.json` cases are never scored.
- Each threshold row holds:
  - `threshold`;
  - golden: `answered`, `right_source_found` (expected answered, answered, `source_match`), `correct_abstentions` (expected abstained, state match), `broken`;
  - traps: `correct_abstentions` (expected abstained, abstained, `abstention_reason_match` true), `unexpected_answers`, `right_source_found` for expected-answered traps, `must_not_say_hits`, `worse`;
  - the ids that changed state compared with today.
- `broken` and `worse` compare against today using `reranker_measure.compare` definitions.
- Two runs with the same inputs produce byte-identical files.
- The files contain no question or answer text, no timing, and no wall-clock date.

### 2. Today's `/ask` is the baseline, and the zero row proves it

Given a run, when the sweep starts:
- It first scores every item through the in-process `/ask` path with a plain `Bm25Backend` (environment: extractive drafting, answer cache off, reranker off, retrieval mode ignored).
- It then scores the `t = 0.0` row through the threshold ranker.
- If any `t = 0.0` row differs from the baseline row for the same id, nothing is written. The command exits 1 with `Result: the threshold sweep stopped because the zero threshold did not reproduce today's answers.`

### 3. The threshold only removes weak candidates

Given lexical candidates `(id, score)` best first, when the ranker runs at `t`:
- It returns the candidates with `score ≥ t` (all of them at `t = 0.0`), in their original order.
- It never adds, reorders, or rescores a candidate.
- When none is left, `/ask` abstains with `no_evidence`.
- Questions answered before retrieval (screen, scope guard, year check) are identical at every `t`.

### 4. The grid is fixed by the data, and the table stays short

Given the top BM25 score of each question reaching retrieval in the `t = 0.0` pass, then:
- The grid is `0.0, 0.5, 1.0, …` up to and including the first step strictly above the largest top score. With no question reaching retrieval, the grid is `[0.0]`.
- A grid over 200 rows exits 1 with `Result: the threshold sweep stopped because the score range is too wide for the fixed 0.5 step.`
- `report.json` holds every row.
- `table.md` holds the `0.0` row, every row whose counts differ from the previous row, the last row, and the recommended row.

### 5. One recommended value by a fixed rule

Given all rows, a threshold is eligible when all of these hold:
- golden `broken = 0`;
- traps `worse = 0`;
- golden `right_source_found ≥` the baseline count.

The recommendation is the eligible threshold with the most trap `correct_abstentions`, with ties going to the smallest. If no eligible threshold beats the baseline, it is `0.0` ("keep today's"). The report records the rule text, the value, and its row. Each grid row also carries one plain reason line explaining why it is not eligible (e.g. `loses 2 golden right sources`).

### 6. The three cooperative traps get a recorded outcome

Given `trap-013`, `trap-014`, and `trap-016`, the report and `table.md` show for each:
- its top score at `t = 0.0`;
- its state and reason today and at the recommended value;
- the smallest grid threshold where it abstains with an acceptable reason, or `never in the grid`, plus the golden `right_source_found` at that threshold.

If any of the three ids is not an approved trap, the command exits 1 with `Result: the threshold sweep stopped because a cooperative follow-up trap is missing or not approved.`

### 7. Read-only, offline, and the default untouched

Given any run:
- The SHA-256 of every file under `knowledge/` is unchanged.
- Nothing is written outside `--out`. An `--out` path inside `knowledge/` exits 2 before scoring.
- No socket connects: tests guard `socket.socket.connect`.
- No model or optional runtime is imported.
- Against the branch's merge-base with `main`, `knowledge/`, `backend/config/`, and `backend/app/{retrieval,retrieval_backend,ask_api,abstention,main}.py` are unchanged.
- A missing or invalid input file exits 2 with `error: <reason>`, like `evaluate_pac_answers.py`, and writes nothing (both files are written atomically, only at the end).
- On success the last stdout line is `Result: threshold sweep over G golden and T trap questions at N thresholds. Recommended minimum search score: X (today 0.0). The /ask default is unchanged.`

## Technical approach

- **`backend/app/threshold_calibration.py`** (imports no `golden_set`, is not imported by `app.main`) holds:
  - `MinScoreRanker(threshold)`, a `CandidateRanker` that records the top lexical score per call;
  - `ThresholdBackend(threshold)`, whose `attach` returns `retriever.with_ranker(...)`;
  - the pure functions `grid(top_scores)`, `row_metrics(baseline_rows, rows)` (built on `reranker_measure.compare` with empty timings, plus local counts), `recommend(rows)`, and `cooperative_outcome(...)`;
  - `run_sweep(inputs, cases_loader, out)`, which builds the app as `reranker_measure._run_pass` does: `create_app(load_config(...), retention_store=None, answer_cache=None)`, the same dependency overrides plus `get_retrieval_backend`, `reranker_measure._measurement_environment`, and `evaluate(..., row_extra=trap_set.row_extra)` per case.
  - Constants: `GRID_STEP = 0.5`, `MAX_GRID_ROWS = 200`, `COOPERATIVE_FOLLOW_UP = ("trap-013", "trap-014", "trap-016")`.
- **`backend/scripts/calibrate_retrieval_threshold.py`** takes the arguments of `evaluate_pac_answers.py` (`--catalog --passages --cases --golden --traps --active-campaign --as-of --k`) plus `--out`.
  - It loads approved golden items (`golden_set.load_golden` / `approved_cases`) and approved traps (`trap_set.load_traps` / `approved_cases`), tagging each with `case_set`.
  - It writes `report.json` (`retrieval-threshold-calibration-v1`, sorted keys, `report_only: true`, `default_changed: false`) and `table.md` atomically.
- Rules: [Safety evaluation and Abstention](../constraints/answers-and-knowledge.md). The ranker is evaluation-only, so the Reranking MUSTs for runtime rankers do not apply. Recording that is part of the constraint update.

## Expected file changes

- Create: `backend/app/threshold_calibration.py`, `backend/scripts/calibrate_retrieval_threshold.py`, `backend/tests/test_threshold_calibration.py`.
- Modify: `backend/README.md` (≤15 lines), `docs/constraints/answers-and-knowledge.md`, `docs/risks-and-open-questions.md`.
- Do not change: `backend/app/*` other than the new module, `backend/config/`, `knowledge/`, `contracts/`, `shared/`, `scripts/init.sh`, `feature_list.json` status, `PROGRESS.md`.
- Validator only: `docs/validations/retrieval_threshold_calibration.md`. It carries the recommended value, `table.md` (≤25 lines), and the cooperative-trap outcome, for owner approval at acceptance.

## Visual design impact

UI involved: no. Developer terminal and Markdown output only.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed. This is an offline evaluation script beside `evaluate_pac_answers.py`, with no new boundary or runtime surface.
- `docs/constraints/answers-and-knowledge.md`: update with one Abstention MUST. The `/ask` lexical floor (`score > 0.0`) MUST NOT change except through a separate feature that adopts a value the owner approved from a recorded `calibrate_retrieval_threshold.py` report. The sweep's ranker is evaluation-only and never composed in `/ask`.
- `docs/risks-and-open-questions.md`: update. The calibration covers the BM25 default only; hybrid `vector_min_similarity` is uncalibrated. The result rests on 75 author-reviewed items. Adopting the recommended value is pending.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, owner guide: not needed. The owner runs nothing.
- `backend/README.md`: one short section with the command and its outputs; link this spec.

## Focused verification (required)

The sweep takes about 75 questions × (2 + grid rows) in-process requests with extractive drafting. No model, no network.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests -q tests/test_threshold_calibration.py tests/test_reranker_measure.py tests/test_trap_set.py tests/test_question_glossary.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/calibrate_retrieval_threshold.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --traps knowledge/trap_set.json --active-campaign 2026 --as-of 2026-11-07 --k 5 --out build/threshold-calibration
git diff --exit-code "$(git merge-base main HEAD)" -- knowledge/ ':(exclude)knowledge/README.md' backend/app/retrieval.py backend/app/retrieval_backend.py backend/app/ask_api.py backend/app/abstention.py backend/app/main.py backend/config/hybrid_retrieval.json backend/config/bge_m3_embedding.json backend/config/bge_reranker_v2_m3.json backend/config/reranker.json
```
<!-- verify:end -->

## Appendix

See [`retrieval_threshold_calibration.appendix.md`](retrieval_threshold_calibration.appendix.md) for research, plan, evidence, and the validator checklist.
