# Validation: `screenshot_regression_tests`

**Verdict: accept** — 2026-10-25

Independent validation of the uncommitted implementation against
[`docs/specs/screenshot_regression_tests.md`](../specs/screenshot_regression_tests.md), the
appendix checklist in
[`screenshot_regression_tests.appendix.md`](../specs/screenshot_regression_tests.appendix.md),
`docs/design/ui-refresh-plan.md` §§10.2/10.4, and `PROGRESS.md`. All probes were disposable and were
reverted; the worktree is back to the implementer's state (`git status` shows only the feature's own
modified and untracked files, `git diff --check` clean).

Environment used for every run below: macOS 27.0.1 **arm64**, Temurin JDK 17.0.6, Gradle 9.8.0
(wrapper), Kotlin 2.4.20, Compose Multiplatform 1.12.1, Roborazzi 1.77.0.

## What was checked

**Scope is test-only.** `git status`/`git diff` contain exactly three modified files
(`feature_list.json` status `not_started` → `passing`; `gradle/libs.versions.toml`;
`shared/build.gradle.kts`) plus the new test sources, four PNG goldens, the feature spec and
appendix, and this acceptance record.
No production Compose, `commonMain`, `backend/`, `contracts/`, `knowledge/`, `design-references/`,
navigation, data, or `scripts/init.sh` change; no new module, no new target, no CI workflow file
touched (`.github/workflows/gate.yml` is unmodified).

**Wiring.** `shared/build.gradle.kts` adds Roborazzi/Compose-Desktop test dependencies to
`jvmTest` only and registers two `Test` tasks sharing the JVM test classpath:
`:shared:verifyScreenshots` (`record=false`, `verify=true`, read-only) and
`:shared:recordScreenshots` (`record=true`, `verify=false`, explicit). Both filter to
`com.jamarglex.manijero.screenshots.*` with `isFailOnNoMatchingTests = true`, use
`outputs.upToDateWhen { false }`, and write artifacts to
`shared/build/reports/screenshot-regression/` (gitignored). `:shared:jvmTest` excludes that package.
No Roborazzi Gradle plugin is applied.

**Tests render the real shared UI.** `SharedScreenshotsTest` imports `ChatHomeScreen` and
`LandListScreen` from `commonMain` and pins width/height per capture, explicit
`ManijeroTheme(darkTheme = …)`, `Density(1f, fontScale = 1f)`, LTR, `Locale.setDefault("es-ES")` per
test, and code-owned `ScreenshotFixtures` with no clock, network, disk, or backend access.
`requireScreenshotMode()` fails loudly if neither record nor verify mode is active.

**Versions and dependency isolation (independent check).** `:shared:dependencies
--configuration jvmTestRuntimeClasspath` resolves `io.github.takahirom.roborazzi:roborazzi-compose-desktop:1.77.0`
and `org.jetbrains.compose.ui:ui-test-junit4-desktop:1.12.1`;
`:shared:dependencies --configuration androidUnitTestRuntimeClasspath` contains no Roborazzi entry,
so the Android/iOS graphs are untouched.

**Threshold rationale (independent check of the library, not the prose).** Disassembled
`roborazzi-core-jvm-1.77.0.jar`: `RoborazziOptions.CompareOptions.DefaultImageComparator` is
`SimpleImageComparator(0.007f)` and the default result validator is `ThresholdValidator(0f)`. So the
appendix's claim is accurate: the suite sets an explicit `changeThreshold = 0.001F` on top of the
library's default per-pixel tolerance, i.e. it does *not* inherit an undocumented default.

**Baseline images reviewed at full size (validator's own review, not the implementer's).**
All four PNGs were opened and judged:

- `chat_home_idle_light.png` (900×1200, light) — `ChatHomeScreen` idle: title "¿En qué puedo
  ayudarte?", subtitle, three suggestion buttons, composer placeholder, disabled "Preguntar",
  "Mis terrenos", device-only privacy note, "Privacidad y ayuda", "Qué cubre la app". Real render,
  nothing blank, clipped, or overlapping.
