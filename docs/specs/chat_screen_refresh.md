# Feature Spec: `chat_screen_refresh`

## Source metadata

- **Feature:** `chat_screen_refresh` — refresh the assistant screen (`client`).
- **Status at planning:** `not_started`; depends on accepted `app_chrome_navigation` and
  `ui_component_library`.
- **Source behavior:** the same assistant conversation — hero, suggested questions, transcript,
  working, failure, clarification, composer and privacy/help footer — restyled with the accepted
  component layer and moved out of `App.kt` into `chat/`. No copy, payload, state rule, navigation
  rule or land/privacy behavior changes.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md) §5.2, §5.10,
  §6 (`ChatBubble`, `ChatComposer`, `SuggestedQuestionChips`, `SourceCardView`,
  `ClarificationChooser`), §4.2 file map, P2-01…P2-08; `DESIGN.md` "Shared component layer".
- **Decisions recorded at planning (2026-10-25):** the composer keeps a **visible** `Preguntar`
  label with a decorative send glyph (no unnamed icon-only send); the fixed 85 % user bubble stays
  end-aligned while its `Tú` label and body remain one merged node; the working state stays
  text-only with no animated three-dot indicator so a golden never captures a random animation
  phase; the abstention keeps a chat-specific caution card (not `ManijeroCallout`) because the
  speaker and state labels must stay inside the merged entry; suggestions are wrapping
  `AssistChip`s **or** full-width outlined buttons with the same glyph and action, whichever keeps
  every question fully visible at 2× text (P2-03's requirement is the wrapping and the unchanged
  action, not the chip shape).
- **Acceptance record:** [`docs/validations/chat_screen_refresh.md`](../validations/chat_screen_refresh.md)
  (created at acceptance); planning and verification detail is in the
  [appendix](chat_screen_refresh.appendix.md).

## Goal and boundaries

Make the assistant screen read as a finished, calm conversation surface inside the accepted shell:
one hero, one clear transcript with distinguishable speakers, visible sources, one honest failure
state, and one obvious way to ask. The conversation, its answer contract, its semantics and its
Spanish copy stay exactly as accepted; only presentation and file ownership change.

**In scope**

- **Extraction.** Move every chat composable and every chat `@Preview` out of
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` into
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/`, leaving `App.kt` as the composition
  root (routes, state wiring, land actions) it is today.
- **Component adoption.** `ManijeroScreen` for the page frame, `ManijeroCard` (tonal hero, outlined
  source card and chooser), `ManijeroCallout(Danger)` for the recoverable failure,
  `ManijeroBrandMark` for identity, `ManijeroIcon` for the accepted glyphs, and the accepted shape,
  spacing, icon-size and layout tokens in place of local literals.
- **Transcript treatment.** `primary`/`onPrimary` end-aligned user entry at 85 % width, outlined
  neutral assistant entry, caution abstention entry with its speaker and state labels, tonal
  working notice, superscript citation numerals, restyled source cards, and the restyled chooser.
- **Composer and footer.** The existing field with its label, hint and over-limit error, plus a
  visible `Preguntar` action with `ic_send`; the unchanged privacy summary and the two named footer
  actions with `ic_info`/`ic_help`.
- **Strings.** Only the retirement of the unused `chat_home_submitted` key. No new visible copy.
- **Evidence.** Two new chat goldens per host, ten intentionally changed goldens re-recorded after
  review, and one permanent Desktop interaction test.
- **Durable docs.** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and the delivery
  note in `docs/design/ui-refresh-plan.md`.

**Non-goals**

- No new copy, string key, glyph, drawable, colour, shape, spacing token, font, module, dependency
  or Gradle change. No `material-icons-*` entry, no Compose navigation/adaptive library.
- No change to `ChatHomeState.kt`, `ChatConversation.kt`, the answer/citation/land-context
  contracts, the reducer, the effects, the retry/clarification rules, the request payload, the
  local land store, or the privacy/coverage screens.
