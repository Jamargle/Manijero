# Validation record: `qa_knowledge_deployment`

- **Verdict:** accept (independent validator, round 1, 2026-11-11). Final; no owner walkthrough, by
  owner decision: the automated command walkthrough in `test_qa_knowledge_commands.py` stands in.
- **Reviewed:** worktree `qa_knowledge_deployment`, branch `feature/qa_knowledge_deployment`, on top
  of `db9f88e`, uncommitted diff at `passing`. Spec:
  [qa_knowledge_deployment.md](../specs/qa_knowledge_deployment.md); evidence:
  [appendix](../specs/qa_knowledge_deployment.appendix.md) "Feature evidence".
- **Scope:** no push, `gh`, or amend. `pilot-token.local` and `~/manijero/*/credentials/` not read.

## Checks rerun

| Command | One-line result |
|---|---|
| `./scripts/init.sh --feature qa_knowledge_deployment` | 237 passed; `bash -n` ok; no diff in `knowledge/` (except README) or the quality-gate baseline. |
| `CI=true ./scripts/init.sh --fast` | Backend 3587 passed, 3 failed, 9 skipped; every other check ok. |
| The 3 fast-tier failures rerun alone | Fail the same way on an extra `MANIJERO_KNOWLEDGE_OPS_STATE_DIR` key, added by `local_rag_service` / `health_metrics.py` only when `~/manijero/knowledge-ops` exists on the host; neither file is in the diff. Host-dependent and unrelated to this feature. |
| `--verify` | Not rerun: no `shared/`, Android, Desktop, Gradle, or packaging change. |

## Owner decisions held

- Approved knowledge reaches QA only through the named owner command `--qa-knowledge-deploy`, after
  an explicit `yes`; there is no automatic deploy after merge (no launchd, merge, or knowledge-ops hook).
- QA is checked after every switch; a failed check rolls back automatically to the previous knowledge
  and is reported in plain words. If the way back also fails, Funnel is turned off and QA is stopped.
- No owner walkthrough; the automated walkthrough is the binding acceptance check.

## Scope and security

- `knowledge/` content, the baseline, `knowledge_release.py`, and `contracts/` unchanged.
- No `shell=True`; no secrets in output or logs; container additions are exactly one bind mount, two
  environment keys, and a label; `qa_knowledge` is on the operator-only module list.

## Limits that remain

- Real Docker, Tailscale, and GitHub fetch paths are exercised only by fakes.
- "Approved" means merged to `origin/main`; individual pull requests are not re-verified.
- Whether Chroma can write to the bind-mounted vector store is unproven; the post-switch checks and the
  automatic way back are the guard.
- The 3 host-dependent fast-tier tests fail whenever `~/manijero/knowledge-ops` exists; worth a separate
  fix that isolates that variable in tests.
