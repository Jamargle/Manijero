# Feature Spec: `network_error_recovery`

## Source metadata

- **Feature:** `network_error_recovery` — Recover from service errors (`client`)
- **Status at planning:** `not_started` (2026-10-13); `depends_on: chat_question_submission`,
  `visual_foundation` (both accepted).
- **Source behavior:** If a request fails or the service is unavailable, the person sees a clear Spanish
  explanation and can retry without losing the question.
- **Source verification:** Simulate a timeout and a service error; confirm the question remains available
  and retry is clear.
- **Note carried from the feature list:** Do not describe a failed or offline request as an answered one.
- **Carried owner (validator finding F2, `docs/validations/chat_question_submission.md`):** the bounded
  Ktor `HttpTimeout` belongs to this feature, mapping the timeout to the existing failure transition.

## Goal and boundaries

Turn the two already-existing but invisible failure paths (transport exception, stall) into an honest,
recoverable state: one plain-Spanish explanation that the question was **not** answered, a one-tap
`Reintentar` that resends the exact original wording, and a bounded request timeout so the composer can
never stay stuck on "Estoy preparando la respuesta…". The accepted reducer already releases the request
and keeps the wording; this feature adds the visible copy, the retry action, and the timeout.

**In scope**

- A pure, shared failure state on the existing chat model: a bounded failure reason and the exact failed
  wording, kept out of the transcript so a failure can never be read as an assistant answer.
- A `RetryClicked` path that re-emits the existing `Submit` effect with the original wording, appends no
  second user message, and returns to the normal success/abstention flow.
- A danger-styled, plainly labelled failure notice with a visible `Reintentar` action, rendered from state
  (never appended as a `ChatMessage`), announced politely.
- Mapping transport failures to two honest categories: "could not reach the service" (timeout, connection,
  I/O) and "service error" (error status, unusable body, no service configured).
- Installing Ktor `HttpTimeout` (already available through `ktor-client-core`) with named bounded constants,
  and requiring non-2xx `/ask` responses to fail instead of decoding into an answer.
- Pure `commonTest` coverage for the new reducer/classification behavior and a MockEngine timeout/error test.

**Non-goals**

- No offline queue, background/automatic retry, exponential backoff, connectivity detection, caching, or
  "send when online"; retry is manual only.
- No change to the accepted `answered`/`abstained`/`needs_land_clarification` semantics or their eventual
  presentation (`response_states`); an abstention is an answer and must never be shown as a failure.
- No platform `/ask` wiring, Ktor engine dependency, or base-URL configuration. Validator finding F1 (the
  contract client is unreachable from the runnable apps) stays with the `/ask` wiring slice, not here.
- No new Gradle module, dependency, version, navigation, ViewModel, DI, or coroutine scope: `HttpTimeout`
  ships inside `ktor-client-core`.
- No change to the accepted API contract, backend, retrieval/generation, land features, theme tokens,
  platform entry points, `init.sh`, or Gradle files.
- No logging, printing, telemetry, or display of the question, request payload, URL, or exception text.

## Job story

When I ask a question and the service does not answer, I want to be told clearly, in words I understand,
that my question has not been answered yet and that my own words are still there, so I can simply try again
without typing it all over or believing I already got an answer.

## Acceptance scenarios

### A timeout or unreachable service is explained, not answered

Given I submitted `  ¿Puedo regar hoy?  ` and the service does not respond within the configured bound,
when the request fails, then the working indication stops, a plain-Spanish notice says the service could not
be reached and that there is no answer yet, exactly one user message (the original wording, spaces intact)
remains in the conversation, the wording is still in the composer, one `Reintentar` action is visible, and
**no assistant/answered message is added**.

### A service error is explained, not answered

Given the service answers with an error status (for example `500`, or a declared `400`/`422`) or with a
body that cannot be decoded into `AskResponse`, when the request fails, then the service-error notice and
`Reintentar` appear with the same guarantees as the timeout case and no partial or fabricated answer is
shown. The default no-endpoint wiring (`UnavailableAnswerService`) follows this same path.

### Retry keeps the question and cannot duplicate it

Given either failure notice is shown, when I select `Reintentar` and the service then returns a valid
response, then exactly one new `POST /ask` is sent with the same original wording, the notice disappears,
the transcript holds **one** user message and **one** assistant message, and the composer returns to idle.

### Retrying can fail again safely

Given the notice is shown, when `Reintentar` fails again, then the same notice returns, the transcript still
holds exactly one user message for that question, and `Reintentar` is offered again; no duplicate user
messages or assistant answers accumulate. While a retry is in flight, `Reintentar` is not actionable.

