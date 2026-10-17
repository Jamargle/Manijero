# Feature evidence

Per-feature evidence sections, moved out of [`PROGRESS.md`](../../PROGRESS.md) on 2026-10-17
without rewording. Loaded on demand: the routine entry point is the `PROGRESS.md` status board,
and each accepted feature's authoritative record is `docs/validations/<feature-id>.md`.

The section headings were demoted from `###` to `##` when the file moved, and the
`visual_foundation` section status was corrected from `passing` to `accepted` to match
`feature_list.json`. Section text is otherwise unchanged.

## chat_home — accepted

Independent validator accepted commit 47e80c8 (acceptance commit a79946f; record:
`docs/validations/chat_home.md`). Verification recorded at acceptance:

- `./init.sh` passes with the restored Gradle 9.8.0 wrapper and reports the current feature state.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes and compiles the shared Compose screen.
- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android` stopped before compilation because the worktree had no `ANDROID_HOME` or `local.properties` with `sdk.dir`. No Android result was claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running target; compilation is covered by `:desktopApp:build`.
- Outstanding: the spec's Android/Desktop manual smoke ("locate the Spanish field without adding a land, type a question, and confirm the action becomes available") was not executed at acceptance. It is not evidence of failure and can now be run where the Android SDK is configured.

## chat_question_submission — accepted

- `ChatHomeState.reduce` is a pure reducer returning `ChatReduction(state, effect)`. It
  rejects blank and over-2,000-character questions, refuses a second submit while a
  request is in flight, keeps the submitted wording immutable for both the user message
  and `AskRequest.question`, appends at most one assistant message per response, retains
  `abstained` / `needs_land_clarification` status plus opaque `land_ids_to_choose` without
  inventing an answer or a land choice, and releases the request on failure without
  discarding a newly typed draft.
- `ChatConversation` applies the reducer and runs the single `AnswerService.ask` call on
  its injected `CoroutineScope` (composition-scoped `rememberCoroutineScope()` in
  `App`), so no Composable performs a network call and `CancellationException` is
  rethrown. `App(answerService = UnavailableAnswerService)` injects the boundary, renders
  the ordered transcript with text labels "Tú"/"Asistente", a plain-Spanish working
  indication ("Estoy preparando la respuesta…") with a polite live region, a disabled
  **Preguntar** while in flight, the Spanish limit explanation without rewriting wording,
  and a neutral clarification acknowledgement that claims no answer.
- `KtorAnswerService` posts the contract `AskRequest` to `<baseUrl>/ask`
  (`ContentNegotiation` + `answerJson` with `explicitNulls = false`). No production base
  URL is hard-coded, and platform engines can be supplied through `answerHttpClient`.
- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples
  against answer_api_contract".
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL, 24 tests, 0 failures
  (`ChatHomeStateTest` 13, `ChatConversationTest` 3, `KtorAnswerServiceTest` 2,
  `LandRepositoryTest` 4, 2 scaffold tests). `KtorAnswerServiceTest` asserts `POST /ask`,
  the exact original question `"  ¿Puedo regar hoy?  "`, exactly
  `{"mode":"general","lands":[]}` for `land_context`, and decodes the accepted
  `contracts/examples/response-answered.json` from the repository working tree.
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, 22 tests, 0 failures.
- `./gradlew :desktopApp:build` → BUILD SUCCESSFUL; `./gradlew :androidApp:assembleDebug`
  → BUILD SUCCESSFUL (`androidApp/build/outputs/apk/debug/androidApp-debug.apk`);
  `./init.sh --verify` → BUILD SUCCESSFUL. This worktree has
  `local.properties` (`sdk.dir=/Users/jose/Library/Android/sdk`), so the Android checks
  ran; no environment blocker remains.
- Runtime smoke: `./gradlew :desktopApp:run` started the Desktop window with the shared
  chat screen and produced no exception in the run log. No scripted click-through or
  screenshot was taken (interactive GUI target), and no live answer was requested because
  the backend still has no `/ask`; the working-state/one-reply behavior is covered by
  `ChatConversationTest`.
- Privacy check: `grep -rn "println|Log\.|Logger|printStackTrace" shared/src` returns no
  matches, so no raw question or land content is logged.
- Deliberately not implemented (owned by later features): `response_states`, source
  cards, land selection/context, retry UI and failure copy, suggested prompts, and any
  backend/contract change.

## source_catalog_validation — accepted

- Canonical catalog `knowledge/source_catalog.json` is `schema_version: source-catalog-v1`
  with an empty `sources` array; it validates and does not imply corpus coverage.
- `knowledge/source_catalog.schema.json` is the readable contract; the test suite
  asserts its required/optional fields, issuer enum, and version stay in sync with
  `backend/app/source_catalog.py`.
- `backend/app/source_catalog.py` is standard-library only and offline. It enforces
  strict/unknown keys, unique slug ids, non-blank text, HTTPS approved-host and
  issuer-host match, SHA-256 digest shape, ISO dates and ordering, `approved`
  review with a named reviewer, `current` lifecycle, and `--as-of` expiry.
- Commands actually run:
  - `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12`
    → exit 0, `valid source catalog: ... (schema source-catalog-v1, 0 source(s) checked as of 2026-10-12)`.
  - Accepted fixture `valid_official_source.json` (3 sources: BOE, Junta de Andalucía,
    FEGA) → exit 0; `valid_empty_catalog.json` → exit 0 with 0 sources.
  - All 21 rejection fixtures → non-zero. Twenty fail with exit 1 and a located
    diagnostic such as `$.sources[0].content_sha256: required key is missing`,
    `$.sources[1].id: duplicate id; already used by $.sources[0]`,
    `$.sources[0].original_url: host is not on the approved official-domain allowlist`,
    and `$.sources[0].valid_until: is before the validation date; the document is
    expired and ineligible`; `malformed_json.json` fails with exit 2.
  - `cd backend && python -m pytest tests/test_source_catalog.py` → 43 passed.
  - `cd backend && python -m pytest` → 45 passed (43 new + 2 existing health tests).
  - `git diff --check` → clean.
- Not run: Android/Gradle checks (not applicable to this knowledge/backend feature).
- Independent validation (2026-10-12): `accept`. The validator re-ran the canonical
  and valid fixtures (exit 0), all 23 fixtures (20 exit 1 + 1 exit 2), the `--as-of`
  expiry boundary, a socket-guard no-network check, and a no-content-leak check; it
  also confirmed scope discipline and that the recorded evidence matched. Record:
  `docs/validations/source_catalog_validation.md`.
- Limitation: the validator proves catalog-policy conformance, not that a remote
  document is authentic, current, or legally applicable. No real document was added.

## source_retrieval — accepted

What changed:

- `knowledge/passages.schema.json`: readable, versioned `passage-set-v1` contract
  mirroring the catalog schema style. Top level has only `schema_version` and
  `passages`; each passage has non-blank `id` (unique, lowercase slug),
  `source_id`, `location`, `text`, plus optional `critical` and `applicability`
  (same value rules as the catalog). The tests assert the schema and the
  in-code validator stay in sync.
- `backend/app/retrieval.py`: standard-library only and offline.
  - `validate_passage_set` / `load_passage_set`: strict, located diagnostics
    (`$.passages[0].excerpt: unknown key is not allowed`) that never echo field
    values or excerpt text.
  - `tokenize`: lowercase, NFKD + combining-mark stripping, split on
    non-alphanumerics, Spanish stopword removal, so `"solicitud única"` and
    `"SOLICITUD unica"` tokenize identically.
  - `Bm25Index`: Okapi BM25, `k1 = 1.5`, `b = 0.75`, deterministic ordering with
    ties broken by passage id, and no candidate returned with a zero score.
  - `Retriever.from_documents` and `Retriever.search`: re-runs
    `validate_catalog`, raises `CatalogRejectedError` on an invalid catalog
    (fail closed, no partial index), raises `PassageSetError` located at
    `$.passages[i].source_id` for an unknown source, indexes only sources that
    are `approved`, `current`, and unexpired as of `as_of`, and maps
    `RetrievedPassage` to the accepted `AnswerSource` field names
    (`title`, `issuing_body`, `url`, `location`, `published_or_updated_on`,
    `verified_on`, `excerpt`) plus `passage_id`, `source_id`, `applicability`,
    `critical`, `score`, `rank`. Applicability and `critical` use the
    passage-level value when declared, otherwise the source-level value, and are
    surfaced only (no filtering).
- `backend/scripts/evaluate_retrieval.py`: report-only baseline CLI with an
  explicit `--as-of` and `--k`, per-question expected-passage ranks, aggregate
  `hit@k`/`recall@k`/MRR, `--json`, and `--fail-on-miss` off by default. Exit
  codes: `0` report, `1` only with `--fail-on-miss` and a miss, `2`
  unreadable/invalid input.
- `backend/tests/fixtures/retrieval/`: synthetic, clearly labelled fixtures — an
  approved 3-source catalog, 12 reviewed passages, 7 JSONL questions, and the
  edge cases (unknown `source_id`, unknown key, bad applicability value,
  malformed JSON, expired catalog, non-approved catalog, non-current catalog).
  None of them states a real deadline, amount, or article.
- `knowledge/README.md` and `backend/README.md`: document the passage contract,
  the eligibility coupling to the accepted catalog gate, and the baseline
  command. `/health` remains the only route.

Measured baseline (synthetic fixtures, reported not enforced):

- `python3 backend/scripts/validate_source_catalog.py backend/tests/fixtures/retrieval/catalog.json --as-of 2026-10-13`
  → exit 0, `(schema source-catalog-v1, 3 source(s) checked as of 2026-10-13)`.
- `python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0; `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`;
  3 eligible sources, 12 indexed passages, 0 excluded. Six source-anchored
  questions return the expected passage at rank 1 (including the unaccented
  `"solicitud unica"` variant); the deliberate synonym probe
  (`"¿Quién puede pedir las ayudas?"` vs the `titular de la explotación`
  passage) misses and is reported as a miss.
- Determinism: two `--json` runs are byte-identical (`diff` clean); repeated
  in-process searches return identical `(passage_id, rank, score)` tuples.
- Canonical empty corpus:
  `python3 backend/scripts/evaluate_retrieval.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5`
  → exit 0 with 0 eligible sources, 0 indexed passages, no questions; with
  `--eval` and no `--passages`, every question returns zero candidates
  (`hit@5 = 0.0`).
- Fail closed: expired (`valid_until 2026-01-01`), non-approved
  (`review_status pending`), and non-current (`lifecycle_status repealed`)
  catalogs raise `CatalogRejectedError` and the CLI exits 2; an unknown
  `source_id` exits 2 with `$.passages[0].source_id`.
- `cd backend && python -m pytest tests/test_retrieval.py` → 76 passed.
- `cd backend && python -m pytest` → 121 passed (76 new + 45 existing).
- `python3 -m py_compile backend/app/retrieval.py backend/scripts/evaluate_retrieval.py backend/tests/test_retrieval.py`
  → clean; `git diff --check` → clean.
- No network: a socket-guard test replaces `socket.socket` with a raising stub
  and still builds the index and searches successfully.
- Not run: Android/Desktop/Gradle checks (not applicable to this
  backend/knowledge feature) and no browser/API/E2E test (no user-facing or API
  flow; no persistent E2E framework exists).

Environment note: this worktree has no `python` on `PATH` and the system
interpreter has no `pytest`, so the pytest commands ran with the interpreter of
a temporary virtualenv (`python -m pytest` semantics) created outside the
repository. No dependency was added to `backend/requirements.txt` or the repo.

Limitations (honest):

- The evaluation set is tiny, synthetic, and authored by the implementer, so the
  baseline is a calibration starting point, not a legal-coverage or
  question-answering quality claim.
- Retrieval is lexical (BM25) only, so it misses synonyms and acronyms; the
  synonym probe above demonstrates the gap.
- Because the accepted catalog gate already rejects non-approved, non-current,
  and expired sources, the retriever's per-source eligibility re-check is
  defense in depth: with a valid catalog the
  `excluded_passages_ineligible_source` count is normally 0. The predicate is
  unit-tested directly, and fail-closed refusal is tested with the ineligible
  catalog fixtures.
- `knowledge/passages.json` is intentionally not created; the passage format is
  exercised only by fixtures until a reviewed ingestion feature exists.

Independent validation (2026-10-13): accept. The validator reproduced the fixture
catalog gate (exit 0, 3 sources), the measured baseline (`hit@5 = 0.857 (6/7)`,
`recall@5 = 0.857`, `MRR = 0.857`), the per-question ranks (including the disclosed
synonym miss), byte-identical deterministic `--json` runs (also across hash seeds and
shuffled corpus order), hand-recomputed metrics, `k`-window semantics, the
empty-corpus zero-candidate case, and fail-closed exits `2` with located paths for
expired/non-approved/non-current catalogs and unknown `source_id`/keys. It confirmed
local-only behavior with a stricter independent socket/DNS/TLS guard and a
blocked-socket CLI subprocess, verified schema/validator sync and synthetic-only
fixtures with no real legal facts, and ran the suites in a venv outside the repo
(76 focused, 121 full) with no dependency added. Scope confirmed clean: `contracts/`,
the catalog validator, the `/health`-only service, client code, and `init.sh` are
untouched. Findings F1-F4 are non-blocking; F4 (flag an eval line that names an
unknown passage id) is optional harness hardening. Record:
`docs/validations/source_retrieval.md`.

## local_land_store — accepted

- `LandRepository` supports create/list/update/delete with stable generated ids,
  required trimmed names, explicit unknown attributes, and optional fields.
- `SharedPreferencesLandStorage` persists Android records; `FileLandStorage`
  persists Desktop/JVM records. Both use the shared versioned format.
- Malformed individual records are skipped during recovery; writes replace the
  complete snapshot.
- Verification: `/Users/jose/AndroidStudioProjects/Manijero/gradlew -p . :shared:jvmTest`
  passed. Android compilation could not run because the worktree has no Android
  SDK location (`ANDROID_HOME`/`local.properties`).

