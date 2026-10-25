# `help_privacy_refresh` — planning and evidence record

Planning and verification detail for [`help_privacy_refresh.md`](help_privacy_refresh.md). Independent acceptance belongs in [`docs/validations/help_privacy_refresh.md`](../validations/help_privacy_refresh.md).

## Repository research

- At planning time, `feature_list.json` marked the feature `not_started`; it depends on accepted
  `ui_component_library` and `land_measurement_fields`. Scope/verification are sourced from
  `docs/design/ui-refresh-plan.md` P2-15…P2-16.
- `DESIGN.md`: shared components are presentational, strings and domain rules remain owned by screens/content; `ManijeroScreen` owns one scroll/frame and the shell owns insets/bars. Privacy remains a detail route; coverage is the Help tab surface.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageScreen.kt`: current stateless screen renders pinned coverage topic, limits and help text and links to privacy. Existing implementation is a plain scrollable column with 720 dp inner cap; this is the P2-15 target.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt`: current notice renders local storage, sent attributes (`SHARED_LAND_ATTRIBUTES`), promises and help, with coverage cross-link and Back. Attribute labels use an exhaustive `when`; preserve it and the copy.
- `App.kt` and `AppNavigation.kt`: already own coverage/privacy destinations and previous-section/back behavior. Do not modify routing for this visual feature.
- `coverage_and_help` and `land_data_disclosure` contracts/appendices define the truth constraints and exact disclosure semantics. The coverage contract explicitly requires pinned topic scope and no invented details; privacy facts must remain aligned with accepted land fields and minimal payload.
- `shared/src/commonTest/.../screenshots/ScreenshotFixtures.kt`, host screenshot tests and `docs/screenshot-regression.md` are the established screenshot system. `./scripts/init.sh --feature` runs fenced commands; `:shared:verifyScreenshots` checks existing baselines. Goldens are host renders, not device/accessibility evidence.
- Current `PROGRESS.md` reports open manual checks for refreshed screens and human review of screenshot images. Keep those limitations open unless this feature supplies direct evidence.
- Inspected `DESIGN.md`, `PROGRESS.md`, `AGENTS.md`, `feature_list.json`, the two target screens, `App.kt`, `coverage_and_help` contract/appendix, `lands_screens_refresh` contract/appendix, the existing screenshot fixtures and all relevant existing/candidate PNGs. No runtime-device visual behavior is inferred from host images.

## Implementation plan and tasks

1. Inspect target screen implementations, current screenshot fixtures/tests/baselines and available shared component APIs. Map every current content section and callback before changing the presentation.
2. Restyle `CoverageScreen.kt` with the shared frame/components: retain exact content/order and existing privacy link; emphasize limits neutrally, without adding copy or links.
3. Restyle `PrivacyScreen.kt` with the same frame/components: retain all notice copy/order, exhaustive shared-attribute rendering, existing coverage link and Back; make device-local facts easy to scan without changing their meaning.
4. Add or update focused persistent UI/interaction coverage if the existing host test harness can assert the relevant callbacks/structure; do not add a new UI framework. Capture meaningful help/privacy states for supported light/dark host renderers.
5. Run target screenshot suites and inspect candidate images before recording. Record only reviewed target images; leave shell/chat/unrelated failures and goldens untouched.
6. Update `DESIGN.md`, `CONSTRAINTS.md`, screenshot documentation and the P2-15…P2-16 delivery note to describe actual adopted treatment and evidence, without accessibility overclaims.
7. Append dated evidence here. Leave status/acceptance to the independent validator.

## Verification plan

- Focused command: `./scripts/init.sh --feature help_privacy_refresh` (shared JVM tests and screenshot verification, exactly as fenced in the contract).
- If target baselines change, run the focused Desktop and Android screenshot test tasks documented in `docs/screenshot-regression.md`; inspect every changed image and verify no unrelated images were recorded.
- Run `./scripts/init.sh --fast` and `./scripts/init.sh --verify` as environment permits; report pytest/SDK/toolchain failures precisely. Full build does not replace target visual review.
- Manual Android/Desktop checks: open Help and privacy routes; check links/back restoration, content parity, compact and wide widths, light/dark, 2× text and scrolling. Perform keyboard/focus and screen-reader checks only where observable; explicitly mark any unavailable checks unverified.
- Copy/fact review against `coverage_and_help`, `land_data_disclosure`, `land_measurement_fields` and current `AskRequest`/`SHARED_LAND_ATTRIBUTES`. Ensure no copy or payload changes slipped into the visual adaptation.

## Evidence to capture

