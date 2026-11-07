# Appendix: `question_scope_guard`

Contract: [`question_scope_guard.md`](question_scope_guard.md).

## Repository research

Inspected after main was merged in (`b0caeba`):

- `backend/app/abstention.py`: `answer_or_abstain` order is stale corpus, blank, length, `corpus.search`, presupposition, unit conflict, generation. There is no scope check today. The reasons and copy are pinned and digit-free.
- `backend/app/clarification.py`: `answer_with_clarification` runs `clarify_land_scope`, which calls `corpus.search`, before `answer_or_abstain`. A guard placed only in `answer_or_abstain` would still let land clarification run first.
- `backend/app/ask_api.py` `_answer`: a four-digit year that differs from the active campaign abstains `no_evidence` before the corpus loads (`campana-no-soportada` relies on it). This is the precedent for mapping "other campaigns" to `no_evidence`.
- `backend/app/generation.py`: `normalize_text` lowercases, strips accents, and keeps punctuation. `ELIGIBILITY_PHRASES` only checks **drafts**, not questions.
- `backend/app/health_metrics.py`, `backend/tests/test_health_metrics.py`: the reason label set is pinned. Reusing existing reasons avoids changing it.
- `backend/scripts/evaluate_pac_answers.py`, `backend/app/answer_eval.py`: report fields used here are `expected_state_agreement`, `unexpected_answers`, `source_citation_agreement`, `critical_fact_matches`, and `case_rows`. Exit is `0` regardless of the metrics.
- `knowledge/pac_answer_eval.json`: 14 cases. `coverage.omissions` holds the 8 labels the guard is tied to.
- `knowledge/pac_coverage.md`: "Exclusiones" and the matrix. The `tema-fuera-de-alcance` row still says it abstains, which is stale since the 2026-11-07 extractive change.
- `knowledge/passages.json`: 7 passages. In-scope vocabulary includes `notificaciones … medios electrónicos`, `rectificar … errores materiales`, recinto SIGPAC, `plazo`, `modificar`, `parcelas`.
- `backend/tests/fixtures/abstention/eval_questions.jsonl`, `backend/tests/fixtures/land_safety/cases.json`: these fixture questions must keep their recorded outcomes: "¿Cuál es el importe ficticio de ejemplo?" → answered; "¿Cuánto dura el plazo ficticio de prueba?" → `conflicting_evidence`; "¿Cuánto cuesta matricular un tractor viejo?" → `no_evidence`; "¿Puedo usar el riego de apoyo en la parcela de muestra?" → clarification/answered; "campaña ficticia" → answered.
- `backend/tests/test_answer_trace.py`, `test_answer_inspection.py`, `test_hybrid_retrieval.py`: these use "¿Qué ayuda de pesca me corresponde?" as an abstaining question, and assert only `abstained`, a non-empty reason, on/off byte equality, and that the embedder is not called. All of that stays true when the guard abstains before retrieval.
- `backend/app/procedure_map.py`, `knowledge/procedure_map.json`: a `proposed` taxonomy, not an answer source, with stale `uncovered` states. Not reused (decision in the contract).
- `backend/app/source_validity.py`: offline source-validity review. Not related to question scope.
- `scripts/init.sh` `feature_commands` / `run_feature`: runs the spec's verify block through `bash -euo pipefail`. `--backend-tests` takes paths relative to `backend/`.
- `docs/progress/known-limitations.md`: the regression item and the singular/plural trial evidence.
- Not inspected: the clients (unchanged), `contracts/openapi.yaml` (unchanged wire shape).

**Baseline:** the planner had no shell, so it did not run the evaluation. The documented baseline (known limitations, 2026-11-07) is 12/14 expected states, 11/11 expected answers answered, `source_citation_agreement` 8, `critical_fact_matches` 9, 1/3 expected abstentions, and `unexpected_answers` 2 (`tema-no-cubierto` cites `pasaje-definicion-recinto-sigpac`; `reclamacion-fuera-de-alcance` cites `pasaje-plazo-modificacion-2026-andalucia`). Task 1 confirms it.

## Pattern starting list (normalized; the implementer may tune it, the tests decide)

