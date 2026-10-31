# Feature Spec: `hosted_pilot_operations`

## Source metadata

- **Feature:** `hosted_pilot_operations` — Prepare and operate a private hosted pilot service (`operations`).
- **Status at planning:** `not_started`; depends on `hosting_provider_review`, `backend_ask_endpoint`, and `backend_campaign_validity`.
- **Source behavior:** The project owner can deploy, monitor, update, roll back, and respond to outages for a private hosted `/ask` service.
- **Feature-list verification:** A documented deployment and recovery rehearsal succeeds on the selected host, with campaign configuration and a tested rollback.
- **Feature-list note:** Prefer the owned server plus a managed tunnel if the readiness review supports it; otherwise use the reviewed managed-host fallback.

## Goal and boundaries

Make the existing local FastAPI service operable for a small private pilot. The project owner is the initial operator and owns service availability, campaign configuration, source refresh, rollback, and outage response.

**In scope:** repeatable deploy/redeploy, HTTPS ingress via the reviewed provider, explicit campaign setting, restricted administration, health and outage checks, update/rollback/runbook, corpus/config backup and restore, and a clear pilot support contact/path.

**Non-goals:** public launch, high availability/SLA, public account system, a hosted LLM, telemetry beyond approved operational logs, or private app packaging/distribution (separate feature).

## Job story

When a pilot user opens Manijero, I want the owner-operated API to be reachable and recoverable, so the user receives the reviewed service or a clear unavailable message.

## Acceptance scenarios

### Deploy and configure

Given the selected provider and deployment artifact, when the owner deploys, then `/health` reports process liveness and `/ask` uses the explicit active campaign and reviewed local corpus.

### Recover from an update failure

Given a deployment introduces a failure or invalid corpus/configuration, when the owner follows the runbook, then the prior known-good release and corpus can be restored and the service's state is confirmed.

### Handle outage

Given the service or ingress is unreachable, when a health check or pilot report detects it, then the owner has a documented response path and the client renders its accepted service-unavailable state without treating failure as an answer.

### Limit operations data

Given requests reach the hosted service, when operations logs are inspected, then they contain only the minimum reviewed operational metadata and do not include raw questions, land names, notes, or land context.

## Technical approach

Use the reviewed provider decision. Add a production deployment definition separate from the development `--backend` script; do not use reload mode or bind assumptions from the local workflow. Keep campaign configuration explicit and validate it before accepting traffic. Define readiness, liveness, corpus refresh, backup/restore, rollback, access, and outage steps. Retention of question/answer text is controlled only by `pilot_privacy_readiness`; the operations feature must not independently log it.

## Expected file changes

- `backend/` deployment files and runbook; `scripts/` only for reproducible deployment operations.
- `backend/README.md`, `README.md`, and `docs/risks-and-open-questions.md`.
- Smoke/contract tests for deployed configuration boundaries where feasible.

## Visual design impact

None.

## Durable documentation impact

- `ARCHITECTURE.md`: update hosting and operational boundary after selection.
- `CONSTRAINTS.md`: add any durable data/logging or deployment rules established by the accepted runbook.
- `AGENTS.md`: not needed.
- `backend/README.md`: create/update the pilot deployment and recovery procedure.

## Focused verification

<!-- verify:start -->
```sh
./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`hosted_pilot_operations.appendix.md`](../archive/specs/hosted_pilot_operations.appendix.md).