- No "Verificado"/`Oficial` badge, no timestamp, no cooperative notice, no related-question block,
  no profile/avatar, no badge counts, no two-pane transcript, no animated indicator or motion
  system. The Stitch mockups are visual direction only; their extra content is explicitly out of
  scope in the plan (§2.5).
- No land-attribute chips, summary cards or land-row restyle — those belong to
  `lands_screens_refresh`; the chooser keeps the accepted `LandDetails` plain-detail block.
- No change to the app shell, top bar, bottom bar/rail, insets, back rules, theme, tokens, Android
  or Desktop entry points, `backend/`, `contracts/`, `knowledge/`, or `design-references/`.
- No claim of device, screen-reader, iOS, product-owner or legal acceptance beyond the evidence
  actually run.

## Job story

When I ask Manijero about my olives, I want my own words and the assistant's answer to look
clearly different, the answer's sources and limits to stay visible, and one obvious `Preguntar`
button under a comfortable text box, so I can follow the conversation and never mistake a failed
request or a cautious "no lo sé" for a confident answer.

## Acceptance scenarios

1. **One page frame, one hero.** The assistant screen renders inside the shell with the
   `background` surface, one vertical scroll, the shared 24/40 dp horizontal padding, 32 dp
   vertical padding and a centred 720 dp column. The top block is one tonal card containing the
   32 dp decorative brand mark, `¿En qué puedo ayudarte?` as the single `heading()` in
   `headlineMedium`, and the unchanged description in `bodyLarge`/`onSurfaceVariant`. An empty
   transcript shows no placeholder entry.
2. **Suggested questions.** The section keeps `Puedes empezar con una de estas preguntas` and the
   three accepted questions. Each suggestion is a visible, named control with the `ic_chat` glyph;
   on compact widths the controls wrap to as many lines as the text needs and are never clipped or
   ellipsized at 2× text. Selecting one emits `SuggestedQuestionSelected` with the exact question
   text — it fills the composer and never submits.
3. **Transcript speakers.** Every entry still renders `Tú` or `Asistente` as visible text and stays
   one merged semantics node reading label, scope caption, optional state label and body.
   - A `Tú` entry uses the `primary` container with `onPrimary` label and body, sits at the end of
     the column with a width of at most 85 % of it, and is never announced as a reply.
   - An answered `Asistente` entry is an outlined neutral card on `surfaceContainerLowest` with a
     1 dp `outlineVariant` boundary, the speaker label, the scope caption and the body; its
     citation numerals stay superscript and are not links. Its source cards follow below.
4. **Abstention stays cautious.** A `Sin respuesta segura` entry keeps the caution pair
   (`cautionSurface` container, 1 dp `caution` boundary, `caution` state label), adds the
   `ic_warning` glyph as decoration, keeps the `Asistente` label and scope caption, shows the
   server message verbatim, and is one polite live region. No confident colour, badge, check or
   "verified" cue is added.
5. **Working and failure are states, not answers.** While submitting, a neutral
   `surfaceContainerLow` notice shows `Estoy preparando la respuesta…` as a polite live region and
   no spinner or animated dots. A failure renders a `ManijeroCallout(Danger)` with the warning
   glyph, the accepted plain-Spanish message, and `Reintentar` in its action slot; the callout's
   text block is the polite live region, `Reintentar` remains its own focusable node, and the
   failure is never appended to the transcript or merged with the retry.
6. **Clarification still cannot invent a land.** The chooser is an outlined card with the accepted
   title, the explanation, then: nothing while the guarded local read is unresolved; the accepted
   `No puedo mostrar tus terrenos…` line when it resolved empty; otherwise one checkbox row per
   filtered land (name plus the unchanged `LandDetails`) and `Continuar`, disabled until at least
   one row is selected. Rows keep `Role.Checkbox` and the 12 dp vertical padding that gives a large
   target. A land outside `landIdsToChoose` is never shown.
7. **Composer.** The composer keeps the `OutlinedTextField` with `Escribe tu pregunta`, the example
   placeholder, 3–6 lines and the unchanged over-limit message and error state. It is followed by
   one filled button with the visible `Preguntar` label and a decorative `ic_send` glyph, disabled
   when `canAsk` is false (blank, over the limit, or submitting). The text, selection and focus are
   never moved by a transcript append.
