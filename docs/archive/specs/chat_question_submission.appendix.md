# Appendix — `chat_question_submission`

Planning and verification record for [`docs/specs/chat_question_submission.md`](../../specs/chat_question_submission.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/chat_question_submission.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: one shared Compose
  screen owns `ChatHomeState` locally; submit currently only displays a placeholder.
- `ChatHomeState.kt` and `ChatHomeStateTest.kt`: reducer preserves original wording
  and rejects blank input; it has no request, conversation, or failure state.
- `shared/src/commonMain/composeResources/values/strings.xml`: Spanish UI strings are
  centralized in Compose resources.
- `contracts/openapi.yaml`: canonical `/ask` request and three response states;
  general requests require an empty lands array and a question no longer than 2,000
  characters. Source and land-clarification payloads are already typed by contract.
- `backend/app/main.py` and `backend/README.md`: no `/ask` route exists yet; `/health`
  proves HTTP liveness only.
- `shared/build.gradle.kts` / `gradle/libs.versions.toml`: shared module has Compose,
  lifecycle, and kotlin-test only; it has no HTTP, serialization, coroutine, or mock
  HTTP dependencies yet.
- `scripts/init.sh`: available checks are shared JVM/Android host tests and Android/Desktop
  builds; there is no persistent end-to-end test runner.

Relevant constraints come from `CONTEXT.md`, `docs/archive/build-brief.md`,
`docs/domain-model.md`, `DESIGN.md`, and `docs/risks-and-open-questions.md`: shared
`commonMain` behavior/UI, plain Spanish, no raw-question or land-data logging, and
minimal service context. `docs/archive/MasterPlanV3.md` calls for a client API boundary, Ktor
`MockEngine` tests, and a deterministic `/ask` pipeline.

## Implementation plan and tasks

1. Confirm the contract fixtures with `python3 contracts/validate_examples.py`; choose
   Ktor versions compatible with the existing Kotlin 2.4.20/Compose setup.
2. Define DTOs, request mapping, narrow service interface, injected endpoint/client,
   and a MockEngine-backed test double. Encode only the contract's general request.
3. Implement the pure state machine and tests for blank/over-limit rejection, exact
   wording, one in-flight request, success, returned status retention, and recovery to
   editable idle state after completion/failure.
4. Wire the shared use case to Compose with lifecycle-safe coroutine handling and
   render messages/progress using resource strings and accessible semantics.
5. Add focused transport tests that assert POST path/body and decode the accepted
   answered fixture; add one UI/presentation test or reducer assertion proving a
   response becomes exactly one assistant message.
6. Run feasible builds and manually use a deterministic mock/local `/ask` responder.
   Record evidence and only then update `feature_list.json` and `PROGRESS.md` with the
   implementation result; the planner must not mark the feature complete.

## Verification plan

Run before and after implementation:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest
./gradlew :desktopApp:build
./gradlew :androidApp:assembleDebug
./scripts/init.sh --verify
```

The last two Android-inclusive checks may be environment-blocked if this worktree has
no valid Android SDK; record the actual outcome rather than claiming success. There is
no E2E command today, so focused common/JVM reducer plus Ktor MockEngine tests are the
appropriate automated coverage. Once a local `/ask` implementation is available,
manually submit an answered fixture through Android and Desktop: verify exact user text,
one working state, one reply, disabled duplicate submit, and a new question afterward.

## Evidence to capture

- Test output for the contract validator and shared tests.
- MockEngine assertion showing `POST /ask`, original question, and exactly
  `{ "mode": "general", "lands": [] }` land context.
- Build output for Desktop and, if configured, Android.
- A short Android/Desktop manual-smoke record or screenshot showing the Spanish working
  state and one completed conversation; identify the mock/local responder used.
- Confirmation that logs/test diagnostics contain no raw question or land content.

## Validator checklist

- [ ] Shared UI/business behavior remains in `commonMain`; platform code is only HTTP
  engine/configuration wiring.
- [ ] Blank and over-2,000-character questions make no request; accepted input retains
  exact original wording.
- [ ] One active submission produces one user message, one visible working state, and
  at most one assistant message for the response.
- [ ] The request is contract-valid `POST /ask` with `general` and no land data.
- [ ] Returned response statuses are decoded without invented sources, land labels, or
  legal conclusions; status-specific presentation is not claimed complete.
- [ ] Spanish copy, semantic labels, text scaling, scrollability, and Desktop keyboard
  operation are reviewed.
- [ ] MockEngine/reducer tests and all feasible Gradle checks pass, with environmental
  blockers documented.
- [ ] No backend, contract, unrelated feature, or planning-progress status is changed
  without implementation evidence.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Shared chat flow lives in commonMain: pure ChatHomeState.reduce returning ChatReduction(state, effect) plus composition-scoped ChatConversation that runs the single in-flight AnswerService.ask on a rememberCoroutineScope; App takes an injected AnswerService defaulting to UnavailableAnswerService because the backend has no /ask.
- Blank and over-2,000-character questions produce no request or message; the composer shows a Spanish limit explanation and never rewrites the wording. Transcript entries are ordered and labelled "Tú"/"Asistente" as text; a plain-Spanish working indication with a polite live region shows while submitting and Preguntar is disabled; needs_land_clarification keeps its status and opaque ids and shows a neutral acknowledgement that claims no answer.
- KtorAnswerService posts the contract AskRequest to <baseUrl>/ask with JSON ContentNegotiation (explicitNulls = false); no production base URL is hard-coded and no logging was added.
- python3 contracts/validate_examples.py -> "Validated 2 request and 3 response examples against answer_api_contract".
- ./gradlew :shared:jvmTest -> BUILD SUCCESSFUL, 24 tests 0 failures (ChatHomeStateTest 13, ChatConversationTest 3, KtorAnswerServiceTest 2, LandRepositoryTest 4, 2 scaffold). KtorAnswerServiceTest asserts POST /ask, the exact question "  ¿Puedo regar hoy?  ", land_context exactly {"mode":"general","lands":[]}, and decodes contracts/examples/response-answered.json from the repo.
- ./gradlew :shared:testAndroidHostTest -> BUILD SUCCESSFUL, 22 tests 0 failures; ./gradlew :desktopApp:build and ./gradlew :androidApp:assembleDebug -> BUILD SUCCESSFUL (debug APK produced); ./scripts/init.sh --verify -> BUILD SUCCESSFUL. Android checks ran because this worktree has local.properties sdk.dir.
- Runtime smoke: ./gradlew :desktopApp:run opened the Desktop window with no exception in the run log. No scripted click-through or screenshot (interactive GUI) and no live answer, because the backend still exposes only /health; the working-state/one-reply behavior is proven by ChatConversationTest.
- Independent validator accepted (2026-10-12), docs/validations/chat_question_submission.md: re-ran the contract validator, :shared:jvmTest --rerun (24 tests), :shared:testAndroidHostTest --rerun (22 tests), a full :androidApp:assembleDebug :desktopApp:build --rerun-tasks, :shared:compileKotlinIosSimulatorArm64, and ./scripts/init.sh --verify (all BUILD SUCCESSFUL) plus a 50s :desktopApp:run launch with no exceptions.
- Independent validator confirmed all four acceptance scenarios hold and decoded all three contract fixtures (answered/abstained/needs_land_clarification) with the shipped DTO, beyond the implementer's answered-only transport test; no raw question/land logging, no hard-coded production URL, no /health misuse, and contracts/ plus backend/ untouched.
- Validator findings F1-F3 are non-blocking and carried forward: F1 platform engine/endpoint wiring + Android/Desktop manual smoke (owner: the /ask wiring slice), F2 bounded HttpTimeout (owner: network_error_recovery), F3 small/wide-window + text-scale/keyboard evidence and transcript auto-scroll (owner: chat_accessibility).
