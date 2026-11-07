# `seed_corpus_expansion` — appendix

## Repository research

### Files inspected

- `PROGRESS.md` — current corpus statement (four official sources, four literal passages, three topics) and known-limitation wording that must be updated.
- `knowledge/source_catalog.json` — four approved entries; the IDs, hosts, dates, digest, and optional campaign/applicability pattern to follow.
- `knowledge/source_catalog.schema.json` — `source-catalog-v1` admission rules: exact issuer hosts, SHA-256 of the original, `approved`/`current` only, `valid_until` ineligibility, no unknown applicability.
- `backend/app/source_catalog.py` — executable validator; `valid_until < as-of` fails as expired, campaign requires `valid_until`, and non-current lifecycle is rejected.
- `knowledge/passages.json` and `knowledge/passages.schema.json` — literal excerpt + `location` + resolving `source_id`; no paraphrase, no extra fields.
- `backend/app/retrieval.py` — passage-set validator and index; an unknown source is a load error and only approved/current/unexpired sources are indexed.
- `knowledge/pac_coverage.md` — the Spanish coverage record: supported topics, exclusions, reviewer/date, and the report-only evaluation boundary.
- `knowledge/README.md` — file table, issuer/host policy, reviewer procedure, correction/update procedure, and the four-source/four-passage statements to update.
- `knowledge/pac_answer_eval.json` — `pac-answer-eval-v2` coverage areas, omissions, and 14 author-only cases; the after-state case set the merge gate binds.
- `backend/app/review_package.py`, `backend/scripts/knowledge_review.py` — `knowledge-update-proposal-v1` prepare/decide/merge; proposal links each corpus change to quarantined candidates and requires the reviewed case set.
- `backend/README.md` §"Human-reviewed knowledge update packages" and §"Manual official-document candidate ingestion" — operator commands, candidate admission, extraction limits, and the merge-is-not-release rule.
- `backend/tests/test_pac_corpus.py` — hardcoded 4 sources / 4 passages, exact `2026-10-17` validity, three topic strings, and one retrieval probe; the main guard to update.
- `backend/tests/test_source_catalog.py`, `backend/tests/test_retrieval.py` — additional canonical `len(...) == 4` assertions.
- `backend/tests/test_pac_answer_eval.py` — canonical load of catalog/passages/cases; the after-state must keep every expected reference resolvable.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageContent.kt`, `shared/src/commonMain/composeResources/values/strings.xml`, `scripts/validate_coverage_copy.py` — pinned disclosure model, plain-Spanish copy, and the independent expected-list check (including the current "not yet" list).
- `docs/constraints/answers-and-knowledge.md` §Campaign scope, §Coverage disclosure, §Knowledge updates and retrieval — the durable rules this change must obey.
- `docs/archive/specs/backend_pac_corpus.appendix.md` — precedent for the independent review record: verified copies, hashes, exact literal passages, and the coverage boundary.
- `docs/archive/MasterPlanV3.md` §11.1–11.3 — historical seed list, candidate URLs, and known validity concerns (only leads, re-verified against official sources).
- `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md` — corpus-boundary statements that must track the reviewed slice.

### Existing patterns to follow

- Canonical knowledge is Git-tracked, human-approved, and read-only at runtime; only the controlled merge writes it.
- Every source carries the original official URL, a reviewed-copy digest, real download/verification dates, and only official metadata; unknowns stay absent.
- Passages are literal excerpts with a location and a resolvable source; no automatic ingestion or summarisation is allowed.
- Corpus changes require an evaluation-case file at prepare and merge; orphaned cases block readiness.
- Coverage is described in Spanish in `pac_coverage.md`; the client disclosure is pinned copy checked by `scripts/validate_coverage_copy.py`, with no digits or legal facts.
- Network access belongs only to operator commands; tests stay offline and report-only.
- Historical source leads are unverified until a human reviews the official copy.

### Source candidates (unverified leads only)

These identities and URLs come from `docs/archive/MasterPlanV3.md` §11.2–11.3 and the existing
`passages.json` citation of Law 39/2015. They are leads to re-locate, not verified facts; no
validity, campaign, or amendment status is asserted here.

| Item | Candidate identity / lead | Open point |
|---|---|---|
| RD 1047/2022 | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23047` | Locate the SIGPAC provisions; the archive says it repealed RD 1077/2014 |
| RD 1049/2022 | `https://www.boe.es/eli/es/rd/2022/12/27/1049` | Locate the original publication and consolidated text; the archive names later amending decrees |
| RD 1054/2022 | `https://www.boe.es/eli/es/rd/2022/12/27/1054/con` (consolidated lead) | Find the original URL and the modifying decree; do not quote a superseded notebook regime |
| Order 24/03/2023 | `https://www.juntadeandalucia.es/boja/2023/61/BOJA23-061-00030-5898-01_00280950.pdf` | BOJA PDF extraction may lose glyphs; compare with the official page |
| Order correction | `https://www.juntadeandalucia.es/boja/2023/80/BOJA23-080-00002-7483-01_00282518.pdf` | Register separately; record what it corrects |
| FEGA extension | `https://www.fega.gob.es/es/noticias/node-16804` | May be a news item rather than a citable act; the archive's `2026-06-15` end date is not a validity finding |
| Law 39/2015 | Not located in the archive; find the BOE original of Ley 39/2015, de 1 de octubre | Select only representation/notification/rectification provisions that are literally quotable |


