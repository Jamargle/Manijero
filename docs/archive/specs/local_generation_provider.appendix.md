# `local_generation_provider` planning appendix

This is the on-demand record for the contract in
[`local_generation_provider.md`](../../specs/local_generation_provider.md). It was planned on 2026-10-31 in
the worktree `integration_chroma_gemini`, on branch
`integration/chroma-hybrid-and-gemini-gate-2026-10-31` (clean at `f7cddec`).

## Repository research

Inspected on 2026-10-31:

- **`backend/app/gemini_generation.py`** (accepted `gemini_generation_provider`).
  - `GeminiTransport.send(request) -> str` is the only seam.
  - `GeminiDraftRequest` carries `model`, `instruction`, `instruction_version`, `payload_json`,
    `max_output_tokens`, and `timeout_seconds`.
  - `GeminiDraftClient` pins `GEMINI_INSTRUCTION` (vendor-neutral Spanish) and its version,
    `gemini-draft-v1`.
  - `parse_draft` is strict: exact keys, ≤ 8192 raw chars, no fences, URLs, notice, or lead-in.
  - `RateLimiter` is per-process.
  - `GatedGeminiGenerator` offers only the citation window (`max_claims` = 2), runs
    `verify_draft`, and falls back to `ExtractiveGroundingGenerator`.
  - It currently hard-codes `provider=PROVIDER_GEMINI` in its log line and returns
    `OUTCOME_USED = "gemini_used"`. Those are the two values this feature makes into
    defaulted fields.
  - `ProviderResolution(provider, blockers, gemini)` has the method
    `generator_for(land_context, max_claims)`.
  - `resolve_startup_provider(transport, clock)` never raises.
- **`backend/tests/test_gemini_generation.py`.**
  - The AST guard (line 932) applies only to `gemini_generation.py` and allows
    `__future__`, `dataclasses`, `datetime`, `json`, `os`, `pathlib`, `threading`, `time`,
    `typing`, and `app`. The new module must not be imported by `gemini_generation.py`, so that
    guard keeps passing.
  - The env guard (line 482) asserts that only `MANIJERO_GENERATION_PROVIDER` and
    `MANIJERO_GEMINI_MODEL` are read by `resolve_generation_provider`. The local dispatch
    therefore lives outside that function.
  - The log-field test asserts exactly `event, time, provider, outcome`.
- **`backend/app/privacy_review.py`.**
  - `GENERATION_PROVIDERS = {"extractive", "gemini"}`. `generation_provider_problem` would flag
    `local` as `generation_provider_invalid` in preflight, so the value must be added.
  - `decide_generation_provider` reports `gemini_not_configured` for any other value; that is
    unchanged.
  - `evaluate_pilot_review(record, as_of)` is reusable for the pilot-profile condition.
  - `minimal_provider_payload` is the only payload builder.
- **`backend/app/main.py`.**
  - `create_app(config, retention_store, *, generation_transport, generation_clock)` resolves
    once, logs `generation_provider` (provider plus blockers), and stores the result in
    `app.state.generation_provider`.
  - The module-level `app = create_app()` runs at import, so resolution must make no network
    call and must never raise.
  - `resolved.pilot` is the profile flag.
- **`backend/app/ask_api.py`.** `_answer` calls `generation.generator_for(land_context,
  max_claims=DEFAULT_MAX_CLAIMS)`. Nothing here needs to change.
- **`backend/app/pilot_ops.py`.** Preflight uses `generation_provider_problem` and
  `decide_generation_provider`. It is unchanged apart from the allowed value.
- **`backend/app/answer_eval.py` and `backend/scripts/evaluate_pac_answers.py`.**
  - `evaluate(cases, client, catalog, passages, k, coverage=...)` posts each case to `/ask`,
    validates the result with `AskResponse`, and returns aggregates and `case_rows`. The rows
    carry ids and booleans only, no answer text.
  - The script uses dependency overrides for corpus, `as_of`, campaign, and `k`.
- **`docs/archive/specs/chroma_hybrid_retrieval.appendix.md`.** This is the precedent for a per-mode
  comparison on the 14 cases (`--as-of 2026-10-31 --active-campaign 2026`, `k=5`). The accepted
  extractive baseline is 13/14 states, 11/11 answered, 8/11 source/passage, 9/11 critical
  literal, 2/3 abstentions, and 1 unexpected answer.
- **`shared/.../chat/AnswerService.kt`.** `REQUEST_TIMEOUT_MILLIS = 15_000` and
  `SOCKET_TIMEOUT_MILLIS = 15_000`. A backend draft slower than about 14 s would surface in the
  app as a failure, not as the extractive fallback. That is why `timeout_seconds` is capped at
  14 and committed at 10.
