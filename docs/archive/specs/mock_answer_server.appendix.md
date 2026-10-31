# mock_answer_server — appendix

## Repository research

### Files inspected

- `contracts/openapi.yaml` — declares only `POST /ask` and the `AskRequest`/`AskResponse` schemas. It has no inline examples and no `/health` or `/ready` path.
- `contracts/examples/*.json` — three requests and three responses (answered/general, abstained/all_active, clarification/selected with `land-001`, `land-002`). These are the only contract examples.
- `contracts/validate_examples.py` — Python check of the same examples. It is unchanged and stays in `--fast`.
- `backend/app/main.py` — the `/health` (`status`, `service`) and `/ready` (`ready`/`unavailable`, `service`) payload shapes the mock copies.
- `backend/app/clarification.py`, `backend/app/ask_api.py` — clarification uses the request's own IDs with `land_scope: selected`; otherwise `land_scope` equals the request mode. These are the source of the two substitutions.
- `shared/src/commonMain/.../chat/AnswerService.kt` — `AskRequest`/`AskResponse` DTOs, `answerJson`, `KtorAnswerService` (`expectSuccess`, payload-free errors).
- `shared/src/commonMain/.../ChatHomeState.kt`, `chat/ChatHomeScreen.kt` — the chooser keeps only local lands whose IDs are in `land_ids_to_choose`. Serving the example IDs verbatim would show an empty chooser.
- `shared/src/jvmMain/.../platform/DesktopAskConfiguration.kt`, `shared/src/androidMain/.../platform/AndroidAskConfiguration.kt`, `androidApp/build.gradle.kts` — the default addresses `http://127.0.0.1:8000` (Desktop) and `http://10.0.2.2:8000` (emulator).
- `shared/build.gradle.kts` — KMP `jvm()` target; `jvmTest` already has test-only dependencies and declares file inputs for a guard test; screenshot tests are excluded from `jvmTest`.
- `shared/src/jvmTest/.../chat/KtorAnswerServiceTest.kt` — finds `contracts/examples` by walking parent directories; that pattern can be reused.
- `gradle/libs.versions.toml` — `ktor = 3.1.3` with client artifacts only; no server artifact yet.
- `gradle.properties`, `gradle/gradle-daemon-jvm.properties` — configuration cache on; the daemon JVM is Azul 21.
- `settings.gradle.kts`, `build.gradle.kts`, `desktopApp/build.gradle.kts` — three modules; Desktop ships `shared` plus CIO client.
- `scripts/init.sh` — mode dispatch, `--backend` foreground launcher (binds `0.0.0.0`), `run_feature` executes the verify block with `bash -euo pipefail`, compact logs in `build/verify-logs/`.
- `docs/constraints/operations.md` — owner operability rules; `docs/owner-guide.md` does not exist yet.
- `ARCHITECTURE.md`, `CONSTRAINTS.md`, `PROGRESS.md` "Current state" — boundaries and status; `docs/archive/MasterPlanV3.md` row 0.8 is the origin of the "examples from `openapi.yaml`" wording.

### Location decision (module or source set)

| Option | Cost | Verdict |
|---|---|---|
| New Gradle module `:mockAnswerServer` | New build file, a settings entry, and a module the owner asked to avoid; it would still depend on `:shared` for the DTOs | Rejected: not the smallest |
| `desktopApp` second main class | Puts a server dependency into the shipped Desktop distribution and mixes test tooling with a product host | Rejected |
| `shared/src/jvmMain` | Ships a server inside the product library for every JVM consumer | Rejected |
| `shared/src/jvmTest` (chosen) | Three test-only dependencies plus one Gradle task; reuses the client DTOs, the JVM toolchain, and the existing examples-path test pattern; no product artifact changes | Smallest fit |

The cost of the chosen option: `prepareMockAnswerServer` compiles the whole `jvmTest` source set, including the screenshot test classes. `--fast` already pays for that compile, so the mock adds no new toolchain.

### Existing patterns to follow

- One plain line per check and a log path on failure (`run_offline_checks`, `run_feature`). Mode dispatch lives in the final `case`.
- `jvmTest` file inputs are declared with `inputs.files(...).withPathSensitivity(RELATIVE)` (backup guard). Do the same for `contracts/examples`.
- Tests use `kotlin.test` with fakes and no mocks (`android-unit-testing` skill). Ktor `testApplication` keeps the HTTP tests in memory.

### Current gaps

