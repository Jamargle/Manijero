# welcome_first_use — appendix

## Repository research

### Files inspected

- `feature_list.json` (line 103) — feature row. The dependencies are accepted, and `usability_session` depends on this feature.
- `docs/archive/MasterPlanV3.md` §16 and §17.1 #1 — the source wording: "capabilities, limits, privacy, and optional land setup".
- `docs/specs/coverage_and_help.md`, `help_privacy_refresh.md`, `land_data_disclosure.md` — define the `CR1` hand-off, the accepted copy, and the restyle rule that forbids new links (overridden here by the owner).
- `shared/src/commonMain/.../App.kt` — composition root. It builds remembered controllers and wires callbacks for `ChatHomeScreen` and `CoverageScreen`.
- `shared/src/commonMain/.../AppNavigation.kt` — `initialDestination` opens `LandList` when a repository exists. Back from Chat returns `null`.
- `shared/src/commonMain/.../chat/ChatHomeScreen.kt` — order is hero, transcript, suggestions, composer, footer. It has one `heading()` and one filled button.
- `shared/src/commonMain/.../coverage/CoverageScreen.kt` — help card, privacy `TextButton`, and an optional test-tools card that appears only when its callback is non-null.
- `shared/src/commonMain/composeResources/values/strings.xml` (lines 173–254) — the accepted source strings quoted in the copy table.
- `shared/src/commonMain/.../connection/ServiceAddress.kt`, `ConnectionController.kt` — the store interface, the guarded load/save, and the `mutableStateOf` holder pattern.
- `shared/src/androidMain/.../connection/AndroidServiceAddressStore.kt` — a separate private preferences file written with `commit()` + `check`.
- `shared/src/jvmMain/.../connection/FileServiceAddressStore.kt`, `DesktopTestBuild.kt` — the `~/.manijero/*.txt` store and path-helper pattern.
- `androidApp/.../MainActivity.kt`, `desktopApp/.../main.kt` — the host injection points.
- `shared/src/jvmTest/.../platform/AndroidBackupExclusionGuardTest.kt`, `TestBuildGatingGuardTest.kt` — guards the new store must not trip. Its regex targets `*ServiceAddressStore` only.
- `shared/src/jvmTest/.../chat/ChatHomeInteractionTest.kt`, `lands/LandBackupFlowInteractionTest.kt` — `runDesktopComposeUiTest` patterns, including full-`App` rendering.
- `shared/src/jvmTest/.../screenshots/{ChatHome,HelpPrivacy}ScreenshotsTest.kt`, `androidHostTest/.../ChatHomeAndroidScreenshotsTest.kt` — capture helpers. Existing calls use default parameters.
- `shared/src/jvmTest/.../smoke/SmokeUiScript.kt`, `androidApp/src/androidTest/.../AndroidLocalSmokeTest.kt` — both build `App(...)` without the new parameter, so the smoke tests are unaffected.
- `DESIGN.md` "Assistant surface" and "Help and privacy surfaces"; `docs/constraints/client-chat.md`; `docs/constraints/answers-and-knowledge.md` "Coverage disclosure"; `ARCHITECTURE.md` "Data and platform boundaries".

### Existing patterns to follow

- Optional host capabilities are nullable `App` parameters. A null value removes the UI entirely (`connectionTools`, `landBackupFiles`).
- Device stores are small interfaces in commonMain with platform adapters in shared `androidMain`/`jvmMain`. Callers wrap every store call in `runCatching`, and nothing is logged.
- Screen composables take nullable or defaulted callbacks so previews, goldens, and tests stay unchanged.
- Copy lives in `strings.xml`. Tests reference keys and never restate strings in Kotlin product code.

### Current gaps

- There is no general app-preferences store today. This feature adds the first non-test-build, non-land device flag.
- No test reads `strings.xml` values yet. `WelcomeCopyGuardTest` parses the XML file from the repository root, using the root lookup in `AndroidBackupExclusionGuardTest`.

## Implementation plan