- **`backend/requirements.txt` and `backend/requirements-dev.txt`.** They contain `fastapi`,
  `uvicorn`, `httpx`, `pytest`, and `jsonschema`. Stdlib `urllib.request` is enough, so no
  dependency is added. `.python-version` pins 3.12, and `scripts/python-env.sh` builds the shared
  environment.
- **`scripts/init.sh`.**
  - `--feature <id>` runs the spec's verify block generically from the repository root. No
    per-id wiring is needed; only `backend_answer_evaluation` has special handling.
  - `--backend-tests` auto-links `backend/.venv` through `python-env.sh dev --if-present`.
  - Note: `init.sh` checks for `java` before dispatching `--feature`. This is the same
    precondition earlier features hit (see the `chroma_hybrid_retrieval` evidence for the
    Gradle-provisioned JDK workaround).
- **`CONSTRAINTS.md`.** Lines 8–22 cover answer grounding, 230–252 the Gemini gate and
  `GatedGeminiGenerator` MUSTs, and 533–536 forbid a real-user question transiting a generation
  provider before the qualified review.
- **`ARCHITECTURE.md`.** Line 40 is the Gemini paragraph.
- **`docs/pilot-privacy.md`.** Line 24 is the Gemini data-flow row.
- **`docs/risks-and-open-questions.md`.** Line 65 is the Gemini row with the postponement note.
- **`docs/specs/hosting_provider_review.md`.** Lines 205–220 hold the owner decisions.
- **`docs/specs/private_pilot_distribution.md`.** It lists this feature as a dependency but
  assumes nothing about it.

Not inspected:

- Ollama 0.40.13's API reference. Its endpoint and field names (`/api/tags` `models[].name`,
  `model`, `digest`, `size`; `/api/show` `license` and `details`; `/api/chat` `message.content`,
  `format`, `options`, `keep_alive`, and the duration fields; `/api/ps` `size` and `size_vram`;
  `/api/version`) are taken from the long-standing public API. **The implementer must confirm
  them against the installed server's live responses before writing the transport, and record any
  difference.**
- The Ollama registry page for the pinned tag.

## Design decisions

- **Reuse the accepted generator rather than fork it.** The same instruction, parser, citation
  window, verifier, rate limiter, and fallback mean the local path inherits every accepted
  property. The CONSTRAINTS rule that a model draft reaches `/ask` only through
  `GatedGeminiGenerator` stays literally true. The class names stay Gemini-named to avoid churn;
  docstrings say they are shared.
- **No privacy review for local development, but a pilot review for the pilot profile.** No data
  leaves the host in development. In the pilot profile, real users' questions would reach the
  model process, so the passed pilot review is required, consistent with CONSTRAINTS 533–536.
  The pilot review is `pending` today, so `local` is effectively development-only.
- **Two-key enable.** `MANIJERO_GENERATION_PROVIDER=local` plus `MANIJERO_LOCAL_MODEL`, which
  must exactly match the record. This mirrors Gemini, and a stray provider value cannot turn on
  drafting.
- **Loopback constant, not configuration.** Whether an external server is needed is the owner's
  later decision. Making the URL configurable now would pre-empt it and widen the privacy
  surface.
- **Digest checked lazily, not at startup.** `create_app` runs at import and must stay
  network-free. The first draft checks `/api/tags`, and only a success is cached, so pulling the
  right model later needs no restart.
- **JSON-schema `format`.** It is a transport mapping of the same draft shape, and it lowers the
  malformed-output rate. `parse_draft` stays the authority.
- **Determinism.** `temperature: 0` and `seed: 0`. Determinism is only reported as observed,
  never claimed.
- **Cold start is not hidden.** There is no warm-up at startup. With `keep_alive` at 1800 s, a
  first question after an unload may exceed the 10 s timeout and fall back to extractive. The
  script measures and reports this.

## Implementation plan

1. **Environment.**
   - Run `./scripts/init.sh --setup-python` and confirm `backend/.venv` links to the shared Python
     3.12 environment.
   - Record the full-suite baseline with
     `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests`.
2. **Confirm the Ollama API and pin the model.** Use only the local API:
   - `curl -s http://127.0.0.1:11434/api/version` and confirm `0.40.13`.
   - `ollama pull mistral-small3.2:24b-instruct-2506-q4_K_M`. A registry download is allowed. If
     the pull fails, **stop and report**.
   - `curl -s http://127.0.0.1:11434/api/tags` and take the entry's `digest` (64 hex) and `size`.
   - `curl -s http://127.0.0.1:11434/api/show -d '{"model":"<tag>"}'` and take `license` (it
     must be Apache 2.0, otherwise **stop and report**) and `details.parameter_size` and
     `quantization_level`.
   - Save trimmed copies of these responses (no prompts) as evidence.
