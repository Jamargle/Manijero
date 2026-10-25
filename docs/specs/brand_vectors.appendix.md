# Appendix — `brand_vectors`

Planning and verification record for [`docs/specs/brand_vectors.md`](brand_vectors.md). Sections:
repository research, vector geometry and licence record, implementation plan and tasks, verification
plan, evidence to capture, feature evidence, and the validator checklist.
`docs/validations/brand_vectors.md` is the authoritative acceptance record.

## Repository research

Inspected on 2026-10-25 in the `feature/brand_vectors` worktree (base `main` @ `8b3f680`), planning
only; no source file was changed by the planning step.

- **Compose and resources.** `gradle/libs.versions.toml` pins Compose Multiplatform `1.12.1`, Material 3
  `1.12.0-alpha03`, Kotlin `2.4.20`, AGP `9.4.1`. `shared/build.gradle.kts` already depends on
  `compose.components.resources` in `commonMain`, so no dependency is needed for vectors. The generated
  accessor package is `manijero.shared.generated.resources` and its members are `internal` to the
  `shared` module (verified in `shared/build/generated/.../Res.kt` and the drawable accessors).
- **Official XML-vector support.** The Kotlin Multiplatform resource documentation
  ("Using multiplatform resources in your app", JetBrains, October 2026) states that `painterResource`
  returns a `VectorPainter` for Android XML vector drawables on every target, that external Android
  resource references are unsupported, and that Material Symbols XML icons should carry
  `android:fillColor="#000000"` with tinting applied in Compose. This is the basis for the wrapper tint
  policy and the black-mask gate. The only XML vector in the repository today is the wizard placeholder
  `shared/src/commonMain/composeResources/drawable/compose-multiplatform.xml`, which already proves the
  directory and pipeline exist; nothing in `commonMain` loads it.
- **Resources present.** `shared/src/commonMain/composeResources/drawable/` contains only that
  placeholder; `composeResources/values/strings.xml` holds the shipped Spanish copy consumed through
  `stringResource`. No font, image, or other drawable asset exists. `androidApp/src/main/res/mipmap-*`
  and `iosApp/.../AppIcon.appiconset` hold launcher icons only and are out of scope.
- **No icon system yet.** There is no `design/` package; `commonMain` has `theme/`, `chat/`, `lands/`,
  `coverage/`, `privacy/`, `platform/`, and the app root. No file imports `Icons.*`, `painterResource`,
  or any Material icon; no screen draws an icon today. `ManijeroIconSize` (`Inline` 20, `Default` 24,
  `Large` 32) and `ManijeroLayout` (content width 720, padding 24/40/32, border 1, min touch target 48)
  are already accepted tokens, and the contract reuses them instead of adding values.
- **Theme roles available for tinting.** `design_token_refresh` accepted the Stitch palette with gated
  pairs. The two pairs this feature relies on are `primary` on `background` (light 10.18:1, dark 6.91:1)
  and `onPrimaryContainer` on `primaryContainer` (light 4.56:1, dark 9.10:1), both asserted in
  `ManijeroColorsTest`/`ManijeroDesignSystemTest`. The wrapper defaults are therefore contrast-backed
  without new gates.
- **Screenshot regression harness.** `screenshot_regression_tests` accepted two suites:
  `shared/src/jvmTest/.../screenshots/` (Compose Desktop, `ScreenshotTestSupport.capture`, fixed
  900×1200 and 360×800 viewports, density 1, font scale 1, LTR, pinned `es-ES`, `changeThreshold`
  0.001) and `shared/src/androidHostTest/.../screenshots/` (Robolectric 4.17, `@Config(sdk = [35],
  qualifiers = "es-rES-w360dp-h800dp-mdpi")`, native graphics). Goldens are twelve PNGs
  (8 Desktop, 4 Android); `./gradlew :shared:verifyScreenshots` verifies read-only, and
  `:shared:recordScreenshots` is the explicit record path. Both suites are excluded from `:shared:jvmTest`,
  `:shared:testAndroidHostTest`, and `--fast`.
