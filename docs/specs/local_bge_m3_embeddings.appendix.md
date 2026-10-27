# `local_bge_m3_embeddings` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

Inspected before implementation:

- `backend/app/retrieval.py` is the only retrieval boundary; `Retriever.from_documents` owns catalog/passage eligibility and exposes only eligible passages. `POST /ask` composes it through `app/clarification.py`; `app/ask_api.py` owns the wire model and status codes.
- `backend/requirements.txt` is deliberately small (FastAPI/Uvicorn/httpx); `backend/requirements-dev.txt` adds pytest/jsonschema. `torch` is too large to add to either.
- `scripts/init.sh` is the verification harness; the spec's focused block is the backend pytest suite, and `--fast` runs it with the other offline checks.
- `app/document_ingestion.py` and `app/review_package.py` already keep derived/operator artifacts outside `knowledge/` and use fixed error codes; this feature follows those patterns.

## Implementation plan

1. Inspect the current owning modules, schemas, and focused command before changing code.
2. Implement the capability behind a narrow interface with explicit configuration and fail-closed behavior.
3. Add representative and adversarial fixtures, including malformed, stale, duplicate, unavailable, and ambiguous cases as applicable.
4. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Implementation notes

- `backend/app/embeddings.py` owns the closed `embedding-model-v1` pin
  (`backend/config/bge_m3_embedding.json`), the SHA-256/size/immutable-revision
  artifact gate, the `EmbeddingModel` protocol, CLS/mean pooling, L2
  normalization, and the optional `LocalBgeM3Embedder`. The hub offline flags are
  forced before the runtime import; the runtime is imported lazily; errors carry
  fixed codes and never the embedded text.
- `backend/app/embedding_index.py` owns the derived
  `passage-embedding-index-v1` file: build from `Retriever.indexed_documents()`
  (eligibility is not re-implemented), atomic write, refusal under `knowledge/`,
  closed validation, cosine search, and `up_to_date`/`stale`/`invalid`/`missing`
  freshness with named reasons.
- `backend/app/retrieval.py` gained one read-only accessor,
  `Retriever.indexed_documents()`, returning `(passage_id, text)` for passages
  that already passed the catalog/passage gates. `search` is unchanged, and
  `POST /ask` neither imports nor reads the embedding modules.
- `backend/scripts/manage_embeddings.py` is the operator entry point:
  `verify` (with optional `--measure`), `build`, and `check`. Exit codes follow
  the repository convention: `0` success, `1` pin/index mismatch, `2`
  unreadable/invalid input or unavailable runtime.
- `backend/requirements-embeddings.txt` pins the optional runtime exactly
  (`torch==2.14.1`, `transformers==5.21.0`, `tokenizers==0.23.3`,
  `huggingface-hub==2.3.0`, `safetensors==0.8.0`, `numpy==2.5.4`).
- `backend/tests/test_embeddings.py` adds 72 focused tests over synthetic
  four-dimension fixtures; the default suite still runs without `torch`.
- Operator lifecycle, failure recovery, and measured limits are in
  `backend/README.md`; the durable boundary is in `CONSTRAINTS.md`; the module
  map is in `ARCHITECTURE.md`.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

### Environment and bootstrap

Host: macOS on Apple M1 Max, 32 GiB RAM, 468 GiB free disk at the start,
Python 3.14.5 (`/usr/local/bin/python3`), repository worktree
`local_bge_m3_embeddings`.

`backend/.venv` did not exist. Bootstrapped with the runtime and development
requirements (the harness's pytest discovery prefers `MANIJERO_PYTHON`, then
`backend/.venv/bin/python`):

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
# -> fastapi 0.162.0, pytest 8.x, jsonschema 4.x, httpx
```

The optional embedding runtime was installed separately, so the default backend
and test environment stay small:

```sh
python3 -m venv backend/.venv-embeddings
backend/.venv-embeddings/bin/python -m pip install torch==2.14.1 transformers==5.21.0
# additionally resolved and now pinned exactly in requirements-embeddings.txt:
# tokenizers 0.23.3, huggingface-hub 2.3.0, safetensors 0.8.0, numpy 2.5.4
```

`.venv-embeddings` is ignored by `.gitignore` (`.venv-*/`). It is not part of the
delivered application and contains no secrets.

### Artifact provenance and pin

Hugging Face metadata for `BAAI/bge-m3` (`GET https://huggingface.co/api/models/BAAI/bge-m3?blobs=true`,
fetched 2026-10-27) recorded: commit `5617a9f61b028005a4858fdac845db406aefb181`,
`lastModified` 2024-07-03, license `MIT`, dense `pytorch_model.bin` 2,271,145,830
bytes with LFS SHA-256 `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`.
`config.json` declares `hidden_size: 1024`, `max_position_embeddings: 8194`;
`1_Pooling/config.json` declares `pooling_mode_cls_token: true`. The pin in
`backend/config/bge_m3_embedding.json` records the commit (a branch/tag is
rejected), all nine required files with size and SHA-256, 1024 dimensions, CLS
pooling, L2 normalization, `float32`, 8192-token bound, and batch 8.

