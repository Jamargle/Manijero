# Send approved knowledge to QA with one confirmed command, with automatic and one-command rollback

## Source metadata

- `id`: qa_knowledge_deployment · `area`: operations · `depends_on`: qa_server_deployment, ci_quality_gates, structured_chunk_index (all accepted) · `status` at planning: not_started
- User-visible behavior: after the owner merges a knowledge review pull request on GitHub, `./scripts/init.sh --qa-knowledge-deploy` takes the approved knowledge from `main`, rebuilds the search indexes, runs the release and quality gates, publishes it to QA's own release folder, restarts QA on it, and checks QA. If the QA checks fail, it goes back to the previous knowledge on its own and says so in plain words. `./scripts/init.sh --qa-knowledge-rollback` returns QA to the previous knowledge, and `--qa-status` shows which knowledge QA serves. Each command ends with one plain `Result:` line.
- Verification: offline automated tests only, using fake Docker and Tailscale CLIs, a local bare Git remote, fake builder runs, fake probes, temporary QA, local, and address homes, and fake tokens. Acceptance includes the automated command walkthrough `test_qa_knowledge_commands.py` through `scripts/init.sh` (Focused verification).
- Notes: owner decisions (2026-11-11), verbatim in substance:
  1. Approved knowledge goes to QA only when the owner runs one named command. No automatic deploy after merge.
  2. If the QA checks fail after a deploy, the owner is told in plain language and QA rolls back automatically to the previous knowledge.
  3. No owner walkthrough unless it is strictly necessary. Automated tests stand in for it: the acceptance check is automated, not an owner walkthrough. The validator's accept is final.
  - Planner choices (appendix "Planner decisions"): "approved" means the fetched `origin/main` (`protected-main`, merged by the owner); the first knowledge deploy adopts the knowledge built into the image as QA's first release, so a real earlier release always exists to go back to; if the automatic way back also fails, QA is taken off the internet and stopped.

## Goal

Let the owner put merged, gated knowledge in front of real QA devices without rebuilding the container image, always with a tested way back: automatically when the QA checks fail after a deploy, and by one command otherwise.

## Non-goals

- Merging, approving, or opening pull requests, and any `gh` call. The owner merges on GitHub, and this feature only reads the merged `main`.
- Deploying automatically (on merge, on a schedule, or from `--knowledge-updates-*`). Publishing to local or prod, or editing `knowledge/` in the owner's checkout.
- Changing the gates themselves: `release_gates`, `quality_gate`, the committed baseline, the release manifest, `/ask`, `contracts/`, the image build, or `--container-*`. The structured chunk index stays off in QA, because no QA command sets `MANIJERO_STRUCTURED_INDEX`.
- Downloading any model, or garbage-collecting old releases. Making any legal-coverage or answer-quality claim.

## Job story

When the owner has merged a knowledge update on GitHub, they want one command that puts it on QA only if every check passes and that undoes it by itself if QA breaks. Then they can test new answers on a phone without touching Docker, Git, or Python.

## Acceptance Scenarios

### 1. Deploy new approved knowledge
Given QA runs (`--qa-status` all OK) and `origin/main` holds knowledge that differs from QA's current release · When the owner runs `./scripts/init.sh --qa-knowledge-deploy` · Then, in this order:
- The command fetches `main` read-only and builds in a temporary worktree of `origin/main`. The owner's checkout is never touched.
- It runs the quality gate (`check_quality_gate.py check`) and the embedding index build, then `prepare --with-vector-store` into QA's release root. That root is also the regression baseline.
- It shows what will change (QA switches from release `<old>` to `<new>` from `main` at `<short sha>`) and the way back (`--qa-knowledge-rollback`), and asks for `yes`.
- On `yes`, it publishes the new release, replaces the `manijero-qa` container with the same image serving it, and runs the QA checks (scenario 4).
- It ends `Result: QA now answers from knowledge release <new> (main at <short sha>). If something is wrong, run ./scripts/init.sh --qa-knowledge-rollback.` and exits `0`.

### 2. First knowledge deploy adopts the image's knowledge
Given QA's release root has no `current` release · When deploy runs · Then, before building, it copies the release built into the running image (`docker cp`), verifies it with `knowledge_release.verify_release`, and publishes it as QA's first release. The new release then replaces it as in scenario 1, so the earlier knowledge is always a real release to go back to. If the image's release cannot be copied or verified, it says so and nothing changes.

### 3. Nothing new
Given the catalog, passages, and case bytes at `origin/main` equal those of QA's current release · Then no build, prompt, or container change happens. It ends `Result: QA already has the approved knowledge from main; nothing was changed.` and exits `0`.

