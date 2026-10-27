# Validation: `official_source_monitoring`

## Verdict

**Accept** — 2026-10-27.

## Independent checks

- Reviewed the feature spec, implementation diff, feature index, evidence appendix,
  operator documentation, architecture boundary, and scope.
- Ran `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_monitoring`:
  **625 backend tests passed**, including seven source-monitor tests. One existing
  Starlette/httpx deprecation warning was emitted.
- Ran `./scripts/init.sh --fast`: **all nine offline checks passed**, including
  shared JVM tests, contract examples, backend tests, source-catalog validation,
  and the five synthetic evaluators. Evaluator evidence remains report-only.
- Confirmed monitor input host validation, bounded response reads/timeouts,
  same-host HTTPS redirect restriction, conditional request support, last-good
  snapshot retention on failure, and independent state-file writes. The feature
  does not alter canonical knowledge or answer behavior.

## Limits and security assessment

No blocking feature-scoped security or privacy issue found. The monitor is limited
by design to configured official hosts and does not follow feed document links.
The BOE JSON is validated as JSON, not against an endpoint-specific schema; hashes
cover whole feed responses, not individual documents. No live BOE/BOJA upstream
smoke test or recurring scheduler is included. External owner-managed dispatch
must not be treated as proof of corpus currency or legal coverage. See the
[feature evidence appendix](../specs/official_source_monitoring.appendix.md) and
[operator instructions](../../backend/README.md) for details.
