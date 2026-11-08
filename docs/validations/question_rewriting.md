# Validation: question_rewriting

Spec: [question_rewriting.md](../specs/question_rewriting.md) · Appendix: [question_rewriting.appendix.md](../specs/question_rewriting.appendix.md)

## Verdict

`accept` (spec scenario 11 satisfied). First validated 2026-11-08 pending the owner walkthrough; revalidated the same day after the owner completed it and the implementer repaired the tests the applied decisions broke. The orchestrator may persist `accepted`.

## Checks rerun

- `./scripts/init.sh --feature question_rewriting`: 278 passed; `glossary_review.py check` exit 0 (15 entries OK, proposed=0, approved=14, rejected=1; 66 cases checked, 3 improved).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 3021 passed, 9 skipped).
- Owner decisions in `backend/config/question_glossary.json`: 14 approved, 1 rejected (gl-002), each with `decision` matching `review_state`, reviewer, and date; no proposed entries remain.
- Test repair (`backend/tests/test_question_glossary_review.py`): `copy_committed` now strips decisions so list/decide tests no longer depend on owner choices; the committed-glossary test asserts a fully decided, consistent state; the `check` test pins the new counts. No test was removed or weakened.
- `--verify` not rerun: no `shared/`, apps, Gradle, or packaging changes.

## Review against the spec

- Owner decisions: only `approved` pairs apply (`approved_count` gate in `ask_api._answer`); deterministic stdlib expansion, no model call; the original question is kept and official terms appended.
- Expansion lives inside `Retriever.search` via `with_query_expansion`, so screening, year, scope, presupposition, drafting, and response keep the original text. The cache identity gets the glossary suffix only. `release_gates.evaluation_app` is untouched, so gates stay glossary-free.
- Fail-closed loader and the off switch are in `main.py`. The log line carries only state, count, and a reason code, never a term.
- `question_glossary.py` imports the standard library and `app.retrieval` only. The `/ask` path does not import the review module, `notice_pipeline`, or `golden_set`. The one relaxed `test_notice_pipeline` guard is limited to the offline review module and is justified.
- `knowledge/`, `notice_pipeline.py`, `release_gates.py`, `contracts/`, and the apps are unchanged.
- Docs present: ARCHITECTURE, constraint MUST, owner guide (52 lines) plus README row, backend README, CONTEXT, known limitations, and the PROGRESS digest.

## Owner walkthrough

2026-11-08, owner `Jose`, following `docs/owner-guide/question-glossary-review.md`: `--glossary-review` ends `Result: no word pairs wait for your decision (14 approved, 1 rejected).` (rejected `gl-002`). Glossary committed in `9551a21`; `check` rerun exit 0 with no regression. The missing-name and unknown-number results were not reported separately.

## Remaining limits

- Approved pairs now expand retrieval queries; the effect on answers is only partly measured (`check`: 3 of 66 cases improved) until `colloquial_ab_evaluation`.
