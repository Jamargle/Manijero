# Risks and Open Questions — Olive Grove Assistant

Current scope and terms live in [`CONTEXT.md`](../CONTEXT.md); the [domain model](domain-model.md)
describes concepts, and feature specs hold detailed decisions and evidence. This register contains
unresolved risks and evidence gaps. Remove resolved questions from the open tables and keep their
record in the owning spec or acceptance record. [`PROGRESS.md`](../PROGRESS.md) summarizes the
current implementation limits and manual checks.

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
| Summary totals read as a verified or cadastral measurement | A person, or someone reading over their shoulder, could treat `Superficie anotada` / `Olivos anotados` as an official or measured figure | The wording says `anotado`, every card carries an `x de y` denominator, nothing annotated reads `Sin datos` and never `0 ha`/`0 olivos`, and the summary is never used as eligibility information. **No user test yet**: the design assumes the wording is understood; validating it with intended users, including low digital confidence, stays outstanding. |
| Search cannot find a land the person expects | A blank or unexpected result may read as “my land is gone” instead of “this word is not in the record” | Search covers only name, zone, municipality, variety (or custom `Otra` text), water regime and production method; the hint names those fields and the results keep the stored order. Searching by surface or tree count is deliberately unsupported. **No user test yet**: expect questions about why a measure does not match. |
| Refreshed chat, lands, and help screens have incomplete device and user evidence | Host-rendered screenshots do not prove device behavior, screen-reader output, or that people with low digital confidence can complete the flows. | Complete the manual checks and owner review listed in [`PROGRESS.md`](../PROGRESS.md) and the relevant feature acceptance records before making usability claims. On compact chat the `Preguntar` action may require a short scroll; confirm that cost before release. |

## Open decisions

### Blocking next phase

| Decision | Why it matters | Owner / trigger |
|---|---|---|
| Is device-local land storage acceptable for the proposed pilot, or is recovery required first? | Device loss can permanently remove land records. | **Open.** The product owner must define the pilot audience and gather evidence about record importance, replaceability, and acceptable loss/recovery. Revisit before any real-user pilot. See [`land_backup_decision`](specs/land_backup_decision.md). |
| Who owns service operation, source refresh, rollback, and outage response? | A local prototype does not establish operational ownership for a pilot or public service. | Assign an owner and document the operating procedure before pilot or deployment. |
| What hosting and distribution targets are supported? | Cost, privacy, reliability, and platform compatibility depend on the actual deployment. | Decide and verify before public deployment or pilot distribution; iOS remains outside MVP release scope. |

### Conditional decisions

| Decision | Trigger |
|---|---|
| Question, feedback, and trace retention | Before enabling telemetry with real users. |
| Whether to use a hosted answer provider | Only after corpus coverage and the measured baseline are reviewed; before enabling it, review data handling, current terms, limits, and cost. |
| Whether to add vector/RRF retrieval or reranking | After a source-anchored retrieval evaluation shows a measurable need. |

### Later

| Question | Revisit when |
|---|---|
| Accounts, cloud sync, shared access, and multi-device restore | Users need continuity or collaboration across devices |
| SIGPAC references, parcel boundaries, maps, or multiple plots within a land | A validated workflow needs precise geographic records |
| Voice, document/photo interpretation, and offline assistant use | Accessibility and privacy constraints are understood and evaluated |
| iOS release details and native integrations | Android/Desktop MVP is stable; reuse shared logic and UI |
| Cooperative-facing review tools or content | A cooperative agrees to participate and boundaries are clear |
| Hosted LLM for answer generation | After corpus coverage and the first measured baseline are reviewed; check current terms, privacy, limits, cost, and verifier behavior |

Last reviewed: 2026-10-26
