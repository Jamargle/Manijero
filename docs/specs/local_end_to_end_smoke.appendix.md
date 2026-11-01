# local_end_to_end_smoke — appendix

## Repository research

### Files inspected

- `docs/specs/local_full_rag_stack.md`: the run record holds the port, and `find_running` handles stale records. Status has three checks (Answers, Search, Drafting), and each non-`OK` line names its fix. The service binds loopback only. The app addresses are `127.0.0.1:<port>` and `10.0.2.2:<port>`. The first question may exceed the draft budget while Ollama loads.
- `docs/specs/local_service_connection.md`: covers `ActiveServiceAddress`, `ServiceAddressSource`, `KtorServiceStatusChecker` outcomes, and debug-variant and Desktop `run`-only gating. No owner command was added.
- `backend/app/local_rag_service.py`: `find_running`, `report_running` (prints the checks inline, so a quiet `service_checks` must be extracted), `service_url`, `MSG_STALE`, `NOT_RUNNING`, and the `ServicePorts` and real port classes.
- `backend/scripts/local_rag.py`: argparse choices, `_run_service_command` exception wording, and `RunLog` traceback handling, all reused for `smoke`.
- `backend/tests/test_local_rag_commands.py`: the subprocess pattern (temporary home, empty venv root, free port, skip without `backend/.venv`).
- `scripts/init.sh`: the early `--local-rag-*` dispatch, which runs before the `local.properties` write, the Java check, and the SDK export. `run_android_on_emulator` shows the adb path, emulator serial selection, and boot wait. The mock section supplies the output style.
- `androidApp/src/main/.../MainActivity.kt`: wiring through `answerHttpClient(Android)` and `testBuildConnectionTools`, plus a runtime `ACCESS_LOCAL_NETWORK` request on API 37+.
- `androidApp/src/debug/.../TestBuildTools.kt`: the debug-only tools. The androidTest source of the debug variant can call them.
- `androidApp/build.gradle.kts`: no `testInstrumentationRunner` and no androidTest dependencies. `ASK_BASE_URL` comes from the Gradle property `manijeroAskBaseUrl`.
- `desktopApp/src/main/.../main.kt`: the private `~/.manijero/connection-v1.txt` path, test-build tools only under `desktopTestBuildEnabled()`, and lands from `FileLandStorage`.
- `desktopApp/build.gradle.kts`: the `run`-only `manijero.testBuild`, which `TestBuildGatingGuardTest` guards (the property may appear exactly once).
- `shared/build.gradle.kts`: jvmTest dependencies include ui-test-junit4-desktop and the Ktor server but no client engine. `verifyDesktopScreenshots` is the pattern for a dedicated `Test` task. The jvmTest exclusion filter and the `prepareMockAnswerServer` classpath pattern were also read.
- `gradle/libs.versions.toml`: has `androidx-test`, `androidx-test-junit`, ui-test-junit4/manifest, and `ktor-client-cio`. It has no `androidx.test:runner` entry.
- `shared/src/commonMain/.../chat/AnswerService.kt`: request timeout 15 s, `KtorAnswerService(client, () -> String)`, statuses `answered`, `abstained`, and `needs_land_clarification`.
- `chat/ChatTranscript.kt`, `ChatStates.kt`: show where the answered block, abstention card, source section, and failure notice with `Reintentar` render. There are no test tags today.
- `connection/ServiceAddress.kt`, `ServiceStatusChecker.kt`, `ConnectionTools.kt`: the address resolution, the store interface (save and clear can throw), and the five check results.
- `shared/src/jvmTest/.../chat/ChatHomeInteractionTest.kt`: the `runDesktopComposeUiTest` interaction pattern.
- `docs/constraints/operations.md`: the owner-operability MUSTs.
- `docs/owner-guide.md` headings: existing local-service sections and the walkthrough format.
- Not inspected: `ClarificationChooser.kt` and `SourceCards.kt` bodies beyond the string references; `ChatConversation` internals; the AGP `installDebug` reinstall flags (taken as "keeps data", to be confirmed in evidence); and Compose `waitUntil` behavior with real network I/O on Android.

### Existing patterns to follow

- Owner output uses fixed English sentences, progress lines, and one `Result:` line, with exits `0`/`1`/`2`. Tracebacks go to a printed log only.
- Operator modules are stdlib-only, with injected ports and fakes in pytest, and never import into the service.
- Test-only Gradle entry points are explicit tasks outside the ordinary tiers, so they never run in `--fast` or `--verify`.
- Test-build-only behavior lives in commonMain `connection/`, reachable only through host injection.

