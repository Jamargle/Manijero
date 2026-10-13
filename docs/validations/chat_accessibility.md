# Validation — `chat_accessibility`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted `chat_accessibility`
implementation against `docs/specs/chat_accessibility.md`.

Feature id: `chat_accessibility`. Spec: `docs/specs/chat_accessibility.md`.
Claimed status: `passing` (self-verified by the implementer). State update: the orchestrator sets
`status` to `accepted` and records concise evidence.

The validator did not implement or repair anything in the product. It re-read the diff, re-ran the
acceptance checks, re-drove the Android emulator on an APK it rebuilt itself, re-drove the Desktop
app through the macOS accessibility tree, and applied the rubric/security criteria from the
`feature-validator` skill body (its `references/` files are absent in this worktree).

## Review target

`git status --porcelain` before and after validation showed exactly the implementer's footprint
(unchanged by validation; a temporary validator probe test was deleted again):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`.
- New (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/TranscriptScroll.kt`.
- New (tests): `shared/src/commonTest/kotlin/com/jamarglex/manijero/TranscriptScrollTest.kt`.
- New (docs): `docs/specs/chat_accessibility.md` (planner artifact).
- Modified (docs/harness): `CONSTRAINTS.md`, `DESIGN.md`, `docs/specs/land_clarification.md`,
  `docs/specs/response_states.md`, `feature_list.json`, `PROGRESS.md`.

Untouched, as the spec's "do not modify" list requires: `ChatHomeState.kt`, `ChatConversation.kt`,
`chat/`, `lands/`, `privacy/`, `theme/`, `strings.xml`, `contracts/`, `backend/`, `knowledge/`,
`androidApp/`, `desktopApp/`, `shared/src/iosMain/`, every Gradle file and the version catalog, and
`init.sh`. No test file was modified (only the new one added), so no previously passing test changed.
`git diff --check` clean. No new module, dependency, ViewModel, navigation, permission, endpoint, or
logging.

## Independent checks and results

Re-run by the validator with `--rerun-tasks` where relevant, so results are real executions:

- `python3 contracts/validate_examples.py` → exit 0, "Validated 2 request and 3 response examples
  against answer_api_contract".
- Focused `:shared:jvmTest --tests "com.jamarglex.manijero.TranscriptScrollTest"` → 8 tests /
  0 failures / 0 errors (report XML).
- `:shared:jvmTest --rerun-tasks` → **192 tests / 0 failures** (21 suites; was 184 / 20 suites at
  `land_data_disclosure`). Every prior suite is present with its prior count (`ChatHomeStateTest` 44,
  `ChatConversationTest` 16, `CitationPresentationTest` 23, `LandContextBuilderTest` 16,
  `ManijeroColorsTest` 10, `LandDataDisclosureTest` 3, …) and the +8 is `TranscriptScrollTest`; no
  test was removed or renamed.
- `:shared:testAndroidHostTest --rerun-tasks` → **178 tests / 0 failures** (17 suites; was 170).
- `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL, 72 actionable
  tasks executed, fresh `androidApp-debug.apk`.
- `./init.sh --verify` → **exit 0**, BUILD SUCCESSFUL (91 actionable tasks).
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include="*.kt" | grep -v /theme/`
  → no matches (every hex stays in `theme/ManijeroColors.kt`).
- `grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src`
  → no matches. Logging grep (`println|Log\.|Logger|printStackTrace|NSLog|System\.out` over
  `shared/src androidApp/src desktopApp/src`) → no matches.
- `git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml` → empty: the
  whole `strings.xml` is byte-identical to the accepted file, so every accepted string is unchanged
  and no string was added.
- `git diff --check` → clean.
- **Validator's own probe test** (temporary `ZzValidatorProbeTest`, 7 cases, deleted afterwards; the
  report XML showed 7/0 before deletion) reproduced the pure key from angles the implementer's test
  does not use: the four fields mirror `messages.size`/`phase`/`failure != null`/`awaitingLandClarification`
  exactly; a `SuggestedQuestionSelected` inside an existing conversation leaves the key equal; a
  keystroke while `SUBMITTING` leaves it equal; a blank-composer `AskClicked`, a refused
  `RetryClicked` and a refused `LandChoiceSubmitted` leave it byte-identical; `RetryClicked` after a
  failure moves it back to `SUBMITTING`; equal states always produce equal keys.

### Android re-drive (real `emulator-5554`, `Medium_Phone_API_35`, 1080×2400 @ density 2.625)

