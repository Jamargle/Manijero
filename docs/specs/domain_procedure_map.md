# Olive-grove procedure map (`procedure-map-v1`)

## Source metadata

- `id`: `domain_procedure_map` · `area`: knowledge · `depends_on`: `backend_pac_corpus`, `coverage_and_help` (both accepted) · `status` at planning: `not_started`.
- User-visible behavior: none in the app. The map is a Git-tracked, reviewed taxonomy that a person (owner/reviewer) reads in `knowledge/procedure_map.json` and `knowledge/README.md`, and that an offline validator reports on. No app screen, route, or answer changes.
- Verification: offline validator over the canonical map plus its cross-references to the approved catalog and passages, and a focused pytest module; commands are in Focused verification.
- Notes (owner decisions recorded as planning assumptions; the owner could not be asked interactively):
  - Scope = the seed topics of `docs/archive/MasterPlanV3.md` §7.3, each with a review state; anything not human-reviewed stays `proposed`. §7.3 names **16** topics; the owner brief said "17". The map ships the 16 named topics verbatim, and adding a further topic is a reviewed change (see the appendix's "Current gaps").
  - Surface = `knowledge/` artifacts only: data file, JSON Schema, stdlib validator module, CLI wrapper, and `knowledge/README.md`. No UI, Compose, backend route, or `contracts/openapi.yaml` change.
  - Coverage gaps are **reported, not gated**: a topic with no reviewed evidence passes validation and appears in the coverage report.
  - A later owner review of the topic list is expected and is **not blocking**; until then every topic is `proposed`.

## Goal

Give the product one reviewed list of olive-grove procedures so source scouting, question work, coverage disclosure, and evaluation stop inventing separate topic lists. The map names each procedure in plain Spanish, carries search wording for later scouting/rewriting, and records — per topic — whether the approved corpus contains reviewed evidence, without turning the map into legal knowledge or a coverage gate.

## Non-goals

- No legal content: no dates, amounts, thresholds, article numbers, requirements, eligibility conclusions, or applicability claims anywhere in the map.
- No change to `knowledge/source_catalog.json`, `knowledge/passages.json`, `knowledge/pac_coverage.md`, `knowledge/pac_answer_eval.json`, or any accepted corpus bytes; the map never approves, retires, or re-dates evidence.
- No answer-path, retrieval, classifier, glossary, evaluation-case, suggested-question, or `/ask` integration; `relevance_classifier` and `question_rewriting` consume the map later, in their own features.
- No app UI or Compose copy change (including the pinned `coverage_and_help` disclosure) and no backend route or OpenAPI change.
- No keyword scraping, automatic topic extraction from documents, or scheduled job.
- No new dependency: Python standard library only, offline.

## Job story

When I need to decide which olive-grove procedures the assistant is meant to cover, I want one reviewed, machine-readable list with honest per-topic evidence states, so that scouting, questions, coverage copy, and evaluation all refer to the same procedures instead of drifting apart.

## Acceptance Scenarios

### 1. The canonical map lists exactly the seed topics

Given the accepted `MasterPlanV3.md` §7.3 seed list · When the canonical map is validated · Then it contains the 16 topics below in that order, each with a stable id, a plain-Spanish title, a one-or-two-sentence summary, and unique search wording; every topic has `review_status: "proposed"` and no `reviewed_by`; the PAC topic is `partial` and every other topic is `uncovered`.

| id | title (plain Spanish) |
|---|---|
| `solicitud-unica-pac` | Solicitud Única de la PAC |
| `sigpac` | SIGPAC |
| `ayuda-directa-olivar` | Ayuda directa al olivar |
| `agricultor-activo` | Agricultor activo |
| `superficies-minimas` | Superficies mínimas |
| `riego` | Riego |
| `condicionalidad` | Condicionalidad |
| `cuaderno-digital` | Cuaderno digital |
| `ayudas-junta-andalucia` | Ayudas de la Junta de Andalucía |
| `notificaciones-y-rectificaciones` | Notificaciones y rectificaciones |
| `delegacion-entidades-colaboradoras` | Delegación en entidades colaboradoras |
| `pagos` | Pagos |
| `quema-restos-poda` | Quema de restos de poda |
| `productos-fitosanitarios` | Productos fitosanitarios |
| `seguros-agrarios` | Seguros agrarios |
| `produccion-ecologica` | Producción ecológica |

### 2. Evidence references resolve to the accepted corpus

Given the canonical catalog and passage set · When the map is validated with both supplied · Then `solicitud-unica-pac` (state `partial`) references the four approved source ids and the four reviewed passage ids of the accepted PAC slice, every referenced id exists in those files, and each referenced passage's `source_id` is listed by that topic.

### 3. Uncovered topics are reported, never rejected

Given 15 topics with state `uncovered` and no references · When the map is validated · Then validation exits `0` and prints a coverage summary with the `partial`/`uncovered` counts and how many approved sources and reviewed passages are mapped anywhere; with `--report` it also prints one line per topic; no missing coverage fails the run.

### 4. Unsupported or unsafe entries are rejected with located, value-free errors

Given a map with a missing seed topic, an unknown topic id, a duplicate id, `reviewed` without a reviewer, a reviewer on a `proposed` topic, a covered/partial topic without references, references to an unknown source/passage, an unknown key, a blank or over-long text, or a digit in a human-readable field (title, summary, search wording, gap note) · When it is validated · Then it exits `1`, reports every violation with a JSON path and the rule, and echoes no field values; an unreadable or non-JSON file exits `2`.

### 5. The map cannot be read as legal knowledge

Given the canonical map and the updated `knowledge/README.md` · When a reviewer reads them · Then human-readable fields contain no digits (no dates, amounts, article numbers) and no eligibility or applicability claim; the README states the map is a taxonomy index, not approved knowledge or an answer source, and that `reviewed` requires a named human reviewer in a reviewed change.

### 6. Nothing else changes

Given this feature is implemented · When the diff is reviewed · Then `knowledge/source_catalog.json`, `knowledge/passages.json`, `knowledge/pac_coverage.md`, `knowledge/pac_answer_eval.json`, `contracts/`, `backend/app` request-path modules, `shared/`, and `scripts/init.sh` are byte-unchanged.

## Technical approach

- Add one canonical artifact `knowledge/procedure_map.json` (`schema_version: "procedure-map-v1"`) and its readable JSON Schema `knowledge/procedure_map.schema.json` (draft 2020-12, `$id` under `manijero.invalid`, description stating the map is not legal knowledge and not an answer source). Follow `knowledge/source_catalog.schema.json` conventions and keep the executable validator in sync.
- Model each topic as: `id`, `title`, `summary`, `search_terms` (1–6 plain-Spanish phrases for later scouting/rewriting), `review_status` (`proposed` | `reviewed`), optional `reviewed_by`, and `coverage` (`state`: `covered` | `partial` | `uncovered`; `source_ids`; `passage_ids`; optional `gap_note`). The artifact carries no date fields; review provenance is Git.
- Pin the seed set in the validator as an ordered tuple of the 16 ids above; reject a missing seed topic and an id outside the set, so widening the taxonomy is a reviewed code + data change. Reject duplicate ids, unknown keys, blank/over-long text, and digit characters in `title`, `summary`, `search_terms`, and `gap_note`. Note in the schema description that the ordered seed set, duplicate ids, the no-digit rule, and cross-file references are enforced by the validator, not by the schema.
- Enforce declaration honesty, not coverage: `covered`/`partial` need at least one source and one passage; `uncovered` must carry none; `partial` needs a `gap_note`; `reviewed` needs a non-blank `reviewed_by`; `proposed` must omit it.
- Add `backend/app/procedure_map.py` (stdlib only): immutable read error, `validate_procedure_map(document, catalog_ids=None, passage_sources=None)` returning a report with payload-safe `issues` (JSON path + rule only, mirroring `backend/app/source_catalog.py`), plus a deterministic coverage report; cross-check references only when both optional inputs are supplied and reject a passage whose source the topic did not list.
- Add `backend/scripts/validate_procedure_map.py`: `map` positional, optional `--catalog` + `--passages` (both or neither), `--report` for one line per topic; exit `0` valid, `1` invalid, `2` unreadable; prints a coverage summary (counts, mapped sources/passages, unreferenced ids) that never gates exit `0` on gaps.
- Python only; do not touch runtime modules, the app, or the answer path. Tests use in-memory valid/mutated documents (no new fixture corpus) and schema validation with `jsonschema`. Leave `scripts/init.sh` unchanged: its existing `--feature` mode must run this block as published.

## Expected file changes

- `knowledge/procedure_map.json` — create; canonical 16-topic map, all `proposed`, PAC topic `partial` with the accepted evidence ids.
- `knowledge/procedure_map.schema.json` — create; `procedure-map-v1` readable contract.
- `backend/app/procedure_map.py` — create; offline validator + coverage report.
- `backend/scripts/validate_procedure_map.py` — create; stdlib CLI wrapper.
- `backend/tests/test_procedure_map.py` — create; canonical map, seed set, schema, rejection cases, CLI, report.
- `knowledge/README.md` — update; two Files rows, validator row, and a `procedure-map-v1` section.
- `docs/constraints/answers-and-knowledge.md` + `CONSTRAINTS.md` — update; one "Procedure map" rule and its index entry.
- `ARCHITECTURE.md` — update; one clause that the map is a taxonomy index, not an answer source.
- `docs/risks-and-open-questions.md` — update; one medium-risk row (unreviewed taxonomy, owner review pending).
- `PROGRESS.md` and `docs/progress/known-limitations.md` — update after verification only (one limitation line).

## Visual design impact

None. No UI, Compose, string resource, or DESIGN.md change.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — the `knowledge/` bullet states the procedure map is a reviewed taxonomy index, never an answer source.
- `docs/constraints/answers-and-knowledge.md`: update — new "Procedure map" MUST rules (not legal knowledge, not an answer/coverage gate, `reviewed` only with a named human reviewer, gaps reported not enforced, no corpus bytes changed by mapping); list the section in the `CONSTRAINTS.md` index row.
- `AGENTS.md`: not needed — no workflow, startup, or repo-wide rule changes; the knowledge/ route already points at the artifact schema.
- Other: `knowledge/README.md` as above; `docs/risks-and-open-questions.md` one row; `PROGRESS.md` + `docs/progress/known-limitations.md` after verification. `CONTEXT.md`, `docs/domain-model.md`, `DESIGN.md`, `contracts/openapi.yaml`, `backend/README.md`: not needed.

## Focused verification (required)

<!-- verify:start -->
```sh
python3 backend/scripts/validate_procedure_map.py knowledge/procedure_map.json --catalog knowledge/source_catalog.json --passages knowledge/passages.json --report
./scripts/init.sh --backend-tests tests/test_procedure_map.py
```
<!-- verify:end -->

### Manual acceptance check

1. Open `knowledge/procedure_map.json`: read the 16 topics in the table order; confirm plain-Spanish titles/summaries, search wording unique across topics, no dates, amounts, article numbers, or eligibility wording, `proposed` everywhere with no reviewer, and that only `solicitud-unica-pac` carries `partial` with references that exist in the catalog/passages.
2. Run the first verification command: it prints `valid procedure map`, a coverage line with `1 partial, 15 uncovered` and mapped counts, then 16 `topic …` lines, and exits `0`.
3. Read the new `knowledge/README.md` section: it states what the map is and is not, how a topic becomes `reviewed`, that gaps are reported only, and how to run the validator.

## Appendix

Research, plan, verification detail, evidence, and the validator checklist are in [`domain_procedure_map.appendix.md`](domain_procedure_map.appendix.md).