3. **Write the record.** Write `backend/config/local_generation_model.json` with those values,
   the committed limits from the contract, `license: "Apache-2.0"`, a `license_reference`
   (the Ollama `/api/show` licence text header plus the Mistral model card URL), and
   `recorded_on` set to the date of recording.
4. **Add the synthetic fixture.** Write
   `backend/tests/fixtures/local_generation/synthetic_model_record.json`, with `model` set to
   `synthetic-local-model:test`, a fixed fake digest, `recorded_on` 2026-10-01, and
   `license_reference` beginning `SYNTHETIC TEST FIXTURE`.
5. **Change `gemini_generation.py`.** Add the defaulted `provider_name`, `used_outcome`, and
   `log` fields to `GatedGeminiGenerator`, and pass them through `GatedGeminiProvider`. Run
   `tests/test_gemini_generation.py`; it must pass unchanged.
6. **Write `local_generation.py`, in this order:**
   1. constants (`OLLAMA_BASE_URL`, `MEMORY_BUDGET_BYTES = 50_000_000_000`, ranges, blocker and
      outcome codes, `PROVIDER_LOCAL`, `OUTCOME_LOCAL_USED = "local_used"`, the draft JSON
      schema, `OLLAMA_OPTIONS = {"temperature": 0, "seed": 0}`, `MAX_RESPONSE_BYTES = 65536`);
   2. `load_local_model_record` and `evaluate_local_model_record(document, *, as_of) ->
      (GateResult, LocalModelRecord | None)`;
   3. `loopback_opener()`, which uses `ProxyHandler({})` and a redirect handler that raises;
   4. `LocalTransportError(code)`;
   5. `OllamaTransport`;
   6. `resolve_local_provider(env, *, record_document, transport, as_of, clock, pilot,
      review_record)`;
   7. `resolve_startup_generation(...)`.

   Allowed imports: stdlib only (`urllib.request`, `urllib.error`, `socket` only for the timeout
   type, `json`, `re`, `threading`, `dataclasses`, `datetime`, `os`, `pathlib`, `typing`) plus
   `app.*`.
7. **Wire it in.**
   - `main.create_app`: add the keyword-only `local_transport=None` and call
     `resolve_startup_generation`. Keep the startup log line unchanged in shape.
   - `privacy_review.GENERATION_PROVIDERS`: add `local`, and update the docstrings.
8. **Write the tests** in `backend/tests/test_local_generation.py` (see the verification plan),
   with fake openers and fake clocks only. Patch `socket.socket.connect` and
   `socket.create_connection` in the route tests.
9. **Write `backend/scripts/measure_local_generation.py`.** Its arguments are `--catalog`,
   `--passages`, `--cases`, `--active-campaign`, `--as-of`, `--k 5`, `--repeats 3`, and
   `--record` (defaulting to the committed one).
   - Put the pure helpers (`summarize_latencies`, `verified_draft_rate`, `changed_case_ids`,
     `budget_check`) at module level so tests can import them with `importlib`.
   - It builds both apps with dependency overrides, as `evaluate_pac_answers.py` does.
   - It sets `os.environ` for each mode before calling `create_app`, and records outcomes through
     the provider's `log` field.
   - It prints sorted, compact JSON with no question, passage, or answer text.
   - Exit codes: `0` when the run completed and stayed within budget; `1` when it completed but
     over budget; `2` when Ollama was unreachable, the model was missing, the digest differed, or
     the input was invalid.
10. **Update the durable docs** listed in the contract.
11. **Run the focused verify block,** then `CI=true ./scripts/init.sh --fast` if a JDK is
    available.
12. **Run the live measurement** (below) at least twice, and append the evidence.
13. **Update `PROGRESS.md`** following the implementer skill. Report the numbers without any
    recommendation about the Mac.

## Verification plan

Automated, in `backend/tests/test_local_generation.py`; none of these needs Ollama.

- **Record gate.**
  - The committed record passes. Evaluate it with `as_of` set to the real UTC date, not
    `FIXED_DAY`, because the record is dated on or after 2026-10-31.
  - The synthetic fixture passes.
  - A missing or unreadable record gives `unreadable`.
  - An extra or missing key, the wrong schema version, a bool given as an int, a bad digest
    format, a blank licence, or a model with whitespace gives `invalid`.
  - Each bound ±1, and NaN, give `out_of_range`.
  - `size_bytes` equal to 50,000,000,001 gives `over_budget`.
  - A future `recorded_on` gives `future_date`.
