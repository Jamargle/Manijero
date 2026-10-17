# Feature Spec: `land_form_accessibility`

## Source metadata

- **Feature:** `land_form_accessibility` — Complete a land form accessibly (`accessibility`), `not_started` at planning (2026-10-13).
- **Depends on:** `add_land` and `edit_land`, both **accepted**.
- **Source behavior:** A person can add or edit a land with readable labels, understandable unknown options, and recoverable validation errors.
- **Source verification:** Complete and correct a land form using enlarged text and keyboard or assistive-technology navigation.
- **Feature-list note:** Validate the form with people who have low digital confidence.
- **Carried handoffs this feature owns:** `add_land` evidence ("screen-reader/large-text checks … the spec defers this to `land_form_accessibility`"); `edit_land` ("A full accessibility validation (screen reader, enlarged text, low-digital-confidence users) stays with `land_form_accessibility`", plus its F3 no-UI-test-harness and F6 implementer-only smoke); `land_list` ("TalkBack row-merge reading and Desktop keyboard focus were not verified end-to-end … deferred to `chat_accessibility` / `land_form_accessibility`" — the *journey into* the form only; no list-code change is proposed).
- **Scope:** the two land forms (`AddLandScreen`, `EditLandScreen`) only. Accepted chat, backend, storage, list, and removal behavior stays untouched.

## Goal and boundaries

Make the add and edit land forms verifiably usable with enlarged system text, a screen reader, and a keyboard alone: every control keeps a readable name, the two `No lo sé` options stop being ambiguous when read aloud, and a validation error both says what is wrong and puts the person back on the field to fix it without losing anything already entered.

**In scope**

- An accessible name for every radio option that names its own group, plus group semantics, so `No lo sé` is never read twice without saying whether it is `Riego` or `Producción`.
- Recoverable validation on both forms: after a blank-name save, the plain-Spanish message is announced *and* input focus moves to the name field; every entered value survives.
- The form title exposed as a `heading`.
- Verified enlarged text (Android `font_scale 2.0`, narrow Desktop window, 2x preview), a keyboard-only completion with visible focus on Desktop, Android touch targets ≥48dp, and no colour-only error state.
- The literal verification (complete one add form, correct one edit form at enlarged text with keyboard/assistive navigation) plus the recorded low-digital-confidence manual checks.

**Non-goals**

- No visible copy change: `add_land_*`, `edit_land_*`, and `land_list_*` strings stay byte-identical. "Understandable unknown options" comes from the existing visible description, the default `No lo sé`, and the new group-qualified accessible name; rewording the mixed labels is a product copy review, not this slice (U1).
- No change to `AddLandState`/`EditLandState`/`reduce`/`toDraftOrNull()`, `Land`, `LandDraft`, `LandRepository`, the `land-store-v1` format, the storage adapters, or the `App()` read/write call sites (the save already preserves values and clears the error on the next edit).
- No change to `LandListScreen`, `RemoveLandScreen`, `PrivacyScreen`, the chat surface, `theme/`, entry points, `contracts/`, `backend/`, `knowledge/`, or `init.sh`.
- No new module, dependency (including test-only), ViewModel, coroutine, navigation, dialog, or Compose UI-test harness; no logging of land data or exceptions.
- No wide-window centring of the land columns and no layout restructure: large-window adaptation is owned by `desktop_mvp_build` (U2).
- No iOS release work; product UI and behavior stay in `commonMain`.

## Job story

When I fill in a land on my phone or computer, with big letters, with a screen reader, or with only a keyboard, I want to know which question each option belongs to, and if I forget the name I want the app to tell me what is wrong and put me back on the field — so I can finish or correct the form myself without help.

## Acceptance scenarios

### Enlarged text keeps the whole form readable

Given Android `font_scale 2.0` (or the `fontScale = 2f` preview), when the add form and the prefilled edit form are shown, then every label, option, message and action wraps without clipping, overlap, or horizontal overflow, and both forms stay vertically scrollable.

### Enlarged text with keyboard/assistive navigation completes a form

