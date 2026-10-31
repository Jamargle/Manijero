# Feature Spec: `suggested_questions`

## Source metadata

- **Feature:** `suggested_questions` — Example questions
- **Status / dependency:** `not_started`; `chat_home` is accepted.
- **Source behavior:** A person can tap a short example question and have its Spanish text placed in the chat flow, without needing to formulate a prompt.
- **Source verification:** Tap an example and confirm its text is submitted or ready to submit in the composer.
- **Note from the feature list:** Use examples drawn from topics actually covered by the approved MVP corpus.

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
- **Do not change** Android/Desktop entry points, Gradle dependencies, backend/contracts, land storage, or `scripts/init.sh`.

## Visual design impact

Use the current calm Material surface and theme colors; no new palette or icon is needed. Place a concise instruction plus three vertically scannable text controls near the composer. Preserve ample spacing, readable body text, and the current 720dp content maximum. Full question text must be visible (wrap rather than ellipsize) and controls must not rely on color alone to communicate that they are selectable.

## Durable documentation impact

- `AGENTS.md`: **not needed**; its shared-UI, Spanish, accessibility, and source-grounding rules already apply.
- `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, and `docs/archive/MasterPlanV3.md`: **not needed**; this implements their existing example-prompt direction without changing product policy.
- `ARCHITECTURE.md` and `CONSTRAINTS.md`: **not needed**; neither exists and this feature adds no architecture/constraint.
- `PROGRESS.md` and `feature_list.json`: **update after verified implementation only** with result/evidence; do not update as part of planning.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ChatHomeStateTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/suggested_questions.appendix.md`](../archive/specs/suggested_questions.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/suggested_questions.md` remains the authoritative acceptance record.
