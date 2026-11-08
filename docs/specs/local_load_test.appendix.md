# local_load_test — appendix

## Repository research

### Files inspected

- `scripts/init.sh` — early owner-command dispatch for the `--local-rag-*` and `--local-smoke` modes: overflow-arg sentence + exit `2`, `python-env.sh dev --if-present` link, `usage`, `--check` listing; `--feature <id>` runs the published block from the spec.
- `backend/scripts/local_rag.py` — owner entry point for setup/status/smoke/service/container commands, per-command Ctrl+C wording, `RunLog` traceback path.
- `backend/app/local_rag_service.py` — `find_running` (verified pid + stale record), `service_checks` (Answers/Search/Drafting, each failing line names its fix), `ServiceRecord` (pid, port, started_at, release_id, log), `service_url`, `START_COMMAND`, `SERVICE_STATUS_COMMAND`, fixed sentence constants.
- `backend/app/local_smoke.py` — the closest precedent: `_check_service` gate (settings, verified record, first failing check), `_NotRun` + `NOT_RUN_RESULT`/`FIX_SHOWN`, home lock, fixed owner sentences, injected `SmokePorts`, stdlib-only.
- `backend/scripts/measure_local_generation.py` — report-only measurement precedent: text-free JSON, `summarize_latencies` (nearest-rank p95), fixed-error `MeasurementError` codes, exit `0/1/2`, never prints question/passage/answer text.
- `backend/app/answer_eval.py` — `load_case_document(path, catalog, passages)`, authoritative `pac-answer-eval-v2` validation (keys, ids, question ≤ 2000, general land context, expected status).
- `backend/app/local_generation.py`, `backend/config/local_generation_model.json` — 10 s per-draft timeout, 30 requests/minute and 2000/day limiter, `keep_alive` 1800 s, `num_ctx` 4096, 15.17 GB model; the provider returns to extractive per request on timeout/limiter without a response signal.
- `backend/app/answer_inspection.py`, `backend/app/main.py` — `inspection` (with `drafting.outcome`, `outcome`, timings) is sent only when the deployment profile is explicitly `development`; the local start allowlist sets no profile, so it is off.
- `backend/app/ask_api.py` — `/ask` is a sync `def` (threadpool), request `question` + `land_context` only, response `status` ∈ `answered|abstained|needs_land_clarification`.
- `contracts/openapi.yaml` — `AskRequest` requires `question` and `land_context`; `retain_for_improvement` defaults false; `AskResponse.status` and the dev-only `inspection`.
- `knowledge/pac_answer_eval.json` — 14 reviewed PAC cases, `pac-answer-eval-v2`, every case `{"mode": "general", "lands": []}`.
- `docs/archive/MasterPlanV3.md` §9.2 and its testing-strategy table — p95 8 s is a candidate starting point, not proven performance or a release promise; the table lists `Locust / k6` as the load tool, superseded here by the owner decision.
- `docs/owner-guide/local-checks.md` — local service start/check sections, `Result:` + "if you see something else" table style, "Owner walkthrough" sections.
- `backend/README.md` — `## One-command local setup` → `### Local answer service`, `### Local smoke test` (placement for the new subsection).
- `docs/constraints/operations.md` — owner operability MUSTs (one command, prerequisites before change, one `Result:` line, owner guide, walkthrough with a missing-prerequisite case and a recovery).
- `docs/risks-and-open-questions.md` — Medium-risk row style; existing "status reports configuration, not what each answer used" row.
- `ARCHITECTURE.md` local-RAG layer bullets — operator-only, stdlib-only, never imported by the service.
- Not inspected: the client Ktor `/ask` timeout and connection reuse; the actual loopback round-trip cost on the owner's Mac.

### Existing patterns to follow

- Owner output: fixed English sentences, one `Result:` line, exit `0`/`1`/`2`; unexpected error → one sentence plus a printed log path.
- Operator modules are stdlib-only, injected ports, and never imported by the service.
- The service gate is `find_running` + `service_checks`, not a hand-rolled health check.
- Measurements are report-only JSON with fixed failure codes and no text.

