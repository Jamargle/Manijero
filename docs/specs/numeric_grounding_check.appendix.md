# numeric_grounding_check — appendix

## Repository research

### Files inspected

- `backend/app/generation.py` — `verify_draft`, `extract_figures`, `_canonical_figure`,
  `normalize_text`, `GROUNDING_FAILURE_CODES`, `_reason_for`. This is the only place the rule
  goes.
- `backend/app/gemini_generation.py` (lines 395–500) — `GatedGeminiGenerator._gemini_draft`
  runs `verify_draft(draft, offered)` and returns `OUTCOME_REJECTED` with no draft. `generate`
  then returns the extractive draft. The shared Gemini and local path needs no change.
- `backend/app/local_generation.py` and the `local_generation_provider` spec — the local
  provider reuses the gated generator unchanged. The instruction and outcomes are pinned.
- `backend/tests/test_generation.py` — the existing `extract_figures` parametrized cases
  (lines 282–300); the figure, critical, and policy rejections; recorded-fixture tests (lines
  469–500: a case name must equal its code or start with it, and the code must be in
  `GROUNDING_FAILURE_CODES`); privacy-detail tests (lines 503–535); fixture hygiene (lines
  1198–1225).
- `backend/tests/fixtures/generation/drafts_ungrounded.json` and `passages.json` — the
  recorded draft cases and the synthetic passages. None contains a month name or a number word.
- `backend/tests/test_local_generation.py` — `_outcome_cases` (line 895) and
  `test_every_failure_on_ask_equals_the_extractive_baseline` (line 925). They use the
  clarification fixture passage "se presenta una vez al año" through `_solicitud_handle`.
- `backend/tests/fixtures/{clarification,abstention,land_safety,generation}/passages.json` —
  the synthetic excerpts the extractive regression must keep passing. They contain "una vez",
  "una parcela", and "la segunda frase"; none of these is a number fact under the rule.
