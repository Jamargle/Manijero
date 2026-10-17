# Feature Spec: `source_catalog_validation`

## Source metadata

- Feature: `source_catalog_validation` — Approved source catalog validation
- Area: knowledge
- Depends on: `answer_api_contract` (accepted)
- Feature-list behavior: only catalog entries with approved provenance and required metadata can enter the MVP corpus.
- Feature-list verification: accept a valid official-source fixture and reject a malformed or non-approved fixture.
- Feature-list note: keep the MVP corpus curated and manually reviewed; automated discovery is deferred. The validator proves catalog-policy conformance only, never that a document is authentic, current, or legally applicable.
- Scope size: one versioned data contract plus one offline validation flow; correctly sized.

## Goal

Create a version-controlled, manually reviewed source-catalog boundary that prevents a document from becoming eligible for the MVP corpus unless its provenance is on the approved official-domain allowlist and its identity, freshness, integrity, and review metadata are complete. The validator is an offline Knowledge Ops tool; it must not make legal conclusions or fetch the web.

## Non-goals

- Downloading, parsing, OCRing, chunking, embedding, indexing, or retrieving documents.
- Automatic source discovery, classification, approval, or updating; human review remains required.
- Adding `/ask` behavior, a client flow, an LLM, a vector store, or a source card.
- Claiming a fixture or URL has been legally/currently verified. Validation checks catalog policy and metadata, not remote document contents or legal validity.
- Adding a real seed corpus unless a named reviewer supplies and approves it separately.

## Job story

When a maintainer proposes an official document for the MVP corpus, I want a deterministic local check to reject incomplete, unreviewed, expired, or non-approved-provenance metadata, so only traceable, human-approved documents can be handed to a future retrieval pipeline.

## Acceptance scenarios

### Valid approved source

Given a catalog entry with a unique stable ID, non-empty title and issuing body, an HTTPS original publication URL on an approved official domain, a SHA-256 content digest, ISO dates, explicit human approval, and `current` lifecycle state, when the offline validator runs, then it accepts the catalog and reports the checked entry count without network access.

### Malformed metadata

Given an entry missing a required field, using an invalid date or hash, duplicating an ID, or carrying an invalid URL, when validation runs, then it exits non-zero and names the entry/path and violated rule; it must not silently skip or accept the entry.

### Non-approved provenance or review

Given an entry whose URL host is outside the approved allowlist, uses non-HTTPS, has no explicit human approval/reviewer/date, is not `current`, or has a `valid_until` before the validation date, when validation runs, then it exits non-zero and the document is ineligible for corpus ingestion.

### Reproducible empty starting catalog

Given the repository has no separately reviewed source documents yet, when the canonical catalog is validated, then it is a valid versioned empty catalog and does not imply corpus coverage or readiness to answer legal questions.

## Repository research

Inspected:

- `feature_list.json`: this feature is not started, depends on accepted `answer_api_contract`, and defers automated discovery.
- `CONTEXT.md`, `docs/build-brief.md`, and `docs/domain-model.md`: regulatory claims require approved official material; sources require a stable link, issuing body, publication/update information, and last verification date.
- `docs/risks-and-open-questions.md`: unreviewed/malicious corpus content is a high risk; additions and changes need human review, and corpus ownership is unresolved.
- `MasterPlanV3.md` §§3, 6.1–6.3, 7.4–7.6, and 11.3: catalog decisions live in Git; intended offline flow preserves URL/hash/download date, uses current/validity metadata, and whitelists `boe.es`, `juntadeandalucia.es`, `fega.gob.es`, and `mapa.gob.es`.
- `contracts/openapi.yaml` and `docs/specs/answer_api_contract.md`: future answer sources expose provenance fields, but no retrieval or corpus implementation exists.
- `backend/app/main.py`, `backend/tests/test_health.py`, and `backend/README.md`: FastAPI currently has only `/health`; pytest is the existing backend test convention.
- `init.sh`: verifies KMP targets only; it has no backend/catalog command.

