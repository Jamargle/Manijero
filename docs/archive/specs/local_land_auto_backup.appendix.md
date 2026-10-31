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

### What changed

- `shared/.../lands/LandRepository.kt`: the aggregate store now takes an optional
  `LandSnapshotStorage` (defaulting to the same adapter when it implements it) and writes one
  automatic copy only after a successful primary write. A read validates the primary structurally,
  rebuilds it from the newest fully valid copy when it is unreadable, reports one
  `LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY` through `consumeRecovery()`, and throws
  `LandStoreUnreadableException` instead of opening an empty store. `permanentlyDelete` writes the
  durable purge marker first, then the primary aggregate, then sanitizes every retained copy, and
  clears the marker last. Every read filters marked ids.
- `shared/.../lands/LandAutomaticCopies.kt` (new): `MAX_AUTOMATIC_LAND_SNAPSHOTS`,
  `LandSnapshotStorage`, `LandStoreRecovery`, `LandStoreUnreadableException`, the snapshot envelope
  (`manijero-land-snapshot-1` + FNV-1a 64 checksum + whole `land-store-v2` body) and the purge-marker
  line format.
- `shared/.../lands/LandStoreFormat.kt`: one decoder now returns `null` for a value that is not a
  complete current store (missing header/section markers, repeated removed marker), and a strict
  `requireEveryRecord` mode rejects a copy with any undecodable record. The v1 reader and the
  lenient per-record skip for a complete current store are unchanged.
- `shared/src/androidMain/.../AndroidLandStorage.kt` and
  `shared/src/jvmMain/.../FileLandStorage.kt`: both adapters implement `LandSnapshotStorage`.
  Android uses `land_store_snapshot_1..3` plus `land_store_purge` in the same private preferences
  commit; Desktop uses sibling `lands-v1.txt.snapshot-1..3` files plus `lands-v1.txt.purge`, written
  through the existing temporary-file + atomic-replace path.
- `shared/.../App.kt` and `shared/.../lands/LandListScreen.kt`: a recovered read shows a neutral
  `He recuperado tus terrenos` callout with the plain explanation and one `Entendido` action, while a
  failed read keeps the separate error notice and `Reintentar`. Copy lives in `strings.xml`.
- Android backup boundary (repair after validator `revise`): the manifest previously declared
  `android:allowBackup="true"` with no rule files, so Android Auto Backup and device-to-device
  transfer could carry `shared_prefs/manijero_lands.xml` (`land_store`,
  `land_store_snapshot_1..3`, `land_store_purge`) off the device while the shipped privacy copy said
  there is no copy on the internet or on another device. `androidApp/src/main/AndroidManifest.xml`
  now declares `android:fullBackupContent="@xml/backup_rules"` and
  `android:dataExtractionRules="@xml/data_extraction_rules"`; the two new files
  (`androidApp/src/main/res/xml/backup_rules.xml`, `.../data_extraction_rules.xml`) exclude
  `domain="sharedpref" path="manijero_lands.xml"` from Auto Backup (API 29-30) and from both
  `<cloud-backup>` and `<device-transfer>` (API 31+). `allowBackup` stays `true` because no other app
  data is land data and `false` would change unrelated platform behaviour.
- `shared/src/jvmTest/.../platform/AndroidBackupExclusionGuardTest.kt` (new, fast tier): reads the
  checked-in manifest and both rule files, derives the excluded preferences name from
  `AndroidLandStorage`'s `getSharedPreferences("manijero_lands", …)` call, and fails when the
  manifest stops referencing a rule file, a rule file stops excluding that file, or a rule file
  starts including it. `shared/build.gradle.kts` declares the manifest and `res/xml` as `jvmTest`
  inputs so the guard re-runs locally when they change. Negative control: deleting
  `android:dataExtractionRules` from the manifest made the guard fail; restoring it made it pass.
- Privacy copy (`privacy_local_body_3`, `privacy_promise_body_1`) now states that the app keeps
  several automatic copies on the same device and that they do not survive losing the device or
  deleting the app. Nothing claims device-loss protection or a cloud copy.
