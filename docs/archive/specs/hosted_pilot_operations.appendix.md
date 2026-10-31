# `hosted_pilot_operations` Appendix

## Repository research

- `backend/app/main.py` exposes `/health` and `/ask`; `MANIJERO_ACTIVE_CAMPAIGN` is mandatory.
- `scripts/init.sh --backend` starts a development Uvicorn process with reload and is not a production deployment.
- No deployment container, public host, monitoring service, or release runbook is present.

## Implementation plan and tasks

1. Translate `hosting_provider_review` outcome into deployment configuration and secrets handling.
2. Package the service without reload; pin runtime dependencies and validate campaign/corpus before serving.
3. Define access, TLS, liveness/readiness, source update, backup/restore, rollback, and outage-response steps for the owner.
4. Rehearse first deploy, bad config, rollback, restore, and client-unavailable behavior; document actual results.

## Verification plan

- Backend unit/contract tests and a deployment smoke against a staging/pilot endpoint.
- Rehearse restore and rollback from a known-good backup; record provider and campaign settings without secrets.
- No long-running server is started by the standard `init.sh` check tier.

## Evidence to capture

- Provider decision link, deployment revision, health/ask smoke result, campaign, backup/restore and rollback results, owner and contact path.

## Feature evidence

Implementation started 2026-10-27 in the `feature/hosted_pilot_operations` worktree. The
harness status in `feature_list.json` was left `in_progress` by the parent session and was
not edited by the implementer; no acceptance is claimed here.

### What was implemented

- `backend/app/pilot_config.py` — `development`/`pilot` profiles, explicit four-digit
  campaign, closed client-credentials document (`pilot-clients-v1`, SHA-256 digests only,
  POSIX mode `0600` required), body-bound parsing.
- `backend/app/pilot_guard.py` — pure-ASGI guard: bounded request body (`413`), per-client
  bearer authentication (`401`) and sliding-window per-client limit (`429`) in the pilot
  profile, body/query never logged.
- `backend/app/pilot_logging.py` — one JSON request record: method, path without query,
  status, duration, gate.
- `backend/app/readiness.py` — campaign + corpus readiness reusing the accepted
  `ask_api._prepare_runtime_corpus`, with fixed problem codes and no corpus detail.
- `backend/app/main.py` — `create_app(config)` factory, new `GET /ready`, generic `500`
  handler, docs/OpenAPI disabled in the pilot profile, `/health` unchanged (liveness only).
- `backend/app/pilot_ops.py` + `backend/scripts/pilot_ops.py` — `preflight`, `backup`,
  `restore --confirm`, `smoke`, `upsert-client`, `remove-client`, `hash-token`.
- `backend/scripts/serve_pilot.py` — pilot-only launcher: preflight, loopback origin (a
  non-loopback bind needs an explicit acknowledgement), no reload, Uvicorn access log off,
  `--preflight-only` for a service-manager precondition.
- `backend/deploy/pilot.env.example`, `backend/deploy/requirements-production.txt`,
  `backend/deploy/systemd/manijero-pilot.service`,
  `backend/deploy/cloudflared/config.yml.example`.
- `backend/tests/test_pilot_operations.py` — 34 tests for configuration, credentials,
  token strength, guards, readiness, logging, generic errors, preflight, backup/restore,
  backup secret refusal, restore preconditions, restore mode/readability, smoke, and
  launcher refusal.
- `backend/README.md` operator runbook; root `README.md`, `ARCHITECTURE.md`,
  `CONSTRAINTS.md`, `PROGRESS.md`, `docs/risks-and-open-questions.md`, and the `/ask`
  error responses in `contracts/openapi.yaml` updated.
- `backend/app/ask_api.py` — `load_corpus_documents()` accepts optional paths for the
  operator tools; the request path still uses the canonical artifacts and the version/id
  validation is unchanged.

### Executed locally (real results)

Environment: macOS host, Python 3.14.5, existing `backend/.venv`, no Docker/podman, no
host, tunnel, domain, or provider account. All questions used in probes are synthetic or
come from the reviewed corpus; no real-user data was used.

