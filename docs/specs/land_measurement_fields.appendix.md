# Appendix: `land_measurement_fields`

Planning record for [`land_measurement_fields.md`](land_measurement_fields.md). The contract is the bounded
implementation/validation read; this appendix keeps the repository research, the ordered plan, the verification
detail and the raw evidence.

## Repository research (inspected at base `83e02ba`)

### Domain and storage

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/Land.kt`: `Land` stores `id`, `name`, `municipality`,
  `waterRegime`, `productionMethod`, `areaHectares`, `notes`, timestamps; `LandDraft` mirrors it without id/timestamps.
  No zone, variety or tree count exists today.
- `lands/LandRepository.kt`: `LandRepository` owns list/create/update/delete; `normalize` requires a non-blank name and
  a non-negative area; `LandStoreFormat` writes `land-store-v1` with nine `|`-separated, escaped fields and decodes only
  that header, skipping corrupt lines.
- Desktop storage keeps the file `~/.manijero/lands-v1.txt`; Android uses `manijero_lands` SharedPreferences (same
  format). Desktop store tests (`AddLandDesktopStoreTest`, `EditLandDesktopStoreTest`, `RemoveLandDesktopStoreTest`)
  exercise real files with the v1 name.

### Forms and state

- `lands/AddLandState.kt`: raw name/municipality text, enum selections, `showNameError`/`showSaveError`,
  `toDraftOrNull()`; blank name blocks the draft. `lands/EditLandState.kt`: prefilled form, `landId` only,
  `preservedAreaHectares`/`preservedNotes` carried through because the short form does not show them,
  `EditLandFailure` distinguishes write failure from a missing land.
- `lands/AddLandScreen.kt` / `EditLandScreen.kt`: one scrolling `Surface` + 720 dp column, `OutlinedTextField`s,
  a local `ChoiceGroup` with `Role.RadioButton`, save/cancel actions, and light/dark/2×/compact/wide previews. Name
  errors are announced with a polite live region and re-request focus from the save path.
- `App.kt` owns the only write paths: `repository.create(draft)` on `SaveClicked`, `repository.update(landId, draft)`
  on edit, with `AddLandAction.SaveFailed` / `EditLandFailure` when storage refuses or the id is gone.

### Shared land details

- `lands/LandListScreen.kt` defines `internal fun LandDetails(municipality, waterRegime, productionMethod)` used by
  the list row, `lands/RemoveLandScreen.kt`, and the clarification chooser in `App.kt`. It deliberately omits name,
  id, area and notes today.
- `lands/RemoveLandState.kt` snapshots exactly the identity fields `LandDetails` renders.

### Design layer available for this feature

- `design/ManijeroFields.kt` already provides `internal ManijeroDropdownField` (caller-owned options, selected value,
  error + supporting text) and `internal ManijeroMeasureField` (verbatim text, keyboard type, error text, no parsing).
  They are presentational only and have light/dark/2× previews.
- `design/ManijeroChoiceCard` exists but the existing form uses its own `ChoiceGroup`; this feature does not restyle
  water/production, so the existing group stays.

### Privacy and chat boundary

- `privacy/LandDataDisclosure.kt` pins `SharedLandAttribute` / `SHARED_LAND_ATTRIBUTES` to the three sendable
  dimensions; `privacy/PrivacyScreen.kt` renders the local/sent sections from `strings.xml`.
- `privacy/LandDataDisclosureTest.kt` encodes an `AskRequest` for a fully populated land and asserts the optional keys
  equal the pinned sendable list.
- `chat/LandContextBuilder.kt` decides needed attributes from question vocabulary and builds the minimal per-land
  context; `minimal_land_context`'s accepted constraint forbids names, notes, area, timestamps and unknown keys.
- `CONSTRAINTS.md` "Land editing" currently requires the edit form to carry `areaHectares` and `notes` through
  unchanged; "Land data disclosure" names name/notes/area/timestamp as never sent.

### Screenshots

- `ScreenshotFixtures.twoLands` feeds `land_list_light`/`land_list_light_phone` (Desktop), `land_list_light`
  (Android) and `app_shell_lands_rail_dark` (both hosts). `recordScreenshots` re-records the whole suite, so the
  implementer must filter the two record tasks to the affected test classes or restore untouched goldens from git.
- `:shared:jvmTest` and `:shared:testAndroidHostTest` exclude `com.jamarglex.manijero.screenshots.*`;
  `:shared:verifyScreenshots` aggregates the two host suites.

### Product inputs

- `docs/design/ui-refresh-plan.md` (approved 2026-10-25): D5/D6 add search/count/surface/tree summary plus optional
  surface, tree count and variety with a required zone; D12–D17 fix the superseding decision, local-only rule, search
  fields, summary honesty, zone rules and legacy validity; §7 gives the model, store v2 layout, validation table,
  privacy split and copy inventory; §9 assigns P1-01…P1-09 and P1-14…P1-16 to this feature.
- `docs/specs/land_setup_fields_decision.md` (accepted 2026-10-20): deferred area/notes and kept only the name
  required, explicitly as a desk review with **no target-user session**; it must be superseded, not rewritten.
- `docs/risks-and-open-questions.md` line 36 records that deferral; `docs/domain-model.md` lists area as
  "collect only if an MVP use case needs it"; `DESIGN.md` says to ask for a name first and collect only useful details.
- Product-owner confirmation for this run: accept all approved plan defaults (required zone, approved variety list
  with required `Otra` text, optional surface/trees, show the values in the existing rows, local-only).

### Unknowns / honest gaps

- No new target-user evidence exists. The required zone and the 10-option variety list are product decisions, not
  usability findings, and may lengthen setup for low-digital-confidence users.
- The repo has no automated UI/E2E harness for form interaction or screen-reader output; the evidence is unit tests,
  previews, host goldens and a manual walkthrough.
- No real v1→v2 upgrade on a device is performed; compatibility is proven by decoder/encoder unit tests.

## Implementation plan and tasks

Ordered; each task ends with the stated check. Docs first so the superseding record exists before code changes.

1. **Append the superseding decision** (P1-01): add a dated section to `land_setup_fields_decision.md` with the new
   required/optional rules, the approved variety list, legacy handling, local-only rule, no-new-evidence statement and
   downstream owners; update the matching question in `docs/risks-and-open-questions.md`. Check: old 2026-10-20 text
   is byte-identical.
2. **Field helpers** (P1-02/04 support): add `lands/LandFields.kt` (`ZONE_MAX_LENGTH`, `VARIETY_OTHER_MAX_LENGTH`,
   zone/variety checks, `parseAreaHectares`, `parseTreeCount`, `roundHectares`, `formatHectares`,
   `formatTreeCount`, `areaInputText`) and `LandFieldsTest`. Check: parse/format boundary, overflow, unicode, comma/dot,
   blank, negative, non-finite, 3-decimal rounding.
3. **Model**: add `zone` to `Land`/`LandDraft` (draft zone non-null), `LandVariety`, `varietyOther`, `treeCount`; add
   `LandVariety` label mapping where the existing water/production mapping lives. Update every `LandDraft(...)` call
   site (41 today, mostly tests) with a zone. Check: compiles; no test relies on the old default.
4. **Store v2** (P1-03): writer emits `land-store-v2` (13 fields); decoder accepts v1 (9 fields) and v2, keeps escaping
   and conservative skipping. Add `LandStoreFormatTest`: v1 file, v2 round-trip, mixed file, escaped zone/variety,
   invalid enum/number, unknown header, empty file. Check: Desktop store tests still pass with the same file name.
5. **Normalize** (P1-04): require a trimmed non-blank zone ≤ 80; require `varietyOther` only for `OTHER` (trimmed,
   ≤ 40) and clear it otherwise; reject negative/non-finite area and trees < 1; round area to two decimals. Extend
   `LandRepositoryTest`/`EditLandRepositoryTest`. Check: no invalid record can be written and notes/createdAt survive
   an edit.
6. **Add flow** (P1-05/07): extend `AddLandState`/`reduce`/`toDraftOrNull` with zone, variety, variety-other, surface
   and tree text plus error flags; render zone, variety dropdown, conditional `Otra` field and two measure fields in
   `AddLandScreen` via the existing component layer; focus the first invalid field on save; add/adjust previews.
   Extend `AddLandStateTest` (blank/too-long zone, Otra without text, invalid/valid measurements, raw text preserved,
   unknown defaults, emoji/accents). Check: previews and tests.
7. **Edit flow** (P1-06/08): prefill all new fields from `Land` (legacy zone empty), keep `preservedNotes` only, block
   save until invalid fields are fixed, keep id/createdAt; extend `EditLandStateTest` and Desktop edit tests. Check:
   editing a legacy record requires a zone and preserves notes.
8. **Surfaces** (P1-09): extend `LandDetails` and its three callers (list, remove confirmation, clarification chooser)
   with zone/variety/surface/tree lines; update `RemoveLandState` + `RemoveLandStateTest` and previews; update the
   screenshot fixture lands. Check: known values only, absent measures omitted, unknown variety reads `No lo sé`.
9. **Privacy** (P1-14/15): update `privacy_local_body_2` and `privacy_sent_not_sent`, and add a
   `LandDataDisclosureTest` assertion that the encoded request for a fully populated land contains none of the five
   new names/values. Check: pinned sendable list unchanged, test fails if a new field enters the payload.
10. **Copy and previews**: add the new `strings.xml` keys, update add/edit descriptions, light/dark/2× previews for
    the new field states. Check: `validate_coverage_copy.py` unaffected; plain Spanish reviewed.
11. **Screenshots**: re-record only `land_list_light`, `land_list_light_phone`, `app_shell_lands_rail_dark` (Desktop)
    and `land_list_light`, `app_shell_lands_rail_dark` (Android); restore any other image that the full record task
    touched. Check: `git status` lists only those five PNGs plus intended sources.
12. **Durable docs**: update `docs/domain-model.md`, `CONTEXT.md`, `DESIGN.md`, `CONSTRAINTS.md`; leave
    `ARCHITECTURE.md`/`AGENTS.md` untouched.
13. **Verify and record**: run the focused block, `--fast` and `--verify`; add the raw evidence below; after the
    independent validator accepts, update `feature_list.json`, `PROGRESS.md`, `docs/progress/current-state.md` and
    `docs/progress/session-log.md` and write `docs/validations/land_measurement_fields.md`.

## Verification plan

Automated (published in the contract):

- `./scripts/init.sh --feature land_measurement_fields` — `:shared:jvmTest`, both host screenshot suites, the static
  v1/v2/no-leak/string/test-file gates.
- `./scripts/init.sh --fast` — shared host tests, contract examples, backend suite (if pytest is available), offline
  evaluators; no backend behaviour changed, so this is a regression guard.
- `./scripts/init.sh --verify` — adds the Android host tests, debug APK and Desktop build.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` — optional shared-code compatibility smoke; record if unavailable.