### Owner decisions (2026-11-06, pre-decided)

1. Tooling: standard-library-only Python measurement inside this repo behind a named `./scripts/init.sh` command, following `backend/scripts/measure_local_generation.py`; no k6, no Locust, no new dependency, no download.
2. Load profile: pilot is 8–10 people, so up to 10 concurrent clients against the real service started by `./scripts/init.sh --local-rag-start`, short ramp (for example 1 → 10), steady phase of a few minutes, reviewed corpus questions; no invented traffic claims.
3. Execution: the owner runs the real measurement on the owner's Mac from numbered copy-paste steps in `docs/owner-guide/local-checks.md`; the orchestrator records the reported numbers as evidence. Automated verification uses fakes only (no real service/Ollama, no `torch`/`chromadb`, no writes outside temporary directories, loopback fake ports at most).
4. Thresholds: report median/p95/max and achieved throughput; show the 8 s p95 as the plan's candidate reference only, no pass/fail gate and no capacity claim; report an outcome/fallback mix only if the service exposes it without new product surface, otherwise say so and leave it out.
5. Privacy: no question, passage, answer, land, or token text in output, logs, or records; only aggregate timing/counts and a corpus case count.

### Planner decisions (owner may rename before implementation)

- Command `--local-rag-load-test`, script `backend/scripts/measure_local_load.py`, invoked directly by `init.sh` (like a measurement tool, not a service operation); `local_rag.py` stays unchanged.
- Plan constants: 10 clients, 10 s ramp (client *i* at *t0 + i*), 180 s steady, 2 warm-ups, 60 s timeout. The measured window is the steady phase; warm-up and ramp are reported but excluded from the headline.
- Closed loop with no think time: the reported throughput is what back-to-back asks at that concurrency achieve, not a model of human pacing.
- The target is the port in the verified `--local-rag-start` run record; no port input, so a container or `--backend` service is not measured.
- `status` counts (answered/abstained/needs a land choice) are contract surface and are reported; drafting/ranking fallback counts are not available and stay out of scope.
- Report file `<local home>/reports/local-load-<UTC>.json`, `0600`, schema `local-load-measurement-v1`; per-case ids and timings excluded.
- Exit `0` only when the run finished, nothing failed, and the same service pid/release was still running at the end; latency itself never affects the exit code.

### Current gaps

- No per-answer ranking/provider signal outside `development` (`inspection`), and the local start has no profile, so drafting use and fallbacks cannot be counted.
- The pinned local provider allows 30 drafts/minute: a 10-client closed loop asks far more, so most loaded answers may be extractive and the measured p95 may understate drafting cost. This is a known product limitation, not something this feature fixes.
- The service is one uvicorn process (no `--workers`), so concurrency is the process threadpool plus Ollama queueing; the number is host-specific.
- The reviewed cases use `general` context, so land-context payload size is unmeasured.

## Implementation plan

1. Create `backend/scripts/measure_local_load.py`: constants (command, plan, schema, case paths, report dir), `MeasurementError`/`Prerequisite` fixed-code types, `main(argv)` with a zero-argument contract.
2. Add pure helpers: `parse_cases` (reusing `load_case_document`), `client_start_offsets`, `phase_of`, `summarize` (nearest-rank p95, median, max, mean), `aggregate`, `build_report`, `render_lines`.
3. Add `AskConnection` (one `http.client` connection per simulated client, loopback host/port, timeout, body cap, fixed error codes, discard text after reading `status`).
4. Add `run_plan` (workers start at their offset, closed loop until the steady deadline or the stop event, phase by request start) and `run_load` (facts → warm-up → ramp/steady → end re-check → report).
5. Add the prerequisite gate mirroring `local_smoke._check_service`, returning injected `ServiceFacts` (record or refusal lines) so tests never build settings or pins; validate the reviewed cases before any file write; add the home lock, the atomic `0600` report writer, and the fixed sentences.
6. Wire `scripts/init.sh`: `--local-rag-load-test` block, misuse exit `2`, dev-env link, `usage`, `--check` listing.
7. Write `backend/tests/test_local_load.py` (pure helpers, gate, runner, report, privacy) with fake service facts, fake clock, and fake connections.
8. Add the two `init.sh` subprocess cases to `backend/tests/test_local_rag_commands.py` (temporary home, never contacts a service).
9. Update `docs/owner-guide/local-checks.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`, `docs/risks-and-open-questions.md`.
10. Run the focused block and `./scripts/init.sh --fast`; record one-line results below.
11. Hand the walkthrough to the orchestrator for the owner; record the reported numbers below.

