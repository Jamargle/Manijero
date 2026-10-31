# Appendix — `chat_screen_refresh`

Planning and verification record for [`chat_screen_refresh.md`](../../specs/chat_screen_refresh.md). The
authoritative acceptance record is
[`docs/validations/chat_screen_refresh.md`](../../validations/chat_screen_refresh.md); this appendix
holds the repository research, component decisions, plan, evidence, and validator checklist.

## Repository research

Inspected 2026-10-25 in the base checkout (`main` @ `eaceed8`); planning changed no source file.

- **Where the chat lives.** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` is 1676
  lines: the `App` composition root (≈490 lines) followed by the whole chat surface and **24**
  `@Preview` functions. The chat block is `ChatHomeScreen` plus `ChatMessageBubble`,
  `ChatAssistantCard`, `landScopeCaption`, `answerAnnotations`, `SourceCardsSection`,
  `SourceCardView`, `SourceCardDetail`, `ChatNoticeBubble`, `LandClarificationChooser`,
  `ChatFailureNotice` and `ChatBubble`, with the preview-only constants `ANSWERED_SAMPLE`,
  `ANSWERED_TWO_SOURCES_SAMPLE`, `SOURCE_SAMPLE`, `SOURCE_SAMPLE_TWO`,
  `ABSTAINED_SAMPLE_NO_EVIDENCE`, `ABSTAINED_SAMPLE_FALSE_PREMISE`. A private
  `ContentMaxWidth = 720.dp` is used only by chat code. Moving the block leaves the composition
  root and the land actions untouched.
- **Existing chat entry contract.** `internal fun ChatHomeScreen(state, onAction, onPrivacyClick?,
  onCoverageClick?, clarificationLands?, modifier)` renders inside `AppShell`; `App` passes the
  conversation state, the four callbacks and `clarificationLands`. Two host `AppShellScreenshotsTest`
  classes and two `ChatHome*ScreenshotsTest` classes import `com.jamarglex.manijero.ChatHomeScreen`,
  so the extraction changes four imports and no call arguments.
- **Page frame today.** `Surface(background)` + `Column(fillMaxSize, verticalScroll, padding(24/32))`
  with every block capped by `widthIn(max = 720.dp)` and centred. `ManijeroScreen` already
  implements exactly that frame with 24/40 dp horizontal padding from `WideWindowBreakpoint`
  (840 dp), 32 dp vertical padding, `ManijeroContentWidth` 720 dp and
  `ManijeroSpacing.Comfortable` between sections. It owns the scroll and no insets; the shell is the
  single inset owner.
- **Component layer.** `design/` holds `ManijeroScreen`, `ManijeroCard`
  (`Surface`/`Tonal`/`Outlined`/`Danger`), `ManijeroSectionHeader`, `ManijeroCallout`
  (`Info`/`Caution`/`Danger`/`Confirmation`, icon + text, title/text as the only polite live
  region, optional action slot), `ManijeroStatCard`, `ManijeroEmptyState`,
  `ManijeroAttributeChip` (non-interactive land attributes only), `ManijeroChoiceCard`,
  `ManijeroSearchField`, `ManijeroDropdownField`, `ManijeroMeasureField`, `ManijeroBrandMark`
  (32 dp default, decorative), `ManijeroIcon` (explicit description, 20/24/32 dp) and the three
  navigation components. No generic chip wrapper exists; `ManijeroAttributeChip` is deliberately
  not an action, so the suggestions use Material 3 `AssistChip` inside a `FlowRow`.
- **Tokens.** `ManijeroShapes` (4/12/16/24 dp), `ManijeroSpacing` (4/6/8/12/16/24/32/48),
  `ManijeroIconSize` (20/24/32), `ManijeroLayout` (720 dp cap, 24/40/32 dp padding, 1 dp border,
  48 dp minimum target). `ManijeroColors.kt` exposes the Material roles plus `caution`,
  `cautionSurface`, `onCaution`, `primaryStrong`, `ecoContainer`, `onEcoContainer`. Contrast
  pairs in `DESIGN.md` cover `onPrimary`/`primary` (10.68 light / 6.73 dark),
  `error`/`errorContainer` (5.00 / 5.51) and `caution`/`cautionSurface` (7.37 / 8.12), so the
  restyle needs no new pair.
- **Copy.** One Spanish `values/strings.xml` with 37 `chat_*` keys. `chat_home_submitted` is unused
  in every source set; `chat_home_lands` is still referenced by `LandListScreen`; every other chat
  key has a live call site. No new copy is needed: the hero, suggestions, composer, failure,
  clarification and footer already have accepted strings.
- **Icons.** 19 XML assets = 16 `ic_*` glyphs + `brand_mark` + `olive_branch` +
  `compose-multiplatform`; `ic_chat`, `ic_send`, `ic_info`, `ic_help`, `ic_external_link`, `ic_retry`
  and `ic_warning` already exist. The restyle adds no asset and no `material-icons-*` entry.
- **Semantics today.** One `mergeDescendants` node per transcript entry; `answered`, `abstained`
  and the working notice are polite live regions; the failure surface is a polite live region whose
  retry button is a sibling; the chooser renders nothing while `lands == null`; the 1 dp
  `bringIntoView` marker is deliberately non-zero height (documented implementation finding in
  `App.kt`). All of this is behavior to preserve, not to redesign.
- **Screenshot harness.** Desktop Compose on `jvmTest` and Robolectric SDK 35 on `androidHostTest`
  with 20 and 16 committed goldens, pinned `es-ES`, density 1, font scale 1 and 0.1 % comparison
  threshold. The suites are excluded from `:shared:jvmTest`/`:shared:testAndroidHostTest` and from
  `--fast`/the Linux gate; the record tasks are explicit and can be filtered with `--tests`. Chat
  goldens today: Desktop `chat_home_idle_light`, `chat_home_idle_light_phone`,
  `chat_answered_source_dark`, `chat_answered_source_dark_phone`; Android `chat_home_idle_light`,
  `chat_answered_source_dark`. Four `app_shell_assistant_*` goldens per host also contain the chat
  screen.
- **Fixtures.** `ScreenshotFixtures` (commonTest) owns `idleChat`, `answeredChat` (verbatim accepted
  answer + one source) and `twoLands`. It has no abstention or clarification state yet, so the two
  new captures need two small code-owned states; `clarificationChat` can be built from
  `ChatHomeState(lastResponseStatus = needs_land_clarification, landIdsToChoose = …)` plus
  `twoLands.lands`, since `awaitingLandClarification` only checks the phase and that status.
- **UI-test capability.** `jvmTest` already declares `libs.compose.uiTestJunit4Desktop` and
  `ScreenshotTestSupport` calls `androidx.compose.ui.test.v2.runDesktopComposeUiTest` with
  `onRoot()`. A permanent non-screenshot interaction test can use the same API
  (`onNodeWithText`, `performClick`, `performScrollTo`, `assertIsNotEnabled`) without adding a
  dependency; `commonTest` has no Compose UI dependency and gains none.
- **Shell state.** `app_chrome_navigation` already hides the old chat `Mis terrenos` button and puts
  the screen inside the bars; `App.kt` no longer passes `onLandsClick`. `App` routes privacy and
  coverage from the chat footer, which this feature keeps.

## Component decisions

| Surface | Accepted components | Local pieces kept and why |
|---|---|---|
| Page | `ManijeroScreen` | Nothing: it already owns scroll, padding and the centred 720 dp column. |
| Hero | `ManijeroCard(Tonal)`, `ManijeroBrandMark`, `ManijeroSpacing` | The mark sits above the heading (stacked, see deviation 4), so 2× text keeps the title column full width. |
| Suggestions | `FlowRow`, Material 3 `AssistChip`, `ManijeroIcon(ic_chat)` | Fallback to full-width `OutlinedButton` + the same glyph if 2× text clips; the action and list never change. |
| User entry | None | `ChatBubble` keeps its own `Surface`: the four transcript tones and the 85 % end alignment are chat-specific, and `ManijeroCard` fixes the container and always fills the width. Uses tokens only. |
| Answered entry | `ManijeroShapes`/`ManijeroLayout`/`ManijeroSpacing` inside `ChatBubble` | `ChatBubble` is the one place that guarantees the merged semantics, label/scope/state order and live region. |
| Abstention | None (`ChatAbstentionCard`) | `ManijeroCallout(Caution)` puts the icon and text in its own live-region block and has no speaker-label slot; the entry must announce `Asistente` + scope + `Sin respuesta segura` + body as one node. |
| Working notice | `ChatBubble` with `surfaceContainerLow` | No animated dots: an infinite animation would make the golden non-deterministic, and the text already states the state. |
| Failure | `ManijeroCallout(Danger)` + `Button` (error/onError) in `action` | The callout already isolates the text live region and keeps the action a sibling, which is the accepted contract. |
| Sources | `ManijeroCard(Outlined)`, `ManijeroShapes.Medium`, `ManijeroSpacing`, `ManijeroIcon(ic_external_link)` | The source number stays plain text (a numbered `ManijeroAttributeChip` would read as a land attribute). |
| Chooser | `ManijeroCard(Outlined)`, accepted `LandDetails`, `Checkbox`, `Button` | `LandDetails` is the shared lands detail block; land chips wait for `lands_screens_refresh`. |
| Composer | `OutlinedTextField`, `Button`, `ManijeroIcon(ic_send)` | Visible `Preguntar` label; no icon-only or unnamed send. |
| Footer | `TextButton`, `ManijeroIcon(ic_info/ic_help)` | Same copy and callbacks; icons are decorative. |

Deliberate deviations from the plan's prose, recorded so review can accept or reject them:

1. **No three-dot working indicator.** §5.2 lists one; a static indicator adds no information and an
   animated one cannot be captured deterministically. The accepted text `Estoy preparando la
   respuesta…` plus the polite live region carries the state.
2. **Suggestion shape is conditional.** The plan says chips; the hard requirement is full visibility
   at 2× text and the unchanged fill-only action. If `AssistChip` cannot meet it, full-width
   outlined buttons with the same glyph are used and the appendix records the reason.
3. **No source-number chip.** §5.10 says "numbered chip"; the shared chip is a land-attribute
   component, so the number stays a labelled text line until a generic chip exists.
4. **Stacked hero.** The plan and the first technical approach put the brand mark beside the heading
   in a `Row`; the shell large-text review showed the narrower title column breaking the final `?`
   onto its own line, so the mark sits above the heading. The acceptance scenario is unchanged: one
   tonal card with the 32 dp mark, the single heading and the untouched description.
5. **Chooser checkbox meets the land name.** Each land row keeps the 12 dp vertical padding and
   Material's 48 dp `Checkbox` target, but the box is offset up by `ManijeroSpacing.Small` so it sits
   beside the land name instead of the middle of the seven-line detail block. This is a display fix
   inside the restyled chooser; the selection, the `needs_land_clarification` state, the scope filter
   and the "no lands" branch are unchanged.

## Implementation plan

Ordered so every step leaves the tree compiling:

1. **Extract, unchanged.** Create the six `chat/` files and move the composables, previews and
   sample constants verbatim; keep `ChatHomeScreen`'s signature and visibility. Update the four test
   imports. Delete the chat block and now-unused imports from `App.kt`. Run
   `:shared:jvmTest` to prove a behavior-free move.
2. **Page frame + hero.** Replace the manual frame with `ManijeroScreen`; replace the plain
   title/description column with the tonal hero card and the decorative brand mark. Keep the
   heading semantic.
3. **Transcript.** Restyle `ChatBubble` with tokens; add the end-aligned 85 % user row; add
   `ChatAbstentionCard`; move the working notice to `surfaceContainerLow`; keep assistant and
   citation rendering.
4. **Failure and chooser.** Convert the failure to `ManijeroCallout(Danger)` with the retry in the
   action slot; wrap the chooser in `ManijeroCard(Outlined)` and keep its `when` unchanged.
5. **Sources.** Wrap the source card in `ManijeroCard(Outlined)`, add `ic_external_link` to the open
   action, and keep the excerpt panel and unavailable line.
6. **Suggestions, composer, footer.** `FlowRow` of chips (or the reviewed fallback), visible
   `Preguntar` + `ic_send`, footer icons; no copy edits.
7. **Strings.** Delete `chat_home_submitted`; leave every other key untouched.
8. **Fixtures and captures.** Add `abstainedChat` and `clarificationChat`; add
   `chat_abstention_dark` and `chat_clarification_light` to both host classes; record the four new
   PNGs and re-record the ten intentionally changed ones with filtered record tasks.
9. **Interaction test.** Add `ChatHomeInteractionTest` with the blank-send, suggestion and retry
   assertions; keep it in `:shared:jvmTest`.
10. **Durable docs and harness state.** Update `DESIGN.md`, `CONSTRAINTS.md`,
    `docs/screenshot-regression.md` and the plan's delivery note; set the feature `in_progress`, run
    the focused block, `--fast` and `--verify`, record exact results in "Feature evidence", and set
    `passing` only when all required checks pass. Leave the acceptance record and `accepted` status
    to the orchestrator after independent validation.

## Verification plan

Cheapest first; record the exact command and result for each.

1. **Focused block (contract).** `./scripts/init.sh --feature chat_screen_refresh` — the interaction
   test, both screenshot suites, the extraction/scope gates and the golden inventory. Needs the
   Android SDK.
2. **No-device tier.** `./scripts/init.sh --fast`.
3. **Full gate.** `./scripts/init.sh --verify` — adds Android host tests and the Android/Desktop
   builds.
4. **Common-source purity.** `./gradlew :shared:compileKotlinIosSimulatorArm64` (the extraction must
   stay in `commonMain`).
5. **Android emulator smoke.** `./scripts/init.sh --android-run`, then: hero and suggestions; a
   suggestion fills the field without submitting; send is disabled while blank; a real or local
   failure shows the danger callout and `Reintentar` works; the clarification chooser shows the
   stored lands, `Continuar` is disabled until a row is selected, and a picked land is submitted;
   the working notice appears; light/dark and 2× text; keyboard open; scroll to the newest entry.
   Capture screenshots for the acceptance record.
6. **Desktop smoke.** `./scripts/init.sh --desktop` at a narrow and a wide window: the 720 dp column,
   85 % user bubble, chip wrapping, visible `Preguntar`, keyboard traversal, footer links.
7. **Screenshot review.** Open all 14 PNGs (4 new, 10 replaced) at full size and confirm the intended
   tones, Spanish labels, alignment, no clipping and no half-painted frame. Record that the review
   happened; owner sign-off remains a manual item.

Not available or not claimed: a persistent UI/E2E harness, screen-reader output capture, a real
device/tablet/desktop-OS matrix, iOS behavior, reduced-motion behavior, or product-owner
acceptance.

## Evidence to capture

- Focused block output and the interaction-test result.
- `--fast` and `--verify` results (task count, exit status).
- iOS simulator compile result.
- New and replaced golden list with a review note per image.
- Android emulator observations: each state, send enablement, retry, chooser, keys, 2× text.
- Desktop observations: narrow/wide, chip wrap, keyboard order.
- Any deviation from this plan and why (chip fallback, previews count, etc.).

## Feature evidence

Verified 2026-10-25 in `../Manijero-worktrees/chat_screen_refresh` on branch
`feature/chat_screen_refresh`, from `main` @ `7759b83` (the planning commit).

### What shipped

- **Extraction.** The whole chat surface and its 24 previews moved from `App.kt` into
  `chat/ChatHomeScreen.kt`, `ChatTranscript.kt`, `SourceCards.kt`, `ClarificationChooser.kt`,
  `ChatStates.kt` and `ChatPreviews.kt`. `App.kt` is 356 lines and contains only the composition
  root, the answer service wiring and the four host call sites; `ChatHomeScreen` keeps its exact
  parameter list. The four screenshot test classes import `com.jamarglex.manijero.chat.ChatHomeScreen`.
- **Page and hero.** `ManijeroScreen` owns the one scroll, the 24/40/32 dp padding and the centred
  720 dp column. The hero is one `ManijeroCard(Tonal)` with the 32 dp decorative `ManijeroBrandMark`
  above the heading (`headlineMedium`, the single `heading()`), the untouched description and no
  badge, date, status or greeting.
- **Transcript.** The user entry is `primary`/`onPrimary`, end-aligned and 85 % wide, with the
  visible `Tú` label. An answered entry is an outlined neutral card on `surfaceContainerLowest` with
  the `Asistente` label, scope caption and superscript citation numerals. The abstention is a
  chat-owned caution card (`ChatAbstentionCard`) with the decorative warning glyph, `Asistente`,
  scope caption, `Sin respuesta segura` and the server message verbatim in one polite node. The
  working state is the `surfaceContainerLow` text notice with no animation. A failure is
  `ManijeroCallout(Danger)` with `Reintentar` in its action slot, so the callout text stays the live
  region and the retry remains a sibling focusable node.
- **Sources.** `ManijeroCard(Outlined)` with the source marker, title, issuing body, location,
  verification date, the `surfaceVariant` excerpt panel and the `Abrir documento oficial` button
  with `ic_external_link`; the unavailable-link line is unchanged.
- **Suggestions and composer.** A `FlowRow` of Material `AssistChip`s with a decorative `ic_chat`;
  selecting one only emits `SuggestedQuestionSelected(question)`. The composer keeps every field
  parameter and is followed by one full-width `Preguntar` button with a decorative `ic_send`,
  disabled from `state.canAsk` (blank, over the limit or submitting).
- **Footer.** The privacy summary and the two `TextButton`s with `ic_info`/`ic_help` stay behind the
  same nullable callbacks; the summary remains the always-present line.
- **Chooser.** `ManijeroCard(Outlined)` around the unchanged title/description/`when` branches,
  `LandDetails` and selection state; the `Checkbox` visual box is nudged to the land name (deviation
  5) while its 48 dp target and `Role.Checkbox` stay.
- **Strings and fixtures.** Only `chat_home_submitted` was deleted (37 → 36 `chat_*` keys, 19
  drawables). `ScreenshotFixtures` gained `abstainedResponse` (the verbatim
  `contracts/examples/response-abstained.json` text) and `clarificationChat`; the two new chat
  captures were added to both host classes.
- **Tests and docs.** A permanent `jvmTest` interaction test (three tests) and the durable docs
  (`DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, the plan delivery note and this
  appendix) were updated. `ChatHomeState`, the conversation/answer domain, `design/`, `theme/`,
  drawables, the shell and the backend/contracts are untouched.

