# validity_checker — appendix

## Repository research

### Files inspected

- `feature_list.json` — the `validity_checker` row: `knowledge`, `not_started`, depends on `legal_change_impact_analysis` and `official_source_discovery` (both accepted).
- `PROGRESS.md` — current state; source monitoring, ingestion, change impact, and review packages are local, manual, fixture-backed, and make no currency or completeness claim.
- `docs/constraints/answers-and-knowledge.md` — change impact is read-only; ambiguous or negated signals and canonical merges stay human-reviewed; expired campaign records rotate out of active artifacts.
- `docs/constraints/operations.md` — owner-operable service commands and monitoring; this is a knowledge-reviewer CLI, not a routine service operation.
- `knowledge/source_catalog.schema.json` — source fields `lifecycle_status` (`current`), optional `consolidated_url`, optional `valid_until`, `campaign`, `published_on`, and `additionalProperties: false`.
- `knowledge/source_catalog.json` — the four reviewed sources: three campaign sources with `valid_until: 2026-12-31`; one has `consolidated_url`.
- `knowledge/passages.schema.json` — each passage has `source_id`, the link a retirement proposal uses to list affected passages.
- `knowledge/legal-change-impact.schema.json` — `legal-change-impact-report-v1`: `signals` (`kind`, `classification`, `reason`, `instrument_keys`), `potentially_affected.sources[].reasons` (`repeal_target` etc.), `review_gate`, `version_status`, and input digests.
- `backend/app/change_impact.py` — generates the accepted report, canonical JSON, fixed failures, and `automatic_retirement_allowed: false`; source links can come from ambiguous signals too, so the checker must inspect `classification`.
- `backend/scripts/analyze_legal_changes.py` — CLI pattern: explicit paths and `--as-of`, fixed error names, exit `0/1/2`, canonical report.
- `backend/app/source_catalog.py` — `validate_catalog(document, as_of)` rejects a `valid_until` before `as_of`; structural/policy checks are otherwise reusable.
- `backend/app/retrieval.py` — `validate_passage_set`, and `_is_expired` uses `valid_until < as_of` (equal to `as_of` is still in force).
- `backend/tests/test_change_impact.py` and `backend/tests/fixtures/change_impact/` — report/schema/CLI test style, synthetic official-document fixtures, fixed failure assertions.
- `backend/tests/test_source_catalog.py` — catalog validator regression coverage that must stay green.
- `scripts/init.sh` — `--feature <id>` extracts the verify block and runs it from the repository root; `--backend-tests tests/<file>.py` runs targeted pytest from `backend/`.
- `backend/README.md` § Legal change-impact analysis — command, artifact, determinism, failure, and limits style; the new section should stay within about 25 lines.
- `knowledge/README.md` — schema table, admission gate, and "derived artifact is not canonical knowledge" language.
- `ARCHITECTURE.md` — module/dependency map; change impact is the existing read-only derived boundary to extend.
- `docs/archive/MasterPlanV3.md` A10 — historical intent: BOE states, repeal patterns, automatic `valid_until`, and review proposals; not current authority.

### Existing patterns to follow

- A standard-library `backend/app/` module plus a thin `backend/scripts/` CLI; no model, network, or optional runtime at import.
- Fixed, value-free failure categories; never echo an exception, path, or document value.
- Derived artifacts are canonical JSON with sorted keys and a trailing newline, written atomically outside `knowledge/`, with input digests and no wall-clock time.
- Reuse the accepted catalog and passage validators; do not duplicate host, date-order, or passage policy.
- JSON Schema in `knowledge/`, executable validation in `backend/app/`, and a `jsonschema` test that validates the produced artifact.
- Offline synthetic fixtures; sockets blocked; focused pytest is a subset of `--fast`.

### Current gaps

- No one command turns reviewed catalog dates plus accepted impact signals into a validity review.
- The accepted catalog validator refuses an expired entry, so expiry cannot be inspected through the normal answer-path validation.
- No structured BOE consolidation state exists in accepted inputs: only the optional `consolidated_url`. Absence must stay unknown, not become "not consolidated".
- Impact signals carry no structured date; only the catalog supplies `valid_until` and `published_on`.
- No derived retirement/addition artifact exists for a human reviewer.

