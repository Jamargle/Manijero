# Feature Spec: `visual_foundation`

## Source metadata

- **Feature:** `visual_foundation` — Apply the shared visual foundation (`client`), `depends_on: []`.
- **Status at planning:** `not_started` (2026-10-13). This is the first unfinished dependency-ready feature; `response_states`, `answer_source_cards`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, and `chat_accessibility` are blocked behind it.
- **Source behavior:** A person sees the same calm, warm, olive-toned look on every screen: a warm page background, olive primary actions and navigation, and clear caution and danger cues that never rely on color alone.
- **Source verification:** (1) On Android and Desktop, confirm the chat and land screens use the centralized tokens (olive-800 primary, canvas background, surface cards/inputs, caution and danger states) instead of the default Material palette. (2) Check text/background and control contrast against WCAG AA, and confirm text scaling and large touch targets remain usable after theming.
- **Notes carried from the feature list:** tokens are initial product direction, not a verified brand palette; compare with the launcher artwork and adjust on a meaningful mismatch; keep tokens centralized in `commonMain`; add no modules, frameworks, or dependencies; this feature is the token/theme layer only, so per-screen redesigns stay with `chat_home`, `add_land`, and later features.

## Goal and boundaries

Create one shared Material 3 theme in `commonMain` from the `DESIGN.md` "Visual foundation" tokens, apply it once at the shared composition root so Android, Desktop, previews, and the iOS scaffold all render the same palette, and prove WCAG AA contrast with dependency-free tests.

**In scope**

- A centralized token layer in `commonMain`: the ten `DESIGN.md` tokens plus the minimum derived values needed to replace every Material 3 default color role.
- A complete `lightColorScheme(...)` mapping (no role left at a Material default), a `Typography` value that keeps the platform system sans and generous line height, and a small semantic-color local for the tokens Material 3 has no role for (caution, caution surface, strong olive).
- Applying the theme once in `App()`, so `MainActivity` and desktop `main.kt` (and the iOS scaffold) inherit it without platform-specific theme code.
- Repointing all existing `@Preview` wrappers from `MaterialTheme { }` (default purple palette) to the shared theme, plus one review-only token-board preview.
- Pure `commonTest` coverage for token values, role mapping, "no Material default leaked", and WCAG contrast ratios, runnable on JVM and Android host.
- Explicit non-color cue requirements for caution, danger, selection, validation, and disabled states.

**Non-goals**

- No redesign of `ChatHomeScreen` or `AddLandScreen` layouts, spacing, component choice, or copy. Only the theme wrapper changes (plus preview wrappers).
- No new UI surface: another theme, palette, dark theme, icon, illustration, font asset, or bundled font family; no Material dynamic color.
- No navigation, typography-scale, or shape-scale redesign: shapes stay at the Material 3 baseline.
- No new Gradle module (`:core:design-system` is explicitly **not** added), no new dependency (including test-only), no launcher-artwork replacement, no Android window-background/launch-frame resource work.
- No caution/danger callout components: those arrive with `response_states` / `network_error_recovery`, which consume these tokens.
- No changes to `feature_list.json`, `PROGRESS.md`, backend, contracts, or land data.

## Job story

When I open Manijero for the first time on my phone or computer, I want every screen to look the same calm, warm, olive-and-paper place with obvious green actions and clearly worded warnings, so I can trust that I am in the right app and never have to guess what a color means.

## Acceptance scenarios

### One shared look on both MVP platforms

Given the Android and Desktop apps start through `App()`, when any screen is shown, then the page background is `canvas` `#F7F6F0`, primary actions and navigation labels are `olive-800` `#354B32`, and no screen or preview renders the Material default purple/blue palette.

### Cards and inputs use surface and border tokens