| Omission (`coverage.omissions`) | Reason | Starting patterns | Must match (tests) |
|---|---|---|---|
| `importes de ayudas` | `unsafe_request` | `importe(s)? de (la \|las \|mi )?ayudas?`, `importe por hectarea`, `cuantia de (la )?ayuda`, `cuanto (dinero )?(voy a \|me van a \|se )?(cobr\|pag\|recib)\w*`, `euros por hectarea` | "¿Qué importe de ayuda me corresponde por hectárea?", "¿Cuánto voy a cobrar de la PAC?", "¿Cuánto se paga por hectárea de olivar?" |
| `elegibilidad individual` | `unsafe_request` | `tengo derecho`, `(cumplo\|reuno) (los )?requisitos`, `me corresponde\w* (la \|una \|alguna )?ayuda`, `ayuda\w* .* me corresponde`, `puedo cobrar`, `soy (agricultor activo\|beneficiari)` | "¿Tengo derecho a la ayuda?", "¿Cumplo los requisitos para la ayuda al olivar?", "¿Qué ayuda de pesca me corresponde?" |
| `notificaciones individuales` | `unsafe_request` | `mi expediente`, `(estado\|situacion) de mi`, `me (han\|ha) (enviado\|notificado\|pagado\|ingresado\|concedido\|denegado\|resuelto\|llegado)`, `ya me (han\|ha)` | "¿Me han enviado ya la notificación de mi expediente de la PAC?", "¿Cómo va mi expediente?", "¿Ya me han pagado la ayuda?" |
| `reclamaciones y recursos` | `no_evidence` | `reclamacion\w*`, `reclamar`, `recurso (de\|contra\|contencioso)`, `recurr\w*`, `impugn\w*`, `interponer` | "¿Cuál es el plazo para presentar una reclamación?", "¿Cómo recurro la resolución?", "¿Puedo presentar un recurso de alzada?" |
| `penalizaciones por mora` | `no_evidence` | `penaliz\w*`, `sancion\w*`, `recargo`, `fuera de plazo`, `presentacion tardia`, `(presento\|entrego) .* tarde` | "¿Qué penalización tengo si presento tarde?", "¿Qué pasa si presento la solicitud fuera de plazo?" |
| `fuerza mayor` | `no_evidence` | `fuerza mayor`, `circunstancias excepcionales` | "¿Qué hago si no pude presentar por fuerza mayor?", "¿Cuentan las circunstancias excepcionales?" |
| `adaptaciones por controles de monitorizacion` | `no_evidence` | `monitoriz\w*`, `control(es)? por satelite`, `satelite` | "¿Cómo adapto la solicitud tras los controles de monitorización?", "¿Qué pasa si el satélite detecta otro cultivo?" |
| `otras campañas` | `no_evidence` | `campana (pasada\|anterior\|proxima\|siguiente\|que viene)`, `ano (pasado\|que viene)`, `proximo ano` | "¿Cuál era el plazo de la campaña pasada?", "¿Cambia algo para la próxima campaña?" |

The `omission` field must equal the JSON label exactly, including accents (for example `adaptaciones por controles de monitorización`, `otras campañas`).

**Near-misses that must NOT match:** every `answered` question in `knowledge/pac_answer_eval.json`, plus:
- "¿Hasta cuándo puedo modificar mi solicitud?"
- "¿Las notificaciones se hacen por medios electrónicos?"
- "¿Puede la Administración corregir un error material en un acto?"
- "¿Qué es un recinto SIGPAC?"
- "¿Qué entidades reconocidas puedo usar?"
- "¿Cuál es el importe ficticio de ejemplo?"
- "¿Cuánto dura el plazo ficticio de prueba?"
- "¿Cuánto cuesta matricular un tractor viejo?"
- "¿Puedo usar el riego de apoyo en la parcela de muestra?"
- "¿Cómo se presenta la solicitud anual de la campaña ficticia?"
- "¿Qué recursos naturales protege la norma?" (`recurso` alone must not match)

## Implementation plan and tasks

