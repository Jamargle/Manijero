# Feature Spec: `gemini_generation_provider`

## Source metadata

- **Feature:** `gemini_generation_provider` — Integrate gated Gemini answer generation (`backend`).
- **Status at planning:** `not_started`; depends on accepted `grounded_answer_generation`,
  `backend_answer_evaluation`, `hosting_provider_review`, and `pilot_privacy_readiness`.
- **Source behavior:** Implement a replaceable Gemini client and structured draft output, but keep
  outbound calls disabled until the exact current model, official terms, data flows, cost/rate
  limits, and qualified privacy/legal review are recorded and approved. Never send land names/notes
  or stable identifiers. Every draft passes the existing whole-draft verifier; citations, sources,
  notices, and abstentions remain code-owned. Retain extractive generation as a safe fallback.
- **Feature-list verification:** Implementation, operational evidence, focused verification, and
  limits are recorded before acceptance. No legal-coverage or answer-quality claim is implied by
  successful automation.
- **Owner constraints for this run (2026-10-31):** no real network call to Google and no API key or
  secret read, looked for, or required — by the code or its tests; tests use an injected fake
  transport only; no new pip dependency (no Google SDK); only the minimal payload is sent; extractive
  generation is the fallback on every failure; the app wire contract is unchanged.
- **Replanned 2026-10-31** over the accepted `pilot_privacy_readiness` gate
  (`backend/app/privacy_review.py`, `backend/config/pilot_privacy_review.json`) and the
  `hosting_provider_review` decision (model/tier, quotas, and limits deliberately unresolved).

## Goal and boundaries

Add a replaceable, gated Gemini drafting path behind the existing `GroundingGenerator` seam so a
later reviewed change can turn it on without redesign, while today it provably cannot reach Google:
this repository ships **no real transport**, so the effective provider stays `extractive` in every
deployment until a separate reviewed change supplies one.

**In scope:**

- A new `backend/app/gemini_generation.py`: a narrow `GeminiTransport` protocol (the only seam that
  could ever touch a network), a `GeminiDraftClient` that builds a code-owned request and strictly
  parses a structured draft, a `GatedGeminiGenerator` implementing `GroundingGenerator` with
  verify-then-fallback, an in-process rate limiter, and a provider resolver.
- A recorded, reviewable limits file `backend/config/gemini_provider_limits.json`
  (`gemini-provider-limits-v1`), committed with every value `null`, so the gate stays closed until
  timeout, output-token, rate, and cost limits are recorded by a person.
- Wiring the resolved provider into `POST /ask` through `create_app` and a FastAPI dependency, with
  fixed-code operational logging only.
- Focused tests with a fake transport, a fake clock, synthetic review/limits fixtures, and guards
  that the module has no network import, no secret/env read beyond the two existing settings, and
  that no Google dependency was added.

**Non-goals:** a real HTTP/SDK transport, endpoint URL, credential/API-key handling, or region/tier
selection (a later reviewed change); choosing or recording a model id; changing
`pilot_privacy_review.json` or its schema; changing `verify_draft`, `generate_grounded_answer`,
abstention, clarification, or `contracts/openapi.yaml`; prompt tuning or any answer-quality,
fluency, or legal-coverage claim; sending land context, land ids, catalog ids, URLs, titles, or
retained text; streaming, caching, or retries; pilot preflight/backup changes.

## Job story

When the owner later approves Gemini for the private pilot, I want a drafting path that already
sends only the minimal payload, is checked by the same verifier, and falls back to today's
extractive answer on any problem, so enabling a model cannot weaken grounding, privacy, or the app
contract — and until then nothing can leave the service.

## Acceptance scenarios

### Gate closed by default (committed state)

Given the committed review record (`pending`) and limits file (all `null`), and any combination of
`MANIJERO_GENERATION_PROVIDER` / `MANIJERO_GEMINI_MODEL`, when the app is created and `/ask` is
called, then no transport method is invoked, no socket connect is attempted, the JSON response
equals the extractive baseline, and one startup `generation_provider` log line carries
`provider=extractive` and fixed blocker codes only.

### Every gate input is required

