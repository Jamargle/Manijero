# `pac_evidence_expansion` Appendix

## Repository research

- `PROGRESS.md` limits the corpus to three procedural topics and states that the current six-case evaluation has known citation and critical-fact misses.
- `backend_answer_evaluation` owns the deterministic report-only evaluator and canonical cases.
- `backend_citation_hardening` owns response-local citation numbering; `backend_pac_corpus` owns approved source passages and coverage.

## Implementation plan and tasks

1. Capture the baseline case-level report and enumerate every known mismatch before edits.
2. Build a topic/boundary coverage matrix from `knowledge/pac_coverage.md`; author cases only for approved passages and expected abstention/clarification boundaries.
3. Review each case and critical fact against the cited official passage as project author; label review role honestly.
4. Fix source, code, or evaluator errors at their owning boundary; preserve unresolved cases in the final report.
5. Run twice with pinned date/campaign/retrieval settings and update coverage/evidence notes with exact counts and limitations.

## Verification plan

- Run evaluator tests and canonical evaluator twice with the same flags; compare complete output.
- Validate every case source/passage against the canonical catalog and passages.
- Confirm no new legal topic, unsupported fact, user-derived data, metric threshold, or independent-review claim appears.

## Evidence to capture

- Baseline and final case-level outputs, current case/topic counts, each prior miss and resolution, fixed inputs, exact author-review method, residual gaps.

## Feature evidence

### Fixed inputs and environment

- Worktree: `/Users/Jose1/AndroidStudioProjects/Manijero-worktrees/pac_evidence_expansion`; base commit before this change: `6e0921f`.
- Python: `backend/.venv/bin/python`; offline evaluator, no network, no model provider, no LLM judge.
- Identical pinned inputs for every run below: `--active-campaign 2026 --as-of 2026-10-26 --k 5`.
- Canonical artifacts: `knowledge/source_catalog.json`, `knowledge/passages.json`, `knowledge/pac_answer_eval.json`.

### Baseline before the change (six cases)

The baseline was re-run from an untouched detached worktree pinned at `6e0921f` (old `pac-answer-eval-v1` artifact, old evaluator and generation code), using this worktree's venv, so the numbers below are reproduced rather than recalled:

```sh
backend/.venv/bin/python <baseline-worktree>/backend/scripts/evaluate_pac_answers.py \
  --catalog <baseline-worktree>/knowledge/source_catalog.json \
  --passages <baseline-worktree>/knowledge/passages.json \
  --cases <baseline-worktree>/knowledge/pac_answer_eval.json \
  --active-campaign 2026 --as-of 2026-10-26 --k 5
```

Exit status 0. Raw report:

```json
{"active_campaign":"2026","as_of":"2026-10-26","case_rows":[{"actual_status":"answered","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"canal-sga-2026","land_ids_to_choose":[],"passage_match":false,"source_match":false},{"actual_status":"answered","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"fecha-presentacion-2026","land_ids_to_choose":[],"passage_match":true,"source_match":true},{"actual_status":"answered","clarification_ids_match":true,"critical_facts_match":false,"expected_state_match":true,"expected_status":"answered","id":"fecha-modificacion-2026","land_ids_to_choose":[],"passage_match":false,"source_match":false},{"actual_status":"answered","clarification_ids_match":true,"critical_facts_match":false,"expected_state_match":true,"expected_status":"answered","id":"distingue-fechas-2026","land_ids_to_choose":[],"passage_match":false,"source_match":false},{"actual_status":"abstained","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"abstained","id":"campana-no-soportada","land_ids_to_choose":[],"passage_match":true,"source_match":true},{"actual_status":"abstained","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"abstained","id":"tema-no-cubierto","land_ids_to_choose":[],"passage_match":true,"source_match":true}],"cases":6,"clarification_outcomes":0,"critical_fact_matches":2,"expected_answer_coverage":4,"expected_state_agreement":6,"k":5,"quality_metrics_are_report_only":true,"schema_version":"pac-answer-eval-v1","source_citation_agreement":1,"unexpected_answers":0}
```

