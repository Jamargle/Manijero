# Backend campaign validity — planning and verification record

## Repository research

- `contracts/openapi.yaml` has no campaign field. `AskRequest` is the original question plus minimal land context; keep it stable.
- `backend/app/retrieval.py` filters by source approval, current lifecycle, and `valid_until`, but currently ignores the optional catalog `campaign` label.
- `backend/app/source_catalog.py` accepts a non-blank campaign string but does not enforce a year format or require `valid_until` for campaign-tagged sources.
- `source_catalog.validate_catalog` rejects an expired source. `prepare_corpus` returns a stale-evidence abstention when all declared sources are ineligible; the active canonical artifacts therefore must not accumulate expired campaign entries beside otherwise-current material.
- `backend/app/abstention.py` already owns pinned `no_evidence` and `stale_evidence` copy. `backend/app/generation.py` and the response assemblers own grounding and response invariants; campaign logic must not duplicate them.
- `backend/app/main.py` currently exposes only liveness `/health`; the planned `backend_ask_endpoint` adds `/ask` and the explicit runtime-setting boundary.

## Policy decisions for implementation

1. **Two independent inputs:** `as_of` is the UTC date for legal validity; `MANIJERO_ACTIVE_CAMPAIGN` is an explicitly configured four-digit campaign required by every `/ask` request. Do not derive one from the other.
2. **No request-contract migration:** unqualified questions use the configured active campaign. A conservative standalone-year scan treats one matching year as in-scope, a different year as unsupported, and multiple distinct years as an unsupported comparison. Unsupported scope uses the existing pinned no-evidence response.
3. **Source rules:** campaign-neutral sources may support generally applicable claims; a campaign-tagged source is eligible only for the exact active campaign and if its existing review/lifecycle/date checks pass. Campaign-specific metadata must be reviewable and finite (`valid_until` required).
4. **Expired-source rotation:** because accepted catalog validation treats an expired entry as an invalid catalog, the active runtime catalog is a current slice, not an archive. Remove expired campaign entries and their passages during a reviewed update; do not silently weaken the accepted validator.
5. **No match is not a server error:** with a valid setting and valid catalog, a question that has no source for its active campaign returns the accepted no-evidence abstention. Missing/invalid configuration or malformed artifacts return the route's generic 503.

## Implementation plan and tasks

1. Add strict parse/validation for `MANIJERO_ACTIVE_CAMPAIGN`, injected through a small config boundary and testable without process-global mutation.
2. Extend catalog validation and readable schema for four-digit campaign labels and required `valid_until` on campaign-specific records. Add malformed and missing-boundary fixtures.
3. Add a small campaign selection boundary that validates the complete catalog and passage set, then selects eligible source IDs and linked passages for the configured campaign. Keep unknown references and invalid catalog data as errors.
4. Add the conservative explicit-year guard before any retrieval/generation. Test no year, current year, other year, repeated same year, and multiple distinct years.
5. Wire the active setting into `/ask`; preserve existing `prepare_corpus`, clarification, extractive generation, verifier, response models, and generic error handling.
6. Test exact `valid_until` boundary and after-expiry behavior with fixed dates; test that a matching source is never substituted from a different campaign.
7. Update OpenAPI 503 description, backend/knowledge README, architecture, and durable constraints; add a short operator note on changing the active campaign and rotating expired artifacts.
8. Run the focused contract and backend checks and append only observed evidence to the feature appendix and `PROGRESS.md`.

## Verification plan and evidence

- Validate a request with campaign 2026 and fixture sources tagged 2025, 2026, and campaign-neutral; verify only 2026 plus neutral passages are indexed.
- Verify a direct question mentioning 2025 while active campaign is 2026 abstains without returning 2026 sources; verify a two-year comparison also abstains.
- Verify missing/malformed active-campaign configuration does not leak the setting value, source text, or file path in HTTP responses or logs.
- Verify `valid_until == as_of` is eligible and `valid_until < as_of` is not; use explicit `as_of` dates and no real clock.
- Run contract examples and the focused campaign/endpoint test target. A test pass confirms implementation behavior only; it does not prove the source's legal interpretation.

## Validator checklist

- [ ] Campaign labels are strict four-digit years, and campaign-specific sources have a reviewed finite validity date.
- [ ] The active campaign is configured explicitly and never inferred from the system year, question topic, land record, or source text.
- [ ] The UTC `as_of` date and active campaign are independent inputs with separate boundary tests.
- [ ] Only campaign-neutral and exact-active-campaign passages can reach generation; other-campaign passages cannot leak into citations or excerpts.
- [ ] A question explicitly about another year or comparing years abstains before generation.
- [ ] Unknown source references and malformed full-corpus data remain located errors; filtering does not hide bad artifact structure.
- [ ] Expired entries are removed from runtime files during reviewed rotation; historical sources are not silently retained as answer evidence.
- [ ] Every `/ask` request requires valid campaign configuration; missing/invalid values fail closed with generic 503 while `/health` stays liveness-only.
- [ ] Request and response shapes, privacy, land clarification, and grounding verifier behavior remain accepted and unchanged.
