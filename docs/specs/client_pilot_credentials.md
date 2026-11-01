# Feature Spec: `client_pilot_credentials`

## Source metadata

- `id`: `client_pilot_credentials` · `area`: client · `depends_on`: `platform_ask_wiring`, `hosted_pilot_operations`, `local_service_connection` (all accepted) · `status` at planning: `not_started`; reopened 2026-11-01 (`in_progress`) for decision 5
- User-visible behavior: when the owner has saved a pilot bearer token with one command, the next test builds (Android debug, Desktop `run`) send it on each question (`POST /ask`), so a pilot-profile service answers them. Release and packaged builds never carry it. Testers never see or type it. With no token saved, builds and answers behave exactly as today against the mock and local RAG services.
- Verification: focused shared transport, redaction, and guard tests; an in-process fake of the pilot profile's `/ask` gate; a pytest for the owner save command; host compiles; and a build-injection check with a fake token file. No running service, device, or emulator. Commands are in Focused verification.
- Notes: owner decisions recorded 2026-11-01:
  1. The pilot bearer token reaches Android and Desktop as a local, git-ignored build-time setting. Testers never type it; no in-app token entry screen or on-device token storage UI.
  2. The setting must NOT live in `local.properties` (agents are forbidden from reading or modifying it). Choose a dedicated git-ignored source (e.g. a git-ignored file, environment variable, or Gradle property), documented as one copy-paste step in `docs/owner-guide.md`. Agents never read or print a real token; tests use fake tokens only.
  3. The token must never appear in logs, crash text, UI, or committed files, consistent with [`docs/constraints/hosting-and-pilot.md`](../constraints/hosting-and-pilot.md). With no token configured, builds still work against the local unauthenticated services (mock and local RAG) exactly as today.
  4. "Test them against the local pilot profile": automated verification must not need a running service, real device, or emulator; use fakes/in-process servers. Any real-service check belongs to the owner walkthrough.
  5. (2026-11-01) Only Android DEBUG builds may carry the pilot token; release builds must never carry it, even when the token file exists. Desktop is unchanged unless the same release/debug distinction exists there.
- Desktop answer to decision 5 (planner, from repository evidence): the same distinction exists. [ARCHITECTURE.md](../../ARCHITECTURE.md) "Answer service boundary" and [`local_service_connection`](local_service_connection.md) already pair Android `src/debug` with the Desktop Gradle `run` task (`manijero.testBuild`, `./scripts/init.sh --desktop`) as the test build, and Android `src/release` with packaged Desktop apps (`createDistributable`, `package*`, `runDistributable`, `runRelease`, `packageRelease*`) as release; `TestBuildGatingGuardTest` enforces it. So only the Desktop `run` task carries the token; every packaged or release Desktop output never does, even when the file exists.

## Goal

The owner copies the pilot token they were given and runs one command. The test builds they make next (Android debug, Desktop `run`) then send that token to the pilot-profile service, so pilot `/ask` requests are no longer refused. Release and packaged apps never contain it. No tester ever handles the token, and nothing shows, logs, or commits it.

## Non-goals

- Any in-app token entry, display, status, or on-device token storage; any change to the `Conexión` screen.
- Issuing, generating, rotating, or revoking server-side credentials (`pilot_ops.py upsert-client` stays as is), or generating the client token for an environment (`environment_profiles`).
- Per-environment builds or flavours (`client_environment_builds`), signing, or distribution (`private_pilot_distribution`, on hold).
- New user-facing copy for 401/429: those stay the accepted generic service-error notice.
- Backend, `contracts/openapi.yaml` (no `securityScheme` added), or mock-server changes. A token on `/health` or `/ready`.
- A command that removes or shows the saved token. iOS.

## Job story

When I prepare a test build for the pilot service, I want to copy the token once and run one command, so the apps I build can ask questions without testers ever typing a secret.

## Acceptance scenarios

### 1. No token saved: nothing changes

Given no `pilot-token.local` file (and no `MANIJERO_PILOT_TOKEN_FILE` override) · When Android (debug and release) and Desktop are built and a question is sent · Then the build succeeds, no request carries an `Authorization` header, the mock and local RAG services answer as today, and every existing test passes unchanged.

### 2. Token saved: every eligible question from a test build carries it

