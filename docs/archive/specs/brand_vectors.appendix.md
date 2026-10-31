# Appendix — `brand_vectors`

Planning and verification record for [`brand_vectors.md`](../../specs/brand_vectors.md). The authoritative
acceptance record is [`docs/validations/brand_vectors.md`](../../validations/brand_vectors.md); this
appendix holds the repository research, geometry/licence, plan, evidence, and validator checklist.

## Repository research

Inspected 2026-10-25 in `feature/brand_vectors` (base `main` @ `8b3f680`); planning changed no source.

- Compose Multiplatform `1.12.1`, Material 3 `1.12.0-alpha03`, Kotlin `2.4.20`, AGP `9.4.1`.
  `compose.components.resources` is already a `commonMain` dependency, so no dependency is needed.
  Generated accessors (`manijero.shared.generated.resources`) are `internal` to `shared`.
- The JetBrains multiplatform-resources documentation states that `painterResource` returns a
  `VectorPainter` for Android XML vectors on every target, external Android references are
  unsupported, and Material Symbols should use `android:fillColor="#000000"` with tinting in Compose.
  This is the basis for the mask/tint policy and the black-fill gate.
- The drawable directory contains only the wizard placeholder `compose-multiplatform.xml` (untouched,
  no `commonMain` consumer). No font, image, or other drawable exists; launcher icons are out of scope.
- There is no `design/` package and no icon usage today. `ManijeroIconSize` (20/24/32) and
  `ManijeroLayout` are accepted tokens and are reused; no new token is introduced.
- The contrast pairs this feature relies on are already gated: `primary`/`background` (10.18:1 light,
  6.91:1 dark) and `onPrimaryContainer`/`primaryContainer` (4.56:1, 9.10:1).
- The screenshot harness provides a Desktop suite (Compose Desktop) and an Android host suite
  (Robolectric 4.17, SDK 35), twelve goldens, read-only `verifyScreenshots`, explicit record tasks,
  and pinned density/font scale/`es-ES`. Both suites are excluded from `:shared:jvmTest`,
  `:shared:testAndroidHostTest`, and `--fast`.
- Tiers: `--feature` runs the spec's `verify:start` block; `--fast` adds shared host tests, contract
  examples, backend pytest, catalog validation, and offline evaluators; `--verify` adds
  `:shared:testAndroidHostTest` and both app builds.
- `DESIGN.md` records the palette and plan §3.4 intent but had no mark, icon, illustration, or licence
  section; `CONSTRAINTS.md` had no asset rules; `ARCHITECTURE.md` needs no change because resources
  stay inside the existing `shared` `commonMain` boundary.
- Adoption is deliberately later: `ui_component_library`, `app_chrome_navigation`, and the
  screen-refresh features introduce the call sites; a screen needing another glyph adds it in its own
  feature instead of inlining a path.

## Vector geometry and licence record

- **Icons.** 24×24 viewport, `android:width/height="24dp"`, 2 dp stroke, round caps and joins, content
  inside x/y 2–22, outline only (no filled shape), so one tint gives the set one visual weight.
- **Mark.** 32×32 viewport, stroke 2: an open olive ring with a leaf and a short stem; no text, check,
  badge, or seal shape. Reads as identity at 28/32/48 dp.
- **Illustration.** 96×96 viewport, stroke 2: a stem with paired leaves and two olives. The halo is not
  in the vector: `ManijeroOliveBranch` paints a `primaryContainer` circle in Compose and tints the
  sprig `onPrimaryContainer`. Valid sizes 160–200 dp, 180 dp default.
- **Source and licence.** Geometry follows Material Symbols conventions (Google Fonts Icons gallery,
  Apache 2.0); every path is authored for this repository, not copied from a file. If a later
  implementer copies an exported Material Symbols path, it must carry the Apache 2.0 attribution and
  still obey the 2 dp grid. No third-party font, image, or binary asset is added.

## Implementation plan

Ordered; each task ends with the stated check.