Given the Android app with enlarged text (or the Desktop window with the keyboard only), when a person fills an add form (name, optional municipality, one water and one production choice) and activates `Guardar terreno`, then the land is saved and the list shows it with the accepted plain-Spanish confirmation, with no step requiring an unlabelled control.

### The unknown options are unambiguous when read aloud

Given a screen reader (or the Android accessibility-node dump) on either form, when the two choice groups are read, then each option's accessible name states its group — `Riego: No lo sé`, `Producción: No lo sé`, `Riego: Regadío`, `Producción: Ecológico` — and each option also reports its role and selected state, so the two `No lo sé` choices can never be confused.

### A missing name is announced and recoverable

Given either form with an empty or whitespace-only name and other values already filled in, when the person activates `Guardar terreno` / `Guardar cambios`, then no record is written, the unchanged plain-Spanish name message is visible **and** announced, input focus is on the name field (a repeated attempt re-focuses it), and every entered value and selection is still there.

### Correcting the name completes the form

Given the error state above, when the person types a name and saves, then the error clears as soon as typing starts, exactly one record is written, and the accepted `add_land`/`edit_land` confirmation follows.

### Failures are announced and never lose work

Given a storage write that fails (or an edit target that is no longer stored), when the person saves, then the accepted plain-Spanish message is announced politely, no confirmation or success navigation occurs, and the values stay on screen for retry or `Cancelar`.

### Nothing else changes

Given the feature ships, when the existing suites run, then the add/edit screens' behavior, copy, layout and persistence, and the accepted list/removal/privacy/chat surfaces behave exactly as before, with no previously passing test regressing and no new module, dependency, or logging.

