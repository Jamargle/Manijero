# Feature Spec: `client_environment_builds`

## Source metadata

- `id`: `client_environment_builds` · `area`: client · `depends_on`: `local_service_connection`, `client_pilot_credentials`, `environment_profiles` (all accepted) · `status` at planning: `not_started`
- User-visible behavior: one build setting chooses whether the Android and Desktop test apps target the **local** or the **QA** environment. A QA build is named `Manijero QA`, installs beside the local app, uses the QA address, and (test builds only) sends the QA access key. Local builds behave exactly as today.
- Verification: a build-output check with fake QA address and token files in temporary folders, desktop environment unit tests, updated guard tests, host compiles, and the existing pilot-token build check. No device, emulator, or running service. The commands are in Focused verification.
- Notes: owner decisions recorded 2026-11-02:
  1. One build setting picks the target environment: local or QA.
  2. The QA app is named `Manijero QA` and installs beside the local one: a separate Android application id suffix and a separate Desktop app name.
  3. The QA host does not exist yet. Until `qa_server_deployment` chooses it, the build reads the QA address from a git-ignored local file and defaults to a placeholder. Never commit a real host or credentials.
  4. Keep the pilot token rules: agents never read `pilot-token.local`; tests use fake tokens via `MANIJERO_PILOT_TOKEN_FILE` in temporary folders.
  5. Desktop: a runnable app from the existing Gradle tasks, no signed installer.
  6. Approval: the independent validator's accept is final, no owner walkthrough. Checking a real device against QA belongs to `qa_real_device_check` (out of scope).
- Planner choices (appendix "Planner decisions"; confirm or rename before implementation): the setting is the Gradle property `manijeroEnvironment`; the address file is `<repo>/qa-address.local`; the QA token comes from the QA access key that `environment_profiles` made for this feature; Desktop QA data lives in `~/.manijero-qa`.

## Goal

The owner or a developer runs one command to build a test app for QA. It is clearly named `Manijero QA`, lives next to the local app without sharing its data, points at the QA address, and carries the QA access key in test builds only. Nothing about the local app changes.

## Non-goals

- Deploying or choosing the QA host, TLS, or domain (`qa_server_deployment`); checking a real device against QA (`qa_real_device_check`).
- A prod build, Android product flavors, signing, a signed or notarized Desktop installer, or distribution (`private_pilot_distribution`, on hold).
- Any in-app UI or Spanish copy change: no environment badge, no change to `Conexión`, `Ayuda`, or the top bar.
- Generating, rotating, or showing tokens; changing `--pilot-token-save` or the local token source (`pilot-token.local` stays the local token).
- Backend, `contracts/`, `knowledge/`, `environment_profiles.py`, or iOS changes.

## Job story

When I want testers to try Manijero against the QA service, I want to build a separate `Manijero QA` app with one command, so they can keep the local app and never mix the two up or type a key.

## Acceptance scenarios

### 1. Local stays the default and unchanged

Given no `manijeroEnvironment` setting, or `-PmanijeroEnvironment=local` · When Android (debug and release) and Desktop are built or run · Then the application id is `com.jamarglex.manijero`, the launcher label and window title are `Manijero`, and `ASK_BASE_URL` follows `manijeroAskBaseUrl` or defaults to `http://10.0.2.2:8000`. Desktop keeps `http://127.0.0.1:8000` with its existing overrides and stores data in `~/.manijero`. The pilot token still comes only from `pilot-token.local` (or `MANIJERO_PILOT_TOKEN_FILE`). The QA address file and QA access key are never read, even when they exist or are malformed. Every existing test and the pilot-token build check pass unchanged.

### 2. A QA build is a separate app

Given `-PmanijeroEnvironment=qa` · When Android is built · Then every variant has the application id `com.jamarglex.manijero.qa`, the launcher label is `Manijero QA`, and `BuildConfig.MANIJERO_ENVIRONMENT` is `"qa"`. The app installs beside the local one with its own data, because its application id differs.
When Desktop runs via `:desktopApp:run` · Then the window title is `Manijero QA`, lands, the welcome notice, and the saved `Conexión` address live in `~/.manijero-qa/` (never `~/.manijero/`), and the native-distribution package name is `com.jamarglex.manijero.qa`. The `Conexión` test tools stay available in QA test builds, as today.

### 3. QA address from the git-ignored file

