# `lands_screens_refresh` — planning and evidence record

## Repository research

- `AGENTS.md`, `PROGRESS.md`, `DESIGN.md`, and `docs/design/ui-refresh-plan.md` establish shared
  `commonMain` UI, screen composition, shell inset ownership, visual tokens, accessibility rules and
  the P2-09…P2-14 source scope.
- `LandListScreen.kt` already implements the accepted empty/populated/search-no-results/load-failure
  states, summary, search, confirmation live region, row actions and `LandDetails`; preserve these.
- `AddLandScreen.kt` and `EditLandScreen.kt` use the accepted land fields and shared dropdown/measure
  fields. Their MVI-like states/actions and repositories are in `AddLandState.kt`, `EditLandState.kt`
  and the lands repository sources; do not move validation or persistence into composables.
- `RemoveLandScreen.kt` is the existing confirmation surface. Inspect its current callback and
  semantics before editing; preserve its identity and cancel-safe behavior.
- Shared visual primitives live in `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/`;
  tokens and theme live under `theme/`. The app shell owns global navigation and insets.
- `shared/src/commonTest/.../lands/` contains pure state, repository, summary, search and format
  tests. Host screenshot suites and their fixtures live under `shared/src/{commonTest,jvmTest,
  androidHostTest}/.../screenshots/`; the golden verification task is `:shared:verifyScreenshots`.
- `scripts/init.sh --feature <id>` executes the exact fenced block from the contract. It runs checks;
  plain `./scripts/init.sh` only checks the toolchain and prints guidance. The focused Gradle checks
  require the host build toolchain; screenshot goldens have documented host-render limitations.
- Historical UI plan target details are directional; current accepted specs and `DESIGN.md` win if
  they conflict. In particular, do not revive plan-era copy or interaction patterns rejected by later
  accepted features.

## Implementation plan and tasks

1. Read the four target screens and current goldens/tests; map every existing callback and state branch
   before changing presentation. Inspect `RemoveLandScreen.kt` and its tests specifically.
2. Restyle `LandListScreen.kt` using `ManijeroScreen` and accepted components. Preserve all list
   scenarios, search/summary wording, order, semantics and callbacks. Show chips for known values and
   a compact plain-text unknown-values description; do not imply a missing value is zero.
3. Restyle `AddLandScreen.kt` and `EditLandScreen.kt` with one shared frame and clear grouping. Preserve
   field order, input values, errors, focus-on-invalid-save, save failure, and Cancel. Keep the forms
   functionally aligned and avoid domain logic in view code.
4. Restyle `RemoveLandScreen.kt` with a danger treatment and explicit safe Cancel. Verify the chosen
   land is the exact one passed to confirmation and that no delete occurs on entry or cancel.
5. Add/update persistent tests for distinct interactions not covered by current pure tests. Prefer
   existing host test patterns. Extend screenshot fixtures only for meaningful states and capture both
   hosts where the screenshot harness supports them.
6. Record only reviewed changed/added goldens. Check the diff for unrelated PNG churn and avoid
   overwriting existing user changes.
7. Update the durable docs listed in the contract with actual adopted behavior and honest evidence;
   append evidence below. Do not edit acceptance status or progress board until independent validation.

## Verification plan

- Focused contract command: `./scripts/init.sh --feature lands_screens_refresh`.
- It runs `./gradlew :shared:jvmTest` and `./gradlew :shared:verifyScreenshots` exactly as fenced in
  the contract. Also run the target's broader required tier from `AGENTS.md` as appropriate; report
  unavailable Android SDK/pytest or other environment limitations rather than implying a pass.
- If Android host screenshots are changed, run the Android host screenshot suite and its verification
  task using the repository's documented task names; inspect all resulting images. The focused
  Desktop/host gate does not substitute for Android evidence.
- Manual checks: empty and populated list, no-results/clear, add/edit validation and save, remove then
  cancel and confirm, 320 dp with 2× text, wide Desktop, light/dark, keyboard traversal and screen
  reader labels. Record which were actually performed; do not infer them from goldens.

## Evidence to capture

- Commands, exit status, and environment/toolchain limitations.
- Names of added/re-recorded screenshot files and confirmation that unrelated goldens are unchanged.
- Tests that prove row controls and destructive confirmation dispatch the correct land/callback.
- Manual observations for compact/wide, large text, light/dark, keyboard and assistive technology,
  explicitly marking unperformed checks and owner review as outstanding.
- Any deviation from accepted copy, data behavior or the historical plan, with a reason. No legal or
  user-comprehension claim without corresponding reviewed evidence.

## Feature evidence

<!-- Implementer: append dated verification and evidence here. Leave acceptance to the independent validator. -->

### Implementer evidence — 2026-10-25 (partial; not ready for validation)

- Existing partial change renders known water, production and variety values as chips and collects
  unknown labels in one plain-text line. This continuation changed the removal confirmation to use
  `ManijeroScreen` and a `ManijeroCard(Danger)` for the selected land's known details; identity,
  callbacks, and safe Cancel remain caller-driven.
- This does **not** complete the contract: list framing/row treatment, add/edit shared-frame adoption
  and grouping, persistent interaction tests, removal interaction proof, screenshot updates/review,
  and the rest of the durable documentation remain outstanding. The feature stays `in_progress`.
