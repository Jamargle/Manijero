# answer_feedback_ui — appendix

## Repository research

### Files inspected

- `docs/specs/feedback_endpoint.md` + `docs/validations/feedback_endpoint.md` — the accepted `POST /feedback` contract: one field `rating` (`useful`/`not_useful`), `204`, pilot-gated with its own rate window, no idempotency.
- `docs/specs/chat_screen_refresh.md` — the accepted assistant surface, its merged transcript nodes, the `Inspeccionar` sibling node, and the pixel/scope conventions this feature extends.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` — `AnswerService`, `KtorAnswerService`, `answerJson`, the payload-free failure mapping and the per-request `baseUrl()`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/PilotToken.kt` — `PilotToken`, `mayCarryPilotToken` (https or loopback `http`), the only token rules to reuse.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt` — `ChatHomeState`, `ChatMessage`, `ChatHomeAction`, `ChatEffect` (its interface-level `question`/`retainForImprovement`), `reduce`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt` — effects run on the composition scope; payload-free failure mapping into `RequestFailure`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatTranscript.kt` — `ChatMessageBubble` branches per status, merged live regions, `InspectLink`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatHomeScreen.kt` — `state.messages.forEach`, the scroll key and the footer/composer callbacks.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatTestTags.kt` — invisible tags; `LocalSmokeGuardTest` keeps them `Modifier.testTag`-only.
- `shared/src/commonMain/composeResources/values/strings.xml` — the 36 `chat_*` keys; no feedback copy exists yet. `drawable/ic_check.xml` exists but is deliberately unused here.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/KtorAnswerServiceTest.kt`, `PilotProfileClientTest.kt`, `shared/src/jvmTest/.../platform/PilotTokenGuardTest.kt` — MockEngine and repo-guard patterns to extend.
- `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/ChatHomeInteractionTest.kt` — the permanent Compose Desktop interaction suite this feature extends.
- `shared/src/commonTest/.../screenshots/ScreenshotFixtures.kt`, `shared/src/jvmTest/.../screenshots/ChatHomeScreenshotsTest.kt`, `shared/src/androidHostTest/.../ChatHomeAndroidScreenshotsTest.kt` — the chat fixtures and the goldens the new row changes.
- `shared/build.gradle.kts`, `scripts/init.sh` (`feature_commands`, `run_feature`) — `:shared:jvmTest` excludes screenshots; `verify*Screenshots` tasks accept `--tests`; the verify block runs under `bash -euo pipefail` with `REPO_ROOT`.
- `docs/constraints/client-chat.md`, `docs/constraints/hosting-and-pilot.md`, `ARCHITECTURE.md` (answer transport and pilot-token paragraph), `DESIGN.md` "Assistant surface", `docs/screenshot-regression.md` — the durable text this feature must extend.

### Existing patterns to follow

- One transport for both endpoints: `KtorAnswerService` resolves the per-request address, reuses `answerHttpClient`, maps failure classes, and never logs or exposes a URL/body.
- Pure reducer + `ChatEffect`; the composable only renders state and never performs a request.
- Controls below a transcript entry are siblings of the merged, politely announced card (the `InspectLink` precedent), so a live region never swallows a control.
- New copy goes to `strings.xml` next to the existing `chat_*` keys; tests drive controls by Spanish text or by `ChatTestTags`.

### Current gaps / risks

- No client feedback type, transport method, string, tag or UI exists.
- `ChatEffect`'s interface-level `question`/`retainForImprovement` cannot be implemented by a feedback effect; the `QuestionEffect` split in the contract is the minimal fix and keeps `request(lands)` unchanged.
- 5 Desktop and 4 Android chat goldens (answered, abstained, answered-inspect, abstained-inspect, plus the two phone captures) change by intent and must be reviewed and re-recorded, one image at a time.
- `docs/screenshot-regression.md` counts are already stale (its table says 38 Desktop / 34 Android; 46 Desktop PNGs exist today), so the implementer must recount from the run rather than trust the table.
- The accepted `chat_screen_refresh` verify block asserts exactly 36 `chat_*` keys and fixed golden counts; it will not pass after this feature. Accepted blocks are historical: do not edit them, and record the staleness in Feature evidence.
- The mock answer service has no `/feedback` and must not gain one, so a mock-backed build shows the retry line when a rating is sent.
- No live rating against a real service can be observed by an agent session; the owner asked for no walkthrough, so that stays an honest gap.

