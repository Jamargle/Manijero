# `knowledge_update_review_pr` acceptance

## Verdict

**Accepted** on 2026-10-27 after one validator `revise` cycle and independent re-validation.

- Spec: [`knowledge_update_review_pr.md`](../specs/knowledge_update_review_pr.md)
- Evidence: [`knowledge_update_review_pr.appendix.md`](../archive/specs/knowledge_update_review_pr.appendix.md)
- Reviewed scope: `backend/app/review_package.py`, `backend/scripts/knowledge_review.py`, `backend/tests/test_knowledge_update_review.py`, the public `candidate_admission_issue()` seam in `backend/app/document_ingestion.py`, `knowledge/knowledge-update-review.schema.json`, `knowledge/knowledge-update-review-decisions.schema.json`, plus `backend/README.md`, `knowledge/README.md`, `ARCHITECTURE.md`, `CONSTRAINTS.md`, `PROGRESS.md`, `docs/risks-and-open-questions.md`, this feature's spec/appendix, and the `feature_list.json` status line. `feature_list.json` still says `passing`; persisting `accepted` stays with the orchestrator.

## Independent verification

- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature knowledge_update_review_pr` — passed, `774 passed, 1 warning in 10.86s` (one unrelated Starlette/httpx deprecation warning). The published focused block (`--backend-tests`) is accurate and still runs.
- `cd backend && .venv/bin/python -m pytest tests/test_knowledge_update_review.py -q` — `46 passed in 1.18s`; the file contains 46 focused test functions.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --fast` — passed, all nine offline checks, `Fast tier passed.`
- `./scripts/init.sh --verify` was not run: the change is backend/knowledge-documentation only and does not touch the shared/Android/Desktop surface, packaging, the HTTP contract, or the answer path; focused plus fast cover the changed code.

### Independent CLI probes

All probes used temporary copies of `backend/tests/fixtures/change_impact` or copies of the repository's `knowledge/source_catalog.json`, `knowledge/passages.json`, and `knowledge/pac_answer_eval.json`; no repository canonical file was modified.

- **Coherent removal with `--cases`:** `prepare` exited `1` with `proposal_evaluation_impact:orphaned_cases:fixture-caso-plazo-rd` (`11 passed / 1 failed / 2 report-only`), `approval_blocked` on `decide`, `approval_required` on `merge`, and unchanged catalog/passages/cases hashes; no `merge.json` was written.
- **Normal addition:** `prepare` exited `0` with package id `a1161b1ad49b3a1fb79ad53c9746e0de32d98abcd1e8673d7c0feb5dadbef9d1`, `ready_for_review`, `12 passed / 0 failed / 2 report-only`. A requested human approval on `2099-10-27` exited `0`; `merge` exited `0` with `canonical_changes_applied: true`, `reindex_required: true`, `reindexed: false`, `released: false`.
- **Approval identity and sequencing:** `github-actions[bot]` → `reviewer_not_human`; the proposal author → `self_approval`; a non-requested human → `reviewer_not_requested`; merge before any decision → `approval_required`; a second merge and a decision after merge → `already_merged`.
- **No-op on repository field-order files:** the package's `proposal.before == proposal.after`; `merge` exited `0`; both canonical files remained byte-identical, and the cases file was untouched.
- **One-entry addition on repository field-order files:** source count changed from 4 to 5; every pre-existing source remained identical, the first entry's key order was preserved, only `fixture-rd-2200-2099` was appended, and `merge` exited `0`.

## Repair items closed

1. **After-state evaluation gate (closed).** `prepare` loads and validates the current case set, evaluates orphaned/rewritten cases against the after-state, records `proposal.evaluation` (`cases_sha256`, `case_count`, `validated_against: after`, orphaned/rewritten ids), and blocks readiness with `orphaned_cases:<ids>`. `merge` requires the digest-bound case file, rejects `evaluation_cases_drift`, and revalidates the after-state before writing. Tests cover removal, no-case changes, digest changes, and rewritten cases. The removal rule is documented in the appendix, `backend/README.md`, `knowledge/README.md`, `PROGRESS.md`, and `CONSTRAINTS.md`.
2. **Order-preserving canonical serialization (closed).** `_ordered_json` is used for after hashes and merge writes; sorted canonical JSON remains for package/decision/merge identities. Regression tests cover a no-op package on the real field-order files and a one-entry addition; both were independently reproduced above.
3. **Truthful provenance coverage (closed).** `proposal_provenance` checks catalog additions/updates/removals and passage additions/updates/removals for exactly one source-to-candidate link, rejects links to unselected candidates, and reports `removals_only` / `passages_only` instead of claiming there were no catalog changes. Tests cover passage-only, removal-only, unselected-candidate, and no-op details.
4. **Automation identity and requested-reviewer gate (closed).** The denial list covers `ci`, `cd`, `ci/cd`, `actions`, `github-actions`, `workflow`, `pipeline`, `automation-*`, `service-account*`, `preparer`, and bot names; approval additionally requires the reviewer to be in the package's `requested_reviewers`. Tests and CLI probes cover bot, author, and non-requested approvals. Docs now say this is a known-name denial list, not authentication.
5. **Durable docs and schemas (closed).** The two schemas are registered in `knowledge/README.md`; `backend/README.md` documents prepare/decide/merge, exit codes, digests, case handling, and limits; `ARCHITECTURE.md`, `CONSTRAINTS.md`, `PROGRESS.md`, `docs/risks-and-open-questions.md`, and the appendix were updated consistently.

