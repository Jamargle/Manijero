# Appendix — `land_setup_fields_decision`

Planning and verification record for [`land_setup_fields_decision.md`](../../specs/land_setup_fields_decision.md).

## Repository research

Inspected:

- `feature_list.json`: feature depends on accepted `add_land` and `minimal_land_context`; source question is explicitly recorded as blocking in risks register.
- `docs/risks-and-open-questions.md`: asks which fields are required at first setup and whether approximate area is essential; proposed evidence is review of real questions plus target-user test.
- `docs/archive/build-brief.md`: current minimum useful details are name, municipality, water regime, production method; area/notes only if they help an identified MVP question.
- `docs/domain-model.md`: area is optional and only collected if an MVP use case needs it; never infer it. Unknown is valid for water/production; land data does not establish eligibility.
- `docs/specs/add_land.md`: current form requires name, municipality optional, water and production default unknown; area and notes intentionally not collected pending validation.
- `docs/specs/minimal_land_context.md`: sends only municipality, water regime, production method when needed; explicitly excludes area and notes.
- `knowledge/pac_coverage.md` and `shared/.../lands/Land.kt`: inspect current coverage/model during implementation before deciding; repository research observed that area is persisted but not in the minimal-context contract.
- `DESIGN.md`: short plain-Spanish setup, progressive disclosure, accessibility and low-confidence user validation direction.

The question is well-sized as a decision feature, not a code change. Critical unknown: whether actual target-user input can be obtained; developer-authored examples alone cannot close that evidence requirement. Do not expand into multiple new fields or implementation.

## Implementation plan and tasks

1. Read current approved question coverage and identify what land attributes those questions actually require; separate known supported use cases from hypothetical future features.
2. Compare fields (name, municipality, water, production, area, notes) by concrete use, privacy/effort, and handling when unknown. Record why not collecting a field is acceptable or what safe limitation remains.
3. Prepare a short, non-leading test of the current minimal record. Ask participants to explain labels/choices and identify whether any omitted field blocks a real task; avoid asking for actual sensitive farm details.
4. Run the check if feasible and record anonymized method, participant profile in broad terms, observations, and limits. If infeasible, preserve the open question and state what evidence is still needed; do not manufacture a resolution.
5. Update the risks register and this appendix/contract. If outcome calls for a form, storage, payload, or disclosure change, list the owning follow-up feature(s) and stop before implementing.

## Verification plan

- Run `python3 contracts/validate_examples.py` to ensure the existing API contract examples remain valid; this is a regression sanity check, not proof of user research.
- Manually validate the decision against the enumerated MVP questions and the current `add_land` / `minimal_land_context` contracts.
- Verify the evidence record includes method, scope, limitations, result, and clear field disposition; check that it contains no participant-identifying or unnecessary farm details.
- No persistent UI/E2E harness exists, and this feature changes no executable product behavior. No build is warranted unless implementation scope is explicitly expanded.

## Evidence to capture

- Question/use-case inventory with links to authoritative product/corpus artifacts.
- Anonymized user-check method and observations, participant/context count at an appropriately non-identifying level, and explicit sampling limitations.
- Field-by-field disposition: required, optional at setup, deferred, or retained-only; treatment of unknown values; whether area is essential to any current supported question.
- Decision rationale and downstream follow-up identifiers. Separate observed evidence from judgment and unresolved assumptions.

## Feature evidence

### 2026-10-20 — implementer

- Desk-reviewed `docs/archive/build-brief.md`, `knowledge/pac_coverage.md`, `docs/domain-model.md`, and the accepted `add_land` / `minimal_land_context` contracts. Current supported scope is limited to SGA submission route, 2026 filing date, and 2026 modification date; no reviewed question requires approximate area. The current context contract excludes area and notes.
- **No intended-user test was conducted**: no target-user participant or session was available in this implementation. No observations or comprehension results are claimed. Low-digital-confidence comprehension and whether omitted fields block a real task remain open evidence gaps.
- Decision recorded in the contract and risk register: leave current field choices unchanged provisionally (name required, municipality optional, water/production optional and unknown-valid); defer area and notes; area is not essential to a currently supported question. This is explicitly not a user-validated final minimum.
- Downstream behavior remains unchanged. Potential changes belong to `add_land`, `minimal_land_context`, and `land_data_disclosure` owners and need a separately scoped approved follow-up.
- `./scripts/init.sh --feature land_setup_fields_decision` — passed; ran `python3 contracts/validate_examples.py`, validating 2 request and 3 response examples against `answer_api_contract`.
- `./scripts/init.sh --fast` — passed all 9 concurrent checks: shared JVM tests, contract examples, source catalog, retrieval, generation, abstention, clarification, land safety; backend pytest suite was explicitly skipped because pytest is not installed (harness printed its installation recipe). All other fast-tier checks completed successfully.
- Manual evidence check — passed: reviewed scope/source links, method and explicit absence of target-user evidence, each field classification, unknown handling, downstream owners, and absence of personal data. User comprehension remains an explicitly recorded gap, not an assertion of validation.


## Validator checklist

- [x] Decision addresses the exact blocking question: minimum required setup fields and area necessity.
- [x] Current supported question scope is cited; hypothetical future utility is not presented as current need.
- [x] Target-user evidence is recorded if conducted; otherwise the uncertainty remains explicitly unresolved rather than falsely accepted.
- [x] Every field has an explicit disposition and unknown values are not converted to guesses/default facts.
- [x] No legal eligibility claim or unsupported regulatory statement is introduced.
- [x] Privacy/minimization and the existing three-attribute chat context boundary are considered.
- [x] No product source, code, form, API, persistence format, or feature status is changed in this decision-only work.
- [x] Required follow-up implementation is delegated to a named feature/spec before any behavioral change.
- [x] Contract examples pass and decision evidence contains no personal identifying details.
