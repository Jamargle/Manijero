# Validation: `land_measurement_fields`

**Verdict: accept** — 2026-10-25

Independent validation against [`land_measurement_fields.md`](../specs/land_measurement_fields.md),
its [appendix](../specs/land_measurement_fields.appendix.md) checklist,
[`land_setup_fields_decision.md`](../specs/land_setup_fields_decision.md), `CONSTRAINTS.md`,
`DESIGN.md`, `CONTEXT.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md` and
`PROGRESS.md`, in the `land_measurement_fields` worktree (branch `feature/land_measurement_fields`,
base `83e02ba`, accepted HEAD `c229b74`; commits `ef1d1aa` spec, `5edc2b8` implementation,
`c32ba00` + `c229b74` review fixes). No required code fix was needed; five low notes are recorded
below and none of them blocks acceptance.

## What was checked

### Contract scenarios 1–9

1. **A v1 store still opens (scenario 1).** `LandStoreFormat.decode` switches on the header
   (`LandRepository.kt:153-161`); `decodeV1` maps nine fields with `zone = null`,
   `variety = UNKNOWN`, `varietyOther = null`, `treeCount = null`
   (`LandRepository.kt:163-181`). `LandStoreFormatTest` "a v1 store still loads without inventing the
   missing values" (11 field assertions) and "a v1 snapshot is rewritten as v2 on the next write"
   (asserts the `land-store-v2` header, the preserved `createdAtEpochMillis = 1` and the new
   `updatedAtEpochMillis`) pin it.
2. **New records require a zone (scenario 2).** `zoneProblem`/`isValidZone`
   (`LandFields.kt:37-47`) trim first; `normalize` rejects a blank/over-long zone before any write
   (`LandRepository.kt:90`). `AddLandState.SaveClicked` sets `showNameError`/`showZoneError`
   (`AddLandState.kt:105-112`), `toDraftOrNull` returns `null` (`:121-127`), `AddLandScreen` moves
   focus to the first invalid field from the save path (`AddLandScreen.kt:137-153`), the zone
   supporting text switches from help to the plain-Spanish error (`:181-218`,
   `strings.xml:12-13`), and the draft zone is trimmed (`AddLandState.kt:132`). `AddLandStateTest`
   covers blank/whitespace/over-long zones, raw-text retention and the trimmed save.
3. **Legacy land readable, zone required only on edit (scenario 3).** `LandDetails` omits a null or
   blank zone (`LandListScreen.kt:273-275`); `toEditLandState` prefills `zone.orEmpty()`
   (`EditLandState.kt:60-72`); the edit save path blocks exactly like the add form
   (`EditLandState.kt:131-138`, `EditLandScreen.kt:126-136`). `EditLandRepositoryTest`
   "a legacy land without zone requires a zone and keeps its identity notes and area" starts from a
   real `land-store-v1` fixture and asserts the same `id`, `createdAtEpochMillis = 1`, the area and
   the stored notes after the update; `EditLandStateTest` covers the prefill, the block and the
   preserved notes/id for every action.
4. **Optional measurements stay optional (scenario 4).** Blank measures parse to
   `MeasureResult.Valid(null)` (`LandFields.kt:96`, `:120`); the add draft leaves variety `UNKNOWN`
   and the rest `null` (`AddLandState.kt:130-140`); `LandDetails` always renders the variety line,
   renders `No lo sé` for `UNKNOWN` (`LandListScreen.kt:279-285`) and omits absent surface/trees
   (`:286-293`). `AddLandStateTest` "name and zone only land is saved with unknown attributes and
   survives reopening" and `EditLandStateTest` "prefilled_state_mirrors_the_stored_record" pin the
   save and the exact prefill.
5. **Validation, never guessing (scenario 5).** `parseAreaHectares` rejects letters, signs, several
   separators, non-finite values, negatives and `1e3`, and rounds a longer entry
   (`LandFields.kt:94-111`); `parseTreeCount` accepts only ASCII digits ≥ 1 and fits `Int`
   (`:118-125`); `isValidVarietyOther` requires trimmed non-blank ≤ 40 text for `OTHER` only
   (`:53-57`). Raw text is never rewritten on rejection (`AddLandStateTest`, `EditLandStateTest`
   assert the exact typed text after a failed save).
