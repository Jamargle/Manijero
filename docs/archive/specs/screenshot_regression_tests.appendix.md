# Appendix — `screenshot_regression_tests`

Planning and verification record for [`docs/specs/screenshot_regression_tests.md`](../../specs/screenshot_regression_tests.md). The acceptance record is `docs/validations/screenshot_regression_tests.md`.

**Scope extension (2026-10-25):** the original Desktop-only contract was extended at the owner's request to Android host rendering with Robolectric. The Desktop research and evidence below are preserved; the Android extension and its self-verification are recorded at the end under "Feature evidence".

## Repository research

Inspected on 2026-10-25, planning only; no source or application file was changed.

- `feature_list.json` registers this as `not_started`, dependent on `design_token_refresh`; `PROGRESS.md` lists that prerequisite as accepted and describes this feature as owner-approved Roborazzi on Desktop JVM with human-approved goldens.
- `docs/design/ui-refresh-plan.md` §§10.2/10.4 require reviewed screenshot artifacts, fixed dimensions/theme/font scale/locale/fixtures, an explicit comparison threshold, verify-only CI, and honest non-claims. It identifies Compose Desktop Roborazzi support as experimental and manual screenshots as fallback.
- `shared/build.gradle.kts` declares Kotlin Multiplatform targets for JVM, Android, and iOS. Its existing `jvm()` target is hosted by `desktopApp`; common tests use `kotlin.test` and coroutines test. No screenshot-specific plugin/dependency or screenshot fixture exists in the inspected configuration.
- `desktopApp/build.gradle.kts` uses Compose Multiplatform and depends on `:shared`; Desktop app production entrypoint is `MainKt`.
- `scripts/init.sh --feature <id>` executes the command block published in the feature contract. `--fast` runs `:shared:jvmTest` without requiring an Android SDK; `--verify` adds Android host tests and Android/Desktop builds.
- Existing Compose and screen logic is shared under `shared/src/commonMain`; `DESIGN.md` defines light/dark theme roles and accessibility/design boundaries. Representative screenshots must render that shared UI, not a duplicate mock implementation.
- `PROGRESS.md` says no automated UI/E2E harness exists yet and explicitly limits any future screenshot claim to shared rendering, not Android or iOS.
- The repository's CI workflow/task wiring was not established during this planning pass; inspect before deciding whether an existing workflow should run the verify task. Do not add a new workflow without an explicit scope decision.

## Implementation plan and tasks

1. Confirm current Roborazzi Desktop/KMP integration compatibility with the repository's Kotlin 2.4.20 and Compose Multiplatform 1.12.1; pin a compatible release and record any experimental compatibility constraints. Do not upgrade the toolchain as a workaround without approval.
2. Add the minimal plugin/dependency and JVM test configuration in `gradle/libs.versions.toml` and `shared/build.gradle.kts`; verify Android/iOS source-set dependency graphs are not pulled into the screenshot test path.
3. Create deterministic fixtures and a small set of test captures for representative common UI. Include at least light and dark rendering, and document the selected screens/states and why other states are omitted.
4. Fix render dimensions, theme, locale, font scale, and fixture values. Set an explicit compare threshold appropriate to the pinned recording environment; do not widen it to mask meaningful layout/color changes.
5. Record initial images using the explicit record mode, inspect each image, and commit only human-reviewed baselines. Configure normal verification to compare only and never rewrite expected images.
6. Confirm changed pixels fail verification, confirm normal verification leaves baseline files untouched, and confirm the focused harness works without Android SDK/emulator. Publish exact command(s) and recording instructions in the contract.
7. Run the focused check, capture feature evidence and limitations, then update status/progress records only through the acceptance workflow.

## Verification plan

- Inspect the dependency graph and relevant Gradle tasks; ensure the exact focused command includes screenshot verification rather than just ordinary JVM unit tests.
- Run `./scripts/init.sh --feature screenshot_regression_tests` and `./gradlew :shared:jvmTest` from a clean baseline state.
- Prove verify mode does not mutate golden files (compare checksums or git diff before/after).
- In a disposable fixture/source change, prove an intentional image difference causes a failing verify result and useful expected/actual/diff outputs; remove the probe without affecting accepted work.
- Record through the explicit task and confirm only the intended baseline changes; inspect the resulting PNGs manually.
- Confirm the Desktop focused run needs no Android SDK; the Android host suite needs an Android SDK to build but no emulator, device, backend, or network (apart from the first Robolectric SDK download). If a platform integration is unusable on the supported environment, stop and report the blocker rather than silently replacing pixel tests with pure unit tests.

