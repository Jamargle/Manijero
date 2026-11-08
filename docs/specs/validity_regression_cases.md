# Add validity cases: repealed RD 1077/2014, expired deadline, and voluntary digital notebook

## Source metadata

- `id`: validity_regression_cases · `area`: evaluation · `depends_on`: `validity_checker`, `seed_corpus_expansion` · `status` at planning: `not_started`
- User-visible behavior: none new. The reviewed evaluation set gains three validity regression cases, and one offline test pins how `/ask` answers them on the reviewed corpus: no claim that a repealed or uncovered rule is in force or mandatory, and an explicit expired-deadline notice.
- Verification: offline pytest through the real `/ask` route on the canonical corpus (BM25, extractive, sockets blocked) plus the report-only evaluator; commands in Focused verification.
- Notes: Owner decisions 2026-11-07, defaults:
  - Add three validity regression cases to the reviewed evaluation set, grounded only in reviewed source/catalog metadata. Never invent legal facts. If a needed source is not in the reviewed corpus, the case expects an honest abstention instead, and the gap is recorded.
    1. Repealed RD 1077/2014: the app must not present it as in force. It may say it is repealed, or point to the replacing rule, only if a reviewed source states it.
    2. An expired deadline: the answer must flag it as expired (`answer_deadline_notices` behavior) against an injected as-of date.
    3. Voluntary digital notebook (cuaderno digital de explotación): the answer must not call it mandatory where reviewed sources say it is voluntary.
  - Cases run offline in the existing evaluation harness with deterministic checks. No model or network in tests. No change to canonical knowledge unless already reviewed.
  - Developer-only: no owner-guide step. Acceptance: validator accept is final, no owner walkthrough.
  - Planner grounding decisions (from the reviewed corpus on 2026-11-08, see appendix research):
    - Case 1 is an **abstention**. No reviewed catalog source or passage names RD 1077/2014. `rd_1047_2022` is reviewed, but only for its SIGPAC definition passage, and no reviewed passage states the repeal. Gap: a reviewed repeal provision would be needed before the app may say "derogado" or name the replacement.
    - Case 2 is **grounded** in `dl_1_2026` / `pasaje-plazo-presentacion-2026-andalucia`, with reviewed `official_deadline` `2026-05-15`.
    - Case 3 is an **abstention**. No reviewed source covers the digital notebook. `rd_1054_2022` was reviewed `not_added` because SIEX and the digital notebook are a pinned "not yet covered" topic (`knowledge/pac_coverage.md`). Gap: no reviewed source states whether the notebook is voluntary.
  - Correction 2026-11-08 (coordinator, from an implementer run on unchanged code): case 1 expects `no_evidence` (no candidates), not the planner-assumed `false_premise`. Either reason is an honest abstention under the owner decision.

## Goal

Make the three validity risks named by the owner permanent, deterministic regressions in the reviewed evaluation set. Each case must reflect only what the reviewed corpus supports. A repealed instrument the corpus does not contain abstains rather than being answered. A reviewed deadline that has passed by the injected as-of date carries the code-owned expired notice. An uncovered obligation question abstains rather than calling the notebook mandatory. If the corpus later gains a source for case 1 or case 3, a test fails so that the case is revisited.

## Non-goals

- Adding, approving, or editing catalog sources, passages, `official_deadline` values, releases, or indexes. This includes adding RD 1077/2014, a repeal passage from RD 1047/2022, or RD 1054/2022.
- Changing `/ask`, retrieval, generation, abstention copy, deadline notices, the question-scope guard, input guardrails, or the validity checker.
- Adding a coverage omission such as "cuaderno digital". The scope guard must stay one-to-one with the declared omissions (`test_question_scope.py`).
- Changing the `pac-answer-eval-v2` schema or loader (no per-case as-of field, no forbidden-phrase field), and adding quality gates or thresholds to the report-only evaluator.
- Claiming that RD 1077/2014 is repealed, naming what replaced it, or claiming that the digital notebook is voluntary or mandatory anywhere in repository copy.
- Owner-guide steps, Compose UI, Spanish UI copy, or contract changes.

## Job story

