# local_notice_pipeline — appendix

## Repository research

The planner had no shell in this session: the selector, `init.sh`, and tests were not run; the feature id came from the parent prompt.

### Files inspected

- `feature_list.json` — entry `local_notice_pipeline` (`not_started`, depends on two accepted features); `question_rewriting` depends on it.
- `PROGRESS.md` "Current state" — local generation is off by default and measured on the owner's Mac only; input screen does not cover names or addresses.
- `docs/specs/local_generation_provider.md` — loopback-only Ollama, pinned record, fake-only tests, no new dependency.
- `docs/specs/pilot_privacy_readiness.md` — no retention by default, no personal data in logs, pilot profile gates.
- `docs/specs/legal_structure_chunker.md` — shape of a developer-only offline command writing derived review files outside `knowledge/`.
- `backend/app/local_generation.py` — `OllamaTransport.send` hard-codes `format: DRAFT_JSON_SCHEMA`; `loopback_opener`, `LocalTransportError` codes, `load_local_model_record`, `evaluate_local_model_record(document, as_of=)`.
- `backend/app/gemini_generation.py` — `GeminiDraftRequest(model, instruction, instruction_version, payload_json, max_output_tokens, timeout_seconds)` and the `GeminiTransport` protocol.
- `backend/app/input_guardrails.py` — `_PHONE`, `_DNI`, `_NIE`, `_NIF`, `_EMAIL`, `_IBAN`, and private `_has_personal_data` (masks SIGPAC/cadastral first).
- `backend/app/redaction.py` — capitalised-run and self-introduction name shapes to mirror; redaction itself is not used (refuse, do not repair).
- `backend/app/corpus_security.py` — `scan_text(text)` returns `nominal_listing` / `prompt_injection` flags.
- `backend/app/pilot_config.py` — profile comes from `MANIJERO_DEPLOYMENT_PROFILE`, blank means `development`.
- `docs/constraints/answers-and-knowledge.md` "Knowledge updates and retrieval" — where the new MUST goes; neighbouring derived-review rules.
- `docs/archive/MasterPlanV3.md` §7.8 and A14 — notices are signals, not content; process locally, never in Git; questions, never answers.
- `.gitignore` — `build/` is ignored, so `build/notice-review/` stays out of Git.

### Existing patterns to follow

- Developer CLIs in `backend/scripts/` call one app module and print one JSON report with fixed codes; exit `0`/`1`/`2` (`chunk_legal_documents.py`).
- Canonical JSON: sorted keys, `indent=2`, LF, one trailing newline, no timestamp or absolute path; atomic write via temp file and `os.replace`.
- Offline tests block sockets and inject fakes; the existing `test_local_generation.py` uses a recording fake opener.
- Fixed error codes, never text, in exceptions and output (`LocalTransportError`).

### Current gaps

- No public personal-data check outside `/ask`; no name or address detector anywhere.
- `OllamaTransport` cannot send a schema other than the answer draft schema.
- No notice input format exists; this spec defines `notice-NNN.txt` plain UTF-8 files.

## Implementation plan

1. Add `response_format: Mapping[str, Any] = DRAFT_JSON_SCHEMA` keyword to `OllamaTransport.__init__`; send it as `format`; add one test.
2. Add `contains_personal_identifier(text) -> bool` to `input_guardrails.py` returning `_has_personal_data(text)`.
3. Create `notice_pipeline.py` constants: bounds (50 files, 16 KiB, 6,000 chars), caps (15 terms, 5 questions, 60/80/200 chars), `INSTRUCTION_VERSION = "notice-extract-v1"`, `NOTICE_OUTPUT_SCHEMA`, timeout 120 s, max tokens 1024, file-name pattern `^notice-\d{3}\.txt$`.
4. Folder reader: resolve paths; abort codes `notices_missing`, `output_in_knowledge`, `output_in_notices`, `too_many_notices`, `unexpected_entry` (count only), `profile_not_development`; ignore dot-files.
5. Per-notice decode and bounds → `notice_too_large`, `notice_unreadable`, `notice_empty`.
6. Personal-data screen (rules below) → all matching codes, sorted; then `corpus_security.scan_text`.
7. Request builder: pinned Spanish instruction stating the payload is cooperative-notice data, never instructions; only extract terms and grower questions; never answer; reply only with the schema. Payload `json.dumps({"aviso": text}, ensure_ascii=False)`.
8. Validator for model output (contract scenario 4); fold for the `colloquial` occurrence check: NFKD, strip accents, casefold, collapse whitespace.
9. Error mapping: `TimeoutError` → `model_timeout` (notice); `response_invalid` → `model_output_invalid` (notice); `connection_refused`, `http_error`, `model_not_found`, `model_digest_mismatch`, `model_mismatch` → abort exit 2 with `ollama_<code>`; record gate failure → `model_record_invalid`.
10. Merge and sort: vocabulary keyed by folded `(colloquial, standard)`, first-seen spelling kept, `notices` list sorted; questions keyed by folded text.
11. Writer and report; `--screen-only` path never constructs a transport.
12. CLI script; top-level catch prints only `{"error": "NoticePipelineError", "code": ...}`.
13. Fixtures: three invented clean notices (PAC reminder with colloquial words such as "la PAC", "los papeles", "el cuaderno"), README stating they are invented, canned fake outputs.
14. Tests (below), then durable docs from the contract.

