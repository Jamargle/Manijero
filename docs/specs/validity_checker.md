# Feature Spec: `validity_checker`

## Source metadata

- **Feature:** `validity_checker` — Detect repeals, consolidation states, and expiry dates; retire automatically and propose additions for review (`knowledge`).
- **Depends on:** `legal_change_impact_analysis`, `official_source_discovery` (both accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no new screen or copy. A knowledge reviewer runs one offline command over the reviewed catalog and passages plus an accepted change-impact report; it writes a derived review file that proposes retirements and catalog additions, and never changes the corpus or `/ask`.
- **Verification:** offline pytest over synthetic fixtures plus the accepted catalog and change-impact regression tests; the commands are in Focused verification.
- **Notes:** owner decisions, 2026-11-06:
  - Standalone offline command over the reviewed catalog/passages and the accepted legal-change-impact signals.
  - Detect only explicit repeal, consolidation state, and expiry/publication dates from reviewed structured metadata; judge expiry against an injected UTC as-of date and keep unknown dates unknown.
  - Automatic retirement is limited to machine-evident cases and is written only as a derived, review-required retirement/proposal artifact outside knowledge/; it never edits canonical catalog, passages, releases, indexes, or /ask, and ambiguous or negated signals become review-required proposals.
  - Propose additions only for human review.
  - One command with a deterministic JSON report and plain-language Result lines; no model, network, or schedule; tests offline with fixtures.
  - Acceptance: validator accept is final, no owner walkthrough (the canonical merge still needs a named human reviewer under the existing review rule).

## Goal

Turn the accepted, review-only change-impact signals plus the reviewed catalog into one derived validity review: each catalog source's explicit expiry, publication and consolidation facts, a retirement proposal only for machine-evident repeal or structured expiry, a review proposal for every ambiguous or negated signal, and an addition proposal for a machine-evident publication that is not in the catalog. A human decides; the canonical corpus, releases, indexes, and answer path stay byte-identical.

## Non-goals

- Legal interpretation, detecting a change from document text beyond the accepted report, or resolving conflicting signals.
- Editing canonical catalog, passages, releases, indexes, evaluation cases, campaign rotation, or `/ask` behavior.
- New catalog fields, issuers, hosts, or a BOE consolidation-state API.
- A model, network call, scheduler, systemd/GitHub workflow, or repository-hosted schedule.
- Owner-guide steps or an owner walkthrough; acceptance is the validator's, and a canonical merge still requires a named human reviewer.
- Any Compose UI, route, Spanish copy, or app wire-contract change.

## Job story

When an approved source may have expired or been explicitly repealed, I want one offline check to turn the reviewed metadata and accepted signals into a review file, so a human can retire or add sources without automation silently changing what the assistant answers.

## Acceptance Scenarios

### 1. Structured expiry becomes a review-required retirement

Given a reviewed catalog with one source whose `valid_until` is before the injected UTC `--as-of`, one unexpired source, and reviewed passages for both · When `check_source_validity.py` runs with an accepted impact report · Then it writes a `validity-review-v1` file outside `knowledge/`, reports the expired source as `expiry.state: expired` with its passage ids in a retirement proposal whose `review.required` is true and `review.applied` is false, reports the other as `in_force`, prints one `Proposal:` line per proposal plus one `Result:` line, and exits `1`.

### 2. Only a machine-evident repeal can propose retirement

Given the accepted report has a machine-evident `repeal` signal whose `instrument_keys` match a source linked with reason `repeal_target`, and another candidate has an ambiguous or negated signal of any kind · When the checker runs · Then the linked source gets the retirement proposal with reason `machine_evident_repeal`; the ambiguous/negated candidate gets only a review proposal (reasons `ambiguous_signal`, plus `negated_signal` when the report says so); a machine-evident `validity` or linked `publication` signal gets only a review proposal; a machine-evident `amendment` signal is not consumed.

### 3. Unknowns stay unknown and a future publication is reviewed

Given a source without `valid_until` or `consolidated_url`, and another source whose `published_on` is after `--as-of` · When the checker runs · Then the first reports `expiry.state: unknown` with `valid_until: null` and `consolidation.state: unknown`, the second gets a review proposal with reason `future_publication_date`, and no date, consolidation, or applicability value is inferred.

### 4. Additions are proposals only

Given a machine-evident `publication` signal for a candidate that links no catalog source and is not an `approved_copy` · When the checker runs · Then the report contains an addition proposal for that candidate with `review.required: true` and `review.applied: false`; the same signal for a linked candidate gets a review proposal instead, and for an unlinked `approved_copy` it adds nothing; no catalog, passage, release, or index byte changes.

### 5. Invalid or unsafe input fails closed

Given an invalid catalog, passage set, or impact report; an impact report whose catalog/passages digests differ from the supplied files; or a report path inside `knowledge/` or equal to an input path · When the command runs · Then it exits `2`, prints one fixed failure `Result:` line with a fixed failure name and writes nothing; valid inputs are unaffected.

### 6. Deterministic, offline, and read-only

Given the same inputs and `--as-of`, when the command runs twice, then the two JSON files are byte-identical, carry input digests and no wall-clock time, and the run reads no local timezone, model, network, or schedule. Tests block sockets and assert canonical knowledge, release, index, and answer-path bytes are unchanged, and that the checker imports neither the answer service nor a model or HTTP client.

## Technical approach

- **New standard-library module `backend/app/source_validity.py`** plus the thin CLI `backend/scripts/check_source_validity.py`. Reuse `app.source_catalog.load_catalog`/`validate_catalog` and `app.retrieval.load_passage_set`/`validate_passage_set`; never import the API service, generation, embeddings, or an HTTP/model client.
- **Structural catalog read.** The accepted validator rejects a catalog whose `valid_until` is before the validation date, so the checker validates with the same validator at `structural_as_of = min(as_of, every parsed valid_until)`: every structural, policy, date-order, and host error still fails closed, while an already-expired entry remains inspectable. The answer path, `/ready`, release gate, and campaign rotation keep their unchanged strict behavior; only this derived check uses the structural date.
- **Input integrity.** Require `impact_report.schema_version == "legal-change-impact-report-v1"`, a complete signal/source shape, and `inputs.catalog_sha256`/`inputs.passages_sha256` equal to the SHA-256 of the supplied catalog/passages; otherwise abort `invalid_impact_report` or `impact_inputs_mismatch`. Do not read discovery state directly: the accepted report is the only candidate surface. Bound it at 1,000 candidates and the artifact at 5,000 proposals; exceeding either aborts `candidate_count_exceeded` or `proposal_count_exceeded`. Do not require the report's `as_of` to equal the injected date; expiry is judged at the injected date over the same reviewed bytes.
- **Per-source facts.** `--as-of` is one `YYYY-MM-DD` UTC calendar date; never read the local timezone, `datetime.now()`, or a wall clock. Each source records its reviewed `lifecycle_status`. `expiry`: `expired` when `valid_until < as_of`, `in_force` when `valid_until >= as_of`, `unknown` when absent. `publication`: `published` when `published_on <= as_of`, `future` when later, `unknown` when absent. `consolidation`: `official_consolidated_text_linked` only when the reviewed catalog records `consolidated_url`, otherwise `unknown`. Never infer a missing date or consolidation state from campaign, title, text, or the current date.
- **Proposals.** One retirement per source with reasons from `expired_valid_until` and/or a machine-evident `repeal` whose `instrument_keys` intersect that source's `repeal_target` link; a retirement lists every reviewed passage with that `source_id`. A machine-evident repeal with no such link is `unmatched_repeal_target` review. Every ambiguous or negated signal of any kind is an `ambiguous_signal`/`negated_signal` review proposal. A machine-evident `validity` signal is a review proposal; expiry never changes from text. A machine-evident `publication` for an unlinked candidate whose `version_status` is not `approved_copy` is an addition proposal; a linked candidate is a review proposal; an unlinked `approved_copy` adds nothing. A machine-evident `amendment` is ignored; the impact report remains its review surface.
- **Artifact.** Write canonical JSON (`sort_keys`, indent 2, trailing newline) atomically outside `knowledge/`, refusing a path inside `knowledge/` or equal to any input. Include `schema_version`, `checker`, `as_of`, input SHA-256 digests, sorted `sources`, sorted `proposals`, `summary`, `review_gate` (`canonical_changes_applied: false`, `automatic_retirement: false`, `requires_human_approval: true`), and a fixed `limits` list. The limits state that this is not a legal conclusion and that the impact report remains the review surface for amendment, version, and conflict review. No timestamp, excerpt, question, land, or personal data.
- **CLI contract.** One `Proposal:` line per proposal in deterministic order and one `Result:` line: `Result: no proposals need review; report written to <path>.`, `Result: 1 proposal needs review; report written to <path>.`, `Result: <n> proposals need review; report written to <path>.` for `n > 1`, or on abort one fixed `Result:` line on stderr: `Result: the validity check did not run: <failure>. Nothing was written.` Exit `0` no proposals, `1` proposals written, `2` aborted before writing; a failure prints only the fixed name, never a path or exception text. New schema `knowledge/validity-review.schema.json` (`validity-review-v1`).

## Expected file changes

- `backend/app/source_validity.py` — create; structural catalog read, input-digest checks, per-source states, proposal mapping, canonical writer, exit code, fixed failures.
- `backend/scripts/check_source_validity.py` — create; the one command with required `--catalog`, `--passages`, `--impact-report`, `--as-of`, `--report`.
- `knowledge/validity-review.schema.json` — create; `validity-review-v1` derived-report contract.
- `backend/tests/fixtures/source_validity/` — create; synthetic catalog (expired, unexpired, unknown, future publication, consolidated and unknown), passages, and accepted impact reports (machine-evident/ambiguous/negated/unmatched/linked/unlinked, amendment control).
- `backend/tests/test_source_validity.py` — create; states, proposal rules, failures, determinism, schema, CLI, offline/read-only guards.
- `backend/README.md` — update; command, inputs, artifact, exit/Result protocol, limits (about 25 lines).
- `knowledge/README.md` — update; one row for the new derived schema.
- `ARCHITECTURE.md` — update; add the read-only validity checker boundary beside change impact.
- `docs/constraints/answers-and-knowledge.md` — update; one MUST for structural expiry read and review-only proposals.
- `docs/risks-and-open-questions.md` — update; the consolidation-state gap and unmeasured detection.
- `feature_list.json`, `PROGRESS.md`, `docs/progress/session-log.md`, `docs/validations/validity_checker.md` — implementer/validator only, after evidence exists.
- `docs/owner-guide.md` — not changed; owner decision: no walkthrough. No init.sh mode: this is a knowledge-reviewer CLI like `analyze_legal_changes.py`.

## Visual design impact

None. No Compose UI, route, Spanish copy, or screenshot baseline changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — add `source_validity.py` and its derived, review-only artifact boundary.
- `docs/constraints/answers-and-knowledge.md`: update — a derived validity check may read an expired catalog structurally but never makes anything eligible; retirement/addition proposals stay review-only outside `knowledge/`.
- `AGENTS.md`: not needed — no workflow, startup path, or repo-wide rule changes.
- Other: `backend/README.md` (command and artifact), `knowledge/README.md` (schema row), `docs/risks-and-open-questions.md` (limits); `DESIGN.md`, `CONTEXT.md`: not needed. `docs/owner-guide.md`: not needed by owner decision.

## Focused verification

`./scripts/init.sh --feature validity_checker` runs the block unchanged from the repository root. It is the feature-scoped subset: the new tests plus the accepted catalog and change-impact regression tests.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_source_validity.py tests/test_source_catalog.py tests/test_change_impact.py -q
```
<!-- verify:end -->

## Appendix

See [`validity_checker.appendix.md`](validity_checker.appendix.md) for repository research, the ordered plan, verification detail, evidence, and the validator checklist.
