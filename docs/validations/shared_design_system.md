# Validation: `shared_design_system`

**Verdict: accept** — 2026-10-24

## What was checked

- Independently reviewed the implementation diff against [`docs/specs/shared_design_system.md`](../specs/shared_design_system.md), its appendix checklist, `DESIGN.md`, and the shared-source constraints.
- Confirmed explicit paired Material 3 light/dark role mappings and semantic caution roles in common code; `ManijeroTheme` uses the common `isSystemInDarkTheme()` signal by default and supports explicit light/dark preview/test selection. The shared root remains the only theme application; no host theme fork or appearance preference was added.
- Confirmed named shared shape/spacing tokens, shared typography roles, and common light/dark/enlarged-text previews. Common tests cover all 36 applicable Material roles in both schemes, documented WCAG pairs, semantic locals, explicit appearance mapping, and all 15 typography roles' size/weight/family/line-height behavior against platform-default `Typography()` (with the documented `bodySmall` 18sp line-height override).
- Confirmed the dark `outlineVariant` adjustment from Stitch `#424942` to `#646B64` is documented and contrast-tested. No screens, layouts, app behavior, navigation, platform source, dependencies, or Gradle configuration were changed for this feature.

## Verification

- `./scripts/init.sh --feature shared_design_system` — **PASS**; focused `:shared:jvmTest --tests ManijeroDesignSystemTest`, `BUILD SUCCESSFUL`.
- `./scripts/init.sh --verify` — **PASS**; all 9 offline checks passed, followed by Android host tests, Android debug build, and Desktop build (`BUILD SUCCESSFUL`).
- Backend pytest was skipped by the harness because pytest is not installed in this environment. The iOS simulator compile was not run; no iOS release or runtime validation is claimed.
- `git diff --check` — **PASS** before final acceptance documentation updates.

## Host visual observations

Reviewed all supplied host PNG captures; the image artifacts are verification evidence outside the repository and are not part of the commit.

- **Android light** (`android-light-home.png`, Pixel_10a): warm light canvas, dark text, olive links, outlined question chips and light input surface; no appearance setting/control is visible.
- **Android dark** (`android-dark-home.png`): near-black green background, light body text and olive links/outlines, without light-mode surface leftovers.
- **Android dark lands** (`android-dark-lands.png`): dark empty-state surfaces/text and olive primary action; Spanish copy is unchanged.
- **Android dark error** (`android-dark-error3.png`): the submitted question and deep-red service error container are visible with a Spanish explanation and pale “Reintentar” action; failure is stated in text, not communicated by color alone. `android-dark-error.png` and `android-dark-error2.png` instead show focused question input with the keyboard open and are not error-state evidence.
- **Android enlarged text** (`android-light-large-text.png`, system font scale 1.5): headings, chips, field label, and body wrap without clipping or overlap among the visible controls. The capture ends before the full screen content, so it does not prove the complete flow fits in one viewport.
- **Desktop light** (`desktop-light-home.png`): warm light palette. **Desktop dark** (`desktop-dark-home.png`): shared theme changes live after the user-authorized temporary macOS appearance toggle, without restarting the app. The original macOS Auto preference was restored.
- **Desktop dark lands** (`desktop-dark-lands.png`): existing land record uses dark surfaces/light labels and olive actions, without light-mode leftovers.

These captures provide visual evidence of appearance selection and review states. They do not constitute a keyboard-navigation/focus-order audit or exhaustive accessibility validation.

## Limitations and owner decision

- **Font gate deferred by owner decision:** no font binary was downloaded, added, or bundled. The platform default font family is preserved exactly; Source Serif 4 / Source Sans 3 are not silently replaced by another bundled family. Adoption remains blocked pending verified provenance and redistribution terms plus a future owner decision.
- Backend pytest is unavailable and was skipped. No iOS simulator compilation was run.
- The enlarged-text capture is limited to the visible viewport; full-flow scrolling and a keyboard-navigation/focus-order audit were not evaluated. There is no automated screenshot/E2E harness.

No feature-specific security or privacy issue was found. The acceptance record and raw verification evidence are also indexed in [`docs/progress/session-log.md`](../progress/session-log.md) and the spec appendix.