- **Test tiers.** `./scripts/init.sh --feature <id>` executes exactly the spec's `verify:start` block;
  `--fast` runs shared host tests, the contract examples, backend pytest, the catalog validation, and the
  offline evaluators; `--verify` adds `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and
  `:desktopApp:build`. `local.properties` points at an installed Android SDK, and the previous accepted
  feature ran the Android host suite successfully on this host, so no emulator is required.
- **Documentation state.** `DESIGN.md` already records the palette, contrast contract, and the plan's
  §3.4 intent ("24 dp icons, 2 dp stroke, rounded caps/joins; 20 dp inline; 48 dp minimum interactive
  target"), but has no section for the mark, icon set, illustration, or licence. Plan §3.4 explicitly
  requires the geometry and licence note to live in this feature's appendix. `CONSTRAINTS.md` has no
  asset rules yet. `ARCHITECTURE.md` does not mention `composeResources`, and the resources stay inside
  the existing shared `commonMain` boundary, so it needs no update.
- **Scope of adoption.** Plan §9 orders this slice before `ui_component_library`, which introduces the
  call sites (`ManijeroTopAppBar`, `ManijeroEmptyState`, navigation, and screen components). Wiring any
  vector into a screen here would pre-empt those contracts and change goldens the screenshot suite is
  meant to hold stable.
- **Inventory decision.** The sixteen glyphs are exactly the plan's list; the spec fixes names, so a later
  screen that needs a new glyph extends the inventory (test + shell gate) in its own feature instead of
  improvising an inline path.

## Vector geometry and licence record

- **Grid.** UI icons are authored on a 24×24 viewport with `android:width/height="24dp"`, a 2 dp stroke,
  round caps, round joins, and a 2 dp safety margin (content within x/y 2–22). Outline-only: no filled
  shapes, so a single tint produces one visual weight across the set. `ManijeroIcon` draws them at 24 dp
  by default and 20 dp inline.
- **Brand mark.** 32×32 viewport, stroke 2, monochrome: an open olive ring enclosing a leaf and a short
  stem. It reads as identity at 28/32/48 dp, holds no text, and carries no check, badge, or seal shape
  that could be mistaken for verification.
- **Illustration.** 96×96 viewport, stroke 2, monochrome olive sprig (a stem with paired leaves and two
  olives). The halo is not part of the vector: `ManijeroOliveBranch` paints a `primaryContainer` circle
  behind it and tints the sprig `onPrimaryContainer`. Valid sizes 160–200 dp; 180 dp default.
- **Source geometry.** Glyph conventions follow Material Symbols (Google Fonts Icons gallery, Apache
  License 2.0) — chat bubble, land rows, help circle, magnifier, plus, pencil, bin, back arrow, circular
  retry arrow, paper plane, external-link box, info circle, warning triangle, check, chevron, and clear
  cross. Each path is authored in this repository on the 24 dp outline grid above; no exported SVG or
  Android XML file is copied. If an implementer does copy an exported Material Symbols path, the file
  must then carry the Apache 2.0 attribution from that source in a comment, and the 2 dp stroke grid rules
  still apply.
- **Licence.** Material Symbols is Apache License 2.0 (compatible with this repository's use); the
  repository's own path data is original. No third-party font, image, or binary asset is added.

## Implementation plan and tasks

Ordered; each task ends with the stated check.

| Task | Work | Files | Done when |
|---|---|---|---|
| T1 | Author the brand mark vector (32×32, stroke 2, monochrome, no gradients) | `composeResources/drawable/brand_mark.xml` | Renders recognisably at 28/32/48 dp in the board on both hosts |
| T2 | Author the olive-branch vector (96×96, stroke 2, monochrome, no halo) | `composeResources/drawable/olive_branch.xml` | Renders at 160/200 dp inside the theme halo |
| T3 | Author the sixteen outline icons from the inventory table | `composeResources/drawable/ic_*.xml` | File count 16; every style gate in the focused block passes |
| T4 | Add `ManijeroIcon` with required `contentDescription`, explicit size, `LocalContentColor` tint, `painterResource` loading | `design/ManijeroIcon.kt` | Preview renders 20 dp and 24 dp icons in both appearances |
| T5 | Add `ManijeroBrandMark` (primary tint, no description parameter, 32 dp default) | `design/ManijeroBrandMark.kt` | Preview shows 28/32/48 dp, no blur, decorative |
| T6 | Add `ManijeroOliveBranch` (`primaryContainer` halo, `onPrimaryContainer` sprig, no description/colour parameters, 180 dp default) | `design/ManijeroOliveBranch.kt` | Preview shows 160/200 dp, decorative |
| T7 | Add the review-only `BrandVectorBoard` in test sources (`commonTest`), labels as review identifiers only; no previews, because the wrappers already own them | `commonTest/design/BrandVectorBoard.kt` | Board shows the mark, the illustration, and all sixteen icons at 24 dp (two at 20 dp) |
| T8 | ~~Add a separate inventory test~~ — dropped as redundant: the board names all eighteen accessors, so a missing or renamed vector already fails compilation, the shell gates pin the file set and style, and the goldens render every vector. No third copy of the list is maintained. | — | Inventory, style, and rendering covered by the board references, the focused gates, and the four goldens |
| T9 | Add Desktop and Android host screenshot classes for the board in both appearances and record only the four new goldens | `jvmTest/.../BrandVectorBoardScreenshotsTest.kt`, `androidHostTest/.../BrandVectorBoardAndroidScreenshotsTest.kt`, four PNGs | `verifyScreenshots` passes; `git status` shows the twelve existing goldens unchanged |
| T9b | `--fast` and `--verify` after the focused block | — | Full gate green with no new failures |
| T10 | Record the durable rules: brand vectors/iconography section in `DESIGN.md`, asset rules in `CONSTRAINTS.md`; append evidence to this appendix and write `docs/validations/brand_vectors.md` at acceptance | docs | Docs match the shipped assets and tint policy |

## Verification plan

1. `./scripts/init.sh --feature brand_vectors` — runs both screenshot suites in verify mode plus the
   inventory/style/colour/dependency shell gates. The suites compile every named accessor (a missing or
   renamed vector breaks the build) and render all eighteen vectors in both appearances. Cheapest tier
   that touches the feature.
2. `./scripts/init.sh --fast` — shared host tests, contract examples, backend pytest, catalog validation,
   and offline evaluators; catches an accidental test-source regression outside the focused filter.
3. `./scripts/init.sh --verify` — adds `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and
   `:desktopApp:build`, proving the new resources are packaged for both hosts.
