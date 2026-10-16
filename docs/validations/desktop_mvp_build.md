# Validation: `desktop_mvp_build`

- Feature id: `desktop_mvp_build`
- Spec: `docs/specs/desktop_mvp_build.md`
- Validator role: independent feature validator (feature-validator skill)
- Date: 2026-10-16
- Verdict: **revise** on first pass (core verification reproduced; one acceptance scenario was contradicted by measurement) → **accept** on second pass after the documentation repair (see “Second pass — repair re-validation” at the end).

## Review target

- Spec path: `docs/specs/desktop_mvp_build.md` (new, untracked).
- Claimed status in `feature_list.json`: `passing` (self-verified build/launch; the implementer reported the GUI journey smoke as blocked and did not claim it).
- Diff: modified `README.md` (one Desktop land-store line), `feature_list.json`, `PROGRESS.md`; new untracked `docs/specs/desktop_mvp_build.md`. No other path changed.
- **Did not trust the implementer's report.** The implementer claimed the GUI/AX route was denied (`AXIsProcessTrusted=false`, `osascript -1728`). In this session the macOS accessibility permission **was** available (`AXIsProcessTrusted` = `true`, `UI elements enabled` = `true`, `screencapture -x` wrote a real PNG), so the validator re-drove the whole smoke independently through the AX tree, with screenshots and per-screen AX dumps under gitignored `build/evidence-validator/`.

## Checks rerun and results

| Check | Result |
|---|---|
| `./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build --rerun-tasks` | exit `0`; `BUILD SUCCESSFUL`; **91 actionable tasks: 91 executed, 0 from cache** |
| `:shared:jvmTest` | **192 tests / 0 failures / 0 errors** (21 suites) |
| `:shared:testAndroidHostTest` | **178 tests / 0 failures / 0 errors** (17 suites) |
| `:androidApp:assembleDebug` | `androidApp/build/outputs/apk/debug/androidApp-debug.apk` 36,014,513 bytes, sha256 `4b4ab9d6cc50e026436116defdf3ffb79023dc84b7c715c6ce9b2c8e874ed538` (byte-identical to the recorded claim) |
| `:desktopApp:build` | runs; produces the JVM run target (`desktopApp/build/classes/kotlin/main/com/jamarglex/manijero/MainKt.class`) |
| `./init.sh --desktop` (launch 1 and 2) | `:desktopApp:run`; window "Manijero" opened; run log has no exception/stack trace/error; clean `BUILD SUCCESSFUL` / exit `0` on close (both runs) |
| `init.sh` byte-unchanged | `git diff --exit-code -- init.sh` → no output (exit 0) |
| Scope | `git status --porcelain` = `M PROGRESS.md`, `M README.md`, `M feature_list.json`, `?? docs/specs/desktop_mvp_build.md`; `git diff --check` clean |
| Logging grep | `println|Log.|Logger|printStackTrace|System.out|NSLog` over `shared/src androidApp/src desktopApp/src` → **no matches** |
| No `/ask`/grounded path | `backend/app/main.py` exposes only `@app.get("/health")`; `App(answerService = UnavailableAnswerService)` default; `UnavailableAnswerService.ask` throws |

## Independent GUI reproduction (real `:desktopApp:run`, window "Manijero", macOS AX tree)

Method: JXA/`System Events` driver (`build/evidence-validator/ax/ax.js`), walking and pressing/dumping the AX subtree; a full-screen `screencapture` raised to the window for each screen. Window 800x600 at (48,81) on launch; resized to 1400x900 through the AX setter for the wide-window read.

