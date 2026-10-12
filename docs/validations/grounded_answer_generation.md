# Validation: grounded_answer_generation

## Verdict

**Accept** — independently validated against
`docs/specs/grounded_answer_generation.md` on 2026-10-13. No repair required.
The two findings below are non-blocking and are handed to the orchestrator for
the deferred hosted-model seam and for `answer_source_cards`.

## Evidence

All commands were run from the repository root unless noted. Pytest ran with the
interpreter of a temporary virtualenv created **outside** the repository
(`/private/var/folders/.../venv_gen_validate`); no dependency was added to
`backend/requirements.txt` or to the repository.

- Focused suite: `cd backend && <venv>/bin/python -m pytest tests/test_generation.py`
  → **100 passed**. Full suite: `cd backend && <venv>/bin/python -m pytest`
  → **221 passed** (121 existing + 100 new). Matches the recorded counts.
- Static: `python3 -m py_compile backend/app/generation.py
  backend/scripts/evaluate_generation.py backend/tests/test_generation.py`
  → clean; `git diff --check` → clean. Independently checked trailing whitespace
  and final newlines on every new file → clean.
- Fixture evaluation: `python3 backend/scripts/evaluate_generation.py --catalog
  backend/tests/fixtures/generation/catalog.json --passages
  backend/tests/fixtures/generation/passages.json --eval
  backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0; 2 eligible sources, 4 indexed passages, 0 excluded, `answers
  produced: 5`, `claims checked: 8`, `ungrounded claims: 0`, `invented sources:
  0`, `no-evidence outcomes: 1`, `grounding invariants hold: yes`, `outcomes
  differing from expect: 0`. Every answered question printed its per-claim
  verdict and cited candidate numbers; the out-of-corpus line `zzzz qqqq`
  returned `no_candidates`.
- Feature-list verification reproduced literally: for
  `¿Cuánto dura el plazo ficticio de prueba?` claim 1 = the `critical` rank-1
  excerpt (with the fictitious `42 días`) cited `[1]` → `ok`; claim 2 = the rank-2
  excerpt cited `[2]` → `ok`; both excerpts are the retrieved passages.
- Canonical empty corpus: `python3 backend/scripts/evaluate_generation.py
  --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5` → exit 0 with
  0 eligible sources, 0 indexed passages, `no evaluation questions supplied`.
  With `--eval` and no passages the index check names the unknown ids and exits 2
  (documented harness behavior, fail closed).
- Determinism: two `--json` runs are byte-identical; sha256
  `f8345c124a3ba4ab0b2fd1e4947244b54e21b5cc2a289f024e13cf5b28a4e453` matches the
  recorded digest. Ten in-process runs produced one distinct serialized payload.
- No network: an independent, stricter socket guard (patching `socket.socket`,
  `socket.create_connection`, and `socket.getaddrinfo` before the call) still
  produced the answer; `generation.py` imports only `re`, `unicodedata`,
  `dataclasses`, `datetime`, `typing`, and `app.retrieval`, and contains no
  `print`/logging.
- Fail closed: an `eligibility_claim` passage set → `outcome: policy_failed`,
  `claim 1: failed; cites [1] (eligibility_claim)`, exit 1. Independently injected
  drafts returned `policy_failed`, `grounding_failed` (`unknown_marker`,
  `no_markers`+`uncited_sentence`, `empty_answer`, `incoherent_draft`,
  `uncited_sentence`), `generator_abstained`, and `generation_error`, and no
  `NotAnswered` result exposed an `answer` attribute. A real paraphrase of a
  `critical` excerpt whose figure *is* present (`"...dura 42 dias..."`) was still
  rejected with `critical_not_literal`, so rule 5 is independent of rule 4.
- No generator call without evidence: an out-of-vocabulary question with an
  exploding generator returned `no_candidates` and never invoked the generator.
- Privacy: fuzzing all 13 recorded drafts and their retrieved excerpts found no
  draft or excerpt text in any `GroundingIssue.detail`; the CLI prints question
  and claim text only as the review output the spec mandates.
- Contract: `python3 contracts/validate_examples.py` → "Validated 2 request and
  3 response examples against answer_api_contract". The assembled payload's top
  keys are exactly `{status, answer, sources, land_scope, land_ids_to_choose}`,
  every source has exactly the seven `AnswerSource` keys, no retrieval-local
  field (`passage_id`, `source_id`, `applicability`, `critical`, `score`, `rank`)
  leaked, `status: answered` and `land_scope: general` are legal enum values,
  and `len(answer) = 284 ≤ 1200`. `contracts/` is unchanged.
- Regression boundary: the retrieval fixture baseline is unchanged at
  `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`.
- Scope: `git status` confirms `contracts/`, `backend/app/retrieval.py`,
  `backend/app/source_catalog.py`, `backend/app/main.py`,
  `knowledge/source_catalog.json`, `knowledge/passages.schema.json`,
  `backend/requirements.txt`, `init.sh`, `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`,
  `docs/build-brief.md`, `docs/domain-model.md`, `MasterPlanV3.md`, and all
  client/shared/Android/Desktop code are unmodified. No canonical
  `knowledge/passages.json` was created and no manifest/dependency file was added.
- Fixtures: synthetic and labelled (`"fixture"`, `"no es una norma real"`,
  `"Fragmento sintético de prueba"`); the only figures are the explicitly
  fictitious `42 días`, `1.200 euros`, and `3 documentos`; two passages are
  `critical`. Sources pass the accepted catalog gate; excerpts are
  single-sentence, as the recorded implementation finding requires.
- Documentation: `knowledge/README.md` and `backend/README.md` gained accurate
  "Grounded answer generation" sections (evidence boundary, citation/figure/
  extractive rules, exit codes, reviewer guidance); `CONSTRAINTS.md` records two
  operational MUST rules and matches the spec's escape hatch; the spec gained an
  "Implementation findings" section. `PROGRESS.md` and `feature_list.json`
  report only commands that were re-run here successfully.

## Scope and security review

Feature-scoped review of the diff found no blocking security or privacy issue.
The module is offline, standard-library-only, adds no route (`/health` remains
the only one), no model provider, no prompt, no API key, and no dependency. It
reads no catalog or passage file itself; retrieval remains the only evidence
source. Invalid questions are rejected before retrieval, the 2000-character
question bound and the 1200-character answer bound are enforced, and the figure
and date extraction regexes have no nested-ambiguity backtracking. Diagnostics
carry codes, candidate numbers, and rule names only. Fixtures contain no real
deadline, amount, article number, or eligibility statement.

## Findings

Non-blocking:

- **F1 (low–medium; fix before the hosted-model path is enabled or before
  `answer_source_cards` maps markers to cards).** The documented invariant
  "marker `[n]` always means `sources[n-1]`" holds only when the cited candidate
  set is the prefix `[1..m]`. A draft that cites a non-prefix set is accepted by
  `verify_draft` and assembled as `sources` = exactly the cited candidates in
  ascending order, so marker `[2]` can point at a one-element `sources` array.
  Reproduced: `DraftAnswer("answered", rank2.excerpt + " [2]", (2,))` →
  `verify_draft.ok == True`, `cited_markers == (2,)`, `len(sources) == 1`,
  `marker [2] resolves to sources[1] == False`. Not reachable today: the only
  enabled generator (`ExtractiveGroundingGenerator`) always emits ranks
  `1..max_claims` in order and `_fit_claims` only drops trailing claims, so the
  shipped path always produces a prefix. The spec's own wording is the source of
  the ambiguity ("exactly the cited candidates … so marker `[n]` always means
  `sources[n-1]`"), so this is a latent spec/implementation mismatch, not an
  implementer error. Suggested minimal repair (either): renumber markers in the
  emitted payload to `1..m` and emit `sources` in that same order, or reject a
  non-prefix cited set in `verify_draft` with a new code (e.g.
  `sparse_markers`) and cover it in `test_generation.py` and
  `drafts_ungrounded.json`. Either way, correct the sentence in
  `knowledge/README.md` that promises `[n] == sources[n-1]` unconditionally.
- **F2 (low; hardening at the generator seam).** A malformed generator draft
  whose `source_markers` is not iterable escapes as an exception instead of a
  reason code: `DraftAnswer("answered", "texto [1]", 1)` and
  `DraftAnswer("answered", "texto [1]", None)` both raise `TypeError` out of
  `generate_grounded_answer`, while `None` drafts, non-`DraftAnswer` values,
  non-`str` answers, and `("1",)` markers are handled (`generation_error` /
  `grounding_failed`). Fail-closed is still satisfied (no answer is emitted), but
  the "a generator error becomes `generation_error`" contract is not. Cheap fix:
  coerce/validate `source_markers` inside `verify_draft` (or wrap the
  `verify_draft` call in the existing `try`), and add the two cases to
  `drafts_ungrounded.json`.

Informational (no action required for this feature):

- **N1.** `init.sh` line 56 still lists retrieval, answer generation, and the
  visual foundation as deferred; the spec mandates `init.sh`: no change, so this
  is orchestrator housekeeping, as the spec's Risks section already notes.
- **N2.** The `feature_list.json` evidence quotes the temporary eligibility
  fixture loosely ("`...tienes derecho a ninguna ayuda real.`"); the temporary
  file is not a persisted artifact, so the quote is unverifiable but harmless.
  The re-run policy path reproduces exactly as recorded otherwise.
- **N3.** The spec's technical approach lists `RetrievalError`,
  `CatalogRejectedError`, and `PassageSetError` among `generation.py`'s imports;
  the module imports only `DEFAULT_K`, `RetrievedPassage`, and `Retriever`, which
  is stricter (no unused imports) and consistent with "retrieval is the only
  evidence source".

## Residual uncertainty

The grounding checks are lexical by design: figure presence is not entailment,
the eligibility check is a short phrase list, and semantic grounding, conflict
detection, and the user-visible abstention copy are explicitly deferred to
`safe_abstention` and a later judge — so "grounded" here means "every material
claim was copied from or checked against a retrieved, reviewed excerpt", not
"the claim is legally correct". The corpus is a tiny implementer-authored
synthetic fixture set, so nothing here is a coverage or answer-quality claim;
`hit@5`-style thresholds remain unenforced. No Android/Desktop/Gradle check and
no browser/API/E2E check apply (no product UI, no `/ask` route, no persistent E2E
harness); the CLI is the manual smoke check for this slice.
