# Feature specification: `backend_ask_endpoint`

## Source metadata

- **Feature:** `backend_ask_endpoint` — Serve safe answers from the local `POST /ask` endpoint (`backend`).
- **Depends on:** `answer_api_contract`, `backend_health`, `source_catalog_validation`, `source_retrieval`, `grounded_answer_generation`, `safe_abstention`, and `land_clarification` (all accepted).
- **Source behavior:** A contract-shaped question reaches the local FastAPI service and returns an answered, abstained, or land-clarification response using the existing source-grounded decisions.
- **Source verification:** Exercise `POST /ask` with fixture-backed requests for all three states, invalid request shapes, an empty canonical corpus, and invalid server corpus files; compare response shapes with `contracts/openapi.yaml`.
- **Source note:** The canonical source catalog is empty and there is no canonical passage set today. The endpoint must safely abstain on an empty valid corpus; fixture-backed answers do not establish legal coverage. The initial real corpus is a separate feature.

## Goal

Expose the accepted source-grounded answer flow at `POST /ask` while preserving the existing API contract, code-owned answer checks, minimal land context, and liveness-only meaning of `GET /health`.

## Non-goals

- Adding or approving real source documents or passages; that belongs to `backend_pac_corpus` and requires a named human reviewer.
- Hosted LLMs, embeddings, vector search, reranking, question rewriting, or a campaign-selection algorithm.
- Public deployment, authentication, public rate limits, production telemetry, `/feedback`, or Android/Desktop production wiring.
- Changing land-context semantics, answer policy, abstention copy, or the accepted response JSON keys.
- Claiming legal coverage based on the synthetic fixtures or an empty corpus.

## Job story

When the app or a local integration test submits a question, I want the backend to return only a contract-valid, evidence-grounded answer, a pinned abstention, or a necessary land clarification, so the client never mistakes missing or invalid evidence for a legal answer.

## Acceptance scenarios

### Answer from retrieved evidence

Given a valid request and an injected, approved synthetic catalog/passage set with a matching passage, when `POST /ask` runs, then it returns HTTP 200 with `status: answered`, the existing verified answer, its matching source fields, and the request's land scope. The fixture must remain clearly synthetic and must not be added to the canonical knowledge files.

### Abstain when the canonical corpus is empty or evidence is missing

Given the valid empty canonical catalog and passage set, or a valid fixture with no matching passage, when the request reaches `POST /ask`, then it returns HTTP 200 with the pinned code-owned abstention, `sources: []`, no land choices, and the appropriate scope. It emits no candidate excerpt, number, date, or unsupported claim.

### Ask the person to choose a land when applicability differs

Given an `all_active` request containing at least two lands and fixture evidence whose applicability materially differs across those lands, when `POST /ask` runs, then it returns HTTP 200 with `status: needs_land_clarification`, an empty answer, no sources, `land_scope: selected`, and only unique opaque IDs from that request.

### Do not repeat a completed land choice

Given a `selected` request or a request with one land, when the available fixture evidence cannot safely answer, then the endpoint follows the accepted answer/abstention path and does not return another land clarification.

### Reject invalid request shapes

Given malformed JSON, when submitted, then the endpoint returns the contract's HTTP 400 response. Given valid JSON with an invalid enum, missing field, extra key, duplicate land ID, inconsistent `mode`/`lands`, or a field outside its documented bound, then it returns HTTP 422 and never starts answer generation. Validation responses do not echo request values.

### Fail closed on unavailable or unsafe corpus configuration

Given an unreadable, malformed, or policy-invalid catalog/passage file, or campaign-tagged sources before campaign filtering is implemented, when the request reaches `POST /ask`, then the endpoint returns a generic HTTP 503 response, emits no `AskResponse`, and exposes no file path, catalog value, or passage text. `GET /health` remains HTTP 200 because it reports process liveness only.

### Keep the published contract and health behavior

Given the running application, when its OpenAPI document is requested, then it documents `POST /ask` with operation ID `askQuestion`, the accepted request and response fields, and the documented error statuses. `GET /health` retains its existing response and liveness-only behavior.

