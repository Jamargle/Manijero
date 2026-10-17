# Feature Spec: `suggested_questions`

## Source metadata

- **Feature:** `suggested_questions` — Example questions
- **Status / dependency:** `not_started`; `chat_home` is accepted.
- **Source behavior:** A person can tap a short example question and have its Spanish text placed in the chat flow, without needing to formulate a prompt.
- **Source verification:** Tap an example and confirm its text is submitted or ready to submit in the composer.

## Goal

Make the existing shared chat home easier to start by presenting a small, readable set of approved Spanish question examples. Selecting one fills the existing composer and makes the existing `Preguntar` action available; it does **not** send a request.

## Non-goals

- No answer-service request, chat transcript, loading state, answer rendering, or navigation.
- No new land context, storage, telemetry, or personal-data collection.
- No legal advice, legal facts, deadlines, amounts, eligibility, or claim that an example will receive an answer.
- No dynamic/retrieval-driven suggestion service, topic configuration screen, or source-catalog implementation.
- Do not alter the existing blank-input or submit semantics beyond clearing stale `submittedQuestion` when an example replaces an earlier question.

## Job story

When I do not know how to phrase an agricultural question, I want to choose a short example in everyday Spanish so that I can start with wording I understand and still review or edit it before asking.

## Acceptance scenarios

### Examples are visible and understandable

Given the chat home opens with an empty composer, when the user views the home content, then a short Spanish heading/instruction and a small set of clearly tappable example questions appear between the home explanation and composer, without requiring a land.

### Selecting an example prepares, rather than sends, the question

Given the user taps an example question, when the selection is processed, then the composer contains exactly that example text, `Preguntar` is enabled, and no network/API call or simulated answer is made.

### The user remains in control of wording

Given an example has filled the composer, when the user edits it, then the edited text remains in the composer and the existing submit behavior preserves that edited wording. Given a previously submitted-state message is visible, when an example is selected, then the stale submitted state is cleared.

### Existing composer behavior remains intact

Given no example is selected, when the user enters only whitespace, then `Preguntar` remains disabled. Given the user selects an example and presses `Preguntar`, then the existing local "ready to continue" state receives the exact selected text; real submission remains deferred to `chat_question_submission`.

### Shared, accessible presentation

Given Android or Desktop renders `App()`, when the suggestion area is reached by touch, pointer, keyboard, or screen reader, then every example has its full question as an accessible text label, uses a Material control with its normal minimum target/state feedback, and its text can wrap at enlarged text scale without clipping or horizontal scrolling.

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

There is no navigation framework, Compose UI-test dependency/convention, persistent E2E command, or `ARCHITECTURE.md`/`CONSTRAINTS.md` in the repository. `./init.sh --verify` runs shared host tests plus Android/Desktop builds and does not start a long-running service.

## Content decision (resolved)

The source/corpus owner has **approved** this compact static whitelist of three questions for this feature. There is **no outstanding content approval**: the strings below are approved to ship. Ship them **verbatim**, including the opening `¿` and the exact accents/punctuation — do not retrim, reword, translate, or append text.

Approved examples:

1. `¿Qué necesito preparar para la solicitud única?`
2. `¿Qué es el SIGPAC y para qué sirve?`
3. `¿Qué obligaciones tengo por la condicionalidad?`

Each approved question is topic-level and contains no date, deadline, amount, eligibility, or cooperative-specific premise. Keep this fixed list in shared presentation code with its displayed strings in Compose resources; no content is fetched at runtime.

This approval covers only these three example strings as seed wording for this feature. It does **not** assert corpus coverage, does not accept `source_catalog_validation`, and does **not** approve the remaining hypotheses in Master Plan §17.3 — in particular its deadline-oriented wording ("¿Hasta cuándo puedo cambiar mi solicitud?") remains unapproved and must not be shipped. This is a content decision, not an expansion of scope into source catalog validation.

## Technical approach

1. Add a `SuggestedQuestionSelected` (or equivalently named) `ChatHomeAction` that carries the selected `String`.
2. In `ChatHomeState.reduce`, handle it exactly as a question replacement: set `question` to the supplied text and set `submittedQuestion` to `null`. Do not trim, translate, append punctuation, or call an API.
3. In `ChatHomeScreen`, render the approved fixed list as separate Material text controls (for example `OutlinedButton`/`TextButton`, selected only after confirming available Material APIs) with a resource heading. Each click emits that action. Retain the established full-width/`widthIn(max = 720.dp)` layout and vertical scrolling; use a `Column`/wrapping-safe layout rather than a horizontal chip row.
4. Keep screen state hoisted through the existing `App()` reducer callback. Do not introduce a ViewModel, event flow, route, dependency, or platform adapter for this synchronous state-only addition.
5. Add previews for the visually distinct empty home with suggestions and a long/wrapped example at compact width and enlarged font scale, using the existing `MaterialTheme` wrapper.

