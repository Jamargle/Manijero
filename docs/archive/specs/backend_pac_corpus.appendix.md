# Backend PAC corpus — research and verification record

## Repository research

- `knowledge/source_catalog.schema.json` and `backend/app/source_catalog.py` require strict provenance, a source hash, human approval, current lifecycle, and validity dates. Validation does not fetch documents or establish their authenticity.
- `knowledge/passages.schema.json` and `backend/app/retrieval.py` require literal, non-blank passages that resolve to an approved catalog source; a bad source reference is a load error.
- The canonical source catalog and passage set contain the four approved official sources and four literal passages for the bounded 2026 coverage. The source catalog validator checks metadata and policy; it does not fetch documents or establish authenticity.
- Diego is the named independent reviewer. His approval of the source copies, literal passages, and coverage boundary is recorded in the catalog, passage artifacts, and `knowledge/pac_coverage.md`.
- `docs/archive/technical-discovery.md` records the product decision: narrow Andalusia PAC single-application scope, exact coverage only after current official-source review, and no eligibility/aid calculation claims.

## Official-source review completed 2026-10-17

The following primary official materials were researched. The four documents used by the corpus were downloaded, checked against their official publications, hashed, and approved by Diego. The campaign page remains an operational reference only and is not included as a corpus source.

| Selected source | Official URL | Corpus use and review note |
|---|---|---|
| Resolution of 21 January 2026 on Andalusia's 2026 Solicitud Única | https://www.juntadeandalucia.es/boja/2026/20/2 | Describes the 2026 aid call, submission through SGA via recognized entities, initial 30 April filing date, and specific adaptation provisions. The filing date was later amended; do not use it alone for the final date. |
| Decreto-ley 1/2026, Article 14 | https://www.juntadeandalucia.es/boja/2026/38/c02/1 | Extends the 2026 Andalusian application filing deadline through 15 May 2026. This is the binding later amendment for the filing-date question. |
| Real Decreto 1048/2022, consolidated text | https://www.boe.es/buscar/act.php?id=BOE-A-2022-23048&lang=es&p=&tn=1 | Articles 108 and 112 provide national presentation and modification rules, including the electronic means provision and its competent-authority exception. The consolidated page showed an update published 8 July 2026 when reviewed. |
| Real Decreto 537/2026 | https://www.boe.es/buscar/doc.php?id=BOE-A-2026-14763 | Adds a 2026 Andalusia-specific modification deadline of 15 June to the 2026 transition provisions. This modifies applications; it is distinct from the 15 May filing deadline and from later adaptation after controls. |
| Andalusia's 2026 Solicitud Única campaign page | https://www.juntadeandalucia.es/organismos/agriculturapescaaguaydesarrollorural/areas/politica-agraria-comun/ayudas-pac/paginas/solicitud-unica-2026.html | Current navigation to forms, recognized entities, applications, and SIGPAC. Treat as an operational pointer, not as a substitute for the binding legal source for a date. |

An Andalusian news item dated 26 April 2026 reported a request to extend filing to 31 May and the modification period to 15 June. The request itself is not the legal basis for a deadline. The official BOE amendment later establishes 15 June for modifications in Andalusia; it does not change the 15 May filing extension identified in Article 14 of Decreto-ley 1/2026. The corpus must not turn a requested extension into a granted one.

### Approved coverage

1. **Submission route:** ordinary Andalusian 2026 procedure through the SGA tool via a recognized entity, with wording that preserves the national rule's limited exception for an individual without established electronic access. Do not state that the app files the application or that using an entity is an eligibility condition.
2. **Filing deadline:** for the 2026 Andalusian campaign, filing through 15 May 2026 under Article 14 of Decreto-ley 1/2026. Retain a citation to the amendment; do not cite only the initial 30 April date.
3. **Modification deadline:** for Andalusia in 2026, changes/additions covered by the 2026 transition provision could be made through 15 June 2026. Pair the date with the kind of modification described in Article 112; do not call this the original filing deadline.

