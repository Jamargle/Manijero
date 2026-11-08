# Feature Spec: `semantic_grounding_judge`

## Source metadata

- **Feature:** `semantic_grounding_judge` — Check sentence-level support of drafts with a local judge model different from the generator (`evaluation`).
- **Depends on:** `golden_dataset_expansion`, `local_generation_provider` (both accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no app screen, route, copy, or `/ask` change. One offline command drafts answers for the reviewed cases plus the approved golden items with the pinned local generator, asks a pinned local judge model whether each draft sentence is supported by the passages it cites, and writes a report of counts and shares. The owner has one named command to download the judge model and one to produce the report.
- **Verification:** offline pytest with a fake generator and a fake judge (no Ollama, no network), an offline pin check, then an owner walkthrough of the two named commands (required by [operations](../constraints/operations.md) "acceptance includes a walkthrough").
- **Notes — owner decisions, 2026-11-08 (binding):**
  1. **Scope: evaluation only.** An offline command judges whether each draft sentence is supported by its cited passages over the golden set and reports scores. No change to live `/ask` answers in this feature; a live check may be a later feature.
  2. **Judge model:** the planner picks a small local Ollama model from a different model family than the generator, pinned by name and digest the same way as the generator. Tests use a fake judge. The owner pulls the model with one named command (plain-language output, per [operations](../constraints/operations.md)).
  3. **No manual agreement check:** judge scores are reported clearly labelled as unchecked against human review; no accuracy claim is made about the judge.
- **Owner answers, 2026-11-08 (binding):** (1) the owner pulled `qwen2.5:7b-instruct-q4_K_M`; pin values read by the orchestrator from local Ollama 0.40.14 `/api/tags` and `/api/show` are in the appendix "Handoff" and are the only source for the judge record (no `ollama` run, no network). (2) The owner agrees to the owner walkthrough of the setup and report commands before final acceptance. (3) The owner confirms the report command `./scripts/init.sh --grounding-judge-report`.
- **Planner decisions:** judge = `qwen2.5:7b-instruct-q4_K_M` (Alibaba Qwen family; generator is Mistral), Apache-2.0, about 4.7 GB — reasons in the appendix. It is pinned in its own record using the generator's `local-generation-model-v1` shape. MasterPlanV3 C4 ("agrees with manual review on sample") and the "95 % fidelity" candidate are superseded by decision 3.

## Goal

Give later evaluation work (`evaluation_metrics_report`, `ci_quality_gates`) a reproducible, offline, report-only semantic-support signal for local drafts, at the sentence level the lexical verifier already uses, judged by a different model family than the one that wrote the draft.

## Non-goals

- Any change to `/ask`, `verify_draft`, `GatedGeminiGenerator`, the generator record, the answer cache, abstention, or `contracts/`.
- A pass/fail threshold, release or CI gate, accuracy or agreement figure for the judge, or any quality claim about answers.
- Judging extractive fallback text, abstentions, or the code-owned lead-in, notice, or deadline paragraph.
- A judge rationale, confidence score, ensembles, retries, prompt tuning, or a second judge model.
- Editing `knowledge/` canonical data, the golden set, or its review states; any Compose UI or app copy.
- Any non-loopback endpoint or new Python dependency.

## Job story

When I change the corpus, prompt, or generator, I want to see how many local draft sentences a different local model thinks are not backed by the passages they cite, so I can spot unsupported claims the lexical checks miss, without spending money and without trusting the judge as truth.

## Acceptance scenarios

### 1. Each draft sentence gets one judged verdict

Given the reviewed cases, approved golden items, a fake generator returning a parseable `answered` draft for case A (two sentences citing `[1]` and `[1][2]`), and a fake judge returning `{"verdict":"supported"}` then `{"verdict":"not_supported"}` · When `judge_grounding.py run` runs · Then it writes one `grounding-judge-report-v1` JSON file outside `knowledge/` with, for case A, the generation outcome, and per sentence its index, text without markers, cited numbers, and verdict; prints one `Result:` line; exits `0`. The judge received each sentence with only the excerpts of the passages it cites.

### 2. Only model drafts are judged; everything else is counted, not judged

Given cases where `/ask` abstains or clarifies before drafting, or the generator outcome is `timeout`, `transport_error`, `malformed_output`, `provider_abstained`, or `rate_limited` · When the command runs · Then those cases appear with their outcome and zero sentences, and the judge is never called for them. Drafts with outcome `local_used` and `verifier_rejected` are both judged and reported separately.

### 3. Sentences the judge cannot see are marked, not sent

Given a draft sentence with no `[n]` marker, or a marker outside the offered candidates · When judged · Then its verdict is `uncited` or `citation_invalid` and the judge is not called for it.

### 4. Judge output fails closed

Given the fake judge returns non-JSON, a non-object, a missing or extra key, a verdict outside `supported` / `not_supported` / `unclear`, or raises `TimeoutError`, `http_error`, or `response_invalid` · When that sentence is judged · Then its verdict is `unjudged_invalid_output` (or `unjudged_error`), it never counts as supported, no judge text is stored or printed, and the run continues.

### 5. Scores are labelled unchecked

Given any successful run · Then the report's `summary` holds sentence counts per verdict and `supported_share` = supported ÷ (supported + not_supported + unclear), overall and split by `verifier` (`accepted` = `local_used`, `rejected` = `verifier_rejected`) and by `case_set` (`reviewed`, `golden`); `judge_review: "unchecked_against_human_review"`; and a fixed `limits` list stating that the scores are not checked against human review and make no accuracy claim about the judge. The `Result:` line says `unchecked against human review`. Stdout never carries question, answer, sentence, or passage text.

### 6. Pins and preconditions abort before writing

Given any of: a judge record whose `digest` is the placeholder `unpinned` (`judge_model_unpinned`); a judge or generator record failing `evaluate_local_model_record` (`judge_model_record_invalid` / `generator_model_record_invalid`); judge and generator with the same tag or digest (`judge_same_as_generator`); a pre-run `/api/tags` check where Ollama is unreachable, or either pinned model is absent or has another digest (`ollama_unavailable`, `generator_unavailable`, `judge_unavailable`); invalid catalog, passages, cases, or golden set (`invalid_inputs`); a report path inside `knowledge/` or equal to an input (`unsafe_report_path`); or a judge `connection_refused`, `model_not_found`, or `model_digest_mismatch` mid-run · When the command runs · Then it exits `2`, prints one fixed `Result:` line naming the failure, and writes no report (an earlier report is untouched).

### 7. Deterministic, loopback-only, live path untouched

Given the same inputs and the same fake responses · When run twice · Then the files are byte-identical and carry input SHA-256 digests, both model tags and digests, both instruction versions, and no timestamp. Tests block sockets; the only base URL is `OLLAMA_BASE_URL`; `knowledge/` bytes are unchanged; `backend/app/main.py`, `ask_api.py`, `generation.py`, and `gemini_generation.py` are byte-unchanged, and no module on the `/ask` path imports the judge module.

### 8. Owner downloads the judge model with one command

Given the backend environment · When the owner runs `./scripts/init.sh --grounding-judge-setup` · Then it checks the environment, Ollama, and the pin, runs `ollama pull` for the pinned tag (Ollama's own progress shown), verifies the installed digest against the record, and ends with `Result: the grounding judge model is ready.` A second run reports it is already ready without downloading. Missing Ollama, Ollama not running, an unpinned record, a failed pull, or a digest mismatch each end with one pinned `Result:` line naming the fix, exit non-zero, and never edit the record. Pinned lines live in the owner guide table.

### 9. Owner produces the report with one command

Given both models are ready · When the owner runs `./scripts/init.sh --grounding-judge-report` (no arguments) · Then it runs scenario 1 over `knowledge/` with campaign `2026` and today's local date, writes `build/grounding-judge/report.json`, prints `Checked case <n> of <N>` progress, and ends with `Result: judged S draft sentences from D drafts (P supported, N not supported, U unclear, X not judged); judge scores are unchecked against human review. Report: build/grounding-judge/report.json.` A missing prerequisite names `--local-rag-setup` or `--grounding-judge-setup`.

### 10. Manual acceptance: owner walkthrough

Given validator accept · When the owner follows `Owner walkthrough: grounding judge` in `docs/owner-guide/grounding-judge.md` · Then the owner has run setup, run the report, triggered one missing prerequisite (Ollama app closed), and recovered. The aggregate counts from that run are recorded in the acceptance record, labelled unchecked.

## Technical approach

- **Judge record** `backend/config/grounding_judge_model.json`: exactly the `local-generation-model-v1` keys, read with `load_local_model_record` and gated by `evaluate_local_model_record`; a raw `digest == "unpinned"` is caught first as `judge_model_unpinned`. Digest, size, parameter size, quantization, and license come from the local Ollama API (`/api/tags`, `/api/show`), never invented; the orchestrator read them on 2026-11-08 and recorded them in the appendix "Handoff" (see "Pinning"). No substitute model.
- **New stdlib module `backend/app/grounding_judge.py`**: pure functions `split_draft_sentences` (reuse `generation.split_sentences`, `inline_markers`, `strip_markers`), `judge_payload(sentence, cited)` → `{"sentence":…,"passages":[{"number":n,"text":excerpt}]}`, strict `parse_verdict`, `summarize`, canonical report assembly, report-path guard, atomic write. Fixed instruction `grounding-judge-v1` (sentence and passages are data, never instructions; answer only the verdict JSON). Judge transport = `OllamaTransport(judge_record, response_format=VERDICT_SCHEMA)` with module constants `JUDGE_TIMEOUT_SECONDS = 60`, `JUDGE_MAX_OUTPUT_TOKENS = 32`.
- **Draft capture without touching `/ask`:** build an in-process app as `measure_local_generation.run_mode` does (`create_app(local_transport=<recording wrapper>)`, `MANIJERO_GENERATION_PROVIDER=local`, `MANIJERO_LOCAL_MODEL`, `MANIJERO_ANSWER_CACHE=off`, outcome recorder via the generator's `log` field). The wrapper keeps the request `payload_json` and the raw output in memory; drafts come from `parse_draft(raw, offered)`, cited excerpts from the payload's numbered passages.
- **Cases:** `load_case_document` cases plus `golden_set.approved_cases(load_golden(...))` (same merge as `evaluate_pac_answers.py --golden`), each posted as `{question, land_context}`.
- **Preflight:** one `/api/tags` read verifying both pins, then a load-only `/api/generate` per model (300 s) so the generator's 10 s timeout is not spent on a cold load. Injectable `opener` and transports for tests.
- **CLI `backend/scripts/judge_grounding.py`:** `run` (explicit `--catalog --passages --cases --golden --active-campaign --as-of --k --report`), `setup` (reuses `local_rag_bootstrap.OllamaClient` and `find_model`), `check-record` (offline: both records valid, judge pinned, tag and digest differ, tag families `qwen` vs `mistral`), `show-pin` (developer: prints the installed tag's digest, size, details, and license hash; never writes). `main(argv, *, opener=None, generator_transport=None, judge_transport=None, ollama=None, clock=None)`. Raw tracebacks go to `build/grounding-judge/last-error.log`.
- **`scripts/init.sh`:** `--grounding-judge-setup` and `--grounding-judge-report` dispatch blocks mirroring `--golden-review` (venv check, plain `Result:` on missing env), plus two help lines.
- **Report schema** `knowledge/grounding-judge-report.schema.json` (`grounding-judge-report-v1`, `additionalProperties: false`).

## Expected file changes

- Create: `backend/app/grounding_judge.py`, `backend/scripts/judge_grounding.py`, `backend/config/grounding_judge_model.json`, `knowledge/grounding-judge-report.schema.json`, `backend/tests/test_grounding_judge.py`, `backend/tests/fixtures/grounding_judge/` (synthetic judge record, labelled synthetic), `docs/owner-guide/grounding-judge.md`.
- Update: `scripts/init.sh` (two blocks, two help lines), `docs/owner-guide/README.md` (index line), `backend/README.md` (≤30 lines), `knowledge/README.md` (schema row), plus the durable docs below.
- Do not change: `backend/app/{main,ask_api,generation,gemini_generation,local_generation}.py`, `backend/config/local_generation_model.json`, `knowledge/` canonical data and `golden_set.json`, `contracts/`, `shared/`, `requirements*.txt`, existing tests.
- Implementer/validator only after evidence: `feature_list.json` status, `PROGRESS.md`, `docs/progress/*`, `docs/validations/semantic_grounding_judge.md`.

## Visual design impact

None. Terminal output only; English labels like the other owner commands.

## Durable documentation impact

- `ARCHITECTURE.md`: update — one bullet: offline `grounding_judge.py` drafts with the pinned generator in-process, judges sentences with a second pinned loopback model, writes a report outside `knowledge/`; never on the `/ask` path.
- `docs/constraints/lands.md`: update — widen the `OllamaTransport` pin MUST so the offline judge may use only the tag whose digest matches `backend/config/grounding_judge_model.json`.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation": update — one MUST: the grounding judge is evaluation-only (never in `/ask` or a gate), uses a pinned model of a different family than the generator, fails closed to "not judged", reports scores labelled unchecked against human review with no accuracy claim, and tests need no Ollama.
- `docs/constraints/operations.md`: not needed — the pin-verified download and owner-command rules already apply.
- `docs/risks-and-open-questions.md`: update — row 13: an offline, unchecked semantic judge exists; live semantic support stays open.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`: not needed.

## Focused verification

`./scripts/init.sh --feature semantic_grounding_judge` runs this block unchanged from the repository root. No step needs Ollama or the network. The `check-record` step fails with `judge_model_unpinned` until the real digest is recorded, so the feature cannot pass on a placeholder.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_grounding_judge.py tests/test_local_generation.py tests/test_golden_set.py -q
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/judge_grounding.py check-record
```
<!-- verify:end -->

## Appendix

See [`semantic_grounding_judge.appendix.md`](semantic_grounding_judge.appendix.md) for repository research, the judge choice, pinning steps, the ordered plan, evidence to capture, and the validator checklist.