## Implementation plan

1. Add `AnswerRating`, `FeedbackRequest` and the `sendFeedback` default to `AnswerService`; override it in `KtorAnswerService` with the `/feedback` URL and the `mayCarryPilotToken` rule.
2. Extend `KtorAnswerServiceTest`: exact body `{"rating":"useful"}` / `{"rating":"not_useful"}`, token present on loopback/https only, no token on LAN `http`, `204` accepted, `401`/`422`/`500` and I/O error mapped to the existing payload-free failures, `/ask` unchanged.
3. Add the reducer tests (new `AnswerFeedbackStateTest`): only answered/abstained assistant entries accept `FeedbackClicked`; `Sending` → `Sent`/`Failed` for the same rating only; no other field changes; `Submit`/`SubmitSelected` and `request(lands)` unchanged.
4. Wire `SendFeedback` in `ChatConversation` and cover it in `ChatConversationTest` (success, failure, no logging, composer untouched).
5. Add the six `chat_feedback_*` strings and the three `ChatTestTags` constants.
6. Create `chat/AnswerFeedback.kt`: `FlowRow`, two `OutlinedButton`s with `heightIn(min = ManijeroLayout.MinTouchTarget)` and content descriptions, the confirmation/retry `Text`, no icon or colour literal.
7. Render it from `ChatMessageBubble` under `answered` and `abstained` only (converting the no-inspector abstention branch to a `Column`), before `InspectLink`; pass the index from `ChatHomeScreen`'s `forEachIndexed`.
8. Extend `ChatHomeInteractionTest`: two controls per finished answer and none elsewhere; tap emits the action; the control is outside the polite live region; sent state removes the controls and shows the thanks line; failed and in-flight states keep/disable them as specified; 2× text does not clip.
9. Add `ScreenshotFixtures.answeredFeedbackSent`; add `chat_feedback_sent_dark` to both chat screenshot classes.
10. Review and re-record the changed chat goldens per host with filtered `recordDesktopScreenshots`/`recordAndroidScreenshots` runs (open each image first).
11. Run the focused block; then `./scripts/init.sh --fast` for the shared/contract tiers and `./scripts/init.sh --verify` only when the desktop/Android builds are worth the cost.
12. Update the durable docs listed in the contract, then hand the pair to the validator.

## Verification plan

- `python3 contracts/validate_examples.py` — the feedback examples and the rest of the contract still validate.
- `./gradlew :shared:jvmTest --tests …` (block) — reducer, conversation, transport, control and tag-guard tests pass.
- `./gradlew :shared:verifyDesktopScreenshots --tests '…ChatHomeScreenshotsTest'` and the Android equivalent — the reviewed chat goldens match; needs an Android SDK for the Robolectric suite.
- Static gates — six strings, the new composable, `/feedback` only in the shared transport, no `feedback` in the mock, both new goldens, no raw colour.
- Manual: open the new and changed screenshots and check the control reads as secondary, sits with its answer and stays legible; record the result. No device, screen-reader, owner or privacy-review claim.
- E2E: no new persistent E2E. The mock service has no `/feedback` (owner decision) and `--local-smoke` needs the owner's Mac and a running service, so the send path is proven in-process (MockEngine against the real contract, Compose interaction test) and the live path stays unverified.

## Evidence to capture

- Each block command with its one-line result (test counts, pixel verdict) and the exact list of recorded goldens.
- One line per static gate outcome.
- One line for the screenshot review (`chat_feedback_sent_dark`, the re-recorded answered/abstained captures).
- One line for the `chat_screen_refresh` stale-count observation and for `docs/screenshot-regression.md`'s recounted totals.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-06 — implementer session.

