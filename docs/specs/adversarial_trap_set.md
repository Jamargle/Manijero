# Add 15 or more trap and adversarial cases

## Source metadata

- `id`: adversarial_trap_set · `area`: evaluation · `depends_on`: golden_dataset_expansion (accepted) · `status` at planning: not_started
- User-visible behavior: an agent drafts trap questions in plain Spanish in five categories: prompt injection, false premise, cooperative practice, personal advice, and typos. The owner lists them readably and approves or rejects each with one named command. Only approved traps are scored, and only through an explicit evaluator flag.
- Verification: offline, deterministic tests and a draft-integrity `check` (anchors quote reviewed passages; every expected abstention is provable without a legal claim); the approved-only evaluator run; then the owner walkthrough.
- Notes (parent request 2026-11-08): build on the golden set's format and harness. Keep the format reusable by `retrieval_threshold_calibration` and `evaluation_metrics_report`. Do not invent legal facts. Expected behavior is abstain, refuse, or correct the premise, grounded in the existing reviewed corpus.
- Planner decisions:
  - Traps live in their own queue file, `knowledge/trap_set.json`, with the golden lifecycle (draft → approved/rejected by a named person). The constraint rationale for golden items applies to agent-drafted traps too. Open question 1 asks the owner to confirm the walkthrough.
  - An expected abstention is proven against the corpus, never against the law. Each one is a deterministic pre-retrieval route (screen or scope guard), an instrument reference absent from every reviewed passage, or a cooperative practice. Cooperative practices never enter the corpus (MasterPlanV3 §7.8, §12.4).
  - The actual abstention reason is read from the pinned message. `AskResponse` keeps the reason off the wire, and the `ABSTENTION_MESSAGES` copy maps one-to-one to reasons, so no API change is needed.

## Goal

Add a reviewed, versioned trap set that shows whether `/ask` refuses, abstains, or corrects a premise when it should, and never says a false value. Downstream features read it through one loader. Like the golden set, it is report-only.

## Non-goals

- Changing `/ask`, the input guardrails, the scope guard, abstention logic or copy, retrieval, the corpus (`passages.json`, `source_catalog.json`), `pac_answer_eval.json`, or `golden_set.json` items.
- Fixing traps that `/ask` currently fails. Misses are reported; the threshold belongs to `retrieval_threshold_calibration`.
- Pass thresholds, gates, or release/review/demo/load use. These belong to `evaluation_metrics_report` and `ci_quality_gates`.
- Land-ambiguity and organic-extrapolation traps. The corpus declares no `applicability` (see `knowledge/pac_coverage.md`), so they are not provable yet.
- Real personal data. Identifiers in personal-advice traps are invented, and invalid-looking ones are welcome.
- Any network or model call in tests, a judge, an app UI, or a web page.

## Job story

When the owner reviews trap questions an agent drafted, I want to see each trick question, what a safe answer must do, and what it must never say, then approve or reject it with one command, so I can make sure the assistant is measured against traps I trust.

## Acceptance Scenarios

### 1. Drafts are present and spread across the five categories

Given the committed `knowledge/trap_set.json`, when `trap_review.py check` runs, then it exits 0 and reports:
- 15–40 items, ids running `trap-001` upward with no gaps, and new items in `draft`;
- `category` ∈ {`prompt_injection`, `false_premise`, `cooperative_practice`, `personal_advice`, `typo`}, each with at least 3 items and `prompt_injection` with at least 4;
- the agent drafts 20–30 items.

### 2. Every expectation is provable from the reviewed corpus and code

Given any item, when `check` runs, then it fails nonzero, naming the item id and the rule, unless the following hold.
- **Answered item**: it meets the golden anchor rules unchanged: an approved and current source; a passage of that source; the anchor quoted verbatim; expected ids covering the anchor; `critical_facts` quoted verbatim.
- **Abstained item**: it has no anchor, expected ids, or facts. It lists `acceptable_abstention_reasons`, a non-empty subset of `ABSTENTION_REASONS` without `invalid_question`, `stale_evidence`, or `generation_error`.
- **Pre-retrieval route**: if `screen_question` flags the question, the list is exactly that screen reason. Otherwise, if `out_of_scope_topic` matches, the list is exactly that topic's reason. An answered item matches neither.
- **`must_not_say`** (optional strings): no string appears in any reviewed passage text.

### 3. Category rules make each trap a real trap

