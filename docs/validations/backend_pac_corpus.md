# Validation: `backend_pac_corpus`

**Verdict: accept**  
**Validated:** 2026-10-18  
**Spec:** [backend_pac_corpus](../specs/backend_pac_corpus.md)  
**Independent reviewer:** Diego (approved source copies, passages, scope, and exclusions on 2026-10-17)

## Acceptance evidence

- The catalog contains four official 2026 PAC sources with approved provenance, reviewer, review dates, and SHA-256 digests. The four downloaded PDF hashes independently match the catalog values.
- The passage set contains four literal, source-located passages supporting only the three published procedural topics. It preserves the electronic-access exception and distinguishes the 15 May filing deadline from the 15 June modification deadline.
- `knowledge/pac_coverage.md` states the reviewer, review date, supported scope, and exclusions. No eligibility or aid-amount claims are made.
- The appendix records source chronology, reviewer approval, and implementation evidence; `PROGRESS.md`, the risk register, and feature status reflect the populated corpus.

## Checks run

- `python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-18` — passed; 4 sources.
- SHA-256 comparison of all four downloaded PDF files against catalog values — passed.
- `PYTHONPATH=backend python3 -c "import backend.tests.test_pac_corpus as test_mod; test_mod.test_canonical_artifacts_are_valid_and_have_approved_coverage(); test_mod.test_approved_topics_and_exclusions()"` — passed both invariant checks.
- `./scripts/init.sh --feature backend_pac_corpus` — catalog step passed, but its pytest step could not run in the default environment because pytest was not installed. The pytest target was run in an isolated environment with backend requirements and pytest installed — passed (2 tests).

## Scope and safety

The catalog and passage validators are offline and validate format/policy, not legal authenticity or current legal advice. Independent source review and passage approval are recorded separately. The corpus excludes individual eligibility, amounts, penalties, appeals, monitoring adaptations, and other campaign years. No runtime retrieval, generation, API, or land behavior was changed.
