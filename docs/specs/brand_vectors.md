# Feature Spec: `brand_vectors`

## Source metadata

- **Feature:** `brand_vectors` — brand mark, icon set, and empty-state illustration (`client`).
- **Status at planning:** `not_started`; depends on accepted `design_token_refresh` and
  `screenshot_regression_tests`.
- **Source behavior:** the shared app owns a hand-authored identity layer — a brand mark, sixteen
  single-colour outline icons, and an olive-branch illustration — as Android vector XML in shared
  compose resources, drawn by thin Compose wrappers that take every colour from the theme. No screen
  adopts them in this feature.
- **Plan steps:** P0-07…P0-10 of [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md),
  decisions D8 (vectors only, no generated or binary assets) and D11 (no `material-icons-*` runtime
  dependency). `DESIGN.md` and plan §3.4 are the visual authority.
- **Record:** geometry, licence, and verification evidence are in the
  [appendix](../archive/specs/brand_vectors.appendix.md); the acceptance record is
  [`docs/validations/brand_vectors.md`](../validations/brand_vectors.md).

## Goal and boundaries

Give the UI refresh its visual vocabulary: one identity mark, one coherent outline icon set, and one
decorative empty-state illustration, authored as vectors and tinted from the theme so light and dark
need no duplicate assets. The feature stops at the assets and wrappers; adoption belongs to later
slices.

**In scope**

- Eighteen vector XML files under `shared/src/commonMain/composeResources/drawable/`: the brand mark,
  the illustration, and exactly sixteen `ic_*.xml` glyphs.
- Three shipped wrappers in a new `commonMain` package `design/`, each with light/dark previews.
- A review-only `BrandVectorBoard` in `commonTest`, rendered by the Desktop and Android host screenshot
  suites; four new goldens, with the twelve existing ones byte-identical.
- Focused shell gates over the asset set, and durable rules in `DESIGN.md`, `CONSTRAINTS.md`, and
  `docs/screenshot-regression.md`.

**Non-goals**

- No screen, shell, navigation, copy, component-library, or behaviour change; no vector wired into
  `App.kt`, a screen, or a platform module.
- No launcher/store asset, generated image, raster/SVG, binary asset, icon font, dependency, or module.
- No typography, palette, token-scale, or theme-construction change.
- No accessibility, usability, device, or iOS claim: host renders prove decode and tint only.

## Job story

When the interface starts using the refreshed design language, I want one calm, familiar mark, a small
set of legible outline icons, and a friendly empty-state illustration that work in light and dark, so
the app feels considered rather than templated.

## Acceptance scenarios

1. **Inventory.** The drawable directory holds exactly eighteen vectors: `brand_mark.xml`,
   `olive_branch.xml`, and these sixteen icons: `ic_chat`, `ic_lands`, `ic_help`, `ic_search`, `ic_add`,
   `ic_edit`, `ic_delete`, `ic_back`, `ic_retry`, `ic_send`, `ic_external_link`, `ic_info`, `ic_warning`,
   `ic_check`, `ic_chevron_down`, `ic_clear`.
2. **One outline system.** Every `ic_*.xml` is a 24 dp glyph on a 24×24 viewport with a 2 dp stroke,
   round caps and joins, no filled shape, and content inside the 2–22 dp safe area, legible at 20 dp
   and 24 dp.
3. **Theme-only colour.** The only colour literals are `#000000` and `#00000000`; every rendered colour
   comes from `MaterialTheme.colorScheme`, `LocalManijeroSemanticColors`, or `LocalContentColor`. No
   `android:tint`, gradient, `aapt:attr`, clip path, or external reference.
4. **Both hosts render it.** The board renders in both appearances on Desktop and Android, with the
   mark, illustration, and all sixteen icons visible, single-colour, and legible against the themed
   background.
5. **The mark is identity, not status.** `ManijeroBrandMark` exposes no description or colour parameter,
   draws decoratively in `primary` at 28/32/48 dp without blur, and never reads as verified/official.
6. **The illustration is decorative.** `ManijeroOliveBranch` paints a `primaryContainer` halo in Compose
   with the sprig in `onPrimaryContainer`, adds no description or semantics node, and scales 160–200 dp
   without clipping.
7. **Existing screens are unchanged.** The twelve committed app goldens match unchanged, no screen or
   host-module file is modified, and the only new goldens are the board's four.
8. **No new dependency.** No `material-icons-*` entry or module is added, and the vectors use only the
   Android XML subset Compose Multiplatform decodes on every target.

