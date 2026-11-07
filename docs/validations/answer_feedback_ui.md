# Validation: answer_feedback_ui

- Verdict: **accept** (independent validator, 2026-11-06). Owner decision: validator accept is final for this feature; no owner walkthrough.
- Spec: [answer_feedback_ui.md](../specs/answer_feedback_ui.md) · Evidence: [appendix](../specs/answer_feedback_ui.appendix.md)

## Checks rerun
- `./scripts/init.sh --feature answer_feedback_ui`: passed (23 published command lines). Filtered `:shared:jvmTest` 68 tests, 0 failed (`AnswerFeedbackStateTest` 8, `ChatConversationTest` 20, `KtorAnswerServiceTest` 23, `ChatHomeInteractionTest` 13, `LocalSmokeGuardTest` 4); Desktop `ChatHomeScreenshotsTest` 14 captures and Android 9 passed, including `chatFeedbackSentDark`; contract examples 3/3/2; all static gates silent.
- `./scripts/init.sh --fast`: passed (all 10 offline checks; `:shared:jvmTest` 546 tests, backend 2041 passed 5 skipped, harness 20 passed).
- `./scripts/init.sh --verify`: passed (fast tier plus Android host tests and Android/Desktop builds).
- Tree counted independently: 46 Desktop / 39 Android goldens, 45 `chat_*` keys; 46 = 11 chat + 2 inspector + 10 lands + 2 board + 4 gallery + 4 shell + 7 coverage + 6 privacy.

## Spec review
- Placement: the row renders only in the `answered`/`abstained` assistant branches, after the card and source cards and before `Inspeccionar`; user, clarification, idle, working and failure surfaces have no `ChatMessage` control path. UI tests assert the three displayed cases and the two exclusions; the working/failure notices are separate composables.
- Wire: `FeedbackRequest(rating)` is the only body; `KtorAnswerServiceTest` asserts the exact `{"rating":"useful"}` / `{"rating":"not_useful"}` body, a single `rating` key, `POST /feedback` on the `/ask` address, the trailing-slash rule, and the bearer added only over `https`/loopback with no token over cleartext LAN. Any 2xx accepted, no body decoded, failures map to payload-free signals.
- State: `AnswerFeedback` lives on `ChatMessage` in memory; `FeedbackClicked` accepts only a finished unrated/failed answer and sets `Sending` with one `SendFeedback`; results settle only the entry still sending the same rating. `Sending` disables both controls, `Sent` replaces them with the thanks line, `Failed` keeps both enabled with the retry line and adds no transcript entry or failure state.
- Accessibility: two `OutlinedButton`s with `heightIn(min = ManijeroLayout.MinTouchTarget)`, own `contentDescription`, own tags, `FlowRow` wrapping; every state is stated in text or semantics, no icon/badge/checkmark/success colour. Verified visually in the new and re-recorded goldens.
- Scope: only `shared/**` chat code, strings, tests, chat goldens and the five required docs changed. Backend, `contracts/`, `knowledge/`, `App.kt`, platform entry points, `design/`, `theme/`, the test-only mock (no `feedback` symbol) and `sendFeedback` call sites (transport and conversation only) are untouched.
- Goldens: 4 Desktop and 2 Android chat captures changed by intent (answered/abstention row); 1 new capture per host. Unchanged frames genuinely end above the row; opened `chat_answered_source_dark`, `chat_answered_inspect_link_light`, `chat_feedback_sent_dark` and Android `chat_abstention_dark` myself.

## Security / privacy
No findings. The request is one enumerated `rating` value; no question, answer, land, source, index, device, client id or free text is in the DTO. The bearer rule is the accepted `mayCarryPilotToken` one, errors are the payload-free exceptions, nothing is logged, persisted or linked, and no secret appears in the diff or tests (fake tokens only). No new dependency, route or permission.

## Durable documentation
ARCHITECTURE (rating token sentence + unlinked one-field note), DESIGN (feedback row), `docs/constraints/client-chat.md` (one MUST block), `docs/screenshot-regression.md` (recounted totals + intent note) and `docs/progress/known-limitations.md` are updated; `AGENTS.md`, owner guide, `backend/README.md` and the privacy row stay untouched as the spec required. No contradiction found with the implemented behavior.

## Harness note
`docs/specs/chat_screen_refresh.md` still asserts 36 `chat_*` keys and 6/4 chat captures; the appendix records the staleness honestly. I confirmed it predates this feature (HEAD: 39 keys, 10/7 captures vs 45/11/8 now), so it is accepted-gate debt for a future maintenance change, not a defect of this diff; `--verify` does not run per-feature blocks, so the full gate is unaffected. Running `--feature chat_screen_refresh` will fail on those counts.

## Limits that remain
- No real-device, screen-reader or 2× phone-width reading evidence; no live rating against the owner's service (no walkthrough by owner decision).
- The mock answer service has no `/feedback`, so a mock-backed build shows the retry line rather than counting.
- The UI tests do not assert the `contentDescription` strings directly; the labels are present in code and the visual/semantics state checks pass.
- Android `chat_feedback_sent_dark` ends above the confirmation line, so the thanks state is pixel-proven only on Desktop; the row itself is shown in the Android abstention captures.
