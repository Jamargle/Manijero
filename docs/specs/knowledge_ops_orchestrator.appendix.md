# Appendix: `knowledge_ops_orchestrator`

Contract: [`knowledge_ops_orchestrator.md`](knowledge_ops_orchestrator.md). This file holds research, plan, verification plan, evidence, and the validator checklist.

## Repository research

Inspected (planner, 2026-11-08):

- `feature_list.json` line for this feature — five accepted dependencies; `hosted_review_pull_requests` depends on this feature.
- `docs/specs/knowledge_update_scheduler.md`, `backend/app/source_update_scheduler.py` — `run_updates(state_dir, monitor_config, jobs, force, boe_dates, trigger, now, sleep, run_id)` wraps monitor + BOE/BOJA discovery with its own lock, ledger, due rules, and `BACKOFF_SECONDS = (60, 300)`; `TRIGGERS = ("manual", "systemd")` is checked at run start and in `read_ledger` (line 142); the CLI uses it as argparse `choices`.
- `backend/deploy/systemd/manijero-source-updates.{service,timer}` — host-only templates, not installed; no owner command exposes the scheduler today (`scripts/init.sh` has no scheduler block).
- `backend/app/page_monitor.py` `run(config, state_path, report_path, now)`; config shape documented in `backend/README.md` "Manual official-page change monitoring" (three example pages); exit `1` = a page failed.
- `backend/app/relevance_classifier.py` `classify(discovery_state, procedure_map, report, transport, clock, record_path)`; `backend/scripts/classify_candidate_relevance.py` builds `OllamaTransport` from `local_generation.DEFAULT_RECORD_PATH`; `ClassificationAbort` when the model is not running (per-candidate model errors become `unsure`).
- `backend/app/document_ingestion.py` `ingest(discovery_state, state_path, quarantine_dir, monitoring_state, now)` — per-candidate failures recorded, `IngestionError` for global errors; `candidate_admission_issue(candidate)` is the public seam `review_package` uses.
- `backend/app/change_impact.py` `analyze(ingestion_state, quarantine_dir, catalog_path, passages_path, cases_path, as_of)`, `write_report`; `exit_code` 1 means "needs review", not failure.
- `backend/app/source_validity.py` `check_validity(catalog, passages, impact_report, as_of)` — requires the impact report, so validity runs after impact; `write_report`; `exit_code` 1 means proposals exist.
- `backend/app/review_package.py` `prepare(...)` needs a human `knowledge-update-proposal-v1` (catalog/passage edits) plus reviewers; `merge` is the only canonical writer. `docs/validations/knowledge_update_review_pr.md` — local draft package, no hosting PR.
- `backend/app/health_metrics.py` — `read_source_updates` pattern (env-named folder, `readable` false on any error, fixed labels; `outcome` and `state` already allowlisted).
- `backend/app/local_rag_service.py` ~line 311 — allowlisted child environment for `--local-rag-start`.
- `docs/specs/monitoring_dashboard.md`, `backend/monitoring/` (`thresholds.json`, `prometheus/rules.json`, `grafana/dashboards/manijero-health.json`) — rule code scheme `-1/0/1/2/4`, static file checks in `tests/test_monitoring_files.py`.
- `backend/app/qa_alerts.py` — launchd pattern: `SystemLaunchctl` (label hard-coded), `MANIJERO_LAUNCHCTL_CLI` / `MANIJERO_LAUNCH_AGENTS_DIR` / home env test seams, plist without secrets, `LAUNCHD_PATH`; `scripts/init.sh` lines 250–275 dispatch block to copy.
- `docs/constraints/operations.md`, `docs/constraints/answers-and-knowledge.md` lines 198–206 — owner-operability MUSTs; scheduled checks only from operator-installed host units; tests offline.
- `knowledge/` — `source_catalog.json`, `passages.json`, `pac_answer_eval.json`, `procedure_map.json` are the read-only inputs.

Not inspected: ingestion/discovery network seams in detail (orchestrator tests fake whole steps), `local_container.py` (container gets no new env by constraint).

## Implementation plan

1. Add `knowledge_ops` to `source_update_scheduler.TRIGGERS`; extend its test for the new value.
2. Add optional `label` to `qa_alerts.SystemLaunchctl` (default `LABEL`); regression test that QA calls are unchanged.
3. `backend/app/knowledge_ops.py`: paths/home (`MANIJERO_KNOWLEDGE_OPS_HOME` test seam, default `~/manijero/knowledge-ops`), lock, ledger read/append, step table with `needs` (classify←discover, ingest←discover, impact←ingest, validity←impact, review←impact+validity).
4. Step adapters (one function per step) calling the entry points in the contract; each returns `ok` + counts or `failed(code, retryable)`; config/input error codes are non-retryable.
5. Step runner port: real runner spawns the child with timeout = time left, terminate then kill after 10 s; fake runner for tests.
6. `run_cycle`: deadline = start + 1 h on the injected clock; attempts ≤ 3, waits `min(backoff, time left)`; `not_run` reasons; outcome `review_ready | failed | stopped_at_time_limit`; always write summary, `latest-summary.txt`, `run_finished`.
7. Prepare-review step: `REVIEW.md` (counts, candidate ids with admission codes, report links, manual next step) and `review-ready.json` (digests, `published: false`).
8. `status`: schedule state via launchctl, last run, `missed` / `interrupted` warnings.
9. `on` / `off`: prerequisite checks, folder + configs from `backend/deploy/{source-monitor,page-monitor}.json.example`, plist (`StartCalendarInterval` 10:20, `LAUNCHD_PATH`, no `MANIJERO_*`), bootstrap/bootout; idempotent.
10. `backend/scripts/knowledge_ops.py` thin CLI (`on|off|run|status|step`), value-safe stderr, exit codes 0/1/2/3; `scripts/init.sh` dispatch + usage lines.
11. `health_metrics`: `MANIJERO_KNOWLEDGE_OPS_STATE_DIR` reader + four families; `local_rag_service` passes it when the folder exists.
12. Monitoring: threshold, recording rule, "Knowledge updates" row and stat panel with value-mapped sentences; update static checks.
13. Docs per the contract's documentation list; evidence below.

