# Backend `POST /ask` — planning and verification record

## Repository research

- `backend/app/main.py` creates the FastAPI application and exposes only `GET /health` with a liveness-only response.
- `contracts/openapi.yaml` defines `POST /ask`, `AskRequest`, the three `AskResponse` statuses, minimal land fields, and 400/422 descriptions. It currently has no 503 response description.
- `backend/app/abstention.py::prepare_corpus` composes catalog validity and retrieval setup. An empty catalog/passage set is valid; malformed or unreadable artifacts raise the existing catalog/passage exceptions.
- `backend/app/clarification.py::answer_with_clarification` runs the accepted land-clarification decision and otherwise delegates to `answer_or_abstain`. Its companion `to_clarification_response` builds the exact contract keys.
- `backend/app/generation.py::to_answer_response` builds the source-bearing answer payload; `backend/app/abstention.py::to_abstention_response` owns the pinned source-free abstention payload.
- `backend/app/retrieval.py` provides BM25, source eligibility, `valid_until` filtering, and passage-set loading. It does not implement campaign filtering.
- `backend/tests/test_health.py` uses FastAPI `TestClient` and checks both the health body and generated OpenAPI. `httpx` is already a backend dependency.
- Existing retrieval, generation, abstention, and land-safety fixtures are synthetic. `knowledge/source_catalog.json` is empty; there is no canonical passage JSON file today.
- `contracts/validate_examples.py` validates accepted request/response examples and privacy/cross-field rules without adding a dependency.
- `./scripts/init.sh --backend-tests <target>` runs focused backend pytest targets; `--feature` reads the verification block from this contract.

## Implementation plan and tasks

1. Add strict Pydantic models that match the request and response fields, bounds, enums, and closed-object rules in `contracts/openapi.yaml`. Add semantic validation for unique land IDs and mode/lands consistency.
2. Add a thin `/ask` router/service boundary. It loads the canonical JSON artifacts, uses UTC `as_of`, calls `prepare_corpus`, `answer_with_clarification`, and the existing response assemblers, and does not reimplement their policy.
3. Add a valid empty `knowledge/passages.json`. Keep campaign-tagged sources unavailable until a later feature implements and evaluates campaign scoping; fail closed if such metadata is presented to this route.
4. Distinguish malformed JSON (400), request contract validation (422), and broken/unavailable corpus configuration (generic 503). Do not echo request values or return internal file/content details.
5. Register the route on the existing app while keeping `/health` independent of corpus readiness.
6. Add `TestClient` coverage with injected synthetic documents for answered, abstained, and clarification responses, plus empty-corpus, invalid-input, campaign-source, artifact-failure, OpenAPI, and health cases.
7. Update the OpenAPI contract, backend/knowledge README files, and `ARCHITECTURE.md`. Preserve synthetic labels and do not add unreviewed legal content.

## Verification plan

- Run `python3 contracts/validate_examples.py` to protect the accepted wire examples and privacy rules.
- Run `./scripts/init.sh --backend-tests tests/test_ask_endpoint.py` for route, validation, response-shape, and failure tests.
- Confirm the spec's focused block is executed verbatim by `./scripts/init.sh --feature backend_ask_endpoint` after implementation.
- Do not use evaluator scores from existing synthetic fixtures as a quality threshold or legal-coverage claim. The later `backend_answer_evaluation` feature owns reviewed source-anchored measurement.

## Evidence to capture

- Test output for each response state and each error class.
- OpenAPI evidence that `POST /ask` uses `askQuestion`, publishes the contract models and documents 400, 422, and 503.
- Evidence that empty canonical data returns the pinned abstention, while malformed, expired, or campaign-tagged server data cannot produce an answer.
- Evidence that clarification returns only IDs supplied by the request and that selected mode is never clarified again.
- README/architecture changes that state the corpus is empty and that `/health` remains liveness-only.
- A clear note that fixture-backed answered responses are synthetic and do not establish legal coverage.

## Feature evidence

<!-- Implementer: append verified implementation and command evidence below. -->

## Validator checklist

- [ ] `POST /ask` accepts only the contract request keys and enforces bounds, enums, unique IDs, and mode/lands invariants.
- [ ] The route composes `prepare_corpus`, `answer_with_clarification`, and the existing response assemblers without duplicating their policy.
- [ ] Answered responses cite only the retrieved evidence; no draft bypasses the grounding verifier.
- [ ] Abstention payload is code-owned, source-free, and contract-shaped.
- [ ] Clarification is offered only by the accepted land applicability rule and returns only unique IDs from the request.
- [ ] Empty corpus safely abstains; invalid, unreadable, or campaign-tagged corpus configuration fails closed without leaking paths or source text.
- [ ] `GET /health` remains independent of corpus availability and retains its current liveness response.
- [ ] OpenAPI and examples match the static contract; malformed JSON, shape validation, and backend configuration have the documented statuses.
- [ ] Tests use synthetic fixtures as test data only; no unsupported legal source or metric claim is introduced.
- [ ] Durable backend, knowledge, API contract, and architecture docs are updated; no client or UI scope is added.
