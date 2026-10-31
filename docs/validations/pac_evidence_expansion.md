# `pac_evidence_expansion` acceptance

## Verdict

**Accepted** on 2026-10-27 after independent re-running. The published evidence was reproduced byte for byte; no acceptance scenario failed.

## Independent verification

Environment: this worktree (`/Users/Jose1/AndroidStudioProjects/Manijero-worktrees/pac_evidence_expansion`, base `6e0921f`, no commits made), `backend/.venv/bin/python`, offline only.

| Command | Exit | Result |
|---|---|---|
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature pac_evidence_expansion` | 0 | 20 focused tests passed; the canonical evaluator printed the 14-case `pac-answer-eval-v2` report |
| `backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-26 --k 5` (run 1) | 0 | 14 rows; see aggregates below |
| same command (run 2, plus `PYTHONHASHSEED=0` and `PYTHONHASHSEED=12345` runs) | 0 | `cmp` stdout and stderr byte-identical across all four runs |
| `MANIJERO_PYTHON=backend/.venv/bin/python CI=true ./scripts/init.sh --fast` | 0 | `:shared:jvmTest`, contract examples, 644 backend tests, source catalog, retrieval, generation, abstention, clarification, land safety; all nine offline checks passed |
| `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature backend_answer_evaluation` | 0 | the other feature that publishes this artifact still passes (20 tests + evaluator at as-of `2026-10-17`) |
| `git diff --check 6e0921f` | 0 | clean |

Reproduced report (`sort_keys`, one line): `schema_version` `pac-answer-eval-v2`, `cases` 14, `answered_cases` 11, `abstention_cases` 3, `clarification_cases` 0, `expected_state_agreement` 13, `expected_answer_coverage` 11, `unexpected_answers` 1, `source_citation_agreement` 8, `critical_fact_matches` 9, `clarification_outcomes` 0, `review.roles` `["author_only"]`, `review.independent_legal_review` false, `quality_metrics_are_report_only` true, `coverage.topics` `{canal-presentacion: 3, plazo-presentacion: 2, plazo-modificacion: 4}`, `coverage.boundaries` five areas with one case each, eight declared omissions. The emitted line is byte-identical to the raw report block in the appendix, and the appendix's six-case baseline block was regenerated from an archive of `6e0921f` and is also byte-identical.

## Acceptance scenarios

- **Resolve known misses.** All six `pac-answer-eval-v1` cases are present and their expectations are unchanged (checked case-by-case against `git show 6e0921f:knowledge/pac_answer_eval.json`); eight cases were added, none deleted. `canal-sga-2026`, `fecha-modificacion-2026`, and `distingue-fechas-2026` remain in the report as visible source/passage (and, for the last two, critical-literal) mismatches, each explained in `knowledge/pac_coverage.md` and `PROGRESS.md`. No miss became a pass by rewriting its expectation.
- **Cover current scope.** Every case's `expected_source_ids`, `expected_passage_ids`, and `critical_facts` were checked programmatically against `knowledge/source_catalog.json` and `knowledge/passages.json`: all references resolve, each expected passage belongs to its expected source, every critical fact is a literal substring of the cited passage (normalized for case/diacritics/whitespace), and all four sources are `approved`, `lifecycle_status: current`, reviewed by Diego. No new source, passage, or topic was introduced (both canonical artifacts are untouched).
- **Applicable land clarifications.** The report's `clarification_cases: 0` is correct and the scenario is satisfied vacuously, not by omission: neither the source catalog nor any canonical passage declares `applicability` (verified), so no answer in this slice can differ by land and a clarification cannot be applicable. `alcance-terrenos-2026` is the boundary case that pins the resulting behavior (two lands, deadline question, answered rather than clarified), the schema/loader already accept `needs_land_clarification` cases with `expected_land_ids_to_choose`, and the mixed-land clarification machinery remains covered by `land_safety_eval` fixtures via the fast tier. `knowledge/pac_coverage.md` states this reasoning explicitly. Residual limit: this case set would not detect a PAC clarification regression, because there is nothing land-dependent to clarify; if an applicability-declared passage is ever approved, a clarification case becomes required.
- **Author review and honest claims.** Every case carries `review.role: author_only` (`reviewed_by` Diego, `reviewed_on` 2026-10-27), the loader rejects any other role, the report states `independent_legal_review: false`, and `PROGRESS.md`, `docs/progress/current-state.md`, `docs/risks-and-open-questions.md`, `backend/README.md`, `knowledge/README.md`, and `knowledge/pac_coverage.md` all say author-only and disclaim legal correctness, broad quality, and independent review. Cases, topics, boundaries, and the eight omissions are listed.
- **Deterministic report.** Four runs with fixed corpus, campaign, date, and `k` compared byte-identical (stdout and stderr), including two different `PYTHONHASHSEED` values. No threshold or `--fail-on-miss` was added; `quality_metrics_are_report_only` is `true` and only input/contract/integrity errors exit nonzero.
- **No unsupported answer counted as evidence.** Cases are evaluated through the real `/ask` route, so an emitted answer has already passed `verify_draft`; a verifier failure becomes an abstention, never a row. `reclamacion-fuera-de-alcance` (an out-of-scope answer) is counted only in `unexpected_answers` and `expected_state_match: false`; the ranked citation/literal aggregates are computed over expected-answer cases only, so it cannot contribute to `source_citation_agreement` or `critical_fact_matches`, and `expected_answer_coverage` is documented as a state metric, not correctness.

## Generation change (`backend/app/generation.py`)

The defect and the fix were reproduced independently rather than taken from the appendix: building the pre-fix space-joined draft for `canal-excepcion-persona-fisica-2026` yields `verify_draft` failures `answer_too_long` + `critical_not_literal` on one merged claim, while the newline-joined draft verifies as two claims `(1,)` and `(2,)`. Running the new 14-case questions against an archive of `6e0921f` shows the only behavioral change is that single case (previously `abstained`, now an answered, cited answer with `rd_1048_2022`); the other 13 answers are byte-identical, and the generation, abstention, retrieval, and land-safety fixture outputs are identical to the baseline (the clarification evaluator is covered by the passing fast tier). The user-facing contract is unchanged: `_assemble_claims` still joins verified claims with a space, every probed answer is single-line with code-owned lead-in, dense response-local markers, and the orientative notice, and no Kotlin/UI/contract file changed. Skipping `--verify` is therefore defensible: the diff is Python plus JSON/docs, and `--fast` already runs `:shared:jvmTest`, the full backend suite, and every offline evaluator.

## Scope discipline

Only `pac_evidence_expansion` changed status in `feature_list.json` (`not_started` → `passing`). No other feature's spec, status, or validation record changed; no `shared/`, `androidApp/`, `desktopApp/`, `iosApp/`, `contracts/`, or Gradle file changed; no UI or Spanish copy changed; no commit was made (`HEAD` is still `6e0921f`); `.opencode-run.log` is untracked and is not part of the diff.

## Security assessment

No blocking feature-scoped issue. The diff adds no secret, dependency, network call, auth surface, or user data; cases are synthetic with opaque land ids and no personal details. Boundary validation is explicit at load (`schema_version`, closed key sets, duplicate-id, declared-area, and id-existence checks) and the report emits only source/passage identifiers, counts, and the coverage/omission metadata, never raw corpus text or case answers. Errors name the case id and JSON path without question text.

## Non-blocking findings and follow-ups

1. **Low — line break inside a reviewed excerpt.** `split_sentences` now treats every line break as a claim boundary, and the extractive generator wraps `passage.excerpt` verbatim. No current canonical or fixture excerpt contains a newline (verified), but a future approved excerpt pasted with a hard line break would be split into a claim without a marker and the whole draft would fail closed to an abstention instead of answering. Suggested follow-up (not required for this acceptance): either normalize internal whitespace when the claim is built, or reject newlines in the passage-set validator, plus one regression test.
2. **Low — vacuous per-case match booleans.** For cases that expect abstention, `source_match`, `passage_match`, and `critical_facts_match` are vacuously `true` because the expected sets are empty; the appendix table then prints "match" for boundary rows that have no expected literal. The aggregates are unaffected (they exclude non-answer cases), but the appendix table could say "sin literal esperado" so a reader cannot mistake a vacuous match for a checked one.
3. **Low — zero-clarification rationale is only in the coverage doc.** `knowledge/pac_coverage.md` justifies `clarification_cases: 0` well; the appendix states the zero without repeating the reason. A one-line pointer in the appendix's residual-limits list would keep the evidence self-contained.
4. **Note — historical record still says "six-case".** `docs/validations/backend_answer_evaluation.md` and its appendix describe the pre-expansion artifact. That is a point-in-time acceptance record and should not be rewritten; `PROGRESS.md` now points readers at `knowledge/pac_coverage.md` for the current numbers.

## Residual honesty limits that must survive into any final report

- Four case-level gaps remain measured and visible: `canal-sga-2026`, `fecha-modificacion-2026`, `distingue-fechas-2026` (wrong or incomplete reviewed passage, the last two also missing the critical literal) and `reclamacion-fuera-de-alcance` (an out-of-scope reclamación answered with the modification deadline). None is fixed by this change; the last one predates it and is not a regression.
- Review is author-only (Diego), by the same person who approved the corpus; it is not independent legal review, not a user study, not an LLM judge, and not a quality threshold.
- The sample is 14 synthetic questions over three procedural topics and five boundaries, with eight declared omissions. It says nothing about eligibility, aid amounts, penalties, individual notifications, monitoring-control adaptations, appeals or other resources, force majeure, other campaigns, or real user phrasing.
- `clarification_cases: 0` reflects a corpus with no declared `applicability`, not evidence that land clarification works on the PAC slice.
- The generation fix corrects a claim-merging defect; it is not evidence of improved answer quality, and no retrieval, readability, or user-facing-answer-quality claim is supported.

See [`pac_evidence_expansion.appendix.md`](../archive/specs/pac_evidence_expansion.appendix.md) for the implementer record and [`pac_evidence_expansion.md`](../specs/pac_evidence_expansion.md) for the contract.