### Planner decisions (not owner decisions; the owner may rename before implementation)

- The command is named `--local-smoke`: it is short, and it tests the apps rather than the RAG tools. It uses the early dispatch so tests never write `local.properties`, and AGP reads `ANDROID_HOME` instead.
- The Desktop driver renders the shared `App` offscreen through `runDesktopComposeUiTest`. It uses the same address resolution, store file, client factory, and checker as `--desktop`. No window opens, so the check does not prove windowing.
- The Android driver is an instrumented Compose test in the debug app's process. It is installed with `installDebug` and `installDebugAndroidTest` and run with `am instrument`. It does not use `connectedAndroidTest`, which uninstalls the app and wipes the owner's emulator data.
- The drivers read `testTag`s instead of Spanish copy, so copy edits never break the smoke test, and the generated `Res` stays internal.
- The fixed question is `¿Qué es la solicitud única de la PAC?`. It is in scope, contains no personal data, and has no land context. Either `answered` with sources or `abstained` passes.
- There is exactly one `Reintentar` press after `unreachable`: it covers the first-question model load and nothing more.
- No emulator is booted automatically, per owner decision 2. Physical devices are ignored: they cannot reach a loopback service.
- Pass and fail lines use the labels "Desktop" and "Android emulator". Timeouts are 15 min per build and install (first runs), 5 min for instrumentation, and 90 s for the reply inside each driver.

### Current gaps

- Compose UI tests with real network I/O (`waitUntil` on wall time) are untested here on both platforms. Risk: idling or clock behavior may need `mainClock.autoAdvance` or polling. The implementer confirms this with `DesktopSmokeDriverTest` (MockEngine) and the walkthrough.
- First-run Gradle may fetch Maven dependencies (free). This is the same as for `--desktop` and `--android-run`.

## Implementation plan

1. Add `chat/ChatTestTags.kt` and the `Modifier.testTag` calls (tags only). Run the chat screenshot verify tasks.
2. Add commonMain `connection/LocalSmoke.kt` (question, `SmokeOutcome` codes, address/check mapping, result line) and `LocalSmokeTest`.
3. Add `desktopConnectionStorePath()` to shared jvmMain and use it in `main.kt`.
4. Add jvmTest `smoke/SmokeUiScript.kt` (read-only store wrapper, address check, probe, ask, wait, one retry, classify), plus `DesktopSmokeDriverTest`.
5. Add `DesktopLocalSmokeRun` (it self-skips without the property and writes the result file atomically). In `shared/build.gradle.kts`, add the exclusion, the `runDesktopLocalSmoke` task, and jvmTest `ktor-client-cio`. Add `LocalSmokeGuardTest`.
6. Add the catalog `androidx-test-runner`. In `androidApp/build.gradle.kts`, add the runner and the `androidTestImplementation`/`debugImplementation` test dependencies.
7. Add `AndroidLocalSmokeTest` (debug tools with a read-only store, permission grant, script, `sendStatus`, assert pass). Run the compile.
8. Extract `service_checks` in `local_rag_service.py`, keeping output byte-identical (existing tests stay green).
9. Add `backend/app/local_smoke.py` (ports, lock, prerequisite order, Desktop and Android steps, protocol parser, line wording, result) and `test_local_smoke.py`.
10. Add the `smoke` choice to `local_rag.py`. In `init.sh`, add the dispatch, usage, and `--check` listing. Extend `test_local_rag_commands.py`.
11. Update the docs listed in the contract (owner guide sections and walkthrough, `backend/README.md`, `ARCHITECTURE.md`, `operations.md`, `client-chat.md`, risks).
12. Run the focused block, then `./scripts/init.sh --fast`, and record one-line results below.
13. Hand the walkthrough to the orchestrator for the owner, and record the results below.

## Verification plan

### Automated (focused block)

