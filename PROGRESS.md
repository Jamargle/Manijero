# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` now contains the shared Spanish chat starting screen; answer service, land management, and official-source retrieval are not implemented.
- Shared tests include reducer coverage for the chat composer; backend and full UI behavior are deferred to later features.
- The backend now has a minimal FastAPI service with a documented liveness endpoint.
- The shared chat home now shows three approved Spanish example questions that fill the composer (without sending) when tapped; the answer service, land management, and official-source retrieval are not implemented.
- The knowledge boundary now exists: `knowledge/source_catalog.json` is a valid versioned (`source-catalog-v1`) catalog that is intentionally empty, and `backend/scripts/validate_source_catalog.py` rejects any entry whose provenance, metadata, review, or lifecycle state does not conform to policy. No document has been reviewed or added.
- `add_land` is accepted: shared `AddLandState`/`AddLandScreen`, resource-backed Spanish copy, and Android/Desktop composition roots wired to the accepted storage adapters. Android and Desktop checks ran in this worktree because `init.sh` created `local.properties` with the installed SDK; independent validation recorded in `docs/validations/add_land.md`.
- Product features are tracked in `feature_list.json`. `backend_health`, `answer_api_contract`, `local_land_store`, `chat_home`, `suggested_questions`, `add_land` and `source_catalog_validation` are accepted. Android verification awaits SDK configuration.
- The Desktop app stores lands in `~/.manijero/lands-v1.txt`; Android uses the `manijero_lands` SharedPreferences file. Both go through the shared versioned `land-store-v1` format.

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
| 2026-10-12 | Implemented `add_land` (self-verified, ready for independent validation) | Shared `AddLandState`/`AddLandAction` reducer, stateless `AddLandScreen` with previews, resource-backed Spanish copy, `App()` destination and lands wiring, Android/Desktop composition roots. `./init.sh --verify` passed: `:shared:jvmTest` 21 tests, `:shared:testAndroidHostTest` 20 tests, `:androidApp:assembleDebug`, `:desktopApp:build`. Desktop startup smoke via `:desktopApp:run` ran without startup errors. |
| 2026-10-12 | Accepted `add_land` | Independent validator re-ran `./init.sh --verify`, `:shared:jvmTest` and `:shared:testAndroidHostTest` with `--rerun-tasks` (21 and 20 tests, 0 failures), `:androidApp:assembleDebug`, `:desktopApp:build`, and a Desktop startup smoke; confirmed scope, commonMain-only UI, no land-data/exception logging, and the copy contract. Verdict accept; record `docs/validations/add_land.md`. |
| 2026-10-12 | Implemented `suggested_questions` | Shared `ChatHomeAction.SuggestedQuestionSelected` reducer case, three approved example strings in Compose resources with a wrapping-safe vertical layout in `ChatHomeScreen`, new reducer tests, and previews. `:shared:jvmTest` (7/7), `:shared:testAndroidHostTest` (7/7), `:androidApp:assembleDebug`, and `:desktopApp:build` pass via `./init.sh --verify`; Android emulator UI smoke and Desktop launch smoke recorded. Awaiting independent validation. |
| 2026-10-12 | Accepted `suggested_questions` | Independent validator accepted after re-running `:shared:jvmTest --rerun-tasks` (7/7), `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build`, and a byte-for-byte string check against the spec. Record: `docs/validations/suggested_questions.md`. |
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

### add_land — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandState.kt`: pure
  `AddLandState` (raw name/municipality text, selected enums, name-error and save-error
  flags), `AddLandAction`, `reduce`, and `toDraftOrNull()`. It keeps raw text for
  correction, trims only to validate and to build the `LandDraft`, leaves `areaHectares`
  and `notes` unset, and owns no ids, timestamps, or persistence rules.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: stateless
  Material 3 form with a required name field (error state plus plain-Spanish message),
  optional `Municipio (opcional)`, accessible `RadioButton` rows for `Riego` and
  `Producción` (both starting on `No lo sé`), a live-region save-failure message, one
  prominent `Guardar terreno` action, and `Cancelar` as the visible back control.
  Eight previews cover blank, name error, known values, save failure, long text,
  compact, wide, and 2x font scale.
- `shared/src/commonMain/composeResources/values/strings.xml`: all add-land labels,
  choices, errors, and the success confirmation.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `App(landRepository)`
  holds the `Chat`/`AddLand` destination, routes `Mis terrenos` to the form, performs the
  synchronous repository write, returns to the chat home with a plain-Spanish saved
  confirmation, and shows the failure message while keeping every entered value.
  `App()` (no argument) is retained for the iOS scaffold and previews; without a
  repository the lands action is unavailable instead of creating a store in common code.
