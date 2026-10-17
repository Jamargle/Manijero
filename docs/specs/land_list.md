# Feature Spec: `land_list`

## Source metadata

- **Feature:** `land_list` — Find a saved land (`lands`)
- **Status at planning:** `not_started`; depends on accepted `local_land_store`, `add_land`, and
  `visual_foundation`.
- **Source behavior:** A person can see their saved lands by their chosen names, distinguish similar
  lands, and reach an add action.
- **Feature verification:** With two saved lands, confirm both are visible and distinguishable;
  confirm the empty state explains how to add one.
- **Note:** use a simple list rather than a map-first or spreadsheet-style layout.

## Goal and boundaries

Add the missing `Mis terrenos` screen: a read-only, shared, plain-Spanish list of locally saved lands
with a visible add action, an empty state that explains how to add the first land, and an honest
failure state. `land_list` becomes the parent surface of the existing add form.

**In scope**

- A `LandList` destination reached from the existing chat-home `Mis terrenos` affordance.
- One synchronous `LandRepository.list()` read when the list is entered, and again after a save or a
  retry.
- One simple row per land: the exact user-chosen name plus the distinguishing facts the MVP collects
  (municipality only when known; water and production always, with unknown shown as `No lo sé`).
- Visible `Añadir terreno` (opens the unchanged form) and `Volver` (back to chat home) actions.
- An empty state that explains how to add the first land; a plain-Spanish load-failure state with one
  `Reintentar` action; a plain-Spanish saved confirmation after adding from this screen.

**Non-goals**

- Selecting a land for chat, land detail, editing, removal, undo, or archiving (`minimal_land_context`,
  `edit_land`, `remove_land` own those). Rows are not clickable.
- Any change to `Land`, `LandDraft`, `LandRepository`, the `land-store-v1` format, the storage
  adapters, `AddLandState`/`AddLandScreen` behavior, the entry points, or the theme.
- Map/SIGPAC, table layout, search, filter, sort, counts, badges, or lazy/paged list infrastructure.
- Displaying `areaHectares` or `notes`; showing, logging, or exporting land IDs; telemetry, cloud,
  accounts, backup, or any network call.
- A navigation library, ViewModel, DI, coroutine, or new dependency for this synchronous local read;
  iOS release work is out of scope and product behavior stays in `commonMain`.

## Job story

When I have saved one or more olive lands, I want to open a plain list and recognize each one by the
name I chose and the few details I know, so I can check that my lands were saved and add another one
without remembering a hidden structure.

## Acceptance scenarios

### See saved lands by their chosen names

Given two lands are saved locally, when the person opens `Mis terrenos`, then both appear as separate
rows showing the exact names they were saved with, in repository (creation) order, and no third,
merged, or invented row appears.

### Distinguish similar lands

Given one land was saved with only a name and another with a municipality and known water and
production, when the person views the list, then each row also shows its known municipality, water,
and production, and unknown values read `No lo sé` rather than a guessed value. Two lands sharing a
name both stay visible (unmerged) so their other details can tell them apart.

### Reach the add action

Given the list is visible, when the person selects `Añadir terreno`, then the existing form opens with
fresh default state and the navigation itself creates no record; after a successful save the app
returns to the list, the new land is visible, and the plain-Spanish saved confirmation appears.

### Explain the empty state

Given no land is saved, when the person opens `Mis terrenos`, then a short plain-Spanish explanation
says no land has been saved yet and points to the visible `Añadir terreno` action, and no empty row,
fake land, or map/table placeholder appears.

### Never present an unreadable or stale list

Given reading local lands fails, when the person opens the list or retries, then a plain-Spanish
message says the saved lands could not be read, one `Reintentar` action is offered, `Añadir terreno` is
not offered while the read fails, and neither the empty-state message nor previously loaded rows are
presented as current. The copy exposes no land data or raw exception text.

### Leave the list and stay local

Given the list is open, when the person selects `Volver`, then the app returns to the chat home and
creates no record. The screen reads only through `LandRepository.list()`, sends nothing over the
network, and logs no land name, municipality, or exception contents.

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
  focus, and no color-only cues. `MasterPlanV3.md` line 942 also requires home access to `Mis terrenos`;
  `docs/domain-model.md` allows zero or more lands, requires a name that helps distinguish similar
  lands, keeps unknown a real state that must not become a default category, keeps data on device, and
  forbids logging land values.

