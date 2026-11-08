# Grow the reviewed golden set to 40–60 source-anchored questions

## Source metadata

- `id`: golden_dataset_expansion · `area`: evaluation · `depends_on`: seed_corpus_expansion, backend_answer_evaluation (both accepted) · `status` at planning: not_started
- User-visible behavior: an agent drafts 40–60 plain-Spanish golden questions anchored to the reviewed corpus; the owner lists them in readable form and approves or rejects each with one named command; only approved items are scored.
- Verification: offline tests and a draft-integrity check (anchors exist and quote the reviewed passage); the approved-only evaluator run; then the owner walkthrough.
- Notes — owner decisions 2026-11-07 (binding):
  - The session drafts 40–60 golden questions in plain Spanish. Each one is anchored to a source and passage already in the reviewed corpus. Never invent legal facts: no question may have an answer that is missing from a reviewed source, except deliberate abstention cases marked as such. The drafts are spread across the existing segments and these question types: procedure, deadline, eligibility caveat, land-dependent, out-of-scope/abstention, colloquial wording.
  - New items are marked draft. They are excluded from scoring and from every gate until a named human reviewer approves them. Existing reviewed items are untouched.
  - The owner gets one plain command that lists the drafts for review in readable form, and one that records approve/reject per item (no hand-editing of JSON). Each ends with one `Result:` line. The owner guide gets a section titled `Owner walkthrough: golden set review`.
  - Tests are offline and deterministic, with no model or network.
  - Acceptance: validator accept plus the owner review walkthrough, where the owner approves or rejects the drafts. Only approved items count.
- Notes — integration repair 2026-11-08: `validity_regression_cases` added the areas `norma-derogada`, `plazo-vencido`, and `cuaderno-digital-fuera-de-alcance`, so the unchanged distribution rule (every reviewed area used) failed. Fix: draft items `golden-047` to `golden-049` (one per area, `draft`, no decision) and the case-id abstention basis above. The 46 existing items are unchanged; the 3 drafts await the owner's `--golden-decide`.
- Planner decisions: drafts live in a separate queue file, so no existing consumer of `knowledge/pac_answer_eval.json` (release gates, review merge, demo, load test, guard tests with fixed counts) can see them. Approved items are scored through an explicit evaluator flag. Feeding approved items into the release and review gates is left to `evaluation_metrics_report` / `ci_quality_gates`.

## Goal

Give later evaluation features (`adversarial_trap_set`, `retrieval_threshold_calibration`, `reranker_evaluation`, `semantic_grounding_judge`, `evaluation_metrics_report`) a larger golden set. Every answered item must quote a reviewed passage verbatim, and no item may count until a named person approves it.

## Non-goals

- Changing `knowledge/pac_answer_eval.json`, its schema, its 14 cases, its coverage or omissions, `source_catalog.json`, `passages.json`, the corpus, retrieval, the scope guard, input guardrails, or `/ask`.
- Adding approved items to `release_gates.py`, `knowledge_review.py`, the release manifest, demo rehearsal, or load test inputs.
- Trap/adversarial cases (injection, personal data, false premise, typos). Those belong to `adversarial_trap_set`.
- `needs_land_clarification` items. The reviewed corpus declares no `applicability`, so land-dependent items expect the same answer for every land (see `knowledge/pac_coverage.md`).
- Numeric pass thresholds, quality claims, legal review, a model judge, generated expected answers, or any network/model call.
- An app UI, or a web review page.

## Job story

When the owner reviews golden questions an agent drafted, I want to read each question beside the exact official sentence it relies on and say approve or reject with one command, so I can ensure only questions I trust count in the evaluation.

## Acceptance Scenarios

### 1. Source-anchored drafts are present and spread out

Given the committed `knowledge/golden_set.json` · When `golden_review.py check` runs · Then it exits 0 and reports these properties:
- 40–60 items, all `draft`, ids `golden-001`… numbered without gaps.
- Each `question_type` meets its minimum: procedure ≥6, deadline ≥8, eligibility_caveat ≥4, land_dependent ≥5, out_of_scope ≥6, colloquial ≥6.
- Each `segment` (`secano-convencional`, `regadio-convencional`, `ecologico`, `transversal`) has ≥3 items.
- Each of the 7 reviewed passages is the anchor of ≥2 answered items, and each of the 8 declared coverage areas is used at least once.

