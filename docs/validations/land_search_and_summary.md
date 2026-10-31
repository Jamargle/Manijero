# Validation: `land_search_and_summary`

**Verdict: accept** — 2026-10-25

Independent validation against [`land_search_and_summary.md`](../specs/land_search_and_summary.md),
its [appendix](../archive/specs/land_search_and_summary.appendix.md) checklist and evidence, the four
confirmed product decisions recorded in the spec, `CONSTRAINTS.md`, `DESIGN.md`, `CONTEXT.md`,
`docs/domain-model.md`, `docs/risks-and-open-questions.md`, `docs/screenshot-regression.md` and
`PROGRESS.md`, in the `land_search_and_summary` worktree (branch
`feature/land_search_and_summary`, base `6ac20d0`). Two validation passes were run: the first
returned **revise** with one blocking finding (F1) and four lower ones; after the repair pass the
second returned **accept**. No code change was required after the second pass; three documentation
wording notes from it were folded into the spec, appendix and `DESIGN.md` in the acceptance commit.

## What was checked

### The four confirmed product decisions

1. **Text-only search (decision 1).** `filterLands` (`lands/LandSearch.kt`) builds the searchable
   text from name, zone, municipality, the variety text (the custom `Otra` text for
   `LandVariety.OTHER`, otherwise its resolved label), the water-regime label and the
   production-method label, and nothing else. `LandSearchTest` asserts no match for `85`, `1,5`,
   `1.5`, `2,5`, `land-1`, `aceituna` and an epoch timestamp on a land that carries all of them,
   and a match for each listed text field, every resolved label (including `Mezcla de variedades`,
   `Una parte de cada uno` and `No lo sé`) and the custom `Otra` text.
2. **Summary over the current result set (decision 2).** `LandListScreen` summarizes
   `summarizeLands(matches)`, where `matches = filterLands(state.lands, query, labels)`, so a blank
   query summarizes every saved land and an active query only the matches. `LandSummaryTest`
   "a filtered subset counts only the lands it received" pins the derivation; the new
   `land_list_search_filtered` golden (both hosts) shows the filtered frame with
   `1 de 2 terrenos guardados`, `Sin datos` + `0 de 1 terreno encontrado con superficie` and
   `Sin datos` + `0 de 1 terreno encontrado con olivos`; the appendix records the four reachable
   ratios observed (1 of 1, 1 of N, N of N, 0 of N).
3. **Wording (decision 3).** `strings.xml` ships `Superficie anotada` and `Olivos anotados`; both
   values carry an `x de y` caption and `Sin datos` replaces the value when nothing is annotated.
   No card can render `0 ha` or `0 olivos`: `LandSummary.surfaceTotal`/`treeTotal` are `null`
   exactly when their known count is `0`, and `LandSummaryTest` "an absent value is never a zero
   and no total is derived from another attribute" pins it in both directions.
4. **Empty store (decision 4).** `state.isEmpty` renders the shared `ManijeroEmptyState` with the
   decorative olive branch, `Aún no tienes terrenos añadidos`, the new body and exactly one primary
   `Añadir terreno` action inside the state; no summary and no search field are composed in that
   branch. Both `land_list_empty_dark` goldens (Desktop wide and phone, Android) show it, and the
   retired `land_list_empty` key has no remaining reference in `shared/src`.

### Contract scenarios 1–10

| # | Exercised by | Result |
|---|---|---|
| 1 empty store, one Add action | both empty goldens per host, `isEmpty` branch, `LandListStateTest` | pass |
| 2 honest summary over all lands | `LandSummaryTest` (3 lands → `2,25`, `1 285`, counts 2/2), `land_list_light` goldens, recorded rendered copy | pass |
| 3 absent values never zero | `LandSummaryTest` null totals + `Int.MAX_VALUE` `Long` sum, `Sin datos`/`0 de 3` and `0 de 1` rendered copy, previews | pass |
| 4 summary follows the result set | filtered captions + scope line, `land_list_search_filtered` goldens, no cards on empty match | pass |
| 5 text-only match | `LandSearchTest` measures/ids/notes/timestamp cases | pass |
| 6 accents, `ñ`, case, punctuation, emoji | `LandSearchTest` fold and token cases; `hasSearchTokens` decides the scope so a tokenless query never shows filtered copy | pass (after repair) |
| 7 repository order, untouched rows | `LandSearchTest` order/duplicate cases; `LandRow`/`LandDetails` diff unchanged; goldens show the same rows and controls | pass |
| 8 no-results recoverable | `land_list_search_no_results` goldens (both hosts), named clear action in the field and in the panel, Add above the panel | pass |
| 9 query is display state only | `LandListStateTest` ×4 (keeps lands/order; cleared by load, failure and reload), `grep` shows no store/payload/log/chat reference, no `Land`/`LandDraft` change | pass |
| 10 scope | diff review: only `lands/`, `App.kt`, `strings.xml`, its tests, four screenshot classes/fixtures, the lands/shell goldens and the durable docs | pass |

### Verification re-run independently

| Tier | Command | Result |
|---|---|---|
| Focused | `./scripts/init.sh --feature land_search_and_summary` | exit `0`; all static gates passed; `verifyDesktopScreenshots` 20 + `verifyAndroidScreenshots` 16 = 36 captures |
| No-device | `./scripts/init.sh --fast` | exit `0`; contract examples, `All 9 offline checks passed.`, backend pytest skipped (absent, no backend change) |
| Full | `./scripts/init.sh --verify` | exit `0`; `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build` |
| Forced unit rerun | `./gradlew :shared:jvmTest --rerun-tasks` | `266` tests / `27` classes, 0 failures (`LandSummaryTest` 8, `LandSearchTest` 11, `LandListStateTest` 10, `LandFieldsTest` 11) |
| Forced host rerun | `./gradlew :shared:testAndroidHostTest --rerun-tasks` | `252` tests / `23` classes, 0 failures |

