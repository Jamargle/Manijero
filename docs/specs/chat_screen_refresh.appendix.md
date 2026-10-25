# Appendix — `chat_screen_refresh`

Planning and verification record for [`chat_screen_refresh.md`](chat_screen_refresh.md). The
authoritative acceptance record is
[`docs/validations/chat_screen_refresh.md`](../validations/chat_screen_refresh.md); this appendix
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
| Hero | `ManijeroCard(Tonal)`, `ManijeroBrandMark`, `ManijeroSpacing` | Row layout only, so the mark sits beside the title. |
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

_To be completed by the implementer in the worktree._

### What shipped

_To be completed._

### Verification results

_To be completed._

### New goldens

_To be completed._

### Changed goldens and review

_To be completed._

### Accessibility notes

_To be completed._

### Deviations and limits

_To be completed._

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
