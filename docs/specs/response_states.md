# Feature Spec: `response_states`

## Source metadata

- **Feature:** `response_states` — Show answer and abstention states (`client`), `not_started` at planning (2026-10-13).
- **Depends on:** `chat_question_submission`, `safe_abstention`, `visual_foundation` (all accepted).
- **Source behavior:** The conversation makes a supported answer visibly different from an abstention and presents the limitation in plain Spanish.
- **Source verification:** Show one answered and one abstained response and confirm their states and next steps are understandable.
- **Feature-list note:** Do not use a confident visual treatment to imply legal certainty.
- **Handoffs received:** `safe_abstention` hands the abstention's look (layout, colour, announcement) to this feature and requires that it "must not add a legal fact or contradict the pinned message"; `grounded_answer_generation` states the answered `answer` already contains the code-owned lead-in and orientative notice and that this feature "must not duplicate the notice"; `visual_foundation` R3 requires this feature to consume the caution tokens, not redefine them.

## Goal and boundaries

Make the two decoded response states visibly different **inside the transcript** using only the accepted theme tokens and the server's own Spanish copy: an answered reply keeps the calm neutral `Asistente` card, an abstention becomes a caution-styled `Asistente` entry with a short plain-Spanish state label and the pinned limitation/next step rendered verbatim. No answer may gain a "definitive/verified" treatment, and an abstention must never look like an answer or like a network failure.

**In scope**

- One minimal presentation state carried by each assistant transcript entry, so every entry keeps the state it arrived with (an earlier abstention stays visible after a later answer).
- One caution treatment for the abstained entry built from the accepted `cautionSurface`/`caution` tokens plus one new state label; the answer text is always the server `answer` verbatim.
- Non-color cue and semantics for the new state (visible label, merged node, polite announcement).
- Previews showing one answered and one abstained response together, plus narrow (`widthDp = 320`) and large-text (`fontScale = 2f`) variants.
- Pure `commonTest` coverage for the per-entry state, one abstention driven through `ChatConversation` with a fake `AnswerService`, and one contrast row for the new colour pair.

**Non-goals**

- Source cards, links, verification dates, or `[n]` marker presentation: `answer_source_cards` owns them; the answer body is rendered verbatim.
- Land clarification UI, land names, `land_scope`, or `land_ids_to_choose` rendering: `land_clarification`/`minimal_land_context` own them. The existing neutral acknowledgement is unchanged.
- Failure/retry copy and behavior: accepted in `network_error_recovery`, unchanged here.
- Any new dependency, Gradle module, navigation, ViewModel, DI, or coroutine scope; any change to `contracts/`, `backend/`, `knowledge/`, the shipped theme values (one added contrast test row only), land code, platform entry points, `init.sh`, or Gradle.
- Client-generated abstention text, reason-specific copy, next-step copy, disclaimer, or any confident affordance (badge, checkmark, green/success colour, "verificado" wording).
- A full screen-reader/focus/large-text audit: `chat_accessibility` owns it (carried finding F3, `visual_foundation` U3).

## Job story

When the assistant replies, I want to see at a glance whether it actually found a supported answer or is telling me, in plain words, that it cannot confirm this and what to do next — so I never act on a "no lo sé" as if it were a rule, and never mistake a real answer for a promise.

## Acceptance scenarios

### One answered response shows the supported-answer state

Given a contract-valid `answered` response arrives, when it is appended, then exactly one assistant entry appears carrying the `answered` state, its body is the server `answer` character-for-character (lead-in and orientative notice included), the entry keeps the neutral `surface` card and the `Asistente` label, and no client disclaimer, success colour, badge, source card, or invented citation is added.

### One abstained response shows a distinguishable limitation

Given a contract-valid `abstained` response arrives, when it is appended, then exactly one assistant entry appears carrying the `abstained` state, its body is the server `answer` character-for-character, and it is rendered with the caution fill (`cautionSurface`), a caution border, and an explicit plain-Spanish state label above the message, so the state is readable from text alone and never from colour alone. The visible next step is the one already inside the server message; the client adds none.

