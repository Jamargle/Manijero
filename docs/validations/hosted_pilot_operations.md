# `hosted_pilot_operations` validation

## Verdict

**Accept — third validation round, 2026-10-27.** The one remaining High finding from the
previous round (a successful `restore` rewrote the canonical corpus as `0600`, unreadable by
the `User=manijero` service account) is repaired and was reproduced as repaired by independent
probes. No new blocking finding was found. The feature satisfies its spec as a **prepared, not
operating** pilot: deployment artifacts, runbook, backup/restore, readiness, guarded access,
and operational limits are implemented and tested locally; no host rehearsal is claimed.

- Feature: `hosted_pilot_operations`
- Spec: [`hosted_pilot_operations.md`](../specs/hosted_pilot_operations.md)
- Implementation record: [`hosted_pilot_operations.appendix.md`](../specs/hosted_pilot_operations.appendix.md)
- Harness state reviewed: `in_progress` in `feature_list.json`; the validator did not edit
  that file. The orchestrator may set it to `accepted` (see “Acceptance record status”).
- Reviewed scope: `backend/app/pilot_config.py`, `pilot_guard.py`, `pilot_logging.py`,
  `pilot_ops.py`, `readiness.py`, the modified `backend/app/main.py`, `backend/app/ask_api.py`,
  `backend/scripts/pilot_ops.py`, `backend/scripts/serve_pilot.py`,
  `backend/tests/test_pilot_operations.py`, `backend/deploy/*`, and the modified
  `backend/README.md`, `README.md`, `ARCHITECTURE.md`, `CONSTRAINTS.md`, `PROGRESS.md`,
  `docs/risks-and-open-questions.md`, `contracts/openapi.yaml`, and this feature's appendix.
  `feature_list.json` was compared with `HEAD`, not edited.

## Checks rerun (real results)

| Check | Result |
| --- | --- |
| `./scripts/init.sh --feature hosted_pilot_operations` | Exit `0`; backend suite **816 passed**, 1 Starlette/httpx deprecation warning. |
| `./scripts/init.sh --fast` | Exit `0`; **All 9 offline checks passed. Fast tier passed.** |
| `git diff --check` | Exit `0`; no whitespace errors. |
| `cd backend && .venv/bin/python -m pytest tests/test_pilot_operations.py -q` | Exit `0`; **34 passed**, 1 warning. |
| `git status --porcelain knowledge/` | Empty; the validator did not touch the canonical corpus. |
| `git ls-files -s knowledge/source_catalog.json knowledge/passages.json` | Both `100644` (`6754bf2…`, `419db0b…`). |
| `stat` on the canonical files | Both mode `644` (`-rw-r--r--`). |
| `git hash-object` vs `HEAD:` blobs | Identical for both files; the permission repair changed mode only, not content. |
| `git status --porcelain .local-run.log` | Empty; the local rehearsal transcript is absent. |
| Scope probe: `feature_list.json` vs `HEAD` | Only `hosted_pilot_operations` changed (`not_started` → `in_progress`); board counts 59 accepted / 1 in progress / 8 not started; no id, spec, dependency, or validation path changed elsewhere. |
| Untracked inventory | Only the expected new feature files plus this validation record (`backend/app/pilot_*.py`, `readiness.py`, `backend/deploy/`, `backend/scripts/pilot_ops.py`, `serve_pilot.py`, `backend/tests/test_pilot_operations.py`). |

## Independent repair verification

Nine assertions in a throwaway probe script (temporary directories outside the repository,
reviewed fixture corpus, synthetic values, no server left running) all passed:

1. A target catalog at `0600` plus a target passages file at `0644` restore to `0644` both,
   and `_service_readable` returns true for each.
2. A restore with **absent** targets under `umask 077` still writes both as `0644`
   (i.e. the restrictive umask does not leak into the canonical artifacts).
3. A backup tree remains `0700` directories / `0600` files (5 entries in the probe), so the
   readability change did not widen backup permissions.
4. A simulated failure on the second write raises `restore_write_failed`, restores the first
   target's prior bytes **and** its `0640` mode, and leaves the second target's prior bytes
   and `0600` mode untouched.