4. Manual review of the four new goldens (Desktop light/dark, Android light/dark): each glyph reads at
   20/24 dp, the mark is recognisable and calm at 28/32/48 dp, the illustration looks intentional at
   160/200 dp, and nothing implies verification or official status.
5. `git status --short` / `git diff --stat` review: only the files listed in the contract changed; the
   twelve existing goldens are byte-identical; no screen, theme, string, Gradle, or backend file is
   touched.

Recording discipline: use `./gradlew :shared:recordScreenshots` once, inspect the four new images, and
confirm the twelve existing PNGs are unmodified before committing. Verification must never rewrite a
baseline.

## Evidence to capture

- The focused block output, including the test counts and the `verifyScreenshots` result.
- `--fast` and `--verify` results with test counts.
- The four new golden file names and a short description of what each shows.
- The output of the inventory/style gates (or a statement that they passed silently).
- The final `git status --short` and `git diff --stat -- shared/src/*/screenshots` evidence that the
  twelve existing goldens are unchanged.
- The manual judgement above, stated as an observation with its limits (host-rendered board only).
- A note that the four new goldens join the pending owner sign-off item already recorded in
  `PROGRESS.md`; the mechanism and validator review exist, product-owner approval does not.

## Feature evidence

### Implementation (implementer, 2026-10-25)

- Assets: `brand_mark.xml` (32×32, open ring + leaf + stem), `olive_branch.xml` (96×96, stem, two
  leaf pairs, two olives), and the sixteen `ic_*.xml` glyphs in
  `shared/src/commonMain/composeResources/drawable/`. All eighteen are stroke-only masks
  (`strokeColor="#000000"`, `fillColor="#00000000"`, stroke 2, round caps/joins) so the wrapper
  supplies every rendered colour. The wizard placeholder `compose-multiplatform.xml` is untouched.
