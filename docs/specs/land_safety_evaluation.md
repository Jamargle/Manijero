# Feature Spec: `land_safety_evaluation`

## Source metadata

- Feature: `land_safety_evaluation` — Evaluate land-aware answer safety
- Area: evaluation
- Depends on: `safe_abstention` (accepted), `land_clarification` (accepted)
- Feature-list behavior: changes to retrieval or land context can be checked against reviewed cases for correct sources, safe abstention, and correct land clarification.
- Feature-list verification: run source-anchored covered, uncovered, mixed-land, unknown-attribute, and false-premise cases; review critical facts against original sources.
- Feature-list note: set numerical gates only after measuring a baseline.
- Scope size: one reviewed case-set contract plus one offline evaluation harness over the accepted end-to-end decision. One data model, one offline flow; correctly sized. It stops at a report and does not touch any route, client, contract, or accepted module.

## Goal

Add a reviewed, source-anchored evaluation set and an offline harness that runs the **accepted** end-to-end decision (`answer_with_clarification`, which already composes retrieval, grounding, abstention, and land clarification) over those cases and reports, per category, whether the service returned the correct sources, abstained safely, or clarified the correct land. Turn the deferred measurements from the accepted slices — `safe_abstention`'s "measured trap set and any score threshold belong to `land_safety_evaluation`" and `land_clarification`'s "`land_safety_evaluation` owns measurement" — into one reproducible, dependency-free baseline, and record the critical-fact review provenance the corpus policy requires. Report numbers; do **not** enforce thresholds, because the corpus is synthetic and no real legal source exists yet.

## Non-goals

- Serving HTTP or wiring `POST /ask`. `backend/app/main.py` keeps `/health` as its only route and no FastAPI/Pydantic dependency is added.
- A model provider, a semantic judge/NLI, an LLM grader, embeddings, or any network access. The only enabled generator is the accepted code-composed extractive one, and grading is deterministic rule checking.
- Changing the contract (`contracts/`), the accepted modules (`app/generation.py`, `app/retrieval.py`, `app/abstention.py`, `app/clarification.py`, `app/source_catalog.py`), the per-feature CLIs/tests, `knowledge/source_catalog.json`, `knowledge/passages.schema.json`, `backend/requirements.txt`, `scripts/init.sh`, or any client/shared/Android/Desktop/iOS code.
- Enforcing metric gates or adding CI/nightly automation. Thresholds are reported as *candidate* starting points and are off by default; a separate, agreed change owns enforcement.
- Adding a canonical real corpus or asserting any real legal fact. All cases/passages remain synthetic and labelled; critical-fact review is recorded as a human process, never performed by the harness.
- Client presentation or UI. This feature only produces a backend report.

## Job story

When I change retrieval, generation, abstention, or the land-context/clarification logic, I want a single reviewed case set and one offline command that tells me whether the accepted end-to-end decision still cites the right sources, still abstains on uncovered/false-premise questions, still asks for the right land on mixed-land questions, and still does **not** over-ask or invent a value on unknown attributes — so I can see a regression the moment I introduce one, and calibrate any threshold from a measured baseline instead of a guess.

## Acceptance scenarios

### Covered, source-anchored case cites the expected source

Given a `covered` case whose `expected_source_ids` name reviewed synthetic sources, when the harness runs it, then the outcome is `answered` and every expected source id appears among the returned `Answered.sources` source ids.

### Uncovered case abstains safely

Given an `uncovered` case (out-of-corpus) with `expect: abstained` and an expected reason, when the harness runs it, then the outcome is `abstained` with that reason, `sources == []`, and a pinned message with no digit and no date.

### Mixed-land case clarifies the correct land

Given a `mixed_land` case with two lands whose known `water_regime`/`production_method` disagree with retrieved applicability, when the harness runs it, then the outcome is `needs_land_clarification` and `land_ids_to_choose` is exactly the expected set, drawn from the request's own ids.

### Unknown-attribute case answers without over-clarifying or inventing

Given an `unknown_attribute` case whose lands omit or declare `unknown` for the discriminating dimension, when the harness runs it, then the outcome is `answered` (no clarification), and the harness records **no** over-clarification and no invented attribute value.

### False-premise case abstains instead of answering around the premise

Given a `false_premise` case naming an instrument/article identifier absent from all retrieved candidates, when the harness runs it, then the outcome is `abstained` with reason `false_premise` and empty `sources`.

### Critical facts carry a completed human review

Given a `critical` case, when the harness loads it without a completed `review` block (reviewer, review date, level, source anchor), then loading fails closed (exit `2`); a well-formed critical case is echoed in the report's review section for manual audit.

### Reproducible, report-only baseline

Given the fixtures and an explicit `--as-of`/`--k`, when the harness runs, then it prints each case's outcome plus per-category metrics (`covered_source_hit_rate`, `correct_abstention_rate`, `correct_clarification_rate`, `no_over_clarification_rate`), two `--json` runs are byte-identical, and thresholds are not enforced unless `--fail-on-miss` is passed.

