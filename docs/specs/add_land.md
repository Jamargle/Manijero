# Feature Spec: `add_land`

## Source metadata

- **Feature:** `add_land` — Add a land (`lands`)
- **Status at planning:** `not_started`; depends on accepted `local_land_store`.
- **Source behavior:** A person can add a named land and can leave attributes unknown rather than guessing.
- **Feature verification:** Save one land with only a name and another with known water and production details.

## Goal and boundaries

Provide an Android/Desktop shared Compose path from the existing chat home to a short Spanish “Añadir terreno” form. Saving creates exactly one `Land` through the accepted local repository and leaves unknown water and production attributes explicitly `UNKNOWN`.

**In scope**

- Name (required), municipality (optional), water regime, and production method.
- Visible “No lo sé” choices for the two enum fields, selected by default.
- Required-name validation, an understandable persistence failure, cancel/back, and successful-save confirmation.
- Platform composition-root wiring to the existing Android `SharedPreferencesLandStorage` and Desktop `FileLandStorage`.

**Non-goals**

- A saved-land list, land detail screen, editing, removal, selection for chat, or a general navigation framework.
- Area and free-text notes inputs. They remain persisted-domain fields, but are deliberately not collected in this short first form pending product validation.
- Accounts, backup/export, cloud sync, map/SIGPAC fields, network calls, or disclosure UI.
- iOS MVP support. Do not make Android/JVM-specific APIs part of shared UI or business logic.

## Job story

When I want the assistant to know the basic differences between my olive lands, I want to save a simple named land without being forced to know its technical details, so I can continue using the app without guessing.

## Acceptance scenarios

### Save only the required information

Given the chat home is visible and local storage is available, when the person opens `Mis terrenos`, enters `Los Olivos`, keeps both choices as `No lo sé`, and selects `Guardar terreno`, then one local record is created with the trimmed name and `UNKNOWN` water and production values, and Spanish success feedback is visible.

### Save known attributes

Given the add form is visible, when the person enters a name and selects `Regadío` and `Ecológico`, then the saved `Land` has `WaterRegime.IRRIGATED` and `ProductionMethod.ORGANIC`; reopening the app backed by the same storage retains it.

### Do not force a guess

Given a person does not know water regime or production method, when viewing the form, then `No lo sé` is clearly available and selected initially for each attribute; it is not converted to mixed, conventional, or dryland during save.

### Correct a missing name

Given the form has an empty, whitespace-only name, when `Guardar terreno` is selected, then no record is written, the name field shows a plain-Spanish required-field error, and all entered values remain available to correct.

### Recover from a local save failure

Given the repository rejects the draft or its storage write fails, when the person saves, then no success feedback or navigation occurs, a plain Spanish failure message is shown, and the form values remain intact for retry or cancellation.

### Leave without saving

Given the add form is open, when the person selects `Cancelar` or the visible back control, then the app returns to the chat home and creates no record.

## Repository research

Inspected:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` contains the shared chat home and an unwired `Mis terrenos` callback; there is no navigation library or app theme wrapper.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/Land.kt` already supplies `LandDraft`, required `name`, optional `municipality`, and the required enums including `UNKNOWN` and `MIXED`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandRepository.kt` synchronously validates and trims drafts, persists via `LandStorage`, and can throw on invalid input or a storage write.
- `shared/src/androidMain/.../lands/AndroidLandStorage.kt` and `shared/src/jvmMain/.../lands/FileLandStorage.kt` are the accepted platform adapters, but neither is yet constructed by an app entry point.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt` each invoke `App()` with no injected dependencies.
- `shared/src/commonTest/.../lands/LandRepositoryTest.kt` verifies repository persistence and validation. `shared/build.gradle.kts` has Kotlin test but no established Compose UI test setup or navigation/DI dependency.
- `shared/src/commonMain/composeResources/values/strings.xml` is the existing KMP resource location. `DESIGN.md` requires plain Spanish, one obvious primary action, a short form, large controls, text scaling, and shared `commonMain` product UI.

The feature is correctly sized: it consumes one existing domain model/repository through one add flow. The open question about whether area belongs in first setup is intentionally not resolved here.

## Technical approach

