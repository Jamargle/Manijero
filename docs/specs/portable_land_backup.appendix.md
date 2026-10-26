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

## Validator checklist

- [ ] Android and Desktop read the same portable format.
- [ ] Restore previews then replaces only after confirmation; invalid input never mutates local data.
- [ ] Export includes active and removed lands but excludes chat/service data and device identifiers.
- [ ] Copy says plainly that exported files are unencrypted and outside app deletion control.
- [ ] No cloud/account behavior was added.