## add_land — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandState.kt`: pure
  `AddLandState` (raw name/municipality text, selected enums, name-error and save-error
  flags), `AddLandAction`, `reduce`, and `toDraftOrNull()`. It keeps raw text for
  correction, trims only to validate and to build the `LandDraft`, leaves `areaHectares`
  and `notes` unset, and owns no ids, timestamps, or persistence rules.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt`: stateless
  Material 3 form with a required name field (error state plus plain-Spanish message),
  optional `Municipio (opcional)`, accessible `RadioButton` rows for `Riego` and
  `Producción` (both starting on `No lo sé`), a live-region save-failure message, one
  prominent `Guardar terreno` action, and `Cancelar` as the visible back control.
  Eight previews cover blank, name error, known values, save failure, long text,
  compact, wide, and 2x font scale.
- `shared/src/commonMain/composeResources/values/strings.xml`: all add-land labels,
  choices, errors, and the success confirmation.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `App(landRepository)`
  holds the `Chat`/`AddLand` destination, routes `Mis terrenos` to the form, performs the
  synchronous repository write, returns to the chat home with a plain-Spanish saved
  confirmation, and shows the failure message while keeping every entered value.
  `App()` (no argument) is retained for the iOS scaffold and previews; without a
  repository the lands action is unavailable instead of creating a store in common code.
- `androidApp/.../MainActivity.kt`: one `LandRepository(SharedPreferencesLandStorage(applicationContext))`.
- `desktopApp/.../main.kt`: one remembered `LandRepository(FileLandStorage(~/.manijero/lands-v1.txt))`.

Verification (2026-10-12):

- `./init.sh` passed and created the worktree `local.properties`, so Android checks could
  run for the first time in this checkout.
- `./init.sh --verify` (i.e. `:shared:jvmTest :shared:testAndroidHostTest
  :androidApp:assembleDebug :desktopApp:build`) passed: 21 shared JVM tests (0 failures),
  20 Android host tests (0 failures), `androidApp/build/outputs/apk/debug/androidApp-debug.apk`
  produced, Desktop app built.
- New tests: `AddLandStateTest` (11) — default `UNKNOWN` choices, blank/whitespace name
  rejected with no draft, trimmed name-only draft with no area/notes, `IRRIGATED`+`ORGANIC`
  mapping, deliberate `MIXED`, Unicode name, save failure retaining values for retry,
  error clearing on edit, and two lands surviving reopening. `AddLandDesktopStoreTest` (1)
  — the real `FileLandStorage` keeps a name-only and a known-attributes land after
  reopening.
- Desktop startup smoke: `./gradlew :desktopApp:run` launched `com.jamarglex.manijero.MainKt`
  with the injected file store and ran without startup errors until the session stopped it
  (Gradle reported the expected SIGTERM exit 143).
- Not verified by automated UI tests: interactive Android/Desktop clicking, screen-reader, and
  large-system-text behavior; no emulator, device, or Compose UI test harness exists yet. The
  spec defers this to `land_form_accessibility`, and it is reported here rather than claimed.

Independent validation (2026-10-12): accept. The validator re-ran `./init.sh --verify`,
`:shared:jvmTest` and `:shared:testAndroidHostTest` with `--rerun-tasks` (21 and 20 tests,
0 failures), `:androidApp:assembleDebug`, `:desktopApp:build`, and a Desktop startup smoke,
then confirmed scope discipline, `commonMain`-only product UI, no land-data or raw-exception
logging, and the copy contract. Record: `docs/validations/add_land.md`.

## suggested_questions — accepted

- Independent validator accepted (record: `docs/validations/suggested_questions.md`) after re-running
  `:shared:jvmTest --rerun-tasks` (ChatHomeStateTest 7/7), `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug`, and `:desktopApp:build`, and independently confirming the three shipped
  strings match the spec byte-for-byte with no unapproved deadline wording.
- `ChatHomeAction.SuggestedQuestionSelected(question: String)` sets `question` to the supplied
  text and clears `submittedQuestion`; the reducer performs no I/O and adds no dependency,
  ViewModel, route, or platform adapter.
- The three approved strings ship verbatim in
  `shared/src/commonMain/composeResources/values/strings.xml`
  (`chat_home_suggestion_solicitud_unica`, `chat_home_suggestion_sigpac`,
  `chat_home_suggestion_condicionalidad`); a Python byte-for-byte comparison against the spec's
  Content decision matched all three, and the unapproved deadline wording
  ("¿Hasta cuándo puedo cambiar mi solicitud?") is not shipped.
- `ChatHomeScreen` renders a plain-Spanish heading plus the three examples as full-width
  `OutlinedButton` controls in a vertical `Column` inside the existing 720dp content width.
- Verification commands:
  - `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; `ChatHomeStateTest` 7/7 (4 new).
  - `./init.sh --verify` → BUILD SUCCESSFUL; `:shared:jvmTest`, `:shared:testAndroidHostTest`
    (ChatHomeStateTest 7/7), `:androidApp:assembleDebug` (`androidApp-debug.apk`),
    `:desktopApp:build`.
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, debug APK): all three examples visible
  without sideways scrolling; tapping each filled the composer with the exact question and enabled
  `Preguntar`; submit showed only "Tu pregunta está lista para continuar."; re-selecting an example
  cleared the stale submitted message; at `font_scale 2.0` labels wrapped to two lines with no
  horizontal overflow.
- Desktop smoke: `:desktopApp:run` launched the shared `App()` and stayed alive ~50s with no
  runtime exception; interactive window/click inspection was not captured in this session.

## visual_foundation — accepted

What changed:

- New shared theme package `shared/src/commonMain/kotlin/com/jamarglex/manijero/theme/`:
  - `ManijeroColors.kt`: the ten `DESIGN.md` tokens plus the derived values, a fully specified
    `lightColorScheme(...)` (every documented role set explicitly, so no Material default can leak),
    `ManijeroSemanticColors` + `LocalManijeroSemanticColors` for the roles Material 3 lacks
    (caution, caution surface, strong olive; `danger` = `colorScheme.error`, `border` =
    `colorScheme.outline`), and the dependency-free WCAG `relativeLuminance`/`contrastRatio` helpers.
  - `ManijeroTypography.kt`: Material 3 `Typography` with the single documented `bodySmall`
    line-height override (16sp → 18sp); size, weight, letter spacing, and font family untouched.
  - `ManijeroTheme.kt`: `ManijeroTheme { }` (Material 3 theme + semantic local) plus review-only
    token-board previews at 1x and `fontScale = 2f`.
- `App.kt`: wraps the destination content in `ManijeroTheme` once (the shared composition root), and
  all seven previews use `ManijeroTheme`. `lands/AddLandScreen.kt`: all eight previews use
  `ManijeroTheme`. No layout, copy, spacing, or behavior changed; the Android/Desktop/iOS hosts stay
  theme-free so they inherit the one shared theme.
- `DESIGN.md`: added the derived-token table and the light-only decision to the "Visual foundation"
  section.
- Not changed: `MainActivity.kt`, desktop `main.kt`, `MainViewController.kt`, `strings.xml`, any
  Gradle file or the version catalog, backend/contracts, land storage, `init.sh`; no new module,
  framework, or dependency.

Verification (commands run from the repository root):

- `./init.sh --verify` → BUILD SUCCESSFUL.
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL:
  54 JVM tests / 0 failures (`ManijeroColorsTest` 10, `ManijeroTypographyTest` 4 new) and
  51 Android host tests / 0 failures (same 14 new theme tests).
- `./gradlew :androidApp:assembleDebug` and `./gradlew :desktopApp:build` → BUILD SUCCESSFUL
  (debug APK produced) as part of `--verify`.
- Centralization greps: no `Color(0x` outside `theme/`; no argument-less `MaterialTheme {`; the only
  `MaterialTheme(` call site is the `ManijeroTheme` wrapper; no
  `LocalMinimumInteractiveComponentSize`/`minimumInteractiveComponentSize` override; the theme is
  applied once in `App()`.

Honest gaps:

- Interactive Android/Desktop UI smokes (screenshots, greyscale non-color cue check, emulator
  `font_scale 2.0`, Desktop window resize/keyboard focus) were not run in this non-interactive
  session. They are covered by the review-only token-board preview and the pure contrast tests, and
  remain the manual checks for independent validation.
- Light-only by decision: no dark palette exists (`DESIGN.md` records this). Desktop OS-level text
  scaling is not wired in this repository, so enlarged-text evidence is preview-based
  (carried validator finding F3, owner `chat_accessibility`).
  
## grounded_answer_generation — accepted

Independent validator accepted (2026-10-13, record:
`docs/validations/grounded_answer_generation.md`). It reproduced the 100 focused /
221 full pytest passes, `py_compile`, `git diff --check`, the fixture CLI run
(exit 0; 5 answers, 8 claims, 0 ungrounded, 0 invented sources, 1 no-evidence,
invariants hold, 0 expect-mismatches), the literal feature-list verification
(plazo claim 1 = the `critical` rank-1 excerpt with the fictitious `42 días`
cited `[1]`; claim 2 = the rank-2 excerpt `[2]`), the canonical empty-corpus run
(exit 0; exit 2 with `--eval` naming unknown ids), byte-identical deterministic
`--json` runs (sha256 `f8345c12…e453`), and a stricter independent socket guard
that still produced the answer. It confirmed fail-closed paths (eligibility →
`policy_failed`, exit 1; `--fail-on-miss` opt-in), the assembled payload matching
`AskResponse`/`AnswerSource` with no retrieval-local leakage, the unchanged
retrieval baseline (`hit@5 = 0.857`), `contracts/validate_examples.py` passing,
synthetic-only labelled fixtures with no real legal fact, and that `contracts/`,
`retrieval.py`, `source_catalog.py`, `main.py`, `knowledge/source_catalog.json`,
`passages.schema.json`, `requirements.txt`, `init.sh`, and all client/shared code
are untouched with no repo dependency. Non-blocking findings carried forward:
F1 (prefix-only marker/`sources` invariant; fix before the hosted-model path or
`answer_source_cards`) and F2 (non-iterable `source_markers` raises `TypeError`
instead of returning `generation_error` at the model seam); N1 (`init.sh` banner
stale; the spec mandates no change); N3 (spec lists retrieval imports the module
deliberately omits).

What changed:

- `backend/app/generation.py` (new, standard-library only, offline): the *write*
  side of the accepted source gate.
  - `DraftAnswer(status, answer, source_markers)` mirrors the projected
    `{"status", "answer", "sources"}` shape so a future model adapter produces
    the same draft type; `verify_draft` is applied to it unchanged.
  - `verify_draft` rules: status must be `answered`; non-blank answer; at least
    one `[n]` marker; every marker must be a returned candidate number; declared
    `source_markers` must equal the inline markers; every sentence must carry a
    marker; every figure/date (± ISO and `dd/mm/yyyy` dates, thousands
    separators, decimal comma, percent) must appear in the text of the cited
    passage(s); a claim citing a `critical` passage must be a literal substring
    of that passage after whitespace/case/diacritic normalization; a
    legal-status assertion (starter phrase list) is a policy violation.
  - `ExtractiveGroundingGenerator` is the only enabled generator: one verbatim
    reviewed excerpt plus its marker per top candidate, no clock, no model. A
    hosted rephrasing path must implement `GroundingGenerator` and pass the same
    `verify_draft`.
  - `generate_grounded_answer` returns `Answered` only when the whole draft
    verifies, otherwise `NotAnswered(reason, issues, claims)` with reason
    `invalid_question`, `no_candidates`, `generator_abstained`,
    `grounding_failed`, `policy_failed`, or `generation_error`. A failing draft
    is discarded whole; no rejected-draft text is emitted.
  - Citation markers, the `sources` array (`[n]` = `sources[n-1]`, deduplicated
    ascending), the pinned lead-in and notice, and the seven accepted
    `AnswerSource` keys are all code-owned; retrieval-local fields never cross
    into the payload.
- `backend/scripts/evaluate_generation.py` (new): report-only CLI with `--catalog`,
  `--passages`, `--eval`, `--as-of`, `--k`, `--json`, `--fail-on-miss`.
  Grounding invariants are enforced (exit `1`); answer coverage is not, unless
  `--fail-on-miss` is passed. Exit `2` for unreadable/invalid input; an `--eval`
  line naming a passage id absent from the built index is a harness error
  (exit `2`), closing accepted finding F4.
- `backend/tests/test_generation.py` (new, 100 tests) plus synthetic fixtures
  `backend/tests/fixtures/generation/{catalog.json,passages.json,eval_questions.jsonl,drafts_ungrounded.json}`
  (2 approved sources, 4 labelled-synthetic passages, 2 of them `critical` with
  fictitious figures 42 and 1.200, 6 evaluation lines including an out-of-corpus
  one, and 13 rejected drafts keyed by issue code).
- `knowledge/README.md` and `backend/README.md`: document the generation
  boundary, the code-owned citation/notice rules, the enforced exit codes, the
  reviewer excerpt guidance, and the report command. `CONSTRAINTS.md` (new)
  records the two answer-grounding MUST rules. The spec gained an
  "Implementation findings" section.

Verification (commands run from the repository root unless noted):

- `cd backend && python -m pytest tests/test_generation.py` → 100 passed.
- `cd backend && python -m pytest` → 221 passed (121 existing + 100 new).
- `python3 -m py_compile backend/app/generation.py backend/scripts/evaluate_generation.py backend/tests/test_generation.py`
  → clean; `git diff --check` → clean (a trailing blank line accidentally added
  to `knowledge/README.md` was trimmed).
- `python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0: 2 eligible sources, 4 indexed passages, 0 excluded,
  `answers produced: 5`, `claims checked: 8`, `ungrounded claims: 0`,
  `invented sources: 0`, `no-evidence outcomes: 1`, `grounding invariants hold: yes`,
  `outcomes differing from expect: 0`. Every answered question prints its
  per-claim verdict and cited candidate numbers; the out-of-corpus line
  (`zzzz qqqq`) returns `no_candidates`.
- `python3 backend/scripts/evaluate_generation.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5`
  → exit 0 with 0 eligible sources, 0 indexed passages, "no evaluation questions
  supplied". With `--eval` and the empty catalog the index check exits `2`,
  naming the unknown ids (documented harness behavior).
- Enforced invariant, fail closed: a temporary passage set whose reviewed text
  contains a starter eligibility phrase → `outcome: policy_failed`,
  `claim 1: failed; cites [1] (eligibility_claim)`,
  `grounding invariants hold: no`, exit `1`. The 13 recorded rejected drafts each
  reproduce their expected issue code.
- Determinism: two `--json` runs are byte-identical (`diff` clean), sha256
  `f8345c124a3ba4ab0b2fd1e4947244b54e21b5cc2a289f024e13cf5b28a4e453`.
- Unchanged boundaries re-checked: `python3 contracts/validate_examples.py` →
  "Validated 2 request and 3 response examples against answer_api_contract"; the
  retrieval fixture baseline is unchanged at `hit@5 = 0.857 (6/7)`,
  `recall@5 = 0.857`, `MRR = 0.857`.

Not run and why:

- Android/Desktop/Gradle and `./init.sh --verify`: not applicable to this
  backend slice (no product UI, route, or Gradle input changed) and `init.sh`
  has no backend command.
- No browser/API/E2E check: there is no `/ask` route and no persistent E2E
  harness. The CLI is the manual smoke check for this feature.
- Environment: this worktree has no `python` on `PATH` and the system
  interpreter has no `pytest`, so the pytest commands ran with the interpreter of
  a temporary virtualenv created outside the repository. No dependency was added
  to `backend/requirements.txt` or the repo.

Limitations (honest):

- The checks are lexical: figure presence is not entailment, the eligibility
  check is a short phrase list, and semantic grounding plus conflict detection
  are explicitly deferred to `safe_abstention` and a later judge.
- The extractive default requires single-sentence excerpts; a multi-sentence
  excerpt whose trailing marker lands after the final period fails closed
  (`uncited_sentence`). Recorded in the spec and in `knowledge/README.md`.
- An excerpt containing a starter eligibility phrase is unanswerable through the
  extractive default (the verbatim claim is rejected). Fail closed and
  intentional; the reviewer guidance says to avoid such phrasing.
- Nothing about a canonical corpus changed: no `knowledge/passages.json` was
  created, and the fixture corpus is tiny, synthetic, and implementer-authored,
  so nothing here is a legal-coverage or answer-quality claim.
- `safe_abstention` was not implemented by this feature: it returned
  machine-readable reason codes only and no user-facing abstention copy. (The
  later `safe_abstention` feature, now accepted, consumes those codes and owns
  the pinned abstention copy.)

## land_list — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListState.kt`: pure
  `LandListState` (`lands`, `loadFailed`, `isEmpty`), `LandListAction`
  (`LandsLoaded`/`LoadFailed`/`ReloadClicked`), and `reduce`. `LandsLoaded` stores the supplied
  list exactly (order, identities, duplicate names — no sort/dedupe/rename) and clears
  `loadFailed`; `LoadFailed` clears `lands` and sets `loadFailed = true`, so a failed read never
  looks empty and stale rows never survive; `ReloadClicked` clears both before the caller re-reads.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt`: stateless
  `LandListScreen(state, onAddLand, onBack, onRetry, modifier, savedConfirmation)`. Plain,
  non-clickable rows show the exact name, municipality only when known, and always water and
  production with `UNKNOWN → No lo sé` and `MIXED → mixed copy`; rows use
  `mergeDescendants = true`; failure copy and the confirmation are `LiveRegionMode.Polite`;
  in the failure state `Añadir terreno` is withheld and a single `Reintentar` is offered.
  Eleven previews cover empty, two distinguishable, duplicate names, many, long text, failure,
  just-saved, compact (320dp), wide (900dp), and 2x font scale.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: new `LandList` destination and a
  single synchronous read site (`runCatching { repository.list() }` folded into
  `LandsLoaded`/`LoadFailed`, then reduced) invoked only on entry, retry, and after a save.
  `Añadir terreno` opens the unchanged `AddLandScreen`; `Cancelar` and a successful save return to
  the list with a reload and confirmation after a save. The intended `land_list` routing change
  removes the now-unreachable `ChatHomeScreen` `landSavedConfirmation` parameter, its block, and its
  preview. `App()` (iOS scaffold/previews) is unchanged; without a repository the lands action
  stays unavailable.
- `shared/src/commonMain/composeResources/values/strings.xml`: 9 new `land_list_*` keys (explanation,
  empty state, `Añadir terreno`, `Volver`, `Municipio`/`Riego`/`Producción` row lines, failure text,
  `Reintentar`) matching the spec copy verbatim, reusing `add_land_unknown`, `add_land_water_*`,
  `add_land_production_*`, `add_land_saved`, and `chat_home_lands`.
- Not changed: `Land`/`LandDraft`/`LandRepository`, the `land-store-v1` format, both storage
  adapters, `AddLandState`/`AddLandScreen` behavior, `MainActivity.kt`, `desktopApp/main.kt`,
  `MainViewController.kt`, Gradle files, `init.sh`, `theme/`, backend/contracts/knowledge, and
  unrelated features; no new module, dependency, ViewModel, coroutine, or navigation library.

Verification (commands run from the repository root):

- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **60 tests / 0 failures**
  (`LandListStateTest` 6 new).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **57 tests / 0 failures**.
- `./init.sh --verify` → BUILD SUCCESSFUL (`:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:androidApp:assembleDebug` producing `androidApp-debug.apk`, `:desktopApp:build`).
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400): the empty state names `Añadir terreno`
  with no fake row; saving `Los Olivos` (name only) returns to the list with
  `Riego: No lo sé` / `Producción: No lo sé` and the saved confirmation; a second land
  (Municipio: Martos, Regadío, Ecológico) adds a distinguishable row in creation order; force-stop
  + relaunch keeps both rows with no duplicates or stale confirmation; `Volver` returns to the chat
  home and `Cancelar` returns to the list creating no record; `font_scale 2.0` wraps all rows and
  actions with no horizontal overflow.
- Desktop run: no read happens at startup; with an unreadable store the plain-Spanish failure state
  shows only `Reintentar` and `Volver` with `Añadir terreno` withheld; `Reintentar` keeps the honest
  failure while unreadable and recovers once the store is fixed.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out" shared/src` returns no
  matches; no network call, permission, dependency, or module was added; no land id/area/notes are
  shown and no land data or exception text is surfaced.