### Current gaps and risks

- No correction/amendment/repeal relation field exists; the relationship can only be documented in prose and as separate source records.
- No digest field exists for a consolidated text; a passage quoted from consolidation must disclose that in its location and evidence.
- The FEGA extension lead carries `valid_until: 2026-06-15`; a catalog entry with that end date fails the validator after that date. It cannot be cataloged unless the official text establishes a later current validity.
- The seed documents are not in a live discovery registry. Ingestion needs an operator-authored seed discovery state so quarantine provenance and hashes exist for the review package.
- The corpus guards hardcode 4/4 and the 2026-10-17 date; adding sources without updating them fails, and editing the counts without per-document presence checks would weaken the guard.
- Adding passages for a "not yet" topic (digital notebook, conditionality detail) would contradict the pinned disclosure; either keep it uncovered or update copy and validator together.
- A merge is not a release: any existing local knowledge release stays bound to the old corpus until the separate reindex/release step.
- The human reviewer must be available; an agent cannot produce the approval and must not bypass the gate.

## Seed review record (2026-11-06)

Every publication in the seed list has one recorded outcome. The reviewed copy is the quarantined official page whose SHA-256 is below; `added` ids are the proposed catalog ids, `not_added` ids stay absent. No human decision exists yet, so the reviewer/date column is the pending reviewer request and the table is a proposal, not an approval.

| Stable id | Seed item | Verdict | Official URL | Issuer | Retrieved | Reviewer/date | SHA-256 of reviewed copy | Official basis |
|---|---|---|---|---|---|---|---|---|
| `rd_1047_2022` | RD 1047/2022 | `added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23047` | BOE | 2026-11-06 | pending (Diego) | `5b507f512acda38782acee7c29c18cffa0fccb89d0d5e71b8f698347ffbb34e8` | Original text; art. 2.g/h wording also appears unchanged in the consolidated copy last updated 20/11/2025. |
| `rd_1049_2022` | RD 1049/2022 | `not_added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23049` | BOE | 2026-11-06 | pending (Diego) | `29a7f4aec0608ee76f7a7da7e2ec5e7f1748afc121dd9219ead83ba8e94be1d2` | In force, but conditionality is a pinned "not yet covered" disclosure topic; adding a passage would contradict the copy. |
| `rd_1054_2022` | RD 1054/2022 | `not_added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23054` | BOE | 2026-11-06 | pending (Diego) | `b296b58825adc299d16ed0c80e14c1f04765e1df82636fefeb8663a4951d1220` | In force, but SIEX and the digital notebook are a pinned "not yet covered" disclosure topic; adding a passage would contradict the copy. |
| `orden_2023_03_24` | Order 24/03/2023 | `added` | `https://www.juntadeandalucia.es/boja/2023/61/4` | Junta de Andalucía | 2026-11-06 | pending (Diego) | `8408b2c3702a9d5fee5cf12bbe821b087111943a552f0141efa8f344d690b111` | Original text; art. 4.2 is the SIGPAC alegación step for the single application, untouched by the BOJA 2023/80 correction. |
| `orden_2023_03_24_correccion` | Order correction | `not_added` | `https://www.juntadeandalucia.es/boja/2023/80/1` | Junta de Andalucía | 2026-11-06 | pending (Diego) | `e68f738b0fa246690a5544563f72d7575d2db8848cdec93f0c9a338331416be0` | Corrects arts. 46–51 of the Order, unrelated to the selected art. 4.2; establishes no independent provision, so it is recorded as evidence only. |
| `fega_res_2026_05_20` | FEGA extension | `not_added` | `https://www.fega.gob.es/es/noticias/node-16804` | FEGA | 2026-11-06 | pending (Diego) | `b019e854f6b51f5011d665b8a09e03945cd6a2e2950165606a9a3e514986010d` | News item announcing a deadline of 15/06/2026 that has passed; the extension is consolidated in the already-approved RD 537/2026. |
| `ley_39_2015` | Ley 39/2015 | `added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2015-10565` | BOE | 2026-11-06 | pending (Diego) | `25e65461e3bd13abb4b2821f2e2bbd317d4ea363cd915f3923cc2bedc6fea683` | Original text; art. 41.1 and 109.2 wording also appears unchanged in the consolidated copy last updated 06/11/2024. |