Given a QA build and `qa-address.local` (or the file named by `MANIJERO_QA_ADDRESS_FILE`) holding one valid address · Then Android `ASK_BASE_URL` and the Desktop default address are that address, with surrounding whitespace and trailing `/` removed. `manijeroAskBaseUrl`, `manijero.ask.baseUrl`, and `MANIJERO_ASK_BASE_URL` are ignored, so a QA app never targets a local address by default. A valid address is `https://`, has a host, an optional port 1–65535, an optional path, no user info, query, fragment, or whitespace, and at most 512 characters.
Given no such file · Then the address is the placeholder `https://qa.manijero.invalid`. The build succeeds and prints once: `The QA address is a placeholder (https://qa.manijero.invalid) until the QA server is chosen; this app cannot reach QA yet.`

### 4. Invalid settings fail the build plainly

| Condition | Build result |
|---|---|
| `manijeroEnvironment` is anything other than `local` or `qa` (including `prod`, `QA`, blank) | fails: `manijeroEnvironment must be local or qa; prod is not configured.` |
| QA build, address file present but not a valid address (scenario 3) | fails: `qa-address.local is not a valid QA address. Write one https:// address on one line, for example https://qa.example.org` |

Neither message echoes the file content. A local build is unaffected by a malformed address file.

### 5. QA access key: test builds only

Given a QA build and the QA access key at `<QA home>/credentials/qa-test-device.token` (QA home is `MANIJERO_QA_HOME`, for tests only, or `~/manijero/qa`) · When the Android debug variant or the Desktop `run` task is built · Then that key is the built-in pilot token, using the same validation, plain error message rule (no content echoed), and `/ask`-only, https-or-loopback sending rule as `client_pilot_credentials`. `MANIJERO_PILOT_TOKEN_FILE` still overrides the path for tests.
A QA build never reads `pilot-token.local`, and a local build never reads the QA key. With no QA key, `PILOT_TOKEN` is `null` and the build succeeds. A malformed QA key fails the QA test build with `The QA access key is not valid. Run ./scripts/init.sh --qa-settings-setup again.`
Android release variants and every Desktop jar, packaged, or release output never carry any token, in any environment (unchanged from `client_pilot_credentials` scenario 2a).

### 6. One named command per host

`./scripts/init.sh --android-qa` builds the QA Android debug APK and ends with `Result: the Manijero QA app was built: androidApp/build/outputs/apk/debug/androidApp-debug.apk`. `./scripts/init.sh --desktop-qa` opens the `Manijero QA` Desktop app. Both are listed in `usage`. `--android`, `--android-run`, `--desktop`, and `--local-smoke` stay local. An extra argument is refused with exit `2`, as for other modes.

### 7. Nothing secret is committed or printed

- `/qa-address.local` is git-ignored.
- No build output, log, or check prints the QA key or the pilot token.
- Desktop jars contain the non-secret `manijero/environment.properties` (environment name, and the address in QA) but no token.
- No committed file holds a real QA host. Only `.invalid` placeholders and `qa.example.org` in messages appear.

## Technical approach

- **Setting:** the Gradle property `manijeroEnvironment` (`-P…` or `ORG_GRADLE_PROJECT_manijeroEnvironment`), read through `providers.gradleProperty` in both host scripts and validated to `local`/`qa`. It is the only switch; product flavors are not added, so every existing task name stays the same.
- **Android (`androidApp/build.gradle.kts`):** in QA, `defaultConfig.applicationIdSuffix = ".qa"`, the manifest placeholder `appLabel` = `Manijero QA` (local: `@string/app_name`; the manifest label uses `${appLabel}`), `ASK_BASE_URL` from the validated address provider, and `BuildConfigField MANIJERO_ENVIRONMENT`. The existing `pilotTokenFile` provider becomes environment-aware: the override, or the local file, or the QA key path. The debug-only `onVariants` split is unchanged. `MainActivity` is unchanged.
- **Desktop (`desktopApp/build.gradle.kts`):** a new `generateEnvironmentResource` task writes `manijero/environment.properties` into `build/generated/environment/`, which is added to the `main` resources. Its inputs are the environment name and, in QA, the address; both are non-secret `inputs.property` values. The token task reads the environment-aware file exactly as today, and only `run` sees its folder. In QA, `nativeDistributions.packageName` gets the `.qa` suffix.
- **Desktop runtime (shared `jvmMain`):** a new `platform/DesktopEnvironment.kt` parses the resource into `local` or `qa`, plus the address, title, and data folder name (`.manijero` or `.manijero-qa`). A missing resource means local (unit tests, IDE runs); a present but malformed one (unknown environment, QA without a valid address) stops startup with a plain message instead of silently running as local. `main.kt` uses it for the title, the default address (QA: the resource address; local: `desktopAskBaseUrl()`), and the data folder passed to `desktopConnectionStorePath` and `desktopWelcomeStorePath` (both gain a folder parameter, defaulting to `.manijero`) and the land store.
- **Validation:** the address and key checks are duplicated in the two build scripts, following the existing token-check pattern. A guard test keeps the messages, placeholder, and paths identical in both.
- **Boundaries:** [ARCHITECTURE.md](../../ARCHITECTURE.md) "Answer service boundary"; [hosting-and-pilot.md](../constraints/hosting-and-pilot.md) token rules; [operations.md](../constraints/operations.md) owner operability.

