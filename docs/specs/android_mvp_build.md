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

Given a running emulator with `adb`, when the debug APK is installed (`adb install -r …`) and the launcher activity `com.jamarglex.manijero/.MainActivity` starts, then the app opens on the shared chat home with no crash, no ANR, and no fatal `AndroidRuntime` entry in `logcat`.

### The accepted land journey works on the installed artifact

Given the installed APK, when a person adds a land (name only) and a second land (name + municipality + both attributes), lists `Mis terrenos`, edits one land, and removes one land, then each accepted plain-Spanish confirmation appears, the store reflects exactly one change per action, and after a force-stop and relaunch the surviving lands are still shown.

### The shared chat surface and honest failure path work

Given the installed APK, when the chat home is shown, a suggested question fills the composer, and the question is submitted, then the app shows the accepted plain-Spanish failure notice with its `Reintentar` control (because no `/ask` is wired) and **never** renders the failed question as an answer; the privacy notice (`Privacidad y ayuda`) opens.

### The repository's own guidance is truthful

Given the checkout, when `./scripts/init.sh --check` is run, then its banner no longer claims accepted features are deferred, and it names the real verification command and the debug APK output path; `README.md` "Running the MVP targets" documents the real commands and the APK path instead of "common tasks may include … confirm task names".

### Nothing else changes

Given the slice ships, when the diff is inspected, then no `shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, or `knowledge/` source file changed; no Gradle file, dependency, module, or endpoint changed; and only the entry-point copy, the README section, the evidence/validation record, and `PROGRESS.md`/`feature_list.json` (after verification) differ.

## Repository research

Inspected directly (paths relative to the repository root):

- `scripts/init.sh` — auto-detects `ANDROID_HOME`/`ANDROID_SDK_ROOT`, writes `local.properties` when missing, then `--verify` runs `./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`; `--android` runs `:androidApp:assembleDebug`; `--check` prints a **stale banner** ("…retrieval, answer generation, response states, and the visual foundation remain deferred", lines 54-63). `--check` runs `./gradlew --version` and prints; the script executes checks and never starts a long-running service. No new mode is needed.
- `androidApp/build.gradle.kts` — `applicationId = "com.jamarglex.manijero"`, `minSdk` 29, `targetSdk`/`compileSdk` 37, `versionCode = 1`, `versionName = "1.0"`, `buildFeatures { compose = true }`, `release { isMinifyEnabled = false }`; depends on `project(":shared")` and `androidx.activity.compose` only. The debug artifact path is the standard `build/outputs/apk/debug/androidApp-debug.apk`.
- `androidApp/src/main/AndroidManifest.xml` — single exported `.MainActivity` launcher; `app_name` = `Manijero` (`androidApp/src/main/res/values/strings.xml`).
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt` — `enableEdgeToEdge()` then `setContent { App(landRepository) }` with `LandRepository(SharedPreferencesLandStorage(applicationContext))`: a thin platform adapter over the shared `App()`. Entry points stay platform-specific; no product behavior lives here.
- `gradle/libs.versions.toml`, `settings.gradle.kts`, root `build.gradle.kts` — modules `:shared`, `:androidApp`, `:desktopApp`; Compose Multiplatform 1.12.1, AGP 9.4.1, Kotlin 2.4.20. `shared/build.gradle.kts` declares iOS targets (kept for later reuse, out of MVP acceptance) and `withHostTest` for `:shared:testAndroidHostTest`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` — `App(landRepository, answerService: AnswerService = UnavailableAnswerService)`; the whole shared UI lives in `commonMain` and is what the APK renders.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` — `KtorAnswerService` posts to `<baseUrl>/ask`; `UnavailableAnswerService.ask` throws, so the shipped APK shows the failure path. `ChatConversation.kt` maps an unclassified throwable to `RequestFailure.SERVICE_ERROR` and never logs or renders it as an answer. This is `chat_question_submission` F1, and it defines the honest smoke limit.
- `README.md` — "MVP platforms" and "Running the MVP targets" say template task names "may include" the two Gradle tasks and to "confirm task names"; useful but stale/tentative for a release slice.
- `PROGRESS.md` — the accepted-state ledger; "Start and verify" lists the real commands. `feature_list.json` — `android_mvp_build` is `not_started`; `desktop_mvp_build` is the sibling release slice.
- Prior Android evidence in `docs/validations/{chat_accessibility,land_form_accessibility,land_list,remove_land}.md` — real emulator used (`emulator-5554`, `Medium_Phone_API_35`, 1080×2400 @ 2.625), `adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk`, `adb shell settings put system font_scale`, `adb shell uiautomator dump`; evidence written under gitignored `build/`; TalkBack speech is not capturable; taps inside the IME window can miss buttons (dismiss the keyboard first); pressing back with no IME up exits the app (no `BackHandler`, by design).
- `.gitignore` ignores `build/`, `local.properties`, `.gradle`; the APK and smoke captures are therefore untracked by construction.

