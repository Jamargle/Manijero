# Manijero Durable Constraints

Operational MUST/MUST NOT rules that future features have to respect on top of
`AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, and the accepted contracts.

## Answer grounding

- **MUST**: no component may emit a user-visible answer claim that has not passed
  `backend/app/generation.py::verify_draft`. A draft produced by a hosted model,
  a prompt, a cache, or any future generator must be discarded **whole** when it
  fails, never partially emitted, repaired, or replaced by model or unreviewed
  knowledge. Reason: `grounded_answer_generation` established that code — not a
  model — is the authority on whether an answer may be shown, and an
  unverified claim is exactly the failure a wrong Spanish deadline or amount
  would come from.
- **MUST**: a user-visible answer's citation markers, its `sources` array, and
  the orientative notice are owned by code (`generate_grounded_answer` /
  `to_answer_response`), never by a generator. Draft markers are verified as
  original retrieval candidate ranks; emitted markers MUST be dense response-
  local positions, so `[n]` selects `sources[n-1]`. Reason: sparse retrieval
  ranks cannot be exposed as response indexes, and the notice is a fixed
  orientative line, not generated prose.

## Local embeddings

- **MUST**: the default answer behavior MUST stay the accepted BM25 retrieval
  with every code-owned answer property unchanged. An embedding model may run on
  the `/ask` path only through the explicit hybrid opt-in
  (`MANIJERO_RETRIEVAL_MODE=hybrid`, `chroma_hybrid_retrieval`); any other
  composition is a separately reviewed change. A missing optional runtime, a
  missing/invalid artifact, or a stale derived index or store MUST NOT alter an
  answer, citation, abstention, or land clarification. Reason:
  `local_bge_m3_embeddings` added an optional capability, not a new answer
  authority; silently swapping retrieval on a host without the model would
  weaken grounding without review.
- **MUST**: an embedding model may load only from a local artifact directory
  whose immutable upstream revision and every per-file SHA-256 match the pinned
  configuration, with hub/network access forced off. A model name, branch, or
  tag MUST NOT be loaded directly. A changed pin is a new reviewed configuration,
  never an edited checksum. Reason: an unpinned model silently changes vectors,
  storage, and results, and no download belongs on the answer-service host.
- **MUST**: a derived embedding index MUST be written outside `knowledge/`, MUST
  NOT contain passage text, and MUST NOT be treated as reviewed canonical
  knowledge. It MUST record the model pin and its catalog/passages/`as_of`/
  campaign inputs, and MUST be reported stale instead of reused when any of them
  change. Reason: the index is reproducible derived data; promoting it into the
  reviewed corpus would create a second, unreviewed answer source.

## Hybrid retrieval

- **MUST**: a vector or fused ranking MUST compose into `app.retrieval.Retriever`
  only through `Retriever.with_ranker`; it MUST NOT construct `RetrievedPassage`
  values, re-implement eligibility, or bypass the lexical gate. A question with no
  positive BM25 match MUST return no candidate in every mode, and only passages
  the retriever admitted may be returned. Reason: `chroma_hybrid_retrieval` kept
  approved-source provenance and zero-evidence abstention code-owned; vector
  similarity is positive for almost any text, so without the gate it would turn
  unrelated questions into answers.
- **MUST**: hybrid ranking MUST be used for a request only while the store
  manifest matches the current model pin, active campaign, and the digest of the
  exact admitted `(passage_id, text)` documents; otherwise, and on any load or
  query failure, the request MUST use the unchanged BM25 ranking and log only a
  fixed reason code or exception type name. Importing the service MUST NOT import
  `chromadb`, `torch`, or the vector/hybrid modules. Reason: a stale or broken
  vector store must degrade to the reviewed behavior, never to an answer from
  passages that are no longer admitted, and third-party error text can echo a
  question.
- **MUST NOT**: change the default retrieval mode to hybrid, or claim a retrieval
  or answer improvement, without a measured BM25 vs hybrid comparison on reviewed
  cases recorded with the change. Reason: the 2026-10-31 comparison on the
  14-case author-only sample measured no answer-level difference.

## Client request failure

- **MUST**: a request that failed or never reached the answer service MUST NOT be rendered as an
  answer, and recovery MUST keep the exact original wording. The failure lives in
  `ChatHomeState.failure` and is shown as a separate notice — never a transcript entry, never an
  `Asistente` label — while `RetryClicked` re-sends `ChatHomeState.failedQuestion` verbatim and
  appends no second user message (`ChatConversation` classifies the thrown failure; the transport
  signals are the payload-free `AnswerServiceUnavailableException`/`AnswerServiceErrorException`).
  Reason: `network_error_recovery` established that a person must never believe an unanswered
  question was answered, and `response_states`/`answer_source_cards` will render this transcript
  next, so a retryable failure must keep the question recoverable and out of the answer stream.

## Client response states

- **MUST**: a supported answer and an abstention MUST stay distinguishable in the transcript, and
  no answer MUST receive a confident legal-certainty treatment (no badge, checkmark, success green,
  or "verificado" wording). Every assistant entry MUST carry the `answerStatus` it arrived with
  (copied from the decoded `AskResponse.status`, never inferred from `lastResponseStatus`); an
  abstention MUST render its code-owned message verbatim in the transcript with the non-confident
  caution treatment plus an explicit text state label, and MUST NOT add a source, citation marker,
  figure, date, land name, or client-authored next step, nor branch on an abstention reason (the
  wire payload carries none). Reason: `response_states` established that a person must never read a
  "no lo sé" as a rule or mistake a real answer for legal certainty; `answer_source_cards` and
  `chat_accessibility` render this transcript next.

## Abstention

- **MUST**: no component may emit an abstention that carries a source, a figure,
  or a date, and abstention copy is code-owned (`ABSTENTION_MESSAGES` /
  `to_abstention_response`), never generated, paraphrased, or supplied by a
  caller. An abstention payload is exactly the accepted `AskResponse` keys with
  `status: "abstained"`, `sources: []`, `land_ids_to_choose: []`, and one pinned
  plain-Spanish message with no digit and no date. Reason: the point of
  abstaining is to avoid an invented deadline or amount; leaking evidence or
  figures into the "I cannot answer" path would reintroduce exactly that failure,
  and generated abstention prose could contradict the pinned counsel to consult
  the Oficina Comarcal Agraria or the cooperative.

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

## Client source cards

- **MUST**: every assistant entry MUST render only the `sources` its own decoded response carried
  (copied at the single creation site `ChatHomeState.ResponseReceived`, never from
  `lastResponseStatus`); the client MUST NOT invent a source, excerpt, date, or link, MUST open only
  an https URL, MUST NOT render a source, reference, figure, or date on an abstention, and MUST NOT
  alter the answer's claim text — only a `[n]` token may become a reference numeral, and only when
  the reply's distinct markers line up exactly with `sources` (a non-conforming payload rewrites
  nothing). Reason: `answer_source_cards` established that marker `[n]` means `sources[n-1]` only
  for a conforming cited set, so a mismatched or non-https payload must fail closed rather than point
  at the wrong document; `chat_accessibility` and `answer_land_scope` render this transcript next.

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

- **MUST**: a model draft MUST reach `/ask` only through
  `backend/app/gemini_generation.py::GatedGeminiGenerator`, which runs `verify_draft` itself and
  otherwise returns the extractive draft; it MUST NOT raise or emit any text of a rejected draft, and
  logs MUST carry only fixed `provider`/`outcome` codes. The provider payload MUST be built only by
  `minimal_provider_payload` from the `redact_text`-redacted question and candidate-numbered reviewed
  excerpts of the citation window (no land context, catalog id, URL, title, metadata, or retained
  text). No transport, endpoint, credential handling, or Google dependency may be added except by a
  reviewed change that also records the exact model, both reviews in
  `backend/config/pilot_privacy_review.json`, and the limits; `backend/config/gemini_provider_limits.json`
  MUST only become non-null through a reviewed change carrying a real limits and spend-cap decision.
  Reason: `gemini_generation_provider`; the absent transport is the guarantee that nothing leaves the
  service, and a fallback keeps a model problem from ever being worse than the extractive answer.

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

## Client land context

- **MUST**: the `land_context` sent with a question MUST carry every active stored land whenever at
  least one exists — `mode: all_active`, repository order, opaque local ids verbatim — and, per land,
  only the optional attributes the question actually needs (`municipality`, `water_regime`,
  `production_method`); it MUST NOT carry a land name, free-text note, area, timestamp, or any
  contract-unknown key, MUST send a needed but unknown stored value as `unknown` (never a guess),
  MUST omit a value it does not have (an unset `municipality`) rather than a placeholder or an empty
  string, MUST use `mode: general` with `lands: []` only when no active land is stored, and MUST NOT
  rewrite the person's exact wording or change the attribute decision silently (a vocabulary change
  is a spec and test change). Removed-list lands MUST NOT enter `land_context`, a clarification, or
  an answer request even when they are the only stored records; that case is `general` with
  `lands: []`. Reason: `minimal_land_context` established that the device's private labels and
  details never leave it with a question, that omission in the payload means "not needed" and never
  "invented", and that the current active lands must be re-read at submit and retry time so an added,
  edited, or removed land is reflected without exposing anything new.

## Land clarification

- **MUST**: a land clarification (`needs_land_clarification`) MUST be decided by the service — never by
  the client — and offered only when the request is `mode: all_active` with two or more lands whose
  known attributes disagree with a retrieved candidate's `applicability`; `general`, a single land, and
  a `selected` request MUST delegate to the accepted answer/abstention path and MUST never be asked to
  clarify again (a `selected` request is a person who has already chosen). A clarification payload MUST
  be exactly the accepted `AskResponse` keys with `answer: ""`, `sources: []`, and a non-empty unique
  list of the request's own opaque land ids; it MUST NOT carry a passage, excerpt, figure, date, or a
  `crop`-based distinction (the request has no crop field), and an omitted/`unknown` land attribute
  MUST never exclude a candidate or be given an invented value. The client MUST resolve `land_ids_to_choose`
  against the local list, show the lands' **saved names and known attributes** (never invent, rename, or
  reorder a land; ignore a returned id it does not store) and, on the person's choice, resubmit the
  **exact original wording** as `mode: selected` over only the chosen local ids with only the needed
  attributes (a chosen land no longer stored degrades to the accepted `general` request) while appending
  **no second user message**. Reason: `land_clarification` established that the service alone knows the
  retrieved source applicability (so the trigger cannot live in the client), that a person must never be
  asked to choose when only one land exists or after they already chose, and that the whole point of the
  feature — the assistant asking instead of guessing one land — is lost if the client fabricates a land,
  loses the person's wording, or dresses the question up as a new one.

## Client land scope

- **MUST**: every assistant entry MUST render only the `land_scope` its own decoded response carried,
  copied at the single creation site `ChatHomeState.ResponseReceived` (never from
  `lastResponseStatus`), and that caption MUST state in plain Spanish which lands were taken into
  account (`general` / all lands / the chosen lands) while MUST NOT naming a land or an id, implying
  that land details prove eligibility, adding a confident or success affordance, or appearing on a
  failed request or a clarification. Reason: `answer_land_scope` established that a person must be
  able to tell at a glance whether an answer used none, all, or the chosen lands without ever being
  told their land's details prove they qualify; `chat_accessibility` renders this transcript next.

## Land data disclosure

- **MUST**: the on-screen data-handling notice MUST describe only the current behaviour — the lands
  are saved device-locally in bounded automatic copies on the same device, and a question sends the
  question as written plus, for a land-aware answer, each land's opaque id and only the needed
  `municipality`/`water_regime`/`production_method` (an unknown value sent as `unknown`; name, zone,
  variety, custom variety, surface, tree count, notes and timestamps never sent). It MUST NOT promise
  recovery after device loss, an uninstall, a cloud copy, or confidentiality beyond what the answer
  service's own terms offer, and MUST NOT name a land, an id, or make any eligibility or legal claim.
  Its sendable-attribute list MUST stay pinned (`privacy/LandDataDisclosure.kt`) and tied to the real
  encoded payload by a test, so adding a sendable dimension fails until the notice is updated.
  Reason: `land_data_disclosure` established that a person must be able to trust the plain-Spanish
  notice to match what the app actually does, so over-promising a backup or under-describing the
  payload is the failure to avoid; `chat_accessibility` audits the surface next, and
  `local_land_auto_backup` made same-device copies real.

## Chat accessibility

- **MUST**: the chat surface MUST keep plain-Spanish text on every control and transcript entry (never
  an unnamed button), one `mergeDescendants` node per transcript entry reading its `Tú`/`Asistente`
  label, scope caption, optional state label, and body, and every newly appended assistant reply —
  `answered` as well as `abstained` — a `LiveRegionMode.Polite` node (a `Tú` entry is never
  announced as a reply, and the failure notice MUST stay a polite live region that does not merge its
  retry control, so `Reintentar` remains its own focusable node). It MUST NOT convey any state by
  colour alone, MUST keep a visible focus indication on its controls (Material's default indication,
  or a shared outline that keeps it — never remove it), MUST NOT override Material's minimum
  interactive size (no `LocalMinimumInteractiveComponentSize`), MUST bring the newest transcript
  element (entry, working notice, failure notice, or chooser) into view once per appended element
  without moving the composer's text or focus and without jumping to the page bottom, MUST keep the
  capped content column centred instead of stretched, and MUST NOT render the clarification chooser's
  "no puedo mostrar tus terrenos" fallback before the guarded local read resolves (an unresolved read
  shows only the title and explanation). Reason: `chat_accessibility` established the first
  accessibility baseline for this surface, and a later feature can silently regress a control's name,
  an entry's merged node, an announcement, a target size, or the scroll timing without any test
  failing.

## Chat surface presentation

- **MUST**: the assistant surface MUST keep one visible `Preguntar` action with a decorative send
  glyph under the question field (never an icon-only, unlabeled or renamed send), MUST keep the `Tú`
  and `Asistente` speaker labels visible inside every transcript entry even when the user entry is
  end-aligned at 85 % of the column, MUST keep the abstention's `Asistente` label, scope caption and
  `Sin respuesta segura` state label together inside its single merged caution node, MUST keep the
  three suggested questions as controls that only fill the composer and never submit, and MUST keep
  the recoverable failure a `ManijeroCallout(Danger)` whose `Reintentar` remains a sibling focusable
  node. Reason: `chat_screen_refresh` restyled this surface; each of these carries meaning that
  colour, alignment or position alone cannot, and a later "cleaner" card could drop a label or merge
  the retry without any test failing.

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

## Safety evaluation

- **MUST**: a land-safety evaluation case MUST be source-anchored and human-reviewed: it names the
  sources it expects, and a case whose expectation turns on a critical fact (a deadline, an amount,
  a threshold) MUST NOT enter the set without a completed `review` block (reviewer, review date,
  level, `<source_id>#<location>` anchor) — a critical case without it fails closed at load time.
  The harness MUST run the accepted end-to-end decision (`answer_with_clarification`) unchanged and
  MUST NOT re-implement eligibility, grounding, or clarification, MUST report coverage metrics
  report-only (a safety invariant leak may fail, a coverage mismatch only with `--fail-on-miss`),
  and MUST NOT treat any metric as a release gate until a measured baseline is reviewed and
  enforcement is agreed separately. Reason: `land_safety_evaluation` established the reproducible
  synthetic baseline; a gate whose numbers came from synthetic fixtures, or a case whose critical
  fact nobody checked, would turn an unverified expectation into a false safety guarantee.