- Commands, exit codes and environment/toolchain limitations; distinguish focused passes from full-gate outcomes.
- Changed screenshot filenames, host/appearance/viewport and review result; confirm unrelated baselines were not recorded.
- Route/link/back observations and checks that existing coverage and privacy facts remain complete and correct.
- Actual compact/wide, dark/light, large-text, keyboard and screen-reader observations, each marked performed or not performed.
- Diff scope, durable docs changed, and any deviations. Do not present host goldens as device, accessibility or owner approval.

## Feature evidence

### 2026-10-25 — independent validation accepted

- Validator verdict: **accept**. Independently reviewed the contract, current diff, evidence, scope,
  and prior `lands_screens_refresh` acceptance record. Existing copy, callbacks, exhaustive privacy
  attribute mapping, and local-data boundaries remain intact.
- Validator reran `./scripts/init.sh --feature help_privacy_refresh` and `./scripts/init.sh --fast`;
  both passed. Focused verification selected all 12 Help/Privacy captures and only
  `appShellHelpRailLight` on each host. Backend pytest remained unavailable and was skipped.
- Device interaction, manual navigation/restoration, keyboard/focus, and screen-reader checks remain
  unperformed; host screenshots do not substantiate those claims. No acceptance-blocking finding.
- Feature status is now `accepted`; acceptance record: [`docs/validations/help_privacy_refresh.md`](../validations/help_privacy_refresh.md).

### 2026-10-25 — focused contract repair and self-verification (newest)

- Updated the focused contract to filter screenshot verification to all 12 Help/Privacy captures
  and only `AppShellScreenshotsTest.appShellHelpRailLight` on each host. This avoids unrelated
  shell/chat baseline failures while covering every target capture and the sole intentionally
  refreshed shell capture.
- `./scripts/init.sh --feature help_privacy_refresh` — PASS. `:shared:jvmTest`, Desktop and
  Android screenshot verification all passed; each host selected exactly its 12 Help/Privacy
  methods plus `appShellHelpRailLight`.
- `./scripts/init.sh --fast` — PASS for JVM tests, contract examples, source catalog and all five
  offline evaluators. Backend pytest was unavailable and skipped by the harness, which printed its
  setup instructions.
- Feature status is `passing`: implemented and self-verified, ready for independent validation;
  this is not acceptance. Android/Desktop route and back behavior, interactive compact/wide
  walkthroughs, keyboard/focus and screen-reader checks remain unperformed. Host renders do not
  establish device rendering, accessibility, usability or owner approval.

### 2026-10-25 — focused verification repair

- Updated the contract's focused screenshot block to run unfiltered `:shared:jvmTest`, then
  host-specific verification for the 12 methods in each Help/Privacy screenshot class plus only
  `AppShellScreenshotsTest.appShellHelpRailLight` on that host. This matches the feature's scope:
  the Help/Privacy method sets exercise all twelve captures per renderer, and the one app-shell
  capture is the sole intentionally refreshed shell baseline. The accepted
  `lands_screens_refresh` validation establishes that `appShellLandsRailDark` and
  `chatClarificationLight` mismatches predate this product diff; they remain unchanged.
- Confirmed Gradle's filters select precisely those methods: Desktop listed 12
  `HelpPrivacyScreenshotsTest` methods and `appShellHelpRailLight`; Android listed 12
  `HelpPrivacyAndroidScreenshotsTest` methods and `appShellHelpRailLight`. Both commands passed;
  no lands/chat captures were selected or recorded.
- `./scripts/init.sh --feature help_privacy_refresh` — PASS. The unfiltered `:shared:jvmTest`,
  focused Desktop screenshot verification, and focused Android screenshot verification all passed.
- `./scripts/init.sh --fast` — PASS: JVM tests, contract examples, source catalog and all five
  offline evaluators passed. Backend pytest was skipped because pytest is unavailable in the
  environment; setup instructions were printed.
- This earlier focused block was later updated and its failure was superseded by the passing
  focused verification recorded above. Manual Android/Desktop route, link/back restoration,
  compact/wide interaction, scrolling, keyboard/focus and screen-reader checks remain unperformed.
  Host screenshots do not establish device rendering, accessibility, usability, or owner approval.
  At the time of this entry, this evidence was not an acceptance claim.

### 2026-10-25 — implementer repair

- Restyled both common screens with `ManijeroScreen`; coverage topics/help are outlined cards and
  the existing limit resources are grouped in a neutral info callout. Privacy keeps its resource
  strings and exhaustive `SHARED_LAND_ATTRIBUTES` rendering in outlined cards. Cross-link and Back
  callbacks are unchanged; title and section headings retain semantic heading semantics.
