# Feature Spec: `ui_refresh_accessibility_audit`

## Source metadata

- **Feature:** `ui_refresh_accessibility_audit` — Audit refreshed UI accessibility and evidence (`accessibility`); `not_started` at planning (2026-10-25).
- **Depends on:** `design_token_refresh`, `brand_vectors`, `ui_component_library`, `app_chrome_navigation`, `land_measurement_fields`, `land_search_and_summary`, `chat_screen_refresh`, `lands_screens_refresh`, `help_privacy_refresh` (all accepted).
- **Source behavior:** Verify the completed refreshed Android/Desktop interface across wide, dark, large-text, keyboard/focus and screen-reader conditions; close concrete accessibility defects found without changing accepted product behavior, and record evidence and limits.
- **Source plan:** [`docs/design/ui-refresh-plan.md`](../design/ui-refresh-plan.md), P2-17…P2-20 and P3-01…P3-10; [`DESIGN.md`](../../DESIGN.md) “Accessibility and validation”.
- **Source verification:** Wide Desktop and dark appearance per screen; 2× text at 320 dp without clipping/hidden actions; per-screen keyboard/focus/screen-reader pass; contrast/system tests, fast/full gates, Android emulator and Desktop screenshots, optional iOS compile, low-digital-confidence review or explicit open status.
- **Feature-list note:** This is a cross-surface verification and bounded remediation feature. User comprehension is not claimed unless an actual participant review is completed.

## Goal and boundaries

Establish an honest, reproducible accessibility evidence baseline for the refreshed UI, identify and fix in-scope defects that prevent readable and operable use, and document remaining platform/tooling/user-test limitations. Audit the actual shell destinations and forms: Assistant, Lands (empty/populated/search), add/edit/remove, Help and Privacy, including relevant states and routes.

**In scope**

- Review Android and Desktop at compact/narrow and wide sizes, light and dark, and 2× text; verify content wrapping, reachability by scrolling, no clipping/overlap, and no hidden essential action.
- Verify keyboard navigation and visible focus on Desktop; accessible names/semantics, heading structure, announcements and destructive-action focus behavior on Android and where Desktop accessibility APIs permit.
- Re-run existing contrast/design-system tests and screenshot regressions; capture actual emulator and Desktop evidence where available, distinct from host golden evidence.
- Fix narrow presentation/semantics defects within existing shared UI and accepted behavior. Add persistent regression tests where an existing test pattern can express the defect without adding a test framework/dependency.
- Record per-surface evidence and explicit not-verified items; perform low-digital-confidence owner review only if an appropriate reviewer is available and record method/observations without overgeneralizing.
- Update durable accessibility guidance and the historical refresh-plan delivery note only where actual evidence warrants it.

**Non-goals**

- No redesign, new product behavior/copy/route, new feature, backend/data changes, or broad accessibility certification claim.
- No new module, dependency, UI automation framework, permission, telemetry, or platform-specific UI fork. Keep app behavior/UI in `commonMain`.
- No assumption that screenshots or previews prove screen-reader, keyboard, device, iOS runtime, or usability success.
- No requirement to close a limitation that the environment or reviewer availability prevents; record it accurately instead.

## Job story

When I use the refreshed app with larger text, a keyboard or assistive technology, I want to read and reach the important information and actions on every screen, so I can manage my lands and get help without hidden controls or assistance.

## Acceptance scenarios

### Compact large text remains usable

Given each shell destination and its essential states at 320 dp with 2× text on Android and Desktop where supported, when the user scrolls and navigates, then labels and controls do not clip, overlap, or overflow horizontally, and every essential action remains reachable; any platform-specific exception is recorded with evidence.

### Wide and dark layouts remain coherent

Given Desktop at 800×600 and 1280×800 and Android compact/wide windows, when each destination is rendered in light and dark appearance, then the shell adapts, content remains readable and correctly centred/capped where specified, and no important state is conveyed by color alone.

### Keyboard and assistive access are audited honestly

Given Desktop keyboard-only operation and Android accessibility inspection, when each route/state is traversed, then focus order is predictable, focus is visible, controls have meaningful names, headings and live updates follow the owning contracts, and destructive actions do not receive unsafe automatic focus. Unavailable checks are explicitly marked unverified rather than inferred.

