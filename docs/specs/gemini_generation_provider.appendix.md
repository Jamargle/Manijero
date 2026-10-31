# `gemini_generation_provider` planning appendix

On-demand record for the contract in
[`gemini_generation_provider.md`](gemini_generation_provider.md). Replanned 2026-10-31 over the
accepted `pilot_privacy_readiness` and `hosting_provider_review` work; the earlier generic batch
template is superseded.

## Repository research

Inspected on 2026-10-31 in worktree `feature/gemini_generation_provider` (clean at `dd16fe7`):

- `backend/app/generation.py` — `DraftAnswer(status, answer, source_markers)` already mirrors the
  projected `{"status","answer","sources"}` draft; `GroundingGenerator` is the seam (`generate(question,
  numbered_candidates, *, as_of) -> DraftAnswer`); `ExtractiveGroundingGenerator(max_claims=2)` is the
  only implementation; `verify_draft` enforces markers, uncited sentences, figures/dates, critical
  literal substrings, the eligibility phrase list, and size; `generate_grounded_answer` converts a
  raising generator into `NotAnswered("generation_error")` (an abstention, **not** an extractive
  fallback) — so the fallback must live inside the Gemini generator. `LEAD_IN`, `NOTICE`, and
  `MAX_ANSWER_CHARS = 1200` are module constants.
- `backend/app/privacy_review.py` — `evaluate_gemini_review` (pilot gate + `gemini_review` section,
  exact `model` vs `MANIJERO_GEMINI_MODEL`, `data_sent ⊆ {question, approved_passages}`),
  `decide_generation_provider` (always `provider="extractive"`), `generation_provider_problem`, and
  `minimal_provider_payload(question, passages)` (returns only `question` and `{passage_id, text}`
  items; rejects a blank question or non-string fields). Blockers are fixed codes; no record value is
  echoed.
- `backend/config/pilot_privacy_review.json` — both sections `pending`, `model: null`,
  `data_sent: []`. CONSTRAINTS.md requires it change to approved only via a reviewed change with a real
  dated review.
- `backend/tests/fixtures/privacy/synthetic_approved_review.json` — labelled synthetic approval with
  `model: "synthetic-model-for-tests"`, dated 2026-10-01; tests use `FIXED_DAY = date(2026, 10, 13)`.
- `backend/tests/test_privacy_retention.py` — existing Gemini gate tests, including
  `test_even_a_passed_gemini_gate_keeps_the_extractive_path` and
  `test_configured_gemini_makes_no_network_request_on_ask` (monkeypatches `socket.socket.connect` and
  `socket.create_connection`); both must keep passing unchanged. `_app()` builds `create_app(...)` with
  dependency overrides; `PERSONAL_QUESTION` and `SINGLE_LAND` are reusable privacy probes.
- `backend/app/abstention.py` / `backend/app/clarification.py` — `answer_with_clarification(question,
  land_context, corpus, *, k, max_claims=DEFAULT_MAX_CLAIMS, as_of, generator=None)` forwards
  `generator` to `answer_or_abstain`, which runs presupposition and unit-conflict pre-checks before
  `generate_grounded_answer`. Clarification decisions return before any drafting.
- `backend/app/ask_api.py` — `_answer` calls `answer_with_clarification` without a generator; the
  request carries `land_context` with opaque `id`, optional `municipality`, `water_regime`,
  `production_method`. Response models are closed (`extra="forbid"`).
- `backend/app/main.py` — `create_app(config, retention_store=...)` stores per-app state and logs
  fixed codes via `operational_log`; module-level `app = create_app()` runs at import, so startup
  resolution must never raise.
- `backend/app/redaction.py` — `redact_text(text, land_values)` and `land_context_values(land_context)`
  raise `RedactionError` on invalid input; they replace land-context values, names after land words,
  and identifiers (also slash dates such as `30/04/2026`).
- `backend/app/pilot_logging.py` — `operational_log(event, **fields)` keeps primitive fields only.
- `backend/app/pilot_ops.py` — preflight calls `decide_generation_provider` and reports
  `generation_provider`; not changed by this feature.
- `backend/requirements.txt` (`fastapi`, `uvicorn[standard]`, `httpx`), `requirements-dev.txt`
  (`pytest`, `jsonschema`) — no Google package; none is needed because no real transport is built.
- `scripts/init.sh` — `--backend-tests [targets]` runs `pytest` from `backend/` with targets relative to
  `backend/`; `pytest_python` tries `MANIJERO_PYTHON`, `.venv`, `backend/.venv`, then `python3`.
  `--feature <id>` runs this spec's verify block from the repository root.
- `docs/specs/hosting_provider_review.md` — model/tier unselected, quotas and limits not reviewed,
  Paid tier required for EEA API clients, 55-day abuse/log retention; "disable Gemini by keeping the
  provider call absent and the key unset".