Independent validation (2026-10-13): accept. The validator re-ran `./init.sh`, the focused and full
`:shared:jvmTest` (60/0), `:shared:testAndroidHostTest` (57/0), `./init.sh --verify`, and a full
`--rerun-tasks` Android+Desktop build, and byte-for-byte checked the nine new strings plus the reused
land vocabulary against the spec; it confirmed the empty-vs-failure distinction (an independent
throwing-storage probe showed `LoadFailed` is not `isEmpty`), the no-logging/no-network constraints,
and file-by-file scope discipline (only the intended `add_land` routing change). Record:
`docs/validations/land_list.md`. Findings F1-F6 are non-blocking and carried forward (F1 optional
confirmation guard, F2 post-save failure pairing, F2b corrupt-store-content robustness owned by
`local_land_store` hardening, F3 Android system back owned by `chat_accessibility`, F5 evidence
hygiene, F6 default-clock `createdAt`).

Honest gaps:

- No persistent E2E or Compose UI-test framework exists, so no automated UI/E2E coverage is claimed.
- TalkBack row-merge reading and Desktop keyboard focus/resize were not verified end-to-end
  (assistive access denied / no harness); the `mergeDescendants` and polite live-region attributes are
  present in code, and these checks are deferred to `chat_accessibility` / `land_form_accessibility`.
- The failure state requires the read itself to throw (a non-string `land_store` value or an
  unreadable file); a corrupt-content store decodes to an empty list under the accepted
  `LandStoreFormat.decode` contract, which `land_list` is forbidden to change (F2b).
- Spec-recorded limits stand: two identical name-only lands render identically; `areaHectares` and
  `notes` are not shown; the read is synchronous on the composition frame.

## safe_abstention — accepted

Spec: `docs/specs/safe_abstention.md`. Status is `accepted` after independent validation (record:
`docs/validations/safe_abstention.md`, 2026-10-13). Detection is lexical and conservative, and no
score threshold is a release gate.

What was added:

- `backend/app/abstention.py` — the stable 9-reason taxonomy (`ABSTENTION_REASONS`), one pinned
  plain-Spanish message per reason (`ABSTENTION_MESSAGES`, no digit, no date, always a next step), a
  frozen `Abstention` (`reason`, `generation_reason`, `issues`, `claims`; no text field, so copy is
  code-owned), the one-way `GENERATION_REASON_MAP` (`no_candidates`→`no_evidence`,
  `grounding_failed`→`insufficient_evidence`, `policy_failed`→`unsafe_request`, everything else
  unchanged, unknown→`generation_error`), `prepare_corpus` (a corpus-level `stale_evidence`
  `Abstention` when the catalog declares sources but `eligible_source_ids` is empty as of `as_of`),
  `answer_or_abstain` (pre-checks then the accepted `generate_grounded_answer`), the lexical
  presupposition check (`presupposed_identifiers` / `has_unsupported_presupposition`), the
  unit-anchored conflict check (`CRITICAL_UNITS` / `unit_values` / `find_unit_conflict`), and
  `to_abstention_response` (exactly the accepted `AskResponse` keys with `status: abstained`,
  `sources: []`, `land_ids_to_choose: []`).
- `backend/scripts/evaluate_abstention.py` — offline report-only CLI (stdlib only, no network, no
  model provider) with `--catalog/--passages/--eval/--as-of/--k/--json/--fail-on-miss`, per-question
  outcome/reason/generation-reason/issue-codes/message, corpus `current`/`not_current`, and the
  aggregate counters `abstentions_with_sources`, `abstentions_with_figures`,
  `abstention_invariants_hold`. Exit `0` reported, `1` on a violated abstention invariant or (only
  with `--fail-on-miss`) an expect mismatch, `2` on unreadable/invalid input or arguments.
- `backend/tests/test_abstention.py` — 178 focused tests (taxonomy/copy, payload shape, every
  generation reason mapped, `prepare_corpus` current/stale/hard-error, false premise hit/miss, unit
  conflict vs different units, generator-never-called, determinism, socket guard, content-silent
  diagnostics, CLI 0/1/2, fixture hygiene, accepted-generation regression).
- `backend/tests/fixtures/abstention/{catalog.json,passages.json,eval_questions.jsonl,eval_questions_stale.jsonl}`
  — synthetic, labelled fixtures (7 passages: ordinary, identifier-present, two `critical` fictitious
  deadlines, a multi-sentence excerpt, a starter-eligibility excerpt, a `critical` fictitious amount).
  Every numeric line is marked `cifra inventada`; the only numbered reference is a deliberately
  impossible `999/2099`.
- `backend/README.md` and `CONSTRAINTS.md` — the abstention boundary, taxonomy table, CLI usage, and
  one MUST rule (an abstention may never carry a source, figure, or date, and its copy is code-owned).

Commands actually run and real results:

- `python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit `0`; `corpus: current`; eligible sources `2`, indexed passages `7`, excluded `0`; answered
  `3`, abstained `7`, `abstentions with sources: 0`, `abstentions with figures: 0`,
  `abstention invariants hold: yes`, `outcomes differing from expect: 0` (10 questions). Outcomes:
  answered for the solicitud/norma/importe questions; `conflicting_evidence` for the fictitious plazo
  question (`unit_conflict`; `critical` 30 días vs `critical` 45 días); `insufficient_evidence`
  (generation reason `grounding_failed`, issue `uncited_sentence`) for the multi-sentence excerpt;
  `unsafe_request` (generation reason `policy_failed`, issue `eligibility_claim`) for the
  starter-eligibility excerpt; `false_premise` for the `Real Decreto sintético` and the numbered
  `reglamento 999/2099` questions (`unconfirmed_presupposition`); `no_evidence` for `zzzz qqqq`;
  `invalid_question` for a blank question. Two `critical` passages about different units (a `días`
  deadline and a `euros` amount) still answer, so the accepted covered critical question is not
  over-abstained.
- Stale corpus: `python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/retrieval/catalog_expired.json --eval backend/tests/fixtures/abstention/eval_questions_stale.jsonl --as-of 2026-10-13 --k 5` (no `--passages`)
  → exit `0`; `corpus: not_current`; answered `0`, abstained `3`, every question `stale_evidence`
  (issue `stale_corpus`, `sources: []`, pinned message). Unit tests reproduce the same for
  `catalog_not_approved.json` and `catalog_not_current.json` and confirm the stale `Abstention` wins
  over an `invalid_question`. A structurally broken catalog, a malformed passage set, an unknown
  `source_id`, and an unreadable file stay hard errors (`CatalogRejectedError`/`PassageSetError`;
  CLI exit `2`), and the canonical empty `knowledge/source_catalog.json` still prepares a retriever
  with 0 sources and 0 passages.
- Literal feature-list verification with a two-line JSONL outside the repo: `¿Cuánto cuesta matricular un tractor viejo?`
  → `no_evidence` (generation reason `no_candidates`, `sources: 0`, message "No he encontrado esta
  información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal
  agraria o con tu cooperativa.") and `¿Qué dice el Real Decreto 123/2099 sobre el plazo de la solicitud?`
  → `false_premise` (issue `unconfirmed_presupposition`, `sources: 0`, message "No puedo confirmar ese
  dato con los documentos oficiales revisados. Comprueba el nombre o el número exacto con tu oficina
  comarcal agraria o con tu cooperativa."). `0` answered, `2` abstained, `0` with sources, `0` with
  figures, invariants hold, `0` expect-mismatches; no invented legal fact appears. The same
  identifier present in a candidate does not trigger the check (the `norma` question still answers).
- Exit contract and determinism: `--fail-on-miss` → exit `0` on the fixtures and exit `1` on a
  deliberately mismatched expectation while printing byte-identical output; without the flag the
  mismatch still exits `0`; `--k 0` → exit `2` ("--k must be a positive integer"); a malformed eval
  line, an eval file with no questions, an invalid `--as-of`, a missing catalog, and a missing or
  malformed passage set each exit `2` with empty stdout. Two `--json` runs are byte-identical
  (`cmp` exit `0`). A payload that leaks a source, a land choice, a blank/over-long message, a digit
  or a date, a non-`abstained` status, or an off-taxonomy reason makes the CLI exit `1`.
- Tests: `cd backend && python -m pytest tests/test_abstention.py` → **178 passed**;
  `cd backend && python -m pytest` → **399 passed** (221 existing + 178 new); `python3 -m py_compile backend/app/abstention.py backend/scripts/evaluate_abstention.py backend/tests/test_abstention.py`
  → clean; `git diff --check` → clean.
- Offline and content-silent: tests monkeypatch `socket.socket` to raise and the pipeline still
  abstains in both `prepare_corpus` and `answer_or_abstain`; a test asserts `abstention.py` imports
  no `socket`/`urllib`/`httpx`/`requests`; a test asserts no question text, excerpt text, or figure
  number reaches the issue diagnostics or the emitted message; a recorded generator draft is
  discarded whole.
- Regression boundaries unchanged: generation CLI → exit `0`, `5` answers, `8` claims, `0`
  ungrounded, `1` no-evidence; retrieval CLI → `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`,
  `MRR = 0.857`; the 6 accepted generation eval questions re-run through `answer_or_abstain` still
  resolve exactly as their expects say; `python3 contracts/validate_examples.py` → "Validated 2
  request and 3 response examples against answer_api_contract".
- Change scope: `git status --porcelain` shows only `backend/README.md`, `CONSTRAINTS.md`,
  `feature_list.json`, and `PROGRESS.md` modified (`backend/README.md` +54 / `CONSTRAINTS.md` +13
  insertions) plus the new paths; `contracts/`, `backend/app/generation.py`,
  `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`,
  `backend/scripts/evaluate_generation.py`, `backend/tests/test_generation.py`, `knowledge/`,
  `backend/requirements.txt`, `init.sh`, and all client/shared code are unmodified (checked per path).

Honest gaps:

- No `/ask` route and no persistent E2E harness exist, so the abstention reason stays observable only
  through this CLI and these tests until the route slice exists; no browser/API/E2E test was run.
- Android/Desktop/Gradle and `./init.sh` checks were not run: no product UI, route, or shared code
  changed and `init.sh` has no backend command.
- Detection is lexical, not semantic: a retrieval miss, or two unrelated `critical` passages that
  share a unit, can abstain. `prepare_corpus` treats any declared-but-all-ineligible catalog as
  `stale_evidence` even when the ineligibility comes from a malformed currency field (structurally
  broken catalogs stay hard errors). Widening conflict detection requires measurement, not assumption.
- No calibrated threshold and no trap-set measurement is introduced (`land_safety_evaluation` owns
  both); the tiny implementer-authored synthetic corpus means no reason code here is a coverage or
  answer-quality claim.
- Carried-forward accepted generation finding F2 (non-iterable `source_markers` at the model seam) is
  unchanged.
- Environment note: this worktree has no `python` on `PATH` and the system interpreter has no
  `pytest`, so pytest ran from a temporary venv outside the repository (Python 3.9.6) with the repo's
  own `backend/requirements.txt` installed into it; no dependency was added to the repo.

Independent validation (2026-10-13): accept. The validator did not trust the implementer report and
reproduced the 178 focused / 399 full pytest passes, `py_compile` and `git diff --check`, both CLI runs
(current corpus: 3 answered / 7 abstained, 0 abstentions with sources or figures, invariants hold; and
expired/non-approved/non-current catalogs: every question `stale_evidence`), the fail-closed exit `2`
cases with located JSON paths, the exit `0`/`1` contract, byte-identical `--json` runs (also under two
`PYTHONHASHSEED` values), an independent `jsonschema` validation of every payload against the
dereferenced `AskResponse`, a byte-for-byte comparison of the nine pinned messages plus digit/date and
eligibility checks, its own out-of-corpus, false-premise (present/absent/different-instrument/location-
only), and same-unit-versus-different-unit conflict probes, generator provenance (0 generator calls for
invalid/no_evidence/false_premise/conflict; rejected drafts never emitted), and a stricter independent
`socket`/DNS guard that still abstains and answers. It confirmed the unchanged generation
(`5` answers, `8` claims, `0` ungrounded, `1` no-evidence) and retrieval (`hit@5 = 0.857 (6/7)`,
`recall@5 = 0.857`, `MRR = 0.857`) baselines, `contracts/validate_examples.py` passing with
`contracts/` untouched, `GET /health` the only route, synthetic labelled fixtures with no real legal
fact, and no repo dependency (pytest ran from an out-of-repo venv, Python 3.9.6). Findings N1-N4 are
non-blocking: N1 (evidence wording over-narrow about which files were modified; corrected here),
N2 (a structurally-plausible-but-semantically-invalid catalog can yield `stale_evidence` instead of a
hard error; matches spec rule 6, fails safe, owner a later catalog-hardening slice), N3
(`test_abstention.py:553` uses a real-looking statute id `7/2022`; a pure extractor literal, prefer an
impossible id for fixture-policy consistency), N4 (substring containment in the presupposition check
can under-abstain, e.g. `ley` inside `leyenda`; the prescribed lexical behaviour, to be measured in
`land_safety_evaluation`). Record: `docs/validations/safe_abstention.md`.

## network_error_recovery — accepted

What changed:

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatHomeState` gains
  `failure: RequestFailure?` and `failedQuestion: String?`, both kept **outside** `messages`, so a
  failure can never render as an assistant answer. `ChatHomeAction.RequestFailed` becomes
  `data class RequestFailed(val failure: RequestFailure)`, and the new `data object RetryClicked`
  re-emits `ChatEffect.Submit(failedQuestion)` only from `IDLE` with a retained failure, sets
  `SUBMITTING`, clears `failure`/`question`, and leaves `messages`/`failedQuestion` untouched, so a
  retry appends no second user message and a repeated failure stays retryable. `AskClicked`,
  `QuestionChanged`, `SuggestedQuestionSelected` and `ResponseReceived` clear the notice;
  `canAsk`/`isOverCharacterLimit`/`awaitingLandClarification` are unchanged.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerFailure.kt` (new): the
  `RequestFailure` enum (`COULD_NOT_REACH_SERVICE`, `SERVICE_ERROR`) plus the two payload-free
  exceptions `AnswerServiceUnavailableException`/`AnswerServiceErrorException` with fixed literal
  messages, so no URL, body, or question text can travel with a failure.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/AnswerService.kt`: `answerHttpClient`
  sets `expectSuccess = true` and installs bounded `HttpTimeout` (`REQUEST_TIMEOUT_MILLIS` 15_000,
  `CONNECT_TIMEOUT_MILLIS` 10_000, `SOCKET_TIMEOUT_MILLIS` 15_000; the request bound is a parameter
  only so tests can use a tiny one). `KtorAnswerService.ask` rethrows `CancellationException` and
  translates `ResponseException`/`ContentConvertException`/`SerializationException` to the service
  error and `kotlinx.io.IOException` (timeout, connect, socket, I/O) to the unavailable signal.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`: maps
  `AnswerServiceUnavailableException` to `RequestFailed(COULD_NOT_REACH_SERVICE)` and every other
  exception (including `UnavailableAnswerService`'s `IllegalStateException`) to
  `RequestFailed(SERVICE_ERROR)`; still rethrows `CancellationException`; no logging was added.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatFailureNotice` renders from
  `state.failure` after the transcript — themed `errorContainer` fill with an `error` border, the
  `onErrorContainer` message, and a `Reintentar` button using the `error`/`onError` pair. It is a
  polite live region, carries no `Asistente` label, is never a `ChatMessage`, and is mutually
  exclusive with the working indication. Two previews added (unreachable; service error at
  `widthDp = 320`, `fontScale = 2f`).
