---
name: feature-flow
description: Orchestrate the planner, implementer, and validator workflow for one feature using the project's configured subagents. Use when the user asks to run the feature flow, continue the next available feature, delegate to planner/implementer/validator agents, or move a feature through spec, implementation, and validation.
---

# Feature Flow

Use this skill to let the main agent coordinate the three project subagents:

- `planner` wraps `$feature-spec`.
- `implementer` wraps `$feature-implementer`.
- `validator` wraps `$feature-validator`.

The main agent is the orchestrator. It chooses the next role, launches the right subagent, reviews the result, and keeps the same feature moving until the flow reaches an explicit stop condition.

## Hard Rules

- Work on one feature at a time.
- Do not run planner, implementer, and validator in parallel for the same feature.
- Do not skip roles unless the required artifact already exists and is current.
- Do not implement work in the main agent while a subagent owns that role.
- Subagents do not create commits. The main orchestrator owns final staging and commit after validator acceptance.
- Do not treat `passing` as accepted. `passing` means implementer self-verification passed; validator `accept` is independent.
- After validation returns `accept`, persist acceptance by changing the selected feature status in `feature_list.json` from `passing` to `accepted`. `feature_list.json` is a lean index, so never add an `evidence` array: the feature's evidence belongs in that feature's appendix (`docs/specs/<feature-id>.appendix.md`, section `Feature evidence`) and its acceptance record in `docs/validations/<feature-id>.md` — the two canonical stores; `docs/progress/session-log.md` gets one pointer line per accepted feature and never restates evidence.
- If validation returns `revise`, route the repair brief back to `implementer` for the same feature.
- Verification is tiered, and each tier must be reachable: a spec that publishes no focused command block is incomplete, and implementer/validator runs use `./scripts/init.sh --feature <feature-id>` and `./scripts/init.sh --fast` before paying for `./scripts/init.sh --verify`.
- After a `revise` repair, route the same feature back to `validator`; do not stop after the repair unless the user explicitly asked for a single role step.
- If validation returns `block`, stop and report the blocker.
- After validation returns `accept`, stage only the accepted feature's changes and create a Conventional Commit before selecting or reporting the next feature.
- After every accepted feature pass, the main orchestrator must report what changed and how the user can try it locally. The implementer supplies raw verification notes, the validator checks they are real, and the orchestrator presents the final user-facing testing steps after the commit.
- Do not push commits unless the user explicitly asks for a push.

## Inputs To Read First

1. `../../../AGENTS.md`
2. The **Current state** section of `../../../PROGRESS.md`; read other sections only when the task needs them
3. `./scripts/select-feature.sh --next` (feature selection); read `feature_list.json` only when you must update a feature's status
4. `docs/specs/` if present
5. `docs/validations/` if present
6. Current git status

## Feature Selection

Run `./scripts/select-feature.sh --next`. It reads `feature_list.json` and prints the selected feature id and its next role; do not read or re-derive the index by hand.

- `NEXT_FEATURE` / `NEXT_ROLE` — the next dependency-ready feature and the role to run (`planner`, `implementer`, or `validator`).
- `NEXT_ROLE=none` — no dependency-ready unfinished feature. `NEXT_REASON=all features accepted` means the list is complete; otherwise `NEXT_BLOCKED` lists each blocked id and its unmet `depends_on` ids — report those instead of selecting a later blocked feature.
- When the user provides a feature id, use that feature; take its role from the Role Selection rules below (the selector does not know a user-chosen id).

Run `./scripts/select-feature.sh --status` for the whole-board view: a `SUMMARY` line by status, the next feature/role, and one `FEATURE` line per unfinished feature with `ready`, `unmet`, `role`, and `spec` state. When the user asks what can run in parallel, list the unfinished features with `ready=yes` in `feature_list.json` order.

The selector treats a dependency as satisfied only when its status is `accepted` (`passing` is not accepted) and never selects a `blocked` feature. It picks, in order: an `in_progress` feature, then the first `passing` feature, then the first dependency-ready unfinished feature that has a spec, then the first that has none.

## Role Selection

`./scripts/select-feature.sh --next` reports `NEXT_ROLE` for the selected feature using the rules below; apply the same rules when the user provides a feature id. The selector checks whether the spec file exists, so you must still judge rule 1 when the spec is present but stale.

For the selected feature:

0. If the feature status is `accepted`, report that the feature is already planned, implemented, and accepted; select the next available feature if the user asked to continue.
1. If `../../../docs/specs/<feature-id>.md` is missing or stale, run `planner`.
2. Else if the feature is neither `passing` nor `accepted`, run `implementer`.
3. Else if the feature is `passing`, run `validator`.

