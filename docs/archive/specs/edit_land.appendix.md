# Appendix — `edit_land`

Planning and verification record for [`docs/specs/edit_land.md`](../../specs/edit_land.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/edit_land.md` remains the authoritative
acceptance record.

## Repository research

Inspected in this planning session:

- `feature_list.json`: `edit_land` depends on accepted `land_list` and `visual_foundation`;
  `remove_land`, `minimal_land_context`, and `land_form_accessibility` depend on `edit_land` and must
  stay untouched (the accessibility validation of this form belongs to `land_form_accessibility`).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandRepository.kt`: `update(id, draft)`
  normalizes the draft (drops blank name by `require`, trims name, nulls an empty municipality/notes),
  finds the record by id, returns `null` **without writing** when the id is unknown, and otherwise
  does `old.copy(name/municipality/waterRegime/productionMethod/areaHectares/notes, updatedAt = now)`.
  Two consequences drive this spec: (a) `update` takes a **full** `LandDraft`, so an edit draft must
  carry the untouched area/notes forward or it would silently erase them; (b) `id` and
  `createdAtEpochMillis` are preserved and only the targeted index is replaced, so creation order and
  the other records are untouched. `LandStoreFormat` encodes the whole snapshot as `land-store-v1`, so
  “the other record is unchanged” is directly observable at line level.
- `shared/.../lands/Land.kt`: `Land` already carries id, trimmed name, optional municipality,
  explicit `UNKNOWN` water/production, optional area/notes, and timestamps. No model change is needed.
- `shared/.../lands/AddLandState.kt` and `AddLandScreen.kt`: the accepted house pattern — a pure
  state/reducer file with no Compose or platform imports, a stateless `@Composable` screen with named
  callbacks, raw text kept for correction, trimming only when validating/building a `LandDraft`,
  `showNameError`/`showSaveError` flags, resource-backed copy, and previews. `ChoiceGroup`/`ChoiceItem`
  in `AddLandScreen.kt` are `private` and reusable as-is (`label: StringResource`, `selected`,
  `onSelect`).
- `shared/.../lands/LandListState.kt` / `LandListScreen.kt`: pure `LandListState` + `reduce`, read-only
  rows with `mergeDescendants`, a single primary action, `Volver`, `AddLandScreen` unchanged, and a
  `savedConfirmation: Boolean` flag rendering `add_land_saved`. Rows are deliberately not clickable.
- `shared/.../App.kt`: private `AppDestination { Chat, LandList, AddLand }`, nullable injected
  `LandRepository`, one `readLands()` site (`runCatching { repository.list() }` folded into
  `LandListAction`), add-form wiring that catches failures without logging, and `App()` (no argument)
  retained for the iOS scaffold/previews. There is no edit destination yet.
- `shared/src/commonMain/composeResources/values/strings.xml`: one shared resource file holding the
  reusable vocabulary (`add_land_name_label`, `add_land_municipality_label`, `add_land_water_*`,
  `add_land_production_*`, `add_land_unknown` = `No lo sé`, `add_land_cancel`, `add_land_saved`,
  `land_list_*`); `ManijeroTheme` is already applied once in `App()`.
- `shared/build.gradle.kts`: Compose/Ktor/kotlinx only — **no clock/date dependency**, and no Compose
  UI-test dependency. `repository.update`'s `now` therefore keeps its existing default (see
  limitations).
- Tests available today: `commonTest/.../lands/LandListStateTest.kt` (pure state, direct `Land`
  values), `commonTest/.../lands/AddLandStateTest.kt`, `commonTest/.../lands/LandRepositoryTest.kt`
  (in-memory `LandStorage` fake, `idGenerator` injection; already asserts
  `update_and_delete_do_not_change_other_land`), and `jvmTest/.../lands/AddLandDesktopStoreTest.kt`
  (real `FileLandStorage` in a temp dir). `scripts/init.sh --verify` runs
  `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt`: each already constructs exactly one
  repository and passes it to `App(...)`, so **no entry-point change is required**.
