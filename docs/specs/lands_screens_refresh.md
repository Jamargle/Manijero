# Feature Spec: `lands_screens_refresh`

## Source metadata

- **Feature:** `lands_screens_refresh` — Refresh the land screens (`client`).
- **Status at planning:** `not_started`; depends on accepted `app_chrome_navigation` and
  `land_search_and_summary`.
- **Source behavior:** Preserve local land management and its accepted data/state rules while adapting
  the list, add, edit, and remove surfaces to the accepted shared design system and app shell.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md), P2-09…P2-14 and
  §§5.3–5.4; [`DESIGN.md`](../../DESIGN.md), “Shared component layer” and layout rules; accepted
  [`land_search_and_summary`](land_search_and_summary.md) and `land_measurement_fields` contracts.
- **Source verification:** Empty/populated/search-no-results list, safe land-specific actions,
  confirmation/load-error feedback, add/edit forms and destructive confirmation, across compact and
  wide layouts without changing saved values or navigation behavior.
- **Acceptance record:** [`docs/validations/lands_screens_refresh.md`](../validations/lands_screens_refresh.md)
  (created at acceptance); planning and evidence detail is in the
  [appendix](../archive/specs/lands_screens_refresh.appendix.md).

## Goal and boundaries

Make local land management feel like one calm, consistent flow: a useful list, forms that group the
existing fields clearly, and a deletion confirmation that is unmistakably destructive. Reuse the
accepted shared components; do not change what a land means, what is saved, or where navigation goes.

**In scope**

- Adopt `ManijeroScreen`, `ManijeroCard`, `ManijeroSectionHeader`, `ManijeroCallout`,
  `ManijeroAttributeChip`, `ManijeroIcon`, shared spacing/shape tokens, and the existing screen
  strings as appropriate for the list, add, edit and remove screens.
- Preserve the accepted `land_search_and_summary` empty/populated/no-results branches and summary,
  search scope, ordering, actions, and local-only behavior.
- Restyle populated land rows with chips for known water, production and variety values; clearly
  describe unknown values without repeating bare `No lo sé` chips. Keep rows non-clickable and retain
  separate, named Edit and Remove controls.
- Keep add and edit field order, validation, prefilled values, unknown selections, and save/cancel
  behavior. Group the existing fields for legibility without hiding any field or changing its data.
- Present removal identity and consequence in a danger treatment with a safe, explicit cancel action.
- Add focused interaction/screenshot coverage and update only the goldens intentionally changed by
  these land screens.

**Non-goals**

- No changes to `Land`, `LandDraft`, validation, repository/store format, search/summary rules,
  `AskRequest`, `MinimalLandContext`, or backend/API behavior.
- No new fields, copy claims, icons, colors, tokens, dependencies, modules, routes, shell behavior,
  or platform entry-point changes. No mapping, eligibility, verification, or measured-data claims.
- No changes to chat, help/privacy, theme foundations, design-system components, or unrelated
  screenshot baselines. Do not claim a real-device, screen-reader, or owner review unless performed.

## Job story

When I manage my saved olive lands, I want to find and understand each record, change its details, or
remove the right one without confusing actions or losing my place, so I can manage my own information
with confidence.

## Acceptance scenarios

1. **List states remain truthful.** Given no lands, a populated list, a load failure, or a search with
   no results, when the lands tab is displayed, then each state retains the accepted content and
   behavior: empty state has one Add action and no search/summary; populated state retains the summary,
   search, Add action and rows; no-results retains clear-search and Add; load failure offers retry.
2. **Rows are readable and actions are separate.** Given a land with known and unknown attributes,
   when its row renders, then its exact saved name and known details are visible, known attributes use
   the accepted chips, unknowns are plainly described, and the row itself is not clickable. Its Edit
   and Remove controls remain distinct, reachable, and accessible by action plus land name.
3. **List behavior is unchanged.** Given saved lands, when searching, summarizing, editing, removing,
   or retrying, then the accepted filter fields, Spanish folding, result order, summary denominators,
   clear behavior, and query-reset rules remain unchanged. A row action alone does not mutate storage.
4. **Add and edit preserve the form contract.** Given either form, when rendered at compact or wide
   width, then it uses one scrollable shared frame, preserves the accepted field order and values,
   identifies required name/zone in words, exposes every optional field including unknown choices, and
   retains validation, first-invalid focus, save-error feedback, save and cancel behavior. Edit starts
   with the stored values and does not silently discard them.
5. **Removal is safe.** Given a selected land, when the removal screen is shown, then its identity and
   irreversible consequence are clear, the destructive action uses the danger treatment, and Cancel
   is an explicit safe choice. Cancel performs no delete; confirmation invokes the existing remove
   callback for exactly that land.