- `shared/src/commonMain/composeResources/values/strings.xml`: `chat_home_failure_unreachable`,
  `chat_home_failure_service`, `chat_home_retry` shipped byte-for-byte from the spec (verified with
  an XML parse + string comparison); `chat_home_working`, `chat_home_question_too_long`,
  `chat_home_needs_land_clarification`, `chat_speaker_you`/`chat_speaker_assistant` and
  `land_list_retry` are unchanged.
- `CONSTRAINTS.md`: new "Client request failure" MUST rule (a failed/unreached request is never an
  answer and recovery keeps the exact wording). `docs/specs/network_error_recovery.md`: four
  implementation findings (IF1-IF4). `docs/specs/chat_question_submission.md`: F2 recorded as closed
  from this side, F1 still owned by the `/ask` wiring slice.
- Not changed: `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`,
  `theme/`, any Gradle file or the version catalog, and `init.sh`; no new module, dependency, engine
  wiring, base URL, ViewModel, DI, or coroutine scope (Ktor `HttpTimeout` ships in `ktor-client-core`).

Verification (commands run from the repository root unless noted):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.ChatHomeStateTest" --tests
  "com.jamarglex.manijero.ChatConversationTest" --tests
  "com.jamarglex.manijero.chat.KtorAnswerServiceTest"` → BUILD SUCCESSFUL, 40 tests / 0 failures.
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **78 tests / 0 failures**
  (`ChatHomeStateTest` 25, `ChatConversationTest` 7, `KtorAnswerServiceTest` 8, plus the 38
  pre-existing).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **69 tests / 0 failures**.
- `./gradlew :desktopApp:build` and `./gradlew :androidApp:assembleDebug` → BUILD SUCCESSFUL
  (`androidApp-debug.apk` rebuilt); `./init.sh --verify` → BUILD SUCCESSFUL.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL, so the new `commonMain`
  Ktor/kotlinx-io usage does not break the pre-existing iOS target.
- Timeout evidence (carried finding R1 fallback): `HttpClient.plugin(HttpTimeout)` is not readable as
  a config in Ktor 3.1, so the test asserts installation (a missing plugin throws), that the three
  named constants are finite and differ from `HttpTimeoutConfig.INFINITE_TIMEOUT_MS`, and a stalled
  `MockEngine` with `requestTimeoutMillis = 200` fails in ~0.3 s as
  `AnswerServiceUnavailableException` instead of hanging. `expectSuccess` is proven behaviourally (a
  `500` carrying the accepted `answered` fixture body and a declared `422` both fail; the accepted
  `200` fixture still decodes on the same client), and an undecodable `200` body fails too.
- Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, rebuilt debug APK, shipped default
  `UnavailableAnswerService`): selecting an example and pressing `Preguntar` shows one `Tú` bubble
  with the exact question, **no** `Asistente` answer, the service-error notice
  ("El servicio no está disponible en este momento, así que todavía no tengo tu respuesta. Inténtalo
  otra vez dentro de un momento.") in the danger colours with a red `Reintentar`, and the exact
  wording still in the composer; `Reintentar` returns to the same single-notice state with still
  exactly one user message and no duplicate; selecting another example clears the notice and refills
  the composer. Screenshots were inspected and deleted.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src androidApp/src
  desktopApp/src` → no matches (exit 1). The new exception messages are fixed literals and the Ktor
  messages (which name the endpoint) are never rethrown, logged, or shown; no network call other than
  the existing `POST /ask` was added.

Honest gaps:

- A live network timeout cannot be produced in the running apps until platform `/ask` engine/endpoint
  wiring exists (carried finding F1, separate owner). The `COULD_NOT_REACH_SERVICE` notice therefore
  has no on-device screenshot; it is covered by the `MockEngine` timeout probe, the installed-constant
  assertions, and the reducer/transport tests.
- The Desktop app launched the shared UI (`MainKt` frontmost, no exception in the run log) but an
  interactive Desktop click-through/screenshot of the notice was not captured in this non-interactive
  session.
- No Compose UI-test harness exists, so no automated UI or E2E coverage is claimed; the observable
  working state during a retry is too brief to capture on the default path (`UnavailableAnswerService`
  throws synchronously).
- Recorded behaviour: `RetryClicked` clears the composer as specified, so a draft typed during the
  failed request and left unsent is discarded by an explicit retry; the person can instead press
  `Preguntar` with that draft, which dismisses the notice (spec finding IF1).
Independent validation (2026-10-13): accept. The validator re-ran the acceptance checks with
`--rerun-tasks` (contract validator; focused three-class run 40/0; `:shared:jvmTest` 78/0;
`:shared:testAndroidHostTest` 69/0; `:desktopApp:build`; `:androidApp:assembleDebug`;
`:shared:compileKotlinIosSimulatorArm64`; `./init.sh --verify` exit 0) and independently
reproduced the stalled-`MockEngine` request timeout (200 ms bound fired in 0.209 s as the
unavailable signal), the `500`/`422` and undecodable-`200` service-error paths with the `200`
fixtures still decoding, byte-for-byte equality of the three spec strings, the
failure-never-renders-as-an-answer invariant, retry with no duplicate user message and exact
wording retention, and scope discipline (no new module/dependency/Gradle/contract/backend/land/
theme/`init.sh` change). It confirmed on the resolved `kotlinx-io-core-jvm` artifact that
catching `kotlinx.io.IOException` also catches `java.io.IOException` and its timeout subclasses,
so real unreachable-service failures map to the correct notice, and found no leak. Non-blocking
findings N1-N5 recorded; F1 (platform `/ask` engine/endpoint wiring) stays with its own slice and
F2 (bounded timeout) is closed from this side. Record:
`docs/validations/network_error_recovery.md`.

## edit_land — accepted

Feature: `edit_land` (`area: lands`). Spec: `docs/specs/edit_land.md`. Accepted by independent
validation (record: `docs/validations/edit_land.md`); the implementation and self-verification below
were produced by the implementer and are reproduced/confirmed by the validator.

Independent validation (accept): re-ran `./init.sh`, the focused three-class run (`20/0`), the full
`:shared:jvmTest --rerun-tasks` (**98/0**, 14 classes), `:shared:testAndroidHostTest --rerun-tasks`
(**87/0**, 11 classes), `./init.sh --verify`, and a full `--rerun-tasks` build (91 tasks, 0 from
cache); confirmed the accepted `add_land`/`land_list` suites and copy still pass and the `Editar`
affordance did not regress the non-clickable row. For the literal feature-list verification it wrote
and then deleted an independent scratch JVM probe against the real `FileLandStorage`: with two lands
saved and only the first edited, the snapshot's other record line was **byte-identical**, order
preserved, and the edited record kept its `id`/`createdAt`; it also reproduced the byte-identical
no-write on a `LAND_MISSING` (`null`) update, the blank-name no-draft/no-write path, the
emptied-municipality→absent and known→`UNKNOWN` round-trips, and the preserved `area`/`notes`. The
eight new Spanish strings and the `CONSTRAINTS.md` rule were checked byte-for-byte, `git diff --check`
was made clean, and six emulator screenshots were corroborated against the behavior. Non-blocking
findings: F1 (the implementer's `PROGRESS.md` trailing blank line, fixed here before the acceptance
commit), F2 (a spec sentence overstated the `Cancelar` re-read; the spec now matches the code and the
accepted `add_land` cancel path), F3 (no Compose UI-test harness, so the `App()` save-decision wiring
is inspection + smoke only), F4 (`LAND_MISSING` is a defensive/unit-tested branch), F5
(`updatedAtEpochMillis` still not meaningful — carried `land_list` F6), F6 (the interactive Android
smoke is implementer-produced; the validator corroborated the artifacts and code semantics).

What changed (implementer record):

- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandState.kt` (pure, no Compose
  or platform imports): `EditLandFailure { WRITE_FAILED, LAND_MISSING }`, `EditLandState` (the
  targeted `landId`, raw `name`/`municipality` text, the two enums, plus `preservedAreaHectares`
  and `preservedNotes` carried through because this short form neither collects nor shows them),
  `Land.toEditLandState()` (prefills verbatim, `null` municipality → empty field, `UNKNOWN` → the
  `No lo sé` choice), field/save/failure actions, `reduce` (field actions and `SaveClicked` clear a
  stale failure; `SaveFailed` only sets it), and `toDraftOrNull()` (blank trimmed name → `null`;
  emptied municipality → absent; trimmed name; area/notes preserved).
- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/EditLandScreen.kt`: stateless
  prefilled form that renders whatever state it gets, with the required name field (error state plus
  `Escribir un nombre…`), the optional municipality, the two accessible radio groups, a polite
  live-region failure message that distinguishes `WRITE_FAILED` from `LAND_MISSING`, one primary
  `Guardar cambios`, `Cancelar` as the visible back control, and 9 previews (prefilled name-only,
  known values, name error, write failure, missing land, long text, compact 320dp, wide 900dp, 2x
  font). It reuses the accepted `add_land_*` vocabulary and the shared `ChoiceGroup`/`ChoiceItem`.
- `LandListScreen.kt`: `onEditLand: (Land) -> Unit` added, `savedConfirmation: Boolean` replaced by
  `confirmation: LandListConfirmation?` with `enum class LandListConfirmation { ADDED, UPDATED }`
  (`ADDED` still renders `add_land_saved` byte-for-byte), per-row visible `Editar` button whose
  accessible description is `land_list_edit_description` with the land's exact saved name, the row
  card still non-clickable, the details still a merged descendant node, plus a "just updated"
  preview.
- `AddLandScreen.kt`: `ChoiceGroup`/`ChoiceItem` visibility only, `private` → `internal`.
- `App.kt`: `EditLand` destination, `editLandState: EditLandState?` and
  `landConfirmation: LandListConfirmation?`, the row edit action, and the single
  `repository.update(reduced.landId, draft)` call site inside the `SaveClicked` branch (never while
  composing, never at startup). A non-null result clears the edit state, sets `UPDATED`, re-reads the
  list, and returns; `null` shows the `LAND_MISSING` notice and a thrown failure shows
  `WRITE_FAILED`, both keeping the values on screen and navigating nowhere. `Cancelar` clears the
  state, returns to the list, and shows no confirmation. `App()` (no argument) is unchanged.
- `shared/src/commonMain/composeResources/values/strings.xml`: the eight new keys from the spec.
- New tests: `commonTest/.../EditLandStateTest.kt` (12), `commonTest/.../EditLandRepositoryTest.kt`
  (6, in-memory `LandStorage` fake), `jvmTest/.../EditLandDesktopStoreTest.kt` (2, real
  `FileLandStorage` in a temp dir).
- `CONSTRAINTS.md`: new "Land editing" MUST rule (one targeted record, untouched attributes carried
  through, preserved `id`/`createdAt`, no `create`/`delete` from an edit path, never report
  `null`/thrown as saved).

Commands actually run (repository root):

- `./init.sh` → exit 0 (Gradle 9.8.0 wrapper; `local.properties` present, so Android checks run).
- `./gradlew :shared:jvmTest --tests EditLandStateTest --tests EditLandRepositoryTest --tests
  EditLandDesktopStoreTest` → BUILD SUCCESSFUL; 20 tests / 0 failures
  (`EditLandStateTest` 12, `EditLandRepositoryTest` 6, `EditLandDesktopStoreTest` 2).
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; **98 tests / 0 failures** across 14 classes (was
  78). The accepted `add_land`/`land_list` suites are still green (`AddLandStateTest` 11,
  `LandListStateTest` 6, `LandRepositoryTest` 4, `AddLandDesktopStoreTest` 1).
- `./init.sh --verify` (`:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`) → BUILD SUCCESSFUL (exit 0); `androidApp-debug.apk` produced;
  `:shared:testAndroidHostTest` **87 tests / 0 failures** across 11 classes (was 69).
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build --rerun-tasks` → BUILD SUCCESSFUL, 91 tasks executed; same 98/0 and 87/0.
- Copy fidelity: a Python byte-for-byte comparison of the spec's XML block against
  `strings.xml` matched all eight new keys exactly, each appearing once; `land_list_edit_description`
  is used only as the `Editar` control's accessible description and never as body text.
- Privacy: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|System.out" shared/src` → no matches;
  no network call, permission, dependency, module, ViewModel, coroutine, or navigation framework was
  added (`strings.xml` + `shared/src` are the only product edits).
- `git diff --check` → clean.

Android emulator smoke (`Medium_Phone_API_35`, API 35, 1080x2400, fresh install + `pm clear`,
16 screenshots captured outside the repository):

1. `Mis terrenos` empty → `Añadir terreno` → saved `Los Olivos` (name only): the list shows the
   unchanged add confirmation, `Riego: No lo sé`, `Producción: No lo sé`, no `Municipio:` line, and a
   visible `Editar` whose node reads `Editar el terreno «Los Olivos»`. Saved `La Loma` with
   `Municipio: Martos`, `Regadío`, `Ecológico` → a second distinguishable row in creation order.
2. The row body is not clickable: tapping `La Loma alta` text left the screen on the list.
3. Editing `Los Olivos` only (prefilled form shows `Los Olivos`, empty municipality, and `No lo sé`
   selected in both groups) and typing `Los Olivos del camino` → back to the list with
   `Los cambios se han guardado en este dispositivo.` visible (polite live region), the corrected name
   in the **same first position**, and `La Loma` still showing `Municipio: Martos` / `Regadío` /
   `Ecológico`.
4. Editing `La Loma` (prefill confirmed: `Martos`, and the `checked` rows are exactly `Regadío` and
   `Ecológico`) → cleared the municipality and selected `No lo sé` in both groups → the row lost its
   `Municipio:` line and reads `No lo sé` for both, with the other land untouched.
5. `am force-stop` + relaunch → both records persist exactly as shown, no duplicates, no stale
   confirmation.
6. Blank name: cleared the name and saved → no navigation, no confirmation, the required message
   `Escribe un nombre para el terreno.` appeared, and the other edited values stayed on screen;
   correcting it to `La Loma alta` saved successfully.
7. `Cancelar` from a further edit with an edited name → returned to the list with no confirmation and
   the stored name unchanged.
8. `font_scale 2.0`: the list and the edit form wrap with no horizontal overflow (max text right edge
   1017 of 1080) and `Guardar cambios` / `Cancelar` are reachable by vertical scroll.

