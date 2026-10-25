# Feature Appendix: `app_chrome_navigation`

Planning and verification record for
[`app_chrome_navigation.md`](app_chrome_navigation.md). The contract holds the bounded implementation
instructions; this appendix holds the research, the ordered plan, the evidence to capture and the
validator checklist.

## Repository research (2026-10-25, worktree base `4405b71`)

### Current shell and routes

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` is the composition root and the only
  route owner: a private `AppDestination { Chat, LandList, AddLand, EditLand, RemoveLand, Privacy,
  Coverage }`, one `destination` state, one `previousDestination` state for privacy/coverage
  cross-links, and one `ManijeroTheme` around the whole `when`. There is no `Scaffold`, app bar,
  tab state, or system back handling.
- The chat screen is `ChatHomeScreen` in the same file. It renders its own title block, transcript,
  suggestions, composer, a `Mis terrenos` `TextButton`, a privacy summary, and `Privacidad y ayuda`
  + `Qué cubre la app` text links. Its `onLandsClick: (() -> Unit)?` is null when no repository is
  injected.
- `lands/LandListScreen.kt` renders its own heading (`chat_home_lands`), rows, add/edit/remove
  controls, and a full-width `Volver` (`land_list_back`) calling `onBack`.
- `coverage/CoverageScreen.kt` renders the help content, a privacy cross-link, and a full-width
  `Volver` (reusing `privacy_back`) calling `onBack`.
- `privacy/PrivacyScreen.kt` renders the notice with its own `Volver` (`privacy_back`) and a
  coverage cross-link. It is a detail route, not a tab; this feature leaves it unchanged.
- `lands/AddLandScreen.kt`, `EditLandScreen.kt`, `RemoveLandScreen.kt` already expose `Cancelar`
  and use `onCancel`; they never had a `Volver`. The shell will hide its bars on those routes.

### Accepted component layer this feature adopts

- `design/navigation/ManijeroTopAppBar.kt`: flat `surfaceContainerLowest` bar, 32 dp
  `ManijeroBrandMark`, caller title, optional privacy action (omitted when the callback is null),
  1 dp `outlineVariant` divider, no window insets, 48 dp targets.
- `design/navigation/ManijeroNavigation.kt`: `ManijeroDestination(label, icon)`,
  `ManijeroBottomNavigation`, `ManijeroNavigationRail`, `selectedDestinationIndex`, visible labels,
  indicator + heavier label, 48 dp targets, `WindowInsets(0)`.
- `design/ManijeroScreen.kt`: `WideWindowBreakpoint = 840.dp` and `screenHorizontalPadding`; the
  screen wrapper is not adopted by the existing screens yet, so the shell must not assume it.
- `theme/ManijeroTokens.kt`: `ManijeroLayout.ContentMaxWidth`, `MinTouchTarget`, spacing and border
  tokens. No new token is needed.
- The shared component rule in `CONSTRAINTS.md` forbids domain imports, copy ownership, raw colours
  and missing accessible names inside `design/`. The shell composes those components from outside
  `design/`, so it may own `Res.string` lookups and navigation state.

### Strings, icons and tests

- `shared/src/commonMain/composeResources/values/strings.xml` has `chat_speaker_assistant`
  ("Asistente"), `chat_home_lands` ("Mis terrenos"), `coverage_title` ("Qué puedes preguntar"),
  `privacy_back` ("Volver") and `land_list_back` ("Volver"). The plan's copy inventory reserves
  `app_title`, `nav_assistant`, `nav_lands`, `nav_help` (and `nav_privacy`, not needed after the
  no-action decision). `land_list_back` becomes unused when the lands `Volver` is removed.
- The sixteen brand glyphs already include `ic_chat`, `ic_lands`, `ic_help`; no vector work.
- `shared/src/jvmTest/.../screenshots/` has 14 Desktop goldens; `shared/src/androidHostTest/...`
  has 10. Existing app scenes render `ChatHomeScreen`/`LandListScreen` directly, not `App`, so the
  new shell needs its own capture class. `ScreenshotFixtures.kt` already provides idle/answered chat
  and populated/empty lands. `docs/screenshot-regression.md` documents the read-only verify and
  explicit record tasks and the host-only limits.
- `App.kt` contains roughly thirty `@Preview` composables that call `ChatHomeScreen` with
  `onLandsClick = {}`; removing the parameter requires updating every call site.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/` is where the pure navigation test belongs;
  JUnit 4 is the current runner for these Kotlin tests and no new test dependency is needed.