6. **Feedback and navigation remain accepted.** Given successful add/edit/remove or a load/save error,
   when feedback is shown, then existing plain-Spanish strings and polite announcements remain; forms
   retain their shell/back and Cancel behavior, and no duplicate top-level navigation is introduced.
7. **Responsive presentation remains usable.** Given compact phone width, 2× text, or a wide Desktop
   window, when each land screen renders, then content stays centred and readable, actions do not
   overlap or disappear, and wide layouts use the accepted responsive patterns rather than stretching
   a phone layout. Light and dark appearance use theme colors only.
8. **Scope and evidence are controlled.** Given the feature diff, when reviewed, then storage/domain
   contracts and unrelated screens are untouched, screenshot changes are limited to intentionally
   reviewed land captures, and any host-only/manual limitations are stated accurately.

## Technical approach

- Keep all product UI in `shared/src/commonMain`. Use `ManijeroScreen` as the single scroll/frame
  owner; do not add insets or bars because `AppShell` owns them.
- Apply shared cards, callouts, chips, icons, spacing and shape tokens at the screen call sites; do
  not add domain behavior or copy to `design/`.
- Keep list search, summary, state, strings, and `LandDetails` semantics as accepted. Resolve localized
  attribute labels in composables and pass them to presentational UI; unknown data remains unknown.
- Keep add/edit state/action/reducer/repository boundaries intact. Reuse shared field components where
  already used; group fields visually with headings/cards only where this improves scanability and
  does not hide or reorder existing information.
- Keep removal confirmation driven by the existing selected land and callback. Danger styling must
  not make the destructive action the default focus or merge it with Cancel.
- Add or update durable screenshot fixtures/tests for the affected states; inspect changed images
  before recording. Retain pure state/repository tests as the authority for behavior.

## Expected file changes

- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`,
  `AddLandScreen.kt`, `EditLandScreen.kt`, and `RemoveLandScreen.kt`.
- **Update as needed:** focused `shared/src/commonTest` or `shared/src/jvmTest` UI tests,
  `shared/src/commonTest/.../screenshots/ScreenshotFixtures.kt`, Desktop/Android screenshot tests and
  only affected PNG baselines under the two host screenshot directories.
- **Update durable docs:** `DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, and the
  delivery note in `docs/design/ui-refresh-plan.md`; update open-risk wording only if evidence changes.
- **After independent acceptance:** `feature_list.json`, `PROGRESS.md`,
  `docs/progress/session-log.md`, this appendix's evidence, and the acceptance record.
- **Not expected:** land model/repository/state/search/summary logic, resources/copy, `App.kt`,
  `AppShell.kt`, `AppNavigation.kt`, `design/`, `theme/`, chat/help/privacy, Gradle, platform entry
  points, backend, contracts, or knowledge. Any exception requires a concrete contract reason.

## Visual design impact

The land list adopts the shared page frame, cards, chips, and summary/search components already
specified and accepted. Forms become easier to scan without changing their content or validation.
Removal gets a clear danger surface while retaining a visibly safe cancel route. Follow `DESIGN.md`
for tokens, spacing, contrast, accessibility and wide-window behavior; no new visual vocabulary is
introduced.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record the adopted land-list, form and removal presentation rules. |
| `CONSTRAINTS.md` | Update | Preserve durable rules for truthful land attributes, safe delete, and non-clickable rows. |
| `docs/screenshot-regression.md` | Update | Record changed/added land captures and accurate host counts/limits. |
| `docs/design/ui-refresh-plan.md` | Update | Mark P2-09…P2-14 delivered and record any intentional deviation. |
| `ARCHITECTURE.md` | Not needed | No module, dependency direction, or data boundary changes. |
| `AGENTS.md` | Not needed | Existing UI routing and skills cover this work. |
| `docs/risks-and-open-questions.md` | Update only if needed | Keep manual accessibility/owner checks outstanding unless actually completed. |
| `PROGRESS.md`, `feature_list.json`, `docs/progress/session-log.md` | Update after acceptance | Record status and evidence only after independent validation. |

## Focused verification

The focused block exercises shared host tests and screenshot baselines, then ensures the scope remains
within the named screens. Review captured images manually; screenshot verification alone is not a
usability or accessibility audit.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest
./gradlew :shared:verifyScreenshots
```
<!-- verify:end -->

## Appendix

See [`lands_screens_refresh.appendix.md`](../archive/specs/lands_screens_refresh.appendix.md) for repository research,
implementation tasks, screenshot targets, evidence and validator checklist.
