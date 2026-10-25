# Shared UI screenshot goldens

These PNGs are the **expected images** for the shared Compose UI, rendered on the Compose Desktop
(JVM) target by `shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/`. They are reviewed
images, not build output: they are committed on purpose and must only change through the recording
procedure below.

The suite is split by screen: `ChatHomeScreenshotsTest` and `LandListScreenshotsTest` own their
captures, and `ScreenshotTestSupport` holds the shared determinism harness.

## Check the current UI against the baselines (read-only)

```sh
./gradlew :shared:verifyScreenshots
```

8 tests must pass. The task never rewrites these files. On a failure it leaves reviewable artifacts
under `shared/build/reports/screenshot-regression/`:

- `<capture>_actual.png` — what the current code rendered,
- `<capture>_compare.png` — baseline, diff heat map, and current render side by side,
- `results/*.json` — per-capture result (`unchanged` / `changed` / `added` / `removed`),
- `shared/build/reports/tests/verifyScreenshots/index.html` — the JUnit report with the assertion.

A failure means the shared UI changed beyond the documented threshold. **Do not re-record to make a
red test green.** First decide, from the compare image, whether the change was intended.

## Record new baselines after an intentional, reviewed change

Recording is a separate, explicit action; normal verification can never record.

```sh
./gradlew :shared:recordScreenshots
```

Then, before committing:

1. Open `git status` / `git diff --stat` and confirm only the captures you expected changed.
2. Open **each** changed PNG at full size and confirm the new render is the intended design: right
   screen, right appearance, right Spanish copy, no clipped or overlapping controls, no blank or
   half-painted frame.
3. When a capture also failed verification beforehand, compare `_compare.png` with the new PNG and
   confirm the difference is the intended one.
4. Commit the PNGs together with the code change that caused them, and say in the commit/message
   that the images were reviewed by a human.
5. Re-run `./gradlew :shared:verifyScreenshots` from a clean state and confirm it passes.

If the render is unexpected, fix the code instead of recording; a baseline refresh is never a way to
hide a regression.

## Captures

The same four shared screens are captured twice: at the fixed desktop surface used for the original
baselines and at one phone-width viewport (`360×800` dp at density 1). Both are Compose Desktop
renders of `commonMain`, not Android or iOS renders. The phone-width captures make narrow-screen
reflow, wrapping, and clipping visible in addition to the roomier desktop layout.

| Golden | Size (dp at density 1) | Appearance | Shared state |
|---|---|---|---|
| `chat_home_idle_light.png` | 900×1200 | light | `ChatHomeScreen`, empty conversation, suggestions and composer |
| `chat_home_idle_light_phone.png` | 360×800 | light | `ChatHomeScreen`, same idle state at phone width |
| `chat_answered_source_dark.png` | 900×1200 | dark | `ChatHomeScreen`, answered reply with scope caption and one source card |
| `chat_answered_source_dark_phone.png` | 360×800 | dark | `ChatHomeScreen`, same answered state at phone width; records the top of the page |
| `land_list_light.png` | 900×1000 | light | `LandListScreen`, two saved lands (known and unknown attributes) |
| `land_list_light_phone.png` | 360×800 | light | `LandListScreen`, same two lands at phone width |
| `land_list_empty_dark.png` | 900×800 | dark | `LandListScreen`, no saved lands: empty state |
| `land_list_empty_dark_phone.png` | 360×800 | dark | `LandListScreen`, same empty state at phone width |

## Fixed render conditions and threshold

- density 1, font scale 1, layout direction LTR, JVM locale pinned to `es-ES` for each test;
- appearance is the explicit `ManijeroTheme(darkTheme = ...)` argument, never the host setting;
- fixtures are code-owned (`ScreenshotFixtures`): no clock, network, disk, backend, or land store;
- comparison: Roborazzi `SimpleImageComparator(maxDistance = 0.007)` with
  `changeThreshold = 0.001F` (0.1% of the frame). A real regression (moved control, changed colour,
  wrapped line) covers far more than that; the threshold exists only for sub-visible antialiasing
  noise between same-host renders.

## Limitations

- **Host-pinned fonts.** Compose Desktop resolves fonts from the operating system. These goldens
  were recorded on macOS. A different OS (including the Linux CI runner) must record and review its
  own baselines before it can verify them; that is why the suite is not part of `:shared:jvmTest`,
  `./scripts/init.sh --fast`, or the current CI gate.
- Desktop JVM rendering of `commonMain` only. No Android, iOS, accessibility, usability, legal, or
  product-behavior claim is made by these images.
- A passing suite proves that the eight selected frames match the committed images within the
  threshold. It does not prove that other screens, states, or sizes are unchanged.
