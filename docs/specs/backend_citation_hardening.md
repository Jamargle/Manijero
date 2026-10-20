# Feature Spec: `backend_citation_hardening`

## Source metadata

- **Feature:** `backend_citation_hardening` — Enforce citation numbering for every generated answer (`backend`).
- **Depends on:** `grounded_answer_generation`, `backend_pac_corpus` (accepted).
- **Source behavior:** every generated answer's inline citation `[n]` identifies the corresponding returned `sources[n-1]`, including when the cited retrieval candidates are not a prefix of candidate ranks.
- **Source verification:** exercise a verified draft that cites a non-prefix candidate set (notably rank 2 alone); assert the emitted answer and source list have dense, matching numbers, while grounding still uses original retrieval ranks.
- **Source note:** carried finding F1 from `grounded_answer_generation` and `answer_source_cards`; the client already fails closed for malformed mapping, but the backend generator's promise was not enforced for sparse cited ranks.
- **Scope size:** one citation-index mapping invariant in the existing generation pipeline plus focused tests and documentation; correctly sized.

## Goal

Guarantee for every `Answered` result and serialized `answered` payload that distinct inline citations are exactly `1..len(sources)` and citation `[n]` refers to `sources[n-1]`. Preserve verification against the original retrieved candidate ranks, while transforming the final answer to a dense response-local citation numbering after verified claims are selected.

## Non-goals

- No change to citation grounding rules, evidence eligibility, retrieval ranking, answer claims, API schemas, source-card client behavior, or abstention/clarification paths.
- No new model/provider, route, dependency, corpus data, legal facts, or UI behavior.
- Do not weaken verification or accept a draft that references an unknown candidate; do not change what evidence a marker cites.
- Do not treat the client-side fail-closed behavior as a substitute for the backend invariant.

## Job story

When a generated answer cites retrieved evidence, I want each displayed citation number to select the matching source in the response, so that a person never follows a valid-looking marker to the wrong document.

## Acceptance scenarios

### Sparse rank citation is dense in the response

Given retrieval candidates ranked 1, 2, and 3 and a generator draft whose only verified claim cites candidate rank 2, when generation assembles the answer, then its marker is `[1]`, the response has exactly the rank-2 source at `sources[0]`, and the claim remains grounded against rank 2's passage.

### Multiple cited ranks map consistently

Given verified claims citing candidate ranks 2 and 4 (in either claim order, with repeats allowed), when the pipeline assembles the result, then the output uses dense numbers in ascending candidate-rank order, every marker resolves to the source at that one-based position, and `sources` contains exactly those cited candidates once each.

### Verification still rejects invalid citations

Given a draft with an unknown marker, a declared/inline marker mismatch, or a claim unsupported by its cited candidate, when verified, then it remains rejected whole with the existing reason and issue codes; renumbering never repairs or legitimizes it.

### Canonical prefix behavior is unchanged

Given the extractive generator emits citations for candidate ranks 1 and 2, when assembled, then answer markers and source order remain `[1]`, `[2]` and existing response payload shape is unchanged.

### Durable guidance is accurate

Given a non-prefix cited candidate set is possible, when `knowledge/README.md` describes citation semantics, then it states the invariant for emitted answers without implying that response marker numbers always equal retrieval ranks.

## Technical approach

- Keep `verify_draft` as the authority and validate the original draft markers against candidate ranks exactly as today.
- After report success and `_fit_claims` selection, derive a deterministic map from the distinct candidate ranks actually cited by kept claims to dense response ordinals `1..m`. Use ascending candidate-rank order to match the existing `sources` ascending-order contract.
- Rewrite only the verified inline marker tokens in the assembled user answer using that map; leave claim text byte-for-byte unchanged. Build `sources` from the same ordered ranks, ensuring ordinal `n` and `sources[n-1]` share the same candidate.
- Keep internal `ClaimVerdict.markers` as candidate ranks unless implementation proves a response-local representation is required; document the boundary and ensure tests cover the exposed `Answered`/response values.
- Correct `knowledge/README.md`'s citation paragraph to distinguish retrieval rank during verification from dense response citation numbering and retain the user-facing `[n]` to `sources[n-1]` guarantee.
- No changes to `contracts/`, `backend/app/retrieval.py`, generation eligibility, or client-side behavior.

## Expected file changes

- `backend/app/generation.py` — dense response-local marker mapping during final assembly, keeping verification on candidate ranks.
- `backend/tests/test_generation.py` — sparse and multi-rank remapping, repeated marker, source ordering, and no-claim-text mutation regressions.
- `knowledge/README.md` — fix the unconditional statement that response `[n]` is candidate retrieval rank `n`.
- `backend/README.md` — not needed unless implementation alters its existing generation explanation; current summary need not duplicate this invariant.
- `CONSTRAINTS.md` — update the answer-grounding citation ownership rule only if needed to make explicit that emitted markers are dense response-local positions; preserve code ownership.
- `ARCHITECTURE.md` — not needed; no component boundary or runtime architecture changes.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`, `feature_list.json`, `PROGRESS.md` — no planner-time edits; status/evidence updates occur after implementation and independent validation.

## Visual design impact

None. The client already maps canonical markers to cards and degrades malformed payloads safely; only backend answer assembly changes.

## Durable documentation impact

- `knowledge/README.md`: update citation semantics to describe original candidate ranks as internal verification references and emitted markers as dense response positions mapped to `sources[n-1]`.
- `CONSTRAINTS.md`: review/update the citation MUST wording if the distinction is not adequately stated; do not relax ownership or grounding requirements.
- `backend/README.md`: no change unless implementation makes its current description inaccurate.
- `ARCHITECTURE.md`: not needed; this is an internal generation invariant.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/openapi.yaml`: not needed; no user flow or wire shape changes.
- `PROGRESS.md` and `feature_list.json`: orchestrator updates after checks and acceptance, not during planning.
- `docs/validations/backend_citation_hardening.md`: created by independent validator only.

## Focused verification

`./scripts/init.sh --feature backend_citation_hardening` runs the focused regression test; it is the cheapest check covering the changed pipeline. Run the full backend suite as a broader regression check.

<!-- verify:start -->
```sh
./scripts/init.sh --backend-tests tests/test_generation.py
```
<!-- verify:end -->

## Appendix

See [`backend_citation_hardening.appendix.md`](backend_citation_hardening.appendix.md) for repository research, ordered implementation tasks, verification, evidence, and validator checklist.
