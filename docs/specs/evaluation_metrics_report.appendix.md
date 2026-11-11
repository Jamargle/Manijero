# evaluation_metrics_report — appendix

Contract: [`evaluation_metrics_report.md`](evaluation_metrics_report.md).

## Repository research

Inspected 2026-11-10 (planner, read-only):

- `feature_list.json`: all three dependencies are `accepted`. The downstream features `colloquial_ab_evaluation` and `ci_quality_gates` depend on this one.
- `knowledge/pac_answer_eval.json`: 17 cases (`expected_status` count) with `author_only` review. This is the reviewed `/ask` sample. Some cases are `needs_land_clarification`.
- `knowledge/golden_set.json`: 49 items, 49 `"review_state": "approved"`. `knowledge/trap_set.json`: 26 items, 26 approved.
- `backend/app/answer_eval.py`: `load_case_document`, plus `evaluate(cases, client, catalog, passages, k, coverage=, row_extra=)`. It posts `/ask`, validates against `AskResponse`, and builds rows with `expected_state_match`, `source_match`, `passage_match`, `critical_facts_match` (verbatim substring), and `clarification_ids_match`. This is the case runner to reuse.
- `backend/app/golden_set.py`: `load_golden`, and `approved_cases`, which drops `question_type`. Map it back by id from the doc. `VERSION = "golden-set-v1"`.
- `backend/app/trap_set.py`: `load_traps`, `approved_cases` (keeps `category`, `acceptable_abstention_reasons`, `must_not_say`), `row_extra` (`abstention_reason_match`, `must_not_say_found`), `CATEGORIES`. `VERSION = "trap-set-v1"`.
- `backend/scripts/evaluate_pac_answers.py`: the merge order and id-collision checks for `--golden` and `--traps`, and its dependency overrides. Copy the loading, not the printing.
- `backend/app/reranker_measure.py` `_measurement_environment` and `_run_pass`: the pattern for an env-isolated in-process `create_app` with overrides. It builds the app with `answer_cache=None` and `retention_store=None`.
- `backend/app/main.py` `create_app(..., answer_inspection=, answer_cache=, question_glossary=)`: passing `answer_inspection=True` enables inspection regardless of profile.
- `backend/app/answer_inspection.py` `build_inspection`/`_retrieval`: `retrieval.passages[]` with `rank` and `passage_id` (top k, sorted). `retrieval` is `None` when no search ran. Inspection is omitted on cache hits, so the cache must be off.
- `backend/app/ask_api.py`: `AskResponse.inspection` is optional (closed model). The screen and year check return before retrieval. The glossary is applied via `with_query_expansion` only when it is passed in.
- `backend/app/question_glossary.py`: `load_question_glossary(environ, path)` and `DEFAULT_PATH = backend/config/question_glossary.json`. Expansion is off unless the setting is on.
- `backend/scripts/evaluate_retrieval.py` and `manage_vector_store.py` `_retrieval_summary`: existing hit@k/MRR conventions (MRR uses 0 for a miss, first expected rank). Keep the same semantics.
- `backend/scripts/judge_grounding.py`: `main(argv, *, opener, generator_transport, judge_transport, ollama, clock, error_log)`. `run` aborts with `Result: ... did not run (<code>)` and exit 2. It covers the case sets `reviewed` and `golden` only and writes via `check_report_path` (refuses `knowledge/`).
- `backend/app/grounding_judge.py`: `summarize` blocks (`overall.supported_share`, `verdicts`, `by_case_set`), `JUDGE_REVIEW`, and `canonical_json` / `write_report` (sorted keys, indent 2, atomic).
- `backend/tests/test_grounding_judge.py`: the socket-blocking and fake Ollama/transport patterns to mirror.
- `scripts/init.sh` `run_feature`: extracts the verify block with awk and runs it with `bash -euo pipefail`. No per-feature entry is needed (only `backend_answer_evaluation` has one).
- `.gitignore`: `build/` is ignored, so reports are never committed.
- `docs/constraints/operations.md`: the owner rules apply to owner operations. This is a developer command, like `evaluate_retrieval.py`.
- Not inspected: hybrid/reranker internals (out of scope), Android/Desktop code (untouched).

## Implementation plan

1. `eval_metrics.py`: constants (`SCHEMA_VERSION = "eval-metrics-report-v1"`, `K = 5`, `CASE_SETS`, the `NOT_JUDGED` reasons, failure texts).
2. Pure helpers: `first_expected_rank`, `numeric_facts` (regex `[0-9]`), `case_row` (no text fields), `metric_block`, and `summarize` (overall, by set, by golden type, by trap category).
3. `version_block` and `version_id`: file SHA-256s, glossary digest or `off`, settings, schema versions, label (`^[A-Za-z0-9._-]{1,40}$`).
4. `faithfulness_from_judge`, mapping exit code, captured stdout, and report to `judged` or `not_judged`/reason. It never yields 0 without judged sentences.
5. `build_report`, `result_line` (4-decimal values, `n/a` for null), `abort_line`, `check_reports_root` (refuse inside `knowledge/` or the input files), atomic canonical write.
6. `evaluate_metrics.py`: argparse, input loading (`invalid_inputs`), an env-isolation context manager, and the in-process run with `row_extra` merging trap fields and ranks (`ask_failed` on `AnswerEvalError`).
7. Default judge runner: in-process `judge_grounding.main` with `redirect_stdout`, skipped under `--no-judge`. Import the sibling script via `importlib` from its path.
8. Assemble, write `<root>/<version_id>/metrics.json`, print the result line, exit 0. Unexpected errors go to `<root>/last-error.log` and exit 2.
9. Tests (below), then the real `--no-judge` run. Record its numbers.
10. Durable docs and the `backend/README.md` section (≤30 lines: command, flags, metric definitions linked to the contract, report-only).

