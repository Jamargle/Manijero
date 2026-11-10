# Feature Spec: `evaluation_metrics_report`

## Source metadata

- **Feature:** `evaluation_metrics_report` — Report hit@k, MRR, faithfulness, abstention, and numeric accuracy per version (`evaluation`).
- **Depends on:** `golden_dataset_expansion`, `adversarial_trap_set`, `semantic_grounding_judge` (all accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no app screen, route, copy, `/ask`, or contract change. One developer command runs the reviewed `/ask` sample, the approved golden items, and the approved trap items through the in-process `/ask` path and writes one deterministic metrics report per version under `build/eval-reports/`. It prints one `Result:` line. There is no owner command and no owner guide.
- **Verification:** offline pytest with synthetic rows, the real repository `knowledge/` files read-only, and fake Ollama/judge transports (no live service, no real judge, no network). Then one real `--no-judge` run over `knowledge/`, checked for the expected case counts and an unchanged `knowledge/`.
- **Owner decisions, 2026-11-10 (final, do not ask again):**
  1. Report deterministic hit@1/3/5, MRR, abstention correctness, and numeric/date accuracy over the **49 approved golden items**, the **26 approved traps**, and the **reviewed 17-case `/ask` sample**. The planner checked these counts on 2026-11-10: `knowledge/pac_answer_eval.json` has 17 cases, and every item in `knowledge/golden_set.json` (49) and `knowledge/trap_set.json` (26) is `approved`.
  2. Faithfulness runs only when the pinned local `qwen2.5` judge is available. Otherwise the report says **"not judged"**, never `0`.
  3. Read-only. The command writes only under `build/eval-reports/`, never under `knowledge/`, and does not drive the live service.
  4. Report-only. No gate, no threshold change, no spend.
  5. Independent validator accept is final. No owner walkthrough.
- **Planner decisions:** ranks come from the `/ask` answer inspection, which shows what `/ask` actually ranked. Retrieval is the repository default: BM25 with extractive drafting and the glossary off unless `--glossary on` is passed. Faithfulness reuses `judge_grounding.py run` in-process. "Per version" means each report is keyed by a `version_id` that hashes its inputs and settings. Developer-only command, so [operations](../constraints/operations.md) owner rules do not apply. `scripts/init.sh` needs no change: `--feature` reads the verify block generically.

## Goal

Give `ci_quality_gates`, `colloquial_ab_evaluation`, and `nightly_evaluation` one reproducible, version-keyed baseline of retrieval, abstention, numeric, and (when available) faithfulness metrics over the owner-approved sets. The baseline makes no quality claim and enforces nothing.

## Non-goals

- Any pass/fail threshold, exit code that depends on a metric, CI gate, or change to the abstention/retrieval thresholds (`ci_quality_gates`, `retrieval_threshold_calibration`).
- Comparing two versions, hybrid/reranker/structured-index retrieval modes, or local/Gemini drafting for the non-faithfulness metrics.
- Any change to `answer_eval`, `golden_set`, `trap_set`, `grounding_judge`, `judge_grounding.py`, `/ask`, `contracts/`, `knowledge/`, `shared/`, `scripts/init.sh`, or requirements.
- An owner command, owner guide, HTTP call to a running service, model download, or a judge accuracy claim.

## Job story

When I change the corpus, glossary, prompt, or code, I want one command that tells me how often the right passage ranks first or near the top, whether traps and out-of-scope questions still abstain correctly, and whether reviewed numbers and dates still appear, keyed to exactly what I ran. Then a later gate has a trustworthy baseline, and nobody mistakes "no judge" for "zero faithfulness".

## Acceptance scenarios

### 1. One report over exactly the approved sets
Given the repository `knowledge/` files · When `backend/scripts/evaluate_metrics.py run --as-of 2026-11-10 --no-judge` runs · Then it posts each case once to an in-process app and writes `build/eval-reports/<version_id>/metrics.json` (`eval-metrics-report-v1`). The cases are the 17 reviewed cases, then the approved golden items, then the approved traps. `case_counts` is `{"reviewed":17,"golden":49,"trap":26,"total":92}`. The command prints one `Result:` line and exits `0`. Draft or rejected items never appear (proven with a synthetic golden doc holding one `draft` and one `rejected` item).

### 2. Retrieval metrics come from what `/ask` ranked
Given cases with non-empty `expected_passage_ids` · Then each row's `first_expected_rank` is the smallest `rank` in the response's `inspection.retrieval.passages` whose `passage_id` is expected. It is `null` when retrieval did not run (screened, scope-guarded, or year-routed) or no expected passage is in the top 5. `hit_at_1/3/5` is the share of those cases with rank ≤ 1/3/5. `mrr` is the mean of `1/rank`, with 0 when the rank is `null`. Values are rounded to 4 decimals, counts are also given, and every value is `null` when there are no such cases. A synthetic test with ranks `1, 2, 4, null` gives hit@1 0.25, hit@3 0.5, hit@5 0.75, and MRR 0.4375.

### 3. Abstention correctness
Given cases expected `abstained` · Then `abstention.correct` counts those whose actual status is `abstained` and, for traps, whose `abstention_reason_match` is `true`. The block also reports `expected`, `status_matched`, `wrongly_answered` (expected abstained, actual answered), and `over_abstained` (expected answered, actual abstained), plus `share = correct ÷ expected`. Clarification cases are reported in a separate `clarification` block (`expected`, `status_matched`, `ids_matched`).

### 4. Numeric and date accuracy
Given expected-`answered` cases · Then a *numeric fact* is a `critical_facts` entry containing at least one ASCII digit. It is *correct* when it appears verbatim in the answer, the same rule as `answer_eval`'s `critical_facts_match`. `numeric.facts`, `numeric.correct`, and `numeric.share` are reported, with `share` `null` when there are no facts, and `numeric.must_not_say_hits` totals the trap `must_not_say_found`. Facts without a digit are not counted.

### 5. Breakdowns
Every metric block appears `overall`, `by_case_set` (`reviewed`, `golden`, `trap`), `by_golden_question_type` (taken from the golden doc by id), and `by_trap_category`. Per-case rows hold only ids, set, type/category, expected/actual status, ranks, retrieved passage ids, match flags, and fact counts. They never hold question, answer, passage, or land text.

### 6. Faithfulness is judged or "not judged", never 0
- Given `--no-judge` · Then `faithfulness` is `{"status":"not_judged","reason":"skipped"}`.
- Given the judge runner returns an abort code (for example `ollama_unavailable`, `judge_unavailable`, `generator_unavailable`, `judge_model_unpinned`) · Then the status is `not_judged` with that code.
- Given a run that judged no sentence · Then the reason is `no_judged_sentences`. An unreadable judge report gives `judge_report_unreadable`.
- Given a successful judge run (fake Ollama and fake transports) · Then the status is `judged`, with `supported_share`, verdict counts, `by_case_set` (`reviewed`, `golden`), the judge and generator tags and digests, `drafts_from: "local_generator"`, `judge_review: "unchecked_against_human_review"`, and the judge report path `build/eval-reports/<version_id>/grounding-judge.json`.
- In every `not_judged` case, no numeric faithfulness field exists, and the `Result:` line says `faithfulness: not judged (<reason>)`.
- The judge's own output lines are captured, not printed.

### 7. Deterministic and version-keyed
- `version` holds the SHA-256 of the catalog, passages, cases, golden, and trap files, plus the glossary file's digest (or `off`). It also holds `retrieval_mode: "bm25"`, `k: 5`, `as_of`, `active_campaign`, `label` (`--label`, default `repository`), and the schema versions of `answer_eval`, `golden_set`, `trap_set`, and the report.
- `version_id` is the first 16 hex characters of the SHA-256 of the canonical `version` JSON.
- The same inputs and fakes give byte-identical files: sorted keys, no timestamp, no absolute paths. Changing any input file or `--glossary` changes `version_id`.

### 8. Read-only and isolated
During the run, the generation-provider, local/Gemini model, answer-trace, reranker, retrieval-mode, structured-index, knowledge-release, and glossary environment keys are removed, the answer cache is set off, and all of them are restored afterwards. The corpus comes only from the given files. `knowledge/` bytes are unchanged. A reports root inside `knowledge/` is refused with `unsafe_report_path`. Tests block sockets, and no request leaves the process except the fake judge transports.

### 9. Failures stop cleanly, with no gate
Given invalid or colliding inputs (`invalid_inputs`), an `/ask` non-200 response or contract violation (`ask_failed`), an unsafe reports root (`unsafe_report_path`), or any unexpected error (`internal_error`, with the traceback only in `build/eval-reports/last-error.log`) · Then the command prints one fixed `Result:` line naming the code, exits `2`, and writes no report. An earlier report is untouched. No metric value ever changes the exit code.

### 10. Result line
`Result: evaluated T questions (R reviewed, G golden, X trap) for version <id>: hit@1 a, hit@3 b, hit@5 c, MRR d over E questions with an expected passage; abstention correct A of B; numbers and dates correct N of M; faithfulness: <s supported (unchecked against human review) | not judged (<reason>)>. Report only, no gate. Report: build/eval-reports/<id>/metrics.json.` `null` values are rendered as `n/a`.

## Technical approach

- **`backend/app/eval_metrics.py`** (stdlib plus existing app modules): `SCHEMA_VERSION`, `first_expected_rank(inspection, expected)`, `numeric_facts`, `case_row(case, actual, case_set, question_type)`, `metric_block(rows)`, `summarize(rows)`, `version_block(...)`, `version_id`, `faithfulness_from_judge(exit_code, captured_stdout, report_path)`, `build_report`, `result_line`, `abort_line`, `check_reports_root`, canonical JSON, and atomic write. Only `metric_block` and `summarize` hold metric definitions.
- **Running cases:** follow `reranker_measure._run_pass`. Use `create_app(load_config(...), retention_store=None, answer_cache=None, answer_inspection=True, question_glossary=<None or loaded>)` with dependency overrides for corpus, as-of, campaign, and k=5. Call `answer_eval.evaluate(cases, client, catalog, passages, 5, row_extra=...)`, where `row_extra` merges `trap_set.row_extra` with rank extraction from `actual["inspection"]`. Loading follows `evaluate_pac_answers.py` (`load_case_document`, `golden_set.load_golden` + `approved_cases`, `trap_set.load_traps` + `approved_cases`, id-collision check).
- **Faithfulness:** the default runner calls `judge_grounding.main(["run", ...same files, --active-campaign, --as-of, --k 5, --report <root>/<version_id>/grounding-judge.json], **judge_options)` inside `contextlib.redirect_stdout`. It parses the abort code from `did not run (<code>)` and otherwise reads the judge report's `summary`. The runner is skipped entirely with `--no-judge`.
- **CLI `backend/scripts/evaluate_metrics.py run`:** defaults are the repository `knowledge/` files, `--active-campaign 2026`, a required `--as-of`, `--glossary off|on`, `--label`, and `--no-judge`. The signature is `main(argv, *, reports_root=None, judge_options=None)`, and the CLI root is fixed at `<repo>/build/eval-reports`.

## Expected file changes

- Create: `backend/app/eval_metrics.py`, `backend/scripts/evaluate_metrics.py`, `backend/tests/test_eval_metrics.py`, `backend/tests/test_evaluate_metrics_command.py`.
- Update: `backend/README.md` (≤30 lines), `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `docs/risks-and-open-questions.md`.
- Do not change: anything listed in Non-goals, `knowledge/`, or any existing test file.
- Implementer/validator only after evidence: `feature_list.json` status, `PROGRESS.md`, `docs/progress/*`, `docs/validations/evaluation_metrics_report.md`.

## Visual design impact

None. Terminal output only.

## Durable documentation impact

- `ARCHITECTURE.md`: update. Add one bullet saying the offline metrics report runs approved sets through in-process `/ask` with inspection on and writes version-keyed reports under `build/eval-reports/`. It is never on the `/ask` path.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation": update. Add one MUST: the metrics report is report-only (no metric-dependent exit), counts only reviewed or `approved` items, writes only under `build/eval-reports/`, and reports faithfulness as `not_judged` with a reason, never `0`, when the judge did not run.
- `docs/risks-and-open-questions.md`: update. Add one line: the numbers rest on author-reviewed sets, BM25 extractive answers only, and faithfulness covers local-generator drafts with an unchecked judge.
- `docs/constraints/operations.md`, `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, owner guide, `knowledge/README.md`: not needed, because this is a developer command with no owner operation and no `knowledge/` artifact.

## Focused verification

`./scripts/init.sh --feature evaluation_metrics_report` runs this block unchanged from the repository root. It needs no Ollama, network, or running service.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_eval_metrics.py tests/test_evaluate_metrics_command.py tests/test_golden_set.py tests/test_trap_set.py -q
out="$("${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_metrics.py run --as-of 2026-11-10 --no-judge)"; printf '%s\n' "$out" | tail -n 1; printf '%s\n' "$out" | grep -q '(17 reviewed, 49 golden, 26 trap)'; printf '%s\n' "$out" | grep -q 'faithfulness: not judged (skipped)'
git diff --quiet -- knowledge/
```
<!-- verify:end -->

## Appendix

See [`evaluation_metrics_report.appendix.md`](evaluation_metrics_report.appendix.md) for repository research, the ordered plan, tests by behavior, evidence to capture, and the validator checklist.
