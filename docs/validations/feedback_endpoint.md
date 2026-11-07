# Validation: feedback_endpoint

Verdict: accept (independent validator, 2026-11-06; backend-only feature, no owner walkthrough in the
spec).

Spec: [../specs/feedback_endpoint.md](../specs/feedback_endpoint.md) · Evidence:
[appendix](../specs/feedback_endpoint.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature feedback_endpoint`: 48 passed (published focused block accurate and
  unchanged).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 1895 passed, 4 skipped; harness
  20 passed; contract examples validated).
- `python3 contracts/validate_examples.py`: `Validated 3 request, 3 response, and 2 feedback examples`.
- `contracts/openapi.yaml` parsed independently: `/feedback` is `submitAnswerFeedback` with `204`,
  `400`, `401`, `413`, `422`, `429`; `FeedbackRequest` is `additionalProperties: false`, requires
  only `rating`, enum `useful`/`not_useful`; `/ask` unchanged.
- `--verify` not rerun: the diff touches only `backend/`, `contracts/`, docs, and the feature index;
  no `shared/`, apps, Gradle, or packaging.

## Review

- Scenarios 1–6 map to `backend/tests/test_feedback_endpoint.py` (23 collected tests): both ratings return
  `204` with `b""`; works with `/ready` 503 and no campaign/corpus; empty, unknown, non-string,
  comment/question/answer/land/answer-id/device/client/text keys, malformed JSON, and oversized
  bodies are `422`/`400`/`413` with the generic detail and zero counts.
- Pilot: `/feedback` is in `PilotGuardMiddleware.GATED_PATHS`; the per-path window key
  (`path:client_id`) keeps feedback off the client's `/ask` allowance, proven by the
  interleaved 204/429 test; `development` stays open; `/health` and `/ready` stay token-free.
- Privacy: the route has no corpus, campaign, retention, trace, or generation dependency; a real
  `RetentionStore` plus an `on` answer trace stayed empty; `/metrics`/logs carry only
  `feedback_total{rating}`, `http_requests_total{route="/feedback",code="204"}`, and the metadata
  request line; both rating series start at `0`; the hook is `_safe` and request-bound.
- Scope: no client UI/DTO, mock-service, durable store, export, log event, review-record, or
  dependency change; `/ask` is byte-identical before and after a feedback request.
- Docs: ARCHITECTURE endpoint list and privacy boundary, both hosting-and-pilot MUSTs (widened token
  path, fixed-rating payload), pilot-privacy data-flow row plus review scope, `backend/README.md`
  "Answer feedback" (19 lines), `known-limitations` bullet, `PROGRESS.md` digest, and the
  risks-and-open-questions retention line all match the implemented behavior.
- Security checklist: no secrets or real tokens in the diff; server-side validation and auth at the
  middleware boundary; nothing user-supplied reaches metrics, logs, storage, or error bodies; no new
  dependency. No blocking findings. Residual: an unauthenticated pilot caller is rejected `401`
  before the limiter (existing `/ask` design, tunnel still fronts it).

## Remaining limits

- Counters are per process, reset on restart; no durable store, export, dashboard, or idempotency
  (a retry counts again), as the spec states.
- No client transport or UI path until `answer_feedback_ui`; evidence is in-process
  `TestClient` plus the implementer's loopback smoke, not a live pilot-profile run (the review is
  still `pending`).
- Low: `backend/README.md` "Health metrics → Families" still enumerates families without
  `feedback_total{rating}`; add it so that catalog matches the exporter.
- Low: `PROGRESS.md` still says "The 37 `not_started` features"; the board is 82 accepted, 1
  on_hold, 36 not_started, 1 passing (120 total). Reconcile the count when acceptance is persisted
  (`github-flow` integrate recounts as well).