## Technical approach

### Case-set contract

Add a readable, versioned contract `knowledge/land_safety_eval.schema.json` (`land-safety-eval-v1`) mirroring the catalog/passage schemas, plus its strict in-code validator. A case document is:

```json
{
  "schema_version": "land-safety-eval-v1",
  "cases": [
    {
      "id": "covered-solicitud-unica-01",
      "category": "covered",
      "question": "¿Pregunta sintética de ejemplo?",
      "land_context": { "mode": "general", "lands": [] },
      "expect": "answered",
      "expected_source_ids": ["fixture-src-a"],
      "expected_passage_ids": ["fixture-passage-a1"],
      "critical": false,
      "review": null
    }
  ]
}
```

Rules: `category` ∈ `covered | uncovered | mixed_land | unknown_attribute | false_premise`; `expect` ∈ `answered | abstained | needs_land_clarification`; `land_context` uses only the accepted request keys (`mode`, `lands`; each land: `id` plus the optional `municipality`/`water_regime`/`production_method`). Conditional requirements (a missing one is a located load error, exit `2`): `expect_reason` (one of the 9 taxonomy reasons, from `ABSTENTION_REASONS`) required when `expect == "abstained"`; `expected_source_ids` non-empty required when `expect == "answered"`; `expected_land_ids_to_choose` non-empty required when `expect == "needs_land_clarification"`; a non-null `review` required when `critical == true`. Unknown keys are rejected. `review` is `{ "reviewed_by", "reviewed_on" (YYYY-MM-DD), "level" (int ≥ 1), "anchor" ("<source_id>#<location>") }`. The document is Git-tracked and human-reviewed like the catalog and passage set.

### Evaluation harness

Add `backend/app/land_safety_eval.py`, a pure standard-library module that imports the accepted modules unchanged and never re-implements eligibility, grounding, or clarification:

- `load_cases(path)` — strict validation with located errors (`LandSafetyEvalError`, path such as `$.cases[0].expected_source_ids`), never echoing case text into a message the CLI prints by default.
- `run_case(case, corpus, as_of, k)` — calls `answer_with_clarification` once and records: the outcome, reason, generation reason, returned source ids/passage ids, `land_ids_to_choose`, the assembled payload, and per-check verdicts.
- `evaluate(cases, corpus, as_of, k)` — returns a report with per-case rows, per-category totals, the aggregate metrics below, and the list of critical cases with their review provenance.
- Checks per case: `correct_outcome` (matches `expect`); `correct_sources` (every `expected_source_ids` present, and no source outside the corpus); `safe_abstention` (abstained payload has empty `sources`/`land_ids_to_choose`, a pinned message, no digit, no date); `correct_clarification` (clarified ids equal `expected_land_ids_to_choose`, all drawn from the request); `no_over_clarification` (a `covered`/`unknown_attribute` case is not clarified).
- Metrics: `covered_source_hit_rate` (covered answered cases with `correct_sources`), `correct_abstention_rate` (uncovered + false_premise cases abstaining with the expected reason), `correct_clarification_rate` (mixed_land cases with `correct_clarification`), `no_over_clarification_rate` (covered + unknown_attribute cases not clarified), and `expected_outcome_match_rate` overall.

Enforced safety invariants (exit `1`, because they mean the service leaked or invented something): every assembled payload has exactly the accepted `AskResponse` keys; an abstention carries no source/figure/date and a reason inside the taxonomy; a clarification carries an empty answer, no sources, and only the request's own ids; an answered payload has at least one source and every `[n]` marker within the `sources` range. Coverage and expected-source/clarification mismatches are **report-only** unless `--fail-on-miss` is passed.

### CLI

Add `backend/scripts/evaluate_land_safety.py`, mirroring the accepted CLIs:

```sh
python3 backend/scripts/evaluate_land_safety.py \
  --catalog backend/tests/fixtures/land_safety/catalog.json \
  --passages backend/tests/fixtures/land_safety/passages.json \
  --cases backend/tests/fixtures/land_safety/cases.json \
  --as-of 2026-10-13 --k 5
```

Flags: `--catalog` (required), `--passages`/`--cases` (optional; omit for a corpus summary), `--as-of` (default current UTC date), `--k`, `--max-claims`, `--json`, `--fail-on-miss`. It prepares the corpus with `prepare_corpus` (reporting `current`/`not_current`), runs each case, prints the per-case verdicts, the per-category table, the metric block, and the critical-review section, and emits `fixtures_are_synthetic: true` and `thresholds_are_release_gates: false`. Exit codes: `0` report produced and every safety invariant held; `1` an invariant failed or (`--fail-on-miss`) any case's outcome/sources/clarification ids differed from its expectation; `2` an unreadable/rejected input or invalid argument (unknown category/expect, missing conditional field, a critical case without a completed review, malformed JSON, `--k`/`--max-claims` < 1). The canonical empty catalog with no cases reports zero candidates and no metrics, inventing nothing.