### Regression and documentation evidence agree

Given all available automated checks, when the audit is complete, then applicable contrast/design-system tests and focused/full gates are reported with outcomes; screenshots are identified by platform, viewport, scale and appearance; changed baselines are reviewed and limited to intentional changes; durable docs distinguish observed facts from limitations.

### No unsupported usability claim

Given a low-digital-confidence review is unavailable or not performed, when this feature is reported, then the review remains explicitly outstanding and no usability/accessibility acceptance is claimed on its behalf.

## Technical approach

1. Build a surface/state audit matrix from current contracts and `DESIGN.md`; include shell destinations, empty/populated/search, form validation/removal confirmation, chat answer/abstention/clarification/failure, Help and Privacy, and route/back behavior.
2. Run existing automated checks first. Use actual Android emulator and Desktop interaction/render evidence for manual conditions; previews and goldens are supporting evidence only.
3. For each observed defect, make the smallest shared `commonMain` fix consistent with the owning accepted spec. Add/adjust persistent tests and focused screenshots only when appropriate; do not refresh unrelated goldens.
4. Re-run affected checks and record each matrix cell as pass, fail/fixed, blocked, or not performed. Avoid blanket “accessible” claims.

## Expected file changes

- **Likely update:** `shared/src/commonMain/kotlin/com/jamarglex/manijero/` screen/design files only if a concrete defect is found; corresponding `shared/src/commonTest/`, `shared/src/jvmTest/`, or `shared/src/androidHostTest/` tests only as warranted.
- **Likely update:** `shared/src/{jvmTest,androidHostTest}/screenshots/` goldens only for intentional, inspected changes caused by a confirmed fix.
- **Update:** this appendix with audit matrix/evidence; `DESIGN.md` and `docs/design/ui-refresh-plan.md` delivery note only where current durable statements need correction or evidence status.
- **After independent validation only:** `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`; acceptance record in `docs/validations/` by validator.
- Do not change accepted contracts, strings, backend/API/knowledge, data model, shell routing, or build dependencies absent an explicitly justified in-scope defect and owning-spec-compatible fix.

## Visual design and accessibility impact

This is an audit, not a restyle. Preserve the approved palette, component patterns, Spanish copy and route behavior. Any correction must improve actual accessibility without introducing color-only status, shrinking targets, hiding labels, or reducing large-text reflow. Full evidence should include Android device/emulator and Desktop observations; host screenshots alone do not prove interaction or accessibility.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | **Update if needed** | Keep durable guidance and verified limits aligned; do not paste the audit log. |
| `CONSTRAINTS.md` | **Update if needed** | Add only a newly discovered durable MUST/MUST NOT rule. |
| `docs/screenshot-regression.md` | **Update if needed** | Only if capture inventory/procedure changes. |
| `docs/design/ui-refresh-plan.md` | **Update delivery note** | Point to this feature's evidence and state which planned audits remain open. |
| `AGENTS.md`, `ARCHITECTURE.md`, `CONTEXT.md`, domain/build docs | **Not needed** | No architecture, product scope or domain change. |
| `feature_list.json`, `PROGRESS.md`, session log | **After validation only** | Repository workflow reserves status/progress updates for verified acceptance. |

## Risks and open decisions

- The repository has no persistent cross-platform Compose accessibility UI-test harness; manual checks may not be automatable without a separate approved scope change.
- TalkBack/host accessibility access, emulator availability, Desktop accessibility APIs and macOS display capture may be unavailable. Record command/platform and exact consequence.
- P3-10 requires an appropriate human reviewer; screenshots cannot substitute. If no participant review occurs, leave it outstanding.
- The historical plan spans many screens/states. Use the bounded matrix in the appendix; if defects require a redesign or unrelated feature work, stop and split/escalate rather than broadening this audit.

## Focused verification

The feature is verification-dominant; this focused block runs the existing shared tests and screenshot gate without recording images or starting services. Manual evidence is required separately.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :shared:verifyScreenshots
```
<!-- verify:end -->

## Appendix

Repository research, audit matrix, implementation/remediation tasks, verification and evidence checklist are in [`ui_refresh_accessibility_audit.appendix.md`](ui_refresh_accessibility_audit.appendix.md).
