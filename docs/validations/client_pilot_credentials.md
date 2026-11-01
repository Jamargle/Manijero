# `client_pilot_credentials` acceptance

## Verdict

**Accepted** on 2026-11-01 after independent validation. No revise round was needed.
Spec: [`client_pilot_credentials.md`](../specs/client_pilot_credentials.md); implementer evidence:
[appendix](../specs/client_pilot_credentials.appendix.md) "Feature evidence".

## Independent verification

- `./scripts/init.sh --feature client_pilot_credentials` passed: filtered `:shared:jvmTest` set,
  `test_pilot_token_command.py` (15 passed), Android debug/release and Desktop compiles, and
  `check-pilot-token-build.sh` (3 PASS lines plus its `Result:` line).
- `CI=true ./scripts/init.sh --fast`: all 9 checks passed (backend 1533 passed, 4 skipped).
- `./scripts/init.sh --verify` passed (Android host tests, Android and Desktop builds).
- After the checks no `pilot-token.local` exists, and `androidApp/build` and `desktopApp/build`
  hold no fake token.
- Diff review: the header is added only in `KtorAnswerService.ask` and only when
  `mayCarryPilotToken` holds (https, or http to localhost, 127.0.0.1, [::1], 10.0.2.2);
  `KtorServiceStatusChecker` is untouched. `PilotToken` is not a data class and prints
  `PilotToken(redacted)`. There is no Ktor `Logging` plugin (guard-tested). The malformed-file
  build error is a fixed message. The Desktop `run` block carries no token. `/pilot-token.local`
  is git-ignored. No build script reads `local.properties` for the token. The save command
  validates in-shell (the token is never a process argument), writes through `mktemp`,
  `chmod 600`, and `mv`, and prints neither the token nor its length.

## Deviations accepted

- Android injects `PILOT_TOKEN` through `androidComponents.onVariants` rather than
  `defaultConfig.buildConfigField`. This is lazy, and debug and release both get the value or `null`.
- `shared/build.gradle.kts` declares the guard test's file inputs so a cached result cannot hide
  a regression.
- An extra save-command failure line for an unwritable target: plain language, non-zero exit,
  existing file untouched, documented in the owner guide.

## Revision 2026-11-01: debug-only token (owner decision 5)

**Accepted** after a fresh independent validation with no findings.

- `./scripts/init.sh --feature client_pilot_credentials`, `CI=true ./scripts/init.sh --fast` (9 of 9;
  backend 1533 passed, 4 skipped) and `./scripts/init.sh --verify` all passed.
- **Android:** only the `debug` build type maps the token provider. Every other build type gets a
  constant `PILOT_TOKEN = null` and never reads the file. `check-pilot-token-build.sh` asserts that
  release is `null` with a valid fake present, and that release builds with a malformed fake.
  `PilotTokenGuardTest` pins this.
- **Desktop:** the generated folder is no longer a `main` resource. Only `run` depends on it, and
  `run` appends it to its classpath in `doFirst`, after Compose sets the classpath.
  - The jar and `build/resources/main` hold no token entry or characters.
  - A dry run shows that `jar`, `createDistributable`, `createReleaseDistributable`,
    `runDistributable` and `runRelease` never depend on the token task.
  - An init-script probe confirms the `run` classpath includes the folder. It stops before the JVM
    starts, so no window opens.
- A malformed file fails only the test-build tasks, without echoing its content.
- The docs consistently say test builds only, and the save command now says "next test build".

## Accepted scope and remaining limits

- A token built into a test build can be extracted by whoever holds that build. Release and
  packaged apps never carry it, so they cannot reach a pilot-profile service until a release
  credential path exists. Both points are recorded in
  [`known-limitations.md`](../progress/known-limitations.md) and the risks register.
- No live pilot-profile answer has been observed from an app, because no named command starts
  that profile locally yet (`environment_profiles`).
- Owner walkthrough (2026-11-01): the owner ran the owner-guide steps (empty clipboard, short
  text, real token, then `--mock` and `--desktop` with a question) and reported that all went
  as documented. Individual `Result:` lines were not sent.
