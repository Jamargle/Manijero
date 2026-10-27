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

- [ ] Draft PR contains provenance, hashes, source/extracted text locations, a readable version diff, proposed canonical changes, affected-answer/evaluation results, the after-state evaluation-case gate, and machine-check outcomes.
- [ ] Reviewer can approve, request changes, or reject; decision, identity, and date are preserved.
- [ ] Required checks pass and a named requested human other than the PR author approves before merge; known automation identities, bot/label/CI status, and an unrequested approver cannot substitute.
- [ ] A corpus change supplies the reviewed evaluation case set; the after-state is validated, orphaned case ids block readiness, and merge requires the same digest-bound case file.
- [ ] Provenance covers added/updated catalog entries and removals, and passage additions/updates/removals, without claiming coverage that was not checked.
- [ ] Missing provenance, extraction issues, unknown values, ambiguity, and failed checks remain visible and block merge readiness.
- [ ] Rejection/request changes leaves canonical catalog, passages, and retrieval index unchanged; revised proposals rerun checks.
- [ ] Merge is the only path that changes canonical knowledge; reindex/release is a separate post-merge operation.
- [ ] Canonical after hashes and writes preserve the field order of untouched entries: a no-op package merges byte-identically, and a one-entry addition changes only the appended entry; a newly added or rewritten entry may take the proposal's serialization.
- [ ] Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- [ ] Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- [ ] Evidence and docs distinguish human approval of this bounded update from legal completeness or answer-quality certification.

## Feature evidence

Implemented as a deterministic local review-package and controlled-merge flow. No
Git or hosting-platform API is called; the "pull request" is an inspectable local
draft directory.

**Implementation**

- `backend/app/review_package.py` — `prepare`, `record_decision`, `merge`, the
  proposal/package/decision validators, the after-state evaluation-case gate,
  the order-preserving canonical serializer, and the bounded
  `REVIEW.md`/`DECISION.md` renderers. `prepare`/`decide` are read-only over
  canonical knowledge; `merge` is the only canonical writer and never reindexes
  or releases.
- `backend/scripts/knowledge_review.py` — operator CLI (`prepare`, `decide`,
  `merge`). Refusals print only a fixed `{"error": "<name>"}` and exit `2`;
  `prepare` exits `1` when the draft needs human attention.
- `backend/app/document_ingestion.py` — exposes the existing URL admission rule
  as public `candidate_admission_issue()` so review preparation reuses the host
  allowlist instead of duplicating it.
- `knowledge/knowledge-update-review.schema.json` — `knowledge-update-review-package-v1`.
- `knowledge/knowledge-update-review-decisions.schema.json` —
  `knowledge-update-review-decisions-v1`.
- `backend/tests/test_knowledge_update_review.py` — 46 focused tests and helpers.

**Contracts.** A proposal is `knowledge-update-proposal-v1`: `summary`, 1–20
candidate ids, optional per-candidate `resolution`/`unknown_fields`, catalog and
passage `{add,update,remove}` sections, optional `author`, source→candidate
`links` for every catalog addition/update/removal and passage change, and
`unresolved_questions`. The package is
`knowledge-update-review-package-v1` (readable schema
`knowledge/knowledge-update-review.schema.json`); `proposal.evaluation` binds
the reviewed case digest, count, post-validation state, orphaned case ids, and
rewritten case ids. After hashes and merge writes use an insertion-order
serializer so a no-op package is byte-stable. Decision history is
`knowledge-update-review-decisions-v1` and binds the package id plus a checks
digest. Merge is recorded as `knowledge-update-merge-v1`.

**Verification (actual commands and results)**

1. Focused feature tests, from `backend/`:
   `python3 -m pytest tests/test_knowledge_update_review.py -q` →
   `46 passed in 1.18s`.
2. Published focused verification, from the repository root:
   `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature knowledge_update_review_pr`
   → `774 passed, 1 warning in 10.84s` (the same backend suite the
   `--backend-tests` block runs).
3. Fast tier:
   `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` →
   all nine offline checks passed; `Fast tier passed.`
