# Validation — `land_list`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted `land_list`
implementation against `docs/specs/land_list.md`.

Feature id: `land_list`. Spec: `docs/specs/land_list.md`. Claimed status:
`passing` (self-verified by the implementer). Recommended state update:
orchestrator sets `status` to `accepted`.

Two independent validator runs reached the same verdict. The first was
backgrounded and ended before reporting; the second ran to completion and its
results are recorded here together with the first run's confirmations.

## Review target

`git status` before and after validation showed exactly the expected footprint
(hashes unchanged by validation):

- Modified: `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- New: `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`,
  `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandListStateTest.kt`,
  `docs/specs/land_list.md` (planner artifact).

Untouched: `Land.kt`, `LandRepository.kt`, both storage adapters,
`AddLandState.kt`, `AddLandScreen.kt`, `MainActivity.kt`, `desktopApp/main.kt`,
`MainViewController.kt`, all Gradle files, `scripts/init.sh`, `theme/`, `backend/`,
`contracts/`, `knowledge/`, `docs/specs/add_land.md`, `PROGRESS.md`,
`feature_list.json`. `git diff --check` clean. The only cross-feature change is
the intended `Mis terrenos` routing change and the removal of the now-unreachable
`ChatHomeScreen` confirmation.

## Independent checks and results

Commands were re-run by the validator with `--rerun-tasks` / `--no-build-cache`
so the results are actual executions, not cached `UP-TO-DATE` output.

- `./scripts/init.sh`: exit 0 (Gradle 9.8.0 bootstrap; `--verify` is a real gate, not a
  print-only command).
- `./gradlew :shared:jvmTest --tests LandListStateTest --rerun-tasks`:
  **BUILD SUCCESSFUL**, `LandListStateTest` **6 tests / 0 failures**.
- `./gradlew :shared:jvmTest --rerun-tasks`: **60 tests / 0 failures / 0 errors**
  across 11 classes.
- `./scripts/init.sh --verify` (`:shared:jvmTest :shared:testAndroidHostTest
  :androidApp:assembleDebug :desktopApp:build`): **BUILD SUCCESSFUL** (exit 0);
  `:shared:testAndroidHostTest` **57 tests / 0 failures** (includes
  `AddLandStateTest` 11/0, satisfying the spec's validator note).
- `--rerun-tasks :androidApp:assembleDebug :desktopApp:build`: **BUILD
  SUCCESSFUL**, 91 tasks executed; `androidApp-debug.apk` produced.
- Privacy grep (`println|Log\.|Logger|printStackTrace|System.out` in
  `shared/src`, `androidApp/src`, `desktopApp/src`): **no matches**. New files
  import no HTTP/networking, no logging API, no raw `Color(`, no `Icon(`, no
  `maxLines`/`overflow` ellipsis; no `land.id`/`areaHectares`/`notes` rendered.
- Copy fidelity: the 9 new `land_list_*` keys (plus the reused `add_land_*` and
  `chat_home_lands` vocabulary) match the spec **byte-for-byte**, including the
  guillemets in the empty-state copy; the confirmation reuses `add_land_saved`
  and is device-scoped ("... en este dispositivo.").
- Behavioural probes (temporary JVM test, written, run, deleted — worktree left
  byte-identical): a storage whose `read()` throws propagates through
  `LandRepository.list()` and reduces to `LoadFailed`, and
  `LandListState(loadFailed = true)` is **not** `isEmpty`; malformed record lines
  are skipped while valid records survive.

## Acceptance-scenario mapping

1. **Two lands visible, distinguishable, repository order** —
   `reduce(LandsLoaded)` stores the list verbatim (tests kill sorting/dedup/
   renaming mutations); each row shows the exact name, municipality only when
   known, and always water/production with `UNKNOWN → No lo sé` and `MIXED →
   mixed copy`, never presented as unknown. Emulator screenshots show `Los
   Olivos` (name only, two "No lo sé") and `La Loma` (Martos / Regadío /
   Ecológico). **Pass.**
2. **Empty state** — exact spec copy, names the visible `Añadir terreno`, no
   fake/placeholder land; reproduced live on the emulator. **Pass.**
3. **Reach the add action** — `Añadir terreno` opens a fresh `AddLandState` and
   the unchanged `AddLandScreen`; `Cancelar` and a successful save return to the
   list; save success triggers exactly one reload plus the polite confirmation;
   navigation itself writes no record. **Pass.**
4. **Never unreadable or stale** — `loadFailed` is checked before `isEmpty` and
   before rows; `LoadFailed` clears `lands`; `Añadir terreno` is replaced by a
   single `Reintentar`; copy exposes no land data or exception text. **Pass.**
5. **Leave and stay local** — `Volver → AppDestination.Chat`; rows are
   non-clickable `Surface`s with `mergeDescendants = true`; no
   select/detail/edit/remove/area/notes affordance; the read path is only
   `LandRepository.list()`, once per entry/retry/save, never at startup or on
   recomposition. **Pass.**
6. **Tests + gate** — as tabulated above; no E2E or Compose UI-test coverage is
   claimed because none exists in the repo. **Pass.**
7. **Copy / accessibility / architecture** — all new strings are
   resource-backed and reuse the form vocabulary; confirmation and failure text
   are `LiveRegionMode.Polite`; no new module, dependency, ViewModel, coroutine,
   or navigation library; state and UI stay in `commonMain`; no land-data
   logging. **Pass.**
8. **Scope discipline** — verified file-by-file against the spec's "Expected
   file changes"; every "Do not modify" entry is untouched. **Pass.**

## Manual smoke (Android emulator and Desktop)

Android (`Medium_Phone_API_35`, 1080x2400), APK from a fresh build, app data
cleared: chat home with `Mis terrenos` enabled → the list shows the empty-state
copy with `Añadir terreno` + `Volver` and no fake row → `Añadir terreno` opens
the unchanged form with fresh defaults (both enums `No lo sé`) → saving `Los
Olivos` returns to the list with the polite confirmation and `Riego: No lo sé` /
`Producción: No lo sé` (no municipality line) → `La Loma` (Martos / Regadío /
Ecológico) adds a second distinguishable row in creation order → force-stop +
relaunch keeps both with no duplicate and no stale confirmation → `Volver`
returns to chat home with the store unchanged → `Cancelar` from the form returns
to the list creating no record → at `font_scale 2.0` every row/action wraps with
no horizontal overflow (max text right edge ≤ 1017 of 1080).

Desktop (`:desktopApp:run`): the app starts normally even with an unreadable
store (a directory at `~/.manijero/lands-v1.txt`), independently proving no read
happens at startup; `Mis terrenos` shows
`No se han podido leer los terrenos guardados. Puedes intentarlo otra vez.` with
exactly `Reintentar` and `Volver` and **`Añadir terreno` withheld**; `Reintentar`
while still unreadable keeps the honest failure (no crash, no empty fallback, no
stale rows); after the store was fixed, `Reintentar` recovered to the two correct
rows.

## Validator checklist

- [x] Two lands visible as separate rows with exact names in repository order, no
      merging/duplication/invention; known municipality/water/production shown,
      unknown reads `No lo sé`, mixed never shown as unknown.
- [x] Empty state is plain Spanish, says no land is saved, points to
      `Añadir terreno`, and shows no fake or placeholder land.
- [x] `Añadir terreno` opens the unchanged form; cancel and successful save
      return to the list; the saved land is visible immediately; navigation
      alone creates no record.
- [x] A failed read shows plain-Spanish failure text with `Reintentar`, never
      looks empty or stale, and exposes no land data or exception contents.
- [x] `Volver` returns to the chat home; rows are non-clickable; no
      edit/remove/select/detail/area/notes affordance was added.
- [x] `LandListStateTest` covers empty-load success, failure-not-empty,
      order/duplicate-name/identity preservation, reload clearing, and
      Unicode/long-name preservation; `:shared:jvmTest` (60/0) and
      `./scripts/init.sh --verify` pass.
- [x] New copy/labels are resource-backed and reuse the existing land
      vocabulary; rows merge descendants, confirmation is a polite live region,
      and controls work with large text without color-only cues; product
      UI/state stays in `commonMain` with no new module/dependency/ViewModel/
      coroutine/navigation framework and no land-data logging.
- [x] Scope discipline: `Land`/`LandRepository`/storage format and adapters,
      `AddLandState`, `AddLandScreen`, entry points, Gradle, `theme/`,
      backend/contracts, and unrelated features are untouched; the only
      `add_land` change is the intended routing plus unreachable-confirmation
      removal.

## Findings (all non-blocking)

1. **F1 — low, owner: future `App` routing / `edit_land`.** `landSaved` is not
   cleared on `Volver`; it is reset on list entry and when opening the form, so
   no stale confirmation is observable today, but it is fragile. Optional guard:
   reset it in `onBack`.
2. **F2 — low, owner: `local_land_store` hardening.** If the post-save re-read
   itself fails, the saved confirmation and the read-failure text can appear
   together (both true, reads oddly). Optional guard: confirm only when the
   post-save read succeeded. Related below.
3. **F2b — informational, owner: `local_land_store` hardening /
   `docs/risks-and-open-questions.md`.** A store whose *content* is corrupt (bad
   header or every record malformed) decodes to an empty list, so the person
   would see the empty state instead of a failure. This is the accepted
   `LandStoreFormat.decode` contract, which `land_list` is explicitly forbidden
   to change; the failure state therefore requires the read itself to throw
   (e.g. a non-string value under `land_store`, or an unreadable file on
   Desktop). Worth recording as a real robustness gap.
4. **F3 — informational, owner: `chat_accessibility` / navigation hardening.**
   No `BackHandler`; Android system back exits the app from any destination, and
   only `Volver` navigates back. Pre-existing, unchanged here, not required by
   the spec.
5. **F4 — harness, owner: repo harness/planner.** The feature-validator skill
   references `references/validation-rubric.md` and
   `references/security-checklist.md`, which are absent from this checkout; the
   embedded rubric and a portable security review were applied inline. Also,
   `./scripts/init.sh --check` prints a stale status line, and `scripts/init.sh` is out of scope
   for this feature.
6. **F5 — evidence hygiene, owner: orchestrator (this record).** Manual-smoke
   evidence and the failure trigger are recorded here because the emulator
   screenshots live outside the repo; Android reproduction of the corrupted-store
   branch needs a route other than `adb shell` writes (SELinux blocks them).
7. **F6 — informational, owner: future land features.** The Android composition
   root uses the repository's default clock, so persisted lands carry
   `createdAtEpochMillis = 0`. Pre-existing, invisible to this read-only list,
   but any future "order by time" behavior must set a real clock.
8. **Informational.** TalkBack row-merge reading and Desktop keyboard
   focus/resize were not verified end-to-end (assistive access denied / no UI-test
   harness); the `mergeDescendants` and polite live-region attributes are present
   in code, and the spec defers this verification to `chat_accessibility` /
   `land_form_accessibility`.

## Security and privacy assessment

Scoped to this feature and diff: **no relevant issues found**.

- No network call, permission, dependency, module, or persistence-format change;
  the land store stays in the existing private app store.
- No `println`/`Log`/`printStackTrace`/logger usage in any changed file; the
  caught read throwable is discarded, and failure copy leaks no land data or
  exception text.
- `Land` ids, `areaHectares`, and `notes` are never rendered, logged, or sent;
  rows are non-clickable with no destructive affordance; the screen accepts no
  input (no injection surface); no authorization surface exists.
- The deliberate trade-off of dropping the read throwable removes any diagnostic
  breadcrumb, consistent with this repo's "keep personal details out of logs"
  rule.

## Documentation and harness state

- `feature_list.json` was updated to `status: accepted` with evidence matching
  the independently reproduced results; `PROGRESS.md` records the implementation
  and the honest unverified items.
- `docs/specs/land_list.md` is present and matches the implementation.
- `DESIGN.md` surface 4 (simple list, one primary action, visible `Volver`,
  labelled controls, no map/table, no color-only cues) is followed. No
  `ARCHITECTURE.md`/`CONSTRAINTS.md` exist and none were needed.
- No persistent E2E or Compose UI-test harness exists; focused pure-state tests
  plus manual Android/Desktop smoke are the right coverage for this read-only
  local slice.

## Required follow-up

None for acceptance. Optional follow-ups: F1 confirmation guard, F2 post-save
failure pairing, F2b store-content corruption robustness (owner:
`local_land_store` hardening), F3 Android system back (owner:
`chat_accessibility`), and the deferred TalkBack/keyboard verification.
