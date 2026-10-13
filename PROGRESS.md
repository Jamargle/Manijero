# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` now renders the shared Spanish chat flow: ordered transcript, composer, a plain-Spanish working state, a Spanish explanation of the 2,000-character contract limit, a neutral acknowledgement while a land clarification is pending, the three approved example questions that fill the composer, and a `Chat`/`AddLand` destination that saves a land and confirms it in plain Spanish.
- The chat boundary is a shared contract client: pure `ChatHomeState` reducer plus `ChatConversation` (composition-scoped effect runner) over an injected `AnswerService`; `KtorAnswerService` talks to `<baseUrl>/ask` and the default app wiring is `UnavailableAnswerService` because the backend exposes no `/ask` yet. Retrieval, answer/source presentation, and failure-recovery copy remain deferred.
- Shared tests include reducer coverage for the chat flow and suggested-question selection, presentation coverage for one reply per submission, and a Ktor MockEngine transport test that decodes the accepted contract fixture.
- The backend now has a minimal FastAPI service with a documented liveness endpoint; it still has no `/ask` route.
- The knowledge boundary now exists: `knowledge/source_catalog.json` is a valid versioned (`source-catalog-v1`) catalog that is intentionally empty, and `backend/scripts/validate_source_catalog.py` rejects any entry whose provenance, metadata, review, or lifecycle state does not conform to policy. No document has been reviewed or added.
- The offline retrieval boundary now exists: `knowledge/passages.schema.json` (`passage-set-v1`), `backend/app/retrieval.py` (strict passage-set validator, Spanish tokenizer, deterministic BM25 `Retriever`/`RetrievedPassage`), and `backend/scripts/evaluate_retrieval.py` (report-only baseline CLI). It re-validates the accepted catalog, fails closed on an ineligible catalog, and searches only synthetic reviewed fixture passages, because no canonical `passages.json` exists yet. Measured fixture baseline: `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`.
- `add_land` is accepted: shared `AddLandState`/`AddLandScreen`, resource-backed Spanish copy, and Android/Desktop composition roots wired to the accepted storage adapters. Android and Desktop checks ran in this worktree because `init.sh` created `local.properties` with the installed SDK; independent validation recorded in `docs/validations/add_land.md`.
- The Desktop app stores lands in `~/.manijero/lands-v1.txt`; Android uses the `manijero_lands` SharedPreferences file. Both go through the shared versioned `land-store-v1` format.
- The offline grounded-generation boundary now exists: `backend/app/generation.py` (code-owned citation markers and notice, `verify_draft` grounding rules, deterministic extractive generator, fail-closed `NotAnswered` reasons, accepted-`AskResponse` assembly) and `backend/scripts/evaluate_generation.py` (report-only CLI, grounding invariants enforced with exit `1`). It answers only from `Retriever` candidates, keeps `/health` as the only route, and configures no model provider. Fixture report: 5 answers, 8 claims, 0 ungrounded claims, 1 no-evidence outcome. `CONSTRAINTS.md` records the answer-grounding MUST rules.
- `visual_foundation` (the shared olive-toned theme in `commonMain`) is accepted: `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/ManijeroColors.kt`, `ManijeroTheme.kt`, and `ManijeroTypography.kt` define the `DESIGN.md` tokens, a fully specified `lightColorScheme`, a `LocalManijeroSemanticColors` local for caution/strong olive, and the `bodySmall` line-height override; `ManijeroTheme` is applied once inside `App()` and all fifteen existing previews use it (record: `docs/validations/visual_foundation.md`). `response_states`, `answer_source_cards`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, and `chat_accessibility` now have their `visual_foundation` dependency satisfied.
- `land_list` is accepted: `Mis terrenos` now opens the shared lands **list** (the parent surface of the add form) via pure `LandListState`/`LandListAction`/`reduce` and the stateless `LandListScreen`, with a single synchronous `LandRepository.list()` read on entry/retry/after-save, an empty state that names `Añadir terreno`, a distinct plain-Spanish failure state (`Reintentar`, no add action), non-clickable merged-semantics rows, and a device-scoped saved confirmation. The intended routing change moves the `add_land` return destination to the list and removes the now-unreachable chat-home confirmation (record: `docs/validations/land_list.md`). `edit_land`, `remove_land`, and `minimal_land_context` now have their `land_list` dependency satisfied.
- `edit_land` is accepted (record: `docs/validations/edit_land.md`): every `Mis terrenos` row gained a visible `Editar` control, pure `EditLandState`/`EditLandScreen` render the prefilled short form, and `App()` performs exactly one `LandRepository.update(id, draft)` on an explicit `Guardar cambios`, carrying `areaHectares`/`notes` through untouched and never reporting a `null`/thrown result as saved. Independent validation reproduced the byte-level one-record update (the untouched record's serialized line is unchanged) plus the preserved-attribute, cleared-municipality, un-known, blank-name, and `LAND_MISSING` no-write semantics. `land_form_accessibility` now has its `edit_land` dependency satisfied.
- The offline abstention boundary now exists: `backend/app/abstention.py` turns every "no safe answer" outcome into one deterministic, code-owned `Abstention` with a stable reason (`invalid_question`, `no_evidence`, `insufficient_evidence`, `stale_evidence`, `conflicting_evidence`, `false_premise`, `unsafe_request`, `generator_abstained`, `generation_error`) and one pinned plain-Spanish message per reason (`ABSTENTION_MESSAGES`; no digit, no date, always a next step). It adds the pre-checks the accepted generation feature deferred — an instrument/article presupposition no retrieved candidate contains, two `critical` candidates disagreeing about the same documented unit, and a catalog that declares sources but has none eligible as of `--as-of` — and `backend/scripts/evaluate_abstention.py` reports the assembled decision per question with the abstention invariants enforced (exit `1`). Every payload is exactly the accepted `AskResponse` keys with `status: abstained`, `sources: []`, and `land_ids_to_choose: []`; the sub-reason stays Python-level, `/health` remains the only route, and no model provider is configured. Detection is lexical and conservative, and no score threshold is a release gate.
- `network_error_recovery` is accepted: the chat failure path is now visible and recoverable in shared `commonMain`. `ChatHomeState` keeps `failure: RequestFailure?`/`failedQuestion` **outside** `messages`, `RequestFailed(failure)` and the new `RetryClicked` re-send the exact original wording with no second user message, and `ChatFailureNotice` shows the two plain-Spanish notices with a danger-styled `Reintentar` as a polite live region. `KtorAnswerService` translates Ktor failures into the payload-free `AnswerServiceUnavailableException`/`AnswerServiceErrorException`, and `answerHttpClient` installs a bounded `HttpTimeout` plus `expectSuccess = true`, closing carried finding F2 from `chat_question_submission` (F1, the platform `/ask` wiring, stays with its own slice). `CONSTRAINTS.md` records the client MUST rule. Independent validation accepted 2026-10-13 (record: `docs/validations/network_error_recovery.md`); F1 (platform `/ask` wiring) remains with its own slice.
- `response_states` is accepted: each assistant transcript entry now carries its own decoded `answerStatus` (copied from `response.status` in `ResponseReceived`), so a supported answer and an abstention are visibly different and distinguishable in place. `ChatMessageBubble` branches exhaustively on speaker × status: an answered reply keeps the neutral `surface` `Asistente` card with the server `answer` verbatim, while an abstained reply renders in the accepted `cautionSurface`/`caution` tokens with the new `Sin respuesta segura` label, the pinned limitation message verbatim, merged semantics and a polite live region — never colour alone, never a confident legal-certainty treatment, and never folded into the danger failure notice. `CONSTRAINTS.md` records the client MUST rule. Independent validation accepted 2026-10-13 (record: `docs/validations/response_states.md`); the rendered-evidence gap stays with `chat_accessibility` and the marker-card rendering with `answer_source_cards`.

## Start and verify

- Startup/toolchain check: `./init.sh`
- Standard verification: `./init.sh --verify`
- Android build: `./init.sh --android`
- Launch Desktop: `./init.sh --desktop`
- Source catalog check: `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of YYYY-MM-DD`
- Retrieval baseline (fixture, report-only): `python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5`
- Grounded generation (fixture, report-only; grounding invariants enforced): `python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5`
- Abstention decisions (fixture, report-only; abstention invariants enforced): `python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5` (a catalog whose sources are all ineligible as of `--as-of` yields `corpus: not_current` and `stale_evidence` for every question; omit `--passages` in that case)
- Backend tests: `cd backend && python -m pytest` (note: bare `pytest` cannot collect `tests/test_health.py`, because nothing puts `backend/` on `sys.path`; use `python -m pytest` or install the test runner into a local virtualenv)


## Session log

| Date | Change | Evidence |
|---|---|---|
| 2026-10-05 | Build brief initiated | User described project: olive tree field manager app with AI chatbot |
| 2026-10-05 | Discovery documents created | CONTEXT.md, build-brief.md, domain-model.md, risks-and-open-questions.md |
| 2026-10-07 | Harness starter started | AGENTS.md, init.sh created; feature_list.json in progress |
| 2026-10-07 | Harness starter completed | Minimal repo harness created |
| 2026-10-08 | Refreshed the startup harness and split MVP work into session-sized features. | Repository inspection; no tests run in this harness update. |
| 2026-10-09 | Product discovery and harness with OpenAI Luna High. | Some conflicts manually solved 😂 and additional skills.|
| 2026-10-11 | Added subagent workflow agents | .opencode/agents workflow files |
| 2026-10-11 | Implemented and independently validated `backend_health` | `backend/tests`: 2 passed; live Uvicorn `/health` smoke check returned HTTP 200 and the documented JSON response |
| 2026-10-11 | Completed `chat_home` | Added shared Spanish chat starting screen and composer, pure reducer tests, Compose resources, and implementation spec. `:shared:jvmTest` and `:desktopApp:build` pass. Android checks are blocked by missing Android SDK configuration in the worktree. |
| 2026-10-11 | Accepted `answer_api_contract` | OpenAPI 3.1 contract, five representative fixtures, dependency-free validator, and independent validation record; focused checks passed. |
| 2026-10-11 | Implemented and independently reviewed `local_land_store` | Shared `LandRepository`, versioned local format, Android/Desktop adapters; `:shared:jvmTest` passed (5 tests); Android compile blocked by missing SDK configuration. |
| 2026-10-12 | Implemented `add_land` (self-verified, ready for independent validation) | Shared `AddLandState`/`AddLandAction` reducer, stateless `AddLandScreen` with previews, resource-backed Spanish copy, `App()` destination and lands wiring, Android/Desktop composition roots. `./init.sh --verify` passed: `:shared:jvmTest` 21 tests, `:shared:testAndroidHostTest` 20 tests, `:androidApp:assembleDebug`, `:desktopApp:build`. Desktop startup smoke via `:desktopApp:run` ran without startup errors. |
| 2026-10-12 | Accepted `add_land` | Independent validator re-ran `./init.sh --verify`, `:shared:jvmTest` and `:shared:testAndroidHostTest` with `--rerun-tasks` (21 and 20 tests, 0 failures), `:androidApp:assembleDebug`, `:desktopApp:build`, and a Desktop startup smoke; confirmed scope, commonMain-only UI, no land-data/exception logging, and the copy contract. Verdict accept; record `docs/validations/add_land.md`. |
| 2026-10-12 | Implemented `suggested_questions` | Shared `ChatHomeAction.SuggestedQuestionSelected` reducer case, three approved example strings in Compose resources with a wrapping-safe vertical layout in `ChatHomeScreen`, new reducer tests, and previews. `:shared:jvmTest` (7/7), `:shared:testAndroidHostTest` (7/7), `:androidApp:assembleDebug`, and `:desktopApp:build` pass via `./init.sh --verify`; Android emulator UI smoke and Desktop launch smoke recorded. Awaiting independent validation. |
| 2026-10-12 | Accepted `suggested_questions` | Independent validator accepted after re-running `:shared:jvmTest --rerun-tasks` (7/7), `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build`, and a byte-for-byte string check against the spec. Record: `docs/validations/suggested_questions.md`. |
| 2026-10-12 | Implemented `source_catalog_validation` (passing, awaiting independent validation) | Added versioned empty `knowledge/source_catalog.json`, `knowledge/source_catalog.schema.json`, `knowledge/README.md`, dependency-free `backend/app/source_catalog.py`, CLI `backend/scripts/validate_source_catalog.py`, and 23 fixtures with 43 focused tests. `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12` exited 0 with 0 sources; `python -m pytest tests/test_source_catalog.py` 43 passed; `python -m pytest` 45 passed; `git diff --check` clean. |
| 2026-10-12 | Accepted `source_catalog_validation` | Independent validator reproduced exit 0 on canonical/valid fixtures, 20 policy and 1 malformed non-zero rejections with located diagnostics, the `--as-of` expiry boundary, a socket-guard no-network check, and no content leakage across all fixtures. See `docs/validations/source_catalog_validation.md`. |
| 2026-10-12 | Implemented `chat_question_submission` | Shared reducer/effect chat flow, composition-scoped `ChatConversation`, Ktor `/ask` service with MockEngine test decoding `contracts/examples/response-answered.json`, injected `AnswerService` wiring, Spanish working/limit/clarification strings, and updated reducer tests. `python3 contracts/validate_examples.py`, `:shared:jvmTest` (24 tests), `:shared:testAndroidHostTest` (22 tests), `:desktopApp:build`, `:androidApp:assembleDebug`, and `./init.sh --verify` all pass; Desktop app started without exceptions. |
| 2026-10-12 | Accepted `chat_question_submission` | Independent validator (docs/validations/chat_question_submission.md) confirmed all four acceptance scenarios, re-ran the contract validator, JVM (24) and Android host (22) tests, a full `--rerun-tasks` Android+Desktop build, the iOS compile, and `./init.sh --verify`; decoded all three contract fixtures with the shipped DTO and confirmed no logging, no hard-coded production URL, and no contract/backend changes. Findings F1-F3 carried forward to the `/ask` wiring, `network_error_recovery`, and `chat_accessibility`. |
| 2026-10-13 | Added `visual_foundation` as a feature definition and wired the visual-foundation dependency into `response_states`, `answer_source_cards`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, and `chat_accessibility` | `feature_list.json` (commit 139d460); definition only, no implementation or checks run. |
| 2026-10-13 | Documentation consistency pass over accepted features | Added `docs/validations/chat_home.md` (reconstructed acceptance record), linked each accepted feature's validation record from `feature_list.json`, and corrected the `PROGRESS.md` next-feature and `visual_foundation` status. No product code changed. |
| 2026-10-13 | Implemented `visual_foundation` (self-verified; awaiting independent validation) | Added the shared `theme` package (`ManijeroColors.kt`, `ManijeroTheme.kt`, `ManijeroTypography.kt`) with the `DESIGN.md` tokens, a complete `lightColorScheme` mapping, a `LocalManijeroSemanticColors` local for caution/strong olive, and the single `bodySmall` line-height override; applied `ManijeroTheme` once in `App()` and repointed all fifteen previews. Tests: `:shared:jvmTest` 54 (incl. `ManijeroColorsTest` 10, `ManijeroTypographyTest` 4), `:shared:testAndroidHostTest` 51, all 0 failures; `:androidApp:assembleDebug` and `:desktopApp:build` pass via `./init.sh --verify`. Updated `DESIGN.md` with the derived-token table and light-only decision. |
| 2026-10-13 | Accepted `visual_foundation` | Independent validator re-ran `./init.sh --verify` and `:shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` (54 JVM / 51 Android host tests, 0 failures), reproduced the WCAG AA contrast pairs with an independent computation, and confirmed scope discipline (commonMain-only theme, no new module/dependency, hosts/strings/Gradle untouched, no logging). Record: `docs/validations/visual_foundation.md`. |
| 2026-10-13 | Implemented `source_retrieval` (passing, awaiting independent validation) | Added `knowledge/passages.schema.json` (`passage-set-v1`), `backend/app/retrieval.py`, `backend/scripts/evaluate_retrieval.py`, `backend/tests/test_retrieval.py`, and synthetic retrieval fixtures under `backend/tests/fixtures/retrieval/`; updated `knowledge/README.md` and `backend/README.md`. Fixture catalog validated exit 0; measured baseline `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`; `python -m pytest tests/test_retrieval.py` 76 passed; `python -m pytest` 121 passed; `git diff --check` clean. |
| 2026-10-13 | Accepted `source_retrieval` | Independent validator reproduced the fixture gate, the measured baseline and per-question ranks, determinism, k-window semantics, the empty-corpus case, and fail-closed exits 2 with located paths; confirmed no-network behavior with an independent socket/DNS/TLS guard, schema/validator sync, synthetic-only fixtures, scope discipline, and 76/121 passing tests in an out-of-repo venv. Findings F1-F4 non-blocking. See `docs/validations/source_retrieval.md`. |
| 2026-10-13 | Implemented `grounded_answer_generation` (passing, awaiting independent validation) | Added `backend/app/generation.py` (code-owned markers/notice, `verify_draft` rules, extractive generator, fail-closed `NotAnswered`, `to_answer_response`), `backend/scripts/evaluate_generation.py` (report CLI; invariants enforced, exit 0/1/2), `backend/tests/test_generation.py` (100 tests), and synthetic fixtures under `backend/tests/fixtures/generation/`; updated `knowledge/README.md` and `backend/README.md`, appended the spec's implementation findings, and created `CONSTRAINTS.md`. `python -m pytest tests/test_generation.py` 100 passed; `python -m pytest` 221 passed; fixture report exit 0 (5 answers, 8 claims, 0 ungrounded, 1 no-evidence); canonical empty catalog exit 0; ambiguity/harness-error path exit 2; enforced-invariant path exit 1 (`policy_failed`); byte-identical `--json` runs; `contracts/validate_examples.py` and the unchanged retrieval baseline (`hit@5 = 0.857`) re-checked; `git diff --check` clean. No dependency, no route, no client change. |
| 2026-10-13 | Accepted `grounded_answer_generation` | Independent validator reproduced the 100 focused / 221 full pytest passes, the fixture CLI run (exit 0; 5 answers, 8 claims, 0 ungrounded, 0 invented sources, 1 no-evidence), the literal feature-list verification, the empty-corpus runs, byte-identical `--json` runs, an independent socket guard, and fail-closed paths; confirmed the assembled payload matches `AskResponse`/`AnswerSource`, the retrieval baseline is unchanged (`hit@5 = 0.857`), fixtures are synthetic-only, and scope is clean with no repo dependency. Findings F1/F2 non-blocking. See `docs/validations/grounded_answer_generation.md`. |
| 2026-10-13 | Implemented `land_list` (self-verified; awaiting independent validation) | Added pure `LandListState`/`LandListAction`/`reduce` and the stateless resource-backed `LandListScreen` with 11 previews, 9 new `land_list_*` strings, and `App()` wiring: a `LandList` destination with one synchronous read site, the intended `Mis terrenos` routing change, and removal of the unreachable chat-home confirmation. `:shared:jvmTest` 60 tests, `:shared:testAndroidHostTest` 57 tests, `./init.sh --verify` pass; Android emulator and Desktop smoke recorded. |
| 2026-10-13 | Accepted `land_list` | Independent validator re-ran `./init.sh`, the focused and full `:shared:jvmTest` (60/0), `:shared:testAndroidHostTest` (57/0), `./init.sh --verify`, and a full `--rerun-tasks` build, and byte-for-byte checked the nine new strings against the spec; confirmed the failure/empty-state distinction and file-by-file scope discipline (only the intended `add_land` routing change). Findings F1-F6 non-blocking. See `docs/validations/land_list.md`. |
| 2026-10-13 | Implemented `safe_abstention` (passing, awaiting independent validation) | Added `backend/app/abstention.py` (9-reason taxonomy, pinned Spanish `ABSTENTION_MESSAGES`, false-premise/unit-conflict/stale-corpus pre-checks, one-way generation-reason map, `to_abstention_response`), `backend/scripts/evaluate_abstention.py` (offline report CLI; abstention invariants enforced, exit 0/1/2), `backend/tests/test_abstention.py` (178 tests), and synthetic fixtures `backend/tests/fixtures/abstention/*`; updated `backend/README.md` and `CONSTRAINTS.md`. Current-corpus run exit 0 (3 answered, 7 abstained, 0 abstentions with sources, 0 abstentions with figures, invariants hold, 0 expect-mismatches); expired-catalog run exit 0 with 3/3 `stale_evidence`; feature-list check: out-of-corpus → `no_evidence` and a numbered `Real Decreto` → `false_premise`, both with `sources: []` and a pinned rule-free message; `python -m pytest tests/test_abstention.py` 178 passed and `python -m pytest` 399 passed; generation/retrieval baselines and `contracts/validate_examples.py` unchanged; `py_compile` and `git diff --check` clean. No dependency, no route, no client change. |
| 2026-10-13 | Accepted `safe_abstention` | Independent validator reproduced the 178 focused / 399 full pytest passes, both CLI runs (current: 3 answered / 7 abstained, 0 abstentions with sources or figures, invariants hold; expired/non-approved/non-current: every question `stale_evidence`), the fail-closed exit 2 cases, the exit 0/1 contract, byte-identical `--json` runs, an independent `jsonschema` check of every payload against the dereferenced `AskResponse`, a byte-for-byte comparison of the nine pinned messages, its own out-of-corpus/false-premise/conflict probes, generator provenance, a stricter socket/DNS guard, and the unchanged generation (`5/8/0/1`) and retrieval (`hit@5 = 0.857`) baselines; confirmed `contracts/` and all do-not-touch files unmodified, `/health` the only route, synthetic labelled fixtures, and no repo dependency. Findings N1-N4 non-blocking. See `docs/validations/safe_abstention.md`. |
| 2026-10-13 | Implemented `network_error_recovery` (self-verified; awaiting independent validation) | Added the visible, recoverable failure path in `commonMain`: `ChatHomeState` gains `failure`/`failedQuestion` (outside `messages`), `RequestFailed(failure)` and `RetryClicked`; new `chat/AnswerFailure.kt` (`RequestFailure` + two payload-free exceptions); `KtorAnswerService` failure translation and `answerHttpClient` bounded `HttpTimeout` + `expectSuccess`; `ChatFailureNotice` with the `Reintentar` action and two previews; three spec-verbatim strings; 22 new tests (78 JVM / 69 Android host, 0 failures). `python3 contracts/validate_examples.py`, `./init.sh --verify`, `:androidApp:assembleDebug`, `:desktopApp:build`, and `:shared:compileKotlinIosSimulatorArm64` pass; Android emulator smoke captured the notice, the preserved wording, and a retry that returns to the same state. CONSTRAINTS.md gained the client MUST rule and `chat_question_submission.md` records F2 as closed from this side. |
| 2026-10-13 | Accepted `network_error_recovery` | Independent validator re-ran the contract validator, the focused three-class run (40/0), `:shared:jvmTest` (78/0), `:shared:testAndroidHostTest` (69/0), `:desktopApp:build`, `:androidApp:assembleDebug`, `:shared:compileKotlinIosSimulatorArm64`, and `./init.sh --verify` (exit 0); reproduced the bounded-timeout, `500`/`422`, and undecodable-`200` failure paths; byte-for-byte checked the three strings; and confirmed the failure-never-renders-as-an-answer invariant, retry without a duplicate user message, exact-wording retention, and clean scope. Findings N1-N5 non-blocking. Record: `docs/validations/network_error_recovery.md`. |
| 2026-10-13 | Implemented `edit_land` (self-verified; awaiting independent validation) | Added the pure `EditLandState`/`EditLandFailure`/`EditLandAction`/`reduce`/`Land.toEditLandState()`/`toDraftOrNull()` and the stateless prefilled `EditLandScreen` with 9 previews; each `Mis terrenos` row now has its own visible `Editar` control (row card stays non-clickable), `LandListScreen` takes `confirmation: LandListConfirmation?` (`ADDED`/`UPDATED`), `ChoiceGroup`/`ChoiceItem` widened `private`→`internal`, and `App()` gained the `EditLand` destination with the single `update(id, draft)` call site. 20 new tests (98 JVM / 87 Android host, 0 failures); `./init.sh --verify` passes; Android emulator smoke ran the two-land correction, cleared municipality, un-known, blank-name, cancel, relaunch-persistence, non-clickable row, and `font_scale 2.0` scenarios; Desktop startup smoke ran with no exception. `CONSTRAINTS.md` gained the “Land editing” MUST rule. |
| 2026-10-13 | Accepted `edit_land` | Independent validator re-ran `./init.sh`, the focused three-class run (20/0), `:shared:jvmTest --rerun-tasks` (98/0), `:shared:testAndroidHostTest --rerun-tasks` (87/0), `./init.sh --verify`, and a full `--rerun-tasks` build (91 tasks, 0 from cache), and byte-for-byte checked the eight new strings and the `CONSTRAINTS.md` rule; an independent scratch JVM probe against the real `FileLandStorage` reproduced the literal verification (editing one of two lands left the other record's serialized line byte-identical), the preserved `area`/`notes`, the emptied-municipality/`UNKNOWN` round-trips, and the blank-name / `LAND_MISSING` no-write paths. Verdict accept; findings F1-F6 non-blocking. Record: `docs/validations/edit_land.md`. |
| 2026-10-13 | Implemented `response_states` (self-verified; awaiting independent validation) | Added the per-entry assistant `ChatMessage.answerStatus` (copied from `response.status` only in `ResponseReceived`) and an exhaustive speaker × status rendering branch in `App.kt`: a neutral `surface` answered card vs a `cautionSurface`/`caution` abstained card with the new `Sin respuesta segura` label, verbatim `answer` body, merged semantics and a polite live region. New tests (an abstained entry state, an earlier abstention surviving a later answer, a `ChatConversation` abstention, one `onSurface`-on-`cautionSurface` contrast row) and the `CONSTRAINTS.md` client MUST rule. `python3 contracts/validate_examples.py`, focused `:shared:jvmTest` (46/0), `:shared:jvmTest` (82/0), `:shared:testAndroidHostTest` (73/0), `:desktopApp:build`/`:androidApp:assembleDebug`, `./init.sh --verify`, and `:shared:compileKotlinIosSimulatorArm64` all pass; greps clean. |
| 2026-10-13 | Accepted `response_states` | Independent validator re-ran the contract validator, `:shared:jvmTest --rerun-tasks` (82/0), `:shared:testAndroidHostTest --rerun-tasks` (73/0), `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` (72 tasks, exit 0), `./init.sh --verify` (exit 0), and `:shared:compileKotlinIosSimulatorArm64`; reproduced the per-entry answer/abstention behavior with its own probe test, the `14.58` contrast pair, and the byte-for-byte string; confirmed the exhaustive branch, verbatim rendering, three distinct states, and clean scope. Findings N1-N5 non-blocking. Record: `docs/validations/response_states.md`. |


## Feature evidence

### chat_home — accepted

Independent validator accepted commit 47e80c8 (acceptance commit a79946f; record:
`docs/validations/chat_home.md`). Verification recorded at acceptance:

- `./init.sh` passes with the restored Gradle 9.8.0 wrapper and reports the current feature state.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes and compiles the shared Compose screen.
- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android` stopped before compilation because the worktree had no `ANDROID_HOME` or `local.properties` with `sdk.dir`. No Android result was claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running target; compilation is covered by `:desktopApp:build`.
- Outstanding: the spec's Android/Desktop manual smoke ("locate the Spanish field without adding a land, type a question, and confirm the action becomes available") was not executed at acceptance. It is not evidence of failure and can now be run where the Android SDK is configured.

### chat_question_submission — accepted

- `ChatHomeState.reduce` is a pure reducer returning `ChatReduction(state, effect)`. It
  rejects blank and over-2,000-character questions, refuses a second submit while a
  request is in flight, keeps the submitted wording immutable for both the user message
  and `AskRequest.question`, appends at most one assistant message per response, retains
  `abstained` / `needs_land_clarification` status plus opaque `land_ids_to_choose` without
  inventing an answer or a land choice, and releases the request on failure without
  discarding a newly typed draft.
- `ChatConversation` applies the reducer and runs the single `AnswerService.ask` call on
  its injected `CoroutineScope` (composition-scoped `rememberCoroutineScope()` in
  `App`), so no Composable performs a network call and `CancellationException` is
  rethrown. `App(answerService = UnavailableAnswerService)` injects the boundary, renders
  the ordered transcript with text labels "Tú"/"Asistente", a plain-Spanish working
  indication ("Estoy preparando la respuesta…") with a polite live region, a disabled
  **Preguntar** while in flight, the Spanish limit explanation without rewriting wording,
  and a neutral clarification acknowledgement that claims no answer.
- `KtorAnswerService` posts the contract `AskRequest` to `<baseUrl>/ask`
  (`ContentNegotiation` + `answerJson` with `explicitNulls = false`). No production base
  URL is hard-coded, and platform engines can be supplied through `answerHttpClient`.
- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples
  against answer_api_contract".
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL, 24 tests, 0 failures
  (`ChatHomeStateTest` 13, `ChatConversationTest` 3, `KtorAnswerServiceTest` 2,
  `LandRepositoryTest` 4, 2 scaffold tests). `KtorAnswerServiceTest` asserts `POST /ask`,
  the exact original question `"  ¿Puedo regar hoy?  "`, exactly
  `{"mode":"general","lands":[]}` for `land_context`, and decodes the accepted
  `contracts/examples/response-answered.json` from the repository working tree.
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, 22 tests, 0 failures.
- `./gradlew :desktopApp:build` → BUILD SUCCESSFUL; `./gradlew :androidApp:assembleDebug`
  → BUILD SUCCESSFUL (`androidApp/build/outputs/apk/debug/androidApp-debug.apk`);
  `./init.sh --verify` → BUILD SUCCESSFUL. This worktree has
  `local.properties` (`sdk.dir=/Users/jose/Library/Android/sdk`), so the Android checks
  ran; no environment blocker remains.
- Runtime smoke: `./gradlew :desktopApp:run` started the Desktop window with the shared
  chat screen and produced no exception in the run log. No scripted click-through or
  screenshot was taken (interactive GUI target), and no live answer was requested because
  the backend still has no `/ask`; the working-state/one-reply behavior is covered by
  `ChatConversationTest`.
- Privacy check: `grep -rn "println|Log\.|Logger|printStackTrace" shared/src` returns no
  matches, so no raw question or land content is logged.
- Deliberately not implemented (owned by later features): `response_states`, source
  cards, land selection/context, retry UI and failure copy, suggested prompts, and any
  backend/contract change.

### source_catalog_validation — accepted

- Canonical catalog `knowledge/source_catalog.json` is `schema_version: source-catalog-v1`
  with an empty `sources` array; it validates and does not imply corpus coverage.
- `knowledge/source_catalog.schema.json` is the readable contract; the test suite
  asserts its required/optional fields, issuer enum, and version stay in sync with
  `backend/app/source_catalog.py`.
- `backend/app/source_catalog.py` is standard-library only and offline. It enforces
  strict/unknown keys, unique slug ids, non-blank text, HTTPS approved-host and
  issuer-host match, SHA-256 digest shape, ISO dates and ordering, `approved`
  review with a named reviewer, `current` lifecycle, and `--as-of` expiry.
- Commands actually run:
  - `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12`
    → exit 0, `valid source catalog: ... (schema source-catalog-v1, 0 source(s) checked as of 2026-10-12)`.
  - Accepted fixture `valid_official_source.json` (3 sources: BOE, Junta de Andalucía,
    FEGA) → exit 0; `valid_empty_catalog.json` → exit 0 with 0 sources.
  - All 21 rejection fixtures → non-zero. Twenty fail with exit 1 and a located
    diagnostic such as `$.sources[0].content_sha256: required key is missing`,
    `$.sources[1].id: duplicate id; already used by $.sources[0]`,
    `$.sources[0].original_url: host is not on the approved official-domain allowlist`,
    and `$.sources[0].valid_until: is before the validation date; the document is
    expired and ineligible`; `malformed_json.json` fails with exit 2.
  - `cd backend && python -m pytest tests/test_source_catalog.py` → 43 passed.
  - `cd backend && python -m pytest` → 45 passed (43 new + 2 existing health tests).
  - `git diff --check` → clean.
- Not run: Android/Gradle checks (not applicable to this knowledge/backend feature).
- Independent validation (2026-10-12): `accept`. The validator re-ran the canonical
  and valid fixtures (exit 0), all 23 fixtures (20 exit 1 + 1 exit 2), the `--as-of`
  expiry boundary, a socket-guard no-network check, and a no-content-leak check; it
  also confirmed scope discipline and that the recorded evidence matched. Record:
  `docs/validations/source_catalog_validation.md`.
- Limitation: the validator proves catalog-policy conformance, not that a remote
  document is authentic, current, or legally applicable. No real document was added.

### source_retrieval — accepted

What changed:

- `knowledge/passages.schema.json`: readable, versioned `passage-set-v1` contract
  mirroring the catalog schema style. Top level has only `schema_version` and
  `passages`; each passage has non-blank `id` (unique, lowercase slug),
  `source_id`, `location`, `text`, plus optional `critical` and `applicability`
  (same value rules as the catalog). The tests assert the schema and the
  in-code validator stay in sync.
- `backend/app/retrieval.py`: standard-library only and offline.
  - `validate_passage_set` / `load_passage_set`: strict, located diagnostics
    (`$.passages[0].excerpt: unknown key is not allowed`) that never echo field
    values or excerpt text.
  - `tokenize`: lowercase, NFKD + combining-mark stripping, split on
    non-alphanumerics, Spanish stopword removal, so `"solicitud única"` and
    `"SOLICITUD unica"` tokenize identically.
  - `Bm25Index`: Okapi BM25, `k1 = 1.5`, `b = 0.75`, deterministic ordering with
    ties broken by passage id, and no candidate returned with a zero score.
  - `Retriever.from_documents` and `Retriever.search`: re-runs
    `validate_catalog`, raises `CatalogRejectedError` on an invalid catalog
    (fail closed, no partial index), raises `PassageSetError` located at
    `$.passages[i].source_id` for an unknown source, indexes only sources that
    are `approved`, `current`, and unexpired as of `as_of`, and maps
    `RetrievedPassage` to the accepted `AnswerSource` field names
    (`title`, `issuing_body`, `url`, `location`, `published_or_updated_on`,
    `verified_on`, `excerpt`) plus `passage_id`, `source_id`, `applicability`,
    `critical`, `score`, `rank`. Applicability and `critical` use the
    passage-level value when declared, otherwise the source-level value, and are
    surfaced only (no filtering).
- `backend/scripts/evaluate_retrieval.py`: report-only baseline CLI with an
  explicit `--as-of` and `--k`, per-question expected-passage ranks, aggregate
  `hit@k`/`recall@k`/MRR, `--json`, and `--fail-on-miss` off by default. Exit
  codes: `0` report, `1` only with `--fail-on-miss` and a miss, `2`
  unreadable/invalid input.
- `backend/tests/fixtures/retrieval/`: synthetic, clearly labelled fixtures — an
  approved 3-source catalog, 12 reviewed passages, 7 JSONL questions, and the
  edge cases (unknown `source_id`, unknown key, bad applicability value,
  malformed JSON, expired catalog, non-approved catalog, non-current catalog).
  None of them states a real deadline, amount, or article.
- `knowledge/README.md` and `backend/README.md`: document the passage contract,
  the eligibility coupling to the accepted catalog gate, and the baseline
  command. `/health` remains the only route.

Measured baseline (synthetic fixtures, reported not enforced):

- `python3 backend/scripts/validate_source_catalog.py backend/tests/fixtures/retrieval/catalog.json --as-of 2026-10-13`
  → exit 0, `(schema source-catalog-v1, 3 source(s) checked as of 2026-10-13)`.
- `python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0; `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`;
  3 eligible sources, 12 indexed passages, 0 excluded. Six source-anchored
  questions return the expected passage at rank 1 (including the unaccented
  `"solicitud unica"` variant); the deliberate synonym probe
  (`"¿Quién puede pedir las ayudas?"` vs the `titular de la explotación`
  passage) misses and is reported as a miss.
- Determinism: two `--json` runs are byte-identical (`diff` clean); repeated
  in-process searches return identical `(passage_id, rank, score)` tuples.
- Canonical empty corpus:
  `python3 backend/scripts/evaluate_retrieval.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5`
  → exit 0 with 0 eligible sources, 0 indexed passages, no questions; with
  `--eval` and no `--passages`, every question returns zero candidates
  (`hit@5 = 0.0`).
- Fail closed: expired (`valid_until 2026-01-01`), non-approved
  (`review_status pending`), and non-current (`lifecycle_status repealed`)
  catalogs raise `CatalogRejectedError` and the CLI exits 2; an unknown
  `source_id` exits 2 with `$.passages[0].source_id`.
- `cd backend && python -m pytest tests/test_retrieval.py` → 76 passed.
- `cd backend && python -m pytest` → 121 passed (76 new + 45 existing).
- `python3 -m py_compile backend/app/retrieval.py backend/scripts/evaluate_retrieval.py backend/tests/test_retrieval.py`
  → clean; `git diff --check` → clean.
- No network: a socket-guard test replaces `socket.socket` with a raising stub
  and still builds the index and searches successfully.
- Not run: Android/Desktop/Gradle checks (not applicable to this
  backend/knowledge feature) and no browser/API/E2E test (no user-facing or API
  flow; no persistent E2E framework exists).

Environment note: this worktree has no `python` on `PATH` and the system
interpreter has no `pytest`, so the pytest commands ran with the interpreter of
a temporary virtualenv (`python -m pytest` semantics) created outside the
repository. No dependency was added to `backend/requirements.txt` or the repo.

Limitations (honest):

- The evaluation set is tiny, synthetic, and authored by the implementer, so the
  baseline is a calibration starting point, not a legal-coverage or
  question-answering quality claim.
- Retrieval is lexical (BM25) only, so it misses synonyms and acronyms; the
  synonym probe above demonstrates the gap.
- Because the accepted catalog gate already rejects non-approved, non-current,
  and expired sources, the retriever's per-source eligibility re-check is
  defense in depth: with a valid catalog the
  `excluded_passages_ineligible_source` count is normally 0. The predicate is
  unit-tested directly, and fail-closed refusal is tested with the ineligible
  catalog fixtures.
- `knowledge/passages.json` is intentionally not created; the passage format is
  exercised only by fixtures until a reviewed ingestion feature exists.

Independent validation (2026-10-13): accept. The validator reproduced the fixture
catalog gate (exit 0, 3 sources), the measured baseline (`hit@5 = 0.857 (6/7)`,
`recall@5 = 0.857`, `MRR = 0.857`), the per-question ranks (including the disclosed
synonym miss), byte-identical deterministic `--json` runs (also across hash seeds and
shuffled corpus order), hand-recomputed metrics, `k`-window semantics, the
empty-corpus zero-candidate case, and fail-closed exits `2` with located paths for
expired/non-approved/non-current catalogs and unknown `source_id`/keys. It confirmed
local-only behavior with a stricter independent socket/DNS/TLS guard and a
blocked-socket CLI subprocess, verified schema/validator sync and synthetic-only
fixtures with no real legal facts, and ran the suites in a venv outside the repo
(76 focused, 121 full) with no dependency added. Scope confirmed clean: `contracts/`,
the catalog validator, the `/health`-only service, client code, and `init.sh` are
untouched. Findings F1-F4 are non-blocking; F4 (flag an eval line that names an
unknown passage id) is optional harness hardening. Record:
`docs/validations/source_retrieval.md`.

### local_land_store — accepted

- `LandRepository` supports create/list/update/delete with stable generated ids,
  required trimmed names, explicit unknown attributes, and optional fields.
- `SharedPreferencesLandStorage` persists Android records; `FileLandStorage`
  persists Desktop/JVM records. Both use the shared versioned format.
- Malformed individual records are skipped during recovery; writes replace the
  complete snapshot.
- Verification: `/Users/jose/AndroidStudioProjects/Manijero/gradlew -p . :shared:jvmTest`
  passed. Android compilation could not run because the worktree has no Android
  SDK location (`ANDROID_HOME`/`local.properties`).

### add_land — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandState.kt`: pure
  `AddLandState` (raw name/municipality text, selected enums, name-error and save-error
  flags), `AddLandAction`, `reduce`, and `toDraftOrNull()`. It keeps raw text for
  correction, trims only to validate and to build the `LandDraft`, leaves `areaHectares`
  and `notes` unset, and owns no ids, timestamps, or persistence rules.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: stateless
  Material 3 form with a required name field (error state plus plain-Spanish message),
  optional `Municipio (opcional)`, accessible `RadioButton` rows for `Riego` and
  `Producción` (both starting on `No lo sé`), a live-region save-failure message, one
  prominent `Guardar terreno` action, and `Cancelar` as the visible back control.
  Eight previews cover blank, name error, known values, save failure, long text,
  compact, wide, and 2x font scale.
- `shared/src/commonMain/composeResources/values/strings.xml`: all add-land labels,
  choices, errors, and the success confirmation.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `App(landRepository)`
  holds the `Chat`/`AddLand` destination, routes `Mis terrenos` to the form, performs the
  synchronous repository write, returns to the chat home with a plain-Spanish saved
  confirmation, and shows the failure message while keeping every entered value.
  `App()` (no argument) is retained for the iOS scaffold and previews; without a
  repository the lands action is unavailable instead of creating a store in common code.
- `androidApp/.../MainActivity.kt`: one `LandRepository(SharedPreferencesLandStorage(applicationContext))`.
- `desktopApp/.../main.kt`: one remembered `LandRepository(FileLandStorage(~/.manijero/lands-v1.txt))`.

Verification (2026-10-12):

- `./init.sh` passed and created the worktree `local.properties`, so Android checks could
  run for the first time in this checkout.
- `./init.sh --verify` (i.e. `:shared:jvmTest :shared:testAndroidHostTest
  :androidApp:assembleDebug :desktopApp:build`) passed: 21 shared JVM tests (0 failures),
  20 Android host tests (0 failures), `androidApp/build/outputs/apk/debug/androidApp-debug.apk`
  produced, Desktop app built.
- New tests: `AddLandStateTest` (11) — default `UNKNOWN` choices, blank/whitespace name
  rejected with no draft, trimmed name-only draft with no area/notes, `IRRIGATED`+`ORGANIC`
  mapping, deliberate `MIXED`, Unicode name, save failure retaining values for retry,
  error clearing on edit, and two lands surviving reopening. `AddLandDesktopStoreTest` (1)
  — the real `FileLandStorage` keeps a name-only and a known-attributes land after
  reopening.
- Desktop startup smoke: `./gradlew :desktopApp:run` launched `com.jamarglex.manijero.MainKt`
  with the injected file store and ran without startup errors until the session stopped it
  (Gradle reported the expected SIGTERM exit 143).
- Not verified by automated UI tests: interactive Android/Desktop clicking, screen-reader, and
  large-system-text behavior; no emulator, device, or Compose UI test harness exists yet. The
  spec defers this to `land_form_accessibility`, and it is reported here rather than claimed.

Independent validation (2026-10-12): accept. The validator re-ran `./init.sh --verify`,
`:shared:jvmTest` and `:shared:testAndroidHostTest` with `--rerun-tasks` (21 and 20 tests,
0 failures), `:androidApp:assembleDebug`, `:desktopApp:build`, and a Desktop startup smoke,
then confirmed scope discipline, `commonMain`-only product UI, no land-data or raw-exception
logging, and the copy contract. Record: `docs/validations/add_land.md`.

### suggested_questions — accepted

- Independent validator accepted (record: `docs/validations/suggested_questions.md`) after re-running
  `:shared:jvmTest --rerun-tasks` (ChatHomeStateTest 7/7), `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug`, and `:desktopApp:build`, and independently confirming the three shipped
  strings match the spec byte-for-byte with no unapproved deadline wording.
- `ChatHomeAction.SuggestedQuestionSelected(question: String)` sets `question` to the supplied
  text and clears `submittedQuestion`; the reducer performs no I/O and adds no dependency,
  ViewModel, route, or platform adapter.
- The three approved strings ship verbatim in
  `shared/src/commonMain/composeResources/values/strings.xml`
  (`chat_home_suggestion_solicitud_unica`, `chat_home_suggestion_sigpac`,
  `chat_home_suggestion_condicionalidad`); a Python byte-for-byte comparison against the spec's
  Content decision matched all three, and the unapproved deadline wording
  ("¿Hasta cuándo puedo cambiar mi solicitud?") is not shipped.
- `ChatHomeScreen` renders a plain-Spanish heading plus the three examples as full-width
  `OutlinedButton` controls in a vertical `Column` inside the existing 720dp content width.
- Verification commands:
  - `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; `ChatHomeStateTest` 7/7 (4 new).
  - `./init.sh --verify` → BUILD SUCCESSFUL; `:shared:jvmTest`, `:shared:testAndroidHostTest`
    (ChatHomeStateTest 7/7), `:androidApp:assembleDebug` (`androidApp-debug.apk`),
    `:desktopApp:build`.
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, debug APK): all three examples visible
  without sideways scrolling; tapping each filled the composer with the exact question and enabled
  `Preguntar`; submit showed only "Tu pregunta está lista para continuar."; re-selecting an example
  cleared the stale submitted message; at `font_scale 2.0` labels wrapped to two lines with no
  horizontal overflow.
- Desktop smoke: `:desktopApp:run` launched the shared `App()` and stayed alive ~50s with no
  runtime exception; interactive window/click inspection was not captured in this session.

### visual_foundation — passing (awaiting independent validation)

What changed:

- New shared theme package `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/`:
  - `ManijeroColors.kt`: the ten `DESIGN.md` tokens plus the derived values, a fully specified
    `lightColorScheme(...)` (every documented role set explicitly, so no Material default can leak),
    `ManijeroSemanticColors` + `LocalManijeroSemanticColors` for the roles Material 3 lacks
    (caution, caution surface, strong olive; `danger` = `colorScheme.error`, `border` =
    `colorScheme.outline`), and the dependency-free WCAG `relativeLuminance`/`contrastRatio` helpers.
  - `ManijeroTypography.kt`: Material 3 `Typography` with the single documented `bodySmall`
    line-height override (16sp → 18sp); size, weight, letter spacing, and font family untouched.
  - `ManijeroTheme.kt`: `ManijeroTheme { }` (Material 3 theme + semantic local) plus review-only
    token-board previews at 1x and `fontScale = 2f`.
- `App.kt`: wraps the destination content in `ManijeroTheme` once (the shared composition root), and
  all seven previews use `ManijeroTheme`. `lands/AddLandScreen.kt`: all eight previews use
  `ManijeroTheme`. No layout, copy, spacing, or behavior changed; the Android/Desktop/iOS hosts stay
  theme-free so they inherit the one shared theme.
- `DESIGN.md`: added the derived-token table and the light-only decision to the "Visual foundation"
  section.
- Not changed: `MainActivity.kt`, desktop `main.kt`, `MainViewController.kt`, `strings.xml`, any
  Gradle file or the version catalog, backend/contracts, land storage, `init.sh`; no new module,
  framework, or dependency.

Verification (commands run from the repository root):

- `./init.sh --verify` → BUILD SUCCESSFUL.
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL:
  54 JVM tests / 0 failures (`ManijeroColorsTest` 10, `ManijeroTypographyTest` 4 new) and
  51 Android host tests / 0 failures (same 14 new theme tests).
- `./gradlew :androidApp:assembleDebug` and `./gradlew :desktopApp:build` → BUILD SUCCESSFUL
  (debug APK produced) as part of `--verify`.
- Centralization greps: no `Color(0x` outside `theme/`; no argument-less `MaterialTheme {`; the only
  `MaterialTheme(` call site is the `ManijeroTheme` wrapper; no
  `LocalMinimumInteractiveComponentSize`/`minimumInteractiveComponentSize` override; the theme is
  applied once in `App()`.

Honest gaps:

- Interactive Android/Desktop UI smokes (screenshots, greyscale non-color cue check, emulator
  `font_scale 2.0`, Desktop window resize/keyboard focus) were not run in this non-interactive
  session. They are covered by the review-only token-board preview and the pure contrast tests, and
  remain the manual checks for independent validation.
- Light-only by decision: no dark palette exists (`DESIGN.md` records this). Desktop OS-level text
  scaling is not wired in this repository, so enlarged-text evidence is preview-based
  (carried validator finding F3, owner `chat_accessibility`).
  
### grounded_answer_generation — accepted

Independent validator accepted (2026-10-13, record:
`docs/validations/grounded_answer_generation.md`). It reproduced the 100 focused /
221 full pytest passes, `py_compile`, `git diff --check`, the fixture CLI run
(exit 0; 5 answers, 8 claims, 0 ungrounded, 0 invented sources, 1 no-evidence,
invariants hold, 0 expect-mismatches), the literal feature-list verification
(plazo claim 1 = the `critical` rank-1 excerpt with the fictitious `42 días`
cited `[1]`; claim 2 = the rank-2 excerpt `[2]`), the canonical empty-corpus run
(exit 0; exit 2 with `--eval` naming unknown ids), byte-identical deterministic
`--json` runs (sha256 `f8345c12…e453`), and a stricter independent socket guard
that still produced the answer. It confirmed fail-closed paths (eligibility →
`policy_failed`, exit 1; `--fail-on-miss` opt-in), the assembled payload matching
`AskResponse`/`AnswerSource` with no retrieval-local leakage, the unchanged
retrieval baseline (`hit@5 = 0.857`), `contracts/validate_examples.py` passing,
synthetic-only labelled fixtures with no real legal fact, and that `contracts/`,
`retrieval.py`, `source_catalog.py`, `main.py`, `knowledge/source_catalog.json`,
`passages.schema.json`, `requirements.txt`, `init.sh`, and all client/shared code
are untouched with no repo dependency. Non-blocking findings carried forward:
F1 (prefix-only marker/`sources` invariant; fix before the hosted-model path or
`answer_source_cards`) and F2 (non-iterable `source_markers` raises `TypeError`
instead of returning `generation_error` at the model seam); N1 (`init.sh` banner
stale; the spec mandates no change); N3 (spec lists retrieval imports the module
deliberately omits).

What changed:

- `backend/app/generation.py` (new, standard-library only, offline): the *write*
  side of the accepted source gate.
  - `DraftAnswer(status, answer, source_markers)` mirrors the projected
    `{"status", "answer", "sources"}` shape so a future model adapter produces
    the same draft type; `verify_draft` is applied to it unchanged.
  - `verify_draft` rules: status must be `answered`; non-blank answer; at least
    one `[n]` marker; every marker must be a returned candidate number; declared
    `source_markers` must equal the inline markers; every sentence must carry a
    marker; every figure/date (± ISO and `dd/mm/yyyy` dates, thousands
    separators, decimal comma, percent) must appear in the text of the cited
    passage(s); a claim citing a `critical` passage must be a literal substring
    of that passage after whitespace/case/diacritic normalization; a
    legal-status assertion (starter phrase list) is a policy violation.
  - `ExtractiveGroundingGenerator` is the only enabled generator: one verbatim
    reviewed excerpt plus its marker per top candidate, no clock, no model. A
    hosted rephrasing path must implement `GroundingGenerator` and pass the same
    `verify_draft`.
  - `generate_grounded_answer` returns `Answered` only when the whole draft
    verifies, otherwise `NotAnswered(reason, issues, claims)` with reason
    `invalid_question`, `no_candidates`, `generator_abstained`,
    `grounding_failed`, `policy_failed`, or `generation_error`. A failing draft
    is discarded whole; no rejected-draft text is emitted.
  - Citation markers, the `sources` array (`[n]` = `sources[n-1]`, deduplicated
    ascending), the pinned lead-in and notice, and the seven accepted
    `AnswerSource` keys are all code-owned; retrieval-local fields never cross
    into the payload.
- `backend/scripts/evaluate_generation.py` (new): report-only CLI with `--catalog`,
  `--passages`, `--eval`, `--as-of`, `--k`, `--json`, `--fail-on-miss`.
  Grounding invariants are enforced (exit `1`); answer coverage is not, unless
  `--fail-on-miss` is passed. Exit `2` for unreadable/invalid input; an `--eval`
  line naming a passage id absent from the built index is a harness error
  (exit `2`), closing accepted finding F4.
- `backend/tests/test_generation.py` (new, 100 tests) plus synthetic fixtures
  `backend/tests/fixtures/generation/{catalog.json,passages.json,eval_questions.jsonl,drafts_ungrounded.json}`
  (2 approved sources, 4 labelled-synthetic passages, 2 of them `critical` with
  fictitious figures 42 and 1.200, 6 evaluation lines including an out-of-corpus
  one, and 13 rejected drafts keyed by issue code).
- `knowledge/README.md` and `backend/README.md`: document the generation
  boundary, the code-owned citation/notice rules, the enforced exit codes, the
  reviewer excerpt guidance, and the report command. `CONSTRAINTS.md` (new)
  records the two answer-grounding MUST rules. The spec gained an
  "Implementation findings" section.

Verification (commands run from the repository root unless noted):

- `cd backend && python -m pytest tests/test_generation.py` → 100 passed.
- `cd backend && python -m pytest` → 221 passed (121 existing + 100 new).
- `python3 -m py_compile backend/app/generation.py backend/scripts/evaluate_generation.py backend/tests/test_generation.py`
  → clean; `git diff --check` → clean (a trailing blank line accidentally added
  to `knowledge/README.md` was trimmed).
- `python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0: 2 eligible sources, 4 indexed passages, 0 excluded,
  `answers produced: 5`, `claims checked: 8`, `ungrounded claims: 0`,
  `invented sources: 0`, `no-evidence outcomes: 1`, `grounding invariants hold: yes`,
  `outcomes differing from expect: 0`. Every answered question prints its
  per-claim verdict and cited candidate numbers; the out-of-corpus line
  (`zzzz qqqq`) returns `no_candidates`.
- `python3 backend/scripts/evaluate_generation.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5`
  → exit 0 with 0 eligible sources, 0 indexed passages, "no evaluation questions
  supplied". With `--eval` and the empty catalog the index check exits `2`,
  naming the unknown ids (documented harness behavior).
- Enforced invariant, fail closed: a temporary passage set whose reviewed text
  contains a starter eligibility phrase → `outcome: policy_failed`,
  `claim 1: failed; cites [1] (eligibility_claim)`,
  `grounding invariants hold: no`, exit `1`. The 13 recorded rejected drafts each
  reproduce their expected issue code.
- Determinism: two `--json` runs are byte-identical (`diff` clean), sha256
  `f8345c124a3ba4ab0b2fd1e4947244b54e21b5cc2a289f024e13cf5b28a4e453`.
- Unchanged boundaries re-checked: `python3 contracts/validate_examples.py` →
  "Validated 2 request and 3 response examples against answer_api_contract"; the
  retrieval fixture baseline is unchanged at `hit@5 = 0.857 (6/7)`,
  `recall@5 = 0.857`, `MRR = 0.857`.

Not run and why:

- Android/Desktop/Gradle and `./init.sh --verify`: not applicable to this
  backend slice (no product UI, route, or Gradle input changed) and `init.sh`
  has no backend command.
- No browser/API/E2E check: there is no `/ask` route and no persistent E2E
  harness. The CLI is the manual smoke check for this feature.
- Environment: this worktree has no `python` on `PATH` and the system
  interpreter has no `pytest`, so the pytest commands ran with the interpreter of
  a temporary virtualenv created outside the repository. No dependency was added
  to `backend/requirements.txt` or the repo.

Limitations (honest):

- The checks are lexical: figure presence is not entailment, the eligibility
  check is a short phrase list, and semantic grounding plus conflict detection
  are explicitly deferred to `safe_abstention` and a later judge.
- The extractive default requires single-sentence excerpts; a multi-sentence
  excerpt whose trailing marker lands after the final period fails closed
  (`uncited_sentence`). Recorded in the spec and in `knowledge/README.md`.
- An excerpt containing a starter eligibility phrase is unanswerable through the
  extractive default (the verbatim claim is rejected). Fail closed and
  intentional; the reviewer guidance says to avoid such phrasing.
- Nothing about a canonical corpus changed: no `knowledge/passages.json` was
  created, and the fixture corpus is tiny, synthetic, and implementer-authored,
  so nothing here is a legal-coverage or answer-quality claim.
- `safe_abstention` was not implemented by this feature: it returned
  machine-readable reason codes only and no user-facing abstention copy. (The
  later `safe_abstention` feature, now accepted, consumes those codes and owns
  the pinned abstention copy.)

### land_list — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt`: pure
  `LandListState` (`lands`, `loadFailed`, `isEmpty`), `LandListAction`
  (`LandsLoaded`/`LoadFailed`/`ReloadClicked`), and `reduce`. `LandsLoaded` stores the supplied
  list exactly (order, identities, duplicate names — no sort/dedupe/rename) and clears
  `loadFailed`; `LoadFailed` clears `lands` and sets `loadFailed = true`, so a failed read never
  looks empty and stale rows never survive; `ReloadClicked` clears both before the caller re-reads.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: stateless
  `LandListScreen(state, onAddLand, onBack, onRetry, modifier, savedConfirmation)`. Plain,
  non-clickable rows show the exact name, municipality only when known, and always water and
  production with `UNKNOWN → No lo sé` and `MIXED → mixed copy`; rows use
  `mergeDescendants = true`; failure copy and the confirmation are `LiveRegionMode.Polite`;
  in the failure state `Añadir terreno` is withheld and a single `Reintentar` is offered.
  Eleven previews cover empty, two distinguishable, duplicate names, many, long text, failure,
  just-saved, compact (320dp), wide (900dp), and 2x font scale.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: new `LandList` destination and a
  single synchronous read site (`runCatching { repository.list() }` folded into
  `LandsLoaded`/`LoadFailed`, then reduced) invoked only on entry, retry, and after a save.
  `Añadir terreno` opens the unchanged `AddLandScreen`; `Cancelar` and a successful save return to
  the list with a reload and confirmation after a save. The intended `land_list` routing change
  removes the now-unreachable `ChatHomeScreen` `landSavedConfirmation` parameter, its block, and its
  preview. `App()` (iOS scaffold/previews) is unchanged; without a repository the lands action
  stays unavailable.
- `shared/src/commonMain/composeResources/values/strings.xml`: 9 new `land_list_*` keys (explanation,
  empty state, `Añadir terreno`, `Volver`, `Municipio`/`Riego`/`Producción` row lines, failure text,
  `Reintentar`) matching the spec copy verbatim, reusing `add_land_unknown`, `add_land_water_*`,
  `add_land_production_*`, `add_land_saved`, and `chat_home_lands`.
- Not changed: `Land`/`LandDraft`/`LandRepository`, the `land-store-v1` format, both storage
  adapters, `AddLandState`/`AddLandScreen` behavior, `MainActivity.kt`, `desktopApp/main.kt`,
  `MainViewController.kt`, Gradle files, `init.sh`, `theme/`, backend/contracts/knowledge, and
  unrelated features; no new module, dependency, ViewModel, coroutine, or navigation library.

Verification (commands run from the repository root):

- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **60 tests / 0 failures**
  (`LandListStateTest` 6 new).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **57 tests / 0 failures**.
- `./init.sh --verify` → BUILD SUCCESSFUL (`:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug` producing `androidApp-debug.apk`, `:desktopApp:build`).
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400): the empty state names `Añadir terreno`
  with no fake row; saving `Los Olivos` (name only) returns to the list with
  `Riego: No lo sé` / `Producción: No lo sé` and the saved confirmation; a second land
  (Municipio: Martos, Regadío, Ecológico) adds a distinguishable row in creation order; force-stop
  + relaunch keeps both rows with no duplicates or stale confirmation; `Volver` returns to the chat
  home and `Cancelar` returns to the list creating no record; `font_scale 2.0` wraps all rows and
  actions with no horizontal overflow.
- Desktop run: no read happens at startup; with an unreadable store the plain-Spanish failure state
  shows only `Reintentar` and `Volver` with `Añadir terreno` withheld; `Reintentar` keeps the honest
  failure while unreadable and recovers once the store is fixed.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out" shared/src` returns no
  matches; no network call, permission, dependency, or module was added; no land id/area/notes are
  shown and no land data or exception text is surfaced.

Independent validation (2026-10-13): accept. The validator re-ran `./init.sh`, the focused and full
`:shared:jvmTest` (60/0), `:shared:testAndroidHostTest` (57/0), `./init.sh --verify`, and a full
`--rerun-tasks` Android+Desktop build, and byte-for-byte checked the nine new strings plus the reused
land vocabulary against the spec; it confirmed the empty-vs-failure distinction (an independent
throwing-storage probe showed `LoadFailed` is not `isEmpty`), the no-logging/no-network constraints,
and file-by-file scope discipline (only the intended `add_land` routing change). Record:
`docs/validations/land_list.md`. Findings F1-F6 are non-blocking and carried forward (F1 optional
confirmation guard, F2 post-save failure pairing, F2b corrupt-store-content robustness owned by
`local_land_store` hardening, F3 Android system back owned by `chat_accessibility`, F5 evidence
hygiene, F6 default-clock `createdAt`).

Honest gaps:

- No persistent E2E or Compose UI-test framework exists, so no automated UI/E2E coverage is claimed.
- TalkBack row-merge reading and Desktop keyboard focus/resize were not verified end-to-end
  (assistive access denied / no harness); the `mergeDescendants` and polite live-region attributes are
  present in code, and these checks are deferred to `chat_accessibility` / `land_form_accessibility`.
- The failure state requires the read itself to throw (a non-string `land_store` value or an
  unreadable file); a corrupt-content store decodes to an empty list under the accepted
  `LandStoreFormat.decode` contract, which `land_list` is forbidden to change (F2b).
- Spec-recorded limits stand: two identical name-only lands render identically; `areaHectares` and
  `notes` are not shown; the read is synchronous on the composition frame.

### safe_abstention — accepted

Spec: `docs/specs/safe_abstention.md`. Status is `accepted` after independent validation (record:
`docs/validations/safe_abstention.md`, 2026-10-13). Detection is lexical and conservative, and no
score threshold is a release gate.

What was added:

- `backend/app/abstention.py` — the stable 9-reason taxonomy (`ABSTENTION_REASONS`), one pinned
  plain-Spanish message per reason (`ABSTENTION_MESSAGES`, no digit, no date, always a next step), a
  frozen `Abstention` (`reason`, `generation_reason`, `issues`, `claims`; no text field, so copy is
  code-owned), the one-way `GENERATION_REASON_MAP` (`no_candidates`→`no_evidence`,
  `grounding_failed`→`insufficient_evidence`, `policy_failed`→`unsafe_request`, everything else
  unchanged, unknown→`generation_error`), `prepare_corpus` (a corpus-level `stale_evidence`
  `Abstention` when the catalog declares sources but `eligible_source_ids` is empty as of `as_of`),
  `answer_or_abstain` (pre-checks then the accepted `generate_grounded_answer`), the lexical
  presupposition check (`presupposed_identifiers` / `has_unsupported_presupposition`), the
  unit-anchored conflict check (`CRITICAL_UNITS` / `unit_values` / `find_unit_conflict`), and
  `to_abstention_response` (exactly the accepted `AskResponse` keys with `status: abstained`,
  `sources: []`, `land_ids_to_choose: []`).
- `backend/scripts/evaluate_abstention.py` — offline report-only CLI (stdlib only, no network, no
  model provider) with `--catalog/--passages/--eval/--as-of/--k/--json/--fail-on-miss`, per-question
  outcome/reason/generation-reason/issue-codes/message, corpus `current`/`not_current`, and the
  aggregate counters `abstentions_with_sources`, `abstentions_with_figures`,
  `abstention_invariants_hold`. Exit `0` reported, `1` on a violated abstention invariant or (only
  with `--fail-on-miss`) an expect mismatch, `2` on unreadable/invalid input or arguments.
- `backend/tests/test_abstention.py` — 178 focused tests (taxonomy/copy, payload shape, every
  generation reason mapped, `prepare_corpus` current/stale/hard-error, false premise hit/miss, unit
  conflict vs different units, generator-never-called, determinism, socket guard, content-silent
  diagnostics, CLI 0/1/2, fixture hygiene, accepted-generation regression).
- `backend/tests/fixtures/abstention/{catalog.json,passages.json,eval_questions.jsonl,eval_questions_stale.jsonl}`
  — synthetic, labelled fixtures (7 passages: ordinary, identifier-present, two `critical` fictitious
  deadlines, a multi-sentence excerpt, a starter-eligibility excerpt, a `critical` fictitious amount).
  Every numeric line is marked `cifra inventada`; the only numbered reference is a deliberately
  impossible `999/2099`.
- `backend/README.md` and `CONSTRAINTS.md` — the abstention boundary, taxonomy table, CLI usage, and
  one MUST rule (an abstention may never carry a source, figure, or date, and its copy is code-owned).

Commands actually run and real results:

- `python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit `0`; `corpus: current`; eligible sources `2`, indexed passages `7`, excluded `0`; answered
  `3`, abstained `7`, `abstentions with sources: 0`, `abstentions with figures: 0`,
  `abstention invariants hold: yes`, `outcomes differing from expect: 0` (10 questions). Outcomes:
  answered for the solicitud/norma/importe questions; `conflicting_evidence` for the fictitious plazo
  question (`unit_conflict`; `critical` 30 días vs `critical` 45 días); `insufficient_evidence`
  (generation reason `grounding_failed`, issue `uncited_sentence`) for the multi-sentence excerpt;
  `unsafe_request` (generation reason `policy_failed`, issue `eligibility_claim`) for the
  starter-eligibility excerpt; `false_premise` for the `Real Decreto sintético` and the numbered
  `reglamento 999/2099` questions (`unconfirmed_presupposition`); `no_evidence` for `zzzz qqqq`;
  `invalid_question` for a blank question. Two `critical` passages about different units (a `días`
  deadline and a `euros` amount) still answer, so the accepted covered critical question is not
  over-abstained.
- Stale corpus: `python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/retrieval/catalog_expired.json --eval backend/tests/fixtures/abstention/eval_questions_stale.jsonl --as-of 2026-10-13 --k 5` (no `--passages`)
  → exit `0`; `corpus: not_current`; answered `0`, abstained `3`, every question `stale_evidence`
  (issue `stale_corpus`, `sources: []`, pinned message). Unit tests reproduce the same for
  `catalog_not_approved.json` and `catalog_not_current.json` and confirm the stale `Abstention` wins
  over an `invalid_question`. A structurally broken catalog, a malformed passage set, an unknown
  `source_id`, and an unreadable file stay hard errors (`CatalogRejectedError`/`PassageSetError`;
  CLI exit `2`), and the canonical empty `knowledge/source_catalog.json` still prepares a retriever
  with 0 sources and 0 passages.
- Literal feature-list verification with a two-line JSONL outside the repo: `¿Cuánto cuesta matricular un tractor viejo?`
  → `no_evidence` (generation reason `no_candidates`, `sources: 0`, message "No he encontrado esta
  información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal
  agraria o con tu cooperativa.") and `¿Qué dice el Real Decreto 123/2099 sobre el plazo de la solicitud?`
  → `false_premise` (issue `unconfirmed_presupposition`, `sources: 0`, message "No puedo confirmar ese
  dato con los documentos oficiales revisados. Comprueba el nombre o el número exacto con tu oficina
  comarcal agraria o con tu cooperativa."). `0` answered, `2` abstained, `0` with sources, `0` with
  figures, invariants hold, `0` expect-mismatches; no invented legal fact appears. The same
  identifier present in a candidate does not trigger the check (the `norma` question still answers).
- Exit contract and determinism: `--fail-on-miss` → exit `0` on the fixtures and exit `1` on a
  deliberately mismatched expectation while printing byte-identical output; without the flag the
  mismatch still exits `0`; `--k 0` → exit `2` ("--k must be a positive integer"); a malformed eval
  line, an eval file with no questions, an invalid `--as-of`, a missing catalog, and a missing or
  malformed passage set each exit `2` with empty stdout. Two `--json` runs are byte-identical
  (`cmp` exit `0`). A payload that leaks a source, a land choice, a blank/over-long message, a digit
  or a date, a non-`abstained` status, or an off-taxonomy reason makes the CLI exit `1`.
- Tests: `cd backend && python -m pytest tests/test_abstention.py` → **178 passed**;
  `cd backend && python -m pytest` → **399 passed** (221 existing + 178 new); `python3 -m py_compile backend/app/abstention.py backend/scripts/evaluate_abstention.py backend/tests/test_abstention.py`
  → clean; `git diff --check` → clean.
- Offline and content-silent: tests monkeypatch `socket.socket` to raise and the pipeline still
  abstains in both `prepare_corpus` and `answer_or_abstain`; a test asserts `abstention.py` imports
  no `socket`/`urllib`/`httpx`/`requests`; a test asserts no question text, excerpt text, or figure
  number reaches the issue diagnostics or the emitted message; a recorded generator draft is
  discarded whole.
- Regression boundaries unchanged: generation CLI → exit `0`, `5` answers, `8` claims, `0`
  ungrounded, `1` no-evidence; retrieval CLI → `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`,
  `MRR = 0.857`; the 6 accepted generation eval questions re-run through `answer_or_abstain` still
  resolve exactly as their expects say; `python3 contracts/validate_examples.py` → "Validated 2
  request and 3 response examples against answer_api_contract".
- Change scope: `git status --porcelain` shows only `backend/README.md`, `CONSTRAINTS.md`,
  `feature_list.json`, and `PROGRESS.md` modified (`backend/README.md` +54 / `CONSTRAINTS.md` +13
  insertions) plus the new paths; `contracts/`, `backend/app/generation.py`,
  `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`,
  `backend/scripts/evaluate_generation.py`, `backend/tests/test_generation.py`, `knowledge/`,
  `backend/requirements.txt`, `init.sh`, and all client/shared code are unmodified (checked per path).

Honest gaps:

- No `/ask` route and no persistent E2E harness exist, so the abstention reason stays observable only
  through this CLI and these tests until the route slice exists; no browser/API/E2E test was run.
- Android/Desktop/Gradle and `./init.sh` checks were not run: no product UI, route, or shared code
  changed and `init.sh` has no backend command.
- Detection is lexical, not semantic: a retrieval miss, or two unrelated `critical` passages that
  share a unit, can abstain. `prepare_corpus` treats any declared-but-all-ineligible catalog as
  `stale_evidence` even when the ineligibility comes from a malformed currency field (structurally
  broken catalogs stay hard errors). Widening conflict detection requires measurement, not assumption.
- No calibrated threshold and no trap-set measurement is introduced (`land_safety_evaluation` owns
  both); the tiny implementer-authored synthetic corpus means no reason code here is a coverage or
  answer-quality claim.
- Carried-forward accepted generation finding F2 (non-iterable `source_markers` at the model seam) is
  unchanged.
- Environment note: this worktree has no `python` on `PATH` and the system interpreter has no
  `pytest`, so pytest ran from a temporary venv outside the repository (Python 3.9.6) with the repo's
  own `backend/requirements.txt` installed into it; no dependency was added to the repo.

Independent validation (2026-10-13): accept. The validator did not trust the implementer report and
reproduced the 178 focused / 399 full pytest passes, `py_compile` and `git diff --check`, both CLI runs
(current corpus: 3 answered / 7 abstained, 0 abstentions with sources or figures, invariants hold; and
expired/non-approved/non-current catalogs: every question `stale_evidence`), the fail-closed exit `2`
cases with located JSON paths, the exit `0`/`1` contract, byte-identical `--json` runs (also under two
`PYTHONHASHSEED` values), an independent `jsonschema` validation of every payload against the
dereferenced `AskResponse`, a byte-for-byte comparison of the nine pinned messages plus digit/date and
eligibility checks, its own out-of-corpus, false-premise (present/absent/different-instrument/location-
only), and same-unit-versus-different-unit conflict probes, generator provenance (0 generator calls for
invalid/no_evidence/false_premise/conflict; rejected drafts never emitted), and a stricter independent
`socket`/DNS guard that still abstains and answers. It confirmed the unchanged generation
(`5` answers, `8` claims, `0` ungrounded, `1` no-evidence) and retrieval (`hit@5 = 0.857 (6/7)`,
`recall@5 = 0.857`, `MRR = 0.857`) baselines, `contracts/validate_examples.py` passing with
`contracts/` untouched, `GET /health` the only route, synthetic labelled fixtures with no real legal
fact, and no repo dependency (pytest ran from an out-of-repo venv, Python 3.9.6). Findings N1-N4 are
non-blocking: N1 (evidence wording over-narrow about which files were modified; corrected here),
N2 (a structurally-plausible-but-semantically-invalid catalog can yield `stale_evidence` instead of a
hard error; matches spec rule 6, fails safe, owner a later catalog-hardening slice), N3
(`test_abstention.py:553` uses a real-looking statute id `7/2022`; a pure extractor literal, prefer an
impossible id for fixture-policy consistency), N4 (substring containment in the presupposition check
can under-abstain, e.g. `ley` inside `leyenda`; the prescribed lexical behaviour, to be measured in
`land_safety_evaluation`). Record: `docs/validations/safe_abstention.md`.

### network_error_recovery — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatHomeState` gains
  `failure: RequestFailure?` and `failedQuestion: String?`, both kept **outside** `messages`, so a
  failure can never render as an assistant answer. `ChatHomeAction.RequestFailed` becomes
  `data class RequestFailed(val failure: RequestFailure)`, and the new `data object RetryClicked`
  re-emits `ChatEffect.Submit(failedQuestion)` only from `IDLE` with a retained failure, sets
  `SUBMITTING`, clears `failure`/`question`, and leaves `messages`/`failedQuestion` untouched, so a
  retry appends no second user message and a repeated failure stays retryable. `AskClicked`,
  `QuestionChanged`, `SuggestedQuestionSelected` and `ResponseReceived` clear the notice;
  `canAsk`/`isOverCharacterLimit`/`awaitingLandClarification` are unchanged.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerFailure.kt` (new): the
  `RequestFailure` enum (`COULD_NOT_REACH_SERVICE`, `SERVICE_ERROR`) plus the two payload-free
  exceptions `AnswerServiceUnavailableException`/`AnswerServiceErrorException` with fixed literal
  messages, so no URL, body, or question text can travel with a failure.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `answerHttpClient`
  sets `expectSuccess = true` and installs bounded `HttpTimeout` (`REQUEST_TIMEOUT_MILLIS` 15_000,
  `CONNECT_TIMEOUT_MILLIS` 10_000, `SOCKET_TIMEOUT_MILLIS` 15_000; the request bound is a parameter
  only so tests can use a tiny one). `KtorAnswerService.ask` rethrows `CancellationException` and
  translates `ResponseException`/`ContentConvertException`/`SerializationException` to the service
  error and `kotlinx.io.IOException` (timeout, connect, socket, I/O) to the unavailable signal.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`: maps
  `AnswerServiceUnavailableException` to `RequestFailed(COULD_NOT_REACH_SERVICE)` and every other
  exception (including `UnavailableAnswerService`'s `IllegalStateException`) to
  `RequestFailed(SERVICE_ERROR)`; still rethrows `CancellationException`; no logging was added.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatFailureNotice` renders from
  `state.failure` after the transcript — themed `errorContainer` fill with an `error` border, the
  `onErrorContainer` message, and a `Reintentar` button using the `error`/`onError` pair. It is a
  polite live region, carries no `Asistente` label, is never a `ChatMessage`, and is mutually
  exclusive with the working indication. Two previews added (unreachable; service error at
  `widthDp = 320`, `fontScale = 2f`).
- `shared/src/commonMain/composeResources/values/strings.xml`: `chat_home_failure_unreachable`,
  `chat_home_failure_service`, `chat_home_retry` shipped byte-for-byte from the spec (verified with
  an XML parse + string comparison); `chat_home_working`, `chat_home_question_too_long`,
  `chat_home_needs_land_clarification`, `chat_speaker_you`/`chat_speaker_assistant` and
  `land_list_retry` are unchanged.
- `CONSTRAINTS.md`: new "Client request failure" MUST rule (a failed/unreached request is never an
  answer and recovery keeps the exact wording). `docs/specs/network_error_recovery.md`: four
  implementation findings (IF1-IF4). `docs/specs/chat_question_submission.md`: F2 recorded as closed
  from this side, F1 still owned by the `/ask` wiring slice.
- Not changed: `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`,
  `theme/`, any Gradle file or the version catalog, and `init.sh`; no new module, dependency, engine
  wiring, base URL, ViewModel, DI, or coroutine scope (Ktor `HttpTimeout` ships in `ktor-client-core`).

Verification (commands run from the repository root unless noted):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests
  "com.jamarglex.manijero.ChatConversationTest" --tests
  "com.jamarglex.manijero.chat.KtorAnswerServiceTest"` → BUILD SUCCESSFUL, 40 tests / 0 failures.
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **78 tests / 0 failures**
  (`ChatHomeStateTest` 25, `ChatConversationTest` 7, `KtorAnswerServiceTest` 8, plus the 38
  pre-existing).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **69 tests / 0 failures**.
- `./gradlew :desktopApp:build` and `./gradlew :androidApp:assembleDebug` → BUILD SUCCESSFUL
  (`androidApp-debug.apk` rebuilt); `./init.sh --verify` → BUILD SUCCESSFUL.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL, so the new `commonMain`
  Ktor/kotlinx-io usage does not break the pre-existing iOS target.
- Timeout evidence (carried finding R1 fallback): `HttpClient.plugin(HttpTimeout)` is not readable as
  a config in Ktor 3.1, so the test asserts installation (a missing plugin throws), that the three
  named constants are finite and differ from `HttpTimeoutConfig.INFINITE_TIMEOUT_MS`, and a stalled
  `MockEngine` with `requestTimeoutMillis = 200` fails in ~0.3 s as
  `AnswerServiceUnavailableException` instead of hanging. `expectSuccess` is proven behaviourally (a
  `500` carrying the accepted `answered` fixture body and a declared `422` both fail; the accepted
  `200` fixture still decodes on the same client), and an undecodable `200` body fails too.
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, rebuilt debug APK, shipped default
  `UnavailableAnswerService`): selecting an example and pressing `Preguntar` shows one `Tú` bubble
  with the exact question, **no** `Asistente` answer, the service-error notice
  ("El servicio no está disponible en este momento, así que todavía no tengo tu respuesta. Inténtalo
  otra vez dentro de un momento.") in the danger colours with a red `Reintentar`, and the exact
  wording still in the composer; `Reintentar` returns to the same single-notice state with still
  exactly one user message and no duplicate; selecting another example clears the notice and refills
  the composer. Screenshots were inspected and deleted.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src
  desktopApp/src` → no matches (exit 1). The new exception messages are fixed literals and the Ktor
  messages (which name the endpoint) are never rethrown, logged, or shown; no network call other than
  the existing `POST /ask` was added.

Honest gaps:

- A live network timeout cannot be produced in the running apps until platform `/ask` engine/endpoint
  wiring exists (carried finding F1, separate owner). The `COULD_NOT_REACH_SERVICE` notice therefore
  has no on-device screenshot; it is covered by the `MockEngine` timeout probe, the installed-constant
  assertions, and the reducer/transport tests.
- The Desktop app launched the shared UI (`MainKt` frontmost, no exception in the run log) but an
  interactive Desktop click-through/screenshot of the notice was not captured in this non-interactive
  session.
- No Compose UI-test harness exists, so no automated UI or E2E coverage is claimed; the observable
  working state during a retry is too brief to capture on the default path (`UnavailableAnswerService`
  throws synchronously).
- Recorded behaviour: `RetryClicked` clears the composer as specified, so a draft typed during the
  failed request and left unsent is discarded by an explicit retry; the person can instead press
  `Preguntar` with that draft, which dismisses the notice (spec finding IF1).
Independent validation (2026-10-13): accept. The validator re-ran the acceptance checks with
`--rerun-tasks` (contract validator; focused three-class run 40/0; `:shared:jvmTest` 78/0;
`:shared:testAndroidHostTest` 69/0; `:desktopApp:build`; `:androidApp:assembleDebug`;
`:shared:compileKotlinIosSimulatorArm64`; `./init.sh --verify` exit 0) and independently
reproduced the stalled-`MockEngine` request timeout (200 ms bound fired in 0.209 s as the
unavailable signal), the `500`/`422` and undecodable-`200` service-error paths with the `200`
fixtures still decoding, byte-for-byte equality of the three spec strings, the
failure-never-renders-as-an-answer invariant, retry with no duplicate user message and exact
wording retention, and scope discipline (no new module/dependency/Gradle/contract/backend/land/
theme/`init.sh` change). It confirmed on the resolved `kotlinx-io-core-jvm` artifact that
catching `kotlinx.io.IOException` also catches `java.io.IOException` and its timeout subclasses,
so real unreachable-service failures map to the correct notice, and found no leak. Non-blocking
findings N1-N5 recorded; F1 (platform `/ask` engine/endpoint wiring) stays with its own slice and
F2 (bounded timeout) is closed from this side. Record:
`docs/validations/network_error_recovery.md`.

### edit_land — accepted

Feature: `edit_land` (`area: lands`). Spec: `docs/specs/edit_land.md`. Accepted by independent
validation (record: `docs/validations/edit_land.md`); the implementation and self-verification below
were produced by the implementer and are reproduced/confirmed by the validator.

Independent validation (accept): re-ran `./init.sh`, the focused three-class run (`20/0`), the full
`:shared:jvmTest --rerun-tasks` (**98/0**, 14 classes), `:shared:testAndroidHostTest --rerun-tasks`
(**87/0**, 11 classes), `./init.sh --verify`, and a full `--rerun-tasks` build (91 tasks, 0 from
cache); confirmed the accepted `add_land`/`land_list` suites and copy still pass and the `Editar`
affordance did not regress the non-clickable row. For the literal feature-list verification it wrote
and then deleted an independent scratch JVM probe against the real `FileLandStorage`: with two lands
saved and only the first edited, the snapshot's other record line was **byte-identical**, order
preserved, and the edited record kept its `id`/`createdAt`; it also reproduced the byte-identical
no-write on a `LAND_MISSING` (`null`) update, the blank-name no-draft/no-write path, the
emptied-municipality→absent and known→`UNKNOWN` round-trips, and the preserved `area`/`notes`. The
eight new Spanish strings and the `CONSTRAINTS.md` rule were checked byte-for-byte, `git diff --check`
was made clean, and six emulator screenshots were corroborated against the behavior. Non-blocking
findings: F1 (the implementer's `PROGRESS.md` trailing blank line, fixed here before the acceptance
commit), F2 (a spec sentence overstated the `Cancelar` re-read; the spec now matches the code and the
accepted `add_land` cancel path), F3 (no Compose UI-test harness, so the `App()` save-decision wiring
is inspection + smoke only), F4 (`LAND_MISSING` is a defensive/unit-tested branch), F5
(`updatedAtEpochMillis` still not meaningful — carried `land_list` F6), F6 (the interactive Android
smoke is implementer-produced; the validator corroborated the artifacts and code semantics).

What changed (implementer record):

- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandState.kt` (pure, no Compose
  or platform imports): `EditLandFailure { WRITE_FAILED, LAND_MISSING }`, `EditLandState` (the
  targeted `landId`, raw `name`/`municipality` text, the two enums, plus `preservedAreaHectares`
  and `preservedNotes` carried through because this short form neither collects nor shows them),
  `Land.toEditLandState()` (prefills verbatim, `null` municipality → empty field, `UNKNOWN` → the
  `No lo sé` choice), field/save/failure actions, `reduce` (field actions and `SaveClicked` clear a
  stale failure; `SaveFailed` only sets it), and `toDraftOrNull()` (blank trimmed name → `null`;
  emptied municipality → absent; trimmed name; area/notes preserved).
- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`: stateless
  prefilled form that renders whatever state it gets, with the required name field (error state plus
  `Escribir un nombre…`), the optional municipality, the two accessible radio groups, a polite
  live-region failure message that distinguishes `WRITE_FAILED` from `LAND_MISSING`, one primary
  `Guardar cambios`, `Cancelar` as the visible back control, and 9 previews (prefilled name-only,
  known values, name error, write failure, missing land, long text, compact 320dp, wide 900dp, 2x
  font). It reuses the accepted `add_land_*` vocabulary and the shared `ChoiceGroup`/`ChoiceItem`.
- `LandListScreen.kt`: `onEditLand: (Land) -> Unit` added, `savedConfirmation: Boolean` replaced by
  `confirmation: LandListConfirmation?` with `enum class LandListConfirmation { ADDED, UPDATED }`
  (`ADDED` still renders `add_land_saved` byte-for-byte), per-row visible `Editar` button whose
  accessible description is `land_list_edit_description` with the land's exact saved name, the row
  card still non-clickable, the details still a merged descendant node, plus a "just updated"
  preview.
- `AddLandScreen.kt`: `ChoiceGroup`/`ChoiceItem` visibility only, `private` → `internal`.
- `App.kt`: `EditLand` destination, `editLandState: EditLandState?` and
  `landConfirmation: LandListConfirmation?`, the row edit action, and the single
  `repository.update(reduced.landId, draft)` call site inside the `SaveClicked` branch (never while
  composing, never at startup). A non-null result clears the edit state, sets `UPDATED`, re-reads the
  list, and returns; `null` shows the `LAND_MISSING` notice and a thrown failure shows
  `WRITE_FAILED`, both keeping the values on screen and navigating nowhere. `Cancelar` clears the
  state, returns to the list, and shows no confirmation. `App()` (no argument) is unchanged.
- `shared/src/commonMain/composeResources/values/strings.xml`: the eight new keys from the spec.
- New tests: `commonTest/.../EditLandStateTest.kt` (12), `commonTest/.../EditLandRepositoryTest.kt`
  (6, in-memory `LandStorage` fake), `jvmTest/.../EditLandDesktopStoreTest.kt` (2, real
  `FileLandStorage` in a temp dir).
- `CONSTRAINTS.md`: new "Land editing" MUST rule (one targeted record, untouched attributes carried
  through, preserved `id`/`createdAt`, no `create`/`delete` from an edit path, never report
  `null`/thrown as saved).

Commands actually run (repository root):

- `./init.sh` → exit 0 (Gradle 9.8.0 wrapper; `local.properties` present, so Android checks run).
- `./gradlew :shared:jvmTest --tests EditLandStateTest --tests EditLandRepositoryTest --tests
  EditLandDesktopStoreTest` → BUILD SUCCESSFUL; 20 tests / 0 failures
  (`EditLandStateTest` 12, `EditLandRepositoryTest` 6, `EditLandDesktopStoreTest` 2).
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; **98 tests / 0 failures** across 14 classes (was
  78). The accepted `add_land`/`land_list` suites are still green (`AddLandStateTest` 11,
  `LandListStateTest` 6, `LandRepositoryTest` 4, `AddLandDesktopStoreTest` 1).
- `./init.sh --verify` (`:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`) → BUILD SUCCESSFUL (exit 0); `androidApp-debug.apk` produced;
  `:shared:testAndroidHostTest` **87 tests / 0 failures** across 11 classes (was 69).
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build --rerun-tasks` → BUILD SUCCESSFUL, 91 tasks executed; same 98/0 and 87/0.
- Copy fidelity: a Python byte-for-byte comparison of the spec's XML block against
  `strings.xml` matched all eight new keys exactly, each appearing once; `land_list_edit_description`
  is used only as the `Editar` control's accessible description and never as body text.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out" shared/src` → no matches;
  no network call, permission, dependency, module, ViewModel, coroutine, or navigation framework was
  added (`strings.xml` + `shared/src` are the only product edits).
- `git diff --check` → clean.

Android emulator smoke (`Medium_Phone_API_35`, API 35, 1080x2400, fresh install + `pm clear`,
16 screenshots captured outside the repository):

1. `Mis terrenos` empty → `Añadir terreno` → saved `Los Olivos` (name only): the list shows the
   unchanged add confirmation, `Riego: No lo sé`, `Producción: No lo sé`, no `Municipio:` line, and a
   visible `Editar` whose node reads `Editar el terreno «Los Olivos»`. Saved `La Loma` with
   `Municipio: Martos`, `Regadío`, `Ecológico` → a second distinguishable row in creation order.
2. The row body is not clickable: tapping `La Loma alta` text left the screen on the list.
3. Editing `Los Olivos` only (prefilled form shows `Los Olivos`, empty municipality, and `No lo sé`
   selected in both groups) and typing `Los Olivos del camino` → back to the list with
   `Los cambios se han guardado en este dispositivo.` visible (polite live region), the corrected name
   in the **same first position**, and `La Loma` still showing `Municipio: Martos` / `Regadío` /
   `Ecológico`.
4. Editing `La Loma` (prefill confirmed: `Martos`, and the `checked` rows are exactly `Regadío` and
   `Ecológico`) → cleared the municipality and selected `No lo sé` in both groups → the row lost its
   `Municipio:` line and reads `No lo sé` for both, with the other land untouched.
5. `am force-stop` + relaunch → both records persist exactly as shown, no duplicates, no stale
   confirmation.
6. Blank name: cleared the name and saved → no navigation, no confirmation, the required message
   `Escribe un nombre para el terreno.` appeared, and the other edited values stayed on screen;
   correcting it to `La Loma alta` saved successfully.
7. `Cancelar` from a further edit with an edited name → returned to the list with no confirmation and
   the stored name unchanged.
8. `font_scale 2.0`: the list and the edit form wrap with no horizontal overflow (max text right edge
   1017 of 1080) and `Guardar cambios` / `Cancelar` are reachable by vertical scroll.

Desktop `:desktopApp:run` startup smoke: the app launched `com.jamarglex.manijero.MainKt` against the
injected `~/.manijero/lands-v1.txt` store and stayed running ~6.5 minutes with **0 exceptions** in the
run log until the session stopped it (`:desktopApp:run` then reported the expected non-zero exit 143 =
SIGTERM). Interactive Desktop clicking, keyboard-focus traversal, and window-resize checks were not
driven in this session.

Honest gaps:

- No Compose UI-test harness exists, so the `App()` save-decision wiring (the `LAND_MISSING` /
  `WRITE_FAILED` branches, the confirmation, and the re-read on return) is verified by code
  inspection plus the emulator smoke, not by an automated test. The reducer and the repository
  semantics are covered by the focused tests.
- The two failure branches are reachable only defensively (`LAND_MISSING` needs the record to vanish
  between the list read and the save), so they were unit-tested rather than reproduced on the
  emulator.
- Screen-reader behaviour (merged row details, the `Editar` description announcement) and
  low-digital-confidence usability were not verified; the spec defers that validation to
  `land_form_accessibility`.
- No persistent E2E command exists, so no E2E or automated UI coverage is claimed.
- `updatedAtEpochMillis` is still not meaningful: `update` receives no timestamp from the app
  because the project has no clock/date dependency (carried finding F6 from `land_list`).
- As the spec records, `area`/`notes` are preserved but neither shown nor editable from this form,
  and two identical-looking lands still rely on the prefilled name to tell them apart.

### response_states — accepted

What changed (all in shared `commonMain`):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatMessage` gains
  assistant-only `answerStatus: AnswerStatus = AnswerStatus.answered`, documented as copied from the
  decoded `AskResponse.status`. `ResponseReceived` — the only assistant-entry creation site — passes
  `response.status` into the entry, so every assistant entry keeps the state it arrived with and
  rendering never depends on the mutable `lastResponseStatus` (which still drives only
  `awaitingLandClarification`). The non-empty-answer guard and the clarification path are unchanged.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatMessageBubble` renders from
  `speaker` + `answerStatus` through an exhaustive `when`; `ChatBubble` gains defaulted
  `borderColor`/`stateLabel`/`stateLabelColor` (existing call sites unchanged) plus a private neutral
  `ChatAssistantCard` helper. The answered entry keeps the neutral `surface`/`outlineVariant`
  `Asistente` card (no confident affordance); the abstained entry uses
  `LocalManijeroSemanticColors.cautionSurface` for the fill, a `caution` border, the `Asistente` label
  in `onSurfaceVariant`, a visible `Sin respuesta segura` label in `caution`, and the verbatim body in
  `onSurface` — one merged semantics node and a `LiveRegionMode.Polite` region. `needs_land_clarification`
  stays a neutral card (defensive, exhaustive). Four new previews (answered, abstained, both states
  together, abstention at `widthDp = 320`/`fontScale = 2f`), all inside `ManijeroTheme`.
- `shared/src/commonMain/composeResources/values/strings.xml`: one added string,
  `chat_answer_state_abstained` = `Sin respuesta segura` (byte-for-byte equal to the spec); no existing
  string changed or deleted (`chat_home_submitted` left untouched).
- The server `answer` is rendered verbatim, so the code-owned lead-in/orientative notice is not
  duplicated and no source, marker, figure, date, land name, or client-authored next step is added. The
  client does not branch on an abstention reason: `AskResponse` is `additionalProperties: false` with
  five keys, so no reason reaches the client and all nine reasons share the one state label.
- `CONSTRAINTS.md`: new "Client response states" MUST rule (answer/abstention stay distinguishable, the
  per-entry `answerStatus` is copied from the decoded response, an abstention renders its code-owned
  message verbatim with a non-confident caution treatment and no added content, no answer gains a
  confident legal-certainty treatment).
- Not changed: `contracts/`, `backend/`, `knowledge/`, `lands/`, `androidApp/`, `desktopApp/`,
  `shared/src/iosMain/`, the theme source values (`theme/ManijeroColors.kt`/`ManijeroTheme.kt`), any
  Gradle file or the version catalog, and `init.sh`; no new module, dependency, endpoint, engine,
  navigation, ViewModel, DI, or coroutine scope.

Verification (commands run from the repository root):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --tests "…ChatHomeStateTest" --tests "…ChatConversationTest" --tests
  "…theme.ManijeroColorsTest"` → BUILD SUCCESSFUL, 46 tests / 0 failures.
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL, **82 tests / 0 failures** (was 78; `ChatHomeStateTest`
  25→28, `ChatConversationTest` 7→8, plus one `ManijeroColorsTest` contrast row).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **73 tests / 0 failures** (was 69; +4).
- `./gradlew :desktopApp:build :androidApp:assembleDebug` → BUILD SUCCESSFUL (`androidApp-debug.apk`
  rebuilt); `./init.sh --verify` → BUILD SUCCESSFUL; `./gradlew :shared:compileKotlinIosSimulatorArm64`
  → BUILD SUCCESSFUL.
- New tests: an answered response appends exactly one assistant entry carrying `answered`; an abstained
  response carries `abstained` with the pinned message verbatim; an earlier abstention keeps its state
  after a later answered reply (per-entry, not `lastResponseStatus`); the clarification test asserts no
  assistant entry; a fake `AnswerService` returning the accepted abstained shape through
  `ChatConversation` yields one user message, one assistant entry carrying `abstained`, the pinned
  message verbatim and no `failure`; one `ManijeroColorsTest` row asserts `onSurface` on
  `cautionSurface` = 14.58:1.
- Centralization/privacy: `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero`
  matches only under `theme/`; `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src
  androidApp/src desktopApp/src` → no matches (exit 1).

Honest gaps:

- No rendered visual evidence: this is a non-interactive session with no Compose preview/UI-test
  runner, so the greyscale non-colour-cue check and the `widthDp = 320`/`fontScale = 2f` no-clipping
  claim are structural + compiled-preview based, not an inspected render. Owner: `chat_accessibility`.
- No on-device answered/abstained turn: the shipped default is `UnavailableAnswerService` and there is
  still no platform `/ask` route (carried finding F1), so a real turn would need a temporary
  non-committed fake; `:desktopApp:run` interactive smoke was not run. No E2E or automated UI coverage
  is claimed (none exists).
- Carried risk R5: `[1]`-style markers render verbatim until `answer_source_cards` ships cards; with
  the corpus still empty no real marker-bearing answer exists yet.

Independent validation (2026-10-13): accept. The validator re-ran the contract validator,
`:shared:jvmTest --rerun-tasks` (82/0), `:shared:testAndroidHostTest --rerun-tasks` (73/0),
`:desktopApp:build :androidApp:assembleDebug --rerun-tasks` (72 tasks, exit 0), `./init.sh --verify`
(exit 0), `:shared:compileKotlinIosSimulatorArm64`, the two greps, and `git diff --check`; it
recomputed the `onSurface`-on-`cautionSurface` pair independently (14.58) and byte-for-byte compared
the new string. It reproduced the per-entry behavior with its own temporary probe test (10 tests,
including an earlier abstention surviving a later answer while `lastResponseStatus` differs, a
mismatch-proof hand-built state, clarification appending no entry, and a failure never becoming an
answer) and confirmed the exhaustive speaker × status branch in `App.kt`, verbatim body rendering with
no added source/marker/figure/date/client next step, and the three distinct neutral/caution/danger
states. Scope confirmed clean with no logging. Non-blocking findings N1-N5 recorded (N1 closed here at
acceptance time; N2 rendered-evidence gap owned by `chat_accessibility`). Record:
`docs/validations/response_states.md`.
