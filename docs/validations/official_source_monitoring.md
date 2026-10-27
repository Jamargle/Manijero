# Validation: `official_source_monitoring`

## Verdict

**Accept** — 2026-10-27, after addressing independent validation findings.

## Independent checks

- The independent validator reviewed the spec, implementation diff, tests, feature status, evidence appendix, operator documentation, and downstream review-flow documentation.
- Ran `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_monitoring`: **9 focused source-monitor tests passed**.
- Ran `GRADLE_USER_HOME=/private/tmp/manijero-gradle-home ./scripts/init.sh --fast`: **all nine offline checks passed**, including the JVM suite, 627 backend tests, contract examples, source-catalog validation, and offline evaluators. Evaluator metrics remain synthetic/report-only.
- `git diff --check` passed. No live BOE/BOJA upstream request was made.
- An earlier independent review found that HTTP `206` could be treated as success and malformed nested state could escape the documented CLI error path. The implementation now rejects statuses other than `200`/handled `304`, validates persisted source records before requesting or writing, and includes regression tests for both cases. The independent validator reran the focused suite and accepted the repairs.

## Security assessment and limits

No blocking feature-scoped security or privacy issues remain. Configured endpoints use the exact approved HTTPS host policy; requests have a timeout and response cap; redirects cannot change host or scheme; feed item links are not fetched; failed scans retain the last-good snapshot.

The BOE JSON is syntax-validated, not checked against an endpoint-specific record schema. Hashes cover whole response bytes, not individual documents. There was no live upstream smoke test and no recurring scheduler. These limitations mean successful polling does not establish source authenticity, legal currency, completeness, or answer quality. See the [feature evidence appendix](../specs/official_source_monitoring.appendix.md) and [operator instructions](../../backend/README.md).
