# colloquial_ab_evaluation — appendix

Contract: [`colloquial_ab_evaluation.md`](colloquial_ab_evaluation.md).

## Repository research

Inspected 2026-11-10 on branch `feature/colloquial_ab_evaluation` (base f7d851c, accepted `evaluation_metrics_report`):

- `feature_list.json` — `colloquial_ab_evaluation` is `not_started`; `question_rewriting`, `golden_dataset_expansion`, and `evaluation_metrics_report` are all `accepted`.
- `knowledge/golden_set.json` — 49 items, all `approved`: deadline 11, procedure 9, out_of_scope 9, colloquial 8, eligibility_caveat 6, land_dependent 6; 37 answered and 12 deliberately abstained (10 declared omissions + 2 reviewed-case bases).
- `knowledge/trap_set.json` — 26 approved traps in five categories; `row_extra` supplies `abstention_reason_match` and `must_not_say_found`.
- `knowledge/pac_answer_eval.json` — 17 reviewed `/ask` cases; the duplicate check reads it, nothing is scored from it here.
- `backend/app/eval_metrics.py` — `metric_block` (hit@1/3/5, MRR), `case_row`, `version_block`/`version_id`, `check_reports_root`, canonical atomic write. Reuse, do not re-implement metrics.
- `backend/scripts/evaluate_metrics.py` — the exact in-process pattern: `create_app(..., answer_inspection=True, answer_cache=None, question_glossary=...)`, dependency overrides for corpus/as-of/campaign/k, `answer_eval.evaluate`, and `_isolated_environment` (clears every answer-affecting `MANIJERO_*` key, cache off). Copy it.
- `backend/app/answer_eval.py` — `evaluate(cases, client, catalog, passages, k, row_extra=...)` posts `/ask` per case and validates the response against `AskResponse`.
- `backend/app/question_glossary.py` — `load_question_glossary`, immutable `QuestionGlossary.expand` (whole-token, longest-first, ≤ 4 appended, no term logged), `identity()`, and `pair_failures` official-term rules (1–8 tokens, ≤ 80 chars, single line, no digit/URL) to mirror for model terms.
- `backend/config/question_glossary.json` — 15 entries, 14 approved, 1 rejected; the approved pairs are the vocabulary a variant can reuse so arm B actually fires.
- `backend/app/question_glossary_review.py` + `backend/scripts/glossary_review.py` — readable list, atomic `decide`, `golden_set.valid_name`, fixed bilingual `Result:` lines, `build/<topic>/last-error.log`. Mirror for the variant review.
- `backend/app/golden_set.py` — `load_golden`, `approved_cases` (expectation → v2 case), `valid_name`, `write_atomically`; the strict quote/route discipline this feature copies.
- `backend/app/local_generation.py` — `load_local_model_record`, `evaluate_local_model_record`, `OllamaTransport` (loopback `127.0.0.1:11434`, digest check via `/api/tags`, `temperature 0`, `seed 0`, schema-constrained JSON, fixed error codes). The only model seam needed.
- `backend/config/local_generation_model.json` — pinned `mistral-small3.2:24b-instruct-2506-q4_K_M`, Apache-2.0, digest, timeout 10 s, ≤ 400 output tokens. Already downloaded by `local_generation_provider`; no new pin or spend.
- `backend/container/Dockerfile` — copies `backend/config/` wholesale, so the variant file ships inert inside the image; no module reads it at import and the service never opens it. Small and harmless, noted so the validator does not treat it as a new runtime input.
- `backend/app/ask_api.py` — the glossary reaches retrieval only through `Retriever.with_query_expansion(glossary.expand)`; nothing else reads it. A duck-typed object exposing `expand` is therefore a zero-code-change arm C.
- `backend/app/reranker_measure.py` — `_trap_got_worse`, `compare`, `verdict`, and a one-line plain result: the model for reporting a rule without changing a default.
- `scripts/init.sh` — `--glossary-review`/`--glossary-decide` block and help lines; `run_feature` executes the verify block unchanged.
- `.gitignore` — `build/` is ignored, so reports, review lists, and the rewrite cache are never committed.
- `docs/constraints/operations.md` — owner commands need one named command and a guide; line 17 requires an acceptance walkthrough, replaced here by the automated command walkthrough per owner decision 5.
- Not inspected: hybrid/reranker/structured-index internals, Android/Desktop, `contracts/` (untouched).

