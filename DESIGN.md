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

The coverage disclosure is part of surface 7: it is reachable from chat without a question and
states the pinned reviewed-topic scope, limitations, and named human referral paths. Runtime
inspection covered Android navigation and large text, plus Desktop navigation and narrow/wide
layout. Keyboard focus and spoken screen-reader announcements remain unverified under the
product-owner disposition recorded in the feature appendix and validation record.

## Accessibility and validation

- Validate contrast against WCAG AA as a baseline, text resizing, screen-reader labels, focus order, keyboard access, and non-color status cues.
- Test the main journey with users who have low digital confidence. Ask them to add two lands, ask a land-dependent question, identify which land the answer refers to, and find the source without coaching.
- Avoid claiming the UI is accessible until these checks have been performed on Android and Desktop.

### Chat surface baseline (`chat_accessibility`, 2026-10-13)

The shared chat surface has been inspected on a real Android emulator (`Medium_Phone_API_35`,
system `font_scale` 1.0 and 2.0, `uiautomator` accessibility dumps) and in a Desktop session (the
macOS accessibility tree; the window resized narrow and wide). What is verified:

- **Enlarged text.** At `font_scale 2.0` every chat state — home, a long answered reply with two
  source cards, an abstention, the working notice, a failure notice, and the clarification chooser —
  wraps with no clipping, overlap, or horizontal overflow, and the newest transcript content is
  brought into view while the composer and privacy summary stay below the fold.
- **Names and merged entries.** Each transcript entry is one merged node reading its `Tú`/`Asistente`
  label, scope caption, optional state label, and body; the chooser rows are checkbox toggles
  exposing the saved name plus known details and their checked state; the source-card control carries
  a description naming the document; every control has a text name; the screen title carries an
  `heading()` semantic; and the failure notice's `Reintentar` stays a separate focusable node.
- **Announcements.** A newly appended `answered` reply is now a polite live region, alongside the
  accepted working notice, abstention, and failure notice. The answered announcement is confirmed by
  its semantics wiring and code path, not by a captured TalkBack utterance (TalkBack is bound on the
  emulator, but its spoken output is not logged).
- **Targets and contrast.** Every clickable chat control measures at least 48dp at density 2.625
  (measured from the dump), no minimum-size override exists, and the chat text/control colour pairs
  are covered by the accepted `ManijeroColorsTest` table.
- **Keyboard and focus (Desktop).** Controls are named through the accessibility description and are
  reachable and activatable by keyboard (for example Shift+Tab out of the multi-line composer, then
  Space activates the focused suggestion). Forward Tab is consumed by the multi-line composer as a
  tab character; that is a platform text-field behaviour, not a defect.
- **Wide windows.** The 720dp readable content column is capped and centred (measured at 800pt, a
  1400pt window, and a 420pt narrow window with no overflow).

Recorded remaining gaps (not claimed as passing):

- The Desktop **visual** focus indication could not be inspected, because host screen-capture
  permission was not granted to the verification process; the default Material focus indication was
  therefore relied on and no additional outline was added.
- There is no Compose UI-test harness, so merged semantics, live regions, and focus order are
  verified by the accessibility dumps/previews and code inspection rather than an automated UI test.
- Desktop OS text scaling has no runtime integration, so Desktop large-text evidence stays
  preview-based.
- **Wide-window cap is chat-home-only (recorded finding, pre-existing).** Independently measured at a
  1400x900 Desktop window: the chat home is capped and centred (720pt at x=400), but the `Mis terrenos`
  list, the add/edit/remove land forms, and the privacy notice use `.fillMaxWidth().widthIn(max = 720.dp)`
  with no centring and render full-width (1352pt at x=84) — not capped, not centred. Cause: the chat
  applies the cap before the fill, the land/privacy screens fill first. This is **pre-existing**
  behavior (the `chat_accessibility` cap was scoped to `ChatHomeScreen`), recorded in
  `docs/validations/desktop_mvp_build.md` finding H1; it is **not** verified as capped/centred, and a
  capped/centred land layout, if wanted, is a separate product feature.

### Land add/edit form baseline (`land_form_accessibility`, 2026-10-13)

The two land forms (`AddLandScreen`, `EditLandScreen`) were inspected on the same real Android
emulator and Desktop session, at `font_scale` 1.0 and 2.0 and with a narrow (≈420pt) and wide
(1200pt) Desktop window. What is verified:

- **Unambiguous options.** Both water and production choice groups are a `selectableGroup`, and every
  option row carries an accessible name built from the visible group label (`Riego: No lo sé`,
  `Producción: No lo sé`, `Riego: Regadío`, `Producción: Ecológico`, …). The Android dump exposes all
  eight `content-desc`s at 1.0 and 2.0 with the row reporting its role and selected state, and the
  Desktop AX tree exposes each row as an `AXRadioButton` with that group-qualified name and a `0`/`1`
  selected value — so the two `No lo sé` options can no longer be confused.
- **Recoverable validation.** A blank-name save writes nothing, keeps every entered value and
  selection, shows the unchanged plain-Spanish message, and moves input focus back to the name field.
  On Android the name field reports `focused="true"` after the save and a second blank attempt
  re-focuses it; on Desktop, typing immediately after the save lands in the name field and the field's
  accessible description includes the message. The visible error `Text` is a polite live region and
  the field carries Compose `error()` semantics. Correcting the name clears the error and writes
  exactly one record.
- **Heading and names.** Each form title carries a `heading()` semantic; every field, option and action
  keeps a plain-Spanish name. No visible copy or layout changed.
- **Enlarged text and targets.** At `font_scale 2.0`, at the `widthDp = 320 / fontScale = 2f` preview
  and in a 420pt Desktop window the forms wrap with no clipping, overlap or horizontal overflow and
  stay vertically scrollable; every Android clickable node is ≥48dp with no minimum-size override.
  The name-error state is never colour-only — the message text is always present (confirmed in a
  greyscale render of the Android error screen).

Recorded remaining gaps (not claimed as passing):

- The Desktop **visual** focus indication still could not be inspected (host screen capture and the
  AX per-element focus attribute are unavailable in this environment); the default Material indication
  was relied on and no outline was added.
- Android `uiautomator` exposes neither merged nodes nor headings, so the group association and the
  form-title heading rest on the Compose semantics plus the exposed `content-desc`/AX nodes; the AX
  tree likewise shows the title as a plain static text, with no separate heading role.
- Focus moving to the name field opens the Android IME (expected and helpful for correcting, recorded
  so it is not later mistaken for a defect); no autofocus happens on form entry.
- No Compose UI-test harness exists, so the semantics, focus and announcement are verified by the
  dumps, the AX tree and code inspection rather than an automated UI test.
- The low-digital-confidence human validation (feature-list note) is a manual session and was **not**
  run here; it stays an outstanding check.

## Platform consistency

Implement the Compose UI and product behavior in shared `commonMain`. Adapt navigation, window sizing, keyboard behavior, and input affordances to phone and desktop instead of forcing a narrow phone layout onto large screens. Keep only platform integrations and entry points in platform-specific source sets so the later iOS target can reuse the same UI and business logic.
