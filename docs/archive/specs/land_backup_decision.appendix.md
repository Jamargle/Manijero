# Appendix — `land_backup_decision`

Planning and verification record for [`land_backup_decision.md`](../../specs/land_backup_decision.md). The decision's evidence and any implementation findings belong below; `docs/validations/land_backup_decision.md` is the acceptance record.

## Repository research

Inspected repository files:

- `PROGRESS.md`: accepted set includes both prerequisites; current state says lands are device-local and lists no backup capability.
- `feature_list.json`: feature is `not_started`, depends on `local_land_store` and `land_data_disclosure`, and specifies a decision about local backup/recovery.
- `docs/specs/local_land_store.md`: `land-store-v1`; Android SharedPreferences and Desktop file persistence; no account or backup; malformed records are skipped but this is corruption tolerance, not recovery.
- `docs/specs/land_data_disclosure.md` and `.appendix.md`: notice already says no automatic backup and device loss may lose lands; explicitly does not resolve whether local-only is acceptable for a pilot.
- `docs/risks-and-open-questions.md`: high risk “Local device loss removes land records”; open question asks whether export/backup is required for a limited pilot, with audience and acceptable recovery behavior undecided.
- `scripts/init.sh`: feature mode runs commands in contract markers; no documentation-specific validator exists. No persistent UI/E2E command applies because behavior is unchanged.

No target-user research, pilot definition, or evidence of acceptable data-loss consequences was discovered in these inspected files. Do not infer acceptance from the existing disclosure or from an implementer's preference. The specific decision remains dependent on evidence gathering.

**Sizing:** correctly bounded as one product decision and risk-record update. It does not introduce a data model, user flow, or implementation.

## Implementation plan and tasks

1. Confirm the proposed limited-pilot audience and the value/replaceability of the stored land records with a relevant stakeholder or intended users.
2. Capture the evidence with date, method, participants or source, findings, and limitations. Do not collect unnecessary personal data; anonymize summaries.
3. Choose one explicit outcome: local-only acceptable within stated pilot limits; backup/recovery required before pilot; or unresolved pending evidence.
4. Append a dated “Decision and evidence” section to the contract, including scope, rationale, disclosure requirements, residual risk, owner, and review trigger. For an unresolved outcome, state exactly what evidence is missing and who must obtain it.
5. Update the risk register only if the outcome changes its current state. Keep the risk open when evidence is insufficient.
6. Run the focused documentation check, inspect `git diff --check`, and verify no application files or status board were changed.
7. Independent validator checks the record against the checklist; feature status/evidence is updated only after acceptance by the responsible parent workflow.

## Verification plan

Run from repository root:

```sh
./scripts/init.sh --feature land_backup_decision
git diff --check
```

Manual document review is the substantive check. Confirm the recorded outcome is traceable to evidence, bounded to a stated pilot, and does not imply restore/backup that does not exist. No code tests or E2E coverage are warranted: the planned feature changes documentation only. If implementation adds UI or storage behavior, stop and re-scope rather than treating this spec as authority for that change.

## Evidence to capture

- Source and date of decision evidence, collection method, relevant findings, and limitations; if no evidence exists, the explicit unresolved state and evidence/owner needed.
- Outcome and rationale; pilot audience/boundary; required disclosure and residual risk; owner and review trigger.
- Any corresponding risk-register edit and why it is accurate.
- `./scripts/init.sh --feature land_backup_decision` and `git diff --check` results.
- Diff scope confirming no application code, tests, privacy copy, status board, or storage behavior changed.

## Feature evidence

<!-- Implementer: append concise factual evidence here. Do not claim user research or acceptance without its source. -->

- 2026-10-20: Recorded explicit unresolved outcome. Repository review found no target-user research, pilot definition, or evidence of acceptable data-loss consequences (research findings above); no user/pilot evidence was supplied. Decision states required truthful disclosure, residual loss risk, product-owner evidence task, and pre-pilot/material-change review trigger. Kept the high risk and blocking question open, refining owner/evidence/trigger wording. No application code, tests, strings, `feature_list.json`, or `PROGRESS.md` changed.
- Verification: `./scripts/init.sh --feature land_backup_decision` passed; the focused block ran `git diff --check`. A separate `git diff --check` also passed. `git status --short` showed only the risk register modified and the two pre-existing untracked feature documents; no app/test/privacy-string/status-board files changed. No user-flow/E2E check applies because this is decision documentation only.

## Validator checklist

- [ ] Decision is explicit: local-only acceptable with bounds, recovery required before pilot, or unresolved; no ambiguous implied approval.
- [ ] Evidence has provenance/date/method and limitations; no user acceptance is invented or inferred from the existing disclosure.
- [ ] Decision names its pilot scope, rationale, residual risk, owner, and review trigger; unresolved outcome names evidence needed.
- [ ] User-facing disclosure requirement is consistent with `land_data_disclosure`: lands are device-local, may be lost with device loss, and no automatic backup/restore is promised.
- [ ] Risk register is updated only when justified; unresolved question remains open otherwise.
- [ ] No application code, tests, privacy strings, storage behavior, `feature_list.json`, or `PROGRESS.md` changed as part of planning/decision implementation.
- [ ] Focused command and `git diff --check` pass; no E2E/UI result is claimed.
- [ ] Any independent acceptance record accurately points to the decision and evidence; feature status is not advanced before validation.
