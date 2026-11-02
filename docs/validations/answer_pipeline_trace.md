# Validation: answer_pipeline_trace

## Verdict

**Accept** — independently validated against `docs/specs/answer_pipeline_trace.md` on
2026-11-02. No blocking findings. Per owner decision 4 (2026-11-02) this accept is final; no owner
walkthrough is required. Evidence: the "Feature evidence" section of
[`answer_pipeline_trace.appendix.md`](../specs/answer_pipeline_trace.appendix.md).

## Independently rerun checks

| Check | Result |
|---|---|
| Focused block (`./scripts/init.sh --feature answer_pipeline_trace`, pytest part) | 754 passed, 1 warning; includes `tests/test_answer_trace.py` |
| `CI=true ./scripts/init.sh --fast` | all 9 offline checks passed; backend tests 1766 passed, 4 skipped |
| `git check-ignore` on a trace path | not rerun by the validator (permission denied); `.gitignore` `build` rules cover `build/answer-traces/`; implementer run succeeded |

`--verify` was not run: the diff touches only `backend/`, docs, and `feature_list.json`.

## What is accepted

An off-by-default per-question trace (`MANIJERO_ANSWER_TRACE=on`, also settable in
`~/manijero/local/settings.env`) of retrieval, ranking, drafting, and verification, written as one
`0600` JSON file per question to the git-ignored `build/answer-traces/` (`0700`, atomic write).
Question, answer, and draft text appear only when the validated profile is exactly `development`;
every other profile is checked against a metadata-only key allowlist. No trace in any profile holds
land values, client id, token, IP, the retention flag, issue detail, or passage excerpts. Files older
than 7 days are purged at startup (even when tracing is off) and before each write. Responses are
byte-identical with tracing on and off, and trace failures only log fixed codes.

## Limits

- Purge runs only while the service runs; a stopped service leaves older files until next start.
- An unset `MANIJERO_DEPLOYMENT_PROFILE` counts as `development`, so a hosted service started
  outside `serve_pilot.py` (forbidden by the hosting constraint) with tracing on would record text.
  `environment_profiles` must replace this with a positive local marker.
  Resolved 2026-11-02 in the batch 4 integration (owner decision): text is recorded only when the
  profile is explicitly `development`, which the local service start now states; the container image
  states no profile, so its trace records no text. Covered by `backend/tests/test_answer_trace.py`.
- No hosted trace has been observed; no endpoint exposes traces (`rag_inspector_view` reads files).

## Notes (non-blocking)

- Style: `ask_api.py` imports `answer_trace` two ways; one call wraps needlessly.
