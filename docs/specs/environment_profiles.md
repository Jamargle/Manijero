# Define local, QA, and prod environment profiles

## Source metadata

- `id`: environment_profiles · `area`: operations · `depends_on`: hosted_pilot_operations, local_full_rag_stack (both accepted) · `status` at planning: not_started
- User-visible behavior: three named environments. **local** is complete, working, and the default for development: its one commented settings file (`~/manijero/local/settings.env`) names its environment and deployment profile explicitly and points at its own knowledge release root, and `--local-rag-setup` generates local credentials under `~/manijero/local/credentials` (the local service still does not enforce tokens; they exist so local client builds in `client_environment_builds` use the same flow). **QA** gets one commented settings file created on this computer from a committed template with placeholder host values only, plus locally generated, never-printed credentials and its own knowledge release root; nothing is deployed and no server is contacted. **prod** is left unconfigured. `./scripts/init.sh --environments-status` says in plain words what each environment has; `./scripts/init.sh --qa-settings-setup` prepares QA on this computer.
- Verification: offline pytest with temporary homes and fake prompts plus `init.sh` subprocess runs (Focused verification). Manual acceptance check: the independent validator runs every new owner-guide step against temporary homes (never the real `~/manijero`), including one missing-prerequisite case and one recovery.
- Notes — owner decisions dated 2026-11-02:
  1. Three profiles: local (complete, working, the default for development); QA as a commented settings template with placeholder host values only (choosing a QA host belongs to `qa_server_deployment`; do not deploy or contact any server); prod left unconfigured.
  2. Each profile's credentials are generated locally by a script and git-ignored; never commit secrets.
  3. Each profile points at its own knowledge release.
  4. Zero budget: no paid services.
  5. Sibling feature `answer_pipeline_trace` treats an unset `MANIJERO_DEPLOYMENT_PROFILE` as local; make the profile explicit in each settings file so a non-local deployment never silently runs as local. The trace code is not on this branch; do not edit or depend on it.
  6. The independent validator's accept is final; no owner walkthrough is required.
  - Orchestrator answers (2026-11-02): (a) decision 2 applies literally to local too: token file plus digest-only clients file, `0600`, under `~/manijero/local/credentials`, created idempotently by `--local-rag-setup`, never overwriting an existing token; the local service still does not enforce tokens. (b) This feature does not depend on `answer_pipeline_trace`'s contract: the local start environment stays as is (`MANIJERO_DEPLOYMENT_PROFILE` unset, which `pilot_config` reads as `development`, i.e. local); the safety requirement is only that QA settings state `MANIJERO_ENVIRONMENT=qa` and `MANIJERO_DEPLOYMENT_PROFILE=pilot` explicitly and are refused otherwise. (c) Command names and `~/manijero/qa` confirmed.
  - Planner choices (appendix "Planner decisions"): homes `~/manijero/<environment>`, client ids, the placeholder host.

## Goal

Give every later environment feature (`monitoring_dashboard`, `client_environment_builds`, `qa_server_deployment`, `qa_knowledge_deployment`) one validated place to read an environment's settings, credentials, and knowledge release, and make it impossible for a QA or prod settings file to be read as local by default.

## Non-goals

- Deploying, starting, or contacting any QA or prod server; choosing a QA host, domain, tunnel, or TLS; turning the QA file into the host's `pilot.env` (`qa_server_deployment`).
- Publishing any knowledge release to QA (`qa_knowledge_deployment`); building apps for an environment or giving an app the QA token (`client_environment_builds`).
- Starting a pilot-profile service locally: `serve_pilot.py` preflight blocks while the privacy review is `pending`, and no gate is relaxed here.
- Prod settings, files, homes, or commands of any kind.
- Credential rotation or revocation beyond regenerating an incomplete QA pair (`pilot_ops.py upsert-client`/`remove-client` stay as is).
- Changing the answer service (`main.py`, `pilot_config.py`, `ask_api.py`), its accepted profile values (`development`, `pilot`), `contracts/`, `knowledge/`, pins, or `pilot-token.local`. Any paid service.

## Job story

When I start testing Manijero outside my own computer, I want each environment to have its own settings, its own access keys made for me, and its own knowledge, and one command that tells me what each one has, so I never mix QA up with my local setup or leak a key.

