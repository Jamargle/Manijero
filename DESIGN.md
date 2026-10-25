# Design Direction — Olive Grove Assistant

## Scope and authority

Use this guide for shared UI design and Spanish user-facing copy. Feature behavior belongs in its
spec; architecture and source-set boundaries belong in `ARCHITECTURE.md`; implementation and
verification status belong in `PROGRESS.md` and `docs/validations/`.

Stitch mockups reference archive is indexed in [`design-references/README.md`](design-references/README.md). The shared app's palette is the Stitch token palette, with two documented accessibility corrections; the values are recorded below. The launcher icon is an identity asset, not a UI reference.

### Reference designs and adoption rules

- Treat screen PNGs and HTML under `design-references/stitch/` as visual inspiration, not production-ready Compose or a source of truth for product behavior.
- The winning palette is the `colors:` token block in the front matter of `stitch/manijero_design_system/DESIGN.md` (light) and `stitch/manijero_design_system_dark_mode/DESIGN.md` (dark). Those are the values the exported screens were generated from. The prose colour names in the light export — deep olive `#385E39`, earth brown `#8C6239`, sun-baked amber `#D9A036`, limestone cream `#F4F1EA` — contradict that same file's token block and its screenshots; they are retained as provenance, not adopted.
- Two accessibility corrections are the only deviations from Stitch: `outlineVariant` `#C2C8BD` → `#757C71` in light and `#424942` → `#868E86` in dark. Stitch's values measure 1.63:1 and 1.97:1 against the page, and this repository gates non-text boundaries at 3:1. Every other role keeps its Stitch value verbatim. `scrim` `#000000` is the one role neither export defines.
- Stitch PRD/masterplan text is historical design input. Where it proposes behavior outside the current MVP (for example navigation or content not in the accepted contracts), existing product scope and approved feature specs take precedence.
- Screen references map to existing feature contracts rather than creating duplicate feature entries. See the archive index for the mapping and known gaps.

### Shared design system

`shared_design_system` defines paired roles in `shared/src/commonMain`, selected automatically with the common Compose system appearance signal. No appearance setting or platform theme fork exists. The constructors explicitly map every applicable Material 3 role plus the semantic caution, emphasis, and Ecológico chip colours; source values are in `ManijeroColors.kt`. Common previews cover light, dark, and enlarged text. Shape and spacing scales live in `ManijeroTokens.kt`.

**Typography:** the app uses the Material 3 default typography, which resolves to the platform font. Stitch's Source Serif 4 / Source Sans 3 scale is not adopted: no custom family, scale, or bundled font asset is part of the design system.

**Palette status (2026-10-25).** The values below are the implemented palette: `design_token_refresh` applies them in `ManijeroColors.kt` and re-gates the contrast tests in both appearances. Earlier acceptance records keep their original values as history.

## Design intent

Design for people who may use apps only occasionally. Make the interface calm, familiar, practical,
and reassuring. Use everyday Spanish; make the next action obvious and explain agricultural or legal
terms. Never imply that an answer is legally definitive through confident visual treatment.

## Visual foundation

The palette is the Stitch agricultural system: deep olive primary, earth-brown secondary, plum tertiary in light mode and blue tertiary in dark mode, over a limestone-neutral family. Keep the values centralized; do not use raw colour literals in screens. The shared theme is the only implementation location for hex colours and maps them to Material 3 roles or semantic colours.

### Core tokens

The ten accepted token names keep their roles. Seven take the Stitch value; `primaryStrong`, `caution`, and `caution-surface` stay as accepted because Stitch has no emphasis or status roles. `surface` here means card and input surfaces, so it maps to `surfaceContainerLowest` (`#FFFFFF`), because Stitch's own `surface` equals `background`.

