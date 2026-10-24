# Appendix — `shared_design_system`

Planning and verification record for [`docs/specs/shared_design_system.md`](shared_design_system.md). Feature evidence is appended here by the implementer; `docs/validations/shared_design_system.md` will be the authoritative independent acceptance record.

## Repository research

Inspected (paths relative to repository root):

- `AGENTS.md`, `PROGRESS.md`, `CONTEXT.md`, `DESIGN.md`, `ARCHITECTURE.md`: project docs are English; shared UI belongs in `commonMain`; Android/Desktop are MVP targets and iOS release is out of scope. The visual direction now references the planned Stitch adoption.
- `design-references/README.md`, `stitch/manijero_design_system/DESIGN.md`, `stitch/manijero_design_system_dark_mode/DESIGN.md`: light tokens, dark tokens, shapes, spacing, and component proposals. Its HTML exports use design references, not Compose source.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`: current centralized light ColorScheme, semantic-color CompositionLocal, and WCAG contrast helpers. It currently has no dark color scheme.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTheme.kt`: current theme is applied once at the shared root, is intentionally light-only, and has a token-board preview. It currently accepts no appearance override. Typography remains the Material default.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ManijeroTheme` wraps all app destinations in the shared composition root; previews are hosted here and in the land-screen files.
- `shared/build.gradle.kts`: shared module already configures `iosArm64`, `iosSimulatorArm64`, JVM, Android and Compose resources. Material 3, Compose UI/foundation, and Compose resources are already in `commonMain`; no design-system dependency is currently required.
- `feature_list.json` plus `./scripts/select-feature.sh --status`: all existing features were accepted; `visual_foundation` is accepted; this design-system extension is added as a distinct feature depending on it.
- `./scripts/init.sh --feature` documentation in `AGENTS.md` and existing specs: focused checks execute the shell block in the spec; `./scripts/init.sh --verify` is the full test/build gate. The repo has no persistent Compose UI screenshot/E2E harness.

### Sizing and decisions

This remains one shared presentation-foundation feature: no data model or user flow, and no new module. It is bounded to token/role mapping, system-selected appearance, shape/spacing values, review previews, and tests. Typography stays at the Material 3 default. Existing screen redesigns are explicitly excluded.

Confirmed with the user: adopt Stitch's design-system colors as the baseline (correct contrast failures as needed), keep the Material 3 default typography, implement both light and dark schemes, follow OS appearance automatically, and do not add a manual setting. Project documentation remains English per `CONTEXT.md`.

## Implementation plan and tasks

1. **Translate both Stitch palettes into semantic roles.** Create a table mapping every used Material 3 role plus Manijero-only caution/status roles for light and dark. Calculate all text and non-text pairs with the existing WCAG helper. Adjust failing pairs, document measured ratios and reasons in the contract/evidence and `DESIGN.md`, and test the final values.
2. **Extend the common theme.** Add a `darkColorScheme` mapping and a `ManijeroTheme` appearance parameter defaulting to Compose's common `isSystemInDarkTheme()` signal. Keep an explicit override for previews/tests. The app remains one theme application at `App()`; do not fork per platform.
3. **Add named shape and spacing tokens.** Add common shape/spacing definitions based on the archive's values, documenting mapping rather than scattering numeric literals. Keep the Material 3 default typography; no typography file or font asset is added.
4. **Review surface and previews.** Extend/create a token board with side-by-side or separately named light/dark previews and an enlarged-text preview. Point current app previews at the shared theme; do not revise screen hierarchy or behavior.
5. **Add common tests.** `ManijeroDesignSystemTest` verifies both scheme role mappings, semantic locals, representative exact values, WCAG thresholds, shared shape/spacing values, and the theme's explicit light/dark selection override. Keep tests pure and in-process; no screenshot dependencies.
6. **Verify target builds and existing behavior.** Run focused tests first, then JVM and Android host suites and Android/Desktop builds. Compile an iOS simulator framework only where the local toolchain supports it; document an unavailable Xcode toolchain rather than claiming iOS validation.
7. **Manual review.** On Android and Desktop, toggle OS appearance and verify both themes; inspect high-contrast text, focus, error/caution labels, and enlarged text. Record captures or exact observations. No manual appearance setting should appear.
8. After implementation and independent acceptance, append feature evidence, update `DESIGN.md` with final checked values, update the feature status and `PROGRESS.md`, and add the acceptance pointer to `docs/progress/session-log.md`.

## Verification plan

Run from repository root, cheapest first:

```sh
./gradlew :shared:jvmTest --tests ManijeroDesignSystemTest
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest
./gradlew :androidApp:assembleDebug
./gradlew :desktopApp:build
./scripts/init.sh --verify
```

Where Xcode is installed, also run the repository-supported iOS simulator framework compile task (`:shared:compileKotlinIosSimulatorArm64`); if task naming/toolchain differs, inspect Gradle tasks and record the exact command/outcome. Do not treat an unavailable host toolchain as app failure, and do not claim an iOS release test.

Automated assertions:

- Explicitly map and check all Material 3 roles used by the app in both color schemes; verify no brand-bearing role falls back to Material's default.
- Test semantic caution/error colors in both schemes and compute all documented WCAG pairs: text >= 4.5:1; meaningful boundaries/icons >= 3:1.
- Verify both explicit theme overrides produce their correct schemes; verify runtime default reads system appearance via common Compose API (without platform-specific wrappers).
- Verify named shape and spacing tokens exist and are common-source declarations.
- Confirm centralized color literals are only in the theme token implementation and previews are wrapped by ManijeroTheme.

There is no persistent Compose UI/E2E or screenshot test harness in this repository. Pure common tests plus manual Android/Desktop appearance checks are the appropriate current coverage; do not add a test framework for this feature.

## Evidence to capture

- Focused `ManijeroDesignSystemTest` output and test counts; JVM and Android-host suite outputs; Android and Desktop build results; full `--verify` result or exact environmental blocker.
- Final light/dark token tables with WCAG contrast results and any changed Stitch values/reasons.
- Android and Desktop screenshots or written visual inspection for light and dark, plus enlarged text and a focus/error/caution state. Confirm no setting UI was added.
- iOS simulator compile outcome or an honest toolchain limitation.

## Feature evidence

<!-- Implementer: append verified implementation and test evidence here. -->

### Implementer evidence (2026-10-24)

- Added an explicit paired Material 3 light/dark scheme, dark semantic caution colors, system-driven common `isSystemInDarkTheme()` selection with test/preview override, common shapes/spacing, and light/dark/enlarged-text review previews. No screen layouts, platform entry points, dependencies, or appearance settings changed.
- Common test `ManijeroDesignSystemTest` now enumerates all 36 applicable Material roles in both schemes against their intended values and computes each documented normal-text (>=4.5:1) and boundary/icon (>=3:1) pair, plus semantic caution checks including the light canvas/surface pairs. This describes only the listed intended-use pairs, not every possible role combination. The dark outline-variant was raised from Stitch `#424942` to `#646B64` (3.33:1 against the dark base surface); full declarations are in `ManijeroColors.kt`.
- `./scripts/init.sh --feature shared_design_system` — PASS; focused `:shared:jvmTest --tests ManijeroDesignSystemTest`, `BUILD SUCCESSFUL`.
- `./scripts/init.sh --fast` — PASS; all 9 offline checks passed. Backend unit tests explicitly skipped because pytest is not installed.
- `./scripts/init.sh --verify` — PASS; fast tier's 9 checks passed (backend pytest skipped for missing pytest), then Android host tests, Android debug build and Desktop build completed, `BUILD SUCCESSFUL`.
- At the time this initial evidence was written (before the later capture review), manual Android/Desktop appearance and enlarged-text visual review had not yet been performed. This is a historical pre-capture limitation, superseded by the visual review below. No screenshot/E2E harness exists. iOS compile was not run; no iOS release claim.
- Status set to `passing` for independent validation; this is not acceptance.

