# Reject drafts whose numbers, dates, or deadlines do not appear in the cited passages

## Source metadata

- `id`: numeric_grounding_check · `area`: backend · `depends_on`: local_generation_provider,
  backend_citation_hardening (both accepted) · `status` at planning: not_started
- User-visible behavior: a drafted answer is never shown when a claim states a number, month,
  date, or deadline that its cited passages lack. The draft is dropped whole, and a model draft
  falls back to today's extractive answer. No new text, copy, or wire field appears.
- Verification: fixture-only tests plus the report-only 14-case evaluation; no Ollama, network,
  or owner step.
- Notes (run instructions 2026-11-01, treated as the owner's request): backend only, owned by
  code. A failed check falls back through the existing verify-then-extractive path, never to an
  unverified draft. No new dependency, no model call, no owner command, so
  [`operations.md`](../constraints/operations.md) does not apply.

## Goal

Close the lexical gap in `verify_draft`. Today it checks only digit figures and ISO or
`d/m/yyyy` dates (`figure_unsupported`). So a claim that cites a non-critical passage can say
"en junio", "quince días", or "10 días naturales" against a passage that says "15 de mayo" or
"10 días hábiles", and still pass. Add one lexical rule to that verifier. Every generator
(extractive, gated Gemini, gated local) goes through it, so a failing model draft is discarded
by the accepted fallback with no provider change.

## Non-goals

- No semantic judge (`semantic_grounding_judge`), numeric-accuracy metric
  (`evaluation_metrics_report`), or deadline notices (`answer_deadline_notices`).
- No change to `extract_figures`, `figure_unsupported`, the critical-literal rule, the
  abstention and land-safety figure checks, or citation renumbering.
- No change to `gemini_generation.py`, `local_generation.py`, the `gemini-draft-v1`
  instruction, outcome codes, log fields, or `measure_local_generation.py`; no re-measurement.
- No units beyond the time units below and `por ciento`; no ranges, relative expressions ("el
  mes siguiente"), `medio/media`, ordinals other than the day `primero`, Roman numerals, or
  millions.
- No change to `contracts/`, `knowledge/` data, `shared/`, requirements, or `scripts/init.sh`.

## Job story

When a model rewords an official passage, I want each number, date, or deadline it states
checked against the passages it cites, so a person never acts on one no reviewed source says.

## Acceptance Scenarios

Passages are non-critical synthetic fixtures (`sintético`, `prueba`, `cifra inventada`).
"Rejected" means `verify_draft(...).ok is False` with `numeric_fact_unsupported` on that claim.

### 1. A changed month or day is rejected

Given a passage with "del 1 de abril al 15 de mayo de 2031" · When a draft claims "hasta el 15
de junio [1]" or "hasta el 1 de mayo [1]" · Then it is rejected, without `figure_unsupported`
(every digit appears; only the day–month pairing is wrong).

### 2. Number words and month names without digits are checked

Given a passage with no number, month, or date (the fixture's `SOLICITUD_EXCERPT`) · When a
draft claims "se presenta en mayo [1]", "dispone de quince días [1]", or "el veinte por ciento
[1]" · Then each is rejected. Today the verifier accepts all three.

### 3. A deadline's unit and qualifier must match

Given a passage that says "un plazo de 10 días hábiles" · When a draft claims "10 días
naturales [1]", "10 días [1]", or "10 semanas [1]" · Then each is rejected. When it claims
"diez días hábiles [1]" or "10 días hábiles [1]" · Then it passes.

### 4. The same fact in another written form passes; an added fact does not

Given a passage with "15/05/2031" · When a draft claims "hasta el 15 de mayo [1]" or "en mayo
[1]" · Then it passes.
Given a passage with "15 días hábiles" · When a draft claims "quince (15) días hábiles [1]" ·
Then it passes.
Given a passage that says "Para la campaña 2031 … finalizará el 15 de junio", with no year next
to the date · When a draft claims "el 15 de junio de 2031 [1]" · Then it is rejected. Both
digits appear in the passage, but the full date does not.

### 5. Support is the union of the passages a sentence cites, as today

Given candidates 1 ("15 de mayo") and 2 ("10 días hábiles") · When one sentence cites `[1][2]`
and states "15 de mayo" and "diez días hábiles" · Then it passes. When the same sentence cites
only `[1]` · Then it is rejected.

### 6. Existing rejections and helpers are unchanged

Given every existing `drafts_ungrounded.json` and `test_generation.py` case · When verified ·
Then each yields exactly today's codes. A claim with an unsupported digit figure or digit date
carries `figure_unsupported` only (at most one numeric code per claim; the old code wins).
`extract_figures` returns today's values, so the abstention and land-safety checks are untouched.

### 7. Extractive answers are unaffected

Given every passage in `knowledge/passages.json` and in each
`backend/tests/fixtures/*/passages.json` · When the extractive generator drafts from it
alone · Then `verify_draft` passes.
Given the 14 cases in `knowledge/pac_answer_eval.json` · When evaluated · Then the aggregate
report is identical before and after the change.

### 8. A local model draft that fails the check falls back

Given the `local` provider is active with a fake opener · When the model returns a well-formed
draft whose only problem is a month that the cited passage lacks · Then `/ask` returns exactly
the extractive baseline. There is one `generation` log line, with `provider=local` and
`outcome=verifier_rejected`. No draft text reaches the response or the log, and no socket
outside the fake is opened.
Given the existing verified local draft ("Se presenta una vez al año [n]") · Then it is still
used (`local_used`).

### 9. Diagnostics stay content-free

Given any `numeric_fact_unsupported` issue · Then its `detail` is the fixed string "a number,
date, or deadline in the claim is absent from the cited passage(s)". It contains no claim text,
excerpt text, or extracted value.
Given the pipeline returns that rejection · Then the result is
`NotAnswered("grounding_failed")`, as for every other grounding code.

## Technical approach

- All changes are in `backend/app/generation.py`, inside `verify_draft`'s per-claim check, next
  to the digit rule. Add `numeric_fact_unsupported` to `GROUNDING_FAILURE_CODES`. With that,
  `_reason_for`, `evaluate_generation.py`'s enforced invariants, and the recorded-fixture
  code-name test pick it up with no other edit.
- Add a pure function, `extract_numeric_facts(text) -> FrozenSet[str]`, that works on
  `normalize_text(text)`. That function lowercases, strips diacritics, and collapses
  whitespace, so "dieciséis" and "dieciseis" match, and "año" becomes "ano". It returns
  canonical tokens of these kinds:

  | Kind | Recognized in text | Supported when the cited passages contain |
  |---|---|---|
  | Number word | A maximal run of Spanish cardinal words from 0 to 999 999 (for example `quince`, `treinta y uno`, `veintiún`, `dos mil quinientos`). `un/una/uno` counts only inside a duration or as a day. `<n> por ciento` is read as a percent. | The same value, in words or in digits, using the canonical form from `_canonical_figure` (so "quince" is supported by "15"). |
  | Unparsed run | A number-word run that is not a valid cardinal. | The same normalized run. |
  | Month | `enero` … `diciembre`, plus `setiembre`. | The same month, by name or inside an ISO or `d/m/yyyy` date. |
  | Day and month | `<day> de <month>`, where the day is 1–31, in digits (an optional `º`/`.º` is allowed) or in words, including `primero`. | The same day and month, written out or inside an ISO or `d/m/yyyy` date. |
  | Full written date | `<day> de <month> de <yyyy>`. | The same full date in any of the three written forms. |
  | Duration | `<number> <unit>`, where the number is digits, number words, or `un/una`, optionally followed by a parenthetical digit restatement `(15)`. The unit is `dia`, `semana`, `mes`, or `ano`, singular or plural. `dias` takes an optional `habiles` or `naturales` qualifier. | The same value, unit, and qualifier. |

- Claim rule: let *claim facts* be `extract_numeric_facts(claim)`. Let *support* be the union,
  over the cited passages, of `extract_numeric_facts(excerpt)` plus a number-value token for
  every non-date digit figure in `extract_figures(excerpt)`. If any claim fact is outside
  support, and the claim does not already carry `figure_unsupported`, append one
  `numeric_fact_unsupported` issue with the fixed detail.
- The rule only adds rejections: it never removes an issue, repairs a claim, or changes
  `extract_figures`. Extractive claims are verbatim excerpts, so they keep passing (scenario 7).
- The gated generators already run `verify_draft` and return the extractive draft on rejection
  (`OUTCOME_REJECTED`), which the pipeline verifies again; see
  [`ARCHITECTURE.md`](../../ARCHITECTURE.md) on verify-then-fallback.
- The module stays standard-library only and offline; existing tests in `test_generation.py`
  guard this.

## Expected file changes

- `backend/app/generation.py` — modify: vocabulary tables, `extract_numeric_facts`, the support
  helper, the new code, the per-claim rule, and one docstring durable-rule line.
- `backend/tests/test_generation.py` — modify: tests for scenarios 1–7 and 9.
- `backend/tests/fixtures/generation/drafts_ungrounded.json` — modify: add cases
  `numeric_fact_unsupported`, `numeric_fact_unsupported_month`, and
  `numeric_fact_unsupported_deadline_unit`.
- `backend/tests/test_local_generation.py` — modify: one `verifier_rejected` row in
  `_outcome_cases` (scenario 8).
- Docs below. **Do not change** anything listed in Non-goals.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed; it already describes verify-then-fallback through
  `verify_draft`, and no boundary changes.
- `docs/constraints/answers-and-knowledge.md`: update "Answer grounding" with one MUST: every
  number word, month, day–month or full written date, and day/week/month/year duration (with
  any `hábiles`/`naturales` qualifier) in a claim must appear, in an equivalent written form,
  in its cited passages, or the draft is discarded whole; `extract_figures` stays digit-only
  because abstention checks depend on it. Reason: this feature.
- `knowledge/README.md`: update the "Figures and dates are checked" bullet.
- `backend/README.md`: name the new rule in the generation paragraph's `verify_draft` sentence.
- `docs/risks-and-open-questions.md`: one clause in the "Unsupported or outdated legal answer"
  mitigation: numeric support is checked lexically; semantic support stays open.
- `docs/progress/known-limitations.md`: one line at acceptance: lexical and Spanish-only, it
  rejects some correct paraphrases (ranges, an added year), and it checks only time units.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `docs/constraints/operations.md`: not needed.

## Focused verification (required)

Needs the shared backend environment (`./scripts/init.sh --setup-python`); no Ollama, network,
or owner step. Line 1 runs the touched suites. Line 2 runs the report-only real-corpus
evaluation (exit `0`; compare its aggregates with the appendix baseline). Line 3 runs the full
backend suite, because `verify_draft` gates every answer path.

<!-- verify:start -->
```sh
./scripts/init.sh --backend-tests tests/test_generation.py tests/test_local_generation.py tests/test_gemini_generation.py tests/test_abstention.py tests/test_land_safety_eval.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-31 --k 5
./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`numeric_grounding_check.appendix.md`](numeric_grounding_check.appendix.md) for research,
plan, evidence, and the validator checklist.
