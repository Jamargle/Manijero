# Feature Spec: `answer_pipeline_trace`

## Source metadata

- **Feature:** `answer_pipeline_trace` — Record a privacy-safe per-question trace of retrieval, ranking, drafting, and verification for local debug use (`backend`).
- **Status at planning:** `not_started`; depends on accepted `backend_ask_endpoint`, `chroma_hybrid_retrieval`, `local_generation_provider`, `pilot_privacy_readiness`. Consumer: `rag_inspector_view` (client, later).
- **Source behavior:** the feature-list title plus the owner decisions below. No earlier spec or discovery record defines more.
- **Feature-list verification:** none recorded; this spec's focused block is the verification.
- **Feature-list notes (owner decisions 2026-11-02, binding):**
  1. The trace may include question text and answer text **only** when the backend runs with the local profile; in any non-local (QA/prod) setting text must never be recorded — only ids, scores, timings, and verification outcomes.
  2. Tracing is off by default and turned on by one local setting.
  3. Traces are written to a git-ignored local folder and deleted automatically after 7 days.
  4. The independent validator's accept is final; no owner walkthrough is required.
- **"Local profile" (planner definition, fail closed):** `environment_profiles` is not started, so the definition uses what exists. The backend has exactly two profiles (`backend/app/pilot_config.py`): `development` (the local workflow: `--backend`, `--local-rag-start`, the local container; selected when `MANIJERO_DEPLOYMENT_PROFILE` is unset, empty, or `development`) and `pilot` (the only hosted profile; `serve_pilot.py` refuses anything else, and `docs/constraints/hosting-and-pilot.md` requires every hosted service to start through it). Any other value already stops startup (`profile_invalid`). **Local** therefore means the validated `PilotConfig.profile` equals exactly `development`. Everything else is non-local, including `pilot` and any future `qa`, `prod`, or `local` value, until a later feature (`environment_profiles`) deliberately adds its local profile to the allowlist.

## Goal and boundaries

When a developer turns tracing on, every `/ask` that reaches the answer route leaves one JSON file. The file shows what retrieval found, how ranking fused it, what the drafter did, and why verification accepted or rejected the draft. The trace never changes an answer, never fails a request, and keeps text out of anything that is not the local profile.

**In scope**

- One setting, `MANIJERO_ANSWER_TRACE` (`on` | `off`, default off), read once at startup. `--local-rag-start` also accepts it as an optional line in its `settings.env`.
- One trace file per question in `<repository>/build/answer-traces/`, a fixed path that is git-ignored by the existing `build` rule. Files older than 7 days are deleted automatically.
- Text (question, final answer, draft answer) is included only in the local profile. Every other profile gets metadata only.

**Non-goals**

- Any HTTP endpoint, response field, `contracts/openapi.yaml` change, or client change. How a trace reaches a developer view is `rag_inspector_view`'s job.
- New profiles or settings files (`environment_profiles`), dashboards (`monitoring_dashboard`), Langfuse or any new dependency.
- Tracing inside the container image. Its environment is fixed and does not carry the setting, so tracing stays off there.
- Redacting the local question text, recording land context beyond its mode, or tracing requests that are rejected before the route (`400`/`401`/`413`/`422`/`429`).
- Any change to retrieval, ranking, drafting, verification, or answer behavior.

## Job story

When a local answer looks wrong, I want to see which passages were found and scored, whether the vector side ran, what the drafter produced, and which verification rule rejected it. Then I can fix the cause instead of guessing, without that detail ever leaking from a shared server.

## Acceptance scenarios

### Off by default

Given `MANIJERO_ANSWER_TRACE` is unset, empty, or `off`, when the service starts and answers questions, then it creates no `build/answer-traces/` folder and no file, and every response is unchanged. Given any other value (`On`, `1`, `yes`), then tracing stays off and startup logs one `answer_trace` record with `state=off reason=value_invalid`.

### One trace per question, local profile

Given the `development` profile and `MANIJERO_ANSWER_TRACE=on`, when `/ask` returns `answered`, `abstained`, `needs_land_clarification`, or the `503` unavailable path, then exactly one new file `build/answer-traces/<UTC yyyymmddThhmmssZ>-<32 hex>.json` exists. It holds schema `answer-trace-v1` and these fields:

- `trace_id`, `created_at` (UTC, seconds), `profile`, and `text_included: true`;
- `question` and the final `answer` text;
- `retrieval`: the effective mode (`bm25` or `hybrid`), `k`, the BM25 lexical ranking (passage id, score, rank; at most 20), the vector side (used or not, fallback code, passage id and similarity per match), the final candidates (passage id, source id, score, rank), the number of search calls, and the duration;
- `drafting`: the provider (`extractive`, `local`, or `gemini`), its fixed outcome code, the draft status, the cited markers, the draft text (at most 4000 characters, with a truncation flag), and the duration;
- `verification`: ok, the issue codes, and for each claim its index, markers, ok, and issue codes, plus the duration;
- `outcome`: the response status, the abstention reason and generation reason codes, the cited passage ids, `land_scope`, and the number of lands to choose from;
- `total_ms`.

A stage that did not run, such as the year-mismatch abstention or `503`, is `null`.

Given any profile, the file never contains a land id, municipality, water regime, production method, client id, token, IP address, or the `retain_for_improvement` value. A `GroundingIssue.detail` string is never recorded, only codes. Excerpts are never copied in; passage ids reference them.

### Non-local profiles record no text

Given the `pilot` profile and tracing on, when an authenticated `/ask` is answered, then the file has `text_included: false`. It has no `question`, `answer`, or draft-text key at any depth, and its full key set equals the published metadata-only allowlist. The bytes of a unique marker word in the question appear nowhere in the file. Given `text_allowed(profile)`, it is `True` only for exactly `development`. It is `False` for `pilot`, `qa`, `prod`, `local`, `Development`, ` development`, and the empty string.

