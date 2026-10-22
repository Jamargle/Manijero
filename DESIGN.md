# Design Direction — Olive Grove Assistant

## Scope and authority

Use this guide for shared UI design and Spanish user-facing copy. Feature behavior belongs in its
spec; architecture and source-set boundaries belong in `ARCHITECTURE.md`; implementation and
verification status belong in `PROGRESS.md` and `docs/validations/`. For routine feature work, read
this file only when the feature changes user-facing UI or copy.

No authoritative mockups or verified brand palette exist. This is the initial MVP direction, not a
pixel specification. The launcher icon is an identity asset, not a UI reference.

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

| Token | Initial value | Intent |
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

The ten tokens above are shipped verbatim by the shared theme in
`shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`, which is also the only
place in the repository allowed to declare a hex colour. Screens read Material 3 roles or the
`LocalManijeroSemanticColors` values instead of raw hex. The launcher artwork is still the stock
Android Studio template, so no token was changed on that basis.

### Derived tokens

`DESIGN.md` names only the ten tokens above. Material 3 needs a value for every other colour role it
exposes, and leaving a role unset would leak the default purple/teal palette. The following derived
values fill those roles. They stay in the same warm-neutral/olive families (no new hue) and are
documented where they are declared in `ManijeroColors.kt`.

| Derived value | Hex | Use |
|---|---|---|
| `surfaceVariant` / `surfaceContainerHighest` | `#E7E5DD` | Low-emphasis container (the person's own message bubble) |
| `surfaceContainerLow` / `surfaceContainer` / `surfaceContainerHigh` | `#FCFBF6` / `#F2F0E9` / `#EDEBE3` | Warm lift family for cards, menus, and sheets |
| `surfaceContainerLowest` / `surfaceBright` | `#FFFFFF` / `#FFFFFC` | Surface extremes |
| `surfaceDim` | `#DFDDD4` | Recessed surface |
| `outlineVariant` | `#7E8479` | Softer separator/bubble border; still clears 3:1 against canvas, surface, and `surfaceVariant` |
| `primaryContainer` / `onPrimaryContainer` | `#D9E2D2` / `#263724` | Light olive fill for selected/tonal containers |
| `secondaryContainer` / `onSecondaryContainer` | `#DFE4D8` / `#263724` | Second tonal fill in the same family |
| `tertiary` / `onTertiary` | `#40573C` / `#FFFFFF` | Third olive emphasis step (no brown, which would read as caution) |
| `tertiaryContainer` / `onTertiaryContainer` | `#E9EDE2` / `#263724` | Lightest tonal fill |
| `inverseSurface` / `inverseOnSurface` / `inversePrimary` | `#2E332C` / `#F1F2EC` / `#B6C4AC` | Snackbar/reverse surfaces without purple leakage |
| `errorContainer` / `onErrorContainer` | `#F9DEDA` / `#6E1714` | Calm danger container derived from `danger` |

`caution`, `caution-surface`, and `olive-900` (as `primaryStrong`) have no Material 3 role and are
provided through `LocalManijeroSemanticColors`. `danger` is `colorScheme.error` and `border` is
`colorScheme.outline`, so each value keeps a single source.

The MVP uses the verified warm light palette, including when the device is in dark mode. Dark-theme
support is not specified; do not imply that a dark palette has been verified.

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
