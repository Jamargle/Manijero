# Start, stop, and check the full local RAG service with one command each

## Source metadata

- `id`: local_full_rag_stack · `area`: operations · `depends_on`: local_rag_bootstrap, backend_ask_endpoint (both accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --local-rag-start` to start the real local answer service in the background with hybrid Chroma/RRF retrieval and local Ollama drafting over the artifacts in `~/manijero/local`, `./scripts/init.sh --local-rag-service-status` to see in plain words whether it runs, whether it can answer, and the addresses the apps use, and `./scripts/init.sh --local-rag-stop` to stop it. Re-running start or stop reports the current state.
- Verification: offline tests with fake process, probe, and Ollama ports plus `init.sh` subprocess runs that never start a service (commands in Focused verification); the owner walkthrough in `docs/owner-guide.md` is the manual acceptance check.
- Notes: owner decisions 2026-11-01 — one named command each to start, stop, and check the full local RAG service over the `local_rag_bootstrap` artifacts in `~/manijero/local`; prerequisite checks that name the fix (for example run `--local-rag-setup`, open Ollama); plain-language `Result:` lines; re-running start/stop reports the current state; status prints the address the apps use; mirror the style of `--mock`/`--mock-status`/`--mock-stop` and `--local-rag-*`; downloads nothing; the owner runs the walkthrough personally (guided by the orchestrator), with numbered copy-paste steps in `docs/owner-guide.md` including one missing-prerequisite case and one recovery; automated verification uses fakes only (no real service start, no real Ollama, no agent writes to `~/manijero/local`); focused block reachable via `./scripts/init.sh --feature local_full_rag_stack`. Command names and the loopback-only bind are planner choices (appendix, "Planner decisions").

## Goal

Let the owner run the real local answer service (reviewed knowledge release, hybrid search, local drafting) on this computer for the Desktop app and the Android emulator with three copy-paste commands, without knowing Python, environment variables, or process management, and get an honest plain-language answer to "is it running and can it answer?".

## Non-goals

- Downloading, building, or repairing any artifact (that is `--local-rag-setup`); installing, opening, or quitting Ollama; changing `--local-rag-setup` or `--local-rag-status` behavior.
- Changing the answer service (`backend/app/main.py`, `ask_api.py`, retrieval, generation, release reading), `contracts/`, any pin in `backend/config/`, `knowledge/`, or the settings-file keys.
- The pilot profile, authentication, retention, or Gemini; LAN or physical-device access (bind is loopback only); QA/prod profiles (`environment_profiles`); a container image (`backend_container_image`).
- Monitoring, metrics, or a dashboard (`monitoring_dashboard`); start at login or after a restart; a warm-up question; app end-to-end checks (`local_end_to_end_smoke`); load tests (`local_load_test`).
- Any claim of answer quality, legal coverage, or that a given answer used hybrid ranking or a model draft.

## Job story

When I want to try Manijero with real answers on my computer, I want one command to start the answer service, one to see whether it is working and where the apps should connect, and one to stop it, so I can test the apps without a developer.

## Acceptance Scenarios

### 1. Start when everything is ready

Given setup completed (`--local-rag-status` would print six `OK` lines), Ollama is running with the pinned model, and port 8000 is free · When the owner runs `./scripts/init.sh --local-rag-start` · Then it prints `Checking the local answer tools...`, starts the service in the background bound to `127.0.0.1:8000`, waits until `/health` answers as `manijero-backend` and `/ready` answers ready, prints that it started with hybrid search, knowledge release `<id>`, and the local drafting model, the Desktop address `http://127.0.0.1:8000`, the Android emulator address `http://10.0.2.2:8000`, that these are the apps' default addresses, next steps (`--desktop`, `--android-run`, `--local-rag-stop`), and the log path, then `Result: the local answer service started at http://127.0.0.1:8000.`, exit `0`, and the terminal is free. Closing the Terminal window does not stop the service.

### 2. A prerequisite is missing

Given any of: setup has never run (no `settings.env`), a part `--local-rag-status` would not report `OK` (for example Ollama closed, drafting model missing, knowledge changed since the release), an invalid settings line, a setup currently running, or another start or stop currently running · When start runs · Then before writing anything under the local home or starting any process it prints the same plain line `--local-rag-status` would print for each part that is not `OK` (each naming its fix, for example `Open the Ollama app, then run this command again.` or `Run ./scripts/init.sh --local-rag-setup.`), or the single matching sentence for the never-set-up, settings, setup-running, or start-running case, then `Result: the local answer service did not start. <first fix>`, exit `1`. It never downloads, pulls, or builds.

### 3. The port is in use

Given port 8000 answers as the mock service, as a `manijero-backend` this command did not start (for example `./scripts/init.sh --backend`), or as another program · When start runs · Then it says which, names the one step (`./scripts/init.sh --mock-stop`; Ctrl+C in the `--backend` window; close the other program), starts nothing, writes nothing, exits `1`.

### 4. Start while already running

Given the service started by this command is running · When start runs again · Then it starts nothing, prints the same lines as service status, and ends `Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000.` with exit `0`, or, when a status check is not `OK`, `... already running at <address>, but a check needs attention: do the first step shown above.` with exit `1`.

### 5. Start fails after the process was launched

Given the launched process exits while starting, `/health` does not answer within 60 seconds, `/ready` answers unavailable, or the owner presses Ctrl+C · When start notices it · Then it ends that process, removes the run record, prints one plain sentence (for `/ready` unavailable: run `--local-rag-status` and do its first step) and the log path, then `Result: the local answer service did not start. ...`, exit `1`. Tracebacks and server output are only in the log.

### 6. Service status when running and healthy

Given the service is running · When the owner runs `./scripts/init.sh --local-rag-service-status` · Then it prints that it is running at `http://127.0.0.1:8000` (process id and start time in UTC), three check lines `OK  Answers` (`/ready` ready), `OK  Search` (started with hybrid search and release `<id>`, which is still the published release), `OK  Drafting` (Ollama answers and lists the pinned model with the pinned digest), the two app addresses with the default-address note, the log path, and `Result: the local answer service is running at http://127.0.0.1:8000.`, exit `0`.

### 7. Service status with a problem

Given the service runs but Ollama is closed or holds a different digest, a newer release was published after start, `/ready` is unavailable, or `/health` does not answer · When status runs · Then the matching line starts `PROBLEM` and says what it means in plain words (Ollama closed: answers continue without the drafting model until Ollama is opened; newer release: run `--local-rag-stop` then `--local-rag-start` to use it; not answering: stop and start, and send the log if it repeats), the addresses still print, and the result is `Result: the local answer service is running at <address>, but a check needs attention: do the first step shown above.`, exit `1`.

### 8. Service status when not running

Given no run record, or a record whose process is gone or is not this service (crash, kill, restart, reused pid) · When status runs · Then a leftover record is removed with the line `An earlier local answer service ended without being stopped; its leftover record was cleared.`, it makes no network call, and ends `Result: the local answer service is not running. Start it with ./scripts/init.sh --local-rag-start.`, exit `1`.

### 9. Stop

Given the service is running · When the owner runs `./scripts/init.sh --local-rag-stop` · Then it sends a polite stop, waits up to 10 seconds, ends the process for sure only if it is still verified as this service, removes the run record, and prints `Result: the local answer service has stopped.`, exit `0`. Given it is not running (or the record is stale, which is cleared with the scenario-8 line) · Then `Result: the local answer service was not running, so there was nothing to stop.`, exit `0`. A process that is not this service is never signalled. Ollama keeps running.

### 10. Misuse

Given an extra argument after any of the three commands, or `MANIJERO_LOCAL_RAG_PORT` (tests and developers only) that is not a port number 1–65535 · When it runs · Then it prints one plain sentence, changes nothing, and exits `2`.

### 11. Safety and privacy

Given any run · Then the service runs from `backend/.venv-hybrid` with no reload, bound only to `127.0.0.1`, in the default (non-pilot) profile, with an environment built from an allowlist (no inherited `MANIJERO_*`, so no pilot profile, retention store, or Gemini setting reaches it); no command downloads, pulls, or builds anything; network calls are only loopback (the service port and Ollama); no output, run record, or orchestrator log line contains a question, passage text, land data, or token.

## Technical approach

- **Commands.** `scripts/init.sh` adds `--local-rag-start`, `--local-rag-stop`, `--local-rag-service-status` to the existing early `--local-rag-*` dispatch (before the Android/Java/`local.properties` steps), with the same "run it on its own" misuse check and the same dev-environment link as `--local-rag-status` (no dev environment: start and status print the existing "not set up yet" pair and exit `1`; stop prints the scenario-9 "nothing to stop" result and exits `0`). They run `backend/.venv/bin/python backend/scripts/local_rag.py start|stop|service-status`; `local_rag.py` keeps its exception handling (one sentence plus a log path under `<local home>/logs/`, Ctrl+C sentence per command). `usage` and the `--check` listing gain the three commands.
- **Module.** New `backend/app/local_rag_service.py`: operator-only, stdlib-only at import, never imported by the service, mirrors `local_rag_bootstrap.py` style (fixed English sentences, injected ports, exit `0`/`1`/`2`). It reuses `local_rag_bootstrap` as is: `local_paths`, `read_settings`, `load_pins`, `inspect`, `status_lines`, `lock_is_held`, `RunLog`, `OllamaClient`, `find_model`. Ports (fakes in tests): `Processes` (spawn detached, is-alive, command line via `ps -ww -p <pid> -o command=`, terminate, kill), `ServiceProbe` (`GET /health`, `GET /ready` on `127.0.0.1:<port>` with a no-proxy, no-redirect opener, 2 s timeout), `Clock`/`sleep`, plus the bootstrap `Ports` for inspection.
- **Start order.** (1) Read the run record; running and verified -> scenario 4. (2) No `settings.env` -> scenario 2. (3) Read settings, load pins, `inspect` (all six must be `OK`). (4) Setup lock held -> stop. (5) Port owner by `/health` (`free`, `manijero-mock`, `manijero-backend`, other). (6) Only then take `<home>/.service.lock` (flock), re-check the record, open a new `RunLog("service", …)`, spawn, write the record, wait, verify `/ready`.
- **Launch.** argv: `<repo>/backend/.venv-hybrid/bin/python -m uvicorn app.main:app --app-dir <repo>/backend --host 127.0.0.1 --port <port> --no-access-log`, `cwd` `<repo>/backend`, new session (survives closing Terminal), stdin `/dev/null`, stdout/stderr to the log. Environment: `PATH`, `HOME`, `TMPDIR`, `LANG`, `LC_ALL` (when set) plus exactly `MANIJERO_ACTIVE_CAMPAIGN=<settings>`, `MANIJERO_KNOWLEDGE_RELEASE_ROOT=<home>/knowledge-releases`, `MANIJERO_RETRIEVAL_MODE=hybrid`, `MANIJERO_VECTOR_STORE=<home>/knowledge-releases/releases/<current id>/vector-store` (resolved once at start), `MANIJERO_EMBEDDING_ARTIFACT=<home>/models/bge-m3`, `MANIJERO_GENERATION_PROVIDER=local`, `MANIJERO_LOCAL_MODEL=<record model tag>`.
- **Run record.** `<home>/run/service.json` (mode `0600`, written atomically): `pid`, `port`, `started_at` (UTC), `release_id`, `log`. A record is "running" only when the pid is alive and its command line contains `uvicorn app.main:app`, `--host 127.0.0.1`, and `--port <port>`; anything else is stale (mock precedent). One service per local home; `MANIJERO_LOCAL_RAG_PORT` (default `8000`) is test/developer-only.
- **Status checks.** Answers = `/ready` status; Search = record `release_id` equals `current_release_id(<home>/knowledge-releases)`; Drafting = `OllamaClient.tags()` plus `find_model` and the record digest (Ollama-closed wording from the bootstrap reasons, extended with "answers continue without the drafting model"). Status never inspects the six artifacts and never writes except clearing a stale record. The orchestrator never sends `/ask`.
- **Mock interplay.** `mock_start`'s "port in use by the real local answer service" message in `init.sh` also names `./scripts/init.sh --local-rag-stop`.

## Expected file changes

- `backend/app/local_rag_service.py` — create; start/stop/service-status, run record, ports.
- `backend/scripts/local_rag.py` — modify; add `start`, `stop`, `service-status` choices and their Ctrl+C sentences.
- `scripts/init.sh` — modify; early dispatch of the three modes, `usage`, `--check` listing, mock port-in-use message.
- `backend/tests/test_local_rag_service.py` — create; orchestration with fakes (appendix list).
- `backend/tests/test_local_rag_commands.py` — modify; subprocess cases for the three modes (no service start).
- `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`, `docs/risks-and-open-questions.md` — update; see below.
- Not changed: `backend/app/local_rag_bootstrap.py` (reused; a new public helper only if a private one must be shared), `backend/app/main.py`, `ask_api.py`, `retrieval_backend.py`, `local_generation.py`, `knowledge_release.py`, `backend/config/*`, `knowledge/*`, `contracts/*`, requirements files.

## Visual design impact

UI involved: no. No app screen or Spanish app copy changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — extend the `local_rag_bootstrap.py` bullet: `local_rag_service.py` is the operator-only launcher behind the three commands; it runs the unchanged service from `.venv-hybrid` on loopback with an allowlisted environment and a run record in the local home, and never imports into the service.
- `docs/constraints/operations.md`: update — one MUST: a local start command binds only loopback, runs without reload in the default profile, passes only an allowlisted environment, and starts only when the status check it mirrors is all `OK`; it is not a pilot launcher. Reason: `local_full_rag_stack`.
- `AGENTS.md`: not needed — no workflow or repo-wide rule change.
- `docs/owner-guide.md`: update — sections "Start the local answer service", "Check the local answer service", "Stop the local answer service" (numbered copy-paste steps, expected `Result:` line, an "if you see something else" table), a note to stop and start after a setup that changed something, the mock table row naming `--local-rag-stop`, and "Owner walkthrough: local answer service" with the numbered steps in the appendix verification plan (command, expected `Result:` line, what to report back), including Ollama closed before start (missing prerequisite) and Ollama quit while running then reopened (recovery).
- `backend/README.md`: update — a "Local answer service" subsection under "One-command local setup" (launch argv and environment keys, run record, log, port owner rules, exit codes, test-only `MANIJERO_LOCAL_RAG_PORT`); revise its "Neither command starts the service" sentence.
- `docs/risks-and-open-questions.md`: update — status reports configuration and live probes, not which ranking or draft each answer used (silent BM25/extractive fallback); the first question after start may exceed the 10 s draft budget while Ollama loads the model and fall back to extractive; a publish while running needs a restart for hybrid ranking.
- `PROGRESS.md` "Start and verify" and `docs/progress/known-limitations.md`: update one line each at acceptance (loopback only: Desktop and emulator, no physical device).
- `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

Offline in the shared `backend/.venv`: no service process, no Ollama, no model, no `torch`/`chromadb`, no write outside temporary directories. Subprocess tests pass a temporary `MANIJERO_LOCAL_HOME`, an empty `MANIJERO_VENV_ROOT`, and a free `MANIJERO_LOCAL_RAG_PORT`.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_rag_service.py tests/test_local_rag_commands.py tests/test_local_rag_bootstrap.py tests/test_local_generation.py -q
```
<!-- verify:end -->

The owner walkthrough (real service, real Ollama, real `~/manijero/local`) is run by the owner and recorded by the orchestrator; it is not part of this block.

## Appendix

See [`local_full_rag_stack.appendix.md`](local_full_rag_stack.appendix.md) for research, plan, evidence, and the validator checklist.
