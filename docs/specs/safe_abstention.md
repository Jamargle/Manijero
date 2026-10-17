# Feature Spec: `safe_abstention`

## Source metadata

- Feature: `safe_abstention` — Abstain when evidence is inadequate
- Area: backend
- Depends on: `grounded_answer_generation` (accepted)
- Feature-list behavior: for unsupported, stale, conflicting, or insufficient evidence, the assistant clearly says it cannot answer safely and gives an appropriate next step.
- Feature-list verification: submit out-of-corpus and false-premise questions and confirm they return an abstention without invented legal facts.
- Feature-list note: critical dates and amounts require especially strong source evidence.
- Scope size: one backend decision module (widen the accepted `NotAnswered` handoff into a stable abstention taxonomy that also detects stale, conflicting, false-premise, and unsafe cases) plus one offline evaluation CLI. One data shape, one decision flow; correctly sized. It stops at the `AskResponse` payload and does not touch any route, client, contract, or accepted module.

## Goal

Turn every "no safe answer" outcome into one deterministic, offline, code-owned **abstention decision**. `backend/app/abstention.py` composes the accepted `generate_grounded_answer` pipeline and adds the pre-checks the generation feature explicitly deferred: an unsupported (false-premise) question, a corpus that cannot be confirmed current as of `--as-of`, and two critical passages that disagree. Every abstention carries a stable machine-readable reason and produces a contract-conformant `AskResponse` with `status: abstained`, **no sources**, and a fixed plain-Spanish limitation with a next step. Code owns the copy; no generator, prompt, model, or clock contributes to it, and the copy contains no digit and no date, so an abstention can never invent a deadline or an amount.

## Non-goals

- Serving HTTP or wiring `POST /ask`. `backend/app/main.py` keeps `/health` as its only route, and no `FastAPI`/Pydantic dependency is added.
- Changing the accepted contract. `AskResponse` rejects extra properties, so the abstention sub-reason stays a Python-level value; no `reason` field is added to the wire payload and `contracts/` is untouched.
- Client presentation. How an abstention looks (layout, icon, colour, announcement, source-card absence) is `response_states`; retry/offline copy for a service failure is `network_error_recovery`. The backend only supplies a pinned message the client may render.
- Semantic judgement (NLI/entailment), model-based conflict detection, or a hosted LLM. Detection stays lexical and conservative, as recorded in `MasterPlanV3` §12.4 and `docs/risks-and-open-questions.md`.
- Score thresholds as release gates. No calibrated score cutoff is introduced; `land_safety_evaluation` owns measurement.
- Land applicability, land clarification, or `land_scope` behaviour beyond echoing a validated value: those belong to `minimal_land_context` / `land_clarification`.
- Rewriting or touching `backend/app/generation.py`, `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/tests/test_generation.py`, `backend/scripts/evaluate_generation.py`, `init.sh`, or any client/shared code.
- Adding real legal documents, deadlines, amounts, article numbers, or a canonical `knowledge/passages.json`. All fixtures stay synthetic and labeled.

## Job story

When the retrieved evidence is missing, not current, contradictory, or does not support what the question presupposes, I want the assistant to stop and say so in plain Spanish with a concrete next step — because a person who acts on an invented Spanish deadline or amount can lose real money, and an honest "no lo sé" is always better than a confident wrong answer.

## Acceptance scenarios

### Out-of-corpus question abstains with no evidence

Given a question whose tokens match no reviewed passage, when `answer_or_abstain` runs, then it returns `Abstention(reason="no_evidence")`, no text from any generator is emitted, and `to_abstention_response` yields `status: abstained`, `sources: []`, `land_ids_to_choose: []`, and a non-blank pinned Spanish message containing no digit and no date.

### False-premise question abstains instead of answering around the premise

Given a question that names an instrument or article (`Real Decreto`, `RD`, `ley`, `orden`, `decreto`, `reglamento`, `norma`, or `artículo N`, with an optional `N/YYYY` identifier) and retrieval returns candidates that never contain that identifier, when `answer_or_abstain` runs, then it returns `Abstention(reason="false_premise")` and the answer never asserts the presupposed fact; when the identifier does appear in a retrieved candidate, the pipeline proceeds normally.

### Stale corpus abstains for every question

Given a catalog that declares sources but has no source eligible as of `--as-of` (expired, non-`approved`, or non-`current`), when the corpus is prepared, then it yields a corpus-level `Abstention(reason="stale_evidence")`, every question abstains with that reason, and no candidate or answer text is emitted.

### Conflicting critical evidence abstains instead of choosing

Given the top candidates include two `critical` passages that state different canonical values for the same unit (for example two fictitious deadlines in `días`), when `answer_or_abstain` runs, then it returns `Abstention(reason="conflicting_evidence")`. Two `critical` passages with different, non-overlapping units (a deadline in `días` and an amount in `euros`) are **not** a conflict, so an ordinary covered question still answers.

