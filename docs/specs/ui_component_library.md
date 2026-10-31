# Feature Spec: `ui_component_library`

## Source metadata

- **Feature:** `ui_component_library` — build the shared visual component library (`client`).
- **Status at planning:** `not_started`; depends on accepted `brand_vectors` (accepted) and is the
  next dependency-ready feature.
- **Source behavior:** add the presentational component layer the screen refreshes will use: layout,
  cards, callouts, chips, form controls and navigation bars, all built from the existing theme,
  brand glyphs and spacing tokens. No screen adopts them yet.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md) §3.3, §3.4, §4.2,
  §5 and §6, steps P0-11…P0-16; `DESIGN.md` "Shared design system", "Brand vectors and iconography",
  "Layout and interaction".
- **Acceptance record:** [`docs/validations/ui_component_library.md`](../validations/ui_component_library.md)
  (created at acceptance); planning and verification detail is in the
  [appendix](../archive/specs/ui_component_library.appendix.md).

## Goal and boundaries

Give the UI refresh one small, tested, theme-driven component layer so every later screen is built
from the same surfaces, controls and navigation bars instead of re-inventing them. The layer is
presentational: it renders the strings, colours, values and callbacks its caller supplies.

**In scope**

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/`: fourteen components
  (`ManijeroScreen`, `ManijeroCard`, `ManijeroSectionHeader`, `ManijeroCallout`,
  `ManijeroStatCard`, `ManijeroEmptyState`, `ManijeroAttributeChip`, `ManijeroChoiceCard`,
  `ManijeroSearchField`, `ManijeroDropdownField`, `ManijeroMeasureField`, and the navigation
  components `ManijeroTopAppBar`, `ManijeroBottomNavigation`, `ManijeroNavigationRail`).
- Light, dark and 2× text previews per component.
- A review-only `commonTest` gallery plus four Desktop and four Android host screenshot goldens.
- Durable rules in `DESIGN.md`, `CONSTRAINTS.md` and `docs/screenshot-regression.md`.

**Non-goals**

- No screen, shell, navigation behaviour, route, back-handling or tab-state change; every existing
  screen and its ten Desktop / six Android goldens stay unchanged.
- No new shipped string in `strings.xml`; the gallery's labels are review identifiers only.
- No new vector, icon, font, image, token, module, Gradle dependency or `material-icons-*` entry.
- No land, chat, privacy or coverage domain type, state, repository or network import in the layer.
- No business rule inside a component (filtering, validation, number parsing, formatting, selection
  persistence, logging).
- No accessibility, usability, device, iOS or screenshot-baseline claim beyond the host renders.

## Job story

When the assistant, lands, help and privacy screens are refreshed one by one, I want them to look and
behave like one app — the same cards, warnings, chips, fields and navigation — and to stay readable in
light and dark and at large text, so the app feels calm and familiar instead of assembled from
mismatched pieces.

## Acceptance scenarios

1. **One component set, no screens changed.** The listed components exist in
   `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/`, are `internal`, and no screen
   (`App.kt`, `lands/`, `privacy/`, `coverage/`) imports them. Existing app screens and goldens are
   unchanged.
2. **Presentational only.** A component takes everything it renders as parameters (text, values, icons,
   selection, callbacks). The package imports no `lands`, `chat`, `privacy`, `coverage` or `platform`
   type, contains no `Res.string` accessor, reads no store, sends no request and logs nothing.
3. **Theme-only styling.** The layer contains no hex or `Color(0x…)` literal and no new colour. Every
   colour is a theme role (`MaterialTheme.colorScheme`), a `LocalManijeroSemanticColors` value, or
   `LocalContentColor`; every shape and spacing value comes from `ManijeroShapes`,
   `ManijeroSpacing` or `ManijeroLayout`.
4. **Screen wrapper.** `ManijeroScreen` paints the `background` role, gives the content one vertical
   scroll, applies 24 dp horizontal padding below 840 dp and 40 dp from 840 dp, 32 dp vertical
   padding, and centres a 720 dp maximum content column. It does not own window insets.
5. **Cards and sections.** `ManijeroCard` renders four tones (`Surface`, `Tonal`, `Outlined`,
   `Danger`) with the 16 dp large radius and 1 dp `outlineVariant` / `error` border where the tone
   defines one; it is not clickable unless the caller adds an interactive child. `ManijeroSectionHeader`
   renders a title plus optional explanation and adds the `heading()` semantic only when the caller
   explicitly says the title is a real heading.
6. **Callouts never use colour alone.** `ManijeroCallout` has `Info`, `Caution`, `Danger` and
   `Confirmation` tones, always shows an icon and the supplied text, uses the accepted token pairs
   (`cautionSurface`/`caution`, `errorContainer`/`error`, `primaryContainer`/`onPrimaryContainer`,
   `surfaceContainerLow`/`onSurface`), marks only its text node as a polite live region, and keeps an
   optional action slot as its own focusable node.
7. **Stat cards stay honest.** `ManijeroStatCard` requires a `supporting` caption that states what the
   value counts or how many records contributed; the component never formats, totals or invents a
   value, and never renders a bare "total".
8. **Empty state.** `ManijeroEmptyState` renders the decorative `ManijeroOliveBranch` (no description,
   no semantics node), a real heading, a plain explanation and exactly one action slot.
9. **Chips always carry text.** `ManijeroAttributeChip` has `Dryland`, `Irrigated`, `Organic` and
   `Neutral` tones using the accepted chip pairs (`secondaryContainer`, `primaryContainer`, semantic
   `ecoContainer`, `surfaceContainerHighest`), is non-interactive, and is never the only cue for a
   status.
10. **Choice cards are real radio options.** `ManijeroChoiceCard` renders a selection card at least
    48 dp high with a `RadioButton`, the `Role.RadioButton` role and `selected` state from
    `Modifier.selectable`, an optional merged option description (for example "Riego: No lo sé"),
    and an error border when `isError` is true. Grouping (`Modifier.selectableGroup()`) stays the
    caller's responsibility; the component never hides an option.
11. **Search field filters nothing.** `ManijeroSearchField` renders a labelled single-line field with
    a decorative leading search glyph and, when the value is non-blank, a clear `IconButton` with the
    caller's description and a 48 dp target. It reports every keystroke and performs no filtering.
12. **Dropdown and measure fields stay dumb.** `ManijeroDropdownField` lists the caller's options,
    shows the selected value or placeholder, exposes an error state and supporting text, and reports
    the chosen option. `ManijeroMeasureField` accepts a text value, an optional helper, an optional
    error and a keyboard type, marks the error state from `errorText`, preserves the value, and performs
    no parsing, rounding or inference.
13. **Top app bar.** `ManijeroTopAppBar` shows the 32 dp `ManijeroBrandMark` (identity, no status
    meaning) and the title, on a flat `surfaceContainerLowest` surface with a 1 dp `outlineVariant`
    bottom divider and no shadow. The optional privacy action uses `ic_info` and is a `TextButton` with
    icon plus visible label from 840 dp and an `IconButton` with the caller's accessible description
    below it; both meet the 48 dp target and the action is omitted when its callback is null.
14. **Navigation bars.** `ManijeroBottomNavigation` and `ManijeroNavigationRail` render the caller's
    destinations (label + icon) with labels always visible, the selected item marked by indicator and
    emphasised label (never colour alone), 48 dp targets, and no window insets. An out-of-range or
    negative selected index selects nothing and does not throw.
15. **Review-only gallery and goldens.** A `commonTest` `ComponentGallery()` composable renders every
    component and tone. The Desktop and Android host suites add exactly four goldens each:
    `component_gallery_light`, `component_gallery_dark` at 1200×3000 dp with font scale 1, and
    `component_gallery_narrow_large_text_light`, `component_gallery_narrow_large_text_dark` at
    360 dp wide with font scale 2 (tall enough that no section is clipped). All ten existing Desktop
    and six existing Android goldens stay unchanged.
16. **Accessibility baseline.** Every interactive control has a text or caller-supplied accessible
    name, every interactive target is at least 48 dp, nothing communicates state by colour alone, and
    no component removes or shrinks Material's focus indication or minimum interactive size.
17. **Scope discipline.** No new dependency, module, token, vector, asset, string resource, backend,
    contract, knowledge or design-reference change.

## Component contract

All declarations are `internal`, stateless, in
`shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` (navigation components may live in a
`design/navigation/` file but keep package `com.jamarglex.manijero.design`).

| File | Declaration |
|---|---|
| `ManijeroScreen.kt` | `ManijeroScreen(modifier = Modifier, content: @Composable ColumnScope.() -> Unit)`; pure `screenHorizontalPadding(windowWidth: Dp): Dp` |
| `ManijeroCard.kt` | `ManijeroCard(modifier = Modifier, tone: ManijeroCardTone = Outlined, content: @Composable ColumnScope.() -> Unit)`; `enum ManijeroCardTone { Surface, Tonal, Outlined, Danger }` |
| `ManijeroSectionHeader.kt` | `ManijeroSectionHeader(title: String, modifier = Modifier, description: String? = null, heading: Boolean = false)` |
| `ManijeroCallout.kt` | `ManijeroCallout(text: String, tone: ManijeroCalloutTone, modifier = Modifier, title: String? = null, action: (@Composable () -> Unit)? = null)`; `enum ManijeroCalloutTone { Info, Caution, Danger, Confirmation }` |
| `ManijeroStatCard.kt` | `ManijeroStatCard(label: String, value: String, supporting: String, modifier = Modifier)` |
| `ManijeroEmptyState.kt` | `ManijeroEmptyState(title: String, body: String, action: @Composable () -> Unit, modifier = Modifier)` |
| `ManijeroChip.kt` | `ManijeroAttributeChip(label: String, tone: ManijeroChipTone, modifier = Modifier)`; `enum ManijeroChipTone { Dryland, Irrigated, Organic, Neutral }` |
| `ManijeroChoiceCard.kt` | `ManijeroChoiceCard(label: String, selected: Boolean, onSelect: () -> Unit, modifier = Modifier, optionDescription: String? = null, isError: Boolean = false)` |
| `ManijeroFields.kt` | `ManijeroSearchField(value, onValueChange, label, clearDescription, modifier = Modifier, placeholder = null)`; `ManijeroDropdownField(label, options: List<String>, selected: String?, onSelect: (String) -> Unit, modifier = Modifier, placeholder = null, isError = false, supportingText = null)`; `ManijeroMeasureField(value, onValueChange, label, modifier = Modifier, supportingText = null, errorText = null, keyboardType = KeyboardType.Decimal)` |
| `navigation/ManijeroTopAppBar.kt` | `ManijeroTopAppBar(title: String, modifier = Modifier, onPrivacyClick: (() -> Unit)? = null, privacyLabel: String? = null, privacyDescription: String? = null)` |
| `navigation/ManijeroNavigation.kt` | `data class ManijeroDestination(val label: String, val icon: DrawableResource)`; `ManijeroBottomNavigation(destinations, selectedIndex, onSelect, modifier = Modifier)`; `ManijeroNavigationRail(destinations, selectedIndex, onSelect, modifier = Modifier)`; pure `selectedDestinationIndex(destinationsCount: Int, requestedIndex: Int): Int` |

Rules that hold for every row:

- Text, labels, values and option lists are `String` parameters. No `StringResource`, no generated
  `Res.string`, no shipped-copy ownership.
- Previews: at minimum light, dark and `fontScale = 2f` for each component, wrapped in `ManijeroTheme`
  with an explicit `darkTheme`.
- No animation is required; where an implementation animates, it stays under 250 ms and is never the
  only cue.
- `ManijeroCallout.action` and `ManijeroEmptyState.action` are slots, so the caller supplies the
  button and its string; the component adds no control of its own.
- `ManijeroDestination` has no selected flag; selection is `selectedIndex` plus
  `selectedDestinationIndex`, so the bars cannot disagree with the caller's state.

## Technical approach

- Build only from `compose.foundation`, `compose.material3`, `compose.ui` and
  `compose.components.resources`, already in `commonMain`. `ExposedDropdownMenuBox` and its anchor
  modifier come from Material 3 and need only the module's existing experimental opt-in.
- `ManijeroScreen` uses `BoxWithConstraints` for the 24/40 dp padding decision; the navigation bars
  set `windowInsets = WindowInsets(0)` because the future `Scaffold` owns insets.
- Chips and cards are non-clickable `Surface`s; the only interactive surfaces are the choice card,
  the search clear button, the top-bar action and the navigation items, all with Material's default
  indication and minimum target.
- The gallery lives in `shared/src/commonTest/kotlin/com/jamarglex/manijero/design/ComponentGallery.kt`
  and uses plain review labels (never `strings.xml`). It is not referenced by `commonMain`.
- Reuse the existing screenshot harness: two dedicated test classes, the pinned threshold, and the
  explicit record tasks. Record only the eight new gallery goldens; never re-record an app or brand
  board golden.
- The two pure helpers have no dedicated test class. Their behaviour is exercised by the gallery
  renders and read in review; the fixed viewports do not assert the 839/840 dp boundary, and the
  renders use only valid selections. No new test dependency.

## Expected file changes

- **Add** the nine component files plus the two navigation files under `design/`.
- **Add** `commonTest/design/ComponentGallery.kt`.
- **Add** `jvmTest/.../screenshots/ComponentGalleryScreenshotsTest.kt`,
  `androidHostTest/.../screenshots/ComponentGalleryAndroidScreenshotsTest.kt`, and the eight PNGs.
- **Update** `DESIGN.md` (component layer, top-bar action glyph decision), `CONSTRAINTS.md`
  (presentational-layer rule), `docs/screenshot-regression.md` (capture table and viewports).
- After acceptance: `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, the appendix,
  and the acceptance record.
