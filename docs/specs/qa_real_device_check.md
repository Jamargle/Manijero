# Check the QA Desktop app against the live QA service end to end with one command

## Source metadata

- `id`: qa_real_device_check · `area`: testing · `depends_on`: qa_server_deployment, client_environment_builds (both accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --qa-check`. It builds the `Manijero QA` Desktop app wiring (QA address from `qa-address.local`, QA access key, QA data folder), renders it offscreen, and checks end to end that the QA service is reachable at its https address, that one fixed synthetic question gets an answer with at least one source card, and that the `Útil` feedback button is accepted. It prints one `PASS`/`FAIL` line per step and ends with one plain `Result:` line.
- Verification: offline tests only, with fake runner, fake probe, fake QA homes, fake address files, fake tokens in temporary folders (`MANIJERO_PILOT_TOKEN_FILE`), and a Ktor `MockEngine`; the commands are in Focused verification. The live run is the owner walkthrough.
- Notes: owner decisions (2026-11-07):
  1. The owner has no Android device. This feature covers only an automated Desktop end-to-end check against the QA service. Android real-device verification is out of scope (no emulator, no adb, no USB) and is recorded in `docs/progress/known-limitations.md`.
  2. One named owner command, ending with one plain-language `Result:` line, uses the QA Desktop app configured for the QA https address from `qa_server_deployment` and checks: service reachable, one synthetic test question answered with sources, and the feedback control works. Synthetic data only.
  3. No pilot token or QA key is read, printed, or logged by agents; tests are offline with fakes (fake tokens via `MANIJERO_PILOT_TOKEN_FILE` in temporary folders). Zero cost.
  4. Acceptance: validator accept plus the owner running the one command against live QA (owner walkthrough). The validator may return accept with the condition "pending owner walkthrough".
  5. The `feature_list.json` title no longer mentions a real Android device (updated at planning).
  6. QA key rule (2026-11-07): the QA key stays on `:shared:runDesktopQaCheck` as built, only because it stays on the owner's Mac; anything deployed or reachable online never contains secrets, enforced by offline guard tests (image build context, git ignore, qa-check log/result, Funnel target, desktop packaging via `PilotTokenGuardTest`).
  Planner decisions (appendix "Planner decisions"): command name `--qa-check`; reuse the `local_end_to_end_smoke` offscreen Desktop driver; the QA key reaches the check only as the same build-generated classpath resource the `run` task uses; an abstention fails (the owner asked for an answer with sources); exactly one `Útil` press per run.

## Goal

Give the owner one command that proves the QA Desktop app, wired exactly like `./scripts/init.sh --desktop-qa`, reaches the live QA service over https, shows a sourced answer to a made-up question, and gets its feedback rating accepted, with no clicking and no logs to read.

## Non-goals

- Android in any form: device, emulator, adb, USB, `--android-qa` runs, or instrumented tests.
- Deploying, updating, starting, or repairing QA (`--qa-*` behavior unchanged), Tailscale, Docker, or Ollama; QA alerts (`qa_service_alerts`); knowledge publishing (`qa_knowledge_deployment`).
- Judging answer correctness, latency, or legal coverage; proving the real window/AWT (the render is offscreen).
- Changing the answer service, `contracts/`, Spanish copy, layout, screenshot baselines, `--local-smoke` output, or the QA key format; new modules or dependencies.

## Job story

When QA is deployed, I want one command that tells me in plain words whether the QA Desktop app can reach it, get a sourced answer, and send a rating, so I know QA works end to end without a phone or a developer.

## Acceptance Scenarios

### 1. Everything passes
Given QA is deployed (`qa-address.local` holds its https address), the QA access key exists, Java and the wrapper are present · When the owner runs `./scripts/init.sh --qa-check` · Then it prints `Checking the QA service at <address>...`, `PASS  Service: QA answers at <address>.`, `Checking the QA Desktop app (the first run can take a few minutes)...`, `PASS  Answer: the QA app asked the test question and showed an answer with <n> source card(s).`, `PASS  Feedback: QA accepted the app's Útil rating.`, then `Result: the QA check passed: QA is reachable, answers with sources, and accepts feedback from the Desktop app.`, exit `0`.

### 2. A prerequisite is missing
Given any of: no dev environment; `qa-address.local` (or `MANIJERO_QA_ADDRESS_FILE`) missing, empty, the placeholder `https://qa.manijero.invalid`, or not an `https://` address; no QA access key file at `<QA home>/credentials/qa-test-device.token`; Java or the Gradle wrapper missing; another QA check running · When the command runs · Then before building anything it prints one plain line and `Result: the QA check did not run. <fix>`, exit `1`. Fixes: `Deploy QA with ./scripts/init.sh --qa-deploy, then run this command again.`; `Run ./scripts/init.sh --qa-settings-setup, then run this command again.`; the existing Java, wrapper, and "wait for it to finish" sentences from `local_smoke`.

### 3. QA is not reachable
Given `<address>/health` does not answer as the Manijero service · Then `FAIL  Service: QA does not answer at <address>.` and `Result: the QA check failed at the service step. Run ./scripts/init.sh --qa-status and do its first step, then run this command again.`, exit `1`; no Gradle build starts.

### 4. The app does not show a sourced answer
Given the app's `Conexión` probe fails, a saved QA `Conexión` address differs from `<address>`, or after the question the app shows an abstention, an answer without source cards, a land clarification, a service error, an unreachable failure (after the one allowed `Reintentar`), or nothing within 90 s · Then `FAIL  Answer: <what the app showed, in plain words>` naming one step (a saved address: open `Ayuda > Herramientas de prueba > Conexión` in `./scripts/init.sh --desktop-qa` and press `Usar la dirección predeterminada`; otherwise run `--qa-status` and do its first step, or send `build/qa-check/desktop.log` to a developer), and `Result: the QA check failed at the answer step. Do the first step shown above.`, exit `1`.

### 5. Feedback is not accepted
Given a finished reply (answer or abstention) was shown · When the driver presses `Útil` once · Then the feedback outcome is `sent` (thanks line within 30 s), `failed` (the failure line), `not_on_qa` (the failure line after HTTP 404 from `/feedback`: QA runs an older version, so the line says to run `--container-build`, `--qa-update`, then `--qa-check`), `no_reply` (neither within 30 s), or `not_shown` (no rating buttons). Any outcome but `sent` prints `FAIL  Feedback: ...` with one step; the result names the first failing step (answer before feedback), exit `1`. With no finished reply, no feedback line is printed.

### 6. The check cannot run
Given Gradle exits non-zero, times out (15 min), or leaves no well-formed result line · Then `FAIL  Answer: the check could not run. Details are in build/qa-check/desktop.log; send that file to a developer.` and the failed result, exit `1`. No Gradle output or traceback reaches the terminal. A well-formed `not_qa_build` or `no_access_key` line gets its own plain line instead (`... was not built as the QA app, so no question was asked. Send build/qa-check/desktop.log to a developer.`; `... the QA access key did not reach the check app, so no question was asked. Run ./scripts/init.sh --qa-settings-setup, then run this command again.`) and the same failed result.

### 7. Misuse and interruption
An extra argument prints one sentence, exit `2`. Ctrl+C ends the child and prints `The QA check was stopped.` and `Result: the QA check was stopped before it finished.`, exit `1`.

### 8. Safety and privacy
Given any run: the question is the existing fixed synthetic `LOCAL_SMOKE_QUESTION`, sent as `general` with no lands and no retention; exactly one `useful` rating is sent; the driver opens no land store and reads the QA `Conexión` store read-only; output, result file, and log carry only outcome codes, source count, address source, and the address, never question, answer, passage, or key text; the Python side only tests that the key file exists and never opens it; the key reaches the check only as the build-generated classpath resource (never a JVM property, environment entry, argument, or log); writes stay under `build/qa-check/` and the existing build-output folders.

## Technical approach

- **Command.** `scripts/init.sh` adds an early `--qa-check` block beside `--local-smoke` (same misuse, no-dev-env pair, `manijero_resolve_java || true`), then `exec backend/.venv/bin/python backend/scripts/qa_check.py`. `usage` and `--check` list it.
- **Orchestrator.** New stdlib-only `backend/app/qa_check.py` (operator-only, never imported by the service): lock `build/qa-check/.lock`; read the address (`qa_deployment.ADDRESS_FILE_ENV`, default `<repo>/qa-address.local`); check the key path via `environment_profiles.credential_paths(qa_home(), QA_CLIENT_ID)` with `is_file()` only; probe with `qa_deployment.system_public_probe`; reuse `local_smoke` `Runner`/`SubprocessRunner`, `SystemTools.java_available`, the lock helper, and the Java/wrapper messages (refactor for reuse with unchanged `--local-smoke` output). Then run `./gradlew --console=plain --quiet -PmanijeroEnvironment=qa :shared:runDesktopQaCheck -PmanijeroSmokeExpected=<address> -PmanijeroSmokeResult=<file>` (15 min, log `build/qa-check/desktop.log`), parse the one result line, and map it to the fixed lines.
- **Gradle.** `shared/build.gradle.kts` registers `runDesktopQaCheck` like `runDesktopLocalSmoke` (jvmTest classes, headless, never up to date, same two `-P` mappings, filter on `DesktopQaCheckRun`); it `dependsOn` `:desktopApp:generateEnvironmentResource` and `:desktopApp:generatePilotTokenResource` and appends `desktopApp/build/generated/environment` and `.../generated/pilotToken` to its classpath when the task is configured (`classpath = jvmTest classpath + files(...)`; a `doFirst` append never reaches the forked test JVM, the 2026-11-07 walkthrough defect). A Gradle-level wiring test runs the task against a fake QA key and a closed loopback address. `jvmTest` excludes `DesktopQaCheckRun`.
- **Driver.** New jvmTest `smoke/DesktopQaCheckRun.kt` (self-skips without the result property): `desktopEnvironment()` must be QA (else `not_qa_build`), `desktopPilotToken()` must be present (else `no_access_key`); wire `ActiveServiceAddress(env.defaultAskBaseUrl(), ReadOnly(FileServiceAddressStore(desktopConnectionStorePath(folder = env.dataFolder))))`, `KtorAnswerService(client, address::current, pilotToken = token, acceptInspection = true)` as `main.kt`'s test-build branch does; run `SmokeUiScript.preflight`/`ask`, then a new `SmokeUiScript.rateUseful(test)` in the same compose session. Result line: `MANIJERO_QA_CHECK_RESULT outcome=<smoke code|not_qa_build|no_access_key> sources=<n> feedback=<sent|failed|no_reply|not_shown|not_tried> address=<default|saved> url=<address>`, built by a jvmTest `smoke/QaCheckProtocol.kt`.
- **Tag.** `ChatTestTags.FEEDBACK_FAILED` on the existing feedback failure line in `AnswerFeedback.kt`; tag only ([client-chat](../constraints/client-chat.md)).

## Expected file changes

- Create: `backend/app/qa_check.py`, `backend/scripts/qa_check.py`, `backend/tests/test_qa_check.py`, `backend/tests/test_qa_check_commands.py`, `backend/tests/test_qa_check_gradle_wiring.py`, `shared/src/jvmTest/.../smoke/DesktopQaCheckRun.kt`, `smoke/QaCheckProtocol.kt`, `smoke/DesktopQaCheckDriverTest.kt`, `platform/QaCheckGuardTest.kt`.
- Modify: `scripts/init.sh`, `backend/app/local_smoke.py` (reuse only, output unchanged), `shared/build.gradle.kts`, `shared/src/jvmTest/.../smoke/SmokeUiScript.kt` (`rateUseful`), `shared/src/commonMain/.../chat/ChatTestTags.kt`, `chat/AnswerFeedback.kt` (tag only), `platform/LocalSmokeGuardTest.kt` (only if its jvmTest-exclusion assertion must admit the second live class).
- Not changed: `desktopApp/build.gradle.kts`, `main.kt`, androidApp, backend service modules, `qa_deployment.py` behavior, `contracts/`, `knowledge/`, strings, screenshot goldens.

## Visual design impact

UI involved: no visible change. One invisible test tag; chat screenshot baselines must pass unchanged.

## Durable documentation impact (required)

- `docs/constraints/hosting-and-pilot.md`: update the Desktop token rule: only the Desktop `run` task and the test-only `:shared:runDesktopQaCheck` may carry the generated token resource. Reason: this spec.
- `docs/constraints/operations.md`: update the smoke/check MUST: a check against QA sends only the fixed synthetic question and at most one `useful` rating per run. Reason: this spec.
- `ARCHITECTURE.md`: update the local smoke harness bullet with one sentence on the QA Desktop check.
- `docs/owner-guide.md`: update (at most ~40 lines): "Check the QA Desktop app" (command, `Result:` lines, table of reachable failure lines), "Owner walkthrough: QA check", and replace step 4 of "Owner walkthrough: QA" (Android) with `--qa-check`.
- `backend/README.md`: update (at most ~20 lines): QA check order, result line, codes, log, timeouts.
- `docs/progress/known-limitations.md`, `docs/risks-and-open-questions.md`, `PROGRESS.md`: update at acceptance: no Android device or emulator check against QA (owner has no device, 2026-11-07); `--android-qa` never ran on a device; the Desktop check is offscreen; each run adds one `useful` to QA's per-process feedback count; the first question may need the one retry.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

Offline: no QA, Tailscale, Docker, Ollama, network, or real key; temporary QA homes, address files, and fake `MANIJERO_PILOT_TOKEN_FILE` only.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_qa_check.py tests/test_qa_check_commands.py tests/test_local_smoke.py tests/test_container_image_files.py tests/test_qa_deployment.py -q
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.smoke.*' --tests 'com.jamarglex.manijero.platform.*' --tests 'com.jamarglex.manijero.chat.*'
./gradlew --quiet :shared:runDesktopQaCheck --dry-run
MANIJERO_GRADLE_WIRING_TEST=1 MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_qa_check_gradle_wiring.py -q
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeScreenshotsTest'
```
<!-- verify:end -->

The owner walkthrough (live QA, real key) is the manual acceptance check; the orchestrator records it.

## Appendix

See [`qa_real_device_check.appendix.md`](qa_real_device_check.appendix.md) for research, planner decisions, plan, evidence, and the validator checklist.
