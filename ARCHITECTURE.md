# Architecture

This document records the architecture that exists in the repository. It is the feature-level map; `MasterPlanV3.md` is a historical planning reference and is not the source of current implementation boundaries.

## Runtime surfaces and dependency direction

```text
androidApp ─┐
            ├──> shared
desktopApp ─┘

shared ──HTTP/JSON contract──> backend `/ask`
                                │
                                └── reads local knowledge artifacts

contracts/ ──defines──> shared client payloads and backend response shape
knowledge/*.schema.json ──defines──> knowledge artifact formats
```

- **`shared`** owns reusable Kotlin domain and presentation behavior, including Compose UI in `shared/src/commonMain`. Android and Desktop are hosts of that shared code. Platform entry points and integrations stay in `androidApp` and `desktopApp` or the corresponding `shared` platform source sets; shared code does not depend on either host.
- **`androidApp`** and **`desktopApp`** depend on `shared`. They provide launch/runtime wiring and platform-specific integrations; neither host depends on the other.
- **`backend`** is a separate Python service. It does not import app code. Its HTTP surface includes liveness-only `GET /health` and `POST /ask`. `/ask` requires explicit four-digit `MANIJERO_ACTIVE_CAMPAIGN`; UTC validity date is independent. Retrieval permits only neutral and exact-campaign sources. Operators rotate expired campaign entries and passages out of active artifacts in a reviewed update. Invalid configuration or corpus fails closed with generic 503.
- **`contracts/`** is the versioned, language-neutral HTTP contract shared by the Kotlin client and the backend. `contracts/openapi.yaml` and its examples are authoritative for wire shape; Kotlin DTOs and any future backend route must conform to it.
- **`knowledge/`** holds reviewed knowledge artifacts and their JSON Schema contracts. `knowledge/*.schema.json` defines on-disk formats; the corresponding executable validators live in `backend/app/` and must remain aligned with those schemas. Synthetic evaluation fixtures live under `backend/tests/fixtures/`, not as canonical knowledge.

## Answer service boundary

`shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt` defines the narrow `AnswerService` interface and shared request/response DTOs. `KtorAnswerService` sends the contract-shaped request and maps transport failures to payload-free app errors. The shared presentation layer depends on `AnswerService`, not Ktor engine or platform URL configuration. HTTP engine creation and base-URL configuration belong at the platform composition root. The request contains only the question and minimal land context; local land names and notes remain on-device.

The client contract and backend route now exist, but platform base-URL wiring remains an open item. Until that wiring is completed, the shipped app still presents its unavailable-service failure state rather than using this endpoint.

## Offline boundaries

- Catalog validation, retrieval, answer verification/generation, abstention, clarification, and land-safety evaluation are currently deterministic offline backend modules. They use reviewed local inputs, make no network calls, and have no configured model provider.
- The knowledge source catalog and canonical `passages.json` are intentionally empty. The valid empty passage set produces safe abstention. Evaluation data is synthetic and report-only; its metrics do not establish legal coverage or answer quality for real users.
- Knowledge discovery, ingestion automation, scheduled jobs, hosted model providers, and persistence/vector services are not current runtime components. Any such design in `MasterPlanV3.md` is historical/planned material until implemented and documented here.
- Lands are stored locally by platform: Android uses SharedPreferences and Desktop uses `~/.manijero/lands-v1.txt`, with the shared `land-store-v1` representation. Land data is not backend storage.

## Contract locations

| Concern | Contract/source | Implementation or consumer |
|---|---|---|
| HTTP request and answer response | `contracts/openapi.yaml`, `contracts/examples/` | `shared/.../chat/AnswerService.kt`, `backend/app/ask_api.py` |
| Reviewed source catalog | `knowledge/source_catalog.schema.json` | `backend/app/source_catalog.py` |
| Reviewed passages | `knowledge/passages.schema.json` | `backend/app/retrieval.py` |
| Land-safety evaluation cases | `knowledge/land_safety_eval.schema.json` | `backend/app/land_safety_eval.py` |

When adding a schema, keep its validator and examples/fixtures aligned. When changing a domain, dependency direction, runtime surface, or boundary, update this document so feature work can use it without reconstructing the architecture from the historical plan.