| Token | Light | Dark | Material role |
|---|---|---|---|
| `primary` (`olive-800`) | `#214624` | `#85A886` | `primary` |
| `primaryStrong` (`olive-900`) | `#263724` | `#CFE8CF` | no role; semantic emphasis |
| `canvas` | `#F9FAF4` | `#121612` | `background` |
| `surface` | `#FFFFFF` | `#0D100D` | `surfaceContainerLowest` |
| `text-primary` | `#1A1C19` | `#E1E3DF` | `onSurface` / `onBackground` |
| `text-secondary` | `#424940` | `#C2C8BF` | `onSurfaceVariant` |
| `border` | `#72796F` | `#8C948C` | `outline` |
| `caution` | `#704600` | `#FFD18A` | no role; semantic |
| `caution-surface` | `#FFF2D4` | `#4B350D` | no role; semantic |
| `danger` | `#BA1A1A` | `#FFB4AB` | `error` |

`outlineVariant` is a separate gated boundary token rather than one of those ten: light `#757C71`, dark `#868E86` — the corrected values. The shared theme is the only place in the repository allowed to declare a hex colour; screens read Material 3 roles or the `LocalManijeroSemanticColors` values instead. The launcher artwork is still the stock Android Studio template, so no token was changed on that basis.

### Material role map

Stitch exports a complete Material 3 role set in both modes, so no role is left to a derived value. Roles are listed in pairs.

| Material roles | Light | Dark |
|---|---|---|
| primary / onPrimary | `#214624` / `#FFFFFF` | `#85A886` / `#0D1B0E` |
| primaryContainer / onPrimaryContainer | `#385E39` / `#ABD6A7` | `#283C29` / `#CFE8CF` |
| secondary / onSecondary / secondaryContainer / onSecondaryContainer | `#7E562E` / `#FFFFFF` / `#FDC796` / `#79512A` | `#D4C5A9` / `#382E1C` / `#4F422E` / `#F1E5CC` |
| tertiary / onTertiary / tertiaryContainer / onTertiaryContainer | `#602E40` / `#FFFFFF` / `#7B4557` / `#FEB7CC` | `#B8C5D6` / `#222D3B` / `#93A0B0` / `#2B3745` |
| background / onBackground; surface / onSurface | `#F9FAF4` / `#1A1C19`; `#F9FAF4` / `#1A1C19` | `#121612` / `#E1E3DF`; `#121612` / `#E1E3DF` |
| surfaceVariant / onSurfaceVariant / surfaceTint | `#E2E3DD` / `#424940` / `#416741` | `#333532` / `#C2C8BF` / `#ABD0AC` |
| inverseSurface / inverseOnSurface / inversePrimary | `#2F312D` / `#F1F1EB` / `#A7D2A3` | `#E3E3DE` / `#2F312E` / `#456648` |
| error / onError / errorContainer / onErrorContainer | `#BA1A1A` / `#FFFFFF` / `#FFDAD6` / `#93000A` | `#FFB4AB` / `#690005` / `#93000A` / `#FFDAD6` |
| outline / outlineVariant (corrected) / scrim | `#72796F` / `#757C71` / `#000000` | `#8C948C` / `#868E86` / `#000000` |
| surfaceBright / surfaceDim | `#F9FAF4` / `#DADAD5` | `#242C24` / `#1A201B` |
| surfaceContainerLowest / Low / Container / High / Highest | `#FFFFFF` / `#F3F4EE` / `#EEEEE9` / `#E8E9E3` / `#E2E3DD` | `#0D100D` / `#181E18` / `#202820` / `#2C362C` / `#384438` |

Light `background`, `surface`, and `surfaceBright` are the same `#F9FAF4`. Cards, inputs, and app bars that must read as raised therefore use `surfaceContainerLowest` (`#FFFFFF`) or the low/container family, never `surface`.

`outlineVariant` is the one documented deviation: `#757C71` and `#868E86` are the softest in-family values that still clear 3:1 on every light and dark surface. They sit close to `outline` (`#72796F` / `#8C948C`); that reduced separation is the deliberate cost of the accessibility gate.

Stitch also exports expressive `*Fixed` roles, which this Material version does not expose; they are not claimed as mapped. The Ecológico chip pair is exposed as the semantic `ecoContainer` / `onEcoContainer` values below because `primaryFixed` / `onPrimaryFixed` cannot be roles here.

### Manijero-only semantic colours

