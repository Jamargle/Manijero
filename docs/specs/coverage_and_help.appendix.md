# Appendix — `coverage_and_help`

Planning and verification record for [`docs/specs/coverage_and_help.md`](coverage_and_help.md).
The implementation plan, verification plan, repository research, and validator checklist currently
remain in the contract; implementation findings and feature evidence will be recorded here when the
feature is implemented. `docs/validations/coverage_and_help.md` will remain the authoritative
independent acceptance record.

## Feature evidence

Implemented the shared coverage disclosure and navigation from chat and privacy. The pinned content
identifies the currently reviewed topic areas and refusal classes, and the screen provides named
human referral paths without contact details. Repair added an independent reviewed topic expectation,
modeled the not-yet list, and added a resource-backed check that enumerates rendered strings and
rejects figures/promissory wording.

Verification actually performed:

- Repair `./scripts/init.sh --feature coverage_and_help` — failed during common test compilation due
  to unresolved symbols in unrelated existing theme/chat/land tests; it did not reach coverage tests.
- Repair `./scripts/init.sh --fast` — shared JVM tests and offline checks passed; backend pytest was
  skipped because `pytest` is not installed. This run raced with the full build below, so the
  Android/Desktop compile outcome is taken only from the serial full-gate rerun, not this run.
- Repair `./scripts/init.sh --verify` — failed at `:desktopApp:compileKotlin` with unresolved
  `lands`/`App` references in `desktopApp/main.kt` (and the shared host-test failures above).
- `python3 scripts/validate_coverage_copy.py` — initial attempt exposed that the required refusal
  phrase “te corresponde” must remain allowed when it explicitly says the app cannot determine
  eligibility; the validator was narrowed to forbid numeric/legal facts and promises. Rerun passed:
  all 17 rendered resource keys exist, model topics match the independent expected set, and every
  uncovered topic is present in the not-yet copy.