Given chat or land screens show a card, transcript bubble, or text field, when they are rendered, then card and input fills are `surface` `#FFFFFF` (or the derived low-emphasis `surfaceVariant` for the person's own message), and every input/bubble boundary is drawn with `outline` `#777D73` or `outlineVariant` `#7E8479`, each with at least 3:1 contrast against `canvas` and `surface`.

### Caution and danger are available and never color-only

Given a later screen needs a caution or error cue, when it reads `LocalManijeroSemanticColors` or `MaterialTheme.colorScheme.error`, then it gets the `DESIGN.md` caution (`#704600` on `#FFF2D4`) and danger (`#A12622`) values, and the cue is always accompanied by explanatory text (and an accessible announcement where the text changes), never by color or an icon alone.

### Contrast is machine-checked, not asserted

Given the shipped theme, when `:shared:jvmTest` and `:shared:testAndroidHostTest` run, then a focused test asserts every documented text pair is at least 4.5:1 and every documented non-text pair at least 3:1 using a WCAG relative-luminance helper implemented in the repository.

### Text scaling and touch targets survive theming

Given system text is enlarged (Android `font_scale 2.0`, preview `fontScale = 2f`), when the chat and land screens render, then no label, field, or button is clipped or overlapped and controls still wrap; and every interactive control keeps the Material 3 minimum interactive size (no `LocalMinimumInteractiveComponentSize` override, no sub-48dp sizing added).

### Nothing else changes

Given the theme is applied, when the existing suites run, then chat and land behavior, the Spanish copy contract, persistence, and the `/ask` boundary are unchanged, and no test that passed before regresses.

## Repository research

Inspected (all paths relative to the repository root):

- `DESIGN.md` lines 11-28 (tokens) and 52-56 (accessibility baseline); `CONTEXT.md` (plain Spanish, high contrast, Android/Desktop MVP); `docs/risks-and-open-questions.md` (no visual/theme row today); `docs/domain-model.md` (no visual constraint).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` — `ChatHomeScreen` and the only two shared destinations; its comment already calls `App()` the composition root. It reads `colorScheme.background`, `onBackground`, `onSurface`, `onSurfaceVariant`, `primary`, `surface`, `surfaceVariant`, `outlineVariant`, and `typography.headlineMedium/bodyLarge/titleMedium/labelLarge`. Seven `@Preview` wrappers use `MaterialTheme { }` (default palette). No theme is applied to real content.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt` — reads `background`, `onBackground`, `onSurfaceVariant`, `error`, `typography.headlineMedium/bodyLarge/titleMedium`; eight `@Preview` wrappers use `MaterialTheme { }`.
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt` and `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` — both call `App(landRepository)` inside `setContent`/`Window`; neither wraps it in any theme. `shared/src/iosMain/.../MainViewController.kt` calls `App()`.
- No `theme`/`color`/`typography` file exists anywhere under `shared/src`. `MaterialTheme` appears only as an implicit default.
- `gradle/libs.versions.toml` — Compose Multiplatform 1.12.1, `material3 1.12.0-alpha03`, `kotlin 2.4.20`. No font, color, or theme dependency and none may be added. `shared/build.gradle.kts` exposes `compose.material3`, `compose.foundation`, `compose.ui`, and `ui-tooling-preview` in `commonMain`, and `kotlin-test` in `commonTest`.
- Existing tests (`ChatHomeStateTest`, `ChatConversationTest`, `KtorAnswerServiceTest`, `LandRepositoryTest`, `AddLandStateTest`, host/desktop scaffold tests, 24 JVM / 22 Android host) never import `androidx.compose.*`; no Compose UI-test harness or screenshot test exists. Compose types are expected to be reachable from the associated test compilation; see Risk R2 for the fallback if they are not.
- `androidApp/src/main/res/drawable/ic_launcher_background.xml` and `drawable-v24/ic_launcher_foreground.xml` — the launcher artwork is the **unmodified Android Studio template**: solid template green `#3DDC84` background with the white Android robot. There is no olive-grove artwork in the repository, so the requested palette sanity check has nothing to compare against; `DESIGN.md` tokens stay as written (see U1). `androidApp/src/main/AndroidManifest.xml` already uses `@android:style/Theme.Material.Light.NoActionBar`.
- `./init.sh` — `--verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; it must not gain new modes or a long-running service for this feature.

The feature is correctly sized: one cross-cutting presentation layer, no data model, no user flow, no new module. Two screens change only at their theme/preview wrapper.

## Technical approach

### 1. New shared theme package

All new code lives in `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/` (same module and `commonMain`, matching the flat package convention of `com.jamarglex.manijero`, `.lands`, `.chat`). No Gradle module is added, per `AGENTS.md` and the module-structure skill's "adapt to this repository" rule.

### 2. Palette: `DESIGN.md` tokens are the source of truth

Verbatim tokens (screen code must never reference these hex values directly; it reads Material 3 roles or the semantic local):

| Token | Value | Purpose |
|---|---|---|
| `olive-800` | `#354B32` | primary actions, navigation, selected states |
| `olive-900` | `#263724` | pressed/strong emphasis (`primaryStrong`) |
| `canvas` | `#F7F6F0` | warm page background |
| `surface` | `#FFFFFF` | cards and input surfaces |
| `text-primary` | `#1D221B` | main text |
| `text-secondary` | `#4B5149` | secondary text and metadata |
| `border` | `#777D73` | form boundaries and separators (`outline`) |
| `caution` | `#704600` | warnings, always paired with text/icon |
| `caution-surface` | `#FFF2D4` | caution callout background |
| `danger` | `#A12622` | errors and destructive actions (`error`) |

Derived values are allowed only to replace roles `DESIGN.md` does not name. They must stay in the same warm-neutral/olive families (no new hue), be documented where they are declared, and each is justified below:

| Derived value | Hex | Why |
|---|---|---|
| `surfaceVariant` / `surfaceContainerHighest` | `#E7E5DD` | low-emphasis container (the person's own message bubble); warm neutral so olive keeps its "primary/selected" meaning |
| `surfaceContainerLow` / `surfaceContainer` / `surfaceContainerHigh` | `#FCFBF6` / `#F2F0E9` / `#EDEBE3` | warm lift family for future cards, menus, and sheets |
| `surfaceContainerLowest` / `surfaceBright` | `#FFFFFF` / `#FFFFFC` | surface extremes |
| `surfaceDim` | `#DFDDD4` | recessed surface |
| `outlineVariant` | `#7E8479` | softer separator/bubble border that still clears 3:1 against canvas, surface, and `surfaceVariant` |
| `primaryContainer` / `onPrimaryContainer` | `#D9E2D2` / `#263724` | light olive fill for selected/tonal containers |
| `secondaryContainer` / `onSecondaryContainer` | `#DFE4D8` / `#263724` | second tonal fill, same family |
| `tertiary` / `onTertiary` | `#40573C` / `#FFFFFF` | third emphasis step, still olive (no brown, which would read as caution) |
| `tertiaryContainer` / `onTertiaryContainer` | `#E9EDE2` / `#263724` | lightest tonal fill |
| `inverseSurface` / `inverseOnSurface` / `inversePrimary` | `#2E332C` / `#F1F2EC` / `#B6C4AC` | snackbar/reverse surfaces without purple leakage |
| `errorContainer` / `onErrorContainer` | `#F9DEDA` / `#6E1714` | calm danger container derived from `danger`, not a Material default |

### 3. Color scheme mapping (every role is set explicitly)

`lightColorScheme(...)` must be called with all of these roles. Any role left unset keeps a Material 3 default (purple/teal), which is exactly what the feature forbids.

| Material 3 role | Value | Source |
|---|---|---|
| `primary` | `#354B32` | `olive-800` |
| `onPrimary` | `#FFFFFF` | `surface` |
| `primaryContainer` / `onPrimaryContainer` | `#D9E2D2` / `#263724` | derived / `olive-900` |
| `secondary` / `onSecondary` | `#4B5149` / `#FFFFFF` | `text-secondary` (keeps one brand hue) |
| `secondaryContainer` / `onSecondaryContainer` | `#DFE4D8` / `#263724` | derived / `olive-900` |
| `tertiary` / `onTertiary` | `#40573C` / `#FFFFFF` | derived olive-700 |
| `tertiaryContainer` / `onTertiaryContainer` | `#E9EDE2` / `#263724` | derived / `olive-900` |
| `background` / `onBackground` | `#F7F6F0` / `#1D221B` | `canvas` / `text-primary` |
| `surface` / `onSurface` | `#FFFFFF` / `#1D221B` | `surface` / `text-primary` |
| `surfaceVariant` / `onSurfaceVariant` | `#E7E5DD` / `#4B5149` | derived / `text-secondary` |
| `surfaceTint` | `#354B32` | `olive-800` |
| `inverseSurface` / `inverseOnSurface` / `inversePrimary` | `#2E332C` / `#F1F2EC` / `#B6C4AC` | derived |
| `error` / `onError` | `#A12622` / `#FFFFFF` | `danger` |
| `errorContainer` / `onErrorContainer` | `#F9DEDA` / `#6E1714` | derived from `danger` |
| `outline` / `outlineVariant` | `#777D73` / `#7E8479` | `border` / derived |
| `scrim` | `#000000` | Material default, intentionally unchanged |
| `surfaceBright` / `surfaceDim` | `#FFFFFC` / `#DFDDD4` | derived |
| `surfaceContainerLowest` / `Low` / `Container` / `High` / `Highest` | `#FFFFFF` / `#FCFBF6` / `#F2F0E9` / `#EDEBE3` / `#E7E5DD` | derived |

If the installed `material3 1.12.0-alpha03` does not expose one of the newer surface roles, omit that single parameter (and its test row) instead of adding a dependency.

Material 3 derives pressed/ripple feedback as a state layer over `primary`, so `olive-900` is not a container swap; it is exposed as `primaryStrong` for strong-emphasis surfaces or labels.

### 4. Semantic colors Material 3 has no role for

`@Immutable data class ManijeroSemanticColors(caution, onCaution, cautionSurface, primaryStrong)` provided through `staticCompositionLocalOf` (e.g. `LocalManijeroSemanticColors`) whose default value is the light semantic colors, so a missing provider can never crash a preview or screen. Each value has a documented contract:

- `caution` `#704600` — caution text/icon on `canvas`, `surface`, or `cautionSurface` (all ≥ 4.5:1).
- `onCaution` `#FFFFFF` — content on a solid caution-filled surface (8.19:1).
- `cautionSurface` `#FFF2D4` — caution callout background, always beside caution text.
- `primaryStrong` `#263724` — `olive-900` emphasis (11.72:1 as text on canvas).

Danger is **not** duplicated here: it is `MaterialTheme.colorScheme.error` (`#A12622`), and border is `colorScheme.outline`. One value, one source.

### 5. Typography

`ManijeroTypography` = Material 3 `Typography()` (which already resolves to the platform system sans via `FontFamily.Default`) with exactly one override: `bodySmall` line height `16.sp → 18.sp`, because `bodySmall` is the smallest text in the app (text-field labels, supporting text, and validation errors) and 12sp at a 1.33 ratio is cramped for accented Spanish. Every other role keeps the Material baseline; the rule to test is that the prose body roles (`bodyLarge`, `bodyMedium`, `bodySmall`) and `labelLarge` keep `lineHeight ≥ 1.4 × fontSize`, and no font asset or font dependency is introduced. Do not change font sizes, weights, or letter spacing.

### 6. Theme application

- `internal fun ManijeroTheme(content: @Composable () -> Unit)` wraps `MaterialTheme(colorScheme = ManijeroLightColorScheme, typography = ManijeroTypography, content = ...)` inside `CompositionLocalProvider(LocalManijeroSemanticColors provides ManijeroSemanticColors)`.
- Apply it **once, inside `App()`**, around the `when (destination)` content. `App()` is already documented as the composition root and is called by `MainActivity`, desktop `main.kt`, and `MainViewController`, so all three hosts plus every `App()` preview inherit one theme with no duplicated platform code. Platform entry points stay unchanged (and must not add a second `MaterialTheme`); if an implementer instead wraps each platform root, all three hosts and every preview must be updated — the single shared wrap is the chosen approach.
- Light-only: pass an explicit light scheme and do not call `isSystemInDarkTheme()`. Consequence and owner are recorded in U2.
- Shapes stay at the Material 3 baseline (`MaterialTheme` default): `DESIGN.md` asks for simple rounded cards/buttons, which the baseline already provides; introducing a custom shape scale is unverified work.

### 7. Previews and the token board

- Replace the `MaterialTheme {` wrapper in all seven `App.kt` previews and all eight `AddLandScreen.kt` previews (fifteen in total) with `ManijeroTheme {`. Previews must never show the default palette. `AppAndroidPreview` in `MainActivity.kt` calls `App()` and is therefore already themed.
- Add a review-only `@Preview` composable in the theme file (light, plus one at `fontScale = 2f`) that renders each token as a labelled swatch, a caution callout (`cautionSurface` fill + `caution` text), a danger line (existing `Res.string.add_land_save_failed`), and a selected/unselected `RadioButton` pair. This is how caution/danger and contrast can be reviewed before `response_states` ships. Preview-only sample strings are acceptable (existing previews already use literals); no shipped string is added, so `strings.xml` is unchanged.

### 8. Non-color cue requirements (binding for this layer and its consumers)

1. Caution and danger are always paired with text (and, if an icon is used, text or a `contentDescription`); never color or icon alone.
2. Error/validation states keep a text `supportingText` plus the control's own error semantics (`OutlinedTextField(isError = …)`); a red border alone is not acceptable.
3. Selection (radio groups, chosen land, selected navigation) is communicated by the control's semantics (`selected`, `Role.RadioButton`) and its label, not by the primary color alone.
4. Transcript speakers stay labelled in text ("Tú"/"Asistente"); `surfaceVariant` vs `surface` is decoration, never the only distinction.
5. Disabled controls rely on `enabled = false` semantics; when the reason is not obvious (for example the question limit), visible text explains it. WCAG 1.4.3 exempts inactive controls, and the theme keeps Material's disabled state layers rather than inventing a low-contrast enabled look.
6. Visible focus indicators on Desktop must not be removed or made transparent by theming; `primary` against `canvas`/`surface` is ≥ 3:1 for that reason.
7. Do not lower `LocalMinimumInteractiveComponentSize`; Material's 48dp minimum interactive size is the large-touch-target guarantee.

### 9. Contrast verification (expected values)

Computed at planning time with the WCAG 2.x relative-luminance formula; the tests must reproduce them.

Text/icon pairs (≥ 4.5:1): `onBackground`/`onSurface` on canvas/surface 14.96 / 16.19 · `onSurfaceVariant` on canvas/surface 7.54 / 8.16 · `onPrimary` on `primary` 9.53 · `primaryStrong` as text on canvas 11.72 · `primary` as label on canvas 8.80 and on surface 9.53 · `onSurface` on `surfaceVariant` 12.84 · `primary` label on `surfaceVariant` 7.55 · `caution` on `cautionSurface` 7.37, on canvas 7.56, on surface 8.19 · `onCaution` on `caution` 8.19 · `error` on surface 7.46 and on canvas 6.89 · `onError` on `error` 7.46 · `error` on `errorContainer` 5.86 · `onErrorContainer` on `errorContainer` 9.18 · `onPrimaryContainer` on `primaryContainer` 9.53 · `onSecondaryContainer` on `secondaryContainer` 9.81 · `onSecondary` on `secondary` 8.16 · `onTertiary` on `tertiary` 7.93 · `onTertiaryContainer` on `tertiaryContainer` 10.68 · `inverseOnSurface` on `inverseSurface` 11.47 · `inversePrimary` on `inverseSurface` 7.06 · `onSurface` on the surface-container/dim/bright values 11.90-16.16 · `onSurfaceVariant` on `surfaceContainerHighest` 6.47.

Non-text pairs (≥ 3:1): `outline` on canvas 3.91 and on surface 4.23 · `outlineVariant` on canvas 3.55, on surface 3.84, on `surfaceVariant` 3.05, on `surfaceContainer` 3.37 · `primary` vs canvas 8.80 · `error` vs canvas 6.89 · `caution` vs `cautionSurface` 7.37.

Documented non-requirements: container fills (`surface` vs `canvas` 1.08, `surfaceVariant` vs `canvas` 1.16) are intentionally low-contrast; WCAG 1.4.11 is satisfied by the 3:1 boundary token, and grouping is also carried by text. Disabled controls (composited ~2.29:1) are exempt under 1.4.3.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`: `DESIGN.md` tokens and derived values as documented `internal` Compose `Color` constants, `ManijeroLightColorScheme: ColorScheme`, `ManijeroSemanticColors` + `LocalManijeroSemanticColors`, and the `internal` WCAG helpers `relativeLuminance(Color)` / `contrastRatio(Color, Color)`. No Compose UI imports beyond `androidx.compose.ui.graphics.Color` and `material3`.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTypography.kt`: `ManijeroTypography: Typography` with the single documented `bodySmall` line-height override.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTheme.kt`: `ManijeroTheme(content)`, the semantic-color provider, and the token-board previews.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: wrap the destination content in `ManijeroTheme`; switch the seven previews from `MaterialTheme {` to `ManijeroTheme {`. No layout, copy, or behavior change.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: switch the eight previews from `MaterialTheme {` to `ManijeroTheme {`. No layout, copy, or behavior change.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/theme/ManijeroColorsTest.kt`: token values, role mapping, "no Material default leaked", and the contrast pairs.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/theme/ManijeroTypographyTest.kt`: the line-height rule, `labelLarge` rule, and no bundled font family.
- **Do not modify** `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`, `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`, `shared/src/iosMain/.../MainViewController.kt`, `shared/src/commonMain/composeResources/values/strings.xml`, any Gradle file or version catalog, backend/contracts, land storage, or `init.sh`.
- **Documentation (implementation phase):** update the `DESIGN.md` "Visual foundation" section with the derived token table and the light-only decision; optionally add one row to the implementation-time table in `docs/risks-and-open-questions.md` for dark mode / launcher artwork. Planning changes neither.

## Implementation plan and tasks

1. Write `ManijeroColorsTest` expectations first (exact hex values, role mapping, contrast thresholds), then implement `ManijeroColors.kt` until the test passes. Keep the WCAG helper in the palette file and free of I/O.
2. Add `ManijeroTypography.kt` with the single override and its test.
3. Add `ManijeroTheme.kt` (theme + semantic local + token-board previews); confirm the preview renders olive/canvas values, not purple.
4. Apply `ManijeroTheme` once inside `App()`; repoint all fifteen existing previews; run the existing suites to confirm no behavior regression.
5. Re-run the contrast table against the shipped values and correct any value that misses its threshold by adjusting the derived value (never by lowering the threshold or dropping a pair).
6. Run the full command set below, capture output, then perform the Android and Desktop manual checks and the greyscale non-color cue check.
7. After implementation and independent validation only: update `feature_list.json`/`PROGRESS.md`, refresh the `init.sh` banner text, and make the `DESIGN.md` documentation update.

## Verification plan and evidence

Run from the repository root:

```sh
./init.sh                                   # toolchain check; creates local.properties
./gradlew :shared:jvmTest                   # existing suites + new theme tests
./gradlew :shared:testAndroidHostTest       # same tests on the Android host
./gradlew :androidApp:assembleDebug
./gradlew :desktopApp:build
./init.sh --verify                          # the accepted one-shot check
```

Automated, in-repo checks:

- Token contract: each `DESIGN.md` token and derived value equals the exact hex in this spec.
- Mapping: each tested `ColorScheme` role equals its documented value (`background` = canvas, `primary` = olive-800, `surface` = white, `surfaceVariant`, `onSurfaceVariant`, `onSurface`, `onBackground`, `outline`, `outlineVariant`, `error`, `errorContainer`, `primaryContainer`, `secondaryContainer`, `tertiaryContainer`, `inverseSurface`).
- No default palette: for the brand-bearing roles listed in this spec, assert the value differs from `lightColorScheme()`'s own default (computed at runtime, not hard-coded) so a future Material default cannot leak in.
- Contrast: the documented text pairs ≥ 4.5:1 and non-text pairs ≥ 3:1, using the repository's own helper; failure messages must name the pair and the measured ratio.
- Centralization: `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt` returns matches only under `theme/`; `grep -rn "MaterialTheme {" shared/src/commonMain` returns nothing (no argument-less default-palette wrapper remains) and `grep -rn "MaterialTheme("` matches only `theme/ManijeroTheme.kt`; `grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src` returns nothing.

Manual checks (record screenshots or a short written record for each):

1. Android emulator (`Medium_Phone_API_35`, debug APK from `:androidApp:assembleDebug`): canvas page background, olive `Preguntar`/`Guardar terreno` buttons, olive `Mis terrenos` navigation label, `Tú` bubble in the low-emphasis neutral and `Asistente` in white with a visible border, and no purple/blue anywhere on the chat or add-land screens.
2. Desktop (`./init.sh --desktop`): the same checks, plus window resize (narrow and wide) and keyboard focus visibility on the field, `Preguntar`, and `Guardar terreno`.
3. Android Studio preview panel: every preview in `App.kt`, `AddLandScreen.kt`, and the theme file renders the olive/canvas palette, and the token-board preview shows caution and danger pairs.
4. Text scaling: Android `font_scale 2.0` and the `fontScale = 2f` previews — nothing clipped or overlapped on either screen. Desktop OS-level text scaling is not wired in this repository (verified: no font-scale integration exists), so Desktop evidence is preview-based; report that limitation instead of claiming a Desktop scaling pass.
5. Non-color cues: render the danger message and the caution callout sample, convert the screenshot to greyscale, and confirm the state is still readable from text and control semantics alone.
6. Submit a question and save a land once on each platform to confirm theming changed appearance only.

Evidence to capture: the two test-task outputs with new test names and counts, `--verify` output (or the exact Android SDK blocker), screenshots/preview captures for chat, add-land, token board, and enlarged text, the greyscale capture, and the three `grep` outputs. This repository has **no persistent E2E or screenshot-test command** (verified: `./init.sh --verify` only runs the shared host tests and the Android/Desktop builds, and no Compose UI-test dependency or harness exists), so focused pure unit tests plus the Android/Desktop manual checks above are the justified coverage for this presentation-layer feature; report that limitation honestly instead of implying E2E coverage. Desktop font-scaling and Android launch-frame behavior remain known gaps (U2, U3, U4).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | **Update during implementation** | Add the derived-token table and the light-only decision so the token source of truth stays in one place. Planning made no change. |
| `docs/risks-and-open-questions.md` | Optional update | One or two implementation-time rows for dark-mode/light-only support and the missing olive launcher artwork. |
| `ARCHITECTURE.md` | Not needed | Does not exist; no durable architectural decision beyond "shared tokens in `commonMain`", already stated in `AGENTS.md` and `DESIGN.md`. |
| `CONSTRAINTS.md` | Not needed | Does not exist; this feature adds no constraint beyond the accessibility baseline already documented. |
| `AGENTS.md` | Not needed | Its shared-UI, Spanish, accessibility, and no-new-module rules already cover this work. |
| `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md` | Not needed | No product, glossary, or domain change. |
| `init.sh` | Not needed for acceptance | The script needs no new mode and must not start a service; refresh the informational banner wording only after acceptance. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record evidence/status only after independent validation; planning does not touch them. |

## Unknowns and risks

- **U1 Launcher artwork:** the app icon is the stock Android Studio template (green `#3DDC84`, white robot). There is no olive-grove artwork to compare against, so no token is changed on that basis. A real launcher asset belongs to a later branding/release feature; this feature keeps the `DESIGN.md` values.
- **U2 Light-only theme:** no dark tokens exist and dark mode is explicitly out of scope. A person whose system is in dark mode still sees the light warm theme (the Android activity theme is already `Theme.Material.Light.NoActionBar`). Acceptable for MVP; record as a follow-up rather than silently implying dark support.
- **U3 Desktop text scaling:** Compose Desktop in this repository does not surface an OS font-scale setting, so Desktop large-text evidence is preview-based only; the runtime check belongs to `chat_accessibility` (carried validator finding F3).
- **U4 Android launch frame:** with `enableEdgeToEdge()` and no shared insets handling, a brief platform-colored launch frame and possible status/navigation-bar overlap are pre-existing; verify during manual checks and report, but do not expand this token-layer feature into inset or window-background resource work (owner: `chat_accessibility`/release polish).
- **U5 Material 3 alpha API:** `material3 1.12.0-alpha03` may deprecate `surfaceVariant` or omit a newer role. Keep existing call sites unchanged; omit an unsupported role from the scheme and its test row instead of adding a dependency.
- **R1 Low container contrast:** card/bubble fills differ from the page by ~1.1-1.3:1 by design. Every container that needs to read as a card must draw `outline`/`outlineVariant` or use a Material `Card` with defined elevation; the token layer cannot fix separation by luminance without breaking the calm look.
- **R2 Test classpath:** `commonTest` is expected to reach `androidx.compose.ui.graphics.Color` through its association with `commonMain`. If it cannot, move the token values to plain ARGB constants in the same `theme` file and build `Color` values from them (one file, no new dependency, tests unchanged in intent).
- **R3 Preview-only verification:** caution/danger have no shipping surface yet, so they are proven by the token-board preview and the contrast tests; `response_states` and `network_error_recovery` must consume them, not redefine them.

## Validator checklist

- [ ] Tokens live only in `shared/src/commonMain/.../theme/` (no new module, no new dependency, no hardcoded hex outside `theme/`).
- [ ] Every `DESIGN.md` token value ships unchanged, and every derived value appears in the spec's table with a reason.
- [ ] `lightColorScheme(...)` sets every role listed in the spec; no screen, host, or preview renders Material's default purple/blue.
- [ ] `ManijeroTheme` is applied once at the shared composition root, so Android, Desktop, `MainViewController`, and all `App()` previews inherit it; platform roots contain no second theme.
- [ ] All fifteen existing previews use the shared theme; the token-board preview shows every token plus caution and danger samples.
- [ ] `:shared:jvmTest` and `:shared:testAndroidHostTest` pass with new tests covering exact token values, role mapping, "no Material default leaked", and the documented contrast thresholds (≥ 4.5:1 text, ≥ 3:1 non-text); the measured ratios match this spec.
- [ ] Non-color cue requirements hold: no color-only caution/danger/selection/validation/disabled cue; visible focus is preserved; 48dp minimum interactive size is untouched.
- [ ] Themed screens keep plain Spanish copy, existing behavior, and land persistence; no chat/land logic, contract, backend, or storage change.
- [ ] Enlarged-text checks show no clipping on the chat and land screens, with the Desktop scaling limitation reported rather than claimed.
- [ ] Android and Desktop manual evidence (screenshots or a written record) shows canvas background, olive primary, surface cards/inputs, and caution/danger pairs, and the greyscale check is recorded.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the spec's file list matches the actual diff.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ManijeroColorsTest --tests ManijeroTypographyTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/visual_foundation.md.
- New shared theme package in commonMain (shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/): ManijeroColors.kt (DESIGN.md tokens + derived values, a fully specified lightColorScheme, ManijeroSemanticColors/LocalManijeroSemanticColors, dependency-free WCAG helpers), ManijeroTypography.kt (single documented bodySmall 16sp->18sp line-height override), and ManijeroTheme.kt (theme + semantic local + review-only token-board previews).
- ManijeroTheme is applied once inside App() (the shared composition root) and all fifteen existing previews (seven in App.kt, eight in AddLandScreen.kt) use it; the Android, Desktop and iOS hosts stay theme-free and inherit one shared theme. No layout, copy, spacing, or behavior changed; no new module, framework, or dependency.
- ./init.sh --verify -> BUILD SUCCESSFUL. ./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks -> BUILD SUCCESSFUL: 54 JVM tests / 0 failures (ManijeroColorsTest 10, ManijeroTypographyTest 4 new) and 51 Android host tests / 0 failures; :androidApp:assembleDebug and :desktopApp:build pass.
- Centralization greps: no Color(0x outside theme/; no argument-less MaterialTheme {; MaterialTheme( only in theme/ManijeroTheme.kt; no LocalMinimumInteractiveComponentSize/minimumInteractiveComponentSize override.
- DESIGN.md updated with the derived-token table and the light-only decision. Self-verified; awaiting independent validation.
- Independent validator ACCEPTED (record: docs/validations/visual_foundation.md) after re-running ./init.sh --verify and :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks (54 JVM / 51 Android host tests, 0 failures), reproducing the WCAG pairs with an independent computation, and confirming scope discipline (commonMain-only theme, no new module/dependency, hosts/strings/Gradle untouched, no logging).
