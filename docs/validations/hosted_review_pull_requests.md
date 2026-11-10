Validation of hosted_review_pull_requests

Verdict: accept (validator, 2026-11-10, second round). Spec: docs/specs/hosted_review_pull_requests.md; evidence: docs/specs/hosted_review_pull_requests.appendix.md. Implementation at b2b1bed (base 91adc1f); status left `passing` for the orchestrator to persist as `accepted`.

Why: all five round-one findings are fixed and independently reproduced, and the full spec (scenarios 1-7, non-goals, durable docs) still holds offline. The only unexercised surface is the live GitHub call, which the spec assigns to the owner.

Round-one findings (each reproduced at b2b1bed)
1. Fixed — ruleset ref field. The committed file and `_condition_ref` use `conditions.ref_name`; `_committed_ruleset` refuses a committed file whose `ref_name.include` lacks `refs/heads/main` and refuses a rule entry without a string `type`. Probe: documented GET shape → `matches=True`; legacy `ref` shape → `False`; both committed-file refusals → `True`; shipped file accepted.
2. Fixed — normalised "already matching". `_checks_match` compares sorted contexts, so a live check carrying `integration_id` (null or set) still matches; `_parameters_match` still compares `strict_required_status_checks_policy`. Probe: `integration_id` plus extra `allowed_merge_methods`/`required_reviewers` → `True`; 2 approvals or an extra required context → `False`.
3. Fixed — live rules preserved. `_merged_rules` keeps live rules whose type the committed file does not name; `ruleset_payload` passes live `bypass_actors` through. Probe: payload rules are pull_request/required_status_checks/non_fast_forward plus one unchanged `deletion`, bypass actors byte-equal, `ref_name` present, no `ref`.
4. Fixed — private diagnostics. `_publish` appends `push failed (exit N)` and `pull request create failed (exit N)` (or `returned no url`) to `<home>/logs/hosted-review.log` (`0600`); tests assert the fixed-code text, no temp path, no stderr, and the owner sentence is unchanged.
5. Fixed — appendix drift. The socket-blocking claim is gone (unit tests are fake-port only; the walkthrough uses a fake `gh` and a local bare origin). Body source/passage rows are labelled "(answered cases)" and count only `expected_status == "answered"`, matching `answer_eval.py`'s answered-only `source_citation_agreement`.

Checks rerun
- `./scripts/init.sh --feature hosted_review_pull_requests` → focused tier passed, `122 passed in 4.09s`; the published block is accurate.
- Same four files one by one → 27 / 6 / 46 / 43 passed; the `merge` extraction moved no existing review/orchestrator test.
- `./scripts/init.sh --fast` → all 10 offline checks passed; backend `3409 passed, 9 skipped`.
- `--verify` not rerun: no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging change.
- `git diff --name-only 91adc1f..HEAD` → no `.github/`, `contracts/`, canonical knowledge JSON, or `knowledge_review.py` change; `PROGRESS.md` untouched; `feature_list.json` only `not_started` → `passing`.
- Ruleset probe with fake data (python, no GitHub, no `gh`) → documented GET matches; old ref shape and weakening changes do not.

Scenarios and non-goals
- 1-3 pass: temporary detached worktree of `origin/main`; commit is exactly the catalog, passages, and `knowledge/reviews/<id>/{package.json,REVIEW.md}`; after hashes equal the package; `pull-request.json` is `0600`; one `gh pr create`; `opened:`/`Result:`/exit 0; owner HEAD/tree byte-unchanged; re-runs report open/merged/closed with one `gh pr view`; an unrecorded branch is refused.
- 4 passes: not-ready, failed check, damaged manifest, baseline drift, case drift, invalid after-state, and evaluation failure each print one package line, send nothing, keep processing, exit 1.
- 5 passes: missing home, no origin, `gh` absent, and failed `gh auth` stop with exit 2 and one fix; the walkthrough proves recovery. The backend-env branch in `init.sh` was read, not exercised (hiding the shared venv is unsafe); it mirrors the accepted `--knowledge-updates-*` block.
- 6 holds: `ref_name`/`id` read, `yes` gate, one PUT, `already protected`, `no` → exit 1, missing ruleset → exit 2, bypass actors kept, other live rules kept. Live GitHub effect remains owner-only.
- 7 holds: no `pr merge`, `--auto`, `pr review`, `--admin`, non-ruleset `api`, or force/delete argv in code or recorded calls; tests use a local bare remote and fake `gh`; unit tests are fake-port only.
- Non-goals: no merge/auto-merge/approve/push/force-push/delete path; `prepare`/`decide`/`merge` failure codes unchanged by the extraction; no release, reindex, `/ask`, `contracts/`, `gate.yml`, dependency, or workflow change; the orchestrator still stops at review ready.

Security and docs
- No secret, token, document text, or local filesystem path reaches the body or record; the one owner-visible absolute path is the private log location printed on an unexpected crash. `pull-request.json` and logs are `0600`; `gh` uses the owner's existing login; no test reaches the network.
- Security checklist: no blocking issue. The argv allowlist is closed by construction and asserted; the managed files are fixed paths; no new dependency.
- Durable docs (ARCHITECTURE, operations/answers-and-knowledge constraints, owner guide 57 lines, backend/knowledge READMEs, risks, known limitations) match the implementation and keep the hosted path honest as unexercised.

Residual risk for the owner
- The live push/PR/ruleset path has never run; after this accept the owner runs protect once and confirms `fast`/`full`, 0 approvals, force pushes blocked, and the intended bypass actors.
- A live ruleset carrying an extra required check would be replaced by `fast`/`full` (the committed file and scenario 6 name exactly those checks); the confirmation does not call out that removal. Same-rule parameters take the committed values; unrelated rule types and bypass actors are kept.
- A successful push followed by a failed create or record write leaves an unrecorded branch; the next run refuses it and the owner deletes it on GitHub.
- Zero required approvals means GitHub enforces no second reviewer; committed evidence carries the names typed at `prepare`.
- Non-blocking copy nit: the damaged-record line says "First thing to ask:" (`backend/app/hosted_review.py:529`).
