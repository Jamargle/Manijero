# Feature Spec: `knowledge_update_scheduler`

## Source metadata

- **Feature:** `knowledge_update_scheduler` — Run and monitor scheduled source scans (`operations`).
- **Status at planning:** `not_started`; depends on `official_source_monitoring`, `official_source_discovery`, `hosted_pilot_operations`.
- **Source behavior:** Run configured-source scans and approved-registry discovery on a documented cadence with retries, backoff, idempotency, run ledger, failure notification, and manual dispatch. Scheduled execution is best-effort: surface missed/failed runs and never claim coverage freshness from a cron schedule alone. Assess whether the selected owned server or repository automation is reliable and supported.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

The initial schedule should support daily/weekly configuration for priority sources and configured discovery registries, but its exact cadence is an operations decision recorded with expected publication frequency and host constraints. GitHub Actions schedules are best-effort and may be delayed or dropped, so monitor actual run history, add manual dispatch, and report stale scans rather than claiming a guaranteed refresh SLA. Source discovery is limited to verified registries for already approved issuers; a registry or host addition still needs human approval.

## Goal and boundaries

Turn this backend capability into a reviewable, repeatable part of the bounded PAC answer service while preserving approved-source provenance and the existing safe-answer contract.

**In scope:** Run configured source monitoring and official-registry discovery on a documented cadence with retries, backoff, idempotency, run ledger, failure notification, and manual dispatch. Surface per-registry coverage, missed/failed runs, and stale scans. Assess whether the selected owned server or repository automation is reliable and supported.

**Non-goals:** automatic legal interpretation, unreviewed canonical corpus changes, changes to the app wire contract unless explicitly required, and claims beyond the reviewed corpus/evaluation.

## Job story

When the answer service needs this capability, I want its behavior and evidence to be inspectable and recoverable, so that automation cannot silently weaken source grounding or operational confidence.

## Acceptance scenarios

### Normal operation

Given a supported and configured run, when the feature executes, then it produces the documented result with source provenance, bounded resource use, and an observable status.

### Invalid, unavailable, or ambiguous input

Given a malformed artifact, unavailable upstream, ambiguous legal change, or failed verification, when the run processes it, then it fails closed, preserves existing approved behavior, and records an actionable failure without exposing personal data.

### Reproducibility and review

Given the same pinned code, configuration, and approved inputs, when the work is repeated, then outputs are reproducible or differences are explicitly reported; any user-answerable knowledge change has a recorded human approval.

## Technical approach

Run configured-source monitoring and official-registry discovery on a documented cadence with retries, backoff, idempotency, run ledger, failure notification, and manual dispatch. Scheduled execution is best-effort: surface per-registry coverage, missed/failed runs, and stale scans; never claim coverage freshness from a cron schedule alone. Assess whether the selected owned server or repository automation is reliable and supported. Inspect the current backend and knowledge schemas before implementation; preserve existing API and code-owned answer properties. Add focused fixtures for boundary and failure cases. Pin mutable dependencies and model/artifact revisions. Make resource, timing, freshness, and evaluation evidence visible. Discovery candidates remain quarantined and cannot change canonical knowledge without identified human approval.

## Expected file changes

- `backend/` implementation and focused tests/fixtures.
- `knowledge/` schemas or generated artifacts only where the approved format requires them.
- `docs/risks-and-open-questions.md`, `PROGRESS.md`, and `backend/README.md` as implementation evidence resolves current limitations.

## Visual design impact

None.

## Durable documentation impact

- Update `ARCHITECTURE.md` and `CONSTRAINTS.md` if a durable boundary or invariant changes.
- Update `backend/README.md` with operator setup, execution, failure recovery, and artifact lifecycle.
- Keep current evidence and honest limits in this spec appendix and acceptance record.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`knowledge_update_scheduler.appendix.md`](knowledge_update_scheduler.appendix.md).