8. **Footer.** The privacy summary line is always visible. With callbacks injected, `Privacidad y
   ayuda` and `Qué cubre Manijero` remain named controls with `ic_info`/`ic_help` and open the same
   destinations; with no callback (iOS scaffold and previews) they are absent, exactly as today.
   No text is added or reworded.
9. **Semantics and scrolling survive the restyle.** One merged node per transcript entry, the
   polite announcement of answered, abstained and working states, the failure/retry split, the
   chooser's loading/no-lands/rows states, and the one-per-append `bringIntoView` of the newest
   element (a non-zero-height end marker) all behave as accepted. The restyle adds no new focus
   trap, removes no focus indication, and overrides no Material minimum target.
10. **Theme-only reuse.** The chat package declares no `Color(0x…)` or hex literal, no raw
    `RoundedCornerShape`, and no `dp` spacing/radius literal where a token exists; it imports the
    shared `design/` components and says nothing domain-specific inside `design/`. Visible strings
    come from `strings.xml`; the only string change is deleting the unused `chat_home_submitted`.
11. **App.kt is a composition root again.** No chat composable, chat preview, chat sample constant
    or chat-only import remains in `App.kt`; `ChatHomeScreen` keeps its exact parameter list, so
    `App` and the four host test classes change only by importing
    `com.jamarglex.manijero.chat.ChatHomeScreen`.
12. **Honest visual and behavioral evidence.** Desktop and Android suites add `chat_abstention_dark`
    and `chat_clarification_light`; the ten goldens the restyle intentionally changes are
    re-recorded after opening each image, and no unrelated golden is rewritten. A Desktop
    interaction test proves the send action is disabled while blank, a suggestion fills the field
    without submitting, and `Reintentar` is a separate clickable control. The screenshot document
    states 22 Desktop / 18 Android captures and keeps its host-only limits.

## Technical approach

- **File split.** `chat/ChatHomeScreen.kt` holds `ChatHomeScreen` (page frame, hero, suggestions,
  composer, footer, scroll key), `chat/ChatTranscript.kt` holds `ChatMessageBubble`,
  `ChatAssistantCard`, `ChatAbstentionCard`, `ChatBubble`, `ChatNoticeBubble`,
  `answerAnnotations` and `landScopeCaption`, `chat/SourceCards.kt` holds
  `SourceCardsSection`/`SourceCardView`/`SourceCardDetail`, `chat/ClarificationChooser.kt` holds
  `LandClarificationChooser`, `chat/ChatStates.kt` holds `ChatFailureNotice`, and
  `chat/ChatPreviews.kt` holds all 24 previews plus their code-owned sample constants. Chat domain
  files (`ChatHomeState.kt`, `ChatConversation.kt`, `AnswerService`, `CitationPresentation`, …)
  stay where they are.
- **Page frame.** `ChatHomeScreen` keeps its signature and builds its sections inside
  `ManijeroScreen`; section spacing comes from `ManijeroSpacing.Comfortable`, internal card spacing
  from `Compact`/`Small`, and the 720 dp cap lives only in `ManijeroScreen`. The
  `BringIntoViewRequester` and its 1 dp end marker move unchanged inside the transcript section.
- **Hero.** `ManijeroCard(tone = ManijeroCardTone.Tonal)` with `ManijeroBrandMark()` stacked above
  the column holding the heading and description. The mark was planned beside the heading, but at
  2× text the narrower title column broke the heading's final `?` onto its own line (reviewed on
  the shell large-text capture); stacking keeps the heading readable at both scales. The heading
  keeps `semantics { heading() }`; the mark is decorative (`contentDescription = null` inside the
  wrapper) and is never attached to an answer.