Manual evidence to capture:

- Desktop (or emulator): add a land with name + zone only, then one with all fields; observe the row lines and the
  remove confirmation; edit a legacy v1 record and confirm the required-zone path, focus, and preserved notes.
- Light/dark and 2× text on the form at 320 dp: no clipped field, action or error; screen-reader names for the new
  fields and the `Otra` field.
- Visual review of the five re-recorded goldens in the PR (product owner sign-off remains a separate outstanding item,
  as already recorded in `PROGRESS.md`).

Not verifiable in this repo: real-user comprehension, a real v1→v2 device upgrade, downgrade to an older build,
iOS runtime rendering, and any claim that the new fields improve answers.

## Evidence to capture

- Exact commands and exit codes for the three tiers; test counts for the new/updated classes.
- The five re-recorded goldens and confirmation that no other image changed.
- The manual walkthrough notes (host, appearance, text scale, focus order, what was observed).
- The v1 fixture that the decoder test uses and the exact v2 line it writes.
- Explicit "not verified" lines: no user evidence, no device migration, no downgrade, no accessibility audit.

## Feature evidence

### 2026-10-25 — implementer self-verification

Environment: macOS (darwin), repository worktree `land_measurement_fields` at base `83e02ba`; JDK and
Android SDK from `local.properties` (ignored, not committed).