- `DESIGN.md`: surface 5 is explicitly “Add/edit land: short, plain-language form … allow unknown
  values without forcing a guess”; one primary action per screen; visible back navigation; keyboard
  access and visible focus on Desktop; never rely on color alone; preserve user-entered data when
  validation fails. `docs/domain-model.md`: a name that distinguishes similar lands, `UNKNOWN` as a
  real state that must not become a default category, optional municipality/area/notes, local-only
  data, and no logging of land values.

The feature is correctly sized for one spec: one existing data model and repository call, one screen,
one navigation hop from an accepted surface, no new dependency. No file was found that already
contains edit form, edit state, or an edit affordance — this feature creates them.

## Implementation plan and tasks

1. Write `EditLandStateTest` from the acceptance contract first: prefilled state mirrors the record
   (including `UNKNOWN` → `No lo sé` and an absent municipality → empty text); blank/whitespace name
   sets the error and yields no draft; a name-only edit carries the original municipality, enums,
   preserved area and notes into the draft; clearing the municipality drafts `null`; selecting
   `No lo sé` after a known value drafts `UNKNOWN`; a deliberate `MIXED` survives; `SaveFailed` keeps
   every value and a later edit clears the failure; `WRITE_FAILED` and `LAND_MISSING` stay distinct;
   Unicode/emoji/long names survive verbatim while the draft is trimmed. Then implement the pure state
   file.
2. Write `EditLandRepositoryTest` against the fake storage: create two lands (the second with a
   municipality, known attributes, an area and notes), update the first, and assert the other land is
   equal field-by-field **and** that its encoded line in the snapshot is byte-identical while the
   snapshot keeps both records in creation order; assert the target keeps its id/`createdAt` and takes
   the new values; assert `preservedAreaHectares`/`preservedNotes` reach the stored record; assert
   `update` for an unknown id returns `null`, writes nothing, and leaves the snapshot unchanged; assert
   an `UNKNOWN` value written by an edit is read back as `UNKNOWN`.
3. Build `EditLandScreen` with resource-backed copy, the prefilled fields, the shared choice group,
   the polite live-region messages, and all required previews; reuse `add_land_*` vocabulary so a
   value reads the same in the form, the list, and the add form.
4. Modify `LandListScreen` (edit control, confirmation parameter, previews) and `AddLandScreen`
   (visibility only), then wire `App`: destination, edit action, the single `update` call, the
   `LAND_MISSING`/`WRITE_FAILED` branches, the confirmation, the list re-read on every edit return,
   and no read/write at startup or on the chat home. Confirm no `println`/`Log`/exception text.
5. Add `EditLandDesktopStoreTest` for the real Desktop file store, then run the checks below and the
   Android/Desktop manual scenarios; report any environment blocker honestly.
6. Update `CONSTRAINTS.md` and, only after implementation and independent validation,
   `feature_list.json`/`PROGRESS.md`.

Suggested new `CONSTRAINTS.md` rule, “Land editing” section:

> **MUST**: editing a land MUST update exactly one stored record: it carries every attribute the edit
> form does not collect (`areaHectares`, `notes`) through unchanged, preserves the targeted `id` and
> `createdAtEpochMillis`, never calls `create`/`delete`, and MUST NOT report an update as saved when
> `update` returned `null` or threw. Reason: `edit_land` established that correcting one detail must
> never rewrite another land or silently erase stored data.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.lands.EditLandStateTest" \
  --tests "com.jamarglex.manijero.lands.EditLandRepositoryTest" \
  --tests "com.jamarglex.manijero.lands.EditLandDesktopStoreTest"
