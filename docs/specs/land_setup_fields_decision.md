# Feature Spec: `land_setup_fields_decision`

## Source metadata

- **Feature:** `land_setup_fields_decision` — Decide the minimum land setup fields (`lands`).
- **Status at planning:** `not_started`; dependencies `add_land` and `minimal_land_context` are accepted.
- **Source behavior:** Settle the minimum fields asked during first setup, including whether approximate area is essential to an MVP question.
- **Source verification:** Review real user questions and test a minimal record with target users.
- **Feature-list note:** Resolve the open product question before changing setup fields.

## Goal and boundaries

Make an evidence-based, explicit product decision about whether the current short add-land setup is sufficient or whether area or another field is necessary. This is a decision/documentation feature, not an implementation of new fields. Preserve the existing rule that unknown values remain unknown and that setup is short.

**In scope**
- Review the questions supported by the current MVP and determine whether any requires approximate area to answer safely/usefully.
- Validate the proposed minimum record with intended users, prioritizing low digital confidence; document evidence and limits.
- Decide the minimum first-setup field set and whether optional fields are deferred, collected, or merely retained in the domain model.
- Record rationale and downstream consequences for form, privacy disclosure, and minimal chat context.

**Non-goals**
- Implement form, storage, API, disclosure, or chat changes; add area/notes fields to UI; change serialization or land context.
- Add precise parcel identifiers, maps, SIGPAC, eligibility calculations, or legal claims.
- Treat synthetic evaluator fixtures or developer preference as user evidence; infer that missing attributes are zero/none.
- Decide backup/recovery or desktop layout (separate features).

## Job story

When I first save a land, I want to be asked only for information that helps the app answer my questions, so setup stays understandable and I am not pressured to guess.

## Acceptance scenarios

### Decision is grounded in MVP questions
Given the current supported MVP question slice and land-context contract, when the decision is recorded, then each proposed required field is linked to a concrete question/use and the spec states whether approximate area is essential; no legal or eligibility inference is made.

### Minimal record is checked with intended users
Given a short proposed setup record and a representative target user (including low digital confidence where feasible), when the user is asked to complete or review it and describe what each field means, then observations, participant/context limitations, and unresolved comprehension issues are recorded without claiming broad usability from a single session.

### A clear minimum field set is approved
Given the evidence and existing domain/privacy constraints, when the decision is published, then it explicitly classifies fields as required, optional at setup, deferred, or retained-only, and states whether the current `name`, municipality, water regime, and production method choices remain unchanged.

### Downstream changes are bounded
Given the decision requires a later product change, when this feature is accepted, then affected owner specs/features are named; no production form, storage, request, or disclosure behavior has been changed in this decision feature.

## Technical approach

1. Inventory real MVP-supported question categories from `docs/build-brief.md`, `knowledge/pac_coverage.md`, `docs/specs/minimal_land_context.md`, and domain model. Distinguish the current narrow PAC corpus from hypothetical future questions.
2. Assess each candidate field against a concrete supported use, privacy/minimization cost, and safe behavior when unknown. Area is currently persisted in `Land` but not collected by add/edit UI and is not among the `MinimalLandContext` attributes; do not assume it should be transmitted.
3. Conduct/commission a small formative check using the short setup and a plain-language explanation. Record method, anonymized observations, whether prompts were understood, and limits; do not collect unnecessary personal details.
4. Publish a decision record in the risks/open-questions register (or an explicitly linked product decision document if substantial evidence warrants it). Update the relevant source feature notes only if asked/approved; this feature does not implement the resulting change.
5. If findings call for form or payload changes, identify follow-up feature(s) and contracts rather than silently broadening this scope.

## Expected file changes

- **Update** `docs/risks-and-open-questions.md`: resolve the blocking first-setup-fields question with the decision, evidence basis, and caveats, or retain it as open with a precise evidence gap if target-user evidence was unavailable.
- **Update** this contract and appendix with the final decision/evidence and downstream handoffs.
- **Do not modify** application code, `feature_list.json`, `PROGRESS.md`, land persistence/API contracts, or user-facing copy in this decision-only slice.

## Visual design impact

None. No UI behavior, form, labels, or layout changes. Any later field change must follow `DESIGN.md` and the land form accessibility contract.

## Durable documentation impact