### Repair iteration (2026-10-24)

- Documentation-only correction in `ManijeroTheme.kt`: its KDoc now describes shared system-selected light/dark palettes and the default appearance signal. Runtime behavior was not changed.
- Focused verification, exact result: `./scripts/init.sh --feature shared_design_system` — PASS. Ran `./gradlew :shared:jvmTest --tests ManijeroDesignSystemTest`; output ended `BUILD SUCCESSFUL in 53s`, `18 actionable tasks: 6 executed, 12 up-to-date`, `Configuration cache entry reused.`
- At the time of this repair entry, no manual Android/Desktop review was claimed; the orchestrator reported `adb: command not found` and the prior android-run failed with `error: closed`. This predates and is superseded by the user-supplied host screenshot review below.

### Test-gap repair (2026-10-24)

- Added pure `selectManijeroColorScheme(darkTheme)` used by `ManijeroTheme`; common test explicitly asserts `false` selects the light scheme and `true` selects the dark scheme. The theme's system-signal default remains `darkTheme: Boolean = isSystemInDarkTheme()`.
- `./scripts/init.sh --feature shared_design_system` — PASS; `:shared:jvmTest --tests ManijeroDesignSystemTest`, `BUILD SUCCESSFUL in 5s`, `18 actionable tasks: 7 executed, 11 up-to-date`.
- No UI/layout/behavior changes, dependencies, acceptance record, or progress-board update.