- `chat_answered_source_dark.png` (900×1200, dark) — user bubble, assistant answer with
  "Tiene en cuenta todos tus terrenos.", the `[1]` citation marker, "Fuentes"/"Fuente 1" card
  (title, issuing body, document part, "Comprobado el 01/10/2026", excerpt, "Abrir documento
  oficial"), suggestions, composer. The bottom edge cuts the privacy note mid-line, as documented in
  the test KDoc and appendix.
- `land_list_light.png` (900×1000, light) — "Mis terrenos", two distinct land cards (`Los Olivos`
  known attributes, `La Loma` with "Producción: No lo sé"), "Editar"/"Eliminar", "Añadir terreno",
  "Volver".
- `land_list_empty_dark.png` (900×800, dark) — empty-state sentence, "Añadir terreno", "Volver".

They depict the claimed shared screens/states in light *and* dark, are four distinct frames, and are
not duplicates or placeholder blanks. Sizes match the documented matrix exactly.

## Verification (independently run)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature screenshot_regression_tests` | **PASS**, exit 0 — the spec's `verify` block resolves to `./gradlew :shared:verifyScreenshots`; 4/4 `PASSED` (`chatHomeIdleLight`, `chatAnsweredSourceDark`, `landListLight`, `landListEmptyDark`) |
| `./scripts/init.sh --fast` | **PASS**, exit 0 — all 9 offline checks, incl. `:shared:jvmTest` |
| `./gradlew :shared:jvmTest --rerun-tasks` | **PASS** — 23 suites, 200 tests, 0 failures; result XML contains no `SharedScreenshotsTest` |
| `./gradlew :shared:check --dry-run` | no screenshot task in the graph (`jvmTest`/`testAndroidHostTest` only) |
| `./gradlew :shared:verifyScreenshots --rerun-tasks --no-configuration-cache` with `local.properties` removed and `ANDROID_HOME`/`ANDROID_SDK_ROOT` unset | **PASS**, exit 0, 4/4 — no Android SDK needed; `local.properties` restored |
| `git diff --check` | **PASS** |

### Read-only proof for the goldens (SHA-256 before/after)

Pristine checksums (unchanged across every verify run, including the failing probes):

```
6f256ca99c29812278238def87b2b73d729072a41f3545c8c65b36bc87a1f69f  chat_answered_source_dark.png
7cb4959d66e999a49dad30f7dffbde81accc978146168ec55a23bc445c7ae0e4  chat_home_idle_light.png
f296302e8b2ef3014146cb9f5d25279f8659934db119d93cee79b3e620fe4841  land_list_empty_dark.png
f6475a3982eb7007a4f33f750d6ed4331a2d0dfdb6036335e6721258fe418d0f  land_list_light.png
```

A passing verify writes only `shared/build/reports/screenshot-regression/results/*.json`
(`"type":"unchanged"`); the goldens directory stays byte-identical and `git status` does not change.

### Probe A — real difference fails and leaves reviewable artifacts (own probe, reverted)

Temporarily changed one production render input,
`shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt:447`,
`Arrangement.spacedBy(20.dp)` → `28.dp`, then ran `./gradlew :shared:verifyScreenshots`:

- **exit 1**, `4 tests completed, 2 failed` — `chatHomeIdleLight` and `chatAnsweredSourceDark` failed
  with `AssertionError` at `RoborazziOptions.common.kt:327`; the two lands captures passed (the
  change does not touch that screen);
- artifacts left for review under `shared/build/reports/screenshot-regression/`:
  `chat_home_idle_light_actual.png` (50,559 B), `chat_home_idle_light_compare.png` (195,625 B),
  `chat_answered_source_dark_actual.png` (94,066 B), `chat_answered_source_dark_compare.png`
  (316,944 B), plus result JSON with `"type":"changed"` and `diff_percentage` **0.04444** and
  **0.1275** — far above the 0.001 threshold;
- the compare image was opened: left = committed golden, middle = diff heat map (suggestion rows,
  labels, composer and footer shifted down), right = current render — a genuine layout change, not
  noise;
- the four goldens were **unchanged** by the failing run; `App.kt` was restored from a backup
  (`git diff` empty for that file) and verify passed again.

### Probe B — a missing golden fails closed and is not silently re-created (own probe, reverted)

Moved `land_list_light.png` aside and ran verify: **exit 1**, 1 failed / 3 passed, result
`"type":"added"`, `_actual`/`_compare` written only under `build/reports/…`, and the goldens
directory stayed without the PNG — verification did not recreate a baseline. Golden restored
byte-identical.

### Probe C — recording is explicit, selective, and never on the verify path (own probe, reverted)

With the same temporary 20→28 dp change, `./gradlew :shared:recordScreenshots` exited 0 and rewrote
**exactly** the two affected goldens (`chat_home_idle_light` 7cb4959d… → 3200e713…;
`chat_answered_source_dark` 6f256ca9… → acbeea4f…); `land_list_light` and `land_list_empty_dark`
stayed byte-identical. The re-recorded image was opened and shows the wider spacing. This reproduces
the implementer's reported checksums independently. Pristine goldens and `App.kt` were restored, and
verify passed against them.

### Probe D — same-host determinism (own probe)

`./gradlew :shared:recordScreenshots` with no code change rewrote all four goldens with
**byte-identical** SHA-256 values. Combined with Probe C, repeated same-host rendering is
byte-exact, so the comparison gate is not sitting on a noisy signal.

### Probe cleanliness

After all probes: `git status` shows only the feature's own files (listed at the top), `git diff`
for `App.kt` is empty, the four goldens match the pristine checksums, and the final verify run is
green. Probe leftovers live only in gitignored `shared/build/`.

## Checks passed / failed

| Appendix checklist item | Result |
|---|---|
| Scope is test-only; no production UI or behavior changed | **PASS** |
| Roborazzi/tooling versions pinned and compatible; no unrelated upgrade or module | **PASS** (1.77.0 / CMP 1.12.1 / Kotlin 2.4.20 unchanged) |
| Captures shared UI on Desktop JVM with stable fixtures, dimensions, appearance, font scale, locale | **PASS** |
| Focused command runs screenshot verification, needs no Android SDK/emulator, reachable via `--feature` | **PASS** |
| Verify mode read-only for baselines; a changed render fails with reviewable diff artifacts | **PASS** (Probes A and B) |
| Recording explicit, documented, human-reviewed; baselines match reviewed output | **PASS** on the mechanism and docs (Probe C, README); the human *sign-off* is a residual manual step, see below |
| Threshold rationale explicit and not hiding meaningful regressions | **PASS with a bounded caveat** (see risks) |
| Coverage/limitations reported accurately; no Android/iOS/accessibility/behavior/usability claim | **PASS** — spec, appendix, README, and test KDoc all bound the claim to Desktop JVM frames |
| Progress/status/session-log consistent with the validation result | **Pending acceptance update** (see follow-up) |

No failed check. Findings that would need `revise`: none.

## Considered risks and limitations

- **No CI enforcement.** The suite is excluded from `:shared:jvmTest`, `./scripts/init.sh --fast`,
  and the `ubuntu-latest` CI gate, so the gate runs only when a developer or reviewer invokes
  `:shared:verifyScreenshots`. This is the spec's own documented decision (host fonts, macOS-recorded
  goldens vs a Linux runner) and the feature spec forbids adding a CI workflow as part of this
  feature, so it is a limitation rather than a defect — but the plan's §10.4 line "CI runs verify
  only" is not yet realized anywhere. Wiring a Linux-recorded baseline set and a verify-only CI step
  remains a separate, explicit decision.