## Expected file changes

- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: selection action and pure reducer case.
- **Update** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: shared suggestion section, click wiring, and targeted previews.
- **Update** `shared/src/commonMain/composeResources/values/strings.xml`: approved heading/instruction and example text resources.
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatHomeStateTest.kt`: focused reducer coverage.
- **Do not change** Android/Desktop entry points, Gradle dependencies, backend/contracts, land storage, or `init.sh`.

## Visual design impact

Use the current calm Material surface and theme colors; no new palette or icon is needed. Place a concise instruction plus three vertically scannable text controls near the composer. Preserve ample spacing, readable body text, and the current 720dp content maximum. Full question text must be visible (wrap rather than ellipsize) and controls must not rely on color alone to communicate that they are selectable.

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
./init.sh --verify
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
- `./init.sh --verify` output, or the exact Android SDK blocker while retaining any completed checks.
- Android and Desktop screenshots or a concise manual-check record showing examples, selected composer text, and enlarged/wrapped text.
- The recorded approval in the Content decision section of this spec, matched byte-for-byte against the shipped Compose string resources (no separate owner approval remains outstanding).

## Durable documentation impact

- `AGENTS.md`: **not needed**; its shared-UI, Spanish, accessibility, and source-grounding rules already apply.
- `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, and `MasterPlanV3.md`: **not needed**; this implements their existing example-prompt direction without changing product policy.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: **not needed**; neither exists and this feature adds no architecture/constraint.
- `PROGRESS.md` and `feature_list.json`: **update after verified implementation only** with result/evidence; do not update as part of planning.

## Validator checklist

- [ ] The shipped examples are exactly the three approved strings in the Content decision section (verbatim, including `¿` and accents), with no extra, removed, reordered, or reworded prompts.
- [ ] The home has a small, plain-Spanish, shared suggestion area with all text in Compose resources.
- [ ] Tapping every example fills—not sends—the composer exactly, enables `Preguntar`, and clears stale submitted state.
- [ ] Existing whitespace rejection and original-wording submission behavior still pass.
- [ ] Reducer tests include replacement, stale-state clearing, edit/submit preservation, and a Unicode/Spanish-text case.
- [ ] Controls are keyboard-operable, screen-reader-readable as text controls, wrap under enlarged text, and fit Android/Desktop layouts.
- [ ] `:shared:jvmTest` passes; `--verify` result and any Android SDK limitation are truthfully recorded.
- [ ] No backend, land, navigation, platform-entry, dependency, or unrelated feature changes are included.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ChatHomeStateTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/suggested_questions.md.
- Added ChatHomeAction.SuggestedQuestionSelected(String) and a pure reducer case that sets question to the supplied text and clears submittedQuestion; no API/navigation/dependency added.
- The three approved example strings are shipped verbatim as shared Compose string resources (chat_home_suggestion_solicitud_unica, chat_home_suggestion_sigpac, chat_home_suggestion_condicionalidad); a byte-for-byte comparison against the spec Content decision passed, and the unapproved deadline wording is absent.
- ./gradlew :shared:jvmTest passes; ChatHomeStateTest 7/7, including 4 new tests (example replaces existing text, clears stale submitted state, submits verbatim then keeps edits, Spanish/Unicode punctuation intact).
- ./init.sh --verify BUILD SUCCESSFUL: :shared:jvmTest, :shared:testAndroidHostTest (ChatHomeStateTest 7/7), :androidApp:assembleDebug (androidApp-debug.apk built), :desktopApp:build.
- Android emulator smoke (Medium_Phone_API_35, 1080x2400, debug APK): all three examples visible without sideways scrolling; tapping each fills the composer with the exact question and enables Preguntar with no answer/network state; submit shows only 'Tu pregunta está lista para continuar.'; re-selecting an example clears the stale submitted message; at font_scale 2.0 the labels wrap to two lines with no horizontal overflow (max right edge 954 of 1080).
- Desktop: :desktopApp:run launched the shared App() and stayed alive ~50s with no runtime exception; interactive visual/click smoke was not captured in this non-interactive session.
- Ready for independent validation; no Android SDK blocker remains in this worktree.
- Independent validator ACCEPTED this feature (record: docs/validations/suggested_questions.md) after re-running :shared:jvmTest --rerun-tasks (ChatHomeStateTest 7/7), :shared:testAndroidHostTest, :androidApp:assembleDebug, and :desktopApp:build, and independently confirming the three shipped strings match the spec byte-for-byte with no unapproved wording.
