# Acceptance record: `reranker_evaluation`

- **Verdict:** accept, condition `pending owner walkthrough` (validator, 2026-11-10). Spec: [reranker_evaluation.md](../specs/reranker_evaluation.md); evidence: [appendix](../specs/reranker_evaluation.appendix.md) "Feature evidence".
- The reranker ships OFF (`default_state: "off"`). The owner's run of `--reranker-download` and `--reranker-measure` is the walkthrough; the real `Result:` line is not yet recorded.

## Checks rerun

- `./scripts/init.sh --feature reranker_evaluation`: 463 passed; `check-pin`: valid (6 files, 2.3 GB, revision 953dc6f6f85a).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend-tests 3312 passed, 9 skipped).
- `--verify` not rerun: no `shared/`, Android, Desktop, Gradle, or packaging change.
- Pin values (revision, sizes, SHA-256, git-blob SHA-1) compared with `build/reranker-metadata.json`: all match. No change under `knowledge/`, `contracts/`, `shared/`, `backend/container/`, `requirements*`.
- Code read: `reranker_measure.py` computes rule 3 exactly (gain >= 2, broken == 0, trap worse == 0, slowest <= 2.0 s) with reasons in the fixed order; BM25 fallback stops with no verdict.

## Remains for the owner run

- Real download passes the `config.json` one-label check; real `torch`/`transformers` load and latency; `bge-m3` plus reranker memory use.
- The real `Result:` line, then rule 3 decides `default_state`.

## Notes

- Owner guide is 61 lines (spec budget 60); plain language, one named command each, on/off explained. Not blocking.
