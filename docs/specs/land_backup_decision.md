# Feature Spec: `land_backup_decision`

## Source metadata

- **Feature:** `land_backup_decision` — Decide the local land backup and recovery stance (`privacy`).
- **Status at planning:** `not_started`; dependencies `local_land_store` and `land_data_disclosure` are accepted.
- **Source behavior:** Record a product decision on whether device-local land storage is acceptable for a limited pilot, and define what users must be told about loss and recovery.
- **Feature-list verification:** A written decision identifies the intended pilot audience, acceptable recovery behavior, user-facing disclosure, and any release blocker.
- **Feature-list note:** This is a decision/evidence feature, not an implementation of export, backup, or recovery.
- **Size:** One bounded product decision with explicit evidence and a durable record; no application behavior change.

## Goal and boundaries

Resolve whether current device-only land storage is acceptable for a limited pilot and establish the minimum truthful user-facing stance. The decision must be grounded in evidence about the audience and consequences of device loss; absent such evidence, explicitly leave the decision unresolved and block any claim that the data is recoverable.

**In scope**

- Assess a limited pilot audience and whether losing the device-local land records is acceptable.
- Choose among: local-only storage with an explicit risk acknowledgement/mitigation, or a requirement for export/backup/recovery before pilot; if evidence is insufficient, state the open decision and evidence needed.
- Define required plain-Spanish disclosure consistent with the actual store and `land_data_disclosure` contract.
- Record rationale, evidence and residual risks in the decision record and update the risk register if resolved.

**Non-goals**

- No backup/export, restore, cloud sync, account, encryption, migration, persistence, or UI implementation.
- No change to land storage format, platform adapters, privacy notice copy, or data transmission.
- No assertion of legal compliance, provider confidentiality, user acceptance, or validated audience preference without evidence.
- No release approval; this decision only defines the backup/recovery stance and any gating condition.

## Job story

When deciding whether people can use Manijero in a limited pilot, I want a clear, evidence-based position on local land-data loss and recovery, so the pilot does not imply that records can be restored when they cannot.

## Acceptance scenarios

### Evidence supports local-only pilot

Given the intended pilot audience and consequences of losing records have been assessed with relevant evidence, when the decision is recorded, then it states why local-only storage is acceptable, the pilot boundary/mitigation, residual risk, and the exact disclosure users must receive.

### Evidence requires recovery

Given evidence shows local-only storage is not acceptable, when the decision is recorded, then export/backup/recovery is stated as a pre-pilot requirement, with the required user outcome and the decision explicitly marked as an implementation blocker; no implementation is included in this feature.

### Evidence is insufficient

Given there is no relevant user or pilot evidence, when the decision is recorded, then it remains open, lists the evidence and owner needed, and does not claim acceptance or mark the risk resolved.

### Truthful disclosure

Given the accepted land store is device-local and has no automatic recovery, when the record defines disclosure, then it requires saying plainly that data remains on the device and may be lost if the device is lost, and prohibits implying automatic backup or restore.

### Scope remains decision-only

Given this feature is complete, when the repository is reviewed, then no application code, storage behavior, network behavior, or user-facing strings have changed.

## Technical approach

1. Review the accepted `local_land_store` and `land_data_disclosure` contracts/evidence and current open risk.
2. Seek or inspect evidence relevant to the proposed limited-pilot audience and record provenance, date, method, and limitations. Do not manufacture user research; if none is available, use the insufficient-evidence outcome.
3. Create a durable decision record at `docs/specs/land_backup_decision.md` (this contract may include the outcome section once evidence is gathered) with decision status, scope, rationale, evidence, user disclosure requirements, residual risk, and follow-up owner/trigger.
4. If resolved, update the matching row in `docs/risks-and-open-questions.md`; leave it open if unresolved. No app code changes are expected.

## Expected file changes

- **Modify** `docs/specs/land_backup_decision.md`: append the dated decision/evidence outcome while preserving this contract.
- **Modify conditionally** `docs/risks-and-open-questions.md`: mark the backup/recovery question resolved only if evidence supports a decision; otherwise refine evidence-needed/owner wording.
- **Do not modify** application source, tests, `feature_list.json`, `PROGRESS.md`, storage formats/adapters, `CONSTRAINTS.md`, or privacy strings. Status/evidence changes happen only after independent validation.

## Visual design impact

None. No UI or visual behavior changes.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `docs/specs/land_backup_decision.md` | Update | This is the decision record and acceptance contract. |
| `docs/risks-and-open-questions.md` | Conditional update | Reflect a supported decision, or accurately specify remaining evidence and owner. |
| `ARCHITECTURE.md` | Not needed | No technical boundary or architecture changes. |
| `CONSTRAINTS.md` | Not needed | Existing no-overclaim and data minimization rules suffice. |
| `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `docs/domain-model.md` | Not needed | No operating rule, product scope, visual system, or domain model change. |
| `feature_list.json`, `PROGRESS.md` | Not during planning | Update only after implementation of the record and independent validation. |
| `scripts/init.sh` | Not needed | No code or automated test change. |

## Focused verification

The feature changes decision documentation only; the cheapest meaningful check is patch hygiene plus checking the decision references its evidence and makes no unsupported claim. `./scripts/init.sh --feature land_backup_decision` runs the block below unchanged.

<!-- verify:start -->
```sh
git diff --check
```
<!-- verify:end -->

## Appendix

See [`land_backup_decision.appendix.md`](land_backup_decision.appendix.md) for repository research, tasks, verification, evidence capture, and validator checklist.

## Decision and evidence — 2026-10-20

**Outcome: unresolved; local-only storage is not approved as acceptable for a limited pilot.** No target-user research, defined pilot audience, or evidence about the consequences/replaceability of losing land records is available in the repository or supplied for this decision. The existing disclosure is evidence of current behavior, not evidence that users accept the risk. No user or pilot evidence is claimed.

**Scope and rationale:** This is a decision about whether the currently device-local land records are acceptable for a limited pilot, not a release approval. Without an identified audience and relevant evidence, choosing either local-only acceptance or a recovery requirement would be unsupported. The high risk remains open.

**Required disclosure:** Before use, state plainly that lands are saved only on this device, may be lost if the device is lost, and there is no automatic backup or restore. Do not imply cloud copy, backup, or recoverability. This matches the current `land_data_disclosure` contract; it does not resolve acceptability.

**Evidence needed / owner / trigger:** The product owner must define the proposed pilot audience and ask intended users or a relevant stakeholder about the importance and replaceability of their land records and acceptable loss/recovery behavior. Record date, method, source/participant count, findings, and limitations without unnecessary personal data. Revisit this decision before any real-user pilot is proposed, and again if audience or stored data materially changes. Until then, pilot acceptability remains undecided; no recovery capability is promised.

**Residual risk:** Device loss can permanently remove locally stored land records. No mitigation beyond truthful disclosure is established by this decision.
