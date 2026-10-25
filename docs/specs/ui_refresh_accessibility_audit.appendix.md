# Appendix — `ui_refresh_accessibility_audit`

Planning and verification record for [`ui_refresh_accessibility_audit.md`](ui_refresh_accessibility_audit.md). The acceptance record belongs in `docs/validations/ui_refresh_accessibility_audit.md`.

## Repository research

- `AGENTS.md`, `PROGRESS.md`, `DESIGN.md`, `CONSTRAINTS.md`, `feature_list.json`: shared Compose UI is in `commonMain`; preserve plain Spanish, shared behavior, and evidence honesty. Progress identifies outstanding manual reviews and host-only screenshot limits.
- `docs/design/ui-refresh-plan.md` P2-17…P2-20 and P3-01…P3-10: wide/dark/large-text/keyboard-screen-reader per-screen checks, automated/full gates, Android/Desktop evidence, optional iOS compile and low-digital-confidence check.
- `DESIGN.md` records shell, chat, lands, Help/Privacy layouts and general accessibility requirements. It also documents that 2× text and keyboard/screen-reader/device audits are not generally established by host goldens.
- Accepted screen contracts and evidence inspected: `chat_accessibility.md/.appendix.md`, `chat_screen_refresh.md/.appendix.md`, `lands_screens_refresh.md/.appendix.md`, `help_privacy_refresh.md/.appendix.md`, `land_form_accessibility.md`, `app_chrome_navigation.md`. These own behavior; audit findings must not silently replace their contracts.
- `docs/screenshot-regression.md`: current local gate comprises 34 Desktop and 30 Robolectric Android host captures; read-only `:shared:verifyScreenshots`; no CI, device, accessibility, or usability proof. Recording is a separate reviewed action.
- Existing relevant tests include theme contrast (`shared/src/commonTest/.../theme/ManijeroColorsTest.kt`), navigation, chat interactions (`shared/src/jvmTest/.../chat/ChatHomeInteractionTest.kt`), land interactions (`.../lands/LandScreenInteractionTest.kt`), screenshot suites and screenshot fixtures. No dedicated Compose UI accessibility-test framework is present in the inspected test inventory.
- Current focused harness supports `./scripts/init.sh --feature <id>` and parses fenced commands; `--fast` runs shared JVM tests/contracts/catalog/evaluators; `--verify` adds Android host tests and Android/Desktop builds. `:shared:verifyScreenshots` is a local host render gate.
- Feature size: correctly scoped as one cross-cutting audit with bounded remediation of discrete defects, no new data model or user flow. It is evidence-heavy; redesigns or unrelated defects must be split/escalated.

## Audit matrix

Record exact state, environment, viewport, scale, appearance, observed result and artifact/reference. Each cell is **pass**, **defect fixed**, **blocked**, or **not performed**; never infer a pass from a preview. This environment's attempted live checks and their consequence are recorded below; host goldens are not substituted for any direct check.

| Surface/state | Compact / 2× | Wide | Dark | Keyboard / focus | Screen reader / semantics |
|---|---|---|---|---|---|
| Shell + Assistant: idle, suggestions, answer/source, abstention, working, failure, chooser | Android + Desktop | Desktop | Both | Desktop controls/order | Android TalkBack/tree; Desktop AX if available |
| Lands: empty, populated, search/no-results, load/retry | Android + Desktop | Desktop | Both | search/actions | names, counts, action identity |
| Add/Edit: validation and saved values | Android + Desktop | Desktop | Both | field order, focus/error | required/optional and errors |
| Remove: confirmation, cancel, confirm | Android + Desktop | Desktop | Both | safe initial focus, cancel/confirm | selected land and destructive action name |
| Help + Privacy; cross-links/back restoration | Android + Desktop | Desktop | Both | links/back | heading/section and disclosure names |

### Attempted direct-check matrix (2026-10-25)

Environment: macOS host; Android target is unavailable to the shell. Each surface cell below covers the states named in its matrix row (not every possible application/backend outcome). “Not performed” is not a pass. No direct evidence artifact was produced.