- **Resolver.**
  - Run a matrix over provider env (unset, `extractive`, `gemini`, `local`, `Local`), model env
    (unset, mismatched, matched), pilot versus development profile, and review record (committed
    pending versus synthetic approved). Only all-valid inputs give `local`.
  - Unset or `gemini` delegates to `resolve_startup_provider` with identical output.
  - Blockers echo no value.
  - A recording env mapping shows that only the two keys were read.
  - An injected exception gives `generation_provider_unresolved`.
  - With the env unset, `create_app()` never constructs an `OllamaTransport` (patched constructor).
- **Transport (fake opener).**
  - The exact URL sequence: `/api/tags` once, then `/api/chat` for each call.
  - The exact body keys and values, with `stream: false`, the `format` schema, `options`, and
    `keep_alive`.
  - The model-mismatch error.
  - The default opener has no `ProxyHandler` proxies, even with `HTTP_PROXY` and `HTTPS_PROXY`
    set, and a 302 raises.
  - Each error mapping: `connection_refused`, timeout to `TimeoutError`, 404 to
    `model_not_found`, 500 to `http_error`, non-JSON, oversize, or a missing `message.content` to
    `response_invalid`, a model absent from the tags to `model_not_found`, and a different digest
    to `model_digest_mismatch`.
  - A digest failure is not cached; a success is cached.
  - `on_metrics` receives only the six integer fields.
  - Exception strings contain no response text.
- **Default real transport, no Ollama.** With the env set to `local`, the matched model, and the
  synthetic record patched in, `socket.create_connection` is patched to record the address and
  raise `ConnectionRefusedError`. Then:
  - the only address attempted is `("127.0.0.1", 11434)`;
  - `/ask` equals the extractive baseline;
  - the log shows `provider=local outcome=transport_error`.
- **Generator through `/ask`.**
  - A verified draft gives `local_used`; the response validates with `AskResponse`, and the
    notice and lead-in appear once.
  - One test per fallback outcome, each equal to the baseline.
  - Clarification, false premise, conflict, no evidence, invalid request, and stale corpus never
    call the opener.
  - The captured payload equals `minimal_provider_payload(redact_text(...))`, and 15 forbidden
    values are absent: land id, municipality, land name, catalog ids, URLs, titles, issuing body,
    dates, and client id.
- **Guards.**
  - The AST of `local_generation.py` imports no `http.client`-level third-party library
    (`httpx`, `requests`, `aiohttp`), no `google*`, and no `subprocess`.
  - Its source has no `0.0.0.0`, `localhost` override, or env read for a URL.
  - `OLLAMA_BASE_URL` parses to the host `127.0.0.1`.
  - No requirements file changed (compare against the git `HEAD` content, or assert the exact
    known lines).
- **Script helpers.** Run them on synthetic numbers: nearest-rank p95, the rate with a zero
  denominator, `changed_case_ids`, and `budget_check` at the boundary. Run `main()` with a fake
  opener that refuses the connection; it must exit `2` and print no stack trace or text.
- **Regression.** The full backend suite must pass. In particular, `test_gemini_generation.py`,
  `test_privacy_retention.py`, `test_pilot_operations.py`, `test_ask_endpoint.py`, and
  `test_pac_answer_eval.py` pass unchanged.

**Live measurement (manual, opt-in, this Mac only).** Ollama must be running and the pinned model
pulled:

```sh
backend/.venv/bin/python backend/scripts/measure_local_generation.py \
  --catalog knowledge/source_catalog.json --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-31 \
  --k 5 --repeats 3 > /tmp/local-generation-run1.json
```

Run it twice. The second run checks the stability of outcomes and changed cases.

No E2E or app check is needed. The wire contract, shared client, and UI are unchanged, and the
route tests cover `/ask`.

## Evidence to capture

- **Environment:**
  - Python version and the `backend/.venv` link target;
  - the Ollama `/api/version`;
  - the machine: `sysctl -n machdep.cpu.brand_string`, `hw.memsize`, and `sw_vers`;
  - the trimmed `/api/tags` and `/api/show` entries for the pinned tag: tag, digest, size,
    licence id, parameter size, and quantization.
- **The committed record** as written.
- **Verification:** the focused verify block with its pass counts; the baseline and after
  full-suite counts; and the `--fast` result, or the reason it was not run.
- **The committed-state startup log line** with the env unset, and the line with
  `local` + matched model in development.
- **For each live run,** a table with:
  - per-question `/ask` latency, extractive and local (median, p95, max);
  - `send` latency;
  - Ollama `eval_count` and tokens/s;
  - `cold_load_seconds`, plus the cold first-case latency and outcome;
  - peak `/api/ps` `size` and `size_vram`, and peak summed `ollama` RSS, each against
    50,000,000,000 bytes;
  - outcome counts and the verified-draft rate (`local_used` / drafting invocations);
  - side-by-side `answer_eval` aggregates (states, answered, source, passage, critical literal,
    abstentions, unexpected answers);
  - `changed_case_ids`, with the flags that changed;
  - whether the outcomes were identical across repeats.
