# Validation: adversarial_trap_set

Verdict: accept, condition `pending owner walkthrough` (spec scenario 7).
Spec: docs/specs/adversarial_trap_set.md. Evidence: docs/specs/adversarial_trap_set.appendix.md.

## Checks rerun (validator)
- `./scripts/init.sh --feature adversarial_trap_set`: passed (check: 26 drafts, abstained 19, answered 7; evaluator ran).
- `./scripts/init.sh --fast`: passed (3130 backend tests, 10 offline checks). `--verify` not rerun: no shared/, app, Gradle, or packaging change.
- `--traps` with zero approved: case rows equal the run without the flag (66 rows); `traps` block reports draft=26, approved=0.
- Source files `pac_answer_eval.json`, `golden_set.json`, `passages.json`, `source_catalog.json` unchanged.
- Only `evaluate_pac_answers.py` and `trap_review.py` import `trap_set`; no gate, release, demo, load, or judge path reads it.
- Evaluator diff: the no-flag path only gains a `row_extra=None` default, so its output is unchanged by inspection (not byte-compared against a pre-feature run).
- `test_question_glossary.py` exempt-list addition is consistent with the existing `golden_set.py` exemption.

## Remaining (only the owner walkthrough can show)
- The plain-Spanish list reads clearly to the owner.
- Decide, missing-input and unknown-number recovery behave as the guide says.
- Final `Result: no trap questions wait ...`; then commit decided `trap_set.json` and rerun `check` and `--traps`.

## Limits
- Cooperative-practice traps 013, 014, 016 are answered by /ask today: a baseline miss for the later calibration feature, not fixed here.
- All items are drafts; no trap is scored until approved.
