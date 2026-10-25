# Appendix: `land_search_and_summary`

Planning record for [`land_search_and_summary.md`](land_search_and_summary.md). The contract is the
bounded implementation/validation read; this appendix keeps the repository research, the ordered plan,
the verification detail, the exact copy inventory and the raw evidence.

## Repository research

**Base commit.** The worktree's git metadata lives outside this sandbox, so the exact `HEAD` hash could
not be read here; the research is a file-level inspection of this worktree on 2026-10-25, which starts
from the accepted `land_measurement_fields` tip (`344d902`, follow-up `204d024`, per
[`docs/validations/land_measurement_fields.md`](../validations/land_measurement_fields.md)). Every claim
below names the file that was read.

### Land list surface and state

- `lands/LandListState.kt` (35 lines): `data class LandListState(lands, loadFailed)` with `isEmpty` as a
  computed property, `sealed interface LandListAction { LandsLoaded, LoadFailed, ReloadClicked }` and a
  pure `reduce`. No search, no summary, no Compose types.
- `lands/LandListScreen.kt` (597 lines): one `Surface` + scrolling `Column` + 720 dp column
  (`private val ContentMaxWidth`), `headlineMedium` title (`chat_home_lands`),
  `land_list_description`, an optional confirmation `Text` with `LiveRegionMode.Polite`, then a
  `when` over `loadFailed` / `isEmpty` / rows, then a full-width Add `Button` (or `Reintentar` in the
  failure state) at the **bottom**. The empty state is a single `bodyLarge` sentence
  (`land_list_empty`) plus that bottom button. `private fun LandRow` renders name + `internal fun
  LandDetails` + full-width `Editar`/`Eliminar` `TextButton`s with per-land `contentDescription`.
  Twelve `@Preview`s (empty, two lands, duplicate names, many lands, long text, load failure, just
  saved/updated/removed, compact 320 dp, wide 900 dp, 2× text) plus a private `previewLand` helper, all
  of which must pass the new `onQueryChange` argument.
- `lands/LandDetails` is shared with `RemoveLandScreen` and the clarification chooser in `App.kt`; it
  renders zone, municipality, variety (custom `Otra` text), surface/trees only when known, water,
  production, and `No lo sé` for unknown enums. **Rows are out of scope here.**
- `App.kt` owns the only list state: `var landListState by remember { mutableStateOf(
  initialLandListState(landRepository)) }` (line 226), the guarded `readLands` (lines 252-263) that folds
  `LandsLoaded`/`LoadFailed` after `ReloadClicked`, `openSection` re-reading on tab entry (lines 275-285)
  and `readLands()` after create/update/delete (lines 384, 420, 461) before returning to
  `AppDestination.LandList`. `LandListScreen` is rendered at lines 349-368 with
  `onAddLand`/`onEditLand`/`onRemoveLand`/`onRetry`.
- `commonTest/.../AppLaunchTest.kt` compares `initialLandListState(...)` with `LandListState()`; adding a
  defaulted `query` keeps those assertions valid.
- `commonTest/.../lands/LandListStateTest.kt` (6 tests) covers empty/loaded/failed/reload/unicode order.
  No search or summary test exists.

### Pure helpers already available (reuse, do not duplicate)

- `lands/LandFields.kt`: `formatHectares(Double)` (comma, ≤ 2 decimals, trims zeros, rounds with
  `roundHectares`), `roundHectares(Double)`, `formatTreeCount(Int)` (plain-space thousands grouping),
  `areaInputText`, `parseAreaHectares`, `parseTreeCount`, `LAND_VARIETY_OPTIONS`, zone/variety-other
  validation. No Compose imports.
- `lands/Land.kt`: `Land(id, name, zone, municipality = null, waterRegime, productionMethod, variety,
  varietyOther = null, areaHectares = null, treeCount = null, notes = null, createdAtEpochMillis,
  updatedAtEpochMillis)`; `areaHectares: Double?` and `treeCount: Int?` are `null` when the person did
  not provide them; `zone` and the `createdAtEpochMillis`/`updatedAtEpochMillis` keys are required;
  `varietyOther` is only populated for `LandVariety.OTHER`. `LandVariety` has `OTHER` (custom text) and
  `UNKNOWN`; `WaterRegime` and `ProductionMethod` have `UNKNOWN` and `MIXED`; every enum value has an
  existing `StringResource` label (`add_land_water_*`, `add_land_production_*`, `add_land_variety_*`,
  `add_land_unknown`), which is what `LandSearchLabels` has to carry.
- `lands/LandRepository.kt`: `list()` returns records in stored order; nothing here needs to change.

### Design components to adopt (all `internal`, presentational, preview-backed)