### Verification results

| Check | Command | Result |
|---|---|---|
| Focused block | `./scripts/init.sh --feature chat_screen_refresh` | exit 0: the three interaction tests pass, `:shared:verifyScreenshots` passes both hosts, and every extraction, import, string, drawable, count and raw-literal gate passes |
| Interaction test alone | `./gradlew :shared:jvmTest --tests 'com.jamarglex.manijero.chat.ChatHomeInteractionTest'` | BUILD SUCCESSFUL (3 tests) |
| No-device tier | `./scripts/init.sh --fast` | exit 0, "Fast tier passed", all 9 offline checks pass |
| Full gate | `./scripts/init.sh --verify` | exit 0, "Fast tier passed" plus the full tier: `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` |
| iOS common-source compile | `./gradlew :shared:compileKotlinIosSimulatorArm64` | BUILD SUCCESSFUL |
| 2× text review | two temporary Desktop captures at 360×2000 and 360×2400 dp, font scale 2 (deleted afterwards) | every suggestion chip wraps to two or three lines with the whole question visible; the field, disabled `Preguntar`, summary and both footer actions are fully visible; the chooser's rows keep the box beside the land name, the details wrap without clipping and the column scrolls |

Not run, and not claimed: the Android emulator smoke (`--android-run`), the Desktop smoke
(`--desktop`), TalkBack/keyboard traversal, a real device/tablet/Desktop-OS matrix, iOS rendering,
and owner visual sign-off. The host-rendered goldens and the interaction test are the evidence that
exists.