## Evidence to capture

- Pinned Roborazzi and Compose test versions, task names, exact recording command, environment, render matrix, and threshold rationale.
- Focused verification output and screenshot test names/counts.
- Proof the normal verify task leaves expected images unchanged; failure output/artifact paths from the regression probe.
- Reviewed baseline image inventory and the human review disposition for each capture.
- Explicit limitations: Desktop JVM host/font only; Android Robolectric host on the pinned SDK only, not a device or emulator; no iOS runtime, behavior, accessibility, usability, or legal correctness claim.

## Feature evidence

### 2026-10-25 — implementation and self-verification (implementer)

Environment: macOS (darwin; host fonts resolved by Compose Desktop), Temurin JDK 17.0.6, Gradle
9.8.0. Pinned toolchain: Kotlin 2.4.20, Compose Multiplatform 1.12.1, AGP 9.4.1 (declared for the
Android target; never exercised by this task). Screenshot tooling: Roborazzi **1.77.0**
(`roborazzi-compose-desktop`) with `org.jetbrains.compose.ui:ui-test-junit4-desktop` 1.12.1. No
toolchain upgrade was needed.

**Wiring.** `gradle/libs.versions.toml` pins `roborazzi = "1.77.0"` plus the two library aliases.
`shared/build.gradle.kts` adds them to `jvmTest.dependencies` together with
`compose.desktop.currentOs` (Jvm-only; `jvmMain`, Android, and iOS dependency graphs are untouched),
and registers two dedicated Gradle `Test` tasks:

| Task | Mode | Behaviour |
|---|---|---|
| `:shared:verifyScreenshots` | `roborazzi.test.verify=true`, `record=false` | Compare-only gate; read-only for goldens |
| `:shared:recordScreenshots` | `roborazzi.test.record=true`, `verify=false` | Explicit re-record, only after human review |

Both use `useJUnit()`, `includeTestsMatching("com.jamarglex.manijero.screenshots.*")`,
`isFailOnNoMatchingTests = true`, `outputs.upToDateWhen { false }`, and `java.awt.headless=true`.
Exactly one Roborazzi mode is set per task, and the test body asserts that a mode is active, so a
misconfigured run fails instead of silently capturing nothing. `:shared:jvmTest` now filters that
package out (see the Linux/host-font limitation below). No Roborazzi Gradle plugin is applied: the
plugin would make plain `jvmTest` a no-op and can combine record with verify.

**Commands run on 2026-10-25 (all from the repository root)**

| Command | Result |
|---|---|
| `./gradlew :shared:verifyScreenshots --console=plain --no-daemon` | BUILD SUCCESSFUL — `chatHomeIdleLight`, `chatAnsweredSourceDark`, `landListLight`, `landListEmptyDark` PASSED, 4/4 |
| `./scripts/init.sh --feature screenshot_regression_tests` | exit 0 — the contract's focused block resolves to the same task, 4/4 PASSED |
| `./gradlew :shared:jvmTest --rerun-tasks` | exit 0 — 200 tests, 0 failures; result XML contains no `SharedScreenshotsTest` (suite is excluded by filter) |
| `./scripts/init.sh --fast` | exit 0 — all nine offline checks passed, including `:shared:jvmTest` |
| `./scripts/init.sh --verify` | not run for this feature: no Android/Desktop packaging or production behaviour changed |

**Render matrix** (goldens in `shared/src/jvmTest/screenshots/`, committed; density 1, font scale 1,
LTR, JVM locale `es-ES`):

| Golden | Size | Appearance | Shared state + fixture |
|---|---|---|---|
| `chat_home_idle_light.png` | 900×1200 | light | `ChatHomeScreen`, `ScreenshotFixtures.idleChat` (empty conversation, suggestions, composer, privacy note) |
| `chat_answered_source_dark.png` | 900×1200 | dark | `ChatHomeScreen`, `ScreenshotFixtures.answeredChat` (answered reply, scope caption, one source card) |
| `land_list_light.png` | 900×1000 | light | `LandListScreen`, `ScreenshotFixtures.twoLands` (known and unknown attributes) |
| `land_list_empty_dark.png` | 900×800 | dark | `LandListScreen`, `ScreenshotFixtures.noLands` (empty state) |

Fixtures are code-owned (`ScreenshotFixtures.kt`): no clock, network, disk, land store, or backend
call. The answered reply and its source copy are the reviewed text from
`contracts/examples/response-answered.json` plus the `[1]` citation marker needed to render the
source card. Transient states (loading, error, clarification, form editing, help/privacy/coverage
pages) are deliberately not goldened: they are covered by ordinary behaviour tests, and every extra
golden increases review cost without adding layout signal.

