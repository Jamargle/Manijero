# Feature specification: `backend_answer_evaluation`

## Source metadata

- **Feature:** `backend_answer_evaluation` — Measure the reviewed PAC answer slice (`evaluation`).
- **Depends on:** `backend_ask_endpoint`, `backend_pac_corpus`, `backend_campaign_validity`, and `land_safety_evaluation` (implemented and accepted before this feature).
- **Source behavior:** A deterministic offline evaluator runs a small independently reviewed set of PAC questions through the local `/ask` pipeline and reports answer-state, citation, critical-fact, and clarification results.
- **Source verification:** Validate the case artifact; run the evaluator twice with fixed campaign/date inputs; confirm stable report output and report-only quality metrics.
- **Source note:** Cases are source-anchored to the approved PAC corpus. No threshold or quality claim is accepted until the first measured real-source baseline is reviewed.

## Goal

Measure whether the local extractive `/ask` path covers the independently reviewed Andalusia 2026 PAC question slice, cites the intended reviewed material, abstains outside coverage, and respects land clarification. Produce a reproducible report without inventing a numeric pass threshold.

## Non-goals

- A release-quality guarantee, legal correctness certificate, public leaderboard, hard retrieval/answer threshold, or claim of coverage beyond the cases listed.
- Hosted LLM judges, embeddings, external APIs, vector search, generation-provider comparison, telemetry, user-question logging, or production monitoring.
- Replacing `backend/scripts/evaluate_land_safety.py` or changing the accepted grounding, abstention, citation, or clarification policies.
- Expanding the corpus or its legal scope from evaluation failures; changes to approved source content remain a separately reviewed corpus update.

## Job story

When the reviewed corpus and local answer route are connected, I want a repeatable report against source-anchored questions, so that coverage gaps and unsafe state/citation mismatches are visible before anyone describes this MVP as useful for real PAC questions.

## Acceptance scenarios

### Evaluate reviewed source-anchored questions end to end

Given a valid independently reviewed case set and the approved canonical corpus, when the evaluator sends each case through the same local `/ask` route and campaign/date policy used by the service, then it records the expected and actual response state, eligible citation sources, expected passage match, critical-fact checks, and land-choice IDs by case ID.

### Report coverage and safety without a quality gate

Given completed cases, when the report is printed, then it includes case count, expected-state agreement, expected-answer coverage, unexpected-answer count for cases expected to abstain or clarify, source/citation agreement, critical-fact outcomes, and land-clarification outcomes. Quality mismatches are reported, not hidden and not compared with an invented target.

### Enforce structural and grounding invariants

Given malformed cases, unknown source/passage IDs, invalid campaign data, contract-invalid responses, or an answer that fails the code-owned grounding verifier, when evaluation runs, then it reports a clear case identifier and returns a nonzero error status without exposing a private question or raw corpus text. These implementation-integrity failures are not quality thresholds.

### Evaluate out-of-scope, stale, and land-aware cases

Given cases for an unsupported campaign year, stale evidence, a question outside the reviewed topic slice, and a mixed-land clarification condition where applicable, when evaluated, then expected abstention/clarification is counted separately from answered coverage. Clarification IDs must be a subset of the request fixture IDs, and no unsupported case is silently dropped.

### Produce deterministic, report-only results

Given fixed case data, corpus, `--active-campaign`, `--as-of`, and retrieval `--k`, when the evaluator is run twice, then both reports are byte-identical. Changing a case outcome changes the report but does not fail solely for a low coverage score or a state mismatch.

## Technical approach

