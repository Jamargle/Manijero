# Known limitations — full text

Moved verbatim from `PROGRESS.md` "Current state" on 2026-10-31 so the routine entry point stays
short. [`PROGRESS.md`](../../PROGRESS.md) keeps a one-line digest of each item; this file holds the
exact wording and links. Read it before writing any user-facing or acceptance claim in an area
listed here, and update the matching item (and its digest line) when a feature changes a limit.
Do not over-claim.

- Apps need a reachable local service and valid campaign configuration to answer. Without them,
  they show the plain-Spanish failure notice and `Reintentar`. The supported legal scope is the
  narrow reviewed corpus in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md).
- Offline retrieval, generation, abstention, clarification, and safety metrics use synthetic
  fixtures and are report-only. The reviewed `/ask` evaluation is a 17-case sample over the three
  approved topics and eight boundaries, reviewed only by the project author. Its exact result is
  17/17 expected states, 12/12 expected-answer cases answered, 9/12 with the expected source and
  passage, 10/12 with the expected critical literal, and 5/5 expected abstentions with 0 unexpected answers. Known gaps stay
  visible in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md): `canal-sga-2026`,
  `fecha-modificacion-2026`, and `distingue-fechas-2026` cite a different reviewed passage. Neither that sample nor the
  fixture metrics are independent legal review or evidence of general accuracy.
- **The question-scope guard is lexical** ([`question_scope_guard`](../specs/question_scope_guard.md)).
  Questions matching a declared omission of `knowledge/pac_coverage.md` (aid amounts, individual
  eligibility, individual notifications, reclamaciones, late-filing penalties, fuerza mayor,
  monitoring adaptations, other campaigns) abstain before retrieval, which fixed the
  `tema-no-cubierto` and `reclamacion-fuera-de-alcance` regressions. The list is a code-owned set of
  patterns in `backend/app/question_scope.py`, so an unlisted paraphrase of an omitted topic can still
  reach retrieval and be answered with a nearby passage. Trial evidence, not merged: matching Spanish
  singular/plural forms in `retrieval.py` made the draft case `rectificacion-errores-2026`
  (“¿Puede la Administración corregir un error material en un acto?”) answer, but also broke
  `plazo-modificacion-parcelas-2026`. The guard already covers its other two side effects
  (`tema-no-cubierto` and the individual-notification boundary); retry it only with that ranking break
  fixed.
- The numeric-fact check in `verify_draft` ([`numeric_grounding_check`](../specs/numeric_grounding_check.md))
  is lexical and Spanish-only, not entailment: it rejects some correct paraphrases (ranges, an
  added year), checks only day/week/month/year durations and `por ciento`, and its effect on the
  local model's verified-draft rate is unmeasured.
- The 72 screenshot baselines (38 Desktop, 34 Android) are local host-rendered pixel checks, not
  device, accessibility, usability, or iOS evidence. The procedure and limits are in
  [`docs/screenshot-regression.md`](../screenshot-regression.md). At 2× text, compact navigation
  labels wrap mid-word; on the compact chat screen, `Preguntar` may need a short scroll.
- The required zone, variety shortlist, search scope, and annotated summary wording are approved
  product decisions without target-user evidence. Land-field persistence has no real-device
  upgrade/downgrade evidence; details stay in the [field validation](../validations/land_measurement_fields.md)
  and [search validation](../validations/land_search_and_summary.md).
- Device-local land records can be exported to, and restored from, one plaintext portable file
  (`Ajustes` → `Copia en un archivo`, replace-all after a preview); see the
  [acceptance record](../validations/portable_land_backup.md). Removing a
  land is recoverable on the device until the user confirms `Borrar para siempre`; the app also keeps up to
  three bounded same-device automatic copies of the whole aggregate and recovers a damaged primary from the
  newest fully valid one. Those copies live in the same app data area, so without an exported file, losing the device or
  uninstalling the app still loses the records; permanent deletion purges the aggregate and every app-managed copy. The
  product direction is local-only storage with required recovery features before the private pilot; this is
  not user evidence that data loss is acceptable. See the
  [decision record](../specs/land_backup_decision.md), the
  [removal acceptance record](../validations/recover_removed_lands.md), and the
  [automatic-copy evidence](../archive/specs/local_land_auto_backup.appendix.md). The shipped privacy
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
  Default-off, opt-in (`Ayúdanos a mejorar`, a standing choice since 2026-11-08) redacted Q/A retention (deleted within 30 days) is tested locally only; redaction
  is pattern-based on synthetic text. No qualified review, participant privacy/incident contact, or
  per-person early deletion exists yet. See [`docs/pilot-privacy.md`](../pilot-privacy.md) and the
  [acceptance record](../validations/pilot_privacy_readiness.md).
