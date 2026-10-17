# Appendix — `answer_source_cards`

Planning and verification record for [`docs/specs/answer_source_cards.md`](answer_source_cards.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/answer_source_cards.md` remains the authoritative
acceptance record.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatMessage(speaker, text, answerStatus)` has **no** source field, so the decoded `sources` are currently discarded; `ResponseReceived` is the only site that appends an assistant entry and it copies `response.status` (the pattern to follow for `sources`); `lastResponseStatus` is latest-turn-only and must not be used for rendering.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatMessageBubble` branches exhaustively on `speaker × answerStatus`; `ChatAssistantCard` → `ChatBubble` merges semantics and renders a plain `String` body; the content column is capped at `ContentMaxWidth = 720.dp`; the answered preview sample has no marker (N3).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `AnswerSource(title, issuing_body, url, location, published_or_updated_on, verified_on, excerpt)` — exactly the seven accepted keys, **no criticality**, with `excerpt` up to 2000 characters; `AskResponse(status, answer, sources, land_scope, land_ids_to_choose)`.
- `contracts/openapi.yaml`: `AnswerSource` requires all seven keys; `url` is `format: uri`; `verified_on`/`published_or_updated_on` are `format: date`; `abstained` requires `sources: []`; `AskResponse` is `additionalProperties: false`.
- `backend/app/generation.py`: marker `[n]` is `RetrievedPassage.rank`, `sources` = exactly the cited candidates, deduplicated and ascending (so `[n] == sources[n-1]` under the prefix set); `_render_claim` writes `"{text} [n]"`; `ANSWER_SOURCE_KEYS` drops `passage_id`, `source_id`, `applicability`, `critical`, `score`, `rank`; `LEAD_IN`/`NOTICE` are already inside `answer` and must not be duplicated.
- `docs/validations/grounded_answer_generation.md` F1: reproduced non-prefix acceptance (`DraftAnswer("answered", rank2.excerpt + " [2]", (2,))` → `len(sources) == 1`); not reachable from the enabled `ExtractiveGroundingGenerator`, and `knowledge/README.md` promises `[n] == sources[n-1]` unconditionally.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/`: `surface`, `surfaceVariant`, `onSurfaceVariant`, `outlineVariant`, `primary`, plus `LocalManijeroSemanticColors(caution, cautionSurface, primaryStrong)`; hex colours exist only under `theme/`. `material3` `Button`/`TextButton` give the 48dp minimum target and Desktop keyboard focus for free.
- `shared/src/commonMain/composeResources/values/strings.xml`: one Spanish file; `%1$s` placeholders are already used (`land_list_municipality`, `land_list_edit_description`), including the `«%1$s»` quoting style to follow.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt` lines 188-224: the accepted pattern for a card with an inner `semantics(mergeDescendants = true)` content node **plus** a sibling control carrying its own `contentDescription` — the source card reuses it.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/{ChatHomeStateTest,ChatConversationTest}.kt`: `kotlin.test`, inline `AskResponse` builders, fake `AnswerService`s; no Compose UI-test harness exists, so a pure presentation layer is the only automatable surface.
- `androidApp/.../MainActivity.kt` and `desktopApp/.../main.kt` call `App(landRepository)` with no `answerService`, so the shipped default stays `UnavailableAnswerService`; there is still no `/ask` route and `knowledge/source_catalog.json` is still empty, so no real answer with sources can be produced in the running app (evidence gap, see verification plan).
- `consume`/open capability: `androidx.compose.ui.platform.LocalUriHandler` is a common (Cmn) API in the already-present `compose-ui` dependency and opens the default browser on Android and on Desktop through AWT (`java.awt.Desktop.browse`); on a Desktop/Linux host without BROWSE support `openUri` throws instead of opening (known Upstream issue), which is why the call must be best-effort and never crash the screen. No new dependency is needed in either case.

Sized correctly: one added field on the transcript entry, one pure presentation file, one UI section, one string set, and tests. One user flow, no new data model, persistence, transport, or contract change.

## Implementation plan and tasks

1. Write `CitationPresentationTest` first (conforming mapping, text fidelity, non-conforming degradation, abstention gate, URL guard, date formatting) and implement `CitationPresentation.kt` until it passes.
2. Add `sources` to `ChatMessage`, pass it in `ResponseReceived`, and extend `ChatHomeStateTest`/`ChatConversationTest`.
3. Add the `annotatedText` parameter to `ChatBubble`, the answered branch, `SourceCardsSection`/`SourceCardView`, and the `LocalUriHandler` control with the best-effort `runCatching`.
4. Add the nine strings and the refreshed/new previews.
5. Run the checks below plus the manual link smoke; byte-for-byte compare the nine strings with this spec; run the colour-centralization, logging, and (new) no-raw-marker-in-preview greps.
6. Update `CONSTRAINTS.md`, and append a short note to `docs/specs/response_states.md` recording that R5 is closed from this side for conforming payloads (the accepted response_states behavior itself is unchanged).
7. Update `feature_list.json`/`PROGRESS.md` only after implementation and independent validation, recording only the commands actually run and the F1 evidence gap (the planner must not mark this feature complete).

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.chat.CitationPresentationTest" --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests "com.jamarglex.manijero.ChatConversationTest"
./gradlew :shared:jvmTest
./gradlew :shared:testAndroidHostTest
./gradlew :desktopApp:build
./gradlew :androidApp:assembleDebug
./scripts/init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # matches only under theme/
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
```

`local.properties` exists in this worktree, so the Android steps are expected to run; if the SDK is unavailable, record the exact blocker instead of claiming a result. There is no persistent E2E command and no Compose UI-test harness, so focused pure tests plus preview/manual review are the justified coverage; do not claim E2E or automated UI coverage.

Manual / preview evidence (record what actually happened):

1. **Feature-list verification (link reachability).** Configure a **temporary, non-committed** fake `AnswerService` in a platform entry point that returns the accepted fixture shape with `[1]` markers added to the answer, then open each card's control on the Android emulator and on Desktop and confirm the default browser opens the cited URL (`https://www.mapa.gob.es/` from `contracts/examples/response-answered.json`). Record the exact URL observed and the app/browser state; delete the fake afterwards. Never commit a fake and never hard-code an endpoint.
2. Preview/manual review: answered reply with cards, two cards, and an abstention with none; confirm the reference numeral matches the card number and the excerpt is visible without any disclosure step.
3. `fontScale = 2f` and `widthDp = 320`: no clipping, no horizontal overflow, excerpt and control still readable.
4. Greyscale check: with colour removed, the card is still identifiable by its `Fuente n`/heading text and the reference numeral is still distinguishable by position.
5. Honest limitations to state: the canonical corpus is empty and there is still no `/ask` route (carried F1 from `chat_question_submission`), so no *real* cited document can be produced in the running app — the opened URL is the accepted fixture's official URL; Desktop link opening depends on `java.awt.Desktop` BROWSE support and may fail on a Linux host (reported, not hidden); interactive Desktop click-through may be preview-based in a non-interactive session.

Capture: focused and full test counts/names; the nine strings compared byte-for-byte with this spec; the text-fidelity and non-conforming-degradation assertions; the F1 reproduction case as a test (a non-prefix payload yields no numbered card and unmodified text); the URL-guard and date-format tests; the greps; and `./scripts/init.sh --verify` output (or the exact blocker).

## Validator checklist

- [ ] An answered response appends exactly one assistant entry carrying its own decoded `sources` in payload order; a later turn does not alter an earlier entry's sources and nothing is rendered from `lastResponseStatus`.
- [ ] One card per source shows title, issuing body, location, formatted verification date, and an always-visible (never collapsed, never truncated) excerpt; the reference numeral matching the card number is rendered and no client-authored claim, disclaimer, badge, success colour, or "verificado" wording was added.
- [ ] `Abrir documento oficial` opens exactly the card's URL through `LocalUriHandler`, its accessible description names the source title, it is a separate focusable control, and a non-https/blank/hostless `url` yields the pinned unavailability line with no control and no crash.
- [ ] A conforming reply's text is byte-for-byte identical to the server `answer` after substituting each rendered reference back to its `[n]` token; a non-conforming payload (F1 case: absent/sparse/out-of-range/non-numeric markers) rewrites no marker, numbers no card, and leaves the text exactly as received.
- [ ] An abstention renders no card, reference, figure, date, or link even when a malformed payload carries a `sources` entry, and its pinned message is verbatim; the clarification and failure paths are unchanged.
- [ ] The nine strings match this spec verbatim; no existing string was changed or deleted (including the unused `chat_home_submitted`); the code-owned notice is not duplicated.
- [ ] Cards stay inside the existing content width, the excerpt block uses theme roles only, nothing is clipped at `widthDp = 320`/`fontScale = 2f`, and the citation cue is not colour-only.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, Gradle change, permission, endpoint, engine, or shipped fake; `contracts/`, `backend/`, `knowledge/`, `theme/`, land code, platform roots, and `scripts/init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`; no logging/printing of URLs, excerpts, questions, payloads, or exception text (grep evidence); no URL or question is sent anywhere new.
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, `./scripts/init.sh --verify`, and the contract validator pass (or the exact environment blocker is reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning; the final diff matches this spec's file list; the F1 client-side handling is recorded and the backend F1 hardening plus the `knowledge/README.md` sentence are handed back as follow-ups rather than silently "fixed" here.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/answer_source_cards.md.
- Implemented in shared commonMain: new pure, Compose-free chat/CitationPresentation.kt (AnswerSegment/Reference/SourceCard/AnswerSourcePresentation, answerSourcePresentation, openableOfficialUrl, formatVerificationDate); ChatMessage gains assistant-only sources: List<AnswerSource> copied only in ResponseReceived; App.kt gains ChatBubble.annotatedText, the answered-branch source-card section (numbered Fuente n cards with title/issuing body/location/verification date and an always-visible excerpt in one merged semantics node) and one Abrir documento oficial Button with a source-naming contentDescription via LocalUriHandler; nine pinned Spanish strings; four new/refreshed previews; one CONSTRAINTS.md client MUST rule; a one-line R5-closed note in docs/specs/response_states.md.
- Fail-closed marker/card gate (carried grounded_answer_generation F1 handled from the client side): references and card numbers appear only when the distinct [n] markers are exactly 1..sources.size; a non-conforming payload (absent, sparse, out-of-range, non-numeric, leading-zero) rewrites nothing and numbers no card, so the client can never point at the wrong document. The URL guard accepts only https with a dotted host and refuses http/javascript:/mailto:/blank/hostless. A non-answered status renders no card, reference, figure, or date even with a malformed payload.
- Commands actually run (repository root): python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'; ./gradlew :shared:jvmTest --rerun-tasks -> 129 tests / 0 failures (CitationPresentationTest 23, ChatHomeStateTest 31, ChatConversationTest 9); ./gradlew :shared:testAndroidHostTest --rerun-tasks -> 118 tests / 0 failures; ./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks -> BUILD SUCCESSFUL (debug APK); ./scripts/init.sh --verify -> exit 0; ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; greps: Color(0x only under theme/, no println/Log/Logger/printStackTrace/NSLog; no raw marker in shipped copy; nine strings byte-for-byte vs the spec; git diff --check clean. No test removed (HEAD 104 -> 129).
- Honest gaps: the feature-list link-reachability smoke (open each card's URL on Android/Desktop) was NOT run and would only be reachable through a temporary non-committed fake because the shipped default is UnavailableAnswerService, there is no /ask route, and the corpus is empty; greyscale and widthDp=320/fontScale=2f rendered review are structural/compile-based, not an inspected render (owner chat_accessibility). No E2E or automated UI coverage is claimed. Documented deviation: leading-zero markers ([01]) are treated as non-conforming so the byte-for-byte text-fidelity invariant holds. Backend F1 hardening and the unconditional [n] == sources[n-1] sentence in knowledge/README.md were left untouched (backend-owned) and are handed back as follow-ups; the client is safe either way.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/answer_source_cards.md). It re-ran the contract validator, the focused three-class run, :shared:jvmTest --rerun-tasks (129/0), :shared:testAndroidHostTest --rerun-tasks (118/0), :desktopApp:build :androidApp:assembleDebug --rerun-tasks (72 tasks, exit 0), ./scripts/init.sh --verify (exit 0), :shared:compileKotlinIosSimulatorArm64, and the iosSimulatorArm64 test run (129 tests / 0 failures incl. CitationPresentationTest 23/0 on Kotlin/Native, via a temporary clean-up of two pre-existing comma-in-test-name files that it then reverted); it reproduced byte-for-byte text fidelity, the non-conforming/abstention fail-closed paths, the F1 non-prefix case, the URL/date matrices and per-entry sources with its own 11-test probe, byte-for-byte checked the nine strings (strings.xml numstat 9/0, chat_home_submitted intact), and confirmed no rendering from lastResponseStatus, clean scope (contracts/, backend/, knowledge/, theme/, lands/, platform roots, Gradle, scripts/init.sh untouched), no logging, and no Color(0x) outside theme/. Non-blocking findings N1-N7 recorded; N1 (record harness evidence) closed by this acceptance commit and N7 (backend F1 handoff) escalated.
