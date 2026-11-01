# Smoke-test Android and Desktop against the running local RAG service end to end

## Source metadata

- `id`: local_end_to_end_smoke · `area`: testing · `depends_on`: local_full_rag_stack, local_service_connection (both accepted) · `status` at planning: not_started
- User-visible behavior: with the local answer service running, the owner runs `./scripts/init.sh --local-smoke`. The command asks one fixed question through the Desktop app and through the app on the running Android emulator. For each platform it prints one plain `PASS` or `FAIL` line, then one final `Result:` line. A missing prerequisite produces one plain line that names the fix.
- Verification: offline tests with fake runner, adb, Gradle, and service ports; `init.sh` subprocess runs that never reach Gradle or adb; shared Compose tests of the Desktop driver against a Ktor `MockEngine`; compile-only for the Android driver. The commands are in Focused verification. The real run is the owner walkthrough in `docs/owner-guide.md`.
- Notes: owner decisions recorded 2026-11-01:
  1. The smoke test is automated. One named `init.sh` command runs it and prints a plain-language pass or fail line for Desktop and one for the Android emulator, then a final `Result:` line (see [`docs/constraints/operations.md`](../constraints/operations.md)). The owner only watches the result.
  2. It runs against the real local RAG service from `local_full_rag_stack` (`--local-rag-start` / `--local-rag-service-status` / `--local-rag-stop`). It reuses the app connection settings from `local_service_connection`. Each prerequisite gap (setup not done, Ollama closed, service not running, no emulator) is reported as one plain line naming the fix, never as a stack trace.
  3. Automated verification of the smoke command itself uses fakes. It never needs a running service, Ollama, a model, an emulator, or a device. The real run is the owner walkthrough in `docs/owner-guide.md`.
  4. No answer-quality or legal-coverage claim. The smoke test proves that the apps reach the service and render either a grounded answer or an honest abstention. It does not prove that answers are correct.
  5. (2026-11-01, after the owner walkthrough hit macOS's "Unable to locate a Java Runtime") The scripts find Java on their own. One shared resolution in `scripts/java-env.sh`, sourced by `scripts/init.sh` for every path that runs `./gradlew` or `java`, tries in order: a working `JAVA_HOME`; `/usr/libexec/java_home -v 21`; a `java` on `PATH` that runs (`java -version` succeeds, so Apple's placeholder is rejected); the newest JDK 21 under `~/.gradle/jdks`, chosen by version. Both a system-wide Temurin 21 and a Gradle-downloaded JDK must work. When none is found, one line names the fix (install Temurin 21 from https://adoptium.net) and a `Result:` line follows. `local_smoke.py` accepts only the resolved `JAVA_HOME`, so it always agrees with `init.sh`.
  The command name, the offscreen Desktop driver, the instrumented Android driver, and the test tags are planner choices; see the appendix, "Planner decisions".

## Goal

Give the owner one command that proves both test apps reach the real local answer service and show its reply the way a person would see it. The command needs no developer, no clicking through the apps, and no reading of logs.

## Non-goals

- Starting, stopping, or repairing the service, Ollama, the emulator, or any local artifact. Changing `--local-rag-*`, `--mock*`, `--android-run`, or `--desktop` behavior.
- Judging answer correctness, legal coverage, latency, or load (`local_load_test`), or whether hybrid ranking or a model draft was used.
- Physical devices, LAN or QA addresses (`qa_real_device_check`), pilot tokens (`client_pilot_credentials`), release or packaged builds, and iOS.
- Sending land data. Reading or writing the owner's lands, or changing a saved `Conexión` address.
- Changing the answer service, `contracts/`, Spanish copy, layout, or any screenshot baseline.

## Job story

When I have started the local answer service, I want one command that tells me in plain words whether the Desktop app and the emulator app can ask it a question and show its reply, so I know the whole chain works before I try the apps or show them to someone.

## Acceptance Scenarios

### 1. Both platforms pass

Given the service started by `--local-rag-start` is running with its three status checks `OK` and an Android emulator has finished booting · When the owner runs `./scripts/init.sh --local-smoke` · Then the command prints `Checking the local answer service...`, `Checking the Desktop app (the first run can take a few minutes)...`, and `Checking the Android emulator app (the first run can take a few minutes)...` in turn. Each platform renders the shared app with that platform's test-build address. On each platform the command types the fixed question, presses `Preguntar`, and sees either an `answered` reply with at least one source card or an `abstained` reply (`Sin respuesta segura`). It prints `PASS  Desktop: ...` and `PASS  Android emulator: ...`, each saying which of the two it saw, then `Result: the smoke test passed on Desktop and the Android emulator.`, exit `0`.

### 2. A service prerequisite is missing

Given any of these conditions:

- no dev environment or no `settings.env` (setup not done),
- no running service started by `--local-rag-start` (including a stale record, which is cleared with the `local_full_rag_stack` stale line),
- any service-status check is not `OK` (for example Ollama closed, a newer release published, or `/ready` unavailable),
- Java or the Gradle wrapper is missing,
- another smoke test is running.

When the command runs · Then it prints exactly one plain line naming the fix. For the status checks, that line is the first non-`OK` status line itself. The other fixes are `Run ./scripts/init.sh --local-rag-setup.`, `Start it with ./scripts/init.sh --local-rag-start, then run this command again.`, a Java install sentence, or `wait for it to finish`. Then it prints `Result: the smoke test did not run. <fix>`, exit `1`. It builds nothing, installs nothing, and starts no app.

### 3. No emulator

Given the service is ready but adb is not found, no emulator is listed, or the emulator is still booting · When the command runs · Then the Desktop check still runs. The Android line is `FAIL  Android emulator: ...` and names one fix: install SDK Platform-Tools; start an emulator with `./scripts/init.sh --android-run` or Android Studio's Device Manager; or wait for the home screen. In each case it ends `then run this command again.` Physical devices are never used, and nothing is installed anywhere. The result is `Result: the smoke test failed on the Android emulator. Do the first step shown above.`, exit `1`.

### 4. The app uses a different address

Given a platform's address in use differs from that platform's service address: Desktop expects `http://127.0.0.1:<port>`, the emulator expects `http://10.0.2.2:<port>`, where `<port>` comes from the run record. This happens with a saved `Conexión` address or a non-default build address · When that platform is checked · Then it sends no request. Its `FAIL` line names the address in use and the fix:

- when the build default equals the expected address: `open Ayuda > Herramientas de prueba > Conexión, press Usar la dirección predeterminada`;
- otherwise: `enter <expected> and press Comprobar`.

Either way the line ends `then run this command again.`

### 5. The app reaches the service but does not show a passing reply

Given the `Conexión` probe on the address in use returns `NotReady`, `ReadyUnknown`, `Unreachable`, or `NotManijero`; or, after the question, the app shows a failure, an answer with no source card, a land clarification, or nothing within 90 seconds · When that platform is checked · Then its line starts `FAIL` and says what the app showed in plain words. It names one step: run `--local-rag-service-status` and do its first step, or send the named log file to a developer. Exactly one `Reintentar` press is allowed after an unreachable failure, because the first question after start can exceed the app's 15 s request bound while Ollama loads the model. The result names the failing platforms, exit `1`.

### 6. A build, install, or run step fails

Given Gradle, install, or instrumentation exits non-zero, times out, or reports no well-formed result · Then that platform's line is `FAIL  <platform>: the check could not run. Details are in build/local-smoke/<platform>.log; send that file to a developer.` No traceback or Gradle output reaches the terminal.

### 7. Misuse and interruption

Given an extra argument after `--local-smoke` · Then one sentence, nothing changes, exit `2`. Given Ctrl+C · Then the running child step is ended and the command prints `The smoke test was stopped.` and `Result: the smoke test was stopped before it finished.`, exit `1`.

### 8. Safety and privacy

Given any run, these hold:

- The question is one fixed, in-scope, non-personal constant. It is sent with `land_context.mode = general` and no lands, and without retention permission.
- The Desktop driver never opens the land store.
- Each driver wraps the address store read-only, so it never saves or clears an address.
- Output lines, result files, and logs carry no question, answer, or passage text. They contain only the outcome code, the source count, and the address in use.
- Network use is loopback only: the service and the emulator host alias.
- The only writes are under `<repo>/build/local-smoke/`, plus, on the emulator, installing the debug app and its test APK over the existing app with data kept, and granting `ACCESS_LOCAL_NETWORK` on API 37+.

## Technical approach

- **Command.** `scripts/init.sh` adds `--local-smoke` to the early dispatch, next to `--local-rag-*`. It has the same misuse check and dev-environment link, and the same "not set up yet" pair when no dev environment exists. It exports `ANDROID_HOME`/`ANDROID_SDK_ROOT` (default `~/Library/Android/sdk`), so it never creates `local.properties`. Then it runs `backend/.venv/bin/python backend/scripts/local_rag.py smoke`. `local_rag.py` gains the `smoke` choice with the same one-sentence-plus-log handling. `usage` and `--check` list the command.
- **Orchestrator.** A new operator-only, stdlib-only module, `backend/app/local_smoke.py`, uses injected ports (`Runner` for subprocesses with timeout, log, and Ctrl+C termination; `Tools` for `java` and the adb path; `ServicePorts` from `local_rag_service`; a lock). It runs these steps in order:
  1. Take the lock `build/local-smoke/.lock`.
  2. Run the service check: `find_running`, then the public `service_checks(...)` that is extracted from `report_running` with unchanged output.
  3. Check Java and the wrapper.
  4. Desktop: `./gradlew --console=plain --quiet :shared:runDesktopLocalSmoke -PmanijeroSmokeExpected=<url> -PmanijeroSmokeResult=<file>`, bounded at 15 min and logged to `build/local-smoke/desktop.log`.
  5. Android: find the first `emulator-*` serial in state `device` with `sys.boot_completed=1`. Run `ANDROID_SERIAL=<serial> ./gradlew :androidApp:installDebug :androidApp:installDebugAndroidTest` (15 min), then `adb -s <serial> shell am instrument -w -r -e class com.jamarglex.manijero.smoke.AndroidLocalSmokeTest -e expectedAddress <url> com.jamarglex.manijero.test/androidx.test.runner.AndroidJUnitRunner` (5 min). Log to `android.log`. Never use `connectedAndroidTest`, because it uninstalls the app and its data.
  6. Map each result to the fixed English lines.
- **Result protocol.** Each driver reports one line, `MANIJERO_SMOKE_RESULT outcome=<code> sources=<n> address=<default|saved> url=<address in use>`. Desktop writes it to the result file. Android sends it as the instrumentation status key `manijero_smoke_result`. The codes are `answered`, `abstained`, `answered_without_sources`, `land_clarification`, `unreachable`, `service_error`, `not_ready`, `ready_unknown`, `not_manijero`, `other_address`, `no_answer`, and `error`. Only `answered` and `abstained` pass. A missing or malformed line follows scenario 6.
- **Shared smoke protocol.** It lives in commonMain `connection/LocalSmoke.kt` (test-build tooling next to `Conexión`, pure, no UI-test types). It holds `LOCAL_SMOKE_QUESTION`, `SmokeOutcome` with its codes, `smokeAddressOutcome(address, expected)`, `smokeOutcomeFor(ServiceCheckResult)`, and `smokeResultLine(...)`.
- **Test tags.** A new `chat/ChatTestTags.kt` defines the tags. `Modifier.testTag` is added, with no other change, on the question field, `Preguntar`, the answered block, the abstention card, each source card, the land-clarification chooser, each failure notice (unreachable or service), and `Reintentar`. Tags are invisible to people and to screen readers, and the pixels do not change.
- **Desktop driver.** This is shared jvmTest `smoke/` code. `SmokeUiScript` runs over `ComposeUiTest`:
  1. Resolve `ActiveServiceAddress(desktopAskBaseUrl(), ReadOnly(FileServiceAddressStore(desktopConnectionStorePath())))`.
  2. Run the address check, then the `KtorServiceStatusChecker` probe.
  3. Call `App(landRepository = null, KtorAnswerService(client, address::current), connectionTools = tools)` with the real CIO `answerHttpClient`.
  4. Type the question, press ask, wait up to 90 s for a terminal tag, retry once on unreachable, then classify.

  `DesktopLocalSmokeRun` is the live entry. It is excluded from `:shared:jvmTest` and self-skips when the result property is absent. `runDesktopLocalSmoke` is a `Test` task that reuses jvmTest classes, is headless, is never up to date, and maps the two `-P` values to system properties. `desktopConnectionStorePath()` moves to shared jvmMain, and `main.kt` uses it, so both read the same `~/.manijero/connection-v1.txt`.
- **Android driver.** `androidApp/src/androidTest/.../smoke/AndroidLocalSmokeTest.kt` runs in the debug app's process with `createComposeRule()`. It reuses `testBuildConnectionTools(context, androidAskBaseUrl(BuildConfig.ASK_BASE_URL), client)` with a read-only store wrapper and the same script steps. It grants `ACCESS_LOCAL_NETWORK` through `uiAutomation` on API 37+. It reports through `sendStatus` and asserts a passing code.
- **Boundaries.** The work follows [ARCHITECTURE.md](../../ARCHITECTURE.md) "Answer service boundary" and the [ui-shell](../constraints/ui-shell.md) test-build gating, and the release source set stays untouched. New test-only dependencies are `androidx.test:runner` (a catalog entry, `androidx-test` 1.7.0) and the existing `ktor-client-cio` for jvmTest. Existing catalog entries cover `androidTestImplementation` of ui-test-junit4 and ext-junit, and `debugImplementation` of ui-test-manifest.

## Expected file changes

- `scripts/init.sh` — modify: dispatch, `usage`, `--check` listing.
- `backend/app/local_smoke.py`, `backend/tests/test_local_smoke.py` — create. `local_smoke.py`'s Java check accepts only the `JAVA_HOME` resolved by `scripts/java-env.sh` (its `bin/java -version` must run).
- `scripts/java-env.sh`, `backend/tests/test_java_resolution.py` — create: the one shared Java resolution sourced by `scripts/init.sh` (owner decision 5), and its offline tests.
- `backend/scripts/local_rag.py` — modify: add `smoke`.
- `backend/app/local_rag_service.py` — modify: extract `service_checks`, with no output change.
- `backend/tests/test_local_rag_commands.py` — modify: `--local-smoke` subprocess cases.
- `shared/src/commonMain/.../chat/ChatTestTags.kt` and `connection/LocalSmoke.kt` — create.
- `chat/ChatHomeScreen.kt`, `ChatTranscript.kt`, `ChatStates.kt`, `SourceCards.kt`, `ClarificationChooser.kt` — modify: tags only.
- `shared/src/commonTest/.../connection/LocalSmokeTest.kt` — create.
- `shared/src/jvmMain/.../connection/DesktopTestBuild.kt` — modify: add `desktopConnectionStorePath()`.
- `desktopApp/src/main/.../main.kt` — modify: use it.
- `shared/src/jvmTest/.../smoke/SmokeUiScript.kt`, `DesktopSmokeDriverTest.kt`, `DesktopLocalSmokeRun.kt`, and `platform/LocalSmokeGuardTest.kt` — create.
- `shared/build.gradle.kts` — modify: jvmTest exclusion, `runDesktopLocalSmoke`, jvmTest `ktor-client-cio`.
- `androidApp/build.gradle.kts` — modify: `testInstrumentationRunner`, test dependencies, the androidTest-only `espresso-core` pin, and the offline `verifyAndroidTestDependencies` task (fails when the resolved `espresso-core` is older than 3.6.1, which crashes on API 34+).
- `gradle/libs.versions.toml` — modify: `androidx-test-runner`, `androidx-test-espresso-core` (3.7.0).
- `androidApp/src/androidTest/kotlin/com/jamarglex/manijero/smoke/AndroidLocalSmokeTest.kt` — create.
- Not changed: `androidApp/src/release/**`, `MainActivity.kt`, every backend service module, `contracts/`, `knowledge/`, `strings.xml`, and screenshot goldens.

## Visual design impact

UI involved: no visible change. Only invisible `testTag`s are added, and the existing chat screenshot baselines must pass unchanged.

## Durable documentation impact (required)

- `docs/owner-guide.md`: update. Add a section "Smoke-test the apps against the local answer service". It gets numbered copy-paste steps, the expected `Result:` line, and an "if you see something else" table with one row per scenario 2–6 fix. Add "Owner walkthrough: local smoke test" with the appendix steps, including service stopped (missing prerequisite) and start-then-rerun (recovery).
- `backend/README.md`: update. Add a "Local smoke test" subsection covering the orchestrator order, the result protocol and codes, logs, timeouts, and the no-`connectedAndroidTest` reason.
- `ARCHITECTURE.md`: update with one bullet. The local smoke harness consists of the operator-only `local_smoke.py`, the test-only drivers (shared jvmTest and androidApp androidTest) over the commonMain smoke protocol, and `ChatTestTags`. The service and release wiring are unchanged.
- `docs/constraints/operations.md`: update with one MUST. A smoke or check command that drives the apps is read-only for the owner's data: no land store, no saved-address change, no uninstall. It reports only outcome codes, never question or answer text. Reason: `local_end_to_end_smoke`.
- `docs/constraints/client-chat.md`: update with one MUST NOT. `ChatTestTags` never change semantics, copy, or layout, and no product logic reads them.
- `docs/risks-and-open-questions.md`: update. A pass proves reachability and rendering only. The first question after start may need the one retry. The Desktop check renders offscreen, so it does not prove the window or AWT. The emulator is not a real device.
- `PROGRESS.md` "Start and verify" and `docs/progress/known-limitations.md`: update one line each at acceptance.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed. The workflow, terms, design, and wire contract do not change.

## Focused verification (required)

This block runs offline: no service, Ollama, model, emulator, device, or network. Subprocess tests use a temporary `MANIJERO_LOCAL_HOME`, an empty `MANIJERO_VENV_ROOT`, and a free `MANIJERO_LOCAL_RAG_PORT`.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
bash -n scripts/java-env.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_smoke.py tests/test_local_rag_commands.py tests/test_local_rag_service.py tests/test_java_resolution.py -q
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.smoke.*' --tests 'com.jamarglex.manijero.connection.*' --tests 'com.jamarglex.manijero.chat.*' --tests 'com.jamarglex.manijero.platform.*'
./gradlew --quiet :androidApp:compileDebugAndroidTestKotlin :androidApp:compileReleaseKotlin :desktopApp:compileKotlin
./gradlew --quiet :androidApp:verifyAndroidTestDependencies :androidApp:assembleDebugAndroidTest
./gradlew --quiet :shared:runDesktopLocalSmoke --dry-run
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeScreenshotsTest'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeAndroidScreenshotsTest'
```
<!-- verify:end -->

The owner runs the walkthrough against the real service, Ollama, and emulator, and the orchestrator records it. It is not part of this block.

## Appendix

See [`local_end_to_end_smoke.appendix.md`](local_end_to_end_smoke.appendix.md) for research, plan, evidence, and the validator checklist.
