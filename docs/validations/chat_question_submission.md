# Validation — chat_question_submission

## Verdict

**Accept** — independently reviewed against `docs/specs/chat_question_submission.md`.

- Feature: `chat_question_submission` (worktree `feature/chat_question_submission`, uncommitted diff).
- Claimed status: `passing` (implementer self-verification) — validated here, not accepted on trust.
- Reviewer evidence: source/diff inspection, re-run Gradle and contract checks, plus probes written
  outside the repository. No product code or `feature_list.json` status was modified.

## Independent checks rerun (all from this worktree, 2026-10-12)

| Check | Result |
| --- | --- |
| `python3 contracts/validate_examples.py` | Passed — "Validated 2 request and 3 response examples against answer_api_contract" |
| `./gradlew :shared:jvmTest --rerun` | BUILD SUCCESSFUL — 24 tests, 0 failures (`KtorAnswerServiceTest` 2, `ChatConversationTest` 3, `ChatHomeStateTest` 13, `LandRepositoryTest` 4, 2 scaffold) |
| `./gradlew :shared:testAndroidHostTest --rerun` | BUILD SUCCESSFUL — 22 tests, 0 failures (includes `ChatConversationTest`/`ChatHomeStateTest`) |
| `./gradlew :desktopApp:build` | BUILD SUCCESSFUL |
| `./gradlew :androidApp:assembleDebug` | BUILD SUCCESSFUL; `androidApp/build/outputs/apk/debug/androidApp-debug.apk` produced |
| `./gradlew :androidApp:assembleDebug :desktopApp:build --rerun-tasks` | BUILD SUCCESSFUL — full independent recompilation of shared + both apps (APK rebuilt) |
| `./scripts/init.sh --verify` | BUILD SUCCESSFUL (runs `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build`) |
| `./gradlew :shared:compileKotlinIosSimulatorArm64` | BUILD SUCCESSFUL — the new `commonMain` Ktor/serialization dependencies do not break the pre-existing iOS target |
| `./gradlew :desktopApp:run` (50 s, then killed) | Desktop window opened; no exception, error, or warning in the run log |
| `git diff --check` | Clean |

`local.properties` with `sdk.dir=/Users/jose/Library/Android/sdk` exists, so no Android check is
environment-blocked in this worktree; the implementer's "no remaining blocker" claim is accurate.

### Probes beyond the implementer's suite

- Decoded every contract fixture with the shipped `AskResponse` DTO and `answerJson` from a throwaway
  JVM program kept outside the repo (`/tmp/mnjr-validation/scratch/Scratch.java`):
  `answered` (answer 174 chars, 1 source, `general`, no ids), `abstained` (145 chars, 0 sources,
  `all_active`), `needs_land_clarification` (empty answer, `selected`, ids `[land-001, land-002]`) all
  decode. The implementer's MockEngine test only covers the `answered` fixture, so statuses 2 and 3
  were previously unproven at the transport level.
- Encoded `generalAskRequest("  ¿Puedo regar hoy?  ")` from the same program:
  `{"question":"  ¿Puedo regar hoy?  ","land_context":{"mode":"general","lands":[]}}` — exact wording,
  exactly the contract keys, no `null`s, no land data.
- `grep` for logging APIs (`println`, `Log.`, `Logger`, `printStackTrace`, `System.out`, `NSLog`) across
  `shared/src`, `androidApp/src`, `desktopApp/src`: no matches; no Ktor `Logging` plugin is installed.
- `grep` for `http(s)://`, `localhost`, `127.0.0.1`, `/health`: only the reserved
  `https://api.example.invalid/` host in `KtorAnswerServiceTest`. No production endpoint is hard-coded
  and `/health` is never used as answer readiness.
- `git status`/`git diff --stat`: changes limited to `App.kt`, `ChatHomeState.kt`, new
  `ChatConversation.kt`, new `chat/AnswerService.kt`, tests, `strings.xml`, the two Gradle files, and
  the workflow docs (`PROGRESS.md`, `feature_list.json`). `contracts/` and `backend/` are untouched; no
  other feature entry in `feature_list.json` changed; no retry/suggestion/source-card/land-selection UI
  was added.

## Acceptance scenarios

