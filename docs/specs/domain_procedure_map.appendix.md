# `domain_procedure_map` — appendix

## Repository research

### Files inspected

- `AGENTS.md` — routing rules for knowledge work, Spanish copy, no invented legal facts, lean-context budgets.
- `PROGRESS.md` "Current state" — dependencies accepted; knowledge limitations that must not be over-claimed.
- `feature_list.json` line for `domain_procedure_map` — area `knowledge`, deps `backend_pac_corpus` + `coverage_and_help`, spec/validation paths; two dependent features (`relevance_classifier`, `question_rewriting`).
- `docs/archive/MasterPlanV3.md` §7.3 — the seed-topic list and the three purposes (scouting keywords, evaluation coverage, suggested questions); §11.2 — seed corpus and "pending localization" topics (organic, irrigation, pruning burning, insurance).
- `docs/specs/backend_pac_corpus.md` — bounded-corpus rules, honest gaps, verify-block shape.
- `docs/specs/coverage_and_help.md` — pinned plain-Spanish topic copy and refusal classes; the copy must track corpus scope in the same change that widens/narrows it (future handoff, not this feature).
- `docs/constraints/answers-and-knowledge.md` "Coverage disclosure", "Knowledge updates and retrieval" — the MUST rules the map must not violate.
- `CONSTRAINTS.md` — area index and rule-writing convention.
- `knowledge/README.md` — Files table, reviewer procedure, `passage-set-v1` section, validator command convention.
- `knowledge/pac_coverage.md` — three reviewed PAC topics, exclusions, reviewer/date, report-only metrics.
- `knowledge/source_catalog.json`, `knowledge/source_catalog.schema.json` — four approved ids (`res_20260121`, `dl_1_2026`, `rd_1048_2022`, `rd_537_2026`); schema style (`manijero.invalid` `$id`, descriptions that state limits).
- `knowledge/passages.json` — four passage ids and their `source_id` links.
- `backend/app/source_catalog.py` — validator architecture to mirror: accumulating issues, JSON-path + rule only, read error type, stdlib only.
- `backend/scripts/validate_source_catalog.py` — CLI shape: positional artifact, optional flags, exit `0/1/2`, no network.
- `backend/tests/test_source_catalog.py` — test conventions: backend root on `sys.path`, CLI via `subprocess`, schema/validator parity asserted from plain JSON; `jsonschema` is an existing dev dependency (`backend/requirements-dev.txt`) if stricter checks are wanted.
- `scripts/init.sh` — `--feature` extracts and runs the verify block with `bash -euo pipefail`; `--backend-tests <target>` runs pytest from `backend/` and skips (exit `0`) when pytest is absent, fails under `CI`.
- `docs/risks-and-open-questions.md` — medium-risk and open-decision rows where the taxonomy risk belongs.
- `ARCHITECTURE.md` — `knowledge/` ownership bullet and the "Knowledge artifact shape" table row.

Not inspected: full `backend/README.md` (no backend operator surface planned), `docs/owner-guide/` (no owner command), Gradle/shared sources (untouched), each schema's full JSON.

### Existing patterns to follow

- One readable JSON Schema beside one stdlib executable validator that must stay in sync, with the schema's `description` stating what validation does **not** prove.
- Diagnostics carry only JSON path and rule; field values are never echoed. All violations are accumulated in one report.
- Canonical artifacts live in `knowledge/`; CLI wrappers live in `backend/scripts/`; tests stay offline with synthetic or in-memory data.
- Deterministic, repeatable output; no `--as-of` is needed because the map carries no dates.
- A focused spec verify block of two short commands, run unchanged by `./scripts/init.sh --feature`.

### Current gaps

- No taxonomy artifact, schema, validator, or report exists; topic lists live in prose (`MasterPlanV3` §7.3, `coverage_and_help` copy) and drift silently.
- No owner/target-user review of the topic list exists; all entries must therefore ship `proposed`.
- The owner brief says 17 seed topics; §7.3 names 16. No 17th name exists in the repository, so the map ships the 16 named topics and a reviewed change adds another later if the owner names it.

