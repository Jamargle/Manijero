# Feature Spec: `brand_vectors`

## Source metadata

- **Feature:** `brand_vectors` — Add the brand mark, icon set, and empty-state illustration (`client`).
- **Status at planning:** `not_started`; depends on accepted `design_token_refresh` and
  `screenshot_regression_tests`.
- **Source behavior:** The shared app owns a hand-authored identity layer — a brand mark, sixteen
  single-colour UI icons, and an olive-branch empty-state illustration — stored as Android vector XML
  in shared multiplatform resources and drawn by thin shared Compose wrappers whose colour always comes
  from the shared theme. No screen adopts them in this feature.
- **Feature verification:** Focused shared tests prove the published vector inventory, the vector-style
  gates prove the monochrome/24 dp contract, and the existing Desktop and Android host screenshot suites
  render a review-only vector board in both appearances while leaving the twelve existing goldens
  byte-identical.
- **Plan steps:** P0-07…P0-10 of [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md), with
  decisions D8 (vector brand mark + olive-branch illustration, no image generation, no binary assets)
  and D11 (no `material-icons-core` runtime dependency).
- **Approval:** `DESIGN.md` and plan §3.4 are the approved visual authority; the vector source geometry
  and Apache 2.0 attribution are recorded in this feature's appendix.

## Goal and boundaries

Give the UI refresh its visual vocabulary: one identity mark, one coherent outline icon set, and one
decorative empty-state illustration, all authored as vectors under version control and all tinted from
the accepted theme so light and dark appearances need no duplicate assets. The feature stops at the
assets and their wrappers; adopting them in the app shell, components, or screens belongs to later
slices.

**In scope**

- Eighteen hand-authored vector XML files in `shared/src/commonMain/composeResources/drawable/`: the
  brand mark, the olive-branch illustration, and exactly sixteen `ic_*.xml` UI glyphs.
- Three shared wrappers in a new `commonMain` package `design/`: `ManijeroIcon`, `ManijeroBrandMark`,
  `ManijeroOliveBranch`, each with light/dark previews.
- A review-only `BrandVectorBoard` composable in `commonTest` (test sources, not production code), used
  by the screenshot suites as the rendering proof for every vector in both appearances. It lives in
  test sources because nothing in the app renders it; the three wrappers stay in `commonMain` because
  they are the shipped API.
- Focused checks that pin the vector inventory, the asset style, and the rendering: the shell gates in
  this contract plus the Desktop and Android host screenshot suites, which cannot compile without every
  named accessor and cannot pass without rendering every vector.
- Documentation that records the icon/illustration/tint rules in `DESIGN.md`, the durable asset
  constraints in `CONSTRAINTS.md`, and the source geometry and licence in the appendix.

**Non-goals**

- No screen, shell, navigation, layout, copy, component-library, or behaviour change; no vector is wired
  into `App.kt`, the lands/help/privacy screens, or any platform module.
- No launcher-icon redesign, no store listing asset, no iOS app-icon change.
- No generated imagery, raster PNG/SVG asset, image-generation prompt, or binary asset of any kind.
- No `material-icons-*` runtime dependency and no new Gradle dependency or module.
- No typography, palette, token-scale, or theme-construction change.
- No accessibility, usability, or device claim: rendering a board proves decoding and tinting on the two
  pinned host renderers, not screen-reader output, touch targets, or legibility in real screens.

## Job story

When the interface starts using the refreshed design language, I want the app to show one calm, familiar
mark, a small set of legible outline icons, and a friendly empty-state illustration that works in light
and dark appearance, so the product feels like one considered app rather than a template.

## Acceptance scenarios

### The published vector inventory exists and is complete

Given the shared resources, when the focused check runs, then exactly sixteen `ic_*.xml` files, one
`brand_mark.xml`, and one `olive_branch.xml` exist under
`shared/src/commonMain/composeResources/drawable/`, with the sixteen glyph names fixed by this spec
(`ic_chat`, `ic_lands`, `ic_help`, `ic_search`, `ic_add`, `ic_edit`, `ic_delete`, `ic_back`, `ic_retry`,
`ic_send`, `ic_external_link`, `ic_info`, `ic_warning`, `ic_check`, `ic_chevron_down`, `ic_clear`).

### The icon set is one consistent outline system

