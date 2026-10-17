# Feature Spec: `land_clarification`

## Source metadata

- **Feature:** `land_clarification` — Ask which land applies (`lands-chat`)
- **Status at planning:** `not_started`; depends on accepted `minimal_land_context` and
  `source_retrieval` (both `accepted`, so it is dependency-ready).
- **Source behavior:** When the answer materially differs between lands, the assistant asks the
  person to choose the relevant land or lands before giving land-specific guidance.
- **Feature-list verification:** Use two lands with different relevant attributes and confirm the
  assistant requests a choice instead of selecting one arbitrarily.
- **Feature-list note:** Candidate choices come from the local list; preserve the original question
  through the clarification.
- **Size:** one user flow (ask → choose → land-specific answer) with one pure backend decision
  function and no new persisted data model. The backend and client halves are thin; if the validator
  judges it too broad, the clean split is "backend applicability trigger" vs "client chooser +
  `selected` resubmission".

## Goal and boundaries

Make the accepted `needs_land_clarification` response **actually happen** and let the person resolve
it, end to end: the answer service decides that the applicable evidence differs across the supplied
lands and returns the opaque local ids to choose; the client shows a chooser built from the saved
lands (names from the local list only), and resubmits the **same original question** with
`land_context.mode: selected` over the chosen lands so the answer is land-specific.

**In scope**

- One new, pure backend decision module that compares each supplied land's known attributes with the
  retrieved candidates' `applicability` and returns `needs_land_clarification` with the ids of the
  differentiated lands when they materially differ; otherwise it delegates to the accepted
  `answer_or_abstain`.
- One offline report-only CLI plus synthetic fixtures and focused tests to make the decision
  observable without a `/ask` route (the house pattern of `safe_abstention`/`grounded_answer_generation`).
- Client: retain the original question across the clarification, a `selected` request builder, a
  multi-select land chooser resolved from the local store, and resubmission with no second user
  message.

**Non-goals**

- Wiring `POST /ask` in FastAPI, changing `backend/app/main.py`, adding a model/provider, or changing
  `contracts/` (the contract already has the status and the payload).
- Rendering the answer's `land_scope` (`answer_land_scope`), a land-data disclosure notice
  (`land_data_disclosure`), or an unknown-attribute follow-up beyond the chooser.
- Changing any accepted module: `backend/app/{generation,retrieval,source_catalog,abstention}.py`,
  `contracts/`, `knowledge/`, `theme/`, `lands/`, platform entry points, Gradle, or `scripts/init.sh`.
- Re-clarifying a `selected` request (loop protection) or asking the person to choose when no stored
  land or only one land exists.
- Semantic/embeddings applicability, a calibrated score threshold, or any legal conclusion: detection
  is lexical and conservative; `land_safety_evaluation` owns measurement.
- Inventing, renaming, sorting, or deduping a land; inferring eligibility; any new module,
  dependency, ViewModel, or navigation framework.

## Job story

When two of my lands differ in the detail my question depends on, I want the assistant to ask me
which land I mean instead of guessing one — so the answer is about my actual grove, it keeps my own
words, and it never treats my stored details as proof of anything.

## Acceptance scenarios

### Two lands with different relevant attributes trigger a choice, not a guess

Given the local store has `land-A` (`water_regime: irrigated`) and `land-B` (`water_regime:
dryland`) and the approved corpus contains a passage applicable only to irrigated lands and one
applicable only to dryland lands, when the person submits a water question, then the pipeline returns
`status: needs_land_clarification` with `answer: ""`, `sources: []`, `land_ids_to_choose` = both
opaque land ids, and the accepted neutral acknowledgement is replaced by a chooser listing both lands
by their saved names.

### Lands that do not differ keep answering across all lands

Given the same two lands when the question depends on a dimension where they are equal (or when no
retrieved candidate restricts a known land attribute), when the person submits the question, then no
clarification is returned and the accepted `all_active` answer/abstention path runs unchanged.

### Unknown and missing attributes never cause a guess or a filter

Given a land whose needed attribute is `unknown` (or omitted), when it is compared with a candidate,
then it is treated as compatible with every candidate (never excluded, never used to filter), and no
value is inferred for it; only a known value that disagrees with a candidate's declared applicability
excludes that candidate.

