# Feature Spec: `gemini_generation_provider`

## Source metadata

- **Feature:** `gemini_generation_provider` — Integrate gated Gemini answer generation (`backend`).
- **Status at planning:** `not_started`; depends on `grounded_answer_generation`, `backend_answer_evaluation`, `hosting_provider_review`, `pilot_privacy_readiness`.
- **Source behavior:** Implement a replaceable Gemini client and structured draft output, but keep outbound calls disabled until the exact current model, official terms, data flows, cost/rate limits, and qualified privacy/legal review are recorded and approved. Never send land names/notes or stable identifiers. Every draft passes the existing whole-draft verifier; citations, sources, notices, and abstentions remain code-owned. Retain extractive generation as a safe fallback.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by successful automation.

## Goal and boundaries

Turn this backend capability into a reviewable, repeatable part of the bounded PAC answer service while preserving approved-source provenance and the existing safe-answer contract.

**In scope:** Implement a replaceable Gemini client and structured draft output, but keep outbound calls disabled until the exact current model, official terms, data flows, cost/rate limits, and qualified privacy/legal review are recorded and approved. Never send land names/notes or stable identifiers. Every draft passes the existing whole-draft verifier; citations, sources, notices, and abstentions remain code-owned. Retain extractive generation as a safe fallback.

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

Implement a replaceable Gemini client and structured draft output, but keep outbound calls disabled until the exact current model, official terms, data flows, cost/rate limits, and qualified privacy/legal review are recorded and approved. Never send land names/notes or stable identifiers. Every draft passes the existing whole-draft verifier; citations, sources, notices, and abstentions remain code-owned. Retain extractive generation as a safe fallback. Inspect the current backend and knowledge schemas before implementation; preserve existing API and code-owned answer properties. Add focused fixtures for boundary and failure cases. Pin mutable dependencies and model/artifact revisions. Make resource, timing, freshness, and evaluation evidence visible.

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

See [`gemini_generation_provider.appendix.md`](gemini_generation_provider.appendix.md).
