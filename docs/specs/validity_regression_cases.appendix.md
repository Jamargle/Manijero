# validity_regression_cases — appendix

## Repository research

### Files inspected

- `feature_list.json` — row `validity_regression_cases`: `evaluation`, `not_started`, depends on `validity_checker` and `seed_corpus_expansion`.
- `PROGRESS.md` "Current state" — 14-case author-reviewed sample, report-only metrics; `seed_corpus_expansion` listed `in_progress` pending owner approval (selector owns readiness).
- `knowledge/source_catalog.json` — 6 reviewed sources (`res_20260121`, `dl_1_2026`, `rd_1048_2022`, `rd_537_2026`, `rd_1047_2022`, `ley_39_2015`); none mentions RD 1077/2014 or the digital notebook; no repeal or `valid_until` field for any non-campaign source.
- `knowledge/passages.json` — 7 passages; `pasaje-plazo-presentacion-2026-andalucia` (`official_deadline` `2026-05-15`) and `pasaje-plazo-modificacion-2026-andalucia` (`2026-06-15`); `rd_1047_2022` has only the SIGPAC definition (art. 2.1.h), no derogation provision.
- `knowledge/pac_coverage.md` — verdict table: `rd_1054_2022` `not_added` (SIEX and digital notebook are a pinned "not yet covered" disclosure topic); evaluation matrix, totals, and pinned evaluator command (`--as-of 2026-10-26`).
- `docs/specs/seed_corpus_expansion.appendix.md` — research note "the archive says [RD 1047/2022] repealed RD 1077/2014": a research lead, not a reviewed passage, so not grounding.
- `knowledge/pac_answer_eval.json` / `pac_answer_eval.schema.json` — `pac-answer-eval-v2`; abstention cases must not carry source/passage/fact expectations; `review.role` only `author_only`; areas `topic`/`boundary`.
- `backend/app/answer_eval.py` — loader rules and `evaluate`: state, source, passage, and `critical_facts` substring match; report-only.
- `backend/scripts/evaluate_pac_answers.py` — dependency overrides for corpus, as-of, campaign, `k`; one run-level `--as-of`.
- `backend/app/abstention.py` — `answer_or_abstain` order: scope guard, retrieval, `has_unsupported_presupposition` (instrument + number must appear in a candidate excerpt/location → else `false_premise`), unit conflict, generation; pinned `ABSTENTION_MESSAGES`.
- `backend/app/retrieval.py` — `tokenize`: lowercase, strip diacritics, stopwords, no stemming; exact-token BM25.
- `backend/app/deadline_notices.py` — `deadline_paragraph`: `EXPIRED` when `official_deadline < as_of`, always `COOPERATIVE`; `EXPIRED_PREFIX`, `COOPERATIVE` constants.
- `docs/specs/answer_deadline_notices.md` — notices appended to answered results only, driven by reviewed `official_deadline` and injected as-of.
- `docs/specs/validity_checker.md` — derived review artifact only; never changes `/ask`, so it is not the runtime path these cases exercise.
- `backend/app/question_scope.py` / `backend/tests/test_question_scope.py` — guard is one-to-one with declared omissions; reviewed answered questions must not match the guard (count pinned at 11).
- `backend/app/input_guardrails.py` / `backend/tests/test_input_guardrails.py` — every eval question must pass screening; none of the three new questions matches personal-data, injection, or off-topic patterns.
- `backend/tests/test_pac_answer_eval.py`, `backend/tests/test_local_load.py` — pin 14 cases, 11 answered, 3 abstained, 5 boundaries.
- `backend/app/source_catalog.py` — catalog validation rejects only expired `valid_until` vs as-of; as-of `2026-05-15` stays valid for the control run.
- `backend/tests/test_source_validity.py` — socket-blocking fixture pattern.
- `backend/app/knowledge_release.py` — gate summary keys `cases`, `expected_state_agreement`, `unexpected_answers`; more matching cases cannot regress it.

### Existing patterns to follow

- Report-only evaluator; deterministic pytest pins behavior with the app's own constants (no retyped Spanish copy).
- `TestClient(app)` with `app.dependency_overrides` cleared in `finally`.
- Canonical knowledge edits are owner-approved data changes recorded in `pac_coverage.md`; author-only review metadata.

### Current gaps

