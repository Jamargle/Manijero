# Ayudante Agrícola — Progress Log

## Current Verified State

- ✅ Discovery phase complete (build-brief workflow executed)
- ✅ CONTEXT.md created with 25+ canonical domain terms
- ✅ docs/build-brief.md created — problem, users, goals, non-goals, MVP slice
- ✅ docs/domain-model.md created — domain entities, relationships, lifecycle rules
- ✅ docs/risks-and-open-questions.md created — 16 risks registered, 15 open questions (P1-P15)
- ✅ AGENTS.md created — project landing page and operating rules
- ✅ init.sh created — provisional startup/verification path
- ⏳ Feature list to be created (harness-starter output)
- ⏳ Docker backend setup pending (technical bootstrap phase)
- ⏳ First feature implementation (profile selection screen)

## Session Log

| Date | Action | Evidence |
|------|--------|----------|
| 2026-10-05 | Build brief initiated | User described project: olive tree field manager app with AI chatbot |
| 2026-10-05 | Discovery documents created | CONTEXT.md, build-brief.md, domain-model.md, risks-and-open-questions.md |
| 2026-10-07 | Harness starter started | AGENTS.md, init.sh created; feature_list.json in progress |
| 2026-10-07 | Harness starter completed | Minimal repo harness created |

## Standard Startup and Verification Paths

**To start the app:**
```
./init.sh           # Confirm directory (this script)
docker compose up -d  # Start backend services
./gradlew :desktopApp:run  # Run desktop app
# or open in Android Studio and run androidApp
```

**To verify the work:**
```
./gradlew :shared:jvmTest     # Quality gates (CI blocking if thresholds not met)
./gradlew :shared:jvmTest     # Golden dataset validation
# Manual: use app, ask questions, verify citations and legal notice
```

## Pending Items

- Create feature_list.json with session-sized features
- Set up Docker Compose (backend, ChromaDB, etc.)
- Implement first feature: profile selection (2 toques)
- Begin technical bootstrap phase