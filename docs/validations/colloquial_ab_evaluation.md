# Validation — `colloquial_ab_evaluation`

- **Verdict: revise** (independent validator, 2026-11-10). Spec: [`colloquial_ab_evaluation.md`](../specs/colloquial_ab_evaluation.md); evidence: [`appendix`](../specs/colloquial_ab_evaluation.appendix.md) "Feature evidence". The code satisfies scenarios 1–9, but scenario 10 is not met and the recorded real run was made before the owner approved any variant. The repair is evidence/process work; no runtime redesign is needed.
- **Feature:** developer-only, report-only three-arm comparison over owner-approved colloquial variants, their approved golden parents, and the 26 approved traps; writes only `build/colloquial-ab/`; no default, gate, `/ask`, retrieval, glossary-default, or `knowledge/` change.

## Checks rerun

- `./scripts/init.sh --feature colloquial_ab_evaluation` — focused tier passed; `65 passed`; `check` exit 0 with `49 variants OK (approved=0, draft=49, rejected=0); 49 approved golden parents, 49 covered, 0 orphans`; `git diff --quiet -- knowledge/` exit 0.
- `./scripts/init.sh --fast` — all 10 offline checks passed; backend `3424 passed, 9 skipped`; harness `22 passed`.
- `backend/.venv/bin/python backend/scripts/colloquial_ab.py check ... --variants backend/config/colloquial_variants.json` — exit 0, same 49-variant line; committed set has 49 items, 0 approved, 49 draft, 0 decisions, exact seven-key shape, and the golden digest matches.
- Real `run` replay with sockets disabled over the existing developer cache — exit 0, one `Result:` line; hit@5 24/37 no rewriting, 26/37 glossary, 34/37 glossary+model; 2/2 trap regressions (`trap-013`, `trap-016`); both verdicts `not adoptable (a trap got worse)`; `version_id 244592b70f8d5526`; second run byte-identical; no socket opened.
- `prepare` on the committed all-draft set and on an all-rejected copy — exit 2, pinned `no_approved_variants` line, no files written; `run` behaves the same.
- Mixed one-approved-plus-poison-draft `prepare` — exit 0; rewriter called once; poison question never sent; cache contains only `coll-001`, ids/terms/status, and no question text.
- `prepare` with a rewriter raising `OSError` — exit 2, pinned `model_unavailable` line, no cache written.
- Independent recomputation from `report.json` rows — every arm has 124 rows, 37 answered colloquial variants, and hits 24/26/34; `sha256(canonical version JSON)[:16]` reproduces `244592b70f8d5526`; cache key `119997fc11857103` reproduces from the cache's model/digest and the approved cases.
- Trap rule — the two candidate arms both improve hit@5 but each has two trap regressions, so both stay `adoptable: false`, `reason: trap_worse`; unit coverage also covers improved-with-regression, no-gain, no-effect, and incomplete-review.
- `git diff --quiet -- knowledge/` and `git diff --quiet -- backend/config/question_glossary.json` — both exit 0; `git status --short` is clean apart from this validation record.

## Acceptance scenarios

1. One variant per approved golden item — **pass**: 49 ids `coll-001`…`coll-049`, 49 approved parents used once, no orphan/duplicate, digest bound, exact stored keys, all draft.
2. New plain wording of the same need — **pass**: the check enforces length, single line, screen, digit/URL, duplicate, answer/omission, and 1–4 contiguous new terms; focused tests cover each rule.
3. Owner lists and decides — **pass**: pinned waiting/closed/recorded/no-environment lines, atomic `decide`, repeat replaces, bad input/unknown ref/damaged file/approval-of-invalid records nothing, full list in `build/colloquial-ab/variants.txt`.
4. Unapproved variants never scored — **pass in code**: drafts/rejected are filtered before `prepare`/`run`; zero approved aborts and writes nothing; the mixed poison probe proves the rewriter never sees a draft. **The recorded evidence run bypassed this** (finding 1).
5. Three arms identical except expansion — **pass**: one app per arm with the same corpus, campaign, as-of, `k=5`, extractive drafting, cache off, inspection on, and case order; only the expansion object differs; the command test records every setting.
6. Rule reported, no default changed — **pass**: fixed 37-answer denominator, strict hit@5 gain plus zero trap regressions, incomplete-review and no-effect phrases, C-vs-B information only, no ranking, `defaults_changed: false`.
7. Model terms pinned, bounded, fail closed — **pass**: pinned record over loopback only, digest verified by `OllamaTransport`, temperature 0/seed 0, ≤4 terms, 1–8 tokens/≤80 chars/single line/no digit/URL/screen, fixed statuses, `model_unavailable` aborts with no cache.
8. Deterministic, cached, outside `knowledge/` — **pass**: byte-identical re-run, version-keyed report, cache missing/stale aborts, output root refused inside `knowledge/` or on an input, only `build/colloquial-ab/` written, `run` offline.
9. Failures stop cleanly — **pass** for the covered paths: fixed lines, exit 2, no report, earlier report untouched, traceback only in `last-error.log`; see residual risks for CLI/missing-input edge wording.
10. Acceptance evidence — **fail**: the owner has not decided any variant (0 approved, 49 draft), so there is no owner-approved A/B. The appendix's "real" numbers came from a Git-ignored copy where all 49 variants were marked `approved` by `reviewed_by: "rehearsal"`, not by the owner. The appendix also cites a test name that does not exist.

