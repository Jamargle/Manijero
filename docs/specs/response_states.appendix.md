# Appendix — `response_states`

Planning and verification record for [`docs/specs/response_states.md`](response_states.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/response_states.md` remains the authoritative
acceptance record.

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
- `scripts/init.sh`: `--verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; no new mode is needed, and `local.properties` exists in this worktree so the Android checks are expected to run.

Sized correctly: one added presentation field, one UI branch, one string, one caution style, previews, and tests. One user flow; no new data model, persistence, transport, or contract change.

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
./scripts/init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # matches only under theme/
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
```

`local.properties` exists, so the Android steps are expected to run; if the SDK is unavailable, record the exact blocker instead of claiming a result. There is no persistent E2E command and no Compose UI-test harness, so focused pure tests plus preview/manual review are the justified coverage; do not claim E2E or automated UI coverage.

Manual / preview evidence (record what actually happened):

1. Show one answered and one abstained response in the same transcript (the preview set, or a temporary non-committed fake `AnswerService` at a platform root) and confirm each state and next step is understandable from text alone; the next step must be the sentence inside the server message.
2. Greyscale check: with the caution fill removed, the abstention is still identifiable from the state label alone.
3. `fontScale = 2f` and `widthDp = 320` on the abstention entry: no clipping or overlap.
4. Honest limitation: the shipped default is `UnavailableAnswerService` and there is still no platform `/ask` (carried finding F1), so a real answered/abstained turn cannot be produced in the running apps without a temporary fake. Report that limit; never ship a production fake and never hard-code an endpoint.

Capture: focused and full test counts/names; the byte-for-byte string comparison; the per-entry state assertions; a screenshot or written record of both states plus the greyscale and large-text checks; the two `grep` outputs; and `./scripts/init.sh --verify` output (or the exact blocker).

## Validator checklist

- [ ] An `answered` response appends exactly one assistant entry carrying `answered`, its text equals the server `answer` byte-for-byte (lead-in and notice included), and no client disclaimer, success colour, badge, checkmark, source, or invented citation was added.
- [ ] An `abstained` response appends exactly one assistant entry carrying `abstained`, rendered with the accepted `cautionSurface`/`caution` tokens plus the `Sin respuesta segura` label, with text equal to the pinned server message byte-for-byte.
- [ ] An abstention in an earlier turn is still caution-marked after a later answered turn, so per-entry rendering never depends on `lastResponseStatus`; assistant entries are created only from a decoded response.
- [ ] No abstention adds a source, marker, figure, date, land name, or client next step; the client does not branch on an abstention reason.
- [ ] A `needs_land_clarification` response still appends no answer entry and keeps the neutral acknowledgement; a failed request still shows only the accepted danger notice with `Reintentar`; a decoded abstention is never shown as a failure.
- [ ] The new state is not colour-only: the state label is visible text, the entry is one merged semantics node and a polite live region, and nothing is clipped at `widthDp = 320` / `fontScale = 2f`.
- [ ] The single new string matches this spec verbatim; no existing string was changed or deleted; `chat_home_submitted` was left untouched.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, Gradle change, endpoint, engine, or shipped fake; `contracts/`, `backend/`, `knowledge/`, the theme values (beyond one added contrast row), land code, platform roots, and `scripts/init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`, and no logging/printing of question, answer, payload, or exception text (grep evidence).
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, `./scripts/init.sh --verify`, and the contract validator pass (or the exact environment blocker is reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the final diff matches this spec's file list, and the F1 limitation is recorded rather than worked around.

### Follow-up status after `answer_source_cards`

- **R5 closed from this side** (2026-10-13): for a conforming payload (distinct `[n]` markers exactly `1..sources.size`) `answer_source_cards` now renders each `[n]` token as a reference numeral with a matching numbered source card; a non-conforming payload (F1: absent, sparse, out-of-range, non-numeric, or leading-zero markers) rewrites nothing, so this feature's accepted answer/abstention rendering is unchanged.

### Follow-up status after `chat_accessibility`

- **U2 decided** (2026-10-13): an `answered` assistant entry **is** now a polite live region, exactly like
  the abstention. `ChatAssistantCard` gained a defaulted `liveRegionMode` and the `answered` branch
  passes `LiveRegionMode.Polite`; the `Tú` entries, the defensive `needs_land_clarification` branch, the
  working notice, the non-merging failure notice (its `Reintentar` stays a separate focusable node), and
  the abstention keep their accepted announcements. This adds no copy, token, or state and does not
  revise the accepted answer/abstention rendering.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/response_states.md.
- Implemented in shared commonMain: `ChatMessage` gains assistant-only `answerStatus: AnswerStatus = answered`, copied only in `ResponseReceived` from `response.status`, so every assistant entry keeps the state it arrived with and rendering never depends on the mutable `lastResponseStatus`; `ChatMessageBubble` branches on speaker + status through an exhaustive `when`; `ChatBubble` gains defaulted `borderColor`/`stateLabel`/`stateLabelColor` and a new neutral `ChatAssistantCard` helper.
- Presentation: answered stays the neutral `surface`/`outlineVariant` `Asistente` card (no confident affordance); abstained uses `LocalManijeroSemanticColors.cautionSurface` fill + `caution` border + visible `Sin respuesta segura` label (`caution`) over the verbatim body on `onSurface`, one merged semantics node and a polite live region; failure keeps the accepted danger `ChatFailureNotice`. The server `answer` is rendered verbatim so the code-owned lead-in/notice is not duplicated and no source/marker/figure/date/client next step is added.
- Added string `chat_answer_state_abstained` = `Sin respuesta segura` (byte-for-byte equal to the spec, verified by UTF-8 byte comparison); no existing string changed or deleted (`chat_home_submitted` untouched). Four new previews (answered, abstained, both states together, abstention at widthDp=320/fontScale=2f) all inside `ManijeroTheme`.
- Commands run (all pass): python3 contracts/validate_examples.py -> "Validated 2 request and 3 response examples against answer_api_contract"; focused ./gradlew :shared:jvmTest --tests ChatHomeStateTest --tests ChatConversationTest --tests ManijeroColorsTest -> 46 tests / 0 failures; ./gradlew :shared:jvmTest -> 82 tests / 0 failures (was 78, +4 new); ./gradlew :shared:testAndroidHostTest -> 73 tests / 0 failures (was 69, +4 new); ./gradlew :desktopApp:build :androidApp:assembleDebug -> BUILD SUCCESSFUL (androidApp-debug.apk rebuilt); ./scripts/init.sh --verify -> BUILD SUCCESSFUL; ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; git diff --check clean.
- New tests: an answered response appends exactly one assistant entry carrying `answered`; an abstained response carries `abstained` with the pinned message verbatim; an earlier abstention keeps its state after a later answered reply (per-entry, not `lastResponseStatus`); the clarification test now asserts no assistant entry; a fake `AnswerService` returning the accepted abstained shape through `ChatConversation` yields one user message, one assistant entry carrying `abstained`, the pinned message verbatim and no `failure`; one ManijeroColorsTest row asserts `onSurface` on `cautionSurface` = 14.58:1 (>= 4.5:1), no theme value changed.
- Centralization/privacy: `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero` matches only under theme/; `grep -rn "println|Log\.|Logger|printStackTrace|NSLog" shared/src androidApp/src desktopApp/src` -> no matches. CONSTRAINTS.md gained the one short client MUST rule. Scope: only CONSTRAINTS.md, strings.xml, App.kt, ChatHomeState.kt, the three test files, and the new spec changed; contracts/, backend/, knowledge/, theme values, lands/, platform roots, Gradle and scripts/init.sh untouched.
- Honest gaps: no rendered visual evidence (no interactive session, no Compose preview/UI-test runner), so the greyscale non-colour-cue and widthDp=320/fontScale=2f no-clipping claims are structural + compiled-preview based rather than an inspected render; no on-device answered/abstained turn because the shipped default is `UnavailableAnswerService` and there is still no platform `/ask` (carried F1), so on-device evidence would need a temporary non-committed fake; `:desktopApp:run` interactive smoke not run; no E2E/automated UI coverage claimed. Risk R5 (`[n]` markers render verbatim) unchanged, owned by `answer_source_cards`.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/response_states.md). It re-ran the checks itself (contract validator; :shared:jvmTest --rerun-tasks 82/0; :shared:testAndroidHostTest --rerun-tasks 73/0; :desktopApp:build :androidApp:assembleDebug --rerun-tasks 72 tasks exit 0; ./scripts/init.sh --verify exit 0; :shared:compileKotlinIosSimulatorArm64; the two greps; git diff --check clean), reproduced the WCAG pair (onSurface on cautionSurface 14.58) and byte-for-byte equality of the single new string, and independently reproduced the per-entry behavior with its own temporary probe test (10 tests: answered/abstained entry state, an earlier abstention surviving a later answer while lastResponseStatus differs, mismatch-proof per-entry rendering, clarification appending no entry, failure never an answer). It confirmed the exhaustive speaker x status branch in App.kt, verbatim body rendering with no added source/marker/figure/date/client next step, and the three distinct neutral/caution/danger states. Scope confirmed: contracts/, backend/, knowledge/, theme values (one added contrast row only), lands/, platform roots, Gradle and scripts/init.sh untouched, no logging. Non-blocking findings N1-N5 recorded (N1 closed by the orchestrator at acceptance; N2 rendered-evidence gap owned by chat_accessibility; R5 markers verbatim until answer_source_cards).
