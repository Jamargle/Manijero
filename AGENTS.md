# Manijero Agent Guide

Manijero is a Kotlin Multiplatform olive-grove assistant for people with little computer experience. The MVP centers on plain-Spanish, source-grounded chat and basic local management of multiple lands. Android and Desktop are MVP targets; keep business logic and Compose UI in `shared/src/commonMain` for later iOS reuse.

## Start and verify

- Read [CONTEXT.md](CONTEXT.md), [the build brief](docs/build-brief.md), [the domain model](docs/domain-model.md), and [the design direction](DESIGN.md) before product work.
- Read [risks and open questions](docs/risks-and-open-questions.md) and the relevant section of [MasterPlanV3.md](MasterPlanV3.md) for unresolved constraints and technical context.
- Run `./init.sh` to check the local toolchain and show standard commands. Run `./init.sh --verify` for the documented Android, Desktop, and shared test/build checks.
- Track user-visible work in [feature_list.json](feature_list.json); record verified progress in [PROGRESS.md](PROGRESS.md).

## Project skills

- Read the matching skill under `.agents/skills/` for Compose components, data, dependency injection, errors, module structure, navigation, MVI presentation or unit tests.
- These are opinionated patterns; adapt them to this repository's existing KMP modules and shared `commonMain` architecture. Do not add modules, frameworks, or dependencies solely because a skill example assumes them.

## Operating rules

- Do not invent legal facts. Ground regulatory claims in approved official sources, cite them, and abstain when evidence is inadequate.
- Use all active lands by default; ask the user to choose when an answer materially differs by land. Keep unknown attributes unknown; land records do not establish eligibility.
- Minimize land context sent to services and keep personal details out of logs.
- Keep Spanish UI copy plain, forgiving, and usable with large text, touch, keyboard, and screen readers.
- Keep product behavior and Compose UI in `commonMain`; keep platform integrations and entry points in platform source sets.
- Do not implement out-of-scope features such as iOS release, cloud sync, precise parcel mapping, document upload, or aid calculations without an explicit scope change.