### The chooser uses the local list and the original question survives

Given a clarification response whose `land_ids_to_choose` are resolved against the saved lands, when
the person selects one or more lands and presses **Continuar**, then the client resubmits the **exact
original wording** with `land_context.mode: selected` carrying only the chosen lands (opaque ids plus
only the needed attributes), appends no second user message, and a `selected` request is never asked
to clarify again.

### Choosing produces land-specific guidance

Given the person selected `land-A`, when the service answers for that selection, then the assistant
entry appears as usual (answered or abstained) and nothing in the client claims or implies that the
stored details prove eligibility.

### No land or one land stays as accepted

Given zero lands, the accepted `general` payload is unchanged; given exactly one land, the accepted
`all_active` payload is unchanged and no clarification is ever produced for it.

## Repository research

Inspected (paths relative to the repository root):

- `contracts/openapi.yaml` + `contracts/validate_examples.py` + `contracts/examples/response-needs-land-clarification.json`:
  `status ∈ {answered, abstained, needs_land_clarification}`; a clarification response must have
  `answer == ""`, `sources == []`, non-empty unique `land_ids_to_choose` (1..128 chars), and a
  `land_scope ∈ {general, all_active, selected}` (the accepted example uses `selected`). The request
  `land_context.lands[].id` is the same opaque local id.
- `shared/.../chat/AnswerService.kt`: `AnswerStatus.needs_land_clarification`, `AskResponse(..., land_scope, land_ids_to_choose)`, `LandContextMode { general, all_active, selected }`, `MinimalLandContext(id, municipality, water_regime, production_method)`, `generalAskRequest`.
- `shared/.../ChatHomeState.kt`: `ResponseReceived` appends an assistant entry only for a non-empty
  `answer` (so a clarification appends none), clears `submittedQuestion`, and stores
  `lastResponseStatus`/`landIdsToChoose`; `awaitingLandClarification` is derived from them. There is
  no field that survives to resent the original question, and `ChatEffect` has only `Submit(question)`.
- `shared/.../ChatConversation.kt`: reads lands via `landsProvider` on submit/retry and calls
  `answerService.ask(effect.request(lands))`; a failing read degrades to `general`; failures map to
  payload-free signals, never logged.
- `shared/.../chat/LandContextBuilder.kt`: pure builder producing only `general`/`all_active`;
  `minimalLandContext` sends only the needed attributes (`unknown` for a needed unknown, municipality
  omitted when unset); the local→contract enum mapping is exhaustive.
- `shared/.../App.kt`: `ChatHomeScreen` currently renders a neutral `chat_home_needs_land_clarification`
  notice when `awaitingLandClarification`, and receives no land list; `App(landRepository, answerService)`
  already holds the one `LandRepository`.
- `shared/.../lands/Land.kt` + `LandRepository.kt`: `Land(id, name, municipality, waterRegime,
  productionMethod, ...)`; `list()` is synchronous, in creation order, opaque ids, no sort/dedupe.
- `backend/app/abstention.py`: `answer_or_abstain(...)` returns only `Answered | Abstention`;
  `to_abstention_response` emits `abstained`; there is **no** clarification path today. `abstention.py`
  explicitly hands "land applicability, land clarification … beyond echoing a validated value" to
  `minimal_land_context` / `land_clarification`.
- `backend/app/retrieval.py`: `RetrievedPassage.applicability` is `Optional[Dict[str,str]]` with keys
  `crop`, `water_regime`, `production_method`; it is "surfaced, **never used to filter here**:
  applicability-based selection belongs to `minimal_land_context` / `land_clarification`." `Retriever.search`
  is deterministic and returns candidates with `rank`, `critical`, `applicability`. `LAND_SCOPES` lives
  in `generation.py`.
- `MasterPlanV3.md` B13 ("Compare minimal user land attributes with source applicability; preserve
  unknowns and detect materially different cases → returns clarification-needed when context changes
  the answer"), D5, §8.2 rule 12 ("do not choose one arbitrarily … ask … before giving personalized
  guidance"), §8.2 line 470 (clarification keeps `answer` empty, returns only local land ids; the
  client supplies names and collects the selection).