- Durable docs: `ARCHITECTURE.md`, `CONSTRAINTS.md` (new "Land automatic copies" rules including
  the Android OS-backup exclusion, updated disclosure rule), `docs/domain-model.md`,
  `docs/risks-and-open-questions.md`, `PROGRESS.md` limitations, and the screenshot inventory in
  `docs/screenshot-regression.md`.
- Screenshot goldens re-recorded for the intentional privacy copy change only: 4 Desktop
  (`privacy_light`, `privacy_dark`, `privacy_phone_light`, `privacy_phone_dark`) and 4 Android
  (same names). The two incidental land-list rewrites produced by the record task were reverted;
  both suites verify green with only the privacy images changed.
- Recovery-callout goldens added (repair after validator `revise`, finding 6): 4 Desktop
  (`land_list_recovery_light`, `land_list_recovery_dark`, `land_list_recovery_light_phone`,
  `land_list_recovery_dark_phone`, the first two at 900×1200 dp) and 4 Android (same names; the
  first two use the per-method `es-rES-w900dp-h1200dp-mdpi` qualifier, the phone pair the class
  360×800 dp viewport). They were recorded with a `--tests` filter that matched only the four new
  methods, and `git status` showed no other capture changed. The implementer inspected all eight:
  the callout title, body and `Entendido` action are fully inside each frame, the list and summary
  below match the existing land captures, and no control overlaps or is half-painted. The 1200 dp
  frame clips the second land row exactly like the existing `land_list_light` frame clips it, which
  is the accepted framing of that capture. Totals are now 38 Desktop and 34 Android captures.

### Chosen retention policy

- **Count:** at most `MAX_AUTOMATIC_LAND_SNAPSHOTS = 3` copies, newest first; each committed change
  pushes the previous copies down and drops the oldest. Copies are whole aggregates, not deltas, so
  the user-visible options and the earlier states are never reconstructed from partial data.
- **Size:** bounded by the data the person already has — at most three encoded `land-store-v2`
  aggregates plus one `manijero-land-snapshot-1` header/checksum line per copy (well under 100 extra
  bytes per copy). No separate byte cap is enforced because a cap below the user's aggregate would
  silently stop protecting larger stores; the count is the bound.
- **Purge marker:** one escaped id per pending permanent deletion; cleared after the primary and all
  retained copies are clean, so it is normally empty.

### Verification (raw results)

| Command | Result |
|---|---|
| `./gradlew :shared:jvmTest :desktopApp:build` | `BUILD SUCCESSFUL`; `:shared:jvmTest` 323 tests, 0 failures/errors/skips (322 before the backup guard test); `:desktopApp:build` up to date |
| `./scripts/init.sh --feature local_land_auto_backup` | `BUILD SUCCESSFUL` (runs the published `:shared:jvmTest :desktopApp:build` block) |
| `./scripts/init.sh --fast` | `Fast tier passed.` — "All 9 offline checks passed" (jvmTest, contract examples, backend pytest, source catalog, five evaluators) |
| `ANDROID_HOME=~/Library/Android/sdk ./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug` | `BUILD SUCCESSFUL`; 296 Android host tests, 0 failures/errors/skips, including `AndroidLandStorageTest` (2) and `LandAutomaticBackupTest` (12); debug APK built |
| `./gradlew :shared:verifyDesktopScreenshots` | `BUILD SUCCESSFUL`; 38 captures passed (34 before the four new recovery captures) |
| `ANDROID_HOME=~/Library/Android/sdk ./gradlew :shared:verifyAndroidScreenshots` | `BUILD SUCCESSFUL`; 34 captures passed (30 before the four new recovery captures) |
| `AndroidBackupExclusionGuardTest` negative control | Removing `android:dataExtractionRules` from the manifest made `:shared:jvmTest --tests …AndroidBackupExclusionGuardTest` `FAILED`; restoring it made the same command `BUILD SUCCESSFUL`. The `jvmTest` task re-ran on the manifest edit because the file is now a declared input. |
| Packaged APK inspection (`aapt2 dump`, see “Packaged APK backup-exclusion proof” below) | The APK manifest carries both attributes and the packaged rule resources exclude `sharedpref/manijero_lands.xml` in all three sections |

