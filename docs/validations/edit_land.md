# Validation: `edit_land` — accept

- **Feature:** `edit_land` (`area: lands`) — "Edit a land".
- **Spec:** `docs/specs/edit_land.md`.
- **Status at validation:** `passing` (implementer self-verified); this record is the independent
  validator's acceptance.
- **Verdict:** **accept** (2026-10-13).

## What was validated

The feature-list verification literally: *edit one of two saved lands and confirm the other record
remains unchanged*, together with the repository semantics the spec relies on (one targeted record,
preserved unknown attributes, cleared optional field, deliberate `UNKNOWN`), scope discipline, and
copy fidelity.

## Checks the validator re-ran

| Check | Result |
|---|---|
| `./init.sh` | exit 0 |
| Focused `:shared:jvmTest --tests EditLandStateTest/EditLandRepositoryTest/EditLandDesktopStoreTest --rerun-tasks` | BUILD SUCCESSFUL, 20/0 (12 + 6 + 2) |
| `:shared:jvmTest --rerun-tasks` | BUILD SUCCESSFUL, 98 tests / 14 classes / 0 failures |
| `:shared:testAndroidHostTest --rerun-tasks` | BUILD SUCCESSFUL, 87 tests / 11 classes / 0 failures |
| `./init.sh --verify` | exit 0 |
| `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build --rerun-tasks` | BUILD SUCCESSFUL, 91 tasks executed, 0 from cache; APK regenerated |
| Accepted `add_land`/`land_list` suites | `AddLandStateTest` 11, `LandListStateTest` 6, `LandRepositoryTest` 4, `AddLandDesktopStoreTest` 1 — all 0 failures |
| Eight new Spanish strings vs the spec's XML block | byte-for-byte equal, each appearing exactly once; `strings.xml` diff is additions only |
| `CONSTRAINTS.md` "Land editing" MUST rule vs the spec | byte-equal (whitespace-normalized) |
| Privacy | `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out" shared/src` → no matches; no raw colors/network in the new/changed product files |
| Single write site | exactly one production `repository.update(...)` (`App.kt:200`); no `create`/`delete` on any edit path |

## Independent reproduction (not the implementer's tests)

The validator wrote and then deleted a temporary scratch JVM test against the **real
`FileLandStorage`** (4/4 pass), then confirmed `git status` was back to the pre-validation set.

- **Literal verification, byte level.** Two lands saved; only the first edited via
  `toEditLandState() → reduce → toDraftOrNull() → update`. Raw snapshot before/after: the
  `land-store-v1` header + 2 lines, the **other record's serialized line byte-identical**, order
  preserved, the edited line the only one changed, no third record; the edited record keeps its `id`
  and `createdAtEpochMillis` and takes the new name/`updatedAt`.
- **Unknown id (`LAND_MISSING`)** → `update` returns `null`, file bytes identical, zero bytes
  rewritten, list unchanged.
- **Blank/whitespace name** (`""`, `" "`, `"\t\n"`) → `showNameError = true`,
  `toDraftOrNull() == null` (the app skips the write entirely), file bytes unchanged, other edited
  values retained.
- **Emptied municipality** → reopens as absent (`null`), not empty text; **known → `UNKNOWN` reset**
  round-trips as `UNKNOWN`; `areaHectares`/`notes` carried through a name-only edit and read back
  intact.
- **App wiring** read line-by-line: no confirmation, no navigation, no land/exception text shown on
  either `LAND_MISSING`/`WRITE_FAILED` failure; `update` only in the `SaveClicked` branch, never at
  startup or on recomposition.
- **UI evidence corroborated.** Six of the implementer's emulator screenshots were viewed
  (two-land list with per-row `Editar`; prefilled `Editar terreno`; post-edit list with the updated
  confirmation and the other land intact; the other land with its municipality cleared and both
  choices `No lo sé`; blank-name error with no navigation; 2× font scale wrapping without horizontal
  overflow). The Desktop `:desktopApp:run` log matched the claim (no app exception, expected exit 143
  from SIGTERM).

## Scope and non-regression

- **Scope discipline: clean.** Modified: `CONSTRAINTS.md`, `PROGRESS.md`, `feature_list.json`,
  `strings.xml`, `App.kt`, `AddLandScreen.kt` (visibility only, 2 lines), `LandListScreen.kt`. New:
  `EditLandState.kt`, `EditLandScreen.kt`, 3 test files, the spec. `Land.kt`, `LandRepository.kt`,
  the storage adapters and `land-store-v1`, `AddLandState.kt`, `LandListState.kt`, entry points,
  Gradle/version catalog, `init.sh`, `theme/`, and `backend/contracts/knowledge` untouched — no new
  module, dependency, ViewModel, coroutine, navigation framework, network call, permission, or
  logging.
- **Cross-feature:** rows stay non-clickable (no `onClick` on the row `Surface`), details stay one
  merged node, `Editar` is a labelled per-row button whose content-description is
  `land_list_edit_description` with the exact saved name (never body text), `ADDED` still renders
  `add_land_saved` byte-for-byte, and `ChoiceGroup`/`ChoiceItem` were widened `private`→`internal`
  with no other change.
- **Security review (feature-scoped): no relevant issues.** Local-only file/SharedPreferences writes,
  no network, no new input surface, no data or exception echoed or logged, no auth/access-control
  surface touched.

## Findings (all non-blocking)

1. **F1 — low, docs accuracy.** `PROGRESS.md` ended with an extra blank line, so `git diff --check`
   exited 2 while the evidence claimed it clean. *Fixed* by trimming the trailing blank line before
   the acceptance commit.
2. **F2 — low, spec-vs-code deviation.** The spec said both edit exits (successful save **and**
   `Cancelar`) re-read through `readLands()`; `App.kt` `onCancel` does not, matching the accepted
   `add_land` cancel path. *Amended the spec* to describe the implemented (and accepted) behavior;
   no acceptance scenario depended on it.
3. **F3 — informational.** The `App()` save-decision wiring has no automated coverage (no Compose
   UI-test framework exists); it is covered by inspection plus the emulator smoke, as the spec's
   honest-gap section states.
4. **F4 — informational.** `LAND_MISSING` is unreachable in normal use (needs the record to vanish
   between the list read and the save); unit-level only, correctly not claimed as an emulator
   reproduction.
5. **F5 — informational.** `updatedAtEpochMillis` is still not meaningful (`update` receives no
   timestamp; no clock dependency exists) — carried `land_list` finding F6, correctly recorded.
6. **F6 — informational (evidence provenance).** The interactive Android smoke is implementer-produced;
   the artifacts and code semantics were corroborated, but the emulator was not re-driven (no device
   attached). Nothing depends on that alone — the semantics are reproduced by the JVM/file-store
   probes and the focused suites.

## Accepted changes at commit time

- Persisted acceptance: `feature_list.json` `edit_land` → `accepted` with the validator evidence;
  `PROGRESS.md` current-state/session-log/feature section updated to `accepted`.
- F1 cleanup in `PROGRESS.md`; F2 spec sentence amended in `docs/specs/edit_land.md`.
