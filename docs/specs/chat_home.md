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