Supporting copies compared in the same review (not catalog entries):

| Copy | URL | SHA-256 | Use |
|---|---|---|---|
| RD 1047/2022 consolidation | `https://www.boe.es/buscar/act.php?id=BOE-A-2022-23047` | `3d362d7a16598858a1b36f2672f2e7ab8d0100342832f1fd645fa37913647590` | Confirms art. 2.g/h wording; the catalog digest stays on the original. |
| Ley 39/2015 consolidation | `https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565` | `52fe28b88b4f5510345b274098ed3faf25fcefb3c72ebc8d62a57108494fcb9c` | Confirms art. 41.1/109.2 wording; the catalog digest stays on the original. |
| Order 24/03/2023 PDF | `https://www.juntadeandalucia.es/boja/2023/61/BOJA23-061-00030-5898-01_00280950.pdf` | `ddd0a484a44782465f8362b9c0e8977c2760ebaa93933aa2b68ea839341b603d` | Rejected: 12,987 U+FFFD characters; the official HTML page is the reviewed copy. |

### Proposal package

- Proposal `knowledge-update-proposal-v1`, author `manijero-feature-implementer` (automation), requested reviewer `Diego`; 7 quarantined candidates (the three added documents, the two not-added decrees, the correction, and the FEGA item).
- `prepare --cases knowledge/pac_answer_eval.json --as-of 2026-11-06`: `ready_for_review`, 61 passed / 0 failed / 1 report-only; package id `8c7b2e22c5cb10c2a02a5b303f67e92ebe192dd077f7b4d2cb29e324ee3907b9`.
- Adds: 3 catalog sources and 5 passages; 3 source-to-candidate links; 0 updates/removals; 0 orphaned or rewritten evaluation cases (14 cases bound).
- Passage ids and locations: `pasaje-definicion-parcela-sigpac` (RD 1047 art. 2.1.g), `pasaje-definicion-recinto-sigpac` (RD 1047 art. 2.1.h), `pasaje-alegacion-sigpac-solicitud-unica` (Order art. 4.2), `pasaje-notificacion-preferencia-electronica` (Ley 39/2015 art. 41.1), `pasaje-rectificacion-errores-materiales` (Ley 39/2015 art. 109.2).
- Canonical before/after hashes in the package: catalog `e9d87ef0…243a` / `27c7c896…41d`, passages `ac01d564…da3e` / `a4d026ad…a074`. Canonical files were not written; the package is a draft.
- The proposal has 8 difference entries; their fields exceed the package's 40-field display bound, so `differences_truncated` is true. The full entries are in the package's proposal body.

### Implementation findings

- The change-impact analyzer's 50-signal cap made every full statute fail analysis (`size_limit_exceeded`, 103 signals for RD 1047 and 77 for Ley 39/2015). The bound was raised to 200 with an inclusive-bound regression test, and the current `backend/README.md` description was updated; the archived historical appendix is unchanged.
- `scripts/validate_coverage_copy.py` did not count `coverage_open`, which is rendered by `chat/ChatHomeScreen.kt`; the guard was failing on the tracked baseline. The home screen was added to the displayed-source set, so the check now resolves all 20 coverage resource keys. No Spanish copy changed.
- The evaluation case set cannot be extended in this package: `prepare` validates `--cases` against the before-state, so a case naming an unmerged passage id fails. Extension is deferred until after a merge and is recorded as a residual gap.

## Implementation plan