5. A forced `0600` canonical write raises `corpus_not_readable` and rolls both targets back
   to their prior bytes and `0640` modes.
6. `_service_readable` rejects `0600` and `0640` and accepts `0644`.
7. Both worktree canonical artifacts are `0644` (checked separately with `stat`).

Code paths that make this hold, re-read in the diff:

- `backend/app/pilot_ops.py:53` defines `CANONICAL_CORPUS_MODE = 0o644`;
  `_read_prior` (lines 548–566) records bytes, mode, uid, and gid; `_write_canonical`
  (581–595) always writes `0644` and passes the prior owner best-effort; `_restore_prior`
  (569–578) reapplies the prior mode with the prior bytes; `_service_readable` (598–606)
  requires all three read bits; `_write_atomically` (609–638) applies the chosen mode after
  chmod and ignores a denied `chown`, so a non-root restore still ends `0644`.
- `restore_backup` (267–326) validates the catalog/passages pair **before** the first write
  (291–292), snapshots prior state (298), writes both files, then fails closed with
  `corpus_not_readable` and rolls back if any written file lacks a read bit (300–313).
- `backend/tests/test_pilot_operations.py` grew from 29 to **34** tests and covers the
  round-trip `0644` result, a `0600` source becoming service-readable, the `umask 077` path,
  prior-mode preservation on a failed second write, and the `corpus_not_readable` rollback.

## Prior findings

| Prior item | Third-round result |
| --- | --- |
| **High** — restore left the corpus unreadable to `User=manijero` | **Resolved.** Restored artifacts are always `0644`, prior owner is reapplied best-effort, the command re-checks all read bits and fails closed with rollback, and the runbook checks `sudo -u manijero test -r` on both files before start. Reproduced in probes 1, 2, 5, 6, 7. |
| Clients-file ownership/mode path | **Resolved as far as a same-account rehearsal can show.** Docs/unit specify `root:manijero 0750` and `manijero:manijero 0600`; code accepts owner `0600` and rejects `0640` or a non-traversable directory; the real `sudo -u manijero` check stays host-only. |
| Restore while the service is active | **Resolved.** The CLI refuses `service_running`, proceeds when inactive, and warns when systemd is absent; the README stops the unit before restore and re-checks after. |
| Backup could carry credentials | **Resolved.** Allowlist basenames, credential-marker scan, owner-only tree, and no-tree refusals hold; backup files remain `0600`. |
| Restore atomicity/validation wording | **Resolved without overclaim.** The pair is validated before the first write; replacement is per file; README and `CONSTRAINTS.md` state that a crash between replacements can leave a mixed pair and is recovered by re-running the verified restore. No pair-atomicity or owner-preservation guarantee is claimed; owner preservation is explicitly best-effort. |
| Invalid backup campaign | **Resolved.** Non-four-digit campaigns are refused before a tree is created, from API and CLI. |
| Status/documentation drift | **Resolved for this handoff.** The post-acceptance 60/68 board sentence is present, and the appendix records the third repair round. The first “board shows … in_progress” sentence is a dated snapshot the orchestrator refreshes when it sets `accepted`; the appendix's “Independent revalidation is still pending” line sits in the first-round section and is historically scoped. |
| Token strength, last-client revocation, support path | **Resolved.** 32-character minimum, `last_client_refused`, a documented pre-pilot support path with no invented address/SLA, and an explicit “unauthenticated failures are not rate-limited” limit. |
| Local rehearsal transcript | **Resolved.** `.local-run.log` is absent. |

## Findings

No Critical, High, or Medium finding remains. Two low-severity notes, neither blocking:

- **Low — runbook check not executable here.** `sudo -u manijero test -r` needs a
  passwordless user switch that this environment does not provide. The probes used
  same-account `stat`/read checks plus the all-read-bits rule, and the docs honestly label
  the cross-user run as host-only. The orchestrator/owner must run the documented check on
  the real host before the first start.