- `docs/domain-model.md` rules 2–5 (ask which land; never pick arbitrarily; unknown stays unknown;
  unanswered questions do not need land selection), `CONTEXT.md`, `CONSTRAINTS.md` (client land-context
  and no-invented-legal-facts rules), `docs/risks-and-open-questions.md` (medium risk "several lands
  differ"; open question "exact rule for when all-land answers are safe").
- `backend/app/main.py`: `/health` is the only route; no `/ask` (carried `chat_question_submission` F1).
  `backend/scripts/evaluate_{retrieval,generation,abstention}.py` and `backend/tests/fixtures/*` are the
  CLI/fixture conventions to mirror. Environment: this worktree has no `python` on `PATH`; pytest ran
  from a temporary out-of-repo venv with no repo dependency.

## Technical approach

### 1. Backend decision module `backend/app/clarification.py` (new, standard library only)

Composes the accepted modules unchanged (`retrieval`, `abstention`, `generation`); it never reads a
catalog/passages file, never calls a model or the network, and never filters by applicability anywhere
else.

- `NeedsLandClarification(land_ids_to_choose: Tuple[str, ...])` — a frozen dataclass; the payload is
  assembled by `to_clarification_response` from the accepted keys only.
- **Discriminating dimensions** are `water_regime` and `production_method` (the two the client can
  send; `crop` is not a request field, so a `crop` restriction is compatible with every land and never
  discriminates).
- **Compatibility:** in the citation window (first `max_claims` candidates, default 2, matching
  `abstention`), a candidate `c` declares a dimension `d` when `c.applicability` has `d` with a value
  other than `unknown`. `c` is compatible with a land `L` on `d` when `c` does not declare `d`, or `L`
  omits `d`, or `L.d == "unknown"`, or `L.d == c.applicability[d]`. `c` is **applicable** to `L` when
  compatible on every dimension it declares. `compatible(L)` = the passage ids applicable to `L`.
- **Material difference:** arrays `compatible(L)` are not all equal — equivalently, some candidate is
  applicable to one supplied land and not to another. `land_ids_to_choose` = the ids of every supplied
  land involved in a difference (a land that excludes a candidate, and a land that includes a
  candidate another excludes, so a differing pair yields both ids), in request order, deduplicated.
  An absent or `unknown` land attribute never excludes a candidate and never invents a value.
- `clarify_land_scope(question, land_context, corpus, *, k, max_claims) -> Optional[NeedsLandClarification]`:
  returns `None` unless `land_context.mode == "all_active"` with **≥ 2** lands; searches once
  (`corpus.search`) and returns `None` when there are no candidates (the abstention path owns
  `no_evidence`). `general` and `selected` always return `None` (a person who has already chosen is not
  asked again — loop protection).
- `answer_with_clarification(question, land_context, corpus, *, k, max_claims, as_of, generator=None) -> Union[Answered, Abstention, NeedsLandClarification]`:
  runs `clarify_land_scope`; on a decision returns it; otherwise delegates to
  `abstention.answer_or_abstain(..., land_scope=land_context.mode)`.
- `to_clarification_response(needs) -> dict`: exactly `{status: "needs_land_clarification", answer: "",
  sources: [], land_scope: "selected", land_ids_to_choose: list(needs.land_ids_to_choose)}` (matching
  `contracts/examples/response-needs-land-clarification.json`; the validator checks scope membership
  and the clarification invariants).

### 2. Backend CLI and fixtures (new)

`backend/scripts/evaluate_clarification.py`, mirroring `evaluate_abstention.py`: `--catalog/--passages/
--eval/--as-of/--k/--json/--fail-on-miss`, exit `0` (report, invariants hold) / `1` (a clarification
invariant failed, or `--fail-on-miss` with a mismatch) / `2` (unreadable/rejected input, malformed
JSONL, unknown key). Eval lines are `{"question", "land_context", "expect"}` with `expect` one of
`answered`/`abstained`/`needs_land_clarification`. Enforced invariants (exit `1`): a clarification
payload has empty `answer`, empty `sources`, a non-empty `land_ids_to_choose`, and every chosen id is
one of the request's land ids.

`backend/tests/fixtures/clarification/{catalog.json,passages.json,eval_questions.jsonl}` — synthetic,
labelled, no real legal fact: at least one passage `applicability.water_regime = irrigated`, one
`= dryland`, and one with no applicability; eval lines for the differentiating pair and for a pair that
does not differ.

### 3. Client: retain the question and build a `selected` request

- `shared/.../chat/LandContextBuilder.kt`: add
  `fun selectedAskRequest(question: String, selected: List<Land>): AskRequest` returning
  `LandContext(mode = LandContextMode.selected, lands = selected.map { minimalLandContext(it, landContextNeeds(question)) })`
  (request order, needed attributes only, ids verbatim; never called with an empty list).
- `shared/.../ChatHomeState.kt`:
  - add `clarificationQuestion: String? = null`;
  - in `ResponseReceived`, set `clarificationQuestion = submittedQuestion` when `response.status ==
    needs_land_clarification`, else `null` (so the exact original wording survives the empty-answer
    response, which currently clears `submittedQuestion`);
  - add `data class LandChoiceSubmitted(val selectedLandIds: List<String>) : ChatHomeAction`; its
    reducer branch is actionable only when `awaitingLandClarification && phase == IDLE &&
    clarificationQuestion != null && selectedLandIds.isNotEmpty()`, and then sets `question = ""`,
    `phase = SUBMITTING`, `submittedQuestion = clarificationQuestion`, clears failure, leaves
    `messages` **untouched** (no second user message — exactly the `RetryClicked` pattern), and emits
    `ChatEffect.SubmitSelected(clarificationQuestion, selectedLandIds)`;
  - `AskClicked` clears `clarificationQuestion` (a fresh question is not a clarification);
  - add `data class SubmitSelected(val question: String, val landIds: List<String>) : ChatEffect`;
  - `ChatEffect.request(lands)` handles both: `Submit` stays `askRequestFor`; `SubmitSelected` filters
    `lands` to the chosen ids (repository order) and returns `selectedAskRequest` when non-empty,
    otherwise `generalAskRequest(question)` (a removed land degrades to the accepted general payload,
    matching the accepted failing-read precedent).
- `shared/.../ChatConversation.kt`: launch `submit` for both effects; `submit` keeps the guarded
  `landsProvider` read and calls `effect.request(lands)`.

### 4. Client: the chooser (App.kt + strings)

- Replace the `chat_home_needs_land_clarification` notice with a multi-select chooser rendered while
  `awaitingLandClarification` and a resolved local land list is available.
- `App.kt`: when the conversation transitions into `awaitingLandClarification`, read
  `landRepository?.list()` once (guarded, never logged) into local state via a `LaunchedEffect` keyed
  on the flag, and clear it otherwise; pass the resolved `List<Land>` to `ChatHomeScreen`.
- The chooser filters that list to the ids in `state.landIdsToChoose` (local order; a returned id not
  present locally is ignored, never invented), shows each land's saved **name** and its known
  attributes reused from the existing land strings (`land_list_municipality`/`_water`/`_production`,
  `add_land_unknown` for `unknown`), offers multi-select, and one primary **Continuar** enabled only
  when ≥ 1 land is selected, dispatching `LandChoiceSubmitted(selectedIds)`.
- If the filtered list is empty (no saved land matches, or the local read failed), show a short plain
  notice and submit nothing; never fabricate a land. The chooser is one merged-semantics control group
  with large targets and non-colour cues, matching `land_list`/`response_states` style.

### 5. Deliberately recorded decisions

- The trigger lives in the **backend** because only the service knows the retrieved source
  applicability; the client cannot decide "the answer materially differs". `source_retrieval` is a
  dependency for exactly this reason.
- Clarification only for `all_active` with ≥ 2 lands; `selected` never re-clarifies.
- Detection is conservative and lexical: two lands that differ on a *needed* attribute are treated as
  possibly material even if no candidate restricts it — because no candidate restricting the dimension
  makes the compatible sets equal, this over-ask only occurs when a candidate actually restricts a
  known, differing value.

## Expected file changes

- **Create** `backend/app/clarification.py`, `backend/scripts/evaluate_clarification.py`,
  `backend/tests/test_clarification.py`, `backend/tests/fixtures/clarification/{catalog.json,passages.json,eval_questions.jsonl}`.
- **Update** `backend/README.md` (clarification boundary, CLI, `/health` remains the only route).
- **Update** `shared/.../chat/LandContextBuilder.kt` (`selectedAskRequest`),
  `shared/.../ChatHomeState.kt` (`clarificationQuestion`, `LandChoiceSubmitted`, `SubmitSelected`,
  `request` mapping), `shared/.../ChatConversation.kt` (both effects),
  `shared/.../App.kt` (chooser + wiring), `shared/.../composeResources/values/strings.xml` (chooser copy).
- **Create/update** tests: `backend/tests/test_clarification.py`; `LandContextBuilderTest`,
  `ChatHomeStateTest`, `ChatConversationTest` (selected-request capture, question retention, no second
  user message, clarification → answer via a fake `AnswerService`).
- **Update** `CONSTRAINTS.md` (one rule) and record the follow-up note in
  `docs/specs/minimal_land_context.md` (its "no land selection" non-goal is now owned here).
- **Do not change** `contracts/`, `knowledge/`, `backend/app/{generation,retrieval,source_catalog,abstention}.py`,
  `backend/app/main.py`, `theme/`, `lands/`, platform entry points, Gradle files, or `scripts/init.sh`.

## Visual design impact

Implements DESIGN.md surface 6 ("Choose land clarification: list named lands with simple attributes …
let the user select one or more and continue"). Uses only the accepted theme tokens; the existing
`chat_home_needs_land_clarification` string is replaced by chooser copy (title, description, continue,
and a no-lands fallback), all plain Spanish, no digit/date/legal claim. New previews: two-land chooser,
one-land chooser, and the chooser at `widthDp = 320` / `fontScale = 2f`. No control relies on colour
alone; no answer gains a confident affordance. `answer_land_scope` still owns rendering the scope.

## Cross-feature interactions and handoffs

- **Consumes** `minimal_land_context` (the `all_active` payload with needed attributes) and
  `source_retrieval` (`RetrievedPassage.applicability`); it must not change either accepted module.
- **Replaces** the accepted neutral clarification acknowledgement in `App.kt` and
  `chat_home_needs_land_clarification`; transcript, working state, failure/retry, answered/abstained
  states, and source cards stay as accepted.
- **Hands off** the answer's `land_scope` rendering to `answer_land_scope`, the disclosure notice to
  `land_data_disclosure`, the unknown-attribute follow-up beyond the chooser, and trap-set measurement
  plus any threshold to `land_safety_evaluation` (the direct dependent feature).
- **Owns** the decision that a `selected` request is never re-clarified and that the client never
  invents or renames a land.

## Implementation plan and tasks

1. Add `backend/app/clarification.py` (compatibility/difference helpers, `clarify_land_scope`,
   `answer_with_clarification`, `to_clarification_response`).
2. Add the synthetic `backend/tests/fixtures/clarification/` set and `backend/scripts/evaluate_clarification.py`.
3. Add `backend/tests/test_clarification.py`: two lands differing → clarification with both ids; equal
   lands → delegate (answered/abstained unchanged); `unknown`/omitted never filters; `crop`-only
   applicability never discriminates; `general`/one land/`selected` never clarify; payload shape and
   invariants; determinism; socket-guard offline; CLI exit `0`/`1`/`2`.
4. Add `selectedAskRequest` to `LandContextBuilder.kt` and its tests (mode `selected`, chosen ids,
   needed attribute only, no forbidden key).
5. Add `clarificationQuestion`, `LandChoiceSubmitted`, `SubmitSelected`, and the `request` mapping to
   `ChatHomeState.kt`; extend `ChatConversation.kt`; write the reducer/request tests.
6. Add the `App.kt` chooser, the `LaunchedEffect` local read, the strings, and the previews.
7. Add the `CONSTRAINTS.md` rule and the `minimal_land_context.md` follow-up note.
8. Run the verification commands, capture evidence, then update `feature_list.json`/`PROGRESS.md` (the
   planner must not mark the feature complete).

## Verification plan and evidence

```sh
python3 contracts/validate_examples.py
python3 backend/scripts/evaluate_clarification.py \
  --catalog backend/tests/fixtures/clarification/catalog.json \
  --passages backend/tests/fixtures/clarification/passages.json \
  --eval backend/tests/fixtures/clarification/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
cd backend && python -m pytest tests/test_clarification.py && python -m pytest
python3 -m py_compile backend/app/clarification.py backend/scripts/evaluate_clarification.py backend/tests/test_clarification.py
./gradlew :shared:jvmTest --rerun-tasks
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./scripts/init.sh --verify
git diff --check
```

Also:

- **Literal feature-list verification** (two lands, different relevant attributes): the CLI run and a
  `test_clarification.py` case where `irrigated` + `dryland` lands on a water question return
  `needs_land_clarification` with **both** land ids, `answer == ""`, `sources == []`; and the client
  case where a fake `AnswerService` returns that payload, the chooser allows a selection, and the
  resubmission is a `selected` request carrying the exact original wording and only the chosen land.
- Greps: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog\|System\.out" shared/src backend/app` → no
  matches; `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero | grep -v /theme/` → no
  matches; `MinimalLandContext` still has exactly the four contract properties.
- Honest limit: there is no `/ask` route (carried F1) and no Compose UI-test harness, so the backend
  decision is observed through the CLI/tests and the client flow through a fake `AnswerService` plus
  previews; do not claim a live end-to-end answer or automated UI coverage.
- `scripts/init.sh` is **not** changed: `--verify` already runs the shared tests and Android/Desktop builds.
  The backend slice is verified with the documented Python commands (pytest from an out-of-repo venv).

## Durable documentation impact

- `CONSTRAINTS.md`: **update** with one rule (a clarification is offered only for `all_active` ≥ 2 lands
  and requests the person to choose; the client resubmits the exact original question with
  `mode: selected` and only the chosen local ids, appends no second user message, never invents/renames
  a land, ignores unknown ids, and a `selected` request is never re-clarified).
- `backend/README.md`: **update** (clarification boundary, rules, CLI; `/health` stays the only route).
- `docs/specs/minimal_land_context.md`: **update** with a follow-up note that land selection/clarification
  is now owned here.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, `docs/risks-and-open-questions.md`,
  `MasterPlanV3.md`: **not needed** — this implements their existing rules (B13/D5, §8.2 rule 12, domain
  model rules 2–5) without changing a product decision.
- `ARCHITECTURE.md`: **not needed** (absent; a narrow decision module plus a chooser does not justify it).
- `feature_list.json` / `PROGRESS.md`: **update after verification only**, with truthful evidence.

## Risks and open questions

- **Detection is lexical and conservative.** Compatibility uses only `water_regime`/`production_method`
  and the citation window; it can over-ask (a differing known value with a candidate that restricts it)
  but never guesses. Semantic applicability and thresholds belong to `land_safety_evaluation`.
- **No `/ask` route (F1)** means the decision is observable only through the CLI/tests and the client
  through a fake; a real end-to-end clarification needs the route slice.
- **Copy churn:** `chat_home_needs_land_clarification` is replaced by chooser copy; no legal fact, digit,
  or date may enter the new strings.
- **Selected-set ambiguity:** if the person selects lands that still differ, the service answers for
  their explicit selection (no re-clarification); whether to warn again is left open for
  `land_safety_evaluation`/`answer_land_scope`.
- **Local-library absence in previews:** the no-argument `App()` (iOS scaffold/previews) has no
  repository, so the chooser cannot resolve names there; previews must supply a sample list and the
  shipped path must show the fallback rather than a fabricated land.

## Validator checklist

- [ ] Two supplied lands that differ on a dimension a retrieved candidate restricts yield
      `needs_land_clarification` with `answer == ""`, `sources == []`, `land_scope: selected`, and the
      ids of the differentiated lands (both, for a differing pair); no one land is chosen arbitrarily.
- [ ] Lands that do not differ (or candidates that restrict no known land attribute) still follow the
      accepted `all_active` answered/abstained path unchanged.
- [ ] An `unknown` or omitted land attribute never filters a candidate and no value is invented;
      `crop`-only applicability never discriminates.
- [ ] `general`, one-land, and `selected` requests never produce a clarification (no loops).
- [ ] The client resubmits the **exact original wording** with `mode: selected` and only the chosen
      local ids (needed attributes only), appends no second user message, and the chooser lists lands
      by their saved names from the local list (unknown ids ignored, never invented).
- [ ] Every clarification payload matches `AskResponse` exactly and `contracts/validate_examples.py`
      passes with `contracts/` untouched.
- [ ] `backend/app/{generation,retrieval,source_catalog,abstention}.py`, `main.py`, `knowledge/`,
      `theme/`, `lands/`, platform roots, Gradle, and `scripts/init.sh` are unchanged; fixtures are synthetic
      and labelled with no real legal fact.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, ViewModel, endpoint, or
      logging; the new strings match this spec verbatim and replace the acknowledgement cleanly.
- [ ] Feasible checks pass (or the exact environment blocker is reported) with no previously passing
      test regressing; the CLI, backend tests, and client tests exist and pass; no E2E/UI coverage is
      claimed; `feature_list.json`/`PROGRESS.md` report only commands actually run.

### Follow-up status after `chat_accessibility`

- **N2 closed** (2026-10-13): the chooser no longer flashes the "no puedo mostrar tus terrenos" fallback
  before the local read resolves. `clarificationLands` is now `List<Land>?` (`null` = unresolved) and
  `LandClarificationChooser` renders only its title and explanation while it is `null`; the fallback
  appears only for a resolved empty list (or a failed read, which resolves to `emptyList()`), and the
  rows plus `Continuar` otherwise. No copy, string, or clarification behavior changed.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_clarification.py --catalog backend/tests/fixtures/clarification/catalog.json --passages backend/tests/fixtures/clarification/passages.json --eval backend/tests/fixtures/clarification/eval_questions.jsonl --as-of 2026-10-13 --k 5
./scripts/init.sh --backend-tests tests/test_clarification.py
./gradlew :shared:jvmTest --tests LandContextBuilderTest --tests ChatHomeStateTest --tests ChatConversationTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Implemented (self-verified; awaiting independent validation). Backend: offline, standard-library `backend/app/clarification.py` composes the accepted retrieval/abstention/generation modules unchanged, compares each supplied land's known `water_regime`/`production_method` with the citation-window candidates' `applicability`, and returns `needs_land_clarification` with the differing lands' opaque ids only for `mode: all_active` with >= 2 lands; `general`, a single land, a `selected` request, a stale corpus, and an empty candidate set delegate to the accepted `answer_or_abstain`. `unknown`/omitted attributes never filter a candidate and `crop`-only applicability never discriminates. `to_clarification_response` emits exactly `{status, answer: "", sources: [], land_scope: "selected", land_ids_to_choose}`. `backend/scripts/evaluate_clarification.py` reports it offline with the clarification invariants enforced (exit 0/1/2). Synthetic `backend/tests/fixtures/clarification/*` carry no real legal fact.
- Client (commonMain): `chat/LandContextBuilder.selectedAskRequest` (exact wording, `mode: selected`, need-only attributes, ids verbatim, non-empty required); `ChatHomeState` `clarificationQuestion` (retains the exact original wording across the empty-answer clarification, cleared by `AskClicked`), `LandChoiceSubmitted` (idle + pending clarification + retained wording + >= 1 land), `SubmitSelected`, and `ChatEffect.request(lands)` (chosen stored lands in repository order; unknown ids ignored; none left -> accepted `general`); `ChatConversation` handles both effects; `App.kt` multi-select chooser from a one-shot guarded local read (no-lands fallback, never a fabricated land) with saved names and known attributes; four plain-Spanish chooser strings replace `chat_home_needs_land_clarification`; three previews.
- Verification commands actually run: `python3 contracts/validate_examples.py` -> exit 0; the clarification CLI (catalog/passages/eval, --as-of 2026-10-13 --k 5) -> exit 0, `corpus: current`, 5 answered, 1 clarification with both `land-A, land-B`, invariants hold, 0 expect-mismatches; `python3 -m py_compile` on the three new files -> clean; `cd backend && python -m pytest tests/test_clarification.py` -> 70 passed and `python -m pytest` -> 469 passed (399 existing + 70 new), run from the out-of-repo venv (Python 3.9.6), no repo dependency added; `:shared:jvmTest --rerun-tasks` -> 174/0 (was 162; 12 new: `LandContextBuilderTest` +3, `ChatHomeStateTest` +7, `ChatConversationTest` +2, no test removed); `:shared:testAndroidHostTest --rerun-tasks` -> 0 failures; `:shared:compileKotlinIosSimulatorArm64` -> BUILD SUCCESSFUL; `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` -> BUILD SUCCESSFUL (72 tasks); `./scripts/init.sh --verify` -> exit 0; `git diff --check` clean.
- Literal feature-list verification: the fixture CLI's differentiating case returns `needs_land_clarification` with both land ids instead of picking one, and `ChatConversationTest` drives a fake `AnswerService` returning that payload -> choose a land -> the resubmission is a `selected` request with the exact original wording and only the chosen land (no second user message); `LandContextBuilderTest`/`ChatHomeStateTest` assert the byte-for-byte `selected` body, the chosen-only/repository-order filter, the removed-land -> `general` degrade, and the unknown-id ignore, plus `unknown` never filtering (backend tests) and `crop`-only applicability never discriminating.
- Scope/privacy: `contracts/`, `backend/app/{generation,retrieval,source_catalog,abstention}.py`, `backend/app/main.py`, `knowledge/`, `theme/`, `lands/`, the platform entry points, all Gradle files, and `scripts/init.sh` are untouched; no new module, dependency, route, ViewModel, or logging; the logging and raw-`Color(0x)` greps have no matches and `MinimalLandContext` still has exactly the four contract properties. `CONSTRAINTS.md` gained the land-clarification MUST rule; `backend/README.md` and `docs/specs/minimal_land_context.md` were updated.
- Honest limits: there is no `/ask` route (carried `chat_question_submission` F1) and no Compose UI-test harness, so the backend decision is observed through the CLI/tests and the client flow through a fake `AnswerService` plus previews; no live end-to-end answer and no automated UI coverage is claimed. Detection is lexical and conservative (can over-ask, never guesses); `land_safety_evaluation` owns measurement and `answer_land_scope` owns rendering the scope. Self-verified; not accepted.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/land_clarification.md). It did not trust the implementer report and independently re-ran `python3 contracts/validate_examples.py` (exit 0, `contracts/` byte-unchanged), `pytest tests/test_clarification.py` (70 passed) and `pytest` (469 passed) from a temp out-of-repo venv with no repo dependency, `py_compile`, and `git diff --check`; re-ran the clarification CLI (exit 0; corpus current, 5 answered, 1 clarification with both ids `land-A, land-B`, invariants hold, 0 expect-mismatches; byte-identical `--json`; `--fail-on-miss` 0->1; empty eval and `--k 0` exit 2; expired catalog -> `stale_evidence` with 0 clarifications); re-ran `:shared:jvmTest --rerun-tasks` (174/0), `:shared:testAndroidHostTest --rerun-tasks` (160/0), `:shared:compileKotlinIosSimulatorArm64`, `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` (72 tasks, APK) and `./scripts/init.sh --verify` (exit 0). With its own synthetic corpus it independently reproduced the differing pair -> both ids and the exact 5-key payload (validated against the dereferenced `AskResponse` via jsonschema), equal lands/no-restriction -> delegate, `unknown`/omitted never filtering, `crop`-only never discriminating, `general`/one-land/`selected` never clarifying, order+dedup, and the `max_claims` window. It confirmed all do-not-touch paths (`contracts/`, `knowledge/`, `generation/retrieval/source_catalog/abstention`, `main.py`, `theme/`, `lands/`, platform roots, Gradle, `scripts/init.sh`, `requirements.txt`) unchanged, `MinimalLandContext` still 4 properties, no logging/`Color(0x)` outside `theme/`, no new module/dependency/route/ViewModel, and synthetic/labelled fixtures with no real legal fact. Non-blocking findings N1-N4 recorded: N1 (evidence baseline/count corrected to 162/12 at acceptance), N2 (chooser briefly shows the no-lands fallback before the guarded read resolves; owner `chat_accessibility`), N3 (a >128-char land id would raise an uncaught `ValueError` in the CLI; contract already bounds `land.id` to 128; defensive note), N4 (carried honest limits: no `/ask` route, no UI-test harness, lexical/conservative detection).
