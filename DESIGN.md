# Design Direction — Olive Grove Assistant

## Scope and authority

Use this guide for shared UI design and Spanish user-facing copy. Feature behavior belongs in its
spec; architecture and source-set boundaries belong in `ARCHITECTURE.md`; implementation and
verification status belong in `PROGRESS.md` and `docs/validations/`.

Stitch mockups reference archive is indexed in [`design-references/README.md`](design-references/README.md). The shared app implements the selected paired Stitch-derived light/dark design system. The launcher icon is an identity asset, not a UI reference.

### Reference designs and adoption rules

- Treat screen PNGs and HTML under `design-references/stitch/` as visual inspiration, not production-ready Compose or a source of truth for product behavior.
- The selected baseline palettes and typography are recorded in `stitch/manijero_design_system/DESIGN.md` and `stitch/manijero_design_system_dark_mode/DESIGN.md`. The implemented values below are authoritative; contrast-driven adjustments are noted.
- Stitch PRD/masterplan text is historical design input. Where it proposes behavior outside the current MVP (for example navigation or content not in the accepted contracts), existing product scope and approved feature specs take precedence.
- Screen references map to existing feature contracts rather than creating duplicate feature entries. See the archive index for the mapping and known gaps.

### Shared design system (implemented; owner-approved font gate deferred)

`shared_design_system` defines paired roles in `shared/src/commonMain`, selected automatically with the common Compose system appearance signal. No appearance setting or platform theme fork exists. The constructors explicitly map every applicable Material 3 role and semantic caution colors; source values are in `ManijeroColors.kt`. Common previews cover light, dark, and enlarged text. Shape and spacing scales live in `ManijeroTokens.kt`.

**Font gate — deferred by owner decision:** do not download, add, or bundle font binaries, and do not substitute another bundled family. Preserve the platform default font family exactly as before; existing scalable Material typography roles remain. The Stitch Source Serif 4 / Source Sans 3 direction cannot be adopted until provenance and redistribution terms are approved.

The paired scheme extends the original light-only foundation without changing screen layouts or behavior. Screen-level changes remain with each owning feature. The ten base light tokens in the table below remain the accepted warm olive palette (including their original hex values); derived Material roles and a dark counterpart are added.

## Design intent

Design for people who may use apps only occasionally. Make the interface calm, familiar, practical,
and reassuring. Use everyday Spanish; make the next action obvious and explain agricultural or legal
terms. Never imply that an answer is legally definitive through confident visual treatment.

## Visual foundation

Use a restrained olive and warm-neutral palette. The values below are product-direction tokens, not
a verified brand palette. Keep them centralized; do not use raw color literals in screens. The
shared theme is the sole implementation location for hex colors and maps these tokens to Material 3
roles or semantic colors. Its derived role values and contrast mapping are documented in
[`ManijeroColors.kt`](shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt)
and the [`visual_foundation` spec](docs/specs/visual_foundation.md).

| Light base token | Value | Intent |
|---|---|---|
| `olive-800` | `#354B32` | Primary actions, navigation, selected states |
| `olive-900` | `#263724` | Pressed state and strong emphasis |
| `canvas` | `#F7F6F0` | Warm page background |
| `surface` | `#FFFFFF` | Cards and input surfaces |
| `text-primary` | `#1D221B` | Main text |
| `text-secondary` | `#4B5149` | Secondary text and metadata |
| `border` | `#777D73` | Boundaries and separators |
| `caution` | `#704600` | Warnings, paired with text/icon |
| `caution-surface` | `#FFF2D4` | Caution callout background |
| `danger` | `#A12622` | Errors and destructive actions, paired with text/icon |

The ten tokens above remain implemented verbatim by the shared theme in
`shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`, which is also the only
place in the repository allowed to declare a hex colour. Screens read Material 3 roles or the
`LocalManijeroSemanticColors` values instead of raw hex. The launcher artwork is still the stock
Android Studio template, so no token was changed on that basis.

### Derived tokens

The original light foundation names only the ten tokens above. Material 3 needs a value for every other colour role it
exposes, and leaving a role unset would leak the default purple/teal palette. The following derived
values fill those roles. They stay in the same warm-neutral/olive families (no new hue) and are
documented where they are declared in `ManijeroColors.kt`.

