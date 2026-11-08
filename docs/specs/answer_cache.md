# Reuse answers keyed by question, land context, knowledge release, and model version

## Source metadata

- `id`: answer_cache · `area`: backend · `depends_on`: local_generation_provider, knowledge_reindex_release, pilot_privacy_readiness · `status` at planning: not_started
- Source: `feature_list.json` title; `docs/archive/MasterPlanV3.md` answer-cache intent (historical only). `nightly_evaluation` depends on this feature.
- User-visible behavior: asking the same question again, with the same lands, returns the same verified answer or abstention quickly, without a new model draft. The response shape does not change.
- Verification: in-process pytest with a fake clock, fake corpus, and a counting fake generator. Commands are in Focused verification.
- Owner decisions (2026-11-03), binding:
  1. In memory only, cleared on every restart. Question text and land context are never written to disk, logs, or metrics.
  2. The key is the question normalized for case, accents, and whitespace, plus the land context, the active knowledge release, and the model version. No fuzzy or semantic matching.
  3. An entry lives until the knowledge release or the model changes, and for at most 24 hours.
  4. Grounded answers and abstentions are cached. Generation errors and other transient failures are never cached.
  5. On by default in local and QA, with a setting to turn it off.
  6. `docs/constraints/answers-and-knowledge.md` applies: a cached answer that no longer verifies is discarded whole.
  7. Acceptance: the validator's accept is final. There is no owner walkthrough.
- Planning decisions (stricter than the owner decisions, never looser):
  - "Active knowledge release" means the served release id (or `repository`) **plus** a SHA-256 of the admitted passage records and the active campaign. A checkout edit or a day-boundary expiry therefore also invalidates.
  - "Model version" means the provider plus the pinned model (`extractive`, `gemini:<model>`, or `local:<tag>@<digest>`) **plus** the request's effective retrieval mode (`bm25`/`hybrid`), `k`, and `max_claims`.
  - The cache holds at most 1,000 entries and evicts the oldest first. Only a SHA-256 digest of the key is held, never the question or the land text.

## Goal

Skip repeated slow model drafts for the same question asked against the same knowledge and model. Never serve an answer that the current corpus and verifier would not produce.

## Non-goals

- Fuzzy, semantic, embedding, or punctuation-insensitive matching. Sharing a cache across processes or workers. Disk, Redis, or any other persistent store.
- Caching land clarifications, the corpus-level `stale_evidence` abstention, the campaign-year pre-check abstention, a 4xx/503 response, or the `inspection` object.
- A setting in the Docker container (`docs/constraints/operations.md` lets a container command pass only the campaign). A QA `settings.env` key, which belongs to `qa_server_deployment`. A client or UI change, an OpenAPI change, or an owner-guide operation.
- Changing grounding, retrieval, clarification, abstention copy, retention, or the trace schema. Changing the evaluation harnesses, which keep calling `answer_with_clarification` directly.

## Job story

When I ask the assistant a question I already asked, with the same lands, I want the same verified answer straight away, so that I do not wait for a slow local model again. I must never get an answer the current sources no longer support.

## Acceptance Scenarios

### 1. A repeat is served from the cache
Given the cache is on and a question was answered (or abstained) with no transient failure · When the same question is sent again with the same land context, differing only in letter case, accents, or runs of whitespace · Then the response is byte-identical to the first one, the generator is not called again, and `manijero_answer_cache_lookups_total{outcome="hit"}` and `manijero_answers_total{status}` each rise by one.

### 2. Anything else in the key misses
Given a cached entry · When the punctuation or wording differs, or the land context differs (mode, a land id, or a land attribute), or the served release id, the admitted passages, the campaign, the model version, or the effective retrieval mode differ · Then the request runs the full pipeline (`outcome="miss"`). A change of knowledge or model identity empties the whole cache.

### 3. Entries expire after 24 hours
Given an entry stored at fake-clock time T · When the same request arrives at T+23:59:59 · Then it is a hit. At T+24:00:00 or later it is not served, it counts as `outcome="expired"`, and it is replaced by a fresh result.

### 4. Transient failures are never cached
Given the model provider is configured · When drafting ends in `rate_limited`, `timeout`, `transport_error`, `redaction_failed`, `payload_invalid`, `malformed_output`, `provider_abstained`, or `verifier_rejected` (an extractive fallback), or the result is a `generation_error` abstention, or the route raises 503 · Then nothing is stored, and the next identical request calls the generator again. A model draft with outcome `*_used`, and every result of the extractive provider, is cacheable.

### 5. A cached answer that no longer verifies is discarded whole
Given a cached answer · When `verify_draft` no longer accepts its stored draft against its stored cited passages (forced in a test), or a cached abstention no longer has the code-owned abstention shape · Then the entry is removed, nothing from it is emitted, it counts as `outcome="discarded"`, and the request returns the fresh pipeline result.

### 6. Clarification and pre-checks run on every request
Given a cached answer for a question in `all_active` mode · When the request's lands now need a choice · Then `needs_land_clarification` is returned exactly as without a cache. The campaign-year pre-check, corpus validation, and the 503 paths also run before any lookup.

### 7. The setting turns it off
Given `MANIJERO_ANSWER_CACHE` is unset, empty, or `on`, in the `development` or `pilot` profile · Then the cache is on. Given `off` · Then no lookup or store happens, `/ask` calls the accepted `answer_with_clarification` path unchanged, and no lookup counter moves. Given any other value · Then the cache is off and startup logs `answer_cache state=off reason=value_invalid`. Given `MANIJERO_ANSWER_CACHE=off` in `~/manijero/local/settings.env` · Then `--local-rag-start` passes it to the service. Any other value in that file is refused with a sentence naming the line.

