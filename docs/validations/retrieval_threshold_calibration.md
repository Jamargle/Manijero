# Acceptance record: `retrieval_threshold_calibration`

- **Verdict: accept** (validator, 2026-11-10, independent; round 2 after round-1 `revise`). Round 1's single defect (Finding 1, docs only) was fixed in `de5c170` and reverified below; no code, evidence, or other check regressed. Spec: [retrieval_threshold_calibration.md](../specs/retrieval_threshold_calibration.md); evidence: [appendix](../specs/retrieval_threshold_calibration.appendix.md) "Feature evidence".
- Recommended minimum search score: **1.5** (today 0.0), advisory only. `/ask` keeps the `score > 0.0` lexical floor; the report is `report_only: true` with `default_changed: false`, and adopting a value is a separate feature. The owner approves the value at acceptance by reading this record.

## Round 2 checks (fix verification)

- `git show --stat de5c170` — 2 files, +2/−2, docs only: the spec's verify-block `git diff` line and the appendix's matching sentence. No code, config, `knowledge/`, or status change; `de5c170` is a new commit on `ad4a1c9`, not an amend.
- Scenario 7 now matches the block: it names `knowledge/`, `backend/config/`, `backend/app/{retrieval,retrieval_backend,ask_api,abstention,main}.py`, and the block (`docs/specs/retrieval_threshold_calibration.md:143`) ends `… backend/app/main.py backend/config/`.
- Corrected third command run verbatim — exit 0, **0 bytes** of output.
- Guard is not vacuous: the same command against a file the branch does change (`backend/README.md`) exits 1, so an empty result is meaningful.
- Appendix line 77 now says the third command gained `backend/app/main.py` and that the corrected command was rerun and was empty — true as rerun here.
- `./scripts/init.sh --feature retrieval_threshold_calibration` — focused tier passed on the corrected block: 3 command lines, 157 tests, sweep exit 0 (18 thresholds, recommended 1.5), merge-base diff empty. `init.sh` runs the block under `bash -euo pipefail`, so the silent third command is enforced.
- Regenerated `report.json` `8881f2a0…dd0667` and `table.md` `953d0d59…b7798d` — identical to the committed evidence and to round 1 (a third byte-identical run); `table.md` is 25 lines; sweep reports 49 golden / 26 traps.
- `git status --short` — only this record is untracked; no stray files. The working tree otherwise equals `de5c170`.

## Round 1 checks (still valid: the fix touched only docs text)

- `./scripts/init.sh --fast` — all 10 offline checks passed; backend 3407 passed, 9 skipped; harness 22 passed.
- `backend/.venv/bin/python -m pytest -q backend/tests/test_threshold_calibration.py` — 31 passed; `test_reranker_measure.py test_trap_set.py test_question_glossary.py` — 126 passed.
- Real sweep twice into fresh `--out` directories — exit 0 each; outputs byte-identical to each other and to the committed evidence.
- Knowledge SHA-256 over all 34 files before/after the runs — unchanged.
- `--out knowledge/...` — exit 2, `error: --out must be outside knowledge/…`, nothing written; missing and malformed inputs — exit 2 with `error: …`, nothing written.
- Zero row: sweep identity check passed; re-run rows at 0.0 equal today's baseline for all 75 items; a forced ranker mismatch stops exit 1 with the pinned line and writes nothing.
- Approved-only: 49 golden and 26 traps scored; synthetic draft/rejected copies excluded from scoring (both reviewed files currently hold zero unapproved items).
- Offline/model-free: socket-guard test passes; no `torch`, `transformers`, `sentence_transformers`, `chromadb`, or `app.hybrid_retrieval` in `sys.modules` after a sweep (`reranker_measure` imports `app.reranker`/`app.embeddings`; their `torch` import is lazy).
- `--verify` not rerun: the diff touches backend evaluation code, docs, and the feature status — no `shared/`, Android, Desktop, Gradle, or packaging files.

## Recommendation (advisory; not adopted)

The report records the spec's rule: eligible when no golden question breaks, no trap gets worse, and golden right sources do not drop below today's count; the eligible threshold with the most trap correct abstentions wins, ties go to the smallest, otherwise 0.0. At 1.5: golden right source 29 (= baseline), broken 0, traps worse 0, trap correct abstentions 18 (> 16). 2.0+ rows are ineligible (broken, worse, or lost sources). Recommended value: **1.5**.

## Trade-off table (`table.md`, 25 lines)