**Focused gate** — `./scripts/init.sh --feature land_measurement_fields` → exit `0`.

```text
BUILD SUCCESSFUL in 10s
jvmTest suites 25 tests 245 failures 0 errors 0
verifyDesktopScreenshots suites 5 tests 18 failures 0 errors 0
verifyAndroidScreenshots suites 5 tests 14 failures 0 errors 0
```

The static gates in the published block all passed: v2 writer and v1 reader present, `LandVariety`
enum, `zone`/`treeCount` in `Land.kt`, no new field name in `chat/LandContextBuilder.kt`, all fourteen
required string keys, and both new test files present.

**No-device tier** — `./scripts/init.sh --fast` exited `0`:

- `:shared:jvmTest` passed (245 tests).
- Contract examples: `Validated 2 request and 3 response examples against answer_api_contract`.
- Backend unit tests: `[skip] Backend unit tests: pytest is not installed.` (`python3 -c 'import pytest'`
  failed; no virtualenv was present). No backend file changed.
- The nine offline evaluators: `All 9 offline checks passed.` (`Fast tier passed.`).

**Full gate** — `./scripts/init.sh --verify` — exit `0`: fast tier passed, `:shared:testAndroidHostTest`
reported 231 tests / 0 failures, `:androidApp:assembleDebug` produced the debug APK, and
`:desktopApp:build` succeeded.

**New and updated test counts** (JVM results XML): `LandFieldsTest` 10, `LandStoreFormatTest` 8,
`LandRepositoryTest` 6, `AddLandStateTest` 14, `EditLandStateTest` 12, `EditLandRepositoryTest` 7,
`RemoveLandStateTest` 8, `RemoveLandRepositoryTest` 5, `LandDataDisclosureTest` 3, plus the existing
Desktop store tests (5). All passed.

