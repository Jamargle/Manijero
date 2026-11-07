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
