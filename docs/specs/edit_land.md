# Feature Spec: `edit_land`

## Source metadata

- **Feature:** `edit_land` — Edit a land (`lands`)
- **Status at planning:** `not_started`; depends on accepted `land_list`, `local_land_store`,
  `add_land`, and `visual_foundation` (all dependency-ready and accepted).
- **Source behavior:** A person can correct the name or known details of one land without changing
  another land.
- **Feature verification:** Edit one of two saved lands and confirm the other record remains
  unchanged.
- **Note from the feature list:** Unknown values remain valid after editing.

## Goal and boundaries

A person who taps `Editar` on one row of `Mis terrenos` gets a short, prefilled Spanish form, saves
a correction through the accepted `LandRepository.update(id, draft)`, returns to the list, and sees
the correction confirmed. The edit writes **exactly one** record: the targeted id, every attribute
this form does not collect (area, notes), and every other land stay exactly as they were.

**In scope**

- A visible `Editar` control on each saved-land row of the existing `Mis terrenos` list.
- A prefilled edit form for the four fields the MVP actually collects: name (required),
  municipality (optional), water regime, production method.
- Corrections in both directions: setting a detail, **clearing** the optional municipality, and
  deliberately setting a known detail back to `No lo sé` (`UNKNOWN`).
- Required-name validation, an understandable update failure, a distinct “this land is no longer
  saved” outcome, cancel/back, and a plain-Spanish updated confirmation on the list.
- One `LandRepository.update` call at the UI boundary, inside the existing `App()` composition root.

**Non-goals**

- Removal, archiving, undo, or any destructive confirmation (`remove_land` owns them).
- Collecting or displaying `areaHectares` or `notes` (they are preserved untouched, not edited).
- Selecting a land for chat or land-aware context (`minimal_land_context` owns it).
- Duplicate-name detection, rename collisions, merge/split, numbering rows, or exposing land ids.
- Any change to `Land`, `LandDraft`, `LandRepository`, the `land-store-v1` format, the storage
  adapters, the `AddLandState`/`AddLandScreen` behavior, entry points, Gradle, or the theme.
- A navigation library, ViewModel, DI, coroutine, Compose UI-test framework, or any new dependency;
  no network call, no telemetry, no land-data or exception logging.
- iOS release work; product behavior and Compose UI stay in `commonMain`. A full accessibility
  validation (screen reader, enlarged text, low-digital-confidence users) stays with
  `land_form_accessibility`, which depends on this feature.

## Job story

When a detail of one of my olive lands changes — or I got the name wrong the first time — I want to
correct just that land on its own short form, so the assistant keeps working with the right facts
and my other lands are not touched.

## Acceptance scenarios

### Correct one land without touching the other

Given two lands are saved and the second has a municipality and known water/production, when the
person selects `Editar` on the first row, changes only its name, and selects `Guardar cambios`, then
exactly that record changes, the second record keeps every value (name, municipality, water,
production, and any stored area/notes), the list shows the corrected name in the same position, and
the plain-Spanish updated confirmation is visible.

### Keep unknown values unknown

Given a land was saved with only a name, when the person adds a municipality and saves, then its
stored water regime and production method are still `UNKNOWN`, no guessed value replaces them, and
the row still reads `Riego: No lo sé` and `Producción: No lo sé`.

### Deliberately un-know a detail

Given a land has `Regadío` and `Ecológico`, when the person selects `No lo sé` for both and saves,
then the stored values are `WaterRegime.UNKNOWN` and `ProductionMethod.UNKNOWN`, and the list shows
`No lo sé` for both; unknown is written only because the person chose it.

### Clear an optional detail

Given a land shows `Municipio: Martos`, when the person empties the municipality field and saves,
then the stored municipality is absent (not an empty string), the row no longer shows a `Municipio:`
line, and this is treated as a valid correction, not as a missing-name error.

### Correct a missing name

Given the edit form has an empty or whitespace-only name, when the person selects `Guardar cambios`,
then no record is written, the name field shows the plain-Spanish required-field message, all
edited values remain available, and the other land is untouched.

### Never present an unsaved edit as saved

Given the storage write fails, or the targeted id is no longer stored, when the person saves, then no
confirmation and no success navigation occur, a plain-Spanish message explains that nothing was
saved (and, when the land is gone, that it is no longer stored), the edited values remain on screen
for retry or cancel, and no new record is created.

