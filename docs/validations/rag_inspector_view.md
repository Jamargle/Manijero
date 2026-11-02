# Validation: `rag_inspector_view`

Verdict: **accept** (independent validator, 2026-11-02; no owner walkthrough per spec decision 3).
Spec: [rag_inspector_view.md](../specs/rag_inspector_view.md). Evidence: appendix "Feature evidence".

## Checks rerun
- `./scripts/init.sh --feature rag_inspector_view`: passed (backend inspection/trace/ask/retention tests, shared jvmTest groups, android/desktop compile incl. release, desktop and Android screenshot verification).
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend 1854 passed, harness 13 passed).
- `--verify` not rerun: the focused tier already ran the shared/host compile, jvmTest groups and both screenshot verifications on unchanged inputs.
- `git diff --stat -- '*.png'`: no existing baseline modified; only seven new PNGs.

## Findings
- Backend gate: `inspection_allowed` delegates to `text_allowed` (profile in `{development}` and explicitly stated, exact match); tests cover unset, empty, pilot, ` development`, `Development`. Key omitted unless set (`response_model_exclude_unset`); attached after trace and retention; builder failure omits key and logs a fixed code.
- Privacy: inspection is built from an allowlist (`INSPECTION_KEYS`), carries codes, scores, public corpus text; no question/answer/land/token/`GroundingIssue.detail`. Closed models and OpenAPI schema (`additionalProperties: false`, five required keys unchanged).
- Client gate: fixed-URL constructor delegates with `false`; hosts pass `acceptInspection = true` only in the tools branch (guard tests extended); kept only for loopback URLs; decode failures yield null without failing the answer.

## Remaining limits
- A real device on a LAN address never shows the inspector; no GUI run.
- `client_environment_builds` is not accepted; "local build" is defined by test tools plus loopback host.
