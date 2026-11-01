# client_pilot_credentials — appendix

## Repository research

### Files inspected

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `answerHttpClient` (no logging plugin, `expectSuccess`), `KtorAnswerService(client, baseUrl: () -> String)` and its fixed-URL constructor, and the payload-free failure mapping where the token header goes.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerFailure.kt`: the two payload-free exceptions. 401 and 429 already map to `AnswerServiceErrorException`.
- `androidApp/build.gradle.kts`: `buildConfig = true`, and `ASK_BASE_URL` comes from the `manijeroAskBaseUrl` Gradle property. This is the pattern for `PILOT_TOKEN`. There is no `local.properties` use.
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`: two `KtorAnswerService` branches (test tools vs fixed URL), and both need the token.
- `desktopApp/build.gradle.kts`: no BuildConfig. The `run`-only `manijero.testBuild` block is guarded by `TestBuildGatingGuardTest`, which also forbids any `jvmArgs`.
- `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`: two service branches, mirroring Android.
- `shared/src/jvmMain/kotlin/com/jamarglex/manijero/platform/DesktopAskConfiguration.kt`: the shape for a small jvmMain host-config reader.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/platform/TestBuildGatingGuardTest.kt`: the repo-text guard style (repository root lookup, regex checks) to reuse for `PilotTokenGuardTest`.
- `shared/src/commonTest/.../connection/ServiceStatusCheckerTest.kt`: already asserts that a probe carries no `Authorization` header (line ~135). This must keep passing.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/KtorAnswerServiceTest.kt`: `MockEngine` request-history assertions to extend.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock/MockAnswerServerTest.kt`: `testApplication` plus `answerHttpClient(client.engine)`. This is the in-process server pattern for `FakePilotGuard`.
- `backend/app/pilot_guard.py`: gated paths `{"/ask"}`; 401 plus `www-authenticate: Bearer`; 429 plus `retry-after: 60`; `_bearer_token` takes a case-insensitive `Bearer` scheme and a stripped token.
- `backend/app/pilot_config.py`: stores tokens as SHA-256 digests. `backend/README.md` sets a minimum of 32 characters and has the runbook generate them with `openssl rand -base64 48`, so the client shape is base64/b64token, 32–512 characters.
- `backend/README.md` ("Current gap", around line 385): says no client can present a token. Update it on completion.
- `contracts/openapi.yaml`: documents `401` for the pilot profile and has no `securityScheme`. Left unchanged by design.
- `scripts/init.sh`: `--feature` runs the spec's verify block unchanged, with no per-feature entry needed. `usage()` and the dispatch `case` are where `--pilot-token-save` goes. `run_backend_tests` is used by the verify block.
- `backend/tests/test_local_rag_commands.py`: the `run_init(tmp_path, ..., extra=env)` pattern, with `MANIJERO_*_CLI` overrides, for testing an init.sh mode with fakes.
- `scripts/select-feature.sh`: the role comes from spec existence, so status stays `not_started` at planning.
- `.gitignore`: ignores `local.properties` and has no token entry yet.
- `docs/constraints/hosting-and-pilot.md` and `docs/constraints/operations.md`: the logging/no-token rules and the owner-command rules (Result line, prerequisite checks, no exported variable).
- `docs/owner-guide.md`: section shape (numbered steps, expected `Result:`, "If the result differs").
- `gradle/libs.versions.toml`: `ktor-client-mock` and `ktor-server-test-host` already exist. No new dependency is needed.

### Existing patterns to follow

- Repo-text guard tests in `platform/` and the in-process Ktor `testApplication` for server fakes.
- Owner commands: one plain `Result:` line and a non-zero exit on failure. Tests redirect every path through `MANIJERO_*` env overrides.
- Optional constructor parameters with defaults, so existing call sites and tests stay unchanged.

### Current gaps

- No client code path can attach any header to `/ask`, and there is no client credential type.
- Desktop has no build-time config mechanism, so a generated resource is the first one.
- No named command starts the pilot profile locally, so a live pilot answer from an app cannot be part of this feature's walkthrough.

## Implementation plan

1. Add `/pilot-token.local` to `.gitignore`.
2. Write `PilotTokenTest`, then `PilotToken.kt` (shape check, redacted `toString`, `mayCarryPilotToken`).
3. Extend `KtorAnswerServiceTest` with the header cases, then add the optional `pilotToken` to `KtorAnswerService`.
4. Add `FakePilotGuard.kt` and `PilotProfileClientTest` (scenario 4 table plus the leak assertions from scenario 5).
5. Add `DesktopPilotToken.kt` and `DesktopPilotTokenTest` (resource present, absent, blank, malformed).
6. Android: add the `PILOT_TOKEN` buildConfigField read from the token file or `MANIJERO_PILOT_TOKEN_FILE`, with validation; wire it in `MainActivity`.
7. Desktop: add `generatePilotTokenResource` and the resources `srcDir`; wire it in `main.kt`; leave the `run` block untouched.
8. Add `PilotTokenGuardTest` (gitignore entry, no `local.properties`, no token on Desktop task properties, env, or jvmArgs, no Ktor `Logging` import in client main sources, release and debug both wired).
9. Add `--pilot-token-save` to `init.sh` (dispatched before Python or venv logic) and to `usage()`; add `test_pilot_token_command.py`.
10. Add `scripts/check-pilot-token-build.sh` (fake valid, fake invalid, none, then a final clean regeneration).
11. Update the durable docs listed in the contract, then `PROGRESS.md` and the feature evidence.

## Verification plan

Tests, each named with the behavior it covers:

- `PilotTokenTest`:
  - blank or null gives no token;
  - 31 and 513 characters are refused, and 32 and 512 are accepted;
  - internal space, newline, non-ASCII, or emoji are refused;
  - trailing `=` padding is accepted;
  - `toString` never contains the value;
  - `mayCarryPilotToken` is true for https and for http to `localhost`, `127.0.0.1`, `[::1]`, and `10.0.2.2`; false for http to a LAN IP, a look-alike host (`127.0.0.1.example`), and `localhost.evil`.
- `KtorAnswerServiceTest` (extend):
  - no token gives no `Authorization` header;
  - a token plus https gives exactly one `Bearer` header and an unchanged body;
  - a token plus LAN http gives no header;
  - a provider address switch from loopback to LAN drops the header on the next ask;
  - a 401 response gives `AnswerServiceErrorException`, whose message and stack text lack the token.
- `PilotProfileClientTest` (in-process fake guard):
  - the correct token gives a decoded answer;
  - a missing or wrong token gives a service error;
  - an exceeded allowance (429) gives a service error;
  - `KtorServiceStatusChecker` reports ready without a token;
  - the fake records `Authorization` only on `/ask`.
- `DesktopPilotTokenTest`: a present resource gives a token; an absent, blank, or malformed resource gives none.
- `PilotTokenGuardTest`: the repo-text rules in plan step 8.
- `test_pilot_token_command.py` (fake clipboard script via `MANIJERO_CLIPBOARD_CLI`, temp `MANIJERO_PILOT_TOKEN_FILE`):
  - success writes exactly the trimmed value with mode `0600`;
  - the output lacks the token and its length;
  - a re-run reports the replacement;
  - empty, short, multi-line, or internal-space input exits non-zero and leaves the previous file byte-identical;
  - a missing clipboard tool gives the plain message;
  - the command runs with an empty `MANIJERO_VENV_ROOT`.
- `check-pilot-token-build.sh`: runs the scenarios in the contract's verification note, using `:androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :desktopApp:processResources`.
- `ServiceStatusCheckerTest` and `mock.*` run unchanged to prove the no-token and probe paths.

E2E: no persistent E2E command exists for the client. In-process fakes cover the auth flow, as owner decision 4 requires.

## Evidence to capture

- One line per focused command with its pass result. Use `./scripts/init.sh --feature client_pilot_credentials`.
- `git check-ignore -v pilot-token.local` output, a path line only.
- A statement that no real token was read, printed, or created by an agent. Only fake values in temporary folders were used.
- The owner walkthrough result lines, when the owner has run them. Until then, record that they are pending.

## Feature evidence

Implementer self-verification, 2026-11-01 (JDK 21, macOS):

- `./scripts/init.sh --feature client_pilot_credentials`: focused tier passed (all 4 command lines).
  - `:shared:jvmTest` filtered set: passed; new or extended suites `PilotTokenTest` 8, `KtorAnswerServiceTest` 15 (5 new), `PilotProfileClientTest` 6, `DesktopPilotTokenTest` 3, `PilotTokenGuardTest` 6, 0 failures. `ServiceStatusCheckerTest`, `mock.*`, and `TestBuildGatingGuardTest` unchanged and passing.
  - `--backend-tests -q tests/test_pilot_token_command.py`: 15 passed.
  - `:androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:classes`: passed.
  - `./scripts/check-pilot-token-build.sh`: 3 PASS lines (valid fake reaches debug and release `BuildConfig` and the Desktop resource; invalid fake fails all three tasks with the plain message and no content; no file gives `PILOT_TOKEN = null` and no resource), then `Result: the pilot token build check passed; build outputs hold no fake token.`
- `CI=true ./scripts/init.sh --fast`: all 9 offline checks passed (backend 1533 passed, 4 skipped).
- `CI=true ./scripts/init.sh --verify`: full tier passed (Android host tests, debug APK, Desktop build).
- `./scripts/init.sh --backend-tests -q` rerun after the doc edits: 1533 passed, 4 skipped.
- Git ignore: `.gitignore` lists `/pilot-token.local`, asserted by `PilotTokenGuardTest`. `git check-ignore -v` was not run because the sandbox requires approval for it.
- Tokens: no real token was read, printed, or created by the agent. No `pilot-token.local` exists at the repository root. Only fake values in `mktemp` folders or test temp dirs were used, through `MANIJERO_PILOT_TOKEN_FILE` and `MANIJERO_CLIPBOARD_CLI`.
- Side effect: the first `./scripts/init.sh` run created the missing git-ignored SDK file with `sdk.dir` only. This is the script's existing behavior. The agent never opened it.
- Implementation notes for the validator:
  - Android injects `PILOT_TOKEN` through `androidComponents.onVariants { buildConfigFields.put(...) }` for every variant, not through `defaultConfig.buildConfigField`. The lazy provider reads the file only when `BuildConfig` is generated, so a malformed file fails app builds but not unrelated tasks. The field value is still an input of `generate*BuildConfig`, which AGP requires.
  - `shared/build.gradle.kts` declares the files that `PilotTokenGuardTest` reads as `jvmTest` inputs, so a cached result cannot hide a guard regression.
  - The save command's validation runs in-process, so the token is never a process argument. It also has one extra failure line, `Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.`, for an unwritable target. It is documented in the owner guide.
- Owner walkthrough (manual, spec "Focused verification"): pending, not run by an agent.
- Independent validation, 2026-11-01: `accept`; see [acceptance record](../validations/client_pilot_credentials.md). The orchestrator restored the `--android` column in `usage()` (validator nit; help text only).

## Validator checklist

- [ ] Scenario 1: with no token file, no request has an `Authorization` header, and existing chat, connection, and mock tests are unchanged.
- [ ] Scenarios 2–3: the header goes only on `/ask`, only over https or the four loopback hosts, and is re-evaluated for each question.
- [ ] Scenario 4: the fake mirrors `pilot_guard.py` (gated paths, statuses, headers), and the outcomes match the table.
- [ ] Scenario 5: there is no logging plugin and no token in `toString`, exceptions, state, or UI. A malformed file fails the build without echoing. `.gitignore` covers the file.
- [ ] Scenario 6: the command output matches the table, writes `0600` atomically, and never prints the token or its length.
- [ ] `local.properties`, `.env`, and the real `pilot-token.local` were never read. Only fake tokens appear in tests, logs, and evidence.
- [ ] `TestBuildGatingGuardTest` still passes, the Desktop `run` block is unchanged, and no new dependency was added.
- [ ] The durable docs listed in the contract are updated, including the extractable-token limitation.
- [ ] The focused verification passes through `./scripts/init.sh --feature client_pilot_credentials` as published.
