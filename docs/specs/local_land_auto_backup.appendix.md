# `local_land_auto_backup` Appendix

## Repository research

- Android stores the whole current snapshot in a private `SharedPreferences` value.
- Desktop `FileLandStorage` currently writes directly to the land file under `~/.manijero/`.
- `LandRepository` is the shared single write gate; the prior feature introduces active/removed aggregate data.

## Implementation plan and tasks

1. Agree bounded retention count/size and a stable local aggregate layout without adding a cloud path.
2. Add integrity validation, bounded rotation, and recovery from separate same-device snapshots.
3. Add a durable purge marker so a crash cannot expose a record selected for permanent deletion through a stale snapshot; clear it only after all copies are sanitized.
4. Add failure/recovery copy and update local-data disclosure.

## Verification plan

- In-memory storage tests cover rotation, invalid snapshots, newest-valid selection, commit failures, and purge.
- Desktop temporary-directory test covers restart and atomic replacement.
- `:shared:jvmTest` plus `:desktopApp:build`; no persistent E2E harness exists.

## Evidence to capture

- Snapshot count/size policy, synthetic store before/after recovery, and failure outcome.
- Confirm no snapshot path uses a network API or OS cloud-backup setting.

## Feature evidence

## Validator checklist

- [ ] Snapshots are written only after successful primary writes.
- [ ] Recovery never silently turns corruption into an empty store.
- [ ] Retention is bounded and permanent deletion purges all app-managed copies.
- [ ] User-facing copy does not claim protection from device loss.
- [ ] Progress and feature status change only after verification/acceptance.
