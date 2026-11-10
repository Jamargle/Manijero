# Acceptance record: `evaluation_metrics_report`

- **Verdict:** accept (independent validator, 2026-11-10). Spec: [evaluation_metrics_report.md](../specs/evaluation_metrics_report.md); appendix evidence: [appendix](../specs/evaluation_metrics_report.appendix.md) "Feature evidence". Owner decision 5 makes validator accept final; no owner walkthrough.
- **Feature:** developer-only, report-only metrics report over the 17 reviewed `/ask` cases, the 49 approved golden items, and the 26 approved trap items; writes one version-keyed `build/eval-reports/<version_id>/metrics.json`; no gate, no threshold, no `/ask` or contract change.

## Checks rerun

- `./scripts/init.sh --feature evaluation_metrics_report` — 126 passed in 6.1 s; real run exit 0, one `Result:` line, `(17 reviewed, 49 golden, 26 trap)`, `faithfulness: not judged (skipped)`, version `3371d43c659ae38e`.
- `./scripts/init.sh --fast` — all 10 offline checks passed (backend-tests 3401 passed, 9 skipped; harness 22 passed; contract examples valid).
- Independent recomputation (own script, not the feature code): replayed the 92 cases through the in-process `/ask` and recomputed every metric from `knowledge/`; matched the report exactly — hit@1 0.7321, hit@3 0.8214, hit@5 0.8214, MRR 0.7768 over 56 cases; abstention 34/36 (2 wrongly answered, 2 over-abstained); numbers/dates 27/34; `must_not_say_hits` 0; clarification 0/0/0.
- Hand-built fixture for `metric_block` ranks 1, 2, 4, null gave 0.25 / 0.5 / 0.75 / 0.4375 and hit counts 1/2/3; numeric helper counted only digit facts found verbatim; a trap expected abstained with the wrong reason stayed incorrect.
- Version identity: `sha256(canonical version JSON)[:16]` recomputed from the written report equals `3371d43c659ae38e`; the same id reproduced on a second run; unit test covers input/glossary/label sensitivity.
- Data check: `knowledge/golden_set.json` 49 items and `trap_set.json` 26 items, every item `review_state` and `decision` `approved`; `pac_answer_eval.json` 17 cases (12 `answered`, 5 `abstained`, no clarification case today); report `case_counts` 17/49/26/92, retrieval denominator 56 (37 golden + 12 reviewed + 7 trap), abstention denominator 36 (12 golden + 5 reviewed + 19 trap), numeric denominator 34 digit facts (10 reviewed + 18 golden + 6 trap).
- `git diff 91adc1f -- knowledge/ contracts/ shared/ scripts/init.sh backend/requirements.txt` — empty; `build/` (hence `build/eval-reports/`) is gitignored; report contains no absolute path; `git status` clean after runs.

## Acceptance scenarios

1. Approved sets only — pass: order reviewed → golden → trap, counts 17/49/26/92, real run writes `<version_id>/metrics.json`; synthetic draft/rejected golden items are excluded (test `test_drafts_and_rejected_items_never_counted`, 47/90).
2. Retrieval from `/ask` ranks — pass: smallest expected rank in `inspection.retrieval.passages`, null when retrieval absent/miss; 4-decimal values plus counts; synthetic 1/2/4/null example matches the spec.
3. Abstention and clarification — pass: trap correctness requires an acceptable `abstention_reason_match`; `expected`, `status_matched`, `wrongly_answered`, `over_abstained`, `share` present; separate clarification block.
4. Numeric/date accuracy — pass: digit-only `critical_facts`, verbatim per fact (same predicate as `answer_eval`'s `fact not in answer`), share null with no facts, `must_not_say_hits` totals trap output.
5. Breakdowns and row shape — pass: every block has overall, by case set, by golden question type, by trap category; rows are whitelisted to ids/status/flags/counts, no question, answer, passage, or land text (test asserts this, and the written report has no such text).
6. Faithfulness — pass: `--no-judge` → `{"status":"not_judged","reason":"skipped"}`; abort codes parse from the judge's fixed line; no judged sentences → `no_judged_sentences`; unreadable/missing report → `judge_report_unreadable`; judged path (fake Ollama and fake transports) carries `supported_share`, verdicts, reviewed/golden blocks, judge/generator model+digest, `drafts_from`, `judge_review`, report path; no numeric field when not judged; judge stdout captured. Judge report keys verified against `grounding_judge.build_report`.
7. Deterministic and version-keyed — pass: five file digests, glossary digest or `off`, `bm25`, `k: 5`, `as_of`, campaign, label, four schema versions; canonical sorted JSON, no timestamp or absolute path; two runs byte-identical; no test needs Ollama.
8. Read-only and isolated — pass: answer-affecting env keys removed and restored (sentinel test), cache forced off, corpus injected from the given files, `knowledge/` hashes unchanged, sockets blocked in tests, report root inside `knowledge/` refused, no live service.
9. Failures stop cleanly — pass: `invalid_inputs`, `ask_failed`, `unsafe_report_path`, `internal_error` each print one fixed `Result:` line, exit 2, write no metrics report, traceback only in `last-error.log`, earlier report untouched; no metric affects the exit code.
10. Result line — pass: matches the template, `n/a` for null, prints exactly one line and no judge output.

## Non-goals and documentation

- No threshold, gate, metric-dependent exit, or change to abstention/retrieval thresholds; no version comparison, hybrid/reranker/structured-index mode, or Gemini drafting in the report; no change to `answer_eval`, `golden_set`, `trap_set`, `grounding_judge`, `judge_grounding.py`, `/ask`, `contracts/`, `knowledge/`, `shared/`, `scripts/init.sh`, or requirements; no owner command, owner guide, HTTP call, model download, or judge accuracy claim.
- Durable docs match the spec: `ARCHITECTURE.md` bullet; `docs/constraints/answers-and-knowledge.md` "Safety evaluation" MUST; `docs/risks-and-open-questions.md` author-reviewed/BM25/unchecked-judge risk line; `backend/README.md` section is 30 added lines. Report carries `report_only: true`, four limits, and "Report only, no gate."

## Residual risk

- Judged faithfulness is proven only with fakes; no real judge run was made (owner decision 5 and appendix "Agents do not run the real judge"). A real run can only change faithfulness, never the other metrics.
- `clarification` is 0/0/0 because today's 17-case sample has no `needs_land_clarification` case; the block is exercised only by synthetic tests.
- CLI-level argument errors (missing/invalid `--as-of`) produce argparse usage text rather than the fixed `Result:` line; the spec's `invalid_inputs` case covers file loading only.
- The abort text says "Nothing was written"; a judge report already written before a later internal write error would remain. Error-path wording only.
- `by_golden_question_type` derives its keys from approved rows, so a type present only in unapproved items would not appear.
- The baseline rests on author-reviewed sets with BM25 extractive answers, as recorded in `docs/risks-and-open-questions.md`; it is not a quality claim and no gate reads it.