1. Keep `Land`, `LandDraft`, `LandRepository`, the versioned format, and both storage adapters unchanged unless an implementation defect blocks the flow. The UI creates `LandDraft(name, municipality, waterRegime, productionMethod)` with `areaHectares` and `notes` omitted.
2. Add pure `AddLandState`/`AddLandAction` reducer logic in `commonMain`. It owns raw field text, selected enums, name-error visibility, and a save-error state. It must trim only for validation/draft construction; repository normalization remains authoritative. A valid save action produces a draft; the screen/root performs repository I/O and dispatches success/failure. Do not add a ViewModel, coroutine, DI, or navigation dependency solely for this synchronous local slice.
3. Add a stateless `AddLandScreen` in `commonMain` with state and named callbacks. `App` owns the small shared destination state (`chat`/`add land`), routes the existing `Mis terrenos` callback to the form, and returns to chat after cancellation or success. Retain a no-argument `App()` overload for the existing iOS scaffold; Android and Desktop use an injected `LandRepository`. If no repository is supplied, the lands action remains unavailable/no-op rather than creating an in-memory or platform-specific store in common code.
4. At Android composition root, create one `LandRepository(SharedPreferencesLandStorage(applicationContext))` and pass it to `App`. At Desktop composition root, create one remembered repository backed by a stable user-home path such as `~/.manijero/lands-v1.txt`, then pass it to `App`. Do not log a land name, municipality, or exception contents. The implementation must document the selected Desktop filename in code only if it is self-evident; no user-facing backup claim.
5. Use KMP Compose string resources for every Spanish label, choice, error, and confirmation. Use Material 3 controls and `MaterialTheme` colors, an accessible `OutlinedTextField` error state, and `RadioButton`/label rows or equivalently accessible single-select controls. Controls need visible labels, readable grouping, keyboard activation, and no icon-only essential action. Add previews for blank/default, validation-error, populated known-values, long-text, compact/wide, and large-font layouts that the screen can render.

### Copy contract

Use these concepts in plain Spanish (final punctuation may follow existing resource style):

- Title: `Añadir terreno`; short explanation that only the name is required.
- Required field: `Nombre del terreno`; optional field: `Municipio (opcional)`.
- Groups: `Riego` and `Producción`; choices map one-to-one to `UNKNOWN`/`DRYLAND`/`IRRIGATED`/`MIXED` and `UNKNOWN`/`CONVENTIONAL`/`ORGANIC`/`MIXED`. `No lo sé` maps to `UNKNOWN`; mixed must be described as a deliberate “una parte de cada uno,” not as unknown.
- Actions: `Guardar terreno` (primary) and `Cancelar`; provide a text back action with an accessible label if it is separate from cancel.
- Errors: explain that a name is needed; generic save failure says the terrain could not be saved and invites retry, without exposing implementation details. Success identifies that the terrain was saved without suggesting cloud backup.

## Visual design impact

This adds the first land-management surface, not a list or dashboard. It follows the existing calm full-page chat layout: warm Material surface/theme colors, a readable heading and short explanation, one vertical form column constrained to the existing readable desktop width, generous spacing, and one prominent save action. The optional municipality and the two clearly labeled choice groups appear after the required name so the next step stays obvious. Do not use a map, table, icon-only control, color-only validation, or an accordion that hides the `No lo sé` choices. Reuse Material 3 touch-target behavior and expose radio selection and text-field error semantics to assistive technology.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: inject/receive the repository, hold the minimal destination state, and wire chat-home lands affordance, cancel, and successful save.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandState.kt`: reducer/state/draft mapping with no Compose or platform imports.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: shared Material 3 form, private form-choice components, callbacks, and required previews.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: add all form copy and accessibility labels.
- **Modify** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandRepositoryTest.kt` only if needed for a missing end-to-end repository assertion; otherwise add **Create** `AddLandStateTest.kt` for pure form behavior. Use the existing in-memory `LandStorage` fake rather than disk/framework I/O.
- **Modify** `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`: construct and pass the Android-backed repository once.
- **Modify** `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`: construct and pass the stable file-backed repository once.
- **Do not modify** persistence serialization/adapters, backend/contracts, or iOS files unless retaining the no-argument `App()` API proves impossible; if it does, update only the iOS call site to compile, without adding an iOS storage implementation.

## Implementation plan and tasks

1. Write reducer tests from the acceptance contract first: default unknown selections, whitespace rejection without draft, preserved text/selections after validation/save failure, enum-to-draft mapping, and cancellation/success state handling. Include a Unicode/emoji land name angle and a non-finite/negative-area guard only if an area field is introduced (it should not be).
2. Implement the pure state/action/draft boundary and verify it does not duplicate repository IDs, timestamps, or persistence rules.
3. Build the screen using resource-backed strings and Material 3 semantics; add the specified previews and inspect at large font/wide width.
4. Wire the shared app destination and repository save callback. Catch expected validation/write failures at the UI boundary, retaining form state and avoiding data logging.
5. Wire Android and Desktop composition roots to the existing adapters; ensure the same repository instance is not recreated on ordinary recomposition.
6. Run focused tests and builds, then perform the Android/Desktop manual scenarios. Only after implementation/independent validation update `feature_list.json` evidence/status and `PROGRESS.md`.

## Verification plan and evidence

Run from the repository root:

```sh
./init.sh
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
# If the Android SDK is available:
./init.sh --verify
```

Manual Android and Desktop smoke checks:

1. From home, open `Mis terrenos`, find the short add form, and save a name-only land with both `No lo sé` choices.
2. Add a second land with `Regadío` and `Ecológico`; close/relaunch each target and confirm repository data remains (temporary debug inspection or a focused test is acceptable until `land_list` exists).
3. Try blank/whitespace-only name, confirm the record is not saved and text/choices remain; correct it and save.
4. At enlarged system text, use keyboard navigation on Desktop and Android accessibility services where available; confirm labels, selection state, focus, and primary action remain understandable.