- `androidx.compose.ui.backhandler.BackHandler` is present in the transitive
  `org.jetbrains.compose.ui:ui:1.12.1` graph (`ui-backhandler` artifacts exist for Android, Desktop
  and iOS). It is `@ExperimentalComposeUiApi` and deprecated in favour of `NavigationEventHandler`,
  so the implementation must opt in and suppress the deprecation locally. Compose Desktop 1.12.1
  provides the `NavigationEventDispatcherOwner` through its host-default provider, so the common
  call should not fail on Desktop; this is a point to verify, not an assumption to hide.

### Gap analysis against the target

| Target (plan) | Current | Work in this feature |
|---|---|---|
| `Scaffold`, insets, tab state | none; edge-to-edge entry point | new `AppShell`, inset wrappers, section/route state |
| Brand app bar, no action (decision) | no bar | compose `ManijeroTopAppBar(title = app_title)` |
| Bottom bar `< 840`, rail `>= 840` | no navigation | compose existing navigation components |
| Tabs Asistente / Mis terrenos / Ayuda | text buttons and `Volver`s | new `nav_*` strings, section mapping |
| Remove duplicate top-level controls | chat button + two `Volver`s | delete button/params; keep form `Cancelar` and privacy `Volver` |
| Android back rules | system back exits from any route | pure `backTarget`, common `BackHandler` |
| Screenshot evidence | screen-only captures | four shell captures per host + intentional re-records |

## Implementation plan and tasks

Ordered; stop and record a blocker if a step contradicts the contract.

1. **Navigation model.** Add `AppNavigation.kt` with `AppSection`, `AppDestination`,
   `availableSections`, `tabForDestination`, `navigationVisible`, `sectionDestination`,
   `backTarget` and `previousSectionFor` (or equivalent small pure helpers). Keep `AppDestination`
   private to the module (`internal`). No Compose import in this file.
2. **Unit tests first.** Add `AppNavigationTest.kt` covering: three sections with lands available,
   two without; tab index for each destination; `-1`/nothing for privacy via the remembered
   section; navigation hidden only on add/edit/remove; back targets for chat (null), lands list,
   each form, help (from assistant and from lands), and privacy handled by its recorded return;
   no destination maps outside the available list.
3. **Strings.** Add `app_title` ("Manijero"), `nav_assistant` ("Asistente"), `nav_lands`
   ("Mis terrenos"), `nav_help` ("Ayuda"). Remove `land_list_back`. Keep `privacy_back` (privacy
   screen) and `chat_home_lands` (lands heading).
4. **Shell.** Add `AppShell.kt` in the root package. It takes the selected `AppSection`, whether
   navigation is visible, the on-select callback, and a content slot. It resolves the available
   destination list, strings and icons; renders `Scaffold` + `BoxWithConstraints`; wraps the top bar
   for the status bar and the bottom bar for the navigation bar; applies `imePadding`; uses the rail
   in a `Row` from 840 dp; passes the remaining padding to content. The top bar gets no action.
   Add light/dark/2× previews for compact and wide shells (preview-only screens are fine).
5. **Routes and state in `App.kt`.** Replace the bare destination state with section + destination +
   previous-section + privacy-return state. The launch destination is `LandList` when a repository is
   injected and `Chat` otherwise, and the launch list is hydrated with the same guarded read. Tab
   selection maps to a destination, triggers `readLands()` when entering lands, and clears transient
   confirmations as appropriate. Wrap the existing `when` content in `AppShell`. Hide the bars on
   form routes; privacy keeps them and its `Volver` continues to return to the recorded section. Add
   the conditional common `BackHandler`.
6. **Remove duplicate top-level controls.** Remove `onLandsClick` and its button from
   `ChatHomeScreen` and all preview call sites; remove `onBack` and `Volver` from
   `LandListScreen` (and its previews); remove `onBack` and `Volver` from `CoverageScreen` (and its
   previews). Do not alter any other control, copy, heading, spacing or semantics. Keep the chat
   footer privacy/help links and the privacy screen `Volver`.