Given a fake transport and the synthetic approved review and limits fixtures, when any single input
is missing or wrong — provider not `gemini`, model env unset or not equal to the reviewed `model`,
pilot or Gemini review not passed, limits file unreadable/invalid/any `null`/out of range/future
`recorded_on`, or no transport injected (`gemini_transport_unavailable`) — then the resolver returns
no Gemini provider and `/ask` matches the extractive baseline. Only with all inputs valid does the
Gemini path run.

### Minimal payload only

Given an active Gemini path and a `selected`/`all_active` request whose land context has ids and a
municipality, and a question that contains a land name after a land word and the municipality, when
the generator drafts, then the transport receives exactly: the configured model id, the pinned
code-owned instruction and its version, `max_output_tokens` from limits, and a user payload equal to
`minimal_provider_payload(redact_text(question, land_context_values(land_context)), [{"passage_id":
"<candidate number>", "text": <reviewed excerpt>} ...])`. The captured request contains no land id,
municipality, land name, catalog `passage_id`/`source_id`, URL, title, issuing body, date
metadata, as-of date, campaign, client id, or retained text.

### Verified Gemini draft is used, code still owns the answer shell

Given the fake transport returns a well-formed draft whose every sentence cites offered candidate
numbers and passes `verify_draft`, when `/ask` runs, then the response is assembled by the existing
code: lead-in, dense `[n]` markers, `sources` from retrieval, and the pinned notice; the response
validates against the unchanged `AskResponse` model and keys.

### Fallback to extractive on every failure

Given an active Gemini path, when the transport raises, raises `TimeoutError`, exceeds the
configured timeout on the injected clock, returns non-JSON, fenced/extra-key/wrong-type JSON, an
oversize output, an unknown or duplicated candidate number, a draft containing the pinned notice,
lead-in, or a URL, a `status: "abstained"` draft, or a draft that `verify_draft` rejects (including
`eligibility_claim`, `figure_unsupported`, `critical_not_literal`), or the rate limit is reached, or
redaction raises, then no text of that draft reaches the response, the extractive draft is used,
and the `/ask` response equals the extractive baseline for that question. One `generation` log line
records `provider=gemini` and a fixed `outcome` code; never question, passage, or draft text.

### Pipeline order is unchanged

Given a question that today yields a land clarification, `false_premise`, `conflicting_evidence`,
`no_evidence`, an invalid question, or a stale corpus, when the Gemini path is active, then the
transport is never called and the response is unchanged.

### Nothing reaches Google and no secret is read

Given the test suite, when it runs, then `backend/app/gemini_generation.py` imports no network
module (`socket`, `ssl`, `http`, `urllib`, `httpx`, `requests`, `aiohttp`, `google`), the provider
reads only `MANIJERO_GENERATION_PROVIDER` and `MANIJERO_GEMINI_MODEL` from the environment (no key,
token, or credential name is read or looked for), and no `backend/requirements*.txt` or
`backend/deploy/requirements-production.txt` names a Google package.

## Technical approach

1. **Limits record.** `gemini_provider_limits.json` keys exactly: `schema_version`,
   `timeout_seconds` (number, 1–30), `max_output_tokens` (int, 1–2048), `max_requests_per_minute`
   (int, 1–600), `max_requests_per_day` (int, 1–100000), `cost_reference` (non-blank string pointing
   at the recorded pricing/spend-cap decision), `recorded_on` (ISO date, not in the future). Booleans
   are not ints. `evaluate_gemini_limits(document, *, as_of) -> (GateResult, GeminiLimits | None)`
   emits fixed blockers `gemini_limits_unreadable`, `gemini_limits_invalid`,
   `gemini_limits_not_recorded`, `gemini_limits_out_of_range`, `gemini_limits_future_date`.
2. **Resolver.** `resolve_generation_provider(env, *, record, limits_document, transport, as_of,
   clock)` calls the existing `decide_generation_provider` and `evaluate_gemini_review` unchanged,
   adds the limits gate and `gemini_transport_unavailable` when `transport is None`, and returns a
   `ProviderResolution(provider, blockers, gemini)` where `gemini` is a `GatedGeminiProvider` only
   when every gate passes. The model id comes from the env value that matched the review record.
