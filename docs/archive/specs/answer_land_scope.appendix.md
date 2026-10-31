# Appendix — `answer_land_scope`

Planning and verification record for [`docs/specs/answer_land_scope.md`](../../specs/answer_land_scope.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/answer_land_scope.md` remains the authoritative
acceptance record.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `AskResponse(status,
  answer, sources, land_scope, land_ids_to_choose)` already decodes `land_scope: LandContextMode`
  (`general` / `all_active` / `selected`); no DTO, `answerJson`, or transport change is needed.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatMessage(speaker, text,
  answerStatus, sources)` is copied only in `ResponseReceived` from the decoded response;
  `lastResponseStatus` is latest-turn-only and must not be read for rendering.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatMessageBubble` branches
  exhaustively on `speaker × answerStatus`; the `answered` branch renders `ChatAssistantCard` +
  `SourceCardsSection`, the `abstained` branch calls `ChatBubble(stateLabel = "Sin respuesta
  segura", …)`, and the defensive `needs_land_clarification` branch renders a neutral card. `ChatBubble`
  already takes defaulted `stateLabel`/`borderColor`/`liveRegionMode`/`annotatedText`, so one more
  defaulted parameter keeps every existing call site unchanged.
- `shared/src/commonMain/composeResources/values/strings.xml`: one Spanish file; `%1$s`/`%1$d`
  placeholders and the `«%1$s»` quoting style already exist. No scope string exists today.
- `contracts/openapi.yaml` + `contracts/examples/response-answered.json` (land_scope `general`) and
  `response-abstained.json` (land_scope `all_active`): `AskResponse` is `additionalProperties: false`
  with exactly the five keys, `land_scope` enumerated to the three modes. These two accepted fixtures
  are the only scope samples to reuse (no invented value).
- `backend/app/generation.py`/`abstention.py`/`clarification.py`: `to_answer_response` and
  `to_abstention_response` echo `land_scope = land_context.mode`; `to_clarification_response` hard-codes
  `selected` (so a client must never label a clarification entry from it — there is none today). No
  backend change is needed.
- `shared/src/commonTest/.../{ChatHomeStateTest,ChatConversationTest}.kt`: `kotlin.test`, an inline
  `AskResponse` builder whose helper currently hard-codes `land_scope = LandContextMode.general`, and
  fake `AnswerService`s. No Compose UI-test harness exists, so the reducer copy plus previews are the
  automatable surface.
- `CONSTRAINTS.md`: the accepted client rules for response states, source cards, land context, and
  land clarification; `DESIGN.md` lines 78/84 (readable, non-confident treatment; no legality claim).
- `docs/specs/minimal_land_context.md`, `docs/specs/land_clarification.md`,
  `docs/specs/answer_source_cards.md`, `docs/specs/response_states.md`: the handoffs above.

Sized correctly: one added field, one label mapping, one UI line, three strings, previews, tests. No
new data model, persistence, transport, or contract change.

## Implementation plan and tasks

1. Add `landScope` to `ChatMessage`, pass `response.land_scope` in `ResponseReceived`, and extend
   `ChatHomeStateTest`/`ChatConversationTest` (per-entry scope, earlier entry unaffected, abstention
   scope, clarification appends no entry, existing default-equality assertions still hold).
2. Add `scopeLabel` to `ChatBubble`, the `landScopeCaption` exhaustive mapping, and the
   answered/abstained wiring; add the three strings and the previews (general, all-lands, selected,
   abstention with a scope, narrow/large text).
3. Run the checks below; byte-for-byte compare the three strings with this spec; run the
   color-centralization and logging greps.
4. Update `CONSTRAINTS.md`.
5. Update `feature_list.json`/`PROGRESS.md` only after implementation and independent validation,
   recording only the commands actually run (the planner must not mark this feature complete).

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests "com.jamarglex.manijero.ChatConversationTest"
./gradlew :shared:jvmTest --rerun-tasks
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./scripts/init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # matches only under theme/
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
git diff --check
```

Also:

- **Literal feature-list verification** (general, all-lands, selected): the reducer test asserts the
  three decoded `land_scope` values each produce one assistant entry carrying that scope, and the
  previews render the three captions. Because there is no platform `/ask` (carried
  `chat_question_submission` F1), an empty corpus, and no Compose UI-test harness, the on-device view
  needs a **temporary, non-committed** fake `AnswerService` at a platform root returning the accepted
  fixture shapes with each `land_scope`; record what was actually seen and delete the fake afterwards.
  Do not claim an automated UI or E2E result.
- Byte-for-byte comparison of the three new strings against this spec; confirm no existing string was
  changed or deleted and each key appears once.
- Honest limit: the caption text is verified by the string comparison plus the reducer scope
  assertions and previews, not by a UI test; the scope is derived only from the decoded response.

Capture: focused and full test counts/names (no test removed); the byte-for-byte string comparison;
the per-entry scope assertions; a written record (or preview screenshots) of a general, all-lands, and
selected reply plus the abstention with a scope; the greps; `./scripts/init.sh --verify` output (or the exact
blocker); and confirmation that `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, the entry
points, Gradle, and `scripts/init.sh` are untouched.

## Validator checklist

- [ ] Every assistant entry carries the `land_scope` its own decoded response arrived with, copied at
      the single creation site; an earlier entry keeps its scope after a later turn and nothing is
      rendered from `lastResponseStatus`.
- [ ] A `general` reply shows `No tiene en cuenta tus terrenos.`, an `all_active` reply shows
      `Tiene en cuenta todos tus terrenos.`, and a `selected` reply shows
      `Tiene en cuenta los terrenos que elegiste.`, each below the `Asistente` label, with no land
      name or id, no confident affordance, and no eligibility claim.
- [ ] An abstention keeps its caution treatment, its `Sin respuesta segura` label, and its pinned
      message verbatim, and also shows its scope; a clarification appends no entry and shows no
      caption; a failed request shows only the accepted danger notice and no caption.
- [ ] The three strings match this spec verbatim; no existing string was changed or deleted; the
      scope mapping is an exhaustive, `else`-free `when` over the three modes.
- [ ] The caption is text (never color alone), lives inside the merged-semantics node, and renders
      without clipping at `widthDp = 320`/`fontScale = 2f`; the answered card stays neutral.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, ViewModel, control,
      endpoint, or logging; `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, the platform
      roots, Gradle, and `scripts/init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`, and no logging/printing of a question, answer, payload, or
      exception text (grep evidence).
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, the iOS compile, the Android/Desktop builds,
      `./scripts/init.sh --verify`, and the contract validator pass (or the exact environment blocker is
      reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the final diff matches this
      spec's file list; the `/ask`/UI-harness limitation is recorded rather than worked around.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/answer_land_scope.md. Added assistant-only `ChatMessage.landScope: LandContextMode = general` (shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt), copied from `response.land_scope` at the single creation site `ResponseReceived` alongside `status`/`sources`; the safe `general` default keeps every existing user/answered-only assertion compiling and equal and makes a future forgotten field render 'not using lands' rather than implying land context.
- Presentation (App.kt): `ChatBubble` gained a defaulted `scopeLabel: String?` rendered as a `labelLarge` line in `onSurfaceVariant` directly below the `Asistente` label and above any `stateLabel`/body, inside the existing merged-semantics node; `landScopeCaption(scope)` is an exhaustive, `else`-free `when` over the three `LandContextMode` values; the `answered` and `abstained` branches pass `scopeLabel = stringResource(landScopeCaption(message.landScope))`, the defensive `needs_land_clarification` branch and every user/working/failure path pass nothing. The caption is neutral text (no badge, checkmark, success colour, land name, or id) and the abstention keeps its `cautionSurface`/`caution` treatment and `Sin respuesta segura` label.
- Copy (composeResources/values/strings.xml): three new keys shipped byte-for-byte equal to the spec — `chat_land_scope_general` = `No tiene en cuenta tus terrenos.`, `chat_land_scope_all_active` = `Tiene en cuenta todos tus terrenos.`, `chat_land_scope_selected` = `Tiene en cuenta los terrenos que elegiste.` A Python UTF-8 byte comparison matched all three exactly and each key appears once; `strings.xml` numstat is +3/-0, so no existing string was changed or deleted.
- New/changed previews: a general reply (the existing answered previews now default to `general`), an all-lands reply, a selected-lands reply, an abstention with an all-lands scope, and a `widthDp = 320`/`fontScale = 2f` narrow/large-text variant, all inside `ManijeroTheme`, with no control added or resized.
- Tests: `ChatHomeStateTest.response` helper gained a `landScope` parameter; new cases assert the default is `general`, each of the three decoded scopes is copied onto exactly one assistant entry, a user entry never carries a scope, an earlier entry keeps its own scope after a later reply (selected then general), an abstained entry carries its decoded scope and stays `abstained`, and a clarification still appends no assistant entry. `ChatConversationTest.response` gained a `landScope` parameter and a new case drives a fake `AnswerService` returning a `selected` scope and asserts the one assistant entry carries it. No test removed.
- Commands actually run (repository root, all pass): `python3 contracts/validate_examples.py` -> 'Validated 2 request and 3 response examples against answer_api_contract' (exit 0); focused `./gradlew :shared:jvmTest --tests ChatHomeStateTest --tests ChatConversationTest` -> BUILD SUCCESSFUL; `./gradlew :shared:jvmTest --rerun-tasks` -> 181 tests / 0 failures (`ChatHomeStateTest` 44, `ChatConversationTest` 16; was 174, +7 new, no test removed); `./gradlew :shared:testAndroidHostTest --rerun-tasks` -> 167 tests / 0 failures (was 160, +7); `./gradlew :shared:compileKotlinIosSimulatorArm64` -> BUILD SUCCESSFUL; `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` -> 72 tasks, BUILD SUCCESSFUL (debug APK); `./scripts/init.sh --verify` -> BUILD SUCCESSFUL (91 tasks, exit 0); `grep -rn 'Color(0x' ... | grep -v /theme/` -> no matches (all matches are in theme/ManijeroColors.kt); `grep -rn 'println|Log\.|Logger|printStackTrace|NSLog' shared/src androidApp/src desktopApp/src` -> no matches; `git diff --check` -> clean.
- Literal feature-list verification: the three decoded `land_scope` values each produce one assistant entry carrying that scope (reducer test) and the previews render the three captions under `Asistente`; because there is no platform `/ask` (carried `chat_question_submission` F1), an empty corpus, and no Compose UI-test harness, the on-device view would need a temporary non-committed fake `AnswerService` and no on-device screenshot was captured, so no automated UI or E2E result is claimed.
- Scope: only `CONSTRAINTS.md`, `feature_list.json`, `PROGRESS.md`, `strings.xml`, `App.kt`, `ChatHomeState.kt`, `ChatHomeStateTest.kt`, and `ChatConversationTest.kt` changed (git status --porcelain); `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, the platform entry points, all Gradle files, and `scripts/init.sh` are untouched. `./scripts/init.sh` created the worktree `local.properties` (sdk.dir) so the Android checks ran. No new module, dependency, ViewModel, navigation, control, endpoint, or logging.
- `CONSTRAINTS.md` gained the 'Client land scope' client MUST rule. Honest gaps: the caption text is verified by the byte-for-byte string comparison plus the reducer scope assertions and the previews, not by a UI test; the scope is derived only from the decoded response (the wire carries only the mode, so a `selected` caption names no land or id); greyscale and `widthDp = 320`/`fontScale = 2f` no-clipping are structural/compile-based, not an inspected render (owner `chat_accessibility`). Self-verified; awaiting independent validation.
- Independent validator ACCEPTED this feature (2026-10-13). It did not trust the implementer report and independently re-ran: `python3 contracts/validate_examples.py` (exit 0), focused `:shared:jvmTest --tests ChatHomeStateTest --tests ChatConversationTest`, `:shared:jvmTest --rerun-tasks` (181 tests / 0 failures; ChatHomeStateTest 44, ChatConversationTest 16; 174 -> 181, no test removed), `:shared:testAndroidHostTest --rerun-tasks` (167 / 0), `:shared:compileKotlinIosSimulatorArm64`, `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` (debug APK), `./scripts/init.sh --verify` (exit 0, 91 tasks), and `git diff --check` (clean). It byte-for-byte confirmed the three strings (`chat_land_scope_general`/`all_active`/`selected`, numstat +3/-0, no existing string changed) and re-ran the logging and raw-`Color(0x)` greps (matches only in theme/). With its own temporary probe test it reproduced the per-entry behavior (each `LandContextMode` value copied onto exactly one assistant entry, an earlier `selected` entry surviving a later `general` turn while `lastResponseStatus` is the latest, clarification appending no entry, `general` default). It confirmed the exhaustive `else`-free `landScopeCaption` over the three-value enum, the neutral `labelLarge`/`onSurfaceVariant` caption inside the existing merged-semantics node on answered and abstained entries only (no badge/checkmark/success colour, no land name/id, no eligibility claim), the abstention keeping its `cautionSurface`/`caution` treatment, and clean scope discipline (only the intended 8 files plus the spec; contracts/, backend/, knowledge/, theme/, lands/, platform entry points, Gradle, scripts/init.sh untouched; no new module/dependency/logging). A scoped security review found no blocking issue. Non-blocking findings: N1 (implementer updated feature_list/PROGRESS before validation, matching the established workflow), N2 (no preview explicitly named 'general'; covered by the default-scope answered previews), N3 (greyscale/320dp/2f no-clipping structural, owner chat_accessibility), N4 (carried no-on-device/E2E and generic `selected` caption limits). Verdict: accept. No repair brief required.