The exact revision was downloaded into an operator directory outside the
repository (`${TMPDIR}/bgem3-download`, `du -sh` = 2.1 GiB) with `curl -fL` for
each of: `config.json`, `tokenizer.json`, `tokenizer_config.json`,
`special_tokens_map.json`, `sentencepiece.bpe.model`, `1_Pooling/config.json`,
`modules.json`, `config_sentence_transformers.json`, `pytorch_model.bin`.

Verification without loading the model:

```sh
backend/.venv/bin/python backend/scripts/manage_embeddings.py verify \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$TMPDIR/bgem3-download" --json
```

Actual output:

```json
{
  "artifact": {
    "checked_files": 9,
    "ignored_bytes": 0,
    "ignored_files": 0,
    "issues": [],
    "verified_bytes": 2293315747
  },
  "command": "verify",
  "config_sha256": "b1bc262bb8140978a529aafa0348cb9f2a3eabc6ad619398cbf5ff3e94ec6565",
  "license": "MIT",
  "model_id": "BAAI/bge-m3",
  "model_revision": "5617a9f61b028005a4858fdac845db406aefb181"
}
```

`check` on the real corpus needs no model and reported `up_to_date` after the
index build below; a missing index reports `missing` (exit `1`), and a changed
passages digest reports `stale` with `passages_changed` (covered by unit tests).

### Observed host measurements (real, not models or estimates)

Command (two fixed neutral Spanish sentences, three repetitions, 8 torch threads):

```sh
/usr/bin/time -l backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py verify \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$TMPDIR/bgem3-download" --measure --json
```

Actual measurement block from the final run:

```json
"measurement": {
  "determinism_max_abs_diff": 0.0,
  "device": "cpu",
  "dimension": 1024,
  "dtype": "float32",
  "embed_seconds": [0.0766, 0.0767, 0.077],
  "load_seconds": 4.908,
  "max_ms": 77.02,
  "max_tokens": 8192,
  "median_ms": 76.74,
  "min_ms": 76.6,
  "normalized": true,
  "p95_ms": 77.0,
  "peak_rss_mb": 1943.4,
  "pooling": "cls",
  "repetitions": 3,
  "texts_per_run": 2,
  "threads": 8,
  "verified_bytes": 2293315747
}
```

`/usr/bin/time -l` for that run reported `maximum resident set size
2037841920` bytes (1,943 MiB) and 7.25 s wall clock. An earlier first run on the
same host (cold page cache) reported `load_seconds: 9.509`, 11.88 s wall clock,
and `peak_rss_mb: 1942.6`; load time varied, the embedding latency did not. The
optional runtime environment is 928 MB (`du -sh backend/.venv-embeddings`); the
default `backend/.venv` is 60 MB.

Not measured: model load or embedding on the owned server, GPU/half-precision,
long documents, an answer-path latency budget, or any retrieval-quality
comparison against BM25. The two probe sentences are not legal passages.

### Derived index rebuild

```sh
backend/.venv-embeddings/bin/python backend/scripts/manage_embeddings.py build \
  --config backend/config/bge_m3_embedding.json \
  --artifact "$TMPDIR/bgem3-download" \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --as-of 2026-10-27 --active-campaign 2026 \
  --index "$TMPDIR/manijero-embedding-index.json" --json
```

Actual output (index path shortened): 4 indexed passages from 4 eligible
sources, 0 excluded, dimension 1024, `embed_seconds: 0.621`,
`peak_rss_mb: 2014.1`, index file 124,691 bytes, index SHA-256
`c8c821639a5ff6eaa23372a5a8f1f64a0f40ff1ebc4c6b2e98f1b3fb58c0a349`, input
digests `catalog_sha256 e9d87ef0…`, `passages_sha256 ac01d564…`, `as_of
2026-10-27`, campaign `2026`.