7. **Screenshots.** Add `AppShellScreenshotsTest.kt` on Desktop and on Android, rendering real
   fixture screens inside the shell: assistant compact light, lands wide dark, help wide light,
   assistant compact 2× text light. The recorded implementation uses Desktop 360×800 for compact and
   900×1000 for the rail (the same 360×800 frame with `fontScale = 2f` for large text); Android uses
   `es-rES-w360dp-h800dp-mdpi` with a per-method `es-rES-w900dp-h1000dp-mdpi` override for the two
   rail captures and the same compact frame with `fontScale = 2f` for large text. This differs from
   the originally planned 1000×800 / 1400-high frames, chosen so the rail sits close to the 840 dp
   breakpoint and the large-text frame is the real phone height. Record the eight new PNGs and every
   intentionally changed existing PNG with the explicit record tasks, inspect each image, and verify
   read-only afterwards.
8. **Durable docs.** Update `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md` and the
   resolved decision in `docs/design/ui-refresh-plan.md` as the contract describes.
9. **Harness state.** Set the feature `in_progress`, run the focused block, `--fast`, `--verify`
   and the iOS simulator compile; record exact results in "Feature evidence"; set `passing` only
   when all required checks pass. Leave the acceptance record and `accepted` status to the
   orchestrator after independent validation.

## Verification plan

Cheapest first; record the exact command and result for each.

1. **Focused block (contract).** `./scripts/init.sh --feature app_chrome_navigation` — unit tests,
   both screenshot suites, static scope gates and golden inventory. Needs the Android SDK.
2. **No-device tier.** `./scripts/init.sh --fast`.
3. **Full gate.** `./scripts/init.sh --verify` — adds Android host tests and the Android/Desktop
   builds.
4. **Common-source purity.** `./gradlew :shared:compileKotlinIosSimulatorArm64` (the shell must stay
   reusable; the back handler is part of the common graph).
5. **Android emulator smoke.** `./scripts/init.sh --android-run`, then: tab switch across all three
   destinations; conversation text survives; lands list reads; add form hides the bars, back returns
   to the list without saving; privacy opens from the chat footer and `Volver` returns to chat;
   help tab; system back from lands/help/forms/privacy; status/navigation insets; keyboard open in
   chat; 2× font scale. Capture screenshots for the acceptance record.
6. **Desktop smoke.** `./scripts/init.sh --desktop` at a narrow and a wide window: bottom bar vs
   rail, tab switching, form `Cancelar`, privacy `Volver`, help cross-link, keyboard traversal.
7. **Screenshot review.** Open every new and changed PNG at full size; confirm the intended shell,
   Spanish labels, light/dark rendering, no clipping at 2× text, no half-painted frame. Record that
   the review was performed in this session; product-owner sign-off remains an open manual item.

Not available or not claimed: a persistent UI/E2E harness (none exists), screen-reader output
capture, iOS simulator run, real tablet/desktop-OS matrix, reduced-motion behavior, or product-owner
acceptance.

## Evidence to capture

- Focused block output and the pure test count.
- `--fast` and `--verify` results (task count, exit status, APK/jar sizes if printed).
- iOS simulator compile result.
- New/changed golden file list and the review note per image.
- Android emulator: route/back matrix observed, inset observations, keyboard and 2× text notes,
  screenshot paths or descriptions.
- Desktop: narrow/wide observation, keyboard traversal note.
- Any deviation from the plan and why (for example the exact `BackHandler` opt-in shape).

## Feature evidence

Implemented in worktree `app_chrome_navigation`, branch `feature/app_chrome_navigation`, from base
`4405b71`.

### Implementation findings and deviations

- **Back handler dependency.** `androidx.compose.ui.backhandler.BackHandler` is not on `commonMain`'s
  compile classpath through `compose.ui`; `material3` only resolves the artifact at runtime. Added
  the first-party `org.jetbrains.compose.ui:ui-backhandler` pinned to `composeMultiplatform`
  (`libs.versions.toml` alias `compose-uiBackhandler`, `shared/build.gradle.kts`). The contract's
  non-goal was amended to allow this one pinned artifact before this evidence was recorded.
