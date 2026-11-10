# Acceptance record: `reranker_evaluation`

- **Verdict:** accept (validator, 2026-11-10, condition `pending owner walkthrough`); the condition was met by the owner's run on 2026-11-10, accepted with no second validator. Spec: [reranker_evaluation.md](../specs/reranker_evaluation.md); evidence: [appendix](../specs/reranker_evaluation.appendix.md) "Feature evidence".
- The reranker stays OFF (`default_state: "off"`, unchanged) because rule 3 failed. The result is kept as a recorded experiment.

## Recorded experiment (owner run, 2026-11-10)

The owner ran `./scripts/init.sh --reranker-download` and `./scripts/init.sh --reranker-measure`. Result line, verbatim:

> Result: reranker measured on 49 golden and 26 trap questions against today's hybrid search. Right source found: 29 today, 30 with the reranker (+1). Golden questions broken: 1. Trap questions worse: 0. Slowest extra time: 2.0 seconds. Verdict: OFF - fewer than 2 more golden questions found their right source; a golden question that worked today broke; slower than 2 extra seconds. It stays off and this result is kept as a recorded experiment. Send this line to the developer.

- Rule-3 decision: OFF (gain +1, needs 2; 1 golden question broken). Trap questions worse: 0.
- "2.0 seconds" with "slower than 2 extra seconds" is correct, not a wrong comparison: the check is strict (`slowest_extra_seconds > 2.0` fails; exactly 2.0 s passes, pinned by `test_on_at_exactly_the_boundaries`), and the line prints one decimal, so the measured time was above 2.0 s and at most 2.05 s. No code change; the verdict is OFF on the other two rules anyway.
- Not reported by the owner: download output, machine details, memory use.

## Checks rerun

- `./scripts/init.sh --feature reranker_evaluation`: 463 passed; `check-pin`: valid (6 files, 2.3 GB, revision 953dc6f6f85a).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend-tests 3312 passed, 9 skipped).
- `--verify` not rerun: no `shared/`, Android, Desktop, Gradle, or packaging change.
- Pin values (revision, sizes, SHA-256, git-blob SHA-1) compared with `build/reranker-metadata.json`: all match. No change under `knowledge/`, `contracts/`, `shared/`, `backend/container/`, `requirements*`.
- Code read: `reranker_measure.py` computes rule 3 exactly (gain >= 2, broken == 0, trap worse == 0, slowest <= 2.0 s) with reasons in the fixed order; BM25 fallback stops with no verdict.

## Owner run

- The real download and the real model load completed (the measure command prints a verdict only after both), recorded above. Memory use of `bge-m3` plus the reranker was not reported.

## Notes

- Owner guide is 61 lines (spec budget 60); plain language, one named command each, on/off explained. Not blocking.
