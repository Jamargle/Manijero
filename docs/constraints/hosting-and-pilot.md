# Constraints: Hosting and pilot

Durable MUST/MUST NOT rules for hosted pilot operations and provider boundaries. Part of the index in [`CONSTRAINTS.md`](../../CONSTRAINTS.md); paths in backticks are relative to the repository root.

## Hosted pilot and provider boundaries

- **MUST**: a QA test build takes its pilot token only from the QA access key (`<QA home>/credentials/qa-test-device.token`, or the `MANIJERO_PILOT_TOKEN_FILE` test override) and **MUST NOT** read `pilot-token.local`; a local build **MUST NOT** read the QA key or the QA address file. Reason: [`client_environment_builds`](../specs/client_environment_builds.md).
- **MUST**: a managed tunnel (Cloudflare Tunnel for a pilot; Tailscale Funnel for QA only) is transport only; any public pilot API MUST enforce its own
  authentication, authorization, per-client rate limiting, and request-size limits. Reason:
  `hosting_provider_review` found that Cloudflare Tunnel removes the public origin IP but does not
  authenticate the application, and the current OpenAPI contract declares no security scheme.
- **MUST**: QA runs on the owner's Mac behind Tailscale Funnel with made-up test data only, and only `./scripts/init.sh --qa-deploy` (or `--qa-update`/`--qa-rollback`) starts it. The pilot launcher accepts a `pending` privacy review (never `rejected`, invalid, or unreadable) and local drafting is enabled only when the environment is exactly `MANIJERO_DEPLOYMENT_PROFILE=pilot`, `MANIJERO_ENVIRONMENT=qa`, and `MANIJERO_QA_TEST_DATA_ONLY=yes`; it prints a plain test-data-only warning. The flag is set only in the QA `docker run` arguments, never in a settings file. Pilot, prod, and Gemini stay blocked by the review. The launcher's public-bind acknowledgement is allowed only inside the container, whose host publish is `127.0.0.1`. Reason: owner decision 2026-11-02, [`qa_server_deployment`](../specs/qa_server_deployment.md).
- **MUST NOT**: let a real-user question transit a host, tunnel, or generation provider until the
  current terms, data flow, log/retention behavior, and qualified privacy review are recorded and
  approved. Reason: the 2026-10-27 decision keeps the owned-server path blocked on owner attestation
  and keeps Gemini disabled by default; provider selection alone is not pilot approval.
- **MUST**: the hosted pilot service MUST start only through the pilot-profile launcher
  (`backend/scripts/serve_pilot.py`), which validates the explicit campaign, the client
  credentials, and the reviewed corpus before accepting traffic and refuses the development
  profile, reload mode, and a non-loopback origin without an explicit acknowledgement. A
  corpus or campaign defect MUST fail readiness (`503`), never produce a degraded answer.
  Reason: `./scripts/init.sh --backend` is a development path with reload, `0.0.0.0`, a defaulted
  campaign, and no authentication; starting the pilot from it would serve unvalidated configuration
  and wrong-campaign evidence.
- **MUST**: pilot access control MUST be application-owned: one bearer token per client stored only
  as a SHA-256 digest in a mode-`0600` operator file, that client's per-minute request allowance, and
  a bounded request body, all enforced before the answer route runs; `GET /health` MUST stay
  liveness-only and `GET /ready` MUST stay a separate campaign-plus-corpus readiness check whose
  payload carries no corpus value. Rate limits are per process and MUST NOT be described as
  cluster-wide or edge-enforced. Reason: the hosting decision found that a managed tunnel is
  transport only and the API declared no security scheme; a per-worker window that is described as
  global would overstate the protection.
- **MUST**: pilot operational logs MUST contain only one request record with the method, route path
  (no query string), status, duration, and gate; they MUST NOT contain question text, land context,
  names, notes, client identifiers, tokens, or response bodies, and the development access log MUST
  NOT be repurposed as the pilot log. Reason: the hosting decision's log condition and the accepted
  minimal-land-context contract; default ASGI/provider logs are not reviewed and must not be assumed
  silent.
