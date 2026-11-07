# Index reviewed structured chunks for BM25 and vector search, rebuilt from the reviewed catalog with one command

## Source metadata

- `id`: structured_chunk_index · `area`: knowledge · `depends_on`: legal_structure_chunker, chroma_hybrid_retrieval, knowledge_reindex_release (all accepted) · `status` at planning: not_started
- User-visible behavior: none by default. A developer runs one offline command that turns reviewed `legal-chunk-set-v1` artifacts into a derived structured index (a `passage-set-v1` corpus, its BM25 fingerprint, and optionally a `bge-m3` embedding index plus Chroma store) outside `knowledge/`. Only with an explicit off-by-default flag, in the local development environment or the QA environment, do `/ask` and `/ready` read that index instead of the canonical or released passages.
- Verification: offline pytest with fixtures and fakes, a two-root CLI rebuild diff, and a CLI fail-closed check; commands in Focused verification.
- Notes (owner decisions, 2026-11-07, fixed):
  1. Index only human-reviewed structured chunks (from `legal_structure_chunker` output that passed the existing named-human review rule) for BM25 and vector search, using the existing `chroma_hybrid_retrieval` stack and its existing local embeddings: no new model, no network, no paid service.
  2. One named command rebuilds the structured-chunk index deterministically from the reviewed catalog, ends with one plain `Result:` line, and fails closed on malformed or unreviewed input.
  3. `/ask`, retrieval, readiness, and release behavior stay unchanged by default. The structured index is used for answers only when a local/QA flag is turned on (off by default; never on in pilot/prod).
  4. Validity metadata comes only from reviewed source/catalog metadata; unknown stays unknown.
  5. Tests run offline with fixtures.
  6. Developer-only: no owner-guide step.
  7. Acceptance: validator accept is final; no owner walkthrough.
- Orchestrator readings of the 2026-11-07 owner decisions (fixed, 2026-11-07):
  1. Review gate is document-level approval through the existing named-human catalog review rule. A chunk set's `source_sha256` must equal the `content_sha256` of an `approved` catalog entry with a named `reviewed_by`, and that catalog must be bound to human-approval evidence through the release builder's existing `approval_from_options` (a matching `merge.json` or a recorded reviewed Git baseline). There is no per-chunk review flow.
  2. Flag scope: QA is identified by `MANIJERO_ENVIRONMENT=qa`, following the precedent in `privacy_review.py` and `environment_profiles.py`. The flag takes effect only when `MANIJERO_ENVIRONMENT=local` with `MANIJERO_DEPLOYMENT_PROFILE=development`, or when `MANIJERO_ENVIRONMENT=qa` exactly. Any other or unset environment (pilot, prod, unknown) ignores it, failing closed. The default is off everywhere. No QA settings file, deployment script, or `init.sh` mode changes; the flag simply becomes usable in QA.
  3. Fail closed on the whole build: any malformed, unreviewed, unstructured, or failed document in the supplied root refuses the build.

## Goal

Make reviewed, article-scale chunks searchable through the accepted BM25 and Chroma/RRF machinery for local experiments. Each chunk carries the approved source, an honest heading-and-page location, and only catalog validity. The default answer path, readiness, and releases stay byte-for-byte what they are today.

## Non-goals

- No change to the default retrieval mode, `/ask` wire contract, `contracts/openapi.yaml`, generation, verification, abstention, or the answer cache's key shape.
- No chunk-level review flow, no new `review_status`, no change to the review merge or canonical `knowledge/` data; at most one schema file is added under `knowledge/`.
- No release-builder change. Releases stay built from canonical catalog plus passages, and release gates keep forcing the canonical corpus.
- No new model, runtime pin, dependency, download, network call, or paid service. Vectors come only from the existing pinned `bge-m3` artifact and `chromadb==1.5.9`.
- No mixing with reviewed passages: with the flag on, the request corpus is the structured passage set alone.
- No retrieval- or answer-quality claim, and no BM25-vs-structured comparison: no committed real chunk set exists.
- No `scripts/init.sh` mode and no change to container, deployment scripts, QA settings files, or environment profiles; the flag only becomes usable when a developer sets it. No `docs/owner-guide.md` step.

