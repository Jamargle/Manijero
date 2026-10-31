# Validation: `design_token_refresh`

**Verdict: accept** — 2026-10-25

## What was checked

- Independently reviewed the uncommitted implementation diff against
  [`docs/specs/design_token_refresh.md`](../specs/design_token_refresh.md), its appendix checklist,
  `DESIGN.md`, the accepted `shared_design_system` contract, and the winning Stitch token exports under
  `design-references/stitch/manijero_design_system/` and `.../manijero_design_system_dark_mode/`.
- Confirmed both schemes carry the exported role values: 36 roles in light and dark, equal to the
  Stitch front matter except `outlineVariant` (light `#757C71`, dark `#868E86`, the documented
  accessibility correction) and `scrim` (black, not defined by either export). No superseded value
  (`#354B32`, `#F7F6F0`, `#646B64`, `#A12622`) remains in the live palette.
- Confirmed the surface rule: Material role `surface` is the canvas (`#F9FAF4` / `#121612`);
  cards/inputs read `surfaceContainerLowest` (`#FFFFFF` / `#0D100D`). Exactly five screen call sites
  changed (`App.kt` 707, 783, 876, 909; `lands/LandListScreen.kt` 199); the user bubble and source
  excerpt still read `surfaceVariant`. No `colorScheme.surface` card is left on the canvas.
- Confirmed `ManijeroSemanticColors` exposes six fields (the four original plus
  `ecoContainer`/`onEcoContainer`), both appearances are provided through the local, and the light set
  is the safe default.
- Confirmed the review board derives every swatch from `MaterialTheme.colorScheme` or the semantic local
  and prints `Color.hexLabel()` of the rendered colour: all 36 roles, all six semantics, the caution
  block, the filled `onCaution` sample, the error line, the radio states, and the four land chips with
  container and ink. No typed hex label remains.
- Recomputed every documented ratio independently from the implemented values: 35 light text pairs,
  12 light non-text pairs, 29 dark text pairs, 9 dark non-text pairs, and 4 chip pairs per appearance.
  Zero mismatches against `DESIGN.md`; the minimum is 3.03:1 (dark `outlineVariant` on
  `surfaceContainerHighest`), and the WCAG 2.x formula is correct and anchored at 21:1 black/white.
  The tests assert both an absolute threshold and the documented two-decimal ratio, so they cannot
  pass on a wrong value.
- Confirmed the token scale additions (4/8/16 rhythm, 20/24/32 icons, 720 max width, 24/40/32 padding,
  1 dp border, 48 dp touch target) and that shape values and existing spacing names are unchanged.
- Confirmed the "one palette home" rule: no `Color(0x…)`, `Color.White`, or `Color.Black` literal
  outside `theme/ManijeroColors.kt` in `shared/src/commonMain`.
- Confirmed scope discipline: no copy, layout, navigation, state, persistence, request, `contracts/`,
  `backend/`, `knowledge/`, Gradle, or `design-references/` change (`design-references/stitch/` is
  byte-identical). No dependency was added; the local `.venv` already matched
  `backend/requirements-dev.txt`.

## Verification

- `./scripts/init.sh --feature design_token_refresh` — **PASS**; both palette greps found their
  values and the extended raw-literal scan (including `Color.White`/`Color.Black`) printed nothing.
- `./gradlew :shared:jvmTest --tests ManijeroColorsTest --tests ManijeroDesignSystemTest --rerun` —
  **PASS**; `ManijeroColorsTest` 14 tests, `ManijeroDesignSystemTest` 4 tests, 0 failures. The forced
  full `:shared:jvmTest --rerun` ran 200 tests with 0 failures.
- `./scripts/init.sh --fast` — **PASS**; all 9 offline checks, 200 shared host tests and 618 backend
  tests, contract examples, source catalog, and the five offline evaluators.
- `./scripts/init.sh --verify` — **PASS**; the fast tier plus `:shared:testAndroidHostTest` (186 tests,
  0 failures), `:androidApp:assembleDebug`, and `:desktopApp:build`.
- `git diff --check` — **PASS**.

## Review history

- The first independent pass returned **revise** on documentation only: a stale `current-state.md`
  claim that the theme still used the older palette, stale future tense in `DESIGN.md`, an `onCaution`
  value shown only in a filled sample without its hex label, and appendix evidence that implied a
  dark-board observation. The code, palette, and contrast gates were already accept-quality.
- The repair pass fixed those items, deduplicated the two double-listed contrast pairs in `DESIGN.md`,
  and extended the focused scan to `Color.White`/`Color.Black`. The second independent pass returned
  **accept** after rerunning the gates above.

## Limitations

- No token-board preview was rendered in any of light, dark, or 2× text on this host: the repository has
  no headless Compose preview renderer, and the macOS system appearance is dark and was not toggled.
  The Desktop runtime screenshot shows the app canvas (`#111712`, within a step per channel of the
  documented `#121612`), not the review board. Board layout, 2× text reflow, and the board's dark
  appearance remain unverified manual checks; palette values are instead proven by the exact-value and
  contrast tests in both appearances.
- Screen-reader output, focus order, keyboard operation, and the enlarged-text layout of full app
  screens were not audited here; they remain owned by the accessibility audit and later UI features.
- The iOS target was not compiled; no iOS release or runtime validation is claimed.

## Security and documentation

- No security or privacy issue: the diff is colour/token constants, theme tests, preview-only board
  code, two colour-role lines, and docs. No data flow, network, storage, permission, logging, or
  privacy copy changed; no personal or land data is involved.
- `DESIGN.md` is present-tense and consistent with the code; `docs/progress/current-state.md` describes
  the implemented palette; the appendix records the deferred manual preview honestly. `AGENTS.md`,
  `ARCHITECTURE.md`, and `CONSTRAINTS.md` were correctly left untouched.
- The acceptance record is indexed in [`docs/progress/session-log.md`](../progress/session-log.md) and
  the raw verification evidence is in
  [`docs/archive/specs/design_token_refresh.appendix.md`](../archive/specs/design_token_refresh.appendix.md).
