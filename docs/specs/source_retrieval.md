# Feature Spec: `source_retrieval`

## Source metadata

- Feature: `source_retrieval` — Search reviewed source passages
- Area: backend
- Depends on: `source_catalog_validation` (accepted)
- Feature-list behavior: a question retrieves relevant passages from the reviewed corpus with enough metadata to identify the source and its applicability.
- Feature-list verification: run source-anchored questions and confirm the expected source passage appears in the returned candidates.
- Feature-list note: start with a measured retrieval baseline before treating candidate thresholds as release gates.
- Scope size: one passage data model plus one offline retrieval flow; correctly sized.

## Goal

Provide a dependency-free, offline retrieval boundary that, given a plain-Spanish question, returns ranked candidate passages drawn only from **human-reviewed** documents whose provenance is already approved by the accepted source-catalog gate, together with enough metadata (source identity, location, dates, applicability, excerpt) to identify the source and its applicability. Establish a **measured** retrieval baseline (hit@k / MRR) on a small source-anchored evaluation set built from synthetic reviewed test passages, because the canonical catalog is intentionally empty and no ingestion/chunking pipeline exists.

## Non-goals

- Ingestion, download, parsing, OCR, chunking, embedding, vector stores, or automated/unreviewed corpus creation.
- Any network access, model provider, LLM call, prompt, generation, or `/ask` route.
- Applicability-based filtering or land-context selection; this feature only surfaces applicability metadata (filtering belongs to `minimal_land_context` / `land_clarification`).
- Client/Compose UI, contract changes, or `contracts/openapi.yaml` changes; the existing `AnswerSource` fields are reused, not redefined.
- Adding real legal documents or asserting any legal fact. All retrieval fixtures are synthetic, clearly labeled, and contain no real deadlines, amounts, or article claims.
- Treating baseline metrics as release gates. Thresholds are reported, not enforced.

## Job story

When a reviewed passage corpus exists, I want an offline retriever that only ever searches human-approved, current, unexpired sources, so that a later generation step can ground answers in traceable evidence — and I want a reproducible baseline run so the team can calibrate thresholds from measured numbers instead of inherited guesses.

## Acceptance scenarios

### Relevant question returns the expected passage

Given a fixture catalog of approved, current sources and a reviewed passage set referencing them, when a source-anchored fixture question is searched with candidate window `k`, then the expected passage appears in the returned candidates at rank ≤ `k`, ranked above unrelated passages.

### Candidates carry identifying metadata

Given a matching candidate, when it is returned, then it exposes the passage id, the source id, title, issuing body, official URL, location, publication/update date, verification date, applicability, the passage excerpt, and its score/rank — field names and semantics compatible with the accepted `AnswerSource` contract.

### Unreviewed or ineligible evidence is never returned

Given a passage whose source id is unknown, or whose source is not `approved`, not `current`, or expired as of the supplied `--as-of` date, when retrieval runs, then that passage is not returned (ineligible sources are excluded and counted; an unknown source id is a located load error), and retrieval never falls back to unreviewed content.

### Empty retained corpus returns no candidates

Given the canonical repository catalog is empty and no reviewed passage set is supplied, when retrieval runs, then it returns zero candidates without inventing evidence.

### Spanish, accent- and case-insensitive matching

Given a question that differs from the passage only in case or written accents (for example `solicitud unica` vs `solicitud única`), when it is searched, then the passage still matches.

### Reproducible measured baseline

Given the fixture catalog, passage set, and evaluation questions, when the baseline command runs with an explicit `--as-of` and `--k`, then it prints each question's expected-passage rank plus aggregate `hit@k` and MRR, and the run is deterministic across repeated invocations.

## Technical approach

### Passage-set contract

Add a readable, versioned contract `knowledge/passages.schema.json` (`passage-set-v1`) mirroring the catalog-schema style, plus its strict in-code validator. A passage-set document is:

```json
{
  "schema_version": "passage-set-v1",
  "passages": [
    {
      "id": "fixture-rd1048-art1-p1",
      "source_id": "rd_1048_2022",
      "location": "Art. 1",
      "text": "Fragmento sintético de prueba; no afirma ningún plazo real.",
      "critical": false,
      "applicability": { "crop": "olivar", "water_regime": "dryland" }
    }
  ]
}
```

Rules: top level has only `schema_version` and `passages`; every passage has non-blank `id` (unique), `source_id`, `location`, and `text`, plus optional `critical` (boolean) and `applicability` (same value rules as the catalog: `crop` non-blank, `water_regime` ∈ dryland/irrigated/mixed, `production_method` ∈ conventional/organic/mixed; omit unknown values). Unknown keys are rejected. The passage set is a Git-tracked, human-reviewed artifact. This feature ships the contract and fixtures only; the canonical `knowledge/passages.json` will be produced by a later reviewed ingestion feature, so no canonical passage file is created now.

### Retrieval index and scoring

Implement `backend/app/retrieval.py` as a pure, standard-library module (`json`, `re`, `math`, `unicodedata`, `dataclasses`, `datetime`):