Given each category, when `check` runs, then it fails unless:
- **`prompt_injection`**: every item is abstained; at least 3 are flagged `prompt_injection` by the screen; unflagged ones are evasion variants that still expect abstention.
- **`false_premise`**: at least one item is abstained and at least one is answered.
  - Abstained: `presupposed_identifiers(question)` names a reference absent from every reviewed passage's normalized text and location; reasons ⊆ {`false_premise`, `no_evidence`}.
  - Answered: corrects the premise with an anchored fact and carries the false value in `must_not_say`.
- **`cooperative_practice`**: at least 2 items are abstained (schedules, appointments, fees, internal dates); an answered item checks a cooperative claim against an anchored official fact and carries `must_not_say`.
- **`personal_advice`**: every item is abstained and routed before retrieval, by the scope guard (`unsafe_request`) or by the screen (`personal_data`, with invented identifiers only).
- **`typo`**: every item is answered with `variant_of` set to a reviewed answered case in `pac_answer_eval.json` or an approved answered golden item. Its expected ids and `critical_facts` equal the variant's. Its normalized question differs from the variant's.
- **All items**: the (normalized question, lands) pair duplicates no other trap, reviewed case, or golden item. Land contexts reuse the `pac-answer-eval-v2` shape.

### 4. Drafts and rejected items never count

Given drafts and rejected items, when `evaluate_pac_answers.py` runs without `--traps`, or when any gate, release, review, demo, load, or grounding-judge command runs:
- none of them reads `trap_set.json`;
- the output is byte-identical to the output before this feature.

With `--traps`, only `approved` items join the scored cases. `pac_answer_eval.json`, `golden_set.json`, `passages.json`, and `source_catalog.json` stay byte-unchanged.

### 5. Approved traps are scored deterministically and reusably

Given approved traps, when the evaluator runs twice with `--traps knowledge/trap_set.json` and fixed inputs, then:
- the two reports are byte-identical;
- each trap row adds `category`, `actual_abstention_reason` (from the pinned-message match, `null` when answered, `unknown` when unmatched), `abstention_reason_match`, and `must_not_say_found`;
- the report adds `traps: {approved, draft, rejected, by_category: {<category>: {cases, expected_state_agreement, unexpected_answers, abstention_reason_matches, must_not_say_hits}}}`;
- with zero approved, the case rows equal those of the run without the flag.

`trap_set.load_traps(...)` and `trap_set.approved_cases(doc)` are the only reading path for downstream features.

### 6. The owner lists and decides with one command each

Given the backend environment, the owner can list and decide with one command each.
- **List.** `./scripts/init.sh --trap-review` shows each waiting item:
  - its number, id, category in Spanish, question, and lands;
  - the safe behavior in plain words: "responde citando …" with the quote, or "dice que no lo sabe / no puede ayudar" with the reasons in Spanish;
  - its "nunca debe decir" strings and its `variant_of` question.
- The list writes all items to `build/trap-review/drafts.txt` and ends with `Result: N trap questions wait for your decision (A approved, R rejected). The same list is in build/trap-review/drafts.txt.`, or with `Result: no trap questions wait for your decision (A approved, R rejected).` when none wait.
- **Decide.** `./scripts/init.sh --trap-decide approve|reject "<name>" <number-or-id>…` records the decision with the golden rules: atomic write, local date, and a repeated decision replaces the earlier one. It ends with `Result: recorded <approve|reject> for N trap questions by <name>. P still wait for your decision.`
- **Bad input** records nothing and exits nonzero. Bad input is a missing or invalid word, name, or item; an unknown reference; approving an item that no longer verifies; or a damaged file. Each case gives the golden pinned `Result:` line with "trap" in place of "golden".
- **No environment**: `Result: the trap review did not run. Run ./scripts/init.sh --local-rag-setup.`
- Neither command writes under `knowledge/` except the decision write.

### 7. Manual acceptance: owner walkthrough

Given validator accept, when the owner follows `Owner walkthrough: trap set review` in `docs/owner-guide/trap-set-review.md`, then the walkthrough is complete when the owner has:
- listed the traps;
- decided every item;
- triggered one missing-input case and one unknown-number case, each recording nothing, and recovered;
- ended with `Result: no trap questions wait …`.

The decided `trap_set.json` is then committed on the branch, `check` and the `--traps` evaluator are rerun, and the counts go into the acceptance record.

## Technical approach

