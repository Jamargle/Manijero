# Feature Spec: `recover_removed_lands`

## Source metadata

- **Feature:** `recover_removed_lands` — Restore removed lands or delete them permanently (`lands`).
- **Status at planning:** `not_started`; depends on accepted `remove_land`.
- **Source behavior:** Removing a land moves it to a recoverable list. The user can restore it or permanently delete it.
- **Feature-list verification:** Active and removed lists, restart persistence, restore, permanent deletion, and the `land-store-v1` migration are verified with focused shared tests and a Desktop file-store test.
- **Feature-list note:** Removed records remain recoverable until the user explicitly deletes them permanently. The list is local and private.

## Goal and boundaries

Replace irreversible removal with a recoverable lifecycle. `Mis terrenos` contains active lands; a separate `Terrenos eliminados` view lists removed lands with a restore action and a permanent-delete action. Removed lands never enter the chat context. No automatic expiry is introduced.

**In scope**

- Move one confirmed land from active to removed, preserving all fields and list order.
- List removed lands and restore one to the active list.
- Permanently delete one removed land only after a confirmation naming it.
- Persist lifecycle state locally on Android and Desktop and migrate existing `land-store-v1` data without loss.
- Keep removed records out of all active-land queries and requests.

**Non-goals**

- Cloud sync, accounts, multi-device restore, or backup/export (separate features).
- Automatic deletion by age, bulk actions, editing a removed land, or recovering a permanently deleted record.
- User research, legal eligibility logic, or changing land fields.

## Job story

When I remove a land by mistake or need to stop using it temporarily, I want to restore it from a separate list, so I can correct the mistake without re-entering its details.

## Acceptance scenarios

### Remove and restore

Given two active lands, when I confirm removal of one, then it disappears from `Mis terrenos`, appears in `Terrenos eliminados` with all fields intact, and the other land is unchanged.

Given a removed land, when I choose `Restaurar`, then exactly that record returns to the active list in a defined stable position and disappears from the removed list.

### Keep removed data out of answers

Given active and removed lands, when the repository builds an active-land list or a question context, then only active lands are returned, in their existing order.

### Permanently delete

Given a removed land, when I choose permanent deletion and confirm the named land, then it is removed from the app's recoverable store and neither list can read it. The action does not affect other lands.

### Persist and migrate

Given existing data encoded as `land-store-v1`, when the new app version first opens the land store, then every valid existing land is retained as active and a subsequent restart reads the migrated state without running the migration again.

Given a storage read or write failure, when a lifecycle action is attempted, then the UI reports failure plainly and does not claim that the move, restore, or deletion succeeded.

## Technical approach

1. Replace the active-only snapshot with `land-store-v2`, a versioned aggregate containing active records and removed records with a removal timestamp. Read `land-store-v1` only as a one-time migration input; write the new format atomically before switching the repository to it. Keep one current-format decoder after migration.
2. Extend `LandRepository` with explicit `listRemoved`, `restore`, `moveToRemoved`, and `permanentlyDelete` operations. Each lifecycle transition writes one aggregate snapshot, preserves record data and deterministic order, and returns an outcome that distinguishes missing records from storage failure.
3. Add a `Terrenos eliminados` surface in shared `commonMain`, linked from the existing land area. It shows saved names and known details, with separate accessible restore and permanent-delete actions. Permanent deletion uses a second confirmation.
4. Ensure the active repository API used by `LandList`, land context, and chat returns active records only. Do not place removed land data in logs, requests, or previews.
5. Keep local persistence in current platform adapters. Desktop writes must use a temporary file and atomic replacement where supported; Android commits the complete serialized snapshot as one preference value.

## Expected file changes

- `shared/src/commonMain/.../lands/LandRepository.kt`, land state/screens, and `App.kt` — lifecycle operations and UI.
- `shared/src/commonMain/.../lands/` format/model files — aggregate format and one-time migration.
- `shared/src/androidMain/.../lands/AndroidLandStorage.kt`, `shared/src/jvmMain/.../lands/FileLandStorage.kt` — safe snapshot writes.
- `shared/src/commonTest/.../lands/` and `shared/src/jvmTest/.../lands/` — migration, lifecycle, failure, and persistence coverage.
- `docs/domain-model.md`, `CONSTRAINTS.md`, and `docs/risks-and-open-questions.md` — lifecycle and local recovery rules.

## Visual design impact

The feature adds a removed-lands list and permanent-delete confirmation. Follow `DESIGN.md`, existing land screens, plain Spanish, keyboard operation, large text, and screen-reader naming. No generated visual concept is needed.

## Durable documentation impact

- `ARCHITECTURE.md`: update only if the aggregate store or migration changes the documented storage boundary.
- `CONSTRAINTS.md`: update the removal rule to distinguish recoverable removal from confirmed permanent deletion.
- `AGENTS.md`: not needed; no workflow change.
- `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and the store format notes: update to match the lifecycle and migration.

## Focused verification

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :desktopApp:build
```
<!-- verify:end -->

## Appendix

See [`recover_removed_lands.appendix.md`](../archive/specs/recover_removed_lands.appendix.md) for repository research, tasks, verification evidence, and validator checklist.
