# relevance_classifier — appendix

## Repository research

### Files inspected

- `feature_list.json` — `relevance_classifier` row: `knowledge`, `not_started`, depends on three accepted features.
- `PROGRESS.md` "Current state" — discovery/ingestion are local, manual, fixture-backed; local generation is off by default and measured only on the owner's Mac; the procedure map is 16 `proposed` topics.
- `docs/specs/official_source_discovery.md` — candidates are review-only leads; `review_status` stays `pending`.
- `backend/app/source_discovery.py` — `official-discovery-state-v1` shape: `candidates[<sha256>]` with `candidate_id`, `issuer`, `registry_id`, `registry_url`, `publication_url`, `title`, `stable_identity`, `version_hash`, `review_status`, `observations`; only titles, no bodies. `_load_state` is private: validate the shape in the new module.
- `knowledge/official-discovery-state.schema.json` — loose schema (only `review_status`/`observations` required per candidate); the classifier needs a stricter read.
- `backend/README.md` § "Manual official-publication discovery" (line ~1432) — command and state lifecycle; new section goes after it.
- `docs/specs/local_generation_provider.md` and `backend/app/local_generation.py` — `OllamaTransport.send(GeminiDraftRequest)`: system = `request.instruction`, user = `request.payload_json`; `format` hard-coded to `DRAFT_JSON_SCHEMA` (hence the one seam); timeout from `request.timeout_seconds`; fixed error codes; loopback-only opener; digest check cached on success.
- `backend/app/gemini_generation.py` — `GeminiDraftRequest` fields (`model`, `instruction`, `instruction_version`, `payload_json`, `max_output_tokens`, `timeout_seconds`), `SystemClock.utc_day()`.
- `backend/config/local_generation_model.json` — pinned tag/digest and answer-path limits (`timeout_seconds` 10, range 1–14); the classifier uses its own constants and does not edit the record.
- `docs/constraints/lands.md` lines 123–150 — the `OllamaTransport` loopback/pinned-digest/tests-without-Ollama MUST already applies to this reuse.
- `docs/specs/domain_procedure_map.md`, `backend/app/procedure_map.py` — `SEED_TOPIC_IDS` (16), `load_procedure_map`, `validate_procedure_map(document)` without cross-refs; the map is a taxonomy index, not evidence.
- `backend/app/corpus_security.py` — `scan_text(text, title_like=True)` returns `prompt_injection` / `nominal_listing` flags; reuse as the pre-model screen.
- `docs/constraints/answers-and-knowledge.md` "Knowledge updates and retrieval" — derived review artifacts live outside `knowledge/` and never change canonical bytes.
- `docs/specs/validity_checker.md` (+ appendix) — closest accepted pattern: stdlib module + thin CLI, fixed failures, canonical JSON outside `knowledge/`, input digests, `Result:` lines, exit `0/2`, schema in `knowledge/`.
- `scripts/init.sh` — `--feature <id>` runs the verify block; `--backend-tests <targets> -q` runs targeted pytest from `backend/`.
- `backend/tests/test_local_generation.py` — `FakeClock`, `FakeResponse`, `FakeOpener`, and socket-blocking patterns to mirror.
- `docs/archive/MasterPlanV3.md` A9 (line 760) — historical intent (relevance, topic, confidence, measured precision); superseded by the owner decisions.

### Existing patterns to follow

- Fixed, value-free failure names; never echo exception text, paths in failures, or model output.
- Canonical JSON with sorted keys and trailing newline, atomic write, input digests, no wall-clock time.
- Fakes over real services; sockets blocked in tests; a JSON Schema in `knowledge/` validated with `jsonschema` in tests.

### Current gaps

- No code reads discovery candidates for triage; the only candidate surfaces are ingestion and change impact.
- `OllamaTransport` cannot request a non-draft response format without the seam.
- No labelled set of relevant/not-relevant publications exists, so accuracy cannot be measured.

## Implementation plan

