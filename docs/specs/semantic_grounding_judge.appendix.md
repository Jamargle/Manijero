# semantic_grounding_judge — appendix

## Repository research

### Files inspected

- `feature_list.json` — row: `evaluation`, `not_started`, depends on two accepted features; spec/validation paths already set.
- `PROGRESS.md` "Current state" — local generation is off by default, measured only on the owner's Mac; numeric check is lexical; "semantic support stays open".
- `docs/specs/local_generation_provider.md` — how the generator is pinned: committed `local-generation-model-v1` record with tag, 64-hex digest from `/api/tags`, license from `/api/show`, size ≤ 50 GB budget; "implementer stops, no substitute" rule; Ollama 0.40.13 on loopback; registry pulls allowed.
- `backend/config/local_generation_model.json` — generator `mistral-small3.2:24b-instruct-2506-q4_K_M`, about 15.2 GB, Apache-2.0, `timeout_seconds` 10.
- `backend/app/local_generation.py` — `load_local_model_record`, `evaluate_local_model_record(doc, as_of)`, `OllamaTransport(record, opener=, clock=, response_format=)` (seam added by `relevance_classifier`), `loopback_opener`, `LocalTransportError` codes, `OLLAMA_BASE_URL`; request timeout comes from `GeminiDraftRequest.timeout_seconds`, not the record. Record ranges: `timeout_seconds` 1–14, `max_output_tokens` 1–1024, `num_ctx` 2048–32768.
- `backend/app/gemini_generation.py` — `GeminiDraftRequest`, `parse_draft(raw, offered)`, `GatedGeminiGenerator` (outcome codes; `log` field; offers the first `max_claims` candidates as `minimal_provider_payload` with `passage_id` = rank string).
- `backend/app/privacy_review.py::minimal_provider_payload` — payload is `{"question", "passages":[{"passage_id","text"}]}`; the recording wrapper reads cited excerpts from it.
- `backend/app/generation.py` — `split_sentences`, `inline_markers`, `strip_markers`, `verify_draft` (sentence = claim unit, markers required per sentence).
- `backend/scripts/measure_local_generation.py` — in-process app pattern: `_set_mode_env`, `create_app(local_transport=…)`, replacing the resolved provider's `log` with a recorder, dependency overrides for corpus/as-of/campaign/k, `TimedTransport` wrapper, load-only `/api/generate` for cold load.
- `backend/scripts/evaluate_pac_answers.py` — `--golden` merge: `load_golden` + `approved_cases`, id-collision guard, `additional_areas`.
- `backend/app/golden_set.py`, `knowledge/golden_set.json` — 49 items, all `approved` (2026-11-08 snapshot).
- `backend/app/answer_eval.py::evaluate` — `/ask` body is `{question, land_context}`.
- `backend/app/local_rag_bootstrap.py` — `OllamaClient` (`cli_present`, `tags`, `pull` via `ollama pull`, `MANIJERO_OLLAMA_CLI`), `find_model`, `_drafting` pull-then-verify pattern and its plain messages.
- `scripts/init.sh` lines 342–359 — `--golden-review` owner dispatch block to mirror; help lines ~472.
- `docs/constraints/operations.md` — one named command, prerequisite checks, one `Result:` line, pin-verified downloads that never edit a pin (line 18), measurement output without text (line 22), owner walkthrough MUST (line 17).
- `docs/constraints/lands.md` lines 138–145 — `OllamaTransport` pin MUST names only the generator record; needs widening.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation" — where the judge MUST goes.
- `docs/specs/relevance_classifier.md` (+ appendix) — closest pattern: stdlib module + thin CLI, strict parser over the `format` hint, fixed failures, canonical JSON outside `knowledge/`, schema in `knowledge/`, sockets blocked in tests.
- `docs/archive/MasterPlanV3.md` lines 188, 386, 795 — historical intent: local judge different from generator; C4 agreement check superseded by owner decision 3.
- Not inspected: `docs/owner-guide/README.md` format (implementer follows existing lines); `backend/README.md` section placement.

