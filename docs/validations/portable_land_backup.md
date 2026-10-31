# `portable_land_backup` acceptance

## Verdict

**Accepted** on 2026-10-31, by independent validation, with no revise round.

## Independent verification

- `./scripts/init.sh --feature portable_land_backup` — passed (exit 0); the published focused block
  is the real `:shared:jvmTest :desktopApp:build` command.
- `CI=true ./scripts/init.sh --fast` — passed (exit 0); "All 9 offline checks passed", including
  `backend-tests` (888 passed) under the worktree's Python 3.12 venv (`MANIJERO_PYTHON`).
- `CI=true ./scripts/init.sh --verify` — passed (exit 0); Android host tests, debug APK, and Desktop
  build succeeded.
- Forced `./gradlew :shared:jvmTest --rerun :shared:testAndroidHostTest --rerun` — passed;
  `:shared:jvmTest` **353 tests in 40 suites, 0 failures, 0 errors, 0 skipped**; Android host
  **325 tests in 31 suites, 0 failures**. On both hosts: `LandBackupFormatTest` 12/12 (including the
  pinned cross-platform fixture) and `LandBackupRestoreTest` 10/10. JVM only:
  `DesktopLandBackupFilesTest` 5/5 and `LandBackupFlowInteractionTest` 2/2. Android host only:
  `AndroidLandBackupFilesTest` 6/6.
- `./gradlew :shared:verifyScreenshots` — passed. The four re-recorded `privacy_light`/`privacy_dark`
  goldens (Desktop and Android host, 900×1600) were inspected: only the "Lo que no puedo prometer"
  card changed, now naming exported files as unencrypted, user-placed, and undeletable by the app;
  nothing is clipped, and dark contrast is intact.
- `git diff --check` — clean.
- Reviewed:
  - the strict whole-file validation before any preview or repository call: 4 MiB cap, format
    marker, integer version, strict keys, FNV-1a 64 checksum of the canonical `lands`, record
    rules, and ids unique across both lists;
  - `LandRepository.replaceAll`: reads the current store first and refuses to overwrite an
    unreadable one; completes a pending purge that overlaps the backup; writes a pre-restore copy,
    then one aggregate write; a refused write leaves the primary unchanged;
  - confirmation-only restore in `LandBackupController`, with no double tap;
  - SAF `CreateDocument`/`OpenDocument` with no permission or persistent access, and the Desktop
    `FileDialog` with temp-file-plus-move;
  - no network, account, logging, or non-land data in the file.
- Scope discipline: only `portable_land_backup` changed in `feature_list.json`; no other feature's
  spec or status was modified; nothing was staged or committed during validation.

## Accepted scope and limitations

`Mis terrenos` → `Copia en un archivo` saves every active and removed land, in stored order, to one
plaintext JSON file (`manijero-land-backup`, version 1). It restores that file on Android or Desktop
after a preview of counts and names and an explicit `Sustituir todos mis terrenos`, replacing both
lists without merging. A same-device automatic copy of the previous state is kept first. Refused
files show a plain-Spanish reason and change nothing.

Honest limits:

1. No real-device SAF picker or real macOS `FileDialog` run, and no physical Android-to-Mac file
   transfer. Portability rests on the shared pinned fixture passing on the JVM and Android hosts.
2. Restore is refused while the current store cannot be read (no valid automatic copy), so a person
   with a damaged store and no copy cannot restore until that is resolved.
3. Import accepts some values the app's own forms would refuse: a name of only spaces, text with
   spaces at either end, a zone longer than 80 characters, a custom variety longer than 40, and
   control characters. Nothing is lost after a restore, but such a land may fail its edit form.
4. On Desktop, typing a name without `.json` saves to `<name>.json` and can overwrite an existing
   file of that name without a prompt. On Android, if the activity is recreated while the save
   picker is open, the created document stays empty. Neither changes the store.
5. The checksum detects damage, not tampering. The file is unencrypted by product choice; its
   safekeeping, copies, and deletion are the person's responsibility. An older file can bring back
   lands deleted later, as the preview says.
6. Copy names "un ordenador Mac" because Desktop distribution is scoped to macOS.
7. Accessibility is code-level (headings, polite live region for notices, merged name lists) plus
   the implementer's manual render review. There is no TalkBack/VoiceOver run, no golden for the
   backup screen, and no persistent E2E harness.
8. The validator noted that `DESIGN.md`'s list of detail routes and system-back targets did not name
   the `Copia en un archivo` route; the orchestrator added it on acceptance (bars visible, back →
   `Mis terrenos`, matching `navigationVisible` and the back map in `AppNavigation.kt`).

See [`portable_land_backup.appendix.md`](../archive/specs/portable_land_backup.appendix.md) for the full
evidence.
