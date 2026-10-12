# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` now contains the shared Spanish chat starting screen; answer service, land management, and official-source retrieval are not implemented.
- Shared tests include reducer coverage for the chat composer; backend and full UI behavior are deferred to later features.
- The backend now has a minimal FastAPI service with a documented liveness endpoint.
- Product features are tracked in `feature_list.json`. `backend_health`, `answer_api_contract`, `local_land_store`, `chat_home`, and `suggested_questions` are accepted.
- The shared chat home now shows three approved Spanish example questions that fill the composer (without sending) when tapped; the answer service, land management, and official-source retrieval are not implemented.

## Start and verify

- Startup/toolchain check: `./init.sh`
- Standard verification: `./init.sh --verify`
- Android build: `./init.sh --android`
- Launch Desktop: `./init.sh --desktop`

Verification evidence for `chat_home`:

- `./init.sh` passes with the restored Gradle 9.8.0 wrapper and reports the current feature state.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes.
- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android` stop before compilation because neither `ANDROID_HOME` nor `local.properties` with `sdk.dir` is configured in this worktree. No Android result is claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running target; compilation is covered by `:desktopApp:build`.

## Next feature

`suggested_questions` is accepted (record: `docs/validations/suggested_questions.md`). Feasible next features with satisfied dependencies: `source_catalog_validation` (after accepted `answer_api_contract`), `add_land` (after accepted `local_land_store`), and `chat_question_submission` (after accepted `chat_home`/`answer_api_contract`/`backend_health`). The orchestrator should pick by roadmap priority.

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
| 2026-10-12 | Implemented `suggested_questions` | Shared `ChatHomeAction.SuggestedQuestionSelected` reducer case, three approved example strings in Compose resources with a wrapping-safe vertical layout in `ChatHomeScreen`, new reducer tests, and previews. `:shared:jvmTest` (7/7), `:shared:testAndroidHostTest` (7/7), `:androidApp:assembleDebug`, and `:desktopApp:build` pass via `./init.sh --verify`; Android emulator UI smoke and Desktop launch smoke recorded. Awaiting independent validation. |
| 2026-10-12 | Accepted `suggested_questions` | Independent validator accepted after re-running `:shared:jvmTest --rerun-tasks` (7/7), `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build`, and a byte-for-byte string check against the spec. Record: `docs/validations/suggested_questions.md`. |

## Feature evidence

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
