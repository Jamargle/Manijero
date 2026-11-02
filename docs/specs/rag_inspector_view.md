# Feature Spec: `rag_inspector_view`

## Source metadata

- **Feature:** `rag_inspector_view` — Show retrieved passages, scores, and verification steps for an answer in a developer view (`client`).
- **Status at planning:** `not_started`; depends on accepted `answer_pipeline_trace`, `local_service_connection`, `answer_source_cards`. Consumer: `rag_demo_rehearsal`.
- **Source behavior:** the feature-list title plus the owner decisions below. No earlier spec or discovery record defines more.
- **Feature-list verification:** none recorded; this spec's focused block is the verification.
- **Feature-list notes (owner decisions 2026-11-02, binding):**
  1. **Client:** the inspector is shown only in local builds, through an `Inspeccionar` link under each answer. QA and prod builds never show it.
  2. **Backend:** the inspector data (retrieved passages, scores, verification steps) is sent only when the profile is explicitly `development`. This is the same rule as the `answer_pipeline_trace` text (`text_allowed`, commit "fix: record trace text only for an explicitly stated local profile"). It is never sent in QA or prod, and never when the profile is unset or unknown.
  3. **Approval:** the independent validator's accept is final, with no owner walkthrough. The owner reviews it in the batch PR.
- **"Local build" (planner definition, fail closed):** `client_environment_builds` is not accepted and is out of scope. A local build is therefore defined from existing code. The host injects the test-build `Conexión` tools (Android debug and Desktop `run` only, guarded by `TestBuildGatingGuardTest`), **and** the address used for that question is a loopback host (`LOOPBACK_HOSTS` in `chat/PilotToken.kt`: `localhost`, `127.0.0.1`, `::1`, `10.0.2.2`). A future QA build targets a remote `https` host, so it never qualifies, even when it carries test tools. Release and packaged builds never have the tools.

## Goal and boundaries

A developer running the local service asks a question in a local test build. Under the answer, they tap `Inspeccionar` and see what retrieval found, how each passage scored, what the drafter did, and why verification accepted or rejected the draft. Only fixed codes and public corpus text are sent. The inspection never changes an answer, never fails one, and never leaves the explicit `development` profile.

**In scope**

- An optional `inspection` object on the `/ask` 200 response (`answer-inspection-v1`). The backend builds it from the existing trace collector, and it is present only when `text_allowed(profile, environ)` is true.
- The client decodes it leniently, keeps it only under the local-build rule above, and stores it on that assistant entry.
- An `Inspeccionar` link under answered and abstained entries that carry one. It opens a read-only `Inspección de la respuesta` detail route with `Volver`.

**Non-goals**

- `client_environment_builds` scope: no build flavors, environment flag, or QA/prod build logic.
- The mock answer service, the trace file format (`METADATA_KEYS` unchanged), `MANIJERO_ANSWER_TRACE` semantics, `--backend`, or the container. None of these states the profile, so none sends inspection.
- Any change to retrieval, ranking, drafting, verification, answer text, sources, or land handling.
- Persisting, exporting, copying, logging, or sharing inspection data. It lives in memory with the transcript.
- Question, answer, or draft text, land ids, land attributes, `land_scope`, client ids, tokens, or `GroundingIssue.detail` inside `inspection`.

## Job story

When a local answer looks wrong or a trap question abstains, I want to open the passages, scores, and verification codes behind that exact answer in the app I asked from. Then I can explain or fix the cause without reading server files, and none of this ever reaches a farmer's build or a shared server.

## Acceptance scenarios

### Backend sends inspection only for an explicit `development` profile

Given `MANIJERO_DEPLOYMENT_PROFILE=development` is stated, when `/ask` returns `answered`, `abstained` (including the year mismatch), or `needs_land_clarification`, then the body carries `inspection`. Given the profile is unset, empty, `pilot`, ` development`, `Development`, or any other value, the body has no `inspection` key at any depth. The other five keys are byte-identical to the same request without inspection. The `503` path is unchanged. Tracing on or off changes nothing about `inspection`.

### Inspection content is bounded and privacy-safe

Given an inspected response, `inspection` holds the following fields. A stage that did not run is `null`.