| Baseline case | Expected | Actual | Source/passage | Critical facts |
|---|---|---|---|---|
| `canal-sga-2026` | answered | answered | mismatch (`res_20260121` / canal passage expected) | match |
| `fecha-presentacion-2026` | answered | answered | match | match |
| `fecha-modificacion-2026` | answered | answered | mismatch (`rd_537_2026` / modification passage expected) | mismatch (`15 de junio`) |
| `distingue-fechas-2026` | answered | answered | mismatch (`dl_1_2026` / presentation passage expected) | mismatch (`15 de mayo de 2026`) |
| `campana-no-soportada` | abstained | abstained | n/a | match |
| `tema-no-cubierto` | abstained | abstained | n/a | match |

Baseline aggregates: `cases` 6, `expected_state_agreement` 6, `expected_answer_coverage` 4 of 4 expected-answer cases, `unexpected_answers` 0, `source_citation_agreement` 1 of 4 answered cases, `critical_fact_matches` 2 of 4 answered cases, `clarification_outcomes` 0 of 0. The three known misses were `canal-sga-2026`, `fecha-modificacion-2026`, and `distingue-fechas-2026`; none was removed from the case set. The v1 report exposed only match booleans; the v2 report below adds the actual/missing source and passage IDs, which is why the final table can name both sides.

### What changed

- `knowledge/pac_answer_eval.json` + `knowledge/pac_answer_eval.schema.json`: new `pac-answer-eval-v2` artifact with 14 cases. It declares `coverage` (3 topic areas, 5 boundary areas, 8 omissions, `reviewed_against: knowledge/pac_coverage.md`), a per-case `area`, and per-case `review` metadata (`reviewed_by: Diego`, `reviewed_on: 2026-10-27`, `role: author_only`). No new legal topic or source was added.
- Case counts: 14 total = 9 topic cases (`canal-presentacion` 3, `plazo-presentacion` 2, `plazo-modificacion` 4) + 5 boundary cases (`distincion-fechas`, `campana-fuera-de-alcance`, `tema-fuera-de-alcance`, `reclamacion-fuera-de-alcance`, `alcance-terrenos`, one each).
- `backend/app/answer_eval.py`, `backend/scripts/evaluate_pac_answers.py`: load/validate the v2 artifact and report denominators (`answered_cases`, `abstention_cases`, `clarification_cases`), area counts, coverage omissions, review roles, and per-row missing/actual source and passage IDs, missing critical facts, and unexpected land IDs. Outcome mismatches remain report-only.
- `backend/app/generation.py`: fixed a confirmed generation/verifier defect. The extractive generator joined claims with a space; a reviewed excerpt without terminal punctuation merged with the next claim, so the second passage's figure/critical-literal rules were applied to the first claim. The generator now emits one claim per line and `split_sentences` treats a line break as a claim boundary (`_split_line` helper). The assembled user-facing answer still joins verified claims with a space.
- Tests: `backend/tests/test_pac_answer_eval.py` covers v2 loading/schema rejection, coverage declaration, author-only report metadata, denominators, missing-reference detail, strict status/answer rules, and the CLI override; `backend/tests/test_generation.py` asserts the line-break claim boundary and that an excerpt without a final period does not merge with the next claim.

### Confirmed defect fixed at its owning boundary

Before the fix, the new `canal-excepcion-persona-fisica-2026` case abstained with `critical_not_literal` plus `answer_too_long`: the national-exception excerpt has no terminal period, so joining it with the filing-deadline claim produced one over-long sentence that borrowed the deadline claim's critical rules. After the generation fix the case answers with `rd_1048_2022` / `pasaje-canal-presentacion-excepcion-nacional` and passes every check. The two new regression tests pin the boundary and one-claim-per-line behavior so a future join change is caught.

### Final after the change (14 cases)

```sh
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --active-campaign 2026 --as-of 2026-10-26 --k 5
```

Exit status 0. Raw report (run 1 of 2):