- Wrappers (package `com.jamarglex.manijero.design`, all `internal`, stateless, no click handling):
  `ManijeroIcon.kt` (required `contentDescription`, `painterResource`, exact `size`,
  `LocalContentColor` tint), `ManijeroBrandMark.kt` (`primary`, 32 dp default, decorative),
  `ManijeroOliveBranch.kt` (`primaryContainer` halo drawn in Compose, `onPrimaryContainer` sprig,
  180 dp default), each with light/dark previews.
- Review-only `BrandVectorBoard.kt` plus light/dark previews at 900×1200 dp: mark at 28/32/48 dp,
  illustration at 160/200 dp, sixteen icons at 24 dp, two at 20 dp, labels are review identifiers.
  No screen, shell, `App.kt`, theme, string, Gradle, backend, or contract file references it.
- Rendering coverage: one Desktop and one Android host screenshot class render the board in both
  appearances. There is no separate inventory test: the board's references make a missing or renamed
  vector a compile error, the focused shell gates pin file count, grid, stroke, and colour, and the
  goldens show every glyph. This keeps a single list of the eighteen names instead of three.
- Docs: `DESIGN.md` gained a "Brand vectors and iconography" section (icon grid, sizes, tint policy,
  mark and illustration rules, asset/licence policy); `CONSTRAINTS.md` gained the four durable
  brand-vector rules.

### Verification output

1. `./scripts/init.sh --feature brand_vectors` — every published check passed, but the wrapper exits
   **1** because the last line of the published block is
   `grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml" && { ...; exit 1; }`: with no
   `material-icons` dependency the grep returns 1, which is the *passing* outcome but is also the
   script's final status (`bash -euo pipefail`). Reproduced in isolation: the last line alone exits 1,
   the same line plus `true` exits 0, and `grep -c material-icons gradle/libs.versions.toml` prints
   `0`. The block minus that line exits 0. Results inside it:
   - `./gradlew :shared:jvmTest --tests BrandVectorSetTest` — BUILD SUCCESSFUL, 4 tests, 0 failures.
   - `./gradlew :shared:verifyScreenshots` — BUILD SUCCESSFUL, 16 screenshot tests (10 Desktop: 8
     existing + 2 new; 6 Android host: 4 existing + 2 new), all PASSED.
   - Shell gates: `brand_mark.xml` and `olive_branch.xml` present; exactly 16 `ic_*.xml`; no baked
     appearance colour (only `#000000`/`#00000000`); no `aapt:attr`/`Gradient`/`android:tint`/
     `@android:`; every icon 24 dp wide on a 24 viewport with a 2 dp round stroke and no filled shape;
     no `material-icons` dependency.
   Suggested one-line fix for the document owner: replace that final line with
   `if grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml"; then echo "material-icons dependency was added" >&2; exit 1; fi`.
2. `./scripts/init.sh --fast` — exit 0. `:shared:jvmTest` 204 tests in 24 classes, 0 failures
   (includes the 4 new ones). Contract examples: 2 request + 3 response examples validated. Backend
   pytest: 618 passed (run with
   `MANIJERO_PYTHON=/Users/Jose1/AndroidStudioProjects/Manijero/backend/.venv/bin/python`, because
   this worktree has no virtualenv of its own; without it the tier prints the install recipe and
   skips that suite). Source catalog: 4 sources. "All 9 offline checks passed." "Fast tier passed."
3. `./scripts/init.sh --verify` — exit 0. Repeat of the fast tier, then `:shared:testAndroidHostTest`
   190 tests in 20 classes with 0 failures, `:androidApp:assembleDebug`, and `:desktopApp:build`, all
   BUILD SUCCESSFUL. The full run took 29 s; the re-run after the golden re-record reused the
   configuration cache and finished with the same tasks up to date in 1 s.