- **Back handler shape.** `App` uses `@Suppress("DEPRECATION")` and
  `@OptIn(ExperimentalComposeUiApi::class)` because `BackHandler` is deprecated in favour of
  `NavigationEventHandler`. The handler is composed only when `backTarget(...)` is non-null, so
  assistant and lands-after-rule fall through to the platform default. No `expect/actual` and no
  third-party library was added.
- **Privacy selection.** `Privacy` has no tab of its own; `tabForDestination(privacy, fallback)`
  keeps the remembered `previousSection`, and `backTarget` returns the recorded `privacyReturn`.
  Help entered from help itself falls back to `Asistente` instead of returning to itself.
- **Screenshot viewports.** The recorded shell frames use 360×800 compact, 900×1000 rail and a
  360×800 `fontScale = 2f` large-text frame instead of the plan's 1000×1400 variants; the smaller
  capture is closer to the real device and still exercises the ≥840dp rail. The goldens show the
  same states; see the screenshot section below.
- **Privacy-to-help return.** Leaving privacy via its `Ver privacidad y ayuda` cross-link sets
  `previousSection = Coverage`'s tab (Help), so backing out of that privacy-originated help screen
  lands on Assistant rather than the previous tab. This is the `backTarget` no-self-return rule and
  is covered by the pure tests; it is documented here because it is not visible from the screens.
- **Three-control scope.** Otherwise no deviation from the ordered plan: the field-taking screens
  were changed only by deleting `onLandsClick`/`onBack` and their controls, and every
  preview/fixture call site was updated.

### Automated verification

| Command | Result |
|---|---|
| `./scripts/init.sh --feature app_chrome_navigation` | Exit 0. `:shared:jvmTest` 211 tests, 0 failures (13 in `AppNavigationTest`); `:shared:verifyScreenshots` 18 Desktop + 14 Android goldens, 4 `app_shell_*` per host; every static scope gate passed. |
| `./scripts/init.sh --fast` | Exit 0, `Fast tier passed`; 9 offline checks passed (shared host tests, contract examples, evaluators). Backend pytest was **skipped by the harness because pytest is not installed in this environment**; no backend code changed, so that gap is stated rather than hidden. |
| `./gradlew :shared:compileKotlinIosSimulatorArm64` | `BUILD SUCCESSFUL` (UP-TO-DATE, 2 executed / 9 up-to-date), so the shell and back handler remain in the common graph. |
| `./scripts/init.sh --verify` | Exit 0, `BUILD SUCCESSFUL` with 88 actionable tasks, including the Android host screenshot/Robolectric suite and the Android/Desktop assemblies. |

The focused block proves compile, the 13 route/back/selection rules, the grep scope gates and pixel
stability. It cannot judge reading comfort on a device; that is the manual evidence below.

### Validator repair: one content inset owner

Independent validation found that `AppShell` zeroed Scaffold's content insets and then applied only
the horizontal safe-drawing inset to the content row. Because the bottom-bar wrapper was skipped for
the wide rail and for the add/edit/remove forms, content could reach under the Android navigation bar
in those two states (acceptance scenario 7). Fixed in `AppShell.kt` by removing the custom
`contentWindowInsets = WindowInsets(0)` and the row's horizontal-only padding: Scaffold's default
system-bar insets now pad the content by the laid-out top/bottom bar height, or by the system-bar
inset when a bar is absent, and the rail and content share that padding.

Re-verified after the fix: focused block exit 0, `--verify` exit 0 (`BUILD SUCCESSFUL`, 88
actionable tasks), `:shared:compileKotlinIosSimulatorArm64` `BUILD SUCCESSFUL`, host goldens
unchanged. On the emulator at 914 dp (landscape, gesture navigation) the rail and the chat footer
stay above the navigation bar; on the compact add form `Guardar terreno` and `Cancelar` stay above
it; with the keyboard open the bottom bar sits directly above the IME with no extra gap.

### Post-acceptance change: `Mis terrenos` launches by default