| Surface/state | Android compact 320 dp / 2×, 1× comparison, light/dark | Android wide, light/dark | Android keyboard, semantics/tree, TalkBack, destructive focus | Desktop 800×600 and 1280×800, light/dark and 2×/320 dp where constrainable | Desktop keyboard/focus, AX/names/headings/announcements/destructive focus |
|---|---|---|---|---|---|
| Shell + Assistant (idle, suggestions, answer/source, abstention, working, failure, chooser) | **Not performed** — `command -v adb; adb devices -l`: `adb: command not found` (exit 127); no Android target to set viewport/scale/appearance or inspect states. No clipping/reachability conclusion. | **Not performed** — same missing `adb`; no Android wide target. | **Not performed** — same missing `adb`; no TalkBack session or Android accessibility tree available. | **Not performed** — `./scripts/init.sh --desktop` invoked `:desktopApp:run` but exceeded the 30 s command timeout; no live window/capture was obtained. `pgrep -fl 'desktopApp|Manijero'` found no process and `osascript` found no Manijero process. No viewport, appearance or scaling observation. | **Not performed** — attempted `osascript -e 'tell application "System Events" to get name of every process whose name contains "Manijero"'`; it returned no process. No live UI to traverse or inspect, and no AX tree/focus evidence. |
| Lands (empty, populated, search/no-results, load/retry) | **Not performed** — `adb` absent (command above); no state or viewport inspection. | **Not performed** — `adb` absent; no wide inspection. | **Not performed** — `adb` absent; no tree/TalkBack or action-name check. | **Not performed** — Desktop launch attempt timed out with no surviving process/window; no state, viewport, scale or appearance observation. | **Not performed** — no live process for keyboard traversal or AX inspection; named controls/counts unverified. |
| Add/Edit (validation and saved values) | **Not performed** — `adb` absent; no live form, scale, validation or scroll check. | **Not performed** — `adb` absent; no wide form check. | **Not performed** — `adb` absent; field order, error announcements and focus behavior unverified. | **Not performed** — launch attempt timed out/no process; no form interaction, viewport or appearance check. | **Not performed** — no live form for keyboard/focus/AX inspection; field names and errors unverified. |
| Remove (confirmation, cancel, confirm) | **Not performed** — `adb` absent; no device state. | **Not performed** — `adb` absent; no wide state. | **Not performed** — `adb` absent; safe initial focus and spoken destructive target unverified. | **Not performed** — launch attempt timed out/no process; no confirmation inspected. | **Not performed** — no live UI for keyboard/focus or AX inspection; initial focus unverified. |
| Help + Privacy; cross-links/back restoration | **Not performed** — `adb` absent; no route/back inspection. | **Not performed** — `adb` absent; no wide route inspection. | **Not performed** — `adb` absent; headings, link names and announcements unverified. | **Not performed** — launch attempt timed out/no process; no live route, viewport or appearance evidence. | **Not performed** — no live UI for keyboard/back/focus/AX inspection; section names and link semantics unverified. |

`xcrun simctl list devices available` was also run and listed iOS simulators only; it does not provide an Android target and does not enable Android UI checks. The timed-out Desktop launch is not evidence of successful launch or visual behavior. These checks are individually unavailable in this execution environment, not asserted to be universally impossible. To resolve: provide Android SDK/platform-tools and a booted emulator (or device), and a Desktop session in which the application window is available for direct inspection and accessibility APIs can be queried. Participant review requires a separately available willing reviewer; no review was attempted or simulated.

Required target sizes: Android 320 dp wide and compact phone; Desktop 800×600 and 1280×800 (also 320 dp width where the window can be constrained). Use system font scale 2 where supported. Include representative 1× baseline. Wide checks verify adaptive rail and capped/centred content per the current design contract.

## Implementation plan and tasks