### The two states stay distinguishable in one conversation

Given a conversation with an abstained turn followed by an answered turn (and the reverse), when the transcript is rendered, then each entry keeps the state it arrived with (the earlier abstention stays caution-marked), and per-entry rendering never depends on the mutable `lastResponseStatus`. Every assistant entry is created only from a decoded response.

### Both states are understandable when shown together

Given one answered and one abstained response in the same conversation, when a person reads the screen, then the two entries are visually distinct, the abstained entry states its limitation and next step in plain Spanish, and both keep their textual `Tú`/`Asistente` labels. (This is the feature-list verification.)

### An abstention is never an answer and never gains facts

Given any abstained response, when it is rendered, then no source, citation marker, figure, date, land name, or client-authored next step is added, the client does not branch on an abstention reason (the wire payload carries none), and the message is never re-worded, shortened, or replaced — so all nine abstention reasons get the same client state label.

### Clarification stays neutral; a failure is still not an answer

Given a `needs_land_clarification` response (empty `answer`), then no answer or abstention entry is appended and the neutral acknowledgement is unchanged. Given a request fails or never reaches the service, then only the accepted danger `ChatFailureNotice` with `Reintentar` is shown and no transcript entry is added; a decoded abstention is never shown as a failure. The three states are therefore distinct: neutral answer, caution abstention, danger failure.

### Copy and accessibility of the new state

Given the abstained entry is shown, when assistive technology reads it, then `Asistente`, the state label, and the limitation text are read as one merged node, the entry is a polite live region so the limitation is announced, and the caution cue is always accompanied by that text. The entry renders without clipping at `widthDp = 320` and `fontScale = 2f`.

### Nothing else changes

