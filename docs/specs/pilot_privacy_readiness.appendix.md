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

Implementer self-verification, 2026-10-31 (macOS host, JDK 21 Zulu, backend `.venv` Python 3.12). This is
local evidence only: **no qualified privacy/legal review exists**, the committed record
`backend/config/pilot_privacy_review.json` is `pending`, and both gates are closed. Nothing here is a
compliance or approval claim.

Implemented: optional `retain_for_improvement` (default false) in `contracts/openapi.yaml`, the new example
`contracts/examples/ask-request-retention-opt-in.json`, the Pydantic `AskRequest`, and the shared DTO;
`backend/app/redaction.py`, `backend/app/retention.py` (owner-only SQLite, purge-before-write, `expires_on` =
creation + 29 days, export/delete-all/status), retention as a post-answer step in `/ask`;
`backend/app/privacy_review.py` (pilot gate, separate Gemini gate, `minimal_provider_payload`), preflight
blockers and `pilot_ops.py privacy-gate` / `retention-*` commands, purge timer templates; shared
`ChatHomeState.retainNextQuestion` + `RetentionChoiceChanged`, per-send reset, device-side exclusion
(`privacy/QuestionRetention.kt`), the composer checkbox row and the privacy-notice section; data-flow inventory
in `docs/pilot-privacy.md`.

Verification (exports: `JAVA_HOME=…/zulu21.50.19-ca-jdk21.0.11-macosx_aarch64/Contents/Home`):

| Command | Exit | Result |
|---|---|---|
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature pilot_privacy_readiness` | 0 | `:shared:jvmTest` green; backend `938 passed` |
| `MANIJERO_PYTHON=backend/.venv/bin/python CI=true ./scripts/init.sh --fast` | 0 | `Validated 3 request and 3 response examples`; `938 passed`; `All 9 offline checks passed.`; `Fast tier passed.` |
| `MANIJERO_PYTHON=backend/.venv/bin/python CI=true ./scripts/init.sh --verify` | 0 | fast tier plus `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` — `BUILD SUCCESSFUL` |
| `./gradlew :shared:verifyScreenshots` (after recording) | 0 | Desktop 38 and Android 34 captures match |
| `backend/.venv/bin/python backend/scripts/pilot_ops.py privacy-gate --as-of 2026-10-31` | 1 | `pilot_privacy_review: blocked`, `gemini_requests: disabled`; blockers `privacy_review_pending`, `_undated`, `_qualification_missing`, `_scope_incomplete`, `_evidence_missing` |

`:shared:jvmTest` totals 331 tests, 0 failures, including `QuestionRetentionTest` (7: default off and no
retention key on the wire, ticking never sends, one-question scope and reset on ask/retry/land choice,
saved name/zone/municipality/notes drop the opt-in without changing wording, no extra land data encoded,
30-day constant) and `ChatHomeInteractionTest.retentionChoiceIsUncheckedSeparateAndNeverSubmits` (checkbox
role, off by default, toggles only `RetentionChoiceChanged`, 30-day copy present).

Backend `tests/test_privacy_retention.py` (50 tests): no write or log text without opt-in (absent and `false`);
opt-in keeps only the five minimal columns with the question/answer redacted and no land id, municipality,
name, phone, e-mail, or parcel number; non-boolean opt-in is `422`; no store = no retention; clarification
not retained, abstention retained without land values; storage and redaction failures leave the answer
byte-identical and log only `retention_skipped`/`store_failed`; purge at creation + 28 days keeps, at + 29
deletes; every write purges first; status reports overdue and export skips expired, refuses existing or
in-repo destinations and writes `0600`; corrupt store fails; owner-only and outside-repo location enforced
(`0600` file); operator CLI exit codes (`retention-status` 1 when overdue, purge failure 1, delete-all needs
`--confirm`); 11 redaction examples; pending committed record blocks; complete synthetic record passes; 10
incomplete-record variants block; Gemini stays closed with the committed record, requires exact model and
minimal data, stays extractive even when its gate passes, and `/ask` with `MANIJERO_GENERATION_PROVIDER=gemini`
attempts no socket connection; minimal provider payload carries only question and passage text; generated
OpenAPI and the contract both declare the optional boolean. `test_pilot_operations.py` now expects the
preflight to fail with `privacy_review_pending` and to pass only with the labelled synthetic fixture
`tests/fixtures/privacy/synthetic_approved_review.json`.

Synthetic redaction example (land context `opaque-land-7f3a`, `Martos`):

```text
in:  Me llamo Juan Pérez y mi finca Los Olivos está en Martos, polígono 12 parcela 345. Mi teléfono es 600 123 456 y mi correo juan.perez@example.com. ¿Cuándo se presenta la solicitud anual de ejemplo?
out: Me llamo [nombre] y mi finca [nombre del terreno] está en [municipio], polígono [número] parcela [número]. Mi teléfono es [teléfono] y mi correo [correo]. ¿Cuándo se presenta la solicitud anual de ejemplo?
```

Screenshots: `verifyScreenshots` first failed on exactly 12 captures that contain the changed surfaces
(Desktop `chat_home_idle_light`, `chat_home_idle_light_phone`, `chat_answered_source_dark`,
`chat_abstention_dark`, `chat_clarification_light`, `privacy_light`, `privacy_dark`,
`app_shell_assistant_compact_light`; Android `chat_home_idle_light`, `privacy_light`, `privacy_dark`,
`app_shell_assistant_compact_light`). The compare images showed only the inserted checkbox row/detail and the
new privacy section; those classes were re-recorded and the new PNGs were inspected by the implementer (an
agent, not a human reviewer). `git status` shows exactly those 12 PNGs changed.

Limits: host-rendered pixels only, no device, screen-reader, or enlarged-text manual check of the new copy;
the retention store, purge timer, and preflight blocker are local tests only, never run on a host or under
systemd; redaction is pattern-based and synthetic-only; the pilot and Gemini gates are closed because no
qualified review exists, so the validator checklist item "qualified review complete before the pilot is
marked ready" is satisfied only in the sense that the pilot cannot be marked ready.

Independent validator run (2026-10-31, fresh validator subagent, read-only): `git diff --check` exit 0;
`./scripts/init.sh --feature pilot_privacy_readiness` exit 0 (backend 938 passed); `CI=true ./scripts/init.sh --fast`
exit 0 (3 request / 3 response examples, 938 passed, all 9 offline checks passed); `CI=true ./scripts/init.sh --verify`
exit 0 (Android host tests 303, 0 failures; Android and Desktop builds successful); `./gradlew :shared:jvmTest --rerun`
exit 0 (331 tests, 0 failures); `./gradlew :shared:verifyScreenshots` exit 0; `pytest tests/test_privacy_retention.py
tests/test_pilot_operations.py` 84 passed; `pilot_ops.py privacy-gate --as-of 2026-10-31` exit 1 (expected) with
`privacy_review_pending`, `_undated`, `_qualification_missing`, `_scope_incomplete`, `_evidence_missing`. Verdict: accept.

## Validator checklist

- [ ] No question/answer text is retained by default.
- [ ] No land context, opaque land IDs, or stable device/user identifier is retained with Q/A.
- [ ] Redacted Q/A expires no later than 30 days.
- [ ] Disabling opt-in prevents future retention and copy explains limits.
- [ ] Qualified privacy/legal review is complete before the pilot is marked ready.
- [ ] No hosted LLM or unreviewed provider was introduced.