- Answer feedback ([`feedback_endpoint`](../specs/feedback_endpoint.md)) is an anonymous, unlinked fixed
  rating (`useful`/`not_useful`) on `POST /feedback`: the service keeps only a per-process count by
  rating, stores no feedback record, and accepts no question, answer, land, client/device identifier,
  answer id, or free text. There is no durable feedback store, export, dashboard, per-answer linkage, or
  idempotency (a retry after an unknown outcome counts again), and the review record — still `pending` —
  does not yet cover feedback. Do not claim tracked satisfaction, per-person feedback, or reviewed
  feedback handling. The shared chat's `Útil`/`No útil` row
  ([`answer_feedback_ui`](../specs/answer_feedback_ui.md)) keeps the rating only in memory with the
  transcript: it is unlinked, unpersisted, forgotten on restart, and counted per process, and the
  test-only mock answer service has no `/feedback`, so a rating against a mock-backed build shows the
  retry line instead of pretending to be counted.
- The manual official-feed monitor records response hashes and validators separately from canonical knowledge. BOE/BOJA manual discovery now writes pending candidates into separate review state; FEGA/MAPA registries remain explicitly unchecked, BOJA is configured per bulletin, and no completeness is guaranteed. Document-level ingestion now fetches allowlisted pending candidates into a separate quarantine with preserved original/extracted hashes and page/section text, follows only bounded HTTPS redirects within the same issuer's approved hosts, and does not use monitoring feeds as document candidates. Human-reviewed update packages can now prepare a local draft and provide a controlled merge that verifies recorded approval; scheduled dispatch, hosting-platform PR/merge-protection integration, reproducible index rebuilds, and release automation are not implemented. New issuers, hosts, and answerable knowledge must remain human-approved; successful polling does not prove corpus currency.
- The olive-grove procedure map is an unreviewed hypothesis list: all 16 seed topics are `proposed` with no owner or target-user review, and only the PAC topic declares `partial` reviewed evidence while the other 15 are `uncovered`. It is a taxonomy index, never legal knowledge, an answer source, or a coverage gate, and it does not change the pinned coverage disclosure. Adding or retiring a topic, or marking one `reviewed`, requires a reviewed change with a named human reviewer. See [the spec](../specs/domain_procedure_map.md).
- Quarantined document extraction is standard-library PDF/HTML text extraction without OCR. It decodes embedded-font `ToUnicode` maps when present, but incomplete subset-font maps can leave `U+FFFD` placeholders or omit glyphs, and scanned, encrypted, or unsupported-filter PDFs fail closed. Live smoke checks parsed BOE and BOJA PDFs; the BOJA sample retained about 6.3% replacement characters, so extraction accuracy is not a general guarantee and a reviewer must compare both copies. Nothing extracted becomes answerable without later human review; no legal-coverage claim follows.
- Document ingestion keeps `page_count` as the number of pages that yielded text (not total pages), keeps each original-bytes version without garbage collection (re-extracting unchanged bytes replaces the previous extracted text), and assumes a single writer for each state/quarantine pair. It also depends on discovery metadata: `version_hash` covers only title and URL, so a file that changed behind an unchanged URL is not detected without a re-fetch, and an extractor upgrade re-fetches rather than reprocessing stored text. A candidate recorded with a security exclusion is not refetched while its version hash is unchanged.
- Corpus security exclusion ([`corpus_security_rules`](../specs/corpus_security_rules.md)) is a conservative heuristic, not a classifier or a completeness claim: `nominal_listing` keys on listing nouns near a people role in a title or heading, or on two DNI/NIE/affiliation-number shapes counted across the whole extracted document (so one DNI per table row still adds up); the canonical release gate is stricter and rejects any single identifier shape in catalog metadata, passage text, or location. `prompt_injection` keys on Spanish/English directives addressed to a model, role reassignment, and fake role tags. It can miss a reworded listing or a novel instruction, it does not judge legal meaning, and a false positive removes an official document from automation with no override flag — a person who believes the exclusion is wrong uses the normal human-reviewed corpus update. Listing rows, names, and identifiers are never retained, only the official title, URLs, identity, hashes, and a bounded content-free scan record. `verify_draft` still discards an unsupported draft whole, so an undetected instruction in a fragment cannot justify a figure or date the fragment does not contain.
- Legal change-impact analysis is read-only and wording-based: it reads the ingestion state and quarantine and writes only a report file outside `knowledge/`. It detects explicit publication, amendment, repeal and validity wording, classifies machine-evident text apart from wording that needs legal interpretation, and links candidates to approved sources, passages and evaluation cases by instrument identity (only a title that starts with a numbered instrument is the candidate's own identity; otherwise every named instrument is a target) and document identity. It never retires, replaces or re-approves a source, and any ambiguous publication/amendment/repeal/validity signal — negated wording included, and a signal linked only to a reviewed passage or case — makes its candidate review-required even when it links no approved source. Broad word-stem triggers mean static document wording can yield ambiguous signals, so review-required may be near-universal; negation recognition covers only the listed phrasings; and a failed or rejected ingestion leaves the CLI exit `0`. Some gaps do not raise the review gate on their own: a change with no explicit signal (including a static deadline sentence without change wording), an unknown baseline that links no approved source, passage, or case, and a failed or rejected ingestion (reported as `analysis_failure: no_extracted_document`, owned by the ingestion state). A missed change therefore stays possible; only synthetic fixtures back it, there is no live run against published amendments, and detection precision/recall is not measured. See the [feature appendix](../archive/specs/legal_change_impact_analysis.appendix.md).
- Human-reviewed knowledge update packages are local and offline: `prepare` and `decide` write only under an operator workspace, and `merge` writes the canonical catalog/passages only after a named requested human other than the author approves and every required check still passes. It is not a hosted pull request and does not configure hosting-provider merge protection, so anyone with filesystem access can still bypass it; reviewer identities and decisions are plain local records, not authenticated signatures, and the commands only refuse known automation/CI names. Merge revalidates as of the approval date, refuses canonical drift, and never reindexes or releases. A proposal that changes the reviewed corpus now requires the reviewed evaluation case set: preparation validates the after-state and blocks readiness for orphaned cases, and merge requires the same digest-bound case file and revalidates it. A removal without a case set is blocked; a no-op package is allowed. Merge preserves the field order of entries the proposal does not rewrite, so a no-op merge is byte-identical and a real change touches only changed entries; a newly added or rewritten entry follows the proposal's own serialization. Unknown validity/applicability stays absent, unsafe URLs and missing provenance/extraction block readiness, affected and rewritten evaluation cases are report-only rather than re-run, original-byte comparison is unavailable when the quarantine copy is gone, review display is bounded, and review evidence is not garbage-collected. Merge writes the two canonical files sequentially, so a crash between writes can leave an inconsistent pair that must be restored from Git. Only synthetic fixtures exercise the flow; no real published update has been reviewed, and approval is not legal-completeness or answer-quality certification. See the [feature appendix](../archive/specs/knowledge_update_review_pr.appendix.md).
- Official-source discovery corrected the earlier invalid blocker conclusion: the BOE HTTP 400 resulted from the missing `Accept` header; the documented response succeeds with an explicit XML/JSON Accept type. See the feature appendix for endpoints, tests, and the local TLS smoke limitation.
- Private hosted operations are prepared but **not deployed**, and distribution is not
  configured. The 2026-10-27 [hosting decision](../specs/hosting_provider_review.md)
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
  TLS edge, provider account, external monitoring, or measured capacity exists, and
  Android/macOS release artifacts are not implemented. The
  first-deploy credential ownership path, the stop/restore/start sequence, and the
  service-readable `0644` restore mode are repaired and exercised locally, but not on a
  host or through systemd.
- Only test builds (Android debug, Desktop `run`) can carry a pilot bearer token saved with
  `./scripts/init.sh --pilot-token-save` ([`client_pilot_credentials`](../specs/client_pilot_credentials.md)).
  Release and packaged apps never carry it, so they cannot reach a pilot-profile service until a
  release credential path exists (a later decision). In a test
  build the token is built in, so anyone holding that build can extract it: it gates access per
  client and is revocable, but it is not secret from the device holder. A local test build gets
  the saved `pilot-token.local` token and a QA test build the QA access key, it is sent only over
  `https` or to a loopback address, and the auth flow is tested only against an in-process
  fake of the pilot guard. No app has yet been observed getting a live answer from a
  pilot-profile service, because no named command starts one locally.
- QA test builds (`./scripts/init.sh --android-qa`, `--desktop-qa`,
  [`client_environment_builds`](../specs/client_environment_builds.md)) point at the placeholder
  `https://qa.manijero.invalid` until `qa_server_deployment` chooses a host (then the address goes
  in the git-ignored `qa-address.local`). No QA build has been installed or run on a device.
- Local embeddings are implemented but **off the answer path**: a pinned `BAAI/bge-m3` revision
  (`5617a9f…`, MIT), per-file SHA-256 verification, a derived `passage-embedding-index-v1` file
  outside `knowledge/`, and a rebuild/staleness check. Only this development Mac (Apple M1 Max,
  32 GiB, CPU `float32`, 8 threads) was measured: a 2,293,315,747-byte artifact, a 928 MB optional
  runtime, 1,943 MB peak RSS, about 77 ms for a two-text probe, `0.0` repeated-run difference, and a
  0.621 s index rebuild over the four approved passages. That is not owned-server capacity, not a
  per-passage latency budget, and not a BM25 comparison. The BM25 vs hybrid comparison is
  recorded in the [`chroma_hybrid_retrieval` appendix](../archive/specs/chroma_hybrid_retrieval.appendix.md):
  identical answer metrics on the 14-case sample, so BM25 remains the default. The model is CPU-only, `torch`/`transformers` stay optional, the
  artifact is not committed, and the operator owns its storage and backup. No Spanish legal
  retrieval, answer-quality, or license-review claim follows. See the
  [feature appendix](../archive/specs/local_bge_m3_embeddings.appendix.md).
- The answer evidence expansion now covers 14 cases and the three approved topics plus five
  boundaries, but review is author-only. Four case-level gaps remain visible in the report; three
  are the earlier citation/critical-fact misses and one is a newly measured out-of-scope
  reclamación answer. No answer-quality, legal-correctness, or independent-review claim is
  supported.
- The mock answer service (`./scripts/init.sh --mock`) serves only the fixed contract example
  responses, chosen by request shape; they are not real or legal answers and say nothing about
  answer quality. It listens on `127.0.0.1` only, so it serves Desktop and the Android emulator,
  not physical devices or other machines. See the
  [`mock_answer_server`](../specs/mock_answer_server.md) contract.
- The `Conexión` test-build screen (`local_service_connection`) is verified by unit, guard, compile,
  and `Ayuda` screenshot checks only. Typing an address, `Comprobar` against a running, stopped, or
  not-ready service, and the remembered address after restart were not exercised in the Desktop or
  emulator GUI, and the packaged Desktop app was not opened to confirm the card is absent. See the
  [acceptance record](../validations/local_service_connection.md).
- The full local answer service (`./scripts/init.sh --local-rag-start`, `local_full_rag_stack`) was
  walked through on the owner's Mac only, without sending an app question. Its status reports the
  start configuration and live probes, not what each answer used; the first question after a start
  may fall back to extractive while Ollama loads the model. Loopback only. See the
  [acceptance record](../validations/local_full_rag_stack.md) and
  [risks](../risks-and-open-questions.md).
- The answer service container (`./scripts/init.sh --container-*`, `backend_container_image`) was
  walked through on the owner's Apple-silicon Mac only (Docker Desktop 4.97.0), without sending an app
  question; automated checks fake Docker. It is built for arm64 only, binds loopback only, drafts
  through Ollama on the host, and each image (about 5.6 GB) is never pruned. See the
  [acceptance record](../validations/backend_container_image.md) and
  [risks](../risks-and-open-questions.md).
- The local smoke test (`./scripts/init.sh --local-smoke`, `local_end_to_end_smoke`) passed once in the
  owner walkthrough, on one Mac and the `Medium_Phone_API_37.0` emulator. "Desktop" is the shared app
  drawn offscreen with the Desktop connection settings, not the real window. A pass proves the apps
  reach the local service and render a grounded answer or an honest abstention; it makes no
  answer-quality or legal-coverage claim. Whether the emulator app keeps its lands could not be
  observed: the emulator had no lands before the run. Physical devices are never used. See the
  [acceptance record](../validations/local_end_to_end_smoke.md).
- The local load test (`./scripts/init.sh --local-rag-load-test`, `local_load_test`) ran once on one Mac
  (10 clients, 3 minutes steady: 1844 answers, none failed, median 0.70 s, p95 1.18 s, 10.2 per
  second; the first requests were much slower while the model loaded). It is host-specific evidence
  only: no pass/fail, capacity, or pilot-readiness claim, and the pilot host is unmeasured. See the
  [acceptance record](../validations/local_load_test.md).
- The answer trace (`MANIJERO_ANSWER_TRACE=on`, `answer_pipeline_trace`) is off by default and tested
  locally only; no hosted trace has been observed. Old traces are purged only while the service runs,
  so a stopped service keeps files older than 7 days until its next start. Text is recorded only when
  the profile is explicitly `development` (stated by the local service start); the container image
  states no profile, so a trace turned on there records no text. See
  the [acceptance record](../validations/answer_pipeline_trace.md).
- The answer inspector (`rag_inspector_view`) appears only in test builds (Android debug, Desktop
  `run`) whose service address is loopback (`localhost`, `127.0.0.1`, `10.0.2.2`), and the service
  sends inspection data only when the profile is explicitly `development` (stated by
  `--local-rag-start`). A real device on a LAN address never shows it; QA and prod never do. Until
  `client_environment_builds` is accepted, "local build" means test tools plus a loopback address.
  Verified by unit, interaction, and screenshot tests only; no GUI or device run. See the
  [acceptance record](../validations/rag_inspector_view.md).
- Environment profiles (`environment_profiles`): only local is complete. QA is a commented template
  with a placeholder `.invalid` host and an empty knowledge-release folder; no QA host is chosen or
  contacted (that belongs to `qa_server_deployment`), and prod is not configured. Local access keys
  are generated but the local service does not check them. Everything was tested in temporary
  folders with fake tokens only. See the [acceptance record](../validations/environment_profiles.md).
- The health metrics page (`GET /metrics`, `backend_health_metrics`) counts per process and resets on restart, so it is never cluster-wide. Source-update recency appears only when `MANIJERO_SOURCE_UPDATE_STATE_DIR` is already set (no start command sets it), and it reports scheduler run recency, not legal freshness. Verified by in-process tests only; no live scrape, dashboard, or hosted service was observed. See the [spec](../specs/backend_health_metrics.md).
- The legal-document parser (`legal_document_parser`) writes derived Markdown plus a provenance
  manifest outside `knowledge/`; nothing it writes is answerable, and no `review_status` changes.
  Its table and Spanish-OCR adapters were verified only with in-process fakes and small
  deterministic fixtures: Docling, `pymupdf4llm`, and the Tesseract `spa` runtime were not
  installed or run on the owner's Mac, so there is no measured table or OCR accuracy. A fully
  scanned PDF is already failed by accepted ingestion as `no_extractable_text` and never reaches
  the parser, so OCR applies only to text-less pages inside an otherwise extracted PDF. See the
  [spec](../specs/legal_document_parser.md).
- The legal chunker (`legal_structure_chunker`) writes derived chunk sets plus a run manifest outside
  `knowledge/`; nothing it writes is answerable and no `review_status` changes. Splitting is a
  conservative Spanish line-shape rule limited to `Artículo`, `Capítulo`, and `Anexo`: `Título`,
  `Sección`, `Disposición`, and `Preámbulo` lines never split, a heading with no text after it emits
  no chunk, and a heading written in another shape is missed rather than guessed. Validity is only as
  reviewed as `knowledge/source_catalog.json` (the `content_sha256` join; unmatched documents stay
  `unknown`), no date is read from document text, and no chunking or retrieval accuracy is claimed.
  See the [spec](../specs/legal_structure_chunker.md).
- The cooperative-notice pipeline (`local_notice_pipeline`) refuses personal-looking notices with a lexical Spanish heuristic: it can miss an unusual name or address, and can refuse a cooperative named after a person or saint or any parcel reference. It was tested only on invented notices with a fake model; no extraction quality was measured, the pinned model was not run on it, and every output is unreviewed. See the [spec](../specs/local_notice_pipeline.md).
- The structured-chunk index (`structured_chunk_index`) is honoured only with `MANIJERO_STRUCTURED_INDEX=on` in local development or QA (never pilot or prod), and then replaces the release or canonical corpus for `/ask` and `/ready`. Review is source level only (the catalog entry's named reviewer plus approval evidence); the chunk text is not separately reviewed. No retrieval or answer-quality comparison was run (no real chunk set is committed), and an extractive answer may quote the `[título · ruta]` prefix. See the [spec](../specs/structured_chunk_index.md).
- The health dashboard (`monitoring_dashboard`, `./scripts/init.sh --monitoring-start`) runs only on the owner's Mac while Docker Desktop is open and is not alerting or outage detection. QA shows "Not set up yet" until `qa_server_deployment` gives a real address; the QA scrape (token file mount) is unverified live. The OK/warning/problem bounds in `backend/monitoring/thresholds.json` are initial planner choices, not measured. The image pins use explicit version tags with null digests until a developer reads them from the registry (the implementation session was offline), and the Docker-backed parts (`host.docker.internal` reaching the local service, image start) were first seen working in the owner walkthrough on 2026-11-03; `promtool` was not run. See the [spec](../specs/monitoring_dashboard.md).
- Deadline notices (`answer_deadline_notices`) cover only the two hand-entered `official_deadline` dates in `knowledge/passages.json` (15 May and 15 June 2026); passages without a reviewed date get no notice. A knowledge release or embedding index built before this change serves answers without notices until it is rebuilt. Verified by backend tests and the offline evaluation only. See the [acceptance record](../validations/answer_deadline_notices.md).

- **Input screen is lexical (`input_guardrails`).** It covers Spanish and English only,
  out-of-domain fires only on listed topics, and names and addresses are not screened; a miss
  falls through to the grounded path. See the [spec](../specs/input_guardrails.md).
- The answer cache (`answer_cache`) is per process (two pilot workers mean two caches) and lost on restart. It has no container setting and no QA `settings.env` key, a hit carries no `inspection` object, and `answers_total` includes hits. A vector-search fallback is never stored, but a stored hybrid answer can be served while the vector side is failing. It has no owner walkthrough and was not measured on the owner's Mac. See the [spec](../specs/answer_cache.md).
- No Android phone or emulator was checked against QA (`qa_real_device_check`, owner decision 2026-11-07: the owner has no Android device; no emulator, adb, or USB path). `--android-qa` has never run on a device. The only end-to-end QA check is `./scripts/init.sh --qa-check`, which renders the QA Desktop app offscreen (not the real window), adds one `useful` to QA's per-process feedback count per run, and may need one retry for the first question after QA starts. See the [spec](../specs/qa_real_device_check.md).
- QA alerts (`qa_service_alerts`) run on the same Mac as QA, so a sleeping, switched-off, or offline Mac cannot be detected and sends nothing; they are not host-outage alerting. The public check runs from that Mac, so it proves Tailscale answers there, not that the internet can reach it. The error alert needs 15 minutes of samples after each start or QA restart and counts only the dashboard's Problem level (10 %). One problem kind is reported at a time (down, then not ready, erroring, unreachable). macOS may block the background job until the owner allows it. See the [spec](../specs/qa_service_alerts.md).
- QA deployment (`qa_server_deployment`) is on the owner's Mac through Tailscale Funnel: it is unavailable while the Mac sleeps or restarts (rerun `--qa-deploy`), the hostname is public, and test-data-only is a rule, not a filter. QA serves the image's knowledge release until `qa_knowledge_deployment`. `--qa-update`/`--qa-rollback` were not exercised live in the owner walkthrough (no newer image). See the [spec](../specs/qa_server_deployment.md).
- **Usability evidence is pending.** The session kit and `--usability-record` exist ([`usability_session`](../specs/usability_session.md)), but no session with low-confidence users has run. The recorder's personal-data screen is lexical (capitals, cue words, digit runs, `input_guardrails`) and cannot catch every name; on QA the land chooser may not appear in task 3.