Given the feature ships, when the existing suites run, then the composer, working state, character-limit copy, suggested questions, clarification acknowledgement, failure notice, land screens, theme values, contract, and backend behave exactly as before, with no previously passing test regressing.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: pure `ChatHomeState`, `ChatMessage(speaker, text)`, `ChatHomeAction.ResponseReceived`, and `reduce`. `ResponseReceived` appends `ChatMessage(Speaker.ASSISTANT, response.answer)` only when the answer is non-empty, and stores `lastResponseStatus`/`landIdsToChoose` for the **latest** turn — so an abstained and an answered reply are indistinguishable in the transcript, and the only status field is overwritten by the next turn.
- `ChatConversation.kt`: applies `reduce` and runs the single `AnswerService.ask` on the injected scope; it classifies only thrown failures, so a decoded `abstained` response already takes the success path (asserted by `ChatHomeStateTest.a decoded abstention is never treated as a failure`).
- `App.kt`: `ChatHomeScreen` renders the ordered transcript (`ChatMessageBubble` → `ChatBubble`: one shared card for both speakers, `surfaceVariant` for the person, `surface` for the assistant, `outlineVariant` border, textual `Tú`/`Asistente` labels, merged semantics), the working notice, the clarification acknowledgement, `ChatFailureNotice` (danger `errorContainer`/`error`/`onErrorContainer`, polite live region, `Reintentar`), the composer, and seven `ManijeroTheme` previews.
- `theme/ManijeroColors.kt` + `ManijeroTheme.kt`: `ManijeroSemanticColors(caution, onCaution, cautionSurface, primaryStrong)` through the public `LocalManijeroSemanticColors`; `caution` `#704600` on `cautionSurface` `#FFF2D4` is documented and contrast-tested (7.37:1), and the token-board preview already renders a caution callout this way. No screen consumes the semantic local yet.
- `composeResources/values/strings.xml`: one shared Spanish resource file; reusable keys exist (`chat_speaker_you`/`chat_speaker_assistant`, `chat_home_retry`, `land_list_retry`). `chat_home_submitted` is now unused but stays untouched.
- `chat/AnswerService.kt`: `AskResponse(status, answer, sources, land_scope, land_ids_to_choose)`, `AnswerStatus { answered, abstained, needs_land_clarification }`, `AnswerSource`, `KtorAnswerService`, `UnavailableAnswerService`.
- `contracts/openapi.yaml` + `contracts/examples/response-{answered,abstained,needs-land-clarification}.json`: `AskResponse` is `additionalProperties: false` with exactly five keys, so **no abstention reason reaches the client**; `abstained` requires a non-empty `answer` ≤ 1200 with `sources: []` and `land_ids_to_choose: []`; `answered` carries typed `AnswerSource`s.
- `docs/specs/safe_abstention.md`: nine code-owned pinned Spanish messages (no digit, no date, each ending in a next step). Two are used as preview samples and in tests, verbatim: `No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa.` (`no_evidence`) and `No puedo confirmar ese dato con los documentos oficiales revisados. Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa.` (`false_premise`).
- `backend/app/generation.py`: `LEAD_IN`/`NOTICE` are code-owned and part of the answered `answer` string, so the client must not append a second notice.
- `CONSTRAINTS.md`, `DESIGN.md`: no answer claim may bypass `verify_draft`; markers/`sources`/notice are code-owned; an abstention is the accepted payload with `sources: []` and one pinned message; a failed request is never an answer. `DESIGN.md` line 84 asks to "state the limitation and next step visibly" and line 78 forbids a confident legally-definitive treatment.
- Tests: `ChatHomeStateTest`/`ChatConversationTest` (`kotlin.test`, `reduce` assertions, fake/`CompletableDeferred` `AnswerService`, assistant assertions written as `ChatMessage(Speaker.ASSISTANT, "…")`); `KtorAnswerServiceTest` (`MockEngine` + `runTest`); `theme/ManijeroColorsTest` holds the WCAG pair table any new in-app pair can join.
- `init.sh`: `--verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; no new mode is needed, and `local.properties` exists in this worktree so the Android checks are expected to run.

Sized correctly: one added presentation field, one UI branch, one string, one caution style, previews, and tests. One user flow; no new data model, persistence, transport, or contract change.

## Technical approach

### 1. Per-entry response state (pure, in `ChatHomeState.kt`)

```kotlin
data class ChatMessage(
    val speaker: Speaker,
    val text: String,
    /** Assistant-only: the decoded response state. Never read for [Speaker.USER] entries. */
    val answerStatus: AnswerStatus = AnswerStatus.answered,
)
```

- `ResponseReceived` is the **only** site that appends an assistant entry and must pass `response.status`, so the state is copied, never inferred. The non-empty-answer guard and the clarification path (which appends no entry) stay as they are.
- The default keeps every existing `ChatMessage(Speaker.USER, …)` construction and the existing answered-only assistant assertions compiling and equal. It is documented as assistant-only; a future creation site must set it (R4 + the `CONSTRAINTS.md` rule).
- `lastResponseStatus`/`landIdsToChoose` keep their meaning for clarification; the UI renders per-entry state only from `answerStatus`.
- The file stays Compose-free and I/O-free.

### 2. Presentation mapping (exhaustive, in `App.kt`)

`ChatMessageBubble` renders from `message.speaker` plus `message.answerStatus` through an exhaustive `when` over `AnswerStatus`, so a future status cannot silently fall through:

| Entry | Fill | Border | Labels | Body |
|---|---|---|---|---|
| `Speaker.USER` | `surfaceVariant` | `outlineVariant` | `Tú` (`primary`) | verbatim |
| assistant, `answered` | `surface` | `outlineVariant` | `Asistente` (`primary`) | server `answer` verbatim |
| assistant, `abstained` | `cautionSurface` | `caution` | `Asistente` (`onSurfaceVariant`) + state label (`caution`) | server `answer` verbatim |
| assistant, `needs_land_clarification` (only if a non-empty answer ever arrives) | `surface` | `outlineVariant` | as today, no state label | verbatim, neutral, no answer claim |

`ChatBubble` gains only what this needs, all defaulted so existing call sites are unchanged: `borderColor: Color = MaterialTheme.colorScheme.outlineVariant`, `stateLabel: String? = null`, `stateLabelColor: Color = labelColor`.

The abstention body uses `MaterialTheme.colorScheme.onSurface` on `cautionSurface` for long-text readability; the caution hue is carried by the fill, border, and state label. The entry stays one merged semantics node (so the label and message are read together) and becomes a `LiveRegionMode.Polite` region, matching the accepted working/failure notices. No icon is required; if one is added it must be paired with the label text, never colour/icon alone. The answered entry deliberately gets no client-owned label or disclaimer beyond `Asistente`, because the code-owned lead-in/notice already frames it and any "verified/asegurado" affordance would be the confident treatment the feature note forbids.

### 3. Copy contract (ship verbatim)

| Key | Text | Used for |
|---|---|---|
| `chat_answer_state_abstained` | `Sin respuesta segura` | the caution state label on an abstained entry |

Plain Spanish, existing tú voice, no digit, no date, no legal claim, cause-neutral, so it fits all nine pinned abstention messages without contradicting any of them. Do not add reason-specific copy: the reason is not on the wire. Reuse `chat_speaker_you`/`chat_speaker_assistant`; do not change or delete any existing string.

### 4. Deliberately not done

- No marker parsing/annotation and no source rendering: `answer_source_cards` owns them, and verbatim rendering keeps the contract's `[n]` ≡ `sources[n-1]` meaning untouched.
- No client next-step copy, phone number, or link: the pinned message already ends with the next step, and inventing one would add ungrounded content.
- No change to the failure notice, working notice, clarification acknowledgement, or composer.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `answerStatus` on `ChatMessage` and `response.status` in `ResponseReceived`.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the `ChatBubble` border/state parameters, the per-entry `when` in `ChatMessageBubble`, and previews (answered conversation, abstained conversation, both states together, abstention at `widthDp = 320`/`fontScale = 2f`), all inside `ManijeroTheme`.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the single new string.
- **Update** `shared/src/commonTest/.../ChatHomeStateTest.kt`: an abstained response appends one assistant entry with `answerStatus == abstained` and the message verbatim; an answered response appends one with `answered`; an earlier abstention keeps its state after a later answer; a clarification response still appends no entry and keeps `awaitingLandClarification`; a decoded abstention is still never a failure.
- **Update** `shared/src/commonTest/.../ChatConversationTest.kt`: a fake `AnswerService` returning the accepted abstained shape yields exactly one user message, one assistant entry carrying `abstained`, no `failure`, and the pinned message unchanged.
- **Update** `shared/src/commonTest/.../theme/ManijeroColorsTest.kt`: one contrast row asserting `onSurface` on `cautionSurface` ≥ 4.5:1 (no theme value changes).
- **Update** `CONSTRAINTS.md` during implementation with one short client MUST rule (see durable docs).
- **Do not modify**: `contracts/`, `backend/`, `knowledge/`, `theme/ManijeroColors.kt`/`ManijeroTheme.kt`, `lands/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, any Gradle file or version catalog, `init.sh`, and `feature_list.json`/`PROGRESS.md` while implementing.

