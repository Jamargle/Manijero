# Appendix — `visual_foundation`

Planning and verification record for [`docs/specs/visual_foundation.md`](visual_foundation.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/visual_foundation.md` remains the authoritative
acceptance record.

## Repository research

Inspected (all paths relative to the repository root):

- `DESIGN.md` lines 11-28 (tokens) and 52-56 (accessibility baseline); `CONTEXT.md` (plain Spanish, high contrast, Android/Desktop MVP); `docs/risks-and-open-questions.md` (no visual/theme row today); `docs/domain-model.md` (no visual constraint).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` — `ChatHomeScreen` and the only two shared destinations; its comment already calls `App()` the composition root. It reads `colorScheme.background`, `onBackground`, `onSurface`, `onSurfaceVariant`, `primary`, `surface`, `surfaceVariant`, `outlineVariant`, and `typography.headlineMedium/bodyLarge/titleMedium/labelLarge`. Seven `@Preview` wrappers use `MaterialTheme { }` (default palette). No theme is applied to real content.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt` — reads `background`, `onBackground`, `onSurfaceVariant`, `error`, `typography.headlineMedium/bodyLarge/titleMedium`; eight `@Preview` wrappers use `MaterialTheme { }`.
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt` and `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` — both call `App(landRepository)` inside `setContent`/`Window`; neither wraps it in any theme. `shared/src/iosMain/.../MainViewController.kt` calls `App()`.
- No `theme`/`color`/`typography` file exists anywhere under `shared/src`. `MaterialTheme` appears only as an implicit default.
- `gradle/libs.versions.toml` — Compose Multiplatform 1.12.1, `material3 1.12.0-alpha03`, `kotlin 2.4.20`. No font, color, or theme dependency and none may be added. `shared/build.gradle.kts` exposes `compose.material3`, `compose.foundation`, `compose.ui`, and `ui-tooling-preview` in `commonMain`, and `kotlin-test` in `commonTest`.
- Existing tests (`ChatHomeStateTest`, `ChatConversationTest`, `KtorAnswerServiceTest`, `LandRepositoryTest`, `AddLandStateTest`, host/desktop scaffold tests, 24 JVM / 22 Android host) never import `androidx.compose.*`; no Compose UI-test harness or screenshot test exists. Compose types are expected to be reachable from the associated test compilation; see Risk R2 for the fallback if they are not.
- `androidApp/src/main/res/drawable/ic_launcher_background.xml` and `drawable-v24/ic_launcher_foreground.xml` — the launcher artwork is the **unmodified Android Studio template**: solid template green `#3DDC84` background with the white Android robot. There is no olive-grove artwork in the repository, so the requested palette sanity check has nothing to compare against; `DESIGN.md` tokens stay as written (see U1). `androidApp/src/main/AndroidManifest.xml` already uses `@android:style/Theme.Material.Light.NoActionBar`.
- `./scripts/init.sh` — `--verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; it must not gain new modes or a long-running service for this feature.

The feature is correctly sized: one cross-cutting presentation layer, no data model, no user flow, no new module. Two screens change only at their theme/preview wrapper.

## Implementation plan and tasks

1. Write `ManijeroColorsTest` expectations first (exact hex values, role mapping, contrast thresholds), then implement `ManijeroColors.kt` until the test passes. Keep the WCAG helper in the palette file and free of I/O.
2. Add `ManijeroTypography.kt` with the single override and its test.
3. Add `ManijeroTheme.kt` (theme + semantic local + token-board previews); confirm the preview renders olive/canvas values, not purple.
4. Apply `ManijeroTheme` once inside `App()`; repoint all fifteen existing previews; run the existing suites to confirm no behavior regression.
5. Re-run the contrast table against the shipped values and correct any value that misses its threshold by adjusting the derived value (never by lowering the threshold or dropping a pair).
6. Run the full command set below, capture output, then perform the Android and Desktop manual checks and the greyscale non-color cue check.
7. After implementation and independent validation only: update `feature_list.json`/`PROGRESS.md`, refresh the `scripts/init.sh` banner text, and make the `DESIGN.md` documentation update.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh                                   # toolchain check; creates local.properties
./gradlew :shared:jvmTest                   # existing suites + new theme tests
./gradlew :shared:testAndroidHostTest       # same tests on the Android host
./gradlew :androidApp:assembleDebug
./gradlew :desktopApp:build
./scripts/init.sh --verify                          # the accepted one-shot check
```

Automated, in-repo checks:

- Token contract: each `DESIGN.md` token and derived value equals the exact hex in this spec.
- Mapping: each tested `ColorScheme` role equals its documented value (`background` = canvas, `primary` = olive-800, `surface` = white, `surfaceVariant`, `onSurfaceVariant`, `onSurface`, `onBackground`, `outline`, `outlineVariant`, `error`, `errorContainer`, `primaryContainer`, `secondaryContainer`, `tertiaryContainer`, `inverseSurface`).
- No default palette: for the brand-bearing roles listed in this spec, assert the value differs from `lightColorScheme()`'s own default (computed at runtime, not hard-coded) so a future Material default cannot leak in.
- Contrast: the documented text pairs ≥ 4.5:1 and non-text pairs ≥ 3:1, using the repository's own helper; failure messages must name the pair and the measured ratio.
- Centralization: `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt` returns matches only under `theme/`; `grep -rn "MaterialTheme {" shared/src/commonMain` returns nothing (no argument-less default-palette wrapper remains) and `grep -rn "MaterialTheme("` matches only `theme/ManijeroTheme.kt`; `grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src` returns nothing.

Manual checks (record screenshots or a short written record for each):

1. Android emulator (`Medium_Phone_API_35`, debug APK from `:androidApp:assembleDebug`): canvas page background, olive `Preguntar`/`Guardar terreno` buttons, olive `Mis terrenos` navigation label, `Tú` bubble in the low-emphasis neutral and `Asistente` in white with a visible border, and no purple/blue anywhere on the chat or add-land screens.
2. Desktop (`./scripts/init.sh --desktop`): the same checks, plus window resize (narrow and wide) and keyboard focus visibility on the field, `Preguntar`, and `Guardar terreno`.
3. Android Studio preview panel: every preview in `App.kt`, `AddLandScreen.kt`, and the theme file renders the olive/canvas palette, and the token-board preview shows caution and danger pairs.
4. Text scaling: Android `font_scale 2.0` and the `fontScale = 2f` previews — nothing clipped or overlapped on either screen. Desktop OS-level text scaling is not wired in this repository (verified: no font-scale integration exists), so Desktop evidence is preview-based; report that limitation instead of claiming a Desktop scaling pass.
5. Non-color cues: render the danger message and the caution callout sample, convert the screenshot to greyscale, and confirm the state is still readable from text and control semantics alone.
6. Submit a question and save a land once on each platform to confirm theming changed appearance only.

Evidence to capture: the two test-task outputs with new test names and counts, `--verify` output (or the exact Android SDK blocker), screenshots/preview captures for chat, add-land, token board, and enlarged text, the greyscale capture, and the three `grep` outputs. This repository has **no persistent E2E or screenshot-test command** (verified: `./scripts/init.sh --verify` only runs the shared host tests and the Android/Desktop builds, and no Compose UI-test dependency or harness exists), so focused pure unit tests plus the Android/Desktop manual checks above are the justified coverage for this presentation-layer feature; report that limitation honestly instead of implying E2E coverage. Desktop font-scaling and Android launch-frame behavior remain known gaps (U2, U3, U4).

## Validator checklist

- [ ] Tokens live only in `shared/src/commonMain/.../theme/` (no new module, no new dependency, no hardcoded hex outside `theme/`).
- [ ] Every `DESIGN.md` token value ships unchanged, and every derived value appears in the spec's table with a reason.
- [ ] `lightColorScheme(...)` sets every role listed in the spec; no screen, host, or preview renders Material's default purple/blue.
- [ ] `ManijeroTheme` is applied once at the shared composition root, so Android, Desktop, `MainViewController`, and all `App()` previews inherit it; platform roots contain no second theme.
- [ ] All fifteen existing previews use the shared theme; the token-board preview shows every token plus caution and danger samples.
- [ ] `:shared:jvmTest` and `:shared:testAndroidHostTest` pass with new tests covering exact token values, role mapping, "no Material default leaked", and the documented contrast thresholds (≥ 4.5:1 text, ≥ 3:1 non-text); the measured ratios match this spec.
- [ ] Non-color cue requirements hold: no color-only caution/danger/selection/validation/disabled cue; visible focus is preserved; 48dp minimum interactive size is untouched.
- [ ] Themed screens keep plain Spanish copy, existing behavior, and land persistence; no chat/land logic, contract, backend, or storage change.
- [ ] Enlarged-text checks show no clipping on the chat and land screens, with the Desktop scaling limitation reported rather than claimed.
- [ ] Android and Desktop manual evidence (screenshots or a written record) shows canvas background, olive primary, surface cards/inputs, and caution/danger pairs, and the greyscale check is recorded.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the spec's file list matches the actual diff.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/visual_foundation.md.
- New shared theme package in commonMain (shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/): ManijeroColors.kt (DESIGN.md tokens + derived values, a fully specified lightColorScheme, ManijeroSemanticColors/LocalManijeroSemanticColors, dependency-free WCAG helpers), ManijeroTypography.kt (single documented bodySmall 16sp->18sp line-height override), and ManijeroTheme.kt (theme + semantic local + review-only token-board previews).
- ManijeroTheme is applied once inside App() (the shared composition root) and all fifteen existing previews (seven in App.kt, eight in AddLandScreen.kt) use it; the Android, Desktop and iOS hosts stay theme-free and inherit one shared theme. No layout, copy, spacing, or behavior changed; no new module, framework, or dependency.
- ./scripts/init.sh --verify -> BUILD SUCCESSFUL. ./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks -> BUILD SUCCESSFUL: 54 JVM tests / 0 failures (ManijeroColorsTest 10, ManijeroTypographyTest 4 new) and 51 Android host tests / 0 failures; :androidApp:assembleDebug and :desktopApp:build pass.
- Centralization greps: no Color(0x outside theme/; no argument-less MaterialTheme {; MaterialTheme( only in theme/ManijeroTheme.kt; no LocalMinimumInteractiveComponentSize/minimumInteractiveComponentSize override.
- DESIGN.md updated with the derived-token table and the light-only decision. Self-verified; awaiting independent validation.
- Independent validator ACCEPTED (record: docs/validations/visual_foundation.md) after re-running ./scripts/init.sh --verify and :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks (54 JVM / 51 Android host tests, 0 failures), reproducing the WCAG pairs with an independent computation, and confirming scope discipline (commonMain-only theme, no new module/dependency, hosts/strings/Gradle untouched, no logging).
