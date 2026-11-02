@AGENTS.md

## Claude Code notes

`AGENTS.md` above is the single source of truth for every agent runtime. Change shared rules there, not here; this file only maps the shared harness onto Claude Code.

- Skills: `.claude/skills` is a symlink to `.agents/skills`, so the same skills load in Claude Code. Where a skill says `$<skill-name>`, invoke that skill by name.
- Subagents: `.claude/agents/` holds the `planner`, `implementer`, and `validator` wrappers that `feature-flow` launches. They mirror `.codex/agents/` and `.opencode/agents/`; keep the three runtimes in sync when a role changes. Model choice is runtime-specific and is not mirrored: in Claude Code `implementer` and `validator` run on `model: sonnet` to save tokens. The implementer works from a bounded spec, and the validator's reruns decide pass or fail. Only `planner` inherits the session model, because the spec drives every later role. If a validator verdict looks shallow, or an implementer is stuck on the same failure after two repair rounds, rerun that role on the session model before trusting it.
- One session per feature: start each feature with `./scripts/feature-session.sh [feature-id]`, which opens a new `claude` session running `feature-flow` for that feature only (default: the selector's next feature). In a repair loop, continue the implementer with `SendMessage` instead of launching a new one.
- Headless runs: `./scripts/feature-session.sh --headless <feature-id>` runs `claude -p` with JSON output, the owner-approved tool scope (edits in the checkout, project scripts, Python, Gradle, and local commits; no push, `gh`, or amend), and a usage line in `build/agent-sessions/usage.tsv`. `github-flow` uses it for every worktree session.
