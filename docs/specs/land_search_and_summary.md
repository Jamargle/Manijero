# Feature Spec: `land_search_and_summary`

## Source metadata

- **Feature:** `land_search_and_summary` — Search saved lands and summarize annotated measures (`lands`).
- **Status at planning:** `not_started`; dependency `land_measurement_fields` is accepted.
- **Source behavior:** a person with several saved lands can filter the `Mis terrenos` list by typing, and
  sees a plain-Spanish summary of the annotated surface and olive-tree counts for the lands they are
  currently looking at, without any new server call, stored value, or payload field.
- **Source verification:** filtered and unfiltered summary counts in both states; text search that folds
  Spanish accents, case and `ñ`; every other state unchanged.
- **Feature-list note:** owns the approved UI-refresh land slice
  [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md) §5.3 (empty lands), §5.4 (populated
  lands), §7.4 (summary calculations), §7.5 (search), §7.7 (copy inventory), and §8 steps P1-10, P1-11,
  P1-12, P1-13. This spec supersedes the *list-surface* wording of the accepted
  [`land_list.md`](land_list.md) contract; that record is history and is not rewritten.

**Confirmed product decisions (user, 2026-10-25) — binding, recorded verbatim:**

1. "Land search matches text only: name, municipality, zone, variety label including the Otra free text,
   water-regime label, production-method label. Do NOT search numeric measures (surface, tree count) or
   ids/notes/timestamps."
