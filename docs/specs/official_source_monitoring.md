# Feature Spec: `official_source_monitoring`

## Source metadata

- **Feature:** `official_source_monitoring` — Monitor approved official sources (`knowledge`).
- **Status at planning:** `not_started`; depends on no feature dependencies.
- **Source behavior:** Scan allowlisted official BOE, BOJA, Junta, FEGA, and MAPA source endpoints for new or changed documents using documented APIs/RSS and conditional requests where available. Record timestamp, URL, status, validators, and content hash; scans never mutate canonical knowledge. Include manual dispatch and observable failures.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

## Goal and boundaries

Poll allowlisted official source registries and feeds (initially the BOE Open Data API at https://www.boe.es/datosabiertos/api/api.php and BOJA RSS at https://www.juntadeandalucia.es/boja/distribucion/s51.xml) on an owner-configured recurring cadence. This detects candidates; it does not determine legal applicability or change answerable knowledge. Preserve approved-source provenance and the existing safe-answer contract.

**In scope:** Scan allowlisted official BOE, BOJA, Junta, FEGA, and MAPA source endpoints for new or changed documents using documented APIs/RSS and conditional requests where available. Record timestamp, URL, status, validators, and content hash; scans never mutate canonical knowledge. Include manual dispatch and observable failures.

**Non-goals:** automatic legal interpretation, unreviewed canonical corpus changes, changes to the app wire contract unless explicitly required, and claims beyond the reviewed corpus/evaluation.

## Job story

When the answer service needs this capability, I want its behavior and evidence to be inspectable and recoverable, so that automation cannot silently weaken source grounding or operational confidence.

Only explicitly configured official endpoints may be polled. Do not discover arbitrary URLs from fetched content or follow redirects outside the approved host allowlist.

## Acceptance scenarios

### Normal operation

Given a supported and configured BOE API or BOJA RSS source, when its scheduled or manually dispatched scan runs, then it records last-success time, source URL, response validators where available, and stable content hashes for new/changed candidates; it produces no canonical knowledge changes.

### Invalid, unavailable, or ambiguous input

Given a malformed artifact, unavailable upstream, ambiguous legal change, or failed verification, when the run processes it, then it fails closed, preserves existing approved behavior, and records an actionable failure without exposing personal data.

### Reproducibility and review

Given the same pinned code, configuration, and approved inputs, when the work is repeated, then outputs are reproducible or differences are explicitly reported; any user-answerable knowledge change has a recorded human approval.

## Technical approach

Scan allowlisted official BOE, BOJA, Junta, FEGA, and MAPA source endpoints for new or changed documents using documented APIs/RSS and conditional requests where available. Record timestamp, URL, status, validators, and content hash; scans never mutate canonical knowledge. Include manual dispatch and observable failures. Inspect the current backend and knowledge schemas before implementation; preserve existing API and code-owned answer properties. Add focused fixtures for boundary and failure cases. Pin mutable dependencies and model/artifact revisions. Make resource, timing, freshness, and evaluation evidence visible.

## Expected file changes

- `backend/` implementation and focused tests/fixtures.
- `knowledge/` schemas or generated artifacts only where the approved format requires them.
- `docs/risks-and-open-questions.md`, `PROGRESS.md`, and `backend/README.md` as implementation evidence resolves current limitations.

## Visual design impact

None.

## Durable documentation impact

- Update `ARCHITECTURE.md` and `CONSTRAINTS.md` if a durable boundary or invariant changes.
- Update `backend/README.md` with operator setup, execution, failure recovery, and artifact lifecycle.
- Keep current evidence and honest limits in this spec appendix and acceptance record.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`official_source_monitoring.appendix.md`](official_source_monitoring.appendix.md).
