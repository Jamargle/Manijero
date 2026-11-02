# Appendix: `answer_pipeline_trace`

Contract: [`answer_pipeline_trace.md`](answer_pipeline_trace.md). This file holds research, plan, and evidence only.

## Repository research

Inspected 2026-11-02 (planner had no shell; nothing was executed):

- `backend/app/pilot_config.py`: the profile source. `_read_profile` maps unset/empty to `development`, accepts `pilot`, and refuses other values with `profile_invalid`. `PilotConfig.pilot` is the only existing flag. This is the basis for "local = exactly `development`".
- `backend/scripts/serve_pilot.py`: the hosted launcher refuses non-`pilot` (`pilot_profile_required`) and runs `app.main:create_app` with workers 1–8. Trace file names must therefore be unique per process.
- `docs/constraints/hosting-and-pilot.md`: the hosted service must start only through `serve_pilot.py`, and the pilot log rule bans question text. The new rule goes here.
- `backend/app/main.py`: `create_app` resolves retention and the generation provider once at startup and puts them on `app.state`. The trace follows the same pattern, using `_RETENTION_FROM_ENV`-style sentinel seams for tests.
- `backend/app/ask_api.py`: the sync `/ask` route calls `_answer(...)` and then `retain_if_opted_in`. `_answer` raises an `HTTPException` 503 for an unavailable corpus, so the route must catch, trace, and re-raise. The year-mismatch abstention returns before retrieval. `REPOSITORY_ROOT = parents[2]` gives the repo root used for `build/answer-traces`.
- `backend/app/retrieval.py`: `Retriever.search` computes `lexical` (BM25 `(id, score)` pairs with score > 0), applies the optional `CandidateRanker`, and builds `RetrievedPassage` (with `passage_id`, `source_id`, `score`, and `rank`). The hook point is after `lexical` and after the candidates.
- `backend/app/hybrid_retrieval.py`: `HybridRanker.rank` already sets `last_trace` (`used_vector`, `fallback_reason`) and has the vector `matches` (`passage_id`, `similarity`) in hand. `HybridBackend.attach` falls back to BM25 silently. Effective mode = `retriever.uses_ranker` after attach.
- `backend/app/clarification.py` / `abstention.py`: `clarify_land_scope` and `answer_or_abstain` may each call `search` (hence "search calls" count; the last call feeds drafting). `Abstention` carries `reason`, `generation_reason`, and `issues` codes.
- `backend/app/generation.py`: `generate_grounded_answer` runs the generator, then `verify_draft` → `GroundingReport(ok, issues, claims)`. `ClaimVerdict(text, markers, ok, issues)`; claim text is never traced separately (it is part of the draft).
- `backend/app/gemini_generation.py`: `GatedGeminiGenerator.generate` computes one fixed outcome code from `_gemini_draft` and logs it. It is shared by `gemini` and `local` (`provider_name`). Extractive is the case where the generator is `None`.
- `backend/app/retention.py`: the purge-before-write precedent and "failures never change the answer"; the store lives outside the repo. The trace deliberately differs (owner decision 3: git-ignored repo folder).
- `backend/app/local_rag_bootstrap.py`: `read_settings` accepts only `MANIJERO_ACTIVE_CAMPAIGN` and gives named-line errors. `SETTINGS_TEMPLATE` is written once with `O_EXCL`, so it never overwrites.
- `backend/app/local_rag_service.py`: `launch_environment` is an exact allowlist; `INHERITED_KEYS` drop every other `MANIJERO_*`. This is why the setting must travel through `settings.env`.
- `backend/container/entrypoint.py`: fixed image environment with no settings file, so tracing is off in the container (a non-goal).
- `.gitignore`: `build` (line 8) already ignores `build/answer-traces/`. No `.gitignore` edit is needed.
- `scripts/init.sh`: `--backend-tests [targets]` runs pytest in `backend/` with `MANIJERO_PYTHON`. `--feature` runs the verify block line by line from the repo root.
- `docs/archive/MasterPlanV3.md` B11/`Tracer`: historical; Langfuse is not adopted (no new dependency).
- Not inspected: test bodies of the existing suites (only their names). The implementer reuses their fixtures.

## Implementation plan