6. **Approved shortlist (scenario 6).** `LAND_VARIETY_OPTIONS` is `Picual`, `Hojiblanca`, `Picudo`,
   `Lechín de Sevilla`, `Arbequina`, `Manzanilla`, `Gordal`, `Mezcla de variedades`, `Otra`,
   `No lo sé` (`LandFields.kt:17-28`), pinned by `LandFieldsTest` "variety options use the approved
   shortlist order" (order plus `LandVariety.entries` completeness). The `Otra` field appears only
   for `OTHER` (`AddLandScreen.kt:242-279`), the custom text is shown in the details
   (`LandListScreen.kt:279-284`) and `No lo sé` stores `UNKNOWN`.
7. **Values never leave the device (scenario 7).** `chat/`, `contracts/`, `backend/` and
   `knowledge/` have **zero** changed files vs `83e02ba` (`git diff --stat` empty for those paths);
   `MinimalLandContext` keeps `id`, `municipality`, `water_regime`, `production_method` only
   (`chat/AnswerService.kt:87-92`) and `LandContextBuilder.kt` mentions no land field. The published
   grep gate for that is in the focused block and passes. `LandDataDisclosureTest` builds a fully
   populated land (zone, `varietyOther`, 12.5 ha, 1200 trees, notes) and asserts the encoded
   `AskRequest` has exactly the three optional keys and contains none of the new names or values
   (`LandDataDisclosureTest.kt:50-114`). `privacy_local_body_2` and `privacy_sent_not_sent` name the
   zone, variety, surface and tree count as saved-only-on-this-device and not sent
   (`strings.xml:119`, `:128`).
8. **Superseded decision (scenario 8).** The `2026-10-20` body of
   `docs/specs/land_setup_fields_decision.md` is unchanged: the diff hunk is
   `@@ -113,3 +113,45 @@`, additions only. The appended section states the product decision, the field
   table, the local-only boundary, the storage change, the absence of new target-user evidence and
   the affected owners; `docs/risks-and-open-questions.md` and `docs/domain-model.md` were updated to
   match.
9. **Scope (scenario 9).** `git diff --stat 83e02ba...HEAD` touches 40 files: the nine land screens/
   states plus the new `LandFields.kt`, `App.kt`, `strings.xml`, eleven test files,
   `ScreenshotFixtures.kt`, six durable docs, the two feature specs, `feature_list.json` and five
   PNGs. No `chat/`, `contracts/`, `backend/`, `knowledge/`, `design/`, `theme/`, navigation,
   entry-point, Gradle or `docs/screenshot-regression.md` change. Exactly five goldens changed
   (`git diff --name-status | grep png`): Desktop `land_list_light`, `land_list_light_phone`,
   `app_shell_lands_rail_dark`; Android `land_list_light`, `app_shell_lands_rail_dark`. No image was
   added or deleted, and `:shared:verifyScreenshots` passed all 18 Desktop and 14 Android captures,
   so the other 27 PNGs are byte-identical.

### Contract consistency of the surface-rounding resolution

The original contradiction (scenario 5 rejecting 3+ decimals while the technical approach rounded) is
resolved as **"round a longer surface to the stored two decimals, never reject for precision"**, and
every artifact now says the same thing:

- Code: `parseAreaHectares` has no `fraction.length > 2` rejection (`LandFields.kt:94-111`) and
  `roundHectares` rounds, with a guard that keeps huge finite values finite
  (`LandFields.kt:128-134`, added in `c229b74`).
- Tests: `LandFieldsTest.kt:71-74` asserts `1,234` → 1.23, `1.234` → 1.23, `1,236` → 1.24,
  `1,999` → 2.0; `AddLandStateTest.kt:179-185` asserts the same through the form;
  `LandRepositoryTest` "areas are rounded to two decimals".
