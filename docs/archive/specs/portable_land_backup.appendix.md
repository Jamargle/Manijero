# `portable_land_backup` Appendix

## Repository research

- Land fields are defined in `Land.kt`; the local store currently has a private text codec in `LandRepository.kt`.
- Android and Desktop stores use different platform adapters; there is no file-picker abstraction or portable import/export format.
- The existing disclosure page is shared Compose UI; existing UI tests use common state tests and JVM host tests.

## Implementation plan and tasks

1. Define a strict portable schema/version, maximum file size, field bounds, and checksum/integrity policy.
2. Add pure shared import validation and export mapping; do not reuse a private store decoder as the external file contract.
3. Add Android and Desktop file selection adapters and a warning, preview, replace confirmation, and recoverable error states.
4. Snapshot current data before replace; commit the validated backup as one aggregate-store operation.

## Verification plan

- Shared tests: round-trip, unknown fields/version, missing/duplicate IDs, oversized input, malformed values, preserve active/removed order, replace failure atomicity.
- Android and Desktop host tests exercise picker result mapping without using real user files.
- Manually inspect the warning and preview in light/dark and enlarged text; no persistent E2E harness exists.

## Evidence to capture

- Synthetic round-trip output, invalid-file no-write proof, cross-platform fixture result, and user-facing plaintext warning.

## Feature evidence

### Implementation self-verification — 2026-10-31 (implementer; not an acceptance)

**What changed.** Portable schema `manijero-land-backup` v1 (`LandBackupFormat.kt`): plaintext pretty JSON
`{format, version, checksum, lands:{active[], removed[{land, removedAtEpochMillis}]}}`; `checksum` =
`fnv1a64:` + FNV-1a 64 of the compact canonical JSON of `lands` (shared `fnv1a64Hex`, extracted unchanged
from the automatic-copy codec). Whole-file validation before preview: ≤ `MAX_LAND_BACKUP_BYTES` (4 MiB),
UTF-8 (BOM tolerated), JSON object with the format marker, integer `version == 1`, strict keys (unknown or
missing key refused), checksum, every record (non-empty id/name, non-blank zone, known enum names, custom
variety text only and always for `OTHER`, finite non-negative surface, trees ≥ 1, no empty optional text),
ids unique across both lists. Problems: `TOO_LARGE`, `NOT_A_BACKUP`, `UNSUPPORTED_VERSION`, `DAMAGED`,
`INVALID_CONTENT`. `LandRepository.snapshot()` and `replaceAll()` (pre-restore same-device automatic copy,
then one aggregate write; unreadable current store is never overwritten; a pending purge marker that
overlaps the backup is completed first). `LandBackupController`/`LandBackupState`/`LandBackupScreen`
(warning, export, choose file, preview with counts and names of both lists, replace-all danger callout,
old-file note, `Sustituir todos mis terrenos`/`Cancelar`), `Copia en un archivo` link in `Mis terrenos`,
`AppDestination.LandBackup`. Platform adapters behind `LandBackupFiles`: `AndroidLandBackupFiles`
(SAF `CreateDocument("application/json")`/`OpenDocument("*/*")` registered in `MainActivity`, no
permission) and `DesktopLandBackupFiles` (`java.awt.FileDialog` owned by the window; temp-file + move).
Privacy notice `privacy_promise_body_1` now names exported files as unencrypted, user-placed and
undeletable by the app; README, ARCHITECTURE, CONSTRAINTS, domain model and risks updated.

**Tests added.** `commonTest` (run on both the JVM and the Android host): `LandBackupFormatTest` (12:
round trip of both lists/order/all values, empty store, pinned cross-platform fixture written and read byte
for byte, key set limited to land data, absent optionals omitted, formatting/BOM/CRLF tolerance,
not-a-backup, unsupported version, truncated/altered/unknown-key/NaN/Infinity → damaged, rule-breaking
records and unknown enum → invalid, duplicate ids within and across lists, oversize and non-UTF-8 bytes),
`LandBackupRestoreTest` (10: export writes nothing locally, cancelled/failed save, preview writes nothing
then confirm replaces both lists exactly, cancel keeps lands, six invalid inputs leave primary, copies and
write log untouched, pre-restore copy order `snapshot, primary, snapshot`, refused copy or primary write
leaves lands unchanged, unreadable current store never overwritten, old file reintroduces a land deleted
with a pending purge marker, double tap ignored). `jvmTest`: `DesktopLandBackupFilesTest` (5),
`LandBackupFlowInteractionTest` (2: real `App` + `FileLandStorage` + scripted picker, warning → export →
preview counts/names/current counts → confirm → restored; damaged file message with no write).
`androidHostTest`: `AndroidLandBackupFilesTest` (6, Robolectric SDK 35, in-memory documents: save to the
created document, cancel, open + validate, oversize/null/IOException/non-UTF-8, missing provider, stale
result ignored). `AppNavigationTest` extended for `LandBackup`.

