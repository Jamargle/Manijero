# local_full_rag_stack — appendix

## Repository research

### Files inspected

- `docs/constraints/operations.md` — owner-operability MUSTs: one named command, prerequisites before any change, one `Result:` line with non-zero exit on failure, idempotent re-runs, owner guide, walkthrough with a missing-prerequisite case and a recovery.
- `docs/constraints/hosting-and-pilot.md` — the pilot launcher rule (`serve_pilot.py`, no reload, loopback origin); `--backend` is a dev path with reload and `0.0.0.0`. This feature is neither: a loopback, no-reload, default-profile local launcher.
- `docs/constraints/lands.md` — local drafting only via the loopback `OLLAMA_BASE_URL` with the pinned digest, on only when both env keys match; automated tests must not need Ollama.
- `scripts/init.sh` — early `--local-rag-setup|--local-rag-status` dispatch (misuse exit 2, dev-env link with `python-env.sh dev --if-present`); `--backend` (reload, `0.0.0.0`); mock section: per-port pid record, pid verified by `ps -ww -p <pid> -o command=`, port owner by `/health` service name, TERM then KILL after 10 s, stale-record line, app addresses with the default note.
- `backend/scripts/local_rag.py` — entry point; `BootstrapError`/Ctrl+C/unexpected-exception handling with a `RunLog` traceback file.
- `backend/app/local_rag_bootstrap.py` — `LocalPaths`/`local_paths` (documented for reuse by this feature), `read_settings` (allowlisted, never sourced), `load_pins`, `inspect` (six parts incl. Ollama state), `status_lines`, `REASONS`, `lock_is_held`, `RunLog`, `OllamaClient`, `GitCheckout`, `find_model`, `Context.hybrid_python`.
- `backend/app/retrieval_backend.py` — hybrid needs `MANIJERO_RETRIEVAL_MODE=hybrid`, `MANIJERO_VECTOR_STORE`, `MANIJERO_EMBEDDING_ARTIFACT`; loads lazily on first request; any failure falls back to BM25.
- `backend/app/local_generation.py` — `resolve_startup_generation` / `resolve_local_provider(env, …)`; `MANIJERO_LOCAL_MODEL` must equal the record `model`; per-draft fallback to extractive on transport errors.
- `backend/app/main.py` — `/health` returns `service: manijero-backend`; `/ready` 200/503; operational logging only in the pilot profile, so the service exposes no "active ranking/provider" signal.
- `backend/app/ask_api.py` — `MANIJERO_KNOWLEDGE_RELEASE_ROOT` makes each request read the verified `current` release; `MANIJERO_ACTIVE_CAMPAIGN` must be four digits.
- `backend/app/knowledge_release.py` — `RELEASES_DIR`, `CURRENT_LINK`, `VECTOR_STORE_DIR`, `current_release_id`.
- `backend/README.md` "Hybrid retrieval … Lifecycle" step 5, "Local open-weight drafting", "Publish, serve, and roll back", "Optional hybrid artifacts", "One-command local setup" — the manual env recipe this feature automates; the hybrid backend loads its store once per process (stale after a publish until restart); first hybrid request pays 2.7–2.8 s.
- `backend/tests/test_local_rag_commands.py` — subprocess pattern: temporary `MANIJERO_LOCAL_HOME`, empty `MANIJERO_VENV_ROOT`, skip without `backend/.venv`.
- `docs/owner-guide.md` — existing mock and local-tools sections and table style; the mock "Port 8000 is in use by the real local answer service" row.
- `docs/specs/local_rag_bootstrap.md` + appendix — accepted contract shape, walkthrough record format, and the harness note that `&` jobs ignore SIGINT.
- `ARCHITECTURE.md` (component bullets), `PROGRESS.md` "Start and verify", `feature_list.json` (dependents `backend_container_image`, `local_end_to_end_smoke`, `environment_profiles`, `local_load_test`, `monitoring_dashboard`).
- Not inspected: `backend/app/pilot_config.py` beyond its env-key names, `serve_pilot.py`, the Kotlin app address defaults (taken from the accepted mock output and `local_service_connection`).

### Existing patterns to follow

- Owner output: fixed English sentences, one `Result:` line, exit `0`/`1`/`2`; tracebacks only in a printed log path (`local_rag.py`).
- Background service: detached process, record file, pid verified by its command line before any signal, stale record cleared with one sentence (mock).
- Ports injected into a stdlib-only operator module; tests pass fakes and a fake clock (`local_rag_bootstrap.py`).
- Heavy runtimes only in `.venv-hybrid`; orchestration in the dev env with no `torch`/`chromadb` import.

### Planner decisions (not owner decisions; the owner may rename before implementation)

