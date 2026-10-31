# `pilot_privacy_readiness` acceptance

## Verdict

**Accepted** on 2026-10-31 as a technically enforced, *blocked* pilot privacy gate. No qualified privacy/legal review exists; the committed record `backend/config/pilot_privacy_review.json` is `pending`, so the pilot and the separate Gemini gate are closed. This acceptance is not a compliance, approval, or pilot-readiness claim.

## Independent verification

- Reviewed the spec, appendix, and full uncommitted diff (backend redaction/retention/privacy-review modules, `/ask` post-answer retention step, preflight and operator commands, purge timer templates, contract/Pydantic/shared DTO field, shared checkbox, device-side exclusion, privacy copy, docs, 12 screenshot baselines).
- `git diff --check` — exit 0.
- `./scripts/init.sh --feature pilot_privacy_readiness` — exit 0; backend 938 passed.
- `CI=true ./scripts/init.sh --fast` — exit 0; 3 request / 3 response examples validated, 938 passed, all 9 offline checks passed.
- `CI=true ./scripts/init.sh --verify` — exit 0; Android host tests 303, 0 failures; Android and Desktop builds successful.
- `./gradlew :shared:jvmTest --rerun` — exit 0; 331 tests, 0 failures (incl. `QuestionRetentionTest`).
- `./gradlew :shared:verifyScreenshots` — exit 0; re-recorded baselines inspected show only the retention row and the new privacy section.
- `pilot_ops.py privacy-gate --as-of 2026-10-31` — exit 1 with `privacy_review_pending`, `_undated`, `_qualification_missing`, `_scope_incomplete`, `_evidence_missing`; generation provider `extractive`, Gemini requests disabled.
- Security review: no Critical/High findings; retention store owner-only and outside the repository, fixed-code logging only, no provider call, no secrets or real-user data.

## Accepted scope

Optional `retain_for_improvement` (default false) across contract, backend, and shared client; unchecked-by-default per-send checkbox that resets on every send and is dropped on-device when the wording contains a saved land's private label; post-answer redaction and owner-only SQLite retention of five minimal columns, off unless `MANIJERO_RETENTION_DB` is set, purged no later than 30 days after creation, with status/purge/export/delete-all operator commands; failures never affect the answer. Pilot privacy gate and separate Gemini gate evaluate a dated qualified review record; preflight (and so `serve_pilot.py`) blocks while it is pending. Generation stays extractive; `minimal_provider_payload` defines the only data a future gated provider may receive. Data-flow inventory in `docs/pilot-privacy.md`.

## Limits

- No qualified privacy/legal review has been performed; recording one is a human step (`docs/pilot-privacy.md`, "Recording the review"). The pilot MUST NOT be treated as ready for real users until the record passes.
- Open items for the review: participant-facing privacy/incident contact, notice wording (including the existing external-service line), redaction limits, per-person early deletion (records carry no identifier), host journal retention, and current host/tunnel/Gemini terms.
- Redaction is pattern-based and tested on synthetic examples only.
- Retention store, purge timer, and preflight blocker are tested locally only; never run on a host or under systemd.
- Screenshots are host-rendered and agent-inspected; no human screenshot review, device, screen-reader, or enlarged-text manual check of the new copy.

See [`pilot_privacy_readiness.appendix.md`](../archive/specs/pilot_privacy_readiness.appendix.md) for raw evidence.
