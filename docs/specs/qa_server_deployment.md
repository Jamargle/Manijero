# Deploy, update, and roll back the QA answer service on the owner's Mac over Tailscale Funnel

## Source metadata

- `id`: qa_server_deployment · `area`: operations · `depends_on`: environment_profiles, backend_container_image, local_end_to_end_smoke, backend_health_metrics (all accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --qa-deploy` to run the QA answer service from the already built container image on their Mac, in the pilot profile, reachable by real devices at a fixed `https://<mac>.<tailnet>.ts.net` address through Tailscale Funnel; `--qa-update` ships a newer image, `--qa-rollback` puts the previous one back, `--qa-status` says in plain words whether QA runs, answers, and is reachable, and `--qa-stop` takes QA off the internet and stops it. Each ends with one plain `Result:` line.
- Verification: offline unit and subprocess tests with fake Docker and Tailscale CLIs, fake probes, fake QA homes and fake tokens (Focused verification); manual acceptance is the owner walkthrough in `docs/owner-guide/qa.md` ("Owner walkthrough: QA"): set up Tailscale, deploy, check from a phone browser, update, roll back.
- Notes: owner decisions (2026-11-02):
  1. QA host is the owner's own Mac (free). The answer service runs in the existing container image; Ollama runs on the Mac and is reached from the container through the existing relay.
  2. HTTPS for real devices goes through Tailscale Funnel (free account, fixed `https://<mac>.<tailnet>.ts.net`). No Cloudflare, no paid domain.
  3. The owner creates the Tailscale account and turns on Funnel themself from copy-paste steps in `docs/owner-guide/qa.md`; account setup is never automated.
  4. `docs/constraints/hosting-and-pilot.md` and the hosting decision record (`docs/specs/hosting_provider_review.md`) name Tailscale Funnel as QA transport only; QA uses synthetic test data only, no real users.
  5. The service still enforces its own pilot token auth, per-client rate limiting, and request-size limits, and starts only through the pilot-profile launcher (`serve_pilot.py`); the image entrypoint is reconciled with it.
  6. Deploy, update, and roll back are one named command each with plain `Result:` lines (`docs/constraints/operations.md`).
  7. QA client builds read the Funnel address from the existing git-ignored `qa-address.local`.
  8. Acceptance: validator accept plus the owner walkthrough named above.
  9. Privacy gate, option A: the pilot launcher accepts a **pending** privacy review only when `MANIJERO_ENVIRONMENT=qa` and the deploy command sets an explicit test-data-only flag; it prints a plain warning at startup; pilot and prod stay blocked. `operations.md` and `hosting-and-pilot.md` record this decision.
  10. Ollama drafting on the owner's Mac is allowed in QA under the same QA + test-data-only condition, so QA gives full drafted answers.
  Planner choices (appendix "Planner decisions"): add `--qa-status` and `--qa-stop` (operations.md requires status and stop); QA serves the knowledge release packaged in the image until `qa_knowledge_deployment`.

## Goal

Give real phones and computers a working, authenticated QA answer service over HTTPS at no cost, which the owner deploys, updates, and rolls back with one command each, while the pending privacy review keeps blocking any real-user pilot.

## Non-goals

- Real users, real questions, or a pilot/prod start; approving or editing the privacy review record; Gemini (its gate is unchanged).
- Creating the Tailscale account, enabling Funnel or HTTPS in the tailnet, installing Tailscale or Docker Desktop.
- Publishing knowledge to QA's own release folder (`qa_knowledge_deployment`); outage alerts (`qa_service_alerts`); checking QA apps on a device (`qa_real_device_check`); keeping QA up across Mac sleep or restart.
- Changing `/ask`, `/health`, `/ready`, `/metrics`, `contracts/`, app code, Spanish UI copy, pins, or the `--container-*`/`--local-rag-*` behavior.

## Job story

When I want to test Manijero on a real phone away from my desk, I want one command to put the QA answer service on a safe https address and one command each to update, undo, check, and stop it, so I never touch Docker, Tailscale settings, or Python.

## Acceptance Scenarios

### 1. First deploy
Given Docker Desktop is open, `manijero-backend:local` exists and carries the pilot launcher, its campaign equals the QA settings campaign, `--qa-settings-setup` has run, Ollama has the pinned model, Tailscale is logged in with Funnel and HTTPS allowed, and port 8100 is free · When the owner runs `./scripts/init.sh --qa-deploy` and types `yes` at the confirmation (which states that QA becomes reachable from the internet for made-up test questions only and that `--qa-stop` takes it off) · Then it tags the image `manijero-backend:qa-current`, starts container `manijero-qa` publishing only `127.0.0.1:8100`, turns Funnel on for `https://<DNSName>` → `http://127.0.0.1:8100`, waits for `/ready`, runs the smoke check (`/health`, `/ready`, one synthetic `/ask` with the QA key, all on loopback) and `/health` at the https address, writes that address into the QA settings file (`MANIJERO_PUBLIC_URL`) and `qa-address.local`, prints the address, the test-data-only warning, the next steps (rebuild QA apps, open `<address>/health` on the phone), and `Result: QA is running at https://<mac>.<tailnet>.ts.net for test data only.`, exit `0`.

### 2. Deploy while QA already runs, or after it stopped
Given QA runs and Funnel points at it · Then nothing changes and it ends `Result: QA is already running at <address>; nothing was changed. To ship a newer image use ./scripts/init.sh --qa-update.`, exit `0`. Given `qa-current` exists but no container runs (for example after a Mac restart) · Then after confirmation it starts `qa-current` again, turns Funnel on, and ends with scenario 1's result.

### 3. Missing prerequisite
Given any of: Tailscale not installed or not logged in, Funnel or HTTPS not allowed for the account, Funnel on this Mac already sharing something else, Docker Desktop missing or closed, no `manijero-backend:local` (or one without the pilot launcher, or another campaign), QA not prepared or its keys incomplete, QA settings invalid, Ollama closed or model missing, port 8100 used by another program, a `manijero-qa` container Manijero did not create, another QA command running, or no terminal to confirm in · When deploy, update, or rollback runs · Then before changing anything it prints each matching plain line naming its one fix (Tailscale lines point to the owner-guide step "Set up Tailscale"), then `Result: QA was not deployed. <first fix>` (or `... not updated` / `... not rolled back`), exit `1`. Any answer other than `yes` changes nothing, exit `1`.

### 4. Startup refused or failing
Given the container exits, `/ready` does not answer ready within 120 seconds, the smoke check fails, or Ctrl+C · Then it saves the container output to a log, removes the container it created, leaves Funnel off, prints the log path and one plain sentence (a `refused: <code>` from the launcher is translated to its fix), and ends `Result: QA was not deployed. ...`, exit `1`. No question or answer text reaches the screen or the log.

### 5. Update
Given QA was deployed and the owner ran `--container-build` since · When `./scripts/init.sh --qa-update` runs and the owner confirms · Then `qa-current` becomes `qa-previous`, the new `local` image becomes `qa-current`, the container is replaced, readiness and smoke pass, Funnel and address are unchanged, and it ends `Result: QA was updated to manijero-backend:<tag>. If something is wrong, run ./scripts/init.sh --qa-rollback.`, exit `0`. Given the `local` image is the one already running · Then `Result: nothing new to ship; QA already runs manijero-backend:<tag>.`, exit `0`. Given the new image fails scenario 4 · Then the previous image is started again, tags are restored, and it ends `Result: QA was not updated; the earlier version is running again. <first fix>`, exit `1`.

### 6. Rollback
Given `qa-previous` exists · When `./scripts/init.sh --qa-rollback` runs and the owner confirms · Then the two tags swap, the container is replaced, readiness and smoke pass, and it ends `Result: QA was rolled back to manijero-backend:<tag>.`, exit `0`; running it again rolls forward. Given no `qa-previous` · Then `Result: there is no earlier QA version to go back to; nothing was changed.`, exit `1`. A failed rollback restarts the version that was running and says so, exit `1`.

### 7. Status
When `./scripts/init.sh --qa-status` runs · Then it prints `OK`/`PROBLEM` lines for Container (tag, release, start time UTC), Answers (`/ready` on loopback), Drafting (relay reaches Ollama), Internet address (Funnel on and pointing at `127.0.0.1:8100`), and Address files (QA settings and `qa-address.local` agree), plus `Test data only: the privacy review is still pending.`, and ends `Result: QA is running at <address> for test data only.` (exit `0`) or `Result: QA needs attention: <first fix>` / `Result: QA is not running. Start it with ./scripts/init.sh --qa-deploy.` (exit `1`). It changes nothing.

### 8. Stop
When `./scripts/init.sh --qa-stop` runs · Then it first turns off the Funnel entry that points at `127.0.0.1:8100`, then stops and removes `manijero-qa`, keeps both tags and address files, and ends `Result: QA has stopped and is no longer reachable from the internet.`, exit `0`; with nothing running, `Result: QA was not running, so there was nothing to stop.`, exit `0`. Containers without the QA labels and other Funnel entries are never touched.

### 9. Privacy gate
Given the committed review record with `pilot_review.status=pending` · Then the pilot launcher starts and local drafting is enabled only when the environment carries exactly `MANIJERO_DEPLOYMENT_PROFILE=pilot`, `MANIJERO_ENVIRONMENT=qa`, and `MANIJERO_QA_TEST_DATA_ONLY=yes`; startup prints `WARNING: QA test-data-only mode. The privacy review is still pending: use only made-up test questions; no real users.` and `privacy_review: pending (QA test data only)`. Any other environment value, a missing or different flag, or a `rejected`/invalid/unreadable record keeps `refused: privacy_review_*` and extractive answers, exactly as today. Gemini stays blocked. Only the QA commands set the flag; it is not a settings-file key.

### 10. Safety
Given any QA run · Then requests without a valid QA bearer token get `401` on `/ask` and `/metrics`, the per-client limit and body bound apply, logs follow the pilot logging rule, the container publishes only on host `127.0.0.1`, runs non-root with `--cap-drop ALL`, receives only the fixed QA environment and a read-only mount of the digest-only clients file, and no output, label, or log contains a token, question, answer, or land value. Misuse (extra argument) prints one sentence, exit `2`.

## Technical approach

- **Gate.** `backend/app/privacy_review.py` gains `qa_test_data_mode(env)` (exact `pilot` + `qa` + `yes`) and `pilot_gate(record, env, as_of)`, which passes a review whose `pilot_review.status` is exactly `pending` only in that mode and reports `qa_test_data=True`. `pilot_ops.run_preflight` and `local_generation.resolve_local_provider` use it; `evaluate_pilot_review` and the Gemini gate are unchanged. `PreflightReport` gains `qa_test_data_only`; `serve_pilot.py` prints the warning and summary line.
- **Image.** `entrypoint.py` keeps the default path; when `MANIJERO_DEPLOYMENT_PROFILE=pilot` it starts the relay, then calls `serve_pilot.main(["--host","0.0.0.0","--port","8000","--workers","1"])` with `MANIJERO_PILOT_ALLOW_PUBLIC_BIND=1` set for its own process only (the host publish stays loopback). The Dockerfile and allowlist add `backend/scripts/serve_pilot.py` and label `org.manijero.launchers=default,pilot`.
- **Operator.** New stdlib-only `backend/app/qa_deployment.py` (never imported by the service) reuses `local_container` (`DockerCli`, lock, label and image helpers, log saving), `local_rag_service` probes, `environment_profiles` (QA settings, credential paths, a new `write_public_url`), and `pilot_ops.run_smoke`. New port `TailscaleCli` runs `${MANIJERO_TAILSCALE_CLI}` (tests only) else `tailscale` on `PATH` else the app-bundle CLI; it reads `status --json` and turns Funnel on/off for 443 → `http://127.0.0.1:8100`. Fixed argv and constants are in the appendix.
- **Commands.** `scripts/init.sh` adds an early `--qa-deploy|--qa-update|--qa-rollback|--qa-status|--qa-stop` dispatch beside `--container-*` (same misuse and no-dev-env handling) that runs `backend/.venv/bin/python backend/scripts/qa_service.py <op>`; `usage` and `--check` list them.

## Expected file changes

- Create: `backend/app/qa_deployment.py`, `backend/scripts/qa_service.py`, `backend/tests/test_qa_deployment.py`, `backend/tests/test_qa_deployment_commands.py`, `backend/tests/test_qa_test_data_gate.py`.
- Modify: `backend/app/privacy_review.py`, `pilot_ops.py`, `local_generation.py`, `environment_profiles.py` (`write_public_url` only), `backend/scripts/serve_pilot.py`, `backend/container/entrypoint.py`, `Dockerfile`, `Dockerfile.dockerignore`, `scripts/init.sh`; tests `test_container_image_files.py`, `test_pilot_operations.py`, `test_local_generation.py`, `test_environment_profiles.py` for the changed behavior only.
- Not changed: `main.py`, `ask_api.py`, `pilot_guard.py`, `pilot_config.py`, `backend/config/*` (including `pilot_privacy_review.json`), `contracts/*`, `knowledge/*`, client apps and Gradle files.

## Visual design impact

UI involved: no. No app screen or Spanish copy changes; QA apps already read `qa-address.local`.

## Durable documentation impact (required)

- `docs/constraints/hosting-and-pilot.md`: update — the tunnel rule names Tailscale Funnel as QA transport only; new MUST: QA runs on the owner's Mac with synthetic test data only and the pending-review override of scenario 9 (owner decision 2026-11-02, option A), drafting allowed under it, pilot/prod/Gemini still blocked; the launcher's public-bind acknowledgement is allowed only inside the container with a loopback host publish.
- `docs/constraints/operations.md`: update — the intro's "never relax a ... gate" names the owner-decided QA test-data-only exception; new MUST for the five QA commands (loopback publish, QA labels only, Funnel touched only for its own entry, stop removes Funnel first, confirmation before deploy/update/rollback); the `qa-address.local` MUST NOT now says `--qa-deploy` writes the address there and in the QA settings file.
- `docs/specs/hosting_provider_review.md`: update — dated addendum "QA transport (2026-11-02)": Tailscale Funnel on the owner's Mac, transport only, test data only; pilot selection unchanged.
- `ARCHITECTURE.md`: update — one bullet for `qa_deployment.py` and the entrypoint's pilot path.
- `docs/owner-guide/qa.md`: update (≤ ~60 lines) — "Set up Tailscale (one time)" (account, install, log in, turn on HTTPS and Funnel), "Deploy / Update / Roll back / Check / Stop QA", "Owner walkthrough: QA"; update "Build the QA test apps" step 3.
- `backend/README.md`: update (≤ ~30 lines) — QA deployment internals, argv, test-only `MANIJERO_TAILSCALE_CLI`/`MANIJERO_QA_PORT`.
- `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`, `PROGRESS.md`: update at acceptance — QA depends on the Mac being awake; Funnel exposes a public hostname; test-data-only is a rule, not a technical filter; clients-file readability under Docker Desktop is proven only by the walkthrough.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`, `docs/constraints/lands.md`: not needed — the relay is unchanged.

## Focused verification (required)

Offline in `backend/.venv`: no Docker, Tailscale, Ollama, model, or network beyond loopback test sockets; temporary `MANIJERO_QA_HOME`, `MANIJERO_LOCAL_HOME`, `MANIJERO_QA_ADDRESS_FILE`, fake `MANIJERO_DOCKER_CLI` and `MANIJERO_TAILSCALE_CLI`, fake tokens only.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_qa_test_data_gate.py tests/test_qa_deployment.py tests/test_qa_deployment_commands.py tests/test_container_image_files.py tests/test_pilot_operations.py tests/test_local_generation.py tests/test_environment_profiles.py tests/test_local_container.py -q
```
<!-- verify:end -->

The owner walkthrough (real Tailscale, Docker Desktop, Ollama, and a phone browser) is the manual acceptance check; the orchestrator records it, it is not part of this block.

## Appendix

See [`qa_server_deployment.appendix.md`](qa_server_deployment.appendix.md) for research, planner decisions, fixed argv, plan, evidence, and the validator checklist.