1. Snapshot the baseline: counts, focused tests, and the current coverage statement; record the exact approval/validation dates used.
2. Locate each official original (and consolidation/correction where published) on an approved issuer host; discard secondary or unpublishable leads.
3. Build the seed discovery/ingestion state outside `knowledge/`, quarantine the official copies, and record original/extracted hashes; use an official HTML/PDF alternative when extraction fails, never OCR.
4. Compare the official original, extracted text, and consolidated/corrected text; record validity, amendment, campaign, and applicability evidence for each document.
5. Write the per-document verdict table (stable id, `added`/`not_added`, official basis, URL, retrieval date, digest) in `pac_coverage.md`; no silent omission.
6. Draft the proposal's catalog/passage add entries only for admitted current provisions; leave unknown fields absent and defer the disclosure's "not yet" topics.
7. Update the bounded `pac_answer_eval.json` cases for newly answerable topics; confirm no existing expected source/passage becomes orphaned.
8. Draft `knowledge-update-proposal-v1` with links to every candidate; run `prepare --cases`; resolve checks until `ready_for_review`.
9. Hand the package to the named reviewer; record approve/request-changes/reject. On approval only, run `merge`; otherwise leave canonical files byte-identical and record the reason.
10. Update coverage/README/risk/limit statements, exact-count and per-document guards, and the retrieval assertions; change disclosure copy and its expectation only if a topic moves.
11. Run the focused verification block, record the package/merge evidence and limits, and update `PROGRESS.md` and the feature status only after acceptance.

## Verification plan

- `--backend-tests -q tests/test_pac_corpus.py tests/test_source_catalog.py tests/test_retrieval.py tests/test_pac_answer_eval.py` — exit 0; exact new counts, verdict-table consistency (added ids present, not-added ids absent), every added passage indexed and retrievable, no orphaned eval reference.
- `validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-11-06` — exit 0; all entries approved, current, and unexpired at the pinned date; repeat at the actual approval date.
- `python3 scripts/validate_coverage_copy.py` — exit 0; copy and expected topic lists agree and contain no forbidden legal facts.
- Manual reviewer check — each original, extracted, and consolidated/corrected copy compared; one line per document in the evidence.
- Rejection check — after a request-changes/reject decision, `git diff --quiet knowledge/` shows byte-identical canonical files (no merge).
- E2E: not needed; there is no client/server wire change. The bounded `/ask` cases plus the retrieval guard cover the answer path, and the merge gate covers the corpus write path.

## Evidence to capture

- Per-document verdict table: official URL, issuer, retrieval date, SHA-256, reviewed version/consolidation date, outcome, official basis.
- Package id, check summary, reviewer name/role and decision date, merge record and canonical after-hashes (or the recorded rejection).
- Exact new source/passage/topic/case counts and the coverage matrix; the list of not-added documents and why.
- Focused command results, one line each; confirmation that the local release was not rebuilt.
- Residual gaps: amendments not in the corpus, consolidation-digest limit, unsupported topics, author-only evaluation limits.

## Feature evidence

All on 2026-11-06, from the seed worktree; canonical `knowledge/source_catalog.json` and `knowledge/passages.json` were never edited.

- `ingest_official_documents.py` on the operator-authored seed state: 10/10 candidates extracted, 0 failed, originals and extracted digests recorded under `build/seed-corpus-review/quarantine`.
- Extraction scan: 0 U+FFFD in all copies except the Order PDF (12,987), so the HTML Order copy was selected; every selected passage is a literal substring of its extraction, and the RD 1047/Ley 39/2015 passages also appear in the consolidated copies.
- `scripts/validate_coverage_copy.py` before the guard repair: exit 1, `missing references: {'coverage_open'}`; after adding `ChatHomeScreen.kt` to the displayed sources: exit 0, `20 displayed feature resource keys`.
- `knowledge_review.py prepare … --cases knowledge/pac_answer_eval.json --as-of 2026-11-06`: exit 0, `ready_for_review`, 61 passed / 0 failed / 1 report-only, 0 orphaned cases.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests -q tests/test_pac_corpus.py tests/test_source_catalog.py tests/test_retrieval.py tests/test_pac_answer_eval.py`: exit 0, `141 passed`.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests -q tests/test_change_impact.py`: exit 0, `57 passed`.
- `validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-11-06`: exit 0, 4 source(s) checked.
- `validate_source_catalog.py build/seed-corpus-review/after-catalog.json --as-of 2026-11-06`: exit 0, 7 source(s) checked (proposed after-state).
- `git diff --quiet knowledge/source_catalog.json knowledge/passages.json`: exit 0 (byte-identical).
- Retrieval probe on the proposed after-state: all five new passages ranked first for their distinctive plain-Spanish question (`PASS` ×5); no `/ask` or release behavior changed.
- Package review: 7 candidates, 3 catalog adds, 5 passage adds, 3 links, 14 cases bound, no orphaned/rewritten case; reviewer decision and merge are still absent.

