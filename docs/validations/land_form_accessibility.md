# Validation — `land_form_accessibility`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted `land_form_accessibility`
implementation against `docs/specs/land_form_accessibility.md`.

Feature id: `land_form_accessibility`. Spec: `docs/specs/land_form_accessibility.md`.
Claimed status: `passing` (self-verified by the implementer). State update: the orchestrator sets
`status` to `accepted` and records concise evidence.

The validator did not implement or repair anything in the product. It re-read the diff, re-ran the
acceptance checks from a clean `--rerun-tasks` baseline, rebuilt and re-installed the debug APK on a
real Android emulator, re-drove the two forms with `uiautomator` at `font_scale` 1.0 and 2.0, and
re-drove the Desktop app through the macOS accessibility tree. It applied the rubric/security criteria
from the `feature-validator` skill body (its `references/` files are absent in this worktree).

## Review target

`git status --porcelain` before and after validation showed exactly the implementer's footprint
(unchanged by validation; no probe file and no repo file was created or edited by the validator):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- Modified (docs/harness): `CONSTRAINTS.md`, `DESIGN.md`, `docs/specs/add_land.md`,
  `docs/specs/edit_land.md`, `feature_list.json`, `PROGRESS.md`.
- New (docs): `docs/specs/land_form_accessibility.md` (planner artifact).

Untouched, as the spec's "do not modify" list requires: `AddLandState.kt`, `EditLandState.kt`,
`Land.kt`, `LandDraft.kt`, `LandRepository.kt`, the storage adapters/format, `LandListScreen.kt`,
`RemoveLandScreen.kt`, `PrivacyScreen.kt`, `App.kt`, `ChatHomeState.kt`, `ChatConversation.kt`,
`chat/`, `privacy/`, `theme/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, `contracts/`,
`backend/`, `knowledge/`, every Gradle file and the version catalog, and `init.sh`. No test file was
added or modified (the repo refuses test-only dependencies), so the test surface is byte-identical to
the accepted baseline. `git diff --check` clean. No new module, dependency, ViewModel, coroutine,
navigation, dialog, permission, endpoint, Compose UI-test artifact, or logging.

## Independent checks and results

Re-run by the validator with `--rerun-tasks` where relevant, so results are real executions:

- `python3 contracts/validate_examples.py` → exit 0, "Validated 2 request and 3 response examples
  against answer_api_contract".
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **21 suites / 192 tests / 0 failures**
  (report XML). Every prior suite is present with its prior count (`ChatHomeStateTest` 44,
  `AddLandStateTest` 11, `EditLandStateTest` 12, `LandContextBuilderTest` 16,
  `CitationPresentationTest` 23, `ManijeroColorsTest` 10, `TranscriptScrollTest` 8, …); the total is
  unchanged from the accepted 192 baseline, so no test was removed or renamed.
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, **17 suites / 178 tests /
  0 failures** (report XML; unchanged).
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL, 72
  actionable tasks executed; fresh `androidApp-debug.apk` (36,014,513 bytes).
- `./init.sh --verify` → **exit 0**, BUILD SUCCESSFUL (91 actionable tasks).
- `git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml` → `1 0`. The
  single added line is `<string name="add_land_choice_description">%1$s: %2$s</string>`, byte-identical
  to the spec's copy contract; `add_land_choice_description` appears exactly once and is referenced only
  from `AddLandScreen.kt` (in the option `contentDescription`), never as visible body text.
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include="*.kt"` → only
  `theme/ManijeroColors.kt`.
- `grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src` →
  no matches (exactly what the spec forbids). Logging grep
  (`println|Log\.|Logger|printStackTrace|NSLog` over `shared/src androidApp/src desktopApp/src`) →
  no matches.
- `git diff --check` → clean.

### Android re-drive (real `emulator-5554`, `Medium_Phone_API_35`, 1080×2400 @ density 2.625)

The validator rebuilt and re-installed the shipped debug APK itself
(`adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk`), set
`settings put system font_scale` to 1.0 and 2.0, and dumped with `uiautomator`.