- Updated `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and this plan's P2-15…P2-16
  delivery note. No app routing, copy resources, request/domain/backend files changed.
- `./gradlew :shared:jvmTest` — PASS (18 tasks, all JVM tests).
- Inspected Desktop `_compare.png` files. `app_shell_help_rail_light` difference is the intended target presentation update: new outlined topic/help cards and informational limits callout; copy and navigation are intact and nothing is clipped in the 900×1000 capture. `app_shell_lands_rail_dark` and `chat_clarification_light` diffs are unrelated presentation changes; they were not recorded. Re-recorded only the help target among existing images.
- Added dedicated coverage and privacy captures in light/dark on both Desktop and Android host renderers (900 dp wide); all eight candidate images were opened and reviewed. Content is legible, all shown sections/actions fit the selected capture, and privacy facts/list remain visible. These are host renders, not accessibility/device evidence.
- `./gradlew :shared:jvmTest :shared:recordDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest' --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest'` — PASS. Note: the task filter recorded all four app-shell methods, including the unrelated lands image; that accidental unrelated change was immediately restored from version control. The target help image was retained.
- `./gradlew :shared:recordDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest'` — PASS, four target captures.
- `./gradlew :shared:recordAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyAndroidScreenshotsTest'` — PASS, four target captures.
- `./gradlew :shared:recordAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest'` — PASS. Reviewed `app_shell_help_rail_light` (900×1000, light); target treatment and all shown content are correct. The unrelated lands baseline was restored.
- `./scripts/init.sh --feature help_privacy_refresh` — FAIL at screenshot verification. Updated help shell and all eight dedicated target captures pass. Remaining mismatches are unrelated Desktop `appShellLandsRailDark` and `chatClarificationLight`, plus Android `chatClarificationLight`; Android ran and target help shell passed.
- `./scripts/init.sh --fast` — PASS: JVM tests, contract examples, source catalog and all five offline evaluators passed. Backend pytest was skipped because pytest is not installed; setup instructions were printed.
- The aggregate was rerun after updating both host help-shell target images. No unrelated shell/chat baselines were retained. Current artifacts are under `shared/build/reports/screenshot-regression/`.
- Manual Android/Desktop route, link/back, compact/wide, light/dark, 2× text, keyboard, and
  screen-reader walkthroughs were not performed. Host goldens are not device or accessibility
  evidence. Changed target baselines were visually reviewed.
- At the time of this historical evidence entry, the aggregate was blocked by unrelated shell/chat
  baseline mismatches; the current focused contract now passes as recorded above. Manual
  route/layout/a11y checks remain outstanding; no independent acceptance is claimed.

### 2026-10-25 — phone and large-text screenshot coverage

- Added dedicated 360×800 dp captures for Coverage and Privacy on both Desktop and Android host
  renderers, in light and dark appearance at normal and 2× font scale (16 new frames total).
- Updated `docs/screenshot-regression.md` counts to 34 Desktop and 30 Android captures. New PNGs
  were reviewed; the 2× frames intentionally show the phone viewport's initial scroll position and
  do not prove that the remaining content is reachable by scrolling.
- `:shared:recordDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest.*Phone*'`
  — PASS, all 8 new Desktop captures.
- `:shared:recordAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyAndroidScreenshotsTest.*Phone*'`
  — PASS, all 8 new Robolectric captures.
- `:shared:verifyScreenshots` — FAIL only on unrelated captures: Desktop
  `appShellLandsRailDark` and `chatClarificationLight`; Android `appShellLandsRailDark` and
  `chatClarificationLight`. All 12 Help/Privacy captures per host, including all new phone and
  large-text captures, passed. No unrelated image was re-recorded.
- Manual device route/scroll and accessibility checks remain outstanding. This screenshot change
  does not establish feature acceptance.

## Validator checklist

- [ ] Both screens use the shared frame/components and theme tokens; no duplicate insets/bars or new design primitives.
- [ ] Coverage topics, limits and referral copy remain present and faithful to accepted contract; limits are informational, not a promise, legal claim or color-only status.
- [ ] Privacy notice retains all accepted local-storage, sent-data, unknown/not-sent facts and exhaustive shared-land-attribute mapping; new land fields are not implied to be sent.
- [ ] Existing privacy/coverage links, Back behavior and originating-section restoration work; no new route/external link.
- [ ] Compact, wide, dark and large-text presentation has evidence or explicit limitations; changed images are inspected and unrelated goldens untouched.
- [ ] Keyboard/screen-reader/device/owner evidence is reported honestly, never inferred from host screenshots or previews.
- [ ] Focused checks pass or failures are scoped accurately; diff excludes routing, strings/content, land/API/backend/knowledge/contracts and platform entry points.
- [ ] `DESIGN.md`, `CONSTRAINTS.md`, screenshot documentation and plan delivery note reflect implementation; status changes only after independent acceptance.
