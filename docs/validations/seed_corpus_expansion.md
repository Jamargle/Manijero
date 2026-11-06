# Validation: seed_corpus_expansion

- Verdict: **accept**, conditional on the owner decision required by scenario 6 (independent validator, 2026-11-06). The prepared review package is spec-conformant and reproducible; the approval, merge, and post-merge deliverables are the only open items. No repair the implementer could have made is outstanding.
- Spec: [seed_corpus_expansion.md](../specs/seed_corpus_expansion.md) · Evidence: [appendix](../specs/seed_corpus_expansion.appendix.md) · Package `8c7b2e22c5cb10c2a02a5b303f67e92ebe192dd077f7b4d2cb29e324ee3907b9`.
- Canonical knowledge unchanged: `git diff --quiet knowledge/` exit 0; `source_catalog.json` `e9d87ef0…243a`, `passages.json` `ac01d564…da3e`.

## Checks rerun
- `./scripts/init.sh --feature seed_corpus_expansion`: exit 0; 141 passed; catalog valid (4 sources as of 2026-11-06); coverage copy 20 keys. Published block is accurate and runnable.
- `./scripts/init.sh --fast`: exit 0; 10/10 checks, including Gradle JVM tests, contract examples, 1872 backend tests (4 skipped), 20 harness tests, and all five offline evaluator checks.
- Fresh `knowledge_review.py prepare` into a scratch workspace: exit 0, same package id and byte-identical package JSON/REVIEW.md; `ready_for_review`, 0 blocking reasons, 61 passed / 0 failed / 1 report-only, reviewer `Diego`, author automation, 14 cases bound, 5 affected cases report-only.
- After-state recomputed from canonical + proposal via the package's own `_apply_section`: hashes `27c7c896…b41d` / `a4d026ad…a074` match the package; `validate_source_catalog.py` on that after-state exits 0 with 7 sources as of 2026-11-06.
- `tests/test_change_impact.py`: 57 passed.
- `--verify` not rerun: the diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging file.

## Independent review
- Verdict table: 7/7 seed publications have one `added`/`not_added` outcome, URL, issuer, date, digest, and basis. All 7 SHA-256 values match the quarantined originals; the 3 `added` ids are in the proposed catalog and the 4 `not_added` ids appear in no catalog or passage entry.
- Passages: each of the 5 new excerpts is an exact substring of its reviewed copy (0 U+FFFD); locations resolve to the stated article, and the two BOE excerpts also appear verbatim in the consolidated copies. The Order PDF copy is correctly rejected (12,987 U+FFFD) in favour of the official HTML.
- Retrieval: 5/5 new passages rank first for queries using their own distinctive terms. With unconstrained phrasing, 4/5 do; “¿Cómo me notificará la administración?” returns nothing because of morphology (`notificara` ≠ `notificaciones`). The passage is retrievable from its indexed terms; the upcoming eval case must say so.
- Boundary: the out-of-scope amount question retrieves nothing before and the `recinto SIGPAC` definition at a low score (1.37) after. `/ask` abstention on the merged corpus is unmeasured and is a post-reindex check, not a current defect.
- Security/privacy: no findings. No new network path, secret, personal data, or runtime write; approved hosts only; ingestion stays operator-only.
- Documentation: appendix is accurate and the spec is unchanged. `pac_coverage.md`, `README.md`, guards, risks/limitations, and the evaluation set still describe the 4-source merged corpus, which is correct while no merge exists. ARCHITECTURE, CONSTRAINTS, AGENTS, and DESIGN correctly untouched.

## Scope deviations (accepted)
- `backend/app/change_impact.py` 50 → 200 signals: justified. Re-running the analyzer at the old bound marks the RD 1047/2022 (103 signals) and Ley 39/2015 (77) candidates `size_limit_exceeded`, which fails `candidate_impact` and blocks `ready_for_review`; at 200 both analyse cleanly. The change is the constant, one inclusive-bound regression test, and two README lines; no other live document states 50 (the archive appendices are historical). Acceptable.
- `scripts/validate_coverage_copy.py` adds `ChatHomeScreen.kt`: justified. `coverage_open` is defined in `strings.xml` and rendered only at `ChatHomeScreen.kt:387`; without that source the guard fails with `missing references: {'coverage_open'}`, with it all 20 keys resolve. No expectation or Spanish copy changed, and the archived `coverage_and_help` record already says the guard should include this navigation copy. Acceptable.
- Both repairs must be named in the feature PR so the owner sees them as supporting changes, not corpus facts.

## Conditions and follow-up (owner)
1. A named human other than the proposal author (requested `Diego`) must personally confirm the 7 verdicts, the 5 literal passages, and the proposed `reviewed_by`/`reviewed_on`; the package deliberately pre-fills `reviewed_by: Diego` only so the after-state validates and flags this as a reviewer question.
2. Deadline: the after-state fails the catalog validator after 2026-12-31 because `res_20260121`, `dl_1_2026`, and `rd_537_2026` expire then. Approve and merge before that date; if later, re-review those sources first.
3. If the approval date differs from 2026-11-06, set `reviewed_on` to it, rerun `prepare` (new package id and after-hashes) and `validate_source_catalog.py … --as-of <approval date>`, then `decide` approve and `merge --cases knowledge/pac_answer_eval.json`; confirm `reindex_required: true` and the written files match the package after-hashes.
4. After merge, in the same reviewed change: move the verdict table into `knowledge/pac_coverage.md`; update `knowledge/README.md` (4→7 sources, 4→9 passages); update the exact-count and added-cataloged/not-added-absent guards in `test_pac_corpus.py`, `test_source_catalog.py`, `test_retrieval.py`; update risks/limitations/PROGRESS. Change the pinned copy, `CoverageContent.kt`, and the guard expectation only if a topic moves. Do not reindex or release.
5. Extend `knowledge/pac_answer_eval.json` with at least one source-anchored case per newly answerable topic, update its counts, rerun the PAC evaluation, and confirm the three boundary cases still abstain. Ordering limit: `prepare` loads `--cases` against the before-state (`review_package.py:1257`) before the after-state check, so unmerged passage ids cannot be bound in this package; the implementer's deferral is technically forced and the extension belongs immediately after merge, reviewed by the same person.
6. Keep the feature `in_progress` until the merge and step 4 land; this record accepts the pre-approval package, not the merged corpus.

## Limits that remain
- No `/ask` answer or abstention evidence on the merged corpus; the retrieval probe is lexical only.
- No merge, reindex, or release. Consolidated copies remain comparison evidence; catalog digests cover originals.
- The Order correction and FEGA news item stay outside the catalog; later corrections/consolidations must be reread before any passage is added.
- The 200-signal bound has little headroom: the RD 1047/2022 consolidation copy already produces 192 signals, so a future consolidation could exceed it and must be re-checked rather than silently capped.
