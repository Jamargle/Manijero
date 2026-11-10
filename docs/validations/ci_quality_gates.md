# Validation record: `ci_quality_gates`

- **Verdict:** accept (independent validator, round 3, 2026-11-11). The owner reviewed and approved
  the measured baseline on 2026-11-11; the review block, spec, and appendix now agree, and every
  measured number is unchanged. All earlier findings are resolved.
- **Reviewed:** worktree `ci_quality_gates`, branch `feature/ci_quality_gates`, HEAD `a71d78c`
  (on top of `427974e` and `799da54`, from `e8874ad`); `feature_list.json` stays `passing` (not
  `accepted`); I did not change it. Spec:
  [ci_quality_gates.md](../specs/ci_quality_gates.md); evidence:
  [appendix](../specs/ci_quality_gates.appendix.md) "Feature evidence".
- **Scope:** read-only for code. No push, `gh`, amend, or other worktree. I did not read
  `pilot-token.local` or `~/manijero/*/credentials/`.

## Reviewed baseline

- **Review block:** `reviewed_by: "Jose"`, `reviewed_on: "2026-11-11"`, reason
  `"approved by the owner in the batch 2 review on 2026-11-11"`
  (`backend/config/quality_gate_baseline.json:42-44`). `review_problem` returns `None`; the file is
  canonical; settings match.
- **Metrics:** fixtures 6/7 hit@1, 6/7 hit@3, 6/7 hit@5, MRR 0.8571, abstention 10/10; reviewed
  sample 9/12 hit@1, 11/12 hit@3, 11/12 hit@5, MRR 0.8333, abstention 5/5.
- **Unchanged:** `metrics`, `inputs`, `settings`, and `schema_version` are byte-identical to the
  previously validated baseline at `427974e` (and to `e8874ad`); only the three review fields moved
  from 2026-11-10 to 2026-11-11.

## Checks rerun

| Command | One-line result |
|---|---|
| `./scripts/init.sh --feature ci_quality_gates` | Exit 0; 25 tests passed (0.56 s); one pass line; baseline/knowledge/fixtures hashes unchanged. |
| `check_quality_gate.py check` | Exit 0; exactly one line, the committed numbers, `Baseline reviewed by Jose on 2026-11-11.` |
| `--backend-tests tests/test_quality_gate.py tests/test_check_quality_gate_command.py -q` | 25 passed (0.53 s); covers every hit@k/abstention/MRR drop, `record` guards, read-only checks, and the one-line contract. |
| Temp baselines with MRR `NaN`, `Infinity`, `-Infinity` | Each exit 2; one `baseline_invalid` line; no comparison, no write. |
| Temp baselines with reviewed hit@1 `10/12` and MRR `0.9000` | Each exit 1; one line naming the drop (`10/12 to 9/12`, `0.9000 to 0.8333`); no rewrite. |
| Temp `record` with an empty reviewer | Exit 2, `Result: baseline not recorded: the reviewer must be named.`; temp file unchanged. |
| Temp no-change `record` | Exit 0, `Result: baseline recorded: 0 metrics changed; reviewed by Jose on 2026-11-11.`; only the review block changed. |
| `./scripts/init.sh --fast` | Exit 0; 10/10 offline checks; 75 s; zero `quality gate` lines. |
| `./scripts/init.sh --verify` | Exit 0; 74 s; one gate line only: line 18 `Fast tier passed.`, line 21 pass line, line 23 full-tier heading, line 25 `Full tier passed.`; baseline hash unchanged. |
| Scope diff | `git diff main...HEAD -- .github/workflows/gate.yml knowledge/ backend/tests/fixtures/ contracts/ backend/requirements*.txt` is empty. |

The exact pass line is:

`Result: quality gate passed: fixtures 6/7 hit@1, 6/7 hit@3, 6/7 hit@5, MRR 0.8571; fixtures abstention 10/10; reviewed sample 9/12 hit@1, 11/12 hit@3, 11/12 hit@5, MRR 0.8333; reviewed sample abstention 5/5. Baseline reviewed by Jose on 2026-11-11.`

## Findings

### 1. Owner-review contradiction — resolved (Medium)