After acceptance the owner asked that `Mis terrenos` be the default tab. `AppNavigation` gained
`initialDestination(landsAvailable)` and `initialSection(landsAvailable)`: the land list opens when a
local store is injected, and the assistant opens when it is not so the omitted lands tab can never be
the launch screen. `App` starts `previousSection` on that same tab and hydrates the initial
`LandListState` once with the same guarded fold as `readLands`, so the default list never flashes the
empty state before the store answers. Five pure navigation tests were added (default destination,
no-repository fallback, the launch tab is always in `availableSections`, and the two back-to-tab
cases), plus four `AppLaunchTest` cases pinning the hydration fold: no store, an empty store, saved
lands, and a store that refuses to answer (a failed read, never a false empty list). System back to a
top-level tab now also updates `previousSection`, so launch → back → `Ayuda` → back returns to
`Asistente` instead of the tab the app started on. Acceptance scenario 6 was clarified to name the
launch tab explicitly, and the `android_mvp_build`/`desktop_mvp_build` scenarios that still claimed a
chat-home launch were corrected.

Re-verified after the change: focused block exit 0 with 220 host tests (18 in `AppNavigationTest`,
four in `AppLaunchTest`), `--verify` exit 0 (`BUILD SUCCESSFUL`, 88 actionable tasks), iOS simulator
compile `BUILD SUCCESSFUL`, and no golden changed (the shell captures pass an explicit section). On
the Android emulator the app opens with `Mis terrenos` selected, shows the saved land after a
force-stop and relaunch, still switches tabs normally, and back → `Ayuda` → back returns to
`Asistente`; the Desktop app also opens on `Mis terrenos`.

### Post-acceptance change: `Mis terrenos` is the leftmost tab

The owner then asked that `Mis terrenos` be the first tab, followed by `Asistente` and `Ayuda` in
that order. `AppSection` now declares `{ Lands, Assistant, Help }` and `availableSections` filters
that declaration (`Lands` still disappears without a local repository), so the compact bottom bar
and the wide rail both lay out those tabs left to right/top to bottom. A new pure test pins the
three tab positions and asserts the existing expected order. The four shell goldens per host were
re-recorded through `recordDesktopScreenshots`/`recordAndroidScreenshots` with `--tests
AppShellScreenshotsTest` and reviewed: the bar shows `Mis terrenos`, `Asistente`, `Ayuda` with the
lands pill on the left, and the rail lists the same order. No other golden regressed.

Re-verified after the reorder: focused block exit 0 with 221 host tests (19 in `AppNavigationTest`),
`--verify` exit 0 (`BUILD SUCCESSFUL`, 88 actionable tasks), iOS simulator compile `BUILD
SUCCESSFUL`. On the Android emulator the first tab is `Mis terrenos` (its selected pill covers the
left third of the bar), followed by `Asistente` and `Ayuda`, and the app still launches on the saved
`La Loma by` list. The wide rail's longest label still sits flush against the window edge at the
default rail width, exactly as in the accepted rail goldens; the reorder did not change the rail
width or the already-recorded 2× wrap limit.

### Screenshot review (performed 2026-10-25)

New and recorded (8 images, opened at full size): Desktop
`app_shell_assistant_compact_light`, `app_shell_lands_rail_dark`, `app_shell_help_rail_light`,
`app_shell_assistant_compact_large_text`; the same four names under
`shared/src/androidHostTest/screenshots/`. They show the flat `Manijero` top bar with the brand mark,
the correct bar or rail, the Material indicator plus heavier selected label, Spanish labels, light
and dark rendering, and no half-painted frame.

Changed existing goldens (10 images, opened and reviewed): Desktop `chat_home_idle_light`,
`chat_home_idle_light_phone`, `chat_answered_source_dark`, `land_list_light`, `land_list_light_phone`,
`land_list_empty_dark`, `land_list_empty_dark_phone`; Android `chat_home_idle_light`,
`land_list_light`, `land_list_empty_dark`. Each differs only by the removed chat `Mis terrenos`
button or the removed lands `Volver`; no other visual regression was observed.

