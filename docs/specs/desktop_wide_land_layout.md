# Feature Spec: `desktop_wide_land_layout`

## Source metadata

- **Feature:** `desktop_wide_land_layout` — Apply the approved wide-window layout to land screens (area: `client`), `not_started` at planning (2026-10-21).
- **Depends on:** `desktop_land_layout_decision`, `land_list`, `edit_land`, `remove_land`, `land_data_disclosure` — all accepted.
- **Source behavior:** On Desktop wide windows, land list, add/edit/remove flows, and the privacy/data disclosure use a centred column capped at 720dp; narrower windows use available width.
- **Source verification:** Build shared host and Desktop app; manually inspect representative narrow and wide Desktop window geometries for listed screens, and ensure Android/shared behavior is unchanged.
- **Source note:** Approved by `desktop_land_layout_decision`; closes accepted H1 finding recorded in `PROGRESS.md`, `DESIGN.md`, and `docs/risks-and-open-questions.md`.
- **Scope size:** One bounded shared-UI layout correction across related screens; correctly sized.

## Goal

Apply the existing chat layout policy consistently: land list, add land, edit land, remove confirmation, and privacy/data-handling notice content have a maximum width of 720dp and are horizontally centred when the host offers more width. On narrower windows content occupies available width without horizontal overflow. Preserve scrolling, content, navigation, state, accessibility semantics, and mobile behavior.

## Non-goals

- No change to chat, coverage/help screen, or unrelated screens.
- No content, typography, spacing, colors, form behavior, land data, navigation, or privacy-policy changes.
- No Desktop-only fork, new dependency, design system, or user research claim.
- No automated UI/E2E harness creation; none exists currently.

## Job story

When I manage my lands or read the data-handling notice in a wide Desktop window, I want the content centred in a readable column rather than stretched across the window, so it is easier to scan and consistent with the chat screen.

## Acceptance scenarios

### Wide window column

Given a Desktop window substantially wider than 720dp, when I open Mis terrenos, Añadir terreno, Editar terreno, Eliminar confirmation, or the privacy notice, then the visible content is in a horizontally centred column no wider than 720dp.

### Narrow window behavior

Given a window narrower than 720dp, when I open any named screen, then its content uses the available inner width, remains vertically scrollable, and has no horizontal overflow or clipping.

### Existing behavior preserved

Given any named screen at narrow or wide size, when I use its existing controls, then content, actions, navigation, validation, semantics, and state transitions are unchanged; Android remains unaffected.

## Technical approach

Keep implementation in shared `commonMain`. Current screens each place a width-limited inner column inside a full-width vertically scrolling outer column. Correct the parent/child sizing and centring order (or use a small shared layout helper if it reduces duplication) so the capped child is centred within the available parent width. Apply consistently to `LandListScreen`, `AddLandScreen`, `EditLandScreen`, `RemoveLandScreen`, and `PrivacyScreen`, including every privacy section and back action. Avoid changing outer scrolling/padding or nesting that causes scroll regressions. Reuse the existing 720dp cap; no platform-specific condition is required.

## Expected file changes

- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`
- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`
- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`
- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandScreen.kt`
- **Update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt`
- Add/update previews or tests only if useful and consistent with existing patterns; do not add a UI-test dependency.

## Visual design impact

Wide Desktop content becomes a centred, max-720dp readable column. At narrow sizes, retain available width and current 24dp horizontal/32dp vertical page padding. No other visual or behavioral changes are authorized. Verify at least one viewport wider than 720dp and one narrow viewport; account for actual window density when reporting dp/pt measurements.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | **No evidence update** | Keep durable layout intent here; record implementation measurements and verification limits in this feature's validation record and the risks register. |
| `docs/risks-and-open-questions.md` | **Update** | Mark the H1 implementation question resolved, retaining evidence limits if appropriate. |
| `ARCHITECTURE.md` | **Not needed** | No module or ownership boundary changes. |
| `CONSTRAINTS.md` | **Not needed** | No durable MUST/MUST NOT rule changes. |
| `AGENTS.md` | **Not needed** | No workflow changes. |
| `PROGRESS.md`, `feature_list.json` | **Not in implementation** | Status changes follow the planner/implementer/validator harness; do not mark accepted without validation. |

## Focused verification

The focused block runs shared JVM tests and Desktop build: it exercises common code and compiles the target host. Manual geometry inspection remains required because no persistent GUI/E2E harness exists.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :desktopApp:build
```
<!-- verify:end -->

## Appendix

Repository findings, ordered implementation tasks, manual verification/evidence, and validator checklist are in [`desktop_wide_land_layout.appendix.md`](../archive/specs/desktop_wide_land_layout.appendix.md).