Stitch has no status or warning roles, so these four stay as accepted and are the only non-Stitch values in the system besides the two `outlineVariant` corrections: `caution`, `cautionSurface`, `onCaution`, and `primaryStrong`. They have no Material 3 role and are provided through `LocalManijeroSemanticColors`. `danger` is `colorScheme.error` and `border` is `colorScheme.outline`, so each value keeps a single source.

| Token | Light | Dark | Use |
|---|---|---|---|
| `caution` | `#704600` | `#FFD18A` | Uncertainty and limitations, always with text/icon |
| `cautionSurface` | `#FFF2D4` | `#4B350D` | Caution callout background |
| `onCaution` | `#FFFFFF` | `#3A2600` | Text/icon on filled caution |
| `primaryStrong` | `#263724` | `#CFE8CF` | Pressed state and strong emphasis (`olive-900`) |

There are no separate `earth`, `earthContainer`, `sun`, or `sunContainer` tokens. Stitch `secondary` (earth brown) and `tertiary` (plum in light, blue in dark) carry decorative and sectional accents; they must never be the only cue for caution, error, eligibility, or verification. `caution` and `danger` remain the only status hues.

### Land-attribute chips

Chip colours reuse Stitch role pairs rather than introducing new hues; every pair clears 4.5:1 with text.

| Chip | Light container / ink | Dark container / ink | Anchor pair |
|---|---|---|---|
| Secano | `#FDC796` / `#79512A` | `#4F422E` / `#F1E5CC` | `secondaryContainer` / `onSecondaryContainer` |
| Regadío | `#385E39` / `#ABD6A7` | `#283C29` / `#CFE8CF` | `primaryContainer` / `onPrimaryContainer` |
| Ecológico | `#C2EEBE` / `#002106` | `#C7ECC6` / `#02210A` | semantic `ecoContainer` / `onEcoContainer` |
| Neutral / `No lo sé` | `#E2E3DD` / `#1A1C19` | `#384438` / `#E1E3DF` | `surfaceContainerHighest` / `onSurface` |

Chips always carry text, never colour alone.

### Contrast contract

Common tests enumerate the intended readable text pairs (on-colour for primary, secondary,
tertiary, background, surface, surface-variant, tonal containers, inverse surface, error and error
container) at >=4.5:1, and non-text boundaries/icons (error against background, outline against
surface/background/surface-variant, outline-variant against background, surface, and every container
from lowest through highest plus `surfaceDim`, primary against surface) at >=3:1. Semantic tests also
check `caution` on `background` in light and on `surfaceContainerLowest` in dark, `caution` on
`cautionSurface` in both, `onCaution` on its filled caution colour, and every land-attribute chip
pair.

The ratios below are WCAG 2.x relative-luminance results calculated from the values above. The shared
theme tests assert them, so the test helper remains the gate, and any later value change must
recompute them.

Light:

- Text: `onSurface` on background/surface 16.35, on `surfaceContainerLowest` 17.16, on the container
  family 15.51 / 14.74 / 14.05 / 13.29, on `surfaceDim` 12.23. `onSurfaceVariant` on
  background 8.86, on `surfaceContainerLowest` 9.30, on the container family 8.41 / 7.99 / 7.61 /
  7.20, on `surfaceDim` 6.63.
- Brand: `onPrimary`/`primary` 10.68; `onPrimaryContainer`/`primaryContainer` 4.56;
  `secondary`/background 6.14; `onSecondary`/`secondary` 6.45;
  `onSecondaryContainer`/`secondaryContainer` 4.56; `tertiary`/background 10.20;
  `onTertiary`/`tertiary` 10.70; `onTertiaryContainer`/`tertiaryContainer` 4.54;
  `primaryStrong`/background 12.09.
- Status: `caution`/`cautionSurface` 7.37, /background 7.80, /`surfaceContainerLowest` 8.19;
  `onCaution`/`caution` 8.19; `error`/background 6.16, /`surfaceContainerLowest` 6.46,
  /`surfaceVariant` 5.00; `onError`/`error` 6.46; `error`/`errorContainer` 5.00;
  `onErrorContainer`/`errorContainer` 7.24.