## Acceptance Scenarios

### 1. Status on a fresh computer
Given no `~/manijero/local/settings.env` and no `~/manijero/qa` · When the owner runs `./scripts/init.sh --environments-status` · Then it prints three lines in the order local, QA, prod: `NOT SET UP  local` naming `./scripts/init.sh --local-rag-setup`, `NOT SET UP  QA` naming `./scripts/init.sh --qa-settings-setup`, `NOT SET UP  prod: not configured; prod is not planned yet.`, then `Result: the local environment is not set up yet. Run ./scripts/init.sh --local-rag-setup.`, exit `1`. It writes nothing and makes no network call.

### 2. Status with local ready
Given a valid local settings file with both environment lines and a published release under `~/manijero/local/knowledge-releases` · When status runs · Then the local line is `OK  local (default)` with the settings path, `profile development`, the campaign, the release id, and `access keys ready (not checked by the local service)`; QA and prod lines as they are; `Result: the local environment is ready.` (plus `QA is prepared on this computer but has no server yet.` when QA is set up), exit `0`. A valid local file with no published release shows `ATTENTION  local: no knowledge release yet` naming `./scripts/init.sh --local-rag-setup`, exit `1`. Status never runs the six-part `--local-rag-status` check and never shows a token, digest, or settings secret.

### 3. Prepare QA on this computer
Given the dev environment exists and `~/manijero/qa` does not · When the owner runs `./scripts/init.sh --qa-settings-setup` · Then it creates `~/manijero/qa/settings.env` (mode `0644`) from `backend/deploy/environments/qa.settings.env.example` with the QA home paths filled in, `~/manijero/qa/credentials/` (mode `0700`) with `pilot-clients.json` (one enabled client `qa-test-device`, 20 requests per minute, SHA-256 digest only) and `qa-test-device.token` (at least 32 random characters), both mode `0600`, and `~/manijero/qa/knowledge-releases/` (empty). It prints what it created, that the QA address is a placeholder until the QA server is chosen, that no server was contacted, and `Result: QA is prepared on this computer. Nothing was deployed.`, exit `0`. The token never appears on screen, in a log, or in any repository file.

### 4. Re-running QA setup
Given QA is already prepared and consistent · When setup runs again · Then nothing is created or rewritten (bytes and modes unchanged), it prints the QA status line and `Result: QA was already prepared; nothing was changed.`, exit `0`.

### 5. Incomplete QA credentials (recovery)
Given one of the two credential files is missing, unreadable, too open (any group/other bit), or the token's digest is not an enabled client in the clients file · When setup runs in a Terminal · Then it says the QA access keys are incomplete, that new ones replace both files and any copy of the old QA token stops working, and asks `Make new QA access keys? Type yes and press Enter:`. `yes` replaces both files atomically and ends `Result: new QA access keys were made. Nothing was deployed.` exit `0`; anything else changes nothing, exit `1`. Without a terminal it changes nothing, says to run it in a Terminal window, exit `1`. Status shows this case as `PROBLEM  QA` naming `./scripts/init.sh --qa-settings-setup`, exit `1`.

### 6. A settings file that does not say it is non-local (decision 5)
Given a QA settings file with no `MANIJERO_ENVIRONMENT` line, no `MANIJERO_DEPLOYMENT_PROFILE` line, `MANIJERO_ENVIRONMENT` other than `qa`, `MANIJERO_DEPLOYMENT_PROFILE` other than `pilot`, an unknown or repeated key, an invalid campaign, a relative path, or a knowledge release root equal to, inside, or containing the local one · When status reads it, or any later tool reads it through `read_profile_settings("qa")` · Then it is refused with one plain sentence naming the file, the line, and the fix (for the profile lines: `this file is for QA, so it must say MANIJERO_DEPLOYMENT_PROFILE=pilot; it is never treated as local`), status prints `PROBLEM  QA`, exit `1`; nothing is defaulted to local or to `development`. A local settings file that sets `MANIJERO_ENVIRONMENT` other than `local` or `MANIJERO_DEPLOYMENT_PROFILE` other than `development` is refused the same way by every `--local-rag-*`, `--container-*`, and `--local-smoke` command.

