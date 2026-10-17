# Current state — narrative detail

On-demand narrative behind the status board in [`PROGRESS.md`](../../PROGRESS.md). The accepted
set, product shape, known limitations, and open items live there; this page adds the narrative and
points at the per-feature records.

## Product and architecture snapshot

- **App.** Kotlin Multiplatform: `shared` (Compose UI and business logic in `commonMain`),
  `androidApp`, `desktopApp`, plus an iOS target that is not an MVP deliverable. `App.kt` renders
  the shared Spanish chat flow and the `Chat` / `Mis terrenos` lands destinations; both platforms
  reuse it.
- **Chat boundary.** A pure `ChatHomeState` reducer plus `ChatConversation` over an injected
  `AnswerService`. `KtorAnswerService` targets `<baseUrl>/ask`; the shipped default is
  `UnavailableAnswerService` because the backend exposes no `/ask`, so the honest plain-Spanish
  failure notice with `Reintentar` is the real behavior and every answered, abstained, or
  source-card render is preview/reducer-based.
- **Lands.** Device-local and versioned (`land-store-v1`): `~/.manijero/lands-v1.txt` on Desktop,
  `manijero_lands` SharedPreferences on Android. Add, list, edit, and remove all go through the
  shared repository; unknown attributes stay `UNKNOWN`; only the attributes a question needs may
  leave the device (`chat/LandContextBuilder.kt`, pinned by `privacy/LandDataDisclosure.kt`).
- **Backend.** FastAPI with `/health` as the only route: no `/ask`, no model provider configured.
- **Knowledge and offline boundaries.** `knowledge/source_catalog.json` (`source-catalog-v1`) is a
  valid but intentionally empty catalog that retrieval re-validates and fails closed on. The
  standard-library offline chain is `backend/app/{retrieval,generation,abstention,clarification,
  land_safety_eval}.py`, each with a matching `backend/scripts/evaluate_*.py` CLI, a schema under
  `knowledge/`, and synthetic implementer-authored fixtures under `backend/tests/fixtures/`. Their
  numbers are report-only and none is legal-coverage evidence.
- **Theme and accessibility.** `visual_foundation`'s olive theme (`theme/ManijeroColors.kt`,
  `ManijeroTheme.kt`, `ManijeroTypography.kt`) is applied once in `App()`; chat, the land forms,
  and the privacy notice carry the accepted accessibility treatment (merged semantics, polite live
  regions, never colour alone).
- **Verification and evidence.** The `./scripts/init.sh` tiers (`--feature`, `--fast`, `--verify`,
  `--backend-tests`, `--android`, `--desktop`) are the gate. No automated UI/E2E harness exists:
  Android evidence is an emulator-only debug artifact and Desktop evidence is a local run.

## Per-feature record

Each feature's narrative, decisions, and raw `Feature evidence` live in its appendix
[`docs/specs/<feature-id>.appendix.md`](../../docs/specs/); the contract is
`docs/specs/<feature-id>.md`; the authoritative acceptance record is
`docs/validations/<feature-id>.md`. The chronological pointer index is
[`docs/progress/session-log.md`](session-log.md). Status and dependencies are in `feature_list.json`;
use `./scripts/select-feature.sh` instead of reading it by hand.