## Campaign scope

- **MUST**: `/ask` requires an explicitly configured four-digit active campaign, independent of
  the UTC source-validity date. Never infer the campaign from the date, question, land, or evidence;
  only neutral and exact-active-campaign sources may reach generation, and malformed scope fails
  closed. Expired campaign records must be rotated out of active artifacts with their passages.
  Reason: `backend_campaign_validity` prevents evidence for one PAC campaign being mistaken for another.

## Coverage disclosure

- **MUST**: the pinned coverage disclosure MUST name only topic areas represented by the reviewed
  corpus, MUST state the enforced limits (cooperative-specific practices, personalized amounts or
  eligibility, out-of-corpus topics), MUST NOT contain a deadline, amount, threshold, article number,
  eligibility claim, or invented contact detail, and MUST be updated in the same change that widens
  or narrows corpus scope. Reason: `coverage_and_help` establishes that people must not infer broad
  coverage from the assistant; stale or overconfident disclosure could prompt reliance outside the
  evidence actually reviewed.

- **MUST**: restyling the help and privacy surfaces MUST preserve their pinned copy, disclosure facts,
  shared-attribute mapping and existing navigation callbacks; visual grouping MUST NOT introduce a
  new promise, warning/status implication, route or external link. Reason: `help_privacy_refresh` is
  visual adaptation only; changing the facts or their implied certainty during a restyle could make
  the screens contradict the reviewed corpus or the actual local/request data boundary.

