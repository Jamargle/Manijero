# Feature Spec: `android_mvp_build`

## Source metadata

- **Feature:** `android_mvp_build` — Build the Android MVP artifact (area: `release`), `not_started` at planning (2026-10-16).
- **Depends on:** `suggested_questions`, `network_error_recovery`, `land_list`, `edit_land`, `remove_land`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `answer_land_scope` — all **accepted**.
- **Source behavior:** "The MVP can be built as an Android debug APK with shared product UI and behavior."
- **Source verification:** "Run `./scripts/init.sh --verify` and install the generated debug APK on an Android device or emulator for a smoke check."
- **Source note:** "iOS is not part of MVP acceptance."
- **Carried handoff this feature closes:** `chat_question_submission` **F1** — the shipped app wiring is `UnavailableAnswerService` because the backend exposes no `/ask` route. This slice must be honest about it, not fix it (see Non-goals).
- **Scope size:** release/verification slice. **No product behavior and no `commonMain` change.** One entry-point script copy fix, one durable README section, one emulator smoke run, one evidence/validation record. Correctly sized; well under the 100–250 line target after research.

## Goal

Prove that the accepted MVP is a real, installable Android artifact and leave the repository's own instructions truthful about how to build and run it: `./scripts/init.sh --verify` produces `androidApp/build/outputs/apk/debug/androidApp-debug.apk` from the shared `commonMain` UI and behavior, that APK installs and launches on an Android emulator, and the accepted local land journeys plus the chat home and its honest failure path work on the installed artifact. Also correct the stale `./scripts/init.sh --check` banner, which still says retrieval, answer generation, response states, and the visual foundation "remain deferred".

## Non-goals

- **No product code change.** Nothing in `shared/src/commonMain` (or any other source set), no new screen, state, string, or behavior; the accepted features are frozen.
- **No `/ask` wiring and no backend change.** `UnavailableAnswerService` stays the default `App()` wiring, the backend keeps `/health` as its only route, and no model provider is configured. The smoke must state plainly that a question on the shipped APK shows the plain-Spanish failure notice, not a grounded answer.
- **No new module, dependency, Gradle change, version-catalog change, mode, or CI/nightly automation.** `scripts/init.sh` gains no new mode; `--verify`/`--android` stay as accepted.
- **No iOS release work**, no release (non-debug) signing, ProGuard, bundling, Play upload, or store metadata. This is the **debug** artifact only.
- **No new automated UI/E2E harness.** No Compose UI-test artifact, no instrumented test, no persistent E2E command (none exists; the repo refuses test-only dependencies).
- **No physical-device claim.** The smoke runs on the available emulator; a physical device, if used, is recorded as such.
- **No accessibility re-audit.** `chat_accessibility` and `land_form_accessibility` already own the enlarged-text / screen-reader / keyboard baselines; the release smoke only confirms the installed artifact still renders and navigates.
- **No re-litigating accepted behavior.** A smoke discovery that contradicts an accepted feature is reported as a finding, not fixed inside this slice.

## Job story

When I hand the MVP to someone to try on a phone, I want one command to build an installable APK from the shared code and a recorded smoke run that shows the app opening, saving lands, and failing an unanswered question honestly — and I want the repo's own "how to build/run" text to describe what actually happens — so nobody has to rediscover the build command, the APK path, or the fact that the answer service is not wired yet.

## Acceptance scenarios

### The verification command produces an installable debug APK

Given the toolchain and an Android SDK (auto-detected by `scripts/init.sh`, which writes `local.properties`), when `./scripts/init.sh --verify` runs, then it exits `0`, `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build` all succeed, and `androidApp/build/outputs/apk/debug/androidApp-debug.apk` exists.

### The APK installs and launches

Given a running emulator with `adb`, when the debug APK is installed (`adb install -r …`) and the launcher activity `com.jamarglex.manijero/.MainActivity` starts, then the app opens on the shell's launch tab (`Mis terrenos` with its saved lands, since `app_chrome_navigation` changed the entry point) with no crash, no ANR, and no fatal `AndroidRuntime` entry in `logcat`.

### The accepted land journey works on the installed artifact

