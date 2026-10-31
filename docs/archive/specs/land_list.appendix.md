# Appendix — `land_list`

Planning and verification record for [`docs/specs/land_list.md`](../../specs/land_list.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/land_list.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `feature_list.json`: `land_list` depends on the three accepted features above; `edit_land`,
  `remove_land`, and `minimal_land_context` depend on `land_list`, so this feature must leave them
  untouched.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: a private `AppDestination { Chat,
  AddLand }` enum, `App(landRepository, answerService)` with a nullable injected repository, a
  `Mis terrenos` affordance that is disabled when there is no repository, and add-form wiring that
  returns to the chat home after success. No navigation library or `LandList` destination exists.
- `shared/.../lands/LandRepository.kt`: `list()` synchronously returns creation-ordered records
  (`create` appends) and calls `storage.read()`, an I/O boundary that can throw; malformed individual
  records are already skipped by `LandStoreFormat.decode`. `lands/Land.kt` already carries id, trimmed
  name, optional municipality, water regime, production method, optional area/notes, and timestamps, so
  no model change is needed.
- `shared/.../lands/AddLandState.kt` and `AddLandScreen.kt`: the accepted house pattern — a pure
  state/reducer file with no Compose or platform imports, a stateless `@Composable` screen with named
  callbacks, resource-backed copy, and previews for blank/error/long/compact/wide/large-font states.
- `shared/src/commonMain/composeResources/values/strings.xml`: one shared resource file that already
  holds the vocabulary to reuse (`add_land_unknown` = `No lo sé`, `add_land_water_*`,
  `add_land_production_*`, `add_land_saved`, `chat_home_lands` = `Mis terrenos`);
  `theme/ManijeroTheme` is already applied once in `App()`.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt`: already inject one `LandRepository`
  each, so no platform file changes; `commonTest/.../lands/LandRepositoryTest.kt` and
  `AddLandStateTest.kt` show the established `kotlin.test` + in-memory `LandStorage` fake pattern, and
  there is no Compose UI-test dependency or persistent E2E command.
- `DESIGN.md`: line 85 defines surface 4, "simple list with user-chosen names and a visible 'Añadir
  terreno' action … avoid map-first or spreadsheet-style layouts"; line 83 keeps `Mis terrenos` on the
  home; lines 70-78 require one primary action, visible back navigation, keyboard access with visible
  focus, and no color-only cues. `docs/archive/MasterPlanV3.md` line 942 also requires home access to `Mis terrenos`;
  `docs/domain-model.md` allows zero or more lands, requires a name that helps distinguish similar
  lands, keeps unknown a real state that must not become a default category, keeps data on device, and
  forbids logging land values.

The feature is correctly sized: one accepted model/repository, one read-only screen, one navigation hop.

## Implementation plan and tasks

1. Write `LandListStateTest` from the acceptance contract first: an empty successful load is the empty
   state; a failed load is not an empty state and discards previously loaded rows; a load keeps
   repository order, duplicate names, and identities; reload clears the previous failure;
   Unicode/long/emoji names survive verbatim. Then implement the pure state file.
2. Build `LandListScreen` with resource-backed copy, the row mapping, and previews: empty; two
   distinguishable lands (one name-only, one with municipality and known attributes); duplicate names;
   many lands; long name plus long mixed values; failure; compact (`widthDp = 320`); wide
   (`widthDp = 900`); large font (`fontScale = 2f`) — all inside `ManijeroTheme`.
3. Wire `App`: destination, load on entry, reload after save or retry, callbacks, confirmation, and
   removal of the unreachable chat-home confirmation. Confirm no read at startup or on the chat home
   and no `println`/`Log`/exception text.
4. Run the checks below and the Android/Desktop manual scenarios; report any environment blocker
   honestly.
5. Update `feature_list.json` and `PROGRESS.md` only after implementation and independent validation.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.lands.LandListStateTest"
./gradlew :shared:jvmTest
./scripts/init.sh --verify   # :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
```

This worktree has `local.properties` (per `PROGRESS.md`), so the Android steps should run; if the SDK
is unavailable, record the exact blocker instead of claiming an Android result. There is no persistent
E2E command and no Compose UI-test framework, so focused pure tests plus Android/Desktop manual smoke
are the right coverage for this read-only local slice; do not claim E2E or automated UI coverage.

Manual Android and Desktop smoke checks:

1. With an empty store, select `Mis terrenos` and confirm the empty state explains how to add a land
   and that `Añadir terreno` and `Volver` are visible and reachable.
2. Save `Los Olivos` with no extra details; confirm the app returns to the list, the row shows the
   exact name with `Riego: No lo sé` and `Producción: No lo sé`, and the confirmation is visible and
   announced politely.
3. Save a second land with a municipality, `Regadío`, and `Ecológico`; confirm both rows are visible
   and distinguishable by name, municipality, and attributes.
4. Relaunch and reopen `Mis terrenos`; confirm the same lands are listed (platform persistence) with no
   duplicate records from mere navigation. Then use `Volver` and confirm the chat home returns with no
   record created, and that `Cancelar` from the form also returns to the list without creating a record.
5. Android: enlarge system text and confirm rows/actions wrap without clipping or horizontal scrolling,
   and a screen reader reads each row as a name plus details. Desktop: reach `Añadir terreno`,
   `Reintentar`, and `Volver` by keyboard with visible focus, and resize narrow and wide.
6. Privacy check: `grep -rn "println\|Log\.\|Logger\|printStackTrace" shared/src` returns no matches
   and no network call was added.

Capture: focused test output and counts, `./scripts/init.sh --verify` output (or the exact Android blocker),
screenshots or a short record for empty/one-land/two-land/failure plus enlarged text, and the
no-logging grep result.

## Validator checklist

- [ ] With two lands saved, both are visible as separate rows with their exact names, in repository
      order, with no merged, duplicate, or invented rows; known municipality/water/production are
      shown, unknown values read `No lo sé`, mixed is never shown as unknown, and nothing is invented.
- [ ] The empty state is plain Spanish, says no land is saved, points to `Añadir terreno`, and shows no
      fake or placeholder land.
- [ ] `Añadir terreno` opens the unchanged form; cancel and successful save return to the list, the
      saved land is visible immediately after, and navigation alone creates no record.
- [ ] A failed read shows plain-Spanish failure text with `Reintentar`, never looks empty or stale, and
      exposes no land data or exception contents.
- [ ] `Volver` returns to the chat home; rows are not clickable and no edit/remove/select/detail, area,
      or notes affordance was added.
- [ ] `LandListStateTest` covers empty-load success, failure-not-empty, order/duplicate-name/identity
      preservation, reload clearing, and Unicode/long-name preservation; `:shared:jvmTest` passes;
      `./scripts/init.sh --verify` passes or the Android blocker is reported honestly with no E2E/UI-test claim.
- [ ] New copy and labels are resource-backed and reuse the existing land vocabulary; rows merge
      descendants, the confirmation is a polite live region, and controls work with large text and
      Desktop keyboard focus without color-only cues; product UI/state stays in `commonMain` with no
      new module, dependency, ViewModel, coroutine, or navigation framework and no land-data logging.
- [ ] Scope discipline: `Land`/`LandRepository`/storage format and adapters, `AddLandState`,
      `AddLandScreen`, entry points, Gradle, `theme/`, backend/contracts, and unrelated features are
      untouched; the only `add_land` change is the intended routing and unreachable-confirmation removal.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/land_list.md. Added the pure LandListState/LandListAction/reduce (shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt) where isEmpty means a successful empty read and LoadFailed clears rows so a failed read never looks empty or stale, and the stateless resource-backed LandListScreen (LandListScreen.kt) with non-clickable merged-semantics rows, polite live regions, and previews for empty/two-lands/duplicate-names/many/long/failure/compact/wide/2x font.
- App.kt gains the LandList destination with a single synchronous read site (runCatching { repository.list() } folded into LandsLoaded/LoadFailed, then reduced) invoked only on entry/retry/after-save, Añadir terreno opening the unchanged AddLandScreen, and cancel/successful save returning to the list; the intended land_list routing change removes the now-unreachable ChatHomeScreen landSavedConfirmation parameter and its preview. AddLandState/AddLandScreen behavior and App() (iOS scaffold/previews) are unchanged; 9 new land_list_* strings in composeResources/values/strings.xml reuse the existing land vocabulary.
- Verification: ./gradlew :shared:jvmTest --rerun-tasks -> 60 tests / 0 failures (LandListStateTest 6 new); :shared:testAndroidHostTest -> 57 / 0; ./scripts/init.sh --verify -> BUILD SUCCESSFUL (:shared:jvmTest, :shared:testAndroidHostTest, :androidApp:assembleDebug APK, :desktopApp:build); --rerun-tasks :androidApp:assembleDebug :desktopApp:build -> BUILD SUCCESSFUL. No E2E or Compose UI-test framework exists, so none is claimed.
- Android emulator smoke (Medium_Phone_API_35, 1080x2400): empty state names Añadir terreno with no fake row; saving 'Los Olivos' (name only) returns to the list showing Riego/Producción: No lo sé plus the saved confirmation; a second land (Municipio: Martos, Regadío, Ecológico) adds a distinguishable row in creation order; force-stop + relaunch keeps both with no duplicates or stale confirmation; Volver returns to the chat home and Cancelar returns to the list creating no record; font_scale 2.0 wraps all rows/actions with no horizontal overflow. Desktop run proved no read at startup, the plain-Spanish failure state with only Reintentar and Añadir terreno withheld, failure persisting on retry, and recovery after the store was fixed.
- Privacy: grep -rn 'println|Log\.|Logger|printStackTrace|System.out' shared/src -> no matches; no network call, permission, dependency, or module added; no land id/area/notes shown and no land data or exception text surfaced.
- Independent validator ACCEPTED (2026-10-13), record docs/validations/land_list.md: re-ran ./scripts/init.sh, the focused and full :shared:jvmTest (60/0), :shared:testAndroidHostTest (57/0), ./scripts/init.sh --verify, and a --rerun-tasks build, and byte-for-byte checked the nine new strings plus the reused land vocabulary against the spec; confirmed file-by-file scope discipline (only the intended add_land routing change), the failure/empty-state distinction, and the no-logging/no-network constraints. Findings F1-F6 are non-blocking and carried forward (F1 optional confirmation guard, F2 corrupt-store-content robustness owned by local_land_store hardening, F3 system back handling owned by chat_accessibility, F5 evidence hygiene, F6 default-clock createdAt).