## Residual gaps

- No human approval or merge exists in this session; the feature status stays `in_progress`, and the exact-count guards (4 sources / 4 passages) and `pac_coverage.md`/README corpus statements still describe the merged corpus, not the proposal.
- `knowledge/pac_answer_eval.json` has no new cases for the SIGPAC/notification passages; the extension must be a separate reviewed change after merge.
- The catalog digest covers each original copy; consolidated copies are comparison evidence only and are not independently digest-tracked in the catalog.
- The FEGA resolution and the Order correction stay outside the catalog; later official consolidations or corrections must be re-read before any passage is added.
- The 50-to-200 signal-cap change and the coverage-copy guard repair are implementation repairs, not corpus facts; a validator should confirm they are acceptable scope.

## Handoff

- Status: approved and merged; `feature_list.json` = `in_progress`; canonical knowledge committed on `feature/seed_corpus_expansion`.
- Review: package `8c7b2e22…07b9` approved by `Diego` (external validator, named human other than the author) on 2026-11-07 via `knowledge_review.py decide`; note "Veredictos revisados: 3 añadidos, 4 no añadidos."
- Merge: `knowledge_review.py merge` exit 0; catalog after `27c7c896…b41d`, passages after `a4d026ad…a074` (match the package's after-hashes); `reindex_required: true`, `reindexed: false`, `released: false`.
- Follow-up (same day): count guards updated to 7 sources/9 passages in `test_pac_corpus.py`, `test_source_catalog.py`, `test_retrieval.py`; `knowledge/pac_coverage.md` gained a dated expansion section. `./scripts/init.sh --feature seed_corpus_expansion`: 141 passed, catalog validator 7 sources exit 0, coverage-copy guard exit 0. Historical "four passages" measurements in `backend/README.md` and `docs/risks-and-open-questions.md` are dated and left unchanged.
- Not done: eval-case extension for the new passages; reindex/release.
- Note: catalog `reviewed_on` is 2026-11-06 (review copies) while Diego's approval is 2026-11-07; the validator passes at both dates, so this is not a defect.
- Hold-back (same day): post-merge `evaluate_pac_answers.py` showed expected-state agreement 8/14 vs 13/14 on main. Ablation: `pasaje-alegacion-sigpac-solicitud-unica` (7/14 alone) and `pasaje-definicion-parcela-sigpac` (12/14 alone) displace deadline/channel passages; the other three are neutral. Package `dfa5f081…3128` (remove both passages and `orden_2023_03_24`; 21 passed, `ready_for_review`) approved by Diego 2026-11-07 (relayed by the owner in session) and merged: catalog `9afdebba…bd9d`, passages `ca839a3e…4608`, `reindex_required: true`. Corpus is now 6 sources / 7 passages; eval back to 13/14 state, 8 citation, 9 critical facts. Recinto passage recorded in `DELIBERATELY_REJECTED_EXTRACTIVE` (multi-sentence literal). `init.sh --fast` passed (1872); focused tier 141 passed.
- Next role: `feature-validator`.

## Validator checklist

- [ ] Every listed publication has a cited verdict; no document was silently dropped, and the verdict table agrees with the catalog/passage artifacts.
- [ ] Only approved, current, unexpired documents are cataloged; validator exits 0 at the approval date.
- [ ] Passages are literal, located, resolve to approved sources, and introduce no new legal fact or inferred applicability.
- [ ] Corrections and amendments are registered or explicitly excluded; superseded wording is never presented as current.
- [ ] A named human other than the proposer approved; canonical files changed only through `merge`, and a rejection left them byte-identical.
- [ ] Coverage, README counts, risk/limitation statements, guards, and (if applicable) pinned copy are consistent.
- [ ] The focused verification block runs unchanged through `./scripts/init.sh --feature seed_corpus_expansion`.
- [ ] No reindex/release, `/ask` contract change, or legal-coverage/quality overclaim was made.
- [ ] `feature_list.json` and `PROGRESS.md` are updated accurately by the implementer/validator.
