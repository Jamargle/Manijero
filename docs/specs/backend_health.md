# Feature specification: `backend_health`

## Source metadata

- **Feature:** `backend_health` — Service health response (`backend`).
- **Source behavior:** The service exposes a health response that lets the app or operator distinguish an available service from an outage.
- **Source verification:** Request the health endpoint when running the service and confirm its documented success response.
- **Note from the feature list:** The backend is proposed in `MasterPlanV3.md` but was not present in the repository scaffold; this feature establishes its initial service boundary.

## Goal

Expose a small, stable HTTP health response so an app or operator can tell
whether the Manijero backend process is serving requests.

## Scope

- Add a FastAPI application under `backend/app`.
- Add `GET /health` with HTTP 200 and the JSON body
  `{"status":"ok","service":"manijero-backend"}`.
- Publish the endpoint in the generated OpenAPI document and document the
  local run/smoke command.

## Non-goals

This feature does not implement `/ask`, retrieval, model/provider checks,
authentication, deployment, or client integration. The endpoint is a process
liveness check and must not imply that future external dependencies are ready.

## Verification

From `backend/`, install `requirements.txt` (and `pytest` in the development
environment) and run `pytest`. Start the service
with Uvicorn and request `/health` with `curl` for the operator smoke check.

## Durable documentation impact

`backend/README.md` documents the endpoint and explicitly distinguishes HTTP
process liveness from dependency readiness. No client or global architecture
change is required.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
# The health test needs pytest; ./scripts/init.sh --fast prints the virtualenv recipe when it is missing.
./scripts/init.sh --backend-tests tests/test_health.py
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/backend_health.appendix.md`](backend_health.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/backend_health.md` remains the authoritative acceptance record.