### Host screenshot visual review (2026-10-24)

- Reviewed the user-supplied Android and Desktop host PNG captures; all PNGs are verification artifacts stored outside the repository and must not be committed.
- Android `Pixel_10a` light home shows the warm light palette and no theme control. Android dark home shows a dark green-black canvas, light text, olive accents, and no visible light-mode leftovers. The Android dark lands capture shows the lands empty state.
- Android `android-dark-error3.png` shows the submitted question and a deep-red connection-error notice with a readable Spanish explanation and pale `Reintentar` button. Failure is conveyed in text, not color alone. Important capture distinction: `android-dark-error.png` and `android-dark-error2.png` are focused question-input states with the keyboard open; they are not error-state captures.
- Android `font_scale=1.5` capture shows wrapping in headings, chips, and label/body text without clipping or overlap among visible controls. The capture ends before the complete screen content, so this is not evidence that the full flow fits at enlarged text.
- Desktop light home shows the warm palette. Desktop dark home changed live after the authorized brief macOS appearance toggle, without an app restart; the environment was restored afterward and no setting was added. Desktop dark lands shows the existing land record with dark surfaces/text and olive actions.
- No visual focus/error issue was evident in the relevant captures. This was not a keyboard-navigation or focus-order audit. No app relaunch was performed.

### Independent acceptance (2026-10-24)

- Validator verdict: **accept**. All feature checklist items were reviewed against the implementation, tests, docs, command results, and supplied host captures.
- Latest focused check: `./scripts/init.sh --feature shared_design_system` — PASS (`BUILD SUCCESSFUL`).
- Latest full gate: `./scripts/init.sh --verify` — PASS; all 9 offline checks passed, then Android host tests, Android debug build, and Desktop build completed (`BUILD SUCCESSFUL`). Backend pytest was explicitly skipped because pytest is not installed. iOS simulator compilation was not run.
- The PNG review copies in `.review-temp/` were temporary and are excluded from the accepted change; source screenshots remain outside the repository.

## Validator checklist

- [x] Both Stitch system files informed the paired light/dark role mappings; failing contrast pairs were corrected and documented rather than omitted.
- [x] System appearance selects the correct scheme, and a parameter/override makes both modes explicitly testable; there is no preference setting or platform theme fork.
- [x] The one shared theme remains applied once at `App()`; Android, Desktop, previews and shared iOS scaffold consume it.
- [x] Semantic caution/error roles are meaningful in both modes and UI status remains understandable without color alone.
- [x] Typography stays at the Material 3 default, which resolves to the platform font; no custom typography file, scale, or font asset was added or substituted.
- [x] Shape and spacing values are named and shared, not raw copied literals spread among screens.
- [x] All documented text pairs meet 4.5:1 and meaningful non-text pairs meet 3:1 in both themes; tests independently compute ratios.
- [x] Existing feature behavior, Spanish copy, accessibility semantics, and screen structure remain unchanged; no new module/dependency/framework was added.
- [x] Focused tests, host tests and Android/Desktop builds pass; iOS compatibility status is accurately recorded without overclaiming release validation.
- [x] Previews cover both themes and enlarged text; Android/Desktop appearance and visual checks are recorded with the large-text and keyboard-audit limits stated.
- [x] `DESIGN.md` documents the final values and `feature_list.json`/`PROGRESS.md` reflect independent acceptance.