1. `cd backend && .venv/bin/python -m pytest -q` → **803 passed**, 1 deprecation warning
   (first round; the later repair rounds reran the backend suite at **816 passed**).
2. `backend/.venv/bin/python backend/scripts/pilot_ops.py preflight` with no pilot
   configuration → exit `1`, `profile: development`, `problem: pilot_profile_required`,
   `problem: campaign_unavailable`, `corpus_ready: no`.
3. Token/client rehearsal:
   `pilot_ops.py upsert-client --clients-file <tmp>/pilot-clients.json --client-id
   rehearsal-device --requests-per-minute 5 --token-stdin < token.txt` → `clients: 1`; file
   mode `-rw-------`; the file contains the digest and not the token.
4. `MANIJERO_DEPLOYMENT_PROFILE=pilot MANIJERO_ACTIVE_CAMPAIGN=2026
   MANIJERO_PILOT_CLIENTS_FILE=<tmp>/pilot-clients.json
   backend/.venv/bin/python backend/scripts/serve_pilot.py --preflight-only` → exit `0`,
   printed `profile: pilot`, `campaign: 2026`, `configured_clients: 1`,
   `max_request_bytes: 65536`, `bind: 127.0.0.1:8000`, `workers: 2`,
   `limit_concurrency: 64`, `reload: disabled`, `access_log: application-owned`,
   `corpus_ready: yes`.
5. Real pilot process on `127.0.0.1:8765` (`MANIJERO_PILOT_WORKERS=1`), observed:
   `/health` → `200`; `/ready` → `200 {"status":"ready",...}`; `/docs` → `404`;
   `/openapi.json` → `404`; `POST /ask` without a token → `401`; with the token → `200`;
   a 129,066-byte synthetic body → `413 {"detail":"Request body is too large."}`; the sixth
   token-authenticated request inside one minute → `429`. Journal contained only
   `{"event":"request",...}` lines with `method/path/status/duration_ms/gate`; `grep` for
   the synthetic marker and for the token returned 0 hits.
6. Two workers (`MANIJERO_PILOT_WORKERS=2`, port 8766): startup logged a parent plus two
   `Started server process` lines and `/health` → `200` (factory import path works; limits
   are per worker, as documented).
7. `pilot_ops.py smoke --base-url http://127.0.0.1:8765 --token-env <VAR>` → exit `0`,
   `health_status: 200`, `ready_status: 200`, `ask_status: 200`, `ask_state: abstained`.
   Without the token variable → exit `1`, `failure: ask_unauthorized`.
8. Backup: `pilot_ops.py backup --destination <tmp>/backups --config
   backend/deploy/pilot.env.example --campaign 2026` → exit `0`, wrote
   `manijero-pilot-backup-20261027T214947Z/` with `source_catalog.json`,
   `passages.json`, `config/pilot.env.example`, and a manifest of sizes/SHA-256 plus the
   campaign; no credential file was included.
9. Corpus rollback rehearsal on the canonical artifacts: backup taken; one source removed
   from `knowledge/source_catalog.json` (simulated bad deploy) → `/ready` → `503`; `git
   status` showed the modification; `pilot_ops.py restore --backup-dir <backup> --confirm
   --as-of 2026-10-27` → exit `0`, `restored: catalog,passages`, `corpus_ready: yes`,
   `git status --porcelain knowledge/` empty and `/ready` → `200` again. Without
   `--confirm` → exit `2`, `confirmation_required`. With a corrupted backup copy → exit `2`,
   `backup_corrupt`, and canonical knowledge stayed byte-identical.
10. Launcher refusals: `--preflight-only` with the development profile →
   `refused: pilot_profile_required` (exit `2`); with a missing clients file →
   `refused: clients_unreadable` (exit `2`); with campaign `202` →
   `refused: campaign_invalid` (exit `2`).
11. `backend/.venv/bin/python -m pip install --dry-run -r
    backend/deploy/requirements-production.txt` → resolution succeeded against the installed
    environment (fastapi 0.162.0, uvicorn 0.54.0, httpx 0.28.1; Python 3.14.5).
