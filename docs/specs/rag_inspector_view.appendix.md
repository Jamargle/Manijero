# Appendix: `rag_inspector_view`

Contract: [`rag_inspector_view.md`](rag_inspector_view.md).

## Repository research

- `backend/app/answer_trace.py` — `text_allowed(profile, environ)` (explicit `development` only), `TraceCollector`, the `note_*` hooks, `TraceSession`. The collector exists only when tracing is on today. `note_search_end` receives `RetrievedPassage` candidates, which carry title, location, and excerpt.
- `backend/app/ask_api.py` — closed `AskResponse` (`extra="forbid"`). The route opens the trace session, runs `_answer`, then `session.finish` and retention. This is where `inspection` is attached last.
- `backend/app/main.py` — `create_app` resolves `answer_trace` from `os.environ` and `resolved.profile`, with a test seam. Mirror it for inspection.
- `backend/app/retrieval.py` — `RetrievedPassage` fields; `Retriever` k defaults to 5 (`get_retrieval_k`).
- `backend/app/retention.py` — reads only `status` and `answer` from the response. Attaching inspection after retention keeps it out of retained data.
- `backend/app/local_rag_service.py:319` — `--local-rag-start` states `MANIJERO_DEPLOYMENT_PROFILE=development`. `scripts/init.sh --backend` (line 207) and the container do not, so neither sends inspection.
- `backend/tests/test_answer_trace.py` — `create_app(config, retention_store=None, answer_trace=trace)` pattern; the byte-identical on/off test at line 429 must stay green. Inspection resolves from its own seam, so unset tests stay unaffected.
- `contracts/openapi.yaml` — `AskResponse` is `additionalProperties: false`; `test_privacy_retention.py:613` greps the contract text for the retention block (do not reformat it).
- `shared/.../chat/AnswerService.kt` — `answerJson` has no `ignoreUnknownKeys`, so an undeclared response key fails the whole answer. Hence `inspection` is a raw `JsonElement?` decoded separately and leniently.
- `shared/.../chat/PilotToken.kt` — private `LOOPBACK_HOSTS` and `mayCarryPilotToken`. Expose an `internal fun isLoopbackServiceUrl(url)` reused by both.
- `shared/.../ChatHomeState.kt` — `ChatMessage` single creation site at `ResponseReceived`; constraint "copied, never inferred".
- `shared/.../chat/ChatTranscript.kt` — `ChatMessageBubble` answered/abstained branches; source cards are a sibling of the merged card.
- `shared/.../App.kt`, `AppNavigation.kt` — destination table, `backTarget`, `navigationVisible`, and how `Connection`/`Privacy` detail routes are wired.
- `androidApp/src/{debug,release}/.../TestBuildTools.kt`, `MainActivity.kt`, `desktopApp/.../main.kt` — the `connectionTools != null` branch is the only place the supplier-URL `KtorAnswerService` is built.
- `shared/src/jvmTest/.../platform/TestBuildGatingGuardTest.kt` — the static guard to extend.
- `docs/constraints/{client-chat,hosting-and-pilot,ui-shell}.md` — the rules this feature must keep and extend.
- Not inspected: `ChatHomeScreen.kt` internals beyond signatures, the screenshot support classes, and the `answer_source_cards` spec (only its constraint).

## Implementation plan

1. Backend collector: in `note_search_end`, also keep `{passage_id: (title, location, excerpt)}` in a private collector field. Assert that `build_document` never reads it, and that the trace key sets are unchanged.
2. `answer_inspection.py`: `inspection_allowed`, `INSPECTION_KEYS`, `build_inspection` (rank order, ≤ k, lexical and vector lookups by id, `cited` from the outcome ids, excerpt cap 2000), `InspectionError` with fixed codes.
3. `main.py`: resolve the flag once (`answer_inspection=` seam, default from env) and log `answer_inspection state=on|off` with no other fields.
4. `ask_api.py`: open the collector when trace or inspection is on, and attach `inspection` after retention. Add the optional closed pydantic model and serialize only when set (for example `response_model_exclude_unset=True`). Confirm the existing exact-body tests stay green.
5. `contracts/openapi.yaml`: `AnswerInspection` and its nested closed schemas, with an optional `inspection` property.
6. `backend/tests/test_answer_inspection.py` (named below).
7. Shared: `inspector/AnswerInspection.kt` (serializable model + `decodeInspectionOrNull`), the `AskResponse.inspection: JsonElement? = null` field, the `KtorAnswerService` supplier constructor `acceptInspection`, and `isLoopbackServiceUrl`.
8. `ChatMessage.inspection`, copied in `ResponseReceived` for answered and abstained entries.
9. `ChatTranscript`/`ChatHomeScreen`: an `onInspect: ((ChatMessage) -> Unit)?` callback and an `Inspeccionar` `TextButton` sibling with a test tag.
10. `AppDestination.Inspector` plus the table updates; in `App`, `inspected` state, the route, and `Volver`.
11. `AnswerInspectorScreen` with its sections, Spanish strings in `strings.xml`, and previews.
12. Hosts: pass `acceptInspection = true` in the tools branch only. Extend `TestBuildGatingGuardTest`.
13. Screenshot states and baselines (record, then verify), then the documentation edits listed in the contract.

## Verification plan

Backend, `test_answer_inspection.py`:

- explicit `development` yields `inspection` for answered, abstained, year mismatch, and clarification;
- unset, empty, `pilot`, ` development`, `Development`, and `qa` yield no key at any depth;
- the key set equals `INSPECTION_KEYS`;
- the marker word, land id, municipality, and token bytes are absent;
- passages are ≤ k in rank order; `cited` matches; lexical and vector values are `null` when absent; hybrid fallback code is recorded;
- the other five keys are byte-identical with inspection on and off;
- a builder failure omits the key, keeps the status, and logs a fixed code;
- trace on/off does not affect inspection, and trace files keep `METADATA_KEYS` with inspection on;
- retained records never contain inspection;
- the `503` path is unchanged.

