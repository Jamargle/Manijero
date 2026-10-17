# Validation: `android_mvp_build`

- Feature id: `android_mvp_build`
- Spec: `docs/specs/android_mvp_build.md`
- Validator role: independent feature validator (feature-validator skill)
- Date: 2026-10-16
- Verdict: **accept**

## Review target

- Spec path: `docs/specs/android_mvp_build.md` (new, untracked).
- Claimed status in `feature_list.json`: `passing` (self-verified; this pass is the
  independent validation).
- Diff: modified `scripts/init.sh` (heredoc banner body only), `README.md`
  ("Running the MVP targets"), `feature_list.json`, `PROGRESS.md`; new untracked
  `docs/specs/android_mvp_build.md`. No other path changed.
- Method: did not trust the implementer's report. Re-ran the build with
  `--rerun-tasks`, reinstalled the APK on the running emulator, and re-drove every
  claimed journey with my own screenshots/`uiautomator` dumps under gitignored
  `build/evidence-validator/`.

## Checks rerun and results

| Check | Result |
|---|---|
| `./scripts/init.sh --verify` | exit `0`; `BUILD SUCCESSFUL`; 91 actionable tasks (`:shared:jvmTest`, `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, `:desktopApp:build`) |
| Full rebuild `./gradlew … --rerun-tasks` | exit `0`; `BUILD SUCCESSFUL`; **91 tasks executed, 0 from cache** |
| APK artifact | `androidApp/build/outputs/apk/debug/androidApp-debug.apk` exists; 36,014,513 bytes; `shasum -a 256 = 4b4ab9d6cc50e026436116defdf3ffb79023dc84b7c715c6ce9b2c8e874ed538` — byte-identical after the independent rebuild and identical to the recorded claim |
| `./scripts/init.sh --check` banner | No "remain deferred" text (grep count 0); names `./scripts/init.sh --verify`, `--android`/`--desktop`, the APK path, the `PROGRESS.md`/`feature_list.json` pointer, and the no-`/ask` limitation |
| `./scripts/init.sh --help` / modes | Help and the four modes unchanged; `git diff scripts/init.sh` touches only the `--check` heredoc body |
| Emulator | `emulator-5554`; model `sdk_gphone64_arm64`; API 34; Android 14; 1080x2340 |
| `adb install -r` | `Success`; relaunch after `am force-stop` clean |
| Land journey | add name-only `Los Olivos` (Riego/Producción `No lo sé`) → saved confirmation; add full `La Solana` (Martos / Regadío / Ecológico) → list shows both in creation order; edit `La Solana` → `La Solana Alta` (one row changed, "Los cambios se han guardado…", other row unchanged); remove `Los Olivos` (confirmation names the land) → one row removed |
| Persistence | `am force-stop` + `am start` → `Mis terrenos` shows only `La Solana Alta`, attributes intact, no stale confirmation |
| Chat home + honest failure | suggested question fills the composer with its exact text; submit → plain-Spanish "El servicio no está disponible en este momento…" notice + `Reintentar`; the question appears **only** as a `Tú` entry and never as an answer. `Reintentar` re-produces the same notice with a single `Tú` entry (no duplicate user message) |
| Privacy notice | `Privacidad y ayuda` opens the shared disclosure screen with the local/remote/limit sections; `Volver` returns |
| `font_scale 2.0` pass | home and `Mis terrenos` wrap with max text right edge 1014 of 1080 (no horizontal overflow); reset to 1.0 |
| `logcat -d` scan | 0 `FATAL EXCEPTION`, 0 `ANR in`, 0 `E AndroidRuntime` app crash; no land or question text in the log (the only `AndroidRuntime` lines are the `uiautomator` dump commands, uid 2000) |
| Scope | `git status --porcelain` = `M PROGRESS.md`, `M README.md`, `M feature_list.json`, `M scripts/init.sh`, `?? docs/specs/android_mvp_build.md`; `git diff --check` clean |
| No `/ask` / grounded path | `backend/app/main.py` exposes only `@app.get("/health")`; `App(answerService = UnavailableAnswerService)` is the default wiring and `UnavailableAnswerService.ask` throws — no answered/abstained/source-card render is reachable |

## Scope discipline

Only `scripts/init.sh` (banner body), `README.md` ("Running the MVP targets"),
`feature_list.json`, `PROGRESS.md`, and the new spec/validation differ. No
`shared/`, `androidApp/`, `desktopApp/`, `contracts/`, `backend/`, `knowledge/`,
Gradle, or version-catalog file changed; no new module, dependency, mode,
endpoint, or permission. `git diff --check` is clean. The APK and the smoke
captures are untracked by construction (`.gitignore` covers `build/`).

## Findings

### N1 (non-blocking, documentation) — spec names a different illustrative AVD

- Severity: low.
- Evidence: the spec's technical approach/honest-limitations mention
  `Medium_Phone_API_35` as a prior AVD, but the actual run used `Pixel_4a_API_34`
  (API 34, Android 14, `sdk_gphone64_arm64`, 1080x2340).
- Why it matters: only clarity. `feature_list.json` and `PROGRESS.md` record the
  **actual** AVD/serial/model/API honestly, so no claim is wrong.
- Required change: none (optional wording tidy-up in the spec). Not a defect.

### N2 (non-blocking, evidence description) — capture count wording

- Severity: low.
- Evidence: `feature_list.json` says "20 captures, 01–19"; `build/evidence/`
  actually holds 19 PNG+XML pairs (38 files) plus `logcat_fatal_scan.txt`.
- Why it matters: cosmetic; the directory is gitignored and the captures exist.
- Required change: optional (say "19 captures"). Not a defect.

### N3 (informational) — `uiautomator` does not reflect radio selection

- Severity: informational.
- Evidence: on the add/edit forms, the land form's radio rows report
  `selected=false`/`checked=false` even when visibly selected; screenshots show
  the correct selection (`Regadío`, `Ecológico`) and the saved record matches.
- Why it matters: a dump alone cannot assert form selection; the screenshot is the
  evidence. No product impact. (Precedent: `land_form_accessibility`).

### N4 (carried, honest limits)

- Emulator-only (no physical device); debug APK unsigned-for-release,
  `isMinifyEnabled = false`; no automated UI/E2E harness exists; TalkBack speech
  not captured; and only the failure notice is a reachable chat outcome
  (`UnavailableAnswerService` default, no `/ask` route). All are stated in the
  spec, `PROGRESS.md`, and `feature_list.json` and none is over-claimed.

The security checklist found no blocking issue: this slice changes no product,
backend, contract, or knowledge code; no new network route, permission,
dependency, secret, or persistence path; the logcat scan confirms no land or
question content is logged; the artifact is a debug build only.

## Documentation / harness state

- `README.md` "Running the MVP targets" now documents the real commands
  (`./scripts/init.sh --verify` / `--android` / `--desktop`) and the debug APK path, and
  keeps the iOS-out-of-scope statement.
- The `./scripts/init.sh --check` banner points at the living documents instead of
  enumerating features, so it cannot go stale again, and states the honest
  limitation.
- `PROGRESS.md` / `feature_list.json` record only the commands actually run, the
  artifact size/sha256, the real AVD, the clean logcat, and the honest limits, and
  leave the slice at `passing` (not `accepted`) pending this independent pass.
- `docs/validations/android_mvp_build.md` created at validation time per the
  repository convention.

## Verdict

**accept.** The feature satisfies the spec: `./scripts/init.sh --verify` produces the
debug APK (rebuilt and byte-identical), the APK installs and launches cleanly on
the emulator, the accepted land journey and persistence work, the chat failure
path is honest and never renders the question as an answer, the privacy notice
opens, and the repository's own guidance is now truthful. Scope is clean and the
recorded evidence reproduced. Recommended state update: set `android_mvp_build`
to `accepted` and record this validation.