### 4. QA checks after a switch, and the automatic way back
Every publish or rollback is followed by the QA checks: the container is running and ready within 120 seconds, the smoke check passes (`/health`, `/ready`, one synthetic `/ask` with the QA key, on loopback), `/metrics` with the QA key reports `knowledge_release_info` for the expected release id, and `<address>/health` answers over Funnel. If any check fails · Then:
- The command saves the container output to a log.
- It rolls the release back to the one QA served before (`knowledge_release.rollback --to <old>`), restarts the container on it, and reruns the checks.
- It ends `Result: the new knowledge failed the QA checks (<plain reason>), so QA went back to knowledge release <old> automatically. <first fix>` and exits `1`.

If the way back also fails, it turns Funnel off, stops the container, and ends `Result: the new knowledge failed the QA checks and QA could not go back by itself, so QA was stopped and is off the internet. Run ./scripts/init.sh --qa-knowledge-rollback, then ./scripts/init.sh --qa-deploy.` with exit `1`.

### 5. A gate fails, so nothing is published
Given any of these: the quality gate exits `1` or `2`, the embedding build fails, `prepare` exits non-zero (a gate failed, or a regression against QA's current release), the release is not ready for the QA campaign, or approval evidence is refused · Then QA's `current` release and the container are unchanged. A failed candidate may stay under `releases/` and is never publishable (`gate_failed`). Each problem gets one plain line, translated by the existing `gate_failure_message` style, and the command ends `Result: the approved knowledge was not sent to QA: <plain reason>. QA keeps answering from knowledge release <old>.` with exit `1`.

### 6. Missing prerequisites
Given any of these:
- QA is not running.
- Funnel is not on for QA.
- Docker Desktop is closed.
- QA settings or keys are missing or invalid.
- The hybrid environment (`backend/.venv-hybrid`) is missing.
- The pin-verified `bge-m3` artifact in the local home is missing or does not match its pin.
- Git has no `origin`, or the fetch fails.
- Another QA command holds the QA lock.
- The release lock is held.
- There is no terminal to confirm in.

When deploy or rollback runs · Then, before changing anything, it prints one plain line per problem naming its single fix (for example `Start it with ./scripts/init.sh --qa-deploy` or `Run ./scripts/init.sh --local-rag-setup`). It ends `Result: the approved knowledge was not sent to QA. <first fix>` (rollback: `Result: QA's knowledge was not rolled back. <first fix>`) with exit `1`. Any answer other than `yes` prints `Nothing was changed.` and exits `1`.

### 7. One-command rollback
Given QA's release log has an earlier release · When `./scripts/init.sh --qa-knowledge-rollback` runs and the owner confirms · Then:
- The command switches `current` back with `knowledge_release.rollback`, restarts the container on it, and runs the scenario 4 checks.
- It ends `Result: QA was rolled back to knowledge release <id>.` and exits `0`. Running it again rolls forward.
- With no earlier release, it ends `Result: there is no earlier QA knowledge to go back to; nothing was changed.` and exits `1`.
- If the checks fail, it restores the release that was running, restarts, and says so (exit `1`). If that also fails, it stops QA as in scenario 4.

### 8. QA image commands keep QA's knowledge, and status shows it
Given QA's release root has a `current` release · When `--qa-deploy`, `--qa-update`, or `--qa-rollback` starts the container · Then the container serves that release through the mount described in Technical approach. Without one, behavior is exactly as today (the image's release). `--qa-status` adds one line: `OK  Knowledge: release <id> published to QA` / `OK  Knowledge: the release built into the image (<id>)`, or `PROBLEM  Knowledge: QA serves <x> but the published QA release is <y>`, whose fix is `./scripts/init.sh --qa-knowledge-deploy`.

### 9. Safety
Given any run · Then:
- No token, question, answer, passage, or land text appears in output, logs, labels, or the release log.
- The QA key is read only to call `/ask` and `/metrics` on loopback.
- Container rules from `qa_server_deployment` hold: loopback publish, QA labels, `--cap-drop ALL`, and the clients file mounted read-only. The only additions are the release mount and two environment keys.
- Only the `manijero-qa` container and QA's own Funnel entry are touched.
- The temporary worktree is always removed.
- Misuse (an extra argument) prints one sentence and exits `2`.

## Technical approach

- **Module.** New stdlib-only `backend/app/qa_knowledge.py`, operator-only and never imported by the service. It reuses:
  - `qa_deployment` for facts, prerequisites, the lock, `_start`/`_wait_ready`/smoke/`_wait_public`, `_confirm`, logs, and the Funnel off/stop path.
  - `knowledge_release` (in-process) for `verify_release`, `publish`, `rollback`, `status`, and `current_release_id`.
  - `local_rag_bootstrap` for the step pattern, `gate_failure_message`, and the `bge-m3` pin check.
  - `hosted_review`'s git pattern: `git fetch origin main`, `git worktree add --detach`, and removal in `finally`.

  Builder steps run as child processes with the checkout's `.venv`/`.venv-hybrid` interpreters on the worktree's own scripts: `check_quality_gate.py check`, `manage_embeddings.py build`, and `knowledge_release.py prepare --with-vector-store --json`. `--code-revision` and `--reviewed-baseline-revision` are both the fetched `origin/main` SHA, `--as-of` is today in Europe/Madrid, and the campaign comes from the QA settings.