- `docs/risks-and-open-questions.md`: **update** the blocking question with evidence-based outcome or a clearly bounded remaining unknown.
- `docs/specs/land_setup_fields_decision.md` and `.appendix.md`: **update** with decision and traceable evidence.
- `CONSTRAINTS.md`: **not needed**; no durable engineering constraint is introduced unless the decision changes one.
- `ARCHITECTURE.md`: **not needed**; no architecture change.
- `AGENTS.md`, `CONTEXT.md`, `docs/domain-model.md`, `docs/build-brief.md`, `DESIGN.md`: **not needed** for the decision record; update only if the approved decision changes product-wide guidance, which is a separately reviewed follow-up.
- `feature_list.json` / `PROGRESS.md`: **after independent validation only**.

## Focused verification

Documentation-only decision: validate the repository's contracts and inspect the documented record; there is no automated target-user test command. The command is executable and is the cheapest relevant repository check.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
```
<!-- verify:end -->

Manual evidence check: confirm decision explicitly cites reviewed question scope, method and limits of user evidence, field classifications, and any follow-up owner; no participant personal data is included.

## Appendix

Planning record, repository research, decision procedure, evidence capture, and validator checklist: [`land_setup_fields_decision.appendix.md`](land_setup_fields_decision.appendix.md).

## Decision and evidence (2026-10-20)

### Decision

Keep the current first-setup choices unchanged pending formative user evidence: **name is required; municipality is optional; water regime and production method are optional and may remain unknown**. Do not add area or notes to the form, request payload, privacy notice, or chat context. Area is **not essential to any question in the currently supported PAC Andalucía 2026 slice**. This is a bounded product decision to preserve the existing short setup, not a claim that these fields are a user-validated optimal minimum.

The reviewed supported questions concern the SGA/recognized-entity submission route (including its stated national exception), the 2026 filing deadline, and the distinct 2026 modification deadline. None asks for a land's size, location, water regime, or production method. Hypothetical future farm-management, parcel, personalized aid, or eligibility questions do not establish a current need. Land attributes do not establish eligibility, and no legal conclusion is made here.

### Field disposition

| Field | First setup disposition | Supported use / unknown handling |
|---|---|---|
| Name/nickname | Required; unchanged | Locally distinguishes records; never transmitted in minimal chat context. |
| Municipality | Optional at setup; unchanged | Available for a future/current location-sensitive question; unset stays omitted, never inferred. No question in the reviewed PAC slice requires it. |
| Water regime | Optional at setup; unchanged | Available when a question needs it; `unknown` remains unknown. No question in the reviewed PAC slice requires it. |
| Production method | Optional at setup; unchanged | Available when a question needs it; `unknown` remains unknown. No question in the reviewed PAC slice requires it. |
| Approximate area | Deferred; not collected in setup and not sent | No current supported question needs it. Do not infer area or treat absence as zero. Reconsider only with a concrete supported use and user evidence. |
| Free-text notes | Deferred; not collected in setup and not sent | No identified current question/use justifies the extra effort and privacy exposure; notes are not trusted legal evidence. |

### Evidence and limits

This decision is based on desk review of the product question scope in [`docs/build-brief.md`](../build-brief.md), the approved narrow coverage in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md), the existing [`add_land`](add_land.md) and [`minimal_land_context`](minimal_land_context.md) contracts, and [`docs/domain-model.md`](../domain-model.md). The review found no area-dependent question among the three currently supported procedural topics; the minimal context contract also excludes area and notes and sends only needed municipality, water, or production values.

No target-user session was conducted or commissioned in this implementation. There are therefore **no participant observations or comprehension results**. In particular, understanding of “municipio”, “riego”, “producción”, or `No lo sé`, and whether omitted area blocks an actual task, remain untested. This desk review is not usability evidence and does not close the user-validation requirement. The existing feature contracts and their prior implementation evidence are not a substitute for this check.

### Downstream boundary

No production form, storage, request, disclosure, or user-facing copy changed. Existing owner contracts remain in force: [`add_land`](add_land.md) owns setup fields, [`minimal_land_context`](minimal_land_context.md) owns the three-attribute payload, and [`land_data_disclosure`](land_data_disclosure.md) owns its matching notice. If formative research identifies a needed field, create/approve a scoped follow-up under the owning form/data/context/disclosure features before changing behavior. Until then, do not expand the form or payload.
