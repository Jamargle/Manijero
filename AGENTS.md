# Manijero Agent Guide

Manijero is a Kotlin Multiplatform olive-grove assistant for people with little computer experience. The MVP centers on plain-Spanish, source-grounded chat and basic local management of multiple lands. Android and Desktop are MVP targets; keep business logic and Compose UI in `shared/src/commonMain` for later iOS reuse.

## Route by task

Read the row that matches the work in front of you; a routine feature change needs `PROGRESS.md` "Current state" plus that feature's spec. Everything else is on demand, including the long-form history in `docs/progress/`.

| Work in front of you | Read | On demand |
|---|---|---|
| Every session | [PROGRESS.md](PROGRESS.md) "Current state" — accepted set, open items, honesty limits | [docs/progress/current-state.md](docs/progress/current-state.md) for the long-form narrative and [docs/progress/session-log.md](docs/progress/session-log.md) for the chronological pointer index: on demand, not for routine work |
| Plan, implement, or validate one feature | its spec [docs/specs/](docs/specs/)/`<feature-id>.md` and its acceptance record [docs/validations/](docs/validations/)/`<feature-id>.md` | [feature_list.json](feature_list.json) for status and dependencies |
| User-facing UI or Spanish copy | [DESIGN.md](DESIGN.md) | the spec of the feature that owns the surface |
| A domain term, product-scope, or audience question | [CONTEXT.md](CONTEXT.md) — glossary, users, scope markers | [docs/build-brief.md](docs/build-brief.md), [docs/domain-model.md](docs/domain-model.md) |
| An architecture, module, dependency, or contract boundary | [ARCHITECTURE.md](ARCHITECTURE.md) — the current map | a matching [MasterPlanV3.md](MasterPlanV3.md) section is historical, not current |
| Backend, `contracts/`, or `knowledge/` work | [ARCHITECTURE.md](ARCHITECTURE.md) plus the artifact's schema or `contracts/openapi.yaml` | `backend/README.md`, [knowledge/README.md](knowledge/README.md) |
| A rule the change must not break | [CONSTRAINTS.md](CONSTRAINTS.md) — durable MUST/MUST NOT rules | the reason line in the spec that established the rule |
| An unresolved constraint, risk, or honest limit | [docs/risks-and-open-questions.md](docs/risks-and-open-questions.md) | the matching open item in [PROGRESS.md](PROGRESS.md) |
| Any Kotlin, Compose, data, DI, navigation, or test code | the matching skill under [.agents/skills/](.agents/skills/) | — |

## Start and verify

Verify in the smallest tier that covers the change, cheapest first: `./init.sh --feature <feature-id>` runs the focused command block the feature spec publishes, `./init.sh --fast` runs the shared host tests, the contract examples, the backend tests, and the offline evaluators without any Android SDK or Desktop build, and `./init.sh --verify` is the full gate. `./init.sh` alone only checks the toolchain and prints those commands.

## Track the work

- [feature_list.json](feature_list.json) is a lean index of status, dependencies, and verification. Feature detail lives in [docs/specs/](docs/specs/)/`<feature-id>.md` (section "Feature evidence") and its acceptance record in [docs/validations/](docs/validations/)/`<feature-id>.md`.
- Record verified progress in [PROGRESS.md](PROGRESS.md) — the status board — and add one line per accepted feature to [docs/progress/session-log.md](docs/progress/session-log.md), which is a pointer index: link the spec and the acceptance record, never restate the verification.

## Project skills

- The skills under [.agents/skills/](.agents/skills/) are opinionated patterns; adapt them to this repository's existing KMP modules and shared `commonMain` architecture. Do not add modules, frameworks, or dependencies solely because a skill example assumes them.

## Operating rules

- Do not invent legal facts. Ground regulatory claims in approved official sources, cite them, and abstain when evidence is inadequate.
- Use all active lands by default; ask the user to choose when an answer materially differs by land. Keep unknown attributes unknown; land records do not establish eligibility.
- Minimize land context sent to services and keep personal details out of logs.
- Keep Spanish UI copy plain, forgiving, and usable with large text, touch, keyboard, and screen readers.
- Keep product behavior and Compose UI in `commonMain`; keep platform integrations and entry points in platform source sets.
- Do not implement out-of-scope features such as iOS release, cloud sync, precise parcel mapping, document upload, or aid calculations without an explicit scope change.
