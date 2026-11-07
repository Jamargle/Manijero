# Validation: seed_corpus_expansion

- Verdict: **accept** (re-validation after the second reviewed package, 2026-11-07). The earlier revise findings are resolved; the merged corpus is 6 sources and 7 passages and regresses nothing against main.
- Spec: [seed_corpus_expansion.md](../specs/seed_corpus_expansion.md) · Evidence: [appendix](../specs/seed_corpus_expansion.appendix.md) · Packages `8c7b2e22…07b9` then `dfa5f081…`, both approved by Diego.

## Checks rerun
- `./scripts/init.sh --fast`: 10/10 ok; backend 1872 passed, 4 skipped; catalog valid (6 sources).
- `./scripts/init.sh --feature seed_corpus_expansion`: 141 passed; catalog and coverage copy valid.
- `evaluate_pac_answers.py` on this branch vs main, same cases and date: identical headline metrics (state agreement 13/14, source citation 8, critical facts 9, 1 unexpected answer, which is the same case on main). The only difference is that `canal-excepcion-persona-fisica-2026` also cites the Ley 39/2015 passage, and its expected source and passage still match.
- Catalog/passages: rd_1047_2022 (recinto only) and ley_39_2015 (art. 41.1, 109.2) added; retained ids (orden_2023_03_24, parcela passage, alegacion passage) are absent from both artifacts and marked `added, retenido` in the verdict table.
- `--verify` not rerun: no shared, app, Gradle, or packaging change.

## Conditions on the leftovers
- Eval-case extension for the new passages: acceptable follow-up, not blocking. Add it with the next reviewed change, plus an `/ask` abstention check.
- Reindex and release: acceptable follow-up (spec non-goal); `reindex_required: true` stays open.

## Notes (non-blocking)
- `knowledge/pac_coverage.md` still says "Cuatro documentos revisados no se añadieron"; with the 2 retained documents the count of non-added or unpublished is stale. Reword in the next docs touch.
- The retained passages (parcela, alegacion) regressed deadline and channel answers and may return in a later package.

## Limits that remain
- No `/ask` evidence on the new passages; they are retrievable but lack their own eval cases.
- res_20260121, dl_1_2026, and rd_537_2026 expire 2026-12-31; re-review before then.
- Order correction and FEGA news item stay outside the catalog; the 200-signal cap has little headroom.
