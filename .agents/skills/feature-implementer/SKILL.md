---
name: feature-implementer
description: Implement exactly one planned feature from a feature spec file under docs/specs. Use when the user asks to implement a feature spec, execute the selected feature, act as the generator/implementer in a planner-generator-validator workflow, or turn a feature implementation spec into code. The skill self-verifies the work, updates progress/evidence, and updates durable documentation when required, but it does not perform final independent validation.
---

# Feature Implementer

Use this skill to implement one already-planned feature. The implementer writes code, runs the required checks, records evidence, and leaves the repository ready for an independent validator.

## Role Boundary

You are the implementer/generator, not the planner and not the final validator.

- Do implement the selected feature.
- Do self-verify with the checks required by the spec and repo harness.
- Do update status, progress, evidence, and required durable docs.
- Do not broaden the feature scope.
- Do not silently redesign the spec. If the spec is wrong or blocked, update the spec with findings or mark the feature blocked instead of improvising.
- Do not declare final acceptance. Leave that for `feature-validator`.
- Treat `passing` as "implemented and self-verified, ready for independent validation", not as final acceptance.
- Never set a feature to `accepted`; only the main orchestrator may persist `accepted` after an independent validator returns `accept`.

## Inputs To Read First

1. `../../../AGENTS.md`
2. `../../../PROGRESS.md`
3. `./scripts/select-feature.sh --next` (feature selection); read `feature_list.json` only when you must update the selected feature's status
4. Selected feature spec contract: `../../../docs/specs/<feature-id>.md`, plus its appendix `../../../docs/specs/<feature-id>.appendix.md` for repository research, the implementation plan and tasks, the validator checklist, and existing evidence.
5. Durable docs if present and relevant:
   - `../../../ARCHITECTURE.md`
   - `../../../CONSTRAINTS.md`
   - `../../../DESIGN.md` when the spec has UI or visual behavior
   - relevant docs under `docs/`
6. Existing application files named in the spec contract's expected file changes and the appendix's repository research.

If no feature id is provided, run `./scripts/select-feature.sh --next` and use `NEXT_FEATURE` / `NEXT_ROLE`; do not read or re-derive `feature_list.json` by hand. Proceed only when `NEXT_ROLE=implementer`. If `NEXT_ROLE=validator`, the feature is `passing` and belongs to `feature-validator`; if `NEXT_ROLE=planner`, stop and ask the user to run the planner/spec step first; if `NEXT_ROLE=none`, report `NEXT_REASON`/`NEXT_BLOCKED` and stop.

A dependency is satisfied when its status is `accepted` (`passing` is not accepted) and never selects a `blocked` feature. Run `./scripts/select-feature.sh --status` if you need the per-feature readiness of the unfinished set.

If no spec exists for the selected feature (the selector prints `NEXT_SPEC=-` and `NEXT_ROLE=planner`), stop and ask the user to run the planner/spec step first.

## Workflow

### 1. Confirm The Contract

Read the selected spec contract (`../../../docs/specs/<feature-id>.md`) and identify:

- goal and non-goals,
- acceptance scenarios,
- expected file changes,
- durable documentation impact,
- the focused verification block.

Read its appendix (`../../../docs/specs/<feature-id>.appendix.md`) for the repository research, implementation tasks, verification plan, evidence to capture, and validator checklist.

If the spec is too vague for implementation, stop with a concise blocker and recommend revising the spec.

### 2. Set Feature State

Before code changes, ensure `feature_list.json` reflects one active feature:

- mark the selected feature `in_progress` if it is not already,
- keep all unrelated unfinished features `not_started`,
- do not mark anything `passing` before verification evidence exists.

### 3. Implement Only This Feature

Make the smallest coherent set of changes needed to satisfy the spec.

Rules:

- Load skill `clean-code-solid-architecture` and follow it pragmatically.
- Follow existing repository patterns.
- Keep WIP=1.
- Do not implement adjacent features from `feature_list.json`.
- Add regression/unit/integration/smoke tests when they fit the feature and current repo maturity.
- If the repo has a persistent E2E command such as `pnpm test:e2e` and the selected feature changes user-visible behavior, authentication, authorization, routing, or API flows, add or update focused E2E coverage unless the spec explicitly justifies not doing so.
- Use `references/implementation-rules.md` for durable documentation rules.

### 4. Self-Verify

Run the spec's verification plan and the repo's standard gate, cheapest tier first: `./scripts/init.sh --feature <feature-id>` (the focused block the spec publishes), then `./scripts/init.sh --fast`, and `./scripts/init.sh --verify` when the change touches the Android/Desktop surface, packaging, or shared public behavior. If a required check cannot run, document exactly why and what is missing.

If the feature creates or updates `scripts/init.sh`, make it an executable non-blocking gate: some invocation (a checks-running default, or named tiers such as `--feature`/`--fast`/`--verify`) must run the standard verification checks for the current repo state and fail on error, and none may start long-running dev servers. A print-only invocation is acceptable only as the cheapest informational tier when the script also exposes real checks-running tiers; a script that can *only* print the checks is not enough unless the repo is still pre-bootstrap.

Self-verification should include the strongest applicable levels available today:

1. static/syntax checks,
2. tests and runtime/startup checks,
3. persistent E2E checks when the repo has them and the feature affects an observable user/API flow,
4. manual user-flow or smoke checks when persistent E2E is not yet available or cannot cover the case.

If any required check fails, fix it or leave the feature non-passing with a clear blocker. Do not hide failures.

### 5. Update Harness State

After verification:

- update `feature_list.json` for the selected feature only (status, and the `spec`/`validation` paths); it is a lean index, so do not add an `evidence` array,
- record exact evidence for checks that passed in the `Feature evidence` section of `../../../docs/specs/<feature-id>.appendix.md`; never copy the same verification elsewhere,
- do not append verification prose to `../../../docs/progress/session-log.md`; the main orchestrator adds one pointer line when the feature is accepted. Update the `../../../PROGRESS.md` status board only when the accepted set, open items, or honesty limits change,
- update the session handoff note if it exists or if the session leaves meaningful incomplete state,
- update durable docs required by the spec or discovered during implementation.

CONSTRAINTS.md rule: read `../../../CONSTRAINTS.md` before implementing (see Inputs To Read First). When implementation or verification reveals a durable operational constraint (a MUST/MUST NOT rule future features have to respect), append it to `../../../CONSTRAINTS.md` with a short reason. Do not add speculative rules or restate what the spec, `../../../AGENTS.md`, or `../../../ARCHITECTURE.md` already cover; follow the durable documentation rules in `references/implementation-rules.md`.

Status rule:

- `passing` means required verification passed and evidence is recorded.
- `passing` does not mean independently accepted. It means the implementer believes the feature is ready for `feature-validator`.
- `accepted` means an independent validator returned `accept` and the main orchestrator persisted that acceptance.
- `blocked` means implementation cannot continue and the reason is durable in `../../../PROGRESS.md` and/or the feature entry.
- If implementation is partial or unverified, leave `in_progress` or `blocked`, not `passing`.

### 6. Leave Validator-Ready State

Before finishing, ensure a fresh validator can review without this chat:

- source changes are saved,
- generated temporary files are removed,
- checks/evidence are recorded,
- docs and harness state are consistent,
- final response lists changed files and verification run.

## Output Summary

Report:

- selected feature id and spec path,
- what was implemented,
- verification commands/checks and results,
- files changed,
- harness/docs updated,
- whether the feature is ready for independent validation.