### New goldens

| Golden | Hosts | Size / appearance | Review |
|---|---|---|---|
| `chat_abstention_dark` | Desktop + Android | Desktop 900×1200, Android 360×800, dark | The hero, the right-aligned `Tú` entry and the amber caution card: warning glyph, `Asistente`, scope caption, `Sin respuesta segura`, the message verbatim and no source cards. The card is clearly not a confident answer. |
| `chat_clarification_light` | Desktop + Android | Desktop 900×1200, Android 360×800, light | The outlined chooser with the accepted title and explanation, the two stored lands with their details and the box beside each name, then a disabled `Continuar`. Android shows the chooser continuing below the fold; it scrolls with the page, which is why the capture does not reach `Continuar`. |

### Changed goldens and review

Ten existing PNGs were re-recorded after opening each at full size:

- **Desktop (6).** `chat_home_idle_light` and `chat_home_idle_light_phone`: tonal hero with the
  stacked mark, two-line title at 360, wrapping chips, disabled `Preguntar` and the privacy summary.
  `chat_answered_source_dark` and `chat_answered_source_dark_phone`: the primary right-aligned user
  entry, the outlined answer with its scope and superscript `1`, the restyled source card and button;
  the 900×1200 frame keeps the composer's top edge at the fold, as its comment says.
  `app_shell_assistant_compact_light` and `app_shell_assistant_compact_large_text`: the chat inside
  the bars. The 2× shell frame shows the hero at three lines, the description continuing below the
  fold, and the known clipped/wrapped bottom-bar labels; nothing in the shell itself changed.
