# Feature Spec: `minimal_land_context`

## Source metadata

- **Feature:** `minimal_land_context` — Use minimal land context (`lands-chat`)
- **Status at planning:** `not_started`; depends on accepted `land_list`, `chat_question_submission`,
  and `answer_api_contract` (all three are `accepted`, so the feature is dependency-ready).
- **Source behavior:** For a land-relevant question, the app supplies all active lands by default
  using only the attributes needed for that question.
- **Feature verification:** Inspect a request for a land-relevant question and confirm it contains
  relevant attributes without names or free-text notes by default.
- **Note:** a general question must remain usable when no land is configured.

## Goal and boundaries

Fill in the one part of `POST /ask` that the accepted client deliberately left as `general` /
empty: build the request's `land_context` from the lands saved on the device. Every submission
must carry **all** stored lands, identified by their opaque local id, with only the optional
attributes the question actually needs, and **never** a name, free-text note, area, or timestamp.

**In scope**

- One pure, testable request builder in `commonMain` that maps the current `List<Land>` into the
  accepted `LandContext`/`MinimalLandContext` DTOs.
- The mode decision: `all_active` with every stored land, or `general` with an empty list when no
  land exists.
- The attribute decision: per-question, deterministic inclusion of `municipality`,
  `water_regime`, and `production_method` (pinned vocabulary below); everything else omitted.
- A fresh land read **at submit time** (submit and retry), so a land added, edited, or removed
  after the chat screen opened is reflected in the next request.
- Preserving the accepted behavior exactly when no land is configured, and never rewriting the
  person's original wording.

**Non-goals**

- Sending land selection, `needs_land_clarification` handling, or a land chooser
  (`land_clarification` owns them); the accepted neutral clarification acknowledgement is unchanged.
- Displaying the land scope of an answer (`answer_land_scope`), the land-data disclosure notice
  (`land_data_disclosure`), or any new UI, string, preview, or layout. This feature adds **no**
  visible control and **no** copy.
- Backend work: no `/ask` route, no applicability matching of passages against land attributes
  (`MasterPlanV3.md` B13), no retrieval/generation/abstention change, and no `contracts/` change.
  B13's "clarification-needed when context changes the answer" belongs to `land_clarification`.
- An "active/archived" flag, land detail screens, search/sort/dedupe, telemetry, cloud, accounts,
  or a new module, dependency, ViewModel, or navigation framework.

> **Follow-up (`land_clarification`, implemented):** land selection and
> `needs_land_clarification` handling are now owned by `docs/specs/land_clarification.md`. The
> `all_active` builder here is unchanged; a `selected` resubmission reuses `minimalLandContext` and
> `landContextNeeds`, so only the needed attributes are still sent.

## Job story

When I ask a question that depends on my lands, I want the app to add the lands I saved and the
details that matter for that question, so the answer can be about my grove without my names, notes,
or private farm details being sent anywhere.

## Acceptance scenarios

### A land-relevant question carries all lands and the needed attributes

Given two lands are stored locally (`land-1`: municipality `Martos`, `IRRIGATED`, `ORGANIC`;
`land-2`: name only, attributes unknown), when the person submits `¿Puedo regar hoy?`, then the
`AskRequest` has `land_context.mode: all_active`, carries exactly those two lands in repository order
with their ids verbatim, and gives each land `water_regime` (`irrigated` for `land-1`, `unknown` for
`land-2`); `municipality` and `production_method` are absent for both, and no `name`, `notes`, or
`areaHectares` appears anywhere in the encoded body.

### Only the attributes the question needs are sent

Given a stored land with known municipality, water, and production, when the person submits a
question about ecological production then only `production_method` is included; a question about a
place (`municipio`, `provincia`, `comarca`…) includes only `municipality`; a question matching no
attribute vocabulary (for example the plazo of the solicitud única) carries the land id and no
optional attribute.

### Unknown is not "not needed", and nothing is invented

Given a stored land whose water regime is `UNKNOWN` and whose municipality is unset, when the person
submits a water question and then a municipal one, then the land carries `water_regime: unknown`
(never a guess) and omits `municipality` rather than sending a placeholder, `""`, or a name.

### A general question stays usable with no land configured

Given no land is stored, when the person submits any question, then the request is exactly the
accepted `general` / `lands: []` payload with the original wording, and submission, retry, failure,
and response presentation behave exactly as accepted today.

