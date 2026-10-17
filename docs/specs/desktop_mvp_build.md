# Feature Spec: `desktop_mvp_build`

## Source metadata

- **Feature:** `desktop_mvp_build` — Build the Desktop MVP artifact (area: `release`), `not_started` at planning (2026-10-16).
- **Depends on:** `suggested_questions`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `answer_land_scope` — all **accepted**.
- **Source behavior:** "The MVP can be built and launched on Desktop with the same shared Compose UI and business behavior."
- **Source verification:** "Run `./init.sh --verify`, launch the Desktop app, and complete one question and one land-management scenario."
- **Source note:** "Adapt layout and keyboard behavior for large windows rather than stretching the phone layout."
- **Carried handoff this feature closes:** `chat_question_submission` **F1** — the shipped app wiring is `UnavailableAnswerService` because the backend exposes no `/ask` route. This slice must be honest about it, not fix it (see Non-goals).
- **Sibling already accepted:** `android_mvp_build` (record `docs/validations/android_mvp_build.md`) proved the Android artifact and already corrected `init.sh`'s `--check` banner and the README "Running the MVP targets" section. This Desktop slice reuses that wording instead of re-deciding it.
- **Scope size:** release/verification slice. **No product behavior and no `commonMain` change.** One small durable README addition, one Desktop launch/journey smoke via the macOS accessibility tree, one evidence/validation record. The repository already carries the 720dp centred content cap (on the chat home; the land/privacy surfaces render full-width — a recorded pre-existing finding), the 720dp/wide-window and Desktop keyboard baselines, and the versioned local land store; this slice verifies them rather than rebuilding them. Correctly sized; well under the 100–250 line target after research.

## Goal

Prove that the accepted MVP runs as a real Desktop artifact and leave the repository's own instructions Desktop-truthful: `./init.sh --verify` builds the Desktop (JVM) target from the shared `commonMain` UI and behavior, `./init.sh --desktop` launches it (`:desktopApp:run`, window title "Manijero", lands stored by `FileLandStorage` at `~/.manijero/lands-v1.txt`), the accepted land journey and the chat home with its honest failure path work in that window, and the already-shipped 720dp centred content cap keeps a large window from stretching the phone layout **on the chat home** (the lands list, the land forms, and the privacy notice render full-width on a wide window — a pre-existing finding recorded, not fixed, by this slice). Also record the Desktop land-store location in the durable README so a new session does not have to rediscover it.

## Non-goals

- **No product code change.** Nothing in `shared/src/commonMain` (or any other source set), no new screen, state, string, or behavior; the accepted features are frozen. The chat-home 720dp cap, the keyboard behavior, and the store path already exist.
- **No `/ask` wiring and no backend change.** `UnavailableAnswerService` stays the default `App()` wiring, the backend keeps `/health` as its only route, and no model provider is configured. The smoke must state plainly that a question on the shipped Desktop app shows the plain-Spanish failure notice, not a grounded answer.
- **No new module, dependency, Gradle change, version-catalog change, mode, or CI/nightly automation.** `init.sh` gains no new mode and **needs no change at all** (the Android slice already made `--check` Desktop-truthful); `--verify`/`--desktop` stay as accepted.
- **No native installer/packaging.** `compose.desktop.nativeDistributions` declares `Dmg`/`Msi`/`Deb`, but this slice does not run `package*`/`createDistributable` and does not claim a signed or distributable installer. "Desktop packaging and supported operating systems" stays the open question it already is in `docs/risks-and-open-questions.md`.
- **No iOS release work.**
- **No new automated UI/E2E harness.** No Compose UI-test artifact, no instrumented test, no persistent E2E command (none exists; the repo refuses test-only dependencies).
- **No multi-OS or physical-device claim.** The smoke runs on the host macOS Desktop session only; record the OS and window reality. Do not claim Windows/Linux or a packaged build.
- **No accessibility re-audit.** `chat_accessibility` and `land_form_accessibility` already own the Desktop AX baselines (wide/narrow geometry, keyboard, named controls, group-qualified radio rows); this release smoke only confirms the launched artifact still renders and navigates.
- **No re-litigating accepted behavior.** A smoke discovery that contradicts an accepted feature is reported as a finding, not fixed inside this slice.

## Job story

