# Constraints: Lands and local storage

Durable MUST/MUST NOT rules for land editing, fields, storage, automatic copies, search and summary, removal, and form accessibility. Part of the index in [`CONSTRAINTS.md`](../../CONSTRAINTS.md); paths in backticks are relative to the repository root.

## Land editing

- **MUST**: editing a land MUST update exactly one stored record: it carries every attribute the
  edit form still does not collect (`notes`) through unchanged, preserves the targeted `id` and
  `createdAtEpochMillis`, never calls `create`/`delete`, and MUST NOT report an update as saved when
  `update` returned `null` or threw. Reason: `edit_land` established that correcting one detail must
  never rewrite another land or silently erase stored data.

## Land fields and storage

- **MUST**: every stored land MUST have a trimmed non-blank zone of at most 80 characters, both on
  create and on edit; clearing it MUST block the save. Reason: `land_measurement_fields` made the
  zone the second required identity field.
- **MUST**: the current land store MUST have one canonical versioned format (`land-store-v2`: active
  and removed sections in one aggregate) and one current decoder. The recovery transition MUST migrate
  existing valid `land-store-v1` records exactly once, preserving every decoded record as active;
  after migration, the old format is input only and MUST NOT become a second ongoing write/read path.
  A malformed record MUST be skipped whole and every migrated record MUST carry its zone. A refused
  migration write MUST leave the v1 snapshot untouched and surface as a failed read, never as an empty
  store. Reason: an already-shipped v1 store needs an explicit safe migration to represent active and
  removed lands without losing or half-replacing the person's records.
- **MUST NOT**: infer a zone, variety, surface, or tree count from a name, municipality, question, or
  another land. An absent optional value MUST stay absent in the store and MUST be omitted from the
  land details rather than shown as zero. Reason: land records must not imply knowledge or
  eligibility the person did not provide.
- **MUST**: surface text MUST accept comma or dot, reject letters, signs and non-finite values, and store
  at most two decimals by rounding a longer entry; tree count MUST be a whole ASCII number of at
  least one. Raw text MUST stay on screen after an invalid save. Reason: the approved validation table
  rounds a surface to the stored precision instead of refusing a plausible measurement or truncating it
  silently.

## Land automatic copies

- **MUST**: automatic land copies MUST stay on the same device, stay bounded (at most
  `MAX_AUTOMATIC_LAND_SNAPSHOTS` whole-aggregate copies), and be written only after the primary
  aggregate write succeeded. A refused copy MUST NOT turn a completed save into a reported failure;
  the next successful write rotates a fresh copy in. No copy path may use a network API, a cloud
  store, or an operating-system cloud-backup destination. Reason: `local_land_auto_backup` protects
  against one damaged local write, not against device loss or uninstall; an unbounded or off-device
  copy would silently become a different product promise.
- **MUST**: an unreadable primary aggregate MUST be rebuilt from the newest fully valid automatic
  copy and reported as a recovered state. With no fully valid copy the read MUST fail; it MUST NOT
  open an empty store. A copy with damaged integrity metadata or one undecodable record MUST be
  rejected whole, never offered as a complete restore. Reason: `local_land_auto_backup`; showing an
  empty land list after corruption is exactly the data loss the copies exist to prevent.
- **MUST**: permanent deletion MUST write a durable purge marker before rewriting the primary
  aggregate, every read and every restore path MUST filter the marked ids, and the marker MUST be
  cleared only after the primary and every retained copy are sanitized. Reason:
  `local_land_auto_backup`; a crash between the primary write and a copy rewrite must never let an
  older copy bring a deliberately deleted land back.
- **MUST**: the Android host MUST keep the land data out of every operating-system backup and
  transfer destination. Either `android:allowBackup="false"`, or `android:allowBackup="true"` with
  both `android:fullBackupContent` and `android:dataExtractionRules` pointing at rule files that
  exclude `domain="sharedpref" path="manijero_lands.xml"` from cloud backup and from
  device-to-device transfer. A new preferences or file location that holds land data MUST extend
  that exclusion in the same change. Reason: `local_land_auto_backup`; the privacy notice tells the
  person there is no copy on the internet or on another device, and an OS backup of
  `manijero_lands.xml` (the aggregate plus `land_store_snapshot_1..3` and `land_store_purge`) would
  make that notice false. `AndroidBackupExclusionGuardTest` fails in `:shared:jvmTest` if the
  declaration or either rule file regresses.

## Land list search and summary

