# Appendix — `desktop_land_layout_decision`

## Repository research

Inspected directly (paths relative to repository root):

- `AGENTS.md`, `PROGRESS.md`, `feature_list.json`: project requires shared UI in `commonMain`; `desktop_land_layout_decision` is not started and its follow-up is `desktop_wide_land_layout`. Progress records H1: chat alone has the capped/centred column.
- `DESIGN.md`: layout direction calls for adapting Desktop to form factor, comfortable scanning, simple screens, and a 720dp cap is documented and measured for chat. It explicitly records the land list, forms, and privacy notice as uncapped/full-width on wide windows (H1). Design says this is pre-existing, not a defect already fixed.
- `docs/risks-and-open-questions.md`: implementation-time question asks whether the lands list/forms and privacy notice should share chat's cap; cites H1.
- `docs/specs/desktop_mvp_build.md` and `.appendix.md`: prior accepted Desktop smoke and H1 record establish 720dp chat width, the full-width land/privacy behavior, shared Compose ownership, and lack of an automated UI harness.
- `ARCHITECTURE.md`: UI and behavior belong in `shared/src/commonMain`; host-specific entry points remain platform-specific.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: routes to land list and privacy screens; chat uses a centred `ContentMaxWidth = 720.dp` column.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`, `AddLandScreen.kt`, `EditLandScreen.kt`, `RemoveLandScreen.kt`, `privacy/PrivacyScreen.kt`: existing screens use width constraints but do not apply the parent centring behavior; matches H1. Their individual screen implementations should be inspected by the follow-up implementer before choosing the minimal common layout seam.

No target-user research or fresh runtime measurement was performed for this decision. The approval is a consistency and readable-layout policy decision grounded in the existing accepted chat baseline and documented design direction, not a demonstrated user preference.

## Implementation plan and tasks

This feature creates a decision, not UI. The authorized follow-up `desktop_wide_land_layout` should:

1. Inspect current screen/root layout composition and determine the smallest shared `commonMain` seam that applies the same max-width and centring consistently.
2. Apply a maximum width of 720dp, centred horizontally, to the land list, add/edit/remove screens, and privacy/disclosure screen(s) named by that follow-up contract.
3. Preserve available-width behavior on narrower windows, vertical scrolling, accessibility semantics, all screen content, and Android behavior.
4. Add/update previews or available host-level checks where practical; no Compose UI-test harness is present, so report visual/manual checks honestly.
5. Verify at a narrow viewport and a wide viewport (wide enough to exceed 720dp): narrow layout must not overflow; wide layout must render a centred column no wider than 720dp. Do not claim automated GUI validation without an actual harness.

## Verification plan

For this decision artifact, run the exact focused command in the contract and `git diff --check`. Manually review that the contract says yes, names all four land-management screens plus privacy, distinguishes wide/narrow behavior, and records the evidence limitation. No app build is necessary because this slice changes no source.

For the follow-up implementation, use its focused build/test commands and manual wide/narrow Desktop inspection. Existing repository baseline: `./scripts/init.sh --feature <feature-id>` runs contract-published commands; no persistent UI/E2E harness is available.

## Evidence to capture

- Contract check exit status and `git diff --check` result.
- The implementation follow-up should capture before/after or measured content widths and horizontal positions at a narrow and wide Desktop window, noting host/measurement method and any accessibility or capture limitations.

## Feature evidence

- 2026-10-21: `./scripts/init.sh --feature desktop_land_layout_decision` passed; the published contract assertions confirmed the explicit yes decision, 720dp cap, implementation follow-up, and no-Compose-implementation boundary.
- 2026-10-21: `git diff --check` passed. No application source, `DESIGN.md`, `PROGRESS.md`, or risks-register changes were made; the feature index is marked `passing` for independent validation.

## Validator checklist

- [ ] Decision is explicit: approve 720dp max-width and horizontal centring for land list, add/edit/remove, and privacy/disclosure surfaces on wide Desktop windows.
- [ ] Narrow windows remain available-width and no horizontal overflow is introduced as a requirement.
- [ ] Rationale links H1 to the existing chat baseline/design direction; no unsupported claim of user validation is made.
- [ ] Contract clearly defers all source/UI changes to `desktop_wide_land_layout`.
- [ ] Focused contract check passes; no application sources or unrelated durable records were modified.
- [x] Independent validator accepted the decision; focused assertion and `git diff --check` passed.
