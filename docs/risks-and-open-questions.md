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
| Local device loss removes land records | Land data is deliberately local and no service-side copy exists | **Decision:** remain local-only; require same-device automatic copies and a portable, user-managed backup file before pilot. Recoverable removal and bounded same-device automatic copies are implemented; the portable backup file is still planned. Device loss, uninstall, or losing the app data area can still permanently remove records because every copy lives on the same device. Never describe the on-device copies as protection from device loss. See [decision record](specs/land_backup_decision.md) and [`local_land_auto_backup`](specs/local_land_auto_backup.md). |
| Sensitive farm information reaches logs or infrastructure providers | Questions and minimal land attributes transit the hosted API and tunnel; user text may identify a person or operation | Keep land names/notes out of requests and logs; Gemini is planned but gated off until current model terms and data flows receive qualified review; no provider call is permitted before that gate. Question/answer retention is planned default-off, per-question opt-in, redacted, without land context or stable IDs, and limited to 30 days. Qualified privacy/legal review and current host/tunnel terms are required before pilot. |
| Unreviewed or malicious content enters the knowledge corpus | The assistant may follow misleading text or cite unreliable material | Restrict ingestion to approved sources, preserve provenance, treat document text as data, and require human review for additions or changes to critical material. |
| No hosting-enforced review gate for local update packages | A local draft package is not a pull request, so the hosting provider cannot enforce branch protection; anyone with filesystem access can still edit canonical files directly | The controlled merge verifies approval from a requested reviewer, matching package/checks/case digests, and passing checks before writing, and refuses known automation identities. Those identities and decisions are not authenticated, so this remains a procedural boundary. Add Git/hosting integration and provider-enforced protection before relying on it for unattended operations. |
| Active PAC campaign is misconfigured or stale campaign artifacts remain | A valid answer could use evidence for the wrong campaign | Require explicit four-digit `MANIJERO_ACTIVE_CAMPAIGN`; rotate expired source records and passages together after review; configuration is not inferred from date or question. |
| Free service limits or terms change | Costs, privacy, or availability can change after launch | Keep provider adapters replaceable, measure usage, define graceful rate-limit behavior, and do not promise zero ongoing cost until verified. |

| Official source updates are missed or misclassified | A scheduled scan can fail, an official page can change format, or an amendment can be ambiguous | Implement allowlisted scans with run history/retries and stale-run visibility; quarantine candidates, run the read-only change-impact analysis, and require human approval before canonical knowledge changes. The analysis only reports explicit wording, so a missed or ambiguous change remains possible and detection quality is unmeasured.
| Local embedding/index capacity is unknown | bge-m3 and Chroma may exceed owned-server storage or memory limits | Measure the actual deployment host and compare retrieval against BM25 before retaining the added components; keep a rollback path.

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
| Known PAC answer-evaluation misses remain | The six-case sample contains citation and critical-fact misses | Resolve or keep each mismatch visible in the planned scope expansion. Review is author-only; report exact cases and limitations and make no independent legal validation or broad quality claim. |
| Summary totals read as a verified or cadastral measurement | A person, or someone reading over their shoulder, could treat `Superficie anotada` / `Olivos anotados` as an official or measured figure | The wording says `anotado`, every card carries an `x de y` denominator, nothing annotated reads `Sin datos` and never `0 ha`/`0 olivos`, and the summary is never used as eligibility information. **No user test yet**: the design assumes the wording is understood; validating it with intended users, including low digital confidence, stays outstanding. |
| Search cannot find a land the person expects | A blank or unexpected result may read as “my land is gone” instead of “this word is not in the record” | Search covers only name, zone, municipality, variety (or custom `Otra` text), water regime and production method; the hint names those fields and the results keep the stored order. Searching by surface or tree count is deliberately unsupported. **No user test yet**: expect questions about why a measure does not match. |
| Refreshed chat, lands, and help screens have incomplete device and user evidence | Host-rendered screenshots do not prove device behavior, screen-reader output, or that people with low digital confidence can complete the flows. | Complete the manual checks and owner review listed in [`PROGRESS.md`](../PROGRESS.md) and the relevant feature acceptance records before making usability claims. On compact chat the `Preguntar` action may require a short scroll; confirm that cost before release. |

