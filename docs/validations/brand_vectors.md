# Validation: `brand_vectors`

**Verdict: accept** — 2026-10-25 (second pass; first pass returned `revise` for documentation only)

Independent validation of the uncommitted implementation against
[`docs/specs/brand_vectors.md`](../specs/brand_vectors.md), the appendix checklist in
[`brand_vectors.appendix.md`](../specs/brand_vectors.appendix.md), `DESIGN.md`, `CONSTRAINTS.md`, and
`PROGRESS.md`, in the `feature/brand_vectors` worktree (base `main` @ `8b3f680`).

Verdict trail: pass 1 `revise` on one documentation-consistency finding (M1: the harness doc
`docs/screenshot-regression.md` still stated 8 Desktop / 4 Android goldens and a single Android
viewport) plus four low-severity doc/comment nits (L1–L4) → implementer repair pass → pass 2 `accept`.
No code, asset, test behaviour, Gradle, theme, string, backend, contract, or golden change was required
or made by the repair.

## What was checked

- **Inventory and geometry (independent parse, not the shell gates alone).** Exactly eighteen vectors
  under `shared/src/commonMain/composeResources/drawable/`: `brand_mark.xml` (32×32) and
  `olive_branch.xml` (96×96) on their specified viewports, plus the sixteen `ic_*.xml` named by the
  contract. Each icon parses as a 24 dp vector on a 24×24 viewport with one or two paths, all six
  stroke attributes present on every path (stroke 2, round caps, round joins), no filled shape, and
  painted extent inside the 2–22 dp safe area (tightest: `ic_warning` x 2.30–21.70, `ic_retry`
  y 3.66–20.90). The wizard placeholder `compose-multiplatform.xml` is untouched and excluded from
  the inventory (19 files in the directory, 18 in the inventory).
- **Colour separation.** Only `#000000` (28 occurrences) and `#00000000` (28) appear as colour
  literals across the eighteen files; no `android:tint`, gradient, `aapt:attr` block, clip path,
  `@android:` reference, or external resource reference. Every rendered colour comes from a wrapper.
- **Wrapper contract.** `ManijeroIcon` loads through `painterResource`, requires an explicit
  `contentDescription` (no default), draws at exactly the requested `size` and tints from
  `LocalContentColor`. `ManijeroBrandMark` and `ManijeroOliveBranch` expose no description or colour
  parameter and add no semantics node; the mark uses `primary`, the illustration paints its halo in
  Compose (`primaryContainer` + `CircleShape`) with the sprig in `onPrimaryContainer`. All wrappers
  are `internal`, stateless, in `com.jamarglex.manijero.design`, with light/dark previews.
- **No adoption.** A reference grep found no screen, `App.kt`, theme, or string reference to the
  `design` package; only the two screenshot classes import `BrandVectorBoard`. The board's labels are
  review identifiers and do not exist in `composeResources/values/strings.xml`.
- **Test quality.** `BrandVectorSetTest` names all eighteen resources through the generated accessors
  (so a missing or renamed file fails to compile), cross-checks the drawable registry, asserts
  pairwise distinctness, and pins the wizard placeholder as excluded — not a tautology. 4 tests ran.
- **Goldens.** Four new board PNGs, all 900×1200, four distinct hashes, light ≠ dark:

  ```
  a66ad9cf710e575014649198fc405d6775f4bf9622c7cc0086c56f4c3d6d1a0d  jvmTest/.../brand_vector_board_dark.png
  4ba8ea3f7cbf5b14918995ec8fa2c83624e8567b22472ff6302db79ea8e3f415  jvmTest/.../brand_vector_board_light.png
  5fdd9ff7710b3aded7fa47dc7681439285a99f2eea66bbb26506fb49a8184c58  androidHostTest/.../brand_vector_board_dark.png
  0d59c6fd487c3fe9562a5dda750468c39625e4f125b44160de458b531d08f873  androidHostTest/.../brand_vector_board_light.png
  ```

  `git diff --exit-code -- shared/src/jvmTest/screenshots shared/src/androidHostTest/screenshots`
  exited 0 before and after the full gate, and across the repair pass: the eight Desktop and four
  Android pre-existing goldens are byte-identical to `HEAD`. The four new images were recorded
  deliberately with per-class filters (`:shared:recordDesktopScreenshots --tests
  '*BrandVectorBoardScreenshotsTest'`, `:shared:recordAndroidScreenshots --tests
  '*BrandVectorBoardAndroidScreenshotsTest'`); the validator confirmed by hash and mtime that the
  repair pass and re-validation re-recorded nothing.
- **Scope.** `git status --porcelain` over `*.gradle.kts`, `gradle/`, `androidApp`, `desktopApp`,
  `theme/`, `strings.xml`, `App.kt`, `contracts/`, `backend/`, `knowledge/`, `design-references/`,
  `ARCHITECTURE.md`, and `AGENTS.md` was empty. No dependency or module was added; no
  `material-icons-*` entry exists in the catalog.
- **Visual review (host-rendered).** All four goldens opened at full size: sixteen glyphs legible at
  24 dp with `ic_search`/`ic_clear` distinct at 20 dp, the mark at 28/32/48 dp, the sprig inside its
  halo at 160/200 dp with no clipping, single colour, both appearances.

