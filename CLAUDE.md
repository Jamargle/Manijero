@AGENTS.md

## Claude Code notes

`AGENTS.md` above is the single source of truth for every agent runtime. Change shared rules there, not here; this file only maps the shared harness onto Claude Code.

- Skills: `.claude/skills` is a symlink to `.agents/skills`, so the same skills load in Claude Code. Where a skill says `$<skill-name>`, invoke that skill by name.
- Subagents: `.claude/agents/` holds the `planner`, `implementer`, and `validator` wrappers that `feature-flow` launches. They mirror `.codex/agents/` and `.opencode/agents/`; keep the three runtimes in sync when a role changes. Model choice is runtime-specific and is not mirrored: in Claude Code only `validator` runs on `model: sonnet` to save tokens, because it reruns many checks and the commands, not the model, decide pass or fail. `planner` and `implementer` inherit the session model: the spec drives every later role and the implementer writes the code. If a validator verdict looks shallow, rerun it on the session model before trusting it.
- One session per feature: start each feature with `./scripts/feature-session.sh [feature-id]`, which opens a new `claude` session running `feature-flow` for that feature only (default: the selector's next feature). In a repair loop, continue the implementer with `SendMessage` instead of launching a new one.
- `github-flow`: where the skill says `opencode run --dir <worktree> "<prompt>"`, run `(cd <worktree> && claude -p "<prompt>")` instead. Everything else in the skill applies unchanged.