```json
{"abstention_cases":3,"active_campaign":"2026","answered_cases":11,"as_of":"2026-10-26","case_rows":[{"actual_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"actual_source_ids":["dl_1_2026"],"actual_status":"answered","area":"canal-presentacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"canal-sga-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":["pasaje-canal-presentacion-andalucia"],"missing_expected_source_ids":["res_20260121"],"passage_match":false,"source_match":false,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-canal-presentacion-andalucia"],"actual_source_ids":["res_20260121"],"actual_status":"answered","area":"canal-presentacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"canal-sga-entidades-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-canal-presentacion-excepcion-nacional"],"actual_source_ids":["rd_1048_2022"],"actual_status":"answered","area":"canal-presentacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"canal-excepcion-persona-fisica-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"actual_source_ids":["dl_1_2026"],"actual_status":"answered","area":"plazo-presentacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"fecha-presentacion-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"actual_source_ids":["dl_1_2026"],"actual_status":"answered","area":"plazo-presentacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"plazo-presentacion-variante-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"actual_source_ids":["dl_1_2026"],"actual_status":"answered","area":"alcance-terrenos","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"alcance-terrenos-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"actual_source_ids":["dl_1_2026"],"actual_status":"answered","area":"plazo-modificacion","clarification_ids_match":true,"critical_facts_match":false,"expected_state_match":true,"expected_status":"answered","id":"fecha-modificacion-2026","land_ids_to_choose":[],"missing_critical_facts":["15 de junio"],"missing_expected_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"missing_expected_source_ids":["rd_537_2026"],"passage_match":false,"source_match":false,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"actual_source_ids":["rd_537_2026"],"actual_status":"answered","area":"plazo-modificacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"plazo-modificacion-parcelas-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"actual_source_ids":["rd_537_2026"],"actual_status":"answered","area":"plazo-modificacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"plazo-modificacion-confirma-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"actual_source_ids":["rd_537_2026"],"actual_status":"answered","area":"plazo-modificacion","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"answered","id":"plazo-modificacion-inclusive-2026","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"actual_source_ids":["rd_537_2026"],"actual_status":"answered","area":"distincion-fechas","clarification_ids_match":true,"critical_facts_match":false,"expected_state_match":true,"expected_status":"answered","id":"distingue-fechas-2026","land_ids_to_choose":[],"missing_critical_facts":["15 de mayo de 2026"],"missing_expected_passage_ids":["pasaje-plazo-presentacion-2026-andalucia"],"missing_expected_source_ids":["dl_1_2026"],"passage_match":false,"source_match":false,"unexpected_land_ids":[]},{"actual_passage_ids":[],"actual_source_ids":[],"actual_status":"abstained","area":"campana-fuera-de-alcance","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"abstained","id":"campana-no-soportada","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":[],"actual_source_ids":[],"actual_status":"abstained","area":"tema-fuera-de-alcance","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":true,"expected_status":"abstained","id":"tema-no-cubierto","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]},{"actual_passage_ids":["pasaje-plazo-modificacion-2026-andalucia"],"actual_source_ids":["rd_537_2026"],"actual_status":"answered","area":"reclamacion-fuera-de-alcance","clarification_ids_match":true,"critical_facts_match":true,"expected_state_match":false,"expected_status":"abstained","id":"reclamacion-fuera-de-alcance","land_ids_to_choose":[],"missing_critical_facts":[],"missing_expected_passage_ids":[],"missing_expected_source_ids":[],"passage_match":true,"source_match":true,"unexpected_land_ids":[]}],"cases":14,"clarification_cases":0,"clarification_outcomes":0,"coverage":{"boundaries":{"alcance-terrenos":1,"campana-fuera-de-alcance":1,"distincion-fechas":1,"reclamacion-fuera-de-alcance":1,"tema-fuera-de-alcance":1},"cases_by_area":{"alcance-terrenos":1,"campana-fuera-de-alcance":1,"canal-presentacion":3,"distincion-fechas":1,"plazo-modificacion":4,"plazo-presentacion":2,"reclamacion-fuera-de-alcance":1,"tema-fuera-de-alcance":1},"omissions":["elegibilidad individual","importes de ayudas","penalizaciones por mora","notificaciones individuales","adaptaciones por controles de monitorización","reclamaciones y recursos","fuerza mayor","otras campañas"],"topics":{"canal-presentacion":3,"plazo-modificacion":4,"plazo-presentacion":2}},"critical_fact_matches":9,"expected_answer_coverage":11,"expected_state_agreement":13,"k":5,"quality_metrics_are_report_only":true,"review":{"independent_legal_review":false,"roles":["author_only"]},"schema_version":"pac-answer-eval-v2","source_citation_agreement":8,"unexpected_answers":1}
```

