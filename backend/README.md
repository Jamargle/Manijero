# Manijero backend

The local FastAPI service exposes `GET /health` (liveness), `GET /ready` (campaign and
corpus readiness), and a source-grounded `POST /ask`. From the repository root, start it
with the shared startup script:

```sh
./scripts/init.sh --backend
```

The script creates `backend/.venv` when needed, installs/updates the runtime
requirements, sets `MANIJERO_ACTIVE_CAMPAIGN=2026` unless already configured,
and launches Uvicorn with reload enabled, bound to `0.0.0.0` so the Android
emulator can reach the host through `10.0.2.2`. This also makes the development
server reachable from your local network; use a trusted network/firewall, or set
`MANIJERO_BACKEND_HOST=127.0.0.1` to restrict it to this computer (Desktop will
still work, but Android will not). Stop it with `Ctrl+C`. To start it manually
instead, run:

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
MANIJERO_ACTIVE_CAMPAIGN=2026 python -m uvicorn app.main:app --reload --host 0.0.0.0
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"¿Qué información hay?","land_context":{"mode":"general","lands":[]}}'
```

For a physical Android device on the same trusted LAN, use the computer's LAN
address as the Android endpoint when building, for example
`./gradlew :androidApp:assembleDebug -PmanijeroAskBaseUrl=http://192.168.1.20:8000`.
The emulator default remains `http://10.0.2.2:8000`.

For backend tests and artifact validation, install the development dependencies
in a virtual environment instead:

```sh
python -m pip install -r requirements-dev.txt
```

The runtime requirements intentionally do not include `pytest` or `jsonschema`;
the latter is used by the focused PAC answer-evaluation test tier to validate
Draft 2020-12 schemas and artifacts.

Successful response:

```json
{"status":"ok","service":"manijero-backend"}
```

`/health` reports only that this process is serving HTTP requests. It does not
check corpus readiness. `/ask` reads the local `knowledge/source_catalog.json`
and `knowledge/passages.json` artifacts and uses the accepted retrieval,
grounding, abstention, and land-clarification decisions. It does not call a
hosted model or the network. Every `/ask` request requires `MANIJERO_ACTIVE_CAMPAIGN`
to be explicitly set to a four-digit year (for example `2026`); it is never inferred
from today's date or the question. Campaign-neutral and matching campaign sources
may be used. Rotate expired campaign sources and their passages out of the active
artifacts in a reviewed update.

The canonical catalog contains four independently reviewed official sources
and four approved literal passages. `/ask` supports only the three topics in
[`knowledge/pac_coverage.md`](../knowledge/pac_coverage.md) and safely abstains
when it cannot assemble a grounded answer. Fixture-backed answers in tests are
synthetic and do not establish legal coverage. Invalid or unreadable corpus files and
missing/invalid campaign configuration or unsafe corpus data returns a generic `503`; malformed JSON returns `400`,
and valid JSON that violates the request contract returns `422`. Error responses
do not echo question, land, file, or corpus values.

`GET /health` is liveness only. `GET /ready` is the separate readiness check: it
returns `200` with `{"status":"ready","service":"manijero-backend"}` only when
`MANIJERO_ACTIVE_CAMPAIGN` is valid and the reviewed corpus can serve answers as of
today, and `503` otherwise. Neither probe carries corpus values, and a readiness failure
is never rendered as an answer by the clients.

## Private pilot deployment and recovery (prepared, not deployed)

**Status: blocked, never executed on a host.** The [2026-10-27 hosting
decision](../docs/specs/hosting_provider_review.md) selects the owned-server path with a
Cloudflare Tunnel as transport and keeps it conditional on owner attestation, application
access controls, a qualified privacy/legal review, and account-time provider re-checks.
No server, domain, tunnel, TLS edge, provider account, or real-user traffic exists. This
section is the operator procedure for that path; the [feature
appendix](../docs/specs/hosted_pilot_operations.appendix.md) records exactly what was
rehearsed locally and what remains unverified.

Do not route a public hostname to this service, and do not send a real user's question
through it, until the blocking conditions in that decision are met and the
qualified review in `pilot_privacy_readiness` has passed. Fly.io is the only evaluated
fallback and is **not** approved.

### Owner and support path

- The **project owner** is the initial operator: deployment, campaign configuration,
  corpus refresh, backup/restore, rollback, access, and outage response.
- The support path for pilot users is the owner through the pilot invitation channel.
  No support channel, response commitment, SLA, on-call rotation, or third-party support
  plan has been agreed, and this runbook does not claim one.
- **Pre-pilot item:** before the first invitation, record the concrete support address and
  who monitors it in the pilot invitation and the operator log. Do not invent an address
  here; until it is recorded, there is no agreed way for a pilot user to report an outage.
- A person who cannot reach the assistant sees only the accepted plain-Spanish failure
  notice and `Reintentar`; the app never presents a failed request as an answer.

### Topology and what each layer guarantees

```text
client --TLS--> Cloudflare edge/tunnel --> cloudflared (host) --> 127.0.0.1:8000 uvicorn
                                                               --> knowledge/ artifacts (read-only)
```

- **Application (this repository):** authenticates each client with its own bearer token,
  applies that client's per-minute limit, rejects bodies over the configured bound,
  validates campaign and corpus before serving traffic, exposes liveness and readiness,
  and writes one request-metadata log line. A tunnel does not authenticate anything; these
  checks are the access control.
- **Tunnel:** transport and edge TLS only. It removes the public origin and requires no
  inbound port, but it neither authenticates callers nor proves the service is healthy.
- **Host:** OS, disk, power, network, and time. The owner attests these; the repository
  cannot.

Every runtime gate is implemented in the standard library; the only runtime
dependencies stay `fastapi`, `uvicorn[standard]`, and `httpx`.

### Deployment files

| File | Purpose | Rehearsed? |
|---|---|---|
| `backend/scripts/serve_pilot.py` | Production-shaped launcher: pilot profile only, preflight, loopback origin, no reload, access log off. | Locally, yes |
| `backend/scripts/pilot_ops.py` | Operator commands: preflight, backup, restore, smoke, client rotation. | Locally, yes |
| `backend/deploy/requirements-production.txt` | Exact direct runtime pins. | Resolution checked locally |
| `backend/deploy/pilot.env.example` | Configuration template, no secrets. | n/a |
| `backend/deploy/systemd/manijero-pilot.service` | Service unit with preflight as `ExecStartPre`. | **No** |
| `backend/deploy/systemd/manijero-retention-purge.{service,timer}` | Daily purge plus overdue check for the optional retention store. | **No** |
| `backend/deploy/systemd/manijero-source-updates.{service,timer}` | Best-effort daily official-source monitoring and discovery; see "Scheduled source updates". Not installed or enabled. | **No** |
| `backend/deploy/source-monitor.json.example` | Monitor configuration with the two public BOE/BOJA endpoints; no secret. | n/a |
| `backend/deploy/cloudflared/config.yml.example` | Tunnel ingress to the loopback origin. | **No** |

The development launcher (`./scripts/init.sh --backend`) is unchanged and is **not** a
deployment: it enables reload, binds `0.0.0.0`, sets a campaign by default, and has no
authentication. The pilot launcher refuses the development profile.

### Configuration

Read from the process environment; secrets live in an operator-owned file, never in Git.

| Variable | Profile | Meaning |
|---|---|---|
| `MANIJERO_DEPLOYMENT_PROFILE` | both | `pilot` for the hosted service. Any other non-empty value is refused. |
| `MANIJERO_ACTIVE_CAMPAIGN` | pilot (required) | Four-digit campaign. Never inferred; a change is a configuration change plus restart. |
| `MANIJERO_PILOT_CLIENTS_FILE` | pilot (required) | JSON client-credentials file, digests only. `/etc/manijero` is `root:manijero 0750`; the file is owned by the service user (`manijero:manijero`) with mode `0600`. |
| `MANIJERO_PILOT_HOST` / `--host` | pilot | Default `127.0.0.1`. A non-loopback bind also requires `MANIJERO_PILOT_ALLOW_PUBLIC_BIND=1`. |
| `MANIJERO_PILOT_PORT` / `--port` | pilot | Default `8000`; the tunnel ingress must match. |
| `MANIJERO_PILOT_WORKERS` / `--workers` | pilot | Default `2`, maximum `8`. Rate limits are **per worker**. |
| `MANIJERO_PILOT_MAX_CONCURRENCY` | pilot | Default `64`, maximum `512`. A protective placeholder, not a measured capacity. |
| `MANIJERO_MAX_REQUEST_BYTES` | both | Default `65536`, minimum `1024`, maximum `1048576`. |
| `MANIJERO_RETENTION_DB` | both (optional) | Unset = product-improvement retention off. Otherwise an owner-only SQLite path outside the repository (see "Product-improvement retention and the privacy gate"). |
| `MANIJERO_GENERATION_PROVIDER` | both (optional) | `extractive` (default) or `gemini`. `gemini` stays on the extractive path: no client exists and its review gate is closed. Any other value is a preflight problem. |
| `MANIJERO_GEMINI_MODEL` | both (optional) | The exact model the Gemini review approved; only read by the gate. |

The client file is a closed contract:

```json
{"schema_version":"pilot-clients-v1","clients":[
  {"client_id":"pilot-device","token_sha256":"<64 lowercase hex>","requests_per_minute":20,"enabled":true}]}
```

A token must be at least 32 characters; the runbook generates 48 random bytes. A token is
created by the operator and shown once; only its SHA-256 digest is stored. Unknown fields,
duplicate ids, an empty client set, a token shorter than the minimum, or a
group/world-readable file fail closed.

The file must be readable by the **service account**, not only by root. Create the
directory and file as root, then hand the file to `manijero`:

```sh
sudo install -d -o root -g manijero -m 0750 /etc/manijero
sudo /opt/manijero/repo/backend/.venv/bin/python \
  /opt/manijero/repo/backend/scripts/pilot_ops.py upsert-client \
  --clients-file /etc/manijero/pilot-clients.json \
  --client-id pilot-device --requests-per-minute 20 --token-stdin < token.txt
sudo chown manijero:manijero /etc/manijero/pilot-clients.json
sudo chmod 600 /etc/manijero/pilot-clients.json
sudo -u manijero test -r /etc/manijero/pilot-clients.json && echo "clients file readable"
```

`pilot.env` stays `root:root 0600`: systemd reads `EnvironmentFile=` before it drops to
`User=manijero`, so the process never opens it. The clients file is different — it is
opened by the service process, so a root-owned `0600` file is unreadable and preflight
fails closed with `clients_unreadable`. The `chown`/`chmod` pair is required after every
`upsert-client` run as root.

### First deployment (procedure, not yet executed)

1. Install the host prerequisites the owner attested: OS updates, time sync, disk-health
   monitoring, UPS/graceful shutdown, and outbound TCP 7844 for the tunnel connector.