**Store fixtures used by the decoder tests**

- v1 input: `land-store-v1\nland-1|Los Olivos|Martos|UNKNOWN|UNKNOWN|||1|2` loads with `zone = null`,
  `variety = UNKNOWN`, `varietyOther = null`, `treeCount = null`, `areaHectares = 2.5`, notes and
  timestamps intact.
- The same record after a real repository `update` with `zone = "El Llano"` writes exactly the v2
  header plus
  `land-1|Los Olivos|El Llano|Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||1|5` (13 fields), preserving
  `createdAtEpochMillis = 1` and writing `updatedAtEpochMillis = 5`.
- Mixed/corrupt files: an unknown enum, a short line, `NaN` area and a non-numeric tree count are
  skipped whole while their valid neighbours survive; v1 and v2 headers never decode each other's
  line shape.

**Screenshots** — recorded with filtered tasks (each `BUILD SUCCESSFUL`, exit `0`):

```sh
./gradlew :shared:recordDesktopScreenshots \
  --tests 'com.jamarglex.manijero.screenshots.LandListScreenshotsTest.landListLight' \
  --tests 'com.jamarglex.manijero.screenshots.LandListScreenshotsTest.landListLightPhone' \
  --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark'
./gradlew :shared:recordAndroidScreenshots \
  --tests 'com.jamarglex.manijero.screenshots.LandListAndroidScreenshotsTest.landListLight' \
  --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark'
```

Only the five intended goldens changed; `git status` listed no other PNG:

- Desktop `shared/src/jvmTest/screenshots/land_list_light.png`, `land_list_light_phone.png`,
  `app_shell_lands_rail_dark.png`.
- Android `shared/src/androidHostTest/screenshots/land_list_light.png`,
  `app_shell_lands_rail_dark.png`.

Each image was opened and reviewed: both populated rows show `Zona`, `Variedad` and the known
`Superficie`/`Olivos` lines; `La Loma` omits the absent surface/tree lines and shows its custom
`Royal de Cazorla` text; the shell rail keeps the same layout with the taller rows. The phone capture
shows the second card extending past the viewport, which is expected because the list column is
scrollable; it was already a scrolling capture and no control is clipped or disabled.

**Manual/observable limits (not verified)**

- No interactive Desktop or emulator walkthrough was performed in this environment; the user-flow
  evidence is the pure state/repository tests plus the five reviewed host goldens and the Compose
  previews (light, dark, 2×, compact, wide) added/updated with the forms.
- No real `land-store-v1` → v2 device upgrade, no downgrade to an older build, and no backup/sync
  restore was exercised; compatibility is proven only by decoder/encoder and repository tests.
- No screen-reader audit or measured 2×-text verification on a device; focus order and the polite live
  regions are code-reviewed, not observed with assistive technology.
- No new target-user evidence exists for the required zone or the ten-option variety list.

## Validator checklist

- [ ] Contract scenarios 1–9 are each exercised by a test, a static gate, or a recorded manual check, and the evidence
      names which one.
- [ ] A `land-store-v1` fixture loads with `zone = null`, `variety = UNKNOWN`, `treeCount = null`; the writer emits
      `land-store-v2`; escaping, mixed files and corrupt lines behave conservatively.
- [ ] New records cannot be written without a zone; legacy records remain listed; editing a legacy record blocks until
      a zone is supplied and keeps id, `createdAtEpochMillis` and notes.
- [ ] Optional fields stay optional: blank values persist as null/`UNKNOWN`, never zero, never inferred, and the edit
      form prefills stored values.
- [ ] Surface accepts comma/dot, rejects negative/non-finite values with plain Spanish copy, and rounds a
      three-or-more-decimal entry to two decimals; trees require a whole number ≥ 1; raw text survives an error.
- [ ] `Otra` requires non-blank ≤ 40 text; the approved shortlist and `No lo sé` match the contract; the custom text is
      displayed.
- [ ] `LandContextBuilder` and every `AskRequest` shape are unchanged; a fully populated land yields no
      zone/variety/varietyOther/area/treeCount key; the disclosure copy matches.
- [ ] The 2026-10-20 decision text is unmodified and the appended section states the product decision, field rules,
      missing user evidence and affected owner features.
- [ ] Only the intended five goldens changed; forms have light/dark/2× previews; no new colour, token, dependency,
      module, backend, contract or knowledge change.
- [ ] `CONSTRAINTS.md`, `DESIGN.md`, `CONTEXT.md`, `docs/domain-model.md` and `docs/risks-and-open-questions.md` match
      the shipped behaviour; `ARCHITECTURE.md`/`AGENTS.md` are correctly untouched.
- [ ] Verification was run independently, not only quoted from the implementer; honest limits are recorded.
