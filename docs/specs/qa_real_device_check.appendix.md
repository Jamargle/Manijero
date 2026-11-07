# qa_real_device_check — appendix

## Repository research

### Files inspected

- `feature_list.json` — entry, dependencies (both accepted); title updated at planning to Desktop-only scope.
- `docs/specs/qa_server_deployment.md` — QA address in `qa-address.local` and QA settings, `/health` public probe, pilot token auth on `/ask` and `/feedback`, test-data-only rule.
- `docs/specs/client_environment_builds.md` — `-PmanijeroEnvironment=qa`, QA key path, `.manijero-qa` data folder, token only in the `run` task.
- `docs/specs/local_end_to_end_smoke.md` — offscreen Desktop driver, result-line protocol, orchestrator shape, owner-command wording.
- `backend/app/local_smoke.py` — `Runner`, `SubprocessRunner`, `SystemTools`, `smoke_lock`, Java/wrapper messages, `_run_desktop` pattern to reuse.
- `backend/app/qa_deployment.py` — `ADDRESS_FILE_ENV`, `_read_address_file`, `system_public_probe` (https `/health`, service name check).
- `backend/scripts/qa_service.py`, `backend/scripts/local_rag.py` — entry-point patterns (one sentence plus log on unexpected errors).
- `backend/app/environment_profiles.py` — `qa_home()`, `QA_CLIENT_ID`, `credential_paths(...)` for the key path.
- `backend/app/pilot_guard.py`, `feedback_api.py` — `/feedback` is gated like `/ask`; `/health` and `/ready` are open.
- `scripts/init.sh` (lines 227–276) — `--qa-*` and `--local-smoke` dispatch blocks, Java resolution.
- `shared/build.gradle.kts` (lines 158–187, 297–330) — `jvmTest` exclusion and `runDesktopLocalSmoke`.
- `desktopApp/build.gradle.kts` — `generateEnvironmentResource`, `generatePilotTokenResource`, `run` classpath `doFirst` pattern.
- `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` — QA app wiring the driver must mirror.
- `shared/src/jvmMain/.../platform/DesktopEnvironment.kt`, `DesktopPilotToken.kt` — classpath resources the driver reads.
- `shared/src/jvmTest/.../smoke/SmokeUiScript.kt`, `DesktopLocalSmokeRun.kt`, `DesktopSmokeDriverTest.kt` — driver, live entry, MockEngine tests.
- `shared/src/commonMain/.../connection/LocalSmoke.kt` — question constant, outcome codes, read-only address store.
- `shared/src/commonMain/.../chat/AnswerService.kt`, `AnswerFeedback.kt`, `ChatTestTags.kt`, `ChatTranscript.kt` — `sendFeedback` with the same token rule; rating row under answered and abstained replies; failure line has no tag yet.
- `shared/src/jvmTest/.../platform/PilotTokenGuardTest.kt`, `LocalSmokeGuardTest.kt` — rules the new task must respect.
- `docs/constraints/hosting-and-pilot.md` (token rule, line ~66), `docs/constraints/operations.md` (line 20) — rules to update.
- `docs/owner-guide.md` "Deploy, update, ... QA", "Owner walkthrough: QA", "Build the QA test apps" — sections to extend.

### Planner decisions

1. Command `./scripts/init.sh --qa-check`, separate block (it needs Java resolution, which the `--qa-*` block does not do) and a separate entry script.
2. "Uses the QA Desktop app" means the shared `App` with the QA build's generated environment and key resources, rendered offscreen, the same as `--local-smoke`; the real window is not opened (cannot be automated headless).
3. The key reaches the test JVM only as the classpath resource `generatePilotTokenResource` already writes for `run`; no new read path. This widens "only the `run` task" to also the test-only check task, recorded in `hosting-and-pilot.md`.
4. An abstention fails (owner: "answered with sources"); the feedback step still runs on an abstention so the owner learns both facts.
5. One `Útil` press, never retried, so a run adds at most one count.
6. A Python `/health` probe runs first so an unreachable QA fails in seconds, before a long build.