The feature is correctly sized: one accepted model/repository, one read-only screen, one navigation hop.

## Technical approach

1. **Pure state first.** Create `LandListState.kt` in the `lands` package with no Compose, resource, or
   platform imports:

   ```kotlin
   data class LandListState(val lands: List<Land> = emptyList(), val loadFailed: Boolean = false) {
       val isEmpty: Boolean get() = lands.isEmpty() && !loadFailed
   }

   sealed interface LandListAction {
       data class LandsLoaded(val lands: List<Land>) : LandListAction
       data object LoadFailed : LandListAction
       data object ReloadClicked : LandListAction
   }

   fun LandListState.reduce(action: LandListAction): LandListState
   ```

   Contract: `LandsLoaded` stores the supplied list exactly (same order, identities, and duplicate
   names — no sorting, deduplication, or renaming) and clears `loadFailed`; `LoadFailed` clears
   `lands` and sets `loadFailed = true`, so a failed read never looks like an empty list and stale rows
   never survive a failed reload; `ReloadClicked` clears both before the caller re-reads. This layer
   owns no ids, timestamps, persistence rules, or resource lookups.

2. **Stateless screen.** Create `LandListScreen.kt` with
   `LandListScreen(state, onAddLand, onBack, onRetry, savedConfirmation = false)`. It renders the state
   it receives, reports interactions through callbacks, and maps `WaterRegime`/`ProductionMethod` to the
   existing `add_land_*` strings through a private Composable helper. Keep the established `Surface` +
   `Column(verticalScroll)` + `widthIn(max = 720.dp)` layout, and style rows like the existing
   transcript card (`surface` container, `outlineVariant` border, 16dp rounded corners) with no raw
   color.

3. **App wiring.** Extend the private destination enum with `LandList` and route `Mis terrenos` to it,
   keeping the affordance disabled when `landRepository == null` so `App()` for the iOS scaffold and
   previews is unchanged. `App` owns a `LandListState` and performs the read in one place
   (`runCatching { landRepository.list() }` folded into `LandsLoaded` or `LoadFailed`, then reduced):
   never at startup, on the chat home, or on ordinary recomposition, and never logging the throwable or
   a land value. `Añadir terreno` opens a fresh `AddLandState`; `AddLandScreen` is unchanged. `Cancelar`
   and a successful save return to the list (reloading and confirming after a success); a save failure
   keeps the existing form behavior.

4. **No new dependencies.** Keep the read synchronous on the composition frame, like the accepted save
   path. A ViewModel, coroutine, navigation library, DI, lazy list, or Compose UI test framework is
   deliberately out of scope for this bounded local slice.

### Copy contract

Plain Spanish in the established tú voice. Reuse existing resources; only the concepts marked *new*
need new keys.

- Heading: reuse `chat_home_lands` (`Mis terrenos`) so the label the person tapped matches the screen.
- *New*: a one-line explanation (`Estos son los terrenos guardados en este dispositivo.`); an empty
  state that names the visible action (`Todavía no has guardado ningún terreno. Usa «Añadir terreno»
  para guardar el primero.`); the actions `Añadir terreno` (primary) and `Volver` (secondary), both
  labeled text controls and never icon-only; a failure state with one retry action (`No se han podido
  leer los terrenos guardados. Puedes intentarlo otra vez.` plus `Reintentar`); and the labeled row
  lines `Municipio: %1$s` (only when known), `Riego: %1$s`, `Producción: %1$s`.
- Row values reuse `add_land_unknown`, `add_land_water_*`, and `add_land_production_*` so a state reads
  the same as in the form; never substitute a value for `UNKNOWN` and never present mixed as unknown.
- Confirmation: reuse `add_land_saved` in a polite live region; never claim cloud backup, and never
  imply that a saved land proves eligibility or legal status.

## Visual design impact

Reuse `ManijeroTheme` roles only: `background` page, `surface` rows with an `outlineVariant` border,
`onBackground` heading, `onSurface` names, `onSurfaceVariant` details, `primary` for the primary
action, `error` for the failure text. No raw colors, gradients, icons, or new tokens.

```
Mis terrenos                                  (headlineMedium)
Estos son los terrenos guardados…             (bodyLarge, onSurfaceVariant)
[ saved confirmation, when just saved ]        (polite live region)
   rows (name + Municipio/Riego/Producción)  or  empty-state explanation  or  failure explanation
[ Añadir terreno ]  (primary, full width)      or  [ Reintentar ] in the failure state
[ Volver ]          (secondary TextButton, full width)
```

