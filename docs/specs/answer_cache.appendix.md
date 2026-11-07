# answer_cache — appendix

## Repository research

### Files inspected

- `feature_list.json` — the row: `backend`, `not_started`, three accepted dependencies. `nightly_evaluation` depends on this feature.
- `PROGRESS.md` "Current state" — local generation is opt-in and slow (Ollama on loopback). The full local service runs the `development` profile. QA is the `pilot` profile and is not deployed.
- `docs/constraints/answers-and-knowledge.md` — "Answer grounding" names a cache explicitly: discard it whole when `verify_draft` fails. The "Abstention" rule says abstention copy is code-owned.
- `docs/constraints/hosting-and-pilot.md` — pilot logs carry no question or land text. Trace and inspection are allowed only in an explicit `development` profile.
- `docs/constraints/operations.md` — the local start passes an allowlisted environment, so the setting must be passed explicitly. A container command passes only the campaign, so the container gets no setting. `/metrics` carries fixed labels only.
- `backend/app/ask_api.py` — `ask_question` → `_answer`. The order is: year pre-check, `_prepare_runtime_corpus`, `retrieval_backend.attach`, `answer_with_clarification`, then the response builders and `health_metrics.note_answer`. `_load_published_release` already knows `release_id`.
- `backend/app/clarification.py` — `answer_with_clarification` is just `clarify_land_scope` followed by `answer_or_abstain`. This is the seam for the lookup.
- `backend/app/generation.py` — `normalize_text` (lowercase, NFKD, drop combining marks, collapse whitespace) is the key normalizer. Also `verify_draft`, `Answered` (claims with original ranks, plus sources), `to_answer_response`, and the `_render_claim`/`_assemble_claims` helpers.
- `backend/app/retrieval.py` — `tokenize` already folds accents, including ñ→n, so key normalization matches retrieval. Holds `_PassageRecord`, `Retriever._records`, and `indexed_documents()`.
- `backend/app/gemini_generation.py` — `GatedGeminiGenerator.generate` notes one outcome per draft and falls back to extractive. Also `ProviderResolution`, `GatedGeminiProvider`, and `GeminiDraftClient.model`. The outcome constants are the transient-failure list.
- `backend/app/local_generation.py` — `resolve_local_provider` has `record.model` and `record.digest` for `model_version`.
- `backend/app/abstention.py` — `ABSTENTION_REASONS`, `generation_error`, `Abstention.generation_reason`, and `prepare_corpus` (the corpus-level `stale_evidence`).
- `backend/app/main.py` — the `create_app` seams (`answer_trace`, `answer_inspection`), the startup `operational_log`, and `app.state`.
- `backend/app/health_metrics.py` — `FAMILIES`, the `LABEL_NAMES` allowlist (it already has `outcome`), counters initialized to zero, and `note_answer`.
- `backend/app/answer_trace.py` — `parse_setting` and the `ContextVar` hook pattern for a request-scoped note.
- `backend/app/answer_inspection.py` — inspection is on whenever the profile is explicitly `development`, including the full local service. Bypassing the cache when inspection is on would disable it locally, so a hit omits `inspection` instead.
- `backend/app/local_rag_bootstrap.py` — `Settings`, `SETTINGS_TEMPLATE`, and the `read_settings` allowlist with the `MANIJERO_ANSWER_TRACE` precedent.
- `backend/app/local_rag_service.py` — `launch_environment` is an allowlist; trace is passed only when on.
- `backend/app/local_container.py` — passes only `--env MANIJERO_ACTIVE_CAMPAIGN`.
- `backend/app/environment_profiles.py` — the QA `QA_KEYS` allowlist refuses unknown keys. Not changed here.
- `backend/deploy/pilot.env.example` — hosted env template with `MANIJERO_PILOT_WORKERS=2`; commented optional lines are the pattern. `tests/test_container_image_files.py` reads it.
- `scripts/init.sh` — `--feature <id>` runs the verify block. `--backend-tests <targets> -q` runs targeted pytest from `backend/`. No wiring is needed.

### Existing patterns to follow

