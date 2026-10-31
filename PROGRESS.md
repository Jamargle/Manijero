# Project Progress

## Current state

Routine entry point. Exact feature status lives in [`feature_list.json`](feature_list.json); use
[`./scripts/select-feature.sh --status`](scripts/select-feature.sh) to read the board. Feature
contracts, raw evidence, and acceptance records remain in their owning files. Last updated:
2026-10-31.

**Feature status** — 68 of 69 features are accepted, including `local_generation_provider` (off by
default; measured on the owner's Mac, host decision pending) and `knowledge_reindex_release`
(rehearsed locally only; no host step executed); `private_pilot_distribution` is `not_started`. `feature_list.json` and the selector remain the status authority;
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

**Known limitations (do not over-claim)**

- Apps need a reachable local service and valid campaign configuration to answer. Without them,
  they show the plain-Spanish failure notice and `Reintentar`. The supported legal scope is the
  narrow reviewed corpus in [`knowledge/pac_coverage.md`](knowledge/pac_coverage.md).
- Offline retrieval, generation, abstention, clarification, and safety metrics use synthetic
  fixtures and are report-only. The reviewed `/ask` evaluation is a 14-case sample over the three
  approved topics and five boundaries, reviewed only by the project author. Its exact result is
  13/14 expected states, 11/11 expected-answer cases answered, 8/11 with the expected source and
  passage, 9/11 with the expected critical literal, and 2/3 expected abstentions. Known gaps stay
  visible in [`knowledge/pac_coverage.md`](knowledge/pac_coverage.md): `canal-sga-2026`,
  `fecha-modificacion-2026`, and `distingue-fechas-2026` cite a different reviewed passage, and
  `reclamacion-fuera-de-alcance` answers an out-of-scope reclamación. Neither that sample nor the
  fixture metrics are independent legal review or evidence of general accuracy.
- The 72 screenshot baselines (38 Desktop, 34 Android) are local host-rendered pixel checks, not
  device, accessibility, usability, or iOS evidence. The procedure and limits are in
  [`docs/screenshot-regression.md`](docs/screenshot-regression.md). At 2× text, compact navigation
  labels wrap mid-word; on the compact chat screen, `Preguntar` may need a short scroll.
- The required zone, variety shortlist, search scope, and annotated summary wording are approved
  product decisions without target-user evidence. Land-field persistence has no real-device
  upgrade/downgrade evidence; details stay in the [field validation](docs/validations/land_measurement_fields.md)
  and [search validation](docs/validations/land_search_and_summary.md).
- Device-local land records can be exported to, and restored from, one plaintext portable file
  (`Mis terrenos` → `Copia en un archivo`, replace-all after a preview); see the
  [acceptance record](docs/validations/portable_land_backup.md). Removing a
  land is recoverable on the device until the user confirms `Borrar para siempre`; the app also keeps up to
  three bounded same-device automatic copies of the whole aggregate and recovers a damaged primary from the
  newest fully valid one. Those copies live in the same app data area, so without an exported file, losing the device or
  uninstalling the app still loses the records; permanent deletion purges the aggregate and every app-managed copy. The
  product direction is local-only storage with required recovery features before the private pilot; this is
  not user evidence that data loss is acceptable. See the
  [decision record](docs/specs/land_backup_decision.md), the
  [removal acceptance record](docs/validations/recover_removed_lands.md), and the
  [automatic-copy evidence](docs/specs/local_land_auto_backup.appendix.md). The shipped privacy
  statement that there is no copy on the internet or on another device is now backed on Android: the
  host manifest excludes the land preferences from Auto Backup and device transfer.
- That Android exclusion is verified by manifest, rule-file, and packaged-APK inspection only, not by
  an emulator or device backup round-trip; OEM backup behaviour and OS/disk-level copies outside the
  app remain unverified.
- Recoverable removal, bounded same-device automatic copies, and the portable plaintext backup file are
  accepted. The backup file has no real-device SAF picker, real macOS `FileDialog`, or physical
  Android-to-Mac transfer evidence; it is unencrypted and its copies are the person's responsibility. The removed-list screens have no device or screen-reader evidence, the
  automatic-copy recovery notice has host-rendered light/dark goldens at two viewports but no device
  interaction or screen-reader evidence, and `removedAt` is stored as 0 in production because no clock is
  injected. A qualified privacy/legal review is also required before the private pilot.
- Pilot privacy gates are implemented but **closed**: `backend/config/pilot_privacy_review.json` is
  `pending`, so `pilot_ops.py privacy-gate` and the pilot preflight block and Gemini stays disabled.
  Per-question, default-off redacted Q/A retention (deleted within 30 days) is tested locally only; redaction
  is pattern-based on synthetic text. No qualified review, participant privacy/incident contact, or
  per-person early deletion exists yet. See [`docs/pilot-privacy.md`](docs/pilot-privacy.md) and the
  [acceptance record](docs/validations/pilot_privacy_readiness.md).
- The manual official-feed monitor records response hashes and validators separately from canonical knowledge. BOE/BOJA manual discovery now writes pending candidates into separate review state; FEGA/MAPA registries remain explicitly unchecked, BOJA is configured per bulletin, and no completeness is guaranteed. Document-level ingestion now fetches allowlisted pending candidates into a separate quarantine with preserved original/extracted hashes and page/section text, follows only bounded HTTPS redirects within the same issuer's approved hosts, and does not use monitoring feeds as document candidates. Human-reviewed update packages can now prepare a local draft and provide a controlled merge that verifies recorded approval; scheduled dispatch, hosting-platform PR/merge-protection integration, reproducible index rebuilds, and release automation are not implemented. New issuers, hosts, and answerable knowledge must remain human-approved; successful polling does not prove corpus currency.
- Quarantined document extraction is standard-library PDF/HTML text extraction without OCR. It decodes embedded-font `ToUnicode` maps when present, but incomplete subset-font maps can leave `U+FFFD` placeholders or omit glyphs, and scanned, encrypted, or unsupported-filter PDFs fail closed. Live smoke checks parsed BOE and BOJA PDFs; the BOJA sample retained about 6.3% replacement characters, so extraction accuracy is not a general guarantee and a reviewer must compare both copies. Nothing extracted becomes answerable without later human review; no legal-coverage claim follows.
- Document ingestion keeps `page_count` as the number of pages that yielded text (not total pages), keeps each original-bytes version without garbage collection (re-extracting unchanged bytes replaces the previous extracted text), and assumes a single writer for each state/quarantine pair. It also depends on discovery metadata: `version_hash` covers only title and URL, so a changed file behind an unchanged URL is not detected without a re-fetch, and an extractor upgrade re-fetches rather than reprocessing stored text.
- Legal change-impact analysis is read-only and wording-based: it reads the ingestion state and quarantine and writes only a report file outside `knowledge/`. It detects explicit publication, amendment, repeal and validity wording, classifies machine-evident text apart from wording that needs legal interpretation, and links candidates to approved sources, passages and evaluation cases by instrument identity (only a title that starts with a numbered instrument is the candidate's own identity; otherwise every named instrument is a target) and document identity. It never retires, replaces or re-approves a source, and any ambiguous publication/amendment/repeal/validity signal — negated wording included, and a signal linked only to a reviewed passage or case — makes its candidate review-required even when it links no approved source. Broad word-stem triggers mean static document wording can yield ambiguous signals, so review-required may be near-universal; negation recognition covers only the listed phrasings; and a failed or rejected ingestion leaves the CLI exit `0`. Some gaps do not raise the review gate on their own: a change with no explicit signal (including a static deadline sentence without change wording), an unknown baseline that links no approved source, passage, or case, and a failed or rejected ingestion (reported as `analysis_failure: no_extracted_document`, owned by the ingestion state). A missed change therefore stays possible; only synthetic fixtures back it, there is no live run against published amendments, and detection precision/recall is not measured. See the [feature appendix](docs/specs/legal_change_impact_analysis.appendix.md).
- Human-reviewed knowledge update packages are local and offline: `prepare` and `decide` write only under an operator workspace, and `merge` writes the canonical catalog/passages only after a named requested human other than the author approves and every required check still passes. It is not a hosted pull request and does not configure hosting-provider merge protection, so anyone with filesystem access can still bypass it; reviewer identities and decisions are plain local records, not authenticated signatures, and the commands only refuse known automation/CI names. Merge revalidates as of the approval date, refuses canonical drift, and never reindexes or releases. A proposal that changes the reviewed corpus now requires the reviewed evaluation case set: preparation validates the after-state and blocks readiness for orphaned cases, and merge requires the same digest-bound case file and revalidates it. A removal without a case set is blocked; a no-op package is allowed. Merge preserves the field order of entries the proposal does not rewrite, so a no-op merge is byte-identical and a real change touches only changed entries; a newly added or rewritten entry follows the proposal's own serialization. Unknown validity/applicability stays absent, unsafe URLs and missing provenance/extraction block readiness, affected and rewritten evaluation cases are report-only rather than re-run, original-byte comparison is unavailable when the quarantine copy is gone, review display is bounded, and review evidence is not garbage-collected. Merge writes the two canonical files sequentially, so a crash between writes can leave an inconsistent pair that must be restored from Git. Only synthetic fixtures exercise the flow; no real published update has been reviewed, and approval is not legal-completeness or answer-quality certification. See the [feature appendix](docs/specs/knowledge_update_review_pr.appendix.md).
- Official-source discovery corrected the earlier invalid blocker conclusion: the BOE HTTP 400 resulted from the missing `Accept` header; the documented response succeeds with an explicit XML/JSON Accept type. See the feature appendix for endpoints, tests, and the local TLS smoke limitation.
- Private hosted operations are prepared but **not deployed**, and distribution is not
  configured. The 2026-10-27 [hosting decision](docs/specs/hosting_provider_review.md)
  conditionally selects Cloudflare Tunnel as transport for an owned server and R2
  presigned links as the artifact candidate, but the owned-server path stays blocked until
  the owner attests hardware, connectivity, power/backup, maintenance window, capacity, and
  recovery. Fly.io is the only evaluated fallback and is not approved. A separate
  pilot-profile launcher now refuses reload/development mode, validates campaign and corpus
  before traffic, requires per-client bearer tokens (digests only), applies per-client
  per-worker limits and a request-body bound, exposes liveness and readiness separately,
  writes one request-metadata line with no question or land values, and ships preflight,
  hashed backup, verified restore, and smoke commands plus service/tunnel templates. Those
  gates and the corpus restore rehearsal are local evidence only: no host, domain, tunnel,
  TLS edge, provider account, external monitoring, or measured capacity exists, the client
  cannot yet send a token, and Android/macOS release artifacts are not implemented. The
  first-deploy credential ownership path, the stop/restore/start sequence, and the
  service-readable `0644` restore mode are repaired and exercised locally, but not on a
  host or through systemd.
- Local embeddings are implemented but **off the answer path**: a pinned `BAAI/bge-m3` revision
  (`5617a9f…`, MIT), per-file SHA-256 verification, a derived `passage-embedding-index-v1` file
  outside `knowledge/`, and a rebuild/staleness check. Only this development Mac (Apple M1 Max,
  32 GiB, CPU `float32`, 8 threads) was measured: a 2,293,315,747-byte artifact, a 928 MB optional
  runtime, 1,943 MB peak RSS, about 77 ms for a two-text probe, `0.0` repeated-run difference, and a
  0.621 s index rebuild over the four approved passages. That is not owned-server capacity, not a
  per-passage latency budget, and not a BM25 comparison. The BM25 vs hybrid comparison is
  recorded in the [`chroma_hybrid_retrieval` appendix](docs/specs/chroma_hybrid_retrieval.appendix.md):
  identical answer metrics on the 14-case sample, so BM25 remains the default. The model is CPU-only, `torch`/`transformers` stay optional, the
  artifact is not committed, and the operator owns its storage and backup. No Spanish legal
  retrieval, answer-quality, or license-review claim follows. See the
  [feature appendix](docs/specs/local_bge_m3_embeddings.appendix.md).
- The answer evidence expansion now covers 14 cases and the three approved topics plus five
  boundaries, but review is author-only. Four case-level gaps remain visible in the report; three
  are the earlier citation/critical-fact misses and one is a newly measured out-of-scope
  reclamación answer. No answer-quality, legal-correctness, or independent-review claim is
  supported.

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
- Backend Python (3.10+): `./scripts/init.sh --setup-python` builds the shared environment once per requirements change and links it as `backend/.venv` in every checkout and worktree. Start the local API: `./scripts/init.sh --backend` (links that environment if needed and launches Uvicorn). Android build: `./scripts/init.sh --android`; build, boot an emulator if needed, install, and launch: `./scripts/init.sh --android-run` (uses the first configured AVD when none is running). Launch Desktop: `./scripts/init.sh --desktop`.
- The offline checks pin `--as-of 2026-10-13` so runs are deterministic; override with `MANIJERO_AS_OF=YYYY-MM-DD`.

Evaluator flags, report-only caveats, and a feature's own commands live in its spec; the metrics stay report-only (see the limitations above).