When I hand the MVP to someone to try on a computer, I want one command to build and launch the Desktop app from the shared code and a recorded smoke run that shows the window opening, saving lands, and failing an unanswered question honestly — and I want the repo's own "how to build/run" and Desktop data-location text to describe what actually happens — so nobody has to rediscover the launch command, the window, the store path, or the fact that the answer service is not wired yet.

## Acceptance scenarios

### The verification command builds the Desktop target

Given the toolchain, when `./init.sh --verify` runs, then it exits `0`, `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build` all succeed, and the Desktop run class/`MainKt` entry point is produced.

### The Desktop app launches

Given the built Desktop target, when `./init.sh --desktop` (i.e. `./gradlew :desktopApp:run`) runs, then a Desktop window titled "Manijero" opens showing the shared chat home with no exception, stack trace, or error in the run log, and the process stays alive until closed.

### The accepted land journey works on Desktop

Given the launched Desktop app, when a person adds a land (name only) and a second land (name + municipality + both attributes), lists `Mis terrenos`, edits one land, and removes one land, then each accepted plain-Spanish confirmation appears, exactly one record changes per action, and after closing and relaunching the app the surviving land is still shown, matching the `~/.manijero/lands-v1.txt` contents.

### The shared chat surface and honest failure path work

Given the launched Desktop app, when the chat home is shown, a suggested question fills the composer, and the question is submitted, then the app shows the accepted plain-Spanish failure notice with its `Reintentar` control (because no `/ask` is wired), the asked question appears only as a `Tú` entry and **never** as an answer, and the privacy notice (`Privacidad y ayuda`) opens and returns.

### A large window keeps the phone layout from being stretched

Given a Desktop window wider than the 720dp content width, when the chat home is shown, then the chat content stays a single capped, centred readable column (the accepted `ContentMaxWidth = 720.dp`) rather than stretching edge to edge, and keyboard navigation still reaches and activates the controls. The lands list, the add/edit/remove land forms, and the privacy notice do **not** share this cap: on a wide Desktop window they render full-width (edge-to-edge), because they use `.fillMaxWidth().widthIn(max = 720.dp)` with no `Alignment.CenterHorizontally`. That full-width behavior is **pre-existing** (the accepted `chat_accessibility` cap was scoped to `ChatHomeScreen` only) and is recorded as finding H1 in `docs/validations/desktop_mvp_build.md`; it is not claimed as capped/centred here and is not fixed in this slice. This scenario **verifies** the already-shipped chat-home behavior; it changes no layout.

### The repository's own guidance is Desktop-truthful

Given the checkout, when `README.md` "Running the MVP targets" and `./init.sh --check` are read, then `./init.sh --desktop` is named as the launch command, the Desktop land store path (`~/.manijero/lands-v1.txt`) is documented where the Android APK path already is, and the no-`/ask` limitation and iOS-out-of-scope statement remain.

### Nothing else changes

