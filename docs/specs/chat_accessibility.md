# Feature Spec: `chat_accessibility`

## Source metadata

- **Feature:** `chat_accessibility` — Read and operate the chat comfortably (`accessibility`), `not_started` at planning (2026-10-13).
- **Depends on:** `chat_home`, `response_states`, `answer_source_cards`, `visual_foundation` (all accepted).
- **Source behavior:** A person can use the chat with enlarged system text, clear control labels, and keyboard or assistive-technology navigation.
- **Source verification:** Check text scaling, screen-reader labels, keyboard focus, and visible focus on Android and Desktop.
- **Feature-list note:** Also apply large touch targets, high contrast, and plain Spanish.
- **Carried handoffs owned by this feature (each was explicitly deferred to `chat_accessibility`):**
  - `chat_question_submission` **F3** — no small/wide-window or text-scale evidence and no transcript auto-scroll, so a freshly appended message or the working indication can sit below the fold.
  - `visual_foundation` **U3** (Desktop has no OS text-scale integration; large-text evidence is preview-only) and **U4** (Android `enableEdgeToEdge()` launch frame / status-bar overlap: verify and report).
  - `response_states` **U2** (whether an *answered* entry is also announced — decided here) and **N2** (`widthDp=320`/`fontScale=2f` and greyscale claims are structural, not inspected).
  - `network_error_recovery` **N3/N4** (failure-notice announcement order and visible keyboard focus; `Reintentar` clears an unsent draft).
  - `answer_land_scope` **N3**, `answer_source_cards` rendered-evidence gap, `land_data_disclosure` **N3/N5** — the same structural-only large-text/greyscale evidence (N3: the chat-home privacy summary can sit below the fold).
  - `land_clarification` **N2** — the chooser briefly renders its no-lands fallback before the local read resolves.
  - `land_list` informational F3 — Android system back exits from any destination (no `BackHandler`).

## Goal and boundaries

Make the shared chat surface (`ChatHomeScreen` and everything it renders) verifiably comfortable at enlarged system text, announced clearly to assistive technology, fully operable by keyboard with visible focus on Desktop, and never clipped or colour-only — and close the carried gaps this feature owns: announce a newly arrived answer, bring the newest transcript content into view, and stop the chooser's false "cannot show your lands" flash.

**In scope**

- One explicit announcement policy: a newly appended assistant reply (answered and abstained) is a polite live region; user entries are not; the working notice, failure notice and abstention keep their accepted announcements, with the notice's `Reintentar` still a separate focusable control.
- Bringing the newest transcript content into view once per appended element (message, working notice, failure notice, chooser), without moving to the page bottom and without touching composer text or focus. One pure, testable key decides *when*.
- Keyboard and visible-focus verification on Desktop, and the smallest fix needed if the default Material focus indication is not clearly visible.
- Enlarged-text and narrow/wide-window verification on Android and Desktop, plus the centering of the capped content column on wide windows.
- One heading semantic on the screen title; confirm every control/entry exposes a text name.
- The clarification chooser's loading state (no misleading fallback before the local read resolves).
- Recorded evidence for the carried items above, and the accessibility baseline written into `DESIGN.md`.

**Non-goals**

- No change to accepted copy, states, or behavior: the three transcript treatments (neutral answer, caution abstention, danger failure), `answerStatus`/`sources`/`landScope` per-entry data, source cards, land scope captions, clarification semantics, the reducer, `contracts/`, `backend/`, `knowledge/`, land storage, and the privacy notice text are untouched.
- No new dependency (including test-only), Gradle module, navigation, ViewModel, DI, permission, or logging; no Compose UI-test harness is added (see R1/U1).
- No restructure into a pinned composer plus an independently scrolling transcript, no `BackHandler`/Android system-back navigation work, no Android inset/window-background resources, no dark theme, no Desktop OS text-scale integration.
- No accessibility audit of the land screens or the privacy destination; that is `land_form_accessibility` / release polish.
- No tappable reference numerals (needs scroll-to-item), no sticky "follow only if at the bottom" scroll logic, no new string unless the implementation proves one is required (then it is plain Spanish and recorded here).

## Job story

When I use the chat with the system text enlarged, with a screen reader, or with a keyboard, I want every message, warning and control to be readable and reachable by name and in a predictable order, and I want a new reply to be announced and visible without hunting for it — so I can read and operate the conversation without assistance.

## Acceptance scenarios

### Enlarged text stays fully readable

Given Android `font_scale 2.0` (or the `fontScale = 2f` preview), when the chat home, a long answered reply with source cards, an abstention, the working notice, a failure notice and the clarification chooser are shown, then every label, body and control wraps without clipping or overlap, there is no horizontal overflow, and no action label or target becomes unreadable.

### Screen-reader labels and merged entries