**Threshold.** `changeThreshold = 0.001F` (0.1% of the frame) on top of Roborazzi's default
`SimpleImageComparator(maxDistance = 0.007)` per-pixel tolerance. Rationale (in the test KDoc): a
meaningful regression — moved control, changed colour, wrapped line — covers far more than 0.1% of
a frame, while the per-pixel comparator already absorbs sub-visible antialiasing noise on repeated
same-host renders. The threshold was not widened after recording; no baseline was re-recorded to
make a failing run pass.

**Verify is read-only.** SHA-256 of all four goldens before and after every passing verify run (and
during the failing probe run) was identical:

```
6f256ca99c29812278238def87b2b73d729072a41f3545c8c65b36bc87a1f69f  chat_answered_source_dark.png
7cb4959d66e999a49dad30f7dffbde81accc978146168ec55a23bc445c7ae0e4  chat_home_idle_light.png
f296302e8b2ef3014146cb9f5d25279f8659934db119d93cee79b3e620fe4841  land_list_empty_dark.png
f6475a3982eb7007a4f33f750d6ed4331a2d0dfdb6036335e6721258fe418d0f  land_list_light.png
```

A passing verify run writes only `shared/build/reports/screenshot-regression/results/*.json`
(`"type":"unchanged"` for all four); the goldens directory stays byte-identical, so `git status`
does not change.

**Regression-detection probe (disposable).** Changed one production render input temporarily:
`shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt:447`,
`Arrangement.spacedBy(20.dp)` → `Arrangement.spacedBy(28.dp)` in `ChatHomeScreen`. Then:

- `./gradlew :shared:verifyScreenshots --console=plain --no-daemon` → **exit 1**,
  `4 tests completed, 2 failed`, `BUILD FAILED in 7s`;
- `landListEmptyDark` and `landListLight` passed (the change does not touch the lands screen);
- `chatHomeIdleLight` and `chatAnsweredSourceDark` failed with
  `java.lang.AssertionError: Roborazzi: …/shared/src/jvmTest/screenshots/chat_home_idle_light.png is changed. See the compare image at …/shared/build/reports/screenshot-regression/chat_home_idle_light_compare.png`;
- artifacts left for review: `chat_home_idle_light_actual.png` (50,559 B),
  `chat_home_idle_light_compare.png` (195,625 B), `chat_answered_source_dark_actual.png` (94,066 B),
  `chat_answered_source_dark_compare.png` (316,944 B), plus result JSON with
  `"type":"changed"` and `diff_percentage` 0.0444 (chat home, ≈4.4% of pixels) and 0.1275
  (answered, ≈12.8%), far above the 0.001 threshold (Roborazzi computes the value as
  `pixelDifferences / pixelCount`);
- the four goldens' SHA-256 values were unchanged by the failing run (same list as above), proving
  verify did not overwrite them;
- the compare image was opened and reviewed: left = committed golden, middle = diff heat map (all
  suggestion rows, labels, and the footer shift downward), right = current render, i.e. a real
  layout regression rather than noise;
- the probe edit was reverted with a file backup (`git status` shows no change in `App.kt`) and
  `:shared:verifyScreenshots` passed again.

**Record/verify separation probe.** With the same temporary 20→28 dp change,
`./gradlew :shared:recordScreenshots` exited 0 (4/4 PASSED) and rewrote **only** the two affected
goldens: `chat_home_idle_light.png` 7cb4959d… → 3200e713…, `chat_answered_source_dark.png`
6f256ca9… → acbeea4f…. `land_list_light.png` and `land_list_empty_dark.png` stayed byte-identical.
The re-recorded chat images were opened, showing the wider 28 dp spacing, then the pristine goldens
were restored from backup, `App.kt` was reverted, and a verify run passed against the original
goldens. This confirms recording is an explicit separate action, is selective, and never happens on
the verification path.

**No Android SDK/emulator needed.** Moved `local.properties` (the only `sdk.dir` source; `ANDROID_HOME`
and `ANDROID_SDK_ROOT` were unset) out of the worktree and ran
`./gradlew :shared:verifyScreenshots --rerun-tasks --no-configuration-cache --console=plain --no-daemon`:
configuration was recalculated from scratch, no "SDK location not found" error, **exit 0**, 4/4
PASSED. `local.properties` was restored afterwards. No emulator, backend, or network service was
started at any point.

**Human review of the committed baselines (each opened at full size).**

