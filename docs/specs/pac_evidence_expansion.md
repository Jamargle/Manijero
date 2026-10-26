# Feature Spec: `pac_evidence_expansion`

## Source metadata

- **Feature:** `pac_evidence_expansion` — Strengthen evidence within the reviewed PAC scope (`evaluation`).
- **Status at planning:** `not_started`; depends on `backend_answer_evaluation`, `backend_pac_corpus`, and `backend_citation_hardening`.
- **Source behavior:** Resolve the known citation and critical-fact misses, expand the source-anchored evaluation within the current three-topic Andalusia PAC 2026 corpus, and publish exact results and limitations.
- **Feature-list verification:** Each current miss has a reviewed resolution, the expanded case set covers the documented scope/boundaries, and repeated runs with fixed inputs are deterministic.
- **Feature-list note:** Review is by the project author only. Results must not be described as independent legal validation or broad answer-quality proof.

## Goal and boundaries

Improve the evidence behind any future description of the current answer slice. Keep the corpus and evaluation within the current approved topics; make known misses visible and resolved, and state precisely what the resulting evidence does and does not support.

**In scope:** trace each known citation/critical-fact miss to source, retrieval, generation, verifier, or evaluator behavior; fix or explicitly retain as a blocking gap; add source-anchored cases across supported topics and abstention/clarification boundaries; record author review, campaign/date, case count, results, and limitations.

**Non-goals:** expanding legal topics/corpus, user studies, an independent legal reviewer, an LLM judge, a numeric quality threshold, production legal assurance, pilot/demo/defense work, or claims beyond the measured cases.

## Job story

When I describe what the answer service can do, I want a transparent, source-linked evaluation with known misses addressed, so I do not imply legal validation or broad quality from a small sample.

## Acceptance scenarios

### Resolve known misses

Given the current evaluation identifies citation or critical-fact misses, when the expanded evaluator runs, then each miss has a source-reviewed correction or remains explicitly reported as an unresolved blocker; no miss is silently removed from the case set.

### Cover current scope

Given the three approved topic boundaries in `knowledge/pac_coverage.md`, when cases are expanded, then supported variants, boundary cases, abstentions, and applicable land clarifications are represented without introducing unsupported legal topics.

### Author review and honest claims

Given the author is the only reviewer, when the report and coverage description are published, then they say author-reviewed, disclose the absence of independent legal review, list cases/topics and omissions, and do not claim legal correctness or broad user-question quality.

### Deterministic report

Given fixed corpus, campaign, date, and retrieval inputs, when evaluation is run twice, then the reports are identical and quality outcomes remain report-only rather than compared to an invented threshold.

### No unsupported answer reaches the report as evidence

Given an answer violates the code-owned grounding/citation contract, when a case is evaluated, then the evaluator reports the mismatch and never counts it as a supported success.

## Technical approach

Use the existing canonical corpus and `backend/scripts/evaluate_pac_answers.py`. Keep cases synthetic and source-anchored; record expected response status, source and passage, relevant critical facts, and author review metadata. Build a coverage matrix from the three declared topics and known evaluation misses, not from guessed population frequency. Fix implementation or source errors through their owning contracts, rerun the same cases, and publish exact aggregate and case-level results. Any residual miss is visible. No hard numeric pass gate is added.

## Expected file changes

- `knowledge/pac_answer_eval.json` and its schema if new cases require additional valid metadata.
- Backend evaluator/report tests and only the owning generation/retrieval code if a known defect is confirmed.
- `knowledge/pac_coverage.md`, `knowledge/README.md`, `backend/README.md`, `PROGRESS.md`, and this feature's evidence appendix.
- `docs/risks-and-open-questions.md` if measured limits or blockers change.

## Visual design impact

None. No user-facing UI or copy changes.

## Durable documentation impact

- `ARCHITECTURE.md`: not needed unless evaluation changes runtime boundaries.
- `CONSTRAINTS.md`: preserve report-only, source-grounded, no-overclaim rules; add no quality threshold.
- `AGENTS.md`: not needed.
- Coverage and evaluation docs: update exact measured boundary and author-review limitation.

## Focused verification

<!-- verify:start -->
```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests tests/test_pac_answer_eval.py
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-26 --k 5
```
<!-- verify:end -->

## Appendix

See [`pac_evidence_expansion.appendix.md`](pac_evidence_expansion.appendix.md).
