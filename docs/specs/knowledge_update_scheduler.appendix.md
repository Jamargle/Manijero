# `knowledge_update_scheduler` planning appendix

Planning and verification record for [`knowledge_update_scheduler.md`](knowledge_update_scheduler.md). Re-planned 2026-10-31; the earlier generic template is superseded. `docs/validations/knowledge_update_scheduler.md` (not yet created) will be the acceptance record.

## Repository research

Inspected on 2026-10-31 in the `feature/knowledge_update_scheduler` worktree (clean, HEAD `13b5e9b`):

- `backend/app/source_monitor.py` — `scan(sources, state_path, now=None)` validates an explicit `sources` list (`id`, `url`, `format` rss/json, exact approved host), sends conditional requests through the module-level `_request(source, previous)`, writes `source-monitor-state-v1` atomically (`.tmp` + `os.replace`), and returns `{"scanned_at", "sources": [...], "success"}`. Per-source `failure` strings are fixed, value-safe `MonitorError` messages or `"upstream request failed"`. Calling `scan()` with a subset of sources updates only those records, so a retry can target only failed sources. No retry, lock, or scheduling.
- `backend/scripts/scan_official_sources.py` — CLI, exit `0` all success, `1` any source failure, `2` config/state error.
- `backend/app/source_discovery.py` — `discover(config_path, state_path, now=None)` reads an `official-discovery-config-v1` file whose BOE URL embeds one fixed date (`/datosabiertos/api/boe/sumario/YYYYMMDD`) and BOJA URL one fixed year (`calendar?year=YYYY`). Network goes through the module-level `_fetch(url, accept)`. Per-registry failures become `status: unchecked` with the exception class name; config errors raise `ValueError`. Candidates are deduplicated by issuer+identity hash; repeated identical observations are not appended. BOJA enumerates every bulletin of the year (≤ 400 bulletins, ≤ 160 MiB). FEGA/MAPA are always `unchecked / no_verified_machine_readable_registry`. State writes are atomic but unlocked.
- `backend/scripts/discover_official_sources.py` — CLI, exit `1` only for attempted-registry failures.
- `knowledge/official-discovery-config.example.json` — static example (`20261027`, `2026`); a schedule must therefore render the date/year per run.
- `backend/deploy/systemd/manijero-pilot.service`, `manijero-retention-purge.{service,timer}` — the accepted pattern: header "TEMPLATE, NOT REHEARSED", `Type=oneshot`, `User=manijero`, `ProtectSystem=strict`, `ReadOnlyPaths=/opt/manijero`, one `ReadWritePaths=`, timer `OnCalendar=daily`, `Persistent=true`, `RandomizedDelaySec=15m`; failure surfaces through exit code and `systemctl --failed`.
- `backend/README.md` — monitoring section says "no in-process recurring scheduler, retry loop"; deployment-files table; operational limits ("No ... monitoring service, alerting").
- `docs/specs/hosting_provider_review.md` — selects an owned server + Cloudflare Tunnel, conditionally; `ARCHITECTURE.md` — pilot is prepared, not operating; no host is provisioned.
- `CONSTRAINTS.md` "Knowledge updates and retrieval" — scans write only quarantined candidates; scheduled checks MUST expose last-success, failures, and missed runs and MUST NOT be presented as proof of currency.
- `docs/risks-and-open-questions.md` rows 29 and 67 — scheduling reliability is owned by this feature.
- `.github/workflows/gate.yml` — the only workflow; triggered by `pull_request` only, no `schedule:`.
- `scripts/init.sh` — `--feature <id>` extracts the lines between the verify markers (dropping fences and blank lines) and runs them with `bash -euo pipefail` from the repo root. `--backend-tests [targets]` runs `python -m pytest targets` from `backend/`, resolving a relative `MANIJERO_PYTHON` against the repo root. Baseline: `--backend-tests tests/test_source_monitor.py tests/test_source_discovery.py` → 18 passed.
- Test pattern: `backend/tests/test_source_monitor.py` / `test_source_discovery.py` monkeypatch `_request` / `_fetch`; `test_abstention.py` blocks `socket.socket`. No `conftest.py`.
- Not inspected: any real host, systemd version, or live official endpoint (deliberately — no live calls).

## Host decision

