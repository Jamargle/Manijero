# Feature Spec: `app_chrome_navigation`

## Source metadata

- **Feature:** `app_chrome_navigation` — add the app bar and adaptive navigation shell (`client`).
- **Status at planning:** `not_started`; depends on accepted `ui_component_library`.
- **Source behavior:** put the existing shared screens inside one shell: a brand top app bar, three
  top-level destinations (Mis terrenos, Asistente, Ayuda, in that tab order), a bottom bar on compact
  windows and a labelled navigation rail from 840 dp, real window-inset ownership, and predictable
  back rules. The duplicate top-level `Mis terrenos` / `Volver` controls are removed because the tabs
  now own navigation; forms keep `Cancelar`. No screen content is restyled.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md) §3.5, §4.1
  ("App shell"), §5.1, §5.3 ("Volver removed once tabs exist"), §5.8, §8 P0-17…P0-19;
  `DESIGN.md` "Shared component layer" and "Layout and interaction".
- **Decisions recorded at planning (2026-10-25):** the top app bar has **no** right-side action
  (privacy stays reachable from the chat footer and the help screen); the navigation bars are
  **hidden** on add/edit/remove forms so a draft cannot be abandoned by a stray tab tap.
- **Acceptance record:** [`docs/validations/app_chrome_navigation.md`](../validations/app_chrome_navigation.md)
  (created at acceptance); planning and verification detail is in the
  [appendix](app_chrome_navigation.appendix.md).

## Goal and boundaries

Give the app one navigation frame so the existing chat, lands and help screens are peers instead of
screens reached through ad-hoc text buttons. The shell owns window insets and the selected
destination; the screens keep their own content, copy, state and accessibility behavior.

**In scope**

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/AppShell.kt`: the `Scaffold` shell with the
  brand top bar, adaptive bottom bar / rail, inset handling and a content slot.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/AppNavigation.kt`: pure section, tab-index,
  navigation-visibility and back-target rules plus their unit tests.
- `App.kt`: tab state, route wiring, system back, and the removal of the chat `Mis terrenos` button.
- Removal of the now-duplicate visible `Volver` on `LandListScreen` and `CoverageScreen`.
- New navigation/app-title strings; removal of the unused `land_list_back` key.
- Shell screenshot goldens on both hosts and re-recording of the app goldens the button removals
  intentionally change.