### Baseline and gates

Run the harness once over the synthetic fixtures and record the measured numbers in `PROGRESS.md` and the `feature_list.json` evidence as the baseline. Document the `MasterPlanV3` §9.2 candidate starting points (`hit@5 85%`, correct abstention `100%`, invented numbers/dates `0`) in `backend/README.md` as **inherited proposals, not enforced gates**, and state plainly that the synthetic corpus is not legal-coverage evidence. Any enforcement is a later, separately agreed change.

## Expected file changes

- Create `knowledge/land_safety_eval.schema.json` — versioned `land-safety-eval-v1` readable contract.
- Create `backend/app/land_safety_eval.py` — case loading/validation, per-case checks, metrics, critical-review requirement.
- Create `backend/scripts/evaluate_land_safety.py` — offline report-only CLI with the `0`/`1`/`2` contract.
- Create `backend/tests/test_land_safety_eval.py` — focused tests.
- Create `backend/tests/fixtures/land_safety/{catalog.json,passages.json,cases.json}` — synthetic approved catalog, labelled reviewed passages (including a differing `water_regime` pair, an unknown/omitted attribute, a false-premise identifier, and an uncovered topic), and cases for all five categories plus malformed/incomplete edge documents.
- Update `knowledge/README.md` — the case-set contract, the review procedure, and the critical-fact review requirement.
- Update `backend/README.md` — the safety-evaluation boundary, CLI, and the candidate-gate caveat.
- Update `CONSTRAINTS.md` — one MUST rule: evaluation cases are source-anchored and human-reviewed, a critical case cannot enter the set without completed review provenance, the harness runs the accepted decision unchanged, and no metric is a release gate until measured and agreed.
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with the real status, measured baseline, and only the commands actually run. This planning pass records the spec link only.

`scripts/init.sh`: no change. It executes KMP checks only and has no backend command; this backend/knowledge slice is verified with the documented Python commands, and no long-running process or new mode is added.

Explicitly **not** changed: `contracts/`, `backend/app/{generation,retrieval,source_catalog,abstention,clarification}.py`, `backend/app/main.py`, the per-feature `scripts/evaluate_*.py` and `tests/test_*.py`, `knowledge/source_catalog.json`, `knowledge/passages.schema.json`, `backend/requirements.txt`, `scripts/init.sh`, and all client/shared/Android/Desktop/iOS code.

## Visual design impact

None. This is an offline backend/knowledge evaluation harness; it adds no Compose UI and no user-facing Spanish copy.

## Durable documentation impact

- `knowledge/README.md`: update; it is the durable operational contract for how reviewed cases relate to the approved catalog and how critical facts are reviewed.
- `knowledge/land_safety_eval.schema.json`: create; the durable, versioned case format.
- `backend/README.md`: update; the durable backend boundary document now lists the safety-evaluation harness and the not-enforced gate stance.
- `CONSTRAINTS.md`: update; the "reviewed cases, no unmeasured gate" mechanism rule is durable.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, `MasterPlanV3.md`, `docs/risks-and-open-questions.md`: no update; they already state the evaluation and grounding principles.
- `ARCHITECTURE.md`: not needed; absent, and a focused offline evaluation boundary does not establish a broader runtime architecture.
- `PROGRESS.md` and `feature_list.json`: update after verification, recording the measured baseline and stating plainly that it is synthetic, not a legal-coverage or legal-correctness claim.

## Risks and handoff notes

The case set and its baseline are synthetic and implementer-authored: they exercise the mechanism and the trap taxonomy, not legal coverage or real Spanish user questions. The harness records critical-fact review provenance but cannot verify a fact against an original document — a human reviewer must, and until a real legally-reviewed corpus exists the critical cases anchor to labelled synthetic passages. The lexical detection in the accepted slices is conservative (it can abstain or over-ask on a retrieval miss); this feature measures that behaviour rather than changing it, so a low synthetic number is a calibration starting point, not a defect or a gate. Threshold enforcement, nightly runs, a semantic judge, a canonical corpus, and a feedback-to-golden loop are deliberately out of scope.

Handoffs: `answer_land_scope`, `android_mvp_build`, and `desktop_mvp_build` depend on this feature; when a real corpus and a `POST /ask` route land, extend the case set from real, source-anchored questions and only then agree which metrics become hard gates. Carried-forward accepted findings (backend F1 marker/sources hardening, F2 non-iterable `source_markers`, the `land_clarification` >128-char id defensive note) are unchanged and stay with their owners.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_land_safety.py --catalog backend/tests/fixtures/land_safety/catalog.json --passages backend/tests/fixtures/land_safety/passages.json --cases backend/tests/fixtures/land_safety/cases.json --as-of 2026-10-13 --k 5
./scripts/init.sh --backend-tests tests/test_land_safety_eval.py
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/land_safety_evaluation.appendix.md`](land_safety_evaluation.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/land_safety_evaluation.md` remains the authoritative acceptance record.
