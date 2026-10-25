# Feature Spec: `design_token_refresh`

> **Supersedes the palette of `shared_design_system` (2026-10-25).** This feature applies the approved
> Stitch token palette verbatim, plus the two documented `outlineVariant` accessibility corrections, to
> the already-accepted shared theme. Role mapping, system-appearance selection, shape semantics,
> default typography, and the verification requirements stay as accepted there; only the colour
> values, the token-scale additions, and the gates that describe them change.

## Source metadata

- **Feature:** `design_token_refresh` — Refresh the shared palette and design tokens (`client`).
- **Status at planning:** `not_started`; depends on accepted `shared_design_system`. The plan's §9
  lists no dependency; the accepted theme owns the files this feature edits, so the prerequisite is
  declared explicitly instead of left implicit.
- **Source behavior:** The shared app renders the approved Stitch palette in light and dark, with every
  documented Material role, semantic colour, and land-attribute chip pair contrast-gated as documented.
- **Feature verification:** Run the focused shared theme tests and confirm no raw palette literal exists
  outside `ManijeroColors.kt`; inspect the token board previews in light, dark, and 2× text.
- **Plan steps:** P0-01…P0-06 of [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md).
- **Approval:** palette and deviations approved 2026-10-25; values recorded in
  [`DESIGN.md`](../../DESIGN.md) and plan §3.1.

## Goal and boundaries

Replace the earlier warm-olive light palette and the partially updated dark palette with the approved
Stitch token block in both appearances, extend the shared token scale that later components will use,
and re-gate the documented contrast contract so a wrong value fails the build instead of surfacing in a
screen. No screen is restyled, no component is built, and no behaviour changes.

**In scope**

- Light and dark Material 3 role values from the Stitch token blocks, with `outlineVariant` corrected
  in both modes (`#757C71` light, `#868E86` dark) and `scrim` kept at `#000000`.
- The Manijero-only semantic colours that Stitch does not define (`caution`, `cautionSurface`,
  `onCaution`, `primaryStrong`) plus the Ecológico chip pair, which Stitch exposes only as
  `primaryFixed`/`onPrimaryFixed` and this Material version does not map to a role.
- Token-scale additions in `ManijeroTokens.kt`: the 4/8/16 internal rhythm steps, icon sizes, content
  width, screen padding, border width, and minimum touch target.
- Rewritten contrast and design-system gates for both appearances, covering text pairs, non-text
  boundaries, caution pairs, error pairs, tonal/inverse pairs, and the four chip pairs.
- A token board that derives its swatches and hex labels from the theme instead of typed strings, with
  light, dark, and enlarged-text previews.
- Re-pointing the five existing card/tonal `colorScheme.surface` call sites to the documented raised
  surface role, so the palette change does not visually flatten cards between features.
- Documentation updates that keep `DESIGN.md` and the accepted theme's notes aligned with the shipped
  values.

**Non-goals**

- No component library, `design/` package, screen layout, spacing, shape, copy, navigation, or state
  change; no brand/icon/illustration vectors; those are later features in plan §9.
- No typography change: Material 3 default typography, no font asset, no custom scale.
- No new Gradle module, dependency, dynamic colour, manual appearance preference, or platform theme fork.
- No data, store, `/ask`, backend, contract, or privacy-copy change.
- No launcher icon change.
- No claim that a palette change proves accessibility: focus order, screen-reader output, and
  enlarged-text layout of real screens remain owned by later features and the accessibility audit.

## Job story

When I open Manijero on a phone or computer, I want the approved olive, brown, and plum/blue palette in
both light and dark appearance, with readable text and clearly visible boundaries everywhere, so the app
feels calm and legible without me adjusting anything.

## Acceptance scenarios

### Light appearance matches the approved light palette

Given the system requests light appearance, when any shared screen or preview reads a Material 3 colour
role, then that role is the Stitch light value recorded in `DESIGN.md`, including `surface` `#F9FAF4`,
`surfaceContainerLowest` `#FFFFFF`, `primary` `#214624`, `secondary` `#7E562E`, `tertiary` `#602E40`,
`error` `#BA1A1A`, and the corrected `outlineVariant` `#757C71`.

### Dark appearance matches the approved dark palette

Given the system requests dark appearance, when a role is read, then that role is the Stitch dark value
recorded in `DESIGN.md`, including `primary` `#85A886`, `secondary` `#D4C5A9`, `tertiary` `#B8C5D6`,
`error` `#FFB4AB`, and the corrected `outlineVariant` `#868E86`. No role keeps the previous adjusted
value `#646B64` or any earlier derived role.

### No role is left to a Material default

Given either appearance, when every brand-bearing role is compared with the Material default scheme,
then no brand-bearing role equals the Material default. The documented exclusions are the four white
on-colours, light `surfaceContainerLowest` white, and `scrim` black, which have no hue to leak.

### Semantic colours and chips are explicit