Desktop `:desktopApp:run` startup smoke: the app launched `com.jamarglex.manijero.MainKt` against the
injected `~/.manijero/lands-v1.txt` store and stayed running ~6.5 minutes with **0 exceptions** in the
run log until the session stopped it (`:desktopApp:run` then reported the expected non-zero exit 143 =
SIGTERM). Interactive Desktop clicking, keyboard-focus traversal, and window-resize checks were not
driven in this session.

Honest gaps:

- No Compose UI-test harness exists, so the `App()` save-decision wiring (the `LAND_MISSING` /
  `WRITE_FAILED` branches, the confirmation, and the re-read on return) is verified by code
  inspection plus the emulator smoke, not by an automated test. The reducer and the repository
  semantics are covered by the focused tests.
- The two failure branches are reachable only defensively (`LAND_MISSING` needs the record to vanish
  between the list read and the save), so they were unit-tested rather than reproduced on the
  emulator.
- Screen-reader behaviour (merged row details, the `Editar` description announcement) and
  low-digital-confidence usability were not verified; the spec defers that validation to
  `land_form_accessibility`.
- No persistent E2E command exists, so no E2E or automated UI coverage is claimed.
- `updatedAtEpochMillis` is still not meaningful: `update` receives no timestamp from the app
  because the project has no clock/date dependency (carried finding F6 from `land_list`).
- As the spec records, `area`/`notes` are preserved but neither shown nor editable from this form,
  and two identical-looking lands still rely on the prefilled name to tell them apart.

## response_states — accepted

What changed (all in shared `commonMain`):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `ChatMessage` gains
  assistant-only `answerStatus: AnswerStatus = AnswerStatus.answered`, documented as copied from the
  decoded `AskResponse.status`. `ResponseReceived` — the only assistant-entry creation site — passes
  `response.status` into the entry, so every assistant entry keeps the state it arrived with and
  rendering never depends on the mutable `lastResponseStatus` (which still drives only
  `awaitingLandClarification`). The non-empty-answer guard and the clarification path are unchanged.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `ChatMessageBubble` renders from
  `speaker` + `answerStatus` through an exhaustive `when`; `ChatBubble` gains defaulted
  `borderColor`/`stateLabel`/`stateLabelColor` (existing call sites unchanged) plus a private neutral
  `ChatAssistantCard` helper. The answered entry keeps the neutral `surface`/`outlineVariant`
  `Asistente` card (no confident affordance); the abstained entry uses
  `LocalManijeroSemanticColors.cautionSurface` for the fill, a `caution` border, the `Asistente` label
  in `onSurfaceVariant`, a visible `Sin respuesta segura` label in `caution`, and the verbatim body in
  `onSurface` — one merged semantics node and a `LiveRegionMode.Polite` region. `needs_land_clarification`
  stays a neutral card (defensive, exhaustive). Four new previews (answered, abstained, both states
  together, abstention at `widthDp = 320`/`fontScale = 2f`), all inside `ManijeroTheme`.
- `shared/src/commonMain/composeResources/values/strings.xml`: one added string,
  `chat_answer_state_abstained` = `Sin respuesta segura` (byte-for-byte equal to the spec); no existing
  string changed or deleted (`chat_home_submitted` left untouched).
- The server `answer` is rendered verbatim, so the code-owned lead-in/orientative notice is not
  duplicated and no source, marker, figure, date, land name, or client-authored next step is added. The
  client does not branch on an abstention reason: `AskResponse` is `additionalProperties: false` with
  five keys, so no reason reaches the client and all nine reasons share the one state label.
- `CONSTRAINTS.md`: new "Client response states" MUST rule (answer/abstention stay distinguishable, the
  per-entry `answerStatus` is copied from the decoded response, an abstention renders its code-owned
  message verbatim with a non-confident caution treatment and no added content, no answer gains a
  confident legal-certainty treatment).
- Not changed: `contracts/`, `backend/`, `knowledge/`, `lands/`, `androidApp/`, `desktopApp/`,
  `shared/src/iosMain/`, the theme source values (`theme/ManijeroColors.kt`/`ManijeroTheme.kt`), any
  Gradle file or the version catalog, and `init.sh`; no new module, dependency, endpoint, engine,
  navigation, ViewModel, DI, or coroutine scope.

Verification (commands run from the repository root):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --tests "…ChatHomeStateTest" --tests "…ChatConversationTest" --tests
  "…theme.ManijeroColorsTest"` → BUILD SUCCESSFUL, 46 tests / 0 failures.
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL, **82 tests / 0 failures** (was 78; `ChatHomeStateTest`
  25→28, `ChatConversationTest` 7→8, plus one `ManijeroColorsTest` contrast row).
- `./gradlew :shared:testAndroidHostTest` → BUILD SUCCESSFUL, **73 tests / 0 failures** (was 69; +4).
- `./gradlew :desktopApp:build :androidApp:assembleDebug` → BUILD SUCCESSFUL (`androidApp-debug.apk`
  rebuilt); `./init.sh --verify` → BUILD SUCCESSFUL; `./gradlew :shared:compileKotlinIosSimulatorArm64`
  → BUILD SUCCESSFUL.
- New tests: an answered response appends exactly one assistant entry carrying `answered`; an abstained
  response carries `abstained` with the pinned message verbatim; an earlier abstention keeps its state
  after a later answered reply (per-entry, not `lastResponseStatus`); the clarification test asserts no
  assistant entry; a fake `AnswerService` returning the accepted abstained shape through
  `ChatConversation` yields one user message, one assistant entry carrying `abstained`, the pinned
  message verbatim and no `failure`; one `ManijeroColorsTest` row asserts `onSurface` on
  `cautionSurface` = 14.58:1.
- Centralization/privacy: `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero`
  matches only under `theme/`; `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog" shared/src
  androidApp/src desktopApp/src` → no matches (exit 1).

Honest gaps:

- No rendered visual evidence: this is a non-interactive session with no Compose preview/UI-test
  runner, so the greyscale non-colour-cue check and the `widthDp = 320`/`fontScale = 2f` no-clipping
  claim are structural + compiled-preview based, not an inspected render. Owner: `chat_accessibility`.
- No on-device answered/abstained turn: the shipped default is `UnavailableAnswerService` and there is
  still no platform `/ask` route (carried finding F1), so a real turn would need a temporary
  non-committed fake; `:desktopApp:run` interactive smoke was not run. No E2E or automated UI coverage
  is claimed (none exists).
- Carried risk R5: `[1]`-style markers render verbatim until `answer_source_cards` ships cards; with
  the corpus still empty no real marker-bearing answer exists yet.

Independent validation (2026-10-13): accept. The validator re-ran the contract validator,
`:shared:jvmTest --rerun-tasks` (82/0), `:shared:testAndroidHostTest --rerun-tasks` (73/0),
`:desktopApp:build :androidApp:assembleDebug --rerun-tasks` (72 tasks, exit 0), `./init.sh --verify`
(exit 0), `:shared:compileKotlinIosSimulatorArm64`, the two greps, and `git diff --check`; it
recomputed the `onSurface`-on-`cautionSurface` pair independently (14.58) and byte-for-byte compared
the new string. It reproduced the per-entry behavior with its own temporary probe test (10 tests,
including an earlier abstention surviving a later answer while `lastResponseStatus` differs, a
mismatch-proof hand-built state, clarification appending no entry, and a failure never becoming an
answer) and confirmed the exhaustive speaker × status branch in `App.kt`, verbatim body rendering with
no added source/marker/figure/date/client next step, and the three distinct neutral/caution/danger
states. Scope confirmed clean with no logging. Non-blocking findings N1-N5 recorded (N1 closed here at
acceptance time; N2 rendered-evidence gap owned by `chat_accessibility`). Record:
`docs/validations/response_states.md`.

## remove_land — accepted

Feature: `remove_land` (`area: lands`). Spec: `docs/specs/remove_land.md`. Accepted by independent
validation (record: `docs/validations/remove_land.md`, 2026-10-13); the implementation and
self-verification below were produced by the implementer and are reproduced/confirmed by the
validator.

Independent validation (accept): re-ran `./init.sh`, the focused three-class run (`15/0`, forced
`--rerun-tasks` after a `FROM-CACHE` first run), `:shared:jvmTest --rerun-tasks` (**117/0**, 17
suites), `:shared:testAndroidHostTest --rerun-tasks` (**104/0**, 13 suites),
`:shared:compileKotlinIosSimulatorArm64 --rerun-tasks`, and `./init.sh --verify` (91 tasks, exit 0;
APK 35.8 MB + `desktopApp.jar`); byte-for-byte checked the eight new strings and the
`CONSTRAINTS.md` rule against the spec, and confirmed file-by-file scope discipline. For the literal
feature-list verification it wrote and then deleted an independent scratch JVM probe against the real
`FileLandStorage` (4/4): with two lands saved and only the first removed the snapshot's surviving
record line was **byte-identical** and the removed line gone; a second delete of an absent id returned
`false` with a byte-identical snapshot; a throwing write left the store untouched; and the last-land
removal reopened as an empty store. It also independently re-drove an Android emulator
(`Medium_Phone_API_35`, fresh install + `pm clear`): per-row `Eliminar` with the exact-name
accessibility description, a confirmation naming the land, `Cancelar` leaving the store
**byte-identical** (opening and cancelling wrote nothing), confirming removing exactly `Los Olivos`
with `La Loma`'s line byte-identical, force-stop + relaunch listing only `La Loma`, the last-land
header-only store + accepted empty state + successful re-add, and `font_scale 2.0` wrapping (max right
edge 1017/1080). It confirmed the identity-only confirmation payload, no logging/egress/permission,
the single `delete` call site inside the explicit-confirmation callback, and that a `false`/thrown
result is never reported as a removal. Non-blocking findings F1-F6 recorded (F1 the spec's
`LandDetails(land)` superseded by the documented `(municipality, waterRegime, productionMethod)`
extraction; F2 stacked full-width row buttons vs the one-line sketch; F3 no Compose UI-test harness —
happy/cancel/last-land covered by the validator's emulator run, failure paths by its probe, durable UI
coverage owed to a future accessibility-style feature; F4 unreachable null-repository dead branch;
F5 no `BackHandler`, matching the accepted add/edit screens; F6 carried `createdAtEpochMillis`
default `0`).

What changed:

- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandState.kt`: pure
  `RemoveLandState(landId, name, municipality, waterRegime, productionMethod, failure)`,
  `RemoveLandFailure { WRITE_FAILED, LAND_MISSING }`, `RemoveLandAction` (`RemoveClicked`,
  `RemoveFailed`), `reduce`, and `Land.toRemoveLandState()`. The targeted id is the only record the
  state may delete; the name and identity fields are copied verbatim (an `UNKNOWN` value stays
  `UNKNOWN`, an absent municipality stays absent) and no area, notes, or timestamp is carried.
  `RemoveClicked` clears a previous failure and performs no I/O by itself.
- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/RemoveLandScreen.kt`: stateless
  `RemoveLandScreen(state, onRemove, onCancel, modifier)`. It shows the `Eliminar terreno` heading,
  one confirmation sentence naming the exact saved land (`remove_land_confirm`), the land's known
  details through the shared `LandDetails` block in one merged semantics node, a polite live-region
  failure line (`colorScheme.error`), the single primary action `Eliminar el terreno` carrying the
  `danger` pair (`error`/`onError`) together with its text label, and `Cancelar` as the secondary back
  control. Eight previews: name-only, known-details, long text, write failure, missing land, compact
  (`widthDp = 320`), wide (`widthDp = 900`), and `fontScale = 2f`.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/LandListScreen.kt` (declared
  cross-feature changes): `LandListScreen` gained the required `onRemoveLand: (Land) -> Unit`, each
  row gained its own visible full-width `Eliminar` `TextButton` whose accessible description is
  `land_list_remove_description` with the land's exact saved name (the row card stays non-clickable
  and the details stay a merged node), `LandListConfirmation` gained `REMOVED` rendered with
  `remove_land_removed` (`ADDED`→`add_land_saved` and `UPDATED`→`edit_land_saved` unchanged), the
  row's detail lines and their label mapping were factored into one `internal @Composable
  LandDetails(municipality, waterRegime, productionMethod)`, and a “just removed” preview was added.
  The `LandDetails` signature takes the three detail fields rather than a whole `Land`, because the
  confirmation state deliberately carries no full `Land` and building a fake one (ids/timestamps)
  would invent data the screen must not show; behavior and copy of the list are otherwise unchanged.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: `AppDestination` gained `RemoveLand`
  (KDoc updated), `App()` owns `removeLandState: RemoveLandState?`, the row's `Eliminar` action sets
  `removeLandState = land.toRemoveLandState()`, clears the confirmation, and navigates (writing
  nothing), and the destination renders the confirmation and calls `LandRepository.delete(id)` exactly
  once on an explicit `Eliminar el terreno`. Success clears the state, sets
  `LandListConfirmation.REMOVED`, re-reads the list, and returns to `Mis terrenos`; a `false` result
  sets `LAND_MISSING`, a thrown failure sets `WRITE_FAILED`, and both keep the confirmation on screen
  with no confirmation and no navigation. `Cancelar` clears the state, returns to the list, shows no
  confirmation, and writes nothing. `App()` (no argument) and the platform entry points are unchanged,
  so the `RemoveLand` destination stays unreachable when no repository is injected.
- `shared/src/commonMain/composeResources/values/strings.xml`: the eight spec keys
  (`land_list_remove`, `land_list_remove_description`, `remove_land_title`, `remove_land_confirm`,
  `remove_land_remove`, `remove_land_removed`, `remove_land_failed`, `remove_land_missing`). No
  existing string changed or was removed.
- `CONSTRAINTS.md`: one new “Land removal” MUST rule (delete exactly one record by its local id
  through `LandRepository.delete`, never rewrite/reorder another record, never call `create`/`update`
  from a removal path, remove nothing before an explicit confirmation that names the land, and never
  report a removal that `delete` did not confirm).
- Not changed: `Land.kt`, `LandRepository.kt`, the storage adapters and `land-store-v1`,
  `LandListState.kt`, `AddLandState.kt`/`AddLandScreen.kt`, `EditLandState.kt`/`EditLandScreen.kt`,
  `MainActivity.kt`, `desktopApp/main.kt`, `MainViewController.kt`, Gradle/version catalog, `init.sh`,
  `theme/`, backend/contracts/knowledge. No new module, dependency, ViewModel, coroutine,
  dialog/snackbar, navigation framework, network call, or permission.

Removal-path decision (recorded): one path — confirm first, then a single permanent `delete(id)`. No
undo, archive, trash, bulk removal, or restore. Nothing is lost by accident because the row control
opens a confirmation that names the land and the destructive action is a second deliberate choice;
there is no snackbar/undo infrastructure, and re-inserting a removed record would need a new
persistence capability (the accepted `create` generates a new id and the add/edit forms do not collect
`areaHectares`/`notes`). The copy therefore states plainly that removal cannot be undone instead of
promising a recovery that does not exist.

Verification (commands run from the repository root):

- `./init.sh` → created the worktree `local.properties` (`sdk.dir=/Users/jose/Library/Android/sdk`)
  and reported the current feature state; exit 0.
- Focused `./gradlew :shared:jvmTest --tests …RemoveLandStateTest --tests …RemoveLandRepositoryTest
  --tests …RemoveLandDesktopStoreTest` → BUILD SUCCESSFUL; 15 tests / 0 failures
  (`RemoveLandStateTest` 8, `RemoveLandRepositoryTest` 5, `RemoveLandDesktopStoreTest` 2).
- `./gradlew :shared:jvmTest` → BUILD SUCCESSFUL; 117 tests / 0 failures across 17 suites, including
  every accepted land suite (`LandRepositoryTest` 4, `AddLandStateTest` 11, `LandListStateTest` 6,
  `EditLandStateTest` 12, `EditLandRepositoryTest` 6, `AddLandDesktopStoreTest` 1,
  `EditLandDesktopStoreTest` 2) and the unchanged chat/theme suites.
- `./init.sh --verify` (`:shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug
  :desktopApp:build`) → BUILD SUCCESSFUL (91 tasks); `:shared:testAndroidHostTest` 104 tests /
  0 failures across 13 suites, `androidApp/build/outputs/apk/debug/androidApp-debug.apk` produced,
  `desktopApp/build/libs/desktopApp.jar` built.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL (the `App()`/`commonMain`
  change compiles for iOS).
- Byte-for-byte string check: a Python comparison of the spec's XML block against
  `composeResources/values/strings.xml` matched all eight new keys exactly (`ALL MATCH`), and
  `add_land_saved`/`edit_land_saved`/`land_list_edit` are unchanged.
- `git diff --check` → clean; no `Color(0x` outside `theme/`.
- Privacy: `grep -rn "println|Log\.|Logger|printStackTrace|System.out" shared/src androidApp/src
  desktopApp/src` → no matches; no `uses-permission` in any source manifest and the merged debug
  manifest declares no network permission.

Android emulator smoke (`Medium_Phone_API_35`, 1080x2400, fresh install + `pm clear`, screenshots
outside the repo):

- Saved two lands (`Los Olivos` name-only; `La Loma` with `Municipio: Martos`, `Regadío`,
  `Ecológico`); each row shows visible `Editar` and `Eliminar` controls and the row card itself is not
  clickable; the `Eliminar` control's accessibility description is `Eliminar el terreno «Los Olivos»`.
- Selecting `Eliminar` on `Los Olivos` shows a confirmation naming `Los Olivos` with `Riego`/
  `Producción` lines, `Eliminar el terreno`, and `Cancelar`. `Cancelar` returned to the list with both
  lands and no confirmation, and the SharedPreferences store was byte-identical before and after
  (`diff` clean), so opening and cancelling wrote nothing.
- Confirming removal returned to `Mis terrenos` showing only `La Loma` with every value intact
  (`Municipio: Martos`, `Riego: Regadío`, `Producción: Ecológico`) and the plain-Spanish
  `El terreno se ha eliminado de este dispositivo.`; the store became
  `land-store-v1\nland--2a7c7aa4c1961ac1|La Loma|Martos|IRRIGATED|ORGANIC|||0|0` — the surviving
  record's encoded line byte-identical to before and the removed record absent.
- Force-stop + relaunch listed only `La Loma` (the literal feature-list verification: only the removed
  land is absent from future lists).
- Removing the last land left the store as the valid header-only `land-store-v1` snapshot, showed the
  accepted empty state naming `Añadir terreno` plus the removed confirmation, and a new land
  (`Olivar Nuevo`) could still be saved afterwards. `Volver` returned to the chat home.
- `font_scale 2.0`: the list rows, both controls, and the confirmation screen wrapped with no
  clipping or horizontal overflow (max text right edge 1017 of 1080) and the screen scrolled
  vertically.

Honest gaps and non-blocking findings:

- No undo and no backup: a confirmed removal is permanent and local-only, and the app offers no
  recovery; if `areaHectares`/`notes` were stored they are lost with the record (neither the add nor
  the edit form collects them). The copy says removal cannot be undone instead of promising a
  recovery that does not exist.
- `RemoveLandFailure.LAND_MISSING` is a defensive branch, reachable only if a stored record
  disappears between the list read and the confirmation (an external edit of the Desktop file or a
  malformed line dropped by `LandStoreFormat.decode`); it is covered by unit tests, not normal use.
  The `WRITE_FAILED` branch is likewise unit-tested; neither failure path was reproduced on the
  emulator because the accepted storage adapters write successfully.
- Two lands that share a name, have no municipality, and are unknown still render as near-identical
  rows (the accepted `land_list` limitation); the confirmation repeats the same known details.
- The list read and the delete are synchronous on the composition frame, acceptable for a bounded
  local land count; lazy loading, background I/O, and bulk removal are out of scope.
- No Compose UI-test harness and no persistent E2E command exist, so the `App()` removal-decision
  wiring (`LAND_MISSING`/`WRITE_FAILED`, the confirmation, the re-read on return) is covered by code
  inspection plus the emulator smoke, not an automated test; no E2E or automated UI coverage is
  claimed.
- No screen-reader session was captured; the `Eliminar` control's `contentDescription` and the merged
  details node were confirmed from the accessibility tree dump, and a full accessibility audit of the
  removal flow stays with a follow-up (neither `land_form_accessibility` nor `chat_accessibility`
  depends on `remove_land`).
- Carried finding from `land_list` (F6): `createdAtEpochMillis` is still the default `0` because no
  clock is injected; unchanged by this feature.
  
## answer_source_cards — accepted

Spec: `docs/specs/answer_source_cards.md`. Accepted by independent validation (2026-10-13, record:
`docs/validations/answer_source_cards.md`).

What changed (all in shared `commonMain`, plus docs):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/CitationPresentation.kt` (new; pure,
  Compose-free, stdlib-only): `AnswerSegment` (`Text`/`Reference`), `SourceCard`
  (`number`/`title`/`issuingBody`/`location`/`verifiedOn`/`excerpt`/`link`),
  `AnswerSourcePresentation`, `answerSourcePresentation(status, answer, sources)`,
  `openableOfficialUrl(url)`, and `formatVerificationDate(isoDate)`. A reply is *conforming* only
  when its distinct canonical `[n]` markers are exactly `1..sources.size`; then each marker becomes a
  `Reference(n)` and the cards are numbered by payload position. Anything else (non-`answered`,
  absent, sparse, out-of-range, non-numeric, or leading-zero markers, or unexpected `sources`) fails
  closed: no marker is rewritten, no card is numbered, and the single text segment is the body
  exactly as received, so replacing each `Reference(n)` with `[n]` reproduces `answer` byte-for-byte.
  `openableOfficialUrl` returns the URL unchanged only for `https://` with a non-blank dotted host
  and no whitespace/control char (`http`, `javascript:`, `mailto:`, blank, hostless refused; no
  client-side domain allowlist). `formatVerificationDate` converts a strict `yyyy-MM-dd` with a
  plausible month/day to `dd/MM/yyyy` and returns any other shape unchanged.
- `ChatHomeState.kt`: `ChatMessage` gains assistant-only `sources: List<AnswerSource> = emptyList()`;
  `ResponseReceived` (the only assistant-entry creation site) passes `response.sources` unchanged, so
  nothing is rendered from the mutable `lastResponseStatus`.
- `App.kt`: `ChatBubble` gains a defaulted `annotatedText: AnnotatedString? = null`; the answered
  branch renders the neutral `Asistente` card with superscript reference numerals
  (`BaselineShift.Superscript`, `onSurfaceVariant`) plus a `SourceCardsSection`/`SourceCardView` that
  shows `Fuente n`, title, `Publica:`, `Parte del documento:`, `Comprobado el …`, and the excerpt in
  an always-visible `surfaceVariant` block — all inside one `mergeDescendants` node — then one
  `Button` (`Abrir documento oficial`) with a source-naming `contentDescription` whose `onClick` is a
  best-effort `runCatching { LocalUriHandler.current.openUri(link) }`; a `link == null` card shows the
  pinned unavailability line instead. No badge, success colour, or "verificado" affordance was added.
  Four previews refreshed/added (answered, two cards, both states, and a 320dp/2f card), all inside
  `ManijeroTheme`, with the accepted fixture source and markers added to the preview-only samples.
- `shared/src/commonMain/composeResources/values/strings.xml`: the nine pinned strings
  (`chat_source_section_title`, `chat_source_label`, `chat_source_issuing_body`,
  `chat_source_location`, `chat_source_verified_on`, `chat_source_excerpt_label`, `chat_source_open`,
  `chat_source_open_description`, `chat_source_link_unavailable`); no existing string changed or
  deleted (`strings.xml` numstat 9/0; `chat_home_submitted` intact).
- New `commonTest/.../chat/CitationPresentationTest.kt` (23) plus `ChatHomeStateTest` 28→31 and
  `ChatConversationTest` 8→9.
- `CONSTRAINTS.md`: one "Client source cards" MUST rule (render only an entry's own decoded
  `sources`, never invent a source/excerpt/date/link, open only https, never render evidence on an
  abstention, never alter claim text). `docs/specs/response_states.md`: a one-line R5-closed note.
- Not changed: `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, `androidApp/`,
  `desktopApp/`, `shared/src/iosMain/`, any Gradle file or the version catalog, and `init.sh`; no new
  module, dependency, endpoint, permission, ViewModel, DI, or logging.

Verification (commands run from the repository root unless noted):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **129 tests / 0 failures**
  (`CitationPresentationTest` 23, `ChatHomeStateTest` 31, `ChatConversationTest` 9; HEAD baseline 104,
  no test removed).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, **118 tests / 0 failures**.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL, 72 tasks
  executed, debug APK produced; `./init.sh --verify` → exit 0; `./gradlew
  :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- Centralization/privacy: `grep -rn "Color(0x"` matches only under `theme/`; the logging grep finds
  no matches; the raw-marker grep finds `[n]` only in preview-only sample constants (each paired with
  matching sources) and a comment, never in shipped copy; nine strings match the spec byte-for-byte;
  `git diff --check` clean.

Honest gaps:

- The feature-list link-reachability smoke (open each card's control and confirm the cited document
  opens) was **not** run: it needs a temporary non-committed fake `AnswerService` because the shipped
  default is `UnavailableAnswerService`, there is no `/ask` route, and `knowledge/source_catalog.json`
  is still empty, so the running apps cannot produce a real cited answer. The deterministic part is
  covered by unit tests and inspection (payload `url` → `card.link` unchanged → the single
  `LocalUriHandler.openUri(link)`); only the OS-level browser hand-off is unverified.
- No rendered visual evidence: greyscale non-colour-cue and `widthDp = 320`/`fontScale = 2f`
  no-clipping are structural + compiled-preview based, not an inspected render (owner:
  `chat_accessibility`). No E2E or automated UI coverage is claimed (none exists).
- Documented deviation: leading-zero markers (`[01]`) are treated as non-conforming so the
  byte-for-byte fidelity invariant holds. Recorded in the KDoc and a dedicated test; unreachable from
  the enabled `ExtractiveGroundingGenerator`, which emits canonical `[n]` only.
- Backend-owned follow-ups, deliberately not changed here: the `grounded_answer_generation` F1
  hardening (renumber or reject a non-prefix cited set) and the unconditional
  `[n] == sources[n-1]` sentence in `knowledge/README.md`. The client is safe either way; escalate
  before a hosted-model path.

Independent validation (2026-10-13): accept. The validator did not trust the implementer report and
re-ran the contract validator, the focused three-class run, `:shared:jvmTest --rerun-tasks` (129/0),
`:shared:testAndroidHostTest --rerun-tasks` (118/0), `:desktopApp:build :androidApp:assembleDebug
--rerun-tasks` (72 tasks, exit 0), `./init.sh --verify` (exit 0),
`:shared:compileKotlinIosSimulatorArm64`, and `:shared:iosSimulatorArm64Test --rerun-tasks` (129
tests / 0 failures, including `CitationPresentationTest` 23/0 on Kotlin/Native — obtained after
temporarily stripping a pre-existing comma-in-test-name error in two unrelated files, which it then
reverted to HEAD). With its own 11-test probe it reproduced byte-for-byte text fidelity (reordered,
repeated, trailing, newline-edged markers), the non-conforming/abstention fail-closed paths, the F1
non-prefix case, card field/order mapping, a URL matrix (4 accepted / 16 refused) and a date matrix,
and a three-turn per-entry state ending in a malformed abstention; it confirmed zero
`lastResponseStatus` occurrences in `App.kt`, byte-for-byte the nine strings, the unchanged existing
strings, the `mergeDescendants` + separate labelled-button semantics, scope discipline (`contracts/`,
`backend/`, `knowledge/`, `theme/`, `lands/`, platform roots, Gradle, `init.sh` untouched), no
logging, and no `Color(0x)` outside `theme/`. Non-blocking findings N1-N7 recorded (N1 evidence
recorded at this acceptance; N2 un-run manual/render evidence disclosed and owned by
`chat_accessibility`; N3 no calendar-day check in the date formatter; N4 4-digit tokens never match;
N5 non-conforming payloads still show unnumbered cards; N6 per-composition call without `remember`;
N7 backend F1 handoff escalated). Record: `docs/validations/answer_source_cards.md`.

## minimal_land_context — accepted

Spec: `docs/specs/minimal_land_context.md`. Implemented and self-verified by the implementer, then
independently validated (`accept`, 2026-10-13; record: `docs/validations/minimal_land_context.md`).

What changed:

- New `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/LandContextBuilder.kt` (pure,
  standard-library only, Compose-free): `LandContextNeeds(waterRegime, productionMethod,
  municipality)`, `landContextNeeds(question)`, `minimalLandContext(land, needs)`,
  `landContextFor(question, lands)`, and `askRequestFor(question, lands)`. The decision is a pinned,
  reviewable vocabulary matched on **whole folded tokens** (lowercase plus a fixed accent table
  `á à ä â→a`, `é è ë ê→e`, `í ì ï î→i`, `ó ò ö ô→o`, `ú ù ü û→u`, `ñ→n`; tokens are maximal runs of
  letters/digits), so `agua` never matches `aguacate` and every term is at least four characters.
  Mode is `all_active` with every stored land in repository order whenever at least one land exists
  (no topic classifier gates it), and `general`/`lands: []` only when the list is empty, where
  `askRequestFor` delegates to the unchanged `generalAskRequest` so the no-land payload is
  byte-identical. A needed but unknown stored value is sent as `unknown`; an unset or blank
  municipality is always omitted; the local→contract enum mapping is an exhaustive `when` with no
  `else`, so a new stored value breaks compilation instead of being mis-sent. Property order, ids,
  and land order stay exactly as stored (no sort, dedupe, or rename), and `answerJson`
  (`explicitNulls = false`) omits every not-needed property from the wire payload.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: only `ChatEffect.request`
  changed — it now takes the lands explicitly (`fun ChatEffect.request(lands: List<Land>)`), so a
  call site cannot forget them while the reducer stays pure and `AskClicked`/`RetryClicked` are
  untouched.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatConversation.kt`: new
  `landsProvider: () -> List<Land> = { emptyList() }` constructor parameter (defaulted, so the
  existing `ChatConversation(service, scope)` construction keeps working) consumed in `submit` as
  `runCatching { landsProvider() }.getOrElse { emptyList() }`, so every submit **and** every retry
  uses the lands stored at that moment and a failing local read degrades to the accepted `general`
  request instead of turning a question into a failure (never logged, never surfaced).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the conversation is remembered with
  `landRepository` added to the keys and built with `landsProvider = { landRepository?.list().orEmpty() }`.
  No destination, screen, string, preview, or layout changed, so `strings.xml` stays byte-identical.
- Durable docs: `CONSTRAINTS.md` gained the "Client land context" MUST rule (ids and only the needed
  attributes; no name, note, area, timestamp, invented value, or placeholder; `unknown` instead of a
  guess; `general` only when no land is stored). `docs/specs/chat_question_submission.md` gained a
  "Follow-up status after `minimal_land_context`" note superseding its always-`general` statement.
- Not changed: `contracts/`, `backend/`, `knowledge/`, `lands/`, `theme/`, `strings.xml`,
  `shared/src/iosMain/`, the platform entry points, all Gradle files, and `init.sh`; no new module,
  dependency, ViewModel, navigation framework, coroutine API, permission, or network call.

Encoded request bodies (literal feature-list verification, from a temporary JVM probe that was then
deleted; the committed tests assert them byte for byte). Lands: `land-1` (name "Los Olivos",
municipality Martos, `IRRIGATED`, `ORGANIC`, area 12.5, a private note, non-zero timestamps) and
`land-2` (name only):

- `¿Puedo regar hoy?` →
  `{"question":"¿Puedo regar hoy?","land_context":{"mode":"all_active","lands":[{"id":"land-1","water_regime":"irrigated"},{"id":"land-2","water_regime":"unknown"}]}}`
  (the needed attribute only, both ids verbatim; no `name`, `notes`, `areaHectares`, timestamp,
  `municipality`, or `production_method` key appears anywhere).
- `¿Puedo producir en ecológico?` →
  `...{"lands":[{"id":"land-1","production_method":"organic"},{"id":"land-2","production_method":"unknown"}]}}`
- `¿En qué municipio está mi terreno?` →
  `...{"lands":[{"id":"land-1","municipality":"Martos"},{"id":"land-2"}]}` (the unset municipality is
  omitted, not sent as a placeholder).
- `¿Cuál es el plazo de la solicitud única?` (matches no vocabulary) →
  `...{"lands":[{"id":"land-1"},{"id":"land-2"}]}` (ids only, the lands are never dropped).
- No lands → `{"question":"¿Puedo regar hoy?","land_context":{"mode":"general","lands":[]}}`,
  byte-identical to the accepted `generalAskRequest` payload.

Commands actually run (repository root; all pass):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract".
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **162 tests / 0 failures / 19
  classes** (`LandContextBuilderTest` 13 new, `ChatConversationTest` 13, `ChatHomeStateTest` 31,
  `KtorAnswerServiceTest` 9, `CitationPresentationTest` 23, plus the unchanged land/theme suites).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, **148 tests / 0
  failures / 15 classes**.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → 72 tasks executed, BUILD
  SUCCESSFUL (`androidApp/build/outputs/apk/debug/androidApp-debug.apk`, 35,865,622 bytes).
- `./init.sh --verify` → exit 0 (91 tasks, BUILD SUCCESSFUL).
- Focused `:shared:jvmTest --tests LandContextBuilderTest/ChatConversationTest/ChatHomeStateTest/KtorAnswerServiceTest`
  → BUILD SUCCESSFUL.
- Tests added with none removed: `@Test` count 144 at HEAD → 162 (+13 `LandContextBuilderTest`,
  +4 `ChatConversationTest`, +1 `KtorAnswerServiceTest`). No log line was added (the land read and
  the request stay unlogged).

Privacy and scope checks:

- `grep -rn "println|Log\.|Logger|printStackTrace|NSLog|System\.out" shared/src androidApp/src desktopApp/src`
  → no matches.
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero | grep -v /theme/` → no
  matches; `MinimalLandContext` still has exactly the four contract properties; `strings.xml` numstat
  0.