### Insufficient evidence abstains after candidates were found

Given retrieval returns candidates but the accepted pipeline produces no verifiable claim (for example a multi-sentence reviewed excerpt fails the per-sentence citation rule), when `answer_or_abstain` runs, then it returns `Abstention(reason="insufficient_evidence")` carrying the original generation reason and issue codes, and nothing from the rejected draft is emitted.

### Unsafe request abstains and the generator is never the authority

Given a request whose only candidate contains a starter eligibility phrase, when the pipeline runs, then the draft is rejected as `policy_failed`, `answer_or_abstain` returns `Abstention(reason="unsafe_request")`, and no eligibility statement reaches the response.

### Deterministic, offline, and contract-conformant

Given the same catalog, passages, question, `as-of`, and `k`, when the pipeline runs twice, then the outcome, reason, and assembled payload are identical, two `--json` CLI runs are byte-identical, a socket guard that blocks `socket.socket` still lets the pipeline abstain, and every payload matches `contracts/openapi.yaml#/components/schemas/AskResponse` with `contracts/validate_examples.py` still passing.

## Repository research

Inspected:

- `feature_list.json`: this feature is `not_started`; `grounded_answer_generation` is `accepted`; `response_states` and `land_safety_evaluation` depend on it.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`: abstain when evidence is absent, ambiguous, expired, conflicting, or inapplicable; never invent dates/amounts/eligibility/article numbers; fixed next step such as the Oficina Comarcal Agraria or the cooperative; critical amounts and deadlines need especially strong evidence.
- `docs/risks-and-open-questions.md` (high risk "Unsupported or outdated legal answer"; medium risk "Critical sources contradict each other or show amendment history … abstain when status cannot be established") and `MasterPlanV3.md` §8.1 (validation cascade, `found=false` ⇒ fixed message), §9.2 ("correct abstention on trap questions" candidate gate), §12.4 (trap taxonomy: out of corpus/domain, cooperative practices, land ambiguity, false premise, organic extrapolation, prompt injection, personalized advice).
- `docs/specs/grounded_answer_generation.md` and `docs/validations/grounded_answer_generation.md`: generation returns `NotAnswered(reason, issues, claims)` with reasons `invalid_question`, `no_candidates`, `generator_abstained`, `grounding_failed`, `policy_failed`, `generation_error`; semantic grounding, conflict detection, and user-visible abstention copy are explicitly handed to `safe_abstention`; finding F2 (non-iterable `source_markers`) is a hardening item for the generator seam.
- `CONSTRAINTS.md`: two answer-grounding MUST rules (nothing user-visible may bypass `verify_draft`; markers/`sources`/notice are code-owned).
- `backend/app/generation.py`: `Answered`, `NotAnswered`, `GroundingIssue`, `ClaimVerdict`, `generate_grounded_answer(question, retriever, *, k, max_claims, land_scope, as_of, generator)`, `LAND_SCOPES`, `MAX_QUESTION_CHARS`, `MAX_ANSWER_CHARS`, `ELIGIBILITY_PHRASES`, `normalize_text`, `extract_figures`, `to_answer_response`.
- `backend/app/retrieval.py`: `Retriever.search(question, k)` is deterministic and returns `()` for a blank/out-of-vocabulary question and a zero-match index; `Retriever.from_documents` raises `CatalogRejectedError` for a non-`approved`, non-`current`, or expired catalog; public `eligible_source_ids`, `source_is_eligible`, `PassageSetError`, `load_passage_set`, `DEFAULT_K`, `PASSAGE_SET_SCHEMA_VERSION`.
- `backend/app/source_catalog.py`: only `review_status: approved` and `lifecycle_status: current` are accepted, and `valid_until` before `--as-of` is ineligible, so any currency failure rejects the whole catalog.
- `contracts/openapi.yaml` + `contracts/validate_examples.py` + `contracts/examples/response-abstained.json`: `AskResponse` has `additionalProperties: false` and exactly `{status, answer, sources, land_scope, land_ids_to_choose}`; `abstained` requires a non-blank `answer` ≤ 1200, `sources == []`, and `land_ids_to_choose == []`.
- `backend/scripts/evaluate_generation.py`, `backend/tests/test_generation.py`, `backend/tests/fixtures/generation/*`, `backend/tests/fixtures/retrieval/catalog_expired.json` / `catalog_not_current.json` / `catalog_not_approved.json`: the accepted CLI conventions (`--catalog/--passages/--eval/--as-of/--k/--json/--fail-on-miss`, exit `0`/`1`/`2`, deterministic `--json`), the synthetic-fixture style, and the reusable ineligible-catalog fixtures.
- `knowledge/README.md`, `backend/README.md`, `init.sh`, `PROGRESS.md`: corpus policy, backend boundaries, and the fact that `init.sh` has no backend command (KMP checks only).

Absent, and therefore not assumed: a `POST /ask` route, any FastAPI dependency on the pipeline, a model provider, a semantic judge, a canonical `passages.json`, an `ARCHITECTURE.md`, and any persistent E2E command. This worktree has no `python` on `PATH` and the system interpreter has no `pytest`; accepted features ran pytest from a temporary out-of-repo venv with no repo dependency.

## Technical approach

### Evidence boundary and accepted-module reuse

`backend/app/abstention.py` is standard library plus `app.generation` and `app.retrieval` (and read-only `app.source_catalog` helpers if needed), all offline. It never reads a catalog or passage file itself, never re-implements eligibility or grounding, never calls a model or the network, and never re-reads user content for a decision. `backend/app/generation.py`, `backend/app/retrieval.py`, and `backend/app/source_catalog.py` are imported unchanged.

`answer_or_abstain` searches once with the retriever to run its pre-checks and then calls the accepted `generate_grounded_answer` for the actual drafting/verification. `Retriever.search` is deterministic and tested, so both steps see the same ranked candidates; a test asserts the searched ranks equal the ranks the generator receives.

### Abstention taxonomy (stable, machine-readable)

Exactly these reason codes, in this order:

| Reason | Trigger |
|---|---|
| `invalid_question` | Blank question, or longer than the accepted 2000-character bound. |
| `no_evidence` | Retrieval returned no candidate (out-of-corpus/unsupported). |
| `insufficient_evidence` | Candidates existed but no verifiable claim could be assembled (generation `grounding_failed`). |
| `stale_evidence` | The corpus declares sources but none is eligible as of `as_of` (expired, non-`approved`, non-`current`). |
| `conflicting_evidence` | Two `critical` candidates in the citation window state different canonical values for the same unit. |
| `false_premise` | The question presupposes an instrument/article identifier that no retrieved candidate contains. |
| `unsafe_request` | A generated claim asserts the person's legal status (generation `policy_failed`). |
| `generator_abstained` | The generator explicitly declined (its copy is discarded). |
| `generation_error` | The generator raised or returned an unusable object. |

Generation reasons map to this taxonomy one way: `no_candidates → no_evidence`, `grounding_failed → insufficient_evidence`, `policy_failed → unsafe_request`, and `invalid_question`/`generator_abstained`/`generation_error` unchanged. The original generation reason and the issue codes are preserved on the `Abstention` for traceability and CLI reporting; the wire payload carries only the accepted `AskResponse` keys.

### Decision rules

1. **Fail closed, never repair.** An abstention never emits a draft sentence, a candidate excerpt, a source, a figure, or a date, and never falls back to model or unreviewed knowledge. The whole draft is already discarded by `verify_draft`; this feature only decides and phrases.
2. **No evidence, no answer.** An empty candidate tuple (or an ineligible corpus) is itself the decision; the generator is not called and no text is produced.
3. **False premise = unconfirmed presupposition.** A small tested extractor finds normalized instrument/article references (`real decreto`, `rd`, `decreto`, `decreto-ley`, `ley`, `orden`, `reglamento`, `norma`, plus an optional `N`, `N/YYYY`, `n.º N`, or `artículo N`). If any extracted identifier is absent after normalization from the union of the retrieved candidates' `excerpt` and `location`, the question's presupposition is not supported by the retrieved evidence and the pipeline abstains. This is conservative (a lexical retrieval miss also abstains) and it never asserts that the instrument is false; it only refuses to answer around it.
4. **Conflict is unit-anchored and critical-only.** For the citation window (the first `max_claims` candidates, default 2), collect `(unit, canonical value)` pairs from each `critical` candidate using a fixed documented unit list (`días`, `meses`, `años`, `euros`, `hectáreas`, `semanas`, `%`). If the same unit yields two different canonical values from two different candidates, abstain. Non-`critical` candidates never trigger this, and two critical passages about different units are not a conflict, so ordinary covered questions keep answering.
5. **Critical evidence is extra-guarded.** Because the note says critical dates and amounts require especially strong evidence, `critical` candidates are the only ones eligible for the conflict check, are already extractive-only in the accepted pipeline, and cannot be stated from a non-current corpus (`stale_evidence`).
6. **Currency is a corpus property.** `prepare_corpus(catalog_document, passage_document, as_of)` returns a `Retriever`, or a corpus-level `Abstention(reason="stale_evidence")` when the catalog declares sources but `eligible_source_ids(...)` is empty. A malformed passage set, an unknown `source_id`, or an unreadable file stays a hard error (`PassageSetError`/`CatalogReadError` propagates), because a broken deployment must be loud, not silent.
7. **Code owns the copy.** `ABSTENTION_MESSAGES` maps every reason to one pinned Spanish string; `Abstention` has no text field and `to_abstention_response` resolves the message by reason, so no caller can inject copy. Every message is non-blank, ≤ 1200 characters, contains no digit/date, avoids the `ELIGIBILITY_PHRASES`, and ends with a next step (rephrase, or consult the Oficina Comarcal Agraria / cooperative).
8. **Contract-shaped output.** `to_abstention_response(abstention, *, land_scope="general")` returns exactly `{status, answer, sources, land_scope, land_ids_to_choose}` with `status="abstained"`, `sources=[]`, `land_ids_to_choose=[]`, the pinned message, and a `land_scope` validated against generation's `LAND_SCOPES`; an unknown reason or scope raises `ValueError` rather than emitting.

### Pinned message set (byte-for-byte tested, one per reason)

- `invalid_question`: `Necesito una pregunta para poder ayudarte. Escribe tu duda en pocas palabras e inténtalo otra vez.`
- `no_evidence`: `No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa.`
- `insufficient_evidence`: `Los documentos oficiales que tengo no me permiten responderte con seguridad. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa.`
- `stale_evidence`: `No puedo comprobar que la información oficial que tengo siga vigente, así que no te doy una respuesta. Comprueba la convocatoria vigente o pregunta en tu oficina comarcal agraria.`
- `conflicting_evidence`: `He encontrado documentos oficiales que no coinciden entre sí y no puedo darte un dato seguro. Confírmalo en tu oficina comarcal agraria o con tu cooperativa.`
- `false_premise`: `No puedo confirmar ese dato con los documentos oficiales revisados. Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa.`
- `unsafe_request`: `No puedo confirmar tu situación concreta ni calcular lo que te corresponde. Consulta tu caso en tu oficina comarcal agraria o con tu cooperativa.`
- `generator_abstained`: `Con los documentos oficiales que tengo no puedo preparar una respuesta segura para esta pregunta. Consulta con tu oficina comarcal agraria o con tu cooperativa.`
- `generation_error`: `Ahora mismo no he podido preparar la respuesta. Vuelve a intentarlo dentro de un momento; si sigue igual, pregunta en tu oficina comarcal agraria o con tu cooperativa.`

### Evaluation harness

`backend/scripts/evaluate_abstention.py`, an offline report-only CLI mirroring `evaluate_generation.py` (explicit `--as-of`/`--k`, `--json` with `sort_keys=True`/`ensure_ascii=False`, no network, diagnostics without content). The eval file is JSONL with exactly `{"question", "expect"}`, where `expect` is `answered` or one of the nine reason codes (unknown `expect` is a harness error). It prepares the corpus (reporting `current` or `not_current`), runs `answer_or_abstain` per line, and prints the outcome, the reason, the generation reason, the issue codes, and the emitted message.

Enforced invariants (exit `1`, because they mean an abstention leaked something): every abstention payload has empty `sources` and `land_ids_to_choose`, a non-blank message ≤ 1200 characters, a message with no digit/date, and a reason inside the taxonomy. Answer coverage is report-only unless `--fail-on-miss` is passed. Exit `0` report with all invariants holding; `1` an invariant failed or (`--fail-on-miss`) an outcome differed from `expect`; `2` an unreadable/rejected input or invalid argument (`PassageSetError`, `CatalogReadError`, malformed JSONL, unknown key/`expect`).

## Expected file changes

- Create `backend/app/abstention.py` — reason taxonomy, pinned messages, `Abstention`, `prepare_corpus`, `answer_or_abstain`, the false-premise and unit-conflict helpers, and `to_abstention_response`.
- Create `backend/scripts/evaluate_abstention.py` — offline report-only CLI with the `0`/`1`/`2` exit contract.
- Create `backend/tests/test_abstention.py` — focused tests (target ~70–90 tests).
- Create `backend/tests/fixtures/abstention/{catalog.json,passages.json,eval_questions.jsonl,eval_questions_stale.jsonl}` — synthetic approved catalog, labeled reviewed passages (one ordinary, two critical passages that conflict on `días`, one multi-sentence passage, one eligibility-phrased passage), and expectation lines for both a current and an expired-catalog run. Reuse `backend/tests/fixtures/retrieval/catalog_expired.json` (read-only) for the corpus-level stale case.
- Update `backend/README.md` — the abstention boundary, taxonomy, pinned-copy rule, CLI, and that `/health` remains the only route.
- Update `CONSTRAINTS.md` — one new MUST rule: no component may emit an abstention that carries sources, a figure, or a date, and abstention copy is code-owned, never generated.
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with the real status, commands, and results (the orchestrator owns this; the planning pass records the spec link only).

Explicitly **not** changed: `contracts/` (including `openapi.yaml`, examples, and `validate_examples.py`), `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`, `backend/app/generation.py`, `backend/scripts/evaluate_generation.py`, `backend/tests/test_generation.py`, `knowledge/*`, `backend/requirements.txt`, `init.sh`, and all client/shared/Android/Desktop code.

`init.sh`: no change. It currently executes the KMP verification checks (`--check` prints guidance; `--verify` runs the shared/Android/Desktop Gradle targets) and has no backend command; this backend slice is verified with the documented Python commands, and no long-running process or new mode is added. (The stale `--check` banner text it prints is an accepted, tracked housekeeping item, not part of this feature.)

## Visual design impact

None. No Compose UI and no client code change. The client feature `response_states` owns how an abstention is presented; this spec only fixes the backend-facing phrasing contract (one pinned Spanish message per reason). Because `AskResponse` forbids extra properties, the sub-reason is not on the wire, so a client cannot branch on it without a contract change — out of scope here.

## Durable documentation impact

- `backend/README.md`: update; it is the durable boundary document for the backend and now describes the abstention decision and CLI.
- `CONSTRAINTS.md`: update; it is the durable MUST/MUST NOT register, and "an abstention never carries sources, figures, or dates and its copy is code-owned" is a mechanism-level rule later features must follow.
- `knowledge/README.md`: no update needed; the corpus contract and reviewer guidance do not change (the feature reads corpus metadata through the accepted retriever only).
- `AGENTS.md`: no update; "abstain when evidence is inadequate" and "do not invent legal facts" already govern, and this feature makes them executable.
- `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`, `MasterPlanV3.md`, `DESIGN.md`: no update; they already state the abstention principle and the trap taxonomy.
- `ARCHITECTURE.md`: not needed; absent, and a focused offline decision module does not establish a broader runtime architecture.
- `PROGRESS.md` and `feature_list.json`: update after verification with the commands actually run; state plainly that fixtures are synthetic, detection is lexical, thresholds are not release gates, and no route exists.

## Implementation plan and tasks

1. Add `backend/app/abstention.py`: `ABSTENTION_REASONS`, `ABSTENTION_MESSAGES`, the generation-reason map, the `Abstention` dataclass (no text field; `message` property), `prepare_corpus`, `answer_or_abstain`, the presupposition extractor, the unit-anchored conflict helper, and `to_abstention_response`.
2. Add the synthetic `backend/tests/fixtures/abstention/` set (labeled synthetic, no real deadline/amount/article) and the two expectation files.
3. Add `backend/scripts/evaluate_abstention.py` with strict input validation, per-question reporting, aggregate counters (`abstentions_with_sources`, `abstentions_with_figures`, `abstention_invariants_hold`), `--json`, and the `0`/`1`/`2` contract.
4. Add `backend/tests/test_abstention.py`: taxonomy/message invariants; payload shape; every generation reason mapped; `prepare_corpus` current vs stale vs hard error; false-premise hit/miss; unit conflict vs different-units non-conflict; no-answer-without-evidence (generator never called); determinism; socket-guard offline; content-silent diagnostics; CLI exit `0`/`1`/`2`; and a regression assertion that `answer_or_abstain` still returns `Answered` for the accepted generation fixtures.
5. Run the CLI on the current and expired catalogs, the focused and full pytest suites, `contracts/validate_examples.py`, the unchanged generation and retrieval baselines, `py_compile`, and `git diff --check`; fix inconsistencies.
6. Verify the feature-list verification literally: record one out-of-corpus and one false-premise question returning `abstained` with their reasons and messages, and confirm no invented legal fact appears.
7. Update `backend/README.md` and `CONSTRAINTS.md`, then record evidence and status with only the commands actually run.

## Verification plan and evidence

Run from the repository root:

```sh
python3 backend/scripts/evaluate_abstention.py \
  --catalog backend/tests/fixtures/abstention/catalog.json \
  --passages backend/tests/fixtures/abstention/passages.json \
  --eval backend/tests/fixtures/abstention/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
python3 backend/scripts/evaluate_abstention.py \
  --catalog backend/tests/fixtures/retrieval/catalog_expired.json \
  --eval backend/tests/fixtures/abstention/eval_questions_stale.jsonl \
  --as-of 2026-10-13 --k 5
python3 contracts/validate_examples.py
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
cd backend && python -m pytest tests/test_abstention.py
cd backend && python -m pytest
python3 -m py_compile backend/app/abstention.py backend/scripts/evaluate_abstention.py backend/tests/test_abstention.py
git diff --check
```

Capture: the out-of-corpus and false-premise questions with their reason, message, and empty `sources` (the feature-list verification); the expired-catalog run where every question is `stale_evidence`; the conflicting-critical question abstaining while a covered question still answers; `--fail-on-miss` exiting `1` on a deliberately mismatched expectation and `0` on the fixtures; byte-identical repeated `--json` runs; the socket-guard result; pytest counts for the new file and the full suite; the contract validator output plus confirmation that `contracts/` is unchanged; and the unchanged generation (`5 answers, 8 claims, 0 ungrounded, 1 no-evidence`) and retrieval (`hit@5 = 0.857 (6/7)`) baselines. Note the environment: pytest runs from a venv outside the repository and no dependency is added. No browser/API/E2E test is required because there is no `/ask` route and no persistent E2E harness; the CLI plus unit tests cover the decision.

## Validator checklist

- [ ] An out-of-corpus question returns `abstained` with reason `no_evidence`, empty `sources`, and a pinned Spanish message with no digit and no date.
- [ ] A false-premise question (presupposed instrument/article absent from all candidates) returns `abstained` with reason `false_premise` and never asserts the presupposed fact; the same identifier present in a candidate does not trigger it.
- [ ] An expired/non-`current`/non-`approved` catalog yields a corpus-level `stale_evidence` abstention for every question, while a malformed passage set or unreadable file stays a hard error.
- [ ] Two critical candidates disagreeing on the same unit abstain as `conflicting_evidence`; two critical candidates about different units still answer, so the accepted covered question is not over-abstained.
- [ ] Candidates without a verifiable claim map to `insufficient_evidence`; an eligibility assertion maps to `unsafe_request`; generator errors/abstentions map to their reasons; nothing from a rejected draft is emitted.
- [ ] Every assembled payload matches `AskResponse` exactly, `contracts/validate_examples.py` passes, and `contracts/` is untouched.
- [ ] The decision is deterministic (byte-identical `--json` runs), offline (socket guard), and content-silent in diagnostics (no question or excerpt text outside the mandated CLI review output).
- [ ] `backend/app/generation.py`, `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`, `backend/requirements.txt`, `init.sh`, `knowledge/*`, and all client/shared code are unchanged; fixtures are synthetic and labeled with no real legal fact; `/health` remains the only route.
- [ ] `feature_list.json`/`PROGRESS.md` report only the commands actually run and state that detection is lexical and thresholds are not release gates.

## Risks and handoff notes

The false-premise and conflict checks are lexical and conservative: a retrieval miss can cause an abstention, and unit-anchored conflict detection can flag two unrelated critical passages that share a unit. Both err toward abstaining, which is the safe direction, and are documented as approximations; a semantic judge/NLI and the measured trap set belong to `land_safety_evaluation`. Broader conflict detection is intentionally narrow so the accepted covered critical question (`días` deadline plus `euros` amount) keeps answering; widening it must be measured, not assumed. The corpus is a tiny implementer-authored synthetic set, so no reason code here is a coverage or answer-quality claim.

Handoffs: `response_states` owns how an abstention is presented and must not add a legal fact or contradict the pinned message; `network_error_recovery` owns retry/offline copy for `generation_error`; `land_clarification`/`minimal_land_context` own `land_scope`; `land_safety_evaluation` owns trap-question measurement and any threshold. No feature currently owns wiring `POST /ask` in FastAPI or the client's production `AnswerService`, so the abstention reason stays observable only through this CLI and the tests until that route exists; recommend the route slice after this feature, when one route can serve `answered`, `abstained`, and `needs_land_clarification`. Carried-forward accepted finding F2 (non-iterable `source_markers` in the generator seam) is unchanged here and still owed to the hosted-model path.

## Focused verification

`./init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5
./init.sh --backend-tests tests/test_abstention.py
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/safe_abstention.md. Added backend/app/abstention.py (stable 9-reason taxonomy, pinned ABSTENTION_MESSAGES, the deferred pre-checks, corpus preparation), backend/scripts/evaluate_abstention.py (offline report-only CLI with the 0/1/2 exit contract), backend/tests/test_abstention.py (178 focused tests), and synthetic fixtures backend/tests/fixtures/abstention/{catalog.json,passages.json,eval_questions.jsonl,eval_questions_stale.jsonl}. Updated backend/README.md (abstention boundary, taxonomy table, CLI, /health remains the only route) and CONSTRAINTS.md (one Abstention MUST rule). Standard library only, no /ask route, no new dependency, contracts/ and every named do-not-touch file untouched.
- Design: one frozen Abstention dataclass (reason, generation_reason, issues, claims) with no text field, whose message property resolves the pinned copy by reason, so code owns the copy; to_abstention_response emits exactly the accepted AskResponse keys with status abstained, sources [], land_ids_to_choose [], and a message that contains no digit and no date and ends with a next step. The sub-reason stays a Python-level value because AskResponse rejects extra properties, so the wire contract is unchanged. Pre-checks run before the generator: a blank or over-2,000-character question -> invalid_question (no search at all), a retrieval miss -> no_evidence, a presupposed instrument/article identifier absent from every candidate -> false_premise, and two critical candidates in the citation window stating different canonical values for the same documented unit -> conflicting_evidence. Generation reasons map one way: no_candidates -> no_evidence, grounding_failed -> insufficient_evidence, policy_failed -> unsafe_request, invalid_question/generator_abstained/generation_error unchanged, anything unrecognized -> generation_error. prepare_corpus returns a corpus-level stale_evidence Abstention when the catalog declares sources but eligible_source_ids is empty as of as-of (expired, non-approved, or non-current), and that Abstention is returned unchanged for every question.
- Commands actually run: cd backend && python -m pytest tests/test_abstention.py -> 178 passed; cd backend && python -m pytest -> 399 passed (221 existing + 178 new); python3 -m py_compile backend/app/abstention.py backend/scripts/evaluate_abstention.py backend/tests/test_abstention.py -> clean; git diff --check -> clean.
- Acceptance check on the current corpus: python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5 -> exit 0; corpus: current; eligible sources 2, indexed passages 7, excluded 0; answered outcomes 3, abstained outcomes 7, abstentions with sources 0, abstentions with figures 0, abstention invariants hold: yes, outcomes differing from expect: 0 (10 questions). Recorded outcomes: answered for the solicitud, norma and importe questions; conflicting_evidence for the fictitious plazo question (critical 30 dias vs critical 45 dias, issue unit_conflict, generation reason none); insufficient_evidence with generation reason grounding_failed and issue uncited_sentence for the multi-sentence riego excerpt; unsafe_request with generation reason policy_failed and issue eligibility_claim for the starter-eligibility excerpt; false_premise for both the Real Decreto sintetico and the numbered reglamento question (issue unconfirmed_presupposition); no_evidence for zzzz qqqq; invalid_question for a blank question. Two critical passages about different units (a dias deadline and a euros amount) still answer, so the accepted covered critical question is not over-abstained.
- Feature-list verification literally, one out-of-corpus and one false-premise question (temp jsonl outside the repo), both abstained with empty sources and no invented legal fact: '¿Cuánto cuesta matricular un tractor viejo?' -> outcome no_evidence (generation reason no_candidates, no issue codes, sources 0, message: No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa.) and '¿Qué dice el Real Decreto 123/2099 sobre el plazo de la solicitud?' -> outcome false_premise (issue unconfirmed_presupposition, sources 0, message: No puedo confirmar ese dato con los documentos oficiales revisados. Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa.); 0 answered, 2 abstained, 0 abstentions with sources, 0 abstentions with figures, invariants hold, 0 expect-mismatches. The identifier present in a candidate does not trigger false_premise (unit test: the norma question still answers).
- Stale corpus for every question: python3 backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/retrieval/catalog_expired.json --eval backend/tests/fixtures/abstention/eval_questions_stale.jsonl --as-of 2026-10-13 --k 5 (no --passages) -> exit 0; corpus: not_current; 0 answered, 3 abstained, every question stale_evidence with issue code stale_corpus, sources 0, and the pinned message; unit tests reproduce the same for catalog_not_approved.json and catalog_not_current.json and confirm the stale Abstention wins over an invalid question. A structurally broken catalog, a malformed passage set, an unknown source_id, and an unreadable file all stay hard errors (unit tests assert CatalogRejectedError/PassageSetError; the CLI exits 2), and the canonical empty knowledge/source_catalog.json still prepares a retriever with 0 sources and 0 passages.
- Exit contract and determinism: --fail-on-miss exits 0 on the fixtures and 1 on a deliberately mismatched expectation while printing byte-identical output; without the flag the same mismatch still exits 0; --k 0 exits 2 with '--k must be a positive integer'; a malformed eval line, an eval file with no questions, an invalid --as-of, a missing catalog, and a missing or malformed passage set each exit 2 with empty stdout. Two --json runs are byte-identical (cmp exit 0). An abstention payload that carries a source, a land choice, a blank or over-long message, a digit or a date, a non-abstained status, or an off-taxonomy reason makes the CLI exit 1, and the pure invariant helper is unit-tested per leak class.
- Offline and content-silent: tests monkeypatch socket.socket to raise and the pipeline still abstains (both prepare_corpus and answer_or_abstain), a test asserts abstention.py imports no socket/urllib/httpx/requests, and a test asserts no question text, excerpt text, or figure number reaches the issue diagnostics or the emitted message. A recorded generator draft is discarded whole (its copy never appears), and no model provider is configured: the only enabled generator is the accepted code-composed extractive one.
- Regression boundaries unchanged: python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5 -> exit 0, answers produced 5, claims checked 8, ungrounded claims 0, invented sources 0, no-evidence outcomes 1, grounding invariants hold: yes, outcomes differing from expect 0; python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5 -> hit@5 0.857 (6/7), recall@5 0.857, MRR 0.857; the 6 accepted generation fixture questions re-run through answer_or_abstain still resolve exactly as expected (5 answered, 1 no_evidence); python3 contracts/validate_examples.py -> 'Validated 2 request and 3 response examples against answer_api_contract'.
- Change scope: git status --porcelain shows only backend/README.md, CONSTRAINTS.md, feature_list.json, and PROGRESS.md modified (backend/README.md +54 and CONSTRAINTS.md +13 insertions) plus the new paths backend/app/abstention.py, backend/scripts/evaluate_abstention.py, backend/tests/test_abstention.py, and backend/tests/fixtures/abstention/; contracts/, backend/app/generation.py, backend/app/retrieval.py, backend/app/source_catalog.py, backend/app/main.py, backend/scripts/evaluate_generation.py, backend/tests/test_generation.py, knowledge/, backend/requirements.txt, init.sh, and all client/shared code are unmodified (checked per path with git status --porcelain). Fixtures are synthetic and labelled (fixture, no es una norma real, Sintético, cifra inventada); the only numeric material is explicitly fictitious figures and a deliberately impossible 999/2099 identifier, so no real deadline, amount, or article number was introduced.
- Not run, and honest gaps: Android/Desktop/Gradle and ./init.sh checks (no product UI, route, or shared code changed; init.sh has no backend command) and no browser/API/E2E test (there is no /ask route and no persistent E2E harness), so the abstention reason stays observable only through this CLI and these tests until the route slice exists. Detection is lexical and conservative, not semantic: a retrieval miss or two unrelated critical passages that share a unit can abstain, and prepare_corpus treats a catalog whose declared sources are all ineligible as stale even when the ineligibility comes from a malformed currency field (structurally broken catalogs stay hard errors). No calibrated score threshold and no trap-set measurement is introduced (land_safety_evaluation owns both), and the tiny implementer-authored corpus means no reason code here is a coverage or answer-quality claim. Carried-forward accepted generation finding F2 (non-iterable source_markers at the model seam) is unchanged. Environment note: this worktree has no python on PATH and the system interpreter has no pytest, so pytest ran from a temporary venv outside the repository (Python 3.9.6) with the repo's own requirements.txt installed into it; no dependency was added to the repo. Self-verified only; awaiting independent validation, so not marked accepted.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/safe_abstention.md). It did not trust the implementer report and independently reproduced: 178 focused / 399 full pytest passes; py_compile and git diff --check clean; the current-corpus CLI (exit 0; corpus current; 2 eligible sources, 7 indexed passages; 3 answered, 7 abstained; 0 abstentions with sources, 0 with figures; invariants hold; 0 expect-mismatches; all nine reasons exercised with frozen messages); the expired/non-approved/non-current catalog runs (every question stale_evidence, empty sources); the fail-closed exit 2 cases (malformed passage set, unknown source_id, missing file/catalog, --k 0, malformed/empty eval) with located JSON paths and empty stdout; contracts/validate_examples.py passing with contracts/ untouched; independent jsonschema validation of every payload against the dereferenced AskResponse (exactly the five keys, abstained status, empty sources and land_ids_to_choose, non-blank message <= 1200); a byte-for-byte comparison of all nine pinned messages plus digit/date/eligibility checks; its own out-of-corpus and false-premise probes (present/absent/different-instrument/location-only cases); the same-unit critical conflict (conflicting_evidence) versus different-units still-answering (no over-abstention); generator provenance (0 generator calls for invalid/no_evidence/false_premise/conflict; abstain/raise mapped; rejected drafts never emitted); determinism (two byte-identical --json runs under two PYTHONHASHSEED values and three in-process repeats); a stricter independent socket/DNS guard that still abstains and answers; content-silent diagnostics; and the unchanged generation (5 answers, 8 claims, 0 ungrounded, 1 no-evidence) and retrieval (hit@5 0.857, recall@5 0.857, MRR 0.857) baselines. Scope confirmed: contracts/, generation.py, retrieval.py, source_catalog.py, main.py, evaluate_generation.py, test_generation.py, knowledge/, requirements.txt, init.sh, and all client/shared code unmodified; /health the only route; fixtures synthetic/labelled with no real legal fact; no repo dependency (pytest ran from an out-of-repo venv, Python 3.9.6). Findings N1-N4 are non-blocking and carried forward: N1 (evidence wording over-narrow about which files were modified; corrected here), N2 (a structurally-plausible-but-semantically-invalid catalog can yield stale_evidence instead of a hard error; matches spec rule 6, fails safe, owner a later catalog-hardening slice), N3 (test_abstention.py:553 uses a real-looking statute id 7/2022; pure extractor literal, prefer an impossible id for fixture-policy consistency), N4 (substring containment in the presupposition check can under-abstain, e.g. ley inside leyenda; the prescribed lexical behaviour, to be measured in land_safety_evaluation).
