# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` now renders the shared Spanish chat flow: ordered transcript, composer, a plain-Spanish working state, a Spanish explanation of the 2,000-character contract limit, a neutral acknowledgement while a land clarification is pending, the three approved example questions that fill the composer, and a `Chat`/`AddLand` destination that saves a land and confirms it in plain Spanish.
- The chat boundary is a shared contract client: pure `ChatHomeState` reducer plus `ChatConversation` (composition-scoped effect runner) over an injected `AnswerService`; `KtorAnswerService` talks to `<baseUrl>/ask` and the default app wiring is `UnavailableAnswerService` because the backend exposes no `/ask` yet. Retrieval, answer/source presentation, and failure-recovery copy remain deferred.
- Shared tests include reducer coverage for the chat flow and suggested-question selection, presentation coverage for one reply per submission, and a Ktor MockEngine transport test that decodes the accepted contract fixture.
- The backend now has a minimal FastAPI service with a documented liveness endpoint; it still has no `/ask` route.
- The knowledge boundary now exists: `knowledge/source_catalog.json` is a valid versioned (`source-catalog-v1`) catalog that is intentionally empty, and `backend/scripts/validate_source_catalog.py` rejects any entry whose provenance, metadata, review, or lifecycle state does not conform to policy. No document has been reviewed or added.
- `add_land` is accepted: shared `AddLandState`/`AddLandScreen`, resource-backed Spanish copy, and Android/Desktop composition roots wired to the accepted storage adapters. Android and Desktop checks ran in this worktree because `init.sh` created `local.properties` with the installed SDK; independent validation recorded in `docs/validations/add_land.md`.
- The Desktop app stores lands in `~/.manijero/lands-v1.txt`; Android uses the `manijero_lands` SharedPreferences file. Both go through the shared versioned `land-store-v1` format.
- Product features are tracked in `feature_list.json`. `backend_health`, `answer_api_contract`, `local_land_store`, `chat_home`, `suggested_questions`, `add_land`, `source_catalog_validation`, `chat_question_submission`, and `visual_foundation` are accepted.
- `visual_foundation` (the shared olive-toned theme in `commonMain`) is accepted: `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`, `ManijeroTheme.kt`, and `ManijeroTypography.kt` define the `DESIGN.md` tokens, a fully specified `lightColorScheme`, a `LocalManijeroSemanticColors` local for caution/strong olive, and the `bodySmall` line-height override; `ManijeroTheme` is applied once inside `App()` and all fifteen existing previews use it (record: `docs/validations/visual_foundation.md`). `response_states`, `answer_source_cards`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, and `chat_accessibility` now have their `visual_foundation` dependency satisfied.

## Start and verify

- Startup/toolchain check: `./init.sh`
- Standard verification: `./init.sh --verify`
- Android build: `./init.sh --android`
- Launch Desktop: `./init.sh --desktop`
- Source catalog check: `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of YYYY-MM-DD`
- Backend tests: `cd backend && python -m pytest` (note: bare `pytest` cannot collect `tests/test_health.py`, because nothing puts `backend/` on `sys.path`; use `python -m pytest` or install the test runner into a local virtualenv)

## Next feature