- Contract: scenario 5 (`land_measurement_fields.md:78-81`) and the technical approach (`:112-116`)
  now agree; `CONSTRAINTS.md` states it operationally ("store at most two decimals by rounding a
  longer entry … instead of refusing a plausible measurement"); the appendix checklist
  (`land_measurement_fields.appendix.md:262-263`) and the decision record's surface row agree.

### Legacy compatibility, escaping and corrupt records

- v1 reads and v2 writes with the documented 13-field layout (`LandRepository.kt:118-151`); the
  Desktop path still resolves `lands-v1.txt` (`desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt:17`)
  and the three Desktop store tests still exercise that real file name on temp directories.
- Escaping is unchanged and covers `%`, `|`, `\n`, `\r` in both directions
  (`LandRepository.kt:239-249`); `LandStoreFormatTest` round-trips an id/name/zone/notes containing
  `|`, `%` and newlines and asserts the encoded line still has exactly 13 fields.
- Corrupt handling is conservative: a wrong field count, an unknown enum, a `NaN` area and a
  non-numeric tree count are skipped whole while valid neighbours survive
  (`LandStoreFormatTest.kt:118-141`); `v1`/`v2` headers never decode each other's line shape
  (`:143-161`); an unknown header reads as no records (`:10-16`). The shared `land()` guard also
  rejects a non-finite v1 area (`LandRepository.kt:219-221`).

### Local-only privacy boundary and logging

No new field reaches `AskRequest`/`MinimalLandContext`/`LandContextBuilder` (see scenario 7), the
pinned `SHARED_LAND_ATTRIBUTES` list is untouched (`privacy/LandDataDisclosure.kt` unmodified), and
the repository has **no** logging call at all in `commonMain`/`androidMain`/`jvmMain`
(`grep -rn "println|Log|System.out|NSLog|Logger"` → no matches), so no zone, variety, surface or tree
count can be written to a log. Nothing new crosses the network.

### Code review beyond the tests

Read as a reviewer, not just as a test run: required values are gated in one place
(`normalize`, `LandRepository.kt:88-111`) and the forms build a draft only when every field is valid
(`AddLandState.kt:121-140`, `EditLandState.kt:149-167`), so no screen can write a record the store
would reject except through a genuine store failure, which the `App.kt` save paths turn into
`SaveFailed`/`WRITE_FAILED`/`LAND_MISSING` without claiming success (`App.kt:370-440`). The edit
state can only ever target its own `landId` and keeps `preservedNotes` (`EditLandState.kt:60-72`,
pinned for every action by `EditLandStateTest` "field_actions_never_change_the_target_id…"). Variety
selection maps back from the displayed label to the enum by index against the same stable list
(`AddLandScreen.kt:228-238`), and stale custom text is dropped when the variety changes
(`LandFields.kt:63-64`). Absence stays absence end to end: blank form fields → `null`/`UNKNOWN` →
omitted lines → empty prefill. Escaping covers the store delimiter, and no user text is interpolated
into anything but Compose `Text`.

## Verification (independently run in this worktree)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature land_measurement_fields` | **exit 0** — `BUILD SUCCESSFUL`; `:shared:jvmTest` 25 classes / **245 tests / 0 failures**; `verifyDesktopScreenshots` 5 classes / 18 goldens matched; `verifyAndroidScreenshots` 5 classes / 14 goldens matched; every static gate of the published block passed (v2 writer, v1 reader, `LandVariety`, `zone`/`treeCount` in `Land.kt`, no land field in `LandContextBuilder.kt`, all fourteen string keys, both new test files present) |
| `./scripts/init.sh --fast` | **exit 0** — `Fast tier passed`; contract examples `Validated 2 request and 3 response examples`; source-catalog valid; **all 9 offline checks passed**; `:shared:jvmTest` up to date (already executed in the focused tier, same inputs); `[skip] Backend unit tests: pytest is not installed.` with the virtualenv recipe — no backend file changed |
| `./scripts/init.sh --verify` | **exit 0** — fast tier passed, then `BUILD SUCCESSFUL` for the full tier; `:androidApp:assembleDebug` wrote a fresh debug APK during this run, while the already-current Android host test and Desktop build tasks stayed up to date (same inputs) |
| `:shared:testAndroidHostTest` (results dir deleted, task rerun) | `BUILD SUCCESSFUL` — the task was restored from the local build cache on identical inputs; **21 classes / 231 tests / 0 failures**, including `LandFieldsTest` 10, `LandStoreFormatTest` 8, `AddLandStateTest` 14, `EditLandStateTest` 12, `EditLandRepositoryTest` 7, `LandRepositoryTest` 6, `RemoveLandStateTest` 8, `RemoveLandRepositoryTest` 5, `LandDataDisclosureTest` 3 |
| `git diff --name-status 83e02ba...HEAD \| grep png` | exactly the five contract-named PNGs, `M` only, nothing added or deleted |
| `git status --porcelain` | clean tree at `c229b74`; validator wrote no product, test, screenshot or contract file |

Per-class JVM counts match the implementer's claims exactly (`LandFieldsTest` 10,
`LandStoreFormatTest` 8, `LandRepositoryTest` 6, `AddLandStateTest` 14, `EditLandStateTest` 12,
`EditLandRepositoryTest` 7, `RemoveLandStateTest` 8, `RemoveLandRepositoryTest` 5,
`LandDataDisclosureTest` 3), so the self-reported evidence was accurate rather than merely copied.

