# Project Progress

## Current state

Routine entry point. Exact feature status lives in [`feature_list.json`](feature_list.json); use
[`./scripts/select-feature.sh --status`](scripts/select-feature.sh) to read the board. Feature
contracts, raw evidence, and acceptance records remain in their owning files. Last updated:
2026-10-31.

**Feature status** — 68 of 120 features are accepted, including `local_generation_provider` (off by
default; measured on the owner's Mac, host decision pending) and `knowledge_reindex_release`
(rehearsed locally only; no host step executed); `private_pilot_distribution` is `on_hold` by owner
decision (2026-11-01). The 51 `not_started` features are the remaining MasterPlanV3 work, ordered
local environment first, then the QA environment for remote real-device testing; prod is not planned yet. `feature_list.json` and the selector remain the status authority;
this page does not duplicate the feature-id list.

**Product shape** — shared Compose chat, lands, and help surfaces in `shared/src/commonMain`, hosted
by Android and Desktop. Land records stay on-device in the `land-store-v2` aggregate (active and
removed sections), migrated once from `land-store-v1`; removed lands remain local until the user
permanently deletes them.
The local FastAPI service exposes liveness-only `/health`, campaign-plus-corpus readiness at
`/ready`, and `/ask`; the separate `pilot` profile adds per-client bearer authentication,
per-worker rate limiting, a bounded request body, and metadata-only logging. Android and
Desktop use overridable local development URLs; no client can send a pilot bearer token yet.
The reviewed corpus contains four official sources and four literal passages for three topics
in the Andalusian PAC single application for 2026. `/ready` and `/ask` require an explicit
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
`MANIJERO_KNOWLEDGE_RELEASE_ROOT` is set. It was rehearsed only in a local temporary root; the
Chroma packaging path is untested and no release root exists on any host.

**Known limitations (do not over-claim)** — one line each; the exact wording, numbers, and links
are in [`docs/progress/known-limitations.md`](docs/progress/known-limitations.md). Read the full item
before making any claim in its area.

- Answers need the local service and an explicit campaign; legal scope is only the narrow reviewed
  corpus in [`knowledge/pac_coverage.md`](knowledge/pac_coverage.md).
- All answer metrics are report-only: synthetic fixtures plus a 14-case author-reviewed sample with
  visible gaps (13/14 states, 8/11 expected source and passage); no general-accuracy or legal-review claim.
- The 72 screenshot baselines are host-rendered pixel checks, not device, accessibility, usability, or iOS
  evidence; known 2× text wrapping on compact layouts.
- Land-field, search, and summary decisions have no target-user or real-device upgrade evidence.
- Land data is device-local: removal is recoverable, up to three same-device automatic copies, and one plaintext
  export file; losing the device without an export still loses records. Android backup exclusion is
  verified by inspection only; picker, file dialog, and screen-reader flows have no device evidence.
- Pilot privacy gates are closed (review `pending`); retention and redaction are tested locally only.
- Source monitoring, document ingestion, change-impact analysis, and reviewed update packages are local,
  manual, synthetic-fixture-backed, and guarantee neither completeness nor currency.
- Hosted operations are prepared but not deployed; no host, domain, tunnel, or release artifacts exist.
- Local `bge-m3` embeddings and Chroma hybrid retrieval are off the default answer path; measured
  on the development Mac only, with no answer-level improvement over BM25.

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
- Output is compact: one line per passing check and the tail of a failing log; full logs stay in `build/verify-logs/` (`MANIJERO_VERBOSE=1` prints them inline, `MANIJERO_FAIL_TAIL=<n>` sets the tail length).
- The offline checks pin `--as-of 2026-10-13` so runs are deterministic; override with `MANIJERO_AS_OF=YYYY-MM-DD`.

Evaluator flags, report-only caveats, and a feature's own commands live in its spec; the metrics stay report-only (see the limitations above).