- **Group-qualified option names, reproduced at 1.0 and 2.0, on both forms.** All eight option
  `content-desc` values are exactly `Riego: No lo sé`, `Riego: Secano`, `Riego: Regadío`,
  `Riego: Una parte de regadío y otra de secano`, `Producción: No lo sé`, `Producción: Convencional`,
  `Producción: Ecológico`, `Producción: Una parte de cada uno`. Each option row is a `View` with
  `checkable=true`/`checked=`true|false` and `clickable=true` (the already-selected radio reports
  `clickable=false`), containing a child `View` carrying the group-qualified `content-desc`, the
  visible `TextView`, and a `RadioButton` role node.
- **Why the content-desc is on a child node — verified against the Compose source, not taken on
  trust.** The validator extracted `ui-android-1.12.1-sources.jar` and read `SemanticsNode.emitFakeNodes`
  (`commonMain/androidx/compose/ui/semantics/SemanticsNode.kt:459-484`): when a merging node has both a
  `ContentDescription` and unmerged children, Compose emits a fake node at index 0 to carry the content
  description ("Fake node for contentDescription clobbering issue"), and the accessibility delegate
  requests the child list with `includeFakeNodes = true` (`replacedChildren`). The observed Android
  structure is therefore the documented framework behaviour, not a defect, and the name reaches
  assistive technology on the option node.
- **Targets and geometry.** At 1.0, after scrolling the form fully into view, every clickable node is
  ≥48dp (option rows 48.4dp; `Guardar terreno`/`Cancelar` 48.0dp; the two text fields 65.1dp). At 2.0
  the smallest clickable node is 66.7dp, the maximum text right edge is 1017/1080 (no horizontal
  overflow), and no node falls outside `0..1080 × 0..2400`. At 2.0 the forms are taller than the
  viewport and scroll (the Producción group and the buttons are reached by scrolling).
- **Recoverable blank-name save, add form, reproduced.** With a blank name, activating `Guardar
  terreno` stayed on the form, showed `Escribe un nombre para el terreno.`, and left the name field
  `focused="true"` (the field is an `EditText` with `focused="true"` in the dump). Typing a name
  cleared the message; activating `Guardar terreno` again saved exactly one new record with the
  accepted `El terreno se ha guardado en este dispositivo.` confirmation and the new row in the list.
- **Recoverable blank-name save, edit form, reproduced.** Opening `Editar` for a stored land, clearing
  the name to whitespace, and activating `Guardar cambios` stayed on the form, showed the same
  unchanged message, and left the name field `focused="true"`. Correcting the name and saving wrote
  exactly one updated record (`Los cambios se han guardado en este dispositivo.`) while the other rows
  stayed unchanged.
- **Heading semantics** are not exposed by `uiautomator` (it shows the title as a `TextView`), so the
  `heading()` rests on the Compose semantics and source inspection (spec limitation, recorded).
- TalkBack is not asserted as speech: the validator did not capture an uttered announcement, matching
  spec limitation R4; "announced" rests on the live-region + `error()` wiring, the focused-field dump,
  and the Desktop field description.

### Desktop re-drive (real `:desktopApp:run`, window "Manijero", macOS AX tree)

- **Named controls, group-qualified radio rows, and selected state.** The add form AX tree exposes
  `Añadir terreno` as `AXStaticText`, `Nombre del terreno`/`Municipio (opcional)` as `AXTextField`, all
  eight option rows as `AXRadioButton` with the group-qualified names and a `0`/`1` selected value
  (`Riego: No lo sé`=`1`, `Producción: No lo sé`=`1`), and named `Guardar terreno`/`Cancelar`. The edit
  form exposes the same with prefilled values.
- **Recoverable blank-name save, reproduced.** Activating `Guardar terreno` with a blank name stayed on
  the form (no navigation, no record) and the name field's accessible description became
  `"Nombre del terreno, Escribe un nombre para el terreno."`. Typing with no explicit focus/click
  landed the text in the name field (the field value became the typed string) and the error cleared —
  behavioural evidence that focus returned to the name field.
- **Keyboard-only completion, reproduced.** With no pointer, activating `Riego: Secano` and
  `Producción: Ecológico` and then `Guardar terreno` saved one land (`TecladoVal, Riego: Secano,
  Producción: Ecológico`) with the accepted confirmation and the new row; the validator then removed
  that row to restore the store to its prior two lands.
- **Window resize: not re-driven.** Setting the window size through the AX API
  (`win.size = {width, height}`) failed with `AppleEvent handler failed (-10000)` in this environment,
  so the 420pt/1200pt wrapping claim was not independently reproduced; it rests on the
  `widthDp = 320`/`fontScale = 2f` previews and the implementer's recorded Desktop geometry.

## Spec conformance

- **Group-qualified option names and group semantics.** `ChoiceGroup` now wraps exactly the four option
  rows in a nested `Column(Modifier.fillMaxWidth().selectableGroup())` (the group label stays outside
  it). Each row keeps its single `selectable(role = Role.RadioButton, onClick = …)` and adds
  `semantics { contentDescription = stringResource(add_land_choice_description, label,
  stringResource(choice.label)) }`. No second clickable/RadioButton focus stop was added, the selected
  state still comes from `selectable`, and the group is not merged into one node.
- **Heading.** Both titles carry `Modifier.semantics { heading() }` (source-verified; not exposed by
  `uiautomator` nor the macOS AX bridge).
- **Recoverable, announced name error.** Both screens hold a `remember { FocusRequester() }` on the
  name field and request focus from the save path via a `handleAction` wrapper
  (`if (action is …SaveClicked && !state.hasName) nameFocus.requestFocus()`), so even a repeated
  blank-name attempt re-focuses. The visible unchanged message is a `LiveRegionMode.Polite` `Text` and
  the field carries `semantics { if (state.showNameError) error(nameErrorMessage) }`. The reducers are
  untouched and already clear `showNameError` on the next edit and return `null` from `toDraftOrNull()`
  for a blank name, so "nothing is written" is reducer-level and tested.
- **No copy or layout change.** `strings.xml` numstat is `1 0`; the nested column re-creates the
  previous 4dp inter-row spacing, so the rendered geometry is unchanged (measured row heights/step match
  the accepted layout). No `Color(0x)` outside `theme/`; the name error keeps visible text plus
  `isError`, so no state is colour-only.
- **No new dependencies / I/O / state.** No Gradle change, no ViewModel, coroutine, navigation, dialog,
  Compose UI-test harness, or logging; the reducers, repository, and `App()` call sites are untouched.
- **Verification plan**: every command in the spec's plan was re-run by the validator with the exact
  results above (except the Desktop window resize, noted).

## Findings (non-blocking)

1. **Desktop window resize was not independently reproduced.** The AX size setter failed (`-10000`), so
   the 420pt/1200pt wrapping claim rests on the previews and the implementer's record. No code change
   needed; a future Desktop pass (or a manual resize) can confirm it.
2. **Documented wide-window width differs from the spec's plan.** `DESIGN.md`/`feature_list.json`
   record a 1200pt wide window while the spec's verification plan wrote "≥1000pt". Immaterial; both are
   wide windows and the cap/preview behaviour is unchanged.
3. **Android `content-desc` sits on a fake child node, not the option node.** This is Compose's
   documented `emitFakeNodes` workaround (source-verified) and the name reaches assistive technology, so
   no change is required. Recorded so a later reader does not mistake the split for a regression.
4. **One transient input failure during the validator's Android session.** A tap on the edit form's
   `Guardar cambios` was not delivered once (a system `droid.bluetooth` native crash occurred around the
   same time); after the emulator recovered, the same tap reproduced the expected focus + error. Not a
   product defect.
5. **Carried honest limits, not claimed as passed**: no Compose UI-test harness, `uiautomator`/macOS AX
   do not expose headings or merged nodes, the Desktop per-element focus attribute is unavailable,
   TalkBack speech is not capturable, and the low-digital-confidence human session stays an outstanding
   manual check (no reviewer was available). None of these is presented as passing in the diff.

## Security assessment

Scoped to the feature, its diff, and the directly supporting files. No relevant issue found; nothing
blocking.

- The change is UI-semantics only: it adds `selectableGroup()`, `contentDescription`, `heading()`,
  `error()`, a polite live region, and a `FocusRequester`. No I/O, no persistence, no network call, no
  permission, and no new dependency.
- The accessible name is built from two static Spanish resources (the visible group label and option
  label); no land name, municipality, id, or personal data enters the `contentDescription`, so the
  change cannot leak stored land data to assistive technology or logs.
- No logging was added (grep clean). `FocusRequester.requestFocus()` only moves input focus; it cannot
  move data or trigger a write, and `toDraftOrNull()` still refuses a blank name.
- `contracts/`, `backend/`, and `knowledge/` are untouched, so the wire contract and grounding rules
  cannot have shifted.
