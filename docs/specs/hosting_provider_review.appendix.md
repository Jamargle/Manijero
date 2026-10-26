# `hosting_provider_review` Appendix

## Repository research

- `backend/README.md` documents local FastAPI `/health` and `/ask`; no deployment container or host is configured.
- Android/desktop endpoints are currently local development URLs; campaign configuration is explicit.
- MasterPlanV3's own-server/Cloudflare proposal is archived and explicitly not current evidence.

## Implementation plan and tasks

1. Inspect the actual server's owner, connectivity, maintenance window, capacity, power/backup, and recovery capability.
2. Identify one managed-tunnel candidate, a managed-host fallback, and a private artifact-delivery option; read current official terms, privacy/data processing, availability, cost, limits, and exit documentation for each.
3. Map request data, access logs, service logs, and retention for each candidate; include that no hosted LLM is used.
4. Record the owner's selection, review date, source links, unresolved issues, and conditions that trigger re-review.

## Verification plan

- Confirm every provider claim links to a current official source and records an access date.
- Check the decision does not claim legal compliance or zero cost without evidence.
- `git diff --check` is the focused documentation check.

## Evidence to capture

- Server readiness notes, provider comparison, official-source links/access dates, and signed owner decision.

## Feature evidence

## Validator checklist

- [ ] The owned-server path is assessed rather than assumed available.
- [ ] A fallback is evaluated or hosting remains explicitly blocked.
- [ ] Provider data handling, limits, and costs are supported by current official sources.
- [ ] No hosted LLM is described as part of the pilot.
- [ ] The record states its limits and re-review trigger.
