# Appendix — `backend_citation_hardening`

Planning and verification record for [`backend_citation_hardening.md`](../../specs/backend_citation_hardening.md). The acceptance record, when created, belongs to `docs/validations/backend_citation_hardening.md`.

## Repository research

Inspected:

- `AGENTS.md`, `PROGRESS.md`, and `feature_list.json`: open item is backend F1 hardening plus stale knowledge wording; feature is `not_started`, dependencies `grounded_answer_generation` and `backend_pac_corpus` are accepted.
- `docs/specs/grounded_answer_generation.md` and `.appendix.md`, plus `docs/validations/grounded_answer_generation.md`: establishes the verifier, generator contract, response source order, tests and carried F1 finding.
- `docs/specs/answer_source_cards.md` and `docs/validations/answer_source_cards.md`: client fails closed when citations and sources do not align; explicitly hands backend F1 and knowledge wording forward.
- `backend/app/generation.py`: `verify_draft` validates inline/declared markers against retrieved ranks; after success `_fit_claims` chooses claims; current `Answered.cited_markers` and `sources` are built from ascending rank, but `_assemble_claims` preserves rank-valued markers. Thus rank 2 alone can yield marker `[2]` with a single returned source.
- `backend/tests/test_generation.py`: existing tests cover marker parsing/validation, ascending source ranks, claim fitting, and response assembly; add focused end-to-end generator-seam cases here.
- `knowledge/README.md`: its generation section currently says `[n]` is retrieval rank and unconditionally claims `[n]` means `sources[n-1]`; this is false for non-prefix subsets.
- `CONSTRAINTS.md`: answer grounding rules already assign markers, sources, and notice to code and state marker/source correspondence; review for a precise update.
- `backend/README.md`, `ARCHITECTURE.md`, `contracts/openapi.yaml`, and `scripts/init.sh`: current backend boundary and harness commands; no new route/API or architecture is needed. `./scripts/init.sh --backend-tests <target>` is the available focused backend test mode.

The canonical knowledge corpus is empty and no user-visible answer is produced from it. Tests must use existing synthetic fixtures and claim no legal validation. No persistent E2E harness is available or needed: this changes an internal backend assembly invariant, not API routing or user flow.

## Implementation plan and tasks

1. Inspect `Answered`, `ClaimVerdict`, `_fit_claims`, `generate_grounded_answer`, and `to_answer_response` and choose one explicit boundary for candidate-rank markers versus response-local ordinals.
2. Preserve `verify_draft` behavior: it must validate the original draft against retrieved rank identifiers before any transform. Do not mutate/rewrite drafts before verification.
3. Once kept claims are known, compute cited ranks in ascending order, map them to `1..m`, and create the final answer with marker-token-only substitutions. Derive `sources` in exactly the same rank order. Ensure `cited_markers` semantics are clear and internally consistent (prefer preserving original candidate ranks if it is an internal retrieval field; otherwise rename/change only with bounded callsite audit).
4. Add tests using the existing recorded generator/test fixture seam: rank 2 alone maps to `[1]`; sparse ranks 2 and 4 map densely and point to their corresponding source objects; repeated citations remain repeated but use the same ordinal; normal ranks 1 and 2 remain unchanged; unsupported/unknown/mismatch drafts remain rejected; claim prose is unchanged.
5. Update `knowledge/README.md` so it no longer conflates retrieval rank with emitted citation ordinal. Update `CONSTRAINTS.md` if needed to state that emitted answer markers are dense positions in the exact response `sources` list.
6. Run focused generation tests, full backend tests, the generation evaluator, contract examples, and `git diff --check`; verify `contracts/` and retrieval are unchanged.

## Verification plan

From repository root, after implementation:

```sh
./scripts/init.sh --backend-tests tests/test_generation.py
./scripts/init.sh --backend-tests
python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5
python3 contracts/validate_examples.py
git diff --check
```

Focused spec command is the first command above. The backend test wrapper may require its documented virtualenv/development dependencies; report the actual interpreter and results. Generation evaluation metrics are synthetic and report-only; contract examples only confirm no wire change.

## Evidence to capture

- Focused and full backend pytest counts and exact commands.
- A sparse-rank case (rank 2 only) showing emitted `[1]` and the rank-2 `sources[0]` object.
- A multi-rank case demonstrating stable dense numbering, repeated-marker behavior, and unchanged claim prose.
- Fail-closed negative tests preserving existing unknown-marker, mismatch, and grounding behavior.
- Generation evaluator result and contract-example validation; `git diff --check`.
- Explicit confirmation that `contracts/`, `backend/app/retrieval.py`, client/shared source, and canonical legal artifacts were not changed.

## Feature evidence

- Implementation: `backend/app/generation.py` verifies the original draft ranks unchanged, keeps `ClaimVerdict.markers` and `Answered.cited_markers` as retrieval ranks, then rewrites only marker tokens after `_fit_claims` using ascending cited-rank ordinals. Sources use that same rank order. `backend/tests/test_generation.py` adds sparse rank-2-only response/payload checks and sparse ranks 2/4 with repeated marker, deterministic source ordering, and preserved prose. `knowledge/README.md` and `CONSTRAINTS.md` now state the distinction.
- Focused command: `MANIJERO_PYTHON=/private/var/folders/78/v5c0wj2x34q13w54vkc_z3y80000gp/T/manijero-citation-venv/bin/python ./scripts/init.sh --feature backend_citation_hardening` — **passed**, `102 passed in 1.15s` (Python 3.14.5, pytest 8.4.2).
- Full no-device suite: `MANIJERO_PYTHON=/private/var/folders/78/v5c0wj2x34q13w54vkc_z3y80000gp/T/manijero-citation-venv/bin/python ./scripts/init.sh --fast` — **passed**; shared `:shared:jvmTest` BUILD SUCCESSFUL, contract examples validated (2 request and 3 response), full backend suite `618 passed, 1 warning in 8.71s`, and all nine offline checks passed. Synthetic generation evaluation: 5 answers, 8 claims checked, 0 ungrounded, 0 invented sources, 1 no-evidence outcome, invariant holds, 0 outcome mismatches. The warning is Starlette's `httpx`/`TestClient` deprecation.
- Initial focused invocation without `MANIJERO_PYTHON` could not run because host Python did not have pytest installed. Created an isolated virtualenv in the approved temporary directory and installed `backend/requirements-dev.txt`; reran successfully with the explicit interpreter above. No dependency or environment files were added to the repository.
- `git diff --check` — passed. `contracts/`, `backend/app/retrieval.py`, shared/client sources, and canonical legal artifacts are unchanged. No wire shape changed.

## Validator checklist

- [x] Original draft citations are verified against retrieved candidate ranks before mapping.
- [x] Every successful `Answered` result and serialized answered payload has distinct marker numbers exactly `1..len(sources)`.
- [x] Each emitted marker `[n]` corresponds to the candidate represented by `sources[n-1]`.
- [x] Sparse rank 2 alone maps to output marker `[1]`; sparse multiple ranks map deterministically and source list order matches.
- [x] Repeated markers retain meaning and claim text is byte-for-byte unchanged apart from citation tokens.
- [x] Unknown, undeclared, or ungrounded citations still reject the whole draft; mapping does not repair invalid drafts.
- [x] Existing prefix-ranked extractive behavior and accepted `AskResponse`/`AnswerSource` shapes remain unchanged.
- [x] `knowledge/README.md` accurately distinguishes internal candidate ranks from response citation numbers; durable constraints remain aligned.
- [x] Focused tests and full backend suite pass, with only synthetic test data and no legal coverage claims.
