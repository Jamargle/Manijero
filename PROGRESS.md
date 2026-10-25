# Project Progress

## Current state

Routine entry point. This status board is the read budget for `PROGRESS.md`; the long-form narrative and the chronological pointer index are on demand (see "Detail on demand" below).
Last updated: 2026-10-25.

**Feature set**  source of truth `feature_list.json`.

**Accepted features** — `chat_home`, `suggested_questions`, `visual_foundation`, `answer_api_contract`, `backend_health`, `source_catalog_validation`, `source_retrieval`, `grounded_answer_generation`, `safe_abstention`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `local_land_store`, `add_land`, `land_list`, `edit_land`, `remove_land`, `minimal_land_context`, `land_clarification`, `answer_land_scope`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `android_mvp_build`, `desktop_mvp_build`, `backend_ask_endpoint`, `backend_pac_corpus`, `backend_campaign_validity`, `backend_answer_evaluation`, `coverage_and_help`, `platform_ask_wiring`, `backend_citation_hardening`, `land_setup_fields_decision`, `land_backup_decision`, `desktop_land_layout_decision`, `desktop_wide_land_layout`, `shared_design_system`, `design_token_refresh`, `screenshot_regression_tests`, `brand_vectors`, `ui_component_library`, `app_chrome_navigation`.

**Product shape** — shared Compose chat and lands flow in `shared/src/commonMain`, rendered by Android and Desktop. The backend is FastAPI with liveness-only `/health` and local `/ask` routes. Lands are device-local (`~/.manijero/lands-v1.txt` on Desktop, `manijero_lands` SharedPreferences on Android, shared `land-store-v1` format). The knowledge corpus contains 4 verified official sources and 4 literal passages for the 2026 Andalusian PAC single application. `/ask` requires explicit `MANIJERO_ACTIVE_CAMPAIGN`; source retrieval is scoped to that campaign and the UTC validity date. Android and Desktop now inject a platform Ktor engine and local development base URL: Android defaults to the emulator host bridge `http://10.0.2.2:8000` and Desktop to `http://127.0.0.1:8000`, both overridable.

**Known limitations (do not over-claim)**