- `ARCHITECTURE.md` line 39, `CONSTRAINTS.md` (Answer grounding; pilot privacy block at lines
  204–228; Hosted pilot and provider boundaries), `docs/pilot-privacy.md` (Gemini row, gate
  bullet), `docs/risks-and-open-questions.md` (Gemini row), `backend/README.md` (env table lines
  161–162).

Not inspected: `MasterPlanV3.md` §8.1 beyond the `DraftAnswer` docstring that cites it; Google's
current API reference (intentionally — the vendor wire format is out of scope).

## Design decisions

- **No real transport in this feature.** The strongest guarantee that outbound calls stay disabled
  is that no code path can make one. `create_app` defaults `generation_transport=None`, which is a
  gate blocker; only tests inject a fake. Adding a real transport, endpoint, credential handling,
  region/tier, and Google-side logging settings is a later reviewed change.
- **Candidate numbers, not corpus ids.** The payload handle is `str(rank)`, matching the verifier's
  marker semantics, so no catalog `passage_id`/`source_id` leaves the service.
- **Redacted question.** The server cannot see land names, but it can apply the accepted
  `redact_text` with the request's land-context values; this is a strict subset of the reviewed
  `question` data class. Redaction failure falls back.
- **Verify inside, verify again.** The Gemini generator runs `verify_draft` itself so a rejected
  draft can fall back to extractive instead of becoming an abstention; the unchanged pipeline then
  verifies whichever draft is returned.
- **Model abstention falls back.** A model `abstained` draft is not trusted to suppress an answer
  the accepted extractive path would give; behavior equals today's.
- **Limits as a separate record.** The review schema is accepted and strict; cost/rate limits are an
  operator record, not a privacy review field, so they get their own file and gate.
- **Startup resolution.** Resolved once per app; config changes need a restart. Simple, logged, and
  fail-closed.

## Implementation plan

1. Prepare the environment: `python3 --version` (>= 3.10), then
   `python3 -m venv backend/.venv && backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt`.
   Run the full backend suite once to record the baseline.
2. Add `backend/config/gemini_provider_limits.json` (all values `null`) and
   `backend/tests/fixtures/privacy/synthetic_gemini_limits.json` (values in range, `recorded_on`
   `2026-10-01`, `cost_reference` beginning `SYNTHETIC TEST FIXTURE`).
3. In `gemini_generation.py`, implement in order: constants and outcome/blocker codes;
   `load_gemini_limits(path=None)` and `evaluate_gemini_limits`; `GeminiTransport` protocol and
   `GeminiDraftRequest`; `GEMINI_INSTRUCTION` and version; `parse_draft`; `GeminiDraftClient`;
   `RateLimiter` (lock, per-minute sliding window and per-UTC-day count on an injected clock);
   `GatedGeminiGenerator`; `GatedGeminiProvider.generator_for(land_context)`;
   `resolve_generation_provider`. Allowed imports: stdlib `dataclasses`, `datetime`, `json`, `os`,
   `pathlib`, `threading`, `time`, `typing`, plus `app.generation`, `app.privacy_review`,
   `app.redaction`, `app.retrieval`, `app.pilot_logging`.
4. Write `backend/tests/test_gemini_generation.py` before wiring (unit level), covering the
   scenarios below with a recording fake transport and fake clock.
5. Wire `create_app` (keyword-only `generation_transport=None`, `generation_clock=None`) and
   `ask_api.get_generation_provider` + `_answer`. Add route-level tests through `TestClient` using the
   fixture corpus pattern from `test_privacy_retention.py` and patched review/limits loaders.
6. Update docstrings in `privacy_review.py` (Gemini client now exists but has no transport) and
   `generation.py` (`GroundingGenerator`). Do not change behavior.
7. Update durable docs listed in the contract; append Feature evidence; update `PROGRESS.md` per the
   implementer skill.
8. Run the focused verify block, then `./scripts/init.sh --fast` if the toolchain is available.

## Verification plan

Test cases in `backend/tests/test_gemini_generation.py` (names indicative):

- Limits: committed file → `gemini_limits_not_recorded`; missing/unreadable → `unreadable`; extra or
  missing key, wrong schema version, bool-as-int → `invalid`; each bound ±1 → `out_of_range`; future
  `recorded_on` → `future_date`; synthetic fixture passes.
- Resolver: matrix over provider env, model env (unset/mismatch/match), committed vs synthetic
  review, committed vs synthetic limits, transport `None` vs fake → Gemini only when all pass; blockers
  are fixed codes and contain no env or record value.