- **Transcript.** `ChatBubble` becomes the shared surface for user, answered, abstained and notice
  entries: `ManijeroShapes.Large`, `ManijeroSpacing.Comfortable` padding, `Compact` internal
  spacing, caller-supplied container/border/label colours. The user entry is wrapped in a
  full-width `Row` with `Arrangement.End` and `fillMaxWidth(0.85f)`, so alignment is visual only.
  The answered entry keeps the transcript parameters (`surfaceContainerLowest`/`outlineVariant`).
  The abstention gets its own `ChatAbstentionCard` (icon plus labelled column) because
  `ManijeroCallout` has no speaker-label slot and the merged entry must keep `Asistente`, the scope
  caption and `Sin respuesta segura`. The working notice uses `surfaceContainerLow` with no border.
- **Suggestions.** A `FlowRow` of `AssistChip`s, label text allowed to wrap, `ic_chat` as a
  decorative leading glyph. If review at 2× text shows clipping or a chip that cannot show the full
  question, the implementation uses full-width `OutlinedButton`s with the same glyph, start-aligned
  text and the same action, and records the deviation. In both shapes the control list and the
  emitted action stay identical.
- **Failure.** `ManijeroCallout(text = message, tone = Danger, modifier = …)` with `action = {
  Button(colors = error/onError) { ManijeroIcon(ic_retry, null); Text(chat_home_retry) } }`. The
  callout already keeps only its title/text block as the polite live region and leaves the action
  as a sibling node, so the accepted failure/retry contract is preserved by construction.
- **Source cards.** `ManijeroCard(tone = Outlined)` with the source-number text, title, issuing
  body, location, verification date, the excerpt panel (`surfaceVariant`, `ManijeroShapes.Medium`)
  and one `Button` with `ic_external_link` and the accepted content description. The excerpt stays
  fully visible; the URI open stays `runCatching` and the unavailable line stays for a null link.
- **Chooser.** `ManijeroCard(tone = Outlined)` around the existing title, description, `when`
  branches and `toggleable` rows, keeping `LandDetails` unchanged and the selection in local
  `remember(landIdsToChoose)` state.
- **Composer and footer.** The field keeps every parameter from today. The action is a `Button`
  with `Icon` + `Text`, enabled from `state.canAsk`. The footer keeps `chat_home_privacy_summary`
  and the two `TextButton`s (icon + label) behind the same nullable callbacks.
- **Interaction test.** A `jvmTest` class using `runDesktopComposeUiTest` hosts `ChatHomeScreen`
  with a minimal mutable state: it asserts `Preguntar` is disabled while blank, clicks
  `¿Qué es el SIGPAC y para qué sirve?` (after `performScrollTo`), asserts the callback received
  the exact text and no `AskClicked`, and hosts a failure state to click `Reintentar` and assert
  `RetryClicked`. The test is permanently part of `:shared:jvmTest`, not the screenshot suite.
- **Goldens.** Add `ScreenshotFixtures.abstainedChat` (accepted abstention text, scope caption,
  state label) and `clarificationChat` (idle state with `lastResponseStatus =
  needs_land_clarification` and the two fixture land ids). Add `chat_abstention_dark` and
  `chat_clarification_light` per host; re-record only the ten changed goldens with filtered
  `recordDesktopScreenshots`/`recordAndroidScreenshots` runs.

## Expected file changes

- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/ChatHomeScreen.kt`,
  `ChatTranscript.kt`, `SourceCards.kt`, `ClarificationChooser.kt`, `ChatStates.kt`,
  `ChatPreviews.kt`.
- **Add** `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/ChatHomeInteractionTest.kt`.
- **Update** `App.kt` (delete the chat block and its imports, import the new screen).
- **Update** `shared/src/commonTest/.../screenshots/ScreenshotFixtures.kt` (two chat states).
- **Update** `shared/src/jvmTest/.../ChatHomeScreenshotsTest.kt`,
  `shared/src/androidHostTest/.../ChatHomeAndroidScreenshotsTest.kt`, and the two
  `AppShellScreenshotsTest.kt` imports.
- **Add** `chat_abstention_dark.png` and `chat_clarification_light.png` under both screenshot
  folders; **replace** the ten goldens listed in the appendix.
- **Update** `strings.xml` (remove `chat_home_submitted` only).
- **Update** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`,
  `docs/design/ui-refresh-plan.md`.
