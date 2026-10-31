# Feature Spec: `shared_design_system`

> **Palette superseded (2026-10-25):** the palette verified by this feature is the accepted historical
> contract. The approved replacement palette is the Stitch token block (light and dark exports),
> recorded in `docs/design/ui-refresh-plan.md` §3.1 and `DESIGN.md` with two `outlineVariant`
> accessibility corrections; it takes effect when `design_token_refresh` is implemented. Role
> mapping, dark-mode selection, shapes, spacing, and verification requirements here are unchanged.

## Source metadata

- **Feature:** `shared_design_system` — Shared light and dark design system (`client`), `depends_on: [visual_foundation]`.
- **Status at planning:** `not_started`; `visual_foundation` is accepted.
- **Source behavior:** Manijero renders with one coherent, accessible Stitch-derived visual language across Android, Desktop, and the shared iOS-ready code. It follows the operating system's light/dark appearance automatically.
- **Source verification:** Run focused shared tests for token roles, theme selection, shape/spacing and contrast; build the shared JVM, Android host, Android app, and Desktop targets; inspect the theme review previews in both modes and verify system appearance on Android/Desktop.
- **Notes carried from the feature request:** Use Stitch's light and dark design-system exports as the design baseline; adopt their palette with contrast corrections as needed; follow system appearance, without a user preference setting. Typography stays at the Material 3 default. Keep the implementation shared in `commonMain` for future iOS reuse.

## Goal and boundaries

Establish the reusable shared UI foundation described by the Stitch references: semantic light/dark color schemes, shape and spacing scales, default typography, and one system-aware theme applied at the shared root. Make its values reviewable and machine-check the documented contrast pairs. Preserve the existing app behavior and screen layouts; screen-by-screen restyling is owned by existing screen features.

**In scope**

- Centralize Stitch light and dark semantic color roles in the existing shared theme package; map every applicable Material 3 role explicitly and keep non-Material semantic roles available via a typed CompositionLocal.
- Select the scheme with Compose Multiplatform's system appearance signal; all shared screens and previews use the same theme. There is no manual appearance preference, persistence, or platform-specific theme fork.
- Define named shared shape and spacing values based on Stitch's scales, suitable for use from common Compose code.
- Provide light/dark theme previews or a review board and common tests for token-role mapping, shape/spacing values, and contrast.
- Repoint existing previews to the shared theme where needed so preview colors cannot diverge from runtime.

**Non-goals**

- No pixel-perfect screen rebuild or per-screen layout/copy changes; no navigation changes, new app behavior, component library expansion, or redesign of chat/lands/help.
- No settings screen, appearance persistence, or user-selectable theme override; follow-system behavior only.
- No new Gradle module, theme framework, or test-only dependency; no Material dynamic color.
- No product claims or behavior sourced from the bundled PRD/masterplan where they conflict with current contracts.
- No iOS release work. Shared source compatibility is required, but iOS packaging/release validation is not.

## Job story

When I use Manijero on a phone or computer in different lighting conditions, I want its colors, text, and component geometry to stay coherent and readable while matching my system appearance, so the app feels familiar and comfortable without me configuring it.

## Acceptance scenarios

### Shared appearance across hosts

Given the system requests light appearance, when `App()` renders on Android, Desktop, or the shared iOS scaffold, then the Stitch-derived light scheme is used. Given the system requests dark appearance, when it renders, then the corresponding dark scheme is used. No host wraps or overrides the shared theme independently.

### Complete semantic token mapping

Given any shared screen or preview requests a Material 3 color role, when either scheme is active, then that role comes from the documented Manijero light/dark scheme rather than a Material default. Non-Material semantic colors are exposed through the theme's semantic local and have an explicit value for both appearances. Screen code contains no raw palette literals.

### Accessible palette pairs

Given the light and dark schemes, when common tests calculate WCAG contrast, then every documented normal-text pair is at least 4.5:1 and every documented non-text boundary/icon pair is at least 3:1. Any Stitch value that fails is adjusted and the final value, intended use, and measured ratio are documented; a failed pair is not omitted to make the test pass.

### Shape and spacing are shared

Given a screen opts into a documented shared shape or spacing token, when it renders on any supported host, then the same shared value is used and text remains scalable at the platform text scale. Typography stays at the Material 3 default, so there is no custom family, scale, or font asset to maintain.

### Existing behavior is unchanged

Given the new theme is applied, when existing chat, lands, help, and privacy workflows run, then their copy, state transitions, persistence, requests, semantics, and navigation remain unchanged; only shared visual primitives/tokens change.

## Technical approach

- Extend `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/` rather than adding a module. Keep colors, shape/spacing tokens, semantic locals, and theme application in cohesive files consistent with the current package.
- Reuse the existing `ManijeroTheme` at `App()` (the composition root). Use the common Compose system-dark appearance API; keep platform entry points free of theme duplication.
- Source semantic roles and exact starting values from `design-references/stitch/manijero_design_system/DESIGN.md` and `.../manijero_design_system_dark_mode/DESIGN.md`. Treat these as starting values, not exemptions from contrast checks. Document adjustments in `DESIGN.md` and tests.
- Keep semantic error/caution meanings stable in both modes; status is never communicated by color alone. Maintain minimum interactive target and keyboard focus behavior.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt` and `ManijeroTheme.kt` for paired schemes and system appearance.
- **Add** shared shape/spacing token definitions under the same package. Typography keeps the Material 3 default; no typography file or font asset is added.
- **Modify** affected shared preview wrappers to exercise the theme; do not edit screen layouts or behavior.
- **Add** common unit tests under `shared/src/commonTest/kotlin/com/jamarglex/manijero/theme/` for color roles, contrast, and shape/spacing values.
- No host source, backend, contract, data, or Gradle dependency changes are expected. If research demonstrates a required platform-specific change or dependency, stop and revise the contract before implementation.

## Visual design impact

This feature changes the shared theme foundation from the currently shipped light-only palette to the user-selected Stitch light/dark design system. Light and dark mode are both first-class; system appearance selects between them. Exact palette direction comes from the two bundled design-system files; the feature's final verified token table becomes authoritative. Existing screens may change appearance through role mapping but are not structurally redesigned. See [`DESIGN.md`](../../DESIGN.md) and [`design-references/README.md`](../../design-references/README.md).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `DESIGN.md` | Update | Record final accepted light/dark tokens, shape/spacing scales, system appearance behavior, default typography, and any contrast-driven changes. |
| `ARCHITECTURE.md` | Not needed unless ownership changes | Theme stays in existing shared `commonMain`; no new module or boundary. |
| `CONSTRAINTS.md` | Not needed | Existing accessibility and shared-source constraints remain sufficient. |
| `AGENTS.md` | Not needed | Existing shared UI and platform rules apply. |
| `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md` | Not needed | This is a presentation foundation, not a product/domain change. |
| `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md` | Update after implementation and independent acceptance | Keep status and evidence honest; planning must not mark the feature passing/accepted. |

## Focused verification

This is the cheapest focused check that exercises the shared theme contract. The feature command must run tests, not only print guidance; it must not launch a long-running service.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ManijeroDesignSystemTest
```
<!-- verify:end -->

## Appendix

See [`docs/archive/specs/shared_design_system.appendix.md`](../archive/specs/shared_design_system.appendix.md) for repository research, ordered implementation tasks, verification detail, evidence, risks, and validator checklist.
