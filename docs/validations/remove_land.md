# Validation: `remove_land` — accept

- **Feature:** `remove_land` (`area: lands`) — "Remove a land".
- **Spec:** `docs/specs/remove_land.md`.
- **Status at validation:** `passing` (implementer self-verified); this record is the independent
  validator's acceptance.
- **Verdict:** **accept** (2026-10-13).

## What was validated

The feature-list verification literally: *remove one of two lands and confirm only that land is
absent from future lists and requests*, together with the removal semantics the spec relies on
(exactly one targeted record, every other record unchanged, cancel writes nothing, the last land
leaving a valid empty store), scope discipline, copy fidelity, and the destructive-action safety
rules.

## Checks the validator re-ran

| Check | Result |
|---|---|
| `git status --porcelain` / `git diff --stat` | exactly the 6 modified + 6 new expected files; no stray edits (`Land.kt`, `LandRepository.kt`, adapters, `land-store-v1`, `LandListState.kt`, add/edit state/screens, entry points, Gradle, `init.sh`, `theme/` untouched) |
| `git diff --check` | clean |
| `./init.sh` | exit 0; still runs the real `--verify` gate |
| Focused `:shared:jvmTest --tests …RemoveLand* --rerun-tasks` | BUILD SUCCESSFUL, 15/0 (State 8, Repository 5, DesktopStore 2); the first run was `FROM-CACHE`, so `--rerun-tasks` was forced |
| `:shared:jvmTest --rerun-tasks` | BUILD SUCCESSFUL, 117 tests / 17 suites / 0 failures (all accepted land suites green) |
| `:shared:testAndroidHostTest --rerun-tasks` | BUILD SUCCESSFUL, 104 tests / 13 suites / 0 failures |
| `:shared:compileKotlinIosSimulatorArm64 --rerun-tasks` | BUILD SUCCESSFUL (11 tasks executed) |
| `./init.sh --verify` | BUILD SUCCESSFUL (91 tasks); `androidApp-debug.apk` (35.8 MB) and `desktopApp.jar` produced |
| Eight new Spanish strings vs the spec's XML block | byte-for-byte equal, each appearing exactly once; `add_land_saved`/`edit_land_saved`/`land_list_edit` unchanged (diff is additions only) |
| Privacy | `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out"` → no matches; no `uses-permission` in any source manifest; the merged debug manifest declares no `INTERNET`; no `Color(0x` outside `theme/`; no new dependency (empty Gradle diff) |
| `CONSTRAINTS.md` "Land removal" MUST rule vs the spec | matches the spec's suggested text |

## Independent reproduction (not the implementer's tests)

The validator wrote and then deleted its own scratch JVM probe against the **real
`FileLandStorage`** (temp dir; 4/4 pass), then confirmed `git status` was back to the pre-validation
set.

- **Literal verification, byte level.** Two lands saved; one removed via
  `toRemoveLandState() → reduce → delete`. Raw snapshot before/after: the `land-store-v1` header plus
  the **surviving record's serialized line byte-identical**, the removed record absent, order
  preserved, no duplicate or resurrected record.
- **Second delete of an absent id** → `delete` returns `false` with a byte-identical snapshot
  (`LAND_MISSING`, never a claimed removal).
- **A throwing `write()`** surfaces as a failure and leaves the store untouched (`WRITE_FAILED`).
- **Last-land removal** leaves a header-only snapshot that reopens as an empty store.
- **Reducer branches** exercised directly.

The validator also independently re-drove an **Android emulator** (`Medium_Phone_API_35`,
1080×2400, fresh install + `pm clear`, headless via `uiautomator`/`input`, killed afterwards):

- Each row shows a visible `Editar` and `Eliminar`; the `Eliminar` accessibility description reads
  `Eliminar el terreno «Los Olivos»` / `«La Loma»` (exact saved name); row cards non-clickable.
- Opening `Eliminar` shows `Eliminar terreno` / `¿Seguro que quieres eliminar el terreno «Los
  Olivos»? No se puede deshacer.` plus detail lines, `Eliminar el terreno` and `Cancelar`.
- `Cancelar` returns to the list with both lands, no confirmation, and the store file
  **byte-identical** (diff clean) ⇒ opening *and* cancelling wrote nothing.