## Repository research

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt` / `EditLandScreen.kt`: both are `Surface` + `Column(verticalScroll)` + an inner `.fillMaxWidth().widthIn(max = 720.dp)` column; a required `OutlinedTextField` with `isError = state.showNameError` + `supportingText = add_land_name_error`, an optional municipality field, two `ChoiceGroup`s (the shared `internal ChoiceGroup`/`ChoiceItem`), a `LiveRegionMode.Polite` failure `Text`, and full-width `Guardar*`/`Cancelar`. **Gaps:** no `selectableGroup()`; the group label is a plain `Text` never associated with its options, so `No lo sé` appears twice with no group context; option rows carry no accessible name beyond the child text; no `heading()` on the titles; the name error is only a supporting text — no announcement and no focus move, so a screen-reader/keyboard user pressing Guardar hears nothing and stays on the button. Existing previews already cover blank, error, known values, failures, long text, compact, wide and `fontScale = 2f`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandState.kt` / `EditLandState.kt`: pure reducers. `SaveClicked` sets `showNameError = !hasName`; every field edit clears `showNameError` (and the edit form's `failure`); `toDraftOrNull()` returns `null` for a blank name, so "nothing is written" is already reducer-level and tested. **Note for the fix:** the error flag stays `true` across a repeated blank-name attempt, so a state-keyed `LaunchedEffect` alone would not re-focus — request focus from the save path.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `AppDestination.AddLand`/`EditLand` render the two screens with named callbacks; the single `create`/`update` call sites catch failures without logging. Nothing here changes.
- `shared/src/commonMain/composeResources/values/strings.xml`: 102 strings, one Spanish file, every control labelled (`add_land_name_label`, `add_land_municipality_label`, `add_land_water_label` = `Riego`, `add_land_production_label` = `Producción`, `add_land_unknown` = `No lo sé`, `add_land_name_error`, `edit_land_*`).
- `theme/ManijeroColors.kt` + `ManijeroColorsTest` hold the WCAG pair table (no pair change needed); `DESIGN.md` "Accessibility and validation" records the chat baseline and forbids claiming accessibility before the checks are done. `LandListScreen.kt` keeps merged rows, labelled `Editar`/`Eliminar` controls and polite confirmations — used only as the journey in and out.
- Tests today are pure/real-store (`AddLandStateTest`, `EditLandStateTest`, `LandRepositoryTest`, `EditLandRepositoryTest`, the two Desktop store tests); no Compose UI-test artifact exists and the repo refuses test-only dependencies. `compose.foundation` 1.12.1 is present, so `selectableGroup`/`FocusRequester` need no dependency. `init.sh --verify` runs `:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`. Prior features recorded a real Android emulator (`Medium_Phone_API_35`, `adb`, `uiautomator dump`) and the Desktop app through the macOS AX tree, and recorded honestly that TalkBack speech is not capturable and Desktop screen capture was denied.

Sized correctly: two existing stateless screens plus one new string, no data model, no persistence, no transport, no contract change; like `chat_accessibility` it is verification-dominant.

## Technical approach

1. **Group-qualified option names and group semantics** (`ChoiceGroup` in `AddLandScreen.kt`, shared with the edit screen): add `Modifier.selectableGroup()` to the options column so assistive technology treats the four rows as one single-choice set, and give every option row an accessible name built from the *existing* visible strings so the spoken group can never drift from the visible heading.

   ```kotlin
   val optionName = stringResource(
       Res.string.add_land_choice_description, label, stringResource(choice.label),
   )
   Row(
       modifier = Modifier
           .fillMaxWidth()
           .selectable(selected = choice.selected, role = Role.RadioButton, onClick = choice.onSelect)
           .semantics { contentDescription = optionName }
           .padding(vertical = 12.dp),
       ...
   )
   ```

   Do not add a second clickable/`RadioButton(onClick = …)` focus stop, do not merge the whole group into one node, and keep the selected state coming from `selectable`. Rejected alternative: relying on the adjacent group `Text` node — a screen reader reads options in isolation and would still announce two identical `No lo sé` options.
2. **Heading semantics** on both titles: `Modifier.semantics { heading() }` for `add_land_title` and `edit_land_title` (the accepted chat title already does this).
3. **Recoverable, announced name error** (both screens): hold a `FocusRequester` on the name field and move input focus to it on a blank-name save, requested from the save path so a repeated attempt re-focuses:

   ```kotlin
   val nameFocus = remember { FocusRequester() }
   val handleAction: (AddLandAction) -> Unit = { action ->
       if (action is AddLandAction.SaveClicked && !state.hasName) nameFocus.requestFocus()
       onAction(action)
   }
   ```

   (same shape with `EditLandAction.SaveClicked`). Keep `isError`/`supportingText` unchanged and make the message perceivable without sight: mark the visible error `Text` with `liveRegion = LiveRegionMode.Polite` and/or attach Compose error semantics to the field (`Modifier.semantics { error(nameErrorMessage) }`); doing both is recommended. Focus moving to the field opening the Android IME is expected and recorded; do **not** autofocus the form on entry.
4. **No copy or layout change:** keep every visible string byte-identical and every existing modifier order; only semantics, focus, and one accessibility string are added. Keep all existing previews and add one combined preview per form (`widthDp = 320, fontScale = 2f` with `showNameError = true`).
5. **No new dependencies, no state change, no I/O change:** reducers, repository and `App()` call sites stay as accepted.

### Copy contract

One new key only, shipped byte-for-byte in `shared/src/commonMain/composeResources/values/strings.xml`:

```xml
<string name="add_land_choice_description">%1$s: %2$s</string>
```

- `%1$s` is the visible group label (`Riego` / `Producción`), `%2$s` the visible option label. Resulting names: `Riego: No lo sé`, `Riego: Secano`, `Riego: Regadío`, `Riego: Una parte de regadío y otra de secano`, `Producción: No lo sé`, `Producción: Convencional`, `Producción: Ecológico`, `Producción: Una parte de cada uno`.
- `strings.xml` must show `+1/-0`: no existing string may change or disappear, the new key appears exactly once, and it is used only as an accessible name — never visible body text.
- No cloud/backup claim, no eligibility or legal implication, no invented value for `UNKNOWN`.

## Visual design impact

No visual change: same background, Material 3 fields, radio rows, error role, buttons and `720.dp` cap; the additions are semantics and focus only, and no state becomes colour-only (the name error keeps visible text plus `isError`). Consequence to record: the Android IME may open when focus moves to the name field after a blank-name save.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: `selectableGroup()` in `ChoiceGroup`, the group-qualified option `contentDescription`, `heading()` on the title, the name-field `focusRequester`, focus-on-blank-save, the error announcement, and one combined narrow/large-font error preview.
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`: the same `heading()`, focus request, focus-on-blank-save, error announcement and combined preview (the choice fixes arrive through the shared `ChoiceGroup`).
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: add `add_land_choice_description` only.
- **Update** `CONSTRAINTS.md` (new "Land form accessibility" MUST rule) and `DESIGN.md` (land add/edit accessibility baseline + gaps).
- **Append one short note each** to `docs/specs/add_land.md` and `docs/specs/edit_land.md`: the deferred accessibility checks are now done (precedent: the `response_states` U2 and `land_clarification` N2 notes).
- **Do not modify** `AddLandState.kt`, `EditLandState.kt`, `Land.kt`, `LandDraft.kt`, `LandRepository.kt`, the storage adapters/format, `LandListScreen.kt`, `RemoveLandScreen.kt`, `PrivacyScreen.kt`, `App.kt`, `ChatHomeState.kt`, `ChatConversation.kt`, `chat/`, `privacy/`, `theme/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, `contracts/`, `backend/`, `knowledge/`, any Gradle file, `init.sh`, and `feature_list.json`/`PROGRESS.md` while implementing.

## Implementation plan and tasks

1. Add `selectableGroup()`, the group-qualified `contentDescription` and the `heading()` semantics; confirm no option row gained a second focus stop and the selected state still comes from `selectable`.
2. Add the name-field `FocusRequester`, the focus move from the save path and the error announcement on both screens; confirm the reducers/`App()` are untouched and a repeated blank-name save re-focuses.
3. Add the single string key and the two combined previews, then byte-check `strings.xml` (`1 0`, no other change).
4. Run the automated checks and greps below.
5. Android: install the debug APK, set `font_scale` 1.0 and 2.0, and dump both forms with `uiautomator` (see the evidence list); attempt TalkBack and record the outcome honestly.
6. Desktop: `:desktopApp:run`, open the form, complete/correct it by keyboard only reading values from the macOS AX tree, and resize narrow and wide; record whether the visual focus indication could be inspected.
7. Update `CONSTRAINTS.md`, `DESIGN.md` and the two one-line spec notes; record the low-digital-confidence checks; touch `feature_list.json`/`PROGRESS.md` only after independent validation.

Suggested new `CONSTRAINTS.md` rule, "Land form accessibility":

> **MUST**: the land add and edit forms MUST keep a plain-Spanish text name on every control, MUST name each choice option with its group (`Riego: No lo sé`, `Producción: No lo sé`) inside a `selectableGroup`, MUST expose each form title as a heading, and MUST NOT leave a blank-name save silent: the unchanged required-name message is shown *and* announced and input focus returns to the name field with every entered value preserved. Reason: `land_form_accessibility` established that two identically named `No lo sé` options and an unannounced validation error are exactly the failures a person with low digital confidence or a screen reader cannot recover from on their own.

## Verification plan and evidence

```sh
./init.sh
./gradlew :shared:jvmTest --rerun-tasks          # expect the prior 192 tests, 0 failures, none removed
./gradlew :shared:testAndroidHostTest --rerun-tasks
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks
./init.sh --verify
git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml   # expect 1 0
grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt   # only theme/
grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src   # none
grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src desktopApp/src   # none
git diff --check
```

Android (real emulator; `adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk`,
`adb shell settings put system font_scale 2.0` then `1.0`,
`adb shell uiautomator dump … && adb pull …`) — record for **both** forms: the `content-desc` of all
eight option nodes at 1.0 and 2.0; the minimal clickable-node size; whether any node falls outside
`0..width × 0..height`; the name field `focused="true"` after a blank-name save with
`add_land_name_error` visible; that correcting the name saves one land with the list confirmation;
and one edit of one of two lands leaving the other row unchanged. Known harness quirk: a tap inside
the IME window can type instead of pressing a button — dismiss the keyboard first.

Desktop: `./init.sh --desktop`, then Tab/Shift+Tab through the fields and options, type into the name
and municipality fields, activate an option and `Guardar terreno`/`Guardar cambios` by keyboard, and
read the values/control names from the AX tree; resize narrow (≈420pt) and wide (≥1000pt) and record
wrapping. If the visual focus indication cannot be inspected (host screen capture was denied before),
record that exact limitation and rely on the default Material indication — do not add an outline on a
guess.

Preview review: every add/edit preview, including the blank-name error preview and the new narrow +
`fontScale = 2f` error preview, re-checked in greyscale for the non-colour-cue requirement.

Low-digital-confidence manual validation (the feature-list note) — record each task as run or as an
outstanding manual check: (1) add a land with only a name; (2) add a second with a municipality and
both attributes; (3) explain what `No lo sé` means and what happens if they choose it; (4) leave the
name empty, read the message and correct it without help; (5) find `Editar` and correct one land's
name. Never claim this session if no reviewer was available.

Capture: focused and full test counts before/after, the `strings.xml` numstat, the greps, the Android
dump excerpts/screenshots, the Desktop AX/keyboard record with its limits, the TalkBack attempt
outcome, and the manual-validation record (or its absence). No persistent E2E command and no Compose
UI-test harness exist, so no automated UI/E2E result is claimed.

## Honest limitations to record

- No Compose UI-test harness and no test-only dependencies, so the accessible names,
  `selectableGroup`, heading and announcement are verified by the Android node dump, the Desktop AX
  tree and source inspection — never by an automated UI test.
- TalkBack speech is not capturable here, so "announced" rests on the semantics wiring plus the
  focused-field dump; never claim a heard announcement.
- `uiautomator` exposes neither merged nodes nor headings, so the group association and heading rest
  on the Compose semantics plus the exposed `content-desc`; record this per check.
- The Desktop visual focus indication may stay unverifiable (host screen capture denied); the default
  Material indication is relied on rather than adding an unverified outline.
- Focus on the name field opens the Android IME (expected, recorded); no autofocus happens on entry.
- The low-digital-confidence validation is a human session; if it is not run it stays an outstanding
  manual check (never claimed).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One "Land form accessibility" MUST rule (group-qualified option names, `selectableGroup`, heading, announced + refocused name error) so a later screen cannot silently drop it. |
| `DESIGN.md` | **Update during implementation** | Extend "Accessibility and validation" with the land add/edit baseline actually checked and the remaining gaps; that section forbids claiming accessibility before these checks. |
| `docs/specs/add_land.md`, `docs/specs/edit_land.md` | **Append one short note each after implementation** | The deferred accessibility validation (and `edit_land` F3/F6) is closed or explicitly deferred from this side; accepted behavior is not revised. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record status, the checks actually run and every unperformed/manual limit; planning does not touch them. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, `ARCHITECTURE.md`, `init.sh` | Not needed | The plain-Spanish/accessibility/shared-`commonMain` rules already govern; no product, domain, module, boundary, or script-mode change is introduced. |

## Risks and open decisions

- **R1 No Compose UI-test harness** — semantics, focus and announcements cannot be asserted in unit tests; mitigated by the node dump, the AX tree, previews and honest limits.
- **R2 Group-prefixed names are verbose** — TalkBack reads `Riego: No lo sé` for every option; accepted, because two identical `No lo sé` options are the worse failure.
- **R3 Focus move vs Android IME** — focus opens the keyboard; accepted as helpful for correcting and recorded so it is not later "fixed" as a bug.
- **R4 Announcement not capturable** — no claim beyond the wiring plus the focused-field evidence.
- **U1 Visible wording of unknown/mixed options** — accepted copy; rewording needs a copy review (visible text stays byte-identical here).
- **U2 Large-window layout** — wide-window adaptation of the land columns stays with `desktop_mvp_build`.
- **U3 Compose UI-test dependency later** — deliberately not now (repo precedent).

## Validator checklist

- [ ] Both forms' option rows expose a group-qualified accessible name (`Riego: No lo sé`, `Producción: No lo sé`, …) inside a `selectableGroup`, reporting role and selected state, with no extra focus stop added.
- [ ] Both form titles carry `heading()`; every control keeps a plain-Spanish visible label; no visible string changed.
- [ ] A blank-name save writes nothing, shows the unchanged message, moves input focus to the name field (a repeated attempt re-focuses), preserves every value and selection, and clears the error when typing resumes; correcting it writes exactly one record.
- [ ] The storage-failure and missing-land messages stay polite live regions with no confirmation, no success navigation and the values still on screen.
- [ ] At `font_scale 2.0` / `fontScale = 2f` and `widthDp = 320` the forms wrap with no clipping, overlap or horizontal overflow and stay scrollable.
- [ ] On Android every clickable node is ≥48dp with no minimum-size override, and the error state is never colour-only (greyscale cue recorded).
- [ ] On Desktop the form is completable and correctable by keyboard only, with a visible focus indication or the exact limitation recorded, and the AX tree shows named controls.
- [ ] `strings.xml` numstat is exactly `1 0`, the new key matches this spec byte-for-byte and is used only as an accessible name.
- [ ] No `Color(0x` outside `theme/`; no logging; no new module, dependency, Gradle change, endpoint, permission, or Compose UI-test artifact.
- [ ] `:shared:jvmTest --rerun-tasks` (previous 192 tests, none removed), `:shared:testAndroidHostTest`, the iOS compile, the Android/Desktop builds, `./init.sh --verify`, and `git diff --check` pass, or the exact blocker is reported.
- [ ] Only the two form screens, `strings.xml`, `CONSTRAINTS.md`, `DESIGN.md`, the two spec notes and the new spec changed; the reducers, repository, `App()`, the list/removal/privacy/chat surfaces, `theme/`, entry points, `contracts/`, `backend/`, `knowledge/`, Gradle and `init.sh` are untouched; the low-digital-confidence check is recorded as run or outstanding; `feature_list.json`/`PROGRESS.md` changed only after independent validation.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
# No new test class: this feature is verified through the forms' existing reducers plus the
# manual screen-reader and keyboard checks recorded in the evidence below.
./gradlew :shared:jvmTest --tests AddLandStateTest --tests EditLandStateTest
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Scope and implementation: only the two stateless land form screens and the catalog changed. shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt and EditLandScreen.kt gained (1) Modifier.semantics { heading() } on the form title, (2) a remember { FocusRequester() } on the name field with focus requested from the save path (handleAction wraps onAction: `if (action is …SaveClicked && !state.hasName) nameFocus.requestFocus()`), so the unchanged visible error Text (now LiveRegionMode.Polite) and the field `error(nameErrorMessage)` semantics make a blank-name save announce the message and re-focus the field even on a repeated attempt, (3) a nested Column(Modifier.fillMaxWidth().selectableGroup()) holding exactly the four option rows, each row keeping its single `selectable(role = RadioButton)` and adding `semantics { contentDescription = stringResource(add_land_choice_description, label, stringResource(choice.label)) }` — no extra focus stop and selected state still from `selectable`, and (4) one combined narrow/large-font error Preview each (widthDp = 320, fontScale = 2f, showNameError = true). shared/src/commonMain/composeResources/values/strings.xml gained exactly one key, add_land_choice_description = '%1$s: %2$s' (numstat 1 0); it is used only as an accessible name, never as visible body text. No visible copy or layout changed (the nested column re-creates the previous 4dp inter-row spacing, so geometry is unchanged). Not changed: AddLandState.kt, EditLandState.kt, Land.kt, LandDraft.kt, LandRepository.kt, the storage adapters/format, LandListScreen.kt, RemoveLandScreen.kt, PrivacyScreen.kt, App.kt, ChatHomeState.kt, ChatConversation.kt, chat/, privacy/, theme/, androidApp/, desktopApp/, shared/src/iosMain/, contracts/, backend/, knowledge/, every Gradle file and init.sh; no new module, dependency (including test-only), ViewModel, coroutine, navigation, dialog, Compose UI-test harness, or logging.
- Automated checks (repository root): python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'; ./gradlew :shared:jvmTest --rerun-tasks -> BUILD SUCCESSFUL, 21 suites / 192 tests / 0 failures (unchanged from the accepted baseline; no test removed or renamed); ./gradlew :shared:testAndroidHostTest --rerun-tasks -> BUILD SUCCESSFUL, 17 suites / 178 tests / 0 failures; ./gradlew :shared:compileKotlinIosSimulatorArm64 -> BUILD SUCCESSFUL; ./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks -> BUILD SUCCESSFUL (72 tasks; androidApp-debug.apk 36,014,513 bytes); ./init.sh --verify -> exit 0 (91 tasks). git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml -> '1 0'; `grep -rn Color(0x shared/src/commonMain/kotlin/com/jamarglex/manijero --include=*.kt` -> only theme/ManijeroColors.kt; no LocalMinimumInteractiveComponentSize/minimumInteractiveComponentSize in shared/src; the println/Log./Logger/printStackTrace/NSLog grep over shared/src androidApp/src desktopApp/src -> no matches; git diff --check -> clean.
- Android evidence (real emulator-5554, Medium_Phone_API_35, 1080x2400, density 2.625; adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk, adb shell settings put system font_scale 1.0/2.0, adb shell uiautomator dump; raw dumps/screenshots kept outside the repo): both forms expose all eight option content-desc values at font_scale 1.0 AND 2.0 — 'Riego: No lo sé', 'Riego: Secano', 'Riego: Regadío', 'Riego: Una parte de regadío y otra de secano', 'Producción: No lo sé', 'Producción: Convencional', 'Producción: Ecológico', 'Producción: Una parte de cada uno' — and each row reports checkable=true/checked=true plus a RadioButton fake node (role); Compose intentionally reports an already-selected radio as clickable=false (source-verified). The smallest fully-visible clickable node measures 48.0dp at 1.0 and 53.3-66.7dp at 2.0; no node falls outside 0..1080 x 0..2400; at 2.0 there is no horizontal overflow (max text right edge 1017/1080). A blank-name save on BOTH forms shows the name field focused=true with 'Escribe un nombre para el terreno.' visible, and after moving focus to the municipality field a second blank save re-focuses the name field; correcting the name wrote exactly one record with the accepted confirmation and left the other lands unchanged (the add form also saved a new land and the edit form updated exactly one of the existing rows). TalkBack 15.0.0 is installed and enabled (enabled_accessibility_services = com.google.android.marvin.talkback/…TalkBackService); screenshots show its green accessibility-focus rect on the name error field and its hover highlight on the 'Producción: No lo sé' row, but no spoken utterance was captured (adb logcat held only TalkBack 'node is null' lines) — matching spec limitation R4.
- Desktop evidence (real ./init.sh --desktop :desktopApp:run, window 'Manijero'; the macOS accessibility tree via JXA/System Events): the add form exposes the title 'Añadir terreno' (AXStaticText), the named fields 'Nombre del terreno'/'Municipio (opcional)', all eight option rows as AXRadioButton with the group-qualified names (e.g. 'Riego: No lo sé', 'Producción: Ecológico') and a 0/1 selected value, and the named 'Guardar terreno'/'Cancelar'; the edit form shows the same with prefilled values and 'Guardar cambios'. Keyboard-only completion: Tab moved between the two text fields, each option row is its own tab stop, and Space selected an option (2 Tabs+Space selected 'Riego: Secano'; 3 Tabs+Space selected 'Producción: Ecológico'); 2 more Tabs+Space on 'Guardar terreno' saved the land and returned to the list with 'El terreno se ha guardado en este dispositivo.' and the new row; Shift+Tab moved back from municipality to the name field (typed 'Y' landed there). Blank-name: activating Guardar with a blank name wrote nothing and stayed on the form, the field description became 'Nombre del terreno, Escribe un nombre para el terreno.', and typing immediately (no explicit focus) landed in the name field; after moving focus to another field and re-activating Guardar the typed text again landed in the name field (repeated attempt re-focuses), the error cleared as typing resumed, and correcting+saving wrote exactly one updated record with 'Los cambios se han guardado en este dispositivo.' while the other row stayed unchanged. Window resize: at 420pt every content block is 372 wide at x=72 with the explanation wrapped to two lines and no horizontal overflow (the content is taller than the window, i.e. vertically scrollable); at 1200pt the explanation is a single line.
- Preview / non-colour-cue review: the name error is never colour-only — the unchanged visible message 'Escribe un nombre para el terreno.' is always rendered (confirmed in an Android screenshot) and also appears in the Desktop AX field description and in the Android field's error semantics. A greyscale render of the Android font_scale 2.0 error screen (temporary ImageIO converter, deleted after use) still shows the message text and the filled inner dot of the selected radio, so the state does not rely on colour.
- Honest gaps (never claimed as passed): (1) the Desktop per-element focus and the heading role are not exposed by the macOS AX tree (AXFocused stays false and the title is a plain AXStaticText), so the Desktop 'focus moved to the name field' evidence is behavioural (typed text landed in the name field) and the heading rests on the Compose semantics; uiautomator likewise exposes neither merged nodes nor headings. (2) The TalkBack announcement is never captured as speech (spec R4). (3) No Compose UI-test harness exists and the repo refuses test-only dependencies, so the accessible names, selectableGroup, heading, focus and announcement are verified by the Android dump, the AX tree, the previews and code inspection, never an automated UI test (spec R1). (4) The Desktop visual focus indication could not be inspected (host screen capture and per-element AXFocused unavailable), so the default Material indication was relied on and no outline was added. (5) The low-digital-confidence human validation (feature-list note) was NOT run — no reviewer was available — and stays an outstanding manual check. (6) feature_list.json/PROGRESS.md carry self-verification only; the feature is explicitly NOT marked accepted — independent validation is the next step.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/land_form_accessibility.md). It did not trust the implementer report and re-ran the contract validator, :shared:jvmTest --rerun-tasks (21 suites / 192 tests / 0 failures, none removed), :shared:testAndroidHostTest --rerun-tasks (17 suites / 178 / 0), :shared:compileKotlinIosSimulatorArm64, :desktopApp:build :androidApp:assembleDebug --rerun-tasks (72 tasks, fresh APK 36,014,513 bytes), ./init.sh --verify (exit 0, 91 tasks), and git diff --check; byte-for-byte checked the single new key add_land_choice_description = '%1$s: %2$s' (strings.xml numstat 1 0, referenced only as an accessible name in AddLandScreen.kt); confirmed the Color(0x) (only theme/), minimumInteractiveComponentSize (none) and logging (none) greps; and rebuilt/re-installed the APK on a real emulator (font_scale 1.0/2.0) to reproduce all eight group-qualified option content-desc, ≥48dp targets, no overflow, and the blank-name save re-focusing the name field on both forms with exactly one record written on correction, then re-drove the Desktop app through the macOS AX tree (eight AXRadioButtons with group-qualified names and selected state, keyboard-only completion, blank-name no-write with the field description carrying the error). It independently read Compose's SemanticsNode.emitFakeNodes source to confirm the content-desc fake child node is documented framework behavior, not a defect. Scope confirmed: only the two form screens, strings.xml, CONSTRAINTS.md, DESIGN.md, the two spec notes, the new spec, and feature_list.json/PROGRESS.md changed; reducers, repository, App(), list/removal/privacy/chat/theme, entry points, contracts/, backend/, knowledge/, Gradle files and init.sh untouched, no test file added or modified, no new module/dependency/logging. Findings N1-N5 non-blocking (N1 Desktop window resize not re-driven, AX size setter failed -10000; N5 carried honest limits including the outstanding low-digital-confidence manual check).