Given the slice ships, when the diff is inspected, then no `shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, or `knowledge/` source file changed; no Gradle file, dependency, module, or endpoint changed; `init.sh` is byte-unchanged; and only the README Desktop line, the evidence/validation record, and `PROGRESS.md`/`feature_list.json` (after verification) differ.

## Repository research

Inspected directly (paths relative to the repository root):

- `init.sh` — `--verify` runs `./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; `--desktop` runs `./gradlew :desktopApp:run`. The `--check` banner (lines 54-66) now points at `PROGRESS.md`/`feature_list.json`, names `--verify` and `--android`/`--desktop`, and states the no-`/ask` limitation — **already Desktop-truthful from `android_mvp_build`; no change needed.** The script executes checks and never starts a long-running service. No new mode is needed.
- `desktopApp/build.gradle.kts` — `mainClass = "com.jamarglex.manijero.MainKt"`, `compose.desktop.currentOs` + `kotlinx-coroutines-swing` + `compose.uiToolingPreview` only, and `nativeDistributions { targetFormats(Dmg, Msi, Deb); packageName = "com.jamarglex.manijero"; packageVersion = "1.0.0" }`. The package formats exist but no packaging task is run by `--verify`/`--desktop`.
- `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` — `application { … Window(onCloseRequest = ::exitApplication, title = "Manijero") { App(landRepository) } }` with `LandRepository(FileLandStorage(landStorePath()))` and `landStorePath() = Paths.get(System.getProperty("user.home"), ".manijero", "lands-v1.txt")`: a thin platform adapter over the shared `App()`. Entry points stay platform-specific; no product behavior lives here.
- `shared/src/jvmMain/kotlin/com/jamarglex/manijero/lands/FileLandStorage.kt` — `Files.exists/readString` and `Files.createDirectories` + `Files.writeString`: the Desktop `LandStorage`, one human-readable `land-store-v1` file.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` — `App(landRepository, answerService: AnswerService = UnavailableAnswerService)`; the whole shared UI lives in `commonMain`. `private val ContentMaxWidth = 720.dp`; the outer content `Column` uses `horizontalAlignment = Alignment.CenterHorizontally` and each top-level block uses `.widthIn(max = ContentMaxWidth).fillMaxWidth()`, so a wide Desktop window shows one centred 720dp column (added by `chat_accessibility`). This cap applies to the chat surface; the land list/forms (`LandListScreen`, `AddLandScreen`, `EditLandScreen`, `RemoveLandScreen`) and `PrivacyScreen` instead use `.fillMaxWidth().widthIn(max = 720.dp)` with no centring and render full-width on a wide window (finding H1). The failure notice and `Reintentar` are shipped copy.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` — `KtorAnswerService` posts to `<baseUrl>/ask`; `UnavailableAnswerService.ask` throws, so the shipped Desktop app shows the failure path. This is `chat_question_submission` F1, and it defines the honest smoke limit.
- `README.md` — "Running the MVP targets" already names `./init.sh --verify`, `./init.sh --android` (APK path) and `./init.sh --desktop`, plus the no-`/ask` limitation and the iOS-out-of-scope statement. It does **not** name the Desktop land store path; `PROGRESS.md` line 14 does (`~/.manijero/lands-v1.txt`), but that is a ledger, not the durable run contract.
- `DESIGN.md` — the `chat_accessibility` and `land_form_accessibility` baselines already document the Desktop AX evidence, the wide-window 720dp capped/centred column for the **chat surface** (measured at 800pt/1400pt), the narrow window, the keyboard path, and the recorded remaining gaps (Desktop visual focus not inspectable, no Compose UI-test harness, Desktop OS text scaling preview-only). The land list/forms and the privacy notice are **not** capped (`fillMaxWidth().widthIn(max = 720.dp)`, no centring) and stretch full-width on a wide window — a pre-existing finding (H1) this slice records in `DESIGN.md` but does not fix. This slice adds no new baseline.
- Prior Desktop evidence in `docs/validations/*` — real `:desktopApp:run` smoke (`suggested_questions`, `chat_question_submission`, `add_land`, `land_list`, `edit_land`, `remove_land`, `minimal_land_context`), and the **macOS accessibility tree** re-drive (window "Manijero", JXA/System Events, `AXStaticText`/`AXButton`/`AXTextField`/`AXRadioButton` and `AXDescription`) in `chat_accessibility`/`land_form_accessibility`. Host screen capture is unavailable: `screencapture -x` returned only the desktop wallpaper (no screen-recording permission), and the AX size setter fails with `AppleEvent handler failed (-10000)`, so window-resize claims rest on previews/recorded geometry.
- `PROGRESS.md` — the accepted-state ledger; "Start and verify" lists the real commands including `./init.sh --desktop`. `feature_list.json` — `desktop_mvp_build` is `not_started`; `android_mvp_build` is the accepted sibling.
- `docs/risks-and-open-questions.md` — "Desktop packaging and supported operating systems | Before pilot distribution" is already an implementation-time open question; this slice must not pre-empt it.
- `.gitignore` ignores `build/`, `local.properties`, `.gradle`; the smoke captures are therefore untracked by construction. `~/.manijero/lands-v1.txt` is outside the repo.

Absent, and therefore not assumed: a `POST /ask` route or any answer provider; a persistent E2E/Compose UI-test harness; a run packaging/installer task; a Windows/Linux host; screen-capture permission; an `ARCHITECTURE.md`.

## Technical approach

### 1. Build (no code change)

`./init.sh --verify` already builds the Desktop target. The slice adds no build change: it runs the command, confirms exit `0`, and records the `:desktopApp:build` result alongside the shared-test results. The artifact is a JVM run target (no packaged installer is produced or claimed).

