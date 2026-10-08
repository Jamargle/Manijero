# Manijero — Agricultural Assistant

Kotlin Multiplatform app for Jaén olive growers to understand PAC rules and aid using answers grounded only in official sources. MVP targets are Android and Desktop (JVM); an iOS scaffold is present but out of scope.

## Start and verify

- Desktop: `./gradlew :desktopApp:run`
- Android build: `./gradlew :androidApp:assembleDebug`; run on a device or emulator from Android Studio.
- Shared JVM tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`

## Project guidance

- Read [CONTEXT.md](CONTEXT.md) for canonical domain terms and answer-safety rules.
- Read [docs/build-brief.md](docs/build-brief.md) for MVP goals and scope, and [docs/domain-model.md](docs/domain-model.md) for domain behavior.
- Check [feature_list.json](feature_list.json) and [PROGRESS.md](PROGRESS.md) before choosing work. The next feature is F1: first-run profile selection.
- Keep answers grounded in verified BOE, BOJA, and FEGA documents. Never invent legal dates, amounts, thresholds, requirements, or citations; abstain when the corpus does not support an answer.
- Keep user-facing text in plain Spanish. Do not add accounts or collect personal data in the MVP.
