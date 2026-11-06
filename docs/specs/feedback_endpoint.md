# Accept privacy-minimal answer feedback through POST /feedback

## Source metadata

- `id`: feedback_endpoint · `area`: backend-contract · `depends_on`: backend_ask_endpoint, pilot_privacy_readiness · `status` at planning: not_started
- Source: `docs/archive/MasterPlanV3.md` D9 ("simple rating with minimal data collection") and B10 (`/feedback`); the repository privacy rules narrow this to a fixed rating with no stored content or identifiers.
- User-visible behavior: the answer service accepts a two-value rating for an answer at `POST /feedback` and exposes only aggregate, per-process counts. No app UI is added by this feature.
- Verification: dependency-free contract-example checks plus in-process FastAPI tests over fake pilot clients; commands are in Focused verification.
- Notes (planning decisions):
  - The endpoint is anonymous and unlinked: the only field is `rating` (`useful` or `not_useful`). It accepts no question, answer, land context, land/client/device identifier, free text, or answer id.
  - It does not persist feedback, add a feedback log event, or create a new retention surface. It increments an in-memory metric and returns `204`. Durable feedback retention remains an open privacy decision (`docs/risks-and-open-questions.md`, "Feedback and non-content operational trace retention").
  - There is no idempotency key: a client retry after an unknown outcome counts again. The alternative would add a per-submission identifier, which this privacy-minimal endpoint deliberately does not collect.
  - `/feedback` gets the same pilot bearer-token gate as `/ask`, with its own per-client rate window; the `development` profile stays open. The existing token-path rule is widened to allow the pilot token on `/feedback` as well as `/ask`, under the same https/loopback condition; the client transport change itself belongs to `answer_feedback_ui`.
  - The chat control and Spanish copy belong to the separate `answer_feedback_ui` feature.

## Goal

Give the future chat UI a stable, privacy-minimal way to report whether an answer was useful, and give the owner an aggregate signal without collecting what the person asked, who they are, or which land the answer concerned.

## Non-goals

- Client UI, shared DTOs, or sending a rating from Android/Desktop (`answer_feedback_ui`).
- Changing the test-only mock answer service (`shared/src/jvmTest/.../mock`); it continues to serve only its existing examples.
- Free-text comments, answer or question text, land context, answer ids, citations, per-person tracking, or analytics.
- A durable feedback database, export, admin command, dashboard, alert, or retention job; the later dashboard reads the metric.
- Changing `/ask`, `/health`, `/ready`, `/metrics`, retention, tracing, or the pending pilot privacy review record.
- Approving the pending privacy review, enabling real-user pilot traffic, or claiming feedback is covered by the review.

## Job story

When a person has just read an answer, I want to accept only whether it was useful, so the owner can see an honest aggregate signal without collecting the question, the answer, a land, or an identifier.

## Acceptance Scenarios

### 1. A fixed rating is accepted

Given the service is running and no campaign or corpus is configured · When `POST /feedback` carries `{"rating":"useful"}` or `{"rating":"not_useful"}` · Then it returns `204` with an empty response body, and the request does not start answer generation or require readiness.

### 2. Only the fixed rating crosses the boundary

Given any JSON body · When it omits `rating`, uses another value, adds any other key (for example comment, question, answer, land, id, or device), or is malformed · Then it returns `422` (or `400` for malformed JSON) with a generic detail and no submitted value echoed, and no feedback is counted. Given a body over the service bound · Then it returns `413`.

### 3. Local is open and pilot is gated

Given the `development` profile · When `/feedback` is sent without credentials · Then it returns `204`. Given the `pilot` profile with fake clients · When no, malformed, or unknown bearer token is sent · Then the existing detail-free `401` is returned; with a valid client token it returns `204`; over that client's feedback allowance it returns `429`. Feedback uses its own per-path window and never consumes the client's `/ask` allowance.

### 4. Counts only, no content or identifiers

Given accepted feedback of both ratings · When `GET /metrics` is read · Then `manijero_feedback_total{rating}` increases once per accepted request and `http_requests_total{route="/feedback",code="204"}` counts the request; no question, answer, land value, client id, token, or rejected extra value appears in metrics, logs, or the response. The counter is per process and resets on restart.

### 5. No persistence or answer linkage

Given a configured retention store and answer trace · When feedback is accepted · Then no retained row, trace file, answer id, or feedback record is created, and the endpoint reads no corpus or campaign. Feedback cannot change an `/ask` response.

### 6. Contract and examples are published

Given the repository · When `python3 contracts/validate_examples.py` runs · Then both feedback examples validate and carry only `rating`; `GET /openapi.json` documents `POST /feedback` as `submitAnswerFeedback` with `204`, `400`, `401`, `413`, `422`, and `429` responses.

