# Validation: `app_chrome_navigation`

**Verdict: accept** — 2026-10-25

Independent validation against [`app_chrome_navigation.md`](../specs/app_chrome_navigation.md), its
appendix checklist, `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and
`PROGRESS.md` in the `app_chrome_navigation` worktree (base `4405b71`). One required inset defect was
found in the first pass and fixed before acceptance; the re-check passed.

## What was checked

- **Contract and route model.** The shell renders the flat brand top app bar with the visible
  `Manijero` title and no right-side action, then the selected screen; compact windows show the
  bottom bar and windows at 840 dp or more show the labelled rail with no bottom bar. `AppSection`
  omits `Lands` when no repository is injected, and `selectedDestinationIndex` can never point at a
  missing destination. `AppNavigation.kt` has no Compose import and 13 tests cover availability, tab
  mapping, bar visibility and every back target.
- **Top-level navigation only.** The chat `Mis terrenos` button and the lands/help `Volver` controls
  are gone with no dead `onLandsClick`/`onBack` parameter, string or preview; `chat_home_lands` still
  heads the list and `privacy_back` still serves the privacy screen. Forms keep `Cancelar`, hide both
  navigation bars, and leave the top app bar; privacy keeps its `Volver`.
- **Launch route (post-acceptance change).** With a local store injected the app opens on
  `Mis terrenos` and reads the saved lands before the first list frame; without a store it opens on
  `Asistente`, so the omitted lands tab is never the launch screen.
- **Land read and return rules.** Every land read stays guarded and unlogged: `readLands()` runs on
  entering lands from another section, on retry, and after save/edit/remove, while the default
  launch hydrates the same state once. A failed read still shows `Reintentar`, never a false empty
  list. Privacy records both entry points and returns to the section it was opened from; help never
  returns to itself; a form's back and `Cancelar` both abandon the draft without writing.
- **Insets and accessibility.** The shell is the single inset owner: the bar wrappers paint behind the
  status/navigation bars, Scaffold's system-bar padding covers the content when a bar is absent, and
  ime is handled once. Tabs keep visible labels, 48 dp targets, the indicator plus heavier label, and
  decorative brand marking. The first pass found the content could reach under the navigation bar on
  the wide rail and on forms; the fix and re-check are recorded below.
- **Screenshots and docs.** Both host suites add exactly four `app_shell_*` captures each, for 18
  Desktop and 14 Android images; the ten re-recorded app goldens changed only by the intended button
  removals. `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md` and the resolved plan
  decision match the shipped shell; `ARCHITECTURE.md`/`AGENTS.md` were correctly left untouched.
- **Scope.** No backend, contract, knowledge, store, entry point, token, vector or script change; the
  only Gradle change is the contract-permitted first-party `org.jetbrains.compose.ui:ui-backhandler`
  pin at the project's Compose version.

## Verification (independently run)

| Command | Result |
|---|---|
| `./scripts/init.sh --feature app_chrome_navigation` | exit 0 — `:shared:jvmTest` 211 tests / 0 failures (13 navigation), both host golden suites re-executed and matched, every static scope gate passed |
| `./scripts/init.sh --fast` | exit 0 — `Fast tier passed`; 9 offline checks passed; backend pytest skipped because pytest is not installed (documented harness behaviour) |
| `./scripts/init.sh --verify` | exit 0 — `BUILD SUCCESSFUL`, 88 actionable tasks, including the Android host suite and the Android/Desktop assemblies |
| `./gradlew :shared:compileKotlinIosSimulatorArm64` | `BUILD SUCCESSFUL` — the shell and common back API stay in the iOS graph |
| `git status` / golden mtimes / re-executed screenshot tasks | the 8 new shell goldens are the only additions; the 10 re-recorded app goldens predate the fix and still verify pixel-identically; no unrelated image moved |

Not re-run: the manual emulator/Desktop walkthrough is an implementer observation (it is not
reproducible headless); backend pytest is skipped only because pytest is absent. Neither is claimed
as independent evidence.

## Findings

Required fix (resolved before acceptance): `AppShell` zeroed Scaffold's content insets and applied
only a horizontal safe-drawing padding to the content row. Because the bottom-bar wrapper is absent
on the wide rail and on add/edit/remove forms, content could reach under the Android navigation bar
in those two states, against acceptance scenario 7. `AppShell` now uses Scaffold's default system-bar
insets and passes `innerPadding` to the rail/content row, so the bottom inset is the laid-out bar
height when a bar exists and the navigation-bar inset otherwise. Re-verified: focused block,
`--verify`, iOS compile and the host goldens; on the emulator the landscape rail/chat footer, the
compact form's `Guardar terreno`/`Cancelar`, and the bar above an open keyboard all stay clear of the
system bar with no extra gap.

Low notes applied to the docs: the shell is described as owning system-bar (not safe-drawing)
horizontal insets, and the privacy-to-help return note names the existing `Ver privacidad y ayuda`
cross-link. No further code change was required.

Post-acceptance change (same day): the owner asked that `Mis terrenos` be the default tab. `App` now
derives its launch destination from the repository (`Mis terrenos` when one is injected, `Asistente`
otherwise), starts `previousSection` on the same tab, and hydrates the initial land list with the
same guarded fold once, so the empty state is not flashed before the store answers. `AppNavigation`
gained `initialDestination`/`initialSection` with five new tests, and `AppLaunchTest` pins the
hydration fold (no store, empty store, saved lands, refusing store) in four more. System back to a
top-level tab now also updates `previousSection`, so `Ayuda` after back returns to the tab the person
is on rather than the launch tab. Acceptance scenario 6 was clarified to name the launch tab, and the
two MVP build specs that still claimed a chat-home launch were corrected.

Re-verified after the change: focused block exit 0 (220 host tests, 18 navigation, 4 launch),
`--verify` exit 0 (88 tasks), iOS compile `BUILD SUCCESSFUL`, host goldens unchanged. On the emulator
the app launches on the selected `Mis terrenos` tab and shows the saved land after a force-stop and
relaunch; back from `Mis terrenos` reaches `Asistente`; the Desktop app also opens on `Mis terrenos`.
This changes the user-visible entry point in the contract and `DESIGN.md`; the tabs, back rules,
forms and inset ownership are otherwise unchanged.

Post-acceptance tab-order change (same day): the owner asked for `Mis terrenos` to be the leftmost
tab, followed by `Asistente` and `Ayuda`. `AppSection` is now declared in that tab order and
`availableSections` filters it, so the compact bar and wide rail both start with `Mis terrenos`; a
new pure test pins the three positions. The four shell goldens per host were re-recorded and
reviewed for the new order. Re-verified: focused block exit 0 (221 host tests, 19 navigation),
`--verify` exit 0 (88 tasks), iOS compile `BUILD SUCCESSFUL`, and on the emulator the first tab is
`Mis terrenos` with its selected pill, still opening on the saved list. The rail's longest label
remains flush with the window edge at the existing rail width, a pre-existing observation recorded
in the appendix, not a new defect from the reorder.

Declared limits, accepted as scope boundaries:

- At 2× text on a 360 dp compact shell the bottom-navigation labels remain visible but wrap
  (`Asistente` breaks across two lines). This is pre-existing accepted `ManijeroBottomNavigation`
  behavior, not changed by this feature.
- Screenshot evidence is host renders only; product-owner sign-off on the 32 host images remains an
  outstanding manual item.
- The multiline chat composer consumes Tab once focused (Shift+Tab leaves it); this is pre-existing
  chat behavior, not a shell focus trap.

## Honesty boundaries

- Host renders are Desktop macOS-font-pinned and Robolectric SDK 35 at density 1, `es-ES`, plus one
  2× text frame; no real tablet, desktop-OS matrix, screen-reader output capture, or automated UI/E2E
  harness was used.
- The emulator and Desktop smoke observations are manual and cover one emulator, one Android size
  plus a landscape/rail state, and one Desktop window resized across the breakpoint.
- Backend pytest was not exercised (pytest absent); no backend file changed.
- Product-owner visual acceptance and the long-standing low-digital-confidence comprehension check
  are not claimed here.

## Security

No finding. No new network, storage, permission, logging or platform entry point; the land read
(including the one-time launch hydration) is guarded and unlogged; route and draft state stay local
UI state; the single dependency addition is the contract-permitted first-party `ui-backhandler`;
privacy remains reachable from the chat footer and help, with its own `Volver` returning to the
recorded section.

## Handoff

- `feature_list.json`: `app_chrome_navigation` is `accepted`.
- `PROGRESS.md`: accepted set and the 18 Desktop / 14 Android capture table updated; the sign-off
  item now covers 32 images; the 2× label-wrap and host-render limits are recorded.
- `docs/progress/session-log.md`: one pointer line added.
- Next dependent feature: `chat_screen_refresh` (and `lands_screens_refresh` after
  `land_search_and_summary`), both able to build on the accepted shell.
