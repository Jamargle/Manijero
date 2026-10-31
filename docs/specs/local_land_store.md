# Feature spec: local_land_store

## Source metadata

- **Feature:** `local_land_store` — Persist multiple lands locally (`lands`).
- **Source behavior:** The app can store zero or more distinct lands on the device and retains them after the app is closed and reopened.
- **Source verification:** Create two distinct records through the repository boundary and confirm both remain after reopening the app.
- **Note from the feature list:** Choose persistence technology during implementation; define migration and recovery behavior before a real-user pilot.

## Scope

Provide a shared, platform-independent repository boundary for zero or more local
lands. Records must survive a new repository instance when backed by the same
platform storage. This feature does not add land screens, networking, accounts,
backup, or land-aware chat behavior.

## Domain contract

- `Land.id` is generated and stable; it is never derived from the name.
- `Land.name` is required and is trimmed before storage; blank names are rejected.
- Municipality, water regime, production method, approximate area, and notes are
  optional. Unknown water/production values are represented explicitly.
- Create, list, update, and delete operations are exposed by `LandRepository`.
- Updating or deleting an unknown id has no side effect (`null`/`false`).
- Records are returned in creation order and are isolated by id.

## Persistence design

`LandStorage` is a small key/value boundary (`read`/`write`) used by the shared
repository and tests. The repository stores one line-oriented format
(`land-store-v1`) with escaped fields; later features added fields to it, and
nothing has shipped that would need an older shape. Malformed records are ignored so a
partially damaged local file does not prevent the remaining records from being
opened. Writes replace the complete snapshot.

Platform adapters are deliberately thin:

- Android: `SharedPreferencesLandStorage`, constructed with an application
  `Context`.
- Desktop/JVM: `FileLandStorage`, constructed with an explicit file `Path`.

The adapters do not log land contents. The app entry points are not wired to a
land screen in this feature; later features can construct the repository at the
composition root.

## Verification

Common tests cover validation, distinct ids, update/delete isolation, unknown
values, and reopening a repository against the same fake persistent storage.
The shared JVM test task and Android compilation are the focused checks.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests LandRepositoryTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/local_land_store.appendix.md`](../archive/specs/local_land_store.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/local_land_store.md` remains the authoritative acceptance record.