### Existing patterns to follow

- Owner output: English fixed lines, `PASS`/`FAIL` per step, one `Result:` line, exit `0`/`1`/`2` (`docs/constraints/operations.md`).
- Live checks are excluded from `jvmTest` and self-skip without their result property; no tier runs them.
- Token never in JVM properties, env, or args; any token-bearing classpath folder is on one named task's classpath only. (A Test task needs it set at configuration time; see Feature evidence repair.)

### Current gaps

- No `FEEDBACK_FAILED` test tag; added (tag only).
- The fixed question was never asked against QA's packaged release; it may abstain there. The walkthrough will show it; changing the question is out of scope unless it abstains.

## Implementation plan

1. Add `ChatTestTags.FEEDBACK_FAILED` and tag the failure line; rerun chat screenshots unchanged.
2. Add `SmokeUiScript.rateUseful(test)` (press `FEEDBACK_USEFUL` once, wait 30 s for `FEEDBACK_SENT`/`FEEDBACK_FAILED`).
3. Add jvmTest `QaCheckProtocol.kt` (feedback codes, `not_qa_build`, `no_access_key`, result line) and `DesktopQaCheckRun.kt`.
4. Register `runDesktopQaCheck` in `shared/build.gradle.kts`; exclude `DesktopQaCheckRun` from `jvmTest`.
5. Add `DesktopQaCheckDriverTest` (MockEngine over an https base URL with a fake token) and `QaCheckGuardTest`.
6. Refactor `local_smoke.py` helpers for reuse (lock message parameter), with `test_local_smoke.py` unchanged and green.
7. Write `backend/app/qa_check.py` and `backend/scripts/qa_check.py`; add `--qa-check` to `scripts/init.sh` (dispatch, `usage`, `--check`).
8. Write `test_qa_check.py` and `test_qa_check_commands.py`.
9. Update the durable docs listed in the contract; append Feature evidence.

## Verification plan

- Focused block via `./scripts/init.sh --feature qa_real_device_check` — all green.
- `test_qa_check.py`: each scenario 2 gap gives its line and exit 1 with no runner call; key file is never opened (a key file with unreadable mode still passes the existence check); placeholder and non-https addresses refused; probe failure skips Gradle; each result code and feedback code maps to its fixed line; missing/malformed/duplicate result line and timeout give "could not run"; Gradle argv is exactly the contract's; Ctrl+C wording; no output contains a fake token value.
- `test_qa_check_commands.py`: extra argument exit 2; no dev environment gives the not-set-up pair; `usage` lists `--qa-check`.
- `DesktopQaCheckDriverTest`: answered with sources plus 204 feedback gives `answered`/`sent`; `/ask` and `/feedback` carry the bearer over https; 500 feedback gives `failed`; abstained still rates; saved other address sends nothing; no land store opened.
- `QaCheckGuardTest`: only `runDesktopQaCheck` in `shared/build.gradle.kts` references `generated/pilotToken`; it sets no token property or env; `DesktopQaCheckRun` excluded from `jvmTest` and absent from every `init.sh` tier.
- E2E: the live run is the owner walkthrough; offline coverage above is the persistent check.

## Evidence to capture

- Focused block result, one line per command.
- Names of the new tests and their pass counts.
- `--local-smoke` output unchanged (test_local_smoke green).
- Screenshot verify green with no golden change.

## Owner walkthrough (for the orchestrator)

1. Run `./scripts/init.sh --qa-status`; expect `Result: QA is running at ...` (deploy first if not).
2. Run `./scripts/init.sh --qa-check`; expect the three `PASS` lines and the passed `Result:`.
3. Run `./scripts/init.sh --qa-stop`, then `--qa-check`; expect `FAIL  Service: ...` and the service-step result; run `--qa-deploy` to restore.

## Feature evidence