2. Create the service user and checkout:
   `git clone <reviewed origin> /opt/manijero/repo && git -C /opt/manijero/repo checkout <release tag>`.
3. Create the virtualenv and install the pinned runtime:
   `python3 -m venv /opt/manijero/repo/backend/.venv` then
   `/opt/manijero/repo/backend/.venv/bin/python -m pip install -r /opt/manijero/repo/backend/deploy/requirements-production.txt`.
4. Create `/etc/manijero` as `root:manijero 0750`
   (`sudo install -d -o root -g manijero -m 0750 /etc/manijero`), then create
   `/etc/manijero/pilot.env` from `backend/deploy/pilot.env.example` (root, `0600`) and fill
   in the campaign and the clients-file path.
5. Create the client credentials, one command per pilot client, then give the file to the
   service user:
   `sudo ... pilot_ops.py upsert-client --clients-file /etc/manijero/pilot-clients.json --client-id <id> --requests-per-minute 20 --token-stdin < token.txt`
   followed by `sudo chown manijero:manijero /etc/manijero/pilot-clients.json` and
   `sudo chmod 600 /etc/manijero/pilot-clients.json`; deliver the token over an agreed
   private channel and delete the local copy.
6. Validate before serving, as the service user:
   `sudo -u manijero test -r /etc/manijero/pilot-clients.json` then
   `sudo -u manijero /opt/manijero/repo/backend/.venv/bin/python /opt/manijero/repo/backend/scripts/serve_pilot.py --preflight-only`
   Expected: `profile: pilot`, the campaign, the client count, and `corpus_ready: yes`; exit `0`.
   Any `problem:` line means the service must not be started; `clients_unreadable` here means
   the ownership or directory mode is wrong.
7. Install the unit, `systemctl daemon-reload`, `systemctl enable --now manijero-pilot`.
8. Install cloudflared from the provider's official instructions, create the tunnel, write
   `/etc/cloudflared/config.yml` from the template, and run the connector as a service.
   Keep the tunnel credentials out of the repository.
9. Confirm both probes through the public hostname:
   `... pilot_ops.py smoke --base-url https://<pilot host> --token-env PILOT_SMOKE_TOKEN`
   Expected: `health_status: 200`, `ready_status: 200`, `ask_status: 200`, exit `0`.
10. Inspect the journal: one `{"event":"request",...}` line per request with method, path,
    status, duration, and gate only. A question, land value, or token must never appear.
11. Record in the operator log: release revision, campaign, corpus hashes, client count,
    timestamps, and every deviation. This repository's appendix is not a deployment log.

### Campaign change

`MANIJERO_ACTIVE_CAMPAIGN` is explicit configuration. Rotate expired campaign sources and
their passages in a reviewed knowledge change, update the value, restart the service, and
require `preflight --as-of <today>` plus `/ready` to pass again. Do not infer the campaign
from the calendar date, a question, or a land.

### Deploying an update and rolling back

1. Before an update, run `pilot_ops.py backup` (see below) and record the current release
   revision and `curl /ready`.
2. Check out the new release, install `backend/deploy/requirements-production.txt`,
   `serve_pilot.py --preflight-only`, then `systemctl restart manijero-pilot`.
3. Run `pilot_ops.py smoke`. If either probe is not `200` or `/ask` is not a valid state,
   roll back.
4. **Code rollback:** `git -C /opt/manijero/repo checkout <previous release revision>`,
   reinstall the pinned requirements, preflight, restart, smoke. There is no blue/green
   deployment and no second host; a rollback is a restart with the prior files.
5. **Corpus/config rollback:** stop the service, restore the most recent verified backup
   (below), start it again, and re-check `preflight`, `/ready`, and `smoke`. A restored
   corpus that is expired or campaign-mismatched restores the files but stays not-ready;
   that is the honest outcome, not a silent failure. Never restore while
   `manijero-pilot` is still active: the `restore` command refuses with `service_running`
   when systemd reports the unit active.

### Corpus and configuration backup and restore

```sh
backend/.venv/bin/python backend/scripts/pilot_ops.py backup \
  --destination /var/backups/manijero --campaign 2026 \
  --config /etc/manijero/pilot.env
```

The command writes `manijero-pilot-backup-<UTC>/` containing `source_catalog.json`,
`passages.json`, any `--config` files under `config/`, and `backup-manifest.json` with the
campaign, sizes, and SHA-256 of every file. It refuses a `--campaign` that is not a
four-digit year, and a destination inside the repository `knowledge/` tree. The backup
directory and `config/` are owner-only (`0700`) and every file in the tree is mode `0600`;
the destination root is created `0700` if it does not already exist (an existing root is
left as the operator set it).

`--config` is a closed allowlist, not a generic copy. Only `pilot.env` and
`pilot.env.example` may be backed up; any other basename (`pilot-clients.json`,
`credentials-*.json`, keys, certificates) is refused with `config_file_not_allowed`, and
an allowlisted file whose contents contain credential markers (`token_sha256`, a private
key header, `TunnelSecret`, `AccountTag`, …) is refused with `config_file_secret`. A
refused backup writes no tree.

- **Not included:** `pilot-clients.json`, tunnel credentials, or any other secret. Back
  those up separately in a restricted store; the manifest records hashes only.
- Store backups outside the host as well as on it, and restrict access to them.
- **Stop the service before restoring.** The workers read the canonical artifacts on each
  request, so a live restore can serve a mixed pair. Restore only with the explicit flag
  and only while the unit is stopped:

```sh
sudo systemctl stop manijero-pilot
sudo systemctl is-active --quiet manijero-pilot \
  && echo "STILL RUNNING — do not restore" || echo "service stopped"
sudo /opt/manijero/repo/backend/.venv/bin/python \
  /opt/manijero/repo/backend/scripts/pilot_ops.py restore \
  --backup-dir /var/backups/manijero/manijero-pilot-backup-<UTC> --confirm --as-of "$(date +%F)"
sudo -u manijero test -r /opt/manijero/repo/knowledge/source_catalog.json \
  && sudo -u manijero test -r /opt/manijero/repo/knowledge/passages.json \
  || { echo "RESTORED CORPUS NOT READABLE BY manijero — do not start"; exit 1; }
sudo systemctl start manijero-pilot
sudo -u manijero /opt/manijero/repo/backend/.venv/bin/python \
  /opt/manijero/repo/backend/scripts/serve_pilot.py --preflight-only
curl -fsS http://127.0.0.1:8000/ready
/opt/manijero/repo/backend/.venv/bin/python \
  /opt/manijero/repo/backend/scripts/pilot_ops.py smoke \
  --base-url https://<pilot host> --token-env PILOT_SMOKE_TOKEN
```

Restore verifies every recorded hash and size, validates the catalog/passages pair
**before** writing anything, refuses with `target_unreadable` if an existing canonical
file cannot be read, and replaces each file atomically. Each restored canonical artifact is
written mode `0644` (public official text), so a restore run with `sudo` still leaves a
file readable by the `User=manijero` process; the prior owner is preserved where the
process may `chown` it, otherwise the file is root-owned and world-readable. Backup files
inside the backup tree stay `0600`. The command re-checks that every restored file has all
three read bits and fails closed with `corpus_not_readable` if not, rolling the prior
content and mode back first. That check cannot see an untraversable parent directory, so
the explicit `sudo -u manijero test -r` lines above are part of the procedure and must
fail the restore before starting the service. If a later write fails, it attempts to
restore the prior bytes (including the prior mode) and reports `restore_write_failed`; it
does not claim success. It is not a single-transaction swap of the pair: a crash between
the two replacements can leave a mixed pair, so after a crash re-run the same verified
restore (it is idempotent) before starting the service.

Exit `1` means both files were replaced but the service would not be ready as of the
supplied date (an expired or campaign-mismatched corpus); exit `2` means nothing was
changed — missing confirmation, unreadable/corrupt/invalid backup, unreadable prior
target, active service, a result the service account could not read, or a write failure
that attempted to revert. Backed-up `--config` files are verified but **not** written back
over the live configuration; reapply a configuration change by hand and keep the backup as
the reference.

**Restore drill:** rehearse the procedure before the pilot and after any change to this
code, on the host or on a copy: back up, simulate a bad deploy, stop the service, restore,
check `sudo -u manijero test -r` on both artifacts, start it, and confirm `preflight`,
`/ready` `200`, and `smoke`. Expected result: the restored bytes match the manifest, both
artifacts are mode `0644` and readable by the service account, and the journal shows no new
error. Removing `--confirm`, a corrupted backup file, a shape-invalid backup, an unreadable
prior target, a restore while the unit is active, and an expired backup are the negative
cases to exercise.

### Access and rotation

- **Token handling:** create at least 32 characters with `openssl rand -base64 48`
  (64 characters). Keep it out of shell history: `umask 077; openssl rand -base64 48 >
  token.txt`, then `pilot_ops.py upsert-client ... --token-stdin < token.txt`; delete the
  file immediately. `upsert-client` refuses a shorter token with `token_too_weak`.
- Rotate one client with `upsert-client` (same `client_id`, new token), re-apply
  `sudo chown manijero:manijero /etc/manijero/pilot-clients.json` and
  `sudo chmod 600 /etc/manijero/pilot-clients.json`, then restart the service: credentials
  are read at process start. Deliver the new token privately and confirm the old one gets
  `401`.
- Revoke with `remove-client`, then restart. `remove-client` refuses to revoke the last
  enabled client with `last_client_refused`; stopping the service is
  `systemctl stop manijero-pilot`, not deleting the only credential.
- Rotate tunnel credentials and the Cloudflare account per the provider's own procedure;
  R2 presigned links (artifact delivery only) cannot be revoked individually before expiry,
  so keep them short-lived.
- **Current gap:** the Android and Desktop clients have no field for a bearer token. The
  pilot profile's authentication is implemented and tested, but a client build that can
  present the token does not exist yet, so enabling this gate before that change would
  make `/ask` fail (the app renders the accepted failure notice). Add client credential
  support before routing any pilot user to the service.

### Outage response

1. Confirm what is failing, in this order: a pilot report; `GET /health` on the host
   loopback; `GET /ready`; `systemctl status manijero-pilot`; the connector
   (`systemctl status cloudflared`, tunnel metrics); the provider status page.
2. Distinguish the cases: process down (restart and read the journal), not-ready
   configuration/corpus (preflight, campaign validity, restore), tunnel/DNS/TLS failure
   (provider side; the application may still be healthy on loopback), request rejected
   (`401`/`429`/`413`: credentials, per-client limit, or body bound).
3. If a recent deploy caused it, roll back code and/or corpus as above before debugging
   forward.
4. Tell pilot users through the agreed channel. This operator message is a template, not
   shipped app copy: «El asistente no está disponible en este momento. Puedes volver a
   intentarlo más tarde. Tus terrenos siguen guardados en tu dispositivo.» Never describe
   the cause as a legal or answer problem, and never paste a question or land detail.