- **`git diff --stat`** showing no change under `contracts/`, `knowledge/`, `shared/`,
  requirements files, `backend/deploy/`, `pilot_privacy_review.json`, or
  `gemini_provider_limits.json`.
- **Honest limits:**
  - one host, 14 author-only cases, four passages;
  - the same instruction as Gemini, untuned;
  - the verifier is lexical;
  - RSS on unified memory may not include Metal-wired buffers, so `/api/ps` is reported too;
  - Ollama's own logs and update checks are outside the app's control;
  - the Mac-versus-server question is left to the owner.

## Open human decisions (not blocking implementation)

1. **Whether this Mac is enough, or a faster external server is needed.** The owner decides from
   the evidence. This feature records numbers only.
2. **Whether local generation may serve the pilot at all,** and on which host. The gate requires
   a passed pilot review, and the pilot review's `data_flow` scope must explicitly cover local
   model drafting. Recording that is the qualified reviewer's task.
3. **Whether to tune the instruction for the local model,** or try another pinned model (for
   example a faster MoE such as a Qwen3 30B-A3B build). That would be a later feature with new
   measurements.
4. **Whether a warm-up or a longer app timeout is wanted** if cold starts routinely fall back.
   The app timeout is in `shared/` and is out of scope here.

## Feature evidence

<!-- The implementer appends dated evidence below. -->

### 2026-10-31 — implementer self-verification (worktree `integration_chroma_gemini`)

**Environment**

- `./scripts/init.sh --setup-python`: `backend/.venv` ->
  `/Users/agents/StudioProjects/Manijero/.git/manijero-venvs/dev-py3.12.16-e75850911e88`
  (shared environment, Python 3.12.16). No virtualenv was created by hand. No requirements file
  changed.
- Machine: `sysctl -n machdep.cpu.brand_string` = `Apple M5 Max`; `hw.memsize` = `68719476736`;
  `sw_vers` = macOS 27.2 (build 26B123).
- Ollama `/api/version`: `{"version":"0.40.13"}`. `/api/tags` listed no models before the pull.
- Pull: `POST /api/pull {"model":"mistral-small3.2:24b-instruct-2506-q4_K_M"}` through the local
  API ended with `{"status":"success"}` (the main layer was `sha256:41a5b0c36a28…`, 15,177,369,888
  bytes).
- Trimmed `/api/tags` entry: `name` = `model` = `mistral-small3.2:24b-instruct-2506-q4_K_M`;
  `digest` = `5a408ab55df5c1b5cf46533c368813b30bf9e4d8fc39263bf2a3338cfa3b895b` (bare 64 hex, no
  `sha256:` prefix); `size` = `15177384862`; `details.parameter_size` = `24.0B`;
  `details.quantization_level` = `Q4_K_M`; `details.family` = `mistral3`; `capabilities` =
  `completion, vision, tools`.
- Trimmed `/api/show` entry: `license` is the full Apache License, Version 2.0, January 2004 text
  (11,356 chars, sha256 `43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1`, it
  ends with the standard "limitations under the License." clause and carries no extra terms) ->
  recorded as `Apache-2.0`. `details.parameter_size` = `24.0B`, `quantization_level` = `Q4_K_M`;
  `model_info.general.parameter_count` = `24011361280`. The Modelfile has `parameters` =
  `temperature 0.15` and a 2,330-char default `system` prompt. The transport always sends its own
  `system` message and `temperature: 0`. In Ollama, a request's own system message and options
  take the place of these defaults. That is documented Ollama behavior and was not checked
  independently here.
- **Live API field confirmation.** A single synthetic payload went through the real
  `OllamaTransport`; it contained no user or land data. The fields match the planned names:
  - `/api/chat` returned `message.content`, a JSON string whose keys were `answer`, `sources`, and
    `status`.
  - The response carried `total_duration`, `load_duration`, `prompt_eval_count`,
    `prompt_eval_duration`, `eval_count`, and `eval_duration`, all as integers.
  - `/api/ps` entries have the keys `context_length`, `details`, `digest`, `expires_at`, `model`,
    `name`, `runner`, `size`, and `size_vram`.

  Two differences from the plan matter:
  - On 0.40.13, `/api/ps` reports `size` = `size_vram` = 1,534,748,261 bytes, not the 15.18 GB of
    weights.
  - The model runs in a separate `/Applications/Ollama.app/Contents/Resources/llama-server`
    process, not in a process named `ollama`.

