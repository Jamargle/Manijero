# golden_dataset_expansion — appendix

## Repository research

### Files inspected

- `knowledge/pac_answer_eval.json` — 14 `author_only` cases (Diego, 2026-10-27), 8 coverage areas (3 topic, 5 boundary), 8 omissions; the base the golden set extends but must not edit.
- `knowledge/pac_answer_eval.schema.json` — `pac-answer-eval-v2`; `review.role` enum is only `author_only`; land-context shape to reuse.
- `knowledge/passages.json` — 7 passages: canal SGA (`res_20260121`), excepción persona física (`rd_1048_2022`), plazo presentación 15/05/2026 (`dl_1_2026`), plazo modificación 15/06 (`rd_537_2026`), recinto SIGPAC (`rd_1047_2022`), notificación electrónica and rectificación de errores (`ley_39_2015`).
- `knowledge/source_catalog.json` — 6 sources, all `approved` / `current`; title, location, and `original_url` feed the readable list.
- `knowledge/pac_coverage.md` — the approved scope, the coverage matrix, and the omissions. The three 2026-11-07 passages have no eval cases and no coverage area. "notificaciones individuales" is an omission, so notification items must stay general.
- `backend/app/answer_eval.py` — the strict loader: it rejects any role other than `author_only`, requires declared areas, and checks known source/passage ids. `evaluate()` produces report rows and a coverage report.
- `backend/scripts/evaluate_pac_answers.py` — CLI flags `--catalog --passages --cases --active-campaign --as-of --k`. `--golden` attaches here.
- `backend/tests/test_pac_answer_eval.py` — hard-codes `len(cases) == 14` and 3 topic / 5 boundary areas.
- `backend/tests/test_question_scope.py` — hard-codes 11 answered questions. Requires omissions one-to-one with the guard.
- `backend/tests/test_input_guardrails.py` — every question in `pac_answer_eval.json` must pass `screen_question`.
- `backend/tests/test_local_load.py` — hard-codes 14 cases and 13 `general` cases.
- `backend/app/release_gates.py`, `backend/app/knowledge_release.py`, `knowledge/knowledge-release-manifest.schema.json` — the release bundles `pac_answer_eval.json`, and per-case no-regression applies to unchanged cases.
- `backend/scripts/demo_rehearsal.py`, `backend/scripts/measure_local_load.py`, `backend/scripts/knowledge_review.py` (consumer known from specs, not opened) — other `--cases` consumers.
- `scripts/init.sh` — the `--demo-rehearsal` dispatch pattern (venv fallback, `Result:` on missing setup, runs before the `local.properties` write). `run_feature` reads the spec's verify block generically, so no planner wiring is needed.
- `docs/owner-guide.md` — the header promises one `Result:` line per command, and owner sections use numbered steps plus a "You see / What it means / What to do" table.
- `docs/constraints/operations.md` — owner operability: one command, prerequisite check first, one result line, no JSON editing, and a walkthrough with a missing-prerequisite case and a recovery.
- `docs/constraints/answers-and-knowledge.md` — "Safety evaluation" holds the review-before-entry rule; the new golden rule goes there.
- `docs/archive/MasterPlanV3.md` §2.3, §12 — segments A/B/C plus transversal; source-first principle; composition 40–60.
- `docs/specs/backend_answer_evaluation.md`, `docs/specs/question_scope_guard.md` — accepted contracts this must not regress.

### Existing patterns to follow

- Strict stdlib loaders raise `…Error` with a `$.path` message. Evaluators are deterministic and report-only, with explicit `--as-of`.
- Owner commands are `./scripts/init.sh --<name>` and end with one `Result:` line. Tracebacks go to a log under `build/`.
- Atomic JSON writes (temp file + `os.replace`), `ensure_ascii=False`, indent 2, trailing newline.
- Tests run against `backend/tests/fixtures/*` corpora plus one canonical-file test. Schema checks use `Draft202012Validator` + `FormatChecker` (as `test_pac_answer_eval.py` does).
- The init.sh command tests in `backend/tests/test_demo_rehearsal.py` drive init.sh with a fake venv in a temp dir.

### Current gaps

- With only 7 passages, 40–60 items means many paraphrases per passage. Retrieval misses will be visible in the report (report-only); they are not a defect of this feature.
- No eval coverage areas exist yet for SIGPAC, electronic notification, or error rectification. Add them as golden `additional_areas` (`topic`): `definicion-recinto-sigpac`, `notificacion-electronica`, `rectificacion-errores`.

