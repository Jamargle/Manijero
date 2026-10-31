# Feature Spec: `chat_question_submission`

## Source metadata

- **Feature:** `chat_question_submission` — Submit a chat question
- **Status at planning:** `not_started`
- **Depends on:** `chat_home`, `answer_api_contract`, `backend_health` (all accepted)
- **Source behavior:** A person enters a question, submits it once, sees that the
  assistant is working, and receives the service response in the conversation.
- **Source verification:** Submit a question to a local or mocked service and confirm the response appears once in the conversation.
- **Note from the feature list:** Preserve the user's original wording.

## Goal

Turn the existing chat-home composer into a single-question chat flow. Preserve the
user's exact non-blank wording, submit one `general` request to the contract-defined
`POST /ask` boundary, prevent duplicate in-flight sends, visibly communicate progress
in Spanish, and append the returned assistant content exactly once.

## Non-goals

- Implementing `POST /ask`, retrieval, generation, corpus validation, or changing
  backend health. The current backend deliberately exposes only `GET /health`.
- Sending land records or selecting a land; `minimal_land_context` owns that work.
- Distinct answered/abstained presentation, source cards, land-selection UI, or
  response-policy wording; these belong to `response_states` and later features.
- Error explanation and retry behavior; `network_error_recovery` owns failures after
  this slice establishes the request boundary.
- Conversation persistence, account/cloud sync, telemetry, suggested prompts, or
  navigation to lands.

## Job story

When I have an agricultural question, I want to send it without losing my own words
and know that the assistant is working, so I can read its reply without wondering
whether I sent it twice.

## Acceptance scenarios

### Submit one general question

Given the chat home has no lands configured and I enter `  ¿Puedo regar hoy?  `,
when I press **Preguntar**, then the exact text (including leading/trailing spaces)
is shown as my conversation message and is sent in `AskRequest.question`; the request
has `land_context.mode: general` and `land_context.lands: []`; and the composer is
not sent a second time while the first request remains active.

### Visible working state and one reply

Given the request is in progress, when the service has not responded, then a clear,
plain-Spanish working indication is visible, **Preguntar** is disabled, and the
question text remains visible. When a contract-valid answered response arrives, the
working indication disappears and its `answer` is appended once as an assistant
message; the person can enter and submit a later question.

### Invalid input remains unsent

Given the composer is empty or whitespace only, when I try to submit, then no request
is made and no conversation message is added. Given a question exceeds the contract's
2,000-character limit, when I edit it, then the UI prevents a request outside that
limit and explains the limit in Spanish without silently changing the wording.

### Other contract states are retained without false certainty

Given the service returns a contract-valid `abstained` response, when it is appended,
then its plain-language `answer` appears once and is not styled as a supported legal
answer. Given it returns `needs_land_clarification`, then the flow retains the status
and supplied opaque IDs for the later land-clarification feature and does not invent a
land choice or display a fabricated legal conclusion. This slice may show a neutral
temporary plain-Spanish acknowledgement; it must not claim the question was answered.

## Technical approach

1. Replace the home-only state with a pure shared chat presentation model/reducer.
   Model ordered user/assistant messages plus an explicit request phase (`idle` and
   `submitting`). Keep the submitted text immutable in the user message; do not trim,
   rewrite, or use it as a display substitute for server text. Use an action/effect
   boundary so the reducer remains unit-testable and cannot create duplicate requests.
2. Add shared, contract-aligned request/response DTOs and an `AnswerService` (or
   equivalently narrow `AnswerApi`) interface. Its sole operation accepts an
   `AskRequest` and returns an `AskResponse`; it must not expose `Land` names, notes,
   area, or arbitrary metadata. The initial request builder always sends `general` /
   empty lands.
3. Provide a Ktor-backed implementation in shared code using JSON serialization and
   an injected `HttpClient` plus base URL. Use a test `MockEngine`; avoid hard-coding a
   production server address or making network calls from Composables. Platform engines
   and lifecycle-owned client construction belong in their platform source sets or the
   composition root, while the app behavior stays in `commonMain`.
4. Inject the service/use case into `App` rather than coupling UI to transport. The
   production wiring must use an explicit, non-secret development endpoint/configuration
   decision. Because the repository currently lacks `/ask`, do not represent `/health`
   as answer readiness and do not manufacture an answer. A deterministic fake/mock is
   acceptable for previews and focused UI/manual verification until the backend route
   exists.
5. On a valid submit, append the user message, clear the editable composer only after
   capturing its original text, transition to submitting, and launch the suspend call
   from lifecycle-aware shared presentation code. On successful response, append one
   assistant message and return to idle. Preserve typed state needed for all contract
   statuses, but leave status-specific cards, citations, and land choice controls for
   their named dependent features.