### Existing patterns to follow

- Review queue discipline: agent drafts, named owner decision, approved-only consumers, atomic write, pinned `Result:` lines (golden set, trap set, glossary).
- Evaluation discipline: approved sets through the in-process `/ask` path with inspection on and cache off; version-keyed canonical JSON outside `knowledge/`; report-only (metrics report).
- Owner-rule discipline: plain counts, a verdict sentence, and no automatic default change (reranker).
- Fail closed: fixed reason codes, never a term, question, answer, or passage text in a log or line.

### Current gaps

- No variant set, no A/B command, no model-term cache; the glossary's effect is unmeasured (known limitation).
- The variant questions do not exist yet; the implementer drafts all 49 offline, then the owner decides.
- No fixture corpus for a three-arm run or a fake rewriter; both must be added.

## Implementation plan

1. Draft `backend/config/colloquial_variants.json` (`colloquial-variants-v1`): one `coll-0NN` per `golden-0NN`, plain Spanish, 1–4 new grower expressions where the meaning allows (abstained variants only need a different wording), no new number/date/legal fact, land context untouched, all `draft`; bind `golden_sha256`.
2. `colloquial_ab.py`: constants, strict variant loader, `variant_failures` (shape, digit, guardrail, scope, duplicate, term rules), `check_variants` (coverage, parents approved, digest), `readable_variants`, `decide` (valid-name, re-check, atomic).
3. `approved_cases`: derive the parent's expectation/land/type/area/segment, emit v2 cases with the variant id, `parent_id`, and `case_set = "colloquial"`.
4. `GlossaryPlusModel`: wrap the loaded glossary; `expand` appends ≤ 4 validated, deduped model terms, ≤ 8 total; `term_failures` mirrors the official-side rules.
5. `prepare_rewrites`: screen each approved case, ask the pinned loopback model for `{"terms": [...]}`, validate, and write the cache (ids + accepted terms + status only) under `build/colloquial-ab/rewrites/`; key = digest of every scored `(id, question)` in fixed order + model tag/digest; no hosted call, no new model.
6. `run_arms`: one app per arm (`None`, glossary, glossary+model), same corpus/as-of/campaign/k/extractive/cache-off/inspection, same tagged case order, env isolated; `answer_eval.evaluate` per arm.
7. `trap_worse` and `adoption`: fixed-denominator hit@5, trap regressions, incomplete-review and no-effect verdicts, arm C vs B as information.
8. `version_block`/`version_id`, canonical `report.json` (rows without text, `report_only: true`, limits), one `Result:` line, abort lines, output-root refusal, atomic write, `last-error.log`.
9. `backend/scripts/colloquial_ab.py`: `list`, `decide`, `check`, `prepare`, `run`; `main(argv, *, reports_root=None, rewriter=None, today=None)` for fakes.
10. `scripts/init.sh`: `--colloquial-review`, `--colloquial-decide`, two help lines.
11. Tests (below), then real `check` and the full backend suite.
12. Real `prepare` + `run` on the Mac; record counts; rerun `run` and compare bytes; `git diff -- knowledge/`; append evidence; docs; no default change.
13. Owner review: list, approve/reject all 49 (a content decision, not a walkthrough), commit decisions; validator reruns `check`/`run` and recomputes.

## Tests to write (named by behavior)