4. Goldens recorded deliberately with a per-class filter, never by re-recording the suite:
   `./gradlew :shared:recordDesktopScreenshots --tests '*BrandVectorBoardScreenshotsTest'` and
   `./gradlew :shared:recordAndroidScreenshots --tests '*BrandVectorBoardAndroidScreenshotsTest'`.
   The same two filtered commands were run once more after the board's icon grid changed from eight to
   four glyphs per row (see "Notes and deviations"); only the four new files were rewritten. Four new
   files only:
   - `shared/src/jvmTest/screenshots/brand_vector_board_light.png` — Desktop, light: title, mark at
     28/32/48 dp in `primary`, illustration at 160/200 dp on `primaryContainer` halos with the
     `onPrimaryContainer` sprig, sixteen icons at 24 dp in `onBackground`, `ic_search`/`ic_clear` at
     20 dp.
   - `shared/src/jvmTest/screenshots/brand_vector_board_dark.png` — same composition, dark palette.
   - `shared/src/androidHostTest/screenshots/brand_vector_board_light.png` and
     `brand_vector_board_dark.png` — the same board at the same 900×1200 dp viewport, rendered by
     Android through Robolectric.
5. `git status --short` after verification: `M CONSTRAINTS.md`, `M DESIGN.md`, `M
   docs/specs/brand_vectors.appendix.md` (this evidence), the 18 drawable files, `design/` (4
   wrappers), the inventory test, the two screenshot classes, and the four PNGs; no other source,
   theme, string, Gradle, backend, contract, or `design-references/` file changed, and no existing
   golden was modified. The appendix was the only pre-acceptance document the implementation step
   wrote, because this section is where the evidence belongs; the later repair pass additionally
   updates `docs/screenshot-regression.md` and one comment line in the Desktop board class (see
   "Repair pass (validator revise)" below).
   `git diff --exit-code -- shared/src/jvmTest/screenshots shared/src/androidHostTest/screenshots`
   exits 0, so the twelve existing goldens are byte-identical to `HEAD`.

### Manual visual judgement (host-rendered, from the four goldens)

- At 24 dp all sixteen glyphs read as intended (chat bubble, layered lands, help circle, magnifier,
  plus, pencil, bin, back arrow, circular retry arrow, paper plane, external-link box, info circle,
  warning triangle, check, chevron, cross); `ic_search` and `ic_clear` stay distinct at 20 dp.
  Weakest reads: `ic_lands` looks like generic layers rather than fields, and the retry arrowhead is
  small at 24 dp though the circular arrow is recognisable.
- At 32 dp and 48 dp the mark reads as an open olive ring holding a leaf; at 28 dp the leaf collapses
  to a small olive blob inside the ring, so the mark stays recognisable as a calm circular botanical
  symbol but the leaf detail is lost. No check, seal, badge, or "verified" reading appears at any
  size.
- At 160 dp and 200 dp the illustration reads as an olive sprig on a soft halo with two olives near
  the base; nothing is clipped at 200 dp and the branch keeps a margin from the halo edge.
- Limit: these are host renders (Compose Desktop and Robolectric/Android native graphics) at density 1,
  font scale 1, LTR, pinned `es-ES`. They prove decode, tint, and pixel stability on those renderers
  only; no device, emulator, iOS, screen-reader, touch-target, or real-screen legibility claim is made,
  and the board is a review surface rather than a screen. The four new goldens join the pending owner
  sign-off item in `PROGRESS.md`; the mechanism and images exist, product-owner approval does not.

### Notes and deviations

- The Android board class pins `qualifiers = "es-rES-w900dp-h1200dp-mdpi"` rather than the existing
  `w360dp-h800dp` used by the ChatHome/LandList classes, because the contract fixes one 900×1200 dp
  viewport for both hosts. The other four Android goldens are untouched.
- The inventory is pinned by the board's own accessor references (a missing or renamed vector fails
  compilation of `commonTest`), by the focused shell gates, and by the goldens. The earlier
  `BrandVectorSetTest` was removed on review as a redundant third copy of the same eighteen names; the
  per-file geometry, colour, and unsupported-feature rules were already enforced only by the shell gates.
- No iOS target was compiled in this session (the Kotlin/Native toolchain was not exercised), so "all
  targets decode these vectors" rests on the documented Compose Multiplatform XML subset rather than
  an iOS build. Neither `--fast` nor `--verify` covers iOS, and previous features record the same gap.