**Committed record** (`backend/config/local_generation_model.json`, as written)

`schema_version` `local-generation-model-v1`; `model` `mistral-small3.2:24b-instruct-2506-q4_K_M`;
`digest` `5a408ab55df5c1b5cf46533c368813b30bf9e4d8fc39263bf2a3338cfa3b895b`; `license`
`Apache-2.0`; `license_reference` (the Ollama `/api/show` licence text header plus its sha256, and
the Mistral model card URL); `parameter_size` `24.0B`; `quantization` `Q4_K_M`; `size_bytes`
`15177384862`; `num_ctx` 4096; `timeout_seconds` 10; `max_output_tokens` 400;
`max_requests_per_minute` 30; `max_requests_per_day` 2000; `keep_alive_seconds` 1800;
`recorded_on` `2026-10-31`.

**Automated verification (no Ollama needed)**

- Baseline before any change: `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh
  --backend-tests` -> **1134 passed, 1 skipped**.
- After the `gemini_generation.py` field change, `tests/test_gemini_generation.py` passed
  unchanged (**98 passed**).
- `backend/tests/test_local_generation.py`: **173 tests**. They use only fake openers and fake
  clocks. The real-opener tests patch `socket.create_connection`, and the redirect test uses an
  in-process `http.server` bound to `127.0.0.1:0`.
- `./scripts/init.sh --feature local_generation_provider` -> **exit 0**. Block 1 (the four named
  modules) **355 passed**; block 2 (full backend suite) **1307 passed, 1 skipped**.
- `CI=true ./scripts/init.sh --fast`, with the shell as it was, -> **exit 1**. 8 of 9 checks
  passed; `gradle-jvm-test` failed with "Unable to locate a Java Runtime". `/usr/bin/java` here is
  only the macOS stub and there is no system JDK.
- The same command with `JAVA_HOME` and `PATH` pointing, for this one command, at the
  Gradle-provisioned Azul Zulu 21.0.11 under `~/.gradle/jdks/` (the precedent from the
  `chroma_hybrid_retrieval` evidence) -> **exit 0**: "All 9 offline checks passed. Fast tier
  passed." No system configuration changed.
- `./scripts/init.sh --verify` was not run. No Android, Desktop, shared, packaging, or wire
  contract file changed.

**Startup log lines** (development profile, logger pointed at stdout; each appears twice because
importing `app.main` also builds the module-level app)

- Env unset: `{"blockers":"gemini_not_configured","event":"generation_provider","provider":"extractive",…}`.
  This is the same Gemini resolution as before.
- `MANIJERO_GENERATION_PROVIDER=local` plus the matching `MANIJERO_LOCAL_MODEL`:
  `{"blockers":"","event":"generation_provider","provider":"local",…}`.
- `local` without `MANIJERO_LOCAL_MODEL`:
  `{"blockers":"local_model_mismatch","event":"generation_provider","provider":"extractive",…}`.

**Live measurement** (this Mac only, `measure_local_generation.py --catalog
knowledge/source_catalog.json --passages knowledge/passages.json --cases
knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-31 --k 5 --repeats 3`)

An earlier run at 14:36Z had exit 0 and the same latencies and outcomes. It under-reported RSS
(140 MB) because its sampler matched only process names starting with `ollama` and so missed the
`llama-server` runner. The sampler was fixed to count every process under `Ollama.app`, with a
test added, and both runs below were taken after the fix. Each run took about 66 s, and both
exited with code 0.

