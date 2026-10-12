# Design Direction — Olive Grove Assistant

## Status and source of truth

No product UI design system or authoritative mockups were found. The existing launcher icon is an identity asset, not a layout or component specification. This document sets an initial direction for MVP implementation. No generated UI concepts were requested or used.

## Design intent

Design for a person who may use apps only occasionally and wants reassurance that they are in the right place. The interface should feel calm, familiar, and practical, with Spanish copy that sounds like everyday conversation. Each screen should make the next action obvious and keep agricultural/legal terms explainable.

## Visual foundation

Use the existing olive-grove identity as a restrained cue. These initial tokens are product direction, not a verified brand palette; adjust them if comparison with the launcher artwork shows a meaningful mismatch. Keep tokens centralized and shared.

| Token | Initial value | Use |
|---|---|---|
| `olive-800` | `#354B32` | Primary actions, navigation, selected states |
| `olive-900` | `#263724` | Pressed state and strong emphasis |
| `canvas` | `#F7F6F0` | Warm page background |
| `surface` | `#FFFFFF` | Cards and input surfaces |
| `text-primary` | `#1D221B` | Main text |
| `text-secondary` | `#4B5149` | Secondary text and metadata |
| `border` | `#777D73` | Form boundaries and separators |
| `caution` | `#704600` | Warnings and “check this” states, paired with text/icon |
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

### Light-only decision

The shared theme is light-only for the MVP: no dark tokens exist, and only this one warm palette is
verified. The theme deliberately does not call `isSystemInDarkTheme()`, so a person whose system is in
dark mode still sees the warm light theme instead of an unverified dark palette. A dark palette is a
follow-up feature, not part of `visual_foundation`.

Typography uses the platform system sans-serif, generous line height, and a base body size comfortable at phone distance. Support platform text scaling without clipping. Use simple rounded cards and buttons; avoid decorative gradients, dense dashboards, and tiny icon-only controls. Verify final text/background and control contrasts against WCAG AA during implementation.

## Layout and interaction principles

- One primary action per screen; use plain labels such as “Añadir terreno” and “Preguntar”.
- Show a clear heading, short explanation, and visible back/home navigation. Keep important actions in predictable locations.
- Use large touch targets on mobile and comfortable pointer targets on Desktop. Keyboard navigation and visible focus are required on Desktop.
- Pair icons with text when the meaning may not be obvious. Do not rely on hover to reveal essential instructions.
- Prefer progressive disclosure: ask for a land name first, then collect only details that help answer a real question.
- Confirm destructive deletion in plain language and identify which land will be removed.
- Preserve user-entered data when validation or network requests fail.
- Show a clear waiting state for AI responses and allow a simple retry after recoverable failures.
- Never use a confident visual treatment to imply that an answer is legally definitive.

## MVP surfaces

1. **Welcome / first use:** explain simply what the assistant can and cannot do; invite the user to add a land or ask a general question.
2. **Home / ask:** one prominent question field, a small set of example questions, and an easy route to “Mis terrenos”. Avoid an empty chat transcript as the only starting point.
3. **Chat answer:** distinguish the user's message from the answer; place citations beside relevant claims; provide a readable source card and the verification date. For uncertain answers, state the limitation and next step visibly.
4. **My lands:** simple list with user-chosen names and a visible “Añadir terreno” action. Avoid map-first or spreadsheet-style layouts.
5. **Add/edit land:** short, plain-language form. Clearly mark optional details and allow unknown values without forcing a guess.
6. **Choose land clarification:** list named lands with simple attributes when an answer differs by land; let the user select one or more and continue.
7. **Privacy/help:** explain what land information is saved on device and what information may be sent with a question. Link to human help for questions the app cannot answer.

## Accessibility and validation

- Validate contrast against WCAG AA as a baseline, text resizing, screen-reader labels, focus order, keyboard access, and non-color status cues.
- Test the main journey with users who have low digital confidence. Ask them to add two lands, ask a land-dependent question, identify which land the answer refers to, and find the source without coaching.
- Avoid claiming the UI is accessible until these checks have been performed on Android and Desktop.

## Platform consistency

Implement the Compose UI and product behavior in shared `commonMain`. Adapt navigation, window sizing, keyboard behavior, and input affordances to phone and desktop instead of forcing a narrow phone layout onto large screens. Keep only platform integrations and entry points in platform-specific source sets so the later iOS target can reuse the same UI and business logic.