- `test_local_smoke.py` (fakes only):
  - All prerequisites OK, with both drivers reporting `answered` or `abstained`: two PASS lines and a pass result, exit `0`.
  - No settings, not running, a stale record (cleared line), each non-`OK` check (Ollama closed, newer release, `/ready` unavailable), no Java, and a lock held: one line plus `did not run`, exit `1`, and the runner is never called.
  - No adb, no emulator, an emulator still booting, and only a physical device: Desktop runs, Android FAIL with its fix, and no install argv.
  - `ANDROID_SERIAL` set on the install argv, and `am instrument` argv has no `connectedAndroidTest`.
  - Each outcome code maps to its line, `other_address` with default equal or not equal to expected selects the right fix, and a malformed, missing, or extra-field result follows scenario 6.
  - A Gradle non-zero exit or timeout follows scenario 6. Ctrl+C ends the child and prints the stop lines.
  - No output line, log line written by the orchestrator, or result line contains the question text.
- `test_local_rag_commands.py`:
  - `--local-smoke extra` gives exit `2`.
  - Before setup, it prints the not-set-up pair.
  - With no service running, it prints the not-running line plus `did not run`, exit `1`.
  - No `local.properties` is created by any of these, and no Gradle or adb is called.
- `test_local_rag_service.py` is unchanged and stays green (the `service_checks` extraction keeps output identical).
- `LocalSmokeTest` (commonTest): codes are unique and stable, `smokeAddressOutcome` covers saved and default, normalized, and port differences, each `ServiceCheckResult` mapping holds, and the result line carries no question.
- `DesktopSmokeDriverTest` (jvmTest, MockEngine with contract-example bodies):
  - `answered` with sources, `answered` with no sources, `abstained`, 503 `/ready`, unreachable then answered after one retry, unreachable twice, a `/ask` 500 (`service_error`), and no reply before the bound (short test bound gives `no_answer`);
  - the saved address differing from expected gives `other_address` with zero requests;
  - the store wrapper's save and clear are never called;
  - the `/ask` body has `general` mode, no lands, and no retention key.
- `LocalSmokeGuardTest`: the jvmTest filter excludes `DesktopLocalSmokeRun`, and `runDesktopLocalSmoke` is not in any `init.sh` tier. The release source set is unchanged, and `TestBuildGatingGuardTest` still passes. No product source reads `ChatTestTags` outside `Modifier.testTag`.
- Compiles: `compileDebugAndroidTestKotlin`, `compileReleaseKotlin`, and `desktopApp:compileKotlin`. `runDesktopLocalSmoke --dry-run` resolves the task. The chat screenshot verifies pass unchanged.

### Owner walkthrough (manual acceptance, real service and emulator)

1. `./scripts/init.sh --local-rag-start`. Expected: `Result: the local answer service started at http://127.0.0.1:8000.`
2. `./scripts/init.sh --android-run`, then wait for the app to open on the emulator. Expected: the app opens.
3. `./scripts/init.sh --local-smoke`. Expected: two `PASS` lines and `Result: the smoke test passed on Desktop and the Android emulator.` Report both PASS lines.
4. Missing prerequisite: `./scripts/init.sh --local-rag-stop`, then `./scripts/init.sh --local-smoke`. Expected: `Result: the smoke test did not run. Start it with ./scripts/init.sh --local-rag-start, then run this command again.`
5. Recovery: `./scripts/init.sh --local-rag-start`, then `./scripts/init.sh --local-smoke`. Expected: the step 3 result again.
6. Optional: close the emulator window and run `./scripts/init.sh --local-smoke`. Expected: `PASS  Desktop`, a `FAIL  Android emulator` line naming `--android-run`, and `Result: the smoke test failed on the Android emulator. ...`
7. Finally, run `./scripts/init.sh --local-rag-stop`. Report back each `Result:` line, the two PASS line texts, and whether the emulator app still shows its earlier lands after the run.

## Evidence to capture

- The focused block and `--fast`: one line each with the command and its result.
- `DesktopSmokeDriverTest` case count, and confirmation that no real network was used.
- The walkthrough: each step's `Result:` line verbatim, which reply each platform showed (answered or abstained, with the source count), elapsed time, whether the retry was used, and confirmation that emulator app data survived.
- Any deviation from this spec, with its reason.

## Feature evidence

Implementer self-verification, 2026-11-01 (offline, fakes only; no service, Ollama, model, emulator, or device):