## Brand vectors

- **MUST**: shipped brand vectors (the mark, sixteen `ic_*` glyphs, the olive-branch illustration)
  stay single-colour Android-XML masks under
  `shared/src/commonMain/composeResources/drawable/` with only `#000000` / `#00000000` literals — no
  `android:tint`, gradient, `aapt:attr`, clip path, or `@android:` — and take every rendered colour
  from the theme. A new glyph follows the 24 dp outline grid (2 dp round stroke, no fill, 2–22 dp safe
  area) and ships with its board entry and the owning spec's gates. Reason: `brand_vectors`; a baked
  colour or a second dark-mode asset would break the palette and the contrast pairs
  `design_token_refresh` guarantees.
- **MUST**: the mark and illustration stay decorative — no `contentDescription` or colour parameter,
  no semantics node, halo painted in Compose — and MUST NOT read as a check, seal, badge, or
  "verified"/"official" cue, or qualify an answer, source, or land. Reason: `brand_vectors`; a status
  reading would reintroduce the legal-certainty failure `response_states` forbids.
- **MUST NOT**: add an icon font (`material-icons-*`), raster/binary icon asset, or generated image
  for these glyphs. Reason: repository-owned vectors keep the tint policy and the pinned inventory.

## Shared component layer

- **MUST**: everything under `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` stays
  presentational: every visible string, value, icon, selection and callback is a parameter, and the
  package MUST NOT read `Res.string`, import a `lands`/`chat`/`privacy`/`coverage`/`platform` type,
  read a store, send a request, log, or own filtering, validation, parsing, formatting, totals or
  selection persistence. Reason: `ui_component_library` established the layer so later screens share
  one vocabulary; a component that owns copy or a business rule would duplicate the screen's
  authority and make a Spanish-copy or domain review miss the real source.
