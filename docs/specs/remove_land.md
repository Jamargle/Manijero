# Feature Spec: `remove_land`

## Source metadata

- **Feature:** `remove_land` — Remove a land (`lands`)
- **Status at planning:** `not_started`; depends on accepted `land_list` and `visual_foundation`.
  The accepted `local_land_store` already exposes the `LandRepository.delete(id)` this feature needs.
- **Source behavior:** A person can remove a land they no longer manage after seeing which record will
  be removed.
- **Feature verification:** Remove one of two lands and confirm only that land is absent from future
  lists and requests.
- **Note from the feature list:** Use one simple removal path; decide whether undo is needed during
  implementation (decided below: confirmation first, no undo).

## Goal and boundaries

A person who selects `Eliminar` on one row of `Mis terrenos` sees a short Spanish confirmation that
names the exact land that will disappear, and only after an explicit `Eliminar el terreno` is that one
record deleted through the accepted `LandRepository.delete(id)`. Every other land, and the local
`land-store-v1` snapshot's order, stays untouched.

**In scope**

- A visible `Eliminar` control on each saved-land row of the existing `Mis terrenos` list.
- One confirmation step that identifies the land (exact saved name plus the same known details the row
  shows) before anything is written.
- One `LandRepository.delete(id)` call at the UI boundary, inside the existing `App()` composition
  root, only after that confirmation.
- A plain-Spanish removed confirmation on the list, and plain-Spanish recovery when deletion fails or
  the record is already gone.
- Removing the last land leaving a valid empty store and the accepted empty list state.

**Non-goals**

- Undo, redo, archive/restore, trash, bulk removal, "remove all", or any recovery of a removed record
  (decision and rationale below).
- Editing, selecting a land for chat, or land-aware context (`edit_land`, `minimal_land_context`).
- Any change to `Land`, `LandDraft`, `LandRepository`, the `land-store-v1` format, the storage
  adapters, the add/edit states and screens, `LandListState`, entry points, Gradle, or the theme.
- Showing, logging, or exporting land ids, `areaHectares`, or `notes`; telemetry, cloud, accounts,
  backup, or any network call.
- A navigation library, ViewModel, DI, coroutine, dialog/snackbar framework, or any new dependency;
  iOS release work; product behavior stays in `commonMain`. A full accessibility audit of the land
  flows is not part of this feature (see limitations).

## Job story

When I stop managing one of my olive lands, I want to take it out of my list without touching the
others and without deleting the wrong one by accident, so the assistant keeps using only the lands I
really have.

## Acceptance scenarios

### See which record will be removed

Given two lands are saved, when the person selects `Eliminar` on one row, then a confirmation appears
that names that land's exact saved name (with the same known details the row shows) and offers
`Eliminar el terreno` and `Cancelar`, while the local store is still unchanged: no record has been
removed merely by opening the confirmation.

### Remove exactly that land

Given the confirmation for one land is open, when the person selects `Eliminar el terreno`, then
exactly that record leaves the local store, the other land keeps every value (name, municipality,
water, production, area, notes, id, and `createdAt`) and its serialized line stays byte-identical, the
remaining record keeps its position in the snapshot, and the app returns to `Mis terrenos` showing only
the remaining land with the plain-Spanish removed confirmation.

### Cancel removes nothing

Given the confirmation is open, when the person selects `Cancelar`, then nothing is written, the app
returns to the list with both lands unchanged, and no confirmation is shown.

### Removing the last land leaves a valid empty state

Given one land is saved, when the person removes it, then the store holds zero lands (a valid
header-only `land-store-v1` snapshot, not a broken one), the list shows the accepted empty state that
names `Añadir terreno`, and a new land can still be added afterwards.

### Only that land is absent from future lists and requests

Given one of two lands was removed, when the app reads the lands again (re-entering `Mis terrenos`, on
`Reintentar`, after a relaunch, or from a future land-context builder), then the removed record's id,
name, and attributes are absent and the remaining land is returned unchanged; the removal path keeps
no in-memory copy of the removed land, and the app sends nothing over the network and logs no land
value.

### Never present a failed removal as done

Given the storage write fails, when the person confirms removal, then no confirmation and no
navigation to the list occur, a plain-Spanish message says the land could not be removed, the
confirmation stays on screen so the person can try again or cancel, the record is still present, and
the copy exposes no land data or raw exception text.

### Handle a land that is already gone

