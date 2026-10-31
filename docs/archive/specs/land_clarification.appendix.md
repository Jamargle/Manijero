# Appendix — `land_clarification`

Planning and verification record for [`docs/specs/land_clarification.md`](../../specs/land_clarification.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/land_clarification.md` remains the authoritative
acceptance record.

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
- `docs/archive/MasterPlanV3.md` B13 ("Compare minimal user land attributes with source applicability; preserve
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
