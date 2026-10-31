# Appendix — `ui_component_library`

Planning and verification record for [`ui_component_library.md`](../../specs/ui_component_library.md). The
authoritative acceptance record is
[`docs/validations/ui_component_library.md`](../../validations/ui_component_library.md); this appendix
holds the repository research, component decisions, plan, evidence, and validator checklist.

## Repository research

Inspected 2026-10-25 in `feature/ui_component_library` (base `main` @ `ec8e0c6`); planning changed no
source file.

- **Toolchain.** Compose Multiplatform `1.12.1`, Material 3 `1.12.0-alpha03`, Kotlin `2.4.20`,
  AGP `9.4.1` (recorded by the accepted `brand_vectors` appendix). `compose.foundation`,
  `compose.material3`, `compose.components.resources`, `compose.ui` and `uiToolingPreview` are already
  `commonMain` dependencies, so the layer needs no Gradle change.
- **Existing design package.** `design/` holds only the three accepted wrappers:
  `ManijeroIcon` (required explicit description, 24/20 dp, `LocalContentColor`), `ManijeroBrandMark`
  (`primary`, 32 dp default) and `ManijeroOliveBranch` (`primaryContainer` halo, decorative). All are
  `internal`, stateless, preview-backed, and own no padding, target or click handling.
- **Tokens.** `theme/ManijeroTokens.kt` provides `ManijeroShapes` (4/12/16/24 dp),
  `ManijeroSpacing` (6/12/24/32/48 plus 4/8/16), `ManijeroIconSize` (20/24/32) and `ManijeroLayout`
  (720 dp content cap, 24/40 dp screen padding, 32 dp vertical padding, 1 dp border, 48 dp minimum
  target). `ManijeroColors.kt` exposes all Material roles plus semantic `caution`, `cautionSurface`,
  `onCaution`, `primaryStrong`, `ecoContainer`, `onEcoContainer`. `ManijeroTheme` is `internal` and
  takes an explicit `darkTheme` for previews and tests.
- **Repeated patterns today.** Each screen paints `Surface(background)` + a scrolling `Column` +
  `padding(horizontal = 24.dp, vertical = 32.dp)` + a `widthIn(max = 720.dp)` child; cards are
  ad-hoc `Surface` + `RoundedCornerShape(16.dp)` + a 1 dp `outlineVariant` border; confirmations are
  plain `Text`; `AddLandScreen` owns an `internal ChoiceGroup`/`ChoiceItem` radio list and the chat
  owns its own failure/abstention surfaces. This feature supplies shared replacements but does not
  migrate those call sites.
- **Strings.** One default `values/strings.xml`, Spanish, generated accessors `internal` to `shared`.
  Components must take `String` parameters; the gallery's labels are review identifiers and must not
  be added there.
- **Icons.** Sixteen accepted `ic_*` vectors plus `brand_mark.xml` and `olive_branch.xml`. There is no
  shield glyph. `brand_vectors` states that a screen needing another glyph extends the inventory in a
  later feature, and its board goldens are committed.
- **Screenshot harness.** Desktop Compose (`jvmTest`) and Robolectric SDK 35 (`androidHostTest`) suites
  with 10 and 6 goldens, pinned density/font scale/`es-ES`, read-only verify tasks, explicit record
  tasks, and a 0.1 % change threshold. The suites are excluded from `:shared:jvmTest`,
  `:shared:testAndroidHostTest`, `--fast` and the Linux CI gate. A review-only board is an accepted
  pattern (`BrandVectorBoard`), captured by a dedicated class per platform.
- **Test capability.** `commonTest` has `kotlin-test` only; there is no Compose UI test dependency
  there and the plan forbids adding one. Component behavior therefore rests on compile, previews,
  screenshot goldens and review, for the pure helpers as much as for the composables.
  `androidHostTest` already has `compose.ui.test.junit4`, so the Android gallery class can use the
  existing rule.
- **Docs.** `DESIGN.md` already records the palette, chip pairs, icon rules and layout intent;
  `CONSTRAINTS.md` ends at the brand-vector rules; `docs/screenshot-regression.md` states the current
  capture table (10 Desktop / 6 Android) and the "add a capture" procedure.