- Final `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and the copy
  validator).
- Final `./scripts/init.sh --verify` — failed: JVM tests/offline suite passed, but
  `:desktopApp:compileKotlin` fails at the Desktop entry point with unresolved `lands`/`App`
  references. `pytest` remains unavailable and was skipped by the harness.
- Copy review: coverage describes topics, not promised outcomes; no intended deadline, amount,
  threshold, article number, eligibility conclusion, or invented contact detail is shown.

Not performed: Android emulator/Desktop runtime navigation smoke, font-scale 2.0 runtime inspection,
narrow/wide window inspection, keyboard traversal, and screen-reader announcement inspection. Android
`adb` is not installed (`adb: command not found`), so there is no emulator/device bridge. Desktop
runtime inspection was not performed; a buildable artifact/runtime entry point is unavailable because
the full gate cannot compile `desktopApp` due to unresolved shared imports. The previews are structural
only. No E2E/UI harness is available. The feature remains `in_progress` and is not ready for
independent validation until the checks can be completed.

### Second-validator repair — displayed copy checker

- Extended `scripts/validate_coverage_copy.py` to scan resource references in `CoverageScreen.kt`,
  `PrivacyScreen.kt`, and `App.kt`. It now validates existence and forbidden-copy rules for every
  displayed `coverage_*` resource and the reused `privacy_back` label. The allowlist is deliberately
  restricted to this feature's `coverage_*` keys plus that shared back label, so unrelated privacy
  and chat strings are not judged by the coverage-specific rules.
- Regression sensitivity: the checked display set includes navigation copy such as `coverage_open`
  and `privacy_back`, not only the coverage body rendered in `CoverageScreen`.
- `./scripts/init.sh --feature coverage_and_help` — passed: `:shared:jvmTest` and the expanded copy
  validator; validator reported 19 displayed feature resource keys.
- Feature remains `in_progress`; this repair does not supply the outstanding manual/runtime evidence
  or independent acceptance.

### Implementer repair — resource resolution and runtime options

- Updated `scripts/validate_coverage_copy.py` to validate the complete rendered `coverage_*` key set
  against `strings.xml` **before** the defined-key intersection. An explicit negative regression
  assertion feeds a rendered-but-undefined coverage key to the same validator and requires failure.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports
  19 displayed feature keys).
- Investigated Android access rather than assuming `adb` was absent: `adb` exists at
  `$HOME/Library/Android/sdk/platform-tools/adb`, but `adb devices -l` reports no attached devices.
  The SDK includes the emulator and AVD `Pixel_10a`; a headless boot was started, but no booted device
  or app interaction evidence is available yet.
- Retried `./gradlew :desktopApp:compileKotlin --no-daemon`: still fails at the unrelated Desktop
  entry point `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` (`lands`, `LandRepository`,
  `FileLandStorage`, and `App` unresolved; line 16 type inference also fails). Not changed as part of
  this focused repair.
- Runtime/accessibility criteria are **not objectively impossible in this environment**: an emulator
  executable and AVD are present, so the Android check may be achievable after boot. Desktop runtime
  remains blocked by the compile failure. No verified emulator boot, install, render, accessibility,
  or navigation observation is claimed in this evidence. Feature remains `in_progress`, not ready for
  independent validation.

### Implementer repair — Android runtime attempt (2026-10-19)

- Pixel_10a was available as `emulator-5554`; `$HOME/Library/Android/sdk/platform-tools/adb shell
  getprop sys.boot_completed` returned `1`, and `adb emu avd name` returned `Pixel_10a`.
- `./scripts/init.sh --android` passed (`:androidApp:assembleDebug`). Installed
  `androidApp/build/outputs/apk/debug/androidApp-debug.apk` with `adb install -r`; result `Success`.
  Started `com.jamarglex.manijero/.MainActivity`; it opened the chat home.
- `uiautomator dump` of the home showed separate, focusable controls with accessible visible text
  “Privacidad y ayuda” and “Qué cubre la app”. Tapping the latter opened the coverage screen with no
  question or land setup. Its dump exposed the title, intro, all covered-topic lines and refusal
  classes. Scrolling exposed “Dónde pedir ayuda”, the office/cooperative referral, “Ver privacidad y
  ayuda”, and “Volver”. Pressing Android Back returned to the chat home. Dumps were saved locally at
  `/tmp/manijero-coverage/{home.xml,coverage-default.xml,coverage-scroll.xml}` (ephemeral, not committed).
- A `font_scale=2.0` runtime attempt was made and the home was relaunched; the coverage control was
  below the initial viewport and the attempted fixed-coordinate tap did not open it. Therefore this
  does **not** establish large-text coverage-screen rendering or absence of clipping. Font scale was
  restored to `1.0` afterward. No TalkBack session or Desktop keyboard/screen-reader traversal was
  performed; UIAutomator's visible text/focusable control data is not a screen-reader announcement
  test.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and
  `validate_coverage_copy.py`, reporting 19 displayed feature resource keys).
- Desktop remains blocked: the prior serial `./gradlew :desktopApp:compileKotlin --no-daemon` fails
  in the unrelated `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` entry point with
  unresolved `lands`, `LandRepository`, `FileLandStorage`, and `App` references (plus line 16 type
  inference failure). This is not a narrow feature-owned configuration issue, so it was not changed.
- Android regular-size navigation smoke is observed; large-text layout, keyboard traversal,
  screen-reader announcements, narrow/wide Desktop rendering, and Desktop runtime remain unverified.
  Feature stays `in_progress`, not ready for independent validation.

### Implementer repair — fontScale 2.0 Android inspection (2026-10-19)

- Confirmed `emulator-5554` is the `Pixel_10a` AVD and set Android system `font_scale` to `2.0`.
  Relaunched the installed app; the home coverage control was below the first viewport, so scrolled
  the home screen to its lower controls and opened “Qué cubre la app”.
- Inspected the coverage screen at the enlarged text setting in stages while scrolling. The
  scrollable viewport exposed the title/intro, all five covered-topic entries, all refusal copy and
  uncovered-topic list, human-help heading/body, privacy cross-link, and `Volver`. Text wrapped across
  the available width and continued below the viewport; the final referral and both controls were
  visible after scrolling, with no observed truncation/clipping. Android `uiautomator` dumps were
  collected at `/sdcard/coverage-font2.xml`, `/sdcard/coverage-font2-scroll.xml`, and
  `/sdcard/coverage-font2-end.xml` (device-local, not committed). Font scale was restored to `1.0`.
- TalkBack sanity was not performed: `settings get secure enabled_accessibility_services` returned
  `null` (no accessibility service enabled). UIAutomator text/focusable-node exposure is not a
  substitute for a spoken announcement check.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and the copy validator,
  reporting 19 displayed feature resource keys).
- Desktop narrow/wide and keyboard/focus inspection remain unavailable because the Desktop entry
  point still fails compilation on the unrelated unresolved `lands`/`LandRepository`/
  `FileLandStorage`/`App` references documented above. No unrelated entry-point repair was attempted.
- No feature-owned clipping fix was indicated by this inspection. TalkBack and Desktop checks remain
  gaps; feature status remains `in_progress`, not ready for independent validation.

### Implementer repair — TalkBack and Desktop dependency diagnosis (2026-10-19)

- Confirmed `emulator-5554` is online and TalkBack is installed (`com.google.android.marvin.talkback/.TalkBackService`). Enabled the service through Android secure settings and verified it acquired speech audio focus during the app launch/touch attempt. However, the emulator provides no way in this session to hear or transcribe the generated speech, and logcat contains service/audio-focus diagnostics rather than the spoken announcement text. Therefore this is evidence the service can be enabled and speak, **not** a recorded screen-reader announcement check. Restored both accessibility secure settings to their original unset state afterward.
- Re-ran `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and the copy validator, 19 displayed feature resource keys).
- Re-ran `./gradlew :desktopApp:compileKotlin --no-daemon` — still fails in `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` on unresolved `lands`, `LandRepository`, `FileLandStorage`, and `App`. Verified the imports match the package declarations and that `desktopApp` declares `implementation(project(":shared"))`; source files exist in `commonMain`/`jvmMain`. Further inspection found `shared/build/libs/shared-jvm.jar` contains only Compose resources, and `shared/build/classes/kotlin/jvm/main` contains only the Kotlin module metadata (no class files), although the shared JVM compile tasks report up-to-date. This points to absent/stale shared JVM outputs or project variant wiring, rather than an import typo. The cause is not conclusively established and changing shared/Desktop build wiring would reach beyond this coverage-screen repair, so no build configuration or entry-point code was changed. Next useful diagnostic is a clean serial shared JVM/Desktop rebuild, then inspect the resulting shared jar and dependency variant before deciding on a narrow build fix.
- TalkBack utterances, Desktop runtime, narrow/wide Desktop rendering, and keyboard focus remain unverified. Feature remains `in_progress`, not ready for independent validation.

