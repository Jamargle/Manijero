# Expose privacy-safe backend health metrics

## Source metadata

- `id`: backend_health_metrics · `area`: operations · `depends_on`: backend_ask_endpoint, hosted_pilot_operations, knowledge_reindex_release, knowledge_update_scheduler, local_generation_provider · `status` at planning: not_started
- User-visible behavior: the answer service serves `GET /metrics` in Prometheus text format with readiness, answer outcomes, latency, errors, generation fallbacks, rate-limit hits, the active knowledge release, and source-update run recency, as counts and timings only. No app or owner-facing UI changes.
- Verification: in-process FastAPI tests over fake corpora, fake generation transports, fake ledgers, and fake tokens; the commands are in Focused verification.
- Notes (owner decisions, verbatim):
  - Expose a standard /metrics endpoint in Prometheus text exposition format (free, and what monitoring_dashboard will read later).
  - Open (no auth) in the local profile; in QA it requires the same pilot token as the app.
  - Privacy: counts and timings only, never question or answer text or any land details (no high-cardinality or user-derived labels).
  - Approval: the independent validator's accept is final; no owner walkthrough. The owner reviews it in the batch PR.
- Planning decisions: "local profile" is deployment profile `development` and "QA" is profile `pilot` (see `environment_profiles`). The exporter is hand-written with the standard library (no `prometheus_client`); reason in Technical approach.

## Goal

Give the later `monitoring_dashboard` (and an operator with `curl`) one machine-readable page that says whether the service can answer and how it has been behaving since it started, without exposing anything a user typed or any land detail.

## Non-goals

- No dashboard, alerting, scraper, Prometheus server, or metric storage (`monitoring_dashboard`, `qa_service_alerts`).
- No owner command or `docs/owner-guide/` steps; the owner never opens `/metrics` directly.
- No wiring of the source-update state folder into `--local-rag-start`, the container, or the QA settings file; the service only reads it when `MANIJERO_SOURCE_UPDATE_STATE_DIR` is already set.
- No per-client, per-land, per-question, per-passage, or per-source labels; no cross-worker aggregation; no persistence across restarts.
- No change to `/health`, `/ready`, `/ask` responses, `contracts/openapi.yaml`, or the Android/Desktop apps.
- No legal-freshness claim: source-update metrics report scheduler run recency only.

## Job story

When the answer service is running locally or in QA, I want a standard metrics page that a free dashboard can read, so I can see whether it is ready and answering well without reading logs or exposing anyone's questions.

## Acceptance Scenarios

### 1. Local profile serves metrics openly

Given the `development` profile · When `GET /metrics` is sent without credentials · Then it returns `200`, content type `text/plain; version=0.0.4; charset=utf-8`, and every metric family in the table below with one `# HELP` and one `# TYPE` line, parseable as Prometheus text format 0.0.4.

### 2. QA (pilot) profile requires the app's pilot token

Given the `pilot` profile with fake clients · When `/metrics` is sent with no, malformed, or unknown bearer token · Then it returns the existing detail-free `401` with `WWW-Authenticate: Bearer`; with a valid client token it returns `200`. Scrapes count against a separate per-client window with that client's same per-minute allowance, so scraping never uses up the client's `/ask` allowance; exceeding it returns the existing `429`.

### 3. Answer outcomes and latency are counted

Given a ready fake corpus · When `/ask` returns answered, abstained (each tested reason), and needs-land-clarification responses · Then `manijero_answers_total{status}` and `manijero_abstentions_total{reason}` increase by exactly those counts, and `manijero_request_duration_seconds{route="/ask"}` `_count` equals the number of `/ask` requests with cumulative, monotonic buckets.

### 4. Errors and rate-limit hits are counted

