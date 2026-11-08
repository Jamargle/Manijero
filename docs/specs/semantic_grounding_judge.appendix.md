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

The owner already pulled the judge, and the orchestrator read the pin from local Ollama 0.40.14; the values are in `