- **Android (4).** `chat_home_idle_light`, `chat_answered_source_dark`,
  `app_shell_assistant_compact_light` and `app_shell_assistant_compact_large_text`: the same states
  rendered by Robolectric. The Android large-text shell shows the title at two lines and the
  description cut by the viewport edge; the content scrolls, and the bars were already the accepted
  shell's.
- No other golden changed: `git status` lists exactly these ten plus the four new chat captures.

### Accessibility notes

- The accepted semantics are preserved by construction: one merged node per transcript entry,
  visible `Tú`/`Asistente` labels, polite announcements for answered, abstained and working states,
  the failure callout's text-only live region with `Reintentar` as its own node, the chooser's
  loading/no-lands/rows branches, and the one-per-append end marker.
- The interaction test proves the blank-send disabled state, that a suggestion fills the field and
  emits no submit action, and that `Reintentar` is an enabled, separate control that emits
  `RetryClicked`.
- The chooser keeps `Role.Checkbox`, the whole row as the target, the 48 dp Material target and the
  disabled `Continuar` until a selection; the box now shares the first line of the land it selects.
- The 2× frames show the field, the visible `Preguntar` label, the summary and the footer actions
  without clipping, and the suggestion chips fully wrapped. Material's minimum interactive size and
  focus indication are untouched.
