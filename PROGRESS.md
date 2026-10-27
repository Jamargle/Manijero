# Project Progress

## Current state

Routine entry point. Exact feature status lives in [`feature_list.json`](feature_list.json); use
[`./scripts/select-feature.sh --status`](scripts/select-feature.sh) to read the board. Feature
contracts, raw evidence, and acceptance records remain in their owning files. Last updated:
2026-10-27.

**Feature status** — the original 50 features, `official_source_monitoring`, `official_source_discovery`, and `official_document_candidate_ingestion`, and `legal_change_impact_analysis` are accepted. Six backend RAG/knowledge-operations features and eight pilot-readiness features remain `not_started`; no implementation or validation evidence exists for those features. The selector is the current status source; this page does not duplicate the feature-id list.

**Product shape** — shared Compose chat, lands, and help surfaces in `shared/src/commonMain`, hosted
by Android and Desktop. Land records stay on-device in the single 13-field `land-store-v1` format.
The local FastAPI service exposes liveness-only `/health` and `/ask`; Android and Desktop use
overridable local development URLs. The reviewed corpus contains four official sources and four
literal passages for three procedural topics in the Andalusian PAC single application for 2026.
`/ask` requires an explicit `MANIJERO_ACTIVE_CAMPAIGN`; no hosted model, vector index, periodic
official-source scanner, or public deployment is implemented. Gemini is planned but gated off pending
current provider/privacy review.

**Known limitations (do not over-claim)**

- Apps need a reachable local service and valid campaign configuration to answer. Without them,
  they show the plain-Spanish failure notice and `Reintentar`. The supported legal scope is the
  narrow reviewed corpus in [`knowledge/pac_coverage.md`](knowledge/pac_coverage.md).
- Offline retrieval, generation, abstention, clarification, and safety metrics use synthetic
  fixtures and are report-only. The reviewed `/ask` evaluation is a six-case sample with known
  citation and critical-fact misses; see its [acceptance record](docs/validations/backend_answer_evaluation.md)
  and [evidence appendix](docs/specs/backend_answer_evaluation.appendix.md) for the exact results.
  Neither that sample nor the fixture metrics establish legal coverage or answer quality.
- The 64 screenshot baselines (34 Desktop, 30 Android) are local host-rendered pixel checks, not
  device, accessibility, usability, or iOS evidence. The procedure and limits are in
  [`docs/screenshot-regression.md`](docs/screenshot-regression.md). At 2× text, compact navigation
  labels wrap mid-word; on the compact chat screen, `Preguntar` may need a short scroll.
- The required zone, variety shortlist, search scope, and annotated summary wording are approved
  product decisions without target-user evidence. Land-field persistence has no real-device
  upgrade/downgrade evidence; details stay in the [field validation](docs/validations/land_measurement_fields.md)
  and [search validation](docs/validations/land_search_and_summary.md).
- Device-local land records still have no implemented backup or restore. The product direction is
  local-only storage with required recovery features before the private pilot; this is not user
  evidence that data loss is acceptable. See the [decision record](docs/specs/land_backup_decision.md).
- A local-only recovery direction is now recorded: recover removed lands, keep bounded same-device
  snapshots, and support a portable plaintext backup file. Those capabilities are not implemented,
  so the pilot still has no recovery guarantee. A qualified privacy/legal review is also required
  before the private pilot.
- The manual official-feed monitor records response hashes and validators separately from canonical knowledge. BOE/BOJA manual discovery now writes pending candidates into separate review state; FEGA/MAPA registries remain explicitly unchecked, BOJA is configured per bulletin, and no completeness is guaranteed. Document-level ingestion now fetches allowlisted pending candidates into a separate quarantine with preserved original/extracted hashes and page/section text, follows only bounded HTTPS redirects within the same issuer's approved hosts, and does not use monitoring feeds as document candidates. Scheduled dispatch, human-reviewed knowledge updates, reproducible index rebuilds, and release automation are not implemented. New issuers, hosts, and answerable knowledge must remain human-approved; successful polling does not prove corpus currency.
- Quarantined document extraction is standard-library PDF/HTML text extraction without OCR. It decodes embedded-font `ToUnicode` maps when present, but incomplete subset-font maps can leave `U+FFFD` placeholders or omit glyphs, and scanned, encrypted, or unsupported-filter PDFs fail closed. Live smoke checks parsed BOE and BOJA PDFs; the BOJA sample retained about 6.3% replacement characters, so extraction accuracy is not a general guarantee and a reviewer must compare both copies. Nothing extracted becomes answerable without later human review; no legal-coverage claim follows.
- Document ingestion keeps `page_count` as the number of pages that yielded text (not total pages), keeps each original-bytes version without garbage collection (re-extracting unchanged bytes replaces the previous extracted text), and assumes a single writer for each state/quarantine pair. It also depends on discovery metadata: `version_hash` covers only title and URL, so a changed file behind an unchanged URL is not detected without a re-fetch, and an extractor upgrade re-fetches rather than reprocessing stored text.
- Legal change-impact analysis is read-only and wording-based: it reads the ingestion state and quarantine and writes only a report file outside `knowledge/`. It detects explicit publication, amendment, repeal and validity wording, classifies machine-evident text apart from wording that needs legal interpretation, and links candidates to approved sources, passages and evaluation cases by instrument identity (only a title that starts with a numbered instrument is the candidate's own identity; otherwise every named instrument is a target) and document identity. It never retires, replaces or re-approves a source, and any ambiguous publication/amendment/repeal/validity signal — negated wording included, and a signal linked only to a reviewed passage or case — makes its candidate review-required even when it links no approved source. Broad word-stem triggers mean static document wording can yield ambiguous signals, so review-required may be near-universal; negation recognition covers only the listed phrasings; and a failed or rejected ingestion leaves the CLI exit `0`. Some gaps do not raise the review gate on their own: a change with no explicit signal (including a static deadline sentence without change wording), an unknown baseline that links no approved source, passage, or case, and a failed or rejected ingestion (reported as `analysis_failure: no_extracted_document`, owned by the ingestion state). A missed change therefore stays possible; only synthetic fixtures back it, there is no live run against published amendments, and detection precision/recall is not measured. See the [feature appendix](docs/specs/legal_change_impact_analysis.appendix.md).
- Official-source discovery corrected the earlier invalid blocker conclusion: the BOE HTTP 400 resulted from the missing `Accept` header; the documented response succeeds with an explicit XML/JSON Accept type. See the feature appendix for endpoints, tests, and the local TLS smoke limitation.
- Private hosted operations and distribution are not configured. The project owner is the proposed
  operator; owned-server readiness, tunnel/provider terms, and Android/macOS release artifacts remain
  planned work.
- The answer evaluation remains the existing six-case sample with known citation and critical-fact
  misses. The planned evidence expansion has not run; no answer-quality claim is supported.

**Detail on demand**

- [`docs/progress/current-state.md`](docs/progress/current-state.md) — short product narrative and evidence boundaries.
- [`docs/progress/session-log.md`](docs/progress/session-log.md) — chronological pointer index; one line per event, never repeated verification.
- [`docs/specs/<feature-id>.md`](docs/specs/) — behavior and focused verification; the sibling appendix holds planning and implementation evidence.
- [`docs/validations/<feature-id>.md`](docs/validations/) — acceptance evidence and limits.
- [`docs/risks-and-open-questions.md`](docs/risks-and-open-questions.md) — unresolved risks and decisions.

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