- `schema` set to `answer-inspection-v1`.
- `retrieval`: `mode` (`bm25`|`hybrid`), `k`, `search_calls`, `duration_ms`, and `vector` (`used`, `fallback_code`) or `null`. It also has `passages`: one per final candidate, at most `k`, in rank order, with `rank`, `passage_id`, `source_id`, `title`, `location`, `score`, `lexical_rank`/`lexical_score` (or `null`), `vector_similarity` (or `null`), `cited` (whether the passage is in the answer's cited ids), and `excerpt` (≤ 2000 characters).
- `drafting`: `provider`, `outcome`, `status`, `cited_markers`, `duration_ms`.
- `verification`: `ok`, `issues`, `claims[]` (`index`, `markers`, `ok`, `issues`), `duration_ms`. Only codes are included.
- `outcome`: `abstention_reason`, `generation_reason`, `cited_passage_ids`.
- `total_ms`.

Its key set equals a published allowlist constant. A unique marker word in the question, a land id, a municipality, and the bearer token appear nowhere in it. The written trace file's keys still equal `METADATA_KEYS` or the local text keys, unchanged.

### Contract

`contracts/openapi.yaml` declares `inspection` as an optional, closed (`additionalProperties: false`) `AnswerInspection` schema on `AskResponse`. The schema is described as development-profile-only and never sent by QA or prod. `required` stays the existing five keys.

### Client keeps inspection only in a local build

Given a host built the answer service with test-build tools (`acceptInspection = true`) and the question went to a loopback address, when the response carries `inspection`, then the assistant entry keeps it. In each of these cases the entry has none and the answer itself is unchanged:

- the fixed-URL (release/packaged) service;
- a test build pointed at a non-loopback host (`https://qa.example.invalid`, `http://192.168.1.10:8000`);
- an absent `inspection`;
- an `inspection` that fails to decode (unknown key, wrong type, oversize).

A malformed `inspection` never turns an answer into a failure.

### `Inspeccionar` link and inspector screen

Given an answered or abstained entry with an inspection, then one `Inspeccionar` text button sits below it, after any source cards. The button is its own focusable node, outside the entry's merged node and live region. It never appears for entries without an inspection, for `Tú` entries, or for the failure notice or chooser. Tapping it opens `Inspección de la respuesta` for exactly that entry. The screen shows:

- one `heading()` title and a one-line note that this view is for local testing only;
- the sections `Búsqueda`, `Pasajes encontrados` (one outlined card per passage with position, title, location, `passage_id`, scores, `Citado`/`No citado`, and the excerpt), `Redacción`, `Comprobación` (overall and per claim, codes verbatim), and `Resultado`;
- `Volver`.

`Volver`, Android system back, and the `Asistente` tab return to the chat with its transcript and composer intact. The screen adds no success colour or check (state is text, e.g. `Comprobación superada: sí`), and it works with 2× text, keyboard, and a screen reader.

### Release builds and existing surfaces are unchanged

Given a release, packaged, or mock-backed run, there is no link, no route content, and no visual change. All existing chat screenshot baselines pass unchanged. `TestBuildGatingGuardTest` (extended) proves that the fixed-URL `KtorAnswerService` constructor cannot accept inspection and that only the test-tools branch of each host passes `acceptInspection = true`.

### Acceptance by the validator

Given the focused verification passes and the validator accepts, then the feature is accepted with no owner walkthrough (decision 3).

## Technical approach

1. **Backend** — new `backend/app/answer_inspection.py` (stdlib):
   - `inspection_allowed(profile, environ)` delegates to `answer_trace.text_allowed`, so there is one rule.
   - `INSPECTION_KEYS` allowlist and `build_inspection(collector, passages_by_id)`.
   - The collector records candidate `title`/`location`/`excerpt` in a private field that the trace builder ignores.
   - `create_app` resolves the flag once (test seam `answer_inspection=`), logs `answer_inspection state=on|off`, and stores it on `app.state`. The ask route opens a collector when tracing **or** inspection is on.
   - After the trace and retention steps, the route adds `inspection` to the returned dict. A builder failure omits the key and logs `answer_inspection_skipped reason=<code>`.
   - `AskResponse` gains the optional closed model, and the key is serialized only when set.
2. **Client** — the `AskResponse.inspection` raw `JsonElement?` is decoded by `decodeInspectionOrNull` (lenient `Json`, bounds checked, never throws).
   - `KtorAnswerService`'s supplier constructor gains `acceptInspection: Boolean = false` and keeps the result only when it is true **and** the resolved URL is http(s) to a loopback host. The fixed-URL constructor has no such parameter.
   - `ChatMessage.inspection` is copied at `ResponseReceived`.
   - New `inspector/` package: `AnswerInspection` model, `AnswerInspectorScreen`.
   - `AppDestination.Inspector` (tab `Assistant`, back → `Chat`, bars visible); `App` keeps the inspected entry.
3. **Hosts** — `MainActivity` and Desktop `main.kt` pass `acceptInspection = true` only in their existing `connectionTools != null` branch.

## Expected file changes

- Backend: new `backend/app/answer_inspection.py` and `backend/tests/test_answer_inspection.py`; `backend/app/answer_trace.py` (private candidate details), `backend/app/ask_api.py`, `backend/app/main.py`.
- Contract: `contracts/openapi.yaml`.
- Shared: `chat/AnswerService.kt`, `ChatHomeState.kt`, `chat/ChatTranscript.kt`, `chat/ChatHomeScreen.kt` (callback), `App.kt`, `AppNavigation.kt`, new `inspector/AnswerInspection.kt` and `inspector/AnswerInspectorScreen.kt`, `composeResources/values/strings.xml`, `chat/ChatPreviews.kt`.
- Hosts: `androidApp/.../MainActivity.kt`, `desktopApp/.../main.kt`.
- Tests: `KtorAnswerServiceTest`, `ChatHomeStateTest`, `ChatConversationTest`, `ChatHomeInteractionTest`, `AppNavigationTest`, `TestBuildGatingGuardTest`, new `inspector/AnswerInspectionDecodeTest` and `inspector/AnswerInspectorScreenTest`, plus new states in `ChatHomeScreenshotsTest`/`ChatHomeAndroidScreenshotsTest` with recorded baselines.

## Visual design impact

There is one new text link and one new detail screen built from existing components (`ManijeroScreen`, `ManijeroCard` outlined, `ManijeroSectionHeader`, `TextButton`). It uses no new colours or icons and no confident or success treatment. The answered and abstained cards themselves are unchanged. New baselines cover: an answered entry with the link, an abstained entry with the link, and the inspector screen (compact 2× text included).

## Durable documentation impact

- `contracts/openapi.yaml`: update (optional `inspection`).
- `docs/constraints/hosting-and-pilot.md`: update. Add one MUST: `inspection` is sent only when `text_allowed` holds, uses the published allowlist only, and is never sent in pilot, QA, or prod. Reason: decision 2.
- `docs/constraints/client-chat.md`: update. Add one MUST under a new "Answer inspector" section: the link and screen exist only for an entry whose inspection was kept under the local-build rule, they are never persisted or logged, and the screen has no certainty treatment. Reason: decision 1.
- `docs/constraints/ui-shell.md`: update the test-build tools bullet to name the inspector and the extended guard.
- `DESIGN.md`: update. Add one bullet under "Assistant surface" for the link and the inspector screen.
- `ARCHITECTURE.md`: update. Add one sentence next to the trace sentence.
- `backend/README.md`: update, 15 lines or fewer. Explain where inspection appears, and that `--local-rag-start` states `development` while `--backend` needs `MANIJERO_DEPLOYMENT_PROFILE=development`.
- `docs/pilot-privacy.md`: update. Add one row: development-only response data, not stored.
- `PROGRESS.md` and `docs/progress/known-limitations.md`: one line each at acceptance (a real device on a LAN address never shows the inspector; no GUI run).
- `AGENTS.md`, `CONTEXT.md`, `docs/owner-guide.md`: not needed, because nothing changes in workflow, domain terms, or owner steps.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_answer_inspection.py tests/test_answer_trace.py tests/test_ask_endpoint.py tests/test_privacy_retention.py -q
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.inspector.*' --tests 'com.jamarglex.manijero.chat.*' --tests 'com.jamarglex.manijero.platform.*' --tests 'com.jamarglex.manijero.mock.*' --tests AppNavigationTest --tests ChatHomeStateTest --tests ChatConversationTest
./gradlew --quiet :androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:compileKotlin
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeScreenshotsTest'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeAndroidScreenshotsTest'
```
<!-- verify:end -->

No owner walkthrough (decision 3). The implementer also runs `CI=true ./scripts/init.sh --fast` once as evidence.

## Appendix

See [`rag_inspector_view.appendix.md`](rag_inspector_view.appendix.md) for repository research, tasks, verification plan, feature evidence, and validator checklist.
