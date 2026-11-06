# Mark an answer as useful or not useful

## Source metadata

- `id`: answer_feedback_ui · `area`: client · `depends_on`: feedback_endpoint, chat_screen_refresh · `status` at planning: not_started
- User-visible behavior: every finished answer in the shared chat carries two plain-Spanish controls, `Útil` and `No útil`, that post only the chosen rating to `POST /feedback`; a success shows `Gracias, tu respuesta nos ayuda a mejorar.` and locks that answer, a failure shows a retry line and keeps both controls enabled.
- Verification: shared reducer, transport and UI-interaction tests, the two targeted chat pixel suites, and scope gates; commands are in Focused verification.
- Notes:
  - **Owner decisions (2026-11-06, binding).** Add a two-button control under each finished answer in the shared chat: `Útil` and `No útil`, plain Spanish, no comments or free text and no question/answer/land/identifier sent. Sending posts only `{rating}` to the existing `POST /feedback` through the pilot-token transport, with the same https/loopback rule. After a successful send show `Gracias, tu respuesta nos ayuda a mejorar.` and keep the chosen rating locked for that answer; a failed send shows a plain retry message and leaves both buttons enabled. Accessible labels, 48 dp touch targets, no colour-only state. Do not change the mock answer service; local/QA test builds talk to the real service. Acceptance: validator accept is final, no owner walkthrough.
  - Planning: "finished answer" is every completed `Asistente` entry that is a decoded answer (`answered` or `abstained`). The working notice, the failure notice, the clarification chooser and the dev-only `Inspeccionar` link get no rating. Placement is the last product element of the answer block — after the answer card and its source cards, before `Inspeccionar`.
  - Planning: a successful send replaces the two controls with the confirmation line — the lock is met by leaving nothing to tap, without an "elegido" marker, checkmark or colour-only cue on an answer. While the request is in flight both controls are disabled, so one answer cannot be counted twice (`feedback_endpoint` has no idempotency). A failure keeps both enabled, so the person may retry either rating; an accepted retry counts again on the service.
  - Planning copy: retry line `No se ha podido enviar tu valoración. Inténtalo otra vez.`; accessible names `Marcar esta respuesta como útil` / `Marcar esta respuesta como no útil`, with the visible labels staying `Útil` / `No útil`. No other visible copy is added.
  - Planning: the rating lives in memory with the transcript. Nothing is persisted, logged, or linked to an answer id, and reopening the app forgets the lock.

## Goal

Let a person tell the owner, in one tap and in plain Spanish, whether one answer helped, while sending no question, answer, land or identifier — and keep that answer honestly marked so the same rating is not offered twice.

## Non-goals

- Free-text comments, a "why" question, thumbs/topics, per-person tracking, analytics, export, a dashboard (the later dashboard reads the existing metric) or durable feedback storage.
- Sending any answer id, question, answer text, land value, citation, device or client identifier, or a second field besides `rating`.
- Changing `backend/`, `contracts/`, `knowledge/`, the test-only mock answer service, the `/ask` request or response, or the pilot-token rules themselves.
- Asking for feedback on a failure, while an answer is still being prepared, on the clarification chooser, or on the dev-only `Inspeccionar` flow; changing the `Preguntar` action, the retention checkbox, suggestions, source cards or the failure/retry contract.
- Persisting the rating on the device, carrying it across app restarts, or claiming the pending privacy review covers it.
- Owner walkthrough or a new owner command; the owner asked for none.

## Job story

When I finish reading an answer, I want to tap one obvious control that tells Manijero whether it helped, so I feel heard and the app gets better without me writing anything or handing over my question.

## Acceptance Scenarios

### 1. Both controls sit under every finished answer

Given a transcript with an `answered` entry and an `abstained` entry · When the chat renders · Then each of those two entries shows `Útil` and `No útil` as two visible, named, 48 dp controls below the entry (after its source cards, when it has any) and before `Inspeccionar`; an empty transcript, the working notice, a failure notice, the clarification chooser and a user entry show none.

### 2. Only the rating leaves the app

