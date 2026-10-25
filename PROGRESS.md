# Project Progress

## Current state

Routine entry point. This status board is the read budget for `PROGRESS.md`; the long-form narrative and the chronological pointer index are on demand (see "Detail on demand" below).
Last updated: 2026-10-25.

**Feature set**  source of truth `feature_list.json`.

**Accepted features** — `chat_home`, `suggested_questions`, `visual_foundation`, `answer_api_contract`, `backend_health`, `source_catalog_validation`, `source_retrieval`, `grounded_answer_generation`, `safe_abstention`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `local_land_store`, `add_land`, `land_list`, `edit_land`, `remove_land`, `minimal_land_context`, `land_clarification`, `answer_land_scope`, `land_data_disclosure`, `chat_accessibility`, `land_form_accessibility`, `land_safety_evaluation`, `android_mvp_build`, `desktop_mvp_build`, `backend_ask_endpoint`, `backend_pac_corpus`, `backend_campaign_validity`, `backend_answer_evaluation`, `coverage_and_help`, `platform_ask_wiring`, `backend_citation_hardening`, `land_setup_fields_decision`, `land_backup_decision`, `desktop_land_layout_decision`, `desktop_wide_land_layout`, `shared_design_system`, `design_token_refresh`, `screenshot_regression_tests`, `brand_vectors`.

**Product shape** — shared Compose chat and lands flow in `shared/src/commonMain`, rendered by Android and Desktop. The backend is FastAPI with liveness-only `/health` and local `/ask` routes. Lands are device-local (`~/.manijero/lands-v1.txt` on Desktop, `manijero_lands` SharedPreferences on Android, shared `land-store-v1` format). The knowledge corpus contains 4 verified official sources and 4 literal passages for the 2026 Andalusian PAC single application. `/ask` requires explicit `MANIJERO_ACTIVE_CAMPAIGN`; source retrieval is scoped to that campaign and the UTC validity date. Android and Desktop now inject a platform Ktor engine and local development base URL: Android defaults to the emulator host bridge `http://10.0.2.2:8000` and Desktop to `http://127.0.0.1:8000`, both overridable.

**Known limitations (do not over-claim)**

- The launched apps now use the local `/ask` service when it is running. Without a reachable backend or a valid campaign configuration they show the existing plain-Spanish failure notice with `Reintentar`; answered, abstained, and source-card renders were observed only against the local reviewed corpus, not as legal coverage.
- Retrieval, generation, abstention, clarification, and safety numbers come from synthetic, implementer-authored fixtures; no metric is a release gate and none is legal-coverage evidence.
- The canonical `/ask` answer-evaluation run is a narrow, reviewed six-case sample (campaign `2026`, as-of `2026-10-17`), not a representative benchmark: state agreement 6/6, expected-answer coverage 4/4, unexpected answers 0, citation agreement 1/4, critical-fact matches 2/4, and clarification outcomes 0. Cases cover the ordinary SGA/recognized-entity application route, 2026 filing and modification deadlines (including distinguishing 15 May filing from 15 June modification), unsupported campaign 2025, and an uncovered aid-amount question. Explicit gaps: no stale/expired-evidence case and no land-clarification case (the reviewed corpus has no genuinely different land applicability for this question slice). Report-visible mismatches: source and passage misses for `canal-sga-2026`, `fecha-modificacion-2026`, and `distingue-fechas-2026`; critical-fact misses for `fecha-modificacion-2026` and `distingue-fechas-2026`. These metrics are report-only and are neither legal proof nor evidence of answer quality.
- Android evidence is an emulator-only debug artifact; Desktop evidence is a local run. `screenshot_regression_tests` adds a local pixel gate for both platforms, now ten Desktop JVM frames under `shared/src/jvmTest/screenshots/` and six Android frames under `shared/src/androidHostTest/screenshots/`: the twelve unchanged app baselines (four shared scenes — `ChatHome` idle light, `ChatHome` answered-plus-source dark, `LandList` two-land light, `LandList` empty dark — at the desktop surface and a 360×800 dp viewport on Desktop, and at 360×800 dp on Android) plus four new review-only `brand_vectors` board captures (light and dark, 900×1200 dp, a review surface rather than a screen). The Android frames are rendered by Robolectric 4.17 on the host JVM with no emulator or device. `./gradlew :shared:verifyScreenshots` verifies both read-only, `:shared:recordScreenshots` re-records both after review, and per-platform verify/record tasks also exist; the procedure is in `docs/screenshot-regression.md`. Desktop goldens are macOS host-font-pinned; Android goldens are pinned to Robolectric SDK 35 and prove host rendering only, not a device, emulator, or other API level. Both suites are excluded from `:shared:jvmTest`/`:shared:testAndroidHostTest`, `--fast`, and the Linux CI gate: this is a developer-invoked local gate, not CI enforcement, and it makes no iOS rendering, accessibility, usability, or behavior claim. Owner sign-off on the sixteen images (twelve app baselines plus four board captures) is still pending.
- `shared_design_system`: typography is the Material 3 default (no custom typography file, scale, or bundled font asset). The backend pytest suite needs the local virtualenv's dev requirements (`backend/requirements-dev.txt`, including `jsonschema`); with them installed it ran for `design_token_refresh` (618 tests). The iOS simulator compile and full-screen enlarged-text/keyboard-navigation audits were not performed.
- `design_token_refresh`: the Stitch palette and token scale are implemented and contrast-gated in both appearances. No token-board preview (light, dark, or 2× text) was rendered, because the repository has no headless Compose preview renderer and this host stayed in dark appearance; board layout and 2× reflow remain manual checks. Screens are not restyled beyond the five card surfaces now on `surfaceContainerLowest`.
- `brand_vectors`: eighteen hand-authored monochrome Android-XML vectors (brand mark, sixteen `ic_*` outline glyphs, olive-branch illustration) and three decorative wrappers live in `shared/src/commonMain`; no screen, shell, or platform module adopts them yet, so they have no user-visible surface. Rendering evidence is the four review-only board goldens described above, which prove decode and theme tinting on the two host renderers only. The vector subset was not exercised by an iOS build, and the per-file geometry/colour rules are enforced by the focused shell gates and the four board goldens (there is no separate inventory test; the board's accessor references make a missing vector a compile error).

**Open items**

- The remaining backend citation hardening F1 and stale `knowledge/README.md` citation wording are resolved by `backend_citation_hardening`.
- Outstanding manual check: the low-digital-confidence comprehension check (owner `chat_accessibility`).
- Outstanding manual check: human owner sign-off on the sixteen screenshot images — the twelve `screenshot_regression_tests` app baselines under `shared/src/jvmTest/screenshots/` (8 Desktop) and `shared/src/androidHostTest/screenshots/` (4 Android), plus the new review-only `brand_vectors` board captures in both directories (2 + 2) — (the mechanism, images, and validator review exist for the Desktop set and for the four board captures; product-owner approval does not, and the four Android app baselines have not had independent validator review).

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