### 8. Nothing personal leaves memory
Given hits, misses, and stores with a distinctive question and land municipality · Then neither value appears in any log record, the `/metrics` body, a file written under a temporary home or trace folder, or the cache's own fields. Only a key digest and the response are held. A new `create_app` starts with an empty cache. Retention and the trace behave exactly as they would for an uncached response. A hit carries no `inspection` object.

## Technical approach

- New `backend/app/answer_cache.py`, standard library plus `app` only:
  - `AnswerCache(clock=time.monotonic, ttl_seconds=86_400, max_entries=1_000)` behind a lock.
  - `cache_key(...)` returns the SHA-256 of canonical JSON over: `app.generation.normalize_text(question)`, the land context (`model_dump(exclude_none=True)`, keys sorted, lists in request order), the knowledge identity, and the model identity.
  - `load_answer_cache(environ)` reads the setting and returns the cache or `None`.
  - `note_generation_outcome(outcome)` is a request-scoped `ContextVar` hook. It swallows its own errors, like `answer_trace`.
- Lookup site: `ask_api._answer`, only when a cache exists, after the year pre-check, `_prepare_runtime_corpus`, and `retrieval_backend.attach`. Call `clarify_land_scope` first. If it decides, return the clarification. Otherwise look up the key. On a miss, run `answer_or_abstain` with the same arguments `answer_with_clarification` would use, then store the result if it is eligible. This is exactly the existing composition, so nothing is re-implemented.
- Knowledge identity: `CorpusDocuments` gains an optional `release_id` (set by `_load_published_release`). `Retriever` gains a read-only `admitted_fingerprint()`: the SHA-256 of every admitted `_PassageRecord`, ordered by `passage_id`. If the identity differs from the one the cache last saw, the cache empties itself.
- Model identity: `GatedGeminiProvider` gains `model_version`, set at resolution (`gemini:<model>`; `local:<record.model>@<record.digest>`). `None` or an unresolved provider means `extractive`.
- Answered entries keep the response, a re-checkable draft (the kept claims re-rendered with their original candidate ranks), and the cited `RetrievedPassage`s. Every hit re-runs `verify_draft` on them. Abstention entries keep the response and the reason, and a hit re-checks the `ABSTENTION_MESSAGES` shape. Every hit returns a deep copy.
- `GatedGeminiGenerator.generate` calls `answer_cache.note_generation_outcome(outcome)` next to its existing trace and metrics notes. A result is cacheable only when no model outcome was noted, or the only noted outcome is the provider's `used_outcome`.
- `create_app` gains an `answer_cache=` test seam, which defaults to `load_answer_cache(os.environ)`, and logs `answer_cache state=on|off` once at startup.
- `health_metrics`: a new counter `answer_cache_lookups_total{outcome}` with the fixed values `hit|miss|expired|discarded`, initialized to 0. A hit also calls the existing `note_answer` with the stored status and reason. Generation outcomes are counted only when a draft is actually made.
- Local settings: `local_rag_bootstrap` accepts `MANIJERO_ANSWER_CACHE=on|off` and adds a commented template line. `local_rag_service.launch_environment` adds `MANIJERO_ANSWER_CACHE=off` only when the file says `off`.

## Expected file changes

- `backend/app/answer_cache.py`: create.
- `backend/app/ask_api.py`, `backend/app/main.py`, `backend/app/retrieval.py` (`admitted_fingerprint`), `backend/app/gemini_generation.py` (`model_version`, outcome hook), `backend/app/local_generation.py` (local `model_version`), `backend/app/health_metrics.py`: modify.
- `backend/app/local_rag_bootstrap.py`, `backend/app/local_rag_service.py`, `backend/deploy/pilot.env.example` (commented optional line): modify.
- `backend/tests/test_answer_cache.py`: create (scenarios 1–8). `test_health_metrics.py`, `test_local_rag_bootstrap.py`, `test_local_rag_service.py`: extend.
- Docs as listed below.

## Visual design impact

UI involved: no. There is no screen, copy, or `DESIGN.md` change. The response shape is unchanged.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update. One line in the answer path: the per-process in-memory answer cache, where it sits, and its key.
- `docs/constraints/answers-and-knowledge.md`: update. One MUST under "Answer grounding": cache in memory only with a digest key; invalidate on knowledge or model identity change and after 24 h; re-verify every hit and discard it whole; never cache transient failures, clarifications, or `inspection`.
- `docs/pilot-privacy.md`: update. One data-flow row: a key digest and the response are held in memory per process and dropped on restart; no question or land text is kept.
- `backend/README.md`: update. An "Answer cache" section of at most 30 lines, plus a `MANIJERO_ANSWER_CACHE` row in the environment table.
- `docs/progress/known-limitations.md`: update. One line: per process (two pilot workers mean two caches), lost on restart, no container setting, a hit has no `inspection`, `answers_total` includes hits.
- `AGENTS.md`, `CONTEXT.md`, `docs/domain-model.md`, `docs/owner-guide/`, `contracts/openapi.yaml`, `docs/constraints/operations.md`: not needed. There is no workflow, domain, owner operation, contract, or container-rule change.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_answer_cache.py tests/test_ask_endpoint.py tests/test_health_metrics.py tests/test_gemini_generation.py tests/test_local_generation.py tests/test_local_rag_bootstrap.py tests/test_local_rag_service.py tests/test_container_image_files.py -q
```
<!-- verify:end -->

Manual acceptance check: none. The validator's independent rerun of this block and of `./scripts/init.sh --fast` is final (owner decision 7).

## Appendix

See [`answer_cache.appendix.md`](answer_cache.appendix.md) for research, plan, evidence, and the validator checklist.
