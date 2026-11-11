# client_environment_builds — appendix

## Repository research

### Files inspected

- `PROGRESS.md` "Current state" — test builds (Android debug, Desktop `run`) carry the pilot token and `Conexión`; QA has only a placeholder template; prod unconfigured.
- `feature_list.json` — dependents `qa_real_device_check` (needs this feature) and `qa_server_deployment` (chooses the host); `private_pilot_distribution` removed (2026-11-11).
- `docs/specs/client_pilot_credentials.md` — token validation shape, plain error message, debug-only `onVariants` split, Desktop run-only classpath folder, `MANIJERO_PILOT_TOKEN_FILE` override, `check-pilot-token-build.sh` shape.
- `docs/specs/local_service_connection.md` — Android `src/debug`/`src/release` gating, Desktop `manijero.testBuild` on `run` only, `ActiveServiceAddress` default-then-saved resolution, store paths.
- `docs/specs/environment_profiles.md` and appendix "Planner decisions" — QA home `~/manijero/qa` (`MANIJERO_QA_HOME` tests only), key `credentials/qa-test-device.token` (`0600`) kept "for `client_environment_builds`", placeholder `https://qa.manijero.invalid`; non-goal "giving an app the QA token (`client_environment_builds`)".
- `backend/deploy/environments/qa.settings.env.example` — `MANIJERO_PUBLIC_URL=https://qa.manijero.invalid` (the same placeholder).
- `androidApp/build.gradle.kts` — `applicationId com.jamarglex.manijero`, `ASK_BASE_URL` from `manijeroAskBaseUrl` or `http://10.0.2.2:8000`, `pilotTokenFile`/`pilotTokenBuildConfigValue` providers, `onVariants` debug-only token, cleartext placeholders.
- `androidApp/src/main/AndroidManifest.xml` — `android:label="@string/app_name"`; `res/values/strings.xml` `app_name` = `Manijero`.
- `androidApp/src/main/kotlin/.../MainActivity.kt` — reads `BuildConfig.ASK_BASE_URL` and `PILOT_TOKEN`; no change needed.
- `desktopApp/build.gradle.kts` — `generatePilotTokenResource`, `nativeDistributions.packageName com.jamarglex.manijero`, run-only block.
- `desktopApp/src/main/kotlin/.../main.kt` — title `Manijero`, `.manijero` land folder, `desktopAskBaseUrl()`, `testBuildConnectionTools`.
- `shared/src/jvmMain/.../platform/DesktopAskConfiguration.kt` (`manijero.ask.baseUrl`, `MANIJERO_ASK_BASE_URL`, default `http://127.0.0.1:8000`), `platform/DesktopPilotToken.kt` (classpath resource reader pattern), `connection/DesktopTestBuild.kt` and `welcome/FileWelcomeNoticeStore.kt` (hard-coded `.manijero` paths).
- `shared/src/jvmTest/.../platform/TestBuildGatingGuardTest.kt`, `PilotTokenGuardTest.kt` — text guards on both build scripts; `PilotTokenGuardTest` forbids any `inputs.property` in the Desktop script and expects `.orElse("pilot-token.local")`.
- `scripts/check-pilot-token-build.sh` — fake-file build check pattern, cleanup trap, `unzip` jar checks, run-task probe.
- `scripts/init.sh` — single-mode `case "$1"` dispatch; `--android` (`assembleDebug`), `--android-run` (hard-coded package `com.jamarglex.manijero`), `--desktop` (`:desktopApp:run`).
- `gradle.properties` — configuration cache and build cache on: all file and property reads must go through `providers`.
- `.gitignore` — `/pilot-token.local` and environment key guard patterns.
- Not inspected: `LocalSmokeGuardTest`, `AndroidBackupExclusionGuardTest` bodies (the implementer confirms the label placeholder does not trip them), `ARCHITECTURE.md` body, `docs/constraints/*` bodies, the AGP merged-manifest output path.

### Planner decisions (the owner may rename before implementation)

- Setting `manijeroEnvironment` (Gradle property): matches the existing `manijeroAskBaseUrl`, keeps every task name, and avoids flavors that would double variants and break `--android-run`, `--local-smoke`, and the guards.
- Address file `<repo>/qa-address.local` (+ `MANIJERO_QA_ADDRESS_FILE` override): mirrors `pilot-token.local`; decision 3 asks for a git-ignored local file. `~/manijero/qa/settings.env` `MANIJERO_PUBLIC_URL` was not reused because it is outside the checkout and owned by `environment_profiles`; `qa_server_deployment` should make the two agree (open question).
- QA token source: the `environment_profiles` QA key, because that feature generated it for this purpose; the local token stays `pilot-token.local` (no change to accepted behavior).
- Desktop data folder `~/.manijero-qa`: "installs beside" means separate lands, welcome, and saved address, as Android gets from the id suffix.
- QA ignores the address overrides so a `Manijero QA` app never targets a local address by default; `Conexión` remains for deliberate changes in test builds.
- Two init modes `--android-qa`, `--desktop-qa`: operations rules require one named command; an emulator run against a placeholder host is not useful yet.

### Open questions (non-blocking)

- Should the local test builds switch to `~/manijero/local/credentials/local-test-device.token`? Kept on `pilot-token.local` here; the local service does not check tokens.
- Once `qa_server_deployment` chooses the host, should the build read `MANIJERO_PUBLIC_URL` from the QA settings file instead of `qa-address.local`?

## Implementation plan