Given the targeted land is no longer in the store (removed elsewhere), when the person confirms
removal, then nothing is written, a distinct plain-Spanish message says it was no longer saved, and
the app never claims a removal it did not perform.

## Technical approach

1. **Pure state first** — create `RemoveLandState.kt` in the `lands` package with no Compose, resource,
   or platform imports:

   ```kotlin
   /** Why the deletion did not happen, so copy and tests can tell the two cases apart. */
   enum class RemoveLandFailure { WRITE_FAILED, LAND_MISSING }

   data class RemoveLandState(
       val landId: String,                       // the only record this state may ever delete
       val name: String,                         // exact saved name, shown in the confirmation
       val municipality: String?,
       val waterRegime: WaterRegime,
       val productionMethod: ProductionMethod,
       val failure: RemoveLandFailure? = null,
   )

   /** The confirmation target for [this] loaded record; nothing is renamed, defaulted, or guessed. */
   fun Land.toRemoveLandState(): RemoveLandState

   sealed interface RemoveLandAction {
       data object RemoveClicked : RemoveLandAction
       data class RemoveFailed(val failure: RemoveLandFailure) : RemoveLandAction
   }

   fun RemoveLandState.reduce(action: RemoveLandAction): RemoveLandState
   ```

   Contract: `toRemoveLandState()` copies the record's **trimmed, stored** name and its identity
   fields verbatim (an `UNKNOWN` value stays `UNKNOWN`); `RemoveClicked` clears a previous `failure`
   so a retry starts clean and does **not** delete anything by itself (the caller performs the delete
   only for this action); `RemoveFailed(failure)` sets the failure and keeps every field, so the land
   still identifies itself for a retry. No ids, timestamps, persistence rules, or resource lookups
   beyond the copied fields.

2. **Stateless confirmation screen** — create `RemoveLandScreen.kt` with
   `RemoveLandScreen(state, onRemove, onCancel, modifier = Modifier)`. It renders the heading, one
   confirmation sentence naming the exact land, that land's known details through the same shared
   `LandDetails` block the list row uses (so two same-named lands stay distinguishable), the polite
   live-region failure line, one danger-styled `Eliminar el terreno` primary action, and `Cancelar` as
   the secondary/back control. Keep the established `Surface` + `Column(verticalScroll)` +
   `widthIn(max = 720.dp)` layout.

3. **Repository semantics (unchanged API)** — use `LandRepository.delete(id)` exactly as accepted: it
   removes only the targeted record, preserves the order and every other encoded line, returns `false`
   **without writing** for an unknown id, and throws if storage fails. Do **not** add a bulk/restore/undo
   method, change the format, or call `create`/`update` from a removal path.

4. **App wiring** — extend the private destination enum with `RemoveLand`; own
   `removeLandState: RemoveLandState?`; the list row's `Eliminar` action sets
   `removeLandState = land.toRemoveLandState()`, clears the confirmation, and navigates (this
   navigation writes nothing). The destination renders from `removeLandState?.let { … }`:

   ```kotlin
   AppDestination.RemoveLand -> removeLandState?.let { renderedState ->
       val repository = landRepository
       RemoveLandScreen(
           state = renderedState,
           onRemove = {
               val cleared = (removeLandState ?: renderedState)
                   .reduce(RemoveLandAction.RemoveClicked)
               removeLandState = cleared                       // clears a stale failure first
               if (repository != null) {
                   val result = runCatching { repository.delete(cleared.landId) }
                   when {
                       result.getOrNull() == true -> {         // exactly one record removed
                           removeLandState = null
                           landConfirmation = LandListConfirmation.REMOVED
                           readLands()
                           destination = AppDestination.LandList
                       }
                       result.getOrNull() == false ->          // already gone: nothing written
                           removeLandState = cleared.reduce(
                               RemoveLandAction.RemoveFailed(RemoveLandFailure.LAND_MISSING),
                           )
                       else ->                                 // write threw: nothing removed
                           removeLandState = cleared.reduce(
                               RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED),
                           )
                   }
               }
           },
           onCancel = {
               removeLandState = null
               destination = AppDestination.LandList
           },
       )
   }
   ```

   `Cancelar` clears the state, returns to the list, and shows no confirmation, writing nothing.
   Setting `removeLandState = null` on success drops the last in-memory reference to the removed land,
   and the existing `readLands()` re-read means no stale row or stale copy can survive; a failed
   re-read still lands in the accepted `Reintentar` failure state. The delete happens only on the
   person's explicit confirmation click, never while composing, on entry, or at startup. When
   `landRepository == null` (the iOS scaffold and previews) the `Mis terrenos` affordance stays
   disabled, so the `RemoveLand` destination is unreachable there, exactly like the accepted add/edit
   destinations. No throwable and no land value is logged.

