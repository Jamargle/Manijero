# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` now contains the shared Spanish chat starting screen; answer service, land management, and official-source retrieval are not implemented.
- Shared tests include reducer coverage for the chat composer; backend and full UI behavior are deferred to later features.
- The backend now has a minimal FastAPI service with a documented liveness endpoint.
- The knowledge boundary now exists: `knowledge/source_catalog.json` is a valid versioned (`source-catalog-v1`) catalog that is intentionally empty, and `backend/scripts/validate_source_catalog.py` rejects any entry whose provenance, metadata, review, or lifecycle state does not conform to policy. No document has been reviewed or added.
- Product features are tracked in `feature_list.json`. `backend_health`, `answer_api_contract`, `local_land_store`, `chat_home`, and `source_catalog_validation` are accepted; Android verification awaits SDK configuration.

## Start and verify

- Startup/toolchain check: `./init.sh`
- Standard verification: `./init.sh --verify`
- Android build: `./init.sh --android`
- Launch Desktop: `./init.sh --desktop`
- Source catalog check: `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of YYYY-MM-DD`
- Backend tests: `cd backend && python -m pytest` (note: bare `pytest` cannot collect `tests/test_health.py`, because nothing puts `backend/` on `sys.path`; use `python -m pytest` or install the test runner into a local virtualenv)

Verification evidence for `chat_home`:

- `./init.sh` passes with the restored Gradle 9.8.0 wrapper and reports the current feature state.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes.
- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android` stop before compilation because neither `ANDROID_HOME` nor `local.properties` with `sdk.dir` is configured in this worktree. No Android result is claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running target; compilation is covered by `:desktopApp:build`.

## Next feature

Preferred next feature: `suggested_questions` — add example prompts after the accepted chat starting screen. `source_retrieval` is also now dependency-ready (both its prerequisites, `answer_api_contract` and `source_catalog_validation`, are accepted).

## Session log

| Date | Change | Evidence |
|---|---|---|
| 2026-10-05 | Build brief initiated | User described project: olive tree field manager app with AI chatbot |
| 2026-10-05 | Discovery documents created | CONTEXT.md, build-brief.md, domain-model.md, risks-and-open-questions.md |
| 2026-10-07 | Harness starter started | AGENTS.md, init.sh created; feature_list.json in progress |
| 2026-10-07 | Harness starter completed | Minimal repo harness created |
| 2026-10-08 | Refreshed the startup harness and split MVP work into session-sized features. | Repository inspection; no tests run in this harness update. |
| 2026-10-09 | Product discovery and harness with OpenAI Luna High. | Some conflicts manually solved 😂 and additional skills.|
| 2026-10-11 | Added subagent workflow agents | .opencode/agents workflow files |
| 2026-10-11 | Implemented and independently validated `backend_health` | `backend/tests`: 2 passed; live Uvicorn `/health` smoke check returned HTTP 200 and the documented JSON response |
| 2026-10-11 | Completed `chat_home` | Added shared Spanish chat starting screen and composer, pure reducer tests, Compose resources, and implementation spec. `:shared:jvmTest` and `:desktopApp:build` pass. Android checks are blocked by missing Android SDK configuration in the worktree. |
| 2026-10-11 | Accepted `answer_api_contract` | OpenAPI 3.1 contract, five representative fixtures, dependency-free validator, and independent validation record; focused checks passed. |
| 2026-10-11 | Implemented and independently reviewed `local_land_store` | Shared `LandRepository`, versioned local format, Android/Desktop adapters; `:shared:jvmTest` passed (5 tests); Android compile blocked by missing SDK configuration. |
| 2026-10-12 | Implemented `source_catalog_validation` (passing, awaiting independent validation) | Added versioned empty `knowledge/source_catalog.json`, `knowledge/source_catalog.schema.json`, `knowledge/README.md`, dependency-free `backend/app/source_catalog.py`, CLI `backend/scripts/validate_source_catalog.py`, and 23 fixtures with 43 focused tests. `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12` exited 0 with 0 sources; `python -m pytest tests/test_source_catalog.py` 43 passed; `python -m pytest` 45 passed; `git diff --check` clean. |
| 2026-10-12 | Accepted `source_catalog_validation` | Independent validator reproduced exit 0 on canonical/valid fixtures, 20 policy and 1 malformed non-zero rejections with located diagnostics, the `--as-of` expiry boundary, a socket-guard no-network check, and no content leakage across all fixtures. See `docs/validations/source_catalog_validation.md`. |

## Feature evidence

### source_catalog_validation — accepted

- Canonical catalog `knowledge/source_catalog.json` is `schema_version: source-catalog-v1`
  with an empty `sources` array; it validates and does not imply corpus coverage.
- `knowledge/source_catalog.schema.json` is the readable contract; the test suite
  asserts its required/optional fields, issuer enum, and version stay in sync with
  `backend/app/source_catalog.py`.
- `backend/app/source_catalog.py` is standard-library only and offline. It enforces
  strict/unknown keys, unique slug ids, non-blank text, HTTPS approved-host and
  issuer-host match, SHA-256 digest shape, ISO dates and ordering, `approved`
  review with a named reviewer, `current` lifecycle, and `--as-of` expiry.
- Commands actually run:
  - `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12`
    → exit 0, `valid source catalog: ... (schema source-catalog-v1, 0 source(s) checked as of 2026-10-12)`.
  - Accepted fixture `valid_official_source.json` (3 sources: BOE, Junta de Andalucía,
    FEGA) → exit 0; `valid_empty_catalog.json` → exit 0 with 0 sources.
  - All 21 rejection fixtures → non-zero. Twenty fail with exit 1 and a located
    diagnostic such as `$.sources[0].content_sha256: required key is missing`,
    `$.sources[1].id: duplicate id; already used by $.sources[0]`,
    `$.sources[0].original_url: host is not on the approved official-domain allowlist`,
    and `$.sources[0].valid_until: is before the validation date; the document is
    expired and ineligible`; `malformed_json.json` fails with exit 2.
  - `cd backend && python -m pytest tests/test_source_catalog.py` → 43 passed.
  - `cd backend && python -m pytest` → 45 passed (43 new + 2 existing health tests).
  - `git diff --check` → clean.
- Not run: Android/Gradle checks (not applicable to this knowledge/backend feature).
- Independent validation (2026-10-12): `accept`. The validator re-ran the canonical
  and valid fixtures (exit 0), all 23 fixtures (20 exit 1 + 1 exit 2), the `--as-of`
  expiry boundary, a socket-guard no-network check, and a no-content-leak check; it
  also confirmed scope discipline and that the recorded evidence matched. Record:
  `docs/validations/source_catalog_validation.md`.
- Limitation: the validator proves catalog-policy conformance, not that a remote
  document is authentic, current, or legally applicable. No real document was added.

### local_land_store — accepted

- `LandRepository` supports create/list/update/delete with stable generated ids,
  required trimmed names, explicit unknown attributes, and optional fields.
- `SharedPreferencesLandStorage` persists Android records; `FileLandStorage`
  persists Desktop/JVM records. Both use the shared versioned format.
- Malformed individual records are skipped during recovery; writes replace the
  complete snapshot.
- Verification: `/Users/jose/AndroidStudioProjects/Manijero/gradlew -p . :shared:jvmTest`
  passed. Android compilation could not run because the worktree has no Android
  SDK location (`ANDROID_HOME`/`local.properties`).
