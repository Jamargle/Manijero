# Feature specification: `backend_pac_corpus`

## Source metadata

- **Feature:** `backend_pac_corpus` — Curate the initial Andalusia PAC answer corpus (`knowledge`).
- **Depends on:** `source_catalog_validation` and `source_retrieval` (accepted).
- **Source behavior:** A small, explicitly bounded set of 2026 Andalusian PAC single-application questions can be answered only from independently reviewed official sources and literal, source-located passages.
- **Source verification:** Validate canonical catalog and passages with the existing strict validators; verify each passage against its original official source and its independent approval record.
- **Source note:** Candidate coverage and source chronology are mapped in the appendix. The canonical corpus must remain empty until a reviewer other than the corpus author is named and approves the exact source copies, passages, and coverage statement.

## Goal

Provide a small, manually curated corpus for three procedural topics: where the Andalusian 2026 Solicitud Única is presented, its final 2026 filing deadline, and the separate 2026 deadline for modifying an already submitted application. Publish the exact coverage and known gaps alongside the data.

## Non-goals

- Determining whether a person or land qualifies for an aid, estimating amounts, interpreting individual notices, or calculating late-filing reductions.
- Answering detailed parcel-adaptation questions after monitoring, force-majeure cases, claims, appeals, or questions about other campaign years.
- Adding all PAC interventions, olive-specific eligibility rules, source scraping, automatic downloads, OCR, automatic chunking, or a scheduled refresh job.
- Marking sources approved based on this specification, author review alone, a search result, a press release, or synthetic fixtures.
- Modifying retrieval, generation, the `/ask` contract, land rules, provider choice, or public deployment.

## Job story

When a grower asks a basic question about presenting or changing the 2026 Andalusian PAC single application, I want a short answer backed by the exact applicable official passage, so that a campaign deadline or procedure is not guessed from a superseded notice or a different campaign.

## Acceptance scenarios

### Promote only independently reviewed official sources

Given candidate official documents, when the corpus is prepared, then every source promoted into `knowledge/source_catalog.json` has the accepted provenance, review, lifecycle, URL, hash, and date fields; the downloaded original is checked against its official publication; and a human reviewer other than the author records approval. If that reviewer is not yet named or approval is absent, the canonical catalog and passage set remain empty and this feature stays blocked.

### Answer only the published coverage

Given an independently approved corpus and coverage statement, when a question asks where to present the 2026 application, the final filing date, or the separate modification date, then each supported fact has a literal passage with a precise article/resolution location and citation. The coverage statement names these supported questions and the campaign year.

### Preserve amendment chronology

Given official documents that state different 2026 dates, when a passage is selected, then it reflects the later binding campaign amendment for that action and identifies the distinct filing and modification actions. A superseded date is not presented as the final deadline. A request for an extension that was not itself enacted is not treated as a binding date.

### Keep procedure exceptions and gaps honest

Given a question about electronic filing, when the national rule and Andalusian route are combined, then the answer does not imply that every individual must use the same electronic channel if the official rule provides a competent-authority exception. Questions about personal eligibility, amounts, late penalties, notices, or detailed monitoring adaptations return the accepted safe abstention unless the reviewer explicitly approves additional coverage.

### Reject unreviewed, unsupported, or malformed data

Given missing approval, stale verification, a broken source URL, a hash mismatch, an unknown source reference, or an invalid passage schema, when the canonical corpus is validated, then no affected passage is eligible for `/ask`; validation reports a located, payload-safe error and does not silently skip a bad reference.

## Technical approach

- Use the accepted `source-catalog-v1` and `passage-set-v1` formats and their executable validators. Do not add a parallel corpus format or a second feature board.
- Add canonical `knowledge/passages.json` only when the independently reviewed source catalog and its passages are ready together. Keep test-only material under `backend/tests/fixtures/` and label it synthetic.
- Add `knowledge/pac_coverage.md` with the reviewed campaign year, supported question formulations, source IDs and locations, explicit exclusions, review date, and reviewer role/identifier. The page is the human-readable coverage boundary; the evaluator feature later adds reviewed question cases.
- For every critical date, the reviewer compares the cited excerpt with the original source and records its action, campaign, and effective date. Do not merge separate filing, modification, and post-notification adaptation periods into one answer.
- Preserve unknown applicability as absent. These procedural rules do not establish a land's eligibility and do not need land-specific claims.
- Do not include copied source documents in the runtime corpus unless their inclusion is authorized and useful for review; canonical passages remain short, literal excerpts with source locations.

## Expected file changes

- `knowledge/source_catalog.json` — add only independently approved, current primary sources; otherwise keep empty.
- `knowledge/passages.json` (new) — add only reviewer-approved literal passages; otherwise keep absent or explicitly empty according to `backend_ask_endpoint`'s empty-corpus contract.
- `knowledge/pac_coverage.md` (new) — document supported questions, campaign scope, sources, exclusions, review date, and reviewer.
- `knowledge/README.md` — explain the 2026 slice, independent approval gate, and the meaning of an empty canonical corpus.
- `backend/tests/test_pac_corpus.py` (new) — check canonical artifact validity, source-to-passage references, and approved coverage invariants without relying on a network connection.
- `docs/risks-and-open-questions.md` — resolve the corpus-coverage item only after independent approval; keep reviewer ownership open until a reviewer is named.

## Visual design impact

None. This knowledge feature adds no UI or Spanish app copy.

## Durable documentation impact

- `knowledge/pac_coverage.md` and `knowledge/README.md`: update with the approved corpus boundary and review procedure.
- `knowledge/source_catalog.json` and `knowledge/passages.json`: update only after independent approval; never fabricate reviewer metadata.
- `docs/risks-and-open-questions.md`: update only after a reviewer and exact approved coverage are recorded.
- `ARCHITECTURE.md`, `CONSTRAINTS.md`, `contracts/openapi.yaml`, `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, and `docs/domain-model.md`: no change; this feature uses accepted artifact and runtime boundaries.
- `PROGRESS.md` and `feature_list.json`: update status and evidence only after source validation and independent review are complete.
- `docs/validations/backend_pac_corpus.md`: create only during independent feature validation.

## Focused verification

`./scripts/init.sh --feature backend_pac_corpus` runs the exact checks below after implementation. An empty corpus is a valid outcome while reviewer approval is unresolved, but it does not satisfy feature acceptance.

<!-- verify:start -->
```sh
python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-17
./scripts/init.sh --backend-tests tests/test_pac_corpus.py
```
<!-- verify:end -->

## Appendix

The official-source research, source chronology, implementation tasks, and validator checklist are in [`backend_pac_corpus.appendix.md`](backend_pac_corpus.appendix.md).
