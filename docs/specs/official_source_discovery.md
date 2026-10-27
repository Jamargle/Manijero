# Feature Spec: `official_source_discovery`

## Source metadata

- **Feature:** `official_source_discovery` — Discover candidate publications from approved official registries (`knowledge`).
- **Status at planning:** `not_started`; depends on `official_source_monitoring`, `source_catalog_validation`.
- **Source behavior:** Inspect explicitly configured, documented discovery registries for new publication records or source endpoints from the already approved issuers and hosts. Emit deduplicated, provenance-bearing candidates for quarantine/review. Never add issuers, hosts, registries, or documents to canonical knowledge automatically.
- **Feature-list verification:** Record registry coverage, candidate provenance, and unsupported or failed registries. Discovery results are leads for review, not proof of authenticity, current law, or corpus completeness.

## Goal and boundaries

Automate finding newly listed official publications from the project’s approved issuers so that operators do not have to discover each document manually. Discovery is limited to configured first-party registries and approved hosts; it must expose which registries were checked and their last successful scan.

**In scope:** Discover new document records from explicitly configured official publication indexes for BOE, Junta de Andalucía/BOJA, FEGA, and MAPA where a documented machine-readable registry is available. Validate candidate URLs against the existing exact host policy, normalize and deduplicate candidate identity, preserve registry and observation provenance, and write candidates to a separate reviewable queue. Unsupported issuers or registries are reported as coverage gaps.

**Non-goals:** General web crawling, search-engine scraping, adding a new issuer or host to the approved allowlist, fetching/parsing candidate document bodies, legal interpretation, or changing canonical source/passages files. Candidate document fetching belongs to `official_document_candidate_ingestion`; scheduled dispatch belongs to `knowledge_update_scheduler`; approval and corpus edits remain human-reviewed.

## Job story

When official publishers add publications to their registries, I want the system to surface new candidates with a traceable origin, so I can review them without relying on manual discovery or allowing untrusted sources into answers.

## Acceptance scenarios

### New publication from a configured registry

Given a valid registry snapshot containing a publication not seen before, when discovery runs, then it writes one deduplicated candidate with the registry URL, publication URL, issuer, observed time, stable identity/hash, and review status `pending`, without changing canonical knowledge.

### Repeat scan and changed registry entry

Given an already recorded publication, when the same registry is scanned again, then the candidate is not duplicated; a changed entry is recorded as a new observed version linked to the prior candidate, with both observations retained.

### Unapproved or unsafe destination

Given a registry entry whose issuer is unknown, whose URL host is not exactly approved, or whose redirect leaves the approved host, when discovery processes it, then it is rejected with a value-safe diagnostic and is never fetched or placed in the approved catalog.

### Registry failure or incomplete coverage

Given an unavailable, malformed, or unsupported registry, when discovery runs, then it preserves prior candidates, records the failure and last successful scan, and reports the issuer/registry as unchecked rather than implying complete coverage.

### Human review gate

Given a pending discovery candidate, when automated processing completes, then it remains non-answerable until an identified human verifies provenance and approves any catalog change through the existing review workflow.

## Technical approach

Use source-specific adapters for configured first-party registries and parse only documented machine-readable responses. Keep registry configuration separate from `knowledge/source_catalog.json`, and validate discovered publication URLs against the existing issuer/host policy before any later fetch. Store observations and dedupe keys in a separate candidate state/artifact with schema versioning, deterministic normalization, bounded response sizes/timeouts, same-host HTTPS redirects, and no content text in diagnostics. Do not infer that a publisher has no new material when a registry is unsupported or failed. Provide a manual scan command; the scheduler will invoke it in a later feature.

## Expected file changes

- `backend/app/` — registry adapters, validation, deduplication, and candidate persistence.
- `backend/scripts/` — deterministic manual discovery command.
- `backend/tests/` and fixtures — supported registry examples, duplicates, changed records, unsafe URLs, malformed/unavailable registries, and unsupported coverage.
- `knowledge/` — only versioned discovery configuration or candidate schema/artifacts; never mutate canonical catalog/passages automatically.
- `backend/README.md`, `knowledge/README.md`, `docs/risks-and-open-questions.md`, and this spec appendix — operator lifecycle, coverage, and evidence.

## Visual design impact

None. The feature is an operator-facing backend capability; no app UI is introduced.

## Durable documentation impact

- `ARCHITECTURE.md`: update if implementation adds a discovery/candidate storage boundary.
- `CONSTRAINTS.md`: update if new durable source-admission invariants are introduced; preserve human approval as mandatory.
- `AGENTS.md`: not needed; the workflow does not change.
- `knowledge/README.md`: update to describe discovery candidates and the canonical admission gate.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`official_source_discovery.appendix.md`](official_source_discovery.appendix.md).
