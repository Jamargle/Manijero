# Appendix — `answer_api_contract`

Planning and verification record for [`docs/specs/answer_api_contract.md`](../../specs/answer_api_contract.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/answer_api_contract.md` remains the authoritative
acceptance record.

## Repository research

- `docs/archive/MasterPlanV3.md` defines `POST /ask`, an answer status enum, typed sources, and clarification
  IDs, but says final details remain subject to contract review.
- `docs/domain-model.md` requires all-land default behavior, preservation of unknown attributes,
  and minimal land context.
- `docs/archive/build-brief.md` requires citations, verification dates, abstention, and plain Spanish.
- The current `shared` module is a generated Compose sample; no API client, backend, or test
  convention exists yet.

## Verification plan

Run:

```sh
python3 contracts/validate_examples.py
```

The validator must check all representative fixtures, required fields, status-specific invariants,
typed source metadata, unknown enum values, and rejection of forbidden land payload keys. Also review
the OpenAPI document for the three statuses, `POST /ask`, and the privacy description.

## Validator checklist

- [ ] OpenAPI 3.1 document defines `POST /ask` and reusable request/response schemas.
- [ ] All three statuses are explicit and mutually constrained.
- [ ] Sources include title, issuing body, stable URL, location, verification date, and excerpt.
- [ ] Clarification returns only existing land IDs and cannot carry an answer or sources.
- [ ] Fixtures cover general, all-land, answered, abstained, and clarification cases.
- [ ] Focused validation passes with no third-party dependencies.
- [ ] No application or unrelated feature files are changed.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Accepted after independent contract review: python3 contracts/validate_examples.py, Python syntax compilation, Ruby YAML parse, and git diff --check all passed; answered, abstained, and needs_land_clarification fixtures plus privacy rules were reviewed. Record: docs/validations/answer_api_contract.md.
