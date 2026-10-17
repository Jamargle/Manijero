# Feature Spec: `answer_land_scope`

## Source metadata

- **Feature:** `answer_land_scope` — Show which land context was used (`lands-chat`)
- **Status at planning:** `not_started`; depends on accepted `land_clarification` and
  `answer_source_cards` (both `accepted`, so it is dependency-ready).
- **Source behavior:** A person can tell whether an answer is general, based on all lands, or based
  on the land they selected.
- **Feature-list verification:** View general, all-land, and selected-land responses and confirm the
  scope is clear in plain Spanish.
- **Feature-list note:** Never imply that land details prove eligibility.
- **Handoffs received:**
  - `docs/specs/minimal_land_context.md` and `docs/specs/land_clarification.md`: the answer's
    `land_scope` rendering is explicitly handed to this feature; the client "still parses `land_scope`
    but does not render or store it here". The `selected` resubmission and the chooser are accepted.
  - `docs/specs/answer_source_cards.md`: the answered branch of `ChatMessageBubble` and the per-entry
    `sources` pattern are the rendering precedent; the abstention treatment, the code-owned notice,
    and the fail-closed marker/card gate must stay unchanged.
  - `docs/specs/response_states.md` + `CONSTRAINTS.md`: no answer may receive a confident
    legal-certainty treatment; an abstention stays caution with its pinned message verbatim.
- **Size:** one assistant-only presentation field, one short label on the transcript entries, three
  pinned strings, previews, and tests. One user flow, no data model, persistence, transport, or
  contract change.

## Goal and boundaries

Make the scope of each answer visible **inside the transcript**: every assistant entry that carries
an answer states, in plain Spanish, whether the reply did not use the stored lands (`general`), took
all of them into account (`all_active`), or took the lands the person chose (`selected`). The client
renders only the `land_scope` its own decoded response carried — it never infers the scope, never
names a land from it, and never suggests that the land details justify or prove anything.

**In scope**

- Assistant-only `landScope` on `ChatMessage`, copied at the single entry-creation site
  (`ResponseReceived`) from `response.land_scope`, exactly like `answerStatus`/`sources`.
- One short scope caption on each assistant entry that has an answer (answered and abstained),
  mapped exhaustively from the three `LandContextMode` values to three pinned Spanish strings.
- Previews showing a general, an all-lands, and a selected-lands reply (plus an abstention with a
  scope) and a narrow/large-text variant, all inside `ManijeroTheme`.
- Pure `commonTest` coverage for the per-entry scope and one `ChatConversation` case through a fake
  `AnswerService`.

**Non-goals**