- `git status --porcelain` (per path) confirms `contracts/`, `backend/`, `knowledge/`, `lands/`,
  `theme/`, `composeResources`, `androidApp/src`, `desktopApp/src`, the Gradle files, and `init.sh`
  are untouched.
- `git diff --check` → clean.

Honest gaps:

- There is no persistent E2E runner and `POST /ask` is still unrouted (carried
  `chat_question_submission` F1), so there is no live end-to-end answer to smoke; the transport-level
  encoded-body capture plus the pure builder tests are the honest automated equivalent and no
  on-device network evidence is claimed.
- Desktop launch smoke: `:desktopApp:run` started `com.jamarglex.manijero.MainKt` with the real
  `FileLandStorage` and stayed alive about 50 s with no exception in the run log until it was
  stopped (no interactive click-through and no screenshot; the app never submits on startup, so
  nothing was sent).
- The vocabulary is a pinned content decision, not a measurement: a wording that misses a term sends
  fewer attributes and therefore a more general (never wrong) answer; widening the table is a spec
  and test change.
- A failing local land read silently degrades to `general`, so a store problem can never block a
  question, and the payload then honestly says `general`; `ChatConversation.submit` reads the lands
  synchronously (matching the accepted `land_list` read), which is deliberate for MVP store sizes.
- `land_clarification`/`answer_land_scope` (choice and scope presentation), B13 applicability, and
  the land-data disclosure copy remain with their own features.

## land_clarification — accepted

Spec: `docs/specs/land_clarification.md`. Independently accepted 2026-10-13 (record:
`docs/validations/land_clarification.md`). This makes the
accepted `needs_land_clarification` response actually happen end to end: the answer service decides
that the applicable evidence differs across the supplied lands and returns the opaque local ids to
choose; the client shows a chooser built from the saved lands and resubmits the **same original
question** with `mode: selected` over the chosen lands.

What changed:

- `backend/app/clarification.py` (new, standard-library only, offline): composes the accepted
  `retrieval`/`abstention`/`generation` modules unchanged and never reads a catalog/passages file,
  calls a model, or touches the network.
  - `NeedsLandClarification(land_ids_to_choose)` frozen dataclass whose `__post_init__` rejects an
    empty, blank, over-128-char, or duplicate id (a programming error, never a payload).
  - `clarify_land_scope(question, land_context, corpus, *, k, max_claims)` returns `None` unless the
    request is `mode: all_active` with **≥ 2** lands, the corpus is a current `Retriever`, and the
    citation window (first `max_claims`, default 2, matching `abstention`) makes the lands'
    applicable-passage sets differ. `general`, a single land, a `selected` request, a corpus-level
    stale `Abstention`, and an empty candidate set all return `None` (the abstention path owns them).
  - Discriminating dimensions are `water_regime` and `production_method` (the two a request can
    carry); `crop` is absent, so a `crop` restriction is compatible with every land. A candidate
    *declares* a dimension only with a non-blank value other than `unknown`; an omitted, blank, or
    `unknown` land attribute is compatible with every candidate and never excludes one, and no value
    is invented. `land_ids_to_choose` is the request-order, deduplicated, id-bearing lands involved
    in a difference (a differing pair yields both ids).
  - `answer_with_clarification(...)` runs the decision first, then delegates to
    `abstention.answer_or_abstain(..., land_scope=land_context.mode)`;
    `to_clarification_response` emits exactly `{status: "needs_land_clarification", answer: "",
    sources: [], land_scope: "selected", land_ids_to_choose: [...]}`.
- `backend/scripts/evaluate_clarification.py` (new): report-only CLI
  (`--catalog/--passages/--eval/--as-of/--k/--json/--fail-on-miss`), exit `0` report / `1` a
  clarification invariant failed or `--fail-on-miss` with a mismatch / `2` unreadable/rejected
  input. Enforced invariants: a clarification payload has empty `answer`, empty `sources`, a
  non-empty `land_ids_to_choose`, and every chosen id is one of the request's land ids.
- `backend/tests/test_clarification.py` (new, 70 tests) and synthetic
  `backend/tests/fixtures/clarification/{catalog.json,passages.json,eval_questions.jsonl}` (at least
  one irrigated passage, one dryland, one with no applicability; a differentiating pair and a
  non-differing pair). No real legal fact, digit, or date.
- `shared/.../chat/LandContextBuilder.kt`: `selectedAskRequest(question, selected)` — the exact
  wording with `mode: selected`, repository/passed order, needed attributes only, ids verbatim; it
  requires a non-empty list and never merges, renames, reorders, or invents.
- `shared/.../ChatHomeState.kt`: `clarificationQuestion` (set to the submitted wording only on a
  clarification response, so the exact wording survives the empty-answer response), `AskClicked`
  clears it, `LandChoiceSubmitted(selectedLandIds)` (actionable only while a clarification is pending,
  idle, with retained wording and ≥ 1 chosen land; sets `question = ""`, `phase = SUBMITTING`,
  `submittedQuestion = clarificationQuestion`, leaves `messages` untouched, emits
  `SubmitSelected`), and `ChatEffect.request(lands)` maps `SubmitSelected` to the chosen stored lands
  in repository order (unknown ids ignored; none left → the accepted `general` request).
- `shared/.../ChatConversation.kt`: launches `submit` for both effects; the guarded `landsProvider`
  read and error mapping are unchanged.
- `shared/.../App.kt`: a `LaunchedEffect`-driven one-shot guarded read of the local lands on entering
  `awaitingLandClarification` (cleared otherwise, never logged); `ChatHomeScreen` gains
  `clarificationLands`; `LandClarificationChooser` filters that list to `state.landIdsToChoose`,
  renders each land's saved **name** and known attributes (reusing the accepted land strings via the
  `internal LandDetails`), offers merged-semantics multi-select rows, and one primary `Continuar`
  enabled only with ≥ 1 selection; the empty-list case shows a plain no-lands notice and submits
  nothing. Three previews added (two-land, one-land, narrow/large-text).
- `shared/.../composeResources/values/strings.xml`: the neutral `chat_home_needs_land_clarification`
  notice is replaced by `chat_home_clarification_title`/`_description`/`_continue`/`_no_lands`
  (plain Spanish, no digit, date, or legal claim).
- `CONSTRAINTS.md`: new "Land clarification" MUST rule. `backend/README.md`: the clarification
  boundary, rules, and CLI. `docs/specs/minimal_land_context.md`: the follow-up note that land
  selection/clarification is now owned here.
- Not changed: `contracts/`, `backend/app/{generation,retrieval,source_catalog,abstention}.py`,
  `backend/app/main.py`, `knowledge/`, `theme/`, `lands/`, the platform entry points, the Gradle
  files, and `init.sh`; no new module, dependency, route, ViewModel, or logging.

Verification (commands run from the repository root unless noted):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `python3 backend/scripts/evaluate_clarification.py --catalog backend/tests/fixtures/clarification/catalog.json --passages backend/tests/fixtures/clarification/passages.json --eval backend/tests/fixtures/clarification/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0; `corpus: current`; 2 eligible sources, 3 indexed passages; `answered outcomes: 5`,
  `clarifications: 1`, `clarifications with land ids: 1`, `clarification invariants hold: yes`,
  `outcomes differing from expect: 0`. The differentiating pair returns
  `needs_land_clarification` with `land-A, land-B`.
- `python3 -m py_compile backend/app/clarification.py backend/scripts/evaluate_clarification.py backend/tests/test_clarification.py`
  → clean.
- `cd backend && python -m pytest tests/test_clarification.py` → **70 passed**;
  `python -m pytest` → **469 passed** (399 existing + 70 new). Run with the interpreter of the
  temporary out-of-repo venv (Python 3.9.6); no dependency was added to the repo.
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **174 tests / 0 failures** (was 162;
  12 new: `LandContextBuilderTest` +3, `ChatHomeStateTest` +7, `ChatConversationTest` +2), no test
  removed.
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, 160 tests / 0 failures.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL (72
  actionable tasks executed).
- `./init.sh --verify` → BUILD SUCCESSFUL (exit 0).
- Literal feature-list verification: the fixture CLI line 1 returns `needs_land_clarification` with
  **both** land ids, and `ChatConversationTest` drives a fake `AnswerService` that returns the
  clarification payload, selects a land, and asserts the resubmission is a `selected` request with
  the exact original wording and only the chosen land; `LandContextBuilderTest`/`ChatHomeStateTest`
  assert the byte-for-byte `selected` body and the chosen-only/removed-land/unknown-id mapping.
- Privacy/scope: `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog\|System\.out" shared/src backend/app`
  → no matches; `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero | grep -v /theme/`
  → no matches; `MinimalLandContext` still has exactly the four contract properties;
  `git diff --check` → clean.

Honest gaps:

- There is no `/ask` route (carried `chat_question_submission` F1) and no Compose UI-test harness, so
  the backend decision is observed through the CLI/tests and the client flow through a fake
  `AnswerService` plus previews; no live end-to-end answer and no automated UI coverage is claimed.
- Detection is lexical and conservative: it can over-ask (a differing known value with a candidate
  that restricts it) but never guesses. Semantic applicability and any score threshold belong to
  `land_safety_evaluation`, and the answer's `land_scope` rendering belongs to `answer_land_scope`.
- The no-argument `App()` (iOS scaffold/previews) has no repository, so the shipped path shows the
  no-lands fallback rather than a fabricated land; previews supply a sample list.
- `init.sh` is unchanged: `--verify` already runs the shared tests and the Android/Desktop builds,
  and the backend slice is verified with the documented Python commands.

## chat_accessibility — accepted

Spec: `docs/specs/chat_accessibility.md` (new). Independent validation (`accept`, 2026-10-13; record:
`docs/validations/chat_accessibility.md`): the validator re-ran the contract validator,
`:shared:jvmTest --rerun-tasks` (192/0, +8, none removed), `:shared:testAndroidHostTest --rerun-tasks`
(178/0), the Android/Desktop builds, `./init.sh --verify` (exit 0), and the greps; re-drove the Android
emulator on an APK it rebuilt itself (1.0/2.0 no clipping, every clickable node >= 48dp, no
false no-lands fallback, auto-scroll reproduced) and the Desktop app through the macOS AX tree; and
reproduced the pure scroll key with its own probe. Carried gaps (Desktop visual focus indication,
TalkBack announcement capture, no UI-test harness) are recorded in `DESIGN.md` and in the validation
record. All evidence below was produced in this worktree on the final tree.

What changed (implementation):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/TranscriptScroll.kt` (new, pure, Compose-free):
  `TranscriptScrollKey(entryCount, phase, hasFailure, awaitingLandClarification)` and
  `transcriptScrollKey(state)`. The key changes only when a transcript element is appended or the
  working/failure/clarification state appears, so it decides *when* to move and nothing scrolls for a
  keystroke, an example selection, or an equal-state re-reduce.
- `shared/src/commonTest/kotlin/com/jamarglex/manijero/TranscriptScrollTest.kt` (new, 8 tests): a new
  `Tú`/`Asistente` entry, entering/leaving `SUBMITTING`, a failure appearing/clearing, a clarification
  appearing and the resubmission after a choice each change the key; a keystroke, an example selection,
  an equal-state re-reduce and a refused late response do not.
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`:
  - `ChatAssistantCard` gained a defaulted `liveRegionMode: LiveRegionMode? = null`; the `answered`
    branch passes `LiveRegionMode.Polite` (the `Tú` entries, the working notice, the abstention, the
    defensive clarification branch and the non-merging failure notice are unchanged, so `Reintentar`
    stays its own focusable node).
  - `ChatHomeScreen` holds a `BringIntoViewRequester` on a **1dp** end-of-transcript marker
    (`.fillMaxWidth().height(1.dp).bringIntoViewRequester(...)`) after the messages, failure notice,
    working notice and chooser; a `LaunchedEffect(scrollKey)` calls `bringIntoView()` only when the key
    differs from the remembered first key. The marker must not be zero-height — the reasoning
    (`localBoundingBoxOf` collapsing an empty rect to `Rect.Zero`, so the responder drops the request)
    is recorded in a comment and in the spec.
  - `clarificationLands` is now `List<Land>?` in `App()` and `ChatHomeScreen` (`null` = the guarded
    local read has not resolved), and `LandClarificationChooser(lands: List<Land>?)` renders its title
    and explanation only for `null`, the `chat_home_clarification_no_lands` fallback only for a
    resolved empty (or failed) list, and the checkbox rows plus `Continuar` otherwise.
  - The outer content `Column` gained `horizontalAlignment = Alignment.CenterHorizontally`, the
    top-level blocks use `.widthIn(max = ContentMaxWidth).fillMaxWidth()` (the earlier `fillMaxWidth()`
    first made the 720dp cap ineffective), and the title `Text` gained `Modifier.semantics { heading() }`.
  - Previews added: a wide window (`widthDp = 1000`), a long conversation at `fontScale = 1.3f`, and a
    chooser-while-resolving (`clarificationLands = null`); the three chooser previews were updated.
- `CONSTRAINTS.md`: the "Chat accessibility" MUST rule. `DESIGN.md`: the "Accessibility and validation"
  section records the inspected Android/Desktop baseline and the remaining gaps.
- `docs/specs/response_states.md`: U2 decided (an `answered` entry is a polite live region).
  `docs/specs/land_clarification.md`: N2 closed (the fallback flash).
- Not changed: `ChatHomeState.kt`, `ChatConversation.kt`, `chat/`, `lands/`, `privacy/`, `theme/`,
  `strings.xml`, `contracts/`, `backend/`, `knowledge/`, `androidApp/`, `desktopApp/`,
  `shared/src/iosMain/`, all Gradle files, and `init.sh`; no new module, dependency, permission,
  ViewModel, navigation, control, or logging.

Verification (commands run from the repository root unless noted):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --tests "com.jamarglex.manijero.TranscriptScrollTest"` → BUILD SUCCESSFUL
  (report XML: 8 tests / 0 failures / 0 errors).
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **192 tests / 0 failures / 21 suites**
  (was 184; +8 `TranscriptScrollTest`, no test removed).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, **178 tests / 0 failures /
  17 suites** (was 170, +8).
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL (72
  actionable tasks executed).
- `./init.sh --verify` → BUILD SUCCESSFUL (exit 0, 91 actionable tasks).
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include="*.kt" | grep -v /theme/`
  → no matches (every match is in `theme/ManijeroColors.kt`).