1. Confirm dependencies remain accepted and inspect current diffs, contracts and screenshots. Populate the matrix with target paths/states; avoid duplicating behaviors already proven by pure tests.
2. Run focused automated checks and inspect their output before manual work. Run contrast/design-system tests and all relevant screenshot tests read-only.
3. Android: install current debug build, inspect representative/all matrix states at 1× and 2× in light/dark at compact and wide sizes; verify scroll reachability, clipping, semantics/tree, TalkBack where available, touch targets, and route/back behavior. Keep artifacts local or in agreed evidence location; do not commit personal data.
4. Desktop: launch app, capture at 800×600 and 1280×800 in light/dark, traverse by keyboard and inspect focus/accessibility tree. Record any inability to capture host pixels or access the tree.
5. Apply only minimal, accepted-contract-compatible fixes for concrete blockers. Add persistent tests using existing patterns; do not add dependencies. Review each changed golden before recording and leave unrelated captures untouched.
6. Run focused and full gates as available; attempt iOS common-source compile and record toolchain limitation if unavailable. Do not treat compile as runtime accessibility evidence.
7. Conduct the owner/low-digital-confidence walkthrough only with an appropriate reviewer and consent. Record task, non-leading prompts, observed difficulty and date without claiming representative research. Otherwise leave open.
8. Update durable docs to reflect verified outcomes and open gaps; append dated evidence below. Do not update feature status/progress; independent validator owns acceptance.

## Verification plan

Automated, repository root:

```sh
./scripts/init.sh --feature ui_refresh_accessibility_audit
./scripts/init.sh --fast
./scripts/init.sh --verify
./gradlew :shared:compileKotlinIosSimulatorArm64
```

Focused `:shared:jvmTest :shared:verifyScreenshots` is the required cheapest available command touching shared tests and both screenshot renderers. Run `--fast`/`--verify` additionally as environment permits; report exact failures and pytest/SDK limitations. Use `:shared:recordScreenshots` only after intentional visual differences are reviewed, then rerun verification. The feature must not start a long-running server.

Manual: use the matrix above. Store screenshots and structured notes under an agreed non-sensitive evidence location; state whether each capture is emulator/device or Desktop app, not Robolectric. Verify no new status meaning is conveyed by color alone, and focus is not lost or assigned to a destructive action on entry. Compare coverage/privacy disclosure facts and land/chat behavior to owning contracts when testing.

## Evidence to capture

- Commands, exit status, relevant test counts, toolchain and environmental limitations.
- Per-cell result and specific observation; platform/OS, app build, viewport, font scale, appearance, route/state.
- Android emulator screenshots/accessibility-tree excerpts and TalkBack observations if available; Desktop screenshots, keyboard traversal/focus and AX evidence if available.
- Changed golden filenames, full-size visual review, and confirmation unrelated baselines were not recorded.
- Every defect, minimal fix, regression test and owning contract compatibility check.
- Participant review method/outcome only if actually conducted; otherwise explicit outstanding status.
- iOS compile outcome separately from any runtime/platform claim.

## Feature evidence

<!-- Implementer: append dated evidence. Leave independent acceptance to the validator. -->

### 2026-10-25 — implementer repair and self-verification

