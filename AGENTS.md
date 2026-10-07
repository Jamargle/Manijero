# Agricultural Assistant — Project Overview

This is a Kotlin Multiplatform project targeting Android and Desktop (JVM).
The app provides a conversational AI assistant (RAG-based) that helps olive growers
in Jaén with agricultural bureaucracy, PAC regulations, and government aids.

## What is this project?

**Agricultural Assistant** is a mobile app (Android) and desktop app (JVM) for olive growers
that reduces dependence on specialists for understanding PAC, BOE, BOJA, and FEGA
regulations. The AI assistant answers questions exclusively from official documents,
saying "no lo sé" when information is not in the verified corpus.

**Key constraints:** Free tier only (≈0€), Gemini Flash LLM, bge-m3 local embeddings,
ChromaDB + BM25 vector store, Kotlin Multiplatform + Compose Multiplatform,
self-hosted backend + Docker Compose + Cloudflare Tunnel.

## How do I start the app?

1. Ensure Docker is running (backend, ChromaDB, Ollama optional)
2. Run `docker compose up -d` to start services
3. For Android: open the project in Android Studio and run `androidApp` variant
4. For Desktop: run `./gradlew :desktopApp:run`
5. The app will open with a profile selection screen (2 taps: rainfed/irrigated +
   conventional/organic)

## How do I verify the work?

- **Quality gates:** Run `./gradlew :shared:jvmTest` — CI will block PRs if metrics
  fall below thresholds (hit@5 ≥ 85%, 0 fabricated figures, fidelity ≥ 95%)
- **Golden dataset tests:** Run `./gradlew :shared:test` — validates against 40-60
  questions with verified sources
- **Manual test:** Use the app, ask questions about PAC deadlines, requirements,
  or subsidies. Verify answers include citations [1], [2], source, and verification date.
- **Check CONTEXT.md** for the glossary of canonical terms.
- **Check docs/build-brief.md** for the problem, goals, and MVP slice definition.

## Next Feature

The next focused agent session should implement: `Farmer can select profile
(2 taps: rainfed/irrigated + conventional/organic) on first run`.

This feature is tracked in `feature_list.json` with id `F1`.