- `./scripts/init.sh --feature answer_feedback_ui` (23 command lines) — passed; filtered `:shared:jvmTest` 68 tests, 0 failed (`AnswerFeedbackStateTest` 8, `ChatConversationTest` 20, `KtorAnswerServiceTest` 23, `ChatHomeInteractionTest` 13, `LocalSmokeGuardTest` 4).
- `verifyDesktopScreenshots --tests ChatHomeScreenshotsTest` — 14 captures PASSED, including `chatFeedbackSentDark`.
- `verifyAndroidScreenshots --tests ChatHomeAndroidScreenshotsTest` — 9 captures PASSED, including `chatFeedbackSentDark`.
- `python3 contracts/validate_examples.py` — Validated 3 request, 3 response, and 2 feedback examples against the answer contract.
- Static gates — six `chat_feedback_*` keys present, `chat/AnswerFeedback.kt` present, `sendFeedback` only in `AnswerService.kt`/`ChatConversation.kt`, no `feedback` in the test-only mock package, both `chat_feedback_sent_dark.png` present, no raw colour literal in the control: all passed with no output.
- `./scripts/init.sh --fast` — all 10 offline checks passed (`:shared:jvmTest` 546 tests 0 failed; backend 2041 passed, 5 skipped; contract examples 3/3/2; harness 20 passed).
- `./scripts/init.sh --verify` — fast tier plus full tier (Android host tests 402 tests, 0 failed; Android and Desktop builds) passed.

Goldens recorded and every changed or new image opened afterwards:

- Desktop: added `chat_feedback_sent_dark`; changed by intent `chat_answered_source_dark`, `chat_abstention_dark`, `chat_answered_inspect_link_light`, `chat_abstention_inspect_link_dark`.
- Android: added `chat_feedback_sent_dark`; changed by intent `chat_abstention_dark`, `chat_abstention_inspect_link_dark`.
- Unchanged: Desktop `chat_answered_source_dark_phone`, Android `chat_answered_source_dark` and `chat_answered_inspect_link_light` — those frames end above the row; no lands, board, gallery, shell, coverage or privacy golden changed.
- Host totals after recording: 46 Desktop PNGs, 39 Android PNGs (`docs/screenshot-regression.md` recounted; the appendix's "46 Desktop today" note was one high and its table 38/34 was stale).

Manual review: the row reads as a quiet secondary pair of outlined buttons under the answer and its sources; the Desktop sent capture shows the confirmation replacing them; there is no icon, badge, colour-only cue or success treatment. The Android `chat_feedback_sent_dark` frame at 360 dp ends above the confirmation line, so that capture records the answer without it — a frame limit, not a missing state.

Stale accepted gate: `docs/specs/chat_screen_refresh.md` asserts exactly 36 `chat_*` keys and 6 Desktop / 4 Android `chat_*.png`; the tree now has 45 keys and 11 / 8 chat captures. Left untouched, because accepted verify blocks are historical.

Not verified: real-device or screen-reader output, and a live rating against the owner's service (no owner walkthrough by decision). The mock answer service has no `/feedback`, so a mock-backed build shows the retry line instead of counting.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no mock, backend, contract, `App.kt` or platform-entry change).
- [ ] Acceptance scenarios pass with evidence, including the exact `{"rating":"…"}` body and the token rule.
- [ ] The two controls appear only under finished answers and never inside a merged live region.
- [ ] Success locks the answer, failure keeps both controls enabled, one tap sends one request.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature answer_feedback_ui`.
- [ ] Goldens re-recorded only for the intended chat captures, each opened before recording.
- [ ] Durable documentation impact followed; accepted specs' verify blocks left untouched.
- [ ] `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, the acceptance record and `docs/progress/known-limitations.md` updated honestly.

2026-11-06 — validator acceptance (independent).

- Verdict `accept`; checks rerun and evidence judged real; no repair brief. Record: [validation](../validations/answer_feedback_ui.md). Stale `chat_screen_refresh` gate confirmed pre-existing at HEAD.