- The contract has no `/health` or `/ready` schema. The mock mirrors the backend code, and adding them to the contract is a follow-up decision (not a blocker).
- No persistent E2E command exists. The verify block's script smoke and the manual app checks cover the flow.
- The Android emulator reaching a `127.0.0.1`-bound host server through `10.0.2.2` is standard emulator behavior, but nobody has checked it in this repo. Manual check M2 confirms it.

## Implementation plan

1. Add `ktor-server-core`, `ktor-server-cio`, and `ktor-server-test-host` aliases (`version.ref = "ktor"`) to `libs.versions.toml`, and add them to `jvmTest.dependencies` only.
2. `ContractExamples.kt`: given a directory, decode the three response files with `answerJson` into `AskResponse`. On failure, throw an error that names the file and nothing else.
3. `MockAnswerSelection.kt`: write `validate(body: String)` returning `400`, `422`, or `AskRequest`, using the contract rules from scenario 10. Write `select(request, examples)` returning the served file name and `AskResponse`, with the scenario 9 table and its two substitutions.
4. `MockAnswerServer.kt`: write `mockAnswerModule(examples, log: (String) -> Unit)` with the three routes and generic error bodies. `main` parses `--examples`, `--host`, and `--port`, loads the examples (printing a plain error and exiting 1 on failure), starts CIO, and prints one "listening" line.
5. Tests (see Verification plan), all green under `:shared:jvmTest --tests 'com.jamarglex.manijero.mock.*'`.
6. `shared/build.gradle.kts`: register `prepareMockAnswerServer`, which depends on the `jvmTest` compilation and writes `classpath.txt` and `java.txt` under `build/mock-answer-server/`. Keep it configuration-cache-safe by resolving `FileCollection`/`Provider` values at configuration time and accessing no `project` at execution. Also add `contracts/examples` as a `jvmTest` input.
7. `scripts/init.sh`: add `mock_start`, `mock_status`, and `mock_stop` using the per-port pid and log files, a `curl` prerequisite, a port probe that tells the backend apart from another program, stale-pid cleanup, a stop check of the pid's command line, and a 60 s readiness wait. Add usage and `--check` lines.
8. Run the focused verification block through `./scripts/init.sh --feature mock_answer_server`, then `./scripts/init.sh --fast`.
9. Write `docs/owner-guide.md` (start, status, stop; expected output; what to do if the port is busy or start fails).
10. Update `ARCHITECTURE.md`, `PROGRESS.md` "Start and verify", and `docs/progress/known-limitations.md` as the contract says.
11. Run the owner walkthrough (M1–M4) exactly as the guide is written, and record the results below.

## Verification plan

- `ContractExamplesTest` — loads all three committed files; a missing file and a file with an unknown key each fail with a message naming that file.
- `MockAnswerSelectionTest` — each row of the scenario 9 table. Clarification IDs equal request IDs in order, even when they differ from the example's IDs. `selected` overrides `land_scope`. `retain_for_improvement: true` changes nothing. Each scenario 10 case maps to `422` and non-JSON maps to `400`. Error bodies contain none of the request values, including Unicode and emoji question text.
- `MockAnswerServerTest` (`testApplication`) — `/health` and `/ready` bodies are exact. `/ask` returns `200` with JSON content type. Wrong methods on `/ask`, `/health`, and `/ready` do not return `200`. A `KtorAnswerService` built on the test client (`expectSuccess`, `answerJson`) decodes all three states. The captured log lines contain no question text, land ID, or municipality.
- Focused block via `./scripts/init.sh --feature mock_answer_server` — exits 0; covers start, idempotent restart, status, real HTTP, stop, and status after stop.
- `./scripts/init.sh --fast` — still passes; the new tests run inside `:shared:jvmTest`.
- M1 (Desktop): `./scripts/init.sh --mock`, then `./scripts/init.sh --desktop`. Expect the answered card with no lands, abstained with one land, and the chooser then answered with two lands.
- M2 (Android emulator): the same three states via `./scripts/init.sh --android-run`, which proves `10.0.2.2` reaches the loopback-bound mock.
- M3 (missing prerequisite): with `./scripts/init.sh --backend` running, `--mock` reports the local service on port 8000, starts nothing, and exits non-zero.
- M4 (recovery): kill the mock java process by pid, then `--mock-status` reports not running and `--mock` starts cleanly. Also, with an examples file temporarily renamed, `--mock` names it and exits non-zero (restore the file afterwards).
- E2E: no persistent E2E harness exists. The in-memory HTTP tests, the real-process script smoke, and M1/M2 cover the flow, and the app code is unchanged.

## Evidence to capture