## Job story

When reviewed official documents have been parsed and chunked by article, I want one offline command that rebuilds a searchable index from only the reviewed chunks, and a local switch to ask questions against it. Then I can try structured retrieval without touching what the pilot or the default service answers from.

## Acceptance Scenarios

### 1. Reviewed chunk sets become a deterministic structured index

Given a chunks root whose `chunks-manifest.json` lists only `chunked` documents, each with `validity_status: "known"` and a `catalog` block matching an `approved` entry in the supplied catalog, plus approval evidence bound to that catalog · When `manage_structured_index.py build` runs with `--as-of` and `--active-campaign` · Then the output holds:
- `source_catalog.json`: the exact catalog bytes;
- `structured-passages.json`: valid `passage-set-v1`, with one passage per chunk, `id` = chunk id, `source_id` = catalog `source_id`, `text` = the chunk text verbatim, and `location` = chunk `location` plus `, pág. N` or `, págs. N-M`;
- `bm25-index.json`: produced by `release_gates.bm25_fingerprint`;
- `structured-index-manifest.json` (`structured-chunk-index-v1`), written last.

Stdout ends with exactly one `Result:` line naming the chunk and document counts, and the command exits `0`. A second build into another root is byte-identical, and a rebuild into the same root reports unchanged and rewrites nothing.

### 2. Validity is copied, never inferred

Given a reviewed chunk set · Then no passage carries `critical`, `applicability`, or `official_deadline`. Title, dates, applicability, criticality, campaign, and expiry come from the catalog entry through the unchanged `Retriever`, and no value is read from chunk text. Given a chunk set whose `catalog` block differs from the current catalog entry in any copied field or in `catalog_sha256` · Then the build is refused (`chunk_validity_mismatch`).

### 3. Malformed or unreviewed input fails closed

Given any of the following, the build exits `1` with one fixed code, prints a `Result:` line saying nothing was written, and leaves an existing index byte-identical:
- a manifest entry that is not `chunked`, or whose chunk set has `validity_status: "unknown"` (`unreviewed_chunk_set`);
- a chunk set that fails the strict `legal-chunk-set-v1` reader, or whose bytes or id prefix mismatch the manifest (`invalid_chunk_set`);
- a duplicate chunk id (`duplicate_chunk_id`);
- zero chunks (`no_reviewed_chunks`);
- a catalog that fails `validate_catalog` at `--as-of` (`invalid_catalog`);
- missing, ambiguous, invalid, or mismatched approval evidence (the `approval_*` / `merge_record_invalid` codes);
- a `corpus_security.scan_canonical` finding on the derived corpus (`corpus_security`).

### 4. Unsafe roots and usage errors abort before writing

Given an output root under `knowledge/`, equal to or inside the chunks root, or an existing directory that is not a structured index; a missing chunks root or catalog; or more than 1,000 chunk sets or 20,000 chunks · Then the command exits `2` with a `Result:` line and writes nothing. Given `--embedding-artifact` without the hybrid runtime or with an artifact that fails the pin · Then it exits `2` and writes nothing.

### 5. Vectors use the existing local stack only

Given `--embedding-artifact` (and optionally `--embedding-config`) · When the build runs · Then `embedding-index.json` (`passage-embedding-index-v1`) and `vector-store/` (`chroma-passage-store-v1`) are built by the existing `embedding_index` and `vector_store` writers from `structured-passages.json`, and the manifest records their digests. Without the option, the manifest records `vectors: null`. No code path downloads or calls a network service.

### 6. The service is unchanged unless the flag is on in local development or QA

Given `MANIJERO_STRUCTURED_INDEX` unset or `off`, in any environment · Then `/ask` and `/ready` read today's canonical or release corpus unchanged.

Given `on` with `MANIJERO_STRUCTURED_INDEX_DIR` set, and either `MANIJERO_ENVIRONMENT=local` with `MANIJERO_DEPLOYMENT_PROFILE=development` (local-on) or `MANIJERO_ENVIRONMENT=qa` exactly (qa-on) · Then each request reads the catalog and passages from that verified index instead of the checkout or `MANIJERO_KNOWLEDGE_RELEASE_ROOT` corpus, and `/ask` builds the normal `Retriever` from them. The release root itself is not read, changed, published, or rolled back. With `MANIJERO_RETRIEVAL_MODE=hybrid` and `MANIJERO_VECTOR_STORE` set to `<index>/vector-store`, the unchanged hybrid freshness rule applies.

