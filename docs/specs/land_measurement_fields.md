# Feature Spec: `land_measurement_fields`

## Source metadata

- **Feature:** `land_measurement_fields` — Add zone, variety, surface, and tree-count land fields (`lands`).
- **Status at planning:** `not_started`; dependencies `design_token_refresh` and `ui_component_library` are accepted.
- **Source behavior:** collect a required zone (paraje) plus optional variety, surface and olive-tree count for each
  local land, with local persistence and plain-Spanish forms, without changing the `/ask` payload.
- **Source verification:** create/edit/read a land with the new fields in both states; v1 files still load; the encoded
  question request never contains the new values.
- **Feature-list note:** opens the approved UI-refresh land-field slice
  ([`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md) §1 D5/D6/D12–D17, §7, §9: P1-01…P1-09,
  P1-14…P1-16). The scope change supersedes the 2026-10-20 field deferral **by product decision**, with no new
  user evidence.

## Goal and boundaries

Make a saved land describe the place and the grove in the words a person actually uses, so lands stay
distinguishable and later search/summary work has real data. The new attributes stay on the device and never enter
chat context.

**In scope**

- `Land`/`LandDraft` gain `zone`, `variety`, `varietyOther` and `treeCount`; `areaHectares` becomes
  user-entered (it was already stored but never collected).
- Store format `land-store-v2` (13 fields) written by the app; `land-store-v1` files still decode, mapping missing
  fields to `null`/`UNKNOWN`.
- Required-zone validation for new and edited records; optional variety/surface/trees with plain-Spanish errors and
  preserved raw text; legacy lands without zone stay readable and require a zone only when edited.
- Add and edit forms render the new fields; the existing land-row details, remove confirmation and clarification
  chooser show the new known values.
- Privacy copy and the payload-correspondence test state that the new values are local-only.
- A dated superseding decision appended to `land_setup_fields_decision`, without rewriting its 2026-10-20 record.
- Re-record only the land-list/shell goldens that the changed row content actually touches.

**Non-goals**

- No land search, summary cards, chips, or lands-screen restyle (`land_search_and_summary`, `lands_screens_refresh`).
- No map, parcel, SIGPAC, cadastral or eligibility content; no inference of any value.
- No `MinimalLandContext`, `AskRequest`, OpenAPI, backend, knowledge or prompt change.
- No new dependency, module, font, vector, icon or token; no change to name/municipality/water/production semantics.
- No forced migration of existing lands, no backup, sync, restore or downgrade support.
- No claim that new owner-side checks replace the outstanding low-digital-confidence user check.

## Job story

When I save a land, I want to say where it is and, if I know them, its variety, size and number of trees, so I can
tell my lands apart and find them again — without being forced to guess and without those details leaving my device.

## Acceptance scenarios

### 1. A v1 store still opens

Given a device whose `lands-v1.txt` holds `land-store-v1` records, when the repository reads it, then every record
still loads unchanged with `zone = null`, `variety = UNKNOWN`, `varietyOther = null` and `treeCount = null`, no
value is invented, and the next write emits `land-store-v2` for the whole file.

### 2. New records require a zone

Given the add form, when the name is filled but the zone is blank, longer than 80 characters, or only spaces, then
saving writes nothing, shows `Escribe la zona o paraje del terreno.` (or the length message), and returns focus to the
zone field; a valid zone is trimmed and persisted with the record.

### 3. A legacy land stays readable and needs a zone when edited

Given a stored land without zone, when it is listed and opened for editing, then the list shows no zone line and the
form opens with an empty zone; saving without one is blocked exactly as in scenario 2, and saving with one keeps the
same id, `createdAtEpochMillis` and stored notes.

### 4. Optional measurements stay optional and unknown

Given a form with only name and zone, when it is saved, then `variety` is `UNKNOWN`, `varietyOther`, `areaHectares`
and `treeCount` are `null`; the list shows `Variedad: No lo sé`, omits the surface and tree lines and never renders a
zero or a guess; reopening the land in edit prefills exactly the stored values.

### 5. Measurements and free text are validated, never guessed

Given the new input fields, when the person enters letters, a negative or non-finite surface, zero/negative/decimal/overflowing tree counts, an over-long variety text, or selects `Otra` with no
text, then saving is blocked with the matching plain-Spanish message and the raw text stays on screen; when they enter
`1,5`, `1.5`, `0,75`, `85` or `1,234`, the value is stored as 1.5, 1.5, 0.75, 85 or 1.23 (a surface with three or more
decimals is rounded to the stored two decimals, never rejected for precision).

### 6. Variety choices are the approved shortlist

Given the variety selector, when it opens, then the options are `Picual`, `Hojiblanca`, `Picudo`, `Lechín de Sevilla`,
`Arbequina`, `Manzanilla`, `Gordal`, `Mezcla de variedades`, `Otra` and `No lo sé`; choosing `Otra` reveals a short
free-text field (max 40), the custom text is shown in the land details, and `No lo sé` stores `UNKNOWN`.

### 7. New values never leave the device

Given a land with zone, variety, custom variety, surface and tree count, when a land-aware question is encoded, then the
serialized `AskRequest` contains no zone, variety, variety-other, area or tree-count key, and the privacy screen names
those values as saved only on this device and not sent.

### 8. The field decision is superseded explicitly

Given the accepted 2026-10-20 decision record, when this feature is finished, then a dated superseding section is
appended to `land_setup_fields_decision.md` (the old text is not rewritten) stating the product decision, the field
rules, the absence of new target-user evidence, and the owner features affected.

### 9. Scope stays inside the land data slice

Given this feature, when the diff is reviewed, then no backend, contract, knowledge, chat payload, navigation,
theme, token or unrelated screen changed, and the only visual regressions re-recorded are the land rows and shell
frames whose fixtures now carry the new values.

## Technical approach

- **Model** (`lands/Land.kt`): add `zone: String?` to `Land` (null only for legacy rows) and `zone: String` to
  `LandDraft`; add `variety: LandVariety`, `varietyOther: String?`, `treeCount: Int?`; keep `areaHectares` and `notes`.
  `enum class LandVariety { UNKNOWN, PICUAL, HOJIBLANCA, PICUDO, LECHIN_DE_SEVILLA, ARBEQUINA, MANZANILLA, GORDAL, MIXED, OTHER }`.
- **Pure helpers** (new `lands/LandFields.kt`): `ZONE_MAX_LENGTH = 80`, `VARIETY_OTHER_MAX_LENGTH = 40`, zone
  validity, a `MeasureResult`-style parse for surface (`MeasureResult<Double>`, blank = valid null, comma or dot,
  finite, `>= 0`, rounded to two decimals) and trees (`MeasureResult<Int>`, blank = valid null, ASCII digits,
  `>= 1`), plus `formatHectares` (comma, up to two decimals, no trailing zeros), `formatTreeCount` (plain space for
  thousands) and `areaInputText`. No Compose or platform types.
- **Repository** (`lands/LandRepository.kt`): normalize name, zone (required, trimmed, ≤ 80), optional municipality,
  variety-other (retained only for `OTHER`, required then, ≤ 40), area (finite, ≥ 0, rounded) and trees (≥ 1); write
  `land-store-v2` with
  `id|name|zone|municipality|waterRegime|productionMethod|variety|varietyOther|areaHectares|treeCount|notes|createdAt|updatedAt`;
  decode both headers (v1 = 9 fields as today) with the same escaping and skip-corrupt-record behaviour. The Desktop
  path keeps the `lands-v1.txt` name; contents become v2 and older builds cannot read them (recorded limitation).
- **Forms**: `AddLandState`/`EditLandState` keep raw text for name, zone, variety-other, surface and trees, add
  `showZoneError`, `showVarietyOtherError`, `showAreaError`, `showTreeCountError`, and build a draft only when every
  field is valid. `EditLandState` prefills from the stored `Land` (legacy zone → empty), keeps `preservedNotes` only,
  and never targets another id. `AddLandScreen`/`EditLandScreen` add a zone `OutlinedTextField`, a variety
  `ManijeroDropdownField` (stable option list, enum matched by option index), an `Otra` `OutlinedTextField` shown only
  for `OTHER`, and two `ManijeroMeasureField`s (decimal/whole keyboard). Save requests focus on the first invalid
  field. Existing name/municipality/water/production behaviour stays.
- **Surfaces**: `LandListScreen`'s shared `LandDetails` gains zone/variety/surface/tree lines (omit absent municipality,
  surface and trees; `No lo sé` for unknown variety/water/production); the remove state/screen and the clarification
  chooser carry the same known values. No chips, search, summary or row restyle.
- **Privacy**: update `privacy_local_body_2` and `privacy_sent_not_sent`; `SHARED_LAND_ATTRIBUTES` stays the pinned
  three sendable dimensions and `LandDataDisclosureTest` grows an explicit assertion that the five new values never
  appear in the encoded request.
- **Screenshots**: update `ScreenshotFixtures.twoLands` with zone/variety/measures and re-record only
  `land_list_light`, `land_list_light_phone` (Desktop) / `land_list_light` (Android) and `app_shell_lands_rail_dark`
  (both hosts); every other golden stays byte-identical.
- **Decision record**: append the dated superseding section to `land_setup_fields_decision.md`; no past acceptance
  record is edited.

## Expected file changes

- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/`: `Land.kt`, `LandRepository.kt`,
  `AddLandState.kt`, `EditLandState.kt`, `RemoveLandState.kt`, `AddLandScreen.kt`, `EditLandScreen.kt`,
  `LandListScreen.kt`, `RemoveLandScreen.kt`.
- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandFields.kt`.
- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` (clarification chooser passes the new
  details) and `shared/src/commonMain/composeResources/values/strings.xml`.
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/` (`LandRepositoryTest`, `AddLandStateTest`,
  `EditLandStateTest`, `EditLandRepositoryTest`, `RemoveLandStateTest`, `LandListStateTest`,
  `RemoveLandRepositoryTest`) and `privacy/LandDataDisclosureTest.kt`; **update** the Desktop store tests under
  `shared/src/jvmTest/.../lands/` and `screenshots/ScreenshotFixtures.kt`.
- **Add** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandFieldsTest.kt` and
  `LandStoreFormatTest.kt`.
- **Re-record** only the five populated land-list/shell goldens named above.
- **Update** `docs/specs/land_setup_fields_decision.md` (append only), `docs/domain-model.md`, `CONTEXT.md`,
  `DESIGN.md`, `CONSTRAINTS.md`, `docs/risks-and-open-questions.md`.
- After acceptance: `feature_list.json`, `PROGRESS.md`, `docs/progress/current-state.md`,
  `docs/progress/session-log.md`, this appendix and the acceptance record.
- **Not changed:** `chat/LandContextBuilder.kt`, `chat/*` payload types, `contracts/`, `backend/`, `knowledge/`,
  `privacy/LandDataDisclosure.kt`'s shared attributes, theme/design-system components, navigation, Gradle files,
  Android/Desktop entry points and `docs/screenshot-regression.md` capture counts.

## Visual design impact

The new fields reuse the accepted component layer (`ManijeroDropdownField`, `ManijeroMeasureField`) inside the
existing form layout and keep the 720 dp column, 48 dp targets, light/dark and 2× text previews. Required/optional is
said in words in the labels and helper text, never by colour or a bare asterisk. Land rows gain plain detail lines in
the existing `bodyLarge`/`onSurfaceVariant` style, with no new chips, cards, colours or animation; the richer row and
summary treatment stays with `lands_screens_refresh`/`land_search_and_summary`. No new string implies eligibility,
verification, completeness or official status; an absent measure is omitted, never shown as zero.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `docs/specs/land_setup_fields_decision.md` | Append | Dated product decision superseding the 2026-10-20 deferral; never rewrite the accepted record. |
| `docs/domain-model.md` | Update | Add zone, variety/variety-other and tree count; area is now collected; notes stay hidden and unsent. |
| `CONTEXT.md` | Update | Add the zone/parcel and variety terms to the shared glossary. |
| `DESIGN.md` | Update | Record the approved field order, required/optional wording and the local-only rule for measurements. |
| `CONSTRAINTS.md` | Update | Replace the `areaHectares` carry-through rule, and add the v1-read/v2-write, no-inference and never-sent rules. |
| `docs/risks-and-open-questions.md` | Update | Replace the resolved field question with the superseding decision and its missing user evidence. |
| `ARCHITECTURE.md` | Not needed | The change stays inside the existing `shared` land data layer; no module, boundary or data flow changes. |
| `AGENTS.md` | Not needed | Existing routing and operating rules already cover land data and local-only fields. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/*` | Update after implementation and independent acceptance | Keep the board, status and evidence pointers honest. |

## Focused verification

Compiles and tests the land data/forms, verifies the re-recorded goldens and enforces the local-only/field gates.
Read-only apart from Gradle output.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :shared:verifyScreenshots
lands="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/lands"
grep -q 'land-store-v2' "$lands/LandRepository.kt" || { echo "missing v2 writer" >&2; exit 1; }
grep -q 'land-store-v1' "$lands/LandRepository.kt" || { echo "v1 reader was dropped" >&2; exit 1; }
grep -rq 'enum class LandVariety' "$lands" || { echo "missing LandVariety" >&2; exit 1; }
grep -q 'val zone' "$lands/Land.kt" || { echo "missing zone field" >&2; exit 1; }
grep -q 'treeCount' "$lands/Land.kt" || { echo "missing tree count" >&2; exit 1; }
if grep -rnE 'zone|variety|varietyOther|treeCount|areaHectares' "$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt"; then
  echo "a new land field leaked into the chat context builder" >&2
  exit 1
fi
strings="$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml"
for key in add_land_zone_label add_land_zone_help add_land_zone_error add_land_variety_label \
  add_land_variety_other_label add_land_variety_other_error add_land_surface_label add_land_surface_help \
  add_land_surface_error add_land_trees_label add_land_trees_help add_land_trees_error \
  land_list_zone land_list_variety land_list_surface land_list_trees; do
  grep -q "name=\"$key\"" "$strings" || { echo "missing string: $key" >&2; exit 1; }
done
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandFieldsTest.kt" || { echo "missing field tests" >&2; exit 1; }
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandStoreFormatTest.kt" || { echo "missing store tests" >&2; exit 1; }
```
<!-- verify:end -->

The block proves compile, the unit behaviour, the legacy/leave-the-device gates and pixel stability. It cannot judge
form readability with real users, screen-reader output, or whether 2× text keeps every new field usable; those remain
manual and are recorded as limits.

## Appendix

Repository research, the ordered implementation plan, verification plan, evidence to capture and the validator
checklist: [`land_measurement_fields.appendix.md`](land_measurement_fields.appendix.md).
