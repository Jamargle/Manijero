@AGENTS.md

## Claude Code notes

`AGENTS.md` above is the single source of truth for every agent runtime. Change shared rules there, not here; this file only maps the shared harness onto Claude Code.

- Skills: `.claude/skills` is a symlink to `.agents/skills`, so the same skills load in Claude Code. Where a skill says `$<skill-name>`, invoke that skill by name.
- Subagents: `.claude/agents/` holds the `planner`, `implementer`, and `validator` wrappers that `feature-flow` launches. They mirror `.codex/agents/` and `.opencode/agents/`; keep the three runtimes in sync when a role changes.
- `github-flow`: where the skill says `opencode run --dir <worktree> "<prompt>"`, run `(cd <worktree> && claude -p "<prompt>")` instead. Everything else in the skill applies unchanged.
