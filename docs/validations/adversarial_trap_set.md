# Validation: adversarial_trap_set

Verdict: accept. Condition `pending owner walkthrough` (spec scenario 7) met on 2026-11-10; the walkthrough was the final approval, so there was no second validator.
Spec: docs/specs/adversarial_trap_set.md. Evidence: docs/specs/adversarial_trap_set.appendix.md.

## Checks rerun (validator)
- `./scripts/init.sh --feature adversarial_trap_set`: passed (check: 26 drafts, abstained 19, answered 7; evaluator ran).
- `./scripts/init.sh --fast`: passed (3130 backend tests, 10 offline checks). `--verify` not rerun: no shared/, app, Gradle, or packaging change.
- `--traps` with zero approved: case rows equal the run without the flag (66 rows); `traps` block reports draft=26, approved=0.
- Source files `pac_answer_eval.json`, `golden_set.json`, `passages.json`, `source_catalog.json` unchanged.
- Only `evaluate_pac_answers.py` and `trap_review.py` import `trap_set`; no gate, release, demo, load, or judge path reads it.
- Evaluator diff: the no-flag path only gains a `row_extra=None` default, so its output is unchanged by inspection (not byte-compared against a pre-feature run).
- `test_question_glossary.py` exempt-list addition is consistent with the existing `golden_set.py` exemption.

## Owner walkthrough (2026-11-10)
- Owner `Jose` completed the trap-set review walkthrough and approved all 26 traps (0 rejected). The owner keeps the invented-personal-number traps; they only check abstention or an out-of-scope reply.
- `--trap-review` after the decisions: `Result: no trap questions wait for your decision (26 approved, 0 rejected).`
- Missing-input and unknown-number recovery: the owner reported only that the walkthrough was complete; their individual `Result:` lines were not reported.
- Decided `trap_set.json` committed (`7280eac`). Rerun `./scripts/init.sh --feature adversarial_trap_set`: passed, 121 tests, `trap check: 26 items OK`, approved=26.
- `--traps` by category (cases / state agreement / unexpected answers / reason matches / must-not-say hits): prompt_injection 7/7/0/7/0, false_premise 5/5/0/3/0, personal_advice 5/5/0/5/0, cooperative_practice 5/2/3/1/0, typo 4/4/0/0/0.

## Limits
- Cooperative-practice traps 013, 014, 016 are answered by /ask today: a baseline miss for the later calibration feature, not fixed here.
- All 26 traps are approved and scored only through the explicit `--traps` flag.
