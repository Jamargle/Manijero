# hosted_review_pull_requests — appendix

## Repository research

### Files inspected

Inspected (planner, 2026-11-10):

- `feature_list.json` line for this feature — `not_started`; depends on accepted `knowledge_update_review_pr`, `knowledge_ops_orchestrator`.
- `docs/specs/knowledge_update_review_pr.md` and `docs/archive/specs/knowledge_update_review_pr.appendix.md` — local draft package flow; observed limit: "not a hosted PR: hosting merge protection is not configured or enforced". This feature closes that limit for the hosted path.
- `backend/app/review_package.py` — `prepare(...)` writes `<workspace>/<package_id>/{package.json,REVIEW.md}`; `load_package` verifies the content digest; `merge` (line 1758) holds the after-state logic (`_apply_section`, `_ordered_json`, after-hash check, `validate_catalog(as_of)`, `validate_passage_set`, `load_evaluation_cases`) to extract; `render_review_markdown` is the PR body source; `exit_code` 0 ready / 1 needs attention.
- `backend/scripts/knowledge_review.py` — CLI `prepare|decide|merge`, fixed `{"error": name}` refusals; unchanged by this feature (avoids the `operations.md` "changed operator CLI" MUST).
- `docs/specs/knowledge_ops_orchestrator.md`, `backend/app/knowledge_ops.py` — `Ports` dataclass, `Problem`, `_private_dir`, `_write_private`, `append_log`, `result_line`; `step_review` (line 998) "Next step" text names `knowledge_review.py prepare`.
- `scripts/init.sh` lines 277–297 — `--knowledge-updates-*` dispatch shape (no extra args, backend-env check, `exec` Python); line 553 `--backend-tests [target]` accepts pytest targets; usage block lines 631–640.
- `.github/workflows/gate.yml` — jobs `changes`, `fast`, `full`; a skipped tier reports success, so both `fast` and `full` are required checks; a `knowledge/` change runs `full`.
- `backend/scripts/evaluate_pac_answers.py`, `backend/app/answer_eval.py` (`evaluate` return keys at line 299) — offline evaluator over given catalog/passages/cases; exit 2 on input failure; metrics report-only.
- `.agents/skills/github-flow/scripts/batch_flow.py`, `.agents/skills/github-flow/tests/test_batch_flow.py` — existing `gh pr create/view/list` argv shapes and the fake-`gh`-on-`PATH` recording pattern.
- `docs/constraints/answers-and-knowledge.md` line 237 — controlled-merge MUST that the hosted path must extend; `docs/constraints/operations.md` — owner operability rules (one named command, `Result:` line, confirmation for hard-to-reverse changes, walkthrough MUST met by automated test).
- `knowledge/` listing — canonical files `source_catalog.json`, `passages.json`, `pac_answer_eval.json`; no `reviews/` folder yet. `backend/tests/test_relevance_classifier.py:370` globs only `knowledge/*.json` (a subfolder is safe).
- Not inspected: the live `protected-main` ruleset (agents must not call GitHub); its current rules and bypass actors are unknown and handled at run time.

### Existing patterns to follow

- Owner commands: `./scripts/init.sh --<name>`, no arguments, prerequisite check first, one `Result:` line, exit 0/1/2 (see `--knowledge-updates-*`).
- Injected ports and fake CLIs via test-only env (`MANIJERO_LAUNCHCTL_CLI`, `MANIJERO_KNOWLEDGE_OPS_STEP_CLI`); automated command walkthrough `test_knowledge_ops_commands.py`.
- Refusals carry fixed codes; never echo exception text, document text, or local paths to the owner output.

### Current gaps

- No `gh` wrapper in `backend/`; no committed ruleset file; no knowledge review home folder convention (this feature sets `~/manijero/knowledge-reviews/`).
- The live GitHub path (push, PR creation, ruleset update) cannot be exercised by agents; it stays unexercised until the owner runs it.

## Implementation plan

1. Extract `build_after_state` from `review_package.merge`; run `test_knowledge_update_review.py` to prove `merge` is unchanged.
2. Write `backend/deploy/github/protected-main-ruleset.json`: name `protected-main`, target `branch`, enforcement `active`, conditions `refs/heads/main`, rules `required_status_checks` (`fast`, `full`, non-strict), `non_fast_forward`, `pull_request` (0 approvals, no other review requirements).
3. Create `hosted_review.py` ports and real runners (`git`, `gh` from `MANIJERO_GH_CLI` or `PATH`, evaluator child, clock, stdin/stdout).
4. Implement package discovery in the review home (direct child folders with `package.json`; skip `.work`, `logs`), per-package readiness and integrity checks, and the `pull-request.json` record.
5. Implement the git flow in a temporary detached worktree under the review home `.work/`, baseline hash check against `origin/main`, after-state write, evidence copy, commit, non-force push, worktree removal in `finally`.
6. Implement before/after evaluation, `render_pr_body` (fixed lines, counts, ≤20 changed ids, check summary, `REVIEW.md`, 60,000-char cap), and `gh pr create --base main --head ... --title ... --body-file ...`.
7. Implement re-run status via `gh pr view <branch> --json state,url,mergedAt` and the `branch exists` refusal.
8. Implement `protect`: list rulesets, find `protected-main`, read it, compare, describe, ask `yes`, PUT the merged payload keeping `bypass_actors`.
9. Add `backend/scripts/hosted_review.py` (`open|protect`) and the `scripts/init.sh` dispatch + usage lines.
10. Update `knowledge_ops.step_review` Next step text.
11. Write `test_hosted_review.py` and `test_hosted_review_commands.py` (below).
12. Update the durable docs listed in the contract; keep owner guide ≤60 lines and backend README ≤30 lines.