| Final case | Area | Expected | Actual | Source | Passage | Critical facts |
|---|---|---|---|---|---|---|
| `canal-sga-2026` | canal-presentacion | answered | answered | mismatch (`dl_1_2026`; expected `res_20260121`) | mismatch (presentation deadline; expected canal) | match |
| `canal-sga-entidades-2026` | canal-presentacion | answered | answered | match (`res_20260121`) | match | match |
| `canal-excepcion-persona-fisica-2026` | canal-presentacion | answered | answered | match (`rd_1048_2022`) | match | match |
| `fecha-presentacion-2026` | plazo-presentacion | answered | answered | match (`dl_1_2026`) | match | match |
| `plazo-presentacion-variante-2026` | plazo-presentacion | answered | answered | match (`dl_1_2026`) | match | match |
| `alcance-terrenos-2026` | alcance-terrenos | answered | answered | match (`dl_1_2026`) | match | match |
| `fecha-modificacion-2026` | plazo-modificacion | answered | answered | mismatch (`dl_1_2026`; expected `rd_537_2026`) | mismatch (presentation deadline; expected modification) | mismatch (`15 de junio`) |
| `plazo-modificacion-parcelas-2026` | plazo-modificacion | answered | answered | match (`rd_537_2026`) | match | match |
| `plazo-modificacion-confirma-2026` | plazo-modificacion | answered | answered | match (`rd_537_2026`) | match | match |
| `plazo-modificacion-inclusive-2026` | plazo-modificacion | answered | answered | match (`rd_537_2026`) | match | match |
| `distingue-fechas-2026` | distincion-fechas | answered | answered | mismatch (`rd_537_2026`; expected `dl_1_2026`) | mismatch (modification deadline; expected presentation) | mismatch (`15 de mayo de 2026`) |
| `campana-no-soportada` | campana-fuera-de-alcance | abstained | abstained | n/a | n/a | match |
| `tema-no-cubierto` | tema-fuera-de-alcance | abstained | abstained | n/a | n/a | match |
| `reclamacion-fuera-de-alcance` | reclamacion-fuera-de-alcance | abstained | **answered** | `rd_537_2026` | modification deadline | n/a (unexpected answer) |

Final aggregates: `schema_version` `pac-answer-eval-v2`, `cases` 14, `answered_cases` 11, `abstention_cases` 3, `clarification_cases` 0, `expected_state_agreement` 13 of 14, `expected_answer_coverage` 11 of 11, `unexpected_answers` 1, `source_citation_agreement` 8 of 11 answered cases, `critical_fact_matches` 9 of 11 answered cases, `clarification_outcomes` 0 of 0, `review.roles` `["author_only"]`, `review.independent_legal_review` false, `quality_metrics_are_report_only` true.

### Each prior miss and its resolution

| Prior miss | Owning boundary found | Resolution / retained evidence |
|---|---|---|
| `canal-sga-2026` source + passage | Retrieval ranking. The canal excerpt shares no exact tokens with the question (`solicitud`/`solicitudes`, `presento`/`presentarán`), so BM25 ranks the presentation-deadline passage first. Not a safe in-scope defect. | **Retained as a documented gap** and kept in the case set (`test_known_misses_remain_in_the_case_set`). Two new canal cases isolate the behavior: `canal-sga-entidades-2026` matches the canal passage, and `canal-excepcion-persona-fisica-2026` passes after the generation fix. |
| `fecha-modificacion-2026` source + passage + critical fact | Retrieval ranking plus the 1200-character answer budget. The modification passage ranks behind the longer presentation-deadline passage, and the budget keeps only the first claim, dropping `15 de junio`. | **Retained as a documented gap** and kept in the case set. Three additional modification cases (`plazo-modificacion-parcelas-2026`, `plazo-modificacion-confirma-2026`, `plazo-modificacion-inclusive-2026`) confirm the passage and literal match when it is retrieved first. |
| `distingue-fechas-2026` source + passage + critical fact | Boundary/false-premise question. The question denies the presentation date; retrieval ranks the modification passage first and the answer never corrects the premise or states `15 de mayo de 2026`. | **Retained as a documented gap** and re-declared as the `distincion-fechas` boundary case; it remains in the report as a visible mismatch. |

