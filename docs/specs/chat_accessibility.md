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

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests TranscriptScrollTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/chat_accessibility.appendix.md`](chat_accessibility.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/chat_accessibility.md` remains the authoritative acceptance record.
