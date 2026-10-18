# Validation: `backend_campaign_validity`

## Verdict

**Accept** — 2026-10-18.

## Independent checks

- Reviewed the feature contract, implementation diff, full-corpus validation order, API contract, runtime behavior, privacy boundaries, and durable documentation.
- Ran `MANIJERO_PYTHON=<isolated-venv>/bin/python ./scripts/init.sh --feature backend_campaign_validity`: contract examples passed (2 request and 3 response examples); all 40 focused campaign and endpoint tests passed.
- Confirmed malformed off-campaign metadata and dangling source references are rejected before campaign filtering, explicit campaign configuration is required, and mismatched/multiple question years abstain before generation.
- Confirmed the request/response contract remains unchanged and expiry uses the configured UTC request date.

The scoped security review found no relevant issues. Pytest emitted one upstream Starlette/httpx deprecation warning; it did not affect the result.