- `tokenize(text)`: lowercase, strip diacritics via NFKD, split on non-alphanumerics, drop a small built-in Spanish stopword list.
- `Bm25Index`: BM25 with `k1 = 1.5`, `b = 0.75` over passage `text`; deterministic ordering with ties broken by passage `id`.
- `Retriever`: built from a catalog document, a passage-set document, and an `as_of` date; exposes `search(question, k=...) -> tuple[RetrievedPassage, ...]`.
- `RetrievedPassage`: `passage_id`, `source_id`, `title`, `issuing_body`, `url`, `location`, `published_or_updated_on`, `verified_on`, `excerpt`, `applicability`, `critical`, `score`, `rank`. Field names/semantics line up with the accepted `AnswerSource` so `grounded_answer_generation` can reuse them without redefining the contract.

A question with no tokens returns an empty tuple. Empty corpus, absent matches, and out-of-vocabulary questions return fewer than `k` candidates or none; retrieval never fabricates a passage.

### Eligibility and provenance

The retriever is a consumer of the accepted catalog gate:

- It reuses `validate_catalog` from `backend/app/source_catalog.py`; if the catalog is invalid it refuses to build an index (fail closed) rather than indexing partially approved data.
- A passage is indexed only when its `source_id` resolves to a catalog source that is `review_status: approved`, `lifecycle_status: current`, and not expired as of `as_of`. Ineligible sources are excluded from the index and reported as a count.
- A passage whose `source_id` does not exist in the catalog is a located load error (`PassageSetError` with a JSON path such as `$.passages[0].source_id`), never a silent skip.
- The loader never performs network access; tests enforce this with a socket guard.

### Baseline evaluation harness

Add `backend/scripts/evaluate_retrieval.py`, an offline CLI mirroring `validate_source_catalog.py`:

```
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints, per question, the expected-passage rank(s), then aggregate `hit@k`, `recall@k`, and MRR, with an optional `--json` mode. The eval file is JSONL: `{"question": "...", "expected_passage_ids": ["..."]}`. Exit codes: `0` report produced, `2` unreadable/invalid input. An explicit `--fail-on-miss` flag may exit `1` on a miss, but it is **off by default**: the feature-list note says candidate thresholds are not release gates yet.

## Expected file changes

- Create `knowledge/passages.schema.json` — versioned `passage-set-v1` readable contract.
- Create `backend/app/retrieval.py` — passage loading/eligibility, Spanish tokenizer, BM25 index, `Retriever`, `RetrievedPassage`.
- Create `backend/scripts/evaluate_retrieval.py` — offline baseline CLI (report-only by default).
- Create `backend/tests/test_retrieval.py` — focused tests.
- Create `backend/tests/fixtures/retrieval/` — fixture catalog (approved synthetic sources), reviewed synthetic passage set, JSONL evaluation questions, plus edge cases: unknown `source_id`, unknown key, malformed JSON, and an expired source.
- Update `knowledge/README.md` — document the passage-set contract, eligibility coupling to the catalog, and the baseline command.
- Update `backend/README.md` — note the offline retrieval module and baseline script (keep `/health` as the only route).
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with actual status, commands, and the measured baseline numbers. This planning pass records the spec link only.

`scripts/init.sh`: no change. It checks and verifies KMP targets only, so this backend/knowledge feature is verified with the documented Python commands instead of adding a long-running or KMP-coupled step to the wrapper.

No changes to `knowledge/source_catalog.json`, `backend/app/source_catalog.py`, `contracts/`, `backend/app/main.py`, or any client/shared code.

## Visual design impact

None. This is an offline backend boundary; it adds no Compose UI and no user-facing Spanish copy.

## Durable documentation impact

- `knowledge/README.md`: update; it is the durable operational contract for how reviewed passages relate to the approved catalog and how to run the baseline.
- `knowledge/passages.schema.json`: create; the durable, versioned passage format.
- `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`: no update; existing source-grounding, review, and UI rules already govern this work.
- `docs/archive/MasterPlanV3.md`: no update; it is planning context, while the schema/README become executable documentation.
- `ARCHITECTURE.md`, `CONSTRAINTS.md`: not needed; both are absent and this focused offline boundary does not establish a broader runtime architecture.
- `PROGRESS.md` and `feature_list.json`: update after verification, recording the measured fixture baseline and stating plainly that it is synthetic, not a legal-quality claim.

## Risks and handoff notes

The baseline measures lexical ranking quality on a tiny synthetic fixture set; it is not evidence about legal coverage, correctness, or real Spanish user questions. Missing ingestion means the passage model is exercised only by fixtures, so the schema may need review when a real parser/chunker lands. Lexical-only retrieval may underperform on synonyms and acronyms; the `Retriever` boundary is intentionally narrow so a later hybrid (vector + BM25 + RRF) implementation can replace `search` without changing consumers. Hand off the ranked `RetrievedPassage` shape and eligibility rules to `grounded_answer_generation`, and keep applicability filtering deferred to `minimal_land_context` / `land_clarification`.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5
./scripts/init.sh --backend-tests tests/test_retrieval.py
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/source_retrieval.appendix.md`](../archive/specs/source_retrieval.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/source_retrieval.md` remains the authoritative acceptance record.
