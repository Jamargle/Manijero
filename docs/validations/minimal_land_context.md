# Validation — `minimal_land_context`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`minimal_land_context` implementation against `docs/specs/minimal_land_context.md`.

Feature id: `minimal_land_context`. Spec: `docs/specs/minimal_land_context.md`.
Claimed status: `passing` (self-verified by the implementer). State update: the
orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair the feature; it re-ran the acceptance
checks, read the diff, and independently reproduced the literal feature-list
verification with its own temporary probe test (created, run, and deleted before
returning).

## Review target

`git status --short` before and after validation showed exactly the expected
footprint (unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`.
- New (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt`.
- Modified (tests): `ChatConversationTest.kt`, `ChatHomeStateTest.kt`,
  `shared/src/jvmTest/kotlin/com/jamarglex/manijero/chat/KtorAnswerServiceTest.kt`.
- New (tests): `shared/src/commonTest/kotlin/com/jamarglex/manijero/chat/LandContextBuilderTest.kt`.
- Modified (docs): `CONSTRAINTS.md`, `docs/specs/chat_question_submission.md`.
- New (docs): `docs/specs/minimal_land_context.md` (planner artifact).

Untouched: `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`,
`shared/src/commonMain/composeResources/values/strings.xml`, `shared/src/iosMain/`,
`androidApp/`, `desktopApp/`, every Gradle file and the version catalog, and
`init.sh`. `git diff --check` clean. No new module, dependency, endpoint,
permission, ViewModel, navigation, coroutine API, or logging.

## Literal verification (independently reproduced)

The validator wrote its own throwaway probe
(`shared/src/jvmTest/.../ValidatorProbeTest.kt`, deleted before returning) that
drives the real `ChatConversation` with a `landsProvider` over a **real
`FileLandStorage`/`LandRepository`** store (so the land records genuinely carry
names, notes, area, and timestamps) and captures the encoded body at the
transport boundary. Bodies reproduced:

```
water:      {"question":"¿Puedo regar hoy?","land_context":{"mode":"all_active","lands":[{"id":"land-1","water_regime":"irrigated"},{"id":"land-2","water_regime":"unknown"}]}}
no-vocab:   {"question":"¿Cuál es el plazo de la solicitud única?","land_context":{"mode":"all_active","lands":[{"id":"land-1"},{"id":"land-2"},{"id":"land-3"}]}}
no lands:   {"question":"¿Puedo regar hoy?","land_context":{"mode":"general","lands":[]}}
production: {"question":"¿Puedo producir en ecológico?","land_context":{"mode":"all_active","lands":[{"id":"land-1","production_method":"conventional"}]}}
retry:      {"question":"¿Puedo producir en ecológico?","land_context":{"mode":"all_active","lands":[{"id":"land-1","production_method":"conventional"},{"id":"land-2","production_method":"unknown"}]}}
municipality: {"question":"¿Cuál es mi término municipal?","land_context":{"mode":"all_active","lands":[{"id":"land-1","municipality":"Martos"},{"id":"land-2","municipality":"Martos"}]}}
blank muni: {"question":"¿Cuál es mi término municipal?","land_context":{"mode":"all_active","lands":[{"id":"land-1"}]}}
throwing provider: {"question":"¿Puedo regar hoy?","land_context":{"mode":"general","lands":[]}}   (no failure)
```

Confirmed: relevant attribute(s) only, ids verbatim, repository order, **no**
`name`/`notes`/`areaHectares`/timestamps/contract-unknown keys, `unknown` for a
needed-but-unknown value, unset/blank municipality omitted, ids-only for
no-vocabulary questions, byte-identical accepted `general` payload with no lands,
and a land added during the failure notice picked up by the retry.

## Independent checks and results

Re-run by the validator (with `--rerun-tasks` where relevant) so results are real
executions, not cached `UP-TO-DATE` output:

| Check | Result |
|---|---|
| `python3 contracts/validate_examples.py` | exit 0 — "Validated 2 request and 3 response examples" |
| `./gradlew :shared:jvmTest --rerun-tasks` | **162 tests / 0 failures** (19 classes; `LandContextBuilderTest` 13, `ChatConversationTest` 13, `KtorAnswerServiceTest` 9, `ChatHomeStateTest` 31) |
| `./gradlew :shared:testAndroidHostTest --rerun-tasks` | **148 tests / 0 failures** |
| `./gradlew :shared:compileKotlinIosSimulatorArm64 :desktopApp:build :androidApp:assembleDebug --rerun-tasks` | BUILD SUCCESSFUL, 76 tasks executed; APK 35,865,622 bytes (matches the claim byte-for-byte) |
| `./init.sh --verify` | exit 0 (91 tasks) — it really executes the checks |
| `git diff --check` | clean |
| Logging grep (`println\|Log\.\|Logger\|printStackTrace\|NSLog\|System\.out` in `shared/src androidApp/src desktopApp/src`) | no matches (re-checked after probe deletion) |
| `Color(0x` outside `theme/` | none |
| Own Desktop smoke (`:desktopApp:run`) | process alive ~45 s, no exception/stack trace; nothing submitted on startup |

No test removed: HEAD-visible `@Test` = 144 → 162 (+18 = 13 + 4 + 1 exactly),
verified by annotation count and by the executed XML counts.

The vocabulary is identical to the spec's pinned table (water 26, production 27,
municipality 13; no duplicates, every term ≥ 4 chars), checked by a scripted set
comparison.