- **Chat home** (`01-chat-home*`): title `¿En qué puedo ayudarte?`, description, three suggestion `AXButton`s named by their question text, composer `AXTextField` `Escribe tu pregunta`, `Preguntar` (disabled while empty) and `Mis terrenos`, the privacy summary and `Privacidad y ayuda`. One centred 720-wide column at x=88 in the 800 window.
- **Suggested question → composer** (`02-*`): pressing `¿Qué es el SIGPAC y para qué sirve?` set the composer value to exactly that text.
- **Submit → honest failure** (`02-failure*`, `03-retry.json`): pressing `Preguntar` produced **one merged `Tú, ¿Qué es el SIGPAC y para qué sirve?` transcript node** and the plain-Spanish notice `El servicio no está disponible en este momento, así que todavía no tengo tu respuesta. Inténtalo otra vez dentro de un momento.` with a separate `Reintentar` `AXButton`. There were **0** `Asistente`-bearing nodes — the question is never rendered as an answer. `Reintentar` re-produced the same notice with still exactly one `Tú` entry (no duplicated user message).
- **Privacy notice** (`04-*`, `05-*`): `Privacidad y ayuda` opened the shared notice (all sections: qué se guarda / qué se envía with the three attribute bullets / qué no puedo prometer / dónde pedir ayuda); `Volver` returned to the chat home with state preserved.
- **Land journey** (`06-*` … `13-*`, `17-*`):
  - empty `Mis terrenos` (`Todavía no has guardado ningún terreno…`);
  - add name-only `Los Olivos` → `El terreno se ha guardado en este dispositivo.`, one row `Los Olivos, Riego: No lo sé, Producción: No lo sé`, store gained exactly one record `land-…|Los Olivos||UNKNOWN|UNKNOWN|||0|0`;
  - blank-name `Guardar terreno` wrote nothing, showed `Escribe un nombre para el terreno.`, and left input focus on the name field (typing then landed in it) — the accepted recoverable path, reproduced;
  - add full `La Solana` (Martos / `Riego: Regadío` / `Producción: Ecológico`) → second record `land-574287fb556f4dc6|La Solana|Martos|IRRIGATED|ORGANIC`; list showed both lands in creation order with their attributes; the AX radio rows report the group-qualified names and a `0`/`1` selected value (this bridge **does** reflect selection, unlike the Android `uiautomator` dump);
  - edit `La Solana` → `La Solana Alta` → `Los cambios se han guardado en este dispositivo.`, **exactly one** record changed (same id, municipality/attributes intact) and the other row was untouched;
  - remove `Los Olivos` → the confirmation named the exact land and wrote nothing until `Eliminar el terreno` was pressed → `El terreno se ha eliminado de este dispositivo.`, **exactly one** record removed (store left with the single `La Solana Alta` row);
  - **persistence**: closed the window (AX close button → clean exit), relaunched; the new app shows only `La Solana Alta, Municipio: Martos, Riego: Regadío, Producción: Ecológico`, matching `~/.manijero/lands-v1.txt` byte-for-byte.
- **Keyboard (Desktop)** (`keyboard3.js`): with the composer cleared, focusing the composer, `Shift+Tab` moved focus to the third suggestion (AX `AXFocusedUIElement` became the `AXButton` `¿Qué obligaciones tengo por la condicionalidad?`) and `Space` filled the composer with that exact text — keyboard reaches **and** activates controls.
- **Wide window 1400pt** (`14-*`, `15-*`, `16-wide-form.json`): see finding **H1** below.

## Findings

### H1 (blocking for the wording; no product change) — the `720dp capped/centred` claim does not hold for the lands list or the forms

- Severity: **high** (as a spec/record-accuracy finding; the code behavior itself is pre-existing accepted behavior this slice must not change).
- Evidence (independently measured on the launched Desktop app at a 1400x900 window, x=60):
  - **Chat home**: every content block is 720 wide at x=400 — capped **and** centred (`15-wide-chat.json`, `15-wide-chat-crop.png`). At the 800x600 window it is 720 at x=88 (centred).
  - **`Mis terrenos` list**: content blocks are **1352** wide at x=84 — the full window minus the 24dp padding, i.e. **edge-to-edge, not capped and not centred** (`14-wide-1400.json`, `14-wide-1400-list-crop.png`). Even at the 800x600 window the list's `Añadir terreno` `AXButton` measured 752 wide at x=72.
  - **Add form**: title 190, but the name/municipality `AXTextField`s, all eight `AXRadioButton` rows, and `Guardar terreno`/`Cancelar` all measure **1352** wide at x=84 (`16-wide-form.json`). `EditLandScreen`/`RemoveLandScreen`/`PrivacyScreen` use the same shape (source: `.fillMaxWidth().widthIn(max = 720.dp)`).