- The launched apps now use the local `/ask` service when it is running. Without a reachable backend or a valid campaign configuration they show the existing plain-Spanish failure notice with `Reintentar`; answered, abstained, and source-card renders were observed only against the local reviewed corpus, not as legal coverage.
- Retrieval, generation, abstention, clarification, and safety numbers come from synthetic, implementer-authored fixtures; no metric is a release gate and none is legal-coverage evidence.
- The canonical `/ask` answer-evaluation run is a narrow, reviewed six-case sample (campaign `2026`, as-of `2026-10-17`), not a representative benchmark: state agreement 6/6, expected-answer coverage 4/4, unexpected answers 0, citation agreement 1/4, critical-fact matches 2/4, and clarification outcomes 0. Cases cover the ordinary SGA/recognized-entity application route, 2026 filing and modification deadlines (including distinguishing 15 May filing from 15 June modification), unsupported campaign 2025, and an uncovered aid-amount question. Explicit gaps: no stale/expired-evidence case and no land-clarification case (the reviewed corpus has no genuinely different land applicability for this question slice). Report-visible mismatches: source and passage misses for `canal-sga-2026`, `fecha-modificacion-2026`, and `distingue-fechas-2026`; critical-fact misses for `fecha-modificacion-2026` and `distingue-fechas-2026`. These metrics are report-only and are neither legal proof nor evidence of answer quality.
- Android evidence is an emulator-only debug artifact; Desktop evidence is a local run. `screenshot_regression_tests` adds a local pixel gate: eighteen Desktop and fourteen Android host frames (app scenes, the review-only `brand_vectors` board in light and dark at 900×1200 dp, four `ui_component_library` gallery captures per host, and four `app_chrome_navigation` shell captures per host) under `shared/src/{jvmTest,androidHostTest}/screenshots/`. `./gradlew :shared:verifyScreenshots` verifies read-only and `:shared:recordScreenshots` records after review; the procedure is in `docs/screenshot-regression.md`. Desktop goldens are macOS host-font-pinned; Android goldens are Robolectric SDK 35 host renders. Both suites are excluded from the other tiers and the Linux CI gate, so this is a local gate with no iOS, accessibility, or device claim.
- `shared_design_system`: typography is the Material 3 default (no custom typography file, scale, or bundled font asset). The backend pytest suite needs the local virtualenv's dev requirements (`backend/requirements-dev.txt`, including `jsonschema`); with them installed it ran for `design_token_refresh` (618 tests). The iOS simulator compile and full-screen enlarged-text/keyboard-navigation audits were not performed.
- `design_token_refresh`: the Stitch palette and token scale are implemented and contrast-gated in both appearances. No token-board preview (light, dark, or 2× text) was rendered, because the repository has no headless Compose preview renderer and this host stayed in dark appearance; board layout and 2× reflow remain manual checks. Screens are not restyled beyond the five card surfaces now on `surfaceContainerLowest`.
- `brand_vectors`: eighteen monochrome vector assets and three decorative wrappers in `shared/src/commonMain`; no screen adopts them, so there is no user-visible surface yet. Evidence is the four review-only board goldens on the two host renderers only; no iOS build exercised the vector subset.
- `ui_component_library`: fourteen presentational declarations in `shared/src/commonMain/.../design/` (nine component files plus two navigation files), test-only gallery, eight new review-only goldens (four per host). No screen adopts the layer, so there is no user-visible surface yet; evidence is host renders only. At 2× text the compact bottom-navigation labels wrap mid-word while remaining fully visible, recorded for `app_chrome_navigation`; the backend pytest tier was skipped because pytest is absent from the available interpreters.
- `app_chrome_navigation`: the shell is the one frame for Android and Desktop (brand top bar, adaptive bottom bar/rail at 840 dp, tab selection in the order `Mis terrenos`, `Asistente`, `Ayuda`, single inset owner, common back rules); with a local store the app opens on `Mis terrenos`, and the chat `Mis terrenos` button plus the lands/help `Volver` controls are removed. At 2× text on a compact window the bottom-navigation labels still wrap mid-word (pre-existing `ManijeroBottomNavigation` behavior); the device and Desktop checks are manual observations, the goldens are host renders only, and product-owner sign-off on the images is still pending.

**Open items**

- The remaining backend citation hardening F1 and stale `knowledge/README.md` citation wording are resolved by `backend_citation_hardening`.
- Outstanding manual check: the low-digital-confidence comprehension check (owner `chat_accessibility`).
- Outstanding manual check: human owner sign-off on the thirty-two screenshot images (twelve app baselines, four board captures, eight gallery captures, and eight shell captures). The mechanism, images, and validator review exist for the Desktop set, the board captures, the gallery captures, and the shell captures; product-owner approval does not, and the Android app baselines have not had independent validator review.

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
- Start the local API: `./scripts/init.sh --backend` (creates/reuses `backend/.venv`, installs runtime requirements, and launches Uvicorn). Android build: `./scripts/init.sh --android`; build, boot an emulator if needed, install, and launch: `./scripts/init.sh --android-run` (uses the first configured AVD when none is running). Launch Desktop: `./scripts/init.sh --desktop`.
- The offline checks pin `--as-of 2026-10-13` so runs are deterministic; override with `MANIJERO_AS_OF=YYYY-MM-DD`.

Evaluator flags, report-only caveats, and a feature's own commands live in its spec; the metrics stay report-only (see the limitations above).

## Session log

The chronological change log is [`docs/progress/session-log.md`](docs/progress/session-log.md), moved out of this file on 2026-10-17 to keep this file small; since 2026-10-17 it is a one-line pointer index. Append new entries there.