- **MUST**: a pilot corpus/configuration backup MUST record size and SHA-256 for every file
  and MUST NOT contain client tokens, tunnel credentials, or other secrets: the backup
  command accepts only the named non-secret configuration files, refuses a credential
  basename or credential markers in an accepted file, and writes the backup tree
  owner-only. A restore MUST require explicit confirmation, verify every recorded hash,
  validate the catalog/passages pair **before** the first canonical write, refuse a
  canonical target it cannot read, and replace each file atomically; if a later write fails
  it MUST attempt to restore the prior bytes and report failure rather than claim success.
  A restored canonical artifact MUST be readable by the service account: the command writes
  `0644` (backup files stay `0600`), checks that the written files have the read bits, and
  fails closed with `corpus_not_readable`, rolling the prior content and mode back, if they
  do not. The runbook MUST check cross-user readability (`sudo -u manijero test -r`) before
  starting the service, because file mode alone cannot prove path traversal.
  A crash between the two replacements can leave a mixed pair and is recovered by
  re-running the same verified restore, so the command MUST NOT be described as a single
  atomic pair swap. A restore that yields an expired or not-ready corpus MUST report
  `not_ready`, never success; a restore MUST NOT run while the service is active. Reason: a
  half-written catalog/passage pair, a copied credential, or a silently stale corpus is
  worse than a known-good backup, an unverified backup is not a recovery path, and a
  restore that leaves the corpus unreadable by the non-root service takes the pilot down.
- **MUST**: a client's pilot bearer token MUST come only from the git-ignored build setting
  (`pilot-token.local`, or the `MANIJERO_PILOT_TOKEN_FILE` override with fake tokens in tests), never
  from `local.properties`, a JVM system property, an environment entry, or `jvmArgs` of a Desktop
  task. It MUST be sent only on `POST /ask` over `https` or `http` to a loopback host (`localhost`,
  `127.0.0.1`, `[::1]`, `10.0.2.2`), and MUST NOT be shown, logged, committed, put in state or
  exceptions, or sent on `/health` or `/ready`. It MUST NOT be built into an Android release variant
  or a packaged/release Desktop output, even when the file exists; only Android debug and the
  Desktop `run` task may carry it. Reason:
  [`client_pilot_credentials`](../specs/client_pilot_credentials.md) — the token is a per-client
  access credential, and a cleartext LAN request or a logged header would hand it to anyone on the
  path; decision 5 keeps it out of anything that could be distributed.
- **MUST**: the answer pipeline trace (`backend/app/answer_trace.py`) MUST be off by default and
  turned on only by the exact `MANIJERO_ANSWER_TRACE=on`; it MUST record question, answer, or draft
  text only when `MANIJERO_DEPLOYMENT_PROFILE` is explicitly set to exactly `development` (an unset
  profile, and every other profile, gets the
  metadata-only allowlist `METADATA_KEYS`); it MUST write only to the fixed git-ignored
  `build/answer-traces/` folder and delete files after 7 days. Reason: owner decisions 1-3 in
  [`docs/specs/answer_pipeline_trace.md`](../specs/answer_pipeline_trace.md); the explicit-profile
  rule was added in the batch 4 integration (owner decision 2026-11-02), and the local service start
  states `development`.
- **MUST**: the `/ask` response `inspection` object (`answer-inspection-v1`) MUST be sent only when
  `answer_trace.text_allowed` holds (the profile is explicitly stated as exactly `development`), MUST
  carry only the published `INSPECTION_KEYS` allowlist (ids, scores, fixed codes, timings, public
  corpus text), and MUST NOT be sent in pilot, QA, or prod, nor when the profile is unset or unknown.
  Reason: owner decision 2 in [`docs/specs/rag_inspector_view.md`](../specs/rag_inspector_view.md).
