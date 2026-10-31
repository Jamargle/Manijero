# Validation: safe_abstention

## Verdict

**Accept** — independently validated against `docs/specs/safe_abstention.md` on
2026-10-13. No repair required. The four findings below are non-blocking and are
handed to the orchestrator.

Recommended state update (orchestrator-owned; not applied by the validator):
`feature_list.json` `safe_abstention` → `accepted`, with this record linked as
evidence. The validator did **not** mark it accepted and did **not** commit.

## Evidence

All commands were run from the repository root unless noted. Pytest ran with the
interpreter of a temporary virtualenv created **outside** the repository
(`$HOME/.mj_validate_venv`, Python 3.9.6, pytest 8.4.2) with the repo's own
`backend/requirements.txt` installed into it; no dependency was added to the repo.

- Focused suite: `cd backend && <venv>/bin/python -m pytest tests/test_abstention.py`
  → **178 passed**. Full suite: `cd backend && <venv>/bin/python -m pytest`
  → **399 passed** (221 existing + 178 new). Matches the recorded counts.
- Static: `python3 -m py_compile backend/app/abstention.py
  backend/scripts/evaluate_abstention.py backend/tests/test_abstention.py` → clean;
  `git diff --check` → clean.
- Current-corpus CLI: `python3 backend/scripts/evaluate_abstention.py --catalog
  backend/tests/fixtures/abstention/catalog.json --passages
  backend/tests/fixtures/abstention/passages.json --eval
  backend/tests/fixtures/abstention/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  → exit 0; `corpus: current`; eligible sources 2, indexed passages 7, excluded 0;
  3 answered, 7 abstained, `abstentions with sources: 0`, `abstentions with
  figures: 0`, `abstention invariants hold: yes`, `outcomes differing from expect: 0`.
  Every reason in the taxonomy appears with its frozen message:
  `no_evidence` (no_candidates), `conflicting_evidence` (unit_conflict, 30 vs 45
  días), `insufficient_evidence` (grounding_failed, uncited_sentence),
  `unsafe_request` (policy_failed, eligibility_claim), `false_premise` ×2
  (unconfirmed_presupposition), `invalid_question` (blank_question).
- Stale corpus: `--catalog backend/tests/fixtures/retrieval/catalog_expired.json
  --eval .../eval_questions_stale.jsonl --as-of 2026-10-13 --k 5` (no `--passages`)
  → exit 0; `corpus: not_current`; 0 answered, 3 abstained, **every** question
  `stale_evidence` with issue `stale_corpus`, `sources: 0`, and the pinned message.
  The same was independently reproduced via the CLI for
  `catalog_not_approved.json` and `catalog_not_current.json`.
- Hard errors stay hard: a malformed passage set (missing required keys) and an
  unknown `source_id` both exit **2** with empty stdout and a located JSON path;
  a missing passage file and a missing catalog both exit **2**. A structurally
  broken catalog (`sources: ["no-dict"]`), a catalog with a missing `sources` key,
  and an unknown extra source key each raise `CatalogRejectedError` → CLI exit 2.
  The canonical empty `knowledge/source_catalog.json` still prepares a `Retriever`
  with 0 eligible sources and 0 indexed passages.
- Contract: `python3 contracts/validate_examples.py` →
  "Validated 2 request and 3 response examples against answer_api_contract"
  (exit 0). All nine pinned-message payloads plus the three real pipeline
  abstentions were validated **independently** with `jsonschema` against
  `contracts/openapi.yaml#/components/schemas/AskResponse` (dereferenced
  `AnswerSource`): every payload has exactly
  `{status, answer, sources, land_scope, land_ids_to_choose}`, `status: abstained`,
  `sources: []`, `land_ids_to_choose: []`, a non-blank `answer` ≤ 1200; the
  answered payload still validates. Payload keys equal the keys of
  `contracts/examples/response-abstained.json`.