### The current lands are used at submit time

Given a land was added, edited, or removed after the chat screen was opened, when the question is
submitted, then the request uses the lands stored **at that moment**; a retry re-reads that same
current list.

## Repository research

Inspected:

- `shared/src/commonMain/.../chat/AnswerService.kt`: `AskRequest`/`LandContext`/`MinimalLandContext`
  already match `contracts/openapi.yaml`; `answerJson` uses `explicitNulls = false`, so omitting an
  attribute means leaving it `null`; `generalAskRequest(question)` is the accepted `general` builder.
  No DTO or transport change is required.
- `ChatHomeState.kt`: pure reducer; `ChatEffect.Submit(question)` carries only the wording and
  `ChatEffect.request()` maps it with `generalAskRequest`. `ChatConversation.kt` is the only caller of
  `answerService.ask`, runs the single in-flight submission on the injected composition scope, maps
  failures to payload-free signals, and never logs — the natural place to read lands and build.
- `App.kt`: `App(landRepository, answerService)` already receives the one local `LandRepository`, the
  conversation is created in a `remember`, and the no-argument `App()` (iOS scaffold, previews) has no
  repository. `ChatHomeScreen` takes no land parameters today.
- `lands/Land.kt`, `lands/LandRepository.kt`: `Land(id, name, municipality, waterRegime,
  productionMethod, areaHectares, notes, timestamps)`; `list()` is synchronous, returns repository
  order, never sorts or dedupes, and normalizes blank municipality/notes to `null`; ids are locally
  generated opaque strings; there is no archive flag, so "active" means every stored land.
- `contracts/openapi.yaml`: `MinimalLandContext` = `id` (required, opaque, ≤128), `municipality`
  (≤160), `water_regime`, `production_method`, `additionalProperties: false`; omission "means the
  attribute is not needed for this question, not that it is known".
- Tests and checks: `ChatHomeStateTest` (asserts `general`/empty for a no-lands submit),
  `ChatConversationTest` (`ChatConversation(service, scope)`), `jvmTest/.../chat/KtorAnswerServiceTest`
  (MockEngine body capture); `./init.sh --verify`, `:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:shared:compileKotlinIosSimulatorArm64`, Android/Desktop builds. No persistent E2E runner exists and
  there is still no `/ask` route (carried `chat_question_submission` F1).
- `knowledge/README.md` (land-based selection deferred to `minimal_land_context` /
  `land_clarification`), `docs/domain-model.md` (all lands by default, unknown stays unknown, minimum
  attributes, avoid names/notes), `CONTEXT.md`, `docs/build-brief.md`,
  `docs/risks-and-open-questions.md`, `MasterPlanV3.md` (B13 applicability, D13), and `CONSTRAINTS.md`
  (one short MUST rule per accepted boundary).

## Technical approach

1. **New pure builder** `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt`
   (package `chat`), standard-library only and Compose-free:
   - `data class LandContextNeeds(val waterRegime: Boolean, val productionMethod: Boolean, val municipality: Boolean)`
   - `fun landContextNeeds(question: String): LandContextNeeds`
   - `fun minimalLandContext(land: Land, needs: LandContextNeeds): MinimalLandContext`
   - `fun landContextFor(question: String, lands: List<Land>): LandContext`
   - `fun askRequestFor(question: String, lands: List<Land>): AskRequest`
   - `generalAskRequest` stays as-is and is the `lands.isEmpty()` branch, so the accepted payload is
     byte-identical for the no-land case.
2. **Mode decision.** `all_active` whenever at least one land is stored (domain model rule 1: all
   active lands by default, and the service needs the ids to answer or to ask for a choice later);
   `general` with `lands: []` only when the list is empty. No topic classifier gates the mode: a
   missed keyword must never silently drop the lands, and a question that needs no attribute still
   sends ids only.