New and updated tests:

- `shared/src/jvmTest/.../platform/AndroidBackupExclusionGuardTest.kt` (1): fails if the Android
  manifest stops referencing either backup rule file, if a rule file stops excluding the land
  preferences file, or if a rule file starts including it. The excluded file name comes from
  `AndroidLandStorage`'s `getSharedPreferences("manijero_lands", …)` call.
- `LandListScreenshotsTest` / `LandListAndroidScreenshotsTest` (+4 each): the recovered-store callout
  in light and dark at 900×1200 and 360×800 (see the goldens bullet above).
- `shared/src/commonTest/.../LandAutomaticBackupTest.kt` (12): one bounded copy after each
  create/edit/remove/restore/permanent-delete, no copy when the primary write is refused, a refused
  copy never fails a saved land, damaged-primary recovery from the newest fully valid copy reported
  once, a copy with an undecodable record rejected whole, unreadable/truncated primary failing the
  read instead of opening empty, permanent deletion purging the primary and every copy, marker
  written before the primary, an unsanitizable copy still unable to resurrect a purged land, a
  refused permanent delete keeping the durable marker, and purge-marker escaping.
- `shared/src/jvmTest/.../LocalLandBackupDesktopStoreTest.kt` (3): damaged file recovered on restart
  with the rebuilt primary and dropped damaged copy, retention bounded at three copies that follow the
  primary, and permanent deletion purging every file on disk.
- `shared/src/androidHostTest/.../AndroidLandStorageTest.kt` (2): private-preferences rotation /
  replacement / purge marker, and repository recovery of a damaged primary value via Robolectric.
- `shared/src/jvmTest/.../LandScreenInteractionTest.kt` (+1): the recovery callout shows its Spanish
  title and body and only its `Entendido` action dismisses it.
- `LandStoreFormatTest`, `RecoverRemovedLandsDesktopStoreTest`, `RemoveLandDesktopStoreTest`,
  `AddLandDesktopStoreTest`, `EditLandDesktopStoreTest`: updated for the nullable strict-ish decoder
  and for the copy files that now live next to the Desktop store. One assertion was deliberately
  weakened, and this appendix states it instead of claiming otherwise: `RemoveLandDesktopStoreTest`
  no longer asserts the exact directory shape (`== listOf("lands-v1.txt")`); it now asserts only
  that no `.tmp` file survives the write, because sibling copy files legitimately sit next to the
  primary file. The stronger shape check moved to `RecoverRemovedLandsDesktopStoreTest`, which
  whitelists the primary file and its siblings (`lands-v1.txt` or `lands-v1.txt.*`) and separately
  forbids any `.tmp` file. The old exact-shape coverage therefore still exists in the suite, but no
  longer in the test that exercises the remove flow. Other assertions are unchanged.

### Packaged APK backup-exclusion proof

Checked against the debug APK produced by `:androidApp:assembleDebug`, using `aapt2` 37.0.0 from
`~/Library/Android/sdk/build-tools/37.0.0/aapt2`:

```sh
AAPT2=~/Library/Android/sdk/build-tools/37.0.0/aapt2
APK=androidApp/build/outputs/apk/debug/androidApp-debug.apk
unzip -l "$APK" | grep res/xml
"$AAPT2" dump xmltree --file AndroidManifest.xml "$APK"
"$AAPT2" dump resources "$APK" | grep -A3 -E 'xml/(backup_rules|data_extraction_rules)'
"$AAPT2" dump xmltree --file res/xml/backup_rules.xml "$APK"
"$AAPT2" dump xmltree --file res/xml/data_extraction_rules.xml "$APK"
```

Relevant output:

```text
      312  01-01-1981 01:01   res/xml/backup_rules.xml
      576  01-01-1981 01:01   res/xml/data_extraction_rules.xml

E: application (line=27)
  A: http://schemas.android.com/apk/res/android:allowBackup(0x01010280)=true
  A: http://schemas.android.com/apk/res/android:fullBackupContent(0x010104eb)=@0x7f0c0000
  A: http://schemas.android.com/apk/res/android:dataExtractionRules(0x0101063e)=@0x7f0c0001

resource 0x7f0c0000 xml/backup_rules
  () (file) res/xml/backup_rules.xml type=XML
resource 0x7f0c0001 xml/data_extraction_rules
  () (file) res/xml/data_extraction_rules.xml type=XML

E: full-backup-content (line=8)
    E: exclude (line=11)
      A: domain="sharedpref" (Raw: "sharedpref")
      A: path="manijero_lands.xml" (Raw: "manijero_lands.xml")

E: data-extraction-rules (line=8)
    E: cloud-backup (line=9)
        E: exclude (line=12)
          A: domain="sharedpref" (Raw: "sharedpref")
          A: path="manijero_lands.xml" (Raw: "manijero_lands.xml")
    E: device-transfer (line=14)
        E: exclude (line=17)
          A: domain="sharedpref" (Raw: "sharedpref")
          A: path="manijero_lands.xml" (Raw: "manijero_lands.xml")
```

So the packaged manifest carries both attributes, the two resource ids resolve exactly to the two
rule files, and both packaged binaries still contain the `sharedpref`/`manijero_lands.xml` exclusion
in every section. This proves the artifact *declares* the exclusion; it is not a device backup
round-trip.

### Synthetic store before/after recovery

Fixture: create `Uno` (land-0), `Dos` (land-1), `Tres` (land-2). Copies after the third write are
`[ABC, AB, A]`. The newest copy is damaged in place and the primary value is replaced by a non-store
string. Reopening the repository returns `[land-0 Uno, land-1 Dos]` (the newest fully valid copy),
writes that aggregate back as the primary value, drops the damaged copy, and reports
`RESTORED_FROM_AUTOMATIC_COPY` exactly once. With no valid copy the read throws
`LandStoreUnreadableException`, and the app shows the existing failed-read notice with `Reintentar`;
it never shows an empty list as if the lands had never existed.

### No network path and no OS backup destination

**Network/storage audit (what was actually inspected).** `LandSnapshotStorage`, `LandRepository`,
`AndroidLandStorage`, and `FileLandStorage` were read in full. They use only `SharedPreferences`
(`MODE_PRIVATE`, file `manijero_lands.xml`) and `java.nio.file` inside the app's own data directory
(`~/.manijero/lands-v1.txt` plus its sibling `.snapshot-1..3` and `.purge` files). No HTTP client,
account, `BackupAgent`, iCloud, or `Files`/`java.nio` path outside that directory is referenced by
those classes; the only network code in `shared` remains the answer-service client.

