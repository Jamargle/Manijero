# Feature Spec: `local_land_auto_backup`

## Source metadata

- **Feature:** `local_land_auto_backup` — Keep recoverable on-device land backups (`lands`).
- **Status at planning:** `not_started`; depends on `local_land_store` and `recover_removed_lands`.
- **Source behavior:** Maintain automatic local snapshots of active and removed land data on the same device; no cloud destination.
- **Feature-list verification:** Simulated writes, restart recovery, retention pruning, and permanent-delete purge are verified on shared and Desktop storage.
- **Feature-list note:** This protects against some local write failures. It does not protect against loss of the device or app data container.

## Goal and boundaries

Keep a bounded set of app-managed, same-device snapshots so a recoverable copy exists after successful land changes. A snapshot is local to the app's Android preferences or Desktop data directory. It is not a cloud backup and must not be described as recovery after device loss.

**In scope:** snapshots after successful aggregate-store writes; corruption detection; safe restore from the newest valid snapshot if the primary snapshot is unreadable; bounded retention; permanent deletion purges that land from every app-managed snapshot.

**Non-goals:** cloud sync, operating-system backup, user-selected export/import (separate feature), encryption claims beyond platform storage behavior, or recovery from a lost/uninstalled device.

## Job story

When a local store write is interrupted or its current snapshot becomes unreadable, I want the app to recover from a recent on-device copy, so my lands are not lost because of one damaged write.

## Acceptance scenarios

### Snapshot successful changes

Given a valid land store, when a create, edit, remove, restore, or permanent-delete operation commits, then a valid bounded snapshot is updated without changing active/removed ordering or exposing data over the network.

### Recover a damaged primary

Given an unreadable primary snapshot and at least one valid automatic snapshot, when the app opens the store, then it reports the recovery plainly, restores the newest valid snapshot, and never treats a partial decode as a complete recovery.

### Permanent deletion clears automatic copies

Given a land exists in the removed list and in retained automatic snapshots, when the user permanently deletes it, then it is absent from the primary store and every retained automatic snapshot after the operation succeeds.

### Bounded local retention

Given repeated successful store writes, when the snapshot limit is reached, then older copies are pruned by the documented retention policy and storage remains bounded.

### No false guarantee

Given a device or app data directory is lost, when the user reads the disclosure, then it does not imply that this same-device system can recover those records.

## Technical approach

Keep bounded whole-state snapshots separate from the primary `land-store-v2` value so they can recover primary corruption. Each snapshot includes integrity metadata. Write a snapshot only after a successful land change. Permanent deletion uses a durable purge marker before rewriting copies; every restore path filters records marked for purge, and the marker is cleared only after the primary and all retained snapshots are sanitized. On primary corruption, select the newest fully valid snapshot and require a clear recovery outcome before normal use; do not silently initialize an empty store. The exact snapshot count/size policy is an implementation decision and must be recorded in the feature evidence.

## Expected file changes

- Shared land repository/storage interfaces and tests; Android `SharedPreferencesLandStorage` and Desktop `FileLandStorage` adapters.
- `App.kt` recovery state/copy and shared resources for a truthful recovery message.
- `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and privacy disclosure/spec if copy changes.

## Visual design impact

UI may need a recovery notice and retry/continue action. Follow `DESIGN.md`; keep failure and recovered states distinct and accessible. No generated concept is needed.

## Durable documentation impact

- `ARCHITECTURE.md`: update local storage description if it now includes rotating snapshots.
- `CONSTRAINTS.md`: document local-only scope, bounded retention, and deletion propagation to app-managed copies.
- `AGENTS.md`: not needed.
- `docs/risks-and-open-questions.md`: distinguish same-device recovery from device-loss backup.

## Focused verification

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :desktopApp:build
```
<!-- verify:end -->

## Appendix

See [`local_land_auto_backup.appendix.md`](local_land_auto_backup.appendix.md).