5. Record the time, symptom, action, and result, and re-check the provider terms if the
   cause is a provider incident.

### Operational limits and honesty rules

- No availability target, SLA, monitoring service, alerting, on-call rotation, or
  measured capacity/headroom exists. The `limit_concurrency` value and per-client limits
  are protective defaults, not measurements.
- Rate limits and token checks are per process. With `N` workers a client's effective
  allowance is `requests_per_minute x N`, and a restart clears the window. Do not describe
  them as edge or cluster-wide limits.
- Authentication failures are not rate-limited. Only a request with a valid token enters a
  client's window, so an unauthenticated caller can make unlimited token guesses; a
  random 48-byte token makes that infeasible, but IP/edge failure limiting is not
  implemented and remains a pre-pilot hardening item.
- The application writes one request-metadata line; that is not an audit trail. Provider
  (Cloudflare) log retention and access are governed by the provider, and the decision
  record does not assume a request-log archive.
- Readiness depends on the canonical artifacts and today's date: an expired corpus is a
  `503`, not a degraded answer.
- The service has no shared store, no multi-region failover, and no second host. Losing
  the host is an outage.
- Everything in this section is a prepared procedure. The only executed parts are the
  local rehearsal items in the feature appendix.

## Product-improvement retention and the privacy gate

The data-flow inventory, the exact retention rules, the redaction limits, and the review
procedure are in [`docs/pilot-privacy.md`](../docs/pilot-privacy.md). **No qualified
privacy/legal review has been recorded**: `config/pilot_privacy_review.json` is `pending`,
so the pilot preflight fails with `privacy_review_*` blockers and `serve_pilot.py` refuses
to start in the pilot profile. Do not edit that record without a real, dated review.

```sh
backend/.venv/bin/python backend/scripts/pilot_ops.py privacy-gate   # exit 1 while blocked
```

Retention is off unless `MANIJERO_RETENTION_DB` is set; then a question is retained only
when its request carries `retain_for_improvement: true`. Prepare the store (example path):

```sh
sudo install -d -o manijero -g manijero -m 0700 /var/lib/manijero/retention
# pilot.env: MANIJERO_RETENTION_DB=/var/lib/manijero/retention/qa-retention.sqlite3
# manijero-pilot.service: uncomment ReadWritePaths=/var/lib/manijero/retention
```

The directory must have no group/other permissions and must be outside the repository;
the file is created `0600`. A configured but unsafe location leaves retention off at run
time and is a preflight problem (`retention_store_permissions`,
`retention_store_inside_repository`, `retention_store_directory_missing`, …).

Owner commands (run as the service user; output is counts and fixed codes only):

| Command | Purpose | Exit |
|---|---|---|
| `retention-status [--as-of D]` | Record count, overdue count, oldest creation date | `1` and `alert: retention_overdue` when any record is past its expiry |
| `retention-purge [--as-of D]` | Delete records whose expiry date is today or earlier | `1` with `error: retention_*` on failure |
| `retention-export --destination F` | Write unexpired redacted records to a new `0600` file outside the repository | `1` on failure |
| `retention-delete-all --confirm` | Delete every retained record | `2` without `--confirm` |

Schedule the purge daily with the `manijero-retention-purge` timer template in
`deploy/systemd/`; a record is due on its creation date plus 29 days, so a daily purge keeps
every record under 30 days. The purge also runs before each write. An export is outside the
automatic purge: delete it within the same window. Treat a non-zero `retention-status` or
purge exit as an incident: fix the store, purge, and record what happened without copying
any retained text.

Limits: redaction is pattern-based and can miss personal details (see the doc); records
have no identifier of a person, so one person's record cannot be deleted early; the
retention store is not backed up by `pilot_ops.py backup` and must not be. Nothing here is a
compliance claim.

## Offline retrieval baseline

`app/retrieval.py` is the offline retrieval boundary over reviewed passages of
approved catalog sources. It is standard-library only, never performs network
access, re-validates the catalog with `app/source_catalog.py`, and refuses to
index when that catalog is invalid. The `/ask` route composes it with the
accepted grounded-answer pipeline; no LLM call is configured.

Run the report-only baseline against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints per-question expected-passage ranks plus `hit@k`, `recall@k`, and MRR
(`--json` for machine-readable output). Thresholds are **not** enforced: the
numbers come from a small synthetic fixture corpus, not from real user questions
or legal documents. See `knowledge/README.md` for the passage-set contract and
the eligibility rules.

## Local multilingual embeddings (optional, pinned, off the default answer path)

`app/embeddings.py` owns one pinned local model behind the narrow
`EmbeddingModel` protocol, and `app/embedding_index.py` owns its derived,
rebuildable passage index. `backend/scripts/manage_embeddings.py` is the operator
entry point. **By default `/ask` imports and reads neither**: the default answer
retrieval remains the reviewed BM25 path, so a missing model, a missing optional
runtime, or an invalid artifact cannot change an answer, citation, abstention, or
land clarification. The only composition onto `/ask` is the explicit opt-in
hybrid mode described in "Hybrid retrieval with a Chroma vector store" below.
Nothing in this path downloads a file, opens a network
socket, or reads a mutable model name.

`torch` and `transformers` are not part of `requirements.txt`. Install the
pinned optional runtime in a separate environment when you need to embed text or
measure the model:

```sh
python3 -m venv backend/.venv-embeddings
backend/.venv-embeddings/bin/python -m pip install -r backend/requirements-embeddings.txt
```

### Pin

`backend/config/bge_m3_embedding.json` is the reviewed expectation, not a
preference file. It records the upstream model and immutable revision, license,
dense dimension, pooling, normalization, dtype, token bound, batch size, and one
SHA-256 plus byte size for every required artifact file:

| Field | Pinned value |
|---|---|
| Model | `BAAI/bge-m3` (`https://huggingface.co/BAAI/bge-m3`) |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` (3 July 2024) |
| License | `MIT` (from the repository at that revision) |
| Dense embedding | 1024 dimensions, CLS pooling, L2-normalized |
| Runtime arithmetic | CPU, `float32`, 8192-token bound, batch 8 |
| Artifact | 9 files, 2,293,315,747 bytes total |

A branch or tag name is rejected: only a 40-character commit id can pin the
artifact. A changed file, a different revision, or an extra declared field fails
closed. The license and revision are recorded provenance, not a legal review.

### Download and verify

Download the exact revision into an operator-owned directory outside this
repository (the artifact is about 2.1 GiB and must not be committed):

```sh
MODEL_DIR="$HOME/models/bge-m3"
mkdir -p "$MODEL_DIR/1_Pooling"
for file in config.json tokenizer.json tokenizer_config.json \
  special_tokens_map.json sentencepiece.bpe.model 1_Pooling/config.json \
  modules.json config_sentence_transformers.json pytorch_model.bin; do
  curl -fL --retry 3 -o "$MODEL_DIR/$file" \
    "https://huggingface.co/BAAI/bge-m3/resolve/5617a9f61b028005a4858fdac845db406aefb181/$file"
done
```

Verification needs only the standard library plus the backend runtime:

```sh
backend/.venv/bin/python backend/scripts/manage_embeddings.py verify \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$MODEL_DIR"
```

It prints the model id, revision, license, configuration digest, verified file
count/bytes, ignored extra files, and any mismatch. Exit `0` means every pinned
file matched; `1` means the artifact differs from the pin; `2` means the
configuration was unreadable or refused. To observe this host:

```sh
backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py verify \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$MODEL_DIR" --measure --json
```

`--measure` loads the model once and reports load time, dimension, thread count,
three repeated embedding runs over two fixed short Spanish sentences (median,
p95, min, max), peak process RSS, and the maximum absolute difference between
repeated runs. It prints no question, passage, or personal value. These are host
observations, not retrieval-quality evidence.

Measured on 2026-10-27 with the pin above on an Apple M1 Max (32 GiB,
CPU, 8 torch threads, Python 3.14.5):

| Observation | Result |
|---|---|
| Verified artifact | 9 files, 2,293,315,747 bytes (`du` 2.1 GiB) |
| Optional runtime environment | 928 MB (separate `.venv-embeddings`) |
| Peak process RSS while embedding | 1,943 MB (process max 2,037,841,920 bytes) |
| Model load | 4.91 s warm page cache / 9.51 s cold |
| Embedding 2 short texts | 76.74 ms median, 77.00 ms p95 over 3 runs |
| Repeated-run determinism | maximum absolute difference `0.0` |
| Index rebuild over the 4 approved passages | 0.621 s, index file 124,691 bytes |

These numbers are **not** an owned-server capacity measurement, not a
per-passage or per-answer latency budget, and not a comparison against BM25.
Long passages cost many more tokens than the two sentence probe.

### Build and check the derived index

```sh
backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py build \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$MODEL_DIR" \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --as-of 2026-10-27 --active-campaign 2026 \
  --index "$HOME/manijero/embedding-index.json"

backend/.venv/bin/python backend/scripts/manage_embeddings.py check \
  --config backend/config/bge_m3_embedding.json \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --as-of 2026-10-27 --active-campaign 2026 \
  --index "$HOME/manijero/embedding-index.json"
