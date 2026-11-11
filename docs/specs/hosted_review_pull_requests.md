# Open knowledge update reviews as GitHub pull requests with evaluation results and merge protection

## Source metadata

- `id`: hosted_review_pull_requests · `area`: operations · `depends_on` (both accepted): knowledge_update_review_pr, knowledge_ops_orchestrator · `status` at planning: not_started.
- User-visible behavior: a prepared, ready review package becomes one GitHub pull request to `main` that carries the proposed catalog/passage change, the review evidence, and before/after answer-evaluation counts; the owner reviews and merges it on GitHub, and `main` is protected by the `protected-main` ruleset.
- Verification: offline automated tests only (local bare Git remote, fake `gh`, fake evaluator where unit-level), plus an automated command walkthrough through `scripts/init.sh`; commands are in Focused verification.
- Notes — owner decisions (final, 2026-11-10; record, do not reopen):
  1. Review PRs target `main` from a `knowledge-review/<package-id>` branch. The tool never merges and never enables auto-merge; the owner merges.
  2. Enable the existing repository ruleset `protected-main` to require the existing `fast` and `full` gate checks and block force pushes, with zero required approvals and no extra approval for commits GitHub cannot attribute to an account. Delivered as a committed ruleset file plus one owner command; agents never call GitHub.
  3. Tests and checks never call GitHub: fixtures and offline only (fake `gh`, local bare remote). The live path is exercised by the owner later.
  4. No new spend (existing `gate.yml` workflow and the owner's existing `gh` login only).
  5. No owner walkthrough for acceptance; the independent validator's accept is final. The `docs/constraints/operations.md` walkthrough MUST is met by the automated `test_hosted_review_commands.py`, like `knowledge_ops_orchestrator`.
- Planning decisions (this spec): "zero required approvals" is a `pull_request` rule with `required_approving_review_count: 0`; the owner's GitHub merge is the human approval for the hosted path. Only packages whose `merge_readiness` is `ready_for_review` with zero failed checks are sent; blocked packages stay local. Owner commands and copy are English, like every existing owner command.

## Goal

Let a reviewed knowledge update reach `main` only through a GitHub pull request that shows the owner the evidence and the evaluation effect, passes the existing gate checks, and is merged by the owner's own click, never by the tool.

## Non-goals

- No merge, auto-merge, approval, review request, label, force push, branch deletion, or history rewrite by the tool; no `gh pr merge` or `--auto` anywhere.
- No change to `prepare`/`decide`/`merge` behavior, package/decision schemas, the `knowledge_review.py` CLI, the release builder, reindex, `/ask`, `contracts/`, or `gate.yml` jobs.
- No automatic proposal authoring or package preparation by the orchestrator; the scheduled run still stops at review ready.
- No GitHub call from any test, check, or agent session; no new dependency, workflow, paid runner, or service.
- No legal-coverage or answer-quality claim from a merged PR or from the evaluation counts (report-only).

## Job story

When a knowledge update has been prepared and is ready for review, I want it to appear as a pull request on GitHub with what changed and how answers are affected, so I can read it in my browser and merge it myself once the checks pass.

## Acceptance scenarios

### 1. A ready package becomes one pull request
Given a ready package in the knowledge review folder whose baseline hashes match `origin/main` · When the owner runs `./scripts/init.sh --knowledge-review-open` · Then the tool fetches `main`, builds the after-state in a temporary worktree (never the owner's checkout), commits only `knowledge/source_catalog.json`, `knowledge/passages.json` (bytes equal to the package's after hashes), and `knowledge/reviews/<package-id>/{package.json,REVIEW.md}` on branch `knowledge-review/<package-id>`, pushes it without force, and runs exactly one `gh pr create --base main --head knowledge-review/<package-id>`; it writes `pull-request.json` (`0600`) next to the package, prints `opened: <url>` for that package and one `Result:` line, exit `0`. The owner's checkout, branch, and working tree are byte-unchanged.

### 2. The PR body carries evidence and evaluation results
Given scenario 1 · Then the body starts with the fixed lines `The owner merges this on GitHub. Nothing goes live on merge: publishing is a separate release step.` and `Evaluation counts are report-only, not a quality or legal-coverage claim.`, then an "Evaluation results" section with before → after counts from the offline PAC answer evaluator over the package's bound case set (cases, expected-state agreement, unexpected answers, source and passage matches) and at most 20 ids of cases whose row changed, then the package check summary and the package `REVIEW.md`. A body over 60,000 characters is cut at a line boundary with a pointer to the committed `REVIEW.md`. No local path, token, or exception text appears.

### 3. Re-running reports, never duplicates
Given a package that already has `pull-request.json` · When the open command runs again · Then no push or `gh pr create` happens; one read-only `gh pr view` reports `already open: <url>`, `merged on GitHub` (next step: the release steps), or `closed without merging` (next step: prepare a new package). A remote branch `knowledge-review/<id>` that exists without a recorded PR is refused (`branch exists`), never overwritten.

### 4. Unsafe or stale packages are not sent
Given a package that is not `ready_for_review`, has failed checks, fails `load_package` integrity, whose baseline no longer matches `origin/main` (`canonical_drift`), whose bound case file digest differs (`evaluation_cases_drift`), whose after-state fails validation, or whose evaluation cannot run · When the open command runs · Then nothing is pushed or created for that package, it gets one plain line naming the problem and the first thing to do, other packages are still processed, and the exit code is `1`.

### 5. Missing prerequisites fail closed
Given the review folder is missing, the backend environment is missing, `git` has no `origin`, `gh` is absent, or `gh auth status` fails · When either new command runs · Then nothing changes, one plain sentence names the problem and its one fix, and the exit code is `2`. Fixing the prerequisite and re-running succeeds (recovery).

### 6. Protect `main` with the existing ruleset
Given `gh` is logged in and the repository has a ruleset named `protected-main` · When the owner runs `./scripts/init.sh --knowledge-review-protect` · Then it reads that ruleset, states in plain words what will change (active enforcement on `main`; required checks `fast` and `full`; force pushes blocked; pull requests required with 0 approvals and no extra approval for unattributed commits; existing bypass actors kept) and the way back, asks for `yes`, and on `yes` sends one update of that ruleset id from the committed `backend/deploy/github/protected-main-ruleset.json`; exit `0`. Already matching → `already protected`, no update. Not `yes` → nothing sent, exit `1`. No ruleset named `protected-main` → nothing created, exit `2`.

### 7. Never merge, never auto-merge, never call GitHub in tests
Given every test · Then the fake `gh` log contains no `pr merge`, `--auto`, `pr review`, `--admin`, or `api` call other than the `protected-main` ruleset read/update; every `git push` argv has no `--force`, `-f`, `--force-with-lease`, `--delete`, or `+` refspec; and no test reaches the network (only the local bare remote and the fake `gh`).

## Technical approach

- `backend/app/review_package.py`: extract the after-state path of `merge` (load, apply sections, ordered serialization, after-hash check, catalog/passage/case validation) into public `build_after_state(package, catalog_bytes, passages_bytes, cases_path, as_of)` returning the two texts; `merge` calls it with unchanged behavior and refusals.
- `backend/app/hosted_review.py` (stdlib only): `Ports` dataclass (git runner, gh runner, evaluator, clock, input, output) like `knowledge_ops.Ports`; `open_reviews(home, repo, ports)`, `protect(repo, ports)`, `render_pr_body(package, review_md, before_eval, after_eval)`, `ruleset_payload(existing, committed)`, `ruleset_matches(existing, committed)`. Reuse `knowledge_ops` helpers for private files, the log, and `Result:` phrasing. Tracebacks only to `<home>/logs/hosted-review.log` (`0600`).
- Git: `git fetch origin main`, `git worktree add --detach <tmp> origin/main`, write files, `git commit`, `git push origin HEAD:refs/heads/knowledge-review/<id>`, always `git worktree remove` in `finally`. `as_of` = Europe/Madrid date at run start; evaluator = child `backend/scripts/evaluate_pac_answers.py --active-campaign 2026` on before and after files.
- `gh` argv allowlist: `auth status`, `pr create`, `pr view`, `pr list --head`, `api repos/{owner}/{repo}/rulesets[/<id>]` (GET, and PUT only from `protect`). Review home `~/manijero/knowledge-reviews/` (prepare writes there with `--workspace`).
- `backend/scripts/hosted_review.py` ops `open|protect`; `scripts/init.sh` dispatches `--knowledge-review-open|-protect` like the `--knowledge-updates-*` block (no arguments; backend-env check first). Test-only env: `MANIJERO_KNOWLEDGE_REVIEW_HOME`, `MANIJERO_GH_CLI`, `MANIJERO_HOSTED_REVIEW_REPO`.
- `knowledge_ops.step_review` "Next step" text names `--knowledge-review-open` after `prepare`; no other orchestrator change.

## Expected file changes

- Create: `backend/app/hosted_review.py`, `backend/scripts/hosted_review.py`, `backend/deploy/github/protected-main-ruleset.json`, `backend/tests/test_hosted_review.py`, `backend/tests/test_hosted_review_commands.py`, `docs/owner-guide/knowledge-review-pull-requests.md`.
- Modify: `backend/app/review_package.py` (extract `build_after_state`), `backend/app/knowledge_ops.py` (Next step text), `scripts/init.sh` (dispatch + usage), `backend/tests/test_knowledge_update_review.py` and `backend/tests/test_knowledge_ops.py` only if a text assertion moves.

## Visual design impact

UI involved: no. GitHub PR body is Markdown with plain English headings.

## Durable documentation impact

- `ARCHITECTURE.md`: update — one line: hosted review PRs from ready packages; owner merges; `protected-main` ruleset.
- `docs/constraints/answers-and-knowledge.md`: update — the controlled-merge MUST gains the hosted path: a canonical change may also land via a `knowledge-review/<id>` PR opened by this command from a ready package and merged by the owner on GitHub with `fast`/`full` passing; the tool never merges or auto-merges (owner decision 2026-11-10).
- `docs/constraints/operations.md`: update — `--knowledge-review-open|-protect` call `gh` only from the allowlist, never merge, auto-merge, force push, or delete; tests never call GitHub; acceptance is `test_hosted_review_commands.py`, not an owner walkthrough.
- `docs/owner-guide/knowledge-review-pull-requests.md`: create (≤60 lines: protect once, open, read and merge in the browser, after merge, message table); list it in `docs/owner-guide/README.md`.
- `backend/README.md`: update — "Hosted review pull requests" section, ≤30 lines. `knowledge/README.md`: update — reviewer workflow gains the hosted path and `knowledge/reviews/`.
- `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`: update — live path unexercised until the owner runs it; GitHub enforces no second reviewer; committed evidence carries the names typed at `prepare`.
- `AGENTS.md`, `CONSTRAINTS.md` index, `DESIGN.md`, `contracts/`, `feature_list.json`, `PROGRESS.md`: not changed by this feature (integrator owns status).

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_hosted_review.py tests/test_hosted_review_commands.py tests/test_knowledge_update_review.py tests/test_knowledge_ops.py -q
```
<!-- verify:end -->

## Appendix

See [`hosted_review_pull_requests.appendix.md`](hosted_review_pull_requests.appendix.md) for research, plan, verification plan, evidence, and the validator checklist.