- Cause (source inspection): the chat uses `.widthIn(max = ContentMaxWidth).fillMaxWidth()` (cap applied before fill, so it is real), while `LandListScreen`, `AddLandScreen`, `EditLandScreen`, `RemoveLandScreen` and `PrivacyScreen` use `.fillMaxWidth().widthIn(max = 720.dp)` (fill first, so the cap can no longer shrink it) and no `Alignment.CenterHorizontally`.
- Why it matters: the spec's acceptance scenario **"A large window keeps the phone layout from being stretched"** states that when *the chat home, the lands list, and a form* are shown, "the content stays a single capped, centred readable column (the accepted `ContentMaxWidth = 720.dp`) rather than stretching edge to edge". That is true for the chat home and **false for the lands list and the forms**, which stretch to the full window. The validator checklist repeats the same over-broad claim. The feature's whole point is to leave the repository's Desktop story truthful, so the record must not carry this claim.
- Note on origin: this is **pre-existing** behavior, not introduced here. The accepted `chat_accessibility` slice scoped the centring to `ChatHomeScreen` only, and the `land_form_accessibility` validation explicitly recorded that the wide-window wrapping "was not independently reproduced" (so the land-screen geometry was never actually measured wide). Per this spec's own rule ("a smoke discovery that contradicts an accepted feature is reported as a finding, not fixed inside this slice"), it is reported, not fixed.
- Required change: **documentation only, in this slice.**
  1. Correct the spec's wide-window acceptance scenario and the validator checklist so they claim the capped/centred column for the **chat home** only (the verified, accepted behavior), and explicitly record that the lands list/forms/privacy notice render full-width on a wide Desktop window.
  2. Record the land-screen/privacidad stretch as a finding/open item in the durable record (e.g. `DESIGN.md`'s wide-window note and/or `docs/risks-and-open-questions.md`), so it is not later mistaken for verified behavior.
  3. Update the `feature_list.json`/`PROGRESS.md` evidence wording so it does not rest the wide-window claim on the land surfaces.
  4. Do **not** change product code in this slice; if a capped/centred land layout is actually wanted, it is a separate product feature.
- Verification after fix: re-read the corrected spec/checklist/record against the measurements above; the AX evidence already exists (`14-*`, `15-*`, `16-wide-form.json`).

### L1 (non-blocking, evidence wording) — the implementer's AX-blocked claim did not reproduce

- Severity: low.
- Evidence: `feature_list.json`/`PROGRESS.md`/`build/evidence-desktop/session-evidence.md` record `AXIsProcessTrusted=false` and `osascript … (-1728)` / `(-609)`. In this validation session the same host reports `AXIsProcessTrusted` `true`, `UI elements enabled` `true`, one System Events process query succeeded, and `screencapture -x` wrote a real 2.5 MB PNG; the entire journey was driven through the AX tree unchanged.
- Why it matters: the implementer's "blocked" record is honest for their session but is environment-dependent, not a permanent property; leaving it as the durable reason for an unfinished smoke could mislead a future session.
- Required change: none blocking. When the record is updated, phrase the limitation as "the accessibility/AX permission and screen-recording permission were not available in the implementer's session" rather than "the GUI cannot be driven".

### L2 (informational) — harness artifact only

- The AX bridge on this host does not honour writes to a Compose text field's value (`AXValue`/`AXSelectedTextRange` reads/writes fail or are ignored), and a plain `keystroke` inserts at the cursor. The validator cleared a field by moving to end (right arrow) then backspacing before typing; one intermediate edit produced the concatenated name `La Solana AltaLa Solana`, which was then corrected. This is a limitation of the AX driver, **not** a product defect: every saved value was re-read from the field and the store file.
- No product impact.

## Verification claims NOT made

- **No grounded/answered/abstained/source-card render** is reachable (shipped default `UnavailableAnswerService`, backend `/health` only) — not claimed.
- **No packaged installer** (Dmg/Msi/Deb) is built or claimed; only the JVM run target is produced/launched.
- **No Windows/Linux or physical-device claim**; single macOS host only.
- **No screen-reader speech** claim (no utterance captured).
- **No automated UI/E2E harness** exists; verification is manual AX driving + run log.

## Security assessment

The security checklist found no blocking issue. This slice changes no product, backend, contract, or knowledge code; no new network route, permission, dependency, secret, module, mode, endpoint, or persistence path; the app writes only the documented `~/.manijero/lands-v1.txt` (created and then removed to restore the original absent state); the logging grep shows no land/question content is logged; and the artifact is a debug JVM run target. The one code-adjacent observation (H1) is a layout/documentation-accuracy issue, not a security or privacy one.

## Documentation / harness state

- `README.md` "Running the MVP targets" now names the Desktop land store `~/.manijero/lands-v1.txt` (the shared `land-store-v1` format, remove to start empty) next to the existing `--verify`/`--android`/`--desktop` commands, the Android debug APK path, the no-`/ask` limitation, and the iOS-out-of-scope statement. Truthful and verified.
- `init.sh` is byte-unchanged and its `--check` banner remains Desktop-truthful.
- The durable wide-window claim is **not** yet truthful for the land surfaces (H1) and must be corrected before acceptance.
- `PROGRESS.md` / `feature_list.json` honestly leave the slice at `passing` with the GUI smoke flagged as not driven; the evidence text understates what can be verified here (L1).

## Verdict (first pass)

> Superseded by **accept** in “Second pass — repair re-validation” below.

**revise.** The core verification is fully reproduced independently: `./init.sh --verify` succeeds (91 tasks, all executed; `:shared:jvmTest` 192/0, `:shared:testAndroidHostTest` 178/0; byte-identical APK), `./init.sh --desktop` opens the "Manijero" window with no exception and closes cleanly, the chat home with its honest failure notice + `Reintentar` (question only ever a `Tú` entry), the privacy notice, the full land journey (add name-only, add full, list, edit exactly one, remove exactly one, relaunch persistence matching the store), and keyboard reach/activation all work on Desktop. Scope is clean and `init.sh` is byte-unchanged.

The single blocker is H1: the spec's wide-window acceptance scenario and the validator checklist assert a capped, centred column for the lands list and a form, and independent measurement shows those surfaces (and the privacy notice) stretch edge-to-edge while only the chat home is capped/centred. Because this feature exists to make the repository's Desktop story truthful, the spec/checklist/record wording must be corrected (and the land-screen stretch recorded as a finding/open item) before acceptance. No product code should change in this slice.

Recommended state update: keep `desktop_mvp_build` at `passing` (do not set `accepted`) until the H1 documentation repair is applied and re-checked; then the orchestrator may persist acceptance. The implementer's AX-blocked record (L1) should be re-worded as an environment-specific limitation.


## Second pass — repair re-validation (2026-10-16)

Re-validated after the implementer's documentation-only repair. **No product/Gradle/contracts/backend/knowledge/`init.sh` change was made by the repair** — the product code is byte-identical to the code fully reproduced in the first pass.

### Repair scope confirmed

- `git status --porcelain` → `M DESIGN.md`, `M PROGRESS.md`, `M README.md`, `M docs/risks-and-open-questions.md`, `M feature_list.json`, `?? docs/specs/desktop_mvp_build.md`, `?? docs/validations/desktop_mvp_build.md`. **No `shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, `knowledge/`, Gradle, or version-catalog path appears.**
- `git diff --stat` → only `DESIGN.md`, `PROGRESS.md`, `README.md`, `docs/risks-and-open-questions.md`, `feature_list.json` (+27/-3).
- `git diff --check` → clean (exit 0); `git diff --exit-code -- init.sh` → no output (exit 0), `init.sh` byte-unchanged.
- Logging grep (`println|Log.|Logger|printStackTrace|System.out|NSLog` over `shared/src androidApp/src desktopApp/src`) → **no matches**.

### H1 (previously blocking) — RESOLVED

The over-broad wide-window claim is gone from every durable surface:

- **Spec** (`docs/specs/desktop_mvp_build.md`): the wide-window acceptance scenario now reads "when the chat home is shown, then the chat content stays a single capped, centred readable column … The lands list, the add/edit/remove land forms, and the privacy notice do **not** share this cap: on a wide Desktop window they render full-width (edge-to-edge), because they use `.fillMaxWidth().widthIn(max = 720.dp)` with no `Alignment.CenterHorizontally`." The goal, source-metadata, technical approach, visual-design, durable-doc and risk sections were re-worded to the same effect (lines 12, 16, 54, 72, 75, 99, 121, 125, 135, 146, 171, 201).
- **Validator checklist**: the wide-window item now says the capped/centred column is the **chat home** and explicitly "Do **not** claim the lands list, the land forms, or the privacy notice are capped/centred: they render full-width in a wide window (recorded finding H1, pre-existing chat-home-only cap)."
- **`DESIGN.md`**: a new "Wide-window cap is chat-home-only (recorded finding, pre-existing)" bullet records the measurement (chat home 720pt at x=400; list/forms/privacy 1352pt at x=84), the `.fillMaxWidth().widthIn(max=720.dp)` cause, and that it is not verified as capped/centred. It sits immediately after the pre-existing "Wide windows … capped and centred" bullet (which is under the `chat_accessibility` baseline heading and remains true for the chat), so the two do not contradict.
- **`docs/risks-and-open-questions.md`**: a new row tracks "whether the lands list/forms and the privacy notice should share the chat home's 720dp capped/centred column … they currently render full-width — pre-existing, recorded as finding H1".
- **`feature_list.json` / `PROGRESS.md`**: the wide-window evidence bullet no longer rests on the land surfaces — it states the cap "rests only on the already-accepted chat-surface baseline … It is NOT rested on the land surfaces", and the notes field records the chat-home-only cap as finding H1. L1 is re-worded as environment-specific ("the macOS accessibility/AX and screen-recording permissions were not available in the implementer's session … not a claim that the GUI cannot be driven").

### Core verification re-confirmed

- `./init.sh --verify` → **BUILD SUCCESSFUL** (91 actionable tasks; 3 executed / 88 up-to-date — nothing changed since the first-pass `--rerun-tasks` rebuild). Because no product file changed, the first-pass results still hold byte-for-byte: `:shared:jvmTest` 192/0 (21 suites), `:shared:testAndroidHostTest` 178/0 (17 suites), byte-identical debug APK 36,014,513 bytes / sha256 `4b4ab9d6…ed538`.
- Quick Desktop launch re-run: `./init.sh --desktop` reached `> Task :desktopApp:run`; the OS/System Events AX query in this session reported a window titled **"Manijero"**, **800×600**, `AXTitle` = `Manijero`, then closed cleanly. (This session still holds the AX permission, unlike the implementer's.)
- No grounded-answer / packaged-installer / other-OS / speech claim appears in the spec, `DESIGN.md`, `docs/risks-and-open-questions.md`, `feature_list.json`, or `PROGRESS.md`; all four are explicitly disclaimed.

### Remaining minor observation (non-blocking)

- **L3 (informational):** the first `feature_list.json` evidence bullet still says "only `README.md` … `feature_list.json`, and `PROGRESS.md` changed (plus the untracked spec)", which no longer enumerates `DESIGN.md` and `docs/risks-and-open-questions.md` added by the H1 repair. It is not a false product claim (the later "Validator H1" bullet and the `PROGRESS.md` implementation row both list those files), so the record is not contradictory, but the bullet could be tightened to name all changed docs. No product, behavioral, or acceptance impact.

### Second-pass verdict

**accept.** H1 is fully resolved: the spec and validator checklist now claim the capped/centred 720dp column for the chat home only and record the land/privacidad full-width behavior as a finding; `DESIGN.md` and `docs/risks-and-open-questions.md` carry the finding; and `feature_list.json`/`PROGRESS.md` no longer rest the wide-window claim on the land surfaces and re-word L1 as environment-specific. The repair is documentation-only — the product code is byte-identical to the first-pass-verified build (`./init.sh --verify` still succeeds; the "Manijero" window re-opened 800×600). Scope is clean, `init.sh` is byte-unchanged, and no forbidden claim is made. Recommended state update: `desktop_mvp_build` may be persisted as `accepted` by the orchestrator. **Do not** treat the record as accepted until the orchestrator writes that status.
