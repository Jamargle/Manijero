# Validation: validity_regression_cases

- Verdict: **accept** (2026-11-08, independent validator). Developer-only; no owner walkthrough. Spec: [`../specs/validity_regression_cases.md`](../specs/validity_regression_cases.md); evidence: [appendix](../specs/validity_regression_cases.appendix.md).

## Checks rerun

- `./scripts/init.sh --feature validity_regression_cases`: 150 passed; evaluator exits 0 at as-of 2026-10-26: 17 cases, 17/17 expected states, 12 answered, 5 abstained, 9 source/passage matches, 10 critical-fact matches, 0 unexpected answers.
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend 2530 passed, 7 skipped; harness 20 passed).
- `--verify` not rerun: diff touches no `shared/`, Android, Desktop, Gradle, or packaging files.
- Diff review: `backend/app/**`, `source_catalog.json`, `passages.json` unchanged; eval-set additions match the spec text; pre-existing 14 rows unchanged.

## Spec points

- Case 1 (RD 1077/2014) and case 3 (cuaderno digital) abstain with `no_evidence`; no legal claim about repeal or voluntariness is made in any copy. Gaps recorded in `knowledge/pac_coverage.md`; the precondition test fails if a source appears.
- Case 2 cites `dl_1_2026` with the expired notice at as-of 2026-10-26 and no expired prefix on 2026-05-15.
- Approved changes applied: case 1 is `no_evidence`; `backend/README.md` line ~1090 (historical measurement) stays at 14 cases; the network guard patches `connect`, `connect_ex`, `create_connection`, and `getaddrinfo` (the in-process TestClient needs local socketpairs).
- Security/privacy: no relevant issues (test and data only; no secrets, no network).

## Limits that remain

- Review role is author-only; no independent legal review.
- Non-blocking: `backend/README.md` line ~2301 still says "14-case author-only sample" for the current evaluation. Update to 17 with the status-board count updates (`PROGRESS.md`, `current-state.md`, `known-limitations.md`).
