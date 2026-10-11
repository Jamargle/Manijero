# Validation: answer_api_contract

## Verdict

**Accept** — independently reviewed against `docs/specs/answer_api_contract.md`.

## Evidence

- `python3 contracts/validate_examples.py` passed: 2 request and 3 response fixtures.
- `python3 -m py_compile contracts/validate_examples.py` passed.
- Ruby YAML parser loaded `contracts/openapi.yaml` successfully.
- `git diff --check` passed.
- Reviewed status invariants: answered requires evidence, abstained has no unsupported citation,
  and clarification has an empty answer plus existing opaque IDs.
- Reviewed privacy boundary: request schema has no land names, labels, notes, area, or parcel IDs.

## Scope and security review

The change is limited to the API contract, representative fixtures, a focused validator, and
workflow evidence. No backend, network client, credentials, or personal data were added. No
blocking security findings were identified.