- **MUST**: the search query and the summary MUST be display-only: derived from the in-memory
  `LandListState` and the lands on screen, never persisted, never serialized into the store or a
  `Land`/`LandDraft` field, never sent in an `AskRequest`/land context, and never logged. Every read
  MUST start from a blank query. Reason: `land_search_and_summary`; a stored or transmitted query
  would leak what the person was looking for and turn a view filter into hidden state.
- **MUST**: the summary MUST count only annotated values, MUST state its denominator
  (`x de y terrenos`, `x de y … encontrados` while a query is active), and MUST render `Sin datos`
  instead of a zero when nothing is annotated — no total may be inferred from another attribute and
  no card may render a bare number. With a query active every card MUST describe only the shown
  matches; with no match no card may render. Reason: `land_search_and_summary`; a partial or
  inferred total would read as a verified measurement of lands the person cannot see.
- **MUST**: search MUST match text only — name, zone, municipality, the variety label or its custom
  `Otra` text, the water-regime label and the production-method label — and MUST NOT match measures,
  ids, notes or timestamps, rank, reorder, or drop a duplicate row. A query with no letters or digits
  MUST behave like a blank one. Reason: `land_search_and_summary`; matching a measure or note would
  reveal a value the search hint does not promise, and reordering would hide the stored order.
- **MUST**: an empty store MUST show the shared olive-branch empty state with exactly one primary
  `Añadir terreno` action and no summary cards and no search field, and a query with no match MUST
  show one plain sentence with a named clear action while the `Añadir terreno` action stays
  reachable. Reason: `land_search_and_summary`; a second Add action, or cards over zero shown lands,
  would offer an action twice or state a total nobody can see.

## Land removal

- **MUST**: ordinary land removal MUST move exactly one named active record to the local removed list
  only after explicit confirmation; it MUST preserve all other records and keep removed lands out of
  chat context. A restore MUST return exactly that removed record with its stored fields unchanged to
  the end of the active list, and MUST NOT reorder the other active or removed records. Permanent
  deletion MUST target only a record already in the removed list, MUST require a second explicit
  confirmation naming it, and MUST remove that record from the active/removed aggregate and every
  app-managed automatic snapshot. Neither action may claim success after a missing-record or storage
  failure. User-exported files are outside this deletion guarantee and MUST be described as capable
  of restoring their old contents. Reason: the owner chose recoverability without cloud sync; removal,
  restore, and permanent deletion have distinct consequences.

- **MUST**: automatic land snapshots MUST remain on the same device and be bounded. Portable backup
  files MUST use one versioned cross-platform schema, remain plaintext, contain only land data, and
  be clearly described as private files. Import MUST preview then replace all current active and
  removed lands only after confirmation; invalid input MUST not change the store. Reason: the owner
  selected same-device automatic copies plus a user-controlled Android/macOS file, with replace-all
  restore and no cloud or encryption feature.

- **MUST**: the portable land backup MUST stay one plaintext JSON schema (`manijero-land-backup`, `version` integer) separate from the private store codec; a schema change MUST bump `version` and keep reading every earlier version or refuse it as unsupported, never misread it. Import MUST validate the whole file before any preview or repository call, and an invalid file MUST NOT call the repository at all. Restore MUST replace both lists (no merge) only through `LandRepository.replaceAll`, which MUST keep a same-device automatic copy of the current aggregate before rewriting it and MUST NOT overwrite a store it cannot read. The exporter MUST NOT produce a file the importer would refuse (same value rules, same size limit), and the file MUST contain only land data. Copy MUST say the file is unencrypted and that the app cannot delete exported copies. Reason: `portable_land_backup`; a file the person keeps outside the app must stay readable on both platforms and a bad file must never cost them their current lands.

- **MUST**: product-improvement question/answer retention MUST be default-off and opt-in before each
  retained question, redact text, exclude land context and stable user/device identifiers, and delete
  records no later than 30 days. Pilot readiness MUST remain blocked until a qualified privacy/legal
  review of the data flow, notice, retention behavior, and provider terms is recorded. Gemini is in
  pilot scope but MUST remain disabled until the exact current model/tier, terms, data flow, and review
  gate are recorded as approved. Only the minimum question and approved retrieved passages may be
  sent; land names/notes and stable identifiers MUST NOT be sent. Every model draft MUST pass the
  existing whole-draft verifier; citations, source arrays, notices, and abstentions remain code-owned.
  Reason: model output is untrusted and provider exposure requires informed choice and qualified
  review before real users.

