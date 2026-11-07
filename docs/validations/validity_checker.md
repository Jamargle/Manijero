# Validation: validity_checker

Verdict: accept (independent validator). No owner walkthrough: the owner decision of 2026-11-06 makes
the validator's accept final. A canonical merge still requires a named human reviewer under the
existing review rule; this record approves no corpus change.

Spec: [../specs/validity_checker.md](../specs/validity_checker.md) · Evidence:
[appendix](../specs/validity_checker.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature validity_checker`: 127 passed in 1.85s; the published focused block is accurate and unchanged.
- `--fast` not rerun: the diff is backend-additive (one module, CLI, schema, tests, docs) and the focused block already runs the affected catalog and change-impact regression files. The appendix records all 10 offline checks passing (backend 2069 passed, 5 skipped).
- `--verify` not applicable: no `shared/`, app, Gradle, contract, or packaging input changed.
- Independent CLI probes on the committed fixtures: two runs at `--as-of 2099-06-01` wrote byte-identical reports (`cmp` clean), 9 `Proposal:` lines, exit 1; `--report knowledge/validity-review.json` and `--report <catalog>` each exited 2 with `unsafe_report_path` and no file, leaving input bytes unchanged; a report with a mismatched catalog digest exited 2 with `impact_inputs_mismatch` and no file; `--as-of 2099-02-30` exited 2 with `invalid_as_of` and no file.
- `git status --porcelain knowledge/` was identical before and after the probes; only the README row and the new `validity-review.schema.json`.

## Scenario coverage

1. Expired `valid_until` → `expiry.state: expired`, retirement `expired_valid_until` with both passage ids, the valid source `in_force`, one `Proposal:` line per proposal plus `Result:`, exit 1 (`test_expired_source_becomes_a_review_required_retirement`, `test_valid_until_equal_to_as_of_stays_in_force`, `test_cli_result_lines_and_exit_codes`).
2. Machine-evident repeal retires only the source linked with `repeal_target`; ambiguous and negated candidates get review only (`ambiguous_signal`, plus `negated_signal`); validity and linked publication are reviews; an unmatched repeal is `unmatched_repeal_target`; amendment is ignored (`test_machine_evident_repeal_retires_only_the_linked_source`, `test_ambiguous_and_negated_signals_never_retire`, `test_machine_evident_validity_signal_does_not_change_expiry`, `test_machine_evident_amendment_is_not_consumed`, `test_linked_publication_signal_is_review_not_addition`).
3. Missing `valid_until`/`consolidated_url` stay `unknown` with `null`; a future publication gets `future_publication_date`; no date or consolidation value is inferred (`test_missing_valid_until_and_consolidated_url_stay_unknown`, `test_future_publication_date_is_review_required`).
4. Additions only for an unlinked, non-`approved_copy` machine-evident publication; a linked publication is a review; an unlinked `approved_copy` adds nothing; every proposal is `review.required: true`/`review.applied: false` (`test_publication_signal_proposes_addition_only_for_an_unlinked_candidate`, `test_retirement_lists_every_affected_passage`).
5. Invalid catalog, passage set, or impact report; digest mismatch; output inside `knowledge/` or equal to an input all exit 2 with one fixed failure `Result:` on stderr and nothing written (`test_invalid_inputs_and_digest_mismatch_write_nothing`, `test_report_path_equal_to_an_input_is_refused`, `test_report_path_inside_knowledge_is_refused`, `test_oversized_report_aborts_before_writing`; reproduced live).
6. Same inputs and `--as-of` give byte-identical canonical JSON carrying the three input digests and no timestamp; tests block sockets and assert the repo `knowledge/` tree and fixture bytes are unchanged; a fresh subprocess shows no answer-service, generation, embedding, model, or HTTP module import (`test_report_is_byte_identical_for_the_same_inputs_and_as_of`, `test_report_has_no_wall_clock_or_excerpt_and_matches_schema`, `test_checker_is_import_safe_and_offline`).

## Review

- Read-only: the only write is the review artifact (`write_report`, atomic replace); the module imports only stdlib plus `app.source_catalog` and `app.retrieval`. `knowledge/`, releases, the embedding index, and `/api/answer` are untouched; verified by tree digest and live `git status`.
- Containment is resolved-path based for the `knowledge/` root and every input, so traversal and symlink spellings of a forbidden output are refused; verified live, not only in the unit test.
- Input integrity is digest-bound: the report's `catalog_sha256`/`passages_sha256` must match the supplied bytes, and the report version and consumed signal/source shape are required; malformed or extra shapes abort `invalid_impact_report`.
- Fixed failures only (`invalid_as_of`, `invalid_catalog`, `invalid_passage_set`, `invalid_impact_report`, `impact_inputs_mismatch`, `candidate_count_exceeded`, `proposal_count_exceeded`, `unsafe_report_path`, `internal_error`); no paths, exception text, or document values reach stderr. Proposal lines print a catalog or hex candidate id and a whitespace-collapsed title, so no input can forge a second line.
- Security checklist: no secrets, no new dependency, synthetic fixtures, no network/auth surface, bounded counts (1,000 candidates, 5,000 proposals), and output only outside `knowledge/`.
- Docs: `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, `backend/README.md`, `knowledge/README.md`, and `docs/risks-and-open-questions.md` are accurate, updated once each, within budget; `AGENTS.md`, `DESIGN.md`, `CONTEXT.md`, and `docs/owner-guide.md` correctly unchanged.

## Remaining limits

- The checker validates the impact report's consumed shape, not the full `legal-change-impact-report-v1` schema; a producer-side defect (for example a non-`https` `publication_url`) could produce an artifact that fails `validity-review.schema.json`. Accepted reports come from the schema-validated analyzer, so this is defense-in-depth only.
- Scenario 6's release/index/answer-path immutability is guaranteed by the single write path and the import guard; the test digests the repo `knowledge/` tree and fixture inputs rather than a literal operator release/index root (none exists in the repository).
- Detection is only as good as the accepted impact report and reviewed dates: prose-only repeal, an unlinked source, or a missing `valid_until` stays unknown, and precision/recall is unmeasured. The artifact states these limits itself.
- No live run against a real repeal, expiry, or consolidation change; synthetic fixtures only. There is no BOE consolidation-state field, so absent consolidation is `unknown`, never "not consolidated".
- `source_validity.exit_code` is unused by the CLI, which repeats the same expression; cosmetic only.

## Handoff

- The acceptance record is the validator's only write. The orchestrator should still set `validity_checker` to `accepted` in `feature_list.json` and add the one pointer line to `docs/progress/session-log.md`; `PROGRESS.md` "Current state" counts follow the same step.