12. `./scripts/init.sh --feature hosted_pilot_operations` (published block:
    `./scripts/init.sh --backend-tests`) → **803 passed**, 1 deprecation warning, exit `0`
    (first round; **816 passed** after the repair rounds).
13. `./scripts/init.sh --fast` → **All 9 offline checks passed. Fast tier passed.**, exit
    `0` (`:shared:jvmTest`, contract examples, backend pytest, source-catalog validation,
    and the five offline evaluators).

### Repair round after review (2026-10-27)

The independent validator returned **revise** (see the
[validation record](../../validations/hosted_pilot_operations.md)). Its two High, three Medium,
and three Low findings were repaired in this round; the feature is still uncommitted and
still not accepted.

Findings addressed:

1. **High — first deploy could not read the clients file.** The runbook, env template, and
   unit comment now specify `/etc/manijero` `root:manijero 0750` and
   `/etc/manijero/pilot-clients.json` `manijero:manijero 0600`; the first-deploy steps run
   `upsert-client` as root, then `chown`/`chmod`, then
   `sudo -u manijero test -r` before preflight. The env template still keeps `pilot.env`
   `root:root 0600` because systemd reads `EnvironmentFile=` before dropping privileges.
   A root-owned clients file still fails closed with `clients_unreadable`.
2. **High — restore could run against a live service.** `backend/README.md` now stops the
   unit before every corpus restore and runs preflight, `/ready`, and `smoke` after the
   restart. The `restore` command queries `systemctl is-active --quiet manijero-pilot` and
   refuses with `service_running` while it is active; when systemd cannot be queried it
   prints an explicit warning and proceeds only for the local/drill case.
3. **Medium — a secret could enter a backup.** `create_backup` accepts only `pilot.env` and
   `pilot.env.example` (`config_file_not_allowed` otherwise) and scans accepted bytes for
   credential markers (`config_file_secret`). The backup root is not modified if it already
   exists; the new backup directory and `config/` are `0700` and every file is `0600`.
4. **Medium — restore overclaimed atomicity.** The backup pair is shape-validated before
   the first canonical write, an unreadable existing target is refused with
   `target_unreadable` and left in place, and a later write failure restores the prior bytes
   and reports `restore_write_failed`. `backend/README.md` and `CONSTRAINTS.md` now state
   per-file atomic replacement, validation before writing, rollback on write failure, and
   re-running the verified restore after a crash between replacements — not an atomic pair
   swap. Exit `2` now consistently means nothing changed; exit `1` means files were replaced
   but readiness is false.
5. **Medium — `backup --campaign 202` produced an unrestorable backup.**
   `create_backup` validates the four-digit campaign before creating any tree and refuses
   with `campaign_invalid`.
6. **Low — status/doc drift.** `PROGRESS.md` now defers counts to `feature_list.json`, lists
   the eight `not_started` features, and states the 60/8 post-acceptance board; its product
   shape names `/ready` and the pilot profile. `ARCHITECTURE.md` describes a prepared,
   blocked path instead of an operating pilot. The production requirements file now prints
   its real path, `backend/deploy/requirements-production.txt`.
7. **Low — token strength, last-client revocation, unauthenticated guesses, support path.**
   `upsert-client` refuses tokens shorter than 32 characters (`token_too_weak`) and the
   runbook generates 48 random bytes. `remove-client` refuses the last enabled client
   (`last_client_refused`); stopping the service is `systemctl stop`. The runbook states
   honestly that unauthenticated failures are not rate-limited and that edge/IP failure
   limiting is a pre-pilot hardening item. The concrete support address is recorded as a
   pre-pilot item (not invented here), with no SLA.
8. **Low — rehearsal transcript.** The untracked `.local-run.log` was deleted and is not
   used as evidence.

Commands and real outcomes in this repair round:

- `./scripts/init.sh --feature hosted_pilot_operations` → **811 passed**, 1 Starlette/httpx
  deprecation warning, exit `0` (the published block runs `./scripts/init.sh --backend-tests`).