- `chat_home_idle_light.png` — title "¿En qué puedo ayudarte?", subtitle, three suggestion buttons,
  composer placeholder, disabled "Preguntar", "Mis terrenos", privacy note, "Privacidad y ayuda" and
  "Qué cubre la app" links; light surface, nothing clipped or overlapping.
- `chat_answered_source_dark.png` — dark appearance; user bubble, assistant answer with "Tiene en
  cuenta todos tus terrenos.", citation marker, "Fuentes"/"Fuente 1" card (title, issuing body,
  document part, "Comprobado el 01/10/2026", excerpt, "Abrir documento oficial"), suggestions and
  composer; the frame ends inside the privacy notice, so the footer links are cut off by the fixed
  viewport (documented in the test).
- `land_list_light.png` — "Mis terrenos", two land cards (`Los Olivos` with known attributes,
  `La Loma` with "Producción: No lo sé" kept unknown), "Editar"/"Eliminar", "Añadir terreno",
  "Volver"; light surface.
- `land_list_empty_dark.png` — dark appearance, empty-state sentence, "Añadir terreno", "Volver".

These images depict the current shared layout; review confirmed they are the intended render, not a
judgement that the layout is ideal. Android/iOS rendering, accessibility, usability, and product or
legal correctness are not assessed.

**Recording documentation.** `docs/screenshot-regression.md` documents the verify commands,
artifact locations, the explicit record procedures, the per-image review checklist, the commit rule,
the fixed render conditions, the threshold, and the limitations for both platforms; the READMEs next
to each platform's goldens point to it.

**Limitations recorded for the validator.**

- Compose Desktop resolves host fonts, so these goldens are host-pinned: recorded on macOS, they are
  only expected to match on the same host/font setup. The suite is therefore excluded from
  `:shared:jvmTest`, `./scripts/init.sh --fast`, and the existing `ubuntu-latest` CI gate, which do
  not render screenshots. Adding Linux goldens or a Linux screenshot job is a separate decision
  (CI workflow changes are out of scope for this feature).
- Desktop JVM plus Android Robolectric host only: no emulator, device, instrumentation, other
  Android API levels, or iOS runtime coverage, and no claim of device visual fidelity.
- Twelve captures only: eight Desktop frames (four scenes at two widths) and four Android host
  frames (the four scenes at 360×800 dp). A pass means those frames match within the threshold;
  other screens, states, text sizes, locales, window sizes, or Android API levels are not gated.
- No accessibility, usability, behaviour, or legal-correctness proof; the suite does not replace
  behaviour tests.
- Baseline refresh is manual and human-reviewed; there is no automated guard beyond the review
  procedure in `docs/screenshot-regression.md`.

### 2026-10-25 — split by screen (follow-up refactor)

- `SharedScreenshotsTest` was split so each screen owns its file: `ChatHomeScreenshotsTest` (idle
  light, answered-plus-source dark) and `LandListScreenshotsTest` (two-land light, empty dark),
  sharing the determinism harness in `ScreenshotTestSupport`. No capture, fixture, golden,
  threshold, task, or assertion changed; `ScreenshotFixtures` is untouched.
- `./gradlew :shared:verifyScreenshots --rerun-tasks` → BUILD SUCCESSFUL, 4/4 PASSED, now reported
  as `ChatHomeScreenshotsTest > chatHomeIdleLight`, `ChatHomeScreenshotsTest >
  chatAnsweredSourceDark`, `LandListScreenshotsTest > landListEmptyDark`, and
  `LandListScreenshotsTest > landListLight`.
- The four golden SHA-256 values are unchanged by the split, and the Gradle filter
  `com.jamarglex.manijero.screenshots.*` still selects both classes. The `SharedScreenshotsTest`
  name in the earlier evidence entries above refers to the pre-split single file.

### 2026-10-25 — one phone-width viewport added

- Each of the four scenes now also renders at a single phone-width viewport (`360×800` dp at density
  1, still Compose Desktop on the JVM): `chat_home_idle_light_phone`,
  `chat_answered_source_dark_phone`, `land_list_light_phone`, and `land_list_empty_dark_phone`.
  Harness constants `PHONE_WIDTH`/`PHONE_HEIGHT` are pinned in `ScreenshotTestSupport`; the other
  render conditions (appearance, density, font scale, LTR, `es-ES`, fixtures) are unchanged.
- Recorded with the explicit `./gradlew :shared:recordScreenshots --rerun-tasks`. The original four
  goldens kept their SHA-256 values (only the four `*_phone.png` files were added), and all eight
  images were opened at full size and reviewed: the idle chat, answered chat, two-land list, and
  empty lands list render without blank or half-painted frames.