- After acceptance: `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, the
  appendix's evidence, and the acceptance record.
- **Not changed:** `ChatHomeState.kt`, `ChatConversation.kt`, `chat/` domain sources, `design/`,
  `theme/`, `composeResources/drawable/`, `AppShell.kt`, `AppNavigation.kt`, `lands/`, `privacy/`,
  `coverage/`, Android/Desktop/iOS entry points, `gradle/`, `backend/`, `contracts/`,
  `knowledge/`, `design-references/`.

## Visual design impact

The screen becomes a conversation: a warm tonal hero that introduces the assistant without a
badge, the person's words as one compact primary-coloured entry at the right, answers as calm
outlined cards with their sources still visible, a cautious amber card when the assistant does not
know, and a single visible `Preguntar` action under a comfortable field. The shell's flat bar and
the 720 dp column stay untouched, so the screen reads as content inside the app rather than as a
second app. Nothing on this surface asserts verification, official status, eligibility or legal
coverage; the brand mark stays identity, the caution colour stays caution, and the danger callout
stays the only error treatment.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record the adopted assistant surface: tonal hero, user/assistant/abstention/notice tones and alignment, suggestion controls, visible composer action, failure callout, footer icons, and the layout/scroll contract. |
| `CONSTRAINTS.md` | Update | Add the durable chat-visual rules: the visible `Preguntar` label, the always-visible speaker label on an end-aligned user entry, the abstention speaker/state labels inside its merged node, suggestions never submitting, and the failure retry staying its own node. |
| `docs/screenshot-regression.md` | Update | Add the two new chat states per host and the new 22 Desktop / 18 Android counts; keep the host-render limits. |
| `docs/design/ui-refresh-plan.md` | Update | Record P2-01…P2-08 delivered by this feature and name the working-indicator deviation; the plan stays a historical design input. |
| `docs/risks-and-open-questions.md` | Update | Keep the manual 2×/screen-reader/owner sign-off limits explicit if any remain open after acceptance. |
| `ARCHITECTURE.md` | Not needed | The chat screen moves within `shared` `commonMain` into the existing `chat/` package; no module, dependency direction or boundary changes. |
| `AGENTS.md` | Not needed | Existing UI/skill routing covers screen work. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/session-log.md` | Update after independent acceptance | Keep the accepted set, evidence pointers and open manual checks honest. |

## Focused verification

