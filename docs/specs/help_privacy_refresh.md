# Feature Spec: `help_privacy_refresh`

## Source metadata

- **Feature:** `help_privacy_refresh` — Refresh the help and privacy screens (`client`).
- **Status at planning:** `not_started`; dependencies `ui_component_library` and `land_measurement_fields` are accepted.
- **Source behavior:** Preserve the meaning, navigation and disclosure facts of the existing help/coverage and privacy screens while adapting both to the shared visual language; add no new links.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md), P2-15…P2-16 and §§5.3–5.4; [`DESIGN.md`](../../DESIGN.md), shared component/layout/accessibility rules; [`coverage_and_help`](coverage_and_help.md) and [`land_data_disclosure`](land_data_disclosure.md).
- **Source verification:** Inspect coverage and privacy content/navigation on Android and Desktop; verify existing disclosure text/facts, links, and back behavior remain correct while the new card/callout treatment is readable in compact, wide, dark and large-text layouts.
- **Feature-list note:** P2-15 specifies help cards plus a limits callout with the same content and no new links; P2-16 specifies privacy cards and a local-only section whose copy matches the accepted disclosure facts. This is visual adaptation, not a new product disclosure.
- **Acceptance record:** [`docs/validations/help_privacy_refresh.md`](../validations/help_privacy_refresh.md) (created at acceptance); planning/evidence detail is in the [appendix](../archive/specs/help_privacy_refresh.appendix.md).

## Goal and boundaries

Make the existing `Ayuda` coverage disclosure and privacy notice feel like one clear, calm shared-design experience without changing what either screen says, what information is disclosed, or where any control navigates.

**In scope**

- Restyle `CoverageScreen` and `PrivacyScreen` using accepted `ManijeroScreen`, `ManijeroCard`, `ManijeroSectionHeader`, `ManijeroCallout`, `ManijeroIcon` and existing tokens/components as appropriate.
- Maintain all pinned coverage topics, non-coverage limits, human-help referral wording, privacy notice copy and the exact shared-land-attribute list.
- Make the coverage limits visually prominent but informational: no new promise, legal claim, contact detail, or status implication.
- Present privacy's on-device/local-only facts clearly and consistently with `land_data_disclosure` and the fields in `land_measurement_fields`; do not imply backup, cloud sync, or that local data is sent.
- Keep existing links and actions: privacy ↔ coverage and their existing return behavior. Add no new route or external link.
- Add focused screenshot coverage for both surfaces, including light/dark host renders where current harness supports them; update only intentionally reviewed target images.

**Non-goals**

- No change to disclosure facts, existing strings, coverage topic scope, shared-attribute mapping, routes, destination state, shell, or callbacks.
- No new data model, persistence, request fields, backend/knowledge changes, analytics, feedback, welcome gate, external referral details, or legal advice.
- No new design tokens, icons, dependencies, modules, or design-library behavior; no platform-specific UI.
- Do not claim usability, accessibility, device rendering, or owner approval from previews or host goldens alone.

## Job story

When I read what the assistant can help with or how my land information is handled, I want the important points to be easy to find and understand, so I can use the app without mistaking its limits or privacy practices.

## Acceptance scenarios

1. **Coverage meaning is preserved.** Given the help/coverage screen, when it renders, then all currently pinned covered topics, explicit limits, and human-help wording remain present and substantively unchanged; the limits callout adds emphasis only and does not promise answers or imply legal certainty.
2. **Privacy facts are preserved.** Given the privacy screen, when it renders, then existing statements about local storage, question data, shared land attributes, unknown values, and what is not sent remain accurate and complete; the shared attribute list continues to derive from the exhaustive accepted mapping.
3. **Navigation is unchanged.** Given either screen, when the person activates its existing privacy/coverage link or return control, then the same destination and originating section are restored as before; no new links or routes appear.
4. **Shared responsive presentation.** Given compact width, 2× text, or wide Desktop, when either screen renders, then content scrolls without clipping, remains centred/capped per the shared 720 dp frame, and the controls remain visible/reachable. Light and dark use theme tokens only.
5. **Accessible structure.** Given either screen, then headings are semantic headings, content is not conveyed by color alone, controls retain meaningful names and usable targets, and any manual keyboard/screen-reader claims are supported by observed evidence.
6. **Scope is controlled.** Given the feature diff, then only the two target screens, focused screenshot/test artifacts, and durable design/constraint/plan documentation change; `App` routing, disclosure copy/resources, land/request behavior, knowledge/backend/contracts, and platform entry points remain unchanged.

## Technical approach

- Keep both screens in `shared/src/commonMain`; follow the current app shell's single inset ownership and use `ManijeroScreen` as the page-frame/scroll owner (do not add bars or insets).
- Apply existing presentation components at screen call sites. Keep coverage topics and privacy attribute mapping/content owned by their current domain/content sources, not the component library.
- Preserve all resource keys and copy verbatim. If the existing copy does not support a proposed visual grouping, retain the current content order rather than editing copy.
- Use a neutral informational limits callout; no caution/danger color or icon may imply that the topics are warnings or that other answers are verified.
- Preserve privacy's precise distinction between device-local land records and the limited attributes included with a question; never suggest newly added land fields are sent.
- Add/update focused screen captures and persistent interaction/structure coverage only where existing test patterns support it. Inspect changed images before recording; screenshots are not accessibility evidence.

## Expected file changes

- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageScreen.kt` and `privacy/PrivacyScreen.kt`.
- **Update as needed:** focused `shared/src/commonTest` tests, `screenshots/ScreenshotFixtures.kt`, Desktop/Android screenshot tests and only affected PNG baselines under host screenshot directories.
- **Update durable docs:** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and delivery note in `docs/design/ui-refresh-plan.md`.
- **Not expected:** `App.kt`, `AppNavigation.kt`, coverage/privacy content or strings, land data/reducers/store, API payloads, Gradle, platform entry points, backend, contracts, or knowledge. Any exception needs a contract-level reason; content changes are out of scope.

## Visual design impact

Both existing informational surfaces adopt the shared screen frame, cards, section headings and callouts. Use neutral surfaces and theme roles; coverage limits remain explanatory, not a warning or guarantee. Preserve readable prose, headings, scrolling, the privacy/coverage cross-link and return actions. Follow `DESIGN.md` for 720 dp centring, light/dark, large text, contrast and accessible semantics.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record the adopted help/privacy presentation rules and link to this feature contract. |
| `CONSTRAINTS.md` | Update | Preserve factual coverage/privacy copy, local-only distinction and no-new-links behavior across future restyles. |
| `docs/screenshot-regression.md` | Update | Record any changed/added help/privacy captures and accurate host counts/limits. |
| `docs/design/ui-refresh-plan.md` | Update | Record P2-15…P2-16 delivery/deviations; keep historical plan status factual. |
| `ARCHITECTURE.md` | Not needed | No module, dependency direction, or data boundary changes. |
| `AGENTS.md` | Not needed | Existing shared UI and privacy rules cover the work. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/session-log.md` | Update after independent acceptance | Status/evidence workflow; do not mark accepted during implementation. |

## Focused verification

Run shared tests and screenshot verification. Review changed images; report unrelated existing golden failures separately and do not re-record unrelated captures.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest' --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellHelpRailLight'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyAndroidScreenshotsTest' --tests 'com.jamarglex.manijero.screenshots.AppShellScreenshotsTest.appShellHelpRailLight'
```
<!-- verify:end -->

## Appendix

See [`help_privacy_refresh.appendix.md`](../archive/specs/help_privacy_refresh.appendix.md) for repository research, ordered implementation tasks, verification/evidence plan and validator checklist.