### A real answer or abstention is never shown as a failure

Given the service returns a contract-valid `answered` or `abstained` response, when it arrives, then no
failure notice appears, and `abstained` keeps its own status for `response_states` (this feature reacts only
to thrown failures, never to a decoded `AskResponse`).

### The composer cannot stay submitting forever

Given the service stalls, when the bounded timeout elapses, then the phase leaves `SUBMITTING` without any
user action and the unreachable notice is shown.

### Typing again dismisses the old failure

Given the notice is shown, when I edit the composer or pick an example question, then the notice and its
retained wording are cleared and `Preguntar` behaves normally for the new wording.

### Nothing leaks

Given any failure, when it is handled, then no question text, payload, URL, land detail, or exception
message is logged, printed, or shown, and no network call other than the existing `POST /ask` is made.

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

## Technical approach

1. **Failure reason and wording in the pure state.** Extend `ChatHomeState` with
   `failure: RequestFailure? = null` and `failedQuestion: String? = null`; change
   `data object RequestFailed` to `data class RequestFailed(val failure: RequestFailure)`. Keep the failure
   **out of** `messages` so it can never render as an assistant answer. `RequestFailure` is a small closed
   enum owned by the transport package:

   ```kotlin
   enum class RequestFailure { COULD_NOT_REACH_SERVICE, SERVICE_ERROR }
   ```

2. **Transitions (all pure, all guarded by the current phase).**
   - `RequestFailed(kind)` (only from `SUBMITTING`): `phase = IDLE`, `failure = kind`,
     `failedQuestion = submittedQuestion`, `submittedQuestion = null`, and
     `question = question.ifBlank { failedQuestion.orEmpty() }` so an unchanged composer regains the wording
     while a draft typed during the request is preserved (both behaviors already covered by tests).
   - `RetryClicked` (only when `phase == IDLE && failure != null && failedQuestion != null`): re-emit
     `ChatEffect.Submit(failedQuestion)`, set `phase = SUBMITTING`, clear `failure`/`question`, and leave
     `messages` and `failedQuestion` untouched, so the retry adds no second user message and a repeated
     failure can be retried again.
   - `AskClicked` (already clears status fields) also clears `failure`/`failedQuestion`.
   - `ResponseReceived` clears `failure`/`failedQuestion`; `QuestionChanged` and `SuggestedQuestionSelected`
     clear them too, so a new draft or example dismisses a stale notice.
   - `canAsk`, `isOverCharacterLimit`, and `awaitingLandClarification` keep their current meaning.