## Expected file changes

- Modify: `androidApp/build.gradle.kts`, `androidApp/src/main/AndroidManifest.xml` (label placeholder), `desktopApp/build.gradle.kts`, `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`, `shared/src/jvmMain/.../connection/DesktopTestBuild.kt`, `shared/src/jvmMain/.../welcome/FileWelcomeNoticeStore.kt` (folder parameter), `scripts/init.sh` (two modes, usage), `.gitignore` (`/qa-address.local`).
- Create: `shared/src/jvmMain/kotlin/com/jamarglex/manijero/platform/DesktopEnvironment.kt`, `scripts/check-environment-build.sh`.
- Tests: create jvmTest `platform/DesktopEnvironmentTest`, `platform/EnvironmentBuildGuardTest`; update `platform/PilotTokenGuardTest` and `platform/TestBuildGatingGuardTest` only where their text patterns must admit the environment-aware token path and the non-token `inputs.property`, without weakening any token rule; extend existing `connection`/`welcome` path tests for the folder parameter.
- Not changed: commonMain, `MainActivity.kt`, `check-pilot-token-build.sh` (unless its local-mode assertions need `-PmanijeroEnvironment=local` pinned), backend, contracts.

## Visual design impact

UI involved: no in-app change. Only the Android launcher label and the Desktop window title read `Manijero QA` in QA builds; no screens, copy, or screenshot baselines change.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update "Answer service boundary". Add one paragraph: `manijeroEnvironment` selects local or QA at build time; QA uses the `.qa` id suffix, its own Desktop data folder, the git-ignored address file or placeholder, and the QA key in test builds only.
- `docs/constraints/hosting-and-pilot.md`: update the token rule. A QA test build MUST take its token only from the QA access key (or the test override) and MUST NOT read `pilot-token.local`; a local build MUST NOT read the QA key. Reason: this spec.
- `docs/constraints/operations.md`: add one MUST NOT. A real QA host or any credential MUST NOT be committed; the QA address lives only in the git-ignored `qa-address.local` until `qa_server_deployment`. Reason: this spec, decision 3.
- `docs/owner-guide/qa.md`: add "Build the QA test apps", about 25 lines: the two commands, the `Result:` line, the placeholder notice, and the two build-failure messages with their fixes.
- `AGENTS.md` "Operating rules": extend the pilot-token clause to say agents also never read environment access keys under `~/manijero/*/credentials/`.
- `backend/README.md`: update the "Client token" bullet with one line saying QA test builds send the QA key.
- `docs/progress/known-limitations.md`, `docs/risks-and-open-questions.md`: QA builds point at a placeholder until `qa_server_deployment`, and no QA build has run on a device.
- `DESIGN.md`, `CONTEXT.md`, `contracts/`: not needed. There is no UI change, no new domain term, and no wire change.

## Focused verification (required)

<!-- verify:start -->
```sh
bash -n scripts/init.sh
bash -n scripts/check-environment-build.sh
git check-ignore -q qa-address.local
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.platform.*' --tests 'com.jamarglex.manijero.connection.*' --tests 'com.jamarglex.manijero.welcome.*'
./gradlew --quiet :androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:classes
./scripts/check-environment-build.sh
./scripts/check-pilot-token-build.sh
```
<!-- verify:end -->

`check-environment-build.sh` uses only fake address and key files in a `mktemp -d` folder (`MANIJERO_QA_ADDRESS_FILE`, `MANIJERO_QA_HOME`, and `MANIJERO_PILOT_TOKEN_FILE` pointing at a missing temp path for local runs). It never reads `pilot-token.local`, `~/manijero`, or `qa-address.local`. It asserts scenarios 1 to 5 and 7 from generated outputs: both `BuildConfig`s (`APPLICATION_ID`, `MANIJERO_ENVIRONMENT`, `ASK_BASE_URL`, `PILOT_TOKEN`), the merged debug manifest label, `desktopApp/build/generated/environment`, and the Desktop jar. It ends by regenerating in local mode (token override still pointing at the missing temp path), so `build/` holds no fake and no QA output. It prints no token and ends with one `Result:` line.

Manual: none (decision 6). The validator may launch `./scripts/init.sh --desktop-qa` to see the title, but no service, emulator, or device is required.

## Appendix

See [`client_environment_builds.appendix.md`](client_environment_builds.appendix.md) for research, plan, evidence, and the validator checklist.