Given each case · When `/ask` gets a malformed body (`400`), a bad shape (`422`), an unavailable corpus (`503`), an unhandled exception (`500`), a too-large body (`413`), or, in `pilot`, a missing token (`401`) or an over-allowance request (`429`) · Then `manijero_http_requests_total{route,code}` counts each response once, and `manijero_request_rejections_total{route,reason}` counts the `413`/`401`/`429` gate rejections as `too_large`/`unauthenticated`/`rate_limited`.

### 5. Generation fallbacks are counted

Given a model provider with a fake transport · When drafting is used, times out, errors, is malformed, abstains, is rejected by the verifier, or is limited by the provider limiter · Then `manijero_generation_outcomes_total{provider,outcome}` counts `used` or the fixed fallback code once per draft; with the default extractive path no generation sample increments, and `manijero_generation_provider_info{provider="extractive"}` is `1`.

### 6. Readiness and the active knowledge release are reported at scrape time

Given a ready corpus · When `/metrics` is read · Then `manijero_ready` is `1` and every `manijero_readiness_problem{problem}` is `0`. Given a missing campaign or unusable corpus · Then `manijero_ready` is `0` and exactly the matching problem is `1`, and `/metrics` still returns `200`. With `MANIJERO_KNOWLEDGE_RELEASE_ROOT` set, `manijero_knowledge_release_info{release_id,state}` is `1` for the served (or refused) 16-hex release id; without it, `release_id="none",state="repository"`.

### 7. Source-update run recency is reported only when configured

Given `MANIJERO_SOURCE_UPDATE_STATE_DIR` unset · Then `manijero_source_updates_configured` is `0` and no other source-update sample appears. Given it names a fake state folder with a ledger · Then `configured` and `manijero_source_updates_readable` are `1`, `manijero_source_updates_healthy` mirrors the scheduler status, and per job (`monitor`, `boe`, `boja`) `manijero_source_update_stale{job}` and `manijero_source_update_last_success_timestamp_seconds{job}` (only for jobs with a success) match `evaluate_status`. Given an unreadable or invalid ledger · Then `readable` is `0` and `/metrics` still returns `200`.

### 8. Metrics never carry user text, land details, or identifiers, and never break the service

Given `/ask` requests whose question, land names, notes, and ids hold distinctive strings, and a pilot client id and token · When `/metrics` is read · Then none of those strings appear, every label name is in the allowlist below, every label value is a fixed code (or a release id matching `^[0-9a-f]{16}$`), and an unknown path is counted as `route="other"`. A failing recording hook never changes an `/ask` response or status.

## Technical approach

- New stdlib-only module `backend/app/health_metrics.py`: a thread-safe `HealthMetrics` registry (counters and one histogram behind one lock), label values clamped to fixed allowlists, and `render()` producing text format 0.0.4 (sorted families, `# HELP`/`# TYPE`, escaped label values, `_bucket`/`_sum`/`_count`, `+Inf`). Recording hooks are module-level and `_safe`-wrapped, writing to the registry bound in a `ContextVar` by the middleware, mirroring `app/answer_trace.py`.
- Dependency choice: no `prometheus_client`. The repo keeps service modules stdlib-only beyond FastAPI/uvicorn/httpx, the format is a few dozen lines for this fixed metric set, and a global third-party registry would leak between `create_app` instances in tests.
- `create_app` builds one registry per app (`app.state.health_metrics`), records the startup provider and profile, passes the registry to `PilotGuardMiddleware`, and registers `GET /metrics` with `include_in_schema=False`. That route reuses the `/ready` dependencies (`get_corpus_documents`, `get_as_of_date`, `get_configured_campaign`) and `evaluate_readiness`, then reads the release outcome and source-update status, then renders.
- `PilotGuardMiddleware` records every response (route, code, duration) and every gate rejection where it already calls `log_request`. Add `/metrics` to the gated paths with a separate limiter window keyed per path. Route labels are `/ask`, `/ready`, `/health`, `/metrics`, or `other`.
- Answer hooks: `ask_question` records `status` and abstention `reason` after the response exists. `GatedGeminiGenerator.generate` records `(provider_name, "used" if outcome == used_outcome else outcome)` beside its existing `operational_log`. `ask_api._note_release_outcome` keeps the last outcome readable through a small accessor for `/metrics`.
- Freshness: when `MANIJERO_SOURCE_UPDATE_STATE_DIR` is set, lazily import `app.source_update_scheduler` and call `status_for_state_dir`; any exception means `readable 0`. The implementer may cache by ledger `(mtime_ns, size)`.
- Counters are per process and reset on restart, like the rate limiter ([`hosting-and-pilot.md`](../constraints/hosting-and-pilot.md)); document this and never describe them as cluster-wide.