- Names: `--local-rag-start`, `--local-rag-stop`, `--local-rag-service-status` (keeps the `--local-rag-` family; "service-status" avoids confusion with the existing artifact check `--local-rag-status`).
- Bind `127.0.0.1:8000` only: matches the apps' default Desktop and emulator addresses (emulator reaches it through `10.0.2.2`), keeps questions off the network; physical devices belong to the QA environment features.
- Start requires all six `--local-rag-status` parts `OK`: one rule the owner already knows, and every non-OK line already names its fix.
- `MANIJERO_VECTOR_STORE` is the resolved `releases/<id>/vector-store`, recorded as `release_id`, so status can say when a newer release needs a restart.
- `--no-access-log`: the orchestrator log keeps startup and error lines only.
- Run record and log live in the local home (not `build/`), so any checkout can stop the service; one service per local home.

### Current gaps

- The service has no endpoint or non-pilot log that says which ranking or provider served an answer; status can only report the start configuration plus live probes (recorded as a risk, not fixed here).
- No warm-up: the first question after start may fall back to extractive while Ollama loads 15 GB.
- `test_local_rag_commands.py` cannot run the no-dev-environment branch (the module skips without `backend/.venv`); that branch is checked by reading `init.sh`.

## Implementation plan

1. Add `backend/app/local_rag_service.py`: constants (commands, default port, timeouts 60 s start / 10 s stop / 2 s probe), `ServiceRecord` read/write (atomic, `0600`), `port_from_environment` (exit-2 sentence).
2. Add ports: `Processes` (spawn with `start_new_session=True`, `alive`, `command_line`, `terminate`, `kill`), `ServiceProbe` (`health`, `ready` over a no-proxy, no-redirect loopback opener), `Clock`/`sleep`; real defaults.
3. Add `launch_environment(ctx, settings, record, release_id, port)` (allowlist) and `launch_argv(ctx, port)`.
4. Add `find_running` (verify pid by command line, clear stale record, flag the stale line) and `port_owner`.
5. Add `run_start` (order in the contract; catch `BootstrapError` itself so the result line is the start wording), `run_service_status`, `run_stop`; each prints fixed sentences and the addresses block.
6. Extend `backend/scripts/local_rag.py` choices and Ctrl+C sentences; start's Ctrl+C path terminates the child and removes the record.
7. Wire `scripts/init.sh`: dispatch, misuse check, dev-env link rule, `usage`, `--check` listing, mock port-in-use message.
8. Write `test_local_rag_service.py`; extend `test_local_rag_commands.py` (lists below).
9. Update `docs/owner-guide.md` (three sections, walkthrough, mock row), `backend/README.md`, `ARCHITECTURE.md`, `operations.md`, `risks-and-open-questions.md`.
10. Run the focused block, then `./scripts/init.sh --fast`; record one-line results below.
11. Hand the walkthrough to the orchestrator for the owner; record results below.

## Verification plan

- Focused block (contract): offline, all pass.
- `./scripts/init.sh --fast`: no regression.
- `test_local_rag_service.py` (fakes only; temporary home and copied knowledge as in the bootstrap tests):
  - start, all ready: exact argv; environment is exactly the allowlist (inherited `MANIJERO_DEPLOYMENT_PROFILE`, `MANIJERO_RETENTION_DB`, `MANIJERO_GEMINI_MODEL`, `HTTPS_PROXY` dropped); record fields; addresses, log path, result line; exit 0;
  - the launch environment passes the real gates without loading anything: `backend_from_environment(env)` is not `Bm25Backend`, and `resolve_local_provider(env, …committed record…, transport=fake, pilot=False)` resolves `local`;
  - start with each missing prerequisite (never set up, Ollama closed, Ollama not installed, drafting missing, digest mismatch, knowledge changed, invalid settings line, setup lock held, service lock held): fix named, zero spawns, zero pulls/downloads/runner calls, local-home snapshot unchanged, exit 1;
  - port owner mock / foreign `manijero-backend` / other: named step, zero spawns, exit 1;
  - already running (OK and with a problem): zero spawns, status lines, exit 0 / 1;
  - start failures (early exit, health timeout via fake clock, `/ready` 503, Ctrl+C): child terminated, record removed, log path printed, exit 1;
  - stale record (dead pid; live pid with another command line): cleared with the sentence, never signalled;
  - service status: all OK; each PROBLEM (Ollama closed, digest mismatch, newer release, `/ready` 503, `/health` silent); not running makes zero probe and Ollama calls;
  - stop: TERM then record removed; a stubborn process gets KILL only while still verified; not running; stale;
  - bad port values (`0`, `65536`, `abc`) exit 2; no output, record, or log line contains a corpus sentinel string.