### 7. Existing local settings without the environment lines (missing prerequisite)
Given the owner's existing local `settings.env` holds only `MANIJERO_ACTIVE_CAMPAIGN` · Then every `--local-rag-*`, `--container-*`, and `--local-smoke` command still works unchanged; status shows `ATTENTION  local: the settings file does not say it is for the local environment` naming `./scripts/init.sh --local-rag-setup`, exit `1`. When `--local-rag-setup` runs (including on its "already set up" path) it appends exactly `MANIJERO_ENVIRONMENT=local` and `MANIJERO_DEPLOYMENT_PROFILE=development` with their comment lines, keeps every existing byte, and prints `Added the environment lines to the settings file <path>; nothing else in it changed.` A newly created local settings file contains both lines.

### 7b. Local credentials
Given local setup reaches the same point (prerequisite checks passed) · Then it ensures `~/manijero/local/credentials/` (`0700`) holds `local-test-device.token` (at least 32 random characters) and `pilot-clients.json` (client `local-test-device`, 20 requests per minute, digest only), both `0600`, printing `Made the local access keys in <folder>.` only when it created something. An existing token file is never overwritten: a missing or mismatched clients file is rewritten from the existing token's digest; a missing token gets a new token whose digest replaces that client's entry; a group/other bit on either file is removed and named. Re-runs with a consistent pair change nothing. A valid local file with missing or inconsistent credentials shows `ATTENTION  local: the local access keys are missing or incomplete` naming `./scripts/init.sh --local-rag-setup`, exit `1`; the local service, container, and smoke commands never read the credentials. The token never appears on screen, in a log, or in any repository file.

### 8. Prod stays unconfigured
Given any state, including an existing `~/manijero/prod` folder · Then status always prints the constant prod line, reads nothing under it, and no command creates, reads, or accepts a prod settings file (`read_profile_settings("prod")` refuses with `prod_not_configured`).

### 9. Misuse and safety
Given an extra argument after either new command · Then one plain sentence, nothing changed, exit `2`. Given `MANIJERO_QA_HOME` or `MANIJERO_LOCAL_HOME` (tests only) inside this checkout · Then QA setup refuses before writing, exit `1`. Without the dev environment both commands print the existing "not set up yet" pair, exit `1`. No command contacts the network, reads `pilot-token.local` or any `.env` secret file outside the profile homes, or downloads anything; the committed template contains only `.invalid` placeholder hosts and no secret.

## Technical approach

- **Module.** New `backend/app/environment_profiles.py`, operator-only, stdlib plus existing `app` imports, never imported by the service. It owns: the three profile definitions (`local` -> deployment profile `development`, home `MANIJERO_LOCAL_HOME` or `~/manijero/local`; `qa` -> `pilot`, home `MANIJERO_QA_HOME` (tests only) or `~/manijero/qa`; `prod` -> unconfigured), an allowlisted `KEY=VALUE` reader (never sourced), `read_profile_settings(name) -> ProfileSettings` raising `ProfileSettingsError(code, sentence)`, `run_status`, `run_qa_setup`, and injected ports (output, prompter with tty flag) like `local_rag_bootstrap`.
- **QA keys (exact allowlist).** `MANIJERO_ENVIRONMENT=qa`, `MANIJERO_DEPLOYMENT_PROFILE=pilot`, `MANIJERO_ACTIVE_CAMPAIGN` (four digits), `MANIJERO_PUBLIC_URL` (`https://`; host ending `.invalid` = placeholder, reported, not a problem), `MANIJERO_PILOT_CLIENTS_FILE` and `MANIJERO_KNOWLEDGE_RELEASE_ROOT` (absolute, outside the checkout, not overlapping local). The template is committed at `backend/deploy/environments/qa.settings.env.example` with `@QA_HOME@` replaced at setup.
- **Credentials.** Token `secrets.token_urlsafe(48)` written with `O_EXCL`, mode `0600`; clients file written through `pilot_ops.upsert_client` (digest only), then mode-checked. Neither value is printed or logged. `.gitignore` gains guard patterns `*.token` and `pilot-clients*.json`; homes inside the checkout are refused.
- **Local.** `local_rag_bootstrap.read_settings` accepts the two new keys (validated values only); `SETTINGS_TEMPLATE` gains them; `run_setup` appends missing lines and ensures local credentials (shared helper in `environment_profiles.py`) once its prerequisite checks pass (Ollama, clean knowledge, no lock) and before any download question; a cancelled download keeps both. `local_rag_service.launch_environment` and `local_container` stay unchanged (the service still receives no `MANIJERO_DEPLOYMENT_PROFILE`, which `pilot_config` reads as `development`, i.e. local, and no credential path).
- **Commands.** `scripts/init.sh` early dispatch (beside `--local-rag-*`): `--environments-status` and `--qa-settings-setup` run `backend/.venv/bin/python backend/scripts/environments.py status|qa-setup`; same misuse and no-dev-environment handling; `usage` and `--check` listing updated.