## Implementation plan

1. Add `knowledge/validity-review.schema.json` (`validity-review-v1`): `checker`, `as_of`, input digests, sorted `sources`, sorted `proposals`, `summary`, fixed `review_gate`, and `limits`; reject unknown fields.
2. Add `backend/app/source_validity.py` with `CHECKER`, `REPORT_VERSION`, fixed `FAILURES`, and a structural catalog read using `structural_as_of = min(as_of, every parsed valid_until)`; malformed dates fall through to the normal validator failure.
3. Validate passages with the accepted validator and every `source_id` against the catalog; validate the impact report's version, required signal/source fields, and `inputs.catalog_sha256`/`inputs.passages_sha256` against the supplied bytes.
4. Compute per-source `expiry` (`expired`/`in_force`/`unknown`), `publication` (`published`/`future`/`unknown`), and `consolidation` (`official_consolidated_text_linked`/`unknown`); never infer from campaign, title, text, or the current date.
5. Map proposals: retirement for expired `valid_until` and/or a machine-evident `repeal` intersecting a `repeal_target` link; review for ambiguous/negated signals of any kind, unmatched machine-evident repeal, machine-evident `validity`, and linked publication; addition only for an unlinked, non-`approved_copy` machine-evident `publication`; ignore machine-evident `amendment`.
6. Aggregate one proposal per kind and target, list affected passage ids for source proposals, sort deterministically, compute summary counts, and set `review.required: true`/`review.applied: false` everywhere.
7. Write the artifact atomically outside `knowledge/` and refuse an output path inside `knowledge/` or equal to any input; serialize canonical JSON with no timestamp or excerpt.
8. Add `backend/scripts/check_source_validity.py` with required `--catalog`, `--passages`, `--impact-report`, `--as-of`, `--report`; print fixed `Proposal:`/`Result:` lines and map failures to exit `2`.
9. Add fixtures and `backend/tests/test_source_validity.py`; update `backend/README.md`, `knowledge/README.md`, `ARCHITECTURE.md`, the constraints file, and risks; run the focused block and record evidence.

## Verification plan

- `./scripts/init.sh --feature validity_checker` — the focused tier passes with the new tests plus `tests/test_source_catalog.py` and `tests/test_change_impact.py`.
- `./scripts/init.sh --fast` — full backend suite, catalog validator, and offline evaluators pass; the new module changes no answer-path behavior.
- `./scripts/init.sh --verify` — not expected: no shared, Android/Desktop, contract, or packaging input changes.
- New tests to name and assert:
  - `test_expired_source_becomes_a_review_required_retirement` and `test_valid_until_equal_to_as_of_stays_in_force` — boundary and `< as_of` rule.
  - `test_missing_valid_until_and_consolidated_url_stay_unknown` — no inference.
  - `test_future_publication_date_is_review_required` — publication state.
  - `test_machine_evident_repeal_retires_only_the_linked_source` — `repeal_target` and `instrument_keys` intersection.
  - `test_ambiguous_and_negated_signals_never_retire` — review proposals only, including an ambiguous repeal that links a source.
  - `test_machine_evident_validity_signal_does_not_change_expiry` — text never supplies a date.
  - `test_machine_evident_amendment_is_not_consumed` — out-of-scope signal.
  - `test_publication_signal_proposes_addition_only_for_an_unlinked_candidate` and `test_linked_publication_signal_is_review_not_addition`.
  - `test_retirement_lists_every_affected_passage`.
  - `test_report_is_written_outside_knowledge_and_canonical_bytes_are_unchanged` — catalog, passages, release/index roots, and no answer-path writes.
  - `test_report_path_equal_to_an_input_is_refused`, `test_invalid_inputs_and_digest_mismatch_write_nothing`, and `test_oversized_report_aborts_before_writing` — exit `2`, fixed failure, nothing written.
  - `test_report_is_byte_identical_for_the_same_inputs_and_as_of`, `test_report_has_no_wall_clock_or_excerpt_and_matches_schema`.
  - `test_cli_result_lines_and_exit_codes` — `0` none, `1` proposals, `2` abort.
  - `test_checker_is_import_safe_and_offline` — fresh subprocess with sockets blocked; no `app.server`, generation, model, or HTTP client imported.
  - `test_structural_validation_still_rejects_policy_errors` — a bad host/date order still aborts.
