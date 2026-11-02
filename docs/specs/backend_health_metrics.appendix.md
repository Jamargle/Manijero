# backend_health_metrics — appendix

## Repository research

### Files inspected

- `backend/app/main.py` — `create_app` builds the app, adds `PilotGuardMiddleware`, `/health`, `/ready`, the unhandled-exception handler; `/metrics` and the registry wiring go here.
- `backend/app/pilot_guard.py` — pure ASGI guard; `GATED_PATHS = {"/ask"}`, in-memory per-client `RateLimiter`, `_reject` and `log_request` call sites already know route, status, duration, and gate.
- `backend/app/pilot_config.py` — profiles `development` and `pilot`; `authentication_required` only in `pilot`; `client_for_token` (constant-time digest match).
- `backend/app/environment_profiles.py` — local = profile `development`, QA = profile `pilot`.
- `backend/app/readiness.py` — `evaluate_readiness` and the four fixed problem codes.
- `backend/app/ask_api.py` — `/ask` route, `_answer` outcomes (answered, abstained, clarification), 503 path, `_note_release_outcome` with the last `(release_id, state, reason)`.
- `backend/app/abstention.py` — `ABSTENTION_REASONS`, the fixed nine-code taxonomy.
- `backend/app/gemini_generation.py` — `GatedGeminiGenerator.generate` logs one fixed outcome per draft; `OUTCOMES` list; shared by the local provider.
- `backend/app/local_generation.py` — `PROVIDER_LOCAL = "local"`, `OUTCOME_LOCAL_USED = "local_used"`.
- `backend/app/answer_trace.py` — `ContextVar` collector and `_safe` hook idiom to mirror; stdlib-only.
- `backend/app/pilot_logging.py` — pilot request log fields; unchanged by this feature.
- `backend/app/knowledge_release.py` — `RELEASE_ID_PATTERN = ^[0-9a-f]{16}$`.
- `backend/app/source_update_scheduler.py` — `status_for_state_dir` / `evaluate_status` (alerts `stale:<job>`, `jobs[*].last_success_at`, `healthy`, `freshness_claim: none`); the service does not know the state folder today.
- `backend/requirements.txt` — only fastapi, uvicorn, httpx; no metrics library.
- `docs/constraints/operations.md` (Monitoring) and `docs/constraints/hosting-and-pilot.md` — privacy and pilot access rules the feature must keep.
- `backend/README.md` "Local answer service" — the local start passes an allowlisted env without any state-folder key.
- `scripts/init.sh` `run_feature` — extracts the verify block unchanged.
- `ARCHITECTURE.md` line 17 — the backend endpoint list.

### Existing patterns to follow

- Hooks that must never affect an answer are module-level, `_safe`-wrapped, and route to a request-bound `ContextVar` (`answer_trace`).
- Fixed, value-free codes only; never echo configuration, paths, or tokens (`pilot_config`, `readiness`).
- Routes take corpus, date, and campaign through `Depends` so tests use `app.dependency_overrides` (`/ready`).
- Backend focused checks run through `./scripts/init.sh --backend-tests <files> -q` with `MANIJERO_PYTHON` defaulted (accepted `answer_pipeline_trace`).

### Current gaps

- No metrics endpoint, registry, or library exists.
- The source-update state folder is not known to the service; this feature adds the opt-in read key only (non-goal: wiring it into start commands).
- Sync routes run in a thread pool; the `ContextVar` set by the middleware is copied into it by Starlette, so mutating the bound registry works. Confirm this with a test rather than assuming it.

## Implementation plan