The five re-recorded goldens were opened and reviewed independently: both populated rows show
`Zona`, `Variedad` and the known `Superficie`/`Olivos` lines, `La Loma` omits the absent
surface/tree lines and shows its custom `Royal de Cazorla`, the shell rail keeps its layout with the
taller rows, and the phone capture is the same scrollable list (the second card extending past the
viewport is pre-existing scroll behaviour, and the pre-existing whitespace under the detail lines is
unchanged from the base capture).

## Findings

No blocking or required-fix finding. Low notes, recorded rather than silently accepted:

- **L1 — stale KDoc in product code (low).** `RemoveLandScreen.kt:40` still says the confirmation
  "shows no id, area, or notes", but the confirmation now renders `Superficie:` through the shared
  `LandDetails` (`RemoveLandScreen.kt:86-96`). Behaviour is correct and matches the contract; only
  the comment was wrong. **Fixed after validation in `d6022d5`** ("shows no id or notes"); comment
  only, no behaviour, copy or contract defect.
- **L2 — appendix evidence overstated preview coverage (low).** The appendix
  (`land_measurement_fields.appendix.md:244-245`) said the forms were checked with "previews (light,
  dark, 2×, compact, wide)". The two forms gained/kept light, compact, wide, 2× and 320 dp-2×
  previews, but no `darkTheme = true` preview exists for any lands screen
  (`AddLandScreen.kt:496-676`, `EditLandScreen.kt:458-666`); dark coverage comes from the
  `landListEmptyDark`/`app_shell_*_dark` goldens and from the accepted design components' own dark
  previews. This is a pre-existing pattern for these screens, not a regression, and the contract's
  "keep … light/dark and 2× text previews" is satisfied at the component level. **Fixed after
  validation in `d6022d5`** by correcting the appendix sentence to "light, large-font 2×, compact,
  wide".
- **L3 — absurd surface values cannot round-trip through the edit form (low, theoretical).**
  `formatHectares` falls back to `Double.toString()` at `|value| ≥ 1e12` (`LandFields.kt:144`), so a
  stored area that large would be prefilled as `1.0E12`, which `parseAreaHectares` rejects as
  letters. It is reachable only by typing 13+ digits, shows `Superficie: 1.0E12 ha` in the row, and
  the person can clear or correct it, so no ordinary land is affected. If the owner wants the
  invariant "every stored value is re-saveable unchanged", add a magnitude cap to the parse/normalize
  step (a one-line `require` plus a test).
- **L4 — the rounding rule is not stated where a person reads it (low).** The surface helper only
  says "Puedes usar coma o punto. Por ejemplo, 1,5." (`strings.xml:31`), so `1,234` silently becomes
  `1,23`. That is the accepted resolution (never reject, store two decimals) and `CONSTRAINTS.md`
  states it, but the decision record and `docs/domain-model.md` only say "at most two decimals",
  which reads as a rejection rule. Suggested follow-up outside this feature: add "se guarda con dos
  decimales" to the helper copy and the "rounds a longer entry" wording to those two docs.
