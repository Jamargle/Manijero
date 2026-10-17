# Feature Spec: `add_land`

## Source metadata

- **Feature:** `add_land` — Add a land (`lands`)
- **Status at planning:** `not_started`; depends on accepted `local_land_store`.
- **Source behavior:** A person can add a named land and can leave attributes unknown rather than guessing.
- **Feature verification:** Save one land with only a name and another with known water and production details.
- **Note from the feature list:** Keep setup short; area and notes remain optional pending validation.

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

## Durable documentation impact

- `feature_list.json`: **not yet**; retain `not_started` until implementation is independently verified, then record evidence/status.
- `PROGRESS.md`: **not yet**; add only verified implementation evidence and known platform blockers.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, and `docs/risks-and-open-questions.md`: **not needed**; this implements existing decisions without changing them.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: **not needed**; neither exists and this feature introduces no durable architectural decision.

## Follow-up status after `land_form_accessibility`

- **Deferred accessibility checks done** (2026-10-13): the screen-reader and enlarged-text checks this
  spec deferred to `land_form_accessibility` are performed there (spec
  `docs/specs/land_form_accessibility.md`). The form title is now a `heading`, the two `No lo sé`
  options carry group-qualified accessible names (`Riego: No lo sé` / `Producción: No lo sé`) inside a
  `selectableGroup`, and a blank-name save announces the unchanged required-name message and returns
  input focus to the name field. No visible copy, layout, state, persistence, or accepted behavior
  changed.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests AddLandStateTest --tests AddLandDesktopStoreTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/add_land.appendix.md`](add_land.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/add_land.md` remains the authoritative acceptance record.