- **Not changed:** screens, `App.kt`, `theme/`, `composeResources/` (vectors and `strings.xml`),
  Android/Desktop entry points, Gradle/version catalog, `backend/`, `contracts/`, `knowledge/`,
  `design-references/`, and the sixteen existing goldens.

## Visual design impact

The components make the approved visual language reusable: flat `surfaceContainerLowest` cards with a
1 dp `outlineVariant` edge and 16 dp radius, tonal grouping on the container family, caution and danger
only as status hues with icon plus text, the four accepted chip pairs, 720 dp centred content, and
48 dp targets. Navigation is flat (surface + divider, no shadow) so the shell reads as one calm
surface when `app_chrome_navigation` wires it. The top bar reuses `ic_info` for the privacy action
because the fixed sixteen-glyph inventory has no shield; adding a glyph here would re-open the
`brand_vectors` board goldens, so the shield is deferred to a later, visually reviewed change and the
accessible name carries the meaning now. No component implies verification, official status,
eligibility or legal certainty.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record the shared component layer, its tone/variant vocabulary, the no-shadow navigation rule, and the `ic_info` privacy-action decision. |
| `CONSTRAINTS.md` | Update | Add the durable rule that components stay presentational, theme-only and accessible, so later screens cannot turn them into business logic or raw-colour surfaces. |
| `docs/screenshot-regression.md` | Update | Add the review-only component gallery captures and their viewports; keep the existing counts honest. |
| `ARCHITECTURE.md` | Not needed | New files stay inside the existing `shared` `commonMain` boundary; no module, dependency or data flow changes. |
| `AGENTS.md` | Not needed | Existing shared-UI and skill routing already covers component work. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/session-log.md` | Update after implementation and independent acceptance | Keep status, evidence pointers and known limits honest. |

## Focused verification

The block compiles and tests the shared layer, verifies both host screenshot suites (the gallery is
the visual evidence), and enforces the scope rules. It is read-only apart from Gradle output.

<!-- verify:start -->
```sh
./gradlew :shared:verifyScreenshots
design="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/design"
for name in ManijeroScreen ManijeroCard ManijeroSectionHeader ManijeroCallout ManijeroStatCard ManijeroEmptyState ManijeroAttributeChip ManijeroChoiceCard ManijeroSearchField ManijeroDropdownField ManijeroMeasureField ManijeroTopAppBar ManijeroBottomNavigation ManijeroNavigationRail; do
  grep -rq "internal fun $name(" "$design" || { echo "missing component: $name" >&2; exit 1; }