3. **Attribute decision (pinned).** A dimension is *needed* when the folded question text contains
   one of that dimension's terms as a whole token:

   | Dimension | Terms (folded, exact token match) |
   |---|---|
   | `water_regime` | `agua`, `aguas`, `riego`, `riegos`, `riega`, `riegan`, `regar`, `regado`, `regando`, `regadio`, `secano`, `secanos`, `goteo`, `aspersion`, `aspersiones`, `drenaje`, `lluvia`, `lluvias`, `sequia`, `sequias`, `humedad`, `pozo`, `embalse`, `balsa`, `canal`, `acequia` |
   | `production_method` | `ecologico`, `ecologica`, `ecologicos`, `ecologicas`, `convencional`, `convencionales`, `integrada`, `integrado`, `produccion`, `producciones`, `organico`, `organica`, `organicos`, `organicas`, `fertilizante`, `fertilizantes`, `fertilizacion`, `abono`, `abonos`, `fitosanitario`, `fitosanitarios`, `plaga`, `plagas`, `herbicida`, `herbicidas`, `pesticida`, `pesticidas` |
   | `municipality` | `municipio`, `municipios`, `termino`, `terminos`, `provincia`, `provincias`, `comarca`, `comarcas`, `localidad`, `localidades`, `pueblo`, `ayuntamiento`, `andalucia` |

   Folding is `lowercase` plus a fixed character table (`á à ä â→a`, `é è ë ê→e`, `í ì ï î→i`,
   `ó ò ö ô→o`, `ú ù ü û→u`, `ñ→n`); tokens are maximal runs of letters/digits. A term shorter than
   four characters is not allowed in the table (this is why whole tokens are used instead of
   substring matching: `agua` must not match `aguacate`).
4. **Attribute inclusion rules.** If a dimension is needed: send the mapped value, and send
   `unknown` when the stored value is `UNKNOWN`. If it is not needed: leave the property `null` so
   `explicitNulls = false` omits it from the wire payload. `municipality` has no unknown value, so an
   unset municipality is **always** omitted, even when the dimension is needed. Enum mapping is an
   exhaustive `when` from the `lands` enums to the `chat` enums with no `else`, so a new local value
   breaks compilation instead of being silently mis-sent. Property order, ids, and land order stay
   exactly as stored (no sort, dedupe, or rename).
5. **Wiring.** `ChatConversation` gains
   `private val landsProvider: () -> List<Land> = { emptyList() }`; `submit()` reads
   `val lands = runCatching { landsProvider() }.getOrElse { emptyList() }` and calls
   `answerService.ask(askRequestFor(effect.question, lands))`, so every submit **and** every retry
   uses the current list, and a failing local read degrades to the accepted `general` request
   instead of turning a question into a failure (never logged, never surfaced as an answer).
   `ChatHomeState.kt` changes only `ChatEffect.request()` to take the lands explicitly
   (`fun ChatEffect.request(lands: List<Land>): AskRequest`) so a call site cannot forget them; the
   reducer stays pure and `AskClicked`/`RetryClicked` stay unchanged. `App.kt` passes
   `{ repository.list() }` when `landRepository != null` and keeps the empty default otherwise, with
   `landRepository` added to the conversation's `remember` keys.

**Recorded alternative (not chosen):** sending the land context only when the question matches land
vocabulary (mode `general` otherwise). Rejected because the domain model mandates the all-lands
default and because ids-only `all_active` is still the minimum needed to let the service tail a later
clarification; recorded here so the decision is reviewable.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt` (the
  pure policy and builders above). `AnswerService.kt` keeps its DTOs, `answerJson`, `KtorAnswerService`,
  and `generalAskRequest` behaviorally unchanged.
- **Update** `ChatConversation.kt` (injected `landsProvider`, guarded read in `submit`) and
  `ChatHomeState.kt` (`ChatEffect.request(lands)` signature only).
- **Update** `App.kt` (pass the provider; add it to the `remember` keys). No UI, string, preview, or
  layout change.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/chat/LandContextBuilderTest.kt`;
  **update** `ChatHomeStateTest.kt` (its two `effect.request()` call sites; the no-lands assertions
  stay valid) and `ChatConversationTest.kt` (a captured-request test with a fake provider — the
  existing `ChatConversation(service, scope)` construction keeps working through the default).
- **Create/update** a MockEngine transport test under `shared/src/jvmTest/.../chat/` that captures the
  encoded `/ask` body for a two-land land-relevant question.
- **Update** `CONSTRAINTS.md` (one client MUST rule) and `docs/specs/chat_question_submission.md` (a
  short follow-up note superseding its always-`general` statement); update `feature_list.json` and
  `PROGRESS.md` **after** verification.