```

`build` embeds only the passages a validated `Retriever` already found eligible
(approved, current, unexpired, campaign-matching). It does not re-implement
eligibility, does not write `knowledge/`, and replaces the target atomically. The
`passage-embedding-index-v1` file records the model pin, the catalog/passages
SHA-256, `as_of`, the active campaign, passage count, and one 1024-float vector
per opaque passage id — **no passage text, question, or score**. `check` needs no
model runtime and exits `0` only for `up_to_date`; `1` for a missing, stale, or
invalid index; `2` for an unreadable/invalid configuration or corpus. Staleness
reasons name what changed (`catalog_changed`, `passages_changed`,
`as_of_changed`, `active_campaign_changed`, `model_revision_changed`,
`model_config_changed`, `dimension_changed`, `pooling_changed`,
`normalization_changed`, `model_id_changed`).

### Rebuild and failure recovery

- **Rebuild** = re-run `build` with the same pin; vectors are derived, so the
  index can be deleted and regenerated at any time. Rerun it after any approved
  catalog/passage change or a new model pin, then `check` before using it.
- **Artifact mismatch** (`checksum_mismatch`, `size_mismatch`, `file_missing`,
  `dimension_mismatch`, `pooling_mismatch`, `context_too_small`,
  `directory_missing`, `path_escape`, `not_a_regular_file`): re-download the
  pinned revision and verify again. Do not edit a checksum to make a mismatch
  pass; a new artifact is a new reviewed pin.
- **`runtime_unavailable`**: install `backend/requirements-embeddings.txt` in the
  optional environment; the default backend and tests keep working without it.
- **`model_load_failed` / `encode_failed`**: the artifact verified but the pinned
  runtime could not load or run it. Check the runtime pins and platform, then
  rebuild the artifact from the pinned revision. Messages contain a fixed code,
  never the text being embedded.
- **`unsafe_index_path`**: choose a derived-artifact path outside `knowledge/`.
- **`index_write_failed`**: the parent directory is not writable; nothing is
  replaced atomically, so the previous index (if any) is unchanged.

### Limits

- Supported and measured configuration is CPU `float32` only. `dtype` is closed
  to `float32`; a GPU or half-precision path is a separate, measured change.
- Latency, RAM, and index size scale with hardware, thread count, and token
  count. Only this local Mac host and four approved passages were observed; the
  owned server and long documents are unmeasured; the Chroma/hybrid measurement
  is in the hybrid section below.
- Reproducibility means the same pinned code, runtime, artifact, input digests,
  and host produce the same vectors (`0.0` difference measured). Float arithmetic
  can differ across BLAS libraries and hardware; no cross-platform bit-identity
  is claimed.
- No retrieval-quality, Spanish legal-coverage, or answer-quality claim follows
  from successful verification or from a `0.0` determinism result. The measured
  BM25 vs Chroma/RRF comparison is in the hybrid section below.
- Embeddings stay off the default answer path; `chroma_hybrid_retrieval` composes
  them only behind the explicit `MANIJERO_RETRIEVAL_MODE=hybrid` opt-in (see
  below), with the code-owned answer properties unchanged. The derived
  index is not canonical knowledge, is not encrypted, and is owned/backed up by
  the operator.
- `1_Pooling/config.json`, `modules.json`, and `config_sentence_transformers.json`
  are pinned so a silent pooling or pipeline change is visible, even though the
  loader composes pooling and normalization itself.
- Verification counts but does not delete extra files in the artifact directory.
  Because the loader points `transformers` at that directory, keep it to the
  pinned files: an unpinned file whose name the library recognizes would be
  outside this pin.

## Hybrid retrieval with a Chroma vector store (optional, off by default)

`app/vector_store.py` owns a persistent, rebuildable Chroma collection of the
pinned model's passage vectors; `app/hybrid_retrieval.py` owns the fusion,
ranker, and lazily loaded runtime; `app/retrieval_backend.py` selects the mode
from the environment. `backend/scripts/manage_vector_store.py` is the operator
entry point (`build`, `check`, `compare`).

**BM25 stays the default.** `/ask` uses hybrid ranking only when
`MANIJERO_RETRIEVAL_MODE=hybrid` is set **and** the store is fresh for the
current model pin, active campaign, and admitted passages. In every other case
— unset or unknown mode, missing paths, no `chromadb`/`torch`, an artifact that
fails verification, a missing/invalid/stale store, or a query failure — the
request uses the accepted BM25 ranking unchanged. The `/ask` wire contract,
citations, verification, abstention, and land clarification are unchanged; the
service import loads no vector module, runtime, or model.

### Fusion method

Reciprocal Rank Fusion (Cormack, Clarke and Büttcher, 2009), configured in the
closed `backend/config/hybrid_retrieval.json` (`hybrid-retrieval-v1`):

```text
rrf(d) = Σ over lists L containing d of 1 / (rrf_k + rank_L(d))
```

- Two lists with equal weight: the BM25 ranking (positive scores only) and the
  Chroma cosine ranking (similarity strictly above `vector_min_similarity`).
- Each list is truncated to `candidate_depth`; ranks are 1-based; ties break by
  ascending passage id, so results are deterministic for the same inputs.
- Pinned values: `rrf_k: 60` (the published default), `candidate_depth: 20`,
  `vector_min_similarity: 0.0`. They were **not** tuned on the evaluation cases.
- **Lexical gate**: a question with no BM25 match returns no candidate and the
  vector side never runs, so vector similarity cannot turn a zero-evidence
  question into an answer.
- **Provenance**: the ranker can only reorder or add passages the `Retriever`
  already admitted (approved, current, unexpired, active campaign); any other id,
  duplicate, or non-finite score is dropped by `Retriever.search`.

### Install the optional runtime

```sh
python3 -m venv backend/.venv-hybrid
backend/.venv-hybrid/bin/python -m pip install -r backend/requirements-hybrid.txt
```

`requirements-hybrid.txt` adds `chromadb==1.5.9` (exact pin) on top of the
service and embedding pins. Measured here, the environment is 1.2 GB. Chroma
anonymized telemetry is always disabled in code, and no Chroma embedding
function is configured, so Chroma never downloads its own model.

### Lifecycle

```sh
STORE="$HOME/manijero/vector-store"
# 1. Embed the eligible passages (see "Build and check the derived index" above).
backend/.venv-hybrid/bin/python backend/scripts/manage_embeddings.py build \
  --config backend/config/bge_m3_embedding.json --artifact "$MODEL_DIR" \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --as-of "$(date -u +%F)" --active-campaign 2026 \
  --index "$HOME/manijero/embedding-index.json"

# 2. Load that index into Chroma (needs chromadb, not torch).
backend/.venv-hybrid/bin/python backend/scripts/manage_vector_store.py build \
  --config backend/config/bge_m3_embedding.json \
  --embedding-index "$HOME/manijero/embedding-index.json" \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --as-of "$(date -u +%F)" --active-campaign 2026 --store "$STORE"

# 3. Check freshness (manifest only; --deep also opens and verifies the collection).
backend/.venv/bin/python backend/scripts/manage_vector_store.py check \
  --config backend/config/bge_m3_embedding.json \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --as-of "$(date -u +%F)" --active-campaign 2026 --store "$STORE"

# 4. Compare BM25 and hybrid on the reviewed cases before enabling (report only).
backend/.venv-hybrid/bin/python backend/scripts/manage_vector_store.py compare \
  --config backend/config/bge_m3_embedding.json \
  --hybrid-config backend/config/hybrid_retrieval.json \
  --artifact "$MODEL_DIR" --store "$STORE" \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --as-of "$(date -u +%F)" --active-campaign 2026 --json

# 5. Opt in (run the service from the hybrid environment).
MANIJERO_RETRIEVAL_MODE=hybrid MANIJERO_VECTOR_STORE="$STORE" \
MANIJERO_EMBEDDING_ARTIFACT="$MODEL_DIR" MANIJERO_ACTIVE_CAMPAIGN=2026 \
  backend/.venv-hybrid/bin/python -m uvicorn app.main:app --app-dir backend