- **Low — `_service_readable` cannot prove parent-directory traversal.** It checks the file's
  mode only. The README states this and makes the cross-user `test -r` the authoritative
  check, which covers traversal.

## Independent security assessment

- No Critical/High remote authentication or data-exposure finding: the pilot profile enforces
  bearer authentication before `/ask`, compares SHA-256 digests in constant time, bounds the
  body before the route, applies a per-client sliding-window limit, disables interactive
  docs/OpenAPI, returns generic `401`/`413`/`429`/`500` bodies, and logs only request
  metadata. Focused tests reproduce the `401`/`413`/`429` boundaries and metadata-only logs.
- The fixed restore path removes an operator-induced availability failure without widening
  access: only the canonical public corpus becomes `0644`; the clients file, `pilot.env`,
  and the whole backup tree stay `0600` under `0700` directories (probe 3).
- Residual security notes, documented and unchanged: `/ready` is unauthenticated and
  re-reads the corpus per request; unauthenticated `401` guesses are not rate-limited; rate
  limits are per worker and reset on restart; the backup secret check is a basename allowlist
  plus known content markers, not a full secret scanner.
- No real secret, provider credential, token, or personal data appears in the diff or probe
  output, and no `knowledge/` content changed.

## Documentation and harness state

- `backend/README.md:301-330` states `0644`, best-effort prior-owner preservation, backup
  files at `0600`, the fail-closed `corpus_not_readable` behaviour, and the
  `sudo -u manijero test -r` checks before start; `:313-315` states the per-file replacement
  and crash re-run limit. `backend/deploy/systemd/manijero-pilot.service:23-26` carries the
  same permission contract. `CONSTRAINTS.md:475-490` makes service-account readability a
  durable MUST and states that a crash can leave a mixed pair.
- `ARCHITECTURE.md` keeps the prepared-but-not-operating boundary; `PROGRESS.md` carries the
  current board and the 60/68 post-acceptance sentence; `docs/risks-and-open-questions.md`
  keeps the open host/privacy limits.
- The systemd unit and tunnel template remain **unrehearsed templates**. `AGENTS.md` was not
  changed, as the spec intended.

## Limits of this validation

- No owned server, systemd installation, `cloudflared`/Cloudflare account, domain, DNS,
  tunnel, TLS handshake, provider-log configuration, R2 bucket, external monitor, alert,
  status page, support agreement, or SLA was used. No host release rollback was rehearsed;
  only local backup/restore paths against temporary copies were exercised.
- The literal `sudo -u manijero test -r` and a cross-user restore were not executed here;
  the same-account mode probes and the all-read-bits rule stand in, and the docs retain this
  as a host-only limit.
- Restore replaces the two files one at a time, not as a single pair swap; a crash between
  replacements can leave a mixed pair and is recovered by re-running the verified restore.
- The earlier two-worker probe confirms startup and probing, not capacity, latency,
  concurrency headroom, cost, or exact per-worker allowance distribution.
- Android/Desktop still cannot send a bearer token, so the current app cannot use the pilot
  profile until that prerequisite outside this feature lands.
- `pilot_privacy_readiness` and owner hardware attestation remain blocking per the
  2026-10-27 decision. Nothing in this record should be read as a real deployment, tunnel/TLS
  setup, provider account, external monitoring, measured capacity, SLA, or rehearsed host
  rollback.
- No real-user question, land value, note, or token was used, logged, or sent anywhere.
  Probe files were temporary and outside the repository.

## Acceptance note

All checks listed above were run in this round with the stated results; none were inferred
from the implementer's summary. The only unexecuted step is the cross-user `test -r`, which
requires the real host and is documented as such rather than claimed.

## Acceptance record status

**Accepted by independent validation on 2026-10-27.** The orchestrator may set
`hosted_pilot_operations` to `accepted` in `feature_list.json`, record this evidence in the
appendix's “Feature evidence” section, add one pointer line to
`docs/progress/session-log.md`, and refresh the dated board snapshot in `PROGRESS.md`
(59 accepted / 1 in progress → 60 of 68 accepted, 8 not started). This validator did not
edit `feature_list.json`, stage, or commit anything.
