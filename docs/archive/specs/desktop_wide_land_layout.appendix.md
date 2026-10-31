# Appendix — `desktop_wide_land_layout`

## Repository research

Inspected (paths relative to repository root):

- `AGENTS.md`, `PROGRESS.md`, `feature_list.json`: shared Compose belongs in `commonMain`; H1 is accepted and unfixed; all declared prerequisites are accepted.
- `DESIGN.md`: chat's 720dp column is centred; records land list, add/edit/remove forms, and privacy notice rendering full width on wide Desktop. Desktop visual focus capture and automated UI harness are known limitations.
- `docs/specs/desktop_land_layout_decision.md`, `docs/validations/desktop_land_layout_decision.md`: explicit approved policy is centred max 720dp on wide windows, available width on narrower windows; no claim of user research.
- `ARCHITECTURE.md`: shared UI ownership is `shared/src/commonMain`; no architecture change is needed.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`, `AddLandScreen.kt`, `EditLandScreen.kt`, `RemoveLandScreen.kt`: outer full-size vertically scrolling columns apply page padding; inner content columns use `.fillMaxWidth().widthIn(max = 720.dp)` without parent centring. This matches the known modifier-order/centering issue.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt`: outer scrolling column contains width-limited intro, sections, and back button individually; these currently lack a common centring parent.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: chat implements the centred cap using constrained content placement; inspect nearby exact parent layout during implementation before choosing a common seam.
- No persistent Compose UI-test or E2E harness was found; focused host build plus manual Desktop inspection is appropriate.

No new runtime measurements were made during planning. Existing recorded baseline is 1400x900 Desktop: chat content 720pt at x=400; land/privacy content 1352pt at x=84. Treat these as prior evidence, not fresh implementation results.

## Implementation plan and tasks

1. Inspect full composable parent layouts and the chat centring pattern. Confirm modifier constraints at the screen's actual available width and avoid duplicating a brittle workaround.
2. Implement the smallest shared `commonMain` layout correction. Ensure every listed screen's capped content is horizontally centred, including privacy section columns and navigation/back action; retain the 720dp max and narrow fill behavior.
3. Preserve outer vertical scrolling and page padding. Do not alter callbacks, state, strings, semantics, form focus/error behavior, or land persistence.
4. Run the focused contract command. If changing reusable layout utilities, add a focused unit/preview check only where current infrastructure can meaningfully verify it; do not add UI-test dependencies.
5. Build/launch Desktop and inspect representative routes at narrow (about 420pt) and wide (about 1400pt) windows. Measure content bounds/centering consistently, verify scroll reachability and no horizontal overflow. Confirm Android host build if changes affect shared composition beyond pure sizing.
6. Update `DESIGN.md` and `docs/risks-and-open-questions.md` to close H1 based on actual evidence, explicitly retaining any unverified claims. Do not update progress/status to accepted during implementation.

## Verification plan

- Automated focused check: `./scripts/init.sh --feature desktop_wide_land_layout` (published command runs `:shared:jvmTest` and `:desktopApp:build`).
- Manual Desktop geometry checks: for each named route, at wide width the capped region is <=720dp and its left/right margins are equal within measurement tolerance; at narrow width the region uses available width with no horizontal clipping. Cover list, add form, edit form, remove confirmation, and privacy notice, not only the list.
- Exercise vertical scroll to bottom on long forms/privacy notice and ensure all buttons remain reachable. Spot-check list controls and form validation still work.
- Run `git diff --check`. No persistent E2E command exists; manual inspection is required and must be reported with host, viewport, and measurement method.

## Evidence to capture

- Focused command output and `git diff --check` result.
- Desktop host/OS, viewport dimensions and density/scale, measured content width and horizontal position for each route at narrow and wide sizes.
- Confirmation of no horizontal overflow and intact vertical scrolling; any routes not directly inspected must be named.
- Android impact assessment (whether Android build/smoke was needed and run).
- Durable docs diff resolving H1 without overstating accessibility or user validation.