| Measure | Run 1 (14:38:22Z) | Run 2 (14:39:29Z) |
|---|---|---|
| Extractive `/ask` s (median / p95 / max, n=14) | 0.0018 / 0.0032 / 0.0032 | 0.0018 / 0.0032 / 0.0032 |
| Local `/ask` s, all 3 repeats (median / p95 / max, n=42) | 1.633 / 2.866 / 4.592 | 1.633 / 2.875 / 4.619 |
| Local `/ask` s, excluding the cold case (n=41) | 1.632 / 2.861 / 2.970 | 1.632 / 2.869 / 2.994 |
| `send` s per repeat (median / p95 / max, n=12) | r1 1.699 / 4.586 / 4.586; r2 1.647 / 2.858 / 2.858; r3 1.642 / 2.852 / 2.852 | r1 1.701 / 4.610 / 4.610; r2 1.647 / 2.861 / 2.861; r3 1.639 / 2.866 / 2.866 |
| Ollama `eval_count` per draft (median / max) | 55 / 96 (each repeat) | 55 / 96 (each repeat) |
| Prompt tokens per draft (median / max) | 539 / 587 | 539 / 587 |
| Decode tokens/s (median per repeat) | 37.53 / 37.62 / 37.41 | 37.44 / 37.53 / 37.61 |
| `cold_load_seconds` (unload, `/api/ps` empty, load-only `/api/generate`) | 2.536 | 2.286 |
| Cold first drafting case (repeat 1, after a second unload) | `canal-sga-2026`, 4.592 s, `local_used` (Ollama `load_duration` 1.279 s) | `canal-sga-2026`, 4.619 s, `local_used` (`load_duration` 1.279 s) |
| Peak `/api/ps` `size` / `size_vram` (budget 50,000,000,000) | 1,534,748,261 / 1,534,748,261 | 1,534,748,261 / 1,534,748,261 |
| Peak summed Ollama RSS (budget 50,000,000,000) | 36,769,447,936 | 37,106,909,184 |
| Within budget (exit code) | yes (0) | yes (0) |
| Memory samples | 119 | 119 |
| Drafting invocations per repeat | 12 of 14 cases (2 not drafted: `campana-no-soportada`, `tema-no-cubierto`) | same |
| Outcomes, all 3 repeats | `local_used` 6, `provider_abstained` 6, `verifier_rejected` 24 | same |
| Verified-draft rate (`local_used` / invocations) | 6/36 = 0.1667 (2/12 per repeat) | 6/36 = 0.1667 |
| Outcomes identical across repeats | yes | yes |
| Changed cases vs extractive (identical across repeats) | `canal-excepcion-persona-fisica-2026`, `canal-sga-2026`: `response_sha256` only | same |

Per-case outcomes were identical in every repeat of both runs:

- `local_used`: `canal-sga-2026`, `canal-excepcion-persona-fisica-2026`.
- `provider_abstained`: `distingue-fechas-2026`, `reclamacion-fuera-de-alcance`.
- `verifier_rejected`: `alcance-terrenos-2026`, `canal-sga-entidades-2026`,
  `fecha-modificacion-2026`, `fecha-presentacion-2026`, `plazo-modificacion-confirma-2026`,
  `plazo-modificacion-inclusive-2026`, `plazo-modificacion-parcelas-2026`,
  `plazo-presentacion-variante-2026`.
- Not drafted (abstained before generation): `campana-no-soportada`, `tema-no-cubierto`.

Side-by-side `answer_eval` aggregates: extractive and every local repeat of both runs are
identical.

| States | Answered | Source | Passage | Critical literal | Abstentions kept | Unexpected answers |
|---|---|---|---|---|---|---|
| 13/14 | 11/11 | 8/11 | 8/11 | 9/11 | 2/3 | 1 |

In both used cases, only `response_sha256` changed. The compared flags (`actual_status`,
`expected_state_match`, `source_match`, `passage_match`, and `critical_facts_match`) did not
change.

**Memory cross-check** (manual, one-off, while the model was loaded)

- With the model resident:
  - `ps -axo pid=,rss=,comm=` showed `Ollama` (app) at 83,040 KiB, `ollama` (server) at
    44,512 KiB, and `llama-server` at 16,364,336 KiB.
  - `footprint -p <llama-server>` reported a phys_footprint of 2,185 MB: 1,510 MB untagged dirty
    and 617 MB malloc-large.
- During an unload followed by a fresh load, sampled every 0.5 s, there was only one
  `llama-server` process. Its RSS rose to 6.5, 13.9, 26.4, and then 35.3 GB, and stayed at about
  35.3 GB while sampled. So the about 37 GB peak above comes from a single runner process right
  after a load, not from two processes overlapping.

**Scope check**

- `git diff --stat` shows changes only in `ARCHITECTURE.md`, `CONSTRAINTS.md`,
  `backend/README.md`, `backend/app/gemini_generation.py`, `backend/app/main.py`,
  `backend/app/privacy_review.py`, `docs/pilot-privacy.md`, `docs/risks-and-open-questions.md`,
  `PROGRESS.md`, and `feature_list.json`, plus the new files in the contract.
- `git diff` is empty (0 lines) for `contracts/`, `knowledge/`, `shared/`, `backend/deploy/`,
  `backend/requirements*.txt`, `pilot_privacy_review.json`, `gemini_provider_limits.json`,
  `scripts/init.sh`, and every existing test file.

**Deviations and clarifications from the plan**

- `loopback_opener()` builds an `OpenerDirector` explicitly instead of calling `build_opener`. It
  has `ProxyHandler({})`, `UnknownHandler`, `HTTPHandler`, `HTTPDefaultErrorHandler`, a
  redirect-refusing handler, and `HTTPErrorProcessor`, and no HTTPS handler at all. The reason:
  `build_opener` adds an `HTTPSHandler` whose SSL context reads `SSLKEYLOGFILE` from the
  environment, which would break the "only two env keys are read" check. HTTPS is never needed for
  loopback, and this version is stricter.