```
# Retrieval threshold trade-off (report only; /ask default unchanged)
| t | G ans | G src | G abst | G broken | T abst | T unexp | T src | T must-not | T worse | note |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 37 | 29 | 11 | 0 | 16 | 3 | 5 | 0 | 0 | eligible |
| 1.5 | 35 | 29 | 12 | 0 | 18 | 1 | 5 | 0 | 0 | recommended |
| 2.0 | 33 | 27 | 12 | 2 | 18 | 1 | 5 | 0 | 0 | loses 2 golden right sources; breaks 2 golden questions |
| 2.5 | 24 | 21 | 12 | 8 | 19 | 0 | 4 | 0 | 2 | loses 8 golden right sources; breaks 8 golden questions; makes 2 trap questions worse |
| 3.0 | 23 | 21 | 12 | 8 | 19 | 0 | 4 | 0 | 2 | loses 8 golden right sources; breaks 8 golden questions; makes 2 trap questions worse |
| 3.5 | 18 | 17 | 12 | 12 | 19 | 0 | 3 | 0 | 4 | loses 12 golden right sources; breaks 12 golden questions; makes 4 trap questions worse |
| 4.0 | 15 | 15 | 12 | 14 | 19 | 0 | 3 | 0 | 4 | loses 14 golden right sources; breaks 14 golden questions; makes 4 trap questions worse |
| 4.5 | 13 | 13 | 12 | 16 | 19 | 0 | 2 | 0 | 5 | loses 16 golden right sources; breaks 16 golden questions; makes 5 trap questions worse |
| 5.0 | 10 | 10 | 12 | 19 | 19 | 0 | 1 | 0 | 6 | loses 19 golden right sources; breaks 19 golden questions; makes 6 trap questions worse |
| 5.5 | 8 | 8 | 12 | 21 | 19 | 0 | 1 | 0 | 6 | loses 21 golden right sources; breaks 21 golden questions; makes 6 trap questions worse |
| 6.0 | 5 | 5 | 12 | 24 | 19 | 0 | 1 | 0 | 6 | loses 24 golden right sources; breaks 24 golden questions; makes 6 trap questions worse |
| 6.5 | 3 | 3 | 12 | 26 | 19 | 0 | 0 | 0 | 7 | loses 26 golden right sources; breaks 26 golden questions; makes 7 trap questions worse |
| 8.0 | 2 | 2 | 12 | 27 | 19 | 0 | 0 | 0 | 7 | loses 27 golden right sources; breaks 27 golden questions; makes 7 trap questions worse |
| 8.5 | 0 | 0 | 12 | 29 | 19 | 0 | 0 | 0 | 7 | loses 29 golden right sources; breaks 29 golden questions; makes 7 trap questions worse |

## Cooperative-practice traps

| id | top score | today | at 1.5 | first acceptable abstention | golden src then |
|---|---|---|---|---|---|
| trap-013 | 2.249 | answered | answered | 2.5 | 21 |
| trap-014 | 1.314 | answered | abstained (no_evidence) | 1.5 | 29 |
| trap-016 | 1.314 | answered | abstained (no_evidence) | 1.5 | 29 |
```

- `trap-014` and `trap-016` become `no_evidence` at 1.5; `trap-013` still answers there and first abstains acceptably at 2.5, where golden right source falls to 21. The recommendation does not fix all three; the cost is recorded, not hidden.
- At 1.5, `golden-024` (expected abstained, previously answered) now abstains correctly and `golden-042` (expected answered, previously wrong source) now abstains. No previously passing golden question broke and right sources stay 29; the table's answered/abstention counts expose the trade-off.

## Findings

### Finding 1 (round 1): published focused block did not check `backend/app/main.py` — **resolved**

- Round-1 evidence: scenario 7 named `backend/app/{retrieval,retrieval_backend,ask_api,abstention,main}.py`, but the `verify` block's third command ended at `backend/config/`; the appendix wrongly said the command covered `main.py`.
- Fix in `de5c170`: the block's `git diff` now lists `backend/app/main.py`, and the appendix sentence (line 77) was corrected to say the command gained `main.py` and was rerun empty. Docs only, no code change.
- Round-2 result: corrected command exits 0 with no output, the guard is proven non-vacuous, and the whole focused tier passes on the published block. Scenario 7's file set and the block now agree; the evidence sentence matches what ran.

### Low notes (not blocking; unchanged by the fix)

- `test_pre_retrieval_routes_never_change_state` covers the input screen and year check by case; the scope guard is not exercised by a case. Code order in `answer_or_abstain` (`scope_abstention` before `corpus.search`) makes it invariant, so scenario 3 holds, but the test is narrower than its name.
- `feature_list.json` still reads `passing` for this feature (spec line 120 assigns the transition to the integrator); it was not set to `accepted` here.
- `table.md` omits 0.5, 1.0, 7.0, and 7.5 because their counts equal the previous row; that matches scenario 4 (verified programmatically against every report row).
- The corrected appendix sentence summarizes the block's scope ("the named `/ask` files") instead of re-listing the five paths; accurate but slightly less self-contained than the surrounding lines.

## Remaining limits

- The result rests on 75 author-reviewed items and BM25 only; hybrid `vector_min_similarity` is uncalibrated, and adoption of 1.5 is pending a separate feature. The recommendation is a trade-off, not a quality or legal claim.
- No behaviour defect found: `Retriever`/`/ask`, `backend/config/`, and `knowledge/` are byte-unchanged, and the evaluation ranker is referenced only by the new module and command.
- Acceptance covers the report-only sweep and its evidence; it does not make 1.5 the `/ask` default. Any later change to the default needs the recorded owner approval and its own verify block.