- `./scripts/init.sh --feature local_end_to_end_smoke`: focused tier passed (all 7 command lines).
  - `bash -n scripts/init.sh`: ok.
  - backend `tests/test_local_smoke.py tests/test_local_rag_commands.py tests/test_local_rag_service.py`: 143 passed, 2 skipped (the existing Ollama-port skips).
  - `:shared:jvmTest` smoke/connection/chat/platform: `LocalSmokeTest` 7, `DesktopSmokeDriverTest` 11, `LocalSmokeGuardTest` 4, `TestBuildGatingGuardTest` 5, all passing.
  - `compileDebugAndroidTestKotlin`, `compileReleaseKotlin`, `desktopApp:compileKotlin`: ok. `runDesktopLocalSmoke --dry-run`: task resolves (SKIPPED in dry run).
  - `verifyDesktopScreenshots` (6) and `verifyAndroidScreenshots` (4) chat goldens: pass unchanged.
- `./scripts/init.sh --fast`: all 9 offline checks passed (backend 1585 passed, 4 skipped).
- `./scripts/init.sh --verify`: fast and full tier passed.
- `DesktopSmokeDriverTest`: 11 cases on a Ktor `MockEngine` with the committed contract examples; host is asserted `127.0.0.1` and no real network is used. Compose `waitUntil` worked with engine I/O as is, so no `mainClock` change was needed.

Deviations from the spec, with reasons:

- `test_local_rag_service.py` gained `local_smoke` in the operator-module list of `test_the_service_never_imports_the_operator_modules`. The new operator module imports `local_rag_service`, and the guard now also covers it. The output of `local_rag_service.py` is unchanged.
- The Android driver builds `ConnectionTools` itself from `AndroidServiceAddressStore` wrapped in `ReadOnlyServiceAddressStore`. It does not call the debug `testBuildConnectionTools`, which cannot take a wrapped store. The Android script steps repeat `SmokeUiScript`, because androidTest cannot depend on shared jvmTest. The pure parts are shared in `LocalSmoke.kt` (`SmokeScreen`, classification, result line, read-only store).
- `other_address` with a saved address names `Usar la dirección predeterminada` only when the build default equals the expected address. The orchestrator reads the build default from `MANIJERO_ASK_BASE_URL` (Desktop) or `ORG_GRADLE_PROJECT_manijeroAskBaseUrl` (Android), falling back to the standard addresses. A default set in a `gradle.properties` file is not seen; the next run still converges. Documented in `backend/README.md`.
- The "not set up" line from `init.sh` and from Python is followed by `Result: the smoke test did not run. Run ./scripts/init.sh --local-rag-setup.` (scenario 2), instead of the `--local-rag-*` `Result: setup has not run yet.`
- `PROGRESS.md` "Start and verify" and `docs/progress/known-limitations.md` are left for the orchestrator at acceptance, as the contract says.

Not run here (owner walkthrough, recorded by the orchestrator): the real `--local-smoke` run against the service and emulator, AGP `installDebug` keeping app data, and the `ACCESS_LOCAL_NETWORK` grant on API 37.

## Validator checklist

- [ ] `--local-smoke` exists in `init.sh` early dispatch, `usage`, and `--check`. Misuse gives exit `2`, and no tier runs it.
- [ ] Prerequisites are checked before any build or install. Each gap prints one line naming the fix and `Result: the smoke test did not run. ...` (scenario 2).
- [ ] No emulator, or a booting emulator, keeps Desktop running and fails Android with a fix. Physical devices are never targeted (scenario 3).
- [ ] An address mismatch sends no request and names the right `Conexión` fix (scenario 4).
- [ ] Only `answered` with at least one source card, or `abstained`, passes. Exactly one retry. A 90 s bound (scenarios 1 and 5).
- [ ] Build, install, or instrument failures and malformed results give a log-path line with no traceback (scenario 6). Ctrl+C is handled (scenario 7).
- [ ] No `connectedAndroidTest`. Install keeps data, and the drivers never touch the land store or save or clear an address (scenario 8).
- [ ] No question, answer, or passage text appears in output, result files, or orchestrator logs.
- [ ] Tags only: no copy, semantics, or layout change. Chat screenshots pass unchanged. The release source set is untouched, and `TestBuildGatingGuardTest` passes.
- [ ] New dependencies are test-only (`androidx-test-runner`, jvmTest `ktor-client-cio`, androidTest and debug ui-test).
- [ ] `local_rag_service.py` output is byte-identical, and its tests are green.
- [ ] The durable docs are updated as listed. The owner guide has the section, the table, and a walkthrough with a missing-prerequisite case and a recovery.
- [ ] No answer-quality, legal-coverage, latency, or real-device claim anywhere.
- [ ] The focused block passes as published, and the walkthrough is recorded by the orchestrator.
