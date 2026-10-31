# Feature Spec: `official_source_monitoring`

## Source metadata

- **Feature:** `official_source_monitoring` — Monitor approved official sources (`knowledge`).
- **Status at planning:** `not_started`; no feature dependencies. The named worktree already contains an implementation; this contract records its intended boundary for independent validation.
- **Source behavior:** Manually poll explicitly configured BOE/BOJA and other approved-host feeds or API endpoints. Record URL, outcome/status, timestamps, validators when supplied, and a SHA-256 response snapshot. Scans never mutate canonical knowledge. An external owner-managed scheduler may invoke the command; this feature does not implement recurring scheduling.
- **Feature-list verification:** Implementation, focused tests, operational evidence, and limits are recorded before acceptance. Successful polling does not establish legal currency, coverage, or answer quality.

## Goal and boundaries

Give an operator a bounded, repeatable way to detect changes at explicit official endpoints and preserve a local last-good snapshot and failure history for human review. Supported response formats are RSS/Atom XML and JSON. Initial example endpoints are BOE Open Data (`https://www.boe.es/datosabiertos/api/api.php`) and the BOJA feed (`https://www.juntadeandalucia.es/boja/distribucion/s51.xml`); endpoints remain explicit configuration, not inferred from source links.

**In scope:** manual CLI invocation; strict source configuration validation; exact HTTPS host allowlist; same-host HTTPS redirects only; bounded timeout and response size; XML/JSON structural validation; response-byte SHA-256 change detection; conditional ETag/Last-Modified requests when available; atomic local state persistence; per-source success/failure reporting and meaningful exit codes.

**Non-goals:** in-process scheduling or retry loops, alert delivery, fetching linked document bodies, parsing individual document semantics or legal applicability, producing legal-change conclusions, modifying `knowledge/source_catalog.json` / `knowledge/passages.json`, or changing `/ask` and its contract. Do not imply FEGA/MAPA coverage merely because their document hosts are approved.

## Job story

When an operator wants to check configured official feeds, they want a clear record of whether each source responded and whether its response changed, so that a human can decide what to review without the assistant silently changing its evidence.

The configuration is the complete set of requested endpoints. Only HTTPS URLs whose exact host is in the existing approved-host policy are accepted. Redirects may remain on the same HTTPS host only; feed item URLs are never fetched.

## Acceptance scenarios

### Successful snapshot and repeat scan

Given a configured RSS/Atom or JSON endpoint returns a non-empty structurally valid payload, when the operator runs a scan, then local state records source URL, attempt and success timestamps, HTTP status, ETag/Last-Modified when present, the SHA-256 of the exact response bytes, and whether the snapshot differs from the prior successful snapshot. Identical response bytes report unchanged.

### Conditional response and failure

Given validators exist, when a later request receives `304`, then the previous successful hash is retained and the source reports unchanged; a `304` without prior successful hash is failure. Given a timeout, malformed/empty payload, unsupported status, or oversized response, then the source reports failure, retains its last-good hash/time, and the overall CLI exits nonzero without losing other source outcomes.

### URL safety and knowledge isolation

Given a source URL is non-HTTPS, malformed, credential-bearing, lookalike, or outside the exact approved host list, or a redirect changes scheme/host, when validation/request handling occurs, then that destination is rejected. Given any successful or changed scan, then canonical catalog/passages and `/ask` behavior remain untouched; scan output is a monitoring signal only.

## Technical approach

Use a backend module with an explicit source configuration (`id`, `url`, `format`), injected/time-controllable scan entry point where practical, bounded HTTP requests, RSS/Atom root or JSON syntax validation, and a versioned state file outside `knowledge/`. Persist each attempted source record atomically while retaining last-good evidence on failure. Hash exact response bytes: this is intentionally a whole-response signal, not per-document semantic change detection. Do not log arbitrary upstream exception details or response bodies. The CLI prints a JSON report and exits `0` when all configured sources succeed, `1` for any source failure, and `2` for configuration/state errors.

## Expected file changes

- `backend/app/source_monitor.py`: validation, requests, payload validation, hashing, and state.
- `backend/scripts/scan_official_sources.py`: manual CLI and exit/report behavior.
- `backend/tests/test_source_monitor.py`: synthetic tests for host safety, formats, hashes, validators, failures, and last-good preservation.
- `backend/README.md`: configuration example, invocation, state path, limits, and external scheduler guidance.
- `docs/risks-and-open-questions.md`, `PROGRESS.md`, and feature evidence/validation record: acceptance-time status and remaining risks.
- `knowledge/`: no changes to canonical artifacts.

## Visual design impact

None. This feature is backend/operator-facing.

## Durable documentation impact

- `ARCHITECTURE.md`: not needed unless the monitoring-state ownership boundary changes.
- `CONSTRAINTS.md`: not needed unless implementation introduces a durable invariant beyond the existing knowledge approval gate.
- `AGENTS.md`: not needed; repository routing does not change.
- `backend/README.md`: update with actual operator workflow, state, and limitations.
- `PROGRESS.md` and `docs/risks-and-open-questions.md`: update only from verified implementation/operation evidence.
- `knowledge/README.md`: no change unless the explanation of manual discovery changes; canonical human approval remains required.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_source_monitor.py
```
<!-- verify:end -->

## Appendix

See [`official_source_monitoring.appendix.md`](../archive/specs/official_source_monitoring.appendix.md) for repository findings, implementation evidence, verification, and unresolved limits.