```

`MANIJERO_EMBEDDING_CONFIG` and `MANIJERO_HYBRID_CONFIG` override the two
repository configuration files. The store's `build` refuses an embedding index
that is not `up_to_date` for the given inputs.

**Store layout.** `<store>/manijero-vector-store.json` (`chroma-passage-store-v1`
manifest, written last) plus Chroma's own files. The manifest records the model
pin, the corpus inputs, a SHA-256 of the exact admitted `(passage_id, text)`
documents, the sorted passage ids, the source index SHA-256, and a SHA-256 of the
`float32` vectors read back from Chroma. Neither the manifest nor the collection
holds passage text, a question, or a score. Opening a store re-checks the
collection's ids and vector digest against the manifest.

**Freshness at answer time** depends on the model pin, the active campaign, and
the admitted-documents digest, **not** on `as_of` or file digests. A source
that expires, a passage edit, or a campaign change makes the store `stale`
(`documents_changed`, `active_campaign_changed`, `model_*_changed`, …) and
requests use BM25 until the store is rebuilt. If only `as_of` advances and the
admitted passages stay the same, the store remains current.

**Observability.** The service writes a `retrieval_mode` operational record
whenever the outcome changes (`configured`, `active`, `store_state`, `reasons`),
and `hybrid_retrieval_fallback` with a fixed reason code or exception type name
if a query falls back. It never writes the question, passage text, or a land
value. `/ready` is unchanged: a hybrid problem never makes the service unready,
because answers continue on BM25.

### Rebuild and failure recovery

- **Rebuild** = rerun steps 1–3 after any approved catalog/passage change, a new
  model pin, or a campaign change. `build` writes into a sibling staging
  directory, verifies it, then swaps it into place. A failed build leaves the
  previous store untouched. An existing target is replaced only if it is itself
  a store (it has a manifest); any other directory is refused
  (`store_path_not_a_store`) and left alone.
- **`unsafe_store_path`**: choose a path outside `knowledge/`.
- **`vector_runtime_unavailable`**: install `requirements-hybrid.txt` in the
  environment that runs the service or command.
- **`store_missing` / `manifest_*` / `store_ids_mismatch` /
  `store_vectors_mismatch` / `store_open_failed` / `store_model_mismatch`**: the
  store is absent, damaged, or built under another pin. Delete it and rebuild.
  Answers continue on BM25 meanwhile.
- **`store_query_failed` / `encode_failed`** at answer time: that request fell
  back to BM25. Check the log reason, then the runtime and artifact.
- A load failure is remembered until the service restarts, so restart after
  fixing the artifact, runtime, or store. The first hybrid request after start
  pays the model load and artifact verification (2.7–2.8 s measured here).

### Measured comparison (2026-10-31, this development Mac only)

Apple M1 Max, CPU `float32`, Python 3.12.16, `torch==2.14.1`,
`chromadb==1.5.9`, pinned bge-m3 `5617a9f…`, the four approved passages, and the
14 reviewed author-only cases in `knowledge/pac_answer_eval.json` at `k=5`:

| Metric | BM25 | Hybrid (RRF) |
|---|---|---|
| Expected states | 13/14 | 13/14 |
| Expected-answer cases answered | 11/11 | 11/11 |
| Expected source cited | 8/11 | 8/11 |
| Expected passage cited | 8/11 | 8/11 |
| Expected critical literal | 9/11 | 9/11 |
| Expected abstentions | 2/3 | 2/3 |
| Retrieval: expected passage at rank 1 | 8/11 | 8/11 |
| Retrieval: expected passage in top 5 | 10/11 | 11/11 |
| Retrieval: mean reciprocal rank | 0.818 | 0.841 |
| Search latency per question (median / p95) | 0.02 / 0.03 ms | 33.9 / 52.9 ms |

**No answer-level improvement was measured.** Two answers changed:
`canal-sga-2026` now cites a different passage that is still not the expected
one, and `canal-sga-entidades-2026` now cites one extra passage. The single
top-5 recall gain is `canal-sga-2026` (expected passage now at rank 4, absent
before). With four passages, almost any question gives every passage a positive
cosine, so hybrid candidate lists contain all four. The process peaked at
1,967.5 MB RSS. The store is 630,124 bytes; writing it took 0.2–1.3 s. This is a
14-case author-reviewed sample on one host, not legal review and not evidence of
general accuracy; keep BM25 as the default unless a larger reviewed comparison
supports a change.

## Offline grounded answer generation

`app/generation.py` turns retrieval candidates into a plain-Spanish answer whose
material claims are each traceable to a reviewed passage. It imports `Retriever`
and `RetrievedPassage` from `app/retrieval.py`, which stay the only evidence
source: generation never re-reads the catalog or the passage set and never
re-implements eligibility.

It is standard-library only, offline, and configured with **no model provider**.
The default and only enabled generator is the code-composed extractive one; a
draft is re-checked by `verify_draft` before assembly, so a citation marker that
resolves to nothing, an uncited sentence, a figure or date absent from the cited
passage, a non-literal `critical` claim, or an eligibility assertion
(`tienes derecho a`) rejects the whole draft. The extractive generator writes
each claim on its own line before verification, and a line break is a claim
boundary, so an excerpt without terminal punctuation cannot merge with the next
candidate's claim and inherit its figure or critical-literal rules. The pipeline
then returns a `NotAnswered` reason code and no text; `safe_abstention` owns the
user-facing limitation and next step.

Run the report-only grounded-generation tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the produced answer, every material claim
with its cited candidate numbers, and the per-claim grounding verdict
(`--json` for machine-readable output). Grounding invariants are **enforced**
(exit `1`); answer coverage is not, unless `--fail-on-miss` is passed. `/health`
remains liveness-only, and no model provider is configured.

## Offline abstention decisions

`app/abstention.py` turns every "no safe answer" outcome into one deterministic,
offline, code-owned abstention. It is standard-library only, imports
`app/generation.py` and `app/retrieval.py` unchanged, and never reads a catalog
or a passage file itself, never calls a model or the network, and never emits a
draft sentence, candidate excerpt, source, figure, or date.

The taxonomy is stable and machine-readable. Pre-checks (run before the
generator) and pipeline mappings produce exactly one reason:

| Reason | Trigger |
|---|---|
| `invalid_question` | Blank question, or longer than the accepted 2,000-character bound. |
| `no_evidence` | Retrieval returned no candidate (generation `no_candidates`). |
| `insufficient_evidence` | Candidates existed but no verifiable claim could be assembled (generation `grounding_failed`). |
| `stale_evidence` | The corpus declares sources but none is eligible as of `--as-of` (expired, non-`approved`, or non-`current`). |
| `conflicting_evidence` | Two `critical` candidates in the citation window state different values for the same documented unit. |
| `false_premise` | The question presupposes an instrument/article reference that no retrieved candidate contains. |
| `unsafe_request` | A generated claim asserts the person's legal status (generation `policy_failed`). |
| `generator_abstained` | The generator explicitly declined; its copy is discarded. |
| `generation_error` | The generator raised or returned an unusable object. |

Server-side copy is **code-owned**: `ABSTENTION_MESSAGES` maps every reason to one
pinned plain-Spanish message, an `Abstention` has no text field, and no message
contains a digit or a date, so an abstention can never invent a deadline or an
amount. `to_abstention_response` emits exactly the accepted `AskResponse` keys
with `status: "abstained"`, `sources: []`, and `land_ids_to_choose: []`. Because
`AskResponse` rejects extra properties, the sub-reason stays a Python-level value
and `contracts/` is untouched. Detection is lexical and conservative (a retrieval
miss or two unrelated critical passages sharing a unit can abstain); that is the
safe direction, and the measured trap set and any score threshold belong to
`land_safety_evaluation`.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_abstention.py \
  --catalog backend/tests/fixtures/abstention/catalog.json \
  --passages backend/tests/fixtures/abstention/passages.json \
  --eval backend/tests/fixtures/abstention/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, reason, generation reason, issue codes, and
emitted message (`--json` for machine-readable output), and reports whether the
corpus is `current` or `not_current`. Abstention invariants (no sources, no land
choices, a non-blank message at most 1,200 characters with no digit or date, and
a reason inside the taxonomy) are **enforced** (exit `1`); outcome coverage is not
unless `--fail-on-miss` is passed. A catalog whose sources are all ineligible as
of `--as-of` abstains as `stale_evidence` for every question; a malformed passage
set, an unknown `source_id`, or an unreadable file stays a hard error (exit `2`).
`/health` remains liveness-only, and no model provider is configured.

## Offline land clarification decisions

`app/clarification.py` makes the accepted `needs_land_clarification` response actually happen. It
composes the accepted modules unchanged (`app/retrieval.py`, `app/abstention.py`,
`app/generation.py`): it never reads a catalog or a passage file itself, never calls a model or the
network, and never filters by applicability anywhere else.

When the question depends on a detail the supplied lands differ on, the person is asked which land
(or lands) the question is about instead of the service guessing one arbitrarily. Only the opaque
local ids are returned on the wire; the client owns the names and collects the selection, so no
name, note, area, or timestamp leaves the device.

- A clarification is offered **only** for `mode: all_active` with **two or more** lands. `general`,
  a single land, and a `selected` request (the person has already chosen) delegate to the accepted
  `answer_or_abstain`, so a `selected` request is never asked to clarify again.
- The only discriminating dimensions are `water_regime` and `production_method` (the two a request
  can carry); `crop` is not a request field, so a `crop` restriction applies to every land and never
  discriminates. Detection is conservative and lexical, in the citation window (the first `max_claims`
  candidates, matching `abstention`).
- An omitted, blank, or `unknown` land attribute is compatible with every candidate and never
  excludes one; only a known value that disagrees with a candidate's declared applicability excludes
  that candidate, and no value is ever inferred.
- A clarification payload is exactly the accepted `AskResponse` keys with
  `status: "needs_land_clarification"`, `answer: ""`, `sources: []`, `land_scope: "selected"`, and a
  non-empty, unique list of the request's own land ids. `contracts/` is untouched.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_clarification.py \
  --catalog backend/tests/fixtures/clarification/catalog.json \
  --passages backend/tests/fixtures/clarification/passages.json \
  --eval backend/tests/fixtures/clarification/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the chosen land ids for a clarification, and the per-outcome
counts (`--json` for machine-readable output). Clarification invariants (empty answer, no sources, a
non-empty list drawn from the request's own land ids) are **enforced** (exit `1`); outcome coverage is
not unless `--fail-on-miss` is passed. A malformed passage set, an unknown `source_id`, or an
unreadable file stays a hard error (exit `2`). `/health` remains liveness-only, and no model
provider is configured.

## Offline land-safety evaluation

`app/land_safety_eval.py` is the offline, report-only safety harness. It runs the
accepted end-to-end decision (`app/clarification.py::answer_with_clarification`,
which already composes retrieval, grounding, abstention, and land clarification)
over a reviewed, source-anchored case set and reports, per category, whether the
service returned the correct sources, abstained safely, or clarified the correct
land. It imports the accepted modules unchanged: it never re-implements
eligibility, grounding, or clarification, never reads a catalog or a passage file
itself, never configures a model provider, and never touches the network. Grading
is deterministic rule checking, not a semantic judge.

A case is a Git-tracked, human-reviewed artifact. A case whose expectation turns
on a critical fact must carry a completed `review` block; without it the set fails
closed at load time (exit `2`). The harness records that provenance but a human
must verify the fact itself. The case-set contract is `knowledge/land_safety_eval.schema.json`
(`land-safety-eval-v1`); see `knowledge/README.md` for the fields and the review
procedure.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_land_safety.py \
  --catalog backend/tests/fixtures/land_safety/catalog.json \
  --passages backend/tests/fixtures/land_safety/passages.json \
  --cases backend/tests/fixtures/land_safety/cases.json \
  --as-of 2026-10-13 --k 5
```

It prints each case's outcome and per-check verdicts, the per-category table, the
metric block, and the critical-review section (`--json` for machine-readable
output). The enforced **safety invariants** (a payload that leaks or invents:
an abstention carrying a source, a figure, or a date; a clarification carrying an
answer or a foreign land id; an answered payload with no source or an
out-of-range marker) make it exit `1`. Coverage metrics are **report-only**: an
expected-source/clarification mismatch only exits `1` with `--fail-on-miss`, and
`--passages`/`--cases` may be omitted for a corpus summary that invents nothing.
`/health` remains liveness-only, and no model provider is configured.

The measured fixture baseline is: `covered_source_hit_rate` `1.000 (2/2)`,
`correct_abstention_rate` `1.000 (2/2)`, `correct_clarification_rate`
`1.000 (1/1)`, `no_over_clarification_rate` `1.000 (3/3)`, and
`expected_outcome_match_rate` `1.000 (6/6)`. It is **synthetic and
implementer-authored**: it exercises the mechanism and the trap taxonomy, not
legal coverage or real user questions, and it is not legal-coverage evidence.
The `MasterPlanV3` §9.2 numbers (`hit@5 85%`, correct abstention `100%`, invented
numbers/dates `0`) are **inherited proposals, not enforced release gates**;
enforcement is a later, separately agreed change.

## Offline PAC answer evaluation

`app/answer_eval.py` validates the `pac-answer-eval-v2`
`knowledge/pac_answer_eval.json` artifact and calculates a deterministic,
report-only evaluation of its cases through the local `/ask` route. The artifact
declares its reviewed coverage areas (3 topics and 5 boundaries), the out-of-scope
omissions, and an `author_only` review role on every case. The report includes
assertion denominators (`answered_cases`, `abstention_cases`,
`clarification_cases`), per-area counts, author-review metadata, the omissions,
and per-case missing expected source/passage IDs or critical facts. Run it with
the pinned inputs:

```sh
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --active-campaign 2026 --as-of 2026-10-26 --k 5
```

All 14 cases are synthetic, source-anchored, and reviewed only by the project
author (recorded as `author_only`); this is **not** independent legal review and
does not establish answer quality or coverage beyond the listed cases. The
current result is 13/14 expected states, 11/11 expected-answer cases answered,
8/11 answering cases with the expected source and passage, 9/11 with the expected
critical literal, and 2/3 expected abstentions. The report keeps known gaps
visible: `canal-sga-2026`, `fecha-modificacion-2026`, and
`distingue-fechas-2026` cite a different reviewed passage, and
`reclamacion-fuera-de-alcance` answers an out-of-scope reclamación with the
modification deadline. The exact matrix and case-level limits are in
`knowledge/pac_coverage.md`.

Citation matching uses exactly the catalog and passages supplied to the command.
Repeat identical inputs for byte-identical output. Integrity/input/runtime errors
exit nonzero; outcome mismatches and coverage metrics do not. There is no numeric
quality threshold.

Tests:

```sh
cd backend && python -m pytest
```

## Manual official-source monitoring

`app/source_monitor.py` polls only explicitly configured HTTPS endpoints on the
exact approved official-host allowlist. It supports RSS/Atom XML and JSON
responses, including the BOJA RSS and BOE Open Data API endpoints; it does not
interpret response contents or fetch linked documents. A successful snapshot
stores retrieval time, URL, HTTP status, ETag/Last-Modified when supplied, and
SHA-256 of the exact response bytes. A changed feed is a review candidate only;
the scanner never writes `knowledge/source_catalog.json` or `knowledge/passages.json`.

