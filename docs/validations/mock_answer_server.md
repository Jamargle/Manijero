# Validation: `mock_answer_server`

- **Feature:** `mock_answer_server` — Serve contract example answers from a local mock service so the apps run without the Python backend (`testing`, `depends_on: answer_api_contract, platform_ask_wiring`).
- **Spec:** [`docs/specs/mock_answer_server.md`](../specs/mock_answer_server.md); evidence in the [appendix](../archive/specs/mock_answer_server.appendix.md) "Feature evidence".
- **Verdict:** **accept** (2026-11-01), independent validator run.

## Commands that ran

All Gradle runs used `JAVA_HOME` set to the Gradle-provisioned Zulu 21 JDK (this host has no system Java).

- `./scripts/init.sh --feature mock_answer_server` → passed (start, re-start, status, curl, stop, status after stop); port 18765 free afterwards.
- `./scripts/init.sh --fast` → all 9 checks passed; mock tests 21, 0 failures.
- `./scripts/init.sh --verify` → passed (Android host tests, debug APK, Desktop build).

## Independent probes (port 18766)

- Listens on `127.0.0.1` only.
- Two lands → clarification with the request's land IDs in request order; `general` → answered example.
- Non-JSON → 400; unknown key → 422; `GET /ask` and `POST /health` → 404; `/ready` payload exact.
- Log lines hold only method, known path, status, and example file name; planted question and land markers absent.
- A pid file pointing at an unrelated process is treated as stale and that process is not signalled; port released after stop.

## Scope and judgment calls

- No change to `contracts/`, app code, `backend/`, or `knowledge/`; no new Gradle module; Ktor server libraries are `jvmTest`-only, so nothing ships.
- In scope: a mock started from another folder is named and nothing starts (falls under scenario 5's "port taken"). Stricter `/ask` checks (strict JSON → 400, quoted boolean → 422, land ID and municipality length limits) follow `contracts/openapi.yaml` and the backend; scenario 10's list is examples, and error bodies stay generic.
- `docs/owner-guide.md` matches the real messages; ARCHITECTURE, PROGRESS, and known-limitations updated as the spec requires.

## Findings and honest gaps

- **F1 (non-blocking):** M1 (Desktop app) and M2 (Android emulator, proving `10.0.2.2` reaches the loopback bind) were not run in any agent session. The in-memory test decodes all three states through the real `KtorAnswerService`, and app code is unchanged. The owner should run M1/M2 from `docs/owner-guide.md` before relying on scenario 12.
- **F2 (low):** first-run prepare duration not measured (Gradle cache was warm).
- **F3 (low):** `PROGRESS.md` gained a limitations-digest line beyond the one the spec listed; consistent with known-limitations.