- **MUST**: every colour, shape and spacing value comes from `MaterialTheme.colorScheme`,
  `LocalManijeroSemanticColors`, `LocalContentColor`, `ManijeroShapes`, `ManijeroSpacing` or
  `ManijeroLayout` — never a hex/`Color(0x…)` literal or a new token — and no state is colour-only
  (callouts keep an icon plus text, chips keep a label, selection keeps the indicator plus label
  weight). Reason: `design_token_refresh` and `brand_vectors` gate contrast from those sources; a
  literal or a colour-only cue would bypass the gates and the non-colour status rule.
- **MUST**: every interactive control in the layer keeps a text or caller-supplied accessible name,
  a 48 dp minimum target, and Material's focus indication and minimum interactive size; the search
  clear action and the top-bar privacy action are never rendered unnamed (an action with no name is
  omitted), navigation labels stay visible on both bars, and the bars MUST NOT own window insets.
  Reason: `ui_component_library` set the accessibility baseline and `app_chrome_navigation` owns
  insets; a later screen can silently drop a name, a target, or the single-inset-owner rule without
  any test failing.

## App shell and navigation

- **MUST**: `AppShell` stays the single owner of the status bar, navigation bar, horizontal
  system-bar and ime window insets; the top app bar, navigation bar, rail and every hosted screen
  MUST NOT add their own window-inset padding. Reason: `app_chrome_navigation` made the shell the one
  frame, and a second inset owner double-pads or draws under a system bar.
