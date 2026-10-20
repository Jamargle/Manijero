# Validation — `backend_citation_hardening`

**Verdict: accept**

The implementation satisfies the feature contract. Draft markers are verified against original retrieval ranks before selected claims are mapped to dense response-local citations; source order is derived from the same ranks. Regression coverage exercises sparse rank 2, sparse ranks 2 and 4, repeated markers, unchanged claim prose, payload mapping, and preserved fail-closed verification. Citation guidance and durable constraints are aligned. No API or client behavior changed.

## Verification

- `MANIJERO_PYTHON=/private/var/folders/78/v5c0wj2x34q13w54vkc_z3y80000gp/T/manijero-citation-venv/bin/python ./scripts/init.sh --feature backend_citation_hardening` — passed, 102 tests.
- `MANIJERO_PYTHON=/private/var/folders/78/v5c0wj2x34q13w54vkc_z3y80000gp/T/manijero-citation-venv/bin/python ./scripts/init.sh --fast` — passed: shared JVM tests, contract examples, 618 backend tests, and all nine offline checks. One Starlette `httpx`/`TestClient` deprecation warning.
- `git diff --check` — passed.

Synthetic evaluator evidence remains report-only and is not legal-coverage evidence. No acceptance-blocking findings.