Given a valid token file at build time and an Android debug build or the Desktop `run` task · When the app sends `POST /ask` to an address that is `https://`, or `http://` to `localhost`, `127.0.0.1`, `[::1]`, or `10.0.2.2` · Then the request carries exactly one header `Authorization: Bearer <token>` and is otherwise byte-identical to today's request. This applies to the build default address and to a `Conexión` address in test builds, which is read again for each question.
`GET /health` and `GET /ready` probes never carry the header.

### 2a. Release and packaged builds never carry it

Given a valid (or a malformed) token file exists at build time · When an Android release variant or any packaged or release Desktop output (`jar`, `createDistributable`, `package*`, `runDistributable`, `runRelease`, `packageRelease*`) is built · Then the build succeeds without reading the file, release `BuildConfig.PILOT_TOKEN` is the literal `null` (the field stays declared so `src/main` compiles), no Desktop jar or app image contains `manijero/pilot-token.txt` or any token characters, and no question from those builds carries an `Authorization` header.

### 3. Never over cleartext to another host

Given a token is built in and the address in use is `http://` to any other host (for example a LAN address set in `Conexión`) · When a question is sent · Then the request carries no `Authorization` header. A pilot-profile service then refuses it, and the app shows the existing service-error notice.

### 4. Behavior against the local pilot profile (in-process fake)

The fake mirrors `backend/app/pilot_guard.py`: only `/ask` is gated; `401` with `WWW-Authenticate: Bearer` for a missing or unknown token; `429` with `Retry-After: 60` past the allowance.

| Client build | Result in the app |
|---|---|
| Correct token | The answer is decoded and shown as today |
| No token, or a different token | `401`, shown as the existing service-error notice (`RequestFailure.SERVICE_ERROR`) |
| Correct token, allowance exceeded | `429`, the same service-error notice |
| Any build, `Comprobar` in `Conexión` | `/health` and `/ready` succeed without a token |

### 5. The token never leaks

- `PilotToken.toString()` and every failure exception's message, `toString()`, and stack text contain no token characters.
- Chat state, UI strings, and the payload-free failure signals carry no token. No Ktor `Logging` plugin is installed in any client source set.
- A malformed token file fails the test build (Android debug `BuildConfig`, Desktop `generatePilotTokenResource` before `run`) with `pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again.` The message never contains the file's content. Release builds never read the file, so they are unaffected (scenario 2a).
- `pilot-token.local` is git-ignored. No build script reads `local.properties` for the token, and the token is never a JVM system property, environment entry, or `jvmArgs` value on any Desktop task.

### 6. Owner saves the token with one command

Given the owner copied the token · When they run `./scripts/init.sh --pilot-token-save` · Then the command reads the macOS clipboard and trims surrounding whitespace and one trailing line break. It writes `pilot-token.local` at the repository root atomically with mode `0600` and ends with `Result: the pilot token is saved. The next test build will send it.` (or `... saved; it replaced the previous one. ...` on a re-run). It never prints the token or its length.

Each failure exits non-zero, writes nothing, and leaves any existing file untouched:

| Condition | Result line |
|---|---|
| Clipboard empty | `Result: the clipboard is empty. Copy the pilot token first, then run this command again.` |
| Not a token: under 32 or over 512 characters, internal whitespace or line breaks, or characters outside `A–Z a–z 0–9 - . _ ~ + /` with optional trailing `=` | `Result: the clipboard does not hold a pilot token. Copy the whole token again, then run this command again.` |
| No clipboard tool (not macOS) | `Result: this command could not read the clipboard; it needs a Mac. Ask the developer for help.` |

The command needs no Python and no virtualenv.

## Technical approach

