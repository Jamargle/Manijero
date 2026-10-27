# `official_source_monitoring` planning appendix

## Repository research

- `PROGRESS.md` Current state identifies official-source scanning and recurring monitoring as unimplemented in the baseline checkout; the named feature worktree now contains a scanner implementation and verification evidence.
- `ARCHITECTURE.md` assigns backend processing to `backend/` and reviewed canonical knowledge to `knowledge/`. `/health` and `/ask` are the service endpoints; a monitoring CLI is an operator boundary and must not join request-time retrieval or generation.
- `knowledge/README.md` says catalog validation does not fetch URLs or prove authenticity/current legal force. Catalog and passages are Git-tracked human-reviewed artifacts. Monitoring must not bypass this approval gate.
- `backend/app/source_catalog.py` supplies the exact approved host allowlist. `backend/app/source_monitor.py` currently reuses that policy for configured monitor URLs and permits same-host HTTPS redirects.
- Existing implementation files are `backend/app/source_monitor.py`, `backend/scripts/scan_official_sources.py`, `backend/tests/test_source_monitor.py`, and operator instructions in `backend/README.md` under “Manual official-source monitoring.”
- The implementation uses Python's standard-library `urllib`/XML/JSON handling and `httpx` is already listed in `backend/requirements.txt`; no new dependency is necessary.
- `scripts/init.sh --backend-tests <target>` accepts pytest targets from `backend/`; the contract's focused command targets the existing `test_source_monitor.py`.
- The official [BOE Open Data API](https://www.boe.es/datosabiertos/api/api.php) publishes an API with documented service routes, including a daily sumario endpoint. The current example configuration points at the API root and only validates the response as JSON; it does not yet validate a BOE-specific response schema or enumerate individual documents.
- Junta's [BOJA RSS instructions](https://www.juntadeandalucia.es/eboja/preguntas-frecuentes/faq4.html) identify `https://www.juntadeandalucia.es/boja/distribucion/s51.xml`. The implementation validates RSS/Atom XML root structure and hashes the exact response bytes. It does not extract/hash individual entries.
- The supplied BOJA/BOE endpoints are examples, not proof of live availability. No live upstream smoke test was captured in the existing evidence.

## Implementation plan and tasks

The worktree already contains the initial implementation. For any follow-up needed to satisfy this contract:

1. Keep `source_monitor.py` as an operator-side component. Do not add automatic polling to backend startup, `/ask`, or retrieval.
2. Keep configured source identity, exact-host checks, response format, state version (`source-monitor-state-v1`), atomic persistence, and failure semantics explicit and documented.
3. Preserve the current fail-closed boundaries: response byte cap, request timeout, no linked-document fetching, same-host HTTPS redirect restriction, payload validation, and retention of last-good snapshot on failure.
4. Preserve deterministic tests for changed/unchanged hashes, conditional validators, `304` without prior success, malformed feeds, unsafe hosts, and failure state. Add missing tests before expanding supported behavior.
5. If moving from whole-response hashing to per-item discovery or a BOE-specific schema, scope that as an explicit behavior change with fixtures and new acceptance scenarios; do not claim that behavior from the current implementation.
6. Keep recurring dispatch and operational alerting in `knowledge_update_scheduler`; keep document fetch/extraction in `official_document_candidate_ingestion`.

## Verification plan

### Automated

Focused command from the repository root:

```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_source_monitor.py
```

Then run the full backend suite:

```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```

The test suite should remain offline and use monkeypatched transport/time/state paths. Existing captured evidence also includes `./scripts/init.sh --fast`, which exercises the wider offline checks but does not prove legal coverage or live-source completeness.

### Operator check

Use a disposable configuration and state path. Confirm the report distinguishes first/changed from identical snapshots, stores validators when present, retains last-good hash/time after a failed source, and returns documented exit codes. Confirm state is outside `knowledge/` and canonical catalog/passages remain unchanged. Live checks are optional, read-only, bounded, and must record the endpoint and time; they are not legal review.

## Evidence to capture

- Focused and full backend command output/exit codes and dependency/interpreter versions.
- Example synthetic configuration and state shape, with explanation of the `source-monitor-state-v1` schema and atomic replacement behavior.
- Tests for supported formats, host/redirect enforcement, timeout and size bounds, validators/304, stable exact-byte hash, malformed payload, partial failure, and last-good preservation.
- CLI exit behavior for all-success, source failure, and invalid config/state.
- Evidence that the monitor does not fetch linked documents or alter canonical knowledge, `/ask`, or retrieval inputs.
- If a live smoke check is performed, note actual endpoint, date/time, status/format, and limits. Do not turn a successful response into freshness, authenticity, legal correctness, or coverage claims.
- Keep whole-response hashing, no BOE-specific schema validation, lack of FEGA/MAPA endpoint selection, and lack of an in-process scheduler visible as limitations until separately addressed.

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

Verification rerun after the contract was made implementation-specific:

- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_monitoring` — passed; all 7 focused monitor tests. Pytest emitted a cache-write warning in the restricted worktree environment; test results were unaffected.
- `GRADLE_USER_HOME=/private/tmp/manijero-gradle-home ./scripts/init.sh --fast` — passed; all 9 offline checks, including the JVM host suite, all 625 backend tests, contract examples, catalog validation, and offline evaluators. The temporary Gradle cache was needed because the normal user cache was not writable from the sandbox. The initial no-escalation attempt could not access/download the pinned Gradle distribution; the temporary-cache run completed successfully.
- Evaluator outputs remain synthetic/report-only and do not establish legal correctness, coverage, or freshness. No live BOE/BOJA request was made.

Independent validation identified two fail-closed gaps, which were repaired:

- Only HTTP `200` and the explicitly handled `304` now count as successful responses; unsupported response statuses fail and retain the prior successful snapshot. A regression test covers `206 Partial Content`.
- Persisted per-source state records are shape/type checked before any request. Malformed nested state raises `MonitorError`, so the CLI exits through its documented state-error path without contacting sources or overwriting the state file. A regression test covers this case.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_monitoring` — passed; all 9 focused monitor tests. Pytest emitted a restricted-worktree cache-write warning; assertions passed.
- `GRADLE_USER_HOME=/private/tmp/manijero-gradle-home ./scripts/init.sh --fast` — passed; all 9 offline checks, including JVM tests and 627 backend tests. The no-escalation attempt could not create Gradle's local lock socket; rerun with elevated execution and the cached temporary distribution passed.
- `git diff --check` — passed. No live upstream requests were made.

## Validator checklist

- [ ] Scope and docs accurately distinguish manual polling from external scheduling and document fetching/ingestion.
- [ ] Config accepts only explicit sources with unique valid IDs, supported formats, HTTPS, exact approved hosts, no credentials, and no fragment.
- [ ] Redirects cannot change scheme or host; request timeout and response byte limit are enforced.
- [ ] Empty/malformed payloads and unsupported conditions fail; RSS/Atom and JSON are not treated as legal-content validation.
- [ ] State schema/version is checked and writes are atomic; source failure retains last-good hash and success timestamp.
- [ ] ETag/Last-Modified are sent only when available; `304` without a prior successful hash fails safely.
- [ ] SHA-256 is described as a hash of exact response bytes, not per-document identity or authenticity evidence.
- [ ] CLI exits `0` only when all configured sources succeed, `1` on source failure, and `2` on config/state error.
- [ ] No scan updates catalog/passages, follows feed item URLs, or changes `/ask` behavior.
- [ ] Focused and full backend verification are recorded, with offline/live boundaries and unselected FEGA/MAPA endpoints explicit.