Dependency-ready unfinished features: `source_retrieval` (its dependency `source_catalog_validation` is accepted). `visual_foundation` was accepted on 2026-10-13, so `response_states` now depends only on `chat_question_submission` and `safe_abstention` (still `not_started`), and `network_error_recovery` and `land_list` have their `visual_foundation` dependency satisfied but remain blocked by their other `not_started` dependencies. `POST /ask` itself still has no backend implementation, so the `/ask` wiring and Android/Desktop manual smoke remain follow-ups (validator finding F1).

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
| 2026-10-12 | Implemented `chat_question_submission` | Shared reducer/effect chat flow, composition-scoped `ChatConversation`, Ktor `/ask` service with MockEngine test decoding `contracts/examples/response-answered.json`, injected `AnswerService` wiring, Spanish working/limit/clarification strings, and updated reducer tests. `python3 contracts/validate_examples.py`, `:shared:jvmTest` (24 tests), `:shared:testAndroidHostTest` (22 tests), `:desktopApp:build`, `:androidApp:assembleDebug`, and `./init.sh --verify` all pass; Desktop app started without exceptions. |
| 2026-10-12 | Accepted `chat_question_submission` | Independent validator (docs/validations/chat_question_submission.md) confirmed all four acceptance scenarios, re-ran the contract validator, JVM (24) and Android host (22) tests, a full `--rerun-tasks` Android+Desktop build, the iOS compile, and `./init.sh --verify`; decoded all three contract fixtures with the shipped DTO and confirmed no logging, no hard-coded production URL, and no contract/backend changes. Findings F1-F3 carried forward to the `/ask` wiring, `network_error_recovery`, and `chat_accessibility`. |
| 2026-10-13 | Added `visual_foundation` as a feature definition and wired the visual-foundation dependency into `response_states`, `answer_source_cards`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, and `chat_accessibility` | `feature_list.json` (commit 139d460); definition only, no implementation or checks run. |
| 2026-10-13 | Documentation consistency pass over accepted features | Added `docs/validations/chat_home.md` (reconstructed acceptance record), linked each accepted feature's validation record from `feature_list.json`, and corrected the `PROGRESS.md` next-feature and `visual_foundation` status. No product code changed. |
| 2026-10-13 | Implemented `visual_foundation` (self-verified; awaiting independent validation) | Added the shared `theme` package (`ManijeroColors.kt`, `ManijeroTheme.kt`, `ManijeroTypography.kt`) with the `DESIGN.md` tokens, a complete `lightColorScheme` mapping, a `LocalManijeroSemanticColors` local for caution/strong olive, and the single `bodySmall` line-height override; applied `ManijeroTheme` once in `App()` and repointed all fifteen previews. Tests: `:shared:jvmTest` 54 (incl. `ManijeroColorsTest` 10, `ManijeroTypographyTest` 4), `:shared:testAndroidHostTest` 51, all 0 failures; `:androidApp:assembleDebug` and `:desktopApp:build` pass via `./init.sh --verify`. Updated `DESIGN.md` with the derived-token table and light-only decision. |
| 2026-10-13 | Accepted `visual_foundation` | Independent validator re-ran `./init.sh --verify` and `:shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` (54 JVM / 51 Android host tests, 0 failures), reproduced the WCAG AA contrast pairs with an independent computation, and confirmed scope discipline (commonMain-only theme, no new module/dependency, hosts/strings/Gradle untouched, no logging). Record: `docs/validations/visual_foundation.md`. |

## Feature evidence

### chat_home — accepted

Independent validator accepted commit 47e80c8 (acceptance commit a79946f; record:
`docs/validations/chat_home.md`). Verification recorded at acceptance:

- `./init.sh` passes with the restored Gradle 9.8.0 wrapper and reports the current feature state.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes and compiles the shared Compose screen.
- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android` stopped before compilation because the worktree had no `ANDROID_HOME` or `local.properties` with `sdk.dir`. No Android result was claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running target; compilation is covered by `:desktopApp:build`.
- Outstanding: the spec's Android/Desktop manual smoke ("locate the Spanish field without adding a land, type a question, and confirm the action becomes available") was not executed at acceptance. It is not evidence of failure and can now be run where the Android SDK is configured.

### chat_question_submission — accepted

- `ChatHomeState.reduce` is a pure reducer returning `ChatReduction(state, effect)`. It
  rejects blank and over-2,000-character questions, refuses a second submit while a
  request is in flight, keeps the submitted wording immutable for both the user message
  and `AskRequest.question`, appends at most one assistant message per response, retains
  `abstained` / `needs_land_clarification` status plus opaque `land_ids_to_choose` without
  inventing an answer or a land choice, and releases the request on failure without
  discarding a newly typed draft.
- `ChatConversation` applies the reducer and runs the single `AnswerService.ask` call on
  its injected `CoroutineScope` (composition-scoped `rememberCoroutineScope()` in
  `App`), so no Composable performs a network call and `CancellationException` is
  rethrown. `App(answerService = UnavailableAnswerService)` injects the boundary, renders
  the ordered transcript with text labels "Tú"/"Asistente", a plain-Spanish working
  indication ("Estoy preparando la respuesta…") with a polite live region, a disabled
  **Preguntar** while in flight, the Spanish limit explanation without rewriting wording,
  and a neutral clarification acknowledgement that claims no answer.
- `KtorAnswerService` posts the contract `AskRequest` to `<baseUrl>/ask`
  (`ContentNegotiation` + `answerJson` with `explicitNulls = false`). No production base
  URL is hard-coded, and platform engines can be supplied through `answerHttpClient`.
- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples
  against answer_api_contract".
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL, 24 tests, 0 failures
  (`ChatHomeStateTest` 13, `ChatConversationTest` 3, `KtorAnswerServiceTest` 2,
  `LandRepositoryTest` 4, 2 scaffold tests). `KtorAnswerServiceTest` asserts `POST /ask`,
  the exact original question `"  ¿Puedo regar hoy?  "`, exactly
  `{"mode":"general","lands":[]}` for `land_context`, and decodes the accepted
  `contracts/examples/response-answered.json` from the repository working tree.
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, 22 tests, 0 failures.
- `./gradlew :desktopApp:build` → BUILD SUCCESSFUL; `./gradlew :androidApp:assembleDebug`
  → BUILD SUCCESSFUL (`androidApp/build/outputs/apk/debug/androidApp-debug.apk`);
  `./init.sh --verify` → BUILD SUCCESSFUL. This worktree has
  `local.properties` (`sdk.dir=/Users/jose/Library/Android/sdk`), so the Android checks
  ran; no environment blocker remains.
- Runtime smoke: `./gradlew :desktopApp:run` started the Desktop window with the shared
  chat screen and produced no exception in the run log. No scripted click-through or
  screenshot was taken (interactive GUI target), and no live answer was requested because
  the backend still has no `/ask`; the working-state/one-reply behavior is covered by
  `ChatConversationTest`.
- Privacy check: `grep -rn "println|Log\.|Logger|printStackTrace" shared/src` returns no
  matches, so no raw question or land content is logged.
- Deliberately not implemented (owned by later features): `response_states`, source
  cards, land selection/context, retry UI and failure copy, suggested prompts, and any
  backend/contract change.

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

### visual_foundation — passing (awaiting independent validation)

What changed:

- New shared theme package `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/`:
  - `ManijeroColors.kt`: the ten `DESIGN.md` tokens plus the derived values, a fully specified
    `lightColorScheme(...)` (every documented role set explicitly, so no Material default can leak),
    `ManijeroSemanticColors` + `LocalManijeroSemanticColors` for the roles Material 3 lacks
    (caution, caution surface, strong olive; `danger` = `colorScheme.error`, `border` =
    `colorScheme.outline`), and the dependency-free WCAG `relativeLuminance`/`contrastRatio` helpers.
  - `ManijeroTypography.kt`: Material 3 `Typography` with the single documented `bodySmall`
    line-height override (16sp → 18sp); size, weight, letter spacing, and font family untouched.
  - `ManijeroTheme.kt`: `ManijeroTheme { }` (Material 3 theme + semantic local) plus review-only
    token-board previews at 1x and `fontScale = 2f`.
- `App.kt`: wraps the destination content in `ManijeroTheme` once (the shared composition root), and
  all seven previews use `ManijeroTheme`. `lands/AddLandScreen.kt`: all eight previews use
  `ManijeroTheme`. No layout, copy, spacing, or behavior changed; the Android/Desktop/iOS hosts stay
  theme-free so they inherit the one shared theme.
- `DESIGN.md`: added the derived-token table and the light-only decision to the "Visual foundation"
  section.
- Not changed: `MainActivity.kt`, desktop `main.kt`, `MainViewController.kt`, `strings.xml`, any
  Gradle file or the version catalog, backend/contracts, land storage, `init.sh`; no new module,
  framework, or dependency.

Verification (commands run from the repository root):

- `./init.sh --verify` → BUILD SUCCESSFUL.
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL:
  54 JVM tests / 0 failures (`ManijeroColorsTest` 10, `ManijeroTypographyTest` 4 new) and
  51 Android host tests / 0 failures (same 14 new theme tests).
- `./gradlew :androidApp:assembleDebug` and `./gradlew :desktopApp:build` → BUILD SUCCESSFUL
  (debug APK produced) as part of `--verify`.
- Centralization greps: no `Color(0x` outside `theme/`; no argument-less `MaterialTheme {`; the only
  `MaterialTheme(` call site is the `ManijeroTheme` wrapper; no
  `LocalMinimumInteractiveComponentSize`/`minimumInteractiveComponentSize` override; the theme is
  applied once in `App()`.

Honest gaps:

- Interactive Android/Desktop UI smokes (screenshots, greyscale non-color cue check, emulator
  `font_scale 2.0`, Desktop window resize/keyboard focus) were not run in this non-interactive
  session. They are covered by the review-only token-board preview and the pure contrast tests, and
  remain the manual checks for independent validation.
- Light-only by decision: no dark palette exists (`DESIGN.md` records this). Desktop OS-level text
  scaling is not wired in this repository, so enlarged-text evidence is preview-based
  (carried validator finding F3, owner `chat_accessibility`).