- `test_local_rag_commands.py` additions (subprocess, never starts a service, free `MANIJERO_LOCAL_RAG_PORT`):
  - `--local-rag-start` with an empty home: exit 1, names `--local-rag-setup`, home not created;
  - `--local-rag-service-status` with an empty home: exit 1, last line names `--local-rag-start`, home not created;
  - `--local-rag-stop` with an empty home: exit 0, "nothing to stop";
  - a record pointing at a test-owned `sleep` process: status and stop clear it and the `sleep` process is still alive afterwards;
  - extra argument for each new mode and a bad `MANIJERO_LOCAL_RAG_PORT`: exit 2.
- E2E: not applicable here; app-to-service checks are `local_end_to_end_smoke`. Unit and subprocess tests cover the command surface.
- Owner walkthrough (operations.md MUST; run by the owner, guided by the orchestrator, exactly as `docs/owner-guide.md` writes it; agents do not run it). The guide's "Owner walkthrough: local answer service" section carries these steps; for each, the owner reports the `Result:` line and anything that looked different:
  1. Run `./scripts/init.sh --local-rag-status`. Expect `Result: all 6 parts are ready.` (otherwise run the setup first). Report the `Result:` line.
  2. Missing prerequisite: quit Ollama (llama icon in the menu bar, **Quit Ollama**). Run `./scripts/init.sh --local-rag-start`. Expect a `PROBLEM  Drafting model: Ollama is not running. Open the Ollama app…` line and `Result: the local answer service did not start. …`. Report both lines.
  3. Open Ollama, wait 10 seconds, run `./scripts/init.sh --local-rag-start` again. Expect `Result: the local answer service started at http://127.0.0.1:8000.` Report the `Result:` line, the two app addresses, and roughly how long it took.
  4. Close the Terminal window, open a new one at the Manijero folder, run `./scripts/init.sh --local-rag-start`. Expect `Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000.` Report the `Result:` line.
  5. Run `./scripts/init.sh --local-rag-service-status`. Expect three `OK` lines (Answers, Search, Drafting), the two addresses, and `Result: the local answer service is running at http://127.0.0.1:8000.` Report the three lines and the `Result:` line.
  6. Recovery: quit Ollama, run `./scripts/init.sh --local-rag-service-status`. Expect `PROBLEM  Drafting: …` and `Result: … but a check needs attention: …`. Open Ollama, wait 10 seconds, run it again; expect all `OK` and the running result. Report both `Result:` lines.
  7. Run `./scripts/init.sh --local-rag-stop`. Expect `Result: the local answer service has stopped.` Report it.
  8. Run `./scripts/init.sh --local-rag-stop` again. Expect `Result: the local answer service was not running, so there was nothing to stop.` Report it.
  9. Run `./scripts/init.sh --local-rag-service-status`. Expect `Result: the local answer service is not running. Start it with ./scripts/init.sh --local-rag-start.` Report it.

## Evidence to capture

- Focused block and `--fast`: one-line results.
- Test names covering scenarios 1–11.
- Walkthrough steps 1–9: the reported `Result:` line and exit code for each, the release id from step 5, and any difference from the guide. No question or corpus text.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer (fakes and temporary homes only; no real service start, no Ollama call, nothing written to `~/manijero/local`):

