# `knowledge_update_scheduler` acceptance

## Verdict

**Accepted** on 2026-10-31, by independent validation, with no revise round.

## Independent verification

- `./scripts/init.sh --feature knowledge_update_scheduler` — passed (exit 0); 48 passed
  (30 new `test_source_update_scheduler.py`, 9 `test_source_monitor.py`, 9 `test_source_discovery.py`).
- `CI=true ./scripts/init.sh --fast` — passed (exit 0); `:shared:jvmTest` BUILD SUCCESSFUL, backend
  968 passed (1 third-party deprecation warning), "All 9 offline checks passed".
- `CI=true ./scripts/init.sh --verify` — passed (exit 0); fast tier then full tier BUILD SUCCESSFUL.
- `git diff --check` — clean. `knowledge/*.json`, `contracts/`, `.github/`, `source_monitor.py`,
  `source_discovery.py`, and the requirements files are unchanged (only a one-sentence
  `knowledge/README.md` note). `grep -rn "schedule:" .github/workflows` — no match.
- Imports are standard library plus the existing monitor/discovery modules; no new dependency.
  No secret, token, webhook, or notification endpoint in the new code, units, or example config.
- Offline CLI probe (Python `-I`, sockets and DNS blocked, shipped example config, temp state dir,
  injected sleep): `status` on an empty dir → exit 1 `never_run`; full `run` with every upstream
  unreachable → exit 1, backoff `[60, 300]` monitor, `[60, 300]` BOE, `[60]` BOJA, exactly two ledger
  lines with no exception text, URL, or path; ledger, state, and lock files `0600`, state dir `0700`;
  `last_run_failed:*` and `stale:*` for all three jobs. Out-of-window `--boe-date` → exit 2
  `boe_date_invalid`; state dir inside the repository → exit 2 `state_dir_inside_repository`;
  non-allowlisted monitor config → exit 2 `monitor_config_invalid` with no retry sleeps.
- Code review against the spec tables: attempts 3/3/2, backoff 60/300 s, due rules 12 h / 156 h /
  14-day BOE window / 09:00 Madrid / 60-day manual limit, thresholds 30 h / 2 h / 36 h / 36 h / 192 h;
  retries target only failed items; non-blocking `flock` taken before any ledger access (locked run
  exits 3 with no fetch or write); `O_APPEND` + `fsync` ledger with strict read validation;
  `freshness_claim: "none"` and FEGA/MAPA unchecked in every status report.
- Systemd templates headed "TEMPLATE, NOT REHEARSED, NOT INSTALLED OR ENABLED"; no `EnvironmentFile=`
  or `Environment=`; `OnFailure=` is a commented placeholder only.

## Accepted scope and limitations

`backend/scripts/run_source_updates.py run|status` runs the existing configured-source monitoring
and BOE/BOJA registry discovery with per-job due rules, targeted retries with backoff, a
single-run lock, and an append-only metadata-only run ledger, and reports `never_run`,
`missed_run`, `interrupted_run`, `last_run_failed:<job>`, and `stale:<job>` alerts. Failures surface
as a non-zero exit (failed systemd unit plus journald); no secret-bearing notification exists. The
owned-host daily timer (10:20 Europe/Madrid, `Persistent=true`) ships as disabled templates only.

Honest limits:

1. No host is provisioned; the units are not installed, enabled, or rehearsed, and
   `systemd-analyze calendar`/`verify` were not run (no Linux host available).
2. BOE/BOJA publication-calendar assumptions are not live-verified; no live upstream smoke ran.
3. No external dead-man's switch; alerts reach nobody beyond a failed unit and journald unless the
   operator adds an `OnFailure=` unit.
4. Low finding: a manual `status` between about Sunday 22:30 and Monday's run reports a false
   `stale:boe` (no Sunday BOE edition vs. the 36 h threshold); post-run status is unaffected.
5. Low finding: a deterministic BOJA failure mid-year (malformed bulletin or size cap) is retried
   immediately and again daily until it succeeds (about 2 × 250 requests/day instead of weekly).
6. Low finding: errors outside the handled classes, or a host without Europe/Madrid zoneinfo, crash
   the run and surface later only as `interrupted_run` or a failed unit.
7. Successful automation implies no legal-coverage, freshness, or answer-quality claim.
