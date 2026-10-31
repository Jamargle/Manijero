# Feature Spec: answer_api_contract

## Source metadata

- Feature: `answer_api_contract`
- Title: Structured answer contract
- Depends on: none
- Source behavior: The app and answer service agree on a response state for answered, abstained, and needs-land-clarification outcomes, with typed sources and minimal land context.
- Source verification: Validate representative request and response examples against the agreed contract.
- Source note: Define the contract before implementing client/service integration; keep local land labels out of the payload unless a reviewed use case requires them.
- Scope: API boundary only; the repository has no backend implementation yet.

## Goal

Define the stable contract between the future answer service and Android/Desktop clients for
answered, abstained, and land-clarification responses. The contract must preserve the original
question, make answer state explicit, expose typed source provenance, and prevent local land names,
notes, or other unnecessary personal details from crossing the API boundary.

## Non-goals

- Implementing FastAPI, retrieval, generation, health, feedback, authentication, or deployment.
- Adding a Kotlin network client or UI integration.
- Proving legal eligibility from land data.
- Sending land labels, free-text notes, precise identifiers, or area by default.

## Acceptance scenarios

### Answered response

Given a non-empty Spanish question and minimal land attributes, when the service has sufficient
approved evidence, then it returns HTTP 200 with `status: answered`, a non-empty answer, at least
one typed source, a verification date, and an explicit land scope.

### Abstained response

Given a question for which evidence is missing, stale, conflicting, or insufficient, when the
service cannot answer safely, then it returns HTTP 200 with `status: abstained`, no sources used to
support a legal conclusion, a plain limitation, and a next step. It must not fabricate dates,
amounts, eligibility, or article numbers.

### Land clarification response

Given multiple supplied lands where applicability materially differs, when the service needs the
user to choose, then it returns HTTP 200 with `status: needs_land_clarification`, an empty answer,
no sources, and one or more existing opaque land IDs. The original question remains in the request
and the client supplies labels from its local list.

### Privacy-minimized request

Given any request, when it crosses the service boundary, then each land context contains only an
opaque stable ID and relevant structured attributes. `name`, `label`, `notes`, precise parcel
identifiers, and arbitrary extra fields are not contract fields.

## Contract design

The canonical contract is `contracts/openapi.yaml` (OpenAPI 3.1). `POST /ask` accepts a question and
an explicit `land_context` mode. `general` carries no lands, `all_active` carries all relevant
active lands, and `selected` carries the user-selected subset. Land fields use enums with `unknown`
as a valid value; omission means the attribute is not needed for this question, not that it is
known.

Responses use one discriminating `status` enum:

- `answered`: non-empty answer, one or more sources, and land scope.
- `abstained`: non-empty limitation/next-step text, no sources, and land scope.
- `needs_land_clarification`: empty answer, no sources, and IDs to choose.

The schemas provide shape validation. `contracts/validate_examples.py` provides cross-field and
privacy validation without adding a Python dependency to this starter repository.

## Expected files

- Create `contracts/openapi.yaml`.
- Create `contracts/examples/ask-request-general.json`.
- Create `contracts/examples/ask-request-all-lands.json`.
- Create `contracts/examples/response-answered.json`.
- Create `contracts/examples/response-abstained.json`.
- Create `contracts/examples/response-needs-land-clarification.json`.
- Create `contracts/validate_examples.py`.
- Update `feature_list.json` and `PROGRESS.md` with evidence after validation.

## Durable documentation impact

- `AGENTS.md`: no update; the existing guide already requires source-grounded answers and minimal
  land context.
- `CONTEXT.md`, `docs/domain-model.md`, `docs/archive/build-brief.md`: no update; this contract implements
  their existing response and privacy rules without changing product decisions.
- `ARCHITECTURE.md` / `CONSTRAINTS.md`: not present in this starter scaffold; do not create them for
  this narrowly scoped contract slice.
- `PROGRESS.md` and `feature_list.json`: update with the focused validation evidence and status.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/answer_api_contract.appendix.md`](../archive/specs/answer_api_contract.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/answer_api_contract.md` remains the authoritative acceptance record.
