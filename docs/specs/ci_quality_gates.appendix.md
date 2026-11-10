# ci_quality_gates — appendix

Contract: [`ci_quality_gates.md`](ci_quality_gates.md).

## Repository research

Inspected 2026-11-10 (planner, read-only):

- `AGENTS.md` and `PROGRESS.md` "Start and verify" — tier names, the `set -euo pipefail` script, and the current "metrics stay report-only" limitation the gate must qualify.
- `feature_list.json` — `ci_quality_gates` depends on accepted `evaluation_metrics_report`; `status: not_started`.
- `docs/specs/evaluation_metrics_report.md`, its appendix and [acceptance record](../validations/evaluation_metrics_report.md) — accepted report, metric definitions, `--no-judge` baseline, and its explicit "no gate" non-goal.
- `backend/app/eval_metrics.py` — `metric_block`, `case_row`, `summarize`, `_sha256`, `canonical_json`; the only metric definitions; keep unchanged.
- `backend/scripts/evaluate_metrics.py` — `_isolated_environment`, `_run_cases`, and the in-process app setup the gate mirrors; it loads golden and trap, so the gate does not call it.
- `backend/scripts/evaluate_retrieval.py` — `load_eval_questions`, `evaluate`, per-question `ranks` and `reciprocal_rank`; 7 fixture questions.
- `backend/scripts/evaluate_abstention.py` — `load_eval_lines`, `evaluate_line`, `Decision.matched_expectation`; 10 fixture lines covering answered and abstained outcomes.
- `backend/tests/fixtures/retrieval/*`, `backend/tests/fixtures/abstention/*` — deterministic synthetic corpora and question files.
- `knowledge/pac_answer_eval.json` — 17 author-reviewed cases: 12 `answered` each with one expected passage, 5 expected `abstained`, no clarification case.
- `knowledge/source_catalog.json`, `knowledge/passages.json` — the corpus the reviewed sample exercises; deliberately not digest-pinned by the gate.
- `.github/workflows/gate.yml` — `changes` classifies docs-only; `fast` runs `--fast`; `full` runs `--verify`. No edit is needed and none is allowed.
- `scripts/init.sh` — `run_offline_checks` job list, `run_fast`, `run_feature`, `pytest_python`/`run_python`, `AS_OF`, and the `--verify|--full)` branch.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation" — the report-only MUST and the "no metric is a gate until a measured baseline is reviewed" rule.
- `docs/constraints/operations.md` — owner-operability rules; developer-only commands such as `evaluate_retrieval.py` are outside them.
- `docs/specs/screenshot_regression_tests.md` — the accepted verify/record precedent: verification is read-only, recording is explicit, a human reviews the baseline.
- `backend/tests/test_evaluate_metrics_command.py` — socket blocking, real-file read-only, and environment-restore test patterns.
- `docs/risks-and-open-questions.md` — the "metrics baseline can be mistaken for measured quality" row to qualify.
- Not inspected: Gradle/Android/Desktop code, hybrid/reranker internals, judge internals (untouched and never run).

### Existing patterns to follow

- Developer commands print one fixed `Result:` line, name a failure code, and exit `2` for unusable input and `1` for a detected miss or regression (e.g. `evaluate_retrieval.py` `--fail-on-miss`).
- Baselines and reviews already work as commits a person approves (screenshot goldens) and as review blocks that fail closed at load (land-safety critical cases).
- Metric definitions live only in `eval_metrics`; scripts import each other via `importlib` (as `evaluate_metrics` imports `judge_grounding`) instead of parsing stdout.
- Offline checks are synthetic, read-only, socket-free, and concurrent; `build/` is gitignored.

### Current gaps

- No comparison code, no gate step, and no reviewed baseline file exist.
- The accepted 92-case report cannot gate: it mixes report-only sets, loads golden/trap, and has no staleness or review guard.
- A local `--verify` may lack the backend environment; the gate must name `--setup-python` instead of failing obscurely.

## Implementation plan

1. `backend/app/quality_gate.py`: schema/settings constants, review and digest validation, `compare`, fixed drop ordering, `result_line`/`not_enforced_line`, canonical JSON; no app imports.
2. Same module: `rewrite_baseline` logic for `record` (review validation, drop guard, canonical atomic write) so it is unit-testable; `today` injected.
3. `backend/scripts/check_quality_gate.py`: import the two evaluator scripts with `importlib`; build the fixture metric blocks through `eval_metrics.metric_block`.
4. Reviewed group: mirror `evaluate_metrics._run_cases` (inspection on, cache off, corpus/as-of/campaign/k overrides, provider keys removed and restored) over `knowledge/pac_answer_eval.json` only.
5. `check`: load and validate the baseline, verify digests/settings, compare, print one line, exit `0`/`1`/`2`; catch everything as `internal_error`; write nothing (`--baseline`/`baseline_path` exist for tests only).
6. `record`: recompute, list each change as `group metric old -> new`, print one `Result:` line, write the canonical baseline; refuse empty reviewer/reason; refuse a drop without `--accept-regression`; create the file when absent.
7. `scripts/init.sh`: `run_quality_gate()` (interpreter resolution like `--backend-tests`, `--setup-python` hint), called once in `--verify` after `run_fast` and before the Gradle tier; update the one-line `--verify` text.
8. Generate the committed baseline with `record --reviewer owner --reviewed-on 2026-11-10 --reason "<the owner rule>"`; record the measured numbers in evidence.
9. Durable docs and `backend/README.md` (≤30 lines: check, record, review rule).
10. Tests, then `--feature`, `--fast`, and one `--verify` with its timing.

## Verification plan