4. Disposable CLI flow over a copy of the synthetic change-impact fixture
   (temporary workspace, canonical repository files untouched):
   - coherent removal of `fixture-rd-2077-2099` and
     `fixture-pasaje-rd-2077-plazo` with `--cases` → `prepare` exit `1`,
     `proposal_evaluation_impact:orphaned_cases:fixture-caso-plazo-rd`;
     approval → exit `2`, `approval_blocked`; `merge` → exit `2`,
     `approval_required`; catalog, passages, and cases hashes unchanged.
   - normal addition → `prepare` exit `0`, package
     `a1161b1ad49b3a1fb79ad53c9746e0de32d98abcd1e8673d7c0feb5dadbef9d1`,
     `merge_readiness: ready_for_review`, `12 passed / 0 failed / 2 report-only`;
     named-human approval on `2099-10-27` → exit `0`; `merge` → exit `0`,
     `canonical_changes_applied: true`, `reindex_required: true`,
     `reindexed: false`, `released: false`.
   - bot approval → exit `2`, `reviewer_not_human`; a non-requested human
     approval → exit `2`, `reviewer_not_requested`; author approval → exit `2`,
     `self_approval`; merge before any decision → exit `2`, `approval_required`.
   - second merge and a decision after merge → exit `2`, `already_merged`.
5. Serialization probe on copies of the real reviewed files:
   - no-op proposal with `--cases` → `before == after`, `merge` exit `0`, and
     both canonical files byte-identical.
   - one-entry addition → existing entries unchanged, first-entry key order
     preserved, only `fixture-rd-2200-2099` appended; `merge` exit `0`.
6. Tests cover the blocking and recovery cases: missing provenance, unsafe source
   URL, extraction digest mismatch and `U+FFFD` uncertainty, failed ingestion,
   unknown validity/applicability, an inferred `"unknown"` literal, ambiguous
   impact without and with a matching resolution note, mismatched resolution,
   unlinked/provenance-mismatched catalog and passage changes, removals without
   a link, links to unselected candidates, bot/author/non-requested approvals,
   stale checks, orphaned/rewritten/absent evaluation cases, changed case-set
   digests at merge, request-changes/rejection leaving canonical bytes unchanged,
   revised package as a new id with no inherited approval, canonical drift,
   tampered package, catalog expiry at the approval date, draft invisibility to
   retrieval, no-op byte stability, field-order preservation, invalid inputs,
   and the CLI flows.

**Observed limits.** The fixture has no preserved original bytes, so
`candidate_original_bytes` is `report_only / original_bytes_unavailable` and
stays a visible reviewer question; only a human can compare the extraction with
the official original. A proposal that changes the reviewed corpus requires the
reviewed evaluation case set: preparation validates the after-state and blocks
readiness for orphaned case ids, and without cases any change is blocked. A
no-op proposal is allowed without cases. Merge requires the same digest-bound
case file and revalidates it, so later edits cannot bypass the gate. Cases are
checked for references only; they are not re-run, and the package never retires
or rewrites a case. Affected and rewritten cases remain `report_only` once the
after-state reference check passes. The workspace is a local draft, not a hosted
PR: hosting merge protection is not configured or enforced, and direct
filesystem writes can bypass the controlled command. Reviewer identity and
decisions are plain local records, not cryptographic signatures; the commands
refuse known automation identities, self-approval, and approvals outside
`requested_reviewers`, but identities are not authenticated and cannot stop a
malicious operator. Merge records `reindex_required: true` and leaves
reindex/release to the separate feature. The two canonical files are written
atomically one at a time, not as one transaction; a crash between writes can
leave an inconsistent pair that then refuses as `canonical_drift` and must be
restored from Git or re-merged. The field order of entries the proposal does not
rewrite is preserved and a no-op merge is byte-identical; a newly added or
rewritten entry follows the package's sorted proposal JSON, so its own keys are
sorted while untouched entries keep their reviewed order. Review display is
bounded (40 change entries, 400-character values, 50 signals per candidate),
evidence is not garbage-collected, and only synthetic fixtures exercise the
flow. No real published update, legal-coverage claim, or answer-quality
certification exists.

**Post-acceptance clarification (documentation only).** The acceptance record
notes that an updated entry can take the proposal's sorted serialization. The
orchestrator clarified the field-order wording in `CONSTRAINTS.md`,
`ARCHITECTURE.md`, `PROGRESS.md`, both READMEs, and this appendix so it claims
order preservation only for entries the proposal does not rewrite. No code or
verification result changed.
