# `official_source_monitoring` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

## Implementation plan

1. Inspect the current owning modules, schemas, and focused command before changing code.
2. Implement the capability behind a narrow interface with explicit configuration and fail-closed behavior.
3. Add representative and adversarial fixtures, including malformed, stale, duplicate, unavailable, and ambiguous cases as applicable.
4. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

Implemented the manual feed-polling boundary in `backend/app/source_monitor.py`
and its CLI `backend/scripts/scan_official_sources.py`. Only explicitly
configured HTTPS endpoints on the existing exact approved host allowlist are
accepted. RSS/Atom XML and JSON response bodies are bounded and validated;
conditional ETag/Last-Modified requests, response SHA-256, retrieval/last
success timestamps, HTTP result, and failure state are stored in a separate
local state file. Cross-host redirects and linked-document fetching are
prevented. This does not parse legal meaning, approve candidates, write the
canonical catalog/passages, or provide an in-process scheduler. Recurring
dispatch is available to an external owner-managed scheduler; a missing or
delayed dispatch therefore remains an operational limitation. The BOE JSON
response is validated as JSON, not against a documented endpoint-specific
record schema; monitoring hashes the endpoint response as a whole, not each
document. BOE/BOJA live upstream smoke testing was not performed, and successful
polling is not proof of current law or coverage.

Evidence captured 2026-10-27:

- Installed development requirements in local `backend/.venv` from
  `backend/requirements-dev.txt`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_monitoring`:
  passed, 625 backend tests. One existing Starlette/httpx deprecation warning.
- `./scripts/init.sh --fast`: passed all nine offline checks, including all 625
  backend tests, shared JVM tests, contract examples, catalog validation, and
  five synthetic offline evaluators. Evaluator metrics remain report-only and
  do not demonstrate source/legal coverage.
- Focused adversarial tests cover invalid/lookalike hosts, RSS and JSON
  validation, validators and stable hashes, repeated snapshots, malformed
  payloads, failed scans retaining last-good evidence, and 304 without a prior
  snapshot. An initial test assertion expected the absent hash key to be omitted;
  implementation intentionally records it as JSON `null`, and the corrected
  focused/full run passed.