### 2. Every anchor is proven against the reviewed corpus

Given any item · When checked · Then the check fails, nonzero and naming the item id and rule, unless all of these hold:
- An answered item has an `anchor` whose `source_id` is an `approved`, `current` catalog source.
- Its `passage_id` exists in `knowledge/passages.json` with that same source.
- Its anchor `text` is an exact substring of that passage's text.
- `expected_passage_ids` contains the anchor passage, and `expected_source_ids` covers every expected passage's source.
- Every `critical_facts` string is an exact substring of an expected passage.
- An abstention item has no anchor, expected sources, or facts, and declares `deliberate_abstention.basis` equal to one of `pac_answer_eval.json` `coverage.omissions`, or equal to the id of a reviewed case in that file with the same `area` and `expected_status: "abstained"` (integration repair 2026-11-08). Any other basis fails.

### 3. Drafts are safe questions, not traps

Given any item · When checked · Then the check fails if any of these holds:
- `app.input_guardrails.screen_question` flags it.
- An answered item matches `app.question_scope.out_of_scope_topic`.
- Its (normalized question, land context) pair duplicates another item or an existing reviewed case.
- `area` is undeclared. Declared areas are the base areas plus the golden file's `additional_areas`, which are `topic` kind and new ids only.

### 4. Drafts and rejected items never count

Given drafts and rejected items · When `evaluate_pac_answers.py` runs without `--golden`, or any gate, release, review, demo, or load command runs · Then none reads `golden_set.json`, and output is byte-identical to before this feature. With `--golden`, only `approved` items join the scored cases. `knowledge/pac_answer_eval.json` stays byte-unchanged.

### 5. Approved items are scored deterministically

Given approved items · When `evaluate_pac_answers.py … --golden knowledge/golden_set.json` runs twice with fixed inputs · Then the two reports are byte-identical, and each approved item appears as a case under its id and area, using the existing report semantics (report-only). The report adds `golden: {approved, draft, rejected}` counts. With zero approved, case rows equal the no-flag run.

### 6. The owner lists drafts readably

Given the backend environment is set up · When the owner runs `./scripts/init.sh --golden-review` · Then the terminal shows each waiting item with:
- its number, id, type, segment, and area,
- the Spanish question and its lands, if any,
- the expected outcome in plain words, either an answer or a deliberate "no lo sé" with its basis,
- the source title, location, and official link,
- the quoted anchor text and the must-say facts.

The same list for all items, with their state, is written to `build/golden-review/drafts.txt`. The command ends with `Result: N golden questions wait for your decision (A approved, R rejected). The same list is in build/golden-review/drafts.txt.`, or with `Result: no golden questions wait for your decision (A approved, R rejected).` when none wait. It writes nothing under `knowledge/`.

### 7. The owner records decisions with one command

Given waiting items · When the owner runs `./scripts/init.sh --golden-decide approve|reject "<name>" <number-or-id>…` · Then each listed item gets state `approved` or `rejected` with `decision: {decision, reviewed_by, reviewed_on}`, where `reviewed_on` is the local date. The file is rewritten atomically with stable formatting, and the command ends with `Result: recorded <approve|reject> for N golden questions by <name>. P still wait for your decision.` A repeated decision replaces the earlier one.

### 8. Bad decision input records nothing

Given any of these inputs:
- a missing or invalid decision word,
- a missing or invalid name (1–80 characters; letters, spaces, `.`, `-`, `'`),
- no item,
- an unknown number or id,
- an approval of an item whose anchor no longer verifies,
- a damaged file.

When `--golden-decide` runs · Then nothing is written, it exits nonzero, and it ends with one pinned `Result:` line naming the fix (pinned lines in the owner guide table). If the backend environment is missing, both commands end with `Result: the golden review did not run. Run ./scripts/init.sh --local-rag-setup.`

### 9. Manual acceptance: owner walkthrough

Given the validator has accepted the feature · When the owner follows `Owner walkthrough: golden set review` in `docs/owner-guide.md` · Then the walkthrough is complete when the owner has done all of these:
- listed the drafts,
- approved or rejected every item,
- triggered one missing-input case and one unknown-number case, each recording nothing,
- recovered from them,
- ended with `Result: no golden questions wait for your decision …`.