1. Write `test_health_metrics.py` covering the format grammar and the label allowlist first (scenario 1, the label part of 8).
2. Create `health_metrics.py`: registry, fixed allowlists with an `other` clamp, histogram, `render()`, `bind`/`note_*` hooks, freshness reader.
3. Wire `create_app`: registry per app, service and provider info, pass to middleware, `GET /metrics` (`include_in_schema=False`, readiness via the `/ready` dependencies).
4. Extend `PilotGuardMiddleware`: bind the registry per request, record response and duration at both `log_request` sites, record rejections in `_reject`, gate `/metrics` with a per-path limiter window.
5. Add the answer hook in `ask_question`, the release-outcome accessor in `ask_api`, and the generation hook in `GatedGeminiGenerator.generate`.
6. Add scenario tests 2–8 with fake clients, fake transports (see `test_gemini_generation.py` and `test_local_generation.py` fixtures), fake release roots, and fake ledgers under `tmp_path`.
7. Update `ARCHITECTURE.md`, `docs/constraints/operations.md`, `backend/README.md`, and `docs/progress/known-limitations.md` per the contract.
8. Run the focused block and the full backend suite, then record the evidence.

## Verification plan

- Focused block via `./scripts/init.sh --feature backend_health_metrics` — all listed pytest files pass.
- `./scripts/init.sh --backend-tests` — full backend suite passes (no regressions in other guard or route tests).
- Tests named by behavior: `test_metrics_open_in_development_profile`, `test_metrics_text_format_grammar`, `test_metrics_pilot_requires_client_token`, `test_metrics_scrape_does_not_consume_ask_allowance`, `test_answer_status_and_abstention_reason_counted`, `test_ask_latency_histogram_cumulative`, `test_http_errors_and_gate_rejections_counted`, `test_unhandled_exception_counted_as_500`, `test_generation_used_and_fallbacks_counted`, `test_extractive_provider_info_only`, `test_readiness_gauges_follow_corpus`, `test_release_info_served_refused_repository`, `test_source_updates_unconfigured_configured_unreadable`, `test_metrics_carry_no_user_text_land_or_client_values`, `test_unknown_route_clamped_to_other`, `test_failing_hook_never_changes_answer`, `test_registry_isolated_between_apps`.
- E2E: not needed. No client, UI, or client-contract change, and the in-process TestClient exercises the real middleware and route stack. `monitoring_dashboard` will read a live service.

## Evidence to capture

- Focused block result (one line) and full backend suite result (one line).
- One redacted sample of `/metrics` output family names only (no values needed), to confirm the published family list.
- Confirmation that `requirements.txt` is unchanged.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-02 (implementer):
- `./scripts/init.sh --feature backend_health_metrics` (focused block): 469 passed, 1 warning (24 new tests in `test_health_metrics.py`).
- `./scripts/init.sh --backend-tests` (full suite): 1855 passed, 4 skipped.
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed.
- `/metrics` families published (prefix `manijero_`): service_info, generation_provider_info, process_start_time_seconds, ready, readiness_problem, http_requests_total, request_duration_seconds, request_rejections_total, answers_total, abstentions_total, generation_outcomes_total, knowledge_release_info, source_updates_configured, source_updates_readable, source_updates_healthy, source_update_stale, source_update_last_success_timestamp_seconds.
- `backend/requirements.txt` unchanged (no metrics library); `test_requirements_stay_free_of_a_metrics_library` guards it.
- Not run: `--verify` (no Android/Desktop, Gradle, or packaging change); E2E not needed per the verification plan.
2026-11-02 (validator): accept — `--feature` 469 passed; `--fast` all 10 checks passed. Record: `docs/validations/backend_health_metrics.md`.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no dashboard, owner command, start-command wiring, or new dependency).
- [ ] Acceptance scenarios 1–8 pass, with evidence.
- [ ] Every label name is in the allowlist and every value is fixed or a 16-hex release id; no user, land, client, or token value in output.
- [ ] `/metrics` is open only in `development`, needs a valid client token in `pilot`, and scrapes do not consume `/ask` allowance.
- [ ] Hooks cannot alter `/ask` responses; `/health`, `/ready`, `/ask` behavior and `contracts/openapi.yaml` unchanged.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature backend_health_metrics`.
- [ ] Durable documentation impact followed; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