The validator rebuilt and re-installed the shipped debug APK itself
(`adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk`), set
`settings put system font_scale` to 1.0 and 2.0, and dumped with `uiautomator`. Raw captures:
`build/evidence-validator/` (gitignored `build/`).

- **1.0 home**: every node inside `0..1080 × 0..2400`, no horizontal overflow; every clickable node
  is ≥126px = 48dp wide and tall (`[63,594][1017,720]`, `[63,741]…`, `[63,888]…` suggestions,
  `Preguntar` `[63,1417][351,1543]`, `Mis terrenos`, `Privacidad y ayuda` `[63,1723][1017,1849]`);
  `Preguntar` is `enabled=false` with an empty composer; every control carries its Spanish label.
- **2.0 home**: 22 nodes, **zero** overflow/clipping nodes; everything wraps in one column; the
  composer runs past the viewport (scrollable page), which is not text clipping.
- **Auto-scroll, decisive and reproduced by the validator on the shipped build** (no probe): the
  page was swiped to its very bottom at 2.0 (`Privacidad y ayuda` `[250,2197][830,2295]`, composer
  `[63,1061][1017,1517]`, `Preguntar` `[63,1570][496,1710]`, no transcript on screen), then
  `Preguntar` was tapped. The dump taken ~0.8 s later shows the newest content in view — the `Tú`
  entry tail (`Tú` label at `[105,0][183,83]`, body `[105,94][975,316]`) and the failure notice
  `[63,380][1017,1393]` with `Reintentar` `[168,1242][489,1340]` — while the composer, `Preguntar`,
  `Mis terrenos`, the privacy summary and `Privacidad y ayuda` are absent from the dump (below the
  fold). So the view moved to the newest element and neither stayed at nor jumped to the page bottom;
  the screenshot (`build/evidence-validator/tap-1.png`) shows the same frame. This matches the
  implementer's `flow7-*` record structurally (different question wording).
- **Keyboard focus survives the append**: the composer node is still `focused=true` in the dump taken
  after the failure arrived.
- **Failure notice stays non-merging**: the `Reintentar` control is its own `clickable=true,
  focusable=true` node (`[105,1221][552,1361]`) inside the notice container, not merged into the
  notice text.
- **No false chooser fallback on the surface**: the string "no puedo mostrar tus terrenos" appears in
  **none** of the validator's dumps nor in any recorded dump under `build/evidence/`.
- Two environment facts recorded honestly: taps inside the input-method window (the IME window covers
  `[0,1517]-[1080,2400]` per `dumpsys accessibility`) type characters instead of pressing the app's
  buttons — the first submit attempt failed for that reason and was repeated after dismissing the IME
  with a back key; and pressing back with no IME up leaves the app (`land_list` F3, confirmed, no
  `BackHandler` by design).
- TalkBack is bound: `settings get secure enabled_accessibility_services` →
  `com.google.android.marvin.talkback/…TalkBackService`, and `dumpsys accessibility` shows
  `Bound services:{Service[label=TalkBack, …]}`. Its spoken output is not capturable here, so the
  answered live-region *announcement* is not claimed as heard (the implementer recorded the same).

### Desktop re-drive (real `:desktopApp:run`, window "Manijero", macOS AX tree)

- **Geometry**: at a 1000pt window every content block is exactly 720 wide at x=140 (window 0..1000 →
  equal insets); at 1400pt the same 720 block sits at x=340 (centred); at 420pt all blocks are 372
  wide at x=24 with wrapped text and no overflow. So the 720dp cap is effective *and* centred, and
  the narrow layout degrades without clipping.
- **Merged entry + separate retry**: after submitting, the transcript entry is **one** node reading
  `Tú, ¿Qué es el SIGPAC y para qué sirve?` (single `AXStaticText`, `[180,236][900,308]`), while the
  failure notice's text and its `Reintentar` `AXButton` (`[196,396][316,436]`) are separate nodes.
- **Keyboard**: from the composer, Shift+Tab moved focus to the third suggestion and Space activated
  it (the composer filled with `¿Qué obligaciones tengo por la condicionalidad?`); another
  Shift+Tab + Space activated the second suggestion — reachable and activatable, in a predictable
  reverse order. Forward Tab is consumed by the multi-line composer as a literal tab character
  (independently reproduced: the field value became `"\t\t\t\t\t\t\t\t\t\t\t\t"` after tabs), a platform
  text-field behaviour, not a defect.
