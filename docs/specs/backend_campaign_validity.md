# Feature specification: `backend_campaign_validity`

## Source metadata

- **Feature:** `backend_campaign_validity` — Scope answer sources by date and campaign (`backend`).
- **Depends on:** `backend_ask_endpoint` and `backend_pac_corpus` (implemented and independently accepted before this feature).
- **Source behavior:** The local `/ask` path uses only current, approved sources that are valid as of the UTC request date and either campaign-neutral or tagged for the explicitly configured active campaign.
- **Source verification:** Exercise matching, mismatching, missing, and malformed campaign configuration; explicit old/current years in questions; validity boundaries; and the complete endpoint contract.
- **Source note:** The request contract has no campaign field. Do not infer the active campaign from the date; configure it explicitly, and fail closed when campaign-specific material cannot be scoped safely.

## Goal

Prevent a response from mixing a campaign-specific PAC rule with another campaign's rule. Keep the current UTC validity check and add a single explicitly configured active campaign for this MVP, without changing the accepted request or response JSON shapes.

## Non-goals

- Supporting historical campaign lookup, side-by-side comparisons, campaign prediction, question rewriting, or an API field for campaign selection.
- Automatically determining a campaign from the current year, a land attribute, application status, or an untrusted source passage.
- Archiving or serving expired campaigns from the active runtime corpus; old campaign sources remain unsupported.
- Changing filing, modification, adaptation, eligibility, aid amount, land applicability, or generation policy.
- Scheduled source refresh, a public deployment configuration system, telemetry, provider integration, or client/UI changes.

## Job story

When a grower asks about a PAC campaign, I want the service to use evidence for one explicit campaign and the relevant as-of date, so that a valid answer from another year cannot be mistaken for the current rule.

## Acceptance scenarios

### Include only the active campaign and campaign-neutral sources

Given a valid `MANIJERO_ACTIVE_CAMPAIGN` setting, a current corpus with campaign-tagged and campaign-neutral sources, and a fixed `as_of` date, when `/ask` prepares retrieval, then it indexes eligible campaign-neutral sources plus eligible sources tagged with the configured campaign; it excludes passages from other campaigns and never mixes them into a response.

### Do not answer a question explicitly about another campaign

Given an active campaign of `2026`, when a question contains one explicit four-digit campaign year other than `2026`, then the service skips generation and returns the existing pinned no-evidence abstention with no sources. When the question contains multiple distinct campaign years, it also abstains instead of attempting a comparison. A question with no explicit year uses the configured active campaign.

### Respect source validity dates

Given an eligible source with `valid_until` equal to the `as_of` date, when retrieval runs, then it may be used through that date. Given an as-of date after `valid_until`, then the source cannot support an answer. If all sources are expired, the accepted stale-evidence abstention is used; if expired entries remain beside otherwise-current entries in the active catalog, the existing catalog gate fails closed with generic 503. Date checks use the UTC calendar date injected by the route and fixed dates in tests.

### Require explicit and valid campaign configuration

Given no active campaign setting, an invalid setting, or an invalid campaign-tagged source record, when `/ask` runs, then it returns a generic HTTP 503, with no response containing a source excerpt, path, or configuration value. `GET /health` remains liveness-only and returns its accepted response.

### Preserve the API and code-owned answer checks

Given an active campaign request, when the remaining source set is passed through retrieval, land clarification, extractive generation, and grounding verification, then all three accepted response states retain their existing JSON shape. No campaign metadata is exposed in `AskResponse`, and no draft bypasses the answer verifier.

## Technical approach

- Read the active campaign from an explicit `MANIJERO_ACTIVE_CAMPAIGN` runtime setting. Accept only a four-digit year. Do not default to the machine year. Require a valid setting for every `/ask` request so explicit query years have one unambiguous comparison point.
- Keep `as_of` as the UTC calendar date. It is a validity boundary and is independent of `MANIJERO_ACTIVE_CAMPAIGN`; neither value substitutes for the other.
- Strengthen campaign metadata validation: a present `campaign` must be a four-digit year and must have a finite `valid_until` approved for that source. Preserve the existing accepted validity and review gates. A source with no campaign stays campaign-neutral only when the official rule is truly general.
- Validate catalog and passage shape and provenance before selecting an index. Build the request retriever from eligible campaign-neutral plus active-campaign sources and their passages; other-campaign passages are excluded as a group, not exposed as unknown-source load errors. Invalid references in the full source/passages artifacts remain errors.
- Conservatively recognize standalone years in the original user question. If the question names a different year or more than one distinct year, return the accepted pinned no-evidence response without retrieval/generation. Do not rewrite the question or include its contents in logs.
- Rotate the active canonical corpus when a campaign expires: remove expired entries from the runtime catalog/passages after review. The accepted catalog validator rejects expired entries, so historical documents must not remain in the active runtime files. Historical answers are out of scope.
- Keep campaign filter, query-year guard, and date checks deterministic and offline. Tests inject both the active campaign and `as_of` date; the contract and shared client remain unchanged.

## Expected file changes

- `backend/app/retrieval.py` and/or a small `backend/app/campaign.py` (new) — validated campaign selection and safe filtering, with one clear ownership boundary.
- `backend/app/ask_api.py` — pass active campaign and UTC `as_of` to corpus preparation; map unsupported campaign scope to the existing pinned abstention and configuration failures to generic 503.
- `backend/app/source_catalog.py` and `knowledge/source_catalog.schema.json` — validate the strict campaign year and require a finite validity bound when a campaign label is present.
- `backend/tests/test_campaign_validity.py` (new) — campaign matching, mismatch, missing/invalid config, question-year guard, validity boundary, and no-leak checks.
- `backend/tests/test_ask_endpoint.py` — endpoint regression coverage for campaign-scoped behavior and unchanged response shapes.
- `contracts/openapi.yaml` — ensure generic 503 configuration behavior remains documented; do not add campaign fields to `AskRequest` or `AskResponse`.
- `backend/README.md`, `knowledge/README.md`, and `ARCHITECTURE.md` — document the explicit active campaign setting, refresh/rotation rule, and local service behavior.
- `CONSTRAINTS.md` — record the durable campaign-scope, no-inference, and fail-closed rules if they are not already present.

## Visual design impact

None. This backend behavior adds no UI or Spanish app copy.

## Durable documentation impact

- `CONSTRAINTS.md`: update with the explicit campaign-scope and no-year-inference rule.
- `backend/README.md`, `knowledge/README.md`, and `ARCHITECTURE.md`: document runtime setting, validity filtering, and the requirement to rotate expired sources out of active artifacts.
- `contracts/openapi.yaml`: document the generic 503 only; request and response fields remain unchanged.
- `docs/risks-and-open-questions.md`: update the campaign-selection question after the selected active-campaign behavior is implemented and reviewed.
- `PROGRESS.md` and `feature_list.json`: update only after the focused endpoint/campaign checks pass.
- `docs/validations/backend_campaign_validity.md`: create only during independent feature validation.

## Focused verification

`./scripts/init.sh --feature backend_campaign_validity` executes the documented checks after implementation.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./scripts/init.sh --backend-tests tests/test_campaign_validity.py tests/test_ask_endpoint.py
```
<!-- verify:end -->

## Appendix

Repository findings, campaign policy decisions, verification evidence to capture, and the validator checklist are in [`backend_campaign_validity.appendix.md`](../archive/specs/backend_campaign_validity.appendix.md).