The resulting `knowledge/golden_set.json` is then committed on the feature branch, `check` and the `--golden` evaluator are rerun, and the approved/rejected counts are recorded in the acceptance record. This walkthrough is the manual acceptance check.

## Technical approach

- Add the `knowledge/golden_set.schema.json` (`golden-set-v1`) and `knowledge/golden_set.json` artifacts. The top level is `schema_version`, `additional_areas`, and `items`.
  - Item fields are `id`, `question_type`, `segment`, `area`, `question`, `land_context`, `expected_status` (`answered` or `abstained`), the optional `expected_source_ids`, `expected_passage_ids`, and `critical_facts`, then `anchor` (required iff answered), `deliberate_abstention` (required iff abstained), `drafted {by, on}`, `review_state`, and `decision` (required iff not `draft`).
  - Land contexts reuse the `pac-answer-eval-v2` shape.
- `backend/app/golden_set.py` is a strict, standard-library loader (except where it imports `screen_question` and `out_of_scope_topic` for the check). It covers validation, anchor and distribution checks, `approved_cases()` (each converted to a v2 case with `review.role = "author_only"` and `reviewed_by` / `reviewed_on` from the decision), readable rendering, and an atomic decision write. The clock is injected; the CLI uses the local date.
- `backend/scripts/golden_review.py` has three subcommands:
  - `list` (owner)
  - `decide` (owner)
  - `check` (developer/validator: explicit `--catalog --passages --cases --golden`, exit 0/1, one line per failure)

  Raw tracebacks go to `build/golden-review/last-error.log`.
- `scripts/init.sh`: `--golden-review` and `--golden-decide` dispatch blocks mirror `--demo-rehearsal` (backend venv or `python-env.sh dev --if-present`; run before the `local.properties` write). Add two help lines under `--check`.
- `backend/scripts/evaluate_pac_answers.py`: optional `--golden PATH` merges approved cases and `additional_areas` into the loaded cases and coverage. Ids must not collide with base cases. Without the flag, the code path is unchanged.
- Item content follows MasterPlanV3 §12.1. Questions are plain Spanish with no personal or real land data. Land-dependent items use synthetic land ids with dryland/irrigated/organic attributes. Eligibility-caveat items either anchor to a passage that states the caveat (for example, the persona física exception) or deliberately abstain on `elegibilidad individual`. Owner-command rules: [operations constraints](../constraints/operations.md).

## Expected file changes

- `knowledge/golden_set.schema.json`, `knowledge/golden_set.json` — create; queue schema and 40–60 draft items.
- `backend/app/golden_set.py`, `backend/scripts/golden_review.py` — create; loader/checks/render/decide and CLI.
- `backend/scripts/evaluate_pac_answers.py` — modify; optional `--golden`.
- `backend/tests/test_golden_set.py`, `backend/tests/fixtures/golden_set/` — create; offline tests on fixture corpus and the canonical file.
- `scripts/init.sh` — modify; two owner commands and help lines.
- `docs/owner-guide.md` — modify; "Review the golden questions" and "Owner walkthrough: golden set review" (≤60 lines together).
- `backend/README.md` (≤30 lines), `knowledge/README.md`, `knowledge/pac_coverage.md` — modify; see below.

## Visual design impact

UI involved: no. Terminal output only; Spanish item text, English labels like the other owner commands.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed — no new boundary; an offline evaluation artifact beside `pac_answer_eval.json`.
- `docs/constraints/answers-and-knowledge.md`: update — add one "Safety evaluation" MUST: a golden item is not scored or read by any gate until a named reviewer's decision is recorded by the decide command, and an answered item's anchor must quote an approved, current passage verbatim.
- `docs/constraints/operations.md`: not needed — the existing owner-operability rules apply unchanged.
- `AGENTS.md`: not needed.
- Other: `knowledge/README.md` (artifact table rows and the draft→approved rule), `knowledge/pac_coverage.md` (a short Spanish section: drafts do not count, plus approved counts after the walkthrough), `backend/README.md` (`check` and `--golden`), `docs/owner-guide.md`.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests -q tests/test_golden_set.py tests/test_pac_answer_eval.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/golden_review.py check --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --active-campaign 2026 --as-of 2026-11-07 --k 5
```
<!-- verify:end -->

## Appendix

See [`golden_dataset_expansion.appendix.md`](golden_dataset_expansion.appendix.md) for research, plan, evidence, and the validator checklist.