- **Visual focus indication: not verifiable in this environment, reproduced independently.**
  `screencapture -x` (10 MB PNG, 3024×1964) contains only the desktop wallpaper — the app window is
  not captured, because the verification process has no screen-recording permission. The AX tree
  exposes no focus/heading attributes (`AXRole=AXStaticText` for the title; `AXFocusedUIElement` is
  `AXUnknown`). Per the spec's verify-first instruction no focus outline was added and none is
  claimed; this is the same open gap the implementer recorded.
- **Greyscale / colour-only check (performed by the validator on the recorded rendered captures)**:
  `sips --matchTo "Generic Gray Gamma 2.2 Profile"` conversions of the recorded 1.0 Android captures
  (`build/evidence-validator/gray-abstained.png`, `gray-answered.png`) show the abstention carries a
  visible border **and** the explicit text state label "Sin respuesta segura" plus the scope caption
  "Tiene en cuenta todos tus terrenos.", the source cards carry all metadata, the excerpt and a
  labelled `Abrir documento oficial` button, and every control keeps a text label — no state is
  conveyed by colour alone, and nothing is clipped at 1.0.

## Spec conformance

- **Announcement policy.** `ChatAssistantCard` gained a defaulted `liveRegionMode` used by
  `ChatBubble`'s existing merged `semantics(mergeDescendants = true)` node; only the `answered` branch
  passes `LiveRegionMode.Polite` (App.kt:636-642). The `Tú` branches, the defensive
  `needs_land_clarification` branch, the working notice (`ChatNoticeBubble(..., Polite)`) and the
  abstention (unchanged) are untouched; `ChatFailureNotice` still sets only `liveRegion = Polite`
  with no merge, so `Reintentar` remains its own focusable node — confirmed on Desktop AX and in the
  Android dump.
- **Newest content into view.** The pure `TranscriptScrollKey`/`transcriptScrollKey` (Compose-free,
  `commonMain`) changes exactly at the four append points; `ChatHomeScreen` remembers the first key,
  and a `LaunchedEffect(scrollKey)` calls `bringIntoView()` on a 1dp end-of-transcript marker only
  when the key differs. The marker's non-zero height (with the `localBoundingBoxOf`/`Rect.Zero`
  reasoning) is documented beside it and in the spec's implementation finding. No
  `onGloballyPositioned`/`animateScrollTo`/hoisted scroll state remains, the composer's text/focus is
  not touched, and the page is not scrolled to its bottom.
- **Chooser loading state.** `clarificationLands` is `List<Land>?` in `App()` and `ChatHomeScreen`
  (`null` = unresolved), starts `null`, and is only assigned inside the guarded
  `LaunchedEffect { runCatching { landRepository?.list().orEmpty() }.getOrElse { emptyList() } }`;
  `LandClarificationChooser`'s `when` renders `Unit` for `null`, the accepted
  `chat_home_clarification_no_lands` fallback only for a resolved empty/failed list, and rows +
  `Continuar` otherwise. The fallback is therefore unreachable before the read resolves (it can only
  be reached after the effect assigns), and copy is unchanged (`strings.xml` byte-identical).
- **Wide/narrow layout.** The outer content `Column` gained
  `horizontalAlignment = Alignment.CenterHorizontally` and the five top-level blocks use
  `.widthIn(max = ContentMaxWidth).fillMaxWidth()`. The reorder is a **deviation from the spec's
  literal "no width change"** and is justified: with `fillMaxWidth()` first the 720dp cap was
  ineffective (the fill hands an exact width down, so `widthIn(max)` could not shrink it), so
  centring alone would have been invisible. Measured: 720 centred at 1000pt/1400pt (**new**), 372 at
  420pt (**unchanged**), and the phone rendering is provably identical because for any available
  width ≤ 720dp both orders yield the same exact width (verified on the emulator at 1.0 and 2.0).
- **Heading.** `Modifier.semantics { heading() }` is present on the `chat_home_title` `Text`. Neither
  `uiautomator` nor the Desktop AX bridge exposes a heading flag in this toolchain, so this one item
  rests on source inspection of the standard Compose API (recorded as a limitation, not claimed as an
  inspected render).
- **Targets and contrast.** No minimum-size override exists (`grep` clean, which is exactly what the
  spec forbids). Every measured Android clickable node is ≥126px = 48dp. On Desktop the AX heights
  report the visual button size (for example `Preguntar` 116×40 pt) because Compose Multiplatform does
  not enforce the 48dp touch minimum on a pointer platform — a framework/platform behaviour, not a
  repo override. The accepted `ManijeroColorsTest` table is unchanged and still green (10/0).
