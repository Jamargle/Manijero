# Screenshot regression (Desktop and Android)

Two screenshot suites cover the shared Compose UI in `shared/src/commonMain`:

| Platform | Renderer | Goldens | Captures |
|---|---|---|---|
| Desktop | Compose Desktop on the JVM target | `shared/src/jvmTest/screenshots/` | 4 app scenes × 2 widths + board in 2 appearances = 10 |
| Android | Robolectric on the host JVM (no emulator/device) | `shared/src/androidHostTest/screenshots/` | 4 app scenes at 360×800 dp + board at 900×1200 dp in 2 appearances = 6 |

The app scenes are the same on both platforms and use the shared, code-owned fixtures in
`shared/src/commonTest/kotlin/com/jamarglex/manijero/screenshots/ScreenshotFixtures.kt`: chat home
idle (light), chat answered with a source card (dark), saved-lands list with two lands (light), and
saved-lands empty state (dark). A fifth subject is the review-only `BrandVectorBoard` owned by
`brand_vectors`, captured in light and dark so the eighteen brand vectors are rendered by the theme;
it is not a product screen and makes no accessibility claim. The goldens are separate per platform
because Desktop and Android rasterise text, fonts, and controls differently.

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

- density 1, font scale 1, layout direction LTR, JVM locale pinned to `es-ES` for each test;
- appearance is the explicit `ManijeroTheme(darkTheme = ...)` argument, never the host setting;
- fixtures are code-owned: no clock, network, disk, backend, or land store;
- comparison: Roborazzi `SimpleImageComparator(maxDistance = 0.007)` with
  `changeThreshold = 0.001F` (0.1% of the frame).

Android:

- Robolectric SDK 35; the app scenes use qualifiers `es-rES-w360dp-h800dp-mdpi` (360×800 dp phone
  viewport), and the review-only board class pins `es-rES-w900dp-h1200dp-mdpi` (900×1200 dp) per its
  spec so both hosts show the same composition;
- the same explicit `ManijeroTheme(darkTheme = ...)`, density 1, and font scale 1;
- the same fixtures and the same explicit `changeThreshold = 0.001F`.

A real regression (moved control, changed colour, wrapped line) covers far more than the threshold;
it exists only for sub-visible antialiasing noise between same-host renders. Do not widen it to hide
a meaningful change.

## Adding a capture

1. Add a test to the platform's test class next to the existing captures. Keep chat states in the
   chat class and lands states in the lands class, and reuse `ScreenshotFixtures`. A review-only
   board that is neither a chat nor a lands scene gets its own dedicated class on each platform.
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
- **Only the listed frames are gated.** Other screens, states, text sizes, locales, window sizes, and
  Android API levels are not covered.