6. Define the failure transition internally so the flow cannot remain indefinitely
   submitting, but keep failure copy/retry UI out of scope. The implementation must
   neither append a fake assistant reply nor log raw questions, endpoint payloads,
   land context, names, or notes.

## Expected file changes

- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` to render the
  conversation, composer, progress indication, and injected presentation boundary.
- **Replace/update or split** `ChatHomeState.kt` into shared chat state, actions, and
  pure reducer/effects; remove the obsolete `submittedQuestion` placeholder behavior.
- **Create** `shared/src/commonMain/.../chat/AnswerService.kt` and contract DTOs/client
  files (package name may follow the repository's existing flat package convention).
- **Create** platform-specific HTTP client/engine construction only if required by the
  selected Ktor setup; do not move product state/UI out of `commonMain`.
- **Update** `shared/src/commonMain/composeResources/values/strings.xml` with Spanish
  working, character-limit, and neutral clarification strings. Remove the obsolete
  “lista para continuar” string if unused.
- **Update** `shared/build.gradle.kts` and `gradle/libs.versions.toml` for the minimal
  Ktor client, JSON serialization, and coroutine/test dependencies required by the
  chosen implementation. Avoid unrelated frameworks.
- **Update/create** shared tests for reducer and MockEngine service behavior.
- **Do not update** `contracts/openapi.yaml`: this feature consumes the accepted
  contract rather than revising it. Do not change backend source in this client slice.

## Visual and accessibility impact

Keep the warm, spacious chat-home layout and its maximum readable width. Place the
ordered transcript above the composer, visibly distinguish “you” and “assistant” with
text labels as well as visual grouping, and use a textual progress indication such as
“Estoy preparando la respuesta…”. Do not rely on animation or color alone. Controls
need meaningful Compose semantics, readable scaled text, keyboard reachability on
Desktop, and a large primary action. The transcript must remain scrollable without
clipping the active composer; test small Android windows and wide Desktop windows.

## Durable documentation impact

- `AGENTS.md`: **not needed**; its shared-code, privacy, and Spanish-copy rules already
  apply.
- `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, and
  `docs/archive/MasterPlanV3.md`: **not needed**; this implements existing decisions.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: **not needed**; neither exists and this narrow
  client boundary does not justify creating durable architecture documents.
- `feature_list.json` and `PROGRESS.md`: **defer until implementation verification**;
  record status/evidence truthfully then, not during planning.

## Risks and open decisions

- The accepted API schema exists, but the backend has no `/ask`; local integration is
  blocked until a service implementation or deterministic local mock is supplied.
- No base URL/configuration convention exists. The implementation must make it explicit
  and injectable, not assume localhost works on Android devices.
- Response-state UI is intentionally split. The temporary clarification handling must
  not lose opaque IDs or imply a legal conclusion before `response_states` and
  `land_clarification` deliver their flows.
- Network failure behavior is owned by the next recovery feature, but request state must
  still be released safely and without data leakage.

### Follow-up status after `network_error_recovery`

- Finding **F2** from `docs/validations/chat_question_submission.md` (no request timeout) is
  **closed from this side**: `answerHttpClient` now installs a bounded Ktor `HttpTimeout`
  (`REQUEST_TIMEOUT_MILLIS`/`CONNECT_TIMEOUT_MILLIS`/`SOCKET_TIMEOUT_MILLIS`) with
  `expectSuccess = true`, and both timeout and error responses map into the visible
  failure/retry path instead of leaving the composer submitting forever.
- Finding **F1** (no platform `/ask` engine/endpoint wiring) remains open and owned by the
  `/ask` wiring slice; it is why a live network timeout still cannot be produced by hand in
  the running apps.

### Follow-up status after `minimal_land_context`

- Every statement in this spec that a request *always* uses `land_context.mode: general`
  with `lands: []` is **superseded**: it now holds only when **no land is stored**. With at
  least one stored land the same `ChatConversation` submission builds `mode: all_active`
  with every land's opaque local id, in repository order, plus only the attributes the
  question needs (`municipality`, `water_regime`, `production_method`; never a name, note,
  area, or timestamp), and it re-reads the store at submit and retry time. The accepted
  behavior when no land is configured (byte-identical `general` / `lands: []` payload with
  the exact original wording), the single in-flight submission, the working state, failure
  and retry, and the response states are all unchanged. See
  `docs/specs/minimal_land_context.md`.


## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests ChatHomeStateTest --tests ChatConversationTest --tests KtorAnswerServiceTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/chat_question_submission.appendix.md`](../archive/specs/chat_question_submission.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/chat_question_submission.md` remains the authoritative acceptance record.