- `grep -rn "LocalMinimumInteractiveComponentSize\|minimumInteractiveComponentSize" shared/src` → no
  matches; `grep -rn "println\|Log\.\|Logger\|printStackTrace\|NSLog\|System\.out" shared/src androidApp/src desktopApp/src`
  → no matches.
- `git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml` → empty;
  `git diff --check` → clean.

Android evidence (real emulator-5554, `Medium_Phone_API_35`, density 2.625, shipped
`androidApp-debug.apk`; raw dumps/screenshots in the gitignored `build/evidence/`):

- Enlarged text: at `font_scale 1.0` and `2.0` the home, a long answered reply with two source cards,
  an abstention, the working notice, the failure notice and the clarification chooser render with no
  clipping, overlap, or horizontal overflow (every `uiautomator` node inside 0..1080 × 0..2400);
  screenshots `cap-f10-*.png`, `cap-f20-*.png`, `final-*.png`.
- Touch targets at 1.0: every clickable node is at least 126px = 48dp (suggestions `[63,594][1017,720]`
  and siblings, `Preguntar` `[63,1417][351,1543]`, `Mis terrenos`, `Privacidad y ayuda`, source-card
  open button `[105,1151][612,1277]`, chooser row `[105,1087][975,1362]` = 105dp tall, `Reintentar`
  `[105,1056][401,1182]`); `Preguntar` is disabled with an empty composer and enabled with a draft.
- Names and merged entries (`uiautomator dump --compressed`): each transcript entry is one merged node
  reading `Tú`/`Asistente` + scope caption + optional state label + body; the source-card control carries
  `content-desc` "Abrir el documento oficial: «…»"; the failure notice's `Reintentar` is a separate
  clickable+focusable node.
- Clarification chooser: rows are `checkable=true` toggles exposing the saved name + known details,
  `checked` flips false→true on tap, `Continuar` becomes focusable once a land is selected, and "no puedo
  mostrar tus terrenos" appears in **none** of the dumps (`a11y-clarification.xml`,
  `a11y-clarification-checked.xml`) — the false-limitation flash is not reproducible.
- Announcements: TalkBack is enabled and bound (`settings put secure enabled_accessibility_services
  com.google.android.marvin.talkback/...` succeeds; `dumpsys accessibility` shows a bound TalkBack
  service). The answered live region is verified by its code path and semantics wiring, not by a captured
  utterance (TalkBack speech is not logged here).
- Auto-scroll (decisive, shipped build, `font_scale 2.0`, long question): the page was scrolled to its
  very bottom first (`Privacidad y ayuda` `[250,2197][830,2295]`, `Preguntar` `[126,1591][433,1689]` and
  the composer `[63,944][1017,1517]` all visible, no transcript/failure on screen), then `Preguntar` was
  tapped. After the append the dump shows the newest content in view — the user entry tail `[105,0][975,421]`
  and the failure notice `[105,517][975,1294]` with `Reintentar` `[168,1347][489,1445]` — while the
  composer, `Preguntar`, `Mis terrenos`, the privacy summary and `Privacidad y ayuda` are all absent from
  the dump (below the fold): the view scrolled **up** to the newest element and neither stayed at nor
  jumped to the page bottom (`build/evidence/flow7-bottom-2.0.xml`, `flow7-after-2.0.xml`/`.png`). At
  `font_scale 1.0` submitting at the page top leaves the title at `[63,84]` and shows the `Tú` entry +
  failure notice + `Reintentar` already in view, i.e. nothing scrolls when the target is already visible
  (`flow6-*.xml`).
- Launch frame (report-only `visual_foundation` U4): `launch-frame-a/b.png` show the platform default
  splash (system icon on the light background) fading over the already-rendered chat home — no dark/black
  frame, and at rest the title sits below the status bar.

Desktop evidence (real `:desktopApp:run`, window "Manijero"; the macOS accessibility tree via
JXA/System Events, because host pixels are unavailable):

- Geometry: at an 800pt window every content block is exactly 720 wide at x=88; at 1400pt the same 720
  block is centred at x=388 with no overflow; at 420pt all blocks are 372 wide at x=72 with wrapped text
  and no clipping — the 720dp cap is effective and centred.
- Names: every control has an `AXDescription` (the three suggestion questions, "Preguntar", "Mis
  terrenos", "Privacidad y ayuda") and "Preguntar" reports `AXEnabled=false` with an empty composer; a
  merged transcript entry reads as one node ("Tú, ¿Qué obligaciones tengo por la condicionalidad?") and
  the failure notice's "Reintentar" is a separate `AXButton`.
- Keyboard: with the composer focused, Shift+Tab moved focus to the third suggestion and Space activated
  it (the composer filled); Cmd+A/Backspace cleared it — reachable and activatable by keyboard. Forward
  Tab is consumed by the multi-line composer as a tab character (`TextFieldKeyInput`: `KeyCommand.TAB ->
  if (!singleLine) CommitTextCommand("\t", 1) else consumed = false`), a platform text-field behaviour
  rather than a defect.

Honest gaps (nothing below is claimed as passing):

- The Desktop **visual** focus indication could not be inspected: host screen capture is blocked for the
  verification process (`screencapture -x` returns only the desktop wallpaper, and no
  ffmpeg/ffprobe/magick/PIL/Quartz exists). Per the spec's verify-first instruction no shared outline was
  added; the default Material indication was relied on. Recorded as an open item in `DESIGN.md`.
- The answered live-region *announcement* was not captured as audio/video (TalkBack is bound but its
  speech is not logged; no screen-recording tool on the host).
- No Compose UI-test harness exists (spec R1/U1) and this repo refuses test-only dependencies, so merged
  semantics, live regions, and focus order are verified by the `uiautomator`/AX dumps, the previews, and
  code inspection rather than an automated UI test.
- Desktop OS text scaling has no runtime integration, so Desktop large-text evidence stays preview-based.
- The answered/abstained/clarification device captures used a temporary non-committed probe
  `AnswerService` (since reverted; `git status` shows no `androidApp` change), because the shipped
  default is `UnavailableAnswerService` and there is no `/ask` route; the scroll, touch-target,
  focusability, and 1.0/2.0 geometry evidence was captured on the shipped build.
- The transcript stays in the single scrolling page (no pinned composer plus its own scroll region, spec
  U2) and reference numerals are not tappable (spec U5) — both deliberately out of scope.

## land_form_accessibility — accepted

Spec: `docs/specs/land_form_accessibility.md` (new). Self-verified 2026-10-13 and independently
**accepted** 2026-10-13 (record: `docs/validations/land_form_accessibility.md`); the low-digital-
confidence manual session stays an outstanding check. All evidence below was produced in this worktree
on the final tree.

What changed (implementation):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/lands/AddLandScreen.kt` and
  `EditLandScreen.kt` (both stateless screens, options shared via the `internal ChoiceGroup`):
  - The form title gained `Modifier.semantics { heading() }`.
  - A `remember { FocusRequester() }` on the name field: `handleAction` wraps `onAction` and calls
    `nameFocus.requestFocus()` when a `SaveClicked` arrives with `!state.hasName`. The focus is
    requested from the save path deliberately — the error flag stays `true` across a repeated blank
    attempt, so a state-keyed effect would not re-fire. The visible error `Text` became
    `liveRegion = LiveRegionMode.Polite` and the field carries
    `semantics { if (state.showNameError) error(nameErrorMessage) }`; the field modifier kept
    `fillMaxWidth()` first and added `focusRequester`/`semantics`.
  - In `ChoiceGroup`, the four option rows moved into a nested
    `Column(Modifier.fillMaxWidth().selectableGroup())` (the group label stays outside it). Each row
    keeps its single `selectable(role = RadioButton, onClick = …)` and adds
    `semantics { contentDescription = stringResource(Res.string.add_land_choice_description, label,
    stringResource(choice.label)) }`; no second clickable/`RadioButton(onClick = …)` was added and the
    selected state still comes from `selectable`. The nested column re-creates the previous 4dp
    inter-row spacing, so the rendered geometry is unchanged.
  - One combined preview per form (`AddLandNarrowLargeFontNameErrorPreview` /
    `EditLandNarrowLargeFontNameErrorPreview`, `widthDp = 320`, `fontScale = 2f`,
    `showNameError = true`). All existing previews were kept.
- `shared/src/commonMain/composeResources/values/strings.xml`: exactly one new key,
  `add_land_choice_description` = `%1$s: %2$s`, placed after `add_land_unknown`; used only as an
  accessible name, never as visible body text (`git diff --numstat` → `1 0`).
- `CONSTRAINTS.md`: new "Land form accessibility" MUST rule. `DESIGN.md`: a "Land add/edit form
  baseline" subsection under "Accessibility and validation" plus the remaining gaps.
  `docs/specs/add_land.md` and `docs/specs/edit_land.md`: one closure note each.
- Not changed: `AddLandState.kt`, `EditLandState.kt`, `Land.kt`, `LandDraft.kt`, `LandRepository.kt`,
  the storage adapters/format, `LandListScreen.kt`, `RemoveLandScreen.kt`, `PrivacyScreen.kt`,
  `App.kt`, `ChatHomeState.kt`, `ChatConversation.kt`, `chat/`, `privacy/`, `theme/`, `androidApp/`,
  `desktopApp/`, `shared/src/iosMain/`, `contracts/`, `backend/`, `knowledge/`, every Gradle file and
  `init.sh`; no new module, dependency (including test-only), ViewModel, coroutine, navigation,
  dialog, Compose UI-test harness, or logging. No visible copy or layout change.

Verification (commands run from the repository root):

- `python3 contracts/validate_examples.py` → "Validated 2 request and 3 response examples against
  answer_api_contract" (exit 0).
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL, **21 suites / 192 tests / 0 failures**
  (unchanged from the accepted `chat_accessibility` baseline; no test removed or renamed).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → BUILD SUCCESSFUL, **17 suites / 178 tests /
  0 failures**.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD SUCCESSFUL (72
  actionable tasks; `androidApp-debug.apk` 36,014,513 bytes).
- `./init.sh --verify` → BUILD SUCCESSFUL (exit 0, 91 actionable tasks).
- `git diff --numstat -- shared/src/commonMain/composeResources/values/strings.xml` → `1	0`.
- `grep -rn "Color(0x" shared/src/commonMain/kotlin/com/jamarglex/manijero --include="*.kt"` → only
  `theme/ManijeroColors.kt`; no `LocalMinimumInteractiveComponentSize`/`minimumInteractiveComponentSize`
  in `shared/src`; the `println|Log\.|Logger|printStackTrace|NSLog` grep over `shared/src`, `androidApp/src`
  and `desktopApp/src` → no matches; `git diff --check` → clean.

Android evidence (real emulator-5554, `Medium_Phone_API_35`, 1080×2400, density 2.625; shipped debug
APK; `adb shell settings put system font_scale 1.0`/`2.0` and `uiautomator dump`; raw dumps/screenshots
kept in a gitignored temp path outside the repo and removed):

- Group-qualified option names at 1.0 **and** 2.0, on both forms: all eight option `content-desc`
  values are `Riego: No lo sé`, `Riego: Secano`, `Riego: Regadío`,
  `Riego: Una parte de regadío y otra de secano`, `Producción: No lo sé`, `Producción: Convencional`,
  `Producción: Ecológico`, `Producción: Una parte de cada uno`; each row reports
  `checkable=true`/`checked=true` plus a `RadioButton` fake node (role). Compose intentionally reports
  an already-selected radio as `clickable=false` (verified against the `ui-android` 1.12.1 sources) —
  the split between the option node and the `cd='Riego: No lo sé'` node is Compose's documented
  `emitFakeNodes` behaviour, not a defect.
- Enlarged text at 2.0: no horizontal overflow (max text right edge 1017/1080), every node inside
  0..1080 × 0..2400, and both forms vertically scrollable; the smallest fully-visible clickable node
  measures 48.0dp at 1.0 and 53.3–66.7dp at 2.0 (no minimum-size override).
- Recoverable blank-name save on **both** forms: the name field reports `focused="true"` with
  `Escribe un nombre para el terreno.` visible and no record written; after moving focus to the
  municipality field a **second** blank save re-focuses the name field; correcting the name wrote
  exactly one record with the accepted confirmation and left the other lands unchanged (the add form
  saved a new land, the edit form updated exactly one existing row).
- TalkBack 15.0.0 is installed and enabled
  (`enabled_accessibility_services = com.google.android.marvin.talkback/…TalkBackService`); screenshots
  show its green accessibility-focus rect on the name error field and its hover highlight on the
  `Producción: No lo sé` row, but no spoken utterance was captured (`adb logcat` held only TalkBack
  `node is null` lines) — matching spec limitation R4; "announced" rests on the semantics wiring plus
  the focused-field dump, never a heard utterance.

Desktop evidence (real `./init.sh --desktop` / `:desktopApp:run`, window "Manijero"; the macOS
accessibility tree via JXA/System Events, because host pixels are unavailable):

- The add form exposes the title "Añadir terreno" (`AXStaticText`), the named fields "Nombre del
  terreno"/"Municipio (opcional)", all eight option rows as `AXRadioButton` with the group-qualified
  names and a `0`/`1` selected value, and the named "Guardar terreno"/"Cancelar"; the edit form shows
  the same with prefilled values and "Guardar cambios".
- Keyboard-only completion: Tab moved between the two text fields, each option row is its own tab
  stop, and Space selected an option (2 Tabs + Space selected "Riego: Secano"; 3 Tabs + Space selected
  "Producción: Ecológico"); 2 Tabs + Space on "Guardar terreno" saved the land and returned to the list
  with "El terreno se ha guardado en este dispositivo." and the new row; Shift+Tab moved back from
  municipality to the name field (typed "Y" landed there). Correcting the edit form by keyboard saved
  exactly one updated record ("Los cambios se han guardado en este dispositivo.") with the other row
  unchanged.
- Recoverable blank-name, keyboard-only: activating "Guardar" with a blank name wrote nothing and stayed
  on the form; the field description became "Nombre del terreno, Escribe un nombre para el terreno.";
  typing immediately (no explicit focus) landed in the name field; after moving focus to another field
  and re-activating Guardar the typed text again landed in the name field (a repeated attempt re-focuses),
  and the error cleared as typing resumed.
- Window resize: at 420pt every content block is 372 wide at x=72 with the explanation wrapped to two
  lines and no horizontal overflow (content taller than the window, i.e. vertically scrollable); at
  1200pt the explanation is a single line.

Preview / non-colour-cue review: the name error is never colour-only — the unchanged visible message is
always rendered (confirmed in an Android screenshot) and also appears in the Desktop AX field
description and in the Android field's error semantics; a greyscale render of the Android 2.0 error
screen (a temporary ImageIO converter, deleted after use) still shows the message text and the filled
inner dot of the selected radio.

Honest gaps (nothing below is claimed as passing):

- The Desktop per-element focus and the heading role are not exposed by the macOS AX tree
  (`AXFocused` stays false; the title is a plain `AXStaticText`), so the Desktop "focus moved to the
  name field" evidence is behavioural (typed text landed in the name field) and the heading rests on the
  Compose semantics; `uiautomator` likewise exposes neither merged nodes nor headings, so the group
  association and heading are verified by the Compose semantics plus the exposed `content-desc`/AX nodes.
- The TalkBack announcement is never captured as speech.
- No Compose UI-test harness exists and the repo refuses test-only dependencies, so the accessible
  names, `selectableGroup`, heading, focus and announcement are verified by the Android dump, the AX
  tree, the previews and code inspection, never an automated UI test.
- The Desktop visual focus indication could not be inspected (host screen capture and per-element
  `AXFocused` unavailable), so the default Material indication was relied on and, per the spec's
  verify-first instruction, no outline was added.
- Focus moving to the name field opens the Android IME (expected and helpful for correcting, recorded
  so it is not later mistaken for a defect); no autofocus happens on form entry.
- The low-digital-confidence human validation (feature-list note) was **not** run — no reviewer was
  available — and stays an outstanding manual check.