Given TalkBack (or the Android accessibility tree), when the chat is read, then each transcript entry is one node reading its `Tú`/`Asistente` label, its scope caption, its optional state label and its body; the source-card metadata, the excerpt, the chooser rows (name + known details + checkbox state) and the failure notice each carry text; every control is announced with a name (never an unnamed button), and the screen title is reachable as a heading. No state is conveyed by colour alone.

### A newly arrived reply is announced

Given an assistant reply is appended, when it appears, then an `answered` reply is a polite live region (not only the abstention), the working notice, the abstention and the failure notice keep their accepted announcements, a `Tú` entry is not announced as a reply, and the failure notice does not merge its `Reintentar` control into the announcement.

### The newest content is visible without losing the composer

Given a conversation where the newest entry, working notice, failure notice or chooser would fall below the fold, when that element is appended, then it is brought into view once, the page does not jump to its very bottom, the composer's text and focus are unchanged, and a plain recomposition or a keystroke in the composer scrolls nothing.

### Keyboard operation with visible focus on Desktop

Given the Desktop window, when the chat is operated with the keyboard only, then every control (suggestion, composer, `Preguntar`, `Mis terrenos`, `Privacidad y ayuda`, source-card open, chooser checkboxes and `Continuar`, `Reintentar`) is reachable in a predictable order, activates with Enter/Space, retains its state after a failed request (the draft case of `network_error_recovery` N3 is reviewed and recorded), and its focused state is visibly indicated (the default Material indication, or one shared added outline if the default is insufficient).

### Large touch targets and contrast hold

Given the shipped theme, when the chat is inspected, then no control is below Material's minimum interactive size (no `LocalMinimumInteractiveComponentSize` override), and every text/control pair the chat uses meets WCAG AA through the existing `theme/ManijeroColorsTest` table (no token or pair changes are required; the run is recorded).

### The chooser never flashes a false limitation

Given a clarification arrives, when the local land read has not resolved yet, then the chooser shows its title and explanation only — never the "no puedo mostrar tus terrenos" fallback; that fallback appears only after the read resolved with no land matching the offered ids, or failed.

### Nothing else changes

Given the feature ships, when the existing suites run, then all accepted copy, states, source cards, scope captions, clarification behavior, land screens and persistence behave exactly as before, with no previously passing test regressing and no new module, dependency, endpoint or logging.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` (1,442 lines) — the whole chat surface lives here: `ChatHomeScreen` (one outer `Column` with `verticalScroll(rememberScrollState())`, children capped by `fillMaxWidth().widthIn(max = ContentMaxWidth = 720.dp)`, no `horizontalAlignment`), `ChatMessageBubble`, `ChatAssistantCard`, `ChatBubble` (one `semantics(mergeDescendants = true)` node, optional `liveRegionMode`), `SourceCardsSection`/`SourceCardView` (merged metadata node + one `Button` with `contentDescription`), `LandClarificationChooser`, `ChatFailureNotice`, and ~24 `ManijeroTheme` previews including several `widthDp = 320, fontScale = 2f`.
- `App.kt` announcement state today: the working notice (line 461) and the abstained entry (line 620) are `LiveRegionMode.Polite`; the failure notice's `Surface` is a polite live region (line 948) and does **not** merge descendants, so its `Reintentar` stays a separate focusable node; **an `answered` entry is not a live region** — this is `response_states` U2.
- `App.kt` clarification wiring (lines 205-213): `clarificationLands` starts as `emptyList()` and is filled by a `LaunchedEffect`, so the first frame after a clarification renders `chat_home_clarification_no_lands` — `land_clarification` N2.
- `App.kt` has no `bringIntoView`, `onGloballyPositioned` or `heading()` usage, and no focus-indicator modifier; there is no code that scrolls the transcript.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt` — pure `ChatHomeState` (`question`, `messages`, `phase {IDLE, SUBMITTING}`, `submittedQuestion`, `lastResponseStatus`, `landIdsToChoose`, `failure`, `failedQuestion`, `clarificationQuestion`), `ChatMessage(speaker, text, answerStatus, sources, landScope)`, `SubmissionPhase`, and `reduce`. File matches used by this feature's key extractor.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt` — the only hex file; `contrastRatio`/`relativeLuminance` helpers; semantic `caution`/`cautionSurface`/`primaryStrong`. `ManijeroTypography.kt` overrides only `bodySmall` line height (18sp). `ManijeroTheme.kt` applies the theme once in `App()`.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/theme/ManijeroColorsTest.kt` — the WCAG pair table (`onSurface` on `cautionSurface` 14.58 was added by `response_states`); the chat pairs used (`onBackground`/`onSurface` 14.96/16.19, `onSurfaceVariant` 7.54/8.16, `primary` label 8.80/9.53, `onSurface` on `surfaceVariant` 12.84, `caution` 7.37/7.56/8.19, `error` 7.46/6.89, `onErrorContainer` 9.18) are already rows there.
- `shared/src/commonMain/composeResources/values/strings.xml` — one Spanish file, 102 strings; all chat controls already have visible labels (`chat_home_ask`, `chat_home_lands`, `chat_home_privacy`, `chat_source_open`, `chat_home_clarification_continue`, `chat_home_retry`, `chat_speaker_you`/`chat_speaker_assistant`). `chat_home_submitted` is unused and stays untouched.
- `shared/build.gradle.kts` / `gradle/libs.versions.toml` — `compose.foundation` 1.12.1 is present, so `bringIntoViewRequester`/`windowInsetsPadding` need no new dependency; `commonTest` has only `kotlin-test`, `kotlinx-coroutines-test` and `ktor-client-mock`; **no Compose UI-test artifact exists** and the repo has consistently refused test-only dependencies (`visual_foundation` non-goals).
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt` — `enableEdgeToEdge()` then `setContent { App(landRepository) }`, no inset padding (`visual_foundation` U4). `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` — a resizable `Window`.
- Prior Android evidence used a real emulator (`Medium_Phone_API_35`) with `adb shell settings put system font_scale 2.0`; `land_list`/`remove_land` records report that TalkBack/instrumented assistive access was denied and that no UI-test harness exists.
- `scripts/init.sh --verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; no new mode is needed and it must not start a service.
- `DESIGN.md` lines 66, 72, 90-94 (`fontScale` support, large touch targets, keyboard navigation and visible focus on Desktop, "Avoid claiming the UI is accessible until these checks have been performed on Android and Desktop") and `CONSTRAINTS.md` (per-feature client MUST rules this work must not regress).

