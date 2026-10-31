# Appendix — `source_catalog_validation`

Planning and verification record for [`docs/specs/source_catalog_validation.md`](../../specs/source_catalog_validation.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/source_catalog_validation.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `feature_list.json`: this feature is not started, depends on accepted `answer_api_contract`, and defers automated discovery.
- `CONTEXT.md`, `docs/archive/build-brief.md`, and `docs/domain-model.md`: regulatory claims require approved official material; sources require a stable link, issuing body, publication/update information, and last verification date.
- `docs/risks-and-open-questions.md`: unreviewed/malicious corpus content is a high risk; additions and changes need human review, and corpus ownership is unresolved.
- `docs/archive/MasterPlanV3.md` §§3, 6.1–6.3, 7.4–7.6, and 11.3: catalog decisions live in Git; intended offline flow preserves URL/hash/download date, uses current/validity metadata, and whitelists `boe.es`, `juntadeandalucia.es`, `fega.gob.es`, and `mapa.gob.es`.
- `contracts/openapi.yaml` and `docs/specs/answer_api_contract.md`: future answer sources expose provenance fields, but no retrieval or corpus implementation exists.
- `backend/app/main.py`, `backend/tests/test_health.py`, and `backend/README.md`: FastAPI currently has only `/health`; pytest is the existing backend test convention.
- `scripts/init.sh`: verifies KMP targets only; it has no backend/catalog command.

No `knowledge/` directory, catalog, ingestion code, retrieval code, source artifact store, or persistent E2E command exists today. `ARCHITECTURE.md`, `CONSTRAINTS.md`, `docs/archive/technical-discovery.md`, `docs/mvp-scope.md`, and the skill template file are absent.

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