`test_colloquial_ab.py`:
- `test_one_variant_per_approved_parent_and_no_orphans`
- `test_variant_failures_length_digit_guardrail_scope_terms_duplicate`
- `test_variant_derives_parent_expectation_and_land_context`
- `test_approved_cases_are_the_only_ones_and_poison_draft_is_not_read`
- `test_decide_is_atomic_repeatable_and_bad_input_records_nothing`
- `test_arm_a_is_none_arm_b_glossary_arm_c_appends_and_dedupes`
- `test_model_term_rules_and_screened_skip_and_invalid_output`
- `test_prepare_cache_key_changes_with_model_or_case_set_digest_and_stores_no_text`
- `test_run_refuses_missing_or_stale_cache_and_no_approved_variants`
- `test_three_arms_differ_only_in_query_expansion` (fake app records every setting)
- `test_trap_worse_definitions_and_fixed_denominator_hit_at_5`
- `test_adoption_improve_no_improve_trap_worse_incomplete_no_effect`
- `test_report_is_deterministic_version_keyed_and_has_no_text_rows`
- `test_output_root_inside_knowledge_refused_and_abort_lines_exit_two`

`test_colloquial_ab_command.py` (sockets blocked, fake rewriter/transport, real `knowledge/` read-only):
- `test_check_passes_on_repository_variants_and_names_failures_by_id`
- `test_list_waiting_pinned_line_and_full_list_file` (owner decision 5 replacement)
- `test_decide_records_replaces_and_records_nothing_on_bad_input`
- `test_missing_backend_environment_line_and_init_wiring`
- `test_run_writes_one_report_and_one_result_line_without_network`
- `test_knowledge_bytes_and_glossary_default_unchanged`

## Verification plan

- `./scripts/init.sh --feature colloquial_ab_evaluation` — the focused block, unchanged.
- `./scripts/init.sh --backend-tests -q` once — full backend suite, no regression.
- Real `check` — exit `0`, 49 variants, 49 approved parents, 0 orphans, counts by state.
- Owner `--colloquial-review` / `--colloquial-decide` — every variant decided; pinned lines; counts recorded.
- Real `prepare` — pinned model digest verified, one cache file, status counts; no hosted call.
- Real `run` — exit `0`, one `Result:` line, `build/colloquial-ab/reports/<id>/report.json`; rerun gives a byte-identical file (`cmp`).
- `git diff --quiet -- knowledge/ backend/config/question_glossary.json` and `git status --short` — empty/only the intended docs and variant decisions.
- Independent recomputation from `report.json` rows: per-arm hit@5 and counts, trap regressions, `version_id = sha256(canonical version)[:16]`.
- E2E: none. This is a developer-only offline command with no user-visible behavior, route, auth, or API flow; the command walkthrough test plus the real run is the coverage.

## Evidence to capture

- Focused block, full suite, and `check` with one-line results.
- Owner approval counts (approved/rejected) and the date; a statement that no unapproved item was scored.
- Model tag and digest from the cache/report, plus rewrite status counts.
- Per-arm hit@5 counts and values (fixed denominator), changed-query counts, trap regressions per arm, the two `adoptable` outcomes, and `version_id`.
- Second-run byte comparison; `knowledge/` and glossary diff; list of written files outside `knowledge/`.
- A note that acceptance is validator-final with no owner walkthrough (owner decision 5), and the automated command walkthrough result.

## Feature evidence

2026-11-10, branch `feature/colloquial_ab_evaluation` (repaired after independent validation):

