# Appendix — `suggested_questions`

Planning and verification record for [`docs/specs/suggested_questions.md`](suggested_questions.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/suggested_questions.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `feature_list.json`: this feature depends only on accepted `chat_home`; its note requires examples drawn from approved MVP-corpus topics.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `App()` owns `ChatHomeState`; `ChatHomeScreen` already renders shared explanation, composer, `Preguntar`, and `Mis terrenos`. It is the sole UI change point.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: a pure state/reducer already preserves entered wording, disables whitespace-only submission, and clears `submittedQuestion` on `QuestionChanged`.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatHomeStateTest.kt`: `kotlin.test` reducer tests are the established focused test pattern.
- `shared/src/commonMain/composeResources/values/strings.xml`: shared Compose resource strings are already used for all home copy.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt`: both call shared `App()`; no platform UI changes are needed.
- `DESIGN.md`: Home/ask explicitly calls for a small set of example questions; it requires plain Spanish, large controls, shared `commonMain`, keyboard access, and text scaling.
- `MasterPlanV3.md` §17.3 lists **hypotheses to validate with family**, not an approved prompt catalog; its §11 seed corpus/source entries and `docs/risks-and-open-questions.md` both show first-pilot corpus coverage remains unresolved. The three example strings for this feature were approved separately (see Content decision) without establishing corpus coverage.

There is no navigation framework, Compose UI-test dependency/convention, persistent E2E command, or `ARCHITECTURE.md`/`CONSTRAINTS.md` in the repository. `./scripts/init.sh --verify` runs shared host tests plus Android/Desktop builds and does not start a long-running service.

## Implementation plan and tasks

1. Ship the three approved strings from the Content decision section verbatim; do not reword, trim, translate, or add date, amount, eligibility, or cooperative-specific premises.
2. Add resource keys for the approved strings and the reducer action/case, preserving the selected text verbatim.
3. Render the shared suggestion controls and wire them to `onAction`; add state/layout previews.
4. Add distinct unit tests for selection replacing arbitrary existing text, selection clearing submitted state, and subsequent edit/submit preserving the selected or edited text. Retain existing whitespace test coverage; include a Unicode/Spanish punctuation selection case.
5. Run the focused and available platform build checks, then perform Android/Desktop manual checks where environments are available.
6. Only after implementation and verification, update `feature_list.json` and `PROGRESS.md` with status/evidence; this planning change does not update either.

## Verification plan

Run:

```sh
./gradlew :shared:jvmTest
./scripts/init.sh --verify
```

`jvmTest` must cover reducer behavior without I/O. There is no persistent E2E test command or configured Compose UI-test framework, so focused pure tests plus platform manual smoke are sufficient for this state-only UI slice; do not claim E2E coverage.

Manual smoke on both Android and Desktop:

1. Open the home screen with no lands and find all examples without scrolling sideways.
2. Select each example; confirm exact text appears in the composer, `Preguntar` enables, and no answer/network state appears.
3. Edit a selected example, submit it, and confirm the existing ready message reflects preparation only.
4. Check keyboard focus/activation on Desktop and enlarged system text/screen-reader-readable controls on Android; confirm wrapping and no clipping.

Android verification is currently environment-blocked when `ANDROID_HOME`/`local.properties` has no SDK location, as recorded in `PROGRESS.md`; report that limitation rather than marking Android passed. Desktop interactive launch is manual and long-running; `:desktopApp:build` from `--verify` is the non-interactive compilation check.

## Evidence to capture

- Passing `:shared:jvmTest` output, including the new selection tests.
- `./scripts/init.sh --verify` output, or the exact Android SDK blocker while retaining any completed checks.
- Android and Desktop screenshots or a concise manual-check record showing examples, selected composer text, and enlarged/wrapped text.
- The recorded approval in the Content decision section of this spec, matched byte-for-byte against the shipped Compose string resources (no separate owner approval remains outstanding).

## Validator checklist

- [ ] The shipped examples are exactly the three approved strings in the Content decision section (verbatim, including `¿` and accents), with no extra, removed, reordered, or reworded prompts.
- [ ] The home has a small, plain-Spanish, shared suggestion area with all text in Compose resources.
- [ ] Tapping every example fills—not sends—the composer exactly, enables `Preguntar`, and clears stale submitted state.
- [ ] Existing whitespace rejection and original-wording submission behavior still pass.
- [ ] Reducer tests include replacement, stale-state clearing, edit/submit preservation, and a Unicode/Spanish-text case.
- [ ] Controls are keyboard-operable, screen-reader-readable as text controls, wrap under enlarged text, and fit Android/Desktop layouts.
- [ ] `:shared:jvmTest` passes; `--verify` result and any Android SDK limitation are truthfully recorded.
- [ ] No backend, land, navigation, platform-entry, dependency, or unrelated feature changes are included.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/suggested_questions.md.
- Added ChatHomeAction.SuggestedQuestionSelected(String) and a pure reducer case that sets question to the supplied text and clears submittedQuestion; no API/navigation/dependency added.
- The three approved example strings are shipped verbatim as shared Compose string resources (chat_home_suggestion_solicitud_unica, chat_home_suggestion_sigpac, chat_home_suggestion_condicionalidad); a byte-for-byte comparison against the spec Content decision passed, and the unapproved deadline wording is absent.
- ./gradlew :shared:jvmTest passes; ChatHomeStateTest 7/7, including 4 new tests (example replaces existing text, clears stale submitted state, submits verbatim then keeps edits, Spanish/Unicode punctuation intact).
- ./scripts/init.sh --verify BUILD SUCCESSFUL: :shared:jvmTest, :shared:testAndroidHostTest (ChatHomeStateTest 7/7), :androidApp:assembleDebug (androidApp-debug.apk built), :desktopApp:build.
- Android emulator smoke (Medium_Phone_API_35, 1080x2400, debug APK): all three examples visible without sideways scrolling; tapping each fills the composer with the exact question and enables Preguntar with no answer/network state; submit shows only 'Tu pregunta está lista para continuar.'; re-selecting an example clears the stale submitted message; at font_scale 2.0 the labels wrap to two lines with no horizontal overflow (max right edge 954 of 1080).
- Desktop: :desktopApp:run launched the shared App() and stayed alive ~50s with no runtime exception; interactive visual/click smoke was not captured in this non-interactive session.
- Ready for independent validation; no Android SDK blocker remains in this worktree.
- Independent validator ACCEPTED this feature (record: docs/validations/suggested_questions.md) after re-running :shared:jvmTest --rerun-tasks (ChatHomeStateTest 7/7), :shared:testAndroidHostTest, :androidApp:assembleDebug, and :desktopApp:build, and independently confirming the three shipped strings match the spec byte-for-byte with no unapproved wording.