## Verification (independently run)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature brand_vectors` (pass 1, twice, and after the repair) | **exit 0** — `BrandVectorSetTest` 4 tests / 0 failures; `verifyScreenshots` green (10 Desktop + 6 Android screenshot tests); inventory/style/colour/dependency gates silent-pass |
| `./scripts/init.sh --verify` (pass 1 and after the repair) | **exit 0** — fast tier passed, "All 9 offline checks passed", `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` successful |
| `MANIJERO_PYTHON=…/Manijero/backend/.venv/bin/python ./scripts/init.sh --backend-tests` | **618 passed** — matches the appendix claim |
| Parsed `shared/build/test-results/jvmTest/*.xml` and `…/testAndroidHostTest/*.xml` | jvmTest **204 tests / 24 classes**, androidHostTest **190 tests / 20 classes**, 0 failures, 0 errors — matches the appendix |
| `git diff --exit-code -- shared/src/jvmTest/screenshots shared/src/androidHostTest/screenshots` (four runs) | **exit 0** every time — the twelve pre-existing PNGs never changed |
| `sips -g pixelWidth -g pixelHeight` on the four new PNGs | 900 × 1200 each, four distinct SHA-256 values |
| Inline `bash -euo pipefail -c` probes of the corrected `material-icons` gate | **exit 0** without a match, **exit 1** with one; the old `&&` form exited 1 in both cases (the documented defect). The `fillColor="#000000"` and `android:width="24dp"` gates still fail when violated |
| `git diff -- docs/specs/brand_vectors.md` | exactly three hunks: the corrected gate, and two rows recording that `docs/screenshot-regression.md` is part of this feature's delivered docs |

Not re-run: an iOS compile (not covered by any tier; the appendix records the same gap). No golden was
recorded or re-recorded by the validator.

## Findings

**Pass 1 — `revise`, documentation only:**

- **M1 (medium)** `docs/screenshot-regression.md` still declared 8 Desktop / 4 Android goldens, listed
  only the four app scenes, and presented `es-rES-w360dp-h800dp-mdpi` as *the* Android condition. It is
  the doc `AGENTS.md` routes harness questions to, and its own "Adding a capture" step requires
  updating it. **Fixed** in the repair pass (10/6 counts, the board as fifth subject, both Android
  qualifiers, the dedicated-class allowance) and recorded in the spec's expected-changes and
  documentation-impact tables.
- **L1 (low)** `CONSTRAINTS.md` cited a non-existent `shared_theme` feature. **Fixed** — now cites
  `design_token_refresh`.
- **L2 (low)** A stale "eight-column icon grid" comment in `BrandVectorBoardScreenshotsTest.kt`.
  **Fixed** to "four-column".
- **L3 (low)** `DESIGN.md` claimed the assets reuse `ManijeroShapes`; nothing does. **Fixed**.
- **L4 (low)** Stray double blank line in `DESIGN.md`. **Fixed.**

**Pass 2 — `accept`.** All five findings verified closed, nothing unrelated moved, focused tier and
full gate green, no golden re-recorded.

## Appendix validator checklist

All twelve items **PASS**: eighteen named vectors with the placeholder untouched; icon grid geometry
and safe area; no baked appearance colour or unsupported vector feature; `ManijeroIcon`'s required
content description, exact size, tint and loader; decorative mark and illustration with fixed theme
roles; halo in Compose with 160–200 dp working; review-only board and previews unreferenced by any
screen with labels outside `strings.xml`; non-tautological `BrandVectorSetTest`; four new goldens with
the twelve existing PNGs byte-identical; no screen/host/theme/string/Gradle/backend/contract/
`design-references/` change and no new dependency or module; durable rules recorded in `DESIGN.md` and
`CONSTRAINTS.md` with `ARCHITECTURE.md`/`AGENTS.md` untouched; evidence real and bounded.

## Contract correction carried into acceptance

The focused block's final gate originally read
`grep -q 'material-icons' … && { echo …; exit 1; }`, so it returned the *failure* status exactly when
the rule passed and `./scripts/init.sh --feature brand_vectors` could never exit 0. The orchestrator
corrected that single line to `if grep -q …; then …; exit 1; fi` before validation; the corrected form
was probed to fail when such a dependency exists, the block now exits 0 with every check passing, and
no other spec line, acceptance scenario, or contract requirement moved. It is recorded in the
appendix's "Notes and deviations".

## Honest limits carried forward

- The goldens are host renders only: Compose Desktop (macOS host-font-pinned) and Robolectric SDK 35
  on the host JVM, at density 1, font scale 1, LTR, pinned `es-ES`. The board is a review surface, not
  a screen; no device, emulator, iOS, screen-reader, touch-target, or real-screen legibility claim is
  made, and no screen adopts the assets in this feature.
- No iOS target was compiled, so "all targets decode these vectors" rests on the documented Compose
  Multiplatform XML subset, not an iOS build.
- Per-file geometry, colour, and unsupported-feature rules are enforced by the focused shell gates;
  `BrandVectorSetTest` runs in `commonTest` without file-system access, so it pins the inventory and
  registry rather than parsing XML.
- The four new goldens join the pending human owner sign-off, which now covers sixteen images (twelve
  app baselines + four board captures). The mechanism and this validator review exist;
  product-owner approval does not.
- Non-blocking polish left unapplied so the accepted tree stayed exactly as validated: in
  `docs/screenshot-regression.md`, the Android bullet about "the same fixtures and the same explicit
  `changeThreshold`" could be read as applying to the board class, which renders `BrandVectorBoard`
  and uses no fixtures.

## Security

No finding. Static Android-XML masks plus pure Compose wrappers: no network, storage, permissions,
personal or land data, logging, or dynamic content; no new dependency, module, or runtime path.