- Durable rules in `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and the resolved
  top-bar decision in `docs/design/ui-refresh-plan.md`.

**Non-goals**

- No visual restyle of any screen: no cards, chips, callouts, hero block, composer, land fields,
  summary, search or source-card redesign. Those belong to `chat_screen_refresh`,
  `lands_screens_refresh`, `help_privacy_refresh`, `land_measurement_fields` and
  `land_search_and_summary`.
- No new glyph, icon size, colour, shape, spacing token, font, module, `material-icons-*` entry,
  Compose navigation library or adaptive-layout library. The one added artifact is the first-party
  `org.jetbrains.compose.ui:ui-backhandler` at the project's Compose version, because it supplies the
  common back API (implementation finding below).
- No top-bar privacy action, profile/avatar entry, deep link, two-pane layout, window min/default
  size, animation system, or iOS release work.
- No change to the answer contract, land context, clarification, retry semantics, local store, or
  privacy disclosure.
- No removal of the privacy screen's own `Volver`; it stays a detail route with a visible return.
- No claim of device, screen-reader, or product-owner acceptance beyond the evidence actually run.

## Job story

When I open the app on a phone or on my computer, I want to land on my saved lands and still see the
assistant and the help page as equal places I can move between, with the same calm header everywhere,
so I do not have to remember which text link opens what and I never lose a half-filled land form by
accident.

## Acceptance scenarios

1. **One shell, three places.** On Android and Desktop the app renders a top app bar with the 32 dp
   brand mark and the visible title `Manijero`, then the selected screen inside the shell. Compact
   windows (`< 840 dp`) show a bottom bar with `Mis terrenos`, `Asistente`, `Ayuda` from left to
   right; windows at `>= 840 dp` show a labelled rail on the left in the same order and no bottom
   bar. Selection is the Material indicator plus the heavier label, never colour alone.
2. **Tabs are the only top-level navigation.** With a local land store injected the app opens on
   `Mis terrenos` (the saved lands are read once before the first list frame); without a store it
   opens on `Asistente`. Selecting a tab shows that section; the conversation state and the loaded
   land snapshot survive tab switches. The chat's `Mis terrenos` button no longer exists, and the
   lands list and help screen no longer show a `Volver`. Forms keep `Cancelar`; the privacy screen
   keeps its `Volver`.
3. **Lands entry still reads safely.** Entering `Mis terrenos` from the chat tab performs the same
   guarded local read as before, so a failed read shows the existing failure notice with
   `Reintentar`, never a false empty list. After an add, edit or remove the list refreshes exactly as
   today.
4. **No repository, no dead tab.** When `App` is composed without a `LandRepository` (iOS scaffold
   and previews), the `Mis terrenos` destination is omitted; `Asistente` and `Ayuda` remain. A
   selected index can never point at a missing destination.
5. **Forms are focused.** On add, edit and remove, the bottom bar/rail is hidden and the top app bar
   remains; the form's own `Cancelar` and the Android back action return to `Mis terrenos` without
   saving. The shell does not add a second back/close control.
6. **Back rules.** Android system back from `Mis terrenos` returns to `Asistente`; from `Ayuda`
   returns to the tab it was entered from (on launch that is `Mis terrenos` when a local store is
   injected and `Asistente` otherwise, and `Ayuda` never returns to itself); from a form returns to
   `Mis terrenos`; from `Privacidad` returns to the section it was opened from; from `Asistente`, and
   from `Mis terrenos` after the rule above, the platform default applies (the app can exit). Back
   never leaves a stale selected tab or an invisible destination. Desktop gets the same route
   changes through visible controls (`Cancelar`, `Volver`, tab selection); no OS back gesture is
   claimed.
7. **Insets have one owner.** The shell owns the top, bottom and horizontal system insets and the
   ime inset; the top app bar, bottom navigation and rail render inside the safe area on Android and
   on desktop windows. Content is not double-padded, and the shell never draws under the status bar
   or navigation bar. Screens keep their existing scroll and padding.
8. **Theme-only, presentational reuse.** The shell composes only the accepted
   `ManijeroTopAppBar`, `ManijeroBottomNavigation` and `ManijeroNavigationRail`; it declares no hex
   or `Color(0x…)` literal, no new colour/shape/spacing value, and no screen-domain import inside
   the `design/` layer. All visible shell copy comes from `strings.xml`.
9. **Accessible labels.** Every tab keeps its visible label; every interactive target is at least
   48 dp with Material's focus indication; the top app bar title and brand mark are not announced as
   a status; the brand mark stays decorative. Keyboard order on Desktop follows top bar → rail/bottom
   bar → screen content without trapping focus.
10. **Honest visual evidence.** Desktop and Android host suites add exactly four `app_shell_*`
    captures each (compact light assistant, wide dark lands, wide light help, compact large-text
    assistant). The app goldens changed only by the two intentional button removals are re-recorded
    after review; no unrelated golden is rewritten. The screenshot document states the new counts
    and keeps its "host render only, no device/accessibility proof" limits.
11. **Scope discipline.** No backend, contract, knowledge, store, script, token, vector, entry-point
    or unrelated document change, and no Gradle change beyond pinning the first-party
    `ui-backhandler` artifact the common back API needs.

## Technical approach

- **Navigation model.** Extract the small route vocabulary out of `App.kt` into `AppNavigation.kt`:
  `AppSection { Lands, Assistant, Help }` (tab order),
  `AppDestination { Chat, LandList, AddLand, EditLand, RemoveLand, Privacy, Coverage }`,
  `availableSections(landsAvailable)`,
  `tabForDestination(destination)`, `navigationVisible(destination)`,
  `sectionDestination(section)` and `backTarget(destination, previousSection)`. The functions are
  pure and unit-tested; `Privacy` resolves to the section the person came from, so it never clears
  the selected tab.
- **Shell.** `AppShell` owns a `Scaffold` and a `BoxWithConstraints` using the existing
  `WideWindowBreakpoint` (840 dp). It builds the `ManijeroDestination` list from
  `app_title`/`nav_*` strings and `ic_chat`/`ic_lands`/`ic_help`, resolves the selected index with
  `selectedDestinationIndex`, and passes the scaffold padding to its content slot. The top bar is
  wrapped so its flat surface paints behind the status bar; the bottom bar is wrapped so its surface
  paints behind the navigation bar; the wide rail sits beside the content. `imePadding()` is applied
  by the shell so the bottom bar stays above the keyboard.
- **Routes.** `App` keeps the existing destination state plus the current section and the previous
  non-help section. The initial destination is `LandList` when a repository is injected and `Chat`
  otherwise; the launch list is hydrated once with the same guarded read so the empty state never
  flashes. Tab selection maps a section to its destination and triggers `readLands()` when entering
  `LandList` from another section. Privacy records the destination it was opened from
  (`privacyReturn`). Forms keep the section at `Lands` and hide the bars.
- **System back.** Use `androidx.compose.ui.backhandler.BackHandler`, opt in to its experimental
  annotation, and compose it only when `backTarget(...)` is non-null. **Implementation finding
  (2026-10-25):** the API is not on `commonMain`'s compile classpath through `compose.ui` — it lives
  in `org.jetbrains.compose.ui:ui-backhandler`, which `material3` resolves only at runtime. The
  feature therefore pins that first-party artifact at the project's Compose version. No platform
  `expect/actual` and no third-party library; back support is not dropped.
- **Screen changes are deletions only.** Drop `onLandsClick` and its button from
  `ChatHomeScreen`; drop `onBack` and the `Volver` control from `LandListScreen` and
  `CoverageScreen`. Keep every other control, heading, preview state and semantics untouched. Update
  all previews and screenshot fixtures that used the removed parameters.

## Expected file changes

- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/AppShell.kt` and `AppNavigation.kt`.
- **Add** `shared/src/commonTest/kotlin/com/jamarglex/manijero/AppNavigationTest.kt`.
- **Add** Desktop and Android `AppShellScreenshotsTest.kt` classes plus four `app_shell_*.png`
  goldens per host.
