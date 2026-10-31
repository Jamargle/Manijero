# Feature Spec Templates

A feature has two files. Keep each within the size budget in `../SKILL.md` and say each fact once: the contract owns behavior and verification, the appendix owns research, plan, and evidence. Drop any section that would only say "not applicable", except the ones marked required.

## Contract: `../../../../docs/specs/<feature-id>.md`

```md
# <feature title>

## Source metadata

- `id`: <feature-id> · `area`: <area> · `depends_on`: <ids> · `status` at planning: <status>
- User-visible behavior: <one or two sentences>
- Verification: <one sentence; the commands are in Focused verification>
- Notes: <scope decisions, owner decisions, or none>

## Goal

<One short paragraph: the outcome this feature must enable.>

## Non-goals

- <Adjacent behavior or feature that must not be pulled in.>

## Job story

When <situation>, I want to <action>, so I can <outcome>.

## Acceptance scenarios

### 1. <happy path>

Given <state> · When <action> · Then <observable result>

### 2. <edge or error path>

Given <state> · When <action> · Then <observable result>

## Technical approach

<A few bullets an implementer can execute without re-planning. Name boundaries and patterns; link `ARCHITECTURE.md` or `CONSTRAINTS.md` sections instead of restating them.>

### Files Inspected

- `<path>` — <why it matters>

### Existing Patterns To Follow

- <Pattern, convention, command, or architectural choice found in the repo.>

### Current Gaps

- <Missing app infrastructure, missing command, missing table, unknown integration, etc.>

## Technical Approach

<Describe the implementation strategy at a high enough level that another agent can execute it without re-planning.>

## Expected File Changes

- `<path>` — create/modify; <reason>
- `<path>` — create/modify; <reason>

## Visual design impact

UI involved: yes/no. If yes: affected screens and states, and the `DESIGN.md` sections that apply. If `DESIGN.md` lacks what is needed, record it as a planning gap.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update/not needed — <reason>
- `CONSTRAINTS.md`: update/not needed — <rule in one line, or reason>
- `AGENTS.md`: update/not needed — <reason>
- Other: <path or none> — <reason>

Update `AGENTS.md` only when the agent workflow, startup path, or repo-wide rules change; `ARCHITECTURE.md` when a boundary, layer, runtime surface, or adapter changes; `CONSTRAINTS.md` when a durable MUST/MUST NOT rule appears.

## Focused verification (required)

<!-- verify:start -->
```sh
<cheapest commands that touch what this feature changes: targeted test files or filters, quiet flags>
```
<!-- verify:end -->

## Appendix

See [`<feature-id>.appendix.md`](<feature-id>.appendix.md) for research, plan, evidence, and the validator checklist.
```

## Appendix: `../../../../docs/specs/<feature-id>.appendix.md`

```md
# <feature-id> — appendix

## Repository research

- `<path>` — <one line: why it matters>
- Gaps: <missing infrastructure, command, or decision; or none>

## Implementation plan

1. <one line per ordered step>

## Verification plan

- <command or manual check> — <expected result>
- E2E: <coverage to add, or why unit/integration coverage is enough>

## Evidence to capture

- <test name, command result, or manual result to record below>

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

## Validator checklist

- [ ] Scope matches the contract; non-goals respected.
- [ ] Acceptance scenarios pass, with evidence.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature <feature-id>`.
- [ ] Durable documentation impact followed; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
```
