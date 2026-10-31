# Feature Spec: `desktop_land_layout_decision`

## Source metadata

- **Feature:** `desktop_land_layout_decision` — Decide whether land screens need a capped wide-window layout (area: `client`), `not_started` at planning (2026-10-21).
- **Depends on:** `desktop_mvp_build`, `land_list`, `edit_land` — all accepted.
- **Source behavior:** Resolve whether Desktop land-management and related information surfaces should use a readable capped/centred layout on wide windows, based on the recorded H1 finding and existing design principles.
- **Source verification:** Record an explicit, traceable decision and rationale in a decision spec; ensure it bounds the follow-on `desktop_wide_land_layout` implementation.
- **Source note:** H1: chat is capped/centred at 720dp, while lands list, forms, and privacy notice render full-width on wide windows (`PROGRESS.md`, `DESIGN.md`, `docs/risks-and-open-questions.md`).
- **Scope size:** Small decision artifact: one bounded UI policy decision, no implementation or user flow change. Correctly sized.

## Goal

Make the layout policy explicit before changing UI. **Decision: yes** — on Desktop wide windows, land list, add/edit/remove land, and privacy/disclosure screens should share the existing 720dp maximum readable width and be horizontally centred, consistent with chat and the product's readable-column direction. This decision authorizes the dependent implementation feature; it does not itself change UI.

The cap is a maximum, not a fixed width: screens remain full available width when the window is narrower than 720dp. Keep existing vertical scrolling, screen content, navigation, and behavior unchanged.

## Non-goals

- No Kotlin/Compose implementation, preview changes, or layout refactor in this feature.
- No change to chat, coverage/help, or other surfaces beyond the named land-management and privacy/disclosure screens.
- No new tokens, components, dependencies, platform-specific layout, or app behavior.
- No claim that 720dp is user-validated; this is a consistency/usability decision based on the shipped chat baseline and design guidance.
- No change to mobile layouts or form/data requirements.

## Job story

When I manage my lands or read how their data is handled in a wide Desktop window, I want the content to remain in a readable, centred column rather than stretching edge-to-edge, so the experience is consistent with the chat home and easier to scan.

## Acceptance scenarios

### Decision is explicit and actionable

Given the recorded H1 finding and the existing 720dp chat column, when this decision is reviewed, then it approves a maximum 720dp centred column for the land list, add/edit/remove forms, and privacy notice on wide Desktop windows, and states that narrower windows use available width.

### Decision does not imply implementation

Given this decision feature is complete, when application sources are inspected, then no UI behavior has changed; the concrete implementation is left to `desktop_wide_land_layout`.

### Rationale and evidence limits are clear

Given the decision record, when its basis is read, then it identifies the pre-existing H1 geometry finding and the `DESIGN.md` readable-layout principles, and does not present the decision as target-user research or accessibility validation.

## Technical approach

Treat this as a product/layout decision record. Use the existing 720dp chat content maximum as the consistency baseline. The next feature should apply the cap and centring in shared `commonMain` to the named screens, preserving narrow-window behavior and all existing screen semantics. Reuse existing layout patterns where practical; do not introduce a Desktop-only fork.

## Expected file changes

- **Create** this decision contract and `desktop_land_layout_decision.appendix.md`.
- **Do not modify** application source, `DESIGN.md`, `PROGRESS.md`, `feature_list.json`, or the risks register in this planning slice. The decision and research live in this pair; update durable product/design documentation only if implementation or later user evidence changes the policy.

## Visual design impact

No rendered change in this feature. The approved future result is a single centred content column capped at 720dp on wide windows; at or below that width content should use available width without horizontal overflow. Existing colors, typography, spacing, content, and navigation remain unchanged.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `docs/specs/desktop_land_layout_decision.md` and appendix | **Create** | Record the decision, rationale, research, and handoff boundary. |
| `DESIGN.md` | **Not needed now** | It states the durable requirement to adapt shared layouts to Desktop; measured current behavior and this decision's evidence belong in the feature record and validation, not the design guide. Revisit only if the approved design direction changes. |
| `docs/risks-and-open-questions.md` | **Not needed** | Its implementation-time question is answered here; retain the historical/current record unless the project owner wants a separate register cleanup. |
| `ARCHITECTURE.md`, `CONSTRAINTS.md`, `AGENTS.md` | **Not needed** | No module boundary, durable invariant, or workflow changes. |
| `PROGRESS.md`, `feature_list.json` | **Not needed in planning** | Status is updated only after implementation/validation workflow; the feature-list entry already exists. |

## Focused verification

This decision-only feature has no code test. The focused check validates that the explicit decision and implementation boundary remain in the contract; it does not validate UI rendering.

<!-- verify:start -->
```sh
python3 -c 'from pathlib import Path; p=Path("docs/specs/desktop_land_layout_decision.md").read_text(); assert "**Decision: yes**" in p; assert "720dp" in p; assert "desktop_wide_land_layout" in p; assert "No Kotlin/Compose implementation" in p'
```
<!-- verify:end -->

## Appendix

Research, implementation handoff, verification plan, evidence, and validator checklist are in [`desktop_land_layout_decision.appendix.md`](../archive/specs/desktop_land_layout_decision.appendix.md).