5. **No new dependencies.** The read/write stay synchronous on the composition frame like the accepted
   add/edit/delete paths. A ViewModel, coroutine, navigation library, DI, dialog/snackbar, or UI-test
   framework is deliberately out of scope for this bounded local slice.

### Removal path decision (one path, no undo)

- **Decision:** one path — confirm first, then a single permanent `delete(id)`. No undo, no archive,
  no trash.
- **Why:** the domain model asks for “a single simple removal path with a clear confirmation” and only
  “recovery/undo **where practical**”. Nothing is lost by accident because the row control opens a
  confirmation that names the land and the destructive action is a second, deliberate choice; there is
  no snackbar/undo infrastructure in the repository, and re-inserting a removed record would need a
  new persistence capability (the accepted `create` generates a new id and the add/edit forms do not
  collect `areaHectares`/`notes`, so a re-add could not restore them). `docs/risks-and-open-questions.md`
  already records that local-only data has no automatic recovery and that the app must not imply cloud
  backup; the copy therefore states plainly that removal cannot be undone instead of promising a
  recovery that does not exist.
- **Rejected alternatives, recorded so the validator does not ask for them:** an inline row
  confirmation (keeps `LandListState` and per-row failure handling entangled and gives the failure
  case no natural home); a Material 3 `AlertDialog` (the repository has no dialog pattern, and a
  full screen with a heading is clearer for a person with low digital confidence and behaves like
  every other land screen at 2x text and on Desktop); an undo snackbar (needs new infrastructure and a
  re-insert capability). Full accessibility auditing of the removal screen is not delegated to a
  feature that does not depend on `remove_land`; this spec verifies its own large-text/keyboard smoke.

### Copy contract

Plain Spanish in the established tú voice. Reuse existing resources; only these **new** keys need
adding. Ship the values byte-for-byte (mirroring the existing `«…»` guillemets):

```xml
<string name="land_list_remove">Eliminar</string>
<string name="land_list_remove_description">Eliminar el terreno «%1$s»</string>
<string name="remove_land_title">Eliminar terreno</string>
<string name="remove_land_confirm">¿Seguro que quieres eliminar el terreno «%1$s»? No se puede deshacer.</string>
<string name="remove_land_remove">Eliminar el terreno</string>
<string name="remove_land_removed">El terreno se ha eliminado de este dispositivo.</string>
<string name="remove_land_failed">No se ha podido eliminar el terreno. Puedes intentarlo otra vez.</string>
<string name="remove_land_missing">Ese terreno ya no estaba guardado. No se ha eliminado nada.</string>
```

- Reuse: `chat_home_lands` (`Mis terrenos` heading), `land_list_description`, `land_list_municipality`,
  `land_list_water`, `land_list_production`, `add_land_unknown`, `add_land_water_*`,
  `add_land_production_*`, `add_land_cancel` (`Cancelar`), `add_land_saved`, `edit_land_saved`,
  `land_list_edit`, `land_list_edit_description`, `land_list_add`, `land_list_back`,
  `land_list_empty`, `land_list_load_failed`, `land_list_retry`.