## Visual design and accessibility impact

Uses the accepted theme only: `LocalManijeroSemanticColors.caution`/`cautionSurface` for the new state (documented 7.37:1 pair), with `surface`/`surfaceVariant`/`outlineVariant` unchanged and no raw colour outside `theme/`. Three states stay distinct and all are non-colour-cued: neutral answer card, caution abstention card with an explicit label, danger failure notice with `Reintentar`. Long pinned messages wrap and the screen still scrolls; nothing is clipped at `fontScale = 2f`; no control is added or resized, so Material's minimum target size is untouched. Known limits owned elsewhere: no transcript auto-scroll (carried F3), Desktop OS text scaling is preview-based (`visual_foundation` U3), and the full screen-reader announcement policy is `chat_accessibility`.

## Implementation plan and tasks

1. Write the `ChatHomeStateTest` expectations first (abstained entry state, answered entry state, earlier abstention surviving a later answer, clarification unchanged, abstention not a failure), then add `answerStatus` and the `ResponseReceived` mapping until they pass.
2. Add the `ChatConversationTest` abstention coverage.
3. Add the `ChatBubble` parameters and the exhaustive per-entry `when`; add the string and the previews.
4. Add the `onSurface`-on-`cautionSurface` contrast row.
5. Run the checks below plus the preview/manual review; byte-for-byte compare the new string with this spec; run the colour-centralization and logging greps.
6. Update `CONSTRAINTS.md`.
7. Update `feature_list.json`/`PROGRESS.md` only after implementation and independent validation, recording only the commands actually run (the planner must not mark this feature complete).

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests "com.jamarglex.manijero.ChatConversationTest"
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest
./gradlew :desktopApp:build
./gradlew :androidApp:assembleDebug
./init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # matches only under theme/
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
```

`local.properties` exists, so the Android steps are expected to run; if the SDK is unavailable, record the exact blocker instead of claiming a result. There is no persistent E2E command and no Compose UI-test harness, so focused pure tests plus preview/manual review are the justified coverage; do not claim E2E or automated UI coverage.

Manual / preview evidence (record what actually happened):

1. Show one answered and one abstained response in the same transcript (the preview set, or a temporary non-committed fake `AnswerService` at a platform root) and confirm each state and next step is understandable from text alone; the next step must be the sentence inside the server message.
2. Greyscale check: with the caution fill removed, the abstention is still identifiable from the state label alone.
3. `fontScale = 2f` and `widthDp = 320` on the abstention entry: no clipping or overlap.
4. Honest limitation: the shipped default is `UnavailableAnswerService` and there is still no platform `/ask` (carried finding F1), so a real answered/abstained turn cannot be produced in the running apps without a temporary fake. Report that limit; never ship a production fake and never hard-code an endpoint.

Capture: focused and full test counts/names; the byte-for-byte string comparison; the per-entry state assertions; a screenshot or written record of both states plus the greyscale and large-text checks; the two `grep` outputs; and `./init.sh --verify` output (or the exact blocker).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One client MUST rule: a supported answer and an abstention MUST stay distinguishable; an abstention MUST render its code-owned message verbatim in the transcript with a non-confident caution treatment and no source, figure, date, or client next step; no answer MUST receive a confident legal-certainty treatment. `answer_source_cards` and `chat_accessibility` render this transcript next. |
| `DESIGN.md` | Not needed | Lines 78 and 84 already require the treatment implemented here; no token, role, or surface is added. |
| `AGENTS.md` | Not needed | Plain-Spanish, accessibility, and shared-`commonMain` rules already govern. |
| `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, `MasterPlanV3.md` | Not needed | No product, glossary, domain, or risk change; the missing `/ask` route stays tracked as F1 in `feature_list.json`/`PROGRESS.md`. |
| `docs/specs/safe_abstention.md`, `docs/specs/grounded_answer_generation.md` | Not needed | Their handoffs are executed, not revised. |
| `ARCHITECTURE.md` | Not needed | It does not exist; no module, boundary, or dependency is added. |
| `init.sh` | Not needed | No new mode; it must not start a service. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record evidence, status, and the F1 limitation then; planning does not touch them. |

