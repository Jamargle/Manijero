# Appendix — `add_land`

Planning and verification record for [`docs/specs/add_land.md`](../../specs/add_land.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/add_land.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` contains the shared chat home and an unwired `Mis terrenos` callback; there is no navigation library or app theme wrapper.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/Land.kt` already supplies `LandDraft`, required `name`, optional `municipality`, and the required enums including `UNKNOWN` and `MIXED`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandRepository.kt` synchronously validates and trims drafts, persists via `LandStorage`, and can throw on invalid input or a storage write.
- `shared/src/androidMain/.../lands/AndroidLandStorage.kt` and `shared/src/jvmMain/.../lands/FileLandStorage.kt` are the accepted platform adapters, but neither is yet constructed by an app entry point.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt` each invoke `App()` with no injected dependencies.
- `shared/src/commonTest/.../lands/LandRepositoryTest.kt` verifies repository persistence and validation. `shared/build.gradle.kts` has Kotlin test but no established Compose UI test setup or navigation/DI dependency.
- `shared/src/commonMain/composeResources/values/strings.xml` is the existing KMP resource location. `DESIGN.md` requires plain Spanish, one obvious primary action, a short form, large controls, text scaling, and shared `commonMain` product UI.

The feature is correctly sized: it consumes one existing domain model/repository through one add flow. The open question about whether area belongs in first setup is intentionally not resolved here.

## Implementation plan and tasks

1. Write reducer tests from the acceptance contract first: default unknown selections, whitespace rejection without draft, preserved text/selections after validation/save failure, enum-to-draft mapping, and cancellation/success state handling. Include a Unicode/emoji land name angle and a non-finite/negative-area guard only if an area field is introduced (it should not be).
2. Implement the pure state/action/draft boundary and verify it does not duplicate repository IDs, timestamps, or persistence rules.
3. Build the screen using resource-backed strings and Material 3 semantics; add the specified previews and inspect at large font/wide width.
4. Wire the shared app destination and repository save callback. Catch expected validation/write failures at the UI boundary, retaining form state and avoiding data logging.
5. Wire Android and Desktop composition roots to the existing adapters; ensure the same repository instance is not recreated on ordinary recomposition.
6. Run focused tests and builds, then perform the Android/Desktop manual scenarios. Only after implementation/independent validation update `feature_list.json` evidence/status and `PROGRESS.md`.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
# If the Android SDK is available:
./scripts/init.sh --verify
```

Manual Android and Desktop smoke checks:

1. From home, open `Mis terrenos`, find the short add form, and save a name-only land with both `No lo sé` choices.
2. Add a second land with `Regadío` and `Ecológico`; close/relaunch each target and confirm repository data remains (temporary debug inspection or a focused test is acceptable until `land_list` exists).
3. Try blank/whitespace-only name, confirm the record is not saved and text/choices remain; correct it and save.
4. At enlarged system text, use keyboard navigation on Desktop and Android accessibility services where available; confirm labels, selection state, focus, and primary action remain understandable.

Capture command output, environment limitations (especially missing Android SDK), screenshots or a short manual record for default/error/known-value form states, and the persistence assertion. No persistent E2E harness exists in this repository; focused pure-state/repository tests plus Android/Desktop manual smoke are sufficient for this local synchronous UI flow.

### Implementation note (2026-10-12, `add_land` implementer)

- Added one focused test beyond this plan: `shared/src/jvmTest/.../AddLandDesktopStoreTest.kt`
  uses the real `FileLandStorage` with a temporary directory to assert that a name-only land and
  a known water/production land both persist after reopening the store. It complements the
  in-memory fake used by `AddLandStateTest` and makes the Desktop acceptance scenario
  reproducible for the validator. It touches no user data and changes no adapter.
- `./scripts/init.sh` created this worktree's `local.properties`, so for the first time in this checkout
  `./scripts/init.sh --verify` could run the Android host tests and build the debug APK as well as the
  shared JVM tests and Desktop build.

## Validator checklist

- [ ] The only required user input is a nonblank trimmed name; no record is written for blank input.
- [ ] Unknown is visible and preserved independently for water and production; mixed is never used as its substitute.
- [ ] A name-only and known-water/known-production land are correctly saved through `LandRepository` and persist on supported MVP platforms.
- [ ] Municipality is optional; no area, notes, precise identifier, or legal eligibility input is collected.
- [ ] Save failure retains user input, gives plain Spanish recovery guidance, and exposes neither land data nor raw exception text.
- [ ] The full product UI/form behavior is in `commonMain`; only storage construction is platform-specific.
- [ ] UI text and accessibility labels are resource-backed; controls work with large text, keyboard, and visible focus on Desktop.
- [ ] Focused tests and feasible builds pass, with blocked Android checks reported honestly.
- [ ] No unrelated feature, backend, persistence-format, cloud, or iOS-release work is included.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/add_land.md. Implemented the shared AddLandState/AddLandAction reducer with draft mapping (shared/src/commonMain/.../lands/AddLandState.kt), the stateless resource-backed AddLandScreen with previews (AddLandScreen.kt), Spanish add-land copy in composeResources/values/strings.xml, and App() destination plus lands wiring that catches save failures without logging land data.
- Composition roots: Android builds one LandRepository(SharedPreferencesLandStorage(applicationContext)); Desktop builds one remembered LandRepository(FileLandStorage(~/.manijero/lands-v1.txt)). The no-argument App() is retained for the iOS scaffold and previews, where the lands action stays unavailable instead of creating a common-code store.
- ./scripts/init.sh --verify passes (this worktree has local.properties after scripts/init.sh): :shared:jvmTest 21 tests/0 failures, :shared:testAndroidHostTest 20 tests/0 failures, :androidApp:assembleDebug, :desktopApp:build.
- New focused tests: 11 in AddLandStateTest (UNKNOWN defaults, blank/whitespace name rejected with no draft, name-only and IRRIGATED/ORGANIC mapping, deliberate MIXED, Unicode name, save-failure retention and retry, error clearing, two-land persistence after reopening) plus AddLandDesktopStoreTest against the real FileLandStorage.
- Desktop startup smoke: ./gradlew :desktopApp:run launched com.jamarglex.manijero.MainKt with the injected file store and stayed running without startup errors until the session stopped it (SIGTERM exit 143).
- Not verified by automated UI tests: interactive Android/Desktop device clicks and screen-reader/large-text checks; no emulator, device, or Compose UI-test harness exists, and the spec defers this to land_form_accessibility. Reported honestly rather than claimed.
- Independent validator accepted (2026-10-12) after re-running ./scripts/init.sh --verify, :shared:jvmTest and :shared:testAndroidHostTest with --rerun-tasks (21 and 20 tests, 0 failures), :androidApp:assembleDebug, :desktopApp:build, and a Desktop startup smoke; confirmed scope discipline, commonMain-only product UI, no land data or raw exception logging, and the copy contract. Record: docs/validations/add_land.md.
