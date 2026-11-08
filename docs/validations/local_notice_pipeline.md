# Validation — `local_notice_pipeline`

## Verdict

**Accept** — 2026-11-08. Independent validation of the uncommitted implementation against
`docs/specs/local_notice_pipeline.md`. Owner decision: validator accept is final, no owner walkthrough.
Recommended state update: orchestrator may set `status` to `accepted`.

## Checks rerun

- `./scripts/init.sh --feature local_notice_pipeline`: passed (focused pytest block plus screen-only CLI over the invented fixtures: 3 screened, 0 refused).
- `CI=true ./scripts/init.sh --fast`: passed (backend 2601 passed, 7 skipped; harness 20 passed; contract examples, catalog, offline evaluators ok).
- `--verify` not rerun: the diff touches no `shared/`, Android, Desktop, Gradle, or packaging files.

## Review notes

- Data-only handling: pinned instruction as system message, notice only inside a JSON payload; strict per-notice fail-closed output validation; no `logging`; errors carry fixed codes only.
- Personal-data refusal runs before any model call and reports codes only (no text, value, or hash).
- Isolation: only `notice_pipeline.py`, its CLI, tests, and the backend README reference the module or `notice-review.json`; no `/ask`, retrieval, release, or evaluation module imports it.
- No network beyond the loopback Ollama transport; tests use a fake transport.
- `/ask` unchanged: `_has_personal_data` delegates to a refactored kinds function (same checks); `OllamaTransport.response_format` defaults to `DRAFT_JSON_SCHEMA`. Existing guardrail and local-generation tests and the full backend suite pass.
- Durable docs (ARCHITECTURE, constraints, README, limitations, risks, PROGRESS) updated as the spec requires.

## Limits that remain

- The screen is a lexical Spanish heuristic tested only on invented notices; no extraction quality measured; output is unreviewed; no live Ollama run (not required).
- No extra manual adversarial CLI run was done (sandbox blocked ad-hoc temp files); the test suite is the evidence for no-echo and no-retention.
