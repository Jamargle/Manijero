# Manijero — Olive Grove Assistant

Manijero is a Kotlin Multiplatform app for people who own or manage one or more olive lands and want straightforward, source-backed help with agricultural questions. The MVP centers on an AI chat assistant and basic local management of multiple lands.

## MVP platforms

- **Android**
- **Desktop (JVM)**
- **iOS:** outside MVP delivery. Keep shared domain logic and reusable Compose UI suitable for a future iOS target; do not treat the existing iOS scaffold as an MVP release commitment.

The intended user has little experience with computers or apps. The interface and assistant should use plain Spanish, clear next steps, readable text, and source links. Land information is local by default; only the minimum context needed for a question should be sent to the answer service.

See [the build brief](docs/build-brief.md), [domain model](docs/domain-model.md), [risks and open questions](docs/risks-and-open-questions.md), and [design direction](DESIGN.md) before changing product behavior. [MasterPlanV3.md](MasterPlanV3.md) contains the broader technical and delivery plan; its prior schedule was retired pending a new estimate.

## Project structure

- [`shared/src/commonMain`](shared/src/commonMain/kotlin): shared Kotlin business logic and Compose UI for Android/Desktop and later iOS reuse.
- [`androidApp`](androidApp): Android application entry point.
- [`shared`](shared/src): shared Kotlin and Compose code. Current targets are defined in Gradle.
- [`desktopApp`](desktopApp): Desktop launcher.
- `iosApp`: existing project scaffold; not part of MVP build/release acceptance.

Implement product behavior and Compose UI in shared `commonMain`. Keep platform integrations and app entry points in platform-specific source sets so a later iOS target can reuse the same UI and business logic.

## Running the MVP targets

The shared Kotlin Multiplatform UI and behavior live in `shared/src/commonMain` and are rendered by both MVP targets.

Standard verification (shared host tests + Android debug APK + Desktop build):

```sh
./init.sh --verify
```

Build and run:

```sh
./init.sh --android    # builds androidApp/build/outputs/apk/debug/androidApp-debug.apk
./init.sh --desktop    # launches the Desktop app
```

The Desktop app keeps its lands in `~/.manijero/lands-v1.txt` (the shared `land-store-v1` format); remove that file to start from an empty list.

Known limitation: the backend has no `/ask` route yet, so a question in the shipped app ends in the plain-Spanish failure notice with a `Reintentar` button, not a grounded answer. iOS remains outside MVP delivery (see "MVP platforms").

## Product principles

- The assistant grounds legal or regulatory claims in approved official sources, cites them, and says when it cannot answer safely.
- Multiple lands are supported. Use all lands by default and ask the user to choose when the answer differs by land.
- Unknown land details stay unknown; stored details do not prove legal eligibility.
- Collect and transmit as little information as possible, and explain data handling in plain Spanish.

## Documentation

- [Build brief](docs/build-brief.md): users, goals, MVP slice, constraints, and validation.
- [Domain model](docs/domain-model.md): lands, questions, source-backed answers, and lifecycle rules.
- [Risks and open questions](docs/risks-and-open-questions.md): unresolved decisions and mitigations.
- [Design direction](DESIGN.md): visual and accessibility guidance for the MVP UI.
- [Project glossary](CONTEXT.md): stable terms and product constraints.
- [Master Plan v3](MasterPlanV3.md): RAG, knowledge operations, evaluation, and delivery notes.
