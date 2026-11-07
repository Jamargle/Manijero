# Feature Spec: `contract_fuzz_tests`

## Source metadata

- `id`: contract_fuzz_tests · `area`: testing · `depends_on`: `backend_ask_endpoint`, `answer_api_contract` · `status` at planning: not_started
- User-visible behavior: none. This is a developer-only conformance suite; its observable effect is a focused test that fails when the running `/ask` service or the app's advertised schema drifts from `contracts/openapi.yaml`.
- Verification: the focused pytest module below plus the existing contract-example validator; documented in [Focused verification](#focused-verification-required).
- Notes: deterministic in-repo generation, no Hypothesis/schemathesis, no live service; `PyYAML` is added as a pinned dev-only dependency. The pilot-only codes (`401`, `413`, `429`) stay out of scope; their suites already cover them.

## Goal

Prove, offline and deterministically, that the local `/ask` service honors `contracts/openapi.yaml`: contract-valid generated requests are accepted and produce schema-valid responses, contract-invalid requests are rejected with a generic 4xx, no request returns 5xx, and the FastAPI application's advertised schema does not drift from the versioned contract. The suite must be cheap enough for the focused tier and reproducible from a seed.

## Non-goals

- No Hypothesis, schemathesis, property-based library, or new runtime dependency; no CI workflow change.
- No change to retrieval, generation, abstention, clarification, retention, corpus, client, or legal behavior.
- No hosted/live service, network call, load test, or performance claim.
- No pilot-only coverage: bearer auth (`401`), request-body bound (`413`), and rate limits (`429`) stay with their existing pilot suites.
- No contract coverage for `/health`, `/ready`, or `/metrics`; `openapi.yaml` documents only `/ask`.
- No fuzzing of arbitrary byte streams beyond one malformed-JSON case; no new route, endpoint, or corpus.

## Job story

When I change the answer service, the contract, or an endpoint model, I want a fast generated conformance check to fail loudly on the drift, so that clients and the service keep agreeing on the wire shape without a manual review of every field.

## Acceptance scenarios

### 1. Contract and committed examples agree

Given `contracts/openapi.yaml` and `contracts/examples/*.json`, when the suite loads the contract, then it resolves every local `#/components/schemas/…` reference, rejects any other reference form, and every committed request and response example validates against its OpenAPI schema and the existing cross-field rules.

### 2. Generated contract-valid requests are accepted in contract shape

Given a generated request that the contract (schema plus documented cross-field rules) accepts, when it is posted to `/ask` against the fixture corpus, then the response is `200`, JSON, validates against the contract's `AskResponse` schema, satisfies the status invariants (`answered` needs an answer and sources, `abstained` needs an answer and no sources, `needs_land_clarification` needs an empty answer, no sources, and non-empty choices), and contains no undeclared top-level key.

### 3. All three response states are reached and conform

Given the same fixture corpus, when the generated cases include a supported prompt, an unsupported prompt, and a two-land water-regime question, then the run observes at least one `answered`, one `abstained`, and one `needs_land_clarification` response, each schema-valid, and every clarification ID was present in that request's land list.

### 4. Generated contract-invalid requests are rejected without echo

Given a generated request the contract rejects (empty or over-long question, wrong type, missing `land_context`, `general` with lands, land-aware mode without lands, duplicate land IDs, unknown enum, extra field, forbidden privacy key, non-boolean opt-in) or one malformed JSON body, when posted, then the status is `400` or `422`, never `5xx`; the body is JSON whose only field is `detail`; and the sentinel question/land text from the request does not appear in the response.

### 5. Single-field mutations preserve the same rule

Given a contract-valid case mutated in exactly one field (deleted required key, swapped type, over-long string, duplicated ID, added forbidden or unknown key, invalid enum), when posted, then the acceptance/rejection result matches the contract oracle for the mutated payload, still never `5xx`, still non-reflective on rejection.

### 6. Determinism and bounded cost

Given `MANIJERO_CONTRACT_FUZZ_SEED` and `MANIJERO_CONTRACT_FUZZ_CASES`, when the module runs twice with the same seed, then it generates the identical case list; with a different seed it still passes; with the default configuration the focused tier completes well inside the existing backend test budget.

### 7. No silent schema drift

Given the FastAPI application's `/openapi.json`, when compared with `contracts/openapi.yaml`, then for `/ask` the request and response schemas keep the same property names, required sets, string bounds, and enum values. If a real mismatch is found, the smaller side is corrected and recorded; assertions are never loosened to pass.

## Technical approach

- One pytest module `backend/tests/test_contract_fuzz.py`; no planned production change (a real mismatch is fixed on the smaller side).
- Load the contract once with `yaml.safe_load`. Resolve only local `#/components/schemas/<name>` references recursively (copying them, failing loudly on any other `$ref`). Validate with `jsonschema.Draft202012Validator` and a `FormatChecker` for `date`; check `https` URLs with `urllib.parse` as `contracts/validate_examples.py` does.
- Reuse `contracts/validate_examples.py` (`validate_request`, `validate_response`) as the single cross-field oracle by adding `contracts/` to `sys.path`; do not fork its rules into the new test.
- Generate cases from the contract's own bounds and enums (`question.maxLength`, land `id.maxLength`, `municipality.maxLength`, mode/water/production enums), not from hardcoded copies, plus a small fixed list of fixture-corpus prompts for response-state coverage.
- Drive the real app with `fastapi.testclient.TestClient`, reusing the dependency-override seam from `backend/tests/test_ask_endpoint.py` (clarification fixture catalog and passages, `as_of=2026-10-13`, campaign `2026`). Local profile only.
- Deterministic PRNG `random.Random(seed)`; default seed `20261106` and `40` generated cases; environment overrides are optional and documented. No clock, network, or filesystem order inputs.
- Drift guard: read `/openapi.json` from the same `TestClient`, follow its component refs, and compare only `/ask` request/response property names, required sets, enum values, and string bounds against the contract version.
- `PyYAML>=6.0,<7` goes in `backend/requirements-dev.txt` only: the contract is authored in YAML, PyYAML is already pulled transitively by `uvicorn[standard]`, and it stays out of runtime requirements.

## Expected file changes

- `backend/tests/test_contract_fuzz.py` — create; contract loader, deterministic generator, conformance and drift tests.
- `backend/requirements-dev.txt` — add pinned `PyYAML>=6.0,<7` (dev-only, justified above).
- `backend/README.md` — add a short "Contract conformance tests" section: command, coverage, seed/case knobs, honesty limits (~15 lines).
- `feature_list.json` — this feature moves to `in_progress` at planning and `passing` after evidence; exact status stays owned by the selector.
- `contracts/openapi.yaml`, `contracts/examples/`, `backend/app/` — expected unchanged; if a genuine drift appears, fix the smaller side and record it in the appendix.
- `docs/validations/contract_fuzz_tests.md` — created by the independent validator only.

## Visual design impact

No UI involved. No `DESIGN.md` section applies.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed — `contracts/` remains the wire-shape authority; no boundary, dependency direction, or runtime surface changes.
- `docs/constraints/<area>.md`: not needed — no new product, land, client, hosting, or operational MUST rule; contract authority is already recorded in `ARCHITECTURE.md`.
- `AGENTS.md`: not needed — no workflow, startup path, or repo-wide rule change; the focused tier command is unchanged.
- Other: `backend/README.md` — developer-facing command and limits; `docs/specs/contract_fuzz_tests.md` and its appendix own the rest.

## Focused verification (required)

No new `scripts/init.sh` mode is needed: the existing `--feature` runner executes this block unchanged, and `--backend-tests` supplies the shared pytest environment.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./scripts/init.sh --backend-tests tests/test_contract_fuzz.py -q
```
<!-- verify:end -->

## Appendix

See [`contract_fuzz_tests.appendix.md`](contract_fuzz_tests.appendix.md) for research, ordered tasks, the verification plan, evidence, and the validator checklist.