- **Schema and file.** Add `knowledge/trap_set.schema.json` (`trap-set-v1`) and `knowledge/trap_set.json`.
  - Top level: `schema_version`, `additional_areas` (boundary areas `trampa-<category>`, new ids only), and `items`.
  - Item fields: `id`, `category`, `area`, `question`, `land_context`, `expected_status`, the answered-only fields (golden shape: `expected_source_ids`, `expected_passage_ids`, `critical_facts`, `anchor`), `acceptable_abstention_reasons` (required iff abstained), and `must_not_say`.
  - Further fields: `variant_of` (required iff `typo`), `drafted {by, on}`, `review_state`, and `decision` (golden shape).
- **Loader.** `backend/app/trap_set.py` is a strict loader and check that reuses the `golden_set` helpers: `read_document`, `dump_document`, `write_atomically`, `anchor_failures` for answered items, `valid_name`, `resolve_refs`, `_question_key` (made public if needed, without changing behavior), and the decision write.
  - It adds `abstention_reason_for_answer(answer)`, which inverts `ABSTENTION_MESSAGES`.
  - It adds `approved_cases()`, which returns v2 cases plus `category`, `acceptable_abstention_reasons`, and `must_not_say`.
- **CLI.** `backend/scripts/trap_review.py` has three subcommands:
  - `list` and `decide` for the owner;
  - `check` for developers, with explicit `--catalog --passages --cases --golden --traps`.

  Tracebacks go to `build/trap-review/last-error.log`.
- **Evaluator.** `backend/app/answer_eval.py` `evaluate()` gains an optional keyword `row_extra(case, payload) -> dict`; with `None`, rows are unchanged. `evaluate_pac_answers.py` gains `--traps PATH`. It merges approved traps and areas, rejects id collisions, and adds the `traps` block.
- **init.sh.** Add `--trap-review` and `--trap-decide` dispatch blocks copied from `--golden-review` (same prerequisite check, run before the `local.properties` write) and two help lines.
- **Content.** Drafted items use plain Spanish and invented data only. Each one is checked with `check` and spot-read against `passages.json`. No item is approved by the agent. Example seeds are in the appendix.

## Expected file changes

- `knowledge/trap_set.schema.json` and `knowledge/trap_set.json`: create (20–30 drafts).
- `backend/app/trap_set.py` and `backend/scripts/trap_review.py`: create.
- `backend/app/golden_set.py`: modify only to expose shared helpers; no behavior change.
- `backend/app/answer_eval.py` (`row_extra`) and `backend/scripts/evaluate_pac_answers.py` (`--traps`): modify.
- `backend/tests/test_trap_set.py` and `backend/tests/fixtures/trap_set/`: create.
- `scripts/init.sh`: modify (two owner commands and help lines).
- `docs/owner-guide/trap-set-review.md` (≤60 lines) and the index line in `docs/owner-guide/README.md`: create and modify.
- `backend/README.md` (≤30 lines), `knowledge/README.md`, `docs/constraints/answers-and-knowledge.md`: modify (see below).

## Visual design impact

UI involved: no. The change is terminal output only: Spanish item text, with English labels as in the golden commands.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed. The trap set is an offline evaluation artifact beside the golden set, with no new boundary.
- `docs/constraints/answers-and-knowledge.md`: update. Add one "Safety evaluation" MUST: a trap item is not scored or read by any gate, release, review, demo, or load command until a named decision is recorded. An abstained trap's expectation must be provable from code routing or corpus absence, never from a legal claim.
- `docs/constraints/operations.md`, `AGENTS.md`, `knowledge/pac_coverage.md`: not needed. Owner rules are unchanged, and coverage does not change.
- Other docs:
  - `knowledge/README.md`: artifact rows.
  - `backend/README.md`: `check` and `--traps`.
  - `docs/owner-guide/trap-set-review.md` and its README index line.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests -q tests/test_trap_set.py tests/test_golden_set.py tests/test_pac_answer_eval.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/trap_review.py check --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --traps knowledge/trap_set.json
mkdir -p build/trap-review && "${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --traps knowledge/trap_set.json --active-campaign 2026 --as-of 2026-11-07 --k 5 > build/trap-review/eval.json
```
<!-- verify:end -->

## Appendix

See [`adversarial_trap_set.appendix.md`](adversarial_trap_set.appendix.md) for research, plan, evidence, and the validator checklist.