Create an owner-reviewed configuration file, for example:

```json
{"sources":[
  {"id":"boe-api","url":"https://www.boe.es/datosabiertos/api/api.php","format":"json"},
  {"id":"boja-rss","url":"https://www.juntadeandalucia.es/boja/distribucion/s51.xml","format":"rss"}
]}
```

Dispatch manually (or call this command from an owner-managed scheduler):

```sh
cd backend
python scripts/scan_official_sources.py --config source-monitor.json --state var/source-monitor-state.json
```

Exit `0` means each configured endpoint succeeded; `1` means at least one
endpoint failed (the JSON report includes actionable failure categories and
retains its last good hash/time); `2` means config/state could not be read or
validated. Use a durable, access-controlled local state path and back it up if
operational history matters. Conditional requests are sent when validators are
available. Requests have a 15-second timeout and 5 MiB response cap; redirects
are allowed only to the same HTTPS host. The command itself has no retry loop;
scheduled dispatch with retries and a run ledger is described in "Scheduled
source updates (owned host, best-effort)" below. There is no document
ingestion, legal-change interpretation, or automatic canonical update here. Successful polling is not evidence of legal
coverage or corpus currency.

## Manual official-publication discovery

`app/source_discovery.py` scans configured registries into a separate pending
queue; it does not fetch publication bodies or modify the canonical catalog or
passages. BOE uses the documented daily sumario XML API; BOJA uses its
officially documented calendar endpoint to enumerate bulletin numbers, then
fetches each issue through the bulletin endpoint. The scan is bounded to 400
issues and 160 MiB aggregate BOJA response bytes (5 MiB per request); exceeding
a bound fails the registry scan without committing partial candidates.
FEGA/MAPA first-party registries are not
verified and are reported unchecked, not treated as empty. The registry host
`datos.juntadeandalucia.es` is exact-configured for the API only; candidate
publication URLs still require exact issuer-host approval.

Copy `knowledge/official-discovery-config.example.json`, adjust BOE date and
BOJA year, then run:

```sh
python3 backend/scripts/discover_official_sources.py \
  --config /path/to/discovery-config.json \
  --state /path/to/official-discovery-state.json
```

Exit `0` means every attempted supported registry succeeded, `1` means an
attempt failed, and `2` means invalid config/state. The report still lists
unconfigured registries and FEGA/MAPA as unchecked; exit `0` is not full
coverage. Each request has a 15-second
timeout and 5 MiB response cap; HTTPS redirects remain on the exact same host.
Only candidate metadata and observation hashes/times are retained, not response
content. Repeated records add no duplicate observation; changed title/URL
versions retain prior observations. Failures preserve candidates and
last-success timestamps. Candidates remain `pending`; a human must verify
provenance and approve any canonical change. See
`knowledge/official-discovery-state.schema.json`.

## Scheduled source updates (owned host, best-effort)

`app/source_update_scheduler.py` (CLI `scripts/run_source_updates.py`) runs the
two commands above unchanged on the owned pilot host. It adds due rules,
catch-up, retries, a lock, a run ledger, and a status check. Every result stays
a quarantined, `pending` review signal: a successful run means only that the
listed targets responded. It is **not** evidence of legal coverage, corpus
currency, or freshness (`freshness_claim: "none"`), and FEGA/MAPA stay
unchecked. GitHub Actions `schedule:` was rejected (best-effort, auto-disabled
when idle, runs from a merge, and would need committed state or a secret); no
repository workflow schedules or invokes this command.

**Cadence.** One timer, `OnCalendar=*-*-* 10:20:00 Europe/Madrid`,
`RandomizedDelaySec=30m`, `Persistent=true` (one catch-up run after downtime).
Inside a run each job has its own due rule:

| Job | Due when | Targets | Attempts |
|---|---|---|---|
| `monitor` | no successful monitor job in 12 h, or `--force` | every configured source; a retry re-scans only failed ids | 3 |
| `boe` | any pending date | non-Sunday dates from the day after the last successful date (but at most 14 days back) to today; today only after 09:00 Madrid; first run = today only; earlier failed dates still inside the window; `--boe-date` values; `--force` re-adds today when due | 3 |
| `boja` | no successful BOJA job in 156 h, or `--force` | the current Madrid year, plus the previous year when the last success was in an earlier year | 2 |

Backoff is 60 s before attempt 2 and 300 s before attempt 3; only failed
targets are retried. Configuration/state errors are never retried. These
publication-calendar assumptions (BOE daily except Sunday; BOJA working days)
are planning assumptions, not live-verified.

**Install (procedure, not rehearsed).** As root on the host:

```sh
install -d -o manijero -g manijero -m 0700 /var/lib/manijero/source-updates
install -o root -g manijero -m 0640 backend/deploy/source-monitor.json.example /etc/manijero/source-monitor.json
install -m 0644 backend/deploy/systemd/manijero-source-updates.service backend/deploy/systemd/manijero-source-updates.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now manijero-source-updates.timer   # disable: systemctl disable --now manijero-source-updates.timer
systemctl list-timers manijero-source-updates.timer
```

Review the copied monitor configuration first. The unit reads no environment
file and needs no secret. Notification is the failed unit (`systemctl --failed`)
plus the JSON report in `journalctl -t manijero-source-updates`; an operator may
add their own `OnFailure=` unit (a commented placeholder is in the template).
No webhook, email, or token is shipped.

**Manual dispatch and status.** From the repository root (the state directory
must be outside the repository):

```sh
backend/.venv/bin/python backend/scripts/run_source_updates.py run \
  --state-dir /var/lib/manijero/source-updates --monitor-config /etc/manijero/source-monitor.json \
  [--job monitor|boe|boja ...] [--force] [--boe-date YYYYMMDD ...]
backend/.venv/bin/python backend/scripts/run_source_updates.py status --state-dir /var/lib/manijero/source-updates
# on the host: systemctl start manijero-source-updates.service
```

`run` prints the `run_finished` record plus the post-run `status` block.
Exit codes: `0` success or nothing due and healthy; `1` a job failed or status
has an alert; `2` configuration/state error (invalid monitor config, invalid or
unreadable state, corrupt or oversized ledger, state directory inside the
repository, invalid `--boe-date`); `3` another run holds the lock (nothing is
fetched or written). A run limited with `--job` still reports alerts for the
other jobs (for example `stale:monitor`), so it can exit `1`.

**State and ledger.** The state directory holds `source-monitor-state.json`,
`official-discovery-state.json` (the accepted formats), `source-update.lock`,
and the append-only `source-update-ledger.jsonl` (`source-update-ledger-v1`,
files `0600`). Each run writes one `run_started` and one `run_finished` line
with ids, dates, counts, and fixed failure codes only — no URL, response
content, path, or exception text. The reader refuses a malformed line or a
ledger over 10 MiB: archive the file (`mv` it aside) and start a new one; the
first run afterwards scans BOE for today only.

**Alerts.** `status` (also evaluated at the end of every run) reports
`never_run`, `missed_run` (no run started in 30 h), `interrupted_run` (latest
run unfinished after 2 h), `last_run_failed:<job>`, and `stale:<job>` (no
success within monitor 36 h, BOE 36 h, BOJA 192 h). Warnings list
`abandoned_boe_dates` (a failed date that left the 14-day window, looked back
60 days; re-scan it with `--boe-date` while it is at most 60 days old) and
FEGA/MAPA as unchecked.

**Recovery.** After `interrupted_run`, check `journalctl -t
manijero-source-updates`, then dispatch `run` manually; monitoring and
discovery state writes are atomic, and a re-run deduplicates candidates. After
a corrupt state file, move it aside (monitoring restarts without validators;
discovery restarts its candidate queue) and record the incident.

**Limits.** Not installed or rehearsed on any host; `systemd-analyze` was not
run. There is no external dead-man's switch: if the timer itself stops firing,
only `status`, `systemctl list-timers`, or the next run reveals it. No SLA,
alert delivery, coverage, or freshness claim. Scheduled runs do not ingest
documents, analyze change impact, prepare review packages, reindex, or deploy.

## Manual official-document candidate ingestion

`app/document_ingestion.py` fetches the pending publication candidates produced
by discovery into a local **quarantine**. It is the only command in this
repository that downloads a publication body, and it is still not an
answerability path: it never reads or writes `knowledge/source_catalog.json`,
`knowledge/passages.json`, or any index, and every ingested record stays
`review_status: pending`. A human must review, extract approved passages, and
merge a canonical change separately.

**Admission rules.** A candidate is fetched only when its declared issuer is one
of the approved catalog issuers and its `publication_url` uses HTTPS on that
issuer's exact approved host, including the approved `www.` alias where listed
(no subdomain or suffix matching), with no credentials, non-443 port, site root,
or fragment. Anything else is rejected before a request is made. Redirects are
followed only when every hop stays on HTTPS and on an exact host approved for
the same issuer, at most three hops; any other redirect, a final URL outside
that host set, or a non-200 response fails the candidate. FEGA and MAPA
publications still need a BOE host unless the URL host is one of their own
approved hosts.

**Inputs.** `--discovery-state` is the `official-discovery-state-v1` file.
`--monitor-state` is optional. Monitoring deliberately retains only feed
response metadata, not linked document URLs, so it contributes **zero**
candidates and each monitored source is reported as
`unchecked / no_document_candidates`; the command does not guess documents from
a feed.

Run it from the repository root with an operator-owned state and quarantine
path outside `knowledge/`:

```sh
backend/.venv/bin/python backend/scripts/ingest_official_documents.py \
  --discovery-state /path/to/official-discovery-state.json \
  --monitor-state /path/to/source-monitor-state.json \
  --state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine
```

Omit `--monitor-state` when no monitoring state exists. The JSON report lists
one outcome per candidate (`extracted`, `unchanged`, `failed`, `rejected`) with
fixed failure categories and the preserved provenance hashes. Exit `0` means no
candidate failed or was rejected, `1` means at least one did (the run still
persists every other outcome), and `2` means the run aborted before producing a
report: an unreadable or invalid config/state file, a discovery state over 1,000
candidates, a state/quarantine path inside the repository `knowledge/`
directory, or an unexpected exception. Those pre-fetch rejections make no
request. Exit `0` is not coverage evidence: the report still shows the
monitoring gap and any rejected candidate.

**Bounds.** One candidate is requested once per run with no retry loop. Each
request has a 15-second timeout, a 10 MiB response cap, and at most three
same-issuer redirects; exceeding any of these fails that candidate. Per-candidate
PDF/text bounds are 20 MiB decompressed, 500 pages, 20,000 objects, 200 fonts per
page, 65,536 CMap entries, and 5,000 blocks / 2,000,000 characters; exceeding one
fails that candidate closed. A discovery state containing more than 1,000
candidates aborts the whole run as exit `2` before any fetch. Only
`application/pdf`, `text/html`, and `application/xhtml+xml` declared types are
accepted, and the body must have the matching PDF/HTML signature.