The block compiles the extraction and the interaction test, verifies both host screenshot suites
(the restyle's visual evidence), and enforces the scope rules. It needs the Android SDK for the
Robolectric suite. It is read-only apart from Gradle output.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests 'com.jamarglex.manijero.chat.ChatHomeInteractionTest'
./gradlew :shared:verifyScreenshots
root="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero"
chat="$root/chat"
for file in ChatHomeScreen ChatTranscript SourceCards ClarificationChooser ChatStates ChatPreviews; do
  test -f "$chat/$file.kt" || { echo "missing chat/$file.kt" >&2; exit 1; }
done
test -f "$REPO_ROOT/shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/ChatHomeInteractionTest.kt" || { echo "missing chat interaction test" >&2; exit 1; }
grep -q 'internal fun ChatHomeScreen(' "$chat/ChatHomeScreen.kt" || { echo "missing ChatHomeScreen declaration" >&2; exit 1; }
grep -q 'ManijeroScreen' "$chat/ChatHomeScreen.kt" || { echo "the screen does not use ManijeroScreen" >&2; exit 1; }
grep -q 'ManijeroBrandMark' "$chat/ChatHomeScreen.kt" || { echo "the hero does not use the brand mark" >&2; exit 1; }
grep -q 'ManijeroCard(' "$chat/ChatHomeScreen.kt" || { echo "the hero does not use ManijeroCard" >&2; exit 1; }
grep -q 'ManijeroCallout(' "$chat/ChatStates.kt" || { echo "the failure notice does not use ManijeroCallout" >&2; exit 1; }
grep -q 'ManijeroCalloutTone.Danger' "$chat/ChatStates.kt" || { echo "the failure callout is not the Danger tone" >&2; exit 1; }
grep -q 'ic_send' "$chat/ChatHomeScreen.kt" || { echo "the composer has no send glyph" >&2; exit 1; }
grep -q 'ic_chat' "$chat/ChatHomeScreen.kt" || { echo "suggestions have no chat glyph" >&2; exit 1; }
grep -q 'ic_external_link' "$chat/SourceCards.kt" || { echo "the source action has no external-link glyph" >&2; exit 1; }
grep -q 'ic_info' "$chat/ChatHomeScreen.kt" || { echo "the privacy footer has no glyph" >&2; exit 1; }
grep -q 'ic_help' "$chat/ChatHomeScreen.kt" || { echo "the coverage footer has no glyph" >&2; exit 1; }
grep -q 'chat_home_ask' "$chat/ChatHomeScreen.kt" || { echo "the composer lost its visible Preguntar label" >&2; exit 1; }
for test_file in "$REPO_ROOT/shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt" "$REPO_ROOT/shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt" "$REPO_ROOT/shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/ChatHomeScreenshotsTest.kt" "$REPO_ROOT/shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/ChatHomeAndroidScreenshotsTest.kt"; do
  grep -q 'import com.jamarglex.manijero.chat.ChatHomeScreen' "$test_file" || { echo "stale ChatHomeScreen import in $test_file" >&2; exit 1; }
done
if grep -q 'fun ChatHomeScreen\|private fun ChatBubble\|private fun ChatFailureNotice\|private const val ANSWERED_SAMPLE' "$root/App.kt"; then
  echo "chat UI still lives in App.kt" >&2; exit 1
fi
if grep -rnE 'Color\(0x|#[0-9A-Fa-f]{3,8}|RoundedCornerShape\(' "$chat" --include='*.kt'; then
  echo "raw colour, hex or shape literal in the chat package" >&2; exit 1
fi
if grep -rn 'com\.jamarglex\.manijero\.chat\|ChatHome' "$root/design" --include='*.kt'; then
  echo "a chat domain reference leaked into the design layer" >&2; exit 1
fi
if grep -q 'name="chat_home_submitted"' "$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml"; then
  echo "unused chat_home_submitted string remains" >&2; exit 1
fi
test "$(grep -c 'name="chat_' "$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml" | tr -d ' ')" = "36" || { echo "chat copy changed beyond the retired key" >&2; exit 1; }
test "$(find "$REPO_ROOT/shared/src/commonMain/composeResources/drawable" -name '*.xml' | wc -l | tr -d ' ')" = "19" || { echo "a drawable was added or removed" >&2; exit 1; }
for shot in chat_abstention_dark chat_clarification_light; do
  test -f "$REPO_ROOT/shared/src/jvmTest/screenshots/$shot.png" || { echo "missing Desktop golden: $shot" >&2; exit 1; }
  test -f "$REPO_ROOT/shared/src/androidHostTest/screenshots/$shot.png" || { echo "missing Android golden: $shot" >&2; exit 1; }
done
test "$(find "$REPO_ROOT/shared/src/jvmTest/screenshots" -name 'chat_*.png' | wc -l | tr -d ' ')" = "6" || { echo "unexpected Desktop chat capture count" >&2; exit 1; }
test "$(find "$REPO_ROOT/shared/src/androidHostTest/screenshots" -name 'chat_*.png' | wc -l | tr -d ' ')" = "4" || { echo "unexpected Android chat capture count" >&2; exit 1; }
if grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml"; then
  echo "an icon-font dependency was added" >&2; exit 1
fi
```
<!-- verify:end -->

The block proves compilation, the interaction behaviors, the extraction, the scope gates and pixel
stability. It cannot judge whether the screen reads well at phone width with 2× text, whether a
screen reader announces the restyled entries and the failure/retry split as intended, whether the
chips are comfortable to tap, or whether the owner likes the result; those remain the manual checks
recorded in the appendix and acceptance record.

## Appendix

See [`chat_screen_refresh.appendix.md`](chat_screen_refresh.appendix.md) for repository research,
component decisions, the ordered implementation plan, evidence to capture and the validator
checklist.