## Risks and open decisions

- **R1 No abstention reason on the wire:** `AskResponse` is `additionalProperties: false` with five keys, so the client cannot distinguish the nine reasons and must not pretend to; one state label covers all of them. Reason-specific copy needs a contract change owned elsewhere.
- **R2 F1 wiring gap:** with no platform `/ask`, a real answered/abstained turn cannot be produced in the running apps; on-device evidence needs a temporary non-committed fake and the rest is preview-based. State this instead of implying an end-to-end smoke.
- **R3 Do not duplicate the notice:** the answered `answer` already contains the code-owned lead-in and notice; a client disclaimer would duplicate or weaken it, so the body stays verbatim.
- **R4 Fail-open default:** `answerStatus` defaults to `answered`, so a future assistant-entry creation site that forgets it would render neutrally rather than as an abstention. Mitigations: only `ResponseReceived` creates assistant entries today, the value is copied from `response.status`, a test asserts the abstained entry state, and the `CONSTRAINTS.md` rule plus this checklist guard it.
- **R5 Markers render verbatim:** `[1]`-style markers appear in the answer text until `answer_source_cards` ships cards; with the corpus still empty, no real marker-bearing answer exists yet, so this is a documented gap, not a defect here.
- **R6 Three states, three treatments:** abstention uses caution, failure uses danger, an answer uses the neutral card. Do not fold the abstention into `ChatFailureNotice` — an abstention is a decoded answer and belongs in the transcript, while a transport failure is not an answer and stays out of it.
- **R7 Desktop text scaling** stays preview-based (`visual_foundation` U3 / carried F3); the full screen-reader and focus pass stays with `chat_accessibility`.
- **U1** Whether the state label should ever vary by reason (needs a contract change): revisit when a reason reaches the wire.
- **U2** Whether the answered entry should also be a polite live region: `chat_accessibility` decides; this feature only announces the abstention limitation.