Sized correctly: one screen, no data model, no persistence, no transport, no contract change. It is verification-dominant — small code changes plus recorded platform evidence — with one new pure file and its test.

## Technical approach

### 1. Announcement policy (App.kt)

Give the answered branch the same polite announcement the abstention already has: add a defaulted `liveRegionMode: LiveRegionMode? = null` parameter to `ChatAssistantCard` and pass `LiveRegionMode.Polite` only from the `AnswerStatus.answered` branch (the defensive `needs_land_clarification` branch stays silent). Keep `ChatBubble`'s merged node and the `Tú` branches unchanged: a user entry is never a live region. Keep `ChatFailureNotice` non-merging so `Reintentar` stays its own focusable node.

### 2. Newest content into view (App.kt + new pure file)

- New pure, Compose-free `shared/src/commonMain/kotlin/com/jamarglex/manijero/TranscriptScroll.kt` (package `com.jamarglex.manijero`, same package as `ChatHomeState`):

```kotlin
/** What the transcript should move to. Changes only when a new element is appended. */
data class TranscriptScrollKey(
    val entryCount: Int,
    val phase: SubmissionPhase,
    val hasFailure: Boolean,
    val awaitingLandClarification: Boolean,
)

fun transcriptScrollKey(state: ChatHomeState): TranscriptScrollKey
```

The key changes on a new `Tú`/`Asistente` entry, on entering/leaving `SUBMITTING`, when a failure appears or clears, and when a clarification appears; it does **not** change for a keystroke, an example selection, or any unrelated recomposition (tested).

- In `ChatHomeScreen`, hold the existing `rememberScrollState()`, remember the last key, and when the key changes request that the end of the transcript region be brought into view: attach a `BringIntoViewRequester` to a small end-of-transcript marker inside the transcript `Column` (after the messages, failure notice, working notice and chooser) and call `bringIntoView()` from a `LaunchedEffect` keyed on the key. If `bringIntoViewRequester` is unavailable/experimental on this toolchain, fall back to tracking the marker's `onGloballyPositioned` offset and `ScrollState.animateScrollTo`, and record which mechanism shipped (implementation finding). Nothing is scrolled on a plain recomposition, and the page never jumps to its very bottom.

**Implementation finding — shipped mechanism.** `bringIntoViewRequester`/`bringIntoView()` shipped (no `onGloballyPositioned`/`animateScrollTo` fallback). The end-of-transcript marker **must not be zero-height**: `NodeCoordinator.localBoundingBoxOf` collapses an empty rect to `Rect.Zero` (`if (bounds.isEmpty) return Rect.Zero`), and the bring-into-view responder then reads the request as "already visible at the container origin" and silently drops it (`ContentInViewNode.bringChildIntoView` early-returns when the child rect is already reported visible). A zero-height `Spacer` therefore scrolled nothing, which was confirmed on the Android emulator (the transcript stayed put; a 1dp marker moved it). The shipped marker is `Modifier.fillMaxWidth().height(1.dp).bringIntoViewRequester(...)`, with the reasoning recorded in a comment beside it.

### 3. Clarification chooser loading state (App.kt)

Change `clarificationLands` from `List<Land>` to `List<Land>?` in `App()` and `ChatHomeScreen` (`null` = the local read has not resolved). Keep the guarded `LaunchedEffect` read; set `emptyList()` on a failed or empty read so the accepted fallback still appears when there genuinely is no land. In `LandClarificationChooser`, while the value is `null` render only the title and explanation; render the `chat_home_clarification_no_lands` fallback only for a resolved empty/failed list, and the rows + `Continuar` otherwise. Update the three chooser previews for the new parameter and add no copy.

