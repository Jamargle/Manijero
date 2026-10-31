# local_service_connection — appendix

## Repository research

### Files inspected

- `androidApp/build.gradle.kts`: covers `BuildConfig.ASK_BASE_URL` from the `manijeroAskBaseUrl` Gradle property, which defaults to `http://10.0.2.2:8000`. Only the `debug` and `release` build types exist; debug allows cleartext and release does not. There are no variant source sets yet.
- `androidApp/src/main/AndroidManifest.xml`: INTERNET and `ACCESS_LOCAL_NETWORK` permissions, and cleartext through a manifest placeholder. Backup rules exclude only `manijero_lands.xml`.
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`: the composition root. It has a lazy `answerHttpClient(Android.create())`, `KtorAnswerService(client, androidAskBaseUrl(...))`, and calls `App(landRepository, answerService, landBackupFiles)`.
- `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`: the Desktop root. It builds a CIO client and `desktopAskBaseUrl()`, and keeps land storage under `~/.manijero/`.
- `desktopApp/build.gradle.kts`: a Kotlin JVM module with Compose `application`/`nativeDistributions` and no build types. `./scripts/init.sh --desktop` runs `:desktopApp:run`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/platform/AskEndpoint.kt`: `selectAskBaseUrl` precedence: primary override, then secondary override, then default.
- `shared/src/{androidMain,jvmMain}/.../platform/*AskConfiguration.kt`: the platform defaults and overrides (`manijero.ask.baseUrl` system property, `MANIJERO_ASK_BASE_URL` env).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `answerHttpClient` uses `expectSuccess`, a 15 s request, a 10 s connect, and a 15 s socket timeout. `KtorAnswerService` fixes `askUrl` at construction.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the composition root has optional injected capabilities, for example `landBackupFiles` → `LandBackupController` or `null`, which removes the entry point.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/AppNavigation.kt`: the pure route table (`AppDestination`, `tabForDestination`, `backTarget`, `navigationVisible`), tested by `AppNavigationTest`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageScreen.kt`: the `Ayuda` screen, `CoverageScreen(onPrivacyClick, modifier)`, which ends with a privacy `TextButton`.
- `backend/app/main.py`, `backend/app/readiness.py`: `/health` → 200 `{"status":"ok","service":"manijero-backend"}`. `/ready` → 200 `{"status":"ready",...}` or 503 `{"status":"unavailable",...}`, with no problem codes in the body.
- `backend/app/pilot_guard.py`: `GATED_PATHS = {"/ask"}`, so `/health` and `/ready` need no token even in the pilot profile. This means no access-key result is needed.
- `scripts/init.sh`: `--backend` binds `0.0.0.0` by default, so LAN devices can reach it. `--android-run` installs the debug APK, `--desktop` runs `:desktopApp:run`, and `--feature` runs the verify block.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/platform/AndroidBackupExclusionGuardTest.kt`: the precedent for repo-level text/XML guard tests in jvmTest. It reads the first `getSharedPreferences("…")` in `AndroidLandStorage.kt`.
- `shared/build.gradle.kts`: commonTest already has `ktor-client-mock`. The jvmTest Roborazzi screenshots verify by default.
- `docs/constraints/operations.md`, `docs/constraints/ui-shell.md`, `ARCHITECTURE.md`, `DESIGN.md` (sections cited in the contract).
- `contracts/openapi.yaml`: does not describe `/health` or `/ready`; checked with grep only.

### Existing patterns to follow

- Optional host capability: inject a nullable dependency into `App`. When it is null, the route and its entry button do not exist (`LandBackupFiles`).
- Controller plus reducer state in commonMain, with the coroutine scope from `rememberCoroutineScope` (`LandBackupController`).
- Platform stores live in shared `androidMain`/`jvmMain`. Desktop writes use a temporary file and `ATOMIC_MOVE` (`FileLandStorage`, `DesktopLandBackupFiles`). Android uses one private preferences file per concern.
- Pure, testable platform selectors take their inputs as parameters (`desktopAskBaseUrl(systemProperty, environmentVariable)`).
- Copy goes in `composeResources/values/strings.xml` with a screen prefix. Screens use `ManijeroScreen`, `ManijeroCard`, and `ManijeroCallout`.

### Current gaps

- No variant-specific Android source sets and no Desktop debug/release distinction exist. This feature introduces both gates.
- The answer base URL cannot change at runtime.
- No client code reads `/health` or `/ready`.
- No Compose interaction-test runner exists. The UI is covered by reducer/controller tests, previews, and manual runs.

## Implementation plan

1. Add `normalizeServiceAddress` and its `Invalid` result to `connection/ServiceAddress.kt`. Add `ServiceAddressStore` and `ActiveServiceAddress` with the precedence and fallback rules from the contract.
2. Add the `baseUrl: () -> String` constructor to `KtorAnswerService`, evaluated on every `ask`. Keep the `String` constructor delegating to it.
3. Add `ServiceCheckResult` and `KtorServiceStatusChecker` (health first, then readiness, fixed outcome mapping, rethrow cancellation, no logging).
4. Add `ConnectionState`, the actions, the reducer, and `ConnectionController` (save then check, reset, store-failure handling, buttons disabled while checking, cancel on leave). Add `ConnectionTools` to bundle the address and the checker.
5. Add the `connection_*` strings and `ConnectionScreen` with previews for each state.
6. Add `AppDestination.Connection` and its tab, back target, and visibility to `AppNavigation.kt`. Add the optional `connectionTools` to `App`, and the optional `onOpenTestTools` card to `CoverageScreen`.
7. Add `AndroidServiceAddressStore` (`manijero_connection` preferences, in its own file) and `FileServiceAddressStore` (`~/.manijero/connection-v1.txt`, atomic write).
8. Add `desktopTestBuildEnabled(property)` and its property-name constant in shared jvmMain.
9. Create the Android `src/debug` and `src/release` `TestBuildTools.kt` (release returns `null`). Wire `MainActivity` so it gets the tools from that function and uses the address provider only when tools exist.
10. Set the property on the Desktop `run` task only, through a lazy `tasks.withType<JavaExec>().matching { it.name == "run" }`. Wire `main.kt` from `desktopTestBuildEnabled`.
11. Write the tests listed below, then run the focused block and the manual checks.
12. Update `ARCHITECTURE.md`, `docs/constraints/ui-shell.md`, and `DESIGN.md` per the contract. Record evidence below, and update `PROGRESS.md` and `feature_list.json` per `feature-implementer`.

## Verification plan

- `ServiceAddressTest`: trimming, trailing-slash removal, path prefix kept, the 512-character boundary, each rejected form (blank, scheme, host, port 0/65536, user info, query, fragment), and Unicode or emoji hosts handled without a crash.
- `ActiveServiceAddressTest`: default when nothing is saved; a saved value wins over the default; an invalid or unreadable stored value falls back; save or clear failure leaves `current` unchanged.
- `ServiceStatusCheckerTest` (MockEngine): ready; 503 not-ready; `/ready` I/O failure, 500, or bad body → unknown; health connect failure or timeout → unreachable; health 404 or a foreign JSON or HTML body → not-Manijero; `/ready` not called after a failed health check; requests have no body or auth header; cancellation propagates.
- `ConnectionControllerTest`: invalid input makes no request and no save; save-then-check order; storage failure stops before the check; buttons disabled while checking; reset clears and announces the default; a second press during a check is ignored.
- `KtorAnswerServiceTest`: after the provider value changes, the next `ask` posts to the new `<url>/ask`. The existing tests stay green.
- `AppNavigationTest`: `Connection` maps to the `Help` tab, back goes to `Coverage`, and navigation is visible.
- `FileServiceAddressStoreTest` (temp directory): round trip, clear, a missing file returns null, and no partial file is left after a failed write.
- `AndroidServiceAddressStoreTest` (Robolectric): round trip and clear in `manijero_connection`. The land preferences file is untouched.
- `TestBuildGatingGuardTest` checks these rules:
  - The release `TestBuildTools.kt` exists and has no `connection` import.
  - The debug `TestBuildTools.kt` exists.
  - `androidApp/src/main` never names `ConnectionScreen` or `AndroidServiceAddressStore`.
  - In `desktopApp/build.gradle.kts`, `manijero.testBuild` is set only inside the `run` task configuration, never in `jvmArgs` or `nativeDistributions`.
  - `desktopTestBuildEnabled` is true only for `"true"`.
- `HelpPrivacyScreenshotsTest`: the existing baselines pass unchanged, which proves `Ayuda` is unchanged when the tools are absent.
- Compiles: Android debug and release Kotlin, and Desktop.
- Manual: the contract's manual list. Also check large text and keyboard use on the Desktop `Conexión` screen.
- E2E: there is no persistent UI E2E runner. Unit and integration coverage of the reducer, probe, and gating, plus the manual live runs, are enough for a test-only screen. `local_end_to_end_smoke` owns the end-to-end smoke.

## Evidence to capture

- Each focused-block command, with a one-line result.
- The test names added per file.
- Manual Desktop and Android results for scenarios 3, 4, and 6, with the service state used (no addresses that identify a person's network).
- The `runDistributable` check showing no test-tools card. For Android release, the compile result plus the guard test (no installable signed release exists).

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer (JDK: the Gradle-provisioned Zulu 21 via `JAVA_HOME`; no system Java on this host).

- `./scripts/init.sh --feature local_service_connection`: passed (all three command lines).
  - jvmTest: `ServiceAddressTest` 6, `ActiveServiceAddressTest` 5, `ServiceStatusCheckerTest` 9, `ConnectionControllerTest` 10, `FileServiceAddressStoreTest` 4, `TestBuildGatingGuardTest` 5, `KtorAnswerServiceTest` 10 (1 new), `AppNavigationTest` 22 (1 new), plus `AndroidBackupExclusionGuardTest` 1 and `AskEndpointTest` 3; 0 failures.
  - testAndroidHostTest: `AndroidServiceAddressStoreTest` 2 plus the 4 commonTest connection suites; 0 failures.
  - `:androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:compileKotlin`: compiled.
- Repair after the validator's revise verdict: the focused block's `--tests HelpPrivacyScreenshotsTest` jvmTest filter matched nothing, because jvmTest excludes the screenshots package. It is replaced by the `verifyDesktopScreenshots` and `verifyAndroidScreenshots` lines.
  - Rerun of `./scripts/init.sh --feature local_service_connection` with all five lines: passed.
  - Desktop and Android `HelpPrivacy` screenshot tests: 12 + 12 passed, baselines unchanged, 0 failures.
- `CI=true ./scripts/init.sh --fast`: 9 of 9 checks passed (backend 1346 passed, 2 skipped).
- Live probe shapes (uvicorn on loopback, then stopped): with the campaign set, `/health` 200 `ok`/`manijero-backend` and `/ready` 200 `ready`; without it, `/ready` 503 `unavailable`. These match the checker's Ready and NotReady mapping.
- Desktop gating: a Gradle init-script query after evaluation printed `run: manijero.testBuild=true` and `runRelease: null`. `runDistributable` is not a JavaExec. The `createDistributable` launcher `.cfg` has 0 `manijero.testBuild` options.
- Android release: compile plus `TestBuildGatingGuardTest`. The release `testBuildConnectionTools` returns `Nothing?` (always `null`) and imports nothing from `connection`.
- Not run here: the interactive GUI scenarios 3, 4, and 6 on Desktop (`--desktop`) and the emulator (`--android-run`), and the visual `runDistributable` look at `Ayuda`. This session has no way to drive the GUI, so these are left for the validator or owner.
- `--verify`: not run; the spec does not require it, and the focused block covers both host compiles.
- 2026-11-01, validator: first pass `revise` (inert screenshot filter in the focused block), repaired above; second pass `accept` after a fresh `./scripts/init.sh --feature local_service_connection` (all five lines passed). Record: [`docs/validations/local_service_connection.md`](../../validations/local_service_connection.md).

## Validator checklist

- [ ] Scope matches the contract, and the non-goals are respected (no token, no backend or contract change, no release-build configuration).
- [ ] Release exclusion holds on both platforms:
  - Android release returns `null` from the variant source set.
  - The Desktop flag appears only on `run`.
  - The guard test passes, and the `runDistributable` check is recorded.
- [ ] Acceptance scenarios 1–8 pass, with evidence. Every result message matches the contract copy and never shows raw bodies, codes, or exceptions.
- [ ] The saved address takes effect for the next `/ask` without a restart, survives a restart, and reset restores the build default.
- [ ] Shared UI and logic stay in `commonMain`. Stores and gating stay in platform source sets. `design/` components stay presentational.
- [ ] Nothing logs the address or probe results, and the probes send no question, land data, or token.
- [ ] The focused verification block runs unchanged through `./scripts/init.sh --feature local_service_connection`.
- [ ] The durable documentation impact is followed (`ARCHITECTURE.md`, `ui-shell.md`, `DESIGN.md`), and nothing is restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` are updated correctly.