- Any change to `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, the platform entry
  points, Gradle, or `scripts/init.sh`. `AskResponse.land_scope` already exists and is already decoded.
- Naming the selected lands, showing a land id, a land detail, or a per-land breakdown: the wire
  carries only the mode, so the caption stays generic.
- The land-data disclosure notice, what is stored locally, or what leaves the device:
  `land_data_disclosure` owns it. The full screen-reader/focus/large-text audit: `chat_accessibility`
  owns it.
- Any change to the composer, working notice, character-limit copy, suggested questions, the
  clarification chooser, the abstention treatment, the code-owned answer notice, the source cards, or
  the failure notice.
- Client-authored certainty wording, an eligibility claim, a next step, or a new control; any new
  module, dependency, ViewModel, navigation, or logging.

## Job story

When the assistant replies, I want to know at a glance whether it used my lands — none of them, all
of them, or the ones I picked — so I can tell whether adding or choosing a land could change the
answer, without ever being told that my land's details prove I qualify for anything.

## Acceptance scenarios

### A general answer is labelled as not using the lands

Given a decoded `answered` response with `land_scope: general`, when its entry is rendered, then the
entry shows the caption `No tiene en cuenta tus terrenos.` below the `Asistente` label, the answer
body is unchanged, and no land is named.

### An all-lands answer is labelled as using all of them

Given a decoded `answered` response with `land_scope: all_active`, when its entry is rendered, then
the entry shows `Tiene en cuenta todos tus terrenos.` and nothing else about the lands is added.

### A selected-lands answer is labelled as using the chosen lands

Given a decoded `answered` response with `land_scope: selected` (the accepted `selected`
resubmission), when its entry is rendered, then the entry shows `Tiene en cuenta los terrenos que
elegiste.`, names no land and no id, and the answered card keeps its neutral treatment.

### Each entry keeps the scope it arrived with

Given a `selected` reply followed by a `general` reply (and the reverse), when the transcript is
rendered, then each entry keeps the scope its own response carried and nothing is rendered from the
mutable `lastResponseStatus`.

### An abstention also states its scope and stays an abstention

Given a decoded `abstained` response with a `land_scope`, when its entry is rendered, then the entry
keeps the caution treatment and the `Sin respuesta segura` label **and** shows the scope caption; no
source, marker, figure, date, or land name is added and the pinned message stays verbatim.

### A clarification and a failure show no scope

Given a `needs_land_clarification` response (empty `answer`), then no assistant entry is appended and
no scope caption is shown. Given a request fails or never reaches the service, then only the accepted
danger notice is shown and no scope caption is added (a failure is not an answer).

### Copy, clarity, and accessibility

Given any scope caption, when assistive technology reads the entry, then the `Asistente` label, the
caption, and the body are read as one merged node, the caption is plain, calm, and non-color-cued
(neutral text, never a success/olive badge), and the entry renders without clipping or horizontal
overflow at `widthDp = 320` and `fontScale = 2f`. No caption claims or implies that the land details
prove eligibility.

### Nothing else changes

Given the feature ships, when the existing suites run, then the composer, working state, limit copy,
suggested questions, chooser, abstention/answered/source-card rendering, failure notice, land
screens, theme values, contract, and backend behave exactly as before, with no previously passing
test regressing.

## Technical approach

### 1. Per-entry scope (`ChatHomeState.kt`)

```kotlin
data class ChatMessage(
    val speaker: Speaker,
    val text: String,
    val answerStatus: AnswerStatus = AnswerStatus.answered,
    val sources: List<AnswerSource> = emptyList(),
    /** Assistant-only: the `land_scope` the response arrived with. Never read for [Speaker.USER]. */
    val landScope: LandContextMode = LandContextMode.general,
)
```

- `ResponseReceived` (the only assistant-entry creation site) passes `response.land_scope` unchanged,
  alongside `response.status` and `response.sources`.
- The default `general` keeps every existing `ChatMessage(Speaker.USER, …)` and answered-only
  assistant assertion compiling and equal, and is the safe default: a future creation site that
  forgets the field shows "not using lands" rather than implying land context. It is documented as
  assistant-only.
- The file stays Compose-free and I/O-free; `LandContextMode` is imported from `chat`.

### 2. Scope caption (`App.kt`)

`ChatBubble` gains one defaulted parameter `scopeLabel: String? = null`, rendered as a `labelLarge`
line in `MaterialTheme.colorScheme.onSurfaceVariant` directly below the speaker label and above any
`stateLabel`/body. Every existing call site is unchanged.

`ChatMessageBubble` computes the caption for the two branches that carry an answer:

| Entry | Caption |
|---|---|
| assistant, `answered` | the scope of `message.landScope` |
| assistant, `abstained` | the scope of `message.landScope`, above the unchanged `Sin respuesta segura` label |
| assistant, `needs_land_clarification` (defensive; unreachable) | none — kept as today |
| user / working / failure | none — defaulted `null` |

The mapping is an exhaustive, `else`-free `when` over `LandContextMode`, so a fourth mode would break
compilation instead of silently rendering nothing:

```kotlin
private fun landScopeCaption(scope: LandContextMode): StringResource = when (scope) {
    LandContextMode.general -> Res.string.chat_land_scope_general
    LandContextMode.all_active -> Res.string.chat_land_scope_all_active
    LandContextMode.selected -> Res.string.chat_land_scope_selected
}
```

The caption is only a description of the land context taken into account; it is neutral text (not a
badge, checkmark, or success color), adds no land name, id, or claim, and the abstained entry keeps
its caution treatment and pinned message verbatim.

### 3. Copy contract (ship verbatim)

| Key | Text | Used for |
|---|---|---|
| `chat_land_scope_general` | `No tiene en cuenta tus terrenos.` | `land_scope: general` |
| `chat_land_scope_all_active` | `Tiene en cuenta todos tus terrenos.` | `land_scope: all_active` |
| `chat_land_scope_selected` | `Tiene en cuenta los terrenos que elegiste.` | `land_scope: selected` |

Plain Spanish, existing tú voice, no digit, no date, no legal claim, no eligibility implication. Do
not change or delete any existing string.

### 4. Deliberately not done

- No land name or id in the caption: the wire carries only the mode, and the client must not invent a
  name or show a possibly stale one.
- No scope on a clarification or a failure: neither is an answer, and a clarification's `selected`
  scope is a hard-coded echo, not a description of an answer.
- No confidence affordance and no client next step: the captions only state which lands were used.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `landScope` on
  `ChatMessage`; `response.land_scope` in `ResponseReceived`.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the `scopeLabel` parameter
  on `ChatBubble`, the `landScopeCaption` helper, the answered/abstained caption wiring, and the new
  previews.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the three strings above.
- **Update** `shared/src/commonTest/.../ChatHomeStateTest.kt`: the response helper gains a `landScope`
  parameter; a `general`/`all_active`/`selected` response appends one assistant entry carrying that
  scope; an earlier entry keeps its scope after a later turn; an abstained entry carries its scope; a
  clarification still appends no entry.
- **Update** `shared/src/commonTest/.../ChatConversationTest.kt`: a fake `AnswerService` returning a
  response with a non-`general` scope yields one assistant entry carrying that scope.
- **Update** `CONSTRAINTS.md` during implementation with one short client MUST rule (see durable
  docs).
- **Do not modify**: `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, `androidApp/`,
  `desktopApp/`, `shared/src/iosMain/`, any Gradle file or version catalog, `scripts/init.sh`, and
  `feature_list.json`/`PROGRESS.md` while implementing.

