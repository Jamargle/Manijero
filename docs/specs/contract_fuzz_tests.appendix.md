# Appendix — `contract_fuzz_tests`

Planning and verification record for [`contract_fuzz_tests.md`](contract_fuzz_tests.md). The acceptance record belongs to `docs/validations/contract_fuzz_tests.md`.

## Repository research

### Files inspected

- `PROGRESS.md` (Current state) and `feature_list.json` — the feature is `not_started`; both dependencies `backend_ask_endpoint` and `answer_api_contract` are `accepted`.
- `contracts/openapi.yaml` — authority for `/ask` request/response shape, bounds, enums, and documented error codes; written in YAML, no generated twin.
- `contracts/validate_examples.py` — dependency-free cross-field and privacy rules (`validate_request`, `validate_response`) for the committed examples; reusable as the semantic oracle.
- `contracts/examples/*.json` — three requests and three responses (answered, abstained, clarification) plus the retention opt-in; no schema-level validation is wired today.
- `backend/requirements-dev.txt`, `backend/requirements.txt` — `pytest`, `jsonschema`; `PyYAML` only arrives transitively via `uvicorn[standard]`.
- `backend/app/main.py` — `create_app`, `/openapi.json`, `MANIJERO_DEPLOYMENT_PROFILE`-gated inspection, env-resolved retention/trace/generation.
- `backend/app/ask_api.py` — Pydantic `extra="forbid"`, strict request/response models, land-context validator, route error mapping (`400` malformed JSON, `422` contract violation, generic `503`).
- `backend/tests/test_ask_endpoint.py` — the established `TestClient` + dependency-override pattern, fixture corpus paths, non-reflective `422`/`400` assertions.
- `backend/tests/test_pac_answer_eval.py` — `Draft202012Validator` + `FormatChecker` usage already accepted in the repo.
- `backend/tests/fixtures/clarification/{catalog,passages}.json` — deterministic synthetic corpus (two sources, three passages) used by the endpoint tests.
- `scripts/init.sh` (`run_feature`, `run_backend_tests`, `feature_commands`) — focused tier runs the fenced block verbatim; `--backend-tests` links the shared dev environment and runs from `backend/`.
- `ARCHITECTURE.md` (contract map) — `contracts/` owns the wire contract; no boundary change is needed.
- `docs/validations/{answer_api_contract,backend_ask_endpoint}.md` — existing evidence, including that openapi.yaml was parsed by Ruby, and the known Starlette/httpx warning.
- `docs/specs/backend_ask_endpoint.md` and `docs/archive/specs/backend_citation_hardening.appendix.md` — verification-command and appendix shapes to follow.

### Existing patterns to follow

- Focused backend checks use `./scripts/init.sh --backend-tests tests/<file>.py`; the contract-example check is `python3 contracts/validate_examples.py`.
- Tests use synthetic fixtures only and never claim legal coverage; all answer text in tests is explicitly synthetic.
- `contracts/validate_examples.py` stays stdlib-only; new test dependencies belong to `requirements-dev.txt` and must be justified.
- Determinism: existing offline checks pin `--as-of 2026-10-13`; this suite pins the same date and a fixed default seed.

### Current gaps and planning risks

- No Python code parses `contracts/openapi.yaml`; PyYAML is implicit through `uvicorn[standard]`. The plan makes it explicit and pinned as a dev dependency, and the focused block still runs on an existing dev environment because that package is already installed transitively.
- No generated/fuzz contract test exists; no Hypothesis or schemathesis is installed, and adding either is out of scope.
- `openapi.yaml` documents only `/ask`; `/health`, `/ready`, and `/metrics` have their own features and stay out.
- The local profile cannot produce the pilot-only `401`/`413`/`429` codes, so the fuzz assertions limit error codes to `400`/`422` and never `5xx`.
- The contract is hand-maintained, so drift must be caught by comparison, not by regenerating the contract.
- The drift guard and the generated cases have not been executed at planning time; a pre-existing mismatch is possible. Expected resolution is to fix the smaller side (server model or contract) and record it, never to relax the assertion. Runtime cost is expected to be a few seconds but is unmeasured until the implementer runs it.

## Implementation plan

1. Add `PyYAML>=6.0,<7` to `backend/requirements-dev.txt`; rebuild the shared dev env with `./scripts/init.sh --setup-python` only if the linked environment predates the change.
2. Create `backend/tests/test_contract_fuzz.py` with a cached contract loader, a local-only `$ref` resolver, and a `Draft202012Validator` with a `FormatChecker`.
3. Import `validate_request`/`validate_response` from `contracts/validate_examples.py` through `sys.path`; classify every generated payload with that oracle.
4. Add the `TestClient` fixture mirroring `test_ask_endpoint.py` (fixture catalog and passages, `as_of=2026-10-13`, campaign `2026`); handle a possible `inspection` field explicitly rather than assuming it is absent.
5. Implement the generator from contract bounds/enums (question, land id, municipality, enums) plus fixed fixture prompts for answered/abstained/clarification; seed with `random.Random`.
6. Implement the valid-request scenario (200, schema, status invariants, request-owned clarification IDs, no undeclared keys) and the invalid/mutation scenarios (400/422 only, `detail`-only body, no echoed sentinel text, no 5xx).
7. Add the determinism test (same seed twice) and the `/openapi.json` drift guard for `/ask` properties, required sets, bounds, and enums.
8. Run the focused tier and the full backend suite; if real drift appears, fix the smaller side (server or contract) and record it in Feature evidence.
9. Add the ~15-line `backend/README.md` section (command, what passes mean, seed/case knobs, no legal or performance claim).

