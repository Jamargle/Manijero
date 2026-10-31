# Feature Spec: `desktop_mvp_build`

## Source metadata

- **Feature:** `desktop_mvp_build` — Build the Desktop MVP artifact (area: `release`), `not_started` at planning (2026-10-16).
- **Depends on:** `suggested_questions`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `answer_land_scope` — all **accepted**.
- **Source behavior:** "The MVP can be built and launched on Desktop with the same shared Compose UI and business behavior."
- **Source verification:** "Run `./scripts/init.sh --verify`, launch the Desktop app, and complete one question and one land-management scenario."
- **Source note:** "Adapt layout and keyboard behavior for large windows rather than stretching the phone layout."
- **Carried handoff this feature closes:** `chat_question_submission` **F1** — the shipped app wiring is `UnavailableAnswerService` because the backend exposes no `/ask` route. This slice must be honest about it, not fix it (see Non-goals).
- **Sibling already accepted:** `android_mvp_build` (record `docs/validations/android_mvp_build.md`) proved the Android artifact and already corrected `scripts/init.sh`'s `--check` banner and the README "Running the MVP targets" section. This Desktop slice reuses that wording instead of re-deciding it.
- **Scope size:** release/verification slice. **No product behavior and no `commonMain` change.** One small durable README addition, one Desktop launch/journey smoke via the macOS accessibility tree, one evidence/validation record. The repository already carries the 720dp centred content cap (on the chat home; the land/privacy surfaces render full-width — a recorded pre-existing finding), the 720dp/wide-window and Desktop keyboard baselines, and the versioned local land store; this slice verifies them rather than rebuilding them. Correctly sized; well under the 100–250 line target after research.

## Goal

Prove that the accepted MVP runs as a real Desktop artifact and leave the repository's own instructions Desktop-truthful: `./scripts/init.sh --verify` builds the Desktop (JVM) target from the shared `commonMain` UI and behavior, `./scripts/init.sh --desktop` launches it (`:desktopApp:run`, window title "Manijero", lands stored by `FileLandStorage` at `~/.manijero/lands-v1.txt`), the accepted land journey and the chat home with its honest failure path work in that window, and the already-shipped 720dp centred content cap keeps a large window from stretching the phone layout **on the chat home** (the lands list, the land forms, and the privacy notice render full-width on a wide window — a pre-existing finding recorded, not fixed, by this slice). Also record the Desktop land-store location in the durable README so a new session does not have to rediscover it.

## Non-goals

- **No product code change.** Nothing in `shared/src/commonMain` (or any other source set), no new screen, state, string, or behavior; the accepted features are frozen. The chat-home 720dp cap, the keyboard behavior, and the store path already exist.
- **No `/ask` wiring and no backend change.** `UnavailableAnswerService` stays the default `App()` wiring, the backend keeps `/health` as its only route, and no model provider is configured. The smoke must state plainly that a question on the shipped Desktop app shows the plain-Spanish failure notice, not a grounded answer.
- **No new module, dependency, Gradle change, version-catalog change, mode, or CI/nightly automation.** `scripts/init.sh` gains no new mode and **needs no change at all** (the Android slice already made `--check` Desktop-truthful); `--verify`/`--desktop` stay as accepted.
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

Given the toolchain, when `./scripts/init.sh --verify` runs, then it exits `0`, `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build` all succeed, and the Desktop run class/`MainKt` entry point is produced.

### The Desktop app launches

Given the built Desktop target, when `./scripts/init.sh --desktop` (i.e. `./gradlew :desktopApp:run`) runs, then a Desktop window titled "Manijero" opens showing the shell's launch tab (`Mis terrenos` with its saved lands, since `app_chrome_navigation` changed the entry point) with no exception, stack trace, or error in the run log, and the process stays alive until closed.

### The accepted land journey works on Desktop

Given the launched Desktop app, when a person adds a land (name only) and a second land (name + municipality + both attributes), lists `Mis terrenos`, edits one land, and removes one land, then each accepted plain-Spanish confirmation appears, exactly one record changes per action, and after closing and relaunching the app the surviving land is still shown, matching the `~/.manijero/lands-v1.txt` contents.

### The shared chat surface and honest failure path work

Given the launched Desktop app, when the chat home is shown, a suggested question fills the composer, and the question is submitted, then the app shows the accepted plain-Spanish failure notice with its `Reintentar` control (because no `/ask` is wired), the asked question appears only as a `Tú` entry and **never** as an answer, and the privacy notice (`Privacidad y ayuda`) opens and returns.

### A large window keeps the phone layout from being stretched