- Not verified here: actual screen-reader announcements (TalkBack/VoiceOver), contrast measurement
  (the token pairs are previously gated), pointer/touch comfort, or keyboard order on a device.

### Deviations and limits

Deviations: the stacked hero (deviation 4), the chooser checkbox nudge (deviation 5), the static
working notice instead of the plan's three-dot indicator, and the visible `Preguntar` label instead
of the plan's unnamed `Enviar` icon button. All four are recorded above and in the plan delivery
note; none changes an accepted behavior.

Limits found during review, all disclosed in the validation record:

- At 360×800 dp inside the shell, the hero and suggestions fill the first screen and the composer's
  `Preguntar` button starts just below the fold, so the person needs one short scroll. The chat-only
  360×800 goldens show the button above the fold; the compact shell frame does not. The order is
  the accepted plan order, and the field and button remain in the same page scroll.
- The shell's large-text bottom-bar labels wrap and clip at 360 dp with 2× text; this is the
  accepted shell's known weak spot, not a change made here.
- Desktop goldens are host-font-pinned to macOS; Android goldens are Robolectric renders, not a
  device. No screen-reader, emulator, or owner sign-off is claimed.

## Validator checklist

- [ ] The contract's twelve acceptance scenarios are each evidenced by code, test, golden or a
      recorded manual observation.
