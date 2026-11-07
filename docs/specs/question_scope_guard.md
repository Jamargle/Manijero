# Feature Spec: `question_scope_guard`

## Source metadata

- **Feature:** `question_scope_guard` — Abstain on purpose for questions outside the approved coverage (aid amounts, individual cases, excluded topics) before retrieval can answer them (`backend`).
- **Status at planning:** `not_started`; no dependencies.
- **Source behavior (owner-approved goal, 2026-11-07):** `/ask` abstains deliberately for questions on the omissions listed in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md) "Exclusiones" (individual eligibility, aid amounts, late-filing penalties, individual notifications or case status, monitoring-control adaptations, reclamaciones and recursos, fuerza mayor, other campaigns) **before** retrieval or generation runs, instead of relying on retrieval or verification failing by accident.
- **Feature-list verification:** the two regressions in [known limitations](../progress/known-limitations.md) ("No deliberate question-scope check") are fixed and proven with `backend/scripts/evaluate_pac_answers.py` (`--active-campaign 2026 --as-of 2026-11-07 --k 5`) with no currently-correct reviewed case regressing; unit tests cover every omission category plus in-scope near-misses.
- **Feature-list note:** logic stays in the backend abstention layer; plain Spanish; no new legal facts; no new dependencies; must not over-block in-scope questions.

## Goal and boundaries

Add a small, reviewable, code-owned list of out-of-scope topic patterns, one entry per declared omission, and check every valid question against it before any retrieval, land clarification, or drafting. A match abstains with an existing pinned reason and message; no match leaves today's pipeline byte-for-byte unchanged.

**In scope**

- A pure, lexical, accent- and case-insensitive scope check over the question text.
- Wiring the check into `answer_or_abstain` and `answer_with_clarification` so both `/ask` and the offline evaluators see it.
- Unit tests per omission category, in-scope near-misses, and the reviewed case questions.
- Docs: known limitations, `PROGRESS.md`, measured results in `pac_coverage.md`, the backend README abstention section, and one constraint bullet.

**Non-goals**

- New abstention reasons, new copy, `contracts/` or client changes (the reasons and messages already exist).
- Semantic or model-based classification, or any change to retrieval ranking or generation.
- Merging the singular/plural retrieval trial. The guard covers two of its three side effects (`tema-no-cubierto` and the individual-notification boundary), but not the `plazo-modificacion-parcelas-2026` ranking break, so the trial stays separate and unmerged.
- New reviewed eval cases. The four draft cases for new passages stay out of scope; category coverage lives in unit tests because reviewed cases need Diego's review.
- Fixing the three known citation misses (`canal-sga-2026`, `fecha-modificacion-2026`, `distingue-fechas-2026`).
- Moving or changing the existing four-digit year check in `ask_api._answer`.

## Job story

When I ask something Manijero's reviewed documents do not cover, such as how much aid I will get or how to file a reclamación, I want a clear "I can't answer this, ask your office" reply, so a nearby but unrelated legal passage is never presented as my answer.

## Acceptance scenarios

### Known regressions abstain

Given the reviewed corpus, campaign `2026`, and as-of `2026-11-07`, when the PAC evaluation runs, then `tema-no-cubierto` ("¿Qué importe de ayuda me corresponde por hectárea?") and `reclamacion-fuera-de-alcance` ("¿Cuál es el plazo para presentar una reclamación?") are `abstained` with no sources, and `unexpected_answers` is `0`.

### No reviewed case regresses

Given the baseline report recorded before the change, when the evaluation reruns after it, then every case that matched its expected state, expected source, or critical facts at baseline still matches. Expected-state agreement rises from 12/14 to 14/14, and source citation and critical-fact counts are no lower than at baseline (8 and 9 if the recorded baseline matches the documented one).

### Each omission category abstains before retrieval

Given any question matching an omission entry (at least two phrasings per category, listed in the appendix), when it reaches `answer_or_abstain` or `answer_with_clarification`, then the result is an `Abstention` and the retriever's `search` is never called, so no land clarification is offered either. The reason is:
- `unsafe_request` for individual eligibility, aid amounts, and individual notifications or case status;
- `no_evidence` for the other omissions (other campaigns already use `no_evidence` through the year check).

The abstention carries one issue with code `out_of_scope_question` whose detail is the omission label, never question text.

### In-scope and near-miss questions are untouched

Given each `expected_status: "answered"` question in `knowledge/pac_answer_eval.json`, and the near-misses listed in the appendix (for example "¿Hasta cuándo puedo modificar mi solicitud?", "¿Las notificaciones se hacen por medios electrónicos?", "¿Puede la Administración corregir un error material en un acto?", "¿Qué es un recinto SIGPAC?", and the synthetic fixture "¿Cuál es el importe ficticio de ejemplo?"), when the scope check runs, then it returns no match and the pipeline result is unchanged.

### The list is tied to the declared omissions

Given the omission list in `knowledge/pac_answer_eval.json` `coverage.omissions`, when tests run, then every declared omission has exactly one guard entry with at least one pattern, and every guard entry names a declared omission. Adding or removing an omission without updating the guard fails a test.

### Order and invariants are preserved

Given a stale corpus, a blank question, or a question over the length bound, then the existing `stale_evidence` / `invalid_question` outcome still wins over the scope check. Every guard abstention is a standard abstention payload (no source, figure, or date) built by `to_abstention_response`, and no question text reaches logs, traces, or metrics beyond what is recorded today.