## Verification plan

- Focused block via `./scripts/init.sh --feature hosted_review_pull_requests` — all listed files pass.
- `test_hosted_review.py` (unit, fake ports): after-state bytes equal package after hashes; body fixed lines, counts, changed-id cap, 60,000-char cut; each refusal in scenario 4 creates nothing and other packages continue; re-run states open/merged/closed; `branch exists` refusal; ruleset compare/merge keeps bypass actors; `yes` gate; missing ruleset creates nothing; gh/git argv allowlist (no merge, `--auto`, `--force`, `--delete`, `+` refspec).
- `test_hosted_review_commands.py` (walkthrough): temp clone with a local bare `origin` seeded with fixture `knowledge/` files, fake `gh` script recording argv and returning canned JSON, `MANIJERO_KNOWLEDGE_REVIEW_HOME` temp folder; runs `./scripts/init.sh --knowledge-review-open` and `--knowledge-review-protect` exactly as the owner guide writes them; checks the pushed branch tree in the bare remote, owner checkout unchanged, one missing-prerequisite case (no `gh`) and its recovery, and the real evaluator child over fixture files.
- Network guard: subprocess env `PATH` limited to the fake `gh` dir plus system `git`; `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM` isolated; remote URL is a local path; in-process tests block sockets as `test_knowledge_ops.py` does.
- `test_knowledge_update_review.py` — 46 existing tests still pass after the extraction.
- E2E: not applicable (no app UI or `/ask` change); the command walkthrough covers the owner flow.

## Evidence to capture

- Focused block result line; test counts per file.
- One rendered PR body from the walkthrough fixture (paths/ids only, summarized in one or two lines).
- Recorded fake `gh` argv for open, re-run, and protect, showing no merge/auto-merge.
- Bare-remote branch file list and hashes versus the package after hashes.
- Honest limits: live push/PR/ruleset not exercised; zero approvals means GitHub enforces no second reviewer; evidence carries names typed at `prepare`.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

Implementer session, 2026-11-10, worktree `feature/hosted_review_pull_requests` (base `91adc1f`).

- Planning commit: `e4d3bad docs: plan hosted_review_pull_requests`.
- `./scripts/init.sh --feature hosted_review_pull_requests` → `117 passed in 3.98s`; focused tier passed (log `build/verify-logs/feature-hosted_review_pull_requests.log`).
- Per file: `test_hosted_review.py` 22 passed; `test_hosted_review_commands.py` 6 passed; `test_knowledge_update_review.py` 46 passed (extraction unchanged); `test_knowledge_ops.py` 43 passed (Next-step text only).
- `./scripts/init.sh --fast` → all 10 offline checks passed; backend `3404 passed, 9 skipped`; contract examples, harness tests, source catalog, retrieval/generation/abstention/clarification/land-safety OK.
- Walkthrough: every owner-guide command through `scripts/init.sh`, with a temporary clone, local bare `origin`, fake `gh`, and the real offline evaluator. Pushed branch carries exactly `knowledge/source_catalog.json`, `knowledge/passages.json`, `knowledge/reviews/<id>/package.json`, and `REVIEW.md`; both after hashes equal the package; owner checkout byte-unchanged. Body starts with the two fixed lines and shows `| Cases | 4 | 4 |`. Re-run reports OPEN, MERGED, CLOSED without a second create. Recovery after missing `gh` opens exactly one PR.
- Protect walkthrough: weak ruleset → describes, asks, one PUT keeps bypass actors; matching → `already protected`, no PUT; `no` → nothing sent, exit 1; missing ruleset → nothing created, exit 2.
- Unit checks: after-state equals package after hashes; 60,000-char body cut with pointer; ≤20 changed ids; damaged/unsafe/stale/drift packages create nothing while a good package continues; missing `gh` (`127`) and failed `gh auth` stop with exit 2 and recovery; damaged `pull-request.json`; recorded `gh` argv has no merge/auto/review/admin and `git push` has no force/delete.
- Honest limits: live push/PR/ruleset not exercised; zero required approvals means GitHub enforces no second reviewer; committed evidence carries names typed at `prepare`. `PROGRESS.md` untouched (integrator owns it).

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no merge, auto-merge, force push, deletion, CLI/schema/release change).
- [ ] Owner decisions 1–5 recorded and honored; no owner walkthrough named as acceptance.
- [ ] Acceptance scenarios 1–7 pass with evidence; the pushed tree equals the package after hashes plus the two evidence files.
- [ ] No test or check reaches GitHub or the network; fake `gh` log and push argv prove the allowlist.
- [ ] `merge` behavior unchanged; existing review tests pass.
- [ ] Owner output: plain lines, one `Result:` line, exit 0/1/2; no paths, tokens, exception or document text.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature hosted_review_pull_requests`.
- [ ] Durable documentation impact followed within size budgets; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` untouched by this feature (integrator owns them).