- **Host-pinned goldens.** These four PNGs are only valid on the recording host's font stack. The
  validator's host (macOS arm64, Temurin 17.0.6) reproduced them byte-for-byte, so they are current
  and internally consistent there; a different OS, font set, or JDK rendering stack must record its
  own reviewed baselines.
- **Threshold sensitivity.** `changeThreshold = 0.001` is 1,080 px on 900×1200 (900 px and 720 px on
  the lands captures). Given Probe D showed byte-exact repeated renders, a change of one small glyph
  region under ~1,000 px would be absorbed. The current goldens contain no small icons, and the
  documented rationale is honest, but tightening the threshold (or recording measured cross-run noise)
  would be a cheap future improvement.
- **Four captures only.** Passing proves these four frames match; loading, error, clarification, form
  editing, help/privacy/coverage pages, other window sizes, other locales, and 2× text are not gated.
- **Cosmetic cropping in one golden.** `chat_answered_source_dark.png` ends inside the privacy note,
  cutting a text line at the frame edge. It is documented in the test KDoc, appendix, and README and
  does not weaken the gate, but a re-record at a taller viewport would be more presentable.
- **No Android/iOS rendering, accessibility, usability, legal, or behaviour proof.** Verified: every
  claim-bearing document says so explicitly, and the JVM test class does not exercise the Android
  layoutlib, an emulator, iOS, or any backend.