- **Scope/result:** Reviewed the accepted screen contracts, `DESIGN.md`, existing accessibility and interaction tests, and the 34 Desktop / 30 Android-host screenshot inventory. No in-scope defect was established by available automated evidence; no code or golden was changed. This is not a claim that the audited UI is accessible.
- **Focused:** `./scripts/init.sh --feature ui_refresh_accessibility_audit` — rerun exit 0; `:shared:jvmTest` and read-only `:shared:verifyScreenshots` passed. All 34 Desktop and 30 Robolectric Android screenshot cases passed, including compact 2× captures, dark variants, shell, chat, lands, Help/Privacy and component gallery. These are host-render regression observations only, not device or interaction evidence.
- **Fast:** `./scripts/init.sh --fast` — rerun exit 0; all 9 offline checks (shared JVM test, contract examples, source catalog, and five evaluators plus backend test slot) completed; pytest backend suite was explicitly skipped because pytest is not installed. Evaluator metrics are synthetic/report-only.
- **Full:** `./scripts/init.sh --verify` — rerun exit 0; Android host tests, `:androidApp:assembleDebug`, and `:desktopApp:build` passed. Backend pytest was likewise skipped for missing pytest.
- **iOS compile:** `./gradlew :shared:compileKotlinIosSimulatorArm64` — exit 0. Compile-only evidence, not iOS runtime evidence.
- **Direct attempts:** The per-surface matrix above records `command -v adb; adb devices -l` (exit 127; `adb` missing), `./scripts/init.sh --desktop` (reached `:desktopApp:run`, exceeded 30 seconds, produced no inspected window), `pgrep -fl 'desktopApp|Manijero'` (no matching process), `osascript` System Events process query (no Manijero process), and `xcrun simctl list devices available` (iOS simulators only). Consequence: every Android live layout/appearance/semantics/TalkBack cell and every Desktop live layout/keyboard/AX cell remains not performed, per surface/state; the exact cell consequences are in the matrix. No device screenshot or accessibility-tree extract exists. Host goldens do not fill these cells.
- **Participant:** No low-digital-confidence/owner review was conducted or attempted; appropriate reviewer availability was not established. It remains open; no comprehension or usability claim is made.
- **Environment:** `pytest` is missing, so the fast/full backend pytest slot was skipped as stated above. The iOS target compile is compile-only evidence and unrelated to Android/Desktop accessibility.
- **Docs:** `DESIGN.md` and the plan delivery note now state the evidence boundary and remaining manual work. No status/progress, acceptance record, source code, or screenshot baseline was changed.
- **Readiness:** automated self-verification passed, but direct Android/Desktop and assistive-technology audit remains incomplete. The per-surface check cells now document each attempted tool/command and consequence. Not ready for accessibility acceptance; next step is a fresh validator review of this evidence and, if available, a session with Android platform-tools/emulator and a directly inspectable Desktop window, followed by the participant review if a suitable reviewer is available.

### 2026-10-25 — repository-owner validation and acceptance

- **Human validator attestation:** The repository owner explicitly took the validator role and reported personally checking the refreshed UI in person, validating all changes, and finding the accessibility behavior acceptable. The owner requested no additional evidence artifacts. No per-screen observations, device/build details, or review artifacts were supplied; the coding agent did not observe the in-person review. This acceptance is recorded as the owner's decision, not as independently observed evidence by the coding agent.
- **Automated verification after base update:** `./scripts/init.sh --feature ui_refresh_accessibility_audit` passed after incorporating `origin/main` at `15de146ce45b5f1c94bf41ea85efa778a049f5e7`. Shared JVM tests passed; all 34 Desktop and 30 Android-host screenshot comparisons passed. The check was read-only; no golden was recorded or changed. Screenshot tests remain pixel regression checks, not accessibility proof.
- **Limits:** The prior attempt matrix remains as historical detail; this later owner sign-off is not cell-by-cell documented. Low-digital-confidence participant review remains open, and no usability-research or formal accessibility-certification claim is made.
- **Outcome:** Accepted by the repository owner acting as validator. No product code or screenshot baselines changed; durable records and feature status were updated to reflect the owner's decision and its evidence limits.

## Validator checklist

- [x] All current dependencies are accepted; the repository owner validator reports reviewing the refreshed UI in person and accepting the audit.
- [x] Compact/2× and wide/dark checks were included in the owner's in-person review according to the owner; detailed per-cell evidence was not supplied or requested.
- [x] Keyboard/focus and screen-reader behavior were included in the owner's in-person accessibility validation according to the owner; no agent-observed artifacts are claimed.
- [ ] Concrete defects were fixed minimally with persistent tests where feasible; accepted copy, routing, data and contracts were not changed unintentionally.
- [x] Focused verification passed after updating from main; no screenshot baselines changed. Fast/full historical outcomes and pytest limitation remain reported accurately.
- [x] Low-digital-confidence/user review remains explicitly open; no usability claim is made.
- [x] Durable docs distinguish owner attestation from agent-observed evidence and screenshot regression from accessibility proof; feature status changed after the owner's explicit validation decision.