| # | Work | Done when |
|---|---|---|
| T1 | Author `brand_mark.xml`, `olive_branch.xml`, and the sixteen `ic_*.xml` | Style gates pass; vectors render on both hosts |
| T2 | Add `ManijeroIcon`, `ManijeroBrandMark`, `ManijeroOliveBranch` with light/dark previews | Previews show 20/24 dp icons, 28/32/48 dp mark, 160/200 dp illustration |
| T3 | Add the review-only `BrandVectorBoard` in `commonTest` | Board shows all eighteen vectors; labels are review identifiers only |
| T4 | Add the Desktop and Android board classes and record only four new goldens | `verifyScreenshots` green; twelve existing PNGs unchanged |
| T5 | Record the durable rules and the evidence, then validate | Docs match shipped assets and capture counts |

An inventory test was implemented and then dropped on review: the board's accessor references make a
missing or renamed vector a compile error, the shell gates pin style and file count, and the goldens show
every vector. That keeps one list of the eighteen names instead of three.

## Verification plan

Focused block → `--fast` → `--verify`, then manual review of the four goldens (glyph legibility at
20/24 dp, mark at 28/32/48 dp, sprig at 160/200 dp, nothing implying verification) and a
`git diff --stat` scope check. Record goldens only with the per-class record filters; verification never
rewrites a baseline. Results are in "Feature evidence" and the acceptance record.

## Feature evidence

- **Assets.** Eighteen stroke-only mask XMLs (`#000000` stroke, `#00000000` fill); the wizard
  placeholder is untouched.
- **Wrappers.** `ManijeroIcon` (required `contentDescription`, `painterResource`, exact size,
  `LocalContentColor`), `ManijeroBrandMark` (`primary`, 32 dp default), `ManijeroOliveBranch`
  (`primaryContainer` halo in Compose, `onPrimaryContainer` sprig, 180 dp default); all `internal`,
  stateless, with light/dark previews.
- **Board and captures.** Test-only board with a four-column grid (eight columns clipped
  `ic_chevron_down`'s label), captured at 900×1200 dp; only the four new PNGs were recorded.
- **Checks.** Focused block exit 0 (16 screenshot tests: 10 Desktop, 6 Android; gates silent);
  `--fast` exit 0 (204 shared tests including the four inventory tests later removed, contract
  examples, 618 backend tests, 9 offline checks); `--verify` exit 0 (190 Android host tests, APK and
  Desktop builds); parsed results show zero failures.
- **Visual judgement.** All sixteen glyphs read at 24 dp, and `ic_search`/`ic_clear` stay distinct at
  20 dp (weakest: `ic_lands` reads as layers, the retry arrowhead is small). The mark reads as an open
  ring holding a leaf; at 28 dp the leaf collapses to a blob. The sprig reads at 160/200 dp without
  clipping. Limit: host renders only (Desktop macOS-font-pinned; Robolectric SDK 35), density 1, font
  scale 1, `es-ES`; no device, iOS, screen-reader, touch, or real-screen claim.
- **Scope.** No screen, theme, string, Gradle, backend, contract, or `design-references/` change; no new
  dependency; the twelve existing goldens are byte-identical.

## Notes and deviations

- The Android board class pins `es-rES-w900dp-h1200dp-mdpi`; the app scenes keep `w360dp-h800dp`.
- The focused block's last gate was corrected from `grep … && { exit 1; }` to
  `if grep …; then exit 1; fi`, because the old form made `--feature` unable to exit 0.
- No iOS target was compiled; "all targets decode these vectors" rests on the documented Compose XML
  subset.
- Post-acceptance, the board moved from `commonMain` to `commonTest` and the inventory test was removed;
  the decisions and re-verification are in the acceptance record.

## Validator checklist

- [ ] 18 named vectors exist; placeholder untouched; 24 dp grid, 2 dp round stroke, outline only,
      2–22 dp safe area.
- [ ] Only `#000000`/`#00000000`; no tint, gradient, `aapt:attr`, clip path, or external reference.
- [ ] Wrappers match the contract: required description on the icon, none on mark/illustration, fixed
      theme roles, halo in Compose, 160–200 dp.
- [ ] Board is test-only, unreferenced by shipped code, labels absent from `strings.xml`; wrappers stay
      in `commonMain`.
- [ ] Four new goldens recorded deliberately; twelve existing PNGs unchanged.
- [ ] No screen/theme/string/Gradle/backend/contract change, no dependency; durable rules recorded.