- Env access: a recording `Mapping` passed as `env` shows only the two allowed keys were read.
- Payload: captured request for a `PERSONAL_QUESTION`-style question with `SINGLE_LAND` contains none
  of the land id, municipality, land name, catalog ids, URLs, titles, issuing body, dates metadata;
  passage handles are `"1".."k"`; text equals the excerpts; `max_output_tokens`/`timeout_seconds` come
  from limits; model equals the matched env value; instruction version pinned.
- Parse: well-formed answered draft accepted; each malformed class rejected (non-JSON, fenced JSON,
  extra/missing keys, wrong types, bool in `sources`, duplicate or unoffered numbers, blank or >1200
  answer, >8192 raw, contains `NOTICE`, `LEAD_IN`, or a URL).
- Generator outcomes: one test per outcome code asserting the returned draft equals the extractive
  draft (or the Gemini draft for `gemini_used`), the generator never raises, and the log line has
  only `event`, `time`, `provider`, `outcome`.
- Rate limiter: N+1th call within a minute and over the daily cap → `rate_limited` and no transport
  call; window rolls over with the fake clock; concurrent calls under threads never exceed the cap.
- Route: committed state + fake transport → transport never called and response equals baseline;
  synthetic approval + well-formed fake draft → answered response validated by `AskResponse`, notice
  and lead-in present once, dense markers; synthetic approval + rejecting draft → response equals
  baseline; clarification/false-premise/conflict/no-evidence/invalid/stale inputs → transport never
  called; `socket.socket.connect` patched to fail throughout.
- Guards: AST of `gemini_generation.py` imports no `socket`, `ssl`, `http`, `urllib`, `httpx`,
  `requests`, `aiohttp`, `google*`; module source mentions no `API_KEY`/`GOOGLE_`/`api_key`;
  requirements files name no `google` package.
- Regression: full backend suite, especially `test_generation.py`, `test_abstention.py`,
  `test_clarification.py`, `test_privacy_retention.py`, `test_ask_endpoint.py`,
  `test_pilot_operations.py`, `test_pac_answer_eval.py`.

No E2E or app check is needed: the wire contract, shared client, and UI are unchanged, and route
tests cover `/ask`.

## Evidence to capture

- Python version and venv path used; the two verify commands with pass counts.
- Baseline vs after full-suite counts.
- The committed-state startup log line (`generation_provider`, `provider=extractive`, blockers).
- A sample captured fake-transport request (synthetic data) demonstrating the minimal payload.
- `git diff --stat` showing no change under `contracts/`, `knowledge/`, `shared/`, requirements
  files, or `backend/config/pilot_privacy_review.json`.
- Honest limits: no real model was called; no answer-quality, latency, cost, or legal-coverage
  evidence exists; the verifier's checks are lexical, so a non-critical paraphrase is checked only for
  markers, figures/dates, and eligibility phrases.

## Open human decisions (do not guess; keep the gate closed)

1. Exact Gemini model id/revision and tier (Paid required for EEA API clients) — record in
   `gemini_review.model` and `MANIJERO_GEMINI_MODEL` only after review.
2. Qualified pilot and Gemini privacy/legal reviews in `pilot_privacy_review.json`.
3. Timeout, output-token, per-minute and per-day request limits, and the cost/spend-cap reference in
   `gemini_provider_limits.json`.
4. A real transport: endpoint, region routing, credential storage outside the repository, provider-side
   logging/retention settings, and whether a Google dependency is justified — a separate reviewed
   feature. Until it exists, `private_pilot_distribution` cannot use Gemini.

## Feature evidence

<!-- The implementer appends dated evidence below. -->

### 2026-10-31 — implementer self-verification

Environment: worktree-local `backend/.venv`, Python 3.12.16, pytest 8.4.2. No network call, no
key/secret/env file read; every Gemini call in tests goes to an in-process `FakeTransport`.

- `./scripts/init.sh --feature gemini_generation_provider` (exit 0):
  - `--backend-tests tests/test_gemini_generation.py` → **98 passed**
  - `--backend-tests` (full suite) → **1066 passed** (baseline before this feature: 968 passed;
    +98 new, 0 changed or removed). `test_privacy_retention.py` Gemini tests pass unchanged.
