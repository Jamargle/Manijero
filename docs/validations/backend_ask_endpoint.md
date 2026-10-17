# Validation: `backend_ask_endpoint`

## Verdict

**Accept** — 2026-10-17.

## Independent checks

- Reviewed the feature contract, appendix evidence, implementation diff, API contract, runtime behavior, privacy boundaries, and durable documentation.
- Reran `env MANIJERO_PYTHON=/tmp/manijero-backend-ask-endpoint-venv/bin/python PYTEST_ADDOPTS='-p no:cacheprovider' PYTHONDONTWRITEBYTECODE=1 ./scripts/init.sh --feature backend_ask_endpoint`: contract examples passed and all 25 endpoint tests passed.
- Ran `git diff --check`: passed.
- Confirmed the route composes the accepted retrieval, grounding, abstention, and clarification decisions; invalid or unsupported corpus state fails closed; malformed and invalid requests do not echo request values; and `/health` remains liveness-only.
- Confirmed the canonical corpus is valid but empty, fixture-backed answers are explicitly synthetic, and the app's platform base-URL wiring remains an open limitation.

The scoped security and privacy review found no relevant issues. The focused test run emitted an upstream Starlette/httpx deprecation warning; it did not affect the result.
