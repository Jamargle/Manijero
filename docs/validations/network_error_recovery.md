# Validation — `network_error_recovery`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`network_error_recovery` implementation against `docs/specs/network_error_recovery.md`.

Feature id: `network_error_recovery`. Spec: `docs/specs/network_error_recovery.md`.
Claimed status: `passing` (self-verified by the implementer). Recommended state
update: the orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair anything; it re-ran the acceptance
checks, read the diff, and independently reproduced the failure/retry/timeout
behavior.

## Review target

`git status` before and after validation showed exactly the expected footprint
(unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- New (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerFailure.kt`.
- Modified (tests): `ChatHomeStateTest.kt`, `ChatConversationTest.kt`,
  `shared/src/jvmTest/.../chat/KtorAnswerServiceTest.kt`.
- Modified (docs): `CONSTRAINTS.md`, `PROGRESS.md`, `feature_list.json`,
  `docs/specs/chat_question_submission.md` (F2 closure note).
- New (docs): `docs/specs/network_error_recovery.md` (planner artifact).

Untouched: `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`,
`shared/src/iosMain/`, `theme/`, every Gradle file and the version catalog,
`scripts/init.sh`. `git diff --check` clean. No new module, dependency, engine wiring,
base URL, navigation, ViewModel, DI, or coroutine scope.

Validated product artifact hashes (sha256):

- `chat/AnswerFailure.kt` `5ae01e367c0bac6688b4fdcce18a468960eccf572611215d530a93760d0f2478`
- `chat/AnswerService.kt` `81e92f731345cff89bbcbe1d9b1a09ff16ce30557a0cde116331cc02ff95723b`
- `ChatHomeState.kt` `1a91abed6162fd28017adaacfa0a470acd8676d69af873f024013e4542c9bd9e`
- `ChatConversation.kt` `15dde3c33c7d928ec2ffe5ce79a6135ef4286f41bcdabc1a7dd03a68e2c965d3`
- `App.kt` `289141a8f847c907b714fab2bf35821b8bf8fef10122972c3dc4a50037722735`
- `strings.xml` `fc2e4ef268440e0ed35d6c7b6fdc6a27dd95a9169b607840f256442735ec7d3f`

## Independent checks and results

Re-run by the validator with `--rerun-tasks` so results are real executions, not
cached `UP-TO-DATE` output:

- `python3 contracts/validate_examples.py` → exit 0,
  "Validated 2 request and 3 response examples against answer_api_contract".
- `./gradlew :shared:jvmTest --rerun-tasks --tests ChatHomeStateTest --tests
  ChatConversationTest --tests KtorAnswerServiceTest` → **BUILD SUCCESSFUL, 40
  tests / 0 failures** (ChatHomeStateTest 25, ChatConversationTest 7,
  KtorAnswerServiceTest 8).
- `./gradlew :shared:jvmTest --rerun-tasks` → **BUILD SUCCESSFUL, 78 tests / 0
  failures** across 11 classes.
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → **BUILD SUCCESSFUL, 69
  tests / 0 failures**.
- `./gradlew :desktopApp:build` → **BUILD SUCCESSFUL**.
- `./gradlew :androidApp:assembleDebug` → **BUILD SUCCESSFUL**;
  `androidApp/build/outputs/apk/debug/androidApp-debug.apk` produced.
- `./scripts/init.sh --verify` → **BUILD SUCCESSFUL, exit 0** (the standard gate really
  runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`, it is not print-only).
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → **BUILD SUCCESSFUL**, so
  the new `commonMain` Ktor/`kotlinx-io` usage does not break the pre-existing
  iOS target.
- Privacy grep `println|Log\.|Logger|printStackTrace|NSLog|System.out|System.err`
  over `shared/src androidApp/src desktopApp/src` → **no matches** (exit 1).
- Copy fidelity: parsed the spec's Copy-contract table and the shipped XML and
  compared **byte-for-byte**; all three keys match exactly
  (`chat_home_failure_unreachable` 124 chars, `chat_home_failure_service` 127
  chars, `chat_home_retry`). `xmllint --noout` OK; 46 strings, no duplicate keys;
  `chat_home_working`, `chat_home_question_too_long`,
  `chat_home_needs_land_clarification`, `chat_speaker_you`,
  `chat_speaker_assistant`, `land_list_retry` all still present.

## Spec conformance (acceptance scenarios)

- **Timeout/unreachable explained, not answered.** `ChatHomeState.failure`/
  `failedQuestion` live outside `messages`; the notice is rendered from state.
  `ChatFailureNotice` shows exactly one `Reintentar` button, no `Asistente`
  label, and no assistant message is appended (ChatHomeStateTest asserts the
  single transcript entry is the `USER` message).
- **Service error explained, not answered.** Same path;
  `ChatConversationTest` proves `UnavailableAnswerService` (the shipped default)
  maps to `SERVICE_ERROR`.
- **Retry keeps the question and cannot duplicate it.** `RetryClicked` re-emits
  `ChatEffect.Submit(failedQuestion)`, adds no user message, and the
  retry-to-success test ends with exactly one `USER` and one `ASSISTANT` message
  and an idle composer.
- **Retrying can fail again safely.** Covered by reducer and conversation tests:
  one user message survives repeated failures, `Reintentar` stays available, and
  a second `RetryClicked` while `SUBMITTING` is a no-op (the button is not even
  rendered because `failure` is cleared on retry).
- **Real answer/abstention never shown as a failure.** `failure` is only set from
  a thrown exception; `ResponseReceived` clears it; an explicit test asserts a
  decoded `abstained` keeps its status and shows no notice.
- **Composer cannot stay submitting forever.** `answerHttpClient` installs
  `HttpTimeout` (`REQUEST_TIMEOUT_MILLIS` 15_000, `CONNECT_TIMEOUT_MILLIS`
  10_000, `SOCKET_TIMEOUT_MILLIS` 15_000) with `expectSuccess = true`. The
  stalled-`MockEngine` probe (`requestTimeoutMillis = 200`, 5 s delay) fails as
  `AnswerServiceUnavailableException` in **0.209 s** — the timeout fired, not the
  delay.
- **Typing again dismisses the failure.** `QuestionChanged` and
  `SuggestedQuestionSelected` clear `failure`/`failedQuestion` (tested).
- **Nothing leaks.** The two exceptions carry only fixed literal messages and no
  `cause`; the Ktor exception (which names the endpoint) is never rethrown or
  logged. UI text comes exclusively from resources. Only `POST /ask` exists.

## Invariants confirmed by reading the code (not only tests)

- **Failure cannot render as an answer.** `RequestFailed` and `RetryClicked` never
  touch `messages`; the only `ASSISTANT` append site is `ResponseReceived`, fed
  solely by a decoded `AskResponse`. The notice is a sibling `Surface`, not a
  `ChatMessage`. `failure != null` and `SUBMITTING` are mutually exclusive, so the
  working bubble and the notice never coexist.
- **Retry preserves wording exactly.** `retry resends the exact wording` asserts
  `Submitt(originalQuestion)` with the fixture `"  ¿Puedo regar hoy?  "` (leading
  and trailing spaces intact), and `KtorAnswerServiceTest` posts that exact
  string.
- **Real-engine failure mapping is correct.** The spec's "connection/timeout/I-O
  → could not reach" mapping depends on catching `kotlinx.io.IOException`. On the
  resolved JVM artifact (`kotlinx-io-core-jvm` 0.7.0) there is **no**
  `kotlinx/io/IOException.class`, and the library source declares
  `public actual typealias IOException = java.io.IOException`. Catching
  `kotlinx.io.IOException` therefore also catches `java.io.IOException` and its
  subclasses (`ConnectException`, `SocketTimeoutException`, OkHttp/Android engine
  failures) — so a real unreachable service maps to the correct notice, not to
  the service-error one.
- **Scope discipline.** Greps confirm no `RequestFailed` constructed without a
  reason, no raw `Color(0x` outside `theme/`, no `land_list_retry`/theme/Gradle/
  contract/backend/platform changes, and the new notice uses only the themed
  `error`/`onError`/`errorContainer`/`onErrorContainer` roles.

## Security assessment

Feature-scoped review found no blocking issues. The failure signals are
payload-free (no URL, body, land detail, or question in the message), no
exception cause is chained, and no logging/printing/telemetry was added; `grep`
found no logging APIs. Recovery keeps the person's exact words, and a failure or
abstention is never rendered as a confident answer, so the "do not describe a
failed request as answered" constraint holds. No new network call, permission,
endpoint, or dependency was introduced.

## Documentation / harness state

`CONSTRAINTS.md` gained a concrete client MUST rule (failed/unreached request is
never an answer; recovery keeps the exact wording). `docs/specs/chat_question_submission.md`
records carried finding F2 (timeout) as closed from this side with F1 (platform
`/ask` wiring) still owned elsewhere. `PROGRESS.md` and `feature_list.json`
record the feature as `passing` with detailed evidence. `DESIGN.md`,
`docs/risks-and-open-questions.md`, `ARCHITECTURE.md`, `AGENTS.md`, and
`scripts/init.sh` were correctly left unchanged (spec's durable-doc decisions).

## Non-blocking findings

- **N1 (process).** `feature_list.json`/`PROGRESS.md` were set to `passing`
  before independent validation; the spec phrases the update as "after
  implementation and independent validation". This matches the repo convention
  (`passing` = ready for validation) and is required for the validator to run;
  the orchestrator should now set `accepted`.
- **N2 (coverage).** Only the *request* timeout is behaviourally probed; the
  connect/socket bounds are asserted finite against
  `HttpTimeoutConfig.INFINITE_TIMEOUT_MS` but not fired. Spec risk R1 explicitly
  accepts this until the platform `/ask` wiring (F1) exists; a real-engine smoke
  should confirm all three when that slice lands.
- **N3 (UX).** Per spec finding IF1, when a draft is typed during a failed
  request, `failedQuestion` falls back to the last user message, so pressing
  `Reintentar` clears that unsent draft (documented and consistent with the
  transition rule; `Preguntar` remains the alternative). Worth a copy/UX glance
  when `chat_accessibility` lands.
- **N4 (a11y).** The polite live region sits on the notice container while the
  `Reintentar` button is a separate node; screen-reader announcement order and
  visible keyboard focus were not independently exercised. Owned by the deferred
  `chat_accessibility` feature.
- **N5 (evidence).** The Android emulator smoke and the two previews are
  implementer-recorded; this validation re-ran all automated gates but did not
  drive an emulator UI (no Compose UI-test harness exists, and none is claimed).
  A live network timeout still cannot be produced in the running apps until F1
  lands.