- One primary action per screen, in the same predictable bottom block as `AddLandScreen`, with `Volver`
  as the secondary action. In the failure state the primary action is `Reintentar`; `Añadir terreno` is
  withheld until the list reads successfully, so nobody is invited to write onto a store the app could
  not read.
- Rows are plain, non-clickable, never color-coded text cards; the simple list is preferred over a map
  or table. Long names and values wrap in full (no ellipsis, no horizontal scrolling); the screen
  scrolls vertically.
- Accessibility: merge each row's descendants so assistive technology reads the name and its details
  as one item; confirmations use `LiveRegionMode.Polite`; all controls keep Material's normal minimum
  target size, visible labels, and Desktop focus behavior; distinguishability never relies on color.

## Cross-feature interaction (navigation decision)

`land_list` takes over the `Mis terrenos` entry point, so the accepted `add_land` routing changes:

- Chat home `Mis terrenos` → lands list (previously → add form); the form is now reached through the
  list's `Añadir terreno` action, as `DESIGN.md` surface 4 requires.
- After a successful save and after `Cancelar`, the app returns to the lands list (previously the chat
  home), so a person who adds a land immediately sees it.
- Because no path saves directly from the chat home any more, remove the now-unreachable
  `landSavedConfirmation` parameter and its preview from `ChatHomeScreen`; the confirmation lives only
  on the lands list (same `add_land_saved` string).
- Every other `add_land` guarantee is unchanged: blank name rejected with no record, both enums
  defaulting to `No lo sé`, failed save retaining values with plain-Spanish recovery, no land data or
  raw exception logging, form behavior in `commonMain`.
- Validator note: treat this routing change as intended scope, not a regression; re-run the `add_land`
  focused tests and do not require the old chat-home return destination.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt`: pure state,
  actions, reducer, and the `isEmpty` contract; no imports beyond `Land`.
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: stateless
  list screen, private row/label mapping, action block, previews.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `LandList` destination,
  owned `LandListState`, one-place load/reload, `Mis terrenos` routing, add/back/retry wiring,
  post-save return, removal of the unreachable chat-home confirmation, unchanged `App()` behavior.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the new `land_list_*`
  concepts (explanation, empty state, `Añadir terreno`, `Volver`, three labeled row lines, failure
  text, `Reintentar`).
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandListStateTest.kt`: focused
  state tests built from directly constructed `Land` values (no disk, framework, or Compose I/O).
- **Do not modify** `Land.kt`, `LandRepository.kt`, storage adapters, `AddLandState.kt`,
  `AddLandScreen.kt`, `MainActivity.kt`, `desktopApp/main.kt`, `MainViewController.kt`, Gradle files,
  `scripts/init.sh`, `theme/`, backend/contracts/knowledge, or `feature_list.json`/`PROGRESS.md` while
  implementing.

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

## Durable documentation impact

- `feature_list.json`: **not yet**; keep `not_started` until independent verification, then record
  evidence and status.
- `PROGRESS.md`: **not yet**; add only verified evidence and known gaps.
- `docs/specs/add_land.md`: **do not modify**; the navigation change is recorded here and `add_land`'s
  substantive behavior is unchanged.
- `DESIGN.md`, `docs/domain-model.md`, `CONTEXT.md`, `docs/build-brief.md`, `AGENTS.md`: **not needed**;
  this implements existing surface-4 and land-lifecycle decisions.
- `docs/risks-and-open-questions.md`: **not needed**; the duplicate-name limit below is a recorded
  known limit, not a new product question.
- `ARCHITECTURE.md`, `CONSTRAINTS.md`: **not needed**; neither exists and this adds no durable
  architectural decision (it reuses the accepted reducer/screen/injected-repository pattern).

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

## Known limitations to record honestly

- Two lands with the same name, no municipality, and unknown attributes render as visually identical
  rows separated only by order. The app does not invent labels or expose opaque IDs; the domain model
  expects user-chosen names to distinguish lands, and `edit_land` is the eventual remedy. Do not
  silently de-duplicate or number rows.
- `areaHectares` and `notes` are persisted but not shown, so a land that differs only by notes is not
  distinguishable here yet.
- The read is synchronous on the composition frame (like the accepted save path), which is acceptable
  for a bounded local land count; a large store and lazy loading are out of scope.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests LandListStateTest
```
<!-- verify:end -->

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
