# Backend PAC answer evaluation — planning and verification record

## Repository research

- `backend/app/generation.py` provides deterministic extractive generation and a code-owned grounding verifier. No hosted provider is configured.
- `backend/app/abstention.py`, `backend/app/clarification.py`, and `backend/app/land_safety_eval.py` provide accepted abstention, land-clarification, and offline land-safety behaviors.
- `backend/scripts/evaluate_retrieval.py`, `evaluate_generation.py`, `evaluate_abstention.py`, and `evaluate_clarification.py` are independent lower-level evaluators over synthetic fixtures. They do not exercise the assembled HTTP `/ask` route or the real reviewed PAC source slice.
- `backend/scripts/evaluate_land_safety.py` and `knowledge/land_safety_eval.schema.json` establish the report-only, strict artifact, source-review pattern. Its results are report-only; existing fixture metrics are not a legal-coverage claim.
- `contracts/openapi.yaml` defines three response states and intentionally omits internal source/passage IDs. An endpoint evaluator must map a returned source URL/location/excerpt to an approved catalog entry and passage; it must not change the public contract to add evaluator IDs.
- `docs/build-brief.md` and `docs/technical-discovery.md` require source-anchored measurement, report-only results until a baseline is reviewed, and no numerical threshold set before that baseline.

## Case-set design

The first reviewed set should be small enough for a human to audit and should include at least:

- One answered case for each approved procedure topic: ordinary SGA/recognized-entity route, final 2026 filing date, and 2026 modification date.
- One case that distinguishes the 15 May filing date from the 15 June modification date.
- An explicit unsupported campaign-year question and a question outside the approved coverage, both expected to abstain.
- A stale/expired evidence case expected to abstain when the fixture as-of date is after validity.
- A land clarification case only if the approved corpus contains genuinely different land applicability for the question; otherwise retain mixed-land behavior in the already accepted `land_safety_evaluation` suite rather than manufacture a PAC clarification case.

Each case records `reviewed_by`/`reviewed_on`, expected response status, and for an answer the exact supporting source and passage IDs. Critical facts such as a deadline are represented by literal expected strings linked to a passage and independently checked. The evaluator does not determine whether those strings are legally correct; the independent corpus reviewer does.

## Implementation plan and tasks

1. Define strict `pac-answer-eval-v1` JSON Schema and matching dependency-free validator for unique IDs, exact keys, case shape, status-specific requirements, land-context fields, reviewer metadata, and existing source/passage references.
2. Add a small case data set only after `backend_pac_corpus` is independently accepted. Keep fixture examples synthetic and clearly separated from canonical evaluation cases.
3. Add a deterministic evaluator that calls the same local `/ask` orchestration with explicit `as_of`, active campaign, and `k`; do not duplicate retrieval, generation, abstention, or land-safety policies.
4. Map answer sources to canonical source IDs by URL and to passage IDs by URL/location/excerpt equality or an equally strict deterministic match. Ambiguous matches are reported as unmatched; do not guess.
5. Calculate and print case-level state/source/fact/clarification outcomes and aggregate counts/rates. Do not print complete question, land context, or passage content in routine logs.
6. Keep state mismatch, missed coverage, and low rates report-only. Return nonzero only for malformed evaluation/corpus input, broken contract response, unsafe verifier behavior, or runtime configuration failure.
7. Add tests for deterministic output, state confusion, false answers, wrong-source citations, missing critical literal, mismatched land IDs, out-of-scope campaign, stale corpus, and malformed/unknown case references.
8. Document invocation, metrics and limitations; record the first actual run and explicit set size/as-of/campaign in `PROGRESS.md` without an unsupported quality conclusion.

## Verification plan and evidence

- Validate the case JSON against the schema and executable validator.
- Run the evaluator twice with the same canonical source/passages, case file, `--active-campaign`, `--as-of`, and `--k`; reports must be byte-identical.
- Run focused evaluator tests through `./scripts/init.sh --backend-tests tests/test_pac_answer_eval.py`.
- Capture case count and the output values for state agreement, expected-answer coverage, unexpected answers, citation-source agreement, critical facts, and clarification IDs.
- Confirm that a poor state or coverage score is visible but does not produce a false “pass”; verify integrity failures return nonzero.
- Report exact covered question categories and known gaps. Do not compare synthetic fixtures with the real-source report or claim legal correctness from any metric.

## Validator checklist

- [ ] Each canonical case is independently reviewed and references approved source and passage IDs.
- [ ] Every in-scope question category and important coverage boundary is represented; no invented legal case or claim is added.
- [ ] The evaluator exercises the same local `/ask` path, campaign setting, as-of date, and accepted pipeline as runtime.
- [ ] Response source mapping is deterministic and rejects ambiguous or unapproved citations.
- [ ] Critical facts are exact, passage-linked checks; the evaluator makes no semantic/legal judgment.
- [ ] Expected-state, citation, critical-fact, and land-choice results are reported per case and in aggregate.
- [ ] Out-of-scope, stale, and historical-campaign cases are explicit expected abstentions, never omitted from denominators.
- [ ] Quality mismatches are report-only with no invented threshold; structural/contract/grounding failures remain nonzero integrity failures.
- [ ] Reports and logs do not store raw user questions, land data, or full passage content.
- [ ] The measured report states its sample size, campaign, as-of date, covered topics, gaps, and synthetic-vs-real status honestly.