## Open decisions

### Blocking next phase

| Decision | Why it matters | Owner / trigger |
|---|---|---|
| Are land records recoverable enough for a private pilot? | Recoverable removal and bounded same-device automatic copies are implemented; a lost device, a deleted app, or a cleared data directory still removes every copy, and there is still no user-controlled backup file. | **Decision recorded:** stay local-only; require recoverable removal, same-device automatic copies, and portable plaintext backup/restore. Recoverable removal and the automatic copies are accepted; the portable backup/restore feature remains blocking. No real-user pilot until all three are accepted. See `recover_removed_lands`, `local_land_auto_backup`, and `portable_land_backup`. |
| Can the owned server support the pilot, and which managed tunnel/provider is acceptable? | Host availability, current provider terms, and privacy practices are not verified. | **Decision:** the project owner operates the service. Assess owned-server readiness and current official host/tunnel terms; choose a fallback managed host if needed. Pilot remains blocked until the review and runbook are complete. |
| Are private release signing and artifact links ready? | Install friction and signing/provider terms affect the pilot. | **Decision:** direct private links for Android APK and macOS Desktop installer only. Public stores, Windows, Linux, and iOS are out of scope. Signing/notarization and artifact-link provider requirements remain to be verified. |
| Is the question/answer retention design approved for real users? | Redacted free text may still contain identifying details and requires current legal/privacy review. | **Decision:** opt-in per question, default off; redacted Q/A text only, no land context or stable IDs, delete within 30 days. Gemini is planned but remains disabled until a qualified privacy/legal review approves current terms and data flow. The qualified review is a hard pre-pilot gate. |

### Conditional decisions

| Decision | Trigger |
|---|---|
| Feedback and non-content operational trace retention | Before enabling either with real users; Q/A product-improvement retention is specified in `pilot_privacy_readiness`. |
| Which Gemini model/tier and whether its gate can pass | Gemini integration is planned for the private pilot, but outbound calls remain disabled until current official terms, data handling, limits/cost, and a qualified privacy/legal review are recorded. The exact model/tier is not selected. |
| Whether local bge-m3 + Chroma/RRF improves retrieval enough to keep | Planned as a measured experiment against current BM25; retain no quality claim absent reviewed results and capacity measurements. |
| How should supported discovery registries be scheduled reliably, and can FEGA/MAPA expose approved machine-readable registries? | Manual BOE and BOJA adapters are implemented; FEGA/MAPA remain explicit unchecked coverage gaps pending official evidence. `knowledge_update_scheduler` owns cadence/missed-run behavior. Discovery may propose candidates, but canonical additions require human approval. |
| Should knowledge update review move from a local draft package to real hosting-platform pull requests with provider-enforced merge protection? | Before relying on the review workflow for scheduled or unattended updates. The local package and controlled merge verify recorded approval but cannot enforce branch protection or stop direct filesystem writes; choose a provider/API and record its protection settings. |

### Later

| Question | Revisit when |
|---|---|
| Accounts, cloud sync, shared access, and multi-device restore | Users need continuity or collaboration across devices |
| SIGPAC references, parcel boundaries, maps, or multiple plots within a land | A validated workflow needs precise geographic records |
| Voice, document/photo interpretation, and offline assistant use | Accessibility and privacy constraints are understood and evaluated |
| iOS release details and native integrations | Android/Desktop MVP is stable; reuse shared logic and UI |
| Cooperative-facing review tools or content | A cooperative agrees to participate and boundaries are clear |
| Expanding automatic legal interpretation beyond source-change detection | Only after qualified legal review and a separately scoped approval model |

Last reviewed: 2026-10-26