2026-11-07 (implementer; all offline, no live QA, no key read):

- `bash -n scripts/init.sh`: ok.
- `./scripts/init.sh --backend-tests tests/test_qa_check.py tests/test_qa_check_commands.py tests/test_local_smoke.py -q`: 114 passed (`--local-smoke` output unchanged; `local_smoke.py` not modified).
- `./gradlew --quiet :shared:jvmTest --tests 'smoke.*' 'platform.*' 'chat.*'`: green; new `DesktopQaCheckDriverTest` 12 passed, `QaCheckGuardTest` 4 passed.
- `./gradlew --quiet :shared:runDesktopQaCheck --dry-run`: ok (depends on desktopApp environment and access-key generators).
- `./gradlew :shared:verifyDesktopScreenshots --tests '...ChatHomeScreenshotsTest'`: PASSED, no golden changed.
- `./scripts/init.sh --feature qa_real_device_check`: Focused tier passed. `./scripts/init.sh --fast`: 10 offline checks passed (backend-tests 2561 passed, 7 skipped).
- Also changed: `test_local_rag_service.py` operator-module list gains `qa_check`.
- Not run: `--verify` (no Android surface or packaging change); live `--qa-check` is the owner walkthrough.

2026-11-07 repair (implementer; owner walkthrough printed `PASS Service` then `FAIL Answer: the check could not run`, result line `not_qa_build`):

- Root cause: the generated environment and access-key folders were appended to `runDesktopQaCheck`'s classpath in `doFirst`, which Gradle ignores for the forked test JVM (reproduced offline: JVM class path lacked both folders, `desktopEnvironment()` returned Local). Now `classpath = jvmTest classpath + files(...)` at configuration time, `builtBy` the two generators. Key still never in argv, JVM properties, or environment.
- `qa_check.py`: well-formed `not_qa_build` and `no_access_key` now get their own plain lines (build problem: send the log; key: run `--qa-settings-setup`) instead of "could not run". Spec scenario 6, owner-guide table updated.
- `QaCheckGuardTest` updated to the new wiring shape (same checks, plus no `doFirst` in the block): green. `test_qa_check.py`: new parametrized test for the two lines.
- New `backend/tests/test_qa_check_gradle_wiring.py` (runs the real task offline: fake key and address in a temp folder, `https://127.0.0.1:1`): outcome `unreachable`, never `not_qa_build`/`no_access_key`; skipped unless `MANIJERO_GRADLE_WIRING_TEST=1`, set by the new focused-block line.
- `./scripts/init.sh --feature qa_real_device_check`: passed (114 + 1 wiring test passed, jvmTest green).
- `CI=true ./scripts/init.sh --fast`: 10 offline checks passed (backend-tests 2561 passed, 8 skipped).

## Validator checklist

- [ ] Scope is Desktop only; no Android, adb, or emulator path; non-goals respected.
- [ ] Acceptance scenarios 1–8 pass, with test evidence.
- [ ] No code path opens the QA key except the existing Gradle generator; no token in output, logs, properties, or args.
- [ ] `--local-smoke` output and the `--qa-*` commands unchanged.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature qa_real_device_check`.
- [ ] Durable documentation impact followed, including known limitations for the Android scope cut.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly; accept may be conditional on the owner walkthrough.

## Handoff

- Status: `passing`; owner-walkthrough repair done (2026-11-07), not committed.
- Next role: validator. Check the repair only: `shared/build.gradle.kts` classpath wiring, `QaCheckGuardTest`, `backend/tests/test_qa_check_gradle_wiring.py`, the two new `qa_check.py` lines.
- Then the owner reruns `docs/owner-guide.md` "Owner walkthrough: QA check" steps 1-3 against live QA.
- If every step matches: orchestrator records it as evidence only, sets `accepted`, deletes this section, commits `feat: complete qa_real_device_check`.
- Last checks: `--feature qa_real_device_check` passed; `--fast` 10/10 passed.