- **Container.** `qa_deployment.run_argv` gains an optional release id. When it is set, it adds the following, and the image's built-in release is untouched:
  - `--mount type=bind,source=<QA home>/knowledge-releases,target=/opt/manijero/qa-knowledge-releases`;
  - `--env MANIJERO_KNOWLEDGE_RELEASE_ROOT=/opt/manijero/qa-knowledge-releases`;
  - `--env MANIJERO_VECTOR_STORE=/opt/manijero/qa-knowledge-releases/releases/<id>/vector-store`;
  - `--label org.manijero.knowledge-release=<id>`.

  `deploy`/`update`/`rollback` pass QA's `current` release id when one exists. The release check reads `/metrics` with the QA key through a new probe port.
- **Commands.** `backend/scripts/qa_knowledge.py deploy|rollback`. `scripts/commands/qa.sh` gains a `--qa-knowledge-deploy|--qa-knowledge-rollback` block that uses the same misuse and no-dev-environment handling as `--qa-*`, and `usage` lists both. Test-only variables follow the existing pattern and are listed in `backend/README.md`: a repo override, fake builder interpreters, and the existing `MANIJERO_QA_HOME`/`MANIJERO_LOCAL_HOME`/`MANIJERO_DOCKER_CLI`/`MANIJERO_TAILSCALE_CLI`/`MANIJERO_QA_PORT`/`MANIJERO_QA_ADDRESS_FILE`.

## Expected file changes

- Create:
  - `backend/app/qa_knowledge.py`
  - `backend/scripts/qa_knowledge.py`
  - `backend/tests/test_qa_knowledge.py`
  - `backend/tests/test_qa_knowledge_commands.py`
- Modify:
  - `backend/app/qa_deployment.py` (`run_argv` release option, `current` lookup, status line, metrics probe port)
  - `scripts/commands/qa.sh`
  - `scripts/lib/usage.sh`
  - `backend/tests/test_qa_deployment.py` (changed argv and status only)
  - `backend/tests/test_local_rag_service.py` (`qa_knowledge` joins the operator-only module list)
- Not changed:
  - `knowledge_release.py`, `release_gates.py`, `quality_gate.py`, the baseline, `ask_api.py`, `main.py`
  - the Dockerfile, the entrypoint, `contracts/`, `knowledge/`
  - client apps, `.github/`
  - `hosted_review.py`, `knowledge_ops.py`

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `docs/constraints/operations.md`: update.
  - Add a MUST: `--qa-knowledge-deploy`/`--qa-knowledge-rollback` publish only knowledge fetched from `origin/main` and only after the quality and release gates pass, ask for `yes` first, re-check QA after every switch, and roll back automatically (or stop QA) when the checks fail. They never deploy automatically, and their acceptance is the automated walkthrough `test_qa_knowledge_commands.py` (owner decision 2026-11-11).
  - Extend the QA-commands MUST with the release mount and keys.
- `ARCHITECTURE.md`: update. Add one bullet for `qa_knowledge.py` and the QA release mount.
- `docs/owner-guide/qa.md`: update, at most about 60 lines. Add a section "Send approved knowledge to QA" with steps, `Result:` lines, and a table of the reachable messages, plus a pointer from `knowledge-review-pull-requests.md` ("merged on GitHub" → this command).
- `backend/README.md`: update, at most 30 lines. Cover the flow, argv, mount, and test-only variables.
- `knowledge/README.md`: update. One line in the release step naming the QA command.
- `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`, `PROGRESS.md`: update at acceptance.
  - Remove "QA serves the image's release until `qa_knowledge_deployment`".
  - Add the limits: the real Docker, Tailscale, and GitHub fetch paths are exercised only by fakes; "approved" means merged to `origin/main` and is not re-verified per PR; whether Chroma can write to the bind-mounted vector store is unproven, and the post-switch checks plus the automatic way back are the guard.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`, `hosting-and-pilot.md`: not needed. No rule, term, UI, or wire change.

## Focused verification (required)

Offline in `backend/.venv`. Nothing touches real Docker, Tailscale, GitHub, Ollama, a model, or the network beyond loopback test sockets and a local bare remote. Every home is a temporary folder, and every token is fake.

<!-- verify:start -->
```sh
bash -n scripts/init.sh scripts/commands/qa.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_qa_knowledge.py tests/test_qa_knowledge_commands.py tests/test_qa_deployment.py tests/test_qa_deployment_commands.py tests/test_qa_alerts.py tests/test_knowledge_release.py -q
git diff --quiet -- knowledge/ ':!knowledge/README.md' backend/config/quality_gate_baseline.json
```
<!-- verify:end -->

## Appendix

See [`qa_knowledge_deployment.appendix.md`](qa_knowledge_deployment.appendix.md) for research, planner decisions, plan, verification by behavior, evidence, and the validator checklist.
