# Risks and Open Questions — Olive Grove Assistant

Resolved product direction lives in [the build brief](build-brief.md) and [domain model](domain-model.md). This register contains current risks and decisions that still need evidence. Do not keep resolved questions here.

## High risks

| Risk | Why it matters | Current mitigation / next action |
|---|---|---|
| Unsupported or outdated legal answer | A user could act on incorrect deadlines, amounts, or requirements | Use approved official sources, visible citations and verification dates, abstention, and targeted evaluation for critical claims. Assign a human owner for corpus review before real-user release. |
| Backend has no reviewed answer corpus | A working route over synthetic fixtures could look complete while having no legal coverage | Keep the corpus explicitly empty until current official sources and critical passages are reviewed; define coverage only from accepted material and source-anchored questions. |
| Land context is wrong or incomplete | An answer could appear personalized while applying to the wrong land | Treat unknown as unknown; use all lands by default; ask for a land choice when answers differ; show which land context was used. Never infer eligibility from stored details. |
| Low digital confidence blocks adoption | The intended audience may abandon setup or misread a result | Keep the first journey short, explain terms in plain Spanish, allow general questions without setup, and observe low-confidence users completing key tasks. |
| Local device loss removes land records | Local-only data has no automatic recovery | Before release, choose and clearly explain an export/backup or recovery stance; do not imply cloud backup exists. |
| Sensitive farm information reaches logs or model providers | Land notes, locations, and questions may identify a person or operation | Minimize fields and request context, avoid sending names/notes by default, redact telemetry, disclose provider processing, and review current provider terms before deployment. |
| Unreviewed or malicious content enters the knowledge corpus | The assistant may follow misleading text or cite unreliable material | Restrict ingestion to approved sources, preserve provenance, treat document text as data, and require human review for additions or changes to critical material. |
| Free service limits or terms change | Costs, privacy, or availability can change after launch | Keep provider adapters replaceable, measure usage, define graceful rate-limit behavior, and do not promise zero ongoing cost until verified. |

## Medium risks

| Risk | Why it matters | Current mitigation / next action |
|---|---|---|
| Several lands differ in relevant attributes | Broad operation-level answers may hide important differences | Use a land-aware clarification with names and relevant attributes; evaluate mixed dryland/irrigated and production cases. |
| User does not know an attribute | Forced form choices encourage inaccurate data | Support “I don't know” and allow editing later; do not force area or production details without a use case. |
| Critical sources contradict each other or show amendment history | Search can surface an obsolete rule beside a current one | Model validity/version relationships and show the relevant source/date; abstain when status cannot be established. |
| Shared UI behaves differently on desktop and mobile | Small-screen assumptions can make desktop awkward and future iOS expensive | Keep behavior and reusable UI shared where practical; adapt layout to form factor; avoid platform-only dependencies in common code. |
| Evaluation favors conventional, dryland users | Results may not cover irrigated, organic, or mixed cases | Record scenario coverage and gaps; label unvalidated coverage plainly and avoid overstating quality. |

## Open questions

### Blocking next phase

| Question | Why it blocks | Owner / evidence needed |
|---|---|---|
| Which exact land fields are required at first setup? Is approximate area essential to an MVP question? | Defines form length, privacy notice, storage, and chat context | Review real user questions; test a minimal land record with target users |
| Does the first real-user MVP need land export/backup, or is device-local storage acceptable for a limited pilot? | Data loss could remove the user's records | Decide release audience and acceptable recovery behavior |
| Who will independently review and approve the initial official sources and critical passages? | No canonical source or passage is approved today; unreviewed text cannot support a legal answer | Name a reviewer other than the author and agree a source-review procedure before adding canonical corpus data; candidate source map is in `docs/specs/backend_pac_corpus.appendix.md` |
| Which exact questions in the Andalusia PAC single-application slice are supported by current official sources, and what stays uncovered? | Candidate coverage has been mapped to current official materials, but exact passages and the user-facing coverage boundary are not independently approved | Reviewer confirms or narrows the three candidate topics in `knowledge/pac_coverage.md` before canonical corpus data is accepted |

### Implementation-time

| Question | Decision timing |
|---|---|
| Local persistence and migration format for lands | Before implementing land storage |
| Exact rule for when all-land answers are safe versus when to ask for a specific land | Before connecting land context to retrieval/generation |
| Whether selected land context is sent as attributes, derived filters, or both | At API contract design |
| Evaluation size, metrics, and pass thresholds | After a measured baseline; include land-aware, ambiguous, and abstention cases |
| Keep BM25 or add vector/RRF retrieval | After source-anchored retrieval evaluation; add complexity only for measured improvement |
| If a hosted provider is reconsidered, what data may it process and under which current terms? | Before enabling external model requests; document the data flow, privacy, limits, and cost |
| Who owns service operation, source refresh, rollback, and outage response? | Before public deployment or a real-user pilot |
| Exact hosting approach | Before deployment; verify cost, terms, limits, privacy, and operational fit |
| Retention of questions, feedback, and traces | Before enabling telemetry with real users |
| Desktop packaging and supported operating systems | Before pilot distribution |
| Whether the lands list/forms and the privacy notice should share the chat home's 720dp capped/centred column on a wide Desktop window (they currently render full-width — pre-existing, recorded as finding H1 in `docs/validations/desktop_mvp_build.md`) | If a wide-window land layout is wanted; a separate feature, not part of `desktop_mvp_build` |

### Later

| Question | Revisit when |
|---|---|
| Accounts, cloud sync, shared access, and multi-device restore | Users need continuity or collaboration across devices |
| SIGPAC references, parcel boundaries, maps, or multiple plots within a land | A validated workflow needs precise geographic records |
| Voice, document/photo interpretation, and offline assistant use | Accessibility and privacy constraints are understood and evaluated |
| iOS release details and native integrations | Android/Desktop MVP is stable; reuse shared logic and UI |
| Cooperative-facing review tools or content | A cooperative agrees to participate and boundaries are clear |
| Hosted LLM for answer generation | After corpus coverage and the first measured baseline are reviewed; check current terms, privacy, limits, cost, and verifier behavior |

Last reviewed: 2026-10-17
