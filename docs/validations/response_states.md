# Validation — `response_states`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`response_states` implementation against `docs/specs/response_states.md`.

Feature id: `response_states`. Spec: `docs/specs/response_states.md`.
Claimed status: `passing` (self-verified by the implementer). State update:
the orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair anything; it re-ran the acceptance
checks, read the diff, and independently reproduced the per-entry answer vs
abstention behavior with its own temporary probe test (created, run, and
deleted before returning).

## Review target

`git status` before and after validation showed exactly the expected footprint
(unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- Modified (tests): `ChatHomeStateTest.kt`, `ChatConversationTest.kt`,
  `theme/ManijeroColorsTest.kt`.
- Modified (docs): `CONSTRAINTS.md`.
- New (docs): `docs/specs/response_states.md` (planner artifact).

Untouched: `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`,
`shared/src/iosMain/`, the theme source values (`theme/ManijeroColors.kt`,
`theme/ManijeroTheme.kt`), `lands/`, every Gradle file and the version catalog,
`init.sh`. `git diff --check` clean. No new module, dependency, engine wiring,
base URL, navigation, ViewModel, DI, coroutine scope, endpoint, or shipped fake.

Validated product artifact hashes (sha256):

- `App.kt` `27f26e18d9461130efbb47c3eb37c1d24e7906e96181626fd6f91a30a92cf3df`
- `ChatHomeState.kt` `218fc78e808e56ec7e063b512dadcaebcdd181af978897b87d0f088f2f7c251d`
- `strings.xml` `be13b782200bd507e8ac31187968537e200ee38b557cd476c68bbf7738c4dcad`

## Independent checks and results

Re-run by the validator (with `--rerun-tasks` where relevant) so results are real
executions, not cached `UP-TO-DATE` output:

- `python3 contracts/validate_examples.py` → exit 0,
  "Validated 2 request and 3 response examples against answer_api_contract".
- `./gradlew :shared:jvmTest --rerun-tasks` → **BUILD SUCCESSFUL, 82 tests / 0
  failures** (was 78; `ChatHomeStateTest` 25→28, `ChatConversationTest` 7→8,
  `ManijeroColorsTest` +1 row).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → **BUILD SUCCESSFUL, 73
  tests / 0 failures** (fresh run; per-class XML timestamps verified).
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
  --no-configuration-cache` → **BUILD SUCCESSFUL, 72 tasks executed**, exit 0,
  `androidApp-debug.apk` repackaged.
- `./init.sh --verify` → **BUILD SUCCESSFUL, exit 0**.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → **BUILD SUCCESSFUL**.
- `grep -rn "Color(0x" …/manijero --include=*.kt` → matches only
  `theme/ManijeroColors.kt` (pre-existing theme test literals unchanged).
- Privacy grep `println|Log\.|Logger|printStackTrace|NSLog` over
  `shared/src androidApp/src desktopApp/src` → **no matches** (exit 1).
- `git diff --check` → clean.
- Independent WCAG recomputation: `onSurface` on `cautionSurface` = **14.58**
  (matches the added row); `caution` on `cautionSurface` = 7.37; `Asistente`
  label in `primary` on `surface` = 7.35 — all ≥ 4.5.
- Copy fidelity: `chat_answer_state_abstained` = `b'Sin respuesta segura'`,
  byte-equal to the spec; exactly one string added (47 total), no duplicates, no
  existing string changed or deleted, `chat_home_submitted` still present.

## Independent behavior reproduction (validator probe, 10 tests, all passing)

- `answered` → exactly one assistant entry carrying `answered`, `text`
  byte-identical to the server `answer` (including a lead-in/notice-shaped body);
  the user entry is untouched by the new field.
- `abstained` → exactly one entry carrying `abstained`, pinned text verbatim,
  `failure`/`failedQuestion` null, `lastResponseStatus == abstained`.
- Abstained → answered turn: `messages[1].answerStatus == abstained`,
  `messages[3] == answered` while `lastResponseStatus == answered`; and the
  reverse order.
- A hand-built state with a *mismatching* `lastResponseStatus`
  (`needs_land_clarification`) still keeps per-entry `abstained`/`answered`, so
  rendering cannot depend on it.
- Default `answerStatus = answered` keeps old 2-arg `ChatMessage` constructions
  equal (no regression in prior assertions).
- Clarification with empty `answer` → no assistant entry,
  `awaitingLandClarification == true`, no failure; a clarification that did carry
  text keeps its own neutral state.
- Failed request → no transcript entry, `failure` set, no answer state; an
  abstention is never a failure and carries no `[` marker.

Fidelity spot-check: `ABSTAINED_SAMPLE_NO_EVIDENCE`/`ABSTAINED_SAMPLE_FALSE_PREMISE`
and both test pinned strings are byte-identical to
`backend/app/abstention.py::ABSTENTION_MESSAGES`, and `ANSWERED_SAMPLE` starts
with the backend `LEAD_IN` and ends with the code-owned `NOTICE`.

## Spec conformance (by reading the code, not only tests)

- **Per-entry state, never `lastResponseStatus`.** `answerStatus` is written at
  exactly one site (`ChatHomeState.kt:131`, `ResponseReceived`), copied from the
  decoded `response.status`; the only other assistant entry path
  (`needs_land_clarification`) appends no entry. `lastResponseStatus` is read in
  `commonMain` only by `awaitingLandClarification`.
- **Exhaustive rendering branch.** `ChatMessageBubble` (`App.kt` l. 337–378) is a
  `when` over `speaker` × `answerStatus`: USER → `surfaceVariant`;
  `answered` → neutral `surface` card with only `Asistente`;
  `abstained` → `cautionSurface` fill + `caution` border + visible
  `Sin respuesta segura` label (`caution`) + body on `onSurface` +
  `LiveRegionMode.Polite`; `needs_land_clarification` → neutral card
  (defensive only). `ChatBubble` (l. 472–519) defaults
  `borderColor`/`stateLabel`/`stateLabelColor`, keeps
  `mergeDescendants = true` semantics, and renders `message.text` verbatim with
  no parsing.
- **No confident/certainty treatment, no added content.** The answered body is
  the server `answer` verbatim (the code-owned lead-in/notice is not duplicated);
  the abstention adds no source, marker, figure, date, land name, or client next
  step, and the client does not branch on a reason (`AskResponse` keeps exactly
  five keys, so no reason reaches the client).
- **Three distinct states.** Neutral answer card, caution abstention card with an
  explicit text label, danger `ChatFailureNotice` with `Reintentar`; the
  abstention is never folded into the failure notice.
- **Non-colour cue.** The state is carried by a visible `Text` label and a merged
  semantics node, not colour alone.

## Security assessment

Feature-scoped review found no blocking issues. No new network surface,
endpoint, engine, or dependency; no `println`/`Log`/exception-text logging;
question, answer, payload and exception text are never logged; the failure path
stays payload-free. Only presentation of already-decoded responses changed.

## Documentation / harness state

`CONSTRAINTS.md` gained exactly one client **MUST** bullet (state distinguishability,
per-entry `answerStatus` copied from the decoded response, abstention verbatim +
caution + explicit label + no added content, no confident legal-certainty
treatment). `ManijeroColorsTest` gained exactly one contrast row. `DESIGN.md`,
`AGENTS.md`, `docs/risks-and-open-questions.md`, and `init.sh` were correctly
left unchanged.

## Non-blocking findings

- **N1 (docs/harness).** `PROGRESS.md` was untouched during implementation
  although the spec's durable-doc table lists it. Closed by the orchestrator at
  acceptance time (session-log row + evidence section + the F1 limitation);
  the F1 gap was already recorded in `feature_list.json` evidence.
- **N2 (evidence).** The `widthDp=320`/`fontScale=2f` no-clipping and greyscale
  non-colour-cue claims remain structural + compiled-preview based; no rendered
  screenshot or Compose UI-test exists. This matches the spec's stated allowance
  and was reported honestly. Owner: `chat_accessibility`.
- **N3 (minor).** Preview-only sample copy lives as private consts in `App.kt`
  rather than `strings.xml`. Not shipped and faithful to the code-owned strings
  (verified byte-identical), so acceptable; keep it preview-scoped if
  `answer_source_cards` adds real samples.
- **N4 (carried, documented).** R4 fail-open default (`answered`) remains for a
  future forgotten assistant-entry site; mitigated by the single creation site,
  the copy-from-response test, and the new `CONSTRAINTS.md` rule.
- **N5.** `chat_home_submitted` is now unused in resources but correctly left
  untouched, as the spec requires.
- **R5 (carried).** `[1]`-style markers render verbatim until
  `answer_source_cards` ships cards; with the corpus still empty no real
  marker-bearing answer exists yet, so this is a documented gap, not a defect
  here.