- `design/ManijeroStatCard.kt`: `ManijeroStatCard(label, value, supporting, modifier)` — `supporting`
  has **no default** on purpose ("a card cannot render a bare number without saying what it is and how
  complete it is"), and the component never formats or totals.
- `design/ManijeroFields.kt`: `ManijeroSearchField(value, onValueChange, label, clearDescription,
  modifier, placeholder)` — decorative leading magnifier, 48 dp named clear `IconButton` that reports
  `""`, and no filtering; `ManijeroDropdownField`/`ManijeroMeasureField` are unrelated here.
- `design/ManijeroEmptyState.kt`: `ManijeroEmptyState(title, body, action)` — decorative
  `ManijeroOliveBranch` with no semantics, real heading, exactly one caller-supplied action slot.
- `design/ManijeroSectionHeader.kt`: optional `description`, `heading` only when asked.
- `design/ManijeroCard.kt`: four tones; not clickable; adds no semantics. `ManijeroCallout` marks its
  text block as a polite live region, which is why the no-results panel uses a plain card instead.
- `design/ManijeroScreen.kt`: declares `internal val WideWindowBreakpoint = 840.dp` — the accepted
  responsive breakpoint to reuse for the summary grid, so no new constant/token is added. Measure it on
  the **window** (a `BoxWithConstraints` around the padded content): the screen's inner content column is
  capped at 720 dp, so a breakpoint read inside it could never reach 840 dp and the three-column branch
  would never render. The screen frame itself (`ManijeroScreen`) is **not** adopted here; that is
  `lands_screens_refresh`.
- `theme/ManijeroTokens.kt`: `ManijeroSpacing`, `ManijeroShapes`, `ManijeroLayout`, `ManijeroIconSize` —
  no new token is needed.

### Enum labels live in `strings.xml`, not in Kotlin

- `AddLandScreen.kt:483` declares `internal fun landVarietyLabel(variety): StringResource`;
  `LandListScreen.kt:319-332` declares private `waterRegimeLabel`/`productionMethodLabel`
  `StringResource` mappers. Labels are `StringResource` values resolved by `stringResource` during
  composition (`add_land_variety_*`, `add_land_water_*`, `add_land_production_*`, `add_land_unknown`).
- Consequence: a pure `filterLands` **cannot** read them. Hence `LandSearchLabels` (three
  `Map<Enum, String>` parameters) resolved once by the screen from
  `WaterRegime.entries` / `ProductionMethod.entries` / `LandVariety.entries`; the pure file owns no copy,
  so the CONSTRAINTS rule that user-facing strings come from `strings.xml` still holds.

### Strings, plurals and copy

- `shared/src/commonMain/composeResources/values/strings.xml` (153 lines) uses only `<string>`; there is
  **no** existing `<plurals>` entry and no `pluralStringResource` call in the repo. Compose Multiplatform
  is `1.12.1` (`gradle/libs.versions.toml`), so `<plurals>`/`Res.plurals` is expected to work; the
  documented fallback for the six captions is a `<key>_one`/`<key>_other` plain-string pair chosen by
  `if (denominator == 1)`, and the tree value is a plain pair regardless because its total is a `Long`.
- Existing land-list copy: `land_list_description`, `land_list_empty` (mentions `«Añadir terreno»`; retired
  by this feature in favour of the empty-state heading plus a purpose-written body),
  `land_list_add`, `land_list_*` detail labels, `land_list_load_failed`, `land_list_retry`,
  `land_list_edit*`, `land_list_remove*`.
- `docs/design/ui-refresh-plan.md` §7.7 fixes the key areas and §5.3/§5.4 fix the approved Spanish
  wording reused here; §3.7 fixes the copy rules (`tú`, no jargon, no "verificado"/"oficial").

### Screenshot machinery

- Desktop: `shared/src/jvmTest/kotlin/.../screenshots/LandListScreenshotsTest.kt` (4 captures:
  `land_list_light`, `land_list_light_phone`, `land_list_empty_dark`, `land_list_empty_dark_phone`) and
  `AppShellScreenshotsTest.kt` (`app_shell_lands_rail_dark`, 900×1000 dark, shell around
  `LandListScreen(ScreenshotFixtures.twoLands)`). Sizes come from `ScreenshotTestSupport`
  (`LAND_WIDTH=900`, `LAND_HEIGHT=1000`, `EMPTY_LAND_HEIGHT=800`, `PHONE_WIDTH=360`, `PHONE_HEIGHT=800`).
- Android host: `LandListAndroidScreenshotsTest` (`land_list_light`, `land_list_empty_dark`) and
  `AppShellScreenshotsTest.appShellLandsRailDark`, rendered by Robolectric with pinned qualifiers.
- Fixtures: `shared/src/commonTest/kotlin/.../screenshots/ScreenshotFixtures.kt` (`twoLands`, `noLands`).
- `:shared:jvmTest` and `:shared:testAndroidHostTest` exclude `com.jamarglex.manijero.screenshots.*`;
  `:shared:verifyScreenshots` aggregates both read-only suites; `recordScreenshots` /
  `recordDesktopScreenshots` / `recordAndroidScreenshots` re-record, and the accepted procedure is to
  filter with `--tests` so untouched goldens are not rewritten (`docs/screenshot-regression.md`, and the
  `land_measurement_fields` evidence used exactly that).
- `docs/screenshot-regression.md` states 18 Desktop / 14 Android captures (32 PNGs) before this
  feature; with the two capture states per host it becomes 20 Desktop and 16 Android (36 PNGs).

### Harness

- `scripts/init.sh`: `--feature <id>` extracts the shell body between `<!-- verify:start -->` and
  `<!-- verify:end -->` in the spec, writes it to a temp file and runs it with `bash -euo pipefail`, with
  `$REPO_ROOT` set for the block; `--fast` runs `:shared:jvmTest`, contract examples, backend pytest
  (skipped when absent) and the nine offline evaluators; `--verify` adds `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug` and `:desktopApp:build`.
- No UI/E2E harness exists for typing in a field or for screen-reader output: interaction evidence is the
  pure tests plus the goldens and previews.

### Unknowns / honest gaps

- No target-user evidence that a summary of annotated totals is understood as "only what I wrote", or
  that the search wording suggests the right fields. Both are approved product decisions, not findings.
- The no-results golden proves one host render of one appearance, not that the panel is understandable.
- `filterLands` folds `ñ → n`, so `peña` and `pena` match each other; accepted by the plan (§7.5) and
  recorded as a deliberate convenience, not a ranking rule.

## Implementation plan and tasks

Ordered; each task ends with its check. Copy/exact strings are listed below the tasks.

1. **Summary** (P1-10): add `lands/LandSummary.kt` (`LandSummary`, `summarizeLands`) using
   `roundHectares` for the surface sum and a `Long` accumulator for trees; `null` totals exactly when the
   known count is `0`. Check: `LandSummaryTest` — empty list, partial, all known, rounding
   (`0.1 + 0.2`), a single land, a filtered subset, and "no value is ever zero".
2. **Formatter reuse**: widen `lands/LandFields.kt`'s `formatTreeCount` to `Long` and keep the `Int`
   overload delegating; no other formatter. Check: existing `LandFieldsTest` still passes and gains
   `Long` cases (`1 285`, `1 200 000`) through the same grouping implementation.
3. **Search** (P1-11): add `lands/LandSearch.kt` (`LandSearchLabels`, `foldForSearch`, `filterLands`) as
   specified in the contract. Check: `LandSearchTest` — accents/ñ/uppercase, punctuation and emoji as word
   separators (including punctuation-only and emoji-only behaving like a blank query), multiple words in
   any order, blank and whitespace query, no match, id/notes/timestamp excluded, numeric measures excluded
   (`85`, `1,5`, `2,5`), custom `Otra` text, every resolved enum label, order preserved, and a repeated
   name staying two results.
4. **State**: add `query` and `LandListAction.QueryChanged` to `lands/LandListState.kt`, keeping
   `LandsLoaded`/`LoadFailed`/`ReloadClicked` bodies — they already construct a fresh
   `LandListState(...)`, which is what makes every read start with a blank query; do not turn them into
   `copy(...)`. Check: `LandListStateTest` — typing keeps lands/order, a load after a query clears it, a
   failure clears it, reload clears it, `isEmpty` still means "no saved land" (not "no match").
5. **Screen** (P1-12/P1-13): rewrite the content branches of `lands/LandListScreen.kt` (title, empty
   state, summary section, search, add action, rows/no-results), add `onQueryChange` (no default), build
   `LandSearchLabels` from the existing label mappers, and add/adjust previews (empty, populated,
   filtered, no results, 2× text, compact, wide). Keep row, `LandDetails`, confirmation and failure
   rendering unchanged. Check: previews render (including the `1 olivo` singular value and a `Sin datos`
   card); jvmTest compiles; the component gates pass.
6. **Copy**: add the exact strings and `<plurals>` below to `strings.xml`, and delete the retired
   `land_list_empty` with its import. Check: the string/plurals gate in the focused block; a
   `grep -rn land_list_empty` over `shared/src` returns nothing; read every string once for plain Spanish
   (`tú`, no jargon, no "oficial").
6b. **Plural rendering check**: if `Res.plurals`/`pluralStringResource` is not generated by this Compose
   version, switch the six caption plural keys to paired plain keys named `<key>_one`/`<key>_other`, selected by
   `if (denominator == 1)`, and record the substitution, the keys and the observed text in "Feature
   evidence". The focused gate accepts either shape.
7. **Wiring**: pass `onQueryChange` from `App.kt` through `LandListAction.QueryChanged`; nothing else in
   the composition root changes. Check: no other call site breaks; `AppLaunchTest` unchanged and green.
8. **Fixtures and goldens**: add `ScreenshotFixtures.searchNoResults` and
   `ScreenshotFixtures.searchFiltered`, add the `land_list_search_no_results` and
   `land_list_search_filtered` captures to the Desktop and Android lands screenshot classes (the two
   `AppShellScreenshotsTest` classes only gain the `onQueryChange = {}` argument, no new capture). Pin
   both captures to 900 × 1000 dp on both hosts — the Android methods carry
   `@Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")`, the existing rail-capture pattern — so the
   cards, search field and either the panel or the single matching row share one frame; 360 × 800 would
   push the panel below the fold. Then record with the filtered tasks below and inspect each changed/new
   PNG. Check: `git status` lists exactly the eight re-recorded PNGs plus the four new ones.
9. **Durable docs**: `DESIGN.md`, `docs/domain-model.md`, `CONTEXT.md`, `CONSTRAINTS.md`,
   `docs/risks-and-open-questions.md`, `docs/screenshot-regression.md` per the contract table. Check:
   `ARCHITECTURE.md`, `AGENTS.md`, `docs/specs/land_list.md` and `docs/design/ui-refresh-plan.md` are
   untouched (`git status`).
10. **Verify and record**: run the focused block, then `--fast` and `--verify`; append the evidence
    section; after independent acceptance update `feature_list.json`, `PROGRESS.md`,
    `docs/progress/current-state.md`, `docs/progress/session-log.md` and write
    `docs/validations/land_search_and_summary.md`.

### Exact copy inventory (`strings.xml`)

| Key | Text |
|---|---|
| `land_summary_title` | `Resumen` |
| `land_summary_scope_all` | `Cuenta lo que has anotado en los terrenos guardados.` |
| `land_summary_scope_filtered` | `Cuenta solo lo que has anotado en los terrenos que coinciden con la búsqueda.` |
| `land_summary_count_label` | `Terrenos guardados` |
| `land_summary_surface_label` | `Superficie anotada` |
| `land_summary_surface_value` | `%1$s ha` |
| `land_summary_trees_label` | `Olivos anotados` |
| `land_summary_no_data` | `Sin datos` |
| `land_list_empty_title` | `Aún no tienes terrenos añadidos` |
| `land_list_empty_body` | `Cuando guardes uno, verás aquí lo que has anotado.` (replaces `land_list_empty`, which is deleted with its import; the screen is its only reference) |
| `land_search_label` | `Buscar terreno` |
| `land_search_hint` | `Buscar por nombre, municipio o tipo…` |
| `land_search_clear` | `Borrar la búsqueda` |
| `land_search_no_results` | `No hay terrenos que coincidan con la búsqueda.` |
| `land_summary_trees_value_one` | `%1$s olivo` |
| `land_summary_trees_value_other` | `%1$s olivos` |
| plurals `land_summary_count_caption` | one: `Guardado en este dispositivo.` · other: `Guardados en este dispositivo.` |
| plurals `land_summary_count_caption_filtered` | one: `%1$d de %2$d terreno guardado` · other: `%1$d de %2$d terrenos guardados` |
| plurals `land_summary_surface_caption` | one: `%1$d de %2$d terreno con superficie` · other: `%1$d de %2$d terrenos con superficie` |
| plurals `land_summary_surface_caption_filtered` | one: `%1$d de %2$d terreno encontrado con superficie` · other: `%1$d de %2$d terrenos encontrados con superficie` |
| plurals `land_summary_trees_caption` | one: `%1$d de %2$d terreno con olivos` · other: `%1$d de %2$d terrenos con olivos` |
| plurals `land_summary_trees_caption_filtered` | one: `%1$d de %2$d terreno encontrado con olivos` · other: `%1$d de %2$d terrenos encontrados con olivos` |

Plural quantity is always the number the caption itself prints: the count card prints the saved total
(`land_summary_count_caption_filtered`, `%1$d de %2$d terrenos guardados`), while the surface and tree
captions print the number of shown lands, i.e. the match count while a query is active
(`0 de 1 terreno encontrado con superficie`). Only `one`/`other` are needed in Spanish, and `known ≤
denominator` always holds, so `one` renders `0 de 1` or `1 de 1` correctly. The filtered count caption is
the only caption that prints two counts (`%1$d` matches, `%2$d` saved) and it is a verbless noun phrase,
so no verb can agree with the wrong number; the search relation is stated once in the
`land_summary_scope_filtered` line above the cards. The count card
renders `value = matches` with `formatTreeCount(summary.total)` (the one grouping implementation) and the
`x de y` caption over the saved lands, under the `land_summary_scope_filtered` line that states the
search relation. The olive-tree **value** is the exception:
it is a plain `_one`/`_other` pair chosen by `if (treeTotal == 1L)`, because that total is a `Long` and
`pluralStringResource` takes an `Int`; the captions stay `<plurals>` since a land count is an `Int`.

Two deliberate wording choices against the historical plan, recorded so they do not read as drift:
`… terrenos con olivos` replaces the plan's `… terrenos con número de olivos`, staying parallel to
`… terrenos con superficie` and fitting a phone-width card at 200% text; and the number strings carry no
thousands separator of their own because the value is always preformatted by `formatHectares` or
`formatTreeCount`. The empty-state heading, the no-results sentence and the search hint are verbatim from
the plan; the new empty-state body replaces the plan's `Añade tu primer terreno …` placeholder and the old
`land_list_empty` sentence, which repeated the heading.

One search consequence to state plainly: `filterLands` matches the resolved label, so `no lo sé` matches
lands whose water regime, production method or variety is still `UNKNOWN`. That is intended — the person
can find the lands still missing an answer — and it searches no hidden field.

## Verification plan

Automated (published in the contract):

- `./scripts/init.sh --feature land_search_and_summary` — `:shared:jvmTest` (which compiles
  `commonTest`), both host screenshot suites via `:shared:verifyScreenshots`, and the static
  purity/formatter/state/component/chat-boundary/string/plurals/test-file/golden gates.
- `./scripts/init.sh --fast` — shared host tests, contract examples, backend suite (skipped when pytest
  is absent; no backend file changes) and the offline evaluators as a regression guard.
- `./scripts/init.sh --verify` — adds `:shared:testAndroidHostTest`, the debug APK and the Desktop build.
- Recording (only after inspecting the diff, never as a way to hide a regression): filter both record
  tasks so untouched goldens are not rewritten.

  ```sh
  ./gradlew :shared:recordDesktopScreenshots \
    --tests "com.jamarglex.manijero.screenshots.LandListScreenshotsTest" \
    --tests "com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark"
  ./gradlew :shared:recordAndroidScreenshots \
    --tests "com.jamarglex.manijero.screenshots.LandListAndroidScreenshotsTest" \
    --tests "com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark"
  ```

Manual evidence to capture:

- Desktop or emulator: blank query shows the three cards over all lands; typing narrows the list and the
  captions switch to the `encontrado(s)` wording and the count caption to `x de y terrenos guardados`; a
  nonsense query shows the panel and both clear paths; a punctuation-only query keeps the full list and
  the unfiltered wording; clearing restores all rows; the empty store shows the olive branch and only one
  Add action.
- Light, dark and 2× text at 360 dp and at 900 dp: no clipped card, value, caption, field or action; the
  three-column grid only appears on the wide window.
- Keyboard: the search field is reachable, Escape/Tab behave as Material defaults, the clear `IconButton`
  has its announced name; the no-results text is readable by a screen reader (code review only, no audit).
- Visual review of the twelve touched PNGs; product-owner sign-off stays a separate outstanding item.

Not verifiable in this repo: real-user comprehension of the summary or the search wording, screen-reader
output, a real device 2× text measurement, iOS rendering, and any claim that a summary total is a verified
or cadastral measurement.

## Evidence to capture

- Exact commands and exit codes for the three tiers; test counts for `LandSummaryTest`, `LandSearchTest`
  and the updated `LandListStateTest`; total `:shared:jvmTest` count before/after.
- The exact plural strings actually rendered (quote one, other, and a `0 de 1` case; plus all four
  filtered ratios 1-of-1, 1-of-N, N-of-N and 0-of-N) and confirmation that
  `Res.plurals` worked (or the documented fallback).
- `git status` / `git diff --name-status | grep png` output: the eight re-recorded goldens and the four
  new ones only, nothing added or deleted besides those.
- A short note per changed/new golden (what changed and why it is intended), including that
  `app_shell_lands_rail_dark` shows the one-column summary because the shell hands the screen less than
  840 dp, while `land_list_light`, `land_list_search_no_results` and `land_list_search_filtered` at 900 dp
  prove the three-column grid.
- The manual walkthrough notes (host, appearance, text scale, what was observed, what was not).
- Explicit "not verified" lines: no user evidence, no screen-reader audit, no device 2× check, no iOS run.

## Feature evidence

### 2026-10-25 — implementer self-verification (`land_search_and_summary`)

Environment: macOS (darwin), worktree `land_search_and_summary` at base commit `6ac20d0` (merge of
`feature/land_measurement_fields`); JDK and Android SDK from the worktree's ignored `local.properties`.
`feature_list.json` was set to `in_progress` for this feature only; the orchestrator owns the later
status change and the acceptance record.

**Files changed** (working tree, nothing committed):

```text
 M CONSTRAINTS.md
 M CONTEXT.md
 M DESIGN.md
 M docs/domain-model.md
 M docs/risks-and-open-questions.md
 M docs/screenshot-regression.md
 M shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt
 M shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/LandListAndroidScreenshotsTest.kt
 M shared/src/androidHostTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/androidHostTest/screenshots/land_list_empty_dark.png
 M shared/src/androidHostTest/screenshots/land_list_light.png
 M shared/src/commonMain/composeResources/values/strings.xml
 M shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt
 M shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandFields.kt
 M shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt
 M shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt
 M shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandFieldsTest.kt
 M shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandListStateTest.kt
 M shared/src/commonTest/kotlin/com/jamarglex/manijero/screenshots/ScreenshotFixtures.kt
 M shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt
 M shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/LandListScreenshotsTest.kt
 M shared/src/jvmTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark_phone.png
 M shared/src/jvmTest/screenshots/land_list_light.png
 M shared/src/jvmTest/screenshots/land_list_light_phone.png
?? shared/src/androidHostTest/screenshots/land_list_search_no_results.png
?? shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandSearch.kt
?? shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandSummary.kt
?? shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandSearchTest.kt
?? shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandSummaryTest.kt
?? shared/src/jvmTest/screenshots/land_list_search_no_results.png
```

`git status` additionally lists the planner's untracked `docs/specs/land_search_and_summary.md` and
this appendix. `ARCHITECTURE.md`, `AGENTS.md`, `docs/specs/land_list.md`,
`docs/design/ui-refresh-plan.md`, `lands/Land.kt`, `lands/LandRepository.kt`, the add/edit/remove files,
`chat/`, `privacy/`, `theme/`, `design/`, `design/navigation/`, `contracts/`, `backend/`, `knowledge/`,
Gradle files and the platform entry points are untouched (statement from `git status`, not from a
`git status | grep` alone).

**Tier 1 — focused gate**: `./scripts/init.sh --feature land_search_and_summary` → **exit `0`**,
`BUILD SUCCESSFUL in 8s`, 34 screenshot captures passed (`:shared:verifyDesktopScreenshots` 19,
`:shared:verifyAndroidScreenshots` 15), so every re-recorded and new golden matched and every other
golden stayed byte-identical. Every static gate of the published block passed: both pure files exist
and import no Compose/resource type, `summarizeLands`/`filterLands`/`foldForSearch` present, no second
number formatter, `formatHectares(`/`formatTreeCount(` used by the screen, `val query` and
`QueryChanged` in `LandListState.kt`, all four components adopted (`ManijeroStatCard`,
`ManijeroSearchField`, `ManijeroEmptyState`, `ManijeroSectionHeader`; `ManijeroCard` is in the import
list), no search/summary identifier in `chat/`, all sixteen plain keys present, six caption
`<plurals>` entries present, `land_list_empty` gone, both test files present, both new goldens present.

**Tier 2 — no-device gate**: `./scripts/init.sh --fast` → **exit `0`**, `Fast tier passed.`; contract
examples `Validated 2 request and 3 response examples against answer_api_contract`; `[skip] Backend
unit tests: pytest is not installed.` (no backend file changed); `All 9 offline checks passed.`

**Tier 3 — full gate**: `./scripts/init.sh --verify` → **exit `0`**; fast tier passed, then
`:shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build` → `BUILD SUCCESSFUL`,
`:androidApp:assembleDebug` produced the debug APK and `:desktopApp:build` succeeded.

**Test counts** (JUnit XML; the counts were re-read from an executed `:shared:jvmTest --rerun-tasks`
run, `BUILD SUCCESSFUL in 5s`):

| Suite | Before | After | Result |
|---|---|---|---|
| `:shared:jvmTest` (whole suite) | 242 (per `land_measurement_fields`) | **265 / 27 classes** | 0 failures, 0 errors, 0 skipped |
| `LandSummaryTest` (new) | — | 8 | pass |
| `LandSearchTest` (new) | — | 10 | pass |
| `LandListStateTest` | 6 | 10 | pass |
| `LandFieldsTest` | 10 | 11 | pass |
| `:shared:testAndroidHostTest` | — | 251 / 23 classes | 0 failures, 0 errors |

The 23-test delta is exactly `LandSummaryTest` 8 + `LandSearchTest` 10 + four new `LandListStateTest`
cases (query keeps lands and order; a load after a query clears it; a failure clears it; a reload
clears it) + one new `LandFieldsTest` case (the `Long` grouping path, `1 285`, `1 200 000`,
`4 294 967 294`).

**Plural inventory actually rendered.** `Res.plurals` and `pluralStringResource` do work in Compose
Multiplatform 1.12.1, so all six captions ship as `<plurals>` and the documented `_one`/`_other`
fallback was **not** used. The rendered text was read from temporary probe captures
(`TempPluralProbeTest`, `TempScenarioProbeTest`, both deleted and absent from the diff):

- `one` (single land, nothing annotated): count caption `Guardado en este dispositivo.`, surface
  `Sin datos` + `0 de 1 terreno con superficie`, trees `Sin datos` + `0 de 1 terreno con olivos`.
- `other` (three lands, scenario 2): `3` + `Guardados en este dispositivo.`, `2,25 ha` +
  `2 de 3 terrenos con superficie`, `1 285 olivos` + `2 de 3 terrenos con olivos`.
- scenario 3 (three lands, nothing annotated): `Sin datos` + `0 de 3 terrenos con superficie` and
  `Sin datos` + `0 de 3 terrenos con olivos` — never `0 ha` or `0 olivos`.
- filtered (`query = "olivos"`, two saved, one matching): scope `Cuenta solo lo que has anotado en los
  terrenos que coinciden con la búsqueda.`, count `1` + `1 de 2 guardados coinciden con la búsqueda.`
  (first-round text; the 2026-10-25 repair replaced it with `1` + `1 de 2 terrenos guardados`, see the
  repair subsection below), surface `1,5 ha` + `1 de 1 terreno encontrado con superficie`, trees
  `1 olivo` + `1 de 1 terreno encontrado con olivos`.
- The tree **value** pair renders `1 olivo` (one tree) and `1 285 olivos` (many), chosen by
  `if (treeTotal == 1L)`; the `_one` caption is also proven by the `0 de 1` case above, so `known ≤
  denominator` renders correctly.

**Typing and clear paths actually exercised.** A temporary interaction probe
(`TempTypingProbeTest`, 2 tests, both passed, deleted before the final gate) drove the real screen
through `runDesktopComposeUiTest` with `state` hoisted exactly like `App.kt`:

- typing `ubeda` into the real `ManijeroSearchField` set `state.query = "ubeda"`, left `La Loma`
  (municipality `Úbeda`) rendered and removed `Los Olivos` — the accent fold works end-to-end, not only
  in the pure test;
- the field's named clear action (content description `Borrar la búsqueda`) reset `state.query` to `""`
  and `Los Olivos` came back;
- with `query = "zzz"` the panel sentence `No hay terrenos que coincidan con la búsqueda.` was
  displayed and `Resumen` was absent; activating the panel's `Borrar la búsqueda` action reset the
  query, restored both rows and restored `Resumen`.

**Goldens.** Recorded only with the filtered tasks from the verification plan (each `BUILD SUCCESSFUL`,
exit `0`):

```sh
./gradlew :shared:recordDesktopScreenshots \
  --tests "com.jamarglex.manijero.screenshots.LandListScreenshotsTest" \
  --tests "com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark"
./gradlew :shared:recordAndroidScreenshots \
  --tests "com.jamarglex.manijero.screenshots.LandListAndroidScreenshotsTest" \
  --tests "com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellLandsRailDark"
```

`git status --porcelain | grep png` lists exactly the ten intended images and nothing else (the other
24 PNGs are byte-identical):

```text
 M shared/src/androidHostTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/androidHostTest/screenshots/land_list_empty_dark.png
 M shared/src/androidHostTest/screenshots/land_list_light.png
 M shared/src/jvmTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark_phone.png
 M shared/src/jvmTest/screenshots/land_list_light.png
 M shared/src/jvmTest/screenshots/land_list_light_phone.png
?? shared/src/androidHostTest/screenshots/land_list_search_no_results.png
?? shared/src/jvmTest/screenshots/land_list_search_no_results.png
```

Each image was opened at full size before the final gate. What each one shows, and why it is intended:

- Desktop `land_list_light` (900×1000, light): three equal-weight summary columns (`Terrenos
  guardados` `2` + `Guardados en este dispositivo.`; `Superficie anotada` `1,5 ha` + `1 de 2 terrenos
  con superficie`; `Olivos anotados` `85 olivos` + `1 de 2 terrenos con olivos`), the labelled search
  field with the magnifier, the full-width `Añadir terreno` button, then the unchanged `Los Olivos`
  row with `Editar`/`Eliminar` and `La Loma` starting below the fold. This capture is the proof that
  the three-column branch is reachable at the window width (the breakpoint reads 900 dp here).
- Desktop `land_list_light_phone` (360×800): the same summary in one column, values and captions
  inside the card at phone width, the search field and the Add button above the rows; rows stay below
  the fold, exactly as the previous phone capture.
- Desktop `land_list_empty_dark` (900×800) and `land_list_empty_dark_phone` (360×800): the shared
  olive-branch empty state with `Aún no tienes terrenos añadidos`, `Cuando guardes uno, verás aquí lo
  que has anotado.` and exactly one primary `Añadir terreno` inside it; no cards, no search, no second
  Add at the bottom.
- Desktop and Android `app_shell_lands_rail_dark` (900×1000): the shell hands the screen less than
  840 dp (rail plus padding), so the summary is a **single column** here; it also shows the search
  field and the Add action. That is the intended responsive behaviour, not a layout regression.
- Desktop and Android `land_list_search_no_results` (**new**, 900×1000, light; the Android method
  carries `@Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")`): no summary cards at all, the search
  field holding `zzz` with its named clear icon, the `Añadir terreno` button above the panel, and the
  neutral panel with `No hay terrenos que coincidan con la búsqueda.` plus `Borrar la búsqueda`. At
  the phone viewport the panel would be below the fold, which is why both hosts pin 900×1000 dp.
- Android `land_list_light` (360×800): single-column summary, search field, Add button; no clipping,
  no overlap. Android `land_list_empty_dark` (360×800): the empty state and its one action.
- The Android `land_list_light` and app-shell rail rows still render the unchanged `Editar`/`Eliminar`
  controls and detail lines, so no row restyle slipped in.

**Implementation notes (deviations, all declared or purely internal)**

1. `LandSummary.treeTotal` is `Long?` and `filterLands` takes `LandSearchLabels` — both deviations are
   the ones the contract names, for the stated reasons (a sum of many lands can exceed `Int`; a
   non-composable function may not read `Res.string`). No other signature differs: both data classes
   keep exactly the declared fields and take no default arguments.
2. No-results panel tone: the panel is a `ManijeroCard` with `ManijeroCardTone.Tonal` (the neutral low
   container) instead of the default `Outlined`, so it does not read as one more bordered land row.
   No component was restyled and no token, colour or shape was added; the card is not clickable and
   adds no live region.
3. Search is recomputed on every composition from `state.query` (no debounce, no `remember`, no
   internal content composable), exactly as the search-state decision requires; `LandSearchLabels` is
   resolved once per composition of the populated branch.
4. The summary grid measures the **window** through a `BoxWithConstraints` around the padded content
   and compares `maxWidth >= WideWindowBreakpoint`; the 720 dp content column is below it by
   construction, so the three-column branch is reachable (proven by the 900 dp lands captures and the
   sub-840 dp shell rail capture).
5. The query is the appended third `LandListState` parameter with a blank default, and
   `LandsLoaded`/`LoadFailed`/`ReloadClicked` still build a fresh `LandListState(...)`, so no read can
   keep a stale query; `reduce(QueryChanged)` is the only `copy(...)`.
6. `formatTreeCount` gained the `Long` entry point and keeps a delegating `Int` overload, so there is
   one grouping implementation; the `Long` path parses the sign from `toString()`, which also covers
   `Long.MIN_VALUE`.
7. The failure state keeps its exact text, its polite live region and `Reintentar`, with no cards, no
   search and no Add; the retry button now sits directly in the content column, which is the same
   16 dp separation the previous nested single-child column produced.
8. `land_list_empty` was deleted with its import; its only reference was this screen.
9. All temporary probes and their PNGs were deleted; no test-only composable was added for the
   no-results golden (it is captured from `LandListState(lands = …, query = "zzz")`).

**Durable docs updated**: `DESIGN.md` (Lands bullet: summary wording, partial captions, text-only
search, empty store), `docs/domain-model.md` (new “Land search and summary” note under `Land`),
`CONTEXT.md` (two domain terms + `Last reviewed: 2026-10-25`), `CONSTRAINTS.md` (new “Land list search
and summary” block), `docs/risks-and-open-questions.md` (two Medium risks), and
`docs/screenshot-regression.md` (20 Desktop / 16 Android, the no-results and filtered captures and the
Android per-method qualifier). `ARCHITECTURE.md` and `AGENTS.md` are untouched on purpose: no module,
source-set, dependency, data-flow or contract boundary changed and the existing rules already cover
land UI, plain Spanish and the local-only boundary.

**Not verified (honest limits)**

- No interactive walkthrough in the Desktop app window or on an emulator/device: the typed and cleared
  paths were exercised through the Compose Desktop test harness, which is a host render, not a device.
- No screen-reader audit. The field's clear action is an `IconButton` named `Borrar la búsqueda`, the
  field is labelled `Buscar terreno`, and the no-results panel is deliberately not a live region (so
  typing announces nothing); none of that was heard on a screen reader.
- No real-device 2× text measurement: the large-font preview compiles and renders in the IDE, but no
  2× lands golden exists, so clipping at 200% on a device is unproven.
- No iOS run, and no user-comprehension evidence for the summary wording (`anotado`, `x de y`) or for
  the search hint. Both remain product decisions.
- The breakpoint boundary itself (839 dp vs 840 dp) is argued from `WideWindowBreakpoint` and the two
  captures on each side of it, not from an exhaustive sweep of widths.
- The load-failure, confirmation, just-saved/updated/removed and duplicate-name states have no
  goldens; they are covered by previews plus unchanged code and are not re-recorded here.

### 2026-10-25 — repair after validator `revise`

The implementer repair addressed the validator's four findings and recorded the fifth. Nothing is
committed; the working tree holds the same feature plus these changes.

**F1, F2, F4, F5.** `lands/LandSearch.kt` gained
`fun hasSearchTokens(query: String): Boolean = searchTokens(query).isNotEmpty()`, the single rule that
decides whether a search is filtering (it reuses the private tokenizer `filterLands` already had), and
`LandListContent` now derives `queryActive = hasSearchTokens(state.query)` from it instead of
`state.query.isNotBlank()`. A punctuation-only or emoji-only query therefore keeps the single unfiltered
summary. `LandSearchTest` gained one test asserting `false` for `""`, `"   "`, `"\n\t"`, `"..."`, `"¿?"`,
`"😀"` and `"... 😀 ..."` and `true` for `"olivos"`, `"lechín."` and `"85"`. The focused gate greps for
the predicate and rejects `query.isNotBlank()`, so the two rules cannot drift apart again. F2 split the
collapsed signature of the `LandListStateTest` unicode test. F4 changed the count card value from
`summary.total.toString()` to `formatTreeCount(summary.total)`, the one grouping implementation. F5 added
no permanent Compose interaction test, as instructed; the gap is listed as a limit below. No golden moved
because of these: both search goldens carry a token, the fixture totals are `1` and `2` (rendered the same
by either formatter), and the F2 edit is whitespace only.

**F3 — every filtered caption is a noun phrase keyed to the number it prints.** The three filtered
captions were rewritten and re-wired:

- `land_summary_count_caption_filtered`: one `%1$d de %2$d terreno guardado` · other `%1$d de %2$d
  terrenos guardados`, with `quantity = savedTotal` and `%2$d = savedTotal`; the card still shows
  `value = matches`, so `1 of 2` reads `1` + `1 de 2 terrenos guardados`.
- `land_summary_surface_caption_filtered` and `land_summary_trees_caption_filtered` keep their decided
  text (`… terreno encontrado con superficie` / `… terrenos encontrados con olivos`) and pluralize on the
  number they print, which is the shown land count — the match count while a query is active, exactly the
  denominator contract scenario 4 requires.
- The unfiltered captions and every other string are untouched. The search relation is stated once, by
  `land_summary_scope_filtered` above the cards.

*One instruction could not be applied literally.* The repair brief asked for `quantity = savedTotal` on all
three filtered captions **and** for the 2-saved/1-match golden to read `0 de 1 terreno encontrado con
superficie`. Both cannot hold: `quantity = 2` selects the `other` form, which would print `0 de 1 terrenos
encontrados con superficie` — the very disagreement the finding is about. The implementer followed the
observable copy in the brief, the agreement rationale, and scenario 4 (surface/tree denominator = match
count), and pluralizes those two captions on their own printed denominator. The count caption does use
`savedTotal`, which is also what it prints. Every reachable ratio therefore agrees:

| Saved / matches | Count card | Surface card | Tree card |
|---|---|---|---|
| 1 / 1, nothing annotated | `1` + `1 de 1 terreno guardado` | `Sin datos` + `0 de 1 terreno encontrado con superficie` | `Sin datos` + `0 de 1 terreno encontrado con olivos` |
| 2 / 1 (the new golden) | `1` + `1 de 2 terrenos guardados` | `Sin datos` + `0 de 1 terreno encontrado con superficie` | `Sin datos` + `0 de 1 terreno encontrado con olivos` |
| 2 / 2, one annotated | `2` + `2 de 2 terrenos guardados` | `1,5 ha` + `1 de 2 terrenos encontrados con superficie` | `85 olivos` + `1 de 2 terrenos encontrados con olivos` |
| 2 / 2, nothing annotated | `2` + `2 de 2 terrenos guardados` | `Sin datos` + `0 de 2 terrenos encontrados con superficie` | `Sin datos` + `0 de 2 terrenos encontrados con olivos` |

The text was observed on the real screen, not inferred: `TempFilteredCopyProbeTest` (a temporary
`runDesktopComposeUiTest` probe, four cases, each asserting the exact captions and the `Sin datos` values)
passed 4/4 and was deleted before the final gate; no probe file appears in `git status`.

**Filtered golden (light, 900 × 1000 dp, both hosts).** New fixture
`ScreenshotFixtures.searchFiltered = twoLands.copy(query = "ubeda")` (only `La Loma`, municipality
`Úbeda`, matches), captured by `land_list_search_filtered` in `LandListScreenshotsTest` and, with
`@Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")`, in `LandListAndroidScreenshotsTest`. Both images
were opened at full size: the filtered scope line under `Resumen`, three cards (`Terrenos guardados` `1` +
`1 de 2 terrenos guardados`; `Superficie anotada` `Sin datos` + `0 de 1 terreno encontrado con
superficie`; `Olivos anotados` `Sin datos` + `0 de 1 terreno encontrado con olivos`), the field holding
`ubeda`, the full-width `Añadir terreno` above the single `La Loma` row with `Editar`/`Eliminar`. The two
`encontrado` captions wrap to a second line inside the card, as the unfiltered captions already do;
nothing clips. It is the only filtered frame in either suite.

**Goldens and file scope.** `git status --porcelain | grep png` lists the ten images of the first round
(eight modified plus the two `land_list_search_no_results`) and the two new filtered ones, nothing else:

```text
 M shared/src/androidHostTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/androidHostTest/screenshots/land_list_empty_dark.png
 M shared/src/androidHostTest/screenshots/land_list_light.png
 M shared/src/jvmTest/screenshots/app_shell_lands_rail_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark.png
 M shared/src/jvmTest/screenshots/land_list_empty_dark_phone.png
 M shared/src/jvmTest/screenshots/land_list_light.png
 M shared/src/jvmTest/screenshots/land_list_light_phone.png
?? shared/src/androidHostTest/screenshots/land_list_search_filtered.png
?? shared/src/androidHostTest/screenshots/land_list_search_no_results.png
?? shared/src/jvmTest/screenshots/land_list_search_filtered.png
?? shared/src/jvmTest/screenshots/land_list_search_no_results.png
```

All 36 PNGs were hashed (`shasum`), both lands record tasks run again, and the hashes compared: the diff
was empty, so a second record run reproduced every existing image byte for byte and the repair's only
pixel-level addition is the two filtered frames. The other 34 are therefore byte-identical: 24 tracked
PNGs are untouched in `git status`, the 8 feature re-records only carry captions this repair did not move,
and the 2 no-results frames render no cards at all. The total is 20 Desktop + 16 Android = 36 PNGs, which
is the arithmetic `docs/screenshot-regression.md` now carries.

**Commands and results**

```sh
./scripts/init.sh --feature land_search_and_summary   # exit 0, 36 screenshot captures passed
./scripts/init.sh --fast                               # exit 0, "Fast tier passed."
./gradlew :shared:jvmTest --rerun-tasks                # exit 0, 266 tests / 27 classes
./scripts/init.sh --verify                             # exit 0, BUILD SUCCESSFUL
```

- Focused gate: exit `0`; `:shared:verifyDesktopScreenshots` 20 and `:shared:verifyAndroidScreenshots` 16
  captures passed (36 total), including the new filtered golden on both hosts; every static gate of the
  published block passed, with the two new checks (`hasSearchTokens` present, `isNotBlank()` absent from
  the screen) and the four-golden existence loop.
- `--fast`: exit `0`; contract examples `Validated 2 request and 3 response examples against
  answer_api_contract`; backend tests skipped because pytest is absent (no backend file changed);
  `All 9 offline checks passed.`
- Tests: `:shared:jvmTest` 266 / 27 classes (265 before; `LandSearchTest` 10 → 11), 0 failures, 0 errors,
  0 skipped; `:shared:testAndroidHostTest` 252 / 23 classes (251 before), 0 failures, 0 errors.
- `--verify`: exit `0`; `:shared:testAndroidHostTest`, `:androidApp:assembleDebug` and `:desktopApp:build`
  all succeeded.

**Docs updated for the new behaviour**: contract scenario 4 (quoted filtered copy and the agreement rule),
scenario 6 (the scope/caption decision follows the token test), technical item 3 (`hasSearchTokens`), item
6 (the per-caption plural rule), item 8 and the expected-file list (four new goldens, 20/16); this
appendix's copy inventory, plural-quantity note, task 8, verification plan, evidence list and validator
checklist; and `docs/screenshot-regression.md` (20 Desktop / 16 Android, 36 PNGs, both search states
named, Android filtered qualifier). `feature_list.json` status is left for the orchestrator.

**Limits after the repair**: the earlier list stands (no interactive device walkthrough, no screen-reader
audit, no real 2× device measurement, no iOS run, no user-comprehension evidence), plus two now explicit:
no permanent Compose interaction test covers typing or the clear action, so a regression in that wiring
would only show up in a manual walkthrough or a golden; and the filtered golden proves the reviewed copy
renders, not that a person reads `x de y` as "of the lands on screen".

_Validator acceptance evidence is appended below by `feature-validator`._

### 2026-10-25 — independent validation, pass 2 (accept)

The first validation pass returned **revise** with one blocking finding (F1: the summary switched to
filtered copy on a punctuation/emoji-only query while the filter treated it as blank), plus F2
(collapsed test line), F3 (filtered count-caption agreement), F4 (count value bypassed
`formatTreeCount`) and F5 (interaction coverage only in deleted probes). The repair is recorded in the
subsection above; the second pass returned **accept** with no code finding.

Independently re-run by the validator, not quoted:

```text
./scripts/init.sh --feature land_search_and_summary   # exit 0 — 20 desktop + 16 android captures, all static gates
./scripts/init.sh --fast                              # exit 0 — "Fast tier passed.", All 9 offline checks passed
./scripts/init.sh --verify                            # exit 0 — testAndroidHostTest + assembleDebug + desktopApp:build
./gradlew :shared:jvmTest --rerun-tasks               # 266 tests / 27 classes, 0 failures, errors or skips
./gradlew :shared:testAndroidHostTest --rerun-tasks   # 252 tests / 23 classes, 0 failures
```

- Both record tasks re-run from scratch reproduced all **36** goldens byte for byte (`shasum` diff
  empty), so the 8 re-recorded and 4 new images are exactly the feature's pixel change and the other
  34 are byte-identical.
- The 12 touched images were opened and reviewed: the filtered frame shows
  `1 de 2 terrenos guardados`, `0 de 1 terreno encontrado con superficie` and
  `0 de 1 terreno encontrado con olivos` with `ubeda` in the field; the no-results frame shows no
  cards, the field holding `zzz`, Add above the panel; the empty frames show the olive branch and one
  Add action; the shell rail frame keeps the single-column summary as intended.
- Scope, architecture and privacy checks passed: `hasSearchTokens` is the single scope/filter rule,
  no `isNotBlank()` remains in the screen, the pure layer imports no Compose/resource type, the query
  reaches no store, payload, `Land`/`LandDraft` or log line, and no `chat/`, `privacy/`, `theme/`,
  `design/`, navigation, `contracts/`, `backend/`, `knowledge/` or Gradle file changed.

Three documentation wording notes from the second pass were applied in the acceptance commit: the
spec's self-summary and scenario 10 now name the no-results **and** filtered goldens per host; the
spec/appendix caption note now says the filtered count caption is the one caption printing two counts;
`DESIGN.md` no longer claims every card carries an `x de y` caption. The remaining observation — a
filtered count card can be skimmed as "1 saved land" from label plus value — is recorded as input to
the later land comprehension/accessibility feature, not as a defect. Acceptance record:
[`docs/validations/land_search_and_summary.md`](../validations/land_search_and_summary.md).

## Validator checklist

- [x] Contract scenarios 1–10 are each exercised by a test, a static gate, the goldens or a recorded
      manual check, and the evidence names which one.
- [x] The empty store shows no cards and no search and exactly one primary Add action inside
      `ManijeroEmptyState` with the new heading and body, no leftover `land_list_empty` reference; the
      failure state still shows no Add action and no cards.
- [x] `LandSummary` totals are `null` exactly when nothing is annotated; a card without data shows
      `Sin datos` plus its denominator caption and never `0 ha`/`0 olivos`; no total is inferred from
      another attribute.
- [x] With a query active every card describes only the shown set, with the `encontrado(s)` captions and
      the `x de y` denominator of the saved total on the count card; with no match no card is rendered.
- [x] Every caption pluralizes on the number it prints (count card: saved total; surface/tree cards: the
      shown land count), so `1 de 1 terreno guardado`, `1 de 2 terrenos guardados`,
      `2 de 2 terrenos guardados` and `0 de 1 terreno encontrado con superficie` all agree; the count card
      value is formatted by the one grouping implementation.
- [x] The filtered scope and captions follow `hasSearchTokens`, so a punctuation-only or emoji-only query
      renders the unfiltered wording over the unchanged full list.
- [x] `filterLands` matches name, zone, municipality, variety label and custom `Otra` text, water label and
      production label; it does not match the id, notes, timestamps, surface or tree count; it folds
      `á é í ó ú ü ñ` and case, requires every letter/digit token (punctuation and emoji are only
      separators), keeps repository order, and returns the input list for a blank, punctuation-only or
      emoji-only query; `hasSearchTokens` reports that same blank-equivalent set.
- [x] `LandSummary.kt` and `LandSearch.kt` import no Compose/resource type, read no `Res.*`, own no copy,
      and add no second number formatter; the surface/tree totals are formatted by the existing
      `formatHectares`/`formatTreeCount`.
- [x] The query lives only in `LandListState`, resets on every read (load, failure, reload), and reaches no
      store, payload, `Land`/`LandDraft` field or log line.
- [x] Only the eight named goldens were re-recorded and the four new ones (`land_list_search_no_results.png`
      and `land_list_search_filtered.png` per host) were added; the other PNGs are byte-identical;
      `docs/screenshot-regression.md` says 20 Desktop / 16 Android; the 900 dp lands captures show three
      summary columns while the shell rail golden shows one (the shell hands the screen less than 840 dp),
      so neither reads as a layout regression.
- [x] Exactly the contract's files changed; `chat/`, `privacy/`, `theme/`, `design/`, navigation,
      `contracts/`, `backend/`, `knowledge/`, Gradle, platform entry points, `land_list.md` and the
      historical design plan are untouched, and no row/chip/confirmation restyle slipped in.
- [x] `DESIGN.md`, `docs/domain-model.md`, `CONTEXT.md`, `CONSTRAINTS.md`,
      `docs/risks-and-open-questions.md` and `docs/screenshot-regression.md` match the shipped behaviour;
      `ARCHITECTURE.md`/`AGENTS.md` are correctly untouched with a stated reason.
- [x] Verification was run independently, not only quoted from the implementer; the honest limits (no
      user evidence, no screen-reader audit, no device 2× check) are recorded.