Client:

- decode tests: valid payload, unknown key, wrong type, oversize excerpt, too many passages, and `null`, each → model or `null`, never a throw;
- `KtorAnswerServiceTest`: kept for `http://127.0.0.1` and `http://10.0.2.2` with acceptance; dropped for the fixed-URL constructor, `https://qa.example.invalid`, the LAN IP, and acceptance off; the answer is otherwise equal;
- `ChatHomeStateTest`: the entry copies its own inspection;
- `ChatHomeInteractionTest`: the link appears only on answered and abstained entries with an inspection; it is not inside the merged node; tapping it yields that entry;
- `AppNavigationTest`: tab, back target, and bars;
- `AnswerInspectorScreenTest`: sections, `null` stages shown as `No se ejecutó`, codes verbatim, `Volver`;
- `TestBuildGatingGuardTest`: the fixed-URL constructor has no inspection parameter, and only the tools branch of `MainActivity`/`main.kt` passes `acceptInspection = true`.

Screenshots: answered with link, abstained with link, and inspector (default and compact 2×). Existing baselines must stay unchanged.

E2E: `--local-smoke` is not extended, because inspection needs a stated `development` service and unit, interaction, and screenshot coverage pins the gating. Record this justification in the evidence.

## Evidence to capture

- The focused block result lines, plus one `CI=true ./scripts/init.sh --fast` result line.
- The `INSPECTION_KEYS` list, by name only.
- The new screenshot baseline file names; a statement that no existing baseline changed.
- Not run (with reason): GUI walkthrough and device run.

## Notes for later features

- `client_environment_builds` must keep `acceptInspection` false for any QA build, or rely on the loopback rule; it must never add QA hosts to the loopback set.
- `environment_profiles`/QA must never add a profile to `LOCAL_PROFILES`; inspection follows that set automatically.
- `rag_demo_rehearsal` needs `--local-rag-start` (stated `development`) to show the inspector.

## Feature evidence

- `./scripts/init.sh --feature rag_inspector_view`: passed (backend 141 passed; jvmTest inspector/chat/platform/mock/AppNavigation/ChatHomeState/ChatConversation green; android debug+release and desktop compile; desktop and Android screenshot verify green).
- `CI=true ./scripts/init.sh --fast`: 1854 backend passed, 4 skipped; gradle-jvm-test, harness (13), contract examples and offline evaluators ok.
- `CI=true ./scripts/init.sh --verify`: Full tier passed (Android host tests and Android/Desktop builds).
- `INSPECTION_KEYS` (names only, in `backend/app/answer_inspection.py`): schema, total_ms, retrieval{mode,k,search_calls,duration_ms,vector{used,fallback_code},passages[]{rank,passage_id,source_id,title,location,score,lexical_rank,lexical_score,vector_similarity,cited,excerpt}}, drafting{provider,outcome,status,cited_markers,duration_ms}, verification{ok,issues,claims[]{index,markers,ok,issues},duration_ms}, outcome{abstention_reason,generation_reason,cited_passage_ids}.
- New screenshot baselines (recorded only these, no existing baseline changed): jvmTest `chat_answered_inspect_link_light`, `chat_abstention_inspect_link_dark`, `inspector_answered_light`, `inspector_phone_large_text_dark`; androidHostTest `chat_answered_inspect_link_light`, `chat_abstention_inspect_link_dark`, `inspector_large_text_dark`.
- Existing test adjusted: `test_ask_endpoint.py` openapi check now expects optional `inspection` with `required` unchanged.
- Client detail: `AskResponse` keeps raw `inspection` (`rawInspection`, wire name `inspection`) plus transient decoded `inspection`; `KtorAnswerService` decodes only when `acceptInspection` and a loopback address. Hosts pass `acceptInspection = true, pilotToken = pilotToken` (named, so `PilotTokenGuardTest` still sees `pilotToken` last).
- `--local-smoke` not extended: inspection needs a stated `development` service, and unit, interaction and screenshot tests pin the gating.
- Not run: GUI walkthrough and device run (no owner walkthrough, decision 3).
- Validator 2026-11-02: accept (reran `--feature` and `--fast`, both passed; no existing PNG changed). Final by owner decision 3; see [acceptance](../validations/rag_inspector_view.md).

## Validator checklist

- [ ] Inspection is present only for an explicitly stated `development` profile (via `text_allowed`). It is absent for unset, `pilot`, and every other value.
- [ ] The key set equals the published allowlist; no question, answer, or draft text, land data, token, client id, or issue `detail`.
- [ ] The other response keys are unchanged, the `503` path is unchanged, a builder failure never fails a request, and trace files and retention are unaffected.
- [ ] The contract declares an optional, closed `AnswerInspection`; `required` is unchanged.
- [ ] The client keeps inspection only with `acceptInspection` and a loopback URL. A malformed inspection never fails the answer, and the fixed-URL constructor cannot accept it.
- [ ] The link appears only on answered and abstained entries with an inspection, as its own focusable node. The screen has a single heading, no certainty treatment, `Volver`/back/tab return the chat intact.
- [ ] The release and packaged paths are unchanged; the guard test is extended; existing screenshot baselines are unchanged and the new ones are recorded.
- [ ] Nothing is persisted or logged on the client; no new dependency; no `client_environment_builds` scope.
- [ ] Documentation is updated per the contract; the focused block passes as published; there is no owner walkthrough (decision 3).