Capture command output, environment limitations (especially missing Android SDK), screenshots or a short manual record for default/error/known-value form states, and the persistence assertion. No persistent E2E harness exists in this repository; focused pure-state/repository tests plus Android/Desktop manual smoke are sufficient for this local synchronous UI flow.

### Implementation note (2026-10-12, `add_land` implementer)

- Added one focused test beyond this plan: `shared/src/jvmTest/.../AddLandDesktopStoreTest.kt`
  uses the real `FileLandStorage` with a temporary directory to assert that a name-only land and
  a known water/production land both persist after reopening the store. It complements the
  in-memory fake used by `AddLandStateTest` and makes the Desktop acceptance scenario
  reproducible for the validator. It touches no user data and changes no adapter.
- `./init.sh` created this worktree's `local.properties`, so for the first time in this checkout
  `./init.sh --verify` could run the Android host tests and build the debug APK as well as the
  shared JVM tests and Desktop build.

## Durable documentation impact

- `feature_list.json`: **not yet**; retain `not_started` until implementation is independently verified, then record evidence/status.
- `PROGRESS.md`: **not yet**; add only verified implementation evidence and known platform blockers.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, and `docs/risks-and-open-questions.md`: **not needed**; this implements existing decisions without changing them.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: **not needed**; neither exists and this feature introduces no durable architectural decision.

## Validator checklist

- [ ] The only required user input is a nonblank trimmed name; no record is written for blank input.
- [ ] Unknown is visible and preserved independently for water and production; mixed is never used as its substitute.
- [ ] A name-only and known-water/known-production land are correctly saved through `LandRepository` and persist on supported MVP platforms.
- [ ] Municipality is optional; no area, notes, precise identifier, or legal eligibility input is collected.
- [ ] Save failure retains user input, gives plain Spanish recovery guidance, and exposes neither land data nor raw exception text.
- [ ] The full product UI/form behavior is in `commonMain`; only storage construction is platform-specific.
- [ ] UI text and accessibility labels are resource-backed; controls work with large text, keyboard, and visible focus on Desktop.
- [ ] Focused tests and feasible builds pass, with blocked Android checks reported honestly.
- [ ] No unrelated feature, backend, persistence-format, cloud, or iOS-release work is included.

## Follow-up status after `land_form_accessibility`

- **Deferred accessibility checks done** (2026-10-13): the screen-reader and enlarged-text checks this
  spec deferred to `land_form_accessibility` are performed there (spec
  `docs/specs/land_form_accessibility.md`). The form title is now a `heading`, the two `No lo sé`
  options carry group-qualified accessible names (`Riego: No lo sé` / `Producción: No lo sé`) inside a
  `selectableGroup`, and a blank-name save announces the unchanged required-name message and returns
  input focus to the name field. No visible copy, layout, state, persistence, or accepted behavior
  changed.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests AddLandStateTest --tests AddLandDesktopStoreTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/add_land.md. Implemented the shared AddLandState/AddLandAction reducer with draft mapping (shared/src/commonMain/.../lands/AddLandState.kt), the stateless resource-backed AddLandScreen with previews (AddLandScreen.kt), Spanish add-land copy in composeResources/values/strings.xml, and App() destination plus lands wiring that catches save failures without logging land data.
- Composition roots: Android builds one LandRepository(SharedPreferencesLandStorage(applicationContext)); Desktop builds one remembered LandRepository(FileLandStorage(~/.manijero/lands-v1.txt)). The no-argument App() is retained for the iOS scaffold and previews, where the lands action stays unavailable instead of creating a common-code store.
- ./init.sh --verify passes (this worktree has local.properties after init.sh): :shared:jvmTest 21 tests/0 failures, :shared:testAndroidHostTest 20 tests/0 failures, :androidApp:assembleDebug, :desktopApp:build.
- New focused tests: 11 in AddLandStateTest (UNKNOWN defaults, blank/whitespace name rejected with no draft, name-only and IRRIGATED/ORGANIC mapping, deliberate MIXED, Unicode name, save-failure retention and retry, error clearing, two-land persistence after reopening) plus AddLandDesktopStoreTest against the real FileLandStorage.
- Desktop startup smoke: ./gradlew :desktopApp:run launched com.jamarglex.manijero.MainKt with the injected file store and stayed running without startup errors until the session stopped it (SIGTERM exit 143).
- Not verified by automated UI tests: interactive Android/Desktop device clicks and screen-reader/large-text checks; no emulator, device, or Compose UI-test harness exists, and the spec defers this to land_form_accessibility. Reported honestly rather than claimed.
- Independent validator accepted (2026-10-12) after re-running ./init.sh --verify, :shared:jvmTest and :shared:testAndroidHostTest with --rerun-tasks (21 and 20 tests, 0 failures), :androidApp:assembleDebug, :desktopApp:build, and a Desktop startup smoke; confirmed scope discipline, commonMain-only product UI, no land data or raw exception logging, and the copy contract. Record: docs/validations/add_land.md.