./gradlew :shared:jvmTest
./scripts/init.sh --verify   # :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
```

Also re-run the accepted `add_land`/`land_list` reducer tests and confirm the add confirmation still
reads `add_land_saved` (`LandRepositoryTest`, `AddLandStateTest`, `LandListStateTest`,
`AddLandDesktopStoreTest` must stay green). Byte-for-byte compare the eight new strings against this
spec. There is no persistent E2E command and no Compose UI-test framework, so focused pure tests plus
Android/Desktop manual smoke are the right coverage for this bounded local slice; do not claim E2E or
automated UI coverage.

Manual Android and Desktop smoke checks:

1. Save two lands (`Los Olivos` name-only; `La Loma` with `Municipio: Martos`, `Regadío`,
   `Ecológico`). Open `Mis terrenos`, confirm each row shows a visible `Editar` control, then edit
   `Los Olivos` only, change the name, and save: the app returns to the list, the corrected name
   appears in the same position, the updated confirmation is visible and announced politely, and
   `La Loma`'s row is unchanged.
2. Edit `La Loma`: clear `Municipio`, set both choices back to `No lo sé`, save, and confirm the row
   loses the `Municipio:` line and reads `No lo sé` for both attributes; relaunch the app and confirm
   both records persist exactly as shown (this is the feature-list verification, plus the Android
   emulator and Desktop file-store runs).
3. Edit again, clear the name to blank, and save: no record is written, the plain-Spanish required
   message appears, and the other edits remain on screen; correct it and save successfully. Then
   select `Cancelar` on a further edit and confirm the list returns unchanged with no confirmation.
4. Android: enlarge system text and confirm the form, the row controls, and the actions wrap without
   clipping or horizontal scrolling; where a screen reader is available, confirm the row reads its
   details as one item and the `Editar` control is announced with the land's name. Desktop: reach
   `Editar`, `Guardar cambios`, and `Cancelar` by keyboard with visible focus, and resize narrow and
   wide.
5. Privacy check: `grep -rn "println\|Log\.\|Logger\|printStackTrace" shared/src` returns no matches,
   and no network call, permission, or dependency was added.

Capture: focused test output and counts, the full `:shared:jvmTest` and `./scripts/init.sh --verify` output
(or the exact Android blocker), the byte-for-byte string comparison, screenshots or a short record for
the two-land edit, cleared-municipality, un-known, blank-name, and failure states plus enlarged text,
and the no-logging grep result.

## Validator checklist

- [ ] `Mis terrenos` rows each expose a visible, labeled `Editar` control; the row card itself is not
      clickable, so reading a row never navigates, and the empty state still shows no row.
- [ ] With two saved lands, editing one changes exactly that record: the other land's name,
      municipality, water, production, area, notes, id, and `createdAt` are unchanged, both records
      stay in creation order, and no second record appears.
- [ ] `areaHectares` and `notes` on the edited land survive an edit that only changes collected
      fields (proved by a test, not by inspection alone).
- [ ] Unknown values stay valid: a name-only land edited elsewhere keeps `Riego`/`Producción` as
      `No lo sé`, and deliberately selecting `No lo sé` after a known value persists `UNKNOWN`
      (never `MIXED`, dryland, or conventional).
- [ ] Clearing the optional municipality persists an absent municipality (no empty string) and removes
      the `Municipio:` line; clearing is not treated as a validation error.
- [ ] A blank/whitespace name writes nothing, shows the plain-Spanish required message, keeps every
      edited value, and leaves the other land untouched.
- [ ] A failed write, or an id that is no longer stored, shows the correct plain-Spanish message with
      no confirmation and no success navigation, keeps the edited values, creates no record, and
      exposes no land data or raw exception text; the two outcomes stay distinguishable in
      `EditLandFailure`.
- [ ] `Guardar cambios` is the only primary action on the edit screen, `Cancelar` is the visible back
      control and writes nothing, and a successful edit shows the updated confirmation as a polite
      live region.
- [ ] The `update` call happens only on `SaveClicked` in `App()`, never while composing or at
      startup; `create`/`delete` are never called from an edit path; no `now` argument and no new
      dependency, clock, ViewModel, coroutine, or navigation framework was added.
- [ ] The eight new strings match this spec byte-for-byte and the reused vocabulary is unchanged; the
      row's accessible description names the land's exact saved name; product UI/state stays in
      `commonMain` with no id, area, or notes displayed and no land-data or exception logging/no
      network call.
- [ ] `EditLandStateTest`, `EditLandRepositoryTest`, and `EditLandDesktopStoreTest` pass;
      `:shared:jvmTest` passes; `./scripts/init.sh --verify` passes or the Android blocker is reported honestly
      with no E2E/automated-UI claim; the accepted `add_land`/`land_list` tests still pass and their
      copy/behavior is unchanged apart from the declared cross-feature changes.
- [ ] Scope discipline: `Land.kt`, `LandRepository.kt`, storage adapters/format, `AddLandState.kt`,
      entry points, Gradle, `scripts/init.sh`, `theme/`, backend/contracts/knowledge, and unrelated features
      are untouched; the only changes to accepted files are the four declared cross-feature items.
- [ ] `CONSTRAINTS.md` gained the “Land editing” MUST rule, and `feature_list.json`/`PROGRESS.md` were
      updated only after independent validation.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/edit_land.md. Added pure EditLandState/EditLandFailure/EditLandAction/reduce, Land.toEditLandState() and toDraftOrNull() (shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandState.kt) where the targeted id is the only record the state may write, a blank name yields no draft, and preservedAreaHectares/preservedNotes are carried through untouched, plus the stateless prefilled EditLandScreen.kt (9 previews, resource-backed copy, polite live-region failure notice distinguishing WRITE_FAILED from LAND_MISSING, one primary Guardar cambios and Cancelar as the back control).
- Cross-feature (declared in the spec): LandListScreen rows gained a visible Editar control whose accessible description names the land's exact saved name (row card still non-clickable, details still a merged node) and savedConfirmation: Boolean became confirmation: LandListConfirmation? (ADDED renders the unchanged add_land_saved byte-for-byte, UPDATED renders edit_land_saved); ChoiceGroup/ChoiceItem were widened private->internal with no behavior change; App() gained the EditLand destination and the single repository.update(reduced.landId, draft) call site inside the SaveClicked branch (never while composing or at startup), mapping a null result to LAND_MISSING and a thrown failure to WRITE_FAILED with no confirmation and no navigation, and Cancelar clears the state and shows no confirmation. No create/delete call was added to any edit path.
- New focused tests: commonTest EditLandStateTest (12) and EditLandRepositoryTest (6, in-memory LandStorage fake: one-land isolation with the other record's encoded line byte-identical and both records in creation order, preserved area/notes reaching the stored record, unknown preserved for a name-only land, deliberate unknown persisted, unknown-id update returning null and rewriting nothing) plus jvmTest EditLandDesktopStoreTest (2, real FileLandStorage in a temp dir).
- Verification: ./scripts/init.sh exit 0; focused :shared:jvmTest run 20 tests/0 failures; :shared:jvmTest 98 tests/0 failures across 14 classes (was 78, accepted AddLandStateTest 11, LandListStateTest 6, LandRepositoryTest 4, AddLandDesktopStoreTest 1 still green); ./scripts/init.sh --verify -> BUILD SUCCESSFUL with :shared:testAndroidHostTest 87/0 (was 69), :androidApp:assembleDebug APK produced, :desktopApp:build; --rerun-tasks :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build -> 91 tasks executed, same 98/0 and 87/0, BUILD SUCCESSFUL; git diff --check clean.
- Android emulator smoke (Medium_Phone_API_35, API 35, 1080x2400, fresh install + pm clear, 16 screenshots outside the repo): empty list -> saved Los Olivos (name only) and La Loma (Martos/Regadio/Ecologico) in creation order with the unchanged add confirmation; the row body is not clickable; editing only Los Olivos prefilled correctly (Regadio/Ecologico preselected; the checked rows matched those two) and changing its name returned to the list with 'Los cambios se han guardado en este dispositivo.' and the corrected name in the same first position while La Loma kept every value; editing La Loma, clearing the municipality and choosing No lo se in both groups removed the Municipio line and read No lo se for both; force-stop + relaunch kept both records exactly with no duplicates or stale confirmation; a blank name showed 'Escribe un nombre para el terreno.' with no write and kept the other edited values; Cancelar wrote nothing; font_scale 2.0 wrapped the list and the form with no horizontal overflow (max text right edge 1017 of 1080). Desktop :desktopApp:run startup smoke ran ~6.5 minutes with 0 exceptions until stopped (expected exit 143).
- Privacy/scope: grep -rn 'println|Log\.|Logger|printStackTrace|System.out' shared/src -> no matches; a byte-for-byte Python comparison of the spec's XML block against composeResources/values/strings.xml matched all eight new keys exactly and each appears once; string land_list_edit_description is used only as the Editar control's accessible description, never as body text; no new module, dependency, network call, permission, ViewModel, coroutine, or navigation framework; Land.kt, LandRepository.kt, the storage adapters/land-store-v1, AddLandState.kt, MainActivity.kt, desktopApp/main.kt, MainViewController.kt, Gradle files, scripts/init.sh, theme/, backend/contracts/knowledge stay untouched. CONSTRAINTS.md gained the 'Land editing' MUST rule.
- Honest gaps: no Compose UI-test harness exists, so the App() save-decision wiring (LAND_MISSING/WRITE_FAILED, the confirmation, the re-read on return) is covered by code inspection plus the emulator smoke and not by an automated test; the two failure branches are defensive and unit-tested rather than reproduced on the emulator; screen-reader, enlarged-text-at-2x-system-scale verification beyond wrapping, and low-digital-confidence usability stay with land_form_accessibility; no persistent E2E command exists so no E2E or automated UI coverage is claimed; updatedAtEpochMillis is still not meaningful because update receives no timestamp from the app (no clock/date dependency, carried finding F6 from land_list); areaHectares/notes are preserved but neither shown nor editable from this form.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/edit_land.md). It re-ran ./scripts/init.sh, the focused three-class run (20/0), :shared:jvmTest --rerun-tasks (98 tests / 14 classes / 0 failures), :shared:testAndroidHostTest --rerun-tasks (87 / 11 / 0), ./scripts/init.sh --verify, and a full :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build --rerun-tasks (91 tasks executed, 0 from cache); byte-for-byte checked the eight new strings and the CONSTRAINTS.md rule, and confirmed the accepted add_land/land_list suites and copy are intact and the Editar affordance did not regress the non-clickable row. For the literal feature-list verification it wrote and then deleted an independent scratch JVM probe against the real FileLandStorage: editing only the first of two lands left the other record's serialized line byte-identical, order preserved, the edited record keeping its id/createdAt; it also reproduced the byte-identical no-write on a LAND_MISSING (null) update, the blank-name no-draft/no-write path, the emptied-municipality->absent and known->UNKNOWN round-trips, and preserved area/notes, and corroborated six emulator screenshots. Scope clean: Land.kt, LandRepository.kt, the storage adapters/land-store-v1, AddLandState.kt, entry points, Gradle/version catalog, scripts/init.sh, theme/, and backend/contracts/knowledge untouched; no new module, dependency, ViewModel, coroutine, navigation framework, network call, or logging. Non-blocking findings: F1 (implementer PROGRESS.md trailing blank line, fixed before the acceptance commit), F2 (a spec sentence overstated the Cancelar re-read; amended to match the code and the accepted add_land cancel path), F3 (no Compose UI-test harness, so App() save-decision wiring is inspection + smoke only), F4 (LAND_MISSING is a defensive/unit-tested branch), F5 (updatedAtEpochMillis still not meaningful, carried land_list F6), F6 (interactive Android smoke is implementer-produced; artifacts and code semantics were corroborated).
