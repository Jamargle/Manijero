# Appendix — `remove_land`

Planning and verification record for [`docs/specs/remove_land.md`](../../specs/remove_land.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/remove_land.md` remains the authoritative
acceptance record.

## Repository research

Inspected in this planning session:

- `feature_list.json`: `remove_land` depends on accepted `land_list` and `visual_foundation`;
  `android_mvp_build`/`desktop_mvp_build` depend on it. Its own note asks for one simple removal path
  and leaves the undo question open.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandRepository.kt`: `delete(id)` already
  exists and is exactly the needed primitive — it reads the records, `filterNot { it.id == id }`
  (so order is preserved and every other record's encoded line is unchanged), returns `false`
  **without writing** when the id is absent, and otherwise `writeRecords(remaining)` and returns
  `true`; it throws if `storage.read()`/`write()` throws. `LandStoreFormat.decode` already skips
  malformed individual lines and accepts a header-only snapshot as an empty store. No repository,
  model, or format change is needed.
- `shared/.../lands/Land.kt`: `Land` already carries everything the confirmation must identify (id,
  trimmed name, optional municipality, explicit `UNKNOWN` water/production, area/notes, timestamps).
- `shared/.../lands/LandListScreen.kt`: `LandListConfirmation { ADDED, UPDATED }` (line 55) and
  `LandListScreen(state, onAddLand, onEditLand, onBack, onRetry, modifier, confirmation)` (line 65);
  `LandRow` (line 177) is a non-clickable `Surface` card whose name + `Municipio:`/`Riego:`/
  `Producción:` lines are inside one `mergeDescendants` node (line 191), with a per-row `Editar`
  `TextButton` carrying the land's exact name as its accessible description (lines 215-224). The
  enum→string label mapping (`waterRegimeLabel`/`productionMethodLabel`, lines 239-252) and
  `LandRowDetail` (line 230) are `private`. This is the surface that gains the removal affordance.
- `shared/.../lands/LandListState.kt`: pure read-only list state (`lands`, `loadFailed`, `isEmpty`).
  Removal needs no change here, so this accepted file stays untouched; the pending/confirmed removal
  lives in `App()`'s own state.
- `shared/.../lands/EditLandState.kt` / `EditLandScreen.kt` / `App.kt` lines 203-244: the accepted
  house pattern this feature mirrors — a pure state file with no Compose imports, a stateless screen
  with named callbacks and a polite live-region failure line (`colorScheme.error`), a private
  `AppDestination` branch that reduces first and then performs exactly one repository write, and two
  distinct failure outcomes (`WRITE_FAILED` vs `LAND_MISSING`) that are never reported as success.
  `App.kt:97` is the destination enum; `App.kt:157-172` is the list branch. `App()` (no argument) for
  the iOS scaffold/previews stays as it is.
- `shared/src/commonMain/composeResources/values/strings.xml`: one shared file with the reusable
  vocabulary (`chat_home_lands` = `Mis terrenos`, `land_list_description`,
  `land_list_municipality`/`land_list_water`/`land_list_production`, `add_land_unknown` = `No lo sé`,
  `add_land_water_*`, `add_land_production_*`, `add_land_cancel` = `Cancelar`, `add_land_saved`,
  `edit_land_saved`, `land_list_add`/`land_list_back`/`land_list_edit`/`land_list_edit_description`/
  `land_list_empty`/`land_list_load_failed`/`land_list_retry`). No removal string exists yet.
- Tests available today: `commonTest/.../lands/LandRepositoryTest.kt` already asserts
  `update_and_delete_do_not_change_other_land` and uses an in-memory `MemoryStorage` fake with an
  injected `idGenerator`; `EditLandRepositoryTest.kt` shows the byte-identical-encoded-line technique;
  `jvmTest/.../lands/EditLandDesktopStoreTest.kt` exercises the real `FileLandStorage` in a temp dir;
  `LandListStateTest.kt`/`EditLandStateTest.kt` show pure-state test style. There is no Compose
  UI-test dependency and no persistent E2E command.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt`: each already constructs one
  `LandRepository`, so no entry-point change is required.
- `DESIGN.md` line 75: “Confirm destructive deletion in plain language and identify which land will be
  removed”; line 26 maps `danger` (`#A12622`, = `colorScheme.error`) to “errors and destructive
  actions, paired with text/icon”; lines 70-78 require one primary action, visible back navigation,
  keyboard access with visible focus, no color-only cues, and preserved user-entered data.
  `docs/domain-model.md` lines 30-38: land lifecycle `Active land → … Archive or delete`, “remove a
  land they no longer manage”, “prefer a single simple removal path with a clear confirmation and
  recovery/undo where practical”, and “Deleting a land removes its local record and prevents future
  queries from using it”. `docs/archive/build-brief.md` line 31 and `docs/archive/MasterPlanV3.md` lines 823-824/885/943
  list remove as part of the basic multiple-land flow (`My lands`: add, view, edit, remove).

The feature is correctly sized for one spec: one existing repository call, one confirmation screen,
one new per-row control, no new dependency. No file in the repository already contains a removal
state, screen, or affordance — this feature creates them.

## Implementation plan and tasks

1. Write `RemoveLandRepositoryTest` from the acceptance contract first (the accepted `delete` already
   satisfies it, so this locks the contract rather than driving new code): create two lands (the
   second with municipality, known attributes, an area, and notes), delete the first, and assert the
   snapshot holds exactly one line, the second record is equal field-by-field **and** its encoded line
   is byte-identical, and order is unchanged; assert a fresh `LandRepository(storage).list()` contains
   neither the removed id nor its name; assert `delete("land-99")` returns `false` and leaves the
   snapshot byte-identical; assert deleting the only land leaves `list()` empty, a valid header-only
   snapshot, and a reopened repository still reads empty.
2. Write `RemoveLandStateTest`: `toRemoveLandState()` copies the exact stored name and identity fields
   (including an `UNKNOWN` value and a name-only land with an absent municipality); `RemoveClicked`
   clears a previous failure and leaves the rest unchanged; `RemoveFailed` keeps every field and sets
   the failure; `WRITE_FAILED` and `LAND_MISSING` stay distinct; Unicode/long names survive verbatim.
   Then implement the pure state file.
3. Build `RemoveLandScreen` with resource-backed copy, the shared identity block, the polite
   live-region failure line, the danger confirm action, `Cancelar`, and all required previews.
4. Modify `LandListScreen` (row `Eliminar` control, `REMOVED` confirmation, extraction of the
   identity-details helper, previews), then wire `App`: destination, row action, the single `delete`
   call, the `LAND_MISSING`/`WRITE_FAILED` branches, the confirmation, the list re-read on return, and
   no write at startup, on entering the confirmation, or on the chat home. Confirm no
   `println`/`Log`/exception text and no id logging.
5. Add `RemoveLandDesktopStoreTest` for the real Desktop file store, then run the checks below and the
   Android/Desktop manual scenarios; report any environment blocker honestly.
6. Update `CONSTRAINTS.md` and, only after implementation and independent validation,
   `feature_list.json`/`PROGRESS.md`.

Suggested new `CONSTRAINTS.md` rule, “Land removal” section:

> **MUST**: removing a land MUST delete exactly one stored record, by its local id, through
> `LandRepository.delete`; it MUST NOT rewrite, reorder, or otherwise change any other record, MUST NOT
> call `create`/`update` from a removal path, MUST remove nothing before an explicit confirmation that
> names the land being removed, and MUST NOT report a removal that `delete` did not confirm (a `false`
> result or a thrown failure is never a removal). Reason: `remove_land` established that a person's
> other lands and their local-only store must survive a removal untouched, and that a permanent local
> action must never be claimed when it did not happen.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.lands.RemoveLandStateTest" \
  --tests "com.jamarglex.manijero.lands.RemoveLandRepositoryTest" \
  --tests "com.jamarglex.manijero.lands.RemoveLandDesktopStoreTest"
./gradlew :shared:jvmTest
./scripts/init.sh --verify   # :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
```

Also re-run the accepted land suites (`LandRepositoryTest`, `AddLandStateTest`, `LandListStateTest`,
`EditLandStateTest`, `EditLandRepositoryTest`, `AddLandDesktopStoreTest`, `EditLandDesktopStoreTest`)
and confirm both earlier confirmations still read `add_land_saved`/`edit_land_saved` and that the
`Editar` affordance is unchanged. Byte-for-byte compare the eight new strings against this spec. This
worktree has `local.properties` (see `PROGRESS.md`), so the Android steps should run; if the SDK is
unavailable, record the exact blocker instead of claiming an Android result. There is no persistent
E2E command and no Compose UI-test framework, so focused pure/repository tests plus Android/Desktop
manual smoke are the right coverage for this bounded local slice; do not claim E2E or automated UI
coverage.

`scripts/init.sh` is deliberately unchanged: it must keep running the documented non-blocking checks
(`./scripts/init.sh --verify` executes the shared host tests and the Android/Desktop builds) and must not be
turned into a service starter or a print-only banner.

Manual Android and Desktop smoke checks:

1. Save two lands (`Los Olivos` name-only; `La Loma` with `Municipio: Martos`, `Regadío`,
   `Ecológico`). Open `Mis terrenos` and confirm each row shows visible `Editar` and `Eliminar`
   controls, that the row card itself is not clickable, and that selecting `Eliminar` on `Los Olivos`
   shows a confirmation naming `Los Olivos`; leave via `Cancelar` and confirm the list still shows both
   lands with no confirmation (nothing was written by opening or cancelling).
2. Re-open the confirmation for `Los Olivos` and select `Eliminar el terreno`: the app returns to the
   list showing only `La Loma` with every value intact (name, municipality, water, production) and the
   plain-Spanish removed confirmation announced politely; force-stop and relaunch and confirm only
   `La Loma` is listed (this is the feature-list verification); also confirm `Volver` returns to the
   chat home and the chat still works.
3. Remove the last land: the accepted empty state appears naming `Añadir terreno`, and a new land can
   still be saved afterwards.
4. Android: set `font_scale 2.0` and confirm the rows, both controls, and the confirmation screen wrap
   without clipping or horizontal scrolling; where a screen reader is available, confirm the row reads
   its details as one item, `Eliminar` is announced with the land's exact name, and the confirmation
   is read in order. Desktop: reach `Eliminar`, `Eliminar el terreno`, and `Cancelar` by keyboard with
   visible focus, and resize narrow and wide.
5. Privacy check: `grep -rn "println\|Log\.\|Logger\|printStackTrace" shared/src` returns no matches,
   and no network call, permission, or dependency was added.

Capture: focused test output and counts, the full `:shared:jvmTest` and `./scripts/init.sh --verify` output (or
the exact Android blocker), the byte-for-byte string comparison, the two-land removal proof at line
level (the remaining record's encoded line byte-identical), screenshots or a short record for the
confirmation, cancel, removal, empty-after-last-removal, and failure states plus enlarged text, and the
no-logging grep result.

## Validator checklist

- [ ] Each `Mis terrenos` row exposes a visible, labeled `Eliminar` control; the row card itself is not
      clickable, so reading a row never navigates, and the empty state still shows no row.
- [ ] Opening the confirmation (and cancelling it) writes nothing: with two lands saved, the store and
      both rows are unchanged, and no confirmation is shown after `Cancelar`.
- [ ] The confirmation identifies the land: it names the exact saved name and repeats the same known
      details the row shows, so two same-named lands can be told apart; no id, area, or notes appear.
- [ ] With two saved lands, confirming removal removes exactly that record: the other land's name,
      municipality, water, production, area, notes, id, and `createdAt` are unchanged, the remaining
      record keeps its position in the snapshot, and no duplicate or resurrected record appears (proved
      at encoded-line level, not by inspection alone).
- [ ] After removal, a fresh read (`LandRepository(storage).list()`, the list on re-entry/retry, and
      after relaunch) contains neither the removed id nor its name, and no in-memory copy of the
      removed land survives (`removeLandState` is cleared and the list is re-read).
- [ ] Removing the last land leaves a valid header-only `land-store-v1` snapshot that reads back as
      zero lands, the accepted empty state (not a failure) is shown, and a new land can still be added.
- [ ] A failed write or an already-absent record shows the correct plain-Spanish message with no
      confirmation and no success navigation, keeps the confirmation on screen for retry or cancel,
      writes nothing, creates no record, and exposes no land data or raw exception text; the two
      outcomes stay distinguishable in `RemoveLandFailure`.
- [ ] `Eliminar el terreno` is the only primary action on the confirmation screen and uses the
      `danger` pair together with its text label; `Cancelar` is the visible back control and writes
      nothing; the removed confirmation is a polite live region on the list.
- [ ] The `delete` call happens only on the person's explicit confirmation in `App()`, never while
      composing, on entering the confirmation, or at startup; `create`/`update` are never called from a
      removal path; no new dependency, ViewModel, coroutine, dialog/snackbar, or navigation framework
      was added.
- [ ] The eight new strings match this spec byte-for-byte, the reused vocabulary is unchanged, and the
      per-row control's accessible description names the land's exact saved name; product UI/state
      stays in `commonMain` with no land-data or exception logging and no network call.
- [ ] `RemoveLandStateTest`, `RemoveLandRepositoryTest`, and `RemoveLandDesktopStoreTest` pass;
      `:shared:jvmTest` passes; `./scripts/init.sh --verify` passes or the Android blocker is reported honestly
      with no E2E/automated-UI claim; the accepted `add_land`/`land_list`/`edit_land` tests still pass
      and their copy/behavior is unchanged apart from the three declared cross-feature items.
- [ ] Scope discipline: `Land.kt`, `LandRepository.kt`, storage adapters/format, `LandListState.kt`,
      `AddLandState.kt`, `AddLandScreen.kt`, `EditLandState.kt`, `EditLandScreen.kt`, entry points,
      Gradle, `scripts/init.sh`, `theme/`, backend/contracts/knowledge, and unrelated features are untouched.
- [ ] `CONSTRAINTS.md` gained the “Land removal” MUST rule, and `feature_list.json`/`PROGRESS.md` were
      updated only after independent validation.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/remove_land.md. Added pure RemoveLandState/RemoveLandFailure/RemoveLandAction/reduce and Land.toRemoveLandState() (shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandState.kt), where landId is the only record the state may delete, the stored name and identity fields are copied verbatim (UNKNOWN stays UNKNOWN, an absent municipality stays absent), no area/notes/timestamp is carried, and RemoveClicked clears a previous failure without performing any I/O, plus the stateless RemoveLandScreen.kt (8 previews, resource-backed copy, the shared LandDetails block, a polite live-region failure notice distinguishing WRITE_FAILED from LAND_MISSING, one danger-styled Eliminar el terreno primary action, Cancelar as the back control).
- Cross-feature (declared in the spec): LandListScreen rows gained a visible Eliminar TextButton whose accessible description names the land's exact saved name (row card still non-clickable, details still a merged node), LandListConfirmation gained REMOVED rendered with remove_land_removed (ADDED/UPDATED still render add_land_saved/edit_land_saved unchanged), the row detail lines were factored into one internal @Composable LandDetails (which takes the three detail fields rather than a whole Land, because the confirmation state carries no full Land and building a fake one would invent ids/timestamps the screen must not show), and a 'just removed' preview was added. App() gained the RemoveLand destination, removeLandState, the row removal action, and the single repository.delete(cleared.landId) call site inside the explicit-confirmation branch (never while composing or at startup), mapping true to REMOVED + re-read + return to the list, false to LAND_MISSING, and a thrown failure to WRITE_FAILED with no confirmation and no navigation; Cancelar clears the state, returns to the list, and writes nothing. App() (no argument) and the platform entry points are unchanged, so the destination is unreachable with no repository. Removal-path decision recorded in the spec: one path (confirm, then one permanent delete), no undo/archive/trash/restore.
- New focused tests: commonTest RemoveLandStateTest (8: identity-field copy, name-only land with absent municipality and UNKNOWN attributes, RemoveClicked clearing a failure and unchanged identity, RemoveFailed keeping every field and staying retryable, the two failures distinguishable, actions never retargeting, Unicode/emoji/long names verbatim, only-identity-fields data equality) and RemoveLandRepositoryTest (5, in-memory LandStorage fake: exactly-one removal with the other record equal field-by-field and its encoded line byte-identical plus one line in the snapshot, creation order preserved when a middle land is removed at encoded-line level, a fresh repository returning neither the removed id nor name, an unknown id returning false with a byte-identical snapshot, and the last-land removal leaving a valid header-only snapshot that reopens empty) plus jvmTest RemoveLandDesktopStoreTest (2, real FileLandStorage in a temp dir: the removed record and name leave the file, the other record survives reopening unchanged, and removing the last land leaves a reopenable empty store).
- Verification: ./scripts/init.sh exit 0 (created the worktree local.properties with sdk.dir=/Users/jose/Library/Android/sdk); focused :shared:jvmTest run 15 tests/0 failures (RemoveLandStateTest 8, RemoveLandRepositoryTest 5, RemoveLandDesktopStoreTest 2); :shared:jvmTest 117 tests/0 failures across 17 suites (LandRepositoryTest 4, AddLandStateTest 11, LandListStateTest 6, EditLandStateTest 12, EditLandRepositoryTest 6, AddLandDesktopStoreTest 1, EditLandDesktopStoreTest 2 and the unchanged chat/theme suites all green); ./scripts/init.sh --verify -> BUILD SUCCESSFUL (91 tasks) with :shared:testAndroidHostTest 104/0 across 13 suites, :androidApp:assembleDebug APK produced, :desktopApp:build; :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; git diff --check clean; no Color(0x outside theme/.
- String/privacy checks: a Python byte-for-byte comparison of the spec's XML block against composeResources/values/strings.xml matched all eight new keys exactly (land_list_remove, land_list_remove_description, remove_land_title, remove_land_confirm, remove_land_remove, remove_land_removed, remove_land_failed, remove_land_missing); add_land_saved/edit_land_saved/land_list_edit are unchanged and each new key appears once; the row contentDescription renders land_list_remove_description with the land's exact saved name and is never body text. grep -rn 'println|Log\.|Logger|printStackTrace|System.out' shared/src androidApp/src desktopApp/src -> no matches; no uses-permission in any source manifest and the merged debug manifest declares no network permission; no new module, dependency, ViewModel, coroutine, dialog/snackbar, navigation framework, network call, or permission.
- Android emulator smoke (Medium_Phone_API_35, API 35, 1080x2400, fresh install + pm clear, screenshots outside the repo): saved two lands (Los Olivos name-only; La Loma with Municipio Martos, Regadio, Ecologico) with visible Editar and Eliminar controls per row and a non-clickable row card; the Eliminar control's accessible description read 'Eliminar el terreno «Los Olivos»'; the confirmation named Los Olivos with its Riego/Produccion lines, 'Eliminar el terreno', and 'Cancelar'; Cancelar returned to the list with both lands and no confirmation and the SharedPreferences store was byte-identical before/after (diff clean), so opening and cancelling wrote nothing; confirming removal returned to Mis terrenos showing only La Loma with every value intact and 'El terreno se ha eliminado de este dispositivo.', with the store becoming land-store-v1 + the La Loma line byte-identical to before (the removed line absent); force-stop + relaunch listed only La Loma (the literal feature-list verification); removing the last land left the valid header-only land-store-v1 snapshot, showed the accepted empty state naming Anadir terreno plus the removed confirmation, and a new land (Olivar Nuevo) could still be saved; Volver returned to the chat home; font_scale 2.0 wrapped the list, both controls, and the confirmation screen with no horizontal overflow (max text right edge 1017 of 1080).
- CONSTRAINTS.md gained the 'Land removal' MUST rule (delete exactly one record by its local id through LandRepository.delete, never rewrite/reorder another record, never call create/update from a removal path, remove nothing before an explicit confirmation that names the land, and never report a removal that delete did not confirm).
- Honest gaps: no undo and no backup (a confirmed removal is permanent and local-only; stored areaHectares/notes are lost with the record and the copy says removal cannot be undone); LAND_MISSING is a defensive/unit-tested branch reachable only if a record disappears between the list read and the confirmation, and neither failure branch was reproduced on the emulator because the accepted storage adapters write successfully; two same-named name-only unknown lands still render as near-identical rows; the list read and delete stay synchronous on the composition frame (no ViewModel/coroutine); there is no Compose UI-test harness and no persistent E2E command, so the App() removal-decision wiring is covered by code inspection plus the emulator smoke and no E2E/automated UI coverage is claimed; no screen-reader session was captured (the contentDescription and merged details node were confirmed from the accessibility-tree dump) and a full accessibility audit of removal needs its own follow-up; carried land_list finding F6 (createdAtEpochMillis still the default 0 because no clock is injected) is unchanged. Self-verified; awaiting independent validation, so not marked accepted.
- Scope: only CONSTRAINTS.md, feature_list.json, PROGRESS.md, strings.xml, App.kt, LandListScreen.kt, docs/specs/remove_land.md, and the new RemoveLandState.kt/RemoveLandScreen.kt/RemoveLandRepositoryTest.kt/RemoveLandStateTest.kt/RemoveLandDesktopStoreTest.kt changed (git status --porcelain); Land.kt, LandRepository.kt, the storage adapters/land-store-v1, LandListState.kt, AddLandState.kt/AddLandScreen.kt, EditLandState.kt/EditLandScreen.kt, entry points, Gradle/version catalog, scripts/init.sh, theme/, and backend/contracts/knowledge are untouched.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/remove_land.md). It re-ran ./scripts/init.sh, the focused three-class run (15/0, forced --rerun-tasks after a FROM-CACHE first run), :shared:jvmTest --rerun-tasks (117 tests / 17 suites / 0), :shared:testAndroidHostTest --rerun-tasks (104 / 13 / 0), :shared:compileKotlinIosSimulatorArm64 --rerun-tasks, and ./scripts/init.sh --verify (91 tasks, exit 0; APK 35.8 MB + desktopApp.jar), byte-for-byte checked the eight new strings against the spec, the CONSTRAINTS.md rule, and scope discipline (Land.kt, LandRepository.kt, adapters/land-store-v1, LandListState.kt, add/edit state/screens, entry points, Gradle, scripts/init.sh, theme/, backend/contracts/knowledge untouched). For the literal feature-list verification it wrote and deleted its own scratch JVM probe against the real FileLandStorage (4/4: two-land removal with the surviving encoded line byte-identical, an absent-id delete returning false with a byte-identical snapshot, a throwing write leaving the store untouched, and a header-only last-land store reopening empty) and independently re-drove an Android emulator (Medium_Phone_API_35, fresh install + pm clear): per-row Eliminar with the exact-name accessibility description, a confirmation naming the land, Cancelar leaving the SharedPreferences store byte-identical (opening and cancelling wrote nothing), confirming removing exactly Los Olivos with La Loma's line byte-identical, force-stop + relaunch listing only La Loma, the last-land header-only store + accepted empty state + successful re-add, and font_scale 2.0 wrapping with max right edge 1017/1080. It confirmed the identity-only confirmation payload, no logging/egress/permission, the single delete call site inside the explicit-confirmation callback, and that a false/thrown result is never reported as a removal. Non-blocking findings F1-F6 recorded (F1 spec's LandDetails(land) superseded by the documented (municipality, waterRegime, productionMethod) extraction; F2 stacked full-width row buttons vs the one-line sketch; F3 no Compose UI-test harness, happy/cancel/last-land covered by the validator's emulator run and the failure paths by its probe with durable UI coverage owed to a future accessibility-style feature; F4 unreachable null-repository dead branch; F5 no BackHandler, matching the accepted add/edit screens; F6 carried createdAtEpochMillis default 0).
