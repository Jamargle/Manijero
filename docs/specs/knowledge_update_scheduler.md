# Feature Spec: `knowledge_update_scheduler`

## Source metadata

- **Feature:** `knowledge_update_scheduler` — Run and monitor scheduled source scans (`operations`).
- **Status at planning:** `not_started`; depends on `official_source_monitoring`, `official_source_discovery`, `hosted_pilot_operations` (all accepted). Re-planned 2026-10-31; replaces the earlier generic template.
- **Source behavior:** Run configured-source scans and approved-registry discovery on a documented cadence with retries, backoff, idempotency, run ledger, failure notification, and manual dispatch. Scheduled execution is best-effort: surface missed/failed runs and never claim coverage freshness from a cron schedule alone. Assess whether the selected owned server or repository automation is reliable and supported.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

## Decisions recorded by this plan

| Topic | Decision |
|---|---|
| Host | **Owned host, systemd timer template** (`backend/deploy/systemd/manijero-source-updates.{service,timer}`), shipped as an inert, not-installed, not-enabled template like the retention timer. **Repository automation is rejected** (reasons in the appendix): no GitHub Actions `schedule:` workflow is added. |
| Cadence | One daily timer at `10:20 Europe/Madrid`, `RandomizedDelaySec=30m`, `Persistent=true`. Inside a run, each job has its own due rule: feed monitoring daily; BOE sumario discovery for every pending non-Sunday date; BOJA full-year discovery weekly (due when its last success is ≥ 156 h old). |
| Retries / backoff | Retry only the failed targets of a job (source ids, BOE dates, BOJA years). Max attempts: monitor 3, BOE 3, BOJA 2. Fixed backoff before attempt 2 = 60 s, before attempt 3 = 300 s. No retry for configuration/state errors. Sleep and clock are injectable. |
| Idempotency | Exclusive non-blocking `fcntl.flock` lock per state directory; a second run exits `3` without touching state or ledger. A re-dispatch skips jobs that are not due and BOE dates already scanned successfully; `--force` re-runs safely because monitoring compares hashes and discovery deduplicates candidates. |
| Run ledger | Append-only JSON Lines, `source-update-ledger-v1`, at `<state-dir>/source-update-ledger.jsonl` (host: `/var/lib/manijero/source-updates/`). One `run_started` and one `run_finished` record per run; ids, dates, counts, and fixed failure codes only — no URLs, response content, or exception text. |
| Missed / failed / stale | A `status` command (also evaluated at the end of every run) reports alerts: `never_run`, `missed_run` (no run started in 30 h), `interrupted_run` (started, unfinished after 2 h), `last_run_failed:<job>`, `stale:<job>` (last success older than monitor 36 h, BOE 36 h, BOJA 192 h). Warnings: `abandoned_boe_dates`, FEGA/MAPA unchecked. |
| Notification | **No secret by default.** Non-zero exit → failed systemd unit (`systemctl --failed`) plus the JSON report in journald (`SyslogIdentifier=manijero-source-updates`). An operator may add their own `OnFailure=` unit; only a commented placeholder line is shipped. No webhook, email, token, or command hook in code. |
| Manual dispatch | `backend/.venv/bin/python backend/scripts/run_source_updates.py run --state-dir DIR --monitor-config FILE [--job monitor\|boe\|boja ...] [--force] [--boe-date YYYYMMDD ...]`, or `systemctl start manijero-source-updates.service` on the host. |
| Dependencies | None. Standard library only (`fcntl`, `zoneinfo`, `json`, `secrets`). |

## Goal and boundaries

Let the owner run the accepted BOE/BOJA monitoring and discovery commands unattended on the owned pilot host, with bounded retries and a ledger that makes failed, missed, interrupted, and stale runs visible, while every result stays a quarantined review signal.

**In scope:** a scheduler module and CLI (`run`, `status`) wrapping `app.source_monitor.scan` and `app.source_discovery.discover` unchanged; generated per-run discovery configuration (BOE date, BOJA year); due rules, catch-up, retries, lock, ledger, status evaluation; systemd service/timer templates and a public-endpoint monitor config example; offline tests; operator docs.

**Non-goals and safety constraints (mandatory):**

- Tests and verification use fixtures and fakes only. No test, focused verification, or validator check calls an official site; the new test module blocks sockets.
- No `.github/workflows` file gains a `schedule:` trigger or invokes this scheduler; nothing merged runs against real sources or sends a notification by itself. A repository test enforces this.
- No secret, token, webhook, notification endpoint, or private hostname is committed. Placeholders appear only in `.example` files; the scheduler needs no secret and reads no `pilot.env`.
- No new dependency; no change to `source_monitor.py`/`source_discovery.py` behavior, `/ask`, `contracts/`, or canonical `knowledge/` files. No document ingestion, change-impact analysis, review package, reindex, or deploy is triggered.
- No freshness, coverage, or SLA claim: a successful run means only that the listed targets responded. FEGA/MAPA remain unchecked. No external dead-man's-switch: if the timer itself stops firing, only `status`, `systemctl list-timers`, or the next run reveals it.
- No installation or rehearsal on a real host is claimed.

## Job story

When the official BOE and BOJA registries publish new material, I want the owned host to check them every day and tell me plainly when a check failed, was missed, or is stale, so that I can review candidates promptly without trusting a schedule as proof the corpus is current.

## Acceptance scenarios

### Due run succeeds and is recorded

Given an empty state directory outside the repository, a valid monitor config, faked feed and registry responses, and `now = 2026-10-28T09:30Z` (10:30 Madrid, Wednesday), when `run` executes, then monitoring scans every configured source, BOE discovery scans `20261028`, BOJA discovery scans year `2026`, the ledger gains one `run_started` and one `run_finished` (`outcome: success`) record with the same `run_id`, the monitor/discovery state files are written in the state directory, canonical `knowledge/` bytes are unchanged, and the exit code is `0`.

