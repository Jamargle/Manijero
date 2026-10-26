# `pilot_privacy_readiness` Appendix

## Repository research

- Current shared disclosure explains land context; it does not cover hosted infrastructure or stored Q/A.
- `platform_ask_wiring` sends the question and minimal land context to the service. Backend currently has no hosted LLM and no approved Q/A retention store.
- The current risk register requires retention, provider processing, and operational ownership decisions before real users.

## Implementation plan and tasks

1. Map question, answer, context, transport/provider, access log, error log, and retention flows.
2. Have a qualified reviewer assess applicable obligations, the notice, provider terms, redaction limits, consent, retention, deletion, and incident process. Do not proceed to pilot without dated outcome.
3. Implement default-off per-question opt-in and separate the retention path from answer generation and operational logs.
4. Redact question/answer content, exclude all land context/IDs and stable user/device identifiers, enforce deletion by 30 days, and test deletion failures/alerts.
5. Update plain-Spanish disclosure and provide an owner-controlled access/deletion procedure consistent with the review.

## Verification plan

- Shared tests verify opt-in defaults off and explicit selection behavior.
- Backend tests verify no write without opt-in, redaction, excluded fields, 30-day cleanup, and graceful failure.
- Manual review checks the Spanish notice at normal/enlarged text and the qualified review record.

## Evidence to capture

- Data-flow diagram, consent state, synthetic redaction examples, retention deletion results, provider terms and dated reviewer sign-off/conditions.

## Feature evidence

## Validator checklist

- [ ] No question/answer text is retained by default.
- [ ] No land context, opaque land IDs, or stable device/user identifier is retained with Q/A.
- [ ] Redacted Q/A expires no later than 30 days.
- [ ] Disabling opt-in prevents future retention and copy explains limits.
- [ ] Qualified privacy/legal review is complete before the pilot is marked ready.
- [ ] No hosted LLM or unreviewed provider was introduced.