Given either appearance, when a screen needs caution, emphasis, or a land-attribute chip, then it reads
a documented value: `caution`, `cautionSurface`, `onCaution`, `primaryStrong`, and the Ecológico pair
from `LocalManijeroSemanticColors`; Secano, Regadío, and Neutral from their documented role pairs. No
`earth`, `earthContainer`, `sun`, or `sunContainer` token exists.

### Documented contrast is enforced, not described

Given the values above, when common tests measure WCAG 2.x contrast, then every pair listed in the
`DESIGN.md` contrast contract is asserted at its documented ratio, text pairs clear 4.5:1, non-text
boundaries clear 3:1, and every chip pair clears 4.5:1 in both appearances. A failing pair blocks the
build; a documented ratio that proves wrong is corrected in `DESIGN.md` in the same change, never
deleted from the test.

### The palette has exactly one home

Given the shared source set, when the focused check scans `commonMain`, then no file other than
`theme/ManijeroColors.kt` declares a raw colour literal, and screens keep reading Material roles or
semantic tokens.

### Shared tokens are available to later components

Given the token files, when a later component needs internal rhythm, an icon size, the content width, a
screen inset, a border width, or a minimum touch target, then a named token supplies it, and the values
match `DESIGN.md`/plan §3.3.

### Existing behaviour is unchanged

Given the refreshed theme, when the existing chat, lands, help, and privacy flows run, then copy,
layout structure, state transitions, persistence, requests, semantics, and navigation are unchanged.
Cards remain visually raised: the five existing card surfaces read `surfaceContainerLowest` instead of
the canvas-valued `surface` role.

### Review board is trustworthy

Given the token board preview, when it is rendered in light, dark, and 2× text, then every documented
token, semantic colour, and chip pair is visible with its value, the hex text is computed from the
colour rather than typed, and each swatch keeps readable text in both appearances.

## Token contract

`DESIGN.md` is the authoritative table; the values below are the decisions this feature must encode.

### Core tokens

| Token | Light | Dark | Material role |
|---|---|---|---|
| `primary` | `#214624` | `#85A886` | `primary` |
| `primaryStrong` | `#263724` | `#CFE8CF` | no role; semantic emphasis |
| `canvas` | `#F9FAF4` | `#121612` | `background` |
| `surface` (card/input) | `#FFFFFF` | `#0D100D` | `surfaceContainerLowest` |
| `text-primary` | `#1A1C19` | `#E1E3DF` | `onSurface` / `onBackground` |
| `text-secondary` | `#424940` | `#C2C8BF` | `onSurfaceVariant` |
| `border` | `#72796F` | `#8C948C` | `outline` |
| `outlineVariant` | `#757C71` | `#868E86` | `outlineVariant` (corrected) |
| `caution` | `#704600` | `#FFD18A` | no role; semantic |
| `caution-surface` | `#FFF2D4` | `#4B350D` | no role; semantic |
| `danger` | `#BA1A1A` | `#FFB4AB` | `error` |

Every other role takes the Stitch value in the `DESIGN.md` role map verbatim; the two deviations are
`outlineVariant` (`#757C71` / `#868E86`) and no other.

### Semantic additions

`ManijeroSemanticColors` keeps `caution`, `onCaution`, `cautionSurface`, `primaryStrong` and adds one
pair: `ecoContainer` / `onEcoContainer` — light `#C2EEBE` / `#002106`, dark `#C7ECC6` / `#02210A`,
documented as the Ecológico chip pair (Stitch `primaryFixed`/`onPrimaryFixed`). Chips always carry
text; colour is never the only cue. No generic chip type is introduced here.

### Token scale (`theme/ManijeroTokens.kt`)

| Group | Tokens |
|---|---|
| `ManijeroShapes` | unchanged: `Small` 4, `Medium` 12, `Large` 16, `ExtraLarge` 24, `Material` |
| `ManijeroSpacing` | unchanged `ExtraSmall` 6, `Small` 12, `Medium` 24, `Large` 32, `ExtraLarge` 48; new 4 dp-grid steps `Micro` 4, `Compact` 8, `Comfortable` 16 |
| `ManijeroIconSize` | `Inline` 20, `Default` 24, `Large` 32 |
| `ManijeroLayout` | `ContentMaxWidth` 720, `ScreenPaddingHorizontal` 24, `ScreenPaddingHorizontalWide` 40, `ScreenPaddingVertical` 32, `BorderWidth` 1, `MinTouchTarget` 48 |

Existing private `720.dp`/padding constants in screens stay untouched (their screen features adopt the
tokens); this feature only adds and gates the values.

## Technical approach

- Keep all colour values in `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`:
  named light token values plus named light role values (the light scheme keeps referencing names, as
  today), the dark scheme with its documented values, the semantic data class, and the WCAG helpers.
- Keep the scheme constructors explicit for every applicable role; do not reintroduce "derived" values,
  and do not add the `*Fixed` roles this Material version does not expose.
- Keep `ManijeroTheme` as the single theme application and the only place previews get a palette; the
  board must read roles/semantics rather than duplicated constants.