**Selected: owned host + systemd timer template.** Reasons: it is the already-selected pilot host; state and ledger stay in an operator-owned directory outside the repository; `Persistent=true` catches up after downtime; failure surfaces through the existing systemd/journald channel with no secret; nothing runs until the owner copies and enables the units.

**Rejected: GitHub Actions `schedule:`.** Scheduled workflows are best-effort (delayed or dropped under load), are disabled automatically after a period of repository inactivity, and run on the default branch as soon as they are merged — that would make real requests to official sites from a merge, which this feature forbids. State (monitor hashes, candidates, ledger) would have to be committed back to the repository or kept in expiring artifacts, which conflicts with keeping operational state outside `knowledge/` and with human-reviewed canonical changes. Notification beyond the Actions UI would need a stored secret. Repository automation is therefore not the host; no STOP condition applies.

**Cadence rationale (planning assumptions, not live-verified):** BOE publishes a daily summary every day except Sunday; BOJA publishes ordinary issues on working days plus occasional extraordinary issues. Daily monitoring (two conditional requests) and daily BOE discovery (one request per pending date, ≤ 14) match that frequency at negligible load. A BOJA discovery run re-enumerates the whole year (up to ~250+ bulletin requests), so it runs weekly to bound load on `datos.juntadeandalucia.es`; the daily BOJA RSS monitor gives an early change signal in between. 10:20 Madrid avoids scanning before the morning edition; today's BOE date becomes due only after 09:00 Madrid. Human review is the bottleneck, so a ≤ 7-day BOJA lag is acceptable and documented. A validator should confirm the BOE/BOJA publication-calendar assumptions against the official sites manually (not in automated tests).

## Ledger format (`source-update-ledger-v1`)

File `<state-dir>/source-update-ledger.jsonl`, mode `0600`, one JSON object per line, appended with `O_APPEND` + `fsync`, under the run lock. The reader refuses (exit `2`) a malformed line, unknown `schema_version`/`event`, or a file over 10 MiB (README tells the operator to archive and start a new file).

```json
{"schema_version":"source-update-ledger-v1","event":"run_started","run_id":"run-20261028T093000Z-1a2b3c4d","trigger":"manual","started_at":"2026-10-28T09:30:00+00:00","jobs":["monitor","boe","boja"],"forced":false}
{"schema_version":"source-update-ledger-v1","event":"run_finished","run_id":"run-20261028T093000Z-1a2b3c4d","trigger":"manual","started_at":"...","finished_at":"...","outcome":"success",
 "jobs":[
  {"job":"monitor","status":"success","attempts":1,"backoff_seconds":[],"targets":["boe-api","boja-rss"],"succeeded":["boe-api","boja-rss"],"failed":[],"changed":1},
  {"job":"boe","status":"success","attempts":1,"backoff_seconds":[],"targets":["20261028"],"succeeded":["20261028"],"failed":[],"new_or_changed_observations":3,"abandoned_dates":[]},
  {"job":"boja","status":"not_due","attempts":0,"backoff_seconds":[],"targets":[],"succeeded":[],"failed":[]}],
 "unchecked_registries":["fega","mapa"]}
```

- `trigger`: `manual` (default) or `systemd` (the unit passes it).
- `outcome`: `success`, `failure`, `config_error`, `nothing_due`. Job `status`: `success`, `failure`, `config_error`, `not_due`, `not_selected`.
- `failed`: `[{"target": "<source id|YYYYMMDD|YYYY>", "failure": "<existing diagnostic>"}]` — monitor's recorded `failure` string, or discovery's exception class name. No URL, response body, exception message, or path.
- `run_id`: `run-<UTC compact>-<8 hex from secrets>`; injectable for tests.

## Due rules and windows (constants in the module)

| Job | Due when | Targets | Max attempts |
|---|---|---|---|
| `monitor` | no successful monitor job in the last 12 h, or `--force` | all configured source ids (retry: failed ids only) | 3 |
| `boe` | any pending date | non-Sunday dates from max(day after last successful date, today − 13 days) to today (today only after 09:00 Madrid); first run = today only; plus explicit `--boe-date` values (≤ 60 days old, not future, Sunday allowed); `--force` re-adds today | 3 |
| `boja` | no successful BOJA job in the last 156 h, or `--force` | current Madrid year; also the previous year when the last success is in a previous year (cap 2 years) | 2 |