### Never changes or breaks an answer

Given a fixed set of questions covering answered, abstained (including the year mismatch), clarification, and `503`, when they run with tracing on and off, then statuses and response bodies are byte-identical. Given the folder cannot be written, is a symlink, or serialization fails, when `/ask` runs, then the response is unchanged and status stays `200`/`503` as before. No partial or temporary file remains, and one `answer_trace_skipped reason=<fixed code>` record is logged without text.

### Folder, permissions, and git

Given tracing writes a file, then the folder is `<repository>/build/answer-traces/` with mode `0700`, each file has mode `0600`, and each file is written to a temporary name and renamed into place. `git check-ignore -q build/answer-traces/<file>` succeeds. No setting changes the folder; tests inject one.

### Deleted after 7 days

Given trace files whose name time is 7 days or more before now and others younger, when the service starts (tracing on or off, folder present) or before each trace write, then the old files are deleted and the younger ones are kept. Files whose names do not match the trace pattern are untouched. A failed purge never stops startup or a request. Nothing purges while the service is stopped; the next start does it. This limit is documented.

### One setting for the full local service

Given `~/manijero/local/settings.env` has `MANIJERO_ANSWER_TRACE=on`, when `./scripts/init.sh --local-rag-start` launches the service, then the allowlisted environment carries `MANIJERO_ANSWER_TRACE=on`. Given the line is absent or `off`, it does not carry it. Given another value or a repeated line, the existing named-line settings error stops the command before anything starts. The campaign line works unchanged. A newly created settings file shows the line commented out with the value `off`; an existing file is never rewritten.

### Acceptance by the validator

Given the focused verification passes and the validator accepts, then the feature is accepted with no owner walkthrough (decision 4).

## Technical approach

1. New `backend/app/answer_trace.py` (stdlib only):
   - Settings parsing and `text_allowed(profile)` with `LOCAL_PROFILES = frozenset({"development"})`.
   - A per-request collector held in a `contextvars.ContextVar`, plus `note_*` functions that are no-ops when no collector is active and never raise.
   - The `answer-trace-v1` document builder. Text keys are added only when text is allowed, and the metadata-only allowlist is a module constant.
   - The atomic `0600` writer and the 7-day purge, both with an injectable clock and folder.
2. `create_app` resolves the trace once from the validated `PilotConfig` and the environment, mirroring the retention store. It purges at startup, logs `answer_trace` state and text mode, stores the result on `app.state`, and accepts a test seam. The `/ask` route opens the collector, runs the unchanged `_answer`, and writes the file after the response exists, alongside the retention step. It also writes for the `503` path.
3. Read-only hooks call `note_*` and change no return value:
   - `Retriever.search`: lexical ranking, final candidates, timing.
   - `HybridRanker.rank`: vector use, fallback code, matches.
   - `GatedGeminiGenerator.generate`: provider, outcome code, timing.
   - `generate_grounded_answer`: draft and the `verify_draft` report.
   - The ask route: retrieval mode from the backend.
4. `local_rag_bootstrap.read_settings` accepts the optional key, and its template documents it. `local_rag_service.launch_environment` passes it through only when it is `on`.

## Expected file changes

- New: `backend/app/answer_trace.py` and `backend/tests/test_answer_trace.py`.
- `backend/app/main.py`, `backend/app/ask_api.py`, `backend/app/retrieval.py`, `backend/app/hybrid_retrieval.py`, `backend/app/gemini_generation.py`, and `backend/app/generation.py`: the setup and hooks listed above.
- `backend/app/local_rag_bootstrap.py`, `backend/app/local_rag_service.py`, `backend/tests/test_local_rag_bootstrap.py`, and `backend/tests/test_local_rag_service.py`: the optional setting.
- Documentation: `backend/README.md`, `docs/pilot-privacy.md`, `docs/constraints/hosting-and-pilot.md`, and `ARCHITECTURE.md`, as listed below.

## Visual design impact

None. This is backend only and has no UI or Spanish copy.

## Durable documentation impact

- `backend/README.md`: update. Add a configuration-table row and a section of 30 lines or fewer covering how to turn tracing on, where files go, the 7-day purge, text only in `development`, and how to delete everything (remove the folder).
- `docs/constraints/hosting-and-pilot.md`: update. Add one MUST rule: traces off by default, text only in the `development` profile, metadata-only allowlist elsewhere, fixed git-ignored folder, and 7-day deletion. Reason: owner decisions 1–3.
- `docs/pilot-privacy.md`: update. Add one data-flow row for the answer trace.
- `ARCHITECTURE.md`: update. Add one sentence in "Privacy, retention, and review boundary".
- `docs/progress/known-limitations.md` and `PROGRESS.md`: one line each at acceptance. The purge runs only while the service runs, and no hosted trace has been observed.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, and `contracts/`: not needed, because nothing changes in workflow, domain terms, UI, or the API contract.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_answer_trace.py tests/test_ask_endpoint.py tests/test_retrieval.py tests/test_hybrid_retrieval.py tests/test_generation.py tests/test_gemini_generation.py tests/test_local_generation.py tests/test_local_rag_bootstrap.py tests/test_local_rag_service.py -q
git check-ignore -q build/answer-traces/20261102T000000Z-00000000000000000000000000000000.json
```
<!-- verify:end -->

No owner walkthrough (decision 4). The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence.

## Appendix

See [`answer_pipeline_trace.appendix.md`](answer_pipeline_trace.appendix.md) for repository research, tasks, verification plan, feature evidence, and validator checklist.