1. `answer_trace.py`, settings and profile:
   - `SETTING_ENV = "MANIJERO_ANSWER_TRACE"`; `parse_setting(value) -> (on: bool, reason: str|None)` (exact `on`/`off`/empty).
   - `LOCAL_PROFILES = frozenset({"development"})`; `text_allowed(profile)`.
   - `DEFAULT_FOLDER = REPO_ROOT / "build" / "answer-traces"`; `RETENTION = timedelta(days=7)`; `SCHEMA_VERSION = "answer-trace-v1"`.
2. `answer_trace.py`, collector:
   - A `TraceCollector` dataclass with stage dicts, and a `ContextVar` holding it.
   - `note_retrieval_lexical`, `note_candidates`, `note_vector`, `note_drafting`, `note_draft`, `note_verification`, and `note_mode`, each wrapped in `try/except Exception: pass`.
   - A monotonic clock for durations.
3. `answer_trace.py`, document:
   - `build_document(collector, text_included)` adds text keys only when allowed and caps the lexical list at 20 and the draft at 4000 characters (`draft_truncated`).
   - `METADATA_KEYS` is the published allowlist of key paths.
4. `answer_trace.py`, writer and purge:
   - `TraceWriter.write(document)` checks that the folder is not a symlink, runs `mkdir(mode=0o700)` plus `chmod`, purges, writes to `tempfile.mkstemp` in the folder with `0600`, then `os.replace`, and unlinks the temp file on failure.
   - `purge(now)` deletes names matching `^\d{8}T\d{6}Z-[0-9a-f]{32}\.json$` whose name time is 7 days or more before `now`.
   - `AnswerTrace(enabled, text_included, writer)` resolved by `load_answer_trace(env, profile, folder, clock)`.
5. `main.py`:
   - Add a `create_app(..., answer_trace=_FROM_ENV)` seam.
   - Purge at startup when the folder exists, in any state.
   - Log `operational_log("answer_trace", state=..., text=included|excluded, reason=...)` and set `app.state.answer_trace`.
6. `ask_api.py`:
   - Add a `get_answer_trace` dependency.
   - The route opens the collector when enabled, records the mode from `retrieval_backend.mode` and `uses_ranker`, and runs `_answer`.
   - On success or `HTTPException(503)`, it notes the outcome and text, writes, catches every trace error (`answer_trace_skipped reason=write_failed|folder_symlink|serialize_failed`), and re-raises the 503 unchanged.
7. Hooks:
   - `retrieval.py` after `lexical` and after the candidates.
   - `hybrid_retrieval.py` in both `rank` branches.
   - `gemini_generation.py` around `_gemini_draft` (provider, outcome, duration).
   - `generation.py` after the draft (status, markers, text) and after `verify_draft` (report, duration). The extractive path notes the provider `extractive` and outcome `used`.
8. `local_rag_bootstrap.py`:
   - `Settings` gains `answer_trace: bool = False`.
   - `read_settings` accepts the key with `on`/`off`, gives the existing named-line errors for other values or a duplicate, and keeps the campaign required.
   - The template adds a commented explanation and `# MANIJERO_ANSWER_TRACE=off`.
9. `local_rag_service.py`: `launch_environment` adds `MANIJERO_ANSWER_TRACE=on` only when `settings.answer_trace`.
10. Tests (below), then documentation per the contract's impact list, then the focused block, then the full `--backend-tests`.

## Verification plan

New `backend/tests/test_answer_trace.py`, named by behavior:

- `test_setting_unset_empty_off_disables_and_creates_no_folder`
- `test_invalid_setting_values_stay_off_and_log_value_invalid` (`On`, `1`, `yes`, ` on`)
- `test_text_allowed_only_for_exact_development` (`pilot`, `qa`, `prod`, `local`, `Development`, ` development`, `""`)
- `test_local_profile_trace_has_text_and_all_stages` (answered via the canonical corpus)
- `test_trace_written_for_abstained_clarification_year_mismatch_and_503` (null stages where skipped)
- `test_pilot_profile_trace_matches_metadata_allowlist_and_omits_marker_bytes` (authenticated `TestClient`, fake digest)
- `test_no_land_values_client_id_token_or_retain_flag_in_any_profile`
- `test_hybrid_trace_records_vector_matches_and_fallback_code` (fake embedder/store from the hybrid tests)
- `test_model_draft_outcome_and_rejected_verification_codes_recorded` (fake transport returning an unsupported draft → fallback)
- `test_responses_identical_with_trace_on_and_off` (parametrized questions, byte compare)
- `test_write_failure_symlink_and_serialize_error_never_change_response_and_leave_no_temp`
- `test_folder_0700_file_0600_name_pattern_and_atomic_replace`
- `test_purge_removes_seven_day_old_keeps_younger_ignores_foreign_names` (boundary at exactly 7 days, injected clock)
- `test_startup_purges_even_when_tracing_off`
- `test_default_folder_is_repo_build_answer_traces`
- `test_draft_text_truncated_at_4000_with_flag` and `test_lexical_list_capped_at_20`

