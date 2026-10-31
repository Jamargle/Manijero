# `recover_removed_lands` Appendix

## Repository research

Research recorded at planning time; the implemented state is in **Feature evidence** below.

- `LandRepository.kt` stored active lands in one `land-store-v1` string; `delete(id)` removed them
  irreversibly.
- Android uses one `SharedPreferences` value; Desktop uses `~/.manijero/lands-v1.txt` through `FileLandStorage`.
- `RemoveLandScreen` confirmed a permanent delete at planning time. `App.kt` and `LandContextBuilder` consume `LandRepository.list()`.
- No trash/recovery abstraction or persistent UI test harness existed. Shared JVM tests and Desktop file-store tests are established patterns.

## Implementation plan and tasks

1. Specify the aggregate current snapshot format and strict one-time `land-store-v1` migration. Preserve every decoded record; do not silently discard active data on migration write failure.
2. Add explicit lifecycle repository operations and outcome types; ensure each write is one complete snapshot and existing `list()` remains active-only.
3. Add the removed-lands destination, restore action, and separately confirmed permanent deletion in `commonMain`.
4. Update platform storage for safe whole-snapshot replacement and update lifecycle/domain/privacy guidance.

## Verification plan

- Shared tests: v1 migration, malformed records, stable active/removed order, duplicate names, restore, permanent deletion, missing ids, write failure, and no removed records in active context.
- Desktop test: create, remove, restart, restore, and permanently delete through a temporary file.
- Run the focused block in the contract; no E2E harness exists, so state/repository tests plus the Desktop store test are the current verification route.

## Evidence to capture

- Test names and results for migration and each lifecycle transition.
- Before/after active and removed records with synthetic data only.
- Confirmation that no user land data was used in fixtures or logs.

## Feature evidence

**Scope implemented (2026-10-27).** Removal now moves one confirmed active land into a local removed
list; `Terrenos eliminados` lists those records with `Restaurar` and `Borrar para siempre`;
permanent deletion has its own second confirmation naming the land. The store is the
`land-store-v2` aggregate (active section + removed section with `removedAt`), a valid
`land-store-v1` snapshot is migrated once on first read, and `LandRepository.list()` remains
active-only, so removed records never reach `landContextFor` or an answer request. Desktop writes
the aggregate to a same-directory temporary file and replaces the store atomically when supported;
Android still writes one `SharedPreferences` value with a synchronous `commit()`.

### Verification commands and results

- `./gradlew :shared:jvmTest` — **304 tests, 0 failures, 0 errors, 0 skipped** across 33 suites.
  Focused classes: `LandStoreFormatTest` 10/10, `LandMigrationTest` 5/5,
  `LandLifecycleRepositoryTest` 8/8, `RemoveLandRepositoryTest` 5/5, `RemovedLandsStateTest` 10/10,
  `LandScreenInteractionTest` 5/5, `RecoverRemovedLandsDesktopStoreTest` 2/2,
  `AppNavigationTest` 20/20, plus the updated `LandRepositoryTest` 6/6,
  `EditLandRepositoryTest` 6/6, `RemoveLandDesktopStoreTest` 2/2, `RemoveLandStateTest` 8/8,
  `LandListStateTest` 10/10, and `LandSearchTest` 11/11.
- `./scripts/init.sh --feature recover_removed_lands` (the spec block
  `./gradlew :shared:jvmTest :desktopApp:build`) — **BUILD SUCCESSFUL**.
- `./scripts/init.sh --fast` — **All 9 offline checks passed; Fast tier passed.**
- `./scripts/init.sh --verify` — **BUILD SUCCESSFUL**; the Android host test task ran **280 tests,
  0 failures** across 26 suites, and `:androidApp:assembleDebug` plus `:desktopApp:build` succeeded.
- `./gradlew :shared:verifyScreenshots` — **BUILD SUCCESSFUL**, but the suite does not cover this
  feature's new surfaces: it has no golden for `RemovedLandsScreen` or `PermanentlyDeleteLandScreen`,
  and the existing `land_list_*` golden still renders the old `Eliminar` label because the 0.1%
  per-pixel threshold accepts that short copy change. The passing command therefore does not verify
  the new `Quitar` label or either new screen.
- Cross-feature regression inside the same run: the accepted focused classes still pass —
  `LandRepositoryTest` 6/6 (`local_land_store`), `LandListStateTest` 10/10 (`land_list`),
  `RemoveLandStateTest` 8/8 + `RemoveLandRepositoryTest` 5/5 + `RemoveLandDesktopStoreTest` 2/2
  (`remove_land`), and the `add_land`/`edit_land` focused classes; `desktop_mvp_build` publishes the
  same `:shared:jvmTest :desktopApp:build` block verified above.