- Focused verification block: `66 passed` (`test_colloquial_ab.py`, `test_colloquial_ab_command.py`, `test_question_glossary.py`, `test_eval_metrics.py`).
- Full backend suite: `3425 passed, 9 skipped`.
- `colloquial_ab.py check` on the repository variants: `49 variants OK (approved=0, draft=49, rejected=0); 49 approved golden parents, 49 covered, 0 orphans`, exit 0.
- **No owner-approved A/B exists yet.** The owner has approved 0 of 49 variants (49 are draft, 0 rejected), so there is no owner-approved measurement to report.
- **Developer rehearsal, not evidence.** A Git-ignored copy was hand-edited to mark all 49 variants approved with `reviewed_by: "rehearsal"`, which is fabricated approval, not an owner decision; owner decision 2 forbids scoring unapproved variants. That rehearsal `prepare`/`run` produced hit@5 24/37 no rewriting, 26/37 glossary, 34/37 glossary+model, 2/2 trap regressions (`trap-013`, `trap-016`), and `version_id 244592b70f8d5526`. The numbers are kept only to show the tooling runs end to end; they MUST NOT be cited as an owner measurement, used to choose an arm, or allowed to drive adoption. The rehearsal artifacts stay under Git-ignored `build/colloquial-ab/` and are not committed.
- A second rehearsal `run` over the same cache was byte-identical (`cmp` exit 0); this is a determinism check of the tooling, not owner evidence.
- `prepare` on the committed all-draft set: abort `no_approved_variants`, exit 2, nothing written.
- `git diff --quiet -- knowledge/` and the same against `backend/config/question_glossary.json`: both empty.
- `backend/tests/fixtures/colloquial_ab/` was intentionally not created: the tests build temporary copies and read the real `knowledge/` files read-only. This is a recorded deviation from the spec's expected-file list, not a missing artifact.
- Acceptance is validator-final (owner decision 5); the command walkthrough is covered by `test_list_waiting_pinned_line_and_full_list_file`, `test_decide_records_replaces_and_records_nothing_on_bad_input`, and `test_missing_backend_environment_line_and_init_wiring`, all passing inside the focused block.

### Owner-approved run (2026-11-11)

The owner approved all 49 variants (`reviewed_by: "Jose"`, `reviewed_on: "2026-11-11"`), so `backend/config/colloquial_variants.json` now records 49 approved, 0 draft, 0 rejected; `check` prints `49 variants OK (approved=49, draft=0, rejected=0); 49 approved golden parents, 49 covered, 0 orphans`.

- `prepare --as-of 2026-11-11` with the pinned loopback model `mistral-small3.2:24b-instruct-2506-q4_K_M`: 49 rewritten, 0 empty, 0 rejected, 0 skipped.
- `run --as-of 2026-11-11`: hit@5 24/37 no rewriting, 26/37 glossary, 34/37 glossary+model (37 answered, 27 changed queries); traps worse 2 in both arms (`trap-013`, `trap-016`); verdict `not adoptable (a trap got worse)` for both arms; `version_id 0b92f9eb1cb91aa3`.
- These counts and the two trap regressions match the 2026-11-10 rehearsal exactly, so the tooling is deterministic; this run, not the rehearsal, is the owner measurement.
- Report only: no default, threshold, gate, or `knowledge/` change. The report stays under Git-ignored `build/colloquial-ab/`.

## Validator checklist

- [ ] Scope matches the contract; every non-goal respected (no `/ask`, retrieval, glossary default, `eval_metrics`, gate, or `knowledge/` change).
- [ ] Scenarios 1–10 pass with evidence; only approved variants were ever scored; drafts/rejected provably unread.
- [ ] All 49 variants exist, one per approved golden parent, and the owner decided every one; approval recorded per item.
- [ ] The three arms share corpus, campaign, `as-of`, `k`, drafting, cache state, case order, and inspection; only the expansion object differs.
- [ ] The rule uses a fixed denominator, strictly greater hit@5, and no trap worse; incomplete review and no effect cannot read as adoptable; no default changed.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature colloquial_ab_evaluation`.
- [ ] Report is deterministic, version-keyed, text-free, outside `knowledge/`; `prepare` uses only the pinned local model; `run` is offline.
- [ ] Durable documentation impact followed (ARCHITECTURE, constraints, risks, known limitations/PROGRESS, backend README, owner guide + index); nothing restated.
- [ ] `feature_list.json` status and `PROGRESS.md`/`docs/progress/session-log.md` updated by the implementer/validator, not the planner.