done
if grep -rnE 'Color\(0x|#[0-9A-Fa-f]{3,8}' "$design" --include='*.kt'; then
  echo "raw colour literal in the component layer" >&2; exit 1
fi
if grep -rnE 'Res\.string|com\.jamarglex\.manijero\.(lands|chat|privacy|coverage|platform)' "$design" --include='*.kt'; then
  echo "component layer owns copy or a domain dependency" >&2; exit 1
fi
screens="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero"
if grep -rq 'com\.jamarglex\.manijero\.design' "$screens/App.kt" "$screens/lands" "$screens/coverage" "$screens/privacy"; then
  echo "an existing screen adopted the component layer in this feature" >&2; exit 1
fi
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/design/ComponentGallery.kt" || { echo "missing review gallery" >&2; exit 1; }
test ! -f "$design/ComponentGallery.kt" || { echo "gallery must stay test-only" >&2; exit 1; }
for shot in component_gallery_light component_gallery_dark component_gallery_narrow_large_text_light component_gallery_narrow_large_text_dark; do
  test -f "$REPO_ROOT/shared/src/jvmTest/screenshots/$shot.png" || { echo "missing Desktop golden: $shot" >&2; exit 1; }
  test -f "$REPO_ROOT/shared/src/androidHostTest/screenshots/$shot.png" || { echo "missing Android golden: $shot" >&2; exit 1; }
done
if grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml"; then
  echo "an icon-font dependency was added" >&2; exit 1
fi
```
<!-- verify:end -->

The block proves compile, theme-only styling, the scope gates and pixel stability. It cannot judge
whether a component looks right, wraps cleanly at 2× text, or reads well to a screen reader; those are
the gallery review and the limits recorded in the acceptance record.

## Appendix

See [`ui_component_library.appendix.md`](../archive/specs/ui_component_library.appendix.md) for repository research,
component decisions, the ordered implementation plan, evidence to capture and the validator checklist.