### Repeat dispatch is idempotent

Given that successful run, when `run` is dispatched again the same day without `--force`, then no fake request is made, every job reports `not_due`, the outcome is `nothing_due`, exit `0`. With `--force`, monitoring and BOJA run again and the discovery candidate count and observation lists are unchanged.

### Transient failure retries with backoff; persistent failure notifies

Given a fake that fails the first BOE request and then succeeds, when `run` executes, then the BOE job reports `attempts: 2`, the injected sleep was called with `[60]`, and the job succeeds. Given a fake that always fails one monitor source, then only that source is retried, sleep receives `[60, 300]`, the job reports `failure` with that source's existing diagnostic, other sources' outcomes and the source's last-good hash are preserved, the run outcome is `failure`, and exit is `1`.

### Catch-up after downtime and BOE calendar

Given the last successful BOE date is `20261023` and `now` is `2026-10-28T09:30Z`, when `run` executes, then BOE scans `20261024`, `20261026`, `20261027`, `20261028` in order (Sunday `20261025` skipped) and never more than the 14-day window. Before 09:00 Madrid, today's date is not yet due. A date that has failed and leaves the 14-day window is recorded once in `abandoned_boe_dates` and listed as a status warning; `--boe-date` can re-scan it (≤ 60 days old, not in the future).

### Missed, interrupted, and stale runs are visible

Given ledgers with: no records; a last `run_started` 31 h ago; a `run_started` without `run_finished` 3 h ago; or a BOJA last success 9 days ago, when `status` runs, then it reports `never_run`, `missed_run`, `interrupted_run`, or `stale:boja` respectively and exits `1`; a healthy ledger exits `0`. Every status report includes FEGA/MAPA as unchecked and `freshness_claim: "none"`.

### Fail closed

Given an invalid monitor config, a state directory inside the repository checkout, a corrupt ledger line, or an unreadable state file, then the affected job reports `config_error` without retry (or `status` refuses), nothing is fetched for that job, and exit is `2`. Given another process holds the lock, then `run` exits `3` and makes no request or ledger write.

### Repository safety

Given the repository, when the guard test runs, then no `.github/workflows/*` file contains a `schedule:` trigger or references `run_source_updates`, the timer template contains `Persistent=true` and the documented `OnCalendar`, and the service template has no `EnvironmentFile=`/`Environment=` and writes only `/var/lib/manijero/source-updates`.

## Technical approach

`backend/app/source_update_scheduler.py` owns: constants for jobs, attempts, backoff, windows, and thresholds; `run_updates(state_dir, monitor_config, jobs, force, boe_dates, trigger, now, sleep, run_id)`; `evaluate_status(ledger_path, now)`; ledger read/append (`O_APPEND`, one line per write, `fsync`, files `0600`, directory created `0700`); lock handling; and per-run discovery config rendering from `source_discovery.REGISTRIES` into a temporary file inside the state directory (removed afterwards). Monitoring retries call `scan()` with only the failed source entries. Discovery is called once per BOE date and once per BOJA year; BOJA scans the previous year too when the window since its last success crosses 1 January. "Today" is the `Europe/Madrid` date via `zoneinfo`. State files keep their accepted names and formats: `source-monitor-state.json` and `official-discovery-state.json` inside the state directory. Pending BOE dates come from the ledger's successful dates. The JSON report printed by `run` equals the `run_finished` record plus the post-run `status` block; exit `1` when any job failed or post-run status has an alert.

`backend/scripts/run_source_updates.py` is a thin argparse wrapper (`run`, `status`) with exit codes `0/1/2/3` and value-safe stderr (exception class names only).

## Expected file changes

- Create `backend/app/source_update_scheduler.py`, `backend/scripts/run_source_updates.py`, `backend/tests/test_source_update_scheduler.py`.
- Create `backend/deploy/systemd/manijero-source-updates.service`, `backend/deploy/systemd/manijero-source-updates.timer`, `backend/deploy/source-monitor.json.example`.
- Update `backend/README.md`, `ARCHITECTURE.md`, `CONSTRAINTS.md`, `docs/risks-and-open-questions.md`, `knowledge/README.md` (one sentence), and this spec's appendix evidence. `PROGRESS.md` only at acceptance.
- No change: `backend/app/source_monitor.py`, `backend/app/source_discovery.py`, `knowledge/*.json`, `contracts/`, `.github/workflows/`, requirements files.

## Visual design impact

None. Operator-facing backend only.

## Durable documentation impact

- `backend/README.md`: **update** — new "Scheduled source updates (owned host, best-effort)" section (install, enable/disable, manual dispatch, status, ledger, exit codes, recovery, limits); deployment-files table rows; replace "no in-process recurring scheduler" in the monitoring section with a pointer.
- `ARCHITECTURE.md`: **update** — add the scheduler bullet; monitor bullet points at it.
- `CONSTRAINTS.md`: **update** — MUST NOT add a repository-hosted schedule against official sources; scheduler writes only operational state outside `knowledge/`; tests stay offline.
- `docs/risks-and-open-questions.md`: **update** rows on missed updates and registry scheduling with the chosen host and remaining limits.
- `knowledge/README.md`: **update** one sentence (scheduled dispatch exists as a host template; candidates remain pending).
- `AGENTS.md`: **not needed** — routing unchanged.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_source_update_scheduler.py tests/test_source_monitor.py tests/test_source_discovery.py
```
<!-- verify:end -->

## Appendix

See [`knowledge_update_scheduler.appendix.md`](knowledge_update_scheduler.appendix.md) for repository research, the host decision, ledger schema, implementation plan, verification plan, evidence, and validator checklist.