Metric families (prefix `manijero_`; label allowlist: `profile`, `version`, `provider`, `route`, `code`, `reason`, `status`, `outcome`, `problem`, `release_id`, `state`, `job`, `le`):

| Family | Type | Labels |
|---|---|---|
| `service_info`, `generation_provider_info` | gauge | `profile`,`version` / `provider` |
| `process_start_time_seconds` | gauge | — |
| `ready`, `readiness_problem` | gauge | — / `problem` (4 readiness codes) |
| `http_requests_total` | counter | `route`, `code` |
| `request_duration_seconds` | histogram | `route`; buckets 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60 |
| `request_rejections_total` | counter | `route`, `reason` (`too_large`, `unauthenticated`, `rate_limited`) |
| `answers_total`, `abstentions_total` | counter | `status` (3) / `reason` (`ABSTENTION_REASONS`) |
| `generation_outcomes_total` | counter | `provider` (`gemini`, `local`), `outcome` (`used` + fixed fallback codes) |
| `knowledge_release_info` | gauge | `release_id`, `state` (`served`, `refused`, `repository`) |
| `source_updates_configured`, `_readable`, `_healthy` | gauge | — |
| `source_update_stale`, `source_update_last_success_timestamp_seconds` | gauge | `job` |

## Expected file changes

- `backend/app/health_metrics.py` — create; registry, hooks, renderer, freshness reader.
- `backend/app/main.py` — modify; build registry, pass to middleware, `GET /metrics`.
- `backend/app/pilot_guard.py` — modify; record responses and rejections, gate `/metrics` with its own window.
- `backend/app/ask_api.py` — modify; answer-outcome hook, release-outcome accessor.
- `backend/app/gemini_generation.py` — modify; generation-outcome hook.
- `backend/tests/test_health_metrics.py` — create; scenarios 1–8.
- `ARCHITECTURE.md`, `docs/constraints/operations.md`, `backend/README.md`, `docs/progress/known-limitations.md` — see below.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — the backend line also exposes `GET /metrics`.
- `docs/constraints/operations.md`: update — one Monitoring MUST: `/metrics` carries only fixed-label counts, timings, and the release id; it is open only in `development` and needs a client token in `pilot`. Reason: this spec.
- `docs/constraints/hosting-and-pilot.md`: not needed — the operations rule names the pilot gate; logging rules are unchanged.
- `AGENTS.md`: not needed — no workflow change.
- `backend/README.md`: update — a "Health metrics" section of at most 30 lines: families, the profile gate, the opt-in state-folder key, and per-process reset.
- `docs/progress/known-limitations.md`: update — one line: per-process counters reset on restart, freshness only when the state folder is set, in-process tests only.
- `docs/owner-guide/`, `contracts/openapi.yaml`: not needed — no owner operation; not a client contract.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_health_metrics.py tests/test_health.py tests/test_pilot_operations.py tests/test_ask_endpoint.py tests/test_gemini_generation.py tests/test_local_generation.py tests/test_knowledge_release.py tests/test_source_update_scheduler.py tests/test_answer_trace.py -q
```
<!-- verify:end -->

No owner walkthrough (owner decision). The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence.

## Appendix

See [`backend_health_metrics.appendix.md`](backend_health_metrics.appendix.md) for research, plan, evidence, and the validator checklist.