1. Run the evaluation command from the contract on the unchanged tree. Record the summary counts and the per-case `expected_state_match` / `source_match` / `critical_facts_match` in Feature evidence. If they differ from the documented baseline, use the measured numbers and say so.
2. Add `backend/app/question_scope.py` with `ScopeTopic`, `OUT_OF_SCOPE_TOPICS`, the normalization helper, and `out_of_scope_topic`.
3. Add `scope_abstention` to `abstention.py`, call it before `corpus.search` in `answer_or_abstain`, and add a module-docstring rule line.
4. Add the `Retriever`-only pre-check in `answer_with_clarification`.
5. Write `backend/tests/test_question_scope.py` (tests listed below).
6. Run the focused block. If a neighbour test pins the old reason or copy for "¿Qué ayuda de pesca me corresponde?", update only that assertion and record why.
7. Rerun the evaluation. Diff it against the task 1 record and confirm the contract's no-regression scenario.
8. Update `backend/README.md`, `docs/constraints/answers-and-knowledge.md`, the measured lines of `knowledge/pac_coverage.md`, `docs/progress/known-limitations.md` (digest numbers and the narrowed item), and the `PROGRESS.md` digest lines.
9. Run `./scripts/init.sh --fast`. Record one line per command in Feature evidence and fill in `## Handoff`.

## Verification plan

Tests in `backend/tests/test_question_scope.py`:
- `test_each_omission_category_matches_its_phrasings`: parametrized over the "Must match" column; checks the omission and the reason.
- `test_near_misses_and_reviewed_answered_questions_do_not_match`: the reviewed `answered` questions are read from the JSON file.
- `test_guard_is_one_to_one_with_declared_omissions`
- `test_patterns_are_accent_case_and_punctuation_insensitive`: for example "QUÉ IMPORTE DE AYUDA…" and the version without accents.
- `test_scope_abstention_never_calls_search`: a fake retriever whose `search` fails the test, through both `answer_or_abstain` and `answer_with_clarification` with two mixed `all_active` lands.
- `test_stale_corpus_and_invalid_question_win_over_scope`
- `test_guard_issue_carries_omission_label_not_question_text`
- `test_reviewed_regressions_abstain_through_ask`: `TestClient` over the real `knowledge/` files, campaign `2026`, as-of `2026-11-07`. Both regression questions return `abstained` with `sources == []`. This asserts guard behaviour, not PAC quality thresholds, which stay report-only per `pac_coverage.md`.
- `test_guard_module_is_standard_library_only`

Then the contract's focused block, and `./scripts/init.sh --fast` as the full no-device gate.

## Evidence to capture

- The before and after evaluation commands, each with one summary line (states, answered, source, critical, abstentions, unexpected), plus the list of per-case changes. Expected: only `tema-no-cubierto` and `reclamacion-fuera-de-alcance` change, both to `abstained`.
- The focused block result and the `--fast` result, one line each.
- Any neighbour test assertion you changed, with the reason.
- The final pattern table, only if it differs from the starting list.

## Feature evidence

- Baseline, unchanged tree (`backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py ... --k 5`): matches the documented baseline. 12/14 states, 11/11 answered, source 8, critical 9, unexpected 2 (`tema-no-cubierto`, `reclamacion-fuera-de-alcance` answered). Source misses: `canal-sga-2026`, `fecha-modificacion-2026`, `distingue-fechas-2026`; critical misses: the latter two.
- After: 14/14 states, 11/11 answered, source 8, critical 9, unexpected 0. Only the two regression cases changed, both to `abstained` with no sources; every other per-case flag is identical.
- `./scripts/init.sh --feature question_scope_guard`: passed (546 backend tests, evaluation above).
- Pattern change from the starting list: added `(pasada|anterior|proxima|siguiente) campana` to `otras campañas` (the list only had the reversed order); `requisitos` allows `cumplo con`, `soy ...` allows word tails. No neighbour test assertion needed changing.

## Validator checklist

- [ ] Rerun the evaluation. 14/14 expected states and `unexpected_answers` 0. No baseline-passing case lost its state, source, or critical-fact match.
- [ ] `OUT_OF_SCOPE_TOPICS` is one-to-one with `coverage.omissions`. No bare over-broad word patterns. Every near-miss passes.
- [ ] Guard abstentions happen before any `search` call, including on the clarification path. Stale-corpus and invalid-question checks still win.
- [ ] No new reason, message, dependency, contract, or client change. Payloads are standard abstentions. No question text in issues, logs, or traces.
- [ ] `procedure_map` and `source_validity` are not imported by the guard.
- [ ] The singular/plural trial is not merged. The four draft eval cases are not added.
- [ ] Docs are updated as the contract lists, and `pac_coverage.md` changes only its measured-result lines.
- [ ] `./scripts/init.sh --feature question_scope_guard` and `./scripts/init.sh --fast` pass.