- **Nothing else changed.** `strings.xml` numstat empty; no source file other than `App.kt` changed;
  the three transcript treatments, the per-entry `answerStatus`/`sources`/`landScope` data, the source
  cards, the scope captions and the clarification semantics are untouched (no edits in
  `ChatHomeState.kt`, `ChatConversation.kt`, `chat/`, `lands/`, `privacy/`); the reducer and
  `contracts/` are byte-unchanged; the two new previews (`widthDp = 1000`, `fontScale = 1.3f`) and
  the updated chooser previews are the only preview changes.
- **Verification plan**: every command in the spec's plan was re-run by the validator with the exact
  results above; the responses summary is consistent with the recorded values.

## Findings (non-blocking)

1. **Android dump wording overstates the merged node.** `DESIGN.md`/`feature_list.json` say the
   *Android* `uiautomator` dump shows each entry as one merged node; the dumps (the implementer's own
   `build/evidence/a11y-answered.xml` and mine) actually show a container `View` with separate
   `TextView` children. The merge *is* real and observable — the validator's Desktop AX capture shows
   one node `Tú, ¿Qué es el SIGPAC y para qué sirve?` while the non-merging failure notice keeps its
   text and `Reintentar` separate. Required change: none to the code; when convenient, reword the
   Android evidence to "the Desktop AX tree shows the merged entry; the Android dump does not expose
   merging, so on Android the merge rests on the standard Compose `mergeDescendants` behaviour".
2. **Greyscale check not named in the durable docs.** `DESIGN.md`/`PROGRESS.md` do not record the
   greyscale non-colour-cue check the spec's checklist asks for. It is satisfied in fact (this record
   adds the performed `sips` greyscale conversion of the rendered 1.0 captures); a later docs touch
   could name it.
3. **Carried gaps recorded in aggregate, not by id.** The spec's "Source metadata" gaps are closed by
   substance (auto-scroll, text-scale/small/wide-window evidence, chooser flash, `response_states`
   U2 via the spec note, `land_clarification` N2 via the spec note, `visual_foundation` U4 report-only,
   Desktop text scaling preview-only, no UI-test harness), but `chat_question_submission` F3,
   `network_error_recovery` N3/N4, `land_data_disclosure` N3/N5 and `land_list` F3 are not each named
   with a closed/open status. No unperformed check is presented as performed.
4. **Modifier-order deviation** (see Spec conformance). Justified and documented in the code comment,
   `PROGRESS.md` and this record; phone rendering stays identical, so no accepted Android behavior
   changes, but a window wider than ~768dp now shows the capped, centred column instead of a
   stretched one — exactly the spec's stated goal.
5. **The key does not re-fire when the chooser's guarded read resolves.** The spec prescribes the four
   key fields, so the resolved rows/`Continuar` never re-trigger a scroll; on a very short viewport
   the person may need one manual scroll after the rows appear. Outside the spec's requirement; a
   later slice could add a "rows resolved" field.
6. **Probe-built captures.** The answered/abstained/chooser device captures came from a temporary,
   reverted `AnswerService` probe (disclosed by the implementer); the shipped default is
   `UnavailableAnswerService` and there is no `/ask` route (carried `chat_question_submission` F1), so
   the validator could only re-drive home/working/failure on the shipped build and reused the recorded
   captures for the answered/abstained/chooser renders (both inspected, including in greyscale).
7. **Environment limits, reproduced**: Desktop visual focus indication and TalkBack speech are not
   observable here (`screencapture` yields the wallpaper only; TalkBack is bound but its utterances
   are not logged), and no Compose UI-test harness exists. None is claimed as passed.

## Security assessment

Scoped to the feature, its diff, and the directly supporting files. No relevant issue found; nothing
blocking.

- The new `TranscriptScroll.kt` is pure data and a pure function: no I/O, no logging, no state, no
  payload.
- The chooser's guarded read is unchanged in behavior: `runCatching { landRepository?.list().orEmpty() }`
  with `.getOrElse { emptyList() }` still swallows a failure without logging or rethrowing, still
  cannot fabricate a land, and the list is still filtered to the service's opaque ids
  (`landIdsToChoose`) before rendering, so an unknown id can still never be offered.
- The live-region change adds a polite announcement of the already-rendered reply text; it adds no
  data, no persistence, no permission, and no network call.
- No personal data is printed: the logging grep over `shared/src`, `androidApp/src` and
  `desktopApp/src` has no matches; the new comments contain no question, answer, or land content.
- `bringIntoView` is a UI-only scroll request; it cannot move data, composer text, or focus, and it
  does not open any external surface.
- No dependency, module, endpoint, permission, or shipped fake was added; `contracts/` and `backend/`
  are untouched, so the wire contract and the grounding rules cannot have shifted.