1. **Submit one general question — pass.** `AskClicked` captures the composer value before clearing it,
   appends a USER message with the untouched text (no trim/rewrite anywhere), and emits
   `ChatEffect.Submit` whose request is `general` with `lands: []`. `canAsk` is false while
   `phase == SUBMITTING`, so a second `AskClicked` yields no effect; `ChatConversationTest` proves exactly
   one transport call for two clicks, and the UI additionally disables **Preguntar**.
2. **Visible working state and one reply — pass at the presentation/state level.** A single
   `ChatNoticeBubble("Estoy preparando la respuesta…")` with `liveRegion = Polite` renders only while
   submitting, the button is disabled, and the question bubble stays in the transcript. `ResponseReceived`
   is accepted only from `SUBMITTING`, is a no-op otherwise, and appends at most one assistant message
   (empty `answer` appends none), returning to idle so a later question can be submitted.
3. **Invalid input remains unsent — pass.** Blank/whitespace and >2,000-character input produce no effect
   and no message (reducer tests at 2,000 and 2,001 characters); the composer shows
   `chat_home_question_too_long` ("…El máximo son 2.000 caracteres. No cambiaré tus palabras…") instead of
   silently rewriting or truncating the text.
4. **Other contract states retained without false certainty — pass.** `abstained` keeps its status and its
   plain answer is appended once with no source card, citation, or "verified" styling. For
   `needs_land_clarification` the status and opaque `land_ids_to_choose` are kept in state, no assistant
   message is fabricated, and one neutral bubble says "Todavía no puedo responder: necesito saber a qué
   terreno te refieres. Poder elegir el terreno llegará más adelante." — no invented land choice, no legal
   conclusion, no claim that the question was answered.

## Validator checklist

- [x] Shared UI/business behavior in `commonMain`; platform source sets unchanged (there is no platform
      engine wiring at all — see finding F1).
- [x] Blank and over-2,000-character questions make no request or message; accepted input keeps exact
      wording (including leading/trailing spaces) in the user message and in `AskRequest.question`.
- [x] One active submission → one user message, one visible working state, at most one assistant message;
      duplicate in-flight submit is impossible in both reducer and UI.
- [x] Request is contract-valid `POST /ask` with `{"mode":"general","lands":[]}`; no land names, notes,
      area, municipality values, or parcel data are sent.
- [x] Returned statuses decoded without invented sources/land labels/legal conclusions; no document,
      status, or comment claims response-state presentation is complete.
- [x] Spanish copy, semantic labels (text "Tú"/"Asistente", merged bubble nodes, polite live region),
      `sp`-based Material typography and scrollable transcript reviewed in source. Small-window/wide-window
      rendering and Desktop keyboard focus were **not** exercised (finding F3).
- [x] MockEngine/reducer tests and all feasible Gradle checks pass; no environmental blocker in this
      worktree.
- [x] No backend, contract, unrelated-feature, or planning-status change; `feature_list.json` records only
      this feature and does not claim `accepted`.

## Findings (all non-blocking)

**F1 — Medium, evidence gap: the contract client is not reachable from any runnable app.**
`KtorAnswerService`/`answerHttpClient(engine)` are only constructed by the JVM `MockEngine` test; no
platform source set adds a Ktor engine dependency (OkHttp/CIO/Darwin) and `App()` defaults to
`UnavailableAnswerService`, which always throws. Entry points (`MainActivity`, `desktopApp/main.kt`,
`MainViewController`) call `App()` with no argument, so a person cannot complete a conversation in the
running app, and the spec's optional manual-smoke record ("identify the mock/local responder used") could
not be produced. Why it does not block: the spec explicitly conditions that manual smoke on a local `/ask`
existing ("Once a local `/ask` implementation is available"), the backend still exposes only `/health`,
the spec blesses not fabricating an answer, and the Desktop app was independently launched without
exceptions. `chat_home` (accepted) set the same precedent for deferring an Android/Desktop smoke check.
Follow-up (owner: the slice that implements/wires `/ask`, i.e. `response_states`/`network_error_recovery`
or the backend API feature): add the engine dependency in the platform source sets, pass an explicit
non-secret development base URL through build configuration into `KtorAnswerService`, and record an
Android/Desktop manual smoke that shows exact wording, one working state, one reply, a disabled duplicate
submit, and a second question.