- **`--verify` was not rerun in full.** The validator ran the focused task, `--fast`, a forced
  `:shared:jvmTest`, `:shared:check --dry-run`, and the dependency graphs; the change is test-only and
  a configuration failure would surface in every task above. Android APK / Desktop packaging were not
  rebuilt in this pass.

## Residual manual review requirement

The mechanism and documentation satisfy the "explicit, human-reviewed recording" contract, but the
four committed PNGs still need a **human owner sign-off**: open each image at full size and confirm it
is the intended design (`chat_home_idle_light`, `chat_answered_source_dark`, `land_list_light`,
`land_list_empty_dark`), recorded on a macOS host matching the reviewer's font stack (this validator
and the implementer both ran on macOS arm64 / Temurin 17.0.6). Until that sign-off, the baselines are
"reviewed by the implementer and the validator", not product-owner-approved. Beyond the images, the
reviewer does not gain any accessibility, usability, Android, or iOS assurance from this feature.

## Security and documentation

- No security or privacy issue: the diff is Gradle test wiring, test fixtures with synthetic land data
  and already-reviewed contract copy, four PNGs, and docs. No network, storage, permission, logging,
  authentication, or data-flow change; no personal land data is rendered or persisted; capture
  artifacts live in the gitignored build tree.
- Documentation is consistent and bounded: the goldens README next to the images documents verify,
  artifact locations, the explicit record procedure with a per-image checklist and the "do not
  re-record to make red green" rule, the fixed render conditions, the threshold, and the limitations;
  spec, appendix, and test KDoc agree with the code. `scripts/init.sh` did not need a change because
  `--feature` already executes the spec's verify block. `ARCHITECTURE.md`, `CONSTRAINTS.md`,
  `DESIGN.md`, and `AGENTS.md` were correctly left untouched.
- Follow-up for the orchestrator on acceptance: update `PROGRESS.md` (line 19 still says the feature
  is `not_started` and "until it lands, UI evidence stays manual") with the precise Desktop-JVM gated
  states and the retained platform/accessibility limits, set `feature_list.json` to `accepted`, and
  add the single pointer line to `docs/progress/session-log.md`. The presenter also needs to decide
  whether a human-owner image sign-off is recorded before moving to `accepted` or shortly after.

## Post-acceptance follow-up (2026-10-25)

Two follow-ups landed after this acceptance record without re-running the independent validator:

1. The suite was split by screen into `ChatHomeScreenshotsTest`, `LandListScreenshotsTest`, and the
   shared `ScreenshotTestSupport`; captures, fixtures, goldens, threshold, and tasks did not change.
2. One phone-width viewport (360×800 dp) was added, so each of the four scenes now has a desktop and
   a narrow capture (eight goldens total). Recording used the explicit `:shared:recordScreenshots`
   task; the original four goldens stayed byte-identical (only four `*_phone.png` files were added),
   and all eight pass `:shared:verifyScreenshots`.

The original `accept` verdict still applies to the verified mechanism, the four original images, and
the bounded claims. The four new phone-width images still need the same human owner sign-off, and
they remain Desktop JVM renders at a narrow size: they add no Android/iOS, accessibility, usability,
or behavior evidence.
