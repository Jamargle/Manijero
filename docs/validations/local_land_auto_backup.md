# `local_land_auto_backup` acceptance

## Verdict

**Accepted** on 2026-10-27, after one `revise` round and independent re-validation.

## Independent verification

- `./gradlew :shared:jvmTest :desktopApp:build` — passed; `:shared:jvmTest` **323 tests, 0 failures,
  0 errors, 0 skipped** across 36 classes, including `AndroidBackupExclusionGuardTest`,
  `LandAutomaticBackupTest` (12), and `LocalLandBackupDesktopStoreTest` (3).
- `./scripts/init.sh --feature local_land_auto_backup` — passed; the published focused block is the
  real `:shared:jvmTest :desktopApp:build` command.
- `./scripts/init.sh --fast` — passed; "All 9 offline checks passed". The fast tier runs
  `:shared:jvmTest`, so the backup-exclusion guard is inside it.
- `ANDROID_HOME=~/Library/Android/sdk ./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug`
  — passed; 296 Android host tests, 0 failures, and a debug APK.
- `./gradlew :shared:verifyDesktopScreenshots` — passed, 38 captures, including the four new
  `land_list_recovery_*` frames. `:shared:verifyAndroidScreenshots` — passed, 34 captures.
- Packaged APK inspection with `aapt2` 37.0.0: the binary manifest carries `allowBackup="true"`,
  `fullBackupContent="@xml/backup_rules"`, `dataExtractionRules="@xml/data_extraction_rules"`; both
  resource ids resolve to the packaged rule files; both packaged binaries exclude
  `domain="sharedpref" path="manijero_lands.xml"` in `full-backup-content`, `cloud-backup`, and
  `device-transfer`.
- Guard negative controls (temporarily applied and byte-restored by the validator): removing
  `android:dataExtractionRules` failed `AndroidBackupExclusionGuardTest`; removing the `cloud-backup`
  `<exclude>` failed it too; restoring the files returned `:shared:jvmTest` to 323/0.
- Reviewed the write gate (one copy only after a successful primary write; a refused copy never turns
  a completed save into a reported failure), the strict decode (`requireEveryRecord`, header and
  section markers required, `null` instead of an empty aggregate), newest-fully-valid recovery
  reported once via `consumeRecovery()`, `LandStoreUnreadableException` instead of a silent empty
  store, and the permanent-delete order (marker, primary, every retained copy, marker cleared last,
  every read filtering marked ids).
- Scope discipline: no new network, cloud, account, or sync path; no dependency added; snapshot and
  purge logic not relaxed; only `local_land_auto_backup` changed in `feature_list.json`; no other
  feature's spec or status was modified, and nothing was staged during validation.

## Accepted scope and limitations

Automatic same-device copies are implemented: up to three whole-aggregate snapshots are rotated after
each successful land change, a damaged primary is rebuilt from the newest fully valid copy with a
plain Spanish `He recuperado tus terrenos` / `Entendido` notice, an unreadable store with no valid copy
fails loudly instead of opening empty, and permanent deletion purges the land from the primary and
every retained copy. Android keeps the copies in the same private preferences file and now excludes
that file from Auto Backup and device transfer; Desktop keeps sibling `.snapshot-1..3` and `.purge`
files next to the store.

Honest limits:

1. The OS-backup exclusion is proven by source-manifest, rule-file, and packaged-APK inspection only.
   No emulator or device Auto Backup or device-to-device round-trip was run, so OEM backup-agent
   behaviour is unverified. Copies made outside the app (macOS Time Machine, disk images, OEM clones
   or forensic extraction) are outside app control.
2. `AndroidBackupExclusionGuardTest` runs only where `:shared:jvmTest` runs; a build-only or
   Android-only check skips it. Anything that adds a second land-bearing preferences or file location
   must extend the rules in the same change.
3. The recovery notice has a Desktop Compose interaction test and host-rendered light/dark goldens at
   900×1200 and 360×800 dp, but no device, screen-reader, or 2× text evidence. Owner review of the 16
   affected PNGs (8 re-recorded privacy, 8 new recovery) is still outstanding.
4. A refused automatic copy is silent by design (the save succeeds and the next write rotates a fresh
   copy) and has no UI evidence. `removedAt` still stores 0 because no clock is injected. A damaged
   copy is discarded rather than repaired.
5. The copies live in the same app data area as the primary, so losing the device or uninstalling the
   app still loses every record. This record does not claim device-loss protection.
6. The stale "ship verbatim" quote block in `docs/specs/land_data_disclosure.md` (keys
   `privacy_local_body_3`, `privacy_promise_body_1`) is a follow-up for that spec's owner; it was
   deliberately not edited because it belongs to another feature. The shipped screen and
   `strings.xml` are the current truth until that spec is updated.
7. `docs/validations/recover_removed_lands.md` still says no automatic snapshot exists; it is a
   point-in-time acceptance record, superseded on that point by this record and left historical.
8. `docs/risks-and-open-questions.md` and `PROGRESS.md` describe the accepted state; the portable
   plaintext backup/restore feature remains unimplemented and still blocks the pilot.

See [`local_land_auto_backup.appendix.md`](../specs/local_land_auto_backup.appendix.md) for the full
evidence, the retention policy, the APK inspection transcript, and the repair history.
