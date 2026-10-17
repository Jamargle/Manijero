# Feature Spec: `land_data_disclosure`

## Source metadata

- **Feature:** `land_data_disclosure` — Explain land data handling (`privacy`)
- **Status at planning:** `not_started`; depends on accepted `local_land_store` and
  `minimal_land_context` (both `accepted`, so the feature is dependency-ready). The planner moves the
  entry to `in_progress` and writes only this spec.
- **Source behavior:** Before using land-aware answers, a person can understand in plain Spanish what
  is saved on the device and what may be sent with a question.
- **Feature-list verification:** Ask a low-digital-confidence reviewer what is stored locally and what
  leaves the device after reading the notice.
- **Feature-list note:** Do not promise backup or confidentiality beyond verified system behavior and
  provider terms.
- **Handoffs received:**
  - `docs/specs/minimal_land_context.md`: the client disclosure "copy to `land_data_disclosure`" is
    handed here, and "whose notice must match this payload". The payload today is `mode: all_active`
    with each stored land under its opaque local id and only the needed `municipality` /
    `water_regime` / `production_method`; an unknown value is sent as `unknown`; a name, note, area,
    or timestamp is never sent.
  - `docs/specs/answer_land_scope.md`: hands off "the land-data disclosure notice, what is stored
    locally, or what leaves the device".
  - `DESIGN.md` line 88 (MVP surface 7 "Privacy/help") and `docs/domain-model.md` line 83 ("Explain
    that behavior in plain Spanish before first use"); `MasterPlanV3.md` §16 ("Explain data use in
    plain Spanish before first use").
- **Size:** one stateless informational screen, one navigation destination, one short always-visible
  chat-home summary plus a labelled control, a pinned content module, strings, previews, and tests.
  One user flow, no new data model, persistence, transport, or contract change.

## Goal and boundaries

Make the two facts a person must know — **what is stored on the device** and **what may leave it with
a question** — readable in plain Spanish before they rely on a land-aware answer. The essential facts
appear directly on the chat home (so they are read before asking), and a labelled `Privacidad y
ayuda` control opens a fuller explanation. The notice must describe exactly the current behavior and
must not promise more than it.

**In scope**

- A short, always-visible plain-Spanish summary on the chat home stating that the lands are saved on
  the device and that a question may send the question and some land data.
- A labelled chat-home control that opens a shared `PrivacyScreen` rendering the full notice:
  local storage, what is sent, what is not promised, and where to get human help.
- One pinned, Compose-free content module (`privacy/LandDataDisclosure.kt`) whose sendable-attribute
  list is checked against the real request payload so the copy cannot silently under-describe it.
- Previews inside `ManijeroTheme` (chat home with the summary/control, the notice, a narrow/large-text
  variant) and pure `commonTest` coverage for the pinned structure and the payload correspondence.

**Non-goals**

- No blocking first-use gate and no persisted "notice seen" flag: that needs a preference store
  outside the accepted land store and belongs to a separate welcome/first-use slice (`CR1`). The
  always-visible summary is the scoped answer to "before using".
- No privacy policy, provider contract, analytics, consent record, telemetry, log retention, or
  export/backup: the notice describes behavior; it does not implement any.
- No change to `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/` values, the platform entry
  points, Gradle, or `init.sh`.
- No change to the accepted question, working, character-limit, suggested-question, clarification,
  response-state, source-card, failure, or land-surface behavior and copy.
- No naming of a land or id, no eligibility claim, no client-authored legal fact, and no confident
  "protected/backed up" affordance.
- No new module, dependency, ViewModel, navigation framework, coroutine, or logging.

## Job story

When I think about asking the assistant about my olive grove, I want one plain-Spanish place that
tells me exactly what the app saves on my device and what it may send when I ask, so I can decide
whether to use it without being promised a backup or a confidentiality the app cannot guarantee.

## Acceptance scenarios

### The essential facts are visible before asking

Given the chat home is shown (any question/transcript state), when the person looks at the screen
before asking, then a short plain-Spanish line states that the lands are saved on the device and that
a question may send the question and some land data, and a labelled `Privacidad y ayuda` control is
visible and opens the full notice.

### What is saved on the device

Given the person opens `Privacidad y ayuda`, when they read the notice, then it states in plain
Spanish that the lands they add are saved on this device, that no account is needed, that a saved
land holds the name and the details they wrote (municipality, riego, producción), that they can view,
edit, or remove it, that it is not copied to the internet automatically, and that there is no
automatic backup if the device is lost.

### What leaves the device with a question

Given the same notice, when the person reads the "what is sent" section, then it states that the
question text is sent as written, that a land-aware answer also sends each land's identifier and only
the data the question needs — municipio, riego o producción — that an unknown value is sent as
`no lo sé`, and that the land's name and the notes are never sent.

### Nothing is over-promised

Given the same notice, when it is reviewed, then it promises no backup, no cloud copy, and no
confidentiality beyond what the service's own terms offer, names no land and no id, makes no
eligibility or legal claim, and points to a human contact (oficina comarcal agraria or cooperativa).

### The copy matches the real payload

Given the request builder can send only `municipality`, `water_regime`, and `production_method` with
the opaque id (`minimal_land_context`), when the notice's sendable-attribute list is checked, then it
lists exactly those dimensions and the check fails if a fourth sendable attribute is ever added
(pure test).

### Navigation and back

Given the notice is open, when the person chooses `Volver`, then the chat home is shown with its
state unchanged (the typed question and transcript are preserved), and the control opens the notice
again.

### Copy, clarity, and accessibility

Given any part of the notice, when it is read, then the copy is plain everyday Spanish in the
existing tú voice, the state is carried by text (never colour alone), the text is readable and not
clipped or horizontally overflowing at `widthDp = 320` and `fontScale = 2f`, and the control has a
visible label (no icon-only affordance). The full screen-reader/focus/keyboard audit stays with
`chat_accessibility`.

### Nothing else changes

Given the feature ships, when the existing suites run, then the composer, working state, limit copy,
suggested questions, chooser, answer/abstention/source-card rendering, failure notice, land screens,
theme values, contract, and backend behave exactly as before, with no previously passing test
regressing.

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
  `./init.sh --verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`; `./init.sh` has no new mode to add.
- `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`
  (the "Is land export/backup needed" row stays open; "Sensitive farm information reaches logs or
  model providers" is the risk the notice addresses), `DESIGN.md`, `MasterPlanV3.md` §16,
  `CONSTRAINTS.md`.

Sized correctly: one stateless screen, one destination, one short summary line, one pinned content
module, strings, previews, tests. No new data model, persistence, transport, or contract change.

## Technical approach

### 1. Pinned content module (`privacy/LandDataDisclosure.kt`, Compose-free)

```kotlin
package com.jamarglex.manijero.privacy

/**
 * One land attribute that may leave the device with a land-aware question. It mirrors exactly the
 * optional dimensions `chat/LandContextBuilder.landContextNeeds` can request; a fourth sendable
 * attribute must update this enum (a test fails otherwise), so the notice cannot under-describe the
 * payload.
 */
enum class SharedLandAttribute { MUNICIPALITY, WATER_REGIME, PRODUCTION_METHOD }

/** The pinned order the on-screen copy renders. */
val SHARED_LAND_ATTRIBUTES: List<SharedLandAttribute> = listOf(
    SharedLandAttribute.MUNICIPALITY,
    SharedLandAttribute.WATER_REGIME,
    SharedLandAttribute.PRODUCTION_METHOD,
)
```

Standard-library only; no Compose, no I/O. Adding a sendable dimension requires a spec + test change.

### 2. The notice screen (`privacy/PrivacyScreen.kt`)

A stateless `PrivacyScreen(onBack: () -> Unit, modifier: Modifier = Modifier)` — no state, no
reducer, no callback beyond `onBack` — rendering, in order, inside `Surface(background)` +
`verticalScroll` + `widthIn(max = 720.dp)`:

| Section | Rendered from |
|---|---|
| Title + intro | `privacy_title`, `privacy_intro` |
| Qué se guarda en este dispositivo | `privacy_local_title` + `privacy_local_body_1/2/3` |
| Qué se envía cuando preguntas | `privacy_sent_title`, `privacy_sent_body_1`, `privacy_sent_lead`, one bullet per `SHARED_LAND_ATTRIBUTES` entry, `privacy_sent_unknown`, `privacy_sent_not_sent` |
| Lo que no puedo prometer | `privacy_promise_title` + `privacy_promise_body_1/2` |
| Dónde pedir ayuda | `privacy_help_title` + `privacy_help_body` |
| Back | a labelled `Volver` control (`privacy_back`) |

The attribute bullets are driven by the enum through an exhaustive, `else`-free `when`:

```kotlin
private fun sharedAttributeLabel(attribute: SharedLandAttribute): StringResource = when (attribute) {
    SharedLandAttribute.MUNICIPALITY -> Res.string.privacy_attribute_municipality
    SharedLandAttribute.WATER_REGIME -> Res.string.privacy_attribute_water_regime
    SharedLandAttribute.PRODUCTION_METHOD -> Res.string.privacy_attribute_production_method
}
```

Headings use `titleMedium`/`headlineMedium`, body uses `bodyLarge`/`bodyMedium` in
`onSurfaceVariant`/`onSurface`; the back control is a `TextButton`/`Button` reusing the existing back
pattern. Nothing is colour-coded and no icon-only control is added.

### 3. Chat-home summary and control (`App.kt`)

- Add `onPrivacyClick: (() -> Unit)? = null` to `ChatHomeScreen` (defaulted, so the positional
  `ChatHomePreview` call and every existing preview/caller still compile).
- Under the `Preguntar` / `Mis terrenos` row, render a short plain-Spanish summary
  (`chat_home_privacy_summary`) as `bodyMedium` in `onSurfaceVariant`, and a labelled
  `TextButton` (`chat_home_privacy`) that invokes `onPrivacyClick` when it is non-null.
- Add `AppDestination.Privacy`; `App()` renders
  `PrivacyScreen(onBack = { destination = AppDestination.Chat })` and passes
  `onPrivacyClick = { destination = AppDestination.Privacy }` to `ChatHomeScreen`. No repository is
  needed, so the control is always available on Android/Desktop; with `onPrivacyClick == null` (the
  no-argument `App()` used by the iOS scaffold and previews) only the summary line shows.

### 4. Copy contract (ship verbatim in `strings.xml`)

```xml
<string name="chat_home_privacy_summary">Tus terrenos se guardan en este dispositivo. Al preguntar, se puede enviar tu pregunta y algún dato del terreno.</string>
<string name="chat_home_privacy">Privacidad y ayuda</string>
<string name="privacy_title">Privacidad y ayuda</string>
<string name="privacy_intro">Aquí te explico con palabras sencillas qué se guarda en tu dispositivo y qué se envía cuando preguntas.</string>
<string name="privacy_local_title">Qué se guarda en este dispositivo</string>
<string name="privacy_local_body_1">Los terrenos que añades se guardan en este mismo dispositivo. No hace falta crear ninguna cuenta.</string>
<string name="privacy_local_body_2">Guardo lo que escribes en la ficha de cada terreno: su nombre y los datos que rellenes, como el municipio, el riego y la producción. Puedes verlos, editarlos o eliminarlos cuando quieras.</string>
<string name="privacy_local_body_3">No se copian solos a internet. Si pierdes el dispositivo, podrías perderlos, porque no hay copia de seguridad automática.</string>
<string name="privacy_sent_title">Qué se envía cuando preguntas</string>
<string name="privacy_sent_body_1">Para preparar la respuesta, se envía tu pregunta tal como la escribes.</string>
<string name="privacy_sent_lead">Si la respuesta usa tus terrenos, también se envía el identificador de cada terreno y solo los datos que la pregunta necesite:</string>
<string name="privacy_attribute_municipality">El municipio, si lo has escrito.</string>
<string name="privacy_attribute_water_regime">El riego: secano, regadío o una parte de cada uno.</string>
<string name="privacy_attribute_production_method">La producción: convencional, ecológica o una parte de cada una.</string>
<string name="privacy_sent_unknown">Si un dato no lo sabes, se envía como «no lo sé».</string>
<string name="privacy_sent_not_sent">El nombre que le pusiste al terreno y tus notas no se envían.</string>
<string name="privacy_promise_title">Lo que no puedo prometer</string>
<string name="privacy_promise_body_1">No hay copia de seguridad ni recuperación automática de tus terrenos: viven solo en este dispositivo.</string>
<string name="privacy_promise_body_2">La respuesta se prepara con ayuda de un servicio externo. No puedo prometer que ese servicio proteja tus datos más de lo que digan sus propias condiciones.</string>
<string name="privacy_help_title">Dónde pedir ayuda</string>
<string name="privacy_help_body">Para dudas sobre ayudas o trámites que la app no pueda responder, habla con tu oficina comarcal agraria o con tu cooperativa.</string>
<string name="privacy_back">Volver</string>
```

Plain Spanish, existing tú voice, no digit, no date, no legal fact, no confidence/backup promise. Do
not change or delete any existing string.

### 5. Deliberately not done

- No persisted first-use gate (`CR1`): a "seen" flag needs a preference store outside the land store;
  the always-visible summary is the scoped "before use" guarantee.
- No provider/legal wording the repository cannot verify: the notice says only that a service helps
  prepare the answer and that protection depends on that service's terms.
- No land name, id, eligibility implication, or client next step beyond the human contact already used
  by the accepted abstention copy.

## Expected file changes

- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosure.kt`
  (the pure enum + pinned list).
- **Create** `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt` (the
  stateless notice + previews + the exhaustive attribute-label mapping).
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `AppDestination.Privacy`,
  the `onPrivacyClick` parameter and chat-home summary/control, the destination branch, and the new
  previews (chat home with the privacy line/control; the notice; the notice at
  `widthDp = 320`/`fontScale = 2f`).
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the keys above only.
- **Create** `shared/src/commonTest/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosureTest.kt`:
  the pinned structure/order and the payload-key-count correspondence.
- **Update** `CONSTRAINTS.md` during implementation with one short MUST rule (see durable docs).
- **Do not modify**: `contracts/`, `backend/`, `knowledge/`, `lands/` sources, `theme/` values,
  `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, any Gradle file or version catalog, `init.sh`,
  and `feature_list.json`/`PROGRESS.md` while planning/implementing (only the planner's status update
  and the post-validation evidence update touch the feature list).

## Visual design impact

Uses accepted theme roles only: `background`/`onBackground`, `surface`/`onSurface`,
`onSurfaceVariant`, `primary`/`onPrimary` (the back control), `outlineVariant` (section separators if
used). No raw colour, no new token, no caution/danger treatment (the notice is informational), no
badge, checkmark, or success affordance. Text is the only carrier of meaning, so it survives
greyscale. The layout is a single scrollable column bounded at 720 dp; content wraps and is not
clipped at `widthDp = 320`/`fontScale = 2f`. No control is added beyond the labelled chat-home
control and the `Volver` control. Known limits owned elsewhere: the full screen-reader/focus/keyboard
audit and transcript auto-scroll stay with `chat_accessibility`; Desktop OS-level text scaling is
preview-based.

## Cross-feature interactions and handoffs

- **Consumes** the accepted payload rules from `minimal_land_context` (exactly which land data can
  leave the device) and the device-local wording already shipped by `land_list`/`add_land`
  ("en este dispositivo").
- **Adds** a chat-home summary line and a `Privacidad y ayuda` control: this is a declared addition to
  the accepted `chat_home` surface; the existing heading/description/composer/`Mis terrenos` behavior
  and copy are unchanged.
- **Does not change** the answer body, source cards, abstention treatment, chooser, failure notice, or
  any land surface.
- **Hands off** a persisted first-use acknowledgement gate (`CR1`) and the full accessibility audit to
  their own slices.

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
./init.sh --verify
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
`./init.sh --verify` output (or the exact blocker); and confirmation that `contracts/`, `backend/`,
`knowledge/`, `lands/`, `theme/`, the platform roots, Gradle, and `init.sh` are untouched.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One short MUST rule: the data-handling notice MUST describe only the current behavior (device-local lands; the question plus the opaque id and only the needed `municipality`/`water_regime`/`production_method`, unknown sent as `unknown`, name/notes/area/timestamp never sent), MUST NOT promise backup, cloud copy, or confidentiality beyond the service's own terms, and MUST NOT name a land, an id, or an eligibility claim. |
| `docs/domain-model.md` | Not needed | Line 83 already requires explaining data handling in plain Spanish before first use; this feature implements it without changing the domain model. |
| `docs/risks-and-open-questions.md` | Not needed | The open "Is land export/backup needed" and provider-terms rows stay open; the notice references them without resolving them. |
| `DESIGN.md` | Not needed | Surface 7 already specifies the privacy/help content; no token or new surface direction is added. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `MasterPlanV3.md` | Not needed | The operating rules (plain Spanish, minimize sent data, commonMain UI, no invented legal facts) already govern; §16 is implemented as written. |
| `docs/specs/minimal_land_context.md` | Not needed | Its disclosure handoff is executed here, not revised; its accepted payload rules are unchanged. |
| `ARCHITECTURE.md` | Not needed | It does not exist; no module, boundary, or dependency is added. |
| `init.sh` | Not needed | No new mode; the notice needs no script and must not start a service. |
| `feature_list.json`, `PROGRESS.md` | Planner: status only; implementer: after verified implementation | The planner sets `in_progress`; evidence is recorded only after implementation and independent validation. |

## Risks and open decisions

- **R1 No blocking first-use gate.** The essential facts are always visible on the chat home instead
  of gating the first land-aware question; a persisted "seen" flag needs a preference store outside
  the land store and is deferred (`CR1`, owned by a welcome/first-use slice).
- **R2 Copy vs payload drift.** The notice must describe exactly what can be sent. Mitigated by the
  pure test tying the attribute list to the encoded payload key count; if `minimal_land_context` adds
  a sendable dimension, this test fails until the notice is updated.
- **R3 Confidentiality wording.** The repository cannot verify provider terms, so the notice
  deliberately says protection depends on the service's own terms. Provider/legal wording stays a
  release-time review item (`docs/risks-and-open-questions.md`).
- **R4 Backup wording.** "No automatic backup" is the verified behavior (device-local store, no
  export); a future export/backup feature must update this copy.
- **R5 Chat-home surface change.** Adding the summary line/control modifies the accepted `chat_home`
  screen; the change is declared here, is text + one labelled control, and changes no existing
  behavior or string.
- **CR1** Whether to persist a first-use acknowledgement (and where) is left open; the current scope
  answers "before use" with an always-visible summary.

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
      platform roots, Gradle, and `init.sh` are untouched.
- [ ] No `Color(0x` outside `theme/`, and no logging/printing of a question, land, or exception.
- [ ] `:shared:jvmTest`, `:shared:testAndroidHostTest`, the iOS compile, the Android/Desktop builds,
      `./init.sh --verify`, and the contract validator pass (or the exact environment blocker is
      reported) with no previously passing test regressing; no E2E/UI-test coverage is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` were not modified by planning beyond the `in_progress`
      status; the final diff matches this spec's file list.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests LandDataDisclosureTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/land_data_disclosure.md. Added the Compose-free pinned content module shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosure.kt (SharedLandAttribute enum + SHARED_LAND_ATTRIBUTES in the pinned order) and the stateless shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt (title/intro, Qué se guarda, Qué se envía with one bullet per SHARED_LAND_ATTRIBUTES entry driven by an exhaustive else-free sharedAttributeLabel when, Lo que no puedo prometer, Dónde pedir ayuda, and a labelled Volver control) with normal and widthDp=320/fontScale=2f previews.
- Chat home (App.kt): AppDestination.Privacy added; ChatHomeScreen gained a defaulted onPrivacyClick: (() -> Unit)? = null so every existing preview/caller still compiles, plus an always-visible plain-Spanish summary (chat_home_privacy_summary, bodyMedium/onSurfaceVariant) and a labelled chat_home_privacy TextButton (rendered only when onPrivacyClick != null). App() renders PrivacyScreen(onBack = { destination = AppDestination.Chat }) and passes onPrivacyClick = { destination = AppDestination.Privacy }; the notice needs no repository, so it is always reachable on Android/Desktop and writes nothing. One new chat-home preview (summary + control) added.
- Copy contract: all 22 new strings shipped byte-for-byte equal to the spec block (Python UTF-8 comparison) and each appears exactly once; strings.xml numstat +22/-0, so no existing string was changed or deleted.
- Payload correspondence (pure commonTest LandDataDisclosureTest, 3 tests): the pinned order equals SharedLandAttribute.entries with no duplicates, a fully-populated land with a question needing every dimension ('¿Puedo regar en ecológico en mi municipio?') encodes MinimalLandContext optional keys whose size equals SHARED_LAND_ATTRIBUTES.size and which are exactly {municipality, water_regime, production_method} with no name/notes/areaHectares/timestamp in the body, and MinimalLandContext's declared property count minus its `id` equals SHARED_LAND_ATTRIBUTES.size (so a fourth sendable DTO property fails the test).
- Commands actually run (all pass, repository root): python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'; focused ./gradlew :shared:jvmTest --tests 'com.jamarglex.manijero.privacy.LandDataDisclosureTest' -> BUILD SUCCESSFUL (3 tests / 0 failures); ./gradlew :shared:jvmTest --rerun-tasks -> 184 tests / 0 failures (was 181, +3); ./gradlew :shared:testAndroidHostTest --rerun-tasks -> 170 tests / 0 failures (was 167, +3); ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; ./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks -> 72 tasks, BUILD SUCCESSFUL; ./init.sh --verify -> exit 0 (91 tasks); git diff --check clean.
- Privacy/scope: grep -rn 'println|Log\.|Logger|printStackTrace|NSLog' shared/src androidApp/src desktopApp/src -> no matches; grep -rn 'Color(0x' shared/src/commonMain/kotlin/com/jamarglex/manijero -> matches only under theme/ManijeroColors.kt; MinimalLandContext still has exactly the four contract properties; contracts/, backend/, knowledge/, lands/, theme/, the platform entry points, all Gradle files and init.sh are untouched (git status --porcelain shows only CONSTRAINTS.md, feature_list.json, PROGRESS.md, strings.xml, App.kt, the new privacy/ sources, the new privacy/ test, and the spec). No new module, dependency, ViewModel, endpoint, persistence, or logging. CONSTRAINTS.md gained the 'Land data disclosure' MUST rule.
- Honest gaps: the literal feature-list comprehension check (ask a low-digital-confidence reviewer what is stored locally and what leaves the device after reading the notice) was NOT run in this session because no reviewer was available, and is recorded as an outstanding manual check rather than claimed. No Compose UI-test/screenshot harness and no persistent E2E command exist, so the notice and the summary/control are covered structurally (compiled previews + pure test) and no automated UI/E2E or inspected render is claimed; the widthDp=320/fontScale=2f no-clipping claim is structural/compile-based, not an inspected render (owner chat_accessibility). Self-verified; awaiting independent validation.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/land_data_disclosure.md). It did not trust the implementer report and re-ran with --rerun-tasks: python3 contracts/validate_examples.py (exit 0), the focused LandDataDisclosureTest (3/0), :shared:jvmTest (184 tests / 0 failures, 20 suites; was 181, +3, no test removed), :shared:testAndroidHostTest (170 / 0, 16 suites), :shared:compileKotlinIosSimulatorArm64, :desktopApp:build :androidApp:assembleDebug (72 tasks, debug APK), ./init.sh --verify (exit 0, 91 tasks), and git diff --check (clean). It byte-for-byte checked all 22 new strings against the spec (numstat +22/-0, no existing string changed or deleted), ran the Color(0x) (only theme/ManijeroColors.kt) and logging greps, and confirmed MinimalLandContext still has exactly four properties. It verified the always-visible chat-home summary plus labelled Privacidad y ayuda control, the notice content and over-promise guards (no backup/cloud/confidentiality promise, no land name/id, no eligibility/legal claim, human contact), the exhaustive else-free sharedAttributeLabel, the payload-correspondence test (a fourth sendable dimension fails on both the encoded-key set and the DTO property count), and state preservation on Volver (remember-held destination/state). Scope confirmed clean: contracts/, backend/, knowledge/, lands/, theme/, androidApp/, desktopApp/, shared/src/iosMain/, Gradle and init.sh untouched; no new module, dependency, ViewModel, endpoint, persistence or logging. A scoped security review found no blocking issue. Findings N1-N5 non-blocking (N2 the literal low-digital-confidence comprehension check remains an outstanding manual check; N3 summary placement below the fold owns chat_accessibility; N4 the no lo sé wording vs the wire unknown token is spec-mandated; N5 rendered-evidence gap owns chat_accessibility).