- `./scripts/init.sh --fast` → **All 9 offline checks passed. Fast tier passed.**, exit `0`.
- `git diff --check` → exit `0`, no whitespace errors.
- Permission-path rehearsal (no non-root account switch was possible in this environment;
  `sudo` requires a password, so the documented equivalent was used): `install -d -m 0750`
  on the directory, `upsert-client` with a generated token, `chmod 600`, then
  `test -r` → `clients_file_readable: yes`; `serve_pilot.py --preflight-only` as the owning
  account → `configured_clients: 1`, `corpus_ready: yes`, exit `0`. Negative cases: a
  non-traversable directory (the equivalent of the wrong owner/traversal) →
  `problem: clients_unreadable`, exit `1`; a `0640` file → `problem: clients_permissions`.
  The real `sudo -u manijero` form remains host-only and unexecuted.
- Stop/restore/start drill against the canonical corpus with a real pilot process on
  `127.0.0.1:18081`: backup → `/ready` `200` → process stopped (no `/health`) → simulated
  bad catalog deploy (`M knowledge/source_catalog.json`) → a fake active `systemctl` made
  `restore --confirm` exit `2` with `service_running` and changed nothing → without systemd
  the command warned and restored, `corpus_ready: yes`, exit `0`,
  `git status --porcelain knowledge/` empty → process restarted, `/ready` `200`, `smoke`
  exit `0` (`health_status: 200`, `ready_status: 200`, `ask_status: 200`,
  `ask_state: abstained`).
- Backup-with-clients negative probe: `backup --config <pilot-clients.json>` → exit `2`,
  `config_file_not_allowed`, destination tree absent; `grep` for `token_sha256` found no
  tree to match. A normal backup showed `drwx------`/`-rw-------` and `token_sha256_hits: 0`.
  `backup --campaign 202` → exit `2`, `campaign_invalid`, no tree.
- Client commands: a short token → exit `2`, `token_too_weak`; revoking the only client →
  exit `2`, `last_client_refused`.
- Focused tests now **29 passed** (8 added): credentials refusal and secret markers,
  owner-only tree, invalid campaign, shape validation before writes, unreadable target
  refusal, read-only target directory refusal, active-service refusal/inactive/unavailable
  systemd, token minimum, last-client refusal.

Remaining limits after this round: no host, systemd installation, tunnel, TLS edge, domain,
provider account, external monitor, or measured capacity exists; the `sudo -u manijero`
readability check, the systemd stop/restore/start sequence, and a host release rollback were
not executed. The restore command still replaces the two files one at a time (a crash between
replacements is recovered by re-running it), rate limits remain per worker and do not cover
unauthenticated failures, and Android/Desktop still cannot send a bearer token. The clients
file is protected by mode and ownership only; the backup allowlist is by basename plus
content markers, not a full secret scanner. Independent revalidation is still pending.

### Second repair round after revalidation (2026-10-27)

Revalidation returned **revise** once more with one High finding: the restore path used
`mkstemp` (`0600`) plus `os.replace`, so it preserved neither the canonical mode nor the
owner. A `sudo`-run restore therefore left `knowledge/source_catalog.json` and
`knowledge/passages.json` root-owned `0600`, unreadable by the `User=manijero` process.

What changed in this round:

- `backend/app/pilot_ops.py` now has an explicit `CANONICAL_CORPUS_MODE = 0o644` and a
  `_PriorTarget` record of bytes, mode, uid, and gid. `_write_atomically` accepts a mode and
  best-effort uid/gid, sets them on the temporary file before `os.replace`, and rolls back
  with the same metadata. `_write_canonical` always writes `0644`; the prior owner is
  preserved only where `os.chown` is permitted. Backup files remain `0600` and the backup
  tree remains `0700`/`0600`.
- Restore re-checks `_service_readable` (all three read bits) on every written artifact and
  fails closed with `corpus_not_readable`, rolling the prior bytes and mode back, if the
  result is not readable. `restore_write_failed` rollback now restores the prior mode as
  well as the bytes.
- `backend/README.md` and the systemd unit comment state the `0644` guarantee, the
  best-effort owner preservation, and the post-restore `sudo -u manijero test -r` checks
  for both artifacts before starting the service, failing closed if either is unreadable.
  The runbook explains that the in-process check cannot prove parent-directory traversal.
