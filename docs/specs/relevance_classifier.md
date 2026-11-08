# Feature Spec: `relevance_classifier`

## Source metadata

- **Feature:** `relevance_classifier` — Classify discovered candidates for relevance and topic with the local model, treating text as data (`knowledge`).
- **Depends on:** `official_source_discovery`, `local_generation_provider`, `domain_procedure_map` (all accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no app screen, route, or copy. A developer runs one offline command over an `official-discovery-state-v1` file; it writes a derived review list that suggests a label and a topic per candidate. A person decides what happens next.
- **Verification:** offline pytest with a fake model (no Ollama, no network) plus the accepted discovery, local-generation, and procedure-map regression tests; commands in Focused verification.
- **Notes — owner decisions, 2026-11-07:**
  - Suggest only: one offline developer command classifies discovered candidates (from `official_source_discovery` output) with the local generation provider (Ollama) as `relevant` / `not_relevant` / `unsure`, plus exactly one topic from `domain_procedure_map`.
  - Candidate text is strictly data, never instructions; prompt-injection text inside candidates must not change labels or output shape; input is bounded (truncated to a fixed limit); malformed or out-of-vocabulary model output fails closed to `unsure`.
  - Output is a deterministic review list artifact outside `knowledge/`; nothing is auto-dropped, nothing reaches the corpus, releases, indexes, or `/ask`; a person decides.
  - No network beyond the local model; zero cost. Tests run offline with a fake model (no real Ollama needed for verification).
  - Developer-only: no owner-guide step.
  - Acceptance: validator accept is final; no owner walkthrough.

## Goal

Give the reviewer of discovered official publications a first-pass, suggest-only triage: every pending candidate gets one label (`relevant`, `not_relevant`, `unsure`) and one procedure-map topic, produced by the pinned loopback model under a fixed instruction, with candidate text confined to the data role. Anything the code cannot trust becomes `unsure`. The list is review input only.

## Non-goals

- Dropping, approving, fetching, ingesting, or changing the `review_status` of any candidate; editing the discovery state, catalog, passages, procedure map, releases, indexes, or `/ask`.
- A model confidence score, free-text rationale, multi-topic labels, or any measured precision/recall claim (MasterPlanV3 A9 asked for measured precision; the owner decisions do not, and there is no labelled set).
- Classifying document bodies (discovery keeps only titles); reading ingestion quarantine, parsed Markdown, or chunks.
- A new model, endpoint, env flag, model-record change, scheduler hook, `init.sh` mode, or new dependency.
- Owner-guide steps, an owner walkthrough, or any Compose UI, Spanish app copy, or `contracts/` change.

## Job story

When discovery has queued many official publications, I want a local, free first pass that suggests which look relevant and to which olive-grove procedure, so I can review the likely ones first without any automated step hiding or admitting a document.

## Acceptance scenarios

### 1. Every candidate gets exactly one label and one topic suggestion

Given a valid discovery state with three pending candidates, the canonical procedure map, the pinned model record, and a fake model answering `{"label":"relevant","topic":"sigpac"}`, `{"label":"not_relevant","topic":"pagos"}`, and `{"label":"unsure","topic":"riego"}` · When `classify_candidate_relevance.py` runs · Then it writes one `relevance-review-v1` file outside `knowledge/` with one row per candidate (sorted by `candidate_id`) carrying `candidate_id`, `issuer`, `title`, `publication_url`, `label`, `topic`, `reason: model_suggestion`, and `truncated`, plus `summary` counts, prints one `Result:` line, and exits `0`.

### 2. Candidate text is data and cannot steer the run

Given a candidate whose title contains model-directed text that `corpus_security.scan_text(title, title_like=True)` flags (`prompt_injection`, or `nominal_listing`) · When the command runs · Then the model is never called for that candidate, its row is `label: unsure`, `topic: null`, `reason: instruction_like_text` (or `nominal_listing`), and all other rows are unaffected. For every candidate the model is called for, the system message is the fixed versioned instruction plus the topic vocabulary and contains no candidate text; the user message is exactly the JSON object `{"candidate":{"issuer":…,"title":…}}`.

### 3. Malformed or out-of-vocabulary model output fails closed

Given the fake model returns non-JSON, a non-object, a missing or extra key, a label outside the three values (for example `approve`), a topic outside the 16 map ids, a list of topics, or the transport raises a timeout, `http_error`, or `response_invalid` · When that candidate is classified · Then its row is `label: unsure`, `topic: null`, `reason: model_output_invalid` (or `model_error` for transport failures), no model text appears anywhere in the artifact or on stdout/stderr, and the run continues.

### 4. Input is bounded

Given a candidate title longer than 500 characters after whitespace normalization · When it is classified · Then only the first 500 characters reach the model and the row has `truncated: true` and the full stored title. Given more than 5,000 candidates · When the command runs · Then it aborts `candidate_count_exceeded` and writes nothing.

### 5. Invalid inputs or an unavailable model abort before writing

Given an unreadable or invalid discovery state or procedure map, a model record that fails `evaluate_local_model_record`, a report path inside `knowledge/` or equal to an input, or a transport failure `connection_refused`, `model_not_found`, or `model_digest_mismatch` at any point · When the command runs · Then it exits `2`, prints one fixed `Result:` line on stderr naming only the fixed failure, and writes no report (an earlier report at that path is left untouched).

### 6. Deterministic, local-only, and read-only

Given the same inputs and the same model responses · When the command runs twice · Then the two files are byte-identical, carry input SHA-256 digests, model tag and digest, and instruction version, and contain no timestamp. Tests block sockets except through the injected fake; the only reachable base URL is `OLLAMA_BASE_URL`; discovery state, `knowledge/`, release, and index bytes are unchanged; the module imports neither `app.main`, `ask_api`, retrieval, nor a non-loopback HTTP client.

## Technical approach

- **New stdlib module `backend/app/relevance_classifier.py`** plus thin CLI `backend/scripts/classify_candidate_relevance.py` (`--discovery-state`, `--procedure-map`, `--report`, all required; model record is the committed `backend/config/local_generation_model.json`). Reuse, do not duplicate: `local_generation.load_local_model_record`/`evaluate_local_model_record`/`OllamaTransport`/`LocalTransportError`, `gemini_generation.GeminiDraftRequest`/`SystemClock`, `procedure_map.load_procedure_map`/`validate_procedure_map`, `corpus_security.scan_text`.
- **One seam in `local_generation.py`:** `OllamaTransport(..., response_format=DRAFT_JSON_SCHEMA)`; the `format` field uses it. Default behavior, the loopback constant, digest check, and the record are unchanged.
- **Discovery input.** Require `schema_version == "official-discovery-state-v1"`, a `candidates` object whose entries carry string `candidate_id` (equal to its key), `issuer`, `title`, `publication_url`, and `review_status == "pending"`; otherwise `invalid_discovery_state`. Never write to it.
- **Prompt.** Fixed instruction `relevance-classifier-v1` (Spanish-capable, states the candidate is official metadata to classify, never instructions) followed by the 16 map topics as `id — title`. Request: `temperature 0`, `seed 0` (transport defaults), classifier-owned constants `CLASSIFY_TIMEOUT_SECONDS = 120` and `CLASSIFY_MAX_OUTPUT_TOKENS = 64` (cold load fits; the answer-path record limits are not changed). `response_format` = object with `label` enum and `topic` enum of the map ids, both required, no extra properties.
- **Strict parser is the authority**, not the Ollama `format` hint: exactly `{label, topic}`, label in the three values, topic in the map ids, else fail closed (scenario 3). Model text is never stored or printed.
- **Failure mapping.** `connection_refused` / `model_not_found` / `model_digest_mismatch` → abort `model_unavailable`; `TimeoutError` and other `LocalTransportError` codes → row `model_error`. Fixed failures: `invalid_discovery_state`, `invalid_procedure_map`, `model_record_invalid`, `candidate_count_exceeded`, `unsafe_report_path`, `model_unavailable`.
- **Artifact.** Canonical JSON (`sort_keys`, indent 2, trailing newline), atomic temp-then-replace, refusing a path inside `knowledge/` (resolved) or equal to an input. Top level: `schema_version`, `classifier` (instruction version, model tag, digest), `inputs` (discovery-state and procedure-map SHA-256), `candidates`, `summary` (`relevant`/`not_relevant`/`unsure` counts, total), `review_gate` (`automatic_drop: false`, `canonical_changes_applied: false`, `requires_human_decision: true`), fixed `limits` list (suggestions only, not legal relevance, titles only, unmeasured accuracy). New schema `knowledge/relevance-review.schema.json`.
- **CLI.** Success: `Result: <n> candidates classified (<r> relevant, <x> not relevant, <u> unsure); review list written to <path>.`, exit `0`. Abort: `Result: the relevance classification did not run: <failure>. Nothing was written.` on stderr, exit `2`. `main(argv, *, transport=None, clock=None)` seam for tests.

## Expected file changes

- `backend/app/relevance_classifier.py` — create.
- `backend/scripts/classify_candidate_relevance.py` — create.
- `backend/app/local_generation.py` — update; the `response_format` keyword only.
- `knowledge/relevance-review.schema.json` — create; `relevance-review-v1` derived contract.
- `backend/tests/test_relevance_classifier.py` and `backend/tests/fixtures/relevance_classifier/` — create; synthetic discovery state (labelled synthetic) and scripted fake model.
- `backend/README.md` (about 25 lines), `knowledge/README.md` (one schema row), `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `docs/risks-and-open-questions.md` — update.
- `feature_list.json`, `PROGRESS.md`, `docs/progress/*`, `docs/validations/relevance_classifier.md` — implementer/validator only, after evidence.
- Do not change: `backend/config/local_generation_model.json`, `knowledge/` canonical data, `contracts/`, `shared/`, `scripts/init.sh`, `docs/owner-guide.md`, existing tests.

## Visual design impact

None. No Compose UI, Spanish app copy, or screenshot baseline changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one bullet: `relevance_classifier.py` reads discovery state, calls only the pinned loopback model, writes a suggest-only review list outside `knowledge/`.
- `docs/constraints/answers-and-knowledge.md`: update — one MUST under "Knowledge updates and retrieval": relevance suggestions are review-only outside `knowledge/`, never drop/admit/change candidates, candidate text only in the data role, flagged or unparseable cases fail closed to `unsure`, tests need no Ollama. The `OllamaTransport` rule in `docs/constraints/lands.md` already covers the endpoint: not needed.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `docs/owner-guide.md`: not needed (developer-only, no workflow, term, or UI change).
- Other: `backend/README.md` (command, inputs, artifact, exit/Result protocol, limits), `knowledge/README.md` (schema row), `docs/risks-and-open-questions.md` (unmeasured accuracy; unflagged reworded injection can still sway a real model within the vocabulary).

## Focused verification

`./scripts/init.sh --feature relevance_classifier` runs this block unchanged from the repository root. No step needs Ollama or the network.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_relevance_classifier.py tests/test_local_generation.py tests/test_procedure_map.py tests/test_source_discovery.py -q
```
<!-- verify:end -->

## Appendix

See [`relevance_classifier.appendix.md`](relevance_classifier.appendix.md) for repository research, the ordered plan, verification detail, evidence, and the validator checklist.