| Derived value | Hex | Use |
|---|---|---|
| `surfaceVariant` / `surfaceContainerHighest` | `#E7E5DD` | Low-emphasis container (the person's own message bubble) |
| `surfaceContainerLow` / `surfaceContainer` / `surfaceContainerHigh` | `#FCFBF6` / `#F2F0E9` / `#EDEBE3` | Warm lift family for cards, menus, and sheets |
| `surfaceContainerLowest` / `surfaceBright` | `#FFFFFF` / `#FFFFFC` | Surface extremes |
| `surfaceDim` | `#DFDDD4` | Recessed surface |
| `outlineVariant` | `#7E8479` | Softer separator/bubble border; 3.05:1 against `surfaceVariant` |
| `primaryContainer` / `onPrimaryContainer` | `#D9E2D2` / `#263724` | Light olive fill for selected/tonal containers |
| `secondaryContainer` / `onSecondaryContainer` | `#DFE4D8` / `#263724` | Second tonal fill in the same family |
| `tertiary` / `onTertiary` | `#40573C` / `#FFFFFF` | Third olive emphasis step (no brown, which would read as caution) |
| `tertiaryContainer` / `onTertiaryContainer` | `#E9EDE2` / `#263724` | Lightest tonal fill |
| `inverseSurface` / `inverseOnSurface` / `inversePrimary` | `#2E332C` / `#F1F2EC` / `#B6C4AC` | Snackbar/reverse surfaces without purple leakage |
| `errorContainer` / `onErrorContainer` | `#F9DEDA` / `#6E1714` | Calm danger container derived from `danger` |

`caution`, `caution-surface`, and `olive-900` (as `primaryStrong`) have no Material 3 role and are
provided through `LocalManijeroSemanticColors`. `danger` is `colorScheme.error` and `border` is
`colorScheme.outline`, so each value keeps a single source.

### Implemented dark palette

Dark values follow the Stitch dark reference; its contrast-failing outline-variant `#424942` is
corrected to `#646B64`. Below is the complete paired Material role mapping, in role order; all values
are explicit in the common theme (the expressive `*Fixed` extension roles are not applicable to this
Material version and are not claimed as mapped).

| Material roles | Light | Dark |
|---|---|---|
| primary / onPrimary | `#354B32` / `#FFFFFF` | `#85A886` / `#0D1B0E` |
| primaryContainer / onPrimaryContainer / inversePrimary | `#D9E2D2` / `#263724` / `#B6C4AC` | `#283C29` / `#CFE8CF` / `#456648` |
| secondary / onSecondary / secondaryContainer / onSecondaryContainer | `#4B5149` / `#FFFFFF` / `#DFE4D8` / `#263724` | `#D4C5A9` / `#382E1C` / `#4F422E` / `#F1E5CC` |
| tertiary / onTertiary / tertiaryContainer / onTertiaryContainer | `#40573C` / `#FFFFFF` / `#E9EDE2` / `#263724` | `#B8C5D6` / `#222D3B` / `#93A0B0` / `#2B3745` |
| background / onBackground; surface / onSurface | `#F7F6F0` / `#1D221B`; `#FFFFFF` / `#1D221B` | `#121612` / `#E1E3DF`; `#121612` / `#E1E3DF` |
| surfaceVariant / onSurfaceVariant / surfaceTint | `#E7E5DD` / `#4B5149` / `#354B32` | `#333532` / `#C2C8BF` / `#ABD0AC` |
| inverseSurface / inverseOnSurface | `#2E332C` / `#F1F2EC` | `#E3E3DE` / `#2F312E` |
| error / onError / errorContainer / onErrorContainer | `#A12622` / `#FFFFFF` / `#F9DEDA` / `#6E1714` | `#FFB4AB` / `#690005` / `#93000A` / `#FFDAD6` |
| outline / outlineVariant / scrim | `#777D73` / `#7E8479` / `#000000` | `#8C948C` / `#646B64` / `#000000` |
| surfaceBright / surfaceDim | `#FFFFFC` / `#DFDDD4` | `#242C24` / `#1A201B` |
| surfaceContainerLowest / Low / Container / High / Highest | `#FFFFFF` / `#FCFBF6` / `#F2F0E9` / `#EDEBE3` / `#E7E5DD` | `#0D100D` / `#181E18` / `#202820` / `#2C362C` / `#384438` |

### Contrast contract

Common tests enumerate the intended readable text pairs (on-colour for primary, secondary,
tertiary, background, surface, surface-variant, tonal containers, inverse surface, error and error
container) at >=4.5:1, and non-text boundaries/icons (error against background, outline against
surface/background/surface-variant, outline-variant against base surface and low container,
primary against surface) at >=3:1. Semantic tests also check caution on light canvas, white surface,
and caution surface, and onCaution on its filled caution color. Representative calculated ratios:
light onSurface/surface 16.19:1; primary/surface 9.53:1; danger/surface 7.46:1; outlineVariant/
surfaceVariant 3.05:1; caution/cautionSurface 7.37:1; caution/canvas 7.56:1; dark onSurface/surface
14.14:1; primary/surface 6.91:1; error/surface 10.76:1; outline/surface 5.86:1; corrected
outlineVariant/surface 3.33:1. Checks test the full listed pair set, not every mathematically possible
combination of roles.

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
