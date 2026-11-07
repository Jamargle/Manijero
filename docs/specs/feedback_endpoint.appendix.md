# feedback_endpoint — appendix

## Research

### Repository state

- `contracts/openapi.yaml` is the single source of truth for `POST /ask`, `/health`, `/ready`; `/metrics` is intentionally outside it, and `/feedback` is only named in the old roadmap, never specified.
- `contracts/validate_examples.py` is the lightweight contract check and has no external dependency.
- `backend/app/ask_api.py` shows the house request-model style: `extra="forbid"`, strict fields, `mode` validation, and no free-text echo in errors.
- No feedback route, module, schema, example, or counter exists; `backend/app/main.py` includes `ask_router` and installs `TestClient`-friendly handlers.
- `PilotConfig` has exactly two profiles (`development`, `pilot`); only `pilot` authenticates and rate-limits.
- `pilot_logging.py` emits one request line with method, path, status, duration, and gate; it never records bodies or rating values.
- `health_metrics.py` already owns a `ContextVar`-backed, label-clamped registry and is the natural place for an accepted-feedback counter.
- `retention.py` stores redacted Q/A only after the per-question opt-in; it is not a feedback store and must stay untouched.
- `backend/tests/test_ask_endpoint.py` and `test_health_metrics.py` provide the app/client, fake-pilot, and metrics fixtures to copy.
- `docs/archive/MasterPlanV3.md` D9 defines the optional feedback slice as a "simple rating with minimal data collection"; B10 lists `/feedback`. This feature is that endpoint, narrowed to a fixed two-value rating.
- `docs/constraints/hosting-and-pilot.md` currently limits the client pilot token to `POST /ask`; this feature must widen that rule to `/feedback` under the same transport condition.
- `docs/specs/pilot_privacy_readiness.md` accepted default-off, redacted Q/A retention; it does not define feedback.
- `docs/pilot-privacy.md` has one data-flow inventory row per processed item; a feedback rating is a new row.
- `docs/risks-and-open-questions.md` line 69 keeps durable feedback and non-content trace retention open before real-user use.
- `PROGRESS.md` current state says the pilot is prepared but not operating and the privacy review is `pending`.
- `scripts/init.sh` runs `--feature` commands verbatim and `--backend-tests <files> -q` for targeted pytest.

### Existing patterns to follow

- Strict, closed request models (`extra="forbid"`, strict scalar types) and a generic `sanitize_request_validation` handler that never reflects rejected values.
- Pilot access is application-owned in `PilotGuardMiddleware`; `GATED_PATHS` currently gates `/ask` and `/metrics`.
- Metrics hooks are module-level, `_safe`-wrapped, bound by the middleware, and accept only fixed allowlisted label values.
- Contract examples are validated by a dependency-free script in `contracts/`, not by the backend suite.
- Focused backend checks use `MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests <files> -q`.

### Current gaps

- No `/feedback` path, schema, example, route, or counter exists.
- `health_metrics.ROUTES` does not include `/feedback`; its independent test allowlists will reject a new `rating` label and `204` code until updated.
- With no storage or export, feedback is an anonymous aggregate only; it cannot be joined to a particular answer, question, or person. No idempotency key exists, so a retry after an unknown outcome counts again.
- The test-only mock answer service serves only its existing examples and is intentionally unchanged; the UI feature must use its own fake for feedback.
- The pending privacy review record does not yet name the feedback flow; this feature must not claim that it does.

## Implementation plan

1. Add `FeedbackRequest` and the `/feedback` path to `contracts/openapi.yaml`; add the two request examples and extend `contracts/validate_examples.py`.
2. Add focused tests in `backend/tests/test_feedback_endpoint.py`: accepted ratings, 204/empty body, rejected extra fields and free text, malformed JSON, body bound, no corpus/campaign requirement, pilot 401/429, separate `/ask` allowance, metrics, and no retention/trace writes.
3. Create `backend/app/feedback_api.py` with the strict model, metric hook, and `204` response; include the router from `create_app`.
4. Add `/feedback` to `PilotGuardMiddleware.GATED_PATHS`, verify the path-specific limiter key keeps it separate from `/ask`, and widen the token-path constraint to `/ask` plus `/feedback` only.
5. Extend `HealthMetrics` with `feedback_total{rating}`, the `rating` label, `/feedback` route, and both zero-valued series; update `test_health_metrics.py` independent allowlists.
6. Update the durable docs in the contract; keep the pilot privacy review record untouched.
7. Run the focused block, then the full backend suite, then `CI=true ./scripts/init.sh --fast`; record one-line evidence.

## Verification plan