### 2. Desktop launch and journey smoke (manual, via the macOS accessibility tree)

Launch `./init.sh --desktop` in the background and wait for the window titled "Manijero", then drive the accepted scenarios through JXA/`System Events` on the accessibility tree (`AXStaticText`, `AXButton`, `AXTextField`, `AXRadioButton`, and `AXDescription`), the established method in this environment:

```sh
./init.sh --desktop &                 # runs ./gradlew :desktopApp:run
osascript -e 'tell application "System Events" to tell (first process whose name contains "java") to get name of every window'
# JXA: walk the AX tree of the "Manijero" window, activate named AXButtons, set AXTextField values
```

Drive and capture: chat home; suggested question → composer; submit → failure notice + `Reintentar` (never an answer); add land (name only); add land (name + municipality + both choices); `Mis terrenos` list; edit one land; remove one land; the privacy notice; the shared `Volver` paths; a wide-window geometry read of the chat home's 720dp capped column (and a record that the lands list, the forms, and the privacy notice render full-width there — finding H1); and a keyboard-only pass (Shift+Tab out of the composer, Space activates a focused suggestion). Record each AX subtree (text dump) as evidence. Before the smoke, record the pre-existing `~/.manijero/lands-v1.txt` content and restore it afterwards (the app writes to the real user home).

### 3. Truthful durable guidance (small, bounded)

`init.sh` and `DESIGN.md` need no change. Add one short Desktop sentence to `README.md` "Running the MVP targets" so the durable run contract names where Desktop keeps lands (matching how the APK path is already named). Proposed text (wording may be tightened during implementation):

```text
The Desktop app keeps its lands in `~/.manijero/lands-v1.txt` (the shared `land-store-v1`
format); remove that file to start from an empty list.
```

No new mode, no behavior change, no `init.sh` edit.

### 4. Detect any real release blocker before "no change"

If the smoke finds a build/launch/window blocker (target missing, window never opens, launch exception, journey fails on Desktop), that is an implementation finding: stop, record it, and raise it rather than silently editing product code. This slice does not fix accepted product behavior; it may only correct its own guidance copy.

## Expected file changes

- **Modify** `README.md`: add the Desktop land store path (`~/.manijero/lands-v1.txt`) to "Running the MVP targets" (one–two lines). Keep `--verify`/`--android`/`--desktop` and the iOS-out-of-scope statement unchanged.
- **Create** `docs/validations/desktop_mvp_build.md` (validator record: verdict, commands, AX evidence, honest limits) — written at validation time, not by planning.
- **Update** `PROGRESS.md` and `feature_list.json` **after** verification with the real status and only the commands actually run (spec currently links only).
- **Do not modify**: any `shared/`, `androidApp/`, or `desktopApp/` source file; `gradle/*.toml`; any `build.gradle.kts` (no packaging change); `settings.gradle.kts`; `init.sh` (already Desktop-truthful); `contracts/`; `backend/`; `knowledge/`; `AGENTS.md`; `CONTEXT.md`; `CONSTRAINTS.md` (no new product invariant). `DESIGN.md` is not a baseline change: the smoke's finding that the land/privacy surfaces render full-width is recorded there as a pre-existing finding (H1), with no new baseline.

## Visual design impact

