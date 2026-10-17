# Appendix — `land_data_disclosure`

Planning and verification record for [`docs/specs/land_data_disclosure.md`](land_data_disclosure.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/land_data_disclosure.md` remains the authoritative
acceptance record.

## Repository research

Inspected (paths relative to the repository root):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `App(landRepository, answerService)`
  is the composition root; `AppDestination` is a private enum (`Chat, LandList, AddLand, EditLand,
  RemoveLand`) switched inside `when (destination)` under one `ManijeroTheme`. `ChatHomeScreen(state,
  onAction, onLandsClick, clarificationLands, modifier)` renders the heading/description, transcript,
  notices, chooser, suggestions, composer, and the `Preguntar` / `Mis terrenos` row; the lands
  affordance is passed as `onLandsClick: (() -> Unit)?` and the whole column is already
  `verticalScroll` + `widthIn(max = 720.dp)`. About twenty previews exist, all wrapped in
  `ManijeroTheme`; `ChatHomePreview` calls `ChatHomeScreen(ChatHomeState(), {}, {})` positionally.
  There is no settings/help/privacy surface and no persisted preference today.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: pure state; no state change
  is needed for a static notice.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt`: the sendable
  vocabulary — `landContextNeeds` decides `municipality` / `waterRegime` / `productionMethod` whole
  tokens; `minimalLandContext` emits the opaque `id` plus only the needed attributes, `unknown` for a
  needed unknown value, and omits an unset municipality. This is the exact payload the notice must
  describe.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `answerJson`
  (`explicitNulls = false`), `MinimalLandContext` has exactly the four contract properties, so the
  encoded optional-key set is exactly the three sendable dimensions — the pure test can assert this.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/{Land.kt,LandRepository.kt}`: a stored
  `Land` holds `id`, `name`, `municipality`, `waterRegime`, `productionMethod`, optional
  `areaHectares`/`notes`, and timestamps; the store is device-local (`land-store-v1`), with no account
  and no backup. Confirms the "what is saved" facts.
- `shared/src/commonMain/composeResources/values/strings.xml`: one Spanish file, one string per key;
  `land_list_back`/`add_land_cancel` show the surface-owns-its-strings convention. No privacy key
  exists today.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: the closest
  precedent for a stateless, resource-backed, `ManijeroTheme`-previewed surface with a `Volver`
  back control and merged-semantics text.
- Tests/checks: `commonTest` uses `kotlin.test`; `LandContextBuilderTest`/`ChatConversationTest`/
  `KtorAnswerServiceTest` cover the request payload; no Compose UI-test or screenshot harness exists.
  `./scripts/init.sh --verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`; `./scripts/init.sh` has no new mode to add.
- `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`
  (the "Is land export/backup needed" row stays open; "Sensitive farm information reaches logs or
  model providers" is the risk the notice addresses), `DESIGN.md`, `MasterPlanV3.md` §16,
  `CONSTRAINTS.md`.

Sized correctly: one stateless screen, one destination, one short summary line, one pinned content
module, strings, previews, tests. No new data model, persistence, transport, or contract change.

## Implementation plan and tasks

1. Add `privacy/LandDataDisclosure.kt` (enum + pinned list).
2. Write `LandDataDisclosureTest`: the three values in the pinned order with no duplicates; a
   fully-populated land with a question needing every dimension encodes `MinimalLandContext` keys
   whose optional set size equals `SHARED_LAND_ATTRIBUTES.size`, and no `name`/`notes`/`areaHectares`
   key appears.
3. Add the twenty-four strings to `strings.xml`; keep every existing string byte-identical.
4. Add `privacy/PrivacyScreen.kt` (sections, exhaustive attribute-label mapping, `Volver`) and its
   previews (normal; `widthDp = 320`/`fontScale = 2f`).
5. Add `onPrivacyClick` to `ChatHomeScreen`, the summary line + labelled control, the `Privacy`
   destination, and the new chat-home preview; run the existing suites to confirm no regression
   (existing previews/callers keep compiling through the default).
6. Add the `CONSTRAINTS.md` MUST rule.
7. Run the verification commands, byte-for-byte compare the new strings with this spec, then perform
   the manual comprehension check and capture the evidence.
8. Update `feature_list.json` (status + evidence) and `PROGRESS.md` only after implementation and
   independent validation. The planner must not mark the feature complete.

## Verification plan and evidence

Run from the repository root:

```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.privacy.LandDataDisclosureTest"
./gradlew :shared:jvmTest --rerun-tasks
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./scripts/init.sh --verify
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # matches only under theme/
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # no matches
git diff --check
```

Also:

- **Literal feature-list verification** (the comprehension check): ask at least one
  low-digital-confidence reader what is stored locally and what leaves the device after reading the
  notice, and record their answers verbatim. This is a manual step; if no reviewer is available in
  the implementation session, record it as an outstanding manual check rather than claiming it (the
  other features recorded manual steps the same way).
- Byte-for-byte comparison of all new strings against this spec; confirm every existing key is
  unchanged (numstat `+N/-0`) and each new key appears once.
- The pure test is the automated guard that the notice's sendable-attribute list matches the real
  encoded payload (key count and the absence of name/notes/area keys).
- `grep -rn "MinimalLandContext"` still shows exactly four contract properties; no new route, module,
  dependency, network call, permission, or logging.
- No persistent E2E command exists and there is no Compose UI-test/screenshot harness, so the notice
  is covered by the reducer-free pure test, the generated previews, and the manual comprehension
  check; an automated UI or E2E result is not claimed.

Capture: focused and full test counts/names with no test removed; the byte-for-byte string
comparison; the payload-key-count assertion; preview captures (chat home with the line/control; the
notice; the narrow/large-text notice); the reviewer's answers (or the recorded gap); the greps;
`./scripts/init.sh --verify` output (or the exact blocker); and confirmation that `contracts/`, `backend/`,
`knowledge/`, `lands/`, `theme/`, the platform roots, Gradle, and `scripts/init.sh` are untouched.

## Validator checklist

- [ ] The chat home shows a plain-Spanish summary (device-local lands; a question may send the
      question and some land data) and a labelled `Privacidad y ayuda` control visible before asking.
- [ ] The notice states in plain Spanish: the lands are saved on the device (name + municipality,
      riego, producción), no account is needed, no automatic internet copy, and no automatic backup;
      and for a question it sends the question as written plus, for a land-aware answer, each land's
      id and only the needed municipio/riego/producción, unknown as `no lo sé`, never the name or
      notes.
- [ ] The copy promises no backup, cloud copy, or confidentiality beyond the service's own terms,
      names no land or id, makes no eligibility/legal claim, and points to the oficina comarcal
      agraria / cooperativa.
- [ ] The sendable-attribute list is a pinned Compose-free module and the pure test ties it to the
      real encoded payload (key count; no name/notes/area key); a fourth sendable attribute would fail
      the test.
- [ ] All new strings match this spec verbatim and no existing string changed or was deleted; the
      `Volver` control returns to the chat home with its state preserved.
- [ ] Text carries all meaning (no colour-only cue), the control is labelled (no icon-only
      affordance), and the notice renders without clipping/horizontal overflow at
      `widthDp = 320`/`fontScale = 2f`; the full accessibility audit is left to `chat_accessibility`.
- [ ] Product behavior and UI stay in `commonMain`; no new module, dependency, ViewModel, endpoint,
      persistence, or logging; `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, the
      platform roots, Gradle, and `scripts/init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`, and no logging/printing of a question, land, or exception.
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, the iOS compile, the Android/Desktop builds,
      `./scripts/init.sh --verify`, and the contract validator pass (or the exact environment blocker is
      reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning beyond the `in_progress`
      status; the final diff matches this spec's file list.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/land_data_disclosure.md. Added the Compose-free pinned content module shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosure.kt (SharedLandAttribute enum + SHARED_LAND_ATTRIBUTES in the pinned order) and the stateless shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt (title/intro, Qué se guarda, Qué se envía with one bullet per SHARED_LAND_ATTRIBUTES entry driven by an exhaustive else-free sharedAttributeLabel when, Lo que no puedo prometer, Dónde pedir ayuda, and a labelled Volver control) with normal and widthDp=320/fontScale=2f previews.
- Chat home (App.kt): AppDestination.Privacy added; ChatHomeScreen gained a defaulted onPrivacyClick: (() -> Unit)? = null so every existing preview/caller still compiles, plus an always-visible plain-Spanish summary (chat_home_privacy_summary, bodyMedium/onSurfaceVariant) and a labelled chat_home_privacy TextButton (rendered only when onPrivacyClick != null). App() renders PrivacyScreen(onBack = { destination = AppDestination.Chat }) and passes onPrivacyClick = { destination = AppDestination.Privacy }; the notice needs no repository, so it is always reachable on Android/Desktop and writes nothing. One new chat-home preview (summary + control) added.
- Copy contract: all 22 new strings shipped byte-for-byte equal to the spec block (Python UTF-8 comparison) and each appears exactly once; strings.xml numstat +22/-0, so no existing string was changed or deleted.
- Payload correspondence (pure commonTest LandDataDisclosureTest, 3 tests): the pinned order equals SharedLandAttribute.entries with no duplicates, a fully-populated land with a question needing every dimension ('¿Puedo regar en ecológico en mi municipio?') encodes MinimalLandContext optional keys whose size equals SHARED_LAND_ATTRIBUTES.size and which are exactly {municipality, water_regime, production_method} with no name/notes/areaHectares/timestamp in the body, and MinimalLandContext's declared property count minus its `id` equals SHARED_LAND_ATTRIBUTES.size (so a fourth sendable DTO property fails the test).
- Commands actually run (all pass, repository root): python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'; focused ./gradlew :shared:jvmTest --tests 'com.jamarglex.manijero.privacy.LandDataDisclosureTest' -> BUILD SUCCESSFUL (3 tests / 0 failures); ./gradlew :shared:jvmTest --rerun-tasks -> 184 tests / 0 failures (was 181, +3); ./gradlew :shared:testAndroidHostTest --rerun-tasks -> 170 tests / 0 failures (was 167, +3); ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; ./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks -> 72 tasks, BUILD SUCCESSFUL; ./scripts/init.sh --verify -> exit 0 (91 tasks); git diff --check clean.
- Privacy/scope: grep -rn 'println|Log\.|Logger|printStackTrace|NSLog' shared/src androidApp/src desktopApp/src -> no matches; grep -rn 'Color(0x' shared/src/commonMain/kotlin/com/jamarglex/manijero -> matches only under theme/ManijeroColors.kt; MinimalLandContext still has exactly the four contract properties; contracts/, backend/, knowledge/, lands/, theme/, the platform entry points, all Gradle files and scripts/init.sh are untouched (git status --porcelain shows only CONSTRAINTS.md, feature_list.json, PROGRESS.md, strings.xml, App.kt, the new privacy/ sources, the new privacy/ test, and the spec). No new module, dependency, ViewModel, endpoint, persistence, or logging. CONSTRAINTS.md gained the 'Land data disclosure' MUST rule.
- Honest gaps: the literal feature-list comprehension check (ask a low-digital-confidence reviewer what is stored locally and what leaves the device after reading the notice) was NOT run in this session because no reviewer was available, and is recorded as an outstanding manual check rather than claimed. No Compose UI-test/screenshot harness and no persistent E2E command exist, so the notice and the summary/control are covered structurally (compiled previews + pure test) and no automated UI/E2E or inspected render is claimed; the widthDp=320/fontScale=2f no-clipping claim is structural/compile-based, not an inspected render (owner chat_accessibility). Self-verified; awaiting independent validation.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/land_data_disclosure.md). It did not trust the implementer report and re-ran with --rerun-tasks: python3 contracts/validate_examples.py (exit 0), the focused LandDataDisclosureTest (3/0), :shared:jvmTest (184 tests / 0 failures, 20 suites; was 181, +3, no test removed), :shared:testAndroidHostTest (170 / 0, 16 suites), :shared:compileKotlinIosSimulatorArm64, :desktopApp:build :androidApp:assembleDebug (72 tasks, debug APK), ./scripts/init.sh --verify (exit 0, 91 tasks), and git diff --check (clean). It byte-for-byte checked all 22 new strings against the spec (numstat +22/-0, no existing string changed or deleted), ran the Color(0x) (only theme/ManijeroColors.kt) and logging greps, and confirmed MinimalLandContext still has exactly four properties. It verified the always-visible chat-home summary plus labelled Privacidad y ayuda control, the notice content and over-promise guards (no backup/cloud/confidentiality promise, no land name/id, no eligibility/legal claim, human contact), the exhaustive else-free sharedAttributeLabel, the payload-correspondence test (a fourth sendable dimension fails on both the encoded-key set and the DTO property count), and state preservation on Volver (remember-held destination/state). Scope confirmed clean: contracts/, backend/, knowledge/, lands/, theme/, androidApp/, desktopApp/, shared/src/iosMain/, Gradle and scripts/init.sh untouched; no new module, dependency, ViewModel, endpoint, persistence or logging. A scoped security review found no blocking issue. Findings N1-N5 non-blocking (N2 the literal low-digital-confidence comprehension check remains an outstanding manual check; N3 summary placement below the fold owns chat_accessibility; N4 the no lo sé wording vs the wire unknown token is spec-mandated; N5 rendered-evidence gap owns chat_accessibility).
