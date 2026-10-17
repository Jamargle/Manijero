# Validation — `land_data_disclosure`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`land_data_disclosure` implementation against `docs/specs/land_data_disclosure.md`.

Feature id: `land_data_disclosure`. Spec: `docs/specs/land_data_disclosure.md`.
Claimed status: `passing` (self-verified by the implementer). State update:
the orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair anything; it re-ran the acceptance
checks, read the diff, and applied the rubric/security criteria from the
`feature-validator` skill body (its `references/` files are absent in this
worktree).

## Review target

`git diff --name-status 0900fce` before and after validation showed exactly the
expected footprint (unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- New (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosure.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt`.
- New (tests): `shared/src/commonTest/kotlin/com/jamarglex/manijero/privacy/LandDataDisclosureTest.kt`.
- New (docs): `docs/specs/land_data_disclosure.md` (planner artifact).
- Modified (docs/harness): `CONSTRAINTS.md`, `feature_list.json`, `PROGRESS.md`.

Untouched: `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`,
`androidApp/`, `desktopApp/`, `shared/src/iosMain/`, every Gradle file, and
`scripts/init.sh`. `git diff --check` clean. No new module, dependency, ViewModel,
endpoint, persistence, navigation, or logging.

## Independent checks and results

Re-run by the validator with `--rerun-tasks` where relevant, so results are real
executions, not cached output:

- `python3 contracts/validate_examples.py` → exit 0,
  "Validated 2 request and 3 response examples against answer_api_contract".
- Focused `:shared:jvmTest --tests "...privacy.LandDataDisclosureTest"` → 3 tests / 0 failures.
- `:shared:jvmTest --rerun-tasks` → **184 tests / 0 failures** (20 suites,
  `LandDataDisclosureTest` 3/0; was 181, +3, no test removed).
- `:shared:testAndroidHostTest --rerun-tasks` → **170 tests / 0 failures** (16 suites; was 167, +3).
- `:shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `:desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL, 72 tasks, debug APK.
- `./scripts/init.sh --verify` → exit 0, BUILD SUCCESSFUL (91 tasks).
- `git diff --check` → clean.
- Byte-for-byte UTF-8 string comparison vs the spec → 22/22 identical, each key
  once, `strings.xml` numstat `+22/-0`, no existing string changed or deleted.
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero` →
  matches only under `theme/ManijeroColors.kt`.
- Logging grep (`println|Log.|Logger|printStackTrace|NSLog`) → no matches.
- `MinimalLandContext` → still exactly four contract properties (`id` + the three
  sendable dimensions).

## Spec conformance

- **Essential facts visible before asking.** `ChatHomeScreen` unconditionally
  renders `chat_home_privacy_summary` plus a labelled `chat_home_privacy`
  `TextButton` (`onPrivacyClick` → `AppDestination.Privacy`); `App()` always
  passes a non-null handler, so the control is live on Android/Desktop.
- **Navigation and back.** The `PrivacyScreen` branch is wired with
  `onBack = { destination = AppDestination.Chat }`; `destination` and
  `conversation.state` are `remember`-held, so the typed question and transcript
  are preserved on `Volver`.
- **Nothing over-promised.** The copy covers device-local storage, no account,
  name + municipality/riego/producción, view/edit/remove, no automatic internet
  copy, no automatic backup; the question is sent as written, plus each land's
  opaque id and only the needed attributes, unknown as `no lo sé`, name/notes
  never sent. It promises no backup/cloud/confidentiality beyond the service's
  own terms, names no land/id, makes no eligibility/legal claim, and points to a
  human contact (oficina comarcal agraria / cooperativa).
- **Pinned module + real-payload test.** `privacy/LandDataDisclosure.kt` is
  Compose-free; `LandDataDisclosureTest` encodes a real production request via
  `askRequestFor` (the same function `ChatHomeState` uses) with a
  fully-populated land and an all-dimension question, asserts the encoded
  optional keys are exactly `{municipality, water_regime, production_method}`,
  and separately asserts `SHARED_LAND_ATTRIBUTES.size == descriptor.elementsCount - 1`.
  A fourth sendable dimension fails on both guards.
- **Scope discipline.** Only the files above changed; `theme/` values unchanged;
  no new module/dependency/ViewModel/route. `CONSTRAINTS.md` gained exactly the
  one "Land data disclosure" MUST rule the spec required.

## Findings (non-blocking)

- **N1 — workflow.** The implementer advanced `feature_list.json` to `passing`
  and wrote the `PROGRESS.md` line before independent validation, matching the
  established repo workflow (earlier validators logged the same as non-blocking).
- **N2 — literal feature-list verification NOT performed (recorded honestly).**
  The manual low-digital-confidence comprehension check was not run and no
  reviewer was available. The implementation records it as an outstanding manual
  check rather than claiming it. It does not block acceptance of the code and
  remains an open follow-up (owner: a human review session / `chat_accessibility`).
- **N3 — placement / above-the-fold.** The summary + control render after the
  transcript, suggestions, composer, and the `Preguntar`/`Mis terrenos` row, so
  on a small screen or `fontScale 2` they may sit below the fold. This is the
  spec-mandated placement (§3), so the implementation is compliant; flagged for
  UX review by `chat_accessibility`.
- **N4 — unknown sentinel wording.** The copy says an unknown value is sent as
  «no lo sé» while the wire token is `unknown`; the wording is spec-mandated
  byte-for-byte, so this is spec-faithful, not an implementation defect.
- **N5 — rendered-evidence gap.** `widthDp = 320`/`fontScale = 2f` no-clipping
  and greyscale legibility are structural/compile-based (previews compile; no
  preview/screenshot runner). No UI/E2E or inspected render is claimed; owner
  `chat_accessibility`.

## Security assessment

Scoped to this diff: informational-only, stateless screen; no new data flow,
network call, permission, persistence, or dependency. It logs/prints no question,
land data, or exception (grep clean), and exposes no personal data. The copy
makes no unverifiable confidentiality/backup claim and names no land or id. No
blocking issue.