- Tonal and inverse: `inverseOnSurface`/`inverseSurface` 11.59;
  `inversePrimary`/`inverseSurface` 7.75.
- Non-text: `outline`/background 4.28, /`surfaceContainerLowest` 4.49, /`surfaceVariant` 3.48;
  `outlineVariant`/background 4.10, /`surfaceContainerLowest` 4.31, /`surfaceContainerLow` 3.89,
  /`surfaceContainer` 3.70, /`surfaceContainerHigh` 3.53, /`surfaceContainerHighest` 3.33,
  /`surfaceDim` 3.07; `primary`/background 10.18; `error`/background 6.16.
- Land chips: 4.56 (Secano), 4.56 (Regadío), 13.33 (Ecológico), 13.29 (Neutral).

Dark:

- Text: `onSurface` on background/surface 14.14, on `surfaceContainerLowest` 14.82, on the container
  family 13.13 / 11.73 / 9.73 / 7.92, on `surfaceDim` 12.84. `onSurfaceVariant` on
  background 10.71, on `surfaceVariant` 7.26, on `surfaceContainerHighest` 6.00.
- Brand: `onPrimary`/`primary` 6.73; `primary`/background 6.91;
  `onPrimaryContainer`/`primaryContainer` 9.10; `secondary`/background 10.75;
  `onSecondary`/`secondary` 7.84; `onSecondaryContainer`/`secondaryContainer` 7.82;
  `tertiary`/background 10.44; `onTertiary`/`tertiary` 7.96;
  `onTertiaryContainer`/`tertiaryContainer` 4.55; `primaryStrong`/background 14.01.
- Status: `error`/background 10.76; `onError`/`error` 7.72; `error`/`errorContainer` 5.51;
  `onErrorContainer`/`errorContainer` 7.24; `caution`/`cautionSurface` 8.12;
  `caution`/`surfaceContainerLowest` 13.44; `onCaution`/`caution` 10.12.
- Tonal and inverse: `inverseOnSurface`/`inverseSurface` 10.20;
  `inversePrimary`/`inverseSurface` 5.02.
- Non-text: `outline`/background 5.86, /`surfaceVariant` 3.97; `outlineVariant`/background 5.42,
  /`surfaceContainerLowest` 5.68, /`surfaceContainerLow` 5.03, /`surfaceContainer` 4.49,
  /`surfaceContainerHigh` 3.73, /`surfaceContainerHighest` 3.03, /`surfaceDim` 4.92.
- Land chips: 7.82 (Secano), 9.10 (Regadío), 13.26 (Ecológico), 7.92 (Neutral).

Checks test the full listed pair set, not every mathematically possible combination of roles.

## Brand vectors and iconography

The identity layer is hand-authored vector XML under
`shared/src/commonMain/composeResources/drawable/`, drawn by thin wrappers in
`com.jamarglex.manijero.design`. Every vector is a single-colour mask, so one asset serves both
appearances. Names and geometry are fixed by
[`docs/specs/brand_vectors.md`](docs/specs/brand_vectors.md); screens adopt them in later features.

### Icon set

- Sixteen outline glyphs. A screen needing another glyph extends the inventory in its own feature
  instead of drawing a path inline.
- Geometry: 24 dp on a 24×24 viewport, 2 dp stroke, round caps and joins, no fill, content inside the
  2–22 dp safe area. Sizes: 24 dp default, 20 dp inline (`ManijeroIconSize.Default` / `Inline`); never
  stretched.
- `ManijeroIcon(resource, contentDescription, …)` is the only supported way to draw one. The
  description has no default, so each call site states whether the glyph carries meaning (`null` =
  decorative). Pair unclear icons with text; the wrapper adds no padding, touch target, or click
  handling — interactive icons go inside the consuming feature's `IconButton`.
- Tint: `LocalContentColor` by default. Do not hardcode a colour to express status; `caution` and
  `danger` stay the only status hues, and no icon alone conveys caution, error, eligibility, or
  verification.

### Brand mark and empty-state illustration

