# Serve contract example answers from a local mock service so the apps run without the Python backend

## Source metadata

- `id`: mock_answer_server · `area`: testing · `depends_on`: answer_api_contract, platform_ask_wiring (both accepted) · `status` at planning: not_started
- User-visible behavior: one named command starts a local stand-in answer service that serves the committed contract example responses on `GET /health`, `GET /ready`, and `POST /ask`, prints the address the apps use, and a sibling command stops it. Android (emulator) and Desktop then show every answer state with no Python installed.
- Verification: focused JVM tests for example loading, response selection, and HTTP behavior, plus a script-level start/re-start/status/request/stop smoke on a non-default port (commands in Focused verification).
- Notes, owner decisions (2026-11-01, the user's requirements): build it in Kotlin/JVM with Ktor, so no Python is needed; serve the contract examples for the `/health`, `/ready`, and `/ask` contract; start and stop it with one named command each that prints the address for the apps, following [`docs/constraints/operations.md`](../constraints/operations.md); reuse existing modules and build setup, and add a Gradle module only if the plan shows it is the smallest fit (it does not; see the appendix research).
- Notes, planning findings: `contracts/openapi.yaml` declares only `POST /ask` and has no inline examples. The examples are the validated files in `contracts/examples/`. `/health` and `/ready` exist only in `backend/app/main.py`, so the mock copies those payload shapes. Changing the contract is out of scope.

## Goal

Let a tester, or the owner with no terminal or Python expertise, run the Android emulator and Desktop apps against a predictable local service. One command starts it and one stops it. It answers only with the committed contract examples, chosen by request shape, so the answered, abstained, and land-clarification states can all be reached from the real app.

## Non-goals

- Real answers, retrieval, campaign checks, or anything from `knowledge/`. The mock never generates or changes answer text.
- Changing `contracts/openapi.yaml` or `contracts/examples/`. Adding `/health` and `/ready` to the contract is a separate decision.
- Pilot behavior: bearer tokens, rate limits, body bounds, retention, `401`/`413`/`429`/`503` responses.
- Physical devices, LAN or remote access, QA hosts, containers, or a configurable app address (`local_service_connection` owns address configuration).
- Client app code changes. The apps keep their current default addresses.
- A new Gradle module, shipping the mock in any app or library artifact, or a monitoring dashboard.

## Job story

When I want to try Manijero on Desktop or the Android emulator without setting up the Python answer service, I want to start a stand-in service with one command, so I can see every answer state in the real app and stop it again just as easily.

## Acceptance Scenarios

### 1. Start prints where the apps connect

Given no mock is running and port 8000 is free · When the owner runs `./scripts/init.sh --mock` from the repository root · Then the command:
- prepares the mock (the first run may build for a few minutes and says so) and starts it in the background on `127.0.0.1:8000`;
- waits until `GET /health` answers, then prints the Desktop address `http://127.0.0.1:8000` and the Android emulator address `http://10.0.2.2:8000`, noting that both are the apps' default addresses;
- says the apps will show fixed example answers, not real ones, names `./scripts/init.sh --desktop`, `--android-run`, and `--mock-stop` as next steps, and prints the log path;
- ends with one plain-language result line, exits 0, and returns the terminal.

### 2. Re-running start reports the current state

Given the mock is running · When `./scripts/init.sh --mock` runs again · Then it reports that the mock is already running at the same address, exits 0, and no second process starts.

### 3. Status

Given the mock is running · When `./scripts/init.sh --mock-status` runs · Then it prints that the mock is running with its address and exits 0. Given it is not running · Then it prints that it is not running, names `./scripts/init.sh --mock` as the fix, and exits non-zero.

### 4. Stop

Given the mock is running · When `./scripts/init.sh --mock-stop` runs · Then the mock process ends, the port is free, and one line confirms it stopped (exit 0). Given it is not running · Then the command says so and exits 0. It never stops a process that is not this mock.

### 5. Port already in use

Given port 8000 is taken by the real local service (`/health` reports `manijero-backend`) or by another program · When `--mock` runs · Then nothing starts. The command names which of the two cases it found and the single step that fixes it: stop the local service with Ctrl+C in its window, or close the other program. It exits non-zero.

### 6. Recovery after an unclean end

Given the mock process died without `--mock-stop` (crash, killed, or computer restarted) and its pid file remains · When `--mock` or `--mock-status` runs · Then the stale record is detected and cleared. Start then proceeds normally, and status reports "not running".

### 7. Examples missing or unreadable

Given one of `contracts/examples/response-answered.json`, `response-abstained.json`, or `response-needs-land-clarification.json` is missing or does not decode into the app's `AskResponse` · When `--mock` runs · Then the mock does not start. The command names the file in plain words, prints the log path, and exits non-zero. No partial service runs.

### 8. Health and readiness

Given the mock is running · When a client calls `GET /health` · Then it returns `200` with `{"status":"ok","service":"manijero-mock"}`. When a client calls `GET /ready` · Then it returns `200` with `{"status":"ready","service":"manijero-mock"}`. The shapes match `backend/app/main.py`, and the `service` value says honestly that this is the mock.

### 9. `/ask` serves the matching example

Given the mock is running · When a valid `AskRequest` arrives · Then it returns `200` with the matching example. Every field equals the committed file, except the two substitutions marked here:

| Request `land_context` | Served example | Substitution |
|---|---|---|
| `general` | `response-answered.json` | none |
| `all_active` with exactly 1 land | `response-abstained.json` | none |
| `all_active` with 2 or more lands | `response-needs-land-clarification.json` | `land_ids_to_choose` = the request's land IDs, in request order |
| `selected` | `response-answered.json` | `land_scope` = `selected` |

Both substitutions follow the accepted backend: clarification offers the request's own IDs, and `land_scope` mirrors the request mode. Without them the app could not show the chooser or finish a selected round trip. `retain_for_improvement` never changes the answer.

### 10. Invalid requests

Given the mock is running · When the `/ask` body is not JSON · Then it returns `400`. When the body is JSON but breaks the contract (unknown key, bad enum, empty or over-2000-character question, lands present for `general`, no lands for `all_active` or `selected`, duplicate land IDs) · Then it returns `422`. Both carry a fixed generic `{"detail": ...}` body that echoes no request value.

### 11. No personal data in logs

Given any request · When the mock logs it · Then the log line holds only the method, path, status code, and the served example's file name. The question text, land IDs, municipality, other land attributes, and headers never appear in output or logs.

### 12. The real apps show each state

Given the mock is running · When the Desktop app (`./scripts/init.sh --desktop`) or the Android emulator app (`./scripts/init.sh --android-run`) sends a question · Then:
- with no lands, the answered example appears with its source card;
- with one active land, the abstained message appears;
- with two active lands, the land chooser lists those two lands, and choosing them shows the answered example.

### 13. Local machine only

Given the mock is running · Then it listens only on `127.0.0.1`. The Android emulator reaches it through `10.0.2.2`, and other machines on the network cannot reach it.

## Technical approach

- Location: test-only code in the existing `shared` JVM test source set, package `com.jamarglex.manijero.mock`. It reuses the client's own `AskRequest`, `AskResponse`, and `answerJson` from `shared/src/commonMain/.../chat/AnswerService.kt`, so requests decode exactly as the client sends them. The examples are also proven decodable by the app. No product source set, app host, or shipped artifact gains a server dependency. The appendix weighs this against the alternatives.
- Server: Ktor server CIO, embedded, with plain routing and no CallLogging of bodies. It writes responses as text encoded with `answerJson` and content type `application/json`. Add `ktor-server-core`, `ktor-server-cio`, and `ktor-server-test-host` at the existing `ktor` version, and only in `jvmTest`.
- Examples: read once at startup from the `contracts/examples/` directory passed on the command line, which is the committed files and not a copy. Each file is decoded into `AskResponse`. Startup fails closed on any missing or undecodable file (scenario 7). Request-to-example selection is one pure function (scenario 9). Request validation is a separate pure step (scenario 10).
- Launch: a configuration-cache-safe Gradle task in `shared/build.gradle.kts`, `:shared:prepareMockAnswerServer`, compiles `jvmTest`. It writes the runtime classpath and the path of the Java executable Gradle used to `shared/build/mock-answer-server/`, so the launch never depends on the `java` on PATH.
- Command: `scripts/init.sh` gains `--mock`, `--mock-status`, and `--mock-stop`, listed in `--help` and `--check`. Start checks prerequisites first (`curl`, a free port). It then runs the prepare task with its output going to a log, and launches `java -cp … com.jamarglex.manijero.mock.MockAnswerServerKt --examples <repo>/contracts/examples --host 127.0.0.1 --port <port>` with `nohup`. It waits up to 60 s for `/health`. Pid and log files are per port: `build/mock-answer-server/<port>.pid` and `<port>.log`. Stop checks that the pid's command line contains the mock main class before sending TERM.
- Port: 8000, the apps' default, so the owner types nothing else. `MANIJERO_MOCK_PORT` overrides it for tests and developers only; the owner guide does not mention it.
- Follow [`operations.md`](../constraints/operations.md) "Owner operability" for every message: plain words, a final result line, non-zero exit on failure, and raw output in the log file.

## Expected file changes

- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock/MockAnswerServer.kt` — create; `main`, argument parsing, embedded CIO server, routes, request log line.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock/ContractExamples.kt` — create; load and decode the three response examples, with plain failure naming the file.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock/MockAnswerSelection.kt` — create; request validation and example selection.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock/*Test.kt` — create; tests listed in the appendix.
- `shared/build.gradle.kts` — modify; `jvmTest` server dependencies, the `prepareMockAnswerServer` task, and `contracts/examples` declared as a `jvmTest` input.
- `gradle/libs.versions.toml` — modify; three Ktor server library aliases on the existing `ktor` version.
- `scripts/init.sh` — modify; the three modes, usage text, and `--check` text.
- `docs/owner-guide.md` — create; numbered copy-paste steps for start, status, and stop, with expected results and what to do if they differ.
- `ARCHITECTURE.md`, `PROGRESS.md` "Start and verify", `docs/progress/known-limitations.md` — modify; see below.

## Visual design impact

UI involved: no. The apps render the examples through existing accepted chat states. No copy or layout changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update. Add one bullet naming the test-only mock answer service (shared `jvmTest`, loopback, examples only, never shipped, started by `./scripts/init.sh --mock`), and add it as a consumer in the "Contract map" HTTP row.
- `docs/constraints/operations.md`: not needed. The feature follows its existing rules and adds none. Loopback-only binding and serving only examples are this contract's behavior.
- `AGENTS.md`: not needed; agent workflow and routing are unchanged.
- `docs/owner-guide.md`: create (required by the `operations.md` owner-guide rule; this is the first feature that needs it).
- `PROGRESS.md` "Start and verify": update with one line for the three mock commands.
- `docs/progress/known-limitations.md`: update with one line saying that mock answers are fixed contract examples, not real or legal answers, and run on Desktop and the Android emulator only.
- `contracts/`, `backend/README.md`: not needed, because both are unchanged.

## Focused verification (required)

<!-- verify:start -->
```sh
bash -n scripts/init.sh
./gradlew --console=plain --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.mock.*'
trap 'MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock-stop >/dev/null 2>&1 || true' EXIT
MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock
MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock
MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock-status
curl -fsS http://127.0.0.1:18765/health | grep -q '"service":"manijero-mock"'
curl -fsS http://127.0.0.1:18765/ready | grep -q '"status":"ready"'
curl -fsS -H 'Content-Type: application/json' --data @contracts/examples/ask-request-general.json http://127.0.0.1:18765/ask | grep -q '"status":"answered"'
curl -fsS -H 'Content-Type: application/json' --data @contracts/examples/ask-request-all-lands.json http://127.0.0.1:18765/ask | grep -q '"status":"needs_land_clarification"'
MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock-stop
if MANIJERO_MOCK_PORT=18765 ./scripts/init.sh --mock-status; then echo 'mock still reported running after stop' >&2; exit 1; fi
```
<!-- verify:end -->

## Appendix

See [`mock_answer_server.appendix.md`](../archive/specs/mock_answer_server.appendix.md) for research, plan, evidence, and the validator checklist.