- `./scripts/init.sh --feature ci_quality_gates` — focused tests pass; one pass line; fixtures, `knowledge/`, and baseline unchanged.
- `./scripts/init.sh --fast` — the 10 offline checks still pass and no quality-gate line appears.
- `./scripts/init.sh --verify` — the gate line appears once before the builds and `Full tier passed` follows; record the added wall time (target ≤10 s).
- A temp baseline with raised counts gives exit `1` and the expected `fell from ... to ...` text; a temp stale/unreviewed baseline exits `2` without comparing.
- `git diff --stat` — only the listed files; `.github/workflows/gate.yml` and `knowledge/` untouched.
- E2E: not applicable. There is no user-visible flow; command tests plus the real `--verify` run cover the behavior.

## Tests to write (named by behavior)

`backend/tests/test_quality_gate.py` (pure, synthetic baselines):
- `test_baseline_requires_complete_review`
- `test_baseline_rejects_unknown_keys_and_bad_types`
- `test_stale_on_digest_settings_as_of_or_campaign`
- `test_each_hit_at_k_drop_blocks`
- `test_abstention_drop_blocks`
- `test_any_mrr_fall_blocks`
- `test_improvement_passes_and_lists_no_drop`
- `test_drops_are_named_in_fixed_order`
- `test_result_and_not_enforced_lines_are_single_and_text_free`
- `test_zero_question_group_renders_na_and_enforces_nothing`
- `test_record_refuses_without_reviewer_or_reason`
- `test_record_refuses_regression_without_accept_flag`
- `test_record_writes_canonical_sorted_baseline`

`backend/tests/test_check_quality_gate_command.py` (real fixtures/sample, sockets blocked):
- `test_real_check_passes_with_one_line_and_writes_nothing`
- `test_knowledge_fixtures_and_baseline_are_byte_identical`
- `test_stale_baseline_exit_2_without_comparison`
- `test_regression_exit_1_names_old_and_new`
- `test_unreviewed_baseline_exit_2`
- `test_environment_keys_removed_then_restored`
- `test_golden_trap_and_judge_files_are_not_read`
- `test_record_creates_first_baseline_and_reports_deltas`
- `test_internal_error_prints_one_fixed_line`

## Evidence to capture

- The six blocking counts and both MRRs the baseline recorded, with reviewer and date; the exact pass line.
- The `--verify` run: gate line, added seconds, `Full tier passed`; and a `--fast` run with no gate line.
- One temp-baseline failure line with its exit code; one `record` refusal and one recorded change line.
- Hash comparison before/after for `knowledge/`, fixtures, and the baseline; `git status` clean after runs.

## Feature evidence

<!-- Implementer appends dated entries here: commands and one-line results only. -->

### 2026-11-10 — implementer

- Baseline `backend/config/quality_gate_baseline.json` recorded by `record --reviewer "Jose" --reviewed-on 2026-11-10 --reason "initial measured fixture baseline approved with the batch 2 owner decisions (2026-11-10)"`: fixtures 6/7 hit@1, 6/7 hit@3, 6/7 hit@5, MRR 0.8571; fixtures abstention 10/10; reviewed sample 9/12 hit@1, 11/12 hit@3, 11/12 hit@5, MRR 0.8333; reviewed sample abstention 5/5.
- `./scripts/init.sh --feature ci_quality_gates`: 24 passed; exactly one pass `Result:` line; fixtures, `knowledge/`, and the baseline unchanged.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 3424 passed, 9 skipped); no `Result: quality gate` line.
- `./scripts/init.sh --verify`: quality gate ran once after `--fast` and before the builds, printed the pass line, then `Full tier passed`; 74.9 s total, gate ~0.2 s.
- Temp baseline with reviewed hit@1 raised to 10/12: `check --baseline ...` exit 1, `Result: quality gate failed: reviewed sample hit@1 fell from 10/12 to 9/12. ...`.
- Temp baseline with a changed `as_of` and one with no review block: exit 2 `baseline_stale` / `baseline_unreviewed`, no comparison (also covered by command tests).
- `record` with no reviewer: exit 2 `Result: baseline not recorded: the reviewer must be named.`; accepted temp change: `reviewed sample hit@1: 10/12 -> 9/12`, `reviewed sample MRR: 0.8433 -> 0.8333`, `Result: baseline recorded: 2 metrics changed...`, exit 0.
- Command tests block sockets, assert two runs print the same line, confirm byte-identical `knowledge/`, fixtures, and baseline, restored env keys, and that no golden/trap/judge file is read.

## Validator checklist

- [ ] Scope matches the contract; `.github/workflows/gate.yml`, branch protection, and every non-goal file are untouched.
- [ ] Scenarios 1–7 pass with evidence: pass line, each blocked metric (hit@1/3/5, abstention, any MRR fall), improvement, fail-closed baseline, record, read-only.
- [ ] The baseline pins settings and the six fixture files plus the reviewed sample; a changed case set or setting is `baseline_stale`, not silently compared.
- [ ] Only the reviewed baseline authorizes gating; checks never write; `record` is explicit and never called by `check` or `--verify`.
- [ ] The gate reads no golden, trap, numeric, or judge data and opens no socket, service, model, or spend.
- [ ] `--verify` runs it once before the builds and fails the tier on `1`/`2`; `--fast` and docs-only PRs do not run it; timing recorded.
- [ ] One plain `Result:` line on every path, with no question, answer, passage, or path text.
- [ ] Durable docs updated as listed; `backend/README.md` addition is ≤30 lines; the report-only limitation is qualified at acceptance.
- [ ] `feature_list.json` and `PROGRESS.md` updated only after acceptance; the focused block runs unchanged via `./scripts/init.sh --feature ci_quality_gates`.