## Re-checked acceptance scenarios and checklist

- **Prepared review package:** the generated package and `REVIEW.md` contain source URL/issuer, observation/retrieval times, original/extracted hashes and locations, old/new text excerpts, proposed catalog/passage changes, affected sources/passages/cases, automated checks, unresolved questions, and explicit limits; the package is marked draft and never auto-merges. Source text is fenced as untrusted data.
- **Human approval gate:** only an explicit approval by a requested named human other than the author with passing readiness/checks permits merge; bot/CI/label/hash evidence alone is refused. Rejection and request-changes leave canonical bytes unchanged.
- **Uncertain or unsafe candidate:** tests cover missing provenance, unsafe URL, extraction digest mismatch and `U+FFFD` uncertainty, failed ingestion, unknown validity/applicability, an inferred `"unknown"` literal, ambiguous impact without/with a matching resolution, mismatched resolutions, and invalid inputs. These become `needs_human_attention` and cannot be approved.
- **Rejection and rework:** rejection/request-changes preserve canonical knowledge; a revised proposal produces a new package id with fresh checks and no inherited approval. The shape and evidence records remain inspectable.
- **Validator checklist:** all checklist items are covered by the tests and probes above, with the notes recorded below.

## Residual limits and validator notes (non-blocking)

The appendix's observed limits are accurate: the package is a local draft rather than a hosted PR; hosting-platform merge protection is not configured; reviewer identities and decisions are plain local records and are not authenticated; direct filesystem writes can bypass the command; original-byte comparison is unavailable when the quarantine copy is gone; display is bounded; the two canonical files are written sequentially, not as one transaction; only synthetic fixtures exercise the flow; no live published update exists; and no legal-coverage or answer-quality claim follows.

- **Empty case sets are valid input.** A well-formed `pac-answer-eval-v1` file with `cases: []` is accepted with `case_count: 0` and `validated_against_after` (the repository case schema and `knowledge/README.md` allow an empty array). The package therefore proves only that the supplied case references survive; it does not establish case coverage. The real repository case set has six cases, and a reviewer should use it. A later documentation touch could state this explicitly, or the feature could require a non-empty case set for corpus changes.
- **Field-order wording is strongest for untouched entries.** A no-op and a one-entry addition preserve bytes/key order as claimed. Code inspection shows that the update path replaces a proposed entry with the package's sorted proposal object, so an updated entry's own key order can be sorted; `CONSTRAINTS.md` and the README/limit sentence should either say "untouched entries" or preserve updated-entry key order if that stronger guarantee is intended. This does not change JSON semantics or any tested acceptance scenario.
- The package's success output includes the operator workspace path (`package_dir`); refusal output is fixed-name only. This is operator-facing, not a log leak.

## Security assessment

Feature-scoped review found no blocking security issue. The command is offline, standard-library only, and introduces no credentials, network calls, secrets, or new dependencies. It validates ingestion state, catalog, passages, evaluation cases, proposal/package/decision shapes, and quarantine paths before writing; rejects workspaces inside the repository `knowledge/` directory; renders source text only as fenced evidence; and emits fixed failure names on the CLI. The approval gate is explicitly described as a procedural local control, not authentication: a local operator can still edit the workspace or canonical files directly, and hosting merge protection is not present. That limitation is recorded in `docs/risks-and-open-questions.md`, `PROGRESS.md`, `backend/README.md`, and the appendix.

## Documentation and harness state

`ARCHITECTURE.md`, `CONSTRAINTS.md`, `PROGRESS.md`, `backend/README.md`, `knowledge/README.md`, `docs/risks-and-open-questions.md`, the appendix, and the two schemas were updated in the right artifacts. `AGENTS.md` remained short and router-like. No commit was created: `HEAD` is still `68b544b`; the only feature status changed is `knowledge_update_review_pr` (`not_started` → `passing`); `.local-run.log` remains unrelated and untracked.

## Orchestrator acceptance record

Persisted after this verdict: `feature_list.json` status changed from `passing` to `accepted`, and one pointer line was added to `docs/progress/session-log.md`. The non-blocking field-order note above was then applied as a documentation-only clarification: `CONSTRAINTS.md`, `ARCHITECTURE.md`, `PROGRESS.md`, `backend/README.md`, `knowledge/README.md`, and the appendix now claim order preservation only for entries the proposal does not rewrite. No code or test result changed; `./scripts/init.sh --feature knowledge_update_review_pr` re-ran clean (`774 passed`).
