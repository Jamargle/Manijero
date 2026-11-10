# Validation — `colloquial_ab_evaluation`

- **Verdict: accept** (independent validator, 2026-11-10, second round after repair `994c446`). Spec: [`colloquial_ab_evaluation.md`](../specs/colloquial_ab_evaluation.md); evidence: [`appendix`](../specs/colloquial_ab_evaluation.appendix.md) "Feature evidence".
- **Feature:** developer-only, report-only three-arm comparison over owner-approved colloquial variants, their approved golden parents, and the 26 approved traps; writes only `build/colloquial-ab/`; no default, gate, `/ask`, retrieval, glossary-default, or `knowledge/` change.
- **Accepted as:** developer tooling with honest evidence. The real owner-approved A/B has not run because the owner has decided 0 of 49 variants. That is an operational precondition recorded as residual risk, not a blocker: the code never scores a draft or rejected variant, and with zero approved it aborts with `no_approved_variants`.

## Repaired findings

1. **Pre-approval rehearsal recorded as evidence — fixed.** The appendix now states "No owner-approved A/B exists yet", 0 approved / 49 draft / 0 rejected, and calls the hand-edited approval "fabricated approval, not an owner decision". The 24/26/34 numbers are explicitly "not evidence" and "MUST NOT be cited as an owner measurement, used to choose an arm, or allowed to drive adoption". `build/colloquial-ab/REHEARSAL-NOT-EVIDENCE.txt` carries the same warning; `approved-rehearsal.json` has 49 `approved` entries with `reviewed_by: "rehearsal"`, and all rehearsal artifacts remain Git-ignored and uncommitted.
2. **Owner guide said to reject a variant that `check` still rejected — fixed.** `check_variants` now applies the scenario-2 content and duplicate-wording rules only to approved and draft entries; structural and coverage rules still run over every trusted entry. The owner guide says a rejected variant "is never scored and is exempt from the content check"; scenario 2 and the regression test say the same. Probe: a rejected `coll-001` with `colloquial_terms: ["palabra que no está"]` exits 0; the same entry as `draft` exits 1 with `coll-001: term_missing`; a rejected entry with `parent_id: "golden-999"` exits 1 with `coll-001: parent_id is not a golden item`.
3. **Appendix evidence named a test that does not exist — fixed.** The three cited command-walkthrough tests are real and pass: `test_list_waiting_pinned_line_and_full_list_file`, `test_decide_records_replaces_and_records_nothing_on_bad_input`, `test_missing_backend_environment_line_and_init_wiring`. `grep '^def test_'` confirms each against `backend/tests/test_colloquial_ab_command.py`; the new regression test `test_rejected_variant_keeps_structure_but_is_exempt_from_content_rules` also exists and passes.
4. **Fixture-directory drift — fixed.** `backend/tests/fixtures/colloquial_ab/` is absent, matching the appendix statement that it was intentionally not created because the tests build temporary copies and read the real `knowledge/` files read-only. The deviation is recorded, not presented as a missing artifact.

## Checks run

- `./scripts/init.sh --feature colloquial_ab_evaluation` — focused tier passed, `66 passed`; real `check` exit 0 with `49 variants OK (approved=0, draft=49, rejected=0); 49 approved golden parents, 49 covered, 0 orphans`.
- `./scripts/init.sh --fast` — all 10 offline checks passed; backend `3425 passed, 9 skipped`; harness `22 passed`.
- Rejected-variant CLI probe on a temporary copy — rejected invalid term exit 0 (`49 variants OK (approved=0, draft=48, rejected=1)`); draft invalid term exit 1 (`coll-001: term_missing`); rejected bad parent exit 1 (`coll-001: parent_id is not a golden item`).
- Socket-blocked `run` replay over the existing rehearsal cache — exit 0, one `Result:` line; hit@5 24/37 no rewriting, 26/37 glossary, 34/37 glossary+model; traps worse 2/2 (`trap-013`, `trap-016`); both verdicts `not adoptable (a trap got worse)`; `version_id 244592b70f8d5526`; two reruns byte-identical (`cmp` exit 0), no socket connected. This is tooling determinism, not owner evidence.
- Adoption/rule re-check — `git diff 41da97b..994c446 -- backend/app/colloquial_ab.py` changes only `check_variants`; adoption keeps the fixed 37-answer denominator, strict hit@5 gain, zero-trap-worse requirement, and separate `review_incomplete` / `no_effect` phrases. Report records `report_only: true` and `defaults_changed: false`; targeted tests `6 passed`.
- Read-only check — `git diff --quiet -- knowledge/` and `git diff --quiet -- backend/config/question_glossary.json` both exit 0; `git status --short` is empty before this record.
- Fixture check — `test -d backend/tests/fixtures/colloquial_ab` is false; appendix line records the deviation.
- `feature_list.json` remains `status: "passing"`; nothing was committed or pushed by this validation.

## Residual risk

- **No owner-approved A/B exists.** The owner has decided 0 of 49 variants; the real `prepare`/`run` must wait for recorded owner decisions. Until then the only run is the fabricated-approval rehearsal, whose counts are not evidence and must not drive an arm or an adoption decision.
- **Trust boundary is process, not code.** `review_state` is trusted; a hand-edited `approved` is indistinguishable from an owner decision. The rehearsal demonstrates that bypass; approval must remain an owner-recorded, committed decision.
- **Rejected variants can stay mechanically awkward.** They are exempt from content rules but still covered by structure/coverage and are never scored. A rejection is not a repair of the wording.
- Small agent-drafted set, BM25 extractive answers, one pinned local model on one Mac; no quality, legal, or adoption claim.
- **Documentation nit, not a blocker:** the appendix's "Tests to write (named by behavior)" plan retains its original planned names; several were merged or renamed during implementation. Those are plan labels, not evidence citations — every cited evidence name is real and every planned behavior has coverage.
- Earlier error-path polish items remain: a missing catalog/passages/cases/golden/traps file reports `internal_error`; the abort text says "Nothing was written" while writing `last-error.log`; a missing `--as-of` produces argparse usage text. These do not affect a metric-driven exit.
- Acceptance is validator-final (owner decision 5), with no owner walkthrough; the automated command walkthrough plus the checks above are the coverage.