**Android OS backup (repaired after the validator's `revise`).** The earlier version of this
paragraph claimed there was no `android:allowBackup` reference, but it had only grepped the storage
adapters and never read the Android host manifest. `androidApp/src/main/AndroidManifest.xml` did
declare `android:allowBackup="true"` with no `android:fullBackupContent` and no
`android:dataExtractionRules`, so Auto Backup / device-to-device transfer could include
`shared_prefs/manijero_lands.xml` (primary aggregate, `land_store_snapshot_1..3`,
`land_store_purge`) and the privacy sentence "no hay copia en internet ni en otro aparato" was
false. What was checked after the fix, and how:

- Manifest attributes, read from the file and from the packaged APK:
  `android:allowBackup="true"`, `android:fullBackupContent="@xml/backup_rules"`, and
  `android:dataExtractionRules="@xml/data_extraction_rules"` (see “Packaged APK
  backup-exclusion proof” above for the APK commands and output).
- Rule files: `androidApp/src/main/res/xml/backup_rules.xml` is a `<full-backup-content>` document
  with `<exclude domain="sharedpref" path="manijero_lands.xml"/>`;
  `androidApp/src/main/res/xml/data_extraction_rules.xml` has that same exclude inside both
  `<cloud-backup>` and `<device-transfer>`. The excluded file name is derived from
  `AndroidLandStorage`'s `getSharedPreferences("manijero_lands", …)` call by
  `AndroidBackupExclusionGuardTest`, so renaming the preferences file fails the guard instead of
  opening a gap.
- SharedPreferences / `java.nio` audit as described above: `manijero_lands` is the only
  `getSharedPreferences` name in the repository, so excluding that one file covers every land value
  the app writes on Android.

Residual limitation, stated plainly: this is a declarative platform configuration checked by
manifest/resource inspection (source files plus the built APK's binary manifest and packaged rule
resources). No emulator or device `adb`/Auto Backup extraction round-trip was run, so the checks
prove the app *asks* the OS to exclude the data, not that a specific OEM backup agent honours it.
OS-level copies the app does not configure — macOS Time Machine or a whole-device/disk backup of
the Desktop data directory, Android OEM device clones at the storage layer, or a rooted/forensic
extraction — remain outside app control and are not covered by that promise.

### Not verified / open

- No device, accessibility, or screen-reader evidence for the recovery notice; only a Desktop Compose
  interaction test and the host-rendered light/dark goldens at 900×1200 and 360×800 exist. The owner
  should review the 16 affected PNGs before commit: the 8 re-recorded privacy captures and the 8 new
  `land_list_recovery_*` captures (this implementer inspected them; the owner has not).
- **Required follow-up for the `land_data_disclosure` spec owner (not edited here).**
  `docs/specs/land_data_disclosure.md` still quotes the *previous* strings in its "ship verbatim"
  block. The stale keys are `privacy_local_body_3` and `privacy_promise_body_1`. The shipped
  `shared/src/commonMain/composeResources/values/strings.xml` now says
  `privacy_local_body_3` = "No se copian solos a internet. La app guarda varias copias automáticas en
  este mismo dispositivo, pero no en otro sitio: si pierdes el dispositivo o borras la app, podrías
  perderlas." and `privacy_promise_body_1` = "Las copias automáticas no protegen si pierdes el
  dispositivo o borras la app: no hay copia en internet ni en otro aparato.", while that spec's quote
  block still shows the pre-`local_land_auto_backup` wording. This feature must not modify another
  feature's spec, so the discrepancy is recorded here and the owning spec must be updated (and
  re-accepted if its quote block is part of its contract). Until then the shipped screen and
  `strings.xml` are the current truth.
- The OS-backup exclusion is verified by manifest, rule-file, and packaged-APK inspection only. No
  emulator/device Auto Backup or device-transfer round-trip was executed, so OEM backup-agent
  behaviour, and copies made outside the app by the OS or a disk-backup tool, are unverified.
- `AndroidBackupExclusionGuardTest` reads checked-in files; `shared/build.gradle.kts` declares the
  manifest and `res/xml` as `jvmTest` inputs so a local edit re-runs it, but any run that skips
  `:shared:jvmTest` (for example a build-only check) does not execute the guard.
- `removedAt` still stores 0 in production (no clock is injected); unchanged by this feature.
- An automatic copy that the device refuses to write is not surfaced to the person; the save still
  succeeds and the next successful write rotates a fresh copy. This is intentional but has no UI
  evidence.

### Acceptance (orchestrator, 2026-10-27)

Independent validation returned `revise` once — Android OS backup contradicted the shipped privacy
promise, the evidence overstated what had been checked, the `PROGRESS.md` summary was stale, the moved
directory-shape assertion was not explained, the recovery notice had no golden, and a stray session log
sat untracked — and then `accept` after the repair. The validator re-ran the focused block, the fast
tier, the Android host tests plus `assembleDebug`, both screenshot verifications, and its own `aapt2`
inspection of the packaged APK, reproducing 323 shared tests, 296 Android host tests, and 38 Desktop /
34 Android captures. Acceptance record:
[`local_land_auto_backup.md`](../../validations/local_land_auto_backup.md).

## Validator checklist

- [x] Snapshots are written only after successful primary writes.
- [x] Recovery never silently turns corruption into an empty store.
- [x] Retention is bounded and permanent deletion purges all app-managed copies.
- [x] User-facing copy does not claim protection from device loss.
- [x] The Android manifest keeps the land preferences out of OS cloud backup and device transfer
      (both rule files exclude `sharedpref/manijero_lands.xml`), or sets `android:allowBackup="false"`.
- [x] Progress and feature status change only after verification/acceptance.
