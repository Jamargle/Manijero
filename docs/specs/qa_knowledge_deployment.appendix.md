# qa_knowledge_deployment — appendix

Contract: [`qa_knowledge_deployment.md`](qa_knowledge_deployment.md).

## Repository research

- `backend/app/qa_deployment.py` — QA operator: `run_argv` (fixed argv, no release mount today), `_gather`/`_problems` prerequisite collector, `_start` (remove ours, run, `_wait_ready`, smoke), `_wait_public`, `_confirm`, `_log`, `_stop_locked` (Funnel off first), `run_status`, lock `.qa.lock`, `version_tag` from image labels. The main module to extend and reuse.
- `backend/container/Dockerfile:49-63` — the image bakes one release at `/opt/manijero/knowledge-releases/releases/<RELEASE_ID>` (chowned to 10001 because Chroma opens the store in place) and sets `MANIJERO_KNOWLEDGE_RELEASE_ROOT`, `MANIJERO_VECTOR_STORE`, and hybrid retrieval. `docker run --env` overrides these, so no image change is needed.
- `backend/app/knowledge_release.py` — `verify_release`, `publish`, `rollback(to=...)`, `status`, `current_release_id`, `release_lock`, release log events, `prepare_release`, and `approval_from_options` (`--reviewed-baseline-revision`). Used in-process for switching. `prepare` runs as a child process in the hybrid venv.
- `backend/app/local_rag_bootstrap.py:1193-1276` — the existing embedding-build → `prepare --with-vector-store --json` → `publish` steps, `gate_failure_message`/`GATE_WORDS`, `last_json_object`, and the `bge-m3` paths and pin verification (`verify_artifact`). This is the pattern to copy, so the pipeline is not reinvented.
- `backend/app/local_rag_service.py:310-324` — the local launch environment sets `MANIJERO_VECTOR_STORE` per release id. That is why a knowledge switch restarts the container: a store from another release is stale.
- `backend/app/main.py:232-241`, `health_metrics.py:83,246` — `/metrics` exposes `knowledge_release_info{release_id,state}`, which is pilot-token gated in QA. It is the served-release check.
- `backend/app/pilot_ops.py:387` — `run_smoke` (`/health`, `/ready`, synthetic `/ask`), already used by QA.
- `backend/app/hosted_review.py` — the git port, `REPO_ENV` test override, the temporary `git worktree add --detach origin/main` with removal in `finally`, and the Europe/Madrid `as_of`. The merged PR carries `knowledge/source_catalog.json`, `passages.json`, and `knowledge/reviews/<id>/`, not a `merge.json`, so approval evidence is the reviewed baseline revision.
- `backend/scripts/check_quality_gate.py` / `backend/app/quality_gate.py` — `check` resolves the repository from its own file path, so running the worktree's copy gates the merged `main` exactly. Exit `0` pass, `1` regression, `2` not enforced.
- `docs/specs/structured_chunk_index.md` — the flag is honoured in QA only when set, and no QA command sets it, so this feature keeps it off.
- `scripts/commands/qa.sh` — the early-dispatch pattern for `--qa-*`. `scripts/lib/usage.sh` holds the help text.
- `docs/constraints/operations.md:13,17,27` — the confirmation, walkthrough, and QA-command MUSTs this feature extends. The walkthrough MUST is met by an automated walkthrough (owner decision 3), as for `knowledge_ops_orchestrator` and `hosted_review_pull_requests`.
- Not inspected: `test_qa_deployment_commands.py` fake-CLI helpers in detail (the implementer reuses them), the real Docker Desktop bind-mount ownership behavior, and `manage_embeddings.py` argv beyond the bootstrap call.

## Planner decisions

- **Approved source = `origin/main` after `git fetch origin main`.** `main` is protected (`protected-main`: PR plus `fast`/`full` checks) and the owner merges. No `gh` call is made. Building in a temporary worktree means a dirty or off-`main` checkout cannot leak in.
- **Gates.** The quality gate (reviewed baseline) runs first because it is the cheapest. Then come the release builder's structural, BM25, grounding/evaluation, and regression gates. The regression baseline is QA's current release, because `prepare --root <QA root>`.
- **First deploy adopts the image's release.** The command runs `docker cp manijero-qa:/opt/manijero/knowledge-releases/releases/<id> <staging>`, moves it into `<QA root>/releases/<id>` after `verify_release`, then calls `publish`. The automatic way back therefore always targets a real, verified release, and no change to `knowledge_release.py` is needed.
- **Nothing-new check** compares catalog, passages, and case SHA-256. It does not compare release ids, because the id includes `as_of` and the code revision.
- **QA must be running** for deploy and rollback, because the post-switch checks are the safety net (owner decision 2).
- **Double failure stops QA** (Funnel off, then the container is removed). Serving unknown knowledge is worse than being off for test-only QA.
- **The mount is writable**, as the image's store is chowned for Chroma. Ownership under Docker Desktop is unproven, and a failure surfaces in the post-switch checks.
- **Lock order:** the QA lock (`.qa.lock`, shared with `--qa-*`) first, then the release lock only around publish and rollback.
- **Command names:** `--qa-knowledge-deploy`, `--qa-knowledge-rollback`. Status stays in `--qa-status`.