- `ProxyHandler({})` registers no methods, so the tests assert that no proxy-capable handler
  exists. With `HTTP_PROXY` and similar variables set, the real-opener test still dials only
  `("127.0.0.1", 11434)`.
- `OllamaTransport` uses its `clock` so the digest check and the chat share the
  `request.timeout_seconds` budget. The chat timeout is the budget left after the tags call, and
  an exhausted budget raises `TimeoutError`.
- A `request.model` that differs from the record raises `LocalTransportError("model_mismatch")`.
  The contract asks only that this case raise; it did not name a code.
- When the record is unreadable or invalid and `MANIJERO_LOCAL_MODEL` is set, only the record
  blocker is reported, because there is no recorded model to compare against. When the model env
  is unset, `local_model_mismatch` is always reported.
- The script's text-free report adds per-case outcome codes, a `response_sha256` change flag, the
  prompt-token count, Ollama's `load_duration`, and the limits. `cold_load_seconds` was measured
  right after the pull and earlier loads, so the weights were probably in the OS file cache. It is
  a reload time, not a cold-disk read.

**Honest limits**

- One host, 14 author-only cases, and four passages.
- The same `gemini-draft-v1` instruction as Gemini, untuned.
- The verifier is lexical.
- These runs were observed to be deterministic: per-case outcome codes and the set of changed
  cases were identical across repeats. Response hashes were not compared between repeats, and no
  determinism is claimed beyond what was observed.
- RSS counts file-backed mmapped pages, while phys_footprint and `/api/ps` report much smaller
  values. None of these alone is the true memory cost on unified memory; all are reported.
- Ollama's own logs, model cache, and update checks are outside the app's control.
- No claim is made about answer quality, fluency, or legal coverage.
- No recommendation is made on whether this Mac is enough; the owner decides.

### 2026-10-31 — independent validation (accept)

- `./scripts/init.sh --feature local_generation_provider`: exit 0; focused modules 355 passed; full
  backend suite 1307 passed, 1 skipped.
- `CI=true ./scripts/init.sh --fast`: failed only at `gradle-jvm-test` (no Java runtime in the shell);
  rerun with `JAVA_HOME`/`PATH` set for that one command to the Gradle-provisioned Zulu 21.0.11 under
  `~/.gradle/jdks/`: all 9 offline checks passed.
- Protected paths (`contracts/`, `knowledge/`, `shared/`, `backend/deploy/`, requirements files,
  `pilot_privacy_review.json`, `gemini_provider_limits.json`, `scripts/init.sh`, existing tests)
  unchanged; no new dependency.
- Read-only local Ollama queries matched the committed record (tag, digest, size, Apache-2.0 licence
  text hash, 24.0B, Q4_K_M). The live measurement was reviewed, not rerun.
- All eight implementer deviations accepted; see [the acceptance record](../../validations/local_generation_provider.md).

## Validator checklist

- [ ] With the env unset, nothing changes: no `OllamaTransport` is built, no connect happens, and
      the response equals the baseline. Gemini resolution is identical.
- [ ] `local` needs both env keys and a valid committed record. In the pilot profile it also
      needs a passed pilot review. Every blocker is a fixed code that echoes no value.
- [ ] The only network target is `127.0.0.1:11434`, with proxies ignored and redirects refused.
      No new dependency, `requirements*.txt` change, or configurable URL was added.
- [ ] The record pins the exact tag, a 64-hex digest, an Apache-2.0 licence, and a size within
      50 GB, all matching the recorded `/api/tags` and `/api/show` evidence. The transport
      refuses a mismatched digest.
- [ ] The payload is exactly `minimal_provider_payload` of the redacted question plus the
      citation-window excerpts. No land, catalog, URL, metadata, or retained data is included.
- [ ] Every failure class falls back to extractive, never raises, and never emits draft text.
      Logs carry only `provider=local` and a fixed outcome.
- [ ] Accepted local drafts pass `verify_draft` twice. The lead-in, notice, markers, and sources
      stay code-owned. `AskResponse` and `contracts/openapi.yaml` are unchanged.
- [ ] `test_gemini_generation.py`, `test_privacy_retention.py`, and `test_pilot_operations.py`
      pass unchanged. No automated test needs Ollama.
- [ ] The live evidence reports latency, cold start, peak memory, and the verified-draft rate
      against the extractive baseline on the 14 cases, from at least two runs, and makes no
      quality claim or recommendation about the host.
- [ ] Durable docs are updated as listed, and the focused verify block passes as published.