- **MUST**: the shell tabs (`Mis terrenos`, `Asistente`, `Ayuda`, in that left-to-right order) are
  the only top-level navigation; a screen MUST NOT re-add a top-level `Volver` or `Mis terrenos`
  affordance. The lands tab MUST be omitted when no local `LandRepository` is injected, and a
  selected index MUST never point at an omitted destination. Reason: `app_chrome_navigation` removed
  the duplicate routes; re-adding one would give two authorities for the same move and could expose
  a dead destination.
- **MUST**: add/edit/remove land forms hide the navigation bars and keep their own `Cancelar`;
  privacy stays a detail route with its own `Volver`. Android system back MUST follow
  `AppNavigation.backTarget` (lands → assistant, form → lands, help → the tab it was entered from,
  privacy → the section it was opened from) and MUST be absent when that target is null. Reason:
  `app_chrome_navigation` protects an unsaved draft and keeps the selected tab consistent with the
  visible screen.


## Knowledge updates and retrieval

- **MUST**: source scans and document ingestion MUST write only quarantined candidates; they MUST NOT
  make a new or changed document answerable without human approval. Candidate records MUST preserve
  official URL, retrieval time, original-content hash, parser/version provenance, and review status.
  Reason: a new publication can be inapplicable, superseded, malformed, or adversarially formatted.