No `knowledge/` directory, catalog, ingestion code, retrieval code, source artifact store, or persistent E2E command exists today. `ARCHITECTURE.md`, `CONSTRAINTS.md`, `docs/technical-discovery.md`, `docs/mvp-scope.md`, and the skill template file are absent.

## Technical approach

### Canonical catalog and policy

Create `knowledge/source_catalog.json` as the canonical Git-tracked document with `schema_version: "source-catalog-v1"` and an initially empty `sources` array. Empty is intentional: this feature establishes the admission gate, not an unreviewed corpus. Create adjacent `knowledge/source_catalog.schema.json` as the readable versioned contract and `knowledge/README.md` with the approval/addition procedure and validation command.

Each source must contain:

- `id` (unique stable slug), `title`, and `issuing_body`;
- `original_url` (HTTPS direct official publication URL), optional `consolidated_url` (HTTPS official convenience text, never a replacement for the original), and issuer-to-host policy match;
- `published_on`, `downloaded_on`, and `verified_on` as `YYYY-MM-DD`, plus lowercase 64-character `content_sha256` for the downloaded original;
- `review_status: "approved"`, non-empty `reviewed_by` role/identifier, and `reviewed_on`;
- `lifecycle_status: "current"`, with optional `valid_until` on/after the supplied validation date; and
- optional retrieval metadata only when known: `campaign`, `critical`, and applicability fields. Unknown applicability remains absent rather than inferred.

The initial approved-host policy is exact host matching (including `www.` aliases) for BOE, Junta/BOJA, FEGA, and MAPA domains named in `MasterPlanV3.md`. Reject lookalike suffixes/subdomains, redirects, credentials in URLs, non-HTTPS URLs, and issuing-body/domain mismatches. Adding another issuer/domain is a reviewed schema-and-test change, not a fixture shortcut.

### Offline validator

Implement dependency-free validation in `backend/app/source_catalog.py` and a thin executable CLI at `backend/scripts/validate_source_catalog.py`. The CLI accepts a catalog path and optional `--as-of YYYY-MM-DD`; it defaults to current UTC only when omitted. Tests always pass `--as-of` so expiry behavior is deterministic. It reads local JSON only, produces actionable stderr diagnostics, returns zero only for a fully valid catalog, and must never issue HTTP requests or log document contents.

Apply structural and cross-field rules: top-level version/array shape; no unknown keys at every defined level; IDs unique; strings non-blank; URL, host, digest, enum, and ISO-date validity; review/approval and lifecycle requirements; issuer-host correspondence; date ordering (`published_on <= downloaded_on <= verified_on`, and `reviewed_on >= downloaded_on`); and expiry. Do not encode changing legal facts, derive a document's status from a URL, or treat a successful network response as approval.

## Expected file changes

- Create `knowledge/source_catalog.schema.json` — versioned catalog schema and field descriptions.
- Create `knowledge/source_catalog.json` — valid, explicit empty starting catalog.
- Create `knowledge/README.md` — human review/admission process, policy limitation, and command.
- Create `backend/app/source_catalog.py` — pure standard-library parsing and policy validation.
- Create `backend/scripts/validate_source_catalog.py` — local CLI wrapper.
- Create `backend/tests/test_source_catalog.py` and JSON fixtures under `backend/tests/fixtures/source_catalog/` — accepted official fixture plus malformed, non-approved-domain/review, duplicate, and expired cases.
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with actual status and command output evidence. This planning pass records the spec link only.

## Visual design impact

None. This is an offline repository/Knowledge Ops boundary; it changes no Compose UI or user-facing Spanish copy.

## Durable documentation impact

- `knowledge/README.md`: create; it is the durable operational contract for a reviewer adding a document.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, and `DESIGN.md`: no update; their source-grounding, manual review, and UI rules already govern this work.
- `MasterPlanV3.md`: no update; it is planning context, while the schema/README become executable catalog documentation.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: not needed; both are absent and this focused gate does not establish a broader runtime architecture.
- `PROGRESS.md` and `feature_list.json`: update after verification; do not claim a corpus or legal review merely because the validator exists.

