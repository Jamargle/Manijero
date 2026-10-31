# Constraints: Hosting and pilot

Durable MUST/MUST NOT rules for hosted pilot operations and provider boundaries. Part of the index in [`CONSTRAINTS.md`](../../CONSTRAINTS.md); paths in backticks are relative to the repository root.

## Hosted pilot and provider boundaries

- **MUST**: a managed tunnel is transport only; any public pilot API MUST enforce its own
  authentication, authorization, per-client rate limiting, and request-size limits. Reason:
  `hosting_provider_review` found that Cloudflare Tunnel removes the public origin IP but does not
  authenticate the application, and the current OpenAPI contract declares no security scheme.
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
