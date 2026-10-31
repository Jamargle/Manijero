# `recover_removed_lands` acceptance

## Verdict

**Accepted** on 2026-10-27.

## Independent verification

- `./scripts/init.sh --feature recover_removed_lands` — passed; `:shared:jvmTest` and `:desktopApp:build` succeeded.
- A forced `./gradlew :shared:jvmTest --rerun-tasks` re-ran **304 tests in 33 suites: 0 failures,
  0 errors, 0 skipped**. Focused classes were green: `LandMigrationTest` 5/5,
  `LandLifecycleRepositoryTest` 8/8, `LandStoreFormatTest` 10/10, `RemovedLandsStateTest` 10/10,
  `LandScreenInteractionTest` 5/5, `RecoverRemovedLandsDesktopStoreTest` 2/2, `AppNavigationTest` 20/20.
- `./scripts/init.sh --fast` — all nine offline checks passed.
- `./scripts/init.sh --verify` — passed; `:shared:testAndroidHostTest` re-ran **280 tests, 0 failures**
  across 26 suites, and the Android debug APK plus Desktop build succeeded.
- Reviewed the v1-to-v2 migration (one write, every decodable record retained as active, refused
  migration write leaves the v1 bytes intact, restart does not re-migrate), the lifecycle outcomes
  (`Done`/`Missing`/`StorageFailed`), active-only `list()`/`landContextFor`, the separate permanent
  deletion confirmation naming the land, and the Desktop temp-file plus atomic replacement.
- Confirmed the fix for the two review findings: `CONSTRAINTS.md` and the `LandContextBuilder` KDoc
  now say **active** stored land and forbid removed records in any answer request; `DESIGN.md`
  documents the new detail route and the bars-hidden confirmation with their back routes.
- Scope discipline: no commit existed during validation, only this feature's status changed in
  `feature_list.json`, and `PROGRESS.md`, `docs/validations/`, `docs/progress/`, and other features'
  specs and statuses were untouched.

## Accepted scope and limitations

Removal is now recoverable: a confirmed active land moves to a local removed list, `Terrenos
eliminados` offers `Restaurar` and `Borrar para siempre`, and permanent deletion requires its own
confirmation naming the land. The store is the `land-store-v2` aggregate with a one-time
`land-store-v1` migration; `list()` stays active-only, so removed records never enter land context,
clarification, or an answer request. No automatic expiry or bulk action exists.

Honest limits: no Android device/emulator or TalkBack run, so accessibility is code-level and
preview-based; the screenshot suite has no goldens for the two new screens, and the existing land-list
golden still renders old `Eliminar` under the 0.1% threshold, so passing screenshots are not evidence
for the new copy; the Android `SharedPreferences` path is not instrumented; `removedAt` is stored as
0 in production because no clock is injected (same gap as `createdAt`/`updatedAt`), and a storage
read failure during a transition throws while the UI catches it and reports failure; the Desktop
atomic replacement does not fsync, and a downgrade to a v1-only app would read a v2 store as empty.
There is no backup, export, or automatic snapshot yet, so permanent deletion purges the only local
copy.

The accepted records `docs/specs/remove_land.md` and its appendices, `desktop_mvp_build`,
`land_measurement_fields`, `land_setup_fields_decision`, `minimal_land_context`, and
`chat_question_submission` still describe the pre-lifecycle `land-store-v1`/irreversible-removal
state. They are historical acceptance records, were intentionally not rewritten in this feature's
diff, and are superseded by this record and the current `README.md`, `docs/domain-model.md`,
`CONSTRAINTS.md`, and `LandStoreFormat` KDoc. The `land_measurement_fields` static grep gate that
expects `land-store-v1` inside `LandRepository.kt` no longer describes the current format and must not
be treated as migration evidence.

See [`recover_removed_lands.appendix.md`](../archive/specs/recover_removed_lands.appendix.md) for exact
commands, per-test evidence, synthetic fixtures, and the remaining findings.
