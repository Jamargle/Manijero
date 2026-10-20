# Appendix — `platform_ask_wiring`

Planning and verification record for [`platform_ask_wiring.md`](platform_ask_wiring.md). The acceptance record, when created, is `docs/validations/platform_ask_wiring.md`.

## Repository research

Inspected:

- `PROGRESS.md`: backend `/ask` exists, but default app service remains unavailable because platform URL/engine wiring is open; Android evidence has previously been emulator-only and Desktop local.
- `ARCHITECTURE.md`: shared owns `KtorAnswerService`; engine and URL configuration belong in platform composition roots. Current text explicitly says wiring remains open.
- `feature_list.json`: this feature depends on accepted chat submission, backend endpoint, and campaign-validity features; F1 is its stated scope.
- `shared/src/commonMain/.../chat/AnswerService.kt`: contract DTOs, `KtorAnswerService`, `answerHttpClient(HttpClientEngine)`, bounded timeouts, payload-free failures, and `UnavailableAnswerService` already exist.
- `shared/src/commonMain/.../App.kt`: `App` accepts an `AnswerService` defaulting to unavailable; app composition is injectable.
- `androidApp/.../MainActivity.kt`: currently creates `LandRepository` and calls `App(landRepository)`; no answer service/engine supplied.
- `desktopApp/.../main.kt`: similarly injects only the local land repository from its application/window root.
- `shared/src/androidMain/.../Platform.android.kt` and `shared/src/jvmMain/.../Platform.jvm.kt`: existing platform source sets provide suitable places for platform-specific helpers, but contain no HTTP setup.
- `shared/src/jvmTest/.../chat/KtorAnswerServiceTest.kt`: MockEngine tests already cover POST `/ask`, response parsing and service errors.
- `scripts/init.sh`: feature mode executes the contract's marked shell commands; no UI/E2E runner. Android/Desktop builds are available.
- `docs/specs/chat_question_submission.md` and appendix: established service injection pattern; prior validator recorded missing engine/endpoint wiring and lack of live service smoke as F1.

Not inspected during planning: detailed Gradle catalog and Android manifest/network security configuration. Implementer must inspect these before choosing Ktor engine artifacts or cleartext policy. Backend port/bind command should be confirmed from `backend/README.md` when running manual smoke; do not assume a physical device can reach loopback.

## Implementation plan and tasks

1. Inspect engine dependencies, manifests, Ktor versions, backend run instructions and backend bind address. Choose the compatible Android/JVM engines and exact local port from repository configuration.
2. Define explicit endpoint defaults: Desktop loopback; Android emulator host bridge. Add a documented override suitable for local alternative ports/physical-device host addresses without introducing production URL or credentials. Keep URL normalization/trailing slash handling delegated to `KtorAnswerService`.
3. Add platform engine/client/service factory wiring at host composition roots. Ensure client lifecycle is bounded to app lifetime and preserve `LandRepository` and preview defaults.
4. Configure Android Internet permission and only the cleartext policy required for development HTTP. Do not add broad production claims; record limitations in durable architecture documentation.
5. Add focused tests for endpoint selection and override precedence. Do not duplicate contract DTO tests; existing MockEngine verifies payload and `/ask` decoding.
6. Update `ARCHITECTURE.md` after implementation details are known. Avoid changing backend, contract, shared answer semantics, or feature status as part of planning.
7. Run focused tests/builds, then start the backend with explicit `MANIJERO_ACTIVE_CAMPAIGN` and manually submit a supported and an unsupported question on Desktop and Android emulator. Check stopped-backend behavior too. Record actual environment and outcomes; do not claim live response without observing it.

## Verification plan

Automated focused tier (published in contract): `:shared:jvmTest` for existing transport/conversation tests, then Desktop build and Android debug assemble. Add any new platform-configuration tests to the first command's test selection or use the full shared JVM test suite if selection becomes brittle. Run `./scripts/init.sh --verify` as a broader gate when available.

Manual integration is required because there is no persistent UI/E2E harness. Start backend per its README, provide the required campaign environment, ensure its bind address is reachable, then:

1. Launch Desktop; submit a supported query and verify a backend-derived answer/source state appears once.
2. Launch Android emulator; verify host bridge URL reaches the same local service and response appears.
3. Stop backend and submit again; ensure existing retry/error UI appears within bounded timeout, without raw payload in logs.
4. If physical-device override is offered, test only when an explicitly reachable host is available; otherwise record as unverified, not as a failure of emulator support.

## Evidence to capture

- Test and build command output, including environment blockers.
- Endpoint defaults and override mechanism, with confirmation that no production URL is hard-coded.
- Android permission/cleartext configuration review and why its scope is appropriate.
- Desktop and emulator manual smoke records identifying backend configuration and outcome for success and stopped-service cases.
- Confirmation that response is generated by backend rather than a preview/fake, and that logs contain no question or land payload.
- Updated `ARCHITECTURE.md` wording.

## Feature evidence

- Android and Desktop composition roots now create engine instances in platform code and pass them to shared `answerHttpClient(engine)`, which configures JSON content negotiation, bounded timeouts, and `expectSuccess`. Android URL selection uses the Gradle property `manijeroAskBaseUrl` or emulator default `http://10.0.2.2:8000`; Desktop uses JVM property, then `MANIJERO_ASK_BASE_URL`, then `http://127.0.0.1:8000`. Pure selection tests cover defaults, primary override precedence, and blank-primary fallback. No production URL is embedded.
- Android debug-only cleartext allowance and INTERNET permission are present; duplicate Android `buildTypes` blocks were merged. Android client closes in `onDestroy`; Desktop client closes when its window closes. `ARCHITECTURE.md` documents platform wiring.
- `./scripts/init.sh --feature platform_ask_wiring` — passed after the wiring repair with `KtorAnswerServiceTest`, `ChatConversationTest`, `AskEndpointTest`, Desktop build, and Android debug assemble.
- `./scripts/init.sh --verify` — passed on 2026-10-20. Fast tier: shared JVM tests, contract examples, source-catalog validation, and all five offline evaluator checks passed; backend pytest was skipped because pytest is not installed. Full tier: `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build` passed.
- Desktop live success (2026-10-20): with `MANIJERO_ACTIVE_CAMPAIGN=2026` on `127.0.0.1:8000`, `:desktopApp:run` launched, selecting the suggested question and pressing `Preguntar` rendered the backend answer (including the 15 May 2026 deadline) and its source card. The backend logged the matching `POST /ask` 200. The rendered transcript was read from the Desktop accessibility tree, not inferred from the request.
- Android live success (2026-10-20): the debug APK was installed and launched on `Pixel_4a_API_34` (`1080x2340`). Selecting the same suggested question and pressing `Preguntar` rendered the same backend answer and source card; the backend logged a matching `POST /ask` 200. This confirms the emulator host bridge reached the host loopback backend over the debug cleartext policy.
- Stopped-backend behavior (2026-10-20): after stopping the backend, a fresh Desktop submission rendered “No se ha podido conectar con el servicio…” with the `Reintentar` control, and the Android emulator rendered the same failure notice and `Reintentar`. No raw error body was rendered as an answer, and no unbounded wait was observed.
- Payload-free logging: captured Desktop output showed only SLF4J provider warnings; Android logcat contained no app-emitted question, land, or response payload. The only question text found in logcat came from the external `uiautomator dump` inspection itself.
- Status is `passing` after live verification on both platforms; independent validator review is pending.

## Validator checklist

- [ ] Android and Desktop launched applications pass a configured `KtorAnswerService` rather than `UnavailableAnswerService`.
- [ ] Desktop default targets local host; Android emulator default targets host-machine bridge, not device loopback; overrides are explicit and testable.
- [ ] Both platform engine dependencies are compatible with existing Ktor versions and clients have app-bounded lifecycle.
- [ ] Internet permission exists; development cleartext configuration, if needed, is narrowly scoped/documented.
- [ ] Shared contract request, minimal land context, response rendering, bounded timeouts, and payload-free failure behavior are unchanged.
- [ ] Tests/builds pass; manual live backend smoke has been run on both required targets, or limitations are honestly documented.
- [ ] No backend/contract/UI redesign or out-of-scope iOS work was introduced.
- [ ] `ARCHITECTURE.md` reflects the implemented wiring and local endpoint distinction.