Absent, and therefore not assumed: a `POST /ask` route or any answer provider; a persistent E2E/Compose UI-test harness; release signing/bundling config; CI; a physical Android device; an `ARCHITECTURE.md`.

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

## Implementation plan and tasks

1. Correct the `./scripts/init.sh --check` banner (`scripts/init.sh`) to point at `PROGRESS.md`/`feature_list.json`, name `./scripts/init.sh --verify`, the `--android`/`--desktop` commands, the debug APK path, and the no-`/ask` limitation. Confirm no other `scripts/init.sh` line changed.
2. Update `README.md` "Running the MVP targets" with the real commands and the APK path; keep "iOS: outside MVP delivery".
3. Run `./scripts/init.sh --verify`; confirm exit `0` and record the build-task list, the APK path, size, and `shasum -a 256`. Confirm the APK is newer than the sources (`ls -l`).
4. Boot the emulator (`Medium_Phone_API_35`), `adb install -r` the APK, and launch `com.jamarglex.manijero/.MainActivity`; capture the home screenshot + dump and a clean `logcat`.
5. Drive and capture the accepted journeys: suggested question → composer; submit → failure notice + `Reintentar`; add (name-only) and add (full) land; list; edit; remove; privacy; force-stop + relaunch persistence. Capture a `font_scale 2.0` confirmation pass (home/list/forms).
6. Inspect `logcat` for fatal crashes/ANRs and grep the captures for any question/answer/land text leakage; record any finding.
7. `git diff --stat` and confirm only `scripts/init.sh` and `README.md` (plus planning's spec) changed; no source/Gradle/contracts/backend/knowledge change.
8. Record the evidence in `PROGRESS.md` and `feature_list.json` with only the commands actually run and the honest limits; do not mark accepted until an independent validator signs off.

## Verification plan and evidence

Run from the repository root:

```sh
./scripts/init.sh
./scripts/init.sh --verify
ls -l androidApp/build/outputs/apk/debug/androidApp-debug.apk
shasum -a 256 androidApp/build/outputs/apk/debug/androidApp-debug.apk

adb wait-for-device
adb install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
adb shell am start -n com.jamarglex.manijero/.MainActivity
adb logcat -d | grep -iE "AndroidRuntime|FATAL|ANR"    # expect no fatal crash from the app
adb shell am force-stop com.jamarglex.manijero
adb shell am start -n com.jamarglex.manijero/.MainActivity

git diff --stat
git diff --check
```

Capture: the `./scripts/init.sh --verify` exit code and task summary; the APK path/size/sha256; the successful `adb install` line; a screenshot + `uiautomator` dump per screen (home, suggested→composer, failure notice with `Reintentar`, add name-only, add full, list, edit, remove, privacy, post-relaunch list); the `font_scale 2.0` confirmation; a crash-free `logcat` (or the exact fatal line); the final `git diff --stat` showing only `scripts/init.sh` + `README.md` (+ docs). Evidence goes under gitignored `build/` (precedent: `build/evidence/`, `build/evidence-validator/`).

## Honest limitations to record

- **No grounded answer is reachable on the shipped artifact.** `UnavailableAnswerService` is the default `App()` wiring and the backend has no `/ask` route (`chat_question_submission` F1), so the smoke can only exercise the failure notice; it must never claim an answered/abstained/source-card render. A grounded-answer smoke needs its own slice once a route exists.
- **Emulator, not a physical device** (`Medium_Phone_API_35`, API 35). Record the AVD; do not claim a device pass.
- **No automated UI/E2E harness.** Verification is manual `adb` + screenshots/dumps; nothing here becomes a persistent E2E command.
- **TalkBack speech is not capturable** here (precedent: `chat_accessibility`); the release smoke does not re-claim it.
- **Taps may land in the IME window** — dismiss the keyboard before pressing buttons (recorded harness quirk).
- The debug APK is unsigned-for-release and `isMinifyEnabled = false`; it is an MVP artifact, not a store-ready build.

## Validator checklist

- [ ] `./scripts/init.sh --verify` exits `0` and produces `androidApp/build/outputs/apk/debug/androidApp-debug.apk` (record path, size, sha256).
- [ ] `adb install -r` succeeds and `com.jamarglex.manijero/.MainActivity` launches with no fatal `logcat` entry or ANR, on a recorded emulator/device.
- [ ] The land journey works on the installed artifact: add (name-only), add (full), list, edit (one record changes), remove (one record removed), persistence across force-stop + relaunch.
- [ ] The chat home shows the submitted question as the plain-Spanish failure notice with `Reintentar` and **never** as an answer; the privacy notice opens.
- [ ] `./scripts/init.sh --check` no longer claims accepted features are deferred and names the real command + APK path; `README.md` documents the real commands and APK path.
- [ ] No `shared/`, `androidApp/`, or `desktopApp/` source changed; no Gradle/version-catalog/contracts/backend/knowledge change; no new module, dependency, mode, endpoint, or permission.
- [ ] Every claim in the evidence is backed by a capture or a command actually run; the no-`/ask` limitation, emulator-only note, and absent-E2E-harness limit are stated, and no grounded-answer/TalkBack/physical-device pass is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` record only the commands actually run and the real status; the slice is `accepted` only after this independent validation.

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

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/android_mvp_build.md. Release/verification slice: only the entry-point copy (scripts/init.sh --check banner), the README section, and the harness/evidence changed; no product code, Gradle, contract, backend, or knowledge file changed.
- scripts/init.sh: replaced only the stale --check banner body with text pointing at PROGRESS.md/feature_list.json and naming ./scripts/init.sh --verify, --android, --desktop, the debug APK path, and the no-/ask limitation; no mode/case/command changed (git diff scripts/init.sh touches only the heredoc body). README.md 'Running the MVP targets' now documents the real commands and the debug APK path instead of 'common tasks may include … confirm task names'.
- ./scripts/init.sh --verify -> exit 0, BUILD SUCCESSFUL, 91 actionable tasks (:shared:jvmTest, :shared:testAndroidHostTest, :androidApp:assembleDebug, :desktopApp:build). Artifact androidApp/build/outputs/apk/debug/androidApp-debug.apk: 36,014,513 bytes, shasum -a 256 = 4b4ab9d6cc50e026436116defdf3ffb79023dc84b7c715c6ce9b2c8e874ed538.
- Emulator smoke (AVD Pixel_4a_API_34 per environment; adb serial emulator-5554; ro.product.model sdk_gphone64_arm64; API 34; 1080x2340 @ 440dpi; sys.boot_completed=1): adb install -r <debug apk> -> Success; adb shell am start -n com.jamarglex.manijero/.MainActivity launched the shared chat home. logcat scan after the full journey: 0 'FATAL EXCEPTION', 0 'ANR in', 0 'E AndroidRuntime'; no land or question text in logcat.
- Land journey on the installed APK (screenshots + uiautomator dumps under gitignored build/evidence/): add name-only 'Los Olivos' (Riego: No lo sé / Producción: No lo sé) -> saved confirmation; add full 'La Solana' (Municipio: Martos, Regadío, Ecológico) -> list shows both in creation order; edit 'La Solana' -> 'La Solana Alta' (one row changed, confirmation 'Los cambios se han guardado…'); remove 'Los Olivos' (confirmation names the land) -> one row removed; adb shell am force-stop then relaunch -> Mis terrenos still shows only 'La Solana Alta' with its attributes and no stale confirmation (persistence).
- Chat surface on the installed APK: chat home renders; tapping a suggested question fills the composer with its exact text; submitting shows the plain-Spanish service-unavailable failure notice plus 'Reintentar', and the question is NEVER rendered as an answer (only a 'Tú' entry plus a separate failure notice); the privacy notice ('Privacidad y ayuda') opens the shared disclosure screen. This is the honest failure path only: the shipped default is UnavailableAnswerService and the backend has no /ask route, so no grounded/answered/abstained/source-card render was exercised or claimed.
- Light font_scale 2.0 confirmation pass (home + Mis terrenos): no horizontal overflow (max text right edge 1014 of 1080) and all content wraps; font_scale reset to 1.0 afterward. The deep accessibility baselines stay with chat_accessibility/land_form_accessibility.
- Scope: git status --porcelain shows only M README.md, M scripts/init.sh, M feature_list.json, plus the untracked docs/specs/android_mvp_build.md. No shared/, androidApp/, desktopApp/, contracts/, backend/, knowledge/, Gradle, or version-catalog file changed; git diff --check clean. Evidence lives under gitignored build/evidence/ (20 captures, 01–19).
- Honest limits: emulator-only (no physical device); the debug APK is unsigned-for-release and isMinifyEnabled = false; no automated UI/E2E harness exists (verification is manual adb screenshots/dumps); TalkBack speech is not captured; and because UnavailableAnswerService is the default wiring and there is no /ask route, only the failure notice is a reachable chat outcome. Self-verified and ready for independent validation; left 'passing', not 'accepted'.
- Independent validator ACCEPTED this feature (2026-10-16, record: docs/validations/android_mvp_build.md). It did not trust the implementer report and independently reran ./scripts/init.sh --verify (exit 0, BUILD SUCCESSFUL) plus a full --rerun-tasks rebuild (91 tasks executed, 0 from cache) producing a byte-identical APK (36,014,513 bytes; sha256 4b4ab9d6cc50e026436116defdf3ffb79023dc84b7c715c6ce9b2c8e874ed538), confirmed the --check banner no longer claims accepted features are deferred and names the real command and APK path, and confirmed the four modes/help are unchanged. It reinstalled the APK on a real emulator (emulator-5554, sdk_gphone64_arm64, API 34, Android 14, 1080x2340) and re-drove every claimed journey with its own screenshots/uiautomator dumps under build/evidence-validator/: add name-only, add full, list, edit one row, remove one, force-stop + relaunch persistence; chat home + suggested question -> composer -> plain-Spanish failure notice + Reintentar with the question never rendered as an answer (retry reproduces the notice with one Tu entry); privacy notice opens and Volver returns; font_scale 2.0 wraps with max right edge 1014/1080. logcat: 0 FATAL EXCEPTION, 0 ANR in, 0 app AndroidRuntime crash, no land/question text. It confirmed the honest limit independently: backend/app/main.py exposes only @app.get("/health") and App() defaults to UnavailableAnswerService (which throws), so no grounded/answered/abstained/source-card render is reachable. Scope confirmed clean (only scripts/init.sh banner body, README.md, feature_list.json, PROGRESS.md, and the new spec/validation; no shared/androidApp/desktopApp/Gradle/contracts/backend/knowledge change; git diff --check clean). Non-blocking findings N1 (spec's illustrative AVD name differs from the actual Pixel_4a_API_34), N2 ("20 captures" wording), N3 (uiautomator selected=false on radio rows, screenshots/saved record confirm), N4 (carried emulator-only/debug/no-harness/TalkBack limits, none over-claimed). A feature-scoped security review found no blocking issue.
