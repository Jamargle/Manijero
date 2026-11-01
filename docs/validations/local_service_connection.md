# `local_service_connection` acceptance

## Verdict

**Accepted** on 2026-11-01 after independent validation. One revise round: the spec's focused
block used a `--tests HelpPrivacyScreenshotsTest` filter under `:shared:jvmTest`, which excludes
the screenshots package, so it checked nothing. The block now runs `:shared:verifyDesktopScreenshots`
and `:shared:verifyAndroidScreenshots` scoped to the `Ayuda` screenshot classes. No code changed in
the repair.

## Independent verification

All Gradle runs used the Gradle-provisioned Zulu 21 through `JAVA_HOME`; this host has no system Java.

- `./scripts/init.sh --feature local_service_connection`: passed, all five lines.
  - jvm: `ActiveServiceAddressTest` 5, `ConnectionControllerTest` 10, `FileServiceAddressStoreTest` 4,
    `ServiceAddressTest` 6, `ServiceStatusCheckerTest` 9, `TestBuildGatingGuardTest` 5; 0 failures, 0 skipped.
  - Android host: `AndroidServiceAddressStoreTest` 2 plus the four shared connection suites; 0 failures.
  - Android debug and release and Desktop compiles passed.
  - `Ayuda` screenshots: Desktop 12/12 and Android 12/12 against the committed goldens, no golden changed.
- `CI=true ./scripts/init.sh --fast`: 9 of 9 passed (first validation pass; only docs changed since).

## Review

- Scope: no bearer token, backend, `contracts/`, or release-build configuration change.
- Release gating: the Android release `TestBuildTools.kt` returns `Nothing?` (always `null`) and
  imports nothing from `connection`; the Desktop `manijero.testBuild` property is set only on the
  `run` JavaExec task. `TestBuildGatingGuardTest` enforces both.
- Copy matches the spec; callouts pair an icon with text and show no raw bodies or codes.
- Privacy: probes are bodiless GETs without a token; no logging in the connection code; cancellation
  is rethrown. The address store is local and private (Android uses its own `manijero_connection`
  preferences file).
- `ARCHITECTURE.md`, `DESIGN.md`, and `docs/constraints/ui-shell.md` were updated as the spec required.

## Limits (not verified)

- Manual GUI scenarios 3, 4, and 6 on Desktop (`./scripts/init.sh --desktop`) and the Android
  emulator (`./scripts/init.sh --android-run`) against `./scripts/init.sh --backend` were not run;
  only the service's `/health` and `/ready` response shapes were probed live.
- The visual `./gradlew :desktopApp:runDistributable` check that `Ayuda` has no test-tools card was
  not run; release exclusion rests on the guard test, the release compile, and the implementer's
  Gradle task query.
- `./scripts/init.sh --verify` was not run.
