# Project Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, and `DESIGN.md`.
- The repository contains the Kotlin Multiplatform starter scaffold: `shared`, `androidApp`, `desktopApp`, and an existing iOS target. Shared Compose UI is in `commonMain`; the iOS target is not an MVP deliverable.
- `shared/src/commonMain/.../App.kt` is still the generated click-to-reveal greeting sample. Chat, land management, backend, and official-source retrieval are not implemented.
- The existing shared tests are template examples and do not verify product behavior.
- Product features are tracked in `feature_list.json`. No product feature is currently in progress.

## Start and verify

- Startup/toolchain check: `./init.sh`
- Standard verification: `./init.sh --verify`
- Android build: `./init.sh --android`
- Launch Desktop: `./init.sh --desktop`

These are the documented paths; they have not been run as part of this harness update.

## Next feature

Preferred next feature: `chat_home` — build the accessible, plain-Spanish starting screen and question composer in shared Compose UI. Keep it usable for general questions when the user has not added any lands.

## Session log

### 2026-10-09 · Product discovery and harness

- Recorded the MVP direction: chat first, basic local management of multiple lands, all-land context by default, and land clarification when answers differ.
- Added the initial harness. No product implementation or builds were performed in this session.
- Installed nine project skills under `.agents/skills/`, added routing guidance to `AGENTS.md`.
