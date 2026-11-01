# Feature Spec: `local_service_connection`

## Source metadata

- `id`: `local_service_connection` · `area`: client · `depends_on`: `platform_ask_wiring`, `backend_health` (both accepted) · `status` at planning: `not_started`
- User-visible behavior: Android and Desktop test builds offer a `Conexión` screen where a tester types the answer-service address, presses `Comprobar`, and reads a plain-Spanish result from `GET /health` and `GET /ready`. The address is remembered on the device and used for the next questions. Release builds never show the screen.
- Verification: focused shared, platform-store, and release-gating guard tests, plus debug and release compiles of both hosts. Live checks against the local service are manual. The commands are in Focused verification.
- Notes: owner decisions recorded 2026-11-01. The screen exists only in Android and Desktop test/debug builds, never in release builds. Shared UI and logic live in `commonMain`; entry points, storage, and debug-versus-release gating live in platform source sets. The defaults stay the `platform_ask_wiring` development URLs. Any owner-run command follows [`docs/constraints/operations.md`](../constraints/operations.md); this feature adds none.

## Goal

A tester or the owner can point an Android or Desktop test build at any answer service, such as the emulator host, a LAN computer, or later the QA host. They can check from inside the app whether the service is reachable and ready, without rebuilding the app or using a terminal. Release builds behave exactly as they do today.

## Non-goals

- Release-build or end-user endpoint configuration, or any production URL.
- Sending a pilot bearer token (`client_pilot_credentials`), or environment-specific builds (`client_environment_builds`).
- Backend, `contracts/`, or bind-address changes. Service start/stop, or a status command.
- Service discovery, QR codes, scanning the LAN, or automatic retries and polling.
- A developer/RAG inspector view (`rag_inspector_view`), or a generic debug menu beyond this one screen.
- iOS gating or entry points (the iOS scaffold injects nothing, so it shows nothing).

## Job story

When I run a test build on an emulator, a phone, or a computer next to the answer service, I want to type the service address and check it in plain words, so I know whether questions will reach a ready service before I start testing.

## Acceptance scenarios

### 1. Test builds show the entry; release builds do not

Given an Android debug build, or Desktop launched with `./scripts/init.sh --desktop` (`:desktopApp:run`) · When I open `Ayuda` · Then a `Herramientas de prueba` card ends the screen. It reads `Solo aparece en las versiones de prueba.` and has a `Conexión` button that opens the `Conexión` detail route.
Given an Android release build, a packaged Desktop app (`createDistributable`, `runDistributable`, `package*`), `runRelease`, previews, or iOS · When I open `Ayuda` · Then no card, button, or route exists, and the existing `Ayuda` baselines are unchanged.

### 2. The screen shows the address in use

Given no saved address · When `Conexión` opens · Then the field holds the build's current address, which is the `platform_ask_wiring` default or its existing Gradle property or env/system-property override. Below the field it reads `Dirección en uso: <url> (la predeterminada de esta versión)`.
Given a saved address · Then the field holds it, and the line reads `(guardada en este dispositivo)`.

### 3. Comprobar against a ready service

Given the local service runs with `MANIJERO_ACTIVE_CAMPAIGN` set · When I enter its address and press `Comprobar` · Then the address is saved and applied, `Comprobando la conexión…` shows while the check runs, and the result is a confirmation callout: `Conectado. El servicio responde y está listo para contestar preguntas.`
And the next question in `Asistente` goes to `<address>/ask` without restarting the app.

### 4. Not-ready, unreachable, and wrong-service results

Each case below shows its own callout. Each callout has an icon and text, never colour alone. Raw bodies, status codes, and exception text are never shown.

| Condition | Message |
|---|---|
| `/health` OK and `/ready` 503 `unavailable` | `El servicio responde, pero todavía no está listo para contestar preguntas. Revisa su configuración y vuelve a comprobarlo.` |
| `/health` OK, `/ready` fails, times out, or returns an unexpected body | `El servicio responde, pero no se pudo saber si está listo. Vuelve a comprobarlo.` |
| `/health` refused, timed out, or another I/O failure | `No se puede conectar con el servicio. Comprueba que está encendido, que la dirección es correcta y que este dispositivo está en la misma red.` |
| `/health` non-2xx, or body other than `status: ok, service: manijero-backend` | `Algo responde en esa dirección, pero no es el servicio de respuestas de Manijero. Revisa la dirección y el puerto.` |

### 5. Invalid address is refused and nothing changes

Given the field holds one of these inputs:

- blank text,
- text longer than 512 characters,
- a scheme other than `http` or `https`,
- no host, or a port outside 1–65535,
- user info (`user:pass@`), a query, or a fragment.

