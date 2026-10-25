# Screenshot regression (Desktop and Android)

Two screenshot suites cover the shared Compose UI in `shared/src/commonMain`:

| Platform | Renderer | Goldens | Captures |
|---|---|---|---|
| Desktop | Compose Desktop on the JVM target | `shared/src/jvmTest/screenshots/` | 6 chat states (idle light, answered dark, abstention dark, clarification light; idle and answered also at 360×800) + 6 lands states (list light and empty dark, each at 900×1200 and 360×800, plus search no results and one match at 900×1000) + board in 2 appearances + component gallery in 4 configurations + app shell in 4 configurations = 22 |
| Android | Compose UI rendered by Robolectric on the JVM (no emulator/device) | `shared/src/androidHostTest/screenshots/` | 4 chat states at 360×800 dp + 4 lands states (list light and empty dark at 360×800, search no results and one match at 900×1000) + board at 900×1200 dp in 2 appearances + component gallery in 4 configurations + app shell in 4 configurations = 18 |

The land-screen refresh changes the populated-list row treatment; if its list or filtered-list
captures differ, only those land captures may be recorded after visual inspection. Shell and chat
captures are not part of this feature and must remain untouched, even if their host baselines fail.

The app scenes are the same on both platforms and use the shared, code-owned fixtures in
`shared/src/commonTest/kotlin/com/jamarglex/manijero/screenshots/ScreenshotFixtures.kt`: chat idle
(light), chat answered with a source card (dark), chat abstention with its state label (dark), chat
clarification chooser over two lands (light), land list with two lands (light), and land empty
(dark). Two saved-lands search states are captured once per platform at
900×1000 dp instead of the phone width: no results, and one match of two saved lands (both light). The
wide viewport is used because a phone frame would push the no-results panel below the fold, and because
the filtered frame must show the scope caption, the three `x de y` captions and the single matching row
together. A fifth subject is the review-only `BrandVectorBoard`, a `commonTest`
composable owned by `brand_vectors` and captured light/dark so all eighteen vectors are rendered by the
theme; it is not a product screen. A sixth subject is the review-only `ComponentGallery`, a
`commonTest` composable owned by `ui_component_library` that renders every shared component and tone:
light/dark at 1200×3000 dp (font scale 1) and light/dark at 360×5400 dp with font scale 2. The
height was raised from the planned 4000 dp because the measured 2× content reached about 5190 px on
Desktop and 4530 px on Android; 5400 dp leaves headroom so no section clips. It is a review viewport,
not a screen size. Neither review board is a product screen. The goldens are separate per
platform because Desktop and Android rasterise text, fonts, and controls differently.

## Verify before committing or pushing

```sh
./gradlew :shared:verifyScreenshots
```

This runs both suites in read-only mode. It never rewrites a golden. The equivalent through the
repository harness is `./scripts/init.sh --feature screenshot_regression_tests`.

To run one platform only:

```sh
./gradlew :shared:verifyDesktopScreenshots   # no Android SDK needed
./gradlew :shared:verifyAndroidScreenshots   # Robolectric; needs an Android SDK to build, not a device
```

For a feature whose suite shares the aggregate tasks with unrelated screens, a filtered verification
can isolate that feature without weakening the normal gate, for example:

```sh
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.LandListScreenshotsTest' \
  :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.LandListAndroidScreenshotsTest'
```

On a failure, inspect the artifacts:

- `shared/build/reports/screenshot-regression/` — Desktop `_actual.png`, `_compare.png`, results.
- `shared/build/reports/screenshot-regression-android/` — Android `_actual.png`, `_compare.png`, results.
- `shared/build/reports/tests/<task>/index.html` — the JUnit report with the assertion.

A `_compare.png` shows baseline, diff heat map, and current render side by side. A failure means the
UI changed beyond the documented threshold. **Do not re-record to make a red test green.** First
decide from the compare image whether the change was intended.

## Record after an intentional, reviewed change

Recording is a separate, explicit action; normal verification can never record.

```sh
./gradlew :shared:recordScreenshots            # both platforms
./gradlew :shared:recordDesktopScreenshots     # Desktop only
./gradlew :shared:recordAndroidScreenshots     # Android only
```

Then, before committing:

1. Run `git status` / `git diff --stat` and confirm only the captures you expected changed.
2. Open **each** changed PNG at full size and confirm the new render is the intended design: right
   screen, right appearance, right Spanish copy, no clipped or overlapping controls, no blank or
   half-painted frame.
3. Where a capture also failed verification, compare `_compare.png` with the new PNG and confirm the
   difference is the intended one.
4. Commit the PNGs together with the code change that caused them, and say in the commit message
   that the images were reviewed by a human.
5. Re-run `./gradlew :shared:verifyScreenshots` from a clean state and confirm it passes.

If the render is unexpected, fix the code instead of recording; a baseline refresh is never a way to
hide a regression.

## Fixed render conditions and threshold

Desktop:

- density 1, font scale 1, layout direction LTR, JVM locale pinned to `es-ES` for each test; the
  gallery's two large-text captures nest `Density(1f, fontScale = 2f)` around the gallery only, and
  the shell large-text capture uses the same 2× density for its frame only;
- appearance is the `darkTheme` argument on `ManijeroTheme`, never the host setting;
- fixtures are code-owned: no clock, network, disk, backend, or land store;
- comparison: Roborazzi `SimpleImageComparator(maxDistance = 0.007)` with
  `changeThreshold = 0.001F` (0.1% of the frame).

Android:

- Robolectric SDK 35; app scenes use `es-rES-w360dp-h800dp-mdpi` (360×800 dp), the board class pins
  `es-rES-w900dp-h1200dp-mdpi` (900×1200 dp), and the component-gallery class sets
  `es-rES-w1200dp-h3000dp-mdpi` for the wide pair and `es-rES-w360dp-h5400dp-mdpi` for the 2× pair,
  so both hosts show the same compositions. The shell class uses the same 360×800 dp compact
  viewport and overrides the two rail captures per method with `es-rES-w900dp-h1000dp-mdpi`, which is
  also the per-method qualifier of the lands class's `land_list_search_no_results` and
  `land_list_search_filtered` captures; its
  large-text capture nests `Density(1f, fontScale = 2f)` around the shell frame;
- the same explicit `ManijeroTheme(darkTheme = ...)`, density 1, and font scale 1, with the gallery's
  large-text captures nesting `Density(1f, fontScale = 2f)` around the gallery only;
- the same fixtures and the same explicit `changeThreshold = 0.001F`.

A real regression (moved control, changed colour, wrapped line) covers far more than the threshold;
it exists only for sub-visible antialiasing noise between same-host renders. Do not widen it to hide
a meaningful change.

## Adding a capture

1. Add a test to the platform's test class next to the existing captures. Keep chat states in the
   chat class and lands states in the lands class, and reuse `ScreenshotFixtures`. A review-only
   board that is neither a chat nor a lands scene gets its own dedicated class on each platform;
   the shell's four frames live in `AppShellScreenshotsTest` on each host.
2. Record with the explicit task, inspect the new image, and commit it with the test.
3. Update this document's capture table and the feature appendix evidence.

## Limitations

- **Desktop goldens are host-font-pinned.** Compose Desktop resolves fonts from the operating
  system; the committed Desktop images were recorded on macOS. A different OS must record and review
  its own Desktop baselines.
- **Android goldens are host-rendered by Robolectric**, pinned to SDK 35 and Robolectric 4.17. They
  prove Compose/Android rendering on the host JVM, not behavior on a real device, emulator, or a
  different Android API level.
- **Robolectric needs one online download** of its `android-all` SDK jar the first time it runs for a
  pinned SDK (cached afterwards by Gradle/Robolectric).
- **No CI enforcement.** The existing CI gate runs on Linux and does not run these suites. These are
  local, developer-invoked gates.
- **No accessibility, usability, legal, or product-behavior proof.** A pass only means the selected
  Desktop and Android frames match the committed images within the threshold.
- **The component gallery is not a product screen.** Its pass proves the shared layer renders on both
  hosts in two appearances and at one enlarged text size; it does not prove any screen, interaction,
  screen-reader output, device rendering, or usability.
- **Only the listed frames are gated.** The gallery covers one 2× text size in one locale; other
  screens, states, intermediate text sizes, locales, window sizes, and Android API levels are not
  covered.