## Expected file changes

- Create: `backend/app/environment_profiles.py`, `backend/scripts/environments.py`, `backend/deploy/environments/qa.settings.env.example`, `backend/tests/test_environment_profiles.py`, `backend/tests/test_environment_profiles_commands.py`.
- Modify: `backend/app/local_rag_bootstrap.py` (keys, template, append, local credentials step), `scripts/init.sh`, `.gitignore`, `backend/tests/test_local_rag_bootstrap.py`, `backend/tests/test_local_rag_service.py` (launch env has no profile key).
- Docs as below. Not changed: `main.py`, `pilot_config.py`, `pilot_ops.py`, `serve_pilot.py`, `local_rag_service.py` logic, `local_container.py`, `backend/deploy/pilot.env.example`, `contracts/`, `knowledge/`, `backend/config/`, any Kotlin.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `docs/constraints/operations.md`: update — one MUST: every environment settings file names `MANIJERO_ENVIRONMENT` and `MANIJERO_DEPLOYMENT_PROFILE` explicitly and a non-local file without `pilot` is refused, never defaulted to local; environment credentials are generated by a command into that environment's home outside the checkout, mode `0600`, never printed. Reason: `environment_profiles`.
- `ARCHITECTURE.md`: update — one sentence: `environment_profiles.py` is the operator-only reader of per-environment settings, credentials, and release roots that later environment features must use.
- `docs/owner-guide/pilot-token-and-settings.md` and `docs/owner-guide/qa.md` ("Prepare QA on this computer"): update (at most 60 lines) — "Your environments" (status), "Prepare QA on this computer" (steps, `Result:` lines, table of reachable messages), "Your settings file" (the two new lines), and "Where things are kept" (`credentials/` per environment; never share or move it).
- `backend/README.md`: update (at most 30 lines) — "Environment profiles" under "One-command local setup": homes, key allowlist, `read_profile_settings` codes, credential files and modes.
- `docs/risks-and-open-questions.md`: update — the pilot-token row's "once a service can be started (`environment_profiles`)" pointer moves to `qa_server_deployment`/`qa_real_device_check`; add that QA credentials exist only on this computer until deployed.
- `PROGRESS.md`, `docs/progress/known-limitations.md`: one line each at acceptance. `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

Offline in `backend/.venv`; temporary `MANIJERO_LOCAL_HOME`/`MANIJERO_QA_HOME`, empty `MANIJERO_VENV_ROOT`; no network, no real home writes.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
git check-ignore -q backend/qa-test-device.token
git check-ignore -q pilot-clients.json
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_environment_profiles.py tests/test_environment_profiles_commands.py tests/test_local_rag_bootstrap.py tests/test_local_rag_service.py tests/test_local_rag_commands.py -q
```
<!-- verify:end -->

Manual check (validator, not run by the harness): follow the new owner-guide sections exactly, with `MANIJERO_LOCAL_HOME` and `MANIJERO_QA_HOME` set to temporary folders: status before setup (missing prerequisite), QA setup, re-run, delete the token file then re-run setup and answer `yes` (recovery), and an old-style local settings file (campaign line only) then `--local-rag-status` (no settings error) and status (`ATTENTION  local`). The `--local-rag-setup` append path is covered by fakes only; the validator does not run a real setup.

## Appendix

See [`environment_profiles.appendix.md`](environment_profiles.appendix.md) for research, plan, evidence, and the validator checklist.