When I press `Comprobar` · Then the screen shows `Esa dirección no es válida. Escríbela completa, por ejemplo: http://192.168.1.20:8000`, makes no request, and leaves the saved address unchanged. Before validation, surrounding spaces and trailing `/` are removed. A path prefix is allowed.

### 6. The address survives a restart; reset restores the default

Given I saved an address · When I close and reopen the test build · Then `Conexión` and the chat use the saved address.
When I press `Usar la dirección predeterminada` · Then the saved address is deleted and the line reads `(la predeterminada de esta versión)`. The screen confirms `Se usará la dirección predeterminada: <url>`, and the next question uses that default.

### 7. Storage failure is honest

Given the device store refuses a write · When I press `Comprobar` or reset · Then the screen shows `No se pudo guardar la dirección en este dispositivo. Inténtalo de nuevo.` No check runs, and the address in use is unchanged.

### 8. Interaction limits and privacy

- While a check runs, `Comprobar` and reset are disabled.
- Leaving the screen cancels the check.
- `Volver` and Android system back return to `Ayuda`, and the bars stay visible.
- The two probe requests carry no question, land data, token, or body.
- Nothing logs the address or the probe results.

## Technical approach

- **Address model (commonMain `connection/`):** a pure `normalizeServiceAddress(input)` returns either a normalized URL or `Invalid`, using the scenario 5 rules. A `ServiceAddressStore` interface has `load(): String?`, `save(String)`, and `clear()`, and its failures throw. `ActiveServiceAddress(defaultUrl, store)` resolves the address in this order:
  1. the saved and still-valid address,
  2. the build default from `selectAskBaseUrl`.

  It holds the current value in memory after each save or clear. An unreadable or invalid stored value falls back to the default.
- **Answer transport:** `KtorAnswerService` gains a `baseUrl: () -> String` constructor and reads it on each `ask`. The existing `String` constructor delegates to it, so release wiring and all existing tests are unchanged.
- **Probe:** `KtorServiceStatusChecker(client)` reuses the host's `answerHttpClient` and its existing timeouts. It sends `GET <url>/health`, and only after a valid health body it sends `GET <url>/ready`. Every Ktor failure maps to the fixed outcomes `Ready`, `NotReady`, `ReadyUnknown`, `Unreachable`, and `NotManijero`. JSON decoding ignores unknown keys. A `CancellationException` is rethrown.
- **Presentation:** a `ConnectionState` and an action reducer, plus a `ConnectionController` that owns the coroutine. They follow the `LandBackupController` pattern. `ConnectionScreen` uses `ManijeroScreen`, one `heading()`, an `OutlinedTextField` with a label and the example as supporting text, a filled `Comprobar`, a text-button reset, `ManijeroCallout` for results (Info for checking, Confirmation for ready, Caution for not-ready or unknown, Danger for the rest), and `Volver`. All copy comes from `Res.string` under a `connection_` prefix.
- **Injection:** `App(..., connectionTools: ConnectionTools? = null)`. When it is null, the route and the `Ayuda` card do not exist. `CoverageScreen` gains an optional `onOpenTestTools: (() -> Unit)?`. Navigation adds `AppDestination.Connection`:
  - its tab is `Help`,
  - `backTarget` is `Coverage`,
  - navigation stays visible.
- **Android gating:** add the same function `testBuildConnectionTools(context, defaultUrl, client): ConnectionTools?` in two variant source sets:
  - `androidApp/src/debug/kotlin/…` builds the tools with `AndroidServiceAddressStore`.
  - `androidApp/src/release/kotlin/…` returns `null` and imports nothing from `connection`.

  `MainActivity` calls the function once. It passes `tools.address::current` as the base URL when tools exist, and the existing fixed URL otherwise.
- **Desktop gating:** `desktopApp/build.gradle.kts` sets the system property `manijero.testBuild=true` only on the Compose `run` JavaExec task, configured lazily by name. No `application.jvmArgs`, `nativeDistributions`, or `runRelease` setting carries it. `main.kt` builds the tools only when the shared jvmMain function `desktopTestBuildEnabled(System.getProperty(...))` returns true. Otherwise it keeps today's wiring.
- **Storage:**
  - Android: `AndroidServiceAddressStore` in shared `androidMain` uses its own private preferences file, `manijero_connection`, in a separate source file. This keeps the land-store backup guard regex unaffected.
  - Desktop: `FileServiceAddressStore` in shared `jvmMain` writes `~/.manijero/connection-v1.txt` as one UTF-8 line, with a temporary file and an atomic move.
  - Release builds never construct either store, so a saved address is never read there.
