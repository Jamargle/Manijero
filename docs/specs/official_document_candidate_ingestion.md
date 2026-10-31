# Feature Spec: `official_document_candidate_ingestion`

## Source metadata

- **Feature:** `official_document_candidate_ingestion` — Fetch and parse source candidates (`knowledge`).
- **Status at planning:** `not_started`; depends on `official_source_monitoring`, `official_source_discovery`.
- **Source behavior:** Fetch pending publication candidates recorded by source discovery (monitoring snapshots are not document candidates) only when their issuer and HTTPS host pass the allowlist; validate redirects and size/type limits, preserve original bytes and provenance hashes, and extract PDF/HTML text into quarantined candidate documents. Preserve document structure and page/section locations; OCR is a separately measured fallback. No candidate becomes answerable knowledge automatically.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

## Goal and boundaries

Turn this backend capability into a reviewable, repeatable part of the bounded PAC answer service while preserving approved-source provenance and the existing safe-answer contract.

**In scope:** Consume pending document candidates from the discovery state (the only publication-URL input; monitoring feeds retain snapshots only and contribute zero document candidates); fetch only allowlisted HTTPS URLs, validate redirects and size/type limits, preserve original bytes and provenance hashes, and extract PDF/HTML text into quarantined candidate documents. Preserve document structure and page/section locations; OCR is a separately measured fallback. No candidate becomes answerable knowledge automatically.

**Non-goals:** automatic legal interpretation, unreviewed canonical corpus changes, changes to the app wire contract unless explicitly required, and claims beyond the reviewed corpus/evaluation.

## Job story

When the answer service needs this capability, I want its behavior and evidence to be inspectable and recoverable, so that automation cannot silently weaken source grounding or operational confidence.

## Acceptance scenarios

### Normal operation

Given pending candidates in the validated discovery state (the only publication-URL input; monitoring feeds contribute zero document candidates), when the ingestion command runs, then supported documents are fetched into quarantine with registry/source provenance, bounded resource use, and an observable per-candidate status.

### Invalid, unavailable, or ambiguous input

Given a malformed artifact, unavailable upstream, ambiguous legal change, or failed verification, when the run processes it, then it fails closed, preserves existing approved behavior, and records an actionable failure without exposing personal data.

### Reproducibility and review

Given the same pinned code, configuration, and approved inputs, when the work is repeated, then outputs are reproducible or differences are explicitly reported; any user-answerable knowledge change has a recorded human approval.

## Technical approach

Consume the pending candidates recorded by discovery (monitoring responses are stored separately and are not document candidates), fetch only allowlisted HTTPS sources, validate redirects and size/type limits, preserve original bytes and provenance hashes, and extract PDF/HTML text into quarantined candidate documents. Preserve document structure and page/section locations; OCR is a separately measured fallback. Reject candidates without a known approved issuer/host and never make candidate content answerable automatically. Inspect the current backend and knowledge schemas before implementation; preserve existing API and code-owned answer properties. Add focused fixtures for boundary and failure cases. Pin mutable dependencies and model/artifact revisions. Make resource, timing, freshness, and extraction limits visible.

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

See [`official_document_candidate_ingestion.appendix.md`](../archive/specs/official_document_candidate_ingestion.appendix.md).