- The icon grid in the board is four glyphs per row rather than eight: at eight per row the review
  label `ic_chevron_down` was clipped to `ic_chevron_dow` in the goldens. Four per row keeps every
  review identifier readable at the fixed 900 dp width and still fits the 1200 dp height. This is a
  review-board layout detail, not shipped copy or screen layout, and no spec requirement pins the
  column count.
- The focused block's final gate originally read
  `grep -q 'material-icons' ... && { echo ...; exit 1; }`, so it returned 1 — the failing status —
  whenever the rule passed, and `./scripts/init.sh --feature brand_vectors` could never exit 0. The
  orchestrator corrected that single line to `if grep -q ...; then ...; exit 1; fi`, which preserves the
  published intent (fail only when a `material-icons` dependency exists); the block now exits 0 with
  every check passing. No other spec line, behaviour, or acceptance scenario changed.

### Repair pass (validator revise, 2026-10-25)

The validator confirmed the implementation complete and behaviourally correct — acceptance scenarios,
all twelve appendix checklist items, the focused tier, the full gate, and the twelve pre-existing
goldens good — and returned `revise` for documentation consistency only. This pass changed no Kotlin
logic, vector, test behaviour, Gradle, theme, string, backend, contract, or golden:

- `docs/screenshot-regression.md`: the capture table now states 10 Desktop and 6 Android goldens; the
  scenes paragraph names the review-only `BrandVectorBoard` as the fifth subject (light and dark, not
  a product screen, no accessibility claim); the Android render conditions keep
  `es-rES-w360dp-h800dp-mdpi` for the app scenes and add the board class's pinned
  `es-rES-w900dp-h1200dp-mdpi`; "Adding a capture" allows a dedicated class for a review-only board
  while keeping the fixture rule for app scenes. The spec contract now lists this update in "Expected
  file changes" and "Durable documentation impact".
- `CONSTRAINTS.md`: the brand-vector reason cites the contrast tokens of `design_token_refresh`
  (palette/contrast owner) instead of the older `shared_theme` name.
- `DESIGN.md`: the asset policy no longer claims the assets reuse `ManijeroShapes` (nothing does; the
  illustration halo uses `CircleShape`), and the stray double blank line after "Layout and
  interaction" is gone.
- `BrandVectorBoardScreenshotsTest.kt`: one comment now reads four-column grid, matching the shipped
  board; the test bodies and golden names are untouched.

### Validation (validator, 2026-10-25)

First pass `revise` (M1 documentation drift in `docs/screenshot-regression.md`, plus L1–L4 doc/comment
nits), repair pass, second pass **`accept`**. The validator independently re-ran
`./scripts/init.sh --feature brand_vectors` (exit 0: 4 inventory tests, 10 Desktop + 6 Android
screenshot tests), `./scripts/init.sh --verify` (exit 0), and the backend suite through
`MANIJERO_PYTHON` (618 passed), parsed the test-result XML (jvmTest 204/24, androidHostTest 190/20,
zero failures), parsed all eighteen vectors' path data to confirm the 24×24 grid, 2 dp round stroke
and 2–22 dp safe area, and confirmed by hash and mtime that the repair and re-validation re-recorded
no golden and that
`git diff --exit-code -- shared/src/jvmTest/screenshots shared/src/androidHostTest/screenshots`
stayed 0 across four runs. Board golden SHA-256: Desktop light
`4ba8ea3f7cbf5b14918995ec8fa2c83624e8567b22472ff6302db79ea8e3f415`, Desktop dark
`a66ad9cf710e575014649198fc405d6775f4bf9622c7cc0086c56f4c3d6d1a0d`, Android light
`0d59c6fd487c3fe9562a5dda750468c39625e4f125b44160de458b531d08f873`, Android dark
`5fdd9ff7710b3aded7fa47dc7681439285a99f2eea66bbb26506fb49a8184c58`. All twelve appendix checklist
items passed. The authoritative record is
[`docs/validations/brand_vectors.md`](../validations/brand_vectors.md); the one non-blocking polish
left unapplied is noted there.