- Startup-resolved state on `app.state` with a `create_app` keyword seam for tests. Fixed-code startup log line.
- Request-scoped `ContextVar` hooks that never raise (`answer_trace`, `health_metrics`).
- Canonical JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`) before SHA-256.
- Fail-safe setting parse: an unknown value means off, with a `value_invalid` reason.

### Current gaps

- No per-request record of the model outcome reaches `ask_api`. The new hook supplies it.
- No public identity exists for the checkout corpus or the admitted passage set. `admitted_fingerprint()` supplies it.
- `ProviderResolution` exposes the provider name but not the pinned model version.

## Implementation plan

1. `retrieval.py`: add `Retriever.admitted_fingerprint()` (SHA-256 of canonical JSON of every admitted record's fields, ordered by `passage_id`, cached on the instance; `with_ranker` shares it).
2. `gemini_generation.py`/`local_generation.py`: add `model_version` to `GatedGeminiProvider` and set it in both resolvers. Add a `ProviderResolution.model_version` property (`extractive` when no provider).
3. `answer_cache.py`: add the setting parse, `cache_key`, the identity check and flush, TTL with an injected clock (`now - stored_at < ttl`), oldest-first eviction at `max_entries`, the `ContextVar` outcome hook, the eligibility rule, entry types, and hit re-checks.
4. `gemini_generation.py`: call `answer_cache.note_generation_outcome(outcome)` in `generate`.
5. `ask_api.py`: add `release_id` to `CorpusDocuments`. Add a `get_answer_cache` dependency. Add the cache branch in `_answer` (clarify → lookup → `answer_or_abstain` → store). Keep the off path byte-identical. On a hit, call `note_answer` with the stored status and reason and skip `inspection`.
6. `main.py`: add the `answer_cache=` seam, a fresh cache per app, and the startup log line.
7. `health_metrics.py`: add the `answer_cache_lookups_total{outcome}` family, values, zero seeding, and a `note_cache_lookup` hook.
8. `local_rag_bootstrap.py`/`local_rag_service.py`: add the settings key, validation sentence, template line, and the launch pass-through when `off`. Add a commented line to `pilot.env.example`.
9. Tests, then the docs listed in the contract, then run the focused block and `--fast`, then record evidence.

## Verification plan

- `./scripts/init.sh --feature answer_cache`, then `./scripts/init.sh --fast` (full backend suite and offline evaluators). `--verify` is not expected: no shared, contract, or client input changes.
- New tests in `backend/tests/test_answer_cache.py`:
  - `test_normalized_repeat_hits_without_calling_the_generator` — counting fake generator over a fake corpus via `create_app`; case, accent, and whitespace variants.
  - `test_punctuation_wording_and_land_context_changes_miss`.
  - `test_release_corpus_campaign_model_or_retrieval_mode_change_misses_and_flushes`.
  - `test_entry_hits_just_before_and_expires_at_24_hours` — fake clock at T+86_399 and T+86_400.
  - `test_transient_outcomes_and_generation_error_are_not_stored` — parametrized over every non-`used` outcome, plus a 503.
  - `test_model_used_and_extractive_results_are_stored`.
  - `test_failed_reverification_discards_the_entry_whole` and `test_malformed_cached_abstention_is_discarded`.
  - `test_clarification_and_year_precheck_run_before_lookup`.
  - `test_setting_on_off_and_invalid_values` (both profiles) and `test_off_path_uses_answer_with_clarification_unchanged`.
  - `test_question_and_land_values_never_reach_logs_metrics_or_disk` — caplog, the `/metrics` body, a walk of the tmp home and trace folder, and a scan of the cache's fields.
  - `test_hit_omits_inspection_and_keeps_retention_and_trace_behavior`.
  - `test_eviction_keeps_at_most_max_entries` and `test_new_app_starts_empty`.
- Extend: `test_health_metrics.py` (the new family, label values, zero seeding). `test_local_rag_bootstrap.py` (`on|off` accepted, other values refused, template line). `test_local_rag_service.py` (pass-through only when `off`).
- E2E: not added. No client, contract, or routing change. In-process `TestClient` covers the `/ask` flow.

## Evidence to capture

- Focused and `--fast` commands with one-line results, plus the new test count.
- The generator call counts observed in the hit test (1 for two identical requests).
- Confirmation that the off path runs the unchanged `answer_with_clarification` (the test name and result).
- Honest limits: per process and per worker, lost on restart, no container setting, no QA `settings.env` key, not measured on the owner's Mac, no owner walkthrough (owner decision).

## Feature evidence

- `./scripts/init.sh --feature answer_cache`: 528 passed, 1 warning (focused block, 8 files).
- `CI=true ./scripts/init.sh --fast`: backend-tests 2204 passed, 5 skipped; harness-tests 20 passed; all 10 offline checks passed.
- New `backend/tests/test_answer_cache.py`: `test_normalized_repeat_hits_without_calling_the_generator` made 1 counting-transport call for 4 identical-after-normalization requests; `hit` rose by 3 and `answers_total{answered}` by 4.
- Off path: `test_off_path_uses_answer_with_clarification_unchanged` passes (a spy on `ask_api.answer_with_clarification` sees every request; no lookup counter moves).
- 24 h boundary: `test_entry_hits_just_before_and_expires_at_24_hours` (T+86399 hit, T+86400 `expired`).
- Extended: `test_health_metrics.py` (zero-seeded family, label clamp), `test_local_rag_bootstrap.py` (`on|off`, refusals, template line), `test_local_rag_service.py` (pass-through only when `off`).
- Existing tests adjusted for a default-on cache: `test_health_metrics._generation_app` (cache off) and `test_hybrid_retrieval.ask_client` (fresh cache); `test_answer_trace._Resolution` gained `model_version` and `used_outcome`.
- Added beyond the contract: a `HybridRanker` vector fallback marks the request not cacheable (`answer_cache.note_degraded_retrieval`), so a degraded result is never stored.
- Honest limits: per process and per worker, lost on restart, no container setting, no QA `settings.env` key, not measured on the owner's Mac, no owner walkthrough (owner decision 7).

## Validator checklist

- [ ] Every owner decision 1–7 in the contract holds. No disk, log, or metric carries question or land text, and only a key digest is held.
- [ ] The key normalizes exactly case, accents, and whitespace (`normalize_text`). There is no fuzzy or semantic matching.
- [ ] The knowledge identity (release id, admitted fingerprint, campaign) and the model identity (model version, retrieval mode, `k`, `max_claims`) are in the key, and a change flushes the cache.
- [ ] 24-hour expiry is proved with a fake clock at both boundaries.
- [ ] Every non-`used` model outcome, `generation_error`, and every 503 leaves nothing stored.
- [ ] Every hit re-runs `verify_draft` (answers) or the abstention-shape check, and a failure discards the entry whole.
- [ ] Clarification, the year pre-check, and corpus validation run on every request. With the cache off, `/ask` behaves exactly as before.
- [ ] `/metrics` adds only `answer_cache_lookups_total{outcome}` with fixed values. Hits count in `answers_total`.
- [ ] The local settings key works, the container and QA `settings.env` are untouched, and `pilot.env.example` documents the line.
- [ ] The durable docs in the contract are updated within budget. No owner walkthrough is named as the acceptance check.