Migration evidence (`LandMigrationTest`): `a_v1_store_migrates_every_decodable_record_as_active`,
`the_migration_writes_once_and_a_restart_reads_it_without_migrating_again`,
`a_refused_migration_write_throws_and_keeps_the_v1_store`,
`a_corrupt_v1_line_never_becomes_a_land`, `a_header_only_v1_store_migrates_to_an_empty_aggregate`.
Lifecycle evidence (`LandLifecycleRepositoryTest`):
`moving_a_land_preserves_every_field_and_the_order_of_the_rest`,
`restore_returns_exactly_that_record_to_the_end_of_the_active_list`,
`restore_of_a_missing_removed_id_reports_missing_and_writes_nothing`,
`permanent_deletion_removes_only_the_named_removed_record`,
`an_active_id_is_not_a_permanent_deletion_target`,
`duplicate_names_are_told_apart_by_their_ids`,
`a_refused_write_reports_storage_failure_and_keeps_the_store`,
`removed_lands_never_reach_the_active_list_or_a_question_context`.
Desktop persistence evidence (`RecoverRemovedLandsDesktopStoreTest`):
`create_remove_restart_restore_and_permanently_delete_through_the_file` and
`a_v1_file_migrates_once_and_keeps_every_record_as_active`; the first also asserts that no temporary
file survives a completed write. UI evidence (`LandScreenInteractionTest`):
`removeConfirmationMovesTheLandOnlyAfterExplicitConfirmation`,
`removedRowsRestoreOrOpenTheConfirmedDeletionForTheirOwnLand`,
`permanentDeletionDeletesOnlyAfterItsOwnConfirmation`,
`theLandsListOnlyOpensTheRemovedListWhenItsCallbackIsWired`; `AppNavigationTest` adds
`the removed list returns to the lands list and its confirmation to the removed list` and
`only the land forms and the deletion confirmation hide the navigation bars`.

### Synthetic before/after fixtures

Lifecycle fixture (custom ids `land-0`…`land-2`, synthetic data only; moving `land-1` at
`removedAt=99`):

```text
land-store-v2
active
land-0|Los Olivos|El Llano||UNKNOWN|UNKNOWN|UNKNOWN|||1|1
land-1|La Loma|Linde del arroyo|Martos|IRRIGATED|ORGANIC|OTHER|Royal de Cazorla|3.5|120|Junto al arroyo|2|2
land-2|El Cortijo|Las Eras||UNKNOWN|UNKNOWN|UNKNOWN|||3|3
removed
```

```text
land-store-v2
active
land-0|Los Olivos|El Llano||UNKNOWN|UNKNOWN|UNKNOWN|||1|1
land-2|El Cortijo|Las Eras||UNKNOWN|UNKNOWN|UNKNOWN|||3|3
removed
land-1|La Loma|Linde del arroyo|Martos|IRRIGATED|ORGANIC|OTHER|Royal de Cazorla|3.5|120|Junto al arroyo|2|2|99
```

Migration fixture used by `RecoverRemovedLandsDesktopStoreTest` (a real temporary file):

```text
land-store-v1
land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
land-2|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|3|4
```

After the first `list()`, the file is `land-store-v2`, both records are active and byte-identical,
the removed section is empty, and a second repository instance reads the same file without writing
it again.

All fixtures are synthetic. No user land data, name, note, device identifier, or raw question was
used in a test, fixture, log, or failure message. No production code logs land records; the UI
receives only the throwable-free `LandLifecycleResult`/state values.

### Repair pass (2026-10-27)

Documentation-only correction; no lifecycle, store-format, or navigation code changed.
`CONSTRAINTS.md` "Client land context" now says **every active stored land**, uses `general` with
`lands: []` only when **no active land is stored**, and explicitly forbids removed-list lands from
`land_context`, a clarification, or an answer request even when they are the only stored records.
`LandContextBuilder`'s `landContextFor` and `askRequestFor` KDoc now use the same active-only wording,
as does the matching `LandContextBuilderTest` policy comment.
`DESIGN.md` "App shell" now records `Terrenos eliminados` as a detail route with visible bars and its
own `Volver`, the `Borrar para siempre` confirmation as a bars-hidden route with `Cancelar`, and the
matching system-back routes (removed list → lands, confirmation → removed list). The remaining findings
below are recorded without changing behavior. After these documentation and KDoc edits the required gates
were re-run: `./scripts/init.sh --feature recover_removed_lands` — **BUILD SUCCESSFUL** (304 tests,
0 failures in `:shared:jvmTest`), and `./scripts/init.sh --fast` — **All 9 offline checks passed;
Fast tier passed.** A grep for the pre-lifecycle stored-land wording now returns no match in the
`Client land context` section or `LandContextBuilder.kt`; the remaining matches are the separate
zone rule in `CONSTRAINTS.md` ("Land fields and storage") and accepted historical records that this
pass must not edit.