## Visual design impact

Uses accepted theme roles only: the caption is `labelLarge` in `onSurfaceVariant` inside the existing
bubble; the answered card stays neutral, the abstention keeps `cautionSurface`/`caution`, and the
failure notice keeps `errorContainer`/`error`. No raw color, no new token, no badge, checkmark, or
success affordance. The caption lives inside the existing merged-semantics node, so it is announced
with `Asistente` and the body; it is text, never color alone, so it survives greyscale. Long captions
wrap inside the 720dp content width and nothing is clipped at `fontScale = 2f`. No control is added
or resized. Known limits owned elsewhere: no transcript auto-scroll (carried F3) and the full
screen-reader/focus policy stay with `chat_accessibility`; Desktop text scaling is preview-based.

## Cross-feature interactions and handoffs

- **Consumes** the accepted `AskResponse.land_scope` decoded by `answer_api_contract`/
  `chat_question_submission`, the per-entry copy pattern from `response_states`/`answer_source_cards`,
  and the `selected` request from `land_clarification`.
- **Does not change** the answer body, the source cards, the abstention treatment, the chooser, the
  failure notice, or the code-owned notice.
- **Hands off** the local-data disclosure copy to `land_data_disclosure` and the full
  screen-reader/focus/large-text audit plus transcript auto-scroll to `chat_accessibility`.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One client MUST rule: every assistant entry MUST render only the `land_scope` its own decoded response carried (copied at the single creation site, never from `lastResponseStatus`), the caption MUST state in plain Spanish which lands were taken into account and MUST NOT name a land or id, imply that land details prove eligibility, add a confident affordance, or appear on a failed request or a clarification; `chat_accessibility` renders this transcript next. |
| `DESIGN.md` | Not needed | Lines 78/84 already require a readable, non-confident treatment; no token or surface is added. |
| `docs/specs/minimal_land_context.md`, `docs/specs/land_clarification.md`, `docs/specs/answer_source_cards.md`, `docs/specs/response_states.md` | Not needed | Their `land_scope`-rendering handoff is executed here, not revised; the accepted behavior is unchanged. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, `MasterPlanV3.md` | Not needed | No product, glossary, or domain change; the operating rules (plain Spanish, no invented legal facts, commonMain UI) already govern. |
| `ARCHITECTURE.md` | Not needed | It does not exist; no module, boundary, or dependency is added. |
| `scripts/init.sh` | Not needed | No new mode; it must not start a service. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record evidence, status, and the `/ask`/UI-harness limitation then; planning does not touch them. |

## Risks and open decisions

- **R1 The wire carries only the mode, not the lands used.** A `selected` caption cannot name the
  chosen lands without the client holding state; naming them is deliberately out of scope, so the
  caption stays generic. A per-land breakdown would need a contract change owned elsewhere.
- **R2 Scope can be mistaken for a cause of an abstention.** The caption only states which lands were
  taken into account and is rendered identically for answered and abstained entries; the wording
  avoids implying causation, and the abstention keeps its own `Sin respuesta segura` label.
- **R3 Fail-open default.** `landScope` defaults to `general`, so a future creation site that forgets
  it renders "not using lands" rather than implying land context. Only `ResponseReceived` creates
  assistant entries today, a test asserts the copied scope, and the `CONSTRAINTS.md` rule guards it.
- **R4 No real scope in the running apps.** With no `/ask` route, an empty corpus, and no Compose
  UI-test harness, the three captions are reachable on device only through a temporary non-committed
  fake or a preview; state that limit instead of implying an end-to-end smoke.
- **U1** Whether `selected` should ever name the chosen lands (needs client-held state and a
  decision on stale names); revisit with `land_safety_evaluation`/`land_data_disclosure`.
- **U2** Whether a `general` answer should hint that adding a land might change the answer
  (a next step): deliberately not added, because a client next step must not imply eligibility.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests ChatHomeStateTest --tests ChatConversationTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/answer_land_scope.appendix.md`](answer_land_scope.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/answer_land_scope.md` remains the authoritative acceptance record.
