# Appendix — `android_mvp_build`

Planning and verification record for [`docs/specs/android_mvp_build.md`](android_mvp_build.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/android_mvp_build.md` remains the authoritative
acceptance record.

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

## Validator checklist

- [ ] `./scripts/init.sh --verify` exits `0` and produces `androidApp/build/outputs/apk/debug/androidApp-debug.apk` (record path, size, sha256).
- [ ] `adb install -r` succeeds and `com.jamarglex.manijero/.MainActivity` launches with no fatal `logcat` entry or ANR, on a recorded emulator/device.
- [ ] The land journey works on the installed artifact: add (name-only), add (full), list, edit (one record changes), remove (one record removed), persistence across force-stop + relaunch.
- [ ] The chat home shows the submitted question as the plain-Spanish failure notice with `Reintentar` and **never** as an answer; the privacy notice opens.
- [ ] `./scripts/init.sh --check` no longer claims accepted features are deferred and names the real command + APK path; `README.md` documents the real commands and APK path.
- [ ] No `shared/`, `androidApp/`, or `desktopApp/` source changed; no Gradle/version-catalog/contracts/backend/knowledge change; no new module, dependency, mode, endpoint, or permission.
- [ ] Every claim in the evidence is backed by a capture or a command actually run; the no-`/ask` limitation, emulator-only note, and absent-E2E-harness limit are stated, and no grounded-answer/TalkBack/physical-device pass is claimed.
- [ ] `feature_list.json`/`PROGRESS.md` record only the commands actually run and the real status; the slice is `accepted` only after this independent validation.

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
