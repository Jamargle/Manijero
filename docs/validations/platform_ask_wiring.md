# Validation — `platform_ask_wiring`

**Verdict: accept** (2026-10-20).

The implementation meets the feature contract. Android and Desktop composition roots create platform Ktor engines and build their clients through the shared `answerHttpClient(engine)`, preserving JSON content negotiation, bounded timeouts, and non-success handling. Endpoint selection is explicit: Android uses `manijeroAskBaseUrl` with the emulator host bridge default, and Desktop uses a JVM property, then `MANIJERO_ASK_BASE_URL`, then local loopback. The Android cleartext allowance is debug-only and Internet permission is declared. No production endpoint is embedded.

## Checks performed

- `./scripts/init.sh --feature platform_ask_wiring` — passed independently in the validator session: `KtorAnswerServiceTest`, `ChatConversationTest`, `AskEndpointTest`, Desktop build, and Android debug assemble.
- Reviewed the recorded `./scripts/init.sh --verify` result: shared JVM tests, contract examples, source-catalog validation, and all five offline evaluators passed; Android host tests and both app builds passed. Backend pytest was skipped because pytest is not installed.
- Reviewed the recorded live evidence: Desktop and Android emulator each rendered the backend answer and source card for a submitted question, with matching `POST /ask` 200 responses. With the backend stopped, both platforms rendered the existing plain-Spanish connection failure and `Reintentar`.
- Reviewed endpoint-selection tests covering the platform default, primary-override precedence, and blank-primary fallback.
- Reviewed the diff, `ARCHITECTURE.md`, the appendix evidence, and feature status. `git diff --check` is clean.

## Security, scope, and documentation

No feature-scoped blocking issue found. Development HTTP is limited to the Android debug build, the documented endpoints are local development transport rather than production URLs, and captured logs contained no question, land, or response payload. The change keeps the shared contract, land context, retry, and rendering behavior unchanged; no backend, contract, UI redesign, or iOS work was introduced. Durable architecture documentation and feature evidence are current.