1. Add the seven string keys from the contract's copy table to `strings.xml`, verbatim. Do not edit any existing string.
2. Create `welcome/WelcomeNotice.kt`: the `WelcomeNoticeStore` interface, the `WelcomeNotice` holder (`visible`, `dismiss()`, `showAgain()`), and `WELCOME_COPY_SOURCES`.
3. Write `WelcomeNoticeTest` (commonTest) with fake stores. Cover: fresh store visible; dismissed store hidden; dismiss hides and writes once; read throw means visible; write throw hides for the session and a new instance is visible; showAgain is visible with no write; dismiss after showAgain hides again.
4. Create `FileWelcomeNoticeStore` + `desktopWelcomeStorePath()`. `FileWelcomeNoticeStoreTest` covers: missing file not dismissed; mark then a new instance dismissed; garbage content not dismissed; blocked directory throws on write.
5. Create `AndroidWelcomeNoticeStore` (`manijero_welcome`, `commit()`). `AndroidWelcomeNoticeStoreTest` (Robolectric) covers: survives a new instance; does not touch `manijero_lands`.
6. Add `WelcomeCard` and the `showWelcome`/`onDismissWelcome` parameters to `ChatHomeScreen`. Add previews: light, dark, and narrow at 2×.
7. Add `onShowWelcome` and the `Ver bienvenida` button to `CoverageScreen`, plus a preview.
8. Wire `App`: a `welcomeNotice` parameter, a remembered `WelcomeNotice`, the chat props, and the coverage callback (`showAgain`, `previousSection = Assistant`, `destination = Chat`).
9. Inject the stores in `MainActivity` (lazy, `applicationContext`) and in Desktop `main.kt` (remembered).
10. Write `WelcomeFlowInteractionTest` (jvmTest, `App(landRepository = null, welcomeNotice = fake)`). Cover: card shown; `Entendido` hides it and marks the store; a new `App` on the same store shows no card; `Ayuda` → `Ver bienvenida` shows the card on chat; `App` without the store shows neither the card nor the link.
11. Write `WelcomeCopyGuardTest` (jvmTest). It checks that every key and source key in `WELCOME_COPY_SOURCES` exists in `strings.xml`, and that welcome values have no digit, `garantiz`, or `correct`.
12. Add goldens: Desktop `chat_home_welcome_light`, `chat_home_welcome_phone_large_text_dark`, `coverage_welcome_link_light`; Android `chat_home_welcome_light`. Record them with `recordDesktopScreenshots`/`recordAndroidScreenshots` filtered to the new tests, inspect each PNG, and re-record nothing else.
13. Update the durable docs listed in the contract. Run the focused verification block through `./scripts/init.sh --feature welcome_first_use`.

## Verification plan

- `./scripts/init.sh --feature welcome_first_use` — all five commands pass, and the existing goldens pass unchanged.
- Scenarios 1–4 and 6 are covered by `WelcomeNoticeTest` and `WelcomeFlowInteractionTest`. Scenario 5 is covered by `WelcomeCopyGuardTest` plus a validator read of the copy table against `strings.xml`. Scenario 7 is covered by the 2× dark golden and a single-heading assertion in the interaction test (`onAllNodes(isHeading())` count is 1 with the card visible).
- E2E: no persistent E2E suite exists beyond the local smoke tests, which inject no welcome store and do not observe this card. A full-`App` Compose interaction test on Desktop is enough. Android behavior shares the same commonMain code, and its store is covered by Robolectric.
- Manual (optional, not an acceptance gate per owner decision 4): `./gradlew :desktopApp:run` → `Asistente` shows the card → `Entendido` → restart → no card → `Ayuda` → `Ver bienvenida`.

## Evidence to capture

- Each focused command with a one-line result. The names of the new goldens and confirmation that no existing golden changed (`git status` on the screenshot directories).
- The test names that cover each scenario, and the restart result from `WelcomeFlowInteractionTest`.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-02 (implementer)
- `./scripts/init.sh --feature welcome_first_use`: passed (all five commands; existing goldens unchanged).
- `./scripts/init.sh --fast`: passed (9 checks; backend 1716 passed, 4 skipped).
- `./scripts/init.sh --verify`: passed.
- New tests: `WelcomeNoticeTest` (scenarios 2-4), `FileWelcomeNoticeStoreTest`, `AndroidWelcomeNoticeStoreTest`, `WelcomeCopyGuardTest` (5), `WelcomeFlowInteractionTest` (1-3, 6, 7 single heading; new `App` on the same store shows no card = restart).
- New goldens, inspected: Desktop `chat_home_welcome_light`, `chat_home_welcome_phone_large_text_dark`, `coverage_welcome_link_light`; Android `chat_home_welcome_light`. No existing PNG modified (`git status`).

## Validator checklist

- [ ] The owner decisions in the contract's Notes are honoured: card form, one `Ayuda` link, traced copy, and no owner walkthrough required.
- [ ] Each new string matches the copy table verbatim, and no existing string changed (`git diff` on `strings.xml` shows additions only).
- [ ] Each body sentence's facts appear in the cited accepted source keys. There is no new promise, digit, contact detail, or legal claim.
- [ ] The card is not a gate: the composer, suggestions, and tabs work while it is shown. The chat keeps one heading and one filled button.
- [ ] Dismissal persists on Desktop (file) and Android (prefs). Read and write failures are forgiving and never logged. The store is not test-build gated.
- [ ] `Ver bienvenida` is the only new `Ayuda` control. Routes and `AppNavigation.kt` are unchanged. The coverage and privacy copy and callbacks are unchanged.
- [ ] With no store injected, the app, previews, smoke drivers, and every existing golden are unchanged.
- [ ] The focused verification block runs unchanged through `./scripts/init.sh --feature welcome_first_use`.
- [ ] Durable docs are updated as listed (ARCHITECTURE, client-chat constraint, DESIGN, screenshot docs, golden count), and nothing is restated across files.
- [ ] `feature_list.json`, `PROGRESS.md`, and `docs/progress/session-log.md` are updated only after acceptance.