- Pinned copy is byte-for-byte the spec: all nine `ABSTENTION_MESSAGES` entries
  were parsed out of `docs/specs/safe_abstention.md` and compared — **byte-equal**.
  Every message is non-blank, ≤ 1200 chars, contains no digit, yields
  `extract_figures(...) == frozenset()`, contains no `ELIGIBILITY_PHRASES`, and
  ends with a next step (`oficina comarcal agraria` / `cooperativa` /
  `inténtalo otra vez`).
- Acceptance scenarios reproduced with questions the validator authored itself
  (not the fixture questions), on the fixture corpus:
  - out-of-corpus `¿Cuánto cuesta matricular un tractor viejo?` →
    `no_evidence`, generation reason `no_candidates`, `sources: []`,
    `land_ids_to_choose: []`, pinned digitless/dateless message;
  - false premise `¿Qué dice el Real Decreto 123/2099 sobre el plazo de la
    solicitud?` → `false_premise`, code `unconfirmed_presupposition`, and the
    emitted message contains neither `real decreto` nor `123`/`2099`; the
    identifier *present* in a candidate (`¿Qué dice la norma ficticia?`) still
    answers. Crafted candidates confirmed the boundary cases: `ley 5/2020` present
    → not flagged; absent → flagged; the same number under a different instrument
    → flagged; identifier present only in `location` → not flagged;
  - two `critical` candidates on different units (`días` vs `euros`) still answer
    with critical sources — no over-abstention of the accepted covered case;
  - generator provenance: a recording generator was **never called** for
    `invalid_question`, `no_evidence`, `false_premise`, and `conflicting_evidence`
    (0 calls each); an abstaining generator → `generator_abstained`; an exploding
    generator → `generation_error`; a rejected draft's text never appears in the
    payload for either path.
- Determinism: two `--json` runs are byte-identical (`cmp` exit 0, sha256
  `f8ed61c3ff977cbf30c749d3a19a14aeb82e0f4c836391ac5f890ff974f9db9e`,
  an independent digest); `PYTHONHASHSEED=1` vs `PYTHONHASHSEED=98765` runs are
  byte-identical; three in-process repeats produced identical payloads.
- Offline: an independent, stricter socket guard (patching `socket.socket`,
  `socket.create_connection`, `socket.getaddrinfo`, and `socket.socketpair` to
  raise) still abstained and still answered; `abstention.py` contains no
  `open(`/`read_text`/`socket`/`urllib`/`httpx`/`requests` and reads no file.
- Content-silent: issue diagnostics never contain the question text, the excerpt
  text, the rejected draft, or a figure number; the CLI's stderr for a malformed
  eval line containing a secret marker (`SECRETO-CONTENIDO-987`) did not echo it.
- Exit contract: `--fail-on-miss` on a deliberately mismatched expectation exits
  **1** while the same run without the flag exits **0** and prints identical
  output; `--k 0` exits 2 (`--k must be a positive integer`); a malformed eval
  line and an eval file with no questions exit 2 with empty stdout.
- Regression baselines unchanged: generation CLI → exit 0, `5 answers, 8 claims,
  0 ungrounded, 1 no-evidence`; retrieval CLI → `hit@5 = 0.857 (6/7)`,
  `recall@5 = 0.857`, `MRR = 0.857`; the accepted generation fixture questions
  re-run through `answer_or_abstain` still resolve as their `expect` says
  (5 answered, 1 `no_evidence`).
- Scope confirmed by `git status --porcelain`: outside the new feature files, only
  `backend/README.md`, `CONSTRAINTS.md`, `PROGRESS.md`, and `feature_list.json`
  changed. `contracts/`, `backend/app/generation.py`, `backend/app/retrieval.py`,
  `backend/app/source_catalog.py`, `backend/app/main.py`,
  `backend/scripts/evaluate_generation.py`, `backend/tests/test_generation.py`,
  `knowledge/`, `backend/requirements.txt`, `scripts/init.sh`, and all client/shared code
  are unmodified. `backend/app/main.py` still declares exactly one route,
  `GET /health`. Fixtures are synthetic and labelled (`fixture`, `no es una norma
  real`, `Sintético`, `cifra inventada`) with a deliberately impossible
  `999/2099` reference and no real deadline, amount, or article number.