- `./gradlew :shared:verifyScreenshots --rerun-tasks` → BUILD SUCCESSFUL, 8/8 passed:
  `chatHomeIdleLight`, `chatHomeIdleLightPhone`, `chatAnsweredSourceDark`,
  `chatAnsweredSourceDarkPhone`, `landListLight`, `landListLightPhone`, `landListEmptyDark`, and
  `landListEmptyDarkPhone`. The phone-width frames are shared-UI renders at a narrow size, not
  Android/iOS device evidence.

### 2026-10-25 — Android host suite added (scope extension)

- Owner request: validate the shared UI locally for **both** Desktop and Android before committing,
  then record reviewed baselines. Android is rendered by **Robolectric 4.17** on the host JVM, so no
  emulator, device, or instrumentation is involved.
- Tooling: `roborazzi`/`roborazzi-compose` 1.77.0, `androidx.compose.ui:ui-test-junit4` and
  `ui-test-manifest` 1.12.1, `androidx.test:core` 1.7.0, `androidx.test.ext:junit` 1.3.0, added to
  `androidHostTest` only. The shared fixtures moved to `commonTest` so both platforms render the
  same data; no production or main Android dependency changed.
- Tasks: `verifyDesktopScreenshots`/`recordDesktopScreenshots` hold the previous Desktop suite;
  `verifyAndroidScreenshots`/`recordAndroidScreenshots` run Robolectric with the same read-only
  verify versus explicit record split; `verifyScreenshots`/`recordScreenshots` are the aggregate
  entry points. `testAndroidHostTest` and `jvmTest` exclude the screenshot packages.
- Render matrix: the four scenes at `es-rES-w360dp-h800dp-mdpi`, Robolectric SDK 35, density 1,
  font scale 1, explicit `ManijeroTheme(darkTheme = ...)`, threshold 0.001. Goldens live in
  `shared/src/androidHostTest/screenshots/` (4 PNGs). Desktop keeps its 8 PNGs in
  `shared/src/jvmTest/screenshots/`; the two platforms are recorded separately because their
  rasterisation differs.
- Recorded with `./gradlew :shared:recordAndroidScreenshots --rerun-tasks`; all four images were
  opened at full size and reviewed (idle chat light, answered-plus-source dark, two-land list light,
  empty lands dark). Recording twice produced identical Android SHA-256 values.
- Verification: `./gradlew :shared:verifyAndroidScreenshots --rerun-tasks` → 4/4 passed;
  `./gradlew :shared:verifyScreenshots --rerun-tasks` → 8 Desktop + 4 Android passed; focused
  `./scripts/init.sh --feature screenshot_regression_tests` → same aggregate, exit 0.
- Regression probe: temporarily renamed one fixture land (`Los Olivos` → `Los Olivos del Sur`).
  Android verify failed on `landListLight` with
  `shared/build/reports/screenshot-regression-android/land_list_light_compare.png` and
  `_actual.png`; the four Android goldens kept their SHA-256 values. The fixture was restored and
  verify is green again. No emulator or device was started.
- Limitations: Robolectric host rendering is not device/emulator evidence and only SDK 35 is
  pinned; the Android suite needs an Android SDK to build and a one-time download of Robolectric's
  `android-all` jar; it stays out of the ordinary test tiers and CI.

## Validator checklist

- [ ] Scope is test-only; no production UI or feature behavior changed.
- [ ] Roborazzi/tooling versions are pinned and compatible with the current toolchain; no unrelated upgrade or module was introduced.
- [ ] The Android suite stays on the existing Android target through Robolectric, with separate goldens and no emulator/device/instrumentation dependency.
- [ ] Test captures shared UI on Desktop JVM and via Robolectric on the Android host, with stable fixtures, dimensions, appearance, font scale, and locale.
- [ ] The focused command runs both screenshot suites in verify mode through the feature harness; Desktop needs no Android SDK, and Android needs an SDK but no emulator/device.
- [ ] Verify mode is read-only for baselines on both platforms; a changed render fails and provides reviewable diff artifacts.
- [ ] Recording is explicit per platform, documented, and human-reviewed; committed baselines match the reviewed output.
- [ ] Threshold rationale is explicit and does not hide meaningful regressions; CI, if wired, runs verify only.
- [ ] Coverage and limitations are reported accurately; no emulator/device, iOS, accessibility, behavior, or usability claim is implied.
- [ ] Progress/status/session-log updates are consistent with the independent validation result.