When the corpus or answer path changes, I want three fixed validity questions checked offline against reviewed metadata, so I can catch the app presenting a repealed rule as current, hiding an expired deadline, or calling a voluntary obligation mandatory, before anyone sees it.

## Acceptance Scenarios

### 1. The repealed RD 1077/2014 case abstains

Given the canonical catalog, passages, campaign `2026`, as-of `2026-10-26`, and `k=5` · When case `rd-1077-2014-derogado` ("¿Sigue en vigor el Real Decreto 1077/2014?") is posted to `/ask` · Then the status is `abstained`, `sources` is empty, and the answer is exactly the pinned `no_evidence` message (retrieval returns no candidates, so the abstention reason is `no_evidence` with generation reason `no_candidates`). No answer text contains "1077", "vigor", "vigente", or "derog".

### 2. The expired deadline is flagged against the injected as-of date

Given the same inputs · When case `plazo-presentacion-vencido-2026` ("¿Ya terminó el plazo para presentar la solicitud única de 2026?") is posted · Then the status is `answered`, the answer cites `dl_1_2026` / `pasaje-plazo-presentacion-2026-andalucia`, and it contains both `15 de mayo de 2026` and `El plazo oficial terminó el 15 de mayo de 2026.` · And with as-of `2026-05-15` (the last open day), the same question is `answered` with the cooperative notice and without the `El plazo oficial terminó el` prefix.

### 3. The digital-notebook obligation case abstains

Given the same inputs · When case `cuaderno-digital-obligatorio` ("¿Es obligatorio el cuaderno digital de explotación?") is posted · Then the status is `abstained`, `sources` is empty, and the answer is exactly the pinned `no_evidence` message. No answer text contains "obligatori".

### 4. The cases live in the reviewed set and the report stays honest

Given `knowledge/pac_answer_eval.json` · When it is loaded and the evaluator runs at as-of `2026-10-26` · Then the file has 17 cases, including the three above. They use three new `boundary` areas, keep the eight declared omissions unchanged, and carry `review` `{reviewed_by: "Diego", reviewed_on: "2026-11-07", role: "author_only"}`. The abstention cases carry no source, passage, or fact expectations. All three rows report `expected_state_match` and, for case 2, `source_match`, `passage_match`, and `critical_facts_match` as true. The 14 earlier rows are unchanged.

### 5. A new reviewed source forces a revisit

Given a catalog or passage set in which a source title, URL, passage text, or location mentions `1077/2014`, or a passage mentions "cuaderno digital" or "cuaderno de explotación", or the reviewed `official_deadline` of `pasaje-plazo-presentacion-2026-andalucia` is no longer `2026-05-15` · When the grounding-precondition test runs on it · Then it fails with a message telling the reviewer to revisit that case's grounding decision. On today's canonical files it passes.

### 6. Offline and deterministic

Given the tests run · Then no socket is opened, no generation provider, hybrid retrieval, release root, or answer cache is active, and two runs give identical responses. `knowledge/source_catalog.json`, `knowledge/passages.json`, and every release or index file are byte-identical before and after.

## Technical approach

- **Cases only in data.** Append the three cases to `knowledge/pac_answer_eval.json` exactly as stated in the scenarios. Case 2 sets `expected_source_ids` `["dl_1_2026"]`, `expected_passage_ids` `["pasaje-plazo-presentacion-2026-andalucia"]`, and `critical_facts` `["15 de mayo de 2026", "El plazo oficial terminó el 15 de mayo de 2026."]`. Append three `boundary` areas:
  - `norma-derogada` — "Norma cuya vigencia no consta en una fuente revisada"
  - `plazo-vencido` — "Plazo oficial revisado ya vencido en la fecha de evaluación"
  - `cuaderno-digital-fuera-de-alcance` — "Cuaderno digital de explotación, tema aún no cubierto"
  
  Keep the `omissions` list, the schema, and the loader unchanged.
- **Grounding mechanics (no code change).**
  - Case 1: retrieval returns no candidates for the question, so `answer_or_abstain` (`backend/app/abstention.py`) returns `no_evidence` (`no_candidates`) before the presupposition check runs. This was observed by the implementer on unchanged code.
  - Case 2: the existing `deadline_paragraph` (`backend/app/deadline_notices.py`) is applied to the cited passage's reviewed `official_deadline`.
  - Case 3: no passage shares an exact BM25 token with the question, so the answer is `no_evidence`.