- Focused tier result line and test count; `--fast` result line.
- One line each for M1–M4, including the exact message printed in M3 and M4.
- First-run prepare duration, and the start-to-ready time on a warm run.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer (agent host has no system JDK, so every Gradle run used `JAVA_HOME` set to the Gradle-provisioned Zulu 21.0.11 in `~/.gradle/jdks`; nothing downloaded besides the three Ktor 3.1.3 server artifacts).

- `./gradlew --console=plain --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.mock.*'` → exit 0; 21 tests (ContractExamplesTest 4, MockAnswerSelectionTest 10, MockAnswerServerTest 7), 0 failures.
- `./scripts/init.sh --feature mock_answer_server` → exit 0, "Focused tier passed"; port 18765 free afterwards (`lsof`).
- `./scripts/init.sh --fast` → exit 0, "All 9 offline checks passed"; `:shared:jvmTest` 382 tests, 0 failures; backend 1346 passed, 2 skipped.
- `./scripts/init.sh --verify` → exit 0, "Full tier passed" (Android host tests, debug APK, Desktop build).
- Script smoke, port 18765: double `--mock-stop` → second says "was not running, so there was nothing to stop", exit 0; `--mock-status` when stopped → exit 1 naming `./scripts/init.sh --mock`; `MANIJERO_MOCK_PORT=abc` → plain message, exit 2.
- Bind check: `lsof` shows the mock listening on `127.0.0.1:<port>` only.
- Request log lines seen in `build/mock-answer-server/18765.log`: `mock-answer-server POST /ask 200 response-needs-land-clarification.json`, `... POST /ask 422 -`; no question or land values.
- Non-JSON body `xx` → `400` (bare words are rejected even though the kotlinx tree parser tolerates them); quoted `"true"` for `retain_for_improvement` → `422`, matching the backend's `StrictBool`.
- M3 (missing prerequisite, real backend): Uvicorn `app.main:app` on `127.0.0.1:8000`, then `--mock` → "Port 8000 is in use by the real local answer service (./scripts/init.sh --backend)." plus "Result: ... Stop the local answer service with Ctrl+C in its window, then run ./scripts/init.sh --mock again.", exit 1, nothing started. Another program (`python3 -m http.server`) → "Port 18765 is in use by another program.", exit 1. A mock started outside this folder's pid record → names "a mock answer service started from a different folder", exit 1.
- M4 (recovery): `kill -9` of the mock pid, then `--mock-status` → "An earlier mock answer service ended without being stopped; its leftover record was cleared." and not running, exit 1; `--mock` then started cleanly, exit 0. `response-abstained.json` temporarily moved away → "Mock answer service cannot start: the example file contracts/examples/response-abstained.json is missing.", log path, exit 1; file restored, `git status contracts` clean.
- Pid guard: pid file pointing at an unrelated `sleep` process → `--mock-stop` treats it as a stale record, does not signal it (process still alive).
- Default port: `--mock` on 8000 printed both default addresses and the "nothing needs changing in the apps" note; warm start-to-ready 1 s; a `selected` `/ask` returned the answered example; `--mock-stop` → stopped, exit 0. First-run prepare duration not measured (the Gradle cache was already warm from the test runs).
- M1 (Desktop app) and M2 (Android emulator app): not run; this agent session cannot operate the app windows or an emulator. The app client path is covered in-memory by `MockAnswerServerTest` (`KtorAnswerService` decodes all three states, clarification IDs mirror the request). The validator or owner must run M1/M2 from `docs/owner-guide.md`.

2026-11-01, validator: `--feature`, `--fast`, and `--verify` reran green; independent probes on port 18766 (loopback bind, clarification IDs in request order, 400/422/404 cases, planted markers absent from the log, unrelated pid not signalled) passed. Verdict accept; M1/M2 still unrun. Record: [`docs/validations/mock_answer_server.md`](../../validations/mock_answer_server.md).

## Validator checklist

- [ ] Scope matches the contract. No contract, example, app, or backend source changed; no new Gradle module; server dependencies only in `jvmTest`.
- [ ] Scenarios 1–13 pass, with evidence (tests for 7–11, script smoke for 1–4, M1–M4 for 5, 6, 12, 13).
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature mock_answer_server` and leaves no process running.
- [ ] `/ask` field values equal the committed examples apart from the two documented substitutions.
- [ ] Logs and error bodies contain no question text or land data. The bind is `127.0.0.1` only.
- [ ] Every command message is plain-language with a final result line and correct exit code ([`operations.md`](../../constraints/operations.md)). The owner walkthrough was run from the owner guide as written.
- [ ] `--mock-stop` cannot kill a process that is not the mock (pid command-line check).
- [ ] Durable documentation impact followed; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
