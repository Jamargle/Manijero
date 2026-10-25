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
| T7 | Add the review-only `BrandVectorBoard` plus light/dark previews, labels as review identifiers only | `design/BrandVectorBoard.kt` | Board shows the mark, the illustration, and all sixteen icons at 24 dp (two at 20 dp) |
| T8 | Add the inventory test that names all eighteen resources and asserts pairwise distinctness | `commonTest/design/BrandVectorSetTest.kt` | Test fails to compile if a named vector is missing; passes on the authored set |
| T9 | Add Desktop and Android host screenshot classes for the board in both appearances and record only the four new goldens | `jvmTest/.../BrandVectorBoardScreenshotsTest.kt`, `androidHostTest/.../BrandVectorBoardAndroidScreenshotsTest.kt`, four PNGs | `verifyScreenshots` passes; `git status` shows the twelve existing goldens unchanged |
| T9b | `--fast` and `--verify` after the focused block | — | Full gate green with no new failures |
| T10 | Record the durable rules: brand vectors/iconography section in `DESIGN.md`, asset rules in `CONSTRAINTS.md`; append evidence to this appendix and write `docs/validations/brand_vectors.md` at acceptance | docs | Docs match the shipped assets and tint policy |

## Verification plan

1. `./scripts/init.sh --feature brand_vectors` — runs `BrandVectorSetTest`, both screenshot suites in
   verify mode, and the inventory/style/colour/dependency shell gates. Cheapest tier that touches the
   feature.
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

_(Append verified implementation and validation evidence here. Do not restate it in `PROGRESS.md` or
`docs/progress/session-log.md`.)_

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
- [ ] The review-only board and its previews exist, are not referenced by any screen, and its labels are
      not shipped copy in `strings.xml`.
- [ ] `BrandVectorSetTest` names all eighteen resources, fails on a missing/renamed file, and asserts
      distinctness rather than tautologies.
- [ ] The four new goldens exist per platform, were recorded deliberately, and the twelve existing PNGs
      are unchanged (`git diff` shows no modification to them).
- [ ] No screen, shell, theme, string, Gradle, backend, contract, or `design-references/` file changed;
      no dependency or module was added.
- [ ] `DESIGN.md` and `CONSTRAINTS.md` record the asset, tint, decorative, and no-Material-icons rules;
      `ARCHITECTURE.md`/`AGENTS.md` are correctly left untouched.
- [ ] Evidence in this appendix is real command output, and the manual visual judgement is stated with
      its host-rendering limit and the pending owner sign-off.