## Validator checklist

- [ ] An `answered` response appends exactly one assistant entry carrying `answered`, its text equals the server `answer` byte-for-byte (lead-in and notice included), and no client disclaimer, success colour, badge, checkmark, source, or invented citation was added.
- [ ] An `abstained` response appends exactly one assistant entry carrying `abstained`, rendered with the accepted `cautionSurface`/`caution` tokens plus the `Sin respuesta segura` label, with text equal to the pinned server message byte-for-byte.
- [ ] An abstention in an earlier turn is still caution-marked after a later answered turn, so per-entry rendering never depends on `lastResponseStatus`; assistant entries are created only from a decoded response.
- [ ] No abstention adds a source, marker, figure, date, land name, or client next step; the client does not branch on an abstention reason.
- [ ] A `needs_land_clarification` response still appends no answer entry and keeps the neutral acknowledgement; a failed request still shows only the accepted danger notice with `Reintentar`; a decoded abstention is never shown as a failure.
- [ ] The new state is not colour-only: the state label is visible text, the entry is one merged semantics node and a polite live region, and nothing is clipped at `widthDp = 320` / `fontScale = 2f`.
- [ ] The single new string matches this spec verbatim; no existing string was changed or deleted; `chat_home_submitted` was left untouched.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, Gradle change, endpoint, engine, or shipped fake; `contracts/`, `backend/`, `knowledge/`, the theme values (beyond one added contrast row), land code, platform roots, and `init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`, and no logging/printing of question, answer, payload, or exception text (grep evidence).
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, `./init.sh --verify`, and the contract validator pass (or the exact environment blocker is reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the final diff matches this spec's file list, and the F1 limitation is recorded rather than worked around.

### Follow-up status after `answer_source_cards`

- **R5 closed from this side** (2026-10-13): for a conforming payload (distinct `[n]` markers exactly `1..sources.size`) `answer_source_cards` now renders each `[n]` token as a reference numeral with a matching numbered source card; a non-conforming payload (F1: absent, sparse, out-of-range, non-numeric, or leading-zero markers) rewrites nothing, so this feature's accepted answer/abstention rendering is unchanged.
