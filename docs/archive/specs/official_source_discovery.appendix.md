# `official_source_discovery` planning appendix

## Repository research

- `knowledge/README.md` defines the current approved issuers/hosts and states that no automated discovery can add a catalog entry without human review.
- `knowledge/source_catalog.json` is the canonical set of four reviewed sources; it is not a publisher registry.
- `backend/app/source_catalog.py` enforces exact HTTPS host/issuer policy and is the policy to reuse rather than duplicate.
- `docs/specs/official_source_monitoring.md` covers configured feed polling; it does not discover registry endpoints or new issuers.
- `docs/specs/official_document_candidate_ingestion.md` covers fetching/parsing known candidates into quarantine.
- `docs/specs/knowledge_update_scheduler.md` owns recurring scans and missed/failed-run reporting.
- `docs/specs/legal_change_impact_analysis.md`, `knowledge_update_review_pr.md`, and `knowledge_reindex_release.md` cover downstream analysis, human review, and approved release.

## Implementation plan

1. Inventory first-party machine-readable publication registries for each currently approved issuer; verify each registry URL, documented format, update semantics, and access limits from official documentation. Do not invent a registry for an issuer when none is verified; surface the coverage gap.
2. Define a versioned registry configuration and candidate/observation schema that is separate from canonical source and passage files.
3. Implement one adapter per verified registry. Bound network access, parse, and response size; enforce exact approved host and same-host HTTPS redirect rules before accepting a publication URL.
4. Normalize stable identifiers, deduplicate repeated records, retain changed observations, and preserve source registry provenance. Emit only pending candidate records.
5. Add a manual CLI, adversarial fixtures, operator documentation, and evidence showing unsupported/failed registries remain visibly unchecked.
6. Update `knowledge_update_scheduler` to dispatch these discovery checks on its configured cadence after both features are implemented.

## Verification plan

- Run `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests`.
- Unit tests use synthetic registry payloads and a network stub; do not depend on live registries for deterministic acceptance.
- Manually run each implemented adapter against its documented official endpoint before enabling it operationally; record date, endpoint, response status, and whether observed entries were only queued.
- Verify the canonical `knowledge/source_catalog.json` and `knowledge/passages.json` remain unchanged after discovery.

## Evidence to capture

- Official documentation and checked date for each supported registry adapter.
- Adapter coverage matrix for BOE, Junta/BOJA, FEGA, and MAPA, including unsupported/unchecked status.
- Candidate provenance, deduplication and changed-entry tests, unsafe URL rejection, failure preservation, and confirmation that no candidate became answerable.
- Focused test output, command output, and live smoke limitations.

## Feature evidence

Implemented 2026-10-27. The prior blocked conclusion was invalid: the HTTP 400 was caused by omitting `Accept`; that response says `No soportado ningún mime type de la cabecera Accept.` With `Accept: application/xml`, `curl` returned HTTP 200 from `https://www.boe.es/datosabiertos/api/boe/sumario/20261027`; the response contains publication date `20261027`, daily id `BOE-S-2026-266`, 290 item records, identifiers/titles and BOE PDF links. With `Accept: application/json`, the same endpoint returned HTTP 200 (381,221 bytes). Official API docs are https://www.boe.es/datosabiertos/api/api.php. This grounds the BOE XML adapter. Chrome's XML rendering was the user's reproduction, not the basis for parser design.

Official Junta OpenAPI at https://datos.juntadeandalucia.es/api/v0/boja/openapi.json (HTTP 200, checked 2026-10-27) describes `/api/v0/boja/get/calendar` and `/api/v0/boja/get/bulletin`. The live calendar query `?year=2026` returns `{columns:[number,date],rows:[...]}`; the bulletin query `?year=2026&number=1` returned HTTP 200, 502,923 bytes, with 30 result records. Records expose `id`, machine-key `title`, human-readable `summaryNoHtml`, and `pdf[].publicUrl`; the adapter prefers the human title and validates document links against the approved Junta host policy. It deduplicates calendar issue numbers and fetches each bulletin. Limits are 400 issues, 160 MiB aggregate BOJA response bytes, and 5 MiB per response; an over-limit/incomplete scan fails without committing partial candidates. The `/all?year=2026&format=json` endpoint returned HTTP 200 but transferred 45 MB in 30 seconds before the smoke timed out, so it is not used. FEGA and MAPA first-party publication registries remain unverified and explicitly unchecked; neither is guessed from BOE publications.

Implementation: versioned config and separate candidate state; bounded HTTPS requests, exact registry endpoint configuration, same-host redirects, approved exact publication host checks; BOE XML and BOJA calendar+bulletin JSON adapters; deterministic issuer+identifier identity and title/URL version hashes; pending candidates with registry/publication provenance and timestamped observations; repeat deduplication and changed-version retention; failure status preserving last success and prior candidates; per-registry transactional commit; value-safe diagnostics; manual CLI. FEGA/MAPA always appear unchecked. Canonical catalog/passages are not written.

Verification: `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests` — 634 passed (one existing Starlette/httpx deprecation warning); focused adapter tests — 7 passed; `./scripts/init.sh --fast` — all nine checks passed (rerun after final edits). Python syntax compilation and JSON syntax checks passed; config example validates against its JSON Schema. Direct `curl` live smoke verified BOE and BOJA endpoints/payloads as above. The local Python interpreter's certificate store rejected the BOE TLS certificate when attempting live smoke through `urllib`; no TLS verification was disabled. Candidate-state CLI was not run live because of that local trust-store issue, so live operator-state creation remains unverified. No live state was created, and no legal validity or complete-registry coverage is implied.

Validator repair (2026-10-27): BOE now fails the scan when any parsed `<item>` lacks identifier, title, or URL; BOJA record flattening fails on any non-object or incomplete row, while bulletin hit-count validation ensures one complete record per result. Regression tests seed prior good state, then feed mixed valid/malformed BOE and BOJA snapshots and verify unchecked status, unchanged candidates, and preserved `last_success_at` (transactional; no partial candidate commit). `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_discovery` passed: 636 tests; `./scripts/init.sh --fast` passed all nine checks. Existing Starlette/httpx deprecation warning remains.

Independent validator accepted (2026-10-27) after rerunning both commands above and reviewing the malformed-row regression behavior, transactional persistence, source admission boundaries, and documentation. Validator confirmed FEGA/MAPA remain explicitly unchecked and the live CLI/TLS trust-store limitation is accurately recorded. Acceptance record: [`docs/validations/official_source_discovery.md`](../../validations/official_source_discovery.md).

## Validator checklist

- [ ] Only explicitly configured first-party registries are queried.
- [ ] Registry and publication URLs are validated against the existing issuer/host policy; redirects cannot escape it.
- [ ] Candidate and observation data are separate from canonical knowledge artifacts.
- [ ] Repeat scans deduplicate; changed observations retain prior provenance.
- [ ] Failed, malformed, and unsupported registries are reported as unchecked and do not erase last-good candidates.
- [ ] Diagnostics do not expose document content, secrets, or personal/land details.
- [ ] No automatic issuer/host admission, legal conclusion, or answerability change occurs.
- [ ] Feature verification and all source coverage limits are recorded honestly.