The first corpus deliberately excludes late-submission reductions, whether a specific person qualified, payment amounts, document checklists, the status of an individual application, 31 August general adaptations, the special 15 October cotton/rice adaptation, appeals, force majeure, and other campaign years. These may require a separate reviewed feature and more case-specific official sources.

### Independent review decision (2026-10-17)

Diego independently checked the four downloaded official source copies against their official publications, approved their recorded SHA-256 hashes and provenance metadata, and approved the four exact literal passages and their locations, along with the three-topic coverage boundary and exclusions, on 2026-10-17. The approved excerpts and source locations are recorded in `knowledge/passages.json`; source records are in `knowledge/source_catalog.json`. The canonical catalog contains only these four sources; the campaign page is not treated as legal evidence.

## Implementation plan and tasks

1. Download and check the official original for each selected source, recording original and consolidated URLs separately where relevant.
2. Record SHA-256, publication/download/verification/review dates, campaign and validity metadata without implying that a hash proves authenticity.
3. Select only the short excerpts needed for the three supported questions, record exact article/resolution locations, and obtain independent approval of each claim and passage.
4. Record the approved campaign scope, source IDs/locations, exclusions, reviewer, and review date in `knowledge/pac_coverage.md`.
5. Validate each canonical source and passage reference; keep unreviewed alternatives out of the runtime set.
6. Add offline tests for the artifact validators and coverage invariants; do not fetch URLs during validation.
7. Update `knowledge/README.md`, the risk register, and status/evidence records after review and verification.

## Verification plan and evidence

- Run the accepted catalog validator with the same explicit as-of date used for the test fixture.
- Run `./scripts/init.sh --backend-tests tests/test_pac_corpus.py` for strict data shape, source references, coverage manifest, and no-network behavior.
- A passing schema check alone does not establish source authenticity, legal currency, excerpt accuracy, or independent review. Record the reviewer decision separately in `knowledge/pac_coverage.md`.
- Evidence to capture: sources and hashes; exact approved passage locations; independent reviewer identity/role and date; source chronology for the filing and modification dates; canonical artifact validator output; corpus test output; explicit coverage and gap statement.

## Validator checklist

- [x] Independent reviewer Diego approved the four selected source copies, exact passages, three topics, and exclusions on 2026-10-17.
- [x] Exact literal passages, source locations, and source-copy verification metadata are recorded in the canonical artifacts.
- [x] The filing-date passage uses the later binding 15 May amendment (`dl_1_2026`); the superseded 30 April date is not presented as final.
- [x] The 15 June 2026 Andalusia modification date (`rd_537_2026`) is kept distinct from filing and post-notification adaptation.
- [x] The filing-route answer preserves the limited electronic-access exception and does not promise application submission through Manijero.
- [x] Every catalog entry resolves to a specific official source and has provenance, review, hash, and date metadata.
- [x] Every passage is literal, located, traceable to an approved source, and sufficient for its documented claim.
- [x] The coverage file lists the three approved topics and explicit exclusions; unknown eligibility and aid amounts remain unknown.
- [x] No synthetic fixture is promoted as legal evidence; no fetch, scraping, model call, or automatic document ingestion was added.
- [x] The canonical corpus is verified with 4 approved sources and 4 literal passages.

## Feature evidence

- Implementer outcome: **passing**. Diego verified the downloaded original official documents, recorded their SHA-256 hashes in `knowledge/source_catalog.json` (4 sources), and approved the exact literal passages in `knowledge/passages.json` (4 passages).
- `knowledge/pac_coverage.md` records the reviewer and approved boundary. The independent acceptance record is `docs/validations/backend_pac_corpus.md`.
- `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-18`: passed (4 sources).
- `PYTHONPATH=backend python3 -c "import backend.tests.test_pac_corpus as test_mod; test_mod.test_canonical_artifacts_are_valid_and_have_approved_coverage(); test_mod.test_approved_topics_and_exclusions()"`: passed all invariant assertions.
- `./scripts/init.sh --feature backend_pac_corpus`: catalog validation passed, but the published pytest command was unavailable in the original environment. The focused pytest command was subsequently run successfully in an isolated test environment; see the validation record.
