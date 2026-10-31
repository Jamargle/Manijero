# `gemini_generation_provider` acceptance

## Verdict

**Accepted** on 2026-10-31 after independent validation. No revise round was needed. The spec was
refreshed by the planner before implementation, because the original batch template predated the
accepted `pilot_privacy_readiness` and `hosting_provider_review` gates.

## Independent verification

- `./scripts/init.sh --feature gemini_generation_provider` passed (exit 0). The focused
  `tests/test_gemini_generation.py` and the full backend suite ran, with **1066 passed** (968
  baseline plus 98 new; no existing test changed).
- The no-device fast-tier evaluators were run directly with `AS_OF=2026-10-13` and all exited 0:
  `contracts/validate_examples.py`, `evaluate_generation.py`, `evaluate_land_safety.py`, and
  `evaluate_abstention.py`.
- The Gradle `:shared:jvmTest` job **was not run**: the shell has no Java runtime, and a non-offline
  Gradle run would conflict with the no-network rule for this session. This is acceptable for this
  backend-only change, which touches no Kotlin, `shared/`, or contract file.
- Committed-state probe: `resolve_startup_provider()` with `MANIJERO_GENERATION_PROVIDER=gemini`
  resolves to `extractive`, with blockers ending `gemini_limits_not_recorded,gemini_transport_unavailable`.
- Adversarial probe: deeply nested JSON (about 4000 levels, under the 8192-character cap) raises
  `MalformedDraftError` and falls back to extractive; no recursion error escapes.
- `git diff main` shows no change under `contracts/`, `knowledge/`, `shared/`,
  `backend/requirements*.txt`, `backend/deploy/`, or `backend/config/pilot_privacy_review.json`.
- Guard tests cover the following:
  - an AST import allow-list for the module (no network library and no Google package);
  - a source scan with no `API_KEY`, `getenv`, or `environ.get`;
  - a check that only `MANIJERO_GENERATION_PROVIDER` and `MANIJERO_GEMINI_MODEL` are read;
  - a check that no requirements file names a Google package.
- No real network call was made and no API key or secret was read at any point.

## Accepted scope

- `backend/app/gemini_generation.py` provides:
  - a replaceable `GeminiTransport` seam;
  - a strict `{status, answer, sources}` draft parser;
  - a thread-safe per-process minute/day rate limiter on an injectable clock;
  - a generator that redacts the question and sends only `minimal_provider_payload` (the question
    plus approved passage excerpts labelled by candidate rank);
  - a step that runs `verify_draft` and otherwise returns the extractive draft, logging one fixed
    outcome code;
  - a startup resolver that never raises.
- The gate requires all three of these:
  - the existing pilot and Gemini review with an exact model match;
  - the new `backend/config/gemini_provider_limits.json` (`gemini-provider-limits-v1`), committed
    all-`null`;
  - an injected transport.

  The repository ships no transport, so generation is extractive everywhere.
- The app wire contract and `AskResponse` are unchanged. `create_app` gains two keyword-only test
  seams, `generation_transport` and `generation_clock`.
- Accepted deviation: only the first `max_claims` (2) candidates, the citation window, are offered
  to the model. These are the same candidates the land-clarification and unit-conflict pre-checks
  inspect. A draft citing outside that window is treated as `malformed_output` and falls back.

## Honest limits

1. No model was called. There is no evidence on answer quality, latency, cost, or legal coverage.
2. `verify_draft` checks wording, not meaning. A non-critical paraphrase is checked only for markers,
   figures and dates, and eligibility phrases.
3. The timeout is checked after `send` returns. A future real transport must enforce
   `timeout_seconds` itself.
4. The rate limits apply per process (per worker), not per host. A rate slot is consumed before
   redaction, so a failed redaction still counts against the limit.
5. Human decisions are still needed before the gate can open:
   - the exact model id, revision, and tier;
   - the qualified pilot and Gemini privacy/legal reviews;
   - the limits and spend-cap values;
   - a separately reviewed real transport (endpoint, region, credential storage outside the repo,
     and Google-side logging settings).