**F2 — Low, latent robustness: no request timeout on the transport.**
`answerHttpClient` installs only `ContentNegotiation`. A stalled server (or, on Android, an unreachable
host that never RSTs) can leave the UI in `SUBMITTING` indefinitely, which brushes against the spec's
"the flow cannot remain indefinitely submitting". The reducer's `RequestFailed` transition and the
recovery-to-idle path exist and are tested, and failure copy/retry belongs to
`network_error_recovery`. Suggested follow-up: install Ktor `HttpTimeout` (bounded request timeout) when
the engine is wired, mapping the timeout to `ChatHomeAction.RequestFailed`.

**F3 — Low, unperformed visual/accessibility verification.**
No small-Android-window or wide-Desktop-window check, screenshot, or text-scaling check was recorded,
although the spec's visual section asks for them. Structurally the transcript plus composer live in one
`verticalScroll` column with no auto-scroll to the newest entry, so after a long answer the freshly
appended user message or the working indication can sit below the fold until the person scrolls. Nothing
is clipped and no acceptance scenario fails (the editor clears on submit, so the first exchange fits).
Suggested follow-up, ideally inside `chat_accessibility`: auto-scroll to the newest transcript entry
and/or pin the composer, then capture small-window and wide-window evidence.

**F4 — Informational.**
`kotlinx-coroutines-test` is correctly in `commonTest`, but `ktor-client-mock` is declared in
`commonTest` while its only consumer is `shared/src/jvmTest`; narrowing it to `jvmTest` is tidier (no
behavioural impact). `ChatHomeState`/`ChatHomeAction` keep the `ChatHome` prefix while now modelling a
conversation; renaming is optional. `Modifier.fillMaxWidth().widthIn(max = 720.dp)` is unchanged from the
accepted `chat_home` screen; whether the 720 dp maximum readable width is actually enforced on wide
Desktop windows was not verified here (neither feature captured a screenshot) and is out of this
feature's introduced scope. The `chat_home` criterion "typed text is retained on submit" is superseded by
design — the wording is retained as the conversation message and restored to the composer on failure — so
no user input is lost.

## Security and privacy assessment

Feature-scoped review; no blocking findings.

- No secrets, credentials, tokens, telemetry, or analytics were added; no authentication exists in this
  contract.
- No production endpoint, `localhost`, or `127.0.0.1` assumption is hard-coded; the only URL is the
  reserved `.invalid` test host. `/health` is never used as answer readiness.
- Land minimisation holds: `land_context` is always `general` with an empty `lands` array, and the DTOs
  carry no names, notes, area, or parcel identifiers (`MinimalLandContext` exposes only municipality,
  water regime, and production method, and is unused today).
- No raw question, land content, or endpoint payload is logged or printed anywhere in app or platform
  code, and no HTTP logging plugin is installed; the failure path rethrows `CancellationException` and
  swallows other exceptions without echoing content.
- Decoding strictness is acceptable: unknown/missing contract fields fail into `RequestFailed` rather than
  fabricating content.

## Documentation and harness assessment

- `docs/specs/chat_question_submission.md` is the contract used, and it was respected: the obsolete
  "lista para continuar" string was removed, `contracts/openapi.yaml` was not revised, and no backend
  source was touched.
- The spec's `Durable Documentation Impact` was honoured: no new architecture or constraint documents
  were created, `AGENTS.md`/`CONTEXT.md`/`DESIGN.md`/`docs/archive/MasterPlanV3.md` are untouched, and `PROGRESS.md`
  plus the `feature_list.json` evidence were updated after implementation with claims I could reproduce
  (test counts 24/22, contract validator output, Android/Desktop builds, Desktop launch, no-logging grep).
- No overclaim was found: `feature_list.json` still says `passing`, "ready for independent validation",
  and explicitly lists what remains deferred (response states, source cards, land selection, retry,
  suggested prompts, backend `/ask`).

## Recommended state update

Record this validation, then set `chat_question_submission` to `accepted` in `feature_list.json`
(orchestrator action; not performed by the validator). Carry F1–F3 forward as follow-ups for the
`/ask` wiring and `chat_accessibility` slices.