- The review block now records Jose as reviewer on 2026-11-11 with the owner's approval reason
  (`backend/config/quality_gate_baseline.json:42-44`), matching owner decisions 2 and 3
  (`docs/specs/ci_quality_gates.md:11-12`) and the revised spec paragraph
  (`docs/specs/ci_quality_gates.md:88`) and appendix entries
  (`docs/specs/ci_quality_gates.appendix.md:104,115-117`).
- No tracked file contains `personally reviewed` or `on the owner's behalf`; no quality-gate file
  contains `orchestrator recorded`/`orchestrator entered`. The remaining `recorded by the
  orchestrator` strings are in unrelated features' walkthrough docs (`local_load_test`,
  `backend_container_image`, `local_end_to_end_smoke`, `local_full_rag_stack`,
  `qa_service_alerts`) and do not describe this baseline.
- Every `owner-reviewed` reference (`docs/specs/ci_quality_gates.md:7,11,128`,
  `docs/progress/known-limitations.md:14`, `docs/risks-and-open-questions.md:51`,
  `backend/scripts/check_quality_gate.py:2`, `scripts/init.sh:882`) is now accurate: the owner did
  review and approve the measured baseline.

### 2. `PROGRESS.md` count and stale statuses — resolved (Low)

- `PROGRESS.md:62-65` says 5 `not_started`; `feature_list.json` has 114 accepted, 5 `not_started`,
  1 `on_hold`, and 1 `passing` (121 total). `local_load_test`, `rag_demo_rehearsal`, and
  `seed_corpus_expansion` are `accepted`.

### 3. Non-finite MRR — resolved (Low)

- `_validate_metrics` rejects a non-finite MRR as `baseline_invalid`
  (`backend/app/quality_gate.py:173-183`); `test_baseline_rejects_non_finite_mrr` covers
  `NaN`, `Infinity`, and `-Infinity` (`backend/tests/test_quality_gate.py:122-130`). The focused
  tests pass, and three temp baselines each exit 2 with one `baseline_invalid` line.

## Behavior and scope

- **Zero-tolerance rules:** unchanged. The only code change since `e8874ad` is the finite-MRR guard;
  the hit@k, abstention, and MRR comparison paths are untouched. The drop tests and the two temp
  baselines above confirm exit 1 with one naming line.
- **Read-only:** `--feature` and `--verify` leave the baseline, `knowledge/`, and fixtures
  byte-identical; the command tests assert the same.
- **`record` guard:** empty reviewer/reason still exits 2 without writing; a valid no-change
  re-record writes the canonical review block and reports `0 metrics changed`.
- **Tier wiring:** `--fast` prints zero gate lines; `--verify` runs the gate exactly once after the
  fast tier and before the builds.
- **Scope:** no changes to `gate.yml`, `knowledge/`, fixtures, `contracts/`, or dependencies. The
  full diff since `e8874ad` touches only `PROGRESS.md`, the gate module (NaN guard), the baseline
  (review block), the two gate test files, and the spec/appendix — all within the feature's declared
  scope.

## Residual risk

- Synthetic fixtures plus the author-reviewed 17-case sample prove only "these agreed numbers did not
  get worse"; legal correctness and real-user accuracy remain unmeasured.
- The owner approval is a recorded attestation. `record`/`check` validate its shape, not that the
  owner personally read the numbers; the commit author and the review block are the evidence.
- The owner review is dated 2026-11-11, one day after the original measurement. The feature is still
  `passing` and not accepted, so no accepted/merged gate ran before the review.
- The command test now reads the reviewer and date from the baseline instead of pinning them; a
  future accidental review-block change would not fail that test. This acceptance relies on direct
  inspection, the canonical JSON check, and the appendix evidence.
- Numeric fields are type/finiteness-checked but not range-checked (for example MRR above 1 or a
  count above its denominator would pass the schema). The committed baseline is valid, so this is an
  edge case.
- Branch protection is outside the repository and was not changed in this diff; it was not verifiable
  locally. Production `check` does not block sockets itself (tests do); the code opens no network
  path.

## Record

This file: `docs/validations/ci_quality_gates.md`. Raw evidence: appendix "Feature evidence" and
`build/verify-logs/` (gitignored).