## Implementation plan

1. Write `knowledge/procedure_map.schema.json` (`procedure-map-v1`): top-level `schema_version` + `topics`, `$defs` for ids/coverage/review states, `minItems: 16`, `additionalProperties: false`, and descriptions that state the map is not legal knowledge or an answer source.
2. Write `backend/app/procedure_map.py`: `ProcedureMapReadError`, `load_procedure_map`, immutable issues plus per-topic coverage rows (`id`, review state, evidence state, reference counts), `validate_procedure_map(document, catalog_ids=None, passage_sources=None)`, an ordered `SEED_TOPIC_IDS` tuple, unknown-key, duplicate-id, digit/length/slug checks, review and coverage state rules, and cross-reference checks.
3. Write `backend/scripts/validate_procedure_map.py`: positional map, optional `--catalog`/`--passages` (both or neither), `--report`, exit codes `0/1/2`, one summary line plus the coverage line.
4. Write `knowledge/procedure_map.json`: 16 topics in §7.3 order, all `proposed`, plain-Spanish titles/summaries/terms, `solicitud-unica-pac` → `partial` with the four source ids, four passage ids, and a digit-free gap note; the other 15 → `uncovered` with empty arrays.
5. Write `backend/tests/test_procedure_map.py`: canonical map valid with seed set/order and search terms unique across topics; schema checks (valid + rejected); one case per rejection rule; CLI success, invalid (exit `1`), unreadable (exit `2`), `--report` lines, and "gaps do not fail the run".
6. Update `knowledge/README.md` (Files rows + section), `docs/constraints/answers-and-knowledge.md` + `CONSTRAINTS.md` index, `ARCHITECTURE.md` clause, `docs/risks-and-open-questions.md` row.
7. Run the focused verification, record evidence below, then update `PROGRESS.md` status/limitations per `feature-flow` (not during planning).

## Verification plan

- `python3 backend/scripts/validate_procedure_map.py knowledge/procedure_map.json --catalog knowledge/source_catalog.json --passages knowledge/passages.json --report` → exit `0`; `valid procedure map … 16 topics: 16 proposed, 0 reviewed`; coverage line `1 partial, 15 uncovered` plus mapped counts; 16 `topic …` lines.
- `./scripts/init.sh --backend-tests tests/test_procedure_map.py` → focused pytest green (skipped only when pytest is absent locally; required under `CI`).
- Negative checks run by the test module: exit `1` with a located rule per rejection case, exit `2` on broken JSON, no field values in diagnostics.
- Manual acceptance check in the contract (read the map; run the report; read the README section) → reviewer can state what the map is, which topics are unreviewed, and which evidence is mapped.
- E2E: not needed — no UI, route, auth, or API flow changes; the offline validator plus pytest is the whole surface.
- `./scripts/init.sh --fast` is not part of the focused block; it runs the whole backend suite, so run it once before handoff when pytest is available.

## Evidence to capture

- Validator command with its last lines (summary + coverage counts) and exit status.
- Focused pytest result (passed count) and the names of the rejection cases.
- Manual checklist result: 16 topics in order, no digits in human text, all `proposed`, PAC `partial` references resolve, README states limits.
- Diff file list proving corpus bytes, app/shared, contracts, and `scripts/init.sh` unchanged.

## Feature evidence

2026-11-06, implementer self-verification:

- `python3 backend/scripts/validate_procedure_map.py knowledge/procedure_map.json --catalog knowledge/source_catalog.json --passages knowledge/passages.json --report` → exit `0`; `valid procedure map … (schema procedure-map-v1, 16 topics: 16 proposed, 0 reviewed)`; `coverage: 0 covered, 1 partial, 15 uncovered; 4 mapped source(s), 4 mapped passage(s); unreferenced source ids: none; unreferenced passage ids: none`; 16 `topic …` lines.
- `./scripts/init.sh --feature domain_procedure_map` → focused tier passed (both published commands, 49 tests).
- `./scripts/init.sh --backend-tests tests/test_procedure_map.py` → `49 passed`.
- `./scripts/init.sh --fast` → all 10 offline checks passed; backend suite `1920 passed, 4 skipped`.
- Manual check: 16 topics in the contract table order, every `review_status` `proposed` with no `reviewed_by`, only `solicitud-unica-pac` `partial` with the four catalog ids and four passage ids (each passage source listed), 15 `uncovered` with empty lists; no digit in any title, summary, search phrase, or gap note; search wording unique within and across topics; README section states the map is an index, not legal knowledge or an answer source, and how `reviewed` and gaps work.
- Rejection coverage in the test module: missing/unknown/duplicate/out-of-order topic, `reviewed` without reviewer, reviewer on `proposed`, `covered`/`partial` without references, `uncovered` with references, unknown source/passage, passage source not listed, unknown key (topic and top-level), blank/over-long text, digits in each human field, empty/too many/duplicate search phrasing, unknown review/coverage state, broken JSON and missing file (exit `2`), and no field values in diagnostics.
- Diff file list: only the spec's expected paths changed (`knowledge/procedure_map.json`, `knowledge/procedure_map.schema.json`, `backend/app/procedure_map.py`, `backend/scripts/validate_procedure_map.py`, `backend/tests/test_procedure_map.py`, `knowledge/README.md`, `docs/constraints/answers-and-knowledge.md`, `CONSTRAINTS.md`, `ARCHITECTURE.md`, `docs/risks-and-open-questions.md`, `PROGRESS.md`, `docs/progress/known-limitations.md`, `feature_list.json`) plus the planner-created spec and appendix; `knowledge/source_catalog.json`, `knowledge/passages.json`, `knowledge/pac_coverage.md`, `knowledge/pac_answer_eval.json`, `contracts/`, `backend/app` request-path modules, `shared/`, and `scripts/init.sh` are byte-unchanged.
- Seed-count decision: MasterPlanV3 §7.3 names 16 topics and the owner brief assumed 17; no 17th topic name exists in the repository, so the map ships exactly the 16 named topics. A further topic is a reviewed code-and-data change, never an invented entry.

2026-11-06, independent validator: **accept**. Both published commands ran unchanged (focused
pytest `49 passed`), `--fast` passed 10/10 offline checks, and independent probes confirmed
located value-free diagnostics, exit codes `0/1/2`, and gaps that never gate exit `0`. Acceptance
record: [`../validations/domain_procedure_map.md`](../validations/domain_procedure_map.md).

## Validator checklist

- [ ] Contract scenarios pass with evidence: 16-topic canonical map, resolved PAC references, reported (not rejected) gaps, located value-free rejections, no legal facts, untouched accepted bytes.
- [ ] The seed set/order matches §7.3 and the contract table; no extra topic was invented; every topic is `proposed` at delivery (no reviewer exists yet).
- [ ] Schema, validator, and README agree on `procedure-map-v1` field names and state values; schema descriptions state the non-legal, non-answer nature.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature domain_procedure_map`.
- [ ] Coverage gaps only affect output, never exit status; cross-reference checks only run when both `--catalog` and `--passages` are supplied.
- [ ] Diagnostics contain no field values and no document text; validator is stdlib-only and offline.
- [ ] Durable documentation impact followed (README, constraints + index, ARCHITECTURE, risks); no corpus, app, contracts, or `scripts/init.sh` changes.
- [ ] `PROGRESS.md` / `docs/progress/known-limitations.md` updated only after verification, with an honest "proposed taxonomy, no owner or target-user review, 15/16 topics without reviewed evidence" line.
- [ ] `feature_list.json` status updated by the implementing flow, not during planning.