No miss was deleted, hidden, or converted into a pass by editing its expectation.

### Newly measured gap (not a regression from this change)

`reclamacion-fuera-de-alcance` expects abstention for an out-of-scope reclamación, but lexical overlap on `plazo` returns the modification deadline. The report counts it as `unexpected_answers` 1 and never as a supported success. It is retained report-only: fixing relevance for out-of-scope reclamaciones would require retrieval work outside this evidence-expansion scope.

### Determinism

The canonical command was run twice with the same files and flags. Both exited 0; `cmp` on stdout and on stderr reported no differences:

```sh
cmp run1.json run2.json   # exit 0, byte-identical
cmp run1.err run2.err     # exit 0, byte-identical
```

### Verification runs

| Command | Exit | Result |
|---|---|---|
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature pac_evidence_expansion` | 0 | 20 focused tests passed; canonical evaluator emitted the 14-case final report |
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` | 0 | `:shared:jvmTest` plus contract examples, 644 backend tests, source catalog, retrieval, generation, abstention, clarification, and land-safety checks; all 9 offline checks passed |
| Baseline command in the `6e0921f` worktree | 0 | six-case `pac-answer-eval-v1` report above |
| Two canonical final runs plus `cmp` | 0 | byte-identical stdout and stderr |

`./scripts/init.sh --verify` was not run: this feature changes only Python backend/evaluator code, canonical JSON knowledge artifacts, tests, and docs. It does not touch the Android/Desktop UI, packaging, or shared Kotlin behavior, and the fast tier already runs `:shared:jvmTest`, the backend suite, and every offline evaluator.

### Author review method and limits

- Each case was written and checked against the literal approved text in `knowledge/passages.json` and the declared coverage in `knowledge/pac_coverage.md`; expectations are the passage's own status, source ID, passage ID, and a literal critical phrase. No new legal fact or source was introduced.
- Review is recorded per case as `reviewed_by: Diego`, `reviewed_on: 2026-10-27`, `role: author_only`; the report states `independent_legal_review: false`.
- The reviewer checked source anchoring and evaluator behavior, not legal correctness. This is **not** independent legal review, not a user study, and not evidence of general answer quality. Questions are synthetic, the sample is 14 cases, and metrics are report-only with no numeric threshold.

### Residual gaps and limits

1. `canal-sga-2026`: lexical retrieval returns the presentation-deadline passage instead of the canal passage.
2. `fecha-modificacion-2026`: the modification passage loses the ranking and the answer budget drops the `15 de junio` claim.
3. `distingue-fechas-2026`: the false-premise date question is answered with the modification deadline and does not correct the premise.
4. `reclamacion-fuera-de-alcance`: an out-of-scope reclamación is answered with the modification deadline.
5. The sample covers only the reviewed Andalusia PAC 2026 slice: 3 topics and 5 boundaries, with 8 declared omissions; it says nothing about eligibility, aid amounts, penalties, individual notifications, monitoring-control adaptations, appeals, force majeure, or other campaigns.
6. Review is author-only; no independent legal review, user research, LLM judge, numeric threshold, or production legal assurance exists.
7. `clarification_cases` is 0 because neither the catalog nor the canonical passages declare `applicability`, so no answer in this slice can differ by land; the reasoning is in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md). This case set therefore cannot detect a PAC land-clarification regression.
8. Per-case `source_match`, `passage_match`, and `critical_facts_match` are vacuously `true` for abstention cases (empty expected sets), so a "match" on a boundary row is not a checked claim.

## Validator checklist

- [ ] Known misses remain traceable and are fixed or reported unresolved.
- [ ] Cases stay within the current reviewed corpus and declared campaign.
- [ ] Review is labeled author-only; no independent legal assurance is implied.
- [ ] Outputs are deterministic and quality metrics remain report-only.
- [ ] The published description states exact case count, topics, and omissions.
- [ ] User research, defense/demo, and unsupported topics are not added.
