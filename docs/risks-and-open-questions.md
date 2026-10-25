# Risks and Open Questions — Olive Grove Assistant

Resolved product direction lives in [the build brief](build-brief.md) and [domain model](domain-model.md). This register contains current risks and decisions that still need evidence. Do not keep resolved questions here.

## High risks

| Risk | Why it matters | Current mitigation / next action |
|---|---|---|
| Unsupported or outdated legal answer | A user could act on incorrect deadlines, amounts, or requirements | Use approved official sources, visible citations and verification dates, abstention, and targeted evaluation for critical claims. Assign a human owner for corpus review before real-user release. |
| Backend legal coverage is bounded | A working route could be mistaken for broad legal coverage | Publish the approved corpus boundary, cite only reviewed source passages, and abstain outside the three-topic Andalusia PAC 2026 slice. |
| Land context is wrong or incomplete | An answer could appear personalized while applying to the wrong land | Treat unknown as unknown; use all lands by default; ask for a land choice when answers differ; show which land context was used. Never infer eligibility from stored details. |
| Low digital confidence blocks adoption | The intended audience may abandon setup or misread a result | Keep the first journey short, explain terms in plain Spanish, allow general questions without setup, and observe low-confidence users completing key tasks. |
| Local device loss removes land records | Local-only data has no automatic recovery | Open: no user/pilot evidence establishes that loss is acceptable. Product owner must define the pilot audience and assess records' importance, replaceability, and acceptable recovery before any real-user pilot; until then do not imply backup or restore. See [decision record](specs/land_backup_decision.md#decision-and-evidence-2026-10-20). |
| Sensitive farm information reaches logs or model providers | Land notes, locations, and questions may identify a person or operation | Minimize fields and request context, avoid sending names/notes by default, redact telemetry, disclose provider processing, and review current provider terms before deployment. |
| Unreviewed or malicious content enters the knowledge corpus | The assistant may follow misleading text or cite unreliable material | Restrict ingestion to approved sources, preserve provenance, treat document text as data, and require human review for additions or changes to critical material. |
| Active PAC campaign is misconfigured or stale campaign artifacts remain | A valid answer could use evidence for the wrong campaign | Require explicit four-digit `MANIJERO_ACTIVE_CAMPAIGN`; rotate expired source records and passages together after review; configuration is not inferred from date or question. |
| Free service limits or terms change | Costs, privacy, or availability can change after launch | Keep provider adapters replaceable, measure usage, define graceful rate-limit behavior, and do not promise zero ongoing cost until verified. |

## Medium risks

| Risk | Why it matters | Current mitigation / next action |
|---|---|---|
| Several lands differ in relevant attributes | Broad operation-level answers may hide important differences | Use a land-aware clarification with names and relevant attributes; evaluate mixed dryland/irrigated and production cases. |
| User does not know an attribute | Forced form choices encourage inaccurate data | Support “I don't know” and allow editing later; the required zone and optional variety/surface/trees leave unknown attributes unknown. |
| Longer land setup for low-confidence users | The new required zone and ten-option variety list may lengthen setup without target-user evidence | Treat the field set as a product decision, keep plain-Spanish help and `No lo sé`, and validate comprehension and setup time with intended users before claiming the form is user-validated. |
| Critical sources contradict each other or show amendment history | Search can surface an obsolete rule beside a current one | Model validity/version relationships and show the relevant source/date; abstain when status cannot be established. |
| Shared UI behaves differently on desktop and mobile | Small-screen assumptions can make desktop awkward and future iOS expensive | Keep behavior and reusable UI shared where practical; adapt layout to form factor; avoid platform-only dependencies in common code. |
| Evaluation favors conventional, dryland users | Results may not cover irrigated, organic, or mixed cases | Record scenario coverage and gaps; label unvalidated coverage plainly and avoid overstating quality. |
| PAC answer-evaluation sample is narrow | A report could be mistaken for broad answer quality or legal validation | Keep metrics report-only; publish the exact case/topic boundary and omissions. The report makes no quality or legal claim and does not represent untested questions. |

## Open questions

### Blocking next phase

| Question | Why it blocks | Owner / evidence needed |
|---|---|---|
| Which exact land fields are required at first setup? Is approximate area essential to an MVP question? | Defines form length, privacy notice, storage, and chat context | **Decided 2026-10-25, superseding the 2026-10-20 deferral:** name and zone/paraje are required; variety is optional from the approved shortlist with `Otra` free text; surface and tree count are optional and never inferred; all new values stay on the device and out of the question payload. Every saved land carries its zone; nothing has shipped, so no stored land predates the field. This is a product decision with **no new target-user evidence**; validate comprehension, setup time, and omitted-field impact with intended users, including low digital confidence, before claiming the setup is validated. See [decision record](specs/land_setup_fields_decision.md#superseding-decision-2026-10-25). |
| Does the first real-user MVP need land export/backup, or is device-local storage acceptable for a limited pilot? | Data loss could remove the user's records | **Open; unresolved 2026-10-20.** Product owner: define pilot audience and gather intended-user/stakeholder evidence on record importance, replaceability, and acceptable loss/recovery; record method/date/limitations. Trigger: before proposing any real-user pilot, and on material audience/data changes. See [decision record](specs/land_backup_decision.md#decision-and-evidence-2026-10-20). |
| Who will independently review and approve the initial official sources and critical passages? | Unreviewed text cannot support a legal answer | Resolved on 2026-10-17: Diego independently reviewed and approved the 4 official sources and 4 literal passages in `knowledge/source_catalog.json` and `knowledge/passages.json`. |
| Which exact questions in the Andalusia PAC single-application slice are supported by current official sources, and what stays uncovered? | Coverage must remain explicit and narrow to avoid implying unsupported answers | Resolved on 2026-10-17: Diego approved the 3 supported procedural topics and explicit exclusions recorded in `knowledge/pac_coverage.md`. |

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
| H1 (implementation verified): Do the land list/forms and privacy notice use the chat home's centred 720dp column on wide Desktop windows and available width on narrow windows without clipping? The user reports checking all five routes at both sizes, including centring/cap, overflow, scrolling, and controls, and reports them looking good. Exact host, viewport, scale, and numeric bounds were not provided; see the user-reported evidence in the feature appendix. Further visual refinement is deferred. | Closed for the MVP layout implementation; revisit visual polish later if needed. |

### Later

| Question | Revisit when |
|---|---|
| Accounts, cloud sync, shared access, and multi-device restore | Users need continuity or collaboration across devices |
| SIGPAC references, parcel boundaries, maps, or multiple plots within a land | A validated workflow needs precise geographic records |
| Voice, document/photo interpretation, and offline assistant use | Accessibility and privacy constraints are understood and evaluated |
| iOS release details and native integrations | Android/Desktop MVP is stable; reuse shared logic and UI |
| Cooperative-facing review tools or content | A cooperative agrees to participate and boundaries are clear |
| Hosted LLM for answer generation | After corpus coverage and the first measured baseline are reviewed; check current terms, privacy, limits, cost, and verifier behavior |

Last reviewed: 2026-10-18