- Keep screens behaviour-identical: the only permitted screen edits are the five
  `colorScheme.surface` card call sites (`App.kt` assistant card, source card, notice bubble,
  clarification chooser; `lands/LandListScreen.kt` land row) moving to `surfaceContainerLowest`.
- Test structure follows the existing file: token assertions, role assertions, no-default-leak
  comparison, documented-ratio contrast tables per appearance, semantic assertions, WCAG helper
  anchors. No composition, no I/O, no resources in `ManijeroColorsTest`.

## Expected file changes

- **Modify** `theme/ManijeroColors.kt` — light and dark role values, corrected `outlineVariant`,
  semantic Ecológico pair, KDoc and ratio notes.
- **Modify** `theme/ManijeroTokens.kt` — 4 dp rhythm steps, icon sizes, layout tokens.
- **Modify** `theme/ManijeroTheme.kt` — computed-hex token board covering roles, semantics, and chips,
  with light/dark/large-text previews.
- **Modify** `commonTest/theme/ManijeroColorsTest.kt` — rewritten for both appearances.
- **Modify** `commonTest/theme/ManijeroDesignSystemTest.kt` — updated role table, contrast pairs, and
  semantic assertions.
- **Modify** `App.kt`, `lands/LandListScreen.kt` — the five surface call sites only.
- **Update** `DESIGN.md` — remove the "palette status" superseded note, record the Ecológico pair as
  semantic tokens, and correct any documented ratio the tests disprove.
- **Not changed:** any other screen, `ARCHITECTURE.md`, `CONSTRAINTS.md`, `AGENTS.md`,
  `docs/domain-model.md`, `contracts/`, `backend/`, `knowledge/`, Gradle files, `feature_list.json`
  (status changes only after acceptance), `design-references/stitch/` (provenance stays byte-identical).

## Focused verification

The feature command must run tests and repository checks; it must not launch a long-running service.
Run it from the repository root (`REPO_ROOT` is exported by `scripts/init.sh`). The two palette greps
prove the refresh actually happened: before implementation the old tests still pass and would
otherwise hide a no-op (`0xFF214624` is light `primary`, `0xFF868E86` the corrected dark
`outlineVariant`). The raw-literal scan rejects `Color(0x…)`, `Color.White`, and `Color.Black` outside
`theme/ManijeroColors.kt`.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ManijeroColorsTest --tests ManijeroDesignSystemTest
palette="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt"
grep -q '0xFF214624' "$palette" || { echo "palette not refreshed: light primary #214624 missing" >&2; exit 1; }
grep -q '0xFF868E86' "$palette" || { echo "palette not refreshed: dark outlineVariant #868E86 missing" >&2; exit 1; }
hex_outside_theme="$(grep -rlE 'Color\(0x|Color\.(White|Black)' "$REPO_ROOT/shared/src/commonMain" | grep -v 'theme/ManijeroColors.kt' || true)"
test -z "$hex_outside_theme" || { echo "raw colour literal outside ManijeroColors.kt:" >&2; echo "$hex_outside_theme" >&2; exit 1; }
```
<!-- verify:end -->

Manual evidence this command cannot produce: inspection of the token board in light, dark, and 2× text
(font scale), and confirmation that a chat answer card and a land row still read as raised surfaces. No
automated UI/screenshot harness exists in this repository, so these observations are recorded as manual
review, not as reproducible artifacts.

## Risks and decisions

- **Raised cards.** Stitch light deliberately sets `background == surface`; keeping `surface` as the
  card background would put cards on the canvas colour. Decision: the five existing card call sites read
  `surfaceContainerLowest`; the later component feature owns the full card styling.
- **`outlineVariant` separation.** The corrected values sit close to `outline`
  (`#757C71` vs `#72796F`; `#868E86` vs `#8C948C`). The reduced separation is the documented cost of
  clearing 3:1 on every surface; tests keep both tokens distinct and gated.
- **Ecológico chip exposure.** Deferring the pair would leave a documented chip colour with no token and
  no test. Decision: two semantic fields now, no chip component.
- **Documented ratios.** The test asserts the `DESIGN.md` numbers exactly. If recomputation disagrees,
  the implementer fixes the document and the test together and records why; silently loosening the gate
  is a spec violation.
- **Intermediate visual state.** Screens keep their current layout and copy, so the app looks flatter
  and less final than the Stitch mockups until the component and screen features land. That is the
  planned sequence, not a regression to hide.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Drop the superseded-palette status note, record the Ecológico semantic pair, and keep every documented ratio equal to the test. |
| `ARCHITECTURE.md`, `CONSTRAINTS.md`, `AGENTS.md` | Not needed | Same theme package and boundary; the existing contrast, shared-source, and no-raw-colour rules already cover this change. |
| `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md` | Not needed | Presentation-only change. |
| `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md` | Update after implementation and independent acceptance | Keep status and evidence honest; planning must not mark the feature passing or accepted. |

## Appendix

See [`docs/specs/design_token_refresh.appendix.md`](design_token_refresh.appendix.md) for the repository
audit, ordered implementation tasks, verification detail, evidence to capture, and validator checklist.
