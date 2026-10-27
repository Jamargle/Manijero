# Architecture

This document is the short map of stable ownership, dependency direction, and cross-system boundaries. Use feature specs for behavior and verification, and `PROGRESS.md` for current implementation status and limitations. Keep volatile state out of this file.

## Runtime surfaces and dependency direction

```text
androidApp ─┐
            ├──> shared
desktopApp ─┘

shared ──HTTP/JSON──> backend
```

- **`shared`** owns reusable Kotlin domain and presentation behavior, including Compose UI in `shared/src/commonMain`. Android and Desktop are hosts of that shared code. Platform entry points and integrations stay in `androidApp` and `desktopApp` or the corresponding `shared` platform source sets; shared code does not depend on either host.
- **`androidApp`** and **`desktopApp`** depend on `shared`. They provide launch/runtime wiring and platform-specific integrations; neither host depends on the other.
- **`backend`** owns the Python service and knowledge-backed request handling; it does not import app code. It reads local knowledge artifacts and exposes `GET /health` and `POST /ask`. Endpoint behavior and operational rules belong in `backend/README.md` and the relevant feature specs.
- **`backend/app/source_monitor.py`** polls explicitly configured official feeds and writes monitoring state separately from canonical knowledge. It is dispatched manually or by an external owner-managed scheduler; it cannot update the approved catalog or passages.
- **`backend/app/source_discovery.py`** adapts documented BOE and BOJA registries into separate pending-candidate state. It is not an ingestion or answerability path.
- **`backend/app/document_ingestion.py`** fetches allowlisted pending candidates into a separate local quarantine, preserving original bytes/hashes and extracted page/section text. It never writes canonical knowledge or makes a candidate answerable; a human review and approval step remains separate.
- **`backend/app/change_impact.py`** reads the ingestion state and quarantine plus approved catalog, passages, and evaluation cases, and writes one deterministic impact report outside `knowledge/`. It is read-only: it never changes approved knowledge, never retires a source, and marks every potentially affected candidate as review-required. `backend/scripts/analyze_legal_changes.py` is its operator entry point.
- **`backend/app/review_package.py`** prepares a local, deterministic draft review package from quarantined candidates and a reviewed proposal. `prepare` and `decide` are read-only over canonical knowledge; a corpus change requires the reviewed evaluation case set and validates the after-state for orphaned cases. `merge` is the only path that writes the approved catalog/passages, and only after approval from a requested reviewer, matching package/checks/case digests, and an unchanged canonical baseline; it never reindexes or releases and preserves the field order of untouched entries. Its local draft does not depend on a Git/hosting API. `backend/scripts/knowledge_review.py` is its operator entry point.
- **`contracts/`** owns the versioned, language-neutral HTTP wire contract. `contracts/openapi.yaml` is authoritative for request and response shape; examples are checked against it. Client DTOs and backend handlers conform to this contract.
- **`knowledge/`** owns reviewed knowledge artifacts and their JSON Schema formats. Executable validators live in `backend/app/` and must remain aligned with the schemas. Test fixtures are not canonical knowledge.

## Answer service boundary

`AnswerService.kt` defines the narrow shared interface and request/response DTOs. `KtorAnswerService` sends contract-shaped requests and maps transport failures to payload-free app errors. Shared presentation depends on `AnswerService`, not a Ktor engine or platform URL configuration. Hosts create and configure HTTP engines at their composition roots. Requests contain only the question and minimal land context; local land names and notes remain on-device. Platform-specific engine, endpoint, manifest, and lifecycle configuration is documented by the `platform_ask_wiring` feature contract and implemented in the host entry points.

## Data and platform boundaries

- Backend processing uses local knowledge artifacts; land records are stored on-device and are not backend storage. Current corpus contents, service availability, and evaluation limitations are tracked in `PROGRESS.md`.
- Android and Desktop are current hosts; shared business behavior and Compose UI belong in `shared/src/commonMain`, while platform integrations remain in host or platform source sets. Other platform support is not implied by the shared source layout.

## Contract map

| Boundary | Authority | Consumers / implementation |
|---|---|---|
| HTTP wire shape | `contracts/openapi.yaml` and validated examples | Shared client DTOs; backend handlers |
| Knowledge artifact shape | `knowledge/*.schema.json` | Matching validators in `backend/app/` |

When adding a knowledge schema, keep its validator and fixtures aligned. Update this document when ownership, dependency direction, runtime boundaries, or contract authority changes; put endpoint rules, configuration details, and feature behavior in their owning docs instead.
