# `official_document_candidate_ingestion` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

`official_source_discovery` is the upstream producer for newly listed publication candidates. This feature consumes those records and candidates from configured monitoring feeds; it does not perform web discovery itself. The canonical source catalog remains the admission gate.

## Implementation plan

1. Inspect monitor/discovery candidate formats, the catalog validator, and focused command before changing code.
2. Fetch only candidate URLs with a verified approved issuer and exact approved HTTPS host; fail closed on missing provenance.
3. Preserve original bytes/digests and source-registry provenance, then parse supported document formats into quarantined output.
4. Add representative and adversarial fixtures for unsafe destinations, malformed/oversized payloads, duplicate candidates, unavailable origins, and parse failures.
5. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

Not implemented. No implementation or verification evidence exists yet.
