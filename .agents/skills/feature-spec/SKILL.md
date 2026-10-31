---
name: feature-spec
description: Create an implementation-ready specification for one feature. Use when the user asks to plan a feature, create a feature spec, apply lightweight SDD/spec-driven development, prepare work for another implementation agent, or generate specs/tasks/technical plan. When no feature id is provided, use the repository selector and proceed only when its next role is planner.
---

# Feature Spec

Use this skill to turn one harness feature into an implementation-ready contract for another agent. The output is not a PRD and not implementation code. It is a planning artifact that lets a future implementation session execute with minimal rediscovery, and lets a later validation session judge the result.

## Hard Rules

- Plan exactly one feature per run.
- Do not implement code.
- Do not modify application source files.
- Do not generate specs for every feature unless the user explicitly asks after this skill finishes.
- Create or update only the feature's two spec files by default: the contract `../../../docs/specs/<feature-id>.md` and its appendix `../../../docs/specs/<feature-id>.appendix.md`.
- If the feature id is not provided, run `./scripts/select-feature.sh --next`. Proceed only when it reports `NEXT_ROLE=planner`; otherwise report the selected role or blocker and stop. Do not select or reorder features by reading `feature_list.json` yourself.
- If a feature is too broad to plan cleanly, stop and recommend splitting it in `feature_list.json` instead of producing a vague spec. Keep the contract near the 100–250 line target by moving research, implementation steps, and evidence to the appendix; split only when the feature contains independently usable behavior, not just because its contract is long.
- Treat the spec as a contract between agents: planner -> implementer -> validator.
- Prefer concrete repository findings over assumptions. If something was not inspected, say so.

## Inputs To Read First

1. `../../../AGENTS.md` — skip re-reading it when it is already in context (Claude Code loads it through `CLAUDE.md`)
2. The **Current state** section of `../../../PROGRESS.md`; read other sections only when the task needs them
3. `./scripts/select-feature.sh --next` when the user has not supplied a feature id
4. Existing feature spec if present: `../../../docs/specs/<feature-id>.md` and its appendix `../../../docs/specs/<feature-id>.appendix.md`
5. Current product and architecture docs as needed. For any file over ~200 lines, list its headings (`grep -n '^#' <file>`) and read only the sections the feature touches:
   - `../../../CONTEXT.md`
   - `../../../ARCHITECTURE.md`
   - `../../../CONSTRAINTS.md`
   - `../../../docs/domain-model.md`
   - `../../../DESIGN.md` when the selected feature has UI or visual behavior
   - `../../../docs/risks-and-open-questions.md`
   - `../../../docs/build-brief.md` and `../../../docs/technical-discovery.md` only as historical rationale; current requirements live in the guides and feature specs.
   - `../../../backend/README.md` or `../../../knowledge/README.md` for backend/knowledge work
6. Existing application files relevant to the selected feature. Inspect enough of the repo to identify expected file changes, patterns, commands, and risks.

If the selector cannot find `feature_list.json`, stop and tell the user to run the startup harness skill first.

## Workflow

### 1. Select The Feature

Use a user-provided feature id when present. Otherwise, run `./scripts/select-feature.sh --next` and continue only when the selected role is `planner`. The selector owns feature ordering, dependency checks, and role selection.

Use the selector's `NEXT_FEATURE`, `NEXT_ROLE`, `NEXT_REASON`, and `NEXT_BLOCKED` as the source for readiness and dependency decisions. Do not reconstruct the selection order or dependency rules from `feature_list.json`.

Before planning, verify scope from the user's request, an existing spec's `Source metadata`, or current discovery records. If the user-visible behavior or verification is missing everywhere, stop and report the missing decision rather than inventing it. The spec records source behavior, verification, and notes in its own `Source metadata` section. Do not edit feature status as part of planning.

### 2. Research The Repository

Investigate how to implement the selected feature in this specific repo:

- current app/framework state,
- existing routes, components, modules, tests, scripts, or conventions,
- relevant data models and migrations,
- relevant API boundaries,
- relevant auth/permission patterns,
- verification commands available today,
- persistent E2E commands available today, such as `pnpm test:e2e`, when the feature has user-facing or API-flow behavior,
- gaps caused by pre-bootstrap or missing infrastructure.

