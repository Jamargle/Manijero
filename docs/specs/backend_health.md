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

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Implemented FastAPI GET /health with documented HTTP 200 response.
- backend/tests: 2 passed; Uvicorn HTTP smoke check returned the documented JSON body.
- Independent validation: accept (2026-10-11). Record: docs/validations/backend_health.md.
