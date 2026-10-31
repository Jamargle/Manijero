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
  platform entry points, `scripts/init.sh`, or Gradle files.
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
  `shared/src/iosMain/`, `theme/`, any Gradle file or the version catalog, `scripts/init.sh`, or
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
- `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`: **not needed** — no product,
  glossary, or domain change.
- `scripts/init.sh`: **not needed** — it must not gain modes and must not start a service.
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

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests KtorAnswerServiceTest --tests ChatHomeStateTest --tests ChatConversationTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/network_error_recovery.appendix.md`](../archive/specs/network_error_recovery.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/network_error_recovery.md` remains the authoritative acceptance record.
