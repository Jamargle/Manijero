# `knowledge_reindex_release` acceptance

## Verdict

**Accepted** on 2026-10-31 after independent validation. No revise round was needed.

## Independent verification

- `./scripts/init.sh --feature knowledge_reindex_release` passed offline in the shared
  `backend/.venv` (exit 0, about 14 s). The full backend suite gave **1346 passed, 2 skipped**.
  The skips are `test_vector_store_chroma.py` and `test_knowledge_release_chroma.py`, both
  `importorskip("chromadb")`. No virtualenv was created and nothing was downloaded.
- `git diff --stat HEAD` is empty for `contracts/`, canonical `knowledge/*.json`, `retrieval.py`,
  `hybrid_retrieval.py`, `vector_store.py`, `embedding_index.py`, `answer_eval.py`,
  `review_package.py`, `pilot_ops.py`, `backend/requirements*`, and `scripts/init.sh`. The
  `ask_api.py` change is limited to the opt-in read seam and the change-only log record.
  `knowledge/knowledge-release-manifest.schema.json` passes `Draft202012Validator.check_schema`.
- Validator CLI probes in a throwaway root (deleted afterwards). The canonical `knowledge/` hashes
  were unchanged after the probes.
  - Release ids reproduced the implementer's: `aa97b66716f31e37` for `as_of` 2026-10-13 and
    `07e2689c6999b406` for 2026-10-31.
  - Refusals:
    - no approval evidence gives `approval_evidence_required`, exit 2, with no root created;
    - a root inside `knowledge/`, or the repository root itself, gives `unsafe_release_root`.
  - Publish and rollback:
    - publish A, then B, records `previous_release_id`;
    - republishing B gives `already_current`;
    - rollback returns to A, and a second rollback gives `no_previous_release`, exit 1;
    - `rollback --to` an unknown id or `../releases` gives `release_not_found`, exit 2;
    - a held lock gives `release_locked`, exit 2;
    - a not-ready `--as-of` gives `corpus_not_ready:corpus_unavailable`, exit 1, with `current`
      unchanged;
    - a tampered release gives `integrity_mismatch`: exit 2 on publish, exit 1 on `verify`.
  - A failed-gate candidate (catalog cut to one source) gave `corpus_not_ready:…`,
    `evaluation_failed`, `passage_source_unresolved`, exit 1. Publish and `rollback --to` that
    id both gave `gate_failed`, exit 2. The release log held only the four successful events.
- Service seam probes (`ask_api.load_corpus_documents`):
  - with `MANIJERO_KNOWLEDGE_RELEASE_ROOT` set, the published release is served;
  - the explicit path seam ignores the variable;
  - `current` pointing at the failed-gate release, or outside `releases/`, gives `load_error`;
  - an empty variable falls back to the checkout's `knowledge/`.
- Code review confirmed that `release_gates.evaluation_app` mounts the unchanged `ask_api.router`
  with overrides for:
  - corpus, `as_of`, campaign, and `k`;
  - `get_retrieval_backend` set to `Bm25Backend`;
  - `get_generation_provider` and `get_retention_store` set to `None`;
  - `app.state` generation and retention set to `None`.
  BM25, extractive generation, and no retention are therefore forced whatever the environment.
  `test_gate_ignores_environment_knobs_and_never_opens_a_socket` covers this with hybrid/local
  env exported and sockets refused.
- `CI=true ./scripts/init.sh --fast` was not rerun: the feature changes no Kotlin, and the
  backend suite already ran in full. The implementer's run shows a JDK-only failure that passed
  with the cached Zulu 21 `JAVA_HOME`. That is an agent-host environment issue, not a feature
  defect.

## Accepted scope

- `backend/app/knowledge_release.py` (stdlib-only) provides:
  - the closed `knowledge-release-v1` manifest with a content-addressed id;
  - hash verification;
  - staging-then-rename writes, with the manifest written last;
  - the `O_CREAT|O_EXCL` lock;
  - an atomic `os.replace` of the relative `current` symlink, which is reverted if the log
    append fails;
  - an append-only log;
  - `status`, `verify` (with a BM25 rebuild), and `compare`;
  - the opt-in `load_published_corpus` read path.
- `backend/app/release_gates.py` runs, in order: structural checks, a double BM25 fingerprint,
  grounding plus evaluation through the unchanged `/ask` router, and per-case no-regression
  against the published release. It also handles optional vector packaging.
- `backend/scripts/knowledge_release.py` provides `prepare`, `publish`, `rollback`, `status`,
  `verify`, and `compare`, with fixed-key output and the 0/1/2 exit convention.
- Accepted deviations:
  - The evaluation gate uses a minimal in-process app instead of `create_app(load_config(...))`,
    because importing `app.main` reads the operator environment. The overrides are equivalent.
  - Added fixed codes: `cases_orphaned`, `code_revision_invalid`, `active_campaign_invalid`,
    `approval_evidence_invalid`, `input_unreadable`, `vector_options_incomplete`,
    `embedding_config_invalid`, `log_unreadable`, `bm25_mismatch`, `release_unreadable`.
  - Rollback without `--to` returns to the release that the current release replaced at its
    latest publish, and refuses a second bounce with `no_previous_release`.
  - `feature_list.json` was set to `passing` by the implementer, as the orchestrator asked.

## Honest limits

1. Rehearsed only locally (temporary roots, loopback uvicorn). No host, systemd unit, tunnel,
   or off-host backup of a release root has been exercised.
2. The Chroma packaging path (`--embedding-index … --with-vector-store`) and
   `test_knowledge_release_chroma.py` were never executed. No hybrid environment exists, and
   building one needs PyPI downloads that the owner's no-external-call rule forbids. Only the
   fail-closed paths (`embedding_index_stale:…` and `vector_runtime_unavailable`, both with
   nothing written) are verified in the default environment. The spec places the hybrid tests
   outside the contract block.
3. `--reviewed-baseline-revision` and `--code-revision` are recorded operator assertions. The
   tool does not check them against Git.
4. Old releases are never garbage-collected. A lock file left behind by a killed process must be
   removed by hand; the README does not yet say so.
5. A hybrid backend keeps its loaded store until restart, so after a publish with changed
   documents it answers with BM25.
6. The evaluation is the 14-case author-only sample. A passed gate is not a legal-coverage,
   answer-quality, or freshness claim.

## Follow-up (non-blocking)

- When a hybrid environment exists, run:
  `MANIJERO_PYTHON=backend/.venv-hybrid/bin/python ./scripts/init.sh --backend-tests tests/test_knowledge_release_chroma.py tests/test_vector_store_chroma.py tests/test_hybrid_retrieval.py`.
  Record the result in the appendix.
- Add one README line on clearing a stale `<root>/.release.lock` after confirming that no
  publish or rollback is running.
- Rehearse publish and rollback on the attested host before relying on them.