- `python3 contracts/validate_examples.py` — prints the updated validated-example count and fails if a feedback example carries an extra key or an unknown rating.
- `./scripts/init.sh --feature feedback_endpoint` — runs the focused block unchanged.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests -q` — full backend suite has no regression.
- `CI=true ./scripts/init.sh --fast` — all offline checks pass, including contract examples.
- Behavior-focused test names to cover: `test_feedback_accepts_useful_and_not_useful_with_204_no_body`, `test_feedback_rejects_extra_fields_and_free_text_without_echo`, `test_feedback_rejects_malformed_json_with_400`, `test_feedback_returns_413_over_the_body_bound`, `test_feedback_works_without_campaign_or_corpus`, `test_feedback_counts_both_ratings_in_metrics`, `test_feedback_does_not_consume_the_ask_allowance`, `test_feedback_pilot_requires_a_client_token`, `test_feedback_creates_no_retention_or_trace_record`, `test_feedback_is_documented_in_openapi_and_examples`, `test_feedback_metrics_have_no_user_values`, `test_feedback_does_not_change_an_ask_response`.
- E2E: not needed. There is no client UI in this feature and the in-process middleware + route stack is exercised by `TestClient`. `answer_feedback_ui` will supply the shared-client and UI E2E path.

## Evidence to capture

- Focused-block result in one line.
- Full backend suite result in one line; `--fast` result in one line.
- Contract validator output count and the two feedback example filenames.
- One line confirming `backend/requirements.txt` is unchanged and no new dependency was added.
- One manual line: `POST /feedback` with each rating returns `204` and no body; `/metrics` shows `feedback_total{rating}` for both ratings and no submitted secret text.
- One line confirming no retention row, trace file, or feedback database is written.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

### 2026-11-06 — implementer (self-verified, ready for independent validation)

- `python3 contracts/validate_examples.py` → `Validated 3 request, 3 response, and 2 feedback examples against answer_api_contract` (new: `contracts/examples/feedback-useful.json`, `feedback-not-useful.json`).
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature feedback_endpoint` → focused tier passed; its targeted suite reported `48 passed, 1 warning` (`tests/test_feedback_endpoint.py tests/test_health_metrics.py`).
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests -q` → full suite `1895 passed, 4 skipped, 1 warning`.
- `./scripts/init.sh --fast` → `All 10 offline checks passed` (`gradle-jvm-test ok`, contract examples ok, backend tests ok, five evaluators ok).
- Manual loopback smoke (temporary uvicorn on `127.0.0.1:8123`, stopped after): `POST /feedback` with `useful` → `204 bytes=0`, with `not_useful` → `204 bytes=0`; an extra `comment` key → `422 {"detail":"Request validation failed."}` with no echo; `/metrics` showed `feedback_total{rating="useful"} 1`, `feedback_total{rating="not_useful"} 1`, `http_requests_total{code="204",route="/feedback"} 2`, and no submitted secret text.
- `test_feedback_logs_only_request_metadata` → the pilot request line carries only method, path, status, duration, and gate; no rating value, token, client id, or submitted content appears.
- `test_feedback_creates_no_retention_or_trace_record` → a configured retention store stayed at zero `retained_qa` rows and no trace file was written by a feedback request.
- `git diff --stat backend/requirements.txt backend/requirements-dev.txt` → empty: no new dependency.
- Durable docs updated: `ARCHITECTURE.md`, `docs/constraints/hosting-and-pilot.md`, `docs/pilot-privacy.md`, `backend/README.md`, `docs/progress/known-limitations.md` (plus its `PROGRESS.md` digest), `docs/risks-and-open-questions.md`. `backend/config/pilot_privacy_review.json` untouched.
- Scope: no client UI, shared DTO, durable feedback store, export, log event, or free text added; `answer_feedback_ui` remains the UI owner.

## Validator checklist

- [ ] Scope matches the contract: only `rating` is accepted; no question, answer, land, client/device id, free text, or answer id.
- [ ] No durable feedback store, export command, log event, or retention integration exists.
- [ ] `204` with an empty body is returned for both allowed ratings; rejected requests are `400`/`413`/`422` and do not echo values.
- [ ] Pilot `/feedback` requires a valid bearer token, has a separate rate window, and local `development` remains open.
- [ ] The token-path constraint now allows `/ask` and `/feedback` only; `/health` and `/ready` remain token-free.
- [ ] `feedback_total{rating}` and `/feedback` are present and privacy-safe; health-metrics independent allowlists are updated.
- [ ] `/ask`, `/health`, `/ready`, `/metrics`, and the pilot privacy review record are unchanged.
- [ ] Focused verification runs unchanged through `./scripts/init.sh --feature feedback_endpoint`.
- [ ] Durable documentation impact followed; `PROGRESS.md`/`feature_list.json` status is updated only by the normal acceptance flow.
- [ ] `docs/validations/feedback_endpoint.md` is created only by the validator, not by implementation.
