# `recover_removed_lands` Appendix

## Repository research

- `LandRepository.kt` stores active lands in one `land-store-v1` string; `delete(id)` currently removes irreversibly.
- Android uses one `SharedPreferences` value; Desktop uses `~/.manijero/lands-v1.txt` through `FileLandStorage`.
- `RemoveLandScreen` confirms a permanent delete today. `App.kt` and `LandContextBuilder` consume `LandRepository.list()`.
- No trash/recovery abstraction or persistent UI test harness exists. Shared JVM tests and Desktop file-store tests are established patterns.

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

## Validator checklist

- [ ] Existing valid `land-store-v1` records migrate without loss.
- [ ] Removal is recoverable and permanent deletion requires a second confirmation.
- [ ] Only active records reach land context and answer requests.
- [ ] Storage failure never displays false success.
- [ ] UI follows `DESIGN.md` and remains usable with keyboard and assistive technology.
- [ ] `feature_list.json` and `PROGRESS.md` are updated only after verification and acceptance.