- **Do not change** `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, `strings.xml`, the
  platform entry points, Gradle files, or `init.sh`.

## Visual design impact

None. No new control, string, preview, color, or layout: the land list, forms, transcript, notices, and
source cards render exactly as accepted. The only user-visible effect is that the answer service now
receives the minimum land context (and `answer_land_scope` will make the scope visible later), so
`strings.xml` must remain byte-identical.

## Cross-feature interactions and handoffs

- **Supersedes** the accepted `chat_question_submission` statement that a request is always `general`
  / `lands: []`: it now holds only when no land is stored. Transcript, working state, failure/retry,
  response states, and source cards are untouched; a retry re-sends the exact wording with a freshly
  read land context.
- **Hands off** `needs_land_clarification` execution and the answer's `land_scope` presentation to
  `land_clarification`/`answer_land_scope` (the client still parses `land_scope` but does not render or
  store it here), the B13 applicability comparison to
  `land_clarification`/`land_safety_evaluation`, and the disclosure copy to `land_data_disclosure`,
  whose notice must match this payload.
- **Owns** the decision that no attribute classifier gates the mode, so a vocabulary change is a spec
  change, not a silent one.

## Implementation plan and tasks

1. Add `LandContextBuilder.kt` (folding helper, pinned term sets, `landContextNeeds`, exhaustive enum
   mapping, `minimalLandContext`, `landContextFor`, `askRequestFor` delegating to `generalAskRequest`
   for an empty list).
2. Write `LandContextBuilderTest.kt`: empty lands → the accepted `general`/empty payload; the two-land
   water scenario; production-only and municipality-only scenarios; a no-keyword question → ids only;
   unknown → `unknown`; unset municipality → omitted; accent/case variants (`¿PUEDO REGAR?`, `regadío`,
   `término municipal`); duplicates and long/Unicode names not merged or altered; repository order and
   ids preserved; an encoded-body assertion proving the JSON contains only `id` plus the needed
   attribute keys (no `name`, `notes`, `areaHectares`, timestamps, or null-valued keys).
3. Change `ChatEffect.request(lands)` and update its two test call sites.
4. Add `landsProvider` to `ChatConversation`, build the request from the guarded fresh read, and test it
   in `ChatConversationTest` with a captured `AskRequest` plus a throwing-provider case that still
   submits as `general`.
5. Wire `App.kt` (provider from `landRepository`, `remember` keys) and confirm the no-argument `App()`
   path still compiles and stays `general`.
6. Add the jvmTest MockEngine capture of the encoded `POST /ask` body for a land-relevant question
   (`all_active`, both ids, the needed attribute, no name/notes/area key anywhere).
7. Add the `CONSTRAINTS.md` MUST rule and the `chat_question_submission` follow-up note.
8. Run the verification commands, capture the evidence, then update `feature_list.json` (status +
   evidence) and `PROGRESS.md`. The planner must not mark the feature complete.

## Verification plan

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --rerun-tasks
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./init.sh --verify
git diff --check
```

Also:

- The **literal feature-list verification** is the encoded-request capture: print or assert the exact
  `POST /ask` body for a land-relevant question with two lands and confirm the relevant attribute is
  present and no name, note, area, or timestamp appears. The MockEngine test is the automated form; a
  short JVM probe that prints the encoded body may serve as the manual record.
- `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src`
  → no matches (the land read and the request stay unlogged).
- Privacy/scope greps: `MinimalLandContext` still has exactly the four contract properties; no new key
  in `strings.xml`; `Color(0x` only under `theme/`; `git diff --check` clean.
- No persistent E2E command exists and `POST /ask` is still unrouted (carried `chat_question_submission`
  F1), so there is no live end-to-end answer to smoke; the transport-level capture plus the pure
  builder tests are the honest automated equivalent. Record this limitation rather than claiming
  on-device network evidence.
- `init.sh` is **not** changed by this feature: its `--verify` target already runs the shared tests and
  the Android/Desktop builds, which is exactly what this slice needs; no new script, mode, or
  long-running server is introduced.

## Evidence to capture

- The encoded request body for a two-land land-relevant question (needed attribute only, no
  name/notes/area) and for the no-lands case (accepted `general` payload).
- Test output for `LandContextBuilderTest`, the `ChatConversation` captured-request and
  throwing-provider cases, and the MockEngine body capture, with total JVM/Android-host test counts
  (no test removed).