## Vector inventory

All files live in `shared/src/commonMain/composeResources/drawable/`.

| File | Geometry |
|---|---|
| `brand_mark.xml` | 32×32 viewport, stroke 2, monochrome open olive ring with a leaf |
| `olive_branch.xml` | 96×96 viewport, stroke 2, monochrome olive sprig; the halo is drawn in Compose |
| `ic_*.xml` | 24×24, outline, 2 dp round stroke |

Each icon's first intended use is decided by the adopting feature (`ui_component_library`,
`app_chrome_navigation`, and the screen slices). The wizard placeholder `compose-multiplatform.xml` is
untouched and excluded from the inventory.

## Wrapper contract

Package `com.jamarglex.manijero.design`, all `internal`, stateless, no click handling:

```kotlin
@Composable
internal fun ManijeroIcon(
    resource: DrawableResource,
    contentDescription: String?,          // explicit, required: null means decorative
    modifier: Modifier = Modifier,
    size: Dp = ManijeroIconSize.Default,  // 24 dp; ManijeroIconSize.Inline is 20 dp
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

- `ManijeroIcon` loads through `painterResource`, draws at exactly `size`, and is the only wrapper that
  accepts a content description.
- The mark and illustration take no colour or description parameter: `primary` for the mark,
  `primaryContainer` halo plus `onPrimaryContainer` sprig for the illustration (`CircleShape`, painted
  in Compose). They add no semantics node.
- `ManijeroIconSize` and `ManijeroLayout` stay as accepted by `design_token_refresh`.

## Technical approach

- Author Android vector XML using only the subset Compose Multiplatform decodes everywhere:
  `<vector>`/`<path>` with `pathData`, fill/stroke attributes, and simple `<group>` transforms. Black
  mask fill plus call-site tint, following the official Compose Multiplatform guidance; the
  illustration's halo is Compose-painted so no appearance colour enters an asset.
- Keep the wrappers free of layout policy beyond `Modifier.size(size)`: padding, touch target, and click
  handling belong to `ui_component_library`.
- Reuse the screenshot harness: one Desktop and one Android board class, the fixed 900×1200 dp viewport,
  existing capture helpers, and pinned density/font scale/`es-ES`. Record only the four new goldens;
  never re-record the twelve existing ones.

## Expected file changes

- **Add** the eighteen vectors under `composeResources/drawable/`.
- **Add** `design/ManijeroIcon.kt`, `ManijeroBrandMark.kt`, `ManijeroOliveBranch.kt` in `commonMain`, and
  `commonTest/design/BrandVectorBoard.kt` (test-only review board).
- **Add** the two board screenshot classes and the four board PNGs.
- **Update** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`. After acceptance:
  `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, this appendix, and the acceptance
  record.
- **Not changed:** screens, host modules, `theme/*`, `strings.xml`, `ARCHITECTURE.md`, `AGENTS.md`,
  Gradle/version catalog, `contracts/`, `backend/`, `knowledge/`, `design-references/`, and the twelve
  existing goldens.

## Visual design impact

The assets enter the repository now and appear in the app only when later features adopt them. Outline
glyphs on a 24 dp grid with 2 dp strokes stay quieter than filled Material icons and consistent with the
flat, outlined-card foundation. Monochrome masks tinted from gated theme roles mean both appearances
share one asset, using `primary` on background and `onPrimaryContainer` on `primaryContainer`.

## Durable documentation impact

`DESIGN.md` and `CONSTRAINTS.md` gain the durable asset, tint, and decorative rules;
`docs/screenshot-regression.md` gains the new capture counts and the board's viewport. After acceptance,
`feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, this appendix, and the acceptance
record are updated. `ARCHITECTURE.md` and `AGENTS.md` need no change: no module, dependency, or workflow
change is involved.

## Focused verification

The block is read-only apart from Gradle output: it runs both screenshot suites in verify mode and the
shell gates for inventory, style, colour, and dependency rules.

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

The command cannot judge whether each glyph reads correctly at 20/24 dp, whether the mark stays calm at
28/32/48 dp, or whether the illustration looks intentional at 160/200 dp; that is done by inspecting the
four new goldens. A pass proves decode, tint, and pixel stability only.

## Appendix

See [`brand_vectors.appendix.md`](../archive/specs/brand_vectors.appendix.md) for repository research, geometry and
licence, the implementation record, evidence, and the validator checklist.
