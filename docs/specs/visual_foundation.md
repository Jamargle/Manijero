# Feature Spec: `visual_foundation`

> **Palette superseded (2026-10-25):** the colour values in this spec are the accepted historical
> contract. The approved replacement palette is the Stitch token block (light and dark exports),
> recorded in `docs/design/ui-refresh-plan.md` §3.1 and `DESIGN.md` with two `outlineVariant`
> accessibility corrections; it takes effect when `design_token_refresh` is implemented. Behavior
> and verification requirements here are unchanged.

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
- A complete `lightColorScheme(...)` mapping (no role left at a Material default), Material 3 default typography (no custom type scale), and a small semantic-color local for the tokens Material 3 has no role for (caution, caution surface, strong olive).
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

Typography is the Material 3 default `Typography()`, which resolves to the platform font via `FontFamily.Default`. No custom typography object, size/weight/letter-spacing change, line-height override, or bundled font asset is introduced, and text stays scalable with `sp`.

> Amendment 2026-10-25: this contract originally specified a `bodySmall` line-height override (`16.sp → 18.sp`). The owner removed it in favor of pure Material defaults to reduce maintenance surface; the override and its test no longer exist.

### 6. Theme application

- `internal fun ManijeroTheme(content: @Composable () -> Unit)` wraps `MaterialTheme(colorScheme = ManijeroLightColorScheme, content = ...)` inside `CompositionLocalProvider(LocalManijeroSemanticColors provides ManijeroSemanticColors)`. Typography stays the Material 3 default.
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
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroTheme.kt`: `ManijeroTheme(content)`, the semantic-color provider, and the token-board previews. Typography keeps the Material 3 default; no typography file is created.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: wrap the destination content in `ManijeroTheme`; switch the seven previews from `MaterialTheme {` to `ManijeroTheme {`. No layout, copy, or behavior change.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: switch the eight previews from `MaterialTheme {` to `ManijeroTheme {`. No layout, copy, or behavior change.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/theme/ManijeroColorsTest.kt`: token values, role mapping, "no Material default leaked", and the contrast pairs.
- **Do not** add a typography test: typography is the Material 3 default with no local values to assert.
- **Do not modify** `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`, `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`, `shared/src/iosMain/.../MainViewController.kt`, `shared/src/commonMain/composeResources/values/strings.xml`, any Gradle file or version catalog, backend/contracts, land storage, or `scripts/init.sh`.
- **Documentation (implementation phase):** update the `DESIGN.md` "Visual foundation" section with the derived token table and the light-only decision; optionally add one row to the implementation-time table in `docs/risks-and-open-questions.md` for dark mode / launcher artwork. Planning changes neither.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | **Update during implementation** | Add the derived-token table and the light-only decision so the token source of truth stays in one place. Planning made no change. |
| `docs/risks-and-open-questions.md` | Optional update | One or two implementation-time rows for dark-mode/light-only support and the missing olive launcher artwork. |
| `ARCHITECTURE.md` | Not needed | Does not exist; no durable architectural decision beyond "shared tokens in `commonMain`", already stated in `AGENTS.md` and `DESIGN.md`. |
| `CONSTRAINTS.md` | Not needed | Does not exist; this feature adds no constraint beyond the accessibility baseline already documented. |
| `AGENTS.md` | Not needed | Its shared-UI, Spanish, accessibility, and no-new-module rules already cover this work. |
| `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md` | Not needed | No product, glossary, or domain change. |
| `scripts/init.sh` | Not needed for acceptance | The script needs no new mode and must not start a service; refresh the informational banner wording only after acceptance. |
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

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ManijeroColorsTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/visual_foundation.appendix.md`](../archive/specs/visual_foundation.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/visual_foundation.md` remains the authoritative acceptance record.
