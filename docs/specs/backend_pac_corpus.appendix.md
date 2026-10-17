# Backend PAC corpus — research and verification record

## Repository research

- `knowledge/source_catalog.schema.json` and `backend/app/source_catalog.py` require strict provenance, a source hash, human approval, current lifecycle, and validity dates. Validation does not fetch documents or establish their authenticity.
- `knowledge/passages.schema.json` and `backend/app/retrieval.py` require literal, non-blank passages that resolve to an approved catalog source; a bad source reference is a load error.
- The canonical source catalog is empty and there is no canonical `knowledge/passages.json`. Existing retrieval/generation data is synthetic and is not evidence of legal coverage.
- `docs/risks-and-open-questions.md` records that an independent reviewer has not yet been named. This is a promotion blocker, not permission to populate `reviewed_by` with the author.
- `docs/technical-discovery.md` records the product decision: narrow Andalusia PAC single-application scope, exact coverage only after current official-source review, and no eligibility/aid calculation claims.

## Official-source review completed 2026-10-17

The following primary official materials were checked to define candidate coverage. These are source candidates, not approved catalog entries. A later reviewer must re-open the publication, verify its current text and original/official copy, compute its hash, and approve the exact passages before canonical use.

| Candidate source | Official URL | Candidate use and review note |
|---|---|---|
| Resolution of 21 January 2026 on Andalusia's 2026 Solicitud Única | https://www.juntadeandalucia.es/boja/2026/20/2 | Describes the 2026 aid call, submission through SGA via recognized entities, initial 30 April filing date, and specific adaptation provisions. The filing date was later amended; do not use it alone for the final date. |
| Decreto-ley 1/2026, Article 14 | https://www.juntadeandalucia.es/boja/2026/38/c02/1 | Extends the 2026 Andalusian application filing deadline through 15 May 2026. This is the binding later amendment for the filing-date question. |
| Real Decreto 1048/2022, consolidated text | https://www.boe.es/buscar/act.php?id=BOE-A-2022-23048&lang=es&p=&tn=1 | Articles 108 and 112 provide national presentation and modification rules, including the electronic means provision and its competent-authority exception. The consolidated page showed an update published 8 July 2026 when reviewed. |
| Real Decreto 537/2026 | https://www.boe.es/buscar/doc.php?id=BOE-A-2026-14763 | Adds a 2026 Andalusia-specific modification deadline of 15 June to the 2026 transition provisions. This modifies applications; it is distinct from the 15 May filing deadline and from later adaptation after controls. |
| Andalusia's 2026 Solicitud Única campaign page | https://www.juntadeandalucia.es/organismos/agriculturapescaaguaydesarrollorural/areas/politica-agraria-comun/ayudas-pac/paginas/solicitud-unica-2026.html | Current navigation to forms, recognized entities, applications, and SIGPAC. Treat as an operational pointer, not as a substitute for the binding legal source for a date. |

An Andalusian news item dated 26 April 2026 reported a request to extend filing to 31 May and the modification period to 15 June. The request itself is not the legal basis for a deadline. The official BOE amendment later establishes 15 June for modifications in Andalusia; it does not change the 15 May filing extension identified in Article 14 of Decreto-ley 1/2026. The corpus must not turn a requested extension into a granted one.

### Candidate coverage to confirm

1. **Submission route:** ordinary Andalusian 2026 procedure through the SGA tool via a recognized entity, with wording that preserves the national rule's limited exception for an individual without established electronic access. Do not state that the app files the application or that using an entity is an eligibility condition.
2. **Filing deadline:** for the 2026 Andalusian campaign, filing through 15 May 2026 under Article 14 of Decreto-ley 1/2026. Retain a citation to the amendment; do not cite only the initial 30 April date.
3. **Modification deadline:** for Andalusia in 2026, changes/additions covered by the 2026 transition provision could be made through 15 June 2026. Pair the date with the kind of modification described in Article 112; do not call this the original filing deadline.

The first corpus deliberately excludes late-submission reductions, whether a specific person qualified, payment amounts, document checklists, the status of an individual application, 31 August general adaptations, the special 15 October cotton/rice adaptation, appeals, force majeure, and other campaign years. These may require a separate reviewed feature and more case-specific official sources.

## Implementation plan and tasks

1. Obtain the name/role of an independent reviewer before promotion. If the reviewer is not named, keep canonical data empty and leave the feature blocked; do not invent approval metadata.
2. Download or otherwise review the official original for each source candidate and any current consolidation used to interpret amendment history. Record original and consolidated URLs separately when required by the schema.
3. Compare each copy to the official publication, calculate SHA-256, record publication/download/verification/review dates, and record campaign/validity metadata without implying that a hash proves authenticity.
4. Prepare only the short excerpts needed for the three candidate questions. Record exact article/resolution locations. Have the independent reviewer approve or narrow the claim and its passage.
5. Write `knowledge/pac_coverage.md` with campaign, supported question wording, source IDs/locations, excluded issues, reviewer, and review date.
6. Populate canonical catalog and passage artifacts only after the previous approval; validate every source and reference. Keep no unreviewed alternatives in the runtime set.
7. Add offline tests that exercise the canonical file validators and ensure every documented supported topic has an approved source and passage; do not fetch a URL during validation.
8. Update `knowledge/README.md` and the risk register with the approved outcome. Record only actual review and command evidence in `PROGRESS.md` and the appendix.

## Verification plan and evidence

- Run the accepted catalog validator with the same explicit as-of date used for the test fixture.
- Run `./scripts/init.sh --backend-tests tests/test_pac_corpus.py` for strict data shape, source references, coverage manifest, and no-network behavior.
- A passing schema check alone does not establish source authenticity, legal currency, excerpt accuracy, or independent review. Record the reviewer decision separately in `knowledge/pac_coverage.md`.
- Evidence to capture: sources and hashes; exact approved passage locations; independent reviewer identity/role and date; source chronology for the filing and modification dates; canonical artifact validator output; corpus test output; explicit coverage and gap statement.

## Validator checklist

- [ ] The independent reviewer is different from the corpus author and approves each canonical source and critical passage.
- [ ] The filing-date passage uses the later binding 15 May amendment; the superseded 30 April date is not presented as final.
- [ ] The 15 June 2026 Andalusia modification date is kept distinct from filing and post-notification adaptation.
- [ ] The filing-route answer preserves the limited electronic-access exception and does not promise application submission through Manijero.
- [ ] Every catalog entry resolves to a specific official source and has correct provenance, review, hash, and date metadata.
- [ ] Every passage is literal, accurately located, traceable to an approved source, and sufficient for its documented claim.
- [ ] The coverage file lists the three approved topics and the explicit exclusions; unknown eligibility and aid amounts remain unknown.
- [ ] No synthetic fixture is promoted as real legal evidence; no fetch, scraping, model call, or automatic document ingestion is added.
- [ ] The canonical corpus remains empty and the feature remains blocked if reviewer approval is absent.