3. **Two shared failure signals, no transport types in the state layer.** Add to the `chat` package two
   payload-free exceptions (`AnswerServiceUnavailableException`, `AnswerServiceErrorException`).
   `KtorAnswerService.ask` translates transport failures into them: Ktor I/O and timeout exceptions
   (`kotlinx.io.IOException` and its subclasses such as `HttpRequestTimeoutException`,
   `ConnectTimeoutException`, `SocketTimeoutException`) → unavailable; `ResponseException` (from
   `expectSuccess`) and `SerializationException` → service error; `CancellationException` is rethrown first.
   The messages carry no URL, body, or question text. `ChatConversation` then maps:
   `AnswerServiceUnavailableException → RequestFailed(COULD_NOT_REACH_SERVICE)`, any other exception
   (including `UnavailableAnswerService`'s `IllegalStateException`) → `RequestFailed(SERVICE_ERROR)`, and
   rethrows `CancellationException`. No logging is added.

4. **Bounded timeout (finding F2).** `answerHttpClient(engine, requestTimeoutMillis = REQUEST_TIMEOUT_MILLIS)`
   installs `HttpTimeout` with named constants — request/connect/socket bounds — so no request can hang
   forever; the optional parameter exists only so tests can use a tiny bound. Set `expectSuccess = true` on
   the client so a non-2xx `/ask` surfaces as a failure rather than being decoded. Confirm that the accepted
   `200` fixtures still decode and that tests using `MockEngine` return `200`.

5. **Failure notice UI.** In `ChatHomeScreen`, when `state.failure != null`, render a dedicated
   `ChatFailureNotice` (not `ChatMessageBubble`, no `Asistente`/`Tú` label) after the transcript: a
   `surface`/`errorContainer` card with an `outline`-or-`error` border, the message text, and a
   `Reintentar` `Button` that dispatches `ChatHomeAction.RetryClicked`; the container is a
   `LiveRegionMode.Polite` region and the message maps from `RequestFailure` to a string resource. The
   working indication and the notice are mutually exclusive (`SUBMITTING` vs `failure != null`). Add one or
   two previews (failure notice, and failure at `widthDp = 320`, `fontScale = 2f`), all inside
   `ManijeroTheme`.

### Copy contract (ship verbatim)

Plain Spanish, established tú voice; the failure text must never read like an answer.

| Key | Text | Used for |
|---|---|---|
| `chat_home_failure_unreachable` | `No se ha podido conectar con el servicio, así que todavía no tengo tu respuesta. Comprueba tu conexión e inténtalo otra vez.` | timeout, connection, I/O failure |
| `chat_home_failure_service` | `El servicio no está disponible en este momento, así que todavía no tengo tu respuesta. Inténtalo otra vez dentro de un momento.` | error status, unusable body, no service configured |
| `chat_home_retry` | `Reintentar` | the retry action in the notice |

Reuse `chat_speaker_you`/`chat_speaker_assistant` for existing bubbles; do not delete
`chat_home_working`, `chat_home_question_too_long`, or `chat_home_needs_land_clarification`. `chat_home_retry`
carries the same word as `land_list_retry` but keeps a chat-scoped key so the chat screen does not depend on
land naming.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: add `RequestFailure`
  import/field, `failedQuestion`, `RetryClicked`, and the transition rules. Keep the file Compose-free.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`: classify the thrown
  failure into `RequestFailed(kind)`; keep the `CancellationException` rethrow; add no logging.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` (or a new
  `chat/AnswerFailure.kt` in the same package): the `RequestFailure` enum, the two payload-free exceptions,
  `HttpTimeout` + `expectSuccess` in `answerHttpClient`, and their named constants.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the `ChatFailureNotice`
  composable, its wiring in `ChatHomeScreen`, and preview(s).
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the three strings above.
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatHomeStateTest.kt`: the two existing
  `RequestFailed` calls now pass a kind, plus new failure/retry cases.
- **Update/add tests** `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatConversationTest.kt`
  (classification and retry-through-success/no-duplicate) and
  `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/KtorAnswerServiceTest.kt` (timeout, error status,
  malformed body).
- **Update** `CONSTRAINTS.md` during implementation with one short client rule (see durable docs).
- **Do not modify** `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`,
  `shared/src/iosMain/`, `theme/`, any Gradle file or the version catalog, `init.sh`, or
  `feature_list.json`/`PROGRESS.md` while implementing.

## Visual and accessibility impact

Reuse `ManijeroTheme` roles only: `errorContainer` fill with `onErrorContainer` text (the tested danger
pair), or `surface` with an `error` border, plus `error` for the retry emphasis; no raw colors, icons, or
new tokens. The failure is communicated by text ("(todavía no tengo tu respuesta)") plus the always-visible
`Reintentar` label, never by color alone; the transcript keeps its textual `Tú`/`Asistente` labels.
`Reintentar` is a normal Material control (48dp minimum, visible focus on Desktop, keyboard reachable) and
the notice is a polite live region so a screen reader announces the failure. Long text wraps without
clipping and the screen still scrolls vertically. Known limit (owner `chat_accessibility`, carried finding
F3): the transcript has no auto-scroll, so on a long conversation the notice may sit below the fold; the
composer regains the wording, so the question is never lost, but visible auto-scroll is out of scope here.

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
./init.sh --verify
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
`HttpTimeout`/`expectSuccess` assertion and the `500`-not-an-answer test; `./init.sh --verify` output (or the
exact blocker); a Desktop/Android screenshot or short record of the notice and `Reintentar`; and
`grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src` with no
matches.

## Durable documentation impact

- `CONSTRAINTS.md`: **update during implementation** — one short client rule that a request which failed or
  never reached the service MUST NOT be rendered as an answer, and recovery MUST keep the original wording.
  Reason: `response_states` and `answer_source_cards` will render this transcript next and could otherwise
  regress the invariant.
- `DESIGN.md`: **not needed** — lines 76-77 already mandate preserving entered data, a waiting state, and a
  simple retry; this implements them.
- `docs/risks-and-open-questions.md`: **not needed** — no open question is settled or created; the F1 gap is
  recorded in `feature_list.json`/`PROGRESS.md` and owned elsewhere.
- `ARCHITECTURE.md`: **not needed** — it does not exist; this adds no module or architectural boundary.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`: **not needed** — no product,
  glossary, or domain change.
- `init.sh`: **not needed** — it must not gain modes and must not start a service.
- `feature_list.json`, `PROGRESS.md`, `docs/specs/chat_question_submission.md`: **after verified
  implementation only** — record evidence/status then, and reference F2 as closed from this side.

## Risks and open decisions

- **R1 Timeout testability:** Ktor `HttpTimeout` under `MockEngine`/`runTest` may not be driven by virtual
  time. The fallback in the verification plan (classification seam test + installed-constant assertion) is
  acceptable; do not drop the timeout requirement.
- **R2 F1 wiring gap:** with no platform `/ask` wiring, a live timeout cannot be hand-produced and the
  default path always shows the service-error notice. Report this limitation instead of implying an
  end-to-end network smoke; the success path is proven by reducer/transport tests.
- **R3 Two retry affordances:** after a failure the composer regains the wording (accepted behavior,
  validated in F4) **and** the notice offers `Reintentar`; both are intentional. `RetryClicked` must not
  append a second user message, while a fresh `Preguntar` press legitimately starts a new attempt.
- **R4 `expectSuccess = true`:** changes transport semantics so `400`/`422`/`5xx` become failures. Confirm
  the accepted `200` fixtures still decode and no existing MockEngine test relied on a non-2xx body.
- **R5 Keep the failure out of `messages`:** rendering the notice from `state.failure` is the structural
  guarantee that a failure cannot be read as an answer; do not "simplify" it into a `ChatMessage`.
- **U1 Timeout values:** the named bounds are planning defaults; adjust them during implementation with a
  recorded reason if a real `/ask` needs longer, but keep them bounded and named.
- **U2 Cause honesty:** the app cannot reliably distinguish "no connection" from "server down", so the two
  messages avoid asserting a cause beyond reachability; do not add stronger claims such as "estás sin
  conexión".
- **U3 Notice visibility:** with no auto-scroll, the notice can be below the fold in a long conversation
  (owner `chat_accessibility`, F3); the wording stays in the composer, so nothing is lost.

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
      base URL; `contracts/`, `backend/`, land features, theme tokens, platform entry points, and `init.sh`
      are untouched.
- [ ] No question, payload, URL, land detail, or exception text is logged or displayed (grep evidence).
- [ ] Tests cover classification, retry-to-success, repeated failure, notice dismissal, and the timeout/error
      transport paths; `:shared:jvmTest`, `:shared:testAndroidHostTest`, and `./init.sh --verify` pass or the
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


## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests KtorAnswerServiceTest --tests ChatHomeStateTest --tests ChatConversationTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/network_error_recovery.md. Failure state stays out of the transcript: pure ChatHomeState gains `failure: RequestFailure?` and `failedQuestion`, `RequestFailed(failure)` becomes parameterised, and a new `RetryClicked` re-emits `ChatEffect.Submit(failedQuestion)` from IDLE without appending a second user message; `QuestionChanged`/`SuggestedQuestionSelected`/`ResponseReceived`/`AskClicked` clear the notice.
- Transport parity: new shared chat/AnswerFailure.kt (`RequestFailure` enum plus payload-free `AnswerServiceUnavailableException`/`AnswerServiceErrorException`); `KtorAnswerService.ask` rethrows CancellationException and translates ResponseException/ContentConvertException/SerializationException to service error and kotlinx.io IOException (timeout/connect/socket) to unavailable; `answerHttpClient` installs a bounded `HttpTimeout` (named REQUEST_TIMEOUT_MILLIS 15_000, CONNECT_TIMEOUT_MILLIS 10_000, SOCKET_TIMEOUT_MILLIS 15_000) and `expectSuccess = true`; `ChatConversation` maps unavailable to COULD_NOT_REACH_SERVICE and every other exception (including UnavailableAnswerService) to SERVICE_ERROR, with no logging added.
- UI and copy: `App.kt` adds `ChatFailureNotice` rendered from `state.failure` (not a ChatMessage, no Asistente label, danger errorContainer/error/onErrorContainer roles only, polite live region, always-visible `Reintentar` dispatching RetryClicked) and two previews (unreachable; service error at widthDp=320/fontScale=2f); the three spec strings ship byte-for-byte verified in composeResources/values/strings.xml (chat_home_failure_unreachable, chat_home_failure_service, chat_home_retry) and chat_home_working, chat_home_question_too_long, chat_home_needs_land_clarification, chat_speaker_you/assistant and land_list_retry are unchanged.
- Commands actually run (all pass): python3 contracts/validate_examples.py -> "Validated 2 request and 3 response examples against answer_api_contract"; ./gradlew :shared:jvmTest --rerun-tasks -> 78 tests / 0 failures (ChatHomeStateTest 25, ChatConversationTest 7, KtorAnswerServiceTest 8 plus the 38 pre-existing); focused run of those three classes -> 40 tests / 0 failures; ./gradlew :shared:testAndroidHostTest -> 69 tests / 0 failures; ./gradlew :desktopApp:build, ./gradlew :androidApp:assembleDebug (androidApp-debug.apk rebuilt) and ./init.sh --verify -> BUILD SUCCESSFUL; ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL (the commonMain ktor/kotlinx-io change also compiles for iOS).
- New automated coverage: the two failure categories and their exact copy mapping; a stalled MockEngine with requestTimeoutMillis=200 fails in ~0.3 s as the unavailable signal instead of hanging; a 500 carrying the accepted answered fixture and a declared 422 are service errors, never answers; an undecodable 200 body is a service error; the installed HttpTimeout is asserted via client.plugin(HttpTimeout) plus finite named constants checked against HttpTimeoutConfig.INFINITE_TIMEOUT_MS; classification for unavailable/service error/unexpected/default wiring; retry-to-success yielding exactly one user message and one assistant message; a repeated failure staying retryable with one user message; retry non-actionable while in flight; dismissal by typing and by selecting an example; a decoded abstention never becoming a failure.
- Android emulator smoke (Medium_Phone_API_35, 1080x2400, debug APK, shipped default UnavailableAnswerService): selecting an example and pressing Preguntar shows one Tu bubble with the exact question, no Asistente answer, the service-error notice with the verbatim copy in the danger colours and a red Reintentar, and the exact wording still in the composer; Reintentar returns to the same single-notice state with still exactly one user message and no duplicate; selecting another example clears the notice and refills the composer. Screenshots were inspected and then deleted; no scripted UI-test harness exists.
- Privacy: grep -rn 'println|Log\.|Logger|printStackTrace|NSLog' shared/src androidApp/src desktopApp/src -> no matches (exit 1). The new failure signals are fixed-literal messages, so no question text, payload, URL, land detail or Ktor exception text is logged, shown or propagated; no network call other than the existing POST /ask was added.
- Not performed / honest gaps: a live network timeout cannot be produced in the running apps because no platform `/ask` engine/endpoint wiring exists (carried finding F1, separate owner), so the COULD_NOT_REACH_SERVICE notice has no on-device screenshot and is covered by the MockEngine probe plus the installed-constant assertions; the Desktop app launched with the shared UI (MainKt frontmost, no exception in the run log) but an interactive Desktop click-through/screenshot was not captured (non-interactive session); no Compose UI-test harness exists, so no automated UI or E2E coverage is claimed; the working indication during a retry is too brief to capture on the default path because UnavailableAnswerService throws synchronously.
- Implementation findings were appended to the spec: IF1 (failedQuestion falls back to the appended user message when a mid-flight draft cleared submittedQuestion, so a failure always stays retryable), IF2 (Ktor's ContentConvertException is not a SerializationException and needed its own catch), IF3 (the timeout probe used and why), IF4 (expectSuccess proven behaviourally). CONSTRAINTS.md gained the client MUST rule (a failed/unreached request is never an answer, recovery keeps the exact wording) and docs/specs/chat_question_submission.md records F2 as closed from this side with F1 still owned by the /ask wiring slice.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/network_error_recovery.md). It re-ran the acceptance checks with --rerun-tasks (contract validator; focused three-class run 40/0; :shared:jvmTest 78/0; :shared:testAndroidHostTest 69/0; :desktopApp:build; :androidApp:assembleDebug; :shared:compileKotlinIosSimulatorArm64; ./init.sh --verify exit 0) and independently reproduced the stalled-MockEngine request timeout (200 ms bound fired in 0.209 s as the unavailable signal), the 500/422 and undecodable-200 service-error paths with the 200 fixtures still decoding, byte-for-byte equality of the three spec strings, the failure-never-renders-as-an-answer invariant (failure lives outside messages; only ResponseReceived appends an ASSISTANT entry), retry with no duplicate user message and exact wording retention, and scope discipline (no new module/dependency/Gradle/contract/backend/land/theme/init.sh change). It confirmed on the resolved kotlinx-io-core-jvm artifact that catching kotlinx.io.IOException also catches java.io.IOException and its timeout subclasses, so real unreachable-service failures map to the correct notice, and found no leak (payload-free signals, no logging, no extra network call). Non-blocking findings N1-N5 recorded (state was set to passing before validation; connect/socket bounds asserted-finite only until F1 lands; RetryClicked discards a mid-flight draft per IF1; screen-reader/focus not independently exercised; Android smoke was implementer-recorded with no UI harness).