- **L5 — verification gap, not a defect.** The payload boundary is test-pinned, but the privacy copy
  itself (`strings.xml:119`, `:128`) is only code-reviewed; nothing in the suite would fail if a
  future edit dropped "la zona o paraje" from that sentence. Worth a copy assertion when the next
  disclosure-touching feature lands.

## Honest limits

Confirmed as recorded, not silently ignored:

- The appendix's "Manual/observable limits" section
  (`land_measurement_fields.appendix.md:241-250`), the contract's closing paragraph
  (`land_measurement_fields.md:218-220`) and the decision record's "Evidence and limits" all state
  that there is **no** interactive Desktop/emulator walkthrough, **no** screen-reader audit, **no**
  measured 2×-text device check, **no** real `land-store-v1` → v2 upgrade, **no** downgrade and
  **no** backup/restore exercise, and **no** new target-user evidence for the required zone or the
  ten-option variety list.
- I independently confirm those limits are real in this environment: this repository has no
  interactive UI harness, so the user-flow evidence is the pure state/repository tests, the five
  reviewed host goldens and the form previews. Focus order, the polite live regions and the
  scroll-to-focus behaviour are code-reviewed only; they are not observed with assistive
  technology.
- The backend pytest tier could not run (`pytest` absent; the fast tier prints the recipe and skips),
  and no backend file changed. Android/Desktop evidence is host renders plus a debug APK build; no
  device, iOS or Desktop-OS matrix was exercised.
- Product-owner sign-off on the re-recorded goldens and the long-standing low-digital-confidence
  comprehension check remain outstanding manual items, as `PROGRESS.md` says.

## Security

Portable, feature-scoped review: **no finding.** No new network call, permission, entry point,
dependency, module or serialized payload field; the new strings are user text rendered through
Compose `Text` and escaped against the store's `|`/`%`/newline delimiters before persistence; no
logging statement exists in the client source sets, so no land value can leak to a log; the store
stays a single local file/SharedPreferences pair with unchanged file names; the disclosure screen
continues to name exactly the three sendable dimensions and now names the new values as
device-only. The only user-visible risk surface is input validation, which fails closed (nothing is
written when any field is invalid, and a rejected field keeps its raw text for correction).

## Documentation and harness state

- `CONSTRAINTS.md` gains a "Land fields and storage" block (required zone, v1-read/v2-write,
  no-inference, surface/tree rules) and its "Land editing" and disclosure rules were updated rather
  than duplicated; `DESIGN.md` records the field order, the obligatory/optional wording and the
  local-only rule; `CONTEXT.md` adds zone/variety/surface/tree-count terms;
  `docs/domain-model.md` lists the new fields with their required/optional rules and drops the
  "collect only if an MVP use case needs it" area line; `docs/risks-and-open-questions.md` replaces
  the resolved field question with the superseding decision and adds the "longer setup for
  low-confidence users" risk.
- `ARCHITECTURE.md` and `AGENTS.md` are correctly untouched (no module or boundary change), and
  `docs/screenshot-regression.md` keeps its 18 Desktop / 14 Android capture counts.
- The focused verification block in the contract is accurate and still runs: every static gate it
  publishes passes against the current sources, and it does not depend on a long-running process.

## Handoff

- `feature_list.json`: `land_measurement_fields` is `accepted`.
- `PROGRESS.md`: added to the accepted set, the product-shape sentence now describes the
  `land-store-v2` writer with the `land-store-v1` reader, and the feature's limits (no device
  walkthrough, no screen-reader/2× audit, no real v1→v2 upgrade or downgrade, backend pytest skipped,
  product-decision fields without user evidence) are recorded.
- `docs/progress/current-state.md`: the Lands paragraph now names the v2 store and the new fields.
- `docs/progress/session-log.md`: one pointer line added.
- Next dependent feature: `land_search_and_summary` (then `lands_screens_refresh`), which can build
  on the new zone/variety/surface/tree-count data without new storage work.
- Recommended follow-ups are the five low notes above; none of them changes user-visible behaviour
  today.