Given any finished answer · When the person taps `Útil` (or `No útil`) · Then exactly one `POST /feedback` is sent to the address that `/ask` uses, with a JSON body whose only key is `rating` (`"useful"` / `"not_useful"`) and no question, answer, land, source, index, device or client value; the request carries the pilot bearer token only when that address is `https` or loopback `http`, exactly like `/ask`.

### 3. A successful send is confirmed and locked

Given the send is accepted (`204`) · When the response arrives · Then that answer replaces the two controls with `Gracias, tu respuesta nos ayuda a mejorar.`, no control remains for it so the rating cannot change, no second request is sent for it, and every other answer, the composer and the next question behave exactly as before.

### 4. A failed send is honest and retryable

Given the service is unreachable or answers with an error · When the send fails · Then that answer keeps both controls enabled and shows `No se ha podido enviar tu valoración. Inténtalo otra vez.`; no transcript entry, failure notice or composer change is produced, nothing is claimed as counted, and tapping either control again sends one new request.

### 5. One tap, one request

Given a send is in flight · When the person taps the same or the other control · Then no second request starts (both controls are disabled until the answer's own result arrives) and the rest of the screen keeps working.

### 6. The rest of the surface is untouched

Given the restyled chat · When a rating is shown, sent, or fails · Then speaker labels, scope captions, citation numerals, source cards, merged live regions, the `Inspeccionar` node, the polite announcement of a new entry, the retry split, the scroll key and the composer keep their accepted behavior, and no answer gains a badge, checkmark, success colour or "verificado" cue.

### 7. Accessible and not colour-only

Given any rating state · When a person uses large text, a keyboard or a screen reader · Then each control has its own accessible name, its own focusable node with visible focus, a target of at least 48 dp, wraps instead of clipping at 2× text, and every state (enabled, in flight, failed, confirmed) is readable from text or semantics rather than colour alone.

### 8. In-memory, unlinked, and no mock change

Given a rated answer · When the app is restarted, the transcript is replayed in a test, or the mock answer service is used · Then no rating was persisted, logged, or sent with an identifier; `shared/src/jvmTest/.../mock` still serves only its existing examples, so a rating against the mock fails with the retry line instead of pretending to be counted.

## Technical approach

- **Transport** (`chat/AnswerService.kt`): add `@Serializable enum class AnswerRating { @SerialName("useful") USEFUL, @SerialName("not_useful") NOT_USEFUL }` and `@Serializable data class FeedbackRequest(val rating: AnswerRating)` (one field, no defaults). Add `suspend fun sendFeedback(rating: AnswerRating)` to `AnswerService` with a default body that throws `AnswerServiceUnavailableException()` (so fakes and `UnavailableAnswerService` keep compiling and report failure honestly). `KtorAnswerService` overrides it: resolve `"${baseUrl().trimEnd('/')}/feedback"` per call, JSON content type, `Authorization` only when `pilotToken != null && mayCarryPilotToken(Url(url))`, reuse the existing `expectSuccess` client and timeout policy, accept any `2xx` (no body decoded), map failures exactly like `ask` (`ResponseException`/serialization → `AnswerServiceErrorException`, `IOException` → `AnswerServiceUnavailableException`, `CancellationException` rethrown). No logging, no URL or body in any message.
- **State** (`ChatHomeState.kt`): add `sealed interface AnswerFeedback { None; Sending(rating); Sent(rating); Failed(rating) }` and `ChatMessage.feedback: AnswerFeedback = AnswerFeedback.None` (a new defaulted field keeps existing transcript assertions equal). Add actions `FeedbackClicked(messageIndex, rating)`, `FeedbackReceived(messageIndex, rating)`, `FeedbackFailed(messageIndex, rating)` — indices are safe because transcript entries are append-only.
- **Effects** (`ChatHomeState.kt`): keep `Submit`/`SubmitSelected` unchanged but move their `question`/`retainForImprovement` members to a `QuestionEffect : ChatEffect` sub-interface (so `QuestionEffect.request(lands)` stays byte-identical), and add `data class SendFeedback(val messageIndex: Int, val rating: AnswerRating) : ChatEffect`.
- **Reducer**: `FeedbackClicked` copies only that entry to `Sending(rating)` and returns `SendFeedback` when the entry is an assistant `answered`/`abstained` entry whose feedback is `None` or `Failed`; otherwise it is identity with no effect. `FeedbackReceived`/`FeedbackFailed` only accept an entry currently `Sending` the same rating and set `Sent`/`Failed`. Nothing else in the state changes.
- **Conversation** (`ChatConversation.kt`): handle `SendFeedback` by launching `answerService.sendFeedback(rating)` on the existing scope and dispatching `FeedbackReceived`/`FeedbackFailed`; a failure is never logged or surfaced as text from the exception. The send is independent of `phase`, the composer, `failure` and `clarificationQuestion`.
- **UI**: new `chat/AnswerFeedback.kt` with `internal fun AnswerFeedbackControl(feedback, onRating, modifier)`; rendered by `ChatMessageBubble` as a sibling below the card/sources and above `InspectLink`, never inside the card's merged live region. `ChatHomeScreen` passes the entry index through `forEachIndexed` and an `onFeedback` lambda; `ChatMessageBubble` gains `index` and `onFeedback` parameters. Use `FlowRow` + two `OutlinedButton`s (`heightIn(min = ManijeroLayout.MinTouchTarget)`, `Modifier.semantics { contentDescription = … }`, `Modifier.testTag(...)`), a `bodyMedium`/`onSurfaceVariant` `Text` for the confirmation or retry line, `stringResource` for every visible string, and no new icon, colour, shape or spacing literal.
- **Tests**: exact wire body and token rule in `KtorAnswerServiceTest` (MockEngine), reducer rules in a new common test, conversation dispatch in `ChatConversationTest`, control behavior in `ChatHomeInteractionTest`, and pixel evidence in the two chat screenshot classes.

## Expected file changes

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` — modify; rating enum, request DTO, `sendFeedback` contract and `KtorAnswerService` override.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt` — modify; `AnswerFeedback`, `ChatMessage.feedback`, three actions, `QuestionEffect`/`SendFeedback`, reducer.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt` — modify; run `SendFeedback`, dispatch its result.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerFeedback.kt` — create; the control and its confirmation/retry line.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatTranscript.kt` — modify; `index`/`onFeedback` parameters and the sibling control under `answered` and `abstained`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatHomeScreen.kt` — modify; `forEachIndexed` and the `onFeedback` wiring.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatTestTags.kt` — modify; tags for the two controls and the confirmation (applied only through `Modifier.testTag`).
- `shared/src/commonMain/composeResources/values/strings.xml` — modify; six `chat_feedback_*` keys (two labels, two accessible names, confirmation, retry).
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/AnswerFeedbackStateTest.kt` — create; reducer rules.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/screenshots/ScreenshotFixtures.kt` — modify; a sent-rating fixture.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/KtorAnswerServiceTest.kt` — modify; exact feedback body, token rule, failure mapping.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatConversationTest.kt`, `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/ChatHomeInteractionTest.kt` — modify; effect dispatch and control behavior.
- `shared/src/jvmTest/.../screenshots/ChatHomeScreenshotsTest.kt`, `shared/src/androidHostTest/.../ChatHomeAndroidScreenshotsTest.kt` — modify; one new `chat_feedback_sent_dark` capture per host.
- `shared/src/jvmTest/screenshots/`, `shared/src/androidHostTest/screenshots/` — replace the answered/abstained chat goldens the new row changes; add `chat_feedback_sent_dark.png` on both hosts.
- Docs: `DESIGN.md`, `ARCHITECTURE.md`, `docs/constraints/client-chat.md`, `docs/screenshot-regression.md`, `docs/progress/known-limitations.md` — see below.
- Not changed: `App.kt`, platform entry points, `backend/`, `contracts/`, `knowledge/`, `shared/src/jvmTest/.../mock/`, `design/` and `theme/` tokens, `docs/owner-guide.md`, `backend/README.md`.

## Visual design impact

UI involved: yes — the assistant surface (`DESIGN.md` "Assistant surface (adopted 2026-10-25)"). Each finished answer gains one quiet row: two neutral outlined buttons, `Útil` and `No útil`, under the answer and its sources; after a successful send the row is the single `bodyMedium` line `Gracias, tu respuesta nos ayuda a mejorar.`; after a failure the row keeps both buttons with the retry line beneath. The row is calmer than `Preguntar` (never filled, never the screen's primary action), adds no icon, badge, checkmark or success/eco colour, wraps at 2× text and stays inside the existing 720 dp column and section spacing. The compact-screen limit recorded for the composer grows by one short row per answer; no new screen.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — the pilot-token sentence now allows `POST /ask` and `POST /feedback`; one line states the shared transport sends a one-field rating and keeps it unlinked.
- `docs/constraints/client-chat.md`: update — one MUST block: only `rating` may be sent, no answer/question/land/id/free text, the control never blocks asking, success locks the answer, failure keeps both enabled, 48 dp and non-colour-only state.
- `DESIGN.md`: update — the assistant-surface feedback row: placement, the two plain labels, the confirmation and retry copy, no checkmark/colour-only marking.
- `docs/screenshot-regression.md`: update — the chat row and the host totals after recording, and the note that the answered/abstained chat goldens changed by intent.
- `docs/progress/known-limitations.md`: update — one line: anonymous unlinked in-memory rating, per-process counts, no persistence across restarts, mock service has no `/feedback`.
- `AGENTS.md`, `docs/owner-guide.md`, `backend/README.md`, `docs/pilot-privacy.md`, `docs/risks-and-open-questions.md`: not needed — no workflow change, no owner command or walkthrough (owner decision), the endpoint is already documented and the privacy row already names the rating.

## Focused verification (required)

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests 'com.jamarglex.manijero.AnswerFeedbackStateTest' --tests 'com.jamarglex.manijero.ChatConversationTest' --tests 'com.jamarglex.manijero.chat.KtorAnswerServiceTest' --tests 'com.jamarglex.manijero.chat.ChatHomeInteractionTest' --tests 'com.jamarglex.manijero.platform.LocalSmokeGuardTest'
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeScreenshotsTest'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeAndroidScreenshotsTest'
root="$REPO_ROOT/shared/src/commonMain"
strings="$root/composeResources/values/strings.xml"
for key in chat_feedback_useful chat_feedback_not_useful chat_feedback_thanks chat_feedback_failed chat_feedback_useful_description chat_feedback_not_useful_description; do
  grep -q "name=\"$key\"" "$strings" || { echo "missing string: $key" >&2; exit 1; }
done
test -f "$root/kotlin/com/jamarglex/manijero/chat/AnswerFeedback.kt" || { echo "missing chat/AnswerFeedback.kt" >&2; exit 1; }
if grep -rln 'sendFeedback' "$root" --include='*.kt' | grep -vE 'chat/AnswerService.kt|ChatConversation.kt'; then
  echo "sendFeedback is reached outside the shared transport and conversation" >&2; exit 1
fi
if grep -rn 'feedback' "$REPO_ROOT/shared/src/jvmTest/kotlin/com/jamarglex/manijero/mock"; then
  echo "the test-only mock answer service must not gain feedback behavior" >&2; exit 1
fi
for shot in chat_feedback_sent_dark; do
  test -f "$REPO_ROOT/shared/src/jvmTest/screenshots/$shot.png" || { echo "missing Desktop golden: $shot" >&2; exit 1; }
  test -f "$REPO_ROOT/shared/src/androidHostTest/screenshots/$shot.png" || { echo "missing Android golden: $shot" >&2; exit 1; }
done
if grep -rnE 'Color\(0x|#[0-9A-Fa-f]{3,8}' "$root/kotlin/com/jamarglex/manijero/chat/AnswerFeedback.kt"; then
  echo "raw colour literal in the feedback control" >&2; exit 1
fi
```
<!-- verify:end -->

The block proves the wire body and token rule, the reducer and conversation behavior, the control's semantics and interactions, pixel stability of both chat suites (the Android suite needs an Android SDK, not a device), and the scope gates (no mock change, no second call site, no raw colour). It cannot judge whether the row reads as an invitation at phone width with 2× text, how a screen reader announces the two names in context, real-device behavior, or a live rating against the owner's service; those remain unverified and are recorded as such.

## Appendix

See [`answer_feedback_ui.appendix.md`](answer_feedback_ui.appendix.md) for research, the ordered plan, evidence to capture and the validator checklist.