Validation records should live under `../../../docs/validations/<feature-id>.md` when the validator or main agent persists them. If the validator only reports in chat, the main agent should ask before writing a validation record unless the user requested persistence.

## Configured Subagents

Launch the project subagents configured for the active agent runtime.

Send only dynamic handoff context:

- repository path,
- selected feature id,
- selected role,
- spec path when applicable,
- validator repair brief when applicable,
- expected output summary.

Do not duplicate the subagent role prompts in this skill. The stable role instructions live in the configured subagent files.

## Orchestration Loop

Default behavior for this skill is until-accepted mode for one feature. Do not stop after a planner, implementer, or repair step while the next required role is clear.

Mode summary: until-accepted is the default full pipeline for one feature; one-step runs a single role only when explicitly requested; next-feature only selects and reports after an accept, never auto-starts.

- Until-accepted mode: run planner -> implementer -> validator sequentially for one feature, stopping only when the validator returns `accept`, the validator returns `block`, or a subagent cannot continue.
- Repair loop: if validator returns `revise`, run `implementer` with the repair brief, then run `validator` again for the same feature.
- One-step mode: run only the next required role and report the result only when the user explicitly asks for a single step, dry run, preview, or next-role-only execution.
- Next-feature mode: after accept, select the next feature and report the next required role; do not start it unless asked.

## Commit On Acceptance

Creating the commit is the main orchestrator's final step after the validator returns `accept`; subagents never commit (see Hard Rules). The orchestrator must commit the accepted feature before reporting the flow complete.

1. Run `git status --short` and inspect the relevant diff.
2. Persist acceptance by updating `feature_list.json` for the selected feature to status `accepted`, keeping its `spec`/`validation` paths current. Do not add an `evidence` array. Create or update `../../../docs/validations/<feature-id>.md` with the acceptance record, and record the verification in the `Feature evidence` section of `../../../docs/specs/<feature-id>.appendix.md`. Add one pointer line for the accepted feature to `../../../docs/progress/session-log.md` (link the spec and the acceptance record; do not restate verification there), and update the `../../../PROGRESS.md` status board if the accepted set or open items changed.
3. Identify the files changed for the accepted feature, including required harness/docs/evidence updates.
4. Stage only those files. Do not stage unrelated user or other-agent changes.
5. Create one Conventional Commit, using a message that names the feature. Prefer:
   - `feat: complete <feature-id>` for user-visible product/platform features,
   - `docs: complete <feature-id>` for documentation-only features,
   - `chore: complete <feature-id>` for workflow/tooling-only features.
6. If the accepted feature's changes cannot be isolated from unrelated work, stop and report the commit blocker instead of making a mixed commit.
7. Do not push the commit unless the user explicitly requested a push.
8. After the commit succeeds, select the next available feature and report the next required role. Do not start the next feature unless asked.

## Final User Handoff

After a validator `accept` and successful commit, the main orchestrator must give a concise user-facing handoff. Do not delegate this final handoff to a subagent.

The handoff headings below are intentionally in Spanish: the skill is written in English, but the final handoff is addressed to the Spanish-speaking user.

Include:

- `Qué se ha hecho`: 2-5 bullets summarizing the accepted behavior, not internal noise.
- `Cómo probarlo`: the command that actually exercises the accepted feature — the spec's focused block `./scripts/init.sh --feature <feature-id>`, or `CI=true ./scripts/init.sh --fast` for the no-device surface (`CI=true ./scripts/init.sh --verify` for the full gate). Never present the bare `./scripts/init.sh`: it only prints a toolchain banner and exits 0 without running any check. Plus concrete manual/local steps when the feature has observable behavior. Prefer commands the user can run directly. If manual testing needs env vars, database, a dev server, or a port, state that explicitly.
- `Validación`: validator verdict and the most relevant checks/smokes that actually ran.
- `Commit`: hash and Conventional Commit message.
- `Siguiente`: next feature id and next required role/action.

When no meaningful manual test exists, say so and explain the closest verification command. Do not invent product behavior that was not implemented.

## Reviewing Subagent Results

After a subagent returns:

- verify the expected artifact exists or the expected verdict is present,
- check that the subagent stayed in role,
- check for obvious missing state updates,
- summarize the next action.

Do not redo the subagent's work unless it clearly failed or the user asks.

## Output Summary

Report:

- selected feature id,
- role executed,
- subagent used,
- artifact or files produced/updated,
- verification or verdict summary,
- user-facing summary of what changed,
- user-facing instructions for how to test the accepted feature locally,
- commit hash and commit message when a commit was created,
- next required role/action.