### Judge model choice

- **Pick:** `qwen2.5:7b-instruct-q4_K_M` — Qwen 2.5 7B Instruct, Q4_K_M, about 4.7 GB.
- Different family: Alibaba Qwen vs the Mistral generator, so the judge does not share the generator's training lineage or tokenizer.
- Licence: Apache-2.0 for the 7B size (the 3B and 72B sizes use the Qwen licence, so the size matters); same "no separate use policy" bar the generator met.
- Strong Spanish and reliable JSON-schema output through Ollama `format`.
- Not a "thinking" model, so the accepted `OllamaTransport` body (no `think` key) works unchanged; Qwen3 was rejected for that reason (default reasoning output would burn `num_predict` and time).
- Small: generator + judge ≈ 20 GB, well inside the 50 GB budget; both can stay loaded.
- Rejected: Gemma (separate use policy), Llama (community licence), Phi/Granite (weaker Spanish evidence; not needed).

### Pinning (no invented digest)

The owner already pulled the judge, and the orchestrator read the pin from local Ollama 0.40.14; the values are in `## Handoff` below and are the only source. The implementer does not run `ollama`, `show-pin`, or reach the network.

1. Write `backend/config/grounding_judge_model.json` with exactly the keys of `backend/config/local_generation_model.json`, in the same order.
2. From Handoff: `model`, `digest`, `size_bytes`, `parameter_size` (`7.6B`), `quantization` (`Q4_K_M`), `license` (`Apache-2.0`); `recorded_on` = `2026-11-08`.
3. `license_reference` mirrors the generator's wording: `Ollama 0.40.14 /api/show license text 'Apache License, Version 2.0, January 2004' (11343 chars, sha256 832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e), recorded 2026-11-08; model card https://huggingface.co/Qwen/Qwen2.5-7B-Instruct`.
4. Operational keys (not from Ollama): `num_ctx` 4096, `timeout_seconds` 14 (record range is 1–14; the judge's real per-call timeout is `JUDGE_TIMEOUT_SECONDS` = 60 on the request), `max_output_tokens` 32, `max_requests_per_minute` 600, `max_requests_per_day` 100000, `keep_alive_seconds` 1800. All must pass `evaluate_local_model_record`.
5. Record in Feature evidence: "pin copied from Handoff, no Ollama call", and the `check-record` result. `show-pin` is still built and unit-tested with a fake opener for future re-pins.

## Implementation plan

1. Create the judge record per "Pinning"; confirm `evaluate_local_model_record` accepts it in a test.
2. Add `knowledge/grounding-judge-report.schema.json` (`grounding-judge-report-v1`, `additionalProperties: false`): inputs digests, both models (tag, digest), instruction versions, `cases[]` (id, `case_set`, outcome, `sentences[]` with index, text, cited, verdict), `summary`, `judge_review`, `limits`.
3. `backend/app/grounding_judge.py` constants: verdict codes (`supported`, `not_supported`, `unclear`, `uncited`, `citation_invalid`, `unjudged_invalid_output`, `unjudged_error`), `VERDICT_SCHEMA`, `INSTRUCTION_VERSION = "grounding-judge-v1"`, instruction text, `JUDGE_TIMEOUT_SECONDS`, `JUDGE_MAX_OUTPUT_TOKENS`, fixed failure codes and `LIMITS`.
4. Pure functions: `split_draft_sentences`, `judge_payload`, `parse_verdict` (exact one-key object, enum value), `judge_sentence` (uncited/citation_invalid short-circuit; transport errors → `unjudged_error`; fatal `connection_refused`/`model_not_found`/`model_digest_mismatch` raise to abort).
5. `summarize` (counts per verdict, `supported_share` with denominator 0 → `null`, splits by `verifier` and `case_set`) and canonical report assembly (sorted keys, no timestamp).
6. Record checks: `check_records(judge, generator, as_of)` → `judge_model_unpinned` before `evaluate_local_model_record`, then same tag/digest and family (`qwen` vs `mistral` tag prefix) checks.
7. Report-path guard (`unsafe_report_path` inside `knowledge/` or equal to an input) and atomic write (temp file + `os.replace`).
8. Recording transport wrapper: keeps `payload_json` and raw output per call; `parse_draft(raw, offered)` yields the draft, numbered passages yield excerpts.
9. `backend/scripts/judge_grounding.py run`: validate inputs (`invalid_inputs`), `/api/tags` preflight for both pins, load-only `/api/generate` per model (300 s), in-process app per `measure_local_generation.run_mode`, post each case, judge, write report, print progress and one `Result:` line; tracebacks only to `build/grounding-judge/last-error.log`.
10. `setup` (CLI present, Ollama up, record pinned, already-ready short-circuit, `ollama pull`, digest verify, never writes the record), `check-record` (offline), `show-pin` (prints, never writes).
11. `scripts/init.sh`: `--grounding-judge-setup` and `--grounding-judge-report` blocks mirroring `--golden-review`; report block passes `knowledge/` paths, campaign `2026`, today's date, `build/grounding-judge/report.json`; two help lines.
12. `backend/tests/test_grounding_judge.py` and `backend/tests/fixtures/grounding_judge/` (synthetic records labelled synthetic); sockets blocked.
13. Docs: `docs/owner-guide/grounding-judge.md` (≤60 lines, walkthrough + pinned `Result:` table), owner-guide README line, `backend/README.md` (≤30 lines), `knowledge/README.md` schema row, and the durable doc updates listed in the contract.
14. Run the focused verification block; append evidence; set Handoff for the validator.

## Verification plan

Tests in `backend/tests/test_grounding_judge.py` (fake generator transport, fake judge transport, fake opener, sockets blocked):

- `test_answered_draft_sentences_each_get_one_verdict` — scenario 1, payload carries only cited excerpts, exit 0.
- `test_non_drafted_outcomes_are_counted_not_judged` — scenario 2, judge call count stays 0; `local_used` and `verifier_rejected` both judged.
- `test_uncited_and_out_of_range_markers_skip_the_judge` — scenario 3.
- `test_invalid_judge_output_fails_closed` (parametrized: non-JSON, list, missing key, extra key, bad enum) and `test_judge_transport_errors_are_unjudged` — scenario 4; no judge text in report or stdout.
- `test_summary_shares_splits_and_unchecked_label` — scenario 5, including zero-denominator share.
- `test_preconditions_abort_without_writing` (parametrized over every scenario-6 code) — exit 2, one `Result:`, prior report bytes unchanged.
- `test_report_is_byte_identical_across_runs`, `test_knowledge_unchanged_and_ask_path_does_not_import_judge` — scenario 7.
- `test_setup_pulls_verifies_and_reports_ready`, `test_setup_already_ready_skips_pull`, `test_setup_failures_print_pinned_lines_and_never_edit_record` — scenario 8, fake `OllamaClient`.
- `test_committed_judge_record_is_valid_and_differs_from_generator`, `test_show_pin_prints_without_writing`.
- Shell: `./scripts/init.sh --grounding-judge-report` with no venv prints the plain `Result:` naming `--local-rag-setup` (scenario 9 dispatch).
- Regression: `tests/test_local_generation.py`, `tests/test_golden_set.py` in the focused block.
- Manual: owner walkthrough (scenario 10) after validator accept; not run by agents.

## Evidence to capture

- Focused block command and one-line result; `check-record` `Result:` line.
- Note that the pin came from Handoff with no Ollama or network call.
- `git diff --stat` showing the do-not-change files untouched.
- Line counts of the owner guide section and `backend/README.md` addition.
- Owner walkthrough aggregate counts (validator/owner, in the acceptance record).

## Feature evidence

Implementer session 2026-11-08 (no `ollama` run, no network; sockets blocked in tests).

- Pin: `backend/config/grounding_judge_model.json` copied from Handoff, no Ollama call. `license_reference` keeps the model-card URL (same pattern as the generator record).
- `./scripts/init.sh --feature semantic_grounding_judge`: `270 passed, 1 warning` (grounding judge, local generation, golden set); `check-record`: `Result: the grounding judge record is valid and pinned (judge qwen2.5:7b-instruct-q4_K_M, drafting mistral-small3.2:24b-instruct-2506-q4_K_M; different tag, digest, and family).`
- `./scripts/init.sh --backend-tests tests/test_grounding_judge.py -q`: `51 passed` (scenarios 1-8, committed record, show-pin, init.sh dispatch via stub python).
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed (`backend-tests 3017 passed, 9 skipped`, `harness-tests 20 passed`).
- `git status`: `main.py`, `ask_api.py`, `generation.py`, `gemini_generation.py`, `local_generation.py`, `local_generation_model.json`, `golden_set.json`, `contracts/`, `shared/`, `requirements*.txt`, and existing tests unchanged.
- Line counts: owner guide `grounding-judge.md` 49 lines; `backend/README.md` addition 27 lines.
- Not run by the implementer: the real-Ollama commands (`--grounding-judge-setup`, `--grounding-judge-report`) and the owner walkthrough (scenario 10).

## Validator checklist

- [ ] Focused block passes unchanged via `./scripts/init.sh --feature semantic_grounding_judge`; no Ollama or network needed.
- [ ] Judge record matches Handoff values exactly (tag, digest, size, parameter size, quantization, license, license sha256, 11343 chars, Ollama 0.40.14, `recorded_on` 2026-11-08); no invented value.
- [ ] Each acceptance scenario 1–9 maps to a passing test or a shell check.
- [ ] No judge, question, answer, sentence, or passage text on stdout; report outside `knowledge/`; schema validates the report.
- [ ] Judge failures never count as supported; `supported_share` denominator excludes unjudged/uncited.
- [ ] `/ask` path files and the generator record byte-unchanged; no `/ask` module imports `grounding_judge`; no new dependency; only `OLLAMA_BASE_URL`.
- [ ] `setup` never edits the record; pinned `Result:` lines match the owner guide table.
- [ ] Scores labelled `unchecked_against_human_review`; no accuracy or agreement claim anywhere.
- [ ] Durable docs updated as the contract lists; owner guide ≤60 lines, `backend/README.md` ≤30 lines.
- [ ] Owner walkthrough recorded before final acceptance.

## Handoff

- Status: `passing`; validator accepted 2026-11-08 pending owner walkthrough (scenario 10); holding commit made. Next: owner runs `./scripts/init.sh --grounding-judge-setup` (twice) and `./scripts/init.sh --grounding-judge-report` per `docs/owner-guide/grounding-judge.md`, then reports. On a match: evidence-only update, status `accepted`, `feat: complete semantic_grounding_judge`, no second validator. On a defect: repair via implementer.
- Owner answers 2026-11-08: owner pulled the judge; walkthrough of setup and report commands agreed; `./scripts/init.sh --grounding-judge-report` confirmed.
- Judge pin (read by the orchestrator from local Ollama 0.40.14 `/api/tags` + `/api/show`; use as-is, do not run `ollama` or reach the network): model `qwen2.5:7b-instruct-q4_K_M`; digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`; size_bytes `4683087332`; family `qwen2`; parameter_size `7.6B`; quantization `Q4_K_M`; context_length `32768`; license `Apache-2.0`, `/api/show` license text "Apache License, Version 2.0, January 2004" (11343 chars, sha256 `832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e`).
- Checks: see Feature evidence.