### Implementer repair — clean serial shared JVM/Desktop rebuild (2026-10-19)

- Ran `./gradlew :shared:clean :desktopApp:clean --no-daemon --max-workers=1` — passed. This
  cleanup was limited to Gradle build outputs.
- Ran `./gradlew :shared:jvmJar :desktopApp:compileKotlin --no-daemon --max-workers=1
  --rerun-tasks` serially — passed. `:shared:compileKotlinJvm` and `:shared:jvmJar` executed, then
  `:desktopApp:compileKotlin` succeeded; the prior missing-class/unresolved-symbol failures were
  resolved without source or build-wiring changes.
- Ran `./gradlew :desktopApp:build --no-daemon --max-workers=1` — passed, including the shared JVM
  jar dependency and Desktop app jar.
- Ran `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and
  `validate_coverage_copy.py`, 19 displayed feature resource keys).
- Started `./scripts/init.sh --desktop` as the Desktop runtime smoke attempt. This command is
  long-running; no observable render or navigation result was captured in this session. Consequently
  narrow/wide rendering, keyboard traversal/focus, and Desktop navigation remain unverified. No
  unrelated source changes were made.
- TalkBack: the prior attempt enabled TalkBack and confirmed speech audio focus, but this environment
  cannot hear or transcribe its output. No observable announcement evidence was obtained; this is
  still not a screen-reader announcement check.
- The clean rebuild resolves the stale/missing shared JVM output condition; it does not by itself
  establish the manual Desktop/accessibility acceptance checks. Feature remains `in_progress`, not
  ready for independent validation.

### Implementer repair — Desktop runtime launch and GUI observation (2026-10-19)

- `./scripts/init.sh --desktop` reached a successful `:desktopApp:build` (the shell exceeded its
  short 1-second foreground allowance after Gradle emitted successful build tasks). Launched the
  actual app with `./gradlew :desktopApp:run --no-daemon`; its live Java process exposed a window
  titled “Manijero”, 800×600 at screen position (48,81).
- Captured the actual screen after bringing the Java app to front. It showed the chat home with
  title, intro, three suggestion controls, question field, and “Mis terrenos”. Privacy/coverage
  navigation controls were below the visible part of the window. This observes only home, not either
  destination.
- Attempted keyboard `Tab` through AppleScript/System Events. Java was not reliably kept frontmost
  by the automation; the subsequent capture showed Safari frontmost. This was not a valid keyboard
  traversal or visible-focus test. Screen capture worked, but dependable pointer click/resize
  automation and Desktop accessibility-tree traversal were unavailable in this session. Narrow/wide
  rendering and coverage/privacy navigation are therefore not asserted.
- Screen-reader check: not performed on Desktop because no observable/readable utterance output path
  was available. The earlier Android TalkBack attempt remains recorded above; it also yielded no
  observable utterance text.
- The temporary screen capture was removed from the repository. Android runtime/navigation and
  font-scale observations above are preserved unchanged.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and copy validator,
  19 displayed feature resource keys).
- Desktop is buildable and launched, but coverage/privacy navigation, narrow/wide rendering,
  keyboard/visible-focus, and observable screen-reader checks remain unverified. Feature remains
  `in_progress`, not ready for independent validation.

### Implementer repair — native macOS Desktop interaction attempt (2026-10-19)

- Reused the running Desktop app (`java`, window title `Manijero`). Native macOS `System Events`
  automation succeeded in focusing it, querying its accessibility hierarchy, and resizing its window;
  the observed window bounds changed from 800×600 at (48,81) to 1200×850 at (100,60). A 480×650
  resize was also requested.
- Used accessible button descriptions to open “Qué cubre la app” from chat. The native accessibility
  tree exposed the coverage title, intro, all five covered-topic lines, each refusal class, the
  not-yet topic list, human-help body, and both navigation buttons. Clicked “Ver privacidad y ayuda”;
  the next tree query showed the privacy cross-link and “Volver”. Clicked “Volver” and verified the
  chat-home action labels returned, then reopened coverage. This verifies native-tree navigation,
  not a visual screenshot or speech output.
- The requested narrow/wide window sizes were applied, but their rendered appearance, clipping, and
  responsive layout were not visually verified. `screencapture -x` could not write a capture
  (`cannot write file to intended destination`) and the screenshot was not available for review.
- Sent two Tab key events to the Java process; its accessible button list still reported coverage's
  two buttons, but macOS automation did not expose a focused-element attribute (`Can’t get attribute
  "AXFocusedUIElement" of window "Manijero"`). Thus keyboard traversal and visible focus are not
  established. No VoiceOver utterance output was obtained; an accessibility tree is not a substitute
  for spoken screen-reader verification.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports
  19 displayed feature resource keys).
- Remaining gaps: visual narrow/wide Desktop inspection, verified focus appearance, and screen-reader
  output. Feature remains `in_progress`, not ready for independent validation.

### Final implementer attempt — macOS visual, focus, and announcement evidence (2026-10-19)

- Native AX-tree evidence above confirms navigation/content only; it does not establish visual layout, visible keyboard focus, or spoken announcements.
- No screenshot was successfully obtained for review at narrow or wide window dimensions. Prior `screencapture -x` failed to write its destination; no alternative visual observation was available. Thus clipping/layout remain unverified, not observed defects.
- Tab events did not yield an inspectable focused element or visible focus state through available automation. Keyboard traversal/focus remain unverified, not a demonstrated product defect.
- VoiceOver utterance output could not be made observable/transcribable. The AX tree is structural evidence only, not announcement evidence. Screen-reader behavior remains unverified, not a demonstrated defect.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports 19 displayed feature resource keys).
- No code or acceptance criteria changed. Feature remains `in_progress`, not ready for independent validation while these checks remain unresolved.

### Implementer repair — native macOS keyboard/accessibility retry (2026-10-19)

- Re-ran `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports 19 displayed feature resource keys).
- Used native AppleScript/System Events against the live Desktop app (`java`, window “Manijero”). Confirmed it is frontmost and queried its native accessibility hierarchy; the coverage screen's text and controls are exposed. Sent a native Tab key event and requested the window's `AXFocusedUIElement` attribute. System Events returned `Can’t get attribute "AXFocusedUIElement" of window "Manijero" of process "java"` (error -1728). This prevents verifying which element received focus and whether focus is visibly indicated; it does not show a keyboard traversal failure.
- No VoiceOver interaction/utterance was observable in the session. Native AX hierarchy contents are not evidence of spoken announcements, so screen-reader announcements remain unverified.
- Desktop narrow/wide visual evidence is recorded immediately above and remains closed. No source change was indicated by this attempt. Keyboard traversal with visible focus and screen-reader announcements are still the only known open validator criteria; feature remains `in_progress`, not ready for independent validation.

