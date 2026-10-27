# `knowledge_update_scheduler` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

The scheduled workflow consumes configured monitoring sources plus `official_source_discovery` registry results. It does not expand the approved issuer/host list and must expose registry coverage gaps.

## Implementation plan

1. Compare owned-server scheduling and repository automation against support, secret handling, missed-run observability, and cost; select one supported runner.
2. Add daily/weekly configurable scheduling and manual dispatch for source monitoring and `official_source_discovery`.
3. Implement retries with bounded backoff, idempotency, an append-only run ledger, stale-scan detection, and owner notification without logging content or secrets.
4. Add deterministic tests for missed/failed runs and repeated dispatch; document how to recover and how to disable the schedule.
5. Capture operational evidence and limits; scans may only create or update quarantined candidates.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Scheduled jobs invoke discovery only for configured verified registries and make unsupported registries visibly unchecked.
- Missed, failed, and stale runs are observable; the schedule does not claim a freshness SLA.
- Evidence supports only the exact scope claimed.

## Feature evidence

Not implemented. No implementation or verification evidence exists yet.
