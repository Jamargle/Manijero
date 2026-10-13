# Validation: `land_safety_evaluation`

- Feature id: `land_safety_evaluation`
- Spec: `docs/specs/land_safety_evaluation.md`
- Validator role: independent feature validator (feature-validator skill)
- Date: 2026-10-13
- Verdict: **accept**

## Review target

- Spec path: `docs/specs/land_safety_evaluation.md`.
- Claimed status in `feature_list.json`: `passing` (self-verified; this pass is the independent validation).
- Diff: modified `CONSTRAINTS.md`, `PROGRESS.md`, `backend/README.md`, `feature_list.json`,
  `knowledge/README.md`; new `backend/app/land_safety_eval.py`,
  `backend/scripts/evaluate_land_safety.py`, `backend/tests/test_land_safety_eval.py`,
  `backend/tests/fixtures/land_safety/`, `knowledge/land_safety_eval.schema.json`, and the spec.
- Method: reproduced the claims myself from an out-of-repo venv
  (`/private/…/opencode/lse_venv`, Python 3.9.6) built from the repo's `backend/requirements.txt`
  plus `pytest`; no dependency was added to the repository.

## Checks rerun and results

| Check | Result |
|---|---|
| Baseline CLI over the synthetic fixtures (`--as-of 2026-10-13 --k 5`) | exit 0; corpus current; 2 eligible sources, 4 indexed passages, 0 excluded; 3 answered, 2 abstained, 1 clarification; invariants hold; 0 expectation mismatches |
| Metrics block | `covered_source_hit_rate` 1.000 (2/2), `correct_abstention_rate` 1.000 (2/2), `correct_clarification_rate` 1.000 (1/1), `no_over_clarification_rate` 1.000 (3/3), `expected_outcome_match_rate` 1.000 (6/6) — matches `PROGRESS.md` / `feature_list.json` |
| Per-category literal verification | covered-solicitud-01 answered citing `fixture_lse_junta`; covered-plazo-01 (critical) answered on the critical passage; uncovered-tractor-01 abstained `no_evidence`, empty sources, pinned message; false-premise-decreto-01 abstained `false_premise` (absent `999/2099`); mixed-land-riego-01 clarified exactly `land-A, land-B`; unknown-attribute-riego-01 answered citing `fixture_lse_boe` with no over-clarification |
| Determinism | two `--json` runs byte-identical (sha256 `2540…7a5f`); identical under `PYTHONHASHSEED` 0/1/12345 |
| `--fail-on-miss` contract | exit 0 on the whole fixture set; exit 1 on `edge/mismatch.json`; the same mismatch exits 0 without the flag |
| Exit 2 edge cases | critical case without review, unknown category, unknown expect, unknown reason, abstention without `expect_reason`, answered without `expected_source_ids`, clarification without `expected_land_ids_to_choose`, duplicate ids, unknown key, wrong `schema_version`, malformed JSON, `--k 0`, `--max-claims 0`, missing catalog — all exit 2 with empty stdout, located JSON-path diagnostics, no case text echoed |
| Empty canonical catalog (no cases) | exit 0; 0 eligible sources, 0 indexed passages, "no evaluation cases supplied", no metrics |
| Focused tests | `python -m pytest tests/test_land_safety_eval.py` → 91 passed |
| Full suite | `python -m pytest` → 560 passed (469 existing + 91 new) |
| `contracts/validate_examples.py` | exit 0, "Validated 2 request and 3 response examples" |
| Unchanged per-feature baselines | retrieval hit@5 0.857 (6/7) / recall@5 0.857 / MRR 0.857; generation 5 answers / 8 claims / 0 ungrounded / 1 no-evidence / invariants hold; abstention 3 answered / 7 abstained / 0 with sources or figures / invariants hold; clarification 5 answered / 1 clarification with both ids / invariants hold |
| `py_compile` (3 new files) | clean |
| `git diff --check` | clean |
| Offline (socket guard) | independent in-process guard blocking `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` still ran the decision and reported invariants hold; `land_safety_eval.py` imports no network client |
| Content-silent diagnostics | CLI stdout/stderr carry case ids and source ids only, never the question text; located load errors name only the JSON path |
| `/health` only route | `backend/app/main.py` still exposes only `@app.get("/health")` |

## Scope discipline

`git status --porcelain` shows only the expected new/updated paths. `contracts/`,
`knowledge/source_catalog.json`, `knowledge/passages.schema.json`, `backend/requirements.txt`,
`init.sh`, `backend/app/{generation,retrieval,source_catalog,abstention,clarification}.py`,
`backend/app/main.py`, the per-feature `scripts/evaluate_*.py` and `tests/test_*.py`, and all
`shared/`/`androidApp/`/`desktopApp/` code are unmodified. Fixtures are synthetic and labelled
(`fixture`, `no es una norma real`, `Sintético`, `cifra inventada`); the only numeric material is
the fictitious `42 días` and the impossible `999/2099` identifier. The harness imports the accepted
`answer_with_clarification` (default accepted extractive generator) and re-implements no
eligibility, grounding, or clarification.

## Findings

### N1 (non-blocking) — readable schema is slightly stricter than the executable validator

- Severity: low.
- Evidence: `knowledge/land_safety_eval.schema.json` declares `minItems: 1` on
  `expected_source_ids` and `expected_land_ids_to_choose`, so an explicit empty array is
  schema-invalid for any case. The executable validator
  (`_require_str_list(..., non_empty=False)`) accepts an explicit empty array whenever `expect` is
  not `answered`/`needs_land_clarification`. Independently reproduced with `jsonschema`
  (`Draft202012Validator`): an `uncovered`/`abstained` case carrying `"expected_source_ids": []`
  is INVALID against the schema but ACCEPTED by `validate_cases`.
- Why it matters: the spec requires the readable schema and the in-code validator to stay in sync;
  an author who writes an explicit empty list gets a schema rejection the CLI does not enforce.
- Required change (optional, follow-up): either drop `minItems: 1` from those two schema fields
  (the conditional `allOf` already encodes the non-empty requirement for the relevant
  expectations) or make the validator reject an explicit empty array for every category, and add a
  test asserting the two agree. Current fixtures/cases omit these keys, so no shipped artifact is
  affected.

The security checklist found no blocking issue: offline-only (network blocked), payload-explicit,
no secret/PII handling, no new route, no dependency, and diagnostics avoid content leakage.

## Documentation / harness state

- `knowledge/README.md`, `backend/README.md`, and `CONSTRAINTS.md` document the case-set contract,
  the review procedure, the CLI, the exit contract, and the not-enforced gate stance consistently
  with the implemented behavior.
- `PROGRESS.md` / `feature_list.json` record only the commands actually run and label the baseline
  synthetic and not a gate; the recorded numbers match the reproduced run.
- `init.sh` correctly unchanged (KMP-only; no backend command).

## Verdict

**accept.** The feature satisfies the spec, all recorded evidence reproduced, scope is clean, and
the only finding is non-blocking. Recommended state update: set `land_safety_evaluation` to
`accepted` and record this validation.