- `CONSTRAINTS.md` now carries the read-mode and fail-closed rule in the durable backup/restore
  MUST, including the cross-user readability check.
- The worktree's own `knowledge/source_catalog.json` and `knowledge/passages.json` were set
  back to `0644`; their content is unchanged (both hash to the committed blobs).

Tests added or extended in `backend/tests/test_pilot_operations.py` (29 → 34):

- the round-trip restore asserts both targets are `0644`;
- a `0600` canonical target becomes `0644` and `_service_readable` returns true;
- a restore under `umask 077` with absent targets still writes both as `0644`;
- a failed second write restores the first target's prior bytes **and** mode (`0640`), and
  the second target is left untouched at its prior mode (`0600`);
- a result written `0600` raises `corpus_not_readable` (exit `2`) and restores both prior
  bytes and modes;
- `_service_readable` rejects `0600` and `0640` and accepts `0644`.

Commands and real outcomes in this round:

- `./scripts/init.sh --feature hosted_pilot_operations` → **816 passed**, 1 Starlette/httpx
  deprecation warning, exit `0`.
- `./scripts/init.sh --fast` → **All 9 offline checks passed. Fast tier passed.**, exit `0`.
- `git diff --check` → exit `0`, no whitespace errors.
- Canonical worktree modes: before `-rw-------` on both artifacts; after
  `chmod 0644` both are `-rw-r--r--`, `git hash-object` matches the committed blobs, and
  `git status --porcelain knowledge/` is empty.
- Mode probe on temporary copies: a `0600` catalog and a `0644` passages file were backed
  up and restored; both came back `0o644` with `service_readable: True` and
  `restore_ready: True`.
- Stop/restore/start drill on **temporary copies** of `backend/app`, `backend/scripts`, and
  `knowledge`, with a real pilot process on `127.0.0.1:18083`: `/ready` `200` → stopped
  (`service_stopped: yes`) → simulated bad catalog deploy → `umask 077` restore with a
  fake inactive `systemctl` → `restored: catalog,passages`, `corpus_ready: yes`, exit `0`,
  both artifacts `-rw-r--r--`, `restored_files_readable: yes`; backup tree stayed
  `drwx------`/`-rw-------` → restart → `/ready` `200` → `smoke` exit `0`
  (`health_status: 200`, `ready_status: 200`, `ask_status: 200`, `ask_state: abstained`).
  The canonical worktree files were not touched by the drill (`knowledge_status_above`
  empty) and remain `0644`.

Remaining limits after this round: `sudo` requires a password in this environment, so the
literal `sudo -u manijero test -r` command and a non-root service account were not run; the
readability checks used the same mode/traversal test as the owning account. No host,
systemd installation, tunnel, TLS edge, domain, provider account, external monitor, or
measured capacity exists, and a host release rollback remains unrehearsed. Restore is still a
per-file atomic replacement, not a pair swap. The owner-preservation step is best-effort:
when the restoring process may not `chown`, the file is root-owned `0644`, which the service
account can read. Rate limits remain per worker and unauthenticated failures remain
unlimited.

### Third validation round — accepted (2026-10-27)

The independent validator re-ran the gates after the second repair round and returned
**accept**, recorded in the
[validation record](../../validations/hosted_pilot_operations.md): `--feature` **816 passed**,
`--fast` all 9 offline checks, 34 focused tests, clean `git diff --check`, and nine
independent permission assertions (canonical output `0644` under a restrictive umask, backup
tree still `0700`/`0600`, prior bytes and mode restored on a failed or unreadable write,
`_service_readable` rejecting `0600`/`0640`). The validator confirmed the worktree canonical
files are `0644` and byte-identical to `HEAD`. No code changed after that verdict; the
orchestrator only persisted acceptance.

### Not executed — blocked or unverified

- No owned server, host attestation, systemd installation, `cloudflared` installation,
  Cloudflare account/domain/tunnel, edge certificate, DNS record, R2 bucket, or provider
  account was created or inspected. The systemd unit and tunnel template are **unrehearsed
  templates**.
