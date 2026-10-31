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
- No change to `LandListScreen`, `RemoveLandScreen`, `PrivacyScreen`, the chat surface, `theme/`, entry points, `contracts/`, `backend/`, `knowledge/`, or `scripts/init.sh`.
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
- **Update** `CONSTRAINTS.md` (new "Land form accessibility" MUST rule); keep `DESIGN.md` to concise shared accessibility guidance and link to this feature's validation record rather than copying its evidence.
- **Append one short note each** to `docs/specs/add_land.md` and `docs/specs/edit_land.md`: the deferred accessibility checks are now done (precedent: the `response_states` U2 and `land_clarification` N2 notes).
- **Do not modify** `AddLandState.kt`, `EditLandState.kt`, `Land.kt`, `LandDraft.kt`, `LandRepository.kt`, the storage adapters/format, `LandListScreen.kt`, `RemoveLandScreen.kt`, `PrivacyScreen.kt`, `App.kt`, `ChatHomeState.kt`, `ChatConversation.kt`, `chat/`, `privacy/`, `theme/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, `contracts/`, `backend/`, `knowledge/`, any Gradle file, `scripts/init.sh`, and `feature_list.json`/`PROGRESS.md` while implementing.

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
| `DESIGN.md` | **Update during implementation** | Keep shared accessibility guidance concise and link to the authoritative validation record for form-specific evidence and remaining gaps; do not duplicate the report. |
| `docs/specs/add_land.md`, `docs/specs/edit_land.md` | **Append one short note each after implementation** | The deferred accessibility validation (and `edit_land` F3/F6) is closed or explicitly deferred from this side; accepted behavior is not revised. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record status, the checks actually run and every unperformed/manual limit; planning does not touch them. |
| `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, `ARCHITECTURE.md`, `scripts/init.sh` | Not needed | The plain-Spanish/accessibility/shared-`commonMain` rules already govern; no product, domain, module, boundary, or script-mode change is introduced. |

## Risks and open decisions

- **R1 No Compose UI-test harness** — semantics, focus and announcements cannot be asserted in unit tests; mitigated by the node dump, the AX tree, previews and honest limits.
- **R2 Group-prefixed names are verbose** — TalkBack reads `Riego: No lo sé` for every option; accepted, because two identical `No lo sé` options are the worse failure.
- **R3 Focus move vs Android IME** — focus opens the keyboard; accepted as helpful for correcting and recorded so it is not later "fixed" as a bug.
- **R4 Announcement not capturable** — no claim beyond the wiring plus the focused-field evidence.
- **U1 Visible wording of unknown/mixed options** — accepted copy; rewording needs a copy review (visible text stays byte-identical here).
- **U2 Large-window layout** — wide-window adaptation of the land columns stays with `desktop_mvp_build`.
- **U3 Compose UI-test dependency later** — deliberately not now (repo precedent).

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
# No new test class: this feature is verified through the forms' existing reducers plus the
# manual screen-reader and keyboard checks recorded in the evidence below.
./gradlew :shared:jvmTest --tests AddLandStateTest --tests EditLandStateTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/land_form_accessibility.appendix.md`](../archive/specs/land_form_accessibility.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/land_form_accessibility.md` remains the authoritative acceptance record.
