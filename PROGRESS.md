# Project Progress

## Current state

Routine entry point. Exact feature status lives in [`feature_list.json`](feature_list.json); use
[`./scripts/select-feature.sh --status`](scripts/select-feature.sh) to read the board. Feature
contracts, raw evidence, and acceptance records remain in their owning files. Last updated:
2026-11-07.

**Feature status** — 93 of 121 features are accepted, including `validity_checker` (offline, digest-bound check of the reviewed catalog and accepted change-impact signals: explicit expiry versus an injected UTC as-of date, machine-evident repeal/expiry only as a review-required retirement proposal, publication additions as review leads, ambiguous/negated signals never retire; writes one derived `validity-review-v1` artifact outside `knowledge/` and leaves the corpus, releases, indexes, and `/ask` untouched; validator accept final, no owner walkthrough), `official_page_change_monitor`
(developer-only offline-in-tests command that compares approved FEGA, MAPA, and Junta PAC page
snapshots by exact-byte/text hash and a bounded normalized diff, writes a deterministic report and
last-good state outside `knowledge/`, and never fetches in tests or changes catalog/releases/indexes
or `/ask`; validator accept is final, no owner walkthrough), `feedback_endpoint` (privacy-minimal
`POST /feedback` rating, only `useful`/`not_useful`, per-process counts with no stored content,
identifiers, or idempotency; validator accept, no owner walkthrough), `answer_feedback_ui` (`Útil` /
`No útil` under each finished answer in the shared chat; sends only that rating through the pilot-token
transport, thanks line locks the answer, failure keeps both enabled; in-memory, no identifiers;
validator accept, no owner walkthrough) and `contract_fuzz_tests` (developer-only seeded conformance suite generated from `contracts/openapi.yaml`: contract-valid requests get schema-valid `/ask` responses, invalid ones get generic 4xx, and a guard fails on FastAPI-vs-contract drift; offline and fixture-corpus only), `domain_procedure_map`
(git-tracked, reviewed-taxonomy index of 16 olive-grove topics in `knowledge/procedure_map.json` with
an offline validator; every topic stays `proposed`, 15 of 16 `uncovered`; validator accept, no owner
walkthrough by owner decision), `legal_document_parser` (quarantined
official PDFs → deterministic Markdown plus a provenance manifest, outside `knowledge/` and never
answerable; tables and Spanish OCR only through an optional pinned runtime, fake/fixture-verified),
`legal_structure_chunker` (offline developer command that splits that Markdown into
article/chapter/annex chunks with contextual prefixes and catalog-only validity, outside `knowledge/`
and never answerable; validator accept, no owner walkthrough by owner decision), `corpus_security_rules` (offline scan
that rejects prompt-injection or nominal-listing documents at ingestion without keeping their bytes
or text, plus a canonical release gate that refuses a single identifier shape; heuristic, precision
unmeasured), `rag_inspector_view` (developer
`Inspeccionar` view of retrieved passages, scores, and verification steps; local test builds on a
loopback service only, data sent only in the `development` profile; validator accept, no owner
walkthrough by owner decision), `backend_health_metrics`
(privacy-safe `GET /metrics` in Prometheus text format, open locally and pilot-token gated in QA;
validator accept, no owner walkthrough by owner decision), `client_environment_builds` (one
`manijeroEnvironment` setting builds local or `Manijero QA` test apps side by side; QA address is a
git-ignored file or placeholder until `qa_server_deployment`), `welcome_first_use` (dismissible
first-use welcome card in the chat, reopened from `Ayuda` with `Ver bienvenida`; validator accept,
no owner walkthrough by owner decision), `answer_pipeline_trace` (off-by-default
local answer trace; question and answer text only in the `development` profile; 7-day purge),
`environment_profiles` (explicit local and QA settings with locally generated, git-ignored access
keys and separate knowledge-release folders; QA is a placeholder template, prod unconfigured),
`backend_container_image` (build,
start, status, and stop commands for the answer service in Docker Desktop; owner walkthrough on the
owner's Mac), `client_pilot_credentials` (build-time
pilot token in test builds only, sent on `/ask` over https or loopback; debug-only revision re-accepted 2026-11-01; owner walkthrough passed), `local_end_to_end_smoke` (one command
that checks Desktop and the Android emulator against the running local service; owner walkthrough on the
owner's Mac), `local_full_rag_stack` (start, stop,
and status commands for the full local service; owner walkthrough on the owner's Mac), `numeric_grounding_check`
(lexical numeric/date/deadline check on drafts; fixtures only), `local_generation_provider` (off by
default; measured on the owner's Mac, host decision pending), `knowledge_reindex_release`
(rehearsed locally only; no host step executed), `local_rag_bootstrap` (one guided setup
command and a status check, walked through on the owner's Mac), `mock_answer_server` (Desktop and
emulator walkthroughs not yet run), and `local_service_connection` (test builds only);
`private_pilot_distribution` is `on_hold` by owner decision (2026-11-01). The 28 `not_started` features are the remaining MasterPlanV3 work, ordered
local environment first, then the QA environment for remote real-device testing; prod is not planned yet. `feature_list.json` and the selector remain the status authority;
this page does not duplicate the feature-id list.

**Product shape** — shared Compose chat, lands, and help surfaces in `shared/src/commonMain`, hosted
by Android and Desktop. Land records stay on-device in the `land-store-v2` aggregate (active and
removed sections), migrated once from `land-store-v1`; removed lands remain local until the user
permanently deletes them.
The local FastAPI service exposes liveness-only `/health`, campaign-plus-corpus readiness at
`/ready`, and `/ask`; the separate `pilot` profile adds per-client bearer authentication,
per-worker rate limiting, a bounded request body, and metadata-only logging. Android and
Desktop use overridable local development URLs; their test builds (never release builds) add a
`Conexión` screen under `Ayuda` to set, remember, and check (`/health`, `/ready`) the service
address. Test builds (Android debug, Desktop `run`; never release or packaged) send a pilot bearer token on `/ask` once the owner saves one
(`client_pilot_credentials`).
The reviewed corpus contains four official sources and four literal passages for three topics
in the Andalusian PAC single application for 2026. Ingestion now runs an offline corpus-security
scan (`corpus_security_rules`): a nominal listing or model-directed document is rejected with a fixed
category and its quarantined bytes and text are deleted, and the canonical release gate refuses a
single identifier shape in metadata, passage text, or location. `/ready` and `/ask` require an explicit
`MANIJERO_ACTIVE_CAMPAIGN`; no hosted model or public deployment is implemented. Scheduled
source scans exist only as a manual-dispatch runner plus disabled, unrehearsed systemd templates
(`knowledge_update_scheduler`); no host runs them and no freshness is claimed. A pinned local `BAAI/bge-m3` artifact and a derived
passage-embedding index now exist, but stay off the default answer path: `/ask` uses the reviewed
BM25 retrieval unless the accepted opt-in Chroma/RRF hybrid mode is configured
(`chroma_hybrid_retrieval`; no answer-level improvement measured). Gated Gemini drafting code exists
(`gemini_generation_provider`) but ships no transport and an all-`null` limits record, so generation
stays extractive; no model has been called. By owner decision (2026-10-31) Gemini is postponed: no
spending for now, and local open-weight generation (`local_generation_provider`) is tried first:
an opt-in, off-by-default `local` provider drafts through loopback Ollama with a pinned
Apache-2.0 model and the same verify-then-extractive fallback; it was measured only on the
owner's Mac in development (numbers in its appendix evidence, no quality claim or host
recommendation), and the pending pilot review keeps it out of the pilot profile.
Reviewed knowledge can now be packaged into immutable, hash-addressed releases that pass structure,
BM25-fingerprint, citation, and no-regression gates before an atomic publish with rollback
(`knowledge_reindex_release`); the service reads them only when the opt-in
`MANIJERO_KNOWLEDGE_RELEASE_ROOT` is set. It was rehearsed only in a local temporary root. `./scripts/init.sh --local-rag-setup`
(`local_rag_bootstrap`) has since built every local artifact and a Chroma-packaged release in
`~/manijero/local` on the owner's Mac only; no release root exists on any host. `./scripts/init.sh
--local-rag-start` / `--local-rag-service-status` / `--local-rag-stop` (`local_full_rag_stack`) run that
full hybrid-plus-local-drafting service on loopback. `./scripts/init.sh --container-build` /
`--container-start` / `--container-status` / `--container-stop` (`backend_container_image`) build and
run the same service as an arm64 Docker Desktop image with the published release and `bge-m3`,
drafting through Ollama on the host via a fixed relay.

**Known limitations (do not over-claim)** — one line each; the exact wording, numbers, and links
are in [`docs/progress/known-limitations.md`](docs/progress/known-limitations.md). Read the full item
before making any claim in its area.

- Answers need the local service and an explicit campaign; legal scope is only the narrow reviewed
  corpus in [`knowledge/pac_coverage.md`](knowledge/pac_coverage.md).
- All answer metrics are report-only: synthetic fixtures plus a 14-case author-reviewed sample with
  visible gaps (14/14 states, 8/11 expected source and passage); no general-accuracy or legal-review claim.
- The question-scope guard is lexical: questions on declared omissions (aid amounts, individual cases,
  reclamaciones) abstain before retrieval, but an unlisted paraphrase can still reach retrieval.
- The 72 screenshot baselines are host-rendered pixel checks, not device, accessibility, usability, or iOS
  evidence; known 2× text wrapping on compact layouts.
- Land-field, search, and summary decisions have no target-user or real-device upgrade evidence.
- Land data is device-local: removal is recoverable, up to three same-device automatic copies, and one plaintext
  export file; losing the device without an export still loses records. Android backup exclusion is
  verified by inspection only; picker, file dialog, and screen-reader flows have no device evidence.
- Pilot privacy gates are closed (review `pending`); retention and redaction are tested locally only.
- Answer feedback (`POST /feedback`) is an anonymous fixed rating with no storage or answer linkage; counts are per process, there is no export or idempotency (a retry counts again), and the pending review does not name feedback yet. The shared chat's `Útil`/`No útil` rating (`answer_feedback_ui`) is in memory only, unlinked, lost on restart, and unavailable against the mock service.
- Source monitoring, document ingestion, change-impact analysis, and reviewed update packages are local,
  manual, synthetic-fixture-backed, and guarantee neither completeness nor currency.
- The procedure map is an unreviewed taxonomy: 16 `proposed` topics, 15 `uncovered`, no owner or
  target-user review; an index, not evidence or a coverage gate.
- Parsed legal-document Markdown is derived review input outside `knowledge/` and never answerable;
  tables and Spanish OCR are verified with in-process fakes and small fixtures only (no measured accuracy).
- Legal chunk sets are derived review input outside `knowledge/`, split only on explicit
  article/chapter/annex lines (títulos, secciones, and disposiciones stay inside their chunk), with
  validity only from the reviewed catalog; never answerable, no accuracy claimed.
- Corpus security exclusion (nominal listings, personal identifiers, model-directed text) is a
  conservative Spanish-first heuristic with no override; it can miss a reworded listing or instruction,
  and a false positive removes that document from automation.
- The test-build `Conexión` screen has unit, guard, compile, and screenshot evidence only; no GUI run.
- The full local service (start/stop/status) is walked through on the owner's Mac only, with no app question sent; status shows configuration, not per-answer use.
- The answer service container is walked through on the owner's Apple-silicon Mac only (no app question sent); arm64 only, about 5.6 GB per image, never pruned.
- The local smoke test (`--local-smoke`) passed once on the owner's Mac (offscreen Desktop, API 37 emulator); it proves reach and rendering, not answer quality, and lands kept could not be observed (no lands existed on the emulator).
- Environment profiles: QA has only a placeholder template and empty release folder, prod is unconfigured, and the local service does not enforce local access keys; tested in temporary homes only.
- Hosted operations are prepared but not deployed; no host, domain, tunnel, or release artifacts exist.
- QA test builds exist (`--android-qa`, `--desktop-qa`) but point at a placeholder address until `qa_server_deployment`; no QA build has run on a device.
- Only test builds carry the pilot token (release and packaged apps cannot reach a pilot service); it is extractable from a test build; token auth is tested against an in-process fake only, with no live pilot-profile answer observed.
- The mock answer service serves fixed contract examples only (not real or legal answers), on loopback for Desktop and the Android emulator.
- Local `bge-m3` embeddings and Chroma hybrid retrieval are off the default answer path; measured
  on the development Mac only, with no answer-level improvement over BM25.
- The numeric-fact draft check is lexical and Spanish-only, rejects some correct paraphrases (ranges,
  an added year), and its effect on live local drafts is not measured.
- The answer trace is off by default and local-only tested; old traces are purged only while the service runs.
- The answer inspector shows only in test builds talking to a loopback service in the `development` profile; a real device on a LAN address never shows it, and no GUI run was done.
- Health metrics (`GET /metrics`) are per-process counts that reset on restart; source-update recency shows only when its state folder is set; in-process tests only.

**Detail on demand**

- [`docs/progress/current-state.md`](docs/progress/current-state.md) — short product narrative and evidence boundaries.
- [`docs/progress/known-limitations.md`](docs/progress/known-limitations.md) — full text of every known limitation.
- [`docs/progress/session-log.md`](docs/progress/session-log.md) — chronological pointer index; one line per event, never repeated verification.
- [`docs/specs/<feature-id>.md`](docs/specs/) — behavior and focused verification; the sibling appendix holds planning and implementation evidence.
- [`docs/validations/<feature-id>.md`](docs/validations/) — acceptance evidence and limits.
- [`docs/risks-and-open-questions.md`](docs/risks-and-open-questions.md) — unresolved risks and decisions.

## Start and verify

Tiers, cheapest first; `./scripts/init.sh` holds the exact commands.

- Toolchain check: `./scripts/init.sh` (default; prints the same commands).
- Run a feature: `./scripts/feature-session.sh [--agent claude|codex|opencode] [feature-id]` opens a new agent session that runs `feature-flow` for that one feature (default: Claude Code and the next feature). One session per feature.
- Next feature: `./scripts/select-feature.sh --next` — the next dependency-ready feature id and its next role; `./scripts/select-feature.sh --status` prints the board and unfinished-feature readiness. Use these instead of reading `feature_list.json` by hand.
- Focused feature check: `./scripts/init.sh --feature <feature-id>` — runs the command block the feature spec publishes between its `<!-- verify:start -->` and `<!-- verify:end -->` markers.
- No-device tier: `./scripts/init.sh --fast` — `:shared:jvmTest`, `contracts/validate_examples.py`, the backend pytest suite, the `source-catalog-v1` validation of `knowledge/source_catalog.json`, and the five offline evaluators over `backend/tests/fixtures/`.
- Full gate: `./scripts/init.sh --verify` (`--full`) — `--fast` plus `:shared:testAndroidHostTest`, `:androidApp:assembleDebug`, and `:desktopApp:build`.
- Backend unit tests alone: `./scripts/init.sh --backend-tests [targets]` — needs pytest; with none available, `--fast` prints the virtualenv recipe, skips the suite locally, and fails under `CI`.
- Backend Python (3.10+): `./scripts/init.sh --setup-python` builds the shared environment once per requirements change and links it as `backend/.venv` in every checkout and worktree. Start the local API: `./scripts/init.sh --backend` (links that environment if needed and launches Uvicorn). Android build: `./scripts/init.sh --android`; build, boot an emulator if needed, install, and launch: `./scripts/init.sh --android-run` (uses the first configured AVD when none is running). Launch Desktop: `./scripts/init.sh --desktop`.
- Local smoke test (owner, needs `--local-rag-start` and a booted emulator): `./scripts/init.sh --local-smoke` prints one `PASS`/`FAIL` line for Desktop and the Android emulator, then a `Result:` line; steps in [`docs/owner-guide.md`](docs/owner-guide.md).
- Mock answer service (no Python): `./scripts/init.sh --mock` starts it in the background on the apps' default address and prints it, `--mock-status` reports it, `--mock-stop` stops it; owner steps in [`docs/owner-guide.md`](docs/owner-guide.md).
- Output is compact: one line per passing check and the tail of a failing log; full logs stay in `build/verify-logs/` (`MANIJERO_VERBOSE=1` prints them inline, `MANIJERO_FAIL_TAIL=<n>` sets the tail length).
- The offline checks pin `--as-of 2026-10-13` so runs are deterministic; override with `MANIJERO_AS_OF=YYYY-MM-DD`.

Evaluator flags, report-only caveats, and a feature's own commands live in its spec; the metrics stay report-only (see the limitations above).
