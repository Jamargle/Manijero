# Appendix — `shared_design_system`

Planning and verification record for [`docs/specs/shared_design_system.md`](shared_design_system.md). Feature evidence is appended here by the implementer; `docs/validations/shared_design_system.md` will be the authoritative independent acceptance record.

## Repository research

Inspected (paths relative to repository root):

- `AGENTS.md`, `PROGRESS.md`, `CONTEXT.md`, `DESIGN.md`, `ARCHITECTURE.md`: project docs are English; shared UI belongs in `commonMain`; Android/Desktop are MVP targets and iOS release is out of scope. The visual direction now references the planned Stitch adoption.
- `design-references/README.md`, `stitch/manijero_design_system/DESIGN.md`, `stitch/manijero_design_system_dark_mode/DESIGN.md`: light tokens, dark tokens, typography names/scales, shapes, spacing, and component proposals. The archive contains no font binaries or font license files. Its HTML exports use design references, not Compose source.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`: current centralized light ColorScheme, semantic-color CompositionLocal, and WCAG contrast helpers. It currently has no dark color scheme.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTheme.kt`: current theme is applied once at the shared root, is intentionally light-only, and has a token-board preview. It currently accepts no appearance override.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTypography.kt`: current typography uses platform default sans with a line-height adjustment; Stitch calls for Source Serif 4 + Source Sans 3.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ManijeroTheme` wraps all app destinations in the shared composition root; previews are hosted here and in the land-screen files.
- `shared/build.gradle.kts`: shared module already configures `iosArm64`, `iosSimulatorArm64`, JVM, Android and Compose resources. Material 3, Compose UI/foundation, and Compose resources are already in `commonMain`; no design-system dependency is currently required.
- `feature_list.json` plus `./scripts/select-feature.sh --status`: all existing features were accepted; `visual_foundation` is accepted; this design-system extension is added as a distinct feature depending on it.
- `./scripts/init.sh --feature` documentation in `AGENTS.md` and existing specs: focused checks execute the shell block in the spec; `./scripts/init.sh --verify` is the full test/build gate. The repo has no persistent Compose UI screenshot/E2E harness.

### Sizing and decisions

This remains one shared presentation-foundation feature: no data model or user flow, and no new module. It is bounded to token/role mapping, system-selected appearance, typography, shape/spacing values, review previews, and tests. Existing screen redesigns are explicitly excluded.

Confirmed with the user: adopt Stitch's design-system colors and typography as the baseline (correct contrast failures as needed); implement both light and dark schemes; follow OS appearance automatically; do not add a manual setting. Project documentation remains English per `CONTEXT.md`.

## Implementation plan and tasks

1. **Resolve font asset provenance before coding typography.** Locate Source Serif 4 and Source Sans 3 files from an acceptable source, verify format compatibility with Compose Multiplatform common resources and redistribution terms, and include the required license notice. The supplied archive has no font files or license documents. If provenance/terms cannot be verified, pause and request an owner decision; do not fetch runtime fonts or silently replace the chosen families.
2. **Translate both Stitch palettes into semantic roles.** Create a table mapping every used Material 3 role plus Manijero-only caution/status roles for light and dark. Calculate all text and non-text pairs with the existing WCAG helper. Adjust failing pairs, document measured ratios and reasons in the contract/evidence and `DESIGN.md`, and test the final values.
3. **Extend the common theme.** Add a `darkColorScheme` mapping and a `ManijeroTheme` appearance parameter defaulting to Compose's common `isSystemInDarkTheme()` signal. Keep an explicit override for previews/tests. The app remains one theme application at `App()`; do not fork per platform.
4. **Add named typography, shape, and spacing tokens.** Map Stitch semantic text roles to `MaterialTheme.typography`; keep scalable `sp`. Add common shape/spacing definitions based on the archive's values, documenting mapping rather than scattering numeric literals. Bundle fonts only after task 1 succeeds.
5. **Review surface and previews.** Extend/create a token board with side-by-side or separately named light/dark previews, typography samples, and enlarged-text preview. Point current app previews at the shared theme; do not revise screen hierarchy or behavior.
6. **Add common tests.** `ManijeroDesignSystemTest` verifies both scheme role mappings, semantic locals, representative exact values, WCAG thresholds, type-role sizing/line-height, and the theme's explicit light/dark selection override. Keep tests pure and in-process; no screenshot dependencies.
7. **Verify target builds and existing behavior.** Run focused tests first, then JVM and Android host suites and Android/Desktop builds. Compile an iOS simulator framework only where the local toolchain supports it; document an unavailable Xcode toolchain rather than claiming iOS validation.
8. **Manual review.** On Android and Desktop, toggle OS appearance and verify both themes; inspect high-contrast text, focus, error/caution labels, and enlarged text. Record captures or exact observations. No manual appearance setting should appear.
9. After implementation and independent acceptance, append feature evidence, update `DESIGN.md` with final checked values, update the feature status and `PROGRESS.md`, and add the acceptance pointer to `docs/progress/session-log.md`.

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
- Verify typography role-family/size/weight/line-height mappings and text-scaled `sp` values; do not test only a handful of hard-coded layout dimensions.
- Verify named shape and spacing tokens exist and are common-source declarations.
- Confirm centralized color literals are only in the theme token implementation and previews are wrapped by ManijeroTheme.

There is no persistent Compose UI/E2E or screenshot test harness in this repository. Pure common tests plus manual Android/Desktop appearance checks are the appropriate current coverage; do not add a test framework for this feature.

## Evidence to capture

- Focused `ManijeroDesignSystemTest` output and test counts; JVM and Android-host suite outputs; Android and Desktop build results; full `--verify` result or exact environmental blocker.
- Final light/dark token tables with WCAG contrast results and any changed Stitch values/reasons.
- Font file origins, compatibility and license evidence if fonts are bundled; otherwise the owner decision blocking that step.
- Android and Desktop screenshots or written visual inspection for light and dark, plus enlarged text and a focus/error/caution state. Confirm no setting UI was added.
- iOS simulator compile outcome or an honest toolchain limitation.

## Feature evidence

<!-- Implementer: append verified implementation and test evidence here. -->

## Validator checklist

- [ ] Both Stitch system files informed the paired light/dark role mappings; failing contrast pairs were corrected and documented rather than omitted.
- [ ] System appearance selects the correct scheme, and a parameter/override makes both modes explicitly testable; there is no preference setting or platform theme fork.
- [ ] The one shared theme remains applied once at `App()`; Android, Desktop, previews and shared iOS scaffold consume it.
- [ ] Semantic caution/error roles are meaningful in both modes and UI status remains understandable without color alone.
- [ ] Typography uses the selected families/scales; any font assets have verified source/redistribution terms and license notice. If this was blocked, implementation did not silently substitute fonts.
- [ ] Shape and spacing values are named and shared, not raw copied literals spread among screens.
- [ ] All documented text pairs meet 4.5:1 and meaningful non-text pairs meet 3:1 in both themes; tests independently compute ratios.
- [ ] Existing feature behavior, Spanish copy, accessibility semantics, and screen structure remain unchanged; no new module/dependency/framework was added.
- [ ] Focused tests, host tests and Android/Desktop builds pass; iOS compatibility status is accurately recorded without overclaiming release validation.
- [ ] Previews cover both themes and enlarged text; manual Android/Desktop appearance/focus checks are recorded.
- [ ] `DESIGN.md` documents the final accepted values and `feature_list.json`/`PROGRESS.md` status reflects independent validation only.
