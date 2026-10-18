# Validation: `backend_answer_evaluation`

## Verdict

**Accept** — 2026-10-18.

## Independent checks

- Confirmed the Draft 2020-12 schema with `Draft202012Validator.check_schema`; the canonical six-case artifact validates, and six malformed mutations are rejected.
- Ran `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature backend_answer_evaluation`: all 14 focused tests passed and the canonical evaluator completed.
- Ran the canonical evaluator twice with identical campaign (`2026`), as-of (`2026-10-17`), corpus, case, and retrieval (`k=5`) inputs; reports were byte-identical.
- Confirmed supplied catalog and passage inputs drive citation matching; regression coverage uses non-default source and passage identifiers.
- Confirmed report mismatches are visible and report-only. The six-case sample is narrow and does not demonstrate legal correctness or general answer quality.
- `git diff --check` passed. The unrelated fast-tier fixture failures are documented in the feature appendix and do not block this focused acceptance.

A Starlette/httpx TestClient deprecation warning was emitted; it did not affect verification. No blocking security or scope issues were found.
