# Validation — `coverage_and_help`

**Verdict: revise** (2026-10-19). The clean serial rebuild resolves the Desktop compilation issue, and focused JVM/copy checks pass. Prior Android regular-size navigation and fontScale 2.0 observations are recorded in the appendix. However, no Desktop render/navigation/keyboard observation or observable screen-reader announcement evidence exists. The spec explicitly requires those runtime checks; build success and previews are not substitutes. Keep the feature `in_progress`.

## Checks performed

- `./scripts/init.sh --feature coverage_and_help` — passed: `:shared:jvmTest` and `scripts/validate_coverage_copy.py` (19 displayed feature resource keys).
- `./gradlew :shared:clean :desktopApp:clean --no-daemon --max-workers=1` — passed.
- `./gradlew :shared:jvmJar :desktopApp:compileKotlin --no-daemon --max-workers=1 --rerun-tasks` — passed serially; shared JVM classes/jar and Desktop Kotlin compilation executed successfully.
- `./gradlew :desktopApp:build --no-daemon --max-workers=1` — passed.
- `git diff --check` — passed.
- Appendix records Android navigation at normal size and at fontScale 2.0 with staged scroll inspection. TalkBack service activity was not captured as speech/utterance evidence. Desktop runtime was launched as an attempt but no observable render or navigation result was obtained.
- Reviewed spec, current diff, content/screen/tests, copy validator, durable docs, and prior evidence. No feature-specific security/privacy issue found; no invented contact details or legal claims detected in the displayed copy review.

## Finding

1. **Medium — Desktop and screen-reader acceptance criteria remain unverified.** The feature spec requires Desktop narrow/wide rendering and keyboard-reachable controls with visible focus, plus coherent screen-reader announcements. The clean serial build proves compilation only. **Required:** run the Desktop app and record observed coverage/privacy navigation, narrow and wide layouts, keyboard traversal and visible focus; perform a screen-reader announcement sanity check with observable/captured output. If any criterion cannot be performed, obtain an explicit product-owner disposition and record it rather than treating previews/build output as evidence. Rerun focused checks and record results in the appendix and validation record.

## Security, scope, and documentation

No relevant security/privacy finding. Feature scope and `CONSTRAINTS.md`/`DESIGN.md` updates are consistent with the spec; no E2E harness exists. Keep status `in_progress`; do not mark accepted until the remaining criteria are evidenced or explicitly dispositioned.

## Reassessment — Desktop native automation evidence (2026-10-19)

**Verdict: revise.** The new native macOS automation evidence closes the previous uncertainty about Desktop navigation: it opened Coverage from chat, exposed all disclosure content in the AX tree, followed the privacy cross-link, returned to chat, and reopened Coverage. Together with Android normal-size navigation and fontScale 2.0 staged-scroll inspection, the functional flow and large-text content exposure are supported. The focused tier was rerun and passes.

This does not meet all explicit acceptance criteria. The AX tree confirms accessible content exposure, not visual layout: clipping/responsive appearance at narrow and wide widths was not inspected. The automation did not return the focused-element attribute after Tab, so keyboard traversal and visible focus are unverified. No screen-reader utterance/output was observable on either platform. As these are explicit criteria in `docs/specs/coverage_and_help.md` §Accessible and consistent, do not accept based on builds, AX tree presence, or Android UIAutomator text alone.

### Checks rerun / evidence reviewed

- `./scripts/init.sh --feature coverage_and_help` — passed: `:shared:jvmTest` and coverage copy validator (19 displayed feature resource keys).
- `git diff --check` — passed.
- Reviewed latest appendix evidence: Android regular-size navigation and fontScale 2.0 scrolling; Desktop native AX navigation and content exposure; clean serial shared/Desktop rebuild and Desktop build passed.

### Remaining acceptance blockers (medium)

1. **Desktop visual layout/clipping:** capture or otherwise directly inspect Coverage at the requested narrow and wide window sizes, including the complete scrollable content and controls; record observed clipping/overflow (or absence thereof).
2. **Keyboard and visible focus:** perform a valid keyboard traversal to/from `Volver` (and link where appropriate), with focus visibly observed. Merely sending Tab events or listing AX buttons is insufficient.
3. **Screen-reader output:** perform an announcement sanity check with observable/readable output on Android TalkBack or Desktop VoiceOver and record what is announced for headings/sections and controls. An AX/UIAutomator tree is not spoken-output evidence. If genuinely unavailable, obtain an explicit product-owner disposition as allowed by the spec and record it; absent such disposition these remain blockers.

**Required follow-up:** obtain the above evidence (or explicit disposition where the spec permits), rerun the focused tier, update the appendix and this record. Feature remains `in_progress`; no acceptance/status update is recommended now.

