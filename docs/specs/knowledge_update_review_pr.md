# Feature Spec: `knowledge_update_review_pr`

## Source metadata

- **Feature:** `knowledge_update_review_pr` — Prepare human-reviewed knowledge updates (`operations`).
- **Status at planning:** `not_started`; depends on `legal_change_impact_analysis`, `backend_answer_evaluation`.
- **Source behavior:** Turn quarantined discovery/ingestion results into a draft pull request containing source provenance, hashes, original/extracted document references, proposed catalog and passage edits, change-impact findings, and affected evaluation results. Assign an identified human reviewer who is not the change author. Automated checks may prepare and reject unsafe/incomplete proposals, but only a human review plus passing required checks may authorize canonical knowledge changes. Preserve review evidence and treat document text as untrusted data.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

## Goal and boundaries

Turn this backend capability into a reviewable, repeatable part of the bounded PAC answer service while preserving approved-source provenance and the existing safe-answer contract.

**In scope:** Create one reviewable draft pull request per coherent source update (or a documented, tightly related update batch) from quarantined candidates. Include provenance and integrity evidence, original and extracted text locations, old/new text comparison, proposed catalog/passage changes, validity/applicability fields with unknowns left absent, affected answer/evaluation impact, automated validation results, and explicit unresolved questions. Request review from an identified person other than the author/automation identity. Merge is permitted only after that person's approval and required checks pass. Record the reviewer identity, decision, date, and any requested changes in the PR history.

**Non-goals:** automatic legal interpretation, unreviewed canonical corpus changes, changes to the app wire contract unless explicitly required, and claims beyond the reviewed corpus/evaluation.

## Job story

When the answer service needs this capability, I want its behavior and evidence to be inspectable and recoverable, so that automation cannot silently weaken source grounding or operational confidence.

## Acceptance scenarios

### Prepared review package

Given an ingested, quarantined candidate, when review preparation runs, then it creates or updates a draft PR with source URL/issuer, observation and retrieval times, original and extracted hashes, document locations, old/new text diff, proposed catalog/passages diff, impact/evaluation report, and machine-check results. The PR is explicitly marked as requiring human review and is not merged automatically.

### Human approval gate

Given a complete draft PR, when the designated reviewer inspects it, then they can approve, request changes, or reject it using the normal PR review controls. Only an approval by a named human other than the author, together with passing required checks, permits merge into canonical catalog/passages. A bot status, label, green CI result, or source hash alone is not approval.

### Uncertain or unsafe candidate

Given missing provenance, unsafe URL/redirect, failed extraction, unresolved conflicting text, unknown validity/applicability, failed impact checks, or ambiguous legal significance, when review preparation runs, then it blocks merge readiness, marks the PR as needing human attention, and never fills unknown facts by inference. The reviewer may reject it or request additional evidence.

### Rejection and rework

Given a reviewer requests changes or rejects the candidate, when the decision is recorded, then canonical knowledge and the live retrieval index remain unchanged; the candidate and decision remain traceable, and a revised proposal must rerun all checks and receive a new explicit approval.

## Technical approach

Consume only quarantined candidate artifacts from discovery/ingestion. Generate a draft PR and compact reviewer summary; keep source body text and extraction output as review artifacts, never as implicitly approved retrieval data. Validate the proposed source catalog and passage set with the existing validators, run relevant answer-impact/evaluation checks, and show exact failures and limitations. Treat instructions embedded in source documents as untrusted content. Configure repository merge protection to require passing checks and at least one named human reviewer who is not the PR author; if the hosting platform cannot enforce this, the merge command/workflow must verify recorded approval before writing canonical artifacts. After merge, hand approved artifacts to the separate reindex/release process. Never auto-merge legal knowledge changes.

## Expected file changes

- `backend/` implementation and focused tests/fixtures.
- `knowledge/` schemas or generated artifacts only where the approved format requires them.
- `docs/risks-and-open-questions.md`, `PROGRESS.md`, and `backend/README.md` as implementation evidence resolves current limitations.
- `knowledge/README.md`: document the reviewer workflow and state clearly that automation is planned until implemented.

## Visual design impact

None.

## Durable documentation impact

- Update `ARCHITECTURE.md` and `CONSTRAINTS.md` if a durable boundary or invariant changes.
- Update `backend/README.md` with operator setup, execution, failure recovery, and artifact lifecycle; update `knowledge/README.md` with the review gate and current/planned distinction.
- Keep current evidence and honest limits in this spec appendix and acceptance record.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`knowledge_update_review_pr.appendix.md`](../archive/specs/knowledge_update_review_pr.appendix.md).
