# qa_real_device_check — validation

Spec: [docs/specs/qa_real_device_check.md](../specs/qa_real_device_check.md) · appendix: [docs/specs/qa_real_device_check.appendix.md](../specs/qa_real_device_check.appendix.md)

## Verdict (2026-11-07, independent validator)

accept, condition: pending owner walkthrough (live `./scripts/init.sh --qa-check` against QA, appendix "Owner walkthrough").

## Checks rerun (all offline; no live QA contacted, no key read)

- `./scripts/init.sh --feature qa_real_device_check`: passed (five published commands, screenshot baseline unchanged).
- `./scripts/init.sh --fast`: 10 offline checks passed (backend-tests 2561 passed, 7 skipped).
- `--verify` not rerun: no Android, packaging, or `desktopApp` change; only `shared/build.gradle.kts` gained a test-only task.

## Review

- Scope: Desktop only; no Android/adb/emulator path; Android cut recorded in `docs/progress/known-limitations.md`.
- Key handling: Python side checks the key path with `is_file()` only and never opens it; the Kotlin driver gets it only through the build-generated classpath resource (`desktopPilotToken()`), never a property, argument, or environment entry; result line and log carry outcome codes, source count, address only. `runDesktopQaCheck` is excluded from `jvmTest` and guarded by `QaCheckGuardTest`; tests use fakes and `MANIJERO_PILOT_TOKEN_FILE`.
- `--local-smoke` unchanged (`local_smoke.py` not modified; its tests pass); `qa_check` added to the service-never-imports-operator-modules list.
- Docs per spec: constraints, ARCHITECTURE, owner guide, backend README, known limitations, risks, PROGRESS, `feature_list.json` updated.

## Only the owner walkthrough can show

- The real QA https address answers `/health` and the app's first question gets an answer with sources (it may need the one retry).
- QA accepts the single `Útil` rating (adds one `useful` to QA's feedback count).
- The `--qa-stop` then `--qa-check` run prints the service-step failure line.

## Limits that remain

The render is offscreen, not the real window; no Android device or emulator check exists.

## Repair review (2026-11-07, after the owner walkthrough found `outcome=not_qa_build`)

Verdict: accept, condition: pending owner walkthrough (rerun of live `./scripts/init.sh --qa-check` against QA).

- Cause confirmed: the `doFirst` classpath append never reaches the forked test JVM. Fix sets `classpath = jvmTest classpath + files(environmentFolder, pilotTokenFolder).builtBy(generateEnvironmentResource, generatePilotTokenResource)` at configuration time; task dependencies come from `builtBy`; the configuration cache is reused in the focused tier.
- Key handling unchanged: resource folders only, no argument, JVM property, environment entry, or log carries the key. `QaCheckGuardTest` now asserts the new classpath line, both generator names, and no `doFirst`; its other assertions (folders and generators named only inside the task) are intact. `PilotTokenGuardTest` untouched.
- Gradle wiring test `backend/tests/test_qa_check_gradle_wiring.py` runs the real task with a fake key and fake address file in a temp folder and a closed loopback address (`https://127.0.0.1:1`); offline, zero cost; asserts `unreachable` and that the fake key appears in no output. Mutation check: against the old `doFirst` wiring it fails (`outcome='not_qa_build'`); the repaired file was restored byte-identical (same blob as the implementer's) and the test passes again.
- `qa_check.py`: `not_qa_build` and `no_access_key` now have their own plain FAIL lines (key line points at `--qa-settings-setup`); spec scenario 6 and the owner-guide table agree.
- Checks: `--feature qa_real_device_check` passed (114 + 1 wiring test, Gradle focused block); `CI=true --fast` 10 offline checks passed. `--verify` not rerun: only a test-only task changed, no Android, packaging, or `desktopApp` change.
- Only the walkthrough can show: the real QA run now answers with sources and sends `Útil`.
- Notes: the wiring test is skipped by `--fast` (needs `MANIJERO_GRADLE_WIRING_TEST=1`, set only by the focused block). The comment above the task (shared/build.gradle.kts, "when it starts") is loose but harmless.