1. Add `response_format` keyword (default `DRAFT_JSON_SCHEMA`) to `OllamaTransport`; rerun `tests/test_local_generation.py` unchanged.
2. Add `knowledge/relevance-review.schema.json` (`relevance-review-v1`): top-level keys from the contract, row keys, label enum, `topic` = map-id pattern or null, `reason` enum, `additionalProperties: false`.
3. Create `backend/app/relevance_classifier.py`: constants (`INSTRUCTION_VERSION`, `MAX_TITLE_CHARS = 500`, `MAX_CANDIDATES = 5000`, timeout/token constants, `LABELS`, `REASONS`, `FAILURES`), `ClassificationAbort(failure)`.
4. Input loaders: strict discovery-state read, procedure map via `validate_procedure_map`, model record via `evaluate_local_model_record(as_of=clock.utc_day())`; compute input SHA-256 from bytes read once.
5. Report-path guard: resolve path; refuse inside resolved `knowledge/` or equal to any resolved input → `unsafe_report_path`.
6. Build the fixed instruction text and `response_format` from the validated map ids/titles; payload = `json.dumps({"candidate": {"issuer", "title"[:500]}}, ensure_ascii=False, sort_keys=True)`.
7. Per candidate (sorted by id): normalize whitespace, truncate, `scan_text` screen (flag → `unsure` with fixed reason, no call), else send via transport and strictly parse; map errors per contract.
8. Assemble rows, summary, `review_gate`, `limits`; write canonical JSON atomically.
9. CLI `backend/scripts/classify_candidate_relevance.py` with `main(argv, *, transport=None, clock=None)`; default transport = `OllamaTransport(record, response_format=…)`; print `Result:` lines; exit `0/2`.
10. Fixtures (`synthetic` labelled state: normal, long title, injection title, listing title, extra pending candidates) and `backend/tests/test_relevance_classifier.py`.
11. Docs: `backend/README.md` section, `knowledge/README.md` row, `ARCHITECTURE.md` bullet, constraints MUST, risks row; then run focused tier and `--fast`.

### Tests to write (named by behavior)

- three scripted answers produce three sorted rows, `model_suggestion`, summary counts, exit `0`, `Result:` line.
- injection-flagged and listing-flagged titles never reach the fake (call log) and become `unsure` with fixed reasons.
- system message equals the fixed instruction for every call and never contains any candidate title; user message parses to exactly `{"candidate":{"issuer","title"}}`.
- parametrized malformed outputs (non-JSON, array, missing/extra key, bad label, bad topic, topic list, wrong types) → `unsure`/`model_output_invalid`, no model text in file or captured output.
- `TimeoutError`, `http_error`, `response_invalid` → `model_error`; `connection_refused`, `model_not_found`, `model_digest_mismatch` → exit `2`, no file, pre-existing file untouched.
- a 501-char title sends 500 chars and sets `truncated: true`; 5,001 candidates abort `candidate_count_exceeded`.
- invalid state (wrong version, non-pending, missing title, id/key mismatch), invalid map, invalid record, report path in `knowledge/` or equal to an input → exit `2` fixed failure.
- two runs with the same fake answers are byte-identical; artifact validates against the schema; no timestamp keys.
- real `OllamaTransport` with a `FakeOpener`: URL is `OLLAMA_BASE_URL/api/chat`, `format` equals the classifier schema; default transport still sends `DRAFT_JSON_SCHEMA`.
- discovery state, `knowledge/` files hashed before/after are unchanged; module imports exclude `app.main`, `app.ask_api`, `app.retrieval`, `requests`, `httpx`.

## Verification plan

- `./scripts/init.sh --feature relevance_classifier` — focused tier (new tests plus local-generation, procedure-map, discovery regressions).
- `./scripts/init.sh --fast` — full backend suite; confirms the transport seam and new module change no answer-path behavior.
- `./scripts/init.sh --verify` — not expected: no shared, client, contract, or packaging change.
- Optional, not required for acceptance: one developer run against the owner's real Ollama with a synthetic discovery state, recording only counts and runtime in evidence.

## Evidence to capture

- Focused tier and `--fast` command lines with one-line results.
- Diff stat showing only the files listed in the contract; `local_generation_model.json` unchanged.
- Note whether the optional live run happened; if so, counts only, no titles.

## Feature evidence

- `./scripts/init.sh --feature relevance_classifier` — 269 passed, 1 warning (new file: 36 tests; local-generation, procedure-map, discovery regressions green).
- `CI=true ./scripts/init.sh --fast` — all 10 offline checks passed; backend-tests 2552 passed, 7 skipped.
- `local_generation.py` changed only by the `response_format` keyword (default `DRAFT_JSON_SCHEMA`); model record, `contracts/`, `shared/`, `init.sh` untouched.
- Optional live Ollama run: not performed.

## Validator checklist

- [ ] Contract scenarios 1–6 each covered by a named passing test; focused block passes as published.
- [ ] No candidate text in the system message; user payload shape exact; flagged titles never sent.
- [ ] Parser, not the `format` hint, decides; every malformed/out-of-vocabulary case yields `unsure` with `topic: null`; no model text stored or printed.
- [ ] Artifact outside `knowledge/`, deterministic, schema-valid, with `review_gate` all fail-safe values; discovery state and canonical knowledge untouched.
- [ ] Only loopback via `OllamaTransport`; `response_format` default keeps `test_local_generation.py` green; model record unchanged.
- [ ] Tests need no Ollama and no network.
- [ ] Docs: ARCHITECTURE bullet, constraint MUST, backend/knowledge README rows, risks row; no owner-guide change; no accuracy claim anywhere.
- [ ] Acceptance by validator is final (owner decision 2026-11-07); no owner walkthrough requested.