- The list renders `land_list_remove` as the visible label of each row's destructive control and
  `land_list_remove_description` (with the land's exact saved name) as that control's accessible
  description; `land_list_remove_description` is never shown as body text, and the confirmation shows
  the land name only through `remove_land_confirm`.
- Never claim a cloud backup or any recovery, never imply that removing a land changes past answers
  (`docs/domain-model.md` line 85: future questions use the updated list; do not imply prior answers
  were recalculated), and never invent a value for `UNKNOWN`.

## Visual design impact

Reuse `ManijeroTheme` roles only: `background` page, `surface` cards with an `outlineVariant` border,
`onBackground` headings, `onSurface` names, `onSurfaceVariant` details, `primary` for the list's
`Añadir terreno`, the `error`/`onError` pair (= `danger`) for the destructive action and the error
text. No raw colors, gradients, icons, or new tokens.

```
Mis terrenos                                    (headlineMedium)
[ removed confirmation, when just removed ]      (polite live region)
   ┌ Los Olivos                (merged text node: name + Municipio/Riego/Producción)
   │ [ Editar ]  [ Eliminar ]  (secondary TextButtons, full width)
   └ …
[ Añadir terreno ]  (primary, full width)
[ Volver ]          (secondary TextButton, full width)

Eliminar terreno                                (headlineMedium)
¿Seguro que quieres eliminar el terreno «Los Olivos»? No se puede deshacer.  (bodyLarge, onSurfaceVariant)
   Municipio: Martos         (only when known)
   Riego: Regadío            (the same three labelled lines the row shows, merged into one node;
   Producción: Ecológico      the name appears once, in the sentence above)
[ Eliminar el terreno ]  (danger: error/onError, full width, labelled text)
[ Cancelar ]             (secondary TextButton, full width)
```

- **Destructive-affordance decision:** each row gets its own visible, labeled `Eliminar` `TextButton`
  (the row card stays **non-clickable**, matching the accepted `Editar` decision); opening it destroys
  nothing, so that trigger keeps the normal secondary styling. Only the confirming
  `Eliminar el terreno` button carries the `danger` pair, together with its text label, so the
  destructive choice is unmistakable and never color-only. The list keeps exactly one primary action
  (`Añadir terreno`), so “one primary action per screen” still holds; on the confirmation screen the
  confirm action is the single primary action and `Cancelar` is the secondary/back control.
- Both same-named lands stay distinguishable because the confirmation repeats the land's known
  details; no id, area, or notes are shown.
- Accessibility: the row's details stay in a `mergeDescendants` text node and the `Eliminar` control is
  its own labeled button announced with the land's exact name; the confirmation is a heading-led screen
  read in order; the failure message is `LiveRegionMode.Polite`; normal Material minimum touch targets,
  visible focus and keyboard activation on Desktop; long names and 2x text wrap in full with no
  ellipsis or horizontal scrolling, and the screen scrolls vertically.

## Cross-feature interaction (declared changes to accepted files)

`remove_land` needs an entry point and a new confirmation, so it declares these intended changes;
validators should treat them as scope, not regression:

1. `LandListScreen` rows gain the visible `Eliminar` control described above (the `land_list` spec
   deliberately shipped rows with no removal affordance; rows stay non-clickable).
2. `LandListConfirmation` gains `REMOVED`, rendered with `remove_land_removed`; `ADDED` still renders
   `add_land_saved` and `UPDATED` still renders `edit_land_saved` byte-for-byte, and a “just removed”
   preview is added next to the existing “just saved”/“just updated” ones.
3. `LandListScreen.kt`'s detail lines and their label mapping (`LandRowDetail`,
   `waterRegimeLabel`, `productionMethodLabel`) are factored into one `internal @Composable`
   `LandDetails(land)` that both the list row and the confirmation screen call. This is a
   visibility/extraction-only change: no layout, copy, behavior, or preview change in the list.