- No public hostname, TLS handshake through the edge, or provider-side log configuration was
  seen. Cloudflare log retention remains unassumed.
- Release rollback (`git checkout` of a previous tag plus restart) was not rehearsed because
  no deployed release exists; only the corpus/config restore path was rehearsed locally.
- No capacity, latency, concurrency, or cost measurement exists; `limit_concurrency 64` and
  the per-client limits are protective defaults.
- No external monitoring, alerting, status page, on-call rotation, support-channel
  agreement, or SLA exists.
- The Android/Desktop client cannot send a bearer token, so enabling the pilot profile
  against the current app would show the accepted failure notice; client credential support
  is a remaining prerequisite.
- No qualified privacy/legal review (`pilot_privacy_readiness`) has passed, so no real-user
  question was sent anywhere.
- Independent validation reviewed this feature over three rounds on 2026-10-27, returning
  `revise`, `revise`, then **accept** after the two repair rounds. Acceptance covers the
  prepared, locally tested operations surface only; it is not a deployment, host rehearsal,
  or pilot approval.

## Validator checklist

- [x] Project owner is named as initial operator in the runbook (role named; no personal
      name or support commitment invented). The concrete support address is recorded as a
      pre-pilot item, not fabricated.
- [x] Development reload mode is not used for the hosted service: `serve_pilot.py` refuses
      the development profile and starts Uvicorn with `reload=False` and the access log off;
      the refusal was executed locally.
- [x] Campaign configuration remains explicit and validated: pilot config requires a
      four-digit campaign, backup refuses an invalid `--campaign`, preflight/readiness fail
      closed, and the launcher refuses an invalid value (exercised with `202`).
- [x] The client-credentials file ownership path matches the service account in the runbook,
      env template, and unit comment (`/etc/manijero` `root:manijero 0750`; clients file
      `manijero:manijero 0600`; readability check before preflight). The permission path was
      rehearsed locally with those modes, including `clients_unreadable` for a
      non-traversable directory and `clients_permissions` for `0640`; the real
      `sudo -u manijero` check was **not** run (no non-root account switch available).
- [x] A pilot backup cannot carry credentials: only `pilot.env`/`pilot.env.example` are
      accepted, a credential basename or content marker is refused with a fixed code, the
      tree is owner-only, and the negative probe left no tree or digest behind.
- [x] Restore does not run against a live service and does not overclaim a pair swap: the
      command refuses `service_running`, validates the pair before writing, refuses an
      unreadable target without unlinking it, replaces each file atomically, and documents
      that a crash between replacements is recovered by re-running the verified restore.
- [x] Restore leaves the canonical files readable by the service account: the written files
      are `0644` (backup files stay `0600`), `_service_readable` fails closed with
      `corpus_not_readable` and rolls back, a failed write restores the prior mode, and the
      runbook checks `sudo -u manijero test -r` before starting. The literal non-root check
      was **not** run (`sudo` requires a password here); the drill used the same
      mode/`test -r` evidence as the owning account.
- [ ] Rollback and corpus/config restore were rehearsed — **partially**: the stop/restore/
      start drill with a simulated bad deploy, a real pilot process on loopback, no-confirm,
      corrupted, shape-invalid, unreadable-target, invalid-campaign, secret-config,
      unreadable-result, and active-service cases were exercised locally (temporary copies
      for the mode/readability drill; canonical bytes verified byte-identical). systemd, a
      host, tunnel/TLS, and release rollback are not rehearsed.
- [x] Logs do not contain raw questions or land context: unit tests assert it and the real
      local pilot process logged only method/path/status/duration/gate with 0 marker and 0
      token hits. Provider logs remain unverified.
- [x] Operational limits are stated without an invented SLA, availability target, or
      capacity claim; per-worker rate limits and the unauthenticated-failure gap are
      described honestly.
- [x] Token strength and client lifecycle are enforced and tested: a minimum length at
      `upsert-client` and refusal to revoke the last enabled client.
- [x] Status and architecture text describe the prepared, blocked path and defer counts to
      `feature_list.json`; no live deployment is implied.