## Verification plan

- `test_local_load.py` (fakes and a temporary home only):
  - case parsing accepts the reviewed set and rejects each malformed shape (missing key, duplicate id, blank/oversized question, wrong land mode, unreadable file) with exit `2` and no request;
  - ramp offsets spread clients 0…9 and collapse correctly for 1 client or a zero ramp; `phase_of` boundary at `t0+ramp` and `t0+ramp+steady`; percentiles/median/max/mean on known lists and empty input;
  - a tiny plan against fake connections: count per phase, steady-only headline, failures/timeouts counted with fixed codes, one failing client does not stop the others;
  - gate: not running (no record), stale record, health down, `/ready` unavailable, Ollama closed, digest mismatch, newer release → the `PROBLEM`/result lines, exit `1`, zero requests, no report;
  - busy lock, Ctrl+C, service pid/release change mid-run, failed requests, a failed warm-up → the fixed result lines and exit `1`; a finished clean run → exit `0`;
  - report written only under the temporary home with schema, plan, counts, `used_as_gate: false`, and `limitations`; stdout and report contain no question, answer, passage, land, or token sentinel text;
  - importing `app.main` does not import `measure_local_load`.
- `test_local_rag_commands.py` additions: `--local-rag-load-test` with an empty temporary home (no settings) → exit `1` with the existing "not set up yet" sentence and `Result: the load test did not run. Do the first step shown above.` (scenario 4), no `reports/` created; settings with no run record → scenario 3's `--local-rag-start` result; an extra argument → exit `2`.
- E2E: not applicable; this changes no app flow. Unit/subprocess coverage plus the owner run covers the command.
- `bash -n scripts/init.sh`; then `./scripts/init.sh --fast` for no regression.
- Owner walkthrough (run by the owner, guided by the orchestrator, exactly as `docs/owner-guide/local-checks.md` writes it):
  1. `./scripts/init.sh --local-rag-service-status` → three `OK` lines and the running result (if not, `--local-rag-start`). Report it.
  2. **Missing prerequisite:** `./scripts/init.sh --local-rag-stop`, then `./scripts/init.sh --local-rag-load-test` → `Result: the load test did not run. Start the local answer service with ./scripts/init.sh --local-rag-start, then run this command again.` Report it.
  3. `./scripts/init.sh --local-rag-start`; quit Ollama; `./scripts/init.sh --local-rag-load-test` → a `PROBLEM  Drafting:` line and `Result: the load test did not run. Do the first step shown above.` Report both lines.
  4. **Recovery and the measured run:** open Ollama, wait 10 seconds, run `./scripts/init.sh --local-rag-load-test`. Expect the plan line, two warm-up times (the first may be long while the model loads), the steady summary, the honesty note, and `Result: the load test finished; the report is in <path>.`, exit `0` after about five minutes. Report the median, p95, slowest, requests per second, finished/failed counts, answer-kind counts, and the report path.
  5. Send the report file (aggregates only) to the orchestrator, then `./scripts/init.sh --local-rag-stop`.

## Evidence to capture

- Focused block and `--fast`: one-line results.
- Test names covering scenarios 1–9.
- Owner walkthrough steps 1–5: each `Result:` line, the summary numbers, exit codes, and any difference from the guide. No question or corpus text.

## Feature evidence

2026-11-06, implementer (Claude/Codex/opencode wrapper session, feature worktree `local_load_test`):