## Verification plan

- `tests/test_knowledge_ops.py` (sockets blocked, fake clock/sleep/runner): happy path order and artifacts; retry-then-success sleep `[60]`; always-fail `[60, 300]` and reported failure text; non-retryable single attempt; dependent `not_run` vs independent continue; time limit kills child, caps waits, still writes summary; summary ≤15 lines with no title/URL/exception text (seed candidate titles with a marker and assert absence); ledger records and `0600`; lock exit 3; `knowledge/` bytes unchanged; static guard that the module never references `merge`, `record_decision`, or release publish; adapters call the accepted entry points with the expected paths (monkeypatched).
- `tests/test_knowledge_ops_commands.py` (automated owner walkthrough via `scripts/init.sh`, temp HOME, fake `launchctl`, fake step runner): run before `on` → missing-prerequisite message, exit 2; `on` twice idempotent; plist content; `run` with fake Ollama down → `failed` with fix sentence; recovery `run` → `review_ready`; `status` outputs; `off` keeps history.
- Updated: `test_health_metrics.py` (new families, unreadable folder, unknown outcome clamps), `test_monitoring_files.py` (rule, threshold, panel sentences match), `test_local_rag_service.py` (env only when folder exists), `test_qa_alerts.py`, `test_source_update_scheduler.py`.
- Then `./scripts/init.sh --fast`. No Docker smoke and no live official-site run are required.

## Evidence to capture

Focused command result line, `--fast` result, one sample `summary.txt` from a fake run (counts only), the generated plist with paths redacted to `~`, and the list of changed files.

## Feature evidence

Implementer, 2026-11-08 (all offline; fakes only).

- `./scripts/init.sh --feature knowledge_ops_orchestrator` (the spec block): `270 passed, 1 skipped`.
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed; backend `3136 passed, 9 skipped`.
- New tests: `tests/test_knowledge_ops.py` (43: order, artifacts, retries/sleeps `[60]` and `[60, 300]`, non-retryable once, dependents `not_run`, page failure usable, one-hour stop with a hung child, wait capped at time left, summary at most 15 lines, no title/URL/exception text, lock, status `missed`/`interrupted`, on/off, adapters call the accepted entry points, no merge/decision/release reference) and `tests/test_knowledge_ops_commands.py` (10: the automated owner walkthrough through `scripts/init.sh` with a fake `launchctl` and fake step program; missing prerequisite exit 2, on twice, Ollama-down failure, recovery to `review_ready`, status, off, lock exit 3, misuse).
- Updated tests: `test_health_metrics.py` (4 new families, unreadable/missing folder, interrupted), `test_monitoring_files.py` (rule, 30 h threshold, panel sentences), `test_local_rag_service.py` (env only when the folder exists), `test_qa_alerts.py` (label default unchanged), `test_source_update_scheduler.py` (trigger, page example).
- Sample `summary.txt` from a fake run with classify failing (counts only; paths shortened):
  `Knowledge update run on 2026-11-08 10:20 (took 6 min).` / `How it went: something failed.` / `Sort them by relevance: failed after 3 tries. The local drafting program (Ollama) is not running. First thing to do: open Ollama, then run ./scripts/init.sh --knowledge-updates-run again.` / other five steps `done.` / `Counts: 2 new candidates; 2 documents read, 0 failed; 1 impact findings; 1 validity proposals.` / `Nothing was published. You approve every change before it goes live.`
- Generated plist: `Label org.manijero.knowledge-ops`, `ProgramArguments [~/Manijero/backend/.venv/bin/python, ~/Manijero/backend/scripts/knowledge_ops.py, run, --scheduled]`, `StartCalendarInterval {Hour 10, Minute 20}`, `EnvironmentVariables {PATH}` only, logs under `~/manijero/knowledge-ops/logs/launchd.log`.
- Validator, 2026-11-08: `accept`; reran the focused block `270 passed, 1 skipped`; record in [`docs/validations/knowledge_ops_orchestrator.md`](../validations/knowledge_ops_orchestrator.md).
- Not run: `--verify` (no Android/Desktop, Gradle, or packaging change), any live official-site run, the real `launchctl`.

## Validator checklist

- Every contract scenario maps to a passing named test; the focused block runs unchanged via `./scripts/init.sh --feature knowledge_ops_orchestrator`.
- Run order is discover → classify → ingest → analyze impact → check validity → prepare review; each step calls the accepted entry point, not a copy.
- Retries ≤ 2 per step, waits capped by time left; a failed step is always reported with a fixed code, plain sentence, and next step; nothing is silently skipped.
- The one-hour budget is a hard stop on the injected clock, including a running child.
- Nothing publishes: no merge/decision/release call, `knowledge/` unchanged, `review-ready.json` says `published: false`.
- Summary, ledger, metrics, and dashboard carry counts, fixed codes, ids, and times only.
- Owner commands meet `docs/constraints/operations.md` (one named command, prerequisite check, one `Result:` line, idempotent, owner-guide steps); launchctl touches only `org.manijero.knowledge-ops`; QA alerts unchanged.
- No new dependency, network in tests, real token, `.github/workflows` schedule, or container/QA command change.
- Durable docs updated as listed; limits recorded honestly (dashboard needs the local service; Mac off or asleep means a missed or late run; no freshness claim).