1. `.gitignore`: add `/qa-address.local`.
2. `androidApp/build.gradle.kts`: `manijeroEnvironment` provider with validation; QA address provider (file or override, validated, placeholder plus one warning); `applicationIdSuffix`, `appLabel` placeholder, `MANIJERO_ENVIRONMENT` field; environment-aware `pilotTokenFile` with a QA-specific error message; keep the `onVariants` split byte-for-byte in shape.
3. `AndroidManifest.xml`: `android:label="${appLabel}"`.
4. `desktopApp/build.gradle.kts`: the same providers; `generateEnvironmentResource` into `build/generated/environment` added to `sourceSets.main.resources`; environment-aware token file; QA `packageName` suffix.
5. jvmMain `platform/DesktopEnvironment.kt`: resource name constant, parser, `title`, `dataFolder`, `askBaseUrl`; folder parameter on `desktopConnectionStorePath` and `desktopWelcomeStorePath`.
6. `main.kt`: wire the title, the default address, and the data folder (lands, welcome, connection).
7. Guards: create `EnvironmentBuildGuardTest` (both scripts share the messages and placeholder, the QA branch never names `pilot-token.local`, the local branch never names the QA key path, no `inputs.property` carries a token, `MANIJERO_QA_HOME` path matches `environment_profiles`); adjust `PilotTokenGuardTest` and `TestBuildGatingGuardTest` patterns minimally.
8. `scripts/check-environment-build.sh`: fake-file assertions (see Verification plan).
9. `scripts/init.sh`: `--android-qa`, `--desktop-qa`, usage lines, `Result:` line.
10. Run the focused block; record evidence; update the durable docs listed in the contract.

## Verification plan

- jvmTest `DesktopEnvironmentTest`: missing resource is local; `local` and `qa` resources parse; unknown environment, QA without an address, a non-https address, and a duplicated key are refused; the title and data folder per environment; QA ignores the runtime overrides.
- jvmTest path tests: connection and welcome paths under `.manijero` by default and under `.manijero-qa` when given.
- `EnvironmentBuildGuardTest` and the updated guards (text-level, no SDK).
- `check-environment-build.sh` assertions:
  - local default with an invalid fake address file and a fake QA key present: id, label, `ASK_BASE_URL`, `PILOT_TOKEN null`, and Desktop `environment=local`;
  - QA with a valid fake address and fake key: debug `.qa` id, `Manijero QA`, the address, the fake key; release `.qa` with `PILOT_TOKEN null`; Desktop resource QA plus the address; jar without token;
  - QA without an address file: the placeholder plus the single warning line;
  - QA with an invalid address, an invalid key, and `manijeroEnvironment=prod`: each fails with its exact message and no content echoed.
- The existing `check-pilot-token-build.sh` must still pass (local mode).
- Not covered: a GUI launch, a device install, or a reachable QA service (`qa_real_device_check`).

## Evidence to capture

- Each focused command with a one-line result.
- `check-environment-build.sh` PASS lines (one line each, not pasted logs).
- Any guard pattern changed in `PilotTokenGuardTest` or `TestBuildGatingGuardTest`, with one line on why no token rule weakened.
- A configuration-cache note: a QA build followed by a local build reuses no stale QA output.

## Feature evidence

- `./scripts/init.sh --feature client_environment_builds`: passed (jvmTest platform/connection/welcome, host compiles, `check-environment-build.sh` 5 PASS lines + Result, `check-pilot-token-build.sh` 5 PASS + Result).
- `./scripts/init.sh --fast`: passed (10 offline checks, backend 1831 passed, 4 skipped).
- `./scripts/init.sh --verify`: Full tier passed (Android host tests, `assembleDebug`, `:desktopApp:build`).
- `./scripts/init.sh --android-qa extra`: refused, exit 2 (`Run --android-qa on its own, with nothing after it.`).
- Configuration-cache note: `check-environment-build.sh` builds QA then local with caching on and asserts id, token, and resource are back to local (task inputs: BuildConfig fields, manifest placeholders, `inputs.property` environment and askBaseUrl).
- Guard changes in `PilotTokenGuardTest`: (1) `inputs.property` was forbidden in the Desktop script; it must now be exactly the two non-secret properties `environment` and `askBaseUrl` of `generateEnvironmentResource` (no token input is allowed); (2) `resources.srcDir` was forbidden outside the run block; it must now be exactly `resources.srcDir(generateEnvironmentResource)`. Every other rule (token folder only on `run`, debug-only token, no JVM property, logging) is unchanged. `TestBuildGatingGuardTest` is unchanged.
- Deviations: the placeholder notice is printed only by `androidApp/build.gradle.kts` (every build configures both apps, so one notice); Desktop `main.kt` stops with a plain message on a malformed environment resource.

## Validator checklist

- [ ] The focused block passes unchanged through `./scripts/init.sh --feature client_environment_builds`.
- [ ] Local builds are byte-for-byte unchanged in id, label, address, token source, and Desktop data folder (scenario 1).
- [ ] QA builds use the `.qa` id and are named `Manijero QA`, use `~/.manijero-qa`, and use the file address or placeholder (scenarios 2–3).
- [ ] Failure messages match exactly and never echo content (scenario 4).
- [ ] Only Android debug and Desktop `run` carry a token. QA never reads `pilot-token.local`; local never reads the QA key (scenario 5).
- [ ] `--android-qa` and `--desktop-qa` exist, appear in usage, and leave the local modes unchanged (scenario 6).
- [ ] No real host, token, or key appears in the diff; `/qa-address.local` is ignored (scenario 7).
- [ ] Guard changes do not weaken any `client_pilot_credentials` or `local_service_connection` rule.
- [ ] No commonMain, UI copy, backend, or contracts change; durable docs updated as listed.
