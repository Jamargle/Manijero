# Validation: contract_fuzz_tests

Verdict: accept (independent validator, 2026-11-06; developer-only feature, no owner walkthrough in the spec).
Spec: [../specs/contract_fuzz_tests.md](../specs/contract_fuzz_tests.md) · Appendix: [../specs/contract_fuzz_tests.appendix.md](../specs/contract_fuzz_tests.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature contract_fuzz_tests` → focused tier passed, `41 passed` in 0.34 s; the published block runs unchanged.
- `./scripts/init.sh --fast` → all 10 offline checks ok; backend suite `1912 passed, 4 skipped` (matches the appendix).
- Drift-guard sensitivity probe: removing the contract's `AnswerSource.url` `minLength: 1` made `test_the_service_openapi_does_not_drift_from_the_contract` fail; restored with an identical file, so the guard is not vacuous.
- Runtime-requirements guard probe: appending a line to `requirements-embeddings.txt` made `test_no_runtime_requirements_file_changed` fail; restored, so the narrowed guard keeps the runtime freeze.
- `MANIJERO_CONTRACT_FUZZ_CASES=0 MANIJERO_CONTRACT_FUZZ_SEED=99` → `41 passed` (state coverage survives zero generated cases); `git diff --check` clean.

## Review notes

- Contract fix is the smaller side: `app.openapi()` advertises `url: {type: string, minLength: 1, format: uri}`; no application or example file changed and the six committed examples still validate. No assertion was loosened.
- The `test_local_generation.py` guard narrowing keeps the real guarantee: runtime requirement files must still equal HEAD, `deploy/requirements-production.txt` stays covered, `ollama` is still rejected in the dev file, and `test_container_image_files.py` independently proves the dev file never enters the service image.
- Non-blocking coverage notes: the drift guard compares property names, required sets, enums, and string bounds only (`format`, `type`, `additionalProperties`, array sizes unguarded); the mutation test's accept branch is structurally unreachable because all 14 mutations are pre-asserted invalid; dev-requirement additions have no pin/justification check beyond the `ollama` rule.
- Security: no findings (no secrets, no sockets, synthetic sentinel data, non-reflective rejection tested).

## Limits that remain

- Offline, in-process only: no live service, network, load, or performance claim.
- Pilot-only codes (`401`, `413`, `429`) and routes other than `/ask` stay out of scope; their existing suites cover them.
- Generation comes from the contract's own bounds/enums plus a fixed fixture-corpus prompt list, not from arbitrary byte-stream fuzzing.