## Feature evidence

- Implementation: added horizontal centring to all five common screens, with the existing 720dp `widthIn` applied before `fillMaxWidth` so the cap constrains the child; privacy sections and back action share the same centred parent. Outer scroll containers and page padding are unchanged.
- `./scripts/init.sh --feature desktop_wide_land_layout`: PASS (`:shared:jvmTest :desktopApp:build`). An initial attempt exposed a duplicate import, corrected before the passing run.
- `./scripts/init.sh --fast`: PASS all available checks; backend pytest suite skipped because pytest is not installed (harness printed its venv setup instructions).
- `./scripts/init.sh --verify`: PASS Android host tests, Android debug build, Desktop build, and available fast checks; pytest remains unavailable as above.
- Repair recheck (2026-10-21): host is macOS 27.0, arm64 (`MacBook-Pro-de-Jose.local`). No Desktop window was launched or visually inspected in this session, and no screenshot/measurement facility was used. Actual display scale and viewport in dp/pt are therefore unknown; do not infer them from the host or the prior baseline. For each of the five routes, narrow and wide content width/position, clipping/overflow, scroll reachability, and control operation remain unobserved. No per-route geometry observations are claimed. Consequently H1 remains unresolved and the feature is not ready to claim visual acceptance.
- `./scripts/init.sh --feature desktop_wide_land_layout`: PASS (rerun during repair; `:shared:jvmTest :desktopApp:build`). This is compilation/test evidence only, not a geometry check.
- Android impact: common layout-only modifier changes; Android host tests and debug build passed. No device smoke test performed.
- `git diff --check`: PASS (no whitespace errors).
- Follow-up adjustment (2026-10-21): explicitly set the privacy page heading to `TextAlign.Start` so it follows the left-start alignment of the other land-screen headings; no other layout, styling, or content was changed.
- Follow-up verification: the first focused command attempt failed during `:shared:compileTestKotlinJvm` because Gradle's classpath snapshot transform could not find `AppDestination.class`; a serial retry of `./scripts/init.sh --feature desktop_wide_land_layout` passed (`:shared:jvmTest :desktopApp:build`). `git diff --check` passed. No Desktop UI was launched, so this does not verify runtime alignment or previously outstanding geometry/interaction checks.
- User-reported manual verification (2026-10-21): the user confirms checking all five named Desktop routes (land list, add, edit, remove confirmation, and privacy) at narrow and wide sizes. They report that the content centering/cap, narrow-width fit/overflow, scrolling, and controls all look good. This is user observation, not agent-run visual inspection. Host/OS, exact viewport dimensions, display scale, and numeric per-route measurements were not provided; do not infer or invent those details. The user explicitly defers further visual refinements until later.
- Independent validator (2026-10-21): ACCEPT. Reran `./scripts/init.sh --feature desktop_wide_land_layout` and `git diff --check`; both passed. Validator determined the user's qualitative route-by-route confirmation satisfies the manual acceptance scenarios; no relevant security/privacy issues found. Exact host/viewport/scale/numeric measurements remain undisclosed.


## Validator checklist

- [x] All five named screens (land list, add, edit, remove confirmation, privacy notice) use a centred max-720dp content column on wide Desktop windows.
- [x] Narrow windows use available width without horizontal overflow; vertical scrolling and all content/actions remain reachable (user-reported manual check).
- [x] Privacy sections and back action align with the same centered content region.
- [x] No change to content, callbacks, state transitions, land data, privacy claims, or form accessibility behavior.
- [x] Layout remains shared in `commonMain`; no Desktop-only fork or test-only dependency was added.
- [x] Focused shared tests and Desktop build pass; user-reported manual checks cover every named route at narrow and wide sizes.
- [x] `DESIGN.md` and risks register resolve H1 based on the disclosed qualitative evidence; no unsupported user/accessibility claim is introduced.
- [x] `git diff --check` passes; no unrelated feature/status changes are included.