Given any `ic_*.xml`, when its geometry is inspected, then it is a 24 dp vector on a 24×24 viewport,
every stroke is `2` dp wide with round caps and joins, every fill is transparent or absent, and paths
stay inside the 24 dp box so the glyph is legible at 20 dp and 24 dp.

### Colour comes only from the theme

Given any of the eighteen vectors, when its file is inspected, then no appearance colour is baked in:
the only colour literals are the black mask placeholder `#000000` and the transparent `#00000000`, and
every rendered colour is supplied by the wrapper from `MaterialTheme.colorScheme`, `LocalManijeroSemanticColors`,
or `LocalContentColor`. No vector declares `android:tint`, a gradient, or an external resource
reference.

### Icons render and tint on both host platforms

Given the review-only board, when the Desktop and the Android host screenshot suites render it in light
and dark appearance, then all sixteen icons, the brand mark, and the olive-branch illustration are
visible, single-colour, and legible against the themed background in both appearances.

### The brand mark is identity, not a status

Given the brand mark wrapper, when it is used, then it exposes no content-description parameter, renders
decoratively, uses `MaterialTheme.colorScheme.primary` by default, draws without blur at 28 dp, 32 dp,
and 48 dp, and never carries a "verified" or "official" meaning.

### The empty-state illustration is decorative and theme-tinted

Given the olive-branch wrapper, when it renders, then it draws a soft `primaryContainer` halo with the
branch in `onPrimaryContainer`, has no content-description parameter, adds no semantics node, and scales
between 160 dp and 200 dp without clipping.

### Screen appearance is unchanged

Given the existing screenshot goldens, when the screenshot suites verify after this feature, then the
twelve committed PNGs under `shared/src/jvmTest/screenshots/` and `shared/src/androidHostTest/screenshots/`
match unchanged, no screen or host-module file is modified, and the only new goldens are the board's.

### The asset set stays dependency-free

Given the build files, when the focused check runs, then no `material-icons-*` dependency or new module
was added, and the vectors use only the documented Android XML subset so all targets decode them.

## Vector inventory

All files live in `shared/src/commonMain/composeResources/drawable/`.

| File | Purpose (adoption happens in a later feature) | Geometry |
|---|---|---|
| `brand_mark.xml` | Circular olive mark with a leaf; top app bar only | 32×32 viewport, stroke 2, monochrome |
| `olive_branch.xml` | Empty-state illustration; drawn inside the wrapper's halo | 96×96 viewport, stroke 2, monochrome |
| `ic_chat` | Asistente destination and question suggestions | 24×24, outline |
| `ic_lands` | Mis terrenos destination | 24×24, outline |
| `ic_help` | Ayuda destination and informational entries | 24×24, outline |
| `ic_search` | Lands search field leading icon | 24×24, outline |
| `ic_add` | Añadir terreno action | 24×24, outline |
| `ic_edit` | Edit action | 24×24, outline |
| `ic_delete` | Remove action and destructive confirmation | 24×24, outline |
| `ic_back` | Back navigation in forms | 24×24, outline |
| `ic_retry` | Retry after a recoverable failure | 24×24, outline |
| `ic_send` | Send-question action | 24×24, outline |
| `ic_external_link` | Source link that leaves the app | 24×24, outline |
| `ic_info` | Informational callout | 24×24, outline |
| `ic_warning` | Caution callout | 24×24, outline |
| `ic_check` | Confirmation callout | 24×24, outline |
| `ic_chevron_down` | Expander or select affordance | 24×24, outline |
| `ic_clear` | Clear the search field | 24×24, outline |

The wizard placeholder `compose-multiplatform.xml` already in that directory is untouched: it is not a
product asset, this feature neither uses nor deletes it, and it is excluded from the sixteen-glyph
inventory.

## Wrapper contract

Package `com.jamarglex.manijero.design`, all `internal`, all stateless, no click handling:

```kotlin
@Composable
internal fun ManijeroIcon(
    resource: DrawableResource,
    contentDescription: String?,          // explicit, required: null means decorative
    modifier: Modifier = Modifier,
    size: Dp = ManijeroIconSize.Default,  // 24 dp; pass ManijeroIconSize.Inline for 20 dp
    tint: Color = LocalContentColor.current,
)

@Composable
internal fun ManijeroBrandMark(
    modifier: Modifier = Modifier,
    size: Dp = ManijeroIconSize.Large,    // 32 dp; 28 dp and 48 dp are valid call sites
)

@Composable
internal fun ManijeroOliveBranch(
    modifier: Modifier = Modifier,
    size: Dp = 180.dp,                    // valid range 160–200 dp
)
```

