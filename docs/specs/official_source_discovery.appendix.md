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

Not implemented. No implementation or verification evidence exists yet.

## Validator checklist

- [ ] Only explicitly configured first-party registries are queried.
- [ ] Registry and publication URLs are validated against the existing issuer/host policy; redirects cannot escape it.
- [ ] Candidate and observation data are separate from canonical knowledge artifacts.
- [ ] Repeat scans deduplicate; changed observations retain prior provenance.
- [ ] Failed, malformed, and unsupported registries are reported as unchecked and do not erase last-good candidates.
- [ ] Diagnostics do not expose document content, secrets, or personal/land details.
- [ ] No automatic issuer/host admission, legal conclusion, or answerability change occurs.
- [ ] Feature verification and all source coverage limits are recorded honestly.