Honest limit: at 2× text on a 360 dp compact shell the labels stay visible but wrap — `Asistente`
breaks across two lines and `Mis terrenos` wraps. This is pre-existing accepted
`ManijeroBottomNavigation` behavior (the same wrap is in the accepted
`component_gallery_narrow_large_text_*` goldens), not something this feature changed or claims to
fix. Product-owner sign-off on screenshots remains an outstanding repo item.

### Android emulator smoke

Observed on an emulator through the normal debug install/launch flow:

- Tabs switch between `Asistente`, `Mis terrenos` and `Ayuda`; the selected destination is visibly
  selected; conversation text and the loaded land snapshot survive tab switches.
- Entering `Mis terrenos` reads the local store; an existing land renders; the list has no `Volver`.
- Add form hides the bottom bar; `Cancelar` and system back both return to `Mis terrenos` without
  saving, and the top bar remains.
- System back: lands → assistant; help → the tab it was entered from; privacy → the section it was
  opened from; assistant → platform default (app exits).
- Chat footer opens privacy and its `Volver` returns to chat; the chat footer still reaches help.
- Keyboard open in chat keeps the bottom bar above the keyboard; insets are not double-applied.
- At 2× system font the shell bars and labels remain visible; nothing is clipped off-screen.
- Limits: manual observation only; no screen-reader output capture and no UI/E2E harness exists.

### Desktop smoke

- Launched with `./scripts/init.sh --desktop`. At an 800 dp-wide window the bottom bar shows; resizing
  to 1100×800 swaps to the labelled rail with no bottom bar, and the content column keeps its width.
- Pointer activation of the rail's `Mis terrenos` opens the saved land list, selected indicator
  correct (captured during the session).
- Keyboard order observed: `Asistente` → `Mis terrenos` → `Ayuda` (bottom bar) → screen content;
  Enter on the focused `Ayuda` tab activated it. No shell focus trap was observed. The pre-existing
  multiline chat composer consumes Tab once it holds focus (Shift+Tab leaves it); this feature did
  not change the composer and does not claim to fix it.
- Forms and privacy were exercised on Android through the same `commonMain` code; no separate
  keyboard-only form run is claimed here.

## Validator checklist

- [ ] `feature_list.json` shows `app_chrome_navigation` as `passing` before validation, with the
      contract and appendix paths unchanged.
- [ ] The diff implements only the contract: shell, pure navigation, route/back wiring, the three
      duplicate-control removals, strings, tests, goldens and named docs.
- [ ] `AppShell` composes the accepted top bar / bottom bar / rail and owns no copy or colour of its
      own beyond `strings.xml` and theme roles; no raw colour literal; no new token, glyph, module or
      library beyond the pinned first-party `ui-backhandler` artifact the contract allows.
- [ ] The app bar has no right-side action; privacy remains reachable from the chat footer and help
      screen, and its `Volver` still returns to the section it was opened from.
- [ ] Tabs are Asistente / Mis terrenos / Ayuda when lands are available and omit lands when no
      repository is injected; selected index resolves safely; labels stay visible.
- [ ] Navigation is hidden on add/edit/remove; forms keep `Cancelar`; back from a form returns to
      the lands list without writing.
- [ ] Back rules match acceptance scenario 6, including back from help returning to the tab it was
      entered from and back from chat/lands-after-rule using the platform default.
- [ ] The chat `Mis terrenos` button and the lands/help `Volver` controls are gone with no dead
      parameter, string or preview; no other screen behavior changed.
- [ ] Insets have one owner: status/navigation bars and ime are handled by the shell; content is not
      double padded; screens keep their scroll and existing padding.
- [ ] Four new shell goldens exist per host; changed existing goldens are only the intentional
      button removals; the screenshot document counts and limits are accurate; every image was
      opened and reviewed, with product-owner sign-off honestly marked outstanding if absent.
- [ ] `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md` and the plan's resolved decision
      match the implementation; `ARCHITECTURE.md`/`AGENTS.md` unchanged with the stated reason.
- [ ] Focused block, `--fast`, `--verify`, iOS compile and the manual smoke are recorded with exact
      results; failures or missing checks are stated, not hidden.
- [ ] No backend, contract, knowledge, store, entry-point or out-of-scope feature changed; the only
      Gradle change is the pinned `ui-backhandler` artifact; no accepted validation record was
      rewritten.
