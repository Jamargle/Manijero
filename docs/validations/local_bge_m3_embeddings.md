# Validation: local_bge_m3_embeddings

## Verdict

**Accept** — independently validated against `docs/specs/local_bge_m3_embeddings.md`
on 2026-10-27. No Critical, High, or Medium findings. Four Low notes are recorded
below; none blocks acceptance.

## Independently rerun checks

| Check | Result |
|---|---|
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests` | exit 0, `854 passed, 1 warning in 11.98s` (rerun `12.11s`); warning is the pre-existing Starlette `httpx` TestClient deprecation |
| `./scripts/init.sh --feature local_bge_m3_embeddings` | exit 0, `854 passed, 1 warning in 12.11s`; the tier executes the published block, it does not print it |
| `./scripts/init.sh --fast` | exit 0, "All 9 offline checks passed." / "Fast tier passed." |
| `./scripts/init.sh --verify` | exit 0, fast tier plus Android host tests and the Android/Desktop builds (`BUILD SUCCESSFUL`). The appendix skipped this tier; I ran it because it was cheap once Gradle was warm, and it passes |
| `git diff --check` | exit 0 |

## Artifact, pin, and measurement claims re-derived

The evidence artifact still existed at `${TMPDIR}/bgem3-download`, so the recorded
numbers could be re-measured instead of trusted.

- **Per-file digests.** Independent `shasum -a 256` over all nine files matches
  every `sha256` in `backend/config/bge_m3_embedding.json`, including
  `pytorch_model.bin` = `b5e0ce34…6aad38` and 2,271,145,830 bytes.
- **Total size.** The nine pinned sizes sum to exactly 2,293,315,747 bytes, which
  is what `verify` reports (`checked_files: 9`, `issues: []`, `du -sh` = 2.1G).
  The claimed byte count is therefore not invented; it is the pin sum and the
  on-disk artifact.
- **Config digest.** `verify --json` reproduces `config_sha256`
  `b1bc262bb8140978a529aafa0348cb9f2a3eabc6ad619398cbf5ff3e94ec6565`, matching the
  appendix and the index.
- **Index.** `check` on the real corpus with the default (no `torch`) interpreter
  reports `up_to_date`, `reasons: []`, exit 0. The index file is 124,691 bytes with
  SHA-256 `c8c82163…58c0a349`, exactly as recorded.
- **Reproducibility.** An independent `build` into a fresh path produced a
  **byte-identical** index (same SHA-256), 4 indexed passages from 4 eligible
  sources, 0 excluded, dimension 1024, `embed_seconds: 0.603` (appendix 0.621),
  `peak_rss_mb: 2016.0` (appendix 2014.1).
- **Host measurements.** Two independent `verify --measure` runs on the same host
  (Apple M1 Max, 32 GiB, Python 3.14.5, 8 torch threads) produced load 4.75–4.86 s
  (appendix 4.908 warm), two-text latency median 74.27–76.50 ms / max 74.31–77.05 ms
  (appendix 76.74 / 77.02), `peak_rss_mb` 1939.1–1941.6 (appendix 1943.4),
  `/usr/bin/time -l` max RSS 2,035,875,840 bytes (appendix 2,037,841,920), and
  `determinism_max_abs_diff: 0.0` on both runs. `du -sh` gives 928 MB for
  `.venv-embeddings` and 60 MB for `.venv`, as stated.
- Installed optional runtime matches `backend/requirements-embeddings.txt`
  exactly: `torch 2.14.1`, `transformers 5.21.0`, `tokenizers 0.23.3`,
  `huggingface-hub 2.3.0`, `safetensors 0.8.0`, `numpy 2.5.4`.
- `backend/tests/test_embeddings.py` collects **72** tests, as claimed, and the
  default suite runs without `torch`.

Sub-second and few-megabyte differences are host and page-cache noise on the same
machine; they reproduce the recorded shape and are acceptable. No appendix number
was found fabricated or inconsistent with artifacts on disk.

## Contract, default behavior, and fail-closed evidence

- **`/ask` wire contract unchanged.** `contracts/` is unmodified (`git status`
  clean) and `backend/app/ask_api.py`, `app/main.py`, `app/clarification.py`,
  `app/generation.py`, `app/abstention.py` are untouched. The only production edit
  is one read-only accessor, `Retriever.indexed_documents()`; `search` is unchanged.
- **Default answer behavior unchanged.** Importing `app.main` in the default
  environment leaves `app.embeddings`, `app.embedding_index`, and `torch` out of
  `sys.modules`. A `POST /ask` with `contracts/examples/ask-request-all-lands.json`
  returns `200 answered` with the reviewed SGA passage citation and the orientative
  notice, in the default `.venv` that has no `torch`.
- **Strictly optional / off by default.** `torch`/`transformers` are only in the
  separate, git-ignored `.venv-embeddings`; neither `requirements.txt` nor
  `requirements-dev.txt` changed, and no gate uses the embedding environment.
- **Fail-closed, verified by hand (not only by tests):**
  - missing artifact directory → `artifact_dir: directory_missing`, exit 1;
  - artifact missing seven pinned files → seven `file_missing` issues, exit 1;
  - tampered `config.json` → `size_mismatch` plus `dimension_mismatch` and
    `context_too_small`, exit 1;
  - pin with `model_revision: "main"` → `config_invalid`, exit 2;
  - `--measure` in the default venv → `runtime_unavailable: install
    backend/requirements-embeddings.txt`, exit 2;
  - `LocalBgeM3Embedder.load` on the tampered directory raises `artifact_invalid`
    before any text is embedded and does not echo file contents;
  - index freshness: `missing` exit 1, `as_of_changed` stale exit 1,
    `active_campaign_changed` stale exit 1, malformed file `index_malformed` /
    `invalid` exit 1.
- **No writes under `knowledge/`.** `git status --porcelain knowledge contracts` is
  empty after all runs. `write_index_atomic` refuses both
  `knowledge/embedding-index.json` and `knowledge/sub/x.json` with
  `unsafe_index_path` and creates nothing. The 2.1 GiB artifact and both index
  files live in `${TMPDIR}`, outside the repository.
- **Privacy.** Grep of the diff found no secret, key, token, or real personal/land
  value; the only match is the synthetic `"secret personal detail: parcela de Juan"`
  used by a test that asserts the `encode_failed` message omits the text. The
  serialized index contains only the schema, the pin, digests, and passage ids plus
  unit-length vectors (inspected: no excerpt, no `text`/`excerpt` keys). The CLI
  prints fixed codes, counts, timings, and memory only.
- **Corpus unchanged.** No canonical catalog/passage/schema edit; the feature adds
  no answerable knowledge and makes no retrieval-quality claim.

## Security review

Diff-scoped review found no Critical/High issue: no committed secret, no network
client (hub access is forced off and `local_files_only=True`/`trust_remote_code=False`
are set), closed config/index validation, path-traversal and symlink-escape guards,
an index path refusal under `knowledge/`, fixed error codes, and an optional
runtime kept out of the delivered requirements. Notes, not findings: an attacker
with write access to the operator artifact directory could swap a file between
`verify` and `from_pretrained` (TOCTOU; no privilege boundary crossed in this
slice), and `_load_runtime` sets the `HF_*_OFFLINE` variables process-wide, which
is the intended offline lock.

## Scope and durable documentation

Only the files the spec anticipates changed: `backend/app/embeddings.py`,
`backend/app/embedding_index.py`, `backend/scripts/manage_embeddings.py`,
`backend/config/bge_m3_embedding.json`, `backend/requirements-embeddings.txt`,
`backend/tests/{test_embeddings.py,fixtures/embeddings/}`, a one-method addition in
`backend/app/retrieval.py`, `.gitignore`, `backend/README.md`, `ARCHITECTURE.md`,
`CONSTRAINTS.md`, `PROGRESS.md`, `docs/risks-and-open-questions.md`, the appendix,
and this feature's own `status` in `feature_list.json`. No other feature's spec or
status changed, and `AGENTS.md` stayed short and router-like. `ARCHITECTURE.md`
adds one boundary row, `CONSTRAINTS.md` adds three operational MUST rules that match
the code, and `backend/README.md` covers setup, pin, download/verify, measure,
build/check, rebuild, failure recovery, and limits. `PROGRESS.md` and
`docs/risks-and-open-questions.md` repeat the same measured numbers with the same
"development host only" caveat. No commit, push, or PR was created; `.local-run.log`
was left untouched.

## Low notes (non-blocking)

1. `backend/README.md` lists the staleness reasons but omits `dtype_changed`, which
   `index_status` does emit. Add it to the list so operators see every reachable
   reason.
2. Index freshness is bound to the pin and to catalog/passages/`as_of`/campaign
   digests only; a change to the eligibility *rules* with byte-identical corpus
   files would not report the index stale. `chroma_hybrid_retrieval`, which will
   consume it, should decide whether to record an eligibility/code version.
3. `write_index_atomic` uses a fixed `<name>.tmp` sibling, so two concurrent builds
   to the same path would collide; the README does not state the single-writer
   assumption the other operator tools state.
4. `PROGRESS.md` says "a derived passage-embedding index now exist[s]"; the index is
   an operator artifact outside the repository, as the appendix says. Wording only.

## Accepted scope and residual uncertainty

Accepted: a pinned `BAAI/bge-m3` revision (`5617a9f…`, MIT) behind a replaceable
`EmbeddingModel` protocol; SHA-256/size/revision artifact verification with forced
offline loading; a derived, atomically written, `knowledge/`-refusing
`passage-embedding-index-v1` with explicit freshness states; an operator CLI; and
focused tests/fixtures. Embeddings remain off `/ask`; no retrieval-quality or
Spanish legal-coverage claim is validated here.

What this does not establish: owned-server capacity, long-document or per-answer
latency, concurrency, GPU/half-precision behavior, cross-platform bit-identity, a
qualified review of the model license or training-data terms, or any BM25
comparison. The artifact has no garbage collection and is owned/backed up by the
operator; verification counts but does not remove unpinned extra files in the
artifact directory. Comparing bge-m3 (and Chroma/RRF) with the accepted BM25
baseline remains `chroma_hybrid_retrieval`'s decision.

See [`local_bge_m3_embeddings.appendix.md`](../specs/local_bge_m3_embeddings.appendix.md)
for the planning research, implementation notes, and raw evidence.