Record inspected files in the appendix as one line each (path and why it matters). Do not paste code excerpts that the implementer can open themselves, and do not pretend to have inspected files that do not exist.

### 3. Write The Contract And Its Appendix

Keep the spec concise but operational. A good default target is 100-250 lines. If it grows far 
beyond that, the feature may need splitting. Create or update `../../../docs/specs/<feature-id>.md` 
using `references/spec-template.md`.

Write two files, and do not create or edit any other spec file:

- `../../../docs/specs/<feature-id>.md` — the **contract**: the bounded top block a routine implement or validate read loads.
- `../../../docs/specs/<feature-id>.appendix.md` — the **record**: on-demand detail plus the growing `Feature evidence`.

The contract must include, in order:

- source feature metadata,
- goal and non-goals,
- job story or user story,
- acceptance scenarios in Given/When/Then style,
- technical approach,
- expected file changes,
- visual design impact when UI is involved,
- durable documentation impact,
- a focused verification block the harness can run: the exact shell commands for this feature, wrapped in `<!-- verify:start -->` and `<!-- verify:end -->` markers so `./scripts/init.sh --feature <feature-id>` executes them unchanged (see an accepted spec for the shape),
- an `## Appendix` section that points at the appendix file.

The appendix must include, in order:

- repository research,
- implementation plan and tasks,
- verification plan,
- evidence to capture,
- an empty `## Feature evidence` section for the implementer to append to,
- a validator checklist.

Size budget (every later role rereads these files, so length is paid for several times):

- Contract: at most 200 lines. Scenarios state observable results, not implementation steps.
- Appendix before `Feature evidence`: at most 200 lines. Plan steps are one line each; tests are named with the behavior they cover, not written out.
- Say each fact once: the contract owns behavior and verification, the appendix owns research and plan. Link instead of restating `CONSTRAINTS.md`, `ARCHITECTURE.md`, or another spec.
- Focused verification block: the cheapest commands that touch what the feature changes, using targeted pytest files or Gradle test filters rather than whole suites, and quiet flags such as `pytest -q`.

For a sense of the level of detail, look at an accepted compact pair such as `../../../docs/specs/recover_removed_lands.md` with its appendix.

### 4. Quality Gate

Before finishing, check:

- A future implementer can identify exactly what to build without reading this chat.
- A future validator can decide whether the implementation satisfies the spec.
- The plan names concrete files or directories where possible.
- The tasks are ordered and executable.
- Verification includes commands or manual checks available in the repo's current state.
- The focused verification block is executable as published: `./scripts/init.sh --feature <feature-id>` must run it without edits, and it must be the cheapest check that still touches what the feature changes.
- If a persistent E2E command exists and the feature changes user-visible behavior, authentication, authorization, routing, or API flows, the verification plan should include adding/updating focused E2E coverage or explicitly justify why unit/integration coverage is enough.
- For shell scripts such as `scripts/init.sh`, the spec states whether the script must execute checks, print guidance, start services, or provide modes. The default harness rule is: `scripts/init.sh` exposes a non-blocking, checks-running invocation (a default or named tiers) and must not start long-running dev servers. A print-only invocation is acceptable only as the cheapest informational tier alongside real checks-running tiers; a script that can *only* print the checks is not enough unless the repo is still pre-bootstrap.
- Durable documentation impact is explicit: `../../../ARCHITECTURE.md`, `../../../CONSTRAINTS.md`, `../../../AGENTS.md`, and other durable docs are each marked create/update/not needed with a reason.
- Non-goals prevent scope creep.
- The contract and appendix fit their size budgets, and no paragraph restates another file.
- Unknowns are explicit and do not hide blocking ambiguity.

If the spec fails this gate, revise it before reporting completion.

## Output Summary

Report:

- selected feature id,
- spec path,
- whether the feature looked correctly sized,
- key implementation risks,
- next suggested action: usually hand the spec to an implementation agent.