## Findings (non-blocking)

- **N1 — Evidence wording (low).** `feature_list.json` and `PROGRESS.md` state
  "`git status --porcelain` shows only `backend/README.md` and `CONSTRAINTS.md`
  modified". At recording time `PROGRESS.md` and `feature_list.json` were also
  modified. The substantive claim (no source, contract, knowledge, or client file
  touched) is verified true; the sentence is imprecise. Suggested change: say
  "only `backend/README.md` and `CONSTRAINTS.md` changed outside the feature
  tracking files". Owner: orchestrator/next implementer, cosmetic.
- **N2 — Malformed catalog fields fall into `stale_evidence` (low, disclosed).**
  A catalog whose sources are structurally well-formed but semantically invalid
  (missing `review_status`, unparseable `valid_until`) yields a corpus-level
  `stale_evidence` (CLI exit 0) instead of a hard error. Verified directly:
  `missing review_status` → `Abstention: stale_evidence`; `malformed valid_until`
  → `Abstention: stale_evidence`. This matches the spec's rule 6 as written
  (non-`approved` ⇒ stale) and fails safe, and it is already disclosed in the
  recorded honest gaps. Suggested owner: a later catalog-hardening slice (or
  `land_safety_evaluation`) if an operator should be told loudly about a
  malformed catalog. Not required by this spec.
- **N3 — Fixture hygiene (low).** `backend/tests/test_abstention.py:553` uses
  `("¿Qué dice la ley 7/2022?", "ley 7/2022")`. That number coincides with a real
  Spanish statute. It is a pure extractor unit-test literal (no legal content is
  asserted, and it is not in any fixture or corpus), but for consistency with the
  spec's synthetic-only fixture policy an impossible identifier (e.g. `999/2099`)
  would be preferable.
- **N4 — Lexical containment over-match (informational).** `has_unsupported_
  presupposition` uses plain substring containment, so a presupposed `ley` would
  be treated as confirmed by a candidate containing e.g. `leyenda`. This can only
  cause under-abstention, is exactly the lexical behaviour the spec prescribes,
  and cannot emit an invented fact because the accepted generator remains
  extractive and verifies grounding. Worth measuring in `land_safety_evaluation`.

## Security assessment

Feature-scoped review found no security issue. The module is standard-library
only, performs no network access (independently socket-guarded), reads no files,
adds no route (`GET /health` remains the only one), adds no dependency, and adds no
logging. Abstention copy is code-owned and cannot be injected by a caller (no text
field on `Abstention`; the payload resolves the frozen message by reason; an
unknown reason or land scope raises `ValueError` rather than emitting).
Diagnostics and CLI errors are content-silent: no question text, excerpt, draft,
figure, or land data is echoed. The fail-closed direction is correct — a
presupposition miss, a shared-unit critical pair, and any ineligible catalog all
abstain rather than answer, and a rejected draft is discarded whole.

## Documentation and harness state

- `backend/README.md` (abstention boundary, taxonomy table, CLI, `/health` still the
  only route) and `CONSTRAINTS.md` (one new Abstention MUST rule: never carry a
  source, figure, or date; copy is code-owned) are updated correctly and match the
  implemented behaviour — verified by reading both diffs and by triggering the
  described behaviour.
- `docs/validations/safe_abstention.md` (this record) is new.
- `AGENTS.md`, `ARCHITECTURE.md` (absent), `knowledge/README.md`, `CONTEXT.md`,
  `docs/*`, `docs/archive/MasterPlanV3.md`, and `DESIGN.md` were correctly left untouched, per
  the spec's Durable Documentation Impact section.
- `scripts/init.sh` was not changed and was not run: the spec mandates no change and this
  backend slice has no `scripts/init.sh` backend command. No persistent E2E harness exists
  and no `/ask` route exists, so no E2E/browser check is applicable.