None. No token, layout, copy, or screen change. The smoke inspects the **already accepted** rendered UI launched on Desktop; the chat home's 720dp capped/centred column, the wide/narrow geometry, the keyboard path, and the named controls are accepted baselines the smoke confirms. The cap is chat-home-only: the lands list/forms and the privacy notice render full-width on a wide window (recorded finding H1). Any visual difference from the accepted previews/records is a finding, not a redesign.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `README.md` | **Update** | "Running the MVP targets" is the durable build/run contract; it names the Android APK path but not where Desktop keeps lands, so the Desktop data location lives only in the `PROGRESS.md` ledger. One short Desktop line closes that gap. |
| `docs/validations/desktop_mvp_build.md` | **Create at validation** | The accepted convention for a reproducible acceptance record. |
| `PROGRESS.md`, `feature_list.json` | **Update after verification** | Record status, the Desktop launch/journey evidence, and the honest limitation; planning does not touch them. |
| `init.sh` (banner text) | **Not needed** | Already corrected by `android_mvp_build`: it names `--desktop`, the real verification command, and the no-`/ask` limitation, and points at the living documents. Verified in this worktree; no change. |
| `DESIGN.md` | **Update (finding only)** | The Desktop wide-window, keyboard, and form baselines are already recorded by `chat_accessibility`/`land_form_accessibility`; the smoke measured that only the chat home is capped/centred while the land/privacy surfaces render full-width, so H1 is recorded there as a pre-existing finding (no new baseline). |
| `docs/risks-and-open-questions.md` | **Optional** | The "no answer endpoint at MVP debug release" / Desktop-packaging notes are already implied by F1 and the "Desktop packaging" open question; add a row only if the orchestrator wants it tracked. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `CONSTRAINTS.md` | **Not needed** | Start/verify rules, product scope, and the shared-`commonMain` rule already govern; this slice adds no product invariant. |
| `ARCHITECTURE.md` | **Not needed** | It does not exist; no module, boundary, or dependency is added. |

## Implementation plan and tasks