### Limitations and findings

- **Screenshot coverage is incomplete.** The screenshot suite has no goldens for
  `RemovedLandsScreen` or `PermanentlyDeleteLandScreen`, and the `land_list_*` goldens still render
  the old `Eliminar` label because the 0.1% per-pixel threshold accepts that short copy change.
  Passing `verifyScreenshots` is not evidence for the new `Quitar` copy or either new screen.
- No Android emulator or device run was performed, so this evidence does not prove device rendering
  or TalkBack/screen-reader output. Accessibility is code-level: explicit row/action descriptions,
  merged detail nodes, headings, error live regions, and 48 dp-equivalent Material controls; the
  permanent-delete confirmation button also names the land in its accessible description. The new
  screens have previews at compact/wide/large-font sizes.
- No app-managed automatic snapshot feature exists yet, so permanent deletion currently removes the
  record from the single aggregate store; the later `local_land_auto_backup`/`portable_land_backup`
  features must extend that guarantee to their copies.
- The Android `SharedPreferences` `commit()` path is not instrumented; the shared repository tests use
  a fake `LandStorage` to prove a refused write returns `StorageFailed` and leaves the stored
  aggregate untouched. Desktop atomic replacement is exercised through the real file store, including
  the no-leftover-temporary-file assertion.
- The Desktop file keeps its existing name `lands-v1.txt` to preserve the installed path; the
  **format** inside is `land-store-v2`. The name is historical, not a second format.
- **`removedAt` is 0 in production.** `LandRepository` defaults `nowEpochMillis` to `{ 0L }`
  (the same default-clock gap as `createdAt`/`updatedAt`), and both platform entry points construct
  it without a clock, so `RemovedLand.removedAtEpochMillis` is 0 for a real removal. Tests pass
  explicit `now` values. The field is stored but not displayed, and removal order is the append order
  rather than a timestamp sort, so this is a data-quality gap, not a lifecycle break.
- **A read failure throws.** `moveToRemoved`, `restore`, and `permanentlyDelete` call
  `readSnapshot()` before writing; a storage `read()` failure propagates instead of returning
  `StorageFailed`, which only covers a refused write. `App.kt` wraps each call in `runCatching` and
  shows the failure copy, but the repository API itself has no read-failure outcome. Tests cover
  refused writes; a throwing `read()` is not covered.
- `docs/specs/remove_land.md` (accepted) still quotes the previous Spanish copy and describes removal
  as irreversible, and several accepted records (`remove_land.appendix.md`,
  `desktop_mvp_build.md`, `land_measurement_fields.*`, `land_setup_fields_decision.md`) still describe
  `land-store-v1` as the current format. The accepted `minimal_land_context` and
  `chat_question_submission` records still use the pre-lifecycle all-stored-land/no-land wording
  where this feature now means active lands. Those historical acceptance records were intentionally
  left untouched per this task's scope; `README.md`, `docs/domain-model.md`, `CONSTRAINTS.md`, and
  `LandStoreFormat`'s KDoc now describe v2 and the migration. The orchestrator should decide when to
  amend the accepted records.
- The stale static gate in `docs/specs/land_measurement_fields.md` still greps `land-store-v1` inside
  `LandRepository.kt` and forbids `land-store-v2` there. It passes only because `LandRepository.kt`
  keeps a `land-store-v1` KDoc mention and the v2 literal lives in `LandStoreFormat.kt`; that grep
  does not describe the current format and should not be treated as migration evidence.
- No E2E harness exists in this repository, so the current evidence is repository/state/Compose-test
  plus the real Desktop file-store test; the manual Android/Desktop flow and owner usability review
  remain for validation/pilot readiness.


## Validator checklist

- [x] Existing valid `land-store-v1` records migrate without loss.
- [x] Removal is recoverable and permanent deletion requires a second confirmation.
- [x] Only active records reach land context and answer requests.
- [x] Storage failure never displays false success; a refused write returns `StorageFailed` (a refused
  read throws and `App.kt` still shows the failure copy — see the finding above).
- [x] UI follows `DESIGN.md` and remains usable with keyboard and assistive technology at code level;
  no device or TalkBack evidence exists yet.
- [x] `feature_list.json` and `PROGRESS.md` are updated only after verification and acceptance.
