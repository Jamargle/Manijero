# Backend Technical Discovery — pre-implementation snapshot (2026-10-17)

> **Historical discovery record.** The baseline and remaining-work tables below describe the
> repository on 2026-10-17, before the local answer route and reviewed corpus were completed. For the
> current service and knowledge boundary, use [`backend/README.md`](../../backend/README.md),
> [`knowledge/README.md`](../../knowledge/README.md), the relevant feature specs, and
> [`PROGRESS.md`](../../PROGRESS.md).

This note scopes the backend work needed to complete a local end-to-end answer service before public deployment. It complements the product-level [build brief](build-brief.md); it is discovery, not an implementation plan.

## Baseline observed on 2026-10-17

- `backend/app/main.py` exposes only `GET /health`, which reports process liveness.
- `contracts/openapi.yaml` already defines `POST /ask` and the request/response contract, including `answered`, `abstained`, and `needs_land_clarification` states.
- Source-catalog validation, lexical BM25 retrieval, date validity checks, grounded extractive generation, abstention, and land clarification exist as deterministic offline modules. They are not assembled behind an HTTP route.
- Retrieval has no vector/RRF path, its synthetic metrics are not a calibrated answer threshold, and campaign filtering is not implemented. The planned policy is documented in [`backend_campaign_validity`](../specs/backend_campaign_validity.md). Land clarification is also offline-only.
- `knowledge/source_catalog.json` is intentionally empty; there is no canonical reviewed passage set. The evaluators currently use synthetic fixtures and report-only metrics.
- No model provider, deployed backend, production trace store, or feedback route is configured. The Kotlin client currently has no live `/ask` service to call.

## Proposed local workflow at discovery

1. Validate the contract-shaped question and minimal land context.
2. Retrieve only approved, current passages from the reviewed corpus, applying source eligibility, the UTC as-of/validity rules, and an explicitly configured active campaign. Do not infer campaign from date or add it to the request contract; see [`backend_campaign_validity`](../specs/backend_campaign_validity.md).
3. Use the existing land applicability and clarification policy; preserve unknown attributes and never infer eligibility.
4. Produce a code-verified, source-backed answer or a pinned safe abstention, then assemble the contract-shaped response.
5. Exercise all response states through HTTP contract tests and a source-anchored evaluation set. Keep coverage metrics report-only until a real baseline is reviewed.

The initial corpus direction is a narrow Andalusia PAC single-application slice. Current official sources determine which concrete questions can be covered. Source discovery, downloading, passage review, and critical-fact verification remain human-curated. Historical source lists and verification marks in `docs/archive/MasterPlanV3.md` are planning evidence, not current corpus approval.

## Candidate 2026 corpus coverage at discovery

Official material reviewed on 2026-10-17 supports a small candidate slice about where to submit the Andalusian 2026 Solicitud Única, the 2026 filing deadline, and the separate deadline for modifying a submitted application. These are candidate topics for independent review; no canonical source or passage has been approved by this research note.

| Candidate question | Primary source finding | Coverage boundary |
|---|---|---|
| Where is the 2026 application presented? | The Andalusian campaign resolution directs submission through the SGA tool available via recognized entities. The national rule also describes an exceptional non-electronic route when the competent authority has not established that an individual has access to the required electronic means. | Explain the ordinary route and its narrow exception without promising paper filing or giving portal troubleshooting steps. |
| What was the 2026 filing deadline in Andalusia? | The January campaign resolution initially states 30 April. Article 14 of Andalusia's Decreto-ley 1/2026 later extends filing through 15 May 2026. | The later binding amendment controls. Do not repeat the superseded 30 April date as the final deadline. |
| Until when could an Andalusian applicant modify or add interventions/parcels in 2026? | The national Article 112 describes the general modification rule; Real Decreto 537/2026 adds a 2026 Andalusia-specific end date of 15 June. | Keep this distinct from filing and from post-notification adaptation. Do not generalize it to future campaigns. |

