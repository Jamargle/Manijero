# `domain_procedure_map` validation

## Verdict

**Accepted** on 2026-11-06 by an independent validator. The tree checked is the feature commit that
carries this record (worktree clean; the implementing flow had already persisted `accepted`). No
repair round was needed and the validator changed no feature code.

Spec: [../specs/domain_procedure_map.md](../specs/domain_procedure_map.md) ·
Evidence: [appendix](../specs/domain_procedure_map.appendix.md)

## Checks rerun

- Taxonomy: the map holds exactly the 16 topics named in `docs/archive/MasterPlanV3.md` §7.3, in
  seed order, with no invented 17th; a script comparison matched the contract's 16 Spanish titles
  16/16.
- Artifact: every topic `proposed` with no `reviewed_by`; only `solicitud-unica-pac` is `partial`
  (4 source ids, 4 passage ids, digit-free gap note), the other 15 `uncovered` with empty lists.
  Every referenced id exists in `source_catalog.json`/`passages.json`, and each passage's
  `source_id` is listed by its topic.
- Human fields: independent scan found no digit in any title, summary, search phrase, or gap note;
  search wording unique across topics; no date, amount, article-number, eligibility, or
  applicability wording.
- `./scripts/init.sh --feature domain_procedure_map` — both published commands run unchanged;
  focused pytest `49 passed`.
- Validator CLI with `--catalog`/`--passages`/`--report` — exit `0`; `valid procedure map … (schema
  procedure-map-v1, 16 topics: 16 proposed, 0 reviewed)`; `coverage: 0 covered, 1 partial, 15
  uncovered; 4 mapped source(s), 4 mapped passage(s)`; 16 `topic …` lines.
- `./scripts/init.sh --fast` — 10/10 offline checks passed; backend `1920 passed, 4 skipped`.
  `--verify` not rerun: no `shared/`, app, Gradle, contract, or packaging input changed.
- Gaps are report-only: coverage counters and unreferenced-id lists never change exit `0`, and tests
  assert a valid map with 15 `uncovered` topics. The code is stdlib-only (`json`, `re`, `dataclasses`,
  `pathlib`, `typing`, `argparse`, `sys`), with a test forbidding network sockets.
- Throwaway CLI probes (temp dir, deleted): digit in title → exit `1`, stderr names only
  `$.topics[1].title` + the rule, stdout empty; broken JSON → exit `2`; no reference files → exit
  `0` with `reference ids not checked`; `--catalog` alone → exit `2`.
- Scope and docs: `source_catalog.json`, `passages.json`, `pac_coverage.md`, `pac_answer_eval.json`,
  `contracts/`, `shared/`, both app modules, and `scripts/init.sh` are byte-unchanged, no
  request-path module imports the map, and `git diff --check` is clean. The `ARCHITECTURE.md` clause,
  `knowledge/README.md` section, constraint + index, risk row and limitation line match the behavior;
  `PROGRESS.md` counts total 120 (83 accepted, 36 `not_started`, 1 `on_hold`).
- Security checklist: no secrets, personal data, network access, or user input path; diagnostics
  carry only JSON paths and rule text; no feature-scoped issue. E2E not applicable (no UI, route,
  auth, or API flow changed).

## Findings (non-blocking, low)

1. No-digit parity is slightly overstated: `procedure_map.schema.json` defines `$defs/humanText` but
   never references it, and the inline `^[^\\d]*$` accepts superscript numerics such as `²` that the
   validator's `isdigit()` rejects, so "enforced by both" is stronger than the schema. The canonical
   map is unaffected. Next schema touch: reference `$defs/humanText` and either widen the pattern or
   narrow the description to ASCII digits.
2. `_check_search_terms` keeps `_search_terms_seen` and `claim_search_term`/`_search_terms`, making
   the duplicate branch inside `claim_search_term` unreachable. Behavior is correct; collapse the
   trackers when the validator is next edited.

## Residual risks

- The map is an unreviewed hypothesis list: all 16 `proposed`, only the PAC topic `partial`, 15
  `uncovered`, with no owner or target-user review of topics or Spanish wording. The spec makes this
  non-blocking; the risk row and limitation line keep it visible.
- The owner brief said "17" seed topics while §7.3 names 16 and no 17th name exists; widening the
  taxonomy stays a reviewed code-and-data change. Evidence ids carry dates (e.g. `res_20260121`)
  because the canonical ids must resolve; human fields stay digit-free.
- The validator proves id resolution, not corpus currency, approval freshness, or user-question fit;
  `relevance_classifier` and `question_rewriting`, the future consumers, are still `not_started`.
