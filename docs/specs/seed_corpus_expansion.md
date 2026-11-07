# Review and add the remaining seed documents

## Source metadata

- `id`: `seed_corpus_expansion` · `area`: `knowledge` · `depends_on`: `pac_evidence_expansion`, `knowledge_update_review_pr` · `status` at planning: `not_started`
- User-visible behavior: the reviewed corpus gains the seed documents that pass human review, so `/ask` can cite them for the procedural, SIGPAC, and notification topics the coverage screen already names where the reviewed text supports a passage; every document that is expired, repealed, superseded, or not verifiable stays out and is recorded with the official reason.
- Verification: focused backend corpus/catalog/retrieval/evaluation tests, the catalog validator as of the recorded approval date, and the pinned coverage-copy check; canonical changes exist only through a recorded human approval.
- Notes: the list names six items; the Order and its correction are two publications, so the review covers up to seven documents. A named human other than the proposing agent must approve the corpus change; the agent may prepare and run the approved merge, but never supply the approval. Not adding a document after review is an accepted, recorded outcome, not a failure to hide.

## Goal

Close the gap between the planned seed corpus and the four-document reviewed slice by giving every remaining seed document a cited, reviewable verdict and, only where an official copy confirms current wording, adding it as an approved source with literal passages that the answer service can cite.

## Non-goals

- Growing the golden question set to 40–60 cases (`golden_dataset_expansion`) or adding validity regression cases (`validity_regression_cases`).
- Denunciation, complaint, or whistleblowing guidance, or using the corpus to denounce an institution or person: this is a review and expansion feature, not a denouncing context.
- New issuers, hosts, lifecycle values, or schema fields for corrections/amendments/repeals; no relation graph.
- Automatic legal interpretation, validity inference, OCR, summarization, or paraphrased answers.
- Reindexing, releasing, deploying, or changing `/ask`, abstention, or retrieval behavior or its contract.
- Answering eligibility, amounts, penalties, individual notifications, appeals, force majeure, other campaigns, or cooperative practices.
- Widening the pinned "not yet covered" disclosure topics (organic, water, conditionality in detail, digital notebook, insurance, pruning burning) unless the evidence and the copy change together.

## Job story

When the assistant describes or answers within its reviewed corpus, I want each remaining seed document to have a cited verdict and to be answerable only through an approved literal passage, so a repealed, expired, uncorrected, or unverified document cannot silently become legal evidence.

## Acceptance Scenarios

### 1. Every listed document has a cited verdict

Given the seed list (RD 1047/2022, RD 1049/2022, RD 1054/2022, Order 24/03/2023, its BOJA correction, the FEGA extension, Law 39/2015), when the review completes, then each listed item has one recorded outcome — added or not added — with the official URL, issuer, retrieval date, SHA-256 of the reviewed copy, the official basis for the verdict, and the reviewer's date; no listed document is silently dropped.

### 2. An admitted document is cataloged and passes the admission contract

Given an official copy the reviewer confirms is current, when it is added, then `knowledge/source_catalog.json` contains the original official URL on that issuer's approved host, the digest of the reviewed copy, real download/verification/review dates, `review_status: approved`, `lifecycle_status: current`, and campaign/`valid_until`/`applicability` only when the official text establishes them; the catalog validator exits `0` as of the approval date.

### 3. Expired, repealed, superseded, or unverifiable documents stay out

Given official evidence that a document is repealed, expired at the approval date, superseded, or not citable, or no adequate official copy with which to verify it, when the review completes, then it appears in no catalog or passage entry, is recorded as not added with the cited basis, and no answer is derived from it. This includes an extension whose official validity ended before the approval date and a publication that is only a news item rather than a citable act.

### 4. Corrections and amendments are not presented as current by accident

Given the Order 24/03/2023 correction, or a seed document amended after publication, when passages are selected, then the answerable excerpt reflects the corrected or consolidated wording as of a recorded date, the correction's own official URL and digest are recorded in the verdict table and, when it satisfies the catalog's current-document rule, registered as its own approved source, and superseded wording is never presented as current; if the current wording cannot be established from an official copy, the affected provision yields no passage.

### 5. Passages are literal, located, and bounded

Given an added document, when passages are selected, then each is a short literal excerpt with an exact article/section/page location that resolves to the approved source, supports one documented plain-Spanish question, and contains no paraphrase, interpretation, eligibility or amount claim, and no inferred applicability; a topic whose current evidence is insufficient produces no passage and is named as an uncovered gap.

### 6. Human approval is the only path to canonical knowledge

Given the prepared package, when prepare runs, then it reports `ready_for_review` only with all checks passing and the reviewed evaluation-case set bound; when a named human other than the proposal author approves, `merge` writes the approved entries and records `reindex_required: true`; on rejection, failed checks, or no decision, the catalog and passage files stay byte-identical and the outcome is recorded.

### 7. Coverage, copy, and guards stay consistent

Given the corpus is widened or narrowed, when the change is published, then `knowledge/pac_coverage.md`, `knowledge/README.md`, the "four sources / three topics" statements, `docs/risks-and-open-questions.md`, and the exact-count corpus guards are updated in the same change; the verdict table carries a stable id and a fixed `added`/`not_added` token so a guard can assert that every added id is cataloged and every not-added id is absent; the pinned Spanish coverage copy and `scripts/validate_coverage_copy.py` expectations change only if a covered or not-yet topic changes, and the copy still contains no deadline, amount, article number, eligibility claim, or invented contact.

