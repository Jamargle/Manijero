# Measure local answer latency and throughput under expected pilot load

## Source metadata

- `id`: local_load_test · `area`: testing · `depends_on`: local_full_rag_stack (accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --local-rag-load-test` against the running local answer service; it asks the 14 reviewed PAC questions from up to 10 simulated clients for a few minutes, prints median, p95, slowest time and achieved throughput, saves an aggregate-only report, and makes no pass/fail, capacity, or pilot-readiness claim.
- Verification: offline tests with fake service facts and a fake client, plus an `init.sh` subprocess case (commands in Focused verification); the real measurement is run by the owner and recorded by the orchestrator.
- Notes: owner decisions 2026-11-06 — standard-library-only Python measurement, no k6/Locust/dependency/download; 10 concurrent clients with a short ramp and a steady phase against the service started by `--local-rag-start`; the owner runs the real measurement on the owner's Mac from numbered steps in `docs/owner-guide.md`; median/p95/max and throughput only, the 8 s p95 as the plan's candidate reference with no gate and no capacity claim; no question, passage, answer, land, or token text anywhere. Planner decisions (command name, plan constants, report format, exit codes) are in the appendix.

## Goal

Replace guesswork about local answer speed with one reproducible owner command that reports answer latency and throughput for the reviewed corpus at pilot concurrency on this Mac, and records those numbers as evidence without turning them into a promise about the pilot, the QA host, or service capacity.

## Non-goals

- No k6, Locust, load-testing framework, new Python dependency, download, or container.
- No change to the answer service, retrieval, generation, release, `contracts/`, pins, or `knowledge/`; no new metrics, endpoint, dashboard, or per-answer ranking/provider signal.
- No app, Compose, Kotlin, or settings change; no screenshot, UI copy, or `DESIGN.md` work.
- No pilot, QA, prod, container, or LAN path; no physical device; no work against any host other than the recorded loopback local service.
- No latency gate, threshold, regression check, ranked comparison of models/hosts, answer-quality, legal-coverage, or capacity/pilot-readiness conclusion.
- No land context in the measured requests (the reviewed cases use `general`), so land-context payload effects are not measured.
- No separating drafting from the extractive fallback: the service does not expose it (see scenarios 2 and Technical approach).

## Job story

When I need to know whether the local answer service is usable for 8–10 people, I want one command that asks reviewed questions from several clients at once and tells me how long answers took and how many it handled, so I can decide with real numbers from this Mac while knowing the pilot computer has not been measured.

## Acceptance Scenarios

### 1. A complete measurement

Given the local answer service started by `./scripts/init.sh --local-rag-start`, with all three service checks `OK` · When the owner runs `./scripts/init.sh --local-rag-load-test` · Then it prints that it is checking the service, the service address and release, the plan (14 reviewed questions, 2 warm-up questions, 10 clients, one more every second for 10 seconds, 3 minutes at once, about five minutes), a warm-up line, then the steady summary: questions finished, how many did not answer, median, p95, slowest, requests per second, and answer kinds counted from the contract `status` (answered / abstained / needs a land choice); it prints the report path, the honesty note of scenario 2, and `Result: the load test finished; the report is in <path>.`, exit `0`. The report file holds zero failures and says the service was unchanged throughout.

### 2. The numbers stay honest

Given any finished run · Then the last lines before the result say that the numbers describe this Mac at that moment, are not a capacity measurement, and that the pilot computer has not been measured; the p95 line shows the plan's 8 s candidate reference as context only, with no verdict, ratio, or pass/fail; the service may silently answer without the drafting model when its 10 s draft timeout or its pinned 30 requests/minute limit is reached, so a low p95 under load can hide drafting, and the output and report say the drafting/fallback mix cannot be observed.

### 3. The service is not running

Given no run record, or a record whose process is gone (a stale record is cleared with the existing leftover-record sentence) · When the load test runs · Then no question is sent, no report is written, the only files touched are the load-test lock and that cleared record, it prints `Result: the load test did not run. Start the local answer service with ./scripts/init.sh --local-rag-start, then run this command again.`, exit `1`.

### 4. A service check is not OK

Given setup has not run, or the service runs but `/health` does not answer, `/ready` is unavailable, Ollama is closed, the drafting model or digest differs, or a newer release was published after start · When the load test runs · Then it prints the one `PROBLEM` line `--local-rag-service-status` would print for the first failing check (each already names its fix), sends no question, writes no report, and ends `Result: the load test did not run. Do the first step shown above.`, exit `1`. A service on another port, a container, or a `--backend` service is not the target: the missing record falls under scenario 3.

### 5. Some questions fail

Given a finished run in which requests failed, timed out, or the service answered a non-2xx status · Then the summary still prints with counts of finished and failed requests and the latency of the successful ones, and the result is `Result: the load test finished, but <n> questions failed. The numbers above are incomplete; run it again once and send the report to a developer if it repeats.`, exit `1`. No latency is invented for a failed request. Given a warm-up question fails · Then the timed phase does not start and the result is `Result: the load test did not run. The service did not answer the warm-up questions. Run ./scripts/init.sh --local-rag-service-status and do its first step.`, exit `1`, with no report.

### 6. The service changes during the run

Given the recorded service stops, is restarted, or a newer release is published while the test runs · Then the report is written with `service_stopped_during_run` or `service_changed_mid_run` set, exit `1`, and the result says the numbers are not a complete measurement and names `--local-rag-start`.

### 7. Interrupted or already running

Given the owner presses Ctrl+C · Then the workers stop, it prints `The load test was stopped.` and `Result: the load test was stopped before it finished. Nothing was changed.`, exit `1`, and no report is written. Given another load test already holds the local load-test lock · Then it sends no question and ends `Result: the load test did not run. Wait for the other load test to finish, then run this command again.`, exit `1`.

### 8. Misuse and an unreadable case set

Given anything after the command, or a reviewed case file that cannot be read or validated · Then it sends no question, changes nothing, prints one plain sentence saying the command runs on its own or that the questions could not be read, and exits `2`.

### 9. Privacy and read-only behavior

Given any run · Then the only network calls are loopback to the recorded service port; every request is one `/ask` with a reviewed case question and its `general` land context, with no retention request, token, land, or personal data added; no output, report, log, or orchestrator line contains question, passage, answer, land, or token text, only aggregate timings and counts and the reviewed case count; nothing under `knowledge/`, `contracts/`, the service, or the repo state is modified, and the only files written are the load-test lock, the report under the local home, and a traceback log on an unexpected error.

## Technical approach

- **Command.** `scripts/init.sh` adds `--local-rag-load-test` as an early owner command beside `--local-rag-*` (before the Android/Java/`local.properties` steps): it rejects extra arguments with the existing "run it on its own" sentence and exit `2`, applies the same dev-environment link as `--local-rag-status` (missing: the "not set up yet" pair, exit `1`), then runs the measurement script directly from `backend/.venv/bin/python`. It accepts no port, plan, or path input; `MANIJERO_LOCAL_RAG_PORT` is not read. `--check` output and `usage` gain the command.
- **Measurement script.** New `backend/scripts/measure_local_load.py`: stdlib-only, operator-only, never imported by the service, one `main` with no arguments and injected ports for tests. It reuses `app.local_rag_service` (`find_running`, `service_checks`, `ServicePorts`, fixed sentences), `app.local_rag_bootstrap` (`default_context`), and `app.answer_eval.load_case_document` with `app.source_catalog`/`app.retrieval` loaders over `knowledge/pac_answer_eval.json`, `knowledge/source_catalog.json`, and `knowledge/passages.json`. Do not add a second case validator.
- **Prerequisite gate.** Mirror `local_smoke._check_service`: read settings, verified run record for this service (a stale record is cleared with the existing sentence), then the three checks; stop at the first gap with its own line and a fixed result. Refusing when Ollama is closed is deliberate: a run without drafting measures a different stack.
- **Load plan (module constants).** 10 clients, 10 s ramp, 180 s steady phase, 2 sequential warm-up questions, 60 s per-request timeout. Client *i* starts at *t0 + i · ramp / clients*; each client keeps one loopback `http.client` connection, sends the reviewed cases round-robin from its own offset, and sends again as soon as the previous response is read (closed loop, no think time, no randomness). Warm-up runs before *t0* and is reported separately; a failed warm-up ends the run before the timed phase. Phase is decided by request start: before *t0 + ramp* it is ramp, before *t0 + ramp + steady* it is steady; headline statistics use successful steady-phase requests only.
- **Measurement.** Latency is `perf_counter` around the whole request and response body read on loopback. Percentiles are nearest-rank p95, median, max and mean over successful 2xx responses (same rule as `measure_local_generation.summarize_latencies`). Throughput is successful steady requests divided by the measured steady window. Failures, timeouts, and non-2xx are counted per phase with fixed codes only; no exception text is stored. `status` is read from each parsed response for the answer-kind counts; `answer`, `sources`, and passages are discarded immediately.
- **Output and report.** Fixed English sentences, one `Result:` line, exit `0` finished with no failures and an unchanged service, `1` refused/failed/incomplete/interrupted, `2` misuse or unreadable input. The report is written atomically with mode `0600` to `<local home>/reports/local-load-<UTC>.json`, schema `local-load-measurement-v1`: plan constants, service pid/port/release/start time and the two change flags, per-phase counts and timing summaries, HTTP status counts, answer-status counts, the reviewed case count, the 8 s candidate reference marked `used_as_gate: false`, and a fixed `limitations` list. Per-case ids and per-case timings are deliberately excluded.
- **Lock and end check.** The reviewed case file is validated before the lock and the gate, so misuse and unreadable input write nothing. An exclusive non-blocking `flock` on `<local home>/.load-test.lock` prevents two measurements at once. At the end the script re-reads the run record and verifies the same pid is still this service with the same release; otherwise it sets the change flags.

## Expected file changes

- `backend/scripts/measure_local_load.py` — create; measurement, reporting, prerequisite gate.
- `scripts/init.sh` — modify; early dispatch, misuse, dev-env link, usage and `--check` listing.
- `backend/tests/test_local_load.py` — create; pure helpers, fake-service gate, runner, report, privacy.
- `backend/tests/test_local_rag_commands.py` — modify; two subprocess cases (`init.sh` refused with an empty home, extra argument) that never contact a service.
- `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`, `docs/risks-and-open-questions.md` — update; see below.
- Not changed: `backend/app/*` (including `local_rag_service.py`, `local_smoke.py`, `ask_api.py`, `local_generation.py`), `backend/scripts/local_rag.py`, `backend/scripts/measure_local_generation.py`, `knowledge/*`, `contracts/*`, `backend/config/*`, requirements, Kotlin/Gradle, `feature_list.json` status.

## Visual design impact

UI involved: no. No app screen, Spanish copy, or `DESIGN.md` change.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — add one local-RAG-layer line: `backend/scripts/measure_local_load.py` (behind `./scripts/init.sh --local-rag-load-test`) is operator-only and stdlib-only, measures the unchanged local service over loopback `/ask` with aggregate reports under the local home, and is never imported by the service.
- `docs/constraints/operations.md`: update — one MUST under Owner operability: a measurement command is read-only over loopback, takes no arguments from the owner, prints only aggregate counts and timings (never question, answer, passage, land, or token text), and its numbers are host-specific evidence that MUST NOT be described as pilot capacity, a service promise, or a pass/fail result. Reason: `local_load_test`.
- `AGENTS.md`: not needed — no workflow, startup, or repo-wide rule change.
- `docs/owner-guide.md`: update (about 50 lines) — "Measure answer speed under pilot load" with numbered copy-paste steps, the expected summary and `Result:` lines, an "if you see something else" table (not running, `PROBLEM` check line, failures, interrupted, another load test), and "Owner walkthrough: load test" with the steps in the appendix.
- `backend/README.md`: update (under `## One-command local setup`, after the local smoke test) — command, plan constants, report path/schema, exit codes, prerequisite gate, the drafting-limit/timeout caveat, and "no dependency" note. At most 30 lines.
- `docs/risks-and-open-questions.md`: update — one Medium-risk row: numbers come from one Mac, the pilot host is unmeasured, the service hides its drafting/extractive mix and its 30 requests/minute drafting limit, so load numbers are not capacity evidence and a low p95 may hide fallbacks.
- `PROGRESS.md` "Current state" and `docs/progress/known-limitations.md`: one line each at acceptance.
- `CONTEXT.md`, `DESIGN.md`, `contracts/`, `knowledge/README.md`: not needed.

## Focused verification (required)

Offline in the shared `backend/.venv`: no service process, no Ollama, no `torch`/`chromadb`, no network beyond test-owned fakes, no write outside temporary directories. Subprocess cases pass a temporary `MANIJERO_LOCAL_HOME` and never start a service.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_load.py tests/test_local_rag_commands.py -q
```
<!-- verify:end -->

The real measurement (real service, real Ollama, real `~/manijero/local`) is run by the owner and recorded by the orchestrator; it is not part of this block.

## Appendix

See [`local_load_test.appendix.md`](local_load_test.appendix.md) for research, owner and planner decisions, plan, evidence, and the validator checklist.