- **Selection.** `./scripts/select-feature.sh --next` reported `NEXT_FEATURE=ui_component_library`,
  `NEXT_ROLE=planner`, `NEXT_SPEC=-`; `brand_vectors` is `accepted`, so the dependency gate passes.
  Discovery is already complete (approved UI refresh plan and `DESIGN.md`), so `build-brief` was not
  re-run: re-opening product discovery would contradict the approved plan and add no missing decision.

## Component decisions

1. **One package, two files with navigation.** All components stay in package
   `com.jamarglex.manijero.design`; the two navigation files live in `design/navigation/` for
   readability but keep that package, so `internal` access and imports stay simple.
2. **No strings owned by the layer.** Every visible text is a `String` parameter. This keeps the
   component API domain-free and makes the later screen features own their Spanish copy review.
3. **No new glyph.** Plan §3.4 proposes a shield for the top-bar privacy action, but the inventory is
   pinned at sixteen accepted vectors and its board goldens are committed. Using `ic_info` with the
   caller's visible label (wide) or accessible description (compact) avoids re-opening
   `brand_vectors` goldens; a shield becomes a later, visually reviewed asset change. The accessible
   name, not the glyph, carries the meaning today.
4. **Chips are non-interactive.** The catalogue mentions a 48 dp target only when a chip is
   interactive; no accepted screen needs an interactive chip, so keeping one non-interactive component
   avoids an unused interaction API. A later feature can add an overload with its own spec.
5. **Choice grouping is the caller's job.** `ManijeroChoiceCard` owns the row semantics
   (`selectable`, `Role.RadioButton`, description, error border) but not the group semantics. The
   consuming form wraps the options in `Modifier.selectableGroup()`, which keeps the component a single
   option rather than a hidden group container.
6. **Honesty is encoded in the API.** `ManijeroStatCard.supporting` is required, so a stat card cannot
   render a value without stating what it counts. `ManijeroMeasureField` has no parser and
   `ManijeroSearchField` performs no filtering: validation, accent folding, totals and formatting stay
   in the owning data/domain feature.
7. **Bars do not own insets.** `ManijeroBottomNavigation` and `ManijeroNavigationRail` pin
   `WindowInsets(0)`; the future `Scaffold` in `app_chrome_navigation` is the single inset owner.
8. **Adaptive decisions are inside the component.** `ManijeroScreen` chooses 24/40 dp from
   `BoxWithConstraints`; the top bar chooses icon-only vs icon+label at the 840 dp breakpoint. Callers
   never pass a `wide` flag, so a screen cannot disagree with its own width.
9. **Gallery is review-only and parameterless.** `ComponentGallery()` renders every component and
   state stacked; the narrow capture simply renders the same tree at 360 dp with font scale 2, so the
   gallery has no test-only configuration that shipped code could accidentally use. Capture
   viewports are wide 1200×3000 dp and narrow 360×5400 dp (raised from the planned 4000 dp after
   measuring the 2× content; see the evidence); the narrow height is chosen so no section is
   clipped.
10. **Eight new goldens, no re-recording.** Four per host: light/dark wide and light/dark narrow
    large-text. The ten existing Desktop and six existing Android PNGs must be byte-identical because
    no screen or vector changes.

## Implementation plan

Ordered; each task ends with the stated check.

