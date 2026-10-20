# Project Progress

## Current state

Routine entry point. This status board is the read budget for `PROGRESS.md`; the long-form narrative and the chronological pointer index are on demand (see "Detail on demand" below).
Last updated: 2026-10-20.

**Feature set**  source of truth `feature_list.json`.

**Accepted features** — `chat_home`, `suggested_questions`, `visual_foundation`, `answer_api_contract`, `backend_health`, `source_catalog_validation`, `source_retrieval`, `grounded_answer_generation`, `safe_abstention`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `local_land_store`, `add_land`, `land_list`, `edit_land`, `remove_land`, `minimal_land_context`, `land_clarification`, `answer_land_scope`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `android_mvp_build`, `desktop_mvp_build`, `backend_ask_endpoint`, `backend_pac_corpus`, `backend_campaign_validity`, `backend_answer_evaluation`, `coverage_and_help`, `platform_ask_wiring`, `backend_citation_hardening`, `land_setup_fields_decision`, `land_backup_decision`.

**Product shape** — shared Compose chat and lands flow in `shared/src/commonMain`, rendered by Android and Desktop. The backend is FastAPI with liveness-only `/health` and local `/ask` routes. Lands are device-local (`~/.manijero/lands-v1.txt` on Desktop, `manijero_lands` SharedPreferences on Android, shared `land-store-v1` format). The knowledge corpus contains 4 verified official sources and 4 literal passages for the 2026 Andalusian PAC single application. `/ask` requires explicit `MANIJERO_ACTIVE_CAMPAIGN`; source retrieval is scoped to that campaign and the UTC validity date. Android and Desktop now inject a platform Ktor engine and local development base URL: Android defaults to the emulator host bridge `http://10.0.2.2:8000` and Desktop to `http://127.0.0.1:8000`, both overridable.

**Known limitations (do not over-claim)**

- The launched apps now use the local `/ask` service when it is running. Without a reachable backend or a valid campaign configuration they show the existing plain-Spanish failure notice with `Reintentar`; answered, abstained, and source-card renders were observed only against the local reviewed corpus, not as legal coverage.
- Retrieval, generation, abstention, clarification, and safety numbers come from synthetic, implementer-authored fixtures; no metric is a release gate and none is legal-coverage evidence.
- The canonical `/ask` answer-evaluation run is a narrow, reviewed six-case sample (campaign `2026`, as-of `2026-10-17`), not a representative benchmark: state agreement 6/6, expected-answer coverage 4/4, unexpected answers 0, citation agreement 1/4, critical-fact matches 2/4, and clarification outcomes 0. Cases cover the ordinary SGA/recognized-entity application route, 2026 filing and modification deadlines (including distinguishing 15 May filing from 15 June modification), unsupported campaign 2025, and an uncovered aid-amount question. Explicit gaps: no stale/expired-evidence case and no land-clarification case (the reviewed corpus has no genuinely different land applicability for this question slice). Report-visible mismatches: source and passage misses for `canal-sga-2026`, `fecha-modificacion-2026`, and `distingue-fechas-2026`; critical-fact misses for `fecha-modificacion-2026` and `distingue-fechas-2026`. These metrics are report-only and are neither legal proof nor evidence of answer quality.
- Android evidence is an emulator-only debug artifact; Desktop evidence is a local run. No automated UI/E2E harness exists (the repo refuses test-only dependencies).

**Open items**

- The remaining backend citation hardening F1 and stale `knowledge/README.md` citation wording are resolved by `backend_citation_hardening`.
- Desktop H1 (accepted, unfixed): the 720dp capped/centred column holds for the chat home only; `Mis terrenos`, the forms, and the privacy notice render full-width on a wide window (`DESIGN.md`, `docs/risks-and-open-questions.md`).
- Outstanding manual check: the low-digital-confidence comprehension check (owner `chat_accessibility`).

**Detail on demand**

- `docs/progress/current-state.md` — the product and architecture narrative.
- `docs/progress/session-log.md` — the chronological pointer index (newest entries last); one line per event, never restated evidence.
- `docs/specs/<feature-id>.md` — the feature's contract: goal, acceptance scenarios, expected file changes, and focused verification; its planning and verification record is the sibling `docs/specs/<feature-id>.appendix.md` (repository research, implementation plan, validator checklist, "Feature evidence").
- `docs/validations/<feature-id>.md` — the authoritative acceptance record per accepted feature.

## Start and verify

Tiers, cheapest first; `./scripts/init.sh` holds the exact commands.

- Toolchain check: `./scripts/init.sh` (default; prints the same commands).
- Next feature: `./scripts/select-feature.sh --next` — the next dependency-ready feature id and its next role; `./scripts/select-feature.sh --status` prints the board and unfinished-feature readiness. Use these instead of reading `feature_list.json` by hand.
- Focused feature check: `./scripts/init.sh --feature <feature-id>` — runs the command block the feature spec publishes between its `<!-- verify:start -->` and `<!-- verify:end -->` markers.
- No-device tier: `./scripts/init.sh --fast` — `:shared:jvmTest`, `contracts/validate_examples.py`, the backend pytest suite, the `source-catalog-v1` validation of `knowledge/source_catalog.json`, and the five offline evaluators over `backend/tests/fixtures/`.
- Full gate: `./scripts/init.sh --verify` (`--full`) — `--fast` plus `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build`.
- Backend unit tests alone: `./scripts/init.sh --backend-tests [targets]` — needs pytest; with none available, `--fast` prints the virtualenv recipe, skips the suite locally, and fails under `CI`.
- Android build: `./scripts/init.sh --android`. Launch Desktop: `./scripts/init.sh --desktop`.
- The offline checks pin `--as-of 2026-10-13` so runs are deterministic; override with `MANIJERO_AS_OF=YYYY-MM-DD`.

Evaluator flags, report-only caveats, and a feature's own commands live in its spec; the metrics stay report-only (see the limitations above).

## Session log

The chronological change log is [`docs/progress/session-log.md`](docs/progress/session-log.md), moved out of this file on 2026-10-17 to keep this file small; since 2026-10-17 it is a one-line pointer index. Append new entries there.