- **MUST**: scheduled source checks are best-effort and MUST expose last-success time, failures, and
  missed runs; a schedule alone MUST NOT be represented as proof that the corpus is current.
  Reason: external schedulers and official sites can delay or fail.
- **MUST NOT**: add a repository-hosted schedule (for example a `.github/workflows` `schedule:` trigger)
  that scans official sources or invokes `run_source_updates.py`; scheduled source checks run only from
  operator-installed host units. The scheduler MUST write only operational state (monitor/discovery
  state, ledger, lock) in a state directory outside the repository and outside `knowledge/`, and its
  tests MUST stay offline (sockets blocked, fakes only). Reason: `knowledge_update_scheduler` — a
  merged repository schedule would make real requests to official sites without an operator choice,
  and committed state would bypass human-reviewed canonical changes.
- **MUST**: change-impact analysis MUST stay read-only over approved knowledge and MUST NOT retire,
  replace, re-approve, or re-date a source, passage, evaluation case, index, or answer. Every
  potentially affected candidate MUST remain review-required, and an ambiguous publication,
  amendment, repeal, or validity signal MUST NOT authorize retirement or be dropped silently: every
  ambiguous signal, negated wording included, MUST make its candidate review-required even when it
  links no approved source or links only a reviewed passage or evaluation case. Reason:
  `legal_change_impact_analysis` detects wording; only an identified human can decide what a legal
  change means for the reviewed corpus.
- **MUST**: canonical catalog and passage changes MUST go through the controlled merge that verifies
  an explicit approval by a named requested reviewer other than the proposal author, a matching
  package/checks/case digest, all required checks passing, and current canonical bytes matching the
  reviewed baseline. A proposal that changes the reviewed corpus MUST supply the reviewed
  answer-evaluation case set; preparation MUST validate the **after-state** and block readiness with
  the orphaned case ids, and merge MUST require the same digest-bound case set and revalidate it.
  Without cases, a catalog/passage change MUST be blocked (a no-op proposal may pass). A bot, CI
  status, label, or matching hash MUST NOT count as approval; the commands refuse known automation
  identities but identities are not authenticated; a rejected or changes-requested package MUST
  leave canonical knowledge byte-identical; and merge MUST NOT reindex, release, or deploy. Canonical
  after hashes and writes MUST preserve the field order of entries the proposal does not rewrite, so a
  no-op merge is byte-identical; a newly added or rewritten entry may take the proposal's own
  serialization.
  Reason: `knowledge_update_review_pr` keeps approval with a person and separates a bounded reviewed
  merge from publication; an unreviewed case set or a reordered file would hide corpus drift.
- **MUST**: a knowledge release MUST rebuild indexes from approved canonical artifacts, record artifact
  and model versions, pass structural/grounding gates, and support rollback to the prior index.
  Reason: generated indexes are derived data and must not drift from reviewed sources.
