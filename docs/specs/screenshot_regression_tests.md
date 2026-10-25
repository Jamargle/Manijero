# Feature Spec: `screenshot_regression_tests`

## Source metadata

- **Feature:** `screenshot_regression_tests` — Add screenshot regression tests with human-approved baselines (`testing`).
- **Status at planning:** `not_started`; depends on accepted `design_token_refresh`.
- **Source behavior:** Changes to the shared Compose UI are checked against reviewed visual baselines rendered on the existing Desktop JVM target and on Android through Robolectric on the host JVM. Verification detects unexpected changes but never silently updates expected images.
- **Feature verification:** Run the Desktop and Android host screenshot suites in verify mode; demonstrate that an intentional visual change fails against the old baseline and passes only after a human-reviewed baseline is recorded. iOS visual rendering remains out of scope.
- **Plan source:** `docs/design/ui-refresh-plan.md` §§10.2 and 10.4; owner-approved Roborazzi approach.

## Goal and boundaries

Add a persistent screenshot regression gate for representative `shared/src/commonMain` Compose states, using Compose Desktop through the existing `shared` JVM target and Android through Robolectric on the existing `androidHostTest` source set. Commit the expected images alongside the tests. The ordinary test path compares output and fails on unexpected differences; recording is a separate, explicit developer action.

**In scope**

- Add and pin a Roborazzi version and the minimum Compose Desktop UI-test wiring needed on `shared`'s JVM target.
- Add and pin Robolectric/Roborazzi Android host wiring for the existing Android target, rendered without an emulator or device.
- Provide deterministic test fixtures and fixed render conditions (window size, light/dark theme, font scale, locale, and input data) for the selected representative shared screens/states.
- Commit reviewed baseline images per platform and configure an explicit, documented comparison threshold for platform font/antialiasing variation.
- Make verification read-only with respect to baselines; provide an explicit record/update path and document human image review.
- Keep the Desktop suite usable without an Android SDK or emulator.

**Non-goals**

- No emulator, device, or Android instrumentation coverage, no iOS screenshots or runtime coverage, and no claim about Android API levels or devices other than the pinned Robolectric host configuration.
- No accessibility/usability proof, behavior test replacement, design changes, or baseline refresh solely to make a failing test pass.
- No CI workflow changes unless an existing workflow is found and the focused task is already run there; do not introduce a new CI service/workflow as a dependency of this feature.
- No application behavior, production Compose UI, backend, data, or navigation changes.

## Job story

When a shared screen changes, I want an automated comparison against human-reviewed Desktop and Android images, so that an unintended visual change is visible before it reaches users.

## Acceptance scenarios

### Verification detects a visual regression

Given a committed baseline and a screenshot test in verify mode, when the rendered frame differs beyond the documented threshold, then the focused test fails and leaves expected/actual/diff artifacts available for review without changing the baseline.

### Intentional change requires human-reviewed recording

Given an intended visual change, when a developer explicitly invokes the documented record task, then only the affected expected image is updated; the developer reviews the image and commits it with the change. Normal verification never records.

### Render output is reproducible within the pinned environment

Given the same fixtures, render configuration, and pinned recording environment, when the focused test runs, then it uses fixed dimensions, appearance, font scale, locale, and fixture data, and applies the explicit threshold rather than an undocumented default.

### Coverage claims stay bounded

Given this test suite passes, when reporting its result, then the evidence describes Desktop JVM and Android host (Robolectric) shared-UI pixel regression coverage only and does not claim device/emulator, iOS, accessibility, usability, or product behavior correctness.

## Technical approach

- Configure Roborazzi for the existing `shared` JVM target and use its supported Compose Desktop capture path; do not create another module or platform target.
- Configure Roborazzi with Robolectric on the existing Android host-test source set; do not add an emulator, device, or instrumentation dependency.
- Tests should construct the shared UI with controlled fixtures and a fixed theme/configuration, without network, disk, real clock, or application backend dependencies. Keep the fixtures in `commonTest` so both platforms render the same data.
- Keep verify and record operations distinct per platform. Pin the tool/library versions, choose a deliberate pixel threshold, and document the supported recording environment and fallback to manual screenshots if the experimental integration becomes unusable.
- Select a compact but representative set of shared states, including light and dark appearance and key chat/land surfaces, and capture the same scenes on both platforms. Avoid encoding every transient state as a golden; capture the exact set and exclusions in the appendix.
- Configure test outputs so image diffs are inspectable locally; CI remains out of scope for this feature.

## Expected file changes

- **Modify** `gradle/libs.versions.toml` and `shared/build.gradle.kts` — pinned screenshot tooling and Desktop/Android host test wiring.
- **Add/modify** focused tests and fixtures under `shared/src/jvmTest/`, `shared/src/androidHostTest/`, and `shared/src/commonTest/` — Compose Desktop and Robolectric screenshot cases plus deterministic shared data.
- **Add** reviewed expected images per platform in the Roborazzi-managed test resources/output locations, committed in the repository.
- **Add** `docs/screenshot-regression.md` — the single verify/record and human-review procedure for both platforms.
- **Modify** `scripts/init.sh` only if needed to expose the focused screenshot verification as part of the existing `--feature` command; the published block is the aggregate Gradle task.
- **Update** `PROGRESS.md`, `feature_list.json` status, `docs/progress/session-log.md`, and this appendix after implementation/validation, following the repository's acceptance workflow.

## Focused verification

The feature command must run both screenshot suites in verify mode and must not record baselines or start a service. The suites are separate from the general `./gradlew :shared:jvmTest` and `:shared:testAndroidHostTest` tiers: Desktop renders host fonts and its goldens are recorded on macOS, while the standard tiers and CI run on Linux. Android is rendered by Robolectric on the host JVM and needs an Android SDK to build, but no emulator, device, or backend. The published aggregate task is read-only; the Desktop-only and Android-only tasks remain available for narrower local checks.

<!-- verify:start -->
```sh
./gradlew :shared:verifyScreenshots
```
<!-- verify:end -->

Manual review remains required when recording: inspect each changed expected image and its diff before committing. Passing verification proves only that the selected Desktop and Android host frames match within the configured threshold.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `PROGRESS.md` | Update after acceptance | State precisely which Desktop and Android host states are gated and retain platform/accessibility limitations. |
| `docs/screenshot-regression.md` | Add | One verify/record and human-review procedure for both platform suites. |
| `docs/progress/session-log.md` | Update after acceptance | Add the accepted-feature pointer. |
| `ARCHITECTURE.md` | Not needed | No ownership or runtime boundary changes. |
| `CONSTRAINTS.md` | Not needed | No new product invariant; verification/record separation belongs in this contract. |
| `AGENTS.md` | Not needed | Existing verification tiers already cover focused feature checks. |
| `DESIGN.md` | Not needed | This adds regression tooling, not a design decision. |

## Appendix

See [`docs/specs/screenshot_regression_tests.appendix.md`](screenshot_regression_tests.appendix.md) for repository research, implementation tasks, verification details, evidence, and the validator checklist.