- `knowledge/passages.json` — four reviewed passages. The two critical ones ("15 de mayo de
  2026", "15 de junio") are already literal-only. The non-critical one carries "Ley 39/2015, de
  1 de octubre" and "Ley 30/2022, de 23 de diciembre": a changed month there passes today.
- `backend/app/abstention.py`, `backend/app/land_safety_eval.py`,
  `backend/scripts/evaluate_abstention.py` — these call `extract_figures` on abstention copy,
  so it must stay unchanged.
- `backend/scripts/evaluate_generation.py` — `ENFORCED_INVARIANT_CODES =
  GROUNDING_FAILURE_CODES | POLICY_ISSUE_CODES`, so the new code is enforced automatically.
- `backend/scripts/evaluate_pac_answers.py` — the report-only CLI. It exits `0` on a report and
  `2` on an input error.
- `backend/tests/test_pac_answer_eval.py` — uses a fake client. It does **not** run the real
  pipeline, so it is not a regression guard for this feature.
- `docs/constraints/answers-and-knowledge.md` "Answer grounding", `knowledge/README.md` (lines
  380–401), `backend/README.md` (lines 955–965), `ARCHITECTURE.md` (line 43),
  `docs/risks-and-open-questions.md` (line 13) — the durable text the docs impact refers to.
- `docs/constraints/operations.md` — this feature adds no owner command, so the rules do not
  apply.

### Existing patterns to follow

- A verifier rule appends a `GroundingIssue(code, fixed_detail)` to `claim_issues`. The detail
  names only rule names, never content.
- Normalize with `normalize_text` and canonicalize digits with `_canonical_figure`. Do not add
  a second normalizer.
- Recorded ungrounded drafts live in `drafts_ungrounded.json`, keyed by code or `code_variant`.
  Use `make_passage(...)` for verifier tests that must not depend on ranking.
- Every fixture passage text containing digits must be labelled `cifra inventada` or `fixture`
  (`test_generation_fixtures_label_every_fictitious_figure`).
- Local fallback tests assert `response.json() == baseline` and exactly one
  `("local", outcome)` log pair, with forbidden content strings absent.

### Current gaps

- `_FIGURE` matches digits only. Month names, number words, day–month pairing, and duration
  units and qualifiers are not extracted, so they are never checked on non-critical citations.
- There is no real-corpus test that the extractive draft of every committed passage verifies.
  The 14-case report is the only real-pipeline check, and it is report-only.
- No owner decision is pending. The choice of a new issue code over reusing
  `figure_unsupported` is technical: it keeps existing outputs byte-identical and makes the new
  rule observable in tests and in `evaluate_generation.py` reports.

## Implementation plan

1. Baseline: run the `evaluate_pac_answers.py` command from the contract before any edit, and
   record its aggregate block in Feature evidence.
2. In `generation.py`, add closed tables: Spanish cardinal words (units, teens, `veinti-`
   forms, tens, hundreds in masculine and feminine, `cien`/`ciento`, `mil`), the months, and
   the duration units and qualifiers, all in normalized (diacritic-free) spelling.
3. Add a cardinal-run parser for 0–999 999. An invalid run returns an unparsed-literal token.
   `un/una/uno` is only admitted inside a duration or a day position.
4. Add `extract_numeric_facts(text)` with the token kinds from the contract's table. Choose
   stable string prefixes per kind (for example `n:`, `w:`, `m:`, `dm:`, `d:`, `dur:`) and
   document them in the docstring.
5. Add a private `_numeric_support(passages)` helper. It returns the union of
   `extract_numeric_facts(excerpt)`, plus `n:<figure>` for each non-date `extract_figures`
   value, plus the month and day–month tokens of each ISO or `d/m/yyyy` date.
6. In `verify_draft`'s cited branch, after the `figure_unsupported` check: if no
   `figure_unsupported` was added for this claim and `extract_numeric_facts(text) - support`
   is non-empty, append `numeric_fact_unsupported` with the fixed detail.
7. Add `numeric_fact_unsupported` to `GROUNDING_FAILURE_CODES`, and add the durable-rule line
   to the module docstring.
8. Tests in `test_generation.py`, named after the behavior each covers (list below). Add the
   three fixture cases to `drafts_ungrounded.json`.
9. Add a `verifier_rejected` case to `_outcome_cases` in `test_local_generation.py`. Its
   draft is `f"Se presenta una vez al año, en mayo [{handle}]."`, and "mayo" is added to that
   test's forbidden-log list.
10. Run the focused block. Rerun the evaluation, compare its aggregates with step 1, and record
    both results.
11. Make the durable doc edits listed in the contract. Append evidence below.

Test names to add (in `test_generation.py` unless stated otherwise):

- `test_extract_numeric_facts_reads_words_months_dates_and_durations` (parametrized; includes
  accent-free spellings, `veintiún`, `treinta y uno`, `dos mil quinientos`, `primero de mayo`,
  `1.º de mayo`, `quince (15) días hábiles`, `veinte por ciento`).
- `test_extract_numeric_facts_ignores_articles_and_plain_prose` ("una parcela", "una vez al
  año", "la segunda frase", `NOTICE`, `LEAD_IN` → empty).
- `test_extract_figures_is_unchanged_by_the_numeric_check` (the existing cases still pass,
  plus a written date yields the digits only).
- `test_a_changed_month_or_day_is_rejected_without_a_figure_code` (scenario 1).
- `test_number_words_and_months_without_digits_are_checked` (scenario 2).
- `test_a_deadline_unit_or_qualifier_must_match` (scenario 3).
- `test_equivalent_written_forms_pass_and_an_added_year_does_not` (scenario 4).
- `test_numeric_support_is_the_union_of_cited_passages` (scenario 5).
- `test_a_digit_only_problem_keeps_only_figure_unsupported` (scenario 6).
- `test_every_committed_passage_verifies_as_an_extractive_draft` (scenario 7; covers
  `knowledge/passages.json` and every `backend/tests/fixtures/*/passages.json`).
- `test_numeric_rejection_detail_is_fixed_and_content_free` and
  `test_numeric_rejection_is_grounding_failed_and_emits_no_text` (scenario 9; the latter uses a
  fake `GroundingGenerator` through `generate_grounded_answer`).
- `test_local_generation.py`: the new `verifier_rejected` row in
  `test_every_failure_on_ask_equals_the_extractive_baseline` (scenario 8).

## Verification plan

- `./scripts/init.sh --feature numeric_grounding_check` should run all three lines with exit
  `0`.
- Evaluation aggregates (states, sources, passages, critical facts) should be identical to the
  step 1 baseline. Any difference is a regression: stop and report it.
- Mutation spot-check (by hand, not committed): remove the new check from `verify_draft`.
  Scenarios 1–3 and 8 must then fail.
- E2E: not needed. There is no client, route, or contract change. The FastAPI `/ask` path is
  covered by the local-provider fake test and by `test_ask_endpoint.py` in the full suite.
- Live model: not run. With no owner computer access this run, the effect on the local
  verified-draft rate is unmeasured and must not be claimed.

## Evidence to capture

- The baseline and post-change evaluation aggregates, one line each, stated as identical or
  not.
- The focused-block result, one line per command, with pass counts.
- The mutation spot-check result, in one line.
- The doc files edited, one line each.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer (fixtures and fakes only; no Ollama, network, model, or owner step).

- Environment: `./scripts/python-env.sh dev --if-present` linked the already-built shared env
  (no install); `--setup-python` was not needed.
- Baseline (before any edit), `evaluate_pac_answers.py` contract line: exit 0; 14 cases, 13
  state agreement, 11 answered, 11 expected-answer coverage, 8 source agreement, 9 critical
  facts, 3 abstentions, 1 unexpected answer.
- After the change: exit 0; the whole JSON report (aggregates and every case row) is
  byte-identical to the baseline (`cmp`).
- `./scripts/init.sh --feature numeric_grounding_check`: passed. Line 1: 694 passed. Line 2:
  exit 0, report identical. Line 3: 1446 passed, 4 skipped.
- `CI=true ./scripts/init.sh --fast`: 8 of 9 checks ok (contract-examples, backend-tests 1446
  passed / 4 skipped, source-catalog, retrieval MRR 0.857, generation, abstention,
  clarification, land-safety 0 misses). `gradle-jvm-test` could not run: "Unable to locate a
  Java Runtime" (no JDK on this host; installing one is outside the worktree). No Kotlin,
  Gradle, or `shared/` file changed.
- `--verify` not run: Android/Desktop only, it needs the same missing JDK, and this
  backend-only change does not touch those surfaces.
- Mutation spot-check (by hand, reverted): with the new `elif` disabled, 18 tests failed. They
  cover scenarios 1–5 and 9, the three new recorded cases, and the scenario 8 local row.
- Scenario map: 1 `test_a_changed_month_or_day_is_rejected_without_a_figure_code`; 2
  `test_number_words_and_months_without_digits_are_checked`; 3
  `test_a_deadline_unit_or_qualifier_must_match`; 4
  `test_equivalent_written_forms_pass_and_an_added_year_does_not`; 5
  `test_numeric_support_is_the_union_of_cited_passages`; 6
  `test_a_digit_only_problem_keeps_only_figure_unsupported` plus
  `test_extract_figures_is_unchanged_by_the_numeric_check`; 7
  `test_every_committed_passage_verifies_as_an_extractive_draft` (38 passages in 7 files, with
  two deliberate pre-existing non-numeric rejections pinned: `fixture-abs-riego-1`
  uncited_sentence, `fixture-abs-ayuda-1` eligibility_claim) plus the identical evaluation; 8
  new `verifier_rejected` row in `test_every_failure_on_ask_equals_the_extractive_baseline`
  (it now also asserts `no_network == []`, and "mayo" is forbidden in the log), with
  `local_used` still pinned by the existing verified-draft test; 9
  `test_numeric_rejection_detail_is_fixed_and_content_free` and
  `test_numeric_rejection_is_grounding_failed_and_emits_no_text`.
- Docs edited: `docs/constraints/answers-and-knowledge.md` (one MUST), `knowledge/README.md`
  (figures bullet), `backend/README.md` (`verify_draft` sentence),
  `docs/risks-and-open-questions.md` (one clause), `docs/progress/known-limitations.md` (one
  item; the `PROGRESS.md` digest line is left for acceptance).
- Not measured: the effect on the live local model's verified-draft rate.

## Validator checklist

- [ ] Only `generation.py`, the three test files, the one fixture, and the listed docs
      changed. The non-goal files are untouched (`git diff --stat`).
- [ ] `extract_figures` behaves byte-for-byte as before. The existing `figure_unsupported`
      and recorded-fixture codes are unchanged (scenario 6).
- [ ] Each of scenarios 1–9 maps to a named passing test. Scenario 7 covers every committed
      `passages.json`.
- [ ] A rejected local draft yields the exact extractive baseline and `verifier_rejected`.
      No draft text appears in the response or the log.
- [ ] The new issue detail is a fixed string. No new dependency, import, network call, or
      model call.
- [ ] The evaluation aggregates are identical to the recorded baseline.
- [ ] The focused verification block runs unchanged through `./scripts/init.sh --feature
      numeric_grounding_check`.
- [ ] The durable doc edits match the contract, and nothing is restated across files.
      `known-limitations.md` states the lexical, Spanish-only, time-units-only limits.
- [ ] `feature_list.json` and `PROGRESS.md` are updated only at acceptance.