- **Token type (commonMain `chat/PilotToken.kt`):** `class PilotToken private constructor(...)` (not a data class) with `companion fun fromBuildSetting(raw: String?): PilotToken?`. It returns `null` for null or blank input and for any value outside the scenario 6 shape, so a tampered build sends nothing. `toString()` returns `PilotToken(redacted)`. A pure `mayCarryPilotToken(url: Url): Boolean` implements scenarios 2 and 3.
- **Transport:** `KtorAnswerService` gains an optional `pilotToken: PilotToken? = null` on both constructors. On each `ask` it resolves the URL once and adds `HttpHeaders.Authorization` = `Bearer <value>` only when the token is non-null and `mayCarryPilotToken` holds. The existing failure mapping is unchanged: 401 and 429 are `ResponseException`, which becomes `AnswerServiceErrorException`. `KtorServiceStatusChecker` is untouched.
- **Token source:** the single git-ignored file `<repo root>/pilot-token.local`, holding one line. `MANIJERO_PILOT_TOKEN_FILE` overrides the path, read by Gradle through `providers.environmentVariable` and by the save command, so tests and checks never touch the owner's real file. Both host build scripts validate the content, only for test builds, with the scenario 6 shape and fail on a mismatch without echoing it. The token value is never a Gradle task input property, log line, or exception message.
- **Android injection:** `androidApp/build.gradle.kts` keeps `androidComponents.onVariants { buildConfigFields.put("PILOT_TOKEN", …) }` for every variant so `src/main` compiles, but only the `debug` build type gets the lazy file-backed provider (quoted value, or `null` without a file). Every other build type gets a constant `BuildConfigField("String", "null", null)` that never touches the file provider, so the token is neither read nor a `generateReleaseBuildConfig` input. `MainActivity` is unchanged: `PilotToken.fromBuildSetting(BuildConfig.PILOT_TOKEN)` yields `null` in release. Choosing environments per build stays `client_environment_builds`.
- **Desktop injection:** `desktopApp/build.gradle.kts` registers `generatePilotTokenResource`. It declares the file through `inputs.files(...)` (missing allowed), reads it inside the action, and writes `manijero/pilot-token.txt` into `build/generated/pilotToken/`, or leaves the folder empty. Revision: that folder is no longer a `sourceSets.main` resource. It is appended only to the `run` task's classpath (`classpath(generatePilotTokenResource)`) inside the existing lazy `withType<JavaExec>().matching { it.name == "run" }` configuration, so `processResources`, `jar`, and every packaging or release task never see it. It must not become a dependency, configuration, or `compose.desktop.application` input. The implementer confirms that Compose's own `run` classpath setup does not overwrite the appended entry (for example by checking the resolved classpath in a throwaway local run, not committed). Shared jvmMain `platform/DesktopPilotToken.kt` and `main.kt` are unchanged. The `run` block still sets only `manijero.testBuild` as a system property, as `TestBuildGatingGuardTest` requires.
- **Save command:** `scripts/init.sh --pilot-token-save` is dispatched before any Python or virtualenv step. It reads `${MANIJERO_CLIPBOARD_CLI:-pbpaste}`, validates the value, and writes it through `mktemp` in the target folder, `chmod 600`, and `mv`. It follows [operations.md](../constraints/operations.md) "Owner operability". It is added to `usage()`.
- **Boundaries:** [ARCHITECTURE.md](../../ARCHITECTURE.md) "Answer service boundary". The token is a per-client, revocable credential. Anyone holding a built app can extract it, so it gates access and is not secret from the device holder. This is recorded as a limitation, not solved here.

## Expected file changes

Revision 2026-11-01 delta (the rest below is already implemented): modify `androidApp/build.gradle.kts` (debug-only provider), `desktopApp/build.gradle.kts` (run-only classpath), `scripts/init.sh` (two `Result:` lines), `scripts/check-pilot-token-build.sh`, `shared/src/jvmTest/.../platform/PilotTokenGuardTest.kt`, `backend/tests/test_pilot_token_command.py` (expected lines), and the durable docs below. No commonMain, jvmMain, `MainActivity`, or `main.kt` change.

- Create `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/PilotToken.kt`; modify `chat/AnswerService.kt` (add the optional token and the header).
- Create `shared/src/jvmMain/kotlin/com/jamarglex/manijero/platform/DesktopPilotToken.kt`.
- Modify `androidApp/build.gradle.kts`, `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`, `desktopApp/build.gradle.kts`, and `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`.
- Modify `scripts/init.sh` (`--pilot-token-save`, usage); create `scripts/check-pilot-token-build.sh` (build-injection check with fake files); modify `.gitignore` (`/pilot-token.local`).
- Tests:
  - commonTest `chat/PilotTokenTest`,
  - jvmTest `chat/KtorAnswerServiceTest` (extend), `chat/PilotProfileClientTest` with `chat/FakePilotGuard.kt` (ktor test host), `platform/DesktopPilotTokenTest`, `platform/PilotTokenGuardTest`,
  - `backend/tests/test_pilot_token_command.py`.
- Durable docs as listed below.

## Visual design impact

