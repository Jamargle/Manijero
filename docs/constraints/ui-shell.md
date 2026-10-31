# Constraints: UI components and app shell

Durable MUST/MUST NOT rules for brand vectors, the shared component layer, and app navigation. Part of the index in [`CONSTRAINTS.md`](../../CONSTRAINTS.md); paths in backticks are relative to the repository root.

## Brand vectors

- **MUST**: shipped brand vectors (the mark, sixteen `ic_*` glyphs, the olive-branch illustration)
  stay single-colour Android-XML masks under
  `shared/src/commonMain/composeResources/drawable/` with only `#000000` / `#00000000` literals — no
  `android:tint`, gradient, `aapt:attr`, clip path, or `@android:` — and take every rendered colour
  from the theme. A new glyph follows the 24 dp outline grid (2 dp round stroke, no fill, 2–22 dp safe
  area) and ships with its board entry and the owning spec's gates. Reason: `brand_vectors`; a baked
  colour or a second dark-mode asset would break the palette and the contrast pairs
  `design_token_refresh` guarantees.
- **MUST**: the mark and illustration stay decorative — no `contentDescription` or colour parameter,
  no semantics node, halo painted in Compose — and MUST NOT read as a check, seal, badge, or
  "verified"/"official" cue, or qualify an answer, source, or land. Reason: `brand_vectors`; a status
  reading would reintroduce the legal-certainty failure `response_states` forbids.
- **MUST NOT**: add an icon font (`material-icons-*`), raster/binary icon asset, or generated image
  for these glyphs. Reason: repository-owned vectors keep the tint policy and the pinned inventory.

## Shared component layer

- **MUST**: everything under `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` stays
  presentational: every visible string, value, icon, selection and callback is a parameter, and the
  package MUST NOT read `Res.string`, import a `lands`/`chat`/`privacy`/`coverage`/`platform` type,
  read a store, send a request, log, or own filtering, validation, parsing, formatting, totals or
  selection persistence. Reason: `ui_component_library` established the layer so later screens share
  one vocabulary; a component that owns copy or a business rule would duplicate the screen's
  authority and make a Spanish-copy or domain review miss the real source.
- **MUST**: every colour, shape and spacing value comes from `MaterialTheme.colorScheme`,
  `LocalManijeroSemanticColors`, `LocalContentColor`, `ManijeroShapes`, `ManijeroSpacing` or
  `ManijeroLayout` — never a hex/`Color(0x…)` literal or a new token — and no state is colour-only
  (callouts keep an icon plus text, chips keep a label, selection keeps the indicator plus label
  weight). Reason: `design_token_refresh` and `brand_vectors` gate contrast from those sources; a
  literal or a colour-only cue would bypass the gates and the non-colour status rule.
- **MUST**: every interactive control in the layer keeps a text or caller-supplied accessible name,
  a 48 dp minimum target, and Material's focus indication and minimum interactive size; the search
  clear action and the top-bar privacy action are never rendered unnamed (an action with no name is
  omitted), navigation labels stay visible on both bars, and the bars MUST NOT own window insets.
  Reason: `ui_component_library` set the accessibility baseline and `app_chrome_navigation` owns
  insets; a later screen can silently drop a name, a target, or the single-inset-owner rule without
  any test failing.

## App shell and navigation

- **MUST**: `AppShell` stays the single owner of the status bar, navigation bar, horizontal
  system-bar and ime window insets; the top app bar, navigation bar, rail and every hosted screen
  MUST NOT add their own window-inset padding. Reason: `app_chrome_navigation` made the shell the one
  frame, and a second inset owner double-pads or draws under a system bar.
- **MUST**: the shell tabs (`Mis terrenos`, `Asistente`, `Ayuda`, in that left-to-right order) are
  the only top-level navigation; a screen MUST NOT re-add a top-level `Volver` or `Mis terrenos`
  affordance. The lands tab MUST be omitted when no local `LandRepository` is injected, and a
  selected index MUST never point at an omitted destination. Reason: `app_chrome_navigation` removed
  the duplicate routes; re-adding one would give two authorities for the same move and could expose
  a dead destination.
- **MUST**: add/edit/remove land forms hide the navigation bars and keep their own `Cancelar`;
  privacy stays a detail route with its own `Volver`. Android system back MUST follow
  `AppNavigation.backTarget` (lands → assistant, form → lands, help → the tab it was entered from,
  privacy → the section it was opened from) and MUST be absent when that target is null. Reason:
  `app_chrome_navigation` protects an unsaved draft and keeps the selected tab consistent with the
  visible screen.