### Implementer repair — native macOS screenshot and visual inspection (2026-10-19)

- Re-ran `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports 19 displayed feature resource keys).
- Used native macOS `screencapture -x` after focusing the actual running Java Desktop window through System Events. Unlike the earlier failed capture, this succeeded. Directly inspected the coverage screen at 1200×850 (wide) and after resizing the window to 480×650 (narrow). Both screenshots show the entire disclosure including the two navigation controls; at narrow width the content wraps naturally and remains within the window, with no observed clipping or horizontal overflow. Screenshots were temporary under `build/` and are not retained as feature artifacts.
- This direct visual observation closes the Desktop narrow/wide visual-inspection blocker; it does not establish keyboard traversal/visible focus or screen-reader output. Previous Tab attempts still yielded no inspectable focused element, and no VoiceOver utterance output was observable. No owner disposition is recorded in the spec, and none is presumed.
- Focused verification remains green. Feature stays `in_progress` and is not ready for independent validation: keyboard/focus and spoken announcement checks remain unresolved. Stop here pending an observable native accessibility path or explicit owner disposition.

### Implementer repair — alternate macOS focus/VoiceOver attempt (2026-10-19)

- Retried native focus inspection using System Events via AppleScript, querying the front window
  directly (`get value of attribute "AXFocusedUIElement" of front window`) after confirming the
  running Java app's window is named “Manijero”. macOS again returned error -1728: it cannot get the
  `AXFocusedUIElement` attribute. This alternative query does not verify the focused control or
  visible focus; it is not evidence of a traversal failure.
- Attempted to activate VoiceOver using `osascript -e 'tell application "VoiceOver" to activate'`;
  command returned without output. Queried VoiceOver by name successfully, but no observable
  speech-caption/utterance output path was available in this session. Enabling/identifying VoiceOver
  is not evidence of an announcement, and no utterance is claimed.
- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports
  19 displayed feature resource keys).
- Keyboard traversal with visible focus and screen-reader announcements remain unverified. No source
  behavior change is indicated by these failed observation routes. No product-owner disposition or
  approval is present; a disposition is needed if acceptance is to proceed without this evidence.
  Feature remains `in_progress`, not ready for independent validation.

### Product-owner disposition — accessibility evidence (2026-10-19)

- Explicit product-owner instruction: “Approve this feature and do not do any more accessibility
  validations until I ask for them”. Recorded as a disposition to proceed without further accessibility
  validation; this is not evidence that the unmet criteria passed.
- Keyboard traversal/visible focus and screen-reader announcements remain **unverified**, not passed.
  No further accessibility validation was performed after this instruction.
- Re-ran `./scripts/init.sh --feature coverage_and_help` on 2026-10-19 — passed (`:shared:jvmTest`
  and `validate_coverage_copy.py`, 19 displayed feature resource keys). This confirms focused
  verification evidence remains current.
- Feature status and acceptance record are intentionally unchanged; independent validator
  reassessment remains next.