### Leave without saving

Given the edit form is open, when the person selects `Cancelar`, then the app returns to the list,
nothing is written, the unsaved text is discarded, and no confirmation is shown.

## Technical approach

1. **Pure state first** — create `EditLandState.kt` in the `lands` package with no Compose, resource,
   or platform imports:

   ```kotlin
   /** Why the update did not happen, so copy and tests can tell the two cases apart. */
   enum class EditLandFailure { WRITE_FAILED, LAND_MISSING }

   data class EditLandState(
       val landId: String,                        // the only record this state may ever write
       val name: String,
       val municipality: String,
       val waterRegime: WaterRegime,
       val productionMethod: ProductionMethod,
       val preservedAreaHectares: Double?,        // carried through: this form does not collect it
       val preservedNotes: String?,               // carried through: this form does not collect it
       val showNameError: Boolean = false,
       val failure: EditLandFailure? = null,
   ) {
       val hasName: Boolean get() = name.isNotBlank()
   }

   /** The starting form for [this] loaded record; known values are preselected, unknown ones stay. */
   fun Land.toEditLandState(): EditLandState

   sealed interface EditLandAction {
       data class NameChanged(val value: String) : EditLandAction
       data class MunicipalityChanged(val value: String) : EditLandAction
       data class WaterRegimeSelected(val value: WaterRegime) : EditLandAction
       data class ProductionMethodSelected(val value: ProductionMethod) : EditLandAction
       data object SaveClicked : EditLandAction
       data class SaveFailed(val failure: EditLandFailure) : EditLandAction
   }

   fun EditLandState.reduce(action: EditLandAction): EditLandState

   /** The draft to update with, or `null` when the form must not be written yet. */
   fun EditLandState.toDraftOrNull(): LandDraft?
   ```

   Contract:
   - `toEditLandState()` copies the record's **trimmed, stored** name into `name`,
     `municipality.orEmpty()` into `municipality`, the two enums as they are (an `UNKNOWN` value
     preselects `No lo sé`), and keeps `areaHectares`/`notes` in the two preserved fields. It never
     renames, defaults, or guesses a value.
   - Field actions replace raw text / the enum and clear `showNameError` and `failure` (so correcting
     clears a stale notice, exactly like `AddLandState`).
   - `SaveClicked` sets `showNameError = !hasName` and clears `failure`; `SaveFailed(failure)` only
     sets `failure`. Nothing else changes; no ids, timestamps, or persistence rules live here.
   - `toDraftOrNull()` returns `null` for a blank (trimmed) name and otherwise
     `LandDraft(name = name.trim(), municipality = municipality.trim().ifEmpty { null },
     waterRegime, productionMethod, areaHectares = preservedAreaHectares, notes = preservedNotes)`.
     Carrying the preserved fields is what makes a name-only correction incapable of deleting a stored
     area or notes; clearing a *collected* field (municipality, or an enum back to `UNKNOWN`) is a
     deliberate, persisted change.

2. **Stateless screen** — create `EditLandScreen.kt` with
   `EditLandScreen(state, onAction, onCancel, modifier = Modifier)`. It renders a prefilled version of
   the accepted form: the required name field (error state + plain-Spanish message), the optional
   municipality field, the two accessible radio groups, a polite live-region failure message, one
   primary `Guardar cambios` action, and `Cancelar` as the secondary/back control. Keep the
   established `Surface` + `Column(verticalScroll)` + `widthIn(max = 720.dp)` layout, reuse the
   existing `add_land_*` labels and the `add_land_unknown`/`add_land_water_*`/`add_land_production_*`
   choices, and reuse `ChoiceGroup`/`ChoiceItem` by widening their visibility from `private` to
   `internal` in `AddLandScreen.kt` (a visibility-only change; no layout, copy, behavior, or preview
   change there — see the cross-feature section).

3. **Repository semantics (unchanged API)** — use `LandRepository.update(id, draft)` exactly as
   accepted: it replaces only the targeted record, keeps its id/`createdAt` and position, returns
   `null` without writing for an unknown id, and throws if storage fails. Do **not** add a patch
   method, change the format, or call `create` from any edit path (`create` would duplicate a land);
   `edit_land` must never call `delete`.