### 8. Answer behavior is measured, not assumed

Given newly answerable passages, when the reviewed evaluation runs, then each added passage is retrievable from its own distinctive terms and each newly answerable topic has at least one source-anchored `/ask` case; questions outside the reviewed passages still abstain, and all results stay report-only with no legal-correctness or quality claim.

## Technical approach

- Treat the seed list as up to seven operator-curated candidates. Locate each official original publication and, where the issuer publishes one, the consolidated/corrected text; use only approved issuer hosts and never press, cooperative, blog, or aggregator text.
- Fetch through `backend/scripts/ingest_official_documents.py` into a quarantine outside `knowledge/`. Seed documents are not in a live discovery feed, so an operator-authored seed discovery state supplies official URL, issuer, and observation time; the quarantine preserves original and extracted hashes. If extraction fails, use an official HTML/PDF alternative copy; never OCR or repair text by inference.
- For each document, verify validity, corrections/amendments, campaign scope, and applicability against the official text and record the verdict. Unknown values stay absent; a document whose current status cannot be established is not added.
- Draft catalog entries and literal passages only for admitted documents and provisions whose current wording is verified. Keep the correction as a separate record; when it satisfies the catalog's current-document rule it is its own source. When a passage follows consolidated wording, record the consolidation date in its location and evidence, and do not claim the catalog digest covers that consolidated file.
- Build one `knowledge-update-proposal-v1` proposal (at most 20 candidates) linking every catalog/passage change to its quarantined candidate. Run `knowledge_review.py prepare` with `--cases knowledge/pac_answer_eval.json`, present it to the named reviewer, then `decide` and, only on approval, `merge`. Never hand-edit the canonical files.
- Keep the evaluation addition bounded: extend `knowledge/pac_answer_eval.json` only with the source-anchored cases needed to measure the newly answerable topics, keep its declared coverage/omissions honest, and leave the golden-set growth to its own feature.
- Update the coverage record, counts, and guards; change the pinned disclosure copy only through the existing coverage model and validator. Do not reindex or release here.

## Expected file changes

- `knowledge/source_catalog.json` — written only by `merge`; approved entries for admitted documents.
- `knowledge/passages.json` — written only by `merge`; literal reviewed passages, none for not-added or deferred topics.
- `knowledge/pac_coverage.md` — the seed-review verdict table, updated topics/exclusions, amendment/correction notes, and reviewer/date.
- `knowledge/README.md` — replace the four-source/four-passage statements and document the seed-review and correction/expiry handling.
- `knowledge/pac_answer_eval.json` — only the bounded source-anchored cases for newly answerable topics; no orphaned existing case.
- `backend/tests/test_pac_corpus.py`, `backend/tests/test_source_catalog.py`, `backend/tests/test_retrieval.py` — exact new counts, verdict-table consistency (every added id is cataloged, every not-added id is absent), and retrieval of every added passage; keep the coverage/exclusion guard.
- `shared/src/commonMain/composeResources/values/strings.xml`, `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageContent.kt`, `scripts/validate_coverage_copy.py` — only if the supported-topic list changes; copy and expectation change together.
- `docs/risks-and-open-questions.md`, `PROGRESS.md`, `docs/progress/known-limitations.md` — the corpus boundary, not-added reasons, and residual gaps.
- `docs/specs/seed_corpus_expansion.appendix.md` — the review record and evidence, not a second contract.

## Visual design impact

No new screen, control, or layout. The only possible UI effect is the pinned coverage disclosure, owned by `coverage_and_help`: if a topic moves between covered and not-yet, its Spanish copy, the content model, and the validator expectation change together under `DESIGN.md`'s plain-language and accessibility rules. If no topic moves, no UI change is expected.

## Durable documentation impact

- `ARCHITECTURE.md`: not needed — runtime surfaces, read paths, and boundaries are unchanged; the corpus remains read-only at runtime.
- `docs/constraints/answers-and-knowledge.md`: not needed — the existing Campaign scope, Coverage disclosure, and Knowledge updates rules already require current/unexpired sources, the human merge gate, and same-change disclosure updates. Add a rule only if implementation establishes a new durable invariant.
- `AGENTS.md`: not needed — startup path, workflow, and repo-wide rules do not change.
- `knowledge/pac_coverage.md`, `knowledge/README.md`, `docs/risks-and-open-questions.md`, `PROGRESS.md`, `docs/progress/known-limitations.md`: update with the exact corpus boundary, verdicts, and limits.
- `docs/owner-guide.md`: not needed — no owner-run command changes; rebuilding a local release after a corpus change remains the existing setup procedure.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests -q tests/test_pac_corpus.py tests/test_source_catalog.py tests/test_retrieval.py tests/test_pac_answer_eval.py
backend/.venv/bin/python backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-11-06
python3 scripts/validate_coverage_copy.py
```
<!-- verify:end -->

The validator date is the planning date; if the recorded human approval is later, keep the block runnable and treat the approval-date validator run as the authoritative evidence.

## Appendix

See [`seed_corpus_expansion.appendix.md`](seed_corpus_expansion.appendix.md) for research, plan, evidence, and the validator checklist.