## Revalidation after repair attempt (2026-10-19)

**Verdict: revise.** The latest evidence and rerun do not close the remaining explicit acceptance checks. Android regular-size navigation and fontScale 2.0 staged-scroll coverage are documented; Desktop native AX navigation/content exposure is documented, but it is not visual, focus-state, or spoken-output evidence.

### Checks rerun

- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and coverage copy validator; 19 displayed feature resource keys).
- `git diff --check` — passed.
- Reviewed the current diff and latest appendix entries (native Desktop interaction and final evidence attempt).

### Remaining finding

1. **Medium — required Desktop/accessibility evidence is incomplete.** The spec requires visual narrow-window Desktop layout without clipping, keyboard-reachable controls with visible focus, and coherent screen-reader announcements. No reviewable narrow/wide render, inspectable focused element/visible focus, or observable VoiceOver/TalkBack utterance was produced. Existing AX-tree/navigation evidence establishes content exposure and routing only; builds and previews do not establish these properties. **Required:** obtain and record direct narrow/wide Desktop visual inspection (screenshot or equivalent), keyboard traversal with visible focus, and screen-reader announcement sanity output; alternatively obtain the spec-permitted explicit product-owner disposition for any genuinely unavailable check. Rerun the focused tier and update evidence.

Security review found no feature-specific concern in the displayed copy or diff; no invented contact details or unsupported legal claims were found. Durable `CONSTRAINTS.md`/`DESIGN.md` updates and focused verification block are present. No E2E/UI harness exists. Keep `coverage_and_help` `in_progress`; do not accept until these criteria are evidenced or explicitly dispositioned.

## Revalidation after visual Desktop repair (2026-10-19)

**Verdict: revise.** The updated appendix records direct narrow (480×650) and wide (1200×850) Desktop visual inspection, including naturally wrapped content and no observed clipping/overflow. This closes the prior Desktop visual-layout finding. Android navigation and fontScale 2.0 evidence remains. The two remaining accessibility criteria are explicit and still lack evidence: keyboard traversal with visible focus, and coherent spoken screen-reader announcements.

### Checks rerun

- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest`; copy validator reports 19 displayed feature resource keys).
- `git diff --check` — passed.
- Reviewed current feature diff, spec, appendix repairs, and existing validation history.

### Remaining finding

1. **Medium — keyboard/focus and screen-reader acceptance remain unverified.** The native macOS retry returns AXFocusedUIElement error -1728, which prevents observation but does not demonstrate a traversal defect; VoiceOver output remains unavailable and no utterance is recorded. AX hierarchy and screenshots do not substitute for keyboard-visible-focus or spoken-output checks. **Required:** obtain observable keyboard traversal/focus and screen-reader announcement evidence, or an explicit product-owner disposition accepting these unmet criteria. Since retries have not produced an observable route, only owner disposition can unblock acceptance without the evidence; do not infer or grant that approval here. If disposition is granted, record its explicit scope/rationale in the acceptance record and reassess; otherwise keep status `in_progress`.

Security/scope review remains clear: no relevant security/privacy issue, unsupported legal claim, or invented contact detail found. Durable docs and focused verification block are present; no E2E harness exists.

## Revalidation after product-owner disposition (2026-10-19)

**Verdict: accept, with explicit accessibility caveat.** The owner's direct instruction to approve and stop further accessibility validation resolves the prior validator blocker as an explicit disposition, as permitted by the spec's evidence rules; it does not establish that keyboard traversal/visible focus or screen-reader announcements passed. Those criteria remain **unverified**. No accessibility validation was performed after the instruction.

### Checks rerun / evidence reviewed

- `./scripts/init.sh --feature coverage_and_help` — passed (`:shared:jvmTest` and the copy validator; 19 displayed feature resource keys).
- `git diff --check` — passed.
- Reviewed implementation diff and appendix evidence, including Android navigation and fontScale 2.0, Desktop navigation/content exposure and narrow/wide visual inspection, copy review, and the explicit product-owner disposition.

### Findings and handoff

- No blocking functional, copy, security/privacy, scope, or documentation issue found. Keyboard focus and screen-reader announcements are **not passed**; approval is based on the owner's explicit acceptance of proceeding without more accessibility validation.
- No further accessibility checks should be run unless requested by the product owner.
- Focused check is current. Full-gate/backend pytest evidence has limitations already recorded in the appendix; no claim is made that pytest ran (it is unavailable in this environment). Desktop build and runtime observations are recorded there.
- Recommend updating `feature_list.json` status to `accepted` and adding the normal session-log pointer. This validator records the verdict but does not change feature status.
