# Appendix — `network_error_recovery`

Planning and verification record for [`docs/specs/network_error_recovery.md`](../../specs/network_error_recovery.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/network_error_recovery.md` remains the authoritative
acceptance record.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: pure `ChatHomeState`
  (`question`, `messages`, `phase {IDLE, SUBMITTING}`, `submittedQuestion`, `lastResponseStatus`,
  `landIdsToChoose`), `ChatHomeAction` (including an argument-less `data object RequestFailed`),
  `ChatEffect.Submit`, and `reduce`. `RequestFailed` currently restores `question = question.ifBlank {
  submittedQuestion }`, clears `submittedQuestion`, and returns to `IDLE` — the failure transition exists and
  is tested, but there is no failure field, no visible copy, and no retry action.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`: applies `reduce` and runs the
  single `AnswerService.ask` on the injected scope; it rethrows `CancellationException` and swallows every
  other exception as `RequestFailed`. This is the only place that classifies a thrown failure today.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `AnswerService.ask`,
  `KtorAnswerService` (`client.post("<baseUrl>/ask").body()`), `answerHttpClient(engine)` (installs only
  `ContentNegotiation`), the contract DTOs, and `UnavailableAnswerService` (throws). `MAX_QUESTION_LENGTH`
  lives here. No timeout or `expectSuccess` is configured, which is exactly finding F2.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatHomeScreen(state, onAction, onLandsClick)`
  renders the transcript (`ChatMessageBubble`) plus a `ChatNoticeBubble` for the working state and the
  clarification acknowledgement; `App()` owns `ChatConversation` via `remember`. Transcript entries are
  `ChatMessage(Speaker, text)`; the failure UI must be a separate notice, not a message.
- `shared/src/commonMain/composeResources/values/strings.xml`: one shared Spanish resource file already
  holding `chat_home_working`, the clarification acknowledgement, `land_list_retry` (`Reintentar`), and the
  land vocabulary; copy is resource-backed and reused.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatHomeStateTest.kt` and
  `ChatConversationTest.kt`: the established `kotlin.test` patterns (`reduce` assertions; fakes for
  `AnswerService`); two `ChatHomeStateTest` cases call the argument-less `RequestFailed` and will be updated
  by this feature. `shared/src/jvmTest/.../chat/KtorAnswerServiceTest.kt` uses `MockEngine` + `runTest` and
  decodes `contracts/examples/response-answered.json`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt` / `ManijeroTheme.kt`:
  `colorScheme.error`/`errorContainer`/`onErrorContainer` are the danger pair (contrast already tested); no
  raw colors are allowed outside `theme/`.
- `contracts/openapi.yaml`: `/ask` documents only `200` (with `status`), `400`, and `422`; there is no error
  body schema, so a non-2xx response cannot be a valid answer.
- `gradle/libs.versions.toml` / `shared/build.gradle.kts`: Ktor `3.1.3` `ktor-client-core` is already a
  `commonMain` dependency, so `io.ktor.client.plugins.HttpTimeout` needs no new dependency; `commonTest` has
  `kotlin-test`, `kotlinx-coroutines-test`, and `ktor-client-mock`.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt` call `App(landRepository)` with no
  `answerService`, so the shipped default is `UnavailableAnswerService` — a real, reproducible
  "service error" path for manual smoke, while a genuine network timeout needs the F1 wiring.
- `DESIGN.md` lines 76-77: preserve user-entered data when requests fail, show a clear waiting state, and
  allow a simple retry after recoverable failures. `docs/risks-and-open-questions.md` has no open row that
  this feature must settle.

The feature is correctly sized: one added state field plus one action, one notice component, and one
transport plugin/config change. One user flow, no new data model or persistence.

## Implementation plan and tasks

1. Write the `ChatHomeStateTest` expectations first: `RequestFailed(kind)` sets the reason and retains the
   exact wording; a draft typed during the request is preserved; `RetryClicked` emits `Submit(originalWording)`
   with no extra user message and clears the notice; a retry that fails again keeps one user message;
   `QuestionChanged`/`SuggestedQuestionSelected`/`ResponseReceived` clear the notice; retry is a no-op with
   no failure or while submitting. Then implement the state/reducer changes.
2. Add the `RequestFailure` enum and the two payload-free exceptions; translate Ktor failures in
   `KtorAnswerService.ask`; map them in `ChatConversation`; install `HttpTimeout` and `expectSuccess` with
   named constants in `answerHttpClient`.
3. Add `ChatFailureNotice` to `App.kt` with resource-backed copy and previews; keep it out of the
   `messages` list and mutually exclusive with the working indication.
4. Extend `ChatConversationTest` (unavailable vs service-error classification, retry to success with one
   answer and one user message) and `KtorAnswerServiceTest` (stalled response fails within the bound;
   `500`-with-answer-shaped-body fails and is not an answer; malformed `200` body fails).
5. Run the checks below plus Desktop/Android manual smoke; report any blocker or unperformed check honestly.
6. Update `feature_list.json` and `PROGRESS.md` only after implementation and independent validation.

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests "com.jamarglex.manijero.ChatConversationTest" --tests "com.jamarglex.manijero.chat.KtorAnswerServiceTest"
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest
./gradlew :desktopApp:build
./gradlew :androidApp:assembleDebug
./scripts/init.sh --verify
```

This worktree has `local.properties`, so the Android steps should run; if the SDK is unavailable, record the
exact blocker instead of claiming an Android result. There is no persistent E2E command and no Compose
UI-test harness, so focused pure tests plus MockEngine transport tests are the right automated coverage;
do not claim E2E or automated UI coverage.

Manual smoke (record what actually happened):

1. Android emulator and Desktop launch the app with the shipped default `UnavailableAnswerService`: submit a
   question and confirm the service-error notice plus `Reintentar` appear, the exact question stays in the
   conversation and in the composer, no `Asistente` answer appears, and `Reintentar` shows the working state
   and returns to the same notice.
2. Confirm a contract-valid `answered`/`abstained` response (driven by tests or a temporary mock) never
   shows the failure notice, and that `abstained` is not treated as a failure.
3. Re-run the reducer tests to demonstrate the retry path ending in exactly one assistant message.
4. Honest limitation: a real network timeout cannot be reproduced in the running app until the `/ask`
   platform wiring exists (carried finding F1, separate owner); the timeout is covered by
   `KtorAnswerServiceTest` with `MockEngine`. If `runTest` cannot drive Ktor's `HttpTimeout` through a
   stalled mock, cover the timeout-to-copy mapping directly with a fake that throws the unavailable signal,
   assert the installed bounded timeout constants, and state which probe was used.

Capture: focused and full test counts/names; the three strings compared byte-for-byte with this spec;
evidence that a failure appends no assistant message and that a retry adds no second user message; the
`HttpTimeout`/`expectSuccess` assertion and the `500`-not-an-answer test; `./scripts/init.sh --verify` output (or the
exact blocker); a Desktop/Android screenshot or short record of the notice and `Reintentar`; and
`grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src` with no
matches.

## Validator checklist

- [ ] A timeout/unreachable failure and a service error each show a distinct plain-Spanish notice and a
      visible `Reintentar`; the notice is not a `ChatMessage` and carries no `Asistente` answer label.
- [ ] No failure path appends an assistant/answered message, and the message explicitly says the answer has
      not been received; a contract-valid `answered`/`abstained` response never shows the notice.
- [ ] The exact original wording (including leading/trailing spaces) is retained after a failure and is what
      `Reintentar` resends; `RetryClicked` adds no second user message and a repeated failure remains
      retryable; retry is not actionable while a request is in flight.
- [ ] The composer cannot remain `SUBMITTING`: `answerHttpClient` installs a bounded `HttpTimeout` with named
      constants, and a stalled/error `MockEngine` response makes `ask` fail rather than hang.
- [ ] `expectSuccess` makes a non-2xx `/ask` a failure; a `500` with an answer-shaped body is never presented
      as an answer; accepted `200` fixtures still decode.
- [ ] Typing a new question or selecting an example clears the failure notice and restores normal behavior.
- [ ] Copy is resource-backed and matches this spec's three strings verbatim; danger uses the themed
      `error`/`errorContainer` pair with text, the notice is a polite live region, and controls keep
      Material's minimum target size and Desktop keyboard focus.
- [ ] Product behavior stays in `commonMain`; no new module, dependency, Gradle change, engine wiring, or
      base URL; `contracts/`, `backend/`, land features, theme tokens, platform entry points, and `scripts/init.sh`
      are untouched.
- [ ] No question, payload, URL, land detail, or exception text is logged or displayed (grep evidence).
- [ ] Tests cover classification, retry-to-success, repeated failure, notice dismissal, and the timeout/error
      transport paths; `:shared:jvmTest`, `:shared:testAndroidHostTest`, and `./scripts/init.sh --verify` pass or the
      exact environment blocker is reported, with no E2E/UI-test claim.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning, and F2 is referenced as owned/closed
      here while F1 remains the `/ask` wiring slice's follow-up.

## Implementation findings

Recorded while implementing this spec; the acceptance scenarios and checklist are unchanged.

- **IF1 — the failure always keeps a retryable wording (spec transition rule refined).** The transition
  rules say `failedQuestion = submittedQuestion`, but the accepted `QuestionChanged` (and
  `SuggestedQuestionSelected`) clear `submittedQuestion` while the request is still `SUBMITTING`, so a
  draft typed — or an example picked — during the request would leave a failure with **no** retryable
  wording and the notice would offer no `Reintentar`. Implemented as
  `failedQuestion = submittedQuestion ?: messages.lastOrNull { it.speaker == USER }?.text`: during
  `SUBMITTING` the last user message *is* the wording this request sent, so the value is identical in the
  unchanged-composer case and the failure stays retryable and honest in the draft case. Covered by
  `ChatHomeStateTest.a failure does not overwrite a newly typed question` and
  `ChatConversationTest.a retry that fails again keeps one user message and stays retryable`.
  Consequence recorded: `RetryClicked` clears the composer (as specified), so a draft typed during the
  failed request and left unsent is discarded by an explicit retry; the person can instead press
  `Preguntar` with that draft, which dismisses the notice.
- **IF2 — an undecodable 2xx body is caught explicitly.** In Ktor 3.1.3 the content-negotiation failure is
  `io.ktor.serialization.JsonConvertException : ContentConvertException`, and `ContentConvertException`
  extends `java.lang.Exception`, **not** `kotlinx.serialization.SerializationException`. `KtorAnswerService`
  therefore catches `ContentConvertException` (and `SerializationException` for other paths) →
  `AnswerServiceErrorException`. Guarded by
  `KtorAnswerServiceTest.a 200 body that cannot be decoded fails instead of fabricating an answer`.
- **IF3 — the timeout probe used.** Ktor 3.1 exposes `HttpClient.plugin(HttpTimeout)` as
  `ClientPluginInstance<HttpTimeoutConfig>` with no public config accessor, so the installed request/connect/
  socket values cannot be read back. The timeout is therefore evidenced by (a) installation, where a missing
  plugin throws, (b) the three named constants being finite and different from
  `HttpTimeoutConfig.INFINITE_TIMEOUT_MS`, and (c) a stalled `MockEngine` driven in real time with
  `requestTimeoutMillis = 200`, which fails in ~0.3 s as `AnswerServiceUnavailableException` instead of
  hanging. Chosen bounds (planning defaults, U1): request `15_000` ms, connect `10_000` ms, socket
  `15_000` ms.
- **IF4 — `expectSuccess = true` verified by behaviour.** `KtorAnswerServiceTest` proves a `500` carrying
  the accepted `answered` fixture body and a declared `422` both fail as `AnswerServiceErrorException`, and
  that the existing `200` fixture still decodes on the same client.


## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/network_error_recovery.md. Failure state stays out of the transcript: pure ChatHomeState gains `failure: RequestFailure?` and `failedQuestion`, `RequestFailed(failure)` becomes parameterised, and a new `RetryClicked` re-emits `ChatEffect.Submit(failedQuestion)` from IDLE without appending a second user message; `QuestionChanged`/`SuggestedQuestionSelected`/`ResponseReceived`/`AskClicked` clear the notice.
- Transport parity: new shared chat/AnswerFailure.kt (`RequestFailure` enum plus payload-free `AnswerServiceUnavailableException`/`AnswerServiceErrorException`); `KtorAnswerService.ask` rethrows CancellationException and translates ResponseException/ContentConvertException/SerializationException to service error and kotlinx.io IOException (timeout/connect/socket) to unavailable; `answerHttpClient` installs a bounded `HttpTimeout` (named REQUEST_TIMEOUT_MILLIS 15_000, CONNECT_TIMEOUT_MILLIS 10_000, SOCKET_TIMEOUT_MILLIS 15_000) and `expectSuccess = true`; `ChatConversation` maps unavailable to COULD_NOT_REACH_SERVICE and every other exception (including UnavailableAnswerService) to SERVICE_ERROR, with no logging added.
- UI and copy: `App.kt` adds `ChatFailureNotice` rendered from `state.failure` (not a ChatMessage, no Asistente label, danger errorContainer/error/onErrorContainer roles only, polite live region, always-visible `Reintentar` dispatching RetryClicked) and two previews (unreachable; service error at widthDp=320/fontScale=2f); the three spec strings ship byte-for-byte verified in composeResources/values/strings.xml (chat_home_failure_unreachable, chat_home_failure_service, chat_home_retry) and chat_home_working, chat_home_question_too_long, chat_home_needs_land_clarification, chat_speaker_you/assistant and land_list_retry are unchanged.
- Commands actually run (all pass): python3 contracts/validate_examples.py -> "Validated 2 request and 3 response examples against answer_api_contract"; ./gradlew :shared:jvmTest --rerun-tasks -> 78 tests / 0 failures (ChatHomeStateTest 25, ChatConversationTest 7, KtorAnswerServiceTest 8 plus the 38 pre-existing); focused run of those three classes -> 40 tests / 0 failures; ./gradlew :shared:testAndroidHostTest -> 69 tests / 0 failures; ./gradlew :desktopApp:build, ./gradlew :androidApp:assembleDebug (androidApp-debug.apk rebuilt) and ./scripts/init.sh --verify -> BUILD SUCCESSFUL; ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL (the commonMain ktor/kotlinx-io change also compiles for iOS).
- New automated coverage: the two failure categories and their exact copy mapping; a stalled MockEngine with requestTimeoutMillis=200 fails in ~0.3 s as the unavailable signal instead of hanging; a 500 carrying the accepted answered fixture and a declared 422 are service errors, never answers; an undecodable 200 body is a service error; the installed HttpTimeout is asserted via client.plugin(HttpTimeout) plus finite named constants checked against HttpTimeoutConfig.INFINITE_TIMEOUT_MS; classification for unavailable/service error/unexpected/default wiring; retry-to-success yielding exactly one user message and one assistant message; a repeated failure staying retryable with one user message; retry non-actionable while in flight; dismissal by typing and by selecting an example; a decoded abstention never becoming a failure.
- Android emulator smoke (Medium_Phone_API_35, 1080x2400, debug APK, shipped default UnavailableAnswerService): selecting an example and pressing Preguntar shows one Tu bubble with the exact question, no Asistente answer, the service-error notice with the verbatim copy in the danger colours and a red Reintentar, and the exact wording still in the composer; Reintentar returns to the same single-notice state with still exactly one user message and no duplicate; selecting another example clears the notice and refills the composer. Screenshots were inspected and then deleted; no scripted UI-test harness exists.
- Privacy: grep -rn 'println|Log\.|Logger|printStackTrace|NSLog' shared/src androidApp/src desktopApp/src -> no matches (exit 1). The new failure signals are fixed-literal messages, so no question text, payload, URL, land detail or Ktor exception text is logged, shown or propagated; no network call other than the existing POST /ask was added.
- Not performed / honest gaps: a live network timeout cannot be produced in the running apps because no platform `/ask` engine/endpoint wiring exists (carried finding F1, separate owner), so the COULD_NOT_REACH_SERVICE notice has no on-device screenshot and is covered by the MockEngine probe plus the installed-constant assertions; the Desktop app launched with the shared UI (MainKt frontmost, no exception in the run log) but an interactive Desktop click-through/screenshot was not captured (non-interactive session); no Compose UI-test harness exists, so no automated UI or E2E coverage is claimed; the working indication during a retry is too brief to capture on the default path because UnavailableAnswerService throws synchronously.
- Implementation findings were appended to the spec: IF1 (failedQuestion falls back to the appended user message when a mid-flight draft cleared submittedQuestion, so a failure always stays retryable), IF2 (Ktor's ContentConvertException is not a SerializationException and needed its own catch), IF3 (the timeout probe used and why), IF4 (expectSuccess proven behaviourally). CONSTRAINTS.md gained the client MUST rule (a failed/unreached request is never an answer, recovery keeps the exact wording) and docs/specs/chat_question_submission.md records F2 as closed from this side with F1 still owned by the /ask wiring slice.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/network_error_recovery.md). It re-ran the acceptance checks with --rerun-tasks (contract validator; focused three-class run 40/0; :shared:jvmTest 78/0; :shared:testAndroidHostTest 69/0; :desktopApp:build; :androidApp:assembleDebug; :shared:compileKotlinIosSimulatorArm64; ./scripts/init.sh --verify exit 0) and independently reproduced the stalled-MockEngine request timeout (200 ms bound fired in 0.209 s as the unavailable signal), the 500/422 and undecodable-200 service-error paths with the 200 fixtures still decoding, byte-for-byte equality of the three spec strings, the failure-never-renders-as-an-answer invariant (failure lives outside messages; only ResponseReceived appends an ASSISTANT entry), retry with no duplicate user message and exact wording retention, and scope discipline (no new module/dependency/Gradle/contract/backend/land/theme/init.sh change). It confirmed on the resolved kotlinx-io-core-jvm artifact that catching kotlinx.io.IOException also catches java.io.IOException and its timeout subclasses, so real unreachable-service failures map to the correct notice, and found no leak (payload-free signals, no logging, no extra network call). Non-blocking findings N1-N5 recorded (state was set to passing before validation; connect/socket bounds asserted-finite only until F1 lands; RetryClicked discards a mid-flight draft per IF1; screen-reader/focus not independently exercised; Android smoke was implementer-recorded with no UI harness).