- [ ] `ChatHomeScreen`'s parameters and visibility are unchanged; `App.kt` contains no chat
      composable, preview or sample constant.
- [ ] `ChatHomeState.kt`, `ChatConversation.kt`, the chat domain sources, `design/`, `theme/`,
      drawables, shell/navigation, lands/privacy/coverage, entry points and Gradle are untouched.
- [ ] Speaker labels, scope captions, state labels, merged nodes, polite live regions and the
      failure/retry split are preserved; the user entry is not announced as a reply.
- [ ] Suggestions fill without submitting and never clip at 2× text (or the documented fallback is
      used).
- [ ] The composer keeps a visible `Preguntar` label and its disabled state while blank,
      over-limit or submitting.
- [ ] The chooser still cannot flash the no-lands fallback before the local read resolves and
      never fabricates a land.
- [ ] No new string (36 `chat_*` keys), drawable (19), colour/shape/token, dependency or Gradle
      change exists; no new legal, verification or eligibility meaning appears.
- [ ] The two new goldens exist on both hosts, exactly ten existing goldens changed, and each
      changed image was opened and explained by the intended restyle.
- [ ] The focused block, `--fast`, `--verify` and the iOS simulator compile pass, or every failure
      is documented as an honest limit.
- [ ] Durable docs (`DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, the plan's
      delivery note) match what shipped.
- [ ] Open manual checks (owner visual sign-off, screen reader, device) are stated, not implied.

### Validator record

_To be completed after independent validation._