## Technical approach

- Add strict Pydantic request/response models matching `contracts/openapi.yaml`. Forbid extra keys; enforce the question and land-field bounds, enums, unique IDs, and the cross-field rule that `general` has no lands while `all_active` and `selected` have at least one.
- Keep orchestration thin. Load the local catalog and passage set, call `prepare_corpus`, then `answer_with_clarification`; map `Answered`, `Abstention`, and `NeedsLandClarification` through their existing `to_*_response` functions. Do not duplicate retrieval, applicability, abstention, or grounding policy in the route.
- Use the current UTC date as the request's `as_of` value for existing catalog expiry checks. Allow tests to inject a fixed date and fixture documents. Do not invent a campaign from the date; reject campaign-tagged runtime sources until `backend_campaign_validity` adds and verifies that behavior.
- Keep the canonical `knowledge/source_catalog.json` empty and add an explicitly empty `knowledge/passages.json` using the accepted passage-set schema. An empty corpus is valid and yields the ordinary safe abstention. Invalid or unreadable runtime artifacts map to a generic 503.
- Malformed JSON maps to 400; valid JSON that violates the request contract maps to 422. Do not return validation input values or log raw questions/land context.
- Add the router to the existing FastAPI app without changing `/health`. The service loads the repository's canonical knowledge files locally; tests inject fixture documents without modifying the canonical data.

## Expected file changes

- `backend/app/main.py` — register the `POST /ask` route while preserving `/health`.
- `backend/app/ask_api.py` (new) — strict request/response models, input validation, local corpus loading, and mapping to existing decisions; keep the module small and split only if a clear boundary requires it.
- `backend/tests/test_ask_endpoint.py` (new) — HTTP and model tests for all response states, validation, corpus failures, OpenAPI, and health.
- `knowledge/passages.json` (new) — explicitly empty `passage-set-v1` artifact until `backend_pac_corpus` supplies reviewed passages.
- `contracts/openapi.yaml` — document `POST /ask`, its status distinction, and generic 503 behavior without changing the `AskRequest` or `AskResponse` shapes.
- `backend/README.md` — local endpoint usage and honest empty-corpus behavior.
- `knowledge/README.md` — explain that the canonical passage file may be valid but empty and that it carries no answer coverage.
- `ARCHITECTURE.md` — record `/ask` as a runtime surface and the existing decision-module composition.

## Visual design impact

None. This backend feature adds no UI or Spanish app copy.

## Durable documentation impact

- `ARCHITECTURE.md`: update because `/ask` becomes a runtime route and the documented service boundary changes.
- `backend/README.md`: update local run, request, response, and empty-corpus behavior.
- `knowledge/README.md`: update the canonical passage-set description for the empty file.
- `contracts/openapi.yaml`: update the route/error contract; keep request and response payload shapes unchanged.
- `CONSTRAINTS.md`: no update; the existing grounding, abstention, and privacy constraints already govern the route.
- `AGENTS.md`, `CONTEXT.md`, `docs/domain-model.md`, `DESIGN.md`: no update; the feature preserves existing product and domain behavior and has no UI.
- `docs/archive/build-brief.md`, `docs/archive/technical-discovery.md`, `docs/risks-and-open-questions.md`: discovery scope already recorded; update only if implementation exposes a new decision or risk.
- `PROGRESS.md` and `feature_list.json`: record implementation/verification status only after the focused checks pass. The feature entry is already in the shared list as `not_started`.
- `docs/validations/backend_ask_endpoint.md`: create only during independent validation, not implementation.

## Focused verification

`./scripts/init.sh --feature backend_ask_endpoint` runs the commands below unchanged. They cover this endpoint and its contract; no Android SDK or public service is needed.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./scripts/init.sh --backend-tests tests/test_ask_endpoint.py
```
<!-- verify:end -->

## Appendix

The planning and verification record, repository research, implementation tasks, evidence to capture, and validator checklist are in [`backend_ask_endpoint.appendix.md`](../archive/specs/backend_ask_endpoint.appendix.md).