- `ManijeroBrandMark(modifier, size)`: open olive ring with a leaf, `primary`, 32 dp default (28 and
  48 dp valid), no blur, no description or colour parameter. Identity only — never a check, seal,
  badge, or "verified" cue, and never applied to an answer, source, or land.
- `ManijeroOliveBranch(modifier, size)`: olive sprig on a circular `primaryContainer` halo painted in
  Compose, sprig `onPrimaryContainer`, 160–200 dp (180 dp default), decorative with no semantics node.
  The surface shows the text that explains the empty state.
- The gated pairs (`primary`/`background`; `onPrimaryContainer`/`primaryContainer`) cover the tints.

### Asset and tint policy

- Vectors carry no appearance colour: only `#000000` and `#00000000` literals, no `android:tint`,
  gradient, `aapt:attr`, clip path, or external reference, and only the XML subset Compose
  Multiplatform decodes on Android, Desktop, and iOS.
- No generated imagery, raster asset, icon font, `material-icons-*` dependency, or new token.
- Material Symbols conventions (Apache 2.0) inform the geometry; path data is original to the
  repository. The licence record is in the feature appendix.

## Shared component layer

`ui_component_library` adds the presentational blocks the screen refreshes adopt in later features:
`ManijeroScreen`, `ManijeroCard`, `ManijeroSectionHeader`, `ManijeroCallout`, `ManijeroStatCard`,
`ManijeroEmptyState`, `ManijeroAttributeChip`, `ManijeroChoiceCard`, `ManijeroSearchField`,
`ManijeroDropdownField`, `ManijeroMeasureField`, and the navigation components
`ManijeroTopAppBar`, `ManijeroBottomNavigation` and `ManijeroNavigationRail`. They live under
`shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` (navigation in `design/navigation/`),
are `internal`, preview-backed, and take every visible string, value, icon, selection and callback
as a parameter. The layer owns no copy, domain type, store, request or business rule and never reads
`Res.string`. The app shell adopts the navigation components today; the remaining components are
adopted by the screen refreshes.

- **Page frame.** `ManijeroScreen` paints `background`, owns one vertical scroll, applies 24 dp
  horizontal padding below 840 dp and 40 dp from it, 32 dp vertical padding, and centres a 720 dp
  content column. It owns no window insets and no bars; the shell's future `Scaffold` is the single
  inset owner.
- **Containers.** `ManijeroCard` has `Surface`, `Tonal`, `Outlined` and `Danger` tones (16 dp
  radius; 1 dp `outlineVariant` or `error` border where the tone defines one) and is never
  clickable: a caller puts its own button, link or choice row inside. `ManijeroSectionHeader` emits
  a real `heading()` only when asked. `ManijeroStatCard` requires the caption that states what the
  value counts. `ManijeroEmptyState` pairs the decorative olive branch with a real heading, a plain
  explanation and one caller-supplied action.
- **Messages and attributes.** `ManijeroCallout` has `Info`, `Caution`, `Danger` and `Confirmation`
  tones, always an icon plus the caller's text, only its title-and-text block a polite live region,
  and an optional action slot that stays its own focusable node. `ManijeroAttributeChip` carries the
  four accepted chip pairs, always its own label, and no click or target.
- **Choices and fields.** One `ManijeroChoiceCard` is one radio option (`Role.RadioButton`,
  description merged into the announced name, error border); the consuming form owns the
  `selectableGroup`. `ManijeroSearchField` has a named 48 dp clear action and filters nothing;
  `ManijeroDropdownField` renders an exposed menu; `ManijeroMeasureField` is a decimal field with no
  parser. Validation, formatting and totals stay in the owning feature.
- **Navigation.** `ManijeroTopAppBar` is a flat `surfaceContainerLowest` bar with a 1 dp
  `outlineVariant` divider and no shadow: the 32 dp brand mark (identity, never status), the title,
  and an optional privacy action. From 840 dp the action is a `TextButton` with `ic_info` plus the
  visible label; below it an `IconButton` named by the caller's description. The fixed inventory has
  no shield, so the accessible name carries the meaning; a shield stays a later, visually reviewed
  asset change. `ManijeroBottomNavigation` and `ManijeroNavigationRail` keep every label visible,
  mark the selection with Material's indicator plus a heavier label (never colour alone), keep 48 dp
  targets, omit window insets, and resolve an out-of-range index to "nothing selected".