- E2E: not added. The feature changes no API, authentication, routing, UI, or answer path, and the repository has no persistent E2E command for knowledge CLIs; the CLI and artifact are exercised by the focused pytest file.

## Evidence to capture

- Focused and fast tier commands with one-line results.
- New test count and the exact schema-validation test result.
- Two fixture CLI runs with the same inputs and `--as-of` producing byte-identical files.
- Confirmation that `git diff --stat knowledge/` touches no canonical data and that no canonical/release/index bytes changed.
- The fixed `Result:` strings observed for exit `0`, `1`, and `2`.
- Honest limits: no BOE consolidation-state field; an addition is a review lead, not an admission; lexical signals are only as good as the accepted report; no live run; detection precision/recall unmeasured; no owner walkthrough by owner decision.

## Feature evidence

- 2026-11-07 — `./scripts/init.sh --feature validity_checker` → `127 passed in 1.85s`.
- `backend/.venv/bin/python -m pytest tests/test_source_validity.py -q` → `28 passed in 0.64s`.
- Schema: `Draft202012Validator.check_schema` plus strict validation of the produced artifact passes (`test_report_has_no_wall_clock_or_excerpt_and_matches_schema`); the fixture impact report also validates against `knowledge/legal-change-impact.schema.json`.
- Determinism: two CLI runs with the same inputs and `--as-of 2099-06-01` wrote byte-identical reports (`cmp` clean).
- Fixture summary: sources 6 (expired 1, in force 4, expiry unknown 1), future publications 1, retirements 2, additions 1, reviews 6, proposals 9.
- `Result:` strings observed: exit `1` → `Result: 9 proposals need review; report written to <path>.`; exit `2` → `Result: the validity check did not run: invalid_as_of. Nothing was written.` The exit `0` and single-proposal forms are asserted in `test_cli_result_lines_and_exit_codes`.
- `git diff --stat knowledge/` → `knowledge/README.md | 1 +` plus the new untracked `validity-review.schema.json`; no canonical catalog, passage, release, or index bytes changed.
- Offline: `test_checker_is_import_safe_and_offline` runs a fresh subprocess with sockets blocked and no `app.server`, generation, model, or HTTP-client import.
- Limits: no BOE consolidation-state field; an addition is a review lead, not an admission; lexical signals are only as good as the accepted report; no live run; detection precision/recall unmeasured; no owner walkthrough by owner decision.
- 2026-11-07 — `./scripts/init.sh --fast` → all 10 offline checks passed; backend `2069 passed, 5 skipped`.

## Validator checklist

- [ ] Scope matches the contract; no UI, `/ask`, canonical edit, release, index, schedule, or model/network use.
- [ ] Scenarios 1–6 pass with evidence; expiry uses the injected UTC date and `valid_until == as_of` stays in force.
- [ ] Missing `valid_until` and `consolidated_url` stay `unknown`; absent consolidation is never reported as "not consolidated".
- [ ] Retirement is proposed only for structured expiry or a machine-evident repeal intersecting a `repeal_target` link; ambiguous/negated signals, including an ambiguous linked repeal, never retire.
- [ ] Machine-evident validity and linked publication become review proposals, machine-evident amendment is ignored, and additions are review-only, unlinked, and not `approved_copy`.
- [ ] The artifact is outside `knowledge/`, deterministic, schema-valid, input-digest-bound, and lists affected passages; canonical bytes are unchanged.
- [ ] Invalid input, digest mismatch, and unsafe output abort with exit `2`, a fixed failure name, and nothing written.
- [ ] The focused block runs unchanged through `./scripts/init.sh --feature validity_checker`; `--fast` passes.
- [ ] Durable docs updated once each; owner notes are verbatim and no owner walkthrough is claimed.
- [ ] `feature_list.json`, `PROGRESS.md`, and `docs/validations/validity_checker.md` updated by the implementer/validator; the canonical merge still names a human reviewer.