- `bash -n scripts/init.sh` — ok.
- `./scripts/init.sh --feature local_full_rag_stack` — `296 passed, 2 skipped` (the 2 skips are the existing `test_local_rag_commands.py` cases that skip while a real Ollama listens on 11434).
- `CI=true ./scripts/init.sh --fast` — 8 of 9 jobs ok (`backend-tests` `1518 passed, 4 skipped`; contract examples and the five evaluators ok); `gradle-jvm-test` could not run: this host has no Java runtime (`Unable to locate a Java Runtime`, `/usr/libexec/java_home` finds none). The diff touches no Kotlin or Gradle file.
- `CI=true ./scripts/init.sh --verify` — stops at the same `gradle-jvm-test` job; Android/Desktop builds not reached for the same reason.
- Rerun by the orchestrator with Gradle's own JDK (`JAVA_HOME=/Users/agents/.gradle/jdks/azul_systems__inc_-21-aarch64-os_x.2/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home`, `PATH="$JAVA_HOME/bin:$PATH"`; this machine needs it): `CI=true ./scripts/init.sh --fast` — all 9 offline checks ok (`gradle-jvm-test` ok; backend `1518 passed, 4 skipped`); Fast tier passed.
- Same environment: `CI=true ./scripts/init.sh --verify` — Full tier passed (Android host tests plus the Android/Desktop builds).
- Manual: the three commands with a temporary `MANIJERO_LOCAL_HOME` print the expected `Result:` lines (start exit 1 naming `--local-rag-setup`, service status exit 1 naming `--local-rag-start`, stop exit 0 "nothing to stop") and create no home; a dummy `sleep` child spawned by `SystemProcesses` ran in a new session and verified by `ps -ww` tokens.
- Scenario coverage in `backend/tests/test_local_rag_service.py`: 1 `test_start_when_ready_launches_the_service_in_the_background`, `test_the_launch_environment_passes_the_real_hybrid_and_local_gates`; 2 `test_a_missing_prerequisite_stops_before_any_change[8 ids]`, `test_start_before_setup_...`; 3 `test_a_port_in_use_names_the_one_step_and_starts_nothing[3]`; 4 `test_start_while_running_*`; 5 `test_a_failed_start_ends_the_process_and_removes_the_record[early-exit, health-timeout, stubborn-timeout, ready-unavailable, ctrl-c]`, `test_an_unexpected_error_after_launch_ends_the_process`; 6–7 `test_status_when_running_and_healthy`, `test_status_reports_each_problem_in_plain_words[6]`, `test_status_recovers_once_ollama_is_opened_again`; 8 `test_status_when_not_running_...`, `test_a_stale_record_is_cleared_and_never_signalled[4x2]`; 9 `test_stop_*`, `test_a_stubborn_service_...`, `test_a_process_that_stops_being_the_service_is_never_killed`; 10 `test_a_bad_port_is_misuse[8]`, `test_the_entry_point_refuses_a_bad_port_...[3]`; 11 `test_no_output_record_or_log_contains_corpus_text`, `test_the_service_never_imports_the_operator_modules`, real-probe tests. Subprocess cases in `test_local_rag_commands.py` (empty home, stale record for a live `sleep`, misuse).
- Implementation notes: start checks the setup lock before reading settings and inspecting (all read-only, so the "setup running" sentence wins over half-built part lines while a setup runs); stop also takes `<home>/.service.lock`, so a stop during a start says to wait. The service tests reuse `Env` and the fakes from `test_local_rag_bootstrap.py` by import.
- Owner walkthrough (steps 1–9 in `docs/owner-guide.md`): run by the owner on 2026-11-01 on the owner's Mac, from this worktree, guided step by step by the orchestrator; every step matched the guide. Reported lines:
  1. --local-rag-status: all 6 parts ready (owner report).
  2. Ollama quit -> --local-rag-start: PROBLEM Drafting model line + "did not start. Open the Ollama app..." as documented (owner report).
     Note: owner first ran step 3 from the main checkout (help text printed, no --local-rag-start there); re-ran in the worktree.
  3. Ollama open -> --local-rag-start (<1 s): hybrid search, release 3050d1b8b5e10f82, model mistral-small3.2:24b-instruct-2506-q4_K_M; Desktop http://127.0.0.1:8000, emulator http://10.0.2.2:8000; log ~/manijero/local/logs/service-20261101T105321Z.log; "Result: the local answer service started at http://127.0.0.1:8000."
  4. Walkthrough Terminal closed, new one opened -> --local-rag-start: same process 68383 (started 10:53 UTC) still running; OK Answers / OK Search (hybrid, release 3050d1b8b5e10f82 still published) / OK Drafting; "Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000."
  5. --local-rag-service-status: same three OK lines + both addresses; "Result: the local answer service is running at http://127.0.0.1:8000."
  6. Recovery: Ollama quit -> status: "PROBLEM  Drafting: Ollama is not running. Answers continue without the drafting model until Ollama is opened. Open the Ollama app, then run this command again." + "Result: ... running at http://127.0.0.1:8000, but a check needs attention: do the first step shown above." Ollama reopened -> status: three OK lines, "Result: the local answer service is running at http://127.0.0.1:8000." (process 68383 throughout; no restart needed)
  7. --local-rag-stop: "Result: the local answer service has stopped."
  8. --local-rag-stop again: "Result: the local answer service was not running, so there was nothing to stop."
  9. --local-rag-service-status: "Result: the local answer service is not running. Start it with ./scripts/init.sh --local-rag-start."

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no download/pull/build, no service code, pin, contract, or settings-key change, no pilot path, no LAN bind).
- [ ] Every start prerequisite is checked before any write under the local home or any spawn; each non-OK line names its fix.
- [ ] Launch argv binds `127.0.0.1` without reload from `.venv-hybrid`; the environment is exactly the allowlist and passes the real hybrid and local-provider gates in tests.
- [ ] No process is signalled unless its command line verifies it as this service; stale records are cleared with the sentence.
- [ ] Re-running start and stop reports the current state; status exits 0 only when running with all three checks `OK`.
- [ ] Output is plain sentences with one `Result:` line; tracebacks and server output only in the printed log; no corpus or personal text.
- [ ] Acceptance scenarios pass, with evidence; the owner walkthrough steps 1–9 are recorded, including step 2 (missing prerequisite) and step 6 (recovery).
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature local_full_rag_stack`; no test starts a service, needs Ollama, or writes to `~/manijero/local`.
- [ ] Durable documentation impact followed (owner guide sections and walkthrough, README subsection, ARCHITECTURE bullet, operations MUST, risks); nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
