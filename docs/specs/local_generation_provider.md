# Feature Spec: `local_generation_provider`

## Source metadata

- **Feature:** `local_generation_provider` — Draft answers with a local open-weight model (`backend`).
- **Status at planning:** `not_started`; depends on accepted `grounded_answer_generation`,
  `backend_answer_evaluation`, and `gemini_generation_provider` (accepted on the integration branch
  `integration/chroma-hybrid-and-gemini-gate-2026-10-31`, not yet on `main`).
  `private_pilot_distribution` depends on this feature.
- **Source behavior (owner decisions 2026-10-31, `hosting_provider_review.md` "Owner decisions",
  issue #143):** no spending; Gemini is postponed. Answer drafting is tried with a free open-weight
  model run locally through Ollama, using the replaceable generation slot from
  `gemini_generation_provider`. Every draft passes the existing whole-draft verifier. Citations,
  sources, notices, and abstentions stay code-owned. Any failure (timeout, connection refused,
  malformed output, verifier rejection) falls back to the extractive answer. Local generation is
  off by default and needs explicit configuration to turn on.
- **Measurement host:** the owner's Mac (Apple M5 Max, 64 GB RAM). The model may use at most
  50 GB. Ollama 0.40.13 is installed by the owner and serves `http://127.0.0.1:11434`. The code
  talks only to that loopback API. Downloading open-weight models from the Ollama registry is
  allowed. No other external call is allowed.
- **Feature-list verification:** pin the exact model tag and digest and record its license.
  Measure per-question latency, cold start, peak memory, and the verified-draft rate against the
  extractive baseline on the 14 reviewed cases. Report the numbers honestly and claim nothing
  about answer quality beyond them. The feature does **not** decide whether this Mac is enough or
  whether a faster external server is needed; the owner decides that later from these numbers.
- **Test and environment rules:** automated tests must not need Ollama (they use fakes). The live
  measurement is a separate opt-in script whose results go into the appendix evidence. Use the
  shared backend environment (`./scripts/init.sh --setup-python`), never a hand-made virtualenv.
  Add no new Python dependency (stdlib `urllib` only). Keep personal and land details out of logs,
  and minimise the land context sent.

## Goal and boundaries

Add a second provider, `local`, to the slot that `gemini_generation_provider` built. It sends
the same minimal, redacted payload over loopback HTTP to a pinned Ollama model. It reuses the
accepted `GatedGeminiGenerator` verify-then-fallback path, so a local draft can never be worse
than today's extractive answer. An opt-in script then measures the model on this Mac against the
extractive baseline.

**In scope:**

- A new `backend/app/local_generation.py` containing:
  - a committed model record loader and its gate;
  - `OllamaTransport`, a `GeminiTransport` that is loopback-only, digest-checked, and ignores
    proxies;
  - a startup resolver for `MANIJERO_GENERATION_PROVIDER=local`.
- A committed record, `backend/config/local_generation_model.json` (`local-generation-model-v1`).
  It holds the pinned tag, digest, license, size, and operational limits.
- Small, behavior-preserving changes so the shared generator and provider can carry a provider
  name, a "used" outcome code, and a log callable. Gemini keeps its current names and codes.
- An opt-in live measurement script, `backend/scripts/measure_local_generation.py`.
- Fake-only tests, and the operator and durable docs.

**Non-goals:**

- Deciding whether this Mac, an owned server, or an external GPU host serves the pilot.
- Any non-loopback endpoint, configurable base URL, remote Ollama, or cloud call.
- Enabling Gemini, or changing Gemini's gates, limits file, or review record.
- Prompt or instruction tuning, fine-tuning, multiple models, model ensembles, streaming,
  caching, or retries.
- Startup warm-up calls.
- Any change to `verify_draft`, `generate_grounded_answer`, abstention, clarification,
  `contracts/`, `knowledge/`, or `shared/`.
- Any claim about answer quality, fluency, or legal coverage.
- Making the script pull a model (the owner or implementer runs `ollama pull`).

## Job story

When the owner turns on local drafting on their Mac, they want answers drafted by a free local
model that are checked by the same verifier and fall back to today's answer on any problem. They
also want honest latency, memory, and verified-draft numbers, so they can decide later whether
this Mac is enough, without spending money or sending a question anywhere.

## Acceptance scenarios

### Off by default

Given an environment without `MANIJERO_GENERATION_PROVIDER=local`, when the app is created and
`/ask` is called, then:

- no `OllamaTransport` is built;
- no socket connect is attempted;
- the response equals the extractive baseline;
- the startup `generation_provider` log line keeps today's Gemini resolution unchanged.

### Explicit two-key enable

Given `MANIJERO_GENERATION_PROVIDER=local` and `MANIJERO_LOCAL_MODEL` equal to the record's
`model`, a valid record, and a non-pilot profile, the resolver returns `provider=local`.

Each of the following, on its own, resolves to `extractive` with a fixed blocker:

| Missing or wrong input | Blocker |
|---|---|
| Model env unset or different from the record | `local_model_mismatch` |
| Record missing or unreadable | `local_model_record_unreadable` |
| Record has the wrong shape | `local_model_record_invalid` |
| A value is out of range | `local_model_record_out_of_range` |
| `size_bytes` is above 50,000,000,000 | `local_model_over_budget` |
| `recorded_on` is in the future | `local_model_record_future_date` |
| Pilot profile without a passed pilot review | `pilot_privacy_review_not_passed` |

Blockers echo no env or record value. In every one of these cases `/ask` equals the baseline.

### Loopback only, minimal payload

Given the `local` path is active with a recording fake opener, when `/ask` drafts, then every
request goes to `http://127.0.0.1:11434`:

- first `GET /api/tags`, once, for the digest check;
- then `POST /api/chat` with `stream: false`.

The body has exactly these keys: `model`, `messages`, `stream`, `format`, `options`, and
`keep_alive`.

- `messages` holds two entries. The `system` entry is the pinned instruction. The `user` entry is
  the `payload_json` built by `minimal_provider_payload(redact_text(question, land values),
  candidate-numbered citation-window excerpts)`.
- `options` holds `temperature: 0`, `seed: 0`, `num_ctx`, and `num_predict`, taken from the record.

The body contains no land id, municipality, land name, catalog id, URL, title, metadata, client
id, or retained text. The opener ignores `HTTP(S)_PROXY` and refuses redirects.

### Verified local draft is used; code owns the answer shell

Given the fake returns a well-formed draft that passes `verify_draft`, when `/ask` runs, then:

- the response is assembled by existing code: lead-in, dense `[n]` markers, retrieval `sources`,
  and the pinned notice;
- the response validates against the unchanged `AskResponse`;
- one `generation` log line carries `provider=local` and `outcome=local_used`.

### Fallback on every failure

Given the `local` path is active, when any of the following happens, then no draft text reaches
the response, the response equals the extractive baseline, the generator never raises, and the
log carries only `provider=local` plus a fixed outcome code:

- connection refused;
- a socket timeout or exceeding `timeout_seconds`;
- an HTTP 404 or 500;
- a non-JSON or oversize (over 65,536 bytes) HTTP body, or a body missing `message.content`;
- the model is absent from `/api/tags`, or its digest differs from the record;
- malformed draft JSON, an `abstained` draft, or a draft rejected by `verify_draft`;
- the rate limit is reached, or redaction fails.

### Pipeline order unchanged

Given a land clarification, `false_premise`, `conflicting_evidence`, `no_evidence`, an invalid
request, or a stale corpus, when `local` is active, then the opener is never called.

### Opt-in live measurement (not part of automated tests)

Given Ollama is serving the pinned model on this Mac, when the owner runs
`measure_local_generation.py`, it:

- checks the digest;
- runs the 14 cases in `knowledge/pac_answer_eval.json` through `/ask`, once extractive and
  `--repeats` times with `local`;
- prints a text-free JSON report with:
  - per-question latency (median, p95, max),
  - cold load seconds and the cold first-case latency and outcome,
  - peak memory (Ollama `/api/ps` size and summed `ollama` process RSS) against the 50 GB budget,
  - outcome counts and the verified-draft rate,
  - side-by-side `answer_eval` aggregates and the ids of changed cases.

It makes no recommendation. If Ollama is unreachable or the digest differs, it exits `2`.

## Technical approach

1. **Model record.** `local_generation_model.json` has exactly these keys:

   | Key | Rule |
   |---|---|
   | `schema_version` | `local-generation-model-v1` |
   | `model` | Ollama tag, non-blank, no whitespace, ≤ 128 characters |
   | `digest` | 64 lowercase hex characters, as reported by `/api/tags` |
   | `license` | SPDX id |
   | `license_reference` | non-blank pointer |
   | `parameter_size` | string |
   | `quantization` | string |
   | `size_bytes` | int, 1 to 50,000,000,000 (above the budget gives `over_budget`) |
   | `num_ctx` | int, 2048 to 32768 |
   | `timeout_seconds` | number, 1 to 14 — below the app's 15 s `REQUEST_TIMEOUT_MILLIS`, so a fallback still reaches the app |
   | `max_output_tokens` | int, 1 to 1024 |
   | `max_requests_per_minute` | int, 1 to 600 |
   | `max_requests_per_day` | int, 1 to 100000 |
   | `keep_alive_seconds` | int, 0 to 86400 |
   | `recorded_on` | ISO date, not in the future |

   A boolean is never accepted as an int, and NaN is rejected. The committed limits are:
   `timeout_seconds` 10, `max_output_tokens` 400, `num_ctx` 4096, 30 requests/min,
   2000 requests/day, `keep_alive_seconds` 1800. The implementer records `digest`, `size_bytes`,
   `parameter_size`, `quantization`, and `license` from the local API (see the appendix).
2. **Model choice.** Pin `mistral-small3.2:24b-instruct-2506-q4_K_M` (Mistral Small 3.2, 24B,
   Q4_K_M, about 15 GB; Apache-2.0). Reasons:
   - it is a permissive, OSI-approved licence with no separate use policy;
   - its multilingual instruction following, including Spanish, is strong;
   - it supports JSON-schema structured output;
   - at about 15 GB it is well inside the 50 GB budget;
   - Q4 keeps decode fast enough to fit the 10 s timeout.

   If that tag cannot be pulled, or `/api/show` does not report Apache-2.0, the implementer stops
   and reports. It must not substitute another model.
3. **Transport.** `OllamaTransport(record, *, opener=None, clock=None, on_metrics=None)`
   implements `GeminiTransport.send(request) -> str`. It works like this:
   - The constant `OLLAMA_BASE_URL = "http://127.0.0.1:11434"` is the only base URL, and nothing
     can override it.
   - The default opener is `urllib.request.build_opener(ProxyHandler({}), <no-redirect handler>)`.
   - A `request.model` that differs from `record.model` raises.
   - On first use it checks `/api/tags` (2 s timeout) under a lock and caches only a success.
   - It posts `/api/chat` with `timeout=request.timeout_seconds`, `format` set to the draft JSON
     schema (`status` enum, `answer` string, `sources` int array, all required),
     `num_predict=request.max_output_tokens`, and `keep_alive=f"{keep_alive_seconds}s"`.
   - It reads at most 65,536 bytes and returns `message.content`.
   - It maps errors to `LocalTransportError` with a fixed code: `connection_refused`,
     `http_error`, `model_not_found`, `model_digest_mismatch`, or `response_invalid`. A socket
     timeout is re-raised as `TimeoutError`.
   - `on_metrics`, if given, receives only the non-negative integer fields `total_duration`,
     `load_duration`, `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, and
     `eval_duration`.
   - It never logs and never carries response text in an exception.
4. **Shared generator.** In `gemini_generation.py`, `GatedGeminiGenerator` and
   `GatedGeminiProvider` gain three fields, each defaulting to today's value: `provider_name`
   (default `gemini`), `used_outcome` (default `gemini_used`), and `log` (default
   `operational_log`). The instruction, its version `gemini-draft-v1`, `parse_draft`, the
   citation window, `verify_draft`, the rate limiter, and the post-hoc timeout all stay exactly
   as accepted. The local provider builds a `GeminiLimits` from the record, with
   `cost_reference="local-no-spend"`.
5. **Resolver and wiring.** `local_generation.resolve_startup_generation(*, gemini_transport,
   local_transport, clock, pilot)` works like this:
   - It reads `MANIJERO_GENERATION_PROVIDER`.
   - Unless the value is `local`, it returns `resolve_startup_provider(gemini_transport, clock)`
     unchanged.
   - For `local`, it reads only `MANIJERO_LOCAL_MODEL` besides that, and evaluates the record and
     (in the pilot profile) `evaluate_pilot_review`.
   - It builds `local_transport or OllamaTransport(record)`. Construction makes no network call.
   - It returns `ProviderResolution("local", (), provider)`.
   - It never raises; an unexpected error gives `extractive` with `generation_provider_unresolved`.

   `create_app` gains a keyword-only seam, `local_transport=None`, and calls this resolver.
   `privacy_review.GENERATION_PROVIDERS` adds `local`, so preflight does not flag it.
   `ask_api` is unchanged.
6. **Measurement script.** It reuses `answer_eval.load_case_document` and `evaluate` unchanged,
   once per mode, on in-process apps built with `create_app(local_transport=<recording
   OllamaTransport>)`. It times each `/ask` and each `send`. It unloads the model
   (`keep_alive: 0`), polls `/api/ps` until the model is gone, and times a load-only
   `/api/generate` (300 s timeout) to get `cold_load_seconds`. Repeat 1 starts cold. A background
   thread samples `/api/ps` and `ps -axo rss=,comm=` every 0.5 s. Its only network target is the
   loopback constant.

## Expected file changes

- **Create:**
  - `backend/app/local_generation.py`
  - `backend/config/local_generation_model.json`
  - `backend/scripts/measure_local_generation.py`
  - `backend/tests/test_local_generation.py`
  - `backend/tests/fixtures/local_generation/synthetic_model_record.json` (labelled synthetic)
- **Update:**
  - `backend/app/gemini_generation.py`: the three defaulted fields only.
  - `backend/app/main.py`: the seam and the resolver call.
  - `backend/app/privacy_review.py`: the allowed provider value and the docstring.
- **Do not change:** `contracts/`, `knowledge/`, `shared/`, any `requirements*.txt`,
  `backend/deploy/`, `pilot_privacy_review.json`, `gemini_provider_limits.json`,
  `scripts/init.sh`, or the existing tests.
- **`scripts/init.sh`:** no `--feature` wiring is needed. The generic `--feature` runner executes
  the block below. The live measurement stays a documented manual command, not an `init.sh` tier.

## Visual design impact

None. There is no app, copy, or wire-contract change.

## Durable documentation impact

- **`ARCHITECTURE.md` — update.** Describe the `local` provider: loopback Ollama, the pinned
  record, the reuse of `GatedGeminiGenerator` with verify-then-fallback, off by default, and no
  remote endpoint.
- **`CONSTRAINTS.md` — update.**
  - Widen the `GatedGeminiGenerator` MUST to cover the local provider.
  - Add a MUST: the local transport talks only to the `OLLAMA_BASE_URL` loopback constant, with
    no proxy and no redirect. Only the pinned tag whose digest matches the committed record may
    be used. Changing the model, digest, or limits needs a reviewed change with new measurement
    evidence. Local generation stays off unless both env keys are set. In the pilot profile it
    also needs a passed pilot review. Tests must not need Ollama.
  - Scope the "no transport" rule to remote providers.
- **`backend/README.md` — update.**
  - Add env table rows for `local` and `MANIJERO_LOCAL_MODEL`.
  - Add a "Local open-weight drafting (Ollama)" section covering `ollama pull <tag>`, how to read
    the digest, the blockers and outcomes, the measurement command, and the limits.
- **`docs/pilot-privacy.md` — update.** Add a local-generation data-flow row: the question stays
  on the host; Ollama's own server logs are outside the app's control.
- **`docs/risks-and-open-questions.md` — update.**
  - Point the Gemini row at the measured local results.
  - Add the owner's open decision on whether the Mac is enough.
- **`AGENTS.md`, `DESIGN.md`, `CONTEXT.md`, `knowledge/` docs — not needed.** There is no
  routing, UI, domain-term, or corpus change.

## Focused verification

Needs the shared backend environment (`./scripts/init.sh --setup-python`). No step needs Ollama
or the network. The live measurement is in the appendix.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_generation.py tests/test_gemini_generation.py tests/test_privacy_retention.py tests/test_pilot_operations.py
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`local_generation_provider.appendix.md`](local_generation_provider.appendix.md).