- **New test `backend/tests/test_validity_regression_cases.py`.** Use the same dependency overrides as `backend/scripts/evaluate_pac_answers.py` (corpus documents, as-of, campaign, `k`) with `TestClient(app)`. Clear `MANIJERO_GENERATION_PROVIDER`, `MANIJERO_RETRIEVAL_MODE`, and `MANIJERO_KNOWLEDGE_RELEASE_ROOT`, set `MANIJERO_ANSWER_CACHE=off`, and block sockets as in `test_source_validity.py`. Compare answers with `ABSTENTION_MESSAGES`, `COOPERATIVE`, and `EXPIRED_PREFIX` imported from the app, never with retyped copy. Run the three cases through `answer_eval.evaluate` on the real route for scenario 4, and add the grounding-precondition test for scenario 5 over the canonical files plus a tmp-path mutation for each trigger.
- **Stop rule.** If scenario 1, 2, or 3 fails on the unchanged pipeline, do not reword the case to pass, weaken the expectation, or change `/ask`. Record the actual outcome in the appendix evidence and report a blocker for an owner decision.
- **Count updates.** Existing tests that pin the case-set size move to the new totals: 17 cases, 12 answered, 5 abstained, 8 boundaries. Reviewed answered questions go from 11 to 12 in `test_question_scope.py`. The topic counts are unchanged.

## Expected file changes

- `knowledge/pac_answer_eval.json` — modify; three areas and three cases (owner-approved addition to the reviewed set).
- `backend/tests/test_validity_regression_cases.py` — create; scenarios 1–6.
- `backend/tests/test_pac_answer_eval.py`, `backend/tests/test_question_scope.py`, `backend/tests/test_local_load.py` — modify count assertions only.
- `knowledge/pac_coverage.md` — modify "Evaluación de respuestas revisada": three matrix rows, totals (17 cases, 3 topics / 9 cases, 8 boundaries / 8 cases), and the two grounding gaps in one short paragraph (this file owns the gap record).
- `knowledge/README.md` (line ~107), `backend/README.md` (case-count sentences near lines 1068 and 1329), `docs/risks-and-open-questions.md` (the "narrow sample" row) — update the case/boundary counts only. Historical measurement lines (for example, `docs/constraints/answers-and-knowledge.md` line ~94) stay as written.
- `docs/constraints/answers-and-knowledge.md` — one MUST (see below).
- `feature_list.json`, `PROGRESS.md`, `docs/progress/current-state.md`, `docs/progress/known-limitations.md`, `docs/progress/session-log.md`, `docs/validations/validity_regression_cases.md` — implementer/validator only, after evidence exists.
- No change: `source_catalog.json`, `passages.json`, schemas, `backend/app/**`, `backend/scripts/**`, `docs/owner-guide.md`.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: not needed — no boundary, module, or runtime surface changes.
- `docs/constraints/answers-and-knowledge.md`: update "Safety evaluation" with one MUST. A validity regression case MUST rest only on reviewed catalog or passage metadata. When the reviewed corpus lacks the source, the case MUST expect abstention, and a precondition test MUST fail once such a source appears. Reason: `validity_regression_cases`.
- `AGENTS.md`: not needed — no workflow change.
- Other: `knowledge/pac_coverage.md` owns the case matrix and gaps. `known-limitations.md` and `current-state.md` move from 14 to 17 cases at acceptance. `docs/owner-guide.md`, `DESIGN.md`, and `CONTEXT.md`: not needed.

## Focused verification (required)

`./scripts/init.sh --feature validity_regression_cases` runs this block unchanged from the repository root. Line 1 runs the new test and every suite whose case-set counts or questions change. Line 2 is the report-only evaluator at the pinned inputs. It exits `0`, and its aggregates are compared with the appendix baseline.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_validity_regression_cases.py tests/test_pac_answer_eval.py tests/test_question_scope.py tests/test_input_guardrails.py tests/test_local_load.py -q
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-26 --k 5
```
<!-- verify:end -->

## Appendix

See [`validity_regression_cases.appendix.md`](validity_regression_cases.appendix.md) for research, plan, evidence, and the validator checklist.