4. **App wiring** — extend the private destination enum with `EditLand`; own
   `editLandState: EditLandState?` and replace `landSaved: Boolean` with
   `landConfirmation: LandListConfirmation?`. The list row's `Editar` action sets
   `editLandState = land.toEditLandState()`, clears the confirmation, and navigates; the edit
   destination renders from `editLandState?.let { … }` (the only writer always sets it first, so a
   `null` renders nothing rather than crashing or inventing a land). In that branch:

   ```kotlin
   val reduced = state.reduce(action)
   editLandState = reduced
   if (action is EditLandAction.SaveClicked && repository != null) {
       val draft = reduced.toDraftOrNull()
       if (draft != null) {
           val result = runCatching { repository.update(reduced.landId, draft) }
           when {
               result.getOrNull() != null -> {           // updated exactly one record
                   editLandState = null
                   landConfirmation = LandListConfirmation.UPDATED
                   readLands()
                   destination = AppDestination.LandList
               }
               result.isSuccess -> editLandState =        // id no longer stored: nothing written
                   reduced.reduce(EditLandAction.SaveFailed(EditLandFailure.LAND_MISSING))
               else -> editLandState =                    // write threw: nothing confirmed
                   reduced.reduce(EditLandAction.SaveFailed(EditLandFailure.WRITE_FAILED))
           }
       }
   }
   ```

   `Cancelar` clears `editLandState`, returns to the list, and shows no confirmation, writing
   nothing (the same no-write cancel path the accepted `add_land` screen uses). A successful save
   re-reads through the existing `readLands()` and lands on the list, so the corrected row cannot
   linger as a stale value; a failed re-read still lands in the accepted `Reintentar` failure state.
   No `now` argument is passed to `update` (see limitations), no throwable or land value is logged,
   and the write happens only on `SaveClicked`, never while composing.

5. **No new dependencies.** The read/write stay synchronous on the composition frame like the
   accepted add/list paths. A ViewModel, coroutine, navigation library, DI, dialog, or UI-test
   framework is deliberately out of scope for this bounded local slice.

### Copy contract

Plain Spanish in the established tú voice. Reuse existing resources; only these **new** keys need
adding. Ship the values byte-for-byte (mirroring the existing `«No lo sé»` guillemets):

```xml
<string name="land_list_edit">Editar</string>
<string name="land_list_edit_description">Editar el terreno «%1$s»</string>
<string name="edit_land_title">Editar terreno</string>
<string name="edit_land_description">Solo el nombre es obligatorio. Corrige lo que necesites; si ya no sabes un dato, elige «No lo sé».</string>
<string name="edit_land_save">Guardar cambios</string>
<string name="edit_land_saved">Los cambios se han guardado en este dispositivo.</string>
<string name="edit_land_save_failed">No se han podido guardar los cambios. Puedes intentarlo otra vez.</string>
<string name="edit_land_missing">Ese terreno ya no está guardado. No se ha cambiado nada. Vuelve a la lista para ver los terrenos que tienes.</string>
```

- Reuse: `add_land_name_label`, `add_land_name_error`, `add_land_municipality_label`,
  `add_land_water_label`, `add_land_production_label`, `add_land_unknown` (`No lo sé`),
  `add_land_water_*`, `add_land_production_*`, `add_land_cancel` (`Cancelar`), `chat_home_lands`
  (`Mis terrenos` list heading), `land_list_description`, `land_list_municipality`, `land_list_water`,
  `land_list_production`, `add_land_saved` (add confirmation), `land_list_add`, `land_list_back`,
  `land_list_empty`, `land_list_load_failed`, `land_list_retry`.
