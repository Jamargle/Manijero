# Validation: source_catalog_validation

## Verdict

**Accept** — independently validated against `docs/specs/source_catalog_validation.md`
on 2026-10-12.

## Evidence

- `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12`
  exited 0: `valid source catalog: ... (schema source-catalog-v1, 0 source(s) checked as of 2026-10-12)`.
- Valid fixtures accepted: `valid_official_source.json` (3 sources: BOE, Junta de
  Andalucía, FEGA) and `valid_empty_catalog.json` (0 sources).
- Every one of the 23 fixtures was exercised by the CLI: 2 exit 0, 20 rejections
  exit 1 with a located JSON-path diagnostic, and `malformed_json.json` exits 2.
- Re-derived diagnostics independently, e.g.
  `$.sources[0].content_sha256: required key is missing`,
  `$.sources[1].id: duplicate id; already used by $.sources[0]`,
  `$.sources[0].original_url: host is not on the approved official-domain allowlist`,
  `$.sources[0].valid_until: is before the validation date; the document is expired and ineligible`.
- `--as-of` expiry boundary confirmed on `invalid_expired.json` (valid_until
  `2026-06-15`): exit 0 on 2026-06-15, exit 1 on 2026-06-16 and 2026-10-12.
- Focused tests: `cd backend && python -m pytest tests/test_source_catalog.py` → 43 passed.
  Full regression: `python -m pytest` → 45 passed (43 new + 2 health tests).
- Local-only behavior confirmed by hard-blocking `socket.socket`,
  `create_connection`, and `getaddrinfo` before import; validation still succeeded.
- No-content-leak check across every fixture found no title, reviewer, or URL value
  echoed into diagnostics; the synthetic embedded credential is never printed.
- `git diff --check` clean. Scope confirmed: only `GET /health` remains on the service;
  no retrieval, ingestion, `/ask`, client UI, automated discovery, or unrelated files added.

## Scope and security review

The change adds a read-only, standard-library, offline catalog-policy gate plus its
schema, canonical empty catalog, reviewer README, CLI, tests, and fixtures. No
network client, credentials, secrets, writes, auth surface, or personal data were
introduced. Diagnostics contain only JSON paths and rule text. No blocking security
findings were identified.

## Residual uncertainty

The validator proves catalog-policy conformance, not that any remote document is
authentic, current, or legally applicable. Android/Gradle checks do not apply to this
knowledge/backend feature and were not run.
