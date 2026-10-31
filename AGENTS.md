# Manijero Agent Guide

Manijero is a Kotlin Multiplatform olive-grove assistant for people with little computer experience. The MVP centers on plain-Spanish, source-grounded chat and basic local management of multiple lands. Android and Desktop are MVP targets; keep business logic and Compose UI in `shared/src/commonMain` for later iOS reuse.

## Route by task

Read the row that matches the work in front of you; a routine feature change needs `PROGRESS.md` "Current state" plus that feature's spec contract. Everything else is on demand, including that feature's appendix and the long-form history in `docs/progress/`.

| Work in front of you | Read | On demand |
|---|---|---|
| Every session | [PROGRESS.md](PROGRESS.md) "Current state" — status summary, open items, limitations digest; use the selector for exact feature status | [docs/progress/known-limitations.md](docs/progress/known-limitations.md) before claiming anything in a limited area; [docs/progress/current-state.md](docs/progress/current-state.md) and [docs/progress/session-log.md](docs/progress/session-log.md): on demand, not for routine work |
| Plan, implement, or validate one feature | the spec contract [docs/specs/](docs/specs/)/`<feature-id>.md` and its acceptance record [docs/validations/](docs/validations/)/`<feature-id>.md` | the feature's appendix [docs/specs/](docs/specs/)/`<feature-id>.appendix.md`, or [docs/archive/specs/](docs/archive/specs/) once accepted (repository research, implementation plan, validator checklist, feature evidence) and [feature_list.json](feature_list.json) for status and dependencies |
| User-facing UI or Spanish copy | [DESIGN.md](DESIGN.md) | the spec of the feature that owns the surface |
| A domain term, product-scope, or audience question | [CONTEXT.md](CONTEXT.md) — glossary, users and scope | [docs/domain-model.md](docs/domain-model.md) for concepts; [docs/archive/build-brief.md](docs/archive/build-brief.md) is the historical discovery baseline |
| An architecture, module, dependency, or contract boundary | [ARCHITECTURE.md](ARCHITECTURE.md) — the current map | a matching [docs/archive/MasterPlanV3.md](docs/archive/MasterPlanV3.md) section is historical, not current |
| Backend, `contracts/`, or `knowledge/` work | [ARCHITECTURE.md](ARCHITECTURE.md) plus the artifact's schema or `contracts/openapi.yaml` | `backend/README.md`, [knowledge/README.md](knowledge/README.md) |
| A rule the change must not break | [CONSTRAINTS.md](CONSTRAINTS.md) — the index; then only the [docs/constraints/](docs/constraints/) area files the change touches | the reason line in the spec that established the rule |
| An unresolved constraint, risk, or honest limit | [docs/risks-and-open-questions.md](docs/risks-and-open-questions.md) | the matching open item in [PROGRESS.md](PROGRESS.md) |
| Any Kotlin, Compose, data, DI, navigation, or test code | the matching skill under [.agents/skills/](.agents/skills/) | — |

## Start and verify

Use `./scripts/select-feature.sh --next` to pick the next feature and role, or `--status` for the board; do not re-derive selection from `feature_list.json`. See [PROGRESS.md](PROGRESS.md) "Start and verify" for the cheapest-first verification tiers. The bare `./scripts/init.sh` only checks the toolchain and prints the commands.

## Keep context lean

Every line read or written is paid for again by each later agent. Read the smallest unit that answers the question, and write each fact once.

- Large files (`DESIGN.md`, `backend/README.md`, `knowledge/README.md`, `docs/archive/MasterPlanV3.md`, any appendix): list headings with `grep -n '^#' <file>` and read only the matching sections. Never read a whole `docs/specs/` or `docs/validations/` directory; open only the selected feature's files.
- Verification: `./scripts/init.sh` prints one line per passing check and only the tail of a failing log; full logs stay in `build/verify-logs/`. Read a log only when a check fails, and grep it rather than dumping it. Do not rerun a tier whose inputs have not changed since it last passed.
- Writing: follow the size budgets in `feature-spec` and `feature-implementer`. Record commands and one-line results, never pasted output; link the owning file instead of restating it.

## Track the work

- [feature_list.json](feature_list.json) is a lean index of `id`, `area`, `title`, `status`, `depends_on`, `spec`, and `validation`. The feature's user-visible behavior, verification, and notes live in the "Source metadata" section of [docs/specs/](docs/specs/)/`<feature-id>.md`; the planning and verification record (repository research, implementation plan, validator checklist, and the raw "Feature evidence") lives in the feature's appendix [docs/specs/](docs/specs/)/`<feature-id>.appendix.md`, and its acceptance record lives in [docs/validations/](docs/validations/)/`<feature-id>.md`.
- [docs/archive/](docs/archive/) holds historical records that no routine work needs: the original plans and accepted features' appendices. Read them only to trace why a past decision was made. When an accepted feature is reopened, `git mv` its appendix back to `docs/specs/` first.
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