## Findings

### Finding 1: Pre-approval rehearsal was scored and recorded as feature evidence

- Severity: **High**
- Evidence: appendix "Feature evidence" says "Developer rehearsal only, on a Git-ignored copy with all 49 variants marked approved (not owner decisions)". The worktree still contains `build/colloquial-ab/approved-rehearsal.json` (49 `approved`, `reviewed_by: "rehearsal"`), `build/colloquial-ab/reports/244592b70f8d5526/report.json`, and `build/colloquial-ab/rewrites/119997fc11857103.json`. The committed variant file is clean (49 draft, 0 decisions).
- Why it matters: owner decision 2 says variants "MUST be owner-approved before any scoring; unapproved items are never read", and the constraint says the comparison "MUST read only owner-approved variants". The rehearsal read and scored every unapproved draft by relabeling it approved. Its numbers (24/26/34) are not an owner measurement and must not be cited as acceptance evidence or used to choose a mode.
- Required change: remove the rehearsal from acceptance evidence; do not cite its counts or `version_id`. Leave the real `prepare`/`run` for after the owner's recorded decisions.
- Suggested implementation:
  1. Delete or rename `build/colloquial-ab/approved-rehearsal.json`, its report directory, and its cache so no later agent can mistake them for evidence.
  2. Replace the appendix "Feature evidence" rehearsal bullet with "no owner-approved run yet; owner decisions pending".
  3. Keep the deterministic/offline tests as tooling evidence; after the owner decides, run `prepare` and `run` on the decided file and append the real counts.
- Verification after fix: `git status --short` has no variant/report artifacts; `prepare` on the committed all-draft file still exits 2 with `no_approved_variants`; after owner decisions, `check` reports `approved=49` and `run` scores only those ids.

### Finding 2: The owner guide says "reject" a variant that `check` still rejects

- Severity: **Medium**
- Evidence: `docs/owner-guide/colloquial-variants-review.md` line 41 says a variant that "cannot be approved as written" should be rejected or sent to the developer. Probe: reject `coll-001` after replacing its terms with `["palabra que no está"]`; `decide` exits 0, then `check` exits 1 with `coll-001: term_missing`.
- Why it matters: an owner following the guide can leave a rejected, mechanically invalid variant in the durable set; the focused `check` then cannot pass, blocking acceptance even though the owner did what the guide said.
- Required change: make the guide say that a mechanically invalid variant must be fixed by the developer (rejecting it does not repair `check`), or make `check` skip scenario-2 failures for rejected variants and update the spec/tests consistently. The guide-only fix is preferred because scenario 2 says "any variant".
- Suggested implementation: replace "Reject it, or send this line to the developer" with "Send this line to the developer; the variant must be corrected before the set can pass the developer check. Rejecting it does not fix the check." Add a command test for the chosen behavior.
- Verification after fix: reject a deliberately invalid variant, run `check`, and confirm the documented outcome (rejected variants remain well-formed or are explicitly exempt).

### Finding 3: Appendix evidence names a test that does not exist