- No reviewed source states RD 1077/2014's repeal or replacement (case 1 → `no_evidence` abstention; corrected 2026-11-08 from the planner's `false_premise` assumption after an implementer run on unchanged code).
- No reviewed source states the digital notebook's voluntary or mandatory status (case 3 → abstention).
- The harness has one run-level as-of; the expired/open contrast is checked in the new pytest, not in the JSON case set.
- The evaluator does not report the abstention reason; the pytest checks the exact pinned message instead.

## Implementation plan

1. Append the three `boundary` areas and three cases to `knowledge/pac_answer_eval.json` exactly as in the contract (review `Diego`, `2026-11-07`, `author_only`).
2. Add `backend/tests/test_validity_regression_cases.py`: env/socket fixture; `/ask` helper with overrides; scenario 1, 2 (as-of `2026-10-26` and control `2026-05-15`), 3; `evaluate` over the three cases on the real route; grounding preconditions on canonical files plus tmp-path mutations; catalog/passages byte-identity.
3. Run the new test before touching counts; if scenario 1–3 fails, stop per the contract's stop rule.
4. Update count assertions in `test_pac_answer_eval.py`, `test_question_scope.py`, `test_local_load.py`.
5. Update `knowledge/pac_coverage.md` matrix, totals, and gap paragraph; count lines in `knowledge/README.md`, `backend/README.md`, `docs/risks-and-open-questions.md`.
6. Add the MUST to `docs/constraints/answers-and-knowledge.md` "Safety evaluation".
7. Run the focused block, then `./scripts/init.sh --fast`; record results below.

## Verification plan

- `./scripts/init.sh --feature validity_regression_cases` — all listed suites pass; evaluator exits `0`.
- Evaluator baseline at `--as-of 2026-10-26` before this change: 14/14 states, 11/11 answered, source 8/11, critical facts 9/11, unexpected answers 0. Expected after: 17/17 states, 12/12 answered, source 9/12, critical facts 10/12, unexpected answers 0; the 14 earlier rows unchanged. Record the actual numbers; any difference in earlier rows is a stop.
- `./scripts/init.sh --fast` — full backend suite (the case file feeds release, corpus-security, local-load, and generation suites).
- E2E: not needed; no client, contract, or route change. The real `/ask` route is exercised in-process.

## Evidence to capture

- Pre-change evaluator aggregates, post-change aggregates, and the three new case rows (one line each).
- Pinned abstention reason observed for cases 1 and 3 (both expected `no_evidence`); whether case 2 also cited the modification passage.
- Focused block and `--fast` results; `git diff --stat` showing no change under `backend/app`, `backend/scripts`, catalog, or passages.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-08, implementer (resumed after the spec fix: scenario 1 now expects `no_evidence`).

- Observed outcome, case 1: `abstained`, empty `sources`, pinned `no_evidence` message (generation reason `no_candidates`); the test asserts only that outcome. Case 2 cites only `pasaje-plazo-presentacion-2026-andalucia`; control `2026-05-15` has no expired prefix. Case 3: `no_evidence`.
- Files: `knowledge/pac_answer_eval.json` (+3 areas, +3 cases); new `backend/tests/test_validity_regression_cases.py`; counts in `test_pac_answer_eval.py`, `test_question_scope.py`, `test_local_load.py`; docs `pac_coverage.md` (matrix, totals, gap paragraph), `knowledge/README.md`, `backend/README.md` (lines ~1314, ~1329; the ~1068 hybrid measurement stays 14-case as a historical measurement), `docs/risks-and-open-questions.md`, `docs/constraints/answers-and-knowledge.md` (one MUST).
- `./scripts/init.sh --feature validity_regression_cases`: 150 passed; evaluator exit 0: 17/17 states, 12/12 answered, source 9/12, critical facts 10/12, 5 abstentions, 0 unexpected answers; the 14 earlier rows unchanged.
- `CI=true ./scripts/init.sh --fast`: 10/10 checks passed (backend 2530 passed, 7 skipped).
- No change under `backend/app`, `backend/scripts`, catalog, or passages.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no catalog, passage, schema, app, or guard change).
- [ ] Each case's expectation matches the grounding decision; no repository text claims a repeal, replacement, or voluntary/mandatory status.
- [ ] Scenarios 1–6 pass with evidence; the control at `2026-05-15` shows no expired notice.
- [ ] Precondition test fails on each mutation and passes on canonical files.
- [ ] Earlier 14 evaluator rows unchanged; counts updated consistently.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature validity_regression_cases`.
- [ ] Durable documentation impact followed; gaps recorded once in `pac_coverage.md`.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