Backoff before attempt 2 = 60 s, before attempt 3 = 300 s. Status thresholds: missed 30 h, interrupted 2 h, stale monitor 36 h / BOE 36 h / BOJA 192 h; abandoned BOE dates look back 60 days. `TimeoutStartSec=90min` in the unit bounds a run.

## Implementation plan and tasks

1. Write `backend/tests/test_source_update_scheduler.py` first from the acceptance scenarios, with an autouse fixture that replaces `socket.socket` and `socket.create_connection` with a function that raises, plus fakes for `app.source_monitor._request` and `app.source_discovery._fetch` that record calls. Inject `now`, `sleep`, and `run_id`. Use `tmp_path` for the state directory.
2. Implement `backend/app/source_update_scheduler.py`: path guard (refuse a state directory inside the repository root, resolved), directory `0700`/files `0600`, lock (`fcntl.flock(LOCK_EX | LOCK_NB)` on `source-update.lock`; failure → `LockedError`), ledger read/validate/append, due-rule and target computation (Madrid date via `zoneinfo.ZoneInfo("Europe/Madrid")`), job runners with target-level retry, discovery-config rendering from `REGISTRIES` into a temp file in the state directory (deleted in `finally`), `evaluate_status`. Monitor config is validated with `validate_sources` before any request; a config/state error (`MonitorError`, `ValueError`, `OSError`, `json.JSONDecodeError`) is a job `config_error` with no retry. Do not modify `source_monitor.py` or `source_discovery.py`.
3. Implement `backend/scripts/run_source_updates.py` (`run`, `status`), mirroring the existing scripts' `sys.path` setup; print the JSON report to stdout; stderr carries only fixed codes/class names. Exit `0/1/2/3` as in the contract.
4. Add `backend/deploy/systemd/manijero-source-updates.service` (`Type=oneshot`, `User=manijero`, no `EnvironmentFile=`, `ExecStart=... run_source_updates.py run --trigger systemd --state-dir /var/lib/manijero/source-updates --monitor-config /etc/manijero/source-monitor.json`, `TimeoutStartSec=90min`, `Nice=10`, journald with `SyslogIdentifier=manijero-source-updates`, hardening as the retention unit, `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`, `ReadWritePaths=/var/lib/manijero/source-updates`, `MemoryMax=512M`, commented `# OnFailure=<operator-provided-unit>@%n.service`) and `.timer` (`OnCalendar=*-*-* 10:20:00 Europe/Madrid`, `RandomizedDelaySec=30m`, `Persistent=true`, `AccuracySec=1m`), each headed "TEMPLATE, NOT REHEARSED, NOT INSTALLED OR ENABLED". Add `backend/deploy/source-monitor.json.example` with the two public endpoints already in the README.
5. Add the repository-safety tests: workflows contain no `schedule:` and no `run_source_updates`; the unit/timer text matches the decisions; the example config passes `validate_sources`; canonical `knowledge/source_catalog.json` and `passages.json` hashes are unchanged across a faked run.
6. Update docs listed in the contract's durable documentation impact. Do not edit `PROGRESS.md` or `feature_list.json` status beyond what the implementer role permits.
7. Run the focused verification and the full backend suite; append evidence below.

### Test list (minimum)

- due run success, ledger pair, state files, exit 0, no knowledge change;
- same-day re-dispatch makes zero fake calls (`nothing_due`); `--force` keeps candidate count and observations;
- transient BOE failure → attempts 2, sleep `[60]`; persistent monitor failure → only failing id retried, sleep `[60, 300]`, last-good hash kept, exit 1;
- BOJA failure stops after 2 attempts;
- catch-up order with Sunday skipped, 14-day cap, before-09:00 rule, abandoned date recorded once, `--boe-date` validation (future/too old → exit 2);
- BOJA year rollover scans both years;
- status: `never_run`, `missed_run`, `interrupted_run`, `stale:<job>`, `last_run_failed:<job>`, healthy exit 0, FEGA/MAPA + `freshness_claim: "none"` always present;
- config errors: invalid monitor config, state dir inside repo, corrupt ledger line, invalid existing monitor state → exit 2, no fetch for that job, no retry;
- lock held by another `flock` → exit 3, ledger unchanged, zero fake calls;
- ledger/report contain no URL, no exception message sentinel (raise an `OSError("SECRET-SENTINEL")` in a fake and assert absence), files mode `0600`;
- CLI `main()` exercised in-process with fakes for `run` and `status`;
- repository guard tests (workflows, unit/timer text, example config).