- `python3 contracts/validate_examples.py`, `./init.sh --verify`, the Android/Desktop builds, the iOS
  compile, the greps, and `git diff --check` (environment blockers recorded as such), plus confirmation
  that `contracts/`, `backend/`, `knowledge/`, `lands/`, `strings.xml`, the entry points, Gradle, and
  `init.sh` are untouched.

## Durable documentation impact

- `CONSTRAINTS.md`: **update** with one client MUST rule (land context carries only opaque local ids
  and the attributes the question needs; never a name, note, area, timestamp, or invented value; a
  missing/unknown value is omitted or sent as `unknown`, never guessed).
- `docs/specs/chat_question_submission.md`: **update** with a short follow-up note that
  `land_context` is no longer always `general`.
- `docs/risks-and-open-questions.md`: **not needed** here — the "attributes vs derived filters"
  question is settled as contract attributes, but the "exact rule for when all-land answers are safe
  versus when to ask for a specific land" stays open and stays with `land_clarification`; do not
  delete or rewrite that row in this slice.
- `AGENTS.md`, `CONTEXT.md`, `docs/domain-model.md`, `docs/build-brief.md`, `DESIGN.md`,
  `MasterPlanV3.md`: **not needed**; this implements their existing rules without changing a product
  decision.
- `ARCHITECTURE.md`: **not needed** (the file does not exist and this narrow request-building slice
  does not justify creating it).
- `feature_list.json` / `PROGRESS.md`: **update after verification only**, with truthful evidence.

## Risks and open questions

- **Vocabulary coverage is a content decision, not a measurement.** A question whose wording misses a
  term sends fewer attributes and therefore a more *general* (never wrong) answer; the pinned table
  keeps it reviewable, and widening it later requires a spec + test change. `land_safety_evaluation`
  should measure mixed-land and unknown-attribute cases before any threshold is claimed.
- **Ids-only `all_active` for unrelated questions** is the deliberate default; changing it means
  adopting the recorded alternative, not adding a hidden heuristic.
- **A failing local read degrades silently to `general`** so a store problem can never block a
  question. The payload then honestly says `general`; `answer_land_scope` will later surface the scope.
- **No live `/ask`**, so B13 applicability and a real end-to-end answer remain a separate, still-unowned
  slice; and `ChatConversation` reads lands synchronously in `submit` (matching the accepted
  `land_list` read), which is acceptable for MVP store sizes and is recorded deliberately.

## Validator checklist

- [ ] A request for a land-relevant question carries every stored land in repository order with its
      id verbatim, `mode: all_active`, and the attribute(s) the question needs; no `name`, `notes`,
      `areaHectares`, timestamp, or contract-unknown key appears anywhere in the encoded body.
- [ ] A question matching no vocabulary still carries the lands with ids only; `unknown` is sent as
      `unknown`, and an unset `municipality` is omitted rather than invented or blank.
- [ ] With no land stored the payload is byte-identical to the accepted `general` / `lands: []`
      request and the question keeps its exact original wording.
- [ ] The land list is read at submit and at retry (a land added, edited, or removed after the screen
      opened is reflected), and a failing local read cannot turn a question into a failure.
- [ ] The pure builder is in `commonMain`, no UI/string/preview/layout changed, and
      `contracts/`, `backend/`, `knowledge/`, `lands/`, the entry points, Gradle, and `init.sh` are
      untouched.
- [ ] `LandContextBuilderTest`, the `ChatConversation` captured-request case, and the MockEngine body
      capture exist and pass, with all feasible Gradle checks green and blockers documented.
- [ ] The `CONSTRAINTS.md` rule and the `chat_question_submission` follow-up note are present;
      `feature_list.json`/`PROGRESS.md` reflect real evidence only.
