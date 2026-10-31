# Appendix — `design_token_refresh`

Planning and verification record for [`docs/specs/design_token_refresh.md`](../../specs/design_token_refresh.md).
Sections: repository research (including the plan's P0-01 read-only audit), implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator checklist, and
feature evidence. `docs/validations/design_token_refresh.md` will be the authoritative acceptance
record.

## Repository research

Inspected on 2026-10-25, planning only; no source file was changed.

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/` contains exactly three files:
  `ManijeroColors.kt` (235 lines), `ManijeroTheme.kt` (202 lines), `ManijeroTokens.kt` (22 lines). There
  is no `design/` package, no component library, no typography file, and no font asset.
- `ManijeroColors.kt` holds the ten light token values, the derived light role values, the complete
  light scheme, the dark scheme with inline values, the semantic data class/local, and the WCAG helpers
  (`relativeLuminance`, `contrastRatio`).
- The shipped light palette is still the 2026-10-24 accepted warm palette: `primary` `#354B32`,
  `canvas` `#F7F6F0`, `surface` `#FFFFFF`, `text-primary` `#1D221B`, `text-secondary` `#4B5149`,
  `border` `#777D73`, `danger` `#A12622`, plus its derived containers and `outlineVariant` `#7E8479`.
- The dark scheme already equals the Stitch dark token block except `outlineVariant` `#646B64`
  (Stitch `#424942`; the accepted 2026-10-24 correction). Its semantic caution values already match the
  approved palette.
- Raw-colour audit (P0-01): `Color(0x`, `Color.White`, and `Color.Black` appear only in
  `theme/ManijeroColors.kt` and the two theme tests. No screen, host module, or test outside
  `theme/` declares a colour literal, so the "one file owns the hexes" rule already holds and this
  feature must keep it.
- Card surfaces read `MaterialTheme.colorScheme.surface` in five places: `App.kt` assistant card
  (L707), source card (L783), notice bubble (L876), clarification chooser (L909), and
  `lands/LandListScreen.kt` land row (L199). `surfaceVariant` is used for the user bubble (`App.kt`
  L630) and the source excerpt block (L816). Seven screen roots paint `colorScheme.background`
  (Asistente, Mis terrenos, Añadir, Editar, Eliminar, Ayuda, Privacidad), plus the review board.
- The approved palette sets Stitch `background == surface == surfaceBright`, so leaving those five
  call sites on `surface` would put cards on the canvas colour; `surfaceContainerLowest` is the
  documented raised surface.
- `ManijeroTokens.kt` defines only shapes (4/12/16/24) and spacing (6/12/24/32/48). `ManijeroShapes` is
  referenced by `ManijeroTheme` (`shapes = ManijeroShapes.Material`) and by tests; `ManijeroSpacing` is
  referenced only by tests. Screens still use literal dp: `720.dp` caps in `App.kt`,
  `CoverageScreen.kt`, `PrivacyScreen.kt`, `LandListScreen.kt` and inline in the three land forms;
  `padding(horizontal = 24.dp, vertical = 32.dp)` in six screens; 16 dp card radius with 1 dp borders;
  4/8/12/16/20 dp inner spacing.
- `ManijeroTheme.kt` renders a review-only `ManijeroTokenBoard` with ten typed hex strings, a caution
  callout, an existing shipped error string, and a radio sample, plus light/dark/2× previews. At
  planning time the dark preview listed the same light token constants, so it under-reported the dark
  palette.
- `ManijeroColorsTest` (357 lines) is light-only: exact token values, one 35-pair text table and a
  9-pair non-text table with exact documented ratios, a default-leak comparison against
  `lightColorScheme()` with documented exclusions, semantic assertions, and WCAG helper anchors.
- `ManijeroDesignSystemTest` (86 lines) asserts scheme selection, a 36-role list equality for both
  schemes, a 19-pair contrast list with a threshold-by-index rule, semantic values, and a shape/spacing
  spot-check. The 36-role list and the index-based thresholds are brittle and are part of the rewrite.
- Documentation state: `DESIGN.md` already carries the approved Stitch palette, the two
  `outlineVariant` corrections, the chip table, and the contrast contract, with a "palette status"
  note saying the code lags; plan §3.1 is approved; `design-references/README.md` names the Stitch
  token blocks as palette authority; `docs/specs/shared_design_system.md` carries an append-only
  superseding note.
- `feature_list.json` currently lists 39 accepted features and no open feature;
  `./scripts/select-feature.sh --next` prints no next feature. The plan's §9 slicing is the
  authorization to add `design_token_refresh` and its successors; this spec adds only the first entry.
- The palette's documented ratios were recomputed on 2026-10-25 with the repository's own WCAG formula
  and had zero failures at the chosen thresholds; the per-pair numbers in `DESIGN.md` are the expected
  test values.

## Implementation plan and tasks

Ordered; each task ends with the stated check.

| Task | Work | Files | Done when |
|---|---|---|---|
| T1 | Apply the Stitch light token block verbatim, keep named light values, correct `outlineVariant` to `#757C71`, map `surface` to `surfaceContainerLowest` and role `surface` to the canvas value | `theme/ManijeroColors.kt` | Light scheme reads the documented values; no "derived" section remains |
| T2 | Apply the Stitch dark token block verbatim, correct `outlineVariant` to `#868E86`, keep every role explicit | `theme/ManijeroColors.kt` | Dark scheme equals the documented table; no `#646B64` left |
| T3 | Add `ecoContainer`/`onEcoContainer` to `ManijeroSemanticColors` with light/dark values and KDoc; refresh caution/emphasis KDoc ratios | `theme/ManijeroColors.kt` | Semantic local exposes four original fields plus the Ecológico pair |
| T4 | Add `Micro`/`Compact`/`Comfortable` spacing, `ManijeroIconSize`, and `ManijeroLayout` tokens; leave shapes and existing spacing names unchanged | `theme/ManijeroTokens.kt` | Values compile and match the spec table |
| T5 | Re-point the five card `surface` call sites to `surfaceContainerLowest`; change nothing else in those files | `App.kt`, `lands/LandListScreen.kt` | Diff is five colour-role lines |
| T6 | Rebuild the token board from theme roles/semantics with a computed-hex helper; add role, semantic, and chip rows; keep light/dark/large-text previews | `theme/ManijeroTheme.kt` | No typed hex remains; dark preview shows dark values; all four chip pairs carry text |
| T7 | Rewrite `ManijeroColorsTest` for both appearances: tokens, roles, default-leak, per-appearance documented-ratio text/non-text tables, chip pairs, caution pairs, semantic values, WCAG anchors | `commonTest/theme/ManijeroColorsTest.kt` | Tests fail on any single wrong value or ratio |
| T8 | Update `ManijeroDesignSystemTest`: role table for both schemes, threshold-explicit pair list, semantic incl. Ecológico, token assertions | `commonTest/theme/ManijeroDesignSystemTest.kt` | No index-based threshold; failures name the role/token |
| T9 | Align `DESIGN.md` (remove the superseded status note, record the Ecológico semantic pair, fix any disproved ratio) | `DESIGN.md` | Document and test state the same values |
| T10 | Run the focused command and record evidence; inspect the three board previews (deferred: no preview renderer on this host) | this appendix | Green command output recorded; board inspection recorded as deferred with its reason, never claimed as observed |

## Verification plan

- Focused: `./scripts/init.sh --feature design_token_refresh` runs the spec's two commands — the two
  shared theme test classes and the `commonMain` colour-literal scan (`Color(0x…)`, `Color.White`,
  `Color.Black`).
- Expected: `BUILD SUCCESSFUL`; both classes green; the scan prints nothing and exits 0. Before
  implementation the tier fails by design on the palette guard (`palette not refreshed: light primary
  #214624 missing`), because the pre-refresh tests still describe the old values and would otherwise
  pass on a no-op.
- Broader: `./scripts/init.sh --fast` covers the same shared tests plus contracts, backend, and
  evaluators, if the change is to be handed off beyond the focused tier. Backend collection needs
  `jsonschema` in the local `.venv` (installed on 2026-10-25, see findings).
- Manual: inspect `ManijeroTokenBoardPreview`, `...DarkPreview`, `...LargeTextPreview`; confirm swatch
  labels match their colours in both appearances, chip text reads on every chip, and the caution block
  and error line stay legible. Confirm one chat answer card and one land row still read as raised.
  Deferred on the implementation host: no board preview was rendered (see findings and evidence).
- Not proven by this feature: screen-reader output, focus order, keyboard operation, real-device
  enlarged-text layout of full screens, and any visual comparison with the Stitch PNGs. No automated
  UI/screenshot harness exists in this repository.

## Evidence to capture

- Focused command output, including the test class names and `BUILD SUCCESSFUL`.
- The token/role counts covered by the rewritten tests (tokens, roles per scheme, contrast pairs per
  appearance, chip pairs).
- A short manual-preview observation per appearance, dated, naming what was inspected — or a dated
  record that the inspection was deferred and why, never an implied observation.
- Any ratio that had to be corrected in `DESIGN.md`, with the recomputed value and reason.

## Implementation findings

Implemented on 2026-10-25; T1–T9 completed as planned. T10's focused command and evidence recording
are complete; its manual board inspection is deferred because no token-board preview was rendered on
this host (see evidence).

- **Light scheme** now carries the Stitch light token block verbatim. The snapshot values
  `ManijeroOlive800`, `ManijeroOlive900`, `ManijeroCanvas`, `ManijeroSurface`, `ManijeroTextPrimary`,
  `ManijeroTextSecondary`, `ManijeroBorder`, `ManijeroDanger`, `ManijeroCaution`,
  `ManijeroCautionSurface` and a new `ManijeroWhite` keep one name per colour; the previously derived
  light values (`primaryContainer`, `secondary*`, `tertiary*`, `surfaceVariant`, `inverse*`, `error*`,
  `surfaceTint`, the surface extremes) are now explicit `Manijero*` values from the export.
  `outlineVariant` is `#757C71`; `scrim` stays black.
- **Dark scheme** is the Stitch dark block verbatim with two deliberate differences: `outlineVariant`
  is `#868E86` instead of Stitch `#424942`, and `scrim` stays black. The dark `tertiary` family is the
  exported blue-grey. No `earth`/`sun` token was introduced.
- **Surface rule.** Role `surface` is the canvas (`#F9FAF4` / `#121612`), so the five card sites were
  re-pointed to `surfaceContainerLowest` (`App.kt` L707, L783, L876, L909 and
  `lands/LandListScreen.kt` L199). The user bubble and the source-excerpt block still read
  `surfaceVariant`. A scan for `colorScheme.surface` outside the container family is clean.
- **Ecológico pair.** `ManijeroSemanticColors` gained `ecoContainer`/`onEcoContainer`
  (`#C2EEBE`/`#002106` light, `#C7ECC6`/`#02210A` dark) because this Material version exposes no
  `primaryFixed`/`onPrimaryFixed` role. The light semantic set doubles as the local's default.
- **Tokens.** `ManijeroSpacing` gained `Micro`/`Compact`/`Comfortable`; `ManijeroIconSize` and
  `ManijeroLayout` are new. Shape values and existing spacing names are untouched.
- **Board.** The board reads every swatch from `MaterialTheme.colorScheme` or
  `LocalManijeroSemanticColors` and prints `Color.hexLabel()` of the rendered colour, so a label cannot
  drift from a typed value. It lists all 36 roles, all six semantic colours as labelled swatches with
  their computed hex (including `onCaution`), a caution callout block, a filled `onCaution`-on-`caution`
  sample, the error line, a selected/unselected radio sample, and the four chips with their ink.
  Preview names are unchanged (light board, dark board, 2× text). No preview was rendered on this host
  (see evidence), so the board's visual behavior is unverified rather than observed.
- **Ratio audit.** Recomputing every documented pair from the shipped tokens matched `DESIGN.md`
  exactly, so no numeric correction was needed. One documented anchor role was wrong and is fixed: the
  Neutral chip pair is `surfaceContainerHighest`/`onSurface`, not `surfaceVariant`/`onSurface`
  (identical values in light, different in dark; the documented 13.29 light / 7.92 dark ratios only
  hold on `surfaceContainerHighest`). `DESIGN.md` now states that the palette is implemented and
  describes the Ecológico pair as semantic tokens.
- **Environment.** The local `.venv` lacked `jsonschema`, which `backend/tests/test_pac_answer_eval.py`
  imports, so `--fast` and `--verify` failed during collection before reaching this feature's checks.
  Installing `jsonschema 4.26.0` into the untracked venv let both tiers pass; no repository dependency
  was added.

## Validator checklist

- [ ] Light and dark role values equal `DESIGN.md` exactly; only `outlineVariant` deviates from the
      Stitch token blocks, in both modes.
- [ ] `surface` role equals the canvas value and cards read `surfaceContainerLowest`; no screen keeps a
      card on the canvas colour.
- [ ] Every brand-bearing role is explicit and differs from the Material default, with the documented
      exclusions only.
- [ ] No `earth`/`sun` token or role exists; caution and error remain the only status hues.
- [ ] `ManijeroSemanticColors` carries the four original fields plus the Ecológico pair, with both
      appearances provided through the local.
- [ ] Chip pairs for Secano, Regadío, Ecológico, and Neutral are asserted at ≥4.5:1 in both modes and
      use the documented anchors.
- [ ] The contrast tables assert the documented ratios exactly, cover both appearances, and include
      text, boundary, caution, error, tonal/inverse, and chip pairs.
- [ ] `ManijeroTokens.kt` adds only the documented tokens; existing shape and spacing names/values are
      unchanged.
- [ ] The token board derives hex text from colours, shows both appearances correctly, and every chip
      row carries visible text.
- [ ] The `commonMain` colour-literal scan finds nothing outside `ManijeroColors.kt`.
- [ ] No copy, layout, navigation, state, persistence, request, `contracts/`, `backend/`, or Gradle
      change; the only screen diff is the five surface-role lines.
- [ ] `design-references/stitch/` is byte-identical; `DESIGN.md` no longer claims the code lags the
      palette.
- [ ] Verification evidence is recorded honestly, including what was not tested.

## Feature evidence

Self-verified on 2026-10-25 on macOS, with the system appearance set to dark; re-verified the same day
after the review-board and documentation repairs. Feature status is `passing`: implemented and
self-verified, awaiting independent validation.

- **Focused gate** — `./scripts/init.sh --feature design_token_refresh`: exit 0, `BUILD SUCCESSFUL`;
  both palette greps found their values, and the colour-literal scan (`Color(0x…)`, `Color.White`,
  `Color.Black`) outside `theme/ManijeroColors.kt` found nothing. An explicit
  `./gradlew :shared:jvmTest --tests ManijeroColorsTest --tests ManijeroDesignSystemTest --rerun`
  exited 0, recompiled the board change, and ran both classes: `ManijeroColorsTest` 14 tests,
  `ManijeroDesignSystemTest` 4 tests, 0 failures, 0 errors.
- **Coverage of the rewritten tests** — 35 light text pairs, 12 light non-text pairs, 29 dark text
  pairs, and 9 dark non-text pairs asserted at their documented values and at 4.5:1 (text) / 3:1
  (non-text); 4 chip pairs per appearance; both schemes compared role-by-role against 36 expected
  colours; every brand-bearing role compared against the Material default scheme computed at runtime;
  semantic values, the WCAG black/white anchors, and the geometry scale asserted.
- **Fast tier** — `./scripts/init.sh --fast`: exit 0, "All 9 offline checks passed" (shared host tests,
  contract examples, backend pytest, source catalog, retrieval, generation, abstention, clarification,
  land safety); 200 shared host tests and 618 backend tests, 0 failures.
- **Full gate** — `./scripts/init.sh --verify`: exit 0; the fast tier plus
  `:shared:testAndroidHostTest` (186 tests, 0 failures), `:androidApp:assembleDebug`, and
  `:desktopApp:build` all succeeded. The desktop compile stayed up-to-date through ABI avoidance after
  the board-body edit; the shared JVM compile executed in the focused run.
- **Runtime smoke** — `./gradlew :desktopApp:run` opened the window "Manijero" (912×712) with no
  exception in the log. The window content samples the dark canvas (`#111712`, within a step per
  channel of the documented `#121612`), so a real Desktop host renders the dark app palette after the
  refresh. That is the app canvas, not the token board, and is not evidence about the board. Re-running
  with `-Dapple.awt.application.appearance=NSAppearanceNameAqua` still rendered dark: Compose follows
  the macOS system appearance, which was not toggled.
- **Board preview deferred, not observed** — no token-board preview was rendered on this host in any of
  the three states (light, dark, or 2× text). The repository has no headless Compose preview renderer,
  the macOS system appearance is dark and was not toggled, and the Desktop window shows the app canvas
  rather than the review board, so there is no artifact for a board observation. The palette values
  themselves are proven by the exact-value and contrast tests in both appearances; the board's visual
  layout, its 2× text reflow, and its dark appearance remain unverified.
- **Not proven** — screen-reader output, focus order, keyboard operation, and the enlarged-text layout
  of full app screens: unchanged by this feature and still owned by the accessibility audit.
- **No scope drift** — the only screen diff is the five `surface`-role lines; no copy, layout,
  navigation, state, persistence, request, `contracts/`, `backend/`, Gradle, or `design-references/`
  change.

Independent validation ran twice on 2026-10-25. The first pass returned `revise` on documentation
only (stale `current-state.md` claim, future tense in `DESIGN.md`, an unlabelled `onCaution` row, and
evidence implying a dark-board observation); the repair pass fixed those and reran the gates, and the
second pass accepted. The acceptance record is
[`docs/validations/design_token_refresh.md`](../../validations/design_token_refresh.md).
