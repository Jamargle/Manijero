# Feature Spec: `hosting_provider_review`

## Source metadata

- **Feature:** `hosting_provider_review` — Review hosting and tunnel provider terms (`operations`).
- **Status at planning:** `not_started`; depends on accepted `backend_ask_endpoint` and `backend_campaign_validity`.
- **Source behavior:** Record current, source-linked choices for API hosting, managed tunnel, and private artifact delivery, including terms, privacy, reliability, and cost.
- **Feature-list verification:** A dated decision record compares the owned-server/tunnel path with a managed-host fallback using current official provider materials and states the selected path and blockers.
- **Feature-list note:** No hosted LLM is planned for the pilot. This review covers API hosting and network tunnel providers only.

## Goal and boundaries

Choose whether an owned server can reliably host the private API through a managed tunnel. If it cannot, select a managed API host using current official documentation. The review must not rely on MasterPlanV3's historical assumptions or make unverified claims about provider terms.

**In scope:** provider and service identity for hosting, managed tunnel, and private build delivery; current official terms, privacy/data processing, region, access control, TLS, logs/retention, support, limits, incident notice, cost, reliability prerequisites, and exit/rollback path; a written go/no-go decision by the project owner.

**Non-goals:** deployment implementation, provider account creation, hosted LLM selection, user research, or a legal compliance certification. Qualified privacy/legal review is tracked in `pilot_privacy_readiness`.

## Job story

When choosing where the pilot API runs and how it is reachable, I want a current evidence-based provider decision, so questions and service availability are not exposed to an unreviewed infrastructure provider.

## Acceptance scenarios

### Owned server meets pilot requirements

Given an owned server and managed tunnel candidate, when the project owner completes the review, then the record lists tested capacity/availability requirements, official terms and data handling, known costs/limits, operational prerequisites, and a clear go/no-go.

### Owned server is not viable

Given the owned server cannot meet the documented readiness bar, when the comparison is completed, then the record names the evaluated managed-host alternative and its official sources, or leaves hosting blocked if evidence is inadequate.

### Terms change

Given a provider's material privacy, terms, or pricing change, when the owner revisits the decision, then the current record is re-reviewed before the affected service continues for the pilot.

### No AI-provider implication

Given the selected infrastructure, when the record describes data flow, then it states that the current API uses extractive answers and makes no hosted-LLM call.

## Technical approach

Create a dated decision record with a small comparison matrix and direct official links for the host, tunnel, and artifact-delivery options, accessed date, exact relevant sections, data-flow notes, cost assumptions, operational requirements, decision owner, review trigger, and unresolved blockers. Do not copy legal text at length or infer legal compliance. If a provider cannot be selected with official evidence, keep the pilot deployment/distribution blocked and list the missing evidence.

## Expected file changes

- `docs/specs/hosting_provider_review.md` and appendix — decision contract and evidence template.
- `docs/risks-and-open-questions.md` — resolved hosting direction or precise remaining blocker.
- `README.md`/`backend/README.md` only if a later approved provider decision changes operator instructions.

## Visual design impact

None.

## Durable documentation impact

- `ARCHITECTURE.md`: update only after the chosen hosting boundary is implemented.
- `CONSTRAINTS.md`: no new invariant; preserve no hosted-LLM and data-minimization rules.
- `AGENTS.md`: not needed.
- `docs/risks-and-open-questions.md`: update the hosting/tunnel decision and review trigger.

## Focused verification

<!-- verify:start -->
```sh
git diff --check
```
<!-- verify:end -->

## Appendix

See [`hosting_provider_review.appendix.md`](hosting_provider_review.appendix.md).