- Severity: **Low**
- Evidence: `docs/specs/colloquial_ab_evaluation.appendix.md` line 116 names `test_command_walkthrough_list_decide_missing_env_and_recovery`; the actual passing tests are `test_list_waiting_pinned_line_and_full_list_file`, `test_decide_records_replaces_and_records_nothing_on_bad_input`, and `test_missing_backend_environment_line_and_init_wiring`.
- Why it matters: a reader cannot reproduce the named check; evidence should name runnable tests.
- Required change: replace the name with the three actual test names (or one real test id).
- Verification after fix: `grep` the appendix name against `backend/tests/` returns an existing test.

### Finding 4: Summary/file-list drift

- Severity: **Low**
- Evidence: the implementer summary named `docs/constraints/answers-and-questions.md`, `docs/risks-and-questions.md`, and `docs/process/*`; none exists. The actual tracked changes are 17 files: `ARCHITECTURE.md`, `PROGRESS.md`, `backend/README.md`, `backend/app/colloquial_ab.py`, `backend/config/colloquial_variants.json`, `backend/scripts/colloquial_ab.py`, `backend/tests/test_colloquial_ab.py`, `backend/tests/test_colloquial_ab_command.py`, `backend/tests/test_question_glossary.py`, `docs/constraints/answers-and-knowledge.md`, `docs/owner-guide/README.md`, `docs/owner-guide/colloquial-variants-review.md`, `docs/progress/known-limitations.md`, `docs/risks-and-open-questions.md`, `docs/specs/colloquial_ab_evaluation.appendix.md`, `feature_list.json`, `scripts/init.sh`. The spec's expected `backend/tests/fixtures/colloquial_ab/` directory was not created; tests use temp copies and the real read-only `knowledge/` files.
- Why it matters: future agents may look for files that do not exist or assume a missing fixture is a bug.
- Required change: use the actual paths in handoff notes; note the fixture-directory deviation as intentional (temp copies + real read-only knowledge) or add the fixture directory if a self-contained corpus is wanted.
- Verification after fix: `git diff --name-status <base>..HEAD` matches the handoff list; no named path is missing.

## Implementation Repair Brief

Goal: keep the implemented code, remove the pre-approval evidence, and make the owner workflow and evidence text accurate.

Do:
1. Remove/rename the Git-ignored rehearsal artifacts and replace the appendix rehearsal bullet with "no owner-approved run yet; owner decisions pending".
2. Correct the appendix test name to the actual tests.
3. Fix the owner guide's reject-versus-check wording, or make `check` exempt rejected variants and update the spec/tests consistently.
4. Have the owner run `--colloquial-review` and `--colloquial-decide` on all 49, commit the decided file, then run `check`, `prepare`, and `run` on the owner-approved file; append real counts, hit@5, traps, and `version_id`, and confirm a byte-identical second `run`.
5. Re-run `./scripts/init.sh --feature colloquial_ab_evaluation` and `./scripts/init.sh --fast`; update this record and the appendix.

Do not:
- change `knowledge/`, the glossary default, `/ask`, retrieval, `eval_metrics`, golden/trap sets, contracts, or release gates;
- mark variants approved yourself or set `feature_list.json` to `accepted`;
- cite the rehearsal numbers as an owner measurement.

## Residual risk

- **No owner-approved A/B exists today.** The committed tree has 0 approved and 49 draft variants; only a pre-approval developer rehearsal exists (and is rejected as evidence above). The 24/26/34 numbers are not an owner measurement.
- The review discipline trusts `review_state`; a hand-edited `approved` is indistinguishable from a recorded owner decision. The rehearsal demonstrates the bypass; the mitigation is process, not code.
- Small agent-drafted set, BM25 extractive answers, one pinned local model on one Mac; no quality, legal, or adoption claim.
- Tests use a fake rewriter and fake transport; the real model path and a real missing-model condition were not rerun by the validator. `model_unavailable` was proven with a fake transport failure.
- A missing catalog/passages/cases/golden/traps file reports `internal_error` rather than `invalid_inputs`, and the abort text says "Nothing was written" while writing `last-error.log`; a missing required CLI argument (`--as-of`) produces argparse usage text rather than a pinned `Result:` line. These are error-path polish items, not metric-driven exits.
- Durable docs accurately say no owner-approved measurement exists; this is more conservative than the spec's "measured on N approved variants" line and should stay until the owner-approved run happens.