## Implementation plan

1. `qa_deployment.py`: `run_argv(port, campaign, clients, release_id=None)` adds the mount, the two environment keys, and the label. A helper `qa_release_id(home)` wraps `kr.current_release_id`. `deploy`/`update`/`rollback` pass it. Add a `Knowledge` status line, a `metrics_release` probe port with a system implementation (GET `/metrics` with bearer, parse `knowledge_release_info`), and public names for the reused helpers.
2. `qa_knowledge.py`: `Ports` (QA ports plus git runner, builder runner, artifact checker, clock), the prerequisite collector (scenario 6), the fetch/worktree context manager, `adopt_image_release`, `nothing_new`, `build_candidate` (quality gate → embeddings → prepare), `switch_and_check`, `auto_restore`, `stop_qa`, `run_deploy`, `run_rollback`, and a reason → plain-sentence table.
3. `backend/scripts/qa_knowledge.py`: argv dispatch, real ports, a Ctrl+C sentence, and tracebacks to `<QA home>/logs/qa-knowledge-<op>-<UTC>.log` only.
4. `scripts/commands/qa.sh` dispatch block and the `scripts/lib/usage.sh` lines.
5. Tests (below), then docs per the contract, with the owner guide last.

## Verification plan

- `test_qa_knowledge.py` (in-memory fakes; fixture knowledge from `backend/tests/fixtures/` or a temporary copy of `knowledge/`; fake builder runs that call `kr.prepare_release` in-process without vectors and create an empty `vector-store/`):
  - Happy path order: fetch → worktree → quality gate → embeddings → prepare → confirm → publish → container replaced with the mount argv → checks → Result line. The worktree is removed.
  - First deploy adopts the image's release (with `docker cp` argv). A copy or verify failure changes nothing.
  - Nothing new: no build, no prompt, exit 0.
  - Each gate failure: quality `1`/`2`, embeddings, prepare `1` (gate/regression) and `2` (approval). `current` and the container are unchanged, and the Result names the old release.
  - Each post-switch check failure (ready timeout, exited container, smoke, wrong `/metrics` release, public `/health`) leads to the automatic rollback to the old id, a container restart, and exit 1. A failure of that way back too leads to Funnel off before stop and the stop Result.
  - Rollback: swap, roll forward, no earlier release, a failure that restores.
  - Every scenario-6 prerequisite produces one line and nothing changed. A non-`yes` answer and a missing tty change nothing.
  - No token, question, or passage text appears in output or logs. The QA lock is respected.
- `test_qa_knowledge_commands.py` (automated owner walkthrough through `./scripts/init.sh` with fake `docker` and `tailscale` executables, a local bare remote and clone, and fake builder interpreters):
  - Exit codes `0/1/2` and the exact Result lines for deploy, a gate failure, an auto-rollback, rollback, and nothing new.
  - At least one missing-prerequisite case (QA not running), and its recovery after `--qa-deploy`.
  - Misuse prints one sentence and exits `2`.
- `test_qa_deployment.py`: `run_argv` without a release id is byte-identical to today, and with one it adds exactly the mount, the two keys, and the label. Deploy/update/rollback pass QA's current release. Cover the status `Knowledge` lines.
- `test_qa_alerts.py`, `test_knowledge_release.py`: unchanged suites rerun as guards.

## Evidence to capture

- The focused block result line and the `bash -n` result.
- One Result-line transcript per walkthrough case from `test_qa_knowledge_commands.py`.
- The fake-docker argv of a knowledge-serving `docker run`, with tokens redacted.
- `git diff --stat` showing no change to `knowledge/`, gates, the baseline, the Dockerfile, or `contracts/`.
- Honest limits as listed in the contract's documentation section.

## Feature evidence