| # | Work | Done when |
|---|---|---|
| T1 | Add `ManijeroScreen` with `screenHorizontalPadding` and light/dark/2× previews | Previews render; 839/840 dp boundary behaves |
| T2 | Add `ManijeroCard`, `ManijeroSectionHeader`, `ManijeroStatCard`, `ManijeroEmptyState` with every tone/variant and previews | All tones visible; no click handling; required supporting caption |
| T3 | Add `ManijeroCallout` (four tones, icon+text, polite text node, action slot) and `ManijeroAttributeChip` (four tones) | Caution/danger pairs match `DESIGN.md`; action stays its own node |
| T4 | Add `ManijeroChoiceCard`, `ManijeroSearchField`, `ManijeroDropdownField`, `ManijeroMeasureField` with previews and 48 dp targets | Radio role, clear button, exposed menu and error state rendered |
| T5 | Add `ManijeroTopAppBar`, `ManijeroBottomNavigation`, `ManijeroNavigationRail`, `ManijeroDestination`, `selectedDestinationIndex` | Compact/wide action variants; labels always visible; out-of-range index safe |
| T6 | Add `ComponentGallery` in `commonTest` and the two screenshot classes | Eight goldens recorded; existing sixteen PNGs unchanged |
| T7 | Review every new golden image (light/dark, 2× text, no clipping, no colour-only state) | Reviewed images match the spec |
| T8 | Update `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md` | Docs match the shipped layer and capture table |
| T9 | Run focused block, `--fast`, `--verify`; record evidence; validate | All green; honest limits recorded |

## Verification plan

1. Focused block: `./scripts/init.sh --feature ui_component_library` (both screenshot suites and
   the inventory/colour/domain/screen/golden/dependency gates).
2. `./scripts/init.sh --fast` for the shared host tests, contract examples, backend suite and offline
   evaluators, confirming nothing outside `shared` moved.
3. `./scripts/init.sh --verify` for the Android host tests and both app builds, confirming the layer
   compiles into every target that ships it.
4. Manual gallery review of the eight new images; record concrete observations (weakest component,
   wrapping behaviour, whether the top-bar action reads as privacy).
5. Scope check: `git diff --stat` and `git status --short` must show only the files listed in the
   contract; any screen, vector, string or Gradle change fails the review.
6. Record goldens only with the explicit record tasks and only the four new names per host; never
   re-record the existing app or brand board captures.

## Evidence to capture

- Focused block, `--fast` and `--verify` results with pass/fail counts and exit status.
- `git diff --stat` and a statement that the ten + six existing goldens are unchanged.
- The eight new goldens with viewport, font scale and appearance.
- Visual review notes: weakest component at 2× text, any wrapping/truncation, whether the top-bar
  action is understandable, whether cauciones/danger remain distinguishable without colour.
- Accessibility notes: 48 dp targets, accessible names on the search clear button and top-bar action,
  radio role and description on choice cards, labels always visible on both navigation bars.
- Explicit limits: host renders only (Desktop macOS-font-pinned, Robolectric SDK 35), density 1,
  no device, iOS, screen-reader, usability or user-comprehension claim; no screen adopts the layer.
- Any deviation discovered during implementation, with its reason.

## Feature evidence

Implemented 2026-10-25 in `feature/ui_component_library` (worktree
`ui_component_library`). No commit, push, or acceptance record was made: the feature is
`passing`, ready for independent validation.

### What shipped

- Nine component files under `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/`
  (`ManijeroScreen.kt`, `ManijeroCard.kt`, `ManijeroSectionHeader.kt`, `ManijeroCallout.kt`,
  `ManijeroStatCard.kt`, `ManijeroEmptyState.kt`, `ManijeroChip.kt`, `ManijeroChoiceCard.kt`,
  `ManijeroFields.kt`) and two navigation files under `design/navigation/`
  (`ManijeroTopAppBar.kt`, `ManijeroNavigation.kt`), all `internal` in package
  `com.jamarglex.manijero.design`: the fourteen named declarations, their tone enums, and the two
  pure helpers (`screenHorizontalPadding`, `selectedDestinationIndex`).
- Review-only `commonTest/design/ComponentGallery.kt`.
- `jvmTest/.../screenshots/ComponentGalleryScreenshotsTest.kt`,
  `androidHostTest/.../screenshots/ComponentGalleryAndroidScreenshotsTest.kt`, and eight new PNGs
  (four per host).