**Commands and results** (JDK 21 Zulu, macOS arm64):

- `./scripts/init.sh --feature portable_land_backup` → exit 0, `BUILD SUCCESSFUL`.
- `./gradlew :shared:jvmTest --rerun :desktopApp:build` → exit 0; 40 suites, 353 tests, 0 failures/errors/skips.
- `./gradlew :shared:testAndroidHostTest --rerun :androidApp:assembleDebug :desktopApp:build` → exit 0;
  31 suites, 325 tests, 0 failures (includes `LandBackupFormatTest` 12 and `LandBackupRestoreTest` 10 on
  the Android host, so the pinned fixture passes on both platforms); `androidApp-debug.apk` built.
- `./gradlew :shared:verifyScreenshots` → before re-recording, exactly `privacyLight`/`privacyDark` failed on
  each platform (the intended copy change); recorded only `HelpPrivacyScreenshotsTest` and
  `HelpPrivacyAndroidScreenshotsTest`, inspected the four PNGs (new sentence visible, nothing clipped), then
  `verifyScreenshots` → exit 0, all 38 Desktop and 34 Android captures pass. No land-list golden changed
  (the new link is only wired by `App`).
- `CI=true ./scripts/init.sh --fast` → exit 1 **only** on `backend-tests`: this machine has only Python
  3.9.6 and no pytest; with a temporary gitignored venv (pytest 8.4.2) the collection fails with
  `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` (backend needs Python ≥ 3.10). The
  venv was removed afterwards. No backend file changed in this feature. The other 8 checks passed
  (`gradle-jvm-test` BUILD SUCCESSFUL; contract examples 2 requests/3 responses; source catalog valid;
  retrieval/generation/abstention/clarification/land-safety evaluators: `checks failed: (none)`).
- `CI=true ./scripts/init.sh --verify` → exit 1 for the same `backend-tests` reason (its full-tier Gradle
  step was therefore run directly, above).
- Manual render review (temporary Desktop capture, deleted): start screen light 900 dp, preview dark
  360 dp, damaged-file notice at 2× text 360 dp — warning, counts, names and actions readable, no clipping.

**Not verified here.** Real SAF picker on a device/emulator and the real macOS `FileDialog`; an actual
Android-exported file opened on macOS (covered by the shared pinned fixture on both hosts instead).
Backend pytest suite (environment, see above).

### Independent validation — 2026-10-31 (validator; accept)

Verdict **accept**, no revise round. Commands run by the validator (JDK 21, `MANIJERO_PYTHON` set
to a gitignored Python 3.12 venv in `backend/.venv`):

- `./scripts/init.sh --feature portable_land_backup` — exit 0.
- `CI=true ./scripts/init.sh --fast` — exit 0; all 9 offline checks passed, `backend-tests` 888
  passed. This supersedes the implementer's backend-tests failure above, which was caused by the
  host's Python 3.9 only.
- `CI=true ./scripts/init.sh --verify` — exit 0.
- `./gradlew :shared:jvmTest --rerun :shared:testAndroidHostTest --rerun` — exit 0; JVM 353 tests,
  Android host 325 tests, 0 failures.
- `./gradlew :shared:verifyScreenshots` — exit 0; the four re-recorded privacy goldens inspected.
- `git diff --check` — clean.

All five validator checklist items pass. Non-blocking notes (import leniency vs. form rules,
Desktop `.json` auto-suffix overwrite, Android recreated-activity empty document) are recorded as
limits in the [acceptance record](../../validations/portable_land_backup.md).

## Validator checklist

- [x] Android and Desktop read the same portable format.
- [x] Restore previews then replaces only after confirmation; invalid input never mutates local data.
- [x] Export includes active and removed lands but excludes chat/service data and device identifiers.
- [x] Copy says plainly that exported files are unencrypted and outside app deletion control.
- [x] No cloud/account behavior was added.
