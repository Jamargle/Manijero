# Validation — `add_land`

## Verdict

**Accept** — 2026-10-12. Independent validation of the uncommitted `add_land`
implementation against `docs/specs/add_land.md`.

Feature id: `add_land`. Spec: `docs/specs/add_land.md`. Claimed status:
`passing` in `feature_list.json` (self-verified by the implementer).
Recommended state update: orchestrator may set `status` to `accepted`.

## Review target

- Modified: `shared/.../App.kt`, `shared/.../composeResources/values/strings.xml`,
  `androidApp/.../MainActivity.kt`, `desktopApp/.../main.kt`, `PROGRESS.md`,
  `feature_list.json`.
- New: `shared/.../lands/AddLandState.kt`, `shared/.../lands/AddLandScreen.kt`,
  `shared/src/commonTest/.../lands/AddLandStateTest.kt`,
  `shared/src/jvmTest/.../lands/AddLandDesktopStoreTest.kt`, `docs/specs/add_land.md`.

## Independent checks and results

Commands were re-run by the validator; `--rerun-tasks` was used on the tests so
the result is an actual execution, not a cached `UP-TO-DATE` result.

- `./scripts/init.sh --verify` (`:shared:jvmTest :shared:testAndroidHostTest
  :androidApp:assembleDebug :desktopApp:build`): **BUILD SUCCESSFUL** (exit 0).
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks`:
  **BUILD SUCCESSFUL**, 46 tasks executed. Test XML report totals:
  - `:shared:jvmTest` — **21 tests, 0 failures, 0 errors, 0 skipped**
    (includes `AddLandStateTest` 11 and `AddLandDesktopStoreTest` 1 against the
    real `FileLandStorage`).
  - `:shared:testAndroidHostTest` — **20 tests, 0 failures, 0 errors, 0 skipped**
    (includes the 11 `AddLandStateTest` cases and the pre-existing repository tests).
- `:androidApp:assembleDebug` produced
  `androidApp/build/outputs/apk/debug/androidApp-debug.apk` (fresh, 32 MB).
- `:desktopApp:build` succeeded.
- Desktop startup smoke: launched `:desktopApp:run`; `com.jamarglex.manijero.MainKt`
  started with the injected file store and ran for ~45 s with **no startup
  exception** until the validator terminated it (Gradle reported the expected
  exit 143 / SIGTERM). No `MainKt` or Gradle process was left running.
- `git diff --check`: clean.
- Scope check: `git status` shows only the six modified files and five new files
  above; no `iosApp`, `backend`, `contracts`, Gradle build-logic, or
  dependency changes.

## Acceptance-scenario mapping

- **Save only the required information** — `App` routes `Mis terrenos` to
  `AddLandScreen`; default `AddLandState` has both enums `UNKNOWN`; saving builds
  a trimmed `LandDraft` and calls `LandRepository.create` once, then returns to
  chat with the resource string `add_land_saved`
  ("El terreno se ha guardado en este dispositivo."). Covered by
  `AddLandStateTest` (`name only land is saved with unknown attributes ...`,
  blank-name/error tests). **Pass (logic + tests).**
- **Save known attributes** — `IRRIGATED`/`ORGANIC` map through
  `WaterRegimeSelected`/`ProductionMethodSelected`; reopen retention asserted by
  `AddLandDesktopStoreTest` against the real file store and by
  `two lands saved from the form both survive reopening`. **Pass.**
- **Do not force a guess** — `No lo sé` (`UNKNOWN`) is offered first and selected
  by default for both groups; `MIXED` is a separate deliberate choice with its own
  copy. **Pass.**
- **Correct a missing name** — `SaveClicked` sets `showNameError` for blank/
  whitespace names and `toDraftOrNull()` returns `null`, so no write occurs; raw
  text and selections are preserved via `copy`. Covered by tests. **Pass.**
- **Recover from a local save failure** — `runCatching { repository.create(draft)
  }.isSuccess` swallows the failure, stays on the form, and reduces to
  `SaveFailed`; all values remain; no navigation or success feedback. Covered by
  `failed save keeps values, shows plain error, and allows retry` and the
  `FailingStorage` fake. **Pass.**
- **Leave without saving** — `Cancelar` resets state and returns to chat without a
  write; covered by `leaving the form without saving writes no record`. **Pass.**

## Validator checklist

- [x] Only required input is a nonblank trimmed name; blank input writes no record.
- [x] Unknown is visible and independent for water and production; mixed is not
      used as a substitute.
- [x] Name-only and known water/production lands save through `LandRepository`
      and persist after reopening (real file store on Desktop; repository
      semantics shared across platforms).
- [x] Municipality optional; no area, notes, precise identifier, or legal
      eligibility input collected (`toDraftOrNull` omits both).
- [x] Save failure retains input, gives plain Spanish recovery copy, and exposes
      neither land data nor raw exception text (no logging added anywhere).
- [x] Product UI/behavior is in `commonMain`; only storage construction is
      platform-specific (`MainActivity.kt`, `main.kt`).
- [~] UI text and accessibility labels are resource-backed (verified); large-text,
      keyboard-focus, and screen-reader behavior were **not** executed — no
      emulator/device and no Compose UI-test harness; the spec defers this to the
      `land_form_accessibility` feature and the implementer reported it honestly.
- [x] Focused tests and feasible builds pass (`./scripts/init.sh --verify` green).
- [x] No unrelated feature, backend, persistence-format, cloud, or iOS-release
      work included.

## Findings

No blocking or revise-level findings.

Minor, non-blocking observations (optional follow-ups, not acceptance gates):

1. **Android system back** — the form relies on the visible `Cancelar` control
   (which satisfies the "Leave without saving" scenario). A system/gesture back
   press is not intercepted, so on Android it exits the Activity instead of
   returning to chat. Consider a `BackHandler` when `land_form_accessibility`
   lands.
2. **Single-select group semantics** — radio rows use `selectable` +
   `Role.RadioButton` (good); adding `Modifier.selectableGroup()` to each group
   column and an explicit `error()` semantics property on the name field would
   strengthen assistive-technology output. Standard Material 3 patterns are used
   today, so this is polish.
3. **Tooling** — the feature-validator skill references
   `references/validation-rubric.md` and `references/security-checklist.md`, which
   are absent from `.agents/skills/feature-validator/` in this checkout. The
   embedded rubric and the spec's checklist were applied instead. Repo-hygiene
   note only.

## Security and privacy assessment

Scoped to this feature and diff: **no relevant issues found**.

- No network calls, accounts, or telemetry added; land data stays in the local
  repository only.
- No `println`/`Log`/`printStackTrace`/logger usage in any changed file; the save
  failure path catches the exception without logging names, municipality, or raw
  exception text.
- Failure copy is generic ("No se ha podido guardar el terreno. Puedes
  intentarlo otra vez.") and success copy is device-scoped
  ("... en este dispositivo."), so no cloud-backup or confidentiality claim.
- Desktop store path `~/.manijero/lands-v1.txt` and Android `manijero_lands`
  SharedPreferences are stable, documented, and unchanged in format.
- No access-control, injection, or serialization changes; `LandStoreFormat` and
  both adapters are untouched.

## Documentation and harness state

- `feature_list.json` evidence matches the independently reproduced results;
  `passing` is the correct pre-acceptance state.
- `PROGRESS.md` records the implementation and honest unverified items.
- `scripts/init.sh --verify` is a real gate (runs tests/builds and fails on error), not a
  command printer.
- No persistent E2E harness exists in this repo; the spec justifies focused
  pure-state/repository tests plus manual smoke, consistent with the validator
  hierarchy.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `docs/archive/build-brief.md`,
  `docs/domain-model.md`, `docs/risks-and-open-questions.md` were correctly left
  unchanged; no `ARCHITECTURE.md`/`CONSTRAINTS.md` exist and none were needed.

## Required follow-up

None for acceptance. Optional: intercept Android system back and add radio-group
semantics during the deferred `land_form_accessibility` feature; run the manual
large-text/keyboard/screen-reader smoke that could not be executed here.