- `./scripts/init.sh --feature qa_knowledge_deployment` (bash -n; 6 backend suites; `git diff --quiet -- knowledge/ ':!knowledge/README.md' backend/config/quality_gate_baseline.json`): `237 passed, 1 warning`. Spec fix: the `knowledge/` diff check excludes `knowledge/README.md`, which the contract itself updates.
- `test_qa_knowledge.py`: 56 passed (happy path order and argv, adoption and its failures, nothing new, six gate failures, not-ready release, five post-switch failures with automatic way back, double failure stops QA with Funnel off first, Ctrl+C, rollback and roll forward, 11 prerequisites for deploy and rollback, non-`yes`, no secrets, container additions exactly mount + two keys + label).
- `test_qa_knowledge_commands.py` (automated walkthrough via `scripts/init.sh`, pty `yes`, fake docker/tailscale, local bare origin, loopback QA service): 10 passed. Result lines seen: deploy `Result: QA now answers from knowledge release <id> (main at <sha7>). If something is wrong, run ./scripts/init.sh --qa-knowledge-rollback.`; again `Result: QA already has the approved knowledge from main; nothing was changed.`; gate failure `Result: the approved knowledge was not sent to QA: <reason>. QA keeps answering from knowledge release <old>.`; metrics mismatch `Result: the new knowledge failed the QA checks (QA does not report the knowledge release ...), so QA went back to knowledge release <old> automatically. ...`; rollback and roll forward `Result: QA was rolled back to knowledge release <id>.`; none earlier `Result: there is no earlier QA knowledge to go back to; nothing was changed.`; QA not running `Result: the approved knowledge was not sent to QA. Start it with ./scripts/init.sh --qa-deploy` (rollback variant `QA's knowledge was not rolled back.`), then recovered after QA runs; misuse exit 2.
- `test_qa_deployment.py`: 56 passed (run_argv unchanged without a release; deploy/update/rollback pass QA's current release; `Knowledge` status lines).
- Fake-docker argv of a knowledge-serving run (tokens never present): `run --detach --init --name manijero-qa --label ... --label org.manijero.knowledge-release=<id> --publish 127.0.0.1:<port>:8000 --env ... --env MANIJERO_KNOWLEDGE_RELEASE_ROOT=/opt/manijero/qa-knowledge-releases --env MANIJERO_VECTOR_STORE=/opt/manijero/qa-knowledge-releases/releases/<id>/vector-store --mount type=bind,source=<clients>,target=/run/manijero/pilot-clients.json,readonly --mount type=bind,source=<QA home>/knowledge-releases,target=/opt/manijero/qa-knowledge-releases --cap-drop ALL ...`.
- `CI=true ./scripts/init.sh --fast`: backend suite `3587 passed, 3 failed`; every other check ok. The 3 failures (`test_container_image_files::test_the_service_environment_is_the_local_rag_one_with_image_paths`, `test_local_rag_service::test_start_when_ready_launches_the_service_in_the_background`, `...names_the_knowledge_ops_folder_only_when_it_exists`) depend on `~/manijero/knowledge-ops` existing on this host (`launch_environment` adds `MANIJERO_KNOWLEDGE_OPS_STATE_DIR`); they exercise code this feature does not touch. One real fix came from the run: `qa_knowledge` added to the operator-module list in `test_local_rag_service.py`.
- Not run: `--verify` (no Android/Desktop, Gradle, or packaging change). Honest limits: real Docker, Tailscale, GitHub paths only by fakes; bind-mounted Chroma write access unproven.

## Validator checklist

- Publishing happens only after an explicit `yes`, only from fetched `origin/main`, and only after the quality and release gates pass. There is no automatic trigger anywhere (no launchd, merge, or `knowledge_ops` hook).
- Every switch is followed by the checks. A failure rolls back automatically to the old release (or stops QA with Funnel off first) and is reported in plain words with a non-zero exit.
- `run_argv` without a release is unchanged. The additions are exactly the mount, two environment keys, and the label. Loopback publish, the QA labels, the read-only clients file, and `--cap-drop ALL` are kept.
- The owner's checkout and `knowledge/` are untouched, the worktree is always removed, and there is no `gh`, push, or force.
- No token, question, answer, or passage text appears in output, logs, labels, or the release log. Tests use only fake tokens and temporary homes.
- The automated walkthrough covers a missing prerequisite and its recovery. The operations MUST, owner guide (within budget), backend README, and ARCHITECTURE are updated, and the limits are recorded at acceptance.