4. Everything else accepted stays intact: `LandListState`, `AddLandState`/`AddLandScreen`,
   `EditLandState`/`EditLandScreen`, both storage adapters, `land-store-v1`, entry points, `App()` (no
   argument), the theme, and the `add_land`/`land_list`/`edit_land` specs. Re-run the accepted land
   tests and confirm both earlier confirmations still read their own strings.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandState.kt`: pure
  `RemoveLandState`, `RemoveLandFailure`, `RemoveLandAction`, `reduce`, `Land.toRemoveLandState()`;
  no imports beyond the `lands` model.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandScreen.kt`:
  stateless confirmation, resource-backed copy, the shared identity block, the danger-styled confirm
  action, `Cancelar`, and previews for name-only, known-details, long-text, write failure, missing
  land, compact (`widthDp = 320`), wide (`widthDp = 900`), and `fontScale = 2f`.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: required
  `onRemoveLand: (Land) -> Unit`, the per-row `Eliminar` control with its accessible description,
  `LandListConfirmation.REMOVED`, the `internal LandDetails` helper, and the “just removed” preview.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `RemoveLand` destination
  (updating the destination enum's KDoc, which currently names only the add and edit forms),
  `removeLandState`, the row removal action, the single `delete` call site, the
  `LAND_MISSING`/`WRITE_FAILED` branches, the re-read on success, and the no-write cancel; unchanged
  `App()` behavior.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the eight new keys above.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/RemoveLandStateTest.kt`: pure
  mapping/reducer tests from directly constructed `Land` values.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/RemoveLandRepositoryTest.kt`:
  in-memory fake `LandStorage`; exactly-one removal, untouched-and-byte-identical other line, order
  preserved, unknown id no-write `false`, last-land valid empty store, removed land absent from a
  reopened repository.
- **Create** `shared/src/jvmTest/kotlin/com/jamarglex/manijero/lands/RemoveLandDesktopStoreTest.kt`:
  real `FileLandStorage` in a temp dir; remove one of two lands and confirm the file no longer
  contains that record and the other survives reopening unchanged.
- **Update** `CONSTRAINTS.md`: one new MUST rule under a “Land removal” heading (below).
- **Do not modify** `Land.kt`, `LandRepository.kt`, the storage adapters/`land-store-v1`,
  `LandListState.kt`, `AddLandState.kt`, `AddLandScreen.kt`, `EditLandState.kt`, `EditLandScreen.kt`,
  `MainActivity.kt`, `desktopApp/main.kt`, `MainViewController.kt`, Gradle files, `scripts/init.sh`, `theme/`,
  backend/contracts/knowledge, or `feature_list.json`/`PROGRESS.md` while implementing.

## Honest limitations to record

- **No undo and no backup:** a confirmed removal is permanent and local-only, and the app offers no
  recovery; if `areaHectares`/`notes` were stored, they are lost with the record (neither the add nor
  the edit form collects them). The copy says removal cannot be undone instead of promising a recovery
  that does not exist. A reversible archive/undo path is a follow-up, not part of this feature.
- `RemoveLandFailure.LAND_MISSING` is a defensive branch: it is reachable only if a stored record
  disappears between the list read and the confirmation (an external edit of the Desktop file, or a
  malformed line dropped by `LandStoreFormat.decode`). It is covered by unit tests rather than normal
  use; the alternative (treating `false` as a successful removal) would claim an action that did not
  happen.
- Two lands that share a name, have no municipality, and are unknown still render as near-identical
  rows (the accepted `land_list` limitation). The confirmation repeats the same known details, so for
  such a pair the person must rely on their own name choice and on the row they opened.
- The list read and the delete are synchronous on the composition frame, acceptable for a bounded local
  land count; lazy loading, background I/O, large-store behavior, and bulk removal are out of scope.
- Screen-reader, enlarged-text, low-digital-confidence, and persistent-E2E verification are not claimed
  here beyond the manual smoke above. Neither `land_form_accessibility` (depends on `add_land` +
  `edit_land`) nor `chat_accessibility` depends on `remove_land`, so if a full accessibility audit of
  removal is required it needs its own follow-up.

## Durable documentation impact

- `feature_list.json`: **not yet**; keep `not_started` until independent verification, then record
  evidence and status.
- `PROGRESS.md`: **not yet**; add only verified evidence and known gaps.
- `CONSTRAINTS.md`: **update**; add the “Land removal” MUST rule above (it is exactly the durable
  guarantee this feature introduces: one targeted record, everything else untouched, no false
  confirmation).
- `DESIGN.md`: **not needed**; this implements the existing line 75 destructive-confirmation rule and
  uses the already-shipped `danger` token. No new surface, token, or layout principle is introduced.
- `docs/domain-model.md`: **not needed**; this implements the existing land-lifecycle decision
  (single simple removal path with a clear confirmation), and the no-undo choice is recorded here.
- `docs/specs/land_list.md`, `docs/specs/add_land.md`, `docs/specs/edit_land.md`: **do not modify**;
  the intended affordance and confirmation changes are recorded in this spec's cross-feature section.
- `docs/risks-and-open-questions.md`: **not needed**; the existing “local device loss removes land
  records” row already covers the no-recovery stance, and user-initiated permanent removal is recorded
  as a known limitation above rather than as a new unresolved product question.
- `ARCHITECTURE.md`, `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`: **not needed**; `ARCHITECTURE.md`
  does not exist and this reuses the accepted reducer/screen/injected-repository pattern.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests RemoveLandStateTest --tests RemoveLandRepositoryTest --tests RemoveLandDesktopStoreTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/remove_land.appendix.md`](../archive/specs/remove_land.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/remove_land.md` remains the authoritative acceptance record.