Primary-source candidates and the source chronology, including the published request for a further extension that is not itself a binding deadline amendment, are recorded in [`backend_pac_corpus.appendix.md`](specs/backend_pac_corpus.appendix.md). The 2026 official campaign page points to forms and the recognized-entity list. Exact passages, source metadata, and the coverage statement must be independently reviewed before they enter `knowledge/` as approved evidence. Questions about aid eligibility, amounts, late-filing reductions, individual cases, and detailed monitoring adaptations remain outside this first slice.

## Work outstanding at discovery

| Master Plan area | Current repository state | Local MVP direction |
|---|---|---|
| B1/B2/B9/B13 — retrieval, threshold, campaign validity, land applicability | BM25, catalog validity checks, abstention, and land clarification exist offline; no hybrid search, corpus-calibrated threshold, campaign policy, or HTTP orchestration | Wire existing rules first, define date/campaign behavior for the narrow corpus, then measure retrieval before adding vector search or a score threshold. |
| B3-B8 — generator, input guards, provider, rewriting, validation, extractive critical answers | Extractive generation and a strict code verifier exist; no hosted provider, provider prompt, or question rewriting is configured | Use extractive output in the first route. Enforce request-contract validation and existing answer invariants; do not rewrite questions in this slice. Revisit provider-specific prompt/injection controls only if a provider is selected later. |
| B10/B11 — API and traces | `/health` is the only route; no `/ask`, `/feedback`, or query traces | Add local `/ask`; defer feedback and trace storage until their data and retention rules are decided. |
| A1-A5/C1-C3 — reviewed corpus and evaluation prerequisites | Catalog and canonical passages are empty; evaluation fixtures are synthetic | Manually review a small source/passages set and create source-anchored cases before claiming coverage. Keep reports non-gating until a baseline is reviewed. |
| B12/E1-E6 — reranking and deployment operations | No reranker or deployment stack | Reranker remains optional and evidence-led; defer Docker/public hosting, monitoring, backups, and CI/CD to deployment scope. |

## Constraints and boundaries

- `contracts/openapi.yaml` remains the wire source of truth. Do not add land fields or response properties without a contract change and matching client review.
- The request contains the original question and only the minimal land attributes already allowed by the contract. Do not send land names, notes, area, or timestamps. Do not log raw questions or land context by default.
- No answer claim, citation, source card, or critical number may bypass the accepted code verifier and response assembler. Model output, if later enabled, is an untrusted draft and a verifier failure discards it whole.
- The user selected a local service first and public deployment later. This slice does not require hosting, deployment, authentication, public rate limiting, monitoring, backups, or Android/Desktop production wiring; settle those before a public pilot.
- Knowledge scouts, automatic ingestion, scheduled orchestration, nightly evaluation, and human-review automation are later work. Corpus updates stay reviewable and human-approved.

## Decisions and open points

| Topic | Discovery position |
|---|---|
| HTTP API | Implement local `POST /ask` against the accepted contract; keep `/health` as liveness. `/feedback` is deferred. |
| Corpus | Manually curated source catalog and passages for the narrow PAC single-application slice. Candidate 2026 coverage is mapped to current official sources; independent review is still required before canonical approval. |
| Generation | Use the current extractive generator for the first route; do not call a hosted LLM. Revisit provider selection after corpus coverage and the first measured baseline. |
| Retrieval | Use current BM25 as the baseline. Whether to add vector retrieval/RRF or reranking depends on reviewed evaluation evidence. |
| Campaign validity | Keep the existing request contract. Use an explicit active-campaign setting independent of the UTC validity date; reject cross-year requests conservatively and rotate expired sources out of the active corpus. See [`backend_campaign_validity`](../specs/backend_campaign_validity.md). |
| Evaluation | Add source-anchored questions and manually reviewed critical cases. Keep metrics report-only until the first measured baseline is reviewed; synthetic fixture results are not legal-coverage evidence. |
| Source ownership | A reviewer other than the author is required for adding approved sources and critical excerpts. No named reviewer is recorded yet. |
| Feature tracking | Keep one root `feature_list.json` as the status/dependency source. Its `area` field already groups work, and current selector tooling reads one index; a separate backend list would split cross-feature dependencies and require extra harness support. |
