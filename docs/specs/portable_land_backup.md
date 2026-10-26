# Feature Spec: `portable_land_backup`

## Source metadata

- **Feature:** `portable_land_backup` — Export and restore lands across Android and Desktop (`lands`).
- **Status at planning:** `not_started`; depends on `local_land_store`, `recover_removed_lands`, and `local_land_auto_backup`.
- **Source behavior:** A user can save a plain, portable backup file and restore it on Android or macOS Desktop.
- **Feature-list verification:** Export/import round trips preserve active and removed data; invalid files do not mutate the store; restore preview precedes replace-all confirmation.
- **Feature-list note:** The file is unencrypted by product choice and requires a plain-Spanish privacy warning. The user controls its location and copies.

## Goal and boundaries

Give users a manual recovery path that can survive device loss without account or cloud sync. The file uses a versioned, validated format shared by Android and Desktop, and contains both active and removed lands so recovery state is preserved.

**In scope:** export through the platform file picker; import/restore through the file picker; preview counts and names before restore; explicit confirmation to replace all current active and removed lands; schema and integrity validation; warning that the plain file contains private land details.

**Non-goals:** encryption/passphrases, automatic cloud storage, merge semantics, account-based transfer, or deleting copies the user already exported.

## Job story

When I change device or want a copy somewhere I control, I want to export and later restore my lands from one portable file, so I can move them without an account or cloud sync.

## Acceptance scenarios

### Export

Given active and removed lands exist, when the user exports, then one portable file contains both lists, preserves all supported values and order, and the UI warns that the file is unencrypted and contains private land information.

### Preview and replace

Given a valid backup file, when the user selects it, then the app previews the number of active and removed lands and requires explicit confirmation before replacing all existing active and removed data.

### Invalid or unsupported file

Given a malformed, unsupported-version, truncated, or internally inconsistent file, when import is attempted, then the app explains the problem and makes no store or automatic-backup change.

### Cross-platform portability

Given a file exported by Android, when macOS Desktop imports it (and vice versa), then supported fields round-trip unchanged, including user-entered notes and removal state.

### Exported copies remain user-controlled

Given a land was permanently deleted from the app, when an older exported file is later imported, then the preview explains that the file can reintroduce its old contents; the app does not claim it can erase external copies.

## Technical approach

Define a strict versioned portable schema separate from the private platform store. Validate the complete file before showing preview or writing. Use Android document picker and JVM/Desktop file selection adapters while keeping schema, mapping, and preview state in `commonMain` where platform-neutral. Restore replaces both lists as one validated transaction and creates a current local snapshot first. Keep the file plaintext as chosen; do not include chat history, request logs, device identifiers, or service data.

## Expected file changes

- Shared backup schema/model, mapper, validation, restore/export state, screens, and resources.
- Android and JVM platform file-picker adapters and focused tests for both hosts.
- `docs/domain-model.md`, `DESIGN.md` only if UI guidance changes, and `docs/risks-and-open-questions.md`.

## Visual design impact

Add export/import controls and a restore preview/confirmation. Follow `DESIGN.md`; label replace-all clearly and provide keyboard/screen-reader accessible file and error states. No generated concept is needed.

## Durable documentation impact

- `ARCHITECTURE.md`: update platform integration boundary for file pickers and portable backup format.
- `CONSTRAINTS.md`: state plaintext/user-controlled semantics and replace-all restore behavior.
- `AGENTS.md`: not needed.
- `README.md` and the privacy notice: document user responsibility for exported copies.

## Focused verification

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :desktopApp:build
```
<!-- verify:end -->

## Appendix

See [`portable_land_backup.appendix.md`](portable_land_backup.appendix.md).