Golden discipline: re-running both record tasks reproduced all 36 images byte for byte; `git status`
lists exactly the 8 re-recorded goldens and the 4 new ones (`land_list_search_no_results` and
`land_list_search_filtered` per host); the other 34 PNGs are unchanged by git.
`docs/screenshot-regression.md` states 20 Desktop / 16 Android (36 PNGs) with correct arithmetic.

### Pure layer, state and boundary

- `lands/LandSummary.kt` and `lands/LandSearch.kt` contain no Compose, platform or resource import
  (static gate), own no copy and add no second formatter: the surface total is formatted with
  `formatHectares`, the tree total through the widened `formatTreeCount(Long)` entry point (the
  `Int` overload delegates, so one grouping implementation remains).
- `LandListScreen` composes `ManijeroSectionHeader`, `ManijeroStatCard` (three, 1 column below
  `WideWindowBreakpoint`, 3 above, measured on the window), `ManijeroSearchField`,
  `ManijeroEmptyState` and `ManijeroCard`; no component was restyled, no token/colour/shape was
  added, and the land rows keep their accepted content.
- The query lives only in `LandListState` (appended, defaulted) and changes through
  `LandListAction.QueryChanged`; the three read actions still build a fresh state, so every read
  starts blank. No `AskRequest`, `MinimalLandContext`, privacy, `contracts/`, `backend/`,
  `knowledge/`, Gradle, platform entry-point or navigation file changed.

### Documentation

`DESIGN.md` (lands bullet), `docs/domain-model.md` (new derived-only note), `CONTEXT.md` (two terms
+ review date), `CONSTRAINTS.md` (new "Land list search and summary" block with `Reason:` lines),
`docs/risks-and-open-questions.md` (two Medium risks) and `docs/screenshot-regression.md` (counts and
the two new states) match the shipped behaviour. `ARCHITECTURE.md` and `AGENTS.md` are untouched with
the stated reason. `docs/design/ui-refresh-plan.md`, `docs/specs/land_list.md` and every earlier
acceptance record are unmodified.

## Findings

### First pass (revise)

- **F1 (blocking, repaired).** `LandListScreen` decided the filtered copy with
  `state.query.isNotBlank()`, while `filterLands` treats a punctuation/emoji-only query as blank, so
  the rows were unfiltered but the summary claimed a search — contradicting contract scenario 6 and
  the new `CONSTRAINTS.md` rule. Repair: `hasSearchTokens(query)` in `lands/LandSearch.kt`, reusing
  the same private tokenizer, used by the screen and pinned by a new `LandSearchTest` case.
- **F2 (low, repaired).** A collapsed test signature/first statement in `LandListStateTest` was split.
- **F3 (low, repaired).** The filtered count caption pluralized on the saved total but carried a verb,
  so 2 saved / 1 match rendered `1 de 2 guardados coinciden con la búsqueda.` Repair: the filtered
  count caption is now a verbless noun phrase keyed on the saved total
  (`1 de 2 terrenos guardados`), the surface/tree captions stay keyed on the shown match count they
  print, and the search relation is stated once in `land_summary_scope_filtered`. Every reachable
  ratio now agrees.
- **F4 (low, repaired).** The count card now formats its value with `formatTreeCount(summary.total)`
  instead of `toString()`; no pixel changes at today's fixtures.
- **F5 (observation, accepted as a limit).** The typing/clear paths were proven by temporary
  interaction probes the implementer deleted; no permanent Compose interaction test exists. Recorded
  as a limit rather than expanded scope.

### Second pass (accept)

- No blocking or behavioural finding. Three documentation wording notes were applied in the
  acceptance commit: the spec's self-summary and scenario 10 now name both new goldens per host; the
  spec/appendix caption sentence now describes the filtered count caption as the one caption that
  prints two counts; `DESIGN.md` no longer claims every card carries an `x de y` caption.
- One observation is left as input to the later land comprehension/accessibility work: a filtered
  count card reads label `Terrenos guardados`, value = match count, caption `1 de 2 terrenos
  guardados`; the scope line disambiguates it, but the label plus value alone could be skimmed as
  "1 saved land".

## Honest limits

- No interactive Desktop or emulator walkthrough was performed during validation; the typed, cleared
  and no-results paths were exercised through the Compose Desktop test harness by the implementer
  (temporary probes, since deleted) and are otherwise covered by the pure/state tests and goldens.
- No screen-reader audit: the search field is labelled, its clear action is named, and the no-results
  panel is deliberately not a live region, but none of it was heard with assistive technology.
- No real-device 2× text measurement and no 2× lands golden; the large-font preview compiles only.
- No iOS run; no user-comprehension evidence for `anotado`, the `x de y` captions or the search hint.
  These remain approved product decisions, not findings.
- The 839/840 dp boundary is argued from `WideWindowBreakpoint` and the captures on each side, not
  from a width sweep; the filtered golden proves the copy renders, not that a person reads
  `1 de 2` as "of the shown set".
- Backend pytest was unavailable in this environment; no backend file changed.