## Implementation plan

1. Write `knowledge/golden_set.schema.json` (`golden-set-v1`; see the contract's Technical approach). Enums: `question_type` {procedure, deadline, eligibility_caveat, land_dependent, out_of_scope, colloquial}; `segment` {secano-convencional, regadio-convencional, ecologico, transversal}; `review_state` {draft, approved, rejected}; `decision.decision` {approved, rejected}.
2. Write `backend/app/golden_set.py`: `load_golden(path, catalog, passages, base_doc)` with these checks:
   - structural, anchor, safety, and duplicate checks (scenarios 2–3);
   - `distribution_failures(items)` (scenario 1);
   - `approved_cases()`, `render_list(items, catalog, passages, only_waiting)`, and `record_decision(path, decision, name, refs, today)`.
3. Write `backend/scripts/golden_review.py` with `list`, `decide`, and `check` (the CLI defaults to the canonical `knowledge/` paths for `list`/`decide`). `decide` validates everything before writing anything.
4. Add `--golden` to `evaluate_pac_answers.py`, merging approved cases and `additional_areas`, and add `golden` counts to the report only when the flag is given.
5. Add `--golden-review` and `--golden-decide` to `scripts/init.sh` (mirroring `--demo-rehearsal`) and two help lines.
6. Draft 40–60 items into `knowledge/golden_set.json`, all `draft`, with `drafted.by = "agent:golden_dataset_expansion"`. Copy anchors and facts verbatim from `passages.json`, and only answer what a passage says. Meet the minimums, then iterate with `check` until it exits 0.
7. Write tests (below), then the docs: the owner guide, both READMEs, `pac_coverage.md`, and the constraint bullet.
8. Run the focused block twice (determinism) and record the results. Do not approve any item; approval is the owner's alone.
9. Fill the appendix `## Handoff` with the post-walkthrough steps: commit the owner-changed `golden_set.json`, rerun `check` and the `--golden` evaluator, and record the counts in `pac_coverage.md` and the acceptance record.

Pinned `Result:` lines. The success lines are in contract scenarios 6–7; the failure lines below record nothing and exit 1:

| Case | `Result:` line |
|---|---|
| missing/invalid decision word, name, or items | `Result: nothing was recorded. Write approve or reject, your name in quotes, and at least one question number, for example: ./scripts/init.sh --golden-decide approve "Diego" 1 2 3` |
| unknown number/id | `Result: nothing was recorded. These question numbers are not in the list: <refs>. Run ./scripts/init.sh --golden-review and use the numbers shown there.` |
| anchor no longer verifies (approve) | `Result: nothing was recorded. Question <n> no longer matches the approved sources. Send this line to the developer.` |
| damaged or invalid file (list or decide) | `Result: the golden question list could not be read, and nothing was recorded. Send this line to the developer.` |
| no backend environment | `Result: the golden review did not run. Run ./scripts/init.sh --local-rag-setup.` |

## Verification plan

The tests in `backend/tests/test_golden_set.py` are offline, use fixtures, and inject the clock:
- the schema validates the canonical file;
- the canonical file passes `check`, all items are `draft`, the count is 40–60, the distribution minimums hold, and the ids are contiguous;
- each anchor-failure rule fails with item id + rule: unknown source, unapproved/retired source, source/passage mismatch, anchor not a substring, fact not a substring, abstention with an anchor, abstention basis not an omission, answered without an anchor;
- safety: a guardrail-flagged question, an answered item hit by the scope guard, a duplicate question+lands pair (including against base cases), and an undeclared area each fail;
- isolation: draft and rejected items are never in `approved_cases()`; the evaluator without `--golden` is byte-identical to a pre-feature fixture report; with zero approved the case rows are equal; and a source-text guard shows that `backend/app/release_gates.py`, `backend/app/knowledge_release.py`, `backend/scripts/knowledge_release.py`, `backend/scripts/knowledge_review.py`, `backend/scripts/demo_rehearsal.py`, and `measure_local_load.py` never reference `golden_set`;
- scoring: approved items appear with their area; two runs are byte-identical; an id collision with a base case fails;
- decide: approve and reject write the decision fields; a re-decision replaces the earlier one; number and id forms both resolve; each pinned failure leaves the file bytes unchanged; the write is atomic;
- list: shows only waiting items, writes the all-items file under a temp `build/`, gives the correct `Result:` line for N>0 and N=0, and writes nothing under `knowledge/`;
- init.sh dispatch: both commands call the script and print the no-venv `Result:` line (fake venv in a temp dir, same pattern as `test_demo_rehearsal.py`).

Other checks:
- `git diff --stat main -- knowledge/pac_answer_eval.json knowledge/passages.json knowledge/source_catalog.json` — empty.
- Existing suites stay green: `tests/test_pac_answer_eval.py tests/test_question_scope.py tests/test_input_guardrails.py tests/test_local_load.py tests/test_knowledge_release.py`.
- E2E: none. There is no app or HTTP surface; the evaluator already exercises `/ask` in-process.
- Manual: the owner walkthrough (contract scenario 9).

## Evidence to capture

- The focused block run twice, with one-line results and the evaluator report digest for both runs.
- The `check` summary: the count per type, segment, passage, and area.
- The empty diff of the existing knowledge files, and the regression suites listed above.
- After the walkthrough: each owner `Result:` line, the approved/rejected counts, and the `--golden` evaluator summary.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-08 (implementer, resumed session):
- `./scripts/init.sh --backend-tests -q tests/test_golden_set.py` — 40 passed.
- `./scripts/init.sh --feature golden_dataset_expansion` run twice — passed both times; the evaluator JSON (14 base cases plus `golden: {approved: 0, draft: 46, rejected: 0}`) is identical across runs and its `case_rows` equal the no-flag run (tested).
- `golden_review.py check` — 46 items OK. type: colloquial 8, deadline 10, eligibility_caveat 6, land_dependent 6, out_of_scope 7, procedure 9. segment: ecologico 7, regadio 9, secano 8, transversal 22. All 7 passages anchor 3–8 answered items; all 11 areas used.
- `./scripts/init.sh --fast` — all 10 checks passed (backend-tests 2556 passed, 7 skipped).
- `git diff --stat main -- knowledge/pac_answer_eval.json passages.json source_catalog.json pac_answer_eval.schema.json` — empty.
- Spot-check by hand against `passages.json`: 46 anchors and facts are verbatim (enforced by `check`); no answered item goes beyond its passage. No item approved or rejected.
- Not run: `--verify` (no Android/Desktop/Gradle surface touched).

## Handoff

Implementation, tests, and docs are complete and self-verified; all 46 items are `draft`. Remaining:
1. Validator reviews against the checklist below.
2. After acceptance, the owner follows `Owner walkthrough: golden set review` in `docs/owner-guide.md` (approve or reject every item).
3. Commit the owner-changed `knowledge/golden_set.json` on the feature branch.
4. Rerun `golden_review.py check ...` and the `--golden` evaluator (focused block); both must pass.
5. Record the approved/rejected counts and each owner `Result:` line in `docs/validations/golden_dataset_expansion.md`, and replace the placeholder sentence in `knowledge/pac_coverage.md` ("Preguntas de oro en borrador") with the approved/rejected counts.

## Validator checklist

- [ ] The scope matches the contract: `pac_answer_eval.json`, `passages.json`, `source_catalog.json`, and the schema are byte-unchanged; no gate, release, review, demo, or load code reads `golden_set.json`.
- [ ] 40–60 items, all `draft`, distribution minimums met; spot-check ≥10 anchors by hand against `passages.json`, and confirm no answer goes beyond its passage.
- [ ] Abstention items are marked `deliberate_abstention` with an omission basis; there are no trap/injection/personal-data items.
- [ ] Both owner commands follow operations constraints: a prerequisite check, one `Result:` line, nonzero on failure, nothing recorded on bad input, and no JSON editing.
- [ ] The owner guide has `Owner walkthrough: golden set review` with a missing-input case and a recovery, within about 60 lines total.
- [ ] Without `--golden` the evaluator output is unchanged; with it, only approved items are scored and the output is deterministic.
- [ ] The focused verification block runs unchanged through `./scripts/init.sh --feature golden_dataset_expansion`.
- [ ] The constraint bullet, both READMEs, and `pac_coverage.md` are updated without restating the spec.
- [ ] Acceptance is final only after the owner walkthrough, recorded in `docs/validations/golden_dataset_expansion.md`.