UI involved: no. No screen, copy, or baseline changes. Failures reuse the accepted service-error notice.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update "Answer service boundary" with the build-time token source, per-host injection, `/ask`-only header, and the https-or-loopback rule.
- `docs/constraints/hosting-and-pilot.md`: add one MUST/MUST NOT rule. A client token comes only from the git-ignored build setting. It is sent only on `/ask` over https or loopback, and never shown, logged, committed, or put on probes. Reason: this spec.
- `docs/owner-guide.md`: add "Give the apps the pilot token": copy the token, run `./scripts/init.sh --pilot-token-save`, the expected `Result:` line, each failure line with its fix, and that a re-run replaces the token.
- `backend/README.md`: update the "Current gap" bullet under credential rotation. Clients can now send the token, and it points to the owner-guide step.
- `AGENTS.md`: update "Operating rules" with one clause: agents never read, print, or modify `pilot-token.local`, and tests use fake tokens through `MANIJERO_PILOT_TOKEN_FILE`.
- `docs/progress/known-limitations.md` and `docs/risks-and-open-questions.md`: add that a built-in token is extractable from a built app, and that no live pilot-profile answer has been observed from an app.
- Revision 2026-11-01 (decision 5), update each in place, no new sections:
  - `ARCHITECTURE.md` pilot-token paragraph: Android `BuildConfig.PILOT_TOKEN` is file-backed only for `debug` and `null` for release; the Desktop resource folder is on the `run` task's classpath only, never in `jar` or any packaged/release output.
  - `docs/constraints/hosting-and-pilot.md` token rule: add "MUST NOT be built into an Android release variant or a packaged/release Desktop output, even when the file exists; only Android debug and the Desktop `run` task may carry it". Reason: this spec, decision 5.
  - `docs/owner-guide.md` "Give the apps the pilot token": test builds only (`./scripts/init.sh --android`, `--desktop`), release or packaged apps never carry it; update the two quoted `Result:` lines.
  - `docs/progress/known-limitations.md` (entry at "Android and Desktop builds can carry a pilot bearer token") and the matching `docs/risks-and-open-questions.md` row: only test builds carry it, so a release or packaged app cannot reach a pilot-profile service until a release credential path exists (`client_environment_builds` or a later decision). The extractability note stays for test builds.
  - `backend/README.md` "Client token" bullet: Android debug and Desktop `run` builds send it; release and packaged builds never do.
  - `AGENTS.md`: not needed (the agent rule is unchanged).
- `docs/constraints/operations.md`, `DESIGN.md`, `CONTEXT.md`, and `contracts/`: not needed. The command follows the existing rules, there is no UI, there are no new domain terms, and the wire contract is unchanged.

## Focused verification (required)

<!-- verify:start -->
```sh
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.chat.*' --tests 'com.jamarglex.manijero.platform.*' --tests 'com.jamarglex.manijero.connection.ServiceStatusCheckerTest' --tests 'com.jamarglex.manijero.mock.*'
./scripts/init.sh --backend-tests -q tests/test_pilot_token_command.py
./gradlew --quiet :androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:classes
./scripts/check-pilot-token-build.sh
```
<!-- verify:end -->

`check-pilot-token-build.sh` uses only fake tokens in a `mktemp -d` folder via `MANIJERO_PILOT_TOKEN_FILE`, over `:androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :desktopApp:generatePilotTokenResource :desktopApp:jar`. It asserts that:

- a valid fake file reaches the Android debug `BuildConfig` and the Desktop generated folder;
- with that same valid fake present, the release `BuildConfig` has `PILOT_TOKEN = null` and no fake characters, `desktopApp/build/resources/main` has no `manijero/pilot-token.txt`, and the Desktop jar has no such entry and no fake characters in its extracted content (scenario 2a);
- an invalid fake fails the debug `BuildConfig` and `generatePilotTokenResource` with the plain message and without its content, while the release `BuildConfig` and the jar still build with `null` and no resource;
- no file yields `PILOT_TOKEN = null` in both variants and no Desktop resource.

The jar is the input of every packaged and release Desktop task, and `PilotTokenGuardTest` keeps the folder off every other path, so `createDistributable` is not rebuilt here. The script ends by regenerating without the override, so `build/` holds no fake. It prints no token.

Manual (owner walkthrough, not run by the harness): follow the new owner-guide section with an empty clipboard (missing prerequisite), then a short text (recovery), then the token. Then `./scripts/init.sh --mock` and `./scripts/init.sh --desktop`: a question still gets its mock answer. A live answer from a pilot-profile service is observed only when such a service exists. No named command starts one locally yet (`environment_profiles`).

## Appendix

See [`client_pilot_credentials.appendix.md`](client_pilot_credentials.appendix.md) for research, plan, evidence, and the validator checklist.
