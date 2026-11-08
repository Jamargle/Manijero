# Feature Spec: `knowledge_ops_orchestrator`

## Source metadata

- `id`: knowledge_ops_orchestrator · `area`: operations · `depends_on` (all accepted): knowledge_update_scheduler, relevance_classifier, validity_checker, official_page_change_monitor, knowledge_update_review_pr · `status` at planning: not_started.
- User-visible behavior: one scheduled, budgeted, retryable job runs the whole knowledge update cycle (discover, classify, ingest, check validity, analyze impact, prepare review), stops at "ready for review", writes a short plain-language summary, and shows its last result on the health dashboard.
- Verification: offline automated tests with fake steps, fake clock, fake `launchctl`, sockets blocked, and fake tokens only; an automated command walkthrough replaces the owner walkthrough.
- Notes — owner decisions (2026-11-08, verbatim intent):
  - The run starts on a schedule, reusing `knowledge_update_scheduler` (its daily 10:20 cadence and its `run_updates` entry point).
  - Hard budget: stop the whole run after one hour.
  - Each step may retry 2 times; on final failure, report the error for review and fixing (no silent skip).
  - At the end, write a short plain-language summary of how the run went and add an entry to the monitoring dashboard.
  - Stop at review ready: the owner approves before anything goes live; the orchestrator never publishes.
  - No owner walkthrough unless strictly necessary; prefer automated acceptance checks. The `docs/constraints/operations.md` walkthrough MUST is met by `test_knowledge_ops_commands.py`, which runs every documented command through `scripts/init.sh` exactly as the owner guide writes it, including one missing-prerequisite case and one recovery.
- Planning decisions (this spec): run order follows data dependencies (validity needs the impact report), so it is discover → classify → ingest → analyze impact → check validity → prepare review. The schedule runs as a launchd user agent on the owner's Mac (the scheduler's systemd units target a host that does not exist). Owner commands and summary copy are English, like every existing owner command.

## Goal

Let the owner keep the knowledge update cycle running unattended on their Mac with one command, see in plain words how each run went, and never have anything reach answers without their approval.

## Non-goals

- No publish, merge, decision, reindex, release, deploy, or write to `knowledge/`; no call to `review_package.merge`/`record_decision` or `knowledge_release` publish.
- No authoring of `knowledge-update-proposal-v1` files and no automatic review packages: proposals are human legal judgment; `knowledge_review.py prepare` stays the manual next step (hosted PRs are `hosted_review_pull_requests`).
- No change to the accepted step behavior, schemas, `/ask`, `contracts/`, the container or QA commands, or the systemd templates; no GitHub Actions schedule.
- No new dependency, notification channel, or freshness/coverage claim.

## Job story

When new official PAC material may have appeared, I want my Mac to check, sort, download, and analyze it every day within an hour and tell me plainly what is ready for my review or what broke, so I can approve updates without running each tool myself.

## Acceptance scenarios

### 1. Turn on, off, and check the schedule
Given the backend tools are set up · When the owner runs `./scripts/init.sh --knowledge-updates-on` · Then it creates `~/manijero/knowledge-ops/` (`0700`) with the monitor and page configs copied from committed examples, installs the launchd agent `org.manijero.knowledge-ops` (daily 10:20 local time, no `MANIJERO_*` or secret in the plist), and ends with one `Result:` line; re-running reports "already on" and changes nothing. `--knowledge-updates-off` removes only that agent and keeps the folder and history. `--knowledge-updates-status` says on/off, the last run's outcome, finish time, and summary path, and warns `missed` (no run started in 30 h while on) or `interrupted` (started, never finished); exit `0` healthy, `1` otherwise.

### 2. A full run stops at review ready
Given fake steps that all succeed and a fake clock · When `--knowledge-updates-run` (or the schedule) starts a run · Then the steps run once each in order, each in its own child process, the run folder `runs/<run_id>/` holds every step report plus `review/REVIEW.md` and `review/review-ready.json` (`published: false`, `requires_owner_approval: true`), the ledger gains one `run_started` and one `run_finished` (`outcome: review_ready`), `knowledge/` bytes and any release root are unchanged, and the exit code is `0`.

### 3. Retries, then a reported failure
Given a step that fails once and then succeeds · Then it reports `attempts: 2` and the injected sleep received `[60]`. Given a step that always fails with a retryable failure · Then it is attempted 3 times (sleep `[60, 300]`), is reported `failed` with a fixed code, one plain sentence, the first thing to do, and the log path; steps that need its output are reported `not_run: earlier step failed` (never omitted); independent steps still run (classify failing does not stop ingest); the outcome is `failed` and exit `1`. A non-retryable failure (bad configuration or input) is attempted once and reported the same way.

### 4. One-hour hard budget
Given a fake clock and a step child still running when 60 minutes have passed since the run started · Then that child is stopped (terminate, then kill after 10 s), it is reported `stopped_at_time_limit`, no further attempt or wait starts, later steps are `not_run: time limit`, the summary and `run_finished` are still written, outcome `stopped_at_time_limit`, exit `1`. A retry wait is never longer than the time left.

### 5. Plain-language summary
After every finished run, `runs/<run_id>/summary.txt` and `latest-summary.txt` hold at most 15 lines: when it ran and how long it took, one line per step (done / failed after N tries, with the first thing to do / not run, and why), counts only (new candidates, relevant/unsure/not relevant, documents ingested or failed, impact findings, validity proposals), what is waiting for review, and the fixed line `Nothing was published. You approve every change before it goes live.` The run command prints the same summary and one `Result:` line. No titles, URLs, document text, or exception text appear in the summary, ledger, or metrics.

