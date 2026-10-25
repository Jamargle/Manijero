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
  `AnswerService`. `KtorAnswerService` targets `<baseUrl>/ask`; Android and Desktop inject a
  platform Ktor engine and local development base URL, so the launched apps use the running local
  service. Without a reachable backend they show the existing plain-Spanish failure notice with
  `Reintentar`.
- **Lands.** Device-local: the app reads and writes one `land-store-v1` format (13 fields: required
  zone/paraje, plus optional variety, surface and olive-tree count) in `~/.manijero/lands-v1.txt` on
  Desktop and the `manijero_lands` SharedPreferences on Android. Add, list, edit, and remove all go
  through the shared repository; unknown attributes stay `UNKNOWN` and absent measures stay absent;
  only the attributes a question needs may leave the device (`chat/LandContextBuilder.kt`, pinned by
  `privacy/LandDataDisclosure.kt`). The list filters those lands by text and summarizes the annotated
  surface and olive count of the shown set; the query is in-memory only and neither the query nor the
  summary is stored or sent.
- **Backend.** FastAPI exposes liveness-only `/health` and a local, campaign-scoped `/ask`; no
  model provider is configured.
- **Knowledge and offline boundaries.** `knowledge/source_catalog.json` (`source-catalog-v1`)
  contains the reviewed 2026 Andalusia PAC sources, with literal passages in
  `knowledge/passages.json`; retrieval re-validates both and fails closed. The
  standard-library offline chain is `backend/app/{retrieval,generation,abstention,clarification,
  land_safety_eval}.py`, each with a matching `backend/scripts/evaluate_*.py` CLI, a schema under
  `knowledge/`, and synthetic implementer-authored fixtures under `backend/tests/fixtures/`. Their
  numbers are report-only and none is legal-coverage evidence.
- **Theme and accessibility.** The shared design system's themed palette (`theme/ManijeroColors.kt`,
  `ManijeroTheme.kt`) is applied once in `App()` and renders the approved Stitch token palette in
  both appearances, with two `outlineVariant` accessibility corrections. The shared theme tests
  (`ManijeroColorsTest`, `ManijeroDesignSystemTest`) gate the documented values and contrast in light
  and dark, so a wrong value fails the shared build instead of reaching a screen. `DESIGN.md` records
  the values and the two corrections; `docs/design/ui-refresh-plan.md` §3.1 holds the approved plan.
  Screens are not yet restyled beyond the five existing card surfaces, which now read
  `surfaceContainerLowest` so they still look raised against the canvas. Chat, the land forms, and
  the privacy notice carry the accepted accessibility treatment (merged semantics, polite live
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