- `androidApp/.../MainActivity.kt`: one `LandRepository(SharedPreferencesLandStorage(applicationContext))`.
- `desktopApp/.../main.kt`: one remembered `LandRepository(FileLandStorage(~/.manijero/lands-v1.txt))`.

Verification (2026-10-12):

- `./init.sh` passed and created the worktree `local.properties`, so Android checks could
  run for the first time in this checkout.
- `./init.sh --verify` (i.e. `:shared:jvmTest :shared:testAndroidHostTest
  :androidApp:assembleDebug :desktopApp:build`) passed: 21 shared JVM tests (0 failures),
  20 Android host tests (0 failures), `androidApp/build/outputs/apk/debug/androidApp-debug.apk`
  produced, Desktop app built.
- New tests: `AddLandStateTest` (11) — default `UNKNOWN` choices, blank/whitespace name
  rejected with no draft, trimmed name-only draft with no area/notes, `IRRIGATED`+`ORGANIC`
  mapping, deliberate `MIXED`, Unicode name, save failure retaining values for retry,
  error clearing on edit, and two lands surviving reopening. `AddLandDesktopStoreTest` (1)
  — the real `FileLandStorage` keeps a name-only and a known-attributes land after
  reopening.
- Desktop startup smoke: `./gradlew :desktopApp:run` launched `com.jamarglex.manijero.MainKt`
  with the injected file store and ran without startup errors until the session stopped it
  (Gradle reported the expected SIGTERM exit 143).
- Not verified by automated UI tests: interactive Android/Desktop clicking, screen-reader, and
  large-system-text behavior; no emulator, device, or Compose UI test harness exists yet. The
  spec defers this to `land_form_accessibility`, and it is reported here rather than claimed.

Independent validation (2026-10-12): accept. The validator re-ran `./init.sh --verify`,
`:shared:jvmTest` and `:shared:testAndroidHostTest` with `--rerun-tasks` (21 and 20 tests,
0 failures), `:androidApp:assembleDebug`, `:desktopApp:build`, and a Desktop startup smoke,
then confirmed scope discipline, `commonMain`-only product UI, no land-data or raw-exception
logging, and the copy contract. Record: `docs/validations/add_land.md`.

### suggested_questions — accepted

- Independent validator accepted (record: `docs/validations/suggested_questions.md`) after re-running
  `:shared:jvmTest --rerun-tasks` (ChatHomeStateTest 7/7), `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug`, and `:desktopApp:build`, and independently confirming the three shipped
  strings match the spec byte-for-byte with no unapproved deadline wording.
- `ChatHomeAction.SuggestedQuestionSelected(question: String)` sets `question` to the supplied
  text and clears `submittedQuestion`; the reducer performs no I/O and adds no dependency,
  ViewModel, route, or platform adapter.
- The three approved strings ship verbatim in
  `shared/src/commonMain/composeResources/values/strings.xml`
  (`chat_home_suggestion_solicitud_unica`, `chat_home_suggestion_sigpac`,
  `chat_home_suggestion_condicionalidad`); a Python byte-for-byte comparison against the spec's
  Content decision matched all three, and the unapproved deadline wording
  ("¿Hasta cuándo puedo cambiar mi solicitud?") is not shipped.
- `ChatHomeScreen` renders a plain-Spanish heading plus the three examples as full-width
  `OutlinedButton` controls in a vertical `Column` inside the existing 720dp content width.
- Verification commands:
  - `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; `ChatHomeStateTest` 7/7 (4 new).
  - `./init.sh --verify` → BUILD SUCCESSFUL; `:shared:jvmTest`, `:shared:testAndroidHostTest`
    (ChatHomeStateTest 7/7), `:androidApp:assembleDebug` (`androidApp-debug.apk`),
    `:desktopApp:build`.
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, debug APK): all three examples visible
  without sideways scrolling; tapping each filled the composer with the exact question and enabled
  `Preguntar`; submit showed only "Tu pregunta está lista para continuar."; re-selecting an example
  cleared the stale submitted message; at `font_scale 2.0` labels wrapped to two lines with no
  horizontal overflow.
- Desktop smoke: `:desktopApp:run` launched the shared `App()` and stayed alive ~50s with no
  runtime exception; interactive window/click inspection was not captured in this session.