Given a Desktop window wider than the 720dp content width, when the chat home is shown, then the chat content stays a single capped, centred readable column (the accepted `ContentMaxWidth = 720.dp`) rather than stretching edge to edge, and keyboard navigation still reaches and activates the controls. The lands list, the add/edit/remove land forms, and the privacy notice do **not** share this cap: on a wide Desktop window they render full-width (edge-to-edge), because they use `.fillMaxWidth().widthIn(max = 720.dp)` with no `Alignment.CenterHorizontally`. That full-width behavior is **pre-existing** (the accepted `chat_accessibility` cap was scoped to `ChatHomeScreen` only) and is recorded as finding H1 in `docs/validations/desktop_mvp_build.md`; it is not claimed as capped/centred here and is not fixed in this slice. This scenario **verifies** the already-shipped chat-home behavior; it changes no layout.

### The repository's own guidance is Desktop-truthful

Given the checkout, when `README.md` "Running the MVP targets" and `./scripts/init.sh --check` are read, then `./scripts/init.sh --desktop` is named as the launch command, the Desktop land store path (`~/.manijero/lands-v1.txt`) is documented where the Android APK path already is, and the no-`/ask` limitation and iOS-out-of-scope statement remain.

### Nothing else changes

Given the slice ships, when the diff is inspected, then no `shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, or `knowledge/` source file changed; no Gradle file, dependency, module, or endpoint changed; `scripts/init.sh` is byte-unchanged; and only the README Desktop line, the evidence/validation record, and `PROGRESS.md`/`feature_list.json` (after verification) differ.

## Technical approach

### 1. Build (no code change)

`./scripts/init.sh --verify` already builds the Desktop target. The slice adds no build change: it runs the command, confirms exit `0`, and records the `:desktopApp:build` result alongside the shared-test results. The artifact is a JVM run target (no packaged installer is produced or claimed).

### 2. Desktop launch and journey smoke (manual, via the macOS accessibility tree)

Launch `./scripts/init.sh --desktop` in the background and wait for the window titled "Manijero", then drive the accepted scenarios through JXA/`System Events` on the accessibility tree (`AXStaticText`, `AXButton`, `AXTextField`, `AXRadioButton`, and `AXDescription`), the established method in this environment:

```sh
./scripts/init.sh --desktop &                 # runs ./gradlew :desktopApp:run
osascript -e 'tell application "System Events" to tell (first process whose name contains "java") to get name of every window'
# JXA: walk the AX tree of the "Manijero" window, activate named AXButtons, set AXTextField values
```

Drive and capture: chat home; suggested question → composer; submit → failure notice + `Reintentar` (never an answer); add land (name only); add land (name + municipality + both choices); `Mis terrenos` list; edit one land; remove one land; the privacy notice; the shared `Volver` paths; a wide-window geometry read of the chat home's 720dp capped column (and a record that the lands list, the forms, and the privacy notice render full-width there — finding H1); and a keyboard-only pass (Shift+Tab out of the composer, Space activates a focused suggestion). Record each AX subtree (text dump) as evidence. Before the smoke, record the pre-existing `~/.manijero/lands-v1.txt` content and restore it afterwards (the app writes to the real user home).

### 3. Truthful durable guidance (small, bounded)

`scripts/init.sh` and `DESIGN.md` need no change. Add one short Desktop sentence to `README.md` "Running the MVP targets" so the durable run contract names where Desktop keeps lands (matching how the APK path is already named). Proposed text (wording may be tightened during implementation):

```text
The Desktop app keeps its lands in `~/.manijero/lands-v1.txt` (the shared `land-store-v1`
format); remove that file to start from an empty list.
```

No new mode, no behavior change, no `scripts/init.sh` edit.

### 4. Detect any real release blocker before "no change"

If the smoke finds a build/launch/window blocker (target missing, window never opens, launch exception, journey fails on Desktop), that is an implementation finding: stop, record it, and raise it rather than silently editing product code. This slice does not fix accepted product behavior; it may only correct its own guidance copy.

## Expected file changes

- **Modify** `README.md`: add the Desktop land store path (`~/.manijero/lands-v1.txt`) to "Running the MVP targets" (one–two lines). Keep `--verify`/`--android`/`--desktop` and the iOS-out-of-scope statement unchanged.
- **Create** `docs/validations/desktop_mvp_build.md` (validator record: verdict, commands, AX evidence, honest limits) — written at validation time, not by planning.
- **Update** `PROGRESS.md` and `feature_list.json` **after** verification with the real status and only the commands actually run (spec currently links only).
- **Do not modify**: any `shared/`, `androidApp/`, or `desktopApp/` source file; `gradle/*.toml`; any `build.gradle.kts` (no packaging change); `settings.gradle.kts`; `scripts/init.sh` (already Desktop-truthful); `contracts/`; `backend/`; `knowledge/`; `AGENTS.md`; `CONTEXT.md`; `CONSTRAINTS.md` (no new product invariant). `DESIGN.md` carries durable design direction, not this smoke's measured layout finding; keep the finding in the validation record and risks register.

## Visual design impact

None. No token, layout, copy, or screen change. The smoke inspects the **already accepted** rendered UI launched on Desktop; the chat home's 720dp capped/centred column, the wide/narrow geometry, the keyboard path, and the named controls are accepted baselines the smoke confirms. The cap is chat-home-only: the lands list/forms and the privacy notice render full-width on a wide window (recorded finding H1). Any visual difference from the accepted previews/records is a finding, not a redesign.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `README.md` | **Update** | "Running the MVP targets" is the durable build/run contract; it names the Android APK path but not where Desktop keeps lands, so the Desktop data location lives only in the `PROGRESS.md` ledger. One short Desktop line closes that gap. |
| `docs/validations/desktop_mvp_build.md` | **Create at validation** | The accepted convention for a reproducible acceptance record. |
| `PROGRESS.md`, `feature_list.json` | **Update after verification** | Record status, the Desktop launch/journey evidence, and the honest limitation; planning does not touch them. |
| `scripts/init.sh` (banner text) | **Not needed** | Already corrected by `android_mvp_build`: it names `--desktop`, the real verification command, and the no-`/ask` limitation, and points at the living documents. Verified in this worktree; no change. |
| `DESIGN.md` | **No update** | Keep measured implementation state and feature-specific evidence in the validation record, progress board, and risks register; this guide carries durable design direction, not runtime findings. |
| `docs/risks-and-open-questions.md` | **Optional** | The "no answer endpoint at MVP debug release" / Desktop-packaging notes are already implied by F1 and the "Desktop packaging" open question; add a row only if the orchestrator wants it tracked. |
| `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `CONSTRAINTS.md` | **Not needed** | Start/verify rules, product scope, and the shared-`commonMain` rule already govern; this slice adds no product invariant. |
| `ARCHITECTURE.md` | **Not needed** | It does not exist; no module, boundary, or dependency is added. |

## Honest limitations to record

- **No grounded answer is reachable on the shipped Desktop app.** `UnavailableAnswerService` is the default `App()` wiring and the backend has no `/ask` route (`chat_question_submission` F1), so the smoke can only exercise the failure notice; it must never claim an answered/abstained/source-card render. A grounded-answer Desktop smoke needs its own slice once a route exists.
- **Host screen capture is unavailable**, so there are no Desktop screenshots. The journey is evidenced through the macOS accessibility tree (the established method) and the run log; the Desktop **visual focus indication** cannot be inspected and is not claimed.
- **No packaged installer is built or claimed.** `--verify`/`--desktop` compile and run the JVM target only; Dmg/Msi/Deb packaging and supported OS stay open (`docs/risks-and-open-questions.md`).
- **No automated UI/E2E harness.** Verification is manual AX-tree driving + run log; nothing here becomes a persistent E2E command.
- **Desktop OS text scaling has no runtime integration** (precedent: `DESIGN.md`), so large-text evidence stays preview-based and is not re-claimed.
- **Single macOS host.** Only the host Desktop session is exercised; no Windows/Linux and no physical other-OS claim.
- **The smoke writes to the real `~/.manijero/lands-v1.txt`**; the pre-existing store must be recorded and restored, and the record must say so.

## Risks and open decisions

- **R1 F1 blocks a full chat smoke.** The shipped Desktop app cannot produce a grounded answer; the smoke proves build/launch/window/journey and the honest failure path only. Accepted and recorded; not a defect.
- **R2 Host GUI/session availability.** If the Desktop window cannot be launched or driven (no display, no accessibility permission), the build evidence still stands but the launch/journey evidence is blocked — record the exact blocker and do not claim the smoke.
- **R3 Destructive smoke on the real store.** The Desktop app uses the real `~/.manijero/lands-v1.txt`. The plan records and restores it; the record must state what was touched.
- **R4 Wide-window geometry read is AX-based, and the cap is chat-home-only.** The AX size setter previously failed (`-10000`), so the wide-window check may rest on the already-recorded geometry/previews; if so, say so honestly rather than claiming a fresh resize. Independently of the method, only the chat home is capped/centred — the lands list/forms and the privacy notice render full-width (finding H1); the record must not claim a capped/centred land layout.
- **R5 Stale/duplicated guidance.** The README edit must not duplicate or drift from `scripts/init.sh`'s banner or `DESIGN.md`'s baselines; it is one Desktop data-location line only.
- **R6 A real blocker found during smoke.** If the artifact fails to launch or the journey fails on Desktop, this release slice reports it as a finding rather than editing accepted product code; a fix becomes its own slice.
- **U1** Whether `README.md` should also mention the window title or only the store path (keep the line minimal).
- **U2** Whether `docs/risks-and-open-questions.md` gains the "no answer endpoint at MVP debug release" row (optional; sibling left it optional).

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest :desktopApp:build
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/desktop_mvp_build.appendix.md`](../archive/specs/desktop_mvp_build.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/desktop_mvp_build.md` remains the authoritative acceptance record.
