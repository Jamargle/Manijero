# `local_end_to_end_smoke` acceptance

## Verdict

**Accepted** on 2026-11-01. The earlier validator passes found no remaining defect and blocked only on the owner walkthrough. The owner ran it on 2026-11-01, and an independent validator accepted the recorded evidence.

## Independent verification

- Validators: focused block (9 command lines), `CI=true ./scripts/init.sh --fast`, and `--verify` passed offline with fakes and temporary homes, and the [appendix](../specs/local_end_to_end_smoke.appendix.md#validator-checklist) checklist was reviewed. Two owner-walkthrough defects were repaired and revalidated. Repair 2: Java resolution, which no longer accepts Apple's `/usr/bin/java` stub. Repair 3: `espresso-core` 3.5.0 → 3.7.0 for API 34+, with an offline version guard.
- Owner walkthrough ([owner guide](../owner-guide.md#owner-walkthrough-local-smoke-test)) on the owner's Mac, emulator `Medium_Phone_API_37.0`, Java from the scripts' own resolution:
  - Step 3 printed `PASS` for Desktop and the Android emulator, then the passed `Result:` line.
  - Step 4, with the service stopped, printed the "did not run … `--local-rag-start`" result.
  - Step 5 passed again.
  - The final stop step stopped the service.
  - Step lines are in the appendix "Feature evidence".

## Limits

- Walked through once, on one Mac and one API 37 emulator, from the integration worktree `integration/2026-11-01-batch-3`.
- Whether the emulator app kept its lands after the run was not separately reported; the owner confirmed all steps matched the guide. The optional emulator-closed step was not reported.
- "Desktop" is the shared app drawn offscreen with the Desktop connection settings, not the real window.
- A pass proves the apps reach the local service and render a grounded answer or an honest abstention. It makes no answer-quality or legal-coverage claim.