The service ignores the flag, keeps today's corpus path, and logs one fixed reason in each of these cases:
- `MANIJERO_ENVIRONMENT` is unset, `prod`, any other value, or `local` without the `development` profile; this covers a pilot-profile service outside QA (`structured_index_environment_refused`);
- the value is not `on` or `off` (`structured_index_setting_invalid`);
- the directory is missing (`structured_index_not_configured`).

### 7. A broken or stale index never answers

With the flag effective, given a missing or tampered file, an invalid manifest, or an index whose catalog hash differs from the catalog the service would otherwise serve (the verified `current` release catalog when `MANIJERO_KNOWLEDGE_RELEASE_ROOT` is set, otherwise the checkout's `knowledge/source_catalog.json`) · Then the request takes the existing generic corpus-unavailable path and logs a fixed code only (`structured_index_invalid`, `structured_index_stale`). Release gates and `pilot_ops` still read only the canonical corpus. Importing the service still imports neither `chromadb`, `torch`, nor the embedding modules. `manage_structured_index.py check` reports `up_to_date`, `stale`, or `invalid` in one `Result:` line and exits `0` or `1`.

## Technical approach

- New `backend/app/structured_chunk_index.py`, stdlib plus `app.*` at import. It owns:
  - the strict chunk-set and chunk-manifest reader, which reuses the chunker's version and key constants;
  - the review gate (catalog join plus `knowledge_release.approval_from_options`);
  - the passage mapping;
  - an atomic staging-then-swap writer, modelled on `vector_store.write_store`;
  - the manifest, `verify_index`, and `index_status`;
  - the lightweight request loader `structured_corpus_from_environment(environ) -> CorpusDocuments | None`.

  `release_gates`, `embedding_index`, `embeddings`, and `vector_store` are imported lazily inside `build` only.
- CLI `backend/scripts/manage_structured_index.py` has two subcommands:
  - `build --chunks --catalog --as-of --active-campaign --output (--merge-record --passages | --reviewed-baseline-revision) [--embedding-artifact [--embedding-config]]`;
  - `check --index --catalog`.

  Exit `0`/`1`/`2` as in the scenarios. The last stdout line is always one plain English `Result:` line. Reports carry fixed codes and counts, never chunk text, and never a reviewer name; the approval block keeps the release builder's minimized shape.
- Manifest (`structured-chunk-index-v1`, canonical sorted-key JSON, LF, no timestamp or absolute path) holds:
  - `builder`;
  - `inputs`: `catalog_sha256`, `chunk_manifest_sha256`, a sorted `chunk_sets` list (`candidate_id`, `source_id`, `source_sha256`, `chunk_set_sha256`, `chunk_count`), `as_of`, and `active_campaign`;
  - `approval`;
  - `files` (`sha256`, `bytes`);
  - `counts`;
  - `vectors` (model pin plus `documents_sha256`/`vectors_sha256`, or `null`).

  The shape is published in `knowledge/structured-chunk-index.schema.json`.
- `backend/app/ask_api.py`: `load_corpus_documents()`, on its default no-path branch, asks the loader first, before the release-root branch. The loader's environment gate reads `MANIJERO_ENVIRONMENT` and `MANIJERO_DEPLOYMENT_PROFILE` with exact string matches and allows only `local`+`development` or `qa`. A refused or ignored setting returns `None` and logs once per state change through `operational_log`, so the existing path runs. An effective but broken index returns `CorpusDocuments(load_error=True)`. Nothing else in `/ask`, `retrieval_backend`, or `hybrid_retrieval` changes. The answer cache stays correct because its key already includes the admitted fingerprint.

## Expected file changes

- `backend/app/structured_chunk_index.py`: create (reader, gate, mapping, writer, manifest, verify, loader).
- `backend/scripts/manage_structured_index.py`: create (CLI `build`, `check`, exit codes, `Result:` line).
- `backend/app/ask_api.py`: update `load_corpus_documents` only.
- `knowledge/structured-chunk-index.schema.json`: create (manifest contract, no data).
- `backend/tests/test_structured_chunk_index.py`: create (scenarios 1–7, offline, fake embedder and in-memory store writer).
- `backend/tests/test_structured_chunk_index_chroma.py`: create (one real-Chroma build plus `check --deep`-equivalent, skipped without `chromadb`).
- `backend/tests/fixtures/structured_chunk_index/chunks/`: create (chunker output for the reviewed fixture candidate only; regenerate if the chunker changes).
- Durable docs as listed below.

## Visual design impact

UI involved: no. The citation location suffix `, pág. N` / `, págs. N-M` appears only with the flag on in local development or QA.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update. One line beside the chunker line: structured index, its builder, and the local-development/QA-only flag.
- `docs/constraints/answers-and-knowledge.md`: update. One MUST under "Knowledge updates and retrieval": the index is derived and lives outside `knowledge/`; it is built only from chunk sets joined to approved catalog entries bound to approval evidence; it fails closed and copies validity only from the catalog; it is read for answers only with the flag in `MANIJERO_ENVIRONMENT=local`+`development` or `MANIJERO_ENVIRONMENT=qa`, and is ignored in every other or unset environment; it is never read by release gates or the review merge.
- `knowledge/README.md`: update. One Files row for the schema, plus a qualifier on "only reviewed passages ... are ever searchable" naming the flag-only structured index (local development and QA).
- `backend/README.md`: update. One section of at most 30 lines: command, layout, review gate, flag variables, refusal codes, and the hybrid pairing.
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update. One line: honoured only in local development and QA, source-level review only (chunk text not separately reviewed), no quality comparison, and extractive answers may quote the `[título · ruta]` prefix.
- `AGENTS.md`, `docs/owner-guide.md`, `contracts/openapi.yaml`, `DESIGN.md`, `CONTEXT.md`, `scripts/init.sh`, environment and container files: not needed. The feature is developer-only and changes no wire format, UI, domain, workflow, or owner command.

## Focused verification (required)

<!-- verify:start -->
```sh
PY="${MANIJERO_PYTHON:-backend/.venv/bin/python}"
MANIJERO_PYTHON="$PY" ./scripts/init.sh --backend-tests tests/test_structured_chunk_index.py tests/test_embeddings.py -q
CAT=backend/tests/fixtures/legal_structure_chunker/source_catalog.json
REV=0123456789abcdef0123456789abcdef01234567
OUT=build/structured-index-check
rm -rf "$OUT"
for root in first second; do "$PY" backend/scripts/manage_structured_index.py build --chunks backend/tests/fixtures/structured_chunk_index/chunks --catalog "$CAT" --reviewed-baseline-revision "$REV" --as-of 2099-06-01 --active-campaign 2099 --output "$OUT/$root"; done
diff -r "$OUT/first" "$OUT/second"
"$PY" backend/scripts/manage_structured_index.py check --index "$OUT/first" --catalog "$CAT"
"$PY" backend/scripts/chunk_legal_documents.py --documents backend/tests/fixtures/legal_structure_chunker/documents --catalog "$CAT" --output "$OUT/mixed-chunks"
! "$PY" backend/scripts/manage_structured_index.py build --chunks "$OUT/mixed-chunks" --catalog "$CAT" --reviewed-baseline-revision "$REV" --as-of 2099-06-01 --active-campaign 2099 --output "$OUT/refused"
test ! -e "$OUT/refused"
```
<!-- verify:end -->

The last two commands prove the fail-closed rule on the CLI: the mixed root holds one unreviewed document. No owner walkthrough (owner decision). The implementer also runs the full `./scripts/init.sh --backend-tests` once, and `tests/test_structured_chunk_index_chroma.py` in the hybrid venv when it exists, recording each as one line of evidence.

## Appendix

See [`structured_chunk_index.appendix.md`](structured_chunk_index.appendix.md) for research, plan, open questions, evidence, and the validator checklist.