**What is preserved.** For each accepted candidate the quarantine directory
`<quarantine>/<candidate_id>/` holds the exact original bytes
(`original-<sha256>.<pdf|html>`) and the extracted structure
(`extracted-<sha256>.json`), named by content hash so a changed version does
not overwrite the prior copy. The state records the discovery provenance
(issuer, registry URL, publication URL, stable identity, observation version
hash), retrieval time, declared/content type, byte size, original SHA-256,
extractor version, extracted-text SHA-256, page/block counts, previous original
hash, and a bounded attempt history. HTML blocks carry a heading path as their
`section`; PDF blocks carry `Página N`. The readable contracts are
`knowledge/official-ingestion-state.schema.json` and
`knowledge/official-ingestion-document.schema.json`.

**Failure and recovery.** A failed or rejected attempt leaves any previous good
extraction and its files untouched, records the fixed failure category, and
keeps the last-success time. Re-running the same discovery state retries failed
candidates and skips an unchanged successfully ingested candidate (same version
hash, current extractor version/media type, and files present). A changed
discovery version hash re-fetches
and re-extracts, preserving the old hashed files and recording
`previous_original_sha256`. Duplicate candidate URLs and duplicate document
bytes inside one run are rejected (`duplicate_candidate`, `duplicate_content`)
rather than ingested twice. If the ingestion state file is invalid, the command
exits `2` and overwrites nothing. To start over, stop the command, move the
state file and quarantine directory aside, and run again; the deleted quarantine
is not recoverable from the service.

**Refreshing extraction.** A stored `extractor` value that differs from the
current `manijero-document-extractor-v1` makes the candidate eligible for a
re-fetch and re-extraction on the next run. Original bytes stay hashed per
version and are not deleted, but when the bytes are unchanged the same-named
`extracted-<sha256>.json` is replaced by the new extraction, so keep your own
copy if you need to compare parser outputs. Because discovery's `version_hash`
covers only title and URL, a publisher replacing bytes at the same stable URL
without changing either is not detected as a new version. To force a refetch,
remove that candidate's state record (or use a fresh state file) and keep the
old quarantine files for comparison.

**Operational limits.** `page_count` counts PDF pages that produced at least one
text block, not the PDF's declared page count. The quarantine grows with every
changed version and is never garbage-collected. The command has no lock: run one
ingestion process per state/quarantine pair at a time. The state is validated
structurally and file-presence paths must stay inside the candidate's quarantine
directory, but the remaining provenance values in the state file are trusted
operator input.

**Extraction limits.** PDF extraction is standard-library and handles
uncompressed or Flate-compressed content streams with literal/hex strings,
UTF-16BE/LE string BOMs, PDF 1.5 object streams, multiple page content streams,
and embedded-font `ToUnicode` CMaps (`bfchar`/`bfrange`, including array
ranges). It does **not** decode LZW/ASCII85/encrypted PDFs, scanned images, or
glyphs missing from an incomplete subset-font map. Such documents fail as
`unsupported_pdf_encoding`, `malformed_document`, or `no_extractable_text`, or
leave `U+FFFD` placeholders where a map omits a used code; blocks containing
only replacement characters are dropped. OCR is not implemented or measured.

Live smoke checks on 2026-10-27 fetched and parsed one BOE PDF (2 pages, 4,179
characters, no replacement characters) and one BOJA PDF whose HTTP `307`
redirect stayed on the same issuer (35 pages, 80,388 characters, about 6.3%
replacement characters because subset fonts omitted glyph mappings). That is
not a general accuracy measurement: a reviewer must still compare the original
and extracted text, especially for BOJA subset fonts, before proposing a
canonical update. HTML parsing skips
`script`/`style`/`template`/`noscript` and preserves heading hierarchy, but it
is not a full-text browser rendering.

The fetch uses the platform CA trust store. If `urllib` raises
`CERTIFICATE_VERIFY_FAILED` while `curl` succeeds, set `SSL_CERT_FILE` to a CA
bundle (for example the `certifi` bundle inside `backend/.venv`) rather than
disabling certificate verification.

The extractor and state never log document text or upstream exception text;
failure categories are fixed strings. Keep the quarantine and state directories
access-controlled and back them up if review history matters.

## Legal change-impact analysis

`app/change_impact.py` compares the versions that candidate ingestion recorded
and links possible impact to the approved catalog, reviewed passages, and
reviewed answer-evaluation cases. It is read-only: it never reads or writes an
answer path, never edits `knowledge/source_catalog.json`,
`knowledge/passages.json`, or `knowledge/pac_answer_eval.json`, never changes a
lifecycle or review status, and never retires, replaces, or approves a source.
Every candidate that could touch reviewed knowledge stays for an identified
human reviewer.

**Inputs.** `--ingestion-state` and `--quarantine` are the
`official-ingestion-state-v1` file and quarantine directory written by
`ingest_official_documents.py`; only candidates whose state is `extracted` have
text to analyze. `--catalog` and `--passages` are the approved
`source-catalog-v1` and `passage-set-v1` artifacts, validated again with the
existing validators as of `--as-of`; an invalid catalog or passage set is a
hard error. `--cases` is optional and reads the identity and reference fields of
a `pac-answer-eval-v1` case set (`app/answer_eval.py` remains the authoritative
validator for the full case contract). `--as-of` is required and is the only
date in the report.

Run it from the repository root with the ingestion state and quarantine produced
by the previous step:

```sh
backend/.venv/bin/python backend/scripts/analyze_legal_changes.py \
  --ingestion-state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --as-of 2026-10-27 \
  --report /path/to/legal-change-impact-report.json
```

Omit `--cases` when no reviewed case set is available. The command writes the
report and prints a compact summary (counts plus the ids that need review).
Exit `0` means no candidate needs review and no analysis failed, `1` means the
report was written and at least one candidate needs review or failed analysis,
and `2` means the run aborted before writing: an unreadable or invalid catalog,
passage set, case set, or ingestion state, a missing `--as-of`, more than 1,000
candidates, a report path inside the repository `knowledge/` directory, or an
unexpected exception. Error output is the fixed error name only, never a path,
exception text, or document value.

**What it reports.** For each candidate: the recorded current and previous
original hashes, whether the version is an approved copy, unchanged since
ingestion, a new version, or has no baseline; a bounded block-level old/new text
diff (counts plus at most five excerpts); explicit `publication`, `amendment`,
`repeal`, and `validity` signals with page/section location and a bounded
excerpt of at most 280 characters (at most 50 signals per candidate); and the
potentially affected catalog sources, reviewed passages, and reviewed evaluation
cases with the reason for each link. Reported links come from the candidate's own
approved-source identity or URL, the candidate's `content_sha256`, instrument
references such as `Real Decreto 1048/2022` named in the same sentence as a
signal, passages belonging to an affected source, and passages that themselves
cite an affected instrument. Only a title that *starts* with a numbered
instrument (for example `Real Decreto 2200/2099, por el que se modifica …`) makes
that instrument the candidate's own identity; an unnumbered title such as
`Resolución de 9 de septiembre de 2099, por la que se modifica la Ley 5/2098`
keeps the `Ley 5/2098` as a target instead of dropping the link. A passage or case
can link a target instrument whose own source is absent from the catalog; that
candidate is review-required with the reason `affected_passage`, so a reported
link never coexists with `review.required: false`. The readable
contract is `knowledge/legal-change-impact.schema.json`
(`legal-change-impact-report-v1`).

**Machine-evident versus ambiguous.** A signal is `machine_evident` only when
the sentence states the action explicitly: an amendment or repeal that names a
resolvable instrument in the same sentence, a validity statement with an
explicit `d de mes de aaaa` or `dd/mm/aaaa` date, or a publication reference
that names an official bulletin together with a number or date. Triggers are
broad Spanish word stems, not a legal-action parser: `derog*`/`revoc*`/
`deja sin efecto`/`pierde vigencia` for repeal; `modific*`/`modifiq*` (including
the nouns `modificación` and `modificaciones`)/`nueva redacción`/
`se suprime|añade|adiciona` for amendment; `entra|entrada en vigor`/`prorrog*`/
`mantiene su vigencia`/`se extiende|amplía|prorroga|reduce … hasta` for
validity; and bulletin names/`se publica`/`publicado en el` for publication. A
static `el plazo … hasta …` or `la vigencia … hasta …` sentence with no change
wording is not a validity signal at all — only change wording such as
`se extiende/amplía/prorroga/reduce … hasta` plus an explicit date is. Because
the stems are broad, a document-part heading or noun phrase such as
`Disposición derogatoria única.`, `Modificaciones presupuestarias.`, or
`La modificación de las condiciones de acceso se aprueba por resolución.` is
reported as `ambiguous` and needs review; only a document part with no trigger
word, such as a bare `disposición adicional`, emits no signal. Everything else
is `ambiguous`: no named instrument, no explicit date, an incomplete publication
reference, any `U+FFFD` replacement character, or recognised negation. Negation
is sentence-scoped and limited to the listed phrasings:
`no se modifica/deroga/suprime/publica`, `sin que se modifique` (and the other
listed subjunctive verbs), `no supone/implica/conlleva una
modificación/derogación`, `no queda/quedan derogado/modificado/sin efecto`,
`no deja/n deja sin efecto`, `no pierde/n su vigencia`, `en ningún caso`,
`tampoco`, and `nunca`. Other negative wording is read as positive or missed.
Any ambiguous `publication`, `amendment`, `repeal`, or `validity` signal —
negated wording included — makes that candidate review-required
(`ambiguous_signal`), even when it links no approved source, so a negated
sentence or an unlinked blanket repeal cannot pass as "nothing to review".
Negated signals are never linked to an instrument. The rule has no
exception for an unchanged approved copy: if the approved text itself contains
wording this analyzer cannot read as machine-evident, the report keeps asking
for an author instead of deciding for it. No signal of any class authorizes
retirement; the report's `review_gate` fixes `automatic_retirement` to `false`
and `automatic_retirement_allowed` to `false` for every candidate. A candidate
that names an affected source stays review-required until a human resolves it in
the reviewed-update workflow or the operator discards it from the ingestion
state; re-running the analysis is idempotent.

**Determinism.** The report carries the SHA-256 of every input, the analyzer
version, and the supplied `as_of` date — no wall-clock timestamp. Repeated runs
over the same pinned inputs produce byte-identical output, and the file is
written atomically. Byte-identical reports are not a legal conclusion: they
reproduce the same lexical reading of the same extracted text.