Given the installed APK, when a person adds a land (name only) and a second land (name + municipality + both attributes), lists `Mis terrenos`, edits one land, and removes one land, then each accepted plain-Spanish confirmation appears, the store reflects exactly one change per action, and after a force-stop and relaunch the surviving lands are still shown.

### The shared chat surface and honest failure path work

Given the installed APK, when the chat home is shown, a suggested question fills the composer, and the question is submitted, then the app shows the accepted plain-Spanish failure notice with its `Reintentar` control (because no `/ask` is wired) and **never** renders the failed question as an answer; the privacy notice (`Privacidad y ayuda`) opens.

### The repository's own guidance is truthful

Given the checkout, when `./scripts/init.sh --check` is run, then its banner no longer claims accepted features are deferred, and it names the real verification command and the debug APK output path; `README.md` "Running the MVP targets" documents the real commands and the APK path instead of "common tasks may include … confirm task names".

### Nothing else changes

Given the slice ships, when the diff is inspected, then no `shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, or `knowledge/` source file changed; no Gradle file, dependency, module, or endpoint changed; and only the entry-point copy, the README section, the evidence/validation record, and `PROGRESS.md`/`feature_list.json` (after verification) differ.

## Technical approach

### 1. Build (no code change)

`./scripts/init.sh --verify` already builds the artifact. The slice adds no build change: it runs the command, confirms exit `0`, and records the APK path, byte size, and `shasum -a 256`. `:desktopApp:build` is part of `--verify` and is not re-scoped.

### 2. Emulator smoke (manual, via `adb`)

Start the available AVD (prior runs used `Medium_Phone_API_35`), then:

```sh
adb wait-for-device
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
adb shell am start -n com.jamarglex.manijero/.MainActivity
adb shell screencap -p /sdcard/<name>.png && adb pull /sdcard/<name>.png
adb shell uiautomator dump /sdcard/<name>.xml && adb pull /sdcard/<name>.xml
```

Drive the accepted journeys and capture a screenshot + dump for each: chat home; suggested question filling the composer; submit → the failure notice and `Reintentar`; add land (name only); add land (name + municipality + both choices); `Mis terrenos` list; edit one land; remove one land; the privacy notice; force-stop (`adb shell am force-stop com.jamarglex.manijero`) then relaunch to confirm persistence. Watch `adb logcat` for crashes and confirm no `AndroidRuntime` fatal and no logged land/question text. A single `font_scale 2.0` pass over home/list/forms is a light confirmation only (the deep accessibility baselines stay with `chat_accessibility`/`land_form_accessibility`).

### 3. Truthful entry-point copy (small, bounded)

Replace the stale `--check` banner in `scripts/init.sh` with text that points at the living documents instead of enumerating features, and names the real commands and the APK path. Proposed replacement body (wording may be tightened during implementation):

```text
Manijero MVP — the Android and Desktop apps render the shared Kotlin Multiplatform UI and behavior in shared/src/commonMain. See PROGRESS.md and feature_list.json for the accepted feature set and current status.

Standard verification:
  ./scripts/init.sh --verify     # shared tests + Android debug APK + Desktop build

Build and run:
  ./scripts/init.sh --android    # androidApp/build/outputs/apk/debug/androidApp-debug.apk
  ./scripts/init.sh --desktop    # launch the Desktop app