- **MUST**: a model draft (Gemini or the loopback local provider) MUST reach `/ask` only through
  `backend/app/gemini_generation.py::GatedGeminiGenerator`, which runs `verify_draft` itself and
  otherwise returns the extractive draft; it MUST NOT raise or emit any text of a rejected draft, and
  logs MUST carry only fixed `provider`/`outcome` codes. The provider payload MUST be built only by
  `minimal_provider_payload` from the `redact_text`-redacted question and candidate-numbered reviewed
  excerpts of the citation window (no land context, catalog id, URL, title, metadata, or retained
  text). No remote-provider transport, endpoint, credential handling, or Google dependency may be
  added except by a reviewed change that also records the exact model, both reviews in
  `backend/config/pilot_privacy_review.json`, and the limits; `backend/config/gemini_provider_limits.json`
  MUST only become non-null through a reviewed change carrying a real limits and spend-cap decision.
  Reason: `gemini_generation_provider`; the absent transport is the guarantee that nothing leaves the
  service, and a fallback keeps a model problem from ever being worse than the extractive answer.

- **MUST**: the local generation transport (`backend/app/local_generation.py::OllamaTransport`)
  MUST talk only to the `OLLAMA_BASE_URL` loopback constant (`http://127.0.0.1:11434`), with no
  proxy, no redirect, and no configurable or remote URL, and MUST use only the pinned tag whose
  installed digest matches `backend/config/local_generation_model.json`. Changing the model,
  digest, or limits in that record MUST be a reviewed change carrying new measurement evidence.
  Local generation MUST stay off unless both `MANIJERO_GENERATION_PROVIDER=local` and a matching
  `MANIJERO_LOCAL_MODEL` are set; in the pilot profile it MUST also require a passed pilot review.
  Automated tests MUST NOT need Ollama. Reason: `local_generation_provider`; the question stays on
  the host only while the endpoint is a fixed loopback address, and the recorded measurements are
  valid only for the pinned weights and limits.
  Note (owner decision 2026-11-01, [`backend_container_image`](../specs/backend_container_image.md)):
  inside the answer service container the constant is unchanged; a fixed relay
  (`backend/container/ollama_relay.py`) listening only on the container's `127.0.0.1:11434`
  forwards to the constant `host.docker.internal:11434` (Ollama on the host Mac), is not
  configurable, and forwards nowhere else.

- **MUST**: retention MUST run only after the answer is produced, through
  `backend/app/retention.py::retain_if_opted_in`, and MUST NOT change, delay-fail, or replace the
  answer; a redaction or storage failure retains nothing and logs only a fixed outcome code. The
  retained row MUST stay exactly `created_on`, `expires_on`, `answer_status`, `question_redacted`,
  `answer_redacted` (dates, no time; no client, device, land, or network identifier), the store MUST
  live outside the repository in an owner-only directory, and every read or export MUST exclude a
  record whose `expires_on` (creation + 29 days) has arrived. The client MUST send
  `retain_for_improvement: true` only from the unchecked-by-default checkbox for that one send, MUST
  reset it on every send, and MUST drop it when the wording contains a saved land's name, zone,
  municipality, custom variety, or notes. `backend/config/pilot_privacy_review.json` MUST only be
  changed to an approved state by a reviewed change carrying a real dated qualified review; tests use
  the labelled synthetic fixture. Reason: `pilot_privacy_readiness`; the server never sees land
  names, so only the device can exclude them, and a widened row or an in-repo store would turn
  short-lived redacted text into durable, joinable personal data.

- **MUST**: land-list Edit and Remove controls remain separate from the non-clickable row and their
  accessible names MUST include both the action and saved land name. Reason: duplicate land names
  are permitted; an action announced without its target can remove or edit the wrong record.

## Land form accessibility

- **MUST**: the land add and edit forms MUST keep a plain-Spanish text name on every control, MUST
  name each choice option with its group (`Riego: No lo sé`, `Producción: No lo sé`) inside a
  `selectableGroup`, MUST expose each form title as a heading, and MUST NOT leave a blank-name save
  silent: the unchanged required-name message is shown *and* announced and input focus returns to
  the name field with every entered value preserved. Reason: `land_form_accessibility` established
  that two identically named `No lo sé` options and an unannounced validation error are exactly the
  failures a person with low digital confidence or a screen reader cannot recover from on their own.
  The focus is requested from the save path (not a state-keyed effect) because the error flag stays
  true across a repeated blank attempt, so a repeated press must re-focus the field too.