## Technical approach

- Add `FeedbackRequest` to `contracts/openapi.yaml`: an object with `additionalProperties: false`, required `rating`, and rating enum `useful`/`not_useful`. Document `204` as accepted with no body; keep the existing detail-free error shapes and pilot statuses.
- Add `contracts/examples/feedback-useful.json` and `feedback-not-useful.json`, and extend `contracts/validate_examples.py` to assert exactly one `rating` key with an allowed value.
- Create `backend/app/feedback_api.py` with a strict Pydantic model (`extra="forbid"`, `strict=True`) and a router. The handler calls a `health_metrics` recording hook and returns `Response(status_code=204)`. It has no corpus, campaign, retention, trace, or generation dependency.
- Register the router in `create_app` in `backend/app/main.py`; do not change the existing `/ask` router.
- Add `/feedback` to `PilotGuardMiddleware.GATED_PATHS`; reuse the existing body bound, constant-time token check, and per-path limiter key, so pilot feedback is authenticated and has a separate window.
- Update the token-path rule in `docs/constraints/hosting-and-pilot.md`: the same pilot token may be sent on `POST /feedback` and `POST /ask` only, under the existing https/loopback condition; `/health` and `/ready` remain excluded. The client transport change belongs to `answer_feedback_ui`.
- Add `feedback_total` as a counter with a fixed `rating` label (`useful`, `not_useful`) in `backend/app/health_metrics.py`; add `rating` to the label allowlist and `/feedback` to the route allowlist, and initialize both rating series to zero. Keep the hook `_safe` and request-bound.
- Do not add a feedback-specific operational log record. The existing pilot request line continues to record only method, path, status, duration, and gate.

## Expected file changes

- `contracts/openapi.yaml` — modify; `/feedback` path, `FeedbackRequest`, `204` and documented errors.
- `contracts/examples/feedback-useful.json`, `contracts/examples/feedback-not-useful.json` — create; valid request examples.
- `contracts/validate_examples.py` — modify; validate the two feedback examples and their restricted shape.
- `backend/app/feedback_api.py` — create; strict request model, `POST /feedback`, metric hook, `204`.
- `backend/app/main.py` — modify; include the feedback router.
- `backend/app/pilot_guard.py` — modify; gate `/feedback` in the pilot profile with a path-specific limiter window.
- `backend/app/health_metrics.py` — modify; `feedback_total{rating}`, `rating` label, `/feedback` route.
- `backend/tests/test_feedback_endpoint.py` — create; scenarios 1–6.
- `backend/tests/test_health_metrics.py` — modify; independent label/route/family allowlists include feedback.
- `ARCHITECTURE.md`, `docs/constraints/hosting-and-pilot.md`, `docs/pilot-privacy.md`, `backend/README.md`, `docs/progress/known-limitations.md`, `docs/risks-and-open-questions.md` — see below.

## Visual design impact

UI involved: no. The shared chat control, Spanish labels, and accessibility behavior are planned by `answer_feedback_ui`; this feature changes no screen and needs no `DESIGN.md` change.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — add `POST /feedback` to the backend endpoint list and one line in the privacy boundary: fixed rating count only, no storage or answer linkage.
- `docs/constraints/hosting-and-pilot.md`: update — one MUST for the fixed-rating feedback payload (no question/answer/land/client/device values or free text, pilot-authenticated, not persisted), and widen the existing token-path MUST from `/ask` to `/ask` plus `/feedback` only.
- `AGENTS.md`: not needed — no workflow, startup, or repo-wide operating rule changes.
- `docs/pilot-privacy.md`: update — add one data-flow row for the rating and state that the pending review must cover it before real-user use; do not edit the review record.
- `backend/README.md`: update — an "Answer feedback" section of at most 30 lines: request shape, `204`, profile gate, metric, and limits.
- `docs/progress/known-limitations.md`: update — one line: anonymous unlinked rating, per-process counts, no durable feedback store or export, no idempotency (a retry counts again), and the pending review does not yet name feedback.
- `docs/risks-and-open-questions.md`: update — the existing "Feedback and non-content operational trace retention" line notes the fixed-rating implementation and that durable feedback retention remains undecided.
- `docs/owner-guide.md`, `docs/domain-model.md`, `docs/constraints/client-chat.md`: not needed — no owner command, domain record, or client behavior in this feature.

## Focused verification (required)

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_feedback_endpoint.py tests/test_health_metrics.py -q
```
<!-- verify:end -->

## Appendix

See [`feedback_endpoint.appendix.md`](feedback_endpoint.appendix.md) for research, plan, evidence, and the validator checklist.
