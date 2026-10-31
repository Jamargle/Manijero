# Validation: chroma_hybrid_retrieval

## Verdict

**Accept** — independently validated against `docs/specs/chroma_hybrid_retrieval.md` on
2026-10-31. No blocking findings. Evidence: the "Feature evidence" section of
[`chroma_hybrid_retrieval.appendix.md`](../specs/chroma_hybrid_retrieval.appendix.md).

## Independently rerun checks

| Check | Result |
|---|---|
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature chroma_hybrid_retrieval` | exit 0; 1036 passed, 1 skipped (real-Chroma module without `chromadb`), 1 pre-existing Starlette/httpx warning |
| `CI=true MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` (Gradle-provisioned Zulu 21 JDK via `JAVA_HOME`) | exit 0; all 9 offline checks passed, including `gradle-jvm-test` |
| `backend/.venv-hybrid/bin/python -m pytest -q -p no:cacheprovider backend/tests` | exit 0; 1047 passed, including 11 real-Chroma tests |
| Real `manage_vector_store.py compare` (bge-m3 pin, `chromadb==1.5.9`, RRF `rrf_k` 60, depth 20) | exit 0, 0 hybrid fallbacks. BM25 and hybrid answer metrics identical: 13/14 states, 11/11 answered, 8/11 source and passage, 9/11 critical literal, 2/3 abstentions. Top-5 recall 10 → 11 of 11; MRR 0.8182 → 0.8409. Matches the appendix |
| Import probe in hybrid venv | `import app.main` loads no `chromadb`, `torch`, `transformers`, vector, hybrid, or embedding module; default backend is BM25; `HYBRID` (wrong case) falls back to BM25 |
| Privacy probe | No case question in compare stderr; tests assert third-party error text with personal data is not logged |
| `git diff` on `contracts/`, `knowledge/`, `shared/` | No changes |

`--verify` was not run: the change has no Android, Desktop, shared, or packaging surface.

## What is accepted

An opt-in (`MANIJERO_RETRIEVAL_MODE=hybrid`) Chroma vector store plus Reciprocal Rank Fusion
ranking, composed through `Retriever.with_ranker`. It preserves eligibility, the BM25 lexical
gate, citation provenance, and the `/ask` contract. Any unavailable, stale, or failing component
falls back to BM25 and logs fixed codes only. BM25 remains the default.

## Notes (non-blocking)

- The spec's focused block runs in the default venv and therefore skips the real-Chroma tests;
  they pass in the hybrid venv.
- Cosmetic: three consecutive blank lines in `backend/app/hybrid_retrieval.py` (lines 56–58).

## Not accepted / honest limits

- No answer-quality or retrieval-quality improvement is claimed: 4 passages, 14 author-reviewed
  cases, one development Mac, untuned fusion parameters.
- Not an owned-server capacity measurement (about 1.97 GB peak RSS, 34 ms median hybrid search,
  about 2.7 s first-request load on the Mac).
- `/ready` does not report hybrid state; a load failure persists until restart; the store needs a
  writable directory; the format is tied to `chromadb==1.5.9`; determinism observed on one host.
- `gradle-jvm-test` passed only with the Gradle-provisioned JDK, not a system JDK.