- `bash -n scripts/init.sh` → exit 0.
- `MANIJERO_PYTHON="$PWD/backend/.venv/bin/python" ./scripts/init.sh --backend-tests tests/test_local_load.py tests/test_local_rag_commands.py -q` → `58 passed, 2 skipped in 2.21s`.
- `MANIJERO_PYTHON="$PWD/backend/.venv/bin/python" ./scripts/init.sh --feature local_load_test` → `Focused tier passed` (2 command lines, same `58 passed, 2 skipped`; log `build/verify-logs/feature-local_load_test.log`).
- `CI=true ./scripts/init.sh --fast` → `Fast tier passed`; all 10 checks `[ok]` (backend `1913 passed, 4 skipped`).
- `./scripts/init.sh --check` → the new command is listed with its one-line description; `--help` usage lists `--local-rag-load-test`.
- `backend/tests/test_local_load.py` (39 tests) covers scenarios 1–9: gate and stale record, all five failing-check kinds, lock, Ctrl+C, warm-up failure, a failed ramp request affecting the exit code, failed/timeout/non-2xx counts without invented latency, mid-run stop/release change, 0600 aggregate report and the `service_*_during_run` keys, sentinel privacy in output and report, zero-argument misuse, and `app.main` not importing the script. The three subprocess tests in `test_local_rag_commands.py` cover the `init.sh` boundary (extra argument, empty home, settings with no run record).
- Manual checks: no real measurement was run (owner-run, out of scope); no question was sent to a real service, and no report, lock, or log was written outside temporary test homes. Durable docs updated as the contract lists.

Interpretation notes for the validator:

- **Pre-setup vs. no record.** The gate mirrors `local_smoke._check_service` but keeps scenario 4's result: an empty home → the existing `svc.MSG_NOT_SET_UP` sentence (which names `--local-rag-setup`) + `Result: the load test did not run. Do the first step shown above.`, exit `1`; settings present with no run record → scenario 3's exact `--local-rag-start` line. Neither sends a question or writes a report.
- **Land context in the corpus.** `knowledge/pac_answer_eval.json` has one reviewed case (`alcance-terrenos-2026`) with `{"mode": "all_active", ...}`; the other 13 are `general`, contrary to the spec/appendix statement that all use `general`. The measurement follows scenario 9 literally: every request (warm-up and steady) sends the fixed empty `general` context and never replays a case's own land list. The report's limitations and the new risk row say land-context payloads are unmeasured. The corpus itself was not edited.
- **Steady window.** Throughput is successful steady requests over the observed steady span (last request end minus ramp end), capped at the planned `steady_seconds`, so an interrupted run reports its real shorter window and an overlapping request cannot inflate it past 180 s.

2026-11-07, owner walkthrough steps 1–5: all passed, no difference from the guide. Measured run: steady 1844 requests, 0 failed, median 0.70 s, p95 1.18 s, max 10.77 s, 10.24 requests/s; ramp median 10.11 s; warm-up 4.63 s / 6.89 s. Details in the [acceptance record](../validations/local_load_test.md#owner-walkthrough-2026-11-07).

## Validator checklist

- [x] Scope matches the contract; no dependency, service, knowledge, contract, pin, Kotlin, or app change; no metrics surface or per-answer signal added.
- [x] The command is zero-argument, loopback-only, gated on the verified `--local-rag-start` record and its three checks, and names the fix when it refuses.
- [x] Headline statistics use steady-phase successful requests only; warm-up and ramp are reported separately; throughput is measured, not nominal.
- [x] The 8 s p95 is shown as a candidate reference with `used_as_gate: false`; no capacity, SLA, quality, or pilot-readiness wording.
- [x] Output, report, and logs contain no question, answer, passage, land, or token text, only aggregate timings/counts and the case count.
- [x] Exit codes and `Result:` lines match the contract; failures and a mid-run service change are visible, never averaged away.
- [x] Acceptance scenarios pass with evidence; the owner walkthrough including the missing-prerequisite and Ollama-closed cases is recorded.
- [x] The focused block runs unchanged through `./scripts/init.sh --feature local_load_test`; no test starts a service, needs Ollama, or writes outside temporary directories.
- [x] Durable documentation impact followed (owner guide, README, ARCHITECTURE, operations MUST, risk row); nothing restated across files.
- [x] `feature_list.json` and `PROGRESS.md` updated at acceptance.