## Implementation plan and tasks

1. Create the versioned schema, canonical empty catalog, and README; make required metadata and approved-host/issuer map explicit without adding unreviewed legal data.
2. Implement the pure validator and CLI with deterministic `--as-of`, strict keys, local-only I/O, and actionable errors.
3. Add focused fixtures and pytest coverage for the valid official case and every rejection class in the acceptance scenarios, including no-network behavior if practical via a mocked transport guard.
4. Run focused checks and validate the canonical empty catalog; fix contract/fixture inconsistencies.
5. Update feature evidence/status and `PROGRESS.md` with only commands actually run and results.

## Verification plan and evidence

Run from repository root after installing existing backend development dependencies:

```sh
python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12
cd backend && pytest tests/test_source_catalog.py
```

Also run the existing backend regression suite:

```sh
cd backend && pytest
```

Capture command output; accepted fixture name/count; each invalid fixture's non-zero result and diagnostic; canonical empty catalog result; and `git diff --check`. No browser, API, or E2E test is required because the feature has neither a user-facing/API flow nor a persistent E2E framework.

## Validator checklist

- [ ] Canonical catalog and schema are versioned, tracked, and validate while empty.
- [ ] A valid fixture uses a whitelisted official HTTPS host and all required provenance/review fields.
- [ ] Malformed, duplicate-ID, non-HTTPS/lookalike/non-approved host, unapproved, non-current, and expired fixtures fail non-zero with useful diagnostics.
- [ ] Digest/date/order and issuer-host checks are covered by tests.
- [ ] Validation is local-only, deterministic with `--as-of`, dependency-free, and does not log source content or make legal/currentness claims.
- [ ] No retrieval, document ingestion, `/ask`, client UI, automated discovery, or unrelated files are added.
- [ ] `feature_list.json` and `PROGRESS.md` report only verification actually performed.

## Risks and handoff notes

The validator proves catalog-policy conformance, not that a remote document is authentic, current, or legally applicable. A named corpus-review owner and first-pilot topic coverage remain open product/operations questions. The implementation agent should preserve this distinction, add no real document until it has human approval, and hand the validated catalog boundary to the later `source_retrieval` feature.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-13
./init.sh --backend-tests tests/test_source_catalog.py
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/source_catalog_validation.md.
- Added the versioned empty catalog knowledge/source_catalog.json, the readable contract knowledge/source_catalog.schema.json (source-catalog-v1), the review procedure in knowledge/README.md, the dependency-free validator backend/app/source_catalog.py, and the local CLI backend/scripts/validate_source_catalog.py.
- python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12 exited 0 and reported '0 source(s) checked as of 2026-10-12'.
- python -m pytest tests/test_source_catalog.py: 43 passed. Fixture valid_official_source.json was accepted with 3 checked sources; valid_empty_catalog.json was accepted with 0. All 21 rejection fixtures exited non-zero (20 policy cases exit 1 naming the JSON path and violated rule; malformed_json.json exits 2).
- python -m pytest (backend regression): 45 passed (43 new plus the 2 existing health tests). Bare `pytest` cannot collect the pre-existing tests/test_health.py, so the regression suite must be run as `python -m pytest` from backend/.
- git diff --check is clean. Validation is local-only: no network access (enforced by a socket-guard test) and diagnostics never echo catalog field values.
- Android/Gradle checks do not apply to this knowledge/backend feature and were not run.
- Independent validator accepted 2026-10-12 after personally reproducing exit 0 on the canonical/valid fixtures, 20 policy and 1 malformed non-zero rejections, the --as-of expiry boundary, a socket-guard no-network check, and a no-content-leak check across all fixtures. Record: docs/validations/source_catalog_validation.md.
