# Feature Spec: `chat_home`

## Goal

Replace the generated starter greeting with a calm, shared Compose starting screen where a Spanish-speaking user can immediately find a question composer without configuring a land.

## In scope

- Shared `commonMain` UI used by Android and Desktop.
- Plain-Spanish heading, explanation, question field, and prominent `Preguntar` action.
- Submit is enabled only for a non-blank question and preserves the entered wording.
- A visible route affordance for `Mis terrenos`, represented as a callback so navigation can be wired by a later feature.
- Empty and submitted composer state represented by a small pure presentation reducer and unit tests.
- Accessible labels, minimum Material touch targets, readable layout, and responsive width constraints.

## Out of scope

Backend calls, answer rendering, suggested questions, land storage, navigation destinations, and source citations.

## Acceptance criteria

1. `App()` renders the chat starting screen in shared code; no generated greeting remains.
2. With no lands configured, the question field and `Preguntar` action are visible without setup.
3. Blank or whitespace-only input cannot be submitted; typed text is retained on submit.
4. Android and Desktop compile from the shared UI.
5. User-facing strings are in Compose resources and controls have meaningful semantics.

## Verification

- `./gradlew :shared:jvmTest`
- `./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`
- Manual smoke: open Android/Desktop, locate the Spanish field without adding a land, type a question, and confirm the action becomes available.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/chat_home.md.
- Reproducible project wrapper restored from the project setup (Gradle 9.8.0); ./init.sh completes successfully.
- ./gradlew :shared:jvmTest passes; ./gradlew :desktopApp:build passes and compiles the shared Compose screen.
- ./init.sh --verify, ./gradlew :shared:testAndroidHostTest, and ./init.sh --android are blocked before compilation because this worktree has no ANDROID_HOME or local.properties sdk.dir.
- Self-verification passes for the implemented shared/Desktop scope; Android verification remains environment-blocked and is not claimed.
- Independent validator accepted commit 47e80c8 after confirming scope, accessibility labels, wrapper reproducibility, and all feasible checks. Record: docs/validations/chat_home.md.