## Verification plan

1. Focused (published block): `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_source_update_scheduler.py tests/test_source_monitor.py tests/test_source_discovery.py`.
2. Full backend suite: `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests` (no regressions).
3. `./scripts/init.sh --fast` and `git diff --check`.
4. `git status --porcelain knowledge/ .github/` empty; `grep -rn "schedule:" .github/workflows` no match.
5. Manual, optional, only where available: `systemd-analyze calendar '*-*-* 10:20:00 Europe/Madrid'` and `systemd-analyze verify` on a Linux machine. Not required for acceptance; record "not run" if unavailable. No live run against official sites is part of verification.

E2E: not applicable — no app, API, auth, or routing change; unit/integration tests with fakes cover the behavior.

## Evidence to capture

- Exact command outputs and pass counts for steps 1–4.
- One sample faked `run` report and the resulting two ledger lines (from a test `tmp_path`, no real data).
- Confirmation that `source_monitor.py`, `source_discovery.py`, `knowledge/`, `contracts/`, `.github/`, and requirements files are unchanged (`git diff --stat`).
- Honest limits: host not provisioned/rehearsed; systemd templates not installed; calendar assumptions not live-verified; no external dead-man's switch; no live upstream smoke.

## Feature evidence

Implementer self-verification, 2026-10-31, worktree `feature/knowledge_update_scheduler` (uncommitted), macOS arm64, Python 3.12.16 (`backend/.venv`), JDK 21 (Zulu 21.0.11). This is not independent validation.

| Check | Command | Result |
|---|---|---|
| Focused block | `./scripts/init.sh --feature knowledge_update_scheduler` | exit `0`; `48 passed in 0.08s` (30 new scheduler tests + 9 monitor + 9 discovery; baseline 18) |
| Fast tier | `CI=true ./scripts/init.sh --fast` | exit `0`; `:shared:jvmTest` BUILD SUCCESSFUL; backend `968 passed, 1 warning`; "All 9 offline checks passed."; "Fast tier passed." |
| Verify tier | `CI=true ./scripts/init.sh --verify` | exit `0`; fast tier as above, then full tier (Android host tests, Android/Desktop builds) BUILD SUCCESSFUL |
| Whitespace | `git diff --check` | exit `0`, no output |
| Unchanged paths | `git status --porcelain knowledge/*.json contracts/ .github/ backend/app/source_monitor.py backend/app/source_discovery.py backend/requirements*.txt backend/deploy/requirements-production.txt` | empty |
| No schedule | `grep -rn "schedule:" .github/workflows` | no match (exit `1`) |
| systemd syntax | `systemd-analyze calendar` / `verify` | **not run**: no systemd on the macOS verification host |

The full backend suite ran inside the fast tier. The new test module replaces `socket.socket` and `socket.create_connection` with a raising function (autouse), and every upstream call goes through recorded fakes of `source_monitor._request` and `source_discovery._fetch`; no live official-site request was made by any check.

Sample faked run (temporary directory outside the repository, fakes for both network seams, sockets blocked; deleted afterwards). `exit_code_for_run` → `0`; status `{"healthy": true, "alerts": [], "warnings": ["unchecked:fega", "unchecked:mapa"], "freshness_claim": "none"}`. Ledger lines:

```json
{"event":"run_started","forced":false,"jobs":["monitor","boe","boja"],"run_id":"run-20261028T093000Z-1a2b3c4d","schema_version":"source-update-ledger-v1","started_at":"2026-10-28T09:30:00+00:00","trigger":"manual"}
{"event":"run_finished","finished_at":"2026-10-28T09:30:00+00:00","jobs":[{"attempts":1,"backoff_seconds":[],"changed":2,"failed":[],"job":"monitor","status":"success","succeeded":["boe-api","boja-rss"],"targets":["boe-api","boja-rss"]},{"abandoned_dates":[],"attempts":1,"backoff_seconds":[],"failed":[],"job":"boe","new_or_changed_observations":1,"status":"success","succeeded":["20261028"],"targets":["20261028"]},{"attempts":1,"backoff_seconds":[],"failed":[],"job":"boja","new_or_changed_observations":1,"status":"success","succeeded":["2026"],"targets":["2026"]}],"outcome":"success","run_id":"run-20261028T093000Z-1a2b3c4d","schema_version":"source-update-ledger-v1","started_at":"2026-10-28T09:30:00+00:00","trigger":"manual","unchecked_registries":["fega","mapa"]}
```

