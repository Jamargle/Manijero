# Feature Spec: `platform_ask_wiring`

## Source metadata

- **Feature:** `platform_ask_wiring` — Connect Android and Desktop to the local `/ask` service
- **Status at planning:** `not_started`
- **Depends on:** `chat_question_submission`, `backend_ask_endpoint`, `backend_campaign_validity` (all accepted)
- **Source behavior:** Android and Desktop configure a platform HTTP engine and reachable development base URL for the already implemented shared `KtorAnswerService`, replacing the unavailable default in launched apps.
- **Source verification:** Run the local backend and submit a question from each platform; both must reach `POST /ask` and render the service result. Also verify focused tests/builds.
- **Note from the feature list:** Close F1 carried from `chat_question_submission`; endpoint/base URL wiring is still open.

## Goal

Make the existing shared chat use the local backend on Android and Desktop with platform-appropriate engine construction and explicit, configurable development URLs. Preserve the established answer, land-context, timeout, and failure behavior. Android emulator and Desktop localhost must both be usable without changing shared UI/business logic.

## Non-goals

- Backend changes, deployment/hosting, production endpoint selection, or adding a hosted provider.
- iOS engine/endpoint wiring.
- Changing `/ask` contract, campaign configuration, answer behavior, land context construction, response presentation, or retries.
- Automatic backend startup, service discovery, or promising that an Android physical device can reach its host's loopback address.
- New analytics, logging, persistence, or user-facing endpoint configuration UI.

## Job story

When I run Manijero on Android emulator or Desktop beside the local backend, I want my question to reach that backend and its real response to appear, so I can use the integrated flow rather than the unavailable-service fallback.

## Acceptance scenarios

### Desktop reaches local backend

Given the backend is running on the development machine with `MANIJERO_ACTIVE_CAMPAIGN` configured, when I launch Desktop and submit a supported or safely unsupported question, then a platform-created HTTP engine sends the existing contract-shaped `POST /ask` to the configured local base URL and the corresponding answer or abstention is rendered by the existing shared flow.

### Android emulator reaches host backend

Given the backend is running on the development host with campaign configuration, when I launch the Android app in an emulator and submit a question, then the app uses the emulator-reachable host address (not Android's own loopback) and renders the backend response. Cleartext access, if the development server uses HTTP, is enabled only as narrowly as the app's development policy allows and is not described as secure production transport.

### Backend/service failure remains honest

Given the backend is stopped, unreachable, or returns a non-success response, when I submit a question, then the existing bounded timeout and payload-free error/retry state is shown; no error body is displayed as an answer and no question/land data is logged.

### Configuration is explicit

Given the app is started, when its endpoint is selected, then Desktop uses a configurable development base URL defaulting to `http://127.0.0.1:<backend-port>` and Android emulator uses the corresponding host bridge address (commonly `10.0.2.2`); the endpoint choice is documented and injectable/overridable for tests and alternate local setups. No production URL is hard-coded or implied. Physical-device access requires an explicit reachable host override.

## Technical approach

1. Keep `KtorAnswerService`, HTTP serialization, timeout policy, and `AnswerService` interface in shared code. Construct a platform engine in platform source sets and inject the service into `App` from each host composition root; do not create clients in Composables.
2. Use the Ktor engine already supported by dependency versions (expected Android engine and JVM/Desktop engine); inspect catalog/build configuration before adding anything. Own client lifetime at app composition root and close/dispose it when the host exits where supported.
3. Centralize endpoint selection in small platform configuration/factory functions with an explicit default and override path. Desktop loopback and Android emulator host bridge are distinct; do not share a literal `localhost` default across both. Keep override mechanism non-secret and suitable for local development (build config/environment/system property as appropriate to existing build setup).
4. Ensure Android manifest declares Internet permission. If HTTP cleartext is required, enable it narrowly for development rather than broadly claiming production suitability. Backend binds must be reachable from emulator; document any run command/config needed without making app startup launch the service.
5. Preserve existing `LandRepository` injection while passing the configured `AnswerService`; previews/tests may continue to use `UnavailableAnswerService` or injected fakes.
6. Add tests for URL selection/override and service construction where practical. The existing MockEngine tests continue to establish exact `/ask` wire contract; no persistent UI E2E runner exists, so verify live flow manually on Android emulator and Desktop.

## Expected file changes

- **Update** `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt` to create platform engine/client/service and inject into shared `App`.
- **Update** `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt` similarly, retaining local land repository.
- **Create/update** platform configuration/factory code under `shared/src/androidMain` and `shared/src/jvmMain`, or host source sets, for engines and endpoint defaults/overrides.
- **Update** Android manifest/build configuration only as needed for Internet permission and narrowly scoped development HTTP policy.
- **Update** `shared/build.gradle.kts`, `androidApp/build.gradle.kts`, `desktopApp/build.gradle.kts`, and `gradle/libs.versions.toml` only if required engine artifacts/configuration are absent.
- **Add/update** focused platform config tests and any common tests; retain `KtorAnswerServiceTest`.
- **Update** `ARCHITECTURE.md` because platform composition roots now provide concrete engines and local endpoint configuration. `CONSTRAINTS.md`: **not needed**; existing rules suffice. `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, contract/backend: **not needed**.

## Visual and accessibility impact

No intended UI redesign or new copy. Existing working, answered/abstained, and failure/retry states must remain unchanged and accessible. Manual smoke checks must confirm real responses appear in the existing transcript and connection failure remains understandable.

## Durable documentation impact

- `ARCHITECTURE.md`: **update** the answer-service paragraph to document concrete Android/Desktop engines and development endpoint selection, including the Android emulator host bridge distinction; keep iOS/out-of-scope status explicit.
- `CONSTRAINTS.md`: **not needed**; no durable rule changes.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, contracts, backend docs: **not needed**; existing scope and wire contract remain authoritative.
- `feature_list.json` and `PROGRESS.md`: **defer until implementation verification**; planner does not change status.

## Focused verification

The following block is the exact focused harness invocation: it runs shared tests including the existing MockEngine contract tests, then builds both consuming applications.

<!-- verify:start -->
```sh
./gradlew :shared:jvmTest --tests KtorAnswerServiceTest --tests ChatConversationTest --tests AskEndpointTest
./gradlew :desktopApp:build :androidApp:assembleDebug
```
<!-- verify:end -->

## Appendix

Research, ordered tasks, verification details, evidence requirements, and validator checklist are in [`platform_ask_wiring.appendix.md`](../archive/specs/platform_ask_wiring.appendix.md).