- **Update** `App.kt`, `lands/LandListScreen.kt`, `coverage/CoverageScreen.kt`, the two host
  screenshot classes and their fixtures as needed, and the intentionally changed app PNGs.
- **Update** `gradle/libs.versions.toml` and `shared/build.gradle.kts` with the single first-party
  `ui-backhandler` artifact (implementation finding above).
- **Update** `shared/src/commonMain/composeResources/values/strings.xml` (`app_title`,
  `nav_assistant`, `nav_lands`, `nav_help`; remove `land_list_back`).
- **Update** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`,
  `docs/design/ui-refresh-plan.md`.
- After acceptance: `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, the
  appendix, and the acceptance record.
- **Not changed:** `privacy/PrivacyScreen.kt` behavior, `theme/`, `composeResources/drawable/`,
  Android/Desktop entry points, the rest of the Gradle/version catalog, `backend/`, `contracts/`,
  `knowledge/`, `design-references/`.

## Visual design impact

The shell is the first adoption of the component layer and must read as one calm frame: the flat
`surfaceContainerLowest` top bar with the olive brand mark and `Manijero`, the flat bottom bar/rail
with visible labels and a non-colour selection cue, the 720 dp content column unchanged inside, and
no shadow. At 840 dp the rail replaces the bottom bar on the left. No legal, verification, status or
eligibility meaning is added by the chrome. The brand mark stays identity only.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record the adopted shell: brand-only top bar (no action), adaptive bars at 840 dp, tab labels, forms hide navigation, back rules, and the shell as the single inset owner. |
| `CONSTRAINTS.md` | Update | Add the durable rule that the shell owns insets and tabs own top-level navigation, so later screens cannot re-add duplicate routes or a second inset owner. |
| `docs/screenshot-regression.md` | Update | Add the four shell captures per host and the new 18 Desktop / 14 Android counts; keep the host-only limits. |
| `docs/design/ui-refresh-plan.md` | Update | Mark open decision §12.2 resolved (no top-bar action) and record P0-17…P0-19 delivery; the plan stays a historical design input, not a behavior contract. |
| `ARCHITECTURE.md` | Not needed | The shell stays inside `shared` `commonMain`; no module, dependency direction or runtime boundary changes. |
| `AGENTS.md` | Not needed | Existing UI/skill routing covers shell work. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/session-log.md` | Update after independent acceptance | Keep the accepted set, evidence pointers and open manual checks honest. |

## Focused verification

The block compiles and unit-tests the navigation model, verifies both host screenshot suites (the
shell goldens are the visual evidence), and enforces the scope rules. It needs the Android SDK for the
Robolectric suite. It is read-only apart from Gradle output.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest
./gradlew :shared:verifyScreenshots
root="$REPO_ROOT/shared/src/commonMain/kotlin/com/jamarglex/manijero"
test -f "$root/AppShell.kt" || { echo "missing AppShell.kt" >&2; exit 1; }
test -f "$root/AppNavigation.kt" || { echo "missing AppNavigation.kt" >&2; exit 1; }
test -f "$REPO_ROOT/shared/src/commonTest/kotlin/com/jamarglex/manijero/AppNavigationTest.kt" || { echo "missing navigation tests" >&2; exit 1; }
grep -q 'internal fun AppShell(' "$root/AppShell.kt" || { echo "missing AppShell declaration" >&2; exit 1; }
for key in app_title nav_assistant nav_lands nav_help; do
  grep -q "name=\"$key\"" "$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml" || { echo "missing string: $key" >&2; exit 1; }
done
if grep -q 'name="land_list_back"' "$REPO_ROOT/shared/src/commonMain/composeResources/values/strings.xml"; then
  echo "unused land_list_back string remains" >&2; exit 1
fi
if grep -rq 'onLandsClick' "$root"; then
  echo "a duplicate chat lands route remains" >&2; exit 1
fi
if grep -qE '\bonBack[[:space:]]*[:=]' "$root/lands/LandListScreen.kt" "$root/coverage/CoverageScreen.kt"; then
  echo "a duplicate top-level Volver remains" >&2; exit 1
fi
if grep -q 'onPrivacyClick' "$root/AppShell.kt"; then
  echo "the app bar must not expose a privacy action" >&2; exit 1
fi
if grep -rnE 'Color\(0x|#[0-9A-Fa-f]{3,8}' "$root/AppShell.kt" "$root/AppNavigation.kt" --include='*.kt'; then
  echo "raw colour literal in the shell" >&2; exit 1
fi
for shot in app_shell_assistant_compact_light app_shell_lands_rail_dark app_shell_help_rail_light app_shell_assistant_compact_large_text; do
  test -f "$REPO_ROOT/shared/src/jvmTest/screenshots/$shot.png" || { echo "missing Desktop golden: $shot" >&2; exit 1; }
  test -f "$REPO_ROOT/shared/src/androidHostTest/screenshots/$shot.png" || { echo "missing Android golden: $shot" >&2; exit 1; }
done
test "$(find "$REPO_ROOT/shared/src/jvmTest/screenshots" -name 'app_shell_*.png' | wc -l | tr -d ' ')" = "4" || { echo "unexpected Desktop shell capture count" >&2; exit 1; }
test "$(find "$REPO_ROOT/shared/src/androidHostTest/screenshots" -name 'app_shell_*.png' | wc -l | tr -d ' ')" = "4" || { echo "unexpected Android shell capture count" >&2; exit 1; }
if grep -q 'material-icons' "$REPO_ROOT/gradle/libs.versions.toml"; then
  echo "an icon-font dependency was added" >&2; exit 1
fi
```
<!-- verify:end -->

The block proves compile, the pure navigation rules, the scope gates and pixel stability. It cannot
judge whether the shell reads well at 2× text on a device, whether Android back feels right while the
keyboard is open, or whether a screen reader announces the tabs as intended; those are the manual
checks recorded in the appendix and acceptance record.

## Appendix

See [`app_chrome_navigation.appendix.md`](app_chrome_navigation.appendix.md) for repository research,
the ordered implementation plan, evidence to capture and the validator checklist.