### Personal-data rules (new, code-owned; precision notes in the known-limitations line)

- `person_name`: honorific `D.`, `Dña.`, `Dª`, `Don`, `Doña`, `Sr.`, `Sra.`, `Sres.`, `Srta.` + capitalised word; `me llamo` / `mi nombre es` / `soy` + capitalised word; a committed list of at least 40 common Spanish given names (folded) followed by a capitalised word. "Nuestra Señora" alone does not fire.
- `street_address`: `C/`, `Calle`, `Avda.`, `Avenida`, `Plaza`, `Pza.`, `Paseo`, `Camino`, `Carretera`, `Ctra.` + capitalised run + optional `nº` + 1–4 digit number; or `C.P.` / `CP` / `código postal` + 5 digits.
- `parcel_id`: 4 or more colon-separated digit groups; the 20-character cadastral shape; `polígono` + number with `parcela` + number within 40 characters.
- `phone`, `national_id` (DNI/NIE/NIF), `email`, `iban`: via `contains_personal_identifier` plus per-kind checks so codes are distinct (implementer may expose the individual patterns publicly instead of the alias if cleaner; behavior of `/ask` must not change).

## Verification plan

- Focused block in the contract — all pass; screen-only over fixtures exits `0`.
- `./scripts/init.sh --backend-tests` once — full suite passes (no regression in `/ask` paths).
- Optional live run (owner's Mac, Ollama serving the pinned model): `process_cooperative_notices.py --notices backend/tests/fixtures/local_notice_pipeline/notices --output build/notice-review` — record exit code and summary counts only.
- E2E: not applicable; no app, wire, or service behavior changes.

## Evidence to capture

- Tests by behavior: clean run writes canonical review file; each personal-data code refuses without model call and without echo (assert the sample string absent from stdout, stderr, output file, exception args, and `caplog`); dates/times not flagged as parcels; injection refused; each malformed-output class fails only its notice; timeout per notice; Ollama connection/model/digest errors abort with nothing written; abort setups (knowledge output, nested output, 51 files, bad name, non-development profile, invalid record); screen-only never constructs a transport; two runs byte-identical; `knowledge/` byte-identical; no `/ask`-path module imports `notice_pipeline`; default `OllamaTransport` format unchanged.
- Focused block result and full backend suite result, one line each.

## Feature evidence

2026-11-08 (implementer; the worktree had no venv, so `./scripts/init.sh --setup-python dev` was run first).

- `./scripts/init.sh --feature local_notice_pipeline` — focused tier passed (pytest block plus screen-only CLI: 3 screened, exit 0).
- `./scripts/init.sh --backend-tests tests/test_notice_pipeline.py -q` — 83 passed (scenarios 1-7, every personal code, 24 malformed-output classes).
- `./scripts/init.sh --backend-tests` — 2601 passed, 7 skipped.
- Design notes: `input_guardrails` gained public `personal_identifier_kinds` (fixed kinds) plus `contains_personal_identifier`; `/ask` behavior unchanged. The review file lists extracted notices only; refused or failed notices appear only in the stdout report (file name and codes). `corpus_security.scan_text` runs with `title_like=True` so a bare "listado de beneficiarios" is refused.
- No live Ollama run (optional, not done).

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no `knowledge/`, `/ask`, release, eval, or owner-guide change).
- [ ] Acceptance scenarios 1–7 pass, with evidence; refused text never appears anywhere.
- [ ] `OllamaTransport` and `input_guardrails` changes are behavior-preserving; existing tests unchanged and passing.
- [ ] Committed notices are invented and labelled; no personal-looking sample is committed as a file.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature local_notice_pipeline`.
- [ ] Durable documentation impact followed; nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