Known limitation: the backend has no /ask route yet, so the shipped app answers a question with the plain-Spanish failure notice and a Reintentar button, not a grounded answer.
```

No new mode, no behavior change: only the printed guidance changes. `--check`, `--verify`, `--android`, `--desktop` keep their accepted semantics.

### 4. Detect any real release blocker before "no change"

If the smoke finds a build/install/launch blocker (APK missing, install rejected, launch crash), that is an implementation finding: stop, record it, and raise it rather than silently editing product code. This slice does not fix accepted product behavior; it may only correct its own guidance copy.

## Expected file changes

- **Modify** `scripts/init.sh`: replace the stale `--check` banner body only (no case/mode/command change).
- **Modify** `README.md`: replace the tentative "Running the MVP targets" text with the real commands (`./scripts/init.sh --verify`, `./scripts/init.sh --android`, `./scripts/init.sh --desktop`) and the debug APK path `androidApp/build/outputs/apk/debug/androidApp-debug.apk`; keep the iOS-out-of-scope statement.
- **Create** `docs/validations/android_mvp_build.md` (validator record: verdict, commands, captures, honest limits) — written at validation time, not by planning.
- **Update** `PROGRESS.md` and `feature_list.json` **after** verification with the real status and only the commands actually run (spec currently links only).
- **Do not modify**: any `shared/`, `androidApp/`, or `desktopApp/` source file; `gradle/*.toml`; any `build.gradle.kts`; `settings.gradle.kts`; `contracts/`; `backend/`; `knowledge/`; `AGENTS.md`; `DESIGN.md`; `CONSTRAINTS.md` (no new product invariant is introduced); the `Test`/`implementation` sections of `scripts/init.sh`.

## Visual design impact

None. No token, layout, copy, or screen changes. The smoke inspects the **already accepted** rendered UI on the installed artifact; any visual difference from the accepted previews/records is a finding, not a redesign.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `scripts/init.sh` (banner text) | **Update** | The `--check` guidance is the first thing a person or validator runs; it must not claim accepted features are deferred, and must name the real command and artifact path. |
| `README.md` | **Update** | "Running the MVP targets" is the durable build/run contract; it currently hedges with "may include" and does not name the APK path. |
| `docs/validations/android_mvp_build.md` | **Create at validation** | The accepted convention for a reproducible acceptance record. |
| `PROGRESS.md`, `feature_list.json` | **Update after verification** | Record status, the APK evidence, and the honest limitation; planning does not touch them. |
| `docs/specs/desktop_mvp_build.md` | **Not now** | The sibling slice has its own spec/run; this slice must not pre-empt it. |
| `docs/risks-and-open-questions.md` | **Optional** | One row noting the debug MVP ships with no answer endpoint (F1) and that a real-user release still needs the corpus, backup stance, and provider terms — only if the orchestrator wants it tracked there. |
| `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, `CONSTRAINTS.md` | **Not needed** | Start/verify rules, product scope, accessibility baselines, and the shared-`commonMain` rule already govern; this slice adds no product invariant. |
| `ARCHITECTURE.md` | **Not needed** | It does not exist; no module, boundary, or dependency is added. |

## Honest limitations to record

- **No grounded answer is reachable on the shipped artifact.** `UnavailableAnswerService` is the default `App()` wiring and the backend has no `/ask` route (`chat_question_submission` F1), so the smoke can only exercise the failure notice; it must never claim an answered/abstained/source-card render. A grounded-answer smoke needs its own slice once a route exists.
- **Emulator, not a physical device** (`Medium_Phone_API_35`, API 35). Record the AVD; do not claim a device pass.
- **No automated UI/E2E harness.** Verification is manual `adb` + screenshots/dumps; nothing here becomes a persistent E2E command.
- **TalkBack speech is not capturable** here (precedent: `chat_accessibility`); the release smoke does not re-claim it.
- **Taps may land in the IME window** — dismiss the keyboard before pressing buttons (recorded harness quirk).
- The debug APK is unsigned-for-release and `isMinifyEnabled = false`; it is an MVP artifact, not a store-ready build.

## Risks and open decisions

- **R1 F1 blocks a full chat smoke.** The shipped artifact cannot produce a grounded answer; the smoke proves build/install/launch/journey and the honest failure path only. Accepted and recorded; not a defect.
- **R2 Emulator availability.** If no AVD/`adb` is usable, the build evidence still stands but the install/launch/journey evidence is blocked — record the exact blocker and do not claim the smoke.
- **R3 Stale-copy scope creep.** The banner could invite enumerating every accepted feature; the spec deliberately points at `PROGRESS.md`/`feature_list.json` so it cannot go stale again. `README.md` is edited only in "Running the MVP targets".
- **R4 A real blocker found during smoke.** If the artifact fails to install/launch, this release slice reports it as a finding rather than editing accepted product code; a fix becomes its own slice.
- **U1** Whether `docs/risks-and-open-questions.md` gains the "no answer endpoint at MVP debug release" row (optional).
- **U2** Whether `desktop_mvp_build` later reuses this slice's banner wording (its spec decides).

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/android_mvp_build.appendix.md`](android_mvp_build.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/android_mvp_build.md` remains the authoritative acceptance record.