- **Boundaries:** follow [ARCHITECTURE.md](../../ARCHITECTURE.md) "Answer service boundary". The [ui-shell constraints](../constraints/ui-shell.md) cover the shell, insets, back navigation, and component layer. The probe needs no `contracts/` change because `/health` and `/ready` are operational probes. The client reads only `status` and `service`.

## Expected file changes

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/connection/`: create `ServiceAddress.kt`, `ServiceStatusChecker.kt`, `ConnectionState.kt`, `ConnectionController.kt`, `ConnectionTools.kt`, and `ConnectionScreen.kt` (with previews per state).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: modify. Add the provider-based base URL.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`, `AppNavigation.kt`, and `coverage/CoverageScreen.kt`: modify. Add the optional tools, route, and card.
- `shared/src/commonMain/composeResources/values/strings.xml`: modify. Add the `connection_*` copy above.
- `shared/src/androidMain/kotlin/com/jamarglex/manijero/connection/AndroidServiceAddressStore.kt`: create.
- `shared/src/jvmMain/kotlin/com/jamarglex/manijero/connection/FileServiceAddressStore.kt` and `DesktopTestBuild.kt`: create.
- `androidApp/src/debug/kotlin/com/jamarglex/manijero/TestBuildTools.kt` and `androidApp/src/release/kotlin/com/jamarglex/manijero/TestBuildTools.kt`: create.
- `androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt`, `desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt`, and `desktopApp/build.gradle.kts`: modify.
- Tests:
  - commonTest `connection/ServiceAddressTest`, `ActiveServiceAddressTest`, `ServiceStatusCheckerTest` (MockEngine), and `ConnectionControllerTest`,
  - `AppNavigationTest` (update), `KtorAnswerServiceTest` (address change applies to the next ask),
  - jvmTest `connection/FileServiceAddressStoreTest` and `platform/TestBuildGatingGuardTest`,
  - androidHostTest `connection/AndroidServiceAddressStoreTest`.
- Durable docs as listed below.

## Visual design impact

UI involved: yes. This adds the `Ayuda` test-tools card (only when injected) and the `Conexión` detail route. The route has six states: idle, checking, ready, not-ready or unknown, unreachable or wrong service, and invalid or storage failure. Apply these [DESIGN.md](../../DESIGN.md) sections:

- "Shared component layer" (page frame, callouts, the 48 dp targets),
- "Layout and interaction" (one primary action, keep the typed text after an error, no colour-only status),
- "Help and privacy surfaces" (a neutral outlined card),
- "Accessibility and validation" (large text, keyboard, screen reader).

The result callout is the polite live region. No new tokens, icons, or screenshot baselines are needed for this test-only surface. The existing `Ayuda` baselines must still pass unchanged.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update the "Answer service boundary". In test builds, the base URL is resolved per request from `ActiveServiceAddress`, and the `Conexión` probe uses the same client. Gating is by Android variant source sets and the Desktop `run`-only property. Release wiring keeps a fixed URL.
- `docs/constraints/ui-shell.md`: update "App shell and navigation" with one rule. MUST: test-build tools are reachable only when a host injects them. The Android release source set and every Desktop packaging or release task MUST NOT inject them, and `TestBuildGatingGuardTest` guards this.
- `DESIGN.md`: update the "App shell" bullet with one clause: `Conexión` is a test-build-only detail route from `Ayuda`, has its own `Volver`, and back returns to `Ayuda`.
- `docs/constraints/operations.md`, `docs/owner-guide.md`: not needed. No owner command is added or changed; `--android-run` and `--desktop` already launch test builds.
- `AGENTS.md`, `CONTEXT.md`, `contracts/`, and `backend/README.md`: not needed. The workflow, domain terms, wire contract, and service are unchanged.

## Focused verification (required)

<!-- verify:start -->
```sh
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.connection.*' --tests 'com.jamarglex.manijero.platform.*' --tests KtorAnswerServiceTest --tests AppNavigationTest
./gradlew --quiet :shared:testAndroidHostTest --tests 'com.jamarglex.manijero.connection.*'
./gradlew --quiet :androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:compileKotlin
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyAndroidScreenshotsTest'
```
<!-- verify:end -->

Manual (not run by the harness):

- Desktop via `./scripts/init.sh --desktop`, and the Android emulator via `./scripts/init.sh --android-run`, against `./scripts/init.sh --backend`. Exercise scenarios 3, 4 (stop the service, unset the campaign, and use a wrong port), and 6.
- Run `./gradlew :desktopApp:runDistributable` and confirm `Ayuda` has no test-tools card.

## Appendix

See [`local_service_connection.appendix.md`](../archive/specs/local_service_connection.appendix.md) for research, plan, evidence, and the validator checklist.