```sh
backend/.venv/bin/python backend/scripts/manage_embeddings.py check \
  --config backend/config/bge_m3_embedding.json \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --as-of 2026-10-27 --active-campaign 2026 \
  --index "$TMPDIR/manijero-embedding-index.json" --json
```

Actual output: `"state": "up_to_date"`, `"reasons": []`, exit `0`. The index
contains passage ids and 1024-float vectors only; unit tests assert passage text
is absent from the serialized file, and a write refused inside `knowledge/`.

### Verification gates actually run

Focused block from the spec contract:

```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
```

Actual tail: `854 passed, 1 warning in 12.34s` (the warning is Starlette's
pre-existing `httpx` TestClient deprecation notice). No failure. Re-run after
the final freshness/dtype/finite-vector checks: `854 passed, 1 warning in
12.48s`. The harness tier that executes the published block,
`./scripts/init.sh --feature local_bge_m3_embeddings`, also passed:
`854 passed, 1 warning in 11.93s`.

Repository no-device gate:

```sh
./scripts/init.sh --fast
```

Actual tail: all 9 offline checks passed — `gradle-jvm-test`, `contract-examples`,
`backend-tests`, `source-catalog`, `retrieval`, `generation`, `abstention`,
`clarification`, `land-safety` — ending with `Fast tier passed.` The five
evaluators still report the pre-existing fixture metrics; nothing in this
feature changed retrieval or answer behavior.

The full `./scripts/init.sh --verify` tier was not run: this change touches only
backend Python, backend documentation, and configuration/fixtures. It contains no
Android/Desktop/shared, packaging, or wire-contract change, and `--fast` already
covers the backend suite and evaluators. That is a scope judgment, not a claim
that the Android/Desktop build gate passed for this change.

`backend/.venv-embeddings` is not used by the gates; `--fast` deliberately runs
the default suite without `torch`.

### Failure behavior covered by focused fixtures

`backend/tests/test_embeddings.py` (72 tests) covers: closed configuration
(unknown/missing keys, branch revision, non-HTTPS URL, bad dimension/pooling/
dtype/batch, unsafe or duplicate file paths, missing `config.json`), artifact
checksum/size/missing-file/escape/symlink/dimension/pooling/context failures,
missing directory, pooling and normalization math, masked mean pooling, a
missing optional runtime, forced offline flags before import, no-network
embedding, blank/non-string input, an `encode_failed` failure that does not echo
input text, duplicate/blank index documents, query dimension/zero-vector
failures, closed index validation (schema/count/digest/vector), stale reasons,
missing/invalid index, atomic write without a leftover temporary file, refusal
of a `knowledge/` index path, CLI exit codes, and a subprocess check that
importing `app.main` does not import `app.embeddings` or `app.embedding_index`.

### Privacy

No question, land record, personal value, or passage text is written to an
exception message, a console report, or the index. The measurement console
prints only the model identity, counts, timings, and memory. The artifact lives
outside the repository; the derived index in this evidence run lives in the
temporary directory and was not committed. No secrets were used: the download is
an unauthenticated public artifact.

### Honest limits

- Only this development host and four synthetic/approved passages were measured.
  The owned server, long legal documents, concurrency, and a per-user latency
  budget are unmeasured.
- The pin records the upstream `MIT` license and revision; that is provenance,
  not a qualified legal review of model or training-data terms.
- `float32` CPU is the only supported configuration. Cross-platform bit-identical
  vectors are not claimed; determinism was observed on one host (`0.0` maximum
  difference over three runs).
- No retrieval-quality, Spanish legal-coverage, or answer-quality claim follows
  from a successful verify/build/check. Embeddings remain off `/ask`; comparing
  bge-m3 (and Chroma/RRF) with BM25 is `chroma_hybrid_retrieval`'s decision.
- The artifact is not committed and has no built-in garbage collection; the
  operator owns storage, retention, and backup.
- Verification counts but does not remove extra files in the artifact directory.
  The loader hands that directory to `transformers`, so an unpinned file with a
  recognized name would be outside the pin; operators should keep only the
  pinned files there.