## Findings (all non-blocking)

- **N1 (highest priority follow-up).** No bound on `municipality` length although
  the contract declares `maxLength: 160` (and `id` 128). The validator's probe
  sent a 200-char municipality verbatim (`sentLength=200`). The trigger lives in
  the accepted `add_land`/`edit_land` form (no input limit); the consequence is
  only a visible, recoverable failure notice from a real `/ask` (→ 422) — no
  privacy leak, no wrong answer. Recommended follow-up (own spec line): bound the
  municipality field at ≤ 160, or in `minimalLandContext` treat an over-long value
  as not sendable (omit) with a comment and a test. Do **not** silently truncate.
- **N2.** `ChatConversation(landsProvider = { emptyList() })` defaults to no lands,
  so a future composition root that forgets wiring silently degrades to
  `general`. Direction is conservative (less data) and the spec chose the default
  deliberately; when `answer_land_scope` makes scope visible, consider making it a
  required parameter.
- **N3.** `runCatching { landsProvider() }` would also swallow a
  `CancellationException` thrown by a provider; unreachable with today's
  synchronous read, but rethrow `CancellationException` if a provider ever
  suspends.
- **N4 (carried).** `init.sh --check` banner text is stale (spec mandates no
  `init.sh` change).
- **N5 (carried `chat_question_submission` F1).** `/ask` is still unrouted
  (`backend/app/main.py` exposes only `/health`) and no persistent E2E harness
  exists, so the transport-level encoded-body capture is the honest automated
  equivalent; no on-device network evidence is claimed. No Android emulator smoke
  was run (no UI change in this feature).

## Scope, architecture, privacy

- `git status --porcelain` matched the spec's expected file set exactly.
  `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, `strings.xml`,
  platform entry points, all Gradle files, and `init.sh` are untouched;
  `AnswerService.kt` is unmodified (DTOs, `answerJson`, `generalAskRequest`
  behaviorally and byte-for-byte unchanged).
- Policy is a pure, Compose-free builder in `commonMain` with an explicit lands
  parameter at the effect boundary (`ChatEffect.request(lands)`), keeping the
  reducer pure and making the lands impossible to forget; the enum mapping is an
  exhaustive `when` with no `else`.
- Privacy: payload = opaque id + only the needed attributes; the read is unlogged;
  failure signals are payload-free; land data is never stored in UI state; no new
  permission, dependency, endpoint, telemetry, or third party. A scoped security
  review of the diff found no blocking issue.

## Documentation / harness state

`CONSTRAINTS.md` gained one operational MUST rule (ids + needed attributes only;
never name/note/area/timestamp/invented value; omit or `unknown`, never guess;
`general` only when empty; no silent vocabulary change) with its reason. The
`chat_question_submission.md` supersession note is present and accurate.
`docs/risks-and-open-questions.md` and `AGENTS.md`/`CONTEXT.md`/`domain-model`/
`DESIGN.md`/`MasterPlanV3.md` are untouched as the spec required, and no
`ARCHITECTURE.md` was created. `feature_list.json` (`passing`, real evidence) and
`PROGRESS.md` reflect real evidence only.

## Required follow-up / state update

1. Orchestrator: set `minimal_land_context` to **`accepted`** in
   `feature_list.json` and this record; add the acceptance line to `PROGRESS.md`.
2. Carry **N1–N5** as recorded non-blocking findings (N1 owner: a lands-form/builder
   follow-up; N2/N3 owners: `answer_land_scope` / any future suspending provider;
   N4–N5 carried).
3. No repair brief is required; no commit was made by the validator.
