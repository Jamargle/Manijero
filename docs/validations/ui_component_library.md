# Validation: `ui_component_library`

**Verdict: accept** — 2026-10-25

Independent validation against [`ui_component_library.md`](../specs/ui_component_library.md), its
appendix checklist, `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and
`PROGRESS.md` in the `ui_component_library` worktree (base `main` @ `ec8e0c6`). No code, test,
golden, Gradle, theme, string, vector, or backend change was required.

## What was checked

- **Contract and API.** All fourteen declarations from the contract table exist as `internal`
  composables/data classes in `com.jamarglex.manijero.design` (nine files plus `design/navigation/`),
  with the contracted parameter names, defaults and enums; the two pure helpers
  (`screenHorizontalPadding`, `selectedDestinationIndex`) are reviewed in source and exercised by the
  gallery renders. Their 839/840 dp and invalid-index boundaries have no dedicated test.
- **Presentational scope.** The package takes every visible string/value/icon/selection/callback as
  a parameter; it imports no `lands`/`chat`/`privacy`/`coverage`/`platform` type, reads no store,
  sends no request, logs nothing, and contains no `Res.string`. Every colour is a
  `MaterialTheme.colorScheme` role, `LocalManijeroSemanticColors` value or `LocalContentColor`; no
  hex or `Color(0x…)` literal and no new token. No screen or `App.kt` imports the layer.
- **Components.** Card tones/radius/border and non-clickability; heading opt-in; callout four tones
  with icon plus text, a text-only polite live region and an action slot; mandatory stat caption;
  decorative empty-state illustration with a real heading and one action slot; four chip pairs as
  non-interactive labelled chips; radio choice card (≥48 dp, `Role.RadioButton`, selected state,
  optional merged description, error border, caller-owned grouping); search field with a named clear
  action and no filtering; pass-through dropdown/measure fields; flat brand top bar with the wide
  label action and compact named icon action; both bars with always-visible labels, indicator plus
  bolder label, 48 dp targets, `WindowInsets(0)` and safe invalid-index handling.
- **Goldens.** Eight new host renders (Desktop 1200×3000 and 360×5400 dp at 2×; Android same),
  distinct hashes, all components/tones visible, no section clipped, selected state visible without
  colour alone. The ten existing Desktop and six existing Android PNGs are byte-identical.
- **Docs.** `DESIGN.md`, `CONSTRAINTS.md` and `docs/screenshot-regression.md` match the shipped layer
  and capture table; the appendix evidence is honest about host-render-only limits and the pytest
  skip. `feature_list.json` was `passing` pending this record.

## Verification (independently run)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature ui_component_library` | exit 0 — inventory/colour/domain/screen/gallery/golden gates silent-pass; `verifyScreenshots` green (14 Desktop + 10 Android) |
| `./scripts/init.sh --fast` | exit 0 — "All 9 offline checks passed"; backend pytest skipped because pytest is not installed (documented harness behaviour) |
| `./scripts/init.sh --verify` | exit 0 — fast tier, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` all successful |
| `./gradlew :shared:verifyScreenshots --rerun-tasks` | exit 0 — recompiled the JVM/Android main and host-test sources; 24/24 screenshot tests passed |
| `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` | exit 0 — 198 jvm tests / 190 Android host tests, zero failures |
| `git diff --exit-code -- '*.png'`, `git status --porcelain` | exit 0 — only the 8 new goldens untracked; 16 pre-existing goldens unchanged; no screen, vector, string, Gradle, theme, backend, contract, or docs-scope change |

Not re-run: backend pytest (pytest unavailable), device/emulator, iOS build, or a screen-reader
walkthrough; none is claimed by the contract.

## Findings

Post-validation change (2026-10-25): the owner asked to remove
`commonTest/design/ManijeroComponentsTest.kt` because the gallery and screenshot suites were judged
to cover the same ground. It is removed. The fixed-viewport renders do not exercise the 839/840 dp
padding boundary or invalid selected indices, so those two checks are now review-only; the spec and
appendix were corrected accordingly. No shipped source changed.

No blocking or required finding. The disclosed deviations are accepted: the spec prose now matches
its own 9 + 2 file table; the narrow review viewport is 360×5400 dp because the 2× content measures
taller; the top-bar action is also omitted when it has no accessible name; and the pytest tier is
skipped only because pytest is absent.

Known visual limit: at 2× text the compact bottom-navigation labels wrap mid-word
("Asistent/e", "Mis terrenos" across lines). Labels stay fully visible, the selected item keeps the
indicator and a bolder label, and no target shrinks. Recorded for `app_chrome_navigation` to choose
shorter labels or a wrapping policy.

## Honesty boundaries

- Host renders only: Desktop macOS-font-pinned and Robolectric SDK 35, density 1, `es-ES`, one 2×
  text size; no device, emulator, iOS, screen-reader, keyboard/focus, touch-target measurement, or
  usability/comprehension claim.
- No screen adopts the layer yet, so there is no user-visible surface and no interaction
  walkthrough.
- The exposed dropdown's open state needs interaction and is not in the static gallery.
- Contrast for the callout pairs is inherited from the accepted tokens in `DESIGN.md`, not
  re-measured here.

## Security

No finding: static Compose presentational code plus review-only test artifacts; no network, storage,
permission, personal/land data, logging, dynamic content, new dependency, or runtime path.

## Handoff

- `feature_list.json`: `ui_component_library` is `accepted`.
- `PROGRESS.md`: accepted set and golden-count limitation updated to the 14 Desktop / 10 Android
  capture table.
- `app_chrome_navigation` is the next dependency-ready feature and owns real tab labels, tab
  behaviour, and the 2× label-wrap policy.