## Verification plan

- Focused tier: the two commands in the contract's block (contract examples, then the new module) must pass unchanged through `./scripts/init.sh --feature contract_fuzz_tests`.
- Broader regression: `./scripts/init.sh --backend-tests` — no regressions in the existing suite.
- Determinism and soak, evidence only: `MANIJERO_CONTRACT_FUZZ_SEED=7 ./scripts/init.sh --backend-tests tests/test_contract_fuzz.py -q`; optional `MANIJERO_CONTRACT_FUZZ_CASES=200` run, report-only and not part of the focused tier.
- `git diff --check` — whitespace clean.
- E2E: not applicable. No persistent E2E harness targets this boundary, the feature changes no user-visible behavior, and the FastAPI `TestClient` already exercises the HTTP wire shape. Pilot auth/rate-limit/body-bound paths stay covered by their own suites.

## Evidence to capture

- Focused command result with test count and wall-clock time, and the interpreter used.
- Number of generated valid and invalid cases; counts observed per response state.
- Confirmation that no generated case returned `5xx` and that invalid-case bodies contained only `detail` and no sentinel text.
- Same-seed determinism result and the alternate-seed run.
- Drift-guard comparison result against `/openapi.json`.
- Full backend-suite count and `git diff --check`.
- Whether any contract or application file had to change; if so, what and why.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

### 2026-11-06 — implementer

- Env: pinned `PyYAML>=6.0,<7` added to `backend/requirements-dev.txt`; `./scripts/init.sh --setup-python` rebuilt the shared dev env (`backend/.venv` → `dev-py3.12.16-552000138873`, Python 3.12.16; PyYAML 6.0.3 was already present transitively).
- `python3 contracts/validate_examples.py` → `Validated 3 request and 3 response examples against answer_api_contract`.
- `./scripts/init.sh --feature contract_fuzz_tests` → focused tier passed: `41 passed, 1 warning in 0.45s` (tier ~0.9 s wall).
- `./scripts/init.sh --fast` → all 10 offline checks passed; backend suite `1912 passed, 4 skipped in 40.54s`.
- Default cases: 43 contract-valid requests (3 fixed state-coverage + 40 generated); observed `answered=28`, `abstained=6`, `needs_land_clarification=9`. 18 contract-invalid cases, 14 single-field mutations, and 1 malformed JSON all got `400`/`422` (never `5xx`), a body of exactly `{"detail": ...}`, and no sentinel echo; every clarification ID belonged to the request's land list.
- Determinism: the same seed built an identical case list (`test_the_generated_case_list_is_deterministic_for_a_seed`); `MANIJERO_CONTRACT_FUZZ_SEED=7 ./scripts/init.sh --backend-tests tests/test_contract_fuzz.py -q` → `41 passed in 0.50s` (seed `20260601` → `41 passed in 0.50s`); report-only `MANIJERO_CONTRACT_FUZZ_CASES=300 ...` → `41 passed in 1.65s`.
- Drift guard found one real mismatch on first run: `/openapi.json` advertises `AnswerSource.url` `minLength: 1`, the contract declared no string bound. Fixed the smaller side by adding `minLength: 1` to `contracts/openapi.yaml` (one line); no application code changed. Re-run passes; `/ask` property names, required keys, enums, and string bounds now match.
- Pre-existing guard `backend/tests/test_local_generation.py::test_no_requirements_file_changed` compared every requirements file with HEAD, so it failed only because this feature adds a dev-only dependency. Narrowed it to runtime requirement files (the dev file is still checked for `ollama`) and renamed it `test_no_runtime_requirements_file_changed`; the runtime-file equality assertions are unchanged.
- `git diff --check` → clean (exit 0).

### 2026-11-06 — validator (accept)

- `./scripts/init.sh --feature contract_fuzz_tests` → `41 passed` in 0.34 s; `./scripts/init.sh --fast` → 10/10, backend `1912 passed, 4 skipped`.
- Drift guard proved non-vacuous (removing the contract `minLength` fails it); runtime-requirements guard proved live (an added embeddings line fails it).
- Contract `minLength: 1` addition judged the genuine smaller-side fix; `test_local_generation.py` narrowing keeps the runtime freeze.
- Acceptance record: [../../validations/contract_fuzz_tests.md](../../validations/contract_fuzz_tests.md).

## Validator checklist

- [ ] Scope matches the contract; no new runtime dependency, no Hypothesis/schemathesis, no CI change.
- [ ] `PyYAML` is dev-only, pinned, and justified; existing environments still run the focused block.
- [ ] The suite reads `contracts/openapi.yaml` (not a copy) and reuses `contracts/validate_examples.py` rules.
- [ ] Valid/invalid classification is oracle-driven, deterministic from the seed, and bounded in runtime.
- [ ] All three response states are exercised; every clarification ID belongs to the request.
- [ ] Invalid cases yield only `400`/`422`, never `5xx`, and echo no request text.
- [ ] The drift guard compares the live `/openapi.json` schema with the contract and would fail on a real mismatch.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature contract_fuzz_tests`.
- [ ] `backend/README.md` states the command, knobs, and honest limits; no legal-coverage or performance claim.
- [ ] `feature_list.json` / `PROGRESS.md` status reflects the verified result.