Re-verified after the pass: `./scripts/init.sh --feature brand_vectors` exits 0, and
`git diff --exit-code -- shared/src/jvmTest/screenshots shared/src/androidHostTest/screenshots` exits
0, so all sixteen goldens (ten Desktop, six Android) are byte-identical.

## Post-acceptance follow-up (2026-10-25)

Review question raised after acceptance: why the review-only board lived in production `commonMain`. It
has no production consumer — only the two screenshot classes import it — so it was relocated:

- `shared/src/commonTest/kotlin/com/jamarglex/manijero/design/BrandVectorBoard.kt` — moved from
  `commonMain` and unchanged apart from dropping the two `@Preview` functions (a test source set is not
  a preview surface; the three wrappers keep their own light/dark previews).
- `ManijeroIcon.kt`, `ManijeroBrandMark.kt`, and `ManijeroOliveBranch.kt` stay in
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` because they are the shipped API the
  contract, `DESIGN.md`, and `CONSTRAINTS.md` publish for later features to adopt; moving them to test
  sources would hide the product API rather than remove dead code.

Re-verified after the move: `./scripts/init.sh --feature brand_vectors` exits 0, and a SHA-256 snapshot
of all sixteen goldens taken before and after the move is identical (ten Desktop, six Android), so
nothing was re-recorded. Commit: `refactor: move brand vector board to test sources`.

A second review question: the separate inventory test was overkill. It was removed
(`test: remove redundant brand vector inventory test`). The coverage it claimed still exists without it:
the board in `commonTest` references all eighteen accessors, so a missing or renamed vector is a compile
error before any test runs; the focused shell gates pin the file count, 24 dp grid, 2 dp round stroke, the
outline-only rule, the colour literals, and the no-`material-icons` rule; and the four goldens render
every vector in both appearances, where an aliased or duplicated asset is visible. The only lost
assertion is an automated pairwise-distinctness check, which the visual review of the goldens still
covers; the trade was three copies of the eighteen-name list for one.

## Validator checklist

- [ ] Exactly eighteen vectors exist under `shared/src/commonMain/composeResources/drawable/` with the
      spec's names; the wizard placeholder is untouched and excluded from the inventory.
- [ ] Every `ic_*.xml` is 24×24 with a 2 dp stroke, round caps/joins, no filled shape, and content inside
      the 2–22 dp safe area; each glyph is recognisable at 20 dp and 24 dp in the reviewed goldens.
- [ ] No appearance colour is baked in: only `#000000` / `#00000000` literals, no `android:tint`, no
      gradient, no `aapt:attr`, no `@android:` reference.
- [ ] `ManijeroIcon` requires an explicit `contentDescription`, draws at the requested size, tints from
      `LocalContentColor` by default, and loads through `painterResource`.
- [ ] `ManijeroBrandMark` and `ManijeroOliveBranch` expose no description or colour parameter, are
      decorative, and use `primary` / `primaryContainer`+`onPrimaryContainer` respectively.
- [ ] The illustration's halo is painted in Compose, not embedded in the vector; 160–200 dp works.
- [ ] The review-only board lives in `commonTest` (no previews, no production consumer), its labels are
      not shipped copy in `strings.xml`, and no shipped file references it; the three wrappers stay in
      `commonMain` as the published API.
- [ ] No redundant inventory test exists: the board's own accessor references, the shell gates, and the
      four goldens cover presence, style, and rendering without a third copy of the eighteen names.
- [ ] The four new goldens exist per platform, were recorded deliberately, and the twelve existing PNGs
      are unchanged (`git diff` shows no modification to them).
- [ ] No screen, shell, theme, string, Gradle, backend, contract, or `design-references/` file changed;
      no dependency or module was added.
- [ ] `DESIGN.md` and `CONSTRAINTS.md` record the asset, tint, decorative, and no-Material-icons rules;
      `ARCHITECTURE.md`/`AGENTS.md` are correctly left untouched.
- [ ] Evidence in this appendix is real command output, and the manual visual judgement is stated with
      its host-rendering limit and the pending owner sign-off.
