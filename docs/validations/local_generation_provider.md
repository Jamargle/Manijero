# `local_generation_provider` acceptance

## Verdict

**Accepted** on 2026-10-31 after independent validation. No revise round was needed.

## Independent verification

- `./scripts/init.sh --feature local_generation_provider` passed (exit 0): the four named
  modules gave **355 passed**, and the full backend suite gave **1307 passed, 1 skipped**
  (1134 baseline plus 173 new; no existing test changed).
- `CI=true ./scripts/init.sh --fast` failed only at `gradle-jvm-test` because the shell has no
  Java runtime. The same command, with `JAVA_HOME`/`PATH` pointed for that one command at the
  Gradle-provisioned Azul Zulu 21.0.11 under `~/.gradle/jdks/`, passed: "All 9 offline checks
  passed." No system configuration was changed.
- `git diff --quiet HEAD` is clean for `contracts/`, `knowledge/`, `shared/`, `backend/deploy/`,
  `backend/requirements*.txt`, `pilot_privacy_review.json`, `gemini_provider_limits.json`,
  `scripts/init.sh`, `test_gemini_generation.py`, `test_privacy_retention.py`, and
  `test_pilot_operations.py`. No new dependency.
- Read-only queries to the local Ollama API: `/api/version` is 0.40.13, and `/api/tags` lists
  `mistral-small3.2:24b-instruct-2506-q4_K_M` with digest
  `5a408ab55df5c1b5cf46533c368813b30bf9e4d8fc39263bf2a3338cfa3b895b` and size 15,177,384,862,
  both matching the committed record. `/api/show` returns an 11,356-character Apache License 2.0
  text (sha256 `43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1`), `24.0B`, and
  `Q4_K_M`. The model template renders each request message's role and content, which supports
  (but does not prove at runtime) that the request's system message and options replace the
  Modelfile defaults (`temperature 0.15`, the built-in system prompt).
- The live measurement was not rerun. The implementer's two runs in the appendix evidence were
  reviewed for internal consistency and honesty.

## Accepted scope

- `backend/app/local_generation.py` provides:
  - the `local-generation-model-v1` record gate;
  - `OllamaTransport`, which talks only to the `OLLAMA_BASE_URL` loopback constant, has no
    proxy, no redirect, and no HTTPS handler, checks the digest lazily, reads at most 65,536
    bytes, and raises fixed error codes only;
  - `resolve_startup_generation`, which needs both env keys, needs a passed pilot review in the
    pilot profile, and never raises.
- `GatedGeminiGenerator`/`GatedGeminiProvider` are reused with three defaulted fields
  (`provider_name`, `used_outcome`, `log`); Gemini behavior is unchanged.
- `create_app` gains the `local_transport` seam; `privacy_review.GENERATION_PROVIDERS` accepts
  `local`.
- `backend/scripts/measure_local_generation.py` is an opt-in, text-free measurement that makes no
  recommendation.
- Accepted deviations:
  - the opener is assembled without an HTTPS handler (so `SSLKEYLOGFILE` is never read);
  - a `model_mismatch` transport code;
  - the digest check and the chat share the 10 s budget;
  - a record blocker takes precedence over the model-env comparison;
  - the memory sampler counts every process under `Ollama.app` (the model runs in
    `llama-server`);
  - the report has extra text-free fields;
  - the `/api/tags` digest is bare 64-hex.

## Measured results (implementer evidence, owner's Apple M5 Max, 64 GB)

- Warm local `/ask` median is about 1.63 s and p95 about 2.87 s; the cold first drafting case
  took 4.6 s (`local_used`); `cold_load_seconds` was 2.3–2.5 s, a reload that probably hit the
  OS file cache.
- Peak summed Ollama RSS was about 37 GB; `/api/ps` reported 1.53 GB. Both are under the
  50,000,000,000-byte budget.
- Verified-draft rate: 6/36 (0.1667), identical across repeats and runs.
- `answer_eval` aggregates are identical to extractive: 13/14 states, 11/11 answered, 8/11
  source, 8/11 passage, 9/11 critical literal, 2/3 abstentions, 1 unexpected answer.

## Honest limits

1. One host, 14 author-only cases, four passages; the untuned `gemini-draft-v1` instruction; a
   lexical verifier.
2. No single memory figure is the true unified-memory cost: RSS includes mmapped file pages, and
   `/api/ps` on 0.40.13 under-reports the weights. All figures are reported.
3. That the request's system prompt and temperature override the model's defaults was inferred
   from Ollama behavior and the template, not observed directly.
4. The 65,536-byte cap also applies to `/api/tags`; with very many installed models the digest
   check would fail closed (extractive fallback).
5. Ollama's own logs, model cache, and update checks are outside the app's control.
6. No claim about answer quality, fluency, or legal coverage, and no recommendation on whether
   this Mac is enough. The owner decides that later.
