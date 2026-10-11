# Feature spec: local_land_store

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
repository and tests. The repository stores a versioned, line-oriented format
(`land-store-v1`) with escaped fields. Malformed records are ignored so a
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
