# `knowledge_update_review_pr` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

## Implementation plan

1. Inspect the current owning modules, schemas, and focused command before changing code.
2. Implement the capability behind a narrow interface with explicit configuration and fail-closed behavior.
3. Add representative and adversarial fixtures, including malformed, stale, duplicate, unavailable, and ambiguous cases as applicable.
4. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

Not implemented. No implementation or verification evidence exists yet.
