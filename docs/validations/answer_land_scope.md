# Validation — `answer_land_scope`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`answer_land_scope` implementation against `docs/specs/answer_land_scope.md`.

Feature id: `answer_land_scope`. Spec: `docs/specs/answer_land_scope.md`.
Claimed status: `passing` (self-verified by the implementer). State update:
the orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair anything; it re-ran the acceptance
checks, read the diff, and independently reproduced the per-entry land-scope
behavior with its own temporary probe test (created, run, and deleted before
returning).

## Review target

`git status --porcelain` before and after validation showed exactly the expected
footprint (unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- Modified (tests): `ChatHomeStateTest.kt`, `ChatConversationTest.kt`.
- Modified (docs/harness): `CONSTRAINTS.md`, `feature_list.json`, `PROGRESS.md`.
- New (docs): `docs/specs/answer_land_scope.md` (planner artifact).

Untouched: `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`,
`androidApp/`, `desktopApp/`, `shared/src/iosMain/`, every Gradle file, and
`init.sh`. `git diff --check` clean. No new module, dependency, ViewModel,
navigation, control, endpoint, or logging.

## Independent checks and results

Re-run by the validator (with `--rerun-tasks` where relevant) so results are real
executions, not cached output:

- `python3 contracts/validate_examples.py` → exit 0,
  "Validated 2 request and 3 response examples against answer_api_contract".
- Focused `./gradlew :shared:jvmTest --tests ChatHomeStateTest --tests
  ChatConversationTest` → BUILD SUCCESSFUL.
- `./gradlew :shared:jvmTest --rerun-tasks` → **181 tests / 0 failures**
  (`ChatHomeStateTest` 44, `ChatConversationTest` 16; 174 → 181, +7 new, no test
  removed).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → **167 tests / 0
  failures** (was 160, +7).
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` →
  BUILD SUCCESSFUL (debug APK).
- `./init.sh --verify` → BUILD SUCCESSFUL, exit 0 (91 tasks).
- `grep -rn "Color(0x" … --include=*.kt` → matches only
  `theme/ManijeroColors.kt`.
- Privacy grep `println|Log\.|Logger|printStackTrace|NSLog` over
  `shared/src androidApp/src desktopApp/src` → no matches.
- `git diff --check` → clean.
- Copy fidelity: all three new strings byte-for-byte equal to the spec —
  `chat_land_scope_general` = `No tiene en cuenta tus terrenos.`,
  `chat_land_scope_all_active` = `Tiene en cuenta todos tus terrenos.`,
  `chat_land_scope_selected` = `Tiene en cuenta los terrenos que elegiste.`;
  `strings.xml` numstat `+3/-0`; each key appears once; no existing string
  changed or deleted.

## Independent behavior reproduction (validator probe, 4 tests, all passing)

- Each `LandContextMode` value is copied onto exactly one assistant entry at the
  single creation site (`ResponseReceived`).
- An earlier `selected` entry survives a later `general` turn while
  `lastResponseStatus` is the latest turn's status, so rendering never depends on
  the mutable `lastResponseStatus`.
- An empty-answer `needs_land_clarification` response appends no assistant entry.
- The default scope is `general`.

## Spec conformance (by reading the code, not only tests)

- **Per-entry scope, never `lastResponseStatus`.** `ChatMessage.landScope` is
  written only in `ResponseReceived`, alongside `status`/`sources`.
- **Exhaustive, `else`-free mapping.** `landScopeCaption` (`App.kt`) is a `when`
  over the three-value `enum class LandContextMode { general, all_active,
  selected }` (`AnswerService.kt`); a fourth mode would fail compilation.
- **Neutral rendering.** The caption is `labelLarge`/`onSurfaceVariant`, rendered
  directly below the `Asistente` label and above any `stateLabel`/body, inside the
  existing `semantics(mergeDescendants = true)` node — no badge, checkmark, or
  success colour; no land name or id; no eligibility claim.
- **Answered and abstained only.** The answered and abstained branches pass
  `scopeLabel`; the defensive clarification branch, user, working, and failure
  paths pass nothing. An abstained entry keeps its `cautionSurface`/`caution`
  treatment, `Sin respuesta segura` label, and verbatim message, and additionally
  shows its scope.
- **Previews.** All-lands, selected-lands, abstention-with-scope, and a
  `widthDp = 320`/`fontScale = 2f` variant, all inside `ManijeroTheme`; the
  general case is covered by the existing answered previews via the default
  scope.

## Security assessment

Feature-scoped review found no blocking issues. No new network surface or
endpoint, no new dependency, no logging/printing of questions, answers, payloads,
or exceptions, no personal/land data added to any payload (the caption is a
generic mode label), and no injection/URL/deserialization change (schema
unchanged; `land_scope` was already decoded). The fail-open default (`general`)
is safe by design.

## Documentation / harness state

`CONSTRAINTS.md` gained exactly one operational client **MUST** rule
("Client land scope"). `DESIGN.md`, the upstream specs, `AGENTS.md`, and
`ARCHITECTURE.md` correctly needed no change (no new token, boundary, or
dependency). The `/ask`/UI-harness limitation is recorded rather than worked
around.

## Non-blocking findings

- **N1 (process).** The implementer updated `feature_list.json`/`PROGRESS.md`
  before validation; this matches the repo's established workflow (self-verified
  `passing` + evidence, then a separate `Accepted` row). No product impact.
- **N2 (evidence).** No dedicated preview is *named* "general"; the general
  caption is shown by the existing answered previews via the default scope.
  Behaviorally covered.
- **N3 (evidence, owner `chat_accessibility`).** Greyscale and
  `widthDp=320`/`fontScale=2f` no-clipping are established structurally and
  compile-based, not from an inspected render; no Compose UI-test harness exists.
- **N4 (carried limits).** No on-device/UI or E2E result is claimed (no platform
  `/ask`, empty corpus, `UnavailableAnswerService` default); the `selected`
  caption stays generic because the wire carries only the mode. Both are
  explicitly documented by the implementer and the spec.