- Add a strict versioned `knowledge/pac_answer_eval.schema.json` and canonical `knowledge/pac_answer_eval.json` case set. Each case has a stable ID, question, contract-shaped land context, expected status, expected source IDs/passage IDs when applicable, optional exact critical-fact strings, and independent review metadata. Cases contain no real personal or land data.
- Require `expected_status` to be one of `answered`, `abstained`, or `needs_land_clarification`. Answered cases identify allowed catalog sources and supporting passage IDs. Abstention cases state no expected source. Clarification cases list only synthetic land IDs supplied by the case request.
- Add a standard-library loader/validator and `backend/scripts/evaluate_pac_answers.py`. It invokes the in-process FastAPI/TestClient path or a shared request service boundary so evaluation and HTTP behavior use the same orchestration, campaign configuration, and date.
- Match returned citations to canonical catalog URLs and passage fields; the public response does not expose internal passage IDs. Record a passage match only when the cited URL, location, and excerpt map to the expected approved passage(s).
- Check optional critical facts conservatively with exact strings recorded against source-reviewed passages. This is a review aid, not a semantic or legal judge. Report missing/extra outcome facts; do not paraphrase or synthesize legal facts in the evaluator.
- Report deterministic case-level outcomes and aggregate counts/rates: expected-state agreement, expected-answer coverage, unexpected answered cases, citation-source agreement, critical-fact matches, and clarification-ID correctness. Do not invent thresholds or calculate a single quality score that hides false answers.
- Quality mismatches remain report-only. Invalid data, non-contract responses, grounding-verifier violations, unknown source/passage references, and runtime configuration failures produce nonzero execution status. Never persist requests or response traces.
- Include explicit as-of and active-campaign inputs in the CLI; no system clock, network, external model, or host service is needed.

## Expected file changes

- `knowledge/pac_answer_eval.schema.json` (new) — strict versioned format for reviewed end-to-end cases.
- `knowledge/pac_answer_eval.json` (new) — small source-anchored, independently reviewed case set for the published coverage and explicit gaps.
- `backend/app/answer_eval.py` (new) — strict loader and deterministic case/report calculation, reusing the accepted endpoint and pipeline.
- `backend/scripts/evaluate_pac_answers.py` (new) — report-only CLI with explicit corpus, case, date, campaign, and retrieval inputs.
- `backend/tests/test_pac_answer_eval.py` (new) and `backend/tests/fixtures/pac_answer_eval/` (new) — validator, determinism, false-answer, citation, critical-fact, clarification, campaign mismatch, and malformed-input tests.
- `knowledge/README.md`, `backend/README.md`, `PROGRESS.md`, and `docs/risks-and-open-questions.md` — explain what the report measures, its reviewed coverage, and why no threshold is claimed.
- `scripts/init.sh` — add the evaluator command to `--fast` only if its runtime remains offline and small; otherwise publish it as the focused feature command and document why it is not part of `--fast`.

## Visual design impact

None. The evaluation harness is offline and adds no UI or user-facing copy.

## Durable documentation impact

- `knowledge/pac_answer_eval.schema.json` and `knowledge/README.md`: define case format, review gate, and coverage boundary.
- `backend/scripts/evaluate_pac_answers.py` and `backend/README.md`: define invocation, metrics, exit behavior, and report-only limits.
- `scripts/init.sh`: update only if the evaluator qualifies for the shared fast tier; focused command must remain explicit either way.
- `PROGRESS.md`: record the measured run, counts, date/campaign inputs, and exact coverage/gaps; never state that the score proves legal correctness.
- `docs/risks-and-open-questions.md`: revisit metric thresholds only after reviewing the real baseline and user coverage.
- `CONSTRAINTS.md`: no change unless implementation adds a new durable MUST/MUST NOT rule.
- `docs/validations/backend_answer_evaluation.md`: create only during independent feature validation.

## Focused verification

`./scripts/init.sh --feature backend_answer_evaluation` runs the following after implementation. The evaluator itself reports quality outcomes without enforcing numeric targets.

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_pac_answer_eval.py
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-17 --k 5
```
<!-- verify:end -->

## Appendix

Repository research, case design, report semantics, implementation tasks, and the validator checklist are in [`backend_answer_evaluation.appendix.md`](backend_answer_evaluation.appendix.md).
