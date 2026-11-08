# Validation: question_rewriting

Spec: [question_rewriting.md](../specs/question_rewriting.md) · Appendix: [question_rewriting.appendix.md](../specs/question_rewriting.appendix.md)

## Verdict

`accept`, condition `pending owner walkthrough` (spec scenario 11). Validated 2026-11-08 by the independent validator; status stays `passing` until the owner reports the walkthrough matched the guide.

## Checks rerun

- `./scripts/init.sh --feature question_rewriting`: 278 passed; `glossary_review.py check` exit 0 (15 entries, all proposed; 66 cases checked, 0 improved).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 3021 passed, 9 skipped).
- `./scripts/init.sh --glossary-review`: lists 15 waiting pairs with plain labels and ends with the pinned `Result:` line.
- `--verify` not rerun: the diff touches only `backend/`, docs, and `scripts/init.sh` (no `shared/`, apps, Gradle, or packaging).

## Review against the spec

- Owner decisions: only `approved` pairs apply (`approved_count` gate in `ask_api._answer`); deterministic stdlib expansion, no model call; the original question is kept and official terms appended.
- Expansion lives inside `Retriever.search` via `with_query_expansion`, so screening, year, scope, presupposition, drafting, and response keep the original text. The cache identity gets the glossary suffix only. `release_gates.evaluation_app` is untouched, so gates stay glossary-free.
- Fail-closed loader and the off switch are in `main.py`. The log line carries only state, count, and a reason code, never a term.
- `question_glossary.py` imports the standard library and `app.retrieval` only. The `/ask` path does not import the review module, `notice_pipeline`, or `golden_set`. The one relaxed `test_notice_pipeline` guard is limited to the offline review module and is justified.
- `knowledge/`, `notice_pipeline.py`, `release_gates.py`, `contracts/`, and the apps are unchanged.
- Docs present: ARCHITECTURE, constraint MUST, owner guide (52 lines) plus README row, backend README, CONTEXT, known limitations, and the PROGRESS digest.

## Remaining limits

Only the owner walkthrough can show:
- the list and decide output reads clearly to the owner;
- the missing-name and unknown-number cases record nothing;
- the final `Result: no word pairs wait for your decision ...`;
- the approved/rejected counts, with `check` rerun to exit 0 on the resulting glossary.

Until then all 15 pairs are `proposed`, so expansion is a no-op. The effect on answers is unmeasured until `colloquial_ab_evaluation`.
