# Feature Spec: `pilot_privacy_readiness`

## Source metadata

- **Feature:** `pilot_privacy_readiness` — Prepare pilot privacy, retention, and review gates (`privacy`).
- **Status at planning:** `not_started`; depends on accepted `land_data_disclosure`, `platform_ask_wiring`, `hosted_pilot_operations`, and `hosting_provider_review`.
- **Source behavior:** Before a private pilot, users understand the data flow and can opt in to short-lived, redacted question/answer retention for product improvement.
- **Feature-list verification:** Data-flow and retention behavior match the plain-Spanish notice; default is no retention; explicit opt-in is required per question; retained text is redacted, excludes land context and stable IDs, and is automatically deleted after 30 days; qualified privacy/legal review is recorded before pilot; Gemini remains disabled unless its separate current-terms/data-flow review gate is approved.
- **Feature-list note:** Gemini integration is in pilot scope but MUST remain disabled until current provider terms and data flows receive qualified privacy/legal review and the gate is explicitly recorded as passed. This feature does not itself certify legal compliance.

## Goal and boundaries

Make the private hosted pilot's data practices explicit, technically enforced, and reviewed by a qualified privacy/legal reviewer before any pilot participant is invited. Product improvement retention is opt-in and limited to redacted question and answer text.

**In scope:** data-flow inventory; plain-Spanish notice; default-off opt-in before each retained question; redaction and exclusion of land context, land IDs, names, notes, and device identifiers; automatic deletion no later than 30 days; access controls; privacy/incident contact and deletion procedure; qualified review of applicable obligations, notices, and current provider terms, including the selected Gemini model and exact data sent to Google. The Gemini gate remains closed by default.

**Non-goals:** claiming regulatory compliance without review, retaining full chat history, logging land context, sending requests to Gemini before the review gate passes, user research, or public release.

## Job story

When I use Manijero in a private pilot, I want to know what leaves my device and choose whether my redacted question and answer may be kept briefly, so I can make an informed choice.

## Acceptance scenarios

### Default no retention

Given the user has not explicitly opted in for a question, when that question is answered, then no question or answer text is written to the product-improvement store or operational logs.

### Explicit per-question opt-in

Given the user sees a plain-Spanish explanation for the current question, when they explicitly opt in, then only redacted question/answer text may be retained; the land context, land IDs, names, notes, and stable device/user identifiers are excluded.

### Expiration and withdrawal

Given a retained record reaches 30 days, when the cleanup runs, then it is deleted automatically. Turning retention off prevents later retention; the UI states the expiry behavior and any deletion path confirmed by the qualified review.

### Privacy review gate

Given no dated qualified review is recorded, when the owner prepares the pilot, then the feature reports a blocker and does not claim the privacy design is production-ready or approved for real users.

### Gemini review gate

Given Gemini is configured but no dated qualified privacy/legal review of current model terms and data flows is recorded, when the API handles a question, then it makes no Gemini request and uses the existing safe extractive path. After an approved gate, provider data sent is limited to the question and approved retrieved passages required to draft an answer; land names, notes, stable identifiers, and retained Q/A are excluded. Every output still passes the existing verifier.

## Technical approach

Map each collection and processing step across Android/Desktop, API host, managed tunnel, and any provider, including Google only if the gated Gemini provider is approved. Add an explicit default-off retention choice to the client/API contract. The retention path must receive only the question and final answer after a conservative redaction step; it must not receive land context or stable user/device identifiers. If redaction cannot be applied or storage is unavailable, answer service behavior remains unaffected and the text is not retained. Store retained records in owner-controlled storage with strict access and a scheduled 30-day deletion mechanism. The qualified reviewer must approve the notice, opt-in, redaction limitations, retention/deletion behavior, and host/tunnel/Gemini provider terms before the pilot gate can pass; preserve their decision/evidence without unnecessary personal data.

## Expected file changes

- `contracts/openapi.yaml`, examples, shared DTO/client, backend request/service boundary, retention storage and deletion job.
- Shared privacy UI/copy and tests; backend privacy/retention tests.
- `docs/risks-and-open-questions.md`, `docs/domain-model.md`, `CONSTRAINTS.md`, `backend/README.md`, and privacy notice.

## Visual design impact

Add a clear opt-in control and data-flow/retention explanation in shared UI. Follow `DESIGN.md`; opt-in must be unselected by default, accessible, and separate from submitting a question. No generated concept is needed.

## Durable documentation impact

- `ARCHITECTURE.md`: update data flow and retention boundary.
- `CONSTRAINTS.md`: add default-off retention, no land context/IDs, 30-day deletion, and qualified-review gate.
- `AGENTS.md`: not needed.
- `docs/risks-and-open-questions.md` and backend/privacy docs: record reviewer outcome and limits.

## Focused verification

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`pilot_privacy_readiness.appendix.md`](pilot_privacy_readiness.appendix.md).