1. Confirm the baseline: read `init.sh` (`--check` banner + `--desktop`), `README.md` "Running the MVP targets", and `desktopApp/main.kt`; record that `init.sh` and `DESIGN.md` need no change and why.
2. Update `README.md` "Running the MVP targets" with the Desktop land store path (`~/.manijero/lands-v1.txt`); keep the existing commands, the APK path, the no-`/ask` limitation, and the iOS statement.
3. Run `./init.sh --verify`; confirm exit `0` and record the task summary including `:desktopApp:build` and the shared-test counts (and `:shared:jvmTest`/`:shared:testAndroidHostTest` as run).
4. Record the pre-existing `~/.manijero/lands-v1.txt` content; launch `./init.sh --desktop` in the background and confirm the "Manijero" window opens with no exception in the run log.
5. Drive and capture the accepted journeys through the macOS AX tree (JXA/System Events): chat home; suggested question → composer; submit → failure notice + `Reintentar`; add (name-only) and add (full) land; list; edit one; remove one; privacy; the wide-window chat-home 720dp capped/centred geometry (recording that the land/privacy surfaces render full-width — finding H1); a keyboard-only activation pass.
6. Close and relaunch the app; confirm the surviving land is still shown and matches `~/.manijero/lands-v1.txt`; restore the original store content afterwards.
7. Inspect the run log for exceptions and confirm no question/answer/land content is logged; record any finding.
8. `git diff --stat` and confirm only `README.md` (plus planning's spec) changed; no source/Gradle/contracts/backend/knowledge change; `init.sh` byte-unchanged.
9. Record the evidence in `PROGRESS.md` and `feature_list.json` with only the commands actually run and the honest limits; do not mark accepted until an independent validator signs off.

## Verification plan and evidence

Run from the repository root:

```sh
./init.sh
./init.sh --verify                          # expect exit 0; :desktopApp:build included

cp ~/.manijero/lands-v1.txt /tmp/lands-v1.txt.bak 2>/dev/null   # if a store already exists
./init.sh --desktop &                       # runs ./gradlew :desktopApp:run; window "Manijero"
# (drive the "Manijero" window through JXA/System Events; capture the AX subtree per screen)
cat ~/.manijero/lands-v1.txt                # confirm one record per action; then relaunch to confirm persistence
cp /tmp/lands-v1.txt.bak ~/.manijero/lands-v1.txt 2>/dev/null  # restore the original store

git status --porcelain
git diff --stat
git diff --check
```

Capture: the `./init.sh --verify` exit code and task summary; the Desktop run-log lines showing the window opened with no exception; the AX subtree text for home, suggested→composer, the failure notice with `Reintentar`, add name-only, add full, list, edit, remove, privacy, and the post-relaunch list; the wide-window chat-home geometry read (720pt capped/centred column; the lands list/forms/privacy notice full-width — finding H1); the keyboard-only activation note; the `~/.manijero/lands-v1.txt` contents before/after a change and after relaunch; and the final `git status --porcelain`/`git diff --stat` showing only `README.md` (+ docs). Evidence goes under gitignored `build/` (precedent: `build/evidence/`, `build/evidence-validator/`).

## Honest limitations to record

- **No grounded answer is reachable on the shipped Desktop app.** `UnavailableAnswerService` is the default `App()` wiring and the backend has no `/ask` route (`chat_question_submission` F1), so the smoke can only exercise the failure notice; it must never claim an answered/abstained/source-card render. A grounded-answer Desktop smoke needs its own slice once a route exists.
- **Host screen capture is unavailable**, so there are no Desktop screenshots. The journey is evidenced through the macOS accessibility tree (the established method) and the run log; the Desktop **visual focus indication** cannot be inspected and is not claimed.
- **No packaged installer is built or claimed.** `--verify`/`--desktop` compile and run the JVM target only; Dmg/Msi/Deb packaging and supported OS stay open (`docs/risks-and-open-questions.md`).
- **No automated UI/E2E harness.** Verification is manual AX-tree driving + run log; nothing here becomes a persistent E2E command.
- **Desktop OS text scaling has no runtime integration** (precedent: `DESIGN.md`), so large-text evidence stays preview-based and is not re-claimed.
- **Single macOS host.** Only the host Desktop session is exercised; no Windows/Linux and no physical other-OS claim.
- **The smoke writes to the real `~/.manijero/lands-v1.txt`**; the pre-existing store must be recorded and restored, and the record must say so.

## Validator checklist

- [ ] `./init.sh --verify` exits `0` and includes `:desktopApp:build` (record the task summary and shared-test counts).
- [ ] `./init.sh --desktop` launches a Desktop window titled "Manijero" with no exception in the run log; record how it was launched and how it was closed.
- [ ] The land journey works on the launched Desktop app: add (name-only), add (full), list, edit (one record changes), remove (one record removed), and persistence across relaunch matching `~/.manijero/lands-v1.txt`.
- [ ] The chat home shows the submitted question as the plain-Spanish failure notice with `Reintentar` and **never** as an answer; the privacy notice opens and returns.
- [ ] On a window wider than 720dp the **chat home** keeps a capped, centred readable column (no edge-to-edge stretch), and keyboard navigation reaches and activates controls. Do **not** claim the lands list, the land forms, or the privacy notice are capped/centred: they render full-width in a wide window (recorded finding H1, pre-existing chat-home-only cap).
- [ ] `README.md` "Running the MVP targets" names `./init.sh --desktop` and the Desktop store path (`~/.manijero/lands-v1.txt`) and keeps the no-`/ask` limitation and iOS statement; `./init.sh --check` remains Desktop-truthful and `init.sh` is byte-unchanged.
- [ ] No `shared/`, `androidApp/`, or `desktopApp/` source changed; no Gradle/version-catalog/contracts/backend/knowledge change; no new module, dependency, mode, endpoint, or packaging task.
- [ ] Every claim in the evidence is backed by an AX capture, a store file, or a command actually run; the no-`/ask` limitation, no-screen-capture limit, no-installer limit, and single-macOS-host limit are stated, and no grounded-answer/visual-focus/packaged-installer pass is claimed.
- [ ] The pre-existing `~/.manijero/lands-v1.txt` was recorded and restored.
- [ ] `feature_list.json`/`PROGRESS.md` record only the commands actually run and the real status; the slice is `accepted` only after this independent validation.

## Risks and open decisions

- **R1 F1 blocks a full chat smoke.** The shipped Desktop app cannot produce a grounded answer; the smoke proves build/launch/window/journey and the honest failure path only. Accepted and recorded; not a defect.
- **R2 Host GUI/session availability.** If the Desktop window cannot be launched or driven (no display, no accessibility permission), the build evidence still stands but the launch/journey evidence is blocked — record the exact blocker and do not claim the smoke.
- **R3 Destructive smoke on the real store.** The Desktop app uses the real `~/.manijero/lands-v1.txt`. The plan records and restores it; the record must state what was touched.
- **R4 Wide-window geometry read is AX-based, and the cap is chat-home-only.** The AX size setter previously failed (`-10000`), so the wide-window check may rest on the already-recorded geometry/previews; if so, say so honestly rather than claiming a fresh resize. Independently of the method, only the chat home is capped/centred — the lands list/forms and the privacy notice render full-width (finding H1); the record must not claim a capped/centred land layout.
- **R5 Stale/duplicated guidance.** The README edit must not duplicate or drift from `init.sh`'s banner or `DESIGN.md`'s baselines; it is one Desktop data-location line only.
- **R6 A real blocker found during smoke.** If the artifact fails to launch or the journey fails on Desktop, this release slice reports it as a finding rather than editing accepted product code; a fix becomes its own slice.
- **U1** Whether `README.md` should also mention the window title or only the store path (keep the line minimal).
- **U2** Whether `docs/risks-and-open-questions.md` gains the "no answer endpoint at MVP debug release" row (optional; sibling left it optional).

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/desktop_mvp_build.md. Release/verification slice: only README.md (one Desktop land-store line), feature_list.json, PROGRESS.md, DESIGN.md, and docs/risks-and-open-questions.md changed (plus the untracked spec and validation record); no product code, Gradle, contract, backend, or knowledge file changed; init.sh byte-unchanged.
- ./init.sh --verify -> exit 0, BUILD SUCCESSFUL, 91 actionable tasks (:shared:jvmTest, :shared:testAndroidHostTest, :androidApp:assembleDebug, :desktopApp:build). Shared tests: :shared:jvmTest 192 tests / 0 failures (21 suites), :shared:testAndroidHostTest 178 tests / 0 failures (17 suites). androidApp-debug.apk 36,014,513 bytes, sha256 4b4ab9d6cc50e026436116defdf3ffb79023dc84b7c715c6ce9b2c8e874ed538. :desktopApp:build produced the MainKt JVM run target.
- Launch: ./init.sh --desktop (./gradlew :desktopApp:run). The run log shows '> Task :desktopApp:run' with NO exception, stack trace, or error line; the process stayed alive ~7m47s until closed. CoreGraphics window list (CGWindowListCopyWindowInfo, no accessibility needed) shows an on-screen window owned by process 'MainKt' (pid 7856), 800x600 at (48,81); the window title string is set to 'Manijero' in desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt (the live title text cannot be read without screen-recording permission). Closed by SIGTERM; Gradle then reported exit value 143 (the expected SIGTERM shutdown artifact, not an app exception).
- GUI driving (journeys) was not available in the implementer's session and is not claimed by the implementer. In that session macOS reported AXIsProcessTrusted=false and 'osascript is not allowed assistive access. (-1728)' (after an earlier System Events call returned 'Connection is invalid. (-609)' and hung); a system consent prompt (universalAccessAuthWarn, pid 8001) was present and could not be answered without a human. The macOS accessibility (AX) and screen-recording permissions were not available in the implementer's session, so the land journey (add name-only, add full, list, edit, remove, relaunch persistence), the chat home + suggested question + failure notice + Reintentar + privacy notice, the wide-window geometry read, and the keyboard-only pass were NOT driven here. This is an environment-specific limitation (spec risk R2), not a claim that the GUI cannot be driven: the independent validator later drove the whole journey through the macOS AX tree successfully (see docs/validations/desktop_mvp_build.md).
- Land store: no pre-existing ~/.manijero/lands-v1.txt existed at the start (ls: No such file or directory) and none was created (nothing was driven); nothing to restore. The store path is set by desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt (LAND_STORE_FILE = 'lands-v1.txt' under user.home/.manijero).
- README.md 'Running the MVP targets': added one line - 'The Desktop app keeps its lands in `~/.manijero/lands-v1.txt` (the shared `land-store-v1` format); remove that file to start from an empty list.' The existing ./init.sh --verify/--android/--desktop commands, the Android debug APK path, the no-/ask limitation, and the iOS-out-of-scope statement are unchanged.
- Wide-window check (implementer): not freshly measured (AX/geometry driving was unavailable in the implementer's session). The capped/centred column claim rests only on the already-accepted chat-surface baseline (docs/validations/chat_accessibility.md: 720dp capped/centred column at 800pt and 1400pt, 372 at 420pt) and on source inspection of the chat surface in App.kt ('private val ContentMaxWidth = 720.dp' with .widthIn(max = ContentMaxWidth).fillMaxWidth() top-level blocks). It is NOT rested on the land surfaces: LandListScreen/AddLandScreen/EditLandScreen/RemoveLandScreen/PrivacyScreen use .fillMaxWidth().widthIn(max = 720.dp) with no centring. The validator independently measured that at a 1400x900 window only the chat home is capped/centred (720 at x=400), while the lands list/forms/privacy notice render full-width (1352 at x=84) — recorded as finding H1 in docs/validations/desktop_mvp_build.md and repaired in the spec/DESIGN wording without any product change.
- Scope: git status --porcelain = ' M README.md', ' M feature_list.json', '?? docs/specs/desktop_mvp_build.md'; git diff --stat = README.md +2, feature_list.json 1 changed line; git diff --check clean; git diff --exit-code -- init.sh shows init.sh byte-unchanged; no shared/, androidApp/, desktopApp/, contracts/, backend/, knowledge/, Gradle, or version-catalog source changed. Logging grep (println|Log.|Logger|printStackTrace|System.out|NSLog over shared/src androidApp/src desktopApp/src) -> no matches. Evidence under gitignored build/evidence-desktop/.
- Honest limits: single macOS host (macOS 27.0.1); no packaged installer built or claimed (only the JVM run target); no screenshots in the implementer's session (the screen-recording permission was not available there: 'screencapture -x' -> 'could not create image from display'; the validator's session did have the accessibility/AX and screen-recording permissions); no automated UI/E2E harness; the shipped default AnswerService is UnavailableAnswerService and the backend exposes only /health, so no grounded/answered/abstained/source-card render is reachable. Self-verified build/launch only: the implementer's session lacked the macOS accessibility (AX) permission, so the GUI journeys were not driven by the implementer; they were independently re-driven by the validator. Left 'passing', not 'accepted'.
- Validator H1 (documentation repair, no product change): an independent validator re-drove the full Desktop journey through the AX tree (window 'Manijero') and measured that at a 1400x900 window the chat home is capped and centred (720 at x=400) while the Mis terrenos list, the add/edit/remove forms, and the privacy notice render full-width/edge-to-edge (1352 at x=84) - they use .fillMaxWidth().widthIn(max = 720.dp) with no Alignment.CenterHorizontally. This is pre-existing behavior (the chat_accessibility cap was scoped to ChatHomeScreen), not introduced by this slice. The spec's wide-window acceptance scenario/checklist and the evidence wording were corrected to claim the capped/centred column for the chat home only and to record the land/privacy full-width stretch as a finding (spec, DESIGN.md, docs/risks-and-open-questions.md); no product code changed. See docs/validations/desktop_mvp_build.md findings H1 (blocking, wording) and L1 (AX-blocked record re-worded as environment-specific).
- Independent validator ACCEPTED this feature (2026-10-16, record: docs/validations/desktop_mvp_build.md). It did not trust the implementer report: it re-ran the full build (./init.sh --verify -> BUILD SUCCESSFUL, 91 actionable tasks, 91 executed / 0 from cache; :shared:jvmTest 192/0 across 21 suites, :shared:testAndroidHostTest 178/0 across 17 suites; byte-identical debug APK 36,014,513 bytes, sha256 4b4ab9d6…ed538; :desktopApp:build produced MainKt), launched ./init.sh --desktop twice (window 'Manijero' opened with no exception in the run log and closed cleanly), and independently re-drove the entire Desktop journey through the macOS AX tree with its own screenshots and per-screen AX dumps under gitignored build/evidence-validator/: chat home; a suggested question filling the composer; submit -> the plain-Spanish failure notice + Reintentar with the question appearing only as one merged 'Tú' entry and 0 'Asistente' nodes (never an answer); the privacy notice opening and returning; the land journey add name-only, add full, list, edit exactly one record, remove exactly one record, and relaunch persistence matching ~/.manijero/lands-v1.txt byte-for-byte; the keyboard Shift+Tab + Space activation path; and the wide-window measurement. It returned 'revise' once for spec/record wording only (finding H1: the 720dp capped/centred column holds for the chat home only, while the lands list/forms and the privacy notice render full-width — pre-existing, recorded not fixed), and after the documentation-only repair re-checked and returned 'accept'. It confirmed scope clean (only README.md plus docs/records changed; no product/Gradle/contracts/backend/knowledge change; init.sh byte-unchanged), logging grep no matches, and no grounded-answer/packaged-installer/other-OS/speech claim. Accepted on 2026-10-16 by independent validation; H1 is a recorded pre-existing finding, not fixed in this slice.