- **MUST**: retrieval changes MUST be compared with the measured BM25 baseline on the reviewed cases;
  report-only metrics MUST NOT be described as improved answer quality without sufficient reviewed
  evidence.

## Hosted pilot and provider boundaries

- **MUST**: a managed tunnel is transport only; any public pilot API MUST enforce its own
  authentication, authorization, per-client rate limiting, and request-size limits. Reason:
  `hosting_provider_review` found that Cloudflare Tunnel removes the public origin IP but does not
  authenticate the application, and the current OpenAPI contract declares no security scheme.
- **MUST NOT**: let a real-user question transit a host, tunnel, or generation provider until the
  current terms, data flow, log/retention behavior, and qualified privacy review are recorded and
  approved. Reason: the 2026-10-27 decision keeps the owned-server path blocked on owner attestation
  and keeps Gemini disabled by default; provider selection alone is not pilot approval.
- **MUST**: the hosted pilot service MUST start only through the pilot-profile launcher
  (`backend/scripts/serve_pilot.py`), which validates the explicit campaign, the client
  credentials, and the reviewed corpus before accepting traffic and refuses the development
  profile, reload mode, and a non-loopback origin without an explicit acknowledgement. A
  corpus or campaign defect MUST fail readiness (`503`), never produce a degraded answer.
  Reason: `./scripts/init.sh --backend` is a development path with reload, `0.0.0.0`, a defaulted
  campaign, and no authentication; starting the pilot from it would serve unvalidated configuration
  and wrong-campaign evidence.
- **MUST**: pilot access control MUST be application-owned: one bearer token per client stored only
  as a SHA-256 digest in a mode-`0600` operator file, that client's per-minute request allowance, and
  a bounded request body, all enforced before the answer route runs; `GET /health` MUST stay
  liveness-only and `GET /ready` MUST stay a separate campaign-plus-corpus readiness check whose
  payload carries no corpus value. Rate limits are per process and MUST NOT be described as
  cluster-wide or edge-enforced. Reason: the hosting decision found that a managed tunnel is
  transport only and the API declared no security scheme; a per-worker window that is described as
  global would overstate the protection.
- **MUST**: pilot operational logs MUST contain only one request record with the method, route path
  (no query string), status, duration, and gate; they MUST NOT contain question text, land context,
  names, notes, client identifiers, tokens, or response bodies, and the development access log MUST
  NOT be repurposed as the pilot log. Reason: the hosting decision's log condition and the accepted
  minimal-land-context contract; default ASGI/provider logs are not reviewed and must not be assumed
  silent.
- **MUST**: a pilot corpus/configuration backup MUST record size and SHA-256 for every file
  and MUST NOT contain client tokens, tunnel credentials, or other secrets: the backup
  command accepts only the named non-secret configuration files, refuses a credential
  basename or credential markers in an accepted file, and writes the backup tree
  owner-only. A restore MUST require explicit confirmation, verify every recorded hash,
  validate the catalog/passages pair **before** the first canonical write, refuse a
  canonical target it cannot read, and replace each file atomically; if a later write fails
  it MUST attempt to restore the prior bytes and report failure rather than claim success.
  A restored canonical artifact MUST be readable by the service account: the command writes
  `0644` (backup files stay `0600`), checks that the written files have the read bits, and
  fails closed with `corpus_not_readable`, rolling the prior content and mode back, if they
  do not. The runbook MUST check cross-user readability (`sudo -u manijero test -r`) before
  starting the service, because file mode alone cannot prove path traversal.
  A crash between the two replacements can leave a mixed pair and is recovered by
  re-running the same verified restore, so the command MUST NOT be described as a single
  atomic pair swap. A restore that yields an expired or not-ready corpus MUST report
  `not_ready`, never success; a restore MUST NOT run while the service is active. Reason: a
  half-written catalog/passage pair, a copied credential, or a silently stale corpus is
  worse than a known-good backup, an unverified backup is not a recovery path, and a
  restore that leaves the corpus unreadable by the non-root service takes the pilot down.
