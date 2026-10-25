# Validation: `brand_vectors`

**Verdict: accept** — 2026-10-25 (second pass; pass 1 returned `revise` for documentation only)

Independent validation against [`brand_vectors.md`](../specs/brand_vectors.md), its appendix
checklist, `DESIGN.md`, `CONSTRAINTS.md`, and `PROGRESS.md` in the `feature/brand_vectors` worktree
(base `main` @ `8b3f680`). Pass 1 `revise` on M1 (the harness doc still declared 8 Desktop / 4 Android
goldens) plus L1–L4 doc nits → repair pass → pass 2 `accept`. No code, asset, test behaviour, Gradle,
theme, string, backend, contract, or golden change was required.

## What was checked

- **Inventory and geometry.** Independent parse of all eighteen files: `brand_mark.xml` 32×32,
  `olive_branch.xml` 96×96, and sixteen `ic_*.xml` on a 24×24 viewport with stroke 2, round caps/joins,
  no fill, and painted extent inside 2–22 (tightest: `ic_warning` x 2.30–21.70, `ic_retry` y 3.66–20.90).
  The placeholder is untouched and excluded (19 files, 18 in inventory).
- **Colour and wrappers.** Only `#000000`/`#00000000` literals; no tint, gradient, `aapt:attr`, clip
  path, or external reference. `ManijeroIcon` requires `contentDescription`, uses `painterResource`,
  exact size, and `LocalContentColor`; the mark and illustration expose no description or colour
  parameter and use `primary` / `primaryContainer`+`onPrimaryContainer`, with the halo in Compose.
- **No adoption or scope drift.** No screen, `App.kt`, theme, or string reference reaches the `design`
  package; board labels are not shipped copy; `git status` over screens, theme, strings, Gradle,
  backend, contracts, and `design-references/` is empty; no `material-icons-*` entry exists.
- **Goldens and visual review.** Four new 900×1200 PNGs with distinct hashes, light ≠ dark; the twelve
  pre-existing PNGs are byte-identical before, after, and across the repair. All four opened: sixteen
  glyphs legible at 24 dp, `ic_search`/`ic_clear` distinct at 20 dp, the mark at 28/32/48 dp, the sprig
  inside its halo at 160/200 dp.
- **Test quality.** The inventory test named all eighteen accessors (so a missing/renamed file fails to
  compile), cross-checked the registry, asserted distinctness, and excluded the placeholder; 4 tests.
  It was later removed on review — presence is now compile-enforced by the board's references.

## Verification (independently run)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature brand_vectors` (pass 1, twice, and after the repair) | exit 0 — 4 inventory tests; `verifyScreenshots` green (10 Desktop + 6 Android); gates silent-pass |
| `./scripts/init.sh --verify` (pass 1 and after the repair) | exit 0 — fast tier, 9 offline checks, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` |
| `MANIJERO_PYTHON=…/backend/.venv/bin/python ./scripts/init.sh --backend-tests` | 618 passed |
| Parsed `jvmTest`/`testAndroidHostTest` result XML | 204 tests / 24 classes and 190 / 20, zero failures |
| Goldens | `git diff --exit-code` over both screenshot dirs exit 0 in four runs; four new images 900×1200 with distinct hashes |
| Gate probes | corrected `material-icons` gate exits 0 without a match and 1 with one; the old `&&` form exited 1 both ways |

Not re-run: an iOS compile (no tier covers it). No golden was recorded or re-recorded by the validator.

## Findings

Pass 1 `revise`, documentation only: **M1** `docs/screenshot-regression.md` still said 8 Desktop / 4
Android, four scenes, and one Android viewport; it needed the new counts, the board as a subject, both
qualifiers, and the dedicated-class allowance. **L1** `CONSTRAINTS.md` cited a non-existent
`shared_theme` → now `design_token_refresh`. **L2** stale "eight-column" comment → "four-column".
**L3** `DESIGN.md` claimed `ManijeroShapes` reuse (nothing does) → removed. **L4** stray blank line →
removed. Pass 2 `accept`: all five closed, nothing unrelated moved, focused tier and full gate green.

All appendix checklist items passed. The contract's last gate was corrected from
`grep … && { exit 1; }` to `if grep …; then exit 1; fi` before validation (the old form returned failure
exactly when the rule passed) and was probed to fail when a `material-icons` dependency exists.

## Honest limits

- Host renders only: Compose Desktop (macOS-font-pinned) and Robolectric SDK 35, density 1, font scale
  1, LTR, `es-ES`; no device, emulator, iOS, screen-reader, touch-target, or real-screen claim, and no
  screen adopts the assets.
- No iOS target was compiled; "all targets decode these vectors" rests on the documented XML subset.
- Per-file geometry, colour, and unsupported-feature rules are enforced by the focused shell gates; the
  inventory is compile-enforced by the board.
- Owner sign-off now covers sixteen images (twelve app baselines + four board captures); the mechanism
  and this review exist, product-owner approval does not.

## Security

No finding: static XML masks plus pure Compose wrappers; no network, storage, permissions, personal or
land data, logging, or dynamic content; no new dependency, module, or runtime path.

## Post-acceptance follow-ups (2026-10-25)

Both were review clean-ups with no behaviour or pixel change, so the verdict stands.

- **Board moved to test sources.** `BrandVectorBoard` had no production consumer (only the two
  screenshot classes import it), so it moved to
  `shared/src/commonTest/kotlin/com/jamarglex/manijero/design/BrandVectorBoard.kt` and dropped its
  previews. The three wrappers stay in `commonMain` as the API later features adopt. Verified: focused
  block exit 0 and SHA-256 of all sixteen goldens identical before and after
  (`refactor: move brand vector board to test sources`).
- **Inventory test removed.** `BrandVectorSetTest` was a third copy of the eighteen names. Presence is
  compile-enforced by the board, style and file count by the shell gates, rendering by the goldens.
  Verified: focused block exit 0, `--verify` exit 0, all sixteen goldens byte-identical
  (`test: remove redundant brand vector inventory test`).