- `./gradlew :shared:compileKotlinJvm` passed after the continuation; `./scripts/init.sh
  --feature lands_screens_refresh` passed `:shared:jvmTest` but failed screenshot verification.
  Desktop failures: `landListLight`, `landListSearchFiltered`, plus `appShellLandsRailDark` and
  `chatClarificationLight`. Android failures: `landListSearchFiltered`, plus the same app-shell and
  chat clarification captures. The changed list renders account for the land-frame differences;
  shell/chat failures are outside this feature and were not re-recorded. No goldens were recorded.
- `./scripts/init.sh --fast` passed all shared JVM tests, contract examples, source-catalog validation
  and offline evaluators; backend tests were skipped by the harness because pytest is not installed.
- No manual compact/wide, large-text, light/dark interaction, keyboard/screen-reader, device smoke,
  or product-owner review was performed. This implementation is not ready for independent validation.

### Continuation evidence — 2026-10-25 (still partial)

- Switched the list, add, and edit surfaces to the shared `ManijeroScreen` scroll/frame. The populated
  list retains its previous summary, search, actions and state branches; known-value chips and unknown
  text remain as described above. The add/edit fields are not yet visually grouped, row details still
  need the intended shared-card treatment, and persistent interaction coverage and durable docs are
  not complete. No screenshot baselines were recorded or reviewed.
- `./gradlew :shared:compileKotlinJvm` passed and the `:shared:jvmTest` part of
  `./scripts/init.sh --feature lands_screens_refresh` passed. Screenshot verification failed: Desktop
  `landListLight` and `landListSearchFiltered` plus out-of-scope `appShellLandsRailDark` and
  `chatClarificationLight`; Android `landListSearchFiltered` plus the same out-of-scope shell and chat
  images. These differences remain unrecorded pending intentional inspection.
- `./scripts/init.sh --fast` passed shared JVM tests, contract examples, catalog validation and all
  offline evaluators. Backend pytest was skipped because pytest is not installed.
- Feature remains `in_progress`; no manual/device/accessibility or owner checks were performed.

### Implementer continuation — 2026-10-25

- Added separate tonal identity-field and outlined optional-field groups to Add and Edit without
  changing field order, reducer actions, values, or conditional visibility. Rows now use
  `ManijeroCard(Outlined)`; the existing Edit/Remove accessible descriptions explicitly contain
  action + saved name. Removal retains the Danger card and separate Cancel.
- Added `LandScreenInteractionTest`: distinct named row actions dispatch the exact expected land;
  removal performs no callback on screen entry or Cancel and calls remove only after confirmation.
- Reviewed the three new land PNGs at full size: Desktop `land_list_light.png`, Desktop
  `land_list_search_filtered.png`, Android `land_list_search_filtered.png`. They show the intended
  chips/non-clickable outlined row treatment without clipping; no unrelated golden was recorded.
- `./gradlew :shared:jvmTest` passed (271 tests, including the two new interaction cases).
  `./scripts/init.sh --fast` passed shared JVM tests, contract examples, source-catalog validation,
  and offline evaluators; backend pytest was skipped because pytest is unavailable.
- `./gradlew :shared:verifyDesktopScreenshots --tests
  'com.jamarglex.manijero.screenshots.LandListScreenshotsTest' :shared:verifyAndroidScreenshots
  --tests 'com.jamarglex.manijero.screenshots.LandListAndroidScreenshotsTest'` passed all ten land
  captures. The contract's unfiltered `./scripts/init.sh --feature lands_screens_refresh` still
  fails only on Desktop/Android `appShellLandsRailDark` and `chatClarificationLight`; those files,
  code surfaces, and images were not changed here. These same non-land failures were present in the
  pre-recording focused run; isolate them rather than refreshing unrelated goldens.
- Updated `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and this plan's delivery
  note. No manual compact/wide, large-text, light/dark interaction, device, screen-reader, keyboard,
  or owner review was performed. Those limitations remain.
- Screenshot inventory remains 22 Desktop and 18 Android captures; only the 2 Desktop land list
  images and 1 Android filtered land image were updated. `feature_list.json` is `passing` for
  independent validation; aggregate shell/chat baseline failures and unperformed manual audits
  remain explicit limitations.

## Validator checklist

- [x] Dependency acceptance is satisfied and implementation is limited to this feature's scope.
- [x] List states, filters, summaries, query reset, ordering and callbacks match accepted contracts.
- [x] Rows are non-clickable; known chips and unknown details are truthful; Edit/Remove controls name
      both action and land.
- [x] Add/edit preserve values, validation, focus order, save failure and cancel behavior.
- [x] Removal identifies the selected land; cancel is safe; confirmation removes only that land.
- [x] Shared page frame owns no insets; screens add no duplicate shell navigation; theme tokens are
      used with no new palette or component-library domain behavior.
- [x] Persistent tests and focused land checks pass; aggregate unrelated screenshot failures and other
      limitations are explicit and justified.
- [x] Changed screenshots are inspected and limited to the intended states; host-only evidence is not
      described as device, accessibility or product-owner acceptance.
- [x] `DESIGN.md`, `CONSTRAINTS.md`, screenshot docs and historical plan note match implementation;
      progress/status is updated only after this independent accept decision.

## Independent validation — 2026-10-25

Validator verdict: **accept**. See the authoritative [acceptance record](../validations/lands_screens_refresh.md).