2. "Summary cards describe the current search result set: all saved lands when the query is blank, only
   matching lands when a query is active. Copy must stay honest when filtered (e.g. '2 de 3 terrenos
   encontrados tienen superficie'), and unknown values never render as zero or a guess."
3. "Summary wording is 'Superficie anotada' / 'Olivos anotados' with partial-value captions."
4. "Empty store: no summary cards and no search field; exactly one primary Add action
   (ManijeroEmptyState with the decorative olive branch is available)."

## Goal and boundaries

Make a growing list of lands navigable in one step and make the person's own annotations readable at a
glance, while never turning a missing value into a zero, an unverified total, or a hidden land.

**In scope**

- A pure `LandSummary` derivation over an explicit land list, and pure `filterLands` search with
  Spanish accent/`ñ`/case folding, both in `commonMain` with no Compose or platform types.
- Summary cards on the populated list: land count, `Superficie anotada`, `Olivos anotados`, each with a
  denominator caption that states what it counted, describing the currently shown set.
- A search field that filters as the person types (no submit button), with a named clear action and a
  honest no-results panel.
- The empty store becomes the shared `ManijeroEmptyState` with exactly one primary Add action, no cards
  and no search.
- The search query becomes part of the existing in-memory `LandListState` (see the decision below), so
  the screen stays stateless and a golden can capture the no-results state.
- New plain-Spanish copy in `strings.xml`; re-recorded land-list/shell goldens plus one new
  no-results and one new filtered golden per host.

**Non-goals**

- No land row restyle, chips, tonal edit/delete buttons, confirmation callout, header restyle or
  `ManijeroScreen` adoption (`lands_screens_refresh`), and no new colour, token, vector, font, icon,
  dependency or module.
- No sorting, ranking, highlighting, pagination, saved searches, debounce framework, or search history.
- No new land attribute, no change to `Land`/`LandDraft`, `LandRepository`, the `land-store-v1` format,
  validation or the add/edit/remove forms.
- No change to `AskRequest`, `MinimalLandContext`, `LandContextBuilder`, `SHARED_LAND_ATTRIBUTES`,
  `contracts/`, `backend/`, `knowledge/` or any privacy copy: search and summary are display-only.
- No claim that a summary is a verified measurement, a cadastral surface, or eligibility evidence, and no
  claim that search is exhaustive or ranked.
- No rewrite of the historical `docs/design/ui-refresh-plan.md`, `docs/specs/land_list.md` or any past
  acceptance record.
- No real-user comprehension evidence; none is claimed.

## Job story

When I have several lands saved, I want to type a few letters of a name, a village, a zone or a variety
and see only the lands that fit, and see how much surface and how many olive trees I have written down
for whatever I am looking at — so I can find the right land and read my own notes at a glance, without
the app inventing a number I never wrote.

## Acceptance scenarios

### 1. An empty store offers exactly one way in

Given a successful read that found no land, when `Mis terrenos` is shown, then it renders the shared
empty state with the decorative olive branch, the heading `Aún no tienes terrenos añadidos`, the body
`Cuando guardes uno, verás aquí lo que has anotado.`, exactly one primary `Añadir terreno` action, and
**no** summary cards and **no** search field.

### 2. A saved list summarizes every land honestly

Given three saved lands with surfaces `1,5`, `0,75` and none, and tree counts `85`, none and `1 200`,
when the list is shown with a blank query, then the count card states `3`, `Superficie anotada` states
`2,25 ha` with `2 de 3 terrenos con superficie`, and `Olivos anotados` states `1 285 olivos` with
`2 de 3 terrenos con olivos`.

### 3. Absent values never become zero or a guess

Given a list where no land has a surface, when the summary renders, then the surface card states
`Sin datos` (never `0 ha`) with `0 de 3 terrenos con superficie`. Given a single saved land with no
trees, its tree card states `Sin datos` with a singular caption (`0 de 1 terreno con olivos`); with one
tree that card shows `1 olivo` with `1 de 1 terreno con olivos`. No total is derived from another
attribute (no surface from trees, no trees from surface).

### 4. The summary follows the search result set

Given three saved lands where two match the typed query, when the query is active, then every card
describes only the two matches — the count card reads `2 de 3 terrenos guardados` over the value `2`,
and the surface card's caption is `1 de 2 terrenos encontrados con superficie`, so a partial value can
never be read as a total for all saved lands. Every filtered caption is a noun phrase pluralized on the
number it prints (`1 de 1 terreno guardado`, `1 de 3 terrenos guardados`, `2 de 3 terrenos guardados`,
`0 de 1 terreno encontrado con superficie`), so its noun never disagrees with that number; the search
relation itself is stated by `land_summary_scope_filtered` above the cards.

### 5. Search matches text, never measures or private fields

Given a land named `Los Olivos` with surface `1,5 ha`, `85` trees, the id `land-1` and a note containing
`aceituna`, when the query is `85`, `1,5`, `2,5`, `land-1` or `aceituna`, then no land matches; when the
query is a part of its name, zone, municipality, variety label, custom `Otra` text,
`Secano`/`Regadío`/mixed water label, or `Convencional`/`Ecológico`/mixed production label, then that
land matches.

### 6. Search forgives accents, case, `ñ` and punctuation

Given a land named `Peña de los Olivos` in `Úbeda` with variety `Lechín de Sevilla`, when the person types
`pena`, `PEÑA`, `ubeda`, `ÚBEDA`, `lechin`, `lechín.` or `olivos ubeda` (several words, any order), then
the land matches; punctuation and emoji act as word separators and are never matched literally, so a
query made only of them (`...`, `😀`) behaves like a blank query and returns the untouched full list, and
a blank or whitespace-only query does the same. The summary's scope and captions follow the same test
(`hasSearchTokens`), so a tokenless query never renders the filtered wording.

### 7. Results stay in repository order and rows are untouched

Given a filtered result set, when it renders, then the matches keep the repository order of the read (no
ranking, no reordering, no duplicate), and each row still shows the same name, zone, variety, known
surface/tree lines, `Editar` and `Eliminar` as before.

### 8. No results is an honest, recoverable state

Given a typed query that matches no land, when the list renders, then no summary card is shown, a neutral
panel states `No hay terrenos que coincidan con la búsqueda.` with a `Borrar la búsqueda` action, the
`Añadir terreno` action above it stays reachable, and pressing either the panel action or the search
field's named clear action restores the full list.

### 9. The query is display state only

Given any query, when the app is inspected, then the query lives only in the in-memory `LandListState`:
it is never persisted (no store field, no `Land`/`LandDraft` change), never sent (no `AskRequest`,
`MinimalLandContext` or log line contains it), and it resets to blank on the next read — entering the
tab, retrying, and returning from a save, edit or removal all show the full list again.

### 10. Scope stays inside the land list

Given this feature's diff, when it is reviewed, then no `chat/`, `contracts/`, `backend/`, `knowledge/`,
`privacy/`, `theme/`, `design/`, navigation, Gradle or platform entry-point file changed, only the
lands/shell goldens named below were re-recorded, the new no-results and filtered goldens exist on both
hosts, and every other golden is byte-identical.

## Technical approach

**Search-state decision (explicit).** The query is hoisted into the existing pure `LandListState`
(`query: String = ""`) and changed through one new action, `LandListAction.QueryChanged`. The screen stays
stateless — `state` in, `onQueryChange`/`onAddLand`/… out — and `App.kt` owns the value, exactly like
`lands`/`loadFailed` today. This is preferred over a `remember` inside the screen or an internal
content composable because it (a) keeps the whole search state pure and unit-testable, (b) makes the
no-results golden capturable by passing `state = LandListState(lands = …, query = "zzz")` with no test-only
composable, and (c) matches the accepted `LandsLoaded`/`LoadFailed`/`ReloadClicked` pattern. `LandsLoaded`,
`LoadFailed` and `ReloadClicked` keep their current bodies, so every read resets the query.

1. **Summary** — add `lands/LandSummary.kt` (pure):
   `data class LandSummary(total: Int, surfaceTotal: Double?, surfaceKnownCount: Int, treeTotal: Long?,
   treeKnownCount: Int)` and `fun summarizeLands(lands: List<Land>): LandSummary`. `total` is the size of
   the list it received; a total is `null` exactly when its known count is `0`; the surface sum is rounded
   once with the existing `roundHectares`; the tree sum accumulates in `Long` so it cannot wrap. No
   formatting, no Compose, no resource read in this file. The `treeTotal: Long?` type is the one
   deliberate deviation from the historical plan's `Int?` (a sum of many lands can exceed `Int`); the
   field names and meaning are unchanged.
2. **Number formatting reuse** — widen `lands/LandFields.kt`'s `formatTreeCount` to a `Long` entry point
   and keep the `Int` overload delegating to it, so the tree total is formatted by the one accepted
   grouping implementation. `formatHectares` is used unchanged for the surface total (it already rounds to
   the stored two decimals and trims trailing zeros). No second formatter is added anywhere.
3. **Search** — add `lands/LandSearch.kt` (pure): `data class LandSearchLabels(waterRegime:
   Map<WaterRegime, String>, productionMethod: Map<ProductionMethod, String>, variety:
   Map<LandVariety, String>)`, `fun foldForSearch(value: String): String`,
   `fun filterLands(lands: List<Land>, query: String, labels: LandSearchLabels): List<Land>` and
   `fun hasSearchTokens(query: String): Boolean`.
   - `foldForSearch` lowercases with the locale-invariant `lowercase()` and then folds `á é í ó ú ü → a e i
     o u u` and `ñ → n`; uppercased forms are folded by the lowercase step, so one lowercase map suffices.
   - Per land the searchable text is exactly: name, zone, municipality, variety text (the custom `Otra`
     text when `variety == OTHER`, otherwise the resolved variety label), the resolved water-regime label
     and the resolved production-method label. Never the id, notes, timestamps, surface or tree count.
   - The folded query is split into maximal runs of letters or digits (`Char.isLetterOrDigit`), so
     punctuation and emoji are separators and are never matched literally; a land matches when **every**
     token is a substring of its folded searchable text (so `olivos ubeda` and `ubeda olivos` behave the
     same). No tokens — blank, spaces, punctuation only, emoji only — returns the input list unchanged, in
     order. Output preserves repository order; no ranking, no rewriting.
   - The labels arrive as parameters because the Spanish labels live in `strings.xml` and `Res.string` may
     not be read from a non-composable function; the screen resolves them once per composition. The file
     therefore owns no copy. This is the only deviation from the historical plan's
     `filterLands(lands, query)` signature: the injected `labels` argument keeps the pure layer free of
     resource reads without moving Spanish copy into Kotlin.
4. **State** — `lands/LandListState.kt`: third parameter `query: String = ""` (appended, so existing
   positional construction stays valid) plus `LandListAction.QueryChanged(query)`; `reduce` maps it to
   `copy(query = action.query)` and keeps the other branches unchanged. Those three branches build a
   **new** `LandListState(...)` rather than a `copy(...)`, so the appended `query` defaults to blank on
   every read; do not convert them to `copy(...)`, which would silently keep a stale query across a save,
   edit, removal, retry or tab re-entry.
5. **Screen** — `lands/LandListScreen.kt` gains one required parameter `onQueryChange: (String) -> Unit`
   (no default, so `App.kt` cannot forget the wiring). Content order and states:
   title + `land_list_description` (unchanged) → confirmation (unchanged) → then
   `loadFailed` (unchanged text + `Reintentar`, no cards/search) or
   `state.isEmpty` (`ManijeroEmptyState` with heading/body and the single `Añadir terreno` button inside it)
   or the populated branch: `LandSummarySection`, `ManijeroSearchField`, the full-width
   `Añadir terreno` button, then either the rows or the no-results `ManijeroCard`.
   `LandSummarySection` is a private composable: `ManijeroSectionHeader` (`Resumen` + a scope description
   that changes when a query is active, `heading = true`) over a grid of three `ManijeroStatCard`s — one
   column below the existing `design.WideWindowBreakpoint` (840 dp) and three equal-weight columns at or
   above it; there is no new breakpoint constant and no new token. The column count MUST come from the
   **window** width read by a `BoxWithConstraints` that wraps the padded content (the `Surface` child), not
   from the inner content column: that column is capped at 720 dp, so a breakpoint measured inside it would
   never reach 840 dp and the three-column branch would be dead code. The cards are not rendered at all
   when the shown set is empty. Rows, `LandDetails` and the preview data helpers keep their current content.
6. **Copy** — all new strings in `shared/src/commonMain/composeResources/values/strings.xml`, plain
   Spanish, `tú`, no jargon. The six counted captions are Compose `<plurals>` entries whose quantity is
   the denominator each one prints (only `one`/`other` are needed in Spanish):
   `land_summary_count_caption`, `land_summary_count_caption_filtered`,
   `land_summary_surface_caption`, `land_summary_surface_caption_filtered`,
   `land_summary_trees_caption`, `land_summary_trees_caption_filtered`. The count card prints the saved
   total, so its filtered caption is a verbless noun phrase (`%1$d de %2$d terrenos guardados`,
   `1 de N` reads `1 de 2 terrenos guardados`) that pluralizes on that saved total. The surface and tree
   captions print the number of shown lands (the match count while a query is active, as scenario 4
   requires: `0 de 1 terreno encontrado con superficie`), so they pluralize on that number and cannot
   disagree with it under any reachable ratio (1 of 1, 1 of N, N of N, 0 of N). The filtered count
   caption is the exception in shape, not in agreement: it prints two counts (`%1$d` matches,
   `%2$d` saved) and stays a verbless noun phrase, so no verb can agree with the wrong number; each
   noun pluralizes on the denominator its own caption prints. The search relation is stated once, in
   `land_summary_scope_filtered`. The olive-tree
   **value** is instead
   a two-key pair, `land_summary_trees_value_one` (`%1$s olivo`) and `land_summary_trees_value_other`
   (`%1$s olivos`), chosen by `if (treeTotal == 1L)`: the total is a `Long` and `pluralStringResource` takes
   an `Int`, so a plural there would need a lossy cast for a count the app never invents. Plain strings:
   `land_summary_title`, `land_summary_scope_all`, `land_summary_scope_filtered`,
   `land_summary_count_label`, `land_summary_surface_label`, `land_summary_surface_value` (`%1$s ha`),
   `land_summary_trees_label`, `land_summary_no_data` (`Sin datos`), `land_list_empty_title`,
   `land_list_empty_body`, `land_search_label`, `land_search_hint`, `land_search_clear`,
   `land_search_no_results`,
   `land_summary_trees_value_one`, `land_summary_trees_value_other`. The approved
   plan copy is used verbatim where it exists (`Aún no tienes terrenos añadidos`,
   `Buscar por nombre, municipio o tipo…`, `Borrar la búsqueda`,
   `No hay terrenos que coincidan con la búsqueda.`, `Superficie anotada`, `Olivos anotados`). If the
   generated `Res.plurals` accessor is unavailable in this Compose version, fall back the six captions to
   two plain keys named `<key>_one` / `<key>_other`, chosen in the screen by `if (denominator == 1)`, and
   record the substitution in the appendix evidence. The focused block accepts either caption shape. Delete
   the now-unused `land_list_empty` key and its import when the empty state moves to
   `land_list_empty_title`/`land_list_empty_body` plus the action inside `ManijeroEmptyState` (verified:
   the screen is its only reference).
7. **Wiring** — `App.kt` passes `onQueryChange = { landListState = landListState.reduce(
   LandListAction.QueryChanged(it)) }` to `LandListScreen`; nothing else in the composition root changes.
8. **Screenshots** — extend `commonTest/.../screenshots/ScreenshotFixtures.kt` with a
   `searchNoResults` fixture (`twoLands.copy(query = "zzz")`, which matches neither land) and a
   `searchFiltered` fixture (`twoLands.copy(query = "ubeda")`, which matches only `La Loma`), add one
   `land_list_search_no_results` capture and one `land_list_search_filtered` capture to
   `LandListScreenshotsTest` (Desktop) and to `LandListAndroidScreenshotsTest` (Android host). Both
   captures MUST use the **wide 900 × 1000 dp** viewport
   on both hosts — the Android methods carry
   `@Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")` exactly as the shell rail captures already do —
   because at the 360 × 800 phone viewport the summary cards push the no-results panel below the fold and
   the golden would prove nothing; the filtered capture shows the filtered scope, the three `x de y`
   captions and the one matching row in one frame. Note that `app_shell_lands_rail_dark` measures the space the shell hands
   the screen (900 dp minus the rail and padding, i.e. below 840 dp), so that golden shows the
   single-column summary; the three-column layout is proven by the standalone 900 dp lands captures. Then
   re-record only the goldens listed under "Expected file changes".
9. **Docs** — the durable updates in the table below; no historical artifact is rewritten.

## Expected file changes

- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandSummary.kt` and
  `lands/LandSearch.kt`.
- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`,
  `lands/LandListState.kt`, `lands/LandFields.kt` (`formatTreeCount(Long)` entry point),
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` (one callback),
  `shared/src/commonMain/composeResources/values/strings.xml` (new keys; `land_list_empty` retired).
- **Add** `shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandSummaryTest.kt` and
  `lands/LandSearchTest.kt`; **update** `lands/LandListStateTest.kt` (query reduce + reset on every read).
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/screenshots/ScreenshotFixtures.kt`,
  `shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/LandListScreenshotsTest.kt`,
  `shared/src/jvmTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt`,
  `shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/LandListAndroidScreenshotsTest.kt`
  and `shared/src/androidHostTest/kotlin/com/jamarglex/manijero/screenshots/AppShellScreenshotsTest.kt`
  (the two shell classes and the Android lands class only gain the `onQueryChange = {}` argument).
- **Re-record (8)** Desktop `shared/src/jvmTest/screenshots/`: `land_list_light.png`,
  `land_list_light_phone.png`, `land_list_empty_dark.png`, `land_list_empty_dark_phone.png`,
  `app_shell_lands_rail_dark.png`; Android `shared/src/androidHostTest/screenshots/`:
  `land_list_light.png`, `land_list_empty_dark.png`, `app_shell_lands_rail_dark.png`.
- **Add goldens (4)** `land_list_search_no_results.png` and `land_list_search_filtered.png` in
  `shared/src/jvmTest/screenshots/` and in `shared/src/androidHostTest/screenshots/`. Every other PNG (24
  against the base commit, and 34 once the two no-results goldens are counted in) stays byte-identical.
- **Update docs** `DESIGN.md`, `docs/domain-model.md`, `CONTEXT.md`, `CONSTRAINTS.md`,
  `docs/risks-and-open-questions.md`, `docs/screenshot-regression.md` (capture table 18/14 → 20/16 and
  the new lands states).
- After independent acceptance: `feature_list.json`, `PROGRESS.md`, `docs/progress/current-state.md`,
  `docs/progress/session-log.md`, this appendix's "Feature evidence" and
  `docs/validations/land_search_and_summary.md`.
- **Not changed:** `lands/Land.kt`, `lands/LandRepository.kt`, `lands/AddLandScreen.kt`,
  `lands/AddLandState.kt`, `lands/EditLandScreen.kt`, `lands/EditLandState.kt`, `lands/RemoveLand*.kt`,
  everything under `chat/`, `privacy/`, `theme/`, `design/`, `design/navigation/`, `contracts/`,
  `backend/`, `knowledge/`, Gradle files, platform entry points, `docs/specs/land_list.md` and
  `docs/design/ui-refresh-plan.md`.

## Visual design impact

- The list keeps its accepted frame (background `Surface`, one vertical scroll, 24 dp padding, 720 dp
  centred column, `headlineMedium` title, `bodyLarge` explanation) and adopts `ManijeroSectionHeader`,
  `ManijeroStatCard`, `ManijeroSearchField`, `ManijeroEmptyState` and `ManijeroCard` as they are. No
  component is restyled, no colour, shape, spacing or elevation token is added, and no raw colour is
  introduced.
- Summary cards use the accepted `Outlined` stat-card tone with a required caption, so a value can never
  appear as a bare number: label (`Terrenos guardados`, `Superficie anotada`, `Olivos anotados`), value,
  denominator caption. `Sin datos` replaces the value when nothing is annotated; no card ever shows `0 ha`.
  One column below 840 dp keeps values readable at 2× text; three columns appear only on the wide window
  the shell already switches at (the breakpoint reads the window width, not the 720 dp content column, so
  the wide branch is actually reachable).
- `Añadir terreno` becomes a full-width primary button above the list (not a floating action that can
  cover rows) and is the only primary action on the screen; the empty state holds that same single action
  inside it, with no duplicate at the bottom.
- The search field is the accepted labelled field with the magnifier and a named clear action; the
  approved hint copy is the placeholder, which Material renders only while the field is focused and empty.
  Filtering happens on every keystroke with no submit button and no visible spinner.
- The no-results panel is a neutral `ManijeroCard` (no caution/danger hue, no live region, so typing does
  not announce on every keystroke) with the plain message and one `Borrar la búsqueda` text action.
- Land rows, their detail lines, `Editar`/`Eliminar` and the confirmation notice are visually unchanged;
  the chips/tonal-action restyle stays with `lands_screens_refresh`.
- Every new copy is plain Spanish, addresses the person as `tú`, implies no verification, completeness,
  legal status or eligibility, and never states a total that includes a land the person cannot see.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | The **Lands:** bullet must state the summary cards (annotated wording, partial `x de y` captions, `Sin datos`), text-only search with a named clear action, and the empty store = olive-branch empty state with one Add action and no cards/search. |
| `docs/domain-model.md` | Update | Add a short "Land search and summary" note under `Land`: both are derived, never persisted or sent; the summary counts only annotated values; search matches the listed text fields and never measures, ids, notes or timestamps. |
| `CONTEXT.md` | Update | Add two rows to the Domain terms table — `Annotated value` (a value the person entered; absent stays absent, never a zero) and `Land search` (text-only local filter, no measures/notes/ids) — and refresh "Last reviewed". |
| `CONSTRAINTS.md` | Update | Add a "Land list search and summary" block in the house style with a Reason line naming this feature: derived-only (never stored/sent), honest denominators (`x de y`, `Sin datos`, never zero-for-absent), text-only matching over name, zone, municipality, the variety label or custom `Otra` text, the water label and the production label, no ranking/reordering, empty store = one Add action and no cards/search, no payload/store change. |
| `docs/risks-and-open-questions.md` | Update | Add two Medium risks: "Summary totals read as a verified or cadastral measurement" (mitigation: `anotado` wording, `x de y` denominator, `Sin datos`, no eligibility claim) and "Search misses a land the person expected" (mitigation: the field list in the search hint, no ranking, no exhaustive claim). |
| `docs/screenshot-regression.md` | Update | Both count rows become 20 Desktop / 16 Android (the app frames grow from `4 scenes × 2 widths` / `4 scenes` to 10 / 6 with one no-results and one filtered capture, each at a single 900 × 1000 dp viewport), and the app-scene sentence gains "saved-lands search with no results (light)" and "saved-lands search with one match (light)". |
| `ARCHITECTURE.md` | Not needed | No module, source-set, dependency, data-flow or contract boundary changes; the new code stays in `shared/src/commonMain` beside the land state. |
| `AGENTS.md` | Not needed | Existing routing and operating rules already cover land UI, plain Spanish copy and the local-only boundary. |
| `docs/specs/land_list.md`, `docs/design/ui-refresh-plan.md`, past acceptance records | Not changed | Accepted history. This spec supersedes the list-surface behavior; only the durable rules above are rewritten in living docs. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/*`, validation record | Update after implementation and independent acceptance | Keep the board, status and evidence pointers honest. |

## Focused verification

Compiles and tests the land list, its pure summary/search layer, the re-recorded and new goldens, and the
copy/purity/scope gates. Read-only apart from Gradle output.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :shared:verifyScreenshots
lands="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/lands"
strings="$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml"
test -f "$lands/LandSummary.kt" || { echo "missing LandSummary.kt" >&2; exit 1; }
test -f "$lands/LandSearch.kt" || { echo "missing LandSearch.kt" >&2; exit 1; }
if grep -nE 'androidx\.|org\.jetbrains\.compose|Res\.(string|plurals)|stringResource|pluralStringResource' \
  "$lands/LandSummary.kt" "$lands/LandSearch.kt"; then
  echo "the pure summary/search layer imports Compose or reads a resource" >&2
  exit 1
fi
grep -q 'fun summarizeLands' "$lands/LandSummary.kt" || { echo "missing summarizeLands" >&2; exit 1; }
grep -q 'fun filterLands' "$lands/LandSearch.kt" || { echo "missing filterLands" >&2; exit 1; }
grep -q 'fun foldForSearch' "$lands/LandSearch.kt" || { echo "missing foldForSearch" >&2; exit 1; }
grep -q 'fun hasSearchTokens' "$lands/LandSearch.kt" || { echo "missing hasSearchTokens" >&2; exit 1; }
if grep -nE 'fun format(Hectares|TreeCount)|fun formatCount' "$lands/LandSummary.kt" "$lands/LandSearch.kt"; then
  echo "a second number formatter was added" >&2
  exit 1
fi
grep -q 'formatHectares(' "$lands/LandListScreen.kt" || { echo "surface total is not formatted with formatHectares" >&2; exit 1; }
grep -q 'formatTreeCount(' "$lands/LandListScreen.kt" || { echo "tree total is not formatted with formatTreeCount" >&2; exit 1; }
grep -q 'val query' "$lands/LandListState.kt" || { echo "the query is not part of LandListState" >&2; exit 1; }
grep -q 'QueryChanged' "$lands/LandListState.kt" || { echo "missing LandListAction.QueryChanged" >&2; exit 1; }
for component in ManijeroStatCard ManijeroSearchField ManijeroEmptyState ManijeroSectionHeader; do
  grep -q "$component" "$lands/LandListScreen.kt" || { echo "missing component: $component" >&2; exit 1; }
done
if grep -rnE 'LandSummary|LandSearch|filterLands|summarizeLands|QueryChanged' \
  "$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/"; then
  echo "search or summary leaked into the chat layer" >&2
  exit 1
fi
for key in land_summary_title land_summary_scope_all land_summary_scope_filtered \
  land_summary_count_label land_summary_surface_label land_summary_surface_value \
  land_summary_trees_label land_summary_no_data land_list_empty_title land_search_label \
  land_search_hint land_search_clear land_search_no_results \
  land_list_empty_body land_summary_trees_value_one land_summary_trees_value_other; do
  grep -q "<string name=\"$key\"" "$strings" || { echo "missing string: $key" >&2; exit 1; }
done
if grep -q '<string name="land_list_empty">' "$strings"; then
  echo "land_list_empty is superseded by land_list_empty_title/_body; remove it" >&2
  exit 1
fi
for key in land_summary_count_caption land_summary_count_caption_filtered \
  land_summary_surface_caption land_summary_surface_caption_filtered \
  land_summary_trees_caption land_summary_trees_caption_filtered; do
  if grep -q "<plurals name=\"$key\"" "$strings"; then continue; fi
  if grep -q "<string name=\"${key}_one\"" "$strings" && grep -q "<string name=\"${key}_other\"" "$strings"; then continue; fi
  echo "missing plurals: $key (neither <plurals> nor a ${key}_one/${key}_other pair)" >&2
  exit 1
done
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandSummaryTest.kt" || { echo "missing summary tests" >&2; exit 1; }
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/lands/LandSearchTest.kt" || { echo "missing search tests" >&2; exit 1; }
for png in "$REPO_ROOT/shared/src/jvmTest/screenshots/land_list_search_no_results.png" \
  "$REPO_ROOT/shared/src/androidHostTest/screenshots/land_list_search_no_results.png" \
  "$REPO_ROOT/shared/src/jvmTest/screenshots/land_list_search_filtered.png" \
  "$REPO_ROOT/shared/src/androidHostTest/screenshots/land_list_search_filtered.png"; do
  test -f "$png" || { echo "missing golden: $png" >&2; exit 1; }
done
grep -q 'hasSearchTokens' "$lands/LandListScreen.kt" || { echo "the screen does not use hasSearchTokens" >&2; exit 1; }
if grep -q 'query.isNotBlank()' "$lands/LandListScreen.kt"; then
  echo "the filtered scope must follow hasSearchTokens, not isNotBlank" >&2
  exit 1
fi
```
<!-- verify:end -->

The block proves compile, the pure summary/search behaviour, the state reset rules, the string/plurals
inventory, the design-component adoption and pixel stability of both hosts. It cannot judge whether the
Spanish summary is understood by a person with low digital confidence, screen-reader output, or a real
2× text device; those stay manual and are recorded as limits.

## Appendix

Repository research, the ordered implementation plan, verification plan, evidence to capture and the
validator checklist: [`land_search_and_summary.appendix.md`](land_search_and_summary.appendix.md).
