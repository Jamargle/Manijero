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

## Validator checklist

- [ ] Project owner is named as initial operator in the runbook.
- [ ] Development reload mode is not used for the hosted service.
- [ ] Campaign configuration remains explicit and validated.
- [ ] Rollback and corpus/config restore were rehearsed.
- [ ] Logs do not contain raw questions or land context.
- [ ] Operational limits are stated without an invented SLA.