3. **Client.** `GeminiDraftClient(transport, model, limits)` builds a frozen `GeminiDraftRequest(model,
   instruction, instruction_version, payload_json, max_output_tokens, timeout_seconds)`; the
   instruction is a pinned Spanish constant (`GEMINI_INSTRUCTION_VERSION = "gemini-draft-v1"`) telling
   the model to answer only from the numbered passages, end every sentence with `[n]`, copy figures and
   critical text literally, never assert eligibility, and add no notice, lead-in, or link. The transport
   contract is `send(request) -> str` (the model's text output); mapping to a vendor wire format is
   the future real transport's job. `parse_draft(text, offered)` accepts only a JSON object with keys
   exactly `status` (`answered`|`abstained`), `answer` (str, non-blank and ≤ 1200 chars when
   answered), and `sources` (unique non-bool ints within the offered candidate numbers); raw text over
   8192 chars, code fences, the pinned `NOTICE` or `LEAD_IN`, or `http://`/`https://`/`www.` is
   malformed.
4. **Generator.** `GatedGeminiGenerator.generate(question, numbered_candidates, *, as_of)`: take a rate
   slot (thread-safe, injected monotonic/day clock); build the payload with `minimal_provider_payload`
   using the redacted question and `str(rank)` handles; call the client; discard the result if the
   clock shows the timeout exceeded; map to `DraftAnswer`; run `verify_draft`; return it only when
   `ok`. Every other path returns `ExtractiveGroundingGenerator(max_claims).generate(...)` and records
   one outcome: `gemini_used`, `rate_limited`, `redaction_failed`, `payload_invalid`, `transport_error`,
   `timeout`, `malformed_output`, `provider_abstained`, `verifier_rejected`. It never raises.
   `generate_grounded_answer` then verifies the returned draft again, unchanged.
5. **Wiring.** `create_app(..., generation_transport=None, generation_clock=None)` resolves once at
   startup from `os.environ`, `load_review_record()`, and `load_gemini_limits()`, logs
   `generation_provider` (provider plus comma-joined blocker codes), and stores the resolution in
   `app.state`. `ask_api.get_generation_provider` reads it; `_answer` passes
   `provider.generator_for(land_context)` (or `None`) to `answer_with_clarification`. No request or
   response model changes.

## Expected file changes

- Create `backend/app/gemini_generation.py`.
- Create `backend/config/gemini_provider_limits.json` (all values `null`).
- Update `backend/app/main.py` (two keyword-only `create_app` seams, startup resolution and log).
- Update `backend/app/ask_api.py` (`get_generation_provider` dependency; pass the generator).
- Update docstrings only in `backend/app/privacy_review.py` and the `GroundingGenerator` docstring in
  `backend/app/generation.py`; no behavior change in either.
- Create `backend/tests/test_gemini_generation.py`,
  `backend/tests/fixtures/privacy/synthetic_gemini_limits.json` (labelled synthetic), and reuse
  `backend/tests/fixtures/privacy/synthetic_approved_review.json`.
- Do not change `contracts/`, `knowledge/`, `shared/`, requirements files, or
  `backend/config/pilot_privacy_review.json`.

## Visual design impact

None. No app, copy, or contract change.

## Durable documentation impact

- `ARCHITECTURE.md`: update — the Gemini sentence must describe the gated generator, the limits
  file, the absent transport, and verify-then-fallback.
- `CONSTRAINTS.md`: update — add a MUST block: a model draft reaches `/ask` only through
  `GatedGeminiGenerator` (verify, else extractive); payload is the redacted question plus
  candidate-numbered excerpts; no transport, endpoint, credential, or Google dependency may be added
  except by a reviewed change that also records the model, limits, and both reviews; the limits file
  may only become non-null through a reviewed change.
- `backend/README.md`: update the env table rows for the two settings and add a short "Gated Gemini
  drafting" section (gate inputs, blocker/outcome codes, restart to re-resolve).
- `docs/pilot-privacy.md`: update the Gemini data-flow row and the Gemini gate bullet.
- `docs/risks-and-open-questions.md`: update the Gemini row (code exists; transport, model, limits,
  reviews outstanding).
- `AGENTS.md`, `DESIGN.md`, `CONTEXT.md`: not needed — no routing, UI, or domain-term change.

## Focused verification

Requires a worktree-local `backend/.venv` with Python >= 3.10 and `backend/requirements-dev.txt`
installed (see appendix). No step uses the network or a key.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_gemini_generation.py
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`gemini_generation_provider.appendix.md`](../archive/specs/gemini_generation_provider.appendix.md).