- [ ] No logging, telemetry, or extra network call was added.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/minimal_land_context.md. Added the pure, standard-library, Compose-free `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt` (`LandContextNeeds`, `landContextNeeds`, `minimalLandContext`, `landContextFor`, `askRequestFor`): a pinned, reviewable folded whole-token vocabulary decides per-question inclusion of `municipality`/`water_regime`/`production_method`; the mode is `all_active` with every stored land in repository order (ids verbatim) whenever at least one land exists and `general` with `lands: []` only when none; a needed but unknown stored value is sent as `unknown`; an unset or blank municipality is omitted (never a placeholder or an empty string); no topic classifier gates the mode; and the local-to-contract enum mapping is an exhaustive `when` with no `else`. `answerJson` (`explicitNulls = false`) omits every not-needed property, so `AnswerService.kt` keeps its DTOs, `answerJson`, `KtorAnswerService`, and `generalAskRequest` behaviorally (and byte-for-byte) unchanged.
- Wiring: `ChatEffect.request(lands)` now takes the lands explicitly (so a call site cannot forget them, while the reducer stays pure and `AskClicked`/`RetryClicked` are unchanged); `ChatConversation` gained `landsProvider: () -> List<Land> = { emptyList() }` and reads it in `submit` through `runCatching { ... }.getOrElse { emptyList() }`, so every submit AND every retry uses the lands stored at that moment and a failing local read degrades to the accepted `general` request instead of turning a question into a failure (never logged, never surfaced). `App()` passes `{ landRepository?.list().orEmpty() }` and added `landRepository` to the conversation's `remember` keys; the no-argument `App()` (iOS scaffold and previews) still compiles and stays `general`. `ChatHomeScreen`, `strings.xml`, previews, and layouts are unchanged.
- Literal feature-list verification (encoded `POST /ask` body, captured by a temporary JVM probe that was then deleted, and asserted byte for byte in the committed tests). Two lands (`land-1`: name 'Los Olivos', municipality Martos, IRRIGATED, ORGANIC, area 12.5, a private note, timestamps; `land-2`: name only), question '¿Puedo regar hoy?': {"question":"¿Puedo regar hoy?","land_context":{"mode":"all_active","lands":[{"id":"land-1","water_regime":"irrigated"},{"id":"land-2","water_regime":"unknown"}]}} - the needed attribute only, both ids verbatim, no name, note, area, timestamp, `municipality`, or `production_method` key anywhere. Production question '¿Puedo producir en ecológico?': `production_method` only (`organic`/`unknown`). Municipality question '¿En qué municipio está mi terreno?': `municipality` for `land-1` only, `land-2` omitted. No-vocabulary question '¿Cuál es el plazo de la solicitud única?': `[{"id":"land-1"},{"id":"land-2"}]` (ids only). No lands: {"question":"¿Puedo regar hoy?","land_context":{"mode":"general","lands":[]}} - byte-identical to the accepted `generalAskRequest` payload.
- New automated coverage: `shared/src/commonTest/kotlin/com/jamarglex/manijero/chat/LandContextBuilderTest.kt` (13 tests: the accepted `general` payload; the two-land water scenario with no private field or null-valued key in the encoded body; production-only and municipality-only questions; a no-vocabulary question sending ids only; unknown to `unknown` and unset municipality omitted; a blank municipality omitted even when the dimension is needed; accent/case/plural folding (`¿PUEDO REGAR?`, `regadío`, `término municipal`); the whole-token requirement (`aguacates` never matches `agua`); the full stored-to-contract water and production enum matrix; duplicates, long Unicode/emoji names, area, notes, and timestamps never merged, altered, or sent; repository order and opaque ids verbatim; and each encoded land carrying only `id` plus the one needed key). `ChatConversationTest` gained 4 (the accepted `general` payload with no lands; a land-relevant submit carrying both lands and the needed attribute; a retry re-reading a land added after the chat screen opened; a throwing provider still submitting the accepted `general` request and receiving an answer with no failure) and `KtorAnswerServiceTest` gained 1 MockEngine case asserting the exact encoded `POST /ask` body for a two-land land-relevant question plus the byte-identical no-lands body. No test removed: `@Test` count 144 at HEAD to 162.
- Commands actually run (all pass, repository root): `python3 contracts/validate_examples.py` -> 'Validated 2 request and 3 response examples against answer_api_contract'; `./gradlew :shared:jvmTest --rerun-tasks` -> BUILD SUCCESSFUL, 162 tests / 0 failures / 19 classes (`LandContextBuilderTest` 13, `ChatConversationTest` 13, `ChatHomeStateTest` 31, `KtorAnswerServiceTest` 9, `CitationPresentationTest` 23, plus the unchanged land/theme suites); `./gradlew :shared:testAndroidHostTest --rerun-tasks` -> BUILD SUCCESSFUL, 148 tests / 0 failures / 15 classes; `./gradlew :shared:compileKotlinIosSimulatorArm64` -> BUILD SUCCESSFUL; `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` -> 72 tasks executed, BUILD SUCCESSFUL (`androidApp-debug.apk`, 35,865,622 bytes); `./init.sh --verify` -> exit 0 (91 tasks, BUILD SUCCESSFUL); `git diff --check` -> clean.
- Privacy and scope: `grep -rn 'println|Log\.|Logger|printStackTrace|NSLog|System\.out' shared/src androidApp/src desktopApp/src` -> no matches (the land read and the request stay unlogged); `grep -rn 'Color(0x' shared/src/commonMain/kotlin/com/jamarglex/manijero | grep -v /theme/` -> no matches; `MinimalLandContext` still has exactly the four contract properties; `strings.xml` has no new or changed key (numstat 0); `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, the platform entry points (`androidApp/src`, `desktopApp/src`), all Gradle files, and `init.sh` are untouched (checked per path with `git status --porcelain`). No new module, dependency, ViewModel, navigation framework, coroutine API, permission, or network call was added.
- Honest gaps: there is no persistent E2E runner and `POST /ask` is still unrouted (carried `chat_question_submission` F1), so there is no live end-to-end answer to smoke; the transport-level encoded-body capture plus the pure builder tests are the honest automated equivalent and no on-device network evidence is claimed. Desktop launch smoke: `:desktopApp:run` started `com.jamarglex.manijero.MainKt` with the real `FileLandStorage` and stayed alive about 50 s with no exception in the run log until it was stopped (no interactive click-through and no screenshot; the app never submits on startup, so nothing was sent). The vocabulary is a pinned content decision, not a measurement: a wording that misses a term sends fewer attributes and therefore a more general (never wrong) answer. A failing local land read silently degrades to `general`, and `ChatConversation.submit` reads lands synchronously (matching the accepted `land_list` read), which is deliberate for MVP store sizes. `land_clarification`/`answer_land_scope` (choice + scope presentation), B13 applicability, and the disclosure copy remain theirs. Self-verified; awaiting independent validation, so not marked accepted.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/minimal_land_context.md). It did not trust the implementer report and independently reproduced the literal feature-list verification with its own temporary probe (created, run, deleted) that drove the real `ChatConversation` with a `landsProvider` over a real `FileLandStorage`/`LandRepository` store and captured the encoded body: '¿Puedo regar hoy?' -> `water_regime` only (`irrigated`/`unknown`) with both ids verbatim and no name/notes/area/timestamp/other-dimension key; production-only and municipality-only questions; a no-vocabulary question sending ids only; a blank/unset municipality omitted; no lands -> the byte-identical accepted `general` payload; and a land added during the failure notice picked up by the retry (a throwing provider degrades to `general` with no failure). It re-ran with --rerun-tasks: `python3 contracts/validate_examples.py` exit 0; `:shared:jvmTest` 162/0 across 19 classes; `:shared:testAndroidHostTest` 148/0; `:shared:compileKotlinIosSimulatorArm64 :desktopApp:build :androidApp:assembleDebug` (76 tasks, APK 35,865,622 bytes matching byte-for-byte); `./init.sh --verify` exit 0; `git diff --check` clean; the logging and `Color(0x)` greps; and its own ~45 s `:desktopApp:run` smoke with no exception. It confirmed `@Test` 144 -> 162 with no test removed, vocabulary identical to the spec's pinned table (water 26 / production 27 / municipality 13, no duplicates, all >= 4 chars), the pure Compose-free builder with an explicit `ChatEffect.request(lands)` parameter and an exhaustive `when` with no `else`, clean scope (`contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, `strings.xml`, platform entry points, Gradle, `init.sh` untouched; `AnswerService.kt` behaviorally and byte-for-byte unchanged), and a scoped security review finding no blocking issue. Non-blocking findings recorded: N1 (no `municipality` bound although the contract declares maxLength 160; a needed over-long value is sent verbatim and could yield a recoverable 422 on a real `/ask`; recommended follow-up: bound the field or omit over-long values, never silently truncate), N2 (defaulted `landsProvider` silently degrades to `general` if unwired; revisit when `answer_land_scope` makes scope visible), N3 (rethrow `CancellationException` if a provider ever suspends), N4 (stale `init.sh` banner text, carried), N5 (carried `chat_question_submission` F1: `/ask` still unrouted and no persistent E2E harness, so the transport-level encoded-body capture is the honest automated equivalent).
