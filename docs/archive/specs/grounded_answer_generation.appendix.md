# Appendix — `grounded_answer_generation`

Planning and verification record for [`docs/specs/grounded_answer_generation.md`](../../specs/grounded_answer_generation.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/grounded_answer_generation.md` remains the authoritative
acceptance record.

## Repository research

Inspected:

- `feature_list.json`: this feature is `not_started`; both dependencies are `accepted`; its note and verification are the grounding rule above. `safe_abstention` depends on it.
- `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`: approved official material only for regulatory claims; no invented dates/amounts/eligibility/article numbers; citations a non-technical user can open; abstain when evidence is inadequate; critical amounts and deadlines need prominent excerpts; land data never proves eligibility; provider choice and provider terms are unresolved.
- `docs/archive/MasterPlanV3.md` §§3, 5, 6.3–6.4, 8.1–8.3, 9.1–9.2, 11.3: the LLM is a writer, never the knowledge source; `temperature=0`, structured JSON `{found, answer, sources}`, numbered context `[1]…[n]`, extractive mode for `critico:true`, code-added fixed notice lines, and a validation cascade (schema → citations → numeric grounding → semantic grounding → validity → policy → coherence) with "0 invented numbers/dates" as a candidate gate.
- `docs/specs/source_retrieval.md`, `docs/validations/source_retrieval.md`, `backend/app/retrieval.py`: the accepted `Retriever.search(question, k) -> tuple[RetrievedPassage, ...]` boundary, its eligibility rules, its `AnswerSource`-compatible field names plus retrieval-local fields, and the measured synthetic baseline `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`.
- `backend/tests/fixtures/retrieval/{catalog,passages}.json`, `eval_questions.jsonl`: synthetic, clearly labeled fixtures that deliberately contain **no** real or even concrete deadlines/amounts.
- `contracts/openapi.yaml`, `contracts/examples/response-answered.json`, `contracts/validate_examples.py`, `docs/specs/answer_api_contract.md`: `AskResponse` (`status`, `answer` ≤ 1200, `sources`, `land_scope`, `land_ids_to_choose`), `AnswerSource` with `additionalProperties: false`, and `answered` requiring non-empty answer and ≥1 source.
- `backend/app/main.py`, `backend/README.md`, `backend/requirements.txt`, `knowledge/README.md`, `knowledge/passages.schema.json`, `backend/scripts/evaluate_retrieval.py`, `backend/tests/test_retrieval.py`: `/health` is the only route; pytest is the backend convention and must be run as `python -m pytest`; the report-only CLI style (explicit `--as-of`/`--k`, `--json`, `0`/`1`/`2` exit codes, no network) is the established pattern.
- `scripts/init.sh`: checks and verifies KMP targets only; it has no backend command.

Absent, and therefore not assumed: any `LLMClient`, model provider, prompt, `/ask` route, canonical `knowledge/passages.json`, semantic judge, semantic cache, feedback loop, `ARCHITECTURE.md`, `CONSTRAINTS.md`, and any persistent E2E command. The system interpreter has no `pytest` and the worktree has no `python` on `PATH`; the accepted features ran pytest from a temporary venv outside the repository (no repo dependency added).

## Implementation plan and tasks

1. Add `backend/app/generation.py`: draft/report/issue models, Spanish sentence splitting and figure/date normalization helpers, `GroundingGenerator` protocol, `ExtractiveGroundingGenerator`, `verify_draft` with all seven rule groups, `generate_grounded_answer`, and `to_answer_response`.
2. Add the synthetic `backend/tests/fixtures/generation/` set: approved 2–3 source catalog, reviewed labeled passages (one with a fictitious figure marked `critical`, one ordinary), `eval_questions.jsonl` (covered, unaccented-variant, and `no_candidates` cases), and `drafts_ungrounded.json` keyed by issue code. Keep every value clearly labeled synthetic; assert no real deadline, amount, or article number.
3. Add `backend/scripts/evaluate_generation.py` with strict input validation (including unknown `expected_passage_ids`), per-claim verdict reporting, aggregate counters, `--json`, and the `0`/`1`/`2` exit-code contract.
4. Add `backend/tests/test_generation.py`: covered-question answer + per-claim grounding; ascending marker/`sources` order; exact `AnswerSource` key set matching `contracts/examples/response-answered.json`; every `drafts_ungrounded.json` case rejected with its expected issue code; `no_candidates` on the empty canonical catalog and on an out-of-vocabulary question; `invalid_question` bounds; determinism of two identical runs; socket-guard no-network; no excerpt text in rejection messages; `land_scope` validation; and a 1200-character boundary case.
5. Run the CLI on the fixtures and on the canonical empty catalog, the focused and full pytest suites, `contracts/validate_examples.py`, the unchanged retrieval baseline, `py_compile`, and `git diff --check`; fix any inconsistency.
6. Verify the feature-list verification literally: capture one covered source-anchored question with each material claim mapped to its cited passage and its grounding verdict.
7. Update `knowledge/README.md` and `backend/README.md`, then record evidence and status (implementer/orchestrator) with only the commands actually run.

## Verification plan and evidence

Run from the repository root:

```sh
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
python3 backend/scripts/evaluate_generation.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5
python3 contracts/validate_examples.py
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
cd backend && python -m pytest tests/test_generation.py
cd backend && python -m pytest
python3 -m py_compile backend/app/generation.py backend/scripts/evaluate_generation.py backend/tests/test_generation.py
git diff --check
```

Capture: the covered question with its per-claim verdicts and cited passages (the feature-list verification); aggregate counters with zero ungrounded claims and zero invented sources; the empty-corpus run producing no answers and exit `0`; the recorded rejected drafts and their issue codes; byte-identical repeated runs; the socket-guard result; pytest counts for the new file and the full suite; the contract validator output plus confirmation that `contracts/` is unchanged; and the unchanged retrieval baseline numbers. Note the environment: pytest runs from a venv outside the repository and no dependency is added. No browser/API/E2E test is required because this feature has no user-facing or API flow and no persistent E2E framework exists; the CLI plus unit tests cover the pipeline.

## Validator checklist

- [ ] A covered source-anchored fixture question yields a cited plain-Spanish `answered` response, and every material claim is traceable to a returned candidate passage.
- [ ] Figures and dates in a claim are present in its cited passage; a claim with an unsupported figure is rejected, and `critical` claims are literal excerpts.
- [ ] A draft citing an unknown/undeclared marker, leaving a sentence uncited, inventing a figure or article, or asserting eligibility is rejected with the expected issue code, and nothing from it reaches the payload.
- [ ] No candidates (empty canonical catalog, out-of-vocabulary question) produce `no_candidates`, no text, and no model call.
- [ ] The assembled payload matches the accepted `AskResponse`/`AnswerSource` shape (exact key sets), `contracts/validate_examples.py` passes, and `contracts/` is untouched.
- [ ] The pipeline is deterministic, offline (socket guard), and content-silent in diagnostics (no question or excerpt text in rejections).
- [ ] `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`, `knowledge/source_catalog.json`, `knowledge/passages.schema.json`, `backend/requirements.txt`, `scripts/init.sh`, and all client/shared code are unchanged; no canonical `passages.json` or real legal fact was added.
- [ ] Fixtures are synthetic and labeled; `feature_list.json`/`PROGRESS.md` report only the commands actually run and state that the generator is extractive and no provider is configured.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/grounded_answer_generation.md. Added backend/app/generation.py (draft model, verify_draft, ExtractiveGroundingGenerator, generate_grounded_answer, to_answer_response, answer_source), backend/scripts/evaluate_generation.py (offline report CLI, exits 0/1/2), backend/tests/test_generation.py (100 focused tests), and synthetic fixtures backend/tests/fixtures/generation/{catalog.json,passages.json,eval_questions.jsonl,drafts_ungrounded.json}. Updated knowledge/README.md and backend/README.md; created CONSTRAINTS.md (answer-grounding MUST rules); appended the spec's 'Implementation findings'.
- Design: code, not a model, owns evidence selection, citation markers [n] = RetrievedPassage.rank, the sources array (sources[n-1], deduplicated ascending), and the pinned lead-in/notice (no digit or date). Every sentence must carry a marker; every figure/date must appear in the cited passage; a critical claim must be a literal (normalized) substring of its critical excerpt; an eligibility assertion fails policy. A failing draft is discarded whole and returns NotAnswered with a reason code (invalid_question, no_candidates, generator_abstained, grounding_failed, policy_failed, generation_error) and issue codes; no rejected-draft text is emitted. Standard library only, no network, no model provider, no /ask route, no new dependency; contract/retrieval/catalog files untouched.
- Commands actually run: cd backend && python -m pytest tests/test_generation.py -> 100 passed; cd backend && python -m pytest -> 221 passed (121 existing + 100 new); python3 -m py_compile on the three new Python files -> clean; git diff --check -> clean (after trimming a trailing blank line added to knowledge/README.md); python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'.
- Fixture evaluation (acceptance check): python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5 -> exit 0; answers produced: 5, claims checked: 8, ungrounded claims: 0, invented sources: 0, no-evidence outcomes: 1, grounding invariants hold: yes, outcomes differing from expect: 0. Each covered question prints its per-claim verdict and cited candidate numbers; the out-of-corpus line ('zzzz qqqq') returns no_candidates with no invented evidence. No real legal fact is asserted anywhere: every fixture passage is explicitly labelled synthetic, and the fictitious figures (42 days, 1.200 euros, 3 documents) belong to no real procedure.
- Canonical empty corpus: python3 backend/scripts/evaluate_generation.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5 -> exit 0 with 0 eligible sources, 0 indexed passages, 'no evaluation questions supplied'. With --eval and the empty catalog the index check reports the named ids and exits 2 (harness error, fail closed), documented in README.
- Enforced invariant (fail closed) demonstrated: a temporary passage set whose reviewed text contains a starter eligibility phrase ('...tienes derecho a ninguna ayuda real.') produced 'outcome: policy_failed', 'claim 1: failed; cites [1] (eligibility_claim)', 'grounding invariants hold: no', exit 1. The 13 recorded rejected drafts in drafts_ungrounded.json each reproduce their expected issue code.
- Determinism: two --json runs are byte-identical (diff clean), sha256 f8345c124a3ba4ab0b2fd1e4947244b54e21b5cc2a289f024e13cf5b28a4e453.
- Regression boundaries unchanged: retrieval baseline still hit@5 = 0.857 (6/7), recall@5 = 0.857, MRR = 0.857 on the retrieval fixtures; contracts/, backend/app/retrieval.py, backend/app/source_catalog.py, backend/app/main.py, knowledge/source_catalog.json, knowledge/passages.schema.json, backend/requirements.txt, scripts/init.sh and all client/shared code are unmodified.
- Not run: Android/Desktop/Gradle and ./scripts/init.sh checks (no product UI or route changed; scripts/init.sh has no backend command), and no browser/API/E2E test (there is no /ask route and no persistent E2E harness). Environment note: this worktree has no `python` on PATH and the system interpreter has no pytest, so pytest ran with a temporary venv interpreter outside the repo; no dependency was added to the repo.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/grounded_answer_generation.md). It independently reproduced the 100 focused / 221 full pytest passes, py_compile, git diff --check, the fixture CLI run (exit 0; 5 answers, 8 claims, 0 ungrounded, 0 invented sources, 1 no-evidence, invariants hold, 0 expect-mismatches), the literal feature-list verification (plazo claim 1 = critical rank-1 excerpt with the fictitious 42 dias cited [1]; claim 2 = rank-2 excerpt [2]), the canonical empty-corpus run (exit 0, and exit 2 with --eval naming unknown ids), byte-identical deterministic --json runs (sha256 f8345c12...e453), and a stricter independent socket guard that still produced the answer. It confirmed fail-closed paths (eligibility -> policy_failed exit 1; --fail-on-miss opt-in), the assembled payload matching AskResponse/AnswerSource with no retrieval-local leakage, the unchanged retrieval baseline (hit@5 0.857 / recall@5 0.857 / MRR 0.857), contracts/validate_examples.py passing, synthetic-only labelled fixtures, no real legal fact, and that contracts/, retrieval.py, source_catalog.py, main.py, knowledge/source_catalog.json, passages.schema.json, requirements.txt, scripts/init.sh and all client/shared code are untouched with no repo dependency. Non-blocking findings carried forward: F1 (prefix-only marker/sources invariant; fix before the hosted-model path or answer_source_cards) and F2 (non-iterable source_markers raises TypeError instead of returning generation_error at the model seam); N1 scripts/init.sh banner is stale (spec mandates no change); N3 spec lists extra retrieval imports the module deliberately omits.
