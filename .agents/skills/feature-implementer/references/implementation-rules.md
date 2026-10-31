# Feature Implementer Rules

## Durable Documentation Rules

Code changes and durable knowledge changes travel together.

Update docs only when the change creates or changes knowledge future agents need:

- `../../../../AGENTS.md`: update only if the agent workflow, startup path, verification path, or repo-wide operating rules change. Keep it short and router-like.
- `../../../../ARCHITECTURE.md`: create/update when domains, layers, runtime surfaces, dependency direction, adapters/providers, or architectural boundaries are established or changed.
- `../../../../docs/constraints/<area>.md` (indexed by `../../../../CONSTRAINTS.md`): update when a durable MUST/MUST NOT rule appears that future agents must obey.
- `../../../../docs/specs/<feature-id>.md`: update if implementation discovers that the spec was wrong, incomplete, or materially changed by necessary findings.
- `../../../../docs/progress/session-log.md`: the main orchestrator adds one pointer line per accepted feature; do not append verification prose here (the `../../../../PROGRESS.md` status board changes only when the accepted set, open items, or limits change).
- `feature_list.json`: update the selected feature's status every implementation session. It is a lean index (`id`, `area`, `title`, `status`, `depends_on`, `spec`, `validation`); do not add an `evidence` array or duplicate the spec's prose here.
- `docs/specs/<feature-id>.appendix.md`: append what changed, what ran, and what failed to its `Feature evidence` section (the canonical verification store).

Do not create architecture or constraints docs just to look complete. Create them when they reduce future rediscovery or prevent future mistakes.

### Writing budget

Durable docs are reread by every later agent, so each added line has a recurring cost. Write each fact in exactly one owning file and link to it from elsewhere.

- `docs/constraints/<area>.md`: one bullet per new rule, as a MUST/MUST NOT sentence of at most three lines plus a link to the spec that established it. Put the rationale in the spec, not here. Add the rule under the existing section that fits; open a new section or area file only for a new area, and list it in the `CONSTRAINTS.md` index.
- `ARCHITECTURE.md`: change only the lines whose boundary moved; no per-feature history or file inventories.
- `backend/README.md` and `knowledge/README.md`: operator usage only (commands, flags, env vars, exit codes) for what an operator runs, at most about 30 added lines per feature. Design decisions, test lists, and limitations belong in the spec, its appendix, or `docs/progress/known-limitations.md`.
- `Feature evidence`: each command with its one-line result and any manual check in one or two lines; no pasted output, no restated scenarios.
- `docs/risks-and-open-questions.md` and `PROGRESS.md`: touch only when a risk, open item, or limitation actually changes.

## Self-Verification Rules

The implementer must verify its own work, but self-verification is not final acceptance.

Feature status convention:

- `in_progress`: implementation is underway or incomplete.
- `passing`: implementation is complete enough that required self-verification passed and evidence is recorded. This means ready for independent validation, not accepted.
- `accepted`: independent validation returned `accept` and the main orchestrator persisted that result. Implementers must not set this status.
- `blocked`: implementation cannot continue with the current spec/context.

Do not use `passing` to mean final approval. Final approval is a validator verdict persisted by the main orchestrator as `accepted` in `feature_list.json`, with the verification in the `Feature evidence` section of `../../../../docs/specs/<feature-id>.appendix.md`, the acceptance record `../../../../docs/validations/<feature-id>.md`, and one pointer line in `../../../../docs/progress/session-log.md`.

## `scripts/init.sh` Rule

Once a repository has a runnable baseline, `scripts/init.sh` must expose an executable non-blocking gate, not merely a help screen: at least one invocation must run the standard checks that can run without external long-lived services, fail fast on errors via `set -euo pipefail`, avoid starting blocking commands such as `pnpm dev`, and optionally print manual follow-up commands after checks pass.

Whatever invocation the docs present as the verification gate must actually run checks. For a Next.js baseline, a checks-running default is:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

A print-only invocation is acceptable only as the cheapest informational tier, and only when the script also exposes real checks-running tiers (for example a focused per-feature tier, a no-device tier, and the full gate). On a tiered harness the bare `./scripts/init.sh` may print the toolchain status and the available tiers and exit 0, as long as the checks are reachable through named tiers. A script that can *only* print the checks is allowed only during an explicitly pre-bootstrap phase.

Use the strongest applicable available checks:

1. static checks: formatting, lint, typecheck, build;
2. focused tests: unit/integration/regression;
3. runtime checks: app starts, endpoint responds, migration runs;
4. user-flow checks: browser/API/manual smoke or E2E when relevant.

Record exact commands and results. If a check is impossible in the current repo state, record the reason and the next action needed to make it possible.

When the repository has more than one check surface, expose tiers instead of one monolithic gate, and keep the cheapest tier runnable without platform SDKs or a device: a focused per-feature tier that runs the commands a feature spec publishes, a no-device tier covering the whole test-and-evaluator surface, and the full release-shaped gate. The full gate must still run every surface needed for release, including backend or offline checks that no narrower gate covers.

## Scope Rules

- One feature per implementation session.
- No opportunistic adjacent features.
- No false `passing` status.
- If the feature grows beyond the spec, stop and update the spec or ask for a split.