### 4. Wide-window readability and heading (App.kt)

Add `horizontalAlignment = Alignment.CenterHorizontally` to the outer content `Column` of `ChatHomeScreen` so the existing 720dp cap is centred instead of hugging the left edge on a wide Desktop window (no width, spacing, or child change). Add `Modifier.semantics { heading() }` to the `chat_home_title` `Text`. No other screen changes.

### 5. Focus, touch targets and contrast (verify first)

Verify on Desktop whether the default Material focus indication is clearly visible on every interactive control at normal viewing distance. If it is not, add one shared, small focus treatment (a 2dp `primary` outline via a `Modifier` composable in `App.kt`, keeping Material's own indication) and re-capture; `primary` against `canvas`/`surface` is already ≥ 3:1 for exactly this purpose. Do not add a minimum-size override and do not lower the Material minimum interactive size; re-run the existing contrast table and record it as-is.

### 6. Evidence discipline

Every claim that was only structural before (greyscale, `fontScale = 2f`, `widthDp = 320`, keyboard focus, TalkBack) must now be either an inspected Android/Desktop capture or an explicitly recorded limitation with the command attempted. Never claim a check that was not run.

## Expected file changes

- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/TranscriptScroll.kt`: `TranscriptScrollKey` + `transcriptScrollKey` (Compose-free).
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatAssistantCard` live-region parameter and the answered branch; the end-of-transcript marker + bring-into-view effect; `clarificationLands: List<Land>?` (state, `ChatHomeScreen` parameter, `LandClarificationChooser` loading branch); `horizontalAlignment` on the content column; `heading()` on the title; one wide-window preview (`widthDp = 1000`) and one long-conversation preview at `fontScale = 1.3f`; the three chooser previews updated. Optional: the shared focus-outline modifier only if §5 requires it.
- **Add** `shared/src/commonTest/kotlin/com/jamarglex/manijero/TranscriptScrollTest.kt`: the key changes for a new entry, submitting/working, a failure, a clarification; and does not change for a keystroke, an example selection, or an equal-state re-reduce.
- **Do not modify**: `ChatHomeState.kt` behavior, `ChatConversation.kt`, `chat/`, `lands/`, `privacy/`, `theme/`, `strings.xml`, `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, any Gradle file or version catalog, `scripts/init.sh`, and `feature_list.json`/`PROGRESS.md` while implementing (except the documentation updates below).

## Visual design and accessibility impact

No token, copy, or state change: the same `surface`/`surfaceVariant`/`outlineVariant`/`cautionSurface`/`errorContainer` treatment, now verifiably readable at 2× text and announced for answers as well as abstentions. The chat keeps one merged, text-labelled node per entry (never colour-only), the 48dp Material minimum target, and the 720dp readable width — centred rather than left-aligned on wide Desktop windows. Known, recorded limits: Android insets/launch frame (U4, report-only), Desktop OS text scaling has no runtime integration (U3, preview-based), no automated UI-test harness (R1), and the transcript is not split into a pinned composer plus its own scroll region (U2).

## Implementation plan and tasks

1. Write `TranscriptScrollTest` first, then `TranscriptScroll.kt`.
2. Add the answered live region, the end-of-transcript marker and the bring-into-view effect; confirm the working/abstention/failure announcements and the non-merging failure notice are unchanged.
3. Add the chooser loading state (`List<Land>?`) and update the three chooser previews.
4. Add the `horizontalAlignment` centring, the `heading()` semantic, and the two new previews; run §5 and add the focus outline only if the check requires it.
5. Run the automated checks and greps; then the Android emulator checks (font scale, dump, keyboard focus, scroll) and the Desktop checks; capture screenshots/records and the `adb` commands used.
6. Byte-check that no string changed (`git diff --numstat .../strings.xml`), re-run `docs/validations`-style greps (`Color(0x` only under `theme/`; no logging; no minimum-size override; the `liveRegion`/`mergeDescendants`/`contentDescription` attributes still present).
7. Update `CONSTRAINTS.md` and `DESIGN.md`; append the short decision notes to `docs/specs/response_states.md` (U2) and `docs/specs/land_clarification.md` (N2 closure). Touch `feature_list.json`/`PROGRESS.md` only after independent validation.

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.TranscriptScrollTest"
./gradlew :shared:jvmTest --rerun-tasks          # expect the prior 184 + the new tests, 0 failures, none removed
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./scripts/init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # only under theme/
grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src   # no matches
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml   # expected: empty
```

Android evidence (real emulator, `:androidApp:assembleDebug`):

```sh
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
adb shell settings put system font_scale 2.0     # then 1.0
adb shell uiautomator dump /sdcard/chat.xml && adb pull /sdcard/chat.xml
adb shell input keyevent 61                      # TAB, repeated, to read the focus order from the dump
```

Record for each chat state (home, long answered reply with cards, abstention, working, failure notice, clarification chooser): a screenshot at `font_scale 2.0` and `1.0`; whether a false no-lands fallback appeared; from the dump, the labelled nodes and the merged entry text, the checkbox rows' text/checked state, and which node was `focused`; and — after submitting a long answer — whether the newest entry was brought into view without jumping to the page bottom. Attempt TalkBack (`settings put secure enabled_accessibility_services`); if assistive access is denied, record that and rely on the dump plus code inspection, never claiming a TalkBack pass.

Desktop evidence (`./scripts/init.sh --desktop`): resize narrow (`320dp`) and wide (≥ 1000dp) — content stays capped and centred with no horizontal overflow; walk the controls with Tab and capture focus visibility; state honestly if an interactive session is unavailable (then use the `widthDp = 1000` and `fontScale` previews and record the limit). Preview review: every chat preview plus the two new ones, re-checked in greyscale for the non-colour cues.

Capture: test counts/names; the `uiautomator` dump excerpts; screenshots; the greps; the unchanged-`strings.xml` diff; and `./scripts/init.sh --verify` output (or the exact blocker).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One "Chat accessibility" MUST rule: the chat surface MUST keep a text name on every control and transcript entry, one merged text-labelled node per entry, a polite announcement for every newly appended assistant reply, no colour-only state, Material's minimum interactive size, a visible focus indication, newest content brought into view without moving the composer, and no chooser fallback before the local read resolves. Reason: this is the first accessibility baseline for the surface and every later feature can silently regress it. |
| `DESIGN.md` | **Update during implementation** | Record the verified chat accessibility baseline (Android/Desktop checks actually performed, and the remaining gaps) in the "Accessibility and validation" section, which currently forbids claiming accessibility until these checks are done. |
| `docs/specs/response_states.md`, `docs/specs/land_clarification.md` | **Append one short note each after implementation** | `response_states` U2 (the answered entry is announced) and `land_clarification` N2 (the fallback flash) are decided/closed from this side; the accepted behavior is not revised (precedent: the `answer_source_cards` R5 note). |
| `docs/risks-and-open-questions.md` | Optional | One row for the missing automated accessibility/UI-test coverage, if the orchestrator wants it tracked there rather than only in this spec's risks. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md` | Not needed | The plain-Spanish, accessibility, and shared-`commonMain` rules already govern; no product or domain change. |
| `ARCHITECTURE.md` | Not needed | It does not exist; no module, boundary, or dependency is added. |
| `scripts/init.sh` | Not needed | No new mode; it must not start a service or an emulator. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record status, the checks actually run, and every unperformed/manual limit then; planning does not touch them. |

## Risks and open decisions

- **R1 No Compose UI-test harness.** `commonTest` has no Compose UI-test artifact, so merged semantics, live regions, focus order and clipping cannot be asserted in unit tests; adding one is a test-only dependency this repo has refused so far. Mitigation: the pure scroll key, the Android `uiautomator` dump, previews, screenshots, and honest limits (U1).
- **R2 Auto-scroll can fight a reader.** Bringing the newest element into view will also move the view for someone reading an earlier reply. Accepted for the MVP: nothing else scrolls, the move is minimal, and no sticky-follow state is added; revisit if real use shows it is disruptive.
- **R3 Wide-window centring touches accepted layout.** It changes only horizontal alignment, but every chat preview must be re-reviewed and the phone rendering must stay identical.
- **R4 Focus indication may be insufficient on Desktop.** If Material's default is not clearly visible, the added outline must not remove it, and the added colour must come from the `primary` token (no new hex, no `theme/` change).
- **R5 Assistive access may be denied in the harness** (precedent: `land_list`, `remove_land`). Report the attempt and the outcome; never claim a TalkBack pass that was not performed.
- **R6 Live region on every assistant entry.** A node recreated on each render could re-announce; keep the transcript rendering positional (no key churn) and verify the announcement count in the dump/on device.
- **R7 Android insets/launch frame** (`visual_foundation` U4) is report-only here; a fix would need platform inset wiring and is a release-polish decision (U3).
- **U1** Whether to adopt a Compose UI-test dependency later (deliberately not now).
- **U2** Whether to split the chat into a pinned composer plus its own scrolling transcript (a dedicated layout slice; the privacy summary's placement would have to be re-decided with it).
- **U3** Android inset handling and the launch frame, and whether the chat-home privacy summary (`land_data_disclosure` N3) should move above the composer: inspect, decide, and record — copy stays byte-identical either way.
- **U4** Desktop OS text scaling has no runtime integration, so Desktop large-text evidence stays preview-based.
- **U5** Whether a reference numeral should become tappable to its card (needs scroll-to-item; not now).

## Validator checklist

- [ ] An `answered` reply is a polite live region, the working/abstention/failure announcements are unchanged, a `Tú` entry is never one, and `Reintentar` stays a separate focusable node in the non-merging failure notice.
- [ ] The newest transcript element (entry, working notice, failure notice or chooser) is brought into view once when appended, the page does not jump to its bottom, and a keystroke, an example selection, or an unrelated recomposition scrolls nothing (asserted by `TranscriptScrollTest` plus the recorded Android check).
- [ ] The clarification chooser never renders the no-lands fallback before the local read resolves, and still shows it for a genuinely empty or failed read; its copy is unchanged.
- [ ] At `font_scale 2.0` / `fontScale = 2f` and at `widthDp = 320` nothing is clipped or overlapped, and on a wide Desktop window the 720dp content column is centred with no horizontal overflow.
- [ ] Every chat control and transcript entry carries a text name; each entry is one merged node with its label, scope, optional state label and body; the chooser rows expose name + known details + checkbox state; the title is a heading; no state is colour-only (greyscale capture recorded).
- [ ] Keyboard-only operation reaches every control in a predictable order with a visible focus indication on Desktop, or the exact limitation is reported; controls keep Material's minimum interactive size and no minimum-size override exists.
- [ ] `strings.xml` is unchanged (`--numstat` empty) and every accepted string is byte-identical to its accepted value; the per-entry `answerStatus`/`sources`/`landScope` data and the three transcript treatments are untouched.
- [ ] No `Color(0x` outside `theme/`; no logging/printing of question, answer, land, payload, or exception text; no new module, dependency, Gradle change, endpoint, permission, or shipped fake.
- [ ] `:shared:jvmTest` (previous 184 + new, none removed), `:shared:testAndroidHostTest`, the Android/Desktop builds, `./scripts/init.sh --verify`, and the contract validator pass, or the exact environment blocker is reported.
- [ ] Every carried gap named in "Source metadata" is either closed with recorded evidence or explicitly recorded as still open with a reason; no structural-only claim is presented as an inspected render.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the final diff matches this spec's file list; `CONSTRAINTS.md` and `DESIGN.md` were updated as described.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests TranscriptScrollTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/chat_accessibility.md (untracked/new; one implementation-finding note appended to section 2 - the end-of-transcript marker must not be zero-height, because `NodeCoordinator.localBoundingBoxOf` collapses an empty rect to `Rect.Zero` and `ContentInViewNode.bringChildIntoView` then drops the request as 'already visible'). Added the pure, Compose-free shared/src/commonMain/kotlin/com/jamarglex/manijero/TranscriptScroll.kt (`TranscriptScrollKey(entryCount, phase, hasFailure, awaitingLandClarification)` + `transcriptScrollKey(state)`) and shared/src/commonTest/kotlin/com/jamarglex/manijero/TranscriptScrollTest.kt (8 tests): the key changes for a new entry, entering/leaving `SUBMITTING`, a failure appearing/clearing and a clarification appearing, and does not change for a keystroke, an example selection, or an equal-state re-reduce (including a refused late response).
- App.kt (shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt, commonMain only): `ChatAssistantCard` gained a defaulted `liveRegionMode: LiveRegionMode? = null` and the `answered` branch now passes `LiveRegionMode.Polite`, while the `Tú` entries, the defensive `needs_land_clarification` branch, the working notice, the non-merging failure notice (its `Reintentar` stays a separate focusable node) and the abstention keep their accepted announcements; `ChatHomeScreen` holds a `BringIntoViewRequester` on a **1dp** end-of-transcript marker (`.fillMaxWidth().height(1.dp).bringIntoViewRequester(...)`, with the zero-height finding recorded in a comment) and a `LaunchedEffect(scrollKey)` that calls `bringIntoView()` only when the key differs from the remembered first key, so opening/returning/keystrokes never scroll; `clarificationLands` is `List<Land>?` in `App()` and `ChatHomeScreen`, and `LandClarificationChooser(lands: List<Land>?)` renders title+explanation only for `null`, the `chat_home_clarification_no_lands` fallback only for a resolved empty list, and the checkbox rows + `Continuar` otherwise; the outer content `Column` gained `horizontalAlignment = Alignment.CenterHorizontally`, the top-level blocks use `.widthIn(max = ContentMaxWidth).fillMaxWidth()` so the 720dp cap is effective and centred, and the title `Text` gained `Modifier.semantics { heading() }`. Previews added: a wide window (`widthDp = 1000`), a long conversation at `fontScale = 1.3f`, and a chooser-while-resolving (`clarificationLands = null`); the three chooser previews were updated for the nullable parameter. No copy, token, state, per-entry data or control change; no focus outline was added (see the focus gap below).
- Docs: CONSTRAINTS.md gained the 'Chat accessibility' MUST rule (a plain-Spanish name on every control and entry, one merged entry node, a polite announcement for every appended assistant reply, no colour-only state, a visible focus indication, Material's minimum interactive size, newest content brought into view without moving the composer, a centred capped column, and no chooser fallback before the local read resolves). DESIGN.md 'Accessibility and validation' now records the inspected Android/Desktop baseline and the remaining gaps. docs/specs/response_states.md records U2 decided (an `answered` entry is a polite live region) and docs/specs/land_clarification.md records N2 closed (the fallback flash).
- Commands actually run (repository root, all pass): `python3 contracts/validate_examples.py` -> 'Validated 2 request and 3 response examples against answer_api_contract' (exit 0); focused `./gradlew :shared:jvmTest --tests com.jamarglex.manijero.TranscriptScrollTest` -> BUILD SUCCESSFUL (report XML: 8 tests / 0 failures / 0 errors); `./gradlew :shared:jvmTest --rerun-tasks` -> BUILD SUCCESSFUL, 192 tests / 0 failures / 21 suites (was 184, +8, no test removed); `./gradlew :shared:testAndroidHostTest --rerun-tasks` -> BUILD SUCCESSFUL, 178 tests / 0 failures / 17 suites (was 170, +8); `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` -> BUILD SUCCESSFUL, 72 actionable tasks executed; `./scripts/init.sh --verify` -> BUILD SUCCESSFUL (exit 0, 91 tasks); `./gradlew :shared:compileKotlinIosSimulatorArm64` -> BUILD SUCCESSFUL; `grep -rn 'Color(0x' shared/src/commonMain/kotlin/com/jamarglex/manijero --include='*.kt' | grep -v /theme/` -> no matches (all matches are in theme/ManijeroColors.kt); `grep -rn 'LocalMinimumInteractiveComponentSize|minimumInteractiveComponentSize' shared/src` -> no matches; `grep -rn 'println|Log\.|Logger|printStackTrace|NSLog|System\.out' shared/src androidApp/src desktopApp/src` -> no matches; `git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml` -> empty; `git diff --check` -> clean.
- Android evidence (real emulator-5554, Medium_Phone_API_35, density 2.625, `adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk`; dumps/screenshots in the gitignored build/evidence/): at `font_scale 1.0` and `2.0` the home, a long answered reply with two source cards, an abstention, the working notice, the failure notice and the clarification chooser render with no clipping, overlap, or horizontal overflow (every `uiautomator dump` node within 0..1080 x 0..2400; screenshots cap-f10-*.png/cap-f20-*.png and final-*.png, with the newest content and the source cards in view at 2.0 while the composer/buttons/privacy stay below the fold). Touch targets at 1.0: every clickable node is at least 126px = 48dp (suggestion buttons [63,594][1017,720] and siblings, `Preguntar` [63,1417][351,1543], `Mis terrenos` [383,1417][654,1543], `Privacidad y ayuda` [63,1723][1017,1849], the source-card open button [105,1151][612,1277], a chooser row [105,1087][975,1362] = 105dp tall, `Reintentar` [105,1056][401,1182]); `Preguntar` is `enabled=false` with an empty composer and enabled with a draft. Names and merged entries (`uiautomator dump --compressed`): each transcript entry is one merged node reading `Tú`/`Asistente` + scope caption + optional state label + body; the source-card control carries `content-desc` 'Abrir el documento oficial: «…»'; every control has a text label; the failure notice's `Reintentar` is a separate clickable+focusable node (the notice does not merge descendants). Clarification chooser: its rows are `checkable=true` toggles exposing the saved name + known details, `checked` flips false->true on tap, `Continuar` becomes focusable once a land is selected, and the string 'no puedo mostrar tus terrenos' appears in NONE of the dumps (a11y-clarification.xml, a11y-clarification-checked.xml) - the false-limitation flash is not reproducible. TalkBack is enabled and bound (`settings put secure enabled_accessibility_services com.google.android.marvin.talkback/...` succeeds, `dumpsys accessibility` shows a bound TalkBack service).
- Auto-scroll verified on the shipped APK (no probe) at `font_scale 2.0` with a long question: the page was first scrolled to its very bottom (the lowest controls `Privacidad y ayuda` [250,2197][830,2295], `Preguntar` [126,1591][433,1689] and the composer [63,944][1017,1517] all visible, with no transcript entry or failure notice on screen), then `Preguntar` was tapped; after the append the dump shows the newest content in view - the user entry tail [105,0][975,421] and the failure notice [105,517][975,1294] with `Reintentar` [168,1347][489,1445] - while the composer, `Preguntar`, `Mis terrenos`, the privacy summary and `Privacidad y ayuda` are all absent from the dump (below the fold), so the view scrolled up to the newest element and neither stayed at nor jumped to the page bottom (build/evidence/flow7-bottom-2.0.xml, flow7-after-2.0.xml/.png). At `font_scale 1.0` submitting at the page top leaves the title at [63,84] and shows the `Tú` entry [105,485] + failure notice [105,834][975,1086] + `Reintentar` [168,1155][338,1208] already in view, i.e. nothing scrolls when the target is already visible (flow6-*.xml); the working notice appears at the SUBMITTING phase (final-3-working-2.0.png). No instrumentation, `onGloballyPositioned`, `LayoutCoordinates` or hoisted scroll state remains in App.kt.
- Desktop evidence (real `:desktopApp:run`, window 'Manijero'; the macOS accessibility tree via JXA/System Events, because host pixels are unavailable): at an 800pt window every content block is exactly 720 wide at x=88, at 1400pt the same 720 block is centred at x=388 with no overflow, and at 420pt all blocks are 372 wide at x=72 with wrapped text and no clipping - the 720dp cap is effective and centred. Every control is named (`AXDescription`: the three suggestion questions, 'Preguntar', 'Mis terrenos', 'Privacidad y ayuda') and 'Preguntar' reports AXEnabled=false with an empty composer; a merged transcript entry reads as one node ('Tú, ¿Qué obligaciones tengo por la condicionalidad?') and the failure notice's 'Reintentar' is a separate AXButton at its own position. Keyboard: with the composer focused, Shift+Tab moved focus out to the third suggestion and Space activated it (the composer filled), and Cmd+A/Backspace cleared it - reachable and activatable by keyboard. Forward Tab is consumed by the multi-line composer as a tab character (`TextFieldKeyInput`: `KeyCommand.TAB -> if (!singleLine) CommitTextCommand('\t', 1) else consumed = false`), a platform text-field behaviour rather than a defect. The Android launch frame was also captured (launch-frame-a/b.png): the platform default splash (system icon on the light background) fading over the already-rendered chat home, no dark/black frame, and the resting title sits below the status bar (visual_foundation U4: report-only, no permanent overlap observed, no custom splash theme added).
- Honest gaps (never claimed as passed): (1) the Desktop visual focus indication could not be inspected because host screen capture is blocked for the verification process (`screencapture -x` returns only the wallpaper; no ffmpeg/ffprobe/magick/PIL/Quartz available), so the default Material focus indication was relied on and, per the spec's verify-first instruction, no shared outline was added - recorded as an open item in DESIGN.md. (2) The answered live-region announcement is verified by the code path and the accepted `liveRegion`/`mergeDescendants` wiring, not by a captured TalkBack utterance (TalkBack is bound, but its speech is not logged on this emulator). (3) There is no Compose UI-test harness (spec R1/U1) and the repo refuses test-only dependencies, so merged semantics, live regions and focus order are verified by the uiautomator/AX dumps, the previews and code inspection rather than an automated UI test. (4) Desktop OS text scaling has no runtime integration, so Desktop large-text evidence is preview-based. (5) The answered/abstained/clarification device captures used a temporary non-committed probe `AnswerService` (reverted; `git status` shows no androidApp change) because the shipped default is `UnavailableAnswerService` (no `/ask` route); the scroll, touch-target, focusability and 1.0/2.0 geometry evidence was captured on the shipped build. (6) `feature_list.json`/`PROGRESS.md` carry self-verification only; the feature is explicitly NOT marked accepted - independent validation is the next step.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/chat_accessibility.md). It re-ran the contract validator, the focused TranscriptScrollTest (8/0), :shared:jvmTest --rerun-tasks (192/0, 21 suites, +8, none removed or renamed), :shared:testAndroidHostTest --rerun-tasks (178/0), :desktopApp:build :androidApp:assembleDebug --rerun-tasks (72 tasks, fresh APK), ./scripts/init.sh --verify (exit 0, 91 tasks), and the greps; confirmed strings.xml numstat empty and git diff --check clean. It re-drove the Android emulator on an APK it rebuilt and installed itself (font_scale 1.0/2.0 with no clipping or overflow, every clickable node >= 48dp, the 'no puedo mostrar tus terrenos' fallback absent from every dump, the auto-scroll reproduced scrolling up to the newest element without reaching the page bottom) and re-drove the Desktop app through the macOS AX tree (the 720dp cap effective and centred, one merged transcript entry node, the failure notice keeping Reintentar a separate focusable button). With its own temporary 7-case probe test it independently reproduced the pure scroll key's change and non-change cases. It confirmed scope discipline (App.kt plus the two new files and the named docs only; ChatHomeState.kt, ChatConversation.kt, chat/, lands/, privacy/, theme/, strings.xml, contracts/, backend/, knowledge/, platform roots, Gradle files and scripts/init.sh untouched), no Color(0x) outside theme/, no minimum-interactive-size override, no logging, no new module/dependency/endpoint, and a feature-scoped security review with no blocking issue. Non-blocking findings recorded: N1 (the Android-dump 'merged entry' wording overstates what uiautomator exposes; the merge is observable in the Desktop AX tree), N2 (the greyscale non-colour-cue check is now recorded in the validation record), N3 (the carried gaps are recorded in aggregate rather than id-by-id), N4 (the .widthIn(max).fillMaxWidth() reorder deviates from the spec's literal 'no width change' but is documented and leaves phone rendering provably identical), N5 (the scroll key does not re-fire when the chooser's guarded read resolves, so resolved rows may need one manual scroll on a very short viewport), N6 (no Compose UI-test harness; spec R1/U1).