## Technical approach

- New module `backend/app/question_scope.py` (standard library only). It holds an ordered tuple `OUT_OF_SCOPE_TOPICS` of frozen `ScopeTopic(omission, reason, patterns)` entries, where `omission` is the exact `coverage.omissions` label and `reason` is `unsafe_request` or `no_evidence`. It also exposes `out_of_scope_topic(question) -> Optional[ScopeTopic]`.
- Matching runs on `app.generation.normalize_text(question)`, with every character that is not a letter or digit replaced by a space, so patterns are written without accents or `¿?`. Patterns are word-bounded regexes for personal or topic phrasings. They are deliberately **not** bare words such as `importe`, `cuanto`, `puedo`, `mi solicitud`, `notificacion`, `plazo`, `corregir`, or `campana`, which appear in in-scope or fixture questions.
- `backend/app/abstention.py`: add `scope_abstention(question) -> Optional[Abstention]`. It returns `None` for a non-string or blank question, so the invalid-question path stays in charge. In `answer_or_abstain`, call it after the stale-corpus, blank, and length checks and before `corpus.search`.
- `backend/app/clarification.py`: in `answer_with_clarification`, when `corpus` is a `Retriever`, return `scope_abstention(question)` if it is not `None` before calling `clarify_land_scope`.
- No change to `ABSTENTION_REASONS`, `ABSTENTION_MESSAGES`, `health_metrics`, `ask_api`, `contracts/`, or the clients. Trace and metrics record the existing reason codes through the current `ask_api` path.
- **Reuse decision (post-merge `b0caeba`):** neither new module is reused at runtime.
  - `app/procedure_map.py` and `knowledge/procedure_map.json` are a `proposed`, unreviewed taxonomy that is "not an answer source", and their coverage states are stale for the guard's purpose: `sigpac` and `notificaciones-y-rectificaciones` are `uncovered`, yet reviewed SIGPAC and notification passages are now answerable. Blocking on them would over-block in-scope questions.
  - `app/source_validity.py` is an offline review of source validity, not question scope.
  - The guard anchors to the reviewed `coverage.omissions` list instead.

## Expected file changes

| Path | Change |
|---|---|
| `backend/app/question_scope.py` | New: topic table and matcher. |
| `backend/app/abstention.py` | `scope_abstention`; pre-retrieval call in `answer_or_abstain`; docstring rule. |
| `backend/app/clarification.py` | Scope check before `clarify_land_scope`. |
| `backend/tests/test_question_scope.py` | New: category, near-miss, reviewed-question, omission-tie, ordering, and `/ask` tests. |
| `backend/tests/test_*.py` using `"¿Qué ayuda de pesca me corresponde?"` | Update only if a test pins its old reason or copy (status stays `abstained`). |
| `backend/README.md` | Short "Question-scope pre-check" paragraph in "Offline abstention decisions" (at most 12 lines). |
| `docs/constraints/answers-and-knowledge.md` | One MUST bullet under "Abstention". |
| `knowledge/pac_coverage.md` | Measured-result lines only (matrix rows, totals, the reclamación bullet); topics, exclusions, and approvals untouched. |
| `docs/progress/known-limitations.md`, `PROGRESS.md` | Narrow the regression item and update the eval numbers. |

## Visual design impact

None. There is no new copy; existing pinned messages are reused and clients render abstentions unchanged.

## Durable documentation impact

- `docs/constraints/answers-and-knowledge.md`: **update**. Add: "Questions matching a declared `pac_coverage.md` omission MUST abstain before retrieval through the code-owned list in `app/question_scope.py`, kept one-to-one with `coverage.omissions`."
- `backend/README.md`: **update** (see the file table above).
- `knowledge/pac_coverage.md`: **update** measured results only.
- `docs/progress/known-limitations.md` and `PROGRESS.md`: **update**. Remove both regressions, keep the trial note (it is still unmerged), and state that the guard is lexical: unlisted paraphrases can still reach retrieval.
- `ARCHITECTURE.md`, `AGENTS.md`, `CONSTRAINTS.md` index, `DESIGN.md`, `contracts/`: **not needed**. There are no module, contract, copy, or index-section changes; "Abstention" is already indexed.

## Focused verification

The published block runs the guard tests, the neighbours it touches, and the reviewed evaluation. The evaluation prints its JSON report into the focused log for evidence; the guard-specific assertions live in `test_question_scope.py`, so the PAC metrics themselves stay report-only. Before handoff, also run `./scripts/init.sh --fast` (it covers the whole backend suite and the offline evaluators).

<!-- verify:start -->
```sh
./scripts/init.sh --backend-tests tests/test_question_scope.py tests/test_abstention.py tests/test_clarification.py tests/test_pac_answer_eval.py tests/test_land_safety_eval.py tests/test_health_metrics.py tests/test_answer_trace.py tests/test_answer_inspection.py tests/test_hybrid_retrieval.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-11-07 --k 5
```
<!-- verify:end -->

`./scripts/init.sh --feature question_scope_guard` discovers this block automatically (`feature_commands` in `scripts/init.sh`); nothing in `init.sh` needs wiring.

## Appendix

See [`question_scope_guard.appendix.md`](question_scope_guard.appendix.md) for research, the pattern starting list, plan, evidence, and the validator checklist.