**Failure and recovery.** A candidate whose ingestion status is `failed` or
`rejected` has no extracted text, so it is reported as
`version_status: no_extracted_document` with
`analysis_failure: no_extracted_document`, an empty signal list, and no review
reason: the field says why no text analysis exists, and retrying or fixing the
ingestion is owned by the ingestion state (`status`, `failure`, `attempts`), not
by this report. Per-candidate analysis failures are recorded as fixed
categories (`missing_extracted_document`, `extracted_text_mismatch`,
`malformed_extracted_document`, `size_limit_exceeded`, `internal_error`) and
never abort the other candidates; that candidate's previous good report entry is
not preserved, because the report is a derived artifact and is meant to be
regenerated. A globally invalid input exits `2` and overwrites nothing. Bounds
per candidate: 5,000 blocks / 2,000,000 characters of current text, 50 signals
(each with an excerpt of at most 280 characters), five text-diff excerpts, and
1,000 candidates per run.

**Limits.** Detection is lexical Spanish matching over extracted text, not legal
interpretation: it can miss a change phrased in unfamiliar wording, cannot
decide legal effect, and cannot resolve a conflicting or incomplete source.
Triggers are broad word stems, so a real document's static wording (`entrada en
vigor`, `prórroga`, `modificación`, a `Disposición derogatoria` heading) usually
produces an ambiguous signal: review-required may be near-universal, and that
reviewer load is the price of not silently dropping a legal change. Negation
recognition covers only the listed phrasings; other negative wording is read as
positive or missed. A static deadline sentence without change wording produces
no validity signal, so a deadline change inside such a sentence is visible only
through the text diff and `text_changed_without_signal`. Only a version recorded
by candidate ingestion is compared; discovery's `version_hash` covers only title
and URL, so bytes replaced at a stable URL without a new version are invisible
here. If the previous extracted document is missing from the quarantine, the
diff is reported as unavailable instead of guessed. A failed or rejected
ingestion is reported as `analysis_failure: no_extracted_document` with no
review reason and does not raise the gate on its own; if those are the only
unresolved candidates the CLI still exits `0`, so exit status alone does not
report the gap and the ingestion state must be checked separately. Source,
passage, and case links are string- and draft-digest based and do not establish
that a passage is still an accurate answer to any question. The report contains
bounded excerpts of official public document text for review, never an answer,
and never personal or land data; store it with the same access control as the
quarantine. Nothing in this command updates the corpus, so no legal-coverage or
answer-quality claim follows from it. Only synthetic fixtures back the feature
today; there is no live run against a published amendment and detection
precision/recall is unmeasured.

## Human-reviewed knowledge update packages

`app/review_package.py` turns one reviewed proposal over quarantined candidates
into a bounded draft review package. It is standard-library only, offline, and
read-only over `knowledge/`: `prepare` and `decide` write only under the
operator's workspace. `merge` is the only function that writes canonical
artifacts, and only after a named requested reviewer other than the author
approves and every required check still passes.

**This is a local draft, not a hosting-platform pull request.** The package is
an inspectable directory (`package.json`, `REVIEW.md`, and after review
`decisions.json`, `DECISION.md`, `merge.json`) that an operator can attach to a
real repository PR. This repository has no Git/hosting API integration, so
GitHub branch protection is **not** enforced here; the controlled `merge`
command independently verifies the recorded approval. Direct filesystem writes
to `knowledge/` remain possible for anyone with access, so keep the workspace
and canonical files access-controlled and reviewable in Git.

### Prepare

Run it from the repository root with the ingestion state and quarantine produced
by the preceding pipeline, the current approved catalog/passages, a reviewed
proposal, and at least one named reviewer:

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py prepare \
  --ingestion-state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --proposal /path/to/knowledge-update-proposal.json \
  --cases knowledge/pac_answer_eval.json \
  --reviewer "Nombre Revisor" \
  --as-of 2026-10-27 \
  --workspace /path/to/review-workspace
```

Omit `--cases` only when the proposal makes no catalog or passage change: a
proposal that changes the reviewed corpus requires the reviewed case set. With
`--cases`, preparation validates both the current and the **after-state**
catalog/passages against it, records the case-set digest in the package, and
blocks readiness with `proposal_evaluation_impact: orphaned_cases:<ids>` when a
removal or replacement would leave a reviewed case without its expected source
or passage. Without `--cases`, any change is blocked with
`proposal_evaluation_impact: cases_unavailable`; a no-op proposal still passes.
`--workspace` must stay outside the repository `knowledge/` directory. `prepare`
writes `<workspace>/<package_id>/package.json` and `REVIEW.md`; canonical
knowledge is byte-identical afterwards. It exits `0` when `merge_readiness` is
`ready_for_review`, `1` when any automated check failed
(`needs_human_attention`), and `2` on invalid input, a non-human/self reviewer,
a reviewer outside the requested set, or another refused gate.

The proposal contract is `knowledge-update-proposal-v1`: `summary`, 1–20
`candidates` (each a 64-character id from the ingestion state, with optional
`resolution` `{findings, note}` and `unknown_fields`), `catalog` and `passages`
sections `{add, update, remove}`, optional `author` (defaults to the preparer
automation identity), `links` mapping every added, updated, or removed catalog
source and every passage change to its selected candidate, and optional
`unresolved_questions`. A proposal cannot exceed the candidate bound, link to a
candidate it did not select, or introduce an unknown field outside `validity`
and `applicability`. A passage edit or removal without exactly one
source-to-candidate link fails `proposal_provenance`.

The package records source URL/issuer/registry provenance, observation and
retrieval times, original and extracted hashes and locations, page/section
counts, a bounded old/new text diff and signal excerpts, proposed catalog and
passage changes, affected sources/passages/evaluation cases, every automated
check, unresolved questions, and explicit limits. Source document text is
rendered only as fenced evidence, never as instructions. Unknown validity and
applicability stay absent; a proposal that writes a literal unknown value,
omits provenance, links a different candidate hash/URL, misstates the extracted
digest, or leaves an ambiguous impact finding unresolved becomes
`needs_human_attention` and cannot be approved.

The package also binds the evaluation-case digest and the after-state check
result (`proposal.evaluation`), and its after hashes use the catalog/passages'
existing field order for entries the proposal does not rewrite rather than
sorting every entry; a newly added or rewritten entry follows the proposal's
own serialization. The readable contracts
are `knowledge/knowledge-update-review.schema.json` (package) and
`knowledge/knowledge-update-review-decisions.schema.json` (decision history).
An orphaned evaluation case blocks readiness. Affected and rewritten cases are
embedded as **report-only**: they are not re-run and are not a pass/fail gate or
a quality claim.

### Decide

A named human other than the proposal author records one decision:

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py decide \
  --package-dir /path/to/review-workspace/<package_id> \
  --reviewer "Nombre Revisor" \
  --decision approve \
  --decided-on 2026-10-28 \
  --note "Original y texto extraído comparados."
```

`--decision` is `approve`, `request_changes`, or `reject`. Approval is refused
for a known automation/CI identity (`reviewer_not_human`: `ci`, `cd`, `ci/cd`,
`actions`, `github-actions`, `workflow`, `pipeline`, `automation-*`,
`service-account`, `preparer`, bot names), a reviewer the package did not
request (`reviewer_not_requested`), the proposal author (`self_approval`), a
package with failing checks or `needs_human_attention` (`approval_blocked`), or
a stale package/check digest (`stale_approval`). A green CI result, label, or
matching hash is never approval. The identity list is a denial list, not
authentication: local records cannot prove who typed a name. Every decision is
appended to `decisions.json` and `DECISION.md`; a later `request_changes` or
`reject` revokes an earlier approval. A revised proposal produces a new package
id with new checks and no inherited approval.
`decide` exits `0` on a recorded decision, `2` on any refusal; after a merge it
refuses with `already_merged`.

### Merge

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py merge \
  --package-dir /path/to/review-workspace/<package_id> \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json
```

`merge` writes canonical artifacts only when the effective decision is
`approved`, the checks digest still matches, the approver is a named requested
human other than the author, readiness is `ready_for_review`, and the current
canonical bytes still match the package's recorded `before` hashes. When the
package recorded a case-set digest, `--cases` is mandatory (`cases_required`)
and the file must still hash to that digest (`evaluation_cases_drift`);
`merge` then revalidates the after-state against those cases, so editing the
cases after preparation cannot bypass the gate. It revalidates the resulting
catalog/passages as of the **approval date**, recomputes `after` hashes without
reordering entries, writes both files atomically, and records `merge.json` with
`reindex_required: true`, `reindexed: false`, and `released: false`. Canonical
drift, a tampered package/decision, an expired source, changed cases, or an
invalid result refuses with exit `2` and writes nothing. A second merge is
refused (`already_merged`). A no-op proposal leaves both canonical files
byte-identical.

**Merge is not release.** It never reindexes, releases, or deploys. The separate
reindex/release feature owns index rebuilds, artifact/model versions, rollback,
and the plainly stated corpus boundary. An approved bounded update is not
legal-coverage or answer-quality certification.

### Limits

- The local package is not a hosted PR, so host-enforced merge protection and
  reviewer assignment do not exist; the `merge` command is the procedural gate.
- Reviewer identity and decisions are plain local records, not cryptographic
  signatures. The commands refuse known automation identities and
  self-approval, require an approver from the package's `requested_reviewers`,
  and bind decisions to the package/checks digest, but identities are not
  authenticated and a malicious operator can still edit the workspace or
  canonical files directly.
- Original-byte verification requires the quarantined original to still exist.
  A missing copy is a reviewer question, not an automated comparison; only a
  person can compare the extracted text with the official original.
- A proposal that changes the reviewed corpus requires the reviewed evaluation
  case set, and merge must receive the same digest-bound file. Evaluation cases
  are validated for references, not re-run; removing or rewriting a referenced
  source/passage blocks readiness until a human updates the cases in a separate
  reviewed change. A no-op proposal is allowed without cases.
- Review display is bounded (at most 40 change entries and truncated field
  values/excerpts); open large documents in the quarantine for a full reading.
- Canonical after hashes and merge writes preserve the catalog/passages' field
  order. A proposal input is normalized through the package's sorted JSON, so a
  newly added entry's own keys are sorted while every existing entry keeps its
  reviewed order. Only a real change alters the file; an empty proposal leaves
  it byte-identical.
- Extraction inherits the standard-library PDF/HTML limits above (no OCR,
  encrypted/scanned documents fail closed, subset-font maps can leave `U+FFFD`).
- Workspace, decisions, and quarantine evidence are retained by the operator
  and are never garbage-collected. Deleting them makes an old package's
  evidence unrecoverable.
- Merge writes the catalog and passages atomically one file at a time, not as a
  single transaction. An OS failure between the two writes (or before
  `merge.json` is written) can leave the pair inconsistent; the package then
  refuses with `canonical_drift`. Restore both Git-tracked files or reapply the
  approved merge before retrying.
- Review turnaround and reviewer availability are manual; nothing expires an
  unapproved package. A pending package simply never merges.
- Only synthetic fixtures back this flow today; there is no live run against a
  real published update.