### 6. Dashboard entry
Given the local answer service runs with `--local-rag-start` and the knowledge-ops folder exists · Then `GET /metrics` carries `manijero_knowledge_ops_configured`, `_readable`, `_last_run_outcome{outcome=...}`, and `_last_run_finished_timestamp_seconds`, and the dashboard shows a "Knowledge updates" row with one plain-language check: OK (last run `review_ready` within 30 h), Warning (last finished run older than 30 h), Problem (last run `failed`, `stopped_at_time_limit`, or `interrupted`), neutral `Not set up yet` / `No information yet`. Each state names the first thing to do (`--knowledge-updates-status`).

### 7. Fail closed and stay single
Given the folder is missing, the backend environment is missing, or `launchctl` is absent · Then nothing changes, one plain sentence names the problem and its one fix command, exit `2`. Given another run holds `knowledge-ops.lock` · Then a second run starts nothing, writes no ledger line, says a run is already in progress, exit `3`.

## Technical approach

- `backend/app/knowledge_ops.py` (stdlib only): constants (`BUDGET = 1 h`, `MAX_ATTEMPTS = 3`, backoff reused from `source_update_scheduler.BACKOFF_SECONDS`, `MISSED_AFTER = 30 h`); `run_cycle(home, ports, trigger)`; `status(home, ports)`; ledger `knowledge-ops-ledger-v1` (JSON Lines, `O_APPEND`, `0600`); `fcntl` lock; summary renderer; ports dataclass (clock, sleep, step runner, launchctl, output) so tests inject fakes. `as_of` is the Europe/Madrid date at run start.
- Step adapters call the accepted entry points unchanged: discover = `source_update_scheduler.run_updates` (state `<home>/source-updates`, trigger `knowledge_ops`) then `page_monitor.run`; classify = `relevance_classifier.classify` with the pinned `OllamaTransport`; ingest = `document_ingestion.ingest`; analyze impact = `change_impact.analyze` + `write_report` over the repository catalog, passages, and `pac_answer_eval.json` (read-only); check validity = `source_validity.check_validity` + `write_report`; prepare review = `REVIEW.md` (counts, candidate ids, `candidate_admission_issue` codes, report links, the manual `knowledge_review.py prepare` next step) and `review-ready.json` with report SHA-256 digests.
- Each attempt runs as a child `backend/scripts/knowledge_ops.py step <name> --run-dir <dir>` with timeout = time left; the child writes `steps/<name>.json` (`ok` | `failed` + fixed code + `retryable`). Tracebacks go only to `<home>/logs/knowledge-ops.log` (`0600`).
- `backend/scripts/knowledge_ops.py` ops `on|off|run|status|step`; `scripts/init.sh` dispatches `--knowledge-updates-on|-off|-run|-status` like the `--qa-alerts-*` block. The launchd agent reuses `qa_alerts.SystemLaunchctl` with a new optional `label` argument (default unchanged).
- `health_metrics` reads `MANIJERO_KNOWLEDGE_OPS_STATE_DIR` like `MANIJERO_SOURCE_UPDATE_STATE_DIR`; `local_rag_service` adds it to the allowlisted environment only when the folder exists. Rule `manijero:status_knowledge_updates` and its panel follow the `monitoring_dashboard` code scheme; the 30 h threshold lives in `thresholds.json`.

## Expected file changes

- Create: `backend/app/knowledge_ops.py`, `backend/scripts/knowledge_ops.py`, `backend/deploy/page-monitor.json.example`, `backend/tests/test_knowledge_ops.py`, `backend/tests/test_knowledge_ops_commands.py`, `docs/owner-guide/knowledge-updates.md`.
- Modify: `scripts/init.sh` (dispatch + usage), `backend/app/source_update_scheduler.py` (`TRIGGERS` gains `knowledge_ops`), `backend/app/qa_alerts.py` (optional `label`), `backend/app/health_metrics.py`, `backend/app/local_rag_service.py`, `backend/monitoring/{thresholds.json,prometheus/rules.json,grafana/dashboards/manijero-health.json}`, and the matching tests (`test_health_metrics.py`, `test_monitoring_files.py`, `test_local_rag_service.py`, `test_qa_alerts.py`, `test_source_update_scheduler.py`).

## Visual design impact

App UI: none. The dashboard row follows `monitoring_dashboard`: state word always in the text, readable at 200 % zoom.

## Durable documentation impact

- `docs/owner-guide/knowledge-updates.md`: create (≤60 lines: on, run now, status, off, reading the summary, a table of reachable messages); list it in `docs/owner-guide/README.md`; add the dashboard row to `docs/owner-guide/monitoring.md`.
- `backend/README.md`: update — "Knowledge update runs" section, ≤30 lines.
- `ARCHITECTURE.md`: update — one line for the orchestrator and its launchd schedule.
- `docs/constraints/answers-and-knowledge.md`: update — orchestrated runs never publish, merge, or write `knowledge/`; the launchd agent is an operator-installed host unit. `docs/constraints/operations.md`: update — launchctl only for `org.manijero.knowledge-ops`; one-hour hard budget.
- `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`: update — dashboard entry only while the local service runs; Mac off means missed runs.
- `AGENTS.md`, `CONSTRAINTS.md` index, `DESIGN.md`, `contracts/`: not needed.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_knowledge_ops.py tests/test_knowledge_ops_commands.py tests/test_source_update_scheduler.py tests/test_health_metrics.py tests/test_monitoring_files.py tests/test_local_rag_service.py tests/test_qa_alerts.py -q
```
<!-- verify:end -->

## Appendix

See [`knowledge_ops_orchestrator.appendix.md`](knowledge_ops_orchestrator.appendix.md) for research, plan, verification plan, evidence, and the validator checklist.