- `CI=true ./scripts/init.sh --fast`: not run as a whole. Its `gradle-jvm-test` job could resolve
  dependencies from remote Maven repositories (including Google's), which conflicts with this run's
  no-network constraint; `./gradlew --offline :shared:jvmTest` then failed with "Unable to locate a
  Java Runtime" in this shell. No Kotlin/shared file changed. Every other fast-tier job was run
  directly with the same arguments and `AS_OF=2026-10-13`, all exit 0: `contracts/validate_examples.py`,
  `validate_source_catalog.py`, `evaluate_retrieval.py`, `evaluate_generation.py`,
  `evaluate_abstention.py`, `evaluate_clarification.py`, `evaluate_land_safety.py` (backend tests are
  the full suite above).
- Committed-state startup log (env `MANIJERO_GENERATION_PROVIDER=gemini`,
  `MANIJERO_GEMINI_MODEL=synthetic-model-for-tests`, no transport):
  `{"blockers":"pilot_privacy_review_not_passed,gemini_review_pending,gemini_review_undated,gemini_review_qualification_missing,gemini_review_scope_incomplete,gemini_review_evidence_missing,gemini_model_not_recorded,gemini_data_sent_not_minimal,gemini_limits_not_recorded,gemini_transport_unavailable","event":"generation_provider","provider":"extractive",...}`
- Sample captured fake-transport request (synthetic question with land name, municipality, and
  parcel numbers; `selected` land context `opaque-land-7f3a`/`Martos`): model
  `synthetic-model-for-tests`, `instruction_version` `gemini-draft-v1`, `max_output_tokens` 512,
  `timeout_seconds` 10.0, payload
  `{"passages": [{"passage_id": "1", "text": "La solicitud anual se presenta una vez al año ante la oficina comarcal."}, {"passage_id": "2", "text": "El plazo sintético es de 30 días naturales."}], "question": "Mi finca [nombre del terreno] está en [municipio], polígono [número] parcela [número]. ¿Cuándo se presenta la solicitud anual de ejemplo?"}`
  — candidate 3 (outside the citation window) is not sent.
- `git diff --stat` shows no change under `contracts/`, `knowledge/`, `shared/`, any
  `backend/requirements*.txt`, `backend/deploy/requirements-production.txt`, or
  `backend/config/pilot_privacy_review.json`.

Coverage map (`backend/tests/test_gemini_generation.py`): limits gate (committed → not_recorded,
unreadable, 9 invalid shapes incl. bool-as-int, every bound ±1, NaN, future date); resolver matrix
(each input blocks independently, fixed codes echo no value, recording env shows only the two
provider keys read, startup never raises); minimal payload (exact equality with
`minimal_provider_payload(redact_text(...))`, 15 forbidden values absent); parse (21 malformed
classes); generator (one case per outcome code, all returning the extractive draft; rate limit per
minute/day/rollover; 8-thread cap test; log line has only `event,time,provider,outcome`); pipeline
order (conflict, false premise, no evidence, invalid, stale, clarification never call the
transport); route (committed state with injected transport never calls it and equals baseline;
default no-transport app; verified draft through `/ask` validated by `AskResponse` with code-owned
lead-in/notice/markers/sources; four failure drafts equal baseline; clarification/422/no-evidence
never call); guards (AST import allow-list, no key/credential strings, no Google package in
requirements). `socket.socket.connect`/`socket.create_connection` patched to fail in route tests.

Deviation from the contract wording (conservative, recorded): the payload offers only the
candidates inside the citation window (the first `max_claims` = 2), not all `k` retrieved
candidates. The land-clarification and unit-conflict pre-checks inspect exactly that window, so a
draft citing candidate 3–5 could otherwise bypass them; a draft citing outside the window is
`malformed_output` and falls back.

Honest limits: no real model was called; no answer-quality, latency, cost, or legal-coverage
evidence exists. The verifier is lexical, so a non-critical paraphrase is checked only for
markers, figures/dates, and eligibility phrases. The rate limiter is per process (per worker). The
timeout check is post-hoc on the injected clock; a future real transport must itself honour
`request.timeout_seconds`, since a blocking `send` cannot be interrupted here.

## Validator checklist

- [ ] No real transport, endpoint URL, credential/API-key read, or Google dependency exists; the AST,
      env-access, and requirements guards pass.
- [ ] Committed state (`pending` review, `null` limits) resolves to `extractive` with fixed blockers,
      and `/ask` equals the extractive baseline with a fake transport injected and never called.
- [ ] Each gate input independently blocks; blocker codes echo no values.
- [ ] Captured payload is exactly the redacted question plus candidate-numbered excerpts via
      `minimal_provider_payload`; no land, catalog, URL, metadata, or retained data.
- [ ] Every failure class falls back to the extractive draft, never raises, and never emits draft
      text; the model's `abstained` falls back.
- [ ] Accepted Gemini drafts still pass `verify_draft` twice; lead-in, notice, markers, and `sources`
      remain code-owned; `AskResponse` and `contracts/openapi.yaml` unchanged.
- [ ] Pipeline order unchanged: clarification, pre-check abstentions, and invalid/stale paths never
      call the transport.
- [ ] Logs carry only fixed codes; no question, passage, or draft text.
- [ ] Existing `test_privacy_retention.py` Gemini tests pass unchanged.
- [ ] Durable docs updated as listed; no answer-quality or legal-coverage claim anywhere.
- [ ] Focused verify block passes as published.