- Durable documentation: `DESIGN.md` ("Shared component layer"), `CONSTRAINTS.md` ("Shared
  component layer"), `docs/screenshot-regression.md` (capture table, gallery viewports, limits).
- No screen, `App.kt`, `theme/`, vector, `strings.xml`, Gradle, backend, contract, knowledge or
  design-reference change. No new dependency or asset.

### Verification results

| # | Command | Result |
|---|---|---|
| 1 | `./gradlew :shared:recordDesktopScreenshots --tests "...ComponentGalleryScreenshotsTest"` | PASS — only the four Desktop gallery names were written |
| 2 | `./gradlew :shared:recordAndroidScreenshots --tests "...ComponentGalleryAndroidScreenshotsTest"` | PASS — only the four Android gallery names were written |
| 3 | `./gradlew :shared:verifyScreenshots` | PASS — BUILD SUCCESSFUL; 14 Desktop (4 gallery + 10 existing) and 10 Android (4 gallery + 6 existing) captures |
| 4 | `./scripts/init.sh --feature ui_component_library` | exit 0 — focused gate, both screenshot suites, and the inventory/colour/domain/screen/golden/material-icons gates |
| 5 | `./scripts/init.sh --fast` | exit 0 — "All 9 offline checks passed"; backend pytest skipped because pytest is not installed (documented harness behaviour) |
| 6 | `./scripts/init.sh --verify` | exit 0 — BUILD SUCCESSFUL for `:shared:testAndroidHostTest`, `:androidApp:assembleDebug` and `:desktopApp:build` |

### New goldens

| Golden | Host | Viewport | Font scale | Appearance |
|---|---|---|---|---|
| `component_gallery_light` | Desktop, Android | 1200×3000 dp | 1 | light |
| `component_gallery_dark` | Desktop, Android | 1200×3000 dp | 1 | dark |
| `component_gallery_narrow_large_text_light` | Desktop, Android | 360×5400 dp | 2 | light |
| `component_gallery_narrow_large_text_dark` | Desktop, Android | 360×5400 dp | 2 | dark |

### Scope and unchanged goldens

`git status --short` after verification lists only the new design/test/golden files, the two untracked
spec files (`docs/specs/ui_component_library.md` and its appendix, created by planning and not
committed in this worktree), and the four tracked files named above (`DESIGN.md`, `CONSTRAINTS.md`,
`docs/screenshot-regression.md`, `feature_list.json`). `git diff --stat` before the doc edits was
empty. No tracked screenshot PNG is modified: the ten Desktop and six Android app/brand goldens are
byte-identical, and the record tasks were filtered to the new gallery classes with `--tests`.

### Visual review notes

- **Wide, light and dark.** All fourteen components and every tone render. Content ends with visible
  bottom headroom inside 3000 dp on both hosts. The top bar shows the wide action as `ic_info` plus
  the visible "Privacidad" label. Danger and Confirmation callouts keep their text and icon on the
  filled pairs; the dropdown and measure fields show their supporting/error text.
- **Narrow, 2× text.** No section is clipped at 360×5400 dp on either host. The weakest point is the
  compact bottom navigation: at one third of 360 dp and 2× text, "Asistente" breaks mid-word
  ("Asis-/tente") and "Mis terrenos" wraps to two lines. Both labels stay visible, the selected item
  keeps Material's indicator pill plus a heavier label, and no target shrinks; no truncation or
  clipping was chosen to hide the wrap.
- **Without colour.** Callouts keep a distinct icon plus text (info, warning, check), chips keep
  their labels, the error fields keep visible error copy, and the radio choice keeps the radio
  indicator and the error border with the caller's visible "Elige una opción para continuar."
- **Top-bar action.** The meaning reads from the accessible name — visible "Privacidad" on wide and
  the caller's description on compact — not from `ic_info`; the icon is not a shield and makes no
  security/verification claim.
- **Not captured.** The exposed dropdown menu's open state requires interaction and is not in the
  static gallery; the gallery is a review board, not a product screen.

### Accessibility notes

- 48 dp targets: choice card, search clear button, top-bar action and both navigation bars.
- Accessible names: search clear description, top-bar privacy name, choice-card merged option
  description and radio role; navigation labels always visible and the selected item marked by
  shape/weight as well as colour.
- Material's focus indication and minimum interactive size are not overridden. No screen-reader,
  focus-order or keyboard walkthrough was run; none is claimed.

### Deviations and limits

- **Contract file count.** The contract prose said "eleven component files plus the two navigation
  files"; its own table lists nine component files plus two navigation files. Nine were implemented
  and the prose was corrected to "nine" in the same change.
- **Narrow capture height.** The appendix plan said 360×4000 dp; the measured 2× content reached
  about 5190 px on Desktop and 4530 px on Android, so the review viewport was raised to 360×5400 dp.
  The contract only required "tall enough that no section is clipped"; the appendix decision was
  updated to the shipped value.
- **Top-bar guard.** Scenario 13 says the action is omitted when its callback is null. The
  implementation also omits it when the caller supplies no name at all (`privacyDescription ?:
  privacyLabel` is null), because an unnamed interactive control would violate the accessibility
  baseline.
- **Choice-card error cue.** `ManijeroChoiceCard` owns only the `error` border; the caller owns the
  visible error text (as Material text fields do). The gallery now renders that text under the error
  option so the review image demonstrates the non-colour cue.
- **Deprecated menu anchor.** `ManijeroDropdownField` uses `ExposedDropdownMenuAnchorType` rather
  than the deprecated `MenuAnchorType`; behaviour and API surface are unchanged.
- **Helper test removal.** After acceptance, the owner asked to delete `ManijeroComponentsTest`
  because the gallery renders and the screenshot suites were judged to cover the same ground. It was
  removed, and the spec, this appendix, the acceptance record, `PROGRESS.md` and the session log were
  corrected: no test now asserts the 839/840 dp padding boundary or invalid selected indices, and
  those remain review-only checks.
- **Honest limits.** Host renders only: Desktop goldens are macOS-font-pinned and Android goldens are
  Robolectric SDK 35; density 1, `es-ES`, one 2× text size. No device, emulator, iOS, screen-reader,
  focus/keyboard, usability or user-comprehension claim. No screen adopts the layer yet. The
  backend pytest tier was not run because pytest is absent from the available interpreters.

### Validator commands

```sh
./gradlew :shared:verifyScreenshots
./scripts/init.sh --feature ui_component_library
./scripts/init.sh --fast
./scripts/init.sh --verify
git status --short
git diff --stat
```


## Validator checklist

- [x] The fourteen named declarations exist under `design/`, are `internal`, and match the contract
      signatures and file list.
- [x] No existing screen, `App.kt`, vector, `strings.xml`, `theme/`, Gradle file, backend, contract or
      knowledge file changed; existing sixteen goldens unchanged.
- [x] Every component takes its text and values as parameters; the layer imports no domain package and
      no `Res.string`.
- [x] No raw colour, new token, dependency or asset; tones use the accepted role pairs and are never
      colour-only.
- [x] Cards, callouts, chips, stat cards, empty state, fields and navigation match the documented
      variants and states.
- [x] 48 dp interactive targets, accessible names, radio role/description, visible labels on both bars,
      Material focus indication retained.
- [x] The two pure helpers have no dedicated test class (removed at the owner's request); their
      boundary values are reviewed in source, not asserted by a test or by a fixed-viewport render.
- [x] Exactly eight new gallery goldens, reviewed; both screenshot suites pass; record tasks were used
      explicitly and nothing else was re-recorded.
- [x] `DESIGN.md`, `CONSTRAINTS.md` and `docs/screenshot-regression.md` are updated and honest;
      `ARCHITECTURE.md`/`AGENTS.md` are correctly untouched.
- [x] Evidence includes command results, scope diff, visual review and explicit limits; no claim beyond
      host renders.

### Validator record

Independent validation ran on 2026-10-25 against base `ec8e0c6` in this worktree and returned
**accept**, with no code, test, golden or documentation repair required. It re-read all eleven
component sources, the gallery and the two screenshot classes, re-ran the focused block, `--fast` and `--verify`, forced
reruns of the shared host test and golden suites, and confirmed the ten prior app renders and four
prior board renders are byte-identical. The record is
[`docs/validations/ui_component_library.md`](../../validations/ui_component_library.md). Known limit
carried to `app_chrome_navigation`: at 2× text the compact bottom-navigation labels wrap mid-word
while remaining fully visible with indicator and bolder selected label.