- **App shell (adopted 2026-10-25).** `AppShell` is the one frame around every destination: a
  `ManijeroTopAppBar` with the brand mark and the visible `Manijero` title and **no right-side
  action**, the selected screen, and `ManijeroBottomNavigation` below 840 dp or
  `ManijeroNavigationRail` from 840 dp. Tabs are `Asistente`, `Mis terrenos` and `Ayuda`; the lands
  tab is omitted when no local repository is injected, so no tab can be dead. Tabs are the only
  top-level navigation: screens must not add another `Volver` or `Mis terrenos` route. The bars are
  hidden on add/edit/remove forms, which keep their own `Cancelar`; privacy stays a detail route with
  its own `Volver`. Android system back returns lands → assistant, a form → lands, `Ayuda` → the tab
  it was opened from, and privacy → the section it was opened from; it is not installed on the
  assistant tab, so the platform default applies. The shell is the **single** owner of the status
  bar, navigation bar, horizontal system-bar and ime insets; the bars and screens add none.
  Privacy remains reachable from the chat footer and the help screen.
- **Evidence.** The review-only `commonTest` gallery is captured at 1200×3000 dp and at 360 dp with
  2× text on both hosts; see `docs/screenshot-regression.md`.

## Layout and interaction

- Give each screen one primary action, with plain labels such as “Añadir terreno” and “Preguntar”.
- Use a clear heading, short explanation, and predictable back/home navigation and action placement.
- Provide large mobile touch targets, comfortable Desktop pointer targets, keyboard operation, and
  visible focus. Essential instructions must not depend on hover.
- Pair unclear icons with text. Use progressive disclosure: ask for a land name first and collect
  only details that help answer a real question.
- Confirm destructive deletion in plain language and identify the land being removed.
- Preserve entered data after validation or recoverable network failures. Show response waiting
  state and a simple retry where appropriate.
- Do not communicate status through color alone.

## MVP surface intent

- **Welcome and home:** explain what the assistant can and cannot do; offer a clear way to ask or
  manage lands. Do not make an empty transcript the only starting point.
- **Chat:** distinguish user and assistant messages; keep citations close to supported claims and
  make sources, verification date, uncertainty, and next steps easy to find.
- **Lands:** provide a simple named list and short add/edit forms. Mark optional details and allow
  unknown values without forcing a guess; avoid map-first or spreadsheet-style layouts.
- **Land clarification:** when an answer materially differs by land, let the user choose one or more
  named lands and continue.
- **Privacy and help:** explain what is stored on device and what may be sent with a question; make
  human-help routes and reviewed-topic coverage easy to find. Detailed coverage content belongs to
  the [`coverage_and_help` spec](docs/specs/coverage_and_help.md).

Feature-specific content and states are defined by the owning feature specs, not this summary.

## Accessibility and validation

Build for text resizing, named controls, understandable screen-reader output, predictable focus and
keyboard access, sufficiently large targets, and non-color status cues. Validate contrast, text
scaling, screen-reader behavior, focus order, and keyboard operation on Android and Desktop. Test
the main journey with people with low digital confidence: add two lands, ask a land-dependent
question, identify its land scope, and find a source without coaching. Do not claim overall
accessibility until the relevant checks have been performed.

Feature-specific evidence and remaining limitations are recorded in the authoritative validation
records: [`chat_accessibility`](docs/validations/chat_accessibility.md) and
[`land_form_accessibility`](docs/validations/land_form_accessibility.md). The low-digital-confidence
manual check remains outstanding; see `PROGRESS.md`.

## Platform consistency

Adapt the shared experience to phone and Desktop rather than forcing a narrow phone layout onto
large screens. Keep product behavior and Compose UI shared for later platform reuse; implementation
boundaries are defined in `ARCHITECTURE.md` and `AGENTS.md`.
