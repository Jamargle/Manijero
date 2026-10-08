# Manijero — Progress

## Current state

- Product discovery is documented in `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, and `docs/risks-and-open-questions.md`.
- The repository contains a Kotlin Multiplatform client scaffold with Android, Desktop (JVM), and an iOS scaffold. The MVP targets Android and Desktop; iOS is out of scope.
- The next planned feature is F1: first-run selection of the grower's land type and production type.
- Backend, Docker Compose services, official-document ingestion, RAG answering, and golden-dataset quality gates are not present yet.
- No product feature is currently marked in progress.

## Start and verify

Run `./init.sh` to confirm the Gradle project root and print the available commands.

- Desktop: `./gradlew :desktopApp:run`
- Android build: `./gradlew :androidApp:assembleDebug`
- Shared JVM tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`

The Gradle test tasks are the checks currently available in the repository. Retrieval metrics and golden-dataset checks are planned; they are not implemented by these tasks yet.

## Session log

| Date | Change | Evidence |
|---|---|---|
| 2026-10-05 | Build brief initiated | User described project: olive tree field manager app with AI chatbot |
| 2026-10-05 | Discovery documents created | CONTEXT.md, build-brief.md, domain-model.md, risks-and-open-questions.md |
| 2026-10-07 | Harness starter started | AGENTS.md, init.sh created; feature_list.json in progress |
| 2026-10-07 | Harness starter completed | Minimal repo harness created |
| 2026-10-08 | Refreshed the startup harness and split MVP work into session-sized features. | Repository inspection; no tests run in this harness update. |