Implementation choices where the plan left room (recorded for the validator):

- A failed BOE date stays pending while it is inside the 14-day window even when a later date has succeeded (pending = the table's catch-up range plus failed-never-succeeded dates in the window); it is recorded once in `abandoned_dates` when it leaves the window.
- `--force` re-adds today's BOE date only when today is due (after 09:00 Madrid, not Sunday).
- An invalid `--boe-date` is a `boe` job `config_error` (`error: boe_date_invalid`, run exit `2`) recorded in the ledger; the other selected jobs still run. `--boe-date` with `--job` lists that exclude `boe` is an argparse error (exit `2`).
- Job-level config errors carry a fixed `error` code (`monitor_config_missing`, `monitor_config_invalid`, `monitor_state_invalid`, `discovery_state_invalid`, `boe_date_invalid`). Run-level refusals (state directory inside the repository, corrupt/oversized/unreadable ledger) write nothing and print only `{"error": "<code>"}` to stderr.
- `interrupted_run` and `missed_run` look at the most recent `run_started` only; `last_run_failed:<job>` uses the job's most recent attempted (`success`/`failure`/`config_error`) record; a job that has never succeeded is `stale:<job>`. Consequently a run restricted with `--job` still exits `1` while another job is stale.
- State files written by the wrapped commands are chmod-ed to `0600` after each call; the state directory is created `0700` (an existing directory's mode is left unchanged).

Limits: no host is provisioned; the systemd templates are not installed, enabled, or rehearsed, and `systemd-analyze` was not run; the BOE/BOJA publication-calendar assumptions are not live-verified; there is no external dead-man's switch and no alert delivery beyond a failed unit and journald; no live upstream smoke was run (deliberately).

Independent validation, 2026-10-31 (fresh validator, no revise round): verdict **accept**. Focused block 48 passed; `CI=true ./scripts/init.sh --fast` exit 0 (backend 968 passed, 9 offline checks); `CI=true ./scripts/init.sh --verify` exit 0; `git diff --check` clean; no workflow `schedule:`; offline socket-blocked CLI probe confirmed backoff, exit codes 0/1/2, ledger content and `0600`/`0700` modes. Three Low findings recorded as limits in [the acceptance record](../validations/knowledge_update_scheduler.md).

## Validator checklist

- [ ] Focused verify block runs unchanged via `./scripts/init.sh --feature knowledge_update_scheduler` and passes; full backend suite passes.
- [ ] No test or check makes a network connection (socket guard present and autouse); no live official-site call anywhere in the evidence.
- [ ] No `.github/workflows` file has `schedule:` or invokes the scheduler; the guard test exists.
- [ ] No secret, token, webhook, notification URL, or private hostname committed; scheduler reads no `pilot.env`; placeholders only in `.example`/commented lines.
- [ ] No new dependency; requirements files unchanged.
- [ ] `source_monitor.py`, `source_discovery.py`, canonical `knowledge/` files, `contracts/`, and `/ask` unchanged.
- [ ] Due rules, windows, attempts, backoff values, and thresholds match the tables above.
- [ ] Retries target only failed items; config/state errors are not retried; exit codes `0/1/2/3` are as specified.
- [ ] Lock prevents concurrent runs; same-day re-dispatch makes no request; `--force` does not duplicate candidates or observations.
- [ ] Ledger is append-only JSONL with the documented fields, `0600`, and contains no URL, content, path, or exception message.
- [ ] `status` reports each alert type, FEGA/MAPA unchecked, and `freshness_claim: "none"`; abandoned BOE dates are visible.
- [ ] Systemd templates are headed not rehearsed / not enabled, match the documented `OnCalendar`, `Persistent=true`, `TimeoutStartSec`, `ReadWritePaths`, and have no `EnvironmentFile=`.
- [ ] Docs updated as listed; no claim of freshness, coverage, SLA, alert delivery, or host rehearsal.