Extend `test_local_rag_bootstrap.py` (optional key accepted, invalid/duplicate named-line errors, template line commented) and `test_local_rag_service.py` (env carries the key only when on; allowlist otherwise unchanged). Existing suites listed in the focused block must pass unchanged, which shows the hooks are read-only.

## Evidence to capture

- The focused block's result line, plus one full `./scripts/init.sh --backend-tests` result line.
- One sample local trace and one pilot trace from the test fixtures, described by key list only (no pasted file).
- `git check-ignore` result; confirmation that `git status` shows no `build/answer-traces` entry.

## Notes for later features

- `environment_profiles` must add its local profile to `LOCAL_PROFILES` deliberately. QA and prod must never be added.
- `rag_inspector_view` consumes `answer-trace-v1` files by `trace_id`. This feature exposes no endpoint.

## Feature evidence

Implementer self-verification, 2026-11-02:

- `./scripts/init.sh --feature answer_pipeline_trace` (focused block): 754 passed, 1 warning; `git check-ignore -q build/answer-traces/<name>.json` succeeded.
- `CI=true ./scripts/init.sh --fast`: all 9 offline checks passed (backend-tests 1766 passed, 4 skipped).
- `./scripts/init.sh --backend-tests` (full): 1766 passed, 4 skipped, 1 warning.
- New `backend/tests/test_answer_trace.py`: 39 tests (setting, profile allowlist, local/pilot documents, 503/year-mismatch/clarification nulls, hybrid vector and fallback code, gated outcome, rejected-verification codes, byte-identical responses on/off, write/symlink/serialize failures, modes 0700/0600, 7-day boundary purge, startup purge when off, caps). Added 6 cases to `test_local_rag_bootstrap.py` and 1 to `test_local_rag_service.py`.
- Sample key lists: local trace = schema, trace_id, created_at, profile, text_included, question, answer, retrieval{mode,k,search_calls,duration_ms,lexical,vector,candidates}, drafting{provider,outcome,status,cited_markers,duration_ms,draft_text,draft_truncated}, verification{ok,issues,claims,duration_ms}, outcome{status,abstention_reason,generation_reason,cited_passage_ids,land_scope,land_choice_count}, total_ms; pilot trace = the same without question, answer, draft_text, draft_truncated (asserted against `METADATA_KEYS`).
- `git status` shows no `build/answer-traces` entry (ignored by the `build` rule; tests use temp folders).
- Not run: `--verify` (no Android/Desktop, Gradle, or packaging change).
- Validator rerun 2026-11-02: focused block 754 passed; `--fast` all 9 passed (1766 passed, 4 skipped); verdict accept ([record](../validations/answer_pipeline_trace.md)).
- Notes: the vector side lists every match the store returned (uncapped, bounded by candidate depth); `drafting.provider` is `null` for an injected non-gated generator.

## Validator checklist

- [ ] Text keys appear only when the validated profile is exactly `development`. The pilot trace key set equals the allowlist, and the marker bytes are absent.
- [ ] Off by default; only exact `on` enables; an invalid value stays off and is logged with a fixed code.
- [ ] Fixed folder `build/answer-traces/`, git-ignored, `0700`/`0600`, atomic; no folder override setting.
- [ ] Purge at startup (even when off) and before every write; the 7-day boundary is tested; foreign files untouched.
- [ ] Responses are byte-identical with tracing on and off; trace failures never change a status or body; no text in the skip logs.
- [ ] No land values, client id, token, IP, issue `detail`, or excerpts in any trace.
- [ ] Hooks change no return values; existing suites pass unchanged; no new dependency; no API contract change.
- [ ] `settings.env` key works through `--local-rag-start`; an existing settings file is never rewritten.
- [ ] Documentation updated per the contract; known limitation recorded (purge only while the service runs).
- [ ] Focused block passes as published; no owner walkthrough required (decision 4).