- Confirm removes exactly `Los Olivos`; the list shows only `La Loma` with every value intact and
  `El terreno se ha eliminado de este dispositivo.`; the surviving record's encoded line is
  byte-identical and the removed line is gone.
- **Force-stop + relaunch lists only `La Loma`** (the literal feature-list verification).
- Removing the last land leaves the valid header-only `land-store-v1` snapshot, shows the accepted
  empty state naming `Añadir terreno`, and a new land can still be saved.
- `font_scale 2.0` with a long name + long municipality: list and confirmation wrapped with max right
  edge 1017 / 1080, no clipping or horizontal overflow.

## Scope and non-regression

- **Scope discipline: clean.** Modified: `CONSTRAINTS.md`, `PROGRESS.md`, `feature_list.json`,
  `strings.xml`, `App.kt`, `LandListScreen.kt`. New: `RemoveLandState.kt`, `RemoveLandScreen.kt`,
  3 test files, the spec, and this record. `Land.kt`, `LandRepository.kt`, the storage adapters and
  `land-store-v1`, `LandListState.kt`, `AddLandState.kt`/`AddLandScreen.kt`,
  `EditLandState.kt`/`EditLandScreen.kt`, entry points, Gradle/version catalog, `init.sh`, `theme/`
  and `backend/contracts/knowledge` untouched — no new module, dependency, ViewModel, coroutine,
  dialog/snackbar, navigation framework, network call, permission, or logging.
- **Cross-feature:** rows stay non-clickable, details stay one merged node, `Eliminar` is a labelled
  per-row button whose content-description is `land_list_remove_description` with the exact saved
  name (never body text), `ADDED` still renders `add_land_saved` and `UPDATED` still renders
  `edit_land_saved` byte-for-byte, and the `internal LandDetails` extraction is
  visibility/behavior-neutral.
- **Security review (feature-scoped): no relevant issues.** The confirmation carries only
  `landId`, trimmed name, municipality, and the two enums — no id/area/notes rendered or logged
  (verified by the identity-fields data equality test and the on-device dump). No new egress: no new
  dependency, no `uses-permission`, no `INTERNET` in the merged manifest. `delete` is invoked exactly
  once, only inside the explicit-confirmation callback, targeting the state's own `landId`; the row
  trigger and `Cancelar` provably write nothing (byte-identical store proven on-device); a
  `false`/thrown result is never reported as a removal.

## Findings (all non-blocking)

1. **F1 — minor, spec-vs-code deviation.** The spec sketched `LandDetails(land)`; the implementation
   is `LandDetails(municipality, waterRegime, productionMethod)`. The rationale is sound and
   documented (the confirmation state carries no full `Land`, so building a fake one would fabricate
   id/timestamp data), and the extraction is visibility/behavior-neutral. Accepted as-is; the spec
   text is treated as superseded.
2. **F2 — minor, layout vs the spec sketch.** The sketch draws `[ Editar ] [ Eliminar ]` on one line;
   the implementation stacks two full-width secondary `TextButton`s, matching the accepted full-width
   `Editar` pattern and the sketch's own "full width" note. Rows are simply taller. Visual only.
3. **F3 — informational.** No automated coverage for the `App()` removal decision (no Compose
   UI-test harness exists). Disclosed by the implementer; the validator closed the happy/cancel/
   last-land paths with its own emulator run and the failure paths with its probe. A future
   accessibility-style feature should own durable UI coverage.
4. **F4 — informational.** Unreachable dead branch: if `AppDestination.RemoveLand` were reached with
   `landRepository == null`, `Eliminar el terreno` would silently no-op. The destination is
   unreachable without a repository (the `Mis terrenos` affordance is `null`), exactly like the
   accepted add/edit destinations.
5. **F5 — informational.** No `BackHandler`: system back on the confirmation exits the activity rather
   than returning to the list. Identical to the accepted add/edit screens (no `BackHandler` anywhere),
   so not a regression; a worthwhile future hardening item for low-confidence users. Backing out
   writes nothing.
6. **F6 — informational, carried.** `createdAtEpochMillis` is still the default `0` (no clock
   injected) — the carried `land_list` F6 finding, unchanged and disclosed.

## Accepted changes at commit time

- Persisted acceptance: `feature_list.json` `remove_land` → `accepted` with the validator evidence;
  `PROGRESS.md` current-state/session-log/feature section updated to `accepted`.