## Tests to write (named by behavior)

`test_eval_metrics.py` (synthetic rows, no app):
- `test_hit_at_k_and_mrr_from_ranks_1_2_4_none`
- `test_metrics_null_when_no_expected_passage_cases`
- `test_rank_null_when_inspection_has_no_retrieval`
- `test_abstention_correct_needs_trap_reason_match`
- `test_over_abstained_and_wrongly_answered_counted`
- `test_numeric_facts_only_digit_facts_count_verbatim`
- `test_breakdowns_by_set_type_and_category`
- `test_rows_carry_no_question_answer_or_passage_text`
- `test_version_id_changes_with_any_input_digest_glossary_or_label`
- `test_faithfulness_not_judged_reasons_never_zero` (skipped, abort code, no sentences, unreadable report)
- `test_faithfulness_judged_carries_unchecked_label_and_pins`
- `test_result_line_shapes_judged_and_not_judged`
- `test_reports_root_inside_knowledge_refused`

`test_evaluate_metrics_command.py` (real `knowledge/` read-only, sockets blocked):
- `test_real_sets_counts_17_49_26_and_report_written`
- `test_drafts_and_rejected_items_never_counted` (synthetic golden/trap copies in `tmp_path`)
- `test_two_runs_byte_identical_and_knowledge_unchanged`
- `test_environment_keys_removed_then_restored`
- `test_invalid_inputs_exit_2_nothing_written_old_report_kept`
- `test_ask_failure_exit_2`
- `test_internal_error_traceback_only_in_log`
- `test_judge_unavailable_fake_ollama_reports_not_judged`
- `test_judge_available_fake_transports_reports_judged` (fake ollama tags with both pins, fake generator and judge transports, as in `test_grounding_judge.py`)
- `test_judge_stdout_not_printed`

## Evidence to capture

- The focused verify block output (`./scripts/init.sh --feature evaluation_metrics_report`): pytest counts and the final `Result:` line.
- The real `--no-judge` run: `version_id` and the values of hit@1/3/5, MRR, abstention A of B, numbers/dates N of M. Report-only, labelled as a baseline, not a quality claim.
- `git diff --stat` showing no `knowledge/`, `contracts/`, `shared/`, `scripts/init.sh`, or requirements change.
- Agents do not run the real judge. A judged run is optional, owner-side, and not required for acceptance (decision 5).

## Feature evidence

<!-- Implementer appends dated entries here: commands and one-line results only. -->

### 2026-11-10 — implementer

- `./scripts/init.sh --feature evaluation_metrics_report` — focused tier passed: 126 pytest cases; real run exit 0 with `Result: evaluated 92 questions (17 reviewed, 49 golden, 26 trap)` and `faithfulness: not judged (skipped)`; `knowledge/` unchanged.
- `./scripts/init.sh --fast` — all 10 offline checks passed: backend-tests 3401 passed, 9 skipped; harness-tests 22 passed; contract examples valid.
- `tests/test_eval_metrics.py` + `tests/test_evaluate_metrics_command.py` — 25 passed with sockets blocked, real `knowledge/` read-only, fakes for Ollama and the judge transports.
- Baseline `--no-judge`, version `3371d43c659ae38e`: hit@1 0.7321, hit@3 0.8214, hit@5 0.8214, MRR 0.7768 over 56 cases with an expected passage; abstention 34/36; numbers and dates 27/34; faithfulness not judged. Report-only baseline, not a quality claim.
- Data note: `knowledge/pac_answer_eval.json` holds 12 answered and 5 abstained cases and no `needs_land_clarification` case today, so the clarification block reports zeros (the repository-research line says some cases are clarification).
- `git diff --stat` against the base touches only the files the spec lists; no `knowledge/`, `contracts/`, `shared/`, `scripts/init.sh`, or requirements change.
- No real judge run was made; the judged path is proven with fake transports only.

## Validator checklist

- [ ] Case counts are 17/49/26 from the real files. Drafts and rejected items are excluded (test).
- [ ] hit@k and MRR use inspection ranks with the contract's definitions. The synthetic example gives 0.25/0.5/0.75/0.4375.
- [ ] Abstention, clarification, and numeric blocks match scenarios 3–4. Trap reason matching is required for trap correctness.
- [ ] Faithfulness is never a number unless sentences were judged. Every not-judged path names a reason. The judge's stdout is suppressed.
- [ ] `version_id` is deterministic and input-sensitive. Two runs are byte-identical. No timestamp or absolute path appears.
- [ ] Writes only under the reports root, and `knowledge/` is unchanged. No socket is opened in tests. No live service is driven.
- [ ] No metric-dependent exit code, threshold, or gate. Failure exits are 2 with one fixed `Result:` line.
- [ ] No change to `answer_eval`, `golden_set`, `trap_set`, `grounding_judge`, `judge_grounding.py`, `/ask`, `scripts/init.sh`, `contracts/`, or requirements.
- [ ] Durable docs updated as listed. `backend/README.md` addition is ≤30 lines.
- [ ] The focused block passes unchanged via `./scripts/init.sh --feature evaluation_metrics_report`.