- The list renders `land_list_edit` as the visible label of each row's secondary control and
  `land_list_edit_description` (with the land's exact saved name) as that control's accessible
  description; `land_list_edit_description` is never shown as body text.
- Never claim a cloud backup, never imply that a corrected land proves eligibility or legal status,
  and never invent a value for `UNKNOWN`.

## Visual design impact

Reuse `ManijeroTheme` roles only: `background` page, `surface` row cards with an `outlineVariant`
border, `onBackground` headings, `onSurface` names, `onSurfaceVariant` details, `primary` for the
primary action, `error` for failures. No raw colors, gradients, icons, or new tokens.

```
Mis terrenos                                  (headlineMedium)
Estos son los terrenos guardados…             (bodyLarge, onSurfaceVariant)
[ "Los cambios se han guardado…", when just updated ]   (polite live region)
   ┌ Los Olivos                (merged text node: name + Municipio/Riego/Producción)
   │ [ Editar ]                (secondary TextButton, full width)
   └ …
[ Añadir terreno ]  (primary, full width)
[ Volver ]          (secondary TextButton, full width)

Editar terreno                                (headlineMedium)
Solo el nombre es obligatorio. Corrige…        (bodyLarge, onSurfaceVariant)
[ Nombre del terreno ]  [ Municipio (opcional) ]
Riego: (No lo sé) (Secano) (Regadío) (Una parte de regadío y otra de secano)
Producción: (No lo sé) (Convencional) (Ecológico) (Una parte de cada uno)
[ Guardar cambios ]  (primary, full width)
[ Cancelar ]         (secondary TextButton, full width)
```

- **Edit affordance decision:** each row gets its own visible, labeled `Editar` `TextButton`; the row
  card itself stays **non-clickable**, so tapping a row to read it never navigates. This follows
  `DESIGN.md` (“visible action”, “pair icons with text”, “do not rely on hover”) and is safer for
  people with low digital confidence than a hidden whole-row tap target. The rejected alternative
  (making the card clickable) is recorded here so the validator does not ask for it.
- The `Editar` buttons are secondary controls repeated per row; the screen keeps exactly one primary
  action (`Añadir terreno`), so “one primary action per screen” still holds.
- Accessibility: keep the row's details in a `mergeDescendants` text node and keep the `Editar`
  button as its own labeled control (details read as one item, the button announced with the land's
  name), confirmations and failure messages as `LiveRegionMode.Polite`, normal Material minimum touch
  targets, visible focus and keyboard activation on Desktop, and no color-only status cue. The form
  is prefilled so the name identifies which land is being edited; no id, area, or notes are shown.
- Long names/values and 2x text wrap in full with no ellipsis or horizontal scrolling; the screen
  scrolls vertically. Full accessibility validation of both land forms stays with
  `land_form_accessibility`.

## Cross-feature interaction (declared changes to accepted files)

`edit_land` needs an entry point and an updated confirmation, so it declares these intended changes;
validators should treat them as scope, not regression:

1. `LandListScreen` rows gain the visible `Editar` control described above (land_list deliberately
   shipped rows without an edit affordance; rows stay non-clickable).
2. `LandListScreen(..., savedConfirmation: Boolean)` becomes
   `LandListScreen(..., confirmation: LandListConfirmation? = null)` with
   `enum class LandListConfirmation { ADDED, UPDATED }` declared in `LandListScreen.kt`; `ADDED`
   renders the existing `add_land_saved`, `UPDATED` renders the new `edit_land_saved`. The add path's
   text and behavior are unchanged, and the “just saved” preview is updated to the new parameter.
3. `ChoiceGroup`/`ChoiceItem` in `AddLandScreen.kt` change from `private` to `internal` so the edit
   screen reuses them. No other line of `AddLandScreen.kt` changes; `AddLandState` is untouched.
4. Everything else accepted stays intact: `AddLandScreen` behavior/copy, `LandListState`, both
   storage adapters, `land-store-v1`, entry points, `App()` (no argument), the theme, and the
   `add_land`/`land_list` specs. Re-run the `add_land`/`land_list` tests and confirm the add
   confirmation still reads `add_land_saved`.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandState.kt`: pure
  `EditLandState`, `EditLandFailure`, `EditLandAction`, `reduce`, `Land.toEditLandState()`,
  `toDraftOrNull()`; no imports beyond the `lands` model.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`: stateless
  prefilled form, resource-backed copy, reuse of the shared choice group, previews for prefilled,
  name error, write failure, missing land, long text, compact (`widthDp = 320`), wide
  (`widthDp = 900`), and `fontScale = 2f`.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: required
  `onEditLand: (Land) -> Unit`, the per-row `Editar` control, `LandListConfirmation`, and the
  confirmation parameter; update the “just saved” preview and add a “just updated” preview.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`:
  `private` → `internal` on `ChoiceGroup`/`ChoiceItem` only.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `EditLand` destination,
  `editLandState`/`landConfirmation` state, row edit action, the single `update` call site, the
  re-read on a successful save, and the no-write cancel that returns to the list (the accepted
  `add_land` cancel path); unchanged `App()` behavior.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the eight new keys above.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/EditLandStateTest.kt`: pure
  reducer/mapping tests from directly constructed `Land` values.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/EditLandRepositoryTest.kt`:
  in-memory fake `LandStorage`; one-land isolation, preserved area/notes, unknown preservation,
  unknown-id no-write.
- **Create** `shared/src/jvmTest/kotlin/com/jamarglex/manijero/lands/EditLandDesktopStoreTest.kt`:
  real `FileLandStorage` in a temp dir; edit one of two lands and confirm the other record survives
  reopening unchanged.
- **Update** `CONSTRAINTS.md`: one new MUST rule under a “Land editing” heading (below).
- **Do not modify** `Land.kt`, `LandRepository.kt`, the storage adapters, `AddLandState.kt`,
  `MainActivity.kt`, `desktopApp/main.kt`, `MainViewController.kt`, Gradle files, `scripts/init.sh`, `theme/`,
  backend/contracts/knowledge, or `feature_list.json`/`PROGRESS.md` while implementing.

## Honest limitations to record

- `LandRepository.update` receives no timestamp from the app (`now` keeps its default `0L`, matching
  the accepted `create` path), because the project has no clock/date dependency. `updatedAtEpochMillis`
  is therefore still not meaningful; adding a real clock belongs to `local_land_store` hardening
  (carried finding F6 from `land_list`) and must not be smuggled in here.
- `EditLandFailure.LAND_MISSING` is a defensive branch: it is reachable only if a stored record
  disappears between the list read and the save (an external edit of the Desktop file, or a malformed
  line dropped by `LandStoreFormat.decode`). It is covered by unit tests rather than normal use; the
  alternative (treating `null` as success) would lie to the person.
- Two lands that share a name, have no municipality, and are unknown render as identical rows with
  their own `Editar` controls, separated only by order (the accepted `land_list` limitation). The app
  still does not invent labels or expose ids, so the person must rely on the prefilled name to check
  they opened the right row.
- `areaHectares` and `notes` are preserved but neither shown nor editable here, so a person cannot
  see or correct them from this form.
- The list read and the update are synchronous on the composition frame, acceptable for a bounded
  local land count; lazy loading, background I/O, and large-store behavior remain out of scope.
- Screen-reader, large-text, low-digital-confidence, and persistent-E2E verification are not claimed
  here; they belong to `land_form_accessibility` and the MVP build features.

## Durable documentation impact

- `feature_list.json`: **not yet**; keep `not_started`/self-verified `passing` until independent
  validation, then record evidence and status.
- `PROGRESS.md`: **not yet**; add only verified evidence and known gaps.
- `CONSTRAINTS.md`: **update**; add the “Land editing” MUST rule above (it is exactly the durable
  guarantee this feature introduces: one targeted record, preserved untouched attributes, no false
  confirmation).
- `DESIGN.md`, `docs/domain-model.md`, `CONTEXT.md`, `docs/build-brief.md`, `AGENTS.md`: **not
  needed**; this implements the existing surface-5 (add/edit form) and land-lifecycle decisions.
- `docs/specs/land_list.md` and `docs/specs/add_land.md`: **do not modify**; the intended routing and
  affordance changes are recorded in this spec's cross-feature section.
- `docs/risks-and-open-questions.md`: **not needed**; the recorded limits above are known product
  limits, not new unresolved questions.
- `ARCHITECTURE.md`: **not needed**; the file does not exist and this reuses the accepted
  reducer/screen/injected-repository pattern.

## Follow-up status after `land_form_accessibility`

- **Deferred accessibility validation done** (2026-10-13): the full accessibility validation this spec
  left to `land_form_accessibility` (spec `docs/specs/land_form_accessibility.md`) is performed there
  for both land forms — enlarged Android text (`font_scale` 1.0/2.0), the narrow/large-font previews, a
  real Android accessibility dump, and a Desktop keyboard/AX pass. The edit form's title is a
  `heading`, its two `No lo sé` options carry group-qualified accessible names inside a
  `selectableGroup`, and a blank-name save announces the unchanged message and re-focuses the name
  field. The carried no-Compose-UI-test-harness limit (F3) and the implementer-only smoke (F6) stand
  unchanged: the new semantics/focus are verified by the dumps, the AX tree, and code inspection, not
  an automated UI test. No visible copy, layout, state, persistence, or accepted edit behavior changed.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests EditLandStateTest --tests EditLandRepositoryTest --tests EditLandDesktopStoreTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/edit_land.appendix.md`](edit_land.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/edit_land.md` remains the authoritative acceptance record.