- `ManijeroIcon` loads the vector with `painterResource`, draws it at exactly `size` (never intrinsic
  size), and tints it; it is the only wrapper that accepts a content description.
- `ManijeroBrandMark` and `ManijeroOliveBranch` accept no colour or description parameter, so a caller
  cannot turn identity or decoration into a status cue. Their internals are fixed:
  `primary` tint for the mark; `primaryContainer` halo plus `onPrimaryContainer` branch for the
  illustration.
- Wrappers take no size token changes: `ManijeroIconSize` and `ManijeroLayout` stay as accepted by
  `design_token_refresh`.

## Technical approach

- Author the vectors as Android vector XML in the shared compose resources directory, using only the
  subset Compose Multiplatform decodes on every target: `<vector>`, `<path>` with `pathData`,
  `fillColor`, `strokeColor`, `strokeWidth`, `strokeLineCap`, `strokeLineJoin`, and simple `<group>`
  transforms. No gradients, `aapt:attr` blocks, `android:tint`, clip paths, or `@android:` references.
- Follow the official Compose Multiplatform guidance for Material Symbols geometry: black placeholder
  fill and tint at the call site. Geometry is hand-authored on the 24 dp grid (2 dp stroke, round joins),
  not copied verbatim; attribution is recorded in the appendix.
- Draw the illustration's halo in Compose (a `Box` with `background(primaryContainer, CircleShape)`),
  not in the vector, so appearance colours never enter an asset and the branch stays a monochrome mask.
- Keep the wrappers free of layout policy beyond `Modifier.size(size)`: padding, minimum touch target,
  and click behaviour belong to `ui_component_library` and later features.
- Add a review-only `BrandVectorBoard` composable in `commonTest` (test-only on purpose: nothing in
  the app renders it) that shows the 24dp grid, the shared `commonMain` wrappers, the mark at
  28/32/48 dp, the illustration at 160/200 dp, and all sixteen icons at 24 dp (with two at 20 dp).
  Labels are review identifiers, not shipped copy; the wrappers keep their own previews, so the board
  needs none.
- Reuse the accepted screenshot harness: one Desktop class and one Android host class capture the board
  at the fixed 900×1200 dp viewport in both appearances, using the existing `capture` helpers, fixed
  density/font scale, and pinned `es-ES` locale. Record the four new goldens explicitly; never re-record
  the existing twelve.

## Expected file changes

- **Add** `shared/src/commonMain/composeResources/drawable/brand_mark.xml`,
  `olive_branch.xml`, and the sixteen `ic_*.xml` files.
- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/ManijeroIcon.kt`,
  `ManijeroBrandMark.kt`, `ManijeroOliveBranch.kt` — the shipped wrappers — and
  `shared/src/commonTest/kotlin/com/jamarglex/manijero/design/BrandVectorBoard.kt` — the test-only
  review board.
- **Add** `shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/BrandVectorBoardScreenshotsTest.kt`,
  `shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/BrandVectorBoardAndroidScreenshotsTest.kt`,
  and the four goldens `brand_vector_board_light.png` / `brand_vector_board_dark.png` in
  `shared/src/jvmTest/screenshots/` and `shared/src/androidHostTest/screenshots/`.
- **Update** `DESIGN.md` (brand vectors, icon and illustration rules, tint policy, licence pointer),
  `CONSTRAINTS.md` (durable asset rules), `docs/screenshot-regression.md` (the new capture counts and
  the board's dedicated Android viewport).
- **Update after acceptance only:** `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`,
  this feature's appendix, `docs/validations/brand_vectors.md`.
- **Not changed:** every existing screen and host module, `theme/*`, `composeResources/values/strings.xml`,
  `ARCHITECTURE.md`, `AGENTS.md`, Gradle files and the version catalog, `contracts/`, `backend/`,
  `knowledge/`, `design-references/`, and the twelve existing screenshot goldens.

## Visual design impact

- The mark, icon set, and illustration enter the repository now and appear in the app only when
  `ui_component_library`, `app_chrome_navigation`, and the screen-refresh features adopt them.
- Icons are outline glyphs on a 24 dp grid with 2 dp strokes: visually quieter than filled Material
  icons and consistent with the flat, outlined-card foundation.
- The brand mark and illustration are monochrome masks tinted from theme roles, so both appearances use
  the same assets and the contrast gates accepted by `design_token_refresh` cover the pairs actually
  used (`primary` on background; `onPrimaryContainer` on `primaryContainer`).
- `DESIGN.md` gains the durable rules; feature behaviour and screen content stay owned by their specs.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Records the brand mark, icon set, illustration, tint policy, and licence pointer as the visual authority later screens cite. |
| `CONSTRAINTS.md` | Update | Adds the durable asset rules a later change must not break: monochrome theme-tinted vectors only, decorative identity, no Material icon dependency. |
| `docs/screenshot-regression.md` | Update | It is the harness doc future features follow; it needs the new capture counts and the board's viewport so the next suite is added consistently. |
| `PROGRESS.md` | Update after acceptance | Notes the new assets and the pending owner sign-off for the added goldens. |
| `docs/progress/session-log.md` | Update after acceptance | One pointer line to the spec and acceptance record. |
| `ARCHITECTURE.md` | Not needed | Resources stay inside the existing `shared` `commonMain` boundary; no module, dependency, or runtime path changes. |
| `AGENTS.md` | Not needed | Existing verification tiers already cover `--feature`; no new workflow rule. |
| `docs/design/ui-refresh-plan.md` | Not needed | §3.4 and §9 already describe this slice; the licence record lives in the appendix as the plan requires. |

## Focused verification

The published block is read-only apart from Gradle build output: it runs the inventory test, both
screenshot suites in verify mode, and the shell gates for the asset inventory, style, colour, and
dependency rules.

<!-- verify:start -->
```sh
./gradlew :shared:verifyScreenshots
vectors="$REPO_ROOT/shared/src/commonMain/composeResources/drawable"
test -f "$vectors/brand_mark.xml" || { echo "missing brand_mark.xml" >&2; exit 1; }
test -f "$vectors/olive_branch.xml" || { echo "missing olive_branch.xml" >&2; exit 1; }
icons="$(find "$vectors" -maxdepth 1 -name 'ic_*.xml' | sort)"
count="$(printf '%s\n' "$icons" | grep -c . || true)"
test "$count" -eq 16 || { echo "expected 16 ic_*.xml, found $count" >&2; exit 1; }
baked="$(grep -rhoE '#[0-9A-Fa-f]{6,8}' "$vectors"/brand_mark.xml "$vectors"/olive_branch.xml $icons | grep -vx -e '#000000' -e '#00000000' | sort -u || true)"
test -z "$baked" || { echo "appearance colour baked into a vector: $baked" >&2; exit 1; }
unsupported="$(grep -rl -e 'aapt:attr' -e 'Gradient' -e 'android:tint' -e '@android:' "$vectors"/brand_mark.xml "$vectors"/olive_branch.xml $icons || true)"
test -z "$unsupported" || { echo "unsupported vector feature in: $unsupported" >&2; exit 1; }
for icon in $icons; do
  grep -q 'android:width="24dp"' "$icon" || { echo "$icon is not 24 dp wide" >&2; exit 1; }
  grep -q 'android:viewportWidth="24"' "$icon" || { echo "$icon is not on a 24 dp viewport" >&2; exit 1; }
  grep -q 'android:strokeWidth="2"' "$icon" || { echo "$icon has no 2 dp stroke" >&2; exit 1; }
  grep -q 'android:strokeLineCap="round"' "$icon" || { echo "$icon does not use round caps" >&2; exit 1; }
  grep -q 'android:strokeLineJoin="round"' "$icon" || { echo "$icon does not use round joins" >&2; exit 1; }
  grep -q 'android:fillColor="#000000"' "$icon" && { echo "$icon contains a filled shape; the set is outline-only" >&2; exit 1; }
done
if grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml"; then echo "material-icons dependency was added" >&2; exit 1; fi
```
<!-- verify:end -->

Manual evidence this command cannot produce on its own: judging whether each glyph reads correctly at
20/24 dp, whether the mark is recognisable and calm at 28/32/48 dp, and whether the illustration looks
intentional at 160/200 dp. That judgement is made by inspecting the four new goldens; passing verify
proves decode, tint, and pixel stability only.

## Appendix

See [`docs/specs/brand_vectors.appendix.md`](brand_vectors.appendix.md) for repository research, the
vector geometry and licence record, implementation tasks, verification detail, evidence, and the
validator checklist.
