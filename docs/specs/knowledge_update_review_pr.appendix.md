# `knowledge_update_review_pr` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory is Git-tracked and requires a named reviewer other than the author. `official_source_monitoring` currently saves monitoring snapshots; `official_source_discovery`, `official_document_candidate_ingestion`, `legal_change_impact_analysis`, and this PR workflow remain planned. Monitoring state is not itself an approval queue. Current source set and answer-evaluation limits are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

## Implementation plan

1. Define a versioned review-package manifest that links a quarantined candidate to its source registry, official URL, observation/retrieval time, original-byte hash, extraction version, and extracted page/section locations.
2. Generate a draft branch and pull request with bounded, coherent changes. Include the original document or a durable review artifact link, exact old/new text diff, proposed catalog/passage changes, unknown fields left absent, affected answer/evaluation report, and automated check results.
3. Assign a named human reviewer other than the author or automation identity. Configure required PR checks and repository merge protection. Prevent direct writes to canonical knowledge; if merge protections cannot be configured, make the controlled merge path independently verify explicit PR approval before writing.
4. Provide reviewer actions: approve, request changes, or reject. Preserve decisions and comments in PR history; on changes, rerun validators and impact checks. Rejected candidates stay quarantined and do not enter retrieval.
5. After an approved merge, trigger the separate reindex/release process. Do not deploy/reindex unmerged proposals, and do not make PR merge imply that the content is legally comprehensive.
6. Add deterministic tests for incomplete provenance, unsafe source, extraction mismatch, unknown validity/applicability, evaluation failures, missing/self approval, review requested, rejection, and successful approval followed by checks. Test that every non-approved path leaves canonical artifacts/index unchanged.
7. Document the operator and reviewer procedure in `knowledge/README.md` and capture exact evidence and hosting-platform limits.

## Verification plan

- Run the feature-focused backend tests for review package generation, schema/impact checks, reviewer identity and approval gating, and unchanged canonical artifacts on rejected paths.
- Run the full backend suite and the offline evaluators that the review package reports; distinguish pass/fail gates from report-only metrics.
- Exercise a disposable test PR/fixture through draft → request changes → revised checks → approval → merge-ready state. Verify the author cannot satisfy the independent reviewer gate.
- Confirm the normal `/ask` route still reads only canonical approved artifacts; a draft branch or quarantined candidate is not visible to retrieval.

## Evidence to capture

- A synthetic sample review package and PR body showing source evidence, diffs, impact, unknowns, check results, and the explicit human decision.
- Successful and rejected/request-changes PR flow evidence, including reviewer identity and required-check status.
- Tests proving no auto-merge, no self-approval, no canonical mutation before approval, and no reindex/release before merge.
- Exact backend/evaluator commands and results, plus hosting provider/repository settings needed for merge protection.
- Open limitations such as evidence retention, large-document display, unsupported source formats, and review turnaround; no claim of legal completeness.

## Validator checklist

- [ ] Draft PR contains provenance, hashes, source/extracted text locations, a readable version diff, proposed canonical changes, affected-answer/evaluation results, and machine-check outcomes.
- [ ] Reviewer can approve, request changes, or reject; decision, identity, and date are preserved.
- [ ] Required checks pass and an identified human other than the PR author approves before merge; bot/label/CI status cannot substitute.
- [ ] Missing provenance, extraction issues, unknown values, ambiguity, and failed checks remain visible and block merge readiness.
- [ ] Rejection/request changes leaves canonical catalog, passages, and retrieval index unchanged; revised proposals rerun checks.
- [ ] Merge is the only path that changes canonical knowledge; reindex/release is a separate post-merge operation.
- [ ] Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- [ ] Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- [ ] Evidence and docs distinguish human approval of this bounded update from legal completeness or answer-quality certification.

## Feature evidence

Not implemented. No implementation or verification evidence exists yet.
