# Validation: `visual_foundation`

- **Feature:** `visual_foundation` — Apply the shared visual foundation (`client`, `depends_on: []`).
- **Spec:** `docs/specs/visual_foundation.md`.
- **Verdict:** **accept** (2026-10-13).
- **Validator:** independent re-verification of the working-tree diff against the spec and the
  `AGENTS.md`/`DESIGN.md` constraints (scope, `commonMain`-only UI, no new module/dependency,
  accessibility).

## What was validated

- The shared theme lives only in `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/`
  (`ManijeroColors.kt`, `ManijeroTheme.kt`, and `ManijeroTypography.kt` as accepted on this date); no Gradle module, framework, or dependency was added. The typography file was later removed on 2026-10-25 (see amendment).
- The ten `DESIGN.md` tokens ship with their exact documented values, and every derived value appears
  in both the spec's table and `DESIGN.md`.
- `lightColorScheme(...)` sets every documented Material 3 role explicitly, and the "no Material
  default leaked" test compares against `lightColorScheme()` computed at runtime.
- `ManijeroTheme` is applied exactly once, inside `App()` (the documented shared composition root), so
  Android, Desktop, the iOS scaffold, and all previews inherit one palette; the platform hosts contain
  no second theme.
- All fifteen existing previews (`App.kt` seven, `AddLandScreen.kt` eight) use `ManijeroTheme`; the
  review-only token board exposes the caution and danger pairs.
- No layout, copy, spacing, or behavior changed, and `MainActivity.kt`, desktop `main.kt`,
  `MainViewController.kt`, `strings.xml`, Gradle files/version catalog, `backend/`, `contracts/`,
  land storage, and `scripts/init.sh` are untouched.
- No logging was introduced in `shared/src` (no `println`/`Log`/`Logger`/`printStackTrace`/`NSLog`).

## Commands that ran

- `./scripts/init.sh --verify` → **BUILD SUCCESSFUL**.
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` → **BUILD SUCCESSFUL**:
  - `:shared:jvmTest`: **54 tests, 0 failures** (`ManijeroColorsTest` 10, `ManijeroTypographyTest` 4
    new, at acceptance time).
  - `:shared:testAndroidHostTest`: **51 tests, 0 failures** (same 14 new theme tests).
- `:androidApp:assembleDebug` (debug APK produced) and `:desktopApp:build` → **BUILD SUCCESSFUL** via
  `--verify`.
- Centralization greps (all as specified): no `Color(0x` outside `theme/`; no argument-less
  `MaterialTheme {`; `MaterialTheme(` only in `theme/ManijeroTheme.kt`; no
  `LocalMinimumInteractiveComponentSize`/`minimumInteractiveComponentSize` override.

## Independent cross-checks (beyond the shipped tests)

- Recomputed the WCAG 2.x contrast ratios with a separate Python implementation (not the repository
  helper). Every documented pair matched the shipped test expectation and cleared its threshold:
  `onSurface on surface` 16.19, `onBackground on canvas` 14.96, `onSurfaceVariant` on canvas/surface
  7.54/8.16, `onPrimary on primary` 9.53, `primary label on canvas` 8.80, `caution on cautionSurface`
  7.37, `caution on surface` 8.19, `error on surface` 7.46, and non-text `outline` 3.91/4.23,
  `outlineVariant` 3.55/3.05 — all ≥ 4.5:1 (text) or ≥ 3:1 (non-text).
- Confirmed `feature_list.json` parses and no Gradle/host/string files are in the diff.

## Non-color cue requirements

Reviewed against the spec: caution/danger are always paired with text; validation keeps a text
`supportingText` plus field error semantics; selection uses control semantics/labels; transcript
speakers stay labelled "Tú"/"Asistente"; disabled controls use `enabled = false`; visible focus is not
suppressed; the Material 48dp minimum interactive size is untouched. The token-board preview plus the
contrast tests are the evidence available before `response_states` ships.

## Findings and honest gaps

- **F1 (non-blocking):** interactive Android/Desktop smokes (screenshots, greyscale non-color cue
  check, emulator `font_scale 2.0`, Desktop window resize/keyboard focus) were not run in this
  non-interactive session. Enlarged-text evidence is preview-based; Desktop OS-level text scaling is
  not wired in this repository. Runtime accessibility confirmation stays with `chat_accessibility`
  (carried finding F3).
- **F2 (non-blocking, by decision):** the theme is light-only; a system in dark mode still sees the
  warm light palette. `DESIGN.md` records this and a dark palette is a follow-up feature.
- **F3 (non-blocking, carried):** container fills are intentionally low-contrast; card/bubble
  separation relies on the `outline`/`outlineVariant` boundary and text, which the spec documents.

No blocking findings. Verdict: accept.

## Amendment 2026-10-25: Material default typography

- The owner later chose pure Material 3 default typography. `ManijeroTypography.kt` and
  `ManijeroTypographyTest.kt` were deleted, and `ManijeroTheme` no longer passes a `typography`
  argument, so the accepted `bodySmall` 18sp line-height override no longer applies.
- Everything above about the theme, palette, contrast, previews, and accessibility remains as
  accepted. The typography sentence and test-count entries above are historical and were true on
  2026-10-13; they do not describe the current code. Current status is recorded in
  [`docs/validations/shared_design_system.md`](shared_design_system.md).